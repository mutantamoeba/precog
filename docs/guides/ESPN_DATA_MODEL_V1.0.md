# ESPN Data Model Guide

---
**Version:** 1.0
**Created:** 2025-11-27
**Last Updated:** 2025-11-27
**Status:** Complete
**Phase:** 2 (Live Data Integration)
**Related ADR:** ADR-029 (ESPN Data Model with Normalized Schema)
**Related Requirements:** REQ-DATA-001 through REQ-DATA-005
---

## Overview

This guide documents the ESPN data model for the Precog prediction market platform. It covers:

1. **Database Schema** - Tables for venues, team rankings, and live game states
2. **TypedDict Definitions** - Type-safe Python interfaces for ESPN API responses
3. **CRUD Operations** - Functions for creating, reading, and updating ESPN data
4. **JSONB Situation Data** - Sport-specific fields stored as flexible JSON
5. **Query Patterns** - Common database queries for live game tracking

### Supported Sports

| League | Endpoint | Season Structure |
|--------|----------|------------------|
| NFL | `/football/nfl/scoreboard` | 18 weeks + playoffs |
| NCAAF | `/football/college-football/scoreboard` | 15 weeks + bowls |
| NBA | `/basketball/nba/scoreboard` | 82 games + playoffs |
| NCAAB | `/basketball/mens-college-basketball/scoreboard` | Nov-Apr + tournament |
| NHL | `/hockey/nhl/scoreboard` | 82 games + playoffs |
| WNBA | `/basketball/wnba/scoreboard` | May-Oct |

---

## Database Schema

### Table Overview

| Table | Purpose | Versioning | Keys |
|-------|---------|------------|------|
| `venues` | Stadium/arena locations | Simple UPDATE | `venue_id`, `espn_venue_id` |
| `team_rankings` | AP Poll, CFP, etc. | Temporal (season+week) | `ranking_id` |
| `teams` | Multi-sport team entities | Simple UPDATE | `team_id`, `espn_team_id` |
| `game_states` | Live game tracking | SCD Type 2 | `game_state_id`, `espn_event_id` |

### 1. Venues Table

Normalized venue data from ESPN API. Uses simple UPSERT (no versioning) since venue data rarely changes.

```sql
CREATE TABLE venues (
    venue_id SERIAL PRIMARY KEY,
    espn_venue_id VARCHAR(50) UNIQUE NOT NULL,
    venue_name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    capacity INTEGER,
    indoor BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Example Data:**
| venue_id | espn_venue_id | venue_name | city | state | capacity | indoor |
|----------|---------------|------------|------|-------|----------|--------|
| 1 | 3622 | GEHA Field at Arrowhead Stadium | Kansas City | Missouri | 76416 | FALSE |
| 2 | 3687 | SoFi Stadium | Inglewood | California | 70240 | TRUE |

### 2. Team Rankings Table

Temporal validity for weekly poll rankings. Each (team, type, season, week) is a unique snapshot.

```sql
CREATE TABLE team_rankings (
    ranking_id SERIAL PRIMARY KEY,
    team_id INTEGER REFERENCES teams(team_id),
    ranking_type VARCHAR(50) NOT NULL,  -- 'ap_poll', 'cfp', 'coaches_poll'
    rank INTEGER NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER,  -- NULL for preseason/final
    ranking_date DATE NOT NULL,
    points INTEGER,
    first_place_votes INTEGER,
    previous_rank INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (team_id, ranking_type, season, week)
);
```

**Example Data:**
| ranking_id | team_id | ranking_type | rank | season | week | points |
|------------|---------|--------------|------|--------|------|--------|
| 1 | 42 | ap_poll | 1 | 2024 | 13 | 1547 |
| 2 | 42 | cfp | 2 | 2024 | 13 | NULL |

### 3. Teams Table (Enhanced)

Multi-sport support with ESPN ID linking.

```sql
-- Phase 2 additions to existing teams table
ALTER TABLE teams ADD COLUMN IF NOT EXISTS espn_team_id VARCHAR(50);
ALTER TABLE teams ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE teams ADD COLUMN IF NOT EXISTS conference VARCHAR(100);
ALTER TABLE teams ADD COLUMN IF NOT EXISTS division VARCHAR(100);
ALTER TABLE teams ADD COLUMN IF NOT EXISTS sport VARCHAR(20) DEFAULT 'football';
ALTER TABLE teams ADD COLUMN IF NOT EXISTS league VARCHAR(20) DEFAULT 'nfl';

CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_espn_league ON teams(espn_team_id, league);
```

### 4. Game States Table (SCD Type 2)

Complete game state history with SCD Type 2 versioning. Every score change, clock update, and situation change creates a new row.

```sql
CREATE TABLE game_states (
    game_state_id SERIAL PRIMARY KEY,
    espn_event_id VARCHAR(50) NOT NULL,

    -- Team references
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    venue_id INTEGER REFERENCES venues(venue_id),

    -- Score and time
    home_score INTEGER NOT NULL DEFAULT 0,
    away_score INTEGER NOT NULL DEFAULT 0,
    period INTEGER NOT NULL DEFAULT 0,
    clock_seconds DECIMAL(10,2),
    clock_display VARCHAR(20),

    -- Game metadata
    game_status VARCHAR(50) NOT NULL,  -- 'pre', 'in_progress', 'halftime', 'final'
    game_date TIMESTAMP WITH TIME ZONE,
    broadcast VARCHAR(100),
    neutral_site BOOLEAN DEFAULT FALSE,
    season_type VARCHAR(20),  -- 'preseason', 'regular', 'playoff', 'bowl'
    week_number INTEGER,
    league VARCHAR(20),

    -- Flexible data (sport-specific)
    situation JSONB,
    linescores JSONB,

    -- SCD Type 2 versioning
    row_start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    row_end_timestamp TIMESTAMP WITH TIME ZONE,
    row_current_ind BOOLEAN DEFAULT TRUE,

    data_source VARCHAR(50) DEFAULT 'espn'
);

-- Partial unique index: only one current row per event
CREATE UNIQUE INDEX idx_game_states_current_unique
    ON game_states(espn_event_id) WHERE row_current_ind = TRUE;

-- Performance indexes
CREATE INDEX idx_game_states_event ON game_states(espn_event_id);
CREATE INDEX idx_game_states_status ON game_states(game_status);
CREATE INDEX idx_game_states_date ON game_states(game_date);
CREATE INDEX idx_game_states_league ON game_states(league);
CREATE INDEX idx_game_states_situation ON game_states USING GIN (situation);
```

---

## TypedDict Definitions

Type-safe Python interfaces for ESPN API responses. Located in `src/precog/api_connectors/espn_client.py`.

### ESPNTeamInfo

```python
class ESPNTeamInfo(TypedDict, total=False):
    """Static team information from ESPN API."""
    espn_team_id: str       # "12" (ESPN's numeric ID)
    team_code: str          # "KC"
    team_name: str          # "Kansas City Chiefs"
    display_name: str       # "Chiefs"
    record: str             # "10-1"
    home_record: str        # "5-0"
    away_record: str        # "5-1"
    rank: int | None        # College rankings only
```

### ESPNVenueInfo

```python
class ESPNVenueInfo(TypedDict, total=False):
    """Venue/stadium information from ESPN API."""
    espn_venue_id: str      # "3622"
    venue_name: str         # "GEHA Field at Arrowhead Stadium"
    city: str               # "Kansas City"
    state: str              # "Missouri"
    capacity: int           # 76416
    indoor: bool            # False
```

### ESPNGameMetadata

```python
class ESPNGameMetadata(TypedDict, total=False):
    """Static game information that doesn't change during the game."""
    espn_event_id: str              # "401547417"
    game_date: str                  # "2024-11-29T20:15:00Z"
    home_team: ESPNTeamInfo
    away_team: ESPNTeamInfo
    venue: ESPNVenueInfo
    broadcast: str                  # "NBC"
    neutral_site: bool              # False
    season_type: str                # "regular"
    week_number: int | None         # 13
```

### ESPNSituationData

```python
class ESPNSituationData(TypedDict, total=False):
    """Sport-specific situation data (stored as JSONB in database)."""
    # Common to all sports
    possession: str | None
    home_timeouts: int
    away_timeouts: int

    # Football (NFL/NCAAF)
    down: int | None
    distance: int | None
    yard_line: int | None
    is_red_zone: bool
    home_turnovers: int
    away_turnovers: int
    last_play: str
    drive_plays: int
    drive_yards: int

    # Basketball (NBA/NCAAB/WNBA)
    home_fouls: int
    away_fouls: int
    bonus: str | None
    possession_arrow: str | None

    # Hockey (NHL)
    home_powerplay: bool
    away_powerplay: bool
    powerplay_time: str
    home_shots: int
    away_shots: int
```

### ESPNGameState

```python
class ESPNGameState(TypedDict, total=False):
    """Dynamic game state that changes during live games."""
    espn_event_id: str
    home_score: int
    away_score: int
    period: int
    clock_seconds: float
    clock_display: str          # "5:32" or "12:00 - 2nd"
    game_status: str            # 'pre', 'in_progress', 'halftime', 'final'
    situation: ESPNSituationData
    linescores: list[list[int]] # [[7, 14, 3, 0], [10, 0, 7, 0]]
```

### ESPNGameFull

```python
class ESPNGameFull(TypedDict, total=False):
    """Complete game data combining metadata and current state."""
    metadata: ESPNGameMetadata
    state: ESPNGameState
```

---

## CRUD Operations

All functions are in `src/precog/database/crud_operations.py`.

### Venue Operations

#### create_venue()

Create or update a venue record using UPSERT.

```python
from precog.database.crud_operations import create_venue

venue_id = create_venue(
    espn_venue_id="3622",
    venue_name="GEHA Field at Arrowhead Stadium",
    city="Kansas City",
    state="Missouri",
    capacity=76416,
    indoor=False
)
print(f"Venue ID: {venue_id}")  # Venue ID: 1
```

#### get_venue_by_espn_id()

Retrieve venue by ESPN's unique identifier.

```python
from precog.database.crud_operations import get_venue_by_espn_id

venue = get_venue_by_espn_id("3622")
if venue:
    print(f"{venue['venue_name']} - {venue['city']}, {venue['state']}")
    # GEHA Field at Arrowhead Stadium - Kansas City, Missouri
```

### Team Ranking Operations

#### create_team_ranking()

Create or update a team ranking record.

```python
from precog.database.crud_operations import create_team_ranking
from datetime import datetime

ranking_id = create_team_ranking(
    team_id=42,
    ranking_type="ap_poll",
    rank=3,
    season=2024,
    week=13,
    ranking_date=datetime(2024, 11, 24),
    points=1432,
    first_place_votes=12,
    previous_rank=4
)
```

#### get_team_rankings()

Query rankings by team, type, and/or season.

```python
from precog.database.crud_operations import get_team_rankings

# Get all AP Poll rankings for a team in 2024
rankings = get_team_rankings(
    team_id=42,
    ranking_type="ap_poll",
    season=2024
)
for r in rankings:
    print(f"Week {r['week']}: #{r['rank']} ({r['points']} points)")
```

#### get_current_rankings()

Get the latest rankings for a specific poll type.

```python
from precog.database.crud_operations import get_current_rankings

# Get current AP Poll Top 25
top25 = get_current_rankings(
    ranking_type="ap_poll",
    season=2024,
    limit=25
)
for r in top25:
    print(f"#{r['rank']} {r['team_name']} ({r['points']})")
```

### Game State Operations

#### upsert_game_state() - Primary Update Function

The main function for updating live game data. Uses SCD Type 2 versioning.

```python
from precog.database.crud_operations import upsert_game_state
from decimal import Decimal

# Update score during a live game
state_id = upsert_game_state(
    espn_event_id="401547417",
    home_team_id=1,
    away_team_id=2,
    venue_id=1,
    home_score=14,
    away_score=7,
    period=2,
    clock_seconds=Decimal("332.0"),
    clock_display="5:32",
    game_status="in_progress",
    league="nfl",
    situation={
        "possession": "KC",
        "down": 2,
        "distance": 7,
        "yard_line": 35,
        "is_red_zone": False,
        "home_timeouts": 2,
        "away_timeouts": 3
    },
    linescores=[[7, 7], [7, 0]]
)
```

#### get_current_game_state()

Get the current (latest) state for a game.

```python
from precog.database.crud_operations import get_current_game_state

state = get_current_game_state("401547417")
if state:
    print(f"{state['home_team_code']} {state['home_score']}-{state['away_score']} {state['away_team_code']}")
    print(f"Period {state['period']}, {state['clock_display']}")
    # KC 14-7 BUF
    # Period 2, 5:32
```

#### get_game_state_history()

Get complete history for backtesting and analysis.

```python
from precog.database.crud_operations import get_game_state_history

history = get_game_state_history("401547417", limit=50)
for state in history:
    print(f"{state['row_start_timestamp']}: {state['home_score']}-{state['away_score']}")
```

#### get_live_games()

Get all currently in-progress games.

```python
from precog.database.crud_operations import get_live_games

# All live games
games = get_live_games()

# NFL live games only
nfl_games = get_live_games(league="nfl")
for g in nfl_games:
    print(f"{g['home_team_code']} {g['home_score']}-{g['away_score']} {g['away_team_code']}")
```

---

## JSONB Situation Schemas

Sport-specific situation data is stored as JSONB for flexibility. Each sport has different relevant fields.

### Football (NFL/NCAAF)

```json
{
  "possession": "KC",
  "down": 2,
  "distance": 7,
  "yard_line": 35,
  "is_red_zone": false,
  "home_turnovers": 1,
  "away_turnovers": 0,
  "home_timeouts": 2,
  "away_timeouts": 3,
  "last_play": "Rush for 4 yards by P.Mahomes",
  "drive_plays": 5,
  "drive_yards": 32
}
```

### Basketball (NBA/NCAAB/WNBA)

```json
{
  "possession": "LAL",
  "home_fouls": 4,
  "away_fouls": 3,
  "home_timeouts": 4,
  "away_timeouts": 5,
  "bonus": "single",
  "possession_arrow": "BOS"
}
```

### Hockey (NHL)

```json
{
  "home_powerplay": true,
  "away_powerplay": false,
  "powerplay_time": "1:45",
  "home_shots": 28,
  "away_shots": 31,
  "home_saves": 30,
  "away_saves": 27
}
```

### Querying JSONB Data

```sql
-- Find games in red zone
SELECT * FROM game_states
WHERE row_current_ind = TRUE
  AND league = 'nfl'
  AND situation->>'is_red_zone' = 'true';

-- Find games with power play
SELECT * FROM game_states
WHERE row_current_ind = TRUE
  AND league = 'nhl'
  AND (situation->>'home_powerplay' = 'true'
       OR situation->>'away_powerplay' = 'true');

-- Get shot totals from hockey games
SELECT
    espn_event_id,
    (situation->>'home_shots')::int AS home_shots,
    (situation->>'away_shots')::int AS away_shots
FROM game_states
WHERE row_current_ind = TRUE AND league = 'nhl';
```

---

## Query Patterns

### Get Current NFL Scoreboard

```sql
SELECT
    gs.espn_event_id,
    th.team_code AS home_team,
    ta.team_code AS away_team,
    gs.home_score,
    gs.away_score,
    gs.period,
    gs.clock_display,
    gs.game_status,
    v.venue_name
FROM game_states gs
JOIN teams th ON gs.home_team_id = th.team_id
JOIN teams ta ON gs.away_team_id = ta.team_id
LEFT JOIN venues v ON gs.venue_id = v.venue_id
WHERE gs.row_current_ind = TRUE
  AND gs.league = 'nfl'
  AND gs.game_date::date = CURRENT_DATE
ORDER BY gs.game_date;
```

### Get Game State History for Backtesting

```sql
SELECT
    row_start_timestamp,
    home_score,
    away_score,
    period,
    clock_display,
    situation
FROM game_states
WHERE espn_event_id = '401547417'
ORDER BY row_start_timestamp;
```

### Get Team's Recent Games

```sql
SELECT
    gs.game_date,
    CASE
        WHEN gs.home_team_id = 1 THEN ta.team_code
        ELSE th.team_code
    END AS opponent,
    CASE
        WHEN gs.home_team_id = 1 THEN gs.home_score
        ELSE gs.away_score
    END AS team_score,
    CASE
        WHEN gs.home_team_id = 1 THEN gs.away_score
        ELSE gs.home_score
    END AS opp_score,
    gs.game_status
FROM game_states gs
JOIN teams th ON gs.home_team_id = th.team_id
JOIN teams ta ON gs.away_team_id = ta.team_id
WHERE gs.row_current_ind = TRUE
  AND (gs.home_team_id = 1 OR gs.away_team_id = 1)
  AND gs.game_status = 'final'
ORDER BY gs.game_date DESC
LIMIT 10;
```

### Get Current AP Poll Rankings

```sql
SELECT
    tr.rank,
    t.team_name,
    t.team_code,
    tr.points,
    tr.first_place_votes,
    tr.previous_rank
FROM team_rankings tr
JOIN teams t ON tr.team_id = t.team_id
WHERE tr.ranking_type = 'ap_poll'
  AND tr.season = 2024
  AND tr.week = (
      SELECT MAX(week) FROM team_rankings
      WHERE ranking_type = 'ap_poll' AND season = 2024
  )
ORDER BY tr.rank;
```

---

## Data Pipeline Integration

### ESPN API Client Usage

```python
from precog.api_connectors.espn_client import ESPNClient

client = ESPNClient()

# Get scoreboard for any supported league
nfl_games = client.get_scoreboard("nfl")
nba_games = client.get_scoreboard("nba")
ncaaf_games = client.get_scoreboard("ncaaf")

# Process games
for game in nfl_games:
    print(f"{game['home_team']} vs {game['away_team']}")
```

### Full Pipeline Example

```python
from precog.api_connectors.espn_client import ESPNClient
from precog.database.crud_operations import (
    create_venue,
    upsert_game_state,
    get_venue_by_espn_id
)

def sync_espn_games(league: str = "nfl"):
    """Sync live game data from ESPN to database."""
    client = ESPNClient()
    games = client.get_scoreboard(league)

    for game in games:
        # 1. Upsert venue
        venue = game.get("venue", {})
        if venue.get("espn_venue_id"):
            venue_id = create_venue(
                espn_venue_id=venue["espn_venue_id"],
                venue_name=venue.get("venue_name", "Unknown"),
                city=venue.get("city"),
                state=venue.get("state"),
                capacity=venue.get("capacity"),
                indoor=venue.get("indoor", False)
            )
        else:
            venue_id = None

        # 2. Upsert game state
        upsert_game_state(
            espn_event_id=game["espn_event_id"],
            home_team_id=game.get("home_team_id"),
            away_team_id=game.get("away_team_id"),
            venue_id=venue_id,
            home_score=game.get("home_score", 0),
            away_score=game.get("away_score", 0),
            period=game.get("period", 0),
            clock_display=game.get("clock_display"),
            game_status=game.get("game_status", "pre"),
            league=league,
            situation=game.get("situation")
        )
```

---

## Storage Estimates

### Annual Data Volume

| Sport | Games/Year | Updates/Game | Total Records |
|-------|------------|--------------|---------------|
| NFL | 285 | 150 | 42,750 |
| NCAAF | 800 | 150 | 120,000 |
| NBA | 1,350 | 200 | 270,000 |
| NCAAB | 5,500 | 200 | 1,100,000 |
| NHL | 1,350 | 180 | 243,000 |
| WNBA | 200 | 200 | 40,000 |
| **Total** | **9,485** | - | **~1.8M** |

### Storage Projections

| Table | Row Size | Records/Year | Storage |
|-------|----------|--------------|---------|
| game_states | ~500 bytes | 1,815,750 | ~900 MB |
| venues | ~200 bytes | ~150 | <1 MB |
| teams | ~200 bytes | ~2,000 | <1 MB |
| team_rankings | ~100 bytes | ~50,000 | ~5 MB |
| **Total (with indexes)** | - | - | **~1.1 GB/year** |

---

## References

### ADRs
- **ADR-029:** ESPN Data Model with Normalized Schema
- **ADR-002:** Decimal Precision for All Financial Values
- **ADR-018:** SCD Type 2 for Historical Versioning

### Requirements
- **REQ-DATA-001:** Game State Data Collection (SCD Type 2)
- **REQ-DATA-002:** Venue Data Management
- **REQ-DATA-003:** Team Record Tracking
- **REQ-DATA-004:** Team Rankings Storage (Temporal Validity)
- **REQ-DATA-005:** Multi-Sport Support

### Source Code
- `src/precog/api_connectors/espn_client.py` - ESPN API client with TypedDicts
- `src/precog/database/crud_operations.py` - CRUD operations (lines 1822-2429)
- `src/precog/database/migrations/011_create_venues_table.sql`
- `src/precog/database/migrations/012_create_team_rankings_table.sql`
- `src/precog/database/migrations/013_enhance_teams_table.sql`
- `src/precog/database/migrations/014_create_game_states_table.sql`

### Database Documentation
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.12.md` - Section 10: Live Sports Data
- `docs/database/DATABASE_TABLES_REFERENCE.md` - Quick table reference

---

**Document History:**
- V1.0 (2025-11-27): Initial guide created for Phase 2 Live Data Integration
