# Data Collection Guide

---

**Version:** 1.1
**Created:** 2025-11-24
**Last Updated:** 2025-11-28
**Status:** 🔵 Planned (Phase 3+)
**Target Audience:** Developers implementing automated data collection pipelines for model training
**Prerequisites:** API_INTEGRATION_GUIDE_V2.0.md, MODEL_TRAINING_GUIDE_V1.0.md
**Related Documents:**
- `docs/guides/MODEL_MANAGER_USER_GUIDE_V1.1.md` (Future Enhancements - Data Collection Pipelines)
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md` (ESPN, Kalshi, Balldontlie APIs)
- `docs/foundation/MASTER_REQUIREMENTS_V2.18.md` (REQ-DATA-001 through REQ-DATA-006)
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.25.md` (ADR-002: Decimal Precision, ADR-053: Data Validation, ADR-076: Sports Data Source Tiering)

**Changes in V1.1:**
- **SPORTS DATA SOURCE TIERING STRATEGY:** Added Section 11 documenting 3-tier data source architecture
- **ESPN LATENCY CORRECTION:** Changed ESPN latency from "5-15 min" to "UNKNOWN - requires empirical measurement"
- **ESPN RATE LIMITING:** Added self-imposed rate limits for ESPN Hidden API (live game monitoring only, NOT for historical data)
- Added sportsdataverse-py and nflreadpy integration examples for historical data (Tier 1, bulk download, no rate limits)
- Added verified API pricing reference table (MySportsFeeds, Sportradar, Balldontlie)
- **STRATEGY LATENCY TOLERANCE MATRIX:** Added guidance for acceptable delay (10-30s survivable, minutes NOT)
- **LAG-AWARE STRATEGY DESIGN:** Added StrategyConfig pattern with max_tolerated_lag_seconds
- **BOOTSTRAP-FIRST APPROACH:** Added two-stage FREE → PAID upgrade path
- **MULTI-SOURCE RECONCILIATION:** Added GameStateWithConfidence dataclass and confidence scoring
- **GAMESTATEROVIDER ABSTRACTION:** Added source_confidence property and use_free_only parameter
- ✅ **Added:** ADR-076 (Sports Data Source Tiering Strategy) in ARCHITECTURE_DECISIONS_V2.25.md
- ✅ **Documented:** STRATEGY_DEVELOPMENT_GUIDE_V1.0.md as Phase 4 deliverable in DEVELOPMENT_PHASES_V1.9.md

---

## Table of Contents

1. [Overview](#overview)
2. [Data Sources](#data-sources)
3. [DataCollector Implementation](#datacollector-implementation)
4. [Multi-Source Collection](#multi-source-collection)
5. [Incremental Updates](#incremental-updates)
6. [Data Validation](#data-validation)
7. [Data Storage](#data-storage)
8. [Scheduling & Automation](#scheduling--automation)
9. [Error Handling & Retry Logic](#error-handling--retry-logic)
10. [Testing & Validation](#testing--validation)
11. [Data Source Tiering Strategy](#data-source-tiering-strategy) **NEW**

---

## 1. Overview

### What is Data Collection?

**Data Collection** is the automated process of fetching sports data from external APIs for model training and predictions.

**Key Data Types:**
- **Game Results:** NFL/NBA game outcomes (wins/losses, scores)
- **Team Stats:** Season-long statistics (points per game, defensive efficiency)
- **Player Stats:** Individual performance metrics (passing yards, turnovers)
- **Market Prices:** Historical Kalshi market prices (implied probabilities)

**Why Automated Collection?**
- **Consistency:** Collect data on schedule (daily, hourly)
- **Freshness:** Models need recent data for accurate predictions
- **Scalability:** Manually collecting 1000+ games per season is impractical
- **Reproducibility:** Same pipeline produces same data (version control)

### Implementation Scope

**Phase 3+** - This guide documents the `DataCollector` class for automated multi-source data collection.

**Key Features:**
- Multi-source collection (ESPN, Kalshi, Balldontlie APIs)
- Incremental updates (fetch only new data since last collection)
- Data validation (schema validation, outlier detection, missing values)
- Data storage (PostgreSQL tables: `games`, `team_stats`, `player_stats`, `market_prices`)
- Scheduling (daily/hourly automated collection via event loop)

---

## 2. Data Sources

### ESPN API (Game Results)

**Purpose:** Fetch NFL/NBA game results for model training

**Endpoints:**
- `GET /sports/football/nfl/scoreboard?dates={YYYYMMDD}` - NFL game scores
- `GET /sports/basketball/nba/scoreboard?dates={YYYYMMDD}` - NBA game scores

**Data Fields:**
```json
{
  "date": "2024-11-24",
  "home_team": "BUF",
  "away_team": "MIA",
  "home_score": 31,
  "away_score": 24,
  "status": "final",
  "game_id": "401671890"
}
```

**Rate Limiting (CRITICAL):**

The ESPN API is a **hidden/undocumented API** with no published rate limits. However, aggressive usage can result in:
- **Temporary throttling** (429 responses)
- **IP blocking** (403 Forbidden, potentially permanent)
- **Increased latency** (server-side queuing)

**Our Self-Imposed Rate Limits:**

| Use Case | Rate Limit | Rationale |
|----------|------------|-----------|
| **Historical data collection** | 10 req/sec | Bulk collection should be polite |
| **Live game monitoring** | 1 req/10 sec per game | Balance freshness vs. load |
| **Development/testing** | 5 req/sec | Fast iteration without abuse |

**Implementation:**
```python
from precog.api_connectors.rate_limiter import RateLimiter

# ESPN rate limiter (10 requests/second for historical collection)
espn_limiter = RateLimiter(
    max_requests=10,
    time_window=1.0,  # 1 second
    name="espn_api"
)

# Use with ESPN API calls
async def fetch_espn_scoreboard(date: str) -> dict:
    """Fetch ESPN scoreboard with rate limiting."""
    await espn_limiter.acquire()  # Block until rate limit allows

    response = requests.get(
        f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        params={'dates': date},
        timeout=10
    )
    response.raise_for_status()
    return response.json()
```

**Best Practices:**
1. **Always use rate limiter** - Even "unlimited" APIs can throttle aggressive clients
2. **Add jitter** - Randomize request timing to avoid thundering herd
3. **Respect 429 responses** - Implement exponential backoff (see Section 9)
4. **Cache aggressively** - Don't re-fetch data that hasn't changed
5. **Monitor for errors** - Track 429/403 responses to detect throttling early

**Documentation:** https://gist.github.com/nntrn/ee26cb2a0716de0947a0a4e9a157bc1c

### Kalshi API (Market Prices)

**Purpose:** Fetch historical market prices for backtesting

**Endpoints:**
- `GET /markets?series_ticker=KXNFLGAME&status=settled` - NFL settled markets
- `GET /markets/{ticker}/history` - Historical price data

**Data Fields:**
```json
{
  "ticker": "KXNFL-2024-11-24-BUF-MIA",
  "yes_price": 0.52,
  "no_price": 0.48,
  "volume": 1247,
  "timestamp": "2024-11-24T15:30:00Z"
}
```

**Rate Limit:** 100 requests/minute

**Documentation:** https://trading-api.readme.io/reference/getmarkets

### Balldontlie API (NBA Stats)

**Purpose:** Fetch advanced NBA player statistics

**Endpoints:**
- `GET /stats?seasons[]=2024&player_ids[]={id}` - Player game stats
- `GET /players?search={name}` - Player lookup

**Data Fields:**
```json
{
  "player_id": 237,
  "player_name": "LeBron James",
  "team": "LAL",
  "points": 28,
  "assists": 7,
  "rebounds": 11,
  "game_id": "2024-11-24-LAL-DEN"
}
```

**Rate Limit:** 60 requests/minute

**Documentation:** https://www.balldontlie.io/api/v1

---

## 3. DataCollector Implementation

### Class Overview

**File:** `src/precog/data/data_collector.py` (~400 lines)

**Purpose:** Automated data collection from multiple external APIs.

**Key Responsibilities:**
1. Fetch data from ESPN, Kalshi, Balldontlie APIs
2. Validate data schemas and detect anomalies
3. Transform data to internal format (Decimal precision)
4. Store data in PostgreSQL database
5. Track last collection timestamps (incremental updates)
6. Handle errors and retry failed requests

### Constructor

```python
"""
Data Collector for Model Training

Automated data collection from ESPN, Kalshi, and Balldontlie APIs.
Supports incremental updates and comprehensive data validation.

Educational Note:
    Data collection is the FOUNDATION of model training. Poor quality data
    (missing values, outliers, schema mismatches) leads to poor model predictions.

    This class enforces:
    - Schema validation (all expected fields present)
    - Type safety (Decimal for prices, int for scores)
    - Outlier detection (score > 100 in NFL is suspicious)
    - Incremental updates (avoid re-fetching existing data)

Related Requirements:
    - REQ-DATA-001: Multi-source data collection
    - REQ-DATA-002: Data validation
    - REQ-DATA-003: Incremental updates
    - REQ-DATA-004: Error handling and retry logic

Reference:
    - docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md (API details)
    - docs/guides/MODEL_TRAINING_GUIDE_V1.0.md (how data is used)
"""
from decimal import Decimal
from typing import Any
from datetime import datetime, timedelta
import requests

from precog.database.crud_operations import CRUDOperations
from precog.utils.logger import get_logger


class DataCollector:
    """
    Automated data collection from multiple sports APIs.

    Collects game results, team stats, player stats, and market prices
    for model training and backtesting.
    """

    def __init__(
        self,
        crud: CRUDOperations,
        espn_base_url: str = "https://site.api.espn.com/apis/site/v2",
        balldontlie_api_key: str | None = None
    ):
        """
        Initialize DataCollector.

        Args:
            crud: Database CRUD operations for data storage
            espn_base_url: ESPN API base URL (default production)
            balldontlie_api_key: Balldontlie API key (optional, public tier if None)

        Educational Note:
            ESPN API is public (no auth required).
            Balldontlie API has free tier (60 req/min) and paid tier (120 req/min).
            Kalshi API requires RSA-PSS authentication (see KalshiClient).
        """
        self.crud = crud
        self.espn_base_url = espn_base_url
        self.balldontlie_api_key = balldontlie_api_key
        self.logger = get_logger(__name__)

        # Track last collection timestamps for incremental updates
        self._last_nfl_collection = None
        self._last_nba_collection = None
        self._last_kalshi_collection = None
```

---

## 4. Multi-Source Collection

### collect_nfl_games() Method

```python
def collect_nfl_games(
    self,
    start_date: str,
    end_date: str,
    incremental: bool = False
) -> dict[str, Any]:
    """
    Collect NFL game results from ESPN API.

    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        incremental: If True, only fetch games newer than last collection

    Returns:
        Collection summary:
        {
            'games_count': int,
            'new_games': int,
            'updated_games': int,
            'validation_errors': int,
            'collection_time': float (seconds)
        }

    Raises:
        APIError: If ESPN API request fails
        ValidationError: If response schema is invalid

    Educational Note:
        Incremental Collection Strategy:
        - First run: Fetch ALL games in date range (expensive, 100+ API calls)
        - Subsequent runs: Only fetch games after last collection (cheap, 5-10 calls)

        Why incremental?
        - ESPN API has no rate limit, but we're polite (don't hammer their servers)
        - Faster collection (5 sec vs 60 sec for full season)
        - Reduces database writes (only new/updated games)

    Example:
        >>> collector = DataCollector(crud)

        >>> # First collection: Full season (Week 1-12)
        >>> result = collector.collect_nfl_games(
        ...     start_date="2024-09-01",
        ...     end_date="2024-11-24",
        ...     incremental=False  # Fetch ALL games
        ... )
        >>> print(f"Collected {result['games_count']} games in {result['collection_time']:.1f}s")
        Collected 142 games in 58.3s

        >>> # Subsequent collection: Only new games (Week 13)
        >>> result = collector.collect_nfl_games(
        ...     start_date="2024-09-01",
        ...     end_date="2024-12-01",
        ...     incremental=True  # Only fetch games after last collection
        ... )
        >>> print(f"Collected {result['new_games']} new games in {result['collection_time']:.1f}s")
        Collected 16 new games in 4.7s
    """
    import time
    start_time = time.time()

    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # If incremental, only fetch games after last collection
    if incremental and self._last_nfl_collection:
        start = max(start, self._last_nfl_collection)
        self.logger.info(
            f"Incremental collection: fetching games from {start.strftime('%Y-%m-%d')}",
            extra={'incremental': True, 'last_collection': str(self._last_nfl_collection)}
        )

    games_collected = []
    validation_errors = 0

    # Iterate over dates (ESPN API requires single-day queries)
    current_date = start
    while current_date <= end:
        date_str = current_date.strftime("%Y%m%d")  # ESPN format: YYYYMMDD

        try:
            # Fetch scoreboard for this date
            response = requests.get(
                f"{self.espn_base_url}/sports/football/nfl/scoreboard",
                params={'dates': date_str},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            # Parse games from response
            for event in data.get('events', []):
                try:
                    game = self._parse_espn_game(event, sport='nfl')
                    games_collected.append(game)
                except ValidationError as e:
                    self.logger.warning(
                        f"Validation error for game on {date_str}: {e}",
                        extra={'date': date_str, 'error': str(e)}
                    )
                    validation_errors += 1

        except requests.RequestException as e:
            self.logger.error(
                f"Failed to fetch NFL games for {date_str}: {e}",
                extra={'date': date_str, 'error': str(e)}
            )
            # Continue to next date (don't fail entire collection)

        current_date += timedelta(days=1)

    # Store games in database
    new_games = 0
    updated_games = 0

    for game in games_collected:
        existing_game = self.crud.read(
            table='games',
            filters={'game_id': game['game_id']}
        )

        if existing_game:
            # Game exists, update if status changed (in_progress → final)
            if existing_game['status'] != game['status']:
                self.crud.update(
                    table='games',
                    filters={'game_id': game['game_id']},
                    data=game
                )
                updated_games += 1
        else:
            # New game, insert
            self.crud.create(table='games', data=game)
            new_games += 1

    # Update last collection timestamp
    self._last_nfl_collection = datetime.utcnow()

    collection_time = time.time() - start_time

    self.logger.info(
        f"NFL collection complete: {new_games} new, {updated_games} updated, {validation_errors} errors",
        extra={
            'games_count': len(games_collected),
            'new_games': new_games,
            'updated_games': updated_games,
            'validation_errors': validation_errors,
            'collection_time': collection_time
        }
    )

    return {
        'games_count': len(games_collected),
        'new_games': new_games,
        'updated_games': updated_games,
        'validation_errors': validation_errors,
        'collection_time': collection_time
    }
```

---

## 5. Incremental Updates

### Why Incremental Updates?

**Problem:** Re-fetching ALL historical data every day is wasteful:
- 1000+ games per season x 4 sports = 4000+ API calls
- 60+ seconds collection time
- Unnecessary database writes (99% of games unchanged)

**Solution:** Track last collection timestamp, only fetch new data.

**Approach:**
1. Store `last_collection_timestamp` for each data source (NFL, NBA, Kalshi)
2. On subsequent collections, only fetch data where `created_at > last_collection_timestamp`
3. Update `last_collection_timestamp` after successful collection

### Tracking Last Collection

```python
def _get_last_collection_timestamp(self, source: str) -> datetime | None:
    """
    Get last successful collection timestamp for data source.

    Args:
        source: Data source name ('nfl', 'nba', 'kalshi')

    Returns:
        Last collection timestamp, or None if never collected.

    Educational Note:
        We store last collection timestamps in database table:
        CREATE TABLE data_collection_log (
            id SERIAL PRIMARY KEY,
            source VARCHAR(50) NOT NULL,
            last_collection_at TIMESTAMP NOT NULL,
            status VARCHAR(20) NOT NULL,  -- 'success', 'partial', 'failed'
            games_collected INT,
            errors INT
        );

        This provides audit trail of all collections (when, how many, errors).
    """
    log = self.crud.read(
        table='data_collection_log',
        filters={'source': source},
        order_by='last_collection_at DESC',
        limit=1
    )

    if log and log['status'] == 'success':
        return log['last_collection_at']

    return None

def _update_collection_timestamp(
    self,
    source: str,
    status: str,
    games_collected: int,
    errors: int
):
    """
    Update last collection timestamp after collection.

    Args:
        source: Data source name
        status: Collection status ('success', 'partial', 'failed')
        games_collected: Number of games collected
        errors: Number of validation errors

    Educational Note:
        We log EVERY collection attempt (success or failure).
        This helps debug collection issues:
        - "Why did NBA collection fail last night?" → Check log, see API timeout
        - "How many games collected per day on average?" → Query log, calculate mean
    """
    self.crud.create(
        table='data_collection_log',
        data={
            'source': source,
            'last_collection_at': datetime.utcnow(),
            'status': status,
            'games_collected': games_collected,
            'errors': errors
        }
    )
```

---

## 6. Data Validation

### Schema Validation

**Purpose:** Ensure API responses match expected structure.

**Example:**
```python
def _validate_game_schema(self, game: dict[str, Any], sport: str) -> None:
    """
    Validate game data schema.

    Args:
        game: Parsed game data
        sport: Sport type ('nfl', 'nba')

    Raises:
        ValidationError: If schema is invalid

    Educational Note:
        Required fields for NFL games:
        - game_id (str)
        - date (str, YYYY-MM-DD)
        - home_team (str, 3-letter code)
        - away_team (str, 3-letter code)
        - home_score (int, 0-100)
        - away_score (int, 0-100)
        - status (str, 'scheduled', 'in_progress', 'final')

        Missing ANY field → ValidationError (don't store incomplete data)
    """
    required_fields = {
        'game_id': str,
        'date': str,
        'home_team': str,
        'away_team': str,
        'home_score': int,
        'away_score': int,
        'status': str
    }

    for field, expected_type in required_fields.items():
        if field not in game:
            raise ValidationError(f"Missing required field: {field}")

        if not isinstance(game[field], expected_type):
            raise ValidationError(
                f"Field '{field}' has wrong type: expected {expected_type}, got {type(game[field])}"
            )

    # Sport-specific validation
    if sport == 'nfl':
        # NFL scores typically 0-60 (outlier detection)
        if game['home_score'] > 100 or game['away_score'] > 100:
            raise ValidationError(
                f"Suspiciously high score: {game['home_team']} {game['home_score']}, "
                f"{game['away_team']} {game['away_score']}"
            )

    # Valid status values
    valid_statuses = {'scheduled', 'in_progress', 'final', 'postponed', 'cancelled'}
    if game['status'] not in valid_statuses:
        raise ValidationError(f"Invalid status: {game['status']}")
```

### Outlier Detection

```python
def _detect_outliers(self, game: dict[str, Any], sport: str) -> list[str]:
    """
    Detect statistical outliers in game data.

    Args:
        game: Parsed game data
        sport: Sport type

    Returns:
        List of outlier warnings (empty if no outliers)

    Educational Note:
        Outlier Detection Rules (NFL):
        1. Score > 60: Possible data error (NFL record is 73 points)
        2. Score = 0: Shutout (rare, verify correct)
        3. Total points > 100: Possible overtime or error
        4. Score difference > 50: Blowout (verify correct)

        Outliers don't fail validation, but log warnings for manual review.
    """
    warnings = []

    if sport == 'nfl':
        # High score warning
        if game['home_score'] > 60:
            warnings.append(f"High score: {game['home_team']} scored {game['home_score']}")
        if game['away_score'] > 60:
            warnings.append(f"High score: {game['away_team']} scored {game['away_score']}")

        # Shutout warning
        if game['home_score'] == 0 or game['away_score'] == 0:
            warnings.append(f"Shutout: {game['home_team']} {game['home_score']}, {game['away_team']} {game['away_score']}")

        # Blowout warning
        score_diff = abs(game['home_score'] - game['away_score'])
        if score_diff > 50:
            warnings.append(f"Blowout: {score_diff} point difference")

    return warnings
```

---

## 7. Data Storage

### Database Schema

**Table:** `games`

```sql
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(50) UNIQUE NOT NULL,  -- ESPN game ID
    sport VARCHAR(20) NOT NULL,  -- 'nfl', 'nba'
    date DATE NOT NULL,
    home_team VARCHAR(10) NOT NULL,  -- 3-letter team code
    away_team VARCHAR(10) NOT NULL,
    home_score INTEGER,  -- NULL if game not started
    away_score INTEGER,
    status VARCHAR(20) NOT NULL,  -- 'scheduled', 'in_progress', 'final'
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes for querying
    INDEX idx_games_sport_date (sport, date),
    INDEX idx_games_team (home_team, away_team),
    INDEX idx_games_status (status)
);
```

**Table:** `market_prices`

```sql
CREATE TABLE market_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(100) NOT NULL,  -- Kalshi market ticker
    yes_price DECIMAL(10,4) NOT NULL,  -- YES side price (0.0000-1.0000)
    no_price DECIMAL(10,4) NOT NULL,   -- NO side price
    volume INTEGER NOT NULL,  -- Total contracts traded
    timestamp TIMESTAMP NOT NULL,  -- Price timestamp from Kalshi
    collected_at TIMESTAMP NOT NULL DEFAULT NOW(),  -- When we fetched it

    -- Indexes for backtesting queries
    INDEX idx_market_prices_ticker (ticker),
    INDEX idx_market_prices_timestamp (timestamp),
    INDEX idx_market_prices_ticker_timestamp (ticker, timestamp)
);
```

### Storage Best Practices

```python
def _store_games(self, games: list[dict[str, Any]]) -> dict[str, int]:
    """
    Store games in database with upsert logic.

    Args:
        games: List of validated game data

    Returns:
        {'new': int, 'updated': int, 'skipped': int}

    Educational Note:
        Upsert Logic (Insert or Update):
        1. Check if game_id exists in database
        2. If exists AND status changed → UPDATE (in_progress → final)
        3. If exists AND status same → SKIP (no changes)
        4. If not exists → INSERT (new game)

        Why upsert?
        - Games collected before start (status='scheduled')
        - Games collected during play (status='in_progress')
        - Games collected after finish (status='final')

        We need to update status as games progress.
    """
    new_count = 0
    updated_count = 0
    skipped_count = 0

    for game in games:
        existing = self.crud.read(
            table='games',
            filters={'game_id': game['game_id']}
        )

        if existing:
            # Game exists, check if update needed
            if existing['status'] != game['status'] or existing['home_score'] != game['home_score']:
                self.crud.update(
                    table='games',
                    filters={'game_id': game['game_id']},
                    data={**game, 'updated_at': datetime.utcnow()}
                )
                updated_count += 1
                self.logger.debug(
                    f"Updated game {game['game_id']}: {existing['status']} → {game['status']}",
                    extra={'game_id': game['game_id'], 'old_status': existing['status'], 'new_status': game['status']}
                )
            else:
                skipped_count += 1  # No changes
        else:
            # New game, insert
            self.crud.create(table='games', data=game)
            new_count += 1
            self.logger.debug(
                f"Inserted new game {game['game_id']}",
                extra={'game_id': game['game_id'], 'date': game['date']}
            )

    return {'new': new_count, 'updated': updated_count, 'skipped': skipped_count}
```

---

## 8. Scheduling & Automation

### Collection Schedule

**Phase 3+ Event Loop Integration:**

| Data Source | Frequency | Schedule | Rationale |
|-------------|-----------|----------|-----------|
| **ESPN NFL** | Daily | 2 AM EST | Games finish by midnight, collect overnight |
| **ESPN NBA** | Daily | 3 AM EST | Late games finish 1 AM, collect after |
| **Kalshi Markets** | Hourly | Every hour | Prices update frequently, hourly sufficient |
| **Balldontlie NBA** | Daily | 4 AM EST | Advanced stats available next morning |

### Event Loop Integration

```python
# src/precog/event_loop/data_collection_loop.py

async def daily_nfl_collection(collector: DataCollector):
    """
    Daily NFL game collection (runs at 2 AM EST).

    Educational Note:
        Runs at 2 AM to ensure all games finished:
        - Sunday games finish by midnight (last SNF game ~11:30 PM)
        - Monday Night Football finishes ~11:30 PM
        - Thursday Night Football finishes ~11:30 PM

        Collection fetches previous day's games using incremental update.
    """
    logger.info("Starting daily NFL collection")

    # Fetch yesterday's games (date range: yesterday to yesterday)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    result = collector.collect_nfl_games(
        start_date=yesterday,
        end_date=yesterday,
        incremental=True  # Only fetch new games
    )

    logger.info(
        f"NFL collection complete: {result['new_games']} new games, {result['updated_games']} updated",
        extra=result
    )

    return result

async def hourly_kalshi_collection(collector: DataCollector):
    """
    Hourly Kalshi market price collection.

    Educational Note:
        Hourly collection captures price movements for backtesting:
        - Market opens: prices start at ~0.50 (50% implied probability)
        - As game approaches: prices shift based on news, injuries, weather
        - Market closes: final price reflects consensus probability

        Hourly snapshots let us backtest: "If we traded 2 hours before kickoff,
        would our model have found better prices?"
    """
    logger.info("Starting hourly Kalshi price collection")

    result = collector.collect_kalshi_prices(
        market_type='nfl',
        incremental=True
    )

    logger.info(
        f"Kalshi collection complete: {result['markets_count']} markets, {result['prices_collected']} prices",
        extra=result
    )

    return result
```

---

## 9. Error Handling & Retry Logic

### Exponential Backoff

```python
import time
from functools import wraps

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for exponential backoff retry logic.

    Args:
        max_retries: Maximum retry attempts (default 3)
        base_delay: Base delay in seconds (default 1.0)

    Educational Note:
        Exponential Backoff Strategy:
        - Attempt 1: Immediate
        - Attempt 2: Wait 1 second
        - Attempt 3: Wait 2 seconds
        - Attempt 4: Wait 4 seconds

        Why exponential?
        - API temporary failure (rate limit, server busy) → Give server time to recover
        - Linear backoff (1s, 1s, 1s) → May hammer failing server
        - Exponential backoff (1s, 2s, 4s) → Polite, gives server breathing room

    Example:
        >>> @retry_with_backoff(max_retries=3, base_delay=1.0)
        ... def fetch_game_data(game_id: str):
        ...     response = requests.get(f"https://api.espn.com/game/{game_id}")
        ...     response.raise_for_status()
        ...     return response.json()
        >>>
        >>> # First attempt fails (HTTP 500) → Wait 1s → Retry
        >>> # Second attempt fails → Wait 2s → Retry
        >>> # Third attempt succeeds → Return data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        # Final attempt failed, re-raise exception
                        raise

                    # Calculate delay: 2^attempt * base_delay
                    # Attempt 0: 2^0 * 1.0 = 1.0s
                    # Attempt 1: 2^1 * 1.0 = 2.0s
                    # Attempt 2: 2^2 * 1.0 = 4.0s
                    delay = (2 ** attempt) * base_delay

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...",
                        extra={'attempt': attempt + 1, 'delay': delay, 'error': str(e)}
                    )

                    time.sleep(delay)

        return wrapper
    return decorator
```

---

## 10. Testing & Validation

### Unit Tests

**File:** `tests/unit/data/test_data_collector.py`

```python
"""
Unit tests for DataCollector.

Tests data collection logic in isolation using mocked API responses.
"""
from decimal import Decimal
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from precog.data.data_collector import DataCollector


class TestDataCollector:
    """Test DataCollector data collection and validation."""

    @patch('requests.get')
    def test_collect_nfl_games_success(self, mock_get, mock_crud):
        """
        Test successful NFL game collection.

        Scenario:
            - Fetch games for 2024-11-24 (1 game: BUF vs MIA)
            - Verify game parsed correctly
            - Verify game stored in database
        """
        # Mock ESPN API response
        mock_get.return_value.json.return_value = {
            'events': [{
                'id': '401671890',
                'date': '2024-11-24T18:00Z',
                'competitions': [{
                    'competitors': [
                        {'team': {'abbreviation': 'BUF'}, 'score': '31', 'homeAway': 'home'},
                        {'team': {'abbreviation': 'MIA'}, 'score': '24', 'homeAway': 'away'}
                    ],
                    'status': {'type': {'completed': True}}
                }]
            }]
        }
        mock_get.return_value.raise_for_status = Mock()

        collector = DataCollector(crud=mock_crud)

        result = collector.collect_nfl_games(
            start_date='2024-11-24',
            end_date='2024-11-24',
            incremental=False
        )

        # Verify collection summary
        assert result['games_count'] == 1
        assert result['new_games'] == 1
        assert result['validation_errors'] == 0

        # Verify game data stored
        assert mock_crud.create.called
        stored_game = mock_crud.create.call_args[1]['data']
        assert stored_game['game_id'] == '401671890'
        assert stored_game['home_team'] == 'BUF'
        assert stored_game['away_team'] == 'MIA'
        assert stored_game['home_score'] == 31
        assert stored_game['away_score'] == 24
        assert stored_game['status'] == 'final'
```

---

## 11. Data Source Tiering Strategy

**NEW IN V1.1** - Documents 3-tier data source architecture for strategy-appropriate cost optimization.

### Overview

Sports data sources vary dramatically in cost, latency, and reliability. This section documents the 3-tier architecture for selecting appropriate data sources based on strategy requirements.

### Three-Tier Architecture

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │               DATA SOURCE TIERING PYRAMID                    │
                    └─────────────────────────────────────────────────────────────┘

    Latency                                                                     Cost
    ───────►                                                                    ◄───────

      ▲                          ┌───────────────────┐
      │                          │   TIER 3: PAID    │                            ▲
   <1 min                        │  MySportsFeeds    │                         $909+/mo
      │                          │   Sportradar      │                            │
      │                          │   (Sub-second)    │                            │
      │                          └───────────────────┘
      │                      ┌───────────────────────────┐
      │                      │    TIER 2: DEV/TESTING    │
   UNKNOWN                   │   ESPN Hidden API (FREE)  │                       FREE
      │                      │    Balldontlie (FREE)     │                    (unreliable)
      │                      │   (Latency: TBD Phase 2)  │
      │                      └───────────────────────────┘
      │              ┌─────────────────────────────────────────┐
      │              │        TIER 1: HISTORICAL DATA          │
   Hours             │    sportsdataverse-py / nflreadpy       │                FREE
      │              │          (No latency req)               │             (reliable)
      ▼              └─────────────────────────────────────────┘

```

### Tier 1: Historical Data (FREE, Reliable)

**Data Sources:**
- **sportsdataverse-py**: Python wrapper for nflverse data (50+ years NFL stats)
- **nflreadpy**: Alternative Python package for nflverse
- **GitHub Releases**: Direct download from nflverse/nfldata

**Use Cases:**
- Model training (historical game outcomes, team stats)
- Backtesting strategies (historical win probabilities)
- Elo ratings bootstrap (pre-2024 games)

**Example (sportsdataverse-py):**
```python
import sportsdataverse.nfl as nfl

# Fetch NFL play-by-play data (FREE, ~10 sec/season)
pbp = nfl.load_nfl_pbp(seasons=[2023, 2024])

# Fetch team schedules with outcomes
schedules = nfl.load_nfl_schedule(seasons=[2024])

# Fetch weekly rosters for injury tracking
rosters = nfl.load_nfl_weekly_rosters(seasons=[2024])

# All data is FREE, reliable, comprehensive
# Latency: Hours (batch download, not real-time)
```

### Tier 2: Development/Testing (FREE, Unreliable)

**Data Sources:**
- **ESPN Hidden API**: Score updates (latency UNKNOWN - requires empirical measurement)
- **Balldontlie**: NBA/NFL/MLB/NHL (latency varies)

**CRITICAL: ESPN Latency is UNKNOWN**

Reports vary wildly on ESPN hidden API latency:
- Some users report ~194ms (near real-time)
- Others report "updates only occurring once daily" for some leagues
- Community consensus: "still slower than TV" but exact delay unclear

**Action Required (Phase 2):** Empirically measure ESPN delay by comparing API timestamps
to TV/official feed for a sample of games. This determines which strategies are viable.

**Use Cases:**
- Development environment testing
- Pre-game model features (hours before kickoff)
- **Lag-aware strategies** that tolerate 30-60+ second delays (quarter/half markets)
- **NOT for sub-second scalping** (use Tier 3 paid feeds)

**Example (ESPN Hidden API):**
```python
import requests
import time

# Fetch live NFL scoreboard
response = requests.get(
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)
games = response.json()['events']

# CRITICAL: Latency is UNKNOWN until empirically measured
# Reliability: Moderate (no SLA, may break without notice)
# Rate limit: Self-imposed 1 req/10-15 sec to avoid IP blocking
```

### Tier 3: Production (PAID, Reliable)

**Data Sources (Verified Pricing, November 2024):**

| Provider | Latency | Price/Month/League | Notes |
|----------|---------|-------------------|-------|
| **MySportsFeeds** | 10 min | $109 | Best budget option |
| **MySportsFeeds** | 5 min | $309 | Mid-tier latency |
| **MySportsFeeds** | 1 min | $909 | Low-latency production |
| **MySportsFeeds** | Near-RT | $1,599 | Enterprise grade |
| **Sportradar** | Sub-second | $1,000-5,000+ | Official NFL partner |
| **SportsDataIO** | Real-time | $600-2,000 | Enterprise pricing |
| **Balldontlie** | ~10 min | FREE | Free alternative |

**Use Cases:**
- Production live trading (Phase 5+)
- Live in-game strategies requiring <1 min latency
- Sub-second scalping strategies

### Strategy Latency Tolerance Matrix

**Key Insight:** For Kalshi-style prediction markets, a delay of **10-30 seconds is usually survivable**
for many edges. A delay of **several minutes is NOT acceptable** for live trading.

| Strategy Type | Latency Tolerance | Recommended Tier | Monthly Cost | Notes |
|--------------|-------------------|------------------|--------------|-------|
| **Pre-game (model features)** | Hours | Tier 1 | FREE | Elo, priors, team strength |
| **Pre-game (final line check)** | 30 min | Tier 2 | FREE | Check for line movement |
| **Live quarter/half props** | 30-60 sec | Tier 2 | FREE | Slow-moving markets |
| **Live structural edges** | 10-30 sec | Tier 2/3 | FREE-$109 | Stale lines after obvious events |
| **Live in-game (score-based)** | 5-10 sec | Tier 3 | $909+ | Fast-moving markets |
| **Live scalping (sub-second)** | <1 sec | Tier 3 ONLY | $1,599+ | NOT recommended for bootstrap |

### Lag-Aware Strategy Design (CRITICAL)

**Design Principle:** Instead of building for tick-by-tick, sub-second reactions, focus on
**edges that persist for MINUTES, not seconds:**

1. **Markets that update slowly after scoring drives** - Book may be slow to adjust
2. **Quarter/half markets** - Structural edges where the book is slow to move
3. **Mispriced futures/season-long markets** - Not time-sensitive
4. **Pre-game edges** - Hours of tolerance, no live data needed

**Strategy Metadata Pattern:**
```python
@dataclass
class StrategyConfig:
    """Each strategy explicitly declares its data requirements."""
    name: str
    max_tolerated_lag_seconds: int  # e.g., 60 for quarter props
    required_fields: list[str]      # e.g., ["score", "time_remaining"]
    min_confidence_threshold: float  # e.g., 0.8 for multi-source agreement

# Only enable strategies whose data requirements can be met
def can_enable_strategy(strategy: StrategyConfig, provider: GameStateProvider) -> bool:
    return provider.latency_seconds <= strategy.max_tolerated_lag_seconds
```

### Bootstrap-First Two-Stage Approach

**The Problem:** Premium feeds cost $100-$1,600+/month per league. Without proven ROI,
this expense cannot be justified.

**Stage 1: Bootstrap (FREE/Low-Cost)**
- Build and validate end-to-end system on historical data
- Use free or delayed "live" data (ESPN, Balldontlie)
- Paper trading and micro-sized positions
- Focus on lag-tolerant strategies (quarter props, slow markets)
- **Goal:** Prove the system works before paying for premium data

**Stage 2: Scale (After Proving Value)**
- Upgrade to pro feed ONLY after demonstrating profitability
- Premium feed bill comes AFTER de-risking the concept
- By then, you'll know exact latency requirements
- Can negotiate trial/discounted start with providers

**Cost Timeline:**
```
Phase 2-3: $0/month (Tier 1 + Tier 2 only, paper trading)
Phase 4:   $0/month (Live trading with micro positions, lag-tolerant strategies)
Phase 5+:  $109-909/month (Add Tier 3 ONLY when metrics justify ROI)
```

### Multi-Source Reconciliation (Confidence Scoring)

**Problem:** Single data source may be delayed, stale, or wrong.

**Solution:** Combine multiple free/hobby-tier feeds and reconcile discrepancies:

```python
@dataclass
class GameStateWithConfidence:
    """Game state with confidence score based on source agreement."""
    score_home: int
    score_away: int
    time_remaining: str
    quarter: int
    timestamp: datetime
    confidence: float  # 0.0 - 1.0
    sources_agreeing: int
    sources_total: int

class MultiSourceReconciler:
    """Reconcile game state from multiple data sources."""

    def __init__(self, providers: list[GameStateProvider]):
        self.providers = providers

    def get_reconciled_state(self, game_id: str) -> GameStateWithConfidence:
        states = [p.get_game_state(game_id) for p in self.providers]

        # Count agreement
        scores = [(s['home_score'], s['away_score']) for s in states]
        most_common_score = max(set(scores), key=scores.count)
        agreeing = scores.count(most_common_score)

        # Calculate confidence
        confidence = agreeing / len(states)

        return GameStateWithConfidence(
            score_home=most_common_score[0],
            score_away=most_common_score[1],
            confidence=confidence,
            sources_agreeing=agreeing,
            sources_total=len(states),
            # ... other fields
        )

# Risk layer uses confidence to gate trading
def should_trade(state: GameStateWithConfidence, strategy: StrategyConfig) -> bool:
    if state.confidence < strategy.min_confidence_threshold:
        return False  # Sources disagree - don't trade or be very conservative
    return True
```

**Confidence-Based Trading Rules:**
- **High confidence (>0.9):** Multiple sources agree, recent timestamps -> Trade normally
- **Medium confidence (0.7-0.9):** Some disagreement -> Trade conservative edges only
- **Low confidence (<0.7):** Sources disagree significantly -> DO NOT TRADE

### GameStateProvider Abstraction

**Pattern for Tier-Agnostic Code:**

```python
from typing import Protocol
from decimal import Decimal

class GameStateProvider(Protocol):
    """Abstract interface for game state data sources."""

    def get_current_score(self, game_id: str) -> dict:
        """Get current game score."""
        ...

    def get_game_clock(self, game_id: str) -> dict:
        """Get game clock (quarter, time remaining)."""
        ...

    @property
    def latency_seconds(self) -> int:
        """Expected latency in seconds (-1 if unknown)."""
        ...

    @property
    def source_confidence(self) -> float:
        """Source reliability confidence (0.0-1.0). Use for reconciliation weighting."""
        ...


class ESPNGameStateProvider:
    """Tier 2: ESPN Hidden API (FREE, latency UNKNOWN - requires empirical measurement)."""

    @property
    def latency_seconds(self) -> int:
        # UNKNOWN - requires Phase 2 empirical measurement
        # Reports range from ~194ms to "daily updates" depending on league
        return -1  # Unknown until measured

    @property
    def source_confidence(self) -> float:
        return 0.7  # Free tier, no SLA, may break without notice


class MySportsFeedsProvider:
    """Tier 3: MySportsFeeds (PAID, configurable latency, high reliability)."""

    def __init__(self, plan: str = "live_10min"):
        self._latency_map = {
            "live_10min": 600,    # $109/mo
            "live_5min": 300,     # $309/mo
            "live_1min": 60,      # $909/mo
            "near_realtime": 5,   # $1,599/mo
        }
        self.plan = plan

    @property
    def latency_seconds(self) -> int:
        return self._latency_map[self.plan]

    @property
    def source_confidence(self) -> float:
        return 0.95  # Paid tier with SLA, highly reliable


# Strategy selects provider based on latency tolerance
def create_game_provider(strategy_latency_tolerance: int, use_free_only: bool = True) -> GameStateProvider:
    """Factory method: Select provider based on strategy needs.

    Args:
        strategy_latency_tolerance: Max acceptable latency in seconds
        use_free_only: If True (bootstrap mode), always return ESPN regardless of tolerance

    Note:
        During bootstrap phase, always use free providers. The latency tolerance
        determines which STRATEGIES to enable, not which provider to use.
    """
    if use_free_only:
        # Bootstrap mode: Free provider only. Strategy layer decides if this
        # latency is acceptable for the strategy's requirements.
        return ESPNGameStateProvider()

    # Production mode: Select based on tolerance
    if strategy_latency_tolerance >= 60:
        return MySportsFeedsProvider("live_1min")  # $909/mo
    else:
        return MySportsFeedsProvider("near_realtime")  # $1,599/mo
```

### nflverse/sportsdataverse Integration

**Installation:**
```bash
pip install sportsdataverse nfl-data-py nflreadr
```

**Available Data (All FREE):**

| Dataset | Description | Update Frequency |
|---------|-------------|------------------|
| `load_nfl_pbp()` | Play-by-play (1999-present) | Daily during season |
| `load_nfl_schedule()` | Season schedules with outcomes | Weekly |
| `load_nfl_weekly_rosters()` | Weekly active rosters | Weekly |
| `load_nfl_player_stats()` | Individual player stats | Post-game |
| `load_nfl_team_stats()` | Team-level statistics | Post-game |
| `load_nfl_combine()` | NFL Combine results | Annual |
| `load_nfl_draft()` | Draft picks (1936-present) | Annual |

**Example: Model Training Pipeline:**
```python
import sportsdataverse.nfl as nfl
import pandas as pd

# Collect 5 years of data for model training (FREE)
pbp_data = nfl.load_nfl_pbp(seasons=list(range(2019, 2024)))

# Filter to regular season games
regular_season = pbp_data[pbp_data['season_type'] == 'REG']

# Calculate features for Elo model
team_stats = regular_season.groupby(['game_id', 'home_team']).agg({
    'yards_gained': 'sum',
    'score_differential': 'last',
    'epa': 'sum'  # Expected Points Added
}).reset_index()

# This is ~50,000 games of data, completely FREE
print(f"Collected {len(team_stats)} game records for model training")
```

---

`★ Insight ─────────────────────────────────────`
**Data Collection: Foundation of Accurate Predictions**

1. **Incremental Updates Save Time:** Fetching ALL historical data daily is wasteful (60s collection time). Tracking last collection timestamp reduces this to 5s (only fetch new games).

2. **Schema Validation Prevents Garbage In, Garbage Out:** Missing fields or wrong types corrupt model training. Strict validation ensures only clean, complete data enters the database.

3. **Tiered Data Sources Optimize Cost/Latency:** Start with FREE sources (Tier 1-2) for development and pre-game strategies. Only pay for Tier 3 when live trading ROI justifies $109-1,599/month per league.

4. **Bootstrap-First Approach:** Measure empirical latency requirements before committing to expensive APIs. Many strategies work fine with 5-10 minute delay (FREE).
`─────────────────────────────────────────────────`

---

## Appendix A: API Pricing Reference (November 2024)

| Provider | Tier | Latency | Price/Month | Leagues |
|----------|------|---------|-------------|---------|
| **sportsdataverse** | 1 | Hours | FREE | NFL, NBA, NCAAF, NCAAB |
| **nflreadpy** | 1 | Hours | FREE | NFL only |
| **ESPN Hidden API** | 2 | 5-15 min | FREE | All major sports |
| **Balldontlie** | 2/3 | ~10 min | FREE | NBA, NFL, MLB, NHL |
| **MySportsFeeds (10min)** | 3 | 10 min | $109 | Per league |
| **MySportsFeeds (5min)** | 3 | 5 min | $309 | Per league |
| **MySportsFeeds (1min)** | 3 | 1 min | $909 | Per league |
| **MySportsFeeds (RT)** | 3 | Near-RT | $1,599 | Per league |
| **Sportradar** | 3 | Sub-sec | $1,000-5,000+ | Enterprise |
| **SportsDataIO** | 3 | Real-time | $600-2,000 | Enterprise |
| **The Odds API** | 2 | Real-time | $25+ | Odds only |

**Note:** Prices verified November 2024. Check provider websites for current pricing.

---

**END OF DATA_COLLECTION_GUIDE V1.1**
