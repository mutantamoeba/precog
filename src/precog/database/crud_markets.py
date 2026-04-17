"""CRUD operations for markets and orderbook snapshots.

Extracted from crud_operations.py during Phase 1b domain split.

Tables covered:
    - markets: SCD Type 2 versioned market snapshots with pricing
    - orderbook_snapshots: Point-in-time order book depth data
"""

import json
import logging
import uuid
from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .crud_shared import (
    retry_on_scd_unique_conflict,
    validate_decimal,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MARKET OPERATIONS
# =============================================================================
#
# Migration 0021: Markets table split into dimension + fact.
#   - markets (dimension): stable identity + lifecycle state. One row per market.
#   - market_snapshots (fact): volatile pricing. SCD Type 2 versioned.
#
# Column renames: yes_price → yes_ask_price, no_price → no_ask_price
# New columns: yes_bid_price, no_bid_price, last_price, liquidity
#
# Migration 0022: downstream tables (edges/positions/trades/settlements) now use
# market_id INTEGER FK → markets(id). VARCHAR market_id is dropped.
# =============================================================================


def create_market(
    platform_id: str,
    event_id: int | None,
    external_id: str,
    ticker: str,
    title: str,
    yes_ask_price: Decimal,
    no_ask_price: Decimal,
    market_type: str = "binary",
    status: str = "open",
    volume: int | None = None,
    open_interest: int | None = None,
    spread: Decimal | None = None,
    metadata: dict | None = None,
    subtitle: str | None = None,
    open_time: str | None = None,
    close_time: str | None = None,
    expiration_time: str | None = None,
    outcome_label: str | None = None,
    subcategory: str | None = None,
    bracket_count: int | None = None,
    source_url: str | None = None,
    *,
    yes_bid_price: Decimal | None = None,
    no_bid_price: Decimal | None = None,
    last_price: Decimal | None = None,
    liquidity: Decimal | None = None,
    settlement_value: Decimal | None = None,
    expiration_value: str | None = None,
    notional_value: Decimal | None = None,
    volume_24h: int | None = None,
    previous_yes_bid: Decimal | None = None,
    previous_yes_ask: Decimal | None = None,
    previous_price: Decimal | None = None,
    yes_bid_size: int | None = None,
    yes_ask_size: int | None = None,
) -> int:
    """
    Create new market (dimension) + initial snapshot (fact).

    Inserts a row into the markets dimension table and a corresponding
    initial snapshot row into market_snapshots with row_current_ind = TRUE.

    Args:
        platform_id: Foreign key to platforms table (VARCHAR)
        event_id: Integer FK to events(id) surrogate PK. This is the
            integer returned by get_or_create_event().
            None if the market has no associated event.
        external_id: External market ID from platform
        ticker: Market ticker (e.g., "NFL-KC-BUF-YES")
        title: Market title/description
        yes_ask_price: YES ask price as DECIMAL(10,4) (cost to buy YES contract)
        no_ask_price: NO ask price as DECIMAL(10,4) (cost to buy NO contract)
        market_type: Market type (default: 'binary')
        status: Market status (default: 'open')
        volume: Trading volume
        open_interest: Open interest
        spread: Bid-ask spread as DECIMAL(10,4)
        metadata: Additional metadata as JSONB
        subtitle: Market subtitle from Kalshi API (e.g., "Week 14")
        open_time: When the market opened for trading (ISO 8601 string)
        close_time: When the market closes for trading (ISO 8601 string)
        expiration_time: When the market expires/settles (ISO 8601 string)
        outcome_label: Parsed outcome from ticker (e.g., "YES", "Over 42.5")
        subcategory: Sport subcategory (e.g., "nfl", "nba") — matches events.subcategory
        bracket_count: Number of markets in the parent event bracket
        source_url: URL to the market on the platform
        yes_bid_price: YES bid price as DECIMAL(10,4) (keyword-only, optional)
        no_bid_price: NO bid price as DECIMAL(10,4) (keyword-only, optional)
        last_price: Last traded price as DECIMAL(10,4) (keyword-only, optional)
        liquidity: Market liquidity as DECIMAL(10,4) (keyword-only, optional)
        settlement_value: Settlement outcome as DECIMAL(10,4) (keyword-only, optional)
        expiration_value: Free-text settlement outcome description (keyword-only, optional).
            e.g., "above 42.5", "yes". Dimension-level (per-market constant).
        notional_value: Dollar notional value of the contract as DECIMAL(10,4)
            (keyword-only, optional). Dimension-level (per-market constant).
        volume_24h: 24-hour rolling trading volume in contracts (keyword-only, optional).
            Integer count, not dollar value. Snapshot-level (per-poll observation).
        previous_yes_bid: Yesterday's YES bid price as DECIMAL(10,4) (keyword-only, optional).
            Snapshot-level (per-poll observation).
        previous_yes_ask: Yesterday's YES ask price as DECIMAL(10,4) (keyword-only, optional).
            Snapshot-level (per-poll observation).
        previous_price: Yesterday's last trade price as DECIMAL(10,4) (keyword-only, optional).
            Snapshot-level (per-poll observation).
        yes_bid_size: Number of contracts at best YES bid (keyword-only, optional).
            Integer count. Snapshot-level (per-poll observation).
        yes_ask_size: Number of contracts at best YES ask (keyword-only, optional).
            Integer count. Snapshot-level (per-poll observation).

    Returns:
        Integer surrogate PK (markets.id) of the newly created market.

    Note:
        yes_ask_price and no_ask_price store Kalshi ask prices, NOT implied
        probabilities. yes_ask_price + no_ask_price > 1.0 is normal (ask prices
        include the spread). At settlement, both can reach 1.0 or 0.0.

    Example:
        >>> market_pk = create_market(
        ...     platform_id="kalshi",
        ...     event_id=7,
        ...     external_id="KXNFLKCBUF",
        ...     ticker="NFL-KC-BUF-YES",
        ...     title="Chiefs to beat Bills",
        ...     yes_ask_price=Decimal("0.5200"),
        ...     no_ask_price=Decimal("0.4900"),
        ...     subtitle="Week 14",
        ...     close_time="2026-01-15T18:00:00Z",
        ...     volume_24h=150,
        ...     previous_yes_bid=Decimal("0.5100"),
        ... )

    Reference:
        - Migration 0021: markets split into dimension + market_snapshots fact
        - Migration 0022: market_id VARCHAR dropped, downstream uses integer FK
        - Migration 0033: enrichment columns added to dimension table
        - Migration 0037: league renamed to subcategory
        - Migration 0046: depth signals + daily movement columns
    """
    # Runtime type validation (enforces Decimal precision)
    yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    no_ask_price = validate_decimal(no_ask_price, "no_ask_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")
    if yes_bid_price is not None:
        yes_bid_price = validate_decimal(yes_bid_price, "yes_bid_price")
    if no_bid_price is not None:
        no_bid_price = validate_decimal(no_bid_price, "no_bid_price")
    if last_price is not None:
        last_price = validate_decimal(last_price, "last_price")
    if liquidity is not None:
        liquidity = validate_decimal(liquidity, "liquidity")
    if settlement_value is not None:
        settlement_value = validate_decimal(settlement_value, "settlement_value")
    # Migration 0046: depth + daily movement enrichment fields
    if notional_value is not None:
        notional_value = validate_decimal(notional_value, "notional_value")
    if previous_yes_bid is not None:
        previous_yes_bid = validate_decimal(previous_yes_bid, "previous_yes_bid")
    if previous_yes_ask is not None:
        previous_yes_ask = validate_decimal(previous_yes_ask, "previous_yes_ask")
    if previous_price is not None:
        previous_price = validate_decimal(previous_price, "previous_price")

    # Migration 0062 (#791): markets.market_key is NOT NULL + UNIQUE.  We
    # can only know the surrogate ``id`` after INSERT, so we use a
    # two-step pattern: insert with a uniquely-generated TEMP sentinel,
    # then UPDATE to ``MKT-{id}`` in the same transaction.  The TEMP
    # sentinel uses ``uuid.uuid4`` so concurrent INSERTs never collide
    # on the UNIQUE index during the ~microseconds between INSERT and
    # UPDATE.  Because both steps share ``get_cursor(commit=True)``,
    # readers outside the transaction never see the TEMP value.
    temp_market_key = f"TEMP-{uuid.uuid4()}"

    with get_cursor(commit=True) as cur:
        # Step 1: Insert dimension row with TEMP market_key placeholder.
        # Migration 0022: market_id VARCHAR dropped — no longer inserted.
        # Migration 0033: enrichment columns added (subtitle, timestamps, etc.)
        # Migration 0037: league renamed to subcategory
        # Migration 0046: expiration_value, notional_value added
        # Migration 0062: market_key added (two-step: TEMP → MKT-{id})
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_id, external_id,
                ticker, title, market_type, status, settlement_value,
                subtitle, open_time, close_time, expiration_time,
                outcome_label, subcategory, bracket_count, source_url,
                expiration_value, notional_value,
                metadata, market_key, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (
                platform_id,
                event_id,
                external_id,
                ticker,
                title,
                market_type,
                status,
                settlement_value,
                subtitle,
                open_time,
                close_time,
                expiration_time,
                outcome_label,
                subcategory,
                bracket_count,
                source_url,
                expiration_value,
                notional_value,
                json.dumps(metadata) if metadata else None,
                temp_market_key,
            ),
        )
        dim_row = cur.fetchone()
        market_pk = cast("int", dim_row["id"])

        # Step 1b: Replace TEMP market_key with the canonical ``MKT-{id}``.
        # Must happen before transaction commit so the TEMP value is never
        # observable externally.
        cur.execute(
            "UPDATE markets SET market_key = %s WHERE id = %s",
            (f"MKT-{market_pk}", market_pk),
        )

        # Step 2: Insert initial snapshot (fact row)
        # Migration 0021: yes_bid_price, no_bid_price, last_price, liquidity
        # Migration 0046: volume_24h, previous_*, yes_bid_size, yes_ask_size
        cur.execute(
            """
            INSERT INTO market_snapshots (
                market_id, yes_ask_price, no_ask_price,
                yes_bid_price, no_bid_price, last_price,
                spread, volume, open_interest, liquidity,
                volume_24h, previous_yes_bid, previous_yes_ask,
                previous_price, yes_bid_size, yes_ask_size,
                row_current_ind, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            """,
            (
                market_pk,
                yes_ask_price,
                no_ask_price,
                yes_bid_price,
                no_bid_price,
                last_price,
                spread,
                volume,
                open_interest,
                liquidity,
                volume_24h,
                previous_yes_bid,
                previous_yes_ask,
                previous_price,
                yes_bid_size,
                yes_ask_size,
            ),
        )

        return market_pk


def get_current_market(ticker: str) -> dict[str, Any] | None:
    """
    Get current market dimension + latest snapshot by ticker.

    Returns a single dict with dimension columns (ticker, title, status, etc.)
    and current snapshot columns (yes_ask_price, no_ask_price, volume, etc.).

    Note: Settled markets show yes_ask_price=1.0 AND no_ask_price=1.0 (Kalshi
    post-settlement behavior). For historical trading prices, use
    get_market_history() instead. See Issue #315.

    Args:
        ticker: Market ticker

    Returns:
        Dictionary with market + snapshot data, or None if not found

    Example:
        >>> market = get_current_market("NFL-KC-BUF-YES")
        >>> print(market['yes_ask_price'])  # Decimal('0.5200')

    Reference:
        - Migration 0021: markets dimension + market_snapshots fact
    """
    # Migration 0022: market_id VARCHAR dropped. Use ticker for lookup.
    # Migration 0033: enrichment columns added to dimension table.
    # Migration 0046: depth signals + daily movement columns.
    query = """
        SELECT
            m.id,
            m.platform_id,
            m.event_id,
            m.external_id,
            m.ticker,
            m.title,
            m.subtitle,
            m.market_type,
            m.status,
            m.settlement_value,
            m.open_time,
            m.close_time,
            m.expiration_time,
            m.outcome_label,
            m.subcategory,
            m.bracket_count,
            m.source_url,
            m.expiration_value,
            m.notional_value,
            m.metadata,
            m.created_at,
            m.updated_at,
            ms.yes_ask_price,
            ms.no_ask_price,
            ms.yes_bid_price,
            ms.no_bid_price,
            ms.last_price,
            ms.spread,
            ms.volume,
            ms.open_interest,
            ms.liquidity,
            ms.volume_24h,
            ms.previous_yes_bid,
            ms.previous_yes_ask,
            ms.previous_price,
            ms.yes_bid_size,
            ms.yes_ask_size,
            ms.row_start_ts,
            ms.row_end_ts,
            ms.row_current_ind
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id
            AND ms.row_current_ind = TRUE
        WHERE m.ticker = %s
    """
    return fetch_one(query, (ticker,))


def count_open_markets() -> int:
    """
    Count markets with status='open'.

    Returns:
        Number of currently open markets in the database.

    Educational Note:
        After migration 0021, the markets table is a dimension table with
        one row per market (no SCD versioning). Status is mutable on the
        dimension row directly, so no row_current_ind filter is needed.

    Example:
        >>> count = count_open_markets()
        >>> print(f"Tracking {count} open markets")
    """
    query = """
        SELECT COUNT(*) AS count
        FROM markets
        WHERE status = 'open'
    """
    result = fetch_one(query)
    if result is None:
        return 0
    return int(result["count"])


def count_open_markets_by_subcategory(subcategory: str) -> int:
    """Count open (non-settled) markets for a given subcategory (e.g., 'nfl', 'nba').

    Uses COALESCE to check both the market's denormalized subcategory and
    the parent event's subcategory, matching the pattern in get_markets_summary.

    Args:
        subcategory: Sport subcategory to filter by (e.g., "nfl", "nba").

    Returns:
        Number of open markets for the given subcategory.

    Educational Note:
        Migration 0037 renamed league to subcategory. Markets may have the
        subcategory denormalized directly, or it may only exist on the parent
        event. COALESCE handles both cases.

    Example:
        >>> nfl_count = count_open_markets_by_subcategory("nfl")
        >>> print(f"Tracking {nfl_count} open NFL markets")
    """
    query = """
        SELECT COUNT(*) AS count
        FROM markets m
        LEFT JOIN events e ON e.id = m.event_id
        WHERE m.status = 'open'
          AND LOWER(COALESCE(m.subcategory, e.subcategory)) = LOWER(%s)
    """
    result = fetch_one(query, (subcategory,))
    if result is None:
        return 0
    return int(result["count"])


def update_market_with_versioning(
    ticker: str,
    yes_ask_price: Decimal | None = None,
    no_ask_price: Decimal | None = None,
    status: str | None = None,
    volume: int | None = None,
    open_interest: int | None = None,
    market_metadata: dict | None = None,
    subtitle: str | None = None,
    open_time: str | None = None,
    close_time: str | None = None,
    expiration_time: str | None = None,
    outcome_label: str | None = None,
    subcategory: str | None = None,
    bracket_count: int | None = None,
    source_url: str | None = None,
    *,
    spread: Decimal | None = None,
    yes_bid_price: Decimal | None = None,
    no_bid_price: Decimal | None = None,
    last_price: Decimal | None = None,
    liquidity: Decimal | None = None,
    settlement_value: Decimal | None = None,
    expiration_value: str | None = None,
    notional_value: Decimal | None = None,
    volume_24h: int | None = None,
    previous_yes_bid: Decimal | None = None,
    previous_yes_ask: Decimal | None = None,
    previous_price: Decimal | None = None,
    yes_bid_size: int | None = None,
    yes_ask_size: int | None = None,
) -> int:
    """
    Update market: SCD Type 2 on snapshots, direct UPDATE on dimension.

    After migration 0021, pricing updates create new snapshot rows
    (SCD Type 2), while status/metadata/enrichment updates go to the
    dimension table directly.

    Steps:
    1. UPDATE markets dimension row (status, metadata, enrichment columns)
    2. If price changed: mark current snapshot as historical, insert new snapshot

    Args:
        ticker: Market ticker to update
        yes_ask_price: New YES ask price (optional)
        no_ask_price: New NO ask price (optional)
        status: New status (optional)
        volume: New volume (optional)
        open_interest: New open interest (optional)
        market_metadata: New metadata (optional)
        subtitle: Market subtitle (optional, dimension-level)
        open_time: When market opened for trading (optional, ISO 8601)
        close_time: When market closes for trading (optional, ISO 8601)
        expiration_time: When market expires/settles (optional, ISO 8601)
        outcome_label: Parsed outcome from ticker (optional)
        subcategory: Sport subcategory (optional) — matches events.subcategory
        bracket_count: Number of markets in parent event bracket (optional)
        source_url: URL to the market on the platform (optional)
        spread: Fresh bid-ask spread as DECIMAL(10,4) (keyword-only, optional)
        yes_bid_price: YES bid price as DECIMAL(10,4) (keyword-only, optional)
        no_bid_price: NO bid price as DECIMAL(10,4) (keyword-only, optional)
        last_price: Last traded price as DECIMAL(10,4) (keyword-only, optional)
        liquidity: Market liquidity as DECIMAL(10,4) (keyword-only, optional)
        settlement_value: Settlement outcome as DECIMAL(10,4) (keyword-only, optional).
            Must be 0.0000 (no) or 1.0000 (yes). CHECK constraint: 0.0000-1.0000.
        expiration_value: Free-text settlement outcome description (keyword-only, optional).
            Dimension-level (per-market constant).
        notional_value: Dollar notional value as DECIMAL(10,4) (keyword-only, optional).
            Dimension-level (per-market constant).
        volume_24h: 24-hour rolling volume in contracts (keyword-only, optional).
            Integer count. Snapshot-level (per-poll observation).
        previous_yes_bid: Yesterday's YES bid as DECIMAL(10,4) (keyword-only, optional).
            Snapshot-level (per-poll observation).
        previous_yes_ask: Yesterday's YES ask as DECIMAL(10,4) (keyword-only, optional).
            Snapshot-level (per-poll observation).
        previous_price: Yesterday's last trade price as DECIMAL(10,4) (keyword-only, optional).
            Snapshot-level (per-poll observation).
        yes_bid_size: Contracts at best YES bid (keyword-only, optional).
            Integer count. Snapshot-level (per-poll observation).
        yes_ask_size: Contracts at best YES ask (keyword-only, optional).
            Integer count. Snapshot-level (per-poll observation).

    Returns:
        Integer surrogate PK of the market (markets.id)

    Example:
        >>> market_pk = update_market_with_versioning(
        ...     ticker="NFL-KC-BUF-YES",
        ...     yes_ask_price=Decimal("0.5500"),
        ...     no_ask_price=Decimal("0.4500"),
        ...     volume_24h=200,
        ...     previous_price=Decimal("0.5300"),
        ... )

    Reference:
        - Migration 0021: markets dimension + market_snapshots fact
        - Migration 0033: enrichment columns on dimension table
        - Migration 0037: league renamed to subcategory
        - Migration 0046: depth signals + daily movement columns
    """
    # Runtime type validation (enforces Decimal precision)
    if yes_ask_price is not None:
        yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    if no_ask_price is not None:
        no_ask_price = validate_decimal(no_ask_price, "no_ask_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")
    if yes_bid_price is not None:
        yes_bid_price = validate_decimal(yes_bid_price, "yes_bid_price")
    if no_bid_price is not None:
        no_bid_price = validate_decimal(no_bid_price, "no_bid_price")
    if last_price is not None:
        last_price = validate_decimal(last_price, "last_price")
    if liquidity is not None:
        liquidity = validate_decimal(liquidity, "liquidity")
    if settlement_value is not None:
        settlement_value = validate_decimal(settlement_value, "settlement_value")
    # Migration 0046: depth + daily movement enrichment fields
    if notional_value is not None:
        notional_value = validate_decimal(notional_value, "notional_value")
    if previous_yes_bid is not None:
        previous_yes_bid = validate_decimal(previous_yes_bid, "previous_yes_bid")
    if previous_yes_ask is not None:
        previous_yes_ask = validate_decimal(previous_yes_ask, "previous_yes_ask")
    if previous_price is not None:
        previous_price = validate_decimal(previous_price, "previous_price")

    def _attempt_update_and_snapshot() -> int:
        """One attempt at the dimension UPDATE + SCD snapshot close+insert.

        Opens its own ``get_cursor(commit=True)`` block so the retry helper
        can run this closure twice and get a fresh transaction (with a fresh
        MVCC snapshot) on the second invocation.

        Issue #625: concurrent-update race on market_snapshots. When two
        callers update the same market's snapshot concurrently, both can
        close (the second as a no-op) and both can INSERT, colliding on
        idx_market_snapshots_unique_current. On retry, the FOR UPDATE lock
        serializes the second caller against the sibling's committed row,
        and the close+insert path proceeds normally.

        ``get_current_market`` is called INSIDE the closure so retries pick
        up fresh snapshot values committed by the sibling caller. NOW() is
        captured INSIDE each attempt for temporal continuity.
        """
        # Re-fetch current market + snapshot on each attempt so retries see
        # the sibling caller's now-committed row.
        current = get_current_market(ticker)
        if not current:
            msg = f"Market not found: {ticker}"
            raise ValueError(msg)

        market_pk = current["id"]

        # Determine what changed
        new_yes = yes_ask_price if yes_ask_price is not None else current["yes_ask_price"]
        new_no = no_ask_price if no_ask_price is not None else current["no_ask_price"]
        new_status = status if status is not None else current["status"]
        new_volume = volume if volume is not None else current["volume"]
        new_open_interest = open_interest if open_interest is not None else current["open_interest"]
        new_metadata = market_metadata if market_metadata is not None else current["metadata"]

        # Snapshot microstructure: use fresh values when provided, fall back to current
        new_spread = spread if spread is not None else current["spread"]
        new_yes_bid = yes_bid_price if yes_bid_price is not None else current["yes_bid_price"]
        new_no_bid = no_bid_price if no_bid_price is not None else current["no_bid_price"]
        new_last_price = last_price if last_price is not None else current["last_price"]
        new_liquidity = liquidity if liquidity is not None else current["liquidity"]

        # Migration 0046: snapshot enrichment — use fresh values, fall back to current
        new_volume_24h = volume_24h if volume_24h is not None else current.get("volume_24h")
        new_prev_yes_bid = (
            previous_yes_bid if previous_yes_bid is not None else current.get("previous_yes_bid")
        )
        new_prev_yes_ask = (
            previous_yes_ask if previous_yes_ask is not None else current.get("previous_yes_ask")
        )
        new_prev_price = (
            previous_price if previous_price is not None else current.get("previous_price")
        )
        new_yes_bid_size = yes_bid_size if yes_bid_size is not None else current.get("yes_bid_size")
        new_yes_ask_size = yes_ask_size if yes_ask_size is not None else current.get("yes_ask_size")

        # Enrichment columns: only override if explicitly provided (not None)
        new_subtitle = subtitle if subtitle is not None else current["subtitle"]
        new_open_time = open_time if open_time is not None else current["open_time"]
        new_close_time = close_time if close_time is not None else current["close_time"]
        new_expiration_time = (
            expiration_time if expiration_time is not None else current["expiration_time"]
        )
        new_outcome_label = outcome_label if outcome_label is not None else current["outcome_label"]
        new_subcategory = subcategory if subcategory is not None else current["subcategory"]
        new_bracket_count = bracket_count if bracket_count is not None else current["bracket_count"]
        new_source_url = source_url if source_url is not None else current["source_url"]
        new_settlement_value = (
            settlement_value if settlement_value is not None else current["settlement_value"]
        )
        # Migration 0046: dimension enrichment — use fresh values, fall back to current
        new_expiration_value = (
            expiration_value if expiration_value is not None else current.get("expiration_value")
        )
        new_notional_value = (
            notional_value if notional_value is not None else current.get("notional_value")
        )

        with get_cursor(commit=True) as cur:
            # Capture timestamp once for temporal continuity within THIS attempt.
            cur.execute("SELECT NOW() AS ts")
            now = cur.fetchone()["ts"]

            # Step 0: Lock the current snapshot row (if any) for the target
            # market. FOR UPDATE serializes concurrent updates; on retry the
            # sibling caller's committed row is visible and gets locked.
            cur.execute(
                """
                SELECT id FROM market_snapshots
                WHERE market_id = %s
                  AND row_current_ind = TRUE
                FOR UPDATE
                """,
                (market_pk,),
            )

            # Step 1: Update dimension row — always bump updated_at, plus
            # status/metadata/enrichment if they changed.
            # Migration 0033: enrichment columns updated on dimension row.
            # Migration 0046: expiration_value, notional_value added.
            cur.execute(
                """
                UPDATE markets
                SET status = %s,
                    metadata = %s,
                    subtitle = %s,
                    open_time = %s,
                    close_time = %s,
                    expiration_time = %s,
                    outcome_label = %s,
                    subcategory = %s,
                    bracket_count = %s,
                    source_url = %s,
                    settlement_value = %s,
                    expiration_value = %s,
                    notional_value = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    new_status,
                    json.dumps(new_metadata) if new_metadata else None,
                    new_subtitle,
                    new_open_time,
                    new_close_time,
                    new_expiration_time,
                    new_outcome_label,
                    new_subcategory,
                    new_bracket_count,
                    new_source_url,
                    new_settlement_value,
                    new_expiration_value,
                    new_notional_value,
                    now,
                    market_pk,
                ),
            )

            # Step 2: Create new snapshot (SCD Type 2 on market_snapshots)
            # Mark current snapshot as historical using the captured timestamp
            # so the close/insert pair share one temporal boundary.
            cur.execute(
                """
                UPDATE market_snapshots
                SET row_current_ind = FALSE,
                    row_end_ts = %s
                WHERE market_id = %s
                  AND row_current_ind = TRUE
                """,
                (now, market_pk),
            )

            # Insert new snapshot
            # Migration 0021: yes_bid_price, no_bid_price, last_price, liquidity
            # Migration 0046: volume_24h, previous_*, yes_bid_size, yes_ask_size
            cur.execute(
                """
                INSERT INTO market_snapshots (
                    market_id, yes_ask_price, no_ask_price,
                    yes_bid_price, no_bid_price, last_price,
                    spread, volume, open_interest, liquidity,
                    volume_24h, previous_yes_bid, previous_yes_ask,
                    previous_price, yes_bid_size, yes_ask_size,
                    row_current_ind, row_start_ts, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                """,
                (
                    market_pk,
                    new_yes,
                    new_no,
                    new_yes_bid,
                    new_no_bid,
                    new_last_price,
                    new_spread,
                    new_volume,
                    new_open_interest,
                    new_liquidity,
                    new_volume_24h,
                    new_prev_yes_bid,
                    new_prev_yes_ask,
                    new_prev_price,
                    new_yes_bid_size,
                    new_yes_ask_size,
                    now,
                    now,
                ),
            )

            return cast("int", market_pk)

    return retry_on_scd_unique_conflict(
        _attempt_update_and_snapshot,
        "idx_market_snapshots_unique_current",
        business_key={"ticker": ticker},
        logger_override=logger,
    )


def get_market_history(ticker: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    Get price snapshot history for a market (all versions).

    After migration 0021, history comes from market_snapshots (the fact table).
    Each row represents a point-in-time price observation.

    Args:
        ticker: Market ticker
        limit: Maximum number of snapshots to return (default: 100)

    Returns:
        List of snapshot records, newest first

    Example:
        >>> history = get_market_history("NFL-KC-BUF-YES", limit=10)
        >>> for version in history:
        ...     print(version['yes_ask_price'], version['row_start_ts'])

    Reference:
        - Migration 0021: price history now in market_snapshots
    """
    query = """
        SELECT ms.*
        FROM market_snapshots ms
        JOIN markets m ON ms.market_id = m.id
        WHERE m.ticker = %s
        ORDER BY ms.created_at DESC
        LIMIT %s
    """
    return fetch_all(query, (ticker, limit))


def get_markets_summary(
    subcategory: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get market summary data for display.

    Returns current markets with key fields for browsing and filtering.
    JOINs dimension (markets) + current snapshot (market_snapshots) +
    event (for subcategory/sport info).

    Args:
        subcategory: Filter by sport/subcategory (nfl, nba, etc.) via events
        status: Filter by status (open, closed, settled)
        search: Search term for ticker or title (case insensitive)
        limit: Maximum number of markets to return (default: 100)
        offset: Number of markets to skip for pagination

    Returns:
        List of market dictionaries with summary fields:
        - ticker, title, subcategory, yes_ask_price, no_ask_price, status, volume

    Example:
        >>> markets = get_markets_summary(subcategory='nfl', status='open', limit=50)
        >>> for m in markets:
        ...     print(f"{m['ticker']}: ${m['yes_ask_price']:.2f}")

    Reference:
        - Migration 0021: markets dimension + market_snapshots fact
    """
    # Migration 0033: enrichment columns (subtitle, subcategory, close_time) added for GUI.
    # Migration 0037: league renamed to subcategory. Prefer market's denormalized copy,
    # fall back to event's subcategory for markets without the enrichment column populated.
    query = """
        SELECT
            m.ticker,
            m.title,
            m.subtitle,
            COALESCE(m.subcategory, e.subcategory, 'unknown') as subcategory,
            ms.yes_ask_price,
            ms.no_ask_price,
            m.status,
            m.close_time,
            COALESCE(ms.volume, 0) as volume
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id AND ms.row_current_ind = TRUE
        LEFT JOIN events e
            ON e.id = m.event_id
        WHERE 1=1
    """
    params: list[Any] = []

    if subcategory is not None:
        query += " AND LOWER(COALESCE(m.subcategory, e.subcategory)) = LOWER(%s)"
        params.append(subcategory)

    if status is not None:
        query += " AND LOWER(m.status) = LOWER(%s)"
        params.append(status)

    if search is not None:
        query += " AND (LOWER(m.ticker) LIKE %s OR LOWER(m.title) LIKE %s)"
        search_pattern = f"%{search.lower()}%"
        params.extend([search_pattern, search_pattern])

    query += " ORDER BY m.updated_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    return fetch_all(query, tuple(params))


# =============================================================================
# ORDERBOOK SNAPSHOT OPERATIONS (Migration 0034)
# =============================================================================


def insert_orderbook_snapshot(
    market_id: int,
    best_bid: Decimal | None = None,
    best_ask: Decimal | None = None,
    spread: Decimal | None = None,
    bid_depth_total: int | None = None,
    ask_depth_total: int | None = None,
    depth_imbalance: Decimal | None = None,
    weighted_mid: Decimal | None = None,
    bid_prices: list[Decimal] | None = None,
    bid_quantities: list[int] | None = None,
    ask_prices: list[Decimal] | None = None,
    ask_quantities: list[int] | None = None,
    levels: int | None = None,
) -> int:
    """
    Insert an order book depth snapshot.

    Stores a point-in-time snapshot of the full order book for a market.
    This is append-only time-series data (not SCD Type 2).

    Args:
        market_id: Integer FK to markets(id)
        best_bid: Best bid price as DECIMAL(10,4)
        best_ask: Best ask price as DECIMAL(10,4)
        spread: Bid-ask spread as DECIMAL(10,4), must be >= 0
        bid_depth_total: Total bid depth (sum of all bid quantities)
        ask_depth_total: Total ask depth (sum of all ask quantities)
        depth_imbalance: Imbalance ratio in [-1, 1] (negative = ask-heavy)
        weighted_mid: Volume-weighted midpoint price as DECIMAL(10,4)
        bid_prices: Array of bid prices at each level, DECIMAL(10,4)[]
        bid_quantities: Array of bid quantities at each level, INTEGER[]
        ask_prices: Array of ask prices at each level, DECIMAL(10,4)[]
        ask_quantities: Array of ask quantities at each level, INTEGER[]
        levels: Number of depth levels captured

    Returns:
        id of the inserted snapshot row

    Example:
        >>> snapshot_id = insert_orderbook_snapshot(
        ...     market_id=42,
        ...     best_bid=Decimal("0.5000"),
        ...     best_ask=Decimal("0.5200"),
        ...     spread=Decimal("0.0200"),
        ...     bid_depth_total=500,
        ...     ask_depth_total=300,
        ...     depth_imbalance=Decimal("0.2500"),
        ...     weighted_mid=Decimal("0.5075"),
        ...     bid_prices=[Decimal("0.5000"), Decimal("0.4900")],
        ...     bid_quantities=[200, 300],
        ...     ask_prices=[Decimal("0.5200"), Decimal("0.5300")],
        ...     ask_quantities=[150, 150],
        ...     levels=2,
        ... )

    References:
        - Migration 0034: orderbook_snapshots table
        - Issue #443: Orderbook depth storage
    """
    query = """
        INSERT INTO orderbook_snapshots (
            market_id, best_bid, best_ask, spread,
            bid_depth_total, ask_depth_total, depth_imbalance, weighted_mid,
            bid_prices, bid_quantities, ask_prices, ask_quantities, levels,
            snapshot_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
    """

    params = (
        market_id,
        best_bid,
        best_ask,
        spread,
        bid_depth_total,
        ask_depth_total,
        depth_imbalance,
        weighted_mid,
        bid_prices,
        bid_quantities,
        ask_prices,
        ask_quantities,
        levels,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_latest_orderbook(market_id: int) -> dict[str, Any] | None:
    """
    Get the most recent order book snapshot for a market.

    Args:
        market_id: Integer FK to markets(id)

    Returns:
        Dictionary of snapshot columns, or None if no snapshots exist

    Example:
        >>> snapshot = get_latest_orderbook(market_id=42)
        >>> if snapshot:
        ...     print(snapshot['spread'], snapshot['depth_imbalance'])

    References:
        - Migration 0034: orderbook_snapshots table
    """
    query = """
        SELECT * FROM orderbook_snapshots
        WHERE market_id = %s
        ORDER BY snapshot_time DESC
        LIMIT 1
    """
    return fetch_one(query, (market_id,))


def get_orderbook_history(
    market_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get order book snapshot history for a market, newest first.

    Args:
        market_id: Integer FK to markets(id)
        limit: Maximum number of snapshots to return (default: 100)

    Returns:
        List of snapshot dictionaries, ordered by snapshot_time DESC

    Example:
        >>> history = get_orderbook_history(market_id=42, limit=50)
        >>> for snap in history:
        ...     print(snap['snapshot_time'], snap['spread'], snap['levels'])

    References:
        - Migration 0034: orderbook_snapshots table
    """
    query = """
        SELECT * FROM orderbook_snapshots
        WHERE market_id = %s
        ORDER BY snapshot_time DESC
        LIMIT %s
    """
    return fetch_all(query, (market_id, limit))


# =============================================================================
# Games Dimension CRUD (Migration 0035)
# =============================================================================
