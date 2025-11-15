# Documentation v2.0 Review Guide

**Date:** October 8, 2025
**Purpose:** Focused review of critical v2.0 changes
**Documents:** CONFIGURATION_GUIDE.md v2.0, ARCHITECTURE_DECISIONS.md v2.0

---

## Critical Change: Decimal Pricing (MOST IMPORTANT)

### What Changed

**❌ OLD (v1.0 - WRONG):**
```yaml
max_spread: 5  # Integer cents
```

```sql
yes_bid INTEGER CHECK (yes_bid >= 0 AND yes_bid <= 100)
```

```python
yes_bid = market_data["yes_bid"]  # Deprecated field
```

**✅ NEW (v2.0 - CORRECT):**
```yaml
max_spread: 0.0500  # Decimal format, 4 decimal places
```

```sql
yes_bid DECIMAL(10,4) CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999)
```

```python
from decimal import Decimal
yes_bid = Decimal(market_data["yes_bid_dollars"])  # Future-proof field
```

### Why This Is Critical

1. **Kalshi is deprecating integer cent fields** - They're moving to sub-penny precision
2. **Timeline unclear** - Could happen "in near future"
3. **Breaking change** - Code using old approach will break
4. **Sub-penny pricing coming** - Examples: 42.75¢, 58.33¢

### Impact on Your Implementation

**Phase 1 (Database Setup):**
- MUST use `DECIMAL(10,4)` for ALL price columns
- Cannot use `INTEGER` type

**Phase 1 (API Integration):**
- MUST parse `*_dollars` fields (e.g., `yes_bid_dollars`)
- CANNOT parse deprecated integer fields (`yes_bid`, `no_bid`)

**Phase 1 (Configuration):**
- All YAML price parameters use decimal format
- Example: `max_spread: 0.0500` not `max_spread: 5`

**All Phases (Code):**
- ALWAYS use `Decimal` type, never `float` or `int`
- ALWAYS validate prices in range (0.0001-0.9999)

### Review Checklist

- [ ] Understand why integer cents are deprecated
- [ ] Understand decimal format (4 decimal places)
- [ ] Know which API fields to parse (`*_dollars`)
- [ ] Know which API fields to avoid (integer fields)
- [ ] Understand DECIMAL(10,4) database type
- [ ] Know to use Python's `Decimal` type
- [ ] Understand price range (0.0001-0.9999)

---

## Enhancement: Platform-Specific Configuration

### What's New in v2.0

CONFIGURATION_GUIDE.md now includes platform-specific settings:

```yaml
platform_specific:
  kalshi:
    fee_structure:
      maker_fee: 0.0000
      taker_fee: 0.0070
    execution:
      use_websocket: true
      rest_polling_interval: 60

  polymarket:
    fee_structure:
      base_gas_estimate: 0.0050  # Ethereum gas variable
      gas_price_buffer: 1.20
    execution:
      use_websocket: false  # May not be available
      rest_polling_interval: 30
```

### Why This Matters

**You confirmed Phase 10 (Polymarket) is a real goal.**

This design prepares for:
- Different fee structures per platform
- Different execution approaches (Kalshi has WebSocket, Polymarket may not)
- Gas fees for blockchain platforms (Polymarket on Polygon)
- Platform-specific polling intervals

### When You'll Use This

- **Phase 1-9:** Only Kalshi, use `platform_specific.kalshi` settings
- **Phase 10:** Add Polymarket, use `platform_specific.polymarket` settings
- **Configuration system:** Can select platform at runtime

### Review Checklist

- [ ] Understand platform-specific vs. global settings
- [ ] Know Kalshi has zero maker fees, 0.7% taker fees
- [ ] Know Polymarket has gas fees (blockchain-based)
- [ ] Understand this is for Phase 10, not immediate

---

## Enhancement: Sport-Specific Trading Parameters

### What's New in v2.0

CONFIGURATION_GUIDE.md now breaks down trading parameters by sport:

```yaml
categories:
  sports:
    nfl:
      kelly_fraction: 0.25
      max_spread: 0.0500
      auto_execute_threshold: 0.1500

    nba:
      kelly_fraction: 0.22  # More conservative
      max_spread: 0.0600   # Wider spread tolerance
      auto_execute_threshold: 0.1700  # Higher threshold

    tennis:
      kelly_fraction: 0.18  # Very conservative
      max_spread: 0.1000   # Much wider spread
      auto_execute_threshold: 0.2500  # Much higher threshold
```

### Rationale

**Different sports have different characteristics:**

**NFL:**
- More predictable outcomes
- Less momentum swings
- Lower volatility
- → More aggressive Kelly fraction (0.25)

**NBA:**
- Higher variance (more possessions)
- More frequent lead changes
- → More conservative Kelly fraction (0.22)
- → Higher auto-execute threshold (17% vs 15%)

**Tennis:**
- Extreme momentum swings (one break can flip match)
- Set-by-set volatility
- → Very conservative Kelly fraction (0.18)
- → Much higher threshold (25%)

### When You'll Use This

- **Phase 1-5:** NFL only, use `categories.sports.nfl` settings
- **Phase 6:** Add NBA, use `categories.sports.nba` settings
- **Phase 6:** Add Tennis, use `categories.sports.tennis` settings
- **Tuning:** Can adjust per sport based on performance

### Review Checklist

- [ ] Understand why different sports need different parameters
- [ ] Know NFL is most aggressive (0.25 Kelly)
- [ ] Know Tennis is most conservative (0.18 Kelly)
- [ ] Understand max_spread varies by sport volatility
- [ ] Know auto_execute_threshold varies by confidence needed

---

## New Decision: Cross-Platform Selection (#11)

### What's New in v2.0

ARCHITECTURE_DECISIONS.md now documents how to choose platform when a market exists on multiple platforms (e.g., same NFL game on both Kalshi and Polymarket):

**Selection Priority:**
1. **Liquidity** (highest volume)
2. **Fees** (lowest total cost)
3. **Execution speed**
4. **Platform preference** (configurable)

**Example Code:**
```python
def select_best_platform(market_options):
    """
    Given same market on multiple platforms, choose best one.

    Args:
        market_options: List of (platform, market_data) tuples

    Returns:
        Selected (platform, market_data)
    """
    scored = []
    for platform, market in market_options:
        score = 0

        # 1. Liquidity (40% weight)
        score += (market.volume / max_volume) * 40

        # 2. Fees (30% weight)
        cost = market.yes_ask + platform.fees
        score += (1 - cost/max_cost) * 30

        # 3. Speed (20% weight)
        score += platform.speed_score * 20

        # 4. Preference (10% weight)
        score += config.platform_preference[platform.name] * 10

        scored.append((score, platform, market))

    return max(scored)[1:]  # Return (platform, market) with highest score
```

**Arbitrage Detection:**
```python
def detect_arbitrage(market_a, market_b):
    """Buy YES on cheaper platform, NO on expensive"""
    cost = market_a.yes_ask + market_a.fees + market_b.no_ask + market_b.fees
    payout = Decimal('1.0000')
    profit = payout - cost

    if profit > Decimal('0.0200'):  # Min 2¢ after fees
        return Arbitrage(...)
```

### Why This Matters

- **Phase 10:** When Polymarket integrated, same markets may exist on both
- **Optimization:** Want to trade on best platform for that specific market
- **Arbitrage:** Can exploit price differences between platforms

### Review Checklist

- [ ] Understand platform selection is for Phase 10
- [ ] Know priority order: liquidity, fees, speed, preference
- [ ] Understand arbitrage opportunity detection
- [ ] Know minimum arbitrage profit is 2¢ after fees

---

## New Decision: Correlation Detection (#12)

### What's New in v2.0

ARCHITECTURE_DECISIONS.md now has explicit three-tier correlation detection:

**Tier 1: Perfect Correlation (1.0)**
- Same event, different platforms
- Example: "Chiefs win" on Kalshi AND Polymarket
- **Limit:** Cannot hold both sides

**Tier 2: High Correlation (0.7-0.9)**
- Same game, related outcomes
- Example: "Chiefs win" + "Chiefs cover spread"
- **Limit:** Max 50% of position size each

**Tier 3: Moderate Correlation (0.4-0.6)**
- Same sport, same day
- Example: Multiple NFL games on Sunday
- **Limit:** max_correlated_exposure ($5,000 default)

**Detection Logic:**
```python
def detect_correlation(position_a, position_b):
    # Tier 1: Perfect correlation
    if (position_a.event_id == position_b.event_id and
        position_a.platform != position_b.platform):
        return 1.0

    # Tier 2: High correlation
    if position_a.event_id == position_b.event_id:
        return 0.8  # Same game, different outcomes

    # Tier 3: Moderate correlation
    if (position_a.sport == position_b.sport and
        position_a.event_date == position_b.event_date):
        return 0.5

    return 0.0  # No correlation

def enforce_correlation_limits(new_position, existing_positions):
    for existing in existing_positions:
        correlation = detect_correlation(new_position, existing)

        if correlation >= 1.0:
            raise CannotHoldBothSides()

        if correlation >= 0.7:
            max_size = existing.size * 0.5
            if new_position.size > max_size:
                raise CorrelationLimitExceeded()

        if correlation >= 0.4:
            total_exposure = sum(p.exposure for p in existing_positions
                                if detect_correlation(new_position, p) >= 0.4)
            if total_exposure + new_position.exposure > config.max_correlated_exposure:
                raise CorrelationLimitExceeded()
```

### Why This Matters

**Risk Management:** Prevents over-concentration in correlated positions

**Examples:**
- Can't be long Chiefs on both Kalshi and Polymarket (Tier 1)
- Can't max out both "Chiefs win" and "Chiefs cover" (Tier 2)
- Can't have 10 NFL positions all on same Sunday (Tier 3)

### When You'll Use This

- **Phase 5:** Implement correlation detection in trading logic
- **Phase 10:** Tier 1 becomes critical (multi-platform)

### Review Checklist

- [ ] Understand three tiers of correlation
- [ ] Know Tier 1 is strictest (cannot hold both sides)
- [ ] Know Tier 2 limits position size (max 50%)
- [ ] Know Tier 3 limits total exposure ($5K default)
- [ ] Understand this is for risk management

---

## New Decision: WebSocket State Management (#13)

### What's New in v2.0

ARCHITECTURE_DECISIONS.md now has explicit WebSocket state machine:

**States:**
1. DISCONNECTED → Initial state
2. CONNECTING → Attempting connection
3. CONNECTED → TCP connection established
4. AUTHENTICATED → API key accepted
5. SUBSCRIBED → Receiving market data
6. RECONNECTING → Connection lost, attempting recovery

**Trading Rules by State:**
- **DISCONNECTED:** No automated trading, manual approval required
- **CONNECTING:** No automated trading
- **AUTHENTICATED:** No automated trading (not subscribed yet)
- **SUBSCRIBED:** Automated trading allowed
- **RECONNECTING:** Pause automated trading, use REST fallback

**Gap Detection on Reconnect:**
```python
async def on_reconnect(self):
    """After reconnection, check for missed updates"""
    gap_updates = await self.rest_client.get_market_updates(
        since=self.last_message_time,
        limit=100
    )

    if len(gap_updates) >= 100:
        # May have missed updates beyond limit
        self.require_manual_review = True
        self.pause_automated_trading()

    # Apply gap updates
    for update in gap_updates:
        self.process_update(update)
```

**Automatic Failover:**
```python
class WebSocketManager:
    def __init__(self):
        self.state = State.DISCONNECTED
        self.rest_fallback = KalshiRestClient()

    async def ensure_data(self):
        """Get market data from WebSocket or REST"""
        if self.state == State.SUBSCRIBED:
            return await self.websocket.get_updates()
        else:
            # Fallback to REST polling
            return await self.rest_fallback.get_markets()
```

### Why This Matters

**Reliability:** WebSocket connections can drop (network issues, server restarts)

**Safety:** Don't want to trade on stale data

**Hybrid Approach:** WebSocket primary, REST backup

### When You'll Use This

- **Phase 3:** Implement WebSocket connection
- **Phase 5:** Add state management and failover logic

### Review Checklist

- [ ] Understand WebSocket state machine
- [ ] Know automated trading only allowed in SUBSCRIBED state
- [ ] Know gap detection checks for missed updates
- [ ] Understand REST fallback when WebSocket down
- [ ] Know manual review required if gap >100 updates

---

## Enhancement: Odds Matrix Clarification

### What Changed in v2.0

**Original Claim:** Unified odds matrix for all categories (sports, politics, entertainment)

**Reality Check:** That would be messy!

**Updated Design:**
- **Unified table:** For sports (NFL, NBA, Tennis) - data similar enough
- **Separate tables:** For non-sports - data too different

**Rationale:**

**Sports:** Structured data
- Score differential
- Time remaining
- Quarter/inning
- Home/away
- → Same schema works for all sports

**Politics:** Semi-structured data
- Days until election
- Polling average
- Approval rating
- → Different schema needed

**Entertainment:** Unstructured data
- Social buzz score
- Box office predictions
- → Very different schema

**Implementation:**
```sql
-- Sports (unified)
CREATE TABLE odds_matrices (
    subcategory VARCHAR,  -- 'nfl', 'nba', 'tennis'
    state_descriptor VARCHAR,
    situational_factors JSONB,
    win_probability FLOAT,
    ...
);

-- Politics (separate)
CREATE TABLE odds_matrices_politics (
    event_type VARCHAR,  -- 'presidential', 'senate'
    days_until_election INT,
    polling_average DECIMAL(5,2),
    win_probability FLOAT,
    ...
);

-- Entertainment (separate)
CREATE TABLE odds_matrices_entertainment (
    event_type VARCHAR,  -- 'boxoffice', 'awards'
    release_date DATE,
    social_buzz_score FLOAT,
    win_probability FLOAT,
    ...
);
```

### Why This Matters

- **Phase 1-7:** Single sports table works fine
- **Phase 8:** When adding politics/entertainment, create separate tables
- **Avoids:** Forcing incompatible data into one schema

### Review Checklist

- [ ] Understand unified table for sports
- [ ] Understand separate tables for non-sports
- [ ] Know this is for Phase 8 (not immediate)
- [ ] Know rationale: data structures too different

---

## Validation Checklist

### Decimal Pricing Understanding

**Test your understanding:**

1. **What Python type should you use for prices?**
   - Answer: `Decimal` (from decimal module)

2. **What API fields should you parse?**
   - Answer: `*_dollars` fields (e.g., `yes_bid_dollars`)

3. **What database type should you use?**
   - Answer: `DECIMAL(10,4)`

4. **What's the valid price range?**
   - Answer: 0.0001 to 0.9999 (0.01¢ to 99.99¢)

5. **Why not use `float`?**
   - Answer: Floating point precision errors (0.1 + 0.2 = 0.30000000000000004)

### Platform-Specific Configuration

**Test your understanding:**

1. **When will you need platform-specific settings?**
   - Answer: Phase 10 (Polymarket integration)

2. **What's different between Kalshi and Polymarket fees?**
   - Answer: Kalshi has fixed %, Polymarket has variable gas fees

3. **Does Kalshi have WebSocket support?**
   - Answer: Yes

### Sport-Specific Parameters

**Test your understanding:**

1. **Which sport has the most aggressive Kelly fraction?**
   - Answer: NFL (0.25)

2. **Which sport has the most conservative Kelly fraction?**
   - Answer: Tennis (0.18)

3. **Why does Tennis need a higher auto-execute threshold?**
   - Answer: More volatility, momentum swings, less predictable

### Correlation Detection

**Test your understanding:**

1. **What's Tier 1 correlation?**
   - Answer: Same event, different platforms (1.0)

2. **What's the limit for Tier 1?**
   - Answer: Cannot hold both sides

3. **What's the limit for Tier 2?**
   - Answer: Max 50% of position size

### WebSocket State Management

**Test your understanding:**

1. **In which state is automated trading allowed?**
   - Answer: SUBSCRIBED only

2. **What happens if WebSocket disconnects?**
   - Answer: Automatic failover to REST polling

3. **What if gap >100 updates on reconnect?**
   - Answer: Require manual review, pause automated trading

---

## Critical Reminders

**⚠️ Before Phase 1 Implementation:**

1. **Print KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md** - Keep at desk!
2. **Never use `float` for prices** - Always `Decimal`
3. **Never parse deprecated integer fields** - Always `*_dollars` fields
4. **Always use DECIMAL(10,4) in database** - Never INTEGER
5. **Always validate price ranges** - 0.0001 to 0.9999
6. **Always include `row_current_ind = TRUE`** - On versioned tables

---

## Questions for Review

Before we proceed, do you:

1. **Understand the decimal pricing change?**
   - Why it's critical
   - What changes in code/database/config

2. **Understand the multi-platform design?**
   - Why it was added
   - When you'll use it (Phase 10)

3. **Understand sport-specific parameters?**
   - Why different sports need different settings
   - How to tune them

4. **Understand correlation detection?**
   - Three tiers
   - Risk management purpose

5. **Understand WebSocket state management?**
   - State machine
   - Failover logic

6. **Have any questions about the changes?**
   - Anything unclear
   - Anything you want to discuss

---

**End of Review Guide**

**Next Step:** Discuss any questions, then proceed to validation and Phase 0 completion.
