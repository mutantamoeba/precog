"""CRUD operations for positions and trades.

Extracted from crud_operations.py during Phase 1b domain split.

Tables covered:
    - positions: SCD Type 2 versioned position tracking
    - trades: Execution event records
"""

import json
import logging
from decimal import Decimal
from typing import Any, cast

from psycopg2.extras import Json

from .connection import fetch_all, fetch_one, get_cursor
from .crud_shared import (
    VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION,
    DecimalEncoder,
    ExecutionEnvironment,
    retry_on_scd_unique_conflict,
    validate_decimal,
)

logger = logging.getLogger(__name__)


def _jsonb_dumps(obj: Any) -> str:
    """
    JSON serializer for JSONB columns that preserves Decimal precision.

    Uses ``DecimalEncoder`` from ``crud_shared`` to serialize ``Decimal``
    values as their string representation (e.g. ``Decimal("0.6500")`` ->
    ``"0.6500"``). Required because ``psycopg2.extras.Json`` defaults to
    plain ``json.dumps`` which raises ``TypeError: Object of type Decimal
    is not JSON serializable`` when the dict contains ``Decimal`` values.

    This is the Marvin blocking-fix for the #629 PR (session 42e):
    ``set_trailing_stop_state`` callers in ``position_manager.py`` build
    ``trailing_stop_state`` dicts containing ``Decimal`` values at every
    level (``activation_price``, ``highest_price``, ``current_stop_price``,
    and nested ``config.*``). Without this encoder, every real production
    call would crash at the INSERT boundary.

    Round-trip semantics: on the READ path, psycopg2's JSONB decoder
    returns the stored value as a Python string (not Decimal). Consumers
    that need Decimal semantics must parse the string back with
    ``Decimal(value)`` at read time. See #669 for the symmetric
    read-path fix in ``check_trailing_stop_trigger``.

    Usage::

        from psycopg2.extras import Json
        cur.execute(sql, (Json(trailing_stop_state, dumps=_jsonb_dumps), ...))
    """
    return json.dumps(obj, cls=DecimalEncoder)


def get_positions_with_pnl(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get current positions with calculated P&L values.

    Returns positions with unrealized and realized P&L calculations
    suitable for TUI display in the position viewer.

    Args:
        status: Filter by status ('open', 'closed', or None for all)
        limit: Maximum number of positions to return
        offset: Number of positions to skip for pagination

    Returns:
        List of position dictionaries with P&L fields:
        - position_id, ticker, side, quantity, entry_price, current_price
        - status, unrealized_pnl, realized_pnl, pnl_percent

    Example:
        >>> positions = get_positions_with_pnl(status='open')
        >>> for p in positions:
        ...     print(f"{p['ticker']}: {p['unrealized_pnl']:+.2f}")

    Educational Note:
        P&L calculation depends on position side:
        - YES side: (current_price - entry_price) * quantity
        - NO side: (entry_price - current_price) * quantity

        Unrealized P&L uses current market price; realized P&L uses
        actual exit price for closed positions.

    Reference:
        - ADR-018: Position tracking with SCD Type 2
        - TUI Position Viewer Screen
    """
    # Migration 0021: markets is now a dimension table (no SCD).
    # Pricing comes from market_snapshots (SCD Type 2 fact table).
    # JOINs: positions → markets (via market_internal_id INTEGER) → market_snapshots (via id)
    query = """
        SELECT
            p.position_id,
            m.ticker,
            p.side,
            p.quantity,
            p.entry_price,
            COALESCE(ms.yes_ask_price, p.entry_price) as current_price,
            p.status,
            p.exit_price,
            p.realized_pnl,
            -- Calculate unrealized P&L based on side
            CASE
                WHEN p.side = 'yes' THEN
                    (COALESCE(ms.yes_ask_price, p.entry_price) - p.entry_price) * p.quantity
                WHEN p.side = 'no' THEN
                    (p.entry_price - COALESCE(ms.no_ask_price, p.entry_price)) * p.quantity
                ELSE 0
            END as unrealized_pnl,
            -- Calculate P&L percentage
            CASE
                WHEN p.entry_price > 0 THEN
                    CASE
                        WHEN p.side = 'yes' THEN
                            ((COALESCE(ms.yes_ask_price, p.entry_price) - p.entry_price) / p.entry_price) * 100
                        WHEN p.side = 'no' THEN
                            ((p.entry_price - COALESCE(ms.no_ask_price, p.entry_price)) / p.entry_price) * 100
                        ELSE 0
                    END
                ELSE 0
            END as pnl_percent
        FROM positions p
        LEFT JOIN markets m ON p.market_internal_id = m.id
        LEFT JOIN market_snapshots ms ON ms.market_id = m.id AND ms.row_current_ind = TRUE
        WHERE p.row_current_ind = TRUE
    """
    params: list[Any] = []

    if status is not None:
        query += " AND LOWER(p.status) = LOWER(%s)"
        params.append(status)

    query += " ORDER BY p.entry_time DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    return fetch_all(query, tuple(params))


# =============================================================================
# POSITION OPERATIONS
# =============================================================================


# =============================================================================
# POSITION OPERATIONS
# =============================================================================


def create_position(
    market_internal_id: int,
    strategy_id: int,
    model_id: int,
    side: str,
    quantity: int,
    entry_price: Decimal,
    execution_environment: ExecutionEnvironment,
    target_price: Decimal | None = None,
    stop_loss_price: Decimal | None = None,
    trailing_stop_state: dict | None = None,
    position_metadata: dict | None = None,
    # ⭐ ATTRIBUTION ARCHITECTURE (Migration 020) - NEW parameters
    calculated_probability: Decimal | None = None,
    market_price_at_entry: Decimal | None = None,
) -> int:
    """
    Create new position with status = 'open' and immutable entry-time attribution.

    Args:
        market_internal_id: Integer foreign key to markets(id)
        strategy_id: Foreign key to strategies (immutable version)
        model_id: Foreign key to probability_models (immutable version)
        side: 'YES' or 'NO'
        quantity: Number of contracts
        entry_price: Entry price as DECIMAL(10,4)
        execution_environment: Execution context — REQUIRED, no default.
            Must be one of 'live' (production), 'paper' (demo API), or
            'backtest' (simulation). Note: 'unknown' is NOT valid here —
            it's reserved for ``account_balance`` only as a forensic
            tombstone (Migration 0051). Callers MUST derive this from
            ``derive_execution_environment(app_env, market_mode)`` at
            the application boundary or pass an explicit literal — never
            inherit a default. The optional-default precedent removed in
            the #622+#686 synthesis PR was the literal cause of #662, #686,
            and #622. See findings_622_686_synthesis.md.
        target_price: Take-profit target
        stop_loss_price: Stop-loss price
        trailing_stop_state: Trailing stop configuration as JSONB
        position_metadata: Additional metadata
        calculated_probability: Model's predicted win probability at entry (immutable snapshot)
        market_price_at_entry: Kalshi market price at entry (immutable snapshot)

    Returns:
        id (surrogate key) of newly created position

    Educational Note:
        Attribution Architecture (Migration 020):
        - calculated_probability + market_price_at_entry are IMMUTABLE entry snapshots
        - edge_at_entry automatically calculated: calculated_probability - market_price_at_entry
        - Enables strategy A/B testing: "Did entry v1.5 outperform entry v1.6?"
        - Performance analytics: "Which models have highest position ROI?"
        - Immutability enforced by ADR-018 (no updates after position creation)
        - 20-100x faster than JSONB for analytics (B-tree index vs GIN index)

        Dual-Key Structure (Migration 015):
        - id SERIAL (surrogate key) - returned by this function
        - position_id VARCHAR (business key) - auto-generated as POS-{id}
        - Enables SCD Type 2 versioning (multiple versions of same position)

    Example:
        >>> pos_id = create_position(
        ...     market_internal_id=42,
        ...     strategy_id=1,
        ...     model_id=2,
        ...     side='YES',
        ...     quantity=100,
        ...     entry_price=Decimal("0.5200"),
        ...     stop_loss_price=Decimal("0.4800"),
        ...     calculated_probability=Decimal("0.6250"),  # Model prediction
        ...     market_price_at_entry=Decimal("0.5200"),   # Kalshi price
        ...     execution_environment='paper'              # Demo API testing
        ... )
        >>> # Returns surrogate id (e.g., 1), position_id auto-set to 'POS-1'
        >>> # edge_at_entry automatically set to 0.1050 (0.6250 - 0.5200)

    Validation:
        - calculated_probability must be in [0.0, 1.0] range (CHECK constraint)
        - market_price_at_entry must be in [0.0, 1.0] range (CHECK constraint)
        - Both are optional (NULL allowed for legacy data or non-model positions)

    Related ADRs:
        - ADR-091: Explicit Columns for Trade/Position Attribution
        - ADR-018: Immutable Versioning (positions locked to strategy/model version at entry)
        - ADR-002: Decimal Precision for All Financial Data

    References:
        - Migration 020: Position Attribution
        - docs/analysis/SCHEMA_ANALYSIS_2025-11-21.md (Gap #2: Position Attribution)
    """
    # Validate execution_environment before any DB interaction. Typo defense
    # (Marvin's recommendation from #662): 'Live', 'demo', and other
    # near-misses must fail loudly at the function boundary, not silently
    # bypass the CHECK constraint via psycopg2 type coercion.
    # Note: positions/trades only allow 3 values (no 'unknown'); the broader
    # 4-value allowlist applies to account_balance only. See
    # crud_shared.VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION.
    if execution_environment not in VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION:
        msg = (
            f"Invalid execution_environment: {execution_environment!r}. "
            f"Must be one of {sorted(VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION)}. "
            f"Note: 'unknown' is reserved for account_balance only and is "
            f"not valid on positions/trades."
        )
        raise ValueError(msg)

    # ⭐ Calculate edge_at_entry if both probability and price provided
    edge_at_entry: Decimal | None = None
    if calculated_probability is not None and market_price_at_entry is not None:
        edge_at_entry = calculated_probability - market_price_at_entry

    # Step 1: INSERT with placeholder position_id (will be updated immediately)
    insert_query = """
        INSERT INTO positions (
            position_id, market_internal_id, strategy_id, model_id, side,
            quantity, entry_price,
            target_price, stop_loss_price,
            trailing_stop_state, position_metadata,
            status, row_current_ind, entry_time,
            calculated_probability, edge_at_entry, market_price_at_entry,
            execution_environment
        )
        VALUES ('TEMP', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', TRUE, NOW(), %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        market_internal_id,
        strategy_id,
        model_id,
        side,
        quantity,
        entry_price,
        target_price,
        stop_loss_price,
        trailing_stop_state,
        position_metadata,
        calculated_probability,
        edge_at_entry,
        market_price_at_entry,
        execution_environment,
    )

    with get_cursor(commit=True) as cur:
        # Get surrogate id
        cur.execute(insert_query, params)
        result = cur.fetchone()
        surrogate_id = cast("int", result["id"])

        # Step 2: UPDATE to set correct position_id (POS-{id} format)
        update_query = """
            UPDATE positions
            SET position_id = %s
            WHERE id = %s
        """
        cur.execute(update_query, (f"POS-{surrogate_id}", surrogate_id))

        return surrogate_id


def get_current_positions(
    status: str | None = None,
    market_internal_id: int | None = None,
    execution_environment: ExecutionEnvironment | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get current positions (row_current_ind = TRUE) with pagination.

    Args:
        status: Filter by status ('open', 'closed', etc.)
        market_internal_id: Filter by market_internal_id (integer FK to markets.id)
        execution_environment: Filter by environment ('live', 'paper', 'backtest').
            If None, returns positions from all environments.
        limit: Maximum number of positions to return (default: 100)
        offset: Number of positions to skip for pagination (default: 0)

    Returns:
        List of current positions

    Example:
        >>> open_positions = get_current_positions(status='open')
        >>> # Only paper trading positions
        >>> paper_positions = get_current_positions(execution_environment='paper')
        >>> # Pagination: get page 2 (positions 100-199)
        >>> page2 = get_current_positions(limit=100, offset=100)
    """
    # Migration 0021: markets is dimension (no SCD), pricing from market_snapshots.
    query = """
        SELECT p.*, m.ticker, ms.yes_ask_price as current_market_price
        FROM positions p
        JOIN markets m ON p.market_internal_id = m.id
        LEFT JOIN market_snapshots ms ON ms.market_id = m.id AND ms.row_current_ind = TRUE
        WHERE p.row_current_ind = TRUE
    """
    params: list[Any] = []

    if status:
        query += " AND p.status = %s"
        params.append(status)

    if market_internal_id:
        query += " AND p.market_internal_id = %s"
        params.append(market_internal_id)

    if execution_environment is not None:
        query += " AND p.execution_environment = %s"
        params.append(execution_environment)

    query += " ORDER BY p.entry_time DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    return fetch_all(query, tuple(params))


def update_position_price(
    position_id: int, current_price: Decimal, trailing_stop_state: dict | None = None
) -> int:
    """
    Update position with new price using SCD Type 2 versioning.

    Used for monitoring price changes and updating trailing stops.

    Args:
        position_id: Position surrogate id (int) to update
        current_price: Current market price
        trailing_stop_state: Updated trailing stop state

    Returns:
        id (surrogate key) of newly created version

    Educational Note:
        SCD Type 2 versioning creates NEW rows instead of updating:
        - Mark current version as historical (row_current_ind = FALSE)
        - INSERT new version with same position_id (business key)
        - New version gets new surrogate id but keeps same position_id

        Example: Position POS-1 price update
        Before: id=1, position_id='POS-1', price=0.52, row_current_ind=TRUE
        After:  id=1, position_id='POS-1', price=0.52, row_current_ind=FALSE (historical)
                id=2, position_id='POS-1', price=0.58, row_current_ind=TRUE (current)

    Example:
        >>> new_id = update_position_price(
        ...     position_id=1,  # Surrogate id
        ...     current_price=Decimal("0.5800"),
        ...     trailing_stop_state={"peak": "0.5800", "stop": "0.5500"}
        ... )
        >>> # Returns new surrogate id (e.g., 2)
    """
    # Get current version using surrogate id. We fetch OUTSIDE the retry
    # closure to (a) satisfy the "raise ValueError if missing" contract
    # immediately (no retry on missing positions) and (b) capture the
    # business key (position_id column) so retries can re-fetch by business
    # key even after the sibling caller creates a new surrogate id.
    initial_current = fetch_one(
        "SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not initial_current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    position_bk = initial_current["position_id"]  # Business key (stable across retries)

    new_trailing_stop = (
        trailing_stop_state
        if trailing_stop_state is not None
        else initial_current["trailing_stop_state"]
    )

    # ⭐ Early return optimization (Issue #113):
    # Skip SCD Type 2 versioning if no state actually changed.
    # This prevents 3600+ unnecessary writes/hour in monitoring loops.
    # The check runs against the initial fetch; if a sibling caller has
    # since changed state we fall through and let the closure re-derive
    # the new version from fresh values.
    price_unchanged = initial_current["current_price"] == current_price
    trailing_stop_unchanged = initial_current["trailing_stop_state"] == new_trailing_stop
    if price_unchanged and trailing_stop_unchanged:
        # No state change - return existing id without creating new version
        return cast("int", initial_current["id"])

    def _attempt_close_and_insert() -> int:
        """One attempt at the SCD close+insert sequence for update_position_price.

        Opens its own ``get_cursor(commit=True)`` block so the retry helper
        can run this closure twice and get a fresh transaction (with a fresh
        MVCC snapshot) on the second invocation.

        Issue #626: concurrent-update race on positions. Two concurrent
        update_position_price calls for the same surrogate id can both
        proceed past their independent close (the second as a no-op) and
        both INSERT, colliding on idx_positions_unique_current. On retry,
        we look up the fresh current row by BUSINESS KEY (position_id
        column) — the surrogate id from the outer fetch is stale after the
        sibling caller created a new version.
        """
        with get_cursor(commit=True) as cur:
            # Capture timestamp once for temporal continuity within THIS attempt.
            cur.execute("SELECT NOW() AS ts")
            now = cur.fetchone()["ts"]

            # Step 1: Lock the current row by business key. FOR UPDATE
            # serializes concurrent updates against the same position_bk.
            # On retry the sibling caller's row is visible and gets locked.
            cur.execute(
                """
                SELECT id FROM positions
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                FOR UPDATE
                """,
                (position_bk,),
            )

            # Step 2: Re-fetch the full current row by business key. On the
            # first attempt this equals initial_current; on retry the
            # sibling caller's new version is the current row.
            cur.execute(
                """
                SELECT * FROM positions
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            current = cur.fetchone()
            if current is None:
                # Extraordinary state: the business key had a current row
                # when we fetched outside the closure but no current row
                # now. A concurrent close_position may have deleted the
                # current version between the outer fetch and this attempt.
                # Surface loudly rather than silently insert a new current
                # row for a position that has been closed.
                raise RuntimeError(
                    f"Position business key {position_bk!r} has no current "
                    f"row inside the retry closure (was present in the "
                    f"outer fetch). A concurrent close_position may have "
                    f"closed this position."
                )

            # Brawne CONCERN 1 parallel (#626 diff-scoped review) +
            # Marvin recommendation #1 (#627 sentinel pass): refuse to
            # update a position that is not in the 'open' state. Without
            # this check, an update racing with a concurrent close hits
            # this closure on retry, sees a non-open status on the
            # sibling's committed row, and silently writes a new SCD
            # version with the caller's price into a position that has
            # already exited or settled. The status field is preserved
            # by the INSERT below, so the row stays in its terminal
            # state -- but the prices/trailing_stop are overwritten with
            # stale values from a caller who believed it was updating an
            # open position.
            #
            # Why ``!= "open"`` instead of ``== "closed"``: positions
            # schema (migration 0001) allows ``{'open', 'closed',
            # 'settled'}`` and the column is nullable. The complete
            # non-open state space is ``{'closed', 'settled', None}``.
            # ``'settled'`` is currently unreachable (no writer sets it
            # on positions.status today) but Kalshi settlement semantics
            # in api_connectors/types.py and migration 0024's defaulting
            # behavior leave the door open. NULL is similarly latent.
            # Use the positive allow-list to close both holes.
            #
            # Raise ValueError so position_manager.update_position's
            # outer ValueError handler can surface the conflict to the
            # caller (parity with "Position not found").
            if current["status"] != "open":
                raise ValueError(
                    f"Position business key {position_bk!r} is not open "
                    f"(observed status: {current['status']!r}). A "
                    f"concurrent close_position or settlement may have "
                    f"transitioned this position between the outer fetch "
                    f"and this retry attempt. Refusing to write an "
                    f"update for a position that is no longer open."
                )

            # Re-derive trailing_stop from the fresh current row so retries
            # use the sibling's committed value when caller did not override.
            fresh_trailing_stop = (
                trailing_stop_state
                if trailing_stop_state is not None
                else current["trailing_stop_state"]
            )

            # Step 3: Close current row by business key so the close and
            # the lock target the same row the partial unique index
            # protects.
            cur.execute(
                """
                UPDATE positions
                SET row_current_ind = FALSE,
                    row_end_ts = %s
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                """,
                (now, position_bk),
            )

            # Step 4: Insert new version with same position_id (business
            # key) but new id (surrogate). row_start_ts matches row_end_ts
            # on the historical row for Pattern 49 temporal continuity.
            # execution_environment is preserved from the original position
            # (Issue #662: Marvin sentinel pass found that omitting this
            # column silently flipped non-'live' positions to the column's
            # DEFAULT 'live' on every price update -- cross-environment
            # contamination with no audit signal).
            cur.execute(
                """
                INSERT INTO positions (
                    position_id, market_internal_id, strategy_id, model_id, side,
                    quantity, entry_price,
                    current_price, unrealized_pnl,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, last_check_time, execution_environment,
                    row_start_ts
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    current["position_id"],  # Copy business key from current version
                    current["market_internal_id"],
                    current["strategy_id"],
                    current["model_id"],
                    current["side"],
                    current["quantity"],
                    current["entry_price"],
                    current_price,
                    (current_price - current["entry_price"])
                    * current["quantity"],  # unrealized_pnl
                    current["target_price"],
                    current["stop_loss_price"],
                    fresh_trailing_stop,
                    current["position_metadata"],
                    current["status"],
                    current["entry_time"],
                    now,  # last_check_time
                    current["execution_environment"],  # Preserve execution environment
                    now,  # row_start_ts
                ),
            )
            result = cur.fetchone()
            if result is None or result.get("id") is None:
                raise RuntimeError(
                    "INSERT INTO positions RETURNING id produced no row -- "
                    "this should be impossible after a successful INSERT and "
                    "indicates a DB trigger or constraint suppressed the return."
                )
            return cast("int", result["id"])  # Return new surrogate id

    return retry_on_scd_unique_conflict(
        _attempt_close_and_insert,
        "idx_positions_unique_current",
        business_key={"position_id": position_bk},
        logger_override=logger,
    )


def close_position(
    position_id: int, exit_price: Decimal, exit_reason: str, realized_pnl: Decimal
) -> int:
    """
    Close position by updating status to 'closed'.

    Args:
        position_id: Position surrogate id (int) to close
        exit_price: Final exit price
        exit_reason: Reason for exit (e.g., 'target_hit', 'stop_loss', 'manual')
        realized_pnl: Realized profit/loss

    Returns:
        id (surrogate key) of closed version

    Example:
        >>> closed_id = close_position(
        ...     position_id=1,  # Surrogate id
        ...     exit_price=Decimal("0.6000"),
        ...     exit_reason='target_hit',
        ...     realized_pnl=Decimal("8.00")
        ... )
    """
    # Get current version using surrogate id. Fetch OUTSIDE the retry
    # closure to satisfy the "raise ValueError if missing" contract
    # immediately and capture the business key for retry correctness.
    initial_current = fetch_one(
        "SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not initial_current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    position_bk = initial_current["position_id"]  # Business key (stable across retries)

    def _attempt_close_and_insert() -> int:
        """One attempt at the SCD close+insert sequence for close_position.

        Opens its own ``get_cursor(commit=True)`` block so the retry helper
        can run this closure twice and get a fresh transaction on the
        second invocation.

        Issue #627: concurrent-close race on positions. Two concurrent
        close_position calls for the same position (e.g., target_hit and
        stop_loss firing in the same monitor tick) can both proceed past
        the close (the second as a no-op) and both INSERT, colliding on
        idx_positions_unique_current. On retry, we look up the fresh
        current row by BUSINESS KEY (position_id column) — the surrogate
        id from the outer fetch is stale after the sibling caller created
        a new version.
        """
        with get_cursor(commit=True) as cur:
            # Capture timestamp once for temporal continuity within THIS attempt.
            cur.execute("SELECT NOW() AS ts")
            now = cur.fetchone()["ts"]

            # Step 1: Lock the current row by business key. FOR UPDATE
            # serializes concurrent close calls against the same position_bk.
            cur.execute(
                """
                SELECT id FROM positions
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                FOR UPDATE
                """,
                (position_bk,),
            )

            # Step 2: Re-fetch the full current row by business key so
            # retries copy the sibling's committed values into the new
            # closed version (not stale values from the outer fetch).
            cur.execute(
                """
                SELECT * FROM positions
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            current = cur.fetchone()
            if current is None:
                raise RuntimeError(
                    f"Position business key {position_bk!r} has no current "
                    f"row inside the retry closure (was present in the "
                    f"outer fetch). A concurrent close_position may have "
                    f"already closed this position."
                )

            # Brawne CONCERN 1 (#627 diff-scoped review) + Marvin
            # recommendation #1 (sentinel pass): refuse to close a
            # position that is not in the 'open' state. Without this
            # check, two concurrent close_position callers can BOTH
            # succeed -- the second's retry attempt sees a non-open
            # status from the first's commit on re-fetch, then proceeds
            # to close the (already-terminal) current row again with
            # the SECOND caller's exit_price and realized_pnl, silently
            # overwriting the first close. The OLD behavior raised
            # UniqueViolation in this race, which propagated past
            # position_manager.close_position's `except ValueError`
            # handler -- loud failure. Preserve that loudness by
            # raising ValueError here so the outer handler can surface
            # the conflict to the caller.
            #
            # Why ``!= "open"`` instead of ``== "closed"``: positions
            # schema (migration 0001) allows ``{'open', 'closed',
            # 'settled'}`` and the column is nullable. The complete
            # non-open state space is ``{'closed', 'settled', None}``.
            # ``'settled'`` is currently unreachable but Kalshi
            # settlement semantics may populate it in Phase 2+. Use the
            # positive allow-list to defend against the entire
            # non-open state space.
            if current["status"] != "open":
                raise ValueError(
                    f"Position business key {position_bk!r} is not open "
                    f"(observed status: {current['status']!r}). A "
                    f"concurrent close_position or settlement may have "
                    f"transitioned this position between the outer fetch "
                    f"and this retry attempt. Refusing to overwrite the "
                    f"existing terminal state with this caller's "
                    f"exit_price and realized_pnl."
                )

            # Step 3: Close current row by business key so the close and
            # the lock target the same row the partial unique index
            # protects.
            cur.execute(
                """
                UPDATE positions
                SET row_current_ind = FALSE,
                    row_end_ts = %s
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                """,
                (now, position_bk),
            )

            # Step 4: Insert closed version with same position_id (business
            # key). row_start_ts matches row_end_ts on the historical row
            # for Pattern 49 temporal continuity. execution_environment is
            # preserved from the original position.
            cur.execute(
                """
                INSERT INTO positions (
                    position_id, market_internal_id, strategy_id, model_id, side,
                    quantity, entry_price, exit_price, current_price,
                    realized_pnl,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, exit_time, execution_environment,
                    row_start_ts
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'closed', %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    current["position_id"],  # Copy business key from current version
                    current["market_internal_id"],
                    current["strategy_id"],
                    current["model_id"],
                    current["side"],
                    current["quantity"],
                    current["entry_price"],
                    exit_price,
                    exit_price,  # Set current_price to exit_price for closed positions
                    realized_pnl,
                    current["target_price"],
                    current["stop_loss_price"],
                    current["trailing_stop_state"],
                    current["position_metadata"],
                    current["entry_time"],
                    now,  # exit_time
                    current["execution_environment"],  # Preserve execution environment
                    now,  # row_start_ts
                ),
            )

            result = cur.fetchone()
            if result is None or result.get("id") is None:
                raise RuntimeError(
                    "INSERT INTO positions RETURNING id produced no row -- "
                    "this should be impossible after a successful INSERT and "
                    "indicates a DB trigger or constraint suppressed the return."
                )
            return cast("int", result["id"])  # Return new surrogate id

    return retry_on_scd_unique_conflict(
        _attempt_close_and_insert,
        "idx_positions_unique_current",
        business_key={"position_id": position_bk},
        logger_override=logger,
    )


def set_trailing_stop_state(
    position_id: int,
    trailing_stop_state: dict,
    current_price: Decimal | None = None,
    unrealized_pnl: Decimal | None = None,
) -> int:
    """
    Update position's trailing stop state (and optionally current_price / unrealized_pnl)
    using SCD Type 2 versioning.

    This is the canonical CRUD entry point for both ``initialize_trailing_stop``
    (which only mutates ``trailing_stop_state``) and ``update_trailing_stop``
    (which additionally mutates ``current_price`` and ``unrealized_pnl``) in
    ``position_manager``. Callers pass a fully-prepared ``trailing_stop_state``
    dict -- this function does not compute or modify the JSONB structure; it
    only persists the SCD version.

    Args:
        position_id: Position surrogate id (int) to update.
        trailing_stop_state: New trailing stop state dict (wrapped in
            ``psycopg2.extras.Json`` for JSONB serialization). Required --
            there is no legitimate reason to call this helper without a
            trailing stop state.
        current_price: Optional new current_price. If None, the current row's
            ``current_price`` is preserved (initialize-trailing-stop path). If
            provided, the INSERT uses this value (update-trailing-stop path).
        unrealized_pnl: Optional new unrealized_pnl. If None, the current
            row's ``unrealized_pnl`` is preserved. If provided, the INSERT
            uses this value. Typically passed alongside ``current_price``
            because the update path recomputes PnL via
            ``PositionManager.calculate_position_pnl``.

    Returns:
        id (surrogate key) of newly created version.

    Raises:
        ValueError: If position not found, or if the current row's status is
            not ``'open'`` (closed/settled positions cannot have their
            trailing stop state mutated).
        RuntimeError: If the INSERT ... RETURNING id produces no row (DB
            trigger or constraint suppression — should be impossible).

    Canonical pattern:
        This function mirrors :func:`update_position_price` and
        :func:`close_position` (both adopted in PR #665 as canonical Pattern 49
        consumers). The shape is:

        1. Outer ``fetch_one`` by surrogate id to raise ValueError-not-found
           immediately and capture the business key.
        2. ``_attempt_close_and_insert`` closure opens its OWN
           ``with get_cursor(commit=True)`` block so the retry helper can
           rerun it in a fresh transaction.
        3. Inside the closure: capture ``NOW()`` once, FOR UPDATE lock by
           business key, re-fetch the current row, check status, close the
           current row, INSERT the new version copying Python values from
           the re-fetch.
        4. Wrap in ``retry_on_scd_unique_conflict`` keyed on
           ``idx_positions_unique_current``.

    Why not ``INSERT ... SELECT FROM positions``:
        Issue #629: the pre-PR-#665 position_manager.initialize_trailing_stop
        and update_trailing_stop methods both issued:

            UPDATE positions SET row_current_ind = FALSE WHERE id = %s;
            INSERT INTO positions (...) SELECT ... FROM positions
                WHERE id = %s AND row_current_ind = TRUE;

        in a single transaction. Under PostgreSQL READ COMMITTED, the INSERT's
        SELECT observes the UPDATE's row-level change within the same
        transaction, so the SELECT returns ZERO rows, the INSERT inserts
        nothing, and ``cur.fetchone()["id"]`` raises TypeError on the
        ``None`` result. Latent for 4.5 months because zero production
        callers and all tests mocked the cursor. This helper captures all
        row values into Python BEFORE the close, then INSERTs from Python
        values -- the same fix PR #665 applied to ``update_position_price``
        and ``close_position``.

    Why ``execution_environment`` appears explicitly:
        The pre-refactor ``INSERT ... SELECT`` preserved all columns including
        ``execution_environment`` implicitly. The refactor makes the INSERT
        column list explicit, so ``execution_environment`` must be copied
        explicitly from the re-fetched current row. Marvin's sentinel audit
        on #662 flagged the same bug in ``update_position_price`` (a
        separate PR); do NOT repeat it here.

    Example:
        >>> # Initialize a trailing stop on an existing open position
        >>> state = {
        ...     "config": {...},
        ...     "activated": False,
        ...     "activation_price": None,
        ...     "current_stop_price": Decimal("0.4500"),
        ...     "highest_price": Decimal("0.5000"),
        ... }
        >>> new_id = set_trailing_stop_state(
        ...     position_id=1,
        ...     trailing_stop_state=state,
        ... )
        >>>
        >>> # Update trailing stop with new price
        >>> state["highest_price"] = Decimal("0.6000")
        >>> state["current_stop_price"] = Decimal("0.5500")
        >>> new_id = set_trailing_stop_state(
        ...     position_id=new_id,
        ...     trailing_stop_state=state,
        ...     current_price=Decimal("0.6000"),
        ...     unrealized_pnl=Decimal("10.0000"),
        ... )

    Reference:
        - Issue #629: latent INSERT...SELECT bug in trailing stop write paths.
        - Issue #628: trailing stop race test coverage.
        - PR #665: canonical Pattern 49 adoption for positions
          (``update_position_price`` and ``close_position``).
        - Pattern 49 (DEVELOPMENT_PATTERNS_V1.30.md): SCD Race Prevention.
    """
    # Fetch OUTSIDE the retry closure to satisfy the "raise ValueError if
    # missing" contract immediately (no retry on missing positions) and
    # capture the business key (position_id column) so retries can re-fetch
    # by business key even after a sibling caller creates a new surrogate id.
    initial_current = fetch_one(
        "SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not initial_current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    position_bk = initial_current["position_id"]  # Business key (stable across retries)

    def _attempt_close_and_insert() -> int:
        """One attempt at the SCD close+insert sequence for set_trailing_stop_state.

        Opens its own ``get_cursor(commit=True)`` block so the retry helper
        can run this closure twice and get a fresh transaction (with a fresh
        MVCC snapshot) on the second invocation.

        Issue #629: concurrent-update race on the trailing-stop write paths.
        Two concurrent callers (e.g., ``initialize_trailing_stop`` racing
        with ``update_trailing_stop``) for the same surrogate id can both
        proceed past their independent close (the second as a no-op) and
        both INSERT, colliding on ``idx_positions_unique_current``. On retry,
        we look up the fresh current row by BUSINESS KEY (``position_id``
        column) -- the surrogate id from the outer fetch is stale after the
        sibling caller created a new version.
        """
        with get_cursor(commit=True) as cur:
            # Capture timestamp once for temporal continuity within THIS attempt.
            cur.execute("SELECT NOW() AS ts")
            now = cur.fetchone()["ts"]

            # Step 1: Lock the current row by business key. FOR UPDATE
            # serializes concurrent updates against the same position_bk.
            # On retry the sibling caller's row is visible and gets locked.
            cur.execute(
                """
                SELECT id FROM positions
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                FOR UPDATE
                """,
                (position_bk,),
            )

            # Step 2: Re-fetch the full current row by business key so the
            # INSERT copies Python values from the LOCKED row (not from a
            # post-UPDATE SELECT that would observe the close and return
            # zero rows -- the bug this function exists to fix).
            cur.execute(
                """
                SELECT * FROM positions
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            current = cur.fetchone()
            if current is None:
                # Extraordinary state: the business key had a current row
                # when we fetched outside the closure but no current row
                # now. A concurrent close_position may have deleted the
                # current version between the outer fetch and this attempt.
                raise RuntimeError(
                    f"Position business key {position_bk!r} has no current "
                    f"row inside the retry closure (was present in the "
                    f"outer fetch). A concurrent close_position may have "
                    f"closed this position."
                )

            # Mirror the hardened ``!= "open"`` guard from update_position_price
            # and close_position (PR #665). Refusing to mutate the trailing
            # stop on a non-open position is critical because the old
            # ``INSERT ... SELECT`` path silently succeeded against closed
            # positions (preserving the ``closed`` status in the new row)
            # which would have layered a new trailing_stop_state onto a
            # terminal position. The positive allow-list defends against
            # ``{'closed', 'settled', None}``.
            if current["status"] != "open":
                raise ValueError(
                    f"Position business key {position_bk!r} is not open "
                    f"(observed status: {current['status']!r}). A "
                    f"concurrent close_position or settlement may have "
                    f"transitioned this position between the outer fetch "
                    f"and this retry attempt. Refusing to write a trailing "
                    f"stop state update for a position that is no longer open."
                )

            # Resolve the price / pnl fields to persist. If the caller did
            # not pass them (initialize path), copy from the re-fetched
            # current row so the new version carries the up-to-date values
            # a sibling caller may have committed between the outer fetch
            # and this closure.
            new_current_price = (
                current_price if current_price is not None else current["current_price"]
            )
            new_unrealized_pnl = (
                unrealized_pnl if unrealized_pnl is not None else current["unrealized_pnl"]
            )

            # Step 3: Close current row by business key so the close and
            # the lock target the same row the partial unique index
            # protects. Uses the captured ``now`` placeholder (not a
            # literal NOW()) to honor Pattern 49's "single NOW() per
            # attempt" temporal-continuity rule.
            cur.execute(
                """
                UPDATE positions
                SET row_current_ind = FALSE,
                    row_end_ts = %s
                WHERE position_id = %s
                  AND row_current_ind = TRUE
                """,
                (now, position_bk),
            )

            # Step 4: Insert new version with same position_id (business
            # key) but new id (surrogate). All columns copied explicitly
            # from the re-fetched ``current`` row (NOT via SELECT FROM
            # positions, which would re-introduce the #629 bug).
            #
            # execution_environment is copied explicitly (Marvin sentinel
            # audit on #662: the pre-refactor INSERT ... SELECT preserved
            # it implicitly; the refactor must preserve it explicitly).
            #
            # trailing_stop_state is wrapped in psycopg2.extras.Json --
            # psycopg2's default adapter does not handle plain dicts, so
            # this is required whenever we pass a dict parameter bound for
            # a JSONB column. The canonical update_position_price and
            # close_position functions pass ``current["trailing_stop_state"]``
            # straight through without wrapping, which is a latent bug
            # (tracked separately) when the field is non-None on re-insert.
            cur.execute(
                """
                INSERT INTO positions (
                    position_id, market_internal_id, strategy_id, model_id, side,
                    quantity, entry_price,
                    current_price, unrealized_pnl, realized_pnl,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, last_check_time,
                    exit_price, exit_reason, exit_time,
                    calculated_probability, edge_at_entry, market_price_at_entry,
                    execution_environment,
                    row_start_ts, row_current_ind
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, TRUE
                )
                RETURNING id
                """,
                (
                    current["position_id"],  # Copy business key from current version
                    current["market_internal_id"],
                    current["strategy_id"],
                    current["model_id"],
                    current["side"],
                    current["quantity"],
                    current["entry_price"],
                    new_current_price,
                    new_unrealized_pnl,
                    current["realized_pnl"],
                    current["target_price"],
                    current["stop_loss_price"],
                    # Marvin blocking-fix (#629 PR review, session 42e):
                    # trailing_stop_state contains Decimal values built by
                    # position_manager (activation_price, highest_price,
                    # current_stop_price, config.*). Plain json.dumps cannot
                    # serialize Decimal. _jsonb_dumps uses DecimalEncoder so
                    # Decimals serialize as their str repr. Round-trip on
                    # read returns the string form; consumers that need
                    # Decimal semantics must parse on read.
                    Json(trailing_stop_state, dumps=_jsonb_dumps),
                    current["position_metadata"],
                    current["status"],
                    current["entry_time"],
                    now,  # last_check_time
                    current["exit_price"],
                    current["exit_reason"],
                    current["exit_time"],
                    current["calculated_probability"],
                    current["edge_at_entry"],
                    current["market_price_at_entry"],
                    current["execution_environment"],  # Preserve execution environment
                    now,  # row_start_ts
                ),
            )
            result = cur.fetchone()
            if result is None or result.get("id") is None:
                raise RuntimeError(
                    "INSERT INTO positions RETURNING id produced no row -- "
                    "this should be impossible after a successful INSERT and "
                    "indicates a DB trigger or constraint suppressed the return."
                )
            return cast("int", result["id"])  # Return new surrogate id

    return retry_on_scd_unique_conflict(
        _attempt_close_and_insert,
        "idx_positions_unique_current",
        business_key={"position_id": position_bk},
        logger_override=logger,
    )


# =============================================================================
# TRADE OPERATIONS
# =============================================================================


# =============================================================================
# TRADE OPERATIONS
# =============================================================================


def create_trade(
    market_internal_id: int,
    side: str,
    quantity: int,
    price: Decimal,
    execution_environment: ExecutionEnvironment,
    order_id: int | None = None,
    is_taker: bool | None = None,
    fees: Decimal | None = None,
    trade_metadata: dict | None = None,
    calculated_probability: Decimal | None = None,
    market_price: Decimal | None = None,
) -> int:
    """
    Record an executed trade (fill event).

    Trades are IMMUTABLE fill records — one row per exchange execution event.
    Attribution (strategy, model, edge, position) lives on the associated
    order, not on the trade. Query attribution via JOIN to orders table.

    Args:
        market_internal_id: Integer foreign key to markets(id)
        side: Trade direction - 'buy' or 'sell'
        quantity: Number of contracts filled
        price: Execution price as DECIMAL(10,4) in [0, 1]
        execution_environment: Execution context — REQUIRED, no default.
            Must be one of 'live', 'paper', or 'backtest'. Note: 'unknown'
            is reserved for ``account_balance`` only and is not valid here.
            See ``create_position`` and findings_622_686_synthesis.md for
            the full rationale on why this is required-without-default.
        order_id: Integer FK to orders(id) — links fill to its order
        is_taker: Whether this fill was a taker (True) or maker (False)
        fees: Per-fill fees as DECIMAL(10,4)
        trade_metadata: Additional metadata as JSONB
        calculated_probability: Model-predicted probability at execution [0, 1]
        market_price: Kalshi market price at execution [0, 1]

    Returns:
        id of newly created trade

    Educational Note:
        Migration 0025 Redesign:
        - Attribution (strategy_id, model_id, edge_id, position_id) moved to orders
        - Trades are pure execution records (what actually happened at the exchange)
        - edge_value auto-calculated: calculated_probability - market_price
        - Query attribution: SELECT o.strategy_id FROM orders o JOIN trades t ON t.order_id = o.id

    Example:
        >>> trade_id = create_trade(
        ...     market_internal_id=42,
        ...     side='buy',
        ...     quantity=10,
        ...     price=Decimal("0.5200"),
        ...     order_id=7,
        ...     is_taker=True,
        ...     fees=Decimal("0.0100"),
        ...     execution_environment='paper',
        ... )

    References:
        - Migration 0025: orders/trades redesign
        - Issue #336: council-approved separation of orders and trades
    """
    # Validate execution_environment before any DB interaction. See
    # create_position for the full rationale.
    if execution_environment not in VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION:
        msg = (
            f"Invalid execution_environment: {execution_environment!r}. "
            f"Must be one of {sorted(VALID_EXECUTION_ENVIRONMENTS_TRADE_POSITION)}. "
            f"Note: 'unknown' is reserved for account_balance only."
        )
        raise ValueError(msg)

    # Calculate edge_value if both probability and price provided
    edge_value: Decimal | None = None
    if calculated_probability is not None and market_price is not None:
        edge_value = calculated_probability - market_price

    if fees is not None:
        fees = validate_decimal(fees, "fees")

    query = """
        INSERT INTO trades (
            market_internal_id, side, quantity, price,
            order_id, is_taker, fees,
            trade_metadata, execution_time,
            calculated_probability, market_price, edge_value,
            execution_environment
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        market_internal_id,
        side,
        quantity,
        price,
        order_id,
        is_taker,
        fees,
        trade_metadata,
        calculated_probability,
        market_price,
        edge_value,
        execution_environment,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_trades_by_market(
    market_internal_id: int,
    limit: int = 100,
    execution_environment: ExecutionEnvironment | None = None,
) -> list[dict[str, Any]]:
    """
    Get all trades for a specific market.

    Args:
        market_internal_id: Integer FK to markets(id)
        limit: Maximum number of trades (default: 100)
        execution_environment: Filter by environment ('live', 'paper', 'backtest').
            If None, returns trades from all environments.

    Returns:
        List of trades, newest first

    Example:
        >>> # All trades for market
        >>> trades = get_trades_by_market(market_internal_id=42, limit=20)
        >>> # Only paper trades (demo API testing)
        >>> paper_trades = get_trades_by_market(market_internal_id=42, execution_environment='paper')
    """
    # Migration 0021: markets is dimension (no SCD, no row_current_ind filter needed).
    query = """
        SELECT t.*, m.ticker
        FROM trades t
        JOIN markets m ON t.market_internal_id = m.id
        WHERE t.market_internal_id = %s
    """
    params: list[str | int] = [market_internal_id]

    if execution_environment is not None:
        query += " AND t.execution_environment = %s"
        params.append(execution_environment)

    query += " ORDER BY t.execution_time DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


def get_recent_trades(
    strategy_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    execution_environment: ExecutionEnvironment | None = None,
) -> list[dict[str, Any]]:
    """
    Get recent trades across all markets with pagination.

    Args:
        strategy_id: Filter by strategy version (optional)
        limit: Maximum number of trades (default: 100)
        offset: Number of trades to skip for pagination (default: 0)
        execution_environment: Filter by environment ('live', 'paper', 'backtest').
            If None, returns trades from all environments.

    Returns:
        List of recent trades, newest first

    Example:
        >>> recent = get_recent_trades(limit=50)
        >>> strategy_trades = get_recent_trades(strategy_id=1, limit=50)
        >>> # Pagination: get page 2 (trades 100-199)
        >>> page2 = get_recent_trades(limit=100, offset=100)
    """
    # Migration 0025: attribution lives on orders, joined through t.order_id.
    query = """
        SELECT t.*, m.ticker,
               o.strategy_id, o.model_id,
               s.strategy_name, pm.model_name
        FROM trades t
        JOIN markets m ON t.market_internal_id = m.id
        LEFT JOIN orders o ON t.order_id = o.id
        LEFT JOIN strategies s ON o.strategy_id = s.strategy_id
        LEFT JOIN probability_models pm ON o.model_id = pm.model_id
        WHERE 1=1
    """
    params: list[int | str] = []

    if strategy_id:
        query += " AND o.strategy_id = %s"
        params.append(strategy_id)

    if execution_environment is not None:
        query += " AND t.execution_environment = %s"
        params.append(execution_environment)

    query += " ORDER BY t.execution_time DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    return fetch_all(query, tuple(params))


# =============================================================================
# Account Balance + Settlement Operations: MOVED to crud_account.py
# Re-exported above for backward compatibility.
# =============================================================================


# =============================================================================
# STRATEGY CRUD OPERATIONS (Immutable Versioning Pattern)
# =============================================================================


def get_position_by_id(position_id: int) -> dict[str, Any] | None:
    """
    Get position by internal id (current version only).

    Args:
        position_id: Position internal id

    Returns:
        Position dictionary or None if not found

    Educational Note:
        Positions use SCD Type 2 versioning. This function returns ONLY
        the current version (row_current_ind = TRUE). For position history,
        query positions table directly with row_current_ind filtering.

    Example:
        >>> position = get_position_by_id(position_id=42)
        >>> if position:
        ...     print(f"Position {position['position_id']}: {position['status']}")

    References:
        - ADR-018: Position Immutable Versioning
        - Pattern 2: Dual Versioning System (DEVELOPMENT_PATTERNS_V1.5.md)
    """
    # Migration 0022: markets is dimension (no SCD, no row_current_ind filter needed).
    query = """
        SELECT p.*, m.ticker, s.strategy_name, pm.model_name
        FROM positions p
        JOIN markets m ON p.market_internal_id = m.id
        JOIN strategies s ON p.strategy_id = s.strategy_id
        LEFT JOIN probability_models pm ON p.model_id = pm.model_id
        WHERE p.id = %s
          AND p.row_current_ind = TRUE
    """
    return fetch_one(query, (position_id,))


def get_trade_by_id(trade_id: int) -> dict[str, Any] | None:
    """
    Get trade by trade_id.

    Args:
        trade_id: Trade ID

    Returns:
        Trade dictionary or None if not found

    Educational Note:
        Trades are immutable records (no SCD Type 2 versioning).
        Each trade represents a single execution event with immutable
        attribution fields (calculated_probability, market_price, edge_value).

    Example:
        >>> trade = get_trade_by_id(trade_id=42)
        >>> if trade:
        ...     print(f"Trade {trade['side']} {trade['quantity']} @ {trade['price']}")
        ...     print(f"Attribution: edge={trade['edge_value']}, model={trade['model_id']}")

    References:
        - ADR-091: Explicit Columns vs JSONB for Trade Attribution
        - Pattern 15: Trade/Position Attribution Architecture
    """
    # Migration 0025: attribution on orders, joined through t.order_id.
    query = """
        SELECT t.*, m.ticker,
               o.strategy_id, o.model_id,
               s.strategy_name, pm.model_name
        FROM trades t
        JOIN markets m ON t.market_internal_id = m.id
        LEFT JOIN orders o ON t.order_id = o.id
        LEFT JOIN strategies s ON o.strategy_id = s.strategy_id
        LEFT JOIN probability_models pm ON o.model_id = pm.model_id
        WHERE t.id = %s
    """
    return fetch_one(query, (trade_id,))


# =============================================================================
# VENUE OPERATIONS (Phase 2 - Live Data Integration)
# =============================================================================
