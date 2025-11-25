# Data Collection Guide

---

**Version:** 1.0
**Created:** 2025-11-24
**Status:** 🔵 Planned (Phase 3+)
**Target Audience:** Developers implementing automated data collection pipelines for model training
**Prerequisites:** API_INTEGRATION_GUIDE_V2.0.md, MODEL_TRAINING_GUIDE_V1.0.md
**Related Documents:**
- `docs/guides/MODEL_MANAGER_USER_GUIDE_V1.1.md` (Future Enhancements - Data Collection Pipelines)
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md` (ESPN, Kalshi, Balldontlie APIs)
- `docs/foundation/MASTER_REQUIREMENTS_V2.18.md` (REQ-DATA-001 through REQ-DATA-006)
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.32.md` (ADR-002: Decimal Precision, ADR-053: Data Validation)

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

**Rate Limit:** Unlimited (public API)

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
- 1000+ games per season × 4 sports = 4000+ API calls
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

`★ Insight ─────────────────────────────────────`
**Data Collection: Foundation of Accurate Predictions**

1. **Incremental Updates Save Time:** Fetching ALL historical data daily is wasteful (60s collection time). Tracking last collection timestamp reduces this to 5s (only fetch new games).

2. **Schema Validation Prevents Garbage In, Garbage Out:** Missing fields or wrong types corrupt model training. Strict validation ensures only clean, complete data enters the database.

3. **Automated Scheduling Ensures Freshness:** Models trained on stale data make poor predictions. Daily/hourly collection via event loop keeps data fresh without manual intervention.
`─────────────────────────────────────────────────`

Perfect! All 5 guides/specs are now created. Let me update the todo list and then update MASTER_INDEX V2.33 → V2.34.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[
  {"content": "Create STRATEGY_EVALUATION_SPEC_V1.0.md (~400 lines)", "status": "completed", "activeForm": "Creating STRATEGY_EVALUATION_SPEC_V1.0.md"},
  {"content": "Create AB_TESTING_FRAMEWORK_SPEC_V1.0.md (~350 lines)", "status": "completed", "activeForm": "Creating AB_TESTING_FRAMEWORK_SPEC_V1.0.md"},
  {"content": "Create MODEL_TRAINING_GUIDE_V1.0.md (~500 lines)", "status": "completed", "activeForm": "Creating MODEL_TRAINING_GUIDE_V1.0.md"},
  {"content": "Create EDGE_CALCULATION_GUIDE_V1.0.md (~400 lines)", "status": "completed", "activeForm": "Creating EDGE_CALCULATION_GUIDE_V1.0.md"},
  {"content": "Create DATA_COLLECTION_GUIDE_V1.0.md (~450 lines)", "status": "completed", "activeForm": "Creating DATA_COLLECTION_GUIDE_V1.0.md"},
  {"content": "Update MASTER_INDEX V2.33 → V2.34 with 5 new specs", "status": "in_progress", "activeForm": "Updating MASTER_INDEX"}
]
