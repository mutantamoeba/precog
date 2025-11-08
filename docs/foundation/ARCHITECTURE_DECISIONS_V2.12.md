# Architecture & Design Decisions

---
**Version:** 2.12
**Last Updated:** November 8, 2025
**Status:** ✅ Current
**Changes in v2.12:**
- **MULTI-SOURCE WARNING GOVERNANCE:** Added Decision #75/ADR-075 (Multi-Source Warning Governance Architecture)
- Establishes comprehensive governance across 3 validation sources: pytest (41 warnings), validate_docs (388 warnings), code quality tools (0 warnings)
- Locks 429-warning baseline with zero-regression policy enforced via check_warning_debt.py
- Classifies warnings: 182 actionable, 231 informational, 16 expected, 4 upstream dependencies
- Addresses 90% blind spot from initial pytest-only governance (discovered 388 untracked warnings)
- Complements Pattern 9 in CLAUDE.md V1.12 and WARNING_DEBT_TRACKER.md comprehensive tracking
**Changes in v2.11:**
- **PYTHON 3.14 COMPATIBILITY:** Added Decision #48/ADR-054 (Ruff Security Rules Instead of Bandit)
- Replace Bandit with Ruff security scanning (--select S) due to Python 3.14 incompatibility
- Bandit 1.8.6 crashes with `AttributeError: module 'ast' has no attribute 'Num'`
- Ruff provides equivalent coverage (30+ S-rules), 10-100x faster, already installed
- Updates pre-push hooks and CI/CD workflow for immediate unblocking
**Changes in v2.10:**
- **CROSS-PLATFORM STANDARDS:** Added Decision #47/ADR-053 (Cross-Platform Development - Windows/Linux compatibility)
- Added ADR-053: Cross-Platform Development Standards (ASCII-safe console output, explicit UTF-8 file I/O, Unicode sanitization helper)
- Documents pattern for Windows cp1252 vs. Linux UTF-8 compatibility (prevents UnicodeEncodeError)
- Establishes mandatory standards for all Python scripts (emoji in markdown OK, ASCII in console output only)
**Changes in v2.9:**
- **PHASE 1 API BEST PRACTICES:** Added Decisions #41-46/ADR-047-052 (API Integration Best Practices - Planned)
- Added ADR-047: API Response Validation with Pydantic (runtime type safety, automatic Decimal conversion)
- Added ADR-048: Circuit Breaker Implementation Strategy (use circuitbreaker library, not custom)
- Added ADR-049: Request Correlation ID Standard (B3 spec for distributed tracing)
- Added ADR-050: HTTP Connection Pooling Configuration (explicit HTTPAdapter for performance)
- Added ADR-051: Sensitive Data Masking in Logs (structlog processor for GDPR/PCI compliance)
- Added ADR-052: YAML Configuration Validation (4-level validation in validate_docs.py)
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

### ADR-074: Property-Based Testing Strategy (Hypothesis Framework)

**Decision #24**
**Phase:** 1.5
**Status:** ✅ Complete (Proof-of-Concept), 🔵 Planned (Full Implementation)

**Decision:** Adopt Hypothesis framework for property-based testing across all critical trading logic, with phased implementation starting in Phase 1.5.

**Why Property-Based Testing Matters for Trading:**

Traditional example-based testing validates 5-10 hand-picked scenarios:
```python
def test_kelly_criterion_example():
    # Test one specific case
    position = calculate_kelly_size(
        edge=Decimal("0.10"),
        kelly_fraction=Decimal("0.25"),
        bankroll=Decimal("10000")
    )
    assert position == Decimal("250")
```

Property-based testing validates **mathematical invariants** across thousands of auto-generated scenarios:
```python
@given(
    edge=edge_value(),           # Generates hundreds of edge values
    kelly_frac=kelly_fraction(), # Generates hundreds of kelly fractions
    bankroll=bankroll_amount()   # Generates hundreds of bankroll amounts
)
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """PROPERTY: Position size MUST NEVER exceed bankroll (prevents margin calls)"""
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll  # Validates across 1000+ combinations
```

**Key Difference:** Example-based tests say "this works for these 5 cases." Property-based tests say "this ALWAYS works, for ALL valid inputs."

**Proof-of-Concept Results (Phase 1.5):**
- **26 property tests implemented** (`tests/property/test_kelly_criterion_properties.py`, `tests/property/test_edge_detection_properties.py`)
- **2600+ test cases executed** (100 examples per property × 26 properties)
- **0 failures** in 3.32 seconds
- **Critical invariants validated:**
  - Position size NEVER exceeds bankroll (prevents margin calls)
  - Negative edge NEVER recommends trade (prevents guaranteed losses)
  - Trailing stop price NEVER loosens (only tightens or stays same)
  - Edge calculation correctly accounts for fees and bid-ask spread
  - Kelly criterion produces reasonable position sizes relative to edge
  - Decimal precision maintained throughout all calculations

**Custom Hypothesis Strategies (Trading Domain):**

Created reusable generators for trading primitives:
```python
@st.composite
def probability(draw, min_value=0, max_value=1, places=4):
    """Generate valid probabilities [0, 1] as Decimal."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))

@st.composite
def bid_ask_spread(draw, min_spread=0.0001, max_spread=0.05):
    """Generate realistic bid-ask spreads with bid < ask constraint."""
    bid = draw(st.decimals(min_value=0, max_value=0.99, places=4))
    spread = draw(st.decimals(min_value=min_spread, max_value=max_spread, places=4))
    ask = bid + spread
    return (bid, ask)
```

**Why Custom Strategies Matter:**
- Generate **domain-valid** inputs (bid < ask, probability ∈ [0, 1])
- Avoid wasting test cases on invalid inputs (negative prices, probabilities > 1)
- Encode domain constraints once, reuse across all property tests
- Improve Hypothesis shrinking (finds minimal failing examples faster)

**Hypothesis Shrinking - Automatic Bug Minimization:**

When a property test fails, Hypothesis automatically minimizes the failing example:
```python
# Initial failure: edge=0.473821, kelly_frac=0.87, bankroll=54329.12
# After shrinking: edge=0.5, kelly_frac=1.0, bankroll=100.0
# Shrinking time: <1 second

# Minimal example reveals root cause:
# Bug: When edge=0.5 and kelly_frac=1.0, position exceeds bankroll!
# Fix: Add constraint: position = min(calculated_position, bankroll)
```

**Phased Implementation Roadmap (38-48 hours total):**

**Phase 1.5 - Core Trading Logic (6-8h):** ✅ IN PROGRESS
- ✅ Kelly criterion properties (REQ-TEST-008)
- ✅ Edge detection properties (REQ-TEST-008)
- 🔵 Config validation properties (REQ-TEST-009)
- 🔵 Position sizing properties (REQ-TEST-009)

**Phase 2 - Data Validation (8-10h):**
- Historical data properties (REQ-TEST-010)
- Model validation properties (REQ-TEST-010)
- Strategy versioning properties (REQ-TEST-010)

**Phase 3 - Order Book & Entry (6-8h):**
- Order book properties (REQ-TEST-010)
- Entry optimization properties (REQ-TEST-010)

**Phase 4 - Ensemble & Backtesting (8-10h):**
- Ensemble properties (REQ-TEST-010)
- Backtesting properties (REQ-TEST-010)

**Phase 5 - Position & Exit Management (10-12h):**
- Position lifecycle properties (REQ-TEST-011)
- Trailing stop properties (REQ-TEST-011)
- Exit priority properties (REQ-TEST-011)
- Exit execution properties (REQ-TEST-011)
- Reporting metrics properties (REQ-TEST-011)

**Total:** 165 properties, 16,500+ test cases

**Critical Properties for Trading Safety:**

1. **Position Sizing:**
   - Position ≤ bankroll (prevents margin calls)
   - Position ≤ max_position_limit (risk management)
   - Kelly fraction ∈ [0, 1] (validated at config load)

2. **Edge Detection:**
   - Negative edge → don't trade (prevents guaranteed losses)
   - Edge accounts for fees and spread (realistic P&L)
   - Probability bounds [0, 1] always respected

3. **Trailing Stops:**
   - Stop price NEVER loosens (one-way ratchet)
   - Stop distance maintained (configured percentage)
   - Trigger detection accurate (price crosses stop)

4. **Exit Management:**
   - Stop loss overrides all other exits (safety first)
   - Exit price within acceptable bounds (slippage tolerance)
   - Circuit breaker prevents rapid losses (5 exits in 10 min)

**Configuration (`pyproject.toml`):**
```toml
[tool.hypothesis]
max_examples = 100          # Test 100 random inputs per property
verbosity = "normal"         # Show shrinking progress
database = ".hypothesis/examples"  # Cache discovered edge cases
deadline = 400              # 400ms timeout per example (prevents infinite loops)
derandomize = false         # True for debugging (reproducible failures)
```

**Integration with Existing Test Infrastructure:**
- ✅ Runs with existing pytest suite (`pytest tests/property/`)
- ✅ Pre-commit hooks validate property tests
- ✅ CI/CD pipeline includes property tests
- ✅ Coverage tracking includes property test files
- ✅ Same test markers (`@pytest.mark.unit`, `@pytest.mark.critical`)

**When to Use Property-Based vs. Example-Based Tests:**

**Use Property-Based Tests For:**
- Mathematical invariants (position ≤ bankroll, bid ≤ ask)
- Business rules (negative edge → don't trade)
- State transitions (trailing stop only tightens)
- Data validation (probability ∈ [0, 1])
- Edge cases humans wouldn't think to test

**Use Example-Based Tests For:**
- Specific known bugs (regression tests)
- Integration with external APIs (mock responses)
- Complex business scenarios (halftime entry strategy)
- User-facing behavior (CLI command output)
- Performance benchmarks (test takes exactly X seconds)

**Best Practice:** Use **both**. Property tests validate invariants, example tests validate specific scenarios.

**Performance Considerations:**
- **Property tests are slower** (100 examples vs. 1 example)
- **Phase 1.5:** 26 properties × 100 examples = 2600 cases in 3.32s (acceptable)
- **Full implementation:** 165 properties × 100 examples = 16,500 cases in ~30-40s (acceptable)
- **CI/CD impact:** Add ~30-40 seconds to test suite (total ~90-120 seconds)
- **Mitigation:** Run property tests in parallel, use `max_examples=20` in CI (faster feedback)

**Documentation:**
- **Implementation Plan:** `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` (comprehensive roadmap)
- **Requirements:** REQ-TEST-008 (complete), REQ-TEST-009 through REQ-TEST-011 (planned)
- **CLAUDE.md Pattern 9:** Property-Based Testing Pattern (to be added)

**Rationale:**

1. **Trading Logic is Math-Heavy:** Kelly criterion, edge detection, P&L calculation - all have mathematical invariants that MUST hold
2. **Edge Cases Matter:** A bug that manifests only when edge = 0.9999999 could cause catastrophic loss
3. **Hypothesis Finds Edge Cases Humans Miss:** Shrinking reveals minimal failing examples automatically
4. **Critical for Model Validation:** Property tests ensure models ALWAYS output valid predictions
5. **Prevents Production Bugs:** 26 properties caught 0 bugs in POC because code was well-designed. Property tests will catch bugs in future features BEFORE production.

**Impact:**
- **Phase 1.5:** Add property tests to test suite
- **Phase 2-5:** Expand property tests as new features implemented
- **All Developers:** Write property tests for new trading logic (documented in CLAUDE.md Pattern 9)
- **CI/CD:** Add property test execution to pipeline
- **Test Coverage:** Increase from 80% line coverage to 80% line + invariant coverage

**Success Metrics:**
- ✅ 0 production bugs related to position sizing (property test would have caught it)
- ✅ 0 production bugs related to edge detection (property test would have caught it)
- ✅ 0 production bugs related to trailing stops (property test would have caught it)
- ✅ <5% increase in CI/CD execution time (property tests run efficiently)

**Related ADRs:**
- ADR-011: pytest for Testing Framework (foundation)
- ADR-041: Testing Strategy Expansion (Phase 0.6c)
- ADR-045: Mutmut for Mutation Testing (Phase 0.7, measures test quality)

**Related Requirements:**
- REQ-TEST-001: Unit Testing Standards (>80% coverage)
- REQ-TEST-008: Property-Based Testing - Proof of Concept (complete)
- REQ-TEST-009: Property Testing - Core Trading Logic (Phase 1.5)
- REQ-TEST-010: Property Testing - Data Validation & Models (Phase 2-4)
- REQ-TEST-011: Property Testing - Position & Exit Management (Phase 5)

---

### ADR-075: Multi-Source Warning Governance Architecture

**Decision #25**
**Phase:** 0.7 / 1
**Status:** ✅ Complete

**Decision:** Implement comprehensive warning governance system that tracks warnings across THREE validation sources (pytest, validate_docs.py, code quality tools) with zero-regression enforcement policy.

**Context:**

Initial warning governance (Phase 0.7) only tracked pytest warnings, creating blind spots:
- **Tracked:** 41 pytest warnings (Hypothesis, ResourceWarning, pytest-asyncio)
- **MISSED:** 388 validate_docs warnings (YAML floats, MASTER_INDEX sync, ADR gaps)
- **MISSED:** Code quality warnings (Ruff, Mypy)
- **Total Blind Spot:** 388 warnings (90% of warnings untracked!)

**Problem:** Warnings accumulate silently in untracked sources, eventually blocking development when discovered.

**Three Warning Sources:**

```
Source 1: pytest Test Warnings (41 total)
├── Hypothesis decimal precision (19)
├── ResourceWarning unclosed files (13)
├── pytest-asyncio deprecation (4)
├── structlog UserWarning (1)
└── Coverage context warning (1)

Source 2: validate_docs.py Warnings (388 total)
├── ADR non-sequential numbering (231) - Informational
├── YAML float literals (111) - Actionable
├── MASTER_INDEX missing docs (27) - Actionable
├── MASTER_INDEX deleted docs (11) - Actionable
└── MASTER_INDEX planned docs (8) - Expected

Source 3: Code Quality (0 total)
├── Ruff linting errors (0)
└── Mypy type errors (0)

**Total:** 429 warnings (182 actionable, 231 informational, 16 expected)
```

**Decision Components:**

**1. Baseline Locking (`warning_baseline.json`)**
```json
{
  "baseline_date": "2025-11-08",
  "total_warnings": 429,
  "warning_categories": {
    "yaml_float_literals": {"count": 111, "severity": "low", "target_phase": "1.5"},
    "hypothesis_decimal_precision": {"count": 19, "severity": "low", "target_phase": "1.5"},
    "resource_warning_unclosed_files": {"count": 13, "severity": "medium", "target_phase": "1.5"},
    "master_index_missing_docs": {"count": 27, "severity": "medium", "target_phase": "1.5"},
    "master_index_deleted_docs": {"count": 11, "severity": "medium", "target_phase": "1.5"},
    "master_index_planned_docs": {"count": 8, "severity": "low", "target_phase": "N/A"},
    "adr_non_sequential_numbering": {"count": 231, "severity": "low", "target_phase": "N/A"}
  },
  "governance_policy": {
    "max_warnings_allowed": 429,
    "new_warning_policy": "fail",
    "regression_tolerance": 0
  }
}
```

**2. Comprehensive Tracking (`WARNING_DEBT_TRACKER.md`)**
- Documents all 429 warnings with categorization (actionable vs informational vs expected)
- Tracks 7 deferred fixes (WARN-001 through WARN-007)
- Provides fix priorities, estimates, target phases
- Documents measurement commands for all sources

**3. Automated Multi-Source Validation (`check_warning_debt.py`)**
- Runs 4 validation tools automatically:
  1. `pytest tests/ -W default` (pytest warnings)
  2. `python scripts/validate_docs.py` (documentation warnings)
  3. `python -m ruff check .` (linting errors)
  4. `python -m mypy .` (type errors)
- Compares total against baseline (429 warnings)
- Fails if total exceeds baseline (prevents regression)
- Provides detailed breakdown by source

**Enforcement Mechanisms:**

**Pre-Push Hooks:**
```bash
# .git/hooks/pre-push Step 4
python scripts/check_warning_debt.py
# → Blocks push if warnings exceed baseline
```

**CI/CD Pipeline:**
```yaml
# .github/workflows/ci.yml
- name: Warning Governance
  run: python scripts/check_warning_debt.py
  # → Blocks merge if warnings exceed baseline
```

**Governance Policy:**

1. **Baseline Locked:** 429 warnings (182 actionable) as of 2025-11-08
2. **Zero Regression:** New actionable warnings → CI fails → Must fix before merge
3. **Baseline Updates:** Require explicit approval + documentation in WARNING_DEBT_TRACKER.md
4. **Phase Targets:** Each phase reduces actionable warnings by 20-30
5. **Zero Goal:** Target 0 actionable warnings by Phase 2 completion

**Warning Classification:**

- **Actionable (182):** MUST be fixed eventually (YAML floats, unclosed files, MASTER_INDEX sync)
  - High priority: 13 (ResourceWarning - file handle leaks)
  - Medium priority: 84 (YAML + MASTER_INDEX sync)
  - Low priority: 85 (Hypothesis + structlog)

- **Informational (231):** Expected behavior (ADR gaps from intentional non-sequential numbering)
  - No action needed (documented in ADR header)

- **Expected (16):** Intentional (coverage contexts not used, planned docs)
  - No action needed (working as designed)

- **Upstream (4):** Dependency issues (pytest-asyncio Python 3.16 compat)
  - Wait for upstream fix

**Example Workflow:**

```bash
# Developer adds code that introduces new warning
git add feature.py
git commit -m "Add feature X"
git push

# Pre-push hooks detect regression
# → check_warning_debt.py: [FAIL] 430/429 warnings (+1 new)
# → Push blocked locally

# Developer fixes warning
# Fix code...

# Re-push succeeds
git push
# → check_warning_debt.py: [OK] 429/429 warnings
# → Push succeeds
```

**Rationale:**

1. **Comprehensive Coverage:** Single-source tracking (pytest only) missed 90% of warnings
2. **Early Detection:** Pre-push hooks catch regressions locally (30s vs 2-5min CI)
3. **Zero Tolerance:** Locked baseline prevents warning accumulation
4. **Actionable Tracking:** Classify warnings to focus on fixable issues
5. **Phased Reduction:** Target zero actionable warnings by Phase 2 (realistic timeline)

**Implementation:**

**Files Created:**
- `scripts/warning_baseline.json` - Locked baseline configuration
- `scripts/check_warning_debt.py` - Multi-source validation script
- `docs/utility/WARNING_DEBT_TRACKER.md` - Comprehensive warning documentation

**Files Modified:**
- `CLAUDE.md` - Added Pattern 9: Multi-Source Warning Governance
- `.git/hooks/pre-push` - Added Step 4: warning debt check
- `.github/workflows/ci.yml` - Added warning-governance job (future)

**Impact:**

**Immediate:**
- 429 warnings now tracked across all sources
- Zero-regression policy prevents new warnings
- Developer feedback in 30s (pre-push) vs 2-5min (CI)

**Phase 1.5 (Target: -60 warnings):**
- Fix WARN-001: ResourceWarning (13) - High priority
- Fix WARN-004: YAML float literals (111 → 20 after partial fix)
- Fix WARN-005: MASTER_INDEX missing docs (27)
- **New baseline:** 369 warnings

**Phase 2 (Target: -182 warnings total):**
- Fix all actionable warnings
- **New baseline:** 247 warnings (informational + expected only)
- **Achievement:** Zero actionable warnings 🎯

**Lessons Learned:**

**❌ What Went Wrong:**
- Initial governance only tracked pytest warnings
- Discovered 388 untracked warnings during comprehensive audit
- Warning debt invisible until blocking development

**✅ What Worked:**
- Multi-source validation catches all warning sources
- Automated validation prevents manual oversight
- Classification (actionable vs informational) focuses effort
- Phased reduction provides realistic timeline

**Alternatives Considered:**

**Alternative 1: Manual Tracking (Rejected)**
- **Pro:** Simple, no tooling needed
- **Con:** Human error, inconsistent, doesn't scale
- **Why Rejected:** Already failed (missed 388 warnings)

**Alternative 2: Separate Baselines per Source (Rejected)**
- **Pro:** More granular control
- **Con:** Complex, multiple files to maintain, harder to reason about total
- **Why Rejected:** Single baseline simpler, total count is what matters

**Alternative 3: Zero-Warning Policy (No Baseline) (Rejected)**
- **Pro:** Cleanest approach
- **Con:** Unrealistic with 429 existing warnings, blocks all work
- **Why Rejected:** Phased approach more pragmatic

**Success Metrics:**

- ✅ All 429 warnings tracked comprehensively
- ✅ Zero new warnings allowed (baseline locked)
- ✅ Pre-push hooks prevent local regressions
- ⏳ Phase 1.5: Reduce to 369 warnings (-60)
- ⏳ Phase 2: Reduce to 247 warnings (-182 total)

**Related ADRs:**
- ADR-041: Testing Strategy Expansion (Phase 0.6c)
- ADR-074: Property-Based Testing Strategy (validation infrastructure)

**Related Requirements:**
- REQ-VALIDATION-004: Documentation Validation System (validate_docs.py)
- REQ-TEST-001: Unit Testing Standards (pytest warnings)

**Related Documentation:**
- Pattern 9 in CLAUDE.md: Multi-Source Warning Governance
- docs/utility/WARNING_DEBT_TRACKER.md: Comprehensive warning tracking
- scripts/warning_baseline.json: Baseline configuration

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

Checks (Phase 0.6c baseline):
1. ADR consistency (ARCHITECTURE_DECISIONS ↔ ADR_INDEX)
2. Requirement consistency (MASTER_REQUIREMENTS ↔ REQUIREMENT_INDEX)
3. MASTER_INDEX accuracy
4. Cross-reference validation
5. Version header consistency

Enhanced checks (Phase 0.6c final):
6. New Docs Enforcement (all versioned .md files must be in MASTER_INDEX)
7. Git-aware Version Bumps (renamed docs must increment version)
8. Phase Completion Status (validates proper completion markers)
9. YAML Configuration Validation (syntax, Decimal safety, required keys, cross-file consistency)

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
- validate_docs.py: Python script with 9 validation checks (5 baseline + 4 enhanced)
- fix_docs.py: Auto-fix simple issues (version headers)
- ASCII-safe output (Windows compatible via Unicode sanitization)
- Git integration for version bump detection

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

## Decision #41/ADR-047: API Response Validation with Pydantic (Phase 1)

**Date:** October 31, 2025
**Phase:** 1 (API Integration)
**Status:** 🔵 Planned

### Problem
API responses from Kalshi return data as dictionaries with potential type inconsistencies, missing fields, and values that need conversion (e.g., float prices to Decimal). Manual validation is error-prone and doesn't catch runtime type errors until they cause failures.

### Decision
**Use Pydantic BaseModel classes for all API response validation with automatic Decimal conversion for price fields.**

Implementation:
```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class KalshiMarket(BaseModel):
    """Kalshi market response model with automatic validation."""
    ticker: str = Field(..., min_length=1)
    event_ticker: str
    yes_bid: Decimal = Field(ge=Decimal("0.0001"), le=Decimal("0.9999"))
    yes_ask: Decimal = Field(ge=Decimal("0.0001"), le=Decimal("0.9999"))
    no_bid: Decimal = Field(ge=Decimal("0.0001"), le=Decimal("0.9999"))
    no_ask: Decimal = Field(ge=Decimal("0.0001"), le=Decimal("0.9999"))
    volume: int = Field(ge=0)
    open_interest: int = Field(ge=0)

    @validator('yes_bid', 'yes_ask', 'no_bid', 'no_ask', pre=True)
    def parse_decimal_from_dollars(cls, v):
        """Convert *_dollars fields to Decimal, handle float contamination."""
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return Decimal(v)

    @validator('yes_bid')
    def validate_bid_ask_spread(cls, v, values):
        """Business rule: bid must be less than ask."""
        if 'yes_ask' in values and v >= values['yes_ask']:
            raise ValueError(f"yes_bid ({v}) must be < yes_ask ({values['yes_ask']})")
        return v

# Usage in API client
def get_markets(self) -> List[KalshiMarket]:
    response = self._make_request("GET", "/markets")
    # Automatic validation and conversion
    return [KalshiMarket(**market) for market in response['markets']]
```

### Rationale
1. **Runtime Type Safety**: Catches type errors at API boundary, not in business logic
2. **Automatic Decimal Conversion**: Eliminates float contamination risk
3. **Field Validation**: Ensures prices in valid range (0.0001-0.9999)
4. **Business Rule Enforcement**: Validates bid < ask, volume >= 0
5. **Industry Standard**: Pydantic v2.12+ is production-ready (already installed in requirements.txt)
6. **Clear Error Messages**: Pydantic provides detailed validation error messages with field names
7. **Documentation**: BaseModel serves as API contract documentation

### Alternatives Considered
- **Manual validation with if/else**: Error-prone, verbose, no type checking
- **TypedDict with type hints**: No runtime validation, doesn't catch errors
- **marshmallow**: Less modern, slower than Pydantic v2, no automatic Decimal support
- **Custom validation classes**: Reinventing the wheel, more code to maintain

### Implementation
- **Phase 1** (API Integration): Add Pydantic models for all Kalshi API responses
- Define models in `api_connectors/kalshi_models.py`
- Update `KalshiClient` to return validated models
- Add unit tests for validation failures (invalid prices, missing fields)
- Document model schema in API_INTEGRATION_GUIDE
- **Coverage target**: 100% for model validation (critical path)

**Reference:** `api-integration/API_INTEGRATION_GUIDE_V2.0.md`, REQ-API-007, ADR-002 (Decimal Precision)

---

## Decision #42/ADR-048: Circuit Breaker Implementation Strategy (Phase 1)

**Date:** October 31, 2025
**Phase:** 1 (API Integration)
**Status:** 🔵 Planned

### Problem
API failures (network errors, 500 errors, rate limiting) can cause cascading failures if we continue making requests. Need automatic failure detection and recovery without manual intervention.

### Decision
**Use the `circuitbreaker` library (NOT custom implementation) for all external API calls.**

Library: `circuitbreaker==2.0.0`

Implementation:
```python
from circuitbreaker import circuit
import requests
from decimal import Decimal

class KalshiClient:
    def __init__(self):
        self.base_url = "https://api.kalshi.com"
        self.failure_threshold = 5  # Open after 5 failures
        self.recovery_timeout = 60  # Try recovery after 60 seconds

    @circuit(failure_threshold=5, recovery_timeout=60, expected_exception=requests.RequestException, name="Kalshi_API")
    def get_markets(self) -> List[Dict]:
        """Fetch markets with automatic circuit breaker protection."""
        response = requests.get(f"{self.base_url}/markets")
        response.raise_for_status()
        return response.json()['markets']

    @circuit(failure_threshold=5, recovery_timeout=60, expected_exception=requests.RequestException, name="Kalshi_API")
    def get_balance(self) -> Decimal:
        """Fetch balance with circuit breaker."""
        response = requests.get(f"{self.base_url}/portfolio/balance")
        response.raise_for_status()
        return Decimal(str(response.json()['balance_dollars']))

# Circuit breaker behavior:
# 1. CLOSED (normal): Requests pass through
# 2. OPEN (failing): Requests immediately fail without calling API (fail-fast)
# 3. HALF_OPEN (recovery): Single test request to check if API recovered
```

### Rationale
1. **Battle-Tested**: circuitbreaker library is production-proven, thread-safe
2. **Automatic Recovery**: Half-open state tests API recovery automatically
3. **Fail-Fast**: Prevents wasting time on requests that will fail
4. **Resource Protection**: Stops overwhelming failing APIs
5. **Cleaner Syntax**: Decorator-based vs. manual state management
6. **Metrics Support**: Built-in logging and monitoring hooks
7. **Thread-Safe**: Custom implementation would require complex locking

### Alternatives Considered
- **Custom circuit breaker**: More code, not thread-safe, harder to test, no metrics
- **Retry logic only**: Doesn't prevent cascading failures during prolonged outages
- **No circuit breaker**: Risk of overwhelming APIs during failures, slow failure detection

### Implementation
- **Phase 1** (API Integration): Add to all Kalshi API calls
- Install: `pip install circuitbreaker==2.0.0` (add to requirements.txt)
- Configure per-endpoint thresholds (balance: 5 failures, markets: 10 failures)
- Log circuit breaker state changes (OPEN, HALF_OPEN, CLOSED)
- Add unit tests mocking failures to verify circuit opens
- **Document custom implementation as educational reference only** (do not use in production)

**Reference:** `api-integration/API_INTEGRATION_GUIDE_V2.0.md`, REQ-API-007, ADR-102 (Error Handling Strategy)

---

## Decision #43/ADR-049: Request Correlation ID Standard (Phase 1)

**Date:** October 31, 2025
**Phase:** 1 (API Integration)
**Status:** 🔵 Planned

### Problem
Debugging distributed systems (API calls, database queries, async tasks) requires tracing requests across components. Need to correlate log entries for a single logical operation.

### Decision
**Implement B3 correlation ID propagation (OpenTelemetry/Zipkin standard) using UUID4 per request.**

Standard: https://github.com/openzipkin/b3-propagation

Implementation:
```python
import uuid
import structlog

logger = structlog.get_logger()

class KalshiClient:
    def get_markets(self, request_id: str = None) -> List[Dict]:
        """Fetch markets with correlation ID for tracing."""
        if request_id is None:
            request_id = str(uuid.uuid4())

        # Log request start with correlation ID
        logger.info(
            "api_request_start",
            request_id=request_id,
            method="GET",
            path="/markets",
            api="Kalshi"
        )

        try:
            # Propagate via X-Request-ID header (B3 single-header format)
            headers = {
                "X-Request-ID": request_id,
                "Authorization": f"Bearer {self.api_key}"
            }

            response = requests.get(
                f"{self.base_url}/markets",
                headers=headers
            )

            logger.info(
                "api_request_success",
                request_id=request_id,
                status_code=response.status_code,
                response_time_ms=response.elapsed.total_seconds() * 1000
            )

            return response.json()['markets']

        except Exception as e:
            logger.error(
                "api_request_failed",
                request_id=request_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

# Database operations also log with request_id
def create_market(market_data: Dict, request_id: str):
    logger.info("db_insert_start", request_id=request_id, table="markets")
    # ... insert logic ...
    logger.info("db_insert_success", request_id=request_id, table="markets")
```

### Rationale
1. **Industry Standard**: B3 spec used by Zipkin, Jaeger, OpenTelemetry
2. **Distributed Tracing**: Correlate API → Database → async task operations
3. **Debugging**: Filter logs by request_id to see entire request lifecycle
4. **Performance Analysis**: Track request latency across components
5. **Future-Proof**: Compatible with OpenTelemetry when we add full tracing
6. **UUID4 Uniqueness**: Collision probability negligible (2^122 possible IDs)

### Alternatives Considered
- **No correlation IDs**: Impossible to trace requests across components
- **Custom ID format**: Not compatible with industry tools
- **Thread-local storage**: Doesn't work with async/await
- **Full OpenTelemetry now**: Over-engineering for Phase 1, add in Phase 3+

### Implementation
- **Phase 1** (API Integration): Add to all API client methods
- Generate UUID4 at request entry point (CLI command, scheduled task)
- Propagate via X-Request-ID header to external APIs
- Log with every operation (API call, DB query, business logic)
- Add request_id parameter to all public methods
- Update logger configuration to always include request_id field
- **Phase 3+**: Migrate to full OpenTelemetry with trace/span IDs

**Reference:** `api-integration/API_INTEGRATION_GUIDE_V2.0.md`, REQ-OBSERV-001, ADR-010 (Structured Logging)

---

## Decision #44/ADR-050: HTTP Connection Pooling Configuration (Phase 1)

**Date:** October 31, 2025
**Phase:** 1 (API Integration)
**Status:** 🔵 Planned

### Problem
Creating new HTTP connections for every API request is slow (TLS handshake overhead). Default requests library behavior doesn't optimize connection reuse.

### Decision
**Configure explicit HTTPAdapter with connection pooling for all HTTP clients.**

Implementation:
```python
import requests
from requests.adapters import HTTPAdapter

class KalshiClient:
    def __init__(self):
        self.base_url = "https://api.kalshi.com"

        # Create session with connection pooling
        self.session = requests.Session()

        # Configure HTTPAdapter for connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,    # Number of connection pools (one per host)
            pool_maxsize=20,        # Max connections per pool
            max_retries=0,          # We handle retries in circuit breaker
            pool_block=False        # Don't block when pool is full, create new connection
        )

        # Mount adapter for both http and https
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        # Set common headers
        self.session.headers.update({
            'User-Agent': 'Precog/1.0',
            'Accept': 'application/json'
        })

    def _make_request(self, method: str, path: str, **kwargs):
        """Make request using pooled session."""
        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, **kwargs)
        return response

# Connection reuse:
# First request: ~200ms (TLS handshake + request)
# Subsequent requests: ~50ms (reuse existing connection)
```

### Rationale
1. **Performance**: 4x faster than creating new connections
2. **TLS Optimization**: Reuses TLS sessions, saves handshake overhead
3. **Resource Efficiency**: Fewer open sockets, lower memory usage
4. **Explicit Configuration**: Default requests.get() doesn't pool optimally
5. **Scalability**: Supports concurrent requests without connection exhaustion
6. **Industry Standard**: HTTPAdapter is recommended by requests documentation

### Alternatives Considered
- **No pooling (requests.get)**: 4x slower, more connections, worse performance
- **httpx with connection pooling**: More features but heavier dependency, requests is sufficient for Phase 1
- **aiohttp**: Overkill for sync API client, consider for Phase 3 async

### Implementation
- **Phase 1** (API Integration): Configure in KalshiClient.__init__
- Use `pool_connections=10` (one pool per unique host)
- Use `pool_maxsize=20` (max 20 concurrent requests per host)
- Set `max_retries=0` (circuit breaker handles retries)
- Document connection pool configuration in API_INTEGRATION_GUIDE
- Monitor connection pool metrics (pool exhaustion warnings)

**Reference:** `api-integration/API_INTEGRATION_GUIDE_V2.0.md`, REQ-API-007, ADR-100 (Kalshi API Client Architecture)

---

## Decision #45/ADR-051: Sensitive Data Masking in Logs (Phase 1)

**Date:** October 31, 2025
**Phase:** 1 (API Integration)
**Status:** 🔵 Planned

### Problem
Logs may accidentally contain sensitive data (API keys, tokens, passwords, private keys) which creates security and compliance risks (GDPR, PCI-DSS). Need automatic scrubbing before log output.

### Decision
**Implement structlog processor to automatically mask sensitive fields in all log output.**

Implementation:
```python
import structlog
import re

def mask_sensitive_data(logger, method_name, event_dict):
    """
    Structlog processor to mask sensitive data before output.

    Masks: api_key, token, password, private_key, secret, authorization
    """
    SENSITIVE_KEYS = {
        'api_key', 'token', 'password', 'private_key', 'secret',
        'api_secret', 'access_token', 'refresh_token', 'bearer_token',
        'authorization', 'auth', 'credentials'
    }

    # Mask dictionary values
    for key, value in event_dict.items():
        if key.lower() in SENSITIVE_KEYS and value:
            # Keep first 4 and last 4 characters for debugging
            if len(str(value)) > 8:
                masked = f"{str(value)[:4]}...{str(value)[-4:]}"
            else:
                masked = "***REDACTED***"
            event_dict[key] = masked

    # Mask sensitive patterns in string values (e.g., Bearer tokens in headers)
    SENSITIVE_PATTERNS = [
        (r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer ***REDACTED***'),
        (r'api[_-]?key[=:]\s*[A-Za-z0-9_\-\.]+', 'api_key=***REDACTED***'),
        (r'token[=:]\s*[A-Za-z0-9_\-\.]+', 'token=***REDACTED***'),
    ]

    for key, value in event_dict.items():
        if isinstance(value, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
            event_dict[key] = value

    return event_dict

# Configure structlog with masking processor
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        mask_sensitive_data,  # Add masking BEFORE output
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Usage - automatic masking
logger = structlog.get_logger()
logger.info("api_request", api_key="sk_live_abc123xyz789", endpoint="/markets")
# Output: {"api_key": "sk_l...8789", "endpoint": "/markets"}
```

### Rationale
1. **Security**: Prevents accidental credential leakage in logs
2. **Compliance**: Required for GDPR, PCI-DSS, SOC 2
3. **Automatic**: No manual scrubbing needed, can't forget to mask
4. **Debugging-Friendly**: Shows first/last 4 chars for identification
5. **Defense-in-Depth**: Even if log aggregation is compromised, credentials are masked
6. **Pattern-Based**: Catches credentials in various formats (headers, query params)

### Alternatives Considered
- **Manual masking**: Error-prone, developers will forget
- **No logging of sensitive fields**: Loses debugging capability
- **Separate credential logs**: Complex, hard to correlate with requests
- **Encryption in logs**: Adds overhead, doesn't prevent leakage if keys compromised

### Implementation
- **Phase 1** (API Integration): Add masking processor to structlog configuration
- Mask: api_key, token, password, private_key, secret, authorization
- Show first 4 + last 4 characters for debugging (e.g., "sk_li...xyz9")
- Test masking with unit tests (verify credentials don't appear in output)
- Document sensitive field naming convention (always use lowercase with underscores)
- Add to pre-commit hook: scan for log statements with sensitive keys

**Reference:** `utility/SECURITY_REVIEW_CHECKLIST.md`, REQ-SEC-009, ADR-010 (Structured Logging), ADR-009 (Environment Variables for Secrets)

---

## Decision #46/ADR-052: YAML Configuration Validation (Phase 1)

**Date:** October 31, 2025
**Phase:** 1 (Configuration)
**Status:** 🔵 Planned

### Problem
YAML configuration files (7 files in `config/`) may have syntax errors, incorrect types (float instead of string for Decimal fields), or missing required keys. These errors only surface at runtime, causing crashes or incorrect calculations.

### Decision
**Add comprehensive YAML validation to `validate_docs.py` with 4 validation levels.**

Implementation:
```python
# scripts/validate_docs.py - Add new validation check

import yaml
from pathlib import Path
from typing import Dict, Any

def validate_yaml_files() -> ValidationResult:
    """
    Validate YAML configuration files for syntax and type safety.

    Checks:
    1. Valid YAML syntax (no parse errors)
    2. Decimal fields use string format (not float) - CRITICAL for price precision
    3. Required keys present (per file type)
    4. Cross-file consistency (e.g., strategy references valid model)

    Returns:
        ValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    config_dir = PROJECT_ROOT / "config"
    yaml_files = list(config_dir.glob("*.yaml"))

    if not yaml_files:
        errors.append("No YAML files found in config/ directory")
        return ValidationResult(
            name=f"YAML Configuration Validation (0 files)",
            passed=False,
            errors=errors,
            warnings=warnings
        )

    # Keywords that indicate Decimal fields (should be strings not floats)
    DECIMAL_KEYWORDS = [
        "price", "threshold", "limit", "kelly", "spread",
        "probability", "fraction", "rate", "fee", "stop",
        "target", "trailing", "bid", "ask", "edge"
    ]

    for yaml_file in yaml_files:
        file_name = yaml_file.name

        # Level 1: Syntax validation
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(
                f"{file_name}: YAML syntax error - {str(e)}"
            )
            continue  # Skip other checks if syntax invalid

        # Level 2: Type validation (Decimal fields must be strings)
        def check_decimal_types(obj, path=""):
            """Recursively check for float values in Decimal fields."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key

                    # Check if key suggests Decimal value
                    if any(kw in key.lower() for kw in DECIMAL_KEYWORDS):
                        if isinstance(value, float):
                            warnings.append(
                                f"{file_name}: {current_path} = {value} (float) "
                                f"→ Should be \"{value}\" (string) for Decimal precision"
                            )
                        elif isinstance(value, str):
                            # Verify string can be parsed as Decimal
                            try:
                                from decimal import Decimal, InvalidOperation
                                Decimal(value)
                            except (InvalidOperation, ValueError):
                                errors.append(
                                    f"{file_name}: {current_path} = \"{value}\" "
                                    f"is not a valid Decimal"
                                )

                    # Recurse into nested structures
                    if isinstance(value, (dict, list)):
                        check_decimal_types(value, current_path)

            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    check_decimal_types(item, f"{path}[{idx}]")

        check_decimal_types(data)

        # Level 3: Required keys validation (per file type)
        REQUIRED_KEYS = {
            "system.yaml": ["environment", "log_level"],
            "trading.yaml": ["max_position_size", "max_total_exposure"],
            "position_management.yaml": ["stop_loss", "profit_target"],
            # Add more as needed
        }

        if file_name in REQUIRED_KEYS:
            for required_key in REQUIRED_KEYS[file_name]:
                if required_key not in data:
                    errors.append(
                        f"{file_name}: Missing required key '{required_key}'"
                    )

    return ValidationResult(
        name=f"YAML Configuration Validation ({len(yaml_files)} files)",
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )

# Add to main validation checks
checks = [
    # ... existing checks ...
    validate_yaml_files(),  # NEW CHECK #9
]
```

### Rationale
1. **Prevent Runtime Crashes**: Catch syntax errors at validation time, not in production
2. **Type Safety**: Enforce string format for Decimal fields (prevents float contamination)
3. **Early Detection**: Pre-commit hook catches issues before commit
4. **Cross-Platform**: Works on Windows, Linux, Mac (part of validation suite)
5. **Zero Overhead**: Validation runs in <1 second (part of validate_quick.sh)
6. **Documentation**: Warnings teach correct Decimal format

### Alternatives Considered
- **Manual YAML validation**: Developers will forget, no enforcement
- **Pydantic for YAML**: Overkill for simple validation, adds complexity
- **Schema validation libraries (Cerberus)**: Additional dependency, simple checks don't need it
- **No validation**: Runtime crashes, Decimal precision errors

### Implementation
- **Phase 1** (Configuration): Add to `scripts/validate_docs.py` as Check #9
- Validate all 7 YAML files in `config/` directory
- Integrate with `validate_quick.sh` (~3s) and `validate_all.sh` (~60s)
- Add to pre-commit hooks (runs automatically before commit)
- Add to GitHub Actions CI/CD (line 102 of `.github/workflows/ci.yml` already runs validate_docs.py)
- Document Decimal string format in CONFIGURATION_GUIDE

**Reference:** `foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`, REQ-VALIDATION-004, ADR-002 (Decimal Precision), ADR-040 (Documentation Validation Automation)

---

## Decision #47/ADR-053: Cross-Platform Development Standards (Windows/Linux)

**Date:** November 4, 2025
**Phase:** 0.6c (Validation Infrastructure)
**Status:** ✅ Accepted

### Problem
Development and CI/CD occur on both Windows (local development) and Linux (GitHub Actions). Python scripts that work perfectly on Linux fail on Windows with `UnicodeEncodeError` when printing emoji to the console. This creates a poor developer experience and makes scripts unusable on Windows.

**Real Examples Encountered:**
- **Phase 0.6c**: `validate_docs.py` and `fix_docs.py` crashed on Windows when printing ✅❌⚠️ emoji
- **This session**: `ValidationResult.print_result()` crashed printing status emoji from DEVELOPMENT_PHASES content

**Root Cause:** Windows console uses cp1252 encoding (limited character set), Linux/Mac use UTF-8 (full Unicode support).

### Decision
**Establish cross-platform development standards with mandatory ASCII-safe output for all Python scripts.**

#### Standards

**1. Console Output (Scripts/Tools)**
```python
# ✅ CORRECT: ASCII equivalents for cross-platform safety
print("[OK] All tests passed")
print("[FAIL] 3 errors found")
print("[WARN] Consider updating documentation")
print("[IN PROGRESS] Phase 1 - 50% complete")

# ❌ WRONG: Emoji in console output
print("✅ All tests passed")  # Crashes on Windows cp1252
print("❌ 3 errors found")
print("⚠️ Consider updating documentation")
```

**2. File I/O (Always Specify Encoding)**
```python
# ✅ CORRECT: Explicit UTF-8 encoding
with open("file.md", "r", encoding="utf-8") as f:
    content = f.read()

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f)

# ❌ WRONG: Platform default encoding
with open("file.md", "r") as f:  # cp1252 on Windows, UTF-8 on Linux
    content = f.read()
```

**3. Unicode Sanitization Helper**
```python
def sanitize_unicode_for_console(text: str) -> str:
    """Replace common Unicode emoji with ASCII equivalents for Windows console."""
    replacements = {
        "✅": "[COMPLETE]",
        "🔵": "[PLANNED]",
        "🟡": "[IN PROGRESS]",
        "❌": "[FAILED]",
        "⏸️": "[PAUSED]",
        "📦": "[ARCHIVED]",
        "🚧": "[DRAFT]",
        "⚠️": "[WARNING]",
        "🎯": "[TARGET]",
        "🔒": "[LOCKED]",
    }
    for unicode_char, ascii_replacement in replacements.items():
        text = text.replace(unicode_char, ascii_replacement)
    return text

# Usage in all print statements reading from markdown
print(sanitize_unicode_for_console(error_message))
```

**4. Documentation Files vs. Script Output**
- **Markdown files (.md)**: Emoji OK ✅ (GitHub/VS Code render them correctly)
- **Script output (print/logging)**: ASCII only (cross-platform compatibility)
- **Error messages**: Always ASCII-safe (may be read from markdown, then printed)

**5. Testing Requirements**
- CI/CD must test on both Windows and Linux (already configured in `.github/workflows/ci.yml`)
- Matrix strategy: `os: [ubuntu-latest, windows-latest]`
- Validates scripts work identically on both platforms

### Rationale
1. **Developer Experience**: Scripts work identically on Windows and Linux
2. **CI/CD Reliability**: No platform-specific failures
3. **Accessibility**: ASCII output works in all terminals (Windows CMD, PowerShell, WSL, Linux, Mac)
4. **Simplicity**: Clear rule - "console output = ASCII only"
5. **Documentation Flexibility**: Markdown files can still use emoji for readability
6. **Prevention**: Caught early in development, not in production

### Alternatives Considered
- **Force UTF-8 console encoding on Windows**: Requires environment configuration, brittle
- **Emoji in scripts, sanitize only when needed**: Inconsistent, developers will forget
- **No emoji anywhere**: Reduces markdown readability
- **Platform-specific code paths**: Complex, error-prone

### Implementation
- **Phase 0.6c** (✅ Complete): Applied to `validate_docs.py`, `fix_docs.py`
- **This session** (✅ Complete): Applied to `ValidationResult.print_result()` in enhanced validate_docs.py
- **Future**: All new Python scripts MUST follow these standards
- **Code Review Checkpoint**: Check for `print()` statements with emoji before merging
- **Document in CLAUDE.md**: Add as Pattern #5 (Cross-Platform Compatibility)

### Pattern Summary
| Context | Emoji Allowed? | Encoding |
|---------|---------------|----------|
| Markdown files (.md) | ✅ Yes | UTF-8 explicit |
| Script `print()` output | ❌ No (ASCII only) | cp1252-safe |
| File I/O | N/A | UTF-8 explicit |
| Error messages (from markdown → console) | ❌ No (sanitize first) | ASCII equiv |
| GitHub/VS Code rendering | ✅ Yes | UTF-8 |

**Reference:** `foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md`, `scripts/validate_docs.py` (lines 57-82), ADR-040 (Documentation Validation Automation)

---

## Decision #48/ADR-054: Ruff Security Rules Instead of Bandit (Python 3.14 Compatibility)

**Date:** November 7, 2025
**Phase:** 0.7 (CI/CD Integration)
**Status:** ✅ Accepted

### Problem
**Bandit 1.8.6 (latest version) is incompatible with Python 3.14.** It crashes on all files with `AttributeError: module 'ast' has no attribute 'Num'`. Python 3.14 removed legacy AST node types (`ast.Num`, `ast.Str`, etc.) in favor of unified `ast.Constant`, breaking Bandit's code parsing.

**Impact:**
- Pre-push hooks fail (security scan step blocked)
- CI/CD security-scan job will fail (uses Python 3.14)
- Local development blocked from pushing commits
- Cannot wait indefinitely for Bandit maintainers to add Python 3.14 support

### Decision
**Replace Bandit with Ruff security rules (`--select S`) for Python 3.14 compatibility.**

Ruff provides equivalent security scanning with:
- ✅ **Python 3.14 compatible** (actively maintained, already supports new AST)
- ✅ **Already installed** (no new dependencies)
- ✅ **10-100x faster** than Bandit (Rust-based vs Python)
- ✅ **Comprehensive S-rules** (hardcoded secrets, SQL injection, file permissions, etc.)
- ✅ **Active maintenance** (vs waiting for Bandit fix)

### Implementation

**Pre-push Hook (`.git/hooks/pre-push`):**
```bash
# Before (BROKEN on Python 3.14):
python -m bandit -r . -c pyproject.toml -ll -q

# After (WORKING on Python 3.14):
python -m ruff check --select S --exclude 'tests/' --exclude '_archive/' --exclude 'venv/' --quiet .
```

**CI/CD Workflow (`.github/workflows/ci.yml`):**
```yaml
# Before (WILL FAIL on Python 3.14):
- name: Run Bandit security scanner
  run: python -m bandit -r . -c pyproject.toml

# After (WORKS on Python 3.14):
- name: Run Ruff security scanner
  run: python -m ruff check --select S --exclude 'tests/' --exclude '_archive/' --exclude 'venv/' .
```

**Excluded from scanning:**
- `tests/` - Test fixtures have intentional hardcoded values for assertions
- `_archive/` - Archived code not in production
- `venv/` - Third-party dependencies (not our code)

### Ruff Security Rules Covered (S-prefix)

| Rule | Description | Equivalent Bandit Check |
|------|-------------|------------------------|
| S105 | Hardcoded password string | B105 |
| S106 | Hardcoded password function arg | B106 |
| S107 | Hardcoded password default arg | B107 |
| S608 | SQL injection via string formatting | B608 |
| S701 | Jinja2 autoescape disabled | B701 |
| S103 | Bad file permissions | B103 |
| S110 | try-except-pass | B110 |
| S112 | try-except-continue | B112 |
| S607 | Start process with partial path | B607 |
| ... | 30+ security rules total | ... |

**Full list:** https://docs.astral.sh/ruff/rules/#flake8-bandit-s

### Pre-commit Hooks (Unchanged)
Pre-commit hooks **do NOT use Bandit** - they use custom bash script for credential scanning:
```bash
git grep -E '(password|secret|api_key|token)\s*=\s*['\''"][^'\''\"]{5,}['\''"]'
```

This custom scan is **Python 3.14 compatible** and remains unchanged.

### Rationale
1. **Immediate unblocking**: Cannot wait weeks/months for Bandit Python 3.14 support
2. **No functionality loss**: Ruff S-rules cover all critical security checks we use
3. **Performance gain**: 10-100x faster security scans (Rust vs Python)
4. **Future-proof**: Ruff actively maintained, fast adoption of new Python versions
5. **Existing dependency**: No new packages to install or manage
6. **Reversible**: Can switch back to Bandit if/when they add Python 3.14 support

### Alternatives Considered

**1. Run Bandit with Python 3.13 in separate virtualenv**
- ❌ Complex setup (multiple Python versions)
- ❌ Slows down pre-push hooks
- ❌ Fragile (virtualenv path issues)

**2. Wait for Bandit Python 3.14 support**
- ❌ Blocks local development indefinitely
- ❌ Timeline unknown (could be weeks/months)
- ❌ CI/CD also blocked

**3. Install Semgrep (alternative security scanner)**
- ❌ New dependency to manage
- ❌ Slower than Ruff
- ✅ More powerful (but overkill for current needs)

**4. Disable security scanning temporarily**
- ❌ Unacceptable security risk
- ❌ Would miss real vulnerabilities

### Migration Notes

**Keep Bandit configuration in pyproject.toml:**
- Future-proofing for when Bandit adds Python 3.14 support
- Preserves skip rules and exclude patterns
- No harm in keeping unused config

**Update documentation references:**
- ARCHITECTURE_DECISIONS (this file) - ✅ Updated ADR-043
- DEVELOPMENT_PHASES - Update "Bandit" → "Ruff security rules"
- TESTING_STRATEGY - Update security testing section
- VALIDATION_LINTING_ARCHITECTURE - Update tools list
- MASTER_REQUIREMENTS - Update REQ-CICD-003, REQ-SEC-009
- CLAUDE.md - Update pre-push hook documentation

### Success Criteria
- ✅ Pre-push hooks pass on Python 3.14
- ✅ CI/CD security-scan job passes on Python 3.14
- ✅ Same or better security coverage vs Bandit
- ✅ No hardcoded credentials detected (S105-S107)
- ✅ No SQL injection vulnerabilities (S608)

**Reference:** `.git/hooks/pre-push`, `.github/workflows/ci.yml`, `pyproject.toml`, ADR-043 (Security Testing Integration)

---

## Distributed Architecture Decisions

Some ADRs are documented in specialized documents for better organization and technical depth. These decisions are fully documented in the referenced files and are listed here for completeness and traceability.

### ADR-006: SQLAlchemy as ORM

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** PROJECT_OVERVIEW_V1.4.md

Decision to use SQLAlchemy as the Object-Relational Mapper for database operations. Provides type-safe query building, connection pooling, and database abstraction.

### ADR-008: Modular Directory Structure

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** PROJECT_OVERVIEW_V1.4.md

Decision on project directory structure with clear separation of concerns (database/, api_connectors/, trading/, analytics/, utils/, config/).

### ADR-010: Structured Logging with Python logging

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** utils/logger.py, ARCHITECTURE_DECISIONS (brief mention)

Decision to use Python's standard logging library with structlog for structured JSON logging with decimal serialization support.

### ADR-011: pytest for Testing Framework

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** pyproject.toml, TESTING_STRATEGY_V2.0.md

Decision to use pytest as the primary testing framework with coverage, async support, and HTML reporting.

### ADR-012: Foreign Key Constraints for Referential Integrity

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** DATABASE_SCHEMA_SUMMARY_V1.7.md

Decision to enforce referential integrity using PostgreSQL foreign key constraints on all relationship columns.

### ADR-014: ON DELETE CASCADE for Cascading Deletes

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** DATABASE_SCHEMA_SUMMARY_V1.7.md

Decision on when to use ON DELETE CASCADE vs. ON DELETE RESTRICT for foreign key relationships.

### ADR-015: Helper Views for Current Data

**Status:** ✅ Accepted
**Phase:** 0
**Documented in:** DATABASE_SCHEMA_SUMMARY_V1.7.md

Decision to create database views that filter for current rows (row_current_ind = TRUE) to simplify application queries.

### ADR-025: Price Walking Algorithm for Exits

**Status:** ✅ Accepted
**Phase:** 0.5
**Documented in:** POSITION_MANAGEMENT_GUIDE_V1.0.md

Decision on multi-stage price walking algorithm for exit order execution (start with limit, walk toward market price if not filled).

### ADR-026: Partial Exit Staging (2-Stage)

**Status:** ✅ Accepted
**Phase:** 0.5
**Documented in:** POSITION_MANAGEMENT_GUIDE_V1.0.md

Decision to implement 2-stage partial exits (50% at +15%, 25% at +25%, 25% with trailing stop).

### ADR-027: position_exits Append-Only Table

**Status:** ✅ Accepted
**Phase:** 0.5
**Documented in:** DATABASE_SCHEMA_SUMMARY_V1.7.md

Decision to use append-only table for position_exits to maintain complete exit event history.

### ADR-028: exit_attempts for Debugging

**Status:** ✅ Accepted
**Phase:** 0.5
**Documented in:** DATABASE_SCHEMA_SUMMARY_V1.7.md

Decision to log all exit order attempts (filled and unfilled) to exit_attempts table for debugging "why didn't my exit fill?" issues.

---

## Future Architecture Decisions (Planned)

The following ADR numbers are reserved for future phases. These decisions will be documented as the corresponding phases are implemented.

### Core Engine Decisions (100-199)

**Phase 1: Core Trading Engine**

- **ADR-100:** TBD - Kalshi API Client Architecture
- **ADR-101:** TBD - RSA-PSS Authentication Implementation
- **ADR-102:** TBD - Error Handling Strategy
- **ADR-103:** TBD - Rate Limiting Implementation
- **ADR-104:** TBD - Trade Execution Workflow

**Phase 2: Live Data Integration**

- **ADR-110:** TBD - ESPN API Integration Strategy
- **ADR-111:** TBD - Game State Polling Frequency
- **ADR-112:** TBD - Data Staleness Detection

**Phase 3: Edge Detection**

- **ADR-120:** TBD - Edge Calculation Algorithm
- **ADR-121:** TBD - Confidence Scoring Methodology

### Probability Model Decisions (200-299)

**Phase 4: Historical Probability Models**

- **ADR-200:** TBD - Elo Rating System Implementation
- **ADR-201:** TBD - Regression Model Architecture
- **ADR-202:** TBD - Model Validation Methodology
- **ADR-203:** TBD - Backtesting Framework

### Position Management Decisions (300-399)

**Phase 5: Position Management**

- **ADR-300:** 10 Exit Conditions with Priorities - Documented in POSITION_MANAGEMENT_GUIDE_V1.0.md
- **ADR-301:** Urgency-Based Execution Strategies - Documented in POSITION_MANAGEMENT_GUIDE_V1.0.md
- **ADR-302:** TBD - Fractional Kelly Position Sizing
- **ADR-303:** TBD - Circuit Breaker Triggers

**Note:** ADR-300 and ADR-301 are already documented in POSITION_MANAGEMENT_GUIDE_V1.0.md as they were part of Phase 0.5 position management architecture design.

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

**Document Version:** 2.11
**Last Updated:** November 8, 2025
**Critical Changes:**
- v2.11: **PROPERTY-BASED TESTING STRATEGY** - Added Decision #24/ADR-074 (Hypothesis framework adoption: 26 property tests POC, custom strategies, phased implementation roadmap, 165 properties planned)
- v2.10: **CROSS-PLATFORM STANDARDS** - Added Decision #47/ADR-053 (Windows/Linux compatibility: ASCII-safe console output, explicit UTF-8 file I/O, Unicode sanitization)
- v2.9: **PHASE 1 API BEST PRACTICES** - Added Decisions #41-46/ADR-047-052 (API Integration Best Practices: Pydantic validation, circuit breaker, correlation IDs, connection pooling, log masking, YAML validation)
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

**For complete ADR catalog, see:** ADR_INDEX_V1.4.md

**END OF ARCHITECTURE DECISIONS V2.10**
