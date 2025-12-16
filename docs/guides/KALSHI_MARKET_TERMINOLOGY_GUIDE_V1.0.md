# Kalshi Market Terminology Guide

---
**Version:** 1.0
**Created:** 2025-11-22
**Target Audience:** Developers working with Kalshi API and position management
**Purpose:** Clarify terminology differences between Kalshi binary markets and traditional stock markets

---

## The Question: YES/NO vs BUY/SELL?

**Common confusion:** "Why does Position Manager use `side='YES'` instead of `side='BUY'`? Don't we use BUY/SELL for trading?"

**Answer:** Kalshi uses BOTH fields - `side` for the **outcome** and `action` for the **operation**.

---

## Kalshi Binary Market Structure

### Traditional Stock Markets

In traditional stock markets (NASDAQ, NYSE):

```python
{
  "side": "buy",   # Action: buying stock
  "symbol": "AAPL",
  "quantity": 10,
  "price": 150.00
}

# Later, close position:
{
  "side": "sell",  # Action: selling stock
  "symbol": "AAPL",
  "quantity": 10,
  "price": 155.00
}
```

**Simple:** You BUY stock, later SELL stock. Only one "side" field needed (action).

---

### Kalshi Binary Markets

Kalshi markets are **prediction markets** with **binary outcomes** (YES or NO):

**Example Market:** "Will the 49ers win vs Cowboys?"
- **YES contracts** = Pay $1.00 if 49ers win, $0.00 if they lose
- **NO contracts** = Pay $1.00 if 49ers lose, $0.00 if they win

**Two decisions required:**
1. **Which outcome do you believe?** (side = YES or NO)
2. **What are you doing?** (action = buy or sell)

---

## Kalshi API Structure

### Order Placement (from Kalshi API Technical Reference)

```json
POST /trade-api/v2/portfolio/orders
{
  "ticker": "KALSHI-NFL-49ERS-WIN-001",
  "side": "yes",       // ← Which outcome you're betting on
  "action": "buy",     // ← What you're doing (opening position)
  "count": 10,         // Number of contracts
  "yes_price": 75      // Price in cents ($0.75)
}
```

**Fields:**
- **`side`**: `"yes"` or `"no"` - Which outcome you believe will occur
- **`action`**: `"buy"` or `"sell"` - Whether you're opening or closing a position

---

## Our Database Schema

### positions table (line 718 of DATABASE_SCHEMA_SUMMARY_V1.13.md)

```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    side VARCHAR NOT NULL,  -- 'yes', 'no' ← Which outcome you're betting on
    entry_price DECIMAL(10,4) NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR DEFAULT 'open',
    ...
);
```

**positions.side** = `'yes'` or `'no'` (outcome you believe in)

---

### trades table (line 795 of DATABASE_SCHEMA_SUMMARY_V1.13.md)

```sql
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    market_id VARCHAR REFERENCES markets(market_id),
    position_id INT REFERENCES positions(position_id),
    side VARCHAR NOT NULL,  -- 'buy', 'sell' ← Action taken
    price DECIMAL(10,4) NOT NULL,
    quantity INT NOT NULL,
    ...
);
```

**trades.side** = `'buy'` or `'sell'` (action: opening or closing)

---

## Complete Example: Position Lifecycle

### Opening a YES Position

**Scenario:** You think 49ers WILL win, so you bet on YES outcome.

**API Call:**
```json
POST /trade-api/v2/portfolio/orders
{
  "ticker": "KALSHI-NFL-49ERS-WIN-001",
  "side": "yes",       // ← Betting on 49ers to WIN
  "action": "buy",     // ← Opening position (buying contracts)
  "count": 10,
  "yes_price": 75      // $0.75 per contract
}
```

**Position Record:**
```python
{
  "position_id": "POS-100",
  "market_id": "KALSHI-NFL-49ERS-WIN-001",
  "side": "yes",              # ← Outcome: betting 49ers will win
  "entry_price": Decimal("0.75"),
  "quantity": 10,
  "status": "open"
}
```

**Trade Record:**
```python
{
  "trade_id": 1234,
  "position_id": "POS-100",
  "side": "buy",              # ← Action: bought contracts (opened position)
  "price": Decimal("0.75"),
  "quantity": 10
}
```

---

### Closing That Position (Profit Target Hit)

**Scenario:** Price moves to $0.85, you want to take profit.

**API Call:**
```json
POST /trade-api/v2/portfolio/orders
{
  "ticker": "KALSHI-NFL-49ERS-WIN-001",
  "side": "yes",       // ← SAME outcome (still YES contracts)
  "action": "sell",    // ← Closing position (selling contracts)
  "count": 10,
  "yes_price": 85      // $0.85 per contract
}
```

**Position Record (updated):**
```python
{
  "position_id": "POS-100",
  "side": "yes",              # ← UNCHANGED (still YES outcome)
  "entry_price": Decimal("0.75"),
  "quantity": 10,
  "status": "closed",         # ← Status changed
  "exit_price": Decimal("0.85"),
  "realized_pnl": Decimal("1.00")  # ($0.85 - $0.75) * 10 = $1.00 profit
}
```

**Trade Record (NEW record):**
```python
{
  "trade_id": 1235,
  "position_id": "POS-100",
  "side": "sell",             # ← Action: sold contracts (closed position)
  "price": Decimal("0.85"),
  "quantity": 10
}
```

---

## Position Manager Code

### Why Position Manager Uses YES/NO

**File:** `src/precog/trading/position_manager.py`

**Lines 232-233:**
```python
if side not in ("YES", "NO"):
    raise ValueError(f"Invalid side '{side}', must be 'YES' or 'NO'")
```

**Rationale:**

Position Manager deals with **positions** (what you're holding), not **trades** (actions you took).

When you open a position, you need to specify:
- **Which outcome?** YES or NO (position.side)
- **How much?** Quantity and price
- **Which strategy/model?** Trade attribution

The **action** (buy/sell) is handled by the execution layer (Phase 5), not Position Manager.

---

## P&L Calculation Logic

### YES Position P&L

**YES contracts profit when price goes UP:**

```python
# position_manager.py lines 651-654
if side == "YES":
    pnl = quantity * (current_price - entry_price)
else:  # NO
    pnl = quantity * (entry_price - current_price)
```

**Example:**
```python
# YES position
entry_price = Decimal("0.50")  # Bought at $0.50
current_price = Decimal("0.75")  # Price now $0.75
quantity = 10

pnl = 10 * (Decimal("0.75") - Decimal("0.50"))
    = 10 * Decimal("0.25")
    = Decimal("2.50")  # $2.50 profit
```

**Why?** YES contracts pay $1.00 if event occurs. If price rises from $0.50 → $0.75, market thinks event more likely → YES contracts more valuable → profit!

---

### NO Position P&L

**NO contracts profit when price goes DOWN:**

```python
# NO position
entry_price = Decimal("0.50")  # Bought at $0.50
current_price = Decimal("0.25")  # Price now $0.25
quantity = 10

pnl = 10 * (Decimal("0.50") - Decimal("0.25"))
    = 10 * Decimal("0.25")
    = Decimal("2.50")  # $2.50 profit
```

**Why?** NO contracts pay $1.00 if event does NOT occur. If YES price drops from $0.50 → $0.25, market thinks event less likely → NO contracts more valuable → profit!

---

## Terminology Comparison Table

| Concept | Traditional Stock Market | Kalshi Binary Market |
|---------|-------------------------|---------------------|
| **What you're trading** | Shares of stock (e.g., AAPL) | Binary outcome contracts (YES or NO) |
| **Position field** | symbol (e.g., "AAPL") | **side** ('yes' or 'no') |
| **Action field** | side ('buy' or 'sell') | **action** ('buy' or 'sell') |
| **Opening position** | Buy shares | Buy YES or NO contracts |
| **Closing position** | Sell shares | Sell YES or NO contracts |
| **Profit mechanism** | Price goes up (for longs) | Event probability changes (YES up or NO down) |
| **Maximum gain (long)** | Unlimited | $1.00 per contract (binary settlement) |
| **Maximum loss (long)** | Full investment | Full investment (contract goes to $0) |
| **Settlement** | Continuous trading | Binary: $1.00 or $0.00 |

---

## Code Examples

### Opening YES Position (Position Manager)

```python
from precog.trading.position_manager import PositionManager
from decimal import Decimal

manager = PositionManager()

# Open YES position (think 49ers WILL win)
position = manager.open_position(
    market_id="KALSHI-NFL-49ERS-WIN-001",
    strategy_id=42,
    model_id=7,
    side="YES",                     # ← Outcome: betting 49ers will win
    quantity=10,
    entry_price=Decimal("0.75"),
    available_margin=Decimal("1000.00")
)

print(f"Opened {position['side']} position: {position['position_id']}")
# Output: Opened YES position: POS-100
```

---

### Updating Position Price

```python
# Price moves to $0.80 (favorable for YES position)
updated = manager.update_position(
    position_id=position['id'],  # Surrogate key (int)
    current_price=Decimal("0.80")
)

print(f"P&L: ${updated['unrealized_pnl']}")
# Output: P&L: $0.50 (10 contracts * ($0.80 - $0.75))
```

---

### Closing Position (Profit Target)

```python
# Close position at $0.85 (profit target hit)
closed = manager.close_position(
    position_id=position['id'],
    exit_price=Decimal("0.85"),
    exit_reason="profit_target"
)

print(f"Realized P&L: ${closed['realized_pnl']}")
# Output: Realized P&L: $1.00 (10 contracts * ($0.85 - $0.75))
```

**Note:** Position Manager doesn't create trade records - that's done by execution layer (Phase 5).

---

## Case Sensitivity Note

### Code vs Database

**Python Code (Position Manager):**
```python
# Uses UPPERCASE
side="YES"  # or "NO"
```

**Database Schema:**
```sql
-- Uses lowercase
side VARCHAR NOT NULL,  -- 'yes', 'no'
```

**Why Different?**

- **Python convention:** UPPERCASE for constants/enums improves readability
- **Database convention:** lowercase for consistency across systems
- **Conversion:** Code should convert to lowercase before INSERT or use case-insensitive comparison

**Recommendation:** Update Position Manager to use lowercase `"yes"` and `"no"` for consistency with database schema and Kalshi API.

---

## Summary

### Key Takeaways

1. **Kalshi uses BOTH fields:**
   - `side` = outcome (yes/no) - what you believe will happen
   - `action` = operation (buy/sell) - what you're doing

2. **Our schema reflects this:**
   - `positions.side` = 'yes'/'no' (which outcome)
   - `trades.side` = 'buy'/'sell' (what action)

3. **Position Manager is correct:**
   - Uses YES/NO because positions represent **outcomes**, not actions
   - Execution layer (Phase 5) will use BUY/SELL for trade records

4. **No documentation inconsistency:**
   - Both fields are needed for binary prediction markets
   - Terminology follows Kalshi API design

---

## References

### Official Documentation

- **Kalshi API Technical Reference:** `docs/api-integration/Kalshi API Technical Reference For Trading Integration.md`
  - Line 57: Order placement API structure
  - Shows both `side` (yes/no) and `action` (buy/sell) fields

### Database Schema

- **DATABASE_SCHEMA_SUMMARY_V1.13.md:**
  - Line 718: positions.side ('yes', 'no')
  - Line 795: trades.side ('buy', 'sell')

### Source Code

- **Position Manager:** `src/precog/trading/position_manager.py`
  - Lines 232-233: Side validation (YES/NO)
  - Lines 651-654: P&L calculation logic (different for YES vs NO)

### Requirements & ADRs

- **REQ-EXEC-001:** Trade Execution Workflow (positions vs trades)
- **ADR-015:** SCD Type 2 for Position History
- **ADR-089:** Dual-Key Schema Pattern

---

**END OF KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md**
