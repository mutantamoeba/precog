# Development Phases & Roadmap

---
**Version:** 1.3
**Last Updated:** 2025-10-21
**Status:** ✅ Current
**Changes in v1.3:**
- **MAJOR**: Split Phase 5 into Phase 5a (Monitoring & Evaluation, Weeks 10-12) and Phase 5b (Execution & Walking, Weeks 13-14)
- Updated Phase 0.5 to 100% complete (Days 1-10 finished)
- Added comprehensive Phase 5a requirements (REQ-MON-*, REQ-EXIT-*)
- Added Phase 5b requirements (REQ-EXEC-* with price walking algorithm)
- Updated database schema to V1.5 (position_exits, exit_attempts tables)
- Added 10 exit conditions with priority hierarchy
- Created VERSIONING_GUIDE, TRAILING_STOP_GUIDE, POSITION_MANAGEMENT_GUIDE
- Updated timeline: Phase 5 total now 4 weeks (was 6 weeks)

**Changes in v1.2:** Added Phase 0.5 (Foundation Enhancement) and Phase 1.5 (Foundation Validation); updated to reflect database schema V1.4 with versioning system; updated timeline to include new phases
**Changes in v1.1:** Clarified Phase 2 (live data), Phase 3 (processing only, no edges), Phase 4 (odds/edges/historical loader); added new deliverables (GLOSSARY Phase 0, DEVELOPER_ONBOARDING Phase 0, DEPLOYMENT_GUIDE Phase 1, MODEL_VALIDATION/BACKTESTING_PROTOCOL Phase 4, USER_GUIDE Phase 5); updated Phase 0 to 100% complete.
---

## Timeline Overview (Realistic Part-Time Estimate)

**Total to Phase 10:** ~1.5-2 years (82 weeks @ 12 hours/week)
**MVP Trading (Phase 5):** ~8 months from Phase 0 start (includes Phase 0.5 and 1.5)
**Current Status:** Phase 0.5 ✅ **100% COMPLETE** (All Days 1-10 finished; ready for Phase 1)

---

## Phase Structure

Each phase has codenames from sci-fi references for fun tracking. Phases are sequential with clear dependencies (see Phase Dependencies Table in PROJECT_OVERVIEW_V1.2.md).

---

## Phase 0: Foundation (Codename: "Genesis")

**Duration:** 8 weeks  
**Status:** ✅ **100% COMPLETE** (Session 7)  
**Goal:** Create comprehensive documentation, configuration system, and project foundation

### Deliverables

#### Core Documentation
- [✅] MASTER_REQUIREMENTS_V2.1.md (complete system requirements)
- [✅] PROJECT_OVERVIEW_V1.2.md (architecture, tech stack, data flow)
- [✅] MASTER_INDEX_V2.1.md (document inventory with locations and phase ties)
- [✅] ARCHITECTURE_DECISIONS_V2.1.md (ADRs 1-15+)
- [✅] DATABASE_SCHEMA_SUMMARY_V1.1.md (complete schema with SCD Type 2)
- [✅] CONFIGURATION_GUIDE_V2.1.md (YAML patterns, DECIMAL format)
- [✅] GLOSSARY_V1.0.md (terminology: EV, Kelly, edge, Elo, etc.)

#### API & Integration
- [✅] API_INTEGRATION_GUIDE_V1.0.md (Kalshi/ESPN/Balldontlie, RSA-PSS auth)
- [✅] KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md (critical reference)
- [✅] ODDS_RESEARCH_COMPREHENSIVE.md (historical odds methodology)

#### Configuration Files
- [✅] system.yaml (DB, logging, API settings)
- [✅] trading.yaml (Kelly fractions, DECIMAL examples)
- [✅] odds_models.yaml (Elo, regression, ML, historical_lookup ensemble)
- [✅] position_management.yaml (position sizing, CI adjustments)
- [✅] trade_strategies.yaml (entry/exit strategies, halftime_entry)
- [✅] markets.yaml (market filtering, research_gap_flag)
- [✅] data_sources.yaml (API endpoints, nflfastR config)
- [✅] .env.template (all Phase 1-10 API keys placeholders)

#### Process & Utility
- [✅] DEVELOPMENT_PHASES_V1.1.md (this file - roadmap)
- [✅] ENVIRONMENT_CHECKLIST_V1.1.md (Windows 11 setup, Parts 1-7)
- [✅] REQUIREMENTS_AND_DEPENDENCIES_V1.0.md (comprehensive vs. sample reqs.txt)
- [✅] VERSION_HEADERS_GUIDE_V2.1.md (version control standards)
- [✅] Handoff_Protocol_V1.0.md (session management, token budget, phase assessment)
- [✅] PROJECT_STATUS.md (living status tracker)
- [✅] DOCUMENT_MAINTENANCE_LOG.md (change tracking with impacts)
- [✅] DEVELOPER_ONBOARDING_V1.0.md (merged with ENVIRONMENT_CHECKLIST, onboarding steps)

### Tasks Completed
1. ✅ Created comprehensive system architecture
2. ✅ Designed database schema with SCD Type 2
3. ✅ Documented all API integrations
4. ✅ Created 7 YAML configuration files
5. ✅ Established version control and handoff systems
6. ✅ Streamlined documentation (73% reduction, 11 docs → 4)
7. ✅ Integrated historical model into configs
8. ✅ Set up developer onboarding process

### Success Criteria
- [✅] Complete documentation for all foundational systems
- [✅] Clear architecture patterns established
- [✅] Risk mitigation strategies defined
- [✅] All configuration files created and validated
- [✅] Handoff system tested and working (3-upload, <10 min)
- [✅] Phase dependencies mapped and documented

**Phase 0 Assessment:** ✅ PASSED (see SESSION_7_HANDOFF.md)

---

## Phase 0.5: Foundation Enhancement (Codename: "Upgrade")

**Duration:** 3 weeks
**Target:** October 2025
**Status:** ✅ **100% COMPLETE**
**Goal:** Enhance foundation with versioning system and trailing stops before Phase 1 implementation

### Dependencies
- Requires Phase 0: 100% complete ✅

### Tasks

#### Database Schema V1.5 (Days 1-2) ✅
- [✅] Create `strategies` table (immutable versions)
- [✅] Create `probability_models` table (immutable versions)
- [✅] Add `trailing_stop_state` JSONB to positions
- [✅] Add `strategy_id`, `model_id` FKs to edges and trades
- [✅] Create helper views (active_strategies, active_models, trade_attribution)
- [✅] Apply migration to precog_dev database
- [✅] Verify migration success

#### Documentation Updates (Days 1-10) ✅
- [✅] Day 1: DATABASE_SCHEMA_SUMMARY V1.4
- [✅] Day 2: MASTER_REQUIREMENTS V2.4, ARCHITECTURE_DECISIONS V2.4 (ADRs 18-23)
- [✅] Day 3: PROJECT_OVERVIEW V1.4, DEVELOPMENT_PHASES V1.2
- [✅] Day 4: position_management.yaml V2.0, probability_models.yaml V2.0, trade_strategies.yaml V2.0
- [✅] Day 5: MASTER_REQUIREMENTS V2.5, DATABASE_SCHEMA_SUMMARY V1.5
- [✅] Day 6: CONFIGURATION_GUIDE V3.1 (comprehensive)
- [✅] Day 7: VERSIONING_GUIDE.md, TRAILING_STOP_GUIDE.md
- [✅] Day 8: POSITION_MANAGEMENT_GUIDE.md, DEVELOPMENT_PHASES V1.3
- [✅] Day 9: Database schema V1.5 applied, MASTER_INDEX V2.3
- [✅] Day 10: Validation tools, final review

### Deliverables
- [✅] Database schema V1.5 applied and verified
- [✅] position_exits table (tracks exit events)
- [✅] exit_attempts table (tracks price walking attempts)
- [✅] Updated foundational documentation (MASTER_REQUIREMENTS V2.5, ARCHITECTURE_DECISIONS V2.4)
- [✅] Updated planning documentation (PROJECT_OVERVIEW V1.4, DEVELOPMENT_PHASES V1.3)
- [✅] VERSIONING_GUIDE.md (immutable versions, A/B testing)
- [✅] TRAILING_STOP_GUIDE.md (progressive tightening, JSONB state)
- [✅] POSITION_MANAGEMENT_GUIDE.md (10 exit conditions, complete lifecycle)
- [✅] Updated CONFIGURATION_GUIDE V3.1 with all Phase 5 enhancements
- [✅] All 3 YAML files updated to V2.0 (versioning + monitoring + exits)
- [✅] Updated MASTER_INDEX to V2.3

### Success Criteria
- [✅] Schema V1.5 deployed to precog_dev
- [✅] All new tables and columns created successfully
- [✅] All documentation updated to reflect versioning system
- [✅] Implementation guides available for Phase 1.5/4/5
- [✅] Architecture decisions documented (ADR-018 through ADR-023)
- [✅] 10 exit conditions documented with priority hierarchy
- [✅] Phase 5 requirements fully specified (REQ-MON-*, REQ-EXIT-*, REQ-EXEC-*)

**Architectural Decision:** Immutable Versions (ADR-019)
- Strategy and model configs are IMMUTABLE once created
- To change config: Create new version (v1.0 → v1.1)
- Enables A/B testing integrity and precise trade attribution
- NO row_current_ind in versioned tables (versions don't supersede each other)

---

## Phase 1: Core Infrastructure (Codename: "Bootstrap")

**Duration:** 6 weeks
**Target:** November-December 2025
**Status:** 🔵 Planned (awaits Phase 0.5 completion)
**Goal:** Build core infrastructure and Kalshi API integration

### Dependencies
- Requires Phase 0.5: 100% complete 🟢

### Tasks

#### 1. Environment Setup (Week 1)
- Python 3.12+ virtual environment
- PostgreSQL 15+ database installation
- Git repository initialization
- IDE configuration (VSCode recommended)
- Install dependencies from requirements.txt
- Verify Spacy model: `spacy download en_core_web_sm`

#### 2. Database Implementation (Weeks 1-2)
- Create all tables with proper indexes (from DATABASE_SCHEMA_SUMMARY_V1.1.md)
- Implement SCD Type 2 versioning logic (`row_current_ind`, `row_effective_date`, `row_expiration_date`)
- Write Alembic migration scripts
- Create CRUD operations in `database/crud_operations.py` (e.g., `get_active_edges()`)
- Implement `database/connection.py` with psycopg2 pool (pool_size: 5)
- Test with sample data

#### 3. Kalshi API Integration (Weeks 2-4)
- Implement RSA-PSS authentication (`cryptography` library, **not** HMAC-SHA256)
- Token refresh logic (30-minute cycle)
- REST endpoints: markets, events, series, balance, positions, orders
- WebSocket connection for real-time updates (Phase 2+)
- Error handling and exponential backoff retry logic
- Rate limiting (100 req/min, throttle if approaching)
- Parse `*_dollars` fields as DECIMAL (never int cents)

#### 4. Configuration System (Week 4)
- YAML loader with validation (`pyyaml`)
- Database override mechanism (config_overrides table)
- Config priority resolution (DB > YAML > defaults)
- CLI commands: `config-show`, `config-validate`, `config-set`
- DECIMAL range validation (e.g., Kelly 0.10-0.50)

#### 5. Logging Infrastructure (Week 5)
- File-based logging with rotation (`utils/logger.py`)
- Database logging for critical events (trades, errors, edge detections)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Performance metrics collection (latency, API call counts)
- Structured logging (JSON format for analysis)

#### 6. CLI Framework (Week 6)
- Click 8.1+ CLI framework (`main.py`)
- Commands: `db-init`, `health-check`, `config-show`, `config-validate`
- Example stubs for future commands (Phase 5: `edges-list`, `trade-execute`)
- Help documentation for all commands

### Deliverables
- Working Kalshi API client (`api_connectors/kalshi_client.py` with RSA-PSS)
- Complete database schema (all tables created and tested)
- Configuration system operational (YAML + DB overrides)
- Logging infrastructure (file + database)
- CLI framework (Click commands)
- DEPLOYMENT_GUIDE_V1.0.md (local setup + AWS stubs for Phase 7+)
- Test suite with >80% coverage
- Requirements traceability matrix (REQ-001 through REQ-050 mapped to code)

### Success Criteria
- [  ] Can authenticate with Kalshi demo environment
- [  ] Can fetch and store market data with DECIMAL precision
- [  ] Database stores versioned market updates (SCD Type 2 working)
- [  ] Config system loads YAML and applies DB overrides correctly
- [  ] Logging captures all API calls and errors
- [  ] CLI commands work and provide helpful output
- [  ] Test coverage >80%
- [  ] No float types used for prices (all DECIMAL)

---

## Phase 1.5: Foundation Validation (Codename: "Verify")

**Duration:** 2 weeks
**Target:** December 2025
**Status:** 🔵 Planned (awaits Phase 1 completion)
**Goal:** Validate versioning system and trailing stop infrastructure before Phase 2 complexity

### Dependencies
- Requires Phase 1: 100% complete

### Tasks

#### 1. Strategy Manager Implementation (Week 1)
- [  ] Create `trading/strategy_manager.py`
  - CRUD operations for strategies table
  - Version validation (enforce immutability)
  - Status lifecycle management (draft → testing → active → deprecated)
  - Active strategy lookup
- [  ] Unit tests for strategy versioning
  - Test immutability enforcement
  - Test version creation (v1.0 → v1.1)
  - Test status transitions
  - Test unique constraint validation

#### 2. Model Manager Implementation (Week 1)
- [  ] Create `analytics/model_manager.py`
  - CRUD operations for probability_models table
  - Version validation (enforce immutability)
  - Status lifecycle management (draft → training → validating → active → deprecated)
  - Active model lookup
- [  ] Unit tests for model versioning
  - Test immutability enforcement
  - Test version creation (v1.0 → v1.1)
  - Test validation metrics updates
  - Test unique constraint validation

#### 3. Position Manager Enhancements (Week 2)
- [  ] Update `trading/position_manager.py`
  - Trailing stop state initialization
  - Trailing stop update logic
  - Stop trigger detection
  - JSONB state validation
- [  ] Unit tests for trailing stops
  - Test state initialization
  - Test stop updates on price movement
  - Test trigger detection
  - Test JSONB schema validation

#### 4. Configuration System Enhancement (Week 2)
- [  ] Update `utils/config.py`
  - YAML file loading for all 7 config files
  - Version resolution (get active version for strategy/model)
  - Trailing stop config retrieval
  - Override handling
- [  ] Unit tests for configuration
  - Test YAML loading
  - Test version resolution
  - Test trailing stop config retrieval
  - Test override priority

### Deliverables
- [  ] strategy_manager.py with full CRUD and validation
- [  ] model_manager.py with full CRUD and validation
- [  ] Enhanced position_manager.py with trailing stops
- [  ] Enhanced config.py with version resolution
- [  ] Comprehensive unit tests (>80% coverage for new code)
- [  ] Integration tests for versioning system
- [  ] PHASE_1.5_PLAN.md (detailed acceptance criteria)

### Success Criteria
- [  ] Can create strategy versions and enforce immutability
- [  ] Can create model versions and enforce immutability
- [  ] Trailing stop state initializes correctly on position creation
- [  ] Trailing stops update correctly on price movement
- [  ] Configuration system loads all YAML files correctly
- [  ] Version resolution returns correct active versions
- [  ] All unit tests pass (>80% coverage)
- [  ] Integration tests validate versioning workflow end-to-end

**Why Phase 1.5?**
- Validates versioning system BEFORE Phase 2 complexity
- Tests manager classes before they're used in production
- Ensures trailing stops work before live trading
- Prevents cascading errors in later phases

---

## Phase 2: Live Data Integration (Codename: "Observer")

**Duration:** 4 weeks
**Target:** January 2026
**Status:** 🔵 Planned (awaits Phase 1.5 completion)
**Goal:** Implement live game data collection for NFL/NCAAF via ESPN API

### Dependencies
- Requires Phase 1.5: Versioning system validated

### Tasks

#### 1. ESPN API Integration (Weeks 1-2)
- **NFL scoreboard endpoint:** `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- **NCAAF scoreboard endpoint:** `https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`
- Parse game state data: scores, period, time remaining, game status
- Store in `game_states` table
- Handle API errors (retries, fallback to cached data)
- Rate limiting (ESPN allows ~500 req/hour)

#### 2. Task Scheduling (Week 2)
- APScheduler 3.10+ implementation (`schedulers/market_updater.py`)
- Cron-like job: Fetch ESPN data every 15 seconds during active games
- Conditional polling: Only poll if games are live (don't waste API calls)
- Job monitoring: Log job execution times, detect failures

#### 3. Data Quality & Validation (Week 3)
- Timestamp validation: Reject stale data (>60 seconds old)
- Data consistency checks: Scores monotonic, period transitions logical
- Missing data handling: Graceful degradation, use last known state
- Alert on anomalies: Email/log if data quality issues detected

#### 4. Historical Data Backfill (Week 4)
- Scrape nflfastR data (2019-2024 seasons for NFL)
- Populate `odds_matrices` table with historical game outcomes
- Map game situations (e.g., "14-7 halftime") to win probabilities
- Validate data quality: Check for completeness, outliers
- **This historical data will be leveraged in Phase 4 for odds calculation**

### Deliverables
- ESPN API client (`api_connectors/espn_client.py`)
- APScheduler task scheduler (`schedulers/market_updater.py`)
- Data quality validation module
- Historical data backfill script (nflfastR)
- Updated test suite
- LIVE_DATA_INTEGRATION_GUIDE_V1.0.md

### Success Criteria
- [  ] Can fetch live NFL game data every 15 seconds
- [  ] Game states stored correctly in database
- [  ] Data quality checks catch anomalies
- [  ] Historical data (2019-2024) loaded into `odds_matrices`
- [  ] No data loss during extended polling sessions
- [  ] APScheduler jobs run reliably

---

## Phase 3: Data Processing (Codename: "Pipeline")

**Duration:** 4 weeks  
**Target:** January-February 2026  
**Status:** 🔵 Planned  
**Goal:** Implement asynchronous data processing and WebSocket handlers (**NO odds calculation or edge detection in this phase**)

### Dependencies
- Requires Phase 2: Live data integration operational

### Tasks

#### 1. Async Processing Framework (Weeks 1-2)
- Implement asyncio-based processing pipeline
- Queue system for incoming data (aiohttp, asyncio.Queue)
- Concurrent processing of multiple games
- Backpressure handling: Throttle if queue fills up
- **Focus: Data ingestion and storage, NOT business logic**

#### 2. WebSocket Handlers (Week 2)
- Kalshi WebSocket integration for real-time market updates
- ESPN WebSocket (if available) for game updates
- Automatic reconnection on disconnect
- Message parsing and routing to appropriate handlers
- **Focus: Real-time data ingestion, NOT edge detection**

#### 3. Data Normalization (Week 3)
- Normalize game state data (scores, time, period)
- Normalize market data (prices, liquidity, metadata)
- Handle different data formats (REST vs. WebSocket)
- Ensure consistent DECIMAL precision across sources

#### 4. Processing Monitoring (Week 4)
- Processing latency tracking
- Queue depth monitoring
- Data throughput metrics
- Alert on processing delays (>5 seconds)
- Dashboard metrics (Phase 7 will visualize these)

### Deliverables
- Async processing framework (asyncio, aiohttp)
- WebSocket handlers (Kalshi, ESPN)
- Data normalization module
- Processing monitoring and metrics
- Updated test suite (async tests with pytest-asyncio)
- DATA_PROCESSING_ARCHITECTURE_V1.0.md

### Success Criteria
- [  ] Can process 50+ concurrent game updates without lag
- [  ] WebSocket connections stable for 24+ hours
- [  ] Data normalized consistently across sources
- [  ] Processing latency <2 seconds (95th percentile)
- [  ] No data loss during high-volume periods
- [  ] **NO edge detection or odds calculation implemented yet**

**Critical Note:** Phase 3 is pure data processing/ingestion. Odds models, edge detection, and trade signals are Phase 4+.

---

## Phase 4: Odds Calculation & Edge Detection (Codename: "Oracle")

**Duration:** 8 weeks  
**Target:** February-April 2026  
**Status:** 🔵 Planned  
**Goal:** Implement odds models, historical lookup, ensemble, and edge detection

### Dependencies
- Requires Phase 2: Historical data loaded (nflfastR)
- Requires Phase 3: Data processing pipeline operational

### Tasks

#### 1. Historical Lookup Model (Weeks 1-2)
- **Implement `models/historical_lookup.py`:**
  - Load historical odds matrices from `odds_matrices` table (populated in Phase 2)
  - Interpolation methods: linear, nearest-neighbor
  - Confidence scoring: Higher confidence for more data points
  - Era adjustment: Weight recent seasons more heavily (2022-2024 > 2019-2021)
- Map current game situations to historical outcomes
- Handle edge cases: No historical data for rare situations
- **Sample Task: "4.1 Historical Loader: Scrape 2019-2024 (nflfastR); populate odds_matrices (ref MODEL_VALIDATION for benchmarks)."**

#### 2. Elo Rating System (Week 2)
- Implement team Elo ratings (`models/elo.py`)
- Home advantage adjustments (post-2020 values: nfl:30, nba:40, mlb:20, nhl:30, soccer:25, tennis:20)
- K-factor tuning (nfl:28, nba:32, etc.)
- Elo-based win probability calculation

#### 3. Regression Model (Week 3)
- Logistic regression on team stats (`models/regression.py`)
- Feature engineering: Offensive/defensive ratings, recent form, injuries
- Coefficients tuned on historical data
- Probability output (0.0-1.0)

#### 4. Ensemble Model (Week 4)
- **Implement `models/ensemble.py`:**
  - Combine Elo (weight 0.40) + Regression (0.35) + ML (0.25) + Historical (0.30)
  - Weighted average with normalization
  - Confidence scoring based on model agreement
- Test ensemble vs. individual models (see MODEL_VALIDATION_V1.0.md for benchmarks)

#### 5. Edge Detection (Weeks 5-6)
- Calculate edge: `ensemble_probability - market_price`
- Threshold filtering: Only signal if edge > 0.0500 (5.00%)
- Confidence threshold: Only signal if ensemble confidence > 0.70
- Efficiency adjustment: Account for home advantage decline post-2020

#### 6. Backtesting & Validation (Weeks 7-8)
- Walk-forward validation on 2019-2024 data (see BACKTESTING_PROTOCOL_V1.0.md)
- Calculate hypothetical P&L
- Measure model accuracy (Brier score, log loss)
- Compare ensemble vs. individual models
- Validate edge detection thresholds

### Deliverables
- Historical lookup model (`models/historical_lookup.py`)
- Elo rating system (`models/elo.py`)
- Regression model (`models/regression.py`)
- Ensemble model (`models/ensemble.py`)
- Edge detection module
- Backtesting framework
- MODEL_VALIDATION_V1.0.md (Elo vs. research, benchmark comparisons)
- BACKTESTING_PROTOCOL_V1.0.md (walk-forward steps, train/test splits)
- Updated test suite

### Success Criteria
- [  ] Historical lookup model achieves >60% accuracy on unseen data
- [  ] Ensemble outperforms individual models by >5%
- [  ] Edge detection generates >10 profitable signals per week (backtest)
- [  ] Backtesting shows positive expectancy (Sharpe >1.0)
- [  ] Models handle rare situations gracefully (no crashes)
- [  ] **Ready to feed trade signals to Phase 5 trading engine**

---

## Phase 5: Position Monitoring & Exit Management (Codename: "Executor")

**Duration:** 4 weeks (split into 5a and 5b)
**Target:** April-May 2026
**Status:** 🔵 Planned
**Goal:** Implement comprehensive position monitoring, exit evaluation, and order execution with price walking

### Dependencies
- Requires Phase 1: Core infrastructure
- Requires Phase 4: Edge detection operational

### Sub-Phases

**Phase 5 Split:**
- **Phase 5a (Weeks 10-12):** Position monitoring, exit evaluation, priority hierarchy
- **Phase 5b (Weeks 13-14):** Order execution, price walking algorithm, exit attempt logging

---

## Phase 5a: Position Monitoring & Exit Evaluation (Codename: "Observer")

**Duration:** 3 weeks (Weeks 10-12)
**Target:** April 2026
**Status:** 🔵 Planned
**Goal:** Implement dynamic position monitoring, exit condition evaluation, and priority hierarchy

### Dependencies
- Requires Phase 1: Core infrastructure
- Requires Phase 4: Edge detection operational

### Tasks

#### 1. Dynamic Monitoring System (Week 1)
- Implement normal frequency monitoring (30 seconds)
- Implement urgent frequency monitoring (5 seconds)
- Urgent condition detection (within 2% of thresholds)
- Price caching (10-second TTL)
- API rate management (60 calls/min maximum)
- Monitor loop with async processing

#### 2. Position State Tracking (Week 1)
- Update `current_price` on every check
- Calculate `unrealized_pnl` and `unrealized_pnl_pct`
- Update `last_update` timestamp
- Maintain `trailing_stop_state` JSONB
- Track peak price and trailing stop price
- Health check monitoring

#### 3. Exit Condition Evaluation (Week 2)
- Implement 10 exit conditions:
  1. **stop_loss** (CRITICAL): Price hits stop loss threshold
  2. **circuit_breaker** (CRITICAL): System protection triggers
  3. **trailing_stop** (HIGH): Price hits trailing stop
  4. **time_based_urgent** (HIGH): <10 min to event, losing position
  5. **liquidity_dried_up** (HIGH): Spread >3¢ or volume <50
  6. **profit_target** (MEDIUM): Price hits profit target
  7. **partial_exit_target** (MEDIUM): 50% @ +15%, 25% @ +25%
  8. **early_exit** (LOW): Edge drops below 2%
  9. **edge_disappeared** (LOW): Edge turns negative
  10. **rebalance** (LOW): Portfolio rebalancing needed
- Per-condition trigger logic
- Confidence-adjusted thresholds

#### 4. Exit Priority Hierarchy (Week 2)
- Implement 4-level priority system:
  - CRITICAL: stop_loss, circuit_breaker
  - HIGH: trailing_stop, time_based_urgent, liquidity_dried_up
  - MEDIUM: profit_target, partial_exit_target
  - LOW: early_exit, edge_disappeared, rebalance
- Conflict resolution (highest priority wins)
- Log all triggered conditions

#### 5. Partial Exit Staging (Week 3)
- Stage 1: Exit 50% at +15% profit
- Stage 2: Exit 25% at +25% profit
- Remaining 25%: Rides with trailing stop
- Track partial exit history in `position_exits` table

#### 6. Testing & Validation (Week 3)
- Unit tests for each exit condition
- Unit tests for priority resolution
- Integration tests for monitoring loop
- Paper trading mode validation
- Performance metrics collection

### Deliverables (Phase 5a)
- Dynamic monitoring system (`trading/position_monitor.py`)
- Exit condition evaluators (10 conditions)
- Priority hierarchy resolver
- Partial exit staging logic
- Database updates (`position_exits` table usage)
- Test suite (>80% coverage)
- MONITORING_IMPLEMENTATION_GUIDE_V1.0.md

### Success Criteria (Phase 5a)
- [  ] Normal monitoring working (30s checks)
- [  ] Urgent monitoring activates correctly (5s when needed)
- [  ] All 10 exit conditions evaluate correctly
- [  ] Priority hierarchy resolves conflicts properly
- [  ] Partial exits execute at correct thresholds
- [  ] Paper trading shows exit logic working correctly
- [  ] API rate limits respected (<60 calls/min)

**Requirements Implemented:**
- REQ-MON-001: Dynamic monitoring frequencies ✓
- REQ-MON-002: Position state tracking ✓
- REQ-EXIT-001: Exit priority hierarchy ✓
- REQ-EXIT-002: 10 exit conditions ✓
- REQ-EXIT-003: Partial exit staging ✓

---

## Phase 5b: Exit Execution & Order Walking (Codename: "Walker")

**Duration:** 2 weeks (Weeks 13-14)
**Target:** May 2026
**Status:** 🔵 Planned
**Goal:** Implement urgency-based execution strategies, price walking algorithm, and exit attempt logging

### Dependencies
- Requires Phase 5a: Exit evaluation system operational

### Tasks

#### 1. Urgency-Based Execution Strategies (Week 1)
- **CRITICAL Priority:**
  - Market orders only
  - 5-second timeout
  - Immediate retry on failure
- **HIGH Priority:**
  - Aggressive limit orders (best_bid + $0.01)
  - 10-second timeout
  - Walk price 2x, then market order
- **MEDIUM Priority:**
  - Fair limit orders (best_bid)
  - 30-second timeout
  - Walk price up to 5x
- **LOW Priority:**
  - Conservative limit orders (best_bid - $0.01)
  - 60-second timeout
  - Walk price up to 10x

#### 2. Price Walking Algorithm (Week 1)
- Start with limit order at initial price
- Wait for timeout
- If not filled, walk price by $0.01 toward market
- Repeat up to max_walks
- HIGH priority: Escalate to market after max walks
- Track all attempts in `exit_attempts` table

#### 3. Exit Attempt Logging (Week 2)
- Create `exit_attempts` table records
- Log every order attempt:
  - Order type (limit/market)
  - Limit price (if applicable)
  - Fill price (if filled)
  - Attempt number
  - Timeout duration
  - Success/failure
- Enable "Why didn't my exit fill?" analysis

#### 4. Order Execution Integration (Week 2)
- Integrate with Kalshi API order placement
- Handle partial fills
- Update position quantity on fills
- Create `position_exits` record on completion
- Error handling and retries

#### 5. Testing & Validation (Week 2)
- Unit tests for each execution strategy
- Unit tests for price walking logic
- Integration tests with mock Kalshi API
- Paper trading validation (2 weeks)
- Performance metrics (fill rates, slippage)

#### 6. Reporting & Analytics (Week 2)
- Exit attempt analysis dashboard
- Fill rate by priority level
- Average slippage by strategy
- Price walking effectiveness metrics
- Performance by exit condition

### Deliverables (Phase 5b)
- Urgency-based execution engine (`trading/exit_executor.py`)
- Price walking algorithm
- Exit attempt logger
- Order execution integration
- Test suite (>80% coverage)
- EXIT_EXECUTION_GUIDE_V1.0.md
- PRICE_WALKING_ANALYSIS_V1.0.md

### Success Criteria (Phase 5b)
- [  ] CRITICAL exits fill within 10 seconds (market orders)
- [  ] HIGH exits fill within 30 seconds (95th percentile)
- [  ] MEDIUM exits achieve <2% slippage average
- [  ] LOW exits achieve <1% slippage average
- [  ] Price walking improves fill prices by 1-2% vs. market
- [  ] Exit attempt logging captures all details
- [  ] Paper trading shows proper exit execution

**Requirements Implemented:**
- REQ-EXEC-001: Urgency-based execution ✓
- REQ-EXEC-002: Price walking algorithm ✓
- REQ-EXEC-003: Exit attempt logging ✓

**MILESTONE: Ready for Small Live Trading ($50-100 positions)**

---

## Phase 6: Multi-Sport Expansion (Codename: "Constellation")

**Duration:** 6 weeks  
**Target:** May-June 2026  
**Status:** 🔵 Planned  
**Goal:** Add NBA, MLB, Tennis, and UFC support

### Dependencies
- Requires Phase 5: Trading engine operational and profitable on NFL/NCAAF

### Tasks

#### 1. NBA Integration (Weeks 1-2)
- Balldontlie API integration (`api_connectors/balldontlie_client.py`)
- Research NBA odds models (pace adjustments, back-to-back penalties)
- Create `nba_odds_matrices` table
- Test with 2024-2025 season data
- Validate profitability (backtest + paper trade 1 week)

#### 2. MLB Integration (Week 2-3)
- ESPN MLB API integration
- Starting pitcher analysis
- Create `mlb_odds_matrices` table
- Test on 2025 season data

#### 3. Tennis Integration (Week 3-4)
- ATP/WTA data sources (TBD - research Phase 6)
- Surface-specific odds (hard, clay, grass)
- Create `tennis_odds_matrices` table
- Test on active tournaments

#### 4. UFC Integration (Weeks 4-5 - Stretch)
- ESPN UFC API: `https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard`
- Fight-specific matrices (round_3_lead, etc.)
- Create `ufc_odds_matrices` table in `odds_matrices` with subcategory: ufc
- Minimal stubs, no deep implementation

#### 5. System Scaling (Week 6)
- Handle 100+ concurrent markets across all sports
- Multi-sport edge detection (run all models in parallel)
- Sport-specific trade strategies (different Kelly fractions: nfl:0.25, nba:0.22, tennis:0.18)
- Unified position tracking across sports

### Deliverables
- NBA trading operational
- MLB trading operational
- Tennis trading operational (if data source found)
- UFC placeholders/stubs (Phase 6+)
- Multi-sport test suite
- SPORT_EXPANSION_GUIDE_V1.0.md

### Success Criteria
- [  ] All new sports profitable in paper trading (2-week validation)
- [  ] System uptime >99% with multi-sport load
- [  ] Edge detection <5 seconds across all markets
- [  ] No cross-sport interference (NBA doesn't break NFL)

---

## Phase 7: Web Dashboard (Codename: "Augment")

**Duration:** 8 weeks  
**Target:** June-August 2026  
**Status:** 🔵 Planned  
**Goal:** Create web dashboard for monitoring and manual control

### Dependencies
- Requires Phase 5: Trading engine operational

### Tasks

#### 1. Backend API (Weeks 1-2)
- FastAPI 0.104+ backend (`/api/*` endpoints)
- Endpoints: `/positions`, `/trades`, `/pnl`, `/edges`, `/health`
- WebSocket for real-time updates
- Authentication (JWT tokens)

#### 2. Frontend Development (Weeks 3-6)
- React + Next.js frontend
- Real-time position monitoring (WebSocket updates)
- P&L charts and visualizations (Recharts or Plotly)
- System health indicators (API status, data freshness)
- Manual trade execution interface (override automation)
- Historical performance dashboard

#### 3. Deployment (Week 7)
- Vercel for frontend (free tier)
- AWS EC2 for backend (or Railway.app)
- SSL certificates (Let's Encrypt)
- Domain setup

#### 4. Advanced Analytics (Week 8)
- Integrate DVOA, EPA, SP+ ratings (NFL)
- Net Rating, pace adjustments (NBA)
- A/B test baseline vs. enhanced odds
- Feature importance visualization

### Deliverables
- Working web dashboard
- FastAPI backend
- React frontend
- Deployment scripts
- GUI_DESIGN_V1.0.md
- ADVANCED_METRICS_GUIDE_V1.0.md

### Success Criteria
- [  ] Can view all positions in real-time
- [  ] Can execute trades via GUI
- [  ] Dashboard loads in <2 seconds
- [  ] Advanced metrics improve edge detection accuracy by 5%+

---

## Phase 8: Non-Sports Markets (Codename: "Multiverse")

**Duration:** 12 weeks  
**Target:** August-November 2026  
**Status:** 🔵 Planned  
**Goal:** Expand to politics, entertainment, and other non-sports categories

### Dependencies
- Requires Phase 5: Trading engine operational

### Tasks

#### 1. Political Markets (Weeks 1-6)
- RealClearPolling API integration
- FiveThirtyEight data integration
- Election outcome probabilities
- Polling-based odds models
- Validate on 2026 midterms

#### 2. Entertainment Markets (Weeks 7-10)
- Box office predictions (BoxOfficeMojo API)
- Award show outcomes (Oscars, Grammys)
- Cultural event markets
- Custom odds matrices for entertainment

#### 3. NLP Sentiment Analysis (Weeks 9-12)
- Spacy 3.7+ sentiment analysis (`utils/text_parser.py`)
- Twitter/news sentiment for political markets
- Integrate sentiment into odds models (Phase 8-9 blend)

#### 4. Generalized Infrastructure (Week 11-12)
- Category-agnostic edge detection
- Custom strategy per category
- Unified reporting across all categories

### Deliverables
- Political market trading
- Entertainment market trading
- NLP sentiment integration
- Generalized odds framework
- NON_SPORTS_MARKETS_GUIDE_V1.0.md

### Success Criteria
- [  ] Profitable trading in at least 2 non-sports categories
- [  ] Sentiment analysis improves political market accuracy by 10%+
- [  ] System handles diverse market types without errors

---

## Phase 9: Machine Learning Enhancement (Codename: "Singularity")

**Duration:** 16 weeks  
**Target:** November 2026 - March 2027  
**Status:** 🔵 Planned  
**Goal:** Integrate advanced ML models for enhanced predictions

### Dependencies
- Requires Phase 4: Baseline odds models operational
- Requires Phase 8: Large dataset for training

### Tasks

#### 1. Feature Engineering (Weeks 1-4)
- Historical game data features (team stats, player stats, situational factors)
- Market sentiment indicators
- Time-series features (momentum, streaks)
- Feature selection and importance analysis

#### 2. Model Development (Weeks 5-10)
- XGBoost 2.0+ gradient boosting (`analytics/ml/train.py`)
- TensorFlow 2.15+ or PyTorch 2.1+ LSTM for time-series
- Ensemble methods (stacking, blending)
- Hyperparameter tuning (grid search, Bayesian optimization)
- Cross-validation on historical data

#### 3. Model Integration (Weeks 11-14)
- Blend ML predictions with statistical odds (Phase 4 ensemble)
- A/B testing framework (baseline vs. ML-enhanced)
- Continuous learning pipeline (retrain monthly)
- Feature drift detection

#### 4. Performance Tracking (Weeks 15-16)
- Model drift detection (alert if accuracy drops >5%)
- Automatic retraining triggers (monthly or on drift)
- Feature importance visualization
- Backtesting on new data

### Deliverables
- XGBoost/LSTM models for NFL, NBA
- Model blending framework
- Continuous learning pipeline
- A/B testing results
- ML_MODELS_GUIDE_V1.0.md
- FEATURE_ENGINEERING_SPEC_V1.0.md

### Success Criteria
- [  ] ML models outperform baseline by 5%+
- [  ] Models retrain automatically monthly
- [  ] Drift detection catches degradation before losses
- [  ] A/B test shows statistical significance (p<0.05)

---

## Phase 10: Multi-Platform & Advanced Features (Codename: "Nexus Prime")

**Duration:** 12 weeks  
**Target:** March-June 2027  
**Status:** 🔵 Planned  
**Goal:** Add Polymarket integration and cross-platform arbitrage

### Dependencies
- Requires all previous phases operational

### Tasks

#### 1. Polymarket Integration (Weeks 1-4)
- Metamask/Web3 authentication
- CLOB API integration
- Adapt data ingestion for different market structure
- Test on Polymarket sandbox

#### 2. Cross-Platform Features (Weeks 5-8)
- Arbitrage detection (Kalshi vs. Polymarket price discrepancies)
- Unified position tracking across platforms
- Optimal platform selection (liquidity, fees, edge)

#### 3. Advanced Risk Management (Weeks 9-10)
- Portfolio optimization (maximize Sharpe ratio)
- Correlation analysis (avoid concentrated risk)
- Dynamic position sizing based on volatility

#### 4. Production Hardening (Weeks 11-12)
- High availability (failover, redundancy)
- Performance optimization (database tuning, caching)
- Security audit (penetration testing, code review)
- Compliance documentation (CFTC regulations)

### Deliverables
- Polymarket integration
- Arbitrage detection system
- Cross-platform position tracking
- Portfolio optimization module
- Production-grade infrastructure
- POLYMARKET_INTEGRATION_GUIDE_V1.0.md
- CROSS_PLATFORM_ARBITRAGE_V1.0.md

### Success Criteria
- [  ] Can trade on both Kalshi and Polymarket seamlessly
- [  ] Arbitrage opportunities detected and exploited (>$100/week)
- [  ] System handles multi-platform load without errors
- [  ] Production ready for continuous operation (99.9% uptime)

---

## Summary of New Deliverables

**Phase 0:**
- ✅ GLOSSARY_V1.0.md (terms like EV, Kelly, edge, Elo, etc.)
- ✅ DEVELOPER_ONBOARDING_V1.0.md (merged with ENVIRONMENT_CHECKLIST, onboarding steps: "Follow Checklist Parts 1-6, then code stubs")

**Phase 1:**
- DEPLOYMENT_GUIDE_V1.0.md (local setup instructions + AWS deployment stubs for Phase 7+)

**Phase 4:**
- MODEL_VALIDATION_V1.0.md (Elo vs. research benchmarks, ensemble comparisons)
- BACKTESTING_PROTOCOL_V1.0.md (walk-forward validation steps, train/test splits)

**Phase 5:**
- USER_GUIDE_V1.0.md (CLI command examples: `edges-list`, `trade-execute --paper`, `positions-view`)

---

## Phase Dependencies Summary

See PROJECT_OVERVIEW_V1.2.md for complete Phase Dependencies Table. Key dependencies:

- Phase 1 → Phase 0 (foundation complete)
- Phase 2 → Phase 1 (API client operational)
- Phase 3 → Phase 2 (live data available)
- Phase 4 → Phases 2-3 (live data + processing + historical data from Phase 2)
- Phase 5 → Phases 1, 4 (infrastructure + edge detection)
- Phase 6+ → Phase 5 (trading engine profitable)

**Critical:** Phase 4 depends on Phase 2 historical data (nflfastR backfill) for historical_lookup model.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-10-12 | Clarified Phase 2 (ESP), 3 (processing only), 4 (odds/edges/historical); added new deliverables; Phase 0 marked 100% |
| 1.0 | Earlier | Initial roadmap with all 10 phases |

---

**Maintained By:** Project lead  
**Review Frequency:** Update after each phase completion  
**Next Review:** Phase 1 kickoff (after Phase 0 complete)

---

**END OF DEVELOPMENT_PHASES**
