# Requirement Index

---
**Version:** 1.14
**Last Updated:** 2025-12-07
**Status:** ✅ Current
**Purpose:** Master index of all system requirements with systematic IDs
**Changes in v1.14:**
- **BASEPOLLER UNIFIED DESIGN PATTERN**: Added REQ-SCHED-003 for BasePoller abstract class
- **REQ-SCHED-003**: BasePoller with Template Method pattern, {Platform}{Entity}Poller naming, generic stats
- Updated MASTER_REQUIREMENTS reference to V2.22
- Updated requirement statistics (127 → 128 total requirements)
**Changes in v1.13:**
- **PHASE 2.5 SCHEDULER REQUIREMENTS ADDED**: Added REQ-SCHED-001, REQ-SCHED-002, REQ-OBSERV-003 for live data collection
- **REQ-SCHED-001**: APScheduler-based Live Data Polling (ESPN MarketUpdater + Kalshi polling)
- **REQ-SCHED-002**: Service Supervisor Pattern (Multi-service orchestration with health monitoring)
- **REQ-OBSERV-003**: Log Aggregation with CloudWatch/ELK (Deferred to Phase 4)
- **NEW CATEGORY**: SCHED (Scheduler) - APScheduler-based service orchestration
- Updated MASTER_REQUIREMENTS reference to V2.21
- Updated requirement statistics (124 → 127 total requirements)
**Changes in v1.12:**
- **REQ-TEST-020 ADDED**: CI-Safe Stress Test Requirements (Issue #168)
- **PROBLEM**: Stress tests using ThreadPoolExecutor hang indefinitely in CI
- **SOLUTION**: Use `skipif(_is_ci)` to skip stress tests in resource-constrained CI environments
- **CROSS-REFS**: ADR-099 (skipif vs xfail decision), Pattern 28 (DEVELOPMENT_PATTERNS_V1.19)
- Updated MASTER_REQUIREMENTS reference to V2.20
**Changes in v1.11:**
- **REQ-SEC-009 COMPLETION**: Marked Sensitive Data Masking in Logs as ✅ Complete
- **IMPLEMENTATION DETAILS**: Added structlog processor `mask_sensitive_data()` in logger.py
  - Masks API keys, tokens, passwords: `abc123-secret` → `abc***ret`
  - Sanitizes connection strings: `postgres://user:pass@host` → `postgres://user:****@host`
  - Sanitizes exception messages containing credentials
  - GDPR/PCI-DSS compliance achieved
- **TEST VALIDATION**: 9 tests in tests/security/test_credential_masking.py (all passing)
- Updated requirement statistics (27 → 28 requirements complete)
**Changes in v1.10:**
- **PHASE 1 COMPLETION UPDATE**: Marked 12 implemented requirements as ✅ Complete
- **API REQUIREMENTS**: REQ-API-001, REQ-API-002, REQ-API-005, REQ-API-006 → ✅ (Kalshi client, auth, rate limiting, error handling implemented)
- **CLI REQUIREMENTS**: REQ-CLI-001 through REQ-CLI-005 → ✅ (Typer framework + all 5 commands implemented)
- **DATABASE REQUIREMENTS**: REQ-DB-008 → ✅ (Connection pooling in connection.py)
- **SYSTEM REQUIREMENTS**: REQ-SYS-006 → ✅ (Structured logging with structlog)
- **TESTING REQUIREMENTS**: REQ-TEST-001, REQ-TEST-002, REQ-TEST-003 → ✅ (87% coverage, unit tests, integration tests)
- Updated requirement statistics (Phase 1 completion progress: 12 requirements marked complete)
**Changes in v1.9:**
- **LIVE DATA MANAGEMENT REQUIREMENTS (PHASE 2)**: Added REQ-DATA-001 through REQ-DATA-005 (5 comprehensive live data requirements)
- **NEW CATEGORY**: DATA (Live Data Management) - Game states, venues, multi-sport support, rankings, JSONB situation data
- **SCD TYPE 2 VERSIONING**: REQ-DATA-001 implements SCD Type 2 for game state history (~1.8M records/year)
- **MULTI-SPORT SUPPORT**: REQ-DATA-003 covers 6 leagues (NFL, NCAAF, NBA, NCAAB, NHL, WNBA)
- **CROSS-REFERENCES**: ADR-029, ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md, Migrations 026-029
- Updated document references to V2.19
- Updated requirement statistics (119 → 124 total requirements)
**Changes in v1.8:**
- **WORKFLOW ENFORCEMENT INFRASTRUCTURE (PHASE 1.5)**: Added REQ-VALIDATION-007 through REQ-VALIDATION-012 (6 comprehensive workflow enforcement requirements)
- **PATTERN ENFORCEMENT**: Requirements enforce Pattern 2 (SCD Type 2 queries), Pattern 8 (Config Sync), Pattern 10 (Property-Based Testing), Pattern 13 (Test Coverage Quality)
- **PHASE START/COMPLETION AUTOMATION**: REQ-VALIDATION-010 (Phase Start Protocol), REQ-VALIDATION-011 (Phase Completion Protocol) automate 3-step and 10-step assessment workflows
- **VALIDATOR ARCHITECTURE**: All validators use YAML-driven configuration (validation_config.yaml), auto-discovery pattern (database introspection, filesystem glob), graceful degradation
- **GIT HOOK INTEGRATION**: Pre-push hook Steps 8-10 (SCD queries ~15s, Property tests ~20s, Test fixtures ~10s) run in parallel with existing steps
- **CROSS-REFERENCES**: References ADR-094 (YAML-Driven Validation), ADR-095 (Auto-Discovery Pattern), ADR-096 (Parallel Execution), ADR-097 (Tier-Specific Coverage)
- Updated document references to V2.18
- Updated requirement statistics (113 → 119 total requirements)
**Changes in v1.7:**
- **RETROACTIVE REQUIREMENTS CREATION**: Added REQ-CICD-004 (Pre-Commit Hooks) and REQ-CICD-005 (Pre-Push Hooks)
- **TRACEABILITY GAP FIX**: Critical infrastructure implemented without formal requirements (DEF-001, DEF-002) now have proper REQ-CICD-* traceability
- **CONSISTENCY ENFORCEMENT**: Updated REQ-CICD-003 status from 🔵 Planned → ✅ Complete (completed 2025-11-07)
- Updated CI/CD section summary to reflect all Phase 0.7 infrastructure completion
- Updated document references to V2.15
- Updated requirement statistics (111 → 113 total requirements)
**Changes in v1.6:**
- **PRODUCTION MONITORING INFRASTRUCTURE**: Added Sentry production error tracking requirement
- **NEW REQUIREMENT**: REQ-OBSERV-002 (Sentry for real-time error tracking with hybrid architecture)
- Updated document references from V2.13 to V2.14
- Updated requirement statistics (110 → 111 total requirements)
- Enhanced Observability section summary to explain hybrid architecture (logger.py + Sentry + alerts table)
**Changes in v1.5:**
- **PHASES 6-9 ANALYTICS INFRASTRUCTURE**: Added analytics and reporting requirements
- **NEW CATEGORIES**: ANALYTICS (Analytics infrastructure), REPORTING (Dashboards and reporting)
- **NEW REQUIREMENTS**: REQ-ANALYTICS-001 through REQ-ANALYTICS-004 (materialized views, refresh automation), REQ-REPORTING-001 (dashboard architecture)
- Updated document references from V2.12 to V2.13
- Updated requirement statistics (105 → 110 total requirements)
- Added Analytics and Reporting sections for Phase 6-9 infrastructure
**Changes in v1.4:**
- **PHASE 0.7C COMPLETION**: Added template enforcement automation requirements
- **NEW REQUIREMENTS**: REQ-VALIDATION-005 (CODE_REVIEW_TEMPLATE enforcement), REQ-VALIDATION-006 (SECURITY_REVIEW_CHECKLIST enforcement)
- Updated document references from V2.10 to V2.12
- Updated requirement statistics (103 → 105 total requirements)
- Updated Validation section summary to include Phase 0.7c completion
**Changes in v1.3:**
- **PHASE 1 API BEST PRACTICES**: Added 4 new requirements for API integration best practices
- **NEW REQUIREMENTS**: REQ-API-007 (Pydantic validation), REQ-OBSERV-001 (correlation IDs), REQ-SEC-009 (log masking), REQ-VALIDATION-004 (YAML validation)
- **NEW CATEGORIES**: OBSERV (Observability), SEC (Security)
- Updated document references from V2.9 to V2.10
- Updated requirement statistics (99 → 103 total requirements)
**Changes in v1.2:**
- **PHASE 0.6C COMPLETION**: Added validation and testing requirements (REQ-TEST-005, REQ-VALIDATION-001-003)
- **PHASE 0.7 PLANNING**: Added CI/CD and advanced testing requirements (REQ-TEST-006-008, REQ-CICD-001-003)
- Added new categories: VALIDATION (Code Quality & Documentation), CICD (Continuous Integration/Deployment)
- Updated document references from V2.7 to V2.9
- Updated requirement statistics (89 → 99 total requirements)
**Changes in v1.1:**
- Added Trading Methods requirements (REQ-METH-001 through REQ-METH-015)
- Added Alerts & Monitoring requirements (REQ-ALERT-001 through REQ-ALERT-015)
- Added Machine Learning requirements (REQ-ML-001 through REQ-ML-004)
- Updated document references from V2.5 to V2.7
- Updated requirement statistics (55 → 89 total requirements)
---

## Overview

This document provides a systematic index of all Precog requirements using category-based IDs (REQ-{CATEGORY}-{NUMBER}).

**Status Key:**
- ✅ Complete - Implemented and verified
- 🔵 Planned - Specified, not yet implemented
- 📝 Draft - Being defined

---

## Requirement Categories

| Category | Code | Description | Phase |
|----------|------|-------------|-------|
| System | SYS | System-level requirements (database, config, logging) | 0-0.5 |
| API | API | API integration requirements | 1-2 |
| CLI | CLI | Command-line interface requirements | 1 |
| Database | DB | Database schema and data requirements | 0-0.5 |
| Monitoring | MON | Position monitoring requirements | 5 |
| Exit | EXIT | Exit management requirements | 5 |
| Execution | EXEC | Order execution requirements | 5 |
| Versioning | VER | Strategy/model versioning requirements | 0.5, 4 |
| Trailing | TRAIL | Trailing stop requirements | 0.5, 5 |
| Kelly | KELLY | Kelly criterion / position sizing | 1-5 |
| Risk | RISK | Risk management requirements | 1-10 |
| Methods | METH | Trading methods bundling (strategy+model+config) | 4-5 |
| Alerts | ALERT | Alert and notification system requirements | 1 |
| Machine Learning | ML | ML infrastructure and model development | 1-9 |
| Testing | TEST | Testing and validation requirements | 1-10 |
| Performance | PERF | Performance requirements | 1-10 |
| Validation | VALIDATION | Code quality and documentation validation | 0.6c-1 |
| CI/CD | CICD | Continuous integration and deployment | 0.7 |
| Observability | OBSERV | Request tracing and distributed system observability | 1 |
| Security | SEC | Security and compliance requirements | 1-10 |
| Analytics | ANALYTICS | Analytics infrastructure (materialized views, performance tracking) | 6-9 |
| Reporting | REPORTING | Dashboards, reports, and data visualization | 7-9 |
| Data | DATA | Live data management (game states, venues, rankings) | 2 |
| Scheduler | SCHED | APScheduler-based service orchestration and polling | 2-2.5 |

---

## System Requirements (SYS)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-SYS-001 | Database Schema Versioning | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-SYS-002 | Configuration Management (YAML) | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-SYS-003 | Decimal Precision for Prices | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-SYS-006 | Structured Logging | 1 | Medium | ✅ | MASTER_REQUIREMENTS_V2.9 |

**Note:** System Uptime and Data Latency requirements are tracked as REQ-PERF-001 and REQ-PERF-002 in the Performance section.

---

## API Requirements (API)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-API-001 | Kalshi API Integration | 1 | Critical | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-API-002 | RSA-PSS Authentication (Kalshi) | 1 | Critical | ✅ | API_INTEGRATION_GUIDE_V1.0 |
| REQ-API-003 | ESPN API Integration | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-API-004 | Balldontlie API Integration | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-API-005 | API Rate Limit Management | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-API-006 | API Error Handling | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-API-007 | API Response Validation with Pydantic | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |

---

## CLI Requirements (CLI)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-CLI-001 | CLI Framework with Typer | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-002 | Balance Fetch Command | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-003 | Positions Fetch Command | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-004 | Fills Fetch Command | 1 | Medium | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-005 | Settlements Fetch Command | 1 | Medium | ✅ | MASTER_REQUIREMENTS_V2.9 |

---

## Database Requirements (DB)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-DB-001 | PostgreSQL 15+ Database | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-DB-002 | SCD Type 2 Versioning Pattern | 0 | Critical | ✅ | DATABASE_SCHEMA_SUMMARY_V1.5 |
| REQ-DB-003 | DECIMAL(10,4) for Prices/Probabilities | 0 | Critical | ✅ | DATABASE_SCHEMA_SUMMARY_V1.5 |
| REQ-DB-004 | position_exits Table | 0.5 | Critical | ✅ | DATABASE_SCHEMA_SUMMARY_V1.5 |
| REQ-DB-005 | exit_attempts Table | 0.5 | Critical | ✅ | DATABASE_SCHEMA_SUMMARY_V1.5 |
| REQ-DB-006 | Foreign Key Constraints | 0 | High | ✅ | DATABASE_SCHEMA_SUMMARY_V1.5 |
| REQ-DB-007 | CHECK Constraints for Enums | 0 | High | ✅ | DATABASE_SCHEMA_SUMMARY_V1.5 |
| REQ-DB-008 | Database Connection Pooling | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-DB-015 | Strategy Type Lookup Table | 1.5 | High | ✅ | MASTER_REQUIREMENTS_V2.17 |
| REQ-DB-016 | Model Class Lookup Table | 1.5 | High | ✅ | MASTER_REQUIREMENTS_V2.17 |

---

## Data Requirements (DATA)

**Overview:** Live game data collection, storage, and versioning for multi-sport prediction markets. Implements SCD Type 2 for complete game history and JSONB for sport-specific situation data.

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-DATA-001 | Game State Data Collection (SCD Type 2 Versioning) | 2 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.22 |
| REQ-DATA-002 | Venue Data Management (Normalized Table) | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.22 |
| REQ-DATA-003 | Multi-Sport Support (6 Leagues) | 2 | Critical | 🟡 | MASTER_REQUIREMENTS_V2.22 |
| REQ-DATA-004 | Team Rankings Storage (Temporal Validity) | 2 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.22 |
| REQ-DATA-005 | JSONB Situation Data (Sport-Specific Fields) | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.22 |

**Details:**

**REQ-DATA-001: Game State Data Collection**
- SCD Type 2 versioning: row_current_ind, row_start_timestamp, row_end_timestamp
- New row created on ANY score/period/status change
- Enables complete game timeline reconstruction for backtesting
- Performance: 30-60s collection frequency, <100ms insert, <50ms query
- Storage: ~1.8M records/year across 6 sports (~900 MB)
- Related: ADR-029 (ESPN Data Model), Migration 029 (game_states table)

**REQ-DATA-002: Venue Data Management**
- Normalized venues table with ESPN venue ID linkage
- Fields: venue_id, espn_venue_id, venue_name, city, state, capacity, indoor
- Benefits: Eliminates duplication, enables venue analytics, weather integration
- Storage: ~150 unique venues (<1 MB)
- Related: ADR-029, Migration 026 (venues table)

**REQ-DATA-003: Multi-Sport Support**
- 6 leagues: NFL (~285 games), NCAAF (~800), NBA (~1,350), NCAAB (~5,500), NHL (~1,350), WNBA (~200)
- Unified game_states table (no separate tables per sport)
- Sport-specific data in JSONB situation field
- Teams table extended with sport/league columns
- Status: ESPN client endpoints ✅ Complete, database schema 🔵 Pending
- Total: ~9,485 games/year, ~1.8M game state records/year (~1.1 GB/year)
- Related: ADR-029, ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md

**REQ-DATA-004: Team Rankings Storage**
- Ranking types: AP Poll, Coaches Poll, CFP, ESPN Power Index, ESPN BPI
- Temporal validity: season, week (NULL for preseason/final), ranking_date
- Uniqueness: (team_id, ranking_type, season, week)
- Use cases: Ranked matchup detection, ranking momentum, model features
- Storage: ~50,000 records/year (~5 MB)
- Related: ADR-029, Migration 027 (team_rankings table)

**REQ-DATA-005: JSONB Situation Data**
- Avoids 30+ nullable columns for sport-specific fields
- Football: possession, down, distance, yard_line, is_red_zone, turnovers, timeouts
- Basketball: possession, fouls, timeouts, bonus, possession_arrow
- Hockey: powerplay status, shots, saves
- GIN index on situation field for flexible queries
- TypedDict: ESPNSituationData in espn_client.py for compile-time safety
- Related: ADR-029, ESPN_DATA_MODEL_IMPLEMENTATION_PLAN_V1.0.md

---

## Monitoring Requirements (MON)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-MON-001 | Dynamic Monitoring Frequencies | 5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-MON-002 | Position State Tracking | 5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-MON-003 | Urgent Condition Detection | 5 | High | ✅ | POSITION_MANAGEMENT_GUIDE |
| REQ-MON-004 | Price Caching (10s TTL) | 5 | Medium | ✅ | POSITION_MANAGEMENT_GUIDE |
| REQ-MON-005 | API Rate Management (60/min) | 5 | High | ✅ | POSITION_MANAGEMENT_GUIDE |

**Details:**

**REQ-MON-001: Dynamic Monitoring Frequencies**
- Normal frequency: 30 seconds
- Urgent frequency: 5 seconds (when within 2% of thresholds)
- Acceptance Criteria:
  - Monitor positions every 30s by default
  - Switch to 5s when urgent conditions detected
  - Price updates reflected in `positions.current_price`

**REQ-MON-002: Position State Tracking**
- Track current_price, unrealized_pnl_pct, last_update
- Acceptance Criteria:
  - `positions.current_price` updated every monitoring cycle
  - `positions.unrealized_pnl_pct` calculated as (current_price - entry_price) / entry_price
  - `positions.last_update` timestamp tracked
  - Alert if last_update > 60 seconds stale

---

## Exit Management Requirements (EXIT)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-EXIT-001 | Exit Priority Hierarchy | 5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-EXIT-002 | 10 Exit Conditions | 5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-EXIT-003 | Partial Exit Staging | 5 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-EXIT-004 | Exit Attempt Logging | 5 | High | ✅ | POSITION_MANAGEMENT_GUIDE |
| REQ-EXIT-005 | Exit Performance Tracking | 5 | Medium | ✅ | POSITION_MANAGEMENT_GUIDE |

**Details:**

**REQ-EXIT-001: Exit Priority Hierarchy**
- 4 priority levels: CRITICAL, HIGH, MEDIUM, LOW
- Acceptance Criteria:
  - Each exit condition assigned a priority
  - Priority determines execution strategy
  - Higher priority = more aggressive execution

**REQ-EXIT-002: 10 Exit Conditions**
- stop_loss (CRITICAL), circuit_breaker (CRITICAL)
- trailing_stop (HIGH), time_based_urgent (HIGH), liquidity_dried_up (HIGH)
- profit_target (MEDIUM), partial_exit_target (MEDIUM)
- early_exit (LOW), edge_disappeared (LOW), rebalance (LOW)
- Acceptance Criteria:
  - All 10 conditions implemented
  - Conditions evaluated every monitoring cycle
  - Exit triggers logged to position_exits table

**REQ-EXIT-003: Partial Exit Staging**
- Stage 1: 50% @ +15% profit
- Stage 2: 25% @ +25% profit
- Remaining: 25% rides with trailing stop
- Acceptance Criteria:
  - Multiple exit events per position supported
  - Each partial exit logged separately
  - Position quantity decremented correctly

---

## Execution Requirements (EXEC)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-EXEC-001 | Urgency-Based Execution | 5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-EXEC-002 | Price Walking Algorithm | 5 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-EXEC-003 | Exit Attempt Logging | 5 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-EXEC-004 | Order Timeout Management | 5 | High | ✅ | POSITION_MANAGEMENT_GUIDE |
| REQ-EXEC-005 | Execution Success >95% | 5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |

**Details:**

**REQ-EXEC-001: Urgency-Based Execution**
- CRITICAL: Market orders, 5s timeout
- HIGH: Aggressive limits, 10s timeout, walk 2x then market
- MEDIUM: Fair limits, 30s timeout, walk up to 5x
- LOW: Conservative limits, 60s timeout, walk up to 10x
- Acceptance Criteria:
  - Execution strategy selected by priority level
  - Timeouts enforced
  - Fallback to market orders when needed

**REQ-EXEC-002: Price Walking Algorithm**
- Start with limit order at initial price
- Walk price by $0.01 toward market if not filled
- Max walks determined by priority level
- Acceptance Criteria:
  - Each walk attempt logged to exit_attempts
  - Price walks correctly toward market
  - Max walks respected

**REQ-EXEC-003: Exit Attempt Logging**
- Log all exit order attempts to exit_attempts table
- Track: attempt_number, order_type, limit_price, fill_price, success
- Acceptance Criteria:
  - Every order attempt logged
  - Success/failure tracked
  - Enables "Why didn't my exit fill?" debugging

---

## Versioning Requirements (VER)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-VER-001 | Immutable Version Configs | 0.5, 4 | Critical | ✅ | VERSIONING_GUIDE |
| REQ-VER-002 | Semantic Versioning | 0.5, 4 | High | ✅ | VERSIONING_GUIDE |
| REQ-VER-003 | Trade Attribution | 0.5, 4 | Critical | ✅ | VERSIONING_GUIDE |
| REQ-VER-004 | Version Lifecycle Management | 4 | High | ✅ | VERSIONING_GUIDE |
| REQ-VER-005 | A/B Testing Support | 4 | Medium | ✅ | VERSIONING_GUIDE |

**Details:**

**REQ-VER-001: Immutable Version Configs**
- Strategy and model configs NEVER change once created
- To update: Create new version (v1.0 → v1.1 for bug fix, v1.0 → v2.0 for major)
- Acceptance Criteria:
  - Config field is IMMUTABLE
  - Status and metrics CAN update
  - Database enforces immutability

**REQ-VER-003: Trade Attribution**
- Every trade links to exact strategy version and model version
- Acceptance Criteria:
  - trades.strategy_id FK to strategies table
  - trades.model_id FK to probability_models table
  - trade_attribution view shows exact versions

---

## Trailing Stop Requirements (TRAIL)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-TRAIL-001 | Dynamic Trailing Stops | 0.5, 5 | High | ✅ | TRAILING_STOP_GUIDE |
| REQ-TRAIL-002 | JSONB State Management | 0.5, 5 | High | ✅ | TRAILING_STOP_GUIDE |
| REQ-TRAIL-003 | Stop Price Updates | 5 | High | ✅ | TRAILING_STOP_GUIDE |
| REQ-TRAIL-004 | Peak Price Tracking | 5 | Medium | ✅ | TRAILING_STOP_GUIDE |

---

## Kelly Criterion Requirements (KELLY)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-KELLY-001 | Fractional Kelly Position Sizing | 1 | Critical | 🔵 | position_management.yaml |
| REQ-KELLY-002 | Default Kelly Fraction 0.25 | 1 | High | 🔵 | position_management.yaml |
| REQ-KELLY-003 | Position Size Limits | 1 | Critical | 🔵 | position_management.yaml |

---

## Risk Management Requirements (RISK)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-RISK-001 | Circuit Breakers (5 consecutive losses) | 1 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-RISK-002 | Daily Loss Limit | 1 | Critical | 🔵 | position_management.yaml |
| REQ-RISK-003 | Max Open Positions | 1 | High | 🔵 | position_management.yaml |
| REQ-RISK-004 | Max Position Size | 1 | High | 🔵 | position_management.yaml |
| REQ-RISK-005 | Stop Loss -15% | 5 | Critical | ✅ | position_management.yaml |

---

## Testing Requirements (TEST)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-TEST-001 | Code Coverage >80% | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-TEST-002 | Unit Tests for Core Modules | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-TEST-003 | Integration Tests for APIs | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-TEST-004 | Backtesting Framework | 4 | High | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-005 | Test Result Persistence | 0.6c | High | ✅ | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-006 | Security Testing Integration | 0.7 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-007 | Mutation Testing | 0.7 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-008 | Property-Based Testing - Proof of Concept | 1.5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-009 | Property-Based Testing - Phase 1.5 Expansion | 1.5 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-010 | Property-Based Testing - Phases 2-4 Expansion | 2-4 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-011 | Property-Based Testing - Phase 5 Expansion | 5 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-012 | Test Type Coverage Requirements | 1.5+ | Critical | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-013 | Mock Usage Restrictions | 1.5+ | Critical | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-014 | Test Fixture Usage Requirements | 1.5+ | Critical | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-015 | Coverage Percentage Standards | 1.5+ | Critical | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-016 | Stress Test Requirements | 1.5+ | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-017 | Integration Test Requirements | 1.5+ | Critical | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-018 | Property-Based Test Requirements | 1+ | Critical | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-019 | End-to-End Test Requirements | 2+ | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-TEST-020 | CI-Safe Stress Test Requirements | 1.9 | High | ✅ | MASTER_REQUIREMENTS_V2.22 |

---

## Validation Requirements (VALIDATION)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-VALIDATION-001 | Automated Code Quality (Ruff) | 0.6c | High | ✅ | MASTER_REQUIREMENTS_V2.12 |
| REQ-VALIDATION-002 | Documentation Validation Automation | 0.6c | Medium | ✅ | MASTER_REQUIREMENTS_V2.12 |
| REQ-VALIDATION-003 | Layered Validation Architecture | 0.6c | High | ✅ | MASTER_REQUIREMENTS_V2.12 |
| REQ-VALIDATION-004 | YAML Configuration Validation | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.12 |
| REQ-VALIDATION-005 | CODE_REVIEW_TEMPLATE Automated Enforcement | 0.7c | High | ✅ | MASTER_REQUIREMENTS_V2.12 |
| REQ-VALIDATION-006 | SECURITY_REVIEW_CHECKLIST Automated Enforcement | 0.7c | High | ✅ | MASTER_REQUIREMENTS_V2.12 |
| REQ-VALIDATION-007 | SCD Type 2 Query Validation (Pattern 2) | 1.5 | High | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-VALIDATION-008 | Property-Based Test Coverage (Pattern 10) | 1.5 | High | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-VALIDATION-009 | Real Test Fixtures Enforcement (Pattern 13) | 1.5 | High | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-VALIDATION-010 | Phase Start Protocol Automation | 1.5 | Medium | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-VALIDATION-011 | Phase Completion Protocol Automation | 1.5 | Medium | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-VALIDATION-012 | Configuration Synchronization (Pattern 8) | 1.5 | Medium | ✅ | MASTER_REQUIREMENTS_V2.22 |

**Summary:** Phase 0.6c implemented automated code quality and documentation validation. Phase 0.7c added CODE_REVIEW_TEMPLATE and SECURITY_REVIEW_CHECKLIST enforcement via pre-commit/pre-push hooks. Phase 1 adds YAML configuration validation with 4-level checks (syntax, Decimal type safety, required keys, cross-file consistency). Phase 1.5 adds comprehensive workflow enforcement infrastructure: SCD Type 2 query validation (Pattern 2), property-based test coverage enforcement (Pattern 10), real test fixtures validation (Pattern 13), phase start/completion protocol automation (3-step and 10-step assessments), and configuration synchronization checks (Pattern 8).

---

## CI/CD Requirements (CICD)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-CICD-001 | GitHub Actions CI/CD Integration | 0.7 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-CICD-002 | Codecov Integration | 0.7 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-CICD-003 | Branch Protection Rules | 0.7 | High | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-CICD-004 | Pre-Commit Hooks Infrastructure | 0.7 | High | ✅ | MASTER_REQUIREMENTS_V2.16 |
| REQ-CICD-005 | Pre-Push Hooks Infrastructure | 0.7 | High | ✅ | MASTER_REQUIREMENTS_V2.16 |

**Summary:** Phase 0.7 integrated GitHub Actions for automated CI/CD, coverage tracking with Codecov, branch protection for main branch, pre-commit hooks (14 checks, ~2-5s), and pre-push hooks (7 validation steps, ~60-90s). All infrastructure requirements completed 2025-11-07.

---

## Observability Requirements (OBSERV)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-OBSERV-001 | Request Correlation IDs (B3 Standard) | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.14 |
| REQ-OBSERV-002 | Sentry Production Error Tracking (Hybrid Architecture) | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.14 |
| REQ-OBSERV-003 | Log Aggregation with CloudWatch/ELK (Deferred to Phase 4) | 4 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.22 |

**Summary:** Phase 1 implements distributed request tracing with B3 correlation IDs (OpenTelemetry/Zipkin compatible) for debugging distributed systems. Phase 2 adds Sentry for real-time production error tracking with hybrid architecture integrating logger.py (audit trail), Sentry (real-time alerts), and alerts table (permanent record). Phase 4 adds centralized log aggregation (CloudWatch or ELK stack) for production monitoring.

---

## Scheduler Requirements (SCHED)

**Overview:** APScheduler-based service orchestration for live data polling and real-time streaming. Implements Service Supervisor pattern for multi-service health monitoring.

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-SCHED-001 | APScheduler-Based Live Data Polling | 2.5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-SCHED-002 | Service Supervisor Pattern | 2.5 | High | ✅ | MASTER_REQUIREMENTS_V2.22 |
| REQ-SCHED-003 | BasePoller Unified Design Pattern | 2.5 | High | ✅ | MASTER_REQUIREMENTS_V2.22 |

**Details:**

**REQ-SCHED-001: APScheduler-Based Live Data Polling**
- BackgroundScheduler for thread-pool job execution
- ESPN ESPNGamePoller: Live game state polling (30s normal, 5s urgent)
- Kalshi KalshiMarketPoller: Market price polling (configurable intervals)
- KalshiWebSocketHandler: Real-time market streaming
- Rate limiting integration with TokenBucket algorithm
- Related: ADR-100, src/precog/schedulers/

**REQ-SCHED-002: Service Supervisor Pattern**
- Multi-service orchestration with health monitoring
- EventLoopService Protocol: start(), stop(), is_running(), get_stats()
- Auto-restart with exponential backoff (max 3 retries)
- Metrics aggregation: poll counts, error rates, uptime
- Alert callbacks for service failures (configurable)
- JSON-formatted logging (CloudWatch/ELK compatible)
- Related: ADR-100, src/precog/schedulers/service_supervisor.py

**REQ-SCHED-003: BasePoller Unified Design Pattern**
- BasePoller abstract class with Template Method pattern
- Naming convention: {Platform}{Entity}Poller for REST, {Platform}{Entity}Handler for WebSocket
- Generic statistics: items_fetched, items_updated, items_created (PollerStats TypedDict)
- Thread-safe statistics with threading.Lock
- Backward compatibility aliases (MarketUpdater → ESPNGamePoller)
- Related: ADR-103, src/precog/schedulers/base_poller.py

---

## Security Requirements (SEC)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-SEC-009 | Sensitive Data Masking in Logs | 1 | High | ✅ | MASTER_REQUIREMENTS_V2.16 |

**Summary:** Phase 1 implements automatic masking of sensitive data (API keys, tokens, passwords) in all log output for GDPR/PCI-DSS compliance. Implementation: `mask_sensitive_data()` structlog processor in `src/precog/utils/logger.py`. Tests: 9 tests in `tests/security/test_credential_masking.py`.

---

## Performance Requirements (PERF)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-PERF-001 | System Uptime 99%+ | 1-10 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-PERF-002 | Data Latency <5s | 1-10 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-PERF-003 | Edge Detection Accuracy 55%+ | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |
| REQ-PERF-004 | Execution Success >95% | 5 | High | 🔵 | MASTER_REQUIREMENTS_V2.16 |

---

## Trading Methods Requirements (METH)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-METH-001 | Method Creation from Templates | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-002 | Immutable Method Configurations | 4-5 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-003 | Semantic Versioning for Methods | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-004 | Configuration Hashing | 4-5 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-005 | Method Lifecycle Management | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-006 | Activation Criteria | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-007 | Trade Attribution to Methods | 4-5 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-008 | A/B Testing Support | 4-5 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-009 | Helper Views | 4-5 | Low | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-010 | Export/Import Capability | 4-5 | Low | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-011 | Deprecation Automation | 4-5 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-012 | Historical Retention | 4-5 | Low | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-013 | Backward Compatibility | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-014 | Method Templates | 4-5 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-METH-015 | Performance Tracking | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |

**Summary:** Trading methods bundle complete trading approaches (strategy + model + position management + risk) into versioned, immutable configurations. Implementation deferred to Phase 4-5.

---

## Alerts & Monitoring Requirements (ALERT)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-ALERT-001 | Centralized Alert Logging | 1 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-002 | Severity Levels | 1 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-003 | Acknowledgement Tracking | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-004 | Resolution Tracking | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-005 | Multi-Channel Notifications | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-006 | Severity-Based Routing | 1 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-007 | Alert Deduplication | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-008 | Rate Limiting | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-009 | Email Notifications | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-010 | SMS Notifications | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-011 | Notification Delivery Tracking | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-012 | Source Linking | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-013 | Environment Tagging | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-014 | Flexible Metadata | 1 | Low | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ALERT-015 | Query Performance | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |

**Summary:** Centralized alert and notification system for critical events, errors, and system health monitoring. Supports email, SMS, Slack, webhook channels with severity-based routing.

---

## Machine Learning Requirements (ML)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-ML-001 | Phase 1-6 - Probability Matrices + Simple Models | 1-6 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ML-002 | Phase 9 - Feature Storage for Advanced ML | 9 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ML-003 | Phase 9 - MLOps Infrastructure | 9 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-ML-004 | Model Development Documentation | 1-10 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |

**Details:**

**REQ-ML-001: Phase 1-6 - Probability Matrices + Simple Models**
- Use probability_matrices for historical lookups
- Elo (Phase 4) calculates on-the-fly without feature storage
- Regression (Phase 4) uses basic stats from game_states
- Sport expansion (Phase 6) extends existing models
- Tables: probability_matrices, probability_models

**REQ-ML-002: Phase 9 - Feature Storage for Advanced ML**
- Add feature_definitions and features_historical tables
- Support XGBoost, LSTM models with historical features
- Store DVOA, EPA, SP+, team/player stats
- Tables: feature_definitions, features_historical

**REQ-ML-003: Phase 9 - MLOps Infrastructure**
- Add training_datasets and model_training_runs tables
- Track experiments, hyperparameters, metrics
- Enable A/B testing and continuous learning
- Tables: training_datasets, model_training_runs

**REQ-ML-004: Model Development Documentation**
- Documents: PROBABILITY_PRIMER.md (Phase 4), ELO_IMPLEMENTATION_GUIDE.md (Phase 4), MACHINE_LEARNING_ROADMAP.md (Phase 9), MODEL_EVALUATION_GUIDE.md (Phase 9)

**Elo Timeline:**
- Phase 4: Initial Elo for NFL (elo_nfl v1.0)
- Phase 6: Extend to new sports (elo_nba, elo_mlb)
- Phase 9: Enhanced Elo with advanced features

---

## Analytics Requirements (ANALYTICS)

**Overview:** Analytics infrastructure for performance tracking, materialized views, and data aggregation (Phases 6-9).

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-ANALYTICS-001 | Materialized View Implementation for Dashboard Queries | 6 | 🟡 High | 🔵 | MASTER_REQUIREMENTS_V2.13, ADR-083 |
| REQ-ANALYTICS-002 | Automated Materialized View Refresh (pg_cron Hourly Schedule) | 6 | 🟡 High | 🔵 | MASTER_REQUIREMENTS_V2.13, ADR-083 |
| REQ-ANALYTICS-003 | Performance Tracking Table (8-Level Time-Series Aggregation) | 1.5-2 | 🟡 High | 🔵 | MASTER_REQUIREMENTS_V2.13, ADR-079 |
| REQ-ANALYTICS-004 | Metrics Collection Pipeline (Real-time + Batch Aggregation) | 6 | 🟡 High | 🔵 | MASTER_REQUIREMENTS_V2.13, ADR-080 |

**Details:**

**REQ-ANALYTICS-001: Materialized View Implementation**
- Create 6 materialized views: mv_daily_model_performance, mv_strategy_profitability, mv_market_edge_distribution, mv_position_outcomes, mv_kelly_sizing_analysis, mv_exit_condition_effectiveness
- 158x-683x query speedup (5-30s → 0.03-0.044s)
- Unique indexes on (date, model_version) for REFRESH CONCURRENTLY
- Related: ADR-083 (Analytics Data Model), PERFORMANCE_TRACKING_GUIDE_V1.0.md

**REQ-ANALYTICS-002: Automated Refresh with pg_cron**
- Install pg_cron extension (CREATE EXTENSION pg_cron)
- Hourly refresh schedule: SELECT cron.schedule('refresh_analytics', '0 * * * *', $$REFRESH MATERIALIZED VIEW CONCURRENTLY...$$)
- CONCURRENTLY mode for zero-downtime refreshes
- Monitoring: cron.job_run_details table for status tracking
- Related: ADR-083 (refresh strategy)

**REQ-ANALYTICS-003: Performance Tracking Architecture**
- Table: performance_metrics with 8 aggregation levels (trade, hourly, daily, weekly, monthly, quarterly, yearly, all_time)
- Columns: win_rate, total_pnl, avg_pnl_per_trade, total_trades, kelly_accuracy, sharpe_ratio, max_drawdown, avg_position_duration_hours
- SCD Type 2 versioning: row_current_ind, row_effective_date, row_expiration_date
- Granularity: strategy_id + model_id + aggregation_period
- Related: ADR-079 (table schema), ADR-080 (metrics collection)

**REQ-ANALYTICS-004: Metrics Collection Strategy**
- Real-time metrics: Update on every trade_executed event (trade-level aggregation)
- Batch aggregation: Hourly cron job for daily/weekly/monthly rollups
- Incremental updates: Only recompute changed time windows
- Pipeline: Event → Trade Metrics → Hourly Rollup → Daily Rollup → Weekly/Monthly/Quarterly/Yearly/All-Time
- Related: ADR-080 (collection pipeline), PERFORMANCE_TRACKING_GUIDE_V1.0.md

---

## Reporting Requirements (REPORTING)

**Overview:** Dashboard architecture, data visualization, and reporting infrastructure (Phases 7-9).

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-REPORTING-001 | Dashboard Architecture (React + Next.js with Real-time WebSocket) | 7 | 🟡 High | 🔵 | MASTER_REQUIREMENTS_V2.13, ADR-081 |

**Details:**

**REQ-REPORTING-001: Dashboard Architecture**
- Frontend: React 18 + Next.js 14 (App Router) for server-side rendering
- Real-time updates: WebSocket connection for live P&L, position updates (<500ms latency)
- Charting: Plotly.js for interactive financial charts (candlesticks, P&L curves, calibration plots)
- Data source: Materialized views (mv_daily_model_performance, etc.) for fast initial load
- Authentication: NextAuth.js with read-only mode for live trading
- Deployment: Vercel for frontend, PostgreSQL backend unchanged
- Related: ADR-081 (dashboard stack), ADR-083 (data source), DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md

---

## Requirement Statistics

**Total Requirements:** 127
**Completed (✅):** 31 (Phase 0-2.5, including REQ-SCHED-001, REQ-SCHED-002)
**In Progress (🟡):** 1 (REQ-DATA-003 - ESPN client complete, database pending)
**Planned (🔵):** 95 (Phase 0.7, 1-10 including REQ-ML-001, REQ-ANALYTICS-001-004, REQ-REPORTING-001, REQ-DATA-001-005, REQ-OBSERV-003)

**By Category:**
- System (SYS): 6 requirements
- **API (API): 7 requirements** (added REQ-API-007 in V1.3)
- Database (DB): 10 requirements
- **Data (DATA): 5 requirements** (NEW in V1.9 - live game data, SCD Type 2 versioning)
- Monitoring (MON): 5 requirements
- Exit (EXIT): 5 requirements
- Execution (EXEC): 5 requirements
- Versioning (VER): 5 requirements
- Trailing (TRAIL): 4 requirements
- Kelly (KELLY): 3 requirements
- Risk (RISK): 5 requirements
- Methods (METH): 15 requirements
- Alerts (ALERT): 15 requirements
- Machine Learning (ML): 4 requirements
- **Testing (TEST): 19 requirements** (added 8 in V1.2, added 6 in V1.8)
- Performance (PERF): 4 requirements
- **Validation (VALIDATION): 12 requirements** (added REQ-VALIDATION-004 in V1.3, 6 in V1.8)
- **CI/CD (CICD): 5 requirements** (added 2 in V1.7)
- **Observability (OBSERV): 2 requirements** (added REQ-OBSERV-002 in V1.6)
- **Security (SEC): 1 requirement** (NEW in V1.3)
- **Analytics (ANALYTICS): 4 requirements** (NEW in V1.5 - materialized views, performance tracking)
- **Reporting (REPORTING): 1 requirement** (NEW in V1.5 - dashboard architecture)

**By Phase:**
- Phase 0: 6 requirements (100% complete)
- Phase 0.5: 17 requirements (100% complete)
- **Phase 0.6c: 3 requirements (100% complete)** - validation infrastructure
- **Phase 0.7: 7 requirements (0% complete)** - CI/CD and advanced testing
- **Phase 1: 29 requirements (0% complete)** - API best practices, alerts, CLI
- **Phase 1.5-2: 1 requirement (0% complete)** - performance tracking architecture (REQ-ANALYTICS-003)
- **Phase 2: 8 requirements (0% complete)** - ESPN data, venues, rankings (REQ-DATA-001-005)
- Phase 4: 5 requirements (0% complete)
- Phase 4-5: 15 requirements (0% complete) - methods system
- Phase 5: 14 requirements (100% complete - documented)
- **Phase 6: 3 requirements (0% complete)** - materialized views (REQ-ANALYTICS-001, 002, 004)
- **Phase 7: 1 requirement (0% complete)** - dashboard architecture (REQ-REPORTING-001)
- **Phase 6-9: 3 requirements (0% complete)** - ML infrastructure (REQ-ML-001, 002, 003)

---

## Next Steps

1. ✅ ~~Update MASTER_REQUIREMENTS_V2.6~~ → **COMPLETED** (V2.7 created with all REQ IDs)
2. ✅ ~~Update REQUIREMENT_INDEX~~ → **COMPLETED** (V1.1 with METH, ALERT, ML requirements)
3. **Update DATABASE_SCHEMA_SUMMARY** - Add ML table placeholder schemas
4. **Update system.yaml** - Add notifications configuration section
5. **Create alerts migration SQL** - 002_add_alerts_table.sql
6. **Update MASTER_INDEX** - Update document versions to V2.7
7. **Create ADR_INDEX** - Catalog all architecture decisions (if not exists)
8. **Update guides** - Use new REQ IDs in cross-references
9. **Maintain index** - Update as new requirements added

---

**Document Version:** 1.13
**Last Updated:** 2025-12-07
**Created:** 2025-10-21
**Purpose:** Systematic requirement tracking and traceability

**END OF REQUIREMENT INDEX V1.13**
