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
    -> Returns 0.5500 (latest version only)

Query for HISTORICAL prices:
    SELECT * FROM markets WHERE market_id = 42 ORDER BY row_start_ts
    -> Returns all 3 versions (complete price history)
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
   - "Why didn't we enter this market?" -> Check historical prices
   - "Did our price feed freeze?" -> Check row timestamps
   - "When did this market close?" -> Check status history

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
- Typical size: ~500 bytes/row -> 500 KB/day per active market
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
# ^ If ticker = "'; DROP TABLE markets; --" -> DELETES ALL DATA!
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

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, cast

from .connection import fetch_all, fetch_one, get_cursor

# Type alias for execution environment - matches database ENUM (Migration 0008)
# - 'live': Production trading with Kalshi Production API (real money)
# - 'paper': Integration testing with Kalshi Demo/Sandbox API (no real money)
# - 'backtest': Historical data simulation (no API calls)
ExecutionEnvironment = Literal["live", "paper", "backtest"]


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts Decimal to string.

    This encoder is required because Python's json module doesn't natively
    support Decimal serialization. We convert Decimal to string to preserve
    precision (Pattern 1: NEVER USE FLOAT).

    Educational Note:
        Why not convert to float? Because float introduces rounding errors!
        Example:
            Decimal("0.4975") -> float -> 0.49750000000000005 ❌ WRONG
            Decimal("0.4975") -> str -> "0.4975" ✅ CORRECT

    Example:
        >>> config = {"max_edge": Decimal("0.05"), "kelly_fraction": Decimal("0.10")}
        >>> json.dumps(config, cls=DecimalEncoder)
        '{"max_edge": "0.05", "kelly_fraction": "0.10"}'

    Reference:
        - Pattern 1 (Decimal Precision): docs/guides/DEVELOPMENT_PATTERNS_V1.2.md
        - ADR-002: Decimal precision for all financial calculations
    """

    def default(self, obj: Any) -> Any:
        """Convert Decimal to string, otherwise use default encoding.

        Args:
            obj: Object to encode

        Returns:
            String representation for Decimal, default encoding for others
        """
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def _convert_config_strings_to_decimal(config: dict[str, Any]) -> dict[str, Any]:
    """Convert string values to Decimal for known financial fields.

    When configs are stored as JSON in the database, Decimal values are
    serialized as strings. This helper converts them back to Decimal objects
    for fields that should use Decimal precision (Pattern 1).

    Educational Note:
        We only convert specific known fields (max_edge, kelly_fraction, etc.)
        rather than converting all numeric-looking strings, because some
        fields like 'min_lead' should remain as integers.

    Args:
        config: Strategy config dict (may have string Decimal values)

    Returns:
        Config dict with Decimal values restored

    Example:
        >>> config = {"max_edge": "0.05", "kelly_fraction": "0.10", "min_lead": 5}
        >>> _convert_config_strings_to_decimal(config)
        {"max_edge": Decimal("0.05"), "kelly_fraction": Decimal("0.10"), "min_lead": 5}

    Reference:
        - Pattern 1 (Decimal Precision): docs/guides/DEVELOPMENT_PATTERNS_V1.2.md
        - ADR-002: Decimal precision for all financial calculations
    """
    # Fields that should be Decimal (financial calculations)
    decimal_fields = {
        "max_edge",
        "min_edge",
        "kelly_fraction",
        "max_position_size",
        "max_exposure",
        "stop_loss_threshold",
        "profit_target",
        "trailing_stop_activation",
        "trailing_stop_distance",
    }

    result = config.copy()
    for field in decimal_fields:
        if field in result and isinstance(result[field], str):
            result[field] = Decimal(result[field])

    return result


# =============================================================================
# TYPE VALIDATION HELPERS
# =============================================================================


def validate_decimal(value: Any, param_name: str) -> Decimal:
    """
    Validate that value is a Decimal type (runtime type enforcement).

    Args:
        value: Value to validate
        param_name: Parameter name for error message

    Returns:
        The value if it's a Decimal

    Raises:
        TypeError: If value is not a Decimal

    Educational Note:
        Python type hints (e.g., `price: Decimal`) are annotations only.
        They provide IDE autocomplete and mypy static analysis, but do NOT
        enforce types at runtime.

        Without runtime validation:
        >>> create_market(yes_price=0.5)  # ✅ Executes (float contamination!)

        With runtime validation:
        >>> create_market(yes_price=0.5)  # ❌ TypeError: yes_price must be Decimal

        Why this matters:
        - Prevents float contamination (0.5 != Decimal("0.5"))
        - Ensures sub-penny precision preserved (0.4975 stored exactly)
        - Catches type errors early (at function call, not database INSERT)

    Example:
        >>> price = validate_decimal(Decimal("0.5200"), "yes_price")
        >>> # ✅ Returns Decimal("0.5200")

        >>> price = validate_decimal(0.5200, "yes_price")
        >>> # ❌ TypeError: yes_price must be Decimal, got float
        >>> #    Use Decimal("0.5200"), not 0.5200
    """
    if not isinstance(value, Decimal):
        raise TypeError(
            f"{param_name} must be Decimal, got {type(value).__name__}. "
            f"Use Decimal('{value}'), not {value} ({type(value).__name__}). "
            f"See Pattern 1 in CLAUDE.md for Decimal precision guidance."
        )
    return value


# =============================================================================
# SERIES OPERATIONS
# =============================================================================


def get_series(series_id: str) -> dict[str, Any] | None:
    """
    Get a series by series_id.

    Series represent recurring market groups (e.g., "NFL Game Markets" contains
    all individual game betting markets). This is the first level in the
    Kalshi hierarchy: Series → Events → Markets.

    Args:
        series_id: The series identifier (primary key, e.g., "KXNFLGAME")

    Returns:
        Dict containing series data if found, None otherwise.
        Keys: series_id, platform_id, external_id, category, subcategory,
              title, frequency, tags, metadata, created_at, updated_at

    Example:
        >>> series = get_series("KXNFLGAME")
        >>> if series:
        ...     print(f"Found: {series['title']}")
        ...     print(f"Tags: {series['tags']}")  # ['Football']
        ... else:
        ...     print("Series not found")

    Educational Note:
        The series table stores metadata about market groups from Kalshi's API.
        The `tags` column (TEXT[]) is particularly useful for sport filtering:
        - ["Football"] → NFL, NCAAF
        - ["Basketball"] → NBA, NCAAB, NCAAW
        - ["Hockey"] → NHL

        Using PostgreSQL arrays with GIN index enables efficient queries:
        SELECT * FROM series WHERE 'Football' = ANY(tags)

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
        - src/precog/api_connectors/kalshi_client.py (get_series, get_sports_series)
    """
    query = """
        SELECT series_id, platform_id, external_id, category, subcategory,
               title, frequency, tags, metadata, created_at, updated_at
        FROM series
        WHERE series_id = %s
    """
    with get_cursor() as cur:
        cur.execute(query, (series_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_series(
    platform_id: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    List series with optional filtering and pagination.

    Retrieves series records with support for filtering by platform, category,
    and tags. Results are paginated for efficient querying of large datasets.

    Args:
        platform_id: Filter by platform (e.g., 'kalshi')
        category: Filter by category (e.g., 'sports', 'politics')
        tags: Filter by tags - series must contain ALL specified tags
        limit: Maximum number of results (default: 100, max: 1000)
        offset: Number of records to skip for pagination (default: 0)

    Returns:
        List of series dicts. Empty list if no matches.

    Example:
        >>> # Get all sports series
        >>> sports = list_series(category='sports', limit=50)
        >>> print(f"Found {len(sports)} sports series")

        >>> # Get all NFL-related series using tags
        >>> nfl = list_series(tags=['Football'])
        >>> for s in nfl:
        ...     print(f"{s['series_id']}: {s['title']}")

        >>> # Paginate through results
        >>> page1 = list_series(limit=100, offset=0)
        >>> page2 = list_series(limit=100, offset=100)

    Educational Note:
        Pagination is critical for API modules that may return large datasets.
        Using LIMIT/OFFSET allows clients to:
        1. Fetch data in manageable chunks (reduces memory usage)
        2. Implement infinite scroll or page-based navigation
        3. Avoid timeouts on large result sets

        The tags filter uses PostgreSQL's array containment operator (@>):
        WHERE tags @> ARRAY['Football'] means "tags contains 'Football'"

    Reference:
        - PostgreSQL array operators: https://www.postgresql.org/docs/current/functions-array.html
    """
    # Validate limit
    if limit > 1000:
        limit = 1000
    if limit < 1:
        limit = 1

    # Build query with optional filters
    conditions = []
    params: list[Any] = []

    if platform_id:
        conditions.append("platform_id = %s")
        params.append(platform_id)

    if category:
        conditions.append("category = %s")
        params.append(category)

    if tags:
        # Use array containment: tags must contain ALL specified tags
        conditions.append("tags @> %s")
        params.append(tags)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT series_id, platform_id, external_id, category, subcategory,
               title, frequency, tags, metadata, created_at, updated_at
        FROM series
        {where_clause}
        ORDER BY series_id
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def create_series(
    series_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    subcategory: str | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> str:
    """
    Create a new series record.

    Series are the top-level grouping in Kalshi's market hierarchy:
    Series → Events → Markets. Each series represents a category of
    related markets (e.g., "NFL Game Markets" or "Presidential Election").

    Args:
        series_id: Unique series identifier (primary key, e.g., "KXNFLGAME")
        platform_id: Foreign key to platforms table (e.g., 'kalshi')
        external_id: External ID from the platform API
        category: Series category - one of: 'sports', 'politics',
                  'entertainment', 'economics', 'weather', 'other'
        title: Human-readable series title
        subcategory: Optional subcategory (e.g., 'nfl', 'nba')
        frequency: Optional frequency - one of: 'daily', 'weekly', 'monthly', 'event', 'once'
        tags: Optional list of tags for filtering (e.g., ['Football'])
        metadata: Optional additional metadata as JSONB

    Returns:
        series_id of the created series

    Raises:
        psycopg2.IntegrityError: If series_id already exists or platform_id invalid

    Example:
        >>> series_id = create_series(
        ...     series_id="KXNFLGAME",
        ...     platform_id="kalshi",
        ...     external_id="KXNFLGAME",
        ...     category="sports",
        ...     title="NFL Game Markets",
        ...     subcategory="nfl",
        ...     frequency="recurring",
        ...     tags=["Football"]
        ... )
        >>> print(f"Created series: {series_id}")

    Educational Note:
        The category CHECK constraint ensures data integrity at the database
        level. PostgreSQL will reject invalid categories before the data is
        even inserted, preventing corrupted records.

        Tags stored as TEXT[] (PostgreSQL array) enable efficient filtering
        with the ANY() operator and GIN indexes:
        SELECT * FROM series WHERE 'Football' = ANY(tags)

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
        - Migration 0010: Added tags column with GIN index
    """
    query = """
        INSERT INTO series (
            series_id, platform_id, external_id, category, subcategory,
            title, frequency, tags, metadata, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING series_id
    """

    params = (
        series_id,
        platform_id,
        external_id,
        category,
        subcategory,
        title,
        frequency,
        tags,  # PostgreSQL handles list -> TEXT[] conversion
        json.dumps(metadata) if metadata else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("str", result["series_id"])


def update_series(
    series_id: str,
    title: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> bool:
    """
    Update an existing series record.

    Updates only the fields that are provided (not None). This allows
    partial updates without affecting other fields.

    Args:
        series_id: The series to update
        title: New title (optional)
        category: New category (optional)
        subcategory: New subcategory (optional)
        frequency: New frequency (optional)
        tags: New tags list (optional) - replaces existing tags
        metadata: New metadata (optional) - replaces existing metadata

    Returns:
        True if series was updated, False if series not found

    Example:
        >>> # Update tags only
        >>> updated = update_series("KXNFLGAME", tags=["Football", "NFL"])
        >>> if updated:
        ...     print("Tags updated!")

        >>> # Update multiple fields
        >>> updated = update_series(
        ...     "KXNFLGAME",
        ...     title="NFL Regular Season Games",
        ...     frequency="recurring"
        ... )

    Educational Note:
        This function builds a dynamic UPDATE query based on provided fields.
        This pattern is common for REST PATCH operations where clients only
        send the fields they want to change.

        Alternative approach: Always update all fields (simpler but overwrites
        unchanged fields with stale values if client doesn't fetch first).

    Reference: REQ-DATA-001 (Data Integrity)
    """
    # Build SET clause dynamically
    set_clauses = ["updated_at = NOW()"]
    params: list[Any] = []

    if title is not None:
        set_clauses.append("title = %s")
        params.append(title)

    if category is not None:
        set_clauses.append("category = %s")
        params.append(category)

    if subcategory is not None:
        set_clauses.append("subcategory = %s")
        params.append(subcategory)

    if frequency is not None:
        set_clauses.append("frequency = %s")
        params.append(frequency)

    if tags is not None:
        set_clauses.append("tags = %s")
        params.append(tags)

    if metadata is not None:
        set_clauses.append("metadata = %s")
        params.append(json.dumps(metadata))

    # Add series_id for WHERE clause
    params.append(series_id)

    # S608 false positive: set_clauses are hardcoded column names, not user input
    query = f"""
        UPDATE series
        SET {", ".join(set_clauses)}
        WHERE series_id = %s
    """  # noqa: S608

    with get_cursor(commit=True) as cur:
        cur.execute(query, tuple(params))
        return cast("bool", cur.rowcount > 0)


def get_or_create_series(
    series_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    subcategory: str | None = None,
    frequency: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
    update_if_exists: bool = True,
) -> tuple[str, bool]:
    """
    Get an existing series or create it if it doesn't exist.

    This upsert pattern is essential for polling services that repeatedly
    fetch data from external APIs. When the same series appears in multiple
    API responses, this function ensures we don't fail on duplicate inserts.

    Args:
        series_id: Unique series identifier
        platform_id: Platform foreign key
        external_id: External API identifier
        category: Series category
        title: Series title
        subcategory: Optional subcategory
        frequency: Optional frequency
        tags: Optional tags list
        metadata: Optional metadata
        update_if_exists: If True, update existing series with new data (default: True)

    Returns:
        Tuple of (series_id, created) where created is True if series was
        newly created, False if it already existed.

    Example:
        >>> series_id, created = get_or_create_series(
        ...     series_id="KXNFLGAME",
        ...     platform_id="kalshi",
        ...     external_id="KXNFLGAME",
        ...     category="sports",
        ...     title="NFL Game Markets",
        ...     tags=["Football"]
        ... )
        >>> if created:
        ...     print(f"Created new series: {series_id}")
        ... else:
        ...     print(f"Series already exists: {series_id}")

    Educational Note:
        This pattern is critical for the KalshiPoller service. When syncing
        series data before markets, the poller calls get_or_create_series()
        for each series returned by the API. This ensures:
        1. New series are created automatically
        2. Existing series are optionally updated with fresh data
        3. No duplicate insert errors occur

        The update_if_exists flag allows the caller to control whether
        existing records should be refreshed with API data. Set to False
        if you only want to create missing records without modifying existing.

    Reference:
        - src/precog/schedulers/kalshi_poller.py
        - Pattern similar to get_or_create_event()
    """
    # Check if series already exists
    existing = get_series(series_id)

    if existing is not None:
        # Optionally update with new data
        if update_if_exists:
            update_series(
                series_id=series_id,
                title=title,
                category=category,
                subcategory=subcategory,
                frequency=frequency,
                tags=tags,
                metadata=metadata,
            )
        return series_id, False

    # Create new series
    create_series(
        series_id=series_id,
        platform_id=platform_id,
        external_id=external_id,
        category=category,
        title=title,
        subcategory=subcategory,
        frequency=frequency,
        tags=tags,
        metadata=metadata,
    )
    return series_id, True


# =============================================================================
# EVENT OPERATIONS
# =============================================================================


def get_event(event_id: str) -> dict[str, Any] | None:
    """
    Get an event by event_id.

    Args:
        event_id: The event identifier (primary key)

    Returns:
        Dictionary with event data, or None if not found

    Example:
        >>> event = get_event("KXNFL-24DEC22-KC-SEA")
        >>> if event:
        ...     print(event['title'])
    """
    query = """
        SELECT *
        FROM events
        WHERE event_id = %s
    """
    return fetch_one(query, (event_id,))


def create_event(
    event_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    series_id: str | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> str:
    """
    Create a new event record.

    Events are the parent entities for markets. Each market belongs to an event,
    enforced via foreign key constraint (markets.event_id -> events.event_id).

    Args:
        event_id: Unique event identifier (primary key)
        platform_id: Foreign key to platforms table (e.g., 'kalshi')
        external_id: External ID from the platform API
        category: Event category ('sports', 'politics', 'entertainment',
                  'economics', 'weather', 'other')
        title: Event title/description
        series_id: Optional foreign key to series table
        subcategory: Optional subcategory (e.g., 'nfl', 'nba')
        description: Optional detailed description
        start_time: Optional event start time (ISO format)
        end_time: Optional event end time (ISO format)
        status: Optional status ('scheduled', 'live', 'final', 'cancelled', 'postponed')
        metadata: Optional additional metadata as JSONB

    Returns:
        event_id of the created event

    Raises:
        psycopg2.IntegrityError: If event_id already exists or platform_id invalid

    Example:
        >>> event_id = create_event(
        ...     event_id="KXNFL-24DEC22-KC-SEA",
        ...     platform_id="kalshi",
        ...     external_id="KXNFL-24DEC22-KC-SEA",
        ...     category="sports",
        ...     title="Chiefs vs Seahawks - Dec 22, 2024",
        ...     subcategory="nfl"
        ... )

    Educational Note:
        Events represent real-world occurrences (games, elections, etc.) that
        markets are based on. One event can have multiple markets:
        - Event: "Chiefs vs Seahawks - Dec 22"
        - Markets: "Chiefs to win", "Total points over 45.5", "Kelce 100+ yards"

        The foreign key constraint ensures data integrity - you can't create
        a market for a non-existent event.

    Reference: docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
    """
    query = """
        INSERT INTO events (
            event_id, platform_id, series_id, external_id,
            category, subcategory, title, description,
            start_time, end_time, status, metadata,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING event_id
    """

    params = (
        event_id,
        platform_id,
        series_id,
        external_id,
        category,
        subcategory,
        title,
        description,
        start_time,
        end_time,
        status,
        json.dumps(metadata) if metadata else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("str", result["event_id"])


def get_or_create_event(
    event_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    series_id: str | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> tuple[str, bool]:
    """
    Get an existing event or create it if it doesn't exist.

    This is a convenience function that combines get_event() and create_event()
    to handle the common pattern of "upsert" behavior for events.

    Args:
        event_id: Unique event identifier (primary key)
        platform_id: Foreign key to platforms table
        external_id: External ID from the platform API
        category: Event category
        title: Event title
        series_id: Optional series foreign key
        subcategory: Optional subcategory
        description: Optional description
        start_time: Optional start time
        end_time: Optional end time
        status: Optional status
        metadata: Optional metadata

    Returns:
        Tuple of (event_id, created) where created is True if event was
        newly created, False if it already existed.

    Example:
        >>> event_id, created = get_or_create_event(
        ...     event_id="KXNFL-24DEC22-KC-SEA",
        ...     platform_id="kalshi",
        ...     external_id="KXNFL-24DEC22-KC-SEA",
        ...     category="sports",
        ...     title="Chiefs vs Seahawks - Dec 22, 2024"
        ... )
        >>> if created:
        ...     print(f"Created new event: {event_id}")
        ... else:
        ...     print(f"Event already exists: {event_id}")

    Educational Note:
        This pattern is essential for polling services like KalshiMarketPoller.
        When polling API data, the same events appear repeatedly. This function
        ensures we don't attempt duplicate inserts (which would fail due to
        primary key constraint) while still creating new events when they appear.

    Reference: src/precog/schedulers/kalshi_poller.py
    """
    # Check if event already exists
    existing = get_event(event_id)
    if existing is not None:
        return event_id, False

    # Create new event
    create_event(
        event_id=event_id,
        platform_id=platform_id,
        external_id=external_id,
        category=category,
        title=title,
        series_id=series_id,
        subcategory=subcategory,
        description=description,
        start_time=start_time,
        end_time=end_time,
        status=status,
        metadata=metadata,
    )
    return event_id, True


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
    # Runtime type validation (enforces Decimal precision)
    yes_price = validate_decimal(yes_price, "yes_price")
    no_price = validate_decimal(no_price, "no_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")

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
        json.dumps(metadata) if metadata else None,
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
    # Runtime type validation (enforces Decimal precision)
    if yes_price is not None:
        yes_price = validate_decimal(yes_price, "yes_price")
    if no_price is not None:
        no_price = validate_decimal(no_price, "no_price")

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
                json.dumps(new_metadata) if new_metadata else None,
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
    # ⭐ ATTRIBUTION ARCHITECTURE (Migration 020) - NEW parameters
    calculated_probability: Decimal | None = None,
    market_price_at_entry: Decimal | None = None,
    # ⭐ EXECUTION ENVIRONMENT (Migration 0008, ADR-107) - NEW parameter
    execution_environment: ExecutionEnvironment = "live",
) -> int:
    """
    Create new position with status = 'open' and immutable entry-time attribution.

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
        calculated_probability: Model's predicted win probability at entry (immutable snapshot)
        market_price_at_entry: Kalshi market price at entry (immutable snapshot)
        execution_environment: Execution context - 'live' (production), 'paper' (demo),
            or 'backtest' (simulation). Default 'live'. See ADR-107.

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
        ...     market_id=42,
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
    # ⭐ Calculate edge_at_entry if both probability and price provided
    edge_at_entry: Decimal | None = None
    if calculated_probability is not None and market_price_at_entry is not None:
        edge_at_entry = calculated_probability - market_price_at_entry

    # Step 1: INSERT with placeholder position_id (will be updated immediately)
    insert_query = """
        INSERT INTO positions (
            position_id, market_id, strategy_id, model_id, side,
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
    market_id: str | None = None,
    execution_environment: ExecutionEnvironment | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get current positions (row_current_ind = TRUE) with pagination.

    Args:
        status: Filter by status ('open', 'closed', etc.)
        market_id: Filter by market_id
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
    # Get current version using surrogate id
    current = fetch_one(
        "SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    new_trailing_stop = (
        trailing_stop_state if trailing_stop_state is not None else current["trailing_stop_state"]
    )

    # ⭐ Early return optimization (Issue #113):
    # Skip SCD Type 2 versioning if no state actually changed.
    # This prevents 3600+ unnecessary writes/hour in monitoring loops.
    price_unchanged = current["current_price"] == current_price
    trailing_stop_unchanged = current["trailing_stop_state"] == new_trailing_stop
    if price_unchanged and trailing_stop_unchanged:
        # No state change - return existing id without creating new version
        return cast("int", current["id"])

    with get_cursor(commit=True) as cur:
        # Mark current as historical using surrogate id
        cur.execute(
            """
            UPDATE positions
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE id = %s
              AND row_current_ind = TRUE
        """,
            (position_id,),
        )

        # Insert new version with same position_id (business key) but new id (surrogate)
        cur.execute(
            """
            INSERT INTO positions (
                position_id, market_id, strategy_id, model_id, side,
                quantity, entry_price,
                current_price, unrealized_pnl,
                target_price, stop_loss_price,
                trailing_stop_state, position_metadata,
                status, entry_time, last_check_time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """,
            (
                current["position_id"],  # Copy business key from current version
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
        return cast("int", result["id"])  # Return new surrogate id


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
    # Get current version using surrogate id
    current = fetch_one(
        "SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE", (position_id,)
    )
    if not current:
        msg = f"Position not found: {position_id}"
        raise ValueError(msg)

    with get_cursor(commit=True) as cur:
        # Mark current as historical using surrogate id
        cur.execute(
            """
            UPDATE positions
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE id = %s
              AND row_current_ind = TRUE
        """,
            (position_id,),
        )

        # Insert closed version with same position_id (business key)
        # NOTE: execution_environment is preserved from original position
        cur.execute(
            """
            INSERT INTO positions (
                position_id, market_id, strategy_id, model_id, side,
                quantity, entry_price, exit_price, current_price,
                realized_pnl,
                target_price, stop_loss_price,
                trailing_stop_state, position_metadata,
                status, entry_time, exit_time, execution_environment
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'closed', %s, NOW(), %s)
            RETURNING id
        """,
            (
                current["position_id"],  # Copy business key from current version
                current["market_id"],
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
                current["execution_environment"],  # Preserve execution environment
            ),
        )

        result = cur.fetchone()
        return cast("int", result["id"])  # Return new surrogate id


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
    # ⭐ ATTRIBUTION ARCHITECTURE (Migration 019) - NEW parameters
    trade_source: str = "automated",
    calculated_probability: Decimal | None = None,
    market_price: Decimal | None = None,
    # ⭐ EXECUTION ENVIRONMENT (Migration 0008, ADR-107) - NEW parameter
    execution_environment: ExecutionEnvironment = "live",
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
        trade_source: Trade origin ('automated' or 'manual') - default 'automated'
        calculated_probability: Model-predicted win probability at execution (0.0-1.0)
        market_price: Kalshi market price at execution (0.0-1.0)
        execution_environment: Execution context - 'live' (production), 'paper' (demo),
            or 'backtest' (simulation). Default 'live'. See ADR-107.

    Returns:
        trade_id of newly created trade

    Educational Note:
        Attribution Architecture (Migrations 018-019):
        - trade_source distinguishes automated (app) vs manual (Kalshi UI) trades
        - calculated_probability + market_price enable performance analytics:
          * "Which model has highest ROI?"
          * "Do high-edge trades correlate with profit?"
        - edge_value automatically calculated: calculated_probability - market_price
        - 20-100x faster than JSONB for analytics (B-tree index vs GIN index)

    Validation:
        - If calculated_probability provided, market_price should also be provided
        - Both must be in range [0.0, 1.0] (enforced by CHECK constraints)
        - trade_source must be 'automated' or 'manual' (enforced by ENUM type)

    Example:
        >>> trade_id = create_trade(
        ...     market_id=42,
        ...     strategy_id=1,
        ...     model_id=2,
        ...     side='YES',
        ...     quantity=100,
        ...     price=Decimal("0.5200"),
        ...     position_id=123,
        ...     trade_source='automated',
        ...     calculated_probability=Decimal("0.6500"),
        ...     market_price=Decimal("0.5800"),
        ...     execution_environment='paper'  # Demo API testing
        ... )
        >>> # edge_value automatically calculated: 0.6500 - 0.5800 = 0.0700
    """
    # Calculate edge_value if both probability and price provided
    edge_value: Decimal | None = None
    if calculated_probability is not None and market_price is not None:
        edge_value = calculated_probability - market_price

    query = """
        INSERT INTO trades (
            market_id, strategy_id, model_id,
            side, quantity, price,
            position_internal_id, order_type,
            trade_metadata, execution_time,
            trade_source, calculated_probability, market_price, edge_value,
            execution_environment
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
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
        trade_source,
        calculated_probability,
        market_price,
        edge_value,
        execution_environment,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["trade_id"])


def get_trades_by_market(
    market_id: str,
    limit: int = 100,
    execution_environment: ExecutionEnvironment | None = None,
) -> list[dict[str, Any]]:
    """
    Get all trades for a specific market.

    Args:
        market_id: Market to query
        limit: Maximum number of trades (default: 100)
        execution_environment: Filter by environment ('live', 'paper', 'backtest').
            If None, returns trades from all environments.

    Returns:
        List of trades, newest first

    Example:
        >>> # All trades for market
        >>> trades = get_trades_by_market(market_id=42, limit=20)
        >>> # Only paper trades (demo API testing)
        >>> paper_trades = get_trades_by_market(market_id=42, execution_environment='paper')
    """
    query = """
        SELECT t.*, m.ticker
        FROM trades t
        JOIN markets m ON t.market_id = m.market_id
        WHERE t.market_id = %s
          AND m.row_current_ind = TRUE
    """
    params: list[str | int] = [market_id]

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
    query = """
        SELECT t.*, m.ticker, s.strategy_name, pm.model_name
        FROM trades t
        JOIN markets m ON t.market_id = m.market_id
        JOIN strategies s ON t.strategy_id = s.strategy_id
        JOIN probability_models pm ON t.model_id = pm.model_id
        WHERE m.row_current_ind = TRUE
    """
    params: list[int | str] = []

    if strategy_id:
        query += " AND t.strategy_id = %s"
        params.append(strategy_id)

    if execution_environment is not None:
        query += " AND t.execution_environment = %s"
        params.append(execution_environment)

    query += " ORDER BY t.execution_time DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

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
        return result["balance_id"] if result else None


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
        return result["balance_id"] if result else None


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
        return result["settlement_id"] if result else None


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
    query = "SELECT * FROM strategies WHERE strategy_id = %s"

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
    query = """
        SELECT * FROM strategies
        WHERE strategy_name = %s AND strategy_version = %s
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
    query = """
        SELECT * FROM strategies
        WHERE strategy_name = %s AND status = 'active'
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


def get_all_strategy_versions(strategy_name: str) -> list[dict[str, Any]]:
    """
    Get all versions of a strategy (for history view).

    Args:
        strategy_name: Strategy name

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
    """
    query = """
        SELECT * FROM strategies
        WHERE strategy_name = %s
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
    Update strategy status (MUTABLE field - does NOT create new version).

    Args:
        strategy_id: Strategy ID
        new_status: New status ("draft", "testing", "active", "deprecated")
        activated_at: Timestamp when activated (optional)
        deactivated_at: Timestamp when deactivated (optional)

    Returns:
        bool: True if updated, False if strategy not found

    Educational Note:
        Status is MUTABLE (can change in-place):
        - draft -> testing -> active -> deprecated (normal lifecycle)
        - active -> deprecated (when superseded by new version)

        Config is IMMUTABLE (cannot change in-place):
        - To change config, create NEW version (v1.0 -> v1.1)

    Example:
        >>> # Move from draft to testing
        >>> update_strategy_status(strategy_id=42, new_status="testing")
        >>> # Activate strategy
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
    """
    query = """
        UPDATE strategies
        SET status = %s,
            activated_at = %s,
            deactivated_at = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE strategy_id = %s
        RETURNING strategy_id
    """

    params = (new_status, activated_at, deactivated_at, strategy_id)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result is not None


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
    if status:
        query = """
            SELECT *
            FROM strategies
            WHERE status = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        results = fetch_all(query, (status, limit, offset))
    else:
        query = """
            SELECT *
            FROM strategies
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        results = fetch_all(query, (limit, offset))

    # Convert config Decimal strings back to Decimal for consistency
    for result in results:
        if result.get("config"):
            result["config"] = _convert_config_strings_to_decimal(result["config"])

    return results


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
    query = """
        SELECT p.*, m.ticker, s.strategy_name, pm.model_name
        FROM positions p
        JOIN markets m ON p.market_id = m.market_id
        JOIN strategies s ON p.strategy_id = s.strategy_id
        LEFT JOIN probability_models pm ON p.model_id = pm.model_id
        WHERE p.id = %s
          AND p.row_current_ind = TRUE
          AND m.row_current_ind = TRUE
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
    query = """
        SELECT t.*, m.ticker, s.strategy_name, pm.model_name
        FROM trades t
        JOIN markets m ON t.market_id = m.market_id
        JOIN strategies s ON t.strategy_id = s.strategy_id
        LEFT JOIN probability_models pm ON t.model_id = pm.model_id
        WHERE t.trade_id = %s
          AND m.row_current_ind = TRUE
    """
    return fetch_one(query, (trade_id,))


# =============================================================================
# VENUE OPERATIONS (Phase 2 - Live Data Integration)
# =============================================================================


def create_venue(
    espn_venue_id: str,
    venue_name: str,
    city: str | None = None,
    state: str | None = None,
    capacity: int | None = None,
    indoor: bool = False,
) -> int:
    """
    Create new venue record (or update if ESPN venue ID exists).

    Venues are mutable entities - no SCD Type 2 versioning. Updates use
    simple UPDATE statements since venue data rarely changes and history
    is not needed for trading decisions.

    Args:
        espn_venue_id: ESPN unique venue identifier (e.g., "3622")
        venue_name: Full venue name (e.g., "GEHA Field at Arrowhead Stadium")
        city: City where venue is located
        state: State/province abbreviation or full name
        capacity: Maximum seating capacity
        indoor: TRUE for domed stadiums/indoor arenas

    Returns:
        venue_id of created/updated record

    Educational Note:
        Venues use UPSERT (INSERT ... ON CONFLICT UPDATE) because:
        - ESPN venue IDs are stable external identifiers
        - Venue data changes rarely (naming rights updates)
        - No need for historical versioning (not trading-relevant)
        - Simplifies data pipeline (always upsert, never check exists)

    Example:
        >>> venue_id = create_venue(
        ...     espn_venue_id="3622",
        ...     venue_name="GEHA Field at Arrowhead Stadium",
        ...     city="Kansas City",
        ...     state="Missouri",
        ...     capacity=76416,
        ...     indoor=False
        ... )

    References:
        - REQ-DATA-002: Venue Data Management
        - ADR-029: ESPN Data Model with Normalized Schema
    """
    # Normalize capacity: ESPN API sometimes returns 0 for unknown capacity
    # DB constraint requires capacity IS NULL OR capacity > 0
    if capacity is not None and capacity <= 0:
        capacity = None

    query = """
        INSERT INTO venues (
            espn_venue_id, venue_name, city, state, capacity, indoor
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (espn_venue_id)
        DO UPDATE SET
            venue_name = EXCLUDED.venue_name,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            capacity = EXCLUDED.capacity,
            indoor = EXCLUDED.indoor,
            updated_at = NOW()
        RETURNING venue_id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (espn_venue_id, venue_name, city, state, capacity, indoor))
        result = cur.fetchone()
        return cast("int", result["venue_id"])


def get_venue_by_espn_id(espn_venue_id: str) -> dict[str, Any] | None:
    """
    Get venue by ESPN venue ID.

    Args:
        espn_venue_id: ESPN unique venue identifier

    Returns:
        Dictionary with venue data, or None if not found

    Example:
        >>> venue = get_venue_by_espn_id("3622")
        >>> if venue:
        ...     print(f"{venue['venue_name']} - {venue['city']}, {venue['state']}")
    """
    query = """
        SELECT *
        FROM venues
        WHERE espn_venue_id = %s
    """
    return fetch_one(query, (espn_venue_id,))


def get_venue_by_id(venue_id: int) -> dict[str, Any] | None:
    """
    Get venue by internal venue_id.

    Args:
        venue_id: Internal venue ID

    Returns:
        Dictionary with venue data, or None if not found
    """
    query = """
        SELECT *
        FROM venues
        WHERE venue_id = %s
    """
    return fetch_one(query, (venue_id,))


# =============================================================================
# TEAM LOOKUP OPERATIONS
# =============================================================================
# These functions provide team lookup by various identifiers.
# Essential for the live polling service to map ESPN IDs to database IDs.


def get_team_by_espn_id(espn_team_id: str, league: str | None = None) -> dict[str, Any] | None:
    """
    Get team by ESPN team ID and optional league filter.

    Educational Note:
        ESPN team IDs are unique per-league but NOT globally unique.
        For example, team ID "1" might exist in both NFL and NBA.
        Always provide the league parameter when you know it to ensure
        correct team matching.

    Args:
        espn_team_id: ESPN's unique team identifier (e.g., "12" for Chiefs)
        league: Optional league filter (nfl, ncaaf, nba, ncaab, nhl, wnba)
                Recommended to prevent cross-league mismatches.

    Returns:
        Dictionary with team data, or None if not found.
        Includes: team_id, team_code, team_name, display_name, espn_team_id,
                  conference, division, sport, league, current_elo

    Example:
        >>> team = get_team_by_espn_id("12", league="nfl")
        >>> if team:
        ...     print(f"{team['team_name']} ({team['team_code']})")
        ...     # Kansas City Chiefs (KC)

    Reference: REQ-DATA-003 (Multi-Sport Support)
    """
    if league:
        query = """
            SELECT *
            FROM teams
            WHERE espn_team_id = %s AND league = %s
        """
        return fetch_one(query, (espn_team_id, league))
    query = """
            SELECT *
            FROM teams
            WHERE espn_team_id = %s
        """
    return fetch_one(query, (espn_team_id,))


# =============================================================================
# TEAM RANKING OPERATIONS (Phase 2 - Live Data Integration)
# =============================================================================


def create_team_ranking(
    team_id: int,
    ranking_type: str,
    rank: int,
    season: int,
    ranking_date: datetime,
    week: int | None = None,
    points: int | None = None,
    first_place_votes: int | None = None,
    previous_rank: int | None = None,
) -> int:
    """
    Create new team ranking record.

    Rankings are append-only history - no SCD Type 2, no updates. Each
    week's ranking is a separate record. Use UPSERT to handle re-imports
    of the same week's rankings.

    Args:
        team_id: Foreign key to teams.team_id
        ranking_type: Type of ranking ('ap_poll', 'cfp', 'coaches_poll', etc.)
        rank: Numeric rank position (1 = best)
        season: Season year (e.g., 2024)
        ranking_date: Date ranking was released
        week: Week number (1-18), None for preseason/final
        points: Poll points (AP/Coaches)
        first_place_votes: Number of #1 votes
        previous_rank: Previous week's rank (None if was unranked)

    Returns:
        ranking_id of created/updated record

    Educational Note:
        Rankings use temporal validity (season + week) instead of SCD Type 2:
        - Each week's poll is a distinct point-in-time snapshot
        - No need to track intra-week changes (polls released weekly)
        - Simpler queries: "Get AP Poll week 12" vs "Get AP Poll at timestamp X"
        - History preserved naturally via (team, type, season, week) uniqueness

    Example:
        >>> ranking_id = create_team_ranking(
        ...     team_id=1,
        ...     ranking_type="ap_poll",
        ...     rank=3,
        ...     season=2024,
        ...     week=12,
        ...     ranking_date=datetime(2024, 11, 17),
        ...     points=1432,
        ...     first_place_votes=12
        ... )

    References:
        - REQ-DATA-004: Team Rankings Storage (Temporal Validity)
        - ADR-029: ESPN Data Model with Normalized Schema
    """
    query = """
        INSERT INTO team_rankings (
            team_id, ranking_type, rank, season, week, ranking_date,
            points, first_place_votes, previous_rank
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (team_id, ranking_type, season, week)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            ranking_date = EXCLUDED.ranking_date,
            points = EXCLUDED.points,
            first_place_votes = EXCLUDED.first_place_votes,
            previous_rank = EXCLUDED.previous_rank
        RETURNING ranking_id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                team_id,
                ranking_type,
                rank,
                season,
                week,
                ranking_date,
                points,
                first_place_votes,
                previous_rank,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["ranking_id"])


def get_team_rankings(
    team_id: int,
    ranking_type: str | None = None,
    season: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get ranking history for a team.

    Args:
        team_id: Team ID to lookup
        ranking_type: Filter by ranking type (optional)
        season: Filter by season (optional)

    Returns:
        List of ranking records ordered by season, week

    Example:
        >>> rankings = get_team_rankings(team_id=1, ranking_type="ap_poll", season=2024)
        >>> for r in rankings:
        ...     print(f"Week {r['week']}: #{r['rank']} ({r['points']} pts)")
    """
    conditions = ["team_id = %s"]
    params: list[Any] = [team_id]

    if ranking_type:
        conditions.append("ranking_type = %s")
        params.append(ranking_type)

    if season:
        conditions.append("season = %s")
        params.append(season)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM team_rankings
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, week DESC NULLS LAST
    """  # noqa: S608
    return fetch_all(query, tuple(params))


def get_current_rankings(
    ranking_type: str, season: int, week: int | None = None
) -> list[dict[str, Any]]:
    """
    Get current rankings for a ranking type.

    If week is not specified, returns the most recent week's rankings.

    Args:
        ranking_type: Type of ranking ('ap_poll', 'cfp', etc.)
        season: Season year
        week: Specific week (optional, defaults to latest)

    Returns:
        List of ranking records ordered by rank

    Example:
        >>> rankings = get_current_rankings("ap_poll", 2024)
        >>> for r in rankings[:5]:
        ...     print(f"#{r['rank']}: Team {r['team_id']} ({r['points']} pts)")
    """
    if week is None:
        # Get most recent week
        week_query = """
            SELECT MAX(week) as max_week
            FROM team_rankings
            WHERE ranking_type = %s AND season = %s
        """
        result = fetch_one(week_query, (ranking_type, season))
        if not result or result["max_week"] is None:
            return []
        week = result["max_week"]

    query = """
        SELECT tr.*, t.team_code, t.team_name, t.display_name
        FROM team_rankings tr
        JOIN teams t ON tr.team_id = t.team_id
        WHERE tr.ranking_type = %s
          AND tr.season = %s
          AND tr.week = %s
        ORDER BY tr.rank
    """
    return fetch_all(query, (ranking_type, season, week))


# =============================================================================
# GAME STATE OPERATIONS (Phase 2 - Live Data Integration, SCD Type 2)
# =============================================================================


def create_game_state(
    espn_event_id: str,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    venue_id: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    period: int = 0,
    clock_seconds: Decimal | None = None,
    clock_display: str | None = None,
    game_status: str = "pre",
    game_date: datetime | None = None,
    broadcast: str | None = None,
    neutral_site: bool = False,
    season_type: str | None = None,
    week_number: int | None = None,
    league: str | None = None,
    situation: dict | None = None,
    linescores: list | None = None,
    data_source: str = "espn",
) -> int:
    """
    Create initial game state record (row_current_ind = TRUE).

    Use this for NEW games only. For updates, use upsert_game_state()
    which handles SCD Type 2 versioning (closes old row, creates new).

    Args:
        espn_event_id: ESPN event identifier (natural key)
        home_team_id: Foreign key to teams.team_id for home team
        away_team_id: Foreign key to teams.team_id for away team
        venue_id: Foreign key to venues.venue_id
        home_score: Home team score
        away_score: Away team score
        period: Current period (0=pregame, 1-4=regulation, 5+=OT)
        clock_seconds: Seconds remaining in period
        clock_display: Human-readable clock (e.g., "5:32")
        game_status: Status ('pre', 'in_progress', 'halftime', 'final', etc.)
        game_date: Scheduled game start time
        broadcast: TV broadcast info
        neutral_site: TRUE for neutral venue games
        season_type: Season phase ('regular', 'playoff', 'bowl', etc.)
        week_number: Week number within season
        league: League code ('nfl', 'nba', etc.)
        situation: Sport-specific situation data (JSONB)
        linescores: Period-by-period scores (JSONB)
        data_source: Source of game data (default: 'espn')

    Returns:
        id (surrogate key) of newly created record

    Educational Note:
        Game states use SCD Type 2 for complete historical tracking:
        - Each score/clock change creates NEW row (old preserved)
        - row_current_ind = TRUE marks latest version
        - Enables replay: "What was the score at halftime?"
        - Critical for backtesting live trading strategies
        - ~190 updates per game = ~190 historical rows per game

        Dual-Key Structure (Migration 029):
        - id SERIAL (surrogate key) - returned by this function
        - game_state_id VARCHAR (business key) - auto-generated as GS-{id}
        - Enables SCD Type 2 versioning (multiple versions of same event)

    Example:
        >>> state_id = create_game_state(
        ...     espn_event_id="401547417",
        ...     home_team_id=1,
        ...     away_team_id=2,
        ...     venue_id=1,
        ...     game_status="pre",
        ...     game_date=datetime(2024, 11, 28, 16, 30),
        ...     league="nfl",
        ...     season_type="regular",
        ...     week_number=12
        ... )

    References:
        - REQ-DATA-001: Game State Data Collection (SCD Type 2)
        - ADR-029: ESPN Data Model with Normalized Schema
        - Pattern 2: Dual Versioning System (SCD Type 2)
    """
    # Step 1: INSERT with placeholder game_state_id (will be updated immediately)
    insert_query = """
        INSERT INTO game_states (
            game_state_id, espn_event_id, home_team_id, away_team_id, venue_id,
            home_score, away_score, period, clock_seconds, clock_display,
            game_status, game_date, broadcast, neutral_site,
            season_type, week_number, league, situation, linescores,
            data_source, row_current_ind, row_start_ts
        )
        VALUES (
            'TEMP', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, TRUE, NOW()
        )
        RETURNING id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            insert_query,
            (
                espn_event_id,
                home_team_id,
                away_team_id,
                venue_id,
                home_score,
                away_score,
                period,
                clock_seconds,
                clock_display,
                game_status,
                game_date,
                broadcast,
                neutral_site,
                season_type,
                week_number,
                league,
                json.dumps(situation) if situation else None,
                json.dumps(linescores) if linescores else None,
                data_source,
            ),
        )
        result = cur.fetchone()
        surrogate_id = cast("int", result["id"])

        # Step 2: UPDATE to set correct game_state_id (GS-{id} format)
        update_query = """
            UPDATE game_states
            SET game_state_id = %s
            WHERE id = %s
        """
        cur.execute(update_query, (f"GS-{surrogate_id}", surrogate_id))

        return surrogate_id


def get_current_game_state(espn_event_id: str) -> dict[str, Any] | None:
    """
    Get current (latest) game state for an event.

    Args:
        espn_event_id: ESPN event identifier

    Returns:
        Dictionary with current game state, or None if not found

    Educational Note:
        Always query with row_current_ind = TRUE to get latest version.
        Without this filter, you may get historical rows with stale data.

    Example:
        >>> state = get_current_game_state("401547417")
        >>> if state:
        ...     print(f"{state['home_score']}-{state['away_score']} ({state['clock_display']})")
    """
    query = """
        SELECT gs.*,
               th.team_code AS home_team_code, th.team_name AS home_team_name,
               ta.team_code AS away_team_code, ta.team_name AS away_team_name,
               v.venue_name, v.city, v.state
        FROM game_states gs
        LEFT JOIN teams th ON gs.home_team_id = th.team_id
        LEFT JOIN teams ta ON gs.away_team_id = ta.team_id
        LEFT JOIN venues v ON gs.venue_id = v.venue_id
        WHERE gs.espn_event_id = %s
          AND gs.row_current_ind = TRUE
    """
    return fetch_one(query, (espn_event_id,))


def game_state_changed(
    current: dict[str, Any] | None,
    home_score: int,
    away_score: int,
    period: int,
    game_status: str,
    situation: dict | None = None,
) -> bool:
    """
    Check if game state has meaningfully changed from current database state.

    Used by upsert_game_state to avoid creating duplicate SCD Type 2 rows
    when game state hasn't changed. This reduces database bloat during
    high-frequency polling (e.g., every 15-30 seconds during live games).

    Args:
        current: Current game state from database (None if no existing state)
        home_score: New home team score
        away_score: New away team score
        period: New period number
        game_status: New game status
        situation: New situation data (downs, possession, etc.)

    Returns:
        True if state has changed and a new row should be created,
        False if state is the same and no update needed.

    Educational Note:
        We intentionally DO NOT compare clock_seconds or clock_display because:
        - Clock changes every few seconds during play
        - This would create ~1000+ rows per game instead of ~50-100
        - Score, period, status, and situation changes are what matter for trading

        We DO compare:
        - home_score, away_score: Core game state
        - period: Quarter/half transitions
        - game_status: Pre/in_progress/halftime/final transitions
        - situation: Possession, down/distance changes (significant for NFL)

    Example:
        >>> current = get_current_game_state("401547417")
        >>> if game_state_changed(current, 14, 7, 2, "in_progress", {"possession": "KC"}):
        ...     upsert_game_state("401547417", home_score=14, ...)

    References:
        - Issue #234: State Change Detection requirement
        - REQ-DATA-001: Game State Data Collection
    """
    # No current state = always insert (new game)
    if current is None:
        return True

    # Compare core state fields
    if current.get("home_score") != home_score:
        return True
    if current.get("away_score") != away_score:
        return True
    if current.get("period") != period:
        return True
    if current.get("game_status") != game_status:
        return True

    # Compare situation (JSONB field) if provided
    # Only compare if new situation is provided - ignore if None
    if situation is not None:
        current_situation = current.get("situation") or {}
        # Compare key situation fields for football
        situation_keys = ["possession", "down", "distance", "yard_line", "is_red_zone"]
        for key in situation_keys:
            if situation.get(key) != current_situation.get(key):
                return True

    return False


def upsert_game_state(
    espn_event_id: str,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    venue_id: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    period: int = 0,
    clock_seconds: Decimal | None = None,
    clock_display: str | None = None,
    game_status: str = "pre",
    game_date: datetime | None = None,
    broadcast: str | None = None,
    neutral_site: bool = False,
    season_type: str | None = None,
    week_number: int | None = None,
    league: str | None = None,
    situation: dict | None = None,
    linescores: list | None = None,
    data_source: str = "espn",
    skip_if_unchanged: bool = True,
) -> int | None:
    """
    Insert or update game state with SCD Type 2 versioning.

    If game exists: closes current row (row_current_ind=FALSE) and inserts new.
    If game doesn't exist: creates new row with row_current_ind=TRUE.

    This is the primary function for updating live game data from ESPN API.

    Args:
        (same as create_game_state)
        data_source: Source of game data (default: 'espn')
        skip_if_unchanged: If True, skip update when state hasn't meaningfully
            changed (score, period, status, situation). Default True.
            Set to False to always create a new row (legacy behavior).

    Returns:
        id (surrogate key) of newly created record, or None if skipped due to
        no state change (when skip_if_unchanged=True).

    Educational Note:
        SCD Type 2 UPSERT pattern:
        1. Check if current row exists for espn_event_id
        2. If exists: UPDATE to close it (row_current_ind=FALSE, row_end_ts=NOW)
        3. INSERT new row with row_current_ind=TRUE

        State Change Detection (Issue #234):
        When skip_if_unchanged=True (default), we check if meaningful state has
        changed before creating a new row. This prevents database bloat from
        high-frequency polling (~1000 rows/game -> ~50-100 rows/game).

        "Meaningful" changes include: score, period, game_status, situation.
        Clock changes are intentionally ignored (changes every few seconds).

    Example:
        >>> # Update score during game
        >>> state_id = upsert_game_state(
        ...     espn_event_id="401547417",
        ...     home_score=7,
        ...     away_score=3,
        ...     period=1,
        ...     clock_display="5:32",
        ...     game_status="in_progress",
        ...     situation={"possession": "KC", "down": 2, "distance": 7}
        ... )
        >>> if state_id is None:
        ...     print("No state change - update skipped")

    References:
        - REQ-DATA-001: Game State Data Collection (SCD Type 2)
        - Issue #234: State Change Detection
        - Pattern 2: Dual Versioning System
    """
    # State change detection (Issue #234)
    # Check if meaningful state has changed before creating a new SCD row
    if skip_if_unchanged:
        current = get_current_game_state(espn_event_id)
        if not game_state_changed(current, home_score, away_score, period, game_status, situation):
            # No meaningful change - return existing ID or None
            return current.get("id") if current else None

    # Use a SINGLE transaction for all operations to maintain atomicity
    # This ensures that if INSERT fails, the UPDATE is also rolled back
    #
    # Educational Note:
    #   SCD Type 2 upsert is a 3-step atomic operation:
    #   1. Close current row (row_current_ind = FALSE)
    #   2. Insert new row with placeholder game_state_id
    #   3. Update new row with proper game_state_id (GS-{id})
    #   All three must succeed or all must fail (ACID transaction)

    close_query = """
        UPDATE game_states
        SET row_current_ind = FALSE,
            row_end_ts = NOW()
        WHERE espn_event_id = %s
          AND row_current_ind = TRUE
    """

    insert_query = """
        INSERT INTO game_states (
            game_state_id, espn_event_id, home_team_id, away_team_id, venue_id,
            home_score, away_score, period, clock_seconds, clock_display,
            game_status, game_date, broadcast, neutral_site,
            season_type, week_number, league, situation, linescores,
            data_source, row_current_ind, row_start_ts
        )
        VALUES (
            'TEMP', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, TRUE, NOW()
        )
        RETURNING id
    """

    update_id_query = """
        UPDATE game_states
        SET game_state_id = %s
        WHERE id = %s
    """

    with get_cursor(commit=True) as cur:
        # Step 1: Close current row (if exists)
        cur.execute(close_query, (espn_event_id,))

        # Step 2: Insert new row with placeholder
        cur.execute(
            insert_query,
            (
                espn_event_id,
                home_team_id,
                away_team_id,
                venue_id,
                home_score,
                away_score,
                period,
                clock_seconds,
                clock_display,
                game_status,
                game_date,
                broadcast,
                neutral_site,
                season_type,
                week_number,
                league,
                json.dumps(situation) if situation else None,
                json.dumps(linescores) if linescores else None,
                data_source,
            ),
        )
        result = cur.fetchone()
        surrogate_id = cast("int", result["id"])

        # Step 3: Update game_state_id to proper value
        cur.execute(update_id_query, (f"GS-{surrogate_id}", surrogate_id))

        return surrogate_id


def get_game_state_history(espn_event_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    Get historical game state versions for an event.

    Returns all versions ordered by timestamp (newest first), useful for:
    - Reviewing game progression
    - Backtesting trading decisions
    - Debugging data pipeline issues

    Args:
        espn_event_id: ESPN event identifier
        limit: Maximum rows to return (default 100)

    Returns:
        List of game state records ordered by row_start_ts DESC

    Example:
        >>> history = get_game_state_history("401547417")
        >>> for state in history[:5]:
        ...     print(f"{state['row_start_ts']}: {state['home_score']}-{state['away_score']}")
    """
    query = """
        SELECT *
        FROM game_states
        WHERE espn_event_id = %s
        ORDER BY row_start_ts DESC
        LIMIT %s
    """
    return fetch_all(query, (espn_event_id, limit))


def get_live_games(
    league: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get all currently in-progress games with pagination.

    Args:
        league: Filter by league (optional)
        limit: Maximum number of games to return (default: 100)
        offset: Number of games to skip for pagination (default: 0)

    Returns:
        List of current game states for in-progress games

    Example:
        >>> games = get_live_games(league="nfl")
        >>> for g in games:
        ...     print(f"{g['home_team_code']} vs {g['away_team_code']}")
    """
    conditions = ["gs.row_current_ind = TRUE", "gs.game_status = 'in_progress'"]
    params: list[Any] = []

    if league:
        conditions.append("gs.league = %s")
        params.append(league)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT gs.*,
               th.team_code AS home_team_code, th.display_name AS home_team_name,
               ta.team_code AS away_team_code, ta.display_name AS away_team_name,
               v.venue_name
        FROM game_states gs
        LEFT JOIN teams th ON gs.home_team_id = th.team_id
        LEFT JOIN teams ta ON gs.away_team_id = ta.team_id
        LEFT JOIN venues v ON gs.venue_id = v.venue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY gs.game_date
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


def get_games_by_date(
    game_date: datetime,
    league: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get all games scheduled for a specific date with pagination.

    Args:
        game_date: Date to query (time component ignored)
        league: Filter by league (optional)
        limit: Maximum number of games to return (default: 100)
        offset: Number of games to skip for pagination (default: 0)

    Returns:
        List of current game states for games on that date

    Example:
        >>> from datetime import datetime
        >>> games = get_games_by_date(datetime(2024, 11, 28), league="nfl")
        >>> for g in games:
        ...     print(f"{g['game_date']}: {g['home_team_code']} vs {g['away_team_code']}")
    """
    conditions = [
        "gs.row_current_ind = TRUE",
        "DATE(gs.game_date) = DATE(%s)",
    ]
    params: list[Any] = [game_date]

    if league:
        conditions.append("gs.league = %s")
        params.append(league)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT gs.*,
               th.team_code AS home_team_code, th.display_name AS home_team_name,
               ta.team_code AS away_team_code, ta.display_name AS away_team_name,
               v.venue_name
        FROM game_states gs
        LEFT JOIN teams th ON gs.home_team_id = th.team_id
        LEFT JOIN teams ta ON gs.away_team_id = ta.team_id
        LEFT JOIN venues v ON gs.venue_id = v.venue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY gs.game_date, gs.league
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


# =============================================================================
# HISTORICAL STATS CRUD OPERATIONS
# =============================================================================
# Functions for historical_stats table (Migration 0009)
# Used for storing player/team statistics from external data sources
# =============================================================================


def insert_historical_stat(
    sport: str,
    season: int,
    stat_category: str,
    stats: dict[str, Any],
    source: str,
    week: int | None = None,
    team_code: str | None = None,
    player_id: str | None = None,
    player_name: str | None = None,
    source_file: str | None = None,
) -> int:
    """
    Insert a single historical stat record with UPSERT semantics.

    Uses INSERT ... ON CONFLICT to handle re-imports idempotently. The unique
    constraint is on (sport, season, week, team_code, player_id, stat_category, source),
    allowing the same stat to be updated if re-imported from the same source.

    Args:
        sport: Sport code (nfl, ncaaf, nba, ncaab, nhl, mlb)
        season: Season year (e.g., 2024)
        stat_category: Category (passing, rushing, receiving, team_offense, etc.)
        stats: JSONB dictionary of stat fields (flexible schema per sport/category)
        source: Data source identifier (nfl_data_py, espn, pro_football_reference)
        week: Week number (None for seasonal aggregates)
        team_code: Team abbreviation (required for team stats)
        player_id: External player ID (required for player stats)
        player_name: Player display name (for player stats)
        source_file: Source filename for CSV-based imports

    Returns:
        historical_stat_id of created/updated record

    Raises:
        ValueError: If neither team_code nor player_id is provided

    Educational Note:
        Historical stats use JSONB for the stats field to support flexible schemas
        across different sports and categories. Unlike the live tables (game_states),
        these use VARCHAR team_code instead of INTEGER team_id FK, allowing data
        loading before team mappings exist. FK resolution is a separate step.

    Example:
        >>> stat_id = insert_historical_stat(
        ...     sport="nfl",
        ...     season=2024,
        ...     week=12,
        ...     team_code="KC",
        ...     stat_category="team_offense",
        ...     stats={"yards": 412, "points": 31, "turnovers": 1},
        ...     source="nfl_data_py"
        ... )

    References:
        - Migration 0009: historical_stats table
        - ADR-106: Historical Data Collection Architecture
        - REQ-DATA-005: Historical Statistics Storage
    """
    if not team_code and not player_id:
        raise ValueError("Either team_code or player_id must be provided")

    # Use a composite conflict target for upsert
    # This handles re-imports of the same data gracefully
    query = """
        INSERT INTO historical_stats (
            sport, season, week, team_code, player_id, player_name,
            stat_category, stats, source, source_file
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, COALESCE(week, -1), COALESCE(team_code, ''),
                     COALESCE(player_id, ''), stat_category, source)
        DO UPDATE SET
            player_name = EXCLUDED.player_name,
            stats = EXCLUDED.stats,
            source_file = EXCLUDED.source_file
        RETURNING historical_stat_id
    """
    with get_cursor(commit=True) as cur:
        # Convert dict to JSON string for psycopg2
        import json

        stats_json = json.dumps(stats)
        cur.execute(
            query,
            (
                sport,
                season,
                week,
                team_code,
                player_id,
                player_name,
                stat_category,
                stats_json,
                source,
                source_file,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["historical_stat_id"])


def insert_historical_stats_batch(
    records: list[dict[str, Any]],
    batch_size: int = 1000,
) -> tuple[int, int]:
    """
    Batch insert historical stat records with progress tracking.

    Efficiently inserts multiple records using executemany with batching.
    Uses UPSERT semantics for idempotent re-imports.

    Args:
        records: List of stat record dictionaries with keys:
            - sport, season, week, team_code, player_id, player_name,
            - stat_category, stats, source, source_file
        batch_size: Number of records per batch (default 1000)

    Returns:
        Tuple of (inserted_count, updated_count)

    Educational Note:
        Batch inserts are significantly faster than individual inserts for large
        datasets (10x-100x improvement). The batch_size parameter balances memory
        usage against transaction overhead. 1000 records is a good default for
        most systems.

    Example:
        >>> records = [
        ...     {"sport": "nfl", "season": 2024, "week": 12, "team_code": "KC",
        ...      "stat_category": "team_offense", "stats": {"yards": 412},
        ...      "source": "nfl_data_py"},
        ...     {"sport": "nfl", "season": 2024, "week": 12, "team_code": "DEN",
        ...      "stat_category": "team_offense", "stats": {"yards": 289},
        ...      "source": "nfl_data_py"},
        ... ]
        >>> inserted, updated = insert_historical_stats_batch(records)
        >>> print(f"Inserted: {inserted}, Updated: {updated}")

    References:
        - Issue #253: CRUD operations for historical tables
        - ADR-106: Historical Data Collection Architecture
    """
    import json

    if not records:
        return (0, 0)

    query = """
        INSERT INTO historical_stats (
            sport, season, week, team_code, player_id, player_name,
            stat_category, stats, source, source_file
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, COALESCE(week, -1), COALESCE(team_code, ''),
                     COALESCE(player_id, ''), stat_category, source)
        DO UPDATE SET
            player_name = EXCLUDED.player_name,
            stats = EXCLUDED.stats,
            source_file = EXCLUDED.source_file
    """
    total_inserted = 0

    with get_cursor(commit=True) as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            params = [
                (
                    r["sport"],
                    r["season"],
                    r.get("week"),
                    r.get("team_code"),
                    r.get("player_id"),
                    r.get("player_name"),
                    r["stat_category"],
                    json.dumps(r["stats"]),
                    r["source"],
                    r.get("source_file"),
                )
                for r in batch
            ]
            cur.executemany(query, params)
            total_inserted += len(batch)

    # Note: PostgreSQL doesn't distinguish inserts vs updates in executemany
    # Return total as inserted, 0 as updated (conservative estimate)
    return (total_inserted, 0)


def get_historical_stats(
    sport: str,
    season: int,
    week: int | None = None,
    team_code: str | None = None,
    player_id: str | None = None,
    stat_category: str | None = None,
    source: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """
    Query historical stats with flexible filtering.

    Supports filtering by sport, season, week, team, player, category, and source.
    Returns stats ordered by season (desc), week (desc), team, player.

    Args:
        sport: Sport code (required)
        season: Season year (required)
        week: Filter by specific week (None for all weeks)
        team_code: Filter by team (None for all teams)
        player_id: Filter by player ID (None for all players)
        stat_category: Filter by category (None for all categories)
        source: Filter by data source (None for all sources)
        limit: Maximum records to return (default 1000)

    Returns:
        List of stat records with all fields including parsed stats JSONB

    Example:
        >>> # Get all KC offensive stats for week 12
        >>> stats = get_historical_stats(
        ...     sport="nfl", season=2024, week=12,
        ...     team_code="KC", stat_category="team_offense"
        ... )
        >>> for s in stats:
        ...     print(f"{s['stat_category']}: {s['stats']}")

    References:
        - Migration 0009: historical_stats table indexes
        - REQ-DATA-005: Historical Statistics Storage
    """
    conditions = ["sport = %s", "season = %s"]
    params: list[Any] = [sport, season]

    if week is not None:
        conditions.append("week = %s")
        params.append(week)

    if team_code:
        conditions.append("team_code = %s")
        params.append(team_code)

    if player_id:
        conditions.append("player_id = %s")
        params.append(player_id)

    if stat_category:
        conditions.append("stat_category = %s")
        params.append(stat_category)

    if source:
        conditions.append("source = %s")
        params.append(source)

    params.append(limit)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_stats
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, COALESCE(week, 0) DESC, team_code, player_id
        LIMIT %s
    """  # noqa: S608
    return fetch_all(query, tuple(params))


def get_player_stats(
    sport: str,
    player_id: str,
    season: int | None = None,
    stat_category: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get all stats for a specific player.

    Retrieves player statistics across seasons, weeks, and categories.
    Useful for player performance analysis and historical comparisons.

    Args:
        sport: Sport code (required)
        player_id: External player ID from source (required)
        season: Filter by season (None for all seasons)
        stat_category: Filter by category (None for all categories)

    Returns:
        List of stat records ordered by season (desc), week (desc)

    Example:
        >>> # Get all passing stats for Patrick Mahomes
        >>> stats = get_player_stats(
        ...     sport="nfl",
        ...     player_id="00-0033873",  # Mahomes NFL ID
        ...     stat_category="passing"
        ... )
        >>> for s in stats:
        ...     print(f"Season {s['season']} Week {s['week']}: {s['stats']}")

    References:
        - idx_historical_stats_player index
        - REQ-DATA-005: Historical Statistics Storage
    """
    conditions = ["sport = %s", "player_id = %s"]
    params: list[Any] = [sport, player_id]

    if season is not None:
        conditions.append("season = %s")
        params.append(season)

    if stat_category:
        conditions.append("stat_category = %s")
        params.append(stat_category)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_stats
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, COALESCE(week, 0) DESC
    """  # noqa: S608
    return fetch_all(query, tuple(params))


def get_team_stats(
    sport: str,
    team_code: str,
    season: int | None = None,
    stat_category: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get all stats for a specific team.

    Retrieves team statistics across seasons, weeks, and categories.
    Excludes individual player stats (player_id IS NULL).

    Args:
        sport: Sport code (required)
        team_code: Team abbreviation (required, e.g., "KC", "DAL")
        season: Filter by season (None for all seasons)
        stat_category: Filter by category (None for all categories)

    Returns:
        List of stat records ordered by season (desc), week (desc)

    Example:
        >>> # Get all Chiefs defensive stats for 2024
        >>> stats = get_team_stats(
        ...     sport="nfl",
        ...     team_code="KC",
        ...     season=2024,
        ...     stat_category="team_defense"
        ... )
        >>> for s in stats:
        ...     print(f"Week {s['week']}: {s['stats']}")

    References:
        - idx_historical_stats_team index
        - REQ-DATA-006: Team Statistics Aggregation
    """
    conditions = ["sport = %s", "team_code = %s", "player_id IS NULL"]
    params: list[Any] = [sport, team_code]

    if season is not None:
        conditions.append("season = %s")
        params.append(season)

    if stat_category:
        conditions.append("stat_category = %s")
        params.append(stat_category)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_stats
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, COALESCE(week, 0) DESC
    """  # noqa: S608
    return fetch_all(query, tuple(params))


# =============================================================================
# HISTORICAL RANKINGS CRUD OPERATIONS
# =============================================================================
# Functions for historical_rankings table (Migration 0009)
# Used for storing team rankings from various polls and rating systems
# =============================================================================


def insert_historical_ranking(
    sport: str,
    season: int,
    week: int,
    team_code: str,
    rank: int,
    poll_type: str,
    source: str,
    previous_rank: int | None = None,
    points: int | None = None,
    first_place_votes: int | None = None,
    source_file: str | None = None,
) -> int:
    """
    Insert a single historical ranking record with UPSERT semantics.

    Uses INSERT ... ON CONFLICT based on the unique constraint
    (sport, season, week, team_code, poll_type) to handle re-imports.

    Args:
        sport: Sport code (nfl, ncaaf, nba, ncaab, nhl, mlb)
        season: Season year (e.g., 2024)
        week: Week number when ranking was released
        team_code: Team abbreviation (e.g., "KC", "ALA")
        rank: Ranking position (1 = best)
        poll_type: Type of poll (ap_poll, cfp, coaches, elo, power_ranking)
        source: Data source identifier (espn, fivethirtyeight, cfbd)
        previous_rank: Previous week's rank (None if unranked or first poll)
        points: Poll points received (for voting polls)
        first_place_votes: Number of first-place votes (for voting polls)
        source_file: Source filename for CSV-based imports

    Returns:
        historical_ranking_id of created/updated record

    Educational Note:
        Rankings differ from stats in that they have a natural unique constraint
        on (sport, season, week, team, poll_type). A team can only have one rank
        in a specific poll for a specific week. The UPSERT pattern allows safe
        re-imports without duplicates.

    Example:
        >>> ranking_id = insert_historical_ranking(
        ...     sport="ncaaf",
        ...     season=2024,
        ...     week=12,
        ...     team_code="UGA",
        ...     rank=1,
        ...     poll_type="ap_poll",
        ...     source="espn",
        ...     points=1525,
        ...     first_place_votes=45
        ... )

    References:
        - Migration 0009: historical_rankings table
        - uq_historical_rankings_team_poll_week unique constraint
        - ADR-106: Historical Data Collection Architecture
    """
    query = """
        INSERT INTO historical_rankings (
            sport, season, week, team_code, rank, previous_rank,
            points, first_place_votes, poll_type, source, source_file
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, week, team_code, poll_type)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            previous_rank = EXCLUDED.previous_rank,
            points = EXCLUDED.points,
            first_place_votes = EXCLUDED.first_place_votes,
            source = EXCLUDED.source,
            source_file = EXCLUDED.source_file
        RETURNING historical_ranking_id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                sport,
                season,
                week,
                team_code,
                rank,
                previous_rank,
                points,
                first_place_votes,
                poll_type,
                source,
                source_file,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["historical_ranking_id"])


def insert_historical_rankings_batch(
    records: list[dict[str, Any]],
    batch_size: int = 1000,
) -> tuple[int, int]:
    """
    Batch insert historical ranking records with progress tracking.

    Efficiently inserts multiple records using executemany with batching.
    Uses UPSERT semantics for idempotent re-imports.

    Args:
        records: List of ranking record dictionaries with keys:
            - sport, season, week, team_code, rank, poll_type, source
            - Optional: previous_rank, points, first_place_votes, source_file
        batch_size: Number of records per batch (default 1000)

    Returns:
        Tuple of (inserted_count, updated_count)

    Example:
        >>> records = [
        ...     {"sport": "ncaaf", "season": 2024, "week": 12, "team_code": "UGA",
        ...      "rank": 1, "poll_type": "ap_poll", "source": "espn", "points": 1525},
        ...     {"sport": "ncaaf", "season": 2024, "week": 12, "team_code": "OSU",
        ...      "rank": 2, "poll_type": "ap_poll", "source": "espn", "points": 1489},
        ... ]
        >>> inserted, updated = insert_historical_rankings_batch(records)

    References:
        - Issue #253: CRUD operations for historical tables
        - ADR-106: Historical Data Collection Architecture
    """
    if not records:
        return (0, 0)

    query = """
        INSERT INTO historical_rankings (
            sport, season, week, team_code, rank, previous_rank,
            points, first_place_votes, poll_type, source, source_file
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, week, team_code, poll_type)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            previous_rank = EXCLUDED.previous_rank,
            points = EXCLUDED.points,
            first_place_votes = EXCLUDED.first_place_votes,
            source = EXCLUDED.source,
            source_file = EXCLUDED.source_file
    """
    total_inserted = 0

    with get_cursor(commit=True) as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            params = [
                (
                    r["sport"],
                    r["season"],
                    r["week"],
                    r["team_code"],
                    r["rank"],
                    r.get("previous_rank"),
                    r.get("points"),
                    r.get("first_place_votes"),
                    r["poll_type"],
                    r["source"],
                    r.get("source_file"),
                )
                for r in batch
            ]
            cur.executemany(query, params)
            total_inserted += len(batch)

    return (total_inserted, 0)


def get_historical_rankings(
    sport: str,
    season: int,
    week: int | None = None,
    poll_type: str | None = None,
    team_code: str | None = None,
    top_n: int | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Query historical rankings with flexible filtering and pagination.

    Supports filtering by sport, season, week, poll type, team, and source.
    Can limit to top N teams (e.g., Top 25 AP Poll).

    Args:
        sport: Sport code (required)
        season: Season year (required)
        week: Filter by specific week (None for all weeks)
        poll_type: Filter by poll type (None for all poll types)
        team_code: Filter by team (None for all teams)
        top_n: Limit to top N ranked teams (e.g., 25 for AP Top 25)
        source: Filter by data source (None for all sources)
        limit: Maximum number of records to return (default: 100)
        offset: Number of records to skip for pagination (default: 0)

    Returns:
        List of ranking records ordered by week (desc), rank (asc)

    Example:
        >>> # Get AP Poll Top 25 for week 12
        >>> rankings = get_historical_rankings(
        ...     sport="ncaaf", season=2024, week=12,
        ...     poll_type="ap_poll", top_n=25
        ... )
        >>> # Pagination: get page 2 (records 100-199)
        >>> page2 = get_historical_rankings(sport="ncaaf", season=2024, limit=100, offset=100)

    References:
        - idx_historical_rankings_poll index
        - idx_historical_rankings_rank index
        - REQ-DATA-007: Historical Rankings Storage
    """
    conditions = ["sport = %s", "season = %s"]
    params: list[Any] = [sport, season]

    if week is not None:
        conditions.append("week = %s")
        params.append(week)

    if poll_type:
        conditions.append("poll_type = %s")
        params.append(poll_type)

    if team_code:
        conditions.append("team_code = %s")
        params.append(team_code)

    if top_n is not None:
        conditions.append("rank <= %s")
        params.append(top_n)

    if source:
        conditions.append("source = %s")
        params.append(source)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_rankings
        WHERE {" AND ".join(conditions)}
        ORDER BY week DESC, rank ASC
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


def get_team_ranking_history(
    sport: str,
    team_code: str,
    poll_type: str,
    season: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get ranking history for a specific team in a specific poll.

    Retrieves how a team's ranking changed over time in a particular poll.
    Useful for tracking team performance and generating ranking charts.

    Args:
        sport: Sport code (required)
        team_code: Team abbreviation (required)
        poll_type: Type of poll (required, e.g., "ap_poll", "cfp")
        season: Filter by season (None for all seasons)

    Returns:
        List of ranking records ordered by season (desc), week (asc)

    Example:
        >>> # Get Georgia's AP Poll history for 2024
        >>> history = get_team_ranking_history(
        ...     sport="ncaaf",
        ...     team_code="UGA",
        ...     poll_type="ap_poll",
        ...     season=2024
        ... )
        >>> for r in history:
        ...     change = ""
        ...     if r['previous_rank']:
        ...         diff = r['previous_rank'] - r['rank']
        ...         change = f" (+{diff})" if diff > 0 else f" ({diff})" if diff < 0 else ""
        ...     print(f"Week {r['week']}: #{r['rank']}{change}")

    References:
        - idx_historical_rankings_team index
        - REQ-DATA-007: Historical Rankings Storage
    """
    conditions = ["sport = %s", "team_code = %s", "poll_type = %s"]
    params: list[Any] = [sport, team_code, poll_type]

    if season is not None:
        conditions.append("season = %s")
        params.append(season)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_rankings
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, week ASC
    """  # noqa: S608
    return fetch_all(query, tuple(params))


# =============================================================================
# Scheduler Status Operations (IPC via Database)
# =============================================================================
# These operations enable cross-process communication for scheduler status.
# The problem: `scheduler status` runs in a separate process from the scheduler
# itself, so it can't see in-memory state. Solution: store status in database.
#
# References:
#   - Migration 0012: scheduler_status table
#   - Issue #255: Scheduler status shows "not running" even when running
#   - ADR-TBD: Cross-Process IPC Strategy
# =============================================================================


def upsert_scheduler_status(
    host_id: str,
    service_name: str,
    *,
    status: str | None = None,
    pid: int | None = None,
    started_at: datetime | None = None,
    stats: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """
    Insert or update scheduler service status.

    This is the primary function for schedulers to report their status. It uses
    PostgreSQL's UPSERT (INSERT ... ON CONFLICT UPDATE) for atomic operation.

    Why UPSERT?
    -----------
    The scheduler might be starting for the first time (INSERT) or restarting
    after a crash (UPDATE). UPSERT handles both cases atomically without race
    conditions that would occur with "check then insert/update" logic.

    Args:
        host_id: Hostname running the service (e.g., 'DESKTOP-ABC123')
        service_name: Service identifier (e.g., 'espn', 'kalshi_rest', 'kalshi_ws')
        status: Current status ('starting', 'running', 'stopping', 'stopped', 'failed')
        pid: Process ID of the running service
        started_at: When the service was started
        stats: JSON with service-specific metrics (polls, errors, etc.)
        config: JSON with service configuration
        error_message: Last error message if status is 'failed'

    Returns:
        True if operation succeeded, False otherwise

    Example:
        >>> # Scheduler starting up
        >>> upsert_scheduler_status(
        ...     host_id=socket.gethostname(),
        ...     service_name="espn",
        ...     status="starting",
        ...     pid=os.getpid(),
        ...     started_at=datetime.now(timezone.utc),
        ...     config={"poll_interval_seconds": 60}
        ... )

        >>> # Scheduler heartbeat (update stats, refresh timestamp)
        >>> upsert_scheduler_status(
        ...     host_id=socket.gethostname(),
        ...     service_name="espn",
        ...     status="running",
        ...     stats={"polls": 142, "errors": 0, "games_updated": 8}
        ... )

    Educational Note:
        The last_heartbeat column is automatically set to NOW() on every upsert.
        This allows other processes to detect stale/crashed services by checking
        if last_heartbeat is older than a threshold (e.g., 2 minutes).

    References:
        - Migration 0012: scheduler_status table schema
        - REQ-OBSERV-001: Observability Requirements
    """
    # Build dynamic INSERT columns and ON CONFLICT UPDATE clause
    # Uses psycopg2-style %s placeholders
    insert_cols = ["host_id", "service_name", "last_heartbeat"]
    insert_vals = ["%s", "%s", "NOW()"]

    if status is not None:
        insert_cols.append("status")
        insert_vals.append("%s")
    if pid is not None:
        insert_cols.append("pid")
        insert_vals.append("%s")
    if started_at is not None:
        insert_cols.append("started_at")
        insert_vals.append("%s")
    if stats is not None:
        insert_cols.append("stats")
        insert_vals.append("%s")
    if config is not None:
        insert_cols.append("config")
        insert_vals.append("%s")
    if error_message is not None:
        insert_cols.append("error_message")
        insert_vals.append("%s")

    # Build SET clause with %s placeholders
    set_clause_parts = ["last_heartbeat = NOW()"]
    if status is not None:
        set_clause_parts.append("status = EXCLUDED.status")
    if pid is not None:
        set_clause_parts.append("pid = EXCLUDED.pid")
    if started_at is not None:
        set_clause_parts.append("started_at = EXCLUDED.started_at")
    if stats is not None:
        set_clause_parts.append("stats = EXCLUDED.stats")
    if config is not None:
        set_clause_parts.append("config = EXCLUDED.config")
    if error_message is not None:
        set_clause_parts.append("error_message = EXCLUDED.error_message")

    query = f"""
        INSERT INTO scheduler_status ({", ".join(insert_cols)})
        VALUES ({", ".join(insert_vals)})
        ON CONFLICT (host_id, service_name)
        DO UPDATE SET {", ".join(set_clause_parts)}
    """  # noqa: S608

    # Build params list: host_id, service_name, then optional params
    all_params: list[Any] = [host_id, service_name]
    if status is not None:
        all_params.append(status)
    if pid is not None:
        all_params.append(pid)
    if started_at is not None:
        all_params.append(started_at)
    if stats is not None:
        all_params.append(json.dumps(stats, cls=DecimalEncoder))
    if config is not None:
        all_params.append(json.dumps(config, cls=DecimalEncoder))
    if error_message is not None:
        all_params.append(error_message)

    with get_cursor() as cur:
        cur.execute(query, tuple(all_params))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0) > 0


def get_scheduler_status(
    host_id: str,
    service_name: str,
) -> dict[str, Any] | None:
    """
    Get status for a specific scheduler service.

    Args:
        host_id: Hostname running the service
        service_name: Service identifier

    Returns:
        Dictionary with service status, or None if not found

    Example:
        >>> status = get_scheduler_status("DESKTOP-ABC123", "espn")
        >>> if status:
        ...     print(f"ESPN scheduler: {status['status']}")
        ...     print(f"Last heartbeat: {status['last_heartbeat']}")
        ...     if status['stats']:
        ...         print(f"Polls: {status['stats'].get('polls', 0)}")

    Educational Note:
        The returned stats and config are automatically parsed from JSON
        back to Python dictionaries by psycopg2's JSON handling.

    References:
        - Migration 0012: scheduler_status table schema
    """
    query = """
        SELECT host_id, service_name, pid, status, started_at, last_heartbeat,
               stats, config, error_message, created_at, updated_at
        FROM scheduler_status
        WHERE host_id = %s AND service_name = %s
    """
    return fetch_one(query, (host_id, service_name))


def list_scheduler_services(
    *,
    host_id: str | None = None,
    status_filter: str | None = None,
    include_stale: bool = True,
    stale_threshold_seconds: int = 120,
) -> list[dict[str, Any]]:
    """
    List all scheduler services and their status.

    This is the primary function for CLI status display. It can filter by
    host, status, and optionally mark services with old heartbeats as stale.

    Args:
        host_id: Filter to specific host (None for all hosts)
        status_filter: Filter by status ('running', 'stopped', etc.)
        include_stale: If True, includes a 'is_stale' field in results
        stale_threshold_seconds: Heartbeat age to consider service stale (default 2 min)

    Returns:
        List of service status dictionaries, ordered by host_id, service_name

    Example:
        >>> # Get all services on this host
        >>> services = list_scheduler_services(host_id=socket.gethostname())
        >>> for svc in services:
        ...     status = svc['status']
        ...     if svc.get('is_stale') and status == 'running':
        ...         status = 'stale (crashed?)'
        ...     print(f"{svc['service_name']}: {status}")

    Educational Note:
        The 'is_stale' field helps detect crashed services. If a service
        status is 'running' but last_heartbeat is >2 minutes old, the
        service likely crashed without updating its status to 'stopped'.

    References:
        - Migration 0012: scheduler_status table schema
        - REQ-OBSERV-001: Observability Requirements
    """
    conditions = []
    params: list[Any] = []

    if host_id is not None:
        conditions.append("host_id = %s")
        params.append(host_id)

    if status_filter is not None:
        conditions.append("status = %s")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Include stale detection in query if requested
    # Note: We use string interpolation for the interval value because PostgreSQL
    # INTERVAL syntax doesn't support parameter substitution in all drivers
    stale_expr = ""
    if include_stale:
        stale_expr = (
            f", (last_heartbeat < NOW() - INTERVAL '{stale_threshold_seconds} seconds') AS is_stale"
        )

    # S608 false positive: conditions built from validated inputs
    query = f"""
        SELECT host_id, service_name, pid, status, started_at, last_heartbeat,
               stats, config, error_message, created_at, updated_at
               {stale_expr}
        FROM scheduler_status
        {where_clause}
        ORDER BY host_id, service_name
    """  # noqa: S608

    return fetch_all(query, tuple(params))


def cleanup_stale_schedulers(
    stale_threshold_seconds: int = 120,
    host_id: str | None = None,
) -> int:
    """
    Mark stale scheduler services as 'failed'.

    A service is considered stale if:
    1. Its status is 'running' or 'starting'
    2. Its last_heartbeat is older than the threshold

    This function should be called periodically (e.g., by a monitoring process)
    to clean up services that crashed without graceful shutdown.

    Args:
        stale_threshold_seconds: How old heartbeat must be to consider stale
        host_id: Only clean up services on specific host (None for all)

    Returns:
        Number of services marked as failed

    Example:
        >>> # Clean up crashed services on this host
        >>> import socket
        >>> cleaned = cleanup_stale_schedulers(
        ...     stale_threshold_seconds=120,
        ...     host_id=socket.gethostname()
        ... )
        >>> if cleaned > 0:
        ...     print(f"Marked {cleaned} crashed services as failed")

    Educational Note:
        This implements a "lease renewal" pattern common in distributed systems.
        Services must renew their lease (heartbeat) periodically to prove they're
        alive. If the lease expires, the service is considered dead.

    References:
        - Migration 0012: scheduler_status table schema
        - Pattern: Lease renewal / heartbeat monitoring
    """
    conditions = [
        "status IN ('running', 'starting')",
        "last_heartbeat < NOW() - INTERVAL '%s seconds'",
    ]
    params: list[Any] = [stale_threshold_seconds]

    if host_id is not None:
        conditions.append("host_id = %s")
        params.append(host_id)

    # S608 false positive: conditions are hardcoded strings
    query = f"""
        UPDATE scheduler_status
        SET status = 'failed',
            error_message = 'Service heartbeat expired (assumed crashed)',
            updated_at = NOW()
        WHERE {" AND ".join(conditions)}
    """  # noqa: S608

    with get_cursor() as cur:
        cur.execute(query, tuple(params))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0)


def delete_scheduler_status(host_id: str, service_name: str) -> bool:
    """
    Delete a scheduler status record.

    Use this when a service is being completely removed (not just stopped).
    For normal shutdown, use upsert_scheduler_status with status='stopped'.

    Args:
        host_id: Hostname running the service
        service_name: Service identifier

    Returns:
        True if record was deleted, False if not found

    Example:
        >>> # Remove old service record during cleanup
        >>> deleted = delete_scheduler_status("OLD-HOST", "legacy_service")

    References:
        - Migration 0012: scheduler_status table schema
    """
    query = """
        DELETE FROM scheduler_status
        WHERE host_id = %s AND service_name = %s
    """
    with get_cursor() as cur:
        cur.execute(query, (host_id, service_name))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0) > 0


# =============================================================================
# Elo Rating Operations
# =============================================================================
# CRUD operations for managing team Elo ratings across the multi-table
# Elo architecture:
#
#   - teams.current_elo_rating: Live/current rating (updated after each game)
#   - historical_elo: Seeded from external sources (FiveThirtyEight, etc.)
#   - elo_calculation_log: Audit trail of every Elo computation (PRIMARY)
#
# Note: elo_rating_history was REMOVED in migration 0015 (2025-12-26).
#       It was superseded by elo_calculation_log which provides:
#         1. Game-centric view (both teams per row) vs team-centric
#         2. Full audit trail with parameters (K-factor, MOV, expected scores)
#         3. Links to source game (game_states or historical_games)
#
#   To get team-centric view from elo_calculation_log:
#     SELECT game_date, home_post_elo as rating FROM elo_calculation_log
#     WHERE home_team_id = :team_id
#     UNION ALL
#     SELECT game_date, away_post_elo as rating FROM elo_calculation_log
#     WHERE away_team_id = :team_id
#     ORDER BY game_date
#
# References:
#   - Migration 0001: teams.current_elo_rating (elo_rating_history removed)
#   - Migration 0005: historical_elo
#   - Migration 0013: elo_calculation_log, historical_epa
#   - Migration 0015: Dropped deprecated elo_rating_history table
#   - ADR-109: Elo Rating Computation Engine Architecture
#   - Issue #273: Comprehensive Elo Rating Computation Module
#   - Issue #277: Remove deprecated elo_rating_history table
# =============================================================================


def update_team_elo_rating(
    team_id: int,
    new_rating: Decimal,
) -> bool:
    """
    Update a team's current Elo rating in the teams table.

    This function syncs the computed Elo rating to the teams table after
    processing a game. It's the final step in the Elo computation pipeline:

        historical_elo (bootstrap) -> elo_calculation_log (audit)
            -> teams.current_elo_rating (LIVE)

    Note: elo_rating_history was removed in migration 0015 (superseded by elo_calculation_log).

    Args:
        team_id: Primary key of the team in the teams table
        new_rating: New Elo rating value (typically 1000-2000 range)

    Returns:
        True if update succeeded, False if team not found

    Example:
        >>> # After computing new Elo from game result
        >>> success = update_team_elo_rating(team_id=42, new_rating=Decimal("1567.25"))
        >>> if success:
        ...     print("Team Elo updated successfully")

    Educational Note:
        Elo ratings are stored as DECIMAL(10,2) for precision. The valid range
        is 0-3000 per the CHECK constraint in Migration 0001. Typical ratings:
        - 1500: Average team (starting point)
        - 1600-1700: Good team (playoff contender)
        - 1700+: Elite team (championship caliber)
        - Below 1400: Rebuilding/struggling team

    References:
        - Migration 0001: teams.current_elo_rating column
        - ADR-109: Elo Rating Computation Engine Architecture
    """
    query = """
        UPDATE teams
        SET current_elo_rating = %s,
            updated_at = NOW()
        WHERE team_id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (new_rating, team_id))
        return int(cur.rowcount or 0) > 0


def get_team_elo_rating(team_id: int) -> Decimal | None:
    """
    Get a team's current Elo rating from the teams table.

    Args:
        team_id: Primary key of the team

    Returns:
        Current Elo rating as Decimal, or None if team not found

    Example:
        >>> rating = get_team_elo_rating(team_id=42)
        >>> if rating:
        ...     print(f"Team Elo: {rating}")
    """
    result = fetch_one(
        "SELECT current_elo_rating FROM teams WHERE team_id = %s",
        (team_id,),
    )
    if result and result.get("current_elo_rating"):
        return Decimal(str(result["current_elo_rating"]))
    return None


def get_team_elo_by_code(
    team_code: str,
    sport: str | None = None,
) -> Decimal | None:
    """
    Get a team's current Elo rating by team code.

    Args:
        team_code: Team abbreviation (e.g., 'KC', 'LAL', 'BOS')
        sport: Optional sport filter (e.g., 'nfl', 'nba')

    Returns:
        Current Elo rating as Decimal, or None if team not found

    Example:
        >>> rating = get_team_elo_by_code("KC", sport="nfl")
        >>> print(f"Chiefs Elo: {rating}")
    """
    if sport:
        result = fetch_one(
            "SELECT current_elo_rating FROM teams WHERE team_code = %s AND sport = %s",
            (team_code, sport),
        )
    else:
        result = fetch_one(
            "SELECT current_elo_rating FROM teams WHERE team_code = %s",
            (team_code,),
        )
    if result and result.get("current_elo_rating"):
        return Decimal(str(result["current_elo_rating"]))
    return None


def insert_elo_calculation_log(
    sport: str,
    game_date: date,
    home_team_code: str,
    away_team_code: str,
    home_score: int,
    away_score: int,
    home_elo_before: Decimal,
    away_elo_before: Decimal,
    k_factor: int,
    home_advantage: Decimal,
    home_expected: Decimal,
    away_expected: Decimal,
    home_actual: Decimal,
    away_actual: Decimal,
    home_elo_change: Decimal,
    away_elo_change: Decimal,
    home_elo_after: Decimal,
    away_elo_after: Decimal,
    calculation_source: str,
    *,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    game_state_id: int | None = None,
    historical_game_id: int | None = None,
    mov_multiplier: Decimal | None = None,
    home_epa_adjustment: Decimal | None = None,
    away_epa_adjustment: Decimal | None = None,
    calculation_version: str = "1.0",
) -> int:
    """
    Insert a record into the elo_calculation_log audit table.

    This function captures every Elo calculation for debugging, compliance,
    and historical analysis. It records all inputs and outputs of the
    Elo formula including K-factor, home advantage, and EPA adjustments.

    Args:
        sport: Sport code ('nfl', 'nba', 'nhl', 'mlb', etc.)
        game_date: Date of the game
        home_team_code: Home team abbreviation
        away_team_code: Away team abbreviation
        home_score: Home team final score
        away_score: Away team final score
        home_elo_before: Home team Elo before game
        away_elo_before: Away team Elo before game
        k_factor: K-factor used (NFL: 20, NBA: 20, NHL: 6, MLB: 4)
        home_advantage: Home advantage points applied (NFL: 65, NBA: 100)
        home_expected: Expected score for home team (0.0 to 1.0)
        away_expected: Expected score for away team (0.0 to 1.0)
        home_actual: Actual score for home team (1.0=win, 0.5=tie, 0.0=loss)
        away_actual: Actual score for away team (1.0=win, 0.5=tie, 0.0=loss)
        home_elo_change: Change in home team Elo
        away_elo_change: Change in away team Elo
        home_elo_after: Home team Elo after game
        away_elo_after: Away team Elo after game
        calculation_source: How triggered ('bootstrap', 'realtime', 'backfill', 'manual')
        home_team_id: FK to teams.team_id (optional, for live games)
        away_team_id: FK to teams.team_id (optional, for live games)
        game_state_id: FK to game_states.game_state_id (optional)
        historical_game_id: FK to historical_games.game_id (optional)
        mov_multiplier: Margin of victory multiplier (optional)
        home_epa_adjustment: EPA-based adjustment for home team (NFL only)
        away_epa_adjustment: EPA-based adjustment for away team (NFL only)
        calculation_version: Version of Elo algorithm used (default: "1.0")

    Returns:
        elo_log_id of the inserted record

    Example:
        >>> log_id = insert_elo_calculation_log(
        ...     sport="nfl",
        ...     game_date=date(2024, 9, 8),
        ...     home_team_code="KC",
        ...     away_team_code="BAL",
        ...     home_score=27,
        ...     away_score=20,
        ...     home_elo_before=Decimal("1650"),
        ...     away_elo_before=Decimal("1620"),
        ...     k_factor=20,
        ...     home_advantage=Decimal("65"),
        ...     home_expected=Decimal("0.5714"),
        ...     away_expected=Decimal("0.4286"),
        ...     home_actual=Decimal("1.0"),
        ...     away_actual=Decimal("0.0"),
        ...     home_elo_change=Decimal("8.57"),
        ...     away_elo_change=Decimal("-8.57"),
        ...     home_elo_after=Decimal("1658.57"),
        ...     away_elo_after=Decimal("1611.43"),
        ...     calculation_source="realtime",
        ... )

    Educational Note:
        The Elo calculation log provides a complete audit trail:
        1. Pre-game state (both teams' ratings)
        2. Parameters used (K-factor, home advantage, MOV multiplier)
        3. Expected vs actual outcomes
        4. Post-game state (new ratings after adjustment)

        This allows debugging of rating discrepancies and analysis of
        the Elo system's predictive accuracy over time.

    References:
        - Migration 0013: elo_calculation_log table schema
        - ADR-109: Elo Rating Computation Engine Architecture
    """
    query = """
        INSERT INTO elo_calculation_log (
            sport, game_date, home_team_id, away_team_id,
            game_state_id, historical_game_id,
            home_team_code, away_team_code,
            home_score, away_score,
            home_elo_before, away_elo_before,
            k_factor, home_advantage, mov_multiplier,
            home_expected, away_expected,
            home_actual, away_actual,
            home_elo_change, away_elo_change,
            home_elo_after, away_elo_after,
            home_epa_adjustment, away_epa_adjustment,
            calculation_source, calculation_version
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING elo_log_id
    """
    params = (
        sport,
        game_date,
        home_team_id,
        away_team_id,
        game_state_id,
        historical_game_id,
        home_team_code,
        away_team_code,
        home_score,
        away_score,
        home_elo_before,
        away_elo_before,
        k_factor,
        home_advantage,
        mov_multiplier,
        home_expected,
        away_expected,
        home_actual,
        away_actual,
        home_elo_change,
        away_elo_change,
        home_elo_after,
        away_elo_after,
        home_epa_adjustment,
        away_epa_adjustment,
        calculation_source,
        calculation_version,
    )
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["elo_log_id"])


def get_elo_calculation_logs(
    sport: str,
    start_date: date | None = None,
    end_date: date | None = None,
    team_code: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Retrieve Elo calculation logs with optional filters.

    Args:
        sport: Sport code to filter by
        start_date: Start of date range (optional)
        end_date: End of date range (optional)
        team_code: Filter by team (matches home or away)
        limit: Maximum records to return (default 100)

    Returns:
        List of Elo calculation log records

    Example:
        >>> logs = get_elo_calculation_logs(
        ...     sport="nfl",
        ...     start_date=date(2024, 9, 1),
        ...     team_code="KC",
        ... )
        >>> for log in logs:
        ...     print(f"{log['game_date']}: {log['home_team_code']} vs {log['away_team_code']}")
    """
    conditions = ["sport = %s"]
    params: list[Any] = [sport]

    if start_date:
        conditions.append("game_date >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("game_date <= %s")
        params.append(end_date)

    if team_code:
        conditions.append("(home_team_code = %s OR away_team_code = %s)")
        params.extend([team_code, team_code])

    params.append(limit)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM elo_calculation_log
        WHERE {" AND ".join(conditions)}
        ORDER BY game_date DESC, created_at DESC
        LIMIT %s
    """  # noqa: S608

    return fetch_all(query, tuple(params))
