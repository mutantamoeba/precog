# A/B Testing Guide V1.0

---
**Version:** 1.0
**Created:** 2025-11-13
**Last Updated:** 2025-11-13
**Phase:** 8 (Model Evaluation & A/B Testing)
**Purpose:** Comprehensive A/B testing methodology for strategy and model evaluation
**Target Audience:** Data scientists, developers implementing experiment tracking
**Related ADRs:** ADR-083 (A/B Testing Methodology)
**Related Requirements:** REQ-ANALYTICS-003 (A/B Testing Infrastructure)
**Related Documents:** VERSIONING_GUIDE_V1.0.md, PERFORMANCE_TRACKING_GUIDE_V1.0.md, MODEL_EVALUATION_GUIDE_V1.0.md
---

## Table of Contents

1. [Overview](#overview)
2. [A/B Testing Fundamentals](#ab-testing-fundamentals)
3. [Experiment Design](#experiment-design)
4. [Database Schema](#database-schema)
5. [Backend Implementation](#backend-implementation)
6. [Statistical Analysis](#statistical-analysis)
7. [Dashboard Integration](#dashboard-integration)
8. [Best Practices](#best-practices)
9. [Common Pitfalls](#common-pitfalls)
10. [Example Experiments](#example-experiments)

---

## 1. Overview

### Purpose

A/B testing enables **rigorous comparison** of trading strategies and probability models to determine which version performs better before full deployment.

**Why A/B Testing Matters:**
- **Data-driven decisions**: Replace gut feelings with statistical evidence
- **Risk mitigation**: Test new strategies on small capital before scaling
- **Continuous improvement**: Iterate strategies based on measured performance
- **Version accountability**: Ensure new versions actually improve results

### Precog A/B Testing Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Experiment Definition                      │
│  - Hypothesis: "Strategy v1.1 increases win rate by 5%"     │
│  - Control: strategy v1.0, model v2.0                        │
│  - Treatment: strategy v1.1, model v2.0                      │
│  - Traffic Split: 50/50                                      │
│  - Duration: 30 days                                         │
│  - Primary Metric: Win Rate                                  │
│  - Secondary Metrics: Net P&L, Sharpe Ratio                 │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Assignment & Execution Engine                   │
│  - Random assignment (market → variant, 50/50 split)        │
│  - Execute trades using assigned strategy/model version     │
│  - Track all trades with experiment_id + variant            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Metrics Collection & Aggregation                │
│  - Aggregate performance_tracking by experiment + variant    │
│  - Calculate: Win Rate, Net P&L, Sharpe Ratio, etc.        │
│  - Store in: ab_test_results table                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Statistical Significance Testing                │
│  - T-test: Is win rate difference statistically significant?│
│  - Chi-square: Are win/loss distributions different?        │
│  - Bayesian: Probability that treatment > control           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Dashboard & Reporting                      │
│  - Real-time experiment progress                            │
│  - Statistical significance indicators                       │
│  - Performance comparison charts                            │
│  - Confidence intervals                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. A/B Testing Fundamentals

### Core Concepts

**Null Hypothesis (H₀):**
> There is **no difference** in performance between control and treatment.

**Alternative Hypothesis (H₁):**
> Treatment performs **significantly better** than control.

**Statistical Significance:**
- **p-value < 0.05**: Reject null hypothesis (treatment IS better)
- **p-value ≥ 0.05**: Fail to reject null hypothesis (no conclusive evidence)

**Effect Size:**
- **Small effect**: Cohen's d = 0.2
- **Medium effect**: Cohen's d = 0.5
- **Large effect**: Cohen's d = 0.8

### When to Use A/B Testing

**✅ Good Use Cases:**
- Testing new strategy versions (e.g., v1.0 vs. v1.1 with different Kelly fractions)
- Comparing probability models (e.g., XGBoost vs. LightGBM)
- Evaluating entry/exit rule changes
- Testing different trailing stop configurations

**❌ Poor Use Cases:**
- Testing on insufficient sample size (<30 trades per variant)
- Testing multiple changes simultaneously (can't isolate cause)
- Testing without clear hypothesis or success criteria
- Testing on correlated markets (violates independence assumption)

---

## 3. Experiment Design

### Experiment Lifecycle

```
1. Design → 2. Launch → 3. Monitor → 4. Analyze → 5. Decide
```

### Step 1: Design Experiment

**Define Hypothesis:**
```markdown
**Hypothesis:** Increasing Kelly fraction from 0.25 to 0.30 improves net P&L
**Control:** Strategy v1.0 (kelly_fraction: 0.25)
**Treatment:** Strategy v1.1 (kelly_fraction: 0.30)
**Primary Metric:** Net P&L per trade
**Secondary Metrics:** Win Rate, Sharpe Ratio, Max Drawdown
**Success Criteria:** p-value < 0.05 AND treatment P&L > control P&L by ≥10%
```

**Calculate Sample Size:**
```python
from scipy.stats import power

# Parameters
alpha = 0.05  # Significance level (5% false positive rate)
beta = 0.20   # Power = 1 - beta = 80% (20% false negative rate)
effect_size = 0.5  # Medium effect (Cohen's d)

# Calculate required sample size per variant
n = power.tt_ind_solve_power(effect_size=effect_size, alpha=alpha, power=0.8, ratio=1.0)
print(f"Required sample size per variant: {int(n)} trades")
# Output: Required sample size per variant: 64 trades
# Total trades needed: 64 x 2 = 128 trades
```

### Step 2: Launch Experiment

**Create Experiment Record:**
```sql
INSERT INTO ab_tests (
    experiment_name,
    hypothesis,
    control_strategy_id,
    treatment_strategy_id,
    control_model_id,
    treatment_model_id,
    traffic_split,
    start_date,
    planned_end_date,
    primary_metric,
    secondary_metrics,
    status
) VALUES (
    'kelly_fraction_030_test',
    'Increasing Kelly fraction from 0.25 to 0.30 improves net P&L',
    1,  -- strategy v1.0 (kelly_fraction=0.25)
    2,  -- strategy v1.1 (kelly_fraction=0.30)
    10, -- model v2.0
    10, -- model v2.0 (same model for both variants)
    0.50, -- 50/50 traffic split
    '2025-11-13',
    '2025-12-13',  -- 30-day test
    'net_pnl_per_trade',
    '{"win_rate", "sharpe_ratio", "max_drawdown"}',
    'running'
);
```

**Assignment Logic (Python):**
```python
import random
from typing import Literal

def assign_variant(market_id: int, experiment_id: int, traffic_split: float = 0.5) -> Literal['control', 'treatment']:
    """
    Randomly assign market to control or treatment variant.

    Args:
        market_id: Market identifier (used as random seed for consistency)
        experiment_id: Experiment identifier
        traffic_split: Fraction of traffic to treatment (0.5 = 50/50 split)

    Returns:
        'control' or 'treatment'

    Educational Note:
        - Uses market_id as seed for **deterministic** assignment
        - Same market always gets same variant (prevents contamination)
        - Random but reproducible (re-running gives same result)
    """
    random.seed(f"{experiment_id}_{market_id}")
    return 'treatment' if random.random() < traffic_split else 'control'

# Example usage
variant = assign_variant(market_id=12345, experiment_id=1, traffic_split=0.5)
print(f"Market 12345 assigned to: {variant}")  # Always same result for this market
```

### Step 3: Monitor Experiment

**Check Sample Size Progress:**
```sql
SELECT
    variant,
    COUNT(*) AS trades_count,
    AVG(realized_pnl - total_fees) AS avg_net_pnl,
    STDDEV(realized_pnl - total_fees) AS stddev_net_pnl
FROM ab_test_results
WHERE experiment_id = 1
GROUP BY variant;
```

**Expected Output:**
```
variant   | trades_count | avg_net_pnl | stddev_net_pnl
----------|--------------|-------------|----------------
control   | 42           | $2.50       | $5.20
treatment | 45           | $3.20       | $4.80
```

**Stop Early if:**
- ❌ **Safety threshold violated**: Treatment Max Drawdown > 25% (vs. control 15%)
- ❌ **Sample Ratio Mismatch**: 60/40 split observed (expected 50/50) → assignment bug
- ✅ **Clear winner emerges**: p-value < 0.01 and effect size > 0.8 (very strong signal)

---

## 4. Database Schema

### ab_tests Table (Experiment Metadata)

```sql
CREATE TABLE ab_tests (
    experiment_id SERIAL PRIMARY KEY,
    experiment_name VARCHAR(100) NOT NULL UNIQUE,
    hypothesis TEXT NOT NULL,
    control_strategy_id INTEGER REFERENCES strategies(strategy_id),
    treatment_strategy_id INTEGER REFERENCES strategies(strategy_id),
    control_model_id INTEGER REFERENCES probability_models(model_id),
    treatment_model_id INTEGER REFERENCES probability_models(model_id),
    traffic_split DECIMAL(3, 2) NOT NULL DEFAULT 0.50,  -- 0.50 = 50/50 split
    start_date DATE NOT NULL,
    planned_end_date DATE,
    actual_end_date DATE,
    primary_metric VARCHAR(50) NOT NULL,  -- 'win_rate', 'net_pnl_per_trade', etc.
    secondary_metrics JSONB,
    min_sample_size INTEGER DEFAULT 64,  -- Minimum trades per variant
    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- 'draft', 'running', 'stopped', 'completed'
    winner VARCHAR(20),  -- 'control', 'treatment', 'no_difference'
    p_value DECIMAL(5, 4),
    effect_size DECIMAL(5, 3),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### ab_test_results Table (Per-Trade Results)

```sql
CREATE TABLE ab_test_results (
    result_id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES ab_tests(experiment_id),
    variant VARCHAR(20) NOT NULL,  -- 'control' or 'treatment'
    trade_id INTEGER NOT NULL REFERENCES trades(trade_id),
    position_id INTEGER NOT NULL REFERENCES positions(position_id),
    market_id INTEGER NOT NULL REFERENCES markets(market_id),
    strategy_id INTEGER NOT NULL REFERENCES strategies(strategy_id),
    model_id INTEGER NOT NULL REFERENCES probability_models(model_id),
    realized_pnl DECIMAL(12, 4),
    total_fees DECIMAL(12, 4),
    net_pnl DECIMAL(12, 4) GENERATED ALWAYS AS (realized_pnl - total_fees) STORED,
    win BOOLEAN,  -- TRUE if net_pnl > 0
    exit_timestamp TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_experiment_trade UNIQUE (experiment_id, trade_id)
);

CREATE INDEX idx_ab_test_results_experiment ON ab_test_results(experiment_id, variant);
```

---

## 5. Backend Implementation

### Experiment Manager Class

```python
from dataclasses import dataclass
from typing import Literal
from decimal import Decimal
from scipy import stats
import numpy as np

@dataclass
class ExperimentResult:
    control_mean: Decimal
    treatment_mean: Decimal
    control_std: Decimal
    treatment_std: Decimal
    control_n: int
    treatment_n: int
    p_value: float
    effect_size: float
    is_significant: bool
    winner: Literal['control', 'treatment', 'no_difference']

class ABTestManager:
    """Manage A/B test lifecycle and statistical analysis."""

    def __init__(self, db_session):
        self.session = db_session

    def create_experiment(
        self,
        name: str,
        hypothesis: str,
        control_strategy_id: int,
        treatment_strategy_id: int,
        primary_metric: str,
        traffic_split: float = 0.5,
        min_sample_size: int = 64,
    ) -> int:
        """
        Create new A/B test experiment.

        Returns:
            experiment_id
        """
        experiment = ABTest(
            experiment_name=name,
            hypothesis=hypothesis,
            control_strategy_id=control_strategy_id,
            treatment_strategy_id=treatment_strategy_id,
            traffic_split=traffic_split,
            primary_metric=primary_metric,
            min_sample_size=min_sample_size,
            status='running',
        )
        self.session.add(experiment)
        self.session.commit()
        return experiment.experiment_id

    def record_trade_result(
        self,
        experiment_id: int,
        variant: Literal['control', 'treatment'],
        trade_id: int,
        position_id: int,
        market_id: int,
        strategy_id: int,
        model_id: int,
        realized_pnl: Decimal,
        total_fees: Decimal,
    ) -> None:
        """Record trade outcome for experiment."""
        result = ABTestResult(
            experiment_id=experiment_id,
            variant=variant,
            trade_id=trade_id,
            position_id=position_id,
            market_id=market_id,
            strategy_id=strategy_id,
            model_id=model_id,
            realized_pnl=realized_pnl,
            total_fees=total_fees,
            win=(realized_pnl - total_fees) > 0,
        )
        self.session.add(result)
        self.session.commit()

    def analyze_experiment(self, experiment_id: int) -> ExperimentResult:
        """
        Analyze experiment results with statistical significance testing.

        Returns:
            ExperimentResult with p-value, effect size, winner

        Educational Note:
            - Uses Welch's t-test (unequal variances assumed)
            - Effect size: Cohen's d = (mean_treatment - mean_control) / pooled_std
            - p-value < 0.05 → statistically significant
        """
        # Fetch control variant results
        control_results = self.session.query(ABTestResult).filter_by(
            experiment_id=experiment_id,
            variant='control'
        ).all()

        # Fetch treatment variant results
        treatment_results = self.session.query(ABTestResult).filter_by(
            experiment_id=experiment_id,
            variant='treatment'
        ).all()

        # Extract net P&L values
        control_pnls = [float(r.net_pnl) for r in control_results]
        treatment_pnls = [float(r.net_pnl) for r in treatment_results]

        # Calculate statistics
        control_mean = np.mean(control_pnls)
        treatment_mean = np.mean(treatment_pnls)
        control_std = np.std(control_pnls, ddof=1)
        treatment_std = np.std(treatment_pnls, ddof=1)

        # Welch's t-test (unequal variances)
        t_stat, p_value = stats.ttest_ind(
            treatment_pnls,
            control_pnls,
            equal_var=False  # Welch's t-test
        )

        # Effect size (Cohen's d)
        pooled_std = np.sqrt((control_std**2 + treatment_std**2) / 2)
        effect_size = (treatment_mean - control_mean) / pooled_std if pooled_std > 0 else 0

        # Determine winner
        is_significant = p_value < 0.05
        if is_significant:
            winner = 'treatment' if treatment_mean > control_mean else 'control'
        else:
            winner = 'no_difference'

        return ExperimentResult(
            control_mean=Decimal(str(control_mean)),
            treatment_mean=Decimal(str(treatment_mean)),
            control_std=Decimal(str(control_std)),
            treatment_std=Decimal(str(treatment_std)),
            control_n=len(control_pnls),
            treatment_n=len(treatment_pnls),
            p_value=p_value,
            effect_size=effect_size,
            is_significant=is_significant,
            winner=winner,
        )
```

---

## 6. Statistical Analysis

### T-Test (Continuous Metrics)

**Use for:** Net P&L, Average Edge, Sharpe Ratio

```python
from scipy import stats

def welch_ttest(control_values, treatment_values, alpha=0.05):
    """
    Welch's t-test for comparing two independent samples.

    Educational Note:
        - Welch's t-test does NOT assume equal variances
        - More robust than Student's t-test for real-world data
        - Returns: t-statistic, p-value
    """
    t_stat, p_value = stats.ttest_ind(treatment_values, control_values, equal_var=False)
    is_significant = p_value < alpha
    return t_stat, p_value, is_significant

# Example
control = [2.5, 3.0, 1.8, 2.2, 2.9]  # Control net P&L
treatment = [3.2, 3.5, 2.8, 3.1, 3.4]  # Treatment net P&L

t, p, sig = welch_ttest(control, treatment)
print(f"p-value: {p:.4f}, Significant: {sig}")
# Output: p-value: 0.0312, Significant: True
```

### Chi-Square Test (Categorical Metrics)

**Use for:** Win Rate (win vs. loss)

```python
from scipy.stats import chi2_contingency

def chi_square_test(control_wins, control_losses, treatment_wins, treatment_losses, alpha=0.05):
    """
    Chi-square test for comparing win/loss distributions.

    Educational Note:
        - Tests if win rates are significantly different
        - Requires: All cells ≥ 5 (otherwise use Fisher's exact test)
    """
    # Contingency table
    observed = [
        [control_wins, control_losses],
        [treatment_wins, treatment_losses]
    ]

    chi2, p_value, dof, expected = chi2_contingency(observed)
    is_significant = p_value < alpha
    return chi2, p_value, is_significant

# Example
chi2, p, sig = chi_square_test(
    control_wins=30, control_losses=20,
    treatment_wins=40, treatment_losses=10
)
print(f"p-value: {p:.4f}, Significant: {sig}")
# Output: p-value: 0.0156, Significant: True
```

---

## 7. Dashboard Integration

### Experiment Overview Card

```typescript
// src/components/experiments/ExperimentCard.tsx
interface ExperimentCardProps {
  experiment: {
    experiment_id: number;
    experiment_name: string;
    status: string;
    control_mean: number;
    treatment_mean: number;
    p_value: number;
    effect_size: number;
    control_n: number;
    treatment_n: number;
    min_sample_size: number;
  };
}

export function ExperimentCard({ experiment }: ExperimentCardProps) {
  const lift = ((experiment.treatment_mean - experiment.control_mean) / experiment.control_mean) * 100;
  const progress = Math.min((experiment.control_n / experiment.min_sample_size) * 100, 100);
  const isSignificant = experiment.p_value < 0.05;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-2">{experiment.experiment_name}</h3>
      <span className={`text-sm px-2 py-1 rounded ${
        experiment.status === 'running' ? 'bg-blue-100 text-blue-800' :
        experiment.status === 'completed' ? 'bg-green-100 text-green-800' :
        'bg-gray-100 text-gray-800'
      }`}>
        {experiment.status.toUpperCase()}
      </span>

      <div className="mt-4 space-y-2">
        <div className="flex justify-between">
          <span className="text-gray-600">Control Mean:</span>
          <span className="font-medium">${experiment.control_mean.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Treatment Mean:</span>
          <span className="font-medium">${experiment.treatment_mean.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Lift:</span>
          <span className={`font-medium ${lift > 0 ? 'text-green-600' : 'text-red-600'}`}>
            {lift > 0 ? '+' : ''}{lift.toFixed(2)}%
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">p-value:</span>
          <span className={`font-medium ${isSignificant ? 'text-green-600' : 'text-gray-600'}`}>
            {experiment.p_value.toFixed(4)} {isSignificant && '✓'}
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-4">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Sample Size: {experiment.control_n + experiment.treatment_n}</span>
          <span>{progress.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
```

---

## 8. Best Practices

### DO:
- ✅ **Define hypothesis BEFORE launching** (prevents p-hacking)
- ✅ **Calculate required sample size** (avoid underpowered tests)
- ✅ **Use randomization** (eliminates selection bias)
- ✅ **Monitor safety metrics** (max drawdown, total trades)
- ✅ **Wait for minimum sample size** (avoid premature conclusions)
- ✅ **Test one change at a time** (isolate causal effect)

### DON'T:
- ❌ **Don't stop early just because p < 0.05** (regression to the mean)
- ❌ **Don't test multiple metrics simultaneously** (multiple testing problem)
- ❌ **Don't peek at results daily** (increases false positive rate)
- ❌ **Don't reuse same control group** (contamination risk)

---

## 9. Common Pitfalls

### Pitfall 1: Insufficient Sample Size
**Problem:** 20 trades per variant → 90% power requires 64 trades
**Solution:** Calculate sample size upfront, wait for minimum N

### Pitfall 2: Multiple Testing Problem
**Problem:** Testing 10 metrics → 40% chance of false positive (p < 0.05)
**Solution:** Use Bonferroni correction (α/n) or focus on single primary metric

### Pitfall 3: Novelty Effect
**Problem:** Treatment appears better initially, regresses after 2 weeks
**Solution:** Run experiments for ≥30 days to account for market cycles

---

## 10. Example Experiments

### Experiment 1: Kelly Fraction Optimization

**Hypothesis:** Increasing Kelly fraction from 0.25 to 0.30 increases net P&L by ≥10%
**Control:** Strategy v1.0 (kelly_fraction=0.25)
**Treatment:** Strategy v1.1 (kelly_fraction=0.30)
**Results:** p=0.032, effect size=0.52, treatment won (+12.5% net P&L)
**Decision:** Deploy strategy v1.1

---

**END OF AB_TESTING_GUIDE_V1.0.md**
