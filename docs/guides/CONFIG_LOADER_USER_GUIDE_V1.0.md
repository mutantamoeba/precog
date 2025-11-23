# ConfigLoader User Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Target Audience:** Developers using Precog configuration system
**Purpose:** Comprehensive guide to loading and accessing YAML configurations programmatically
**Complement to:** CONFIGURATION_GUIDE_V3.1.md (covers YAML structure, this covers API usage)

---

## Overview

### What is ConfigLoader?

**ConfigLoader** is the Python API for loading and accessing Precog's YAML-based configuration system. While **CONFIGURATION_GUIDE** teaches you *what to configure*, this guide teaches you *how to load those configs in your code*.

**Think of it this way:**
- **CONFIGURATION_GUIDE** = "Here's how to write trading.yaml"
- **CONFIG_LOADER_USER_GUIDE** = "Here's how to read trading.yaml in your Python code"

### Why ConfigLoader?

**Problem:** Loading YAML files manually is tedious and error-prone:
```python
# ❌ DON'T DO THIS (manual YAML loading)
with open('config/trading.yaml') as f:
    trading_config = yaml.safe_load(f)
    max_exposure = float(trading_config['account']['max_total_exposure_dollars'])  # WRONG! float contamination!
```

**Solution:** ConfigLoader handles all the complexity:
```python
# ✅ DO THIS (ConfigLoader)
from precog.config import ConfigLoader

loader = ConfigLoader()
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
# Result: Decimal("10000.00") - proper Decimal precision!
```

### Key Features

1. **Automatic Decimal Conversion** - All monetary/price values converted from float to Decimal (Pattern 1)
2. **Environment Prefixing** - DEV_, STAGING_, PROD_, TEST_ automatic prefixes for environment variables
3. **Caching** - First load ~5-10ms (disk read), subsequent loads <0.1ms (cache)
4. **Dot Notation Access** - `loader.get('trading', 'account.max_exposure')` instead of nested dict access
5. **Database Integration** - Retrieve active strategy/model versions from database (not YAML)
6. **Security** - All secrets from .env file, never from YAML files
7. **Validation** - Verify all required configs exist and are valid YAML

---

## Core Concepts

### 1. The Seven Configuration Files

ConfigLoader manages 7 YAML files in `src/precog/config/`:

| File | Purpose | Example Parameters |
|------|---------|-------------------|
| **trading.yaml** | Trading account settings | max_total_exposure_dollars, daily_loss_limit_dollars |
| **trade_strategies.yaml** | Strategy templates | halftime_entry.min_edge, closing_line_value.kelly_fraction |
| **position_management.yaml** | Position lifecycle rules | trailing_stops.activation_threshold, max_position_hold_hours |
| **probability_models.yaml** | Model templates | elo_nfl.k_factor, elo_ncaaf.mean_reversion |
| **markets.yaml** | Market-specific settings | nfl.commission_rate, nba.min_liquidity_contracts |
| **data_sources.yaml** | API endpoints | kalshi.rate_limit_per_minute, espn.timeout_seconds |
| **system.yaml** | System-wide settings | logging.level, database.connection_pool_size |

**Educational Note:**
YAML files are **templates** for creating versioned configs in the database. For strategies and models, the database is the source of truth (immutable versions), not YAML.

### 2. Environment Prefixing (Automatic)

ConfigLoader automatically prefixes environment variables based on `ENVIRONMENT` setting:

```python
# .env file
ENVIRONMENT=development
DEV_DB_HOST=localhost
DEV_DB_NAME=precog_dev
STAGING_DB_HOST=staging.example.com
STAGING_DB_NAME=precog_staging
PROD_DB_HOST=prod.example.com
PROD_DB_NAME=precog_prod

# Python code
loader = ConfigLoader()
db_config = loader.get_db_config()

# If ENVIRONMENT=development → uses DEV_DB_HOST, DEV_DB_NAME
# If ENVIRONMENT=staging → uses STAGING_DB_HOST, STAGING_DB_NAME
# If ENVIRONMENT=production → uses PROD_DB_HOST, PROD_DB_NAME
```

**Fallback Behavior:**
If prefixed variable not found, falls back to unprefixed variable:
```bash
# .env
DB_HOST=localhost  # Fallback
DEV_DB_HOST=localhost
# STAGING_DB_HOST not defined → falls back to DB_HOST
```

### 3. Decimal Conversion (Automatic Pattern 1 Enforcement)

ConfigLoader automatically converts **60+ keys** from float to Decimal:

**Categories:**
- **Money/Dollar Amounts:** `max_total_exposure_dollars`, `daily_loss_limit_dollars`, `balance_dollars`
- **Prices:** `entry_price`, `exit_price`, `yes_price`, `no_price`, `spread`
- **Probabilities:** `probability`, `min_probability`, `confidence`, `threshold`
- **Percentages:** `trailing_stop_percent`, `max_drawdown_percent`, `commission_rate`
- **Kelly/Edge:** `kelly_fraction`, `min_edge`, `max_kelly_fraction`

**Example:**
```yaml
# trading.yaml (YAML stores as float)
account:
  max_total_exposure_dollars: 10000.00  # YAML float
```

```python
# Python code (ConfigLoader converts to Decimal automatically)
loader = ConfigLoader()
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
print(type(max_exposure))  # <class 'decimal.Decimal'>
print(max_exposure)        # Decimal('10000.00')
```

**Why This Matters:**
Prevents float precision errors in financial calculations (0.1 + 0.2 ≠ 0.3 with floats!)

**Reference:** CLAUDE.md Pattern 1 (Decimal Precision)

### 4. Configuration Caching

ConfigLoader caches loaded configs for performance:

```python
loader = ConfigLoader()

# First load: reads from disk (~5-10ms)
trading_config = loader.load('trading')

# Second load: returns cached version (<0.1ms)
trading_config_again = loader.load('trading')  # Same object from cache

# Force reload from disk (e.g., after editing YAML file)
loader.reload('trading')
trading_config_fresh = loader.load('trading')  # Re-reads from disk
```

**When to reload:**
- After manually editing YAML files
- After deploying new config version
- When debugging config issues

**Performance tip:** Don't reload unnecessarily - caching is a feature!

### 5. Database vs YAML Hierarchy

**CRITICAL CONCEPT:** For strategies and models, **database is source of truth**, not YAML.

**YAML files = Templates:**
```yaml
# trade_strategies.yaml
strategies:
  halftime_entry:
    min_edge: "0.06"  # Template default
```

**Database = Runtime Config (Immutable Versions):**
```python
# Create v1.0 from template
strategy_manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="1.0",
    config={"min_edge": Decimal("0.06")}  # Frozen in database
)

# Create v1.1 with different config (A/B testing)
strategy_manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="1.1",
    config={"min_edge": Decimal("0.08")}  # Different frozen config
)

# Set v1.1 to active
strategy_manager.update_strategy_status(strategy_id=42, status="active")
```

**Get active version from database (NOT YAML):**
```python
# ✅ CORRECT: Get from database
loader = ConfigLoader()
active_config = loader.get_active_strategy_version('halftime_entry')
print(active_config['config']['min_edge'])  # Decimal("0.08") - from v1.1

# ❌ WRONG: Get from YAML template
strategy_config = loader.get('trade_strategies', 'strategies.halftime_entry')
print(strategy_config['min_edge'])  # Decimal("0.06") - outdated template!
```

**Why?**
- **Immutability:** Each version has frozen config for audit trail
- **A/B Testing:** Multiple versions active simultaneously
- **Attribution:** Every trade records which strategy_id/model_id was used

**References:**
- REQ-VER-001: Immutable Version Configs
- ADR-018: Immutable Strategy Versions
- ADR-019: Semantic Versioning for Models
- CLAUDE.md Pattern 2 (Dual Versioning System)

---

## Quick Start

### Installation

ConfigLoader is part of Precog, no separate installation needed:

```python
from precog.config import ConfigLoader
```

### Basic Usage (5 Common Patterns)

**1. Load entire config file:**
```python
from precog.config import ConfigLoader

loader = ConfigLoader()
trading_config = loader.load('trading')
print(trading_config.keys())
# dict_keys(['account', 'risk_limits', 'execution', 'environment'])
```

**2. Get nested value with dot notation:**
```python
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
print(max_exposure)  # Decimal("10000.00")
```

**3. Get environment variable with auto-prefixing:**
```python
# Automatically tries DEV_DB_HOST, then DB_HOST
db_host = loader.get_env('DB_HOST', 'localhost')
print(db_host)  # 'localhost' (from DEV_DB_HOST or DB_HOST)
```

**4. Get database connection config:**
```python
db_config = loader.get_db_config()
# {'host': 'localhost', 'port': 5432, 'database': 'precog_dev', 'user': 'postgres', 'password': '...'}

import psycopg2
conn = psycopg2.connect(**db_config)
```

**5. Get active strategy version from database:**
```python
active_halftime = loader.get_active_strategy_version('halftime_entry')
if active_halftime:
    print(f"Active version: {active_halftime['strategy_version']}")
    print(f"Min edge: {active_halftime['config']['min_edge']}")
else:
    print("No active version in database")
```

---

## Complete API Reference

### ConfigLoader Class

#### `__init__(config_dir: str | Path | None = None)`

Initialize configuration loader.

**Args:**
- `config_dir`: Path to config directory (default: `src/precog/config/`)

**Example:**
```python
# Use default config directory
loader = ConfigLoader()

# Use custom config directory (e.g., for testing)
loader = ConfigLoader(config_dir='tests/fixtures/configs')
```

---

#### `get_env(key: str, default: Any = None, as_type: type = str) -> Any`

Get environment variable with automatic environment prefix handling.

**Prefix Logic:**
1. Try `{ENVIRONMENT}_{key}` (e.g., `DEV_DB_HOST`)
2. Fall back to `{key}` (e.g., `DB_HOST`)
3. Return `default` if not found

**Args:**
- `key`: Variable name (without environment prefix)
- `default`: Default value if not found
- `as_type`: Type to convert to (`str`, `int`, `bool`, `Decimal`)

**Returns:**
- Environment variable value converted to requested type

**Type Conversion:**
- `str`: No conversion (default)
- `int`: Converts to integer (returns `default` if invalid)
- `bool`: True if value in ("true", "1", "yes", "on"), case-insensitive
- `Decimal`: Converts to Decimal (returns `default` if invalid)

**Example:**
```python
# String (default)
log_level = loader.get_env('LOG_LEVEL', 'INFO')
# Tries: DEV_LOG_LEVEL → LOG_LEVEL → 'INFO'

# Integer
max_retries = loader.get_env('MAX_RETRIES', 3, as_type=int)
# Tries: DEV_MAX_RETRIES → MAX_RETRIES → 3

# Boolean
enable_trading = loader.get_env('ENABLE_TRADING', False, as_type=bool)
# "true", "1", "yes", "on" → True, everything else → False

# Decimal
max_exposure = loader.get_env('MAX_EXPOSURE', as_type=Decimal)
# Tries: DEV_MAX_EXPOSURE → MAX_EXPOSURE → None
```

---

#### `get_db_config() -> dict[str, Any]`

Get database configuration from environment variables.

**Returns:**
```python
{
    "host": str,      # DB_HOST or DEV_DB_HOST
    "port": int,      # DB_PORT or DEV_DB_PORT (default 5432)
    "database": str,  # DB_NAME or DEV_DB_NAME
    "user": str,      # DB_USER or DEV_DB_USER (default "postgres")
    "password": str   # DB_PASSWORD or DEV_DB_PASSWORD
}
```

**Example:**
```python
# .env file
DEV_DB_HOST=localhost
DEV_DB_PORT=5432
DEV_DB_NAME=precog_dev
DEV_DB_USER=postgres
DEV_DB_PASSWORD=secretpassword

# Python code
loader = ConfigLoader()
db_config = loader.get_db_config()

# Use with psycopg2
import psycopg2
conn = psycopg2.connect(**db_config)

# Use with psycopg2.pool
from psycopg2.pool import SimpleConnectionPool
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    **db_config
)
```

---

#### `get_kalshi_config() -> dict[str, Any]`

Get Kalshi API configuration from environment variables.

**Returns:**
```python
{
    "api_key": str,               # KALSHI_API_KEY or DEV_KALSHI_API_KEY
    "private_key_path": str,      # KALSHI_PRIVATE_KEY_PATH (default "_keys/kalshi_demo_private.pem")
    "base_url": str               # KALSHI_BASE_URL (default "https://demo-api.kalshi.co")
}
```

**Example:**
```python
# .env file
DEV_KALSHI_API_KEY=your-demo-api-key-id
DEV_KALSHI_PRIVATE_KEY_PATH=_keys/kalshi_demo_private.pem
DEV_KALSHI_BASE_URL=https://demo-api.kalshi.co

PROD_KALSHI_API_KEY=your-prod-api-key-id
PROD_KALSHI_PRIVATE_KEY_PATH=_keys/kalshi_prod_private.pem
PROD_KALSHI_BASE_URL=https://api.kalshi.com

# Python code
loader = ConfigLoader()
kalshi_config = loader.get_kalshi_config()

from precog.api_connectors import KalshiClient
client = KalshiClient(
    api_key=kalshi_config['api_key'],
    private_key_path=kalshi_config['private_key_path'],
    base_url=kalshi_config['base_url']
)
```

---

#### `is_production() -> bool`
#### `is_development() -> bool`
#### `is_staging() -> bool`
#### `is_test() -> bool`

Check if running in specific environment.

**Example:**
```python
loader = ConfigLoader()

if loader.is_production():
    # Enable live trading
    print("PRODUCTION MODE - Live trading enabled")
elif loader.is_staging():
    # Use staging API
    print("STAGING MODE - Using staging API")
elif loader.is_test():
    # Use mocks
    print("TEST MODE - Using mocks")
else:  # development
    # Use demo API
    print("DEVELOPMENT MODE - Using demo API")
```

**Environment Detection:**
```bash
# .env file
ENVIRONMENT=development  # development, staging, production, or test
```

---

#### `load(config_name: str, convert_decimals: bool = True) -> dict[str, Any]`

Load a specific configuration file.

**Args:**
- `config_name`: Name of config file (with or without .yaml extension)
- `convert_decimals`: Whether to convert money/price values to Decimal (default True)

**Returns:**
- Dictionary with configuration data (cached after first load)

**Raises:**
- `FileNotFoundError`: If config file doesn't exist
- `yaml.YAMLError`: If YAML parsing fails

**Example:**
```python
loader = ConfigLoader()

# Load trading config (both forms work)
trading1 = loader.load('trading')
trading2 = loader.load('trading.yaml')
assert trading1 is trading2  # Same cached object

# Disable Decimal conversion (NOT RECOMMENDED)
trading_raw = loader.load('trading', convert_decimals=False)
print(type(trading_raw['account']['max_total_exposure_dollars']))  # <class 'float'> - WRONG!

# Normal usage (Decimal conversion enabled)
trading = loader.load('trading')
print(type(trading['account']['max_total_exposure_dollars']))  # <class 'decimal.Decimal'> - CORRECT!
```

**Performance:**
- First load: ~5-10ms (disk read + YAML parse + Decimal conversion)
- Subsequent loads: <0.1ms (cached)

---

#### `load_all(convert_decimals: bool = True) -> dict[str, dict[str, Any]]`

Load all configuration files.

**Args:**
- `convert_decimals`: Whether to convert money/price values to Decimal (default True)

**Returns:**
- Dictionary mapping config names to their data

**Example:**
```python
loader = ConfigLoader()
all_configs = loader.load_all()

print(all_configs.keys())
# dict_keys(['trading', 'trade_strategies', 'position_management',
#            'probability_models', 'markets', 'data_sources', 'system'])

# Access individual configs
trading = all_configs['trading']
strategies = all_configs['trade_strategies']
models = all_configs['probability_models']
```

**Error Handling:**
- Missing files: Logs warning and skips (doesn't raise exception)
- YAML parse errors: Logs error and raises `yaml.YAMLError`

---

#### `get(config_name: str, key_path: str | None = None, default: Any = None) -> Any`

Get configuration value with optional nested key access.

**Args:**
- `config_name`: Name of config file (without .yaml)
- `key_path`: Dot-separated path to nested key (e.g., `'account.max_total_exposure_dollars'`)
- `default`: Default value if key not found

**Returns:**
- Configuration value or default

**Example:**
```python
loader = ConfigLoader()

# Get entire config
trading = loader.get('trading')
print(trading.keys())  # dict_keys(['account', 'risk_limits', ...])

# Get nested value with dot notation
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
print(max_exposure)  # Decimal("10000.00")

# Multiple nesting levels
halftime_min_edge = loader.get('trade_strategies', 'strategies.halftime_entry.min_edge')
print(halftime_min_edge)  # Decimal("0.06")

# With default value
environment = loader.get('trading', 'environment', default='demo')
print(environment)  # 'demo' (if key doesn't exist)

# File doesn't exist → returns default
missing = loader.get('nonexistent_config', 'some.key', default='fallback')
print(missing)  # 'fallback'
```

**Dot Notation Examples:**
```python
# Instead of this (nested dict access):
max_exposure = loader.load('trading')['account']['max_total_exposure_dollars']

# Use this (dot notation):
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
```

---

#### `reload(config_name: str | None = None) -> None`

Reload configuration from disk (clears cache).

**Args:**
- `config_name`: Specific config to reload, or None to reload all

**Example:**
```python
loader = ConfigLoader()

# Load config (gets cached)
trading = loader.load('trading')
print(trading['account']['max_total_exposure_dollars'])  # Decimal("10000.00")

# Edit trading.yaml manually (change max_total_exposure_dollars to 20000.00)
# ...

# Reload just trading.yaml
loader.reload('trading')
trading_fresh = loader.load('trading')
print(trading_fresh['account']['max_total_exposure_dollars'])  # Decimal("20000.00")

# Reload all configs
loader.reload()
```

**When to use:**
- After manually editing YAML files during development
- After deploying new config versions
- When debugging config issues

**Performance impact:** Minimal - only affects next `load()` call (re-reads from disk)

---

#### `validate_required_configs() -> bool`

Verify all required config files exist and are loadable.

**Returns:**
- `True` if all configs valid, `False` otherwise

**Example:**
```python
loader = ConfigLoader()

if loader.validate_required_configs():
    print("All configs valid - safe to start application!")
else:
    print("Config validation failed - check logs for errors")
    sys.exit(1)
```

**Use Cases:**
- Application startup validation
- Pre-deployment checks
- CI/CD pipeline validation

**Logs Output:**
```
INFO: trading.yaml loaded successfully
INFO: trade_strategies.yaml loaded successfully
INFO: position_management.yaml loaded successfully
INFO: probability_models.yaml loaded successfully
INFO: markets.yaml loaded successfully
INFO: data_sources.yaml loaded successfully
INFO: system.yaml loaded successfully
```

**If errors:**
```
ERROR: trade_strategies.yaml not found
ERROR: markets.yaml has YAML errors: mapping values are not allowed here
```

---

#### `get_active_strategy_version(strategy_name: str) -> dict[str, Any] | None`

Get active version configuration for a strategy from **database** (not YAML).

**Args:**
- `strategy_name`: Strategy identifier (e.g., `'halftime_entry'`)

**Returns:**
- Strategy configuration dict from database, or `None` if no active version

**Return Structure:**
```python
{
    "strategy_id": int,           # Surrogate key (primary key)
    "strategy_name": str,         # "halftime_entry"
    "strategy_version": str,      # "1.1"
    "config": dict,               # Frozen config: {"min_edge": Decimal("0.08"), ...}
    "status": str,                # "active"
    "created_at": datetime,
    "created_by": str,
    # ... other fields
}
```

**Example:**
```python
loader = ConfigLoader()

# Get active version from database
active_halftime = loader.get_active_strategy_version('halftime_entry')

if active_halftime:
    print(f"Active version: {active_halftime['strategy_version']}")
    # Active version: 1.1

    print(f"Strategy ID: {active_halftime['strategy_id']}")
    # Strategy ID: 42

    print(f"Min edge: {active_halftime['config']['min_edge']}")
    # Min edge: Decimal("0.08")

    print(f"Status: {active_halftime['status']}")
    # Status: active
else:
    print("No active version in database - create one first!")
```

**Multiple Active Versions (A/B Testing):**
If multiple versions are active, returns **highest version number** (most recent):
```python
# Database has:
# - halftime_entry v1.0 (active)
# - halftime_entry v1.1 (active)
# - halftime_entry v1.2 (active)

active = loader.get_active_strategy_version('halftime_entry')
print(active['strategy_version'])  # "1.2" (highest version)
```

**Educational Note:**
This method queries the **database**, not YAML files. YAML files are templates for creating new versions, but the database is the source of truth for runtime configs.

**References:**
- REQ-VER-001: Immutable Version Configs
- REQ-VER-004: Version Lifecycle Management
- ADR-018: Immutable Strategy Versions
- STRATEGY_MANAGER_USER_GUIDE_V1.0.md

---

#### `get_active_model_version(model_name: str) -> dict[str, Any] | None`

Get active version configuration for a probability model from **database** (not YAML).

**Args:**
- `model_name`: Model identifier (e.g., `'elo_nfl'`)

**Returns:**
- Model configuration dict from database, or `None` if no active version

**Return Structure:**
```python
{
    "model_id": int,              # Surrogate key (primary key)
    "model_name": str,            # "elo_nfl"
    "model_version": str,         # "1.1"
    "config": dict,               # Frozen config: {"k_factor": Decimal("35"), ...}
    "status": str,                # "active"
    "created_at": datetime,
    "created_by": str,
    # ... other fields
}
```

**Example:**
```python
loader = ConfigLoader()

# Get active version from database
active_elo = loader.get_active_model_version('elo_nfl')

if active_elo:
    print(f"Active version: {active_elo['model_version']}")
    # Active version: 1.1

    print(f"Model ID: {active_elo['model_id']}")
    # Model ID: 7

    print(f"K-factor: {active_elo['config']['k_factor']}")
    # K-factor: Decimal("35")

    print(f"Status: {active_elo['status']}")
    # Status: active
else:
    print("No active version in database - create one first!")
```

**Multiple Active Versions (A/B Testing):**
Same behavior as strategies - returns highest version number if multiple active.

**Educational Note:**
Models follow same immutability pattern as strategies (ADR-019). Each version has frozen config for A/B testing and attribution.

**Example A/B Testing:**
```python
# Database has both versions active:
# - elo_nfl v1.0: k_factor=32
# - elo_nfl v1.1: k_factor=35

# Method returns v1.1 (highest version)
active = loader.get_active_model_version('elo_nfl')
print(active['config']['k_factor'])  # Decimal("35")

# But both versions can be used for A/B testing
# Trade 1: uses model_id=6 (v1.0, k_factor=32)
# Trade 2: uses model_id=7 (v1.1, k_factor=35)
# Later analysis: "Did v1.1 improve accuracy?"
```

**References:**
- REQ-VER-001: Immutable Version Configs
- REQ-VER-005: A/B Testing Support
- ADR-019: Semantic Versioning for Models
- MODEL_MANAGER_USER_GUIDE_V1.0.md

---

#### `get_trailing_stop_config(strategy_name: str | None = None) -> dict[str, Any]`

Get trailing stop configuration for a strategy.

**Args:**
- `strategy_name`: Optional strategy identifier for strategy-specific overrides

**Returns:**
- Trailing stop configuration dict

**Return Structure:**
```python
{
    "activation_threshold": Decimal,  # Profit required to activate (e.g., "0.15")
    "distance": Decimal,              # Distance to trail below highest (e.g., "0.05")
    "enabled": bool                   # Whether trailing stops enabled
}
```

**Configuration Layers:**
1. **Default:** `position_management.yaml` → `trailing_stops` → `default`
2. **Strategy-specific:** `position_management.yaml` → `trailing_stops` → `strategies` → `{strategy_name}`

Strategy overrides **merge** with defaults (strategy values take precedence).

**Example:**
```python
loader = ConfigLoader()

# Get default trailing stop config
default_config = loader.get_trailing_stop_config()
print(default_config['activation_threshold'])  # Decimal("0.15")
print(default_config['distance'])              # Decimal("0.05")

# Get strategy-specific config (with overrides)
halftime_config = loader.get_trailing_stop_config('halftime_entry')
print(halftime_config['activation_threshold'])  # Decimal("0.10") (override)
print(halftime_config['distance'])              # Decimal("0.05") (default)
```

**YAML Configuration Example:**
```yaml
# position_management.yaml
trailing_stops:
  default:
    enabled: true
    activation_threshold: "0.15"  # 15¢ profit required
    distance: "0.05"              # Trail 5¢ below highest price

  strategies:
    halftime_entry:
      activation_threshold: "0.10"  # Override: activate sooner (10¢)
      # distance inherited from default (5¢)
```

**Trailing Stop Example:**
```
Buy YES at $0.52, trailing stop config:
- activation_threshold: Decimal("0.15") → activate when $0.67 ($0.52 + $0.15)
- distance: Decimal("0.05") → trail $0.05 below highest price

Price movement:
1. $0.52 → $0.67 (+15¢ profit) → Trailing stop ACTIVATES at $0.62
2. $0.67 → $0.75 (+23¢ profit) → Trailing stop moves to $0.70 ($0.75 - $0.05)
3. $0.75 → $0.72 (-3¢ from peak) → TRIGGERED! Sell at $0.72
   Result: Locked in $0.20 profit ($0.72 - $0.52)
```

**References:**
- REQ-RISK-003: Trailing Stop Loss
- ADR-025: Trailing Stop Implementation
- TRAILING_STOP_GUIDE_V1.0.md
- POSITION_MANAGER_USER_GUIDE_V1.0.md

---

### Module-Level Convenience Functions

These functions use the global `config` instance for simpler imports:

#### `get_trading_config() -> dict[str, Any]`

Get trading configuration.

**Example:**
```python
from precog.config.config_loader import get_trading_config

trading = get_trading_config()
max_exposure = trading['account']['max_total_exposure_dollars']
```

---

#### `get_strategy_config(strategy_name: str) -> dict[str, Any] | None`

Get configuration for a specific strategy from YAML template.

**Args:**
- `strategy_name`: Name of the strategy (e.g., `'halftime_entry'`)

**Returns:**
- Strategy configuration dict from YAML, or `None` if not found

**Example:**
```python
from precog.config.config_loader import get_strategy_config

halftime = get_strategy_config('halftime_entry')
if halftime:
    print(halftime['min_edge'])  # Decimal("0.06") - YAML template value
else:
    print("Strategy not found in YAML")
```

**⚠️ WARNING:** This returns YAML template, NOT active version from database!

For runtime configs, use `loader.get_active_strategy_version()` instead.

---

#### `get_model_config(model_name: str) -> dict[str, Any] | None`

Get configuration for a specific probability model from YAML template.

**Args:**
- `model_name`: Name of the model (e.g., `'elo_nfl'`)

**Returns:**
- Model configuration dict from YAML, or `None` if not found

**Example:**
```python
from precog.config.config_loader import get_model_config

elo_nfl = get_model_config('elo_nfl')
if elo_nfl:
    print(elo_nfl['k_factor'])  # Decimal("32") - YAML template value
else:
    print("Model not found in YAML")
```

**⚠️ WARNING:** This returns YAML template, NOT active version from database!

For runtime configs, use `loader.get_active_model_version()` instead.

---

#### `get_market_config(market_type: str) -> dict[str, Any] | None`

Get configuration for a specific market type.

**Args:**
- `market_type`: Market type (e.g., `'nfl'`, `'nba'`)

**Returns:**
- Market configuration dict, or `None` if not found

**Example:**
```python
from precog.config.config_loader import get_market_config

nfl_config = get_market_config('nfl')
if nfl_config:
    print(nfl_config['commission_rate'])  # Decimal("0.07") - Kalshi 7% commission
    print(nfl_config['min_liquidity_contracts'])  # 10
else:
    print("Market type not found")
```

---

#### `get_db_config() -> dict[str, Any]`

Get database configuration for current environment (module-level wrapper).

**Example:**
```python
from precog.config.config_loader import get_db_config
import psycopg2

db_config = get_db_config()
conn = psycopg2.connect(**db_config)
```

---

#### `get_kalshi_config() -> dict[str, Any]`

Get Kalshi API configuration for current environment (module-level wrapper).

**Example:**
```python
from precog.config.config_loader import get_kalshi_config
from precog.api_connectors import KalshiClient

kalshi_config = get_kalshi_config()
client = KalshiClient(**kalshi_config)
```

---

#### `get_env(key: str, default: Any = None, as_type: type = str) -> Any`

Get environment variable with automatic prefix handling (module-level wrapper).

**Example:**
```python
from precog.config.config_loader import get_env
from decimal import Decimal

log_level = get_env('LOG_LEVEL', 'INFO')
max_retries = get_env('MAX_RETRIES', 3, as_type=int)
max_exposure = get_env('MAX_EXPOSURE', as_type=Decimal)
```

---

#### `get_environment() -> str`

Get current environment name.

**Returns:**
- `'development'`, `'staging'`, `'production'`, or `'test'`

**Example:**
```python
from precog.config.config_loader import get_environment

env = get_environment()
if env == 'production':
    print("PRODUCTION MODE - Live trading enabled")
```

---

#### `is_production() -> bool`
#### `is_development() -> bool`
#### `is_staging() -> bool`
#### `is_test() -> bool`

Check if running in specific environment (module-level wrappers).

**Example:**
```python
from precog.config.config_loader import is_production, is_development

if is_production():
    enable_live_trading()
elif is_development():
    use_demo_api()
```

---

## Common Patterns

### Pattern 1: Application Startup Validation

**Problem:** Ensure all configs valid before starting application.

**Solution:**
```python
from precog.config import ConfigLoader
import sys

def main():
    """Application entry point with config validation."""
    loader = ConfigLoader()

    # Validate all required configs exist
    if not loader.validate_required_configs():
        print("ERROR: Config validation failed - check logs")
        sys.exit(1)

    # Validate database connectivity
    try:
        db_config = loader.get_db_config()
        import psycopg2
        conn = psycopg2.connect(**db_config)
        conn.close()
        print("✓ Database connection successful")
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
        sys.exit(1)

    # Validate environment is set correctly
    env = loader.environment
    if env not in ['development', 'staging', 'production', 'test']:
        print(f"ERROR: Invalid ENVIRONMENT='{env}'")
        sys.exit(1)

    print(f"✓ Running in {env} environment")
    print("✓ All validations passed - starting application")

    # Continue with application logic...
```

---

### Pattern 2: Environment-Specific Configuration

**Problem:** Different settings for development vs staging vs production.

**Solution:**
```python
from precog.config import ConfigLoader

loader = ConfigLoader()

if loader.is_production():
    # Production: strict limits
    max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
    # Decimal("50000.00")

    # Enable live trading
    enable_live_trading = True

    # Use production API
    kalshi_config = loader.get_kalshi_config()
    # base_url: "https://api.kalshi.com"

elif loader.is_staging():
    # Staging: medium limits
    max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
    # Decimal("10000.00")

    # Paper trading only
    enable_live_trading = False

    # Use staging API
    kalshi_config = loader.get_kalshi_config()
    # base_url: "https://staging-api.kalshi.co"

else:  # development
    # Development: low limits
    max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
    # Decimal("1000.00")

    # Demo mode only
    enable_live_trading = False

    # Use demo API
    kalshi_config = loader.get_kalshi_config()
    # base_url: "https://demo-api.kalshi.co"
```

**.env files for each environment:**
```bash
# .env.development
ENVIRONMENT=development
DEV_DB_NAME=precog_dev
DEV_KALSHI_BASE_URL=https://demo-api.kalshi.co
DEV_MAX_TOTAL_EXPOSURE=1000.00

# .env.staging
ENVIRONMENT=staging
STAGING_DB_NAME=precog_staging
STAGING_KALSHI_BASE_URL=https://staging-api.kalshi.co
STAGING_MAX_TOTAL_EXPOSURE=10000.00

# .env.production
ENVIRONMENT=production
PROD_DB_NAME=precog_prod
PROD_KALSHI_BASE_URL=https://api.kalshi.com
PROD_MAX_TOTAL_EXPOSURE=50000.00
```

---

### Pattern 3: Loading Active Strategy/Model Versions

**Problem:** Need to get runtime config from database, not YAML templates.

**Solution:**
```python
from precog.config import ConfigLoader

loader = ConfigLoader()

# Get active strategy version from database
active_halftime = loader.get_active_strategy_version('halftime_entry')

if active_halftime is None:
    # No active version in database - create one from YAML template
    from precog.trading.strategy_manager import StrategyManager

    # Load template from YAML
    template = loader.get('trade_strategies', 'strategies.halftime_entry')

    # Create v1.0 in database
    manager = StrategyManager()
    strategy_id = manager.create_strategy(
        strategy_name='halftime_entry',
        strategy_version='1.0',
        config=template,  # Use YAML template as initial config
        status='active'
    )

    # Now get active version
    active_halftime = loader.get_active_strategy_version('halftime_entry')

# Use active version config
min_edge = active_halftime['config']['min_edge']
kelly_fraction = active_halftime['config']['kelly_fraction']

print(f"Using strategy v{active_halftime['strategy_version']}")
print(f"Min edge: {min_edge}, Kelly fraction: {kelly_fraction}")
```

**Same pattern for models:**
```python
# Get active model version
active_elo = loader.get_active_model_version('elo_nfl')

if active_elo is None:
    # Create from YAML template
    from precog.analytics.model_manager import ModelManager

    template = loader.get('probability_models', 'models.elo_nfl')

    manager = ModelManager()
    model_id = manager.create_model(
        model_name='elo_nfl',
        model_version='1.0',
        config=template,
        status='active'
    )

    active_elo = loader.get_active_model_version('elo_nfl')

# Use active version config
k_factor = active_elo['config']['k_factor']
```

---

### Pattern 4: Nested Config Access with Defaults

**Problem:** Need to access deeply nested config values safely.

**Solution:**
```python
from precog.config import ConfigLoader

loader = ConfigLoader()

# ✅ GOOD: Use dot notation with default
max_exposure = loader.get(
    'trading',
    'account.max_total_exposure_dollars',
    default=Decimal("10000.00")
)

# ✅ GOOD: Check if key exists
halftime_config = loader.get('trade_strategies', 'strategies.halftime_entry')
if halftime_config:
    min_edge = halftime_config.get('min_edge', Decimal("0.05"))
else:
    print("Strategy not found in config")

# ❌ BAD: Nested dict access without safety
try:
    max_exposure = loader.load('trading')['account']['max_total_exposure_dollars']
except KeyError as e:
    print(f"Config key not found: {e}")
```

---

### Pattern 5: Reloading Configs During Development

**Problem:** Edited YAML file but code still using old cached values.

**Solution:**
```python
from precog.config import ConfigLoader

loader = ConfigLoader()

# Load config (gets cached)
trading = loader.load('trading')
print(trading['account']['max_total_exposure_dollars'])  # Decimal("10000.00")

# Edit trading.yaml manually: change max_total_exposure_dollars to 20000.00
# ...

# ❌ WRONG: Still returns cached value
trading = loader.load('trading')
print(trading['account']['max_total_exposure_dollars'])  # Decimal("10000.00") - cached!

# ✅ CORRECT: Reload from disk first
loader.reload('trading')
trading = loader.load('trading')
print(trading['account']['max_total_exposure_dollars'])  # Decimal("20000.00") - fresh!
```

**Reload all configs:**
```python
# Reload all 7 config files
loader.reload()

# Or reload specific file
loader.reload('trading')
loader.reload('trade_strategies')
```

---

### Pattern 6: Overriding Configs for Testing

**Problem:** Need to use test configs instead of production configs.

**Solution 1: Use custom config directory:**
```python
from precog.config import ConfigLoader

# Use test fixtures directory
loader = ConfigLoader(config_dir='tests/fixtures/configs')

# Loads from tests/fixtures/configs/trading.yaml
trading = loader.load('trading')
```

**Solution 2: Use ENVIRONMENT=test with prefixed variables:**
```bash
# .env.test
ENVIRONMENT=test
TEST_DB_NAME=precog_test
TEST_MAX_TOTAL_EXPOSURE=100.00
TEST_KALSHI_BASE_URL=https://demo-api.kalshi.co
```

```python
# test_trading.py
import os
os.environ['ENVIRONMENT'] = 'test'

from precog.config import ConfigLoader
loader = ConfigLoader()

assert loader.is_test()
db_config = loader.get_db_config()
assert db_config['database'] == 'precog_test'
```

**Solution 3: pytest fixtures:**
```python
# conftest.py
import pytest
from precog.config import ConfigLoader

@pytest.fixture
def config_loader():
    """Config loader with test config directory."""
    return ConfigLoader(config_dir='tests/fixtures/configs')

# test_something.py
def test_trading_config(config_loader):
    trading = config_loader.load('trading')
    assert trading['account']['max_total_exposure_dollars'] == Decimal("100.00")
```

---

## Troubleshooting

### Issue 1: "Config file not found" Error

**Error:**
```
FileNotFoundError: Config file not found: /path/to/config/trading.yaml
```

**Cause:** Config file doesn't exist or wrong directory.

**Solution:**
```python
# Check config directory
loader = ConfigLoader()
print(f"Config directory: {loader.config_dir}")
# Expected: /path/to/precog-repo/src/precog/config

# List files in config directory
import os
print(os.listdir(loader.config_dir))
# Expected: ['trading.yaml', 'trade_strategies.yaml', ...]

# If missing, create from template
# Copy from docs/guides/CONFIGURATION_GUIDE_V3.1.md examples
```

---

### Issue 2: Environment Variables Not Found

**Problem:**
```python
loader = ConfigLoader()
db_config = loader.get_db_config()
print(db_config['password'])  # None - expected password!
```

**Cause:** `.env` file not loaded or wrong environment prefix.

**Solution:**
```bash
# 1. Verify .env file exists
ls .env
# If missing: cp .env.template .env

# 2. Verify .env file has correct variables
cat .env
# Should contain:
# ENVIRONMENT=development
# DEV_DB_PASSWORD=yourpassword
# (or DB_PASSWORD=yourpassword without prefix)

# 3. Verify environment variable is set
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DEV_DB_PASSWORD'))"
# Should print: yourpassword
```

**Debug environment prefixing:**
```python
loader = ConfigLoader()
print(f"Current environment: {loader.environment}")
# Expected: development

# Try both prefixed and unprefixed
import os
print(f"DEV_DB_PASSWORD: {os.getenv('DEV_DB_PASSWORD')}")
print(f"DB_PASSWORD: {os.getenv('DB_PASSWORD')}")

# ConfigLoader tries prefixed first, then falls back to unprefixed
password = loader.get_env('DB_PASSWORD')
print(f"ConfigLoader result: {password}")
```

---

### Issue 3: Float Values Instead of Decimal

**Problem:**
```python
loader = ConfigLoader()
max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
print(type(max_exposure))  # <class 'float'> - WRONG!
```

**Cause:** Decimal conversion disabled or key not in conversion list.

**Solution 1: Ensure Decimal conversion enabled (default):**
```python
# ✅ CORRECT: Decimal conversion enabled (default)
trading = loader.load('trading', convert_decimals=True)

# ❌ WRONG: Decimal conversion disabled
trading = loader.load('trading', convert_decimals=False)
```

**Solution 2: Check if key is in conversion list:**
```python
# If your custom key not converted, add to _convert_to_decimal() method
# in config_loader.py lines 254-332

# Example: adding custom_price_field
keys_to_convert = {
    # ... existing keys ...
    "custom_price_field",  # Add your custom key here
}
```

**Manual conversion:**
```python
from decimal import Decimal

# If key not auto-converted, convert manually
max_exposure_float = loader.get('trading', 'account.max_total_exposure_dollars')
max_exposure = Decimal(str(max_exposure_float))
```

---

### Issue 4: Cached Config Not Updating

**Problem:**
```python
# Edit trading.yaml: change max_exposure from 10000 to 20000
# But code still sees old value:
trading = loader.load('trading')
print(trading['account']['max_total_exposure_dollars'])  # Decimal("10000.00") - old value!
```

**Cause:** Config cached from first load.

**Solution:**
```python
# Reload from disk
loader.reload('trading')
trading = loader.load('trading')
print(trading['account']['max_total_exposure_dollars'])  # Decimal("20000.00") - fresh!
```

---

### Issue 5: "No active version in database" Warning

**Problem:**
```python
loader = ConfigLoader()
active_halftime = loader.get_active_strategy_version('halftime_entry')
# WARNING: No active version found for strategy 'halftime_entry' in database
print(active_halftime)  # None
```

**Cause:** Strategy exists in YAML template but not created in database yet.

**Solution:**
```python
from precog.trading.strategy_manager import StrategyManager

# Load template from YAML
template = loader.get('trade_strategies', 'strategies.halftime_entry')

# Create v1.0 in database
manager = StrategyManager()
strategy_id = manager.create_strategy(
    strategy_name='halftime_entry',
    strategy_version='1.0',
    config=template,
    status='active'  # ← Make sure status is 'active'
)

# Now get_active_strategy_version() will find it
active_halftime = loader.get_active_strategy_version('halftime_entry')
assert active_halftime is not None
```

**Check database:**
```sql
-- Verify strategy exists and is active
SELECT strategy_id, strategy_name, strategy_version, status
FROM strategies
WHERE strategy_name = 'halftime_entry'
  AND row_current_ind = TRUE;

-- If status is 'draft', update to 'active'
UPDATE strategies
SET status = 'active'
WHERE strategy_name = 'halftime_entry'
  AND strategy_version = '1.0'
  AND row_current_ind = TRUE;
```

---

### Issue 6: YAML Parse Errors

**Problem:**
```
yaml.scanner.ScannerError: mapping values are not allowed here
  in "trading.yaml", line 15, column 20
```

**Cause:** Invalid YAML syntax.

**Solution:**
```python
# Validate YAML syntax
loader = ConfigLoader()
if not loader.validate_required_configs():
    print("Check logs for YAML errors")
```

**Common YAML mistakes:**
```yaml
# ❌ WRONG: Missing quotes around string with special chars
api_key: my-key-with-dashes

# ✅ CORRECT:
api_key: "my-key-with-dashes"

# ❌ WRONG: Inconsistent indentation (mixing spaces and tabs)
account:
	max_exposure: "10000.00"  # Tab character

# ✅ CORRECT: Use spaces only
account:
  max_exposure: "10000.00"  # 2 spaces

# ❌ WRONG: Duplicate keys
account:
  max_exposure: "10000.00"
account:  # Duplicate key!
  daily_limit: "5000.00"

# ✅ CORRECT: Nested properly
account:
  max_exposure: "10000.00"
  daily_limit: "5000.00"
```

**Validate YAML manually:**
```bash
# Install yamllint
pip install yamllint

# Validate config file
yamllint src/precog/config/trading.yaml
```

---

## Advanced Topics

### Custom Config Directory

**Use Case:** Multiple config sets (production, staging, development), test fixtures.

**Example:**
```python
from precog.config import ConfigLoader
from pathlib import Path

# Production configs
prod_loader = ConfigLoader(config_dir='/etc/precog/config')
prod_trading = prod_loader.load('trading')

# Test configs
test_loader = ConfigLoader(config_dir='tests/fixtures/configs')
test_trading = test_loader.load('trading')

# Compare
print(f"Prod max exposure: {prod_trading['account']['max_total_exposure_dollars']}")
# Decimal("50000.00")

print(f"Test max exposure: {test_trading['account']['max_total_exposure_dollars']}")
# Decimal("100.00")
```

---

### Environment Variable Precedence

**Precedence Order (highest to lowest):**
1. Environment-prefixed variable (e.g., `DEV_DB_HOST`)
2. Unprefixed variable (e.g., `DB_HOST`)
3. Default value

**Example:**
```bash
# .env file
DB_HOST=localhost
DEV_DB_HOST=dev-server
PROD_DB_HOST=prod-server
ENVIRONMENT=development
```

```python
loader = ConfigLoader()
db_host = loader.get_env('DB_HOST', 'fallback-host')

# ENVIRONMENT=development → tries DEV_DB_HOST first
# Result: "dev-server"

# If DEV_DB_HOST not set → tries DB_HOST
# Result: "localhost"

# If DB_HOST not set → uses default
# Result: "fallback-host"
```

---

### Type Conversion with get_env()

**Supported Types:**
- `str` (default, no conversion)
- `int` (converts to integer)
- `bool` (true if value in ["true", "1", "yes", "on"])
- `Decimal` (converts to Decimal)

**Example:**
```bash
# .env
DEV_LOG_LEVEL=DEBUG
DEV_MAX_RETRIES=3
DEV_ENABLE_TRADING=true
DEV_MAX_EXPOSURE=10000.50
```

```python
loader = ConfigLoader()

# String (default)
log_level = loader.get_env('LOG_LEVEL')
print(f"{log_level} ({type(log_level).__name__})")
# DEBUG (str)

# Integer
max_retries = loader.get_env('MAX_RETRIES', as_type=int)
print(f"{max_retries} ({type(max_retries).__name__})")
# 3 (int)

# Boolean
enable_trading = loader.get_env('ENABLE_TRADING', as_type=bool)
print(f"{enable_trading} ({type(enable_trading).__name__})")
# True (bool)

# Decimal
max_exposure = loader.get_env('MAX_EXPOSURE', as_type=Decimal)
print(f"{max_exposure} ({type(max_exposure).__name__})")
# 10000.50 (Decimal)
```

**Boolean Conversion Rules:**
```python
# True values (case-insensitive)
"true"  → True
"True"  → True
"TRUE"  → True
"1"     → True
"yes"   → True
"on"    → True

# False values (everything else)
"false" → False
"0"     → False
"no"    → False
"off"   → False
""      → False
```

---

### Disabling Decimal Conversion (NOT RECOMMENDED)

**When you might need this:**
- Debugging YAML parsing issues
- Comparing raw YAML values

**Example:**
```python
loader = ConfigLoader()

# Normal load (Decimal conversion enabled)
trading = loader.load('trading', convert_decimals=True)
print(type(trading['account']['max_total_exposure_dollars']))
# <class 'decimal.Decimal'>

# Raw load (Decimal conversion disabled)
trading_raw = loader.load('trading', convert_decimals=False)
print(type(trading_raw['account']['max_total_exposure_dollars']))
# <class 'float'> - DANGER! float contamination!
```

**⚠️ WARNING:** Only disable Decimal conversion for debugging. **NEVER use in production code!**

Pattern 1 (Decimal Precision) requires ALL monetary/price values as Decimal to prevent precision errors.

---

### A/B Testing with Multiple Active Versions

**Scenario:** Test if strategy v1.1 performs better than v1.0.

**Setup:**
```python
from precog.trading.strategy_manager import StrategyManager

manager = StrategyManager()

# Create v1.0 (conservative)
v1_0 = manager.create_strategy(
    strategy_name='halftime_entry',
    strategy_version='1.0',
    config={'min_edge': Decimal("0.06"), 'kelly_fraction': Decimal("0.25")},
    status='active'  # Active
)

# Create v1.1 (aggressive)
v1_1 = manager.create_strategy(
    strategy_name='halftime_entry',
    strategy_version='1.1',
    config={'min_edge': Decimal("0.04"), 'kelly_fraction': Decimal("0.35")},
    status='active'  # Also active (A/B testing)
)
```

**Usage:**
```python
loader = ConfigLoader()

# get_active_strategy_version() returns HIGHEST version when multiple active
active = loader.get_active_strategy_version('halftime_entry')
print(active['strategy_version'])  # "1.1"

# But both versions used for A/B testing
# Trade 1: uses strategy_id=50 (v1.0)
# Trade 2: uses strategy_id=51 (v1.1)
# Trade 3: uses strategy_id=50 (v1.0)
# Trade 4: uses strategy_id=51 (v1.1)
# ...

# Later analysis:
# SELECT AVG(realized_pnl) FROM trades WHERE strategy_id = 50  -- v1.0
# SELECT AVG(realized_pnl) FROM trades WHERE strategy_id = 51  -- v1.1
# Compare: "Did v1.1 improve profitability?"
```

**Reference:** ADR-024 (A/B Testing Architecture)

---

## References

### Documentation

- **CONFIGURATION_GUIDE_V3.1.md** - What to configure (YAML structure)
- **CONFIG_LOADER_USER_GUIDE_V1.0.md** - How to load configs (this document)
- **STRATEGY_MANAGER_USER_GUIDE_V1.0.md** - Strategy version management
- **MODEL_MANAGER_USER_GUIDE_V1.0.md** - Model version management
- **POSITION_MANAGER_USER_GUIDE_V1.0.md** - Position management
- **TRAILING_STOP_GUIDE_V1.0.md** - Trailing stop configuration

### Requirements

- **REQ-VER-001:** Immutable Version Configs (strategies/models frozen in database)
- **REQ-VER-004:** Version Lifecycle Management (active/draft/deprecated/archived)
- **REQ-VER-005:** A/B Testing Support (multiple active versions)

### Architectural Decisions

- **ADR-002:** Decimal Precision for Financial Calculations
- **ADR-018:** Immutable Strategy Versions (database > YAML)
- **ADR-019:** Semantic Versioning for Probability Models
- **ADR-024:** A/B Testing Architecture (multiple active versions)
- **ADR-025:** Trailing Stop Implementation
- **ADR-089:** Dual-Key Schema Pattern (business keys + surrogate keys)

### Development Patterns

- **Pattern 1:** Decimal Precision (NEVER USE FLOAT) - CLAUDE.md
- **Pattern 2:** Dual Versioning System - CLAUDE.md
- **Pattern 4:** Security (NO CREDENTIALS IN CODE) - CLAUDE.md
- **Pattern 7:** Educational Docstrings (ALWAYS) - CLAUDE.md

### Source Code

- **src/precog/config/config_loader.py** - ConfigLoader implementation (896 lines)
- **src/precog/config/*.yaml** - 7 configuration files
- **tests/test_config_loader.py** - ConfigLoader tests (98.97% coverage)

---

## Summary

★ **Insight ─────────────────────────────────────**
**Key Takeaways:**

1. **ConfigLoader vs CONFIGURATION_GUIDE:**
   - CONFIGURATION_GUIDE = "What to configure" (YAML structure)
   - CONFIG_LOADER = "How to load configs" (Python API)

2. **Database > YAML for Versioned Configs:**
   - Strategies/models: Use `get_active_strategy_version()` / `get_active_model_version()` (database)
   - NOT `get_strategy_config()` / `get_model_config()` (YAML templates)

3. **Automatic Features:**
   - Decimal conversion (60+ keys, prevents float contamination)
   - Environment prefixing (DEV_/STAGING_/PROD_/TEST_)
   - Caching (5-10ms first load, <0.1ms cached)

4. **Security:**
   - ALL secrets in .env file (gitignored)
   - NEVER in YAML files (version controlled)

5. **Common Operations:**
   ```python
   # Load config
   trading = loader.load('trading')

   # Get nested value
   max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')

   # Get environment variable
   db_host = loader.get_env('DB_HOST', 'localhost')

   # Get database config
   db_config = loader.get_db_config()

   # Get active strategy/model version
   active_strategy = loader.get_active_strategy_version('halftime_entry')
   active_model = loader.get_active_model_version('elo_nfl')
   ```

─────────────────────────────────────────────────

**END OF CONFIG_LOADER_USER_GUIDE_V1.0.md**
