# Strategy Manager User Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Target Audience:** Developers implementing trading strategies
**Purpose:** Comprehensive guide to using Strategy Manager for versioned strategy configuration management

---

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Quick Start](#quick-start)
4. [Complete API Reference](#complete-api-reference)
5. [Configuration Structure](#configuration-structure)
6. [Lifecycle Management](#lifecycle-management)
7. [A/B Testing Workflows](#ab-testing-workflows)
8. [Common Patterns](#common-patterns)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Topics](#advanced-topics)

---

## Overview

### What is Strategy Manager?

Strategy Manager provides CRUD operations for trading strategies with **immutable versioning**. Once a strategy version is created, its configuration CANNOT be changed - only status and metrics can be updated.

### Why Immutable Versioning?

**Problem:** If strategy configs change over time, you can't accurately attribute trade performance:
- "Did strategy v1 outperform because of better config, or better market conditions?"
- "Which specific parameter values generated that 15% return?"

**Solution:** Immutable versions create a permanent record:
- Create `halftime_entry_v1.0` with min_edge=0.05
- Deploy and track performance
- Want to test min_edge=0.08? Create `halftime_entry_v1.1` (NEW version)
- Run BOTH simultaneously (A/B testing) to compare

### Key Features

✅ **Immutable Configurations** - Configs frozen after creation
✅ **Semantic Versioning** - v1.0 → v1.1 (minor) or v2.0 (major)
✅ **A/B Testing Support** - Multiple active versions simultaneously
✅ **Trade Attribution** - Every trade links to exact strategy config
✅ **Lifecycle Management** - draft → testing → active → deprecated
✅ **Metrics Tracking** - Track ROI, trade count separately from config

---

## Core Concepts

### 1. Immutable vs Mutable Fields

**IMMUTABLE (set once, never changes):**
- `config` - Strategy parameters and rules
- `strategy_name` - Strategy identifier
- `strategy_version` - Semantic version string
- `approach` - Strategy type ('value', 'arbitrage', etc.)
- `domain` - Target markets ('nfl', 'nba', etc.)

**MUTABLE (can be updated):**
- `status` - Lifecycle state (draft/testing/active/deprecated)
- `paper_trades_count` - Number of paper trades executed
- `paper_roi` - Paper trading return on investment
- `live_trades_count` - Number of live trades executed
- `live_roi` - Live trading return on investment
- `notes` - Developer notes and observations

**Why This Separation?**

Immutable config ensures trade attribution integrity. Mutable metrics track performance without changing the strategy definition.

### 2. Semantic Versioning Convention

**Format:** `v{major}.{minor}`

**Version Bump Rules:**
- **Minor version (v1.0 → v1.1):** Parameter tuning, calibration changes
  - Example: Change min_edge from 0.05 to 0.08
  - Example: Adjust Kelly multiplier from 0.50 to 0.60

- **Major version (v1.0 → v2.0):** Algorithm/logic changes
  - Example: Switch from simple edge detection to ensemble model
  - Example: Add new entry conditions (market liquidity filter)

**References:**
- REQ-VER-002: Semantic Versioning
- ADR-019: Semantic Versioning for Strategies
- docs/guides/VERSIONING_GUIDE_V1.0.md

### 3. Status Lifecycle

```
┌─────────┐      ┌──────────┐      ┌────────┐      ┌────────────┐
│  draft  │ ───> │ testing  │ ───> │ active │ ───> │ deprecated │
└─────────┘      └──────────┘      └────────┘      └────────────┘
                       │                                    ▲
                       │                                    │
                       └────────────────────────────────────┘
                              (revert to draft)
```

**State Transitions:**
- `draft → testing` - Start backtesting/paper trading
- `testing → active` - Promote to live production
- `testing → draft` - Revert to development (if issues found)
- `active → deprecated` - Retire old version
- `deprecated → [none]` - Terminal state (no way back)

**Invalid Transitions:**
- ❌ `active → testing` (can't go backwards)
- ❌ `deprecated → active` (can't resurrect)
- ❌ `draft → active` (must test first)

### 4. Strategy Types (Lookup Table)

**Available types** (from `strategy_types` table, Migration 023):
- `value` - Value-based strategies (edge detection)
- `arbitrage` - Cross-platform arbitrage
- `momentum` - Trend-following strategies
- `mean_reversion` - Contrarian strategies
- `market_making` - Liquidity provision

**Adding New Type:**
```sql
-- Migration XXX: Add new strategy type
INSERT INTO strategy_types (strategy_type_code, display_name, category, description, active)
VALUES ('ensemble', 'Ensemble Strategy', 'statistical', 'Multi-model ensemble predictions', TRUE);
```

---

## Quick Start

### Installation

```python
from precog.trading.strategy_manager import StrategyManager
from decimal import Decimal

manager = StrategyManager()
```

### Create Your First Strategy

```python
# Create new strategy version
strategy = manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0",
    strategy_type="value",
    config={
        "entry_conditions": {
            "min_edge": Decimal("0.05"),          # 5% minimum edge
            "max_kelly_fraction": Decimal("0.25"), # Max 25% of capital
            "min_liquidity": 100,                  # $100 minimum volume
            "max_spread": Decimal("0.08")          # 8% max bid-ask spread
        },
        "position_sizing": {
            "kelly_multiplier": Decimal("0.50"),   # Half Kelly sizing
            "max_position_size": Decimal("1000.00") # Max $1000 per position
        },
        "exit_conditions": {
            "profit_target": Decimal("0.15"),      # Exit at +15%
            "stop_loss": Decimal("0.30")           # Stop at -30%
        }
    },
    domain="nfl",
    description="NFL halftime entry strategy with conservative sizing",
    status="draft"
)

print(f"Created strategy ID: {strategy['strategy_id']}")
# Output: Created strategy ID: 42
```

### Promote to Testing

```python
# Update status to testing (start backtesting)
strategy = manager.update_status(strategy['strategy_id'], "testing")

print(f"Status: {strategy['status']}")
# Output: Status: testing
```

### Track Performance

```python
# Update metrics after paper trading
strategy = manager.update_metrics(
    strategy_id=42,
    paper_trades_count=100,
    paper_roi=Decimal("0.1234")  # 12.34% return
)

print(f"Paper ROI: {strategy['paper_roi']}")
# Output: Paper ROI: 0.1234
```

### Promote to Production

```python
# Activate strategy for live trading
strategy = manager.update_status(strategy['strategy_id'], "active")

print(f"Status: {strategy['status']}")
# Output: Status: active
```

---

## Complete API Reference

### create_strategy()

Create new strategy version with immutable configuration.

**Signature:**
```python
def create_strategy(
    self,
    strategy_name: str,
    strategy_version: str,
    strategy_type: str,
    config: dict[str, Any],
    domain: str | None = None,
    description: str | None = None,
    status: str = "draft",
    created_by: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strategy_name` | `str` | ✅ Yes | Strategy identifier (e.g., 'halftime_entry') |
| `strategy_version` | `str` | ✅ Yes | Semantic version (e.g., 'v1.0', 'v1.1') |
| `strategy_type` | `str` | ✅ Yes | FK to strategy_types table ('value', 'arbitrage', etc.) |
| `config` | `dict` | ✅ Yes | Strategy parameters (IMMUTABLE after creation!) |
| `domain` | `str \| None` | ❌ No | Target markets ('nfl', 'nba', etc.) or None for multi-domain |
| `description` | `str \| None` | ❌ No | Human-readable description |
| `status` | `str` | ❌ No | Initial status (default 'draft') |
| `created_by` | `str \| None` | ❌ No | Creator identifier (username, system, etc.) |
| `notes` | `str \| None` | ❌ No | Additional notes |

**Returns:** Dict with all strategy fields including generated `strategy_id`

**Raises:**
- `psycopg2.IntegrityError` - If strategy_name + strategy_version already exists
- `psycopg2.ForeignKeyViolation` - If strategy_type not in lookup table
- `ValueError` - If config is empty

**Example:**
```python
strategy = manager.create_strategy(
    strategy_name="momentum_nfl",
    strategy_version="v2.0",
    strategy_type="momentum",
    config={
        "lookback_window_days": 7,
        "momentum_threshold": Decimal("0.10"),
        "entry_conditions": {
            "min_liquidity": 500,
            "min_edge": Decimal("0.03")
        }
    },
    domain="nfl",
    description="NFL momentum strategy with 7-day lookback",
    status="draft",
    created_by="john_doe"
)

print(strategy['strategy_id'])  # 123
print(strategy['config'])       # Full config dict with Decimal values
```

---

### get_strategy()

Retrieve strategy by ID or by name+version.

**Signature:**
```python
def get_strategy(
    self,
    strategy_id: int | None = None,
    strategy_name: str | None = None,
    strategy_version: str | None = None,
) -> dict[str, Any] | None:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strategy_id` | `int \| None` | ⚠️ Either/Or | Strategy primary key (mutually exclusive with name+version) |
| `strategy_name` | `str \| None` | ⚠️ Either/Or | Strategy identifier (requires strategy_version) |
| `strategy_version` | `str \| None` | ⚠️ Either/Or | Strategy version (requires strategy_name) |

**Returns:** Strategy dict or `None` if not found

**Raises:**
- `ValueError` - If neither ID nor name+version provided, or if only one of name/version provided

**Examples:**
```python
# Query by ID
strategy = manager.get_strategy(strategy_id=42)

# Query by name+version
strategy = manager.get_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0"
)

# Error: Must provide both name AND version
strategy = manager.get_strategy(strategy_name="halftime_entry")  # ValueError!
```

---

### get_strategies_by_name()

Get all versions of a strategy by name.

**Signature:**
```python
def get_strategies_by_name(
    self,
    strategy_name: str
) -> list[dict[str, Any]]:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strategy_name` | `str` | ✅ Yes | Strategy identifier |

**Returns:** List of all versions, ordered by created_at DESC (newest first)

**Example:**
```python
strategies = manager.get_strategies_by_name("halftime_entry")

for strategy in strategies:
    print(f"{strategy['strategy_version']}: {strategy['paper_roi']}")

# Output:
# v1.2: 0.1523
# v1.1: 0.1234
# v1.0: 0.0987
```

---

### get_active_strategies()

Get all strategies with status='active'.

**Signature:**
```python
def get_active_strategies(self) -> list[dict[str, Any]]:
```

**Parameters:** None

**Returns:** List of active strategies across all names and versions

**Example:**
```python
active = manager.get_active_strategies()

print(f"Active strategies: {len(active)}")
# Output: Active strategies: 3

for strategy in active:
    print(f"{strategy['strategy_name']} {strategy['strategy_version']}")

# Output:
# halftime_entry v1.2
# momentum_nfl v2.0
# arbitrage_multi v1.0
```

---

### list_strategies()

List strategies with optional filters.

**Signature:**
```python
def list_strategies(
    self,
    status: str | None = None,
    strategy_version: str | None = None,
    strategy_type: str | None = None,
) -> list[dict[str, Any]]:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | `str \| None` | ❌ No | Filter by status ('draft', 'testing', 'active', 'inactive', 'deprecated') |
| `strategy_version` | `str \| None` | ❌ No | Filter by version ('v1.0', 'v1.1', 'v2.0', etc.) |
| `strategy_type` | `str \| None` | ❌ No | Filter by type ('value', 'arbitrage', 'momentum', 'mean_reversion') |

**Returns:** List of strategies matching ALL filters (AND logic), ordered by strategy_name, strategy_version

**Educational Note:**
This method mirrors the `list_models()` API in `model_manager.py` for API consistency.
Useful for flexible strategy queries without requiring rigid status filters.

**Examples:**
```python
# Get all active value strategies
strategies = manager.list_strategies(
    status="active",
    strategy_type="value"
)

# Get all v1.0 strategies (any status/type)
v10_strategies = manager.list_strategies(strategy_version="v1.0")

# Get all active v2.0 value strategies (multiple filters with AND logic)
filtered = manager.list_strategies(
    status="active",
    strategy_version="v2.0",
    strategy_type="value"
)

# Get all strategies (no filters)
all_strategies = manager.list_strategies()

# Get all testing strategies (any version/type)
testing = manager.list_strategies(status="testing")
```

**Related Methods:**
- `get_active_strategies()` - Convenience method for status='active' only
- `get_strategies_by_name()` - Filter by name only
- `get_strategy()` - Fetch single strategy by ID

**References:**
- GitHub Issue #132: Add list_strategies() method
- REQ-VER-004: Version Lifecycle Management
- REQ-VER-005: A/B Testing Support

---

### update_status()

Update strategy status with transition validation.

**Signature:**
```python
def update_status(
    self,
    strategy_id: int,
    new_status: str
) -> dict[str, Any]:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strategy_id` | `int` | ✅ Yes | Strategy to update |
| `new_status` | `str` | ✅ Yes | New status value |

**Returns:** Updated strategy dict

**Raises:**
- `ValueError` - If strategy not found
- `InvalidStatusTransitionError` - If transition is invalid

**Valid Transitions:**
- `draft → testing` (start backtesting)
- `testing → active` (promote to production)
- `testing → draft` (revert to development)
- `active → deprecated` (retire)
- `deprecated → [none]` (terminal state)

**Example:**
```python
# Valid transition
strategy = manager.update_status(42, "testing")  # draft → testing

# Invalid transition (raises InvalidStatusTransitionError)
try:
    manager.update_status(42, "draft")  # active → draft (INVALID!)
except InvalidStatusTransitionError as e:
    print(e)
    # Output: Invalid transition: active → draft. Valid transitions from active: ['deprecated']
```

---

### update_metrics()

Update strategy performance metrics (MUTABLE fields).

**Signature:**
```python
def update_metrics(
    self,
    strategy_id: int,
    paper_trades_count: int | None = None,
    paper_roi: Decimal | None = None,
    live_trades_count: int | None = None,
    live_roi: Decimal | None = None,
) -> dict[str, Any]:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `strategy_id` | `int` | ✅ Yes | Strategy to update |
| `paper_trades_count` | `int \| None` | ❌ No | Number of paper trades executed |
| `paper_roi` | `Decimal \| None` | ❌ No | Paper trading return on investment |
| `live_trades_count` | `int \| None` | ❌ No | Number of live trades executed |
| `live_roi` | `Decimal \| None` | ❌ No | Live trading return on investment |

**Returns:** Updated strategy dict

**Raises:**
- `ValueError` - If strategy not found or no metrics provided

**Note:** At least ONE metric must be provided.

**Example:**
```python
# Update paper trading metrics
strategy = manager.update_metrics(
    strategy_id=42,
    paper_trades_count=100,
    paper_roi=Decimal("0.1234")  # 12.34% return
)

# Update live trading metrics
strategy = manager.update_metrics(
    strategy_id=42,
    live_trades_count=50,
    live_roi=Decimal("0.0987")  # 9.87% return
)

# Update all metrics at once
strategy = manager.update_metrics(
    strategy_id=42,
    paper_trades_count=150,
    paper_roi=Decimal("0.1456"),
    live_trades_count=75,
    live_roi=Decimal("0.1123")
)
```

---

## Configuration Structure

### Recommended Config Schema

While `config` is stored as JSONB and can have any structure, we recommend this standard schema for consistency:

```yaml
config:
  # Entry conditions (when to open positions)
  entry_conditions:
    min_edge: "0.05"              # Minimum edge required (Decimal as string!)
    max_kelly_fraction: "0.25"    # Max % of capital per trade
    min_liquidity: 100            # Minimum market volume (int)
    max_spread: "0.08"            # Maximum bid-ask spread

    # Optional: Additional filters
    min_market_age_hours: 24      # Avoid brand-new markets
    max_time_to_close_hours: 72   # Avoid markets closing soon

  # Position sizing (how much to trade)
  position_sizing:
    kelly_multiplier: "0.50"      # Fraction of Kelly criterion (conservative)
    max_position_size: "1000.00"  # Absolute max per position
    max_total_exposure: "5000.00" # Max total across all positions

  # Exit conditions (when to close positions)
  exit_conditions:
    profit_target: "0.15"         # Take profit at +15%
    stop_loss: "0.30"             # Stop loss at -30%

    # Optional: Trailing stop config
    trailing_stop:
      activation_threshold: "0.10"  # Activate after +10% profit
      initial_distance: "0.05"      # Initial 5% trailing distance
      tightening_rate: "0.10"       # Tighten 10% as profit grows
      floor_distance: "0.02"        # Never tighter than 2%

  # Risk limits (prevent overexposure)
  risk_limits:
    max_positions_per_market: 1   # One position per market
    max_positions_total: 10       # Max 10 concurrent positions
    max_drawdown_pct: "0.20"      # Stop trading if down 20%
```

### Config Validation Best Practices

**1. Use Decimal for ALL prices/percentages:**
```python
# ✅ CORRECT
config = {
    "entry_conditions": {
        "min_edge": Decimal("0.05")  # Decimal from string
    }
}

# ❌ WRONG
config = {
    "entry_conditions": {
        "min_edge": 0.05  # Float - NEVER USE!
    }
}
```

**2. Store Decimals as strings in YAML:**
```yaml
# ✅ CORRECT (src/precog/config/trade_strategies.yaml)
min_edge: "0.05"

# ❌ WRONG
min_edge: 0.05  # YAML parses as float!
```

**3. Provide defaults for new parameters:**
```python
# Phase 5 execution code (backward compatibility)
entry_rules = strategy['config']['entry_conditions']

# Use .get() with default for new parameters
min_age_hours = entry_rules.get("min_market_age_hours", 0)  # Default 0 if not present
```

---

## Lifecycle Management

### Complete Lifecycle Example

```python
from precog.trading.strategy_manager import StrategyManager
from decimal import Decimal

manager = StrategyManager()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 1: DRAFT - Initial Development
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("Creating new strategy in draft mode...")
strategy = manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0",
    strategy_type="value",
    config={
        "entry_conditions": {
            "min_edge": Decimal("0.05"),
            "max_kelly_fraction": Decimal("0.25")
        }
    },
    domain="nfl",
    status="draft"  # Initial status
)

strategy_id = strategy['strategy_id']
print(f"✓ Created strategy {strategy_id} in draft mode")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 2: TESTING - Backtesting & Paper Trading
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("Promoting to testing phase...")
strategy = manager.update_status(strategy_id, "testing")
print(f"✓ Status: {strategy['status']}")

# Run backtests (external script)
print("Running backtests...")
# subprocess.run(["python", "scripts/backtest_strategy.py", f"--strategy_id={strategy_id}"])

# After 60 days of paper trading, update metrics
print("Updating paper trading metrics...")
strategy = manager.update_metrics(
    strategy_id=strategy_id,
    paper_trades_count=100,
    paper_roi=Decimal("0.1234")  # 12.34% return
)
print(f"✓ Paper ROI: {float(strategy['paper_roi']) * 100:.2f}%")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 3: ACTIVE - Live Production
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Promote to production if paper ROI > threshold
if strategy['paper_roi'] >= Decimal("0.10"):  # 10% minimum ROI
    print("Promoting to active (live production)...")
    strategy = manager.update_status(strategy_id, "active")
    print(f"✓ Status: {strategy['status']}")
else:
    print("❌ Paper ROI too low, reverting to draft...")
    strategy = manager.update_status(strategy_id, "draft")

# After live trading, update live metrics
print("Updating live trading metrics...")
strategy = manager.update_metrics(
    strategy_id=strategy_id,
    live_trades_count=50,
    live_roi=Decimal("0.0987")  # 9.87% return
)
print(f"✓ Live ROI: {float(strategy['live_roi']) * 100:.2f}%")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 4: DEPRECATED - Retirement
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# When replacing with better version (v1.1), deprecate v1.0
print("Deprecating old version...")
strategy = manager.update_status(strategy_id, "deprecated")
print(f"✓ Status: {strategy['status']}")

# v1.0 stays in database for historical analysis, but won't execute new trades
```

**Output:**
```
Creating new strategy in draft mode...
✓ Created strategy 42 in draft mode
Promoting to testing phase...
✓ Status: testing
Running backtests...
Updating paper trading metrics...
✓ Paper ROI: 12.34%
Promoting to active (live production)...
✓ Status: active
Updating live trading metrics...
✓ Live ROI: 9.87%
Deprecating old version...
✓ Status: deprecated
```

---

## A/B Testing Workflows

### Scenario: Testing min_edge Parameter

**Goal:** Determine if min_edge=0.08 performs better than min_edge=0.05

**Step 1: Create Two Versions**
```python
# Version 1.0 (baseline)
v1_0 = manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0",
    strategy_type="value",
    config={
        "entry_conditions": {
            "min_edge": Decimal("0.05"),  # Baseline value
            "max_kelly_fraction": Decimal("0.25")
        }
    },
    domain="nfl",
    status="testing"
)

# Version 1.1 (experiment)
v1_1 = manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.1",
    strategy_type="value",
    config={
        "entry_conditions": {
            "min_edge": Decimal("0.08"),  # Higher threshold
            "max_kelly_fraction": Decimal("0.25")
        }
    },
    domain="nfl",
    status="testing"
)
```

**Step 2: Run A/B Test (from trade_strategies.yaml config)**
```yaml
ab_testing:
  enabled: true
  default_traffic_split:
    existing_version: "0.70"  # v1.0 gets 70% of capital
    new_version: "0.30"       # v1.1 gets 30% of capital
  promotion_criteria:
    min_improvement_pct: "0.05"       # Must be 5% better
    min_evaluation_period_days: 60    # Minimum 60 days
    confidence_level: "0.95"          # 95% statistical confidence
    min_trade_count: 50               # At least 50 trades each
```

**Step 3: Compare Performance**
```python
import time

# Run for 60 days
time.sleep(60 * 24 * 60 * 60)  # Simulate 60 days (in reality, wait actual time)

# Fetch both versions
v1_0_updated = manager.get_strategy(strategy_id=v1_0['strategy_id'])
v1_1_updated = manager.get_strategy(strategy_id=v1_1['strategy_id'])

# Compare metrics
print("Performance Comparison:")
print(f"v1.0 (min_edge=0.05): ROI={v1_0_updated['paper_roi']}, Trades={v1_0_updated['paper_trades_count']}")
print(f"v1.1 (min_edge=0.08): ROI={v1_1_updated['paper_roi']}, Trades={v1_1_updated['paper_trades_count']}")

# Calculate improvement
improvement_pct = (v1_1_updated['paper_roi'] - v1_0_updated['paper_roi']) / v1_0_updated['paper_roi']
print(f"Improvement: {float(improvement_pct) * 100:.2f}%")
```

**Step 4: Promote Winner**
```python
# If v1.1 is better by >= 5%
if improvement_pct >= Decimal("0.05"):
    # Activate new version
    manager.update_status(v1_1['strategy_id'], "active")

    # Deprecate old version
    manager.update_status(v1_0['strategy_id'], "deprecated")

    print("✓ Promoted v1.1 to active, deprecated v1.0")
else:
    # Keep using v1.0
    manager.update_status(v1_0['strategy_id'], "active")
    manager.update_status(v1_1['strategy_id'], "deprecated")

    print("✓ v1.1 did not improve enough, keeping v1.0 active")
```

---

## Common Patterns

### Pattern 1: Create Strategy from YAML Config

```python
import yaml
from decimal import Decimal

# Load YAML config
with open("src/precog/config/trade_strategies.yaml") as f:
    yaml_config = yaml.safe_load(f)

# Extract strategy config
strategy_yaml = yaml_config['live_continuous_nfl_v1']

# Convert string decimals to Decimal objects
def convert_decimals(obj):
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        try:
            return Decimal(obj)
        except:
            return obj
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj

config = convert_decimals(strategy_yaml['config'])

# Create strategy
strategy = manager.create_strategy(
    strategy_name=strategy_yaml['name'],
    strategy_version=strategy_yaml['version'],
    strategy_type=strategy_yaml['type'],
    config=config,
    domain=strategy_yaml.get('domain'),
    description=strategy_yaml.get('description'),
    status="draft"
)
```

---

### Pattern 2: Iterate All Versions, Find Best Performer

```python
# Get all versions of a strategy
strategies = manager.get_strategies_by_name("halftime_entry")

# Filter to completed testing phases
completed = [s for s in strategies if s['status'] in ('active', 'deprecated') and s['paper_roi'] is not None]

# Sort by paper ROI (best first)
completed.sort(key=lambda s: s['paper_roi'], reverse=True)

# Print ranking
print("Strategy Performance Ranking:")
for i, strategy in enumerate(completed, 1):
    print(f"{i}. {strategy['strategy_version']}: ROI={float(strategy['paper_roi']) * 100:.2f}%, Trades={strategy['paper_trades_count']}")

# Output:
# Strategy Performance Ranking:
# 1. v1.2: ROI=15.23%, Trades=150
# 2. v1.1: ROI=12.34%, Trades=120
# 3. v1.0: ROI=9.87%, Trades=100
```

---

### Pattern 3: Bulk Status Update (Deprecate All Old Versions)

```python
# Get all active strategies for a given name
strategies = manager.get_strategies_by_name("halftime_entry")
active = [s for s in strategies if s['status'] == 'active']

# Deprecate all except newest
for strategy in active[1:]:  # Skip first (newest)
    manager.update_status(strategy['strategy_id'], "deprecated")
    print(f"Deprecated {strategy['strategy_version']}")
```

---

### Pattern 4: Clone Strategy with Modified Config

```python
# Get existing strategy
old_strategy = manager.get_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0"
)

# Clone config and modify
new_config = old_strategy['config'].copy()
new_config['entry_conditions']['min_edge'] = Decimal("0.08")  # Increase threshold

# Create new version
new_strategy = manager.create_strategy(
    strategy_name=old_strategy['strategy_name'],
    strategy_version="v1.1",  # Increment version
    strategy_type=old_strategy['approach'],
    config=new_config,
    domain=old_strategy['domain'],
    description=f"{old_strategy['description']} (increased min_edge to 0.08)",
    status="draft"
)

print(f"Cloned v1.0 → v1.1 with min_edge={new_config['entry_conditions']['min_edge']}")
```

---

## Troubleshooting

### Issue: IntegrityError - Duplicate strategy version

**Error:**
```
psycopg2.IntegrityError: duplicate key value violates unique constraint "strategies_strategy_name_strategy_version_key"
```

**Cause:** Trying to create strategy with existing (strategy_name, strategy_version) combination.

**Solution:** Increment version number:
```python
# ❌ WRONG - v1.0 already exists
manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.0",  # Duplicate!
    ...
)

# ✅ CORRECT - Use new version
manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.1",  # New version
    ...
)
```

---

### Issue: ForeignKeyViolation - Invalid strategy_type

**Error:**
```
psycopg2.errors.ForeignKeyViolation: insert or update on table "strategies" violates foreign key constraint "strategies_approach_fkey"
```

**Cause:** `strategy_type` value not in `strategy_types` lookup table.

**Solution:** Use valid strategy type or add new one:
```python
# Check available types
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT strategy_type_code FROM strategy_types WHERE active = TRUE")
valid_types = [row[0] for row in cursor.fetchall()]
print(f"Valid types: {valid_types}")
# Output: Valid types: ['value', 'arbitrage', 'momentum', 'mean_reversion', 'market_making']

# Use valid type
manager.create_strategy(
    strategy_type="value",  # ✅ Valid
    ...
)
```

---

### Issue: InvalidStatusTransitionError

**Error:**
```
InvalidStatusTransitionError: Invalid transition: active → testing. Valid transitions from active: ['deprecated']
```

**Cause:** Attempting invalid status transition.

**Solution:** Follow valid transition paths:
```python
# ❌ WRONG - Can't go backwards from active to testing
manager.update_status(42, "testing")

# ✅ CORRECT - Deprecate old version, create new version in testing
manager.update_status(42, "deprecated")  # Retire old

new_strategy = manager.create_strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.1",
    status="testing",  # New version starts in testing
    ...
)
```

---

### Issue: Config uses float instead of Decimal

**Error:**
```
# Silent bug - no error, but causes precision issues
config = {"min_edge": 0.05}  # Float!
```

**Detection:** Check log warnings or run validation:
```python
import json
from decimal import Decimal

config = {"min_edge": 0.05}

# Validate all numeric values are Decimal
def check_decimals(obj, path="config"):
    if isinstance(obj, float):
        raise ValueError(f"Float found at {path}! Use Decimal instead")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            check_decimals(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            check_decimals(item, f"{path}[{i}]")

check_decimals(config)
# ValueError: Float found at config.min_edge! Use Decimal instead
```

**Solution:** Always use Decimal:
```python
# ✅ CORRECT
config = {"min_edge": Decimal("0.05")}
```

---

## Advanced Topics

### Dynamic Config Parameters (Phase 5)

**Scenario:** Profit target should adapt to market volatility.

**YAML Config (stores formula, not value):**
```yaml
exit_conditions:
  profit_target:
    mode: "dynamic"
    base_target: "0.15"           # Base $0.15 target
    volatility_multiplier: "0.50"  # Adjust by 50% of volatility
    min_target: "0.10"
    max_target: "0.30"
```

**Phase 5 Execution Logic:**
```python
def calculate_profit_target(position, market_data, strategy_config):
    target_config = strategy_config['exit_conditions']['profit_target']

    if target_config['mode'] == 'dynamic':
        # Calculate market volatility
        volatility = calculate_market_volatility(market_data)

        # Apply formula
        base = Decimal(target_config['base_target'])
        multiplier = Decimal(target_config['volatility_multiplier'])
        computed = base + (multiplier * volatility)

        # Constrain
        min_target = Decimal(target_config['min_target'])
        max_target = Decimal(target_config['max_target'])

        return max(min_target, min(max_target, computed))

    else:  # static mode
        return Decimal(target_config['value'])
```

**Benefits:**
- ✅ Config stays IMMUTABLE (formula doesn't change)
- ✅ Target adapts to market conditions
- ✅ Testable (backtest different formulas)

---

### Trade Attribution Chain

**Every trade links back to exact strategy config:**

```python
# Query trade attribution
conn = get_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT
        t.trade_id,
        t.price,
        t.realized_pnl,
        s.strategy_name,
        s.strategy_version,
        s.config->>'entry_conditions' AS entry_config
    FROM trades t
    JOIN positions p ON t.position_id = p.position_id
    JOIN strategies s ON p.strategy_id = s.strategy_id
    WHERE t.created_at > NOW() - INTERVAL '30 days'
    ORDER BY t.realized_pnl DESC
    LIMIT 10
""")

for row in cursor.fetchall():
    print(f"Trade {row[0]}: {row[3]} {row[4]} → P&L ${row[2]}")
    print(f"  Config: {row[5]}")

# Output:
# Trade 1234: halftime_entry v1.2 → P&L $15.23
#   Config: {"min_edge": "0.08", "max_kelly_fraction": "0.25"}
# Trade 1235: halftime_entry v1.1 → P&L $12.34
#   Config: {"min_edge": "0.05", "max_kelly_fraction": "0.25"}
```

---

## References

### Related Documentation

- **Versioning Guide:** `docs/guides/VERSIONING_GUIDE_V1.0.md`
- **Configuration Guide:** `docs/guides/CONFIGURATION_GUIDE_V3.1.md`
- **Database Schema:** `docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md`
- **Position Manager Guide:** `docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md` (coming soon)
- **Model Manager Guide:** `docs/guides/MODEL_MANAGER_USER_GUIDE_V1.0.md` (coming soon)

### Requirements & ADRs

- **REQ-VER-001:** Immutable Version Configs
- **REQ-VER-002:** Semantic Versioning
- **REQ-VER-003:** Trade Attribution
- **REQ-VER-004:** Version Lifecycle Management
- **REQ-VER-005:** A/B Testing Support
- **ADR-018:** Immutable Strategy Versions
- **ADR-019:** Semantic Versioning for Strategies
- **ADR-020:** Trade Attribution Architecture

### Source Code

- **Strategy Manager:** `src/precog/trading/strategy_manager.py`
- **Database Schema:** Migrations 001-010, 023 (strategy_types lookup table)
- **Config Examples:** `src/precog/config/trade_strategies.yaml`

---

**END OF STRATEGY_MANAGER_USER_GUIDE_V1.0.md**
