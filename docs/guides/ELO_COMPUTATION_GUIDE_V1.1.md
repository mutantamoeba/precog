# Elo Computation Guide

---
**Version:** 1.1
**Created:** 2025-12-24
**Last Updated:** 2025-12-24
**Status:** Active
**Phase:** 2.6 (Elo Rating Computation)
**Related ADRs:** ADR-109 (Elo Rating Computation Engine)
**Related Requirements:** REQ-ELO-001 through REQ-ELO-007
**Related Documents:**
- `docs/supplementary/DATA_SOURCES_SPECIFICATION_V1.0.md` - Data source details
- `docs/guides/DATA_COLLECTION_GUIDE_V1.2.md` - Historical data collection
- `docs/guides/MODEL_TRAINING_GUIDE_V1.0.md` - Model training with Elo features
- `docs/guides/EDGE_CALCULATION_GUIDE_V1.0.md` - Using Elo for edge calculation
**Changes in v1.1:**
- **SCHEMA CLARIFICATION**: Updated to use EXISTING `historical_elo` table with `source='calculated'` (not new table)
- **NEW TABLE**: Added `historical_epa` table schema for NFL EPA metrics (separate from Elo)
- **NEW TABLE**: Added `elo_calculation_log` audit table for debugging and provenance
- **PHASE CORRECTED**: Fixed phase reference from "3" to "2.6"
---

## Overview

This guide documents the Elo rating computation system for the Precog prediction market platform. It covers:

1. **Elo Algorithm Fundamentals** - The mathematical basis for Elo ratings
2. **Sport-Specific Configuration** - K-factors and parameters per sport
3. **EPA Integration** - Expected Points Added for NFL enhancement
4. **Data Sources** - Where to get game results for each sport
5. **Historical Bootstrapping** - Computing Elo from historical games
6. **Real-Time Updates** - Live Elo updates as games complete
7. **Database Storage** - Storing and querying Elo ratings
8. **Pollers & Schedulers** - Automated Elo update infrastructure
9. **CLI Commands** - Command-line interface for Elo operations
10. **TUI Support** - Terminal UI for monitoring and management

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ELO COMPUTATION ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │  nflreadpy  │    │   nba_api   │    │ nhl-api-py  │    │  pybaseball │   │
│  │    (NFL)    │    │  (NBA/WNBA) │    │    (NHL)    │    │    (MLB)    │   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘   │
│         │                  │                  │                  │          │
│         └──────────────────┴────────┬─────────┴──────────────────┘          │
│                                     │                                        │
│                          ┌──────────▼──────────┐                            │
│                          │   Data Adapters      │                            │
│                          │  (Sport-Specific)    │                            │
│                          └──────────┬──────────┘                            │
│                                     │                                        │
│         ┌───────────────────────────┼───────────────────────────┐           │
│         │                           │                           │           │
│         ▼                           ▼                           ▼           │
│  ┌─────────────┐          ┌─────────────────┐          ┌─────────────┐      │
│  │  Historical │          │   EloEngine     │          │  Real-Time  │      │
│  │ Bootstrapper│          │ (Core Compute)  │          │   Updater   │      │
│  └──────┬──────┘          └────────┬────────┘          └──────┬──────┘      │
│         │                          │                          │             │
│         └──────────────────────────┼──────────────────────────┘             │
│                                    │                                         │
│                          ┌─────────▼─────────┐                              │
│                          │    PostgreSQL      │                              │
│                          │  team_elo_ratings  │                              │
│                          └─────────┬─────────┘                              │
│                                    │                                         │
│         ┌──────────────────────────┼──────────────────────────┐             │
│         │                          │                          │             │
│         ▼                          ▼                          ▼             │
│  ┌─────────────┐          ┌─────────────────┐          ┌─────────────┐      │
│  │ EloPoller   │          │   CLI Commands  │          │    TUI      │      │
│  │ (Scheduler) │          │   (main.py)     │          │  (Textual)  │      │
│  └─────────────┘          └─────────────────┘          └─────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Compute Elo Ourselves?

**FiveThirtyEight shut down in March 2025**, ending the free availability of pre-computed Elo ratings. We must now compute Elo ratings from game results for all sports.

**Benefits of self-computed Elo:**
- Full control over methodology and parameters
- Real-time updates as games complete
- Custom K-factors optimized for our use case
- Integration with proprietary features (EPA, home-field adjustments)

---

## 1. Elo Algorithm Fundamentals

### The Elo Formula

The Elo rating system, originally designed for chess by Arpad Elo, calculates the relative skill of competitors based on game outcomes.

**Expected Score Formula:**
```
E = 1 / (1 + 10^((R_opponent - R_self) / 400))
```

Where:
- `E` = Expected score (probability of winning)
- `R_self` = Team's current Elo rating
- `R_opponent` = Opponent's current Elo rating

**Rating Update Formula:**
```
R_new = R_old + K × (S - E)
```

Where:
- `R_new` = Updated Elo rating
- `R_old` = Current Elo rating
- `K` = K-factor (sensitivity to results)
- `S` = Actual score (1 = win, 0.5 = tie, 0 = loss)
- `E` = Expected score (from formula above)

### Example Calculation

Team A (Elo 1600) vs Team B (Elo 1400):

1. **Expected Score for Team A:**
   ```
   E_A = 1 / (1 + 10^((1400 - 1600) / 400))
       = 1 / (1 + 10^(-0.5))
       = 1 / (1 + 0.316)
       = 0.76
   ```
   Team A is expected to win 76% of the time.

2. **If Team A wins (K=20):**
   ```
   R_A_new = 1600 + 20 × (1.0 - 0.76) = 1600 + 4.8 = 1604.8
   R_B_new = 1400 + 20 × (0.0 - 0.24) = 1400 - 4.8 = 1395.2
   ```

3. **If Team B upsets (K=20):**
   ```
   R_A_new = 1600 + 20 × (0.0 - 0.76) = 1600 - 15.2 = 1584.8
   R_B_new = 1400 + 20 × (1.0 - 0.24) = 1400 + 15.2 = 1415.2
   ```

### Key Properties

- **Zero-sum:** Points gained by winner = points lost by loser
- **Initial rating:** 1500 (league average)
- **Upset sensitivity:** Larger updates for unexpected outcomes
- **Convergence:** Ratings stabilize after sufficient games

---

## 2. Sport-Specific Configuration

### K-Factor Selection

The K-factor determines how quickly ratings respond to game results. Higher K means more volatile ratings.

| Sport | K-Factor | Season Games | Rationale |
|-------|----------|--------------|-----------|
| NFL | 20 | 17 | Short season, high variance per game |
| NCAAF | 20 | 12-15 | Short season, high variance |
| NBA | 20 | 82 | Long season but moderate variance |
| NCAAB | 20 | 30-40 | Moderate season length |
| NHL | 6 | 82 | Long season, low scoring variance |
| MLB | 4 | 162 | Very long season, individual game variance is low |

### Home-Field Advantage

Home-field advantage varies by sport. This is added to the home team's Elo before calculating expected score:

| Sport | Home Advantage (Elo points) | Win % Boost |
|-------|----------------------------|-------------|
| NFL | 48 | +3.4% |
| NCAAF | 55 | +3.9% |
| NBA | 100 | +7.0% |
| NCAAB | 100 | +7.0% |
| NHL | 33 | +2.3% |
| MLB | 24 | +1.7% |

### Season Carryover

At season start, ratings regress toward the mean to account for roster changes:

```python
R_new_season = (R_previous × 0.75) + (1505 × 0.25)
```

This pulls teams toward 1505 (slightly above neutral) to account for league-wide improvement over time.

---

## 3. EPA Integration (NFL Only)

### What is EPA?

**EPA (Expected Points Added)** measures how much a play improves a team's expected points. It's the most predictive publicly available NFL metric.

### Data Source

EPA is available **FREE** in nflreadpy's `load_pbp()` function:

```python
import nflreadpy

# Load play-by-play data with EPA columns
pbp_2024 = nflreadpy.load_pbp(2024)

# Available EPA columns (372 total in play-by-play)
epa_columns = [
    'epa',              # Expected Points Added per play
    'qb_epa',           # QB-specific EPA
    'total_home_epa',   # Cumulative home team EPA
    'total_away_epa',   # Cumulative away team EPA
    'air_epa',          # EPA from air yards
    'yac_epa',          # EPA from yards after catch
    'comp_air_epa',     # Completion air EPA
    'comp_yac_epa',     # Completion YAC EPA
    'total_home_rush_epa',  # Home rush EPA
    'total_away_rush_epa',  # Away rush EPA
    'total_home_pass_epa',  # Home pass EPA
    'total_away_pass_epa',  # Away pass EPA
]
```

### EPA-Weighted Elo Adjustment

EPA can enhance Elo predictions by incorporating offensive/defensive efficiency:

```python
def get_epa_adjustment(team_off_epa: float, team_def_epa: float) -> Decimal:
    """Calculate Elo adjustment based on EPA differential.

    Args:
        team_off_epa: Team's offensive EPA per play (season average)
        team_def_epa: Team's defensive EPA per play (season average)

    Returns:
        Elo adjustment in points (-50 to +50 range)
    """
    # EPA differential: positive = good offense + good defense
    epa_diff = team_off_epa - team_def_epa  # Defense EPA is opponent EPA

    # Scale to Elo points (roughly 10 Elo per 0.1 EPA differential)
    adjustment = Decimal(str(epa_diff * 100)).quantize(Decimal("0.01"))

    # Cap at +/- 50 Elo points
    return max(Decimal("-50"), min(Decimal("50"), adjustment))
```

### DVOA Unavailability

**DVOA (Defense-adjusted Value Over Average)** is a proprietary metric from Football Outsiders/FTN.

- **Status:** NOT available for free computation
- **Cost:** FTN subscription required ($99+/month)
- **Alternative:** Use EPA-based metrics (free and highly predictive)

---

## 4. Data Sources by Sport

### NFL - nflreadpy

```python
import nflreadpy

# Game schedules and results (1999-present)
schedules = nflreadpy.load_schedules([2023, 2024])

# Play-by-play with EPA (1999-present)
pbp = nflreadpy.load_pbp(2024)

# Team rosters
rosters = nflreadpy.load_rosters(2024)

# Required columns for Elo computation
game_columns = [
    'game_id', 'season', 'week', 'game_type',
    'home_team', 'away_team',
    'home_score', 'away_score',
    'gameday'
]
```

**Note:** `nfl_data_py` was archived September 2025. Use `nflreadpy` instead.

### NBA - nba_api

```python
from nba_api.stats.endpoints import LeagueGameFinder
from nba_api.stats.static import teams

# Get all NBA teams
nba_teams = teams.get_teams()

# Get game results (1946-present)
game_finder = LeagueGameFinder(
    league_id_nullable='00',  # NBA
    season_type_nullable='Regular Season'
)
games = game_finder.get_data_frames()[0]

# Required columns
game_columns = [
    'GAME_ID', 'GAME_DATE', 'MATCHUP',
    'WL', 'PTS', 'TEAM_ID'
]
```

### NHL - nhl-api-py

```python
from nhl_api_py import NHLClient

client = NHLClient()

# Get schedule (1917-present)
schedule = client.schedule.get_schedule(date='2024-01-15')

# Get game details
game = client.game_center.boxscore(game_id=2024020001)

# Get standings
standings = client.standings.get_standings()

# EDGE stats (advanced tracking)
edge_stats = client.stats.get_player_stats(player_id=8478402)
```

### MLB - pybaseball

```python
from pybaseball import schedule_and_record, standings

# Get team schedule with results (1871-present)
schedule = schedule_and_record(2024, 'NYY')  # Yankees

# Get league standings
nl_standings = standings(2024, 'NL')
al_standings = standings(2024, 'AL')

# Required columns
game_columns = [
    'Date', 'Tm', 'Opp', 'R', 'RA', 'W/L', 'Home_Away'
]
```

### NCAAF - cfbd

```python
import cfbd
from cfbd.rest import ApiException

configuration = cfbd.Configuration()
configuration.api_key['Authorization'] = 'your_api_key'

api_instance = cfbd.GamesApi(cfbd.ApiClient(configuration))

# Get games (2000-present)
games = api_instance.get_games(year=2024, season_type='regular')

# Required fields
game_fields = [
    'id', 'season', 'week', 'season_type',
    'home_team', 'away_team',
    'home_points', 'away_points',
    'start_date'
]
```

### NCAAB - sportsdataverse

```python
from sportsdataverse.mbb import load_mbb_schedule

# Get schedule with scores (2002-present)
schedule_2024 = load_mbb_schedule(seasons=2024)

# Required columns
game_columns = [
    'game_id', 'game_date',
    'home_display_name', 'away_display_name',
    'home_score', 'away_score',
    'status_type_name'  # Filter for completed games
]
```

---

## 5. Historical Bootstrapping

### Process Overview

To initialize Elo ratings, we process all historical games chronologically:

```python
from decimal import Decimal
from datetime import date
from typing import Dict
from dataclasses import dataclass

@dataclass
class EloState:
    """Current Elo state for a team."""
    rating: Decimal
    last_updated: date
    games_played: int

def bootstrap_elo(
    games: list[dict],
    sport: str,
    initial_rating: Decimal = Decimal("1500"),
    k_factor: int = 20
) -> Dict[str, EloState]:
    """Bootstrap Elo ratings from historical games.

    Args:
        games: List of games sorted by date (oldest first)
        sport: Sport type for K-factor lookup
        initial_rating: Starting rating for new teams
        k_factor: K-factor for this sport

    Returns:
        Dictionary of team -> EloState
    """
    ratings: Dict[str, EloState] = {}

    for game in games:
        home_team = game['home_team']
        away_team = game['away_team']
        home_score = game['home_score']
        away_score = game['away_score']
        game_date = game['date']

        # Initialize teams if needed
        for team in [home_team, away_team]:
            if team not in ratings:
                ratings[team] = EloState(
                    rating=initial_rating,
                    last_updated=game_date,
                    games_played=0
                )

        # Get current ratings
        home_elo = ratings[home_team].rating
        away_elo = ratings[away_team].rating

        # Add home-field advantage
        home_advantage = get_home_advantage(sport)
        adjusted_home = home_elo + home_advantage

        # Calculate expected scores
        home_expected = calculate_expected(adjusted_home, away_elo)
        away_expected = Decimal("1") - home_expected

        # Determine actual scores
        if home_score > away_score:
            home_actual, away_actual = Decimal("1"), Decimal("0")
        elif away_score > home_score:
            home_actual, away_actual = Decimal("0"), Decimal("1")
        else:
            home_actual, away_actual = Decimal("0.5"), Decimal("0.5")

        # Update ratings
        ratings[home_team] = EloState(
            rating=home_elo + Decimal(k_factor) * (home_actual - home_expected),
            last_updated=game_date,
            games_played=ratings[home_team].games_played + 1
        )
        ratings[away_team] = EloState(
            rating=away_elo + Decimal(k_factor) * (away_actual - away_expected),
            last_updated=game_date,
            games_played=ratings[away_team].games_played + 1
        )

    return ratings
```

### Handling Season Transitions

```python
def apply_season_carryover(
    ratings: Dict[str, EloState],
    new_season_start: date,
    carryover_weight: Decimal = Decimal("0.75"),
    mean_regression_target: Decimal = Decimal("1505")
) -> Dict[str, EloState]:
    """Apply season carryover regression."""
    updated = {}

    for team, state in ratings.items():
        new_rating = (
            state.rating * carryover_weight +
            mean_regression_target * (Decimal("1") - carryover_weight)
        )
        updated[team] = EloState(
            rating=new_rating,
            last_updated=new_season_start,
            games_played=0  # Reset for new season
        )

    return updated
```

### Progress Tracking and Checkpointing

For large historical datasets (~100K+ games), implement checkpointing:

```python
import json
from pathlib import Path

def save_checkpoint(ratings: Dict[str, EloState], path: Path):
    """Save current state for resumable processing."""
    data = {
        team: {
            'rating': str(state.rating),
            'last_updated': state.last_updated.isoformat(),
            'games_played': state.games_played
        }
        for team, state in ratings.items()
    }
    path.write_text(json.dumps(data, indent=2))

def load_checkpoint(path: Path) -> Dict[str, EloState]:
    """Load checkpoint for resume."""
    data = json.loads(path.read_text())
    return {
        team: EloState(
            rating=Decimal(state['rating']),
            last_updated=date.fromisoformat(state['last_updated']),
            games_played=state['games_played']
        )
        for team, state in data.items()
    }
```

---

## 6. Real-Time Updates

### Integration with Live Data Pipeline

The Elo system integrates with the live data collection pipeline (see LIVE_DATA_INTEGRATION_GUIDE_V1.1.md):

```python
from precog.database.models import GameState
from precog.analytics.elo_engine import EloEngine

class EloUpdateListener:
    """Listens for game completions and updates Elo ratings."""

    def __init__(self, engine: EloEngine):
        self.engine = engine

    def on_game_completed(self, game: GameState):
        """Called when a game reaches 'final' status."""
        if game.status != 'final':
            return

        # Get current Elo ratings
        home_elo = self.get_team_elo(game.home_team_id)
        away_elo = self.get_team_elo(game.away_team_id)

        # Calculate new ratings
        new_home, new_away = self.engine.update_ratings(
            home_elo=home_elo,
            away_elo=away_elo,
            home_score=game.home_score,
            away_score=game.away_score,
            sport=game.league
        )

        # Store updated ratings
        self.save_elo_update(
            team_id=game.home_team_id,
            new_rating=new_home,
            previous_rating=home_elo,
            game_id=game.id,
            effective_date=game.game_date
        )
        self.save_elo_update(
            team_id=game.away_team_id,
            new_rating=new_away,
            previous_rating=away_elo,
            game_id=game.id,
            effective_date=game.game_date
        )
```

### Performance Requirements

- **Update latency:** < 100ms per game
- **Concurrent updates:** Support multiple simultaneous games
- **Database writes:** Batch inserts for efficiency

---

## 7. Database Storage

### Schema Strategy: Use Existing Tables

**IMPORTANT:** We use the **EXISTING** `historical_elo` table (Migration 0005) rather than creating a new `team_elo_ratings` table. This avoids redundancy and leverages the established historical data infrastructure.

**Key insight:** The `historical_elo` table already has a `source` column that distinguishes data origin:
- `source='fivethirtyeight'` - Historical data from FiveThirtyEight (before March 2025 shutdown)
- `source='calculated'` - Elo ratings computed by our engine

### Using Existing `historical_elo` Table

```sql
-- EXISTING table from Migration 0005 (DO NOT CREATE - already exists)
-- We INSERT with source='calculated' for our computed Elo ratings

-- Example: Insert calculated Elo rating
INSERT INTO historical_elo (
    team_id, sport, rating_date, elo_rating, qb_adjusted_elo,
    season, source, created_at
) VALUES (
    123,                    -- team_id (FK to teams)
    'nfl',                  -- sport
    '2024-12-22',           -- rating_date (effective date)
    1687.50,                -- elo_rating
    1702.25,                -- qb_adjusted_elo (NFL only, NULL for other sports)
    2024,                   -- season
    'calculated',           -- source = 'calculated' distinguishes from imported data
    NOW()                   -- created_at
);
```

### NEW: `historical_epa` Table (Migration 0013)

EPA (Expected Points Added) is stored **separately** from Elo because:
1. EPA is NFL-specific (other sports don't have EPA)
2. EPA has different granularity (offensive/defensive/passing/rushing breakdown)
3. Keeps `historical_elo` simple and multi-sport compatible

```sql
CREATE TABLE historical_epa (
    historical_epa_id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    sport VARCHAR(20) NOT NULL DEFAULT 'nfl',
    season INTEGER NOT NULL,
    week INTEGER,  -- NULL for season-level aggregates

    -- Offensive EPA metrics
    off_epa_per_play DECIMAL(8,4),       -- Overall offensive EPA per play
    pass_epa_per_play DECIMAL(8,4),      -- Passing EPA per play
    rush_epa_per_play DECIMAL(8,4),      -- Rushing EPA per play

    -- Defensive EPA metrics (opponent EPA allowed)
    def_epa_per_play DECIMAL(8,4),       -- Defensive EPA per play (lower = better)
    def_pass_epa_per_play DECIMAL(8,4),  -- Pass defense EPA per play
    def_rush_epa_per_play DECIMAL(8,4),  -- Rush defense EPA per play

    -- Calculated adjustments
    epa_differential DECIMAL(8,4),       -- off_epa - def_epa (overall efficiency)
    elo_adjustment DECIMAL(8,2),         -- EPA-derived Elo adjustment (-50 to +50)

    -- Data provenance
    source VARCHAR(100) NOT NULL DEFAULT 'nflreadpy',
    source_file VARCHAR(255),
    games_played INTEGER,                -- Number of games in aggregate
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT ck_historical_epa_sport CHECK (sport = 'nfl'),
    CONSTRAINT ck_historical_epa_season CHECK (season BETWEEN 1999 AND 2100),
    CONSTRAINT ck_historical_epa_week CHECK (week IS NULL OR week BETWEEN 0 AND 22),
    CONSTRAINT uq_historical_epa_team_season_week UNIQUE (team_id, season, week)
);

-- Indexes
CREATE INDEX idx_historical_epa_team_season ON historical_epa(team_id, season);
CREATE INDEX idx_historical_epa_season_week ON historical_epa(season, week);
CREATE INDEX idx_historical_epa_source ON historical_epa(source);
```

### NEW: `elo_calculation_log` Table (Migration 0013)

Audit table for debugging Elo calculations and maintaining provenance:

```sql
CREATE TABLE elo_calculation_log (
    log_id SERIAL PRIMARY KEY,

    -- Game reference (SCD Type 2 - references specific game state row)
    game_state_id INTEGER,               -- FK to game_states.id (nullable for bootstrap)
    historical_game_id INTEGER,          -- FK to historical_games (for bootstrap)
    sport VARCHAR(20) NOT NULL,
    game_date DATE NOT NULL,

    -- Teams
    home_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id INTEGER NOT NULL REFERENCES teams(team_id),

    -- Scores
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,

    -- Elo BEFORE game
    home_elo_before DECIMAL(8,2) NOT NULL,
    away_elo_before DECIMAL(8,2) NOT NULL,

    -- Calculation inputs
    k_factor INTEGER NOT NULL,
    home_advantage DECIMAL(6,2) NOT NULL,
    home_expected DECIMAL(6,4) NOT NULL,  -- Expected score (0.00-1.00)
    away_expected DECIMAL(6,4) NOT NULL,

    -- Calculation outputs
    home_actual DECIMAL(4,2) NOT NULL,    -- 1.0 win, 0.5 tie, 0.0 loss
    away_actual DECIMAL(4,2) NOT NULL,
    home_elo_change DECIMAL(6,2) NOT NULL,
    away_elo_change DECIMAL(6,2) NOT NULL,

    -- Elo AFTER game
    home_elo_after DECIMAL(8,2) NOT NULL,
    away_elo_after DECIMAL(8,2) NOT NULL,

    -- Metadata
    calculation_source VARCHAR(50) NOT NULL,  -- 'bootstrap', 'realtime', 'backfill'
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT ck_elo_log_sport CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'mlb', 'wnba', 'mls')),
    CONSTRAINT ck_elo_log_expected CHECK (home_expected + away_expected BETWEEN 0.99 AND 1.01),
    CONSTRAINT ck_elo_log_actual CHECK (home_actual + away_actual BETWEEN 0.99 AND 1.01)
);

-- Indexes for common queries
CREATE INDEX idx_elo_log_game ON elo_calculation_log(game_id) WHERE game_id IS NOT NULL;
CREATE INDEX idx_elo_log_historical ON elo_calculation_log(historical_game_id) WHERE historical_game_id IS NOT NULL;
CREATE INDEX idx_elo_log_sport_date ON elo_calculation_log(sport, game_date);
CREATE INDEX idx_elo_log_teams ON elo_calculation_log(home_team_id, away_team_id);
CREATE INDEX idx_elo_log_source ON elo_calculation_log(calculation_source);
```

### Common Queries

**Get current Elo for a team:**
```sql
SELECT elo_rating, effective_date
FROM team_elo_ratings
WHERE team_id = :team_id
ORDER BY effective_date DESC
LIMIT 1;
```

**Get Elo at a specific date:**
```sql
SELECT elo_rating
FROM team_elo_ratings
WHERE team_id = :team_id
  AND effective_date <= :target_date
ORDER BY effective_date DESC
LIMIT 1;
```

**Get Elo trajectory for a team:**
```sql
SELECT effective_date, elo_rating, elo_change
FROM team_elo_ratings
WHERE team_id = :team_id
  AND effective_date >= :start_date
ORDER BY effective_date ASC;
```

**Get all current Elo ratings for a sport:**
```sql
WITH latest_elo AS (
    SELECT DISTINCT ON (team_id)
        team_id, elo_rating, effective_date
    FROM team_elo_ratings
    WHERE sport = :sport
    ORDER BY team_id, effective_date DESC
)
SELECT t.name, le.elo_rating, le.effective_date
FROM latest_elo le
JOIN teams t ON t.id = le.team_id
ORDER BY le.elo_rating DESC;
```

---

## 8. Pollers & Schedulers

### EloPoller Architecture

The `EloPoller` extends the `BasePoller` pattern (ADR-103) to provide automated Elo updates:

```python
# src/precog/schedulers/elo_poller.py
from precog.schedulers.base_poller import BasePoller
from precog.analytics.elo_engine import EloEngine
from typing import Dict, Any

class EloPoller(BasePoller):
    """Polls for completed games and updates Elo ratings.

    Follows BasePoller pattern (ADR-103) for consistent infrastructure.
    Naming: {Functionality}Poller (not platform-specific).
    """

    def __init__(
        self,
        elo_engine: EloEngine,
        sports: list[str],
        poll_interval: int = 300,  # 5 minutes
        enabled: bool = True
    ):
        super().__init__(
            name="EloPoller",
            poll_interval=poll_interval,
            enabled=enabled
        )
        self.elo_engine = elo_engine
        self.sports = sports

    def _poll_all(self) -> Dict[str, Any]:
        """Implementation of BasePoller template method.

        Returns:
            PollerStats with items_fetched, items_updated, items_created
        """
        stats = {
            'items_fetched': 0,
            'items_updated': 0,
            'items_created': 0,
            'by_sport': {}
        }

        for sport in self.sports:
            sport_stats = self._poll_sport(sport)
            stats['items_fetched'] += sport_stats['games_checked']
            stats['items_updated'] += sport_stats['elos_updated']
            stats['by_sport'][sport] = sport_stats

        return stats

    def _poll_sport(self, sport: str) -> Dict[str, int]:
        """Poll a single sport for completed games."""
        # Get games completed since last poll
        completed_games = self._get_newly_completed_games(sport)

        games_checked = len(completed_games)
        elos_updated = 0

        for game in completed_games:
            try:
                self.elo_engine.process_game(game)
                elos_updated += 2  # Both teams updated
            except Exception as e:
                self.logger.error(f"Elo update failed for game {game['id']}: {e}")

        return {
            'games_checked': games_checked,
            'elos_updated': elos_updated
        }
```

### Scheduler Integration

The `EloPoller` integrates with the `ServiceSupervisor` pattern (ADR-100):

```python
# scripts/run_elo_service.py
from precog.schedulers import ServiceSupervisor, EloPoller
from precog.analytics.elo_engine import EloEngine

def main():
    # Initialize Elo engine with sport-specific configuration
    elo_engine = EloEngine(
        k_factors={
            'nfl': 20, 'nba': 20, 'nhl': 6,
            'mlb': 4, 'ncaaf': 20, 'ncaab': 20
        }
    )

    # Create poller
    elo_poller = EloPoller(
        elo_engine=elo_engine,
        sports=['nfl', 'nba', 'nhl', 'mlb'],
        poll_interval=300,  # 5 minutes
    )

    # Create supervisor for health monitoring
    supervisor = ServiceSupervisor(
        services=[elo_poller],
        health_check_interval=60,
        metrics_output_interval=300
    )

    # Start with graceful shutdown handling
    supervisor.run()

if __name__ == '__main__':
    main()
```

### Poll Intervals by Sport

| Sport | Season | Poll Interval | Rationale |
|-------|--------|---------------|-----------|
| NFL | Sep-Feb | 5 min | Few games, high importance |
| NBA | Oct-Jun | 5 min | Multiple daily games |
| NHL | Oct-Jun | 5 min | Multiple daily games |
| MLB | Apr-Oct | 15 min | Many games, lower variance |
| NCAAF | Aug-Jan | 5 min | Weekend-heavy schedule |
| NCAAB | Nov-Apr | 5 min | Many games per day |

### Scheduler Configuration

```yaml
# config/elo_config.yaml
elo_poller:
  enabled: true
  poll_interval_seconds: 300
  sports:
    - nfl
    - nba
    - nhl
    - mlb
    - ncaaf
    - ncaab

  k_factors:
    nfl: 20
    nba: 20
    nhl: 6
    mlb: 4
    ncaaf: 20
    ncaab: 20

  home_advantage:
    nfl: 48
    nba: 100
    nhl: 33
    mlb: 24
    ncaaf: 55
    ncaab: 100

  season_carryover:
    weight: 0.75
    regression_target: 1505

  initial_rating: 1500
```

---

## 9. CLI Commands

### Elo Command Group

The CLI provides comprehensive Elo management through the `elo` command group:

```bash
# Main entry point
python main.py elo --help

# Available subcommands:
#   bootstrap   Bootstrap Elo ratings from historical data
#   update      Update Elo for recently completed games
#   show        Display current Elo ratings
#   history     Show Elo history for a team
#   predict     Calculate win probability between teams
#   export      Export Elo ratings to file
#   import      Import Elo ratings from file
```

### CLI Implementation

```python
# src/precog/cli/elo_commands.py
import typer
from typing import Optional, List
from datetime import date
from decimal import Decimal

elo_app = typer.Typer(name="elo", help="Elo rating management commands")

@elo_app.command()
def bootstrap(
    sport: str = typer.Argument(..., help="Sport to bootstrap (nfl, nba, nhl, mlb, ncaaf, ncaab)"),
    start_year: int = typer.Option(2020, help="Start year for historical data"),
    end_year: Optional[int] = typer.Option(None, help="End year (default: current)"),
    checkpoint: bool = typer.Option(True, help="Enable checkpointing for resume"),
    batch_size: int = typer.Option(1000, help="Games per batch"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output")
):
    """Bootstrap Elo ratings from historical game data.

    Example:
        python main.py elo bootstrap nfl --start-year 2020
        python main.py elo bootstrap nba --start-year 2015 --end-year 2024
    """
    from precog.analytics.elo_engine import EloEngine
    from precog.analytics.bootstrapper import EloBootstrapper

    engine = EloEngine(sport=sport)
    bootstrapper = EloBootstrapper(engine, checkpoint=checkpoint)

    with typer.progressbar(
        length=100,
        label=f"Bootstrapping {sport.upper()} Elo"
    ) as progress:
        def update_progress(pct: int):
            progress.update(pct - progress.pos)

        bootstrapper.run(
            start_year=start_year,
            end_year=end_year or date.today().year,
            batch_size=batch_size,
            progress_callback=update_progress
        )

    typer.echo(f"✓ Bootstrapped {bootstrapper.games_processed} games")
    typer.echo(f"✓ Updated ratings for {bootstrapper.teams_updated} teams")


@elo_app.command()
def show(
    sport: str = typer.Argument(..., help="Sport to show ratings for"),
    top: int = typer.Option(32, help="Number of teams to show"),
    format: str = typer.Option("table", help="Output format: table, json, csv"),
    as_of: Optional[str] = typer.Option(None, help="Historical date (YYYY-MM-DD)")
):
    """Display current Elo ratings for a sport.

    Example:
        python main.py elo show nfl
        python main.py elo show nba --top 10 --format json
        python main.py elo show nfl --as-of 2024-12-01
    """
    from precog.analytics.elo_queries import get_current_ratings

    target_date = date.fromisoformat(as_of) if as_of else None
    ratings = get_current_ratings(sport=sport, as_of=target_date, limit=top)

    if format == "table":
        typer.echo(f"\n{sport.upper()} Elo Ratings")
        typer.echo("=" * 50)
        typer.echo(f"{'Rank':<6}{'Team':<25}{'Elo':<10}{'Change':<10}")
        typer.echo("-" * 50)
        for i, r in enumerate(ratings, 1):
            change = f"+{r['elo_change']}" if r['elo_change'] > 0 else str(r['elo_change'])
            typer.echo(f"{i:<6}{r['team_name']:<25}{r['elo_rating']:<10}{change:<10}")
    elif format == "json":
        import json
        typer.echo(json.dumps(ratings, indent=2, default=str))
    elif format == "csv":
        typer.echo("rank,team,elo,change")
        for i, r in enumerate(ratings, 1):
            typer.echo(f"{i},{r['team_name']},{r['elo_rating']},{r['elo_change']}")


@elo_app.command()
def predict(
    sport: str = typer.Argument(..., help="Sport"),
    team_a: str = typer.Argument(..., help="First team"),
    team_b: str = typer.Argument(..., help="Second team"),
    neutral: bool = typer.Option(False, help="Neutral site (no home advantage)")
):
    """Predict win probability between two teams.

    Example:
        python main.py elo predict nfl "Kansas City Chiefs" "Philadelphia Eagles"
        python main.py elo predict nba "Boston Celtics" "Los Angeles Lakers" --neutral
    """
    from precog.analytics.elo_engine import EloEngine
    from precog.analytics.elo_queries import get_team_elo

    engine = EloEngine(sport=sport)

    elo_a = get_team_elo(sport, team_a)
    elo_b = get_team_elo(sport, team_b)

    if elo_a is None or elo_b is None:
        typer.echo(f"Error: Team not found", err=True)
        raise typer.Exit(1)

    # Calculate win probability
    if not neutral:
        # First team assumed home
        elo_a_adj = elo_a + engine.home_advantage
    else:
        elo_a_adj = elo_a

    prob_a = engine.calculate_expected_score(elo_a_adj, elo_b)
    prob_b = Decimal("1") - prob_a

    typer.echo(f"\n{sport.upper()} Win Probability Prediction")
    typer.echo("=" * 50)
    typer.echo(f"{team_a}: Elo {elo_a} → {prob_a:.1%} win probability")
    typer.echo(f"{team_b}: Elo {elo_b} → {prob_b:.1%} win probability")
    if not neutral:
        typer.echo(f"\n(Home advantage of {engine.home_advantage} Elo points applied to {team_a})")


@elo_app.command()
def history(
    sport: str = typer.Argument(..., help="Sport"),
    team: str = typer.Argument(..., help="Team name"),
    games: int = typer.Option(20, help="Number of games to show"),
    format: str = typer.Option("table", help="Output format: table, json, chart")
):
    """Show Elo history for a team.

    Example:
        python main.py elo history nfl "Kansas City Chiefs" --games 10
        python main.py elo history nba "Boston Celtics" --format chart
    """
    from precog.analytics.elo_queries import get_team_elo_history

    history = get_team_elo_history(sport, team, limit=games)

    if format == "table":
        typer.echo(f"\n{team} Elo History")
        typer.echo("=" * 60)
        typer.echo(f"{'Date':<12}{'Opponent':<25}{'Result':<8}{'Elo':<8}{'Change':<8}")
        typer.echo("-" * 60)
        for h in history:
            result = "W" if h['won'] else "L"
            change = f"+{h['elo_change']}" if h['elo_change'] > 0 else str(h['elo_change'])
            typer.echo(f"{h['date']:<12}{h['opponent']:<25}{result:<8}{h['elo_rating']:<8}{change:<8}")
    elif format == "chart":
        # ASCII chart of Elo over time
        elos = [h['elo_rating'] for h in history]
        min_elo = min(elos) - 20
        max_elo = max(elos) + 20
        height = 10

        typer.echo(f"\n{team} Elo Trend (last {len(history)} games)")
        for row in range(height, -1, -1):
            threshold = min_elo + (max_elo - min_elo) * row / height
            line = f"{int(threshold):>5} |"
            for elo in elos:
                if elo >= threshold:
                    line += "█"
                else:
                    line += " "
            typer.echo(line)


@elo_app.command()
def update(
    sport: Optional[str] = typer.Option(None, help="Specific sport to update (default: all)"),
    hours: int = typer.Option(24, help="Check games from last N hours"),
    dry_run: bool = typer.Option(False, help="Show what would be updated without applying")
):
    """Update Elo ratings for recently completed games.

    Example:
        python main.py elo update
        python main.py elo update --sport nfl --hours 48
        python main.py elo update --dry-run
    """
    from precog.analytics.elo_updater import EloUpdater

    updater = EloUpdater()
    sports = [sport] if sport else ['nfl', 'nba', 'nhl', 'mlb', 'ncaaf', 'ncaab']

    for s in sports:
        typer.echo(f"\nChecking {s.upper()}...")
        updates = updater.get_pending_updates(s, hours=hours)

        if not updates:
            typer.echo(f"  No pending updates")
            continue

        typer.echo(f"  Found {len(updates)} games to process")

        if dry_run:
            for u in updates[:5]:  # Show first 5
                typer.echo(f"    - {u['home_team']} vs {u['away_team']} ({u['date']})")
            if len(updates) > 5:
                typer.echo(f"    ... and {len(updates) - 5} more")
        else:
            processed = updater.process_updates(updates)
            typer.echo(f"  ✓ Processed {processed} games")
```

### CLI Usage Examples

```bash
# Bootstrap all NFL Elo from 2020-present
python main.py elo bootstrap nfl --start-year 2020

# Bootstrap NBA with checkpointing (resumable)
python main.py elo bootstrap nba --start-year 2015 --checkpoint

# Show top 32 NFL teams by Elo
python main.py elo show nfl

# Show top 10 NBA teams as JSON
python main.py elo show nba --top 10 --format json

# Historical ratings as of specific date
python main.py elo show nfl --as-of 2024-12-01

# Predict outcome between two teams
python main.py elo predict nfl "Kansas City Chiefs" "Philadelphia Eagles"

# Neutral site prediction
python main.py elo predict nba "Boston Celtics" "Los Angeles Lakers" --neutral

# Show team Elo history
python main.py elo history nfl "Kansas City Chiefs" --games 20

# ASCII chart of Elo trend
python main.py elo history nba "Boston Celtics" --format chart

# Update Elo for recent games
python main.py elo update

# Dry-run to see what would be updated
python main.py elo update --dry-run --hours 48
```

---

## 10. TUI Support

### Textual-Based TUI

The TUI provides a rich terminal interface for Elo monitoring using the Textual framework:

```python
# src/precog/tui/elo_dashboard.py
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Static, Sparkline
from textual.reactive import reactive

class EloRatingsTable(DataTable):
    """Live-updating Elo ratings table."""

    def __init__(self, sport: str):
        super().__init__()
        self.sport = sport
        self.add_columns("Rank", "Team", "Elo", "Change", "Last Game")

    async def refresh_data(self):
        """Refresh ratings from database."""
        from precog.analytics.elo_queries import get_current_ratings

        ratings = get_current_ratings(self.sport, limit=32)
        self.clear()

        for i, r in enumerate(ratings, 1):
            change = f"+{r['elo_change']}" if r['elo_change'] > 0 else str(r['elo_change'])
            self.add_row(
                str(i),
                r['team_name'],
                str(r['elo_rating']),
                change,
                r['last_game_date']
            )


class EloDashboard(App):
    """Terminal UI for Elo rating monitoring."""

    CSS = """
    #main-container {
        layout: horizontal;
    }

    .sport-panel {
        width: 1fr;
        border: solid green;
        padding: 1;
    }

    .sport-header {
        text-align: center;
        text-style: bold;
        background: $accent;
    }

    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("n", "next_sport", "Next Sport"),
        ("p", "prev_sport", "Prev Sport"),
        ("q", "quit", "Quit"),
    ]

    current_sport: reactive[str] = reactive("nfl")
    sports: list[str] = ["nfl", "nba", "nhl", "mlb", "ncaaf", "ncaab"]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Vertical(classes="sport-panel"):
                yield Static(f"[b]{self.current_sport.upper()} Elo Ratings[/b]",
                           classes="sport-header", id="sport-header")
                yield EloRatingsTable(self.current_sport)
        yield Footer()

    def action_refresh(self):
        """Refresh the current ratings table."""
        table = self.query_one(EloRatingsTable)
        self.run_worker(table.refresh_data())

    def action_next_sport(self):
        """Switch to next sport."""
        idx = self.sports.index(self.current_sport)
        self.current_sport = self.sports[(idx + 1) % len(self.sports)]
        self._update_sport()

    def action_prev_sport(self):
        """Switch to previous sport."""
        idx = self.sports.index(self.current_sport)
        self.current_sport = self.sports[(idx - 1) % len(self.sports)]
        self._update_sport()

    def _update_sport(self):
        """Update displayed sport."""
        header = self.query_one("#sport-header", Static)
        header.update(f"[b]{self.current_sport.upper()} Elo Ratings[/b]")

        table = self.query_one(EloRatingsTable)
        table.sport = self.current_sport
        self.run_worker(table.refresh_data())


def run_dashboard():
    """Launch the Elo dashboard TUI."""
    app = EloDashboard()
    app.run()
```

### TUI Features

| Feature | Keybinding | Description |
|---------|------------|-------------|
| Refresh | `r` | Refresh current sport's ratings |
| Next Sport | `n` | Switch to next sport (NFL→NBA→NHL→...) |
| Prev Sport | `p` | Switch to previous sport |
| Quit | `q` | Exit the dashboard |
| Filter | `/` | Filter teams by name (planned) |
| Sort | `s` | Cycle sort columns (planned) |

### TUI CLI Command

```python
# In main.py
@app.command()
def elo_dashboard():
    """Launch the Elo ratings dashboard TUI.

    Example:
        python main.py elo-dashboard
    """
    from precog.tui.elo_dashboard import run_dashboard
    run_dashboard()
```

### TUI Screenshots (ASCII Preview)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Precog Elo Dashboard                                            12:34:56 PM │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║                          NFL Elo Ratings                              ║  │
│  ╠══════╦═══════════════════════════╦═══════════╦════════╦═══════════════╣  │
│  ║ Rank ║ Team                      ║    Elo    ║ Change ║   Last Game   ║  │
│  ╠══════╬═══════════════════════════╬═══════════╬════════╬═══════════════╣  │
│  ║   1  ║ Kansas City Chiefs        ║   1724    ║  +12   ║  Dec 22, 2024 ║  │
│  ║   2  ║ Philadelphia Eagles       ║   1698    ║   +8   ║  Dec 22, 2024 ║  │
│  ║   3  ║ Detroit Lions             ║   1687    ║  +15   ║  Dec 22, 2024 ║  │
│  ║   4  ║ Buffalo Bills             ║   1672    ║   +5   ║  Dec 22, 2024 ║  │
│  ║   5  ║ Baltimore Ravens          ║   1665    ║  -10   ║  Dec 22, 2024 ║  │
│  ║  ... ║ ...                       ║   ...     ║  ...   ║  ...          ║  │
│  ╚══════╩═══════════════════════════╩═══════════╩════════╩═══════════════╝  │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ [r] Refresh  [n] Next Sport  [p] Prev Sport  [q] Quit                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Data Ingestion Pipeline

### Complete Data Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION PIPELINE                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: DATA COLLECTION                                                    │
│  ───────────────────────                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │nflreadpy │  │ nba_api  │  │nhl-api-py│  │pybaseball│  │   cfbd   │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       │             │             │             │             │            │
│       └──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┘            │
│              │             │             │             │                    │
│              ▼             ▼             ▼             ▼                    │
│  STEP 2: DATA NORMALIZATION                                                 │
│  ──────────────────────────                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    GameResultAdapter                             │       │
│  │  - Normalizes team names across sources                          │       │
│  │  - Standardizes date formats                                     │       │
│  │  - Validates score data                                          │       │
│  │  - Returns: List[GameResult]                                     │       │
│  └──────────────────────────────┬──────────────────────────────────┘       │
│                                 │                                           │
│                                 ▼                                           │
│  STEP 3: ELO COMPUTATION                                                    │
│  ───────────────────────                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                       EloEngine                                  │       │
│  │  - Loads current team ratings from database                      │       │
│  │  - Applies home-field advantage                                  │       │
│  │  - Computes expected scores                                      │       │
│  │  - Updates ratings with K-factor                                 │       │
│  │  - Handles season carryover                                      │       │
│  └──────────────────────────────┬──────────────────────────────────┘       │
│                                 │                                           │
│                                 ▼                                           │
│  STEP 4: DATABASE PERSISTENCE                                               │
│  ────────────────────────────                                               │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    team_elo_ratings                              │       │
│  │  - Append new rating record                                      │       │
│  │  - Store previous rating for delta tracking                      │       │
│  │  - Link to source game_id                                        │       │
│  │  - Set effective_date                                            │       │
│  └──────────────────────────────┬──────────────────────────────────┘       │
│                                 │                                           │
│                                 ▼                                           │
│  STEP 5: NOTIFICATION & LOGGING                                             │
│  ──────────────────────────────                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  - Log Elo update with structured logging                        │       │
│  │  - Emit metric for monitoring                                    │       │
│  │  - Notify subscribers (WebSocket) for real-time updates          │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### Data Adapter Interface

```python
# src/precog/analytics/data_sources/base_adapter.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

@dataclass
class GameResult:
    """Normalized game result for Elo computation."""
    game_id: str
    sport: str
    game_date: date
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    is_neutral: bool = False
    is_playoff: bool = False
    overtime: bool = False


class BaseDataAdapter(ABC):
    """Abstract base class for sport-specific data adapters."""

    @property
    @abstractmethod
    def sport(self) -> str:
        """Return the sport code (e.g., 'nfl', 'nba')."""
        pass

    @abstractmethod
    def fetch_games(
        self,
        start_date: date,
        end_date: date,
        include_playoffs: bool = True
    ) -> List[GameResult]:
        """Fetch game results for the date range."""
        pass

    @abstractmethod
    def fetch_season(
        self,
        year: int,
        season_type: str = 'regular'
    ) -> List[GameResult]:
        """Fetch all games for a season."""
        pass

    def normalize_team_name(self, raw_name: str) -> str:
        """Normalize team name for database matching."""
        # Subclasses override with sport-specific normalization
        return raw_name.strip()
```

### Sport-Specific Adapters

```python
# src/precog/analytics/data_sources/nfl_adapter.py
import nflreadpy
from datetime import date
from typing import List

class NFLDataAdapter(BaseDataAdapter):
    """NFL data adapter using nflreadpy library."""

    @property
    def sport(self) -> str:
        return "nfl"

    def fetch_games(
        self,
        start_date: date,
        end_date: date,
        include_playoffs: bool = True
    ) -> List[GameResult]:
        """Fetch NFL games from nflreadpy."""
        years = list(range(start_date.year, end_date.year + 1))
        schedules = nflreadpy.load_schedules(years)

        # Filter by date range
        mask = (
            (schedules['gameday'] >= start_date.isoformat()) &
            (schedules['gameday'] <= end_date.isoformat())
        )
        if not include_playoffs:
            mask &= (schedules['game_type'] == 'REG')

        games = schedules[mask]

        return [
            GameResult(
                game_id=row['game_id'],
                sport='nfl',
                game_date=date.fromisoformat(row['gameday']),
                home_team=self.normalize_team_name(row['home_team']),
                away_team=self.normalize_team_name(row['away_team']),
                home_score=int(row['home_score']),
                away_score=int(row['away_score']),
                is_playoff=(row['game_type'] != 'REG'),
                overtime=('OT' in str(row.get('overtime', '')))
            )
            for _, row in games.iterrows()
            if row['home_score'] is not None  # Skip unplayed games
        ]

    def fetch_pbp_with_epa(self, year: int) -> 'pd.DataFrame':
        """Fetch play-by-play data with EPA columns."""
        return nflreadpy.load_pbp(year)


# src/precog/analytics/data_sources/nba_adapter.py
from nba_api.stats.endpoints import LeagueGameFinder
from nba_api.stats.static import teams
from datetime import date
from typing import List

class NBADataAdapter(BaseDataAdapter):
    """NBA data adapter using nba_api library."""

    @property
    def sport(self) -> str:
        return "nba"

    def __init__(self):
        # Build team lookup
        self.team_lookup = {
            t['id']: t['full_name']
            for t in teams.get_teams()
        }

    def fetch_games(
        self,
        start_date: date,
        end_date: date,
        include_playoffs: bool = True
    ) -> List[GameResult]:
        """Fetch NBA games from nba_api."""
        season_types = ['Regular Season']
        if include_playoffs:
            season_types.append('Playoffs')

        all_games = []
        for season_type in season_types:
            finder = LeagueGameFinder(
                date_from_nullable=start_date.strftime('%m/%d/%Y'),
                date_to_nullable=end_date.strftime('%m/%d/%Y'),
                season_type_nullable=season_type,
                league_id_nullable='00'
            )
            games_df = finder.get_data_frames()[0]
            all_games.append(games_df)

        # Process and normalize
        # ... (parsing logic)

        return results


# src/precog/analytics/data_sources/nhl_adapter.py
from nhl_api_py import NHLClient
from datetime import date
from typing import List

class NHLDataAdapter(BaseDataAdapter):
    """NHL data adapter using nhl-api-py library."""

    @property
    def sport(self) -> str:
        return "nhl"

    def __init__(self):
        self.client = NHLClient()

    def fetch_games(
        self,
        start_date: date,
        end_date: date,
        include_playoffs: bool = True
    ) -> List[GameResult]:
        """Fetch NHL games from nhl-api-py."""
        results = []

        current = start_date
        while current <= end_date:
            schedule = self.client.schedule.get_schedule(
                date=current.isoformat()
            )

            for game in schedule.get('games', []):
                if game['gameState'] != 'OFF':  # Not completed
                    continue

                results.append(GameResult(
                    game_id=str(game['id']),
                    sport='nhl',
                    game_date=current,
                    home_team=game['homeTeam']['name']['default'],
                    away_team=game['awayTeam']['name']['default'],
                    home_score=game['homeTeam']['score'],
                    away_score=game['awayTeam']['score'],
                    is_playoff=(game['gameType'] == 3),
                    overtime=game.get('periodDescriptor', {}).get('number', 3) > 3
                ))

            current += timedelta(days=1)

        return results
```

---

## 12. Implementation Checklist

### Phase 3 Implementation Tasks

- [ ] **Core Engine** (`src/precog/analytics/elo_engine.py`)
  - [ ] EloEngine class with calculate_expected and update_rating methods
  - [ ] Sport-specific K-factor configuration
  - [ ] Home-field advantage integration
  - [ ] Season carryover logic

- [ ] **Data Source Adapters** (`src/precog/analytics/data_sources/`)
  - [ ] NFLDataAdapter (nflreadpy)
  - [ ] NBADataAdapter (nba_api)
  - [ ] NHLDataAdapter (nhl-api-py)
  - [ ] MLBDataAdapter (pybaseball)
  - [ ] NCAAFDataAdapter (cfbd)
  - [ ] NCAABDataAdapter (sportsdataverse)

- [ ] **Database Integration**
  - [ ] Migration for team_elo_ratings table
  - [ ] CRUD operations in crud_operations.py
  - [ ] Query helpers for current/historical Elo

- [ ] **Historical Bootstrapping**
  - [ ] CLI command: `python main.py elo bootstrap --sport nfl`
  - [ ] Progress tracking and checkpointing
  - [ ] Season transition handling

- [ ] **Real-Time Updates**
  - [ ] EloUpdateListener class
  - [ ] Integration with game_states polling
  - [ ] Batch update for multiple games

- [ ] **EPA Integration** (NFL only)
  - [ ] EPA data collection from nflreadpy
  - [ ] EPA-weighted Elo adjustment
  - [ ] Offensive/defensive EPA ratings

- [ ] **Testing**
  - [ ] Unit tests for Elo calculations
  - [ ] Property tests for mathematical invariants
  - [ ] Integration tests with database
  - [ ] Historical accuracy validation

---

## Appendix: Reference Values

### FiveThirtyEight K-Factors (Historical Reference)

These were the K-factors used by FiveThirtyEight before shutdown:

| Sport | K-Factor | Notes |
|-------|----------|-------|
| NFL | 20 | Standard for football |
| NBA | 20 | Adjusted for playoff performance |
| NHL | 6 | Low due to high game count |
| MLB | 4 | Very low due to 162-game season |

### Expected Win % by Elo Difference

| Elo Difference | Higher-Rated Team Win % |
|----------------|------------------------|
| 0 | 50.0% |
| 50 | 57.1% |
| 100 | 64.0% |
| 150 | 70.3% |
| 200 | 75.9% |
| 250 | 80.8% |
| 300 | 84.9% |
| 400 | 90.9% |
| 500 | 94.7% |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-24 | Initial release - Comprehensive Elo computation guide |

---

**END OF ELO_COMPUTATION_GUIDE V1.0**
