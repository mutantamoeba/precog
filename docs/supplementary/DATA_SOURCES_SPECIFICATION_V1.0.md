# Data Sources Specification

---
**Version:** 1.0
**Created:** 2025-12-25
**Last Updated:** 2025-12-25
**Purpose:** Comprehensive specification of all external data sources for sports data ingestion
**Related:** ADR-106 (Historical Data Collection), ADR-304 (Elo Computation Architecture), Issue #273
---

## 1. Overview

This document specifies all external data sources available for Precog's sports data infrastructure. It covers:
- Primary data sources with comprehensive datasets
- Data types available from each source
- Library specifications and installation
- Data freshness and update frequencies
- Coverage by sport and time period

## 2. Data Source Tier Classification

### Tier 1: Comprehensive Sources (nflverse-quality)
Full play-by-play, stats, rosters, and advanced metrics.

| Source | Sports | Quality | Maintenance |
|--------|--------|---------|-------------|
| nflreadpy | NFL | Excellent | Active (nflverse) |
| nba_api | NBA, WNBA | Excellent | Active |
| nhl-api-py | NHL | Good | Active |
| pybaseball | MLB | Excellent | Active |

### Tier 2: Game-Level Sources
Game results, schedules, basic stats.

| Source | Sports | Quality | Maintenance |
|--------|--------|---------|-------------|
| cfbd | NCAAF | Good | Active (API) |
| cbbd | NCAAB | Good | Active (API) |
| ESPN API | All | Good | Official (undocumented) |

### Tier 3: Specialized Sources
Specific data types (betting, analytics).

| Source | Data Types | Sports | Maintenance |
|--------|------------|--------|-------------|
| itscalledsoccer | xG, g+ | MLS | Active |
| Kaggle datasets | Historical odds | Various | Static |

---

## 3. NFL Data: nflreadpy

### 3.1 Library Information

| Property | Value |
|----------|-------|
| **Package Name** | nflreadpy |
| **Installation** | `pip install nflreadpy` |
| **GitHub** | https://github.com/nflverse/nflreadpy |
| **Documentation** | https://nflreadpy.nflverse.com/ |
| **Data Backend** | Polars (converts to pandas) |
| **License** | CC-BY 4.0 (FTN: CC-BY-SA 4.0) |
| **Replaces** | nfl_data_py (deprecated Sep 2025) |

### 3.2 Available Datasets (21 Functions)

#### Core Game Data
| Function | Description | Years Available | Elo Relevant |
|----------|-------------|-----------------|--------------|
| `load_pbp()` | Play-by-play data (390+ columns) | 1999-present | Yes (margin analysis) |
| `load_schedules()` | Game schedules and results | 1999-present | **Primary** |
| `load_player_stats()` | Player game/season stats | 2000-present | Yes (QB adjustment) |
| `load_team_stats()` | Team game/season stats | 2000-present | Yes |

#### Roster & Personnel
| Function | Description | Years Available | Use Case |
|----------|-------------|-----------------|----------|
| `load_players()` | Player information | All-time | ID mapping |
| `load_rosters()` | Season rosters | 2000-present | Team composition |
| `load_rosters_weekly()` | Weekly rosters | 2000-present | Injury tracking |
| `load_depth_charts()` | Depth charts | Recent | Starter identification |
| `load_injuries()` | Injury reports | Recent | QB adjustment |

#### Advanced Statistics
| Function | Description | Years Available | Use Case |
|----------|-------------|-----------------|----------|
| `load_nextgen_stats()` | Next Gen Stats (passing/rushing/receiving) | 2016-present | QB valuation |
| `load_snap_counts()` | Snap count records | Recent | Playing time |
| `load_ftn_charting()` | FTN charted data | 2022-present | Advanced analytics |

#### Draft & Contracts
| Function | Description | Years Available | Use Case |
|----------|-------------|-----------------|----------|
| `load_draft_picks()` | NFL draft picks | 1980-present | Historical |
| `load_combine()` | Combine results | 2000-present | Prospect data |
| `load_contracts()` | Contract data (OTC) | Recent | Salary cap |
| `load_trades()` | Trade history | Recent | Roster changes |

#### Fantasy & Officials
| Function | Description | Years Available | Use Case |
|----------|-------------|-----------------|----------|
| `load_officials()` | Game officials | Recent | Reference |
| `load_ff_playerids()` | Fantasy player IDs | N/A | Cross-reference |
| `load_ff_rankings()` | FantasyPros rankings | Current | Fantasy |
| `load_ff_opportunity()` | Expected fantasy points | Recent | Fantasy |
| `load_participation()` | Historical participation | Historical | Analytics |

### 3.3 Example Usage

```python
import nflreadpy as nfl

# Load game schedules for Elo computation
schedules = nfl.load_schedules([2020, 2021, 2022, 2023, 2024])
games_df = schedules.to_pandas()

# Filter to completed games
completed = games_df[games_df['home_score'].notna()]

# Columns available: game_id, season, week, gameday, home_team, away_team,
#                    home_score, away_score, home_rest, away_rest, etc.
```

### 3.4 Data Volume Estimates

| Dataset | Records/Season | Total (2020-2024) |
|---------|---------------|-------------------|
| Games (schedules) | ~285 | ~1,425 |
| Play-by-play | ~45,000 | ~225,000 |
| Player stats | ~2,000 | ~10,000 |

---

## 4. NBA/WNBA Data: nba_api

### 4.1 Library Information

| Property | Value |
|----------|-------|
| **Package Name** | nba_api |
| **Installation** | `pip install nba_api` |
| **GitHub** | https://github.com/swar/nba_api |
| **Documentation** | https://github.com/swar/nba_api/tree/master/docs |
| **Python Version** | 3.10+ |
| **Coverage** | NBA, WNBA, G-League |

### 4.2 Available Endpoints

#### Game Data
| Endpoint | Description | Elo Relevant |
|----------|-------------|--------------|
| `LeagueGameFinder` | Search games by criteria | **Primary** |
| `ScoreboardV2` | Daily scoreboard | Live data |
| `BoxScoreTraditionalV2` | Box scores | Stats |
| `PlayByPlayV2` | Play-by-play | Advanced |

#### Team Data
| Endpoint | Description | Use Case |
|----------|-------------|----------|
| `TeamInfoCommon` | Team information | Reference |
| `TeamGameLog` | Team game history | Elo computation |
| `TeamYearByYearStats` | Historical stats | Analytics |
| `CommonTeamRoster` | Team rosters | Personnel |

#### Player Data
| Endpoint | Description | Use Case |
|----------|-------------|----------|
| `PlayerCareerStats` | Career statistics | Analysis |
| `PlayerGameLog` | Player game log | Performance |
| `CommonPlayerInfo` | Player information | Reference |

### 4.3 Example Usage

```python
from nba_api.stats.endpoints import LeagueGameFinder
from nba_api.stats.static import teams

# Get all games for 2023-24 season
game_finder = LeagueGameFinder(
    season_nullable='2023-24',
    league_id_nullable='00'  # NBA (10 = WNBA)
)
games_df = game_finder.get_data_frames()[0]

# Columns: GAME_DATE, TEAM_ID, MATCHUP, WL, PTS, etc.
```

### 4.4 Data Volume Estimates

| League | Games/Season | Total (2020-2024) |
|--------|--------------|-------------------|
| NBA | ~1,230 | ~6,150 |
| WNBA | ~204 | ~1,020 |

---

## 5. NHL Data: nhl-api-py

### 5.1 Library Information

| Property | Value |
|----------|-------|
| **Package Name** | nhl-api-py |
| **Installation** | `pip install nhl-api-py` |
| **GitHub** | https://github.com/coreyjs/nhl-api-py |
| **API Base** | api-web.nhle.com, api.nhle.com |
| **Python Version** | 3.9+ |
| **Status** | Production/Stable |

### 5.2 Available Modules

| Module | Endpoints | Elo Relevant |
|--------|-----------|--------------|
| `teams` | Team info, rosters, franchise data | Reference |
| `schedule` | Game schedules, weekly schedules | **Primary** |
| `stats` | Player/team statistics, query builder | Analysis |
| `edge` | EDGE data (shot speed, skate speed) | Advanced |

### 5.3 Example Usage

```python
from nhlpy import NHLClient

client = NHLClient()

# Get schedule for date range
schedule = client.schedule.get_schedule(date='2024-01-15')

# Get team stats
stats = client.stats.club_stats_season(team_abbr='TOR')
```

### 5.4 Data Volume Estimates

| Dataset | Games/Season | Total (2020-2024) |
|---------|--------------|-------------------|
| Regular Season | ~1,312 | ~6,560 |
| Playoffs | ~85 | ~425 |

---

## 6. MLB Data: pybaseball

### 6.1 Library Information

| Property | Value |
|----------|-------|
| **Package Name** | pybaseball |
| **Installation** | `pip install pybaseball` |
| **GitHub** | https://github.com/jldbc/pybaseball |
| **Data Sources** | Baseball Reference, FanGraphs, Statcast |
| **Coverage** | MLB (1871-present for some data) |

### 6.2 Available Functions

#### Statcast Data
| Function | Description | Years Available |
|----------|-------------|-----------------|
| `statcast()` | Pitch-level data | 2015-present |
| `statcast_pitcher()` | Pitcher statcast | 2015-present |
| `statcast_batter()` | Batter statcast | 2015-present |

#### Game & Schedule Data
| Function | Description | Elo Relevant |
|----------|-------------|--------------|
| `schedule_and_record()` | Team schedules with results | **Primary** |
| `team_game_logs()` | Team game logs | Yes |
| `standings()` | League standings | Reference |

#### Statistics
| Function | Description | Use Case |
|----------|-------------|----------|
| `batting_stats()` | Batting statistics | Analytics |
| `pitching_stats()` | Pitching statistics | Analytics |
| `team_batting()` | Team batting stats | Analytics |
| `team_pitching()` | Team pitching stats | Analytics |

### 6.3 Example Usage

```python
from pybaseball import schedule_and_record, team_game_logs

# Get Yankees 2023 schedule with results
schedule = schedule_and_record(2023, 'NYY')

# Get game logs
game_logs = team_game_logs(2023, 'NYY')
```

### 6.4 Data Volume Estimates

| Dataset | Games/Season | Total (2020-2024) |
|---------|--------------|-------------------|
| Regular Season | ~2,430 | ~12,150 |
| Postseason | ~40 | ~200 |
| Statcast pitches | ~700,000 | ~3,500,000 |

---

## 7. College Sports Data: cfbd / cbbd

### 7.1 Library Information

| Property | CFBD (Football) | CBBD (Basketball) |
|----------|-----------------|-------------------|
| **Package Name** | cfbd | cbbd |
| **Installation** | `pip install cfbd` | `pip install cbbd` |
| **Website** | collegefootballdata.com | collegebasketballdata.com |
| **API Key** | Required (free tier: 1000/month) | Required |

### 7.2 Available Endpoints (CFBD)

| Endpoint | Description | Elo Relevant |
|----------|-------------|--------------|
| `get_games()` | Game results | **Primary** |
| `get_team_game_stats()` | Team game stats | Analysis |
| `get_plays()` | Play-by-play | Advanced |
| `get_drives()` | Drive data | Analysis |
| `get_rankings()` | AP/Coaches polls | Reference |
| `get_betting_lines()` | Betting lines | Validation |
| `get_recruiting()` | Recruiting data | Long-term |

### 7.3 Example Usage

```python
import cfbd

configuration = cfbd.Configuration()
configuration.api_key['Authorization'] = 'YOUR_API_KEY'

api = cfbd.GamesApi(cfbd.ApiClient(configuration))
games = api.get_games(year=2024, classification='fbs')
```

### 7.4 Data Volume Estimates

| Sport | Games/Season | Total (2020-2024) |
|-------|--------------|-------------------|
| NCAAF (FBS) | ~920 | ~4,600 |
| NCAAB | ~5,600 | ~28,000 |

---

## 8. MLS Data: itscalledsoccer

### 8.1 Library Information

| Property | Value |
|----------|-------|
| **Package Name** | itscalledsoccer |
| **Installation** | `pip install itscalledsoccer` |
| **Provider** | American Soccer Analysis |
| **Coverage** | MLS, NWSL, USL |

### 8.2 Available Data

| Data Type | Description | Use Case |
|-----------|-------------|----------|
| xG (Expected Goals) | Shot quality metric | Advanced |
| g+ (Goals Added) | Player contribution | Analytics |
| Team stats | Season/game stats | Elo computation |
| Player stats | Individual performance | Analysis |

### 8.3 Data Volume Estimates

| League | Games/Season | Total (2020-2024) |
|--------|--------------|-------------------|
| MLS | ~425 | ~2,125 |

---

## 9. ESPN API (Universal Fallback)

### 9.1 API Information

| Property | Value |
|----------|-------|
| **Base URL** | site.api.espn.com |
| **Authentication** | None required |
| **Rate Limits** | Unofficial, be respectful |
| **Documentation** | Undocumented (community reverse-engineered) |

### 9.2 Available Endpoints

| Endpoint Pattern | Description | Sports |
|------------------|-------------|--------|
| `/apis/site/v2/sports/{sport}/{league}/scoreboard` | Live/recent scores | All |
| `/apis/site/v2/sports/{sport}/{league}/teams` | Team information | All |
| `/apis/site/v2/sports/{sport}/{league}/teams/{id}` | Team details | All |

### 9.3 Sports Coverage

| Sport | League Code | Team Count |
|-------|-------------|------------|
| Football | nfl, college-football | 32, 130+ |
| Basketball | nba, wnba, mens-college-basketball, womens-college-basketball | 30, 12, 350+, 350+ |
| Hockey | nhl | 32 |
| Baseball | mlb | 30 |
| Soccer | usa.1 (MLS) | 30 |

---

## 10. Deprecated Sources

### 10.1 nfl_data_py (DEPRECATED)

| Property | Value |
|----------|-------|
| **Status** | Archived (Sep 25, 2025) |
| **Replacement** | nflreadpy |
| **Migration** | Same data, different API |
| **Action Required** | Update adapter to use nflreadpy |

### 10.2 FiveThirtyEight (DEFUNCT)

| Property | Value |
|----------|-------|
| **Status** | Shut down (March 2025) |
| **Historical Data** | Available on GitHub (stale) |
| **NFL Elo** | Last updated Feb 2021 |
| **NBA Elo** | Last updated June 2015 |
| **MLB Elo** | Corrupted/incomplete |
| **Action Required** | Compute Elo from game results |

---

## 11. Data Source Priority Matrix

For each sport, prioritize data sources in this order:

| Sport | Primary | Secondary | Fallback |
|-------|---------|-----------|----------|
| NFL | nflreadpy | - | ESPN API |
| NBA | nba_api | - | ESPN API |
| WNBA | nba_api | - | ESPN API |
| NHL | nhl-api-py | - | ESPN API |
| MLB | pybaseball | - | ESPN API |
| NCAAF | cfbd | ESPN API | - |
| NCAAB | cbbd | ESPN API | - |
| MLS | itscalledsoccer | ESPN API | - |

---

## 12. Installation Summary

```bash
# Core data sources (Tier 1)
pip install nflreadpy nba_api nhl-api-py pybaseball

# College sports (Tier 2)
pip install cfbd cbbd

# Soccer analytics (Tier 3)
pip install itscalledsoccer

# All at once
pip install nflreadpy nba_api nhl-api-py pybaseball cfbd cbbd itscalledsoccer
```

---

## 13. Related Documentation

- **ADR-106**: Historical Data Collection Architecture
- **ADR-304**: Elo Computation Architecture
- **ADR-305**: Data Source Adapter Migration (nfl_data_py -> nflreadpy)
- **REQ-DATA-008**: Data Source Adapter Architecture
- **Issue #273**: Comprehensive Elo Rating Computation Module
- **ELO_COMPUTATION_GUIDE_V1.0.md**: Elo methodology and implementation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-25 | Initial creation with 8 data sources, 21 nflreadpy functions |
