# Position Manager User Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Target Audience:** Developers implementing position tracking and management for Precog
**Purpose:** Comprehensive guide to using Position Manager for opening, updating, and closing positions
**Related Guides:** STRATEGY_MANAGER_USER_GUIDE_V1.0.md, MODEL_MANAGER_USER_GUIDE_V1.0.md, KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md, TRAILING_STOP_GUIDE_V1.0.md

---

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Quick Start](#quick-start)
4. [Complete API Reference](#complete-api-reference)
5. [Position Lifecycle](#position-lifecycle)
6. [P&L Calculation](#pnl-calculation)
7. [Trailing Stops](#trailing-stops)
8. [Margin Management](#margin-management)
9. [SCD Type 2 Versioning](#scd-type-2-versioning)
10. [Common Patterns](#common-patterns)
11. [Troubleshooting](#troubleshooting)
12. [Advanced Topics](#advanced-topics)
13. [References](#references)

---

## Overview

### What is Position Manager?

**Position Manager** is the core service for managing trading positions in Precog. It handles opening positions, tracking price updates, calculating P&L, managing trailing stops, and closing positions.

**File:** `src/precog/trading/position_manager.py` (1163 lines)

### Why Use Position Manager?

**Problem Without Position Manager:**
```python
# ❌ WRONG: Direct database manipulation
cursor.execute("""
    INSERT INTO positions (market_id, side, entry_price, quantity)
    VALUES ('MARKET-123', 'YES', 0.75, 10)
""")
# Problems:
# - Floats instead of Decimal (violates Pattern 1)
# - No margin validation (might exceed available funds)
# - No trade attribution (which strategy/model?)
# - No P&L calculation
# - No trailing stop support
# - No SCD Type 2 versioning (price history lost)
```

**Solution With Position Manager:**
```python
# ✅ CORRECT: Managed position lifecycle
from precog.trading.position_manager import PositionManager
from decimal import Decimal

manager = PositionManager()

position = manager.open_position(
    market_id="MARKET-123",
    strategy_id=42,
    model_id=7,
    side="YES",
    quantity=10,
    entry_price=Decimal("0.75"),
    available_margin=Decimal("1000.00"),
    target_price=Decimal("0.85"),
    stop_loss_price=Decimal("0.65")
)
# Benefits:
# - Decimal precision enforced ✅
# - Margin validation (required margin vs available) ✅
# - Trade attribution (strategy_id + model_id) ✅
# - P&L calculated automatically ✅
# - Trailing stops supported ✅
# - SCD Type 2 versioning (price history preserved) ✅
```

### Key Features

1. **Position Lifecycle** - Open → Update → Close (with status tracking)
2. **P&L Calculation** - Automatic unrealized/realized P&L (different for YES vs NO)
3. **Margin Management** - Validates required margin vs available margin
4. **Trade Attribution** - Every position links to strategy_id + model_id
5. **Trailing Stops** - Dynamic stop-loss that follows price (JSONB state)
6. **SCD Type 2 Versioning** - Price updates create new version (history preserved)
7. **YES/NO Position Support** - Handles Kalshi binary market structure
8. **Decimal Precision** - All prices/P&L use `Decimal` type (Pattern 1)
9. **Type Safety** - TypedDict return types with compile-time checking

---

## Core Concepts

### 1. YES vs NO Positions

**CRITICAL:** Kalshi uses binary outcomes (YES or NO), not traditional long/short.

**positions.side Field:**
- `'YES'` = Betting event WILL occur (team wins, price goes UP)
- `'NO'` = Betting event WON'T occur (team loses, price goes DOWN)

**NOT the same as:**
- BUY/SELL (that's `trades.side` - the action you took)
- Long/Short (traditional stock terminology)

**P&L Calculation Differs:**
```python
# YES position: Profit if price goes UP
if side == "YES":
    pnl = quantity * (current_price - entry_price)

# NO position: Profit if price goes DOWN
else:  # NO
    pnl = quantity * (entry_price - current_price)
```

**See:** `docs/guides/KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md` for complete explanation.

---

### 2. SCD Type 2 Versioning

**What is SCD Type 2?**

**Slowly Changing Dimension Type 2** = Every price update creates a NEW database row (immutable history).

**Example:**
```python
# Initial position
position = manager.open_position(
    market_id="MARKET-123",
    side="YES",
    entry_price=Decimal("0.50"),
    quantity=10
)
# Database row: id=123, position_id='POS-100', current_price=0.50, row_current_ind=TRUE

# Price update to $0.55
updated = manager.update_position(
    position_id=123,  # Uses id (surrogate key), not position_id!
    current_price=Decimal("0.55")
)
# Old row: id=123, position_id='POS-100', current_price=0.50, row_current_ind=FALSE (archived)
# New row: id=456, position_id='POS-100', current_price=0.55, row_current_ind=TRUE (current)

# ⚠️ CRITICAL: updated['id'] = 456 (NEW id!)
# You MUST use new id for subsequent operations!
```

**Why SCD Type 2?**

1. **Audit Trail:** See exact price at every point in time
2. **Backtesting:** Reconstruct P&L evolution
3. **Debugging:** "Why did position close at this price?"
4. **Compliance:** Regulatory requirement for trade reconstruction

**See:** Section "SCD Type 2 Versioning" below for complete details.

---

### 3. Dual-Key Schema Pattern

**Two IDs per position:**

1. **id (Surrogate Key):**
   - Auto-increment integer (primary key)
   - Changes with EVERY SCD Type 2 version
   - Used for database operations

2. **position_id (Business Key):**
   - Human-readable string (e.g., 'POS-100')
   - STAYS THE SAME across all versions
   - Used for user communication

**Example:**
```python
# Open position
position = manager.open_position(...)
print(f"Position ID: {position['position_id']}")  # POS-100
print(f"Database ID: {position['id']}")            # 123

# Update position
updated = manager.update_position(
    position_id=position['id'],  # Use database id (123)
    current_price=Decimal("0.55")
)
print(f"Position ID: {updated['position_id']}")  # POS-100 (SAME)
print(f"Database ID: {updated['id']}")            # 456 (DIFFERENT!)

# IMPORTANT: Use NEW id for next operation
updated_again = manager.update_position(
    position_id=updated['id'],  # 456, not 123!
    current_price=Decimal("0.60")
)
```

---

### 4. Margin Calculation (Kalshi Binary Markets)

**Required Margin Formula:**

```python
# YES position: You pay (1.00 - entry_price) per contract
if side == "YES":
    required_margin = quantity * (Decimal("1.00") - entry_price)

# NO position: You pay entry_price per contract
else:  # NO
    required_margin = quantity * entry_price
```

**Why Different?**

Kalshi contracts pay **$1.00** if event occurs, **$0.00** if it doesn't.

**YES Contract:**
- Buy YES @ $0.75
- If YES wins → Get $1.00 → Profit = $1.00 - $0.75 = $0.25
- If YES loses → Get $0.00 → Loss = $0.75
- **Max loss = $0.75** → Need margin of $0.75 per contract
- Actually, you pay $(1.00 - 0.75) = $0.25 upfront (max loss if NO wins)

**NO Contract:**
- Buy NO @ $0.75
- If NO wins → Get $1.00 → Profit = $1.00 - $0.75 = $0.25
- If NO loses → Get $0.00 → Loss = $0.75
- **Max loss = $0.75** → Need margin of $0.75 per contract

**Example:**
```python
# YES position @ $0.75, quantity 10
required_margin = 10 * (1.00 - 0.75) = 10 * 0.25 = $2.50

# NO position @ $0.75, quantity 10
required_margin = 10 * 0.75 = $7.50

# Why different? YES contracts are "cheaper" when market price is high
# If market thinks event is 75% likely (price = $0.75):
# - YES contracts cost more ($0.75 each) but require less margin ($0.25 each)
# - NO contracts cost less ($0.25 each via 1.00-0.75) but require more margin ($0.75 each)
```

---

### 5. Position Status Lifecycle

**Status Values:**
- **open**: Position is active (tracking price updates)
- **closed**: Position manually closed (via close_position)
- **settled**: Market settled (event occurred or didn't)

**Transitions:**
```
open → closed  (manual close)
open → settled (market settlement)

# Note: settled is terminal (cannot reopen)
```

**Querying by Status:**
```python
# Get all open positions
open_positions = manager.get_open_positions()

# Get specific position
position = manager.get_position(position_id=123)
if position['status'] == 'open':
    print("Position is active")
```

---

## Quick Start

### Installation

```python
from precog.trading.position_manager import PositionManager
from precog.database.connection import get_connection, release_connection
from decimal import Decimal
```

### Open Your First Position

```python
# 1. Initialize manager
manager = PositionManager()

# 2. Open YES position (betting team WILL win)
position = manager.open_position(
    market_id="KALSHI-NFL-49ERS-WIN-001",
    strategy_id=42,    # Which strategy?
    model_id=7,         # Which model predicted this?
    side="YES",         # Betting 49ers WILL win
    quantity=10,        # 10 contracts
    entry_price=Decimal("0.75"),         # Bought at $0.75
    available_margin=Decimal("1000.00"),  # We have $1000 available
    target_price=Decimal("0.85"),         # Take profit at $0.85
    stop_loss_price=Decimal("0.65")       # Stop loss at $0.65
)

print(f"Opened position: {position['position_id']}")
print(f"Entry price: ${position['entry_price']}")
print(f"Required margin: ${position['required_margin']}")
print(f"Status: {position['status']}")
```

**Output:**
```
Opened position: POS-100
Entry price: $0.75
Required margin: $2.50
Status: open
```

### Update Position Price

```python
# 3. Price moves to $0.80 (favorable for YES position)
updated = manager.update_position(
    position_id=position['id'],  # Use database id
    current_price=Decimal("0.80")
)

print(f"Current price: ${updated['current_price']}")
print(f"Unrealized P&L: ${updated['unrealized_pnl']}")
```

**Output:**
```
Current price: $0.80
Unrealized P&L: $0.50
```

### Close Position

```python
# 4. Take profit at $0.85
closed = manager.close_position(
    position_id=updated['id'],  # Use NEW id from update!
    exit_price=Decimal("0.85"),
    exit_reason="profit_target"
)

print(f"Exit price: ${closed['exit_price']}")
print(f"Realized P&L: ${closed['realized_pnl']}")
print(f"Status: {closed['status']}")
```

**Output:**
```
Exit price: $0.85
Realized P&L: $1.00
Status: closed
```

---

## Complete API Reference

### Method 1: `open_position()`

**Open new position with margin validation and trade attribution.**

```python
def open_position(
    self,
    market_id: str,
    strategy_id: int,
    model_id: int,
    side: str,
    quantity: int,
    entry_price: Decimal,
    available_margin: Decimal,
    target_price: Decimal | None = None,
    stop_loss_price: Decimal | None = None,
    trailing_stop_config: dict[str, Any] | None = None,
    position_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

**Parameters:**
- `market_id` (str): Market identifier (e.g., 'KALSHI-NFL-49ERS-WIN-001')
- `strategy_id` (int): FK to strategies table (trade attribution)
- `model_id` (int): FK to probability_models table (trade attribution)
- `side` (str): 'YES' or 'NO' (which outcome you're betting on)
- `quantity` (int): Number of contracts (must be positive)
- `entry_price` (Decimal): Entry price per contract ($0.00-$1.00)
- `available_margin` (Decimal): Available funds for margin requirement
- `target_price` (Decimal | None): Take-profit price (optional)
- `stop_loss_price` (Decimal | None): Stop-loss price (optional)
- `trailing_stop_config` (dict | None): Trailing stop configuration (optional)
- `position_metadata` (dict | None): Additional metadata (JSONB, optional)

**Returns:**
- Position dict with all fields including generated `position_id`

**Raises:**
- `InsufficientMarginError`: If `available_margin` < `required_margin`
- `ValueError`: If `side` not in ('YES', 'NO'), quantity <= 0, or entry_price out of range
- `psycopg2.ForeignKeyViolation`: If `market_id`, `strategy_id`, or `model_id` invalid

**Example:**
```python
position = manager.open_position(
    market_id="KALSHI-NFL-49ERS-WIN-001",
    strategy_id=42,
    model_id=7,
    side="YES",
    quantity=10,
    entry_price=Decimal("0.75"),
    available_margin=Decimal("1000.00"),
    target_price=Decimal("0.85"),
    stop_loss_price=Decimal("0.65"),
    trailing_stop_config={
        "activation_price": Decimal("0.80"),
        "trail_distance": Decimal("0.05")
    }
)
```

---

### Method 2: `update_position()`

**Update position price and calculate unrealized P&L.**

**⚠️ CRITICAL: This method creates NEW SCD Type 2 version with DIFFERENT id!**

```python
def update_position(
    self,
    position_id: int,  # Surrogate key (id), NOT business key!
    current_price: Decimal,
) -> dict[str, Any]:
```

**Parameters:**
- `position_id` (int): Database id (surrogate key from previous version)
- `current_price` (Decimal): New market price ($0.00-$1.00)

**Returns:**
- Updated position dict with NEW id (different from input!)

**Raises:**
- `ValueError`: If position not found or status != 'open'

**SCD Type 2 Behavior:**
```python
# Before update
old_position = manager.get_position(position_id=123)
# id=123, position_id='POS-100', current_price=0.50, row_current_ind=TRUE

# Update
new_position = manager.update_position(
    position_id=123,  # Input: old id
    current_price=Decimal("0.55")
)
# id=456, position_id='POS-100', current_price=0.55, row_current_ind=TRUE (NEW!)

# ⚠️ CRITICAL: new_position['id'] != 123!
print(new_position['id'])  # 456 (DIFFERENT!)

# Old version archived in database
# id=123, position_id='POS-100', current_price=0.50, row_current_ind=FALSE
```

**Example:**
```python
# Initial position
position = manager.open_position(...)
current_id = position['id']  # 123

# First update
position = manager.update_position(
    position_id=current_id,  # 123
    current_price=Decimal("0.55")
)
current_id = position['id']  # 456 (NEW!)

# Second update (use NEW id!)
position = manager.update_position(
    position_id=current_id,  # 456, NOT 123!
    current_price=Decimal("0.60")
)
current_id = position['id']  # 789 (ANOTHER NEW id!)
```

---

### Method 3: `close_position()`

**Close position and calculate realized P&L.**

```python
def close_position(
    self,
    position_id: int,
    exit_price: Decimal,
    exit_reason: str,
) -> dict[str, Any]:
```

**Parameters:**
- `position_id` (int): Database id (surrogate key)
- `exit_price` (Decimal): Exit price per contract ($0.00-$1.00)
- `exit_reason` (str): Reason for closing ('profit_target', 'stop_loss', 'trailing_stop', 'manual', etc.)

**Returns:**
- Closed position dict with `realized_pnl` and status='closed'

**Raises:**
- `ValueError`: If position not found or status != 'open'

**Example:**
```python
# Close at profit target
closed = manager.close_position(
    position_id=position['id'],
    exit_price=Decimal("0.85"),
    exit_reason="profit_target"
)

print(f"Realized P&L: ${closed['realized_pnl']}")
print(f"Exit reason: {closed['exit_reason']}")
print(f"Status: {closed['status']}")  # 'closed'
```

---

### Method 4: `get_position()`

**Retrieve current position (row_current_ind = TRUE).**

```python
def get_position(
    self,
    position_id: int,
) -> dict[str, Any] | None:
```

**Parameters:**
- `position_id` (int): Database id (surrogate key)

**Returns:**
- Current position dict if found, None otherwise

**SCD Type 2 Filter:**
```python
# Automatically filters row_current_ind = TRUE
# Only returns CURRENT version, not historical versions
```

**Example:**
```python
position = manager.get_position(position_id=456)

if position:
    print(f"Position: {position['position_id']}")
    print(f"Current price: ${position['current_price']}")
    print(f"Unrealized P&L: ${position['unrealized_pnl']}")
else:
    print("Position not found or not current")
```

---

### Method 5: `get_open_positions()`

**Retrieve all open positions (status='open', row_current_ind=TRUE).**

```python
def get_open_positions(
    self,
    strategy_id: int | None = None,
    market_id: str | None = None,
) -> list[dict[str, Any]]:
```

**Parameters:**
- `strategy_id` (int | None): Filter by strategy (optional)
- `market_id` (str | None): Filter by market (optional)

**Returns:**
- List of open position dicts (may be empty)

**Example:**
```python
# Get all open positions
all_open = manager.get_open_positions()
print(f"Open positions: {len(all_open)}")

# Get open positions for specific strategy
strategy_positions = manager.get_open_positions(strategy_id=42)
for pos in strategy_positions:
    print(f"- {pos['position_id']}: {pos['side']} @ ${pos['current_price']}")

# Get open positions for specific market
market_positions = manager.get_open_positions(
    market_id="KALSHI-NFL-49ERS-WIN-001"
)
```

---

### Method 6: `calculate_position_pnl()`

**Calculate P&L for given prices (utility method).**

```python
def calculate_position_pnl(
    self,
    entry_price: Decimal,
    current_price: Decimal,
    quantity: int,
    side: str,
) -> Decimal:
```

**Parameters:**
- `entry_price` (Decimal): Entry price per contract
- `current_price` (Decimal): Current/exit price per contract
- `quantity` (int): Number of contracts
- `side` (str): 'YES' or 'NO'

**Returns:**
- P&L as Decimal (positive = profit, negative = loss)

**P&L Formula:**
```python
# YES position: Profit if price goes UP
if side == "YES":
    pnl = quantity * (current_price - entry_price)

# NO position: Profit if price goes DOWN
else:
    pnl = quantity * (entry_price - current_price)
```

**Example:**
```python
# YES position
pnl = manager.calculate_position_pnl(
    entry_price=Decimal("0.50"),
    current_price=Decimal("0.75"),
    quantity=10,
    side="YES"
)
print(f"YES P&L: ${pnl}")  # $2.50 (profit)

# NO position
pnl = manager.calculate_position_pnl(
    entry_price=Decimal("0.50"),
    current_price=Decimal("0.25"),
    quantity=10,
    side="NO"
)
print(f"NO P&L: ${pnl}")  # $2.50 (profit)
```

---

## Position Lifecycle

### Complete Lifecycle Example

**Scenario:** Open position, track price updates, hit profit target, close.

```python
from precog.trading.position_manager import PositionManager
from decimal import Decimal

manager = PositionManager()

# ============================================================================
# STEP 1: Open Position
# ============================================================================
print("Step 1: Open YES position @ $0.50")

position = manager.open_position(
    market_id="KALSHI-NFL-49ERS-WIN-001",
    strategy_id=42,
    model_id=7,
    side="YES",
    quantity=10,
    entry_price=Decimal("0.50"),
    available_margin=Decimal("1000.00"),
    target_price=Decimal("0.75"),
    stop_loss_price=Decimal("0.40")
)

print(f"Position ID: {position['position_id']}")
print(f"Database ID: {position['id']}")
print(f"Entry price: ${position['entry_price']}")
print(f"Required margin: ${position['required_margin']}")
print(f"Status: {position['status']}")

# Track current database id
current_id = position['id']

# ============================================================================
# STEP 2: Price Update #1 (price rises to $0.55)
# ============================================================================
print("\nStep 2: Price update to $0.55")

position = manager.update_position(
    position_id=current_id,
    current_price=Decimal("0.55")
)

print(f"Current price: ${position['current_price']}")
print(f"Unrealized P&L: ${position['unrealized_pnl']}")
print(f"Database ID: {position['id']}")  # NEW id!

# Update tracked id
current_id = position['id']

# ============================================================================
# STEP 3: Price Update #2 (price rises to $0.60)
# ============================================================================
print("\nStep 3: Price update to $0.60")

position = manager.update_position(
    position_id=current_id,  # Use NEW id from previous update
    current_price=Decimal("0.60")
)

print(f"Current price: ${position['current_price']}")
print(f"Unrealized P&L: ${position['unrealized_pnl']}")

current_id = position['id']

# ============================================================================
# STEP 4: Price Update #3 (price rises to $0.70)
# ============================================================================
print("\nStep 4: Price update to $0.70")

position = manager.update_position(
    position_id=current_id,
    current_price=Decimal("0.70")
)

print(f"Current price: ${position['current_price']}")
print(f"Unrealized P&L: ${position['unrealized_pnl']}")

current_id = position['id']

# ============================================================================
# STEP 5: Close at Profit Target ($0.75)
# ============================================================================
print("\nStep 5: Close at profit target $0.75")

closed = manager.close_position(
    position_id=current_id,
    exit_price=Decimal("0.75"),
    exit_reason="profit_target"
)

print(f"Exit price: ${closed['exit_price']}")
print(f"Realized P&L: ${closed['realized_pnl']}")
print(f"Exit reason: {closed['exit_reason']}")
print(f"Status: {closed['status']}")

# ============================================================================
# STEP 6: Verify Position Closed
# ============================================================================
print("\nStep 6: Verify position closed")

# Try to update closed position (should fail)
try:
    manager.update_position(
        position_id=closed['id'],
        current_price=Decimal("0.80")
    )
except ValueError as e:
    print(f"✅ Cannot update closed position: {e}")
```

**Output:**
```
Step 1: Open YES position @ $0.50
Position ID: POS-100
Database ID: 123
Entry price: $0.50
Required margin: $5.00
Status: open

Step 2: Price update to $0.55
Current price: $0.55
Unrealized P&L: $0.50
Database ID: 456

Step 3: Price update to $0.60
Current price: $0.60
Unrealized P&L: $1.00

Step 4: Price update to $0.70
Current price: $0.70
Unrealized P&L: $2.00

Step 5: Close at profit target $0.75
Exit price: $0.75
Realized P&L: $2.50
Exit reason: profit_target
Status: closed

Step 6: Verify position closed
✅ Cannot update closed position: Position 789 is not open (status: closed)
```

---

## P&L Calculation

### YES Position P&L

**YES contracts profit when price goes UP.**

**Formula:**
```python
pnl = quantity * (current_price - entry_price)
```

**Example:**
```python
# Buy 10 YES contracts @ $0.50
entry_price = Decimal("0.50")
quantity = 10

# Price rises to $0.75
current_price = Decimal("0.75")

# Calculate P&L
pnl = 10 * (Decimal("0.75") - Decimal("0.50"))
    = 10 * Decimal("0.25")
    = Decimal("2.50")  # $2.50 profit
```

**Why?**
- YES contracts pay $1.00 if event occurs
- If price rises from $0.50 → $0.75, market thinks event MORE likely
- YES contracts become MORE valuable
- Profit = price increase × quantity

---

### NO Position P&L

**NO contracts profit when price goes DOWN.**

**Formula:**
```python
pnl = quantity * (entry_price - current_price)
```

**Example:**
```python
# Buy 10 NO contracts @ $0.50
entry_price = Decimal("0.50")
quantity = 10

# Price falls to $0.25
current_price = Decimal("0.25")

# Calculate P&L
pnl = 10 * (Decimal("0.50") - Decimal("0.25"))
    = 10 * Decimal("0.25")
    = Decimal("2.50")  # $2.50 profit
```

**Why?**
- NO contracts pay $1.00 if event does NOT occur
- If price falls from $0.50 → $0.25, market thinks event LESS likely
- NO contracts become MORE valuable
- Profit = price decrease × quantity

---

### Unrealized vs Realized P&L

**Unrealized P&L:**
- Position is **open**
- P&L calculated using **current_price**
- Changes with every price update
- Not "locked in" yet

**Realized P&L:**
- Position is **closed**
- P&L calculated using **exit_price**
- Final value, won't change
- Actual profit/loss

**Example:**
```python
# Open position
position = manager.open_position(
    side="YES",
    entry_price=Decimal("0.50"),
    quantity=10,
    ...
)

# Price update (unrealized P&L)
position = manager.update_position(
    position_id=position['id'],
    current_price=Decimal("0.70")
)
print(f"Unrealized P&L: ${position['unrealized_pnl']}")  # $2.00 (not final)

# Close position (realized P&L)
closed = manager.close_position(
    position_id=position['id'],
    exit_price=Decimal("0.75"),
    exit_reason="profit_target"
)
print(f"Realized P&L: ${closed['realized_pnl']}")  # $2.50 (final)
```

---

## Trailing Stops

### What is a Trailing Stop?

**Trailing stop** = Stop-loss that "follows" the price, locking in profits.

**Example:**
```
Entry: $0.50
Trailing stop: $0.05 distance

Price rises to $0.70:
- Stop moves to $0.70 - $0.05 = $0.65

Price rises to $0.80:
- Stop moves to $0.80 - $0.05 = $0.75

Price falls to $0.76:
- Stop stays at $0.75 (doesn't move down)

Price falls to $0.74:
- STOP TRIGGERED! Exit at $0.74
- Locked in $0.24 profit (vs $0.00 profit with no trailing stop)
```

### Trailing Stop Configuration

**Config Fields:**
- `activation_price`: Price at which trailing stop activates
- `trail_distance`: Distance to trail behind price
- `current_stop`: Current stop price (tracked in JSONB state)

**Example:**
```python
trailing_stop_config = {
    "activation_price": Decimal("0.60"),  # Activate at $0.60
    "trail_distance": Decimal("0.05")      # Trail $0.05 behind
}

position = manager.open_position(
    side="YES",
    entry_price=Decimal("0.50"),
    quantity=10,
    trailing_stop_config=trailing_stop_config,
    ...
)
```

**Complete Guide:** See `docs/guides/TRAILING_STOP_GUIDE_V1.0.md`

---

## Margin Management

### Required Margin Calculation

**Formula:**
```python
# YES position
required_margin = quantity * (Decimal("1.00") - entry_price)

# NO position
required_margin = quantity * entry_price
```

**Examples:**

**YES Position:**
```python
# YES @ $0.75, quantity 10
required_margin = 10 * (Decimal("1.00") - Decimal("0.75"))
                = 10 * Decimal("0.25")
                = Decimal("2.50")  # $2.50 required
```

**NO Position:**
```python
# NO @ $0.75, quantity 10
required_margin = 10 * Decimal("0.75")
                = Decimal("7.50")  # $7.50 required
```

### Margin Validation

**Position Manager validates margin before opening position:**

```python
try:
    position = manager.open_position(
        side="YES",
        entry_price=Decimal("0.75"),
        quantity=10,
        available_margin=Decimal("2.00"),  # Need $2.50, only have $2.00
        ...
    )
except InsufficientMarginError as e:
    print(f"Margin error: {e}")
    # Output: Required margin $2.50, available $2.00
```

---

## SCD Type 2 Versioning

### How SCD Type 2 Works

**Every price update creates NEW database row:**

```sql
-- Initial position (open)
INSERT INTO positions (
    position_id, market_id, side, entry_price, current_price,
    quantity, status, row_current_ind
) VALUES (
    'POS-100', 'MARKET-123', 'YES', 0.50, 0.50,
    10, 'open', TRUE
);
-- Result: id=123, row_current_ind=TRUE

-- First price update (to $0.55)
-- Step 1: Mark old row as archived
UPDATE positions SET row_current_ind = FALSE WHERE id = 123;

-- Step 2: Insert new row
INSERT INTO positions (
    position_id, market_id, side, entry_price, current_price,
    quantity, status, row_current_ind
) VALUES (
    'POS-100', 'MARKET-123', 'YES', 0.50, 0.55,  -- current_price changed!
    10, 'open', TRUE
);
-- Result: id=456, row_current_ind=TRUE

-- Database now has TWO rows for POS-100:
-- id=123: current_price=0.50, row_current_ind=FALSE (archived)
-- id=456: current_price=0.55, row_current_ind=TRUE (current)
```

### Querying Current vs Historical

**Get Current Position (row_current_ind = TRUE):**
```python
position = manager.get_position(position_id=456)
# Returns: id=456, current_price=0.55, row_current_ind=TRUE
```

**Get Historical Versions (row_current_ind = FALSE):**
```python
# NOT provided by Position Manager (audit queries only)
# Direct SQL for auditing:
cursor.execute("""
    SELECT id, current_price, unrealized_pnl, created_at
    FROM positions
    WHERE position_id = 'POS-100'
    ORDER BY created_at ASC
""")

# Returns ALL versions:
# [(123, 0.50, 0.00, '2025-01-01 10:00:00'),
#  (456, 0.55, 0.50, '2025-01-01 10:05:00'),
#  (789, 0.60, 1.00, '2025-01-01 10:10:00')]
```

### Why Immutable History?

1. **Audit Trail:** "At 10:05 AM, position was worth $0.55 with $0.50 unrealized P&L"
2. **Backtesting:** Reconstruct exact P&L evolution over time
3. **Debugging:** "Why did trailing stop trigger at $0.74?"
4. **Compliance:** Regulatory requirement for trade reconstruction
5. **Performance Analysis:** Compare strategy performance across different price environments

**Example Use Case:**
```
Trader: "My position closed at $0.74, but I thought stop was at $0.75. What happened?"

Developer: "Let me check SCD Type 2 history..."

SELECT id, current_price, trailing_stop_state->>'current_stop', created_at
FROM positions
WHERE position_id = 'POS-100'
ORDER BY created_at DESC
LIMIT 5;

Result:
id=999, price=0.74, stop=0.75, 10:15:03 (stop triggered!)
id=888, price=0.76, stop=0.75, 10:15:02 (stop stayed at 0.75)
id=777, price=0.80, stop=0.75, 10:15:01 (stop moved UP to 0.75)
id=666, price=0.70, stop=0.65, 10:15:00 (stop at 0.65)

Developer: "Stop was at $0.75. Price fell from $0.76 → $0.74, triggering stop at 10:15:03."
```

---

## Common Patterns

### Pattern 1: Track Position in Loop

```python
# Open position
position = manager.open_position(...)
current_id = position['id']

# Simulation loop (price updates)
prices = [
    Decimal("0.55"),
    Decimal("0.60"),
    Decimal("0.65"),
    Decimal("0.70"),
    Decimal("0.75")
]

for price in prices:
    # Update position
    position = manager.update_position(
        position_id=current_id,
        current_price=price
    )

    # Track NEW id
    current_id = position['id']

    print(f"Price: ${price}, P&L: ${position['unrealized_pnl']}")

    # Check profit target
    if position['target_price'] and price >= position['target_price']:
        print("Profit target hit!")
        closed = manager.close_position(
            position_id=current_id,
            exit_price=price,
            exit_reason="profit_target"
        )
        break
```

### Pattern 2: Monitor All Open Positions

```python
def monitor_open_positions(manager: PositionManager) -> dict[str, Any]:
    """
    Monitor all open positions and check exit conditions.

    Returns:
        Summary of open positions and triggered exits
    """
    open_positions = manager.get_open_positions()

    summary = {
        "total_open": len(open_positions),
        "total_unrealized_pnl": Decimal("0.00"),
        "profit_targets_hit": [],
        "stop_losses_hit": []
    }

    for pos in open_positions:
        # Accumulate unrealized P&L
        summary["total_unrealized_pnl"] += pos['unrealized_pnl']

        # Check profit target
        if pos['target_price']:
            if (pos['side'] == 'YES' and pos['current_price'] >= pos['target_price']) or \
               (pos['side'] == 'NO' and pos['current_price'] <= pos['target_price']):
                summary["profit_targets_hit"].append(pos['position_id'])

        # Check stop loss
        if pos['stop_loss_price']:
            if (pos['side'] == 'YES' and pos['current_price'] <= pos['stop_loss_price']) or \
               (pos['side'] == 'NO' and pos['current_price'] >= pos['stop_loss_price']):
                summary["stop_losses_hit"].append(pos['position_id'])

    return summary

# Usage
summary = monitor_open_positions(manager)
print(f"Open positions: {summary['total_open']}")
print(f"Total unrealized P&L: ${summary['total_unrealized_pnl']}")
print(f"Profit targets hit: {summary['profit_targets_hit']}")
print(f"Stop losses hit: {summary['stop_losses_hit']}")
```

### Pattern 3: Calculate Portfolio Exposure

```python
def calculate_portfolio_exposure(manager: PositionManager) -> dict[str, Decimal]:
    """
    Calculate total portfolio exposure (required margin).

    Returns:
        Dict with exposure metrics
    """
    open_positions = manager.get_open_positions()

    exposure = {
        "total_margin_required": Decimal("0.00"),
        "yes_positions": 0,
        "no_positions": 0,
        "total_contracts": 0
    }

    for pos in open_positions:
        exposure["total_margin_required"] += pos['required_margin']
        exposure["total_contracts"] += pos['quantity']

        if pos['side'] == 'YES':
            exposure["yes_positions"] += 1
        else:
            exposure["no_positions"] += 1

    return exposure

# Usage
exposure = calculate_portfolio_exposure(manager)
print(f"Total margin required: ${exposure['total_margin_required']}")
print(f"Total contracts: {exposure['total_contracts']}")
print(f"YES positions: {exposure['yes_positions']}")
print(f"NO positions: {exposure['no_positions']}")
```

### Pattern 4: Close All Positions for Market

```python
def close_all_market_positions(
    manager: PositionManager,
    market_id: str,
    exit_price: Decimal,
    exit_reason: str = "market_close"
) -> list[dict[str, Any]]:
    """
    Close all open positions for a specific market.

    Returns:
        List of closed position dicts
    """
    open_positions = manager.get_open_positions(market_id=market_id)
    closed_positions = []

    for pos in open_positions:
        closed = manager.close_position(
            position_id=pos['id'],
            exit_price=exit_price,
            exit_reason=exit_reason
        )
        closed_positions.append(closed)

    return closed_positions

# Usage: Market settled, close all positions
closed = close_all_market_positions(
    manager=manager,
    market_id="KALSHI-NFL-49ERS-WIN-001",
    exit_price=Decimal("1.00"),  # YES won (settled at $1.00)
    exit_reason="market_settled"
)

print(f"Closed {len(closed)} positions")
for pos in closed:
    print(f"- {pos['position_id']}: {pos['side']} realized P&L ${pos['realized_pnl']}")
```

---

## Troubleshooting

### Error 1: InsufficientMarginError

**Error:**
```python
InsufficientMarginError: Required margin $10.00, available $5.00
```

**Cause:** Not enough funds to open position.

**Solution:**
```python
# Calculate required margin BEFORE opening position
if side == "YES":
    required_margin = quantity * (Decimal("1.00") - entry_price)
else:
    required_margin = quantity * entry_price

print(f"Required margin: ${required_margin}")
print(f"Available margin: ${available_margin}")

if available_margin >= required_margin:
    position = manager.open_position(...)
else:
    print(f"Insufficient margin! Need ${required_margin}, have ${available_margin}")
```

### Error 2: ValueError (Position Not Open)

**Error:**
```python
ValueError: Position 456 is not open (status: closed)
```

**Cause:** Trying to update or close a position that's already closed.

**Solution:**
```python
# Check status before updating
position = manager.get_position(position_id=456)

if position['status'] == 'open':
    updated = manager.update_position(
        position_id=456,
        current_price=Decimal("0.80")
    )
else:
    print(f"Position is {position['status']}, cannot update")
```

### Error 3: Using Wrong ID After Update

**Error:**
```python
ValueError: Position 123 not found
```

**Cause:** Using old id after SCD Type 2 update (id changed!).

**Solution:**
```python
# ❌ WRONG: Reusing old id
position = manager.open_position(...)
old_id = position['id']  # 123

position = manager.update_position(position_id=old_id, current_price=Decimal("0.55"))
# Now position['id'] = 456 (NEW!)

# But you use old_id again...
position = manager.update_position(position_id=old_id, current_price=Decimal("0.60"))
# ERROR! old_id (123) is archived (row_current_ind=FALSE)

# ✅ CORRECT: Track current id
position = manager.open_position(...)
current_id = position['id']

position = manager.update_position(position_id=current_id, current_price=Decimal("0.55"))
current_id = position['id']  # Update to NEW id!

position = manager.update_position(position_id=current_id, current_price=Decimal("0.60"))
current_id = position['id']  # Update again!
```

### Error 4: ValueError (Invalid Side)

**Error:**
```python
ValueError: Invalid side 'BUY', must be 'YES' or 'NO'
```

**Cause:** Confusing `positions.side` ('YES'/'NO') with `trades.side` ('buy'/'sell').

**Solution:**
```python
# ❌ WRONG: Using BUY/SELL for positions
position = manager.open_position(
    side="BUY",  # Wrong! This is trades.side
    ...
)

# ✅ CORRECT: Using YES/NO for positions
position = manager.open_position(
    side="YES",  # Correct! This is positions.side
    ...
)

# See: docs/guides/KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md
```

---

## Advanced Topics

### Position Metadata (JSONB)

**Store additional position data in JSONB field:**

```python
# Open position with metadata
position = manager.open_position(
    market_id="KALSHI-NFL-49ERS-WIN-001",
    side="YES",
    entry_price=Decimal("0.75"),
    quantity=10,
    position_metadata={
        "entry_reason": "Model predicted 80% win probability, market at 75%",
        "model_confidence": Decimal("0.85"),
        "edge": Decimal("0.05"),
        "kelly_fraction": Decimal("0.10"),
        "tags": ["nfl", "49ers", "week_12"]
    },
    ...
)

# Query metadata
print(f"Entry reason: {position['position_metadata']['entry_reason']}")
print(f"Edge: {position['position_metadata']['edge']}")
```

### Position Attribution Chain

**Linking Positions to Strategies and Models:**

```python
# position_id → strategy_id → model_id → exact configs
# Enables: "Which strategy/model generated this position?"

# 1. Create strategy
strategy = strategy_manager.create_strategy(
    strategy_name="value_betting",
    strategy_version="v1.0",
    config={"min_edge": Decimal("0.05")}
)

# 2. Create model
model = model_manager.create_model(
    model_name="elo_nfl",
    model_version="v1.0",
    config={"k_factor": Decimal("32.0")}
)

# 3. Open position (with attribution)
position = position_manager.open_position(
    market_id="MARKET-123",
    strategy_id=strategy['strategy_id'],  # Attribution!
    model_id=model['model_id'],            # Attribution!
    side="YES",
    ...
)

# 4. Later: Look up strategy/model used for this position
strategy_used = strategy_manager.get_strategy(strategy_id=position['strategy_id'])
model_used = model_manager.get_model(model_id=position['model_id'])

print(f"Position {position['position_id']} used:")
print(f"- Strategy: {strategy_used['strategy_name']} {strategy_used['strategy_version']}")
print(f"- Model: {model_used['model_name']} {model_used['model_version']}")
print(f"- Strategy config: {strategy_used['config']}")
print(f"- Model config: {model_used['config']}")
```

### Historical P&L Reconstruction

**Reconstruct P&L evolution using SCD Type 2 history:**

```python
def reconstruct_pnl_history(position_id_business_key: str) -> list[dict]:
    """
    Reconstruct complete P&L history for a position.

    Parameters:
        position_id_business_key: Business key (e.g., 'POS-100')

    Returns:
        List of P&L snapshots ordered by time
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            current_price,
            unrealized_pnl,
            created_at,
            row_current_ind
        FROM positions
        WHERE position_id = %s
        ORDER BY created_at ASC
    """, (position_id_business_key,))

    history = []
    for row in cursor.fetchall():
        history.append({
            "id": row[0],
            "price": row[1],
            "pnl": row[2],
            "timestamp": row[3],
            "current": row[4]
        })

    release_connection(conn)
    return history

# Usage
history = reconstruct_pnl_history("POS-100")

print(f"Position POS-100 P&L History:")
for snapshot in history:
    current_marker = " ← CURRENT" if snapshot['current'] else ""
    print(f"{snapshot['timestamp']}: Price=${snapshot['price']}, "
          f"P&L=${snapshot['pnl']}{current_marker}")
```

---

## References

### Source Code
- **Position Manager:** `src/precog/trading/position_manager.py` (1163 lines)
- **Strategy Manager:** `src/precog/trading/strategy_manager.py`
- **Model Manager:** `src/precog/analytics/model_manager.py`
- **Database Connection:** `src/precog/database/connection.py`

### Documentation
- **Kalshi Market Terminology:** `docs/guides/KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md`
- **Trailing Stop Guide:** `docs/guides/TRAILING_STOP_GUIDE_V1.0.md`
- **Strategy Manager Guide:** `docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.0.md`
- **Model Manager Guide:** `docs/guides/MODEL_MANAGER_USER_GUIDE_V1.0.md`
- **Position Management Guide:** `docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md`
- **Database Schema:** `docs/database/DATABASE_SCHEMA_SUMMARY_V1.11.md`
- **Development Patterns:** `docs/guides/DEVELOPMENT_PATTERNS_V1.6.md`

### Requirements & ADRs
- **REQ-POS-001:** Position Management
- **REQ-POS-002:** Position Lifecycle Tracking
- **REQ-POS-003:** P&L Calculation
- **REQ-POS-004:** Margin Validation
- **ADR-015:** SCD Type 2 for Position History
- **ADR-016:** Position Manager Architecture
- **ADR-089:** Dual-Key Schema Pattern

### Database Tables
- **positions:** Main position storage (SCD Type 2 versioning)
- **trades:** Trade execution records (links to positions)
- **strategies:** Strategy configs (attribution chain)
- **probability_models:** Model configs (attribution chain)

### Related Tools
- **Strategy Manager:** Manages trading strategies (attribution source)
- **Model Manager:** Manages probability models (attribution source)

---

`★ Insight ─────────────────────────────────────`

**Position Manager vs Strategy/Model Managers:**

1. **Different Versioning Pattern:**
   - Strategy/Model: Immutable (frozen configs, new version for changes)
   - Position: SCD Type 2 (mutable prices, history preserved in separate rows)

2. **Why Different?**
   - Strategies/models need frozen configs for A/B testing
   - Positions need price history for audit trail and backtesting
   - SCD Type 2 gives immutable history with mutable "current" view

3. **Attribution Chain:** position → strategy → model → exact configs used

4. **Critical Detail:** SCD Type 2 updates return NEW id. Always track current id!

`─────────────────────────────────────────────────`

---

**END OF POSITION_MANAGER_USER_GUIDE_V1.0.md**
