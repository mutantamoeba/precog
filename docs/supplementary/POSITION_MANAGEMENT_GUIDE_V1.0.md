# Precog Position Management Guide

---
**Version:** 1.0
**Created:** 2025-10-21
**Last Updated:** 2025-10-28 (Phase 0.6b - Filename standardization)
**Purpose:** Comprehensive guide to position lifecycle management in Precog
**Status:** ✅ Complete
**Filename Updated:** Renamed from POSITION_MANAGEMENT_GUIDE_V1.0.md to POSITION_MANAGEMENT_GUIDE_V1.0.md (added version number)
---

## Table of Contents

1. [Overview](#overview)
2. [Position Lifecycle](#position-lifecycle)
3. [Entry Rules](#entry-rules)
4. [Position Sizing](#position-sizing)
5. [Dynamic Monitoring](#dynamic-monitoring)
6. [The 10 Exit Conditions](#the-10-exit-conditions)
7. [Exit Priority Hierarchy](#exit-priority-hierarchy)
8. [Exit Execution Strategies](#exit-execution-strategies)
9. [Partial Exit Staging](#partial-exit-staging)
10. [Portfolio Management](#portfolio-management)
11. [Risk Management](#risk-management)
12. [Complete Position Examples](#complete-position-examples)
13. [Best Practices](#best-practices)
14. [Performance Analysis](#performance-analysis)
15. [Troubleshooting](#troubleshooting)

---

## Overview

Position management is the **complete lifecycle** of a trade from entry through monitoring to exit. Proper position management is the difference between a profitable trading system and losses.

**Core Philosophy:**
- ✅ **Rule-Based**: Every decision follows explicit rules
- ✅ **Risk-First**: Protect capital before seeking profits
- ✅ **Dynamic**: Adapt to changing market conditions
- ✅ **Automated**: Remove emotion from trading
- ✅ **Documented**: Every action is logged and auditable

---

## Position Lifecycle

### The 5 Stages

```
┌─────────┐     ┌──────────┐     ┌────────────┐     ┌──────────┐     ┌────────┐
│ ANALYZE │ --> │  ENTER   │ --> │  MONITOR   │ --> │   EXIT   │ --> │ SETTLE │
└─────────┘     └──────────┘     └────────────┘     └──────────┘     └────────┘
    ↓               ↓                  ↓                  ↓               ↓
  Edge         Position Size      Watch Price        Execute         Realize
 Detection      Kelly Sizing     Exit Triggers       Order          Profit/Loss
```

### Stage 1: ANALYZE

**Purpose:** Identify trading opportunities

**Actions:**
1. Probability model calculates true probability
2. Compare to market price
3. Calculate edge: `Edge = (TrueProb × Payout) - 1`
4. Check against minimum edge threshold

**Example:**
```
Game: Chiefs vs Raiders
Model: elo_nfl_v1.1 predicts Chiefs 72% win probability
Market: Chiefs trading at $0.65 (65% implied)
Payout: $1.00 per contract
Edge: (0.72 × 1.00) - 1 = -0.28? No, this is wrong...

Correct calculation:
Expected Value = TrueProb × Payout - Cost
EV = 0.72 × $1.00 - $0.65 = $0.07
Edge = EV / Cost = $0.07 / $0.65 = 10.8% ✓

Minimum Edge: 5%
Decision: 10.8% > 5% → TRADE ✓
```

### Stage 2: ENTER

**Purpose:** Open position with appropriate size

**Actions:**
1. Calculate position size using Kelly Criterion
2. Verify portfolio limits
3. Check trading hours and market liquidity
4. Place entry order
5. Record position in database

**Example:**
```
Edge: 10.8%
Win Probability: 72%
Kelly Fraction: 0.25 (quarter Kelly)
Bankroll: $10,000

Full Kelly = (0.72 × 1.00 - 0.28) / 1.00 = 0.44 (44% of bankroll)
Quarter Kelly = 0.44 × 0.25 = 0.11 (11% of bankroll)
Position Size = $10,000 × 0.11 = $1,100

But max position limit = $1,000
Final Position Size = $1,000 ✓

Contracts: $1,000 / $0.65 = 1,538 contracts
```

### Stage 3: MONITOR

**Purpose:** Track position and watch for exit triggers

**Actions:**
1. Update current price every 30s (normal) or 5s (urgent)
2. Calculate unrealized P&L
3. Evaluate all 10 exit conditions
4. Update trailing stop state (if active)
5. Log position health metrics

**Example:**
```
Time 14:00: Entry at $0.65
Time 14:30: Price = $0.68 (+4.6%) → Normal monitoring
Time 15:00: Price = $0.71 (+9.2%) → Switch to urgent (near +10% activation)
Time 15:05: Price = $0.72 (+10.8%) → Trailing stop ACTIVATED
Time 15:10: Price = $0.75 (+15.4%) → Partial exit trigger (1st stage)
```

### Stage 4: EXIT

**Purpose:** Close position according to exit rules

**Actions:**
1. Determine exit condition and priority
2. Select execution strategy based on urgency
3. Place exit order (market or limit)
4. Execute price walking if needed
5. Record exit in database

**Example:**
```
Trigger: profit_target (MEDIUM priority)
Price: $0.8125 (+25% profit)
Execution: Fair limit order at $0.8125
Timeout: 30 seconds
Walking: Up to 5 attempts

Attempt 1: Limit $0.8125 → Wait 30s → Filled ✓
Exit Price: $0.8125
Profit: $0.8125 - $0.65 = $0.1625 per contract
Total: 1,538 × $0.1625 = $249.93
ROI: 25%
```

### Stage 5: SETTLE

**Purpose:** Finalize trade and record results

**Actions:**
1. Wait for event settlement
2. Verify outcome matches prediction
3. Calculate final realized P&L
4. Update strategy/model performance metrics
5. Archive trade for analysis

**Example:**
```
Game Result: Chiefs win 31-17 ✓
Model Predicted: Chiefs 72% (correct)
Edge Accuracy: Correct prediction ✓

Performance Update:
- elo_nfl_v1.1: edge_accuracy +1 correct prediction
- halftime_entry_nfl_v1.0: +1 winning trade, +$249.93 profit
```

---

## Entry Rules

### Pre-Entry Checklist

**Must Pass ALL Checks:**

```python
def can_enter_position(opportunity):
    """Validate all entry requirements"""

    # 1. Edge Check
    if opportunity.edge < config.min_edge:
        return False, "Edge too low"

    # 2. Confidence Check
    if opportunity.confidence_level < config.min_confidence:
        return False, "Confidence too low"

    # 3. Timing Check
    if not is_within_trading_hours():
        return False, "Outside trading hours"

    time_until_event = opportunity.event_time - now()
    if time_until_event < config.min_time_before_event:
        return False, "Too close to event"

    # 4. Liquidity Check
    if opportunity.market_volume < config.min_volume:
        return False, "Insufficient liquidity"

    if opportunity.bid_ask_spread > config.max_spread:
        return False, "Spread too wide"

    # 5. Portfolio Limits Check
    if current_open_positions >= config.max_open_positions:
        return False, "Max positions reached"

    if current_total_exposure + position_size > config.max_total_exposure:
        return False, "Portfolio limit exceeded"

    # 6. Correlation Check
    if get_correlated_exposure(opportunity.game) > config.max_correlated_exposure:
        return False, "Too much correlated exposure"

    # 7. Circuit Breaker Check
    if is_circuit_breaker_active():
        return False, "Circuit breaker active"

    return True, "All checks passed"
```

### Entry Order Types

**Default: Limit Orders**

```yaml
execution:
  default_order_type: limit
  limit_order_timeout_seconds: 30
  max_slippage_pct: 0.02  # 2% maximum
```

**When to Use Market Orders:**
- Settlement arbitrage (need immediate fill)
- Extremely high edge (>15%)
- Rapidly moving market
- Low liquidity (limit unlikely to fill)

**Example:**
```python
if opportunity.edge > 0.15 or opportunity.strategy_type == 'settlement_arb':
    order_type = 'market'
else:
    order_type = 'limit'
```

---

## Position Sizing

### Kelly Criterion

**Formula:**

```
f = (bp - q) / b

Where:
f = fraction of bankroll to wager
b = odds received (payout - 1)
p = probability of winning
q = probability of losing (1 - p)
```

**Precog Implementation:**

```python
def calculate_kelly_position_size(
    edge: Decimal,
    win_probability: Decimal,
    bankroll: Decimal,
    kelly_fraction: Decimal = Decimal('0.25')
) -> Decimal:
    """Calculate position size using Kelly Criterion"""

    # For binary outcomes (win $1 or lose cost)
    # Simplified: f = edge / ((payout - 1) × (1 - p))
    # For prediction markets: f = edge

    full_kelly = edge
    fractional_kelly = full_kelly * kelly_fraction

    # Apply limits
    position_size = bankroll * fractional_kelly
    position_size = min(position_size, config.max_position_size)
    position_size = max(position_size, config.min_position_size)

    return position_size

# Example:
edge = Decimal('0.108')  # 10.8%
win_prob = Decimal('0.72')
bankroll = Decimal('10000')
kelly_fraction = Decimal('0.25')

size = calculate_kelly_position_size(edge, win_prob, bankroll, kelly_fraction)
# size = 10000 × 0.108 × 0.25 = $270

# But with max limit of $1000, actual size = min($1080, $1000) = $1000
```

### Safety Constraints

**Position Limits:**

| Parameter | Default | Max | Why |
|-----------|---------|-----|-----|
| Kelly Fraction | 0.25 | 0.50 | Avoid over-betting |
| Max Position Size | $1,000 | $5,000 | Capital protection |
| Max Total Exposure | $10,000 | $50,000 | Portfolio limit |
| Min Position Size | $10 | - | Avoid dust trades |

**Example Portfolio:**

```
Position 1: NFL game, $800 (8% of bankroll)
Position 2: NBA game, $600 (6% of bankroll)
Position 3: MLB game, $400 (4% of bankroll)
Total Exposure: $1,800 (18% of bankroll) ✓

Max allowed: $10,000 (100% of bankroll)
Remaining capacity: $8,200
```

---

## Dynamic Monitoring

### Normal vs. Urgent Monitoring

**Normal Mode (30s checks):**
```yaml
monitoring:
  normal_frequency: 30  # Check every 30 seconds
```

**When:** Position is stable, not near any thresholds

**Actions:**
- Update current price
- Calculate unrealized P&L
- Evaluate all exit conditions
- Log position state

**Urgent Mode (5s checks):**
```yaml
monitoring:
  urgent_frequency: 5  # Check every 5 seconds
```

**When:** Position within 2% of any threshold:
- Near stop loss
- Near profit target
- Near trailing stop

**Why:** Ensure timely exits when thresholds are close

**Example:**
```
Entry: $0.60
Stop Loss: $0.51 (-15%)
Profit Target: $0.75 (+25%)

Normal Mode:
- Price $0.65: Check every 30s ✓
- Price $0.70: Check every 30s ✓

Urgent Mode Triggers:
- Price $0.52: Within 2% of stop ($0.51) → 5s checks
- Price $0.74: Within 2% of target ($0.75) → 5s checks
```

### API Rate Management

**Price Caching:**

```yaml
monitoring:
  price_cache_ttl_seconds: 10  # Cache for 10 seconds
  max_api_calls_per_minute: 60  # Hard limit
```

**Benefits:**
- Reduces API load by ~66%
- Prevents rate limit violations
- Acceptable staleness (10s)

**Calculation:**
```
Without caching:
20 positions × (60s / 30s) = 40 calls/min (normal)
5 positions × (60s / 5s) = 60 calls/min (urgent)
Total: 100 calls/min → EXCEEDS LIMIT ❌

With 10s caching:
20 positions × (60s / 30s) × (10s / 30s) = 13 calls/min (normal)
5 positions × (60s / 5s) × (10s / 5s) = 60 calls/min (urgent)
Total: 73 calls/min → But cache shares across positions
Actual: ~40 calls/min ✓
```

---

## The 10 Exit Conditions

### Complete List with Priorities

| # | Exit Condition | Priority | Trigger | Typical Use |
|---|----------------|----------|---------|-------------|
| 1 | **stop_loss** | CRITICAL | Price drops to -15% | Capital protection |
| 2 | **circuit_breaker** | CRITICAL | 5 consecutive losses | System protection |
| 3 | **trailing_stop** | HIGH | Price drops below trailing stop | Lock in profits |
| 4 | **time_based_urgent** | HIGH | <10 min to event, losing | Cut losses quickly |
| 5 | **liquidity_dried_up** | HIGH | Spread >3¢ or volume <50 | Exit illiquid market |
| 6 | **profit_target** | MEDIUM | Price hits +25% target | Take profits |
| 7 | **partial_exit_target** | MEDIUM | Stage 1: +15%, Stage 2: +25% | Scale out |
| 8 | **early_exit** | LOW | Edge drops below 2% | Exit marginal positions |
| 9 | **edge_disappeared** | LOW | Edge turns negative | Exit bad positions |
| 10 | **rebalance** | LOW | Portfolio rebalancing needed | Optimization |

### Detailed Descriptions

**1. Stop Loss (CRITICAL)**

```yaml
stop_loss:
  enabled: true  # Always on (NOT user-customizable)
  high_confidence: -0.15  # -15%
  medium_confidence: -0.12
  low_confidence: -0.08
```

**Purpose:** Prevent catastrophic losses

**Trigger:**
```python
if (current_price - entry_price) / entry_price <= stop_loss_threshold:
    trigger_exit('stop_loss', priority='CRITICAL')
```

**Example:**
```
Entry: $0.60
Stop Loss: $0.51 (-15%)
Current: $0.50
Action: Market order immediately
```

**2. Circuit Breaker (CRITICAL)**

```yaml
circuit_breaker:
  consecutive_losses: 5  # NOT user-customizable
  rapid_loss_dollars: 200
  rapid_loss_minutes: 15
```

**Purpose:** System protection against catastrophic failure

**Trigger:**
- 5 consecutive losing trades, OR
- $200 loss in 15 minutes

**Action:** Close ALL positions, halt trading

**3. Trailing Stop (HIGH)**

```yaml
trailing_stop:
  enabled: true
  activation_threshold: 0.10
  initial_distance: 0.05
  tightening_rate: 0.01
  floor_distance: 0.02
```

**Purpose:** Lock in profits on winning positions

**See TRAILING_STOP_GUIDE_V1.0.md for complete details**

**4. Time-Based Urgent (HIGH)**

```yaml
time_based_urgent:
  enabled: true
  minutes_remaining: 10
  loss_threshold_pct: 0.05  # Any loss
```

**Purpose:** Exit losing positions near event end

**Trigger:**
```python
minutes_left = (event_time - now()).total_seconds() / 60
if minutes_left <= 10 and unrealized_pnl < 0:
    trigger_exit('time_based_urgent', priority='HIGH')
```

**Example:**
```
Event Time: 16:00
Current Time: 15:52 (8 minutes left)
Position P&L: -$50 (-5%)
Action: Aggressive limit order, walk to market if needed
```

**5. Liquidity Dried Up (HIGH)**

```yaml
liquidity:
  max_spread: 0.03  # 3¢
  min_volume: 50
  exit_on_illiquid: true
```

**Purpose:** Exit before getting trapped in illiquid market

**Trigger:**
```python
if bid_ask_spread > 0.03 or total_volume < 50:
    trigger_exit('liquidity_dried_up', priority='HIGH')
```

**Example:**
```
Best Bid: $0.60
Best Ask: $0.64
Spread: $0.04 > $0.03 ✓ TRIGGER
Volume: 30 contracts < 50 ✓ TRIGGER
Action: Aggressive exit before liquidity disappears completely
```

**6. Profit Target (MEDIUM)**

```yaml
profit_target:
  enabled: true
  high_confidence: 0.25  # +25%
  medium_confidence: 0.20
  low_confidence: 0.15
```

**Purpose:** Take profits at predetermined levels

**Trigger:**
```python
if unrealized_pnl_pct >= profit_target:
    trigger_exit('profit_target', priority='MEDIUM')
```

**Example:**
```
Entry: $0.60
Target: $0.75 (+25%)
Current: $0.76
Action: Fair limit order at $0.76
```

**7. Partial Exit Target (MEDIUM)**

```yaml
partial_exits:
  enabled: true
  stages:
    - profit_threshold: 0.15  # Stage 1: +15%
      exit_percentage: 50     # Exit 50%
    - profit_threshold: 0.25  # Stage 2: +25%
      exit_percentage: 25     # Exit 25%
```

**Purpose:** Scale out of winners, let remainder ride

**See Partial Exit Staging section below**

**8. Early Exit (LOW)**

```yaml
early_exit:
  enabled: true
  edge_threshold: 0.02  # Exit if edge drops below 2%
```

**Purpose:** Exit positions with deteriorating edge

**Trigger:**
```python
current_edge = recalculate_edge(position)
if current_edge < 0.02:
    trigger_exit('early_exit', priority='LOW')
```

**Example:**
```
Entry Edge: 8%
Current Edge: 1.5% (edge deteriorated)
Action: Conservative limit order, patient exit
```

**9. Edge Disappeared (LOW)**

```yaml
edge_disappeared:
  enabled: true
  # Triggers when edge turns negative
```

**Purpose:** Exit positions with negative expected value

**Trigger:**
```python
current_edge = recalculate_edge(position)
if current_edge < 0:
    trigger_exit('edge_disappeared', priority='LOW')
```

**Example:**
```
Entry Edge: 6%
Current Edge: -2% (negative EV)
Action: Exit methodically, no rush but should exit
```

**10. Rebalance (LOW)**

```yaml
rebalance:
  enabled: true
  max_correlated_exposure: 5000
  # Triggers when portfolio needs rebalancing
```

**Purpose:** Maintain portfolio balance and risk exposure

**Trigger:**
```python
if calculate_portfolio_imbalance() > threshold:
    positions_to_exit = select_positions_for_rebalance()
    for pos in positions_to_exit:
        trigger_exit('rebalance', priority='LOW')
```

---

## Exit Priority Hierarchy

### Conflict Resolution

**Rule:** When multiple exit conditions trigger simultaneously, execute the highest priority.

**Priority Levels:**

```
CRITICAL > HIGH > MEDIUM > LOW

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

### Example Scenarios

**Scenario 1: Multiple Triggers**

```
Position State:
- Current Price: $0.52
- Entry Price: $0.60
- Stop Loss: $0.51 (-15%)
- Edge: -1% (negative)

Triggered Conditions:
1. stop_loss (CRITICAL): Price $0.52 below stop $0.51
2. edge_disappeared (LOW): Edge is -1%

Resolution: Execute stop_loss (CRITICAL priority)
Action: Market order immediately
```

**Scenario 2: Trailing Stop vs. Profit Target**

```
Position State:
- Current Price: $0.75
- Entry Price: $0.60
- Profit Target: $0.75 (+25%)
- Trailing Stop: $0.735 (2% below peak of $0.75)

Triggered Conditions:
1. profit_target (MEDIUM): Price hit $0.75 target
2. trailing_stop (HIGH): If price drops to $0.735

Resolution: Both can coexist
- Profit target exits full position at $0.75 → Position closed
- Trailing stop doesn't execute (position already closed)
```

**Scenario 3: Time Urgent vs. Early Exit**

```
Position State:
- Current Price: $0.58
- Entry Price: $0.60 (-3.3%)
- Minutes to Event: 8 minutes
- Current Edge: 1.8%

Triggered Conditions:
1. time_based_urgent (HIGH): <10 min and losing
2. early_exit (LOW): Edge 1.8% < 2% threshold

Resolution: Execute time_based_urgent (HIGH priority)
Action: Aggressive limit order with price walking
```

---

## Exit Execution Strategies

### By Priority Level

**CRITICAL Priority (Immediate Market Orders)**

```yaml
exit_execution:
  CRITICAL:
    order_type: market
    timeout_seconds: 5
    retry_strategy: immediate_market
```

**Use Case:** stop_loss, circuit_breaker

**Execution:**
1. Place market order for full position
2. Wait 5 seconds
3. If not filled, place another market order
4. Repeat until filled

**Goal:** Exit at ANY price, minimize loss

---

**HIGH Priority (Aggressive Limits → Market)**

```yaml
exit_execution:
  HIGH:
    order_type: limit
    price_strategy: aggressive  # Best bid + $0.01
    timeout_seconds: 10
    retry_strategy: walk_then_market
    max_walks: 2
```

**Use Case:** trailing_stop, time_based_urgent, liquidity_dried_up

**Execution:**
1. Limit order at best_bid + $0.01 (aggressive)
2. Wait 10 seconds
3. If not filled, walk to best_bid
4. Wait 10 seconds
5. If still not filled, place market order

**Goal:** Fast exit with minimal slippage

---

**MEDIUM Priority (Fair Limits + Walking)**

```yaml
exit_execution:
  MEDIUM:
    order_type: limit
    price_strategy: fair  # Best bid (no premium)
    timeout_seconds: 30
    retry_strategy: walk_price
    max_walks: 5
```

**Use Case:** profit_target, partial_exit_target

**Execution:**
1. Limit order at best_bid (fair price)
2. Wait 30 seconds
3. If not filled, walk +$0.01
4. Repeat up to 5 times (total: 2.5 minutes)

**Goal:** Balanced price and speed

---

**LOW Priority (Conservative + Patient Walking)**

```yaml
exit_execution:
  LOW:
    order_type: limit
    price_strategy: conservative  # Best bid - $0.01
    timeout_seconds: 60
    retry_strategy: walk_slowly
    max_walks: 10
```

**Use Case:** early_exit, edge_disappeared, rebalance

**Execution:**
1. Limit order at best_bid - $0.01 (wait for better)
2. Wait 60 seconds
3. If not filled, walk +$0.01
4. Repeat up to 10 times (total: 10 minutes)

**Goal:** Best possible price, patient

---

## Partial Exit Staging

### 2-Stage Exit Strategy

**Configuration:**

```yaml
partial_exits:
  enabled: true
  stages:
    - name: "first_target"
      profit_threshold: 0.15  # +15%
      exit_percentage: 50     # Exit 50%

    - name: "second_target"
      profit_threshold: 0.25  # +25%
      exit_percentage: 25     # Exit 25%

# Remaining 25% rides with trailing stop
```

### Complete Example

**Entry:**
- 100 contracts @ $0.60
- Total investment: $60.00

**Stage 1: +15% Profit**
```
Price: $0.69 (+15%)
Exit: 50 contracts @ $0.69
Revenue: 50 × $0.69 = $34.50
Profit on stage 1: $34.50 - (50 × $0.60) = $4.50 (+15%)
Remaining: 50 contracts
```

**Stage 2: +25% Profit**
```
Price: $0.75 (+25%)
Exit: 25 contracts @ $0.75
Revenue: 25 × $0.75 = $18.75
Profit on stage 2: $18.75 - (25 × $0.60) = $3.75 (+25%)
Remaining: 25 contracts
```

**Trailing Stop Exit**
```
Peak: $0.90 (+50%)
Trailing Stop: $0.882 (2% behind)
Exit: 25 contracts @ $0.882
Revenue: 25 × $0.882 = $22.05
Profit on remainder: $22.05 - (25 × $0.60) = $7.05 (+47%)
```

**Total P&L:**
```
Stage 1: $4.50
Stage 2: $3.75
Trailing: $7.05
Total: $15.30 on $60 invested = 25.5% ROI
```

### Benefits

1. **De-Risk Early:** Lock in profits at +15%
2. **Capture More:** Let remainder run to +25%
3. **Maximize Upside:** Final 25% can capture huge moves
4. **Psychological:** Easier to hold winners when profits secured

---

## Portfolio Management

### Position Limits

```yaml
portfolio:
  max_open_positions: 10
  max_total_capital_deployed: 10000
  max_correlated_exposure: 3000

  max_exposure_by_sport:
    nfl: 0.60  # 60% of portfolio
    nba: 0.40
    mlb: 0.30
```

### Correlation Management

**Problem:**
```
Position 1: Chiefs -7.5 (buy Chiefs to win)
Position 2: Raiders +7.5 (buy Raiders to cover)
Correlation: 100% (same game, opposite sides)

If wrong: Both positions lose → Double loss
```

**Solution:**
```python
def calculate_correlated_exposure(new_position):
    """Calculate total exposure to correlated positions"""
    correlated_positions = get_positions_same_game(new_position.game_id)
    total_exposure = sum(pos.size for pos in correlated_positions)
    return total_exposure + new_position.size

# Before entry
if calculate_correlated_exposure(new_pos) > config.max_correlated_exposure:
    reject_entry("Too much correlated exposure")
```

### Diversification

**Best Practices:**

```yaml
# Good Diversification
Position 1: NFL - Chiefs vs Raiders ($800)
Position 2: NBA - Lakers vs Celtics ($600)
Position 3: MLB - Yankees vs Red Sox ($400)
Position 4: NFL - Bills vs Dolphins ($700)
Total: $2,500 across 3 sports ✓

# Poor Diversification
Position 1: NFL - Chiefs -7.5 ($800)
Position 2: NFL - Chiefs ML ($600)
Position 3: NFL - Chiefs/Raiders Over 50.5 ($400)
Position 4: NFL - Chiefs 1H -3.5 ($700)
Total: $2,500 but 100% correlated to Chiefs ❌
```

---

## Risk Management

### Circuit Breakers

**Purpose:** Automatic system shutdown to prevent catastrophic losses

**Types:**

**1. Consecutive Losses**
```yaml
circuit_breakers:
  consecutive_losses:
    threshold: 5
    action: close_all_positions
    reset: manual  # Requires manual investigation
```

**2. Rapid Loss**
```yaml
circuit_breakers:
  rapid_loss:
    loss_dollars: 200
    window_minutes: 15
    action: close_all_positions
```

**3. API Failures**
```yaml
circuit_breakers:
  api_failures:
    threshold: 5
    window_minutes: 5
    action: halt_new_entries  # Keep existing positions
```

### Daily Loss Limits

```yaml
loss_limits:
  daily_loss_limit_dollars: 500
  action: halt_trading
  reset: next_day_midnight
```

**Example:**
```
Day Start: $10,000 bankroll
Loss 1: -$150
Loss 2: -$180
Loss 3: -$120
Total: -$450

Remaining capacity: $500 - $450 = $50
Can only open positions with max loss ≤ $50
```

---

## Complete Position Examples

### Example 1: Clean Winner

**Setup:**
- Strategy: halftime_entry_nfl_v1.0
- Model: elo_nfl_v1.1
- Game: Chiefs vs Raiders, halftime, Chiefs up 14-3
- Edge: 8.5%

**Entry:**
```
Time: 15:32 (halftime, 10 min into break)
Price: $0.65 (Chiefs 2H winner)
Model Probability: 72%
Contracts: 1,000 @ $0.65
Investment: $650
```

**Monitoring:**
```
15:45: Price $0.68 (+4.6%) - Normal monitoring (30s)
16:00: Price $0.70 (+7.7%) - Normal monitoring
16:15: Price $0.72 (+10.8%) - Urgent monitoring (5s), trailing stop activates
16:30: Price $0.75 (+15.4%) - Partial exit stage 1 triggers
```

**Stage 1 Exit:**
```
Price: $0.75
Exit: 500 contracts (50%)
Revenue: $375
Profit: $375 - $325 = $50 (+15.4%)
Remaining: 500 contracts
```

**Continued Monitoring:**
```
16:45: Price $0.80 (+23%) - Approaching stage 2
17:00: Price $0.8125 (+25%) - Partial exit stage 2 triggers
```

**Stage 2 Exit:**
```
Price: $0.8125
Exit: 250 contracts (25%)
Revenue: $203.13
Profit: $203.13 - $162.50 = $40.63 (+25%)
Remaining: 250 contracts
```

**Final Exit (Trailing Stop):**
```
17:30: Price peaks at $0.90 (+38.5%)
Trailing Stop: $0.882 (2% behind, floor distance)
17:45: Price drops to $0.88, then $0.881
17:46: Price hits $0.882 → EXIT
Revenue: $220.50
Profit: $220.50 - $162.50 = $58.00 (+35.7%)
```

**Total P&L:**
```
Stage 1: $50.00 (+15.4%)
Stage 2: $40.63 (+25.0%)
Trailing: $58.00 (+35.7%)
Total: $148.63 / $650 = 22.9% ROI
```

---

### Example 2: Stop Loss Exit

**Setup:**
- Strategy: pre_game_entry_nfl_v1.0
- Model: elo_nfl_v1.1
- Game: Dolphins vs Jets (pre-game)
- Edge: 6.2%

**Entry:**
```
Time: 11:00 (2 hours before kickoff)
Price: $0.58 (Dolphins to win)
Model Probability: 64%
Contracts: 800 @ $0.58
Investment: $464
Stop Loss: $0.493 (-15%)
```

**Monitoring:**
```
11:30: Price $0.56 (-3.4%) - Normal monitoring
12:00: Price $0.54 (-6.9%) - Normal monitoring
12:15: Price $0.52 (-10.3%) - Normal monitoring
12:30: Price $0.505 (-12.9%) - Urgent monitoring (near stop loss)
12:35: Price $0.495 (-14.7%) - Still urgent
12:38: Price $0.49 (-15.5%) - STOP LOSS TRIGGERED
```

**Stop Loss Exit:**
```
Trigger: Price $0.49 below stop $0.493
Priority: CRITICAL
Execution: Market order
Fill Price: $0.485 (slippage)
Revenue: 800 × $0.485 = $388
Loss: $388 - $464 = -$76 (-16.4%)
```

**Analysis:**
```
Stop Loss Worked:
- Prevented larger loss (price went to $0.42 later)
- Slippage: $0.493 target → $0.485 actual = -$6.40
- Protected capital: Lost $76 instead of $128
```

---

### Example 3: Liquidity Dried Up

**Setup:**
- Strategy: live_trading_nfl_v1.0
- Game: Late 4th quarter, close game
- Edge: 12% (high edge, low volume)

**Entry:**
```
Time: 15:50 (8 min left in game)
Price: $0.62
Contracts: 500 @ $0.62
Investment: $310
```

**Monitoring:**
```
15:52: Price $0.65 (+4.8%), Volume: 120 contracts ✓
15:54: Price $0.68 (+9.7%), Volume: 80 contracts ✓
15:56: Price $0.70 (+12.9%), Volume: 45 contracts
```

**Liquidity Check:**
```
Current Volume: 45 contracts < 50 minimum ✓ TRIGGER
Best Bid: $0.68
Best Ask: $0.72
Spread: $0.04 > $0.03 maximum ✓ TRIGGER

Condition: liquidity_dried_up
Priority: HIGH
```

**Exit Execution:**
```
Strategy: Aggressive limit with price walking
Attempt 1: Limit $0.69 (bid + $0.01) → 10s timeout → No fill
Attempt 2: Limit $0.68 (bid) → 10s timeout → No fill
Attempt 3: Market order → Fill at $0.66

Revenue: 500 × $0.66 = $330
Profit: $330 - $310 = $20 (+6.5%)
```

**Analysis:**
```
Saved by liquidity exit:
- Exited at $0.66 before market crashed to $0.52
- Captured +6.5% profit instead of -16% loss
- Accepted $0.02 slippage to escape illiquid market
```

---

## Best Practices

### DO ✅

1. **Always Use Stop Losses**
   ```yaml
   stop_loss:
     enabled: true  # NEVER disable
   ```

2. **Size Positions with Kelly**
   ```python
   size = calculate_kelly_size(edge, bankroll, kelly_fraction=0.25)
   ```

3. **Monitor Actively**
   ```yaml
   monitoring:
     normal_frequency: 30
     urgent_frequency: 5
   ```

4. **Respect Circuit Breakers**
   ```
   5 consecutive losses → STOP, investigate, don't override
   ```

5. **Use Partial Exits**
   ```yaml
   partial_exits:
     enabled: true  # Capture profits early
   ```

6. **Document Every Exit**
   ```sql
   INSERT INTO position_exits (position_id, exit_reason, exit_price, ...)
   ```

7. **Analyze Performance**
   ```sql
   SELECT exit_reason, COUNT(*), AVG(realized_pnl)
   FROM positions
   GROUP BY exit_reason;
   ```

### DON'T ❌

1. **Don't Disable Stop Losses**
   ```yaml
   stop_loss:
     enabled: false  # ❌ NEVER DO THIS
   ```

2. **Don't Over-Leverage**
   ```python
   kelly_fraction = 0.75  # ❌ Over-betting, risk of ruin
   ```

3. **Don't Ignore Correlation**
   ```
   10 positions all on same game ❌
   ```

4. **Don't Override Circuit Breakers**
   ```
   5 losses → "Let me try one more" ❌
   ```

5. **Don't Trade Without Edge**
   ```python
   if edge < config.min_edge:
       # ❌ DON'T TRADE
   ```

6. **Don't Chase Losses**
   ```
   Lost $500 today → Double position size to recover ❌
   ```

7. **Don't Manually Override Exits**
   ```
   Trailing stop triggers → "Let me hold a bit longer" ❌
   ```

---

## Performance Analysis

### Key Metrics

```sql
-- Overall Performance
SELECT
    COUNT(*) as total_trades,
    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as winning_trades,
    AVG(realized_pnl) as avg_pnl,
    AVG(realized_pnl_pct) as avg_roi,
    STDDEV(realized_pnl_pct) as volatility,
    MIN(realized_pnl) as worst_trade,
    MAX(realized_pnl) as best_trade
FROM positions
WHERE exit_price IS NOT NULL;
```

### By Exit Reason

```sql
-- Exit Reason Analysis
SELECT
    exit_reason,
    COUNT(*) as count,
    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as winners,
    AVG(realized_pnl) as avg_pnl,
    AVG(realized_pnl_pct) as avg_roi
FROM positions
WHERE exit_price IS NOT NULL
GROUP BY exit_reason
ORDER BY count DESC;

-- Example Results:
-- trailing_stop: 45 trades, 43 winners, $12.50 avg, +18.2% ROI
-- profit_target: 32 trades, 32 winners, $8.20 avg, +15.0% ROI
-- stop_loss: 18 trades, 0 winners, -$15.40 avg, -14.8% ROI
-- partial_exit: 28 stages, 28 winners, $7.80 avg, +12.5% ROI
```

### Hold Time Analysis

```sql
-- Average Hold Time by Exit Reason
SELECT
    exit_reason,
    AVG(EXTRACT(EPOCH FROM (exit_timestamp - entry_timestamp)) / 60) as avg_hold_minutes,
    MIN(EXTRACT(EPOCH FROM (exit_timestamp - entry_timestamp)) / 60) as min_hold_minutes,
    MAX(EXTRACT(EPOCH FROM (exit_timestamp - entry_timestamp)) / 60) as max_hold_minutes
FROM positions
WHERE exit_price IS NOT NULL
GROUP BY exit_reason;
```

---

## Troubleshooting

### Issue: Position Not Exiting

**Symptoms:**
```
Exit condition triggered but position still open
```

**Diagnosis:**
```sql
-- Check position state
SELECT
    position_id,
    entry_price,
    current_price,
    exit_price,
    (trailing_stop_state->>'active')::boolean as trailing_active,
    (trailing_stop_state->>'current_stop_price')::decimal as stop_price
FROM positions
WHERE position_id = 123;
```

**Common Causes:**
1. Exit execution failed (check exit_attempts table)
2. Monitoring loop not running
3. Order not filled (check Kalshi order status)

**Solution:**
```python
# Manual exit
create_exit_order(position_id=123, exit_reason='manual', priority='HIGH')
```

---

### Issue: Too Many Premature Exits

**Symptoms:**
```
Trailing stops exiting too early
Average hold time: 15 minutes
Missing large moves
```

**Diagnosis:**
```sql
-- Check trailing stop exits
SELECT
    AVG((peak_price - exit_price) / entry_price) as avg_giveback_pct,
    AVG((peak_price - entry_price) / entry_price) as avg_peak_gain_pct
FROM positions
JOIN LATERAL (
    SELECT
        (trailing_stop_state->>'peak_price')::decimal as peak_price
    FROM positions p2
    WHERE p2.position_id = positions.position_id
) ts ON TRUE
WHERE exit_reason = 'trailing_stop';
```

**Solution:**
Loosen trailing stop configuration:
```yaml
trailing_stop:
  activation_threshold: 0.15  # Was 0.10, activate later
  initial_distance: 0.08      # Was 0.05, wider stop
  floor_distance: 0.04        # Was 0.02, looser floor
```

---

### Issue: Hitting Circuit Breakers

**Symptoms:**
```
Circuit breaker triggered after 5 consecutive losses
System halted trading
```

**Diagnosis:**
```sql
-- Check recent trades
SELECT
    trade_id,
    entry_price,
    exit_price,
    realized_pnl,
    exit_reason
FROM positions
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;
```

**Possible Causes:**
1. Model miscalibrated
2. Market conditions changed
3. Strategy no longer working
4. System bug

**Solution:**
1. Review recent trades for patterns
2. Backtest model on recent data
3. Check if edge calculations are correct
4. Paper trade before resuming
5. Reduce position sizes
6. Only resume after root cause identified

---

## Summary

Position management is the **complete lifecycle** from entry to exit:

**Key Principles:**
1. ✅ **Enter with Edge** - Only trade when edge > threshold
2. ✅ **Size with Kelly** - Fractional Kelly prevents over-betting
3. ✅ **Monitor Dynamically** - 30s normal, 5s urgent
4. ✅ **Exit by Rules** - 10 conditions with priority hierarchy
5. ✅ **Execute by Urgency** - CRITICAL = market, LOW = patient
6. ✅ **Protect Capital** - Stop losses and circuit breakers mandatory
7. ✅ **Scale Out** - Partial exits de-risk winners
8. ✅ **Analyze Performance** - Learn from every trade

**Success Formula:**
```
Good Position Management =
  Proper Entry (Edge + Sizing) +
  Active Monitoring (Dynamic Frequency) +
  Rule-Based Exits (Priority Hierarchy) +
  Risk Management (Stops + Circuit Breakers) +
  Performance Analysis (Continuous Improvement)
```

---

**Document:** POSITION_MANAGEMENT_GUIDE_V1.0.md
**Version:** 1.0
**Created:** 2025-10-21
**Last Updated:** 2025-10-21
**Status:** ✅ Complete and validated
