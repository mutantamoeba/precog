# Live Data Integration Guide

---
**Version:** 1.0
**Created:** 2025-12-07
**Last Updated:** 2025-12-07
**Status:** Complete
**Phase:** 2.5 (Live Data Collection Service)
**Related ADRs:** ADR-100 (Service Supervisor Pattern), ADR-103 (BasePoller Unified Design), ADR-029 (ESPN Data Model)
**Related Requirements:** REQ-SCHED-001, REQ-SCHED-002, REQ-SCHED-003, REQ-DATA-001, REQ-OBSERV-003
---

## Overview

This guide documents the live data integration architecture for the Precog prediction market platform. It covers:

1. **CLI Scheduler Commands** - Start, stop, and monitor data collection services
2. **Service Supervisor Pattern** - Multi-service orchestration with health monitoring
3. **Data Collection Services** - ESPN polling, Kalshi REST, Kalshi WebSocket
4. **Configuration Options** - Poll intervals, logging, and service management
5. **Monitoring & Health Checks** - Metrics, alerting, and troubleshooting

### Architecture Overview

```
                              ┌─────────────────────────────────────┐
                              │         Service Supervisor          │
                              │  (Health Monitoring, Auto-Restart)  │
                              └──────────────┬──────────────────────┘
                                             │
           ┌─────────────────────────────────┼─────────────────────────────────┐
           │                                 │                                 │
           ▼                                 ▼                                 ▼
┌─────────────────────┐          ┌─────────────────────┐          ┌─────────────────────┐
│   ESPNGamePoller     │         │  KalshiMarketPoller  │         │ KalshiWebSocket     │
│   (BasePoller)       │         │   (BasePoller)       │         │  Handler            │
│   15s poll interval  │         │   30s poll interval  │         │  <1s latency        │
└──────────┬──────────┘          └──────────┬──────────┘          └──────────┬──────────┘
           │                                 │                                 │
           ▼                                 ▼                                 ▼
┌─────────────────────┐          ┌─────────────────────┐          ┌─────────────────────┐
│  ESPN Scoreboard API │         │   Kalshi REST API    │         │   Kalshi WS API     │
└──────────┬──────────┘          └──────────┬──────────┘          └──────────┬──────────┘
           │                                 │                                 │
           └─────────────────────────────────┼─────────────────────────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────────────┐
                              │         PostgreSQL Database         │
                              │  (SCD Type 2 game_states, venues)   │
                              └─────────────────────────────────────┘
```

---

## CLI Scheduler Commands

The Precog CLI provides a `scheduler` command group for managing live data collection services.

### Starting Data Collection

```bash
# Start all data collectors (ESPN + Kalshi)
python main.py scheduler start

# Start ESPN polling only
python main.py scheduler start --espn --no-kalshi

# Start Kalshi polling only
python main.py scheduler start --no-espn --kalshi

# Custom poll interval (seconds)
python main.py scheduler start --poll-interval 30

# Specify leagues to poll
python main.py scheduler start --leagues nfl,nba,ncaaf

# Verbose output with debug logging
python main.py scheduler start --verbose
```

### Command Options

| Option | Default | Description |
|--------|---------|-------------|
| `--espn/--no-espn` | True | Enable/disable ESPN game polling |
| `--kalshi/--no-kalshi` | True | Enable/disable Kalshi market polling |
| `--poll-interval` | 15 | Seconds between polls (min: 5) |
| `--leagues` | nfl,ncaaf | Comma-separated list of leagues |
| `--verbose/-v` | False | Enable debug logging |

### Stopping Data Collection

```bash
# Stop all running data collectors
python main.py scheduler stop

# Verbose output
python main.py scheduler stop --verbose
```

### Checking Status

```bash
# Check status of all data collectors
python main.py scheduler status

# Detailed status with metrics
python main.py scheduler status --verbose
```

**Example Output:**
```
ESPN MarketUpdater: RUNNING
  - Leagues: nfl, ncaaf, nba
  - Poll interval: 15s
  - Polls completed: 142
  - Games updated: 28
  - Errors: 0
  - Last poll: 2025-12-07T20:15:30+00:00

Kalshi Market Poller: RUNNING
  - Series: KXNFLGAME
  - Poll interval: 30s
  - Polls completed: 71
  - Markets updated: 15
  - Errors: 0
```

---

## Service Supervisor Pattern

For production deployments, use the `ServiceSupervisor` which provides:

- **Multi-service orchestration** - Manage ESPN, Kalshi REST, and WebSocket services together
- **Health monitoring** - Periodic health checks with configurable intervals
- **Auto-restart** - Automatic restart of failed services with exponential backoff
- **Circuit breaker** - Stop restarting after repeated failures
- **Alert callbacks** - Notify external systems on errors

### Running the Data Collector Script

```bash
# Start all data collectors in development mode
python scripts/run_data_collector.py

# Start specific services
python scripts/run_data_collector.py --services espn,kalshi_rest

# Production mode with JSON logging
python scripts/run_data_collector.py --env production

# Custom poll interval
python scripts/run_data_collector.py --poll-interval 30

# Custom health check interval
python scripts/run_data_collector.py --health-interval 120
```

### Script Options

| Option | Default | Description |
|--------|---------|-------------|
| `--env` | development | Environment (development/staging/production) |
| `--services` | all | Comma-separated services (espn, kalshi_rest, kalshi_ws) |
| `--poll-interval` | 15 | Seconds between polls |
| `--log-level` | INFO | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `--log-dir` | logs/ | Directory for log files |
| `--health-interval` | 60 | Health check interval in seconds |
| `--metrics-interval` | 300 | Metrics output interval in seconds |

### Programmatic Usage

```python
from precog.schedulers import (
    MarketUpdater,
    KalshiMarketPoller,
    create_market_updater,
    create_kalshi_poller,
)

# ESPN Game Polling
updater = create_market_updater(
    leagues=["nfl", "ncaaf", "nba"],
    poll_interval=15,
    persist_jobs=True,  # Survive restarts
    job_store_url="sqlite:///jobs.db",
)
updater.start()

# One-time poll without scheduler
result = updater.poll_once()
print(f"Updated {result['games_updated']} games")

# Refresh scoreboards on demand
result = updater.refresh_scoreboards(active_only=True)
print(f"Active games: {result['active_games']}")

# Kalshi Market Polling
poller = create_kalshi_poller(
    series_tickers=["KXNFLGAME"],
    poll_interval=30,
)
poller.start()

# Clean shutdown
updater.stop()
poller.stop()
```

---

## Data Collection Services

### ESPN MarketUpdater

Polls ESPN Scoreboard API for live game states with SCD Type 2 versioning.

**Key Features:**
- Multi-league support (NFL, NCAAF, NBA, NCAAB, NHL, WNBA)
- Configurable poll intervals (15-60 seconds)
- Conditional polling (only when games active)
- Error recovery with logging
- Thread-safe operation

**Data Flow:**
1. Fetch scoreboard from ESPN API
2. Parse game data into normalized `ESPNGameFull` TypedDict
3. Look up team IDs in database (ESPN ID -> database ID)
4. Create/update venues as needed
5. Upsert game state with SCD Type 2 versioning

**Example:**
```python
from precog.schedulers import run_single_poll, refresh_all_scoreboards

# Quick poll without scheduler
result = run_single_poll(["nfl"])
print(f"Fetched: {result['games_fetched']}, Updated: {result['games_updated']}")

# Detailed scoreboard refresh
result = refresh_all_scoreboards(leagues=["nfl", "ncaaf"])
print(f"Active games: {result['active_games']}")
print(f"Elapsed: {result['elapsed_seconds']}s")
```

### Kalshi REST Poller

Polls Kalshi REST API for market prices and order book data.

**Key Features:**
- Series-based polling (e.g., KXNFLGAME for NFL games)
- Rate limit aware (100 requests/minute)
- Exponential backoff on errors
- Market snapshot persistence

**Example:**
```python
from precog.schedulers import create_kalshi_poller, run_single_kalshi_poll

# Scheduled polling
poller = create_kalshi_poller(
    series_tickers=["KXNFLGAME"],
    poll_interval=30,
)
poller.start()

# One-time poll
result = run_single_kalshi_poll(["KXNFLGAME"])
```

### Kalshi WebSocket Handler

Real-time market updates via Kalshi WebSocket API.

**Key Features:**
- Sub-second latency for price updates
- Automatic reconnection on disconnect
- Hybrid mode with REST fallback
- Order book streaming

**Example:**
```python
from precog.schedulers import create_websocket_handler, ConnectionState

handler = create_websocket_handler(environment="demo")
handler.subscribe(["INXD-25AUXA-T64"])
handler.start()

# Check connection state
if handler.state == ConnectionState.CONNECTED:
    print("WebSocket connected")
```

---

## Configuration Options

### Poll Intervals

| Service | Default | Min | Max | Recommended |
|---------|---------|-----|-----|-------------|
| ESPN (active games) | 15s | 5s | 60s | 15s |
| ESPN (no active games) | 60s | 15s | 300s | 60s |
| Kalshi REST | 30s | 10s | 120s | 30s |
| Kalshi WebSocket | Real-time | N/A | N/A | N/A |

### Logging Configuration

**Development Mode:**
- Human-readable format
- DEBUG level to console
- INFO level to file

**Production Mode:**
- JSON format (ELK/CloudWatch compatible)
- INFO level to console
- All levels to file

```bash
# Development (default)
python scripts/run_data_collector.py --env development

# Production with JSON logging
python scripts/run_data_collector.py --env production
```

### Job Persistence

Enable job persistence to survive scheduler restarts:

```python
updater = create_market_updater(
    leagues=["nfl"],
    persist_jobs=True,
    job_store_url="sqlite:///jobs.db",  # or PostgreSQL URL
)
```

When enabled:
- Scheduled jobs stored in SQLite/PostgreSQL
- Jobs automatically restored on restart
- Missed executions tracked and handled

---

## Monitoring & Health Checks

### Health Check Metrics

The ServiceSupervisor provides these metrics:

| Metric | Description |
|--------|-------------|
| `polls_completed` | Total successful poll cycles |
| `games_updated` | Total game states synced to DB |
| `errors` | Total error count |
| `last_poll` | Timestamp of last successful poll |
| `last_error` | Last error message (if any) |
| `uptime_seconds` | Service uptime |
| `restarts` | Number of auto-restarts |

### Accessing Metrics

```python
# From MarketUpdater
stats = updater.stats
print(f"Polls: {stats['polls_completed']}, Errors: {stats['errors']}")

# From CLI
python main.py scheduler status --verbose
```

### Alert Callbacks

Register callbacks for error notifications:

```python
def slack_alert(service_name: str, message: str, context: dict):
    # Send to Slack webhook
    pass

supervisor.register_alert_callback(slack_alert)
```

### Log Files

Logs are stored in the `logs/` directory:

```
logs/
├── data_collector.log      # Main service log
├── data_collector.log.1    # Rotated log (10MB max)
├── data_collector.log.2
└── ...
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Team not found" warnings | Team not in teams table | Run seed data migration |
| "Rate limit exceeded" | Too many API calls | Increase poll interval |
| Connection timeouts | Network/API issues | Check connectivity, wait for retry |
| "No games active" | Outside game windows | Normal behavior, polling continues |

### Debug Commands

```bash
# Test database connection
python scripts/test_db_connection.py

# Run single ESPN poll with debug output
python -c "
from precog.schedulers import run_single_poll
import logging
logging.basicConfig(level=logging.DEBUG)
result = run_single_poll(['nfl'])
print(result)
"

# Check live games in database
python -c "
from precog.database.crud_operations import get_live_games
games = get_live_games(league='nfl')
print(f'Live NFL games: {len(games)}')
for g in games:
    print(f'  {g[\"espn_event_id\"]}: {g[\"home_score\"]}-{g[\"away_score\"]}')
"
```

### Service Recovery

If a service fails repeatedly:

1. Check the logs: `cat logs/data_collector.log | tail -100`
2. Verify API credentials: `echo $KALSHI_API_KEY_ID`
3. Test database connection: `python scripts/test_db_connection.py`
4. Restart with verbose logging: `python scripts/run_data_collector.py --log-level DEBUG`

---

## Related Documentation

- [ESPN Data Model Guide](ESPN_DATA_MODEL_V1.0.md) - Database schema and TypedDict definitions
- [Kalshi Client User Guide](KALSHI_CLIENT_USER_GUIDE_V1.0.md) - REST and WebSocket API usage
- [Configuration Guide](CONFIGURATION_GUIDE_V3.1.md) - YAML configuration reference
- [Development Phases](../foundation/DEVELOPMENT_PHASES_V1.9.md) - Phase 2.5 details

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-07 | Initial release covering CLI scheduler, ServiceSupervisor, and data collection services |
