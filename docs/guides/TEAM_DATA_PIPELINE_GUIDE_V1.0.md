# Team Data Pipeline Guide V1.0

**Version:** 1.0
**Date:** 2026-03-30
**Status:** Current (Session 31)
**Related ADRs:** ADR-111 (Sport-Specific Team Code Mappings), ADR-114 (External Data Source Architecture)

## Overview

The team data pipeline is the backbone of Precog's cross-platform matching system. It
answers the question: "Which real-world game does this Kalshi market refer to?" The
pipeline populates teams from ESPN seed data, classifies them by division (FBS/FCS/D2/D3),
maps their codes across platforms (ESPN, Kalshi, future sources), caches those mappings in
memory for fast lookup, and uses them to link Kalshi events to ESPN games via ticker parsing.

## Architecture Overview

```
  +------------------+     +------------------+     +-------------------+
  | Data Sources     |     | Team Population  |     | Classification    |
  | - ESPN (Tier A)  |---->| - SQL seed files |---->| - CFBD (ncaaf)    |
  | - CFBD (Tier B)  |     | - teams table    |     | - Manual (ncaab)  |
  | - Kalshi tickers |     +--------+---------+     | - Pro leagues auto|
  +------------------+              |               +--------+----------+
                                    v                        |
                          +-------------------+              |
                          | External Codes    |<-------------+
                          | - external_team_  |
                          |   codes table     |
                          | - (source, code,  |
                          |    league) UNIQUE  |
                          +--------+----------+
                                   |
                                   v
                          +-------------------+
                          | Registry (Memory) |
                          | - TeamCodeRegistry|
                          | - O(1) lookups    |
                          +--------+----------+
                                   |
                                   v
                          +-------------------+     +------------------+
                          | Event Matching    |---->| games table      |
                          | - Ticker parsing  |     | - events.game_id |
                          | - Code resolution |     +------------------+
                          | - Game lookup     |
                          +-------------------+
```

## 1. Team Population

### Sources

**ESPN (primary):** Teams are seeded via SQL files in `src/precog/database/seeds/`.
Each league has its own seed file:

| File | League | Count | Contents |
|------|--------|-------|----------|
| `001_nfl_teams_initial_elo.sql` | NFL | 32 | team_code, name, sport, initial Elo, conference, division |
| `002_nfl_teams_espn_update.sql` | NFL | -- | Adds display_name, espn_team_id, league to existing rows |
| `003_nba_teams.sql` | NBA | 30 | Full team data with ESPN IDs |
| `004_nhl_teams.sql` | NHL | 32 | Full team data with ESPN IDs |
| `005_wnba_teams.sql` | WNBA | 12 | Full team data with ESPN IDs |
| `006_ncaaf_teams.sql` | NCAAF | 79 | Power 5 + Group of 5 conferences |
| `007_ncaab_teams.sql` | NCAAB | 89 | Power conferences + mid-majors |
| `008_ncaaw_teams.sql` | NCAAW | -- | Women's basketball |
| `009_mlb_teams.sql` | MLB | -- | Major League Baseball |
| `010_mls_teams.sql` | MLS | -- | Major League Soccer |
| `011_kalshi_teams_code_mapping.sql` | Multi | -- | Sets kalshi_team_code where it differs from team_code |

Seeds are applied via `scripts/seed_multi_sport_teams.py`, which wraps `psql` calls
for idempotent execution. Duplicate-key errors are treated as success.

**Kalshi code overrides (seed 011):** Only teams where Kalshi uses a different code
than ESPN get an explicit `kalshi_team_code`:

```sql
-- Jacksonville: Kalshi uses JAC, ESPN uses JAX
UPDATE teams SET kalshi_team_code = 'JAC'
WHERE team_code = 'JAX' AND league = 'nfl';

-- LA Rams: Kalshi uses LA, ESPN uses LAR
UPDATE teams SET kalshi_team_code = 'LA'
WHERE team_code = 'LAR' AND league = 'nfl';
```

For the ~95% of teams where Kalshi and ESPN codes match, `kalshi_team_code` is NULL
and the matching module uses `team_code` as the Kalshi code.

### Schema: teams Table

```sql
-- Core columns (migration 010):
team_id       SERIAL PRIMARY KEY,
team_code     VARCHAR(10) NOT NULL,     -- ESPN canonical code (e.g., "JAX")
team_name     VARCHAR(100) NOT NULL,    -- Full name ("Jacksonville Jaguars")
sport         VARCHAR(20) NOT NULL,     -- "football", "basketball", "hockey"
current_elo_rating DECIMAL(10,4),
conference    VARCHAR(50),
division      VARCHAR(50),

-- Enhancement columns (migration 013):
display_name  VARCHAR(100),             -- Short name ("Jaguars")
league        VARCHAR(20),              -- "nfl", "ncaaf", "nba", etc.
espn_team_id  VARCHAR(20),             -- ESPN's unique team ID (per-league)

-- Matching columns (migrations 0041, 0042):
kalshi_team_code VARCHAR(10),          -- Only set when Kalshi differs from ESPN
classification   VARCHAR(20),          -- "fbs", "fcs", "d2", "d3", "professional", NULL
```

**Key distinction:** `team_id` is the surrogate PK (SERIAL). `team_code` + `league`
is the effective business key for lookups. ESPN team IDs are unique per-league but
NOT globally unique (team ID "1" may exist in both NFL and NBA).

## 2. Team Classification

### What Classification Means

Classification identifies a team's competitive division. It matters for two reasons:

1. **Collision resolution:** In college sports, multiple teams share the same
   abbreviation across divisions. "ALA" could be Alabama (FBS) or Alabama A&M (FCS).
   Kalshi only trades FBS/FCS games, so the higher-division team wins collisions.

2. **Market filtering:** Classification enables future filtering of which teams
   are tradeable on prediction markets.

**Valid values:** `fbs`, `fcs`, `d2`, `d3`, `d1`, `professional`, `NULL`.

### Sources

**CFBD Adapter (NCAAF):** The `CFBDSource` class in
`src/precog/database/seeding/sources/sports/cfbd_adapter.py` fetches classification
from the College Football Data API:

```python
# CFBD API returns "ii" and "iii" for Division II/III.
# We normalize to our schema values:
CFBD_CLASSIFICATION_MAP = {
    "fbs": "fbs",   # ~130 teams
    "fcs": "fcs",   # ~130 teams
    "ii":  "d2",    # ~170 teams
    "iii": "d3",    # ~240 teams
}
```

Usage: `CFBDSource().get_team_classifications()` calls `GET /teams` on the CFBD API
with Bearer token auth (env var: `CFBD_API_KEY`).

**Professional leagues (migration 0042):** Pro leagues are auto-classified:

```sql
UPDATE teams SET classification = 'professional'
WHERE league IN ('nfl', 'nba', 'nhl', 'mlb', 'wnba', 'mls')
```

**Manual classification (NCAAB/NCAAW):** Basketball teams classified as `d1` via
manual update. No external API source yet.

**Planned: CBBD (#489):** College Basketball Data (CBBD) will provide NCAAB
classification and historical game data, similar to CFBD for football.

### Priority System

When two teams share the same code within a league, the `CLASSIFICATION_PRIORITY`
dict in `team_code_registry.py` determines the winner:

```python
CLASSIFICATION_PRIORITY: dict[str | None, int] = {
    "fbs": 5,            # Highest: FBS is what Kalshi trades
    "fcs": 4,
    "professional": 3,
    "d1": 2,
    "d2": 1,
    "d3": 1,
    None: 0,             # Lowest: unclassified teams always lose
}
```

This matters in the legacy load path (from `teams` table). When loading from
`external_team_codes`, collisions are impossible because of the UNIQUE constraint
on `(source, source_team_code, league)`.

## 3. External Team Codes

### Purpose

The `external_team_codes` table (migration 0045, #516) provides persistent,
multi-source, auditable team code mappings. It replaces the fragile approach of
relying solely on `teams.kalshi_team_code` and in-memory collision resolution.

**Why a separate table:**
- **Multi-source:** Maps codes from Kalshi, ESPN, Polymarket, CFBD, Odds API --
  all in one place with a uniform schema.
- **Auditable:** `confidence` and `notes` columns track how each mapping was
  established and whether it has been verified.
- **No collisions by design:** The UNIQUE constraint on `(source, source_team_code,
  league)` guarantees each platform code maps to exactly one team per league.

### Schema

```sql
CREATE TABLE external_team_codes (
    id                SERIAL PRIMARY KEY,
    team_id           INTEGER NOT NULL REFERENCES teams(team_id),
    source            VARCHAR(30) NOT NULL,   -- 'kalshi', 'espn', 'polymarket', etc.
    source_team_code  VARCHAR(30) NOT NULL,   -- Code on that platform
    league            VARCHAR(20) NOT NULL,   -- 'nfl', 'ncaaf', etc.
    confidence        VARCHAR(20) NOT NULL DEFAULT 'heuristic',
    verified_at       TIMESTAMP WITH TIME ZONE,
    notes             TEXT,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (source, source_team_code, league)
);

-- Indexes:
CREATE INDEX idx_external_team_codes_team   ON external_team_codes(team_id);
CREATE INDEX idx_external_team_codes_source ON external_team_codes(source, league);
```

**Confidence levels:**
- `exact` -- Verified by API response or manual human check.
- `manual` -- Set by a human operator, not independently verified.
- `heuristic` -- Inferred (e.g., assuming Kalshi code = ESPN code for the ~95% that match).

### Seeding

The script `scripts/seed_external_team_codes.py` populates the table from existing
`teams` data. It creates three categories of rows:

1. `source='kalshi', confidence='manual'` -- Teams with explicit `kalshi_team_code`
   (e.g., JAX has kalshi_team_code='JAC').
2. `source='kalshi', confidence='heuristic'` -- Teams without `kalshi_team_code`
   where the Kalshi code is assumed to match `team_code`.
3. `source='espn', confidence='exact'` -- Every team gets an ESPN entry using
   `team_code`, since that IS the ESPN code.

```bash
# Seed all leagues
python scripts/seed_external_team_codes.py

# Dry run
python scripts/seed_external_team_codes.py --dry-run

# Single league
python scripts/seed_external_team_codes.py --league nfl
```

Uses `upsert_external_team_code()` for idempotency -- safe to run repeatedly.

### CRUD Operations

Key functions in `src/precog/database/crud_operations.py`:

| Function | Purpose |
|----------|---------|
| `create_external_team_code()` | Insert a new mapping (raises on conflict) |
| `upsert_external_team_code()` | Insert or update (idempotent, ON CONFLICT) |
| `get_external_team_codes()` | Query with optional source/league/team_id filters |
| `find_team_by_external_code()` | Resolve (source, code, league) to full team row |
| `delete_external_team_code()` | Delete by PK |

## 4. Team Code Registry

### Purpose

`TeamCodeRegistry` (in `src/precog/matching/team_code_registry.py`) is an in-memory
cache providing O(1) team code lookups during polling. Without it, each event match
would require a ~100ms database round-trip. The registry loads all codes in one query
(~5ms) at poller startup.

### Load Strategies

The `load()` method attempts two strategies in order:

1. **Primary: `_try_load_from_external_codes()`** -- Reads from `external_team_codes`
   table. Gets all Kalshi codes, cross-references ESPN codes by `team_id`, and builds
   the Kalshi-to-ESPN mapping. Collisions are impossible due to the UNIQUE constraint.

2. **Fallback: `_load_from_teams_table()`** -- Legacy mode. Reads from `teams` table
   using `get_teams_with_kalshi_codes()`. Used when `external_team_codes` is empty,
   doesn't exist (pre-migration 0045), or encounters an error. Requires
   classification-based collision resolution.

3. **Testing: `load_from_data()`** -- Accepts a list of team dicts directly.
   No database required.

```python
# Production startup
registry = TeamCodeRegistry()
registry.load()  # Tries external_team_codes, falls back to teams table

# Test setup
registry = TeamCodeRegistry()
registry.load_from_data([
    {"team_code": "JAX", "league": "nfl", "kalshi_team_code": "JAC"},
    {"team_code": "KC",  "league": "nfl", "kalshi_team_code": None},
])
```

### Collision Resolution

When loading from the legacy `teams` table, `_build_cache()` handles duplicate codes:

1. For each team, determine the effective Kalshi code (explicit `kalshi_team_code` or
   `team_code` if NULL).
2. If that code already exists in the cache for the same league, compare
   `CLASSIFICATION_PRIORITY`.
3. Higher priority wins. FBS (5) beats FCS (4), which beats unclassified (0).
4. Collisions are logged at DEBUG level with a summary count at INFO.

When loading from `external_team_codes`, collisions cannot occur because each
`(source, source_team_code, league)` combination is unique by constraint.

### Public API

```python
# Resolve a Kalshi code to ESPN canonical code
espn_code = registry.resolve_kalshi_to_espn("JAC", "nfl")  # Returns "JAX"
espn_code = registry.resolve_kalshi_to_espn("HOU", "nfl")  # Returns "HOU"
espn_code = registry.resolve_kalshi_to_espn("ZZZ", "nfl")  # Returns None

# Get all valid Kalshi codes for ticker splitting
codes = registry.get_kalshi_codes("nfl")  # {"JAC", "HOU", "NE", "LA", ...}

# Check if refresh is needed (age > 1hr or unknown codes accumulated)
if registry.needs_refresh():
    registry.load()

# Record an unknown code for monitoring
registry.record_unknown_code("ZZZ", "nfl")  # Adds "ZZZ:nfl" to tracking set
```

## 5. Event-Game Matching

### Ticker Parsing

Kalshi event tickers encode league, date, and matchup in a fixed format:

```
Format:  {SERIES}-{YY}{MON}{DD}{AWAY}{HOME}
Example: KXNFLGAME-26JAN18HOUNE
         |          |  |  | |  |
         series     YY MON DD teams (concatenated, no delimiter)
```

The parser (`src/precog/matching/ticker_parser.py`) extracts:

1. **League** from the series prefix using pattern matching:

   | Pattern | League | Example Series |
   |---------|--------|---------------|
   | NCAAF | ncaaf | KXNCAAFGAME |
   | NCAAB | ncaab | KXNCAABGAME |
   | NFL | nfl | KXNFLGAME |
   | NBA | nba | KXNBAGAME |
   | NHL | nhl | KXNHLGAME |
   | MLB | mlb | KXMLBGAME |

   Order matters: NCAAF is checked before NFL, NCAAB before NBA (longer match first).

2. **Game date** from `YYMONDD` (e.g., `26JAN18` = 2026-01-18).

3. **Team codes** by splitting the remaining string (e.g., `HOUNE`) at every possible
   position and checking both halves against the set of valid codes from the registry:

```python
# "HOUNE" with valid codes {"HOU", "NE", "KC", "BUF", ...}
# Try split at 2: "HO" + "UNE" -- neither valid
# Try split at 3: "HOU" + "NE" -- both valid -> ("HOU", "NE")
```

If zero or multiple valid splits exist, the parse fails. The `ParsedTicker` dataclass
holds all extracted fields:

```python
@dataclass(frozen=True)
class ParsedTicker:
    series: str           # "KXNFLGAME"
    league: str           # "nfl"
    game_date: date       # date(2026, 1, 18)
    away_team_code: str   # "HOU" (Kalshi code)
    home_team_code: str   # "NE"  (Kalshi code)
```

### Matching Flow

`EventGameMatcher` (in `src/precog/matching/event_game_matcher.py`) orchestrates
the full flow:

```
Event ticker
    |
    v
Phase 1: Ticker parsing
    |-- Extract league from series prefix
    |-- Get valid codes: registry.get_kalshi_codes(league)
    |-- Parse date + split team codes
    |-- Resolve: registry.resolve_kalshi_to_espn(code, league)
    |-- Map league to sport: LEAGUE_SPORT_CATEGORY["nfl"] = "football"
    |-- Query: find_game_by_matchup(sport, date, home, away)
    |-- Returns games.id or None
    |
    v (if Phase 1 fails)
Phase 2: Title-based fallback (stub -- not yet implemented)
    |-- Parse team names from event title
    |-- TODO: Issue #462
    |
    v
Result: (game_id, MatchReason)
```

**LEAGUE_SPORT_CATEGORY mapping** (used in game lookup):

```python
LEAGUE_SPORT_CATEGORY = {
    "nfl": "football", "ncaaf": "football",
    "nba": "basketball", "ncaab": "basketball",
    "wnba": "basketball", "ncaaw": "basketball",
    "nhl": "hockey", "mlb": "baseball", "mls": "soccer",
}
```

The games table natural key is `(sport, game_date, home_team_code, away_team_code)`,
so the matcher maps from Kalshi's league-level codes to the games table's sport-level
codes.

### Batch Backfill

`backfill_unlinked_events()` queries for events where `game_id IS NULL` and
`category = 'sports'`, then attempts ticker-based matching for each:

```python
matcher = EventGameMatcher()
matcher.registry.load()
linked = matcher.backfill_unlinked_events("nfl")
# "Backfill complete: 12/50 events linked (league=nfl)"
```

### Match Reasons

The `MatchReason` enum categorizes outcomes for monitoring:

| Reason | Meaning |
|--------|---------|
| `MATCHED` | Successfully linked event to a game |
| `PARSE_FAIL` | Ticker could not be parsed (non-sports, bad format) |
| `NO_CODE` | Parsed ticker but team code(s) not in registry |
| `NO_GAME` | Resolved codes but no matching game found in DB |

Unknown codes are automatically tracked via `registry.record_unknown_code()`,
feeding into `needs_refresh()` for self-healing.

### Current Coverage

| League | Match Rate | Root Cause |
|--------|-----------|------------|
| NBA/NHL | ~1.5% | Games table only has soak-period data (started 2026-03-26) |
| NFL/NCAAF | 0% | Season ended before soak test began |
| NCAAB | ~1.5% | Same temporal limitation as NBA/NHL |
| MLB | 0% | Season not started; limited seed data |

The low match rates are not a code bug. They reflect that the `games` table only
contains games from the soak test period onward. Historical backfill (#524) will
address this.

## 6. Data Sources & Integration

### Current (Implemented)

| Source | Tier | Data Provided | Code Location |
|--------|------|--------------|---------------|
| ESPN | A (Continuous) | Live games, teams, scores, venues | `api_connectors/espn_client.py` + `schedulers/espn_game_poller.py` |
| CFBD | B (Periodic) | NCAAF team classification | `database/seeding/sources/sports/cfbd_adapter.py` |
| Kalshi | A (Continuous) | Market events with team codes in tickers | `api_connectors/kalshi_client.py` + `schedulers/kalshi_poller.py` |

### Planned

| Source | Tier | Issue | Data Provided |
|--------|------|-------|--------------|
| CBBD | B | #489 | NCAAB classification + historical games |
| ESPN backfill | C | #524 | Historical games via date iteration |
| Polymarket | A | #495 | Additional market team codes (needs `external_team_codes`) |
| The Odds API | A | #451 | Sportsbook odds |
| pybaseball | C | #502 | MLB data |

### ADR-114 Tier Model

ADR-114 classifies data sources by update cadence:

- **Tier A (Continuous):** Seconds to minutes. Lives in `api_connectors/` + `schedulers/`.
  Full production-readiness: monitoring, maintenance, logging, reporting, self-healing,
  scheduling.
- **Tier B (Periodic):** Daily to weekly. Lives in `database/seeding/sources/`.
  Monitoring + Reporting + CLI.
- **Tier C (Batch):** One-time or seasonal. Lives in `database/seeding/sources/`.
  Logging only.

## 7. How Games Enter the Database

The ESPN game poller (`ESPNGamePoller`) is the primary path for live game data:

1. Polls ESPN scoreboard API per league (NFL, NCAAF, NBA, NHL).
2. For each game, looks up `home_team_id` and `away_team_id` via
   `get_team_by_espn_id(espn_team_id, league)`.
3. Calls `get_or_create_game()` with the natural key
   `(sport, game_date, home_team_code, away_team_code)`.
4. Calls `upsert_game_state()` for SCD Type 2 score tracking.
5. On game completion, calls `update_game_result()` to set final scores.

The games table row is what `find_game_by_matchup()` queries when the matcher
tries to link a Kalshi event to a game. If the game hasn't been polled yet
(ESPN hasn't returned it on a scoreboard), it won't exist in `games` and the
match will return `NO_GAME`.

## 8. Phase 2 Direction: Decoupled Team Resolution

### Current Limitation

Today, team resolution depends on the `games` table. The matcher can only identify
teams by finding a matching game -- it cannot assign `team_id` values to events
independently. This means events for games not yet in our database remain unlinked.

### Target Architecture

1. **Teams as canonical entity:** Populated from all sources (ESPN, CFBD, Kalshi
   market discovery).
2. **External team codes as mapping layer:** `external_team_codes` maps any
   platform's code to `team_id`.
3. **Events get team_ids immediately:** Parse ticker, resolve codes to team_ids via
   `external_team_codes`, set `home_team_id` and `away_team_id` on the event
   directly. The `game_id` FK becomes a bonus linkage, not a requirement.
4. **Auto-register new codes:** When a Kalshi ticker contains an unknown code,
   attempt to match it to an existing team and create an `external_team_codes` row
   automatically.

### Schema Changes Needed

```sql
-- Add team FKs directly to events (not yet implemented)
ALTER TABLE events ADD COLUMN home_team_id INTEGER REFERENCES teams(team_id);
ALTER TABLE events ADD COLUMN away_team_id INTEGER REFERENCES teams(team_id);
```

### Migration Path (6 Steps)

1. Add `home_team_id` / `away_team_id` to `events` table (migration).
2. Update Kalshi poller to resolve team codes at ingest time.
3. Backfill existing events from parsed tickers.
4. Update matching to set `game_id` as a secondary linkage.
5. Build auto-registration flow for unknown Kalshi codes.
6. Extend to Polymarket and other future sources.

## Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `src/precog/matching/team_code_registry.py` | In-memory cache of team code mappings |
| `src/precog/matching/event_game_matcher.py` | Orchestrates event-to-game matching |
| `src/precog/matching/ticker_parser.py` | Parses Kalshi tickers into structured data |
| `src/precog/database/crud_operations.py` | All team/game/external code CRUD |
| `src/precog/database/seeding/sources/sports/cfbd_adapter.py` | CFBD classification source |
| `src/precog/schedulers/espn_game_poller.py` | ESPN live game polling |
| `src/precog/database/seeds/011_kalshi_teams_code_mapping.sql` | Kalshi code overrides |
| `src/precog/database/alembic/versions/0045_create_external_team_codes.py` | External codes migration |
| `scripts/seed_external_team_codes.py` | Seed external_team_codes from teams data |
| `scripts/seed_multi_sport_teams.py` | Multi-sport team seeding orchestrator |

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `TeamCodeRegistry.load()` | team_code_registry.py | Load codes (external first, teams fallback) |
| `TeamCodeRegistry.resolve_kalshi_to_espn()` | team_code_registry.py | Kalshi code -> ESPN code |
| `TeamCodeRegistry.get_kalshi_codes()` | team_code_registry.py | All valid Kalshi codes for a league |
| `parse_event_ticker()` | ticker_parser.py | Parse ticker into ParsedTicker |
| `split_team_codes()` | ticker_parser.py | Split concatenated codes using valid set |
| `EventGameMatcher.match_event()` | event_game_matcher.py | Full match: ticker -> game_id |
| `EventGameMatcher.backfill_unlinked_events()` | event_game_matcher.py | Batch match unlinked events |
| `find_game_by_matchup()` | crud_operations.py | Query games by natural key |
| `get_teams_with_kalshi_codes()` | crud_operations.py | Legacy registry data source |
| `upsert_external_team_code()` | crud_operations.py | Idempotent external code write |
| `find_team_by_external_code()` | crud_operations.py | Resolve external code to team |
| `get_team_by_espn_id()` | crud_operations.py | Look up team by ESPN ID + league |
| `CFBDSource.get_team_classifications()` | cfbd_adapter.py | Fetch NCAAF classifications |

### Key Issues

| Issue | Description | Status |
|-------|-------------|--------|
| #462 | Event-to-game matching (original epic) | Implemented (Phase 1) |
| #486 | Team code collision fix + classification | Implemented |
| #489 | CBBD integration (NCAAB classification + games) | Planned (Phase 2) |
| #495 | Polymarket integration (needs external_team_codes) | Planned (Phase 2) |
| #496 | Cross-platform event matching | Planned (Phase 2) |
| #502 | MLB enablement | Planned (Phase 2) |
| #513 | Kalshi API enrichment (P0+P1 fields) | In progress |
| #516 | External team codes table | Implemented (Session 31) |
| #518 | ESPN situation parser audit | Planned |
| #524 | ESPN historical backfill | Planned |

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 1.0 | 2026-03-30 | Initial creation (session 31) |
