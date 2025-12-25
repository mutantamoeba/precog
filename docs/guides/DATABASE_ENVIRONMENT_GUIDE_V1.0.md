# Database Environment & Data Seeding Guide

---
**Version:** 1.1
**Created:** 2025-12-21
**Last Updated:** 2025-12-25
**Purpose:** Document database environment strategy, data seeding approach, and scheduling
**Related:** ADR-106 (Historical Data Collection), REQ-DB-001 through REQ-DB-017
---

## Overview

This guide documents the database environment strategy for Precog, including:
- Environment configuration (dev/test/prod)
- Data seeding approach and timing
- Data categories and refresh schedules
- Local vs cloud database strategy

## 1. Database Environments

### Environment Configuration

| Environment | Database | Purpose | Data Characteristics |
|-------------|----------|---------|---------------------|
| **Local Dev** | `precog` (PostgreSQL) | Development, debugging | Minimal real data, test fixtures |
| **Local Test** | `precog_test` (PostgreSQL) | Running pytest, CI/CD | Fresh each run, test fixtures only |
| **Cloud Prod** | TimescaleDB (Railway) | Live trading | Full historical + real-time data |

### Environment Variables

```bash
# Local development
PRECOG_ENV=development
DATABASE_URL=postgresql://postgres:password@localhost:5432/precog

# Cloud production
PRECOG_ENV=production
DATABASE_URL=postgresql://user:pass@railway-host:5432/precog_prod

# Testing (always local, fresh DB)
PRECOG_ENV=test
DATABASE_URL=postgresql://postgres:password@localhost:5432/precog_test
```

### Current State

- **Local PostgreSQL**: Fully operational (dev + test databases)
- **Cloud TimescaleDB**: Planned (Issue #248: Railway Cloud Infrastructure)
- **Migration 0009**: Adds `historical_stats` and `historical_rankings` tables

## 2. Data Categories

### Seeded Data vs Infrastructure

| Data Type | Status | Tables | Source |
|-----------|--------|--------|--------|
| **Teams** | Actually Seeded | `teams` | `seeds/static/*.sql` (8 files) |
| **Elo Ratings** | Infrastructure Only | `historical_elo` | Migration 0005 |
| **Historical Games** | Infrastructure Only | `historical_games` | Migration 0006 |
| **Historical Odds** | Infrastructure Only | `historical_odds` | Migration 0007 |
| **Historical Stats** | Infrastructure Only | `historical_stats` | Migration 0009 |
| **Historical Rankings** | Infrastructure Only | `historical_rankings` | Migration 0009 |

### Data Type Descriptions

| Category | Description | Update Frequency | Tables |
|----------|-------------|------------------|--------|
| **Historical** | Past games, stats, odds, rankings | One-time load + periodic refresh | `historical_*` |
| **Market** | Current Kalshi market data | Real-time via API | `markets` |
| **Live** | Game scores, player stats | Real-time during games | `game_states` |
| **Mode** | Strategy configurations | On-demand | `strategies` |
| **Strategy** | Trading strategy versions | Immutable (SCD Type 2) | `strategy_parameters` |
| **Trade** | Executed trades, positions | Real-time | `positions`, `trades` |

## 3. Seeding Strategy

### Recommended Approach: Cloud First

```
                    +--------------------------------------+
                    |         Railway Cloud                |
                    |  +--------------------------------+  |
                    |  |    TimescaleDB (Production)    |  |
                    |  |  - Full historical data        |  |
                    |  |  - Real-time market data       |  |
                    |  |  - Trade execution             |  |
                    |  +--------------------------------+  |
                    +--------------------------------------+
                                     ^
                                     | Sync (optional)
                    +--------------------------------------+
                    |         Local Development            |
                    |  +--------------------------------+  |
                    |  |    PostgreSQL (Dev/Test)       |  |
                    |  |  - Team reference data         |  |
                    |  |  - 2-season subset (optional)  |  |
                    |  |  - Test fixtures               |  |
                    |  +--------------------------------+  |
                    +--------------------------------------+
```

### Seeding Timeline

| Phase | Action | Data Location |
|-------|--------|---------------|
| **Now** | Tables and infrastructure ready | Local PostgreSQL |
| **Issue #248** | Deploy TimescaleDB on Railway | Cloud |
| **Post-#248** | Seed historical data to cloud | Cloud TimescaleDB |
| **Optional** | Replicate subset to local dev | Local PostgreSQL |

### CLI Seed Commands

```bash
# Seed teams (already works)
python main.py seed teams --sport nfl

# Seed historical data (infrastructure exists, CLI ready)
python main.py seed historical --source elo --sport nfl
python main.py seed historical --source games --sport nfl
python main.py seed historical --source odds --sport nfl
python main.py seed historical --source stats --sport nfl    # Issue #236
python main.py seed historical --source rankings --sport nfl  # Issue #236
```

## 4. Data Refresh Scheduling

### Proposed Schedule (Phase 5+)

```
+-------------------------------------------------------------+
|                    Data Pipeline Schedule                   |
+-------------------------------------------------------------+
| Daily (2 AM):     Refresh Elo ratings, rankings             |
| Pre-game (3h):    Fetch odds, injury reports                |
| Real-time:        Market prices, game states                |
| Post-game (1h):   Update results, calculate P&L             |
| Weekly:           Historical stats refresh                  |
+-------------------------------------------------------------+
```

### Scheduling Implementation

Scheduling will be implemented using:
- **APScheduler** for Python-based job scheduling
- **Environment-aware execution** (only runs in production)
- **Logging and monitoring** via structured logging

```python
# Example scheduler configuration (Phase 5+)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Daily Elo refresh at 2 AM
scheduler.add_job(refresh_elo_ratings, 'cron', hour=2)

# Pre-game odds fetch (3 hours before game time)
scheduler.add_job(fetch_pregame_odds, 'cron', hour='*')

# Real-time market polling (every 30 seconds during trading hours)
scheduler.add_job(poll_market_prices, 'interval', seconds=30)
```

## 5. Environment-Specific Behavior

### Development Environment

- Uses local PostgreSQL
- May use subset of historical data
- Test fixtures for unit/integration tests
- No real API calls (mocked)

### Test Environment

- Uses separate `precog_test` database
- Fresh database on each test run
- Deterministic test fixtures
- All API calls mocked

### Production Environment

- Uses cloud TimescaleDB
- Full historical data
- Real-time API integration
- Actual trading execution

## 6. Data Sources

### External Data Sources

| Source | Data Types | Sports | Status | Verified |
|--------|------------|--------|--------|----------|
| **ESPN API** | Teams, scores, schedules | NFL, NBA, NHL, WNBA, NCAAF, NCAAB, MLB, MLS | ✅ Integrated | 2025-12-25 |
| **nfl_data_py** | Games, stats, rosters | NFL | ✅ Adapter ready | 2025-12-21 |
| **FiveThirtyEight** | Elo ratings, forecasts | NFL, NBA, MLB | ⚠️ Defunct (Mar 2025) | N/A |
| **Kalshi API** | Markets, positions, trades | Prediction Markets | ✅ Integrated | 2025-12-24 |
| **Kaggle datasets** | Historical rankings | NCAAF, NFL | 🔵 Planned | TBD |

### Data Source Verification Log

**ESPN API Team IDs** (Verified 2025-12-25):
- MLB: 30 teams verified via `https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams`
- MLS: 30 teams verified via `https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/teams`
- NFL/NBA/NHL/WNBA: Previously verified and seeded

**FiveThirtyEight Status** (Checked 2025-12-25):
- FiveThirtyEight was shut down by ABC News/Disney in March 2025
- API endpoints now redirect to ABC News politics pages
- Historical data on GitHub is outdated (NFL: Feb 2021, NBA: June 2015, MLB: corrupted)
- **Alternative**: Compute Elo from game results using nfl_data_py schedules

**Seeded Team Counts** (As of 2025-12-25):
| Sport | League | Teams | Source |
|-------|--------|-------|--------|
| MLB | mlb | 30 | ESPN API |
| MLS | mls | 30 | ESPN API |
| NBA | nba | 30 | ESPN API |
| NCAAB | ncaab | 89 | ESPN API |
| NCAAF | ncaaf | 79 | ESPN API |
| NFL | nfl | 32 | ESPN API |
| NHL | nhl | 32 | ESPN API |
| WNBA | wnba | 12 | ESPN API |
| **Total** | | **334** | |

### Data Source Adapters

All data sources implement the `BaseDataSource` interface:

```python
class BaseDataSource(ABC):
    @abstractmethod
    def supports_games(self) -> bool: ...

    @abstractmethod
    def supports_elo(self) -> bool: ...

    @abstractmethod
    def supports_stats(self) -> bool: ...

    @abstractmethod
    def supports_rankings(self) -> bool: ...
```

## 7. Security Considerations

### Database Credentials

- Never hardcode credentials
- Use environment variables for all connections
- Rotate credentials periodically
- Use separate credentials for dev/test/prod

### Data Access

- Production database only accessible from cloud services
- Local development uses separate credentials
- Test database isolated from production

## 8. Related Documentation

- **DATABASE_ENVIRONMENT_STRATEGY_V1.0.md**: Multi-environment workflow, migrations, test isolation (companion guide)
- **ADR-106**: Historical Data Collection Architecture
- **REQ-DATA-005 through REQ-DATA-008**: Historical data requirements
- **Issue #236**: StatsRecord/RankingRecord Infrastructure
- **Issue #248**: Railway Cloud Infrastructure
- **POSTGRESQL_SETUP_GUIDE.md**: Local database setup

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-12-25 | Added Data Source Verification Log, documented FiveThirtyEight shutdown, updated seeded team counts (334 total), added ESPN API verification dates |
| 1.0 | 2025-12-21 | Initial creation with environment strategy, seeding approach, and scheduling |
