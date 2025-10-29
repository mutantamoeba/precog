# Precog Versioning Guide

---
**Version:** 1.0
**Created:** 2025-10-21
**Last Updated:** 2025-10-28 (Phase 0.6b - Filename standardization)
**Purpose:** Comprehensive guide to versioning strategies, models, and methods in Precog
**Status:** ✅ Complete
**Filename Updated:** Renamed from VERSIONING_GUIDE_V1.0.md to VERSIONING_GUIDE_V1.0.md (added version number)
---

## Table of Contents

1. [Overview](#overview)
2. [Why Versioning Matters](#why-versioning-matters)
3. [Versioning Philosophy](#versioning-philosophy)
4. [Semantic Versioning](#semantic-versioning)
5. [Lifecycle States](#lifecycle-states)
6. [Database Schema](#database-schema)
7. [Probability Models Versioning](#probability-models-versioning)
8. [Trade Strategies Versioning](#trade-strategies-versioning)
9. [Methods Versioning](#methods-versioning)
10. [A/B Testing Framework](#ab-testing-framework)
11. [Promotion Criteria](#promotion-criteria)
12. [Trade Attribution](#trade-attribution)
13. [Version Management Workflow](#version-management-workflow)
14. [Best Practices](#best-practices)
15. [Common Scenarios](#common-scenarios)
16. [Troubleshooting](#troubleshooting)

---

## Overview

Precog uses **immutable versioning** for all trading components: probability models, strategies, and methods. Once a version is created and used in production, it NEVER changes. This ensures reproducibility, proper A/B testing, and accurate performance attribution.

**Key Principle:** Trade results must be traceable to the EXACT configuration that generated them.

---

## Why Versioning Matters

### The Problem Without Versioning

**Scenario:**
```
Day 1: Deploy elo_nfl model with K-factor = 32
       Trade 50 games, 8% average ROI ✓

Day 5: "Let's try K-factor = 28, might be better"
       Update elo_nfl model in-place

Day 10: Analyze results - now showing 6% average ROI
        Question: Did performance degrade?
        Answer: UNKNOWN - we changed the model mid-stream!
```

**Problem:** Can't compare apples to apples. Historical trades used K=32, recent trades used K=28.

### The Solution: Immutable Versions

```
Day 1: Deploy elo_nfl_v1.0 (K-factor = 32)
       Trade 50 games, 8% average ROI ✓

Day 5: Deploy elo_nfl_v1.1 (K-factor = 28)
       Both versions run in parallel (A/B test)

Day 10: Compare results:
        v1.0: 50 trades, 8.2% avg ROI
        v1.1: 30 trades, 6.1% avg ROI
        Decision: v1.0 wins, deprecate v1.1 ✓
```

**Solution:** Clear attribution. We know v1.0 performed better with statistical significance.

---

## Versioning Philosophy

### Core Principles

1. **Immutability**: Once a version is active, NEVER modify it
2. **Semantic Versioning**: Use v{major}.{minor} format
3. **Explicit Naming**: Include type and sport in name
4. **Lifecycle States**: Draft → Testing → Active → Deprecated
5. **Trade Attribution**: Every trade links to exact version
6. **Retention**: Keep deprecated versions for historical analysis

### What Gets Versioned?

**✅ Versioned:**
- **Probability Models**: elo_nfl_v1.0, regression_nba_v2.3
- **Trade Strategies**: halftime_entry_v1.0, arbitrage_v1.0
- **Methods** (Phase 4+): conservative_nfl_v1.0

**❌ NOT Versioned:**
- Configuration parameters (handled by YAML/database overrides)
- Position management rules (global defaults)
- Market filters (applied system-wide)

---

## Semantic Versioning

### Format: `{type}_{sport}_v{major}.{minor}`

**Examples:**
- `elo_nfl_v1.0` - Elo rating model for NFL, initial version
- `elo_nfl_v1.1` - Elo rating model for NFL, minor tweak
- `elo_nfl_v2.0` - Elo rating model for NFL, major redesign
- `regression_nba_v1.0` - Regression model for NBA, initial version

### Major vs. Minor Versions

**Major Version Change (v1.x → v2.x):**
- Algorithm change (Elo → Regression)
- Complete model redesign
- Different input features
- Incompatible with previous version

**Example:**
```
elo_nfl_v1.0 → elo_nfl_v2.0
Changes:
- Switched from simple Elo to Elo with MOV adjustment
- Added weather factors
- Different home advantage calculation
```

**Minor Version Change (v1.0 → v1.1):**
- Parameter tuning (K-factor 32 → 28)
- Bug fix
- Small feature addition
- Compatible with previous version

**Example:**
```
elo_nfl_v1.0 → elo_nfl_v1.1
Changes:
- K-factor: 32 → 28
- Home advantage: 65 → 70
- Same algorithm, just parameter tweaks
```

### Naming Convention Rules

**Format Components:**
1. **Type**: elo, regression, ensemble, ml, halftime_entry, pre_game_entry, etc.
2. **Sport**: nfl, nba, mlb, tennis, ufc (lowercase)
3. **Version**: v{major}.{minor}

**Valid Names:**
- ✅ `elo_nfl_v1.0`
- ✅ `halftime_entry_nba_v2.3`
- ✅ `ensemble_mlb_v1.0`

**Invalid Names:**
- ❌ `elo_NFL_v1.0` (uppercase sport)
- ❌ `elo_nfl_1.0` (missing 'v')
- ❌ `elo_nfl_v1` (missing minor version)
- ❌ `nfl_elo_v1.0` (wrong order)

---

## Lifecycle States

Every version progresses through distinct lifecycle states:

```
┌───────┐     ┌─────────┐     ┌────────┐     ┌────────────┐
│ DRAFT │ --> │ TESTING │ --> │ ACTIVE │ --> │ DEPRECATED │
└───────┘     └─────────┘     └────────┘     └────────────┘
```

### 1. DRAFT

**Purpose:** Development and initial configuration

**Characteristics:**
- Not yet deployed
- Can be modified freely
- No trades generated
- Used for configuration and setup

**Actions Allowed:**
- ✅ Modify parameters
- ✅ Change algorithm
- ✅ Delete version
- ❌ Generate trades

**Example:**
```sql
INSERT INTO probability_models (
    model_name, model_version, model_type, sport,
    lifecycle_state, created_at
) VALUES (
    'elo_nfl_v1.2', 'v1.2', 'elo', 'nfl',
    'draft', NOW()
);
```

### 2. TESTING

**Purpose:** Evaluation in paper trading or limited live trading

**Characteristics:**
- Deployed with limited exposure
- Generates real trades (but monitored closely)
- IMMUTABLE (no modifications allowed)
- Minimum evaluation period required

**Actions Allowed:**
- ✅ Generate trades (limited)
- ✅ Analyze performance
- ✅ Promote to ACTIVE
- ✅ Deprecate if failing
- ❌ Modify parameters

**Minimum Requirements:**
- **Models**: 30 days, 100 predictions minimum
- **Strategies**: 60 days, 50 trades minimum

**Example:**
```sql
UPDATE probability_models
SET lifecycle_state = 'testing',
    testing_started_at = NOW()
WHERE model_name = 'elo_nfl_v1.2';
```

### 3. ACTIVE

**Purpose:** Production use with full exposure

**Characteristics:**
- In production with full capital allocation
- Generates trades according to traffic split
- IMMUTABLE (no modifications allowed)
- Can coexist with other ACTIVE versions (A/B testing)

**Actions Allowed:**
- ✅ Generate trades (full exposure)
- ✅ Compare performance vs. other ACTIVE versions
- ✅ Deprecate if underperforming
- ❌ Modify parameters

**Example:**
```sql
UPDATE probability_models
SET lifecycle_state = 'active',
    activated_at = NOW()
WHERE model_name = 'elo_nfl_v1.2';
```

### 4. DEPRECATED

**Purpose:** Historical reference, no longer in use

**Characteristics:**
- No longer generates trades
- Retained for historical analysis
- Trade history preserved
- Cannot be reactivated (create new version instead)

**Actions Allowed:**
- ✅ Analyze historical performance
- ✅ Reference in reports
- ✅ Delete after retention period (5 years)
- ❌ Generate new trades
- ❌ Reactivate

**Example:**
```sql
UPDATE probability_models
SET lifecycle_state = 'deprecated',
    deprecated_at = NOW(),
    deprecation_reason = 'Replaced by v1.3 (2% better edge accuracy)'
WHERE model_name = 'elo_nfl_v1.2';
```

### State Transition Rules

**Valid Transitions:**
```
DRAFT → TESTING → ACTIVE → DEPRECATED
         ↓                      ↑
         └──────────────────────┘
         (can skip ACTIVE if fails testing)
```

**Invalid Transitions:**
```
DEPRECATED → ACTIVE  ❌ (create new version instead)
ACTIVE → DRAFT       ❌ (can't undo production deployment)
TESTING → DRAFT      ❌ (testing is one-way, immutable)
```

---

## Database Schema

### probability_models Table

```sql
CREATE TABLE probability_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) UNIQUE NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    sport VARCHAR(20) NOT NULL,

    -- Lifecycle Management
    lifecycle_state VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW(),
    testing_started_at TIMESTAMP,
    activated_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    deprecation_reason TEXT,

    -- Configuration (stored as JSONB for flexibility)
    model_config JSONB NOT NULL,

    -- Performance Tracking
    total_predictions INT DEFAULT 0,
    correct_predictions INT DEFAULT 0,
    edge_accuracy DECIMAL(6,4),
    avg_edge DECIMAL(6,4),

    -- Versioning Metadata
    parent_model_id INT REFERENCES probability_models(model_id),
    change_description TEXT,
    created_by VARCHAR(100),

    CONSTRAINT valid_lifecycle CHECK (
        lifecycle_state IN ('draft', 'testing', 'active', 'deprecated')
    ),
    CONSTRAINT valid_version_format CHECK (
        model_version ~ '^v[0-9]+\.[0-9]+$'
    )
);

-- Index for active model lookups
CREATE INDEX idx_models_active ON probability_models(sport, lifecycle_state)
WHERE lifecycle_state = 'active';
```

### trade_strategies Table

```sql
CREATE TABLE trade_strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) UNIQUE NOT NULL,
    strategy_version VARCHAR(20) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    sport VARCHAR(20) NOT NULL,

    -- Lifecycle Management
    lifecycle_state VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW(),
    testing_started_at TIMESTAMP,
    activated_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    deprecation_reason TEXT,

    -- Configuration
    strategy_config JSONB NOT NULL,

    -- Performance Tracking
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    win_rate DECIMAL(6,4),
    avg_roi DECIMAL(8,4),
    sharpe_ratio DECIMAL(6,4),
    max_drawdown DECIMAL(6,4),

    -- Versioning Metadata
    parent_strategy_id INT REFERENCES trade_strategies(strategy_id),
    change_description TEXT,
    created_by VARCHAR(100),

    CONSTRAINT valid_lifecycle CHECK (
        lifecycle_state IN ('draft', 'testing', 'active', 'deprecated')
    ),
    CONSTRAINT valid_version_format CHECK (
        strategy_version ~ '^v[0-9]+\.[0-9]+$'
    )
);

-- Index for active strategy lookups
CREATE INDEX idx_strategies_active ON trade_strategies(sport, lifecycle_state)
WHERE lifecycle_state = 'active';
```

### Trade Attribution

```sql
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,

    -- Version Attribution (CRITICAL for reproducibility)
    strategy_id INT NOT NULL REFERENCES trade_strategies(strategy_id),
    model_id INT NOT NULL REFERENCES probability_models(model_id),
    method_id INT REFERENCES methods(method_id),  -- Phase 4+

    -- Trade Details
    position_id INT REFERENCES positions(position_id),
    game_id INT REFERENCES games(game_id),

    -- Captured at Trade Time (immutable snapshot)
    strategy_version VARCHAR(20) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    predicted_probability DECIMAL(6,4),
    market_price DECIMAL(10,4),
    edge DECIMAL(6,4),
    kelly_fraction DECIMAL(6,4),

    -- Performance
    roi DECIMAL(8,4),
    pnl DECIMAL(10,4),

    created_at TIMESTAMP DEFAULT NOW()
);

-- Critical index for performance queries by version
CREATE INDEX idx_trades_strategy_version ON trades(strategy_id, strategy_version);
CREATE INDEX idx_trades_model_version ON trades(model_id, model_version);
```

---

## Probability Models Versioning

### Configuration Example: probability_models.yaml

```yaml
versioning:
  enabled: true

  naming_convention: "{model_type}_{sport}_v{major}.{minor}"

  lifecycle:
    require_testing: true
    min_testing_days: 30
    min_testing_predictions: 100
    auto_deprecate_on_replacement: true
    retain_deprecated: true
    retention_years: 5

  ab_testing:
    enabled: true
    default_traffic_split:
      existing_version: 0.80
      new_version: 0.20

    promotion_criteria:
      min_improvement_pct: 0.02  # 2% better edge accuracy
      min_evaluation_period_days: 30
      confidence_level: 0.95
```

### Creating a New Model Version

**Step 1: Create in DRAFT state**

```sql
INSERT INTO probability_models (
    model_name,
    model_version,
    model_type,
    sport,
    lifecycle_state,
    model_config,
    parent_model_id,
    change_description,
    created_by
) VALUES (
    'elo_nfl_v1.1',
    'v1.1',
    'elo',
    'nfl',
    'draft',
    '{"k_factor": 28, "home_advantage": 70, "mov_adjustment": true}'::jsonb,
    1,  -- parent is elo_nfl_v1.0
    'Reduced K-factor from 32 to 28 based on overfitting analysis',
    'alice@precog.com'
);
```

**Step 2: Test thoroughly in DRAFT**

```python
# Load draft model
model = ProbabilityModel.load('elo_nfl_v1.1')

# Backtest on historical data
results = backtest(model, start_date='2023-01-01', end_date='2023-12-31')

# Verify edge accuracy
print(f"Edge Accuracy: {results.edge_accuracy:.2%}")
print(f"Average Edge: {results.avg_edge:.2%}")

# If satisfactory, promote to TESTING
```

**Step 3: Promote to TESTING**

```sql
UPDATE probability_models
SET lifecycle_state = 'testing',
    testing_started_at = NOW()
WHERE model_name = 'elo_nfl_v1.1';
```

**Step 4: A/B Test in Production**

```yaml
# probability_models.yaml
active_models:
  nfl:
    - model_name: elo_nfl_v1.0
      traffic_pct: 0.80  # Existing champion
    - model_name: elo_nfl_v1.1
      traffic_pct: 0.20  # New challenger
```

**Step 5: Evaluate and Promote/Deprecate**

After 30 days and 100+ predictions:

```sql
-- Check performance
SELECT
    model_name,
    total_predictions,
    edge_accuracy,
    avg_edge
FROM probability_models
WHERE model_name IN ('elo_nfl_v1.0', 'elo_nfl_v1.1');

-- Result:
-- elo_nfl_v1.0: 400 predictions, 65.2% edge_accuracy, 6.8% avg_edge
-- elo_nfl_v1.1: 100 predictions, 67.5% edge_accuracy, 7.1% avg_edge

-- v1.1 is 2.3% better → Promote to ACTIVE
UPDATE probability_models
SET lifecycle_state = 'active',
    activated_at = NOW()
WHERE model_name = 'elo_nfl_v1.1';

-- Deprecate v1.0
UPDATE probability_models
SET lifecycle_state = 'deprecated',
    deprecated_at = NOW(),
    deprecation_reason = 'Replaced by v1.1 (2.3% better edge accuracy)'
WHERE model_name = 'elo_nfl_v1.0';
```

---

## Trade Strategies Versioning

### Configuration Example: trade_strategies.yaml

```yaml
versioning:
  enabled: true

  naming_convention: "{strategy_type}_{sport}_v{major}.{minor}"

  lifecycle:
    require_testing: true
    min_testing_days: 60  # Longer than models (more conservative)
    min_testing_trades: 50
    auto_deprecate_on_replacement: true
    retain_deprecated: true
    retention_years: 5

  ab_testing:
    enabled: true
    default_traffic_split:
      existing_version: 0.70  # More conservative than models
      new_version: 0.30

    promotion_criteria:
      min_improvement_pct: 0.05  # 5% better Sharpe ratio
      min_evaluation_period_days: 60
      confidence_level: 0.95
      min_trade_count: 50

    comparison_metrics:
      - "sharpe_ratio"
      - "win_rate"
      - "avg_profit_per_trade"
      - "max_drawdown"
      - "edge_accuracy"
```

### Creating a New Strategy Version

**Example: Improving Halftime Entry Strategy**

**v1.0 (Current):**
```json
{
    "strategy_type": "halftime_entry",
    "min_edge": 0.06,
    "max_minutes_into_halftime": 10,
    "analysis_factors": {
        "possession_yardage": 0.40,
        "score_differential": 0.20,
        "turnover_margin": 0.20,
        "time_of_possession": 0.20
    }
}
```

**v1.1 (Improvement Hypothesis):**
```json
{
    "strategy_type": "halftime_entry",
    "min_edge": 0.05,  # Lower threshold to capture more opportunities
    "max_minutes_into_halftime": 10,
    "analysis_factors": {
        "possession_yardage": 0.35,  # Reduce weight
        "score_differential": 0.25,  # Increase weight
        "turnover_margin": 0.25,     # Increase weight
        "time_of_possession": 0.15   # Reduce weight
    }
}
```

**Deployment:**

```sql
-- Create v1.1
INSERT INTO trade_strategies (
    strategy_name,
    strategy_version,
    strategy_type,
    sport,
    lifecycle_state,
    strategy_config,
    parent_strategy_id,
    change_description,
    created_by
) VALUES (
    'halftime_entry_nfl_v1.1',
    'v1.1',
    'halftime_entry',
    'nfl',
    'testing',
    '{"min_edge": 0.05, "max_minutes_into_halftime": 10, ...}'::jsonb,
    1,  # parent is halftime_entry_nfl_v1.0
    'Rebalanced analysis factors, lowered min_edge to 5%',
    'bob@precog.com'
);

-- A/B test with 70/30 split
-- 70% of capital to v1.0 (proven)
-- 30% of capital to v1.1 (challenger)
```

**Evaluation After 60 Days:**

```sql
SELECT
    s.strategy_name,
    s.total_trades,
    s.win_rate,
    s.avg_roi,
    s.sharpe_ratio,
    s.max_drawdown
FROM trade_strategies s
WHERE s.strategy_name IN ('halftime_entry_nfl_v1.0', 'halftime_entry_nfl_v1.1');

-- Result:
-- v1.0: 35 trades, 62.8% win_rate, 8.2% avg_roi, 1.85 sharpe, -12% drawdown
-- v1.1: 62 trades, 64.5% win_rate, 8.6% avg_roi, 1.95 sharpe, -10% drawdown

-- v1.1 wins:
-- - 5.4% better Sharpe ratio (1.95 vs 1.85)
-- - More trades (62 vs 35) → better sample size
-- - Lower drawdown (-10% vs -12%)
```

**Decision: Promote v1.1, Deprecate v1.0**

```sql
UPDATE trade_strategies
SET lifecycle_state = 'active',
    activated_at = NOW()
WHERE strategy_name = 'halftime_entry_nfl_v1.1';

UPDATE trade_strategies
SET lifecycle_state = 'deprecated',
    deprecated_at = NOW(),
    deprecation_reason = 'Replaced by v1.1 (5.4% better Sharpe, 77% more trades)'
WHERE strategy_name = 'halftime_entry_nfl_v1.0';
```

---

## Methods Versioning

### Overview (Phase 4-5)

Methods bundle complete configurations: strategy + model + position management + risk + execution.

**See ADR-021 for complete specification.**

### Method Naming

```
Format: {style}_{sport}_v{major}.{minor}

Examples:
- conservative_nfl_v1.0
- aggressive_nba_v2.0
- arbitrage_mlb_v1.1
```

### Method Lifecycle

Same as models and strategies:
- DRAFT → TESTING → ACTIVE → DEPRECATED

### Method Versioning Example

```json
{
    "method_id": 1,
    "method_name": "conservative_nfl_v1.0",
    "method_version": "v1.0",
    "lifecycle_state": "active",

    "strategy_id": 1,  // halftime_entry_nfl_v1.1
    "model_id": 2,     // elo_nfl_v1.1

    "position_mgmt_config": {
        "trailing_stop": {"enabled": true, "activation_threshold": 0.10},
        "profit_targets": {"high_confidence": 0.20},
        "stop_loss": {"high_confidence": -0.10}
    },

    "risk_config": {
        "kelly_fraction": 0.15,
        "max_position_size_dollars": 500
    }
}
```

**Trade Attribution Chain:**

```
Trade → Method → Strategy + Model
  ↓        ↓          ↓        ↓
trade_id method_id strategy_id model_id
  123      1          1         2

Complete attribution:
- Method: conservative_nfl_v1.0
- Strategy: halftime_entry_nfl_v1.1
- Model: elo_nfl_v1.1
- Position config: trailing_stop enabled, 20% profit target
- Risk config: 0.15 Kelly fraction
```

---

## A/B Testing Framework

### Purpose

Compare two versions side-by-side with real capital to determine which performs better.

### Traffic Splits

**Models: 80/20 Split (Less Conservative)**
- 80% to existing champion
- 20% to new challenger
- Reason: Models have shorter feedback loops (predictions)

**Strategies: 70/30 Split (More Conservative)**
- 70% to existing champion
- 30% to new challenger
- Reason: Strategies have longer feedback loops (full trade lifecycle)

### Implementation

**Configuration:**

```yaml
# probability_models.yaml
active_models:
  nfl:
    - model_name: elo_nfl_v1.0
      traffic_pct: 0.80
      lifecycle_state: active

    - model_name: elo_nfl_v1.1
      traffic_pct: 0.20
      lifecycle_state: testing
```

**Code:**

```python
def select_model(sport: str) -> ProbabilityModel:
    """Select model based on traffic split for A/B testing"""
    active_models = get_active_models(sport)

    # Weight by traffic percentage
    weights = [m.traffic_pct for m in active_models]

    # Random selection based on weights
    selected = random.choices(active_models, weights=weights)[0]

    return selected
```

### A/B Test Duration

**Minimum Evaluation Periods:**

| Component | Min Days | Min Samples | Reason |
|-----------|----------|-------------|--------|
| Probability Model | 30 | 100 predictions | Need statistical significance |
| Trade Strategy | 60 | 50 trades | Longer feedback loop |
| Method | 60 | 50 trades | Bundle includes strategy |

**Why These Minimums?**

Statistical significance requires:
- Large enough sample size (Central Limit Theorem)
- Sufficient time to experience different market conditions
- Multiple weeks/weekends (sports seasonality)

### Statistical Significance

**Requirements:**
- Confidence Level: 95% (p < 0.05)
- Minimum Improvement: 2% for models, 5% for strategies
- Sufficient sample size (calculated via power analysis)

**Example Calculation:**

```python
from scipy import stats

def is_significantly_better(v1_results, v2_results, min_improvement=0.02):
    """Test if v2 is significantly better than v1"""

    # T-test for difference in means
    t_stat, p_value = stats.ttest_ind(v1_results, v2_results)

    # Check significance (p < 0.05)
    is_significant = p_value < 0.05

    # Check minimum improvement threshold
    improvement = (v2_results.mean() - v1_results.mean()) / v1_results.mean()
    meets_threshold = improvement >= min_improvement

    return is_significant and meets_threshold

# Example usage
v1_edge_accuracy = [0.65, 0.64, 0.66, ...]  # 100 samples
v2_edge_accuracy = [0.67, 0.68, 0.66, ...]  # 100 samples

if is_significantly_better(v1_edge_accuracy, v2_edge_accuracy, min_improvement=0.02):
    promote_to_active(v2)
    deprecate(v1)
```

---

## Promotion Criteria

### Probability Models

**Must Meet ALL Criteria:**

1. ✅ **Minimum Evaluation Period**: 30 days
2. ✅ **Minimum Sample Size**: 100 predictions
3. ✅ **Statistical Significance**: p < 0.05
4. ✅ **Minimum Improvement**: 2% better edge accuracy
5. ✅ **No Degradation**: No other metrics significantly worse

**Example:**

```
Champion: elo_nfl_v1.0
- Edge Accuracy: 65.2%
- Average Edge: 6.8%
- Sample: 400 predictions over 45 days

Challenger: elo_nfl_v1.1
- Edge Accuracy: 67.5% (+2.3%) ✓
- Average Edge: 7.1% (+0.3%) ✓
- Sample: 100 predictions over 30 days ✓
- p-value: 0.018 (< 0.05) ✓

Decision: Promote v1.1 to ACTIVE, Deprecate v1.0 ✓
```

### Trade Strategies

**Must Meet ALL Criteria:**

1. ✅ **Minimum Evaluation Period**: 60 days
2. ✅ **Minimum Sample Size**: 50 trades
3. ✅ **Statistical Significance**: p < 0.05
4. ✅ **Minimum Improvement**: 5% better Sharpe ratio
5. ✅ **Multi-Metric Validation**: Better on ≥3 of 5 key metrics
6. ✅ **No Critical Degradation**: Max drawdown not significantly worse

**Key Metrics:**
1. Sharpe Ratio (primary)
2. Win Rate
3. Average Profit Per Trade
4. Max Drawdown
5. Edge Accuracy

**Example:**

```
Champion: halftime_entry_nfl_v1.0
- Sharpe: 1.85
- Win Rate: 62.8%
- Avg Profit: $8.20
- Max Drawdown: -12%
- Sample: 35 trades over 60 days

Challenger: halftime_entry_nfl_v1.1
- Sharpe: 1.95 (+5.4%) ✓
- Win Rate: 64.5% (+1.7%) ✓
- Avg Profit: $8.60 (+4.9%) ✓
- Max Drawdown: -10% (better) ✓
- Sample: 62 trades over 60 days ✓
- p-value: 0.032 (< 0.05) ✓
- Better on 5/5 metrics ✓

Decision: Promote v1.1 to ACTIVE, Deprecate v1.0 ✓
```

---

## Trade Attribution

### Complete Attribution Chain

Every trade must be traceable to exact versions:

```
Trade #123
├─ Method: conservative_nfl_v1.0
│   ├─ Strategy: halftime_entry_nfl_v1.1
│   │   └─ Config: min_edge=0.05, max_minutes=10
│   ├─ Model: elo_nfl_v1.1
│   │   └─ Config: k_factor=28, home_adv=70
│   ├─ Position Mgmt: trailing_stop=enabled (10% activation)
│   ├─ Risk: kelly_fraction=0.15, max_position=$500
│   └─ Execution: limit orders, 2% max slippage
└─ Result: +$12.50 ROI (+15.2%)
```

### Database Implementation

```sql
-- trades table captures COMPLETE version snapshot
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,

    -- Version IDs (foreign keys)
    strategy_id INT NOT NULL REFERENCES trade_strategies(strategy_id),
    model_id INT NOT NULL REFERENCES probability_models(model_id),
    method_id INT REFERENCES methods(method_id),

    -- Version Names (redundant but useful for queries)
    strategy_version VARCHAR(20) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    method_version VARCHAR(20),

    -- Configuration Snapshot (captured at trade time)
    config_snapshot JSONB NOT NULL,

    -- Trade details...
    position_id INT,
    predicted_probability DECIMAL(6,4),
    actual_outcome BOOLEAN,
    roi DECIMAL(8,4),

    created_at TIMESTAMP DEFAULT NOW()
);

-- Example query: Performance by model version
SELECT
    model_version,
    COUNT(*) as trades,
    AVG(roi) as avg_roi,
    STDDEV(roi) as volatility,
    AVG(CASE WHEN actual_outcome = (predicted_probability > 0.5)
        THEN 1.0 ELSE 0.0 END) as edge_accuracy
FROM trades
WHERE model_id IN (
    SELECT model_id FROM probability_models
    WHERE model_type = 'elo' AND sport = 'nfl'
)
GROUP BY model_version
ORDER BY model_version;

-- Result:
-- v1.0: 450 trades, 8.2% avg_roi, 12.5% volatility, 65.2% edge_accuracy
-- v1.1: 180 trades, 8.6% avg_roi, 11.8% volatility, 67.5% edge_accuracy
-- v1.2: 62 trades, 9.1% avg_roi, 13.2% volatility, 69.1% edge_accuracy
```

---

## Version Management Workflow

### Creating a New Version

**Step 1: Clone Existing Version**

```sql
-- Clone elo_nfl_v1.0 → elo_nfl_v1.1
INSERT INTO probability_models (
    model_name, model_version, model_type, sport,
    lifecycle_state, model_config, parent_model_id,
    change_description
)
SELECT
    'elo_nfl_v1.1',  -- New name
    'v1.1',          -- New version
    model_type,
    sport,
    'draft',         -- Start in DRAFT
    model_config,    -- Copy config (will modify next)
    model_id,        -- Link to parent
    'Cloned from v1.0 for K-factor tuning'
FROM probability_models
WHERE model_name = 'elo_nfl_v1.0';
```

**Step 2: Modify Configuration**

```sql
-- Update K-factor in cloned version
UPDATE probability_models
SET model_config = jsonb_set(
    model_config,
    '{k_factor}',
    '28'  -- Was 32
)
WHERE model_name = 'elo_nfl_v1.1';
```

**Step 3: Test in DRAFT**

```python
# Load draft model
model = ProbabilityModel.load('elo_nfl_v1.1')

# Backtest
results = backtest(model, historical_data)
print(f"Backtest ROI: {results.roi:.2%}")

# Paper trade for 1 week
paper_trade(model, duration_days=7)
```

**Step 4: Promote to TESTING**

```sql
UPDATE probability_models
SET lifecycle_state = 'testing',
    testing_started_at = NOW()
WHERE model_name = 'elo_nfl_v1.1';
```

**Step 5: A/B Test**

```yaml
# Update probability_models.yaml
active_models:
  nfl:
    - model_name: elo_nfl_v1.0
      traffic_pct: 0.80
    - model_name: elo_nfl_v1.1
      traffic_pct: 0.20
```

**Step 6: Monitor Performance**

```sql
-- Daily performance check
SELECT
    model_version,
    COUNT(*) as predictions_today,
    AVG(edge_accuracy) as edge_accuracy
FROM trades
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY model_version;
```

**Step 7: Promote or Deprecate**

After 30 days and 100 predictions:

```sql
-- If successful: Promote to ACTIVE
UPDATE probability_models
SET lifecycle_state = 'active',
    activated_at = NOW()
WHERE model_name = 'elo_nfl_v1.1';

-- Deprecate old version
UPDATE probability_models
SET lifecycle_state = 'deprecated',
    deprecated_at = NOW(),
    deprecation_reason = 'Replaced by v1.1'
WHERE model_name = 'elo_nfl_v1.0';

-- If unsuccessful: Deprecate challenger
UPDATE probability_models
SET lifecycle_state = 'deprecated',
    deprecated_at = NOW(),
    deprecation_reason = 'Failed A/B test, no improvement'
WHERE model_name = 'elo_nfl_v1.1';
```

---

## Best Practices

### DO ✅

1. **Always Use Semantic Versioning**
   ```
   ✅ elo_nfl_v1.0, elo_nfl_v1.1, elo_nfl_v2.0
   ❌ elo_nfl_new, elo_nfl_final, elo_nfl_v2
   ```

2. **Document Changes Clearly**
   ```sql
   change_description = 'Reduced K-factor from 32 to 28 to reduce overfitting on recent games'
   ```

3. **Test Thoroughly Before Production**
   - Backtest on historical data
   - Paper trade for minimum period
   - Review edge accuracy and ROI

4. **Use A/B Testing for All Major Changes**
   - Don't deploy untested versions to 100% traffic
   - Start with 20-30% traffic split
   - Evaluate with statistical rigor

5. **Preserve Historical Data**
   - Keep deprecated versions for 5 years
   - Maintain trade attribution forever
   - Never delete active/deprecated versions

6. **Link Versions to Parents**
   ```sql
   parent_model_id = 1  -- Links v1.1 back to v1.0
   ```

7. **Capture Configuration Snapshots**
   ```sql
   config_snapshot JSONB  -- Save exact config at trade time
   ```

### DON'T ❌

1. **Never Modify Active Versions**
   ```
   ❌ UPDATE model_config WHERE model_name = 'elo_nfl_v1.0'
   ✅ Create elo_nfl_v1.1 with new config
   ```

2. **Don't Reuse Version Numbers**
   ```
   ❌ Deprecate v1.1, then create new v1.1 with different config
   ✅ Create v1.2 instead
   ```

3. **Don't Skip Testing Phase**
   ```
   ❌ DRAFT → ACTIVE (skip testing)
   ✅ DRAFT → TESTING → ACTIVE
   ```

4. **Don't Promote Too Early**
   ```
   ❌ Promote after 10 days, 30 predictions
   ✅ Wait for 30 days, 100 predictions minimum
   ```

5. **Don't Ignore Statistical Significance**
   ```
   ❌ "v1.1 is 1% better, close enough!"
   ✅ Wait for p < 0.05 and minimum improvement threshold
   ```

6. **Don't Delete Deprecated Versions**
   ```
   ❌ DELETE FROM probability_models WHERE lifecycle_state = 'deprecated'
   ✅ Keep for historical analysis (5 year retention)
   ```

---

## Common Scenarios

### Scenario 1: Parameter Tuning

**Situation:** Want to test different K-factor for Elo model

**Solution:**

1. Clone v1.0 → v1.1 (DRAFT)
2. Change K-factor: 32 → 28
3. Backtest on historical data
4. Promote to TESTING
5. A/B test 80/20 for 30 days
6. Compare edge accuracy
7. Promote winner, deprecate loser

**Time:** ~35 days (5 days prep + 30 days A/B test)

### Scenario 2: Algorithm Redesign

**Situation:** Switching from simple Elo to Elo with MOV adjustment

**Solution:**

1. Create v2.0 (DRAFT) - major version bump
2. Implement new algorithm
3. Extensive backtesting (1+ years historical data)
4. Paper trade for 2 weeks
5. Promote to TESTING
6. A/B test 80/20 for 45 days (longer for major change)
7. Multi-metric validation
8. Promote winner, deprecate loser

**Time:** ~65 days (20 days prep + 45 days A/B test)

### Scenario 3: Bug Fix

**Situation:** Discovered bug in v1.0 causing incorrect home advantage calculation

**Solution:**

1. Immediately create v1.1 (DRAFT) with fix
2. Verify fix with unit tests
3. Backtest to confirm improvement
4. Promote directly to ACTIVE (bug fixes can skip extended testing)
5. Deprecate v1.0 immediately
6. Update traffic split: v1.1 = 100%

**Time:** ~2 days (immediate fix)

**Note:** Document as bug fix in change_description

### Scenario 4: Multi-Sport Expansion

**Situation:** Have elo_nfl_v1.0, want to add NBA

**Solution:**

1. Create elo_nba_v1.0 (DRAFT)
2. Start with NFL config as template
3. Tune sport-specific parameters (K-factor, home advantage)
4. Backtest on NBA historical data
5. Paper trade for 30 days
6. Promote to TESTING
7. A/B test if replacing existing NBA model, or deploy to 100% if first NBA model
8. Promote to ACTIVE

**Time:** ~40 days (10 days prep + 30 days testing)

### Scenario 5: Rollback

**Situation:** v1.1 deployed, but causing issues in production

**Solution:**

1. **Immediate:** Deprecate v1.1
   ```sql
   UPDATE probability_models
   SET lifecycle_state = 'deprecated',
       deprecation_reason = 'Production issues - rollback'
   WHERE model_name = 'elo_nfl_v1.1';
   ```

2. **Reactivate v1.0** (only if needed urgently)
   ```sql
   UPDATE probability_models
   SET lifecycle_state = 'active'
   WHERE model_name = 'elo_nfl_v1.0';
   ```

3. **Update traffic split:**
   ```yaml
   active_models:
     nfl:
       - model_name: elo_nfl_v1.0
         traffic_pct: 1.00  # Back to 100%
   ```

4. **Investigate and fix** v1.1 issues
5. **Create v1.2** with fixes
6. **Repeat testing process**

**Time:** Immediate rollback (< 1 hour)

---

## Troubleshooting

### Issue: Can't Modify Active Version

**Error:**
```sql
ERROR: Cannot modify model in 'active' lifecycle state
```

**Solution:**
Create new version instead:
```sql
-- Clone to new version
INSERT INTO probability_models (...)
SELECT ... FROM probability_models WHERE model_name = 'elo_nfl_v1.0';

-- Modify new version
UPDATE probability_models SET model_config = ...
WHERE model_name = 'elo_nfl_v1.1' AND lifecycle_state = 'draft';
```

### Issue: Duplicate Version Name

**Error:**
```sql
ERROR: duplicate key value violates unique constraint "probability_models_model_name_key"
```

**Solution:**
Check existing versions and increment properly:
```sql
-- Check existing versions
SELECT model_name, model_version, lifecycle_state
FROM probability_models
WHERE model_type = 'elo' AND sport = 'nfl'
ORDER BY model_version;

-- Use next available version
-- If v1.0, v1.1 exist, use v1.2
```

### Issue: Trade Attribution Missing

**Problem:** Trades not linking to correct version

**Solution:**
Verify foreign keys and version capture:
```sql
-- Check trade attribution
SELECT
    t.trade_id,
    t.strategy_version,
    t.model_version,
    s.strategy_name,
    m.model_name
FROM trades t
LEFT JOIN trade_strategies s ON t.strategy_id = s.strategy_id
LEFT JOIN probability_models m ON t.model_id = m.model_id
WHERE t.trade_id = 123;

-- If NULL, fix trade creation code to capture versions:
INSERT INTO trades (strategy_id, model_id, strategy_version, model_version, ...)
VALUES (
    1,
    2,
    (SELECT strategy_version FROM trade_strategies WHERE strategy_id = 1),
    (SELECT model_version FROM probability_models WHERE model_id = 2),
    ...
);
```

### Issue: A/B Test Not Splitting Traffic

**Problem:** All traffic going to one version

**Solution:**
Check traffic split configuration:
```python
# Verify weights sum to 1.0
active_models = get_active_models('nfl')
total_weight = sum(m.traffic_pct for m in active_models)
assert abs(total_weight - 1.0) < 0.01, f"Weights sum to {total_weight}, not 1.0"

# Verify random selection working
for _ in range(100):
    selected = select_model('nfl')
    print(selected.model_name)
# Should see both versions ~80/20 split
```

### Issue: Version Not Meeting Promotion Criteria

**Problem:** v1.1 better but not significantly

**Result:**
```
v1.0: 65.2% edge accuracy (400 samples)
v1.1: 66.1% edge accuracy (100 samples)
Improvement: +0.9% (< 2% threshold)
p-value: 0.08 (> 0.05)
```

**Solution:**
- Continue A/B test for longer period
- Collect more samples
- Re-evaluate after 200 samples or 60 days
- If still not significant, deprecate v1.1 (no improvement)

---

## Summary

**Key Takeaways:**

1. ✅ **Immutability is Critical** - Never modify active versions
2. ✅ **Semantic Versioning** - Use v{major}.{minor} format consistently
3. ✅ **Lifecycle States** - Progress through DRAFT → TESTING → ACTIVE → DEPRECATED
4. ✅ **A/B Testing** - Compare versions side-by-side with real data
5. ✅ **Statistical Rigor** - Require significance and minimum improvement
6. ✅ **Trade Attribution** - Link every trade to exact versions used
7. ✅ **Historical Retention** - Preserve deprecated versions for analysis

**Benefits:**

- ✅ Reproducible results
- ✅ Clear performance comparison
- ✅ Accurate attribution
- ✅ Evidence-based iteration
- ✅ Audit trail for compliance

---

**Document:** VERSIONING_GUIDE_V1.0.md
**Version:** 1.0
**Created:** 2025-10-21
**Last Updated:** 2025-10-21
**Status:** ✅ Complete and validated
