"""
CRUD operations for Precog database using raw SQL queries.

All functions use parameterized queries to prevent SQL injection.
Supports SCD Type 2 versioning (row_current_ind) for markets and positions.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from .connection import execute_query, fetch_one, fetch_all, get_cursor


# =============================================================================
# MARKET OPERATIONS
# =============================================================================

def create_market(
    platform_id: str,
    event_id: str,
    external_id: str,
    ticker: str,
    title: str,
    yes_price: Decimal,
    no_price: Decimal,
    market_type: str = 'binary',
    status: str = 'open',
    volume: Optional[int] = None,
    open_interest: Optional[int] = None,
    spread: Optional[Decimal] = None,
    metadata: Optional[Dict] = None
) -> str:
    """
    Create new market record with row_current_ind = TRUE.

    Args:
        platform_id: Foreign key to platforms table (VARCHAR)
        event_id: Foreign key to events table (VARCHAR)
        external_id: External market ID from platform
        ticker: Market ticker (e.g., "NFL-KC-BUF-YES")
        title: Market title/description
        yes_price: YES price as DECIMAL(10,4)
        no_price: NO price as DECIMAL(10,4)
        market_type: Market type (default: 'binary')
        status: Market status (default: 'open')
        volume: Trading volume
        open_interest: Open interest
        spread: Bid-ask spread as DECIMAL(10,4)
        metadata: Additional metadata as JSONB

    Returns:
        market_id of newly created record

    Example:
        >>> market_id = create_market(
        ...     platform_id="kalshi",
        ...     event_id="EVT-NFL-KC-BUF",
        ...     external_id="KXNFLKCBUF",
        ...     ticker="NFL-KC-BUF-YES",
        ...     title="Chiefs to beat Bills",
        ...     yes_price=Decimal("0.5200"),
        ...     no_price=Decimal("0.4800")
        ... )
    """
    # Generate market_id if needed (using ticker as base)
    market_id = f"MKT-{ticker}"

    query = """
        INSERT INTO markets (
            market_id, platform_id, event_id, external_id,
            ticker, title, market_type,
            yes_price, no_price, status,
            volume, open_interest, spread,
            metadata, row_current_ind, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
        RETURNING market_id
    """

    params = (
        market_id, platform_id, event_id, external_id,
        ticker, title, market_type,
        yes_price, no_price, status,
        volume, open_interest, spread,
        metadata
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result['market_id']


def get_current_market(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get current version of market by ticker.

    Args:
        ticker: Market ticker

    Returns:
        Dictionary with market data, or None if not found

    Example:
        >>> market = get_current_market("NFL-KC-BUF-YES")
        >>> print(market['yes_price'])  # Decimal('0.5200')
    """
    query = """
        SELECT *
        FROM markets
        WHERE ticker = %s
          AND row_current_ind = TRUE
    """
    return fetch_one(query, (ticker,))


def update_market_with_versioning(
    ticker: str,
    yes_price: Optional[Decimal] = None,
    no_price: Optional[Decimal] = None,
    status: Optional[str] = None,
    volume: Optional[int] = None,
    open_interest: Optional[int] = None,
    market_metadata: Optional[Dict] = None
) -> int:
    """
    Update market using SCD Type 2 versioning.

    Steps:
    1. Mark current row as row_current_ind = FALSE, set row_end_ts
    2. Insert new row with updated values, row_current_ind = TRUE

    Args:
        ticker: Market ticker to update
        yes_price: New YES price (optional)
        no_price: New NO price (optional)
        status: New status (optional)
        volume: New volume (optional)
        open_interest: New open interest (optional)
        market_metadata: New metadata (optional)

    Returns:
        market_id of newly created version

    Example:
        >>> new_id = update_market_with_versioning(
        ...     ticker="NFL-KC-BUF-YES",
        ...     yes_price=Decimal("0.5500"),
        ...     no_price=Decimal("0.4500")
        ... )
    """
    # Get current version
    current = get_current_market(ticker)
    if not current:
        raise ValueError(f"Market not found: {ticker}")

    # Use new values or fall back to current
    new_yes_price = yes_price if yes_price is not None else current['yes_price']
    new_no_price = no_price if no_price is not None else current['no_price']
    new_status = status if status is not None else current['status']
    new_volume = volume if volume is not None else current['volume']
    new_open_interest = open_interest if open_interest is not None else current['open_interest']
    new_metadata = market_metadata if market_metadata is not None else current['metadata']

    with get_cursor(commit=True) as cur:
        # Step 1: Mark current row as historical
        cur.execute("""
            UPDATE markets
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE ticker = %s
              AND row_current_ind = TRUE
        """, (ticker,))

        # Step 2: Insert new version
        cur.execute("""
            INSERT INTO markets (
                market_id, platform_id, event_id, external_id,
                ticker, title, market_type,
                yes_price, no_price, status,
                volume, open_interest, spread,
                metadata, row_current_ind, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            RETURNING market_id
        """, (
            current['market_id'],
            current['platform_id'],
            current['event_id'],
            current['external_id'],
            ticker,
            current['title'],
            current['market_type'],
            new_yes_price,
            new_no_price,
            new_status,
            new_volume,
            new_open_interest,
            current['spread'],
            new_metadata
        ))

        result = cur.fetchone()
        return result['market_id']


def get_market_history(ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get price history for a market (all versions).

    Args:
        ticker: Market ticker
        limit: Maximum number of versions to return (default: 100)

    Returns:
        List of market versions, newest first

    Example:
        >>> history = get_market_history("NFL-KC-BUF-YES", limit=10)
        >>> for version in history:
        ...     print(version['yes_price'], version['row_start_ts'])
    """
    query = """
        SELECT *
        FROM markets
        WHERE ticker = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    return fetch_all(query, (ticker, limit))


# =============================================================================
# POSITION OPERATIONS
# =============================================================================

def create_position(
    market_id: str,
    strategy_id: int,
    model_id: int,
    side: str,
    quantity: int,
    entry_price: Decimal,
    target_price: Optional[Decimal] = None,
    stop_loss_price: Optional[Decimal] = None,
    trailing_stop_state: Optional[Dict] = None,
    position_metadata: Optional[Dict] = None
) -> int:
    """
    Create new position with status = 'open'.

    Args:
        market_id: Foreign key to markets
        strategy_id: Foreign key to strategies (immutable version)
        model_id: Foreign key to probability_models (immutable version)
        side: 'YES' or 'NO'
        quantity: Number of contracts
        entry_price: Entry price as DECIMAL(10,4)
        target_price: Take-profit target
        stop_loss_price: Stop-loss price
        trailing_stop_state: Trailing stop configuration as JSONB
        position_metadata: Additional metadata

    Returns:
        position_id of newly created position

    Example:
        >>> pos_id = create_position(
        ...     market_id=42,
        ...     strategy_id=1,
        ...     model_id=2,
        ...     side='YES',
        ...     quantity=100,
        ...     entry_price=Decimal("0.5200"),
        ...     stop_loss_price=Decimal("0.4800")
        ... )
    """
    query = """
        INSERT INTO positions (
            market_id, strategy_id, model_id, side,
            quantity, entry_price,
            target_price, stop_loss_price,
            trailing_stop_state, position_metadata,
            status, row_current_ind, entry_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', TRUE, NOW())
        RETURNING position_id
    """

    params = (
        market_id, strategy_id, model_id, side,
        quantity, entry_price,
        target_price, stop_loss_price,
        trailing_stop_state, position_metadata
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result['position_id']


def get_current_positions(
    status: Optional[str] = None,
    market_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get current positions (row_current_ind = TRUE).

    Args:
        status: Filter by status ('open', 'closed', etc.)
        market_id: Filter by market_id

    Returns:
        List of current positions

    Example:
        >>> open_positions = get_current_positions(status='open')
        >>> for pos in open_positions:
        ...     print(pos['market_id'], pos['quantity'], pos['entry_price'])
    """
    query = """
        SELECT p.*, m.ticker, m.yes_price as current_market_price
        FROM positions p
        JOIN markets m ON p.market_id = m.market_id
        WHERE p.row_current_ind = TRUE
          AND m.row_current_ind = TRUE
    """
    params = []

    if status:
        query += " AND p.status = %s"
        params.append(status)

    if market_id:
        query += " AND p.market_id = %s"
        params.append(market_id)

    query += " ORDER BY p.entry_time DESC"

    return fetch_all(query, tuple(params) if params else None)


def update_position_price(
    position_id: int,
    current_price: Decimal,
    trailing_stop_state: Optional[Dict] = None
) -> int:
    """
    Update position with new price using SCD Type 2 versioning.

    Used for monitoring price changes and updating trailing stops.

    Args:
        position_id: Position to update
        current_price: Current market price
        trailing_stop_state: Updated trailing stop state

    Returns:
        position_id of newly created version

    Example:
        >>> new_id = update_position_price(
        ...     position_id=42,
        ...     current_price=Decimal("0.5800"),
        ...     trailing_stop_state={"peak": "0.5800", "stop": "0.5500"}
        ... )
    """
    # Get current version
    current = fetch_one(
        "SELECT * FROM positions WHERE position_id = %s AND row_current_ind = TRUE",
        (position_id,)
    )
    if not current:
        raise ValueError(f"Position not found: {position_id}")

    new_trailing_stop = trailing_stop_state if trailing_stop_state is not None else current['trailing_stop_state']

    with get_cursor(commit=True) as cur:
        # Mark current as historical
        cur.execute("""
            UPDATE positions
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE position_id = %s
              AND row_current_ind = TRUE
        """, (position_id,))

        # Insert new version with updated price
        cur.execute("""
            INSERT INTO positions (
                market_id, strategy_id, model_id, side,
                quantity, entry_price,
                current_price, unrealized_pnl,
                target_price, stop_loss_price,
                trailing_stop_state, position_metadata,
                status, entry_time, last_check_time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING position_id
        """, (
            current['market_id'],
            current['strategy_id'],
            current['model_id'],
            current['side'],
            current['quantity'],
            current['entry_price'],
            current_price,
            (current_price - current['entry_price']) * current['quantity'],  # unrealized_pnl
            current['target_price'],
            current['stop_loss_price'],
            new_trailing_stop,
            current['position_metadata'],
            current['status'],
            current['entry_time']
        ))

        result = cur.fetchone()
        return result['position_id']


def close_position(
    position_id: int,
    exit_price: Decimal,
    exit_reason: str,
    realized_pnl: Decimal
) -> int:
    """
    Close position by updating status to 'closed'.

    Args:
        position_id: Position to close
        exit_price: Final exit price
        exit_reason: Reason for exit (e.g., 'target_hit', 'stop_loss', 'manual')
        realized_pnl: Realized profit/loss

    Returns:
        position_id of closed version

    Example:
        >>> closed_id = close_position(
        ...     position_id=42,
        ...     exit_price=Decimal("0.6000"),
        ...     exit_reason='target_hit',
        ...     realized_pnl=Decimal("8.00")
        ... )
    """
    # Get current version
    current = fetch_one(
        "SELECT * FROM positions WHERE position_id = %s AND row_current_ind = TRUE",
        (position_id,)
    )
    if not current:
        raise ValueError(f"Position not found: {position_id}")

    with get_cursor(commit=True) as cur:
        # Mark current as historical
        cur.execute("""
            UPDATE positions
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE position_id = %s
              AND row_current_ind = TRUE
        """, (position_id,))

        # Insert closed version
        cur.execute("""
            INSERT INTO positions (
                market_id, strategy_id, model_id, side,
                quantity, entry_price, exit_price,
                realized_pnl,
                target_price, stop_loss_price,
                trailing_stop_state, position_metadata,
                status, entry_time, exit_time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'closed', %s, NOW())
            RETURNING position_id
        """, (
            current['market_id'],
            current['strategy_id'],
            current['model_id'],
            current['side'],
            current['quantity'],
            current['entry_price'],
            exit_price,
            realized_pnl,
            current['target_price'],
            current['stop_loss_price'],
            current['trailing_stop_state'],
            current['position_metadata'],
            current['entry_time']
        ))

        result = cur.fetchone()
        return result['position_id']


# =============================================================================
# TRADE OPERATIONS
# =============================================================================

def create_trade(
    market_id: str,
    strategy_id: int,
    model_id: int,
    side: str,
    quantity: int,
    price: Decimal,
    position_id: Optional[int] = None,
    order_type: str = 'market',
    trade_metadata: Optional[Dict] = None
) -> int:
    """
    Record executed trade with strategy and model attribution.

    Args:
        market_id: Foreign key to markets
        strategy_id: Strategy version that generated this trade
        model_id: Model version used for probability
        side: 'YES' or 'NO'
        quantity: Number of contracts
        price: Execution price as DECIMAL(10,4)
        position_id: Associated position (if any)
        order_type: Order type (default: 'market')
        trade_metadata: Additional metadata

    Returns:
        trade_id of newly created trade

    Example:
        >>> trade_id = create_trade(
        ...     market_id=42,
        ...     strategy_id=1,
        ...     model_id=2,
        ...     side='YES',
        ...     quantity=100,
        ...     price=Decimal("0.5200"),
        ...     position_id=123
        ... )
    """
    query = """
        INSERT INTO trades (
            market_id, strategy_id, model_id,
            side, quantity, price,
            position_id, order_type,
            trade_metadata, execution_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING trade_id
    """

    params = (
        market_id, strategy_id, model_id,
        side, quantity, price,
        position_id, order_type,
        trade_metadata
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result['trade_id']


def get_trades_by_market(
    market_id: str,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get all trades for a specific market.

    Args:
        market_id: Market to query
        limit: Maximum number of trades (default: 100)

    Returns:
        List of trades, newest first

    Example:
        >>> trades = get_trades_by_market(market_id=42, limit=20)
        >>> for trade in trades:
        ...     print(trade['side'], trade['quantity'], trade['price'])
    """
    query = """
        SELECT t.*, m.ticker
        FROM trades t
        JOIN markets m ON t.market_id = m.market_id
        WHERE t.market_id = %s
          AND m.row_current_ind = TRUE
        ORDER BY t.execution_time DESC
        LIMIT %s
    """
    return fetch_all(query, (market_id, limit))


def get_recent_trades(
    strategy_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get recent trades across all markets.

    Args:
        strategy_id: Filter by strategy version (optional)
        limit: Maximum number of trades (default: 100)

    Returns:
        List of recent trades, newest first

    Example:
        >>> recent = get_recent_trades(limit=50)
        >>> strategy_trades = get_recent_trades(strategy_id=1, limit=50)
    """
    query = """
        SELECT t.*, m.ticker, s.strategy_name, pm.model_name
        FROM trades t
        JOIN markets m ON t.market_id = m.market_id
        JOIN strategies s ON t.strategy_id = s.strategy_id
        JOIN probability_models pm ON t.model_id = pm.model_id
        WHERE m.row_current_ind = TRUE
    """
    params = []

    if strategy_id:
        query += " AND t.strategy_id = %s"
        params.append(strategy_id)

    query += " ORDER BY t.execution_time DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))
