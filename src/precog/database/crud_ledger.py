"""
CRUD operations for ledger, temporal alignment, and market trades.

Extracted from crud_operations.py during Phase 1a domain split.
These are append-only tables with zero cross-domain dependencies.

Tables covered:
    - account_ledger (Migration 0026): Transaction-level balance tracking
    - temporal_alignment (Migration 0027): Market snapshot <-> game state linking
    - market_trades (Migration 0028): Public Kalshi trade tape
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import cast

from psycopg2.extras import execute_values

from .connection import fetch_all, fetch_one, get_cursor
from .crud_shared import validate_decimal

logger = logging.getLogger(__name__)


# =============================================================================
# ACCOUNT LEDGER OPERATIONS (Append-Only)
# =============================================================================
#
# Migration 0026: account_ledger table for transaction-level balance tracking.
#   - Append-only: rows are never updated or deleted.
#   - Links balance changes to their causes (deposits, withdrawals, P&L, fees).
#   - amount CAN be negative (withdrawals, fees deducted).
#   - running_balance cannot go below zero (CHECK constraint in DDL).
#   - Polymorphic reference: reference_type + reference_id point to the source
#     entity (order, settlement, trade, manual, system).
#   - Direct order FK for trade-related entries.
# =============================================================================

_VALID_TRANSACTION_TYPES = frozenset(
    {
        "deposit",
        "withdrawal",
        "trade_pnl",
        "fee",
        "rebate",
        "adjustment",
    }
)

_VALID_REFERENCE_TYPES = frozenset(
    {
        "order",
        "settlement",
        "trade",
        "manual",
        "system",
    }
)


def create_ledger_entry(
    platform_id: str,
    transaction_type: str,
    amount: Decimal,
    running_balance: Decimal,
    currency: str = "USD",
    reference_type: str | None = None,
    reference_id: int | None = None,
    order_id: int | None = None,
    description: str | None = None,
) -> int:
    """
    Create an append-only ledger entry recording a balance change.

    The account_ledger explains WHY the balance changed, complementing the
    account_balance SCD Type 2 snapshots that record WHAT the balance is.

    Args:
        platform_id: FK to platforms(platform_id), e.g. 'kalshi'
        transaction_type: One of 'deposit', 'withdrawal', 'trade_pnl',
            'fee', 'rebate', 'adjustment'
        amount: Change amount as DECIMAL(10,4). Can be negative
            (withdrawals, fees).
        running_balance: Balance after this transaction as DECIMAL(10,4).
            Must be >= 0.
        currency: ISO currency code (default 'USD')
        reference_type: Optional polymorphic source type -- one of
            'order', 'settlement', 'trade', 'manual', 'system'
        reference_id: Optional FK to the referenced entity (not enforced)
        order_id: Optional FK to orders(id) for trade-related entries
        description: Optional human-readable description

    Returns:
        Integer surrogate PK (account_ledger.id) of the newly created entry.

    Raises:
        TypeError: If amount or running_balance is not Decimal
        ValueError: If transaction_type or reference_type is invalid

    Educational Note:
        Append-Only vs SCD Type 2:
            account_balance uses SCD Type 2 (versioned snapshots of WHAT
            the balance is). account_ledger is append-only (immutable log
            of WHY it changed). Together they form a complete audit trail:
            - Ledger: "Deposit of $500 at 10:00 AM"
            - Balance snapshot: "Balance is now $1500 at 10:00 AM"

        Why running_balance on every row?
            Avoids expensive SUM(amount) aggregations. The latest row's
            running_balance IS the current balance. O(1) lookup instead
            of O(n) aggregation.

    Example:
        >>> entry_id = create_ledger_entry(
        ...     platform_id='kalshi',
        ...     transaction_type='deposit',
        ...     amount=Decimal("500.0000"),
        ...     running_balance=Decimal("1500.0000"),
        ...     description="Initial deposit via ACH",
        ... )
        >>> # Returns surrogate id (e.g., 1)

        >>> # Fee deduction (negative amount)
        >>> entry_id = create_ledger_entry(
        ...     platform_id='kalshi',
        ...     transaction_type='fee',
        ...     amount=Decimal("-0.0200"),
        ...     running_balance=Decimal("1499.9800"),
        ...     reference_type='order',
        ...     reference_id=42,
        ...     order_id=42,
        ... )

    References:
        - Migration 0026: account_ledger
        - migration_batch_plan_v1.md: Migration 0026 spec
    """
    # Runtime type validation (enforces Decimal precision)
    amount = validate_decimal(amount, "amount")
    running_balance = validate_decimal(running_balance, "running_balance")

    # Domain constraint validation (mirrors DB CHECK constraint)
    if running_balance < Decimal("0"):
        raise ValueError(f"running_balance must be >= 0, got {running_balance}")

    # Runtime enum-like validation
    if transaction_type not in _VALID_TRANSACTION_TYPES:
        raise ValueError(
            f"transaction_type must be one of {_VALID_TRANSACTION_TYPES}, got '{transaction_type}'"
        )
    if reference_type is not None and reference_type not in _VALID_REFERENCE_TYPES:
        raise ValueError(
            f"reference_type must be one of {_VALID_REFERENCE_TYPES}, got '{reference_type}'"
        )

    insert_query = """
        INSERT INTO account_ledger (
            platform_id, transaction_type,
            amount, running_balance, currency,
            reference_type, reference_id,
            order_id, description
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        platform_id,
        transaction_type,
        amount,
        running_balance,
        currency,
        reference_type,
        reference_id,
        order_id,
        description,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_ledger_entries(
    platform_id: str,
    transaction_type: str | None = None,
    limit: int = 100,
    since: datetime | None = None,
) -> list[dict]:
    """
    Retrieve ledger entries for a platform, ordered by created_at DESC.

    Args:
        platform_id: FK to platforms(platform_id)
        transaction_type: Optional filter -- one of _VALID_TRANSACTION_TYPES
        limit: Maximum rows to return (default 100)
        since: Optional datetime filter -- only entries created after this time

    Returns:
        List of dictionaries, one per ledger entry, ordered by created_at DESC.

    Example:
        >>> entries = get_ledger_entries('kalshi', transaction_type='fee', limit=50)
        >>> for e in entries:
        ...     print(e['transaction_type'], e['amount'], e['running_balance'])

        >>> # Get entries from the last hour
        >>> from datetime import datetime, timedelta, timezone
        >>> cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        >>> recent = get_ledger_entries('kalshi', since=cutoff)

    References:
        - Migration 0026: account_ledger
    """
    query = "SELECT * FROM account_ledger WHERE platform_id = %s"
    params: list = [platform_id]

    if transaction_type is not None:
        if transaction_type not in _VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"transaction_type must be one of {_VALID_TRANSACTION_TYPES}, "
                f"got '{transaction_type}'"
            )
        query += " AND transaction_type = %s"
        params.append(transaction_type)

    if since is not None:
        query += " AND created_at >= %s"
        params.append(since)

    query += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


def get_running_balance(platform_id: str) -> Decimal | None:
    """
    Return the running_balance from the most recent ledger entry.

    This is an O(1) lookup -- no aggregation needed because every ledger
    entry stores the running balance at that point in time.

    Args:
        platform_id: FK to platforms(platform_id)

    Returns:
        Decimal running_balance from the latest entry, or None if no entries exist.

    Example:
        >>> balance = get_running_balance('kalshi')
        >>> if balance is not None:
        ...     print(f"Current balance: ${balance}")
        ... else:
        ...     print("No ledger entries yet")

    References:
        - Migration 0026: account_ledger
    """
    query = """
        SELECT running_balance FROM account_ledger
        WHERE platform_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """

    result = fetch_one(query, (platform_id,))
    if result is None:
        return None
    return cast("Decimal", result["running_balance"])


# =============================================================================
# TEMPORAL ALIGNMENT CRUD
# =============================================================================
#
# Migration 0027: temporal_alignment
# Links market snapshots to game state snapshots by timestamp proximity.
# Enables cross-source queries like "what was the market price when the score
# changed?" Critical for Phase 4 backtesting accuracy.
#
# Design:
#   - Append-only: rows are never updated once created.
#   - Denormalizes key snapshot/game-state fields for query convenience.
#   - alignment_quality categorizes the time delta between the two sources.
# =============================================================================

_VALID_ALIGNMENT_QUALITIES = frozenset({"exact", "good", "fair", "poor", "stale"})

# Quality ordering for filtering (higher index = better)
_ALIGNMENT_QUALITY_ORDER = ["stale", "poor", "fair", "good", "exact"]


def insert_temporal_alignment(
    market_id: int,
    market_snapshot_id: int,
    game_state_id: int,
    snapshot_time: datetime,
    game_state_time: datetime,
    time_delta_seconds: Decimal,
    alignment_quality: str = "good",
    yes_ask_price: Decimal | None = None,
    no_ask_price: Decimal | None = None,
    spread: Decimal | None = None,
    volume: int | None = None,
    game_status: str | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    period: str | None = None,
    clock: str | None = None,
    game_id: int | None = None,
) -> int:
    """
    Insert a temporal alignment linking a market snapshot to a game state.

    The temporal_alignment table bridges Kalshi price polls (every 15s) and
    ESPN game-state polls (every 30s) by matching them on timestamp proximity.
    Each row records a SPECIFIC market_snapshot <-> game_state pairing with
    the time delta and denormalized values for query convenience.

    Args:
        market_id: FK to markets(id)
        market_snapshot_id: FK to market_snapshots(id) -- the specific snapshot row
        game_state_id: FK to game_states(id) -- the specific game state row
        snapshot_time: Timestamp of the market snapshot
        game_state_time: Timestamp of the game state
        time_delta_seconds: Absolute time difference as DECIMAL(10,2)
        alignment_quality: One of 'exact', 'good', 'fair', 'poor', 'stale'
            (default 'good')
        yes_ask_price: Denormalized YES ask price as DECIMAL(10,4)
        no_ask_price: Denormalized NO ask price as DECIMAL(10,4)
        spread: Denormalized bid-ask spread as DECIMAL(10,4)
        volume: Denormalized trade volume
        game_status: Denormalized game status string
        home_score: Denormalized home team score
        away_score: Denormalized away team score
        period: Denormalized game period (e.g., '1st', '2nd', 'OT')
        clock: Denormalized game clock (e.g., '12:00', '05:32')
        game_id: Optional FK to games(id). Denormalized from events.game_id
            for direct game-level queries without joining through events.

    Returns:
        Integer surrogate PK (temporal_alignment.id) of the newly created row.

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If alignment_quality is not a valid value

    Example:
        >>> alignment_id = insert_temporal_alignment(
        ...     market_id=42,
        ...     market_snapshot_id=1001,
        ...     game_state_id=501,
        ...     snapshot_time=datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
        ...     game_state_time=datetime(2026, 1, 15, 20, 30, 5, tzinfo=UTC),
        ...     time_delta_seconds=Decimal("5.00"),
        ...     alignment_quality='good',
        ...     yes_ask_price=Decimal("0.5500"),
        ...     no_ask_price=Decimal("0.4500"),
        ...     game_id=15,
        ... )

    References:
        - Migration 0027: temporal_alignment
        - Migration 0035: game_id FK added to temporal_alignment
        - Migration 0038: events.game_id FK (structural source for this value)
        - Issue #375: Temporal alignment table
        - Issue #462: Structural market-to-game linking
    """
    # Runtime type validation (enforces Decimal precision)
    time_delta_seconds = validate_decimal(time_delta_seconds, "time_delta_seconds")
    if yes_ask_price is not None:
        yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    if no_ask_price is not None:
        no_ask_price = validate_decimal(no_ask_price, "no_ask_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")

    # Runtime enum-like validation
    if alignment_quality not in _VALID_ALIGNMENT_QUALITIES:
        raise ValueError(
            f"alignment_quality must be one of {_VALID_ALIGNMENT_QUALITIES}, "
            f"got '{alignment_quality}'"
        )

    insert_query = """
        INSERT INTO temporal_alignment (
            market_id, market_snapshot_id, game_state_id,
            snapshot_time, game_state_time, time_delta_seconds,
            alignment_quality,
            yes_ask_price, no_ask_price, spread, volume,
            game_status, home_score, away_score, period, clock,
            game_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        market_id,
        market_snapshot_id,
        game_state_id,
        snapshot_time,
        game_state_time,
        time_delta_seconds,
        alignment_quality,
        yes_ask_price,
        no_ask_price,
        spread,
        volume,
        game_status,
        home_score,
        away_score,
        period,
        clock,
        game_id,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def insert_temporal_alignment_batch(alignments: list[dict]) -> int:
    """
    Bulk insert temporal alignment rows.

    Accepts a list of dictionaries, each with the same keys as
    insert_temporal_alignment parameters. Uses executemany for efficiency.

    Args:
        alignments: List of dicts, each containing:
            - market_id (int, required)
            - market_snapshot_id (int, required)
            - game_state_id (int, required)
            - snapshot_time (datetime, required)
            - game_state_time (datetime, required)
            - time_delta_seconds (Decimal, required)
            - alignment_quality (str, default 'good')
            - yes_ask_price (Decimal | None)
            - no_ask_price (Decimal | None)
            - spread (Decimal | None)
            - volume (int | None)
            - game_status (str | None)
            - home_score (int | None)
            - away_score (int | None)
            - period (str | None)
            - clock (str | None)
            - game_id (int | None) -- FK to games(id), denormalized from events

    Returns:
        Count of rows inserted (duplicates are silently skipped via
        ON CONFLICT DO NOTHING on the unique constraint
        uq_alignment_snapshot_game).

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If alignment_quality is not a valid value

    Example:
        >>> rows = [
        ...     {
        ...         "market_id": 42,
        ...         "market_snapshot_id": 1001,
        ...         "game_state_id": 501,
        ...         "snapshot_time": datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
        ...         "game_state_time": datetime(2026, 1, 15, 20, 30, 5, tzinfo=UTC),
        ...         "time_delta_seconds": Decimal("5.00"),
        ...     },
        ...     {
        ...         "market_id": 42,
        ...         "market_snapshot_id": 1002,
        ...         "game_state_id": 502,
        ...         "snapshot_time": datetime(2026, 1, 15, 20, 30, 15, tzinfo=UTC),
        ...         "game_state_time": datetime(2026, 1, 15, 20, 30, 10, tzinfo=UTC),
        ...         "time_delta_seconds": Decimal("5.00"),
        ...     },
        ... ]
        >>> count = insert_temporal_alignment_batch(rows)
        >>> # count == 2

    References:
        - Migration 0027: temporal_alignment
        - Migration 0035: game_id FK added to temporal_alignment
        - migration_batch_plan_v1.md: Migration 0027 spec
    """
    if not alignments:
        return 0

    # Validate all rows before inserting any
    validated_params = []
    for i, row in enumerate(alignments):
        time_delta = validate_decimal(
            row["time_delta_seconds"], f"alignments[{i}].time_delta_seconds"
        )

        yes_price = row.get("yes_ask_price")
        if yes_price is not None:
            yes_price = validate_decimal(yes_price, f"alignments[{i}].yes_ask_price")

        no_price = row.get("no_ask_price")
        if no_price is not None:
            no_price = validate_decimal(no_price, f"alignments[{i}].no_ask_price")

        sprd = row.get("spread")
        if sprd is not None:
            sprd = validate_decimal(sprd, f"alignments[{i}].spread")

        quality = row.get("alignment_quality", "good")
        if quality not in _VALID_ALIGNMENT_QUALITIES:
            raise ValueError(
                f"alignment_quality must be one of {_VALID_ALIGNMENT_QUALITIES}, "
                f"got '{quality}' in alignments[{i}]"
            )

        validated_params.append(
            (
                row["market_id"],
                row["market_snapshot_id"],
                row["game_state_id"],
                row["snapshot_time"],
                row["game_state_time"],
                time_delta,
                quality,
                yes_price,
                no_price,
                sprd,
                row.get("volume"),
                row.get("game_status"),
                row.get("home_score"),
                row.get("away_score"),
                row.get("period"),
                row.get("clock"),
                row.get("game_id"),
            )
        )

    insert_query = """
        INSERT INTO temporal_alignment (
            market_id, market_snapshot_id, game_state_id,
            snapshot_time, game_state_time, time_delta_seconds,
            alignment_quality,
            yes_ask_price, no_ask_price, spread, volume,
            game_status, home_score, away_score, period, clock,
            game_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (market_snapshot_id, game_state_id) DO NOTHING
    """

    with get_cursor(commit=True) as cur:
        cur.executemany(insert_query, validated_params)
        return len(validated_params)


def get_alignments_by_market(
    market_id: int,
    limit: int = 100,
    min_quality: str | None = None,
) -> list[dict]:
    """
    Retrieve temporal alignments for a market, ordered by snapshot_time DESC.

    Args:
        market_id: FK to markets(id)
        limit: Maximum rows to return (default 100)
        min_quality: Optional minimum quality filter. Returns entries at this
            quality level or better. Quality ordering (worst to best):
            stale < poor < fair < good < exact

    Returns:
        List of dictionaries, one per alignment row, ordered by
        snapshot_time DESC, id DESC.

    Raises:
        ValueError: If min_quality is not a valid alignment quality value

    Example:
        >>> # Get all alignments for market 42
        >>> alignments = get_alignments_by_market(42)

        >>> # Get only good or better alignments
        >>> good_alignments = get_alignments_by_market(42, min_quality='good')

        >>> # Get latest 10 alignments
        >>> recent = get_alignments_by_market(42, limit=10)

    References:
        - Migration 0027: temporal_alignment
        - migration_batch_plan_v1.md: Migration 0027 spec
    """
    query = "SELECT * FROM temporal_alignment WHERE market_id = %s"
    params: list = [market_id]

    if min_quality is not None:
        if min_quality not in _VALID_ALIGNMENT_QUALITIES:
            raise ValueError(
                f"min_quality must be one of {_VALID_ALIGNMENT_QUALITIES}, got '{min_quality}'"
            )
        # Filter to entries at min_quality or better
        quality_index = _ALIGNMENT_QUALITY_ORDER.index(min_quality)
        acceptable = _ALIGNMENT_QUALITY_ORDER[quality_index:]
        placeholders = ", ".join(["%s"] * len(acceptable))
        query += f" AND alignment_quality IN ({placeholders})"
        params.extend(acceptable)

    query += " ORDER BY snapshot_time DESC, id DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


# =============================================================================
# MARKET TRADES CRUD
# =============================================================================
#
# Migration 0028: market_trades
# Stores Kalshi's public trade tape (all fills on a market, not just ours).
# Reveals volume patterns, price discovery, and liquidity -- critical ML signals.
#
# Design:
#   - Append-only: rows are never updated once created.
#   - Dedup via UNIQUE(platform_id, external_trade_id) + ON CONFLICT DO NOTHING.
#   - yes_price/no_price are executed trade prices (not order book quotes).
#   - taker_side reveals aggressor direction.
# =============================================================================

_VALID_TAKER_SIDES = frozenset({"yes", "no"})


def upsert_market_trade(
    platform_id: str,
    external_trade_id: str,
    market_internal_id: int,
    count: int,
    trade_time: datetime,
    yes_price: Decimal | None = None,
    no_price: Decimal | None = None,
    taker_side: str | None = None,
) -> int | None:
    """
    Insert a public market trade, skipping if it already exists (idempotent).

    Uses INSERT ... ON CONFLICT (platform_id, external_trade_id) DO NOTHING
    to safely handle duplicate ingestion from the Kalshi trade tape API.

    Args:
        platform_id: FK to platforms(platform_id), e.g. 'kalshi'
        external_trade_id: Kalshi's trade UUID (unique per platform)
        market_internal_id: FK to markets(id) -- integer surrogate PK
        count: Number of contracts in this trade (must be > 0)
        trade_time: When the trade was executed on the exchange
        yes_price: Executed yes-side price as DECIMAL(10,4), or None
        no_price: Executed no-side price as DECIMAL(10,4), or None
        taker_side: Aggressor side -- 'yes' or 'no', or None if unknown

    Returns:
        Integer surrogate PK (market_trades.id) if inserted,
        None if the trade already existed (conflict).

    Raises:
        TypeError: If yes_price or no_price is not Decimal (when not None)
        ValueError: If taker_side is not in {'yes', 'no'} (when not None)

    Example:
        >>> trade_id = upsert_market_trade(
        ...     platform_id='kalshi',
        ...     external_trade_id='abc-123-def',
        ...     market_internal_id=42,
        ...     count=10,
        ...     trade_time=datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
        ...     yes_price=Decimal("0.5500"),
        ...     taker_side='yes',
        ... )
        >>> # Returns id (e.g., 1) or None if duplicate

    References:
        - Migration 0028: market_trades
        - Issue #402: Add market_trades table for public trade tape
    """
    # Runtime type validation for Decimal fields
    if yes_price is not None:
        yes_price = validate_decimal(yes_price, "yes_price")
    if no_price is not None:
        no_price = validate_decimal(no_price, "no_price")

    # Runtime enum validation for taker_side
    if taker_side is not None and taker_side not in _VALID_TAKER_SIDES:
        raise ValueError(f"taker_side must be one of {_VALID_TAKER_SIDES}, got '{taker_side}'")

    insert_query = """
        INSERT INTO market_trades (
            platform_id, external_trade_id, market_internal_id,
            count, yes_price, no_price, taker_side,
            trade_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (platform_id, external_trade_id) DO NOTHING
        RETURNING id
    """

    params = (
        platform_id,
        external_trade_id,
        market_internal_id,
        count,
        yes_price,
        no_price,
        taker_side,
        trade_time,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        if result is None:
            return None
        return cast("int", result["id"])


def upsert_market_trades_batch(trades: list[dict]) -> int:
    """
    Bulk insert public market trades, skipping duplicates (idempotent).

    Validates all rows before inserting any. Uses execute_values with
    ON CONFLICT DO NOTHING for safe bulk ingestion and accurate rowcount.

    Args:
        trades: List of dicts, each with keys:
            - platform_id (str): FK to platforms(platform_id)
            - external_trade_id (str): Kalshi's trade UUID
            - market_internal_id (int): FK to markets(id)
            - count (int): Number of contracts (must be > 0)
            - trade_time (datetime): When trade was executed
            - yes_price (Decimal | None): Optional executed yes price
            - no_price (Decimal | None): Optional executed no price
            - taker_side (str | None): Optional 'yes' or 'no'

    Returns:
        Count of rows actually inserted (not skipped by ON CONFLICT).

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If taker_side is not a valid value

    Example:
        >>> trades = [
        ...     {
        ...         "platform_id": "kalshi",
        ...         "external_trade_id": "abc-123",
        ...         "market_internal_id": 42,
        ...         "count": 10,
        ...         "trade_time": datetime(2026, 1, 15, 20, 30, 0, tzinfo=UTC),
        ...         "yes_price": Decimal("0.5500"),
        ...         "taker_side": "yes",
        ...     },
        ... ]
        >>> inserted = upsert_market_trades_batch(trades)
        >>> # inserted == 1 (or 0 if all were duplicates)

    References:
        - Migration 0028: market_trades
        - Issue #402: Add market_trades table for public trade tape
    """
    if not trades:
        return 0

    # Validate all rows before inserting any
    validated_params = []
    for i, row in enumerate(trades):
        yes_price = row.get("yes_price")
        if yes_price is not None:
            yes_price = validate_decimal(yes_price, f"trades[{i}].yes_price")

        no_price = row.get("no_price")
        if no_price is not None:
            no_price = validate_decimal(no_price, f"trades[{i}].no_price")

        taker_side = row.get("taker_side")
        if taker_side is not None and taker_side not in _VALID_TAKER_SIDES:
            raise ValueError(
                f"taker_side must be one of {_VALID_TAKER_SIDES}, got '{taker_side}' in trades[{i}]"
            )

        count = row["count"]
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"count must be a positive integer, got {count!r} in trades[{i}]")

        validated_params.append(
            (
                row["platform_id"],
                row["external_trade_id"],
                row["market_internal_id"],
                count,
                yes_price,
                no_price,
                taker_side,
                row["trade_time"],
            )
        )

    insert_query = """
        INSERT INTO market_trades (
            platform_id, external_trade_id, market_internal_id,
            count, yes_price, no_price, taker_side,
            trade_time
        )
        VALUES %s
        ON CONFLICT (platform_id, external_trade_id) DO NOTHING
    """

    template = "(%s, %s, %s, %s, %s, %s, %s, %s)"

    with get_cursor(commit=True) as cur:
        execute_values(cur, insert_query, validated_params, template=template)
        return cast("int", cur.rowcount)


def get_market_trades(
    market_internal_id: int,
    limit: int = 100,
    since: datetime | None = None,
) -> list[dict]:
    """
    Retrieve public market trades for a market, ordered by trade_time DESC.

    Args:
        market_internal_id: FK to markets(id)
        limit: Maximum rows to return (default 100)
        since: Optional datetime filter -- only trades after this time

    Returns:
        List of dictionaries, one per trade, ordered by trade_time DESC, id DESC.

    Example:
        >>> trades = get_market_trades(42, limit=50)
        >>> for t in trades:
        ...     print(t['yes_price'], t['count'], t['taker_side'])

        >>> # Get trades from the last hour
        >>> from datetime import datetime, timedelta, timezone
        >>> cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        >>> recent = get_market_trades(42, since=cutoff)

    References:
        - Migration 0028: market_trades
        - Issue #402: Add market_trades table for public trade tape
    """
    query = "SELECT * FROM market_trades WHERE market_internal_id = %s"
    params: list = [market_internal_id]

    if since is not None:
        query += " AND trade_time >= %s"
        params.append(since)

    query += " ORDER BY trade_time DESC, id DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


def get_latest_trade_time(market_internal_id: int) -> datetime | None:
    """
    Return trade_time from the most recent public trade for a market.

    Used as a high-water mark for incremental polling -- the poller asks
    Kalshi for trades newer than this timestamp, avoiding re-fetching the
    entire tape on every poll cycle.

    Args:
        market_internal_id: FK to markets(id)

    Returns:
        datetime of the latest trade, or None if no trades exist for this market.

    Example:
        >>> hwm = get_latest_trade_time(42)
        >>> if hwm is not None:
        ...     new_trades = kalshi_client.get_trades(market_id, min_ts=hwm)
        ... else:
        ...     new_trades = kalshi_client.get_trades(market_id)  # full fetch

    References:
        - Migration 0028: market_trades
        - Issue #402: Add market_trades table for public trade tape
    """
    query = """
        SELECT trade_time FROM market_trades
        WHERE market_internal_id = %s
        ORDER BY trade_time DESC, id DESC
        LIMIT 1
    """

    result = fetch_one(query, (market_internal_id,))
    if result is None:
        return None
    return cast("datetime", result["trade_time"])
