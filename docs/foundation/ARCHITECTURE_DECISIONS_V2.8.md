# Architecture & Design Decisions

---
**Version:** 2.8
**Last Updated:** October 29, 2025
**Status:** ✅ Current
**Changes in v2.8:**
- **PHASE 0.6C COMPLETION:** Added Decisions #33-36/ADR-038-041 (Validation & Testing Infrastructure - Complete)
- **PHASE 0.7 PLANNING:** Added Decisions #37-40/ADR-042-045 (CI/CD Integration & Advanced Testing - Planned)
- Added ADR-038: Ruff for Code Quality Automation (10-100x faster than black+flake8)
- Added ADR-039: Test Result Persistence Strategy (timestamped HTML reports)
- Added ADR-040: Documentation Validation Automation (validate_docs.py prevents drift)
- Added ADR-041: Layered Validation Architecture (fast 3s + comprehensive 60s)
- Added ADR-042: CI/CD Integration with GitHub Actions (Phase 0.7 planned)
- Added ADR-043: Security Testing Integration with Bandit/Safety (Phase 0.7 planned)
- Added ADR-044: Mutation Testing Strategy (Phase 0.7 planned)
- Added ADR-045: Property-Based Testing with Hypothesis (Phase 0.7 planned)
**Changes in v2.7:**
- **PHASE 0.6B DOCUMENTATION:** Updated all supplementary specification document references to standardized filenames
- **PHASE 5 PLANNING:** Added Decisions #30-32/ADR-035-037 (Phase 5 Trading Architecture)
- Added ADR-035: Event Loop Architecture (async/await for real-time trading)
- Added ADR-036: Exit Evaluation Strategy (priority hierarchy for 10 exit conditions)
- Added ADR-037: Advanced Order Walking (multi-stage price walking with urgency levels)
- Updated ADR references to point to standardized supplementary specs (EVENT_LOOP_ARCHITECTURE_V1.0.md, EXIT_EVALUATION_SPEC_V1.0.md, ADVANCED_EXECUTION_SPEC_V1.0.md)
**Changes in v2.6:**
- **PHASE 1 COMPLETION:** Added Decisions #24-29/ADR-029-034 (Database Schema Completion)
- Added ADR-029: Elo Data Source (game_states over settlements)
- Added ADR-030: Elo Ratings Storage (teams table over probability_models.config)
- Added ADR-031: Settlements Architecture (separate table over markets columns)
- Added ADR-032: Markets Surrogate PRIMARY KEY (id SERIAL over market_id VARCHAR)
- Added ADR-033: External ID Traceability Pattern
- Added ADR-034: SCD Type 2 Completion (row_end_ts on all versioned tables)
**Changes in v2.5:**
- **STANDARDIZATION:** Added systematic ADR numbers to all architecture decisions
- Mapped all decisions to ADR-{NUMBER} format for traceability
- Added cross-references to ADR_INDEX.md
- Maintained all existing content from V2.4

**Changes in v2.4:**
- **CRITICAL:** Added Decision #18/ADR-018: Immutable Versions (Phase 0.5 - foundational architectural decision)
- Added Decision #19/ADR-019-028: Strategy & Model Versioning
- Added Decision #20/ADR-019: Trailing Stop Loss
- Added Decision #21: Enhanced Position Management
- Added Decision #22: Configuration System Enhancements
- Added Decision #23: Phase 0.5 vs Phase 1/1.5 Split
- Updated Decision #2: Database Versioning Strategy to include immutable version pattern

**Changes in v2.3:**
- Updated YAML file reference from `odds_models.yaml` to `probability_models.yaml`

**Changes in v2.2:**
- **NEW:** Added Decision #14/ADR-016: Terminology Standards (probability vs. odds vs. price)
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

**For comprehensive ADR catalog, see ADR_INDEX.md**

---

## Critical Design Decisions (With Rationale)

### ADR-002: Price Precision - DECIMAL(10,4) for All Prices

**Decision #1**

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

### ADR-003: Database Versioning Strategy (SCD Type 2)

**Decision #2**

**Decision:** Use `row_current_ind` for frequently-changing data, append-only for historical records, and **immutable versions** for strategies and models

**Pattern 1: Versioned Data (row_current_ind = TRUE/FALSE)**
Used for frequently-changing data that needs historical tracking:
- `markets` - Prices change every 15-30 seconds
- `game_states` - Scores update every 30 seconds
- `positions` - Quantity and trailing stop state changes
- `edges` - Recalculated frequently as odds/prices change
- `account_balance` - Changes with every trade

**Pattern 2: Append-Only Tables (No Versioning)**
Used for immutable historical records:
- `trades` - Immutable historical record
- `settlements` - Final outcomes, never change
- `probability_matrices` - Static historical probability data
- `platforms` - Configuration data, rarely changes
- `series` - Updated in-place, no history needed
- `events` - Status changes are lifecycle transitions, no history needed

**Pattern 3: Immutable Versions (ADR-018)**
Used for strategies and models that require A/B testing and precise trade attribution:
- `strategies` - Trading strategy versions (config is IMMUTABLE)
- `probability_models` - ML model versions (config is IMMUTABLE)

**Immutable Version Details:**
- Each version (v1.0, v1.1, v2.0) is IMMUTABLE once created
- Config/parameters NEVER change after creation
- To update: Create new version (v1.0 → v1.1 for bug fix, v1.0 → v2.0 for major change)
- Only `status` and metrics update in-place (draft → active, performance tracking)
- NO `row_current_ind` field (versions don't supersede each other)
- Enables precise A/B testing and trade attribution

**Rationale:**
Balance between historical tracking needs and database bloat. Three patterns for three use cases:
1. **Versioned data (row_current_ind):** Efficient for rapidly-changing data (prices, scores)
2. **Append-only:** Simple for immutable records (trades, settlements)
3. **Immutable versions:** Required for A/B testing integrity and exact trade attribution

Examples:
- We need historical prices to analyze how market moved (Pattern 1)
- We DON'T need historical series data (Pattern 2)
- We need EXACT strategy config that generated each trade (Pattern 3)

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

**Related ADRs:**
- ADR-018: Immutable Versions (Pattern 3)
- ADR-020: Trade Attribution Links
- ADR-022: Helper Views for Active Versions

---

### ADR-013: Material Change Threshold

**Decision #3**

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

### API Integration Strategy: WebSocket + REST Hybrid

**Decision #4**

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

**Related ADRs:**
- See Decision #13: WebSocket State Management

---

### ADR-001: Authentication Method - RSA-PSS Signatures

**Decision #5**

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

### ADR-004: Configuration System - Three-Tier Priority

**Decision #6**

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

**Related ADRs:**
- ADR-009: Environment Variables for Secrets
- ADR-017: Method Abstraction Pattern for YAMLs

---

### Trade Strategies vs. Position Management (Clear Separation)

**Decision #7**

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

**Related ADRs:**
- ADR-023-028: Position Monitoring & Exit Management

---

### Unified Probability Matrix Design (Platform-Agnostic)

**Decision #8**

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

### ADR-009: Multi-Environment Support

**Decision #9**

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

### ADR-007: Platform Abstraction Layer

**Decision #10**

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

### Cross-Platform Market Selection Strategy

**Decision #11**

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

### Correlation Detection and Limits

**Decision #12**

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

### WebSocket State Management

**Decision #13**

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

### ADR-016: Terminology Standards: Probability vs. Odds vs. Price

**Decision #14**

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
- Decision #1/ADR-002: Price Precision (DECIMAL for exact probability representation)
- See GLOSSARY.md for comprehensive terminology guide

---

### Model Validation Strategy (Four Tracks)

**Decision #15**

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

### Safety Layers (Defense in Depth)

**Decision #16**

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

### Scheduling: Dynamic & Event-Driven

**Decision #17**

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

### ADR-018: Immutable Versions (CRITICAL - Phase 0.5)

**Decision #18**

**Decision:** Strategy and model configs are IMMUTABLE once version is created. To change config, create new version.

**What's IMMUTABLE:**
- `strategies.config` - Strategy parameters (e.g., `{min_lead: 7}`)
- `probability_models.config` - Model hyperparameters (e.g., `{k_factor: 28}`)
- `strategy_version` and `model_version` fields - Version numbers

**What's MUTABLE:**
- `status` field - Lifecycle transitions (draft → testing → active → deprecated)
- Performance metrics - `paper_roi`, `live_roi`, `validation_accuracy` (accumulate over time)

**Rationale:**
1. **A/B Testing Integrity** - Cannot compare v1.0 vs v2.0 if configs change after comparison starts
2. **Trade Attribution** - Every trade links to EXACT strategy/model config used, never ambiguous
3. **Semantic Versioning** - v1.0 → v1.1 (bug fix), v1.0 → v2.0 (major change) is industry standard
4. **Reproducibility** - Can always recreate exact trading decision that generated historical trade

**Example:**
```sql
-- Original strategy
INSERT INTO strategies (strategy_name, strategy_version, config, status)
VALUES ('halftime_entry', 'v1.0', '{"min_lead": 7, "max_spread": 0.08}', 'active');

-- Bug fix: min_lead should be 10 → Create v1.1 (NEVER update v1.0 config)
INSERT INTO strategies (strategy_name, strategy_version, config, status)
VALUES ('halftime_entry', 'v1.1', '{"min_lead": 10, "max_spread": 0.08}', 'active');

-- Update v1.0 status (config stays unchanged forever)
UPDATE strategies SET status = 'deprecated' WHERE strategy_name = 'halftime_entry' AND strategy_version = 'v1.0';

-- Metrics update is allowed
UPDATE strategies SET paper_roi = 0.15, paper_trades_count = 42
WHERE strategy_name = 'halftime_entry' AND strategy_version = 'v1.1';
```

**Trade Attribution:**
```sql
-- Every trade knows EXACTLY which strategy config and model config generated it
SELECT
    t.trade_id,
    t.price,
    s.strategy_name,
    s.strategy_version,
    s.config as strategy_config,
    m.model_name,
    m.model_version,
    m.config as model_config
FROM trades t
JOIN strategies s ON t.strategy_id = s.strategy_id
JOIN probability_models m ON t.model_id = m.model_id;
```

**Impact:**
- Database schema V1.5 applied (strategies and probability_models tables created)
- NO `row_current_ind` in these tables (versions don't supersede each other)
- Unique constraint on `(name, version)` enforces no duplicates
- Phase 4 (models) and Phase 5 (strategies) will implement version creation logic
- Every edge and trade must link to strategy_id and model_id (enforced by FK)

**Why NOT row_current_ind?**
- row_current_ind is for data that changes frequently (prices, scores)
- Versions are configs that NEVER change, they're alternatives not updates
- Multiple versions can be "active" simultaneously for A/B testing

**Related ADRs:**
- ADR-003: Database Versioning Strategy (updated to include immutable version pattern)
- ADR-019-021: Strategy & Model Versioning (implementation details)
- ADR-020: Trade Attribution Links

---

### ADR-021: Strategy & Model Versioning Patterns

**Decision #19**

**Decision:** Implement versioning system for strategies and models using semantic versioning (MAJOR.MINOR format).

**Version Numbering:**
- **v1.0** - Initial version
- **v1.1** - Bug fix or minor parameter tuning (backwards compatible)
- **v2.0** - Major change in approach or algorithm (breaking change)

**Lifecycle States:**
```
draft → testing → active → inactive → deprecated
  ↓        ↓         ↓
(Paper) (Paper) (Live Trading)
```

**For Probability Models:**
```sql
CREATE TABLE probability_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR NOT NULL,         -- 'elo_nfl', 'regression_nba'
    model_version VARCHAR NOT NULL,      -- 'v1.0', 'v1.1', 'v2.0'
    model_type VARCHAR NOT NULL,         -- 'elo', 'regression', 'ensemble', 'ml'
    sport VARCHAR,                       -- 'nfl', 'nba', 'mlb' (NULL for multi-sport)
    config JSONB NOT NULL,               -- ⚠️ IMMUTABLE: Model hyperparameters
    status VARCHAR DEFAULT 'draft',      -- ✅ MUTABLE: Lifecycle
    validation_accuracy DECIMAL(10,4),   -- ✅ MUTABLE: Performance metrics
    UNIQUE(model_name, model_version)
);
```

**For Strategies:**
```sql
CREATE TABLE strategies (
    strategy_id SERIAL PRIMARY KEY,
    strategy_name VARCHAR NOT NULL,      -- 'halftime_entry', 'underdog_fade'
    strategy_version VARCHAR NOT NULL,   -- 'v1.0', 'v1.1', 'v2.0'
    strategy_type VARCHAR NOT NULL,      -- 'entry', 'exit', 'sizing', 'hedging'
    sport VARCHAR,                       -- 'nfl', 'nba', 'mlb' (NULL for multi-sport)
    config JSONB NOT NULL,               -- ⚠️ IMMUTABLE: Strategy parameters
    status VARCHAR DEFAULT 'draft',      -- ✅ MUTABLE: Lifecycle
    paper_roi DECIMAL(10,4),             -- ✅ MUTABLE: Performance metrics
    live_roi DECIMAL(10,4),
    UNIQUE(strategy_name, strategy_version)
);
```

**Phase Distribution:**
- **Phase 1:** Schema created (V1.5 applied)
- **Phase 4:** Model versioning logic implemented (create models, validate, compare versions)
- **Phase 5:** Strategy versioning logic implemented (create strategies, test, compare versions)
- **Phase 9:** Use existing system (create more models, don't rebuild versioning)

**Rationale:**
- Phase 4 is where models are created/validated → Model versioning belongs here
- Phase 5 is where strategies are created/tested → Strategy versioning belongs here
- Phase 9 just adds more models using the system built in Phase 4

**Implementation Modules:**
- `analytics/model_manager.py` - CRUD operations for probability_models, version validation
- `trading/strategy_manager.py` - CRUD operations for strategies, version validation
- Both enforce immutability (raise error if config update attempted)

**Related ADRs:**
- ADR-018: Immutable Versions (foundational decision)
- ADR-020: Trade Attribution Links

---

### ADR-019: Trailing Stop Loss (JSONB State)

**Decision #20**

**Decision:** Implement dynamic trailing stop loss stored as JSONB in positions table.

**Schema:**
```sql
ALTER TABLE positions ADD COLUMN trailing_stop_state JSONB;

-- Example trailing_stop_state:
{
  "enabled": true,
  "activation_price": 0.7500,      -- Price at which trailing stop activated
  "stop_distance": 0.0500,         -- Distance to maintain (5 cents)
  "current_stop": 0.7000,          -- Current stop loss price
  "highest_price": 0.7500          -- Highest price seen since activation
}
```

**Logic:**
1. **Initialization** - When position opened, set activation_price = entry_price
2. **Monitoring** - As market price moves favorably, update highest_price
3. **Stop Update** - current_stop = highest_price - stop_distance
4. **Trigger** - If market_price falls to current_stop, close position

**Example:**
```
Entry: $0.70
Stop Distance: $0.05

Price moves to $0.75 → highest_price = 0.75, current_stop = 0.70 (entry)
Price moves to $0.80 → highest_price = 0.80, current_stop = 0.75 (locked $0.05 profit)
Price moves to $0.85 → highest_price = 0.85, current_stop = 0.80 (locked $0.10 profit)
Price falls to $0.80 → TRIGGERED, sell position (realize $0.10 profit)
```

**Configuration (position_management.yaml):**
```yaml
trailing_stops:
  default:
    enabled: true
    activation_threshold: 0.0500    # Activate after $0.05 profit
    stop_distance: 0.0500           # Maintain $0.05 trailing distance

  strategy_overrides:
    halftime_entry:
      stop_distance: 0.0400         # Tighter stop for this strategy
```

**Rationale:**
- Protects profits on winning positions
- Removes emotion from exit decisions
- Configurable per strategy
- JSONB allows flexible configuration without schema changes

**Impact:**
- Positions use row_current_ind versioning (trailing stop updates trigger new row)
- position_manager.py implements update logic
- Stop trigger detection runs every 15-60 seconds depending on game state

**Related ADRs:**
- ADR-023: Position Monitoring Architecture

---

### Enhanced Position Management

**Decision #21**

**Decision:** Centralize position management logic in `trading/position_manager.py` with trailing stop integration.

**Core Responsibilities:**
1. **Position Lifecycle**
   - Create position on trade execution
   - Initialize trailing_stop_state
   - Monitor position P&L
   - Update trailing stops on price movement
   - Detect stop triggers
   - Close positions (stop loss, settlement, manual)

2. **Trailing Stop Management**
   - Update highest_price as market moves favorably
   - Calculate new current_stop = highest_price - stop_distance
   - Trigger stop loss order when price falls to current_stop
   - Log all stop updates for analysis

3. **Position Monitoring**
   - Query current positions (WHERE row_current_ind = TRUE AND status = 'open')
   - Calculate unrealized P&L
   - Check for stop triggers
   - Alert on significant P&L changes

**Implementation Pattern:**
```python
class PositionManager:
    def create_position(self, market_id, side, entry_price, quantity, strategy_id, model_id):
        """Create new position with trailing stop initialization"""
        trailing_stop_state = {
            "enabled": self.config.trailing_stops.enabled,
            "activation_price": entry_price,
            "stop_distance": self.config.trailing_stops.stop_distance,
            "current_stop": entry_price - self.config.trailing_stops.stop_distance,
            "highest_price": entry_price
        }
        # Insert position with trailing_stop_state

    def update_trailing_stop(self, position_id, current_market_price):
        """Update trailing stop if price moved favorably"""
        position = self.get_position(position_id)
        old_state = position.trailing_stop_state

        if current_market_price > old_state["highest_price"]:
            # Price moved up, update trailing stop
            new_state = {
                ...old_state,
                "highest_price": current_market_price,
                "current_stop": current_market_price - old_state["stop_distance"]
            }
            # Insert new position row with updated trailing_stop_state

    def check_stop_trigger(self, position_id, current_market_price):
        """Check if trailing stop triggered"""
        position = self.get_position(position_id)
        if current_market_price <= position.trailing_stop_state["current_stop"]:
            return True  # Trigger stop loss
        return False
```

**Rationale:**
- Centralized position logic prevents duplication
- Trailing stops are first-class feature, not bolt-on
- JSONB state allows flexible configuration per position
- Position versioning (row_current_ind) tracks stop updates over time

**Related ADRs:**
- ADR-019: Trailing Stop Loss (what to track)
- ADR-023-028: Position Monitoring & Exit Management

---

### ADR-017: Configuration System Enhancements

**Decision #22**

**Decision:** Enhance YAML configuration system to support versioning and trailing stop configurations.

**New Configuration Files:**
1. **probability_models.yaml** - Model version settings
   ```yaml
   models:
     elo_nfl:
       default_version: "v2.0"
       active_versions:
         - "v2.0"
         - "v1.1"    # For A/B testing
       config_overrides:
         v2_0:
           k_factor: 30
   ```

2. **trade_strategies.yaml** - Strategy version settings
   ```yaml
   strategies:
     halftime_entry:
       default_version: "v1.1"
       active_versions:
         - "v1.1"
         - "v1.0"    # For A/B testing
       config_overrides:
         v1_1:
           min_lead: 10
   ```

3. **position_management.yaml** - Enhanced with trailing stops
   ```yaml
   trailing_stops:
     default:
       enabled: true
       activation_threshold: 0.0500
       stop_distance: 0.0500
     strategy_overrides:
       halftime_entry:
         stop_distance: 0.0400
   ```

**Configuration Loader (utils/config.py):**
```python
class ConfigManager:
    def __init__(self):
        self.trading = self.load_yaml('config/trading.yaml')
        self.strategies = self.load_yaml('config/trade_strategies.yaml')
        self.position_mgmt = self.load_yaml('config/position_management.yaml')
        self.models = self.load_yaml('config/probability_models.yaml')
        self.markets = self.load_yaml('config/markets.yaml')
        self.data_sources = self.load_yaml('config/data_sources.yaml')
        self.system = self.load_yaml('config/system.yaml')

    def get_active_strategy_version(self, strategy_name):
        """Get default active version for strategy"""
        return self.strategies['strategies'][strategy_name]['default_version']

    def get_trailing_stop_config(self, strategy_name):
        """Get trailing stop configuration for strategy"""
        default = self.position_mgmt['trailing_stops']['default']
        overrides = self.position_mgmt['trailing_stops']['strategy_overrides'].get(strategy_name, {})
        return {**default, **overrides}
```

**Rationale:**
- YAML configuration for defaults, database for runtime overrides
- Strategy/model versions configured in YAML, actual version configs in database
- Trailing stop defaults in YAML, per-position state in database JSONB
- Centralized config loading prevents scattered configuration logic

**Priority Order (unchanged):**
1. Database overrides (highest)
2. Environment variables
3. YAML files
4. Code defaults (lowest)

---

### Phase 0.5 vs Phase 1/1.5 Split

**Decision #23**

**Decision:** Insert Phase 0.5 (Foundation Enhancement) and Phase 1.5 (Foundation Validation) between Phase 0 and Phase 2.

**Phase Distribution:**
- **Phase 0:** Foundation & Documentation (completed)
- **Phase 0.5:** Foundation Enhancement (database schema V1.5, docs) - **COMPLETED**
- **Phase 1:** Core Foundation (Kalshi API, basic tables)
- **Phase 1.5:** Foundation Validation (test versioning system before building on it)
- **Phase 2+:** Remaining phases unchanged

**Why Phase 0.5 BEFORE Phase 1?**
1. **Schema Must Be Final** - Cannot add versioning tables after Phase 1 code written
2. **Documentation First** - All docs must reflect final schema before implementation
3. **Prevents Refactoring** - Adding versioning later = rewrite Phases 1-4
4. **Foundation Quality** - Better to have complete foundation before writing code

**What Phase 0.5 Delivers:**
- ✅ Database schema V1.5 (strategies, probability_models, trailing_stop_state, version FKs)
- ✅ Complete documentation updates (10-day plan)
- ✅ Architectural decisions documented (ADR-018 through ADR-028)
- ✅ Implementation guides (VERSIONING_GUIDE_V1.0.md, TRAILING_STOP_GUIDE_V1.0.md, POSITION_MANAGEMENT_GUIDE_V1.0.md)

**Why Phase 1.5 AFTER Phase 1?**
1. **Validation Before Complexity** - Test versioning system before Phase 2 complexity
2. **Manager Classes** - Build strategy_manager and model_manager to validate schema
3. **Configuration System** - Test YAML loading and version resolution
4. **Unit Tests** - Write tests for immutability enforcement before building on it

**What Phase 1.5 Delivers:**
- strategy_manager.py - CRUD operations for strategies, version validation
- model_manager.py - CRUD operations for probability_models, version validation
- position_manager.py enhancements - Trailing stop initialization and updates
- config.py enhancements - YAML loading for versioning configs
- Unit tests for versioning, trailing stops, configuration

**Rationale:**
- Inserting phases prevents cascading changes to later phases
- Phase 0.5 enhances foundation, doesn't replace Phase 1
- Phase 1.5 validates foundation, then Phase 2 builds on it
- Clear separation: schema (0.5), basic API (1), validation (1.5), market data (2)

**Documentation:**
- CLAUDE_CODE_IMPLEMENTATION_PLAN.md - Full Phase 0.5 details
- PHASE_1.5_PLAN.md - Validation tasks and acceptance criteria
- MASTER_REQUIREMENTS.md - Updated phase descriptions

---

## Key Technology Choices

### ADR-001: Why PostgreSQL?
- ✅ Robust JSONB support for flexible metadata
- ✅ Excellent support for time-series data
- ✅ Strong ACID guarantees (critical for financial data)
- ✅ Native DECIMAL type (exact precision for money)
- ✅ Easy backup/restore
- ✅ Well-understood by developer

### ADR-005: Why Python?
- ✅ Beginner-friendly
- ✅ Excellent libraries (pandas, scipy, asyncio, decimal)
- ✅ Strong API client ecosystem
- ✅ Easy prototyping and iteration
- ✅ Good for data science / model building

### ADR-004: Why YAML for Config?
- ✅ Human-readable
- ✅ Comments supported
- ✅ Standard format
- ✅ Easy Git diffs
- ✅ No compilation needed
- ❌ NOT for secrets (use .env)

### ADR-002: Why Decimal (not Float)?
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
    def __init__(self, market_repo, probability_repo, config):
        self.market_repo = market_repo
        self.probability_repo = probability_repo
        self.config = config

    def calculate_edge(self, market_id):
        # Get market data
        market = self.market_repo.get_by_id(market_id)

        # Get corresponding probabilities
        probability = self.probability_repo.get_probability(
            sport=market.sport,
            state=market.game_state
        )

        # Calculate edge
        true_prob = probability.win_probability
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
probability_repo = ProbabilityRepository(db_connection)
edge_service = EdgeDetectionService(market_repo, probability_repo, config)

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

### Separate Non-Sports Probability Tables = More Maintenance
- **Pro:** Optimal schema for each category
- **Con:** More tables, category-specific code
- **Mitigation:** Worth it to avoid forcing incompatible data into unified schema
- **Verdict:** Unify similar data (sports), separate dissimilar (politics)

---

## Decision Log (Chronological with ADR Numbers)

| Date | Decision | ADR | Rationale |
|------|----------|-----|-----------|
| 2025-10-07 | Use PostgreSQL | ADR-001 | ACID, JSONB, time-series support |
| 2025-10-07 | Python 3.12+ | ADR-005 | Beginner-friendly, great libraries |
| 2025-10-07 | YAML configuration | ADR-004 | Human-readable, version control |
| 2025-10-07 | Three-tier config priority | ADR-004 | Flexibility + safety |
| 2025-10-08 | **DECIMAL pricing (not INTEGER)** | ADR-002 | **Kalshi transitioning to sub-penny** |
| 2025-10-08 | Separate trade strategies from position management | - | Separation of concerns |
| 2025-10-08 | Platform abstraction layer | ADR-007 | Future multi-platform support |
| 2025-10-08 | Separate probability tables for non-sports | - | Data too dissimilar to unify |
| 2025-10-08 | WebSocket + REST hybrid | - | Reliability + performance |
| 2025-10-08 | Three-tier correlation detection | - | Risk management |
| 2025-10-16 | Terminology: Probability not Odds | ADR-016 | Technical accuracy, clarity |
| 2025-10-19 | Immutable Versions | ADR-018 | A/B testing, trade attribution |
| 2025-10-19 | Trailing Stop Loss | ADR-019 | Profit protection |
| 2025-10-21 | Position Monitoring (30s/5s) | ADR-023 | API efficiency, responsiveness |
| 2025-10-21 | Exit Priority Hierarchy | ADR-024 | Systematic exit management |
| 2025-10-22 | Standardization with ADR numbers | - | Traceability |

---

## Future Considerations

### Phase 6: Cloud Migration
- **Decision Needed:** AWS vs. GCP vs. Azure
- **Leaning Toward:** AWS (RDS for PostgreSQL, ECS for compute)
- **Timeline:** After successful demo trading

### Phase 8: Non-Sports Categories
- **Decision Needed:** How much to invest in politics/entertainment probability models
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

## Decision #24/ADR-029: Elo Data Source - game_states over settlements

**Date:** October 24, 2025
**Phase:** 1 (Database Completion)
**Status:** ✅ Accepted

### Problem
Elo rating systems need game outcome data (which team won) to update team ratings. Three potential data sources:
1. `game_states` table (ESPN/external feeds) - home_score vs away_score
2. `settlements` table (Kalshi API) - market outcomes
3. `events.result` JSONB - event outcome data

Which should be the authoritative source for Elo updates?

### Decision
**Use `game_states` table (ESPN/external feeds) as primary Elo data source.**

Query pattern:
```sql
SELECT home_team, away_team, home_score, away_score
FROM game_states
WHERE status = 'final' AND row_current_ind = TRUE;
```

### Rationale
1. **Data Independence**: Not dependent on Kalshi having markets for every game
2. **Clear Semantics**: `home_score > away_score` is unambiguous (no string parsing)
3. **Source of Truth**: ESPN feeds are authoritative for sports scores
4. **Complete Coverage**: Can calculate Elo for all teams, not just games we traded on
5. **No Market Dependency**: Works even if Kalshi doesn't create a market

**Rejected Alternative**: Using `settlements` would require:
- Finding "Will [team] win?" market (fragile string matching)
- Parsing team name from market.title
- Only works for games where Kalshi created markets
- outcome='yes' doesn't directly indicate which team won

### Implementation
- Cross-validate `game_states` winner against `settlements` outcome
- Flag discrepancies for manual review
- Use settlements as validation check, not primary source

**Reference:** ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0.md

---

## Decision #25/ADR-030: Elo Ratings Storage - teams Table

**Date:** October 24, 2025
**Phase:** 1 (Database Completion)
**Status:** ✅ Accepted

### Problem
Elo ratings are mutable values that change after every game. Two storage options:
1. Store in `probability_models.config` JSONB (current pattern for model data)
2. Create dedicated `teams` table with `current_elo_rating` column

### Decision
**Create `teams` table with mutable `current_elo_rating` column.**

Schema:
```sql
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_code VARCHAR(10) NOT NULL UNIQUE,
    current_elo_rating DECIMAL(10,2),  -- Mutable
    ...
);

CREATE TABLE elo_rating_history (
    history_id SERIAL PRIMARY KEY,
    team_id INT REFERENCES teams(team_id),
    rating_before DECIMAL(10,2),
    rating_after DECIMAL(10,2),
    game_result VARCHAR,
    ...
);
```

### Rationale
1. **Semantic Correctness**: Elo ratings are TEAM attributes, not MODEL attributes
2. **Preserves Immutability**: Keeps `probability_models.config` IMMUTABLE as designed
3. **Clear Separation**:
   - `probability_models.config` stores MODEL PARAMETERS (k_factor=30, initial_rating=1500)
   - `teams.current_elo_rating` stores TEAM RATINGS (KC=1580, BUF=1620)
4. **Simpler Queries**: `teams.current_elo_rating` vs `config->>'KC'`
5. **Better Performance**: Indexed DECIMAL column vs JSONB extraction
6. **Future Needs**: teams table needed anyway for team metadata, external IDs

**Rejected Alternative**: Storing in `probability_models.config` would:
- Violate immutability design pattern
- Require new version for every game (256+ versions per NFL season)
- Confuse MODEL config with TEAM state
- Slower JSONB queries

### Implementation
- `probability_models` stores: `{"k_factor": 30, "initial_rating": 1500}`
- `teams` stores: current Elo ratings (1370-1660)
- `elo_rating_history` provides complete audit trail

**Reference:** ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0.md, Migration 010

---

## Decision #26/ADR-031: Settlements as Separate Table

**Date:** October 24, 2025
**Phase:** 1 (Database Completion)
**Status:** ✅ Accepted

### Problem
Settlements represent final market outcomes. Two architectural options:
1. Separate `settlements` table (current design)
2. Add columns to `markets` table (settlement_outcome, settlement_payout, etc.)

### Decision
**Keep `settlements` as separate table.**

### Rationale
1. **Normalization**: Settlement is an EVENT that happens to a market, not market STATE
2. **SCD Type 2 Compatibility**: Avoids duplicating settlement data across market versions
3. **Multi-Platform Support**: Same event can settle differently on different platforms
4. **Clean Append-Only**: settlements table is pure audit trail
5. **Query Clarity**: Easy to query "all settlements" or "unsettled markets"

**Rejected Alternative**: Adding columns to markets would:
- Duplicate settlement data if market updated after settlement (SCD Type 2 issue)
- Create 5+ nullable columns for all unsettled markets
- Unclear semantics (is settlement part of market state or separate event?)
- Harder to model same event settling differently on different platforms

### Implementation
- `markets.status = 'settled'` indicates settlement
- `markets.settlement_value` stores final value for quick reference
- `settlements` table stores complete details (outcome, payout, external_id, api_response)

**Reference:** ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0.md

---

## Decision #27/ADR-032: Markets Surrogate PRIMARY KEY

**Date:** October 24, 2025
**Phase:** 1 (Database Completion)
**Status:** ✅ Accepted

### Problem
`markets` table used business key (`market_id VARCHAR`) as PRIMARY KEY. SCD Type 2 requires multiple rows with same `market_id` (different versions), but PRIMARY KEY prevents duplicates.

### Decision
**Replace business key PRIMARY KEY with surrogate key (`id SERIAL`).**

Schema changes:
```sql
-- Old: market_id VARCHAR PRIMARY KEY
-- New: id SERIAL PRIMARY KEY
ALTER TABLE markets ADD COLUMN id SERIAL PRIMARY KEY;
ALTER TABLE markets DROP CONSTRAINT markets_pkey;

-- Enforce one current version per business key
CREATE UNIQUE INDEX idx_markets_unique_current
ON markets(market_id) WHERE row_current_ind = TRUE;

-- Update FK tables
ALTER TABLE edges ADD COLUMN market_uuid INT REFERENCES markets(id);
-- Similar for positions, trades, settlements
```

### Rationale
1. **Enables SCD Type 2**: Multiple versions can have same market_id, different surrogate id
2. **Referential Integrity**: Surrogate id provides stable FK target
3. **Performance**: Integer FKs faster than VARCHAR FKs
4. **Consistency**: Other SCD Type 2 tables (positions, edges) already use this pattern

**Pattern**:
- Surrogate key (id SERIAL) = PRIMARY KEY for referential integrity
- Business key (market_id VARCHAR) = non-unique, versioned
- UNIQUE constraint on (business_key WHERE row_current_ind = TRUE)

### Impact
- **Tables Updated**: markets, edges, positions, trades, settlements
- **New Columns**: market_uuid INT (replaces market_id VARCHAR FK)
- **Backward Compatibility**: market_id columns kept for human readability

**Reference:** Migration 009

---

## Decision #28/ADR-033: External ID Traceability Pattern

**Date:** October 24, 2025
**Phase:** 1 (Database Completion)
**Status:** ✅ Accepted

### Problem
Internal tables (positions, exits, edges) had no link back to API sources. Difficult to:
- Debug discrepancies between internal data and Kalshi
- Reconcile positions with API state
- Trace calculation batches

### Decision
**Add external_*_id columns to link internal data to API sources.**

Columns added:
```sql
-- Link positions to opening trade
ALTER TABLE positions ADD COLUMN initial_order_id VARCHAR;

-- Link exits to closing trade
ALTER TABLE position_exits ADD COLUMN exit_trade_id INT REFERENCES trades(trade_id);

-- Link exit attempts to API orders
ALTER TABLE exit_attempts ADD COLUMN order_id VARCHAR;

-- Link settlements to Kalshi settlement events
ALTER TABLE settlements ADD COLUMN external_settlement_id VARCHAR;
ALTER TABLE settlements ADD COLUMN api_response JSONB;

-- Link edges to calculation batches
ALTER TABLE edges ADD COLUMN calculation_run_id UUID;
```

### Rationale
1. **Complete Audit Trail**: Can trace any internal record back to API source
2. **Debugging**: Easy to cross-reference with Kalshi data
3. **Reconciliation**: Validate internal state matches API state
4. **Batch Tracking**: Group edges calculated together

### Pattern
- API-sourced data: `external_*_id` (Kalshi API identifier)
- Internal calculations: `calculation_run_id` (batch UUID)
- Always store raw API response in JSONB for complete audit trail

**Reference:** Migration 008

---

## Decision #29/ADR-034: SCD Type 2 Completion (row_end_ts)

**Date:** October 24, 2025
**Phase:** 1 (Database Completion)
**Status:** ✅ Accepted

### Problem
SCD Type 2 pattern requires TWO columns:
1. `row_current_ind` (BOOLEAN) - Which version is current? ✅ All tables have
2. `row_end_ts` (TIMESTAMP) - When did this version become invalid? ❌ 3 tables missing

Without `row_end_ts`:
- Cannot query "What was the value at 2pm yesterday?"
- Cannot calculate "How long did each version last?"
- Incomplete audit trail

### Decision
**Add `row_end_ts` to all SCD Type 2 tables.**

Tables updated:
```sql
ALTER TABLE edges ADD COLUMN row_end_ts TIMESTAMP;
ALTER TABLE game_states ADD COLUMN row_end_ts TIMESTAMP;
ALTER TABLE account_balance ADD COLUMN row_end_ts TIMESTAMP;
-- (markets, positions already had row_end_ts)
```

### Rationale
1. **Complete Temporal Queries**: Can query historical state at any point in time
2. **Duration Calculation**: Know how long each version was active
3. **Audit Compliance**: Complete history for financial records
4. **Pattern Consistency**: All SCD Type 2 tables now have same structure

### Temporal Query Pattern
```sql
-- Get market state at specific time
SELECT * FROM markets
WHERE market_id = 'MKT-NFL-KC-WIN'
AND created_at <= '2025-10-24 14:00:00'
AND (row_end_ts > '2025-10-24 14:00:00' OR row_end_ts IS NULL);

-- Calculate version duration
SELECT created_at, row_end_ts,
       row_end_ts - created_at AS duration
FROM markets WHERE market_id = 'MKT-NFL-KC-WIN'
ORDER BY created_at;
```

**Reference:** Migrations 005, 007

---

## Decision #30/ADR-035: Event Loop Architecture (Phase 5)

**Date:** October 28, 2025
**Phase:** 5 (Trading MVP)
**Status:** 🔵 Planned

### Problem
Need a real-time trading system that:
- Monitors positions continuously for exit conditions
- Processes market data updates efficiently
- Manages multiple concurrent positions
- Maintains low latency while respecting API rate limits

### Decision
**Use single-threaded async event loop with asyncio for all real-time trading operations.**

Architecture:
```python
async def trading_event_loop():
    while True:
        # Entry evaluation (every 30s or on webhook)
        await check_for_entry_opportunities()

        # Position monitoring (frequency varies by position)
        await monitor_all_positions()

        # Exit evaluation (on price updates)
        await evaluate_all_exit_conditions()

        await asyncio.sleep(0.1)  # Prevent tight loop
```

### Rationale
1. **Simplicity**: Single thread eliminates race conditions and locks
2. **Sufficient Performance**: Can handle <200 concurrent positions easily
3. **Python-Native**: asyncio is well-suited for I/O-bound tasks
4. **Easy Debugging**: Sequential execution simplifies troubleshooting
5. **Rate Limit Management**: Centralized control over API calls

### Alternatives Considered
- **Multi-threading**: Complex synchronization, Python GIL limitations
- **Celery task queue**: Overkill for Phase 5, adds dependency
- **Reactive streams (RxPY)**: Steeper learning curve, unnecessary complexity

**Reference:** `supplementary/EVENT_LOOP_ARCHITECTURE_V1.0.md`

---

## Decision #31/ADR-036: Exit Evaluation Strategy (Phase 5)

**Date:** October 28, 2025
**Phase:** 5a (Position Monitoring & Exit Management)
**Status:** 🔵 Planned

### Problem
Multiple exit conditions can trigger simultaneously. Need clear priority hierarchy and evaluation strategy to ensure:
- Critical exits (stop loss) execute immediately
- Conflicting exits don't cause race conditions
- Partial exits are staged correctly

### Decision
**Evaluate ALL 10 exit conditions on every price update, select highest priority.**

Priority Hierarchy:
1. **CRITICAL** (Execute immediately, market order if needed):
   - Stop Loss Hit
   - Expiration Imminent (<2 hours)

2. **HIGH** (Execute urgently, allow 1-2 price walks):
   - Target Profit Hit
   - Adverse Market Conditions

3. **MEDIUM** (Execute when favorable, allow up to 5 price walks):
   - Trailing Stop Hit
   - Market Drying Up (low volume)
   - Model Update (confidence drop)

4. **LOW** (Opportunistic, cancel if not filled in 60s):
   - Take Profit (early profit taking)
   - Position Consolidation
   - Rebalancing

Evaluation Logic:
```python
def evaluate_exit(position):
    triggered_exits = []
    for exit_condition in ALL_10_CONDITIONS:
        if exit_condition.is_triggered(position):
            triggered_exits.append(exit_condition)

    if not triggered_exits:
        return None

    # Select highest priority
    return max(triggered_exits, key=lambda e: e.priority)
```

### Rationale
1. **Complete Coverage**: No exit opportunity missed
2. **Clear Hierarchy**: No ambiguity when multiple conditions trigger
3. **Simple Logic**: Easy to test and debug
4. **Urgency-Based Execution**: Matches exit urgency to execution strategy

### Alternatives Considered
- **First-triggered wins**: Could miss higher-priority exits
- **Separate evaluation loops**: Risk of race conditions
- **Rule-based engine**: Over-engineered for 10 conditions

**Reference:** `supplementary/EXIT_EVALUATION_SPEC_V1.0.md`

---

## Decision #32/ADR-037: Advanced Order Walking (Phase 5b)

**Date:** October 28, 2025
**Phase:** 5b (Advanced Execution)
**Status:** 🔵 Planned

### Problem
In thin markets, aggressive limit orders don't fill. Need to balance:
- **Speed**: Get filled before opportunity disappears
- **Price Improvement**: Don't pay unnecessarily wide spreads
- **Market Impact**: Don't move the market against ourselves

### Decision
**Multi-stage price walking with urgency-based escalation.**

Walking Algorithm:
```
Stage 1 (0-30s): Limit order at best bid/ask (no spread crossing)
Stage 2 (30-60s): Walk 25% into spread every 10s
Stage 3 (60-90s): Walk 50% into spread every 10s
Stage 4 (90s+): Market order if urgency=CRITICAL, else cancel
```

Urgency Levels:
- **CRITICAL** (stop loss, expiration): Market order after 90s
- **HIGH** (target profit): Walk aggressively, give up after 120s
- **MEDIUM** (trailing stop): Walk conservatively, give up after 180s
- **LOW** (take profit): Cancel after 60s if no fill

### Rationale
1. **Adaptive**: Matches execution aggressiveness to exit urgency
2. **Price Improvement**: Attempts best price first
3. **Guaranteed Execution**: CRITICAL exits always fill (market order)
4. **Market Awareness**: Avoids moving thin markets

### Alternatives Considered
- **Immediate market orders**: Expensive in thin markets
- **Static limit orders**: Poor fill rates (<60% in testing)
- **TWAP/VWAP algorithms**: Overkill for binary outcome markets

### Implementation Notes
- Phase 5a: Basic limit orders only
- Phase 5b: Full walking algorithm (conditional on Phase 5a metrics)
- Review fill rates after 2 weeks of Phase 5a before implementing

**Reference:** `supplementary/ADVANCED_EXECUTION_SPEC_V1.0.md`

---

## Decision #33/ADR-038: Ruff for Code Quality Automation (Phase 0.6c)

**Date:** October 29, 2025
**Phase:** 0.6c (Validation & Testing Infrastructure)
**Status:** ✅ Complete

### Problem
Multiple tools (black, flake8, isort) were slow (~15s) and required separate configuration. Need faster, unified code quality tooling.

### Decision
**Adopt Ruff as unified formatter and linter, replacing black + flake8 + isort.**

Configuration:
```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "DTZ", "T10", ...]
fixable = ["ALL"]
```

### Rationale
1. **10-100x Faster**: Rust-based, runs in ~1 second vs ~15 seconds
2. **Unified Config**: Single pyproject.toml for all tools
3. **Auto-fix**: Fixes most issues automatically
4. **Modern**: Actively developed, replaces aging tools

### Alternatives Considered
- **Keep black + flake8**: Slower, multiple configs
- **pylint**: Even slower than flake8
- **mypy only**: Doesn't handle formatting

### Implementation
- Created comprehensive pyproject.toml configuration
- Integrated into validate_quick.sh (~3s) and validate_all.sh (~60s)
- Works cross-platform (Windows/Linux/Mac)

**Reference:** `foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`

---

## Decision #34/ADR-039: Test Result Persistence Strategy (Phase 0.6c)

**Date:** October 29, 2025
**Phase:** 0.6c (Validation & Testing Infrastructure)
**Status:** ✅ Complete

### Problem
Test results were ephemeral, making it difficult to track quality trends over time.

### Decision
**Persist test results in timestamped directories with HTML reports and logs.**

Structure:
```
test_results/
├── 2025-10-29_143022/
│   ├── pytest_report.html
│   ├── test_output.log
│   └── metadata.json (future)
└── README.md
```

### Rationale
1. **Historical Tracking**: Can compare results across sessions
2. **Debugging**: Logs available for failed tests
3. **CI/CD Ready**: Reports can be archived by GitHub Actions
4. **Timestamped**: No conflicts between runs

### Alternatives Considered
- **Ephemeral results**: Discarded after each run (loses history)
- **Git-committed results**: Would bloat repository
- **Database storage**: Overkill for current needs

### Implementation
- test_full.sh creates timestamped directories
- pytest-html generates HTML reports
- .gitignore excludes timestamped runs (keeps README.md)

**Reference:** `foundation/TESTING_STRATEGY_V2.0.md`

---

## Decision #35/ADR-040: Documentation Validation Automation (Phase 0.6c)

**Date:** October 29, 2025
**Phase:** 0.6c (Validation & Testing Infrastructure)
**Status:** ✅ Complete

### Problem
Phase 0.6b revealed documentation drift:
- ADR_INDEX ↔ ARCHITECTURE_DECISIONS mismatches (28 inconsistencies)
- REQUIREMENT_INDEX ↔ MASTER_REQUIREMENTS mismatches (12 inconsistencies)
- Broken cross-references, version header mismatches

### Decision
**Automated documentation consistency validation with validate_docs.py.**

Checks:
1. ADR consistency (ARCHITECTURE_DECISIONS ↔ ADR_INDEX)
2. Requirement consistency (MASTER_REQUIREMENTS ↔ REQUIREMENT_INDEX)
3. MASTER_INDEX accuracy
4. Cross-reference validation
5. Version header consistency

### Rationale
1. **Prevents Drift**: Catches inconsistencies immediately
2. **Fast**: Runs in ~1 second
3. **Pre-commit**: Integrated into validate_all.sh quality gate
4. **Auto-fix**: fix_docs.py auto-fixes simple issues

### Alternatives Considered
- **Manual validation**: Error-prone, time-consuming
- **Pre-commit hooks**: Too slow for development workflow
- **CI/CD only**: Catches issues too late

### Implementation
- validate_docs.py: Python script with 5 validation checks
- fix_docs.py: Auto-fix simple issues (version headers)
- ASCII-safe output (Windows compatible)

**Reference:** `foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`

---

## Decision #36/ADR-041: Layered Validation Architecture (Phase 0.6c)

**Date:** October 29, 2025
**Phase:** 0.6c (Validation & Testing Infrastructure)
**Status:** ✅ Complete

### Problem
Need both fast feedback during development and comprehensive validation before commits.

### Decision
**Two-tier validation architecture:**

Fast (validate_quick.sh - ~3 seconds):
- Ruff linting
- Ruff formatting
- Mypy type checking
- Documentation validation

Comprehensive (validate_all.sh - ~60 seconds):
- All quick validation checks
- Full test suite with coverage
- Security scan (hardcoded credentials)

### Rationale
1. **Fast Feedback**: 3-second loop keeps developers in flow state
2. **Comprehensive Gate**: 60-second validation before commits
3. **Layered**: Fast checks run frequently, slow checks run strategically
4. **Cross-platform**: Works on Windows/Linux/Mac without modification

### Alternatives Considered
- **Single validation script**: Too slow for development
- **IDE integration only**: Not consistent across team
- **Manual checks**: Unreliable, inconsistent

### Implementation
- validate_quick.sh: Development feedback loop (every 2-5 min)
- validate_all.sh: Pre-commit quality gate
- Both use python -m module for cross-platform compatibility

**Reference:** `foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`

---

## Decision #37/ADR-042: CI/CD Integration with GitHub Actions (Phase 0.7)

**Date:** October 29, 2025
**Phase:** 0.7 (CI/CD Integration)
**Status:** 🔵 Planned

### Problem
Manual validation before commits is reliable but not enforced. Need automated quality gates.

### Decision
**GitHub Actions workflow running validate_all.sh on every push/PR.**

Workflow:
```yaml
name: CI
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: ./scripts/validate_all.sh
      - uses: codecov/codecov-action@v3
```

### Rationale
1. **Enforced Quality**: Can't merge without passing validation
2. **Team Collaboration**: Consistent quality across all contributors
3. **Coverage Tracking**: Codecov shows coverage trends
4. **Status Badges**: Public quality signals on README

### Alternatives Considered
- **Pre-commit hooks only**: Can be bypassed
- **Manual validation**: Not scalable to team
- **Travis CI / CircleCI**: GitHub Actions is free for public repos

### Implementation
- Phase 0.7 task (after Phase 0.6c validation suite operational)
- Branch protection rules require passing CI
- Codecov integration for coverage tracking

**Reference:** `foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`, REQ-CICD-001

---

## Decision #38/ADR-043: Security Testing Integration (Phase 0.7)

**Date:** October 29, 2025
**Phase:** 0.7 (CI/CD Integration)
**Status:** 🔵 Planned

### Problem
Manual security scans catch common issues but don't check for Python-specific vulnerabilities or dependency issues.

### Decision
**Integrate Bandit (Python security linter) and Safety (dependency vulnerability scanner) into CI/CD.**

Integration:
```bash
# In validate_all.sh (Phase 0.7)
bandit -r . -ll  # High/Medium severity only
safety check --full-report
```

### Rationale
1. **Automated**: No manual security reviews needed
2. **Dependency Tracking**: Alerts on vulnerable packages
3. **Python-specific**: Catches Python security anti-patterns
4. **CI Integration**: Blocks merge on critical findings

### Alternatives Considered
- **Manual code review only**: Doesn't scale
- **Snyk**: Commercial tool, overkill for current needs
- **SAST tools**: More complex, slower

### Implementation
- Phase 0.7 task (integrate into validate_all.sh)
- CI workflow fails on high/critical findings
- Weekly dependency scans via scheduled workflow

**Reference:** `foundation/TESTING_STRATEGY_V2.0.md`, REQ-TEST-008

---

## Decision #39/ADR-044: Mutation Testing Strategy (Phase 0.7)

**Date:** October 29, 2025
**Phase:** 0.7 (Advanced Testing)
**Status:** 🔵 Planned

### Problem
High code coverage (87%) doesn't guarantee test quality. Need to validate that tests actually catch bugs.

### Decision
**Mutation testing with mutpy on critical modules (database/, api_connectors/, trading/).**

Concept: mutpy changes code (e.g., `>` to `>=`). Good tests catch these mutations.

Usage:
```bash
# Run on critical module
mut.py --target database/ --unit-test tests/unit/test_database*.py
```

Target: >80% mutation score on critical modules

### Rationale
1. **Test Quality**: Validates tests catch real bugs
2. **Focused**: Run on critical modules only (not all code)
3. **Confidence**: High mutation score = high-quality tests
4. **Selective**: Expensive, so run periodically (not every commit)

### Alternatives Considered
- **Code coverage only**: Doesn't measure test quality
- **Manual test review**: Subjective, time-consuming
- **Full mutation testing**: Too slow for all code

### Implementation
- Phase 0.7 task (after Phase 1 completion)
- Run weekly on critical modules
- Track mutation score trends

**Reference:** `foundation/TESTING_STRATEGY_V2.0.md`, REQ-TEST-009

---

## Decision #40/ADR-045: Property-Based Testing with Hypothesis (Phase 0.7)

**Date:** October 29, 2025
**Phase:** 0.7 (Advanced Testing)
**Status:** 🔵 Planned

### Problem
Unit tests cover specific examples but don't test edge cases comprehensively. Need automated edge case discovery.

### Decision
**Property-based testing with Hypothesis for critical calculations (decimal arithmetic, spread calculations, PnL).**

Example:
```python
from hypothesis import given
from hypothesis.strategies import decimals

@given(
    price=decimals(min_value='0.0001', max_value='0.9999', places=4)
)
def test_spread_always_positive(price):
    spread = calculate_spread(price)
    assert spread >= Decimal('0')
```

### Rationale
1. **Edge Cases**: Hypothesis generates edge cases automatically
2. **Regression Prevention**: Shrinks failures to minimal examples
3. **Confidence**: Tests mathematical properties, not just examples
4. **Decimal Safety**: Critical for financial calculations

### Alternatives Considered
- **Exhaustive testing**: Computationally infeasible
- **Manual edge cases**: Incomplete, miss corner cases
- **Fuzzing**: Less structured than property-based testing

### Implementation
- Phase 0.7 task (after Phase 2 completion)
- Focus on financial calculations (decimal precision critical)
- Integrate into test suite (pytest-hypothesis plugin)

**Reference:** `foundation/TESTING_STRATEGY_V2.0.md`, REQ-TEST-010

---

## Lessons for Future Developers

### What Worked Well in Design
1. ✅ **Documentation first** - Prevented costly refactoring
2. ✅ **Decimal precision** - Future-proof for Kalshi changes
3. ✅ **Platform abstraction** - Polymarket will be easy to add
4. ✅ **Versioning strategy** - Tracks price/state history correctly
5. ✅ **Safety mindset** - Circuit breakers, validation, defense-in-depth
6. ✅ **ADR numbering** - Clear traceability and cross-referencing

### Common Pitfalls to Avoid
1. ❌ **Don't use float for prices** - Use Decimal
2. ❌ **Don't parse deprecated integer cent fields** - Use *_dollars fields
3. ❌ **Don't forget row_current_ind on versioned tables** - Queries will be slow
4. ❌ **Don't use singular table names** - Use plural (markets not market)
5. ❌ **Don't skip validation** - Always validate prices are in range

### When to Reconsider Decisions
- **Versioning strategy:** If storage becomes expensive (>$100/month)
- **Conservative Kelly:** If system proves very accurate (>70% win rate)
- **Separate probability tables:** If non-sports categories share more structure than expected
- **Platform abstraction:** If we never add more platforms (YAGNI principle)

---

## Approval & Sign-off

This document represents the architectural decisions as of October 22, 2025 (Phase 0.5 completion with standardization).

**Approved By:** Project Lead
**Date:** October 29, 2025
**Next Review:** Before Phase 8 (Non-Sports Expansion)

---

**Document Version:** 2.8
**Last Updated:** October 29, 2025
**Critical Changes:**
- v2.8: **PHASE 0.6C + 0.7 PLANNING** - Added Decisions #33-40/ADR-038-045 (Validation & Testing Infrastructure complete, CI/CD & Advanced Testing planned)
- v2.7: **PHASE 0.6B DOCUMENTATION + PHASE 5 PLANNING** - Updated supplementary doc references, Added Decisions #30-32/ADR-035-037 (Phase 5 Trading Architecture: Event Loop, Exit Evaluation Strategy, Advanced Order Walking)
- v2.6: **PHASE 1 COMPLETION** - Added Decisions #24-29/ADR-029-034 (Database Schema Completion: Elo data source, Elo storage, settlements architecture, markets surrogate key, external ID traceability, SCD Type 2 completion)
- v2.5: **STANDARDIZATION** - Added systematic ADR numbers to all decisions for traceability
- v2.4: **CRITICAL** - Added Decisions #18-23/ADR-018-028 (Phase 0.5: Immutable Versions, Strategy & Model Versioning, Trailing Stops, Enhanced Position Management, Configuration Enhancements, Phase 0.5/1.5 Split)
- v2.4: Updated Decision #2/ADR-003 (Database Versioning Strategy) to include immutable version pattern
- v2.3: Updated YAML file reference (odds_models.yaml → probability_models.yaml)
- v2.2: Added Decision #14/ADR-016 (Terminology Standards), updated all "odds" references to "probability"
- v2.0: **DECIMAL(10,4) pricing (not INTEGER)** - Fixes critical inconsistency
- v2.0: Added cross-platform selection strategy, correlation detection, WebSocket state management

**Purpose:** Record and rationale for all major architectural decisions with systematic ADR numbering

**For complete ADR catalog, see:** ADR_INDEX_V1.2.md

**END OF ARCHITECTURE DECISIONS V2.8**
