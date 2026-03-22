"""
CRUD operations for Precog database with SCD Type 2 versioning support.

SCD Type 2 (Slowly Changing Dimension) Explained:
--------------------------------------------------
Imagine a Wikipedia article with full edit history. Instead of OVERWRITING the article
(losing the old version), Wikipedia saves each edit as a new version. You can:
- View the current version (what users see now)
- View historical versions (what it looked like on 2023-05-15)
- Compare changes between versions

We do the SAME thing for market snapshots and positions:

**Traditional Database (Loses History):**
```sql
UPDATE market_snapshots SET yes_ask_price = 0.5500 WHERE market_id = 42
-- Old price (0.5200) is GONE FOREVER
-- Can't backtest strategies with historical prices
-- Can't audit "what price did we see at 2PM yesterday?"
```

**SCD Type 2 (Preserves History):**
```sql
-- Step 1: Mark current snapshot as historical
UPDATE market_snapshots SET row_current_ind = FALSE, row_end_ts = NOW()
WHERE market_id = 42 AND row_current_ind = TRUE

-- Step 2: Insert new snapshot version
INSERT INTO market_snapshots (..., row_current_ind = TRUE, row_start_ts = NOW())
VALUES (42, 0.5500, ...)
-- Old price (0.5200) preserved with timestamps
-- Can backtest with exact historical prices
-- Full audit trail for compliance
```

Visual Example - Market Snapshot Price History:
```
┌───────────┬───────────────┬─────────────────────┬─────────────────────┬────────────────┐
│ market_id │yes_ask_price  │ row_start_ts        │ row_end_ts          │row_current_ind │
├───────────┼───────────────┼─────────────────────┼─────────────────────┼────────────────┤
│  42       │ 0.5200        │ 2024-01-01 10:00:00 │ 2024-01-01 11:00:00 │ FALSE (old)    │
│  42       │ 0.5350        │ 2024-01-01 11:00:00 │ 2024-01-01 13:00:00 │ FALSE (old)    │
│  42       │ 0.5500        │ 2024-01-01 13:00:00 │ NULL                │ TRUE (current) │
└───────────┴───────────────┴─────────────────────┴─────────────────────┴────────────────┘

Query for CURRENT price:
    SELECT * FROM market_snapshots WHERE market_id = 42 AND row_current_ind = TRUE
    -> Returns 0.5500 (latest version only)

Query for HISTORICAL prices:
    SELECT * FROM market_snapshots WHERE market_id = 42 ORDER BY row_start_ts
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
    SELECT yes_ask_price, row_start_ts, row_end_ts
    FROM market_snapshots ms
    JOIN markets m ON ms.market_id = m.id
    WHERE m.ticker = %s
    ORDER BY ms.row_start_ts DESC
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
market_pk = create_market(
    platform_id="kalshi",
    ticker="NFL-KC-YES",
    yes_ask_price=Decimal("0.5200"),
    no_ask_price=Decimal("0.4800")
)

# Get current market data (dimension + latest snapshot)
market = get_current_market("NFL-KC-YES")  # Returns latest version only

# Update market price (creates new snapshot version)
new_id = update_market_with_versioning(
    ticker="NFL-KC-YES",
    yes_ask_price=Decimal("0.5500")
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
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, cast

import psycopg2.errors

from .connection import fetch_all, fetch_one, get_cursor

logger = logging.getLogger(__name__)

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
        >>> create_market(yes_ask_price=0.5)  # Executes (float contamination!)

        With runtime validation:
        >>> create_market(yes_ask_price=0.5)  # TypeError: yes_ask_price must be Decimal

        Why this matters:
        - Prevents float contamination (0.5 != Decimal("0.5"))
        - Ensures sub-penny precision preserved (0.4975 stored exactly)
        - Catches type errors early (at function call, not database INSERT)

    Example:
        >>> price = validate_decimal(Decimal("0.5200"), "yes_ask_price")
        >>> # Returns Decimal("0.5200")

        >>> price = validate_decimal(0.5200, "yes_ask_price")
        >>> # TypeError: yes_ask_price must be Decimal, got float
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
    Get a series by series_id (business key).

    Series represent recurring market groups (e.g., "NFL Game Markets" contains
    all individual game betting markets). This is the first level in the
    Kalshi hierarchy: Series -> Events -> Markets.

    Args:
        series_id: The series business key (e.g., "KXNFLGAME"). This is the
            human-readable identifier from the Kalshi API, NOT the surrogate
            integer PK.

    Returns:
        Dict containing series data if found, None otherwise.
        Keys: id, series_id, platform_id, external_id, category, subcategory,
              title, frequency, tags, metadata, created_at, updated_at

    Example:
        >>> series = get_series("KXNFLGAME")
        >>> if series:
        ...     print(f"Found: {series['title']} (internal id: {series['id']})")
        ...     print(f"Tags: {series['tags']}")  # ['Football']
        ... else:
        ...     print("Series not found")

    Educational Note:
        The series table uses a surrogate integer PK (id) for internal identity
        and foreign key references. The series_id VARCHAR column is kept as a
        UNIQUE business key for human readability and API compatibility.

        The `tags` column (TEXT[]) is particularly useful for sport filtering:
        - ["Football"] -> NFL, NCAAF
        - ["Basketball"] -> NBA, NCAAB, NCAAW
        - ["Hockey"] -> NHL

        Using PostgreSQL arrays with GIN index enables efficient queries:
        SELECT * FROM series WHERE 'Football' = ANY(tags)

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
        - src/precog/api_connectors/kalshi_client.py (get_series, get_sports_series)
        - Migration 0019: Added surrogate PK, demoted series_id to business key
    """
    query = """
        SELECT id, series_id, platform_id, external_id, category, subcategory,
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
        SELECT id, series_id, platform_id, external_id, category, subcategory,
               title, frequency, tags, metadata, created_at, updated_at
        FROM series
        {where_clause}
        ORDER BY id
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
) -> int:
    """
    Create a new series record.

    Series are the top-level grouping in Kalshi's market hierarchy:
    Series -> Events -> Markets. Each series represents a category of
    related markets (e.g., "NFL Game Markets" or "Presidential Election").

    Args:
        series_id: Unique business key (e.g., "KXNFLGAME"). Stored as
            VARCHAR(100) UNIQUE, but the surrogate integer PK (id) is
            used for all internal references and FK relationships.
        platform_id: Foreign key to platforms table (e.g., 'kalshi')
        external_id: External ID from the platform API
        category: Series category - one of: 'sports', 'politics',
                  'entertainment', 'economics', 'weather', 'other'
        title: Human-readable series title
        subcategory: Optional subcategory (e.g., 'nfl', 'nba')
        frequency: Optional frequency from Kalshi API (e.g., 'daily', 'weekly', 'event', 'custom')
        tags: Optional list of tags for filtering (e.g., ['Football'])
        metadata: Optional additional metadata as JSONB

    Returns:
        Integer surrogate PK (id) of the created series

    Raises:
        psycopg2.IntegrityError: If series_id already exists, platform_id
            invalid, or (platform_id, external_id) pair already exists

    Example:
        >>> series_pk = create_series(
        ...     series_id="KXNFLGAME",
        ...     platform_id="kalshi",
        ...     external_id="KXNFLGAME",
        ...     category="sports",
        ...     title="NFL Game Markets",
        ...     subcategory="nfl",
        ...     frequency="daily",
        ...     tags=["Football"]
        ... )
        >>> print(f"Created series with internal id: {series_pk}")

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
        - Migration 0019: Added surrogate PK (id SERIAL)
    """
    query = """
        INSERT INTO series (
            series_id, platform_id, external_id, category, subcategory,
            title, frequency, tags, metadata, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING id
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
        return cast("int", result["id"])


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
        ...     frequency="daily"
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
) -> tuple[int, bool]:
    """
    Get an existing series or create it if it doesn't exist.

    This upsert pattern is essential for polling services that repeatedly
    fetch data from external APIs. When the same series appears in multiple
    API responses, this function ensures we don't fail on duplicate inserts.

    Args:
        series_id: Business key (e.g., "KXNFLGAME") used for lookup
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
        Tuple of (id, created) where id is the integer surrogate PK and
        created is True if series was newly created, False if it already existed.

    Example:
        >>> series_pk, created = get_or_create_series(
        ...     series_id="KXNFLGAME",
        ...     platform_id="kalshi",
        ...     external_id="KXNFLGAME",
        ...     category="sports",
        ...     title="NFL Game Markets",
        ...     tags=["Football"]
        ... )
        >>> if created:
        ...     print(f"Created new series (id={series_pk})")
        ... else:
        ...     print(f"Series already exists (id={series_pk})")

    Educational Note:
        This pattern is critical for the KalshiPoller service. When syncing
        series data before markets, the poller calls get_or_create_series()
        for each series returned by the API. This ensures:
        1. New series are created automatically
        2. Existing series are optionally updated with fresh data
        3. No duplicate insert errors occur

        The returned integer PK is used by downstream callers (e.g., the
        poller) to set events.series_internal_id when creating events.

        The update_if_exists flag allows the caller to control whether
        existing records should be refreshed with API data. Set to False
        if you only want to create missing records without modifying existing.

    Reference:
        - src/precog/schedulers/kalshi_poller.py
        - Pattern similar to get_or_create_event()
        - Migration 0019: series now uses surrogate integer PK
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
        return cast("int", existing["id"]), False

    # Create new series - returns integer surrogate PK
    new_id = create_series(
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
    return new_id, True


# =============================================================================
# EVENT OPERATIONS
# =============================================================================


def get_event(event_id: str) -> dict[str, Any] | None:
    """
    Get an event by its business key (event_id VARCHAR).

    Args:
        event_id: The event business key (UNIQUE, from Kalshi API).
            Note: this is NOT the integer surrogate PK. The surrogate PK
            is available in the returned dict as result["id"].

    Returns:
        Dictionary with event data (including 'id' surrogate PK), or None if not found

    Example:
        >>> event = get_event("KXNFL-24DEC22-KC-SEA")
        >>> if event:
        ...     print(event['id'])     # Integer surrogate PK
        ...     print(event['title'])  # Event title

    Reference:
        - Migration 0020: event_id demoted to UNIQUE business key, id is SERIAL PK
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
    series_internal_id: int | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> int:
    """
    Create a new event record.

    Events are the parent entities for markets. Each market belongs to an event,
    enforced via foreign key constraint (markets.event_internal_id -> events.id).

    Args:
        event_id: Unique event business key (VARCHAR, from Kalshi API)
        platform_id: Foreign key to platforms table (e.g., 'kalshi')
        external_id: External ID from the platform API
        category: Event category ('sports', 'politics', 'entertainment',
                  'economics', 'weather', 'other')
        title: Event title/description
        series_internal_id: Optional integer FK to series(id). This is the
            surrogate PK from the series table (migration 0019), NOT the
            VARCHAR business key.
        subcategory: Optional subcategory (e.g., 'nfl', 'nba')
        description: Optional detailed description
        start_time: Optional event start time (ISO format)
        end_time: Optional event end time (ISO format)
        status: Optional status ('scheduled', 'live', 'final', 'cancelled', 'postponed')
        metadata: Optional additional metadata as JSONB

    Returns:
        Integer surrogate PK (id) of the created event. Callers use this
        to set markets.event_internal_id FK.

    Raises:
        psycopg2.IntegrityError: If event_id already exists or platform_id invalid

    Example:
        >>> event_pk = create_event(
        ...     event_id="KXNFL-24DEC22-KC-SEA",
        ...     platform_id="kalshi",
        ...     external_id="KXNFL-24DEC22-KC-SEA",
        ...     category="sports",
        ...     title="Chiefs vs Seahawks - Dec 22, 2024",
        ...     series_internal_id=42,
        ...     subcategory="nfl"
        ... )
        >>> # event_pk is an integer, e.g. 7

    Educational Note:
        Events represent real-world occurrences (games, elections, etc.) that
        markets are based on. One event can have multiple markets:
        - Event: "Chiefs vs Seahawks - Dec 22"
        - Markets: "Chiefs to win", "Total points over 45.5", "Kelce 100+ yards"

        The foreign key constraint ensures data integrity - you can't create
        a market for a non-existent event.

    Reference:
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md
        - Migration 0019: events.series_internal_id replaces events.series_id
        - Migration 0020: events.id SERIAL PK, markets.event_internal_id INTEGER FK
    """
    query = """
        INSERT INTO events (
            event_id, platform_id, series_internal_id, external_id,
            category, subcategory, title, description,
            start_time, end_time, status, metadata,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING id
    """

    params = (
        event_id,
        platform_id,
        series_internal_id,
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
        return cast("int", result["id"])


def get_or_create_event(
    event_id: str,
    platform_id: str,
    external_id: str,
    category: str,
    title: str,
    series_internal_id: int | None = None,
    subcategory: str | None = None,
    description: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    metadata: dict | None = None,
) -> tuple[int, bool]:
    """
    Get an existing event or create it if it doesn't exist.

    This is a convenience function that combines get_event() and create_event()
    to handle the common pattern of "upsert" behavior for events.

    Args:
        event_id: Unique event business key (VARCHAR, from Kalshi API)
        platform_id: Foreign key to platforms table
        external_id: External ID from the platform API
        category: Event category
        title: Event title
        series_internal_id: Optional integer FK to series(id) surrogate PK
        subcategory: Optional subcategory
        description: Optional description
        start_time: Optional start time
        end_time: Optional end time
        status: Optional status
        metadata: Optional metadata

    Returns:
        Tuple of (id, created) where id is the integer surrogate PK and
        created is True if event was newly created, False if it already existed.
        Callers use the returned id to set markets.event_internal_id FK.

    Example:
        >>> event_pk, created = get_or_create_event(
        ...     event_id="KXNFL-24DEC22-KC-SEA",
        ...     platform_id="kalshi",
        ...     external_id="KXNFL-24DEC22-KC-SEA",
        ...     category="sports",
        ...     title="Chiefs vs Seahawks - Dec 22, 2024",
        ...     series_internal_id=42
        ... )
        >>> if created:
        ...     print(f"Created new event with PK: {event_pk}")
        ... else:
        ...     print(f"Event already exists with PK: {event_pk}")

    Educational Note:
        This pattern is essential for polling services like KalshiMarketPoller.
        When polling API data, the same events appear repeatedly. This function
        ensures we don't attempt duplicate inserts (which would fail due to
        UNIQUE constraint on event_id) while still creating new events when
        they appear.

    Reference:
        - src/precog/schedulers/kalshi_poller.py
        - Migration 0019: events.series_internal_id replaces events.series_id
        - Migration 0020: events.id SERIAL PK, returns integer instead of VARCHAR
    """
    # Check if event already exists — return its surrogate PK
    existing = get_event(event_id)
    if existing is not None:
        return cast("int", existing["id"]), False

    # Create new event — create_event() now returns the integer PK
    event_pk = create_event(
        event_id=event_id,
        platform_id=platform_id,
        external_id=external_id,
        category=category,
        title=title,
        series_internal_id=series_internal_id,
        subcategory=subcategory,
        description=description,
        start_time=start_time,
        end_time=end_time,
        status=status,
        metadata=metadata,
    )
    return event_pk, True


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
# market_internal_id INTEGER FK → markets(id). VARCHAR market_id is dropped.
# =============================================================================


def create_market(
    platform_id: str,
    event_internal_id: int | None,
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
    league: str | None = None,
    bracket_count: int | None = None,
    source_url: str | None = None,
) -> int:
    """
    Create new market (dimension) + initial snapshot (fact).

    Inserts a row into the markets dimension table and a corresponding
    initial snapshot row into market_snapshots with row_current_ind = TRUE.

    Args:
        platform_id: Foreign key to platforms table (VARCHAR)
        event_internal_id: Integer FK to events(id) surrogate PK. This is the
            integer returned by get_or_create_event(), NOT the VARCHAR event_id.
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
        league: Sport league (e.g., "NFL", "NCAAF")
        bracket_count: Number of markets in the parent event bracket
        source_url: URL to the market on the platform

    Returns:
        Integer surrogate PK (markets.id) of the newly created market.

    Note:
        yes_ask_price and no_ask_price store Kalshi ask prices, NOT implied
        probabilities. yes_ask_price + no_ask_price > 1.0 is normal (ask prices
        include the spread). At settlement, both can reach 1.0 or 0.0.

    Example:
        >>> market_pk = create_market(
        ...     platform_id="kalshi",
        ...     event_internal_id=7,
        ...     external_id="KXNFLKCBUF",
        ...     ticker="NFL-KC-BUF-YES",
        ...     title="Chiefs to beat Bills",
        ...     yes_ask_price=Decimal("0.5200"),
        ...     no_ask_price=Decimal("0.4900"),
        ...     subtitle="Week 14",
        ...     close_time="2026-01-15T18:00:00Z",
        ... )

    Reference:
        - Migration 0021: markets split into dimension + market_snapshots fact
        - Migration 0022: market_id VARCHAR dropped, downstream uses integer FK
        - Migration 0033: enrichment columns added to dimension table
    """
    # Runtime type validation (enforces Decimal precision)
    yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    no_ask_price = validate_decimal(no_ask_price, "no_ask_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")

    with get_cursor(commit=True) as cur:
        # Step 1: Insert dimension row
        # Migration 0022: market_id VARCHAR dropped — no longer inserted.
        # Migration 0033: enrichment columns added (subtitle, timestamps, etc.)
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_internal_id, external_id,
                ticker, title, market_type, status,
                subtitle, open_time, close_time, expiration_time,
                outcome_label, league, bracket_count, source_url,
                metadata, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (
                platform_id,
                event_internal_id,
                external_id,
                ticker,
                title,
                market_type,
                status,
                subtitle,
                open_time,
                close_time,
                expiration_time,
                outcome_label,
                league,
                bracket_count,
                source_url,
                json.dumps(metadata) if metadata else None,
            ),
        )
        dim_row = cur.fetchone()
        market_pk = cast("int", dim_row["id"])

        # Step 2: Insert initial snapshot (fact row)
        cur.execute(
            """
            INSERT INTO market_snapshots (
                market_id, yes_ask_price, no_ask_price,
                spread, volume, open_interest,
                row_current_ind, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
            """,
            (
                market_pk,
                yes_ask_price,
                no_ask_price,
                spread,
                volume,
                open_interest,
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
    query = """
        SELECT
            m.id,
            m.platform_id,
            m.event_internal_id,
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
            m.league,
            m.bracket_count,
            m.source_url,
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
    league: str | None = None,
    bracket_count: int | None = None,
    source_url: str | None = None,
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
        league: Sport league (optional)
        bracket_count: Number of markets in parent event bracket (optional)
        source_url: URL to the market on the platform (optional)

    Returns:
        Integer surrogate PK of the market (markets.id)

    Example:
        >>> market_pk = update_market_with_versioning(
        ...     ticker="NFL-KC-BUF-YES",
        ...     yes_ask_price=Decimal("0.5500"),
        ...     no_ask_price=Decimal("0.4500")
        ... )

    Reference:
        - Migration 0021: markets dimension + market_snapshots fact
        - Migration 0033: enrichment columns on dimension table
    """
    # Runtime type validation (enforces Decimal precision)
    if yes_ask_price is not None:
        yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    if no_ask_price is not None:
        no_ask_price = validate_decimal(no_ask_price, "no_ask_price")

    # Get current market + snapshot
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

    # Enrichment columns: only override if explicitly provided (not None)
    new_subtitle = subtitle if subtitle is not None else current["subtitle"]
    new_open_time = open_time if open_time is not None else current["open_time"]
    new_close_time = close_time if close_time is not None else current["close_time"]
    new_expiration_time = (
        expiration_time if expiration_time is not None else current["expiration_time"]
    )
    new_outcome_label = outcome_label if outcome_label is not None else current["outcome_label"]
    new_league = league if league is not None else current["league"]
    new_bracket_count = bracket_count if bracket_count is not None else current["bracket_count"]
    new_source_url = source_url if source_url is not None else current["source_url"]

    with get_cursor(commit=True) as cur:
        # Step 1: Update dimension row — always bump updated_at, plus
        # status/metadata/enrichment if they changed.
        # Migration 0033: enrichment columns updated on dimension row.
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
                league = %s,
                bracket_count = %s,
                source_url = %s,
                updated_at = NOW()
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
                new_league,
                new_bracket_count,
                new_source_url,
                market_pk,
            ),
        )

        # Step 2: Create new snapshot (SCD Type 2 on market_snapshots)
        # Mark current snapshot as historical
        cur.execute(
            """
            UPDATE market_snapshots
            SET row_current_ind = FALSE,
                row_end_ts = NOW()
            WHERE market_id = %s
              AND row_current_ind = TRUE
            """,
            (market_pk,),
        )

        # Insert new snapshot
        cur.execute(
            """
            INSERT INTO market_snapshots (
                market_id, yes_ask_price, no_ask_price,
                spread, volume, open_interest,
                row_current_ind, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
            """,
            (
                market_pk,
                new_yes,
                new_no,
                current["spread"],
                new_volume,
                new_open_interest,
            ),
        )

        return cast("int", market_pk)


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
    # Migration 0033: enrichment columns (subtitle, league, close_time) added for GUI.
    query = """
        SELECT
            m.ticker,
            m.title,
            m.subtitle,
            COALESCE(e.subcategory, 'unknown') as subcategory,
            m.league,
            ms.yes_ask_price,
            ms.no_ask_price,
            m.status,
            m.close_time,
            COALESCE(ms.volume, 0) as volume
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id AND ms.row_current_ind = TRUE
        LEFT JOIN events e
            ON e.id = m.event_internal_id
        WHERE 1=1
    """
    params: list[Any] = []

    if subcategory is not None:
        query += " AND LOWER(e.subcategory) = LOWER(%s)"
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


def create_position(
    market_internal_id: int,
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
        market_internal_id: Integer foreign key to markets(id)
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
                position_id, market_internal_id, strategy_id, model_id, side,
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
                current["market_internal_id"],
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
                position_id, market_internal_id, strategy_id, model_id, side,
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
                current["execution_environment"],  # Preserve execution environment
            ),
        )

        result = cur.fetchone()
        return cast("int", result["id"])  # Return new surrogate id


# =============================================================================
# TRADE OPERATIONS
# =============================================================================


def create_trade(
    market_internal_id: int,
    side: str,
    quantity: int,
    price: Decimal,
    order_id: int | None = None,
    is_taker: bool | None = None,
    fees: Decimal | None = None,
    trade_metadata: dict | None = None,
    calculated_probability: Decimal | None = None,
    market_price: Decimal | None = None,
    execution_environment: ExecutionEnvironment = "live",
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
        order_id: Integer FK to orders(id) — links fill to its order
        is_taker: Whether this fill was a taker (True) or maker (False)
        fees: Per-fill fees as DECIMAL(10,4)
        trade_metadata: Additional metadata as JSONB
        calculated_probability: Model-predicted probability at execution [0, 1]
        market_price: Kalshi market price at execution [0, 1]
        execution_environment: 'live', 'paper', or 'backtest' (default 'live')

    Returns:
        trade_id of newly created trade

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
        RETURNING trade_id
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
        return cast("int", result["trade_id"])


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
    market_internal_id: int,
    platform_id: str,
    outcome: str,
    payout: Decimal,
) -> int | None:
    """
    Create settlement record for a resolved market.

    Settlements are append-only (no versioning) because they are final.
    Once a market settles, the outcome and payout never change.

    Args:
        market_internal_id: Integer foreign key to markets(id)
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
        ...     market_internal_id=42,
        ...     platform_id="kalshi",
        ...     outcome="yes",
        ...     payout=Decimal("1.0000")  # $1.00 per contract
        ... )

        >>> # Market resolved NO, YES position pays $0
        >>> settlement_id = create_settlement(
        ...     market_internal_id=43,
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
            market_internal_id, platform_id, outcome, payout, created_at
        )
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING settlement_id
    """

    params = (market_internal_id, platform_id, outcome, payout)

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
        WHERE t.trade_id = %s
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


def create_team(
    team_code: str,
    team_name: str,
    display_name: str,
    sport: str,
    league: str,
    espn_team_id: str | None = None,
    current_elo_rating: Decimal | None = None,
    conference: str | None = None,
    division: str | None = None,
) -> int:
    """
    Create a new team record in the teams table.

    Uses a lookup-first strategy to find existing teams, then INSERT with
    try/except for UniqueViolation to handle race conditions. This approach
    works regardless of which unique constraints exist on the table.

    Lookup order:
        1. By (espn_team_id, league) if espn_team_id is provided
        2. By (team_code, sport, league) as fallback

    Args:
        team_code: Abbreviation code (e.g., 'KC', 'BOS', 'TBL')
        team_name: Full team name (e.g., 'Kansas City Chiefs')
        display_name: Short display name (e.g., 'Chiefs')
        sport: Sport/league code for the sport column (e.g., 'nfl', 'nba')
        league: League code for the league column (e.g., 'nfl', 'nba')
        espn_team_id: ESPN unique team identifier (e.g., '12')
        current_elo_rating: Elo rating from calibrated computation. None if not
            yet calculated. Do NOT pass a placeholder value (e.g., 1500) —
            use the EloEngine to compute real ratings from game results.
        conference: Conference name (e.g., 'AFC', 'Eastern')
        division: Division name (e.g., 'West', 'Atlantic')

    Returns:
        team_id of the created or existing team

    Educational Note:
        The teams table may have multiple unique constraints depending on
        migration state:
        - UNIQUE(team_code, sport) - legacy constraint (being phased out)
        - Partial UNIQUE(espn_team_id, league) WHERE espn_team_id IS NOT NULL
        - Partial UNIQUE(team_code, sport) for pro leagues only (migration 0018)
        This function avoids referencing any specific constraint in SQL,
        using lookup-first + try/except instead of ON CONFLICT.

    Example:
        >>> team_id = create_team(
        ...     team_code="KC",
        ...     team_name="Kansas City Chiefs",
        ...     display_name="Chiefs",
        ...     sport="nfl",
        ...     league="nfl",
        ...     espn_team_id="12",
        ...     conference="AFC",
        ...     division="West",
        ... )

    Related:
        - get_team_by_espn_id() (lookup by ESPN ID)
        - espn_team_validator._create_missing_team() (caller for auto-sync)
    """
    # Step 1: Look up existing team by ESPN ID (most specific identifier)
    if espn_team_id:
        existing = fetch_one(
            "SELECT team_id FROM teams WHERE espn_team_id = %s AND league = %s",
            (espn_team_id, league),
        )
        if existing:
            team_id = int(existing["team_id"] if isinstance(existing, dict) else existing[0])
            logger.debug(
                "Team found by ESPN ID: %s %s (espn_id=%s, team_id=%d)",
                league.upper(),
                team_code,
                espn_team_id,
                team_id,
            )
            return team_id

    # Step 2: Fall back to lookup by (team_code, sport, league)
    existing = fetch_one(
        "SELECT team_id FROM teams WHERE team_code = %s AND sport = %s AND league = %s",
        (team_code, sport, league),
    )
    if existing:
        team_id = int(existing["team_id"] if isinstance(existing, dict) else existing[0])
        logger.debug(
            "Team found by code: %s %s (team_id=%d)",
            league.upper(),
            team_code,
            team_id,
        )
        return team_id

    # Step 3: Team doesn't exist — INSERT it
    insert_query = """
        INSERT INTO teams (
            team_code, team_name, display_name, sport, league,
            espn_team_id, current_elo_rating, conference, division
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING team_id
    """
    params = (
        team_code,
        team_name,
        display_name,
        sport,
        league,
        espn_team_id,
        current_elo_rating,
        conference,
        division,
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(insert_query, params)
            row = cur.fetchone()
            if row:
                team_id = int(row["team_id"] if isinstance(row, dict) else row[0])
                logger.info(
                    "Created team: %s %s (%s, espn_id=%s, team_id=%d)",
                    league.upper(),
                    team_code,
                    team_name,
                    espn_team_id,
                    team_id,
                )
                return team_id

    except psycopg2.errors.UniqueViolation:
        # Race condition: another process created this team between our
        # SELECT and INSERT. Look it up again to get the team_id.
        logger.warning(
            "UniqueViolation on team insert: %s %s (espn_id=%s, league=%s). "
            "Retrieving existing record.",
            league.upper(),
            team_code,
            espn_team_id,
            league,
        )
        # Try ESPN ID first, then team_code
        if espn_team_id:
            conflicting = fetch_one(
                "SELECT team_id FROM teams WHERE espn_team_id = %s AND league = %s",
                (espn_team_id, league),
            )
            if conflicting:
                return int(
                    conflicting["team_id"] if isinstance(conflicting, dict) else conflicting[0]
                )
        conflicting = fetch_one(
            "SELECT team_id FROM teams WHERE team_code = %s AND sport = %s AND league = %s",
            (team_code, sport, league),
        )
        if conflicting:
            return int(conflicting["team_id"] if isinstance(conflicting, dict) else conflicting[0])

    # Should not reach here, but defensive
    raise ValueError(f"Failed to create or find team: {team_code} ({sport}/{league})")


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
    game_id: int | None = None,
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
            data_source, game_id, row_current_ind, row_start_ts
        )
        VALUES (
            'TEMP', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, TRUE, NOW()
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
                game_id,
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
    game_id: int | None = None,
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
            # No meaningful change - return None to indicate skip
            return None

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
            data_source, game_id, row_current_ind, row_start_ts
        )
        VALUES (
            'TEMP', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, TRUE, NOW()
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
                game_id,
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

    with get_cursor(commit=True) as cur:
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

    with get_cursor(commit=True) as cur:
        cur.execute(query, tuple(params))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0)


def check_active_schedulers(
    stale_threshold_seconds: int = 120,
) -> list[dict[str, Any]]:
    """
    Check for actively running scheduler services with recent heartbeats.

    Used by the startup guard to detect concurrent scheduler instances before
    allowing a new supervisor to start. Returns services that appear to be
    genuinely alive (status is 'running'/'starting' AND heartbeat is fresh).

    Args:
        stale_threshold_seconds: How recent heartbeat must be to consider active.
            Default is 120s (2 minutes). Typically set to 2x the health check
            interval to allow for one missed heartbeat.

    Returns:
        List of active service dictionaries with host_id, service_name, pid,
        status, started_at, and last_heartbeat fields.

    Example:
        >>> active = check_active_schedulers(stale_threshold_seconds=120)
        >>> if active:
        ...     for svc in active:
        ...         print(f"Active: {svc['host_id']}/{svc['service_name']} PID {svc['pid']}")

    References:
        - Issue #363: Concurrent scheduler startup guard
        - Migration 0012: scheduler_status table schema
    """
    query = """
        SELECT host_id, service_name, pid, status, started_at, last_heartbeat
        FROM scheduler_status
        WHERE status IN ('running', 'starting')
        AND last_heartbeat >= NOW() - INTERVAL '%s seconds'
        ORDER BY host_id, service_name
    """
    return fetch_all(query, (stale_threshold_seconds,))


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
    with get_cursor(commit=True) as cur:
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
#         3. Links to source game (game_states or games)
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

    Note:
        If multiple teams share the same team_code (e.g., 'ATL' in both
        NFL and MLS), a warning is logged and the first result is returned.
        Callers should provide the sport parameter to avoid ambiguity.

    Example:
        >>> rating = get_team_elo_by_code("KC", sport="nfl")
        >>> print(f"Chiefs Elo: {rating}")
    """
    if sport:
        results = fetch_all(
            "SELECT current_elo_rating FROM teams WHERE team_code = %s AND sport = %s",
            (team_code, sport),
        )
    else:
        results = fetch_all(
            "SELECT current_elo_rating FROM teams WHERE team_code = %s",
            (team_code,),
        )
    if not results:
        return None
    if len(results) > 1:
        logger.warning(
            "Ambiguous team_code lookup: '%s' (sport=%s) matched %d rows. "
            "Returning first result. Pass sport parameter to disambiguate.",
            team_code,
            sport,
            len(results),
        )
    result = results[0]
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
    game_id: int | None = None,
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
        game_id: FK to games.id (optional)
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
            game_state_id, game_id,
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
        game_id,
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


# =============================================================================
# ALERT CRUD OPERATIONS
# =============================================================================


def create_alert(
    alert_type: str,
    severity: str,
    message: str,
    source: str | None = None,
) -> int | None:
    """
    Create an alert record in the alerts table.

    Alerts are append-only operational signals for anomalies, threshold
    breaches, and system events. This is the first writer for the alerts
    table (created in migration 0001 but previously unused).

    Args:
        alert_type: Category of alert (e.g., "validation_error_rate",
            "data_staleness", "circuit_breaker"). VARCHAR(50).
        severity: One of "info", "warning", "error", "critical".
            Enforced by CHECK constraint in the DB.
        message: Human-readable description of the alert.
        source: Optional source component (e.g., "kalshi_poller",
            "espn_poller"). VARCHAR(100).

    Returns:
        alert_id of the newly created record, or None if insert failed.

    Raises:
        psycopg2.IntegrityError: If severity not in allowed values.

    Example:
        >>> alert_id = create_alert(
        ...     alert_type="validation_error_rate",
        ...     severity="warning",
        ...     message="Error rate 15.0% exceeds 10% threshold (3/20 markets)",
        ...     source="kalshi_poller:KXNFLGAME",
        ... )
    """
    query = """
        INSERT INTO alerts (alert_type, severity, message, source, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING alert_id
    """
    params = (alert_type, severity, message, source)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result["alert_id"] if result else None


# =============================================================================
# System Health CRUD Operations
# =============================================================================


def upsert_system_health(
    component: str,
    status: str,
    details: dict[str, Any] | None = None,
    alert_sent: bool = False,
) -> bool:
    """
    Insert or update component health in the system_health table.

    Uses DELETE + INSERT within a single committed transaction to maintain
    one row per component. The system_health table is not SCD Type 2.

    Why DELETE + INSERT?
    --------------------
    The system_health table has a non-unique index on component (not a
    UNIQUE constraint), so ON CONFLICT UPSERT is not available. DELETE +
    INSERT within get_cursor(commit=True) achieves the same result: exactly
    one current health row per component. A future migration can add a
    UNIQUE constraint to enable proper ON CONFLICT.

    Args:
        component: Component identifier. Must match the CHECK constraint:
            'kalshi_api', 'polymarket_api', 'espn_api', 'database',
            'edge_detector', 'trading_engine', 'websocket'.
        status: Health status. Must match the CHECK constraint:
            'healthy', 'degraded', 'down'.
        details: Optional JSONB payload with component-specific metrics
            (e.g., error_rate, polls_completed, last_successful_poll).
        alert_sent: Whether an alert has been sent for this health state.

    Returns:
        True if operation succeeded, False otherwise.

    Raises:
        psycopg2.IntegrityError: If component or status violates CHECK constraints.

    Example:
        >>> upsert_system_health(
        ...     component="kalshi_api",
        ...     status="healthy",
        ...     details={"error_rate": "0.02", "polls": 142, "errors": 3},
        ... )

        >>> upsert_system_health(
        ...     component="espn_api",
        ...     status="degraded",
        ...     details={"error_rate": "0.12", "last_poll_age_seconds": 180},
        ...     alert_sent=True,
        ... )

    Educational Note:
        The system_health table currently has a non-unique index on component.
        DELETE + INSERT keeps one row per component. A future migration should
        add a UNIQUE constraint to enable proper ON CONFLICT UPSERT.

    References:
        - Migration 0001: system_health table schema
        - Issue #389: Wire system_health table
        - REQ-OBSERV-001: Observability Requirements
    """
    # The system_health table has a non-unique index on component, so we use
    # DELETE + INSERT within a single transaction to simulate upsert behavior.
    # This keeps exactly one row per component (latest health snapshot).
    delete_query = "DELETE FROM system_health WHERE component = %s"
    insert_query = """
        INSERT INTO system_health (component, status, last_check, details, alert_sent)
        VALUES (%s, %s, NOW(), %s, %s)
    """
    details_json = json.dumps(details, cls=DecimalEncoder) if details else None

    with get_cursor(commit=True) as cur:
        cur.execute(delete_query, (component,))
        cur.execute(insert_query, (component, status, details_json, alert_sent))
        return int(cur.rowcount or 0) > 0


def get_system_health(component: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch system health records, optionally filtered by component.

    Args:
        component: If provided, fetch health for this component only.
            If None, fetch all components.

    Returns:
        List of health records as dictionaries. Each dict contains:
            health_id, component, status, last_check, details, alert_sent.
        Empty list if no records found.

    Example:
        >>> # Get all component health
        >>> records = get_system_health()
        >>> for r in records:
        ...     print(r["component"], r["status"])
        kalshi_api healthy
        espn_api degraded

        >>> # Get specific component
        >>> records = get_system_health(component="kalshi_api")
        >>> print(records[0]["status"])  # 'healthy'

    References:
        - Migration 0001: system_health table schema
        - Issue #389: Wire system_health table
    """
    if component:
        query = """
            SELECT health_id, component, status, last_check, details, alert_sent
            FROM system_health
            WHERE component = %s
            ORDER BY component
        """
        return fetch_all(query, (component,))

    query = """
        SELECT health_id, component, status, last_check, details, alert_sent
        FROM system_health
        ORDER BY component
    """
    return fetch_all(query)


def get_system_health_summary() -> dict[str, str]:
    """
    Get a compact component -> status mapping for all tracked components.

    This is a convenience function for CLI display and quick health checks.
    Returns only the latest status per component without full details.

    Returns:
        Dictionary mapping component name to status string.
        Example: {"kalshi_api": "healthy", "espn_api": "degraded"}
        Empty dict if no health records exist.

    Example:
        >>> summary = get_system_health_summary()
        >>> if summary.get("kalshi_api") != "healthy":
        ...     print("Kalshi API is not healthy!")

    References:
        - Migration 0001: system_health table schema
        - Issue #389: Wire system_health table
    """
    records = get_system_health()
    return {r["component"]: r["status"] for r in records}


# =============================================================================
# Circuit Breaker CRUD Operations
# =============================================================================


def create_circuit_breaker_event(
    breaker_type: str,
    trigger_value: dict[str, Any] | None = None,
    notes: str | None = None,
) -> int | None:
    """
    Create a circuit breaker event (trip a breaker).

    Circuit breakers are safety guards that halt trading or data collection
    when anomalies are detected. A tripped breaker stays active until
    explicitly resolved via resolve_circuit_breaker().

    Args:
        breaker_type: Type of breaker to trip. Must match CHECK constraint:
            'daily_loss_limit', 'api_failures', 'data_stale',
            'position_limit', 'manual'.
        trigger_value: Optional JSONB payload with context about what
            triggered the breaker (e.g., error counts, component name).
        notes: Optional human-readable reason for tripping the breaker.

    Returns:
        event_id of the newly created record, or None if insert failed.

    Raises:
        psycopg2.IntegrityError: If breaker_type not in allowed values.

    Example:
        >>> event_id = create_circuit_breaker_event(
        ...     breaker_type="data_stale",
        ...     trigger_value={"component": "espn_api", "reason": "not_running"},
        ...     notes="ESPN poller went down during health check",
        ... )

    References:
        - Migration 0001: circuit_breaker_events table schema
        - Issue #390: Wire circuit_breaker_events table
    """
    query = """
        INSERT INTO circuit_breaker_events (breaker_type, triggered_at, trigger_value, notes)
        VALUES (%s, NOW(), %s, %s)
        RETURNING event_id
    """
    trigger_json = (
        json.dumps(trigger_value, cls=DecimalEncoder) if trigger_value is not None else None
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, (breaker_type, trigger_json, notes))
        result = cur.fetchone()
        return result["event_id"] if result else None


def resolve_circuit_breaker(
    event_id: int,
    resolution_action: str | None = None,
) -> bool:
    """
    Resolve an active circuit breaker event.

    Sets resolved_at to NOW() and optionally records what action was taken.
    Only resolves breakers that are currently active (resolved_at IS NULL).

    Args:
        event_id: The event_id of the breaker to resolve.
        resolution_action: Optional description of resolution action taken
            (e.g., "manual reset", "service restarted"). VARCHAR(100).

    Returns:
        True if the breaker was resolved, False if not found or already resolved.

    Example:
        >>> resolved = resolve_circuit_breaker(
        ...     event_id=42,
        ...     resolution_action="ESPN poller restarted successfully",
        ... )
        >>> print(resolved)  # True

    References:
        - Migration 0001: circuit_breaker_events table schema
        - Issue #390: Wire circuit_breaker_events table
    """
    query = """
        UPDATE circuit_breaker_events
        SET resolved_at = NOW(), resolution_action = %s
        WHERE event_id = %s AND resolved_at IS NULL
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (resolution_action, event_id))
        return int(cur.rowcount or 0) > 0


def get_active_breakers(breaker_type: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all active (unresolved) circuit breaker events.

    Active breakers have resolved_at IS NULL, meaning they are currently
    tripped and have not been manually or automatically resolved.

    Args:
        breaker_type: If provided, filter to only this breaker type.
            If None, return all active breakers regardless of type.

    Returns:
        List of active breaker records as dictionaries. Each dict contains:
            event_id, breaker_type, triggered_at, trigger_value, notes.
        Empty list if no active breakers.

    Example:
        >>> # Check if any breakers are active
        >>> breakers = get_active_breakers()
        >>> if breakers:
        ...     print(f"{len(breakers)} active breaker(s)!")

        >>> # Check for specific type
        >>> stale = get_active_breakers(breaker_type="data_stale")

    References:
        - Migration 0001: circuit_breaker_events table schema
        - Issue #390: Wire circuit_breaker_events table
    """
    if breaker_type:
        query = """
            SELECT event_id, breaker_type, triggered_at, trigger_value, notes
            FROM circuit_breaker_events
            WHERE resolved_at IS NULL AND breaker_type = %s
            ORDER BY triggered_at DESC
        """
        return fetch_all(query, (breaker_type,))

    query = """
        SELECT event_id, breaker_type, triggered_at, trigger_value, notes
        FROM circuit_breaker_events
        WHERE resolved_at IS NULL
        ORDER BY triggered_at DESC
    """
    return fetch_all(query)


# =============================================================================
# EDGE OPERATIONS
# =============================================================================
#
# Migration 0023: edges table enriched with analytics-ready columns.
#   - probability_matrix_id dropped (dead FK)
#   - New columns: actual_outcome, settlement_value, resolved_at, strategy_id,
#     edge_status, yes_ask_price, no_ask_price, spread, volume, open_interest,
#     last_price, liquidity, category, subcategory, execution_environment
#   - New views: current_edges (recreated), edge_lifecycle (computed P&L)
#
# SCD Type 2: edges use row_current_ind versioning.
#   - create_edge: sets row_current_ind = TRUE
#   - update_edge_outcome / update_edge_status: direct updates (lifecycle
#     events, not version changes)
# =============================================================================


def create_edge(
    market_internal_id: int,
    model_id: int,
    expected_value: Decimal,
    true_win_probability: Decimal,
    market_implied_probability: Decimal,
    market_price: Decimal,
    yes_ask_price: Decimal | None = None,
    no_ask_price: Decimal | None = None,
    spread: Decimal | None = None,
    volume: int | None = None,
    open_interest: int | None = None,
    last_price: Decimal | None = None,
    liquidity: Decimal | None = None,
    strategy_id: int | None = None,
    confidence_level: str | None = None,
    confidence_metrics: dict | None = None,
    recommended_action: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    execution_environment: ExecutionEnvironment = "live",
) -> int:
    """
    Create a new edge record with SCD Type 2 row_current_ind = TRUE.

    An edge represents a detected positive expected value opportunity: the
    difference between the model's predicted probability and the market's
    implied probability. This function captures the full market microstructure
    snapshot at the moment of edge detection.

    Args:
        market_internal_id: Integer FK to markets(id) surrogate PK
        model_id: FK to probability_models(model_id) that detected this edge
        expected_value: Expected value of the edge as DECIMAL(10,4)
        true_win_probability: Model's predicted probability [0, 1]
        market_implied_probability: Market-implied probability [0, 1]
        market_price: Market price at detection [0, 1]
        yes_ask_price: Kalshi YES ask price snapshot at detection
        no_ask_price: Kalshi NO ask price snapshot at detection
        spread: Bid-ask spread as DECIMAL(10,4)
        volume: Trading volume at detection
        open_interest: Open interest at detection
        last_price: Last traded price at detection
        liquidity: Market liquidity metric
        strategy_id: FK to strategies(strategy_id) for attribution
        confidence_level: 'high', 'medium', or 'low'
        confidence_metrics: Additional confidence data as JSONB
        recommended_action: 'auto_execute', 'alert', or 'ignore'
        category: Market category (e.g., 'sports', 'politics')
        subcategory: Market subcategory (e.g., 'nfl', 'ncaaf')
        execution_environment: 'live', 'paper', or 'backtest' (default 'live')

    Returns:
        Integer surrogate PK (edges.id) of the newly created edge.

    Educational Note:
        Dual-Key Structure (Migration 017):
        - id SERIAL (surrogate key) - returned by this function
        - edge_id VARCHAR (business key) - auto-generated as EDGE-{id}
        - Enables SCD Type 2 versioning (multiple versions of same edge)

        Edge Lifecycle (Migration 0023):
        - Edges start as 'detected' and progress through:
          detected -> recommended -> acted_on -> settled/expired/void
        - Outcome tracking via actual_outcome + settlement_value
        - P&L computed in edge_lifecycle view

    Example:
        >>> edge_pk = create_edge(
        ...     market_internal_id=42,
        ...     model_id=2,
        ...     expected_value=Decimal("0.0500"),
        ...     true_win_probability=Decimal("0.5700"),
        ...     market_implied_probability=Decimal("0.5200"),
        ...     market_price=Decimal("0.5200"),
        ...     yes_ask_price=Decimal("0.5300"),
        ...     no_ask_price=Decimal("0.4800"),
        ...     strategy_id=1,
        ...     confidence_level='high',
        ...     execution_environment='paper',
        ... )
        >>> # Returns surrogate id (e.g., 1), edge_id auto-set to 'EDGE-1'

    References:
        - Migration 0023: edges enrichment and cleanup
        - ADR-002: Decimal Precision for All Financial Data
    """
    # Runtime type validation (enforces Decimal precision)
    expected_value = validate_decimal(expected_value, "expected_value")
    true_win_probability = validate_decimal(true_win_probability, "true_win_probability")
    market_implied_probability = validate_decimal(
        market_implied_probability, "market_implied_probability"
    )
    market_price = validate_decimal(market_price, "market_price")

    if yes_ask_price is not None:
        yes_ask_price = validate_decimal(yes_ask_price, "yes_ask_price")
    if no_ask_price is not None:
        no_ask_price = validate_decimal(no_ask_price, "no_ask_price")
    if spread is not None:
        spread = validate_decimal(spread, "spread")
    if last_price is not None:
        last_price = validate_decimal(last_price, "last_price")
    if liquidity is not None:
        liquidity = validate_decimal(liquidity, "liquidity")

    insert_query = """
        INSERT INTO edges (
            edge_id, market_internal_id, model_id,
            expected_value, true_win_probability,
            market_implied_probability, market_price,
            yes_ask_price, no_ask_price, spread,
            volume, open_interest, last_price, liquidity,
            strategy_id, confidence_level, confidence_metrics,
            recommended_action, category, subcategory,
            execution_environment, edge_status,
            row_current_ind, row_start_ts
        )
        VALUES (
            'TEMP', %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, 'detected',
            TRUE, NOW()
        )
        RETURNING id
    """

    params = (
        market_internal_id,
        model_id,
        expected_value,
        true_win_probability,
        market_implied_probability,
        market_price,
        yes_ask_price,
        no_ask_price,
        spread,
        volume,
        open_interest,
        last_price,
        liquidity,
        strategy_id,
        confidence_level,
        json.dumps(confidence_metrics) if confidence_metrics is not None else None,
        recommended_action,
        category,
        subcategory,
        execution_environment,
    )

    with get_cursor(commit=True) as cur:
        # Get surrogate id
        cur.execute(insert_query, params)
        result = cur.fetchone()
        surrogate_id = cast("int", result["id"])

        # Update to set correct edge_id (EDGE-{id} format)
        cur.execute(
            "UPDATE edges SET edge_id = %s WHERE id = %s",
            (f"EDGE-{surrogate_id}", surrogate_id),
        )

        return surrogate_id


def update_edge_outcome(
    edge_pk: int,
    actual_outcome: str,
    settlement_value: Decimal,
    resolved_at: datetime | None = None,
) -> bool:
    """
    Record settlement outcome for an edge.

    This is a lifecycle event (not an SCD version change), so we update
    the current row directly rather than creating a new SCD version.
    Also sets edge_status to 'settled'.

    Args:
        edge_pk: Surrogate PK (edges.id), NOT the edge_id business key
        actual_outcome: Settlement result - 'yes', 'no', 'void', or 'unresolved'
        settlement_value: Actual settlement price as DECIMAL(10,4)
            (0.0000 or 1.0000 for binary markets)
        resolved_at: Resolution timestamp (defaults to NOW())

    Returns:
        True if the edge was found and updated, False otherwise.

    Educational Note:
        Why direct update instead of SCD version?
        Outcome resolution is a lifecycle event on an existing edge -- it
        doesn't change the edge's identity or detection parameters. The
        edge_lifecycle view computes realized_pnl from settlement_value
        minus market_price, so we need these on the same row.

    Example:
        >>> success = update_edge_outcome(
        ...     edge_pk=42,
        ...     actual_outcome='yes',
        ...     settlement_value=Decimal("1.0000"),
        ... )
        >>> # Edge 42 now has edge_status='settled', actual_outcome='yes'

    References:
        - Migration 0023: edges enrichment
        - edge_lifecycle view: computes realized_pnl from outcome
    """
    settlement_value = validate_decimal(settlement_value, "settlement_value")

    valid_outcomes = ("yes", "no", "void", "unresolved")
    if actual_outcome not in valid_outcomes:
        raise ValueError(f"actual_outcome must be one of {valid_outcomes}, got '{actual_outcome}'")

    query = """
        UPDATE edges
        SET actual_outcome = %s,
            settlement_value = %s,
            resolved_at = COALESCE(%s, NOW()),
            edge_status = 'settled'
        WHERE id = %s AND row_current_ind = TRUE
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (actual_outcome, settlement_value, resolved_at, edge_pk))
        return int(cur.rowcount or 0) > 0


def update_edge_status(
    edge_pk: int,
    new_status: str,
) -> bool:
    """
    Transition an edge's lifecycle status.

    This is a direct update (not an SCD version change) because status
    transitions track lifecycle progression, not identity changes.

    Args:
        edge_pk: Surrogate PK (edges.id), NOT the edge_id business key
        new_status: New lifecycle status. Valid values:
            'detected', 'recommended', 'acted_on', 'expired', 'settled', 'void'

    Returns:
        True if the edge was found and updated, False otherwise.

    Example:
        >>> success = update_edge_status(edge_pk=42, new_status='recommended')
        >>> # Edge 42 status changed from 'detected' to 'recommended'

    References:
        - Migration 0023: edge_status column with CHECK constraint
    """
    valid_statuses = (
        "detected",
        "recommended",
        "acted_on",
        "expired",
        "settled",
        "void",
    )
    if new_status not in valid_statuses:
        raise ValueError(f"new_status must be one of {valid_statuses}, got '{new_status}'")

    query = """
        UPDATE edges
        SET edge_status = %s
        WHERE id = %s AND row_current_ind = TRUE
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (new_status, edge_pk))
        return int(cur.rowcount or 0) > 0


def get_edges_by_strategy(
    strategy_id: int,
    edge_status: str | None = None,
    execution_environment: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query current edges for a specific strategy.

    Only returns rows with row_current_ind = TRUE (SCD Type 2 pattern).

    Args:
        strategy_id: FK to strategies(strategy_id)
        edge_status: Optional filter by lifecycle status
            ('detected', 'recommended', 'acted_on', 'expired', 'settled', 'void')
        execution_environment: Optional filter ('live', 'paper', 'backtest')
        limit: Maximum rows to return (default 100)

    Returns:
        List of edge dictionaries, ordered by created_at DESC.

    Example:
        >>> edges = get_edges_by_strategy(strategy_id=1, edge_status='detected')
        >>> for edge in edges:
        ...     print(f"Edge {edge['edge_id']}: EV={edge['expected_value']}")

    References:
        - Migration 0023: strategy_id column + idx_edges_strategy index
    """
    query = """
        SELECT id, edge_id, market_internal_id, model_id, strategy_id,
               expected_value, true_win_probability, market_implied_probability,
               market_price, yes_ask_price, no_ask_price, spread,
               volume, open_interest, last_price, liquidity,
               edge_status, actual_outcome, settlement_value,
               confidence_level, recommended_action,
               category, subcategory, execution_environment,
               created_at, resolved_at
        FROM edges
        WHERE row_current_ind = TRUE AND strategy_id = %s
    """
    params: list = [strategy_id]

    if edge_status is not None:
        query += " AND edge_status = %s"
        params.append(edge_status)

    if execution_environment is not None:
        query += " AND execution_environment = %s"
        params.append(execution_environment)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


def get_edge_lifecycle(
    market_internal_id: int | None = None,
    strategy_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query the edge_lifecycle view for analytics.

    The view includes computed fields:
    - realized_pnl: settlement_value - market_price (for 'yes' outcomes)
      or market_price - settlement_value (for 'no' outcomes)
    - hours_to_resolution: time from edge creation to resolution in hours

    Args:
        market_internal_id: Optional filter by market
        strategy_id: Optional filter by strategy
        limit: Maximum rows to return (default 100)

    Returns:
        List of edge lifecycle dictionaries with computed fields.

    Example:
        >>> lifecycle = get_edge_lifecycle(strategy_id=1)
        >>> for edge in lifecycle:
        ...     if edge['realized_pnl'] is not None:
        ...         print(f"Edge {edge['edge_id']}: P&L={edge['realized_pnl']}")

    References:
        - Migration 0023: edge_lifecycle view definition
    """
    query = """
        SELECT id, edge_id, market_internal_id, model_id, strategy_id,
               expected_value, true_win_probability, market_implied_probability,
               market_price, yes_ask_price, no_ask_price,
               edge_status, actual_outcome, settlement_value,
               confidence_level, execution_environment,
               created_at, resolved_at,
               realized_pnl, hours_to_resolution
        FROM edge_lifecycle
        WHERE 1=1
    """
    params: list = []

    if market_internal_id is not None:
        query += " AND market_internal_id = %s"
        params.append(market_internal_id)

    if strategy_id is not None:
        query += " AND strategy_id = %s"
        params.append(strategy_id)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


# =============================================================================
# ORDER OPERATIONS
# =============================================================================
#
# Migration 0025: orders table with attribution, simplified trades table.
#   - Orders capture the trading DECISION (what, why, which strategy/model)
#   - Trades capture EXECUTION EVENTS (fills at the exchange)
#   - Attribution (strategy_id, model_id, edge_id, position_id) lives on
#     orders, NOT on trades. Trades inherit via FK JOIN.
#   - Orders are MUTABLE (status, fill quantities change). NOT SCD.
#   - Terminal state guard: filled/cancelled/expired cannot be resurrected.
#
# Kalshi API Status Mapping:
#   Kalshi uses "executed" (we use "filled") and "canceled" (we use "cancelled").
#   Use KALSHI_STATUS_MAP to translate before calling update_order_status().
# =============================================================================

# Kalshi API uses different status names than our internal model.
# Apply this mapping when ingesting order data from the Kalshi API:
#   kalshi_status = KALSHI_STATUS_MAP.get(api_status, api_status)
KALSHI_STATUS_MAP: dict[str, str] = {
    "executed": "filled",
    "canceled": "cancelled",
}

# Valid values for order enum-like fields (used in runtime validation)
_VALID_ORDER_SIDES = {"yes", "no"}
_VALID_ORDER_ACTIONS = {"buy", "sell"}
_VALID_ORDER_TYPES = {"market", "limit"}
_VALID_TIME_IN_FORCE = {"fill_or_kill", "good_till_canceled", "immediate_or_cancel"}
_VALID_EXEC_ENVS = {"live", "paper", "backtest"}
_VALID_TRADE_SOURCES = {"automated", "manual"}
_VALID_ORDER_STATUSES = {
    "submitted",
    "resting",
    "pending",
    "partial_fill",
    "filled",
    "cancelled",
    "expired",
}
_TERMINAL_ORDER_STATUSES = {"filled", "cancelled", "expired"}


def create_order(
    platform_id: str,
    external_order_id: str,
    market_internal_id: int,
    side: str,
    action: str,
    requested_price: Decimal,
    requested_quantity: int,
    order_type: str = "market",
    time_in_force: str = "good_till_canceled",
    strategy_id: int | None = None,
    model_id: int | None = None,
    edge_id: int | None = None,
    position_id: int | None = None,
    client_order_id: str | None = None,
    execution_environment: ExecutionEnvironment = "live",
    trade_source: str = "automated",
    order_metadata: dict | None = None,
) -> int:
    """
    Create a new order record.

    An order represents a trading DECISION: what was requested, why (attribution),
    and the current fill state. Orders are mutable -- status and fill quantities
    update as the exchange processes them.

    Args:
        platform_id: FK to platforms(platform_id), e.g. 'kalshi'
        external_order_id: Exchange-assigned order ID (unique per platform)
        market_internal_id: Integer FK to markets(id) surrogate PK
        side: 'yes' or 'no' (which outcome is being bet on)
        action: 'buy' or 'sell' (entering or exiting a position)
        requested_price: Limit price as DECIMAL(10,4) in [0, 1]
        requested_quantity: Number of contracts requested (> 0)
        order_type: 'market' or 'limit' (default 'market')
        time_in_force: 'fill_or_kill', 'good_till_canceled', or 'immediate_or_cancel'
        strategy_id: FK to strategies(strategy_id) for attribution
        model_id: FK to probability_models(model_id) for attribution
        edge_id: FK to edges(id) for attribution
        position_id: FK to positions(id) for attribution
        client_order_id: User-provided tracking ID
        execution_environment: 'live', 'paper', or 'backtest'
        trade_source: 'automated' or 'manual'
        order_metadata: Additional data stored as JSONB

    Returns:
        Integer surrogate PK (orders.id) of the newly created order.

    Raises:
        TypeError: If requested_price is not Decimal
        ValueError: If side, action, order_type, time_in_force,
            execution_environment, or trade_source has invalid value

    Educational Note:
        Kalshi Status Mapping:
            Kalshi API uses "executed" (we use "filled") and "canceled"
            (we use "cancelled" with double-l). When ingesting from Kalshi,
            translate via KALSHI_STATUS_MAP before calling:
                internal = KALSHI_STATUS_MAP.get(kalshi_status, kalshi_status)

        Attribution Design:
            Attribution lives on orders, not trades. To get a trade's strategy,
            JOIN trades.order_id -> orders.id -> orders.strategy_id. This avoids
            duplicating attribution across every fill event.

    Example:
        >>> order_pk = create_order(
        ...     platform_id='kalshi',
        ...     external_order_id='abc-123',
        ...     market_internal_id=42,
        ...     side='yes',
        ...     action='buy',
        ...     requested_price=Decimal("0.5500"),
        ...     requested_quantity=10,
        ...     strategy_id=1,
        ...     execution_environment='paper',
        ... )
        >>> # Returns surrogate id (e.g., 1)

    References:
        - Migration 0025: create_orders
        - issue336_council_findings.md: UNANIMOUS Option 2
    """
    # Runtime type validation (enforces Decimal precision)
    requested_price = validate_decimal(requested_price, "requested_price")

    # Runtime enum-like validation (Glokta finding #5)
    if side not in _VALID_ORDER_SIDES:
        raise ValueError(f"side must be one of {_VALID_ORDER_SIDES}, got '{side}'")
    if action not in _VALID_ORDER_ACTIONS:
        raise ValueError(f"action must be one of {_VALID_ORDER_ACTIONS}, got '{action}'")
    if order_type not in _VALID_ORDER_TYPES:
        raise ValueError(f"order_type must be one of {_VALID_ORDER_TYPES}, got '{order_type}'")
    if time_in_force not in _VALID_TIME_IN_FORCE:
        raise ValueError(
            f"time_in_force must be one of {_VALID_TIME_IN_FORCE}, got '{time_in_force}'"
        )
    if execution_environment not in _VALID_EXEC_ENVS:
        raise ValueError(
            f"execution_environment must be one of {_VALID_EXEC_ENVS}, "
            f"got '{execution_environment}'"
        )
    if trade_source not in _VALID_TRADE_SOURCES:
        raise ValueError(
            f"trade_source must be one of {_VALID_TRADE_SOURCES}, got '{trade_source}'"
        )

    insert_query = """
        INSERT INTO orders (
            platform_id, external_order_id, client_order_id,
            market_internal_id,
            strategy_id, model_id, edge_id, position_id,
            side, action, order_type, time_in_force,
            requested_price, requested_quantity,
            remaining_quantity, status,
            execution_environment, trade_source,
            order_metadata
        )
        VALUES (
            %s, %s, %s,
            %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, 'submitted',
            %s, %s,
            %s
        )
        RETURNING id
    """

    params = (
        platform_id,
        external_order_id,
        client_order_id,
        market_internal_id,
        strategy_id,
        model_id,
        edge_id,
        position_id,
        side,
        action,
        order_type,
        time_in_force,
        requested_price,
        requested_quantity,
        requested_quantity,  # remaining_quantity = requested_quantity initially
        execution_environment,
        trade_source,
        json.dumps(order_metadata) if order_metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_order_by_id(order_pk: int) -> dict | None:
    """
    Retrieve an order by its surrogate primary key.

    Args:
        order_pk: Integer PK of the order (orders.id)

    Returns:
        Dictionary of column:value pairs, or None if not found.

    Example:
        >>> order = get_order_by_id(42)
        >>> if order:
        ...     print(order['status'], order['filled_quantity'])

    References:
        - Migration 0025: create_orders
    """
    return fetch_one("SELECT * FROM orders WHERE id = %s", (order_pk,))


def get_order_by_external_id(platform_id: str, external_order_id: str) -> dict | None:
    """
    Retrieve an order by its platform + external order ID (unique pair).

    This is the primary lookup path when processing order updates from the
    exchange API, since the exchange provides its own order ID.

    Args:
        platform_id: Platform identifier (e.g. 'kalshi')
        external_order_id: Exchange-assigned order ID

    Returns:
        Dictionary of column:value pairs, or None if not found.

    Example:
        >>> order = get_order_by_external_id('kalshi', 'abc-123')

    References:
        - Migration 0025: UNIQUE(platform_id, external_order_id)
    """
    return fetch_one(
        "SELECT * FROM orders WHERE platform_id = %s AND external_order_id = %s",
        (platform_id, external_order_id),
    )


def update_order_status(order_pk: int, new_status: str) -> bool:
    """
    Update an order's lifecycle status with terminal state guard.

    TERMINAL STATE GUARD (Glokta finding #1): Orders in terminal states
    (filled, cancelled, expired) CANNOT be updated. The WHERE clause rejects
    any attempt to resurrect a terminal order, preventing data corruption.

    Timestamp behavior:
        - filled -> sets filled_at = NOW()
        - cancelled -> sets cancelled_at = NOW()
        - expired -> sets cancelled_at = NOW() (Glokta finding #2: expiration
          is a cancellation variant)
        - All transitions -> sets updated_at = NOW()

    Kalshi Status Mapping:
        Kalshi API uses "executed" (= our "filled") and "canceled" (= our
        "cancelled"). Translate via KALSHI_STATUS_MAP before calling:
            internal = KALSHI_STATUS_MAP.get(kalshi_status, kalshi_status)
            update_order_status(pk, internal)

    Args:
        order_pk: Integer PK of the order
        new_status: Target status (must be in _VALID_ORDER_STATUSES)

    Returns:
        True if the order was updated, False if not found or in terminal state.

    Raises:
        ValueError: If new_status is not a valid order status

    Example:
        >>> success = update_order_status(42, 'resting')
        >>> # Terminal orders silently reject updates:
        >>> update_order_status(42, 'filled')  # True
        >>> update_order_status(42, 'resting')  # False (already terminal)

    References:
        - Migration 0025: create_orders
        - Glokta findings #1, #2, #4
    """
    if new_status not in _VALID_ORDER_STATUSES:
        raise ValueError(f"new_status must be one of {_VALID_ORDER_STATUSES}, got '{new_status}'")

    # Build timestamp updates based on target status
    extra_sets = ""
    if new_status == "filled":
        extra_sets = ", filled_at = NOW()"
    elif new_status in ("cancelled", "expired"):
        # Expired is a cancellation variant (Glokta finding #2)
        extra_sets = ", cancelled_at = NOW()"

    query = f"""
        UPDATE orders
        SET status = %s,
            updated_at = NOW(){extra_sets}
        WHERE id = %s
          AND status NOT IN ('filled', 'cancelled', 'expired')
    """  # noqa: S608 -- extra_sets is built from hardcoded literals, not user input

    with get_cursor(commit=True) as cur:
        cur.execute(query, (new_status, order_pk))
        return int(cur.rowcount or 0) > 0


def update_order_fill(
    order_pk: int,
    fill_quantity: int,
    fill_price: Decimal,
    fees: Decimal = Decimal("0.0000"),
) -> bool:
    """
    Record a fill event on an order (atomic quantity/price/fee update).

    Performs an atomic SQL update that:
    1. Increments filled_quantity by fill_quantity
    2. Decrements remaining_quantity by fill_quantity
    3. Computes weighted average fill price across all fills
    4. Accumulates total_fees
    5. Auto-sets status to 'partial_fill' or 'filled' based on remaining

    Overfill protection: WHERE remaining_quantity >= fill_quantity prevents
    recording more fills than the order requested.

    Terminal state guard: WHERE status NOT IN ('filled', 'cancelled', 'expired')
    prevents fills on already-terminal orders.

    Args:
        order_pk: Integer PK of the order
        fill_quantity: Number of contracts filled in this event (must be > 0)
        fill_price: Execution price as DECIMAL(10,4) in [0, 1]
        fees: Fees for this fill as DECIMAL(10,4) (default 0)

    Returns:
        True if the fill was recorded, False if order not found, already
        terminal, or fill_quantity exceeds remaining.

    Raises:
        TypeError: If fill_price or fees is not Decimal
        ValueError: If fill_quantity <= 0

    Educational Note:
        Weighted Average Price Formula:
            new_avg = (old_avg * old_filled + fill_price * fill_qty) /
                      (old_filled + fill_qty)
        The COALESCE handles the first fill where average_fill_price is NULL.

    Example:
        >>> # First fill: 5 of 10 contracts at 0.55
        >>> update_order_fill(42, 5, Decimal("0.5500"), Decimal("0.0100"))
        >>> # Second fill: remaining 5 at 0.56
        >>> update_order_fill(42, 5, Decimal("0.5600"), Decimal("0.0100"))
        >>> # Order is now 'filled' with average_fill_price ~= 0.5550

    References:
        - Migration 0025: create_orders
        - Glokta finding #3: fill_quantity validation
    """
    # Validate fill_quantity > 0 (Glokta finding #3)
    if fill_quantity <= 0:
        raise ValueError(f"fill_quantity must be > 0, got {fill_quantity}")

    # Runtime type validation (enforces Decimal precision)
    fill_price = validate_decimal(fill_price, "fill_price")
    fees = validate_decimal(fees, "fees")

    query = """
        UPDATE orders
        SET filled_quantity = filled_quantity + %s,
            remaining_quantity = remaining_quantity - %s,
            average_fill_price = (
                COALESCE(average_fill_price, 0) * filled_quantity + %s * %s
            ) / (filled_quantity + %s),
            total_fees = COALESCE(total_fees, 0) + %s,
            status = CASE
                WHEN remaining_quantity - %s = 0 THEN 'filled'
                ELSE 'partial_fill'
            END,
            filled_at = CASE
                WHEN remaining_quantity - %s = 0 THEN NOW()
                ELSE filled_at
            END,
            updated_at = NOW()
        WHERE id = %s
          AND remaining_quantity >= %s
          AND status NOT IN ('filled', 'cancelled', 'expired')
    """

    params = (
        fill_quantity,  # filled_quantity + %s
        fill_quantity,  # remaining_quantity - %s
        fill_price,  # average_fill_price numerator: fill_price * fill_qty
        fill_quantity,  # average_fill_price numerator: fill_price * fill_qty
        fill_quantity,  # average_fill_price denominator
        fees,  # total_fees + %s
        fill_quantity,  # CASE remaining - %s = 0 (status)
        fill_quantity,  # CASE remaining - %s = 0 (filled_at)
        order_pk,  # WHERE id = %s
        fill_quantity,  # WHERE remaining_quantity >= %s
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        return int(cur.rowcount or 0) > 0


def cancel_order(order_pk: int) -> bool:
    """
    Cancel an order if it is still in a cancellable state.

    Only orders with status IN ('submitted', 'resting', 'pending', 'partial_fill')
    can be cancelled. Already-filled, already-cancelled, and expired orders
    are silently rejected (returns False).

    Args:
        order_pk: Integer PK of the order

    Returns:
        True if the order was cancelled, False if not found or not cancellable.

    Example:
        >>> cancel_order(42)  # True if order was open
        >>> cancel_order(42)  # False (already cancelled)

    References:
        - Migration 0025: create_orders
    """
    query = """
        UPDATE orders
        SET status = 'cancelled',
            cancelled_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
          AND status IN ('submitted', 'resting', 'pending', 'partial_fill')
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (order_pk,))
        return int(cur.rowcount or 0) > 0


def get_open_orders(
    strategy_id: int | None = None,
    execution_environment: ExecutionEnvironment | None = None,
    market_internal_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query orders in active (non-terminal) statuses.

    Active statuses: submitted, resting, pending, partial_fill.
    Terminal statuses (excluded): filled, cancelled, expired.

    Args:
        strategy_id: Optional filter by strategy FK
        execution_environment: Optional filter by 'live', 'paper', or 'backtest'
        market_internal_id: Optional filter by market FK
        limit: Maximum rows to return (default 100)

    Returns:
        List of dictionaries, one per open order, ordered by created_at DESC.

    Example:
        >>> orders = get_open_orders(strategy_id=1, execution_environment='paper')
        >>> for o in orders:
        ...     print(o['external_order_id'], o['status'], o['remaining_quantity'])

    References:
        - Migration 0025: create_orders
    """
    query = """
        SELECT * FROM orders
        WHERE status IN ('submitted', 'resting', 'pending', 'partial_fill')
    """
    params: list = []

    if strategy_id is not None:
        query += " AND strategy_id = %s"
        params.append(strategy_id)

    if execution_environment is not None:
        query += " AND execution_environment = %s"
        params.append(execution_environment)

    if market_internal_id is not None:
        query += " AND market_internal_id = %s"
        params.append(market_internal_id)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))


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
        ... )

    References:
        - Migration 0027: temporal_alignment
        - Issue #375: Temporal alignment table
        - migration_batch_plan_v1.md: Migration 0027 spec
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
            game_status, home_score, away_score, period, clock
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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

    Returns:
        Count of rows inserted.

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
            )
        )

    insert_query = """
        INSERT INTO temporal_alignment (
            market_id, market_snapshot_id, game_state_id,
            snapshot_time, game_state_time, time_delta_seconds,
            alignment_quality,
            yes_ask_price, no_ask_price, spread, volume,
            game_status, home_score, away_score, period, clock
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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

    Validates all rows before inserting any. Uses executemany with
    ON CONFLICT DO NOTHING for safe bulk ingestion.

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

        validated_params.append(
            (
                row["platform_id"],
                row["external_trade_id"],
                row["market_internal_id"],
                row["count"],
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (platform_id, external_trade_id) DO NOTHING
    """

    with get_cursor(commit=True) as cur:
        cur.executemany(insert_query, validated_params)
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


# =============================================================================
# ANALYTICS OPERATIONS (Migration 0031 - Analytics Tables)
# =============================================================================

_VALID_RUN_TYPES = frozenset({"model", "strategy", "ensemble"})
_VALID_RUN_STATUSES = frozenset({"running", "completed", "failed", "cancelled"})
_VALID_ENTITY_TYPES = frozenset({"model", "strategy", "evaluation_run", "backtest_run"})


# -----------------------------------------------------------------------------
# Evaluation Runs
# -----------------------------------------------------------------------------


def create_evaluation_run(
    run_type: str,
    model_id: int | None = None,
    strategy_id: int | None = None,
    config: dict | None = None,
) -> int:
    """
    Create an evaluation run record to track model/strategy evaluation.

    Args:
        run_type: One of 'model', 'strategy', 'ensemble'
        model_id: FK to probability_models(model_id) (optional)
        strategy_id: FK to strategies(strategy_id) (optional)
        config: JSONB run configuration (optional)

    Returns:
        Integer surrogate PK (evaluation_runs.id) of the newly created run.

    Raises:
        ValueError: If run_type is invalid

    Example:
        >>> run_id = create_evaluation_run(
        ...     run_type='model',
        ...     model_id=1,
        ...     config={'threshold': '0.05'},
        ... )
    """
    if run_type not in _VALID_RUN_TYPES:
        raise ValueError(f"run_type must be one of {_VALID_RUN_TYPES}, got '{run_type}'")

    insert_query = """
        INSERT INTO evaluation_runs (
            run_type, model_id, strategy_id, config
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """

    params = (
        run_type,
        model_id,
        strategy_id,
        json.dumps(config) if config is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def complete_evaluation_run(
    run_id: int,
    summary: dict | None = None,
    error_message: str | None = None,
    status: str = "completed",
) -> bool:
    """
    Mark an evaluation run as completed (or failed/cancelled).

    Args:
        run_id: PK of the evaluation run
        summary: JSONB results summary (optional)
        error_message: Error details if failed (optional)
        status: Final status -- one of 'completed', 'failed', 'cancelled'

    Returns:
        True if the run was updated, False if run_id not found.

    Raises:
        ValueError: If status is invalid

    Example:
        >>> complete_evaluation_run(
        ...     run_id=1,
        ...     summary={'accuracy': '0.82', 'brier_score': '0.15'},
        ...     status='completed',
        ... )
    """
    if status not in _VALID_RUN_STATUSES:
        raise ValueError(f"status must be one of {_VALID_RUN_STATUSES}, got '{status}'")

    update_query = """
        UPDATE evaluation_runs
        SET status = %s,
            summary = %s,
            error_message = %s,
            completed_at = NOW()
        WHERE id = %s
        RETURNING id
    """

    params = (
        status,
        json.dumps(summary) if summary is not None else None,
        error_message,
        run_id,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(update_query, params)
        result = cur.fetchone()
        return result is not None


def get_evaluation_run(run_id: int) -> dict[str, Any] | None:
    """
    Get an evaluation run by its surrogate PK.

    Args:
        run_id: PK of the evaluation run

    Returns:
        Dictionary with run data, or None if not found.

    Example:
        >>> run = get_evaluation_run(1)
        >>> if run:
        ...     print(f"Run {run['id']}: {run['status']}")
    """
    query = "SELECT * FROM evaluation_runs WHERE id = %s"
    return fetch_one(query, (run_id,))


# -----------------------------------------------------------------------------
# Backtesting Runs
# -----------------------------------------------------------------------------


def create_backtesting_run(
    strategy_id: int | None,
    model_id: int | None,
    config: dict,
    date_range_start: date,
    date_range_end: date,
) -> int:
    """
    Create a backtesting run record to track a backtest experiment.

    Args:
        strategy_id: FK to strategies(strategy_id) (optional)
        model_id: FK to probability_models(model_id) (optional)
        config: JSONB backtest configuration (required)
        date_range_start: Start of backtest date range
        date_range_end: End of backtest date range

    Returns:
        Integer surrogate PK (backtesting_runs.id) of the newly created run.

    Example:
        >>> from datetime import date
        >>> run_id = create_backtesting_run(
        ...     strategy_id=1,
        ...     model_id=2,
        ...     config={'min_edge': '0.05'},
        ...     date_range_start=date(2025, 9, 1),
        ...     date_range_end=date(2026, 1, 31),
        ... )
    """
    insert_query = """
        INSERT INTO backtesting_runs (
            strategy_id, model_id, config,
            date_range_start, date_range_end
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        strategy_id,
        model_id,
        json.dumps(config),
        date_range_start,
        date_range_end,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def complete_backtesting_run(
    run_id: int,
    total_trades: int = 0,
    win_rate: Decimal | None = None,
    total_pnl: Decimal | None = None,
    max_drawdown: Decimal | None = None,
    sharpe_ratio: Decimal | None = None,
    results_detail: dict | None = None,
    error_message: str | None = None,
    status: str = "completed",
) -> bool:
    """
    Mark a backtesting run as completed with result metrics.

    Args:
        run_id: PK of the backtesting run
        total_trades: Total number of simulated trades
        win_rate: Win rate as DECIMAL(10,4)
        total_pnl: Total profit/loss as DECIMAL(10,4)
        max_drawdown: Maximum drawdown as DECIMAL(10,4)
        sharpe_ratio: Sharpe ratio as DECIMAL(10,4)
        results_detail: JSONB with detailed results breakdown
        error_message: Error details if failed
        status: Final status -- one of 'completed', 'failed', 'cancelled'

    Returns:
        True if the run was updated, False if run_id not found.

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If status is invalid

    Example:
        >>> complete_backtesting_run(
        ...     run_id=1,
        ...     total_trades=150,
        ...     win_rate=Decimal("0.5800"),
        ...     total_pnl=Decimal("125.5000"),
        ...     max_drawdown=Decimal("-45.2000"),
        ...     sharpe_ratio=Decimal("1.3200"),
        ...     status='completed',
        ... )
    """
    if status not in _VALID_RUN_STATUSES:
        raise ValueError(f"status must be one of {_VALID_RUN_STATUSES}, got '{status}'")

    # Validate Decimal fields when provided
    if win_rate is not None:
        win_rate = validate_decimal(win_rate, "win_rate")
    if total_pnl is not None:
        total_pnl = validate_decimal(total_pnl, "total_pnl")
    if max_drawdown is not None:
        max_drawdown = validate_decimal(max_drawdown, "max_drawdown")
    if sharpe_ratio is not None:
        sharpe_ratio = validate_decimal(sharpe_ratio, "sharpe_ratio")

    update_query = """
        UPDATE backtesting_runs
        SET status = %s,
            total_trades = %s,
            win_rate = %s,
            total_pnl = %s,
            max_drawdown = %s,
            sharpe_ratio = %s,
            results_detail = %s,
            error_message = %s,
            completed_at = NOW()
        WHERE id = %s
        RETURNING id
    """

    params = (
        status,
        total_trades,
        win_rate,
        total_pnl,
        max_drawdown,
        sharpe_ratio,
        json.dumps(results_detail) if results_detail is not None else None,
        error_message,
        run_id,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(update_query, params)
        result = cur.fetchone()
        return result is not None


def get_backtesting_run(run_id: int) -> dict[str, Any] | None:
    """
    Get a backtesting run by its surrogate PK.

    Args:
        run_id: PK of the backtesting run

    Returns:
        Dictionary with run data, or None if not found.

    Example:
        >>> run = get_backtesting_run(1)
        >>> if run:
        ...     print(f"Backtest {run['id']}: {run['total_trades']} trades, PnL={run['total_pnl']}")
    """
    query = "SELECT * FROM backtesting_runs WHERE id = %s"
    return fetch_one(query, (run_id,))


# -----------------------------------------------------------------------------
# Predictions
# -----------------------------------------------------------------------------


def create_prediction(
    model_id: int | None,
    market_id: int,
    predicted_probability: Decimal,
    confidence: Decimal | None = None,
    market_price_at_prediction: Decimal | None = None,
    edge: Decimal | None = None,
    evaluation_run_id: int | None = None,
    event_id: int | None = None,
) -> int:
    """
    Create a prediction record (live or as part of an evaluation run).

    Args:
        model_id: FK to probability_models(model_id) (optional)
        market_id: FK to markets(id) (required)
        predicted_probability: Model output as DECIMAL(10,4) in [0, 1]
        confidence: Model confidence as DECIMAL(10,4) in [0, 1] (optional)
        market_price_at_prediction: Market price when predicted, DECIMAL(10,4) in [0, 1]
        edge: predicted_probability - market_price (can be negative)
        evaluation_run_id: FK to evaluation_runs(id) (NULL for live predictions)
        event_id: FK to events(id) (optional)

    Returns:
        Integer surrogate PK (predictions.id) of the newly created prediction.

    Raises:
        TypeError: If Decimal fields are not Decimal type
        ValueError: If predicted_probability is out of [0, 1] range

    Example:
        >>> pred_id = create_prediction(
        ...     model_id=1,
        ...     market_id=42,
        ...     predicted_probability=Decimal("0.6500"),
        ...     market_price_at_prediction=Decimal("0.5500"),
        ...     edge=Decimal("0.1000"),
        ... )
    """
    predicted_probability = validate_decimal(predicted_probability, "predicted_probability")
    if predicted_probability < Decimal("0") or predicted_probability > Decimal("1"):
        raise ValueError(
            f"predicted_probability must be between 0 and 1, got {predicted_probability}"
        )

    if confidence is not None:
        confidence = validate_decimal(confidence, "confidence")
        if confidence < Decimal("0") or confidence > Decimal("1"):
            raise ValueError(f"confidence must be between 0 and 1, got {confidence}")

    if market_price_at_prediction is not None:
        market_price_at_prediction = validate_decimal(
            market_price_at_prediction, "market_price_at_prediction"
        )
        if market_price_at_prediction < Decimal("0") or market_price_at_prediction > Decimal("1"):
            raise ValueError(
                f"market_price_at_prediction must be between 0 and 1, "
                f"got {market_price_at_prediction}"
            )

    if edge is not None:
        edge = validate_decimal(edge, "edge")

    insert_query = """
        INSERT INTO predictions (
            evaluation_run_id, model_id,
            market_id, event_id,
            predicted_probability, confidence,
            market_price_at_prediction, edge
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        evaluation_run_id,
        model_id,
        market_id,
        event_id,
        predicted_probability,
        confidence,
        market_price_at_prediction,
        edge,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def resolve_prediction(
    prediction_id: int,
    actual_outcome: Decimal,
    is_correct: bool,
) -> bool:
    """
    Resolve a prediction by recording the actual outcome.

    Args:
        prediction_id: PK of the prediction
        actual_outcome: Actual outcome as DECIMAL(10,4) in [0, 1]
        is_correct: Whether the prediction was correct

    Returns:
        True if the prediction was updated, False if prediction_id not found.

    Raises:
        TypeError: If actual_outcome is not Decimal
        ValueError: If actual_outcome is out of [0, 1] range

    Example:
        >>> resolve_prediction(
        ...     prediction_id=1,
        ...     actual_outcome=Decimal("1.0000"),
        ...     is_correct=True,
        ... )
    """
    actual_outcome = validate_decimal(actual_outcome, "actual_outcome")
    if actual_outcome < Decimal("0") or actual_outcome > Decimal("1"):
        raise ValueError(f"actual_outcome must be between 0 and 1, got {actual_outcome}")

    update_query = """
        UPDATE predictions
        SET actual_outcome = %s,
            is_correct = %s,
            resolved_at = NOW()
        WHERE id = %s
        RETURNING id
    """

    params = (actual_outcome, is_correct, prediction_id)

    with get_cursor(commit=True) as cur:
        cur.execute(update_query, params)
        result = cur.fetchone()
        return result is not None


def get_predictions_by_run(
    evaluation_run_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get predictions for a specific evaluation run.

    Args:
        evaluation_run_id: FK to evaluation_runs(id)
        limit: Maximum number of predictions to return (default 100)

    Returns:
        List of prediction dictionaries ordered by predicted_at DESC.

    Example:
        >>> preds = get_predictions_by_run(evaluation_run_id=1)
        >>> for p in preds:
        ...     print(f"Market {p['market_id']}: {p['predicted_probability']}")
    """
    query = """
        SELECT * FROM predictions
        WHERE evaluation_run_id = %s
        ORDER BY predicted_at DESC, id DESC
        LIMIT %s
    """
    return fetch_all(query, (evaluation_run_id, limit))


def get_unresolved_predictions(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get predictions that have not yet been resolved (actual_outcome IS NULL).

    Args:
        limit: Maximum number of predictions to return (default 100)

    Returns:
        List of unresolved prediction dictionaries ordered by predicted_at DESC.

    Example:
        >>> unresolved = get_unresolved_predictions(limit=50)
        >>> print(f"{len(unresolved)} predictions awaiting resolution")
    """
    query = """
        SELECT * FROM predictions
        WHERE actual_outcome IS NULL
        ORDER BY predicted_at DESC, id DESC
        LIMIT %s
    """
    return fetch_all(query, (limit,))


# -----------------------------------------------------------------------------
# Performance Metrics
# -----------------------------------------------------------------------------


def upsert_performance_metric(
    entity_type: str,
    entity_id: int,
    metric_name: str,
    metric_value: Decimal,
    period_start: date | None = None,
    period_end: date | None = None,
    sample_size: int | None = None,
    metadata: dict | None = None,
) -> int:
    """
    Insert or update a performance metric (upsert on unique constraint).

    Args:
        entity_type: One of 'model', 'strategy', 'evaluation_run', 'backtest_run'
        entity_id: PK of the entity
        metric_name: Name of the metric (e.g., 'accuracy', 'brier_score')
        metric_value: Metric value as DECIMAL(10,4)
        period_start: Start of measurement period (optional)
        period_end: End of measurement period (optional)
        sample_size: Number of samples in calculation (optional)
        metadata: Additional context as JSONB (optional)

    Returns:
        Integer surrogate PK (performance_metrics.id).

    Raises:
        TypeError: If metric_value is not Decimal
        ValueError: If entity_type is invalid

    Example:
        >>> metric_id = upsert_performance_metric(
        ...     entity_type='model',
        ...     entity_id=1,
        ...     metric_name='brier_score',
        ...     metric_value=Decimal("0.1500"),
        ...     period_start=date(2026, 1, 1),
        ...     period_end=date(2026, 3, 31),
        ...     sample_size=500,
        ... )
    """
    if entity_type not in _VALID_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {_VALID_ENTITY_TYPES}, got '{entity_type}'")
    metric_value = validate_decimal(metric_value, "metric_value")

    upsert_query = """
        INSERT INTO performance_metrics (
            entity_type, entity_id, metric_name, metric_value,
            period_start, period_end, sample_size, metadata,
            calculated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (entity_type, entity_id, metric_name, period_start, period_end)
        DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            sample_size = EXCLUDED.sample_size,
            metadata = EXCLUDED.metadata,
            calculated_at = NOW()
        RETURNING id
    """

    params = (
        entity_type,
        entity_id,
        metric_name,
        metric_value,
        period_start,
        period_end,
        sample_size,
        json.dumps(metadata) if metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(upsert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_performance_metrics(
    entity_type: str,
    entity_id: int,
    metric_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get performance metrics for a specific entity.

    Args:
        entity_type: One of 'model', 'strategy', 'evaluation_run', 'backtest_run'
        entity_id: PK of the entity
        metric_name: Optional filter by metric name

    Returns:
        List of metric dictionaries ordered by calculated_at DESC.

    Raises:
        ValueError: If entity_type is invalid

    Example:
        >>> metrics = get_performance_metrics('model', entity_id=1)
        >>> for m in metrics:
        ...     print(f"{m['metric_name']}: {m['metric_value']}")
    """
    if entity_type not in _VALID_ENTITY_TYPES:
        raise ValueError(f"entity_type must be one of {_VALID_ENTITY_TYPES}, got '{entity_type}'")

    query = "SELECT * FROM performance_metrics WHERE entity_type = %s AND entity_id = %s"
    params: list = [entity_type, entity_id]

    if metric_name is not None:
        query += " AND metric_name = %s"
        params.append(metric_name)

    query += " ORDER BY calculated_at DESC, id DESC"

    return fetch_all(query, tuple(params))


# =============================================================================
# ORDERBOOK SNAPSHOT OPERATIONS (Migration 0034)
# =============================================================================


def insert_orderbook_snapshot(
    market_internal_id: int,
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
        market_internal_id: Integer FK to markets(id)
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
        ...     market_internal_id=42,
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
            market_internal_id, best_bid, best_ask, spread,
            bid_depth_total, ask_depth_total, depth_imbalance, weighted_mid,
            bid_prices, bid_quantities, ask_prices, ask_quantities, levels,
            snapshot_time
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
    """

    params = (
        market_internal_id,
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


def get_latest_orderbook(market_internal_id: int) -> dict[str, Any] | None:
    """
    Get the most recent order book snapshot for a market.

    Args:
        market_internal_id: Integer FK to markets(id)

    Returns:
        Dictionary of snapshot columns, or None if no snapshots exist

    Example:
        >>> snapshot = get_latest_orderbook(market_internal_id=42)
        >>> if snapshot:
        ...     print(snapshot['spread'], snapshot['depth_imbalance'])

    References:
        - Migration 0034: orderbook_snapshots table
    """
    query = """
        SELECT * FROM orderbook_snapshots
        WHERE market_internal_id = %s
        ORDER BY snapshot_time DESC
        LIMIT 1
    """
    return fetch_one(query, (market_internal_id,))


def get_orderbook_history(
    market_internal_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get order book snapshot history for a market, newest first.

    Args:
        market_internal_id: Integer FK to markets(id)
        limit: Maximum number of snapshots to return (default: 100)

    Returns:
        List of snapshot dictionaries, ordered by snapshot_time DESC

    Example:
        >>> history = get_orderbook_history(market_internal_id=42, limit=50)
        >>> for snap in history:
        ...     print(snap['snapshot_time'], snap['spread'], snap['levels'])

    References:
        - Migration 0034: orderbook_snapshots table
    """
    query = """
        SELECT * FROM orderbook_snapshots
        WHERE market_internal_id = %s
        ORDER BY snapshot_time DESC
        LIMIT %s
    """
    return fetch_all(query, (market_internal_id, limit))


# =============================================================================
# Games Dimension CRUD (Migration 0035)
# =============================================================================


def get_or_create_game(
    sport: str,
    game_date: date,
    home_team_code: str,
    away_team_code: str,
    *,
    season: int | None = None,
    league: str | None = None,
    season_type: str | None = None,
    week_number: int | None = None,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    venue_id: int | None = None,
    venue_name: str | None = None,
    neutral_site: bool = False,
    is_playoff: bool = False,
    game_type: str | None = None,
    game_time: datetime | None = None,
    espn_event_id: str | None = None,
    external_game_id: str | None = None,
    game_status: str = "scheduled",
    data_source: str = "espn",
    home_score: int | None = None,
    away_score: int | None = None,
    source_file: str | None = None,
    attendance: int | None = None,
) -> int:
    """
    Insert or update a game in the games dimension table (idempotent).

    Uses ON CONFLICT on the natural key (sport, game_date, home_team_code,
    away_team_code) to upsert. On conflict, updates non-null fields via
    COALESCE to avoid overwriting good data with NULLs.

    Args:
        sport: Sport code ('nfl', 'nba', etc.)
        game_date: Date of the game
        home_team_code: Home team abbreviation (e.g., 'KC')
        away_team_code: Away team abbreviation (e.g., 'BAL')
        season: Season year (derived from game_date if not provided)
        league: League code (defaults to sport if not provided)
        season_type: Season phase ('regular', 'playoff', etc.)
        week_number: Week number within season
        home_team_id: FK to teams.team_id for home team
        away_team_id: FK to teams.team_id for away team
        venue_id: FK to venues.venue_id
        venue_name: Denormalized venue name
        neutral_site: True if neutral venue
        is_playoff: True if playoff game
        game_type: Game classification ('regular', 'playoff', etc.)
        game_time: Precise game start timestamp
        espn_event_id: ESPN event identifier for cross-source linking
        external_game_id: External game identifier
        game_status: Current status ('scheduled', 'final', etc.)
        data_source: Data provenance ('espn', 'fivethirtyeight', etc.)
        home_score: Home team final score
        away_score: Away team final score
        source_file: Source filename for file-based imports
        attendance: Game attendance

    Returns:
        id of the games row (created or existing)

    Example:
        >>> game_id = get_or_create_game(
        ...     sport="nfl",
        ...     game_date=date(2024, 9, 8),
        ...     home_team_code="KC",
        ...     away_team_code="BAL",
        ...     season=2024,
        ...     league="nfl",
        ...     espn_event_id="401547417",
        ...     game_status="final",
        ... )

    References:
        - Migration 0035: games dimension table
        - Issue #439: Games dimension unification
    """
    # Derive season from game_date year if not provided
    if season is None:
        season = game_date.year

    # Default league to sport
    if league is None:
        league = sport

    query = """
        INSERT INTO games (
            sport, game_date, home_team_code, away_team_code,
            season, league, season_type, week_number,
            home_team_id, away_team_id, venue_id, venue_name,
            neutral_site, is_playoff, game_type,
            game_time, espn_event_id, external_game_id,
            game_status, data_source,
            home_score, away_score, source_file, attendance
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (sport, game_date, home_team_code, away_team_code) DO UPDATE SET
            updated_at = NOW(),
            espn_event_id = COALESCE(EXCLUDED.espn_event_id, games.espn_event_id),
            game_status = CASE
                WHEN games.game_status IN ('final', 'final_ot') THEN games.game_status
                ELSE EXCLUDED.game_status
            END,
            home_team_id = COALESCE(EXCLUDED.home_team_id, games.home_team_id),
            away_team_id = COALESCE(EXCLUDED.away_team_id, games.away_team_id),
            venue_id = COALESCE(EXCLUDED.venue_id, games.venue_id),
            venue_name = COALESCE(EXCLUDED.venue_name, games.venue_name),
            season_type = COALESCE(EXCLUDED.season_type, games.season_type),
            week_number = COALESCE(EXCLUDED.week_number, games.week_number),
            game_time = COALESCE(EXCLUDED.game_time, games.game_time),
            neutral_site = EXCLUDED.neutral_site,
            is_playoff = EXCLUDED.is_playoff,
            game_type = COALESCE(EXCLUDED.game_type, games.game_type),
            home_score = COALESCE(EXCLUDED.home_score, games.home_score),
            away_score = COALESCE(EXCLUDED.away_score, games.away_score),
            data_source = EXCLUDED.data_source,
            source_file = COALESCE(EXCLUDED.source_file, games.source_file),
            attendance = COALESCE(EXCLUDED.attendance, games.attendance)
        RETURNING id
    """
    params = (
        sport,
        game_date,
        home_team_code,
        away_team_code,
        season,
        league,
        season_type,
        week_number,
        home_team_id,
        away_team_id,
        venue_id,
        venue_name,
        neutral_site,
        is_playoff,
        game_type,
        game_time,
        espn_event_id,
        external_game_id,
        game_status,
        data_source,
        home_score,
        away_score,
        source_file,
        attendance,
    )
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def update_game_result(
    game_id: int,
    home_score: int,
    away_score: int,
) -> None:
    """
    Update final scores, margin, and result for a completed game.

    Called by the ESPN poller when game_status transitions to 'final' or
    'final_ot'. Computes actual_margin (home - away) and result
    ('home_win', 'away_win', 'draw') automatically.

    Args:
        game_id: Primary key of the games row
        home_score: Home team final score
        away_score: Away team final score

    Example:
        >>> update_game_result(game_id=42, home_score=27, away_score=20)
        # Sets actual_margin=7, result='home_win'

    References:
        - Migration 0035: games dimension table
    """
    # Compute derived fields
    actual_margin = home_score - away_score
    if home_score > away_score:
        result = "home_win"
    elif away_score > home_score:
        result = "away_win"
    else:
        result = "draw"

    query = """
        UPDATE games
        SET home_score = %s,
            away_score = %s,
            actual_margin = %s,
            result = %s,
            updated_at = NOW()
        WHERE id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (home_score, away_score, actual_margin, result, game_id))
