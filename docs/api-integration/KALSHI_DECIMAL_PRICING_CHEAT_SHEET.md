# Kalshi API Decimal Pricing - Quick Reference
**Critical**: Keep this handy during Phase 1-3 implementation! 📌

---

## ❌ DON'T DO THIS (Deprecated)

```python
# ❌ WRONG - Will break when Kalshi deprecates integer fields
yes_bid = market_data["yes_bid"]  # 43 (integer cents)
yes_bid_dollars = yes_bid / 100    # 0.43

# ❌ WRONG - Integer database column
CREATE TABLE markets (
    yes_bid INTEGER CHECK (yes_bid >= 0 AND yes_bid <= 100)
);
```

---

## ✅ DO THIS (Future-Proof)

```python
# ✅ CORRECT - Uses decimal fields
from decimal import Decimal

yes_bid = Decimal(market_data["yes_bid_dollars"])  # "0.4275"
no_bid = Decimal(market_data["no_bid_dollars"])    # "0.5700"

# ✅ CORRECT - Decimal database column
CREATE TABLE markets (
    yes_bid DECIMAL(10,4) NOT NULL,
    CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999)
);
```

---

## API Response Parsing Cheat Sheet

```python
from decimal import Decimal

def parse_kalshi_market(market_data: dict) -> dict:
    """
    Parse Kalshi market data correctly.
    
    ALWAYS use *_dollars fields, NEVER integer fields.
    """
    return {
        "ticker": market_data["ticker"],
        "yes_bid": Decimal(market_data["yes_bid_dollars"]),
        "yes_ask": Decimal(market_data["yes_ask_dollars"]),
        "no_bid": Decimal(market_data["no_bid_dollars"]),
        "no_ask": Decimal(market_data["no_ask_dollars"]),
        "last_price": Decimal(market_data.get("last_price_dollars", "0")),
        "volume": market_data["volume"],
        "open_interest": market_data["open_interest"]
    }
```

---

## Order Placement Cheat Sheet

```python
# ✅ CORRECT - Use decimal string
order = {
    "ticker": "MARKET-YES",
    "side": "yes",
    "action": "buy",
    "count": 10,
    "yes_price_dollars": "0.4275",  # Decimal string, NOT integer
    "type": "limit"
}

# ❌ WRONG - Don't use integer cents field
order = {
    "yes_price": 43  # DEPRECATED, will break soon
}
```

---

## Database Schema Cheat Sheet

```sql
-- ✅ ALL price/fee columns should be DECIMAL(10,4)
CREATE TABLE markets (
    ticker VARCHAR(100) PRIMARY KEY,
    yes_bid DECIMAL(10,4) NOT NULL,
    yes_ask DECIMAL(10,4) NOT NULL,
    no_bid DECIMAL(10,4) NOT NULL,
    no_ask DECIMAL(10,4) NOT NULL,
    CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999)
);

CREATE TABLE orders (
    order_id VARCHAR(100) PRIMARY KEY,
    yes_price DECIMAL(10,4),
    no_price DECIMAL(10,4),
    maker_fees DECIMAL(10,4),
    taker_fees DECIMAL(10,4)
);

CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    market_exposure DECIMAL(10,4),
    fees_paid DECIMAL(10,4),
    realized_pnl DECIMAL(10,4)
);
```

---

## Edge Calculation Cheat Sheet

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_edge(true_prob: Decimal, market_price: Decimal) -> Decimal:
    """
    Calculate expected value with sub-penny precision.
    
    Example:
        true_prob = 0.6500 (65% win probability)
        market_price = 0.5800 (market pricing at 58¢)
        
        Returns: 0.0770 (7.7% edge)
    """
    profit_if_win = Decimal("1.0000") - market_price
    expected_gain = true_prob * profit_if_win
    
    prob_loss = Decimal("1.0000") - true_prob
    expected_loss = prob_loss * market_price
    
    edge = expected_gain - expected_loss
    
    # Round to 4 decimal places
    return edge.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

# Example usage
true_prob = Decimal("0.6500")
market_price = Decimal("0.5800")
edge = calculate_edge(true_prob, market_price)
print(f"Edge: {edge}")  # 0.0770 (7.7%)
```

---

## Spread Calculation Cheat Sheet

```python
def calculate_spread(yes_bid: Decimal, no_bid: Decimal) -> Decimal:
    """
    Calculate market spread.
    
    Kalshi orderbooks show bids only.
    YES ask = 1.0 - NO bid
    NO ask = 1.0 - YES bid
    """
    yes_ask = Decimal("1.0000") - no_bid
    spread = yes_ask - yes_bid
    return spread.quantize(Decimal("0.0001"))

# Example
yes_bid = Decimal("0.4200")
no_bid = Decimal("0.5700")
spread = calculate_spread(yes_bid, no_bid)
print(f"Spread: {spread}")  # 0.0100 (1¢)

# With sub-penny pricing (future)
yes_bid = Decimal("0.4275")
no_bid = Decimal("0.5700")
spread = calculate_spread(yes_bid, no_bid)
print(f"Spread: {spread}")  # 0.0025 (0.25¢)
```

---

## Configuration File Cheat Sheet

```yaml
# config/trading.yaml

trading:
  sports_live:
    confidence:
      # Use DECIMAL format (not integers)
      ignore_threshold: 0.0500      # 5%
      alert_threshold: 0.0800       # 8%
      auto_execute_threshold: 0.1500  # 15%
    
    liquidity:
      min_spread: 0.0200  # 2¢ (can go lower with sub-penny)
      max_spread: 0.0800  # 8¢
```

---

## Validation Cheat Sheet

```python
from decimal import Decimal, InvalidOperation

def validate_price(price: Decimal, field_name: str = "price") -> None:
    """
    Validate that price is in valid range.
    
    Raises:
        ValueError: If price is out of bounds
    """
    if not isinstance(price, Decimal):
        raise TypeError(f"{field_name} must be Decimal, got {type(price)}")
    
    if price < Decimal("0.0001"):
        raise ValueError(f"{field_name} too low: {price} < 0.0001")
    
    if price > Decimal("0.9999"):
        raise ValueError(f"{field_name} too high: {price} > 0.9999")

def validate_price_consistency(yes_bid: Decimal, no_bid: Decimal) -> None:
    """
    Validate that YES + NO bids approximately equal 1.0.
    """
    total = yes_bid + (Decimal("1.0000") - no_bid)  # YES bid + YES ask
    
    # Allow for spread (95% to 105%)
    if not (Decimal("0.95") <= total <= Decimal("1.05")):
        raise ValueError(
            f"Price consistency check failed: {yes_bid} + {no_bid} = {total}"
        )
```

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Using Float Instead of Decimal
```python
# ❌ WRONG - Float has precision issues
yes_bid = float(market_data["yes_bid_dollars"])  # 0.42999999999

# ✅ CORRECT - Decimal is exact
yes_bid = Decimal(market_data["yes_bid_dollars"])  # 0.4300
```

### ❌ Mistake 2: Forgetting to Parse Dollars Field
```python
# ❌ WRONG - Still using deprecated integer field
yes_bid = market_data["yes_bid"]  # 43

# ✅ CORRECT - Use dollars field
yes_bid = Decimal(market_data["yes_bid_dollars"])  # 0.4300
```

### ❌ Mistake 3: Integer Database Columns
```sql
-- ❌ WRONG
CREATE TABLE markets (yes_bid INTEGER);

-- ✅ CORRECT
CREATE TABLE markets (yes_bid DECIMAL(10,4));
```

### ❌ Mistake 4: Not Rounding Properly
```python
# ❌ WRONG - Too many decimal places
edge = Decimal("0.077023456")

# ✅ CORRECT - Round to 4 places
edge = edge.quantize(Decimal("0.0001"))  # 0.0770
```

---

## Testing Cheat Sheet

```python
import unittest
from decimal import Decimal

class TestDecimalPricing(unittest.TestCase):
    def test_parse_market_data(self):
        """Test that we parse decimal prices correctly."""
        market_data = {
            "ticker": "TEST-YES",
            "yes_bid_dollars": "0.4275",
            "yes_ask_dollars": "0.4300",
            "no_bid_dollars": "0.5700",
            "no_ask_dollars": "0.5725"
        }
        
        parsed = parse_kalshi_market(market_data)
        
        self.assertIsInstance(parsed["yes_bid"], Decimal)
        self.assertEqual(parsed["yes_bid"], Decimal("0.4275"))
    
    def test_edge_calculation(self):
        """Test edge calculation with sub-penny precision."""
        edge = calculate_edge(
            true_prob=Decimal("0.6500"),
            market_price=Decimal("0.5800")
        )
        
        self.assertEqual(edge, Decimal("0.0770"))  # 7.7%
    
    def test_price_validation(self):
        """Test that invalid prices are rejected."""
        with self.assertRaises(ValueError):
            validate_price(Decimal("1.0500"))  # Too high
        
        with self.assertRaises(ValueError):
            validate_price(Decimal("0.0000"))  # Too low
```

---

## Migration Checklist

When implementing Kalshi integration:

- [ ] Import `decimal.Decimal` in all price-handling modules
- [ ] Parse `*_dollars` fields from ALL API responses
- [ ] Use `DECIMAL(10,4)` for ALL price columns in database
- [ ] Use decimal strings in ALL order placement requests
- [ ] Validate prices are in 0.0001-0.9999 range
- [ ] Round calculated values to 4 decimal places
- [ ] Test with sub-penny prices (e.g., 0.4275)
- [ ] Never use integer cent fields (deprecated)

---

## Reference Links

- [Kalshi Sub-Penny Pricing Docs](https://docs.kalshi.com/getting_started/subpenny_pricing)
- [Python Decimal Module](https://docs.python.org/3/library/decimal.html)
- [PostgreSQL DECIMAL Type](https://www.postgresql.org/docs/current/datatype-numeric.html)

---

## Questions?

**"Why DECIMAL(10,4) specifically?"**
- 10 total digits, 4 after decimal point
- Supports 0.0001 to 9999.9999
- Exact precision (no rounding errors like float)

**"Can I use FLOAT instead?"**
- No! Float has precision issues (0.43 might become 0.42999999)
- DECIMAL is exact for monetary values

**"What about fees and costs?"**
- ALL monetary values use DECIMAL(10,4)
- This includes fees, costs, PnL, exposure, etc.

**"When will integer fields be removed?"**
- Kalshi says "near future" (no specific date)
- By using decimal now, you're future-proof

---

**Print this and keep it at your desk during implementation!** 📌
