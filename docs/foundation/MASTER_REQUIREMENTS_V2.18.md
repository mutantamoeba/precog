# Master Requirements Document

---
**Version:** 2.18
**Last Updated:** 2025-11-22
**Status:** ✅ Current - Authoritative Requirements
**Changes in v2.18:**
- **WORKFLOW ENFORCEMENT REQUIREMENTS**: Added REQ-VALIDATION-007 through REQ-VALIDATION-012 (6 comprehensive workflow enforcement requirements)
- **PATTERN ENFORCEMENT**: Requirements enforce Pattern 2 (SCD Type 2 queries), Pattern 8 (Config Sync), Pattern 10 (Property-Based Testing), Pattern 13 (Test Coverage Quality)
- **PHASE START/COMPLETION AUTOMATION**: REQ-VALIDATION-010 (Phase Start Protocol), REQ-VALIDATION-011 (Phase Completion Protocol) automate 3-step and 10-step assessment workflows
- **VALIDATOR ARCHITECTURE**: All validators use YAML-driven configuration (validation_config.yaml), auto-discovery pattern (database introspection, filesystem glob), graceful degradation
- **GIT HOOK INTEGRATION**: Pre-push hook Steps 8-10 (SCD queries ~15s, Property tests ~20s, Test fixtures ~10s) run in parallel with existing steps
- **CROSS-REFERENCES**: Added ADR-094 (YAML-Driven Validation), ADR-095 (Auto-Discovery Pattern), ADR-096 (Parallel Execution), ADR-097 (Tier-Specific Coverage)
- **ZERO MAINTENANCE**: New SCD Type 2 tables, property test modules, and phase deliverables auto-discovered (no code changes required)
**Changes in v2.17:**
- **LOOKUP TABLES FOR BUSINESS ENUMS**: Added REQ-DB-015 (Strategy Type Lookup Table) and REQ-DB-016 (Model Class Lookup Table)
- **NO-MIGRATION ENUM EXTENSIBILITY**: Requirements document replacement of CHECK constraints with lookup tables for strategy_type and model_class
- **MIGRATION 023 REQUIREMENTS**: Formal requirements for lookup tables infrastructure implemented in Migration 023 (Phase 1.5)
- **BENEFITS DOCUMENTED**: Add new enum values via INSERT (no migration), rich metadata (display_name, description, category), UI-friendly dropdown queries
- **HELPER MODULE**: REQ-DB-015 and REQ-DB-016 reference src/precog/database/lookup_helpers.py for validation functions
- **COMPREHENSIVE TESTING**: 23 tests with 100% coverage of lookup_helpers.py, FK constraint enforcement tests
- **CROSS-REFERENCES**: Both requirements link to ADR-093 (Lookup Tables for Business Enums), Migration 023, DATABASE_SCHEMA_SUMMARY_V1.11
- **TABLE COUNT UPDATE**: Updated total tables from 25 to 29 (added strategy_types and model_classes lookup tables)
**Changes in v2.16:**
- **TEST COVERAGE STANDARDS**: Added REQ-TEST-012 through REQ-TEST-019 (8 comprehensive test coverage requirements)
- **TDD FAILURE RESPONSE**: Requirements address Phase 1.5 TDD failure root cause analysis (Strategy Manager: 17/17 tests passing with mocks → 13/17 failing with real database = 77% failure rate)
- **8 TEST TYPE FRAMEWORK**: REQ-TEST-012 establishes comprehensive test type coverage (Unit, Property, Integration, E2E, Stress, Race Condition, Performance, Chaos)
- **MOCK USAGE RESTRICTIONS**: REQ-TEST-013 prohibits mocking internal infrastructure (database, config, logging) - MUST use real test fixtures
- **MANDATORY TEST FIXTURES**: REQ-TEST-014 requires ALWAYS using conftest.py fixtures (clean_test_data, db_pool, db_cursor) instead of creating mocks
- **COVERAGE PERCENTAGE STANDARDS**: REQ-TEST-015 establishes tiered coverage targets (Critical Path ≥90%, Manager ≥85%, Infrastructure ≥80%)
- **STRESS TESTING**: REQ-TEST-016 requires testing infrastructure limits (connection pool exhaustion, API rate limits, concurrent operations)
- **INTEGRATION TESTING**: REQ-TEST-017 mandates integration tests with real dependencies for manager layer
- **PROPERTY-BASED TESTING**: REQ-TEST-018 requires Hypothesis framework for mathematical invariants (100+ auto-generated test cases)
- **END-TO-END TESTING**: REQ-TEST-019 requires complete workflow tests for user-facing features
- **CROSS-REFERENCES**: All requirements link to ADR-074 (Property-Based Testing), ADR-076 (Test Type Categories), Pattern 13 (Test Coverage Quality)
- **PREVENTION STRATEGY**: These requirements prevent future false confidence from mock-based tests (core development philosophy enhancement)
**Changes in v2.15:**
- **RETROACTIVE REQ CREATION**: Added REQ-CICD-004 (Pre-Commit Hooks) and REQ-CICD-005 (Pre-Push Hooks) for traceability
- **REQUIREMENTS TRACEABILITY GAP FIX**: Critical infrastructure (pre-commit/pre-push hooks) was implemented without formal requirements (DEF-001, DEF-002 completed 2025-11-07)
- **CONSISTENCY ENFORCEMENT**: Updated REQ-CICD-003 (Branch Protection) status from Planned → Complete to match DEF-003 completion
- **CROSS-REFERENCES**: REQ-CICD-004 links to DEF-001 and CLAUDE.md Section 3, REQ-CICD-005 links to DEF-002 and CLAUDE.md Section 3
- **IMPLEMENTATION DETAILS**: Both REQs include comprehensive implementation details (14 pre-commit checks, 7 pre-push validation steps)
- **PHASE COMPLETION PROTOCOL ENHANCEMENT**: This change addresses gap identified in Phase 1 completion assessment - critical infrastructure MUST have formal requirements for audit traceability
**Changes in v2.14:**
- **PRODUCTION MONITORING**: Added REQ-OBSERV-002 for Sentry error tracking and performance monitoring (Phase 2)
- **OBSERVABILITY STACK**: Documented Codecov (pre-release coverage) + Sentry (post-release monitoring) complementary integration
- **SECTION 7.5 EXTENDED**: Added Production Error Tracking requirement after Request Correlation IDs
- **CROSS-REFERENCES**: Added ADR-TBD (Sentry architectural decision), SENTRY_INTEGRATION_GUIDE_V1.0.md (future)
- **INTEGRATION**: Sentry uses existing B3 correlation IDs (REQ-OBSERV-001) and log masking (REQ-SEC-009)
- **FREE TIER**: 5K errors/month, 10K transactions/month sufficient for Phase 0-2 development
**Changes in v2.13:**
- **ANALYTICS & PERFORMANCE TRACKING**: Added 7 new requirements for comprehensive performance tracking and model validation (Phase 1.5-2, 6-7, 9)
- **NEW SECTION 4.11**: Analytics & Performance Tracking (REQ-ANALYTICS-001 through REQ-ANALYTICS-004, REQ-REPORTING-001)
  - REQ-ANALYTICS-001: Performance Metrics Collection (16 metric types: ROI, win_rate, Sharpe ratio, Brier score, ECE, etc.)
  - REQ-ANALYTICS-002: Time-Series Performance Storage (8 aggregation levels: trade → hourly → daily → monthly → yearly → all_time)
  - REQ-ANALYTICS-003: Metrics Aggregation Pipeline (real-time + batch collection with materialized views)
  - REQ-ANALYTICS-004: Historical Performance Retention (hot/warm/cold storage with automated archival)
  - REQ-REPORTING-001: Performance Dashboard (React + Next.js UI with FastAPI backend, 4 dashboard pages)
- **SECTION 4.9 EXTENDED**: Added model validation requirements (REQ-MODEL-EVAL-001, REQ-MODEL-EVAL-002)
  - REQ-MODEL-EVAL-001: Model Validation Framework (backtesting, cross-validation, holdout validation with activation criteria)
  - REQ-MODEL-EVAL-002: Calibration Testing (Brier score ≤0.20, ECE ≤0.10, log loss ≤0.50, reliability diagrams)
- **CROSS-REFERENCES**: Added references to DATABASE_SCHEMA_SUMMARY_V1.11.md (7 new tables + 2 materialized views), ADR-078, ADR-080, ADR-081, ADR-082, DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md, MODEL_EVALUATION_GUIDE_V1.0.md
- **DATABASE INTEGRATION**: References new performance_metrics, evaluation_runs, model_predictions, performance_metrics_archive tables and strategy_performance_summary, model_calibration_summary materialized views
- **USER REQUIREMENTS**: Addresses user's concerns (1) detailed historical performance tracking with database tables, (2) JSONB config storage decision (ADR-078)
**Changes in v2.12:**
- **TEMPLATE ENFORCEMENT**: Added 2 new automated enforcement requirements (REQ-VALIDATION-005, REQ-VALIDATION-006)
- **NEW REQUIREMENTS**:
  - REQ-VALIDATION-005: CODE_REVIEW_TEMPLATE enforcement via validate_code_quality.py
  - REQ-VALIDATION-006: SECURITY_REVIEW_CHECKLIST enforcement via validate_security_patterns.py
- **CROSS-REFERENCES**: Added references to CODE_REVIEW_TEMPLATE_V1.0.md, SECURITY_REVIEW_CHECKLIST.md V1.1, INFRASTRUCTURE_REVIEW_TEMPLATE_V1.0.md
- **INTEGRATION**: Pre-commit hooks (2 lightweight checks), pre-push hooks (2 comprehensive checks)
- **VALIDATION LAYERS**: Enforces requirements traceability (REQ-XXX-NNN), test coverage (≥80%), security patterns (API auth, hardcoded secrets)
**Changes in v2.11:**
- **PYTHON 3.14 COMPATIBILITY**: Updated REQ-TEST-006 and REQ-CICD-001 to replace Bandit with Ruff security rules (--select S)
- **SECURITY SCANNING**: Bandit 1.8.6 incompatible with Python 3.14 (ast.Num removed), replaced with Ruff S-rules (equivalent coverage, 10-100x faster)
- **CROSS-REFERENCE**: Added ADR-054 (Ruff Security Rules Instead of Bandit) for rationale and implementation details
- REQ-TEST-006: Changed "Bandit: Static analysis" → "Ruff security rules (--select S): Static analysis"
- REQ-CICD-001: Changed "Security scanning (Bandit, Safety)" → "Security scanning (Ruff security rules, Safety)"
**Changes in v2.10:**
- **PHASE 1 API BEST PRACTICES**: Added 4 new requirements for API integration best practices (Phase 1)
- **NEW REQUIREMENTS**: REQ-API-007 (Pydantic validation), REQ-OBSERV-001 (correlation IDs), REQ-SEC-009 (log masking), REQ-VALIDATION-004 (YAML validation)
- **CROSS-REFERENCES**: Added ADR-047 (Pydantic), ADR-049 (B3 correlation IDs), ADR-051 (sensitive data masking), ADR-052 (YAML validation)
- **SECTION 7.5 EXTENDED**: Added API Response Validation, Observability (Request Tracing), Security (Log Masking), and YAML Configuration Validation
- **COMPLIANCE**: Added GDPR/PCI-DSS requirements for sensitive data handling
**Changes in v2.9:**
- **PHASE 0.6C COMPLETION**: Added 11 new requirements for validation, testing, and CI/CD infrastructure
- **NEW REQUIREMENTS**: REQ-TEST-005 through REQ-TEST-008 (Test result persistence, security testing, mutation testing, property-based testing)
- **NEW SECTION 7.5**: Code Quality, Validation & CI/CD requirements (REQ-VALIDATION-001 through REQ-VALIDATION-003, REQ-CICD-001 through REQ-CICD-003)
- **PHASE 0.6C STATUS**: REQ-TEST-005, REQ-VALIDATION-001-003 marked as ✅ Complete
- **PHASE 0.7 PLANNING**: REQ-TEST-006-008, REQ-CICD-001-003 marked as 🔵 Planned
- **CROSS-REFERENCES**: Added ADR-038 through ADR-045 references
- **DOCUMENTATION REFERENCES**: Added TESTING_STRATEGY_V3.1.md, VALIDATION_LINTING_ARCHITECTURE_V1.0.md
**Changes in v2.8:**
- **PHASE 0.6B DOCUMENTATION**: Updated all supplementary document references with standardized filenames (removed PHASE_ prefixes, standardized V1.0 format)
- **NEW SECTION 4.10**: CLI Commands requirements (REQ-CLI-001 through REQ-CLI-005) - Typer framework with 5 core commands
- **PHASE 1 EXPANSION**: Expanded Phase 1 from 2 weeks to 6 weeks with detailed weekly breakdown
- **IMPLEMENTATION STATUS**: Added status tracking (✅ Complete, 🟡 Partial, ❌ Not Started) to Phase 1 deliverables
- **DOCUMENTATION REORGANIZATION**: Section 2.4 now organized by document type (Foundation, Supplementary, Supplementary Specifications, Planned)
- Updated all supplementary doc references: VERSIONING_GUIDE_V1.0.md, TRAILING_STOP_GUIDE_V1.0.md, POSITION_MANAGEMENT_GUIDE_V1.0.md, ADVANCED_EXECUTION_SPEC_V1.0.md, EVENT_LOOP_ARCHITECTURE_V1.0.md, EXIT_EVALUATION_SPEC_V1.0.md, POSITION_MONITORING_SPEC_V1.0.md, ORDER_EXECUTION_ARCHITECTURE_V1.0.md, SPORTS_PROBABILITIES_RESEARCH_V1.0.md, USER_CUSTOMIZATION_STRATEGY_V1.0.md
- Added cross-references to ADRs in supplementary spec descriptions (ADR-035, ADR-036, ADR-037)
- Phase 1 now shows 50% complete (Database ✅, API/CLI ❌)
**Changes in v2.7:**
- **COMPLETENESS**: Added 7 missing operational tables to section 4.2 (platforms, settlements, account_balance, config_overrides, circuit_breaker_events, system_health, alerts)
- **NEW SECTION 4.7**: Trading Methods requirements (REQ-METH-001 through REQ-METH-015) - Phase 4-5 implementation
- **NEW SECTION 4.8**: Alerts & Monitoring requirements (REQ-ALERT-001 through REQ-ALERT-015) - Phase 1 implementation
- **NEW SECTION 4.9**: Machine Learning Infrastructure (Phased approach: REQ-ML-001 through REQ-ML-004)
- Added ML table placeholders: feature_definitions, features_historical, training_datasets, model_training_runs (Phase 9)
- Clarified Elo timeline: Phase 4 (initial implementation), Phase 6 (sport expansion), Phase 9 (advanced enhancements)
- Added references to future documentation: MACHINE_LEARNING_ROADMAP.md, PROBABILITY_PRIMER.md, ELO_IMPLEMENTATION_GUIDE.md, MODEL_EVALUATION_GUIDE.md
- Updated table count: 21 operational tables + 4 ML placeholders = 25 total tables
**Changes in v2.6:**
- **STANDARDIZATION**: Added systematic REQ IDs to all requirements (REQ-{CATEGORY}-{NUMBER})
- Added formal requirement identifiers for traceability and cross-referencing
- Maintained all existing content from V2.5
- See REQUIREMENT_INDEX.md for complete requirement catalog
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
**Replaces:** Master Requirements v2.5
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
- **REQ-PERF-001: System Uptime**: 99%+ during market hours
- **REQ-PERF-002: Data Latency**: <5 seconds from API to database
- **REQ-SYS-003: Decimal Precision**: 100% accuracy in price handling (no float rounding errors)
- **REQ-PERF-003: Edge Detection Accuracy**: Validated through backtesting (target: 55%+ win rate)
- **REQ-PERF-004: Execution Success**: >95% of intended trades executed
- **ROI**: Positive returns after transaction costs over 6-month period
- **REQ-VER-003: Strategy Version Tracking**: 100% of trades attributed to exact strategy and model versions

---

## 2. System Architecture

### 2.1 Technology Stack
- **Language**: Python 3.12
- **Database**: PostgreSQL (local dev → AWS RDS production)
- **ORM**: SQLAlchemy + psycopg2
- **API**: requests (sync), aiohttp (async)
- **Data Processing**: pandas, numpy
- **Decimal Precision**: Python Decimal library (NEVER float for prices)
- **Text Parsing**: Transformers (Hugging Face) with PyTorch backend
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
- **Foundation Documents** (in `docs/foundation/`):
  1. `PROJECT_OVERVIEW_V1.5.md` - System architecture and tech stack
  2. `MASTER_REQUIREMENTS_V2.18.md` - This document (requirements through Phase 10)
  3. `MASTER_INDEX_V2.29.md` - Complete document inventory
  4. `ARCHITECTURE_DECISIONS_V2.21.md` - All 97 ADRs with design rationale (Phase 0-4.5)
  5. `REQUIREMENT_INDEX.md` - Systematic requirement catalog
  6. `ADR_INDEX_V1.15.md` - Architecture decision index
  7. `TESTING_STRATEGY_V3.1.md` - Test cases, coverage requirements, future enhancements
  8. `VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Code quality and documentation validation architecture

- **Supplementary Documents** (in `docs/supplementary/`):
  9. `VERSIONING_GUIDE_V1.0.md` - Strategy and model versioning patterns (Phase 0.5)
  10. `TRAILING_STOP_GUIDE_V1.0.md` - Trailing stop loss implementation (Phase 0.5)
  11. `POSITION_MANAGEMENT_GUIDE_V1.0.md` - Position lifecycle management (Phase 0.5)
  12. `ODDS_RESEARCH_COMPREHENSIVE.md` - Historical odds research and validation
  13. `SPORTS_PROBABILITIES_RESEARCH_V1.0.md` - NFL/NBA/Tennis win probability benchmarks

- **Supplementary Specifications** (in `docs/supplementary/`):
  14. `ADVANCED_EXECUTION_SPEC_V1.0.md` - Phase 5b execution strategies (dynamic price walking)
  15. `EVENT_LOOP_ARCHITECTURE_V1.0.md` - Phase 5 event loop design (see ADR-035)
  16. `EXIT_EVALUATION_SPEC_V1.0.md` - Phase 5a exit condition evaluation (see ADR-036)
  17. `POSITION_MONITORING_SPEC_V1.0.md` - Phase 5a position monitoring strategies
  18. `ORDER_EXECUTION_ARCHITECTURE_V1.0.md` - Order execution assessment and architecture
  19. `USER_CUSTOMIZATION_STRATEGY_V1.0.md` - User-facing customization options (Phase 10+)

- **Planned Documentation** (Phase 4-9):
  20. `MACHINE_LEARNING_ROADMAP.md` - ML learning path and phased implementation (Phase 9)
  21. `PROBABILITY_PRIMER.md` - Expected value, Kelly Criterion, probability concepts (Phase 4)
  22. `ELO_IMPLEMENTATION_GUIDE.md` - Elo rating system implementation details (Phase 4)
  23. `MODEL_EVALUATION_GUIDE.md` - Model validation, metrics, A/B testing (Phase 9)
  24. `API_INTEGRATION_GUIDE.md` - Detailed API specs with code examples (Phase 1)
  25. `DEPLOYMENT_GUIDE.md` - Setup instructions, cloud migration (Phase 3)
  26. `KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md` - ⚠️ **PRINT AND KEEP AT DESK** (Phase 1)

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

**REQ-SYS-003: Decimal Precision for Prices**

**Phase:** 0
**Priority:** Critical
**Status:** ✅ Complete

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

### 3.5 Versioning Philosophy

**REQ-VER-001: Immutable Version Configs**

**Phase:** 0.5, 4
**Priority:** Critical
**Status:** ✅ Complete

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

**See VERSIONING_GUIDE_V1.0.md for implementation details**

---

## 4. Database Overview

### 4.1 Design Principles

**REQ-DB-001: PostgreSQL 15+ Database**

**Phase:** 0
**Priority:** Critical
**Status:** ✅ Complete

**REQ-DB-002: SCD Type 2 Versioning Pattern**

**Phase:** 0
**Priority:** Critical
**Status:** ✅ Complete

**REQ-DB-003: DECIMAL(10,4) for Prices/Probabilities**

**Phase:** 0
**Priority:** Critical
**Status:** ✅ Complete

**Additional Principles:**
- **Two Versioning Patterns**: row_current_ind for mutable data, version fields for immutable configs
- **Timestamps**: `created_at` (immutable), `updated_at` (modified on change)
- **Relationships**: Foreign keys link markets → events → series
- **Indexing**: Optimized for time-series queries and joins
- **JSONB**: Flexible storage for metadata, API responses, and trailing stop state
- **Decimal Precision**: ALL price columns use DECIMAL(10,4) - **NO EXCEPTIONS**
- **Trade Attribution**: Every trade links to exact strategy version and model version

### 4.2 Core Tables (Simplified - Schema V1.6)

**REQ-DB-004: position_exits Table**

**Phase:** 0.5
**Priority:** Critical
**Status:** ✅ Complete

**REQ-DB-005: exit_attempts Table**

**Phase:** 0.5
**Priority:** Critical
**Status:** ✅ Complete

**REQ-DB-006: Foreign Key Constraints**

**Phase:** 0
**Priority:** High
**Status:** ✅ Complete

**REQ-DB-007: CHECK Constraints for Enums**

**Phase:** 0
**Priority:** High
**Status:** ✅ Complete

**REQ-DB-015: Strategy Type Lookup Table**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete

Replace CHECK constraint for `strategies.approach` with lookup table for extensibility.

**Requirements:**
- Create `strategy_types` lookup table with metadata (display_name, description, category, display_order, is_active)
- Store 4 initial values: 'value', 'arbitrage', 'momentum', 'mean_reversion'
- Add foreign key constraint: `strategies.strategy_type` → `strategy_types.strategy_type_code`
- Drop CHECK constraint: `strategies_strategy_type_check`
- Provide helper functions for validation and querying (see `lookup_helpers.py`)
- Support no-migration extensibility: Add new strategy types via INSERT (no schema migration)

**Categories:**
- `directional`: Value, momentum, mean reversion, contrarian
- `arbitrage`: Cross-platform arbitrage opportunities
- `risk_management`: Hedging, stop-loss strategies
- `event_driven`: News/catalyst-based strategies

**Benefits:**
- ✅ Add new strategy types via INSERT (no migration required)
- ✅ Store rich metadata (display_name, description, category, help_text)
- ✅ UI-friendly queries for dropdown options
- ✅ Flexible deactivation (is_active = FALSE preserves historical references)
- ✅ Extensible schema (add fields like tags, risk_level without affecting code)

**Implementation:**
- Migration: `migration_023_create_lookup_tables.py`
- Helper module: `src/precog/database/lookup_helpers.py`
- Tests: `tests/test_lookup_tables.py` (23 tests, 100% coverage)

**Cross-references:**
- ADR-093: Lookup Tables for Business Enums
- Migration 023: Create Lookup Tables
- DATABASE_SCHEMA_SUMMARY_V1.11.md: Lookup Tables section
- LOOKUP_TABLES_DESIGN.md: Complete design specification

**REQ-DB-016: Model Class Lookup Table**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete

Replace CHECK constraint for `probability_models.approach` with lookup table for extensibility.

**Requirements:**
- Create `model_classes` lookup table with metadata (display_name, description, category, complexity_level, display_order, is_active)
- Store 7 initial values: 'elo', 'ensemble', 'ml', 'hybrid', 'regression', 'neural_net', 'baseline'
- Add foreign key constraint: `probability_models.model_class` → `model_classes.model_class_code`
- Drop CHECK constraint: `probability_models_model_class_check`
- Provide helper functions for validation and querying (see `lookup_helpers.py`)
- Support no-migration extensibility: Add new model classes via INSERT (no schema migration)

**Categories:**
- `statistical`: Elo, regression, Poisson
- `machine_learning`: ML, neural networks, random forests, XGBoost
- `hybrid`: Ensemble, hybrid approaches
- `baseline`: Simple benchmarks, market consensus

**Complexity Levels:**
- `simple`: Easy to understand/implement (Elo, baseline)
- `moderate`: Requires some expertise (regression, ensemble)
- `advanced`: Complex algorithms (neural networks, XGBoost)

**Benefits:**
- ✅ Add new model classes via INSERT (no migration required)
- ✅ Store rich metadata (display_name, description, category, complexity_level)
- ✅ UI-friendly queries for dropdown options with complexity filtering
- ✅ Progressive disclosure (show simple models first, advanced models later)
- ✅ Extensible schema (add fields like training_complexity, compute_cost)

**Implementation:**
- Migration: `migration_023_create_lookup_tables.py`
- Helper module: `src/precog/database/lookup_helpers.py`
- Tests: `tests/test_lookup_tables.py` (23 tests, 100% coverage)

**Cross-references:**
- ADR-093: Lookup Tables for Business Enums
- Migration 023: Create Lookup Tables
- DATABASE_SCHEMA_SUMMARY_V1.11.md: Lookup Tables section
- LOOKUP_TABLES_DESIGN.md: Complete design specification

#### Operational Tables (29 tables)

| Table | Purpose | Key Columns | Price Columns | Versioning |
|-------|---------|-------------|---------------|------------|
| `platforms` | Platform definitions | platform_id, platform_type, base_url | N/A | None |
| `series` | Kalshi series | ticker, category, tags | N/A | None |
| `events` | Game instances | series_id, start_date, final_state | N/A | None |
| `markets` | Binary outcomes | event_id, status, volume | yes_bid, yes_ask, no_bid, no_ask (ALL DECIMAL(10,4)) | row_current_ind |
| `game_states` | Live stats | event_id, home_score, away_score, time_remaining | N/A | row_current_ind |
| `probability_matrices` | Historical win probabilities | category, subcategory, state_descriptor, value_bucket | win_probability (DECIMAL(10,4)) | None |
| `probability_models` | ML model versions | model_name, model_version, config, status | validation_accuracy (DECIMAL(10,4)) | Immutable Versions |
| `strategies` | Trading strategy versions | strategy_name, strategy_version, config, status | paper_roi, live_roi (DECIMAL(10,4)) | Immutable Versions |
| `strategy_types` | Lookup table for strategy types | strategy_type_code, display_name, description, category | N/A | None (REQ-DB-015) |
| `model_classes` | Lookup table for model classes | model_class_code, display_name, description, category, complexity_level | N/A | None (REQ-DB-016) |
| `edges` | EV+ opportunities | market_id, strategy_id, model_id, side | expected_value, true_win_probability (DECIMAL(10,4)) | row_current_ind |
| `positions` | Open trades | market_id, position_qty, side, trailing_stop_state, exit_reason, exit_priority | position_price, current_price, unrealized_pnl (DECIMAL(10,4)) | row_current_ind |
| `position_exits` | Exit events | position_id, exit_condition, exit_priority, quantity_exited | exit_price (DECIMAL(10,4)) | None (append-only) |
| `exit_attempts` | Exit order attempts | position_id, exit_condition, order_type, attempt_number | limit_price, fill_price (DECIMAL(10,4)) | None (append-only) |
| `trades` | Executed orders | market_id, quantity, side, strategy_id, model_id | price, fees (DECIMAL(10,4)) | None (append-only) |
| `settlements` | Market outcomes | market_id, outcome, payout | payout (DECIMAL(10,4)) | None |
| `account_balance` | Account balance | platform_id, balance | balance (DECIMAL(10,4)) | row_current_ind |
| `config_overrides` | Runtime config | config_key, override_value | N/A | None |
| `circuit_breaker_events` | Breaker logs | breaker_type, triggered_at | N/A | None |
| `system_health` | Component health | component, status | N/A | None |
| `alerts` | Alert logging | alert_id, severity, message | N/A | None |
| `platform_markets` | Multi-platform market linking | kalshi_market_id, polymarket_market_id | N/A | None |
| `methods` | Trading methods (Phase 4-5 - PLACEHOLDER) | method_id, method_name, method_version | N/A | Immutable Versions |
| `method_templates` | Method templates (Phase 4-5 - PLACEHOLDER) | template_id, template_name | N/A | None |

#### ML Infrastructure Tables (Phase 9 - PLACEHOLDERS)

| Table | Purpose | Key Columns | Versioning | Phase |
|-------|---------|-------------|------------|-------|
| `feature_definitions` | Feature metadata | feature_id, feature_name, feature_version | Immutable Versions | Phase 9 |
| `features_historical` | Historical feature values | feature_id, entity_id, timestamp, feature_value | None (time-series) | Phase 9 |
| `training_datasets` | Training data organization | dataset_id, sport, start_date, end_date, feature_ids | None | Phase 9 |
| `model_training_runs` | ML training metadata | run_id, model_id, dataset_id, metrics | None | Phase 9 |

**Note:** ML tables are designed now but implementation deferred to Phase 9 when XGBoost/LSTM models are introduced. Elo (Phase 4) does not require feature storage.

**Total Tables:** 25 operational (21 original + 2 lookup tables + 2 additional) + 4 ML placeholders = 29 tables

**Detailed schema with indexes, constraints, and sample queries**: See `DATABASE_SCHEMA_SUMMARY_V1.11.md`

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

**Trade Attribution Query:**
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

### 4.7 Trading Methods (Phase 4-5 Implementation)

Trading methods bundle complete trading approaches (strategy + model + position management + risk) into versioned, immutable configurations for A/B testing and trade attribution.

**REQ-METH-001: Method Creation from Templates**
- Phase: 4-5
- Priority: High
- Status: 🔵 Planned
- Description: Create methods from templates (conservative, moderate, aggressive) with custom parameters

**REQ-METH-002: Immutable Method Configurations**
- Phase: 4-5
- Priority: Critical
- Status: 🔵 Planned
- Description: Method configs (strategy_id, model_id, position_mgmt_config, risk_config) are IMMUTABLE once created

**REQ-METH-003: Semantic Versioning for Methods**
- Phase: 4-5
- Priority: High
- Status: 🔵 Planned
- Description: v1.0 → v1.1 (bug fix), v1.0 → v2.0 (major change), enforce semantic versioning

**REQ-METH-004: Configuration Hashing**
- Phase: 4-5
- Priority: Medium
- Status: 🔵 Planned
- Description: Generate MD5 hash of all configs for comparison and duplicate detection

**REQ-METH-005: Method Lifecycle Management**
- Phase: 4-5
- Priority: High
- Status: 🔵 Planned
- Description: Status lifecycle: draft → testing → active → deprecated

**REQ-METH-006: Activation Criteria**
- Phase: 4-5
- Priority: High
- Status: 🔵 Planned
- Description: Require minimum 10 paper trades with positive ROI before activation

**REQ-METH-007: Trade Attribution to Methods**
- Phase: 4-5
- Priority: Critical
- Status: 🔵 Planned
- Description: Link trades and edges to method_id for complete attribution

**REQ-METH-008: A/B Testing Support**
- Phase: 4-5
- Priority: Medium
- Status: 🔵 Planned
- Description: Compare performance across method versions with statistical significance tests

**REQ-METH-009: Helper Views**
- Phase: 4-5
- Priority: Low
- Status: 🔵 Planned
- Description: active_methods view, method_performance view, method_comparison view

**REQ-METH-010: Export/Import Capability**
- Phase: 4-5
- Priority: Low
- Status: 🔵 Planned
- Description: Export methods as JSON for sharing, import for restoration

**REQ-METH-011: Deprecation Automation**
- Phase: 4-5
- Priority: Medium
- Status: 🔵 Planned
- Description: Auto-deprecate methods with < 50% win rate over 30 days or < -10% ROI

**REQ-METH-012: Historical Retention**
- Phase: 4-5
- Priority: Low
- Status: 🔵 Planned
- Description: Retain deprecated methods for 5 years for historical analysis

**REQ-METH-013: Backward Compatibility**
- Phase: 4-5
- Priority: High
- Status: 🔵 Planned
- Description: method_id columns on trades/edges are NULLABLE for backward compatibility

**REQ-METH-014: Method Templates**
- Phase: 4-5
- Priority: Medium
- Status: 🔵 Planned
- Description: Provide reusable templates: conservative, moderate, aggressive

**REQ-METH-015: Performance Tracking**
- Phase: 4-5
- Priority: High
- Status: 🔵 Planned
- Description: Track paper_roi, live_roi, sharpe_ratio, win_rate, total_trades per method version

**Implementation Note:** Methods table designed in Phase 0.5 (ADR-021) but implementation deferred to Phase 4-5 when strategy and model versioning systems are fully operational. See DATABASE_SCHEMA_SUMMARY_V1.11.md for complete schema.

---

### 4.8 Alerts & Monitoring (Phase 1 Implementation)

Centralized alert and notification system for critical events, errors, and system health monitoring.

**REQ-ALERT-001: Centralized Alert Logging**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Log all alerts to centralized alerts table with full metadata

**REQ-ALERT-002: Severity Levels**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Four severity levels: critical, high, medium, low

**REQ-ALERT-003: Acknowledgement Tracking**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Track when alerts are acknowledged, by whom, with notes

**REQ-ALERT-004: Resolution Tracking**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Track when alerts are resolved, resolution action (fixed, false_positive, ignored, escalated)

**REQ-ALERT-005: Multi-Channel Notifications**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Support console, file, email, SMS, Slack, webhook notification channels

**REQ-ALERT-006: Severity-Based Routing**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Route alerts by severity (critical → email+SMS, medium → file, low → database only)

**REQ-ALERT-007: Alert Deduplication**
- Phase: 1
- Priority: Medium
- Status: 🔵 Planned
- Description: Use fingerprint (MD5) to detect and suppress duplicate alerts

**REQ-ALERT-008: Rate Limiting**
- Phase: 1
- Priority: Medium
- Status: 🔵 Planned
- Description: Prevent alert spam with configurable rate limits

**REQ-ALERT-009: Email Notifications**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Send email alerts via SMTP (stdlib smtplib)

**REQ-ALERT-010: SMS Notifications**
- Phase: 1
- Priority: Medium
- Status: 🔵 Planned
- Description: Send SMS alerts via Twilio ($1/month + $0.0079/SMS)

**REQ-ALERT-011: Notification Delivery Tracking**
- Phase: 1
- Priority: Medium
- Status: 🔵 Planned
- Description: Track which channels were used, delivery status, attempt count, errors

**REQ-ALERT-012: Source Linking**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Link alerts to source events (circuit_breaker_events, system_health, trades)

**REQ-ALERT-013: Environment Tagging**
- Phase: 1
- Priority: Medium
- Status: 🔵 Planned
- Description: Tag alerts with environment (demo, prod) for filtering

**REQ-ALERT-014: Flexible Metadata**
- Phase: 1
- Priority: Low
- Status: 🔵 Planned
- Description: Store alert details in JSONB for flexible, schema-less metadata

**REQ-ALERT-015: Query Performance**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: Index on type, severity, component, triggered_at, unresolved, fingerprint, environment

**Alert Routing Example:**
- **CRITICAL**: circuit_breaker, daily_loss_limit → console + file + email + SMS + database
- **HIGH**: api_failure, loss_threshold → console + file + email + database
- **MEDIUM**: gain_threshold, system_warning → console + file + database
- **LOW**: informational → file + database

**Implementation:** See DATABASE_SCHEMA_SUMMARY_V1.11.md for alerts table schema. Configuration in system.yaml (notifications section). Implementation in utils/notification_manager.py and utils/alert_manager.py.

---

### 4.9 Machine Learning Infrastructure (Phased Approach)

ML infrastructure evolves across phases from simple lookup tables to advanced feature engineering and model training.

**REQ-ML-001: Phase 1-6 - Probability Matrices + Simple Models (CURRENT)**
- Phase: 1-6
- Priority: Critical
- Status: 🔵 Planned
- Description: Use probability_matrices for historical lookup tables and probability_models for model versioning. Elo (Phase 4) calculates on-the-fly without feature storage. Regression (Phase 4) uses basic stats from game_states table. Sport expansion (Phase 6) applies existing models to new sports.
- Tables Required: probability_matrices, probability_models
- **No ML feature storage needed for Phases 1-6**

**REQ-ML-002: Phase 9 - Feature Storage for Advanced ML (PLANNED)**
- Phase: 9
- Priority: High
- Status: 🔵 Planned
- Description: Add feature_definitions and features_historical tables to support advanced ML models (XGBoost, LSTM). Store DVOA, EPA, SP+, team stats, player stats as time-series features. Enable model training with historical features.
- Tables Required: feature_definitions, features_historical
- Implementation Trigger: When moving beyond simple Elo/regression to complex ML models

**REQ-ML-003: Phase 9 - MLOps Infrastructure (PLANNED)**
- Phase: 9
- Priority: Medium
- Status: 🔵 Planned
- Description: Add training_datasets and model_training_runs tables for full MLOps. Track training experiments, hyperparameters, metrics, feature importance. Support A/B testing and continuous learning pipelines.
- Tables Required: training_datasets, model_training_runs
- Implementation Trigger: When training XGBoost/LSTM models

**REQ-ML-004: Model Development Documentation (CONTINUOUS)**
- Phase: 1-10
- Priority: Medium
- Status: 🔵 Planned
- Description: Document model selection process, feature engineering decisions, validation methodology. Create learning resources for probability and ML concepts.
- Documents Required:
  - PROBABILITY_PRIMER.md (Phase 4)
  - ELO_IMPLEMENTATION_GUIDE.md (Phase 4)
  - MACHINE_LEARNING_ROADMAP.md (Phase 9)
  - MODEL_EVALUATION_GUIDE.md (Phase 9)

**REQ-MODEL-EVAL-001: Model Validation Framework**
- Phase: 1.5-2
- Priority: Critical
- Status: 🔵 Planned
- Reference: DATABASE_SCHEMA_SUMMARY_V1.11.md (evaluation_runs, predictions tables), ADR-082 (Model Evaluation Framework)
- Description: Comprehensive framework for validating probability model performance before deployment to live trading
- Validation Types:
  - **Backtesting**: Test model on historical data (2019-2024 archives) with known outcomes
  - **Cross-Validation**: K-fold validation (k=5) for temporal data (preserve chronological order)
  - **Holdout Validation**: Reserve recent data (e.g., 2024 Q4) for final validation before activation
- Evaluation Runs Tracking:
  - Store run metadata in evaluation_runs table (model_id, model_version, dataset_name, run_type, run_started_at, run_completed_at)
  - Track summary metrics (accuracy, brier_score, calibration_ece, log_loss) for quick reference
  - Support multiple datasets per model (NFL 2023, NFL 2024 Q1-Q3, NBA 2023, etc.)
- Individual Predictions Storage:
  - Store each prediction in predictions table (predicted_prob, actual_outcome, market_price, edge, is_ensemble=FALSE)
  - Enable detailed error analysis (prediction_error, squared_error)
  - Support calibration analysis (probability bins for ECE calculation)
  - Unified table supports both individual model predictions (Phase 1.5-2) and ensemble predictions (Phase 4+)
- Activation Criteria:
  - **Minimum Sample Size**: ≥100 predictions for statistical significance
  - **Accuracy Threshold**: ≥52% correct predictions (better than coin flip + margin)
  - **Brier Score**: ≤0.20 (lower is better, <0.20 indicates good calibration)
  - **Calibration ECE**: ≤0.10 (Expected Calibration Error <10% indicates well-calibrated probabilities)
- Status Lifecycle: Models remain 'draft' until validation criteria met, then eligible for 'testing' (paper trading) status

**REQ-MODEL-EVAL-002: Calibration Testing**
- Phase: 1.5-2
- Priority: Critical
- Status: 🔵 Planned
- Reference: DATABASE_SCHEMA_SUMMARY_V1.11.md (predictions table), MODEL_EVALUATION_GUIDE_V1.0.md
- Description: Validate model probability calibration to ensure predicted probabilities match actual outcome frequencies
- Calibration Metrics:
  - **Brier Score**: Mean squared error between predicted probabilities and actual outcomes (0 = perfect, 1 = worst)
    - Formula: `(1/N) * Σ(predicted_prob - actual_outcome)²`
    - Target: ≤0.20 for deployment
  - **Expected Calibration Error (ECE)**: Average gap between predicted probability and observed frequency across bins
    - Bins: [0.0-0.1], [0.1-0.2], ..., [0.9-1.0] (10 bins)
    - Formula: `Σ (|bin_accuracy - bin_confidence| * bin_weight)`
    - Target: ≤0.10 for deployment
  - **Log Loss**: Penalizes confident incorrect predictions heavily
    - Formula: `-(1/N) * Σ(actual * log(pred) + (1-actual) * log(1-pred))`
    - Target: ≤0.50 for deployment
- Reliability Diagrams:
  - Plot predicted probability (x-axis) vs. observed frequency (y-axis)
  - Perfect calibration = 45-degree diagonal line
  - Store probability bins in predictions table (probability_bin column)
  - Generate plots during evaluation runs (Phase 6-7 dashboard integration)
- Calibration Validation Process:
  1. Run model on validation dataset (100+ predictions)
  2. Store predictions in predictions table with probability bins (is_ensemble=FALSE)
  3. Calculate Brier score, ECE, log loss from stored predictions
  4. Store summary metrics in evaluation_runs table
  5. Compare against thresholds to determine if model is well-calibrated
- Integration: Calibration metrics displayed in model_calibration_summary materialized view (Phase 6-7)

**Elo Timeline Clarification:**
- **Phase 4 (Weeks 7-9)**: Initial Elo implementation for NFL (`elo_nfl v1.0`)
- **Phase 6 (Weeks 15-16)**: Extend Elo to new sports (`elo_nba v1.0`, `elo_mlb v1.0`)
- **Phase 9 (Weeks 21-24)**: Enhanced Elo with DVOA, EPA, SP+ features (requires feature storage)

**ML Table Placeholders:** See Section 4.2 for ML table schemas. Tables designed now but implementation deferred to Phase 9.

---

### 4.10 CLI Commands (Phase 1 Implementation)

Command-line interface for interacting with Kalshi API and managing local database operations.

**REQ-CLI-001: CLI Framework with Typer**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: Implement CLI using Typer framework with automatic type hint inference, help generation, and command grouping
- Implementation: `main.py` as entry point with Typer app instance
- Benefits: Type safety, automatic validation, rich help output, IDE support

**REQ-CLI-002: Balance Fetch Command**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: `main.py fetch-balance` command to retrieve account balance from Kalshi API and store in database
- Functionality: Call Kalshi API `/portfolio/balance`, parse response, store in account_balance table with timestamp
- Output: Display current balance, available balance, and payout_pending_balance (all as Decimal)

**REQ-CLI-003: Positions Fetch Command**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: `main.py fetch-positions` command to retrieve all open positions and store/update in database
- Functionality: Call Kalshi API `/portfolio/positions`, update positions table using SCD Type 2 versioning
- Output: Display count of open positions, total exposure, unrealized P&L

**REQ-CLI-004: Fills Fetch Command**
- Phase: 1
- Priority: Critical
- Status: 🔵 Planned
- Description: `main.py fetch-fills` command to retrieve trade fills and store in trades table
- Functionality: Call Kalshi API `/portfolio/fills`, insert new fills into trades table (append-only)
- Output: Display count of new fills, total executed volume, execution summary

**REQ-CLI-005: Settlements Fetch Command**
- Phase: 1
- Priority: High
- Status: 🔵 Planned
- Description: `main.py fetch-settlements` command to retrieve market settlements and update database
- Functionality: Call Kalshi API `/portfolio/settlements`, update markets and positions tables with settlement data
- Output: Display count of settled markets, total settlement proceeds, realized P&L

**CLI Design Principles:**
- All commands use type hints for automatic validation
- All prices displayed and stored as Decimal (NEVER float)
- Rich console output with tables and colors (using `rich` library)
- Comprehensive error handling with user-friendly messages
- Verbose flag (`--verbose`) for debugging
- Dry-run flag (`--dry-run`) for testing without database writes

---

### 4.11 Analytics & Performance Tracking (Phase 1.5-2, 6-7, 9)

Comprehensive performance tracking, model validation, and analytics infrastructure for measuring strategy effectiveness, model calibration, and A/B testing.

**REQ-ANALYTICS-001: Performance Metrics Collection**
- Phase: 1.5-2
- Priority: Critical
- Status: 🔵 Planned
- Reference: ADR-078 (Config Storage), DATABASE_SCHEMA_SUMMARY_V1.11.md (Section 8)
- Description: Collect and store performance metrics for strategies, models, methods, edges, and ensembles across multiple time-series aggregation periods
- Metrics Tracked:
  - **Trading Performance**: ROI, win_rate, sharpe_ratio, sortino_ratio, max_drawdown, avg_trade_size, total_pnl, unrealized_pnl
  - **Model Validation**: accuracy, precision, recall, f1_score, auc_roc, brier_score, calibration_ece, log_loss
- Data Sources:
  - **Live trading metrics**: Calculated from trades and positions tables
  - **Backtesting metrics**: Calculated from evaluation_runs and model_predictions tables
  - **Unified storage**: performance_metrics table supports both data sources
- Statistical Context: Store confidence intervals (95% CI), standard deviation, standard error for all metrics
- Implementation: Real-time collection during trading (after each trade) + batch aggregation pipelines (hourly, daily, monthly)

**REQ-ANALYTICS-002: Time-Series Performance Storage**
- Phase: 1.5-2
- Priority: Critical
- Status: 🔵 Planned
- Reference: DATABASE_SCHEMA_SUMMARY_V1.11.md (performance_metrics table)
- Description: Store performance metrics at 8 aggregation levels with automated retention policies
- Aggregation Periods:
  1. **trade**: Individual trade-level metrics (sample_size = 1)
  2. **hourly**: 1-hour rolling windows
  3. **daily**: Calendar day aggregations
  4. **weekly**: Calendar week aggregations
  5. **monthly**: Calendar month aggregations
  6. **quarterly**: Calendar quarter aggregations
  7. **yearly**: Calendar year aggregations
  8. **all_time**: Lifetime performance (no time bounds)
- Period Tracking: Store period_start and period_end timestamps for all aggregations except trade-level
- Retention Tiers:
  - **Hot Storage (0-18 months)**: All aggregation levels, <100ms query performance, PostgreSQL main tables
  - **Warm Storage (18-42 months)**: Daily+ only (hourly/trade archived), <500ms query performance, PostgreSQL compressed tables
  - **Cold Storage (42+ months)**: Monthly+ only (daily archived), <5s query performance, S3/Parquet format
- Archival Strategy: Automated archival based on age thresholds with configurable policies

**REQ-ANALYTICS-003: Metrics Aggregation Pipeline**
- Phase: 1.5-2
- Priority: High
- Status: 🔵 Planned
- Reference: ADR-080 (Metrics Collection Strategy - Real-time + Batch)
- Description: Implement dual-mode aggregation for real-time and batch metric calculations
- Real-Time Collection (Phase 1.5-2):
  - Trigger: After each trade execution
  - Scope: Calculate trade-level metrics immediately (ROI, realized_pnl)
  - Update: Update all_time aggregation (rolling lifetime stats)
  - Performance Target: <50ms overhead per trade
- Batch Aggregation (Phase 2):
  - Schedule: Hourly (at :00), daily (at 00:00 UTC), weekly (Sunday 00:00), monthly (1st 00:00)
  - Scope: Calculate aggregated metrics for completed periods
  - Data Sources: Query trades and positions tables for period-specific data
  - Statistical Calculations: Compute confidence intervals, standard deviation, standard error for each metric
  - Performance Target: <5 minutes for daily aggregation, <30 minutes for monthly
- Materialized Views (Phase 6-7):
  - strategy_performance_summary: Pre-aggregated dashboard metrics (refresh hourly)
  - model_calibration_summary: Pre-aggregated validation metrics (refresh daily)
  - Performance Target: <50ms dashboard query response

**REQ-ANALYTICS-004: Historical Performance Retention**
- Phase: 2+
- Priority: High
- Status: 🔵 Planned
- Reference: DATABASE_SCHEMA_SUMMARY_V1.11.md (performance_metrics_archive table)
- Description: Implement automated archival and retrieval for historical performance data
- Archival Triggers:
  - **Age-Based**: Metrics older than 18 months (hot → warm), 42 months (warm → cold)
  - **Performance-Based**: Deprecated strategies/models moved to cold storage immediately
  - **Manual**: Administrative command to archive specific entities
- Archival Process:
  1. Identify metrics meeting archival criteria
  2. Copy to archive table (performance_metrics_archive for warm, S3/Parquet for cold)
  3. Delete trade/hourly aggregations (keep daily+ for warm, monthly+ for cold)
  4. Update storage_tier, archived_at, archival_reason columns
  5. Log archival activity to alerts table
- Retrieval Process:
  - Query combines hot + warm tables automatically (via UNION view)
  - Cold storage requires explicit S3/Parquet query (Phase 7+)
  - Performance Target: <500ms for hot+warm queries, <5s for cold queries
- Retention Policy:
  - Hot: 18 months (configurable)
  - Warm: 24 months (18-42 months total)
  - Cold: Indefinite (compliance requirement)
- Compliance: Historical data retained for 5+ years for regulatory and audit purposes

**REQ-REPORTING-001: Performance Dashboard**
- Phase: 6-7
- Priority: High
- Status: 🔵 Planned
- Reference: ADR-081 (Dashboard Architecture), DATABASE_SCHEMA_SUMMARY_V1.11.md (materialized views), DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md
- Description: Web-based performance dashboard for visualizing strategy/model performance, calibration, and system health
- Technology Stack:
  - **Frontend**: React + Next.js (TypeScript)
  - **UI Framework**: Tailwind CSS + shadcn/ui components
  - **Charts**: Recharts or Chart.js for time-series and calibration plots
  - **Data Fetching**: React Query for caching and server state management
  - **Backend**: FastAPI (Python) REST API
  - **Authentication**: OAuth 2.0 + JWT tokens (Phase 7+)
- Dashboard Pages:
  1. **Strategy Performance**:
     - 30-day and all-time ROI, win rate, Sharpe ratio per strategy version
     - Time-series charts (daily aggregation) showing P&L trends
     - Top 5 best/worst performing strategies
     - Filter by strategy name, version, status (active/testing/deprecated)
     - Data Source: strategy_performance_summary materialized view (<50ms queries)
  2. **Model Calibration**:
     - Latest evaluation run metrics (accuracy, Brier score, ECE, log loss) per model
     - Reliability diagrams (predicted probability vs. observed frequency)
     - Calibration trend over time (track if model degrading)
     - Filter by model name, version, sport
     - Data Source: model_calibration_summary materialized view (<50ms queries)
  3. **Live Trading Status**:
     - Current open positions with unrealized P&L
     - Recent trades (last 24 hours) with execution details
     - Account balance and exposure metrics
     - System health indicators (API connectivity, database status, circuit breakers)
     - Data Source: Direct queries to positions, trades, account_balance, system_health tables
  4. **Historical Analysis** (Phase 7):
     - Query historical performance metrics with custom date ranges
     - Compare strategy/model versions (A/B test results)
     - Drill-down from aggregated to trade-level details
     - Export data as CSV/JSON for external analysis
     - Data Source: performance_metrics table (hot+warm storage), optional S3/Parquet (cold)
- Performance Requirements:
  - **Dashboard Load Time**: <2s for all pages
  - **Chart Render Time**: <500ms for time-series charts
  - **Data Refresh**: Auto-refresh every 30s for live data, manual refresh for historical
  - **Query Performance**: Leverage materialized views for sub-50ms dashboard queries
- Security:
  - Authentication required (no anonymous access)
  - Role-based access control (admin, trader, viewer)
  - API rate limiting (100 req/min per user)
  - HTTPS only (no HTTP)
- Deployment:
  - Containerized (Docker) for easy deployment
  - Reverse proxy (nginx) for SSL termination
  - CI/CD pipeline for automated deployment (Phase 7+)

**Integration Notes:**
- **Phase 1.5-2**: Core tracking implementation (performance_metrics, evaluation_runs, model_predictions tables)
- **Phase 6-7**: Dashboard integration (materialized views, enhanced collection, reporting UI)
- **Phase 9**: Advanced analytics (A/B testing, ensemble tracking, feature importance)

---

## 5. Development Phases

### Phase 0: Foundation & Documentation (COMPLETED)

**Goal**: Complete all planning, documentation, and configuration before writing code.

**Key Requirements:**
- **REQ-SYS-001: Database Schema Versioning**
- **REQ-SYS-002: Configuration Management (YAML)**
- **REQ-SYS-003: Decimal Precision for Prices**

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

### Phase 0.5: Foundation Enhancement (COMPLETED)

**Goal**: Enhance foundation with versioning, trailing stops, and position management before Phase 1 implementation.

**Status**: ✅ Complete (All 10 days finished)

**Key Requirements:**
- **REQ-VER-001: Immutable Version Configs**
- **REQ-VER-002: Semantic Versioning**
- **REQ-VER-003: Trade Attribution**
- **REQ-VER-004: Version Lifecycle Management**
- **REQ-VER-005: A/B Testing Support**
- **REQ-TRAIL-001: Dynamic Trailing Stops**
- **REQ-TRAIL-002: JSONB State Management**
- **REQ-TRAIL-003: Stop Price Updates**
- **REQ-TRAIL-004: Peak Price Tracking**
- **REQ-MON-001: Dynamic Monitoring Frequencies**
- **REQ-MON-002: Position State Tracking**
- **REQ-EXIT-001: Exit Priority Hierarchy**
- **REQ-EXIT-002: 10 Exit Conditions**
- **REQ-EXEC-001: Urgency-Based Execution**

**Key Deliverables**:
- ✅ **Database Schema V1.5 Applied**:
  - ✅ `probability_models` table (immutable versions)
  - ✅ `strategies` table (immutable versions)
  - ✅ `trailing_stop_state` JSONB column in positions
  - ✅ `strategy_id`, `model_id` FKs in edges and trades
  - ✅ `position_exits` and `exit_attempts` tables
  - ✅ Helper views (active_strategies, active_models, trade_attribution)
- ✅ **Documentation Complete** (10-day plan):
  - ✅ Days 1-10: All foundation documentation updated
  - ✅ VERSIONING_GUIDE, TRAILING_STOP_GUIDE, POSITION_MANAGEMENT_GUIDE created
  - ✅ REQUIREMENT_INDEX, ADR_INDEX created
  - ✅ MASTER_INDEX V2.3 updated

**Documentation**:
- `DATABASE_SCHEMA_SUMMARY_V1.11.md`
- `VERSIONING_GUIDE_V1.0.md`
- `TRAILING_STOP_GUIDE_V1.0.md`
- `POSITION_MANAGEMENT_GUIDE_V1.0.md`
- `REQUIREMENT_INDEX.md`
- `ADR_INDEX.md`

---

### Phase 1: Core Foundation (Weeks 1-6)

**Goal**: Establish project structure, Kalshi API connectivity, CLI commands, and account management.

**Status**: 🟡 50% Complete (Database ✅, API/CLI ❌)

**Key Requirements:**
- **REQ-API-001: Kalshi API Integration**
- **REQ-API-002: RSA-PSS Authentication (Kalshi)**
- **REQ-API-005: API Rate Limit Management**
- **REQ-API-006: API Error Handling**
- **REQ-DB-008: Database Connection Pooling**
- **REQ-CLI-001: CLI Command Framework** (NEW)
- **REQ-CLI-002: Balance Fetch Command** (NEW)
- **REQ-CLI-003: Positions Fetch Command** (NEW)
- **REQ-CLI-004: Fills Fetch Command** (NEW)
- **REQ-CLI-005: Settlements Fetch Command** (NEW)

**Key Deliverables**:

**Week 1: Environment Setup** (✅ COMPLETE)
- ✅ Python 3.12+ virtual environment
- ✅ PostgreSQL 15+ database installation
- ✅ Git repository initialization with clean history
- ✅ Multi-environment configuration (.env with DEV/STAGING/PROD/TEST prefixes)
- ✅ Install dependencies from requirements.txt

**Weeks 1-2: Database Implementation** (✅ COMPLETE)
- ✅ All 25 tables created with proper indexes and constraints
- ✅ SCD Type 2 versioning logic implemented (row_current_ind)
- ✅ Database migrations 001-010 applied
- ✅ CRUD operations in `database/crud_operations.py`
- ✅ Database connection pool in `database/connection.py`
- ✅ 66/66 tests passing, 87% coverage
- ✅ All prices using DECIMAL(10,4) precision

**Weeks 2-4: Kalshi API Integration** (❌ NOT STARTED)
- [ ] RSA-PSS authentication implementation
- [ ] Token refresh logic (30-minute cycle)
- [ ] REST endpoints: markets, events, series, balance, positions, orders
- [ ] Error handling and exponential backoff retry logic
- [ ] Rate limiting (100 req/min throttle)
- [ ] Parse `*_dollars` fields as DECIMAL (NEVER integer cents)
- [ ] API client in `api_connectors/kalshi_client.py`

**Week 4: Configuration System** (🟡 PARTIAL)
- ✅ YAML configuration files created (7 files)
- [ ] Config loader with validation (`config/config_loader.py`)
- [ ] Environment variable integration
- [ ] Config override mechanism

**Week 5: CLI Development** (❌ NOT STARTED)
- [ ] CLI framework with Typer
- [ ] `main.py fetch-balance` command (REQ-CLI-002)
- [ ] `main.py fetch-positions` command (REQ-CLI-003)
- [ ] `main.py fetch-fills` command (REQ-CLI-004)
- [ ] `main.py fetch-settlements` command (REQ-CLI-005)
- [ ] Type hints for all commands

**Week 6: Testing & Validation** (🟡 PARTIAL)
- ✅ Database tests (66/66 passing)
- [ ] API client unit tests (mock responses)
- [ ] Integration tests (live demo API)
- [ ] CLI command tests
- [ ] Maintain >80% code coverage

**Critical**: ALL prices must use `Decimal` type and be stored as DECIMAL(10,4)

**Documentation**:
- `API_INTEGRATION_GUIDE_V2.0.md` (Kalshi section) - PLANNED
- `DEVELOPER_ONBOARDING.md` - PLANNED
- `KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md` - PLANNED
- `CLI_DEVELOPMENT_GUIDE.md` - PLANNED

---

### Phase 1.5: Foundation Validation (Week 2.5)

**Goal**: Validate Phase 0.5 enhancements before proceeding to Phase 2.

**Key Requirements:**
- **REQ-VER-001: Immutable Version Configs** (validation)
- **REQ-VER-004: Version Lifecycle Management** (validation)
- **REQ-TRAIL-001: Dynamic Trailing Stops** (validation)

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

**Key Requirements:**
- **REQ-API-001: Kalshi API Integration**
- **REQ-DB-003: DECIMAL(10,4) for Prices/Probabilities**
- **REQ-SYS-003: Decimal Precision for Prices**

**Key Deliverables**:
- ORM models for series, events, markets tables (all prices DECIMAL(10,4))
- Pagination handling for large API responses
- Scripts to fetch series (filter: category=football, tags=NFL/NCAAF)
- Scripts to fetch events (by series_ticker) with final_state capture
- Scripts to fetch markets (by event_ticker) with live price updates
- **Decimal price validation** - reject any non-DECIMAL values
- CLI commands: `main.py fetch-series`, `fetch-events`, `fetch-markets`
- Unit tests for pagination, market data CRUD, and decimal precision

**Documentation**: `API_INTEGRATION_GUIDE.md` (Kalshi pagination), `DATABASE_SCHEMA_SUMMARY_V1.11.md` (relationships)

---

### Phase 3: Live Game Stats (Weeks 5-6)

**Goal**: Retrieve and store live statistics from ESPN, Balldontlie, SportsRadar APIs.

**Key Requirements:**
- **REQ-API-003: ESPN API Integration**
- **REQ-API-004: Balldontlie API Integration**
- **REQ-PERF-002: Data Latency <5s**

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

**Key Requirements:**
- **REQ-VER-001: Immutable Version Configs** (models)
- **REQ-VER-002: Semantic Versioning** (models)
- **REQ-KELLY-001: Fractional Kelly Position Sizing**
- **REQ-KELLY-002: Default Kelly Fraction 0.25**
- **REQ-KELLY-003: Position Size Limits**

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

**Phase 4 Enhancement**: Model versioning logic implemented here
- Create model versions (v1.0, v1.1, v2.0)
- Validate model performance
- Compare model versions (A/B testing)
- Activate/deprecate models

**Documentation**: `EDGE_DETECTION_SPEC.md` (formulas, buckets, EV calculation with Decimal), `VERSIONING_GUIDE_V1.0.md` (model versioning examples)

---

### Phase 5: Position Monitoring & Exit Management (Weeks 10-14)

**Goal**: Monitor open positions dynamically and execute strategic exits based on priority hierarchy and urgency.

**Phase 5 Split**: Divided into Phase 5a (Monitoring & Evaluation) and Phase 5b (Execution & Walking).

#### **Phase 5a: Position Monitoring & Exit Evaluation (Weeks 10-12)**

**REQ-MON-001: Dynamic Monitoring Frequencies**

**Phase:** 5
**Priority:** Critical
**Status:** ✅ Complete (Documented)

**Description:**
- 30-second normal monitoring for stable positions
- 5-second urgent monitoring when within 2% of stop loss, profit target, or trailing stop
- Cache market prices for 10 seconds (reduces API calls ~66%)
- Enforce 60 API calls/minute maximum (stay under Kalshi limits)

**REQ-MON-002: Position State Tracking**

**Phase:** 5
**Priority:** Critical
**Status:** ✅ Complete (Documented)

**Description:**
- Update positions table: current_price, unrealized_pnl, unrealized_pnl_pct, last_update
- Maintain trailing_stop_state as JSONB (active, peak_price, current_stop_price, current_distance)
- Update peak_price and trailing_stop_price on favorable moves

**REQ-MON-003: Urgent Condition Detection**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**REQ-MON-004: Price Caching (10s TTL)**

**Phase:** 5
**Priority:** Medium
**Status:** ✅ Complete (Documented)

**REQ-MON-005: API Rate Management (60/min)**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**REQ-EXIT-001: Exit Priority Hierarchy**

**Phase:** 5
**Priority:** Critical
**Status:** ✅ Complete (Documented)

**Description:**
- 4-level priority system: CRITICAL > HIGH > MEDIUM > LOW
- Resolve multiple triggers by highest priority
- Log all triggered conditions to exit_attempts table

**REQ-EXIT-002: 10 Exit Conditions**

**Phase:** 5
**Priority:** Critical
**Status:** ✅ Complete (Documented)

**Description:**
1. **CRITICAL**: stop_loss, circuit_breaker
2. **HIGH**: trailing_stop, time_based_urgent (<5 min), liquidity_dried_up (spread >3¢ or volume <50)
3. **MEDIUM**: profit_target, partial_exit_target
4. **LOW**: early_exit (edge <2%), edge_disappeared (edge negative), rebalance

**NOTE**: edge_reversal REMOVED (redundant with early_exit + edge_disappeared + stop_loss)

**REQ-EXIT-003: Partial Exit Staging**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**Description:**
- Stage 1: Exit 50% at +15% profit
- Stage 2: Exit 25% (of remaining) at +25% profit
- Remaining 25%: Rides with trailing stop
- Track in position_exits table

**REQ-EXIT-004: Exit Attempt Logging**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**REQ-EXIT-005: Exit Performance Tracking**

**Phase:** 5
**Priority:** Medium
**Status:** ✅ Complete (Documented)

**Description:**
- Track exit performance metrics in position_exits table
- Analyze slippage, execution success rate, urgency vs. fill rate
- Enable "Did my exit strategy work?" analysis
- Reference: POSITION_MANAGEMENT_GUIDE_V1.0.md

#### **Phase 5b: Exit Execution & Order Walking (Weeks 13-14)**

**REQ-EXEC-001: Urgency-Based Execution**

**Phase:** 5
**Priority:** Critical
**Status:** ✅ Complete (Documented)

**Description:**
- **CRITICAL**: Market orders, 5s timeout, retry market if fails
- **HIGH**: Aggressive limits, 10s timeout, walk 2x then market
- **MEDIUM**: Fair limits, 30s timeout, walk up to 5x
- **LOW**: Conservative limits, 60s timeout, walk up to 10x

**REQ-EXEC-002: Price Walking Algorithm**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**Description:**
- Start with limit order at calculated price
- If no fill within timeout, walk price by 1¢ toward market
- Repeat up to max_walks based on urgency
- HIGH urgency: escalate to market after max walks
- MEDIUM/LOW: give up after max walks

**REQ-EXEC-003: Exit Attempt Logging**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**Description:**
- Record every attempt in exit_attempts table: position_id, exit_condition, priority_level, order_type, prices, timeouts
- Enable analysis: "Why didn't my exit fill?"

**REQ-EXEC-004: Order Timeout Management**

**Phase:** 5
**Priority:** High
**Status:** ✅ Complete (Documented)

**REQ-EXEC-005: Execution Success >95%**

**Phase:** 5
**Priority:** High
**Status:** 🔵 Planned

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

**Documentation**: `POSITION_MANAGEMENT_GUIDE_V1.0.md`, `VERSIONING_GUIDE_V1.0.md`, `TRAILING_STOP_GUIDE_V1.0.md`

---

### Phase 6: Expand to Other Sports (Weeks 15-16)

**Goal**: Add NBA, MLB, Tennis, and other sports markets with versioned models.

**Key Requirements:**
- **REQ-VER-001: Immutable Version Configs** (sport-specific models)
- **REQ-KELLY-001: Fractional Kelly Position Sizing** (sport-specific)

**Key Deliverables**:
- Identify Kalshi series for new sports
- API clients for NBA/MLB/Tennis stats (ESPN or alternatives)
- Generate historical probability matrices for new sports (DECIMAL precision)
- **Create sport-specific model versions** (elo_nba v1.0, elo_mlb v1.0)
- Add new sport data to probability_matrices table
- Extend edge detector to support multiple sports
- **Sport-specific Kelly fractions** (NFL: 0.25, NBA: 0.22, Tennis: 0.18)
- CLI command: `main.py fetch-markets --sport NBA`

**Documentation**: `API_INTEGRATION_GUIDE.md` (new sport APIs), update `EDGE_DETECTION_SPEC.md`, `VERSIONING_GUIDE_V1.0.md` (sport-specific model examples)

---

### Phase 7: Live Trading for Other Sports (Weeks 15-16)

**Goal**: Enable automated trading across all supported sports with versioned strategies.

**Key Requirements:**
- **REQ-VER-001: Immutable Version Configs** (sport-specific strategies)
- **REQ-RISK-001: Circuit Breakers**
- **REQ-RISK-002: Daily Loss Limit**
- **REQ-RISK-003: Max Open Positions**

**Key Deliverables**:
- Validate probability accuracy for new sports via backtesting
- **Create sport-specific strategy versions** for new sports
- Sport-specific risk calibration (adjust volatility parameters, max spreads)
- Enable multi-sport automated scheduler
- **Cross-sport exposure tracking** to prevent over-concentration
- **Trailing stops** for all sports positions
- CLI command: `main.py trade --sport all --auto`

**Documentation**: Update `EDGE_DETECTION_SPEC.md` (sport-specific adjustments), `VERSIONING_GUIDE_V1.0.md` (multi-sport versioning)

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

**Documentation**: `WEB_SCRAPING_GUIDE.md` (BeautifulSoup/Scrapy examples, rate limiting), `VERSIONING_GUIDE_V1.0.md` (non-sports model examples)

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

**Documentation**: `MCP_INTEGRATION_GUIDE.md`, update `API_INTEGRATION_GUIDE.md`, `VERSIONING_GUIDE_V1.0.md` (ensemble model examples)

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

**Documentation**: `POLYMARKET_INTEGRATION_GUIDE.md`, `PLATFORM_ABSTRACTION_DESIGN.md`, update `ARCHITECTURE_DECISIONS.md`, `VERSIONING_GUIDE_V1.0.md` (cross-platform versioning)

---

## 6. Configuration & Environment

### 6.1 Environment Variables (.env.template)

**REQ-SYS-002: Configuration Management (YAML)**

**Phase:** 0
**Priority:** Critical
**Status:** ✅ Complete

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

**See CONFIGURATION_GUIDE.md for detailed YAML specifications including versioning and trailing stop configurations**

### 6.3 Dependencies (requirements.txt)
```
python-dotenv==1.0.0
requests==2.31.0
aiohttp==3.9.1
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pandas==2.1.4
numpy==1.26.2
transformers==4.47.0  # Hugging Face Transformers for sentiment analysis
torch==2.5.0  # PyTorch backend for transformers
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

**REQ-TEST-001: Code Coverage >80%**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned

**REQ-TEST-002: Unit Tests for Core Modules**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned

**REQ-TEST-003: Integration Tests for APIs**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned

**REQ-TEST-004: Backtesting Framework**

**Phase:** 4
**Priority:** High
**Status:** 🔵 Planned

**REQ-TEST-005: Test Result Persistence**

**Phase:** 0.6c
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-039, TESTING_STRATEGY_V3.1.md

Test results must be persisted with timestamps for trend analysis and CI/CD integration:
- Timestamped HTML reports in `test_results/YYYY-MM-DD_HHMMSS/`
- Coverage reports (HTML, XML, terminal)
- Latest symlink for easy access
- 30-day retention policy

**REQ-TEST-006: Security Testing Integration**

**Phase:** 0.7
**Priority:** Critical
**Status:** 🔵 Planned
**Reference:** ADR-043, ADR-054

Integrate security testing tools for vulnerability detection:
- **Ruff security rules (--select S)**: Static analysis for security issues (Python 3.14 compatible, replaces Bandit)
- **Safety**: Dependency vulnerability scanning
- **Secret Detection**: Pre-commit hooks for credential scanning
- **SAST Integration**: GitHub Advanced Security

**Note:** Originally specified Bandit, but Bandit 1.8.6 is incompatible with Python 3.14 (`ast.Num` removed). Ruff S-rules provide equivalent coverage (hardcoded passwords, SQL injection, file permissions) with 10-100x better performance. See ADR-054 for rationale.

**REQ-TEST-007: Mutation Testing**

**Phase:** 0.7
**Priority:** Medium
**Status:** 🔵 Planned
**Reference:** ADR-044

Validate test quality through mutation testing:
- **mutmut** for Python mutation testing
- Target: 60%+ mutation score on critical modules
- Focus areas: trading logic, edge detection, risk management
- Exclude: trivial getters, logging, configuration

**REQ-TEST-008: Property-Based Testing - Proof of Concept**

**Phase:** 1.5
**Priority:** 🔴 Critical
**Status:** ✅ Complete
**Reference:** ADR-074, `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md`

Implement property-based testing proof-of-concept with Hypothesis framework:

**Proof-of-Concept Complete (26 tests, 2600+ cases, 0 failures, 3.32s):**
- `tests/property/test_kelly_criterion_properties.py` - 11 properties, 1100+ cases
- `tests/property/test_edge_detection_properties.py` - 16 properties, 1600+ cases

**Custom Hypothesis Strategies:**
- `probability()` - Generate valid probabilities [0, 1] as Decimal
- `market_price()` - Generate market prices [0, 1] as Decimal
- `edge_value()` - Generate edge values [-0.5, 0.5] as Decimal
- `kelly_fraction()` - Generate Kelly fractions [0, 1] as Decimal
- `bankroll_amount()` - Generate bankroll [$100, $100k] as Decimal
- `bid_ask_spread()` - Generate realistic spreads with bid < ask

**Critical Invariants Validated:**
- Position size NEVER exceeds bankroll (prevents margin calls)
- Negative edge NEVER recommends trade (prevents guaranteed losses)
- Trailing stop price NEVER loosens (only tightens)
- Edge calculation correctly accounts for fees and spread
- Kelly criterion produces reasonable position sizes
- Decimal precision maintained throughout calculations

**Why Property-Based Testing Matters:**
- Traditional example-based tests: 5-10 hand-picked scenarios
- Property-based tests: 100+ auto-generated scenarios per property
- Hypothesis shrinking: Automatically minimizes failing examples
- Catches edge cases humans wouldn't think to test (edge = 0.9999999?)

**Integration:**
- Configured in `pyproject.toml` (max_examples=100, deadline=400ms)
- Runs with existing pytest suite
- Pre-commit hooks validate property tests

**REQ-TEST-009: Property Testing - Core Trading Logic (Phase 1.5)**

**Phase:** 1.5
**Priority:** 🔴 Critical
**Status:** 🔵 Planned
**Reference:** ADR-074, `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` (Phase 1.5)

Expand property-based testing to cover core trading logic:

**Test Suites to Implement (6-8 hours):**
1. **Config Validation Properties** (`test_config_validation_properties.py`)
   - YAML structure validation across all edge cases
   - Type safety (no strings where Decimals expected)
   - Constraint enforcement (kelly_fraction ∈ [0, 1])
   - Required fields never missing

2. **Position Sizing Properties** (expand `test_kelly_criterion_properties.py`)
   - Kelly criterion with multiple position limits
   - Fractional Kelly (quarter Kelly, half Kelly)
   - Max position constraints respected
   - Bankroll updates propagate correctly

3. **Edge Detection Properties** (expand `test_edge_detection_properties.py`)
   - Edge calculation with varying fee structures
   - Spread impact on realizable edge
   - Minimum edge threshold enforcement
   - Probability bounds validation [0, 1]

**Custom Strategies Needed:**
- `yaml_config()` - Generate valid/invalid YAML configurations
- `position_limits()` - Generate position size constraints
- `fee_structure()` - Generate fee percentages and tiered fees

**Success Criteria:**
- 40+ total properties (4000+ test cases)
- <5 second total execution time
- All critical trading invariants validated

**REQ-TEST-010: Property Testing - Data Validation & Models (Phase 2-4)**

**Phase:** 2, 3, 4
**Priority:** 🟡 High
**Status:** 🔵 Planned
**Reference:** ADR-074, `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` (Phases 2-4)

Implement property-based testing for data pipelines and models:

**Test Suites to Implement (22-28 hours):**

**Phase 2 - Data Validation (8-10h):**
1. **Historical Data Properties** (`test_historical_data_properties.py`)
   - Timestamp ordering (monotonically increasing)
   - No duplicate records (game_id + timestamp unique)
   - Score progression (scores never decrease)
   - Probability bounds [0, 1] always respected

2. **Model Validation Properties** (`test_model_validation_properties.py`)
   - Model outputs always in valid range
   - Prediction consistency (same inputs → same outputs)
   - Calibration properties (predicted probabilities vs. outcomes)
   - Version immutability enforcement

3. **Strategy Versioning Properties** (`test_strategy_versioning_properties.py`)
   - Config immutability (cannot modify after creation)
   - Status lifecycle valid transitions only
   - Version semantic correctness (v1.0 → v1.1 → v2.0)
   - Trade attribution always valid

**Phase 3 - Order Book & Entry (6-8h):**
4. **Order Book Properties** (`test_order_book_properties.py`)
   - Bid ≤ Ask always (no crossed markets)
   - Order book depth never negative
   - Liquidity aggregation correctness
   - Best execution price selection

5. **Entry Optimization Properties** (`test_entry_optimization_properties.py`)
   - Entry price ≤ worst acceptable price
   - Slippage within tolerance
   - Partial fill handling
   - Order book impact estimation

**Phase 4 - Ensemble & Backtesting (8-10h):**
6. **Ensemble Properties** (`test_ensemble_properties.py`)
   - Weight constraints (sum to 1.0)
   - Weighted average bounds (min ≤ ensemble ≤ max)
   - Model version tracking consistency
   - Feature extraction determinism

7. **Backtesting Properties** (`test_backtesting_properties.py`)
   - No lookahead bias (only past data used)
   - P&L calculation correctness
   - Performance metrics consistency (Sharpe, win rate)
   - Position sizing reflects backtest constraints

**Custom Strategies Needed:**
- `historical_game_state()` - Generate realistic game progressions
- `model_prediction()` - Generate model outputs with constraints
- `order_book()` - Generate realistic order books
- `ensemble_weights()` - Generate valid weight distributions

**Success Criteria:**
- 85+ total properties (8500+ test cases)
- <15 second total execution time
- All data invariants validated
- All model constraints enforced

**REQ-TEST-011: Property Testing - Position & Exit Management (Phase 5)**

**Phase:** 5
**Priority:** 🔴 Critical
**Status:** 🔵 Planned
**Reference:** ADR-074, `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` (Phase 5)

Implement property-based testing for position and exit management:

**Test Suites to Implement (10-12 hours):**

1. **Position Lifecycle Properties** (`test_position_lifecycle_properties.py`)
   - Position state transitions valid (open → monitoring → exited)
   - Position size always ≤ original quantity
   - Realized P&L = (exit_price - entry_price) × quantity
   - Unrealized P&L updates with current market price
   - SCD Type 2 versioning (row_current_ind consistency)

2. **Trailing Stop Properties** (`test_trailing_stop_properties.py`)
   - Stop price NEVER loosens (only tightens or stays same)
   - Stop distance maintains configured percentage
   - Activation threshold respected
   - Trigger detection accuracy (price crosses stop)
   - State persistence across position updates

3. **Exit Priority Properties** (`test_exit_priority_properties.py`)
   - 10-condition hierarchy always respected
   - Stop loss overrides all other exits
   - Target profit takes precedence over time-based
   - Emergency exits trigger immediately
   - No conflicting exit signals

4. **Exit Execution Properties** (`test_exit_execution_properties.py`)
   - Exit price within acceptable bounds
   - Slippage tolerance enforcement
   - Partial exits maintain position integrity
   - Order walking never increases average exit price
   - Circuit breaker prevents rapid exits

5. **Reporting Metrics Properties** (`test_reporting_metrics_properties.py`)
   - Win rate = wins / total_trades ∈ [0, 1]
   - Sharpe ratio calculation correctness
   - Drawdown never positive
   - Total P&L = sum of realized P&L
   - Position count consistency

**Custom Strategies Needed:**
- `position_state()` - Generate valid position states
- `trailing_stop_config()` - Generate trailing stop configurations
- `exit_condition()` - Generate exit trigger conditions
- `price_series()` - Generate realistic price movements
- `execution_context()` - Generate market conditions for execution

**Critical Properties (Trading Safety):**
- Stop loss ALWAYS prevents catastrophic losses
- Position size NEVER exceeds risk limits
- Exit prices NEVER worse than stop loss
- Trailing stops NEVER loosen (one-way ratchet)
- Circuit breaker ALWAYS triggers on rapid losses

**Success Criteria:**
- 40+ total properties (4000+ test cases)
- <8 second total execution time
- All position management invariants validated
- All exit optimization constraints enforced
- Zero false negatives on stop loss triggers

---

**REQ-TEST-012: Test Type Coverage Requirements (All Phases)**

**Phase:** 1.5+ (ongoing)
**Priority:** 🔴 Critical
**Status:** ✅ Complete
**Reference:** ADR-074 (Property-Based Testing), ADR-076 (Test Type Categories), Pattern 13 (Test Coverage Quality), `docs/foundation/DEVELOPMENT_PHILOSOPHY_V1.3.md`

Establish comprehensive test type coverage requirements to prevent false confidence from insufficient testing. Addresses Phase 1.5 TDD failure lesson: Strategy Manager had 17/17 tests passing with mocks but 13/17 tests failed (77% failure rate) when refactored to use real database fixtures.

**8 Required Test Types:**

1. **Unit Tests** - Isolated function logic with mocked external dependencies
2. **Property Tests** - Mathematical invariants with Hypothesis (100+ auto-generated test cases)
3. **Integration Tests** - Components with REAL infrastructure (database, config, logging) - NOT mocks
4. **End-to-End Tests** - Complete user workflows (fetch → analyze → execute → monitor → exit)
5. **Stress Tests** - Infrastructure limits (connection pool exhaustion, API rate limits, concurrent operations)
6. **Race Condition Tests** - Concurrent operations validation (position updates, WebSocket handling)
7. **Performance Tests** - Latency/throughput benchmarks (Phase 5+)
8. **Chaos Tests** - Failure recovery scenarios (Phase 5+)

**Test Type Requirements Matrix:**

| Module Type | Unit | Property | Integration | E2E | Stress | Race | Performance | Chaos |
|-------------|------|----------|-------------|-----|--------|------|-------------|-------|
| **Critical Path** (trading execution, position monitoring) | ✅ Req | ✅ Req | ✅ Req | ✅ Req | ✅ Req | ✅ Req | ⚠️ Phase 5+ | ⚠️ Phase 5+ |
| **Manager Layer** (strategy, model, position) | ✅ Req | ✅ Req | ✅ Req | ⚠️ Recommended | ⚠️ Recommended | ❌ N/A | ❌ N/A | ❌ N/A |
| **Infrastructure** (database, logging, config) | ✅ Req | ⚠️ If math | ✅ Req | ❌ N/A | ✅ Req | ⚠️ If concurrent | ❌ N/A | ❌ N/A |
| **API Clients** (Kalshi, ESPN) | ✅ Req | ❌ N/A | ⚠️ Mocked only | ✅ Req | ✅ Req | ❌ N/A | ⚠️ Phase 5+ | ⚠️ Phase 5+ |
| **Utilities** (helpers, formatters) | ✅ Req | ⚠️ If math | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A |

**Success Criteria:**
- All modules have required test types implemented
- Test review checklist (Pattern 13) passes before marking work complete
- Zero "tests passing but code broken" incidents

---

**REQ-TEST-013: Mock Usage Restrictions (All Phases)**

**Phase:** 1.5+ (ongoing)
**Priority:** 🔴 Critical
**Status:** ✅ Complete
**Reference:** ADR-076, Pattern 13, `docs/utility/TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md`

Establish strict rules for when mocks are appropriate vs. prohibited. Over-reliance on mocks creates false confidence by testing "did we call the right function?" instead of "does the system work correctly?".

**✅ Mocks are APPROPRIATE for:**

- **External APIs** (Kalshi, ESPN, Polymarket) - expensive, rate-limited, flaky, require network access
- **Time-dependent code** (`datetime.now()`, `time.sleep()`) - non-deterministic, difficult to test otherwise
- **Random number generation** (`random.random()`, `uuid.uuid4()`) - non-deterministic
- **Network requests** - expensive, unreliable, require external services
- **File I/O in some cases** - when testing error handling, not core functionality

**❌ Mocks are FORBIDDEN for:**

- **Database** (MUST use test database with `clean_test_data` fixture from conftest.py)
- **Internal application logic** (strategy manager, model manager, position manager)
- **Configuration loading** (MUST use test configs, not mocks)
- **Logging** (MUST use test logger, capture output)
- **Connection pooling** (MUST use `db_pool` fixture with real pool)
- **Any infrastructure we control** (our code, our database, our config files)

**Rationale:**

Mocking internal infrastructure creates tight coupling to implementation details and misses integration bugs. Example: Strategy Manager tests mocked `get_connection()` and passed 17/17 tests, but had critical connection pool leak bug that went undetected. When refactored to use real database fixtures, 13/17 tests failed (77% failure rate).

**Enforcement:**

- Pre-commit code review checks for `@patch("get_connection")` or `mock_connection` fixtures (automatic warning)
- Test review checklist (Pattern 13) includes "Tests use real infrastructure?" validation
- All database tests MUST use `clean_test_data` fixture (NO exceptions)

**Success Criteria:**
- Zero database tests using `@patch` decorators for internal infrastructure
- All tests using appropriate mocking strategy (external only)
- Test review checklist validation passes

---

**REQ-TEST-014: Test Fixture Usage Requirements (All Phases)**

**Phase:** 1.5+ (ongoing)
**Priority:** 🔴 Critical
**Status:** ✅ Complete
**Reference:** ADR-076, Pattern 13, `tests/conftest.py`

Mandate use of established test fixtures from conftest.py instead of creating ad-hoc mocks. Test infrastructure exists for a reason - bypassing fixtures leads to reinventing the wheel poorly and missing bugs.

**MANDATORY Test Fixtures (ALWAYS use these):**

```python
# tests/conftest.py provides these fixtures - ALWAYS USE THEM

@pytest.fixture
def clean_test_data(db_pool):
    """Cleans database before/after each test.

    MANDATORY for ALL database tests. Ensures:
    - Clean slate for each test (no pollution)
    - Automatic cleanup after test
    - Connection pool management
    - Transaction rollback on errors
    """

@pytest.fixture
def db_pool():
    """Provides real connection pool.

    Use for:
    - Connection pool exhaustion tests
    - Concurrent connection tests
    - Pool configuration validation
    """

@pytest.fixture
def db_cursor(db_pool):
    """Provides real database cursor.

    Use for:
    - Direct SQL execution tests
    - Schema validation tests
    - Constraint enforcement tests
    """
```

**FORBIDDEN Fixtures (NEVER create these):**

```python
# ❌ NEVER create these - use real fixtures instead

@pytest.fixture
def mock_connection():
    """FORBIDDEN - use clean_test_data instead"""

@pytest.fixture
def mock_cursor():
    """FORBIDDEN - use db_cursor instead"""

@pytest.fixture
def mock_pool():
    """FORBIDDEN - use db_pool instead"""
```

**Comparison - What We Did Wrong (Strategy Manager) vs. What We Should Do:**

```python
# ❌ WRONG - What we did (mock-based testing)
@patch("precog.trading.strategy_manager.get_connection")
def test_create_strategy(self, mock_get_connection, mock_connection, mock_cursor):
    """Test creating strategy."""
    mock_get_connection.return_value = mock_connection
    mock_cursor.fetchone.return_value = (1, "strategy_v1", "1.0", ...)  # Fake response

    manager = StrategyManager()
    result = manager.create_strategy(...)  # Calls mock, not real DB

    assert result["strategy_id"] == 1  # ✅ Test passes!
    # But implementation has connection pool leak - not caught!

# ✅ CORRECT - What we should do (real database testing)
def test_create_strategy(clean_test_data, manager, strategy_factory):
    """Test creating strategy."""
    result = manager.create_strategy(**strategy_factory)  # Calls REAL database

    assert result["strategy_id"] is not None  # ✅ Test passes
    # If connection pool leak exists → test fails with pool exhausted error ✅
```

**Evidence - Why This Matters:**

- **Model Manager**: ALL 37 tests use `clean_test_data` fixture ✅ → Zero integration bugs found
- **Strategy Manager**: 0/17 tests use `clean_test_data` fixture ❌ → 77% test failure rate when refactored

**Success Criteria:**
- 100% of database tests use `clean_test_data` fixture
- Zero tests creating `mock_connection` or `mock_cursor` fixtures
- Test review checklist validation passes

---

**REQ-TEST-015: Coverage Percentage Standards (All Phases)**

**Phase:** 1.5+ (ongoing)
**Priority:** 🔴 Critical
**Status:** ✅ Complete
**Reference:** ADR-076, Pattern 13, `docs/foundation/DEVELOPMENT_PHILOSOPHY_V1.3.md`

Establish tiered coverage percentage targets based on module criticality. Coverage percentage alone is insufficient (Strategy Manager had tests but they were mocked), but it remains a necessary baseline metric.

**Coverage Tiers:**

| Module Category | Coverage Target | Rationale | Examples |
|-----------------|-----------------|-----------|----------|
| **Critical Path** | ≥90% | Trading execution, position monitoring - bugs = lost money | Order execution, exit evaluation, position lifecycle |
| **Manager Layer** | ≥85% | Business logic coordination - bugs = incorrect decisions | StrategyManager, ModelManager, PositionManager |
| **Infrastructure** | ≥80% | Database, logging, config - bugs = system failures | connection.py, logger.py, config_loader.py |
| **API Clients** | ≥80% | External integration - bugs = missed opportunities | kalshi_client.py, espn_client.py |
| **Utilities** | ≥75% | Helper functions - bugs = minor issues | formatters, validators, converters |

**Current Coverage Status (Phase 1.5):**

```
Critical Path: N/A (Phase 5+)
Manager Layer:
  - ModelManager: 25.75% ❌ (target 85%) - GAP: 59.25%
  - StrategyManager: 19.96% ❌ (target 85%) - GAP: 65.04%
Infrastructure:
  - connection.py: 81.82% ✅ (target 80%)
  - logger.py: 86.08% ✅ (target 80%)
  - config_loader.py: 98.97% ✅ (target 80%)
  - crud_operations.py: 86.01% ✅ (target 80%)
API Clients:
  - kalshi_client.py: 97.91% ✅ (target 80%)
```

**Phase 1.5 Targets:**

- Manager Layer: Increase ModelManager from 25.75% → ≥85% (add ~230 test cases)
- Manager Layer: Increase StrategyManager from 19.96% → ≥85% (add ~260 test cases, refactor from mocks to real database)

**Coverage Quality Requirements:**

Coverage percentage MUST meet these quality standards:
- ✅ Tests use real infrastructure (database, NOT mocks) - see REQ-TEST-013
- ✅ Tests use conftest.py fixtures (clean_test_data, db_pool) - see REQ-TEST-014
- ✅ Tests cover edge cases (pool exhaustion, null values, race conditions)
- ✅ Tests cover failure modes (what happens when database fails?)
- ✅ Tests validate business logic (not just "did we call the function?")

**Success Criteria:**
- All modules meet or exceed coverage targets
- Coverage measured with real infrastructure tests (not mocks)
- Test quality validation passes (Pattern 13 checklist)

---

**REQ-TEST-016: Stress Test Requirements (Phase 1.5+)**

**Phase:** 1.5+ (infrastructure stress tests), Phase 5+ (trading stress tests)
**Priority:** 🟡 High
**Status:** 🔵 Planned
**Reference:** ADR-076, Pattern 13, `docs/utility/TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md`

Require stress testing of infrastructure limits to detect resource exhaustion bugs. Strategy Manager connection pool leak was missed because tests never stressed the pool limit (maxconn=5, tests used ≤5 connections).

**Phase 1.5 Stress Tests (Infrastructure):**

**1. Connection Pool Exhaustion Tests**
```python
def test_connection_pool_exhaustion_recovery(db_pool):
    """Test pool exhaustion detection and recovery.

    Scenario: Acquire maxconn+1 connections
    Expected: Pool exhaustion error raised, system recovers gracefully
    """
    # Acquire maxconn connections (5)
    # Attempt maxconn+1 connection (6)
    # Verify PoolExhausted error raised
    # Release 1 connection
    # Verify new connection acquisition succeeds
```

**2. Concurrent Connection Tests**
```python
def test_concurrent_database_operations(db_pool, clean_test_data):
    """Test 10+ concurrent database operations.

    Scenario: 10 threads executing database operations simultaneously
    Expected: All operations succeed, no deadlocks, no connection leaks
    """
    # Launch 10 threads
    # Each thread: create strategy, update metrics, fetch data
    # Verify all 10 operations succeed
    # Verify connection pool size unchanged (no leaks)
```

**3. API Rate Limit Tests**
```python
def test_api_rate_limit_enforcement(kalshi_client):
    """Test rate limiter prevents exceeding 100 req/min.

    Scenario: Attempt 150 requests in 1 minute
    Expected: Only 100 requests sent, 50 delayed to next minute
    """
    # Attempt 150 rapid requests
    # Verify rate limiter blocks requests 101-150
    # Verify requests resume after 60 seconds
```

**Phase 5+ Stress Tests (Trading):**

**4. Position Monitoring Stress**
- 100+ positions monitored simultaneously
- Exit conditions evaluated every second
- Verify no position updates missed

**5. WebSocket Connection Stress**
- 10,000+ market update events per minute
- Verify all events processed
- Verify no memory leaks

**6. 24-Hour Stability Tests**
- Run trading system for 24 hours
- Monitor memory usage, CPU usage, connection pool
- Verify no resource leaks

**Success Criteria:**
- All infrastructure stress tests passing (Phase 1.5)
- Connection pool exhaustion detected and handled gracefully
- API rate limiting prevents exceeding 100 req/min
- Trading stress tests passing (Phase 5+)

---

**REQ-TEST-017: Integration Test Requirements (Phase 1.5+)**

**Phase:** 1.5+ (manager layer integration)
**Priority:** 🔴 Critical
**Status:** 🔵 Planned
**Reference:** ADR-076, Pattern 13, `docs/foundation/DEVELOPMENT_PHILOSOPHY_V1.3.md`

Require integration tests with real dependencies for manager layer. Unit tests in isolation are insufficient - must test components working together with real infrastructure.

**Manager Layer Integration Tests (Phase 1.5):**

**1. Strategy Manager + Database Integration**
```python
def test_strategy_manager_crud_lifecycle(clean_test_data, manager, strategy_factory):
    """Test complete strategy CRUD lifecycle with real database.

    Workflow:
    1. Create strategy with real database
    2. Fetch strategy and verify data integrity
    3. Update strategy metrics
    4. Verify SCD Type 2 versioning (row_current_ind)
    5. Soft delete strategy
    6. Verify historical data preserved
    """
```

**2. Model Manager + Database Integration**
```python
def test_model_manager_versioning_integration(clean_test_data, manager, model_factory):
    """Test model versioning with real database.

    Workflow:
    1. Create model v1.0 with real database
    2. Create model v1.1 (different weights)
    3. Verify both versions exist in database
    4. Verify immutability (v1.0 weights unchanged)
    5. Verify version comparison queries work
    """
```

**3. Position Manager + Strategy Manager + Model Manager Integration** (Phase 2+)
```python
def test_position_attribution_integration(clean_test_data, position_mgr, strategy_mgr, model_mgr):
    """Test trade attribution across 3 managers.

    Workflow:
    1. Create strategy v1.0 and model v1.0
    2. Open position attributed to strategy v1.0 + model v1.0
    3. Update strategy to v1.1 (different config)
    4. Open new position attributed to strategy v1.1 + model v1.0
    5. Verify both positions correctly attributed
    6. Verify performance metrics segmented by version
    """
```

**API Integration Tests:**

**4. Kalshi Client + Database Integration**
```python
def test_kalshi_market_sync_integration(clean_test_data, kalshi_client, mock_kalshi_api):
    """Test syncing Kalshi markets to database.

    Workflow:
    1. Fetch markets from (mocked) Kalshi API
    2. Parse Decimal prices from *_dollars fields
    3. Insert into database with real connection
    4. Verify all Decimal precision preserved
    5. Verify no float contamination
    """
```

**Config + Database Integration:**

**5. Config Loader + Database Schema Integration**
```python
def test_config_database_schema_consistency(clean_test_data, config_loader):
    """Test configuration matches database schema constraints.

    Workflow:
    1. Load strategy config from YAML
    2. Attempt to insert strategy with config values
    3. Verify all config parameters within database constraints
    4. Verify Decimal precision requirements met
    """
```

**Success Criteria:**
- All manager layer integration tests passing
- Zero mock usage for internal infrastructure (database, config, logging)
- All tests use `clean_test_data` fixture
- Integration tests catch bugs missed by unit tests

---

**REQ-TEST-018: Property-Based Test Requirements (Phase 1+)**

**Phase:** 1+ (infrastructure properties), 4-5 (trading properties)
**Priority:** 🔴 Critical
**Status:** ✅ Complete (Phase 1 proof-of-concept)
**Reference:** ADR-074, Pattern 13, `docs/foundation/DEVELOPMENT_PHILOSOPHY_V1.3.md`

Require property-based testing with Hypothesis framework for mathematical invariants and business rules. Property tests generate 100+ test cases automatically, providing far broader coverage than example-based tests.

**Hypothesis Framework:**
- pytest plugin: `pytest-hypothesis`
- Current version: 6.92+
- Configuration: `pyproject.toml` [tool.hypothesis] settings

**ALWAYS Use Property Tests For:**

**1. Mathematical Invariants**
```python
from hypothesis import given
from hypothesis.strategies import decimals
from decimal import Decimal

@given(
    price=decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4),
    quantity=decimals(min_value=Decimal("1"), max_value=Decimal("10000"), places=2)
)
def test_trade_value_calculation_property(price, quantity):
    """Property: trade_value = price × quantity (exact Decimal arithmetic)."""
    trade_value = price * quantity

    # Invariant: Reverse calculation recovers original price
    recovered_price = trade_value / quantity
    assert recovered_price == price  # Exact equality with Decimal
```

**2. Business Rules**
```python
@given(
    edge=decimals(min_value=Decimal("0.0"), max_value=Decimal("1.0"), places=4),
    kelly_fraction=decimals(min_value=Decimal("0.1"), max_value=Decimal("0.25"), places=2)
)
def test_kelly_bet_sizing_property(edge, kelly_fraction):
    """Property: Kelly bet size ∈ [0, kelly_fraction] for all edges."""
    bet_size = calculate_kelly_bet(edge, kelly_fraction)

    # Invariant: Bet size never exceeds Kelly fraction
    assert Decimal("0") <= bet_size <= kelly_fraction
```

**3. State Transitions**
```python
@given(
    stop_price=decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4),
    market_price=decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4)
)
def test_trailing_stop_property(stop_price, market_price):
    """Property: Trailing stop NEVER loosens (one-way ratchet)."""
    new_stop = update_trailing_stop(stop_price, market_price)

    # Invariant: Stop price only tightens or stays same, NEVER loosens
    assert new_stop >= stop_price
```

**4. Data Validation**
```python
@given(
    probability=decimals(min_value=Decimal("0.0"), max_value=Decimal("1.0"), places=4)
)
def test_probability_bounds_property(probability):
    """Property: All probabilities ∈ [0, 1]."""
    result = calculate_win_probability(probability)

    # Invariant: Probability never outside [0, 1]
    assert Decimal("0") <= result <= Decimal("1")
```

**Custom Hypothesis Strategies (Trading Domain):**

```python
# tests/strategies.py - Custom strategies for trading domain

from hypothesis.strategies import composite, decimals

@composite
def probability(draw, min_value=Decimal("0.0"), max_value=Decimal("1.0")):
    """Generate valid probability values ∈ [0, 1]."""
    return draw(decimals(min_value=min_value, max_value=max_value, places=4))

@composite
def bid_ask_spread(draw, min_spread=Decimal("0.01"), max_spread=Decimal("0.10")):
    """Generate valid bid-ask spreads with bid < ask."""
    bid = draw(decimals(min_value=Decimal("0.01"), max_value=Decimal("0.89"), places=4))
    spread = draw(decimals(min_value=min_spread, max_value=max_spread, places=4))
    ask = bid + spread
    return {"bid": bid, "ask": ask}

@composite
def price_series(draw, length=100, volatility=Decimal("0.05")):
    """Generate realistic price movement series."""
    initial_price = draw(decimals(min_value=Decimal("0.10"), max_value=Decimal("0.90"), places=4))
    # Generate random walk with bounded volatility
    # ... implementation details ...
    return price_series
```

**Phase 1 Proof-of-Concept Results:**
- 26 property tests implemented
- 2,600+ test cases generated automatically (100 examples × 26 properties)
- 0 failures
- 3.32 second execution time
- Hypothesis shrinking: Failed case minimized from 473,821 to 0.5 (edge case discovery)

**Success Criteria:**
- ≥20 property tests for Phase 1 infrastructure (Decimal precision, data validation)
- ≥40 property tests for Phase 4 (strategy, model, features)
- ≥60 property tests for Phase 5 (position lifecycle, trailing stops, exit priority)
- All mathematical invariants tested with property tests
- <15 second total property test execution time

---

**REQ-TEST-019: End-to-End Test Requirements (Phase 2+)**

**Phase:** 2+ (complete workflows), 5+ (trading lifecycle)
**Priority:** 🟡 High
**Status:** 🔵 Planned
**Reference:** ADR-076, Pattern 13, `docs/foundation/DEVELOPMENT_PHILOSOPHY_V1.3.md`

Require end-to-end tests for complete user workflows. E2E tests validate that all components work together correctly in realistic scenarios.

**Phase 2 E2E Tests (Data Pipeline):**

**1. Market Data Ingestion E2E**
```python
def test_market_data_ingestion_e2e(clean_test_data, kalshi_client, config_loader):
    """E2E: Fetch market data from Kalshi → Parse → Store → Validate.

    Workflow:
    1. Fetch markets from (mocked) Kalshi API
    2. Parse Decimal prices from *_dollars fields
    3. Store in database with SCD Type 2 versioning
    4. Verify no float contamination
    5. Verify price history queryable
    """
```

**Phase 4 E2E Tests (Strategy Evaluation):**

**2. Strategy Evaluation E2E**
```python
def test_strategy_evaluation_e2e(clean_test_data, strategy_mgr, model_mgr):
    """E2E: Load strategy → Load model → Calculate features → Predict probability.

    Workflow:
    1. Create strategy v1.0 with config
    2. Create model v1.0 with weights
    3. Fetch market data
    4. Calculate model features
    5. Generate win probability prediction
    6. Calculate edge (true_prob - market_price)
    7. Verify all Decimal precision preserved
    """
```

**Phase 5 E2E Tests (Trading Lifecycle):**

**3. Complete Trading Lifecycle E2E**
```python
def test_trading_lifecycle_e2e(
    clean_test_data,
    kalshi_client,
    strategy_mgr,
    model_mgr,
    position_mgr
):
    """E2E: Complete trading workflow from market fetch to position exit.

    Workflow:
    1. Fetch market data (mocked Kalshi API)
    2. Load strategy v1.0 + model v1.0
    3. Calculate features and predict probability
    4. Identify edge > min_edge threshold
    5. Calculate Kelly bet size
    6. Execute trade (mocked API)
    7. Open position with attribution (strategy_id, model_id)
    8. Monitor position with trailing stop
    9. Trigger exit condition (target profit reached)
    10. Execute exit trade (mocked API)
    11. Close position with P&L calculation
    12. Verify trade attribution maintained
    13. Verify performance metrics updated
    14. Verify all Decimal precision preserved throughout

    Success: Complete workflow executes without errors, all data validated
    """
```

**4. Multi-Strategy Multi-Position E2E**
```python
def test_multi_strategy_multi_position_e2e(clean_test_data, managers):
    """E2E: Multiple strategies with different models managing multiple positions.

    Workflow:
    1. Create strategy v1.0 (conservative) + model v1.0
    2. Create strategy v2.0 (aggressive) + model v1.1
    3. Open 5 positions with strategy v1.0 + model v1.0
    4. Open 5 positions with strategy v2.0 + model v1.1
    5. Monitor all 10 positions simultaneously
    6. Exit positions based on different strategies
    7. Verify attribution correct for all positions
    8. Verify performance metrics segmented by strategy version
    """
```

**Phase 5+ E2E Tests (Failure Scenarios):**

**5. Database Failure Recovery E2E**
```python
def test_database_failure_recovery_e2e(clean_test_data, position_mgr):
    """E2E: System recovers gracefully from database failures.

    Workflow:
    1. Open 3 positions
    2. Simulate database connection loss
    3. Verify system detects failure
    4. Verify system attempts retry with exponential backoff
    5. Restore database connection
    6. Verify system recovers and resumes monitoring
    7. Verify no position data lost
    """
```

**Success Criteria:**
- ≥5 E2E tests for Phase 2 (data ingestion workflows)
- ≥10 E2E tests for Phase 4 (strategy evaluation workflows)
- ≥15 E2E tests for Phase 5 (complete trading lifecycle)
- All E2E tests use real infrastructure (database, config, logging)
- External APIs mocked (Kalshi, ESPN) for deterministic testing
- E2E tests catch integration bugs missed by unit/integration tests

---

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

### 7.4 Critical Tests

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

**Versioning Tests:**
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

**Trailing Stop Tests:**
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

### 7.5 Code Quality, Validation & CI/CD (Phase 0.6c-0.7)

**REQ-VALIDATION-001: Automated Code Quality (Ruff)**

**Phase:** 0.6c
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-038, VALIDATION_LINTING_ARCHITECTURE_V1.0.md

Use Ruff for unified code quality enforcement (10-100x faster than black+flake8):
- **Linting**: 50+ rule categories (E, W, F, I, N, UP, B, C4, DTZ, etc.)
- **Formatting**: Replaces black with consistent 100-char line length
- **Auto-fix**: Automatic correction of most issues
- **Configuration**: Single pyproject.toml for all tools
- **Integration**: validate_quick.sh (~3s) and validate_all.sh (~60s)

**REQ-VALIDATION-002: Documentation Validation Automation**

**Phase:** 0.6c
**Priority:** Medium
**Status:** ✅ Complete
**Reference:** ADR-040, VALIDATION_LINTING_ARCHITECTURE_V1.0.md

Automated documentation consistency validation:
- **validate_docs.py**: Checks version headers, MASTER_INDEX accuracy, paired document consistency
- **fix_docs.py**: Auto-fixes simple issues (version mismatches)
- **Validation Checks**:
  - ADR_INDEX ↔ ARCHITECTURE_DECISIONS consistency
  - REQUIREMENT_INDEX ↔ MASTER_REQUIREMENTS consistency
  - MASTER_INDEX accuracy (filenames, versions, locations)
  - Version header format and filename alignment
- **Performance**: <1 second validation time
- **Integration**: Part of validate_quick.sh and validate_all.sh

**REQ-VALIDATION-003: Layered Validation Architecture**

**Phase:** 0.6c
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-041, VALIDATION_LINTING_ARCHITECTURE_V1.0.md

Two-tier validation for different workflow stages:
- **Fast Layer (validate_quick.sh)**: ~3 seconds
  - Ruff linting and formatting
  - Mypy type checking
  - Documentation validation
  - Use: During development for rapid feedback
- **Comprehensive Layer (validate_all.sh)**: ~60 seconds
  - All fast validations
  - Full test suite with coverage
  - Security scanning (hardcoded credentials, connection strings, .env staging)
  - Use: Before commits and phase completion

**REQ-CICD-001: GitHub Actions CI/CD Integration**

**Phase:** 0.7
**Priority:** High
**Status:** 🔵 Planned
**Reference:** ADR-042, ADR-054

Implement GitHub Actions workflow for automated CI/CD:
- **Trigger**: On push to main, PR creation, manual dispatch
- **Jobs**:
  - Code quality (Ruff lint + format check)
  - Type checking (Mypy)
  - Documentation validation
  - Test suite (pytest with coverage)
  - Security scanning (Ruff security rules --select S, Safety, secret detection)
- **Matrix Testing**: Python 3.12, 3.13, 3.14 on ubuntu-latest, windows-latest
- **Artifacts**: Test reports, coverage reports
- **Status Badges**: README.md integration

**Note:** Security scanning uses Ruff S-rules instead of Bandit for Python 3.14 compatibility. See ADR-054 and REQ-TEST-006 for details.

**REQ-CICD-002: Codecov Integration**

**Phase:** 0.7
**Priority:** Medium
**Status:** 🔵 Planned
**Reference:** ADR-042

Integrate Codecov for coverage tracking and visualization:
- **Upload**: coverage.xml from pytest-cov
- **Dashboard**: Coverage trends, file-level reports
- **PR Comments**: Coverage diff on pull requests
- **Thresholds**: Enforce 80% minimum coverage
- **Configuration**: codecov.yml with project/patch targets

**REQ-CICD-003: Branch Protection Rules**

**Phase:** 0.7
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-042, DEF-003

Configure GitHub branch protection for main branch:
- **Required Checks**: All CI jobs must pass
- **Review Requirements**: 1 approving review (if collaborators)
- **Linear History**: Enforce no merge commits
- **Force Push**: Disabled
- **Delete**: Branch deletion disabled
- **Status Checks**: Codecov, all tests, security scans

**Implementation:** Completed 2025-11-07 via PR #2. See docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md for configuration details.

**REQ-CICD-004: Pre-Commit Hooks Infrastructure**

**Phase:** 0.7
**Priority:** High
**Status:** ✅ Complete
**Reference:** DEF-001, CLAUDE.md Section 3

Implement pre-commit hooks framework to auto-fix code issues before each commit:
- **Framework**: pre-commit v4.0.1 with .pre-commit-config.yaml
- **Code Quality Checks**:
  - Ruff linter with auto-fix (--fix, --exit-non-zero-on-fix)
  - Ruff formatter (automatic code formatting)
  - Mypy type checking (staged files only)
- **Security Checks**:
  - Hardcoded credentials scan (blocks commits with secrets)
  - Decimal precision check (Pattern 1 enforcement, blocks float usage)
  - Code review basics (REQ-XXX-NNN traceability, warning only)
- **File Integrity Checks**:
  - Mixed line ending detection and auto-fix (CRLF→LF)
  - Trailing whitespace removal
  - End-of-file newline enforcement
  - Large file check (>500KB blocked)
  - Merge conflict marker detection
  - YAML/JSON syntax validation
  - Python AST validation
  - Debug statement detection (pdb, breakpoint)
- **Performance**: ~2-5 seconds per commit
- **Integration**: Runs automatically on `git commit`, optional bypass with `--no-verify`
- **Benefits**: Catches issues immediately (60-70% reduction in CI failures), faster feedback loop than waiting for CI

**Implementation:** Completed 2025-11-07. Pre-commit hooks installed and configured with 14 checks across 4 categories.

**REQ-CICD-005: Pre-Push Hooks Infrastructure**

**Phase:** 0.7
**Priority:** High
**Status:** ✅ Complete
**Reference:** DEF-002, CLAUDE.md Section 3

Implement pre-push hooks to provide comprehensive validation before code reaches GitHub:
- **Validation Layers** (7 steps, ~60-90 seconds total):
  - Step 0/7: Branch name convention check (blocks push to main)
  - Step 1/7: Quick validation (Ruff + docs via validate_quick.sh, ~3 sec)
  - Step 2/7: Fast unit tests (pytest for config_loader, logger, ~10 sec)
  - Step 3/7: Full type checking (mypy on entire codebase, ~5 sec)
  - Step 4/7: Security scan (Ruff security rules --select S, ~5 sec)
  - Step 5/7: Warning governance (multi-source baseline check via check_warning_debt.py, ~30 sec)
  - Step 6/7: Code quality validation (≥80% coverage, REQ test coverage via validate_code_quality.py, ~20 sec)
  - Step 7/7: Security pattern validation (API auth, hardcoded secrets via validate_security_patterns.py, ~10 sec)
- **Test Coverage**: Enforces ≥80% overall coverage threshold (pre-commit doesn't run tests)
- **Codebase-Wide Validation**: Validates entire codebase, not just changed files
- **Branch Protection**: Blocks direct pushes to main, requires feature/* branch naming
- **Performance**: ~60-90 seconds (acceptable delay since pushes less frequent than commits)
- **Integration**: Runs automatically on `git push`, optional bypass with `--no-verify` (CI will still catch issues)
- **Benefits**: Catches test failures before CI (80-90% reduction in CI failures), validates entire codebase impact

**Implementation:** Completed 2025-11-07. Pre-push hooks installed with 7 comprehensive validation steps including tests, type checking, security scanning, and template enforcement.

**REQ-VALIDATION-004: YAML Configuration Validation**

**Phase:** 1
**Priority:** Medium
**Status:** 🔵 Planned
**Reference:** ADR-052, VALIDATION_LINTING_ARCHITECTURE_V1.0.md

Comprehensive YAML configuration validation with 4 validation levels:
- **Level 1 - Syntax Validation**: Parse all YAML files (7 files in config/) for syntax errors
- **Level 2 - Type Validation**: Ensure Decimal fields use string format (not float)
  - Keywords: price, threshold, limit, kelly, spread, probability, fraction, rate, fee, stop, target, trailing, bid, ask, edge
  - Warn on float contamination: `threshold: 0.75` (float) → should be `threshold: "0.75"` (string)
- **Level 3 - Required Keys**: Validate required keys per file type
  - system.yaml: environment, log_level
  - trading.yaml: max_position_size, max_total_exposure
  - position_management.yaml: stop_loss, profit_target
- **Level 4 - Cross-file Consistency**: Validate references between files (e.g., strategy references valid model)
- **Implementation**: Add to validate_docs.py as Check #9
- **Integration**: validate_quick.sh (~3s), validate_all.sh (~60s), pre-commit hooks, GitHub Actions CI

**REQ-VALIDATION-005: CODE_REVIEW_TEMPLATE Automated Enforcement**

**Phase:** 0.7c
**Priority:** High
**Status:** ✅ Complete
**Reference:** CODE_REVIEW_TEMPLATE_V1.0.md, validate_code_quality.py

Automated enforcement of CODE_REVIEW_TEMPLATE requirements via validate_code_quality.py (314 lines):
- **Check 1 - Module Coverage ≥80%**: Runs pytest with coverage, parses output, fails validation if any module below 80% threshold
  - Scope: All production modules (database/, api_connectors/, trading/, analytics/, utils/, config/)
  - Exclusions: Test files, _archive/, conftest.py, __init__.py
  - Error Message: Lists all modules below 80% with actual percentages and fix instructions
  - Coverage Target: Section 2 (Test Coverage) of CODE_REVIEW_TEMPLATE
- **Check 2 - REQ Test Coverage**: Verifies all requirements with status Complete or In Progress have test coverage
  - Extracts REQ-XXX-NNN from MASTER_REQUIREMENTS with status ✅ Complete or 🟡 In Progress
  - Searches all test files for requirement IDs in comments/docstrings/test names
  - Fails if any Complete/In Progress requirement missing from test content
  - Traceability Target: Section 1 (Requirements Traceability) of CODE_REVIEW_TEMPLATE
- **Check 3 - Educational Docstrings** (WARNING ONLY): Checks staged files for Pattern 7 components
  - Validates Args, Returns, Educational Note sections in docstrings
  - Only checks staged files (not entire codebase) to avoid flagging existing code
  - Non-blocking validation (warning only) - subjective quality metric
  - Code Quality Target: Section 3 (Code Quality) of CODE_REVIEW_TEMPLATE + CLAUDE.md Pattern 7
- **Integration Points**:
  - Pre-push hooks: Step 6/7 (runs before every push, ~20 seconds)
  - CI/CD: GitHub Actions workflow (runs on all PRs)
  - Manual: `python scripts/validate_code_quality.py` (developer testing)
- **Cross-Platform Compatibility**: Uses ASCII output ([PASS]/[FAIL]/[WARN], >=) instead of Unicode (✅/❌/⚠️/≥) for Windows cp1252 compatibility
- **Exit Codes**: 0 = all checks passed, 1 = validation failed (module coverage or REQ coverage violations)
- **Defense in Depth**: Second layer validation (pre-commit checks basics, pre-push enforces coverage thresholds)

**REQ-VALIDATION-006: SECURITY_REVIEW_CHECKLIST Automated Enforcement**

**Phase:** 0.7c
**Priority:** High
**Status:** ✅ Complete
**Reference:** SECURITY_REVIEW_CHECKLIST.md V1.1, validate_security_patterns.py

Automated enforcement of SECURITY_REVIEW_CHECKLIST requirements via validate_security_patterns.py (413 lines):
- **Check 1 - API Authentication**: Verifies API endpoints have authentication decorators
  - Finds @app.route/@router decorators in staged Python files
  - Checks for @require_auth, @login_required, @authenticate, check_auth(), verify_token() patterns
  - Excludes health check endpoints (/health, /ping, /status, /version) - no auth required
  - Fails validation if new API endpoint missing authentication check
  - Security Target: Section 3 (API Security) of SECURITY_REVIEW_CHECKLIST
- **Check 2 - Sensitive Data Encryption** (WARNING ONLY): Verifies database models encrypt sensitive fields
  - Searches for password/token/secret/api_key/private_key/credential column definitions
  - Checks for encryption patterns: EncryptedType, encrypt(), hash(), bcrypt, argon2, PasswordHash
  - Warning only (not blocking) - subjective determination of "needs encryption"
  - Data Protection Target: Section 4 (Data Protection) of SECURITY_REVIEW_CHECKLIST
- **Check 3 - Security Logging** (WARNING ONLY): Verifies exception handlers in auth code use structured logging
  - Finds exception handlers in authentication/authorization/login code
  - Checks for logger.exception(), logger.error(), logger.warning(), logger.critical() calls
  - Warning only (not blocking) - best practice, not security vulnerability
  - Incident Response Target: Section 5 (Incident Response) of SECURITY_REVIEW_CHECKLIST
- **Check 4 - Hardcoded Secrets** (BLOCKS): Scans for hardcoded credentials (defense in depth)
  - Searches for password/secret/api_key/token assignments with string literals
  - Excludes test placeholders (YOUR_, TEST_, EXAMPLE_, PLACEHOLDER, <>, os.getenv)
  - Fails validation on any potential hardcoded secret detected
  - Redundant with pre-commit 'security-credentials' hook (defense in depth)
  - Credential Management Target: Section 1 (Credential Management) of SECURITY_REVIEW_CHECKLIST
- **Integration Points**:
  - Pre-push hooks: Step 7/7 (runs before every push, ~10 seconds)
  - CI/CD: GitHub Actions workflow (runs on all PRs)
  - Manual: `python scripts/validate_security_patterns.py` (developer testing)
- **Cross-Platform Compatibility**: Uses ASCII output ([PASS]/[FAIL]/[WARN]) instead of Unicode for Windows cp1252 compatibility
- **Exit Codes**: 0 = all checks passed, 1 = security violations found (API auth missing or hardcoded secrets)
- **Defense in Depth**: Third layer validation (pre-commit checks credentials, pre-push checks patterns, CI/CD comprehensive scan)

**REQ-VALIDATION-007: SCD Type 2 Query Validation (Pattern 2)**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-094, ADR-095, validate_scd_queries.py, Pattern 2 (Dual Versioning)

Automated validation that ALL queries on SCD Type 2 tables include `row_current_ind = TRUE` filter to prevent historical data bugs:
- **Auto-Discovery**: Queries database schema (information_schema) to discover SCD Type 2 tables (zero maintenance)
- **Query Analysis**: Scans all Python files for SQLAlchemy queries on discovered tables
- **Violation Detection**: Reports queries missing `filter(table.row_current_ind == True)` or `.filter_by(row_current_ind=True)`
- **Excludes Historical Queries**: Allows explicit historical queries with `# Historical query - intentionally includes all versions` comment
- **Actionable Fixes**: Provides exact fix for each violation (e.g., "Add .filter(Markets.row_current_ind == True)")
- **Integration Points**:
  - Pre-push hooks: Step 8/10 (runs before every push, ~15 seconds, parallel execution)
  - CI/CD: GitHub Actions workflow (runs on all PRs)
  - Manual: `python scripts/validate_scd_queries.py` (developer testing)
- **Exit Codes**: 0 = all queries valid, 1 = violations found, 2 = database connection failed (WARNING)
- **Performance**: <15 seconds for full codebase scan (database introspection + file glob)
- **Zero Maintenance**: New SCD Type 2 tables automatically detected (no code changes needed)

**REQ-VALIDATION-008: Property-Based Test Coverage Validation (Pattern 10)**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-094, ADR-095, validate_property_tests.py, Pattern 10 (Property-Based Testing), ADR-074

Automated validation that ALL critical trading logic has Hypothesis property tests covering mathematical invariants:
- **Module Categories**: Trading logic, decimal operations, API parsing (defined in validation_config.yaml)
- **Auto-Discovery**: Uses filesystem glob with multiple naming strategies (nested, flat, variants)
  - Example: analytics/kelly.py → tests/property/analytics/test_kelly_properties.py OR tests/property/test_kelly_criterion_properties.py
- **Hypothesis Detection**: Verifies test files use `@given` decorator and import Hypothesis
- **Property Coverage**: Checks test files cover required properties (e.g., "Kelly fraction in [0, 1] for all inputs")
- **Naming Flexibility**: Supports multiple test file naming conventions (backward compatibility)
- **Integration Points**:
  - Pre-push hooks: Step 9/10 (runs before every push, ~20 seconds, parallel execution)
  - CI/CD: GitHub Actions workflow (runs on all PRs)
  - Manual: `python scripts/validate_property_tests.py` (developer testing)
- **Exit Codes**: 0 = all modules have property tests, 1 = missing/incomplete tests, 2 = config error (WARNING)
- **YAML-Driven**: Property test requirements in validation_config.yaml (add new modules without code changes)
- **Graceful Degradation**: Falls back to defaults if validation_config.yaml missing

**REQ-VALIDATION-009: Test Fixture Validation (Pattern 13)**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-094, ADR-095, validate_test_fixtures.py, Pattern 13 (Real Fixtures Not Mocks)

Automated validation that ALL integration tests use real fixtures (database connections, pools) instead of mocks:
- **Required Fixtures**: Checks integration tests import required fixtures (db_pool, db_cursor, clean_test_data)
- **Forbidden Mocks**: Blocks mocking of infrastructure (ConnectionPool, psycopg2.connect)
- **Pytest Collection**: Uses pytest introspection to collect integration test files
- **Pattern Detection**: Searches test files for mock patterns (`@patch`, `MagicMock`, `mocker.patch`)
- **Actionable Fixes**: Reports exact fixture violations with suggested fixes
- **Integration Points**:
  - Pre-push hooks: Step 10/10 (runs before every push, ~10 seconds, parallel execution)
  - CI/CD: GitHub Actions workflow (runs on all PRs)
  - Manual: `python scripts/validate_test_fixtures.py` (developer testing)
- **Exit Codes**: 0 = all tests use real fixtures, 1 = mock violations found, 2 = pytest collection failed (WARNING)
- **YAML-Driven**: Fixture requirements in validation_config.yaml (extensible for Phase 2+ fixtures)
- **Phase 1.5 Lesson Learned**: Prevents mocking connection pools (discovered during Manager implementation)

**REQ-VALIDATION-010: Phase Start Protocol Automation**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-094, ADR-095, validate_phase_start.py, CLAUDE.md (Phase Task Visibility System)

Automated 3-Step Phase Start Protocol validation to block phase start until ALL prerequisites met:
- **Step 1 - Deferred Tasks**: Auto-discovers PHASE_*_DEFERRED_TASKS*.md documents, finds tasks targeting current phase
- **Step 2 - Phase Dependencies**: Checks DEVELOPMENT_PHASES.md for phase completion markers (✅ Complete)
- **Step 3 - Test Planning**: Verifies "TEST PLANNING CHECKLIST" section exists for phase
- **Step 4 - Coverage Targets**: Validates ALL deliverables have explicit coverage targets in validation_config.yaml
- **Blocking Logic**: Exit code 1 (BLOCKED) if critical prerequisites missing
  - Missing phase deliverables configuration
  - Dependencies not met (previous phases incomplete)
  - Coverage targets undefined for deliverables
- **Warning Logic**: Exit code 0 (PASS with warnings) if non-critical issues found
  - Deferred tasks targeting current phase (address before implementation)
  - Test planning checklist missing (RECOMMENDED but not blocking)
- **Integration Points**:
  - Manual: `python scripts/validate_phase_start.py --phase 1.5` (run at start of EVERY phase)
  - DEVELOPMENT_PHASES.md: "BEFORE STARTING - RUN PHASE START VALIDATION" section for all 6 phases
- **Exit Codes**: 0 = safe to start phase, 1 = BLOCKED (fix issues first), 2 = config error (WARNING)
- **YAML-Driven**: Phase deliverables and coverage targets in validation_config.yaml
- **Purpose**: Prevents "task blindness" - ensures deferred tasks and test planning not forgotten

**REQ-VALIDATION-011: Phase Completion Protocol Automation**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-094, ADR-095, validate_phase_completion.py, PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md

Automated validation for Steps 1, 5, and 9 of 10-Step Phase Completion Protocol:
- **Step 1 - Deliverable Completeness**: Validates ALL deliverables meet tier-specific coverage targets
  - Loads phase deliverables from validation_config.yaml
  - Checks each deliverable's coverage against its target (e.g., Kalshi API Client: 93.19% vs. 90% target)
  - Fails if ANY deliverable below target
- **Step 5 - Testing & Validation**: Runs full test suite with coverage measurement
  - Executes pytest with coverage reporting
  - Validates total coverage meets threshold (80%+)
  - Reports stats (tests passed/failed, coverage percentage)
- **Step 9 - Security Review**: Automated hardcoded credentials scan
  - Searches for password/secret/api_key assignments with string literals
  - Excludes test placeholders (YOUR_, TEST_, EXAMPLE_)
  - Fails if ANY hardcoded credentials found
- **Manual Steps Checklist**: Provides checklist for 7 manual steps (Steps 2-4, 6-8, 10)
  - Step 2: Internal Consistency (5 min)
  - Step 3: Dependency Verification (5 min)
  - Step 4: Quality Standards (5 min)
  - Step 6: Gaps & Risks + Deferred Tasks (2 min)
  - Step 7: AI Code Review Analysis (10 min)
  - Step 8: Archive & Version Management (5 min)
  - Step 10: Performance Profiling (Phase 5+ only)
- **Integration Points**:
  - Manual: `python scripts/validate_phase_completion.py --phase 1.5` (run at END of every phase)
- **Exit Codes**: 0 = automated steps passed, 1 = violations found (fails phase completion)
- **Purpose**: Automates 30% of Phase Completion Protocol (Steps 1, 5, 9), provides checklist for remaining 70%

**REQ-VALIDATION-012: Configuration Synchronization Validation (Pattern 8)**

**Phase:** 1.5
**Priority:** High
**Status:** ✅ Complete
**Reference:** ADR-094, ADR-095, validate_docs.py (Check #10), Pattern 8 (Configuration Synchronization)

Automated validation that configuration changes synchronized across ALL 4 layers:
- **Layer 1 - Tool Configs**: pyproject.toml, ruff.toml, .pre-commit-config.yaml
- **Layer 2 - Application Configs**: src/precog/config/*.yaml (7 config files)
- **Layer 3 - Documentation**: CONFIGURATION_GUIDE, DEVELOPMENT_PATTERNS (code examples)
- **Layer 4 - Infrastructure**: Terraform configs (Phase 5+)
- **Float Contamination Detection**: Checks YAML files for float values in Decimal fields
  - Decimal keywords: edge, kelly, spread, probability, threshold, price
  - Invalid pattern: `min_edge: 0.05` (float)
  - Valid pattern: `min_edge: "0.05"` (string, parsed as Decimal)
- **Documentation Example Validation**: Scans documentation for YAML code blocks with float contamination
  - Reports: "CONFIGURATION_GUIDE_V3.1.md: Documentation example uses float (should be string)"
  - Actionable fix: "Change threshold: X.XX to threshold: \"X.XX\" in code block N"
- **Tool Migration Detection**: Detects orphaned config sections (e.g., [tool.bandit] after migration to Ruff)
- **Integration Points**:
  - Pre-commit hooks: validate_docs.py Check #10 (runs on every commit, ~2-5 seconds)
  - CI/CD: GitHub Actions workflow (runs on all PRs)
  - Manual: `python scripts/validate_docs.py` (developer testing)
- **Exit Codes**: 0 = all layers synchronized (warnings allowed), 1 = critical drift found
- **YAML-Driven**: Config layer patterns in validation_config.yaml (4 layers defined)
- **Phase 0.7c Lesson Learned**: Bandit → Ruff migration left orphaned [tool.bandit] in pyproject.toml (200+ errors)

**REQ-API-007: API Response Validation with Pydantic**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned
**Reference:** ADR-047, API_INTEGRATION_GUIDE_V2.0.md

Runtime validation of all API responses using Pydantic BaseModel:
- **Automatic Type Conversion**: Float → Decimal for all price fields (*_dollars)
- **Field Validation**: Enforce ranges (prices: 0.0001-0.9999, volumes/open_interest: >= 0)
- **Business Rule Enforcement**: Validate bid < ask, spread >= min_spread
- **Clear Error Messages**: Pydantic provides detailed validation errors with field names
- **Implementation**:
  - Define models in `api_connectors/kalshi_models.py`
  - Use @validator decorators for Decimal conversion
  - Return validated models from all API client methods
- **Coverage Target**: 100% for model validation (critical path)
- **Benefits**: Catches type errors at API boundary, eliminates float contamination, serves as API contract documentation

**REQ-OBSERV-001: Request Correlation IDs (B3 Standard)**

**Phase:** 1
**Priority:** Medium
**Status:** 🔵 Planned
**Reference:** ADR-049, API_INTEGRATION_GUIDE_V2.0.md

Implement distributed request tracing with B3 correlation ID propagation:
- **Standard**: B3 spec (OpenTelemetry/Zipkin compatible)
- **Format**: UUID4 generated at request entry point
- **Propagation**: X-Request-ID header in all API calls
- **Logging**: Include request_id in every log entry (API calls, DB queries, business logic)
- **Use Cases**:
  - Debug distributed systems: trace API → Database → async task operations
  - Performance analysis: track request latency across components
  - Correlate errors: filter logs by request_id to see entire request lifecycle
- **Implementation**:
  - Generate UUID4 at CLI command or scheduled task entry
  - Pass request_id parameter through all method calls
  - Configure structlog to always include request_id field
- **Future**: Migrate to full OpenTelemetry with trace/span IDs (Phase 3+)

**REQ-OBSERV-002: Production Error Tracking with Sentry**

**Phase:** 2
**Priority:** High
**Status:** 🔵 Planned
**Reference:** ADR-TBD, SENTRY_INTEGRATION_GUIDE_V1.0.md (future)

Implement real-time production error tracking, crash reporting, and performance monitoring using Sentry:

- **Error Tracking**:
  - Automatic exception capture with full stack traces and local variables
  - User context (if applicable), environment tags (production/staging/dev)
  - Breadcrumbs: Last 100 events leading to error (API calls, DB queries, function calls)
  - Error grouping by fingerprint, deduplication of identical errors
  - Release tracking: Tag errors by deployment version (precog@X.Y.Z)

- **Performance Monitoring (APM)**:
  - Transaction tracing: Measure latency of API endpoints, trade execution, position updates
  - Database query performance: Identify slow queries (>500ms threshold)
  - External API calls: Track Kalshi, ESPN, Balldontlie response times
  - Custom instrumentation: Measure edge calculation, Kelly sizing, exit evaluation

- **Structured Logging Integration (2025 feature)**:
  - Send structlog events to Sentry (ERROR and above)
  - Search logs by strategy_id, ticker, trade_id
  - Log-based alerts (e.g., "Alert when quantity > 1000")

- **Alerting**:
  - Real-time alerts for error rate spikes (>10 errors/minute)
  - Slow transaction alerts (>5s response time)
  - New error type alerts (never seen before)
  - Slack/Email/PagerDuty integration

- **Integration with Existing Observability**:
  - Use B3 correlation IDs from REQ-OBSERV-001 for distributed tracing
  - Respect log masking from REQ-SEC-009 (sensitive data already masked)
  - Complement Codecov (pre-release) with post-release monitoring
  - Shows untested code causing production errors (Codecov integration)

- **Implementation**:
  - Add sentry-sdk to requirements.txt
  - Initialize Sentry in main.py entry point
  - Configure SENTRY_DSN in .env (excluded from git)
  - Set release tag: `sentry_sdk.init(release="precog@{version}")`
  - Add custom context: strategy_id, model_id, trade_id
  - Configure sampling rates: 100% errors, 10% transactions (free tier)

- **Success Criteria**:
  - <500ms performance overhead (measured with APM)
  - <5K errors/month (free tier limit)
  - <10K transactions/month (free tier limit)
  - 100% of production errors captured and alerted within 60 seconds

- **Cost**:
  - Free tier: 5K errors/month, 10K transactions/month (sufficient for Phase 0-2)
  - Paid tier: $29/month if exceeding free tier (likely Phase 5+ with live trading)

- **Benefits**:
  - Real-time visibility into production issues
  - Faster debugging with full error context
  - Performance regression detection
  - Proactive alerting (catch issues before users report)
  - Integration with Codecov: See which untested code is causing errors

**REQ-SEC-009: Sensitive Data Masking in Logs**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned
**Reference:** ADR-051, SECURITY_REVIEW_CHECKLIST.md

Automatic masking of sensitive data in all log output for GDPR/PCI compliance:
- **Sensitive Keywords**: api_key, token, password, private_key, secret, api_secret, access_token, refresh_token, bearer_token, authorization, auth, credentials
- **Pattern Matching**: Detect and mask sensitive patterns in strings (e.g., "Bearer <token>", "api_key=<value>")
- **Masking Strategy**: Show first 4 + last 4 characters for debugging (e.g., "sk_li...xyz9"), or "***REDACTED***" for short values
- **Implementation**:
  - Add structlog processor `mask_sensitive_data()`
  - Process BEFORE JSONRenderer output
  - Test masking with unit tests (verify no credentials in output)
- **Compliance**: Required for GDPR (data privacy), PCI-DSS (payment card data), SOC 2 (security controls)
- **Benefits**: Defense-in-depth (even if log aggregation compromised, credentials are masked), automatic (can't forget to mask), debugging-friendly (shows partial data)

---

## 8. Error Handling & Logging

### 8.1 Error Categories

**REQ-SYS-006: Structured Logging**

**Phase:** 1
**Priority:** Medium
**Status:** 🔵 Planned

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

**Implementation details**: See `API_INTEGRATION_GUIDE.md` (retry logic), `utils/logger.py`, `utils/decimal_helpers.py`, `VERSIONING_GUIDE_V1.0.md` (error handling)

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

**REQ-RISK-001: Circuit Breakers (5 consecutive losses)**

**Phase:** 1
**Priority:** Critical
**Status:** 🔵 Planned

**REQ-RISK-002: Daily Loss Limit**

**Phase:** 1
**Priority:** Critical
**Status:** 🔵 Planned

**REQ-RISK-003: Max Open Positions**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned

**REQ-RISK-004: Max Position Size**

**Phase:** 1
**Priority:** High
**Status:** 🔵 Planned

**REQ-RISK-005: Stop Loss -15%**

**Phase:** 5
**Priority:** Critical
**Status:** ✅ Complete (Documented)

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

**Detailed risk formulas**: See `EDGE_DETECTION_SPEC.md` (Kelly Criterion, exposure calculations with DECIMAL), `TRAILING_STOP_GUIDE_V1.0.md` (stop loss calculations)

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
3. **VERSIONING_GUIDE_V1.0.md** - Strategy and model versioning patterns
4. **REQUIREMENT_INDEX.md** - Systematic requirement catalog (NEW in V2.6)
5. **ADR_INDEX.md** - Architecture decision index (NEW in V2.6)

**Reference Documentation:**
6. `API_INTEGRATION_GUIDE.md` - Detailed API specifications
7. `DATABASE_SCHEMA_SUMMARY_V1.11.md` - Full schema with versioning tables
8. `EDGE_DETECTION_SPEC.md` - Mathematical formulas
9. `CONFIGURATION_GUIDE.md` - YAML configuration reference (includes versioning configs)
10. `ARCHITECTURE_DECISIONS.md` - Design rationale and trade-offs

**Development Guides:**
11. `TESTING_GUIDE.md` - Test cases and fixtures
12. `DEPLOYMENT_GUIDE.md` - Setup and deployment
13. `ENVIRONMENT_CHECKLIST.md` - Windows 11 setup guide
14. `TRAILING_STOP_GUIDE_V1.0.md` - Trailing stop loss implementation
15. `POSITION_MANAGEMENT_GUIDE_V1.0.md` - Enhanced position management
16. `PHASE_1.5_PLAN.md` - Foundation validation plan

**Phase 10 Documentation:**
17. `POLYMARKET_INTEGRATION_GUIDE.md` - Multi-platform strategy
18. `PLATFORM_ABSTRACTION_DESIGN.md` - Architecture for multiple platforms

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

### ⚠️ Versioning (ALWAYS)
1. Strategy and model configs are IMMUTABLE once created
2. To change config: Create new version (v1.0 → v1.1)
3. Only status and metrics update in-place
4. ALWAYS link trades to strategy_id and model_id
5. Use semantic versioning (major.minor: v1.0, v1.1, v2.0)
6. Test version immutability in unit tests
7. Reference VERSIONING_GUIDE_V1.0.md for patterns

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

### ⚠️ Requirement Traceability (NEW in V2.6)
1. Reference requirements using REQ IDs (e.g., REQ-MON-001)
2. See REQUIREMENT_INDEX.md for complete requirement catalog
3. Use REQ IDs in code comments, commit messages, and documentation
4. Link implementation to specific requirements for traceability

---

## 14. Contact & Support

**Project Lead**: [Your Name]
**Development Team**: [Team Members]
**Repository**: [GitHub URL when available]

For questions or issues:
1. Check supplementary docs in `docs/` folder
2. Review KALSHI_DECIMAL_PRICING_CHEAT_SHEET.md for pricing issues
3. Review VERSIONING_GUIDE_V1.0.md for versioning questions
4. Review REQUIREMENT_INDEX.md for requirement details
5. Review test cases for implementation examples
6. Submit GitHub issues for bugs or feature requests

---

## 15. Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.9 | 2025-10-08 | Initial draft (Session 5) |
| 2.0 | 2025-10-09 | Added decimal pricing, Phase 10 (Polymarket), updated tech stack, multi-platform architecture |
| 2.2 | 2025-10-16 | Updated terminology (odds → probability); renamed odds_models.yaml → probability_models.yaml; clarified probability vs. market price; updated table names (odds_matrices → probability_matrices) |
| 2.3 | 2025-10-16 | Updated environment variable names to match env.template; updated directory structure (data_storers/ → database/) |
| 2.4 | 2025-10-19 | **MAJOR UPDATE**: Added Phase 0.5 (Foundation Enhancement); added versioning requirements (strategies, probability_models with immutable pattern); added trailing stop loss requirements; updated database overview to V1.4; added Phase 1.5 (Foundation Validation); updated all phase descriptions to reflect versioning enhancements |
| 2.5 | 2025-10-21 | **CRITICAL UPDATE**: Added Phase 5 monitoring and exit management requirements; Added REQ-MON-*, REQ-EXIT-*, REQ-EXEC-* requirements; Updated database to V1.5 (position_exits, exit_attempts tables); Added 10 exit conditions with priority hierarchy |
| 2.6 | 2025-10-22 | **STANDARDIZATION**: Added systematic REQ IDs to all requirements; Added REQUIREMENT_INDEX.md and ADR_INDEX.md references; Improved requirement traceability |

---

**NEXT**: Update ARCHITECTURE_DECISIONS V2.4 → V2.5 with ADR numbers

---

**END OF MASTER REQUIREMENTS V2.6**
