# Master Requirements Document

---
**Version:** 2.5
**Last Updated:** 2025-10-21
**Status:** ✅ Current - Authoritative Requirements
**Changes in v2.5:**
- **CRITICAL**: Added Phase 5 monitoring and exit management requirements
- Added REQ-MON-* requirements (Position monitoring with dynamic frequencies)
- Added REQ-EXIT-* requirements (Exit condition evaluation and priority hierarchy)
- Added REQ-EXEC-* requirements (Urgency-based execution strategies)
- Updated database overview to include position_exits and exit_attempts tables (V1.5)
- Added 10 exit conditions with priority levels (CRITICAL/HIGH/MEDIUM/LOW)
- Added partial exit staging requirements (2-stage scaling out)
**Changes in v2.4:** Added Phase 0.5 (Foundation Enhancement) - Versioning, trailing stops, position management; Added versioning requirements for strategies and probability models (IMMUTABLE pattern); Updated database overview to V1.4
**Changes in v2.3:** Updated environment variable names to match actual env.template; updated directory structure (data_storers/ → database/)
**Changes in v2.2:** Updated terminology (odds → probability) in objectives, requirements, and module references
**Replaces:** Master Requirements v2.4
---

## Document Purpose
This is the **master requirements document** providing a high-level overview of the Precog prediction market trading system. Detailed technical specifications are maintained in supplementary documents (see Section 2.4).

**For new developers**: Start here to understand the project scope, then reference supplementary docs for implementation details.

---

## 1. Executive Summary

### 1.1 Project Overview
**Precog** is a modular, scalable Python application to identify and execute positive expected value (EV+) trading opportunities across multiple prediction market platforms, initially focused on Kalshi with NFL and NCAAF markets, with strategic expansion to other sports, non-sports markets, and additional platforms (Polymarket).

### 1.2 Core Objectives
- **Automate Data Collection**: Retrieve market data from multiple platforms and live game statistics
- **Calculate True Probabilities**: Compute win probabilities from historical data and live game states using versioned ML models
- **Identify Edges**: Find EV+ opportunities by comparing true probabilities vs. market prices (minimum 5% threshold after transaction costs)
- **Execute Trades**: Place orders using versioned strategies with robust error handling and compliance checks
- **Manage Positions**: Track positions with dynamic trailing stop losses for profit protection
- **Version Strategies & Models**: Maintain immutable versions for A/B testing and precise trade attribution
- **Multi-Platform Strategy**: Abstract platform-specific logic for cross-platform opportunities
- **Scale Strategically**: Expand to additional sports, non-sports markets, and prediction platforms

### 1.3 Success Metrics
- **System Uptime**: 99%+ during market hours
- **Data Latency**: <5 seconds from API to database
- **Decimal Precision**: 100% accuracy in price handling (no float rounding errors)
- **Edge Detection Accuracy**: Validated through backtesting (target: 55%+ win rate)
- **Execution Success**: >95% of intended trades executed
- **ROI**: Positive returns after transaction costs over 6-month period
- **Strategy Version Tracking**: 100% of trades attributed to exact strategy and model versions

---

## 2. System Architecture

### 2.1 Technology Stack
- **Language**: Python 3.12
- **Database**: PostgreSQL (local dev → AWS RDS production)
- **ORM**: SQLAlchemy + psycopg2
- **API**: requests (sync), aiohttp (async)
- **Data Processing**: pandas, numpy
- **Decimal Precision**: Python Decimal library (NEVER float for prices)
- **Text Parsing**: Spacy
- **Testing**: pytest (target: >80% coverage)
- **Scheduling**: APScheduler
- **Logging**: Python logging library
- **Configuration**: YAML files + environment variables

### 2.2 High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface (CLI)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│                    Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Trading    │  │  Analytics   │  │  Data Storers   │   │
│  │   Module     │  │    Engine    │  │                 │   │
│  │  (Versioned  │  │  (Versioned  │  │                 │   │
│  │  Strategies) │  │   Models)    │  │                 │   │
│  └──────────────┘  └──────────────┘  └─────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│               Platform Abstraction Layer                     │
│  ┌──────────────────────┐  ┌──────────────────────────┐     │
│  │  Kalshi Platform     │  │  Polymarket Platform     │     │
│  │  (Phases 1-9)        │  │  (Phase 10)              │     │
│  └──────────────────────┘  └──────────────────────────┘     │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────┐
│                   API Connectors Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Kalshi  │  │   ESPN   │  │Balldontlie│  │ Scrapers │   │
│  │   API    │  │   API    │  │   API    │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Polymarket│  │ Plus EV  │  │SportsRadar│  │  NCAAF   │   │
│  │   API    │  │   API    │  │   API    │  │   API    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                  ┌─────────┴─────────┐
                  │   PostgreSQL DB    │
                  │   (SQLAlchemy)     │
                  │ ALL PRICES: DECIMAL│
                  │ VERSIONS: IMMUTABLE│
                  └────────────────────┘
```

### 2.3 Module Structure
```
precog/
├── api_connectors/         # External API integrations
│   ├── kalshi_client.py
│   ├── espn_client.py
│   ├── balldontlie_client.py
│   ├── polymarket_client.py
│   ├── plus_ev_client.py
│   ├── sportsradar_client.py
│   └── scrapers/
├── platforms/              # Platform abstraction (Phase 10)
│   ├── base_platform.py
│   ├── kalshi_platform.py
│   ├── polymarket_platform.py
│   └── platform_factory.py
├── database/               # Database operations (renamed from data_storers/)
│   ├── models.py
│   ├── crud_operations.py
│   └── db_connection.py
├── analytics/              # Probability calculation & edge detection
│   ├── probability_calculator.py
│   ├── edge_detector.py
│   ├── historical_loader.py
│   ├── model_manager.py        # NEW in Phase 0.5 - Model versioning
│   └── risk_manager.py
├── trading/                # Order execution
│   ├── order_executor.py
│   ├── strategy_manager.py     # NEW in Phase 0.5 - Strategy versioning
│   ├── position_manager.py     # ENHANCED in Phase 0.5 - Trailing stops
│   └── compliance_checker.py
├── utils/                  # Shared utilities
│   ├── logger.py
│   ├── retry_handler.py
│   ├── pagination.py
│   ├── decimal_helpers.py  # ⚠️ CRITICAL - Decimal conversion
│   └── config.py           # ENHANCED in Phase 0.5 - YAML loading
├── tests/                  # Test suite
├── data/                   # Historical odds JSON files
├── docs/                   # Supplementary documentation
├── config/                 # YAML configuration files
│   ├── trading.yaml
│   ├── trade_strategies.yaml
│   ├── position_management.yaml
│   ├── probability_models.yaml
│   ├── system.yaml
│   ├── markets.yaml
│   └── data_sources.yaml
├── main.py                 # CLI entry point
└── requirements.txt
```

### 2.4 Documentation Structure
- **This Document**: Master requirements (overview, phases, objectives)
- **Supplementary Documents** (in `docs/` folder):
  1. `API_INTEGRATION_GUIDE.md` - Detailed API specs with code examples
  2. `DATABASE_DESIGN.md` - Full schema, relationships, migration scripts
  3. `DATABASE_SCHEMA_SUMMARY.md` - V1.4 (strategies, probability_models, trailing stops)
  4. `EDGE_DETECTION_SPEC.md` - Mathematical formulas, decision algorithms
  5. `TESTING_GUIDE.md` - Test cases, fixtures, mocking strategies
  6. `DEPLOYMENT_GUIDE.md` - Setup instructions, cloud migration
  7. `DEVELOPER_ONBOARDING.md` - Getting started guide for new developers
  8. `KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md` - ⚠️ **PRINT AND KEEP AT DESK**
  9. `CONFIGURATION_GUIDE.md` - YAML configuration reference
  10. `ARCHITECTURE_DECISIONS.md` - Design rationale and trade-offs (includes ADR-019: Immutable Versions)
  11. `VERSIONING_GUIDE.md` - NEW in Phase 0.5 - Strategy and model versioning patterns
  12. `TRAILING_STOP_GUIDE.md` - NEW in Phase 0.5 - Trailing stop loss implementation

---

## 3. Core Concepts

### 3.1 Data Flow
1. **Fetch Market Data**: Platform APIs (Kalshi/Polymarket) → series, events, markets → PostgreSQL
2. **Fetch Live Stats**: ESPN/Balldontlie/SportsRadar APIs → game states → PostgreSQL
3. **Calculate Probabilities**: Historical data + live game state + versioned model → true win probability
4. **Detect Edges**: Compare true probabilities vs. market prices using versioned strategy → identify EV+
5. **Execute Trades**: EV+ opportunities → place orders via versioned strategy → record fills with version attribution
6. **Manage Positions**: Monitor positions → update trailing stops → exit on stop trigger or settlement
7. **Cross-Platform Selection**: Compare opportunities across platforms → execute on best price

### 3.2 Key Terminology
- **Series**: Kalshi's top-level grouping (e.g., KXNFLGAME = all NFL games)
- **Event**: Specific game instance (e.g., kxnflgame-25oct05nebuf = NE@BUF on Oct 5)
- **Market**: Binary outcome on an event (e.g., "Will NE win?" Yes/No)
- **Edge**: Positive expected value opportunity (market price < true probability)
- **EV+**: Expected Value above minimum threshold (default: 5%)
- **RowCurrentInd**: Database versioning flag for mutable data (true = current, false = historical)
- **Immutable Version**: Semantic version (v1.0, v1.1, v2.0) where config NEVER changes
- **Strategy Version**: Immutable trading strategy config (halftime_entry v1.0)
- **Model Version**: Immutable probability model config (elo_nfl v2.0)
- **Trade Attribution**: Exact link from trade to strategy version and model version used
- **Trailing Stop**: Dynamic stop loss that moves with favorable price movement
- **Platform**: Prediction market provider (Kalshi, Polymarket, etc.)
- **Decimal Pricing**: ALWAYS use `Decimal` type, NEVER float, for all prices

### 3.3 Trading Philosophy
- **Value Betting**: Only trade when true odds significantly differ from market prices
- **Risk Management**: Position sizing via Kelly Criterion (fractional for safety)
- **Diversification**: Limit exposure to correlated events
- **Transaction Costs**: Always factor in platform fees before identifying edges
- **Compliance**: Never trade on insider information; log all activity
- **Platform Arbitrage**: Exploit price differences across platforms when available
- **Version Control**: Track exact strategy and model versions for all trades
- **A/B Testing**: Compare performance across strategy/model versions
- **Profit Protection**: Use trailing stops to lock in gains on winning positions

### 3.4 Decimal Pricing Philosophy ⚠️ CRITICAL

**Why Decimal Precision Matters:**
- Kalshi uses sub-penny pricing (e.g., $0.4975)
- Float arithmetic causes rounding errors that compound over thousands of trades
- Example: 0.4975 as float → 0.497500000000001 → incorrect edge calculations

**Mandatory Rules:**
1. **ALWAYS use `from decimal import Decimal`** in Python
2. **ALWAYS parse Kalshi `*_dollars` fields** (e.g., `yes_bid_dollars`)
3. **NEVER parse integer cents fields** (e.g., `yes_bid`) - deprecated
4. **ALWAYS use DECIMAL(10,4) in PostgreSQL** - never FLOAT, REAL, or NUMERIC
5. **ALWAYS convert strings to Decimal**: `Decimal("0.4975")` NOT `Decimal(0.4975)`

**See KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md for code examples**

### 3.5 Versioning Philosophy (NEW in v2.4)

**Why Immutable Versions Matter:**
- A/B testing requires configs to never change after creation
- Trade attribution must be exact (know EXACTLY which config generated each trade)
- Semantic versioning provides clear upgrade path (v1.0 → v1.1 bug fix, v1.0 → v2.0 major change)

**Two Versioning Patterns:**

**Pattern 1: Versioned Data (row_current_ind)**
- For frequently-changing data: markets, positions, game_states, edges
- New data INSERTs new row, UPDATEs old row to set row_current_ind = FALSE
- Efficient for rapid updates

**Pattern 2: Immutable Versions (version field)**
- For strategies and probability models
- Config is IMMUTABLE once version is created
- To update: Create new version (v1.0 → v1.1)
- Only status and metrics update in-place

**What's Mutable in Versions:**
- `status` field (draft → testing → active → deprecated)
- Performance metrics (paper_roi, live_roi, validation_accuracy)
- `trailing_stop_state` in positions

**What's Immutable in Versions:**
- `config` field (strategy parameters, model hyperparameters)
- `version` field (version number)

**See VERSIONING_GUIDE.md for implementation details**

---

## 4. Database Overview

### 4.1 Design Principles
- **Two Versioning Patterns**: row_current_ind for mutable data, version fields for immutable configs
- **Timestamps**: `created_at` (immutable), `updated_at` (modified on change)
- **Relationships**: Foreign keys link markets → events → series
- **Indexing**: Optimized for time-series queries and joins
- **JSONB**: Flexible storage for metadata, API responses, and trailing stop state
- **Decimal Precision**: ALL price columns use DECIMAL(10,4) - **NO EXCEPTIONS**
- **Trade Attribution**: Every trade links to exact strategy version and model version

### 4.2 Core Tables (Simplified - Schema V1.5)
| Table | Purpose | Key Columns | Price Columns | Versioning |
|-------|---------|-------------|---------------|------------|
| `series` | Kalshi series | ticker, category, tags | N/A | None |
| `events` | Game instances | series_id, start_date, final_state | N/A | None |
| `markets` | Binary outcomes | event_id, status, volume | yes_bid, yes_ask, no_bid, no_ask (ALL DECIMAL(10,4)) | row_current_ind |
| `game_states` | Live stats | event_id, home_score, away_score, time_remaining | N/A | row_current_ind |
| `probability_matrices` | Historical win probabilities | category, subcategory, state_descriptor, value_bucket | win_probability (DECIMAL(10,4)) | None |
| `probability_models` | **NEW V1.4**: ML model versions | model_name, model_version, config, status | validation_accuracy (DECIMAL(10,4)) | Immutable Versions |
| `strategies` | **NEW V1.4**: Trading strategy versions | strategy_name, strategy_version, config, status | paper_roi, live_roi (DECIMAL(10,4)) | Immutable Versions |
| `edges` | EV+ opportunities | market_id, strategy_id, model_id, side | expected_value, true_win_probability (DECIMAL(10,4)) | row_current_ind |
| `positions` | Open trades | market_id, position_qty, side, trailing_stop_state, exit_reason, exit_priority | position_price, current_price, unrealized_pnl (DECIMAL(10,4)) | row_current_ind |
| `position_exits` | **NEW V1.5**: Exit events | position_id, exit_condition, exit_priority, quantity_exited | exit_price (DECIMAL(10,4)) | None (append-only) |
| `exit_attempts` | **NEW V1.5**: Exit order attempts | position_id, exit_condition, order_type, attempt_number | limit_price, fill_price (DECIMAL(10,4)) | None (append-only) |
| `trades` | Executed orders | market_id, quantity, side, strategy_id, model_id | price, fees (DECIMAL(10,4)) | None (append-only) |
| `platform_markets` | Multi-platform market linking | kalshi_market_id, polymarket_market_id | N/A | None |

**Detailed schema with indexes, constraints, and sample queries**: See `DATABASE_SCHEMA_SUMMARY_V1.5.md`

### 4.3 Critical Database Rules

**ALWAYS include in queries for versioned data:**
```sql
WHERE row_current_ind = TRUE
```

**NEVER query without this filter** - you'll get historical versions mixed with current data

**For immutable versions (strategies, models):**
```sql
-- Get active version
WHERE status = 'active'

-- Get specific version
WHERE strategy_name = 'halftime_entry' AND strategy_version = 'v1.1'
```

**Price Column Declaration:**
```sql
yes_bid DECIMAL(10,4) NOT NULL,
yes_ask DECIMAL(10,4) NOT NULL,
no_bid DECIMAL(10,4) NOT NULL,
no_ask DECIMAL(10,4) NOT NULL
```

**Python ORM Definition:**
```python
from decimal import Decimal
from sqlalchemy import DECIMAL

yes_bid = Column(DECIMAL(10, 4), nullable=False)
```

**Trade Attribution Query (NEW in V1.4):**
```sql
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

---

## 5. Development Phases

### Phase 0: Foundation & Documentation (COMPLETED)
**Goal**: Complete all planning, documentation, and configuration before writing code.

**Key Deliverables**:
- ✅ All architectural decisions documented
- ✅ Database schema v1.3 finalized
- ✅ Configuration system designed
- ✅ All YAML configuration files created
- ✅ Environment setup guide complete
- ✅ Master requirements v2.3
- ✅ Decimal pricing strategy documented

**Documentation**: All `docs/` files, all `config/` YAML files, `.env.template`

---

### Phase 0.5: Foundation Enhancement (CURRENT - IN PROGRESS)
**Goal**: Enhance foundation with versioning, trailing stops, and position management before Phase 1 implementation.

**Status**: Day 1 Complete (Schema Migration Applied), Day 2 In Progress (Documentation Updates)

**Key Deliverables**:
- ✅ **Database Schema V1.4 Applied**:
  - ✅ `probability_models` table (immutable versions)
  - ✅ `strategies` table (immutable versions)
  - ✅ `trailing_stop_state` JSONB column in positions
  - ✅ `strategy_id`, `model_id` FKs in edges and trades
  - ✅ Helper views (active_strategies, active_models, trade_attribution)
- 🔄 **Documentation Updates** (7-day plan):
  - ✅ Day 1: DATABASE_SCHEMA_SUMMARY V1.4
  - 🔄 Day 2: MASTER_REQUIREMENTS V2.4, ARCHITECTURE_DECISIONS V2.4
  - Day 3: PROJECT_OVERVIEW V1.4, DEVELOPMENT_PHASES V1.2
  - Day 4: CONFIGURATION_GUIDE V3.1, YAML files updates
  - Day 5: VERSIONING_GUIDE (new), TRAILING_STOP_GUIDE (new)
  - Day 6: POSITION_MANAGEMENT_GUIDE, CONFIG_GUIDE, PHASE_1.5_PLAN
  - Day 7: MASTER_INDEX V2.3, final review

**Architecture Decision**: ADR-019 - Immutable Versions
- Strategy and model configs are IMMUTABLE once created
- To change config: Create new version (v1.0 → v1.1)
- Only status and metrics update in-place
- NO row_current_ind in strategies/probability_models tables

**Why Phase 0.5?**
- Versioning must be in database schema BEFORE Phase 1 implementation
- Trailing stops are core position management, not bolt-on
- Better to have complete foundation before writing code
- Prevents refactoring later (Phase 1-4 will use versioned tables immediately)

**Documentation**:
- `DATABASE_SCHEMA_SUMMARY_V1.4.md`
- `MASTER_REQUIREMENTS_V2.4.md` (this doc)
- `ARCHITECTURE_DECISIONS_V2.4.md` (includes ADR-019)
- `VERSIONING_GUIDE.md` (new)
- `TRAILING_STOP_GUIDE.md` (new)
- `CLAUDE_CODE_IMPLEMENTATION_PLAN.md` (Phase 0.5 details)
- `DOCUMENTATION_UPDATE_PLAN.md` (7-day schedule)

---

### Phase 1: Core Foundation (Weeks 1-2)
**Goal**: Establish project structure, Kalshi API connectivity, and account management.

**Key Deliverables**:
- Project setup with .env configuration
- Kalshi API client with HMAC-SHA256 authentication
- Database connection and ORM models for account data (using V1.4 schema)
- **Decimal conversion utilities** in `utils/decimal_helpers.py`
- CRUD operations with versioning (RowCurrentInd)
- CLI to fetch/store balance, positions, fills, settlements
- Unit tests for API client, database operations, and decimal conversion
- **Verify all prices stored as DECIMAL(10,4)**

**Critical**: Parse `*_dollars` fields from Kalshi API, NEVER integer cents

**Documentation**: `API_INTEGRATION_GUIDE.md` (Kalshi section), `DEVELOPER_ONBOARDING.md`, `KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md`

---

### Phase 1.5: Foundation Validation (Week 2.5)
**Goal**: Validate Phase 0.5 enhancements before proceeding to Phase 2.

**Key Deliverables**:
- **Strategy Manager** (`trading/strategy_manager.py`):
  - CRUD operations for strategies table
  - Version validation (enforce immutability)
  - Status lifecycle management
  - Active strategy lookup
- **Model Manager** (`analytics/model_manager.py`):
  - CRUD operations for probability_models table
  - Version validation (enforce immutability)
  - Status lifecycle management
  - Active model lookup
- **Position Manager Enhancements** (`trading/position_manager.py`):
  - Trailing stop state initialization
  - Trailing stop update logic
  - Stop trigger detection
- **Configuration System** (`utils/config.py`):
  - YAML file loading
  - Configuration validation
  - Override handling
- **Unit Tests**:
  - Test immutable version enforcement
  - Test trailing stop logic
  - Test version lifecycle transitions
  - Test trade attribution queries

**Why Phase 1.5?**
- Validate versioning system works before building on it
- Ensure trailing stops integrate properly with positions
- Test configuration system before Phase 2 complexity
- Prevent cascading errors in later phases

**Documentation**: `PHASE_1.5_PLAN.md` (detailed implementation guide)

---

### Phase 2: Football Market Data (Weeks 3-4)
**Goal**: Fetch and store NFL/NCAAF series, events, and markets with decimal precision.

**Key Deliverables**:
- ORM models for series, events, markets tables (all prices DECIMAL(10,4))
- Pagination handling for large API responses
- Scripts to fetch series (filter: category=football, tags=NFL/NCAAF)
- Scripts to fetch events (by series_ticker) with final_state capture
- Scripts to fetch markets (by event_ticker) with live price updates
- **Decimal price validation** - reject any non-DECIMAL values
- CLI commands: `main.py fetch-series`, `fetch-events`, `fetch-markets`
- Unit tests for pagination, market data CRUD, and decimal precision

**Documentation**: `API_INTEGRATION_GUIDE.md` (Kalshi pagination), `DATABASE_SCHEMA_SUMMARY_V1.4.md` (relationships)

---

### Phase 3: Live Game Stats (Weeks 5-6)
**Goal**: Retrieve and store live statistics from ESPN, Balldontlie, SportsRadar APIs.

**Key Deliverables**:
- ORM model for game_states table
- ESPN API client for NFL/NCAAF scoreboards
- Balldontlie API client (fallback for NFL)
- SportsRadar API client (premium data, optional)
- NCAAF API client for college football stats
- Script to poll live stats every 30 seconds during games
- Link game_states to events via event_id
- CLI command: `main.py fetch-live-stats`
- Unit tests for stat parsers and API clients

**Documentation**: `API_INTEGRATION_GUIDE.md` (ESPN, Balldontlie, SportsRadar sections)

---

### Phase 4: Probability Calculation & Edge Detection (Weeks 7-9)
**Goal**: Generate historical probabilities, compute true probabilities using versioned models, and identify EV+ opportunities.

**Key Deliverables**:
- Historical data loader (query ESPN/Balldontlie 2019-2024 archives)
- Generate probability matrices with win probabilities (DECIMAL precision)
- Load probability data into probability_matrices table
- **Create initial probability model versions** (elo_nfl v1.0, regression_nba v1.0)
- Probability calculator: map game_states → state descriptors/value buckets → lookup win probability
- **Model version selection** - Use active model for calculations
- Edge detector: compare true probabilities vs. market prices, calculate EV with DECIMAL math
- **Link edges to model versions** (store model_id in edges table)
- Risk manager: Kelly Criterion position sizing, exposure limits
- **Decimal-safe EV calculations** - no float rounding errors
- ORM models for edges table
- CLI command: `main.py compute-edges`
- Unit tests for odds calculation, edge detection, decimal arithmetic, and model versioning

**Phase 4 Enhancement (from Phase 0.5)**: Model versioning logic implemented here
- Create model versions (v1.0, v1.1, v2.0)
- Validate model performance
- Compare model versions (A/B testing)
- Activate/deprecate models

**Documentation**: `EDGE_DETECTION_SPEC.md` (formulas, buckets, EV calculation with Decimal), `VERSIONING_GUIDE.md` (model versioning examples)

---

### Phase 5: Position Monitoring & Exit Management (Weeks 10-14)
**Goal**: Monitor open positions dynamically and execute strategic exits based on priority hierarchy and urgency.

**Phase 5 Split**: Now divided into Phase 5a (Monitoring & Evaluation) and Phase 5b (Execution & Walking) for clearer implementation.

#### **Phase 5a: Position Monitoring & Exit Evaluation (Weeks 10-12)**

**REQ-MON-001**: **Dynamic Monitoring Frequencies**
- 30-second normal monitoring for stable positions
- 5-second urgent monitoring when within 2% of stop loss, profit target, or trailing stop
- Cache market prices for 10 seconds (reduces API calls ~66%)
- Enforce 60 API calls/minute maximum (stay under Kalshi limits)

**REQ-MON-002**: **Position State Tracking**
- Update positions table: current_price, unrealized_pnl, unrealized_pnl_pct, last_update
- Maintain trailing_stop_state as JSONB (active, peak_price, current_stop_price, current_distance)
- Update peak_price and trailing_stop_price on favorable moves

**REQ-EXIT-001**: **Exit Priority Hierarchy**
- 4-level priority system: CRITICAL > HIGH > MEDIUM > LOW
- Resolve multiple triggers by highest priority
- Log all triggered conditions to exit_attempts table

**REQ-EXIT-002**: **10 Exit Conditions**
1. **CRITICAL**: stop_loss, circuit_breaker
2. **HIGH**: trailing_stop, time_based_urgent (<5 min), liquidity_dried_up (spread >3¢ or volume <50)
3. **MEDIUM**: profit_target, partial_exit_target
4. **LOW**: early_exit (edge <2%), edge_disappeared (edge negative), rebalance

**NOTE**: edge_reversal REMOVED (redundant with early_exit + edge_disappeared + stop_loss)

**REQ-EXIT-003**: **Partial Exit Staging**
- Stage 1: Exit 50% at +15% profit
- Stage 2: Exit 25% (of remaining) at +25% profit
- Remaining 25%: Rides with trailing stop
- Track in position_exits table

#### **Phase 5b: Exit Execution & Order Walking (Weeks 13-14)**

**REQ-EXEC-001**: **Urgency-Based Execution**
- **CRITICAL**: Market orders, 5s timeout, retry market if fails
- **HIGH**: Aggressive limits, 10s timeout, walk 2x then market
- **MEDIUM**: Fair limits, 30s timeout, walk up to 5x
- **LOW**: Conservative limits, 60s timeout, walk up to 10x

**REQ-EXEC-002**: **Price Walking Algorithm**
- Start with limit order at calculated price
- If no fill within timeout, walk price by 1¢ toward market
- Repeat up to max_walks based on urgency
- HIGH urgency: escalate to market after max walks
- MEDIUM/LOW: give up after max walks

**REQ-EXEC-003**: **Exit Attempt Logging**
- Record every attempt in exit_attempts table: position_id, exit_condition, priority_level, order_type, prices, timeouts
- Enable analysis: "Why didn't my exit fill?"

**Common Requirements (Phase 5a + 5b)**:
- **Create initial strategy versions** (halftime_entry v1.0, underdog_fade v1.0)
- Kalshi order creation endpoint integration
- Compliance checker (daily loss limits, position limits, version status)
- **Strategy version selection** - Use active strategy for execution
- **Link trades to strategy and model versions** (store strategy_id, model_id in trades table)
- **Initialize trailing stops** on position entry
- **Decimal price validation** before order submission
- CLI commands: `main.py monitor-positions`, `main.py execute-exits --manual`, `main.py execute-trades --manual`
- Unit tests for monitoring, exit evaluation, execution, and attribution

**Database V1.4 → V1.5**:
- positions table: Add current_price, unrealized_pnl, unrealized_pnl_pct, last_update, trailing_stop_state, exit_reason, exit_priority
- position_exits table (NEW): Track each exit event (including partials)
- exit_attempts table (NEW): Track each exit order attempt (for walking/debugging)

**Documentation**: `POSITION_MANAGEMENT_GUIDE.md`, `PHASE_5_POSITION_MONITORING_SPEC_V1_0.md`, `PHASE_5_EXIT_EVALUATION_SPEC_V1_0.md`, `PHASE_5_EVENT_LOOP_ARCHITECTURE_V1_0.md`, `VERSIONING_GUIDE.md`, `TRAILING_STOP_GUIDE.md`

---

### Phase 6: Expand to Other Sports (Weeks 15-16)
**Goal**: Add NBA, MLB, Tennis, and other sports markets with versioned models.

**Key Deliverables**:
- Identify Kalshi series for new sports
- API clients for NBA/MLB/Tennis stats (ESPN or alternatives)
- Generate historical probability matrices for new sports (DECIMAL precision)
- **Create sport-specific model versions** (elo_nba v1.0, elo_mlb v1.0)
- Add new sport data to probability_matrices table
- Extend edge detector to support multiple sports
- **Sport-specific Kelly fractions** (NFL: 0.25, NBA: 0.22, Tennis: 0.18)
- CLI command: `main.py fetch-markets --sport NBA`

**Documentation**: `API_INTEGRATION_GUIDE.md` (new sport APIs), update `EDGE_DETECTION_SPEC.md`, `VERSIONING_GUIDE.md` (sport-specific model examples)

---

### Phase 7: Live Trading for Other Sports (Weeks 15-16)
**Goal**: Enable automated trading across all supported sports with versioned strategies.

**Key Deliverables**:
- Validate probability accuracy for new sports via backtesting
- **Create sport-specific strategy versions** for new sports
- Sport-specific risk calibration (adjust volatility parameters, max spreads)
- Enable multi-sport automated scheduler
- **Cross-sport exposure tracking** to prevent over-concentration
- **Trailing stops** for all sports positions
- CLI command: `main.py trade --sport all --auto`

**Documentation**: Update `EDGE_DETECTION_SPEC.md` (sport-specific adjustments), `VERSIONING_GUIDE.md` (multi-sport versioning)

---

### Phase 8: Non-Sports Markets (Weeks 17-20)
**Goal**: Explore political, entertainment, and culture markets with versioned models.

**Phase 8a: Political Markets**
- Web scraper for RealClearPolling
- Poll aggregation and trend analysis
- Generate political probability matrices from historical poll-to-outcome data (DECIMAL)
- **Create political model versions** (polling_aggregator v1.0)
- Extend edge detector for political markets

**Phase 8b: Entertainment Markets**
- Web scraper for BoxOfficeMojo
- Opening weekend prediction models
- Generate entertainment probability matrices (DECIMAL)
- **Create entertainment model versions** (boxoffice_predictor v1.0)
- Extend edge detector for box office markets

**Phase 8c: Culture Markets** (Future)
- Scrapers for social media mentions, speeches
- Sentiment analysis with NLP
- **Create culture model versions** (sentiment_analyzer v1.0)
- Extend edge detector for culture markets

**Documentation**: `WEB_SCRAPING_GUIDE.md` (BeautifulSoup/Scrapy examples, rate limiting), `VERSIONING_GUIDE.md` (non-sports model examples)

---

### Phase 9: MCPs & Advanced Integrations (Weeks 21-24)
**Goal**: Integrate Model Context Protocols and advanced data sources. Use existing versioning system from Phase 4.

**Key Deliverables**:
- Plus EV API integration for line shopping
- SportsRadar API for advanced metrics
- MCP integrations for Claude Code assistance
- Advanced team performance metrics (DVOA, SP+, Elo ratings)
- **Create ensemble model versions** combining multiple data sources
- Cross-platform data aggregation
- Enhanced edge detection with premium data
- **Use existing model versioning system** (create new model versions, don't rebuild system)

**Documentation**: `MCP_INTEGRATION_GUIDE.md`, update `API_INTEGRATION_GUIDE.md`, `VERSIONING_GUIDE.md` (ensemble model examples)

---

### Phase 10: Multi-Platform Expansion - Polymarket (Weeks 25-28)
**Goal**: Abstract platform-specific logic and add Polymarket support with unified versioning.

**Key Deliverables**:
- Platform abstraction layer (`platforms/base_platform.py`)
- Kalshi platform adapter (`platforms/kalshi_platform.py`)
- Polymarket platform adapter (`platforms/polymarket_platform.py`)
- Platform factory for selecting execution venue
- Cross-platform market linking (`platform_markets` table)
- **Cross-platform price comparison** - find best execution venue
- **Unified decimal handling** across platforms
- **Unified versioning** - same strategy/model versions work across platforms
- Multi-platform position tracking with trailing stops
- CLI command: `main.py trade --platform polymarket`

**Platform Selection Strategy**:
1. Detect same event/market across platforms
2. Compare prices (net of fees) using DECIMAL precision
3. Execute on platform with best price using same strategy version
4. Track positions across all platforms
5. Aggregate version performance across platforms

**Critical Considerations**:
- Different fee structures per platform
- Different settlement mechanisms
- Different API authentication methods
- Unified compliance checking
- Cross-platform exposure limits
- Trailing stops work consistently across platforms

**Documentation**: `POLYMARKET_INTEGRATION_GUIDE.md`, `PLATFORM_ABSTRACTION_DESIGN.md`, update `ARCHITECTURE_DECISIONS.md`, `VERSIONING_GUIDE.md` (cross-platform versioning)

---

## 6. Configuration & Environment

### 6.1 Environment Variables (.env.template)
```bash
# Kalshi Authentication
KALSHI_API_KEY=your_kalshi_api_key_here
KALSHI_API_SECRET=your_kalshi_api_secret_here
KALSHI_BASE_URL=https://demo-api.kalshi.co  # Use demo for testing
# KALSHI_BASE_URL=https://trading-api.kalshi.com  # Production URL

# Polymarket Authentication (Phase 10)
POLYMARKET_API_KEY=placeholder_for_phase_10
POLYMARKET_PRIVATE_KEY=placeholder_for_phase_10

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog
DB_USER=postgres
DB_PASSWORD=your_password

# API Keys
BALLDONTLIE_API_KEY=your_key
SPORTSRADAR_API_KEY=placeholder_for_phase_9
PLUS_EV_API_KEY=placeholder_for_phase_9

# Trading Parameters
MIN_EV_THRESHOLD=0.05      # 5% minimum edge (DECIMAL)
MAX_POSITION_SIZE=1000     # Max $ per position (DECIMAL)
MAX_TOTAL_EXPOSURE=10000   # Max $ at risk (DECIMAL)
KELLY_FRACTION_NFL=0.25    # NFL Kelly multiplier
KELLY_FRACTION_NBA=0.22    # NBA Kelly multiplier
KELLY_FRACTION_TENNIS=0.18 # Tennis Kelly multiplier

# Platform Configuration (Phase 10)
ENABLED_PLATFORMS=kalshi    # Comma-separated: kalshi,polymarket
DEFAULT_PLATFORM=kalshi

# Environment
TRADING_ENV=PROD           # PROD or DEMO
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR

# Decimal Precision
DECIMAL_PRECISION=4        # Always 4 for sub-penny pricing

# Versioning (Phase 0.5)
DEFAULT_STRATEGY_VERSION=v1.0  # Default strategy version to use
DEFAULT_MODEL_VERSION=v1.0     # Default model version to use
ENABLE_VERSION_TRACKING=true   # Enable trade attribution to versions
```

### 6.2 YAML Configuration Files

**All YAML files in `config/` directory:**

1. **trading.yaml** - Trading execution parameters, trailing stop defaults
2. **trade_strategies.yaml** - Strategy-specific settings, version configurations
3. **position_management.yaml** - Risk limits, Kelly fractions, trailing stop rules
4. **probability_models.yaml** - Probability calculation model definitions, version settings
5. **markets.yaml** - Market filtering and sport configurations
6. **data_sources.yaml** - All API endpoints and authentication
7. **system.yaml** - Logging, scheduling, system-level settings

**See CONFIGURATION_GUIDE_V3.1.md for detailed YAML specifications including versioning and trailing stop configurations**

### 6.3 Dependencies (requirements.txt)
```
python-dotenv==1.0.0
requests==2.31.0
aiohttp==3.9.1
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pandas==2.1.4
numpy==1.26.2
spacy==3.7.2
pytest==7.4.3
apscheduler==3.10.4
beautifulsoup4==4.12.2
pyyaml==6.0.1

# ⚠️ CRITICAL - Never use these for prices
# decimal is built-in, no installation needed
# NEVER: from numpy import float64  # Will cause rounding errors
# NEVER: price = float(...)          # Will cause rounding errors
# ALWAYS: from decimal import Decimal
# ALWAYS: price = Decimal("0.4975")
```

**Detailed setup instructions**: See `ENVIRONMENT_CHECKLIST.md`, `DEPLOYMENT_GUIDE.md`

---

## 7. Testing Strategy

### 7.1 Test Coverage Goals
- **Unit Tests**: >80% code coverage
- **Integration Tests**: All API → DB workflows
- **End-to-End Tests**: Full pipeline (fetch → calculate → trade → attribute)
- **Decimal Precision Tests**: Verify no float rounding in price handling
- **Versioning Tests**: Verify immutability enforcement and trade attribution

### 7.2 Test Categories
1. **API Client Tests**: Mock responses, test pagination, retry logic, decimal parsing
2. **Database Tests**: CRUD operations, versioning, constraint validation, DECIMAL storage, immutability enforcement
3. **Analytics Tests**: Odds calculation accuracy, edge detection logic, decimal arithmetic, model versioning
4. **Trading Tests**: Order generation, compliance checks, execution simulation, price precision, strategy versioning, trade attribution
5. **Decimal Tests**: Conversion accuracy, arithmetic precision, no float contamination
6. **Versioning Tests**: Immutability enforcement, version lifecycle, A/B testing queries, trade attribution
7. **Trailing Stop Tests**: State initialization, stop updates, trigger detection

### 7.3 Test Fixtures
- Mock Kalshi API responses (series, events, markets with decimal prices)
- Mock ESPN/Balldontlie game data
- Sample historical odds JSON (DECIMAL values)
- Mock database with seed data (all prices DECIMAL, sample strategy/model versions)
- Decimal edge cases (sub-penny prices, large calculations)
- Versioning edge cases (immutability violations, lifecycle transitions)
- Trailing stop scenarios (activation, updates, triggers)

### 7.4 Critical Tests (Including New Phase 0.5 Tests)

**Decimal Precision Tests:**
```python
def test_decimal_price_parsing():
    """Verify Kalshi *_dollars fields parsed as Decimal"""
    api_response = {"yes_bid_dollars": "0.4975"}
    price = parse_price(api_response["yes_bid_dollars"])
    assert isinstance(price, Decimal)
    assert price == Decimal("0.4975")

def test_no_float_contamination():
    """Verify floats never enter price calculations"""
    price1 = Decimal("0.4975")
    price2 = Decimal("0.5025")
    spread = price2 - price1
    assert isinstance(spread, Decimal)
    assert spread == Decimal("0.0050")

def test_ev_calculation_precision():
    """Verify EV calculated with Decimal precision"""
    true_prob = Decimal("0.5500")
    market_price = Decimal("0.4975")
    ev = (true_prob - market_price) / market_price
    assert isinstance(ev, Decimal)
    assert ev > Decimal("0.05")  # 5% threshold
```

**Versioning Tests (NEW in Phase 0.5):**
```python
def test_strategy_immutability():
    """Verify strategy config cannot be changed after creation"""
    strategy = create_strategy("halftime_entry", "v1.0", {"min_lead": 7})
    with pytest.raises(ImmutabilityError):
        strategy.config = {"min_lead": 10}  # Should fail

def test_strategy_version_creation():
    """Verify new version can be created with different config"""
    v1 = create_strategy("halftime_entry", "v1.0", {"min_lead": 7})
    v2 = create_strategy("halftime_entry", "v1.1", {"min_lead": 10})
    assert v1.config["min_lead"] == 7
    assert v2.config["min_lead"] == 10

def test_trade_attribution():
    """Verify trades link to exact strategy and model versions"""
    strategy = get_strategy("halftime_entry", "v1.1")
    model = get_model("elo_nfl", "v2.0")
    trade = execute_trade(market_id, strategy_id=strategy.id, model_id=model.id)
    assert trade.strategy_id == strategy.id
    assert trade.model_id == model.id

def test_version_lifecycle():
    """Verify status transitions work correctly"""
    strategy = create_strategy("test", "v1.0", {})
    assert strategy.status == "draft"
    strategy.activate()
    assert strategy.status == "active"
    strategy.deprecate()
    assert strategy.status == "deprecated"
```

**Trailing Stop Tests (NEW in Phase 0.5):**
```python
def test_trailing_stop_initialization():
    """Verify trailing stop state initialized correctly"""
    position = create_position(entry_price=Decimal("0.7500"))
    assert position.trailing_stop_state["enabled"] == True
    assert position.trailing_stop_state["activation_price"] == Decimal("0.7500")

def test_trailing_stop_update():
    """Verify trailing stop moves with favorable price"""
    position = create_position(entry_price=Decimal("0.7500"))
    update_position(position, market_price=Decimal("0.8000"))
    assert position.trailing_stop_state["highest_price"] == Decimal("0.8000")
    assert position.trailing_stop_state["current_stop"] > Decimal("0.7500")

def test_trailing_stop_trigger():
    """Verify stop loss triggers at correct price"""
    position = create_position(entry_price=Decimal("0.7500"))
    update_position(position, market_price=Decimal("0.8000"))
    trigger = check_stop_trigger(position, market_price=Decimal("0.7400"))
    assert trigger == True  # Should trigger stop loss
```

**Detailed test cases and fixtures**: See `TESTING_GUIDE.md`

---

## 8. Error Handling & Logging

### 8.1 Error Categories
- **API Errors**: 4xx/5xx responses, timeouts, rate limits
- **Database Errors**: Connection failures, constraint violations, immutability violations
- **Trading Errors**: Order rejections, insufficient balance
- **Data Errors**: Missing fields, stale data
- **Decimal Errors**: Float contamination, precision loss
- **Versioning Errors**: Immutability violations, version conflicts, missing version links

### 8.2 Logging Levels
- **DEBUG**: API request/response details, SQL queries, decimal conversions, version lookups
- **INFO**: Normal operations (markets fetched, edges calculated, versions created)
- **WARNING**: Recoverable errors (API retry, missing data, float detected in prices, version deprecation)
- **ERROR**: Critical failures (DB connection lost, trade failed, decimal precision lost, immutability violation)

### 8.3 Audit Trail
- All API calls logged with timestamp, endpoint, parameters
- All trades logged with market_id, side, price (DECIMAL), quantity, strategy_id, model_id
- All edge calculations logged with EV (DECIMAL), confidence level, model_id
- All decimal conversions logged in DEBUG mode
- All version creations/updates logged with timestamp, version number, status change
- All trailing stop updates logged with price movements and trigger events
- Log rotation: 7 days retention, compressed archives

### 8.4 Error Detection

**Log WARNING if:**
- Float detected in price variable: `if isinstance(price, float): log.warning(...)`
- Decimal precision loss: `if price.as_tuple().exponent < -4: log.warning(...)`
- String→Decimal conversion fails: `except InvalidOperation: log.error(...)`
- Version not found: `if version is None: log.warning(...)`
- Trailing stop triggered: `log.warning("Stop loss triggered at price {price}")`

**Log ERROR if:**
- Immutability violation attempted: `log.error("Attempted to modify immutable version")`
- Trade without version attribution: `log.error("Trade missing strategy_id or model_id")`
- Trailing stop state corrupted: `log.error("Invalid trailing_stop_state JSONB")`

**Implementation details**: See `API_INTEGRATION_GUIDE.md` (retry logic), `utils/logger.py`, `utils/decimal_helpers.py`, `VERSIONING_GUIDE.md` (error handling)

---

## 9. Compliance & Risk Management

### 9.1 Kalshi Prohibitions
- No trading by league insiders (players, coaches, officials)
- No market manipulation or coordinated trading
- Adhere to Terms of Service

### 9.2 Polymarket Considerations (Phase 10)
- Verify regulatory compliance in user's jurisdiction
- Understand blockchain transaction finality
- Account for gas fees in EV calculations
- Follow Polymarket Terms of Service

### 9.3 Risk Limits (Configurable in YAML)
- **Max Position Size**: $1,000 per market (DECIMAL)
- **Max Total Exposure**: $10,000 across all markets
- **Max Correlated Exposure**: $5,000 (e.g., multiple games in same slate)
- **Kelly Fraction**: 25% of full Kelly for NFL (conservative sizing)
- **Sport-Specific Kelly**: NFL=0.25, NBA=0.22, Tennis=0.18
- **Cross-Platform Limits**: Aggregate positions across Kalshi + Polymarket
- **Trailing Stop Distance**: Configurable per strategy version (default: 5 cents)
- **Trailing Stop Activation**: Configurable profit threshold before activation

### 9.4 Circuit Breakers
- Stop trading if daily loss exceeds 10% of capital
- Pause if API connectivity fails for >5 minutes
- Alert if >3 consecutive trade rejections
- Halt if decimal precision error detected
- Alert if immutability violation detected
- Pause if trailing stops fail to update properly

**Detailed risk formulas**: See `EDGE_DETECTION_SPEC.md` (Kelly Criterion, exposure calculations with DECIMAL), `TRAILING_STOP_GUIDE.md` (stop loss calculations)

---

## 10. Performance Targets

- **Market Update Latency**: <2 seconds API → DB
- **Decimal Conversion**: <1ms per price (negligible overhead)
- **Edge Calculation**: <5 seconds for all active markets
- **Order Execution**: <10 seconds from edge detection to order placement
- **Database Queries**: <500ms for time-series lookups
- **Concurrent Markets**: Support 200+ markets simultaneously
- **Cross-Platform Comparison**: <3 seconds to compare prices across platforms
- **Version Lookup**: <100ms to resolve active strategy/model version
- **Trailing Stop Update**: <1 second to update stop state on price change
- **Trade Attribution Query**: <200ms to fetch trade with full version details

---

## 11. Future Enhancements

### Short-Term (6 months)
- Machine learning models for probability estimation (Phase 5+)
- Advanced team metrics (DVOA, SP+, Elo ratings) (Phase 9)
- Web dashboard for monitoring (React + FastAPI)
- Mobile alerts for high-confidence edges
- Live price streaming (WebSockets)
- Strategy backtesting framework with version comparison
- Model performance dashboards comparing version accuracy

### Long-Term (12+ months)
- Multi-leg arbitrage detection (cross-market)
- Portfolio optimization algorithms with Decimal precision
- Cloud deployment (AWS ECS/Lambda)
- Additional prediction market platforms (PredictIt, Manifold)
- Machine learning for optimal Kelly fraction tuning
- Cross-platform automated arbitrage execution
- Automated strategy parameter optimization (create new versions automatically)
- Ensemble model creation from multiple version performances

---

## 12. Key Resources

### External Documentation
- **Kalshi API Docs**: https://docs.kalshi.com/api-reference/
- **Kalshi Sample Code**: https://github.com/Kalshi/kalshi-starter-code-python
- **Polymarket Docs**: https://docs.polymarket.com/ (Phase 10)
- **ESPN API Guide**: https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b
- **Balldontlie NFL API**: https://nfl.balldontlie.io/
- **NCAAF API**: https://github.com/henrygd/ncaa-api
- **Python Decimal Documentation**: https://docs.python.org/3/library/decimal.html
- **Semantic Versioning**: https://semver.org/

### Internal Documentation (docs/ folder)

**Critical - Read First:**
1. **KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md** ⚠️ **PRINT AND KEEP AT DESK**
2. **DEVELOPER_ONBOARDING.md** - Getting started guide
3. **VERSIONING_GUIDE.md** - NEW in Phase 0.5 - Strategy and model versioning patterns

**Reference Documentation:**
4. `API_INTEGRATION_GUIDE.md` - Detailed API specifications
5. `DATABASE_SCHEMA_SUMMARY_V1.4.md` - Full schema with versioning tables
6. `EDGE_DETECTION_SPEC.md` - Mathematical formulas
7. `CONFIGURATION_GUIDE_V3.1.md` - YAML configuration reference (includes versioning configs)
8. `ARCHITECTURE_DECISIONS_V2.4.md` - Design rationale and trade-offs (includes ADR-019: Immutable Versions)

**Development Guides:**
9. `TESTING_GUIDE.md` - Test cases and fixtures
10. `DEPLOYMENT_GUIDE.md` - Setup and deployment
11. `ENVIRONMENT_CHECKLIST.md` - Windows 11 setup guide
12. `TRAILING_STOP_GUIDE.md` - NEW in Phase 0.5 - Trailing stop loss implementation
13. `POSITION_MANAGEMENT_GUIDE.md` - Enhanced position management
14. `PHASE_1.5_PLAN.md` - Foundation validation plan

**Phase 10 Documentation:**
15. `POLYMARKET_INTEGRATION_GUIDE.md` - Multi-platform strategy
16. `PLATFORM_ABSTRACTION_DESIGN.md` - Architecture for multiple platforms

**Planning Documents:**
17. `CLAUDE_CODE_IMPLEMENTATION_PLAN.md` - Phase 0.5 details and rationale
18. `DOCUMENTATION_UPDATE_PLAN.md` - 7-day documentation update schedule

---

## 13. Critical Reminders

### ⚠️ Decimal Pricing (ALWAYS)
1. `from decimal import Decimal` in every file handling prices
2. Parse Kalshi `*_dollars` fields (e.g., `yes_bid_dollars`)
3. NEVER parse integer cents fields (deprecated)
4. Store all prices as DECIMAL(10,4) in PostgreSQL
5. Convert strings to Decimal: `Decimal("0.4975")` NOT `Decimal(0.4975)`
6. Print and reference KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md

### ⚠️ Database Queries (ALWAYS)
1. Include `WHERE row_current_ind = TRUE` for versioned data (markets, positions, edges, game_states)
2. Use `WHERE status = 'active'` for immutable versions (strategies, probability_models)
3. Never query without appropriate filter
4. Use DECIMAL types in SQLAlchemy models
5. Link trades to strategy_id and model_id for attribution

### ⚠️ Versioning (ALWAYS - NEW in Phase 0.5)
1. Strategy and model configs are IMMUTABLE once created
2. To change config: Create new version (v1.0 → v1.1)
3. Only status and metrics update in-place
4. ALWAYS link trades to strategy_id and model_id
5. Use semantic versioning (major.minor: v1.0, v1.1, v2.0)
6. Test version immutability in unit tests
7. Reference VERSIONING_GUIDE.md for patterns

### ⚠️ Configuration (ALWAYS)
1. Load settings from YAML files in `config/` directory
2. Use `.env` only for secrets and environment-specific values
3. Validate all configuration on startup
4. Version strategy/model configs are stored in database, not YAML

### ⚠️ Testing (ALWAYS)
1. Mock external APIs in tests
2. Test decimal precision explicitly
3. Verify no float contamination in price handling
4. Test version immutability enforcement
5. Test trailing stop logic thoroughly
6. Achieve >80% code coverage

---

## 14. Contact & Support

**Project Lead**: [Your Name]
**Development Team**: [Team Members]
**Repository**: [GitHub URL when available]

For questions or issues:
1. Check supplementary docs in `docs/` folder
2. Review KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md for pricing issues
3. Review VERSIONING_GUIDE.md for versioning questions
4. Review test cases for implementation examples
5. Submit GitHub issues for bugs or feature requests

---

## 15. Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.9 | 2025-10-08 | Initial draft (Session 5) |
| 2.0 | 2025-10-09 | Added decimal pricing, Phase 10 (Polymarket), updated tech stack, multi-platform architecture |
| 2.2 | 2025-10-16 | Updated terminology (odds → probability); renamed odds_models.yaml → probability_models.yaml; clarified probability vs. market price; updated table names (odds_matrices → probability_matrices) |
| 2.3 | 2025-10-16 | Updated environment variable names to match env.template; updated directory structure (data_storers/ → database/) |
| 2.4 | 2025-10-19 | **MAJOR UPDATE**: Added Phase 0.5 (Foundation Enhancement); added versioning requirements (strategies, probability_models with immutable pattern); added trailing stop loss requirements; updated database overview to V1.4; added Phase 1.5 (Foundation Validation); updated all phase descriptions to reflect versioning enhancements; added ADR-019 reference |

---

**NEXT**: Complete Phase 0.5 Day 2 documentation updates (ARCHITECTURE_DECISIONS V2.4)

---

**END OF MASTER REQUIREMENTS V2.4**
