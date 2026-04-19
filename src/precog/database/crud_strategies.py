"""CRUD operations for strategies.

Extracted from crud_operations.py during Phase 1b domain split.

Tables covered:
    - strategies: Immutable versioned trading strategy configurations
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, get_cursor
from .crud_shared import (
    DecimalEncoder,
    _convert_config_strings_to_decimal,
    retry_on_scd_unique_conflict,
)

logger = logging.getLogger(__name__)


# =============================================================================
# STRATEGY CRUD OPERATIONS (Immutable Versioning Pattern)
# =============================================================================


def create_strategy(
    strategy_name: str,
    strategy_version: str,
    strategy_type: str,
    config: dict,
    status: str = "draft",
    platform_id: str | None = None,
    subcategory: str | None = None,
    notes: str | None = None,
) -> int | None:
    """
    Create new strategy version with IMMUTABLE config.

    Args:
        strategy_name: Strategy name (e.g., "halftime_entry")
        strategy_version: Semantic version (e.g., "v1.0", "v1.1")
        strategy_type: HOW you trade - trading style (e.g., "value", "momentum", "mean_reversion")
        config: Strategy configuration (IMMUTABLE after creation)
        status: Strategy status ("draft", "testing", "active", "deprecated")
        platform_id: Platform ID (optional, for platform-specific strategies)
        subcategory: Strategy subcategory (optional, domain-specific like "nfl")
        notes: Additional notes (optional)

    Returns:
        int: strategy_id from database

    Raises:
        IntegrityError: If (strategy_name, strategy_version) already exists

    Educational Note:
        Strategy configs are IMMUTABLE for A/B testing integrity:
        - v1.0 config NEVER changes (preserves test results)
        - To modify config, create NEW version (v1.0 -> v1.1)
        - Status is MUTABLE (draft -> testing -> active -> deprecated)

        Why immutability matters:
        - A/B testing: Need to know EXACTLY which config generated each trade
        - Trade attribution: Trades link to specific immutable versions
        - Backtesting: Can replay historical strategies with original configs

        Mutable vs Immutable:
        - config (IMMUTABLE): Create new version to change
        - status (MUTABLE): Can update in-place
        - activated_at, deactivated_at (MUTABLE): Timestamps

    Example:
        >>> # Create initial version
        >>> v1_0 = create_strategy(
        ...     strategy_name="halftime_entry",
        ...     strategy_version="v1.0",
        ...     strategy_type="momentum",
        ...     config={"min_lead": 7, "min_time_remaining_mins": 5},
        ...     status="draft"
        ... )
        >>> # ✅ Can update status
        >>> update_strategy_status(v1_0, "active")
        >>> # ❌ CANNOT update config - must create v1.1
        >>> v1_1 = create_strategy(
        ...     strategy_name="halftime_entry",
        ...     strategy_version="v1.1",
        ...     strategy_type="momentum",
        ...     config={"min_lead": 10, "min_time_remaining_mins": 5}  # Different
        ... )

    Related:
        - Pattern 2 in CLAUDE.md: Dual Versioning System
        - docs/guides/VERSIONING_GUIDE_V1.0.md
        - ADR-018, ADR-019, ADR-020
    """
    query = """
        INSERT INTO strategies (
            platform_id, strategy_name, strategy_version, strategy_type, domain,
            config, status, notes, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING strategy_id
    """

    params = (
        platform_id,
        strategy_name,
        strategy_version,
        strategy_type,  # HOW you trade (trading style)
        subcategory,  # Maps to 'domain' column (market category like "nfl")
        json.dumps(config, cls=DecimalEncoder),  # Convert dict to JSON string (handles Decimal)
        status,
        notes,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["strategy_id"]) if result else None


def get_strategy(strategy_id: int) -> dict[str, Any] | None:
    """
    Get strategy by strategy_id.

    Args:
        strategy_id: Strategy ID

    Returns:
        Strategy dict or None if not found
        Config field will have Decimal values restored from JSON strings

    Example:
        >>> strategy = get_strategy(42)
        >>> print(strategy["strategy_name"], strategy["strategy_version"])
        halftime_entry v1.0
        >>> print(type(strategy["config"]["max_edge"]))
        <class 'decimal.Decimal'>
    """
    # Post-Migration 0064, strategies is SCD Type 2.  Default behaviour is
    # to return the CURRENT row only (``row_current_ind = TRUE``).  Callers
    # that need historical rows should use ``get_all_strategy_versions``
    # (which always returns current + historical) or run a targeted raw
    # query.  See CLAUDE.md Pattern 3 (SCD2 read-side filter discipline).
    query = """
        SELECT * FROM strategies
        WHERE strategy_id = %s AND row_current_ind = TRUE
    """

    with get_cursor() as cur:
        cur.execute(query, (strategy_id,))
        result = cast("dict[str, Any] | None", cur.fetchone())

        # Convert config string values back to Decimal
        if result and "config" in result:
            result["config"] = _convert_config_strings_to_decimal(result["config"])

        return result


def get_strategy_by_name_and_version(
    strategy_name: str, strategy_version: str
) -> dict[str, Any] | None:
    """
    Get strategy by name and version.

    Args:
        strategy_name: Strategy name
        strategy_version: Strategy version (e.g., "v1.0")

    Returns:
        Strategy dict or None if not found
        Config field will have Decimal values restored from JSON strings

    Example:
        >>> v1_0 = get_strategy_by_name_and_version("halftime_entry", "v1.0")
        >>> v1_1 = get_strategy_by_name_and_version("halftime_entry", "v1.1")
        >>> print(type(v1_0["config"]["kelly_fraction"]))
        <class 'decimal.Decimal'>
    """
    # Post-Migration 0064: filter by row_current_ind = TRUE so the
    # partial UNIQUE index (idx_strategies_name_version_current) picks
    # a deterministic single row.  Historical SCD rows are intentionally
    # excluded — this function returns the CURRENT version of
    # (name, version).
    query = """
        SELECT * FROM strategies
        WHERE strategy_name = %s AND strategy_version = %s
          AND row_current_ind = TRUE
    """

    with get_cursor() as cur:
        cur.execute(query, (strategy_name, strategy_version))
        result = cast("dict[str, Any] | None", cur.fetchone())

        # Convert config string values back to Decimal
        if result and "config" in result:
            result["config"] = _convert_config_strings_to_decimal(result["config"])

        return result


def get_active_strategy_version(strategy_name: str) -> dict[str, Any] | None:
    """
    Get active version of a strategy (status = 'active').

    Args:
        strategy_name: Strategy name

    Returns:
        Active strategy dict or None if no active version
        Config field will have Decimal values restored from JSON strings

    Example:
        >>> active = get_active_strategy_version("halftime_entry")
        >>> print(active["strategy_version"], active["status"])
        v1.1 active
        >>> print(type(active["config"]["kelly_fraction"]))
        <class 'decimal.Decimal'>
    """
    # Post-Migration 0064: filter by row_current_ind = TRUE so supersede
    # history cannot shadow the live row.  Without this filter, after a
    # status supersede the closed historical row and the new current row
    # both match ``status = 'active'`` (or the closed one carries the
    # pre-supersede status), and ORDER BY created_at DESC LIMIT 1 picks
    # non-deterministically since ``created_at`` is NOT refreshed on
    # supersede — the closed row keeps its original created_at and the
    # new row uses CURRENT_TIMESTAMP, but only the new row is the live
    # "active" version.  Glokta P0-3 / Ripley #NEW-C.
    query = """
        SELECT * FROM strategies
        WHERE strategy_name = %s AND status = 'active'
          AND row_current_ind = TRUE
        ORDER BY created_at DESC
        LIMIT 1
    """

    with get_cursor() as cur:
        cur.execute(query, (strategy_name,))
        result = cast("dict[str, Any] | None", cur.fetchone())

        # Convert config string values back to Decimal
        if result and "config" in result:
            result["config"] = _convert_config_strings_to_decimal(result["config"])

        return result


def get_all_strategy_versions(
    strategy_name: str,
    include_historical: bool = False,
) -> list[dict[str, Any]]:
    """
    Get all versions of a strategy (for history view).

    Args:
        strategy_name: Strategy name
        include_historical: If True, include SCD2 historical (superseded)
            rows.  If False (default), return only the CURRENT row for
            each ``strategy_version``.  Post-Migration 0064, a supersede
            creates additional rows with ``row_current_ind = FALSE`` — the
            default hides those so the caller sees one row per logical
            ``strategy_version``.

    Returns:
        List of strategy dicts, sorted by created_at DESC
        Config fields will have Decimal values restored from JSON strings

    Example:
        >>> versions = get_all_strategy_versions("halftime_entry")
        >>> for v in versions:
        ...     print(v["strategy_version"], v["status"])
        v1.2 active
        v1.1 deprecated
        v1.0 deprecated
        >>> print(type(versions[0]["config"]["kelly_fraction"]))
        <class 'decimal.Decimal'>

        >>> # Include SCD2 historical rows (status transition audit trail).
        >>> history = get_all_strategy_versions(
        ...     "halftime_entry", include_historical=True
        ... )
    """
    # Post-Migration 0064: default is one row per current version.  With
    # include_historical=True the caller sees the full SCD audit trail
    # (every status transition produces one historical + one current row).
    if include_historical:
        query = """
            SELECT * FROM strategies
            WHERE strategy_name = %s
            ORDER BY created_at DESC
        """
    else:
        query = """
            SELECT * FROM strategies
            WHERE strategy_name = %s AND row_current_ind = TRUE
            ORDER BY created_at DESC
        """

    with get_cursor() as cur:
        cur.execute(query, (strategy_name,))
        results = cast("list[dict[str, Any]]", cur.fetchall())

        # Convert config string values back to Decimal for each version
        for result in results:
            if "config" in result:
                result["config"] = _convert_config_strings_to_decimal(result["config"])

        return results


def update_strategy_status(
    strategy_id: int,
    new_status: str,
    activated_at: datetime | None = None,
    deactivated_at: datetime | None = None,
) -> bool:
    """
    Update strategy status via SCD Type 2 supersede.

    Post-migration 0064, the ``strategies`` table is SCD Type 2.  Status
    transitions are recorded as a close-and-insert supersede: the current
    row (matching ``strategy_id``) has ``row_current_ind`` flipped to
    FALSE and ``row_end_ts`` set to NOW(), then a new row is INSERTed
    with the same ``(strategy_name, strategy_version)`` natural key and
    the new status.  The partial UNIQUE index on
    ``(strategy_name, strategy_version) WHERE row_current_ind = TRUE``
    enforces at-most-one-current-version invariant.

    Args:
        strategy_id: Strategy row ID.  Must reference a CURRENT row
            (``row_current_ind = TRUE``); superseding a historical row
            is not supported.
        new_status: New status ("draft", "testing", "active", "deprecated")
        activated_at: Timestamp when activated (optional)
        deactivated_at: Timestamp when deactivated (optional)

    Returns:
        bool: True if superseded, False if strategy not found or not
            current.  The new SCD2 row gets a NEW ``strategy_id`` — use
            ``get_strategy_by_name_and_version`` or similar to retrieve it.

    Educational Note:
        Status is MUTABLE across SCD2 versions (can change without
        requiring a new ``strategy_version`` string):
        - draft -> testing -> active -> deprecated (normal lifecycle)
        - active -> deprecated (when superseded by new ``strategy_version``)

        Config is still IMMUTABLE (cannot change between SCD2 versions
        of the same ``strategy_version``).  The immutability trigger
        ``trg_strategies_immutability`` guards ``config``,
        ``strategy_version``, ``strategy_name``, ``strategy_type`` on
        UPDATE — the CLOSE-UPDATE in this function touches only
        ``row_current_ind`` and ``row_end_ts``, neither of which are
        guarded, so the trigger's ``IS DISTINCT FROM`` checks pass.

    Example:
        >>> # Move from draft to testing
        >>> update_strategy_status(strategy_id=42, new_status="testing")
        >>> # Activate strategy (supersede closes current row + inserts
        >>> # a new row with a NEW strategy_id)
        >>> update_strategy_status(
        ...     strategy_id=42,
        ...     new_status="active",
        ...     activated_at=datetime.now()
        ... )
        >>> # Deprecate old version
        >>> update_strategy_status(
        ...     strategy_id=41,
        ...     new_status="deprecated",
        ...     deactivated_at=datetime.now()
        ... )

    Concurrency contract:
        The fetch SELECT uses ``FOR UPDATE`` to serialize concurrent
        supersede callers against the same ``strategy_id`` — without the
        lock, two callers could both see the same current row, both run
        the CLOSE-UPDATE (the second as a rowcount=0 no-op), and both
        INSERT, colliding on ``idx_strategies_name_version_current``.
        A targeted retry via ``retry_on_scd_unique_conflict`` absorbs
        any residual cross-strategy_id race on the INSERT (no-ops
        cleanly if a sibling caller won).

    Timestamp carry-forward:
        ``activated_at`` and ``deactivated_at`` are COALESCEd with the
        current row's values.  Callers updating only one of the two
        (e.g., setting ``deactivated_at`` on a deprecate call) do NOT
        wipe the other from the SCD2 audit chain — the new row preserves
        ``activated_at`` from the earliest activate call in the version's
        history.

    Related:
        - Migration 0064 (adds SCD2 temporal columns)
        - Issue #791 / Epic #745 (Schema Hardening Arc, Cohort C2c)
        - Pattern 2 in CLAUDE.md: SCD Type 2 Versioning
        - ``crud_positions.update_position_price`` (SCD2 supersede precedent,
          FOR UPDATE at crud_positions.py:541)
        - ``crud_markets.update_market_snapshot`` (SCD2 supersede precedent)
        - Glokta + Ripley S62 convergent findings (P0-2 FOR UPDATE,
          P1-1 activated_at/deactivated_at carry-forward)
    """
    # Step 1: Fetch + LOCK the current row by strategy_id.  We need every
    # immutable column verbatim on the new row — natural key
    # (strategy_name / strategy_version), identity (strategy_type,
    # platform_id, domain), config, description, created_at, created_by,
    # and the carry-forward mutable metrics (paper_* / live_*, notes) +
    # SCD2 temporal audit timestamps (activated_at, deactivated_at).
    #
    # The row_current_ind = TRUE filter enforces the contract documented
    # above: superseding a historical row is not supported — a caller
    # holding a stale strategy_id must re-resolve via natural key before
    # calling this function.
    #
    # FOR UPDATE serializes two concurrent supersede callers for the same
    # strategy_id — without it, both would see the same current row, both
    # would UPDATE (the second as a no-op rowcount=0), and both would
    # INSERT, colliding on the partial UNIQUE index
    # ``idx_strategies_name_version_current``.  Glokta P0-2 / Ripley
    # #NEW-B.  Mirrors ``crud_positions.update_position_price`` at
    # crud_positions.py:541 — SCD2 supersede precedent.
    fetch_query = """
        SELECT strategy_name, strategy_version, strategy_type, platform_id,
               domain, config, notes, description, created_by,
               paper_trades_count, paper_roi, live_trades_count, live_roi,
               activated_at, deactivated_at
        FROM strategies
        WHERE strategy_id = %s AND row_current_ind = TRUE
        FOR UPDATE
    """

    close_query = """
        UPDATE strategies
        SET row_current_ind = FALSE,
            row_end_ts = %s
        WHERE strategy_id = %s AND row_current_ind = TRUE
    """

    # The new row carries every field verbatim from the CLOSED row
    # (strategy_name + strategy_version are the SCD2 natural key and
    # MUST match — they are also guarded by the immutability trigger
    # across the logical-entity lifecycle).  ``activated_at`` /
    # ``deactivated_at`` use COALESCE(caller_arg, current_row[col]) so
    # that callers updating only ONE of the two timestamps don't wipe
    # the other one from the audit chain (Glokta P1-1: "activated_at
    # forgotten on deactivate would make the current row claim it was
    # deactivated without ever being activated").  ``status`` comes
    # from the caller; the new ``strategy_id`` is auto-generated from
    # the sequence.  ``updated_at`` + ``row_start_ts`` are explicit
    # NOW() so the SCD temporal chain is coherent (new row's
    # row_start_ts matches old row's row_end_ts).
    insert_query = """
        INSERT INTO strategies (
            platform_id, strategy_name, strategy_version, strategy_type, domain,
            config, status, activated_at, deactivated_at, notes, description,
            created_by, paper_trades_count, paper_roi, live_trades_count, live_roi,
            row_current_ind, row_start_ts, row_end_ts,
            created_at, updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            TRUE, %s, NULL,
            CURRENT_TIMESTAMP, %s
        )
        RETURNING strategy_id
    """

    def _attempt_supersede() -> bool:
        """One supersede attempt (fetch FOR UPDATE → NOW → close → insert).

        Wrapped in ``retry_on_scd_unique_conflict`` so that if two concurrent
        callers both reach the INSERT despite the FOR UPDATE (e.g., two
        first-time supersedes on distinct strategy_ids that happen to be
        racing the same (name, version) — unusual but possible during
        migration windows), the second caller retries after seeing the
        winner's row and no-ops cleanly.
        """
        with get_cursor(commit=True) as cur:
            # 1a: lookup + LOCK the current row (FOR UPDATE)
            cur.execute(fetch_query, (strategy_id,))
            current = cur.fetchone()
            if not current:
                return False

            # 1b: server-side NOW() snapshot so row_end_ts on the close and
            # row_start_ts on the new row agree to the microsecond (matches
            # the crud_positions / crud_markets supersede precedent — avoids
            # gap/overlap between the two clocks that any client-side
            # datetime.now() would create).
            cur.execute("SELECT NOW() AS ts")
            now_row = cur.fetchone()
            now_ts = now_row["ts"]

            # 2: close the current row
            cur.execute(close_query, (now_ts, strategy_id))

            # 3: insert the new (superseding) row.
            # COALESCE the caller's activated_at / deactivated_at with the
            # current row's values (P1-1): callers updating only one of the
            # two must not wipe the other.
            cur.execute(
                insert_query,
                (
                    current["platform_id"],
                    current["strategy_name"],
                    current["strategy_version"],
                    current["strategy_type"],
                    current["domain"],
                    # config: JSONB column; psycopg2 stores the value verbatim,
                    # so we pass the dict-or-str returned from the SELECT
                    # directly.  (``_convert_config_strings_to_decimal`` is
                    # a read-side convenience; round-trip through JSONB on
                    # INSERT does not need it.)
                    json.dumps(current["config"], cls=DecimalEncoder)
                    if not isinstance(current["config"], str)
                    else current["config"],
                    new_status,
                    activated_at if activated_at is not None else current["activated_at"],
                    deactivated_at if deactivated_at is not None else current["deactivated_at"],
                    current["notes"],
                    current["description"],
                    current["created_by"],
                    current["paper_trades_count"],
                    current["paper_roi"],
                    current["live_trades_count"],
                    current["live_roi"],
                    now_ts,  # row_start_ts — matches the close row's row_end_ts
                    now_ts,  # updated_at
                ),
            )
            result = cur.fetchone()
            return result is not None

    return retry_on_scd_unique_conflict(
        _attempt_supersede,
        "idx_strategies_name_version_current",
        business_key={"strategy_id": strategy_id, "new_status": new_status},
    )


def update_strategy_metrics(
    strategy_id: int,
    paper_roi: Decimal | None = None,
    live_roi: Decimal | None = None,
    paper_trades_count: int | None = None,
    live_trades_count: int | None = None,
) -> bool:
    """
    Update strategy performance metrics via SCD Type 2 supersede.

    Post-Migration 0064, the ``strategies`` table is SCD Type 2.  Metric
    updates are recorded as a close-and-insert supersede (same pattern as
    ``update_strategy_status``): the current row has ``row_current_ind``
    flipped to FALSE and ``row_end_ts`` set to NOW(), then a new row is
    INSERTed with the same ``(strategy_name, strategy_version)`` natural
    key and the updated metric values carried forward alongside
    unchanged fields.

    Args:
        strategy_id: Strategy row ID.  Must reference a CURRENT row
            (``row_current_ind = TRUE``); superseding a historical row is
            not supported and returns False.
        paper_roi: Paper trading ROI (optional — None means "preserve existing").
        live_roi: Live trading ROI (optional).
        paper_trades_count: Paper trade count (optional).
        live_trades_count: Live trade count (optional).

    Returns:
        bool: True if superseded, False if strategy not found or not current.

    Raises:
        ValueError: If all four metric arguments are None (nothing to update).

    Educational Note:
        Metrics are MUTABLE across SCD2 versions.  Config remains IMMUTABLE
        — the immutability trigger ``trg_strategies_immutability`` guards
        ``config``, ``strategy_version``, ``strategy_name``,
        ``strategy_type``.  The CLOSE-UPDATE touches only ``row_current_ind``
        and ``row_end_ts`` (neither guarded), so the trigger passes.

    Related:
        - ``update_strategy_status`` — sibling supersede for the status field
        - Glokta P0-1 / Ripley #NEW-A: ``StrategyManager.update_metrics``
          converted to call this CRUD to eliminate the parallel in-place
          UPDATE that bypassed SCD2.
    """
    if all(v is None for v in (paper_roi, live_roi, paper_trades_count, live_trades_count)):
        raise ValueError("At least one metric must be provided")

    fetch_query = """
        SELECT strategy_name, strategy_version, strategy_type, platform_id,
               domain, config, notes, description, created_by, status,
               paper_trades_count, paper_roi, live_trades_count, live_roi,
               activated_at, deactivated_at
        FROM strategies
        WHERE strategy_id = %s AND row_current_ind = TRUE
        FOR UPDATE
    """

    close_query = """
        UPDATE strategies
        SET row_current_ind = FALSE,
            row_end_ts = %s
        WHERE strategy_id = %s AND row_current_ind = TRUE
    """

    insert_query = """
        INSERT INTO strategies (
            platform_id, strategy_name, strategy_version, strategy_type, domain,
            config, status, activated_at, deactivated_at, notes, description,
            created_by, paper_trades_count, paper_roi, live_trades_count, live_roi,
            row_current_ind, row_start_ts, row_end_ts,
            created_at, updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            TRUE, %s, NULL,
            CURRENT_TIMESTAMP, %s
        )
        RETURNING strategy_id
    """

    def _attempt_supersede() -> bool:
        with get_cursor(commit=True) as cur:
            cur.execute(fetch_query, (strategy_id,))
            current = cur.fetchone()
            if not current:
                return False

            cur.execute("SELECT NOW() AS ts")
            now_ts = cur.fetchone()["ts"]

            cur.execute(close_query, (now_ts, strategy_id))

            cur.execute(
                insert_query,
                (
                    current["platform_id"],
                    current["strategy_name"],
                    current["strategy_version"],
                    current["strategy_type"],
                    current["domain"],
                    json.dumps(current["config"], cls=DecimalEncoder)
                    if not isinstance(current["config"], str)
                    else current["config"],
                    current["status"],
                    current["activated_at"],
                    current["deactivated_at"],
                    current["notes"],
                    current["description"],
                    current["created_by"],
                    paper_trades_count
                    if paper_trades_count is not None
                    else current["paper_trades_count"],
                    paper_roi if paper_roi is not None else current["paper_roi"],
                    live_trades_count
                    if live_trades_count is not None
                    else current["live_trades_count"],
                    live_roi if live_roi is not None else current["live_roi"],
                    now_ts,  # row_start_ts
                    now_ts,  # updated_at
                ),
            )
            result = cur.fetchone()
            return result is not None

    return retry_on_scd_unique_conflict(
        _attempt_supersede,
        "idx_strategies_name_version_current",
        business_key={"strategy_id": strategy_id, "metric_update": True},
    )


def list_strategies(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    List all strategies with optional status filtering and pagination.

    Args:
        status: Optional filter by status ("draft", "testing", "active", "deprecated")
        limit: Maximum number of strategies to return (default: 100)
        offset: Number of strategies to skip for pagination (default: 0)

    Returns:
        List of strategy dictionaries ordered by created_at (newest first)

    Educational Note:
        This function provides a simple listing of ALL strategies, regardless
        of version relationships. Use this for:
        - Admin dashboards showing all strategies
        - Database integrity verification (e.g., after SQL injection tests)
        - Auditing strategy counts

        For version-aware queries (e.g., "get latest active version of X"),
        use get_active_strategy_version() instead.

    Example:
        >>> # List all strategies
        >>> all_strategies = list_strategies()
        >>> len(all_strategies)
        15

        >>> # List only active strategies
        >>> active = list_strategies(status="active")
        >>> # Pagination: get page 2 (strategies 100-199)
        >>> page2 = list_strategies(limit=100, offset=100)
    """
    # Post-Migration 0064: every branch filters by row_current_ind = TRUE
    # so ``list_strategies(status="active")`` returns only LIVE active
    # strategies (not historical SCD rows whose status was 'active' before
    # they were superseded).  Glokta P0-3 / Ripley #NEW-C.
    if status:
        query = """
            SELECT *
            FROM strategies
            WHERE status = %s AND row_current_ind = TRUE
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        results = fetch_all(query, (status, limit, offset))
    else:
        query = """
            SELECT *
            FROM strategies
            WHERE row_current_ind = TRUE
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        results = fetch_all(query, (limit, offset))

    # Convert config Decimal strings back to Decimal for consistency
    for result in results:
        if result.get("config"):
            result["config"] = _convert_config_strings_to_decimal(result["config"])

    return results
