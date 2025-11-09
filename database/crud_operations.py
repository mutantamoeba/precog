"""
CRUD operations for Precog database with SCD Type 2 versioning support.

SCD Type 2 (Slowly Changing Dimension) Explained:
--------------------------------------------------
Imagine a Wikipedia article with full edit history. Instead of OVERWRITING the article
(losing the old version), Wikipedia saves each edit as a new version. You can:
- View the current version (what users see now)
- View historical versions (what it looked like on 2023-05-15)
- Compare changes between versions

We do the SAME thing for markets and positions:

**Traditional Database (Loses History):**
```sql
UPDATE markets SET yes_price = 0.5500 WHERE ticker = 'NFL-KC-YES'
-- ❌ Old price (0.5200) is GONE FOREVER
-- ❌ Can't backtest strategies with historical prices
-- ❌ Can't audit "what price did we see at 2PM yesterday?"
```

**SCD Type 2 (Preserves History):**
```sql
-- Step 1: Mark current row as historical
UPDATE markets SET row_current_ind = FALSE, row_end_ts = NOW()
WHERE ticker = 'NFL-KC-YES' AND row_current_ind = TRUE

-- Step 2: Insert new version
INSERT INTO markets (..., row_current_ind = TRUE, row_start_ts = NOW())
VALUES ('NFL-KC-YES', 0.5500, ...)
-- ✅ Old price (0.5200) preserved with timestamps
-- ✅ Can backtest with exact historical prices
-- ✅ Full audit trail for compliance
```

Visual Example - Market Price History:
```
┌────────────┬──────────┬─────────────────────┬─────────────────────┬────────────────┐
│ market_id  │yes_price │ row_start_ts        │ row_end_ts          │row_current_ind │
├────────────┼──────────┼─────────────────────┼─────────────────────┼────────────────┤
│  42        │ 0.5200   │ 2024-01-01 10:00:00 │ 2024-01-01 11:00:00 │ FALSE (old)    │
│  42        │ 0.5350   │ 2024-01-01 11:00:00 │ 2024-01-01 13:00:00 │ FALSE (old)    │
│  42        │ 0.5500   │ 2024-01-01 13:00:00 │ NULL                │ TRUE (current) │
└────────────┴──────────┴─────────────────────┴─────────────────────┴────────────────┘

Query for CURRENT price:
    SELECT * FROM markets WHERE market_id = 42 AND row_current_ind = TRUE
    → Returns 0.5500 (latest version only)

Query for HISTORICAL prices:
    SELECT * FROM markets WHERE market_id = 42 ORDER BY row_start_ts
    → Returns all 3 versions (complete price history)
```

Why This Matters for Trading:
------------------------------
**1. Backtesting Accuracy**
   - Test strategies against EXACT historical prices (not approximations)
   - Know "what price did the API show at 2:15:37 PM on Game Day?"
   - Reproduce trading decisions with 100% accuracy

**2. Compliance & Auditing**
   - SEC/regulatory requirement: "Why did you execute this trade?"
   - Answer: "Market showed 0.5200 at 14:15:37, our model predicted 0.5700, edge = 0.0500"
   - Prove it with immutable database records

**3. Trade Attribution**
   - Every trade links to EXACT strategy version (v1.0, v1.1, v2.0)
   - A/B testing: "Did strategy v1.1 perform better than v1.0?"
   - Know EXACTLY which config generated each trade

**4. Position Monitoring**
   - Track unrealized P&L changes over time
   - Know when trailing stop was triggered (exact price and timestamp)
   - Reconstruct "why did we exit at 0.5800 instead of 0.6000?"

**5. Debugging**
   - "Why didn't we enter this market?" → Check historical prices
   - "Did our price feed freeze?" → Check row timestamps
   - "When did this market close?" → Check status history

The row_current_ind Pattern (CRITICAL):
----------------------------------------
**ALWAYS query with row_current_ind = TRUE to get current data!**

```python
# ✅ CORRECT - Gets current market price only
current_market = db.execute('''
    SELECT * FROM markets
    WHERE ticker = %s
      AND row_current_ind = TRUE
''', ('NFL-KC-YES',))

# ❌ WRONG - Gets ALL versions (including historical)
all_versions = db.execute('''
    SELECT * FROM markets
    WHERE ticker = %s
''', ('NFL-KC-YES',))
# ^ This returns 50 historical rows! Your code will use RANDOM old price!
```

**Common Mistake:**
Forgetting `row_current_ind = TRUE` causes bugs where code uses stale prices
from 3 days ago instead of current market price. ALWAYS filter by row_current_ind!

**When to query historical versions:**
```python
# Get price history for charting
history = db.execute('''
    SELECT yes_price, row_start_ts, row_end_ts
    FROM markets
    WHERE ticker = %s
    ORDER BY row_start_ts DESC
    LIMIT 100
''', ('NFL-KC-YES',))
```

Performance Implications:
-------------------------
**Storage Cost:**
- Each price update creates NEW row (not UPDATE)
- 1000 price updates per day = 1000 rows (vs 1 row with UPDATE)
- PostgreSQL handles this efficiently with indexes
- Typical size: ~500 bytes/row → 500 KB/day per active market
- For 100 active markets: ~50 MB/day (negligible)

**Query Performance:**
- `WHERE row_current_ind = TRUE` uses BTREE index (fast: <1ms)
- Historical queries may scan more rows (add LIMIT to prevent full table scan)
- Vacuum regularly to reclaim space from old versions

**When to use SCD Type 2:**
- ✅ Markets (prices change frequently, need audit trail)
- ✅ Positions (track unrealized P&L changes, trailing stops)
- ✅ Account Balance (track deposits/withdrawals/P&L)
- ❌ Strategies (use immutable versioning instead - see versioning guide)
- ❌ Probability Models (use immutable versioning instead)

Trade Attribution Pattern:
--------------------------
**EVERY trade MUST link to exact strategy and model versions:**

```python
# ✅ CORRECT - Full attribution
trade = create_trade(
    market_id=42,
    strategy_id=1,   # Links to strategies.strategy_id (v1.0)
    model_id=2,      # Links to probability_models.model_id (v2.1)
    quantity=100,
    price=Decimal("0.5200")
)

# Later: Analyze which strategy version performed best
performance = db.execute('''
    SELECT s.strategy_version, AVG(t.realized_pnl) as avg_pnl
    FROM trades t
    JOIN strategies s ON t.strategy_id = s.strategy_id
    GROUP BY s.strategy_version
    ORDER BY avg_pnl DESC
''')
# Output: v1.1 = +$4.50/trade, v1.0 = +$2.10/trade
# Conclusion: v1.1 is 2x better! Keep using it.
```

**Why immutable strategy versions matter:**
If we allowed modifying strategy configs, we'd lose ability to attribute performance.
Example: Strategy v1.0 config changes from `min_edge=0.05` to `min_edge=0.10`.
Now we can't tell which trades used which config! Solution: Create v1.1 instead.

Security - SQL Injection Prevention:
------------------------------------
**ALL functions use parameterized queries:**

```python
# ✅ CORRECT - Safe from SQL injection
ticker = user_input  # Could be malicious: "'; DROP TABLE markets; --"
result = db.execute(
    "SELECT * FROM markets WHERE ticker = %s",
    (ticker,)  # PostgreSQL escapes this safely
)

# ❌ WRONG - SQL injection vulnerability
query = f"SELECT * FROM markets WHERE ticker = '{ticker}'"
# ^ If ticker = "'; DROP TABLE markets; --" → DELETES ALL DATA!
```

**Key principle:** NEVER concatenate user input into SQL strings.
ALWAYS use parameterized queries with %s placeholders.

Common Operations Cheat Sheet:
------------------------------
```python
# Create new market
market_id = create_market(
    platform_id="kalshi",
    ticker="NFL-KC-YES",
    yes_price=Decimal("0.5200"),
    no_price=Decimal("0.4800")
)

# Get current market data
market = get_current_market("NFL-KC-YES")  # Returns latest version only

# Update market price (creates new version)
new_id = update_market_with_versioning(
    ticker="NFL-KC-YES",
    yes_price=Decimal("0.5500")
)
# Old version: row_current_ind = FALSE (preserved)
# New version: row_current_ind = TRUE (active)

# Get price history for backtesting
history = get_market_history("NFL-KC-YES", limit=100)
# Returns all versions ordered by newest first

# Create position
pos_id = create_position(
    market_id=42,
    strategy_id=1,
    model_id=2,
    side='YES',
    quantity=100,
    entry_price=Decimal("0.5200")
)

# Update position price (monitoring)
update_position_price(
    position_id=pos_id,
    current_price=Decimal("0.5800"),
    trailing_stop_state={"peak": "0.5800", "stop": "0.5500"}
)

# Close position
close_position(
    position_id=pos_id,
    exit_price=Decimal("0.6000"),
    exit_reason='target_hit',
    realized_pnl=Decimal("8.00")
)

# Record trade with attribution
trade_id = create_trade(
    market_id=42,
    strategy_id=1,  # Which strategy version generated this?
    model_id=2,     # Which model version predicted probability?
    side='YES',
    quantity=100,
    price=Decimal("0.5200")
)
```

Reference: docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
Related Requirements: REQ-DB-003 (SCD Type 2 Versioning)
Related ADR: ADR-019 (Historical Data Versioning Strategy)
Related Guide: docs/guides/VERSIONING_GUIDE_V1.0.md
"""

from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor

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
    market_type: str = "binary",
    status: str = "open",
    volume: int | None = None,
    open_interest: int | None = None,
    spread: Decimal | None = None,
    metadata: dict | None = None,
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
        market_id,
        platform_id,
        event_id,
        external_id,
        ticker,
        title,
        market_type,
        yes_price,
        no_price,
        status,
        volume,
        open_interest,
        spread,
        metadata,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("str", result["market_id"])


def get_current_market(ticker: str) -> dict[str, Any] | None:
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
    yes_price: Decimal | None = None,
    no_price: Decimal | None = None,
    status: str | None = None,
    volume: int | None = None,
    open_interest: int | None = None,
    market_metadata: dict | None = None,
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
        msg = f"Market not found: {ticker}"
        raise ValueError(msg)

    # Use new values or fall back to current
    new_yes_price = yes_price if yes_price is not None else current["yes_price"]
    new_no_price = no_price if no_price is not None else current["no_price"]
    new_status = status if status is not None else current["status"]
    new_volume = volume if volume is not None else current["volume"]
    new_open_interest = open_interest if open_interest is not None else current["open_interest"]
    new_metadata = market_metadata if market_metadata is not None else current["metadata"]

    with get_cursor(commit=True) as cur:
        # Step 1: Mark current row as historical
        cur.execute(
            """
            UPDATE markets
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE ticker = %s
              AND row_current_ind = TRUE
        """,
            (ticker,),
        )

        # Step 2: Insert new version
        cur.execute(
            """
            INSERT INTO markets (
                market_id, platform_id, event_id, external_id,
                ticker, title, market_type,
                yes_price, no_price, status,
                volume, open_interest, spread,
                metadata, row_current_ind, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            RETURNING market_id
        """,
            (
                current["market_id"],
                current["platform_id"],
                current["event_id"],
                current["external_id"],
                ticker,
                current["title"],
                current["market_type"],
                new_yes_price,
                new_no_price,
                new_status,
                new_volume,
                new_open_interest,
                current["spread"],
                new_metadata,
            ),
        )

        result = cur.fetchone()
        return cast("int", result["market_id"])


def get_market_history(ticker: str, limit: int = 100) -> list[dict[str, Any]]:
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
    target_price: Decimal | None = None,
    stop_loss_price: Decimal | None = None,
    trailing_stop_state: dict | None = None,
    position_metadata: dict | None = None,
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
        market_id,
        strategy_id,
        model_id,
        side,
        quantity,
        entry_price,
        target_price,
        stop_loss_price,
        trailing_stop_state,
        position_metadata,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["position_id"])


def get_current_positions(
    status: str | None = None, market_id: int | None = None
) -> list[dict[str, Any]]:
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
    params: list[Any] = []

    if status:
        query += " AND p.status = %s"
        params.append(status)

    if market_id:
        query += " AND p.market_id = %s"
        params.append(market_id)

    query += " ORDER BY p.entry_time DESC"

    return fetch_all(query, tuple(params) if params else None)


def update_position_price(
    position_id: int, current_price: Decimal, trailing_stop_state: dict | None = None
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
        "SELECT * FROM positions WHERE position_id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    new_trailing_stop = (
        trailing_stop_state if trailing_stop_state is not None else current["trailing_stop_state"]
    )

    with get_cursor(commit=True) as cur:
        # Mark current as historical
        cur.execute(
            """
            UPDATE positions
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE position_id = %s
              AND row_current_ind = TRUE
        """,
            (position_id,),
        )

        # Insert new version with updated price
        cur.execute(
            """
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
        """,
            (
                current["market_id"],
                current["strategy_id"],
                current["model_id"],
                current["side"],
                current["quantity"],
                current["entry_price"],
                current_price,
                (current_price - current["entry_price"]) * current["quantity"],  # unrealized_pnl
                current["target_price"],
                current["stop_loss_price"],
                new_trailing_stop,
                current["position_metadata"],
                current["status"],
                current["entry_time"],
            ),
        )

        result = cur.fetchone()
        return cast("int", result["position_id"])


def close_position(
    position_id: int, exit_price: Decimal, exit_reason: str, realized_pnl: Decimal
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
        "SELECT * FROM positions WHERE position_id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    with get_cursor(commit=True) as cur:
        # Mark current as historical
        cur.execute(
            """
            UPDATE positions
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE position_id = %s
              AND row_current_ind = TRUE
        """,
            (position_id,),
        )

        # Insert closed version
        cur.execute(
            """
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
        """,
            (
                current["market_id"],
                current["strategy_id"],
                current["model_id"],
                current["side"],
                current["quantity"],
                current["entry_price"],
                exit_price,
                realized_pnl,
                current["target_price"],
                current["stop_loss_price"],
                current["trailing_stop_state"],
                current["position_metadata"],
                current["entry_time"],
            ),
        )

        result = cur.fetchone()
        return cast("int", result["position_id"])


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
    position_id: int | None = None,
    order_type: str = "market",
    trade_metadata: dict | None = None,
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
        market_id,
        strategy_id,
        model_id,
        side,
        quantity,
        price,
        position_id,
        order_type,
        trade_metadata,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["trade_id"])


def get_trades_by_market(market_id: str, limit: int = 100) -> list[dict[str, Any]]:
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


def get_recent_trades(strategy_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
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


# =============================================================================
# Account Balance Operations (SCD Type 2)
# =============================================================================


def create_account_balance(
    platform_id: str,
    balance: Decimal,
    currency: str = "USD",
) -> int | None:
    """
    Create new account balance snapshot with row_current_ind = TRUE.

    Account balance uses SCD Type 2 versioning to track balance changes over time.
    Each balance fetch creates a new snapshot.

    Args:
        platform_id: Foreign key to platforms table (e.g., "kalshi")
        balance: Account balance as DECIMAL(10,4) - NEVER use float!
        currency: Currency code (default: "USD")

    Returns:
        balance_id of newly created record

    Raises:
        ValueError: If balance is float (not Decimal)
        psycopg2.Error: If database operation fails

    Educational Note:
        Account balance stored as DECIMAL(10,4) for exact precision.
        NEVER use float for financial calculations!

        Why this matters:
        - Float arithmetic introduces rounding errors
        - Example: float(1234.5678) + float(0.0001) may not equal 1234.5679
        - Decimal: Decimal("1234.5678") + Decimal("0.0001") = Decimal("1234.5679") ✅

        SCD Type 2 Pattern:
        - Every balance fetch creates NEW row with row_current_ind=TRUE
        - Enables balance history tracking without losing data
        - Query current balance: WHERE row_current_ind = TRUE

    Example:
        >>> from decimal import Decimal
        >>> balance_id = create_account_balance(
        ...     platform_id="kalshi",
        ...     balance=Decimal("1234.5678"),
        ...     currency="USD"
        ... )
        >>> print(balance_id)  # 42

        >>> # ❌ WRONG - Float contamination
        >>> balance = 1234.5678  # float type
        >>> # Will raise ValueError

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - ADR-002: Decimal-Only Financial Calculations
        - Pattern 1 in CLAUDE.md: Decimal Precision
        - Pattern 2 in CLAUDE.md: SCD Type 2 Versioning
    """
    if not isinstance(balance, Decimal):
        raise ValueError(f"Balance must be Decimal, got {type(balance).__name__}")

    query = """
        INSERT INTO account_balance (
            platform_id, balance, currency, row_current_ind, created_at
        )
        VALUES (%s, %s, %s, TRUE, NOW())
        RETURNING balance_id
    """

    params = (platform_id, balance, currency)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result[0] if result else None


def update_account_balance_with_versioning(
    platform_id: str,
    new_balance: Decimal,
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
        currency: Currency code (default: "USD")

    Returns:
        balance_id of newly created record

    Raises:
        ValueError: If new_balance is float (not Decimal)

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
        - Query: "What was my balance on 2024-01-15?" → Filter by created_at
        - Query: "How has balance changed this month?" → Aggregate by day
        - Query: "Current balance?" → WHERE row_current_ind=TRUE

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

    # Step 1: Mark current balance as historical (row_current_ind = FALSE)
    update_query = """
        UPDATE account_balance
        SET row_current_ind = FALSE
        WHERE platform_id = %s AND row_current_ind = TRUE
    """

    # Step 2: Insert new balance record
    insert_query = """
        INSERT INTO account_balance (
            platform_id, balance, currency, row_current_ind, created_at
        )
        VALUES (%s, %s, %s, TRUE, NOW())
        RETURNING balance_id
    """

    with get_cursor(commit=True) as cur:
        # Mark old balance as historical
        cur.execute(update_query, (platform_id,))

        # Insert new balance
        cur.execute(insert_query, (platform_id, new_balance, currency))
        result = cur.fetchone()
        return result[0] if result else None


# =============================================================================
# Settlement Operations (Append-Only)
# =============================================================================


def create_settlement(
    market_id: str,
    platform_id: str,
    outcome: str,
    payout: Decimal,
) -> int | None:
    """
    Create settlement record for a resolved market.

    Settlements are append-only (no versioning) because they are final.
    Once a market settles, the outcome and payout never change.

    Args:
        market_id: Foreign key to markets table
        platform_id: Foreign key to platforms table
        outcome: Settlement outcome ("yes", "no", or other)
        payout: Payout amount as DECIMAL(10,4)

    Returns:
        settlement_id of newly created record

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
        ...     market_id="MKT-NFL-KC-YES",
        ...     platform_id="kalshi",
        ...     outcome="yes",
        ...     payout=Decimal("1.0000")  # $1.00 per contract
        ... )

        >>> # Market resolved NO, YES position pays $0
        >>> settlement_id = create_settlement(
        ...     market_id="MKT-NFL-BUF-YES",
        ...     platform_id="kalshi",
        ...     outcome="no",
        ...     payout=Decimal("0.0000")  # Worthless
        ... )

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - Pattern 1 in CLAUDE.md: Decimal Precision
        - Settlements table schema: database/DATABASE_SCHEMA_SUMMARY_V1.7.md
    """
    if not isinstance(payout, Decimal):
        raise ValueError(f"Payout must be Decimal, got {type(payout).__name__}")

    query = """
        INSERT INTO settlements (
            market_id, platform_id, outcome, payout, created_at
        )
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING settlement_id
    """

    params = (market_id, platform_id, outcome, payout)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result[0] if result else None
