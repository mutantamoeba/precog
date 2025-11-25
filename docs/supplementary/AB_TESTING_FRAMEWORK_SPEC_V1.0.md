# A/B Testing Framework Specification

---
**Version:** 1.0
**Created:** 2025-11-25
**Status:** 🔵 Planned (Phase 5a)
**Target Audience:** Backend developers implementing systematic A/B testing
**Prerequisite Reading:**
- `STRATEGY_MANAGER_USER_GUIDE_V1.1.md` - Strategy lifecycle and A/B test workflows
- `STRATEGY_EVALUATION_SPEC_V1.0.md` - Automated activation/deprecation
- `AB_TESTING_GUIDE_V1.0.md` - Statistical methodology reference

**Related Requirements:**
- REQ-TEST-015: A/B Testing Framework
- REQ-TEST-016: Statistical Significance Testing
- REQ-TEST-017: Automated Winner Declaration

**Related ADRs:**
- ADR-122: 50/50 Traffic Allocation Strategy
- ADR-123: Statistical Significance Thresholds (p < 0.05, power ≥ 0.80)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [A/B Test Lifecycle](#ab-test-lifecycle)
4. [50/50 Traffic Allocation](#5050-traffic-allocation)
5. [Statistical Significance Testing](#statistical-significance-testing)
6. [Sample Size Calculation](#sample-size-calculation)
7. [Winner Declaration Logic](#winner-declaration-logic)
8. [Implementation Examples](#implementation-examples)
9. [Testing Strategy](#testing-strategy)
10. [Cross-References](#cross-references)

---

## Overview

### Purpose

The **ABTestingManager** provides systematic statistical comparison of strategy versions to determine which performs better.

**Key Benefits:**
- **Objective decision-making:** Statistical tests remove human bias
- **Risk mitigation:** 50/50 allocation limits exposure to untested variants
- **Early stopping:** Detect winners quickly with sequential testing
- **Audit trail:** All experiments logged with statistical evidence

### Problem Statement

**Without A/B Testing Framework:**
- Developer creates v1.2, manually compares to v1.1 after "enough" trades
- Subjective judgment ("v1.2 looks better")
- No statistical rigor (p-values, confidence intervals)
- Risk of promoting inferior strategy due to random variance

**With ABTestingManager:**
- Automated 50/50 allocation between v1.1 and v1.2
- Statistical significance tests (chi-square for win rate, t-test for ROI)
- Minimum sample size enforcement (200 trades minimum)
- Automated winner declaration when p < 0.05 and power ≥ 0.80

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  TRADE ENTRY POINT                              │
│                                                                 │
│  ┌────────────────┐      ┌──────────────────┐                 │
│  │  New Market    │──────▶│ ABTestingManager │                 │
│  │  Opportunity   │      │  (This Spec)     │                 │
│  └────────────────┘      └──────────────────┘                 │
│                                 │                               │
│                                 ▼                               │
│                    ┌────────────────────────┐                  │
│                    │  Random Allocation     │                  │
│                    │  (50% A, 50% B)        │                  │
│                    └────────────────────────┘                  │
│                      │                    │                     │
│                      ▼                    ▼                     │
│          ┌──────────────────┐  ┌──────────────────┐           │
│          │ Strategy A       │  │ Strategy B       │           │
│          │ (Control)        │  │ (Variant)        │           │
│          └──────────────────┘  └──────────────────┘           │
│                      │                    │                     │
│                      └────────┬───────────┘                     │
│                               ▼                                 │
│                    ┌────────────────────────┐                  │
│                    │  Trades Table          │                  │
│                    │  (ab_test_id col)      │                  │
│                    └────────────────────────┘                  │
│                               │                                 │
│                               ▼                                 │
│                    ┌────────────────────────┐                  │
│                    │  Statistical Evaluator │                  │
│                    │  (Chi-square, t-test)  │                  │
│                    └────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

### ABTestingManager Class

**Location:** `src/precog/trading/ab_testing_manager.py` (~400 lines)

**Key Methods:**
```python
class ABTestingManager:
    """
    Systematic A/B testing framework for strategy comparison.

    Educational Note:
        A/B testing answers: "Is strategy B *significantly* better than A?"

        Key principles:
        1. Randomization: 50/50 allocation eliminates selection bias
        2. Sample size: Need ≥100 trades per variant for validity
        3. Statistical tests: p < 0.05 means <5% chance result is random
        4. Power analysis: Power ≥ 0.80 means 80% chance of detecting real difference

        Common mistake: "v1.2 won 60% vs 55% after 20 trades → v1.2 wins!"
        Reality: With only 20 trades, this difference is NOT statistically significant.
        Could easily be random variance. Need ≥100 trades per variant.
    """

    def __init__(
        self,
        strategy_manager: StrategyManager,
        logger: Logger
    ):
        self.strategy_manager = strategy_manager
        self.logger = logger

        # Statistical thresholds
        self.SIGNIFICANCE_LEVEL = 0.05  # p < 0.05 (5% false positive rate)
        self.MIN_POWER = 0.80  # 80% chance of detecting real difference
        self.MIN_SAMPLE_SIZE = 200  # 100 trades per variant minimum
```

---

## A/B Test Lifecycle

### Lifecycle States

```
┌─────────┐    create_test()    ┌─────────┐    collect ≥200    ┌──────────┐
│ PLANNED │ ──────────────────▶ │ RUNNING │ ─────────────────▶ │ COMPLETE │
└─────────┘                     └─────────┘                    └──────────┘
                                     │                               │
                                     │ stop_test()                   │
                                     ▼                               ▼
                                ┌─────────┐    evaluate_test()  ┌─────────┐
                                │ STOPPED │ ──────────────────▶ │ ANALYZED│
                                └─────────┘                     └─────────┘
```

### Lifecycle Implementation

```python
def create_test(
    self,
    strategy_a_id: int,
    strategy_b_id: int,
    allocation_pct: float = 0.50,
    min_sample_size: int = 200,
    significance_level: float = 0.05
) -> int:
    """
    Create new A/B test comparing two strategies.

    Args:
        strategy_a_id: Control strategy (baseline)
        strategy_b_id: Variant strategy (experiment)
        allocation_pct: Percent traffic to each (0.50 = 50/50)
        min_sample_size: Minimum total trades before evaluation
        significance_level: p-value threshold (default 0.05)

    Returns:
        ab_test_id for tracking

    Educational Note:
        Why 50/50 allocation?
        - Equal sample sizes maximize statistical power
        - Minimizes risk if variant underperforms
        - Industry standard (A/B testing best practice)

        Why 200 minimum trades?
        - Power analysis: Need ≥100 per group to detect medium effect (d=0.5)
        - Trade-off: Larger sample = higher power, but longer wait time
        - 200 total = ~2-4 weeks at 50-100 trades/week
    """
    # Validate strategies exist and have same domain
    strategy_a = self.strategy_manager.get_strategy(strategy_a_id)
    strategy_b = self.strategy_manager.get_strategy(strategy_b_id)

    if strategy_a['domain'] != strategy_b['domain']:
        raise ValueError(
            f"Strategies must have same domain: "
            f"{strategy_a['domain']} vs {strategy_b['domain']}"
        )

    # Create A/B test record
    ab_test = {
        'strategy_a_id': strategy_a_id,
        'strategy_b_id': strategy_b_id,
        'allocation_pct': Decimal(str(allocation_pct)),
        'min_sample_size': min_sample_size,
        'significance_level': Decimal(str(significance_level)),
        'status': 'running',
        'start_time': datetime.now(),
        'trades_collected_a': 0,
        'trades_collected_b': 0
    }

    ab_test_id = self._insert_ab_test(ab_test)

    self.logger.info(
        f"A/B test created: {strategy_a['strategy_name']} v{strategy_a['strategy_version']} "
        f"vs v{strategy_b['strategy_version']} (test_id={ab_test_id})"
    )

    return ab_test_id
```

---

## 50/50 Traffic Allocation

### Random Allocation Logic

```python
def allocate_strategy(
    self,
    ab_test_id: int,
    market_opportunity: dict
) -> int:
    """
    Randomly allocate market opportunity to strategy A or B.

    Args:
        ab_test_id: Active A/B test
        market_opportunity: Market with detected edge

    Returns:
        strategy_id (either A or B) to execute trade

    Educational Note:
        Randomization is CRITICAL for causal inference.

        Without randomization:
        - Assign morning games to A, evening games to B
        - Morning games may have systematically different characteristics
        - Can't isolate strategy effect from time-of-day effect

        With randomization:
        - Each opportunity has 50% chance → A, 50% → B
        - On average, both strategies see same opportunity mix
        - Can confidently attribute performance difference to strategy
    """
    ab_test = self._get_ab_test(ab_test_id)

    # Generate random number [0, 1)
    random_value = random.random()

    # Allocate based on threshold
    if random_value < float(ab_test['allocation_pct']):
        # Assign to strategy A (control)
        strategy_id = ab_test['strategy_a_id']
        self.logger.debug(f"Allocated to strategy A (random={random_value:.3f})")
    else:
        # Assign to strategy B (variant)
        strategy_id = ab_test['strategy_b_id']
        self.logger.debug(f"Allocated to strategy B (random={random_value:.3f})")

    return strategy_id
```

### Trade Tracking

```python
def record_trade_allocation(
    self,
    ab_test_id: int,
    trade_id: int,
    strategy_id: int
) -> None:
    """
    Record which strategy was assigned for this trade.

    Updates trades table with ab_test_id and allocated_strategy_id.
    """
    self._update_trade(
        trade_id=trade_id,
        ab_test_id=ab_test_id,
        allocated_strategy_id=strategy_id
    )

    # Increment allocation counter
    if strategy_id == self._get_ab_test(ab_test_id)['strategy_a_id']:
        self._increment_counter(ab_test_id, 'trades_collected_a')
    else:
        self._increment_counter(ab_test_id, 'trades_collected_b')
```

---

## Statistical Significance Testing

### Win Rate Comparison (Chi-Square Test)

```python
def test_win_rate_significance(
    self,
    ab_test_id: int
) -> dict[str, Any]:
    """
    Test if win rate difference is statistically significant.

    Uses chi-square test of independence (2x2 contingency table).

    Returns:
        {
            'statistic': chi-square value,
            'p_value': probability of observing difference by chance,
            'significant': True if p < 0.05,
            'effect_size': difference in win rates
        }

    Educational Note:
        Chi-square test answers: "Are wins/losses independent of strategy?"

        Contingency table:
                    Wins    Losses   Total
        Strategy A   60       40      100
        Strategy B   65       35      100

        If strategies perform equally, expect 50/50 win distribution.
        Chi-square measures how far observed data deviates from this expectation.

        p < 0.05 means: <5% chance this difference occurred by random luck.
    """
    # Fetch trade outcomes for both strategies
    trades_a = self._get_trades(ab_test_id, strategy='A')
    trades_b = self._get_trades(ab_test_id, strategy='B')

    # Build contingency table
    wins_a = sum(1 for t in trades_a if t['profit_loss'] > 0)
    losses_a = len(trades_a) - wins_a

    wins_b = sum(1 for t in trades_b if t['profit_loss'] > 0)
    losses_b = len(trades_b) - losses_b

    contingency_table = [
        [wins_a, losses_a],
        [wins_b, losses_b]
    ]

    # Run chi-square test
    from scipy.stats import chi2_contingency

    chi2, p_value, dof, expected = chi2_contingency(contingency_table)

    # Calculate effect size (difference in win rates)
    win_rate_a = wins_a / len(trades_a) if trades_a else 0
    win_rate_b = wins_b / len(trades_b) if trades_b else 0
    effect_size = win_rate_b - win_rate_a

    return {
        'statistic': chi2,
        'p_value': p_value,
        'significant': p_value < self.SIGNIFICANCE_LEVEL,
        'effect_size': effect_size,
        'win_rate_a': win_rate_a,
        'win_rate_b': win_rate_b
    }
```

### ROI Comparison (Welch's t-test)

```python
def test_roi_significance(
    self,
    ab_test_id: int
) -> dict[str, Any]:
    """
    Test if ROI difference is statistically significant.

    Uses Welch's t-test (does NOT assume equal variances).

    Returns:
        {
            'statistic': t-value,
            'p_value': probability of observing difference by chance,
            'significant': True if p < 0.05,
            'effect_size': Cohen's d (standardized difference)
        }

    Educational Note:
        Welch's t-test answers: "Do strategies have different mean ROI?"

        Example:
        - Strategy A: mean ROI = 8.3% per trade, std = 12.5%
        - Strategy B: mean ROI = 10.7% per trade, std = 14.2%
        - Difference = +2.4 percentage points

        But is this significant or just luck?
        t-test accounts for both difference size AND variance.

        p < 0.05 means: <5% chance this ROI difference is random.
    """
    # Fetch trade ROI values
    trades_a = self._get_trades(ab_test_id, strategy='A')
    trades_b = self._get_trades(ab_test_id, strategy='B')

    roi_values_a = [float(t['roi']) for t in trades_a]
    roi_values_b = [float(t['roi']) for t in trades_b]

    # Run Welch's t-test (unequal variances)
    from scipy.stats import ttest_ind

    t_stat, p_value = ttest_ind(
        roi_values_b,
        roi_values_a,
        equal_var=False  # Welch's t-test
    )

    # Calculate effect size (Cohen's d)
    mean_a = np.mean(roi_values_a)
    mean_b = np.mean(roi_values_b)
    std_a = np.std(roi_values_a, ddof=1)
    std_b = np.std(roi_values_b, ddof=1)

    # Pooled standard deviation
    pooled_std = np.sqrt((std_a**2 + std_b**2) / 2)
    cohens_d = (mean_b - mean_a) / pooled_std if pooled_std > 0 else 0

    return {
        'statistic': t_stat,
        'p_value': p_value,
        'significant': p_value < self.SIGNIFICANCE_LEVEL,
        'effect_size': cohens_d,
        'mean_roi_a': mean_a,
        'mean_roi_b': mean_b,
        'difference': mean_b - mean_a
    }
```

---

## Sample Size Calculation

### Power Analysis

```python
def calculate_required_sample_size(
    self,
    effect_size: float = 0.5,
    power: float = 0.80,
    significance: float = 0.05
) -> int:
    """
    Calculate minimum sample size for detecting effect.

    Args:
        effect_size: Cohen's d (0.5 = medium effect)
        power: Probability of detecting real effect (0.80 = 80%)
        significance: Alpha level (0.05 = 5% false positive)

    Returns:
        Minimum total sample size (both groups combined)

    Educational Note:
        Power analysis prevents underpowered experiments.

        Example: Want to detect 5 percentage point win rate improvement
        - Effect size d ≈ 0.5 (medium)
        - Power = 0.80 (industry standard)
        - Significance = 0.05 (p < 0.05)

        Result: Need ~100 trades per group = 200 total

        If you only collect 50 per group:
        - Power drops to ~0.50 (50% chance of detecting real difference)
        - High risk of false negative (missing a real winner)
    """
    from statsmodels.stats.power import tt_ind_solve_power

    # Calculate sample size per group
    n_per_group = tt_ind_solve_power(
        effect_size=effect_size,
        alpha=significance,
        power=power,
        ratio=1.0,  # Equal group sizes
        alternative='two-sided'
    )

    # Round up and multiply by 2 (both groups)
    total_sample_size = int(np.ceil(n_per_group)) * 2

    return total_sample_size
```

---

## Winner Declaration Logic

### Evaluate Test

```python
def evaluate_test(
    self,
    ab_test_id: int
) -> dict[str, Any]:
    """
    Evaluate A/B test and declare winner if statistically significant.

    Returns:
        {
            'winner': 'strategy_a' | 'strategy_b' | 'inconclusive',
            'confidence': percentage (e.g., 95.2%),
            'win_rate_result': {...},
            'roi_result': {...},
            'recommendation': 'Action to take'
        }

    Educational Note:
        Winner declaration requires:
        1. Sample size ≥ min_sample_size (statistical validity)
        2. p < 0.05 on BOTH win rate AND ROI (consistency check)
        3. Effect size in same direction (no contradictions)

        Why both tests?
        - Win rate improvement doesn't guarantee ROI improvement
        - Example: Win rate +5% but average win size smaller
        - Require both to ensure real business value
    """
    ab_test = self._get_ab_test(ab_test_id)

    # Check sample size
    total_trades = ab_test['trades_collected_a'] + ab_test['trades_collected_b']

    if total_trades < ab_test['min_sample_size']:
        return {
            'winner': 'inconclusive',
            'confidence': 0,
            'reason': f"Insufficient sample size: {total_trades}/{ab_test['min_sample_size']}"
        }

    # Run statistical tests
    win_rate_result = self.test_win_rate_significance(ab_test_id)
    roi_result = self.test_roi_significance(ab_test_id)

    # Decision logic: BOTH tests must be significant
    if win_rate_result['significant'] and roi_result['significant']:
        # Check consistency (both favor same strategy)
        win_rate_favors_b = win_rate_result['effect_size'] > 0
        roi_favors_b = roi_result['difference'] > 0

        if win_rate_favors_b == roi_favors_b:
            winner = 'strategy_b' if win_rate_favors_b else 'strategy_a'
            confidence = (1 - max(win_rate_result['p_value'], roi_result['p_value'])) * 100

            return {
                'winner': winner,
                'confidence': confidence,
                'win_rate_result': win_rate_result,
                'roi_result': roi_result,
                'recommendation': f"Promote {winner} to active, deprecate other"
            }
        else:
            # Contradictory results (win rate favors A, ROI favors B)
            return {
                'winner': 'inconclusive',
                'confidence': 0,
                'reason': 'Contradictory results: win rate and ROI favor different strategies',
                'win_rate_result': win_rate_result,
                'roi_result': roi_result
            }
    else:
        # Not statistically significant
        return {
            'winner': 'inconclusive',
            'confidence': 0,
            'reason': 'No statistically significant difference detected',
            'win_rate_result': win_rate_result,
            'roi_result': roi_result,
            'recommendation': 'Continue collecting data or accept strategies as equivalent'
        }
```

---

## Implementation Examples

### Example: Full A/B Test Workflow

```python
# Step 1: Create A/B test
ab_manager = ABTestingManager(strategy_manager, logger)

test_id = ab_manager.create_test(
    strategy_a_id=42,  # halftime_entry v1.1 (control)
    strategy_b_id=43,  # halftime_entry v1.2 (variant: min_edge=0.08 vs 0.05)
    min_sample_size=200
)

# Step 2: Allocate trades over time
for market_opportunity in new_opportunities:
    # Random allocation (50/50)
    strategy_id = ab_manager.allocate_strategy(test_id, market_opportunity)

    # Execute trade with allocated strategy
    trade_id = execute_trade(strategy_id, market_opportunity)

    # Record allocation
    ab_manager.record_trade_allocation(test_id, trade_id, strategy_id)

# Step 3: Monitor progress
status = ab_manager.get_test_status(test_id)
print(f"Trades: {status['trades_collected']}/200")
print(f"Current win rates: A={status['win_rate_a']:.1%}, B={status['win_rate_b']:.1%}")

# Step 4: Evaluate when ready
if status['trades_collected'] >= 200:
    result = ab_manager.evaluate_test(test_id)

    if result['winner'] != 'inconclusive':
        print(f"🎯 Winner: {result['winner']} ({result['confidence']:.1f}% confidence)")
        print(f"Win rate: +{result['win_rate_result']['effect_size']*100:.1f} pp (p={result['win_rate_result']['p_value']:.4f})")
        print(f"ROI: +{result['roi_result']['difference']*100:.1f}% (p={result['roi_result']['p_value']:.4f})")
        print(f"Recommendation: {result['recommendation']}")
```

---

## Testing Strategy

### Unit Tests

```python
def test_50_50_allocation_fairness():
    """Test that allocation is approximately 50/50 over large sample."""
    ab_manager = ABTestingManager(...)

    allocations = []
    for _ in range(1000):
        strategy_id = ab_manager.allocate_strategy(test_id, {})
        allocations.append(strategy_id)

    # Should be ~500 A, ~500 B (within statistical margin)
    count_a = sum(1 for s in allocations if s == 42)
    assert 450 <= count_a <= 550  # 45-55% acceptable (binomial variance)


def test_chi_square_calculation():
    """Test chi-square calculation with known outcome."""
    # Known data: 60/40 wins vs 50/50 wins (not significant)
    ab_manager = ABTestingManager(...)

    result = ab_manager.test_win_rate_significance(test_id)

    assert result['p_value'] > 0.05  # Not significant
    assert not result['significant']
```

---

## Cross-References

**Prerequisites:**
- `STRATEGY_MANAGER_USER_GUIDE_V1.1.md` - Strategy lifecycle and A/B workflows
- `AB_TESTING_GUIDE_V1.0.md` - Statistical methodology reference

**Related Specifications:**
- `STRATEGY_EVALUATION_SPEC_V1.0.md` - Automated activation/deprecation

**Requirements:**
- REQ-TEST-015: A/B Testing Framework
- REQ-TEST-016: Statistical Significance Testing
- REQ-TEST-017: Automated Winner Declaration

**Architecture Decisions:**
- ADR-122: 50/50 Traffic Allocation Strategy
- ADR-123: Statistical Significance Thresholds (p < 0.05, power ≥ 0.80)

---

**END OF AB_TESTING_FRAMEWORK_SPEC_V1.0.md**
