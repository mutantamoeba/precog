# Kalshi Sub-Penny Pricing Implementation

**Version:** 1.0
**Created:** 2025-11-23
**Last Updated:** 2025-11-23
**Status:** ✅ Implemented
**Phase:** Phase 1 (API Integration)

---

## Purpose

Documents Precog's implementation of Kalshi's sub-penny pricing format, supporting 4 decimal places (e.g., `0.4275`) for market prices.

**Why This Matters:**
- Kalshi markets support prices like `$0.4275` (sub-penny precision)
- Using wrong API fields loses precision → wrong probabilities → bad trades
- Float arithmetic causes rounding errors (0.96 + 0.04 = 1.0000000000000002) → failed assertions
- Decimal arithmetic with correct fields maintains exact precision (Decimal("0.96") + Decimal("0.04") = Decimal("1.00"))

---

## Background

### Discovery (2025-11-23)

While implementing VCR tests for Pattern 13 (Real Fixtures, Not Mocks), we discovered that our KalshiClient was parsing **the wrong API fields**:

**Problem:**
```python
# We were parsing integer cent fields (WRONG!)
price_fields = ["yes_bid", "yes_ask", "no_bid", "no_ask"]  # Values: 0, 100 (integers)

# This caused test failures:
assert isinstance(4, Decimal)  # FAIL - 4 is int, not Decimal
assert 4 + 96 == Decimal("1.0000")  # FAIL - 100 != Decimal("1.0000")
```

**Root Cause:**
Kalshi API provides **dual format** for backward compatibility:
- **Legacy format:** Integer cents (`yes_bid: 0`, `yes_ask: 100`)
- **Sub-penny format:** String dollars (`yes_bid_dollars: "0.0000"`, `yes_ask_dollars: "1.0000"`)

We were parsing the legacy format, which:
1. Returns integers (not suitable for Decimal conversion)
2. Does not support sub-penny prices (max 2 decimals: $0.01 to $0.99)
3. Loses precision when markets have prices like $0.4275

**Solution:**
Update `_convert_prices_to_decimal()` to parse sub-penny fields:
- Market endpoints: Use `*_dollars` suffix
- Fill endpoints: Use `*_fixed` suffix
- Convert strings to Decimal for exact precision

---

## Kalshi API Dual Format

### Market Endpoint Response

```json
{
  "markets": [{
    "ticker": "KXNFLGAME-25NOV27GBDET-GB",

    // Legacy format (integer cents) - DO NOT USE
    "yes_bid": 0,           // Integer: 0 cents
    "yes_ask": 100,         // Integer: 100 cents = $1.00
    "no_bid": 0,
    "no_ask": 100,
    "last_price": 0,

    // Sub-penny format (string dollars) - USE THESE! ✅
    "yes_bid_dollars": "0.0000",      // String: 4 decimals
    "yes_ask_dollars": "1.0000",      // Supports sub-penny: "0.4275"
    "no_bid_dollars": "0.0000",
    "no_ask_dollars": "1.0000",
    "last_price_dollars": "0.0000",

    // Metadata
    "price_level_structure": "linear_cent",
    "response_price_units": "usd_cent"
  }]
}
```

### Fill Endpoint Response

```json
{
  "fills": [{
    "ticker": "KXALIENS-26",
    "side": "no",
    "action": "buy",
    "count": 103,

    // Legacy format - DO NOT USE
    "yes_price": 4,         // Integer: 4 cents
    "no_price": 96,         // Integer: 96 cents
    "price": 0.04,          // Float (DANGEROUS!)

    // Sub-penny format - USE THESE! ✅
    "yes_price_fixed": "0.0400",   // String: 4 decimals
    "no_price_fixed": "0.9600"     // YES + NO = 1.0000 exactly
  }]
}
```

**Field Naming Pattern:**
- **Market endpoints:** `*_dollars` suffix (e.g., `yes_bid_dollars`)
- **Fill endpoints:** `*_fixed` suffix (e.g., `yes_price_fixed`)
- **Portfolio endpoints:** Integer cents (e.g., `balance: 235084`)

---

## Implementation

### Code Changes (2025-11-23)

**File:** `src/precog/api_connectors/kalshi_client.py`

**Method:** `_convert_prices_to_decimal()` (lines 329-394)

#### Before (WRONG - Integer Cents)

```python
price_fields = [
    "yes_bid",      # Integer: 0, 100
    "yes_ask",
    "no_bid",
    "no_ask",
    "last_price",
    "yes_price",    # Integer: 4, 96
    "no_price",
    # ...
]

# Result: Converts integers to Decimal
# Problem: No sub-penny precision, loses exact string format
```

#### After (CORRECT - String Dollars)

```python
price_fields = [
    # Market price fields (sub-penny format: *_dollars suffix)
    "yes_bid_dollars",          # String: "0.0000" → Decimal("0.0000")
    "yes_ask_dollars",          # String: "1.0000" → Decimal("1.0000")
    "no_bid_dollars",           # String: "0.4275" → Decimal("0.4275")
    "no_ask_dollars",
    "last_price_dollars",
    "previous_price_dollars",
    "previous_yes_bid_dollars",
    "previous_yes_ask_dollars",

    # Fill price fields (sub-penny format: *_fixed suffix)
    "yes_price_fixed",          # String: "0.0400" → Decimal("0.0400")
    "no_price_fixed",           # String: "0.9600" → Decimal("0.9600")

    # Other market fields with *_dollars suffix
    "liquidity_dollars",
    "notional_value_dollars",

    # Position/portfolio fields (various formats)
    "user_average_price",
    "realized_pnl",
    "total_cost",
    "fees_paid",
    "settlement_value",
    "revenue",
    "total_fees",
    "balance",  # Integer cents (no _dollars variant)
]

# Result: Converts strings to Decimal with exact precision
# Supports sub-penny prices: "0.4275" → Decimal("0.4275")
```

### Test Updates

**File:** `tests/integration/api_connectors/test_kalshi_client_vcr.py`

**Changes:**
1. Updated field assertions to use `*_dollars` fields:
   ```python
   # Before
   assert isinstance(market["yes_bid"], Decimal)

   # After
   assert isinstance(market["yes_bid_dollars"], Decimal)
   ```

2. Updated fill assertions to use `*_fixed` fields:
   ```python
   # Before
   assert fill["yes_price"] == Decimal("0.0400")

   # After
   assert fill["yes_price_fixed"] == Decimal("0.0400")
   ```

3. Updated price complementarity test:
   ```python
   # Before (FAILED - 4 + 96 = 100, not 1.0000)
   yes_price = fill["yes_price"]  # 4 (int)
   no_price = fill["no_price"]    # 96 (int)

   # After (PASSES - 0.04 + 0.96 = 1.00 exactly)
   yes_price = fill["yes_price_fixed"]  # Decimal("0.0400")
   no_price = fill["no_price_fixed"]    # Decimal("0.9600")
   ```

---

## Verification

### VCR Test Results (2025-11-23)

**Command:**
```bash
python -m pytest tests/integration/api_connectors/test_kalshi_client_vcr.py -v
```

**Result:** ✅ **8/8 tests passed**

**Tests Verified:**
1. ✅ `test_get_markets_with_real_api_data` - Parses `*_dollars` fields correctly
2. ✅ `test_get_balance_with_real_api_data` - Handles integer cents (balance: 235084)
3. ✅ `test_get_positions_with_real_api_data` - Empty positions list
4. ✅ `test_get_fills_with_real_api_data` - Parses `*_fixed` fields correctly
5. ✅ `test_get_settlements_with_real_api_data` - Empty settlements list
6. ✅ `test_sub_penny_pricing_in_real_markets` - Decimal precision preserved
7. ✅ `test_cent_to_dollar_conversion_accuracy` - Exact cent conversion
8. ✅ `test_yes_no_price_complementarity` - YES + NO = 1.00 exactly

**Key Assertion (Complementarity):**
```python
yes_price = Decimal("0.0400")
no_price = Decimal("0.9600")
total = yes_price + no_price
assert total == Decimal("1.0000")  # PASSES ✅
```

**Why This Works:**
- Decimal("0.96") + Decimal("0.04") = Decimal("1.00") (exact)
- vs. float: 0.96 + 0.04 = 1.0000000000000002 (rounding error!)

### Real API Response (Cassette)

**File:** `tests/cassettes/kalshi_get_markets.yaml`

```yaml
markets:
  - ticker: "KXNFLGAME-25NOV27GBDET-GB"
    yes_bid: 0                    # ← Integer cents (legacy)
    yes_bid_dollars: "0.0000"     # ← String dollars (sub-penny) ✅
    yes_ask: 100
    yes_ask_dollars: "1.0000"
    no_bid: 0
    no_bid_dollars: "0.0000"
    no_ask: 100
    no_ask_dollars: "1.0000"
    last_price: 0
    last_price_dollars: "0.0000"
    price_level_structure: "linear_cent"
    response_price_units: "usd_cent"
```

**File:** `tests/cassettes/kalshi_get_fills.yaml`

```yaml
fills:
  - ticker: "KXALIENS-26"
    side: "no"
    yes_price: 4                  # ← Integer cents (legacy)
    yes_price_fixed: "0.0400"     # ← String dollars (sub-penny) ✅
    no_price: 96
    no_price_fixed: "0.9600"
    price: 0.04                   # ← Float (DANGEROUS!)
```

---

## Trade-offs

### Why Parse `*_dollars` Instead of Integer Cents?

| Aspect | Integer Cents (`yes_bid: 0`) | String Dollars (`yes_bid_dollars: "0.0000"`) |
|--------|------------------------------|---------------------------------------------|
| **Precision** | Max 2 decimals ($0.01 increments) | 4+ decimals ($0.0001 increments) |
| **Type Safety** | int → Decimal conversion | str → Decimal (preserves exact format) |
| **Sub-penny Support** | ❌ No (limited to $0.00, $0.01, ..., $1.00) | ✅ Yes ($0.4275 supported) |
| **Future-proof** | ⚠️ Legacy format (may be deprecated) | ✅ Recommended by Kalshi |
| **Rounding Errors** | ⚠️ Possible (int division) | ✅ None (exact string format) |

**Decision:** Use `*_dollars` fields for all market/fill data to support sub-penny precision and avoid future deprecation.

### Why Not Parse Both Formats?

**Option A (REJECTED):** Parse both integer cents AND string dollars
```python
# Fallback logic
price = data.get("yes_bid_dollars") or data.get("yes_bid")
```

**Problems:**
1. More complex code (fallback logic)
2. Mixed types (string vs. int)
3. Unclear which format is authoritative
4. Harder to test (need both format scenarios)

**Option B (IMPLEMENTED):** Parse ONLY string dollars
```python
# Simple, explicit
price = data.get("yes_bid_dollars")
```

**Benefits:**
1. Simpler code (no fallback logic)
2. Consistent types (always string → Decimal)
3. Explicit format choice (sub-penny)
4. Future-proof (recommended by Kalshi)

**Risk Mitigation:**
- If API ever removes `*_dollars` fields, our conversion will log warning:
  ```python
  logger.warning(f"Failed to convert {field} to Decimal: {data[field]}")
  ```
- We can add fallback logic if needed (not currently necessary)

---

## Kalshi Official Documentation

**Reference:** https://docs.kalshi.com/getting_started/subpenny_pricing

**Key Quotes:**

> "In the near future we will be introducing sub-penny pricing, to enable trading at the below-cent level."

> "To reduce breaking changes, the Kalshi API will continue to return both integer cent fields and fixed-point dollar fields until a later date."

> "We **recommend you update your systems to parse the new fixed-point dollars fields** and prepare for subpenny precision."

**Format Specification:**
- Fixed-point dollar fields: String with 4+ decimal places
- Example: `"price_dollars": "0.1200"`
- Precision: Up to 4 decimals ($0.0001 = 1 basis point)

**Backward Compatibility:**
- Both formats coexist in API responses
- Integer cent fields: `yes_bid`, `yes_ask`, `no_bid`, `no_ask`
- String dollar fields: `yes_bid_dollars`, `yes_ask_dollars`, `no_bid_dollars`, `no_ask_dollars`

**Timeline:**
- No specific deprecation date announced for integer cent fields
- Kalshi recommends switching to `*_dollars` fields now

---

## Educational Note: Why Decimal Matters

### Float Precision Error

```python
# Float arithmetic (WRONG!)
yes_price = 0.04  # float
no_price = 0.96   # float
total = yes_price + no_price
# >>> 1.0000000000000002  # ❌ Rounding error!

assert total == 1.00  # FAILS!
```

**Why This Happens:**
- Binary floating point cannot represent 0.04 exactly
- `0.04` in binary ≈ `0.0399999999999999967...`
- `0.96` in binary ≈ `0.9599999999999999645...`
- Accumulated error: ~2e-16

### Decimal Precision (Correct)

```python
from decimal import Decimal

# Decimal arithmetic (CORRECT!)
yes_price = Decimal("0.04")  # Exact representation
no_price = Decimal("0.96")   # Exact representation
total = yes_price + no_price
# >>> Decimal("1.00")  # ✅ Exact!

assert total == Decimal("1.00")  # PASSES!
```

**Why This Works:**
- Decimal uses base-10 (like human currency)
- `Decimal("0.04")` is stored exactly as 4/100
- No binary conversion → no rounding errors
- Perfect for financial calculations

### Real Impact on Trading

**Scenario:** Buying 1000 contracts at $0.96 each

**Float Calculation:**
```python
price_per_contract = 0.96  # float
contracts = 1000
total_cost = price_per_contract * contracts
# >>> 959.9999999999999  # ❌ Lost $0.0000000000001 (accumulates!)
```

**Decimal Calculation:**
```python
price_per_contract = Decimal("0.96")
contracts = 1000
total_cost = price_per_contract * contracts
# >>> Decimal("960.00")  # ✅ Exact!
```

**At Scale (1,000,000 contracts):**
- Float error accumulates to ~$0.0001 per million contracts
- With thousands of trades → significant drift over time
- Accounting discrepancies, failed reconciliations, regulatory issues

---

## Future Considerations

### When Sub-Penny Pricing Goes Live

**Current State (Nov 2025):**
- Kalshi supports sub-penny **format** (4 decimals)
- Markets still use whole-cent increments ($0.00, $0.01, $0.02, ..., $1.00)
- `yes_bid_dollars: "0.0000"` (4 decimals, but trailing zeros)

**Future State (Timeline TBD):**
- Markets will use sub-penny **pricing** (e.g., $0.4275)
- `yes_bid_dollars: "0.4275"` (4 decimals, non-zero)
- Enables tighter bid-ask spreads (currently min $0.01, future min $0.0001)

**Our Implementation:**
✅ **Already supports sub-penny pricing!**
- Parsing `*_dollars` fields (4 decimal precision)
- Using Decimal type (arbitrary precision)
- Tests verify Decimal("0.4275") works correctly

**No Code Changes Needed:**
- When Kalshi enables sub-penny prices, our code will automatically handle them
- Tests already verify 4 decimal precision
- Decimal type supports any precision (not limited to 4 decimals)

### Edge Cases to Monitor

1. **API Field Deprecation:**
   - Watch for Kalshi announcement deprecating integer cent fields
   - If `*_dollars` fields removed, add fallback logic
   - Current: Log warning if conversion fails

2. **Precision Beyond 4 Decimals:**
   - Current: 4 decimals ($0.4275)
   - Future?: 5+ decimals ($0.42758)?
   - Decimal type already supports this (no code changes)

3. **Mixed Precision Responses:**
   - Some markets use sub-penny, others use whole cents
   - Our code handles both (Decimal("0.4275") and Decimal("0.5000"))

4. **Balance/Portfolio Endpoints:**
   - Currently use integer cents (balance: 235084)
   - May add `balance_dollars` field in future
   - Monitor Kalshi API changelog

---

## Related Documentation

**Implementation:**
- `src/precog/api_connectors/kalshi_client.py` (lines 329-394)
- `tests/integration/api_connectors/test_kalshi_client_vcr.py`

**Pattern Guides:**
- Pattern 1: Decimal Precision (CLAUDE.md)
- Pattern 13: Real Fixtures, Not Mocks (CLAUDE.md)

**API Documentation:**
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md`
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`

**External References:**
- https://docs.kalshi.com/getting_started/subpenny_pricing
- https://docs.kalshi.com/api/market-data

**Requirements:**
- REQ-SYS-003: Decimal Precision for Prices
- REQ-API-001: Kalshi API Integration
- REQ-TEST-002: Integration tests use real API fixtures

**Architecture Decisions:**
- ADR-002: Use Decimal for All Financial Calculations
- ADR-047: RSA-PSS Authentication
- ADR-050: TypedDict for API Responses

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-23 | Claude Code | Initial documentation of sub-penny pricing implementation and Kalshi dual format discovery |

---

**END OF KALSHI_SUBPENNY_PRICING_IMPLEMENTATION_V1.0.md**
