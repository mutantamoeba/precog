# Precog Configuration Guide

---
**Version:** 3.0
**Last Updated:** 2025-10-16
**Status:** ✅ Current - Matches actual implementation
**Changes in v3.0:**
- Complete rewrite to match actual YAML file structures
- Updated environment variable references to match env.template
- Documented actual inline configuration approach
- Removed outdated hierarchical examples that don't exist
- Added phase-based configuration sections
- Aligned with actual system implementation
---

## Overview

Precog uses a **YAML-based configuration system** with comprehensive inline documentation. Each configuration file is self-documenting with extensive comments explaining the purpose, reasoning, and examples for every parameter.

### Configuration Philosophy

1. **Self-Documenting**: YAML files include extensive inline comments
2. **Phase-Based**: Configuration parameters are organized by implementation phase
3. **Safety-First**: Conservative defaults with clear upgrade paths
4. **Environment Separation**: Clear separation between demo, test, and production

### Configuration Priority

1. **Environment Variables** (.env file) - Secrets and API keys (highest priority)
2. **YAML Files** - All configuration parameters (default values)
3. **Database Overrides** (Phase 7+) - Runtime adjustments via `config_overrides` table

---

## Configuration Files Structure

```
config/
├── env.template              # Environment variable template
├── trading.yaml              # Trading parameters and risk limits
├── trade_strategies.yaml     # Strategy definitions (when to enter)
├── position_management.yaml  # Position lifecycle management
├── probability_models.yaml   # Probability calculation models
├── markets.yaml              # Platform and market configuration
├── data_sources.yaml         # API endpoints and data sources
└── system.yaml               # System-wide settings
```

---

## 1. Environment Variables (env.template)

### Phase 1-2: Core Infrastructure & Live Data

```bash
# PostgreSQL Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Kalshi API (Demo for testing)
KALSHI_API_KEY=your_kalshi_api_key_here
KALSHI_API_SECRET=your_kalshi_api_secret_here
KALSHI_BASE_URL=https://demo-api.kalshi.co  # Use demo for testing
# KALSHI_BASE_URL=https://trading-api.kalshi.com  # Production URL

# ESPN API (Public - no key required)
ESPN_API_BASE=https://site.api.espn.com/apis/site/v2
```

### Phase 6: Multi-Sport Expansion

```bash
# BallDontLie API (NBA Data)
BALLDONTLIE_API_KEY=your_balldontlie_api_key_here
BALLDONTLIE_BASE_URL=https://api.balldontlie.io/v1

# MLB Data Source
MLB_DATA_SOURCE=espn

# Tennis Data Source (TBD)
TENNIS_API_KEY=your_tennis_api_key_here
TENNIS_API_BASE=https://api.tennisdata.com

# UFC Data (ESPN - public)
UFC_DATA_SOURCE=espn
```

### Phase 8: Non-Sports Markets

```bash
# RealClearPolling API
RCP_API_KEY=your_rcp_api_key_here
RCP_API_BASE=https://api.realclearpolitics.com

# FiveThirtyEight API
FIVETHIRTYEIGHT_API_KEY=your_538_api_key_here
FIVETHIRTYEIGHT_API_BASE=https://api.fivethirtyeight.com

# Box Office Mojo API
BOXOFFICE_API_KEY=your_boxoffice_api_key_here
BOXOFFICE_API_BASE=https://api.boxofficemojo.com

# Twitter API
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# News API
NEWS_API_KEY=your_news_api_key_here
NEWS_API_BASE=https://newsapi.org/v2
```

### Phase 10: Multi-Platform

```bash
# Polymarket API
POLYMARKET_API_KEY=your_polymarket_api_key_here
POLYMARKET_PRIVATE_KEY=your_polymarket_private_key_here
POLYMARKET_CLOB_BASE=https://clob.polymarket.com
POLYMARKET_GAMMA_BASE=https://gamma-api.polymarket.com

# Ethereum RPC (for Polymarket)
ETH_RPC_URL=https://mainnet.infura.io/v3/your_project_id
ETH_CHAIN_ID=137  # Polygon mainnet
```

### System Configuration

```bash
# Environment Mode
ENVIRONMENT=development  # Options: development, staging, production

# Logging
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE_PATH=/var/log/precog/precog.log
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5

# Application Settings
APP_NAME=Precog
APP_VERSION=0.1.0
DEBUG_MODE=True  # Set to False in production

# Rate Limiting
API_RATE_LIMIT=100  # Requests per minute
RATE_LIMIT_BACKOFF=exponential

# Circuit Breaker
CIRCUIT_BREAKER_ENABLED=True
MAX_API_FAILURES=5
CIRCUIT_RESET_TIMEOUT=300  # Seconds

# Position Limits
MAX_POSITION_SIZE=1000  # Dollars per position
MAX_TOTAL_EXPOSURE=10000  # Dollars across all positions
DAILY_LOSS_LIMIT=500  # Dollars

# Testing
TEST_DB_NAME=precog_test_db
TEST_DB_USER=test_user
TEST_DB_PASSWORD=test_password
MOCK_API_MODE=False

# Paper Trading
PAPER_TRADING_MODE=True  # Start with paper trading!
PAPER_TRADING_BALANCE=10000
```

---

## 2. trading.yaml

**Purpose:** Core trading parameters - risk management, position sizing, circuit breakers

### Key Sections

**Trading Environment**
```yaml
# demo = paper trading (fake money)
# prod = live trading (real money)
environment: demo  # CHANGE TO 'prod' ONLY WHEN READY
```

**Account Limits (Circuit Breakers)**
```yaml
account:
  max_total_exposure_dollars: 10000.00
  daily_loss_limit_dollars: 500.00
  weekly_loss_limit_dollars: 1500.00
  min_balance_to_trade_dollars: 1000.00
  max_trades_per_hour: 10
  max_trades_per_day: 50
```

**Position Sizing (Kelly Criterion)**
```yaml
position_sizing:
  method: kelly  # Options: kelly, fixed, fixed_fraction

  kelly:
    default_fraction: 0.25  # Quarter Kelly (conservative)
    min_edge_threshold: 0.05  # 5% minimum edge
    max_position_pct: 0.05  # 5% of bankroll maximum
    min_position_dollars: 10.00
    max_position_dollars: 500.00
```

**Trade Execution**
```yaml
execution:
  default_order_type: limit  # market or limit
  limit_order_timeout_seconds: 30
  max_slippage_pct: 0.02  # 2% maximum slippage
  retry_on_failure: true
  max_retries: 3
  retry_backoff_seconds: 5
```

**Market Filters**
```yaml
market_filters:
  min_volume_contracts: 100
  max_spread_pct: 0.05  # 5% maximum spread
  exclude_categories:
    - "politics"  # Too unpredictable

  trading_hours:
    enabled: true
    monday:
      start: "09:00"
      end: "23:00"
    # ... (continues for each day)
    timezone: "America/New_York"
```

**Circuit Breakers**
```yaml
circuit_breakers:
  api_errors:
    threshold: 5
    window_minutes: 5

  edge_anomaly:
    threshold_pct: 0.30  # 30% edges are suspicious
    count: 3
    window_minutes: 10

  rapid_loss:
    loss_dollars: 200.00
    window_minutes: 15
```

---

## 3. trade_strategies.yaml

**Purpose:** Define WHEN to enter positions (strategy triggers and conditions)

### Strategy Definitions

**Pre-Game Entry**
```yaml
pre_game_entry:
  enabled: true

  min_hours_before_game: 0.5   # 30 minutes minimum
  max_hours_before_game: 24.0  # 24 hours maximum

  sports_config:
    nfl:
      enabled: true
      required_confidence: 0.08  # 8% minimum edge
      allowed_markets:
        - "game_winner"
        - "total_points"
        - "point_spread"
      require_full_lineup: true
      max_key_injuries: 1
      weather_limits:
        max_wind_mph: 20
        max_precipitation: 0.3
        exclude_snow: true
```

**Halftime Entry (THE MONEY MAKER)**
```yaml
halftime_entry:
  enabled: true
  max_minutes_into_halftime: 10

  sports_config:
    nfl:
      enabled: true
      required_confidence: 0.06  # 6% minimum edge
      allowed_markets:
        - "second_half_winner"
        - "second_half_total"
        - "game_winner"
        - "will_score_next"

      analysis_factors:
        weight_possession_yardage: 0.4
        weight_score_differential: 0.2
        weight_turnover_margin: 0.2
        weight_time_of_possession: 0.2
        blowout_threshold: 17
        close_game_threshold: 7
```

**Settlement Arbitrage**
```yaml
settlement_arbitrage:
  enabled: true
  min_win_probability: 0.98  # 98% or higher
  max_time_remaining_seconds: 120  # 2 minutes or less
  min_edge: 0.02  # 2% minimum (lower than other strategies)

  # These are nearly risk-free, so can size bigger
  kelly_fraction_override: 0.50
  max_position_override: 1000.00
```

---

## 4. position_management.yaml

**Purpose:** Define WHAT to do after entering position (lifecycle management)

### Key Sections

**Portfolio Limits**
```yaml
portfolio:
  max_open_positions: 10
  max_total_capital_deployed: 10000.00
  max_correlated_exposure: 3000.00

  max_exposure_by_sport:
    nfl: 0.60  # 60% of portfolio max
    nba: 0.40
    mlb: 0.30

  max_positions_per_game: 3
  max_exposure_per_game: 1500.00
```

**Position Monitoring**
```yaml
monitoring:
  update_frequency_seconds: 60  # Every minute

  checks:
    - "current_price"
    - "edge_status"
    - "correlation"
    - "time_to_settlement"
    - "liquidity"

  health_score:
    enabled: true
    factors:
      edge_remaining: 0.40
      time_remaining: 0.20
      liquidity_depth: 0.20
      unrealized_pnl: 0.20
```

**Exit Rules**
```yaml
exit_rules:
  mandatory:
    negative_edge:
      enabled: true
      threshold: -0.03  # -3% edge

    late_game_loss:
      enabled: true
      minutes_remaining: 10
      loss_threshold_pct: 0.20

  discretionary:
    profit_target:
      enabled: true
      by_strategy:
        pre_game_entry:
          target_gain_pct: 0.50  # Exit at 50% gain
        halftime_entry:
          target_gain_pct: 0.75

    stop_loss:
      enabled: true
      by_strategy:
        pre_game_entry:
          max_loss_pct: 0.40  # Exit at 40% loss
```

---

## 5. probability_models.yaml

**Purpose:** Configure probability calculation models (formerly odds_models.yaml)

### Model Architecture

```yaml
architecture:
  primary_model: elo  # Options: elo, regression, ensemble, ml

  ensemble:
    enabled: false  # Phase 4+
    models:
      - elo
      - regression
      - ml
    weights:
      elo: 0.40
      regression: 0.35
      ml: 0.25
```

### Elo Rating System

```yaml
elo:
  initial_rating: 1500

  k_factor:
    nfl: 32
    nba: 24
    mlb: 16
    tennis: 40

  mov_adjustment:
    enabled: true
    max_multiplier: 2.0

  home_advantage:
    nfl: 65   # ~3 points in spread terms
    nba: 80   # ~4 points
    mlb: 40   # ~2 points

  probability_scaling:
    nfl: 400
    nba: 350
    mlb: 400
```

### Edge Detection

```yaml
edge_detection:
  method: simple  # Edge = (TrueProb × Payout) - 1

  uncertainty_discount:
    enabled: true
    shrinkage_factor: 0.10  # 10% shrinkage

  transaction_costs:
    enabled: true
    maker_rebate: 0.01  # 1% rebate
    taker_fee: 0.01  # 1% fee
    assume_taker: true

  min_edge:
    pre_game: 0.08  # 8% minimum
    halftime: 0.06  # 6% minimum
    live: 0.10  # 10% minimum
    settlement: 0.02  # 2% minimum
```

---

## 6. markets.yaml

**Purpose:** Configure which markets to trade and platform settings

### Platform Configuration (Kalshi)

```yaml
platforms:
  kalshi:
    enabled: true
    platform_id: "kalshi"

    # API credentials reference .env
    api_key_env: "KALSHI_PROD_API_KEY_ID"
    api_secret_env: "KALSHI_PROD_API_KEYFILE"

    environments:
      demo:
        base_url: "https://demo-api.kalshi.com"
        websocket_url: "wss://demo-api.kalshi.com/trade-api/ws/v2"
        enabled: true
      prod:
        base_url: "https://api.kalshi.com"
        websocket_url: "wss://api.kalshi.com/trade-api/ws/v2"
        enabled: true

    active_environment: "demo"  # Change to "prod" when ready

    rate_limit_per_minute: 100

    fees:
      maker_fee_percent: 0.00  # Maker rebate
      taker_fee_percent: 0.07  # 7% on winnings
```

### Market Categories

```yaml
    categories:
      sports:
        enabled: true
        leagues:
          nfl:
            enabled: true
            series_tickers:
              - "KXNFLGAME"
            min_liquidity: 100
            max_spread: 0.05
            kelly_fraction: 0.25
            min_edge: 0.05

          ncaaf:
            enabled: true
            series_tickers:
              - "KXNCAAFGAME"
            min_liquidity: 50
            max_spread: 0.06
            kelly_fraction: 0.20
            min_edge: 0.06
```

---

## 7. data_sources.yaml

**Purpose:** Configure external APIs and data sources

### Live Game Statistics (ESPN)

```yaml
live_stats:
  espn:
    enabled: true
    provider: "ESPN"

    endpoints:
      nfl:
        scoreboard: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        teams: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
      nba:
        scoreboard: "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

    polling:
      interval_seconds: 30
      timeout_seconds: 10
      retry_attempts: 3

    rate_limit:
      requests_per_minute: 60
      burst_allowance: 10
```

### Historical Data Sources

```yaml
historical_data:
  profootballreference:
    enabled: true
    base_url: "https://www.pro-football-reference.com"

    scraping:
      allowed: true
      rate_limit_per_hour: 20
      delay_between_requests: 5
      user_agent: "precog-trading-bot/1.0 (research purposes)"

    backfill:
      start_year: 2019
      end_year: 2024
      seasons: ["regular", "playoffs"]
```

---

## 8. system.yaml

**Purpose:** System-wide settings (database, logging, health checks)

### Environment Selection

```yaml
environment:
  active: "demo"  # Options: demo | prod | test
```

### Database Configuration

```yaml
database:
  demo:
    host: "localhost"
    port: 5432
    name: "precog_demo"
    user: "postgres"
    password_env: "DEMO_DB_PASSWORD"
    pool_size: 5
    max_overflow: 10
    pool_timeout: 30

  prod:
    host: "localhost"
    port: 5432
    name: "precog_prod"
    user: "postgres"
    password_env: "PROD_DB_PASSWORD"
    pool_size: 10
    max_overflow: 20
    ssl_mode: "require"
    statement_timeout: 60000
```

### Logging Configuration

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

  console:
    enabled: true
    level: "INFO"
    format: "human_readable"

  file:
    enabled: true
    level: "DEBUG"
    directory: "logs"
    max_size_mb: 100
    max_files: 10
    files:
      main: "precog.log"
      trades: "trades.log"
      api: "api_calls.log"
      errors: "errors.log"

  database:
    enabled: true
    retention_days:
      activity: 90
      trades: 365
      api_calls: 30
```

### Circuit Breakers

```yaml
circuit_breakers:
  enabled: true

  api_failures:
    threshold: 5
    timeout_seconds: 300

  data_quality:
    threshold: 3
    timeout_seconds: 600

  loss_limit:
    daily_loss_usd: 500
    timeout_seconds: 86400  # Requires manual reset

  position_limit:
    max_open_positions: 20
    timeout_seconds: 3600
```

---

## Configuration Access in Code

### Loading Configuration

```python
import yaml
from pathlib import Path
from decimal import Decimal

def load_config(config_file: str):
    """Load a YAML configuration file"""
    config_path = Path("config") / config_file
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

# Load trading config
trading_config = load_config('trading.yaml')

# Access nested values
environment = trading_config['environment']  # 'demo' or 'prod'
kelly_fraction = Decimal(str(trading_config['position_sizing']['kelly']['default_fraction']))
max_exposure = Decimal(str(trading_config['account']['max_total_exposure_dollars']))
```

### Environment Variable Access

```python
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access environment variables
kalshi_api_key = os.getenv('KALSHI_API_KEY')
kalshi_api_secret = os.getenv('KALSHI_API_SECRET')
kalshi_base_url = os.getenv('KALSHI_BASE_URL', 'https://demo-api.kalshi.co')
db_password = os.getenv('DB_PASSWORD')
```

---

## Configuration Validation

### Before Starting System

```bash
# Validate all YAML files
python -c "
import yaml
from pathlib import Path

config_files = [
    'trading.yaml',
    'trade_strategies.yaml',
    'position_management.yaml',
    'probability_models.yaml',
    'markets.yaml',
    'data_sources.yaml',
    'system.yaml'
]

for config_file in config_files:
    try:
        with open(Path('config') / config_file, 'r') as f:
            yaml.safe_load(f)
        print(f'✓ {config_file} is valid')
    except Exception as e:
        print(f'✗ {config_file} error: {e}')
"
```

### Environment Variable Checklist

```bash
# Check required variables are set
python -c "
import os
from dotenv import load_dotenv

load_dotenv()

required_vars = [
    'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
    'KALSHI_API_KEY', 'KALSHI_API_SECRET', 'KALSHI_BASE_URL'
]

missing = [var for var in required_vars if not os.getenv(var)]

if missing:
    print('Missing environment variables:')
    for var in missing:
        print(f'  - {var}')
else:
    print('✓ All required environment variables are set')
"
```

---

## Configuration Best Practices

### 1. Start Conservative

```yaml
# Beginner settings (trading.yaml)
position_sizing:
  kelly:
    default_fraction: 0.25  # Quarter Kelly
    min_edge_threshold: 0.08  # 8% minimum edge
    max_position_pct: 0.03  # 3% max per position

account:
  daily_loss_limit_dollars: 200.00
  max_trades_per_day: 20
```

### 2. Always Use Demo First

```yaml
# trading.yaml
environment: demo  # Paper trading first!

# markets.yaml
platforms:
  kalshi:
    active_environment: "demo"
```

### 3. Enable Features Gradually

```yaml
# Start with only essential strategies (trade_strategies.yaml)
pre_game_entry:
  enabled: true

halftime_entry:
  enabled: false  # Enable after mastering pre-game

live_trading:
  enabled: false  # Phase 3+

# Start with simple models (probability_models.yaml)
architecture:
  primary_model: elo  # Start simple
  ensemble:
    enabled: false  # Add complexity later
```

### 4. Monitor and Adjust

Track actual performance vs. configuration expectations:
- Is actual edge matching predicted edge?
- Are circuit breakers triggering appropriately?
- Is position sizing working as expected?

### 5. Document All Changes

When modifying configuration:
1. Comment the reason in YAML file
2. Log the change in git commit message
3. Update CHANGELOG.md if significant

---

## Phase-Based Configuration

### Phase 1: Database & Core Infrastructure
**Status:** ✅ Complete

**Required Configuration:**
- `system.yaml` - database settings
- `.env` - database credentials

### Phase 2: Live Data Integration
**Status:** 🔄 In Progress

**Required Configuration:**
- `data_sources.yaml` - ESPN API configuration
- `.env` - KALSHI_API_KEY, KALSHI_API_SECRET
- `markets.yaml` - Kalshi platform configuration

### Phase 3: Probability Models
**Status:** 📋 Planned

**Required Configuration:**
- `probability_models.yaml` - Elo rating system
- Model data files (to be created)

### Phase 4-5: Trading Strategies
**Status:** 📋 Planned

**Required Configuration:**
- `trading.yaml` - position sizing, risk limits
- `trade_strategies.yaml` - strategy definitions
- `position_management.yaml` - exit rules

---

## Troubleshooting

### Issue: Configuration Not Loading

```python
# Check if file exists
from pathlib import Path
config_path = Path("config/trading.yaml")
print(f"File exists: {config_path.exists()}")

# Check if YAML is valid
import yaml
try:
    with open(config_path, 'r') as f:
        yaml.safe_load(f)
    print("YAML is valid")
except yaml.YAMLError as e:
    print(f"YAML error: {e}")
```

### Issue: Environment Variables Not Found

```bash
# Check .env file location
ls -la .env

# Source .env manually (bash)
export $(cat .env | xargs)

# Or use python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('KALSHI_API_KEY'))"
```

### Issue: Decimal Precision Errors

```python
# ❌ WRONG - Using float
max_spread = 0.05

# ✅ CORRECT - Using Decimal
from decimal import Decimal
max_spread = Decimal('0.0500')
```

---

## Next Steps

1. **Copy env.template to .env**
   ```bash
   cp config/env.template .env
   ```

2. **Fill in your API credentials** in `.env`

3. **Review configuration files** in `config/` directory

4. **Validate configuration**
   ```bash
   python scripts/validate_config.py  # (to be created in Phase 2)
   ```

5. **Start with demo environment**
   - Ensure `trading.yaml` has `environment: demo`
   - Ensure `markets.yaml` has `active_environment: "demo"`
   - Ensure `.env` has `KALSHI_BASE_URL=https://demo-api.kalshi.co`

---

## Quick Reference

### Configuration File Quick Links

| File | Purpose | Key Settings |
|------|---------|-------------|
| `trading.yaml` | Risk management | Position sizing, circuit breakers |
| `trade_strategies.yaml` | Entry strategies | When to enter positions |
| `position_management.yaml` | Exit strategies | When to exit positions |
| `probability_models.yaml` | Probability models | Elo, edge detection |
| `markets.yaml` | Platform config | Kalshi, market filters |
| `data_sources.yaml` | API endpoints | ESPN, historical data |
| `system.yaml` | System settings | Database, logging |

### Common Configuration Changes

| To Do This | Edit This File | Change This Setting |
|-----------|----------------|---------------------|
| Increase position size | `trading.yaml` | `position_sizing.kelly.max_position_dollars` |
| Add new sport | `markets.yaml` | Add to `categories.sports.leagues` |
| Change edge threshold | `trading.yaml` | `position_sizing.kelly.min_edge_threshold` |
| Enable new strategy | `trade_strategies.yaml` | Set strategy `enabled: true` |
| Adjust stop loss | `position_management.yaml` | `exit_rules.discretionary.stop_loss` |
| Change polling frequency | `data_sources.yaml` | `polling.interval_seconds` |
| Switch to production | `trading.yaml`, `markets.yaml` | `environment: prod`, `active_environment: "prod"` |

---

**Document Version:** 3.0
**Last Updated:** 2025-10-16
**Purpose:** Comprehensive configuration guide matching actual implementation
**Status:** Current and validated against actual YAML files and env.template
