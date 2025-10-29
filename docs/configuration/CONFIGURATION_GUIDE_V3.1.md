# Precog Configuration Guide

---
**Version:** 3.1
**Last Updated:** 2025-10-21
**Status:** ✅ Current - Matches actual implementation
**Changes in v3.1:**
- **CRITICAL**: Added Phase 5 position monitoring configuration (dynamic frequencies)
- Added exit priority hierarchy documentation (4 levels: CRITICAL/HIGH/MEDIUM/LOW)
- Added urgency-based execution strategies (market orders, price walking)
- Added partial exit staging configuration (2-stage: 50% @ +15%, 25% @ +25%)
- Added user customization evolution (Phase 1 → 1.5 → 4-5)
- Added configuration hierarchy section (3-level: Database > YAML > Code)
- Added YAML validation and consistency checking
- Added liquidity threshold documentation
- Removed edge_reversal exit condition (deprecated, redundant)
- Updated all monitoring frequency references (30s normal, 5s urgent)
- Updated exit condition count (11 → 10)

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
3. **Database Overrides** (Phase 1.5+) - Runtime adjustments via `config_overrides` table

---

## Configuration Hierarchy

### Phase 1: 2-Level Hierarchy (Current)

```
Priority: YAML File > Code Defaults

┌─────────────────┐
│  YAML File      │  ← User edits directly (restart required)
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  Code Defaults  │  ← Hardcoded fallback values
└─────────────────┘
```

**Example:**
```python
# Config class
config = Config()

# 1. Check position_management.yaml for 'exit_rules.profit_targets.high_confidence'
# 2. If not found, use code default: 0.25
profit_target = config.get('exit_rules.profit_targets.high_confidence', default=0.25)
```

### Phase 1.5: 3-Level Hierarchy (Planned)

```
Priority: Database Override > YAML File > Code Defaults

┌─────────────────┐
│  Database       │  ← Per-user overrides (no restart)
│  Override       │
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  YAML File      │  ← Global defaults
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  Code Defaults  │  ← Hardcoded fallback values
└─────────────────┘
```

**Example:**
```python
# Config class (Phase 1.5)
config = Config(user_id=123)

# 1. Check user_config_overrides table for user 123
# 2. If not found, check position_management.yaml
# 3. If not found, use code default: 0.25
profit_target = config.get('exit_rules.profit_targets.high_confidence', default=0.25)
```

### Phase 4-5: Method-Based Configuration (Planned)

**Complete configuration bundled as "Methods"**

```
Priority: Active Method Config > Database Override > YAML > Code

┌─────────────────┐
│  Active Method  │  ← Complete bundled config for this trade
│  Configuration  │     (strategy + model + position + risk + execution)
└────────┬────────┘
         │ Parameter not in method?
         ▼
┌─────────────────┐
│  User Override  │  ← User's global overrides
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  YAML File      │  ← System defaults
└────────┬────────┘
         │ Not found?
         ▼
┌─────────────────┐
│  Code Defaults  │  ← Hardcoded fallback
└─────────────────┘
```

**See ADR-021 and USER_CUSTOMIZATION_STRATEGY_V1_0 for details.**

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

## User Customization

### Phase 1: YAML Editing (Current)

**How to Customize:**

1. Open `config/position_management.yaml` (or other config file)
2. Find parameter marked with `# user-customizable`
3. Edit value within safe range
4. Save file
5. Restart application

**Example:**

```yaml
# position_management.yaml
trailing_stop:
  activation_threshold: 0.10  # user-customizable: 0.05-0.20
  initial_distance: 0.05      # user-customizable: 0.02-0.10
```

**To change trailing stop activation to 15%:**
```yaml
trailing_stop:
  activation_threshold: 0.15  # Changed from 0.10
  initial_distance: 0.05
```

**Limitations:**
- ❌ Requires application restart
- ❌ Single configuration for all trades
- ❌ No runtime adjustments

### Phase 1.5: Database Overrides (Planned)

**How It Will Work:**

1. Log into webapp
2. Navigate to Settings > Position Management
3. Override any `# user-customizable` parameter
4. Changes take effect immediately (no restart)
5. Fallback to YAML if no override set

**Database Schema:**
```sql
CREATE TABLE user_config_overrides (
    override_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    config_key VARCHAR(200) NOT NULL,
    config_value JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, config_key)
);
```

**Example:**
```
User: Alice (user_id=123)
Override: exit_rules.profit_targets.high_confidence = 0.20

Config resolution:
1. Check database: 0.20 ✓ (Alice's override)
2. If not found, check YAML: 0.25
3. If not found, use code default: 0.25

Result: Alice uses 0.20, everyone else uses 0.25
```

### Phase 4-5: Method Templates (Planned)

**Complete bundled configurations for different trading styles.**

**Available Templates:**
- **Conservative NFL**: Tight stops, small positions, simple execution
- **Aggressive NFL**: Loose stops, larger positions, advanced execution
- **Arbitrage**: Settlement arb focus, high Kelly, market orders
- **Custom**: Build from scratch

**Method Structure:**
```json
{
    "method_name": "Conservative NFL",
    "method_version": "v1.0",
    "strategy_id": 1,
    "model_id": 1,

    "position_mgmt_config": {
        "trailing_stop": {"enabled": true, "activation_threshold": 0.10},
        "profit_targets": {"high_confidence": 0.20},
        "stop_loss": {"high_confidence": -0.10},
        "partial_exits": {"enabled": true}
    },

    "risk_config": {
        "kelly_fraction": 0.15,
        "max_position_size_dollars": 500
    },

    "execution_config": {
        "default_order_type": "limit",
        "max_slippage_percent": 0.01
    }
}
```

**User Workflow:**
1. Select template (e.g., "Conservative NFL")
2. Clone and customize
3. A/B test against other methods
4. Compare performance metrics
5. Iterate with new versions

**See ADR-021 for complete specification.**

### What's Customizable vs. Not

**✅ User-Customizable Parameters:**

**Position Management:**
- Monitoring frequencies (30s → your choice)
- Trailing stop settings (activation, distance, tightening)
- Profit targets (high/medium/low confidence)
- Stop losses (high/medium/low confidence)
- Partial exit staging (thresholds, percentages)
- Liquidity thresholds (max spread, min volume)
- Exit condition enable/disable (except CRITICAL)

**Risk Management:**
- Kelly fractions (default and per-sport)
- Position limits (max size, total exposure)
- Daily loss limits
- Edge thresholds

**Execution:**
- Order types (limit/market)
- Slippage tolerance
- Timeout durations
- Price walking parameters (max_walks)

**❌ NOT Customizable (Safety Constraints):**

**Circuit Breakers:**
- `consecutive_losses` = 5 (hardcoded)
- `rapid_loss_dollars` = $200 (hardcoded)
- **Reason:** Prevent catastrophic losses

**API Limits:**
- `max_api_calls_per_minute` = 60 (hardcoded)
- **Reason:** Prevent API bans

**Critical Exits:**
- `stop_loss.enabled` = true (always on)
- `circuit_breaker.enabled` = true (always on)
- **Reason:** Capital protection mandatory

**Absolute Caps:**
- Max position size: $5000 maximum
- Daily loss limit: $2000 maximum
- **Reason:** Prevent account bankruptcy

### Safe Ranges

| Parameter | Min | Default | Max | Danger Zone |
|-----------|-----|---------|-----|-------------|
| `kelly_fraction` | 0.05 | 0.25 | 0.50 | >0.50 (over-betting) |
| `trailing_stop.activation` | 0.05 | 0.10 | 0.20 | >0.20 (too loose) |
| `profit_target.high` | 0.10 | 0.25 | 0.50 | <0.05 (too greedy) |
| `stop_loss.high` | -0.05 | -0.15 | -0.40 | <-0.50 (too loose) |
| `max_position_size` | $10 | $1000 | $5000 | >$5000 (too risky) |
| `normal_frequency` | 10s | 30s | 120s | <10s (API abuse) |

**⚠️ Danger Warning:**

Changing these parameters outside safe ranges can:
- Lead to over-betting (bankrupt account)
- Cause API bans (rate limit violations)
- Result in poor risk management (large losses)
- Reduce profitability (exits too early/late)

**Always test changes in paper trading mode first!**

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
  normal_frequency: 30      # Check every 30 seconds (normal conditions)
  urgent_frequency: 5       # Check every 5 seconds (urgent conditions)

  urgent_conditions:
    near_stop_loss_pct: 0.02      # Within 2% of stop loss
    near_profit_target_pct: 0.02  # Within 2% of profit target
    near_trailing_stop_pct: 0.02  # Within 2% of trailing stop

  price_cache_ttl_seconds: 10        # Cache prices for 10 seconds
  max_api_calls_per_minute: 60      # Safety limit (NOT user-customizable)

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

### Dynamic Monitoring Configuration (Phase 5)

The position monitoring system uses **dynamic frequencies** to balance API efficiency with responsiveness.

#### Monitoring Frequency

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `normal_frequency` | int | 30 | 10-120 | Seconds between checks (normal) |
| `urgent_frequency` | int | 5 | 3-15 | Seconds between checks (urgent) |

**When Urgent Mode Activates:**

The system automatically switches to urgent mode (5s checks) when position is within 2% of any threshold:
- Near stop loss (2% away)
- Near profit target (2% away)
- Near trailing stop (2% away)

**Example:**
```
Time 0:00 - Position at +10% (normal mode, check every 30s)
Time 0:30 - Position at +12% (normal mode)
Time 1:00 - Position at +13.5% (URGENT: within 2% of +15% target)
Time 1:05 - Position at +14.2% (urgent mode, check every 5s)
Time 1:10 - Position at +15.1% (PROFIT TARGET HIT → EXIT)
```

Without urgent mode, might miss exit at +15% and wait until next 30s check.

#### API Rate Management

```yaml
price_cache_ttl_seconds: 10        # Cache prices for 10 seconds
max_api_calls_per_minute: 60      # Safety limit
```

**Calculation:**
- Normal: 20 positions × (60s / 30s) = 40 calls/min ✓
- Urgent: 5 positions × (60s / 5s) = 60 calls/min ✓
- Cache reduces load by ~66%

**Safety Constraints:**
- `max_api_calls_per_minute` is NOT user-customizable (safety)
- System auto-throttles if approaching limit
- Urgent checks prioritized over normal checks

#### Best Practices

✅ **DO:**
- Use 30s for normal (balances responsiveness and API usage)
- Use 5s for urgent (timely exits without hammering API)
- Keep cache at 10s (acceptable staleness)

❌ **DON'T:**
- Set normal_frequency < 10s (API abuse)
- Set urgent_frequency < 3s (excessive API load)
- Disable caching (will hit rate limits)

### Exit Priority Hierarchy (Phase 5)

Exit conditions are organized into **4 priority levels**. When multiple conditions trigger simultaneously, the highest priority wins.

```yaml
exit_priorities:
  CRITICAL:
    - stop_loss
    - circuit_breaker
  HIGH:
    - trailing_stop
    - time_based_urgent
    - liquidity_dried_up
  MEDIUM:
    - profit_target
    - partial_exit_target
  LOW:
    - early_exit
    - edge_disappeared
    - rebalance
```

**Priority Levels:**

| Level | Purpose | Exit Speed | Price Optimization |
|-------|---------|------------|-------------------|
| CRITICAL | Capital protection | IMMEDIATE | None (market orders) |
| HIGH | Risk management | FAST | Minimal |
| MEDIUM | Profit taking | MODERATE | Balanced |
| LOW | Position optimization | PATIENT | Maximum |

**Conflict Resolution Example:**
- Position triggers both `profit_target` (MEDIUM) and `trailing_stop` (HIGH)
- System executes `trailing_stop` exit (higher priority)
- Ensures risk management takes precedence over profit taking

### Exit Execution Strategies (Phase 5)

Each priority level has a distinct execution strategy optimized for urgency vs. price:

```yaml
exit_execution:
  CRITICAL:
    order_type: market           # Market order (immediate fill)
    timeout_seconds: 5
    retry_strategy: immediate_market

  HIGH:
    order_type: limit            # Limit order (reduce slippage)
    price_strategy: aggressive   # Best bid + $0.01
    timeout_seconds: 10
    retry_strategy: walk_then_market
    max_walks: 2

  MEDIUM:
    order_type: limit
    price_strategy: fair         # Best bid (no premium)
    timeout_seconds: 30
    retry_strategy: walk_price
    max_walks: 5

  LOW:
    order_type: limit
    price_strategy: conservative # Best bid - $0.01
    timeout_seconds: 60
    retry_strategy: walk_slowly
    max_walks: 10
```

#### Price Walking Explained

**What is Price Walking?**

When a limit order doesn't fill, progressively adjust price toward market until filled.

**Example (MEDIUM priority, fair limit):**

```
Market: Best bid $0.65, Best ask $0.68

Attempt 1: Limit at $0.65 (best bid) → Wait 30s → Not filled
Attempt 2: Limit at $0.66 (walk +$0.01) → Wait 30s → Not filled
Attempt 3: Limit at $0.67 (walk +$0.01) → Wait 30s → Not filled
Attempt 4: Limit at $0.68 (best ask) → Wait 30s → FILLED ✓

Total time: 2 minutes
Fill price: $0.68 (vs $0.70 if used market order immediately)
Savings: $0.02 per contract × 100 contracts = $2.00 saved
```

**Price Strategies:**

| Strategy | Starting Price | Rationale |
|----------|---------------|-----------|
| aggressive | best_bid + $0.01 | Pay premium for speed (HIGH priority) |
| fair | best_bid | Market price, no premium (MEDIUM priority) |
| conservative | best_bid - $0.01 | Wait for better price (LOW priority) |

**HIGH Priority Walking Example (Trailing Stop):**

```
Trailing stop triggers at $0.67

Attempt 1: Limit at $0.68 (best bid + $0.01, aggressive) → Wait 10s
If not filled:
Attempt 2: Limit at $0.67 (best bid) → Wait 10s
If not filled:
Attempt 3: Market order → Fill immediately

Total max time: 20 seconds (fast exit to lock in profits)
```

### Partial Exit Staging (Phase 5)

Two-stage profit taking with trailing stop for remainder:

```yaml
partial_exits:
  enabled: true
  stages:
    - name: "first_target"
      profit_threshold: 0.15  # +15% profit
      exit_percentage: 50     # Exit 50% of position
      description: "Initial profit taking to reduce risk"

    - name: "second_target"
      profit_threshold: 0.25  # +25% profit
      exit_percentage: 25     # Exit another 25%
      description: "Further de-risking, let 25% ride with trailing stop"

# Remaining 25% rides with trailing stop for maximum upside
```

**Example P&L:**

```
Entry: 100 contracts @ $0.60, invested $60.00

Stage 1 (+15% profit): Exit 50 contracts @ $0.69
  Revenue: 50 × $0.69 = $34.50
  Profit on stage 1: $34.50 - (50 × $0.60) = $4.50
  Remaining: 50 contracts

Stage 2 (+25% profit): Exit 25 contracts @ $0.75
  Revenue: 25 × $0.75 = $18.75
  Profit on stage 2: $18.75 - (25 × $0.60) = $3.75
  Remaining: 25 contracts

Trailing Stop Exit: 25 contracts @ $0.88 (trailing stop triggered)
  Revenue: 25 × $0.88 = $22.00
  Profit on remainder: $22.00 - (25 × $0.60) = $7.00

Total Profit: $4.50 + $3.75 + $7.00 = $15.25 on $60 invested (25.4% ROI)
```

### Liquidity Thresholds

Configuration to handle illiquid markets:

```yaml
liquidity:
  max_spread: 0.03  # Maximum 3¢ spread
  min_volume: 50    # Minimum 50 contracts

  exit_on_illiquid: true   # Auto-exit if market becomes illiquid
  alert_on_illiquid: true  # Alert user when illiquidity detected
```

**Parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `max_spread` | decimal | 0.03 | 0.01-0.10 | Maximum bid-ask spread |
| `min_volume` | int | 50 | 10-500 | Minimum contracts required |
| `exit_on_illiquid` | bool | true | - | Auto-exit on illiquidity |
| `alert_on_illiquid` | bool | true | - | Alert user |

**When Liquidity Dried Up Exit Triggers:**

```
Condition 1: Spread > max_spread (3¢)
    Example: Best bid $0.60, best ask $0.64 → Spread $0.04 > $0.03 ✓ TRIGGER

Condition 2: Volume < min_volume (50 contracts)
    Example: Order book shows only 30 contracts total → < 50 ✓ TRIGGER

Either condition → liquidity_dried_up exit (HIGH priority)
```

**Why This Matters:**

In illiquid markets:
- ❌ Hard to exit position (no buyers)
- ❌ High slippage (wide spreads)
- ❌ Price manipulation risk

Auto-exit protects capital by getting out before liquidity disappears completely.

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

## YAML Validation

### Validation Rules

All YAML files are validated on load to prevent configuration errors.

#### Type Validation

```yaml
# CORRECT
kelly_fraction: 0.25          # float ✓
max_position_size: 1000       # int ✓
enabled: true                 # bool ✓

# INCORRECT
kelly_fraction: "0.25"        # string ✗ (should be float)
max_position_size: 1000.5     # float ✗ (should be int)
enabled: "true"               # string ✗ (should be bool)
```

#### Range Validation

```yaml
# CORRECT
kelly_fraction: 0.25          # 0.05 ≤ value ≤ 0.50 ✓

# INCORRECT
kelly_fraction: 0.60          # > 0.50 ✗ (over-betting, dangerous)
kelly_fraction: 0.02          # < 0.05 ✗ (too conservative, system won't trade)
```

#### Required Fields

All configuration files have required fields that must be present:

```yaml
# position_management.yaml - REQUIRED FIELDS
monitoring:
  normal_frequency: 30        # Required
  urgent_frequency: 5         # Required

exit_priorities:              # Required
  CRITICAL: [...]
  HIGH: [...]
  MEDIUM: [...]
  LOW: [...]

exit_execution:               # Required
  CRITICAL: { ... }
  HIGH: { ... }
  MEDIUM: { ... }
  LOW: { ... }
```

### Validation on Startup

**System Behavior:**

```
Starting Precog Trading Platform...
├─ Loading configuration files...
│  ├─ trading.yaml ✓
│  ├─ position_management.yaml ✓
│  ├─ trade_strategies.yaml ✓
│  ├─ probability_models.yaml ✓
│  ├─ markets.yaml ✓
│  ├─ data_sources.yaml ✓
│  └─ system.yaml ✓
├─ Validating configuration...
│  ├─ Type validation ✓
│  ├─ Range validation ✓
│  ├─ Required fields ✓
│  └─ Cross-file consistency ✓
└─ Configuration loaded successfully ✓

Ready to trade.
```

**If Validation Fails:**

```
Starting Precog Trading Platform...
├─ Loading configuration files...
│  ├─ trading.yaml ✓
│  ├─ position_management.yaml ✗

ERROR: Configuration validation failed

File: config/position_management.yaml
Line 15: kelly_fraction: 0.60

Error: Value out of range
  - Current: 0.60
  - Allowed: 0.05 - 0.50
  - Reason: Values > 0.50 constitute over-betting (Kelly Criterion violation)

Fix: Edit config/position_management.yaml and restart

SYSTEM WILL NOT START WITH INVALID CONFIGURATION
```

### Manual Validation Command

```bash
# Validate all YAML files without starting system
$ python -m precog.config.validate

Validating configuration files...
✓ trading.yaml (52 parameters)
✓ position_management.yaml (84 parameters)
✓ trade_strategies.yaml (31 parameters)
✓ probability_models.yaml (23 parameters)
✓ markets.yaml (18 parameters)
✓ data_sources.yaml (15 parameters)
✓ system.yaml (27 parameters)

All configuration files valid ✓
```

### Common Validation Errors

**1. Invalid Type**
```yaml
# ERROR
max_position_size: "1000"  # String instead of int

# FIX
max_position_size: 1000
```

**2. Out of Range**
```yaml
# ERROR
kelly_fraction: 0.75  # > 0.50 maximum

# FIX
kelly_fraction: 0.25
```

**3. Missing Required Field**
```yaml
# ERROR
exit_priorities:
  CRITICAL: [...]
  # Missing HIGH, MEDIUM, LOW

# FIX
exit_priorities:
  CRITICAL: [...]
  HIGH: [...]
  MEDIUM: [...]
  LOW: [...]
```

**4. Invalid Reference**
```yaml
# ERROR
methods:
  my_method:
    strategy_id: 999  # Strategy doesn't exist

# FIX (check strategies table for valid IDs)
methods:
  my_method:
    strategy_id: 1
```

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

## Appendix A: Configuration Consistency Check

Use this checklist to verify configuration consistency across files.

### Core Parameters Alignment

#### Kelly Fractions

| File | Parameter | Value | Status |
|------|-----------|-------|--------|
| trading.yaml | kelly.default_fraction | 0.25 | ✓ Must match |
| trading.yaml | kelly.sport_fractions.nfl | 0.25 | ✓ NFL specific |
| trading.yaml | kelly.sport_fractions.nba | 0.22 | ✓ NBA specific |
| trading.yaml | kelly.sport_fractions.tennis | 0.18 | ✓ Tennis specific |

**Verification:**
```bash
$ grep -r "kelly_fraction" config/*.yaml
```

#### Position Limits

| File | Parameter | Value | Status |
|------|-----------|-------|--------|
| trading.yaml | position_limits.max_position_size_dollars | 1000 | ✓ Must match |
| trading.yaml | position_limits.max_total_exposure_dollars | 10000 | ✓ Must match |

#### Exit Conditions

| File | Parameter | Count | Status |
|------|-----------|-------|--------|
| position_management.yaml | exit_priorities | 10 total | ✓ Correct |
| position_management.yaml | exit_priorities.CRITICAL | 2 conditions | ✓ Correct |
| position_management.yaml | exit_priorities.HIGH | 3 conditions | ✓ Correct |
| position_management.yaml | exit_priorities.MEDIUM | 2 conditions | ✓ Correct |
| position_management.yaml | exit_priorities.LOW | 3 conditions | ✓ Correct |

**Verification:**
```bash
$ python -m precog.config.audit

Running configuration audit...
├─ Parameter consistency ✓
├─ Cross-file references ✓
├─ Exit condition count ✓
└─ Type validation ✓

Audit complete: No issues found
```

### Common Inconsistencies

**1. Mismatched Kelly Fractions**
```
PROBLEM: trading.yaml has kelly_fraction: 0.25, but method config has 0.30
FIX: Methods can override defaults (this is OK)
```

**2. Out-of-Sync Limits**
```
PROBLEM: trading.yaml max_position_size: 1000, but code has 1500
FIX: Update code to read from YAML (code should not hardcode limits)
```

**3. Deprecated Exit Condition References**
```
PROBLEM: Code references exit condition "edge_reversal" but not in YAML
FIX: edge_reversal was deprecated in V3.1 - functionality covered by early_exit and edge_disappeared
```

### Automated Audit

Run full consistency audit:

```bash
$ python -m precog.config.audit --verbose

Configuration Audit Report
==========================

1. Parameter Consistency
   ✓ Kelly fractions consistent across files
   ✓ Position limits consistent
   ✓ Exit priorities complete

2. Exit Conditions
   ✓ 10 conditions defined (edge_reversal removed in v3.1)
   ✓ All conditions mapped to priorities
   ✓ No deprecated references

3. Type Validation
   ✓ All parameters have correct types
   ✓ All ranges valid

4. Required Fields
   ✓ All required fields present

ISSUES FOUND: 0
STATUS: All configurations valid ✓
```

### Deprecated Features

**edge_reversal Exit Condition (Removed in V3.1)**

**Status:** DEPRECATED
**Removed:** 2025-10-21
**Reason:** Redundant functionality

**What it did:**
- Triggered exit when edge reversed from positive to negative

**Replacement:**
- `early_exit`: Triggers when edge drops below absolute threshold (e.g., 2%)
- `edge_disappeared`: Triggers when edge turns negative

**Migration:** No action required. Existing coverage is complete through early_exit and edge_disappeared.

If you see references to `edge_reversal` in code or config:
1. Remove the reference
2. Ensure `early_exit` and `edge_disappeared` are enabled
3. Run configuration audit to verify

---

**Document Version:** 3.1
**Last Updated:** 2025-10-21
**Purpose:** Comprehensive configuration guide matching actual implementation (Phase 5 enhancements)
**Status:** Current and validated against actual YAML files, env.template, and Phase 5 requirements
