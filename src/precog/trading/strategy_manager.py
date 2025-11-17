"""Strategy Manager - Versioned Trading Strategy Management.

This module manages versioned trading strategies with immutable configurations
following the Immutable Version Pattern (REQ-VER-001, REQ-VER-002).

Educational Note:
    Strategies use IMMUTABLE versions for A/B testing and precise trade attribution.
    When you need to change a strategy's parameters:
    - Don't modify existing config (IMMUTABLE!)
    - Create new version: v1.0 → v1.1 (bug fix) or v1.0 → v2.0 (major change)
    - This ensures every trade knows EXACTLY which config was used

References:
    - REQ-VER-001: Immutable Version Configs
    - REQ-VER-002: Semantic Versioning
    - REQ-VER-003: Trade Attribution (100% of trades link to exact versions)
    - REQ-VER-004: Version Lifecycle Management
    - REQ-VER-005: A/B Testing Support
    - ADR-018: Immutable Strategy Versions
    - ADR-019: Semantic Versioning for Strategies
    - docs/guides/VERSIONING_GUIDE_V1.0.md
    - docs/database/DATABASE_SCHEMA_SUMMARY_V1.9.md (strategies table with approach/domain fields)

Phase: 1.5 (Foundation Validation)
"""

import json
from decimal import Decimal
from typing import Any, cast

from sqlalchemy.exc import IntegrityError

from precog.database.connection import get_connection, release_connection
from precog.utils.logger import get_logger

logger = get_logger(__name__)


class ImmutabilityError(Exception):
    """Raised when attempting to modify immutable strategy config.

    Educational Note:
        This error prevents a critical bug: changing config after creation
        would break trade attribution. We need to know EXACTLY which config
        generated each trade for A/B testing and performance analysis.

        If you see this error: Create a new version instead!
    """


class InvalidStatusTransitionError(Exception):
    """Raised when attempting invalid status transition.

    Valid transitions:
        - draft → testing → active
        - active → inactive → deprecated
        - testing → draft (revert to draft)

    Invalid transitions:
        - deprecated → active (can't reactivate deprecated)
        - active → testing (can't go backwards)
    """


class StrategyManager:
    """Manages versioned trading strategies with immutable configurations.

    This class provides CRUD operations for strategies with strict immutability
    enforcement. Strategy configs are IMMUTABLE once created - to change parameters,
    create a new version.

    Educational Note:
        Why immutability? Imagine you have strategy v1.0 that made 100 trades.
        If you modify v1.0's config, you can't analyze those 100 trades anymore
        (you don't know which config they used!). Immutability solves this:
        - v1.0 config never changes
        - v1.1 is new version with different config
        - Each trade knows exactly which version it used

    Usage:
        ```python
        manager = StrategyManager()

        # Create strategy v1.0
        strategy = manager.create_strategy(
            strategy_name="halftime_entry",
            strategy_version="v1.0",
            approach="entry",
            domain="nfl",
            config={"min_edge": Decimal("0.05"), "max_spread": Decimal("0.08")},
            description="Enter positions at halftime when leading by 7+ points"
        )

        # Update status (MUTABLE)
        manager.update_status(strategy.strategy_id, "active")

        # Update metrics (MUTABLE)
        manager.update_metrics(
            strategy.strategy_id,
            paper_roi=Decimal("0.15"),
            paper_trades_count=42
        )

        # ❌ CAN'T modify config!
        # manager.update_config(strategy.strategy_id, {...})  # Raises ImmutabilityError

        # ✅ Create new version instead
        v1_1 = manager.create_strategy(
            strategy_name="halftime_entry",
            strategy_version="v1.1",  # New version
            approach="entry",
            domain="nfl",
            config={"min_edge": Decimal("0.10"), "max_spread": Decimal("0.08")},  # Different config
            description="Increased min_edge based on backtest results"
        )
        ```

    Attributes:
        None (stateless, uses database connection)

    Trade-offs:
        **Why not use ORM models?**
        - Pros: Type safety, IDE autocomplete, relationship management
        - Cons: Additional abstraction layer, overhead for simple CRUD
        - Decision: Use raw SQL for Phase 1.5, evaluate ORM for Phase 2+
          when we have complex relationships (strategies → trades → positions)

    References:
        - docs/guides/VERSIONING_GUIDE_V1.0.md - Complete versioning patterns
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.8.md - strategies table schema
    """

    def __init__(self):
        """Initialize Strategy Manager.

        Educational Note:
            Manager is stateless - doesn't hold database connection.
            Each method gets fresh connection for thread safety.
        """

    def create_strategy(
        self,
        strategy_name: str,
        strategy_version: str,
        approach: str,
        config: dict[str, Any],
        domain: str | None = None,
        description: str | None = None,
        status: str = "draft",
        created_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create new strategy version.

        Args:
            strategy_name: Strategy identifier (e.g., 'halftime_entry')
            strategy_version: Semantic version (e.g., 'v1.0', 'v1.1', 'v2.0')
            approach: HOW strategy works ('entry', 'exit', 'sizing', 'hedging', 'value', 'arbitrage')
            config: Strategy parameters (IMMUTABLE once created!)
            domain: WHICH markets ('nfl', 'nba', etc.) or None for multi-domain
            description: Human-readable description
            status: Initial status (default: 'draft')
            created_by: Creator identifier
            notes: Additional notes

        Returns:
            Dictionary containing created strategy with all fields

        Raises:
            IntegrityError: If (strategy_name, strategy_version) already exists
            ValueError: If config is empty or None

        Educational Note:
            Config must contain Decimal values for all prices/probabilities!
            Example CORRECT config:
                {"min_edge": Decimal("0.05"), "max_spread": Decimal("0.08")}
            Example WRONG config:
                {"min_edge": 0.05, "max_spread": 0.08}  # Floats not allowed!

        References:
            - REQ-VER-001: Immutable Version Configs
            - REQ-SYS-003: Decimal Precision (ALWAYS use Decimal for prices)
            - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
        """
        # Validation
        if not config:
            raise ValueError("Strategy config cannot be empty")

        # Convert config to JSONB (with Decimal → string conversion)
        config_jsonb = self._prepare_config_for_db(config)

        # Insert strategy
        conn = get_connection()
        cursor = conn.cursor()

        try:
            insert_sql = """
                INSERT INTO strategies (
                    strategy_name, strategy_version, approach, domain,
                    config, description, status, created_by, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING strategy_id, strategy_name, strategy_version, approach,
                          domain, config, description, status, paper_roi, live_roi,
                          paper_trades_count, live_trades_count, created_at, created_by, notes
            """

            cursor.execute(
                insert_sql,
                (
                    strategy_name,
                    strategy_version,
                    approach,
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
                f"Created strategy {strategy_name} {strategy_version}",
                extra={"strategy_id": row[0], "status": status},
            )

            return self._row_to_dict(cursor, row)

        except IntegrityError as e:
            conn.rollback()
            logger.error(
                f"Strategy {strategy_name} {strategy_version} already exists",
                extra={"error": str(e)},
            )
            raise

        finally:
            cursor.close()
            release_connection(conn)

    def get_strategy(self, strategy_id: int) -> dict[str, Any] | None:
        """Retrieve strategy by ID.

        Args:
            strategy_id: Strategy primary key

        Returns:
            Strategy dict with all fields, or None if not found

        Educational Note:
            Config field contains JSONB - already converted from database.
            Decimal values stored as strings in JSONB, converted back here.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            select_sql = """
                SELECT strategy_id, strategy_name, strategy_version, approach,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes
                FROM strategies
                WHERE strategy_id = %s
            """

            cursor.execute(select_sql, (strategy_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_dict(cursor, row)
            return None

        finally:
            cursor.close()
            release_connection(conn)

    def get_strategies_by_name(self, strategy_name: str) -> list[dict[str, Any]]:
        """Get all versions of a strategy.

        Args:
            strategy_name: Strategy identifier

        Returns:
            List of strategy dicts, ordered by version DESC (newest first)

        Educational Note:
            Returns ALL versions (v1.0, v1.1, v2.0, etc.) regardless of status.
            Use get_active_strategies() to filter by status='active'.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            select_sql = """
                SELECT strategy_id, strategy_name, strategy_version, approach,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes
                FROM strategies
                WHERE strategy_name = %s
                ORDER BY strategy_version DESC
            """

            cursor.execute(select_sql, (strategy_name,))
            rows = cursor.fetchall()

            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def get_active_strategies(self) -> list[dict[str, Any]]:
        """Get all active strategies.

        Returns:
            List of strategies with status='active'

        Educational Note:
            In production, only 'active' strategies are used for live trading.
            'testing' strategies run in paper trading mode.
            'draft' strategies are under development.
            'deprecated' strategies are retired (no longer used).

        References:
            - REQ-VER-004: Version Lifecycle Management
            - REQ-VER-005: A/B Testing Support (multiple active versions allowed)
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Use partial index for better performance (idx_strategies_active)
            select_sql = """
                SELECT strategy_id, strategy_name, strategy_version, approach,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes
                FROM strategies
                WHERE status = 'active'
                ORDER BY strategy_name, strategy_version
            """

            cursor.execute(select_sql)
            rows = cursor.fetchall()

            logger.info(f"Retrieved {len(rows)} active strategies")
            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def update_status(self, strategy_id: int, new_status: str) -> dict[str, Any]:
        """Update strategy status (MUTABLE field).

        Args:
            strategy_id: Strategy to update
            new_status: New status ('draft', 'testing', 'active', 'inactive', 'deprecated')

        Returns:
            Updated strategy dict

        Raises:
            ValueError: If strategy not found
            InvalidStatusTransitionError: If transition is invalid

        Educational Note:
            Status is MUTABLE (config is not!). Common workflows:
            - Development: draft → testing → active
            - Retirement: active → inactive → deprecated
            - Revert: testing → draft

            Invalid transitions that raise errors:
            - deprecated → active (can't reactivate)
            - active → testing (can't go backwards)

        References:
            - REQ-VER-004: Version Lifecycle Management
        """
        # Get current status
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        current_status = strategy["status"]

        # Validate transition
        self._validate_status_transition(current_status, new_status)

        # Update status
        conn = get_connection()
        cursor = conn.cursor()

        try:
            update_sql = """
                UPDATE strategies
                SET status = %s
                WHERE strategy_id = %s
                RETURNING strategy_id, strategy_name, strategy_version, approach,
                          domain, config, description, status, paper_roi, live_roi,
                          paper_trades_count, live_trades_count, created_at, created_by, notes
            """

            cursor.execute(update_sql, (new_status, strategy_id))
            row = cursor.fetchone()
            conn.commit()

            logger.info(f"Updated strategy {strategy_id} status: {current_status} → {new_status}")

            return self._row_to_dict(cursor, row)

        finally:
            cursor.close()
            release_connection(conn)

    def update_metrics(
        self,
        strategy_id: int,
        paper_roi: Decimal | None = None,
        live_roi: Decimal | None = None,
        paper_trades_count: int | None = None,
        live_trades_count: int | None = None,
    ) -> dict[str, Any]:
        """Update strategy performance metrics (MUTABLE fields).

        Args:
            strategy_id: Strategy to update
            paper_roi: Paper trading ROI (optional)
            live_roi: Live trading ROI (optional)
            paper_trades_count: Number of paper trades (optional)
            live_trades_count: Number of live trades (optional)

        Returns:
            Updated strategy dict

        Raises:
            ValueError: If strategy not found or no metrics provided

        Educational Note:
            Metrics are MUTABLE - they accumulate as trades execute.
            Config is IMMUTABLE - never changes.

            This separation enables:
            - Tracking performance of each version independently
            - A/B testing (compare v1.0 vs v1.1 ROI)
            - Knowing EXACTLY which config generated which ROI

        References:
            - REQ-VER-005: A/B Testing Support
        """
        if all(v is None for v in [paper_roi, live_roi, paper_trades_count, live_trades_count]):
            raise ValueError("At least one metric must be provided")

        # Build dynamic UPDATE
        updates: list[str] = []
        params: list[Decimal | int] = []

        if paper_roi is not None:
            updates.append("paper_roi = %s")
            params.append(paper_roi)

        if live_roi is not None:
            updates.append("live_roi = %s")
            params.append(live_roi)

        if paper_trades_count is not None:
            updates.append("paper_trades_count = %s")
            params.append(paper_trades_count)

        if live_trades_count is not None:
            updates.append("live_trades_count = %s")
            params.append(live_trades_count)

        params.append(strategy_id)

        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Safe: updates list contains ONLY hardcoded column names (lines 462-475),
            # never user input. All values use parameterized queries (%s placeholders).
            update_sql = f"""  # noqa: S608
                UPDATE strategies
                SET {", ".join(updates)}
                WHERE strategy_id = %s
                RETURNING strategy_id, strategy_name, strategy_version, approach,
                          domain, config, description, status, paper_roi, live_roi,
                          paper_trades_count, live_trades_count, created_at, created_by, notes
            """

            cursor.execute(update_sql, params)
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Strategy {strategy_id} not found")

            conn.commit()

            logger.info(
                f"Updated strategy {strategy_id} metrics",
                extra={
                    k: v
                    for k, v in zip(
                        ["paper_roi", "live_roi", "paper_trades", "live_trades"],
                        [paper_roi, live_roi, paper_trades_count, live_trades_count],
                        strict=False,
                    )
                    if v is not None
                },
            )

            return self._row_to_dict(cursor, row)

        finally:
            cursor.close()
            release_connection(conn)

    # Private helper methods

    def _prepare_config_for_db(self, config: dict[str, Any]) -> str:
        """Convert config dict to JSONB string (Decimal → string conversion).

        Args:
            config: Strategy config dict

        Returns:
            JSON string ready for JSONB storage

        Educational Note:
            PostgreSQL JSONB doesn't support Python Decimal type natively.
            We convert Decimal → string for storage, string → Decimal on retrieval.

            Example:
                Input:  {"min_edge": Decimal("0.05")}
                Output: '{"min_edge": "0.05"}'  (JSON string)

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

        config_converted = decimal_to_str(config)
        return json.dumps(config_converted)

    def _row_to_dict(self, cursor, row) -> dict[str, Any]:
        """Convert database row to dictionary with Decimal conversion.

        Args:
            cursor: Database cursor (for column names)
            row: Query result row

        Returns:
            Dictionary with column names as keys, config values converted to Decimal

        Educational Note:
            PostgreSQL JSONB returns dict automatically (psycopg2 conversion).
            Config values are stored as strings, we convert back to Decimal here
            for Pattern 1 compliance (ALWAYS use Decimal for prices/probabilities).

        Example:
            Database stores: {"min_edge": "0.05"} (string)
            This method returns: {"min_edge": Decimal("0.05")} (Decimal)
        """
        columns = [desc[0] for desc in cursor.description]
        result = dict(zip(columns, row, strict=False))

        # Convert config string values back to Decimal
        if "config" in result and result["config"] is not None:
            result["config"] = self._parse_config_from_db(result["config"])

        return result

    def _parse_config_from_db(self, config: dict[str, Any]) -> dict[str, Any]:
        """Convert config string values back to Decimal.

        Args:
            config: Config dict from database (string values)

        Returns:
            Config dict with Decimal values

        Educational Note:
            We store Decimals as strings in JSONB: Decimal("0.05") → "0.05"
            This method reverses that: "0.05" → Decimal("0.05")
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
            Valid transitions form a state machine:
            - draft → testing → active (forward progression)
            - active → inactive → deprecated (retirement)
            - testing → draft (revert to development)

            Invalid transitions:
            - deprecated → * (deprecated is terminal)
            - active → testing (can't go backwards)
        """
        # Define valid transitions
        valid_transitions = {
            "draft": ["testing", "draft"],
            "testing": ["active", "draft"],
            "active": ["inactive"],
            "inactive": ["deprecated", "active"],
            "deprecated": [],  # Terminal state
        }

        if new not in valid_transitions.get(current, []):
            raise InvalidStatusTransitionError(
                f"Invalid transition: {current} → {new}. "
                f"Valid transitions from {current}: {valid_transitions.get(current, [])}"
            )
