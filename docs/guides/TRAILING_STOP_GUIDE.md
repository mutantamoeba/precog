# Precog Trailing Stop Guide

---
**Version:** 1.0
**Created:** 2025-10-21
**Purpose:** Comprehensive guide to trailing stop implementation and usage in Precog
**Status:** ✅ Complete
---

## Table of Contents

1. [Overview](#overview)
2. [What is a Trailing Stop?](#what-is-a-trailing-stop)
3. [Why Use Trailing Stops?](#why-use-trailing-stops)
4. [How Trailing Stops Work](#how-trailing-stops-work)
5. [Configuration Parameters](#configuration-parameters)
6. [The Tightening Mechanism](#the-tightening-mechanism)
7. [JSONB State Management](#jsonb-state-management)
8. [Complete Examples](#complete-examples)
9. [Database Schema](#database-schema)
10. [Implementation Details](#implementation-details)
11. [When to Use Trailing Stops](#when-to-use-trailing-stops)
12. [When NOT to Use Trailing Stops](#when-not-to-use-trailing-stops)
13. [Configuration Tuning](#configuration-tuning)
14. [Common Scenarios](#common-scenarios)
15. [Best Practices](#best-practices)
16. [Troubleshooting](#troubleshooting)

---

## Overview

A **trailing stop** is a dynamic exit mechanism that:
- ✅ Locks in profits as position moves in your favor
- ✅ Automatically adjusts stop price as price increases
- ✅ Protects against reversals while allowing upside
- ✅ Tightens distance progressively to maximize gains

**Key Innovation:** Precog's trailing stops use **progressive tightening** - the distance shrinks as profits increase, giving more room early but protecting more aggressively later.

---

## What is a Trailing Stop?

### Traditional Stop Loss (Static)

```
Entry: $0.60
Stop Loss: $0.51 (-15%)

Price moves to $0.80 (+33% profit)
Stop STILL at $0.51
If reverses to $0.52, position closes at $0.52

Problem: Gave back 35% of gains ($0.80 → $0.52)
```

### Trailing Stop (Dynamic)

```
Entry: $0.60
Initial Stop: $0.57 (-5% behind)

Price moves to $0.70 → Stop adjusts to $0.665 (-5% behind)
Price moves to $0.80 → Stop adjusts to $0.76 (-5% behind)
Price moves to $0.90 → Stop adjusts to $0.855 (-5% behind)

If reverses to $0.85, position closes at $0.855

Result: Captured $0.255 gain vs. entry ($0.855 - $0.60 = 42.5% profit)
```

**Benefit:** Locks in profits automatically as price rises, exits on reversal.

---

## Why Use Trailing Stops?

### Problem: Fixed Profit Targets Leave Money on the Table

**Scenario: Fixed 25% Profit Target**

```
Entry: $0.60
Target: $0.75 (+25%)

Price path:
$0.60 → $0.70 → $0.75 → EXIT ✓ (+25%)

But price continued:
$0.75 → $0.80 → $0.85 → $0.90

Missed: Additional 20% gain ($0.75 → $0.90)
```

### Solution: Trailing Stop Rides the Trend

**Same Scenario with Trailing Stop**

```
Entry: $0.60
Trailing Stop: Active at +10% profit

Price path:
$0.60 → $0.70 (stop at $0.665) → $0.75 (stop at $0.7125) →
$0.80 (stop at $0.76) → $0.85 (stop at $0.8075) →
$0.90 (stop at $0.855)

Reverses: $0.90 → $0.86 → $0.855 → EXIT ✓ (+42.5%)

Captured: 42.5% vs. 25% with fixed target (70% more profit!)
```

---

## How Trailing Stops Work

### 4-Step Process

**Step 1: Activation**

Trailing stop activates when position reaches **activation threshold** (default: +10% profit).

```
Entry: $0.60
Activation Threshold: 0.10 (10%)
Activation Price: $0.60 × 1.10 = $0.66

When price hits $0.66:
- Trailing stop: ACTIVATED ✓
- Initial stop price: $0.66 × (1 - 0.05) = $0.627 (5% behind)
```

**Step 2: Tracking Peak**

System continuously tracks **peak price** (highest price since activation).

```
Time 10:00: Price = $0.70 → Peak = $0.70, Stop = $0.665
Time 10:05: Price = $0.68 → Peak = $0.70 (unchanged), Stop = $0.665
Time 10:10: Price = $0.75 → Peak = $0.75 (new high), Stop = $0.7125
```

**Step 3: Tightening**

Distance shrinks by **tightening rate** with each $0.10 gain (default: 0.01 = 1%).

```
Initial distance: 5%
After +$0.10 gain: 5% - 1% = 4%
After +$0.20 gain: 4% - 1% = 3%
After +$0.30 gain: 3% - 1% = 2% (floor reached)
```

**Step 4: Exit Trigger**

Exit triggers when price drops below stop price.

```
Peak: $0.90, Stop: $0.855 (5% behind)
Current Price: $0.86 → Still above stop ✓
Current Price: $0.85 → Below stop ✗ → EXIT at $0.855
```

---

## Configuration Parameters

### Full Configuration (position_management.yaml)

```yaml
trailing_stop:
  enabled: true  # user-customizable

  # Step 1: When to activate
  activation_threshold: 0.10  # user-customizable: 0.05-0.20
  # Activate when position reaches +10% profit

  # Step 2: Initial distance
  initial_distance: 0.05  # user-customizable: 0.02-0.10
  # Start 5% below peak price

  # Step 3: Tightening
  tightening_rate: 0.01  # user-customizable: 0.005-0.02
  # Reduce distance by 1% for each $0.10 gain

  # Step 4: Floor (minimum distance)
  floor_distance: 0.02  # user-customizable: 0.01-0.05
  # Never tighten beyond 2%
```

### Parameter Details

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `activation_threshold` | 0.10 | 0.05-0.20 | Profit % to activate (10% = $0.60 → $0.66) |
| `initial_distance` | 0.05 | 0.02-0.10 | Starting % behind peak (5% = $0.05 on $1.00) |
| `tightening_rate` | 0.01 | 0.005-0.02 | % to reduce per $0.10 gain (1% per $0.10) |
| `floor_distance` | 0.02 | 0.01-0.05 | Minimum % behind peak (2% floor) |

---

## The Tightening Mechanism

### Why Tighten?

**Problem with Fixed Distance:**

```
Entry: $0.60, Stop: 5% behind throughout

At +10% ($0.66): Stop at $0.627 (5% behind) → OK
At +50% ($0.90): Stop at $0.855 (5% behind) → Too loose!

5% of $0.90 = $0.045 giveback
That's 7.5% of original entry price!
```

**Solution: Progressive Tightening**

```
Entry: $0.60

At +10% ($0.66): Stop 5% behind = $0.627
At +20% ($0.72): Stop 4% behind = $0.6912
At +30% ($0.78): Stop 3% behind = $0.7566
At +40% ($0.84): Stop 2% behind = $0.8232 (floor reached)
At +50% ($0.90): Stop 2% behind = $0.882 (floor maintained)
```

### Tightening Formula

**Distance Calculation:**

```python
def calculate_distance(entry_price, current_peak, initial_distance, tightening_rate, floor_distance):
    # Calculate total gain
    gain = current_peak - entry_price
    gain_increments = gain / 0.10  # Number of $0.10 increments

    # Calculate distance reduction
    distance_reduction = tightening_rate * gain_increments

    # Apply reduction with floor
    current_distance = max(
        initial_distance - distance_reduction,
        floor_distance
    )

    return current_distance

# Example:
entry = 0.60
peak = 0.80  # +$0.20 gain
initial_distance = 0.05
tightening_rate = 0.01
floor = 0.02

gain = 0.80 - 0.60 = 0.20
increments = 0.20 / 0.10 = 2
reduction = 0.01 × 2 = 0.02
current_distance = max(0.05 - 0.02, 0.02) = 0.03 (3%)

stop_price = 0.80 × (1 - 0.03) = $0.776
```

### Tightening Schedule

**Default Configuration (5% initial, 1% tightening, 2% floor):**

| Profit | Peak Price | Gain | Distance | Stop Price | Giveback Allowed |
|--------|------------|------|----------|------------|------------------|
| +10% | $0.66 | $0.06 | 5.0% | $0.627 | $0.033 (5.5% of entry) |
| +20% | $0.72 | $0.12 | 4.0% | $0.6912 | $0.0288 (4.8% of entry) |
| +30% | $0.78 | $0.18 | 3.0% | $0.7566 | $0.0234 (3.9% of entry) |
| +40% | $0.84 | $0.24 | 2.0% | $0.8232 | $0.0168 (2.8% of entry) |
| +50% | $0.90 | $0.30 | 2.0% | $0.882 | $0.018 (3.0% of entry) |

**Key Insight:** Maximum giveback is capped at 5.5% of entry price (at activation), then decreases to 2.8-3.0% as profits grow.

---

## JSONB State Management

### Why JSONB?

Trailing stop state is **dynamic and position-specific**, making JSONB ideal:

```sql
trailing_stop_state JSONB
```

**Advantages:**
- ✅ Flexible schema (add fields without ALTER TABLE)
- ✅ Atomic updates (single column update)
- ✅ Efficient indexing (GIN indexes on JSONB)
- ✅ Self-documenting (field names in data)

### State Structure

```json
{
  "active": true,
  "activated_at": "2024-09-15T14:32:18Z",
  "peak_price": 0.90,
  "peak_timestamp": "2024-09-15T15:18:42Z",
  "current_stop_price": 0.882,
  "current_distance": 0.02,
  "activation_price": 0.66,
  "entry_price": 0.60,
  "total_gain": 0.30,
  "config_snapshot": {
    "activation_threshold": 0.10,
    "initial_distance": 0.05,
    "tightening_rate": 0.01,
    "floor_distance": 0.02
  }
}
```

### Database Implementation

```sql
-- positions table
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    entry_price DECIMAL(10,4) NOT NULL,
    quantity INT NOT NULL,
    current_price DECIMAL(10,4),

    -- Trailing stop state
    trailing_stop_state JSONB,

    -- Other fields...
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for querying active trailing stops
CREATE INDEX idx_positions_trailing_stop_active
ON positions ((trailing_stop_state->>'active'))
WHERE trailing_stop_state->>'active' = 'true';

-- Index for stop price queries
CREATE INDEX idx_positions_stop_price
ON positions (((trailing_stop_state->>'current_stop_price')::decimal));
```

### State Transitions

**Initial State (Entry):**
```json
{
  "active": false,
  "entry_price": 0.60,
  "config_snapshot": { ... }
}
```

**Activation (+10% profit):**
```json
{
  "active": true,
  "activated_at": "2024-09-15T14:32:18Z",
  "activation_price": 0.66,
  "peak_price": 0.66,
  "peak_timestamp": "2024-09-15T14:32:18Z",
  "current_stop_price": 0.627,
  "current_distance": 0.05,
  "entry_price": 0.60,
  "total_gain": 0.06,
  "config_snapshot": { ... }
}
```

**New Peak ($0.80):**
```json
{
  "active": true,
  "activated_at": "2024-09-15T14:32:18Z",
  "activation_price": 0.66,
  "peak_price": 0.80,  // Updated
  "peak_timestamp": "2024-09-15T15:05:22Z",  // Updated
  "current_stop_price": 0.776,  // Updated (3% behind)
  "current_distance": 0.03,  // Updated (tightened)
  "entry_price": 0.60,
  "total_gain": 0.20,  // Updated
  "config_snapshot": { ... }
}
```

### Update Queries

**Activate Trailing Stop:**
```sql
UPDATE positions
SET trailing_stop_state = jsonb_build_object(
    'active', true,
    'activated_at', NOW(),
    'activation_price', current_price,
    'peak_price', current_price,
    'peak_timestamp', NOW(),
    'current_stop_price', current_price * 0.95,  -- 5% behind
    'current_distance', 0.05,
    'entry_price', entry_price,
    'total_gain', current_price - entry_price,
    'config_snapshot', (
        SELECT jsonb_build_object(
            'activation_threshold', 0.10,
            'initial_distance', 0.05,
            'tightening_rate', 0.01,
            'floor_distance', 0.02
        )
    )
),
updated_at = NOW()
WHERE position_id = 123
  AND current_price >= entry_price * 1.10;
```

**Update Peak Price:**
```sql
UPDATE positions
SET trailing_stop_state = jsonb_set(
    jsonb_set(
        jsonb_set(
            jsonb_set(
                trailing_stop_state,
                '{peak_price}', to_jsonb(0.80::decimal)
            ),
            '{peak_timestamp}', to_jsonb(NOW())
        ),
        '{current_stop_price}', to_jsonb(0.776::decimal)
    ),
    '{current_distance}', to_jsonb(0.03::decimal)
),
updated_at = NOW()
WHERE position_id = 123
  AND 0.80 > (trailing_stop_state->>'peak_price')::decimal;
```

**Check for Exit Trigger:**
```sql
SELECT
    position_id,
    current_price,
    (trailing_stop_state->>'current_stop_price')::decimal as stop_price
FROM positions
WHERE trailing_stop_state->>'active' = 'true'
  AND current_price < (trailing_stop_state->>'current_stop_price')::decimal;
-- If returns rows, trigger trailing_stop exit
```

---

## Complete Examples

### Example 1: Small Winner (+15%)

**Configuration:**
- Entry: $0.60
- Activation: +10%
- Initial Distance: 5%
- Tightening: 1% per $0.10
- Floor: 2%

**Price Path:**

| Time | Price | Status | Peak | Distance | Stop | Notes |
|------|-------|--------|------|----------|------|-------|
| 10:00 | $0.60 | Entry | - | - | - | Position opened |
| 10:15 | $0.64 | Monitoring | - | - | - | Not yet +10% |
| 10:30 | $0.66 | **ACTIVATED** | $0.66 | 5% | $0.627 | Trailing stop ON |
| 10:45 | $0.68 | Active | $0.68 | 5% | $0.646 | New peak, stop adjusts |
| 11:00 | $0.69 | Active | $0.69 | 5% | $0.6555 | New peak |
| 11:15 | $0.67 | Active | $0.69 | 5% | $0.6555 | Below peak, stop unchanged |
| 11:30 | $0.65 | Active | $0.69 | 5% | $0.6555 | Further down |
| 11:45 | $0.655 | **EXIT** | $0.69 | 5% | $0.6555 | Below stop → Exit |

**Result:**
- Entry: $0.60
- Exit: $0.655
- Profit: $0.055 (+9.2%)
- Peak Reached: $0.69 (+15%)
- Giveback: $0.035 (5% of peak)

**Analysis:** Captured most of the +15% move, gave back 5% on the reversal.

---

### Example 2: Big Winner (+50%)

**Configuration:** Same as Example 1

**Price Path:**

| Time | Price | Status | Peak | Distance | Stop | Gain from Entry |
|------|-------|--------|------|----------|------|-----------------|
| 10:00 | $0.60 | Entry | - | - | - | $0.00 |
| 11:00 | $0.66 | **ACTIVATED** | $0.66 | 5% | $0.627 | $0.06 |
| 12:00 | $0.72 | Active | $0.72 | 4% | $0.6912 | $0.12 (+20%) |
| 13:00 | $0.78 | Active | $0.78 | 3% | $0.7566 | $0.18 (+30%) |
| 14:00 | $0.84 | Active | $0.84 | 2% | $0.8232 | $0.24 (+40%) |
| 15:00 | $0.90 | Active | $0.90 | 2% | $0.882 | $0.30 (+50%) |
| 15:15 | $0.88 | Active | $0.90 | 2% | $0.882 | $0.30 |
| 15:30 | $0.881 | **EXIT** | $0.90 | 2% | $0.882 | $0.30 |

**Result:**
- Entry: $0.60
- Exit: $0.882 (executed at stop)
- Profit: $0.282 (+47%)
- Peak Reached: $0.90 (+50%)
- Giveback: $0.018 (2% of peak, 3% of entry)

**Analysis:** Tightening protected gains - only gave back 2% despite 50% peak!

---

### Example 3: False Breakout

**Configuration:** Same as Example 1

**Price Path:**

| Time | Price | Status | Peak | Distance | Stop | Notes |
|------|-------|--------|------|----------|------|-------|
| 10:00 | $0.60 | Entry | - | - | - | Position opened |
| 10:30 | $0.66 | **ACTIVATED** | $0.66 | 5% | $0.627 | Trailing stop ON |
| 10:45 | $0.70 | Active | $0.70 | 5% | $0.665 | Climbing |
| 11:00 | $0.68 | Active | $0.70 | 5% | $0.665 | Pullback |
| 11:15 | $0.66 | Active | $0.70 | 5% | $0.665 | Further down |
| 11:30 | $0.664 | **EXIT** | $0.70 | 5% | $0.665 | Stop hit |

**Result:**
- Entry: $0.60
- Exit: $0.665
- Profit: $0.065 (+10.8%)
- Peak Reached: $0.70 (+16.7%)
- Giveback: $0.035 (5% of peak)

**Analysis:** Trailing stop protected profits during false breakout. Without it, could have given back entire gain if price returned to entry.

---

### Example 4: Never Activates

**Configuration:** Same as Example 1

**Price Path:**

| Time | Price | Status | Notes |
|------|-------|--------|-------|
| 10:00 | $0.60 | Entry | Position opened |
| 10:30 | $0.64 | Monitoring | +6.7%, not yet +10% |
| 11:00 | $0.65 | Monitoring | +8.3%, still not +10% |
| 11:30 | $0.63 | Monitoring | +5%, dropping |
| 12:00 | $0.58 | Monitoring | -3.3%, never activated |
| 12:30 | $0.51 | **EXIT** | Stop loss hit at -15% |

**Result:**
- Entry: $0.60
- Exit: $0.51
- Loss: -$0.09 (-15%)
- Trailing Stop: Never activated (didn't reach +10%)

**Analysis:** Trailing stop is NOT a substitute for stop loss. Regular stop loss protected capital when trade went against us.

---

## Database Schema

### Complete Schema with Trailing Stops

```sql
-- positions table with trailing stop support
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    trade_id INT REFERENCES trades(trade_id),
    game_id INT REFERENCES games(game_id),

    -- Entry Details
    entry_price DECIMAL(10,4) NOT NULL,
    entry_timestamp TIMESTAMP NOT NULL,
    quantity INT NOT NULL,

    -- Current State
    current_price DECIMAL(10,4),
    unrealized_pnl DECIMAL(10,4),
    unrealized_pnl_pct DECIMAL(6,4),
    last_update TIMESTAMP,

    -- Trailing Stop State (JSONB)
    trailing_stop_state JSONB,

    -- Exit Details
    exit_price DECIMAL(10,4),
    exit_timestamp TIMESTAMP,
    exit_reason VARCHAR(50),
    exit_priority VARCHAR(20),
    realized_pnl DECIMAL(10,4),

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE
);

-- Indexes for trailing stop queries
CREATE INDEX idx_positions_trailing_stop_active
ON positions ((trailing_stop_state->>'active'))
WHERE trailing_stop_state->>'active' = 'true';

CREATE INDEX idx_positions_stop_price
ON positions (((trailing_stop_state->>'current_stop_price')::decimal))
WHERE trailing_stop_state->>'active' = 'true';

CREATE INDEX idx_positions_last_update
ON positions (last_update)
WHERE row_current_ind = TRUE;

-- Query active trailing stops needing evaluation
CREATE OR REPLACE VIEW active_trailing_stops AS
SELECT
    position_id,
    entry_price,
    current_price,
    (trailing_stop_state->>'peak_price')::decimal as peak_price,
    (trailing_stop_state->>'current_stop_price')::decimal as stop_price,
    (trailing_stop_state->>'current_distance')::decimal as distance,
    trailing_stop_state->>'activated_at' as activated_at,
    last_update
FROM positions
WHERE row_current_ind = TRUE
  AND trailing_stop_state->>'active' = 'true'
  AND exit_price IS NULL;
```

---

## Implementation Details

### Monitoring Loop (Pseudo-code)

```python
def monitor_trailing_stops():
    """Check all active trailing stops every monitoring cycle"""

    # Get all open positions with trailing stops
    positions = get_positions_with_trailing_stops()

    for position in positions:
        # Get current market price
        current_price = get_market_price(position.game_id)

        # Update position current_price
        update_position_price(position.position_id, current_price)

        # Check if trailing stop should activate
        if not position.trailing_stop_active:
            check_activation(position, current_price)
            continue  # Don't evaluate until activated

        # Trailing stop is active, check for updates
        state = position.trailing_stop_state

        # Check if new peak
        if current_price > state['peak_price']:
            update_trailing_stop_peak(position, current_price)

        # Check if stop price hit
        if current_price < state['current_stop_price']:
            trigger_trailing_stop_exit(position, current_price)


def check_activation(position, current_price):
    """Check if trailing stop should activate"""
    config = load_config('position_management.yaml')

    unrealized_pnl_pct = (current_price - position.entry_price) / position.entry_price

    if unrealized_pnl_pct >= config.trailing_stop.activation_threshold:
        activate_trailing_stop(position, current_price, config)


def activate_trailing_stop(position, current_price, config):
    """Activate trailing stop for position"""
    initial_distance = config.trailing_stop.initial_distance
    stop_price = current_price * (1 - initial_distance)

    state = {
        'active': True,
        'activated_at': now(),
        'activation_price': current_price,
        'peak_price': current_price,
        'peak_timestamp': now(),
        'current_stop_price': stop_price,
        'current_distance': initial_distance,
        'entry_price': position.entry_price,
        'total_gain': current_price - position.entry_price,
        'config_snapshot': {
            'activation_threshold': config.trailing_stop.activation_threshold,
            'initial_distance': config.trailing_stop.initial_distance,
            'tightening_rate': config.trailing_stop.tightening_rate,
            'floor_distance': config.trailing_stop.floor_distance
        }
    }

    update_position_trailing_stop_state(position.position_id, state)
    log_event('trailing_stop_activated', position.position_id, state)


def update_trailing_stop_peak(position, new_peak):
    """Update peak price and recalculate stop price with tightening"""
    state = position.trailing_stop_state
    config = state['config_snapshot']

    # Calculate new distance with tightening
    total_gain = new_peak - state['entry_price']
    gain_increments = total_gain / 0.10
    distance_reduction = config['tightening_rate'] * gain_increments

    new_distance = max(
        config['initial_distance'] - distance_reduction,
        config['floor_distance']
    )

    # Calculate new stop price
    new_stop_price = new_peak * (1 - new_distance)

    # Update state
    state['peak_price'] = new_peak
    state['peak_timestamp'] = now()
    state['current_stop_price'] = new_stop_price
    state['current_distance'] = new_distance
    state['total_gain'] = total_gain

    update_position_trailing_stop_state(position.position_id, state)
    log_event('trailing_stop_peak_updated', position.position_id, state)


def trigger_trailing_stop_exit(position, current_price):
    """Trigger exit when stop price hit"""
    state = position.trailing_stop_state

    # Create exit order
    exit_order = create_exit_order(
        position=position,
        exit_reason='trailing_stop',
        exit_priority='HIGH',
        trigger_price=current_price,
        stop_price=state['current_stop_price']
    )

    log_event('trailing_stop_triggered', position.position_id, {
        'current_price': current_price,
        'stop_price': state['current_stop_price'],
        'peak_price': state['peak_price'],
        'exit_order_id': exit_order.order_id
    })

    # Execute exit with HIGH priority (aggressive limit orders, price walking)
    execute_exit(exit_order)
```

---

## When to Use Trailing Stops

### ✅ Ideal Scenarios

**1. Trending Markets**
```
NFL game: Team up 14-0 at halftime, continuing to dominate

Price: $0.60 → $0.70 → $0.80 → $0.90

Trailing stop captures trend, exits on reversal.
```

**2. High Confidence Trades**
```
Edge: 12% (very high)
Expected: Position should move strongly in your favor

Use trailing stop to maximize upside while protecting gains.
```

**3. Long Time Horizon**
```
Entry: 2 hours before game ends
Time for price to trend up significantly

Trailing stop lets position run while protecting profits.
```

**4. Low Volatility Predictions**
```
Heavy favorite (90% probability)
Price should steadily increase toward $0.99

Trailing stop captures steady appreciation.
```

**5. Uncertain Exit Timing**
```
Not sure when to take profits (15%? 25%? 50%?)

Let trailing stop decide based on price action.
```

---

## When NOT to Use Trailing Stops

### ❌ Problematic Scenarios

**1. Choppy Markets**
```
Price: $0.65 → $0.70 → $0.65 → $0.72 → $0.66 → $0.68

Stop activates at $0.70, immediately hit by chop → premature exit.

Problem: Whipsawed out of position.
Solution: Use fixed profit target instead.
```

**2. Low Confidence Trades**
```
Edge: 3% (marginal)
Expected: Small gains, high volatility

Trailing stop likely to get stopped out prematurely.
Solution: Use fixed profit target (10-15%).
```

**3. Short Time Horizon**
```
Entry: 10 minutes before game ends
Not enough time to activate trailing stop

Solution: Use profit target or let ride to settlement.
```

**4. High Volatility Predictions**
```
Close game, score swings wildly
Price: $0.60 → $0.75 → $0.55 → $0.80

Trailing stop activates at $0.75, immediately hit by swing → exit at $0.71.
Price then goes to $0.80.

Problem: Stopped out by volatility.
Solution: Use wider initial_distance or fixed targets.
```

**5. Settlement Arbitrage**
```
Game ended, waiting for settlement
Price: $0.98 (should go to $0.99 or $1.00)

Trailing stop unnecessary - outcome known.
Solution: Hold for settlement or use profit target.
```

---

## Configuration Tuning

### Conservative Configuration (Tight Stops)

**Goal:** Protect profits aggressively, accept more frequent exits

```yaml
trailing_stop:
  activation_threshold: 0.08  # Activate earlier (8%)
  initial_distance: 0.03      # Tighter initial stop (3%)
  tightening_rate: 0.015      # Tighten faster (1.5% per $0.10)
  floor_distance: 0.015       # Tighter floor (1.5%)
```

**Characteristics:**
- ✅ Protects profits early
- ✅ Minimal giveback (1.5-3%)
- ❌ More frequent exits
- ❌ May exit prematurely on volatility

**Best For:**
- Low volatility markets
- Risk-averse trading
- Small account sizes

### Aggressive Configuration (Loose Stops)

**Goal:** Maximize upside, accept more giveback

```yaml
trailing_stop:
  activation_threshold: 0.15  # Activate later (15%)
  initial_distance: 0.08      # Looser initial stop (8%)
  tightening_rate: 0.005      # Tighten slower (0.5% per $0.10)
  floor_distance: 0.04        # Looser floor (4%)
```

**Characteristics:**
- ✅ Captures large moves
- ✅ Fewer premature exits
- ❌ More giveback (4-8%)
- ❌ Less protection on reversals

**Best For:**
- High volatility markets
- High confidence trades
- Trending markets

### Balanced Configuration (Default)

**Goal:** Balance protection and upside

```yaml
trailing_stop:
  activation_threshold: 0.10  # Activate at 10%
  initial_distance: 0.05      # 5% initial stop
  tightening_rate: 0.01       # 1% per $0.10
  floor_distance: 0.02        # 2% floor
```

**Best For:** Most scenarios

---

## Common Scenarios

### Scenario 1: "Why didn't my trailing stop activate?"

**Symptoms:**
```
Entry: $0.60
Current Price: $0.68 (+13.3%)
Trailing Stop: Still inactive
```

**Diagnosis:**
Check activation_threshold:
```yaml
activation_threshold: 0.15  # 15% required
```

Current profit: 13.3% < 15% → Not activated yet

**Solution:** Wait for 15% profit or reduce activation_threshold.

---

### Scenario 2: "Trailing stop exited too early"

**Symptoms:**
```
Entry: $0.60
Exit: $0.665 (trailing stop)
Current Price: $0.85 (+41%)
Missed: $0.185 additional profit
```

**Diagnosis:**
Choppy market + tight initial_distance:
```yaml
initial_distance: 0.03  # 3% (too tight)
```

Price path: $0.60 → $0.68 (activate) → $0.66 (stop hit) → $0.85

**Solution:**
- Increase initial_distance to 5-8%
- Or disable trailing stop for choppy markets
- Or wait for higher activation threshold

---

### Scenario 3: "Trailing stop gave back too much profit"

**Symptoms:**
```
Entry: $0.60
Peak: $0.90 (+50%)
Exit: $0.828 (trailing stop)
Giveback: $0.072 (8% of peak, 12% of entry)
```

**Diagnosis:**
Loose configuration:
```yaml
initial_distance: 0.08  # 8% (too loose)
floor_distance: 0.05    # 5% floor (too loose)
```

**Solution:**
- Tighten initial_distance to 5%
- Reduce floor_distance to 2%
- Increase tightening_rate to 1.5%

---

### Scenario 4: "Trailing stop not tightening"

**Symptoms:**
```
Entry: $0.60
Peak: $0.90 (+50%)
Distance: Still 5% (not tightening)
```

**Diagnosis:**
Check tightening_rate:
```yaml
tightening_rate: 0.00  # Disabled!
```

**Solution:** Enable tightening:
```yaml
tightening_rate: 0.01  # 1% per $0.10 gain
```

---

## Best Practices

### DO ✅

1. **Enable for High Confidence Trades**
   ```yaml
   # High edge (8%+) trades
   trailing_stop:
     enabled: true
   ```

2. **Use Progressive Tightening**
   ```yaml
   tightening_rate: 0.01  # Tighten as profits grow
   floor_distance: 0.02   # Cap at 2%
   ```

3. **Set Activation Above Noise**
   ```yaml
   activation_threshold: 0.10  # Wait for 10% profit
   # Avoids activating on minor price fluctuations
   ```

4. **Configure Per Sport**
   ```yaml
   # NFL (lower volatility)
   activation_threshold: 0.10
   initial_distance: 0.05

   # NBA (higher volatility)
   activation_threshold: 0.12
   initial_distance: 0.06
   ```

5. **Monitor Performance**
   ```sql
   -- Analyze trailing stop exits
   SELECT
       COUNT(*) as exits,
       AVG(realized_pnl_pct) as avg_profit,
       AVG((peak_price - exit_price) / entry_price) as avg_giveback
   FROM positions
   WHERE exit_reason = 'trailing_stop';
   ```

### DON'T ❌

1. **Don't Set Activation Too Low**
   ```yaml
   activation_threshold: 0.02  # ❌ Too low, will activate on noise
   ```

2. **Don't Use Zero Tightening**
   ```yaml
   tightening_rate: 0.00  # ❌ Misses key benefit
   ```

3. **Don't Use Trailing Stop Alone**
   ```yaml
   # ❌ Missing stop loss protection
   trailing_stop: {enabled: true}
   stop_loss: {enabled: false}

   # ✅ Use both
   trailing_stop: {enabled: true}
   stop_loss: {enabled: true}
   ```

4. **Don't Use in Settlement Arb**
   ```yaml
   # Settlement arb (outcome known)
   # ❌ Trailing stop unnecessary
   trailing_stop: {enabled: true}

   # ✅ Hold for settlement
   trailing_stop: {enabled: false}
   ```

5. **Don't Ignore Volatility**
   ```
   High volatility market → Wider initial_distance
   Low volatility market → Tighter initial_distance
   ```

---

## Troubleshooting

### Issue: Trailing Stop Not Activating

**Check:**
1. Is trailing_stop.enabled = true?
2. Has position reached activation_threshold?
3. Is current_price being updated?

```sql
-- Debug query
SELECT
    position_id,
    entry_price,
    current_price,
    (current_price - entry_price) / entry_price as unrealized_pnl_pct,
    trailing_stop_state->>'active' as is_active,
    0.10 as activation_threshold
FROM positions
WHERE position_id = 123;
```

### Issue: Trailing Stop Not Updating

**Check:**
1. Is monitoring loop running?
2. Is last_update timestamp recent?
3. Is JSONB update query correct?

```sql
-- Check last update
SELECT
    position_id,
    last_update,
    NOW() - last_update as time_since_update
FROM positions
WHERE trailing_stop_state->>'active' = 'true';

-- Should be < 30 seconds (or configured normal_frequency)
```

### Issue: Exit Not Triggering

**Check:**
1. Is current_price below stop_price?
2. Is exit execution working?

```sql
-- Check positions below stop
SELECT
    position_id,
    current_price,
    (trailing_stop_state->>'current_stop_price')::decimal as stop_price,
    current_price - (trailing_stop_state->>'current_stop_price')::decimal as distance_below
FROM positions
WHERE trailing_stop_state->>'active' = 'true'
  AND current_price < (trailing_stop_state->>'current_stop_price')::decimal;

-- Should trigger exits for these positions
```

---

## Summary

**Trailing stops are powerful tools for:**
- ✅ Maximizing profits on winning trades
- ✅ Protecting against reversals
- ✅ Automating exit decisions
- ✅ Riding trends while managing risk

**Key takeaways:**
1. Activate after reaching profit threshold (default 10%)
2. Start with reasonable distance (5%)
3. Tighten progressively as profits grow (1% per $0.10)
4. Cap tightening with floor (2% minimum)
5. Store state in JSONB for flexibility
6. Monitor and tune based on performance

**Configuration matters:**
- Conservative: Tight stops, early activation
- Balanced: Default settings work well
- Aggressive: Loose stops, late activation

**Always combine with:**
- Stop loss (downside protection)
- Position sizing (Kelly criterion)
- Trade strategy (entry rules)

---

**Document:** TRAILING_STOP_GUIDE.md
**Version:** 1.0
**Created:** 2025-10-21
**Last Updated:** 2025-10-21
**Status:** ✅ Complete and validated
