# Requirement Index

---
**Version:** 1.4
**Last Updated:** 2025-11-09
**Status:** ✅ Current
**Purpose:** Master index of all system requirements with systematic IDs
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

---

## System Requirements (SYS)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-SYS-001 | Database Schema Versioning | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-SYS-002 | Configuration Management (YAML) | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-SYS-003 | Decimal Precision for Prices | 0 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
| REQ-SYS-006 | Structured Logging | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |

**Note:** System Uptime and Data Latency requirements are tracked as REQ-PERF-001 and REQ-PERF-002 in the Performance section.

---

## API Requirements (API)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-API-001 | Kalshi API Integration | 1 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-API-002 | RSA-PSS Authentication (Kalshi) | 1 | Critical | 🔵 | API_INTEGRATION_GUIDE_V1.0 |
| REQ-API-003 | ESPN API Integration | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-API-004 | Balldontlie API Integration | 2 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-API-005 | API Rate Limit Management | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-API-006 | API Error Handling | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-API-007 | API Response Validation with Pydantic | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |

---

## CLI Requirements (CLI)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-CLI-001 | CLI Framework with Typer | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-002 | Balance Fetch Command | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-003 | Positions Fetch Command | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-004 | Fills Fetch Command | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-CLI-005 | Settlements Fetch Command | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.9 |

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
| REQ-DB-008 | Database Connection Pooling | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |

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
| REQ-TEST-001 | Code Coverage >80% | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-TEST-002 | Unit Tests for Core Modules | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-TEST-003 | Integration Tests for APIs | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.9 |
| REQ-TEST-004 | Backtesting Framework | 4 | High | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-005 | Test Result Persistence | 0.6c | High | ✅ | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-006 | Security Testing Integration | 0.7 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-007 | Mutation Testing | 0.7 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-008 | Property-Based Testing - Proof of Concept | 1.5 | Critical | ✅ | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-009 | Property-Based Testing - Phase 1.5 Expansion | 1.5 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-010 | Property-Based Testing - Phases 2-4 Expansion | 2-4 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |
| REQ-TEST-011 | Property-Based Testing - Phase 5 Expansion | 5 | Critical | 🔵 | MASTER_REQUIREMENTS_V2.11 |

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

**Summary:** Phase 0.6c implemented automated code quality and documentation validation. Phase 0.7c added CODE_REVIEW_TEMPLATE and SECURITY_REVIEW_CHECKLIST enforcement via pre-commit/pre-push hooks. Phase 1 adds YAML configuration validation with 4-level checks (syntax, Decimal type safety, required keys, cross-file consistency).

---

## CI/CD Requirements (CICD)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-CICD-001 | GitHub Actions CI/CD Integration | 0.7 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-CICD-002 | Codecov Integration | 0.7 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-CICD-003 | Branch Protection Rules | 0.7 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |

**Summary:** Phase 0.7 will integrate GitHub Actions for automated CI/CD, coverage tracking with Codecov, and branch protection for main branch.

---

## Observability Requirements (OBSERV)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-OBSERV-001 | Request Correlation IDs (B3 Standard) | 1 | Medium | 🔵 | MASTER_REQUIREMENTS_V2.10 |

**Summary:** Phase 1 implements distributed request tracing with B3 correlation IDs (OpenTelemetry/Zipkin compatible) for debugging distributed systems and performance analysis.

---

## Security Requirements (SEC)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-SEC-009 | Sensitive Data Masking in Logs | 1 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |

**Summary:** Phase 1 implements automatic masking of sensitive data (API keys, tokens, passwords) in all log output for GDPR/PCI-DSS compliance.

---

## Performance Requirements (PERF)

| ID | Title | Phase | Priority | Status | Document |
|----|-------|-------|----------|--------|----------|
| REQ-PERF-001 | System Uptime 99%+ | 1-10 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-PERF-002 | Data Latency <5s | 1-10 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-PERF-003 | Edge Detection Accuracy 55%+ | 4-5 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |
| REQ-PERF-004 | Execution Success >95% | 5 | High | 🔵 | MASTER_REQUIREMENTS_V2.10 |

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
| REQ-ML-001 | Phase 1-6 - Probability Matrices + Simple Models | 1-6 | Critical | ✅ | MASTER_REQUIREMENTS_V2.9 |
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

## Requirement Statistics

**Total Requirements:** 103
**Completed (✅):** 27 (Phase 0-0.6c + REQ-ML-001)
**Planned (🔵):** 76 (Phase 0.7, 1-10)

**By Category:**
- System (SYS): 6 requirements
- **API (API): 7 requirements** (added REQ-API-007 in V1.3)
- Database (DB): 7 requirements
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
- **Testing (TEST): 8 requirements** (added 4 in V1.2)
- Performance (PERF): 4 requirements
- **Validation (VALIDATION): 4 requirements** (added REQ-VALIDATION-004 in V1.3)
- **CI/CD (CICD): 3 requirements** (added in V1.2)
- **Observability (OBSERV): 1 requirement** (NEW in V1.3)
- **Security (SEC): 1 requirement** (NEW in V1.3)

**By Phase:**
- Phase 0: 6 requirements (100% complete)
- Phase 0.5: 17 requirements (100% complete)
- **Phase 0.6c: 3 requirements (100% complete)** - validation infrastructure
- **Phase 0.7: 7 requirements (0% complete)** - CI/CD and advanced testing
- **Phase 1: 29 requirements (0% complete)** - API best practices, alerts, CLI
- Phase 2: 3 requirements (0% complete)
- Phase 4: 5 requirements (0% complete)
- Phase 4-5: 15 requirements (0% complete) - methods system
- Phase 5: 14 requirements (100% complete - documented)
- Phase 6-9: 3 requirements (0% complete) - ML infrastructure
- Phase 1-10: 1 requirement (in progress) - REQ-ML-001

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

**Document Version:** 1.1
**Last Updated:** 2025-10-24
**Created:** 2025-10-21
**Purpose:** Systematic requirement tracking and traceability

**END OF REQUIREMENT INDEX**
