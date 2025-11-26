"""Model Manager - Versioned Probability Model Management.

This module manages versioned probability models with immutable configurations
following the Immutable Version Pattern (REQ-VER-001, REQ-VER-002).

Educational Note:
    Models use IMMUTABLE versions for A/B testing and precise trade attribution.
    When you need to change a model's parameters:
    - Don't modify existing config (IMMUTABLE!)
    - Create new version: v1.0 → v1.1 (calibration) or v1.0 → v2.0 (algorithm change)
    - This ensures every trade knows EXACTLY which model was used

References:
    - REQ-VER-001: Immutable Version Configs
    - REQ-VER-002: Semantic Versioning
    - REQ-VER-003: Trade Attribution (100% of trades link to exact versions)
    - REQ-VER-004: Version Lifecycle Management
    - REQ-VER-005: A/B Testing Support
    - ADR-018: Immutable Strategy Versions (applies to models too)
    - ADR-019: Semantic Versioning for Strategies (applies to models too)
    - docs/guides/VERSIONING_GUIDE_V1.0.md
    - docs/database/DATABASE_SCHEMA_SUMMARY_V1.10.md (probability_models table with model_class/domain fields)

Phase: 1.5 (Foundation Validation)
"""

import json
from decimal import Decimal
from typing import Any, cast

import psycopg2

from precog.database.connection import get_connection, release_connection
from precog.utils.logger import get_logger

logger = get_logger(__name__)


class ImmutabilityError(Exception):
    """Raised when attempting to modify immutable model config.

    Educational Note:
        Model configs are IMMUTABLE once created. This prevents accidental
        changes that would invalidate past predictions and break trade attribution.

        To change a model's parameters, create a new version instead.
    """


class InvalidStatusTransitionError(Exception):
    """Raised when attempting invalid status transition.

    Educational Note:
        Models follow a lifecycle: draft → testing → active → deprecated
        Not all transitions are valid (e.g., can't go from deprecated back to active)
    """


class ModelManager:
    """Manages versioned probability models with immutable configurations.

    Educational Note:
        This class provides CRUD operations for probability models while enforcing
        immutability of model configurations. Once a model version is created, its
        config cannot be changed - only status and metrics can be updated.

        Why immutability?
        - A/B testing: Compare v1.0 vs v1.1 calibration
        - Trade attribution: Know exactly which model generated each prediction
        - Audit trails: No ambiguity about which config was used when

    Database Schema:
        Table: probability_models
        - model_id (PK, SERIAL)
        - model_name (VARCHAR, e.g., 'elo_nfl')
        - model_version (VARCHAR, e.g., 'v1.0', 'v1.1', 'v2.0')
        - approach (VARCHAR, e.g., 'elo', 'ensemble', 'ml', 'hybrid')
        - domain (VARCHAR, nullable, e.g., 'nfl', 'ncaaf', 'nba')
        - config (JSONB, IMMUTABLE)
        - description (TEXT, nullable)
        - status (VARCHAR, MUTABLE, default 'draft')
        - validation_calibration (DECIMAL, MUTABLE, nullable)
        - validation_accuracy (DECIMAL, MUTABLE, nullable)
        - validation_sample_size (INTEGER, MUTABLE, nullable)
        - created_at (TIMESTAMP, auto)
        - created_by (VARCHAR, nullable)
        - notes (TEXT, nullable)
        - UNIQUE(model_name, model_version)

    References:
        - REQ-VER-001: Immutable Version Configs
        - REQ-VER-004: Version Lifecycle Management
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.10.md (probability_models table with model_class/domain fields)
    """

    def create_model(
        self,
        model_name: str,
        model_version: str,
        model_class: str,
        config: dict[str, Any],
        domain: str | None = None,
        description: str | None = None,
        status: str = "draft",
        created_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create new model version.

        Args:
            model_name: Model identifier (e.g., 'elo_nfl')
            model_version: Semantic version (e.g., 'v1.0', 'v1.1', 'v2.0')
            model_class: Valid model class code from model_classes lookup table.
                Initial values: 'elo', 'ensemble', 'ml', 'hybrid', 'regression', 'neural_net', 'baseline'
                Query available classes: SELECT * FROM model_classes WHERE is_active = TRUE
                (Constraint enforced by FK - see Migration 023)
            config: Model parameters (IMMUTABLE once created!)
            domain: WHICH markets ('nfl', 'ncaaf', 'nba', etc.) or None for multi-domain
            description: Human-readable description (optional)
            status: Initial status (default 'draft')
            created_by: Creator identifier (optional)
            notes: Additional notes (optional)

        Returns:
            Created model as dict with all fields

        Raises:
            psycopg2.IntegrityError: If model_name + model_version already exists
            psycopg2.ForeignKeyViolation: If model_class is not in model_classes table
            ValueError: If config is invalid

        Educational Note:
            Config is IMMUTABLE after creation. To change model parameters:
            1. Create NEW version (v1.0 → v1.1 or v2.0)
            2. Update status on old version (active → deprecated)
            3. Update status on new version (draft → testing → active)

            This ensures:
            - Every prediction links to exact model config used
            - A/B testing: Compare v1.0 vs v1.1 calibration
            - No ambiguity about which parameters generated which predictions

        Example:
            >>> manager = ModelManager()
            >>> model = manager.create_model(
            ...     model_name="elo_nfl",
            ...     model_version="v1.0",
            ...     model_class="elo",
            ...     config={
            ...         "k_factor": Decimal("32.0"),
            ...         "home_advantage": Decimal("55.0"),
            ...         "mean_reversion": Decimal("0.33")
            ...     },
            ...     domain="nfl",
            ...     description="NFL Elo model with home field advantage"
            ... )
            >>> model['model_id']  # Returns generated ID
            1

        References:
            - REQ-VER-001: Immutable Version Configs
            - REQ-VER-002: Semantic Versioning
            - Pattern 1 (CLAUDE.md): Decimal Precision
            - Migration 023: model_classes lookup table and FK constraint
        """
        # Validate config is not empty
        if not config:
            raise ValueError("Model config cannot be empty")

        # Prepare config for JSONB storage (Decimal → string)
        config_jsonb = self._prepare_config_for_db(config)

        conn = get_connection()
        cursor = conn.cursor()

        try:
            insert_sql = """
                INSERT INTO probability_models (
                    model_name, model_version, model_class, domain, config,
                    description, status, created_by, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING model_id, model_name, model_version, model_class,
                          domain, config, description, status, validation_calibration, validation_accuracy,
                          validation_sample_size, created_at, created_by, notes
            """

            cursor.execute(
                insert_sql,
                (
                    model_name,
                    model_version,
                    model_class,
                    domain,
                    config_jsonb,
                    description,
                    status,
                    created_by,
                    notes,
                ),
            )

            row = cursor.fetchone()
            conn.commit()

            logger.info(
                f"Created model {model_name} {model_version}",
                extra={"model_id": row[0], "status": status},
            )

            return self._row_to_dict(cursor, row)

        except psycopg2.IntegrityError as e:
            conn.rollback()
            logger.error(
                f"Model {model_name} {model_version} already exists",
                extra={"error": str(e)},
            )
            raise

        finally:
            cursor.close()
            release_connection(conn)

    def get_model(
        self,
        model_id: int | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieve model by ID or by name+version.

        Args:
            model_id: Model primary key (exclusive with model_name+model_version)
            model_name: Model identifier (requires model_version)
            model_version: Model version (requires model_name)

        Returns:
            Model as dict, or None if not found

        Raises:
            ValueError: If neither ID nor name+version provided, or if only one of name/version provided

        Educational Note:
            Config returned as dict with Decimal values (Pattern 1 compliance).
            Database stores as JSONB strings, we convert back to Decimal.

        Example:
            >>> model = manager.get_model(model_id=1)
            >>> model = manager.get_model(model_name='nfl_elo_v1', model_version='1.0')
        """
        # Validate parameters
        if model_id is not None and (model_name is not None or model_version is not None):
            raise ValueError("Provide either model_id OR model_name+model_version, not both")

        if model_id is None and (model_name is None or model_version is None):
            raise ValueError("Provide either model_id OR both model_name and model_version")

        conn = get_connection()
        cursor = conn.cursor()

        try:
            if model_id is not None:
                # Query by ID
                select_sql = """
                    SELECT model_id, model_name, model_version, model_class,
                           domain, config, description, status, validation_calibration, validation_accuracy,
                           validation_sample_size, created_at, created_by, notes
                    FROM probability_models
                    WHERE model_id = %s
                """
                cursor.execute(select_sql, (model_id,))
            else:
                # Query by name+version
                select_sql = """
                    SELECT model_id, model_name, model_version, model_class,
                           domain, config, description, status, validation_calibration, validation_accuracy,
                           validation_sample_size, created_at, created_by, notes
                    FROM probability_models
                    WHERE model_name = %s AND model_version = %s
                """
                cursor.execute(select_sql, (model_name, model_version))

            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_dict(cursor, row)

        finally:
            cursor.close()
            release_connection(conn)

    def get_models_by_name(self, model_name: str) -> list[dict[str, Any]]:
        """Get all versions of a model by name.

        Args:
            model_name: Model identifier (e.g., 'elo_nfl')

        Returns:
            List of all versions, ordered by created_at DESC (newest first)

        Educational Note:
            Returns ALL versions of this model, regardless of status.
            Use this to compare performance across versions (A/B testing).

        Example:
            >>> models = manager.get_models_by_name('elo_nfl')
            >>> for model in models:
            ...     print(f"{model['model_version']}: {model['validation_calibration']}")
            v1.1: 0.0523
            v1.0: 0.0687
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            select_sql = """
                SELECT model_id, model_name, model_version, model_class,
                       domain, config, description, status, validation_calibration, validation_accuracy,
                       validation_sample_size, created_at, created_by, notes
                FROM probability_models
                WHERE model_name = %s
                ORDER BY created_at DESC
            """

            cursor.execute(select_sql, (model_name,))
            rows = cursor.fetchall()

            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def get_active_models(self) -> list[dict[str, Any]]:
        """Get all active models (status='active').

        Returns:
            List of active models across all names and versions

        Educational Note:
            Active models are used for live predictions.
            You can have multiple active models (e.g., elo_nfl v1.0 AND v1.1)
            for A/B testing purposes.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            select_sql = """
                SELECT model_id, model_name, model_version, model_class,
                       domain, config, description, status, validation_calibration, validation_accuracy,
                       validation_sample_size, created_at, created_by, notes
                FROM probability_models
                WHERE status = 'active'
                ORDER BY model_name, created_at DESC
            """

            cursor.execute(select_sql)
            rows = cursor.fetchall()

            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def list_models(
        self,
        status: str | None = None,
        domain: str | None = None,
        model_class: str | None = None,
    ) -> list[dict[str, Any]]:
        """List models with optional filters.

        Args:
            status: Filter by status (optional)
            domain: Filter by domain (optional)
            model_class: Filter by model class (optional)

        Returns:
            List of models matching filters, ordered by created_at DESC

        Educational Note:
            This method supports flexible querying for models.
            - No filters: Returns ALL models
            - Single filter: Returns models matching that filter
            - Multiple filters: Returns models matching ALL filters (AND logic)

        Example:
            >>> # Get all active NFL Elo models
            >>> models = manager.list_models(status='active', domain='nfl', model_class='elo')
            >>> # Get all models (no filters)
            >>> all_models = manager.list_models()
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Build dynamic WHERE clause
            where_clauses: list[str] = []
            params: list[str] = []

            if status is not None:
                where_clauses.append("status = %s")
                params.append(status)

            if domain is not None:
                where_clauses.append("domain = %s")
                params.append(domain)

            if model_class is not None:
                where_clauses.append("model_class = %s")
                params.append(model_class)

            # Construct SQL
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            select_sql = f"""
                SELECT model_id, model_name, model_version, model_class,
                       domain, config, description, status, validation_calibration, validation_accuracy,
                       validation_sample_size, created_at, created_by, notes
                FROM probability_models
                {where_sql}
                ORDER BY created_at DESC
            """

            cursor.execute(select_sql, params)
            rows = cursor.fetchall()

            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def update_status(self, model_id: int, new_status: str) -> dict[str, Any]:
        """Update model status (MUTABLE field) with transition validation.

        Args:
            model_id: Model to update
            new_status: New status value

        Returns:
            Updated model as dict

        Raises:
            ValueError: If model not found
            InvalidStatusTransitionError: If transition is invalid

        Educational Note:
            Status is MUTABLE (unlike config). Valid transitions:
            - draft → testing (start backtesting)
            - testing → active (promote to production)
            - testing → draft (revert to development)
            - active → deprecated (retire old version)
            - deprecated → [none] (terminal state)

            Config remains IMMUTABLE. To change model parameters,
            create new version instead.

        Example:
            >>> model = manager.update_status(1, 'testing')  # draft → testing
            >>> model = manager.update_status(1, 'active')   # testing → active
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get current status for validation
            cursor.execute("SELECT status FROM probability_models WHERE model_id = %s", (model_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(
                    f"Model {model_id} not found "
                    f"(operation=update_status, target_status={new_status})"
                )

            current_status = row[0]

            # Validate transition
            self._validate_status_transition(current_status, new_status)

            # Update status
            update_sql = """
                UPDATE probability_models
                SET status = %s
                WHERE model_id = %s
                RETURNING model_id, model_name, model_version, model_class,
                          domain, config, description, status, validation_calibration, validation_accuracy,
                          validation_sample_size, created_at, created_by, notes
            """

            cursor.execute(update_sql, (new_status, model_id))
            row = cursor.fetchone()
            conn.commit()

            logger.info(f"Updated model {model_id} status: {current_status} -> {new_status}")

            return self._row_to_dict(cursor, row)

        finally:
            cursor.close()
            release_connection(conn)

    def update_metrics(
        self,
        model_id: int,
        validation_calibration: Decimal | None = None,
        validation_accuracy: Decimal | None = None,
        validation_sample_size: int | None = None,
    ) -> dict[str, Any]:
        """Update model performance metrics (MUTABLE fields).

        Args:
            model_id: Model to update
            validation_calibration: Brier score / log loss (optional)
            validation_accuracy: Overall accuracy (optional)
            validation_sample_size: Number of samples made (optional)

        Returns:
            Updated model as dict

        Raises:
            ValueError: If model not found or no metrics provided

        Educational Note:
            Config is IMMUTABLE, but metrics are MUTABLE.
            Why? Calibration changes as predictions accumulate, but config stays fixed.

            This separation enables:
            - Tracking performance of each version independently
            - A/B testing (compare v1.0 vs v1.1 calibration)
            - Knowing EXACTLY which config generated which calibration

        Example:
            >>> model = manager.update_metrics(
            ...     model_id=1,
            ...     validation_calibration=Decimal("0.0523"),
            ...     validation_accuracy=Decimal("0.6789"),
            ...     validation_sample_size=1000
            ... )

        References:
            - REQ-VER-005: A/B Testing Support
        """
        if all(
            v is None for v in [validation_calibration, validation_accuracy, validation_sample_size]
        ):
            raise ValueError("At least one metric must be provided")

        # Build dynamic UPDATE
        updates: list[str] = []
        params: list[Decimal | int] = []

        if validation_calibration is not None:
            updates.append("validation_calibration = %s")
            params.append(validation_calibration)

        if validation_accuracy is not None:
            updates.append("validation_accuracy = %s")
            params.append(validation_accuracy)

        if validation_sample_size is not None:
            updates.append("validation_sample_size = %s")
            params.append(validation_sample_size)

        params.append(model_id)

        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Safe: updates list contains ONLY hardcoded column names (lines 480-488),
            # never user input. All values use parameterized queries (%s placeholders).
            update_sql = f"""
                UPDATE probability_models
                SET {", ".join(updates)}
                WHERE model_id = %s
                RETURNING model_id, model_name, model_version, model_class,
                          domain, config, description, status, validation_calibration, validation_accuracy,
                          validation_sample_size, created_at, created_by, notes
            """

            cursor.execute(update_sql, params)
            row = cursor.fetchone()

            if not row:
                # Build context of which metrics were being updated
                metrics_attempted = ", ".join(updates)
                raise ValueError(
                    f"Model {model_id} not found "
                    f"(operation=update_metrics, attempted_updates=[{metrics_attempted}])"
                )

            conn.commit()

            logger.info(
                f"Updated model {model_id} metrics",
                extra={
                    k: v
                    for k, v in zip(
                        ["calibration", "accuracy", "sample_size"],
                        [validation_calibration, validation_accuracy, validation_sample_size],
                        strict=False,
                    )
                    if v is not None
                },
            )

            return self._row_to_dict(cursor, row)

        finally:
            cursor.close()
            release_connection(conn)

    def _prepare_config_for_db(self, config: dict[str, Any]) -> str:
        """Convert config dict to JSONB-safe format (Decimal → string).

        Args:
            config: Model configuration with Decimal values

        Returns:
            JSON string ready for JSONB storage

        Educational Note:
            PostgreSQL JSONB doesn't natively support Python Decimal.
            We store as string: Decimal("32.0") → "32.0" in database
            Then reverse on retrieval: "32.0" → Decimal("32.0")

            Pattern 1 compliance: Application ALWAYS uses Decimal, never float

            Example:
                Input:  {"k_factor": Decimal("32.0")}
                Output: '{"k_factor": "32.0"}'  (JSON string)

        References:
            - Pattern 1 (CLAUDE.md): Decimal Precision
        """

        # Convert Decimal to string for JSONB storage
        def decimal_to_str(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, dict):
                return {k: decimal_to_str(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [decimal_to_str(item) for item in obj]
            return obj

        config_str = decimal_to_str(config)
        return json.dumps(config_str)

    def _row_to_dict(self, cursor, row: tuple) -> dict[str, Any]:
        """Convert database row tuple to dict with column names.

        Args:
            cursor: Database cursor with description
            row: Tuple of values from fetchone()

        Returns:
            Dict mapping column names to values

        Educational Note:
            Automatically converts config from JSONB string → Decimal
            using _parse_config_from_db(). Application always sees Decimal,
            never float (Pattern 1 compliance).
        """
        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row, strict=False))

        # Convert config back to Decimal values
        if result.get("config"):
            result["config"] = self._parse_config_from_db(result["config"])

        return result

    def _parse_config_from_db(self, config: dict[str, Any]) -> dict[str, Any]:
        """Convert config from database format (string → Decimal).

        Args:
            config: Config dict from database (strings for numeric values)

        Returns:
            Config dict with Decimal values

        Educational Note:
            We store Decimals as strings in JSONB: Decimal("32.0") → "32.0"
            This method reverses that: "32.0" → Decimal("32.0")
            Pattern 1 compliance: Application always uses Decimal, never float.
        """

        def str_to_decimal(obj: Any) -> Any:
            if isinstance(obj, str):
                # Try to convert numeric strings to Decimal
                try:
                    return Decimal(obj)
                except (ValueError, TypeError, ArithmeticError):
                    return obj  # Return as-is if not numeric
            elif isinstance(obj, dict):
                return {k: str_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [str_to_decimal(item) for item in obj]
            return obj

        return cast("dict[str, Any]", str_to_decimal(config))

    def _validate_status_transition(self, current: str, new: str):
        """Validate status transition is allowed.

        Args:
            current: Current status
            new: Desired new status

        Raises:
            InvalidStatusTransitionError: If transition is invalid

        Educational Note:
            Models follow a lifecycle:
            - draft → testing (start backtesting)
            - testing → active (promote to production) OR testing → draft (revert)
            - active → deprecated (retire)
            - deprecated → [none] (terminal state, no way back)

            Invalid transitions:
            - deprecated → active (can't resurrect deprecated models)
            - active → testing (can't go backwards)
        """
        # Define valid transitions
        valid_transitions = {
            "draft": ["testing", "draft"],
            "testing": ["active", "draft"],
            "active": ["deprecated"],
            "deprecated": [],  # Terminal state
        }

        if new not in valid_transitions.get(current, []):
            raise InvalidStatusTransitionError(
                f"Invalid transition: {current} → {new}. "
                f"Valid transitions from {current}: {valid_transitions.get(current, [])}"
            )
