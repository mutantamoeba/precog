"""
CRUD operations for account balance and settlements.

Extracted from crud_operations.py during Phase 1a domain split.
These tables have zero cross-domain dependencies within crud_operations.py.

Tables covered:
    - account_balance: SCD Type 2 versioned balance snapshots
    - settlements: Append-only settlement records for resolved markets
"""

import logging
from decimal import Decimal
from typing import cast

from .connection import get_cursor
from .crud_shared import (
    VALID_EXECUTION_ENVIRONMENTS_BALANCE,
    ExecutionEnvironment,
    retry_on_scd_unique_conflict,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Account Balance Operations (SCD Type 2)
# =============================================================================


def create_account_balance(
    platform_id: str,
    balance: Decimal,
    execution_environment: ExecutionEnvironment,
    currency: str = "USD",
) -> int | None:
    """
    Create new account balance snapshot with row_current_ind = TRUE.

    Account balance uses SCD Type 2 versioning to track balance changes over time.
    Each balance fetch creates a new snapshot, partitioned by execution_environment
    so live and paper balances coexist for the same platform_id without
    cross-contamination (Migration 0051).

    Args:
        platform_id: Foreign key to platforms table (e.g., "kalshi")
        balance: Account balance as DECIMAL(10,4) - NEVER use float!
        execution_environment: Execution context — REQUIRED, no default. Must
            be one of 'live' (production), 'paper' (demo API), 'backtest'
            (simulation), or 'unknown' (forensic tombstone). Callers MUST
            obtain this value from
            ``precog.config.environment.derive_execution_environment``
            or pass an explicit literal — never inherit a Python default.
            See findings_622_686_synthesis.md for the rationale: the
            optional-default precedent on ``crud_positions.create_position``
            was the literal cause of the #622/#662/#686 bug class.
        currency: Currency code (default: "USD")

    Returns:
        id of newly created record

    Raises:
        ValueError: If balance is float (not Decimal), or if
            ``execution_environment`` is not one of the four allowed values.
        psycopg2.Error: If database operation fails.

    Educational Note:
        Account balance stored as DECIMAL(10,4) for exact precision.
        NEVER use float for financial calculations!

        Why execution_environment is REQUIRED with no default:
        - Cost of miss with REQUIRED: caller breaks with TypeError. LOUD.
        - Cost of miss with optional default: silent contamination on a
          money table. Indistinguishable from correct behavior.
        See ``findings_622_686_synthesis.md`` for the full rationale.

        SCD Type 2 Pattern:
        - Every balance fetch creates NEW row with row_current_ind=TRUE
        - Enables balance history tracking without losing data
        - Query current balance: WHERE row_current_ind = TRUE
          AND execution_environment = %s

    Example:
        >>> from decimal import Decimal
        >>> from precog.config.environment import (
        ...     derive_execution_environment,
        ...     get_app_environment,
        ...     get_market_mode,
        ... )
        >>> exec_env = derive_execution_environment(
        ...     get_app_environment(), get_market_mode("kalshi")
        ... )
        >>> balance_id = create_account_balance(
        ...     platform_id="kalshi",
        ...     balance=Decimal("1234.5678"),
        ...     execution_environment=exec_env,
        ...     currency="USD",
        ... )

        >>> # WRONG - Float contamination
        >>> balance = 1234.5678  # float type
        >>> # Will raise ValueError on the Decimal guard

        >>> # WRONG - missing execution_environment
        >>> create_account_balance("kalshi", Decimal("1000.00"))
        >>> # TypeError: missing 1 required positional argument

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - REQ-SAFE-005 (proposed): Mandatory translator function for
          execution environment derivation
        - ADR-002: Decimal-Only Financial Calculations
        - ADR-107: Single-Database Architecture with Execution Environments
        - Pattern 1 in CLAUDE.md: Decimal Precision
        - Pattern 2 in CLAUDE.md: SCD Type 2 Versioning
        - Issues #622, #662, #686 (the bug class this signature prevents)
    """
    if not isinstance(balance, Decimal):
        raise ValueError(f"Balance must be Decimal, got {type(balance).__name__}")
    if execution_environment not in VALID_EXECUTION_ENVIRONMENTS_BALANCE:
        msg = (
            f"Invalid execution_environment: {execution_environment!r}. "
            f"Must be one of {sorted(VALID_EXECUTION_ENVIRONMENTS_BALANCE)}. "
            f"This is the typo defense Marvin recommended on #662 -- "
            f"'Live', 'demo', and other near-misses must fail loudly here."
        )
        raise ValueError(msg)

    query = """
        INSERT INTO account_balance (
            platform_id, balance, currency, execution_environment,
            row_current_ind, row_start_ts, created_at
        )
        VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
        RETURNING id
    """

    params = (platform_id, balance, currency, execution_environment)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result["id"] if result else None


def update_account_balance_with_versioning(
    platform_id: str,
    new_balance: Decimal,
    execution_environment: ExecutionEnvironment,
    currency: str = "USD",
) -> int | None:
    """
    Update account balance using SCD Type 2 versioning (insert new row, mark old as historical).

    This implements Slowly Changing Dimension Type 2 pattern:
    1. Find current balance record (row_current_ind = TRUE)
    2. Set row_current_ind = FALSE on old record
    3. Insert new record with row_current_ind = TRUE

    Args:
        platform_id: Platform identifier (e.g., "kalshi")
        new_balance: New balance as DECIMAL(10,4)
        execution_environment: Execution context — REQUIRED, no default. Must
            be one of 'live', 'paper', 'backtest', or 'unknown'. The
            close+insert SCD sequence operates on the row scoped to BOTH
            platform_id AND execution_environment, so passing a value that
            does not match the existing current row will create a parallel
            current row in a different environment (which is the correct
            behavior — live and paper balances coexist for the same
            platform_id post-Migration 0051). Callers MUST derive this value
            from ``derive_execution_environment(app_env, market_mode)`` at
            the application boundary, never inherit a Python default.
        currency: Currency code (default: "USD")

    Returns:
        id of newly created record

    Raises:
        ValueError: If ``new_balance`` is not a ``Decimal``.
        psycopg2.errors.UniqueViolation: If the partial unique index
            conflict on ``idx_balance_unique_current`` persists after one
            retry. This indicates a sustained concurrent first-insert
            race that the SCD race-prevention helper could not resolve.
            The first attempt's exception is chained via ``__cause__``
            for postmortem analysis. See issue #613 and
            ``crud_shared.retry_on_scd_unique_conflict`` for the full
            chaining contract.
        psycopg2.Error: Any other database error (CHECK violation on a
            negative balance, FK violation on an unknown ``platform_id``,
            ``OperationalError`` on connection failure, etc.) propagates
            without retry. The retry helper only discriminates on the
            targeted ``idx_balance_unique_current`` UniqueViolation --
            all sibling IntegrityError sources bypass the retry path
            and surface immediately to the caller.

    Educational Note:
        SCD Type 2 Versioning Pattern:
        - Preserves full history of balance changes
        - Old balances remain in database (row_current_ind=FALSE)
        - Current balance always WHERE row_current_ind=TRUE
        - Enables time-series analysis of account growth

        Why not UPDATE balance column?
        - Loses historical data (can't track balance over time)
        - Can't analyze when balance changed
        - Can't correlate balance with trades/positions

        With SCD Type 2:
        - Query: "What was my balance on 2024-01-15?" -> Filter by created_at
        - Query: "How has balance changed this month?" -> Aggregate by day
        - Query: "Current balance?" -> WHERE row_current_ind=TRUE

    Example:
        >>> # First balance fetch
        >>> balance_id_1 = create_account_balance("kalshi", Decimal("1000.0000"))
        >>> # balance_id_1 has row_current_ind=TRUE

        >>> # Second balance fetch (after trading)
        >>> balance_id_2 = update_account_balance_with_versioning(
        ...     "kalshi", Decimal("1050.0000")
        ... )
        >>> # balance_id_1 now has row_current_ind=FALSE (historical)
        >>> # balance_id_2 now has row_current_ind=TRUE (current)

        >>> # Query current balance
        >>> query = "SELECT balance FROM account_balance WHERE platform_id = %s AND row_current_ind = TRUE"
        >>> # Returns 1050.0000

        >>> # Query balance history
        >>> query = "SELECT balance, created_at FROM account_balance WHERE platform_id = %s ORDER BY created_at"
        >>> # Returns [(1000.0000, '2024-01-15 10:00'), (1050.0000, '2024-01-15 14:30')]

    Related:
        - Pattern 2 in CLAUDE.md: Dual Versioning System (SCD Type 2)
        - docs/guides/VERSIONING_GUIDE_V1.0.md
        - REQ-DB-004: SCD Type 2 for Frequently-Changing Data
    """
    if not isinstance(new_balance, Decimal):
        raise ValueError(f"Balance must be Decimal, got {type(new_balance).__name__}")
    if execution_environment not in VALID_EXECUTION_ENVIRONMENTS_BALANCE:
        msg = (
            f"Invalid execution_environment: {execution_environment!r}. "
            f"Must be one of {sorted(VALID_EXECUTION_ENVIRONMENTS_BALANCE)}. "
            f"Typo defense (Marvin's recommendation on #662): this guard "
            f"fires before any DB interaction, so 'Live', 'demo', and other "
            f"near-misses cannot reach the SCD versioning path."
        )
        raise ValueError(msg)

    # Step 0: Lock current row to prevent concurrent close->insert races.
    # Without FOR UPDATE, two concurrent calls can both close the current row
    # before either inserts, leaving zero current rows for the (platform_id,
    # execution_environment) tuple.
    #
    # The lock is scoped to (platform_id, execution_environment) because
    # post-Migration 0051 the partial unique index is composite. Without the
    # execution_environment predicate, a live update would unnecessarily
    # serialize against a concurrent paper update for the same platform.
    lock_query = """
        SELECT id FROM account_balance
        WHERE platform_id = %s
          AND execution_environment = %s
          AND row_current_ind = TRUE
        FOR UPDATE
    """

    # Step 1: Close current row -- use a single NOW() for temporal continuity
    # between the old row's end and new row's start. Scoped to the same
    # (platform_id, execution_environment) tuple as the lock.
    close_query = """
        UPDATE account_balance
        SET row_current_ind = FALSE,
            row_end_ts = %s
        WHERE platform_id = %s
          AND execution_environment = %s
          AND row_current_ind = TRUE
    """

    # Step 2: Insert new balance record with matching row_start_ts
    insert_query = """
        INSERT INTO account_balance (
            platform_id, balance, currency, execution_environment,
            row_current_ind, row_start_ts, created_at
        )
        VALUES (%s, %s, %s, %s, TRUE, %s, %s)
        RETURNING id
    """

    def _attempt_close_and_insert() -> int | None:
        """One attempt at the SCD close+insert sequence.

        Opens its own ``get_cursor(commit=True)`` block so the retry helper
        can run this closure twice and get a fresh transaction (with a fresh
        MVCC snapshot) on the second invocation. NOW() is captured INSIDE
        each attempt so the close and insert use a single timestamp per
        attempt -- never carrying a timestamp across the retry boundary,
        which would create backward temporal intervals.
        """
        with get_cursor(commit=True) as cur:
            # Capture timestamp once for temporal continuity within THIS attempt.
            cur.execute("SELECT NOW() AS ts")
            now = cur.fetchone()["ts"]

            # Lock current row (serializes concurrent updates against the
            # same platform+env tuple). On the first attempt of a first-insert
            # race, this returns zero rows; on the retry attempt the sibling
            # caller's row is now visible and gets locked, so close+insert
            # proceeds normally. Post-Migration 0051 the lock is scoped to
            # (platform_id, execution_environment) so cross-environment writes
            # do not unnecessarily serialize.
            cur.execute(lock_query, (platform_id, execution_environment))

            # Close old balance version (no-op if no current row exists for
            # this platform+env tuple).
            cur.execute(close_query, (now, platform_id, execution_environment))

            # Insert new balance version. If a sibling caller raced us between
            # the lock query and this insert (only possible on the FIRST insert
            # for this (platform_id, execution_environment) tuple, when the
            # lock query found zero rows to serialize against), this raises
            # psycopg2.errors.UniqueViolation on idx_balance_unique_current.
            # The retry helper catches that specific constraint and re-runs
            # this attempt.
            cur.execute(
                insert_query,
                (platform_id, new_balance, currency, execution_environment, now, now),
            )
            result = cur.fetchone()
            # PR #631 / Claude Review Issue 1: refuse to silently return None
            # for money-touching SCD code. The retry helper is generic over
            # T (including None for callers that legitimately expect it), so
            # the "None is bad" semantics must be enforced at THIS consumer.
            # If INSERT...RETURNING id yields no row, a DB trigger or
            # constraint suppressed the return -- callers must see this loudly
            # rather than receive None and propagate it as a "successful"
            # balance id.
            if result is None or result.get("id") is None:
                raise RuntimeError(
                    "INSERT INTO account_balance RETURNING id produced no row -- "
                    "this should be impossible after a successful INSERT and "
                    "indicates a DB trigger or constraint suppressed the return. "
                    "Refusing to silently return None for money-touching SCD code."
                )
            # cast() satisfies mypy: RealDictCursor.fetchone() is typed Any in
            # the psycopg2 stubs, so without the cast mypy reports
            # ``Returning Any from function declared to return "int | None"``.
            return cast("int", result["id"])

    # Wrap the attempt in the SCD race-prevention retry helper. The helper
    # discriminates on constraint_name=idx_balance_unique_current so CHECK
    # violations, FK violations, and other unrelated IntegrityError sources
    # re-raise immediately without a misleading retry. See issue #613 and
    # crud_shared.retry_on_scd_unique_conflict for the full design rationale.
    return retry_on_scd_unique_conflict(
        _attempt_close_and_insert,
        "idx_balance_unique_current",
        business_key={
            "platform_id": platform_id,
            "execution_environment": execution_environment,
        },
        logger_override=logger,
    )


# =============================================================================
# Settlement Operations (Append-Only)
# =============================================================================


def create_settlement(
    market_id: int,
    platform_id: str,
    outcome: str,
    payout: Decimal,
) -> int | None:
    """
    Create settlement record for a resolved market.

    Settlements are append-only (no versioning) because they are final.
    Once a market settles, the outcome and payout never change.

    Args:
        market_id: Integer foreign key to markets(id)
        platform_id: Foreign key to platforms table
        outcome: Settlement outcome ("yes", "no", or other)
        payout: Payout amount as DECIMAL(10,4)

    Returns:
        id of newly created record

    Raises:
        ValueError: If payout is float (not Decimal)
        psycopg2.Error: If database operation fails

    Educational Note:
        Settlements are FINAL - no versioning needed:
        - Market settles once (outcome determined)
        - Payout calculated once (never changes)
        - row_current_ind NOT NEEDED (settlements don't update)

        Why Decimal for payouts?
        - Market resolution: YES position pays $1.00 per contract
        - Fractional payouts possible (e.g., $0.5000 for 50/50 split)
        - Must be exact (no float rounding errors)

    Example:
        >>> # Market resolved YES, position pays $1 per contract
        >>> settlement_id = create_settlement(
        ...     market_id=42,
        ...     platform_id="kalshi",
        ...     outcome="yes",
        ...     payout=Decimal("1.0000")  # $1.00 per contract
        ... )

        >>> # Market resolved NO, YES position pays $0
        >>> settlement_id = create_settlement(
        ...     market_id=43,
        ...     platform_id="kalshi",
        ...     outcome="no",
        ...     payout=Decimal("0.0000")  # Worthless
        ... )

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - Pattern 1 in CLAUDE.md: Decimal Precision
        - Settlements table schema: database/DATABASE_SCHEMA_SUMMARY.md
    """
    if not isinstance(payout, Decimal):
        raise ValueError(f"Payout must be Decimal, got {type(payout).__name__}")

    query = """
        INSERT INTO settlements (
            market_id, platform_id, outcome, payout, created_at
        )
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id
    """

    params = (market_id, platform_id, outcome, payout)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result["id"] if result else None
