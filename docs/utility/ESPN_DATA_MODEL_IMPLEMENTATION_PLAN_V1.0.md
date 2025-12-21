# ESPN Data Model Implementation Plan

---
**Version:** 1.0
**Created:** 2025-11-27
**Last Updated:** 2025-11-27
**Status:** In Progress
**Phase:** 2 (Live Data Integration)
**Related ADR:** ADR-029 (ESPN Data Model with Normalized Schema)
**Related Requirements:** REQ-DATA-001 through REQ-DATA-005 (to be created)
---

## Executive Summary

This document captures the implementation plan for Phase 2 ESPN data model enhancements, including:
- **Normalized database schema** for multi-sport ESPN data
- **TypedDict refactoring** for compile-time type safety
- **Multi-sport support** for NFL, NCAAF, NBA, NCAAB, NHL, WNBA
- **SCD Type 2 versioning** for complete game state history
- **JSONB situation fields** for sport-specific data without schema explosion

**Storage Estimate:** ~1.1 GB/year for all 6 sports (~9,500 games, ~1.8M game state records)

---

## Implementation Phases

### Phase A: TypedDict Refactoring (COMPLETE)
**Status:** ✅ Complete (2025-11-27)
**Duration:** 1 day

**Deliverables:**
- [x] Added 6 new TypedDicts to `src/precog/api_connectors/espn_client.py`:
  - `ESPNTeamInfo` - Static team data (ID, name, record)
  - `ESPNVenueInfo` - Static venue data (ID, name, capacity)
  - `ESPNGameMetadata` - Static game data (date, teams, venue, broadcast)
  - `ESPNSituationData` - Sport-specific JSONB (downs, fouls, power plays)
  - `ESPNGameState` - Dynamic state (score, period, clock, situation)
  - `ESPNGameFull` - Combined metadata + state
- [x] Maintained `GameState` as backward-compatible alias
- [x] All 44 ESPN client tests passing
- [x] 92.27% coverage maintained

### Phase E: Multi-Sport Endpoints (COMPLETE)
**Status:** ✅ Complete (2025-11-27)
**Duration:** 1 day

**Deliverables:**
- [x] Added NBA endpoint: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- [x] Added NCAAB endpoint: `https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`
- [x] Added NHL endpoint: `https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard`
- [x] Added WNBA endpoint: `https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard`
- [x] Added generic `get_scoreboard(league)` method for sport-agnostic pipelines
- [x] All 44 tests passing

### Phase B: Database Migrations (COMPLETE)
**Status:** ✅ Complete (2025-11-29)
**Duration:** 1 day
**Dependencies:** Phase A complete

**Deliverables:**
- [x] Migration 026: Create `venues` table
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

- [x] Migration 027: Create `team_rankings` table
  ```sql
  CREATE TABLE team_rankings (
      ranking_id SERIAL PRIMARY KEY,
      team_id INTEGER REFERENCES teams(team_id),
      ranking_type VARCHAR(50) NOT NULL,  -- 'ap_poll', 'cfp', 'coaches_poll', 'espn_power', 'espn_fpi'
      rank INTEGER NOT NULL,
      season INTEGER NOT NULL,
      week INTEGER,  -- NULL for preseason (week 0) and final rankings
      ranking_date DATE NOT NULL,
      points INTEGER,  -- For AP/Coaches polls
      first_place_votes INTEGER,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
      UNIQUE (team_id, ranking_type, season, week)
  );
  ```

- [x] Migration 028: Enhance `teams` table
  ```sql
  ALTER TABLE teams ADD COLUMN IF NOT EXISTS espn_team_id VARCHAR(50);
  ALTER TABLE teams ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
  ALTER TABLE teams ADD COLUMN IF NOT EXISTS conference VARCHAR(100);
  ALTER TABLE teams ADD COLUMN IF NOT EXISTS division VARCHAR(100);
  ALTER TABLE teams ADD COLUMN IF NOT EXISTS sport VARCHAR(20) DEFAULT 'nfl';
  ALTER TABLE teams ADD COLUMN IF NOT EXISTS league VARCHAR(20) DEFAULT 'nfl';
  CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_espn_id ON teams(espn_team_id);
  ```

- [x] Migration 029: Create `game_states` table (SCD Type 2)
  ```sql
  CREATE TABLE game_states (
      game_state_id SERIAL PRIMARY KEY,
      espn_event_id VARCHAR(50) NOT NULL,
      home_team_id INTEGER REFERENCES teams(team_id),
      away_team_id INTEGER REFERENCES teams(team_id),
      venue_id INTEGER REFERENCES venues(venue_id),
      home_score INTEGER NOT NULL DEFAULT 0,
      away_score INTEGER NOT NULL DEFAULT 0,
      period INTEGER NOT NULL DEFAULT 0,
      clock_seconds DECIMAL(10,2),
      clock_display VARCHAR(20),
      game_status VARCHAR(50) NOT NULL,  -- 'pre', 'in_progress', 'halftime', 'final', 'delayed', 'postponed'
      game_date TIMESTAMP WITH TIME ZONE,
      broadcast VARCHAR(100),
      neutral_site BOOLEAN DEFAULT FALSE,
      season_type VARCHAR(20),  -- 'preseason', 'regular', 'playoff', 'bowl', 'allstar'
      week_number INTEGER,
      situation JSONB,  -- Sport-specific data (downs, fouls, power plays)
      linescores JSONB,  -- Period-by-period scores
      data_source VARCHAR(50) DEFAULT 'espn',
      -- SCD Type 2 fields
      row_start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
      row_end_timestamp TIMESTAMP WITH TIME ZONE,
      row_current_ind BOOLEAN DEFAULT TRUE,
      CONSTRAINT game_states_one_current UNIQUE (espn_event_id, row_current_ind) WHERE row_current_ind = TRUE
  );

  -- Indexes for common queries
  CREATE INDEX idx_game_states_event ON game_states(espn_event_id);
  CREATE INDEX idx_game_states_current ON game_states(espn_event_id) WHERE row_current_ind = TRUE;
  CREATE INDEX idx_game_states_date ON game_states(game_date);
  CREATE INDEX idx_game_states_status ON game_states(game_status);
  CREATE INDEX idx_game_states_situation ON game_states USING GIN (situation);
  ```

### Phase C: CRUD Operations (PENDING)
**Status:** Pending
**Duration:** 2-3 days
**Dependencies:** Phase B complete

**Deliverables:**
- [ ] `create_venue()` - Insert or update venue
- [ ] `get_venue_by_espn_id()` - Lookup venue
- [ ] `upsert_game_state()` - SCD Type 2 insert (creates new version on change)
- [ ] `get_current_game_state()` - Query current state (row_current_ind = TRUE)
- [ ] `get_game_state_history()` - Query all versions for an event
- [ ] `create_team_ranking()` - Insert ranking record
- [ ] `get_team_rankings()` - Query rankings by team, type, season
- [ ] `get_current_rankings()` - Get latest rankings for a type
- [ ] Unit tests for all CRUD operations
- [ ] Integration tests with real database

### Phase D: Documentation (PENDING)
**Status:** Pending
**Duration:** 1 day
**Dependencies:** Phases A-C complete

**Deliverables:**
- [ ] `docs/guides/ESPN_DATA_MODEL_V1.0.md` - Comprehensive guide
- [ ] Update `docs/database/DATABASE_SCHEMA_SUMMARY.md` (current: V1.13)
- [ ] Update `docs/database/DATABASE_TABLES_REFERENCE.md`
- [ ] Update `docs/foundation/MASTER_INDEX_*.md`
- [ ] Update `docs/foundation/DEVELOPMENT_PHASES_*.md` with Phase 2 tasks

### Phase E (Part 2): Team Seeding (PENDING)
**Status:** Pending
**Duration:** 1 day
**Dependencies:** Phase B complete

**Deliverables:**
- [ ] Seed NBA teams (30 teams)
- [ ] Seed NHL teams (32 teams)
- [ ] Seed NCAAB teams (top 100+ Division I teams)
- [ ] Seed WNBA teams (12 teams)
- [ ] Update existing NFL teams with ESPN IDs
- [ ] Update existing NCAAF teams with ESPN IDs

---

## Storage Estimates

### Data Volume (Annual)

| Sport | Games/Year | Updates/Game | Total Records |
|-------|------------|--------------|---------------|
| NFL | 285 | 150 | 42,750 |
| NCAAF | 800 | 150 | 120,000 |
| NBA | 1,350 | 200 | 270,000 |
| NCAAB | 5,500 | 200 | 1,100,000 |
| NHL | 1,350 | 180 | 243,000 |
| WNBA | 200 | 200 | 40,000 |
| **Total** | **9,485** | - | **~1,815,750** |

### Table Storage

| Table | Row Size | Records/Year | Storage |
|-------|----------|--------------|---------|
| game_states | ~500 bytes | 1,815,750 | ~900 MB |
| game_metadata | ~300 bytes | 9,500 | ~3 MB |
| venues | ~200 bytes | ~150 | <1 MB |
| teams | ~200 bytes | ~2,000 | <1 MB |
| team_rankings | ~100 bytes | ~50,000 | ~5 MB |
| **Indexes + Overhead** | +20% | - | ~180 MB |
| **Total** | - | - | **~1.1 GB/year** |

### Growth Projections

- Year 1: 1.1 GB
- Year 5: 5.5 GB
- Year 10: 11 GB

**PostgreSQL free tier (500 MB):** Insufficient
**PostgreSQL paid tier ($5/mo, 8-20 GB):** Covers 7-18 years

---

## JSONB Situation Schema

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
  "possession": null,
  "home_powerplay": true,
  "away_powerplay": false,
  "powerplay_time": "1:45",
  "home_shots": 28,
  "away_shots": 31,
  "home_saves": 30,
  "away_saves": 27
}
```

---

## TypedDict Reference

```python
# src/precog/api_connectors/espn_client.py

class ESPNTeamInfo(TypedDict, total=False):
    """Static team information from ESPN API."""
    espn_team_id: str
    team_code: str           # 'KC', 'BUF'
    team_name: str           # 'Kansas City Chiefs'
    display_name: str        # 'Chiefs'
    record: str              # '10-1'
    home_record: str         # '5-0'
    away_record: str         # '5-1'
    rank: int | None         # College rankings only

class ESPNVenueInfo(TypedDict, total=False):
    """Venue/stadium information from ESPN API."""
    espn_venue_id: str
    venue_name: str
    city: str
    state: str
    capacity: int
    indoor: bool

class ESPNGameMetadata(TypedDict, total=False):
    """Static game information that doesn't change during the game."""
    espn_event_id: str
    game_date: str
    home_team: ESPNTeamInfo
    away_team: ESPNTeamInfo
    venue: ESPNVenueInfo
    broadcast: str
    neutral_site: bool
    season_type: str
    week_number: int | None

class ESPNSituationData(TypedDict, total=False):
    """Sport-specific situation data (stored as JSONB in database)."""
    # Common
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
    # Basketball (NBA/NCAAB)
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

class ESPNGameState(TypedDict, total=False):
    """Dynamic game state that changes during live games."""
    espn_event_id: str
    home_score: int
    away_score: int
    period: int
    clock_seconds: float
    clock_display: str
    game_status: str
    situation: ESPNSituationData
    linescores: list[list[int]]

class ESPNGameFull(TypedDict, total=False):
    """Complete game data combining metadata and current state."""
    metadata: ESPNGameMetadata
    state: ESPNGameState

# Backward compatibility alias
GameState = ESPNGameState
```

---

## Success Criteria

### Phase 2 Completion Requirements

1. **ESPN Client** (✅ Complete)
   - [x] 6 new TypedDicts defined
   - [x] Multi-sport endpoints (NFL, NCAAF, NBA, NCAAB, NHL, WNBA)
   - [x] Generic `get_scoreboard(league)` method
   - [x] 92%+ coverage maintained

2. **Database Schema** (Pending)
   - [ ] Migrations 026-029 created and tested
   - [ ] venues table with unique ESPN IDs
   - [ ] game_states with SCD Type 2 versioning
   - [ ] team_rankings with temporal validity
   - [ ] teams enhanced with multi-sport support

3. **CRUD Operations** (Pending)
   - [ ] All CRUD functions implemented
   - [ ] Unit tests with 85%+ coverage
   - [ ] Integration tests with real database

4. **Documentation** (Pending)
   - [ ] ESPN_DATA_MODEL_V1.0.md guide
   - [ ] DATABASE_SCHEMA_SUMMARY updated
   - [ ] DEVELOPMENT_PHASES updated
   - [ ] ADR-029 documented (✅ Complete)

5. **Data Seeding** (Pending)
   - [ ] NBA, NHL, NCAAB, WNBA teams seeded
   - [ ] Existing NFL/NCAAF teams updated with ESPN IDs

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| ESPN API structure changes | Medium | TypedDict `total=False` allows missing fields |
| JSONB query performance | Low | GIN indexes on situation field |
| Storage growth exceeds estimate | Low | Implement data retention policy (archive >2 years) |
| SCD Type 2 complexity | Medium | Comprehensive integration tests |
| Multi-sport schema conflicts | Low | Generic design with sport column |

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| Week 1 | A, E | TypedDicts, multi-sport endpoints (COMPLETE) |
| Week 2 | B | Database migrations 026-029 |
| Week 3 | C | CRUD operations and tests |
| Week 4 | D, E | Documentation, team seeding |

**Total Duration:** 4 weeks (matching Phase 2 DEVELOPMENT_PHASES timeline)

---

## References

- **ADR-029:** ESPN Data Model with Normalized Schema
- **DEVELOPMENT_PHASES_V1.6.md:** Phase 2 section (lines 954-1099)
- **DATABASE_SCHEMA_SUMMARY_V1.14.md:** Current schema reference
- **src/precog/api_connectors/espn_client.py:** TypedDict implementations
- **TESTING_STRATEGY_V3.3.md:** Test type requirements

---

**Document History:**
- V1.0 (2025-11-27): Initial implementation plan created from Claude plan file
