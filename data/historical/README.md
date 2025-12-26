# Historical Data Cache

This directory contains cached historical data for reproducibility, backtesting, and production migration.

## Directory Structure

```
data/historical/
├── README.md                    # This file
├── nfl_elo.csv                  # FiveThirtyEight NFL Elo (1920-2020) ✅ VALID
├── nba_elo.csv                  # FiveThirtyEight NBA Elo (historic) ✅ VALID
├── nfl_betting.csv              # NFL betting historical data
├── espn/                        # ESPN API cache
│   ├── nfl/                     # NFL game data by date
│   │   └── 2024-12-25.json
│   ├── nba/
│   ├── mlb/
│   └── nhl/
├── kalshi/                      # Kalshi API cache
│   ├── markets/                 # Market snapshots by date
│   │   └── 2024-12-25.json
│   ├── series/                  # Series definitions by date
│   │   └── 2024-12-25.json
│   └── positions/               # Position snapshots by date
│       └── 2024-12-25.json
└── python_libs/                 # Python library cache docs (data stored externally)
    └── README.md                # Cache location documentation
```

## Data Sources

### 1. FiveThirtyEight Elo (CSV Files)

**⚠️ DATA AVAILABILITY NOTICE (December 2025):**
FiveThirtyEight shut down after Disney's acquisition and merged with ABC News.
- All API endpoints (`projects.fivethirtyeight.com/*`) redirect to ABC News
- GitHub repository (fivethirtyeight/data) removed all CSV files, only READMEs remain
- Data is no longer available from official sources

**Available Files:**
- ✅ `nfl_elo.csv` - FiveThirtyEight NFL Elo 1920-2020 (~16,810 games) - VALID
- ✅ `nba_elo.csv` - FiveThirtyEight NBA Elo historic seasons - VALID
- ✅ `nhl_elo.csv` - Neil Paine NHL Elo 1917-2025 (~137,678 games) - VALID ⭐ NEW
- ⚠️ MLB Elo - No pre-computed source available (compute from game results)

**Format:** CSV with Elo ratings, game scores, probabilities

**NHL Elo Source (Added December 2025):**
Downloaded from [Neil Paine's NHL-Player-And-Team-Ratings](https://github.com/Neil-Paine-1/NHL-Player-And-Team-Ratings)
- 137,678 games from 1917-2025
- Format: game_ID, season, date, team1/team2, elo1_pre/post, score1/score2, prob1/prob2, is_home

**MLB Strategy:**
Since no reliable pre-computed MLB Elo source exists, use:
1. **Seed historical games** from ESPN API or pybaseball library
2. **Compute Elo** using `EloEngine` with MLB-specific parameters
3. **Store results** in `elo_calculation_log` for full audit trail

This approach provides:
- Full traceability (every calculation audited)
- Customizable parameters (K-factor, home advantage)
- Consistency with NFL/NBA/NHL computation pipeline

**MLB Elo Pipeline (Added December 2025):**
```python
from precog.database.seeding.historical_games_loader import load_pybaseball_games

# Step 1: Load MLB games into historical_games table
result = load_pybaseball_games(seasons=[2023, 2024])
print(f"Loaded {result.inserted} games, skipped {result.skipped}")

# Step 2: Compute Elo ratings
from precog.analytics import EloComputationService, compute_elo_ratings
result = compute_elo_ratings(sport="mlb", seasons=[2023, 2024])
```

📚 **Complete Guide:** See `docs/guides/ELO_COMPUTATION_GUIDE_V1.2.md` for full documentation

**Legacy Download Commands (NO LONGER WORK):**
```bash
# These URLs now redirect to ABC News - DO NOT USE
# curl -L "https://projects.fivethirtyeight.com/nfl-api/nfl_elo.csv"
# curl -L "https://projects.fivethirtyeight.com/mlb-api/mlb_elo.csv"
# curl -L "https://projects.fivethirtyeight.com/nhl-api/nhl_elo.csv"
```

**Usage:**
```python
from precog.database.seeding.historical_elo_loader import load_fivethirtyeight_elo
result = load_fivethirtyeight_elo(Path("data/historical/nfl_elo.csv"), seasons=[2019, 2020])
```

### 2. ESPN Historical API (JSON Cache)

**Location:** `data/historical/espn/{sport}/{YYYY-MM-DD}.json`
**Format:** JSON with game details, scores, teams
**Rate Limit:** 500 requests/hour

**Usage:**
```python
from precog.database.seeding.historical_games_loader import fetch_and_cache_games
games = fetch_and_cache_games("nfl", date(2024, 12, 25))
```

**CLI Commands:**
```bash
# Seed games from ESPN
python main.py data seed-espn --sport nfl --start 2024-09-01 --end 2024-12-25

# Check cache statistics
python main.py data cache-stats --sport nfl
```

### 3. Kalshi API (JSON Cache)

**Location:** `data/historical/kalshi/{type}/{YYYY-MM-DD}.json`
**Format:** JSON with Decimal prices stored as strings for precision
**Types:** markets, series, positions, orders

**Usage:**
```python
from precog.database.seeding.kalshi_historical_cache import fetch_and_cache_markets
markets = fetch_and_cache_markets(client, date.today())
```

**CLI Commands:**
```bash
# Cache all Kalshi data
python main.py data cache-kalshi --type all

# Cache specific data type
python main.py data cache-kalshi --type markets --category sports

# Check cache statistics
python main.py data kalshi-cache-stats
```

### 4. Python Sports Libraries

These libraries manage their own caches externally. See `python_libs/README.md` for details.

| Library | Cache Location | Data Coverage |
|---------|----------------|---------------|
| `pybaseball` | `~/.pybaseball/cache` | MLB stats since 2008 |
| `nfl_data_py` | Auto-managed | NFL play-by-play since 1999 |
| `nba_api` | `~/.nba_api/` | NBA stats since 1946 |
| `nflreadpy` | Auto-managed | NFL advanced stats |

**CLI Commands:**
```bash
# Seed from Python library
python main.py data seed-lib --source pybaseball --seasons 2023,2024

# Available sources: nfl_data_py, nflreadpy, nba_api, pybaseball
```

## Cache JSON Format

### ESPN Cache Structure
```json
{
  "cached_at": "2024-12-25T10:30:00",
  "sport": "nfl",
  "game_date": "2024-12-25",
  "source": "espn_scoreboard_api",
  "count": 3,
  "data": [
    {
      "game_id": "401547123",
      "home_team": "KC",
      "away_team": "LVR",
      "home_score": 31,
      "away_score": 17,
      "status": "final"
    }
  ]
}
```

### Kalshi Cache Structure
```json
{
  "cached_at": "2024-12-25T10:30:00",
  "cache_date": "2024-12-25",
  "cache_type": "markets",
  "source": "kalshi_api",
  "count": 150,
  "data": [
    {
      "ticker": "NFLSF-25DEC25-KC",
      "title": "Chiefs vs Raiders",
      "yes_bid": "0.4975",
      "yes_ask": "0.5025"
    }
  ]
}
```

Note: Kalshi prices are stored as **strings** (e.g., `"0.4975"`) to preserve
Decimal precision. Use `Decimal(value)` when loading.

## TimescaleDB Migration

This cache structure supports migration to production TimescaleDB:

1. **Reproducibility:** Load cached data without API calls
2. **Backtesting:** Replay historical market states
3. **Production Migration:** Export to cloud TimescaleDB using:
   ```python
   from precog.database.seeding.kalshi_historical_cache import load_from_cache
   from precog.database.crud_operations import insert_markets

   # Load from cache, insert to production DB
   markets = load_from_cache("markets", date(2024, 12, 25))
   insert_markets(production_session, markets)
   ```

## Database Views for Historical Data

The following database views derive analytics from historical data:

### team_season_records (Migration 0014)
Aggregates win/loss/draw records from `historical_games` table.

```sql
-- Query team season records
SELECT sport, season, team_code, wins, losses, draws, win_pct, record_display
FROM team_season_records
WHERE sport = 'nfl' AND season = 2024
ORDER BY win_pct DESC;

-- Query current season standings with team info
SELECT team_name, conference, division, wins, losses, win_pct, current_elo_rating
FROM current_season_standings
WHERE sport = 'nfl'
ORDER BY win_pct DESC;
```

**Benefits:**
- No data duplication (derived from historical_games)
- Automatically updated when games are inserted
- Supports historical AND current season records

## License

- **FiveThirtyEight:** Creative Commons Attribution 4.0
- **ESPN:** Personal/research use only
- **Kalshi:** Subject to API terms of service
- **Python Libraries:** Various open source licenses
