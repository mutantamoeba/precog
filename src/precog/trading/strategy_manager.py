"""Strategy Manager - Versioned Trading Strategy Management.

This module manages versioned trading strategies with immutable configurations
following the Immutable Version Pattern (REQ-VER-001, REQ-VER-002).

Educational Note:
    Strategies use IMMUTABLE versions for A/B testing and precise trade attribution.
    When you need to change a strategy's parameters:
    - Don't modify existing config (IMMUTABLE!)
    - Create new version: v1.0 -> v1.1 (bug fix) or v1.0 -> v2.0 (major change)
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
    - docs/database/DATABASE_SCHEMA_SUMMARY.md (strategies table with strategy_type/domain fields)

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
        - draft -> testing -> active
        - active -> inactive -> deprecated
        - testing -> draft (revert to draft)

    Invalid transitions:
        - deprecated -> active (can't reactivate deprecated)
        - active -> testing (can't go backwards)
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
            strategy_type="entry",
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
            strategy_type="entry",
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
          when we have complex relationships (strategies -> trades -> positions)

    References:
        - docs/guides/VERSIONING_GUIDE_V1.0.md - Complete versioning patterns
        - docs/database/DATABASE_SCHEMA_SUMMARY.md - strategies table schema
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
        strategy_type: str,
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
            strategy_type: Valid strategy type code from strategy_types lookup table.
                Initial values: 'value', 'arbitrage', 'momentum', 'mean_reversion'
                Query available types: SELECT * FROM strategy_types WHERE is_active = TRUE
                (Constraint enforced by FK - see Migration 023)
            config: Strategy parameters (IMMUTABLE once created!)
            domain: WHICH markets ('nfl', 'nba', etc.) or None for multi-domain
            description: Human-readable description
            status: Initial status (default: 'draft')
            created_by: Creator identifier
            notes: Additional notes

        Returns:
            Dictionary containing created strategy with all fields

        Raises:
            psycopg2.IntegrityError: If (strategy_name, strategy_version) already exists
            psycopg2.ForeignKeyViolation: If strategy_type is not in strategy_types table
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
            - Migration 023: strategy_types lookup table and FK constraint
        """
        # Validation
        if not config:
            raise ValueError("Strategy config cannot be empty")

        # Convert config to JSONB (with Decimal -> string conversion)
        config_jsonb = self._prepare_config_for_db(config)

        # Insert strategy
        conn = get_connection()
        cursor = conn.cursor()

        try:
            insert_sql = """
                INSERT INTO strategies (
                    strategy_name, strategy_version, strategy_type, domain,
                    config, description, status, created_by, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING strategy_id, strategy_name, strategy_version, strategy_type,
                          domain, config, description, status, paper_roi, live_roi,
                          paper_trades_count, live_trades_count, created_at, created_by, notes
            """

            cursor.execute(
                insert_sql,
                (
                    strategy_name,
                    strategy_version,
                    strategy_type,
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

        except psycopg2.IntegrityError as e:
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
            # Post-Migration 0064: filter row_current_ind = TRUE so the
            # returned row is the CURRENT SCD2 version.  Historical
            # (superseded) rows with the same strategy_id never exist
            # post-0064 because supersede allocates a fresh id — but
            # the filter is load-bearing because before 0064 strategy_ids
            # were reused, and tests creating rows via raw SQL might
            # leave historical rows around.
            select_sql = """
                SELECT strategy_id, strategy_name, strategy_version, strategy_type,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes
                FROM strategies
                WHERE strategy_id = %s AND row_current_ind = TRUE
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
            # Post-Migration 0064: row_current_ind = TRUE filter returns
            # the CURRENT SCD2 row per (name, version) — one row per
            # logical version, consistent with the pre-0064 contract
            # ("all versions" means "all versions I declared", not "all
            # SCD history rows").
            select_sql = """
                SELECT strategy_id, strategy_name, strategy_version, strategy_type,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes
                FROM strategies
                WHERE strategy_name = %s AND row_current_ind = TRUE
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
            # Post-Migration 0064: both filters apply — status='active'
            # AND row_current_ind = TRUE — so a historical row that was
            # 'active' before being superseded does not shadow the
            # live version.  Glokta P0-3 / Ripley #NEW-C.
            select_sql = """
                SELECT strategy_id, strategy_name, strategy_version, strategy_type,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes
                FROM strategies
                WHERE status = 'active' AND row_current_ind = TRUE
                ORDER BY strategy_name, strategy_version
            """

            cursor.execute(select_sql)
            rows = cursor.fetchall()

            logger.info(f"Retrieved {len(rows)} active strategies")
            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def list_strategies(
        self,
        status: str | None = None,
        strategy_version: str | None = None,
        strategy_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List strategies with optional filters.

        Args:
            status: Filter by status (optional). Valid values: 'draft', 'testing', 'active', 'inactive', 'deprecated'
            strategy_version: Filter by version (optional). Example: 'v1.0', 'v1.1', 'v2.0'
            strategy_type: Filter by strategy type (optional). Valid values: 'value', 'arbitrage', 'momentum', 'mean_reversion'

        Returns:
            List of strategies matching filters, ordered by strategy_name, strategy_version

        Educational Note:
            This method supports flexible querying for strategies.
            - No filters: Returns ALL strategies
            - Single filter: Returns strategies matching that filter
            - Multiple filters: Returns strategies matching ALL filters (AND logic)

            This mirrors the list_models() API in model_manager.py for consistency.

        Example:
            >>> # Get all active value strategies
            >>> strategies = manager.list_strategies(status='active', strategy_type='value')
            >>> # Get all v1.0 strategies
            >>> strategies = manager.list_strategies(strategy_version='v1.0')
            >>> # Get all strategies (no filters)
            >>> all_strategies = manager.list_strategies()

        References:
            - REQ-VER-004: Version Lifecycle Management
            - REQ-VER-005: A/B Testing Support
            - GitHub Issue #132: Add list_strategies() method
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Post-Migration 0064: row_current_ind = TRUE is an always-on
            # filter.  Historical SCD rows are not part of the "list"
            # contract — callers who want SCD history should query
            # crud_strategies.get_all_strategy_versions(..., include_historical=True).
            where_clauses: list[str] = ["row_current_ind = TRUE"]
            params: list[str] = []

            if status is not None:
                where_clauses.append("status = %s")
                params.append(status)

            if strategy_version is not None:
                where_clauses.append("strategy_version = %s")
                params.append(strategy_version)

            if strategy_type is not None:
                where_clauses.append("strategy_type = %s")
                params.append(strategy_type)

            # Construct SQL (always has at least the row_current_ind clause)
            where_sql = "WHERE " + " AND ".join(where_clauses)

            select_sql = f"""
                SELECT strategy_id, strategy_name, strategy_version, strategy_type,
                       domain, config, description, status, paper_roi, live_roi,
                       paper_trades_count, live_trades_count, created_at, created_by, notes,
                       activated_at, deactivated_at, updated_at
                FROM strategies
                {where_sql}
                ORDER BY strategy_name, strategy_version
            """

            cursor.execute(select_sql, params)
            rows = cursor.fetchall()

            logger.info(
                f"Retrieved {len(rows)} strategies with filters: "
                f"status={status}, strategy_version={strategy_version}, strategy_type={strategy_type}"
            )
            return [self._row_to_dict(cursor, row) for row in rows]

        finally:
            cursor.close()
            release_connection(conn)

    def update_status(self, strategy_id: int, new_status: str) -> dict[str, Any]:
        """Update strategy status (MUTABLE field) via SCD Type 2 supersede.

        Args:
            strategy_id: Strategy to update (MUST reference a CURRENT SCD2 row)
            new_status: New status ('draft', 'testing', 'active', 'inactive', 'deprecated')

        Returns:
            Updated strategy dict (re-fetched via natural key after the
            supersede — the new SCD2 row has a NEW strategy_id).

        Raises:
            ValueError: If strategy not found
            InvalidStatusTransitionError: If transition is invalid

        Educational Note:
            Status is MUTABLE across SCD2 versions (config is IMMUTABLE).
            Post-Migration 0064, this method delegates to
            ``crud_strategies.update_strategy_status`` which performs a
            close+INSERT supersede with FOR UPDATE locking.  The close
            flips the current row's ``row_current_ind`` to FALSE and the
            INSERT creates a new row with a NEW ``strategy_id`` carrying
            the new status — the caller sees the new row via the natural
            key re-fetch below.

            Common workflows:
            - Development: draft -> testing -> active
            - Retirement: active -> inactive -> deprecated
            - Revert: testing -> draft

            Invalid transitions that raise errors:
            - deprecated -> active (can't reactivate)
            - active -> testing (can't go backwards)

        References:
            - REQ-VER-004: Version Lifecycle Management
            - Migration 0064 (SCD2 on strategies)
            - ``crud_strategies.update_strategy_status`` (the CRUD supersede)
            - Glokta P0-1 / Ripley #NEW-A (S62): converted from in-place
              UPDATE to SCD2 supersede delegation.
        """
        # Import locally to avoid a module-load-time cycle between the
        # CRUD layer and the manager layer (crud -> connection -> config).
        from precog.database.crud_strategies import (
            get_strategy_by_name_and_version,
            update_strategy_status,
        )

        # Resolve caller's (potentially stale) strategy_id to the CURRENT
        # SCD2 row.  Post-Migration 0064, ``update_status`` is a
        # supersede: previous supersedes left the old strategy_id
        # referencing a historical (closed) row.  To preserve ergonomic
        # compatibility with the pre-0064 contract ("pass any id, I'll
        # update the logical entity"), we resolve stale ids to the
        # current version via the (name, version) natural key.
        strategy = self.get_strategy(strategy_id)
        if strategy is None:
            # strategy_id might be a historical SCD row.  Look it up
            # WITHOUT the row_current_ind filter, grab (name, version),
            # and redirect to the current row.
            strategy = self._resolve_historical_id(strategy_id)
            if strategy is None:
                raise ValueError(
                    f"Strategy {strategy_id} not found "
                    f"(operation=update_status, target_status={new_status})"
                )
            # The current strategy_id for this (name, version) is on
            # the re-resolved ``strategy`` dict — use it for the supersede.
            strategy_id = strategy["strategy_id"]

        current_status = strategy["status"]

        # Validate transition
        self._validate_status_transition(current_status, new_status)

        # Delegate to the SCD2 supersede CRUD.  Returns True on success,
        # False if the row vanished between the get_strategy fetch and the
        # supersede (extraordinary race — concurrent deletion).
        ok = update_strategy_status(strategy_id=strategy_id, new_status=new_status)
        if not ok:
            raise ValueError(
                f"Strategy {strategy_id} not found during supersede "
                f"(operation=update_status, target_status={new_status}). "
                "A concurrent caller may have closed the row between the "
                "validate-transition fetch and the supersede."
            )

        # The supersede allocated a NEW strategy_id for the new SCD2 row;
        # re-fetch via the natural key (which is preserved across
        # supersedes) to return the current row with the new status.
        new_row = get_strategy_by_name_and_version(
            strategy["strategy_name"], strategy["strategy_version"]
        )
        if not new_row:
            # Should be unreachable — we just inserted it.  Defensive.
            raise ValueError(
                f"Post-supersede fetch returned None for "
                f"({strategy['strategy_name']!r}, {strategy['strategy_version']!r}) "
                "(operation=update_status)"
            )

        # Re-parse config through the manager's Decimal-converter so the
        # returned row matches the pre-0064 shape (broader numeric-string
        # → Decimal conversion than the CRUD's whitelist helper).
        if new_row.get("config") is not None:
            new_row["config"] = self._parse_config_from_db(new_row["config"])

        logger.info(
            f"Updated strategy {strategy_id} status: {current_status} -> {new_status} "
            f"(new SCD2 strategy_id={new_row['strategy_id']})"
        )
        return new_row

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

        # Import locally to avoid a module-load-time cycle.
        from precog.database.crud_strategies import (
            get_strategy_by_name_and_version,
            update_strategy_metrics,
        )

        # Resolve the caller's (potentially stale) strategy_id to the
        # CURRENT SCD2 row.  See update_status for the rationale — we
        # preserve the pre-0064 ergonomics ("pass any id") by redirecting
        # historical ids to the current row of the same (name, version).
        strategy = self.get_strategy(strategy_id)
        if strategy is None:
            strategy = self._resolve_historical_id(strategy_id)
            if strategy is None:
                attempted_metrics = [
                    name
                    for name, value in zip(
                        ["paper_roi", "live_roi", "paper_trades_count", "live_trades_count"],
                        [paper_roi, live_roi, paper_trades_count, live_trades_count],
                        strict=False,
                    )
                    if value is not None
                ]
                raise ValueError(
                    f"Strategy {strategy_id} not found "
                    f"(operation=update_metrics, attempted_updates=[{', '.join(attempted_metrics)}])"
                )
            strategy_id = strategy["strategy_id"]

        # Delegate to the SCD2 supersede CRUD.
        ok = update_strategy_metrics(
            strategy_id=strategy_id,
            paper_roi=paper_roi,
            live_roi=live_roi,
            paper_trades_count=paper_trades_count,
            live_trades_count=live_trades_count,
        )
        if not ok:
            raise ValueError(
                f"Strategy {strategy_id} not found during supersede "
                f"(operation=update_metrics). A concurrent caller may have "
                "closed the row between the pre-supersede fetch and the "
                "supersede itself."
            )

        # Re-fetch via natural key (the supersede allocated a NEW strategy_id).
        new_row = get_strategy_by_name_and_version(
            strategy["strategy_name"], strategy["strategy_version"]
        )
        if not new_row:
            raise ValueError(
                f"Post-supersede fetch returned None for "
                f"({strategy['strategy_name']!r}, {strategy['strategy_version']!r}) "
                "(operation=update_metrics)"
            )

        # Re-parse config through the manager's Decimal-converter (broader
        # than the CRUD whitelist) so the returned row matches pre-0064
        # shape.
        if new_row.get("config") is not None:
            new_row["config"] = self._parse_config_from_db(new_row["config"])

        logger.info(
            f"Updated strategy {strategy_id} metrics "
            f"(new SCD2 strategy_id={new_row['strategy_id']})",
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
        return new_row

    # Private helper methods

    def _resolve_historical_id(self, strategy_id: int) -> dict[str, Any] | None:
        """Resolve a stale strategy_id to the current SCD2 row.

        Post-Migration 0064 every status/metrics update allocates a new
        strategy_id.  Callers that hold an id from before a prior
        supersede still expect ``update_status(stale_id)`` to work on
        the logical entity.  This helper finds the historical row,
        reads its ``(strategy_name, strategy_version)`` natural key, and
        returns the CURRENT row for that key — or None if the id never
        existed or the logical entity has been deleted entirely.

        Returns:
            The current SCD2 row as a dict (same shape as ``get_strategy``),
            or None if no such row exists.
        """
        from precog.database.crud_strategies import get_strategy_by_name_and_version

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Unfiltered lookup (might return historical row with row_current_ind = FALSE).
            cursor.execute(
                """
                SELECT strategy_name, strategy_version
                FROM strategies
                WHERE strategy_id = %s
                """,
                (strategy_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            # row is tuple from raw psycopg2 cursor.
            name, version = row[0], row[1]
        finally:
            cursor.close()
            release_connection(conn)

        return get_strategy_by_name_and_version(name, version)

    def _prepare_config_for_db(self, config: dict[str, Any]) -> str:
        """Convert config dict to JSONB string (Decimal -> string conversion).

        Args:
            config: Strategy config dict

        Returns:
            JSON string ready for JSONB storage

        Educational Note:
            PostgreSQL JSONB doesn't support Python Decimal type natively.
            We convert Decimal -> string for storage, string -> Decimal on retrieval.

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
            We store Decimals as strings in JSONB: Decimal("0.05") -> "0.05"
            This method reverses that: "0.05" -> Decimal("0.05")
            Pattern 1 compliance: Application always uses Decimal, never float.
        """

        def str_to_decimal(obj: Any) -> Any:
            if isinstance(obj, str):
                # Only convert simple decimal patterns that match our storage format
                # Valid patterns: "0.05", "-123.45", "42", "0.00001"
                # Rejected: "+0", "1e10", "Infinity", "NaN", "0e0", " 123", "abc"
                # Our _prepare_config_for_db stores Decimals as str(decimal) which produces
                # formats like "0.05" (no leading +, no scientific notation)
                stripped = obj.strip()
                if not stripped:
                    return obj

                # Check for characters that indicate this isn't a simple decimal
                # Scientific notation (e/E), Infinity, NaN, leading +, etc.
                if "e" in stripped.lower():
                    return obj
                if stripped.startswith("+"):
                    return obj
                if stripped.lower() in ("infinity", "-infinity", "nan", "inf", "-inf"):
                    return obj

                # Try to convert simple numeric strings to Decimal
                try:
                    result = Decimal(obj)
                    # Only accept finite numbers - reject Infinity/NaN
                    if result.is_finite():
                        return result
                    return obj  # Return as-is if Infinity/NaN
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
            - draft -> testing -> active (forward progression)
            - active -> inactive -> deprecated (retirement)
            - testing -> draft (revert to development)

            Invalid transitions:
            - deprecated -> * (deprecated is terminal)
            - active -> testing (can't go backwards)
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
                f"Invalid transition: {current} -> {new}. "
                f"Valid transitions from {current}: {valid_transitions.get(current, [])}"
            )
