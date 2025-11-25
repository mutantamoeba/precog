# Strategy Evaluation Specification

---
**Version:** 1.0
**Created:** 2025-11-25
**Status:** 🔵 Planned (Phase 5a)
**Target Audience:** Backend developers implementing automated strategy evaluation
**Prerequisite Reading:**
- `STRATEGY_MANAGER_USER_GUIDE_V1.1.md` - Strategy lifecycle and status management
- `EVENT_LOOP_ARCHITECTURE_V1.0.md` - Daily evaluation scheduling
- `AB_TESTING_FRAMEWORK_SPEC_V1.0.md` - Statistical significance testing

**Related Requirements:**
- REQ-STRAT-004: Automated Strategy Activation
- REQ-STRAT-005: Performance-Based Deprecation
- REQ-STRAT-006: Strategy Health Monitoring

**Related ADRs:**
- ADR-120: Performance-Based Activation Criteria
- ADR-121: Automated Deprecation Thresholds

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Activation Criteria](#activation-criteria)
4. [Deprecation Criteria](#deprecation-criteria)
5. [Evaluation Schedule](#evaluation-schedule)
6. [Implementation Examples](#implementation-examples)
7. [Integration with Event Loop](#integration-with-event-loop)
8. [Testing Strategy](#testing-strategy)
9. [Cross-References](#cross-references)

---

## Overview

### Purpose

The **StrategyEvaluator** automates the promotion of strategies from `testing` → `active` status when performance criteria are met, and demotes strategies from `active` → `deprecated` when performance degrades.

**Key Benefits:**
- **Removes human bias** from activation decisions (objective thresholds)
- **Ensures quality control** (only profitable strategies reach production)
- **Automates deprecation** (automatically retire underperforming strategies)
- **Provides audit trail** (all decisions logged with rationale)

### Problem Statement

**Without Automation:**
- Manual review of 10+ testing strategies every day (time-consuming)
- Subjective activation decisions ("looks good enough")
- Slow deprecation of failing strategies (lost capital)
- No systematic performance tracking

**With StrategyEvaluator:**
- Automated daily evaluation (2 AM scheduled run)
- Objective criteria (6 activation thresholds, 5 deprecation thresholds)
- Instant notifications when strategies activated/deprecated
- Performance dashboard showing all strategy health metrics

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  EVENT LOOP (Daily 2 AM)                        │
│                                                                 │
│  ┌────────────────┐      ┌──────────────────┐                 │
│  │  Daily Timer   │──────▶│ StrategyEvaluator│                 │
│  │  (2:00 AM)     │      │  (This Spec)     │                 │
│  └────────────────┘      └──────────────────┘                 │
│                                 │                               │
│                                 ▼                               │
│                    ┌────────────────────────┐                  │
│                    │  StrategyManager       │                  │
│                    │  update_status()       │                  │
│                    └────────────────────────┘                  │
│                                 │                               │
│                                 ▼                               │
│                    ┌────────────────────────┐                  │
│                    │  Notification System   │                  │
│                    │  (Email/Slack)         │                  │
│                    └────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

### StrategyEvaluator Class

**Location:** `src/precog/trading/strategy_evaluator.py` (~350 lines)

**Key Methods:**
```python
class StrategyEvaluator:
    """
    Automated strategy performance evaluation and status management.

    Educational Note:
        This class implements evidence-based activation/deprecation:
        - Activation requires ALL 6 criteria met (conservative)
        - Deprecation requires ANY 2 criteria failed (aggressive)

        Why asymmetric thresholds?
        - Activation: High bar prevents bad strategies going live
        - Deprecation: Low bar quickly removes failing strategies

        This protects capital while allowing experimentation.
    """

    def __init__(
        self,
        strategy_manager: StrategyManager,
        logger: Logger,
        notification_service: NotificationService
    ):
        self.strategy_manager = strategy_manager
        self.logger = logger
        self.notifications = notification_service

        # Activation thresholds (ALL must pass)
        self.ACTIVATION_CRITERIA = {
            'min_trades': 100,
            'min_roi': Decimal('0.10'),  # 10%
            'min_win_rate': Decimal('0.55'),  # 55%
            'min_sharpe': Decimal('1.5'),
            'max_drawdown': Decimal('0.15'),  # 15%
            'max_consecutive_losses': 5
        }

        # Deprecation thresholds (ANY 2 failing triggers deprecation)
        self.DEPRECATION_CRITERIA = {
            'min_roi': Decimal('0.05'),  # 5%
            'min_win_rate': Decimal('0.52'),  # 52%
            'min_sharpe': Decimal('1.0'),
            'max_drawdown': Decimal('0.20'),  # 20%
            'max_consecutive_losses': 8
        }
```

---

## Activation Criteria

### The 6 Activation Thresholds

Strategies must meet **ALL 6 criteria** to be promoted from `testing` → `active`:

| # | Criterion | Threshold | Rationale |
|---|-----------|-----------|-----------|
| 1 | **Minimum Trades** | ≥100 trades | Statistical significance (adequate sample size) |
| 2 | **ROI** | ≥10% (30-day) | Profitability requirement (after fees ~2-3%) |
| 3 | **Win Rate** | ≥55% | Consistency requirement (above break-even + fees) |
| 4 | **Sharpe Ratio** | ≥1.5 | Risk-adjusted returns (reward/risk ratio) |
| 5 | **Max Drawdown** | ≤15% | Risk management (acceptable loss tolerance) |
| 6 | **Consecutive Losses** | ≤5 | Strategy not "broken" or overfitted |

### Activation Logic

```python
def evaluate_for_activation(
    self,
    strategy_id: int
) -> dict[str, Any]:
    """
    Evaluate testing strategy for activation to production.

    Args:
        strategy_id: Strategy to evaluate

    Returns:
        Dictionary with activation decision:
        {
            'action': 'activate' or 'continue_testing',
            'reason': 'Explanation of decision',
            'criteria_summary': {criterion: 'pass/fail status'}
        }

    Educational Note:
        All 6 criteria must pass for activation. This conservative
        approach prevents low-quality strategies from reaching production.

        Example: Strategy with 95 trades (4.9% short of 100):
        - All other criteria met (ROI 15%, win rate 60%, etc.)
        - Decision: continue_testing (insufficient sample size)
        - Rationale: Statistical significance requires ≥100 trades
    """
    strategy = self.strategy_manager.get_strategy(strategy_id)

    # Only evaluate strategies in 'testing' status
    if strategy['status'] != 'testing':
        return {
            'action': 'skip',
            'reason': f"Strategy status is '{strategy['status']}', not 'testing'"
        }

    # Fetch performance metrics (last 30 days)
    metrics = self._fetch_metrics(strategy_id, days=30)

    # Evaluate each criterion
    criteria_results = {}

    # Criterion 1: Minimum trades
    trades_count = metrics['trade_count']
    criteria_results['trades'] = {
        'pass': trades_count >= self.ACTIVATION_CRITERIA['min_trades'],
        'value': trades_count,
        'threshold': self.ACTIVATION_CRITERIA['min_trades'],
        'display': f"{'✅' if criteria_results['trades']['pass'] else '❌'} {trades_count} ≥ 100"
    }

    # Criterion 2: ROI
    roi = metrics['roi']
    criteria_results['roi'] = {
        'pass': roi >= self.ACTIVATION_CRITERIA['min_roi'],
        'value': roi,
        'threshold': self.ACTIVATION_CRITERIA['min_roi'],
        'display': f"{'✅' if criteria_results['roi']['pass'] else '❌'} {float(roi) * 100:.1f}% ≥ 10%"
    }

    # Criterion 3: Win rate
    win_rate = metrics['win_rate']
    criteria_results['win_rate'] = {
        'pass': win_rate >= self.ACTIVATION_CRITERIA['min_win_rate'],
        'value': win_rate,
        'threshold': self.ACTIVATION_CRITERIA['min_win_rate'],
        'display': f"{'✅' if criteria_results['win_rate']['pass'] else '❌'} {float(win_rate) * 100:.1f}% ≥ 55%"
    }

    # Criterion 4: Sharpe ratio
    sharpe = metrics['sharpe_ratio']
    criteria_results['sharpe'] = {
        'pass': sharpe >= self.ACTIVATION_CRITERIA['min_sharpe'],
        'value': sharpe,
        'threshold': self.ACTIVATION_CRITERIA['min_sharpe'],
        'display': f"{'✅' if criteria_results['sharpe']['pass'] else '❌'} {float(sharpe):.2f} ≥ 1.5"
    }

    # Criterion 5: Max drawdown
    drawdown = metrics['max_drawdown']
    criteria_results['drawdown'] = {
        'pass': drawdown <= self.ACTIVATION_CRITERIA['max_drawdown'],
        'value': drawdown,
        'threshold': self.ACTIVATION_CRITERIA['max_drawdown'],
        'display': f"{'✅' if criteria_results['drawdown']['pass'] else '❌'} {float(drawdown) * 100:.1f}% ≤ 15%"
    }

    # Criterion 6: Consecutive losses
    consecutive_losses = metrics['max_consecutive_losses']
    criteria_results['consecutive_losses'] = {
        'pass': consecutive_losses <= self.ACTIVATION_CRITERIA['max_consecutive_losses'],
        'value': consecutive_losses,
        'threshold': self.ACTIVATION_CRITERIA['max_consecutive_losses'],
        'display': f"{'✅' if criteria_results['consecutive_losses']['pass'] else '❌'} {consecutive_losses} ≤ 5"
    }

    # Decision: ALL criteria must pass for activation
    all_passed = all(c['pass'] for c in criteria_results.values())

    if all_passed:
        # Activate strategy
        self.strategy_manager.update_status(strategy_id, 'active')

        # Send notification
        self.notifications.send(
            channel='strategy-activation',
            message=f"🎉 Strategy {strategy['strategy_name']} v{strategy['strategy_version']} ACTIVATED\n"
                    f"ROI: {float(roi) * 100:.1f}%, Win Rate: {float(win_rate) * 100:.1f}%, Sharpe: {float(sharpe):.2f}"
        )

        return {
            'action': 'activate',
            'reason': 'All activation criteria met',
            'criteria_summary': {k: v['display'] for k, v in criteria_results.items()}
        }
    else:
        # Continue testing
        failed_criteria = [k for k, v in criteria_results.items() if not v['pass']]

        return {
            'action': 'continue_testing',
            'reason': f"Failed {len(failed_criteria)} criteria: {', '.join(failed_criteria)}",
            'criteria_summary': {k: v['display'] for k, v in criteria_results.items()}
        }
```

---

## Deprecation Criteria

### The 5 Deprecation Thresholds

Strategies are deprecated from `active` → `deprecated` if **ANY 2 criteria** fail:

| # | Criterion | Threshold | Rationale |
|---|-----------|-----------|-----------|
| 1 | **ROI Degradation** | 30-day ROI < 5% | No longer profitable enough |
| 2 | **Win Rate Drop** | Win rate < 52% | Below consistency threshold (break-even ~50% + fees) |
| 3 | **Sharpe Deterioration** | Sharpe ratio < 1.0 | Risk-adjusted returns too low |
| 4 | **Drawdown Spike** | Max drawdown > 20% | Risk tolerance exceeded |
| 5 | **Consecutive Losses** | ≥8 losses in a row | Strategy likely broken |

### Deprecation Logic

```python
def evaluate_for_deprecation(
    self,
    strategy_id: int
) -> dict[str, Any]:
    """
    Evaluate active strategy for deprecation.

    Returns:
        Dictionary with deprecation decision

    Educational Note:
        ANY 2 criteria failing triggers deprecation. This aggressive
        approach quickly removes failing strategies from production.

        Example: Strategy with ROI 4.2% and win rate 51.3%:
        - Both below thresholds (5% and 52%)
        - Decision: deprecate
        - Rationale: 2 failures indicate systematic underperformance
    """
    strategy = self.strategy_manager.get_strategy(strategy_id)

    # Only evaluate strategies in 'active' status
    if strategy['status'] != 'active':
        return {
            'action': 'skip',
            'reason': f"Strategy status is '{strategy['status']}', not 'active'"
        }

    # Fetch performance metrics (last 30 days)
    metrics = self._fetch_metrics(strategy_id, days=30)

    # Evaluate each criterion (failures tracked)
    criteria_results = {}

    # Criterion 1: ROI
    roi = metrics['roi']
    criteria_results['roi'] = {
        'failed': roi < self.DEPRECATION_CRITERIA['min_roi'],
        'value': roi,
        'threshold': self.DEPRECATION_CRITERIA['min_roi'],
        'display': f"{'❌' if criteria_results['roi']['failed'] else '✅'} {float(roi) * 100:.1f}% >= 5%"
    }

    # Criterion 2: Win rate
    win_rate = metrics['win_rate']
    criteria_results['win_rate'] = {
        'failed': win_rate < self.DEPRECATION_CRITERIA['min_win_rate'],
        'value': win_rate,
        'threshold': self.DEPRECATION_CRITERIA['min_win_rate'],
        'display': f"{'❌' if criteria_results['win_rate']['failed'] else '✅'} {float(win_rate) * 100:.1f}% >= 52%"
    }

    # Criterion 3: Sharpe ratio
    sharpe = metrics['sharpe_ratio']
    criteria_results['sharpe'] = {
        'failed': sharpe < self.DEPRECATION_CRITERIA['min_sharpe'],
        'value': sharpe,
        'threshold': self.DEPRECATION_CRITERIA['min_sharpe'],
        'display': f"{'❌' if criteria_results['sharpe']['failed'] else '✅'} {float(sharpe):.2f} >= 1.0"
    }

    # Criterion 4: Drawdown
    drawdown = metrics['max_drawdown']
    criteria_results['drawdown'] = {
        'failed': drawdown > self.DEPRECATION_CRITERIA['max_drawdown'],
        'value': drawdown,
        'threshold': self.DEPRECATION_CRITERIA['max_drawdown'],
        'display': f"{'❌' if criteria_results['drawdown']['failed'] else '✅'} {float(drawdown) * 100:.1f}% <= 20%"
    }

    # Criterion 5: Consecutive losses
    consecutive_losses = metrics['max_consecutive_losses']
    criteria_results['consecutive_losses'] = {
        'failed': consecutive_losses >= self.DEPRECATION_CRITERIA['max_consecutive_losses'],
        'value': consecutive_losses,
        'threshold': self.DEPRECATION_CRITERIA['max_consecutive_losses'],
        'display': f"{'❌' if criteria_results['consecutive_losses']['failed'] else '✅'} {consecutive_losses} < 8"
    }

    # Decision: ANY 2 failures trigger deprecation
    failed_count = sum(1 for c in criteria_results.values() if c['failed'])

    if failed_count >= 2:
        # Deprecate strategy
        self.strategy_manager.update_status(strategy_id, 'deprecated')

        failed_criteria = [k for k, v in criteria_results.items() if v['failed']]

        # Send notification
        self.notifications.send(
            channel='strategy-deprecation',
            message=f"⚠️ Strategy {strategy['strategy_name']} v{strategy['strategy_version']} DEPRECATED\n"
                    f"Failed criteria: {', '.join(failed_criteria)}\n"
                    f"ROI: {float(roi) * 100:.1f}%, Win Rate: {float(win_rate) * 100:.1f}%, Sharpe: {float(sharpe):.2f}"
        )

        return {
            'action': 'deprecate',
            'reason': f"Failed {failed_count} deprecation criteria: {', '.join(failed_criteria)}",
            'criteria_summary': {k: v['display'] for k, v in criteria_results.items()}
        }
    else:
        # Continue active
        return {
            'action': 'continue_active',
            'reason': f"Only {failed_count} criteria failed (need 2+ for deprecation)",
            'criteria_summary': {k: v['display'] for k, v in criteria_results.items()}
        }
```

---

## Evaluation Schedule

### Daily Automated Evaluation (2 AM)

**Scheduling:** Event loop triggers `StrategyEvaluator.run_daily_evaluation()` at 2:00 AM daily.

**Workflow:**
```python
async def run_daily_evaluation(self) -> dict[str, Any]:
    """
    Run daily automated strategy evaluation.

    Called by event loop at 2:00 AM daily.

    Returns:
        Summary of evaluation results
    """
    self.logger.info("Starting daily strategy evaluation (2 AM)")

    # Step 1: Evaluate testing strategies for activation
    testing_strategies = self.strategy_manager.list_strategies(status='testing')

    activation_results = {}
    for strategy in testing_strategies:
        result = self.evaluate_for_activation(strategy['strategy_id'])
        activation_results[strategy['strategy_id']] = result

        if result['action'] == 'activate':
            self.logger.info(
                f"✅ ACTIVATED: {strategy['strategy_name']} v{strategy['strategy_version']}"
            )

    # Step 2: Evaluate active strategies for deprecation
    active_strategies = self.strategy_manager.list_strategies(status='active')

    deprecation_results = {}
    for strategy in active_strategies:
        result = self.evaluate_for_deprecation(strategy['strategy_id'])
        deprecation_results[strategy['strategy_id']] = result

        if result['action'] == 'deprecate':
            self.logger.warning(
                f"⚠️ DEPRECATED: {strategy['strategy_name']} v{strategy['strategy_version']}"
            )

    # Step 3: Generate summary report
    summary = {
        'timestamp': datetime.now().isoformat(),
        'testing_evaluated': len(testing_strategies),
        'activated': sum(1 for r in activation_results.values() if r['action'] == 'activate'),
        'active_evaluated': len(active_strategies),
        'deprecated': sum(1 for r in deprecation_results.values() if r['action'] == 'deprecate'),
        'activation_details': activation_results,
        'deprecation_details': deprecation_results
    }

    self.logger.info(
        f"Daily evaluation complete: {summary['activated']} activated, {summary['deprecated']} deprecated"
    )

    return summary
```

---

## Implementation Examples

### Example 1: Activation Decision

```python
# Scenario: halftime_entry v1.2 tested for 35 days
strategy_id = 42

result = evaluator.evaluate_for_activation(strategy_id)

# Result:
{
    'action': 'activate',
    'reason': 'All activation criteria met',
    'criteria_summary': {
        'trades': '✅ 127 ≥ 100',
        'roi': '✅ 14.2% ≥ 10%',
        'win_rate': '✅ 58.3% ≥ 55%',
        'sharpe': '✅ 1.82 ≥ 1.5',
        'drawdown': '✅ 11.2% ≤ 15%',
        'consecutive_losses': '✅ 3 ≤ 5'
    }
}

# Action taken: Strategy promoted to 'active' status
# Notification sent: Slack #strategy-activation channel
```

### Example 2: Deprecation Decision

```python
# Scenario: market_momentum v2.1 deteriorating performance
strategy_id = 55

result = evaluator.evaluate_for_deprecation(strategy_id)

# Result:
{
    'action': 'deprecate',
    'reason': 'Failed 3 deprecation criteria: roi, win_rate, sharpe',
    'criteria_summary': {
        'roi': '❌ 3.2% >= 5%',
        'win_rate': '❌ 51.5% >= 52%',
        'sharpe': '❌ 0.85 >= 1.0',
        'drawdown': '✅ 14.2% <= 20%',
        'consecutive_losses': '✅ 4 < 8'
    }
}

# Action taken: Strategy demoted to 'deprecated' status
# Notification sent: Slack #strategy-deprecation channel
```

---

## Integration with Event Loop

**Event Loop Configuration:**
```python
# In src/precog/event_loop.py
from precog.trading.strategy_evaluator import StrategyEvaluator

async def run_event_loop():
    """Main trading event loop."""
    evaluator = StrategyEvaluator(
        strategy_manager=StrategyManager(db_pool),
        logger=get_logger('strategy_evaluator'),
        notification_service=SlackNotificationService()
    )

    # Schedule daily evaluation at 2:00 AM
    while True:
        current_time = datetime.now()

        if current_time.hour == 2 and current_time.minute == 0:
            # Run daily strategy evaluation
            await evaluator.run_daily_evaluation()

        # Sleep until next minute
        await asyncio.sleep(60)
```

---

## Testing Strategy

### Unit Tests

```python
def test_activation_all_criteria_met():
    """Test that strategy activates when all 6 criteria met."""
    evaluator = StrategyEvaluator(...)

    # Mock strategy with excellent metrics
    strategy_id = 1
    mock_metrics = {
        'trade_count': 150,
        'roi': Decimal('0.15'),  # 15%
        'win_rate': Decimal('0.60'),  # 60%
        'sharpe_ratio': Decimal('2.0'),
        'max_drawdown': Decimal('0.10'),  # 10%
        'max_consecutive_losses': 3
    }

    result = evaluator.evaluate_for_activation(strategy_id)

    assert result['action'] == 'activate'
    assert all('✅' in v for v in result['criteria_summary'].values())
```

### Integration Tests

```python
@pytest.mark.integration
async def test_daily_evaluation_workflow(db_pool):
    """Test complete daily evaluation workflow."""
    evaluator = StrategyEvaluator(...)

    # Create 2 testing strategies (1 ready, 1 not ready)
    # Create 2 active strategies (1 performing, 1 failing)

    summary = await evaluator.run_daily_evaluation()

    assert summary['activated'] == 1  # 1 testing → active
    assert summary['deprecated'] == 1  # 1 active → deprecated
```

---

## Cross-References

**Prerequisites:**
- `STRATEGY_MANAGER_USER_GUIDE_V1.1.md` - Strategy lifecycle and metrics
- `EVENT_LOOP_ARCHITECTURE_V1.0.md` - Daily evaluation scheduling

**Related Specifications:**
- `AB_TESTING_FRAMEWORK_SPEC_V1.0.md` - Statistical A/B testing framework

**Requirements:**
- REQ-STRAT-004: Automated Strategy Activation
- REQ-STRAT-005: Performance-Based Deprecation
- REQ-STRAT-006: Strategy Health Monitoring

**Architecture Decisions:**
- ADR-120: Performance-Based Activation Criteria (6 thresholds)
- ADR-121: Automated Deprecation Thresholds (2-failure rule)

---

**END OF STRATEGY_EVALUATION_SPEC_V1.0.md**
