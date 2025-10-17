# Architecture & Design Decisions (UPDATED)

---
**Version:** 2.3
**Last Updated:** October 16, 2025
**Status:** ✅ Current
**Changes in v2.3:**
- Updated YAML file reference from `odds_models.yaml` to `probability_models.yaml`

**Changes in v2.2:**
- **NEW:** Added Decision #14: Terminology Standards (probability vs. odds vs. price)
- Updated all references to use "probability" instead of "odds"

**Changes in v2.0:**
- **CRITICAL:** Fixed price precision decision (DECIMAL not INTEGER)
- Added cross-platform selection strategy
- Added correlation detection approach
- Added WebSocket state management decision
- Clarified odds matrix design limits
- Enhanced for multi-platform and multi-category expansion
---

## Executive Summary

This document records all major architectural and design decisions for the Precog prediction market trading system. Each decision includes rationale, impact analysis, and alternatives considered.

**Key Principles:**
1. **Future-Proof:** Design for expansion (sports, categories, platforms)
2. **Safety-First:** Multiple layers of risk management
3. **Data-Driven:** Track everything for post-analysis
4. **Maintainable:** Clear separation of concerns

---

## Critical Design Decisions (With Rationale)

### 1. ⚠️ Price Precision - DECIMAL(10,4) for All Prices **[UPDATED]**

**Decision:** ALL price fields use `DECIMAL(10,4)` data type, NOT INTEGER cents.

**Rationale:**
- Kalshi is transitioning from integer cents (0-100) to sub-penny decimal pricing (0.0001-0.9999)
- The deprecated integer cent fields will be removed "in the near future"
- Sub-penny precision allows prices like 0.4275 (42.75¢)
- Future-proof implementation avoids costly refactoring
- Exact precision (no floating-point rounding errors)

**Impact:**
- **Database:** All price columns use `DECIMAL(10,4)` with constraints `CHECK (price >= 0.0001 AND price <= 0.9999)`
- **Python:** Always use `decimal.Decimal` type, never `float` or `int`
- **API Parsing:** Always parse `*_dollars` fields from Kalshi API (e.g., `yes_bid_dollars`), never deprecated integer fields (e.g., `yes_bid`)
- **Order Placement:** Send decimal strings in orders (e.g., `"yes_price_dollars": "0.4275"`)
- **Configuration:** All price-related config values use decimal format (e.g., `0.0500` not `5`)

**Affected Components:**
```python
# Database schema
yes_bid DECIMAL(10,4) NOT NULL,
CHECK (yes_bid >= 0.0001 AND yes_bid <= 0.9999)

# Python code
from decimal import Decimal
yes_bid = Decimal(market_data["yes_bid_dollars"])

# Configuration
max_spread: 0.0500  # Not 5 or 0.05
```

**Reference Documents:**
- KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md
- KALSHI_DATABASE_SCHEMA_CORRECTED.md

**Why NOT Integer Cents:**
- ❌ Deprecated by Kalshi
- ❌ Cannot represent sub-penny prices (0.4275)
- ❌ Will break when Kalshi removes integer fields
- ❌ Requires conversion to/from cents everywhere

**Why NOT Float:**
- ❌ Precision issues (0.43 becomes 0.42999999)
- ❌ Rounding errors accumulate in calculations
- ❌ Unreliable for financial calculations

**Why DECIMAL(10,4):**
- ✅ Exact precision for monetary values
- ✅ Supports sub-penny (4 decimal places)
- ✅ Range supports 0.0001 to 9999.9999 (future-proof)
- ✅ Standard for financial applications
- ✅ Well-supported by PostgreSQL and Python

---

### 2. Database Versioning Strategy

**Decision:** Use `row_current_ind` for frequently-changing tables, append-only for immutable data

**Tables with Versioning (row_current_ind = TRUE/FALSE):**
- `markets` - Prices change every 15-30 seconds
- `game_states` - Scores update every 30 seconds  
- `positions` - Quantity changes with each trade
- `edges` - Recalculated frequently as odds/prices change
- `account_balance` - Changes with every trade

**Append-Only Tables (No Versioning):**
- `trades` - Immutable historical record
- `settlements` - Final outcomes, never change
- `odds_matrices` - Static historical probability data
- `platforms` - Configuration data, rarely changes
- `series` - Updated in-place, no history needed
- `events` - Status changes are lifecycle transitions, no history needed

**Rationale:** 
Balance between historical tracking needs and database bloat. Version only what requires history for analysis. For example:
- We need historical prices to analyze how market moved
- We DON'T need historical series data (just latest is fine)

**Impact:**
```sql
-- Versioned table example
CREATE TABLE markets (
    ticker VARCHAR(100),
    yes_bid DECIMAL(10,4),
    updated_at TIMESTAMP DEFAULT NOW(),
    row_current_ind BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (ticker, updated_at)
);

-- Query current data only
SELECT * FROM markets WHERE row_current_ind = TRUE;

-- Query historical data
SELECT * FROM markets WHERE ticker = 'KXNFL-YES' ORDER BY updated_at;
```

**Storage Impact:** ~18 GB/year with versioning (manageable)

---

### 3. Material Change Threshold (Hybrid Approach)

**Decision:** Insert new database row only if meaningful change detected

**Criteria for "Material Change":**
```python
# Insert new row if ANY of these conditions are met:
def is_material_change(old, new):
    # Price changes
    if abs(new.yes_bid - old.yes_bid) >= Decimal('0.0100'):  # 1¢
        return True
    if abs(new.yes_bid - old.yes_bid) / old.yes_bid >= Decimal('0.02'):  # 2%
        return True
    
    # Volume changes
    if abs(new.volume - old.volume) >= 10:  # 10 contracts
        return True
    
    # Status changes
    if new.status != old.status:
        return True
    
    return False
```

**Rationale:** 
Reduces database writes by ~90%, prevents noise from tiny fluctuations (e.g., 0.4200 → 0.4201), while capturing all significant market movements.

**Trade-offs:**
- **Pro:** Massive reduction in database size and write load
- **Pro:** Noise filtering improves analysis quality
- **Con:** Lose some granularity (acceptable for our use case)
- **Con:** Slightly more complex insertion logic

**Impact:** 
Estimated 10 price updates/minute → 1 database write/minute = 90% reduction

---

### 4. API Integration Strategy: WebSocket + REST Hybrid

**Decision:** Use WebSocket for real-time data with REST polling as backup

**Primary:** 
- Kalshi WebSocket for real-time price updates (sub-second latency)
- Push notifications when market changes

**Backup:** 
- REST polling every 60 seconds
- Catches gaps if WebSocket disconnects
- Validates WebSocket data

**Game Stats:** 
- ESPN REST polling every 15-30 seconds
- No WebSocket available for ESPN

**Rationale:** 
WebSocket is fastest but can disconnect unexpectedly. REST is reliable but slower. Hybrid approach ensures resilience without sacrificing performance.

**Implementation Pattern:**
```python
class MarketDataStream:
    def __init__(self):
        self.websocket_active = False
        self.last_data_time = None
    
    async def start(self):
        # Start WebSocket
        await self.connect_websocket()
        
        # Start REST backup (runs in background)
        asyncio.create_task(self.rest_backup_loop())
    
    async def rest_backup_loop(self):
        while True:
            await asyncio.sleep(60)
            
            # Check if WebSocket data is fresh
            if self.is_data_stale():
                # Switch to REST
                await self.fetch_via_rest()
```

**Failover Logic:**
1. WebSocket disconnects → Immediately switch to REST (60s polling)
2. Set `reliable_realtime_data = FALSE` flag
3. Log gap duration for later analysis
4. On reconnect: Fetch last 100 updates to detect missed data
5. Resume WebSocket, keep REST backup running

---

### 5. Authentication Method - RSA-PSS Signatures

**Decision:** Use RSA-PSS signatures for Kalshi API authentication (not HMAC-SHA256)

**Implementation:**
```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64

def sign_request(private_key, message):
    signature = private_key.sign(
        message.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode()
```

**Key Management:**
- Development: Private key stored in `.env` file
- Production: AWS Secrets Manager (Phase 6+)
- Token refresh: Every 30 minutes
- Rotation: Every 90 days (manual for now, automated Phase 6+)

**Security Considerations:**
- ✅ Private key never transmitted
- ✅ Signature proves identity without exposing key
- ✅ Each request independently verifiable
- ⚠️ Phase 6: Move to AWS Secrets Manager
- ⚠️ Phase 6: Implement key rotation automation

---

### 6. Configuration System: Three-Tier Priority

**Decision:** Database Overrides > Environment Variables > YAML Files > Code Defaults

**Priority Order:**
1. **Database Overrides** (highest) - Runtime changes via `config_overrides` table
2. **Environment Variables** - Secrets and environment-specific values  
3. **YAML Files** - Default configuration
4. **Code Defaults** (lowest) - Fallback values

**YAML Files (7 separate files for clarity):**
1. `trading.yaml` - Trading parameters, position sizing, risk limits
2. `trade_strategies.yaml` - Strategy definitions (halftime_entry, late_q4_entry, etc.)
3. `position_management.yaml` - Exit rules, stop loss, profit targets
4. `probability_models.yaml` - Which models active, versions, adjustments
5. `markets.yaml` - Platforms, categories, series to monitor
6. `data_sources.yaml` - APIs and polling intervals
7. `system.yaml` - Database, logging, scheduling, monitoring

**Database Overrides Table:**
```sql
CREATE TABLE config_overrides (
    override_id SERIAL PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL,  -- e.g., 'trading.nfl.execution.max_spread'
    override_value JSONB NOT NULL,
    reason TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NULL,         -- Optional expiration
    active BOOLEAN DEFAULT TRUE
);
```

**Rationale:**
- **YAML:** Easy to read/edit, version controlled, good for defaults
- **Environment Variables:** Never commit secrets to Git, environment-specific
- **Database:** Allows live tuning without redeployment (critical for trading)

**Use Cases:**
- YAML: "Max spread is normally 5¢"
- Database: "Today only, allow 8¢ spread due to low liquidity"
- Environment: "Prod uses this API key, demo uses that one"

**Example:**
```python
# Get config with automatic priority resolution
max_spread = config.get('trading.nfl.execution.max_spread')
# Checks: DB override? → .env? → YAML → Code default
```

---

### 7. Trade Strategies vs. Position Management (Clear Separation)

**Decision:** Separate "when to enter" from "what to do after entry"

**Trade Strategies** (`trade_strategies.yaml`): **WHEN** to enter positions
- `halftime_entry` - Enter at halftime based on lead
- `late_q4_entry` - Enter in Q4 final minutes
- `live_continuous` - Enter anytime during game
- Focus: Entry conditions, timing, initial sizing

**Position Management** (`position_management.yaml`): **WHAT** to do after entry
- Monitoring frequency (dynamic based on game state)
- Profit targets and stop losses
- Early exit criteria (edge drops below threshold)
- Scale-in/scale-out rules
- Focus: Lifecycle management, risk control, exit timing

**Why Separate:**
```python
# Strategy: WHEN to enter
def check_halftime_entry(game_state):
    if (game_state.period == "Halftime" and 
        game_state.lead_points >= 7 and
        edge >= 0.08):
        return ENTER_POSITION
    return NO_ENTRY

# Position Management: WHAT to do after
def manage_position(position):
    if position.unrealized_pnl_pct >= 0.20:
        return TAKE_PROFIT
    elif position.unrealized_pnl_pct <= -0.15:
        return STOP_LOSS
    elif position.edge < 0.03:
        return EARLY_EXIT
    return HOLD
```

**Rationale:** 
Separation of concerns. A strategy can work (good entry timing) even if position management is suboptimal, and vice versa. Separating them allows independent testing and optimization.

**Benefits:**
- ✅ Can test strategy effectiveness independently of exit timing
- ✅ Can optimize position management without changing entry logic
- ✅ Easier to add new strategies without rewriting position logic
- ✅ Clearer code organization

---

### 8. Unified Probability Matrix Design (Platform-Agnostic)

**Decision:** Single `probability_matrices` table for sports categories, separate approach for non-sports

**Sports Probability Matrix Schema:**
```sql
CREATE TABLE probability_matrices (
    probability_id SERIAL PRIMARY KEY,
    category VARCHAR,        -- 'sports'
    subcategory VARCHAR,     -- 'nfl', 'nba', 'tennis'
    version VARCHAR,         -- 'v1.0', 'v2.0'
    
    -- Generalized state descriptors
    state_descriptor VARCHAR,-- 'halftime', 'end_Q3', 'set_1_complete'
    value_bucket VARCHAR,    -- '10+_points', '5-7_games', etc.
    
    -- Flexible metadata for sport-specific factors
    situational_factors JSONB,
    
    -- Probability and confidence
    win_probability FLOAT,
    confidence_interval_lower FLOAT,
    confidence_interval_upper FLOAT,
    sample_size INT,
    
    -- Provenance
    source VARCHAR,          -- 'PFR', 'FiveThirtyEight', 'internal'
    methodology TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Why This Works for Sports:**
- ✅ All sports have similar structure (states, scores, time)
- ✅ JSONB handles sport-specific nuances (e.g., tennis serve, NFL down/distance)
- ✅ Single codebase can handle multiple sports
- ✅ Adding new sport requires data, not schema changes

**Example Usage:**
```sql
-- NFL halftime, home team leading by 10-13 points
SELECT win_probability
FROM probability_matrices
WHERE subcategory = 'nfl'
  AND state_descriptor = 'halftime'
  AND value_bucket = '10-13_points'
  AND situational_factors->>'home_away' = 'home'
  AND situational_factors->>'favorite_underdog' = 'favorite';
```

**Non-Sports Approach - Separate Tables:**

**Decision:** Non-sports categories (politics, entertainment) use separate probability tables

**Rationale for Separation:**
- **Sports:** Structured (scores, time, states) → Unified table works
- **Politics:** Semi-structured (polls, dates, approval ratings) → Needs different schema
- **Entertainment:** Unstructured (reviews, social media, buzz) → Very different schema

**Non-Sports Schema Example:**
```sql
-- Politics-specific probability table
CREATE TABLE probability_matrices_politics (
    probability_id SERIAL PRIMARY KEY,
    event_type VARCHAR,      -- 'presidential', 'senate', 'house'
    state_or_nation VARCHAR, -- 'national', 'PA', 'GA'
    
    -- Politics-specific state
    days_until_election INT,
    polling_average DECIMAL(5,2),
    polling_margin DECIMAL(5,2),
    incumbent_advantage BOOLEAN,
    
    # Probability
    win_probability FLOAT,
    confidence_interval_lower FLOAT,
    confidence_interval_upper FLOAT,
    
    source VARCHAR,
    sample_size INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Trade-offs:**
- **Pro:** Each category has optimal schema for its data
- **Pro:** Simpler queries (no complex JSONB filtering)
- **Con:** More tables to maintain
- **Con:** Category-specific code required

**Decision Point:** Worth the trade-off. Sports categories are similar enough to unify, but forcing politics/entertainment into same table would be messy.

**When to Unify vs. Separate:**
- **Unify:** If data structure is 80%+ similar (e.g., NFL, NBA, NCAAF)
- **Separate:** If data structure is <50% similar (e.g., sports vs. politics)

---

### 9. Multi-Environment Support

**Decision:** Separate environments for demo, production, and testing

**Environments:**
- `demo` - Testing with Kalshi demo API (fake money, safe)
- `prod` - Real money trading (requires careful validation)
- `test` - Automated tests (auto-rollback after each test)

**Each Environment Has:**
```yaml
# Environment-specific config
environments:
  demo:
    database: "precog_demo"
    kalshi_api: "https://demo-api.kalshi.co"
    kalshi_api_key_env: "KALSHI_DEMO_API_KEY"
    auto_trading: true              # OK to auto-trade in demo
  
  prod:
    database: "precog_prod"
    kalshi_api: "https://trading-api.kalshi.com"
    kalshi_api_key_env: "KALSHI_PROD_API_KEY"
    auto_trading: false             # Require manual approval initially
    
  test:
    database: "precog_test"
    auto_rollback: true             # Rollback after each test
```

**Rationale:** 
Prevents accidentally trading real money during development. Allows safe experimentation with demo API. Isolated test environment prevents pollution of demo/prod data.

**Critical Safety Rules:**
- ❌ Never connect to prod database from test code
- ❌ Never use prod API keys in demo/test
- ✅ Always clearly label which environment is active
- ✅ Require explicit flag to enable prod trading

**Implementation:**
```python
# Environment selection
ENVIRONMENT = os.getenv('PRECOG_ENV', 'demo')

# Safety check before trading
def place_trade(order):
    if ENVIRONMENT == 'prod':
        if not PROD_TRADING_ENABLED:
            raise PermissionError("Prod trading not enabled!")
        
        # Additional confirmation
        if not order.manual_approval_received:
            raise PermissionError("Prod trades require manual approval!")
    
    # Proceed with trade
    execute_order(order)
```

---

### 10. Platform Abstraction Layer

**Decision:** Abstract base classes + factory pattern for multi-platform support

**Structure:**
```python
# Abstract base class
from abc import ABC, abstractmethod
from typing import List, Dict
from decimal import Decimal

class PredictionMarketPlatform(ABC):
    """
    Abstract interface that all platforms must implement.
    Ensures consistency across Kalshi, Polymarket, etc.
    """
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with platform API"""
        pass
    
    @abstractmethod
    def get_markets(self, filters: Dict) -> List[Dict]:
        """
        Fetch markets from platform.
        Returns standardized format regardless of platform.
        
        Returns:
            List of markets with keys:
            - market_id: str
            - title: str
            - yes_price: Decimal
            - no_price: Decimal
            - volume: int
            - etc.
        """
        pass
    
    @abstractmethod
    def place_order(self, market_id: str, side: str, 
                    price: Decimal, quantity: int) -> Dict:
        """Place order on platform"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        pass

# Concrete implementations
class KalshiPlatform(PredictionMarketPlatform):
    def authenticate(self):
        # RSA-PSS signing logic
        pass
    
    def get_markets(self, filters):
        # Kalshi REST API call
        raw_markets = self._call_kalshi_api('/markets', filters)
        
        # Transform to standard format
        return [self._standardize_market(m) for m in raw_markets]
    
    def _standardize_market(self, kalshi_market):
        """Convert Kalshi format to standard format"""
        return {
            'market_id': kalshi_market['ticker'],
            'title': kalshi_market['title'],
            'yes_price': Decimal(kalshi_market['yes_bid_dollars']),
            'no_price': Decimal(kalshi_market['no_bid_dollars']),
            'volume': kalshi_market['volume'],
            'platform': 'kalshi'
        }

class PolymarketPlatform(PredictionMarketPlatform):
    def authenticate(self):
        # Polymarket's auth (blockchain-based)
        pass
    
    def get_markets(self, filters):
        # Polymarket API call
        raw_markets = self._call_polymarket_api('/markets', filters)
        
        # Transform to standard format
        return [self._standardize_market(m) for m in raw_markets]
    
    def _standardize_market(self, poly_market):
        """Convert Polymarket format to standard format"""
        return {
            'market_id': poly_market['condition_id'],
            'title': poly_market['question'],
            'yes_price': Decimal(str(poly_market['outcome_prices'][0])),
            'no_price': Decimal(str(poly_market['outcome_prices'][1])),
            'volume': poly_market['volume'],
            'platform': 'polymarket'
        }

# Factory for creating platform instances
class PlatformFactory:
    @staticmethod
    def create(platform_name: str) -> PredictionMarketPlatform:
        """
        Factory pattern to instantiate correct client.
        """
        if platform_name == 'kalshi':
            return KalshiPlatform()
        elif platform_name == 'polymarket':
            return PolymarketPlatform()
        else:
            raise ValueError(f"Unknown platform: {platform_name}")

# Usage in code
def fetch_markets(platform_name: str):
    client = PlatformFactory.create(platform_name)
    markets = client.get_markets({'sport': 'nfl'})
    # markets is in standard format regardless of platform!
    return markets
```

**Rationale:** 
Adding Polymarket (Phase 10) will be trivial. Just implement the interface, no changes to core logic. All downstream code works with standard format.

**Benefits:**
- ✅ Add new platform: Create one new class, no other code changes
- ✅ Switch platforms: Change one config value
- ✅ Cross-platform features: Compare prices easily
- ✅ Testing: Mock the interface for unit tests

---

### 11. Cross-Platform Market Selection Strategy **[NEW]**

**Decision:** When same event exists on multiple platforms, select based on prioritized criteria

**Selection Algorithm:**
```python
def select_best_platform(market_options: List[Market]) -> Market:
    """
    Select optimal platform when market exists on multiple platforms.
    
    Priority:
    1. Liquidity (highest volume wins)
    2. Fees (lowest total cost)
    3. Execution speed
    4. Platform preference (configurable)
    """
    # Filter to tradeable markets
    tradeable = [m for m in market_options if m.is_tradeable()]
    
    if not tradeable:
        return None
    
    # Sort by composite score
    def score_market(market):
        # Liquidity score (0-100)
        liquidity_score = min(market.volume / 1000, 100)
        
        # Fee score (0-100, lower fees = higher score)
        fee_pct = market.taker_fee_pct
        fee_score = 100 - (fee_pct * 1000)  # 0.7% fee = 93 score
        
        # Speed score (0-100)
        speed_score = 100 if market.has_websocket else 50
        
        # Weighted composite
        return (
            liquidity_score * 0.50 +  # Liquidity most important
            fee_score * 0.30 +         # Fees second
            speed_score * 0.20         # Speed third
        )
    
    best_market = max(tradeable, key=score_market)
    return best_market
```

**Platform-Specific Considerations:**

**Kalshi:**
- ✅ Low fees (0.7% taker, 0% maker)
- ✅ Fast execution
- ✅ Regulated (CFTC)
- ⚠️ Lower liquidity on some markets

**Polymarket:**
- ✅ Often higher liquidity
- ✅ More markets available
- ⚠️ Gas fees variable (Ethereum)
- ⚠️ Slower execution (blockchain)
- ⚠️ Regulatory uncertainty

**Arbitrage Detection:**
```python
def detect_arbitrage(market_a: Market, market_b: Market) -> Optional[Arbitrage]:
    """
    Detect if price discrepancy allows risk-free profit.
    """
    # Buy YES on cheaper platform, buy NO on more expensive
    cost_platform_a = market_a.yes_ask + market_a.fees
    cost_platform_b = market_b.no_ask + market_b.fees
    
    total_cost = cost_platform_a + cost_platform_b
    payout = Decimal('1.0000')  # $1 payout guaranteed
    
    profit = payout - total_cost
    
    if profit > Decimal('0.0200'):  # Min 2¢ profit after fees
        return Arbitrage(
            buy_yes_on=market_a.platform,
            buy_no_on=market_b.platform,
            profit=profit,
            execution_time_limit=5  # Must execute in 5 seconds
        )
    
    return None
```

**Rationale:** 
Systematic approach to platform selection. Prioritizes factors that actually affect profitability (liquidity, fees) over subjective preferences.

**Implementation:** Phase 10 (multi-platform trading)

---

### 12. Correlation Detection and Limits **[NEW]**

**Decision:** Define market correlation in three tiers with corresponding exposure limits

**Correlation Tiers:**

**Tier 1: Perfect Correlation (1.0)**
- Definition: Same event, different platforms OR complementary outcomes
- Examples:
  - Same market on Kalshi and Polymarket (arbitrage)
  - "Team A wins" vs. "Team B wins" (same game)
- Limit: Cannot hold both sides
- Detection: Automatic via event_id matching

**Tier 2: High Correlation (0.7-0.9)**
- Definition: Same game, related outcomes
- Examples:
  - "Chiefs win" + "Chiefs cover spread"
  - "Player scores TD" + "Player over yards"
  - "Home team wins" + "Over points total"
- Limit: Max 50% of position size in correlated pair
- Detection: Historical price correlation analysis

**Tier 3: Moderate Correlation (0.4-0.6)**
- Definition: Same category, same time period
- Examples:
  - Multiple NFL games same Sunday
  - Related political events (Senate + House races)
  - Correlated economic indicators
- Limit: Use `max_correlated_exposure` config (default $5,000)
- Detection: Category + date matching + correlation matrix

**Implementation:**
```python
class CorrelationDetector:
    def __init__(self):
        self.correlation_matrix = self._load_correlation_matrix()
    
    def check_correlation(self, market_a, market_b) -> CorrelationTier:
        # Tier 1: Perfect correlation
        if self._is_same_event(market_a, market_b):
            return CorrelationTier.PERFECT
        
        # Tier 2: High correlation
        if self._is_same_game(market_a, market_b):
            correlation = self._calculate_historical_correlation(
                market_a, market_b
            )
            if correlation >= 0.70:
                return CorrelationTier.HIGH
        
        # Tier 3: Moderate correlation
        if self._is_same_category_and_time(market_a, market_b):
            correlation = self._calculate_historical_correlation(
                market_a, market_b
            )
            if correlation >= 0.40:
                return CorrelationTier.MODERATE
        
        return CorrelationTier.NONE
    
    def check_exposure_limit(self, proposed_trade, existing_positions):
        """Check if proposed trade violates correlation limits"""
        for position in existing_positions:
            tier = self.check_correlation(proposed_trade.market, position.market)
            
            if tier == CorrelationTier.PERFECT:
                # Block: Cannot hold both sides
                raise CorrelationViolation("Cannot hold opposing positions")
            
            elif tier == CorrelationTier.HIGH:
                # Check 50% limit
                if proposed_trade.size > position.size * 0.5:
                    raise CorrelationViolation(
                        f"High correlation: max {position.size * 0.5} allowed"
                    )
            
            elif tier == CorrelationTier.MODERATE:
                # Check total moderate correlation exposure
                total_moderate = sum(
                    p.exposure for p in existing_positions
                    if self.check_correlation(proposed_trade.market, p.market) 
                    == CorrelationTier.MODERATE
                )
                
                if total_moderate + proposed_trade.exposure > MAX_CORRELATED_EXPOSURE:
                    raise CorrelationViolation(
                        f"Total correlated exposure would exceed ${MAX_CORRELATED_EXPOSURE}"
                    )
        
        return True  # No violations
```

**Correlation Calculation:**
```python
def calculate_historical_correlation(market_a_id, market_b_id):
    """
    Calculate Pearson correlation of historical price movements.
    """
    # Get price history for both markets
    prices_a = db.query("""
        SELECT updated_at, yes_bid 
        FROM markets 
        WHERE ticker = %s 
        ORDER BY updated_at
    """, market_a_id)
    
    prices_b = db.query("""
        SELECT updated_at, yes_bid 
        FROM markets 
        WHERE ticker = %s 
        ORDER BY updated_at
    """, market_b_id)
    
    # Align timestamps and calculate returns
    aligned_a, aligned_b = align_time_series(prices_a, prices_b)
    returns_a = calculate_returns(aligned_a)
    returns_b = calculate_returns(aligned_b)
    
    # Pearson correlation
    correlation = np.corrcoef(returns_a, returns_b)[0, 1]
    
    return correlation
```

**Configuration:**
```yaml
# config/trading.yaml
correlation_detection:
  enabled: true
  
  tiers:
    perfect_correlation:
      threshold: 1.0
      max_exposure_multiplier: 1.0  # Cannot hold both
    
    high_correlation:
      threshold: 0.70
      max_exposure_multiplier: 0.5  # Max 50% of position
    
    moderate_correlation:
      threshold: 0.40
      max_exposure_multiplier: null  # Use global limit
  
  calculation_method: "historical"
  lookback_period_days: 90
  minimum_samples: 50
```

**Rationale:**
- Prevents over-concentration in correlated markets
- Reduces portfolio risk
- Automated detection prevents human error
- Three-tier approach balances safety with flexibility

---

### 13. WebSocket State Management **[NEW]**

**Decision:** Define explicit state machine for WebSocket connection lifecycle

**Connection States:**
```python
class WebSocketState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    SUBSCRIBED = "subscribed"
    ERROR = "error"
    RECONNECTING = "reconnecting"
```

**State Transitions:**
```
DISCONNECTED → CONNECTING → CONNECTED → AUTHENTICATED → SUBSCRIBED
       ↑           ↓              ↓              ↓
       ←-----------←--------------←--------------←  (on error)
                   ↓
              RECONNECTING
```

**Behavior by State:**

**DISCONNECTED:**
- No data flowing
- Use REST polling (60s intervals)
- Flag: `reliable_realtime_data = FALSE`
- Trading: Allowed with manual approval only

**CONNECTING:**
- Attempting connection
- Continue REST polling
- Timeout: 30 seconds
- On timeout: Retry with exponential backoff

**CONNECTED:**
- TCP connection established
- Not yet authenticated
- No data yet

**AUTHENTICATED:**
- Successfully authenticated
- Not yet subscribed to markets
- Send subscription requests

**SUBSCRIBED:**
- Receiving real-time data
- Flag: `reliable_realtime_data = TRUE`
- Trading: Fully automated allowed
- Monitor heartbeat (every 30s)

**ERROR:**
- Connection error occurred
- Switch to REST polling immediately
- Log error details
- Transition to RECONNECTING

**RECONNECTING:**
- Attempting to reestablish connection
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
- Continue REST polling
- After 5 attempts: Require manual intervention

**Gap Detection on Reconnection:**
```python
async def on_reconnect(self):
    """
    When WebSocket reconnects, check for missed updates.
    """
    # Get timestamp of last received message
    last_update = self.last_message_time
    
    # Fetch all updates since then via REST
    gap_updates = await self.rest_client.get_market_updates(
        since=last_update,
        limit=100
    )
    
    if len(gap_updates) >= 100:
        # May have missed some updates
        self.log_warning(f"Gap of {len(gap_updates)}+ updates detected")
        self.require_manual_review = True
    
    # Process gap updates
    for update in gap_updates:
        await self.process_market_update(update)
    
    # Resume WebSocket
    self.state = WebSocketState.SUBSCRIBED
```

**Heartbeat Monitoring:**
```python
async def heartbeat_monitor(self):
    """
    Monitor WebSocket heartbeat to detect stale connections.
    """
    while self.state == WebSocketState.SUBSCRIBED:
        await asyncio.sleep(30)
        
        if time.time() - self.last_message_time > 60:
            # No messages in 60 seconds
            self.log_warning("WebSocket heartbeat timeout")
            self.state = WebSocketState.ERROR
            await self.reconnect()
```

**Configuration:**
```yaml
# config/data_sources.yaml
websocket:
  enabled: true
  heartbeat_interval: 30
  heartbeat_timeout: 60
  
  reconnection:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2
    max_backoff_seconds: 30
  
  gap_detection:
    enabled: true
    max_gap_size: 100
    require_review_if_exceeded: true
```

**Rationale:**
- Explicit state machine prevents undefined behavior
- Gap detection ensures no missed data
- Heartbeat monitoring catches stale connections
- Automatic reconnection with backoff prevents hammering API
- Clear trading rules per state (safety first)

---

### 14. Terminology Standards: Probability vs. Odds vs. Price **[NEW]**

**Decision:** Use "probability" for calculations, "market price" for Kalshi prices, avoid "odds" internally.

**Rationale:**
- **Technical Accuracy:** Probabilities (0.0-1.0) and odds (ratio formats) are mathematically different
- **Kalshi Integration:** Kalshi API returns prices in dollars that represent implied probabilities, NOT traditional bookmaker odds
- **Code Clarity:** Consistent terminology prevents bugs and improves maintainability
- **Team Communication:** Everyone uses the same vocabulary (no confusion between "odds", "implied odds", "true odds", etc.)

**Terminology Rules:**

| Term | Use For | Example | Data Type |
|------|---------|---------|-----------|
| **Probability** | Our calculations | `true_probability`, `win_probability` | DECIMAL(10,4) 0.0000-1.0000 |
| **Market Price** | Kalshi prices | `market_price`, `yes_ask`, `yes_bid` | DECIMAL(10,4) $0.0001-$0.9999 |
| **Edge** | Advantage | `edge = probability - market_price` | DECIMAL(10,4) -1.0000-+1.0000 |
| **Odds** | User displays only | "Decimal Odds: 1.54" | Display string |

**Impact:**

**Database:**
```sql
-- CORRECT ✅
CREATE TABLE probability_matrices (...);
win_probability DECIMAL(10,4) NOT NULL;

-- INCORRECT ❌
CREATE TABLE odds_buckets (...);
win_odds DECIMAL(10,4) NOT NULL;
```

**Python Functions:**
```python
# CORRECT ✅
def calculate_win_probability(game_state) -> Decimal:
    """Calculate true win probability from historical data."""
    return Decimal("0.6500")

# INCORRECT ❌
def calculate_odds(game_state) -> Decimal:
    """Calculate odds..."""  # ❌ Ambiguous - what format?
```

**Config Files:**
```yaml
# CORRECT ✅
probability_models.yaml
win_probability: 0.6500

# INCORRECT ❌
odds_models.yaml
win_odds: 0.6500
```

**Exceptions (Where "Odds" IS Okay):**
1. **User-facing displays:** "Decimal Odds: 1.54" (formatted for readability)
2. **Importing from sportsbooks:** Converting traditional odds to probabilities
3. **Documentation explaining differences:** "Probability vs. Odds" (educational context)

**Affected Components:**
- ✅ Database: `probability_matrices` table (NOT `odds_matrices`)
- ✅ Config: `probability_models.yaml` (NOT `odds_models.yaml`)
- ✅ Functions: `calculate_win_probability()` (NOT `calculate_odds()`)
- ✅ Variables: `true_probability`, `market_price` (NOT `odds`, `implied_odds`)
- ✅ Documentation: Use "probability" in technical docs, "odds" only for user education

**Rationale for Strictness:**
- **Type Safety:** `probability: Decimal` is clear; `odds: Decimal` could be American, fractional, or decimal format
- **Beginner Friendly:** New developers learn the correct concepts immediately
- **Prevents Bugs:** No confusion about whether a value needs conversion

**Related Decisions:**
- Decision #1: Price Precision (DECIMAL for exact probability representation)
- See GLOSSARY.md for comprehensive terminology guide

---

### 15. Model Validation Strategy (Four Tracks)

**Decision:** Separate validation of model accuracy from strategy performance

**Track 1: Model Accuracy** - Did we predict outcomes correctly?
- **Data:** Only settled positions (held to completion)
- **Metrics:**
  - Accuracy: % of correct predictions
  - Brier score: (predicted_prob - actual_outcome)²
  - Calibration: Do 60% predictions win 60% of the time?
- **Why:** Tests if our probability estimates are correct

**Track 2: Strategy Performance** - Did we make money?
- **Data:** All trades including early exits
- **Metrics:**
  - ROI: Return on investment
  - Win rate: % of profitable trades
  - Sharpe ratio: Risk-adjusted returns
  - Max drawdown: Worst losing streak
- **Why:** Tests if our trading decisions are profitable

**Track 3: Edge Realization** - Did predicted edges materialize?
- **Data:** Compare predicted EV vs. actual PnL
- **Metrics:**
  - Edge capture rate: (Actual PnL / Predicted EV)
  - Slippage: Difference between expected and executed price
  - Market impact: Did our orders move the market?
- **Target:** Capturing 50%+ of predicted edge = good
- **Why:** Tests if edges are real or just model optimism

**Track 4: Model Drift Detection** - Is model degrading over time?
- **Data:** Performance by time period (weekly, monthly)
- **Metrics:**
  - Rolling accuracy (last 50 trades)
  - Calibration by period
  - Alert if performance declining
- **Why:** Detects if model needs updating

**Example Tracking:**
```python
class ModelValidator:
    def validate_track_1_accuracy(self, settled_positions):
        """Track 1: Did we predict correctly?"""
        correct = 0
        total = 0
        brier_scores = []
        
        for pos in settled_positions:
            if pos.held_to_settlement:
                predicted_prob = pos.entry_probability
                actual_outcome = 1 if pos.result == 'win' else 0
                
                brier_scores.append((predicted_prob - actual_outcome) ** 2)
                
                if (predicted_prob > 0.5 and actual_outcome == 1) or \
                   (predicted_prob < 0.5 and actual_outcome == 0):
                    correct += 1
                
                total += 1
        
        accuracy = correct / total
        brier_score = sum(brier_scores) / len(brier_scores)
        
        return {
            'accuracy': accuracy,
            'brier_score': brier_score
        }
    
    def validate_track_2_performance(self, all_trades):
        """Track 2: Did we make money?"""
        total_pnl = sum(trade.realized_pnl for trade in all_trades)
        total_invested = sum(trade.cost for trade in all_trades)
        
        roi = total_pnl / total_invested
        win_rate = len([t for t in all_trades if t.realized_pnl > 0]) / len(all_trades)
        
        returns = [t.realized_pnl / t.cost for t in all_trades]
        sharpe = (mean(returns) - RISK_FREE_RATE) / std(returns)
        
        return {
            'roi': roi,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe
        }
    
    def validate_track_3_edge_realization(self, trades):
        """Track 3: Did edges materialize?"""
        edge_capture_rates = []
        
        for trade in trades:
            predicted_ev = trade.predicted_edge * trade.cost
            actual_pnl = trade.realized_pnl
            
            if predicted_ev > 0:
                capture_rate = actual_pnl / predicted_ev
                edge_capture_rates.append(capture_rate)
        
        avg_capture = mean(edge_capture_rates)
        
        return {
            'avg_edge_capture_rate': avg_capture,
            'target_is_50_pct': avg_capture >= 0.50
        }
    
    def validate_track_4_drift(self, trades_by_date):
        """Track 4: Is model degrading?"""
        weekly_accuracy = []
        
        for week, trades in group_by_week(trades_by_date):
            settled = [t for t in trades if t.held_to_settlement]
            accuracy = calculate_accuracy(settled)
            weekly_accuracy.append((week, accuracy))
        
        # Check if declining trend
        recent_10_weeks = weekly_accuracy[-10:]
        trend = linear_regression([a for _, a in recent_10_weeks])
        
        if trend.slope < -0.01:  # Declining by 1%/week
            return {
                'drift_detected': True,
                'trend': trend.slope,
                'action': 'REVALIDATE_MODEL'
            }
        
        return {
            'drift_detected': False
        }
```

**Rationale:** 
Separate validation ensures strategies (stop loss, early exit) don't obscure model accuracy. Can debug which layer is failing.

**Why This Matters:**
- Model can be accurate (Track 1) but unprofitable (Track 2) → Bad strategy
- Model can be profitable (Track 2) but inaccurate (Track 1) → Getting lucky
- Both must pass for system to be sound

---

### 16. Safety Layers (Defense in Depth)

**Decision:** Multiple independent safety systems

**Layer 1: Pre-Trade Checks**
```python
def validate_trade(proposed_trade):
    """All checks must pass before trade executes"""
    checks = [
        check_sufficient_balance(proposed_trade),
        check_position_size_limits(proposed_trade),
        check_market_is_open(proposed_trade),
        check_edge_threshold_met(proposed_trade),
        check_liquidity_requirements(proposed_trade),
        check_correlation_limits(proposed_trade),
        check_not_circuit_broken(),
        check_data_freshness(),
        check_price_sanity(proposed_trade)
    ]
    
    for check in checks:
        if not check.passed:
            raise TradeBlockedError(check.reason)
    
    return True
```

**Layer 2: Circuit Breakers**
```yaml
circuit_breakers:
  daily_loss_limit:
    enabled: true
    threshold: -500.00              # $500 loss
    actions: ["halt_all_trading", "alert_critical", "require_manual_restart"]
  
  hourly_trade_limit:
    enabled: true
    threshold: 10                   # 10 trades/hour
    actions: ["pause_remainder_of_hour", "alert_warning"]
  
  api_failure_limit:
    enabled: true
    threshold: 5                    # 5 consecutive failures
    actions: ["switch_fallback", "alert_warning"]
  
  data_staleness:
    enabled: true
    threshold: 60                   # 60 seconds
    actions: ["pause_trading", "alert_warning"]
  
  position_concentration:
    enabled: true
    max_single_position_pct: 0.10  # 10% of capital
    actions: ["block_trade", "alert_warning"]
  
  rapid_loss:
    enabled: true
    threshold_pct: 0.05             # 5% loss
    time_window_seconds: 900        # In 15 minutes
    actions: ["pause_30_minutes", "alert_critical"]
```

**Layer 3: Position Monitoring**
```python
async def monitor_position(position):
    """Continuous monitoring with automatic exits"""
    while position.is_open:
        await asyncio.sleep(15)  # Check every 15 seconds
        
        # Stop loss
        if position.unrealized_pnl_pct <= -0.15:
            await close_position(position, reason="STOP_LOSS")
            continue
        
        # Profit target
        if position.unrealized_pnl_pct >= 0.20:
            await close_position(position, reason="PROFIT_TARGET")
            continue
        
        # Edge disappeared
        if position.current_edge < 0.03:
            await close_position(position, reason="EDGE_GONE")
            continue
        
        # Time-based exit
        if position.time_remaining < 60:
            await close_position(position, reason="TIME_EXPIRED")
            continue
```

**Layer 4: Reconciliation**
```python
async def daily_reconciliation():
    """
    Compare our records to Kalshi API.
    Detect discrepancies.
    """
    # Our positions
    our_positions = db.query("SELECT * FROM positions WHERE row_current_ind = TRUE")
    
    # Kalshi positions
    kalshi_positions = await kalshi_client.get_positions()
    
    # Compare
    discrepancies = []
    for our_pos in our_positions:
        kalshi_pos = find_matching(kalshi_positions, our_pos.ticker)
        
        if not kalshi_pos:
            discrepancies.append(f"We have {our_pos.ticker}, Kalshi doesn't")
        elif our_pos.quantity != kalshi_pos.quantity:
            discrepancies.append(
                f"{our_pos.ticker}: We have {our_pos.quantity}, "
                f"Kalshi has {kalshi_pos.quantity}"
            )
    
    if discrepancies:
        alert_critical("RECONCILIATION_MISMATCH", discrepancies)
        require_manual_review()
    
    return len(discrepancies) == 0
```

**Rationale:** 
Multiple independent safety systems. If one fails, others catch problems.

**Philosophy:** 
Fail-safe design. When in doubt, pause trading and require human review.

---

### 17. Scheduling: Dynamic & Event-Driven

**Decision:** Adapt polling frequency to market activity

**Game Day Scheduling (NFL Thursday/Sunday/Monday):**
```yaml
game_day:
  market_data:
    method: "websocket_primary_rest_backup"
    websocket: "realtime"
    rest_backup_interval: 60
  
  game_stats:
    method: "rest_poll"
    pregame: 300        # Every 5 min before game
    q1_q2_q3: 30        # Every 30 sec in Q1-Q3
    q4_critical: 15     # Every 15 sec in Q4
    final_2_min: 5      # Every 5 sec in final 2 min
    postgame: 600       # Every 10 min after game
  
  edge_detection:
    trigger: "on_data_update"
    throttle: 15        # Max once per 15 seconds
  
  position_monitoring:
    q1_q2_q3: 60        # Every 60 sec
    q4: 15              # Every 15 sec
    critical: 5         # Every 5 sec when pnl threshold hit
```

**Off-Season / Non-Game Days:**
```yaml
off_season:
  market_data:
    method: "rest_poll"
    interval: 300       # Every 5 min (low activity)
  
  game_stats:
    enabled: false      # No games to poll
  
  edge_detection:
    trigger: "on_new_market_discovered"
    throttle: 60
  
  position_monitoring:
    enabled: false      # No active positions
```

**Dynamic Schedule Selection:**
```python
class Scheduler:
    def get_schedule(self):
        """Determine appropriate schedule based on current state"""
        # Check if any games are active
        active_games = db.query("""
            SELECT COUNT(*) FROM game_states 
            WHERE status = 'in_progress' 
              AND row_current_ind = TRUE
        """)[0][0]
        
        if active_games > 0:
            # Game day schedule
            return self._game_day_schedule()
        
        # Check if any games starting soon
        upcoming_games = db.query("""
            SELECT COUNT(*) FROM events 
            WHERE start_time BETWEEN NOW() AND NOW() + INTERVAL '2 hours'
        """)[0][0]
        
        if upcoming_games > 0:
            # Pregame schedule
            return self._pregame_schedule()
        
        # Off-season schedule
        return self._off_season_schedule()
```

**Rationale:** 
Resource-efficient. Don't waste API calls when no games happening. Aggressive polling only when needed.

---

## Key Technology Choices

### Why PostgreSQL?
- ✅ Robust JSONB support for flexible metadata
- ✅ Excellent support for time-series data
- ✅ Strong ACID guarantees (critical for financial data)
- ✅ Native DECIMAL type (exact precision for money)
- ✅ Easy backup/restore
- ✅ Well-understood by developer

### Why Python?
- ✅ Beginner-friendly
- ✅ Excellent libraries (pandas, scipy, asyncio, decimal)
- ✅ Strong API client ecosystem
- ✅ Easy prototyping and iteration
- ✅ Good for data science / model building

### Why YAML for Config?
- ✅ Human-readable
- ✅ Comments supported
- ✅ Standard format
- ✅ Easy Git diffs
- ✅ No compilation needed
- ❌ NOT for secrets (use .env)

### Why Decimal (not Float)?
- ✅ Exact precision (critical for financial calculations)
- ✅ No rounding errors (0.43 stays 0.43, not 0.42999999)
- ✅ Required by Kalshi's sub-penny pricing
- ✅ Standard for financial applications
- ❌ Float would cause accumulating errors

---

## Architecture Patterns

### Repository Pattern
Each database table has a corresponding "repository" class:
```python
class MarketRepository:
    def get_by_id(self, market_id):
        """Fetch single market"""
        pass
    
    def get_active_markets(self, sport):
        """Fetch all active markets for sport"""
        pass
    
    def insert_market_update(self, market):
        """Insert new market state with versioning"""
        pass
    
    def get_price_history(self, market_id, start_date, end_date):
        """Get historical prices"""
        pass
```

### Service Layer
Business logic separated from data access:
```python
class EdgeDetectionService:
    def __init__(self, market_repo, odds_repo, config):
        self.market_repo = market_repo
        self.odds_repo = odds_repo
        self.config = config
    
    def calculate_edge(self, market_id):
        # Get market data
        market = self.market_repo.get_by_id(market_id)
        
        # Get corresponding odds
        odds = self.odds_repo.get_odds(
            sport=market.sport,
            state=market.game_state
        )
        
        # Calculate edge
        true_prob = odds.win_probability
        market_price = market.yes_bid
        edge = true_prob - market_price
        
        return edge
```

### Configuration Injection
All services receive config via dependency injection:
```python
# At startup
config = Config()
market_repo = MarketRepository(db_connection)
odds_repo = OddsRepository(db_connection)
edge_service = EdgeDetectionService(market_repo, odds_repo, config)

# Service can access config
min_edge = edge_service.config.get('trading.nfl.confidence.auto_execute_threshold')
```

---

## Known Trade-offs

### Versioned Tables = Storage Cost
- **Pro:** Complete historical analysis possible
- **Con:** Database grows ~18 GB/year
- **Mitigation:** Archival strategy (hot 18 months, warm 3.5 years, cold 10 years)
- **Verdict:** Worth it for analysis capabilities

### Separate YAML Files = More Files
- **Pro:** Clear separation, better Git diffs, easier to understand
- **Con:** More files to track, could be consolidated
- **Mitigation:** Clear naming, README in config/ explaining structure
- **Verdict:** Worth it for maintainability

### Platform Abstraction = Complexity
- **Pro:** Easy to add Polymarket later, clean code
- **Con:** Extra abstraction layer, more code
- **Mitigation:** Well-documented interfaces, clear patterns
- **Verdict:** Worth it for Phase 10 multi-platform expansion

### Conservative Kelly Fraction (0.25) = Lower Returns
- **Pro:** Reduced volatility and drawdowns, safer
- **Con:** Slower compounding, less aggressive growth
- **Mitigation:** Acceptable for risk management, can tune later
- **Verdict:** Start conservative, increase if system proves robust

### DECIMAL vs Float = Slightly Slower
- **Pro:** Exact precision, no rounding errors
- **Con:** DECIMAL operations slightly slower than float
- **Mitigation:** Performance difference negligible for our use case
- **Verdict:** Correctness > speed for financial calculations

### Separate Non-Sports Odds Tables = More Maintenance
- **Pro:** Optimal schema for each category
- **Con:** More tables, category-specific code
- **Mitigation:** Worth it to avoid forcing incompatible data into unified schema
- **Verdict:** Unify similar data (sports), separate dissimilar (politics)

---

## Decision Log (Chronological)

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-10-07 | Use PostgreSQL | ACID, JSONB, time-series support |
| 2025-10-07 | Python 3.12+ | Beginner-friendly, great libraries |
| 2025-10-07 | YAML configuration | Human-readable, version control |
| 2025-10-07 | Three-tier config priority | Flexibility + safety |
| 2025-10-08 | **DECIMAL pricing (not INTEGER)** | **Kalshi transitioning to sub-penny** |
| 2025-10-08 | Separate trade strategies from position management | Separation of concerns |
| 2025-10-08 | Platform abstraction layer | Future multi-platform support |
| 2025-10-08 | Separate odds tables for non-sports | Data too dissimilar to unify |
| 2025-10-08 | WebSocket + REST hybrid | Reliability + performance |
| 2025-10-08 | Three-tier correlation detection | Risk management |

---

## Future Considerations

### Phase 6: Cloud Migration
- **Decision Needed:** AWS vs. GCP vs. Azure
- **Leaning Toward:** AWS (RDS for PostgreSQL, ECS for compute)
- **Timeline:** After successful demo trading

### Phase 8: Non-Sports Categories
- **Decision Needed:** How much to invest in politics/entertainment odds models
- **Consideration:** Sports have more structured data (easier models)
- **Timeline:** After multi-sport success

### Phase 10: Multi-Platform
- **Decision Needed:** Support PredictIt, Augur, others beyond Polymarket?
- **Consideration:** Each platform = integration work + maintenance
- **Recommendation:** Start with Kalshi + Polymarket, add others if profitable

### Phase 13+: Community Features
- **Decision Needed:** Open source core? Premium features?
- **Consideration:** Business model vs. community benefit
- **Timeline:** Far future (1-2 years)

---

## Lessons for Future Developers

### What Worked Well in Design
1. ✅ **Documentation first** - Prevented costly refactoring
2. ✅ **Decimal precision** - Future-proof for Kalshi changes
3. ✅ **Platform abstraction** - Polymarket will be easy to add
4. ✅ **Versioning strategy** - Tracks price/state history correctly
5. ✅ **Safety mindset** - Circuit breakers, validation, defense-in-depth

### Common Pitfalls to Avoid
1. ❌ **Don't use float for prices** - Use Decimal
2. ❌ **Don't parse deprecated integer cent fields** - Use *_dollars fields
3. ❌ **Don't forget row_current_ind on versioned tables** - Queries will be slow
4. ❌ **Don't use singular table names** - Use plural (markets not market)
5. ❌ **Don't skip validation** - Always validate prices are in range

### When to Reconsider Decisions
- **Versioning strategy:** If storage becomes expensive (>$100/month)
- **Conservative Kelly:** If system proves very accurate (>70% win rate)
- **Separate odds tables:** If non-sports categories share more structure than expected
- **Platform abstraction:** If we never add more platforms (YAGNI principle)

---

## Approval & Sign-off

This document represents the architectural decisions as of October 8, 2025 (Phase 0 completion).

**Approved By:** Project Lead  
**Date:** October 8, 2025  
**Next Review:** Before Phase 8 (Non-Sports Expansion)

---

**Document Version:** 2.3
**Last Updated:** October 16, 2025
**Critical Changes:**
- v2.3: Updated YAML file reference (odds_models.yaml → probability_models.yaml)
- v2.2: Added Decision #14 (Terminology Standards), updated all "odds" references to "probability"
- v2.0: **DECIMAL(10,4) pricing (not INTEGER)** - Fixes critical inconsistency
- v2.0: Added cross-platform selection strategy, correlation detection, WebSocket state management

**Purpose:** Record and rationale for all major architectural decisions
