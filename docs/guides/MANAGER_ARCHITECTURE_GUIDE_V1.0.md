# Manager Architecture Guide V1.0

**Document Type:** Implementation Guide
**Status:** ✅ Active
**Version:** 1.0
**Created:** 2025-11-17
**Last Updated:** 2025-11-17
**Owner:** Development Team
**Applies to:** Phases 1.5+

---

## Executive Summary

This guide explains the **architecture and design** of Precog's four core managers:
- **Model Manager**: Probability model lifecycle (immutable versions)
- **Strategy Manager**: Trading strategy lifecycle (immutable versions)
- **Position Manager**: Active position tracking (SCD Type 2 versioning)
- **Config Manager**: System configuration (YAML + environment variables)

**Key Design Principles:**
- ✅ **Immutable Versions** (Models + Strategies): Config never changes after creation
- ✅ **SCD Type 2** (Positions): Full history tracking for frequently-changing data
- ✅ **Two-Level Config System**: Database configs (versioned) vs file configs (system-wide)
- ✅ **Pure psycopg2**: 100% raw SQL, no ORM
- ✅ **Decimal Precision**: All prices/probabilities use `DECIMAL(10,4)`

---

## Table of Contents

1. [Model Manager Architecture](#1-model-manager-architecture)
2. [Strategy Manager Architecture](#2-strategy-manager-architecture)
3. [Position Manager Architecture](#3-position-manager-architecture)
4. [Config Manager Architecture](#4-config-manager-architecture)
5. [Design Principles](#5-design-principles)
6. [Documentation References](#6-documentation-references)

---

## 1. Model Manager Architecture

### **Purpose**
Manages **probability models** that predict win probabilities for markets. Each model is an **immutable version** (config can't change once created).

### **Implementation**
- **File**: `src/precog/analytics/model_manager.py` (212 lines)
- **Coverage**: 84.86% (Phase 1.5)
- **Target Coverage**: 85% (Business Logic tier)
- **Database**: `probability_models` table (19 fields)

### **Database Schema**: `probability_models`

| Column | Type | Immutable? | Valid Values | Purpose |
|--------|------|------------|--------------|---------|
| `model_id` | SERIAL PRIMARY KEY | ✅ | Auto-increment | Unique identifier |
| `model_name` | VARCHAR | ✅ | 'elo_nfl', 'regression_nba', 'ensemble_v1' | Descriptive name |
| `model_version` | VARCHAR | ✅ | **'v1.0', 'v1.1', 'v2.0'** | Semantic versioning |
| `approach` | VARCHAR | ✅ | **'elo', 'regression', 'ensemble', 'neural_net'** | **HOW** it works |
| `domain` | VARCHAR | ✅ | **'nfl', 'nba', 'elections', 'economics', NULL** | **WHICH** markets (NULL = multi-domain) |
| `config` | JSONB | ✅ **IMMUTABLE** | `{"k_factor": 20, "base_elo": 1500}` | Model parameters (**NEVER** changes!) |
| `status` | VARCHAR | ❌ **MUTABLE** | **'draft', 'training', 'validating', 'active', 'deprecated'** | Lifecycle state |
| `training_start_date` | DATE | ✅ | Date | When training data starts |
| `training_end_date` | DATE | ✅ | Date | When training data ends |
| `training_sample_size` | INT | ✅ | Integer | Number of training samples |
| `validation_accuracy` | DECIMAL(10,4) | ❌ **MUTABLE** | 0.0000 - 1.0000 | Accuracy on validation set |
| `validation_calibration` | DECIMAL(10,4) | ❌ **MUTABLE** | 0.0000 - 1.0000 | Calibration score |
| `validation_sample_size` | INT | ✅ | Integer | Validation set size |
| `activated_at` | TIMESTAMP | ❌ **MUTABLE** | Timestamp | When promoted to 'active' |
| `deactivated_at` | TIMESTAMP | ❌ **MUTABLE** | Timestamp | When demoted from 'active' |
| `notes` | TEXT | ❌ **MUTABLE** | Free text | Human notes |
| `created_at` | TIMESTAMP | ✅ | Auto-generated | Creation timestamp |
| `description` | TEXT | ✅ | Free text | Model description |
| `created_by` | VARCHAR | ✅ | 'claude', 'user_name' | Who created it |

**Unique Constraint:** `(model_name, model_version)` - can't create 'elo_nfl' v1.0 twice

### **Status Lifecycle**

```
draft → training → validating → active → deprecated
  ↓         ↓          ↓           ↓
(editing) (training) (testing) (production) (retired)
```

**Valid Transitions** (enforced by `_validate_status_transition()`):
- `draft` → `training`, `deprecated`
- `training` → `validating`, `draft`, `deprecated`
- `validating` → `active`, `training`, `deprecated`
- `active` → `deprecated`
- `deprecated` → (terminal state)

### **Why IMMUTABLE config?**

**Problem:** If we allowed changing k_factor from 20 → 30 on existing model v1.0:
- Can't reproduce old predictions (model behavior changed!)
- Can't A/B test (model v1.0 means different things at different times)
- Can't attribute trades (did this trade use k=20 or k=30 version?)

**Solution:** Config is IMMUTABLE. To change parameters:
1. Create NEW version: `elo_nfl v1.1` with `k_factor: 30`
2. Test v1.1 in parallel with v1.0
3. Compare performance, choose winner
4. Deprecate loser

**Benefits:**
- ✅ **Reproducibility**: Model v1.0 always behaves the same
- ✅ **A/B Testing**: Compare v1.0 (k=20) vs v1.1 (k=30) side-by-side
- ✅ **Attribution**: Every trade links to exact model version used
- ✅ **Audit Trail**: Know exactly which config generated which prediction

### **Core Methods**

```python
# Create new model version (config is IMMUTABLE)
model_id = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    approach="elo",
    domain="nfl",
    config={"k_factor": 20, "base_elo": 1500},  # Can't change later!
    training_start_date="2024-01-01",
    training_end_date="2024-12-31",
)

# Update status (MUTABLE - status can change)
manager.update_status(model_id, "training")
manager.update_status(model_id, "validating")
manager.update_status(model_id, "active")  # Now in production!

# Update validation metrics (MUTABLE - metrics can change)
manager.update_validation_metrics(
    model_id,
    accuracy=Decimal("0.7845"),
    calibration=Decimal("0.0234"),
)

# Get active models
active_models = manager.get_models_by_status("active")
```

### **Reference**
- **Schema**: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md` (lines 277-374)
- **Implementation**: `src/precog/analytics/model_manager.py`
- **Tests**: `tests/unit/analytics/test_model_manager.py` (36 tests, 97.3% pass rate)
- **Requirements**: REQ-MODEL-001 through REQ-MODEL-005
- **ADRs**: ADR-019 (Model Versioning), ADR-002 (Decimal Precision)

---

## 2. Strategy Manager Architecture

### **Purpose**
Manages **trading strategies** that decide WHEN to enter/exit trades. Each strategy is an **immutable version** (same pattern as models).

### **Implementation**
- **File**: `src/precog/trading/strategy_manager.py` (274 lines)
- **Coverage**: 84.36% (Phase 1.5)
- **Target Coverage**: 85% (Business Logic tier)
- **Database**: `strategies` table (20 fields)

### **Database Schema**: `strategies`

| Column | Type | Immutable? | Valid Values | Purpose |
|--------|------|------------|--------------|---------|
| `strategy_id` | SERIAL PRIMARY KEY | ✅ | Auto-increment | Unique identifier |
| `platform_id` | VARCHAR | ✅ | 'kalshi', 'polymarket' | Which platform |
| `strategy_name` | VARCHAR | ✅ | 'halftime_entry', 'underdog_fade' | Descriptive name |
| `strategy_version` | VARCHAR | ✅ | **'v1.0', 'v1.1', 'v2.0'** | Semantic versioning |
| `approach` | VARCHAR | ✅ | **'value', 'arbitrage', 'momentum', 'mean_reversion'** | **HOW** it trades |
| `domain` | VARCHAR | ✅ | **'nfl', 'nba', 'elections', 'economics', NULL** | **WHICH** markets (NULL = multi-domain) |
| `config` | JSONB | ✅ **IMMUTABLE** | `{"min_edge": "0.05", "max_exposure": "1000.00"}` | Strategy parameters (**NEVER** changes!) |
| `status` | VARCHAR | ❌ **MUTABLE** | **'draft', 'testing', 'active', 'inactive', 'deprecated'** | Lifecycle state |
| `activated_at` | TIMESTAMP | ❌ **MUTABLE** | Timestamp | When promoted to 'active' |
| `deactivated_at` | TIMESTAMP | ❌ **MUTABLE** | Timestamp | When demoted from 'active' |
| `notes` | TEXT | ❌ **MUTABLE** | Free text | Human notes |
| `paper_trades_count` | INT | ❌ **MUTABLE** | Integer | Number of paper trades |
| `paper_roi` | DECIMAL(10,4) | ❌ **MUTABLE** | -1.0000 to ∞ | Paper trading ROI |
| `live_trades_count` | INT | ❌ **MUTABLE** | Integer | Number of live trades |
| `live_roi` | DECIMAL(10,4) | ❌ **MUTABLE** | -1.0000 to ∞ | Live trading ROI |
| `created_at` | TIMESTAMP | ✅ | Auto-generated | Creation timestamp |
| `updated_at` | TIMESTAMP | ❌ **MUTABLE** | Auto-updated | Last modification |
| `description` | TEXT | ✅ | Free text | Strategy description |
| `created_by` | VARCHAR | ✅ | 'claude', 'user_name' | Who created it |

**Unique Constraint:** `(strategy_name, strategy_version)` - can't create 'halftime_entry' v1.0 twice

### **Status Lifecycle**

```
draft → testing → active → inactive → deprecated
  ↓       ↓         ↓         ↓
(dev)  (paper)  (live)    (paused)  (retired)
```

**Valid Transitions** (enforced by `_validate_status_transition()`):
- `draft` → `testing`, `deprecated`
- `testing` → `active`, `draft`, `deprecated`
- `active` → `inactive`, `deprecated`
- `inactive` → `active`, `deprecated`
- `deprecated` → (terminal state)

### **Why Two ROI Fields?**

**paper_roi** (Paper Trading ROI):
- Performance in **backtesting** (Phase 4)
- Tests strategy with historical data
- **No real money** at risk
- Example: `paper_roi: 0.1845` = 18.45% return in backtest

**live_roi** (Live Trading ROI):
- Performance in **real trading** (Phase 5+)
- Tests strategy with real money
- **Actual profit/loss** tracking
- Example: `live_roi: 0.1234` = 12.34% return in live trading

**Promotion Criteria:**
1. Strategy in `testing` status (paper trading)
2. `paper_roi > 15%` (beats benchmark)
3. `paper_trades_count > 100` (sufficient sample size)
4. Manual approval → Promote to `active` (live trading)

### **Core Methods**

```python
# Create new strategy version (config is IMMUTABLE)
strategy_id = manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0",
    approach="value",
    domain="nfl",
    config={
        "min_edge": "0.05",
        "max_exposure": "1000.00",
        "kelly_fraction": "0.25",
    },  # Can't change later!
    platform_id="kalshi",
)

# Update status (MUTABLE - status can change)
manager.update_status(strategy_id, "testing")
manager.update_status(strategy_id, "active")  # Now in production!

# Update metrics (MUTABLE - metrics can change)
manager.update_metrics(
    strategy_id,
    paper_trades_count=150,
    paper_roi=Decimal("0.1845"),  # 18.45% return!
)

# Get active strategies
active_strategies = manager.get_strategies_by_status("active")
```

### **Reference**
- **Schema**: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md` (lines 376-476)
- **Implementation**: `src/precog/trading/strategy_manager.py`
- **Tests**: `tests/unit/trading/test_strategy_manager.py` (13 tests, 100% pass rate)
- **Requirements**: REQ-STRAT-001 through REQ-STRAT-005
- **ADRs**: ADR-018 (Strategy Versioning), ADR-002 (Decimal Precision)

---

## 3. Position Manager Architecture

### **Purpose**
Manages **active trading positions** with **SCD Type 2 versioning** (positions change frequently, unlike strategies/models).

### **Implementation**
- **File**: `src/precog/trading/position_manager.py` (NOT YET IMPLEMENTED - Phase 1.5)
- **Target Coverage**: **90%** (Critical Path tier - handles real money!)
- **Database**: `positions` table (21 fields)

### **Database Schema**: `positions`

| Column | Type | Valid Values | Purpose |
|--------|------|--------------|---------|
| `position_id` | SERIAL PRIMARY KEY | Auto-increment | Unique identifier |
| `market_id` | VARCHAR | Foreign key to markets | Which market |
| `platform_id` | VARCHAR | 'kalshi', 'polymarket' | Which platform |
| `side` | VARCHAR | **'yes', 'no'** | Long yes or long no |
| `entry_price` | DECIMAL(10,4) | 0.0001 - 0.9999 | Entry price |
| `quantity` | INT | 1 - 10000 | Number of contracts |
| `fees` | DECIMAL(10,4) | 0.0000 - ∞ | Transaction fees |
| `status` | VARCHAR | **'open', 'closed', 'settled'** | Position state |
| `unrealized_pnl` | DECIMAL(10,4) | -∞ to ∞ | Current P&L (open) |
| `realized_pnl` | DECIMAL(10,4) | -∞ to ∞ | Final P&L (closed) |
| `current_price` | DECIMAL(10,4) | 0.0001 - 0.9999 | Latest market price |
| `unrealized_pnl_pct` | DECIMAL(6,4) | -∞ to ∞ | P&L as percentage |
| `last_update` | TIMESTAMP | Timestamp | Last monitoring check |
| `trailing_stop_state` | JSONB | `{"active": true, "peak_price": "0.75", ...}` | Trailing stop data |
| `exit_reason` | VARCHAR(50) | 'stop_loss', 'trailing_stop', 'profit_target', etc. | Why exited |
| `exit_priority` | VARCHAR(20) | **'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'** | Exit urgency |
| `created_at` | TIMESTAMP | Auto-generated | Creation timestamp |
| `updated_at` | TIMESTAMP | Auto-updated | Last modification |
| `row_current_ind` | BOOLEAN | **TRUE/FALSE** | **SCD Type 2: Is this the current row?** |

### **Why SCD Type 2 for Positions?**

**Problem with Immutable Versions (like models/strategies):**
- Positions change **every second** (price updates)
- Immutable versions would create **thousands of rows**:
  - `position_123 v1.0` (price = $0.50)
  - `position_123 v1.1` (price = $0.51) ← 1 second later
  - `position_123 v1.2` (price = $0.52) ← 2 seconds later
  - ... (1000+ versions per day!)
- **Version explosion**: 100 positions × 1000 updates/day = 100,000 rows/day!

**Solution: SCD Type 2 (Slowly Changing Dimension Type 2):**
- **All versions use same `position_id`** (no version number)
- **`row_current_ind` flag** distinguishes current vs historical:
  - `row_current_ind = TRUE` → This is the **latest** state
  - `row_current_ind = FALSE` → This is **historical** state
- **Query pattern**: Always filter `WHERE row_current_ind = TRUE`

**Example SCD Type 2 Update:**
```sql
-- Position price changed from $0.55 to $0.60

-- Step 1: Mark old row as historical
UPDATE positions
SET row_current_ind = FALSE, updated_at = NOW()
WHERE position_id = 123 AND row_current_ind = TRUE;

-- Step 2: Insert new row with updated price
INSERT INTO positions (
    position_id, market_id, side, entry_price, quantity,
    current_price, unrealized_pnl_pct,
    row_current_ind, created_at, updated_at
)
VALUES (
    123, 'KALSHI-NFL-2024', 'yes', 0.5500, 100,
    0.6000, -- NEW price
    0.0909, -- NEW P&L: (0.60-0.55)/0.55 = 9.09%
    TRUE,   -- This is now the current row
    NOW(), NOW()
);
```

**Benefits of SCD Type 2:**
- ✅ **Full history**: Every price update preserved
- ✅ **Simple queries**: `WHERE row_current_ind = TRUE` gets latest
- ✅ **No version explosion**: Reuse `position_id` for all updates
- ✅ **Audit trail**: Can reconstruct position state at any point in time

### **Why 90% Coverage? (Critical Path Tier)**

Position Manager is **NOT** business logic (85%) - it's **critical path** (90%):

**Handles Real Money:**
- Bug in P&L calculation → Wrong unrealized_pnl → Bad exit decisions → **Lose money**
- Bug in trailing stop → Exit too early → **Miss profits** OR hold too long → **Lose gains**
- Bug in exit logic → Hold losing position → **Lose real money**

**Real-Time Decisions:**
- Exit decisions happen **live** (Phase 5: checks every second)
- A rare edge case (0.1% probability) will trigger **hundreds of times per day**

**Complexity:**
- 10-condition exit priority hierarchy
- Trailing stop state machine (activate, update, trigger, reset)
- SCD Type 2 concurrent updates
- Decimal precision (sub-penny price changes)

**Blast Radius:**
- A bug affects **EVERY** open position (not just one)
- Production impact: 100 positions × bug = 100 affected trades

**Comparison to Similar Modules:**
- **Kalshi Client** (97.91% coverage): Handles money, API auth → Critical path ✅
- **Strategy Manager** (84.36% coverage): Just stores configs → Business logic
- **Position Manager**: Handles money + real-time decisions → **More like Kalshi Client**

### **Exit Priority Hierarchy** (10 Conditions)

When multiple exit conditions trigger simultaneously, **exit priority** determines which executes first:

| Priority | Exit Reason | Trigger Condition | Example |
|----------|-------------|-------------------|---------|
| 1. CRITICAL | `force_close` | Manual override (emergency) | "Close all positions NOW!" |
| 2. CRITICAL | `market_close` | Market closing in <5 minutes | NFL game ends at 4:00 PM |
| 3. HIGH | `stop_loss` | Loss exceeds threshold | -15% loss on position |
| 4. HIGH | `drawdown` | Account drawdown threshold | Account down 20% |
| 5. MEDIUM | `trailing_stop` | Price fell from peak | Price was $0.75, now $0.65 |
| 6. MEDIUM | `profit_target` | Profit target reached | +25% gain on position |
| 7. MEDIUM | `correlation_limit` | Too many correlated positions | 5 positions on same game |
| 8. LOW | `low_liquidity` | Spread too wide to exit | Bid-ask spread > 10% |
| 9. LOW | `time_limit` | Held too long | Position open >7 days |
| 10. LOW | `manual` | User-requested exit | "Close this position" |

**Example Scenario:**
```python
# Position has MULTIPLE exit conditions:
# - Trailing stop triggered (MEDIUM priority)
# - Profit target reached (MEDIUM priority)
# - Market closes in 3 minutes (CRITICAL priority)

# Exit priority determines order:
# 1. Execute market_close exit (CRITICAL) ← Executes FIRST
# 2. Ignore trailing_stop (MEDIUM) ← Never executes
# 3. Ignore profit_target (MEDIUM) ← Never executes
```

### **Core Methods** (Phase 1.5 - To Be Implemented)

```python
# Create new position (opens position)
position_id = manager.create_position(
    market_id="KALSHI-NFL-KC-2024",
    platform_id="kalshi",
    side="yes",
    entry_price=Decimal("0.5500"),
    quantity=100,
    fees=Decimal("2.50"),
)

# Update position price (SCD Type 2 - creates new row)
manager.update_position_price(
    position_id=123,
    current_price=Decimal("0.6000"),
    unrealized_pnl_pct=Decimal("0.0909"),  # 9.09% gain
)

# Activate trailing stop
manager.activate_trailing_stop(
    position_id=123,
    trailing_stop_percent=Decimal("0.10"),  # 10% trailing stop
)

# Check exit conditions (10-condition hierarchy)
exit_decision = manager.evaluate_exit_conditions(position_id=123)
if exit_decision['should_exit']:
    manager.exit_position(
        position_id=123,
        exit_reason=exit_decision['reason'],
        exit_priority=exit_decision['priority'],
    )

# Get all open positions
open_positions = manager.get_positions_by_status("open")
```

### **Reference**
- **Schema**: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md` (lines 507-545)
- **Implementation**: **NOT YET IMPLEMENTED** (Phase 1.5 pending)
- **Tests**: **NOT YET WRITTEN** (Phase 1.5 pending)
- **Requirements**: REQ-POS-001 through REQ-POS-008
- **ADRs**: ADR-020 (Position Versioning), ADR-021 (Trailing Stops), ADR-002 (Decimal Precision)
- **Guide**: `docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md`

---

## 4. Config Manager Architecture

### **Purpose**
Loads configuration from **YAML files** (version-controlled) and **environment variables** (.env for secrets). **Completely separate** from database-backed configs in strategies/models tables.

### **Implementation**
- **File**: `src/precog/config/config_loader.py` (643 lines)
- **Coverage**: 98.97% (Phase 1)
- **Target Coverage**: 80% (Infrastructure tier)
- **Storage**: 7 YAML files + .env file (no database table)

### **Two-Level Configuration System**

**Level 1: Database-Backed Configs** (Immutable Versions)
- **strategies.config** (JSONB): `{"min_edge": "0.05", "max_exposure": "1000.00"}`
- **probability_models.config** (JSONB): `{"k_factor": 20, "base_elo": 1500}`
- **Purpose**: Strategy/model parameters that NEVER change (versioning)
- **Managed by**: Strategy Manager, Model Manager
- **Example**: `elo_nfl v1.0` always uses k_factor=20, `v1.1` uses k_factor=30

**Level 2: File-Based Configs** (Mutable, Version-Controlled)
- **7 YAML files** in `config/` directory
- **Purpose**: System-wide settings, defaults, non-versioned parameters
- **Managed by**: Config Manager (config_loader.py)
- **Example**: Max total exposure, database host, API endpoints

**Why Two Systems?**

**What Changes With Each Version:**
- Model k_factor: 20 → 30 (DB config, immutable version)
- Strategy min_edge: 0.05 → 0.08 (DB config, immutable version)

**What Changes With Environment:**
- Database host: localhost → prod.precog.internal (file config, environment-specific)
- API key: demo_key → live_key (file config, secret)
- Max total exposure: $10k → $50k (file config, system-wide)

**This prevents:**
- ❌ **Config bloat**: Don't create "strategy v1.0" just to change database host
- ❌ **Version explosion**: Don't need 100 model versions for different API keys
- ✅ **Clean separation**: Versioned parameters (DB) vs environment settings (files)

### **7 YAML Configuration Files**

| File | Purpose | Example Keys |
|------|---------|--------------|
| `trading.yaml` | Core trading parameters | `max_total_exposure_dollars`, `kelly_fraction`, `daily_loss_limit_dollars` |
| `trade_strategies.yaml` | Strategy templates | Default configs for strategy creation |
| `position_management.yaml` | Position/risk management | `stop_loss_percent`, `trailing_stop_percent`, `max_position_size_dollars` |
| `probability_models.yaml` | Model templates | Default configs for model creation |
| `markets.yaml` | Market-specific settings | NFL, NBA, election market rules |
| `data_sources.yaml` | API endpoints | Kalshi URL, ESPN URL, balldontlie URL |
| `system.yaml` | System settings | Logging level, database pool size, performance tuning |

### **Configuration Hierarchy** (Priority Order)

```
1. Command-line arguments (highest priority)
   ↓ (overrides)
2. Environment variables (.env file)
   ↓ (overrides)
3. YAML files (base defaults)
```

**Example:**
```yaml
# trading.yaml (base defaults)
account:
  max_total_exposure_dollars: 10000.00

# .env file (overrides YAML)
PROD_MAX_TOTAL_EXPOSURE=50000.00

# Command-line argument (overrides both)
python main.py --max-exposure 25000.00

# Final value: $25,000 (command-line wins)
```

### **Multi-Environment Support**

**Environment Prefixes:**
- `DEV_*` - Development (local laptop)
- `STAGING_*` - Staging (pre-production)
- `PROD_*` - Production (live trading!)
- `TEST_*` - Test (pytest)

**Example:**
```bash
# .env file
ENVIRONMENT=development

DEV_DB_HOST=localhost
DEV_DB_NAME=precog_dev
DEV_KALSHI_API_KEY=demo_key_123

PROD_DB_HOST=prod.precog.internal
PROD_DB_NAME=precog_prod
PROD_KALSHI_API_KEY=live_key_456

# Code automatically uses DEV_* prefix
loader = ConfigLoader()
db_host = loader.get_env('DB_HOST')  # Returns 'localhost' (DEV_DB_HOST)

# Change to production:
ENVIRONMENT=production
db_host = loader.get_env('DB_HOST')  # Returns 'prod.precog.internal' (PROD_DB_HOST)
```

### **Security Architecture**

**❌ NEVER in YAML** (version-controlled, checked into git):
```yaml
# ❌ WRONG - This goes in git history FOREVER!
kalshi_api_key: sk_live_abc123
db_password: mysecretpassword
private_key: "-----BEGIN RSA PRIVATE KEY-----..."
```

**✅ ALWAYS in .env** (.gitignore prevents commits):
```bash
# ✅ CORRECT - .env file is NEVER committed to git
PROD_KALSHI_API_KEY=sk_live_abc123
PROD_DB_PASSWORD=mysecretpassword
PROD_KALSHI_PRIVATE_KEY_PATH=_keys/kalshi_prod_private.pem
```

**Why This Matters:**
- YAML files are **checked into git** (version control for base configs)
- Git history is **permanent** (even after deleting files, secrets remain in history)
- Anyone with repo access sees **all secrets in git history**
- Leaked API keys = **unauthorized trading with YOUR money**

**Security Checklist:**
- ✅ All secrets in `.env` file (not YAML)
- ✅ `.env` file in `.gitignore`
- ✅ Private keys in `_keys/` folder (also in `.gitignore`)
- ✅ Pre-commit hooks scan for hardcoded secrets
- ✅ Never use `git add .env` or `git add _keys/`

**Reference:** `docs/utility/SECURITY_REVIEW_CHECKLIST.md`

### **Decimal Precision Auto-Conversion**

Config Manager **automatically converts** money/price values from float → Decimal during YAML load:

**Why?** Prevent float contamination at the **boundary** (config load), not at every usage point.

```python
# trading.yaml (YAML parser uses float):
account:
  max_total_exposure_dollars: 10000.00
  kelly_fraction: 0.25

# After loading (auto-converted to Decimal):
loader = ConfigLoader()
config = loader.load('trading')

max_exposure = config['account']['max_total_exposure_dollars']
# → Decimal('10000.00'), NOT float(10000.00)!

kelly_fraction = config['account']['kelly_fraction']
# → Decimal('0.25'), NOT float(0.25)!
```

**Auto-converted keys** (65+ keys):
- `*_dollars`, `*_price`, `*_spread` → Decimal
- `probability`, `threshold`, `*_percent` → Decimal
- `kelly_fraction`, `min_edge`, `max_exposure` → Decimal

**See:** `_convert_to_decimal()` method (lines 254-327)

### **Caching Strategy**

Configurations **cached after first load** for performance:

```python
# First load: Read YAML from disk (~5-10ms)
config1 = loader.load('trading')

# Second load: Return cached dict (<0.1ms) - 50-100x faster!
config2 = loader.load('trading')

# Force re-read from disk
loader.reload('trading')
config3 = loader.load('trading')  # Fresh from disk
```

### **Core Methods**

```python
# Load specific config file
trading_config = loader.load('trading')
max_exposure = trading_config['account']['max_total_exposure_dollars']
# → Decimal('10000.00')

# Get nested value with dot notation
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
# → Decimal('10000.00')

# Load all config files
all_configs = loader.load_all()
# → {'trading': {...}, 'trade_strategies': {...}, ...}

# Get environment variable with automatic prefixing
db_host = loader.get_env('DB_HOST')  # Looks for DEV_DB_HOST, falls back to DB_HOST
db_port = loader.get_env('DB_PORT', as_type=int)  # Convert to int
enable_logging = loader.get_env('ENABLE_LOGGING', as_type=bool)  # Convert to bool

# Get database config (all environment variables)
db_config = loader.get_db_config()
# → {'host': 'localhost', 'port': 5432, 'database': 'precog_dev', ...}

# Get Kalshi API config
kalshi_config = loader.get_kalshi_config()
# → {'api_key': '...', 'private_key_path': '_keys/kalshi_demo_private.pem', ...}

# Check environment
if loader.is_production():
    # Enable live trading
    pass
elif loader.is_development():
    # Use demo mode
    pass
```

### **Reference**
- **Implementation**: `src/precog/config/config_loader.py`
- **Tests**: `tests/unit/config/test_config_loader.py` (21 tests, 100% pass rate)
- **Guide**: `docs/guides/CONFIGURATION_GUIDE_V3.1.md`
- **Requirements**: REQ-CONFIG-001 through REQ-CONFIG-005
- **ADRs**: ADR-012 (Configuration Management Strategy), ADR-002 (Decimal Precision)

---

## 5. Design Principles

### **Principle 1: Immutable Versions (Models + Strategies)**

**What:** Config field NEVER changes after creation
**Why:** A/B testing, reproducibility, attribution
**Who:** Model Manager, Strategy Manager

**Benefits:**
- ✅ **A/B Testing**: Compare elo_nfl v1.0 (k=20) vs v1.1 (k=30) side-by-side
- ✅ **Reproducibility**: Model v1.0 always behaves the same
- ✅ **Attribution**: Every trade links to exact version used
- ✅ **Audit Trail**: Know which config generated which prediction

**Example:**
```python
# Create model v1.0 with k_factor=20
model_v1 = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    config={"k_factor": 20},
)

# Want to test k_factor=30? Create NEW version v1.1
model_v2 = manager.create_model(
    model_name="elo_nfl",
    model_version="v1.1",  # NEW version
    config={"k_factor": 30},
)

# Now you can:
# - Run BOTH models in parallel (A/B test)
# - Compare predictions (which is more accurate?)
# - Link trades to exact version (which model generated this trade?)
```

---

### **Principle 2: SCD Type 2 (Positions)**

**What:** row_current_ind distinguishes current vs historical
**Why:** Positions change frequently (every second), need full history
**Who:** Position Manager

**Benefits:**
- ✅ **Full History**: Every price update preserved
- ✅ **No Version Explosion**: Reuse position_id for all updates (not 1000 versions)
- ✅ **Simple Queries**: `WHERE row_current_ind = TRUE` gets latest state
- ✅ **Audit Trail**: Reconstruct position state at any point in time

**Comparison:**

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Immutable Versions** (v1.0, v1.1, v1.2) | Clean, simple queries | Version explosion (1000+ versions/day) | Infrequent changes (models, strategies) |
| **SCD Type 2** (row_current_ind) | Full history, no explosion | Slightly more complex queries | Frequent changes (positions, prices) |

**Example:**
```sql
-- Get CURRENT position state (simple!)
SELECT * FROM positions
WHERE position_id = 123 AND row_current_ind = TRUE;

-- Get position state at specific time (audit trail)
SELECT * FROM positions
WHERE position_id = 123
  AND updated_at <= '2024-11-17 14:30:00'
ORDER BY updated_at DESC
LIMIT 1;

-- Get full price history (reconstruct timeline)
SELECT updated_at, current_price, unrealized_pnl_pct
FROM positions
WHERE position_id = 123
ORDER BY updated_at;
```

---

### **Principle 3: Two-Level Config System**

**What:** Database configs (versioned) vs file configs (system-wide)
**Why:** Separate versioned parameters from environment settings
**Who:** All managers

**Level 1: Database Configs (Immutable Versions)**
- **What Changes With Each Version**: Model k_factor, strategy min_edge
- **Example**: elo_nfl v1.0 (k=20) vs v1.1 (k=30)
- **Purpose**: A/B testing, reproducibility

**Level 2: File Configs (Mutable, Version-Controlled)**
- **What Changes With Environment**: Database host, API keys, max exposure
- **Example**: DEV_DB_HOST=localhost, PROD_DB_HOST=prod.precog.internal
- **Purpose**: Environment-specific settings

**Why Separate?**
- ❌ **Wrong**: Create "elo_nfl v1.1" just to change database host
- ✅ **Right**: Use environment variables for database host

**Example:**
```python
# Database config (immutable version) - strategies table
strategy_config = {
    "min_edge": "0.05",  # Strategy parameter (versioned)
    "kelly_fraction": "0.25",
}

# File config (mutable) - trading.yaml
system_config = {
    "max_total_exposure_dollars": "10000.00",  # System-wide setting
    "database_pool_size": 5,  # Infrastructure setting
}

# Environment config (secret) - .env file
env_config = {
    "DB_HOST": "localhost",  # Environment-specific
    "KALSHI_API_KEY": "demo_key_123",  # Secret
}
```

---

### **Principle 4: Pure psycopg2 (No ORM)**

**What:** 100% raw SQL with parameterized queries
**Why:** User preference for SQL, more control, better performance
**Who:** All managers (Model, Strategy, Position)

**Benefits:**
- ✅ **Control**: Full control over SQL queries
- ✅ **Performance**: No ORM overhead
- ✅ **Clarity**: See exactly what SQL is executed
- ✅ **Debugging**: Copy SQL directly to psql for testing

**Example:**
```python
# ✅ CORRECT: Raw SQL with psycopg2
with get_cursor() as cur:
    cur.execute(
        """
        SELECT model_id, model_name, model_version, status
        FROM probability_models
        WHERE status = %s AND row_current_ind = TRUE
        ORDER BY created_at DESC
        """,
        ("active",),  # Parameterized query (safe!)
    )
    models = cur.fetchall()

# ❌ WRONG: SQLAlchemy ORM (we don't use this!)
# models = session.query(ProbabilityModel).filter_by(status='active').all()
```

**Security:**
- ✅ **Always use parameterized queries**: `%s` placeholders
- ❌ **NEVER use string formatting**: `f"SELECT * FROM models WHERE id={model_id}"` (SQL injection!)

---

### **Principle 5: Decimal Precision**

**What:** DECIMAL(10,4) for all prices/probabilities
**Why:** Kalshi uses sub-penny pricing ($0.4975), float is imprecise
**Who:** All managers + Config Manager (auto-conversion)

**Benefits:**
- ✅ **Exact Precision**: 0.1 + 0.2 = 0.3 (not 0.30000000000000004!)
- ✅ **Sub-Penny Prices**: $0.4975 exactly (not $0.497500000000001)
- ✅ **Financial Calculations**: Profit/loss calculations exact to the penny

**Example:**
```python
# ✅ CORRECT: Use Decimal for prices
from decimal import Decimal

entry_price = Decimal("0.5500")
current_price = Decimal("0.6000")
pnl_pct = (current_price - entry_price) / entry_price
# → Decimal('0.09090909090909090909090909091')

# ❌ WRONG: Use float for prices
entry_price = 0.5500
current_price = 0.6000
pnl_pct = (current_price - entry_price) / entry_price
# → 0.09090909090909094 (imprecise!)
```

**Auto-Conversion:**
Config Manager automatically converts float → Decimal during YAML load:
```yaml
# trading.yaml (YAML uses float)
kelly_fraction: 0.25

# After loading (Decimal)
config = loader.load('trading')
kelly_fraction = config['kelly_fraction']
# → Decimal('0.25'), not float(0.25)!
```

**Reference:** ADR-002 (Decimal Precision), Pattern 1 (DEVELOPMENT_PATTERNS_V1.5.md)

---

## 6. Documentation References

### **Database Schema**
- **`docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md`** - Complete schema (25 tables)
  - Lines 277-374: `probability_models` table
  - Lines 376-476: `strategies` table
  - Lines 507-545: `positions` table

### **Implementation Code**
- **`src/precog/analytics/model_manager.py`** - Model Manager (212 lines, 84.86% coverage)
- **`src/precog/trading/strategy_manager.py`** - Strategy Manager (274 lines, 84.36% coverage)
- **`src/precog/config/config_loader.py`** - Config Manager (643 lines, 98.97% coverage)
- **Position Manager**: NOT YET IMPLEMENTED (Phase 1.5 pending)

### **Tests**
- **`tests/unit/analytics/test_model_manager.py`** - 36 tests (97.3% pass rate)
- **`tests/unit/trading/test_strategy_manager.py`** - 13 tests (100% pass rate)
- **`tests/unit/config/test_config_loader.py`** - 21 tests (100% pass rate)

### **Implementation Guides**
- **`docs/guides/CONFIGURATION_GUIDE_V3.1.md`** - YAML configuration reference
- **`docs/guides/VERSIONING_GUIDE_V1.0.md`** - Strategy/model versioning patterns
- **`docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md`** - Position lifecycle management
- **`docs/guides/DEVELOPMENT_PATTERNS_V1.5.md`** - Critical development patterns

### **Requirements**
- **Model Manager**: REQ-MODEL-001 through REQ-MODEL-005
- **Strategy Manager**: REQ-STRAT-001 through REQ-STRAT-005
- **Position Manager**: REQ-POS-001 through REQ-POS-008
- **Config Manager**: REQ-CONFIG-001 through REQ-CONFIG-005

### **Architecture Decisions**
- **ADR-002**: Decimal Precision for Financial Calculations
- **ADR-012**: Configuration Management Strategy
- **ADR-018**: Strategy Versioning (Immutable Versions)
- **ADR-019**: Model Versioning (Immutable Versions)
- **ADR-020**: Position Versioning (SCD Type 2)
- **ADR-021**: Trailing Stop Implementation

---

**END OF MANAGER_ARCHITECTURE_GUIDE_V1.0.md**
