# Architecture Decision Record Index

---
**Version:** 1.12
**Last Updated:** 2025-11-17
**Status:** ✅ Current
**Changes in v1.12:**
- **TESTING ARCHITECTURE (PHASE 1.5):** Added ADR-088 (Test Type Categories - Comprehensive 8 Test Type Framework)
- Added ADR-088: Test Type Categories (addresses Phase 1.5 TDD failure - 17/17 tests passed with mocks → 13/17 failed with real DB)
- Documents 8 test types: Unit, Property, Integration, E2E, Stress, Race, Performance, Chaos
- Mock usage policy: ✅ APPROPRIATE for external APIs/time/randomness, ❌ FORBIDDEN for internal infrastructure
- Test type requirements matrix (REQ-TEST-012), mock usage restrictions (REQ-TEST-013)
- Updated ARCHITECTURE_DECISIONS reference from V2.16 to V2.17
- Total ADRs: 67 → 68 (1 new ADR added for Phase 1.5 testing architecture)
**Changes in v1.11:**
- **SCHEMA STANDARDIZATION (PHASE 1.5):** Added ADR-086 (Schema Classification Field Naming) and ADR-087 (No Edge Manager Component)
- Added ADR-086: Schema Classification Field Naming (approach/domain standardization resolving three-way mismatch)
- Added ADR-087: No Edge Manager Component (calculated outputs pattern - 3 managers not 4)
- Updated ARCHITECTURE_DECISIONS reference from V2.15 to V2.16
- Updated DATABASE_SCHEMA_SUMMARY reference from V1.8 to V1.9
- Total ADRs: 65 → 67 (2 new ADRs added for Phase 1.5)
**Changes in v1.10:**
- **BRANCH PROTECTION INFRASTRUCTURE:** Added ADR-046 (Branch Protection Strategy - Phase 0.7 Retroactive)
- Added ADR-046: Branch Protection Strategy (GitHub Branch Protection with 6 required CI checks)
- Updated ARCHITECTURE_DECISIONS reference from V2.14 to V2.15
- Total ADRs: 64 → 65 (1 new ADR added retroactively for Phase 0.7)
**Changes in v1.9:**
- **PRODUCTION MONITORING INFRASTRUCTURE:** Added ADR-055 (Sentry for Production Error Tracking - Hybrid Architecture)
- Added Phase 2 section for production monitoring infrastructure
- Added ADR-055: Sentry for Production Error Tracking (Hybrid Architecture integrating logger.py + Sentry + alerts table)
- Updated ARCHITECTURE_DECISIONS reference from V2.13 to V2.14
- Total ADRs: 63 → 64 (1 new ADR added)
**Changes in v1.8:**
- **PHASES 6-9 ANALYTICS INFRASTRUCTURE:** Added ADR-078 through ADR-085 (Complete Analytics Foundation)
- Added Phases 6-9 section for analytics infrastructure (performance tracking, dashboards, A/B testing)
- Added ADR-078: Model Configuration Storage Architecture (JSONB vs Dedicated Tables)
- Added ADR-079: Performance Tracking Architecture (8-level time-series aggregation)
- Added ADR-080: Metrics Collection Strategy (Real-time + Batch Pipeline)
- Added ADR-081: Dashboard Architecture (React + Next.js with WebSocket)
- Added ADR-082: Model Evaluation Framework (Backtesting, Cross-Validation, Calibration)
- Added ADR-083: Analytics Data Model (Materialized Views for 158x-683x Speedup)
- Added ADR-084: A/B Testing Infrastructure (Stratified Random Assignment)
- Added ADR-085: JSONB vs Normalized Hybrid Strategy (Materialized Views)
- Updated ARCHITECTURE_DECISIONS reference from V2.13 to V2.13 (same version, added ADRs)
- Total ADRs: 55 → 63 (8 new ADRs added)
**Changes in v1.7:**
- **STRATEGIC RESEARCH PRIORITIES:** Added ADR-076 and ADR-077 (Open Questions Requiring Research)
- Added Phase 4.5 section for strategic research priorities
- Added ADR-076: Dynamic Ensemble Weights Architecture (Open Question - Research Required)
- Added ADR-077: Strategy vs Method Separation (Open Question - HIGHEST PRIORITY Research)
- Updated ARCHITECTURE_DECISIONS reference from V2.12 to V2.13
- Total ADRs: 53 → 55 (2 new ADRs added)
**Changes in v1.6:**
- **PROPERTY-BASED TESTING INTEGRATION:** Added ADR-074 (Property-Based Testing Strategy with Hypothesis)
- Added Phase 1.5 section for property-based testing integration
- Added ADR-074: Property-Based Testing Strategy (Hypothesis Framework) - POC complete
- Total ADRs: 52 → 53 (1 new ADR added)
**Changes in v1.5:**
- **PYTHON 3.14 COMPATIBILITY:** Added ADR-054 (Ruff Security Rules Instead of Bandit)
- Added ADR-054: Ruff Security Rules Instead of Bandit (Python 3.14 compatibility)
- Updated ARCHITECTURE_DECISIONS reference from V2.10 to V2.11
- Total ADRs: 51 → 52 (1 new ADR added)
**Changes in v1.4:**
- **CROSS-PLATFORM STANDARDS:** Added ADR-053 (Cross-Platform Development - Windows/Linux compatibility)
- Added ADR-053: Cross-Platform Development Standards (ASCII-safe console output, UTF-8 file I/O)
- Updated ARCHITECTURE_DECISIONS reference from V2.9 to V2.10
- Total ADRs: 50 → 51 (1 new ADR added)
**Changes in v1.3:**
- **PHASE 1 API BEST PRACTICES:** Added ADR-047 through ADR-052 (API Integration Best Practices - Planned)
- Added ADR-047: API Response Validation with Pydantic
- Added ADR-048: Circuit Breaker Implementation (use library not custom)
- Added ADR-049: Request Correlation ID Standard (B3 spec)
- Added ADR-050: HTTP Connection Pooling Configuration
- Added ADR-051: Sensitive Data Masking in Logs
- Added ADR-052: YAML Configuration Validation
- Updated ARCHITECTURE_DECISIONS reference from V2.8 to V2.9
- Total ADRs: 44 → 50 (6 new ADRs added)
**Changes in v1.2:**
- **PHASE 0.6C COMPLETION:** Added ADR-038 through ADR-041 (Validation & Testing Infrastructure - Complete)
- **PHASE 0.7 PLANNING:** Added ADR-042 through ADR-045 (CI/CD Integration & Advanced Testing - Planned)
- Updated ARCHITECTURE_DECISIONS reference from V2.7 to V2.8
- Total ADRs: 36 → 44 (8 new ADRs added)
**Purpose:** Master index of all architectural decisions with systematic ADR numbers
---

## Overview

This document provides a systematic index of all Precog architecture decisions using ADR-{NUMBER} format.

**Status Key:**
- ✅ Accepted - Decision made and implemented
- 🔵 Proposed - Under consideration
- ⚠️ Superseded - Replaced by newer decision
- ❌ Rejected - Considered but not adopted

---

## ADR Number Ranges

| Range | Category | Description |
|-------|----------|-------------|
| 001-099 | Foundation | Phase 0-0.5 architectural decisions |
| 100-199 | Core Engine | Phase 1-3 trading engine decisions |
| 200-299 | Probability Models | Phase 4 model architecture |
| 300-399 | Position Management | Phase 5 position/exit management |
| 400-499 | Multi-Sport | Phase 6-7 sport expansion |
| 500-599 | Advanced Features | Phase 8-9 non-sports, ML |
| 600-699 | Multi-Platform | Phase 10 platform expansion |

---

## Foundation Decisions (001-099)

### Phase 0: Core Foundation

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-001 | Use PostgreSQL for Primary Database | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-002 | Use DECIMAL for Price/Probability Fields | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-003 | SCD Type 2 for Versioned Data | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-004 | YAML for Configuration Files | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-005 | Python 3.12+ as Primary Language | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-006 | SQLAlchemy as ORM | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-007 | Platform Abstraction Layer | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-008 | Modular Directory Structure | 2025-09 | ✅ | 0 | PROJECT_OVERVIEW_V1.4 |
| ADR-009 | Environment Variables for Secrets | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-010 | Structured Logging with Python logging | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-011 | pytest for Testing Framework | 2025-09 | ✅ | 0 | ARCHITECTURE_DECISIONS_V2.4 |
| ADR-012 | Foreign Key Constraints for Referential Integrity | 2025-09 | ✅ | 0 | DATABASE_SCHEMA_SUMMARY_V1.5 |
| ADR-013 | CHECK Constraints for Data Validation | 2025-09 | ✅ | 0 | DATABASE_SCHEMA_SUMMARY_V1.5 |
| ADR-014 | ON DELETE CASCADE for Cascading Deletes | 2025-09 | ✅ | 0 | DATABASE_SCHEMA_SUMMARY_V1.5 |
| ADR-015 | Helper Views for Current Data | 2025-09 | ✅ | 0 | DATABASE_SCHEMA_SUMMARY_V1.5 |
| ADR-016 | Terminology: "Probability" over "Odds" | 2025-10 | ✅ | 0 | GLOSSARY.md |
| ADR-017 | Method Abstraction Pattern for YAMLs | 2025-10 | ✅ | 0 | CONFIGURATION_GUIDE_V3.1 |

### Phase 0.5: Foundation Enhancement

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-018 | Immutable Version Pattern for Strategies/Models | 2025-10 | ✅ | 0.5 | VERSIONING_GUIDE_V1.0.md |
| ADR-019 | Trailing Stop JSONB Structure | 2025-10 | ✅ | 0.5 | TRAILING_STOP_GUIDE_V1.0.md |
| ADR-020 | Trade Attribution Links (strategy_id, model_id) | 2025-10 | ✅ | 0.5 | DATABASE_SCHEMA_SUMMARY_V1.7.md |
| ADR-021 | Semantic Versioning for Strategies/Models | 2025-10 | ✅ | 0.5 | VERSIONING_GUIDE_V1.0.md |
| ADR-022 | Helper Views for Active Versions | 2025-10 | ✅ | 0.5 | DATABASE_SCHEMA_SUMMARY_V1.7.md |
| ADR-023 | Position Monitoring Architecture (30s/5s) | 2025-10 | ✅ | 0.5 | POSITION_MANAGEMENT_GUIDE_V1.0.md |
| ADR-024 | Exit Priority Hierarchy (4 Levels) | 2025-10 | ✅ | 0.5 | POSITION_MANAGEMENT_GUIDE_V1.0.md |
| ADR-025 | Price Walking Algorithm for Exits | 2025-10 | ✅ | 0.5 | POSITION_MANAGEMENT_GUIDE_V1.0.md |
| ADR-026 | Partial Exit Staging (2-Stage) | 2025-10 | ✅ | 0.5 | POSITION_MANAGEMENT_GUIDE_V1.0.md |
| ADR-027 | position_exits Append-Only Table | 2025-10 | ✅ | 0.5 | DATABASE_SCHEMA_SUMMARY_V1.7.md |
| ADR-028 | exit_attempts for Debugging | 2025-10 | ✅ | 0.5 | DATABASE_SCHEMA_SUMMARY_V1.7.md |

### Phase 1: Database Completion

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-029 | Elo Data Source: game_states over settlements | 2025-10-24 | ✅ | 1 | ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0 |
| ADR-030 | Elo Ratings Storage: teams Table over probability_models.config | 2025-10-24 | ✅ | 1 | ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0 |
| ADR-031 | Settlements as Separate Table over Markets Columns | 2025-10-24 | ✅ | 1 | ELO_AND_SETTLEMENTS_ARCHITECTURE_ANALYSIS_V1.0 |
| ADR-032 | Markets Surrogate PRIMARY KEY (id SERIAL) | 2025-10-24 | ✅ | 1 | Migration 009 |
| ADR-033 | External ID Traceability Pattern | 2025-10-24 | ✅ | 1 | Migration 008 |
| ADR-034 | SCD Type 2 Completion (row_end_ts) | 2025-10-24 | ✅ | 1 | Migrations 005, 007 |

### Phase 0.6c: Validation & Testing Infrastructure

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-038 | Ruff for Code Quality Automation | 2025-10-29 | ✅ | 0.6c | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-039 | Test Result Persistence Strategy | 2025-10-29 | ✅ | 0.6c | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-040 | Documentation Validation Automation | 2025-10-29 | ✅ | 0.6c | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-041 | Layered Validation Architecture | 2025-10-29 | ✅ | 0.6c | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-053 | Cross-Platform Development Standards (Windows/Linux) | 2025-11-04 | ✅ | 0.6c | ARCHITECTURE_DECISIONS_V2.10 |

### Phase 0.7: CI/CD & Advanced Testing (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-042 | CI/CD Integration with GitHub Actions | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.11 |
| ADR-043 | Security Testing Integration | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.11 |
| ADR-044 | Mutation Testing Strategy | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.11 |
| ADR-045 | Property-Based Testing with Hypothesis | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.11 |
| ADR-046 | Branch Protection Strategy (GitHub Branch Protection) | 2025-11-15 | ✅ | 0.7 | ARCHITECTURE_DECISIONS_V2.15 |
| ADR-054 | Ruff Security Rules Instead of Bandit (Python 3.14 Compatibility) | 2025-11-07 | ✅ | 0.7 | ARCHITECTURE_DECISIONS_V2.11 |

### Phase 1: API Integration Best Practices (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-047 | API Response Validation with Pydantic | 2025-10-31 | 🔵 | 1 | ARCHITECTURE_DECISIONS_V2.10 |
| ADR-048 | Circuit Breaker Implementation (circuitbreaker library) | 2025-10-31 | 🔵 | 1 | ARCHITECTURE_DECISIONS_V2.10 |
| ADR-049 | Request Correlation ID Standard (B3 Spec) | 2025-10-31 | 🔵 | 1 | ARCHITECTURE_DECISIONS_V2.10 |
| ADR-050 | HTTP Connection Pooling Configuration | 2025-10-31 | 🔵 | 1 | ARCHITECTURE_DECISIONS_V2.10 |
| ADR-051 | Sensitive Data Masking in Logs | 2025-10-31 | 🔵 | 1 | ARCHITECTURE_DECISIONS_V2.10 |
| ADR-052 | YAML Configuration Validation | 2025-10-31 | 🔵 | 1 | ARCHITECTURE_DECISIONS_V2.10 |

### Phase 1.5: Property-Based Testing Integration

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-074 | Property-Based Testing Strategy (Hypothesis Framework) | 2025-11-08 | ✅ | 1.5 | ARCHITECTURE_DECISIONS_V2.12 |
| ADR-075 | Multi-Source Warning Governance Architecture | 2025-11-08 | ✅ | 0.7/1 | ARCHITECTURE_DECISIONS_V2.12 |

### Phase 2: Production Monitoring Infrastructure (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-055 | Sentry for Production Error Tracking (Hybrid Architecture) | 2025-11-14 | 🔵 | 2 | ARCHITECTURE_DECISIONS_V2.14 |

### Phase 4.5: Strategic Research Priorities (Open Questions)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-076 | Dynamic Ensemble Weights Architecture | 2025-11-09 | 🔵 | 4.5 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-077 | Strategy vs Method Separation (HIGHEST PRIORITY) | 2025-11-09 | 🔵 | 4.5 | ARCHITECTURE_DECISIONS_V2.13 |

### Phases 6-9: Analytics Infrastructure (Performance Tracking, Dashboards, A/B Testing)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-078 | Model Configuration Storage Architecture (JSONB vs Dedicated Tables) | 2025-11-10 | ✅ | 1 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-079 | Performance Tracking Architecture (8-level time-series aggregation) | 2025-11-10 | ✅ | 1.5-2 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-080 | Metrics Collection Strategy (Real-time + Batch Pipeline) | 2025-11-10 | ✅ | 6 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-081 | Dashboard Architecture (React + Next.js with WebSocket) | 2025-11-10 | ✅ | 7 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-082 | Model Evaluation Framework (Backtesting, Cross-Validation, Calibration) | 2025-11-10 | ✅ | 1.5 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-083 | Analytics Data Model (Materialized Views for 158x-683x Speedup) | 2025-11-10 | ✅ | 6 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-084 | A/B Testing Infrastructure (Stratified Random Assignment) | 2025-11-10 | ✅ | 8 | ARCHITECTURE_DECISIONS_V2.13 |
| ADR-085 | JSONB vs Normalized Hybrid Strategy (Materialized Views) | 2025-11-10 | ✅ | 6 | ARCHITECTURE_DECISIONS_V2.13 |

### Phase 5: Trading MVP (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-035 | Event Loop Architecture (async/await) | 2025-10-28 | 🔵 | 5 | EVENT_LOOP_ARCHITECTURE_V1.0.md |
| ADR-036 | Exit Evaluation Strategy (Priority Hierarchy) | 2025-10-28 | 🔵 | 5a | EXIT_EVALUATION_SPEC_V1.0.md |
| ADR-037 | Advanced Order Walking (Multi-Stage Price Walking) | 2025-10-28 | 🔵 | 5b | ADVANCED_EXECUTION_SPEC_V1.0.md |

---

## Core Engine Decisions (100-199)

### Phase 1: Core Trading Engine (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-100 | TBD - Kalshi API Client Architecture | - | 🔵 | 1 | - |
| ADR-101 | TBD - RSA-PSS Authentication Implementation | - | 🔵 | 1 | - |
| ADR-102 | TBD - Error Handling Strategy | - | 🔵 | 1 | - |
| ADR-103 | TBD - Rate Limiting Implementation | - | 🔵 | 1 | - |
| ADR-104 | TBD - Trade Execution Workflow | - | 🔵 | 1 | - |

### Phase 2: Live Data Integration (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-110 | TBD - ESPN API Integration Strategy | - | 🔵 | 2 | - |
| ADR-111 | TBD - Game State Polling Frequency | - | 🔵 | 2 | - |
| ADR-112 | TBD - Data Staleness Detection | - | 🔵 | 2 | - |

### Phase 3: Edge Detection (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-120 | TBD - Edge Calculation Algorithm | - | 🔵 | 3 | - |
| ADR-121 | TBD - Confidence Scoring Methodology | - | 🔵 | 3 | - |

---

## Probability Model Decisions (200-299)

### Phase 4: Historical Probability Models (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-200 | TBD - Elo Rating System Implementation | - | 🔵 | 4 | - |
| ADR-201 | TBD - Regression Model Architecture | - | 🔵 | 4 | - |
| ADR-202 | TBD - Model Validation Methodology | - | 🔵 | 4 | - |
| ADR-203 | TBD - Backtesting Framework | - | 🔵 | 4 | - |

---

## Position Management Decisions (300-399)

### Phase 5: Position Management (Documented)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-300 | 10 Exit Conditions with Priorities | 2025-10 | ✅ | 5 | POSITION_MANAGEMENT_GUIDE |
| ADR-301 | Urgency-Based Execution Strategies | 2025-10 | ✅ | 5 | POSITION_MANAGEMENT_GUIDE |
| ADR-302 | Fractional Kelly Position Sizing | - | 🔵 | 5 | position_management.yaml |
| ADR-303 | Circuit Breaker Triggers | - | 🔵 | 5 | position_management.yaml |

---

## ADR Details (Selected)

### ADR-001: Use PostgreSQL for Primary Database

**Date:** 2025-09-15
**Status:** ✅ Accepted
**Phase:** 0
**Stakeholders:** Development Team

**Context:**
Need to choose a database system that supports:
- ACID compliance for financial transactions
- Complex queries for analytics
- DECIMAL precision for prices
- JSONB for flexible data structures

**Decision:**
Use PostgreSQL 15+ as the primary database.

**Consequences:**
- **Positive:**
  - ACID compliance guarantees
  - Rich type system (DECIMAL, JSONB, Arrays)
  - Mature ORM support (SQLAlchemy)
  - Excellent documentation
  - Free and open-source
- **Negative:**
  - Requires PostgreSQL-specific knowledge
  - More complex than SQLite for local dev
- **Neutral:**
  - Migration to AWS RDS straightforward

---

### ADR-002: Use DECIMAL for Price/Probability Fields

**Date:** 2025-09-15
**Status:** ✅ Accepted
**Phase:** 0
**Stakeholders:** Development Team

**Context:**
Prices and probabilities must be exact to 4 decimal places. Float types cause rounding errors in financial calculations.

**Decision:**
Use DECIMAL(10,4) for all price and probability fields. Use Python's Decimal class in application code.

**Consequences:**
- **Positive:**
  - Exact precision (0.0000-1.0000 range)
  - No float rounding errors
  - Industry standard for financial apps
- **Negative:**
  - Slightly more complex than float
  - Requires explicit Decimal() conversions
- **Neutral:**
  - Performance difference negligible

---

### ADR-018: Immutable Version Pattern for Strategies/Models

**Date:** 2025-10-18
**Status:** ✅ Accepted
**Phase:** 0.5
**Stakeholders:** Development Team

**Context:**
Need to maintain exact trade attribution and support A/B testing. If strategy/model configs change, we can't compare versions accurately.

**Decision:**
Implement immutable version pattern:
- Config field NEVER changes once version created
- To update: Create new version (v1.0 → v1.1)
- Status and metrics CAN update (lifecycle, performance)

**Consequences:**
- **Positive:**
  - Perfect trade attribution integrity
  - A/B testing with confidence
  - Clear audit trail
  - Semantic versioning enables controlled evolution
- **Negative:**
  - More versions to manage
  - Requires discipline to create new versions
- **Neutral:**
  - Database storage cost minimal

**References:**
- VERSIONING_GUIDE_V1.0.md
- DATABASE_SCHEMA_SUMMARY_V1.5.md (strategies, probability_models tables)

---

### ADR-023: Position Monitoring Architecture (30s/5s)

**Date:** 2025-10-21
**Status:** ✅ Accepted
**Phase:** 0.5
**Stakeholders:** Development Team

**Context:**
Need to monitor positions efficiently without overwhelming API rate limits (60 calls/min).

**Decision:**
Implement dynamic monitoring with two frequencies:
- **Normal:** 30-second polling for stable positions
- **Urgent:** 5-second polling when within 2% of thresholds
- **Price Caching:** 10-second TTL to reduce API calls

**Consequences:**
- **Positive:**
  - Responsive to critical events (5s urgent)
  - API rate-friendly (30s normal)
  - Automatic frequency switching
- **Negative:**
  - More complex than single frequency
  - Urgent detection adds overhead
- **Neutral:**
  - Well within 60 calls/min limit

**References:**
- POSITION_MANAGEMENT_GUIDE_V1.0.md Section 4
- REQ-MON-001, REQ-MON-002

---

### ADR-024: Exit Priority Hierarchy (4 Levels)

**Date:** 2025-10-21
**Status:** ✅ Accepted
**Phase:** 0.5
**Stakeholders:** Development Team

**Context:**
Different exit conditions require different urgency levels. Stop losses need immediate execution, while rebalancing can wait.

**Decision:**
Implement 4-level priority hierarchy:
- **CRITICAL:** Market orders, 5s timeout (stop_loss, circuit_breaker)
- **HIGH:** Aggressive limits, 10s timeout (trailing_stop, time_based_urgent, liquidity_dried_up)
- **MEDIUM:** Fair limits, 30s timeout (profit_target, partial_exit_target)
- **LOW:** Conservative limits, 60s timeout (early_exit, edge_disappeared, rebalance)

**Consequences:**
- **Positive:**
  - Capital protection prioritized (CRITICAL fast exits)
  - Efficient for low-urgency exits (LOW patient execution)
  - Clear execution strategies per priority
- **Negative:**
  - More execution paths to test
  - Priority conflicts need resolution
- **Neutral:**
  - Aligns with industry best practices

**References:**
- POSITION_MANAGEMENT_GUIDE_V1.0.md Section 6-7
- REQ-EXIT-001, REQ-EXEC-001

---

### ADR-086: Schema Classification Field Naming (approach/domain)

**Date:** 2025-11-17
**Status:** ✅ Complete
**Phase:** 1.5
**Stakeholders:** Development Team

**Context:**
Three-way schema mismatch blocked Model Manager implementation:
- Documentation: model_type/sport, strategy_type/sport
- Database: category/subcategory
- Manager Code: Expected model_type/sport (from docs)

**Decision:**
Standardize on `approach`/`domain` for both probability_models and strategies tables:
- **approach:** HOW it works (elo, regression, ensemble, value, arbitrage)
- **domain:** WHICH markets (nfl, elections, economics, NULL for multi-domain)

**Consequences:**
- **Positive:**
  - Semantically consistent across tables
  - Future-proof for Phase 2+ expansion
  - More descriptive than generic "type" or "category"
  - Schema drift prevented via automated validation (DEF-P1-008)
- **Negative:**
  - Migration required (Migration 011)
  - Documentation updates across 6+ files
- **Neutral:**
  - Migration 011 took ~2 seconds (metadata-only renames)

**References:**
- Migration 011 implementation
- DATABASE_SCHEMA_SUMMARY_V1.9.md
- scripts/validate_schema.py (DEF-P1-008)
- REQ-DB-006

---

### ADR-087: No Edge Manager Component (Calculated Outputs Pattern)

**Date:** 2025-11-17
**Status:** ✅ Complete
**Phase:** 1.5
**Stakeholders:** Development Team

**Context:**
Phase 1.5 implements manager components. Question: Should we create an Edge Manager to handle edge calculations and queries?

**Decision:**
NO Edge Manager for Phase 1-2. Edges are calculated outputs, not managed entities:
- **Model Manager** calculates edges (part of evaluate())
- **Strategy Manager** queries edges (part of find_opportunities())
- **Database** handles cleanup (TTL-based DELETE)

Phase 1.5 architecture: **3 managers** (Strategy, Model, Position) - NOT 4

**Consequences:**
- **Positive:**
  - Simpler architecture (3 components vs 4)
  - Clearer responsibilities (Model produces, Strategy consumes)
  - Less code (~200-300 lines saved)
  - Easier testing (context-specific edge tests)
- **Negative:**
  - Distributed edge logic (not centralized)
  - Reconsider if Phase 3+ needs ensemble aggregation
- **Neutral:**
  - Edge table acts as message queue between managers

**References:**
- DEVELOPMENT_PHASES_V1.4.md (Phase 1.5 deliverables)
- DATABASE_SCHEMA_SUMMARY_V1.9.md (edges table)
- REQ-TRADING-001, REQ-ML-001

---


### ADR-088: Test Type Categories (Comprehensive Testing Framework)

**Date:** 2025-11-17
**Status:** ✅ Complete
**Phase:** 1.5
**Stakeholders:** Development Team, QA

**Context:**
Phase 1.5 TDD failure exposed testing blind spots. Strategy Manager tests: 17/17 passed with mocks →  13/17 failed with real DB (77% failure rate). Mocking internal infrastructure (get_connection()) created false confidence.

**Decision:**
Establish 8 Test Type Framework for comprehensive coverage:
1. **Unit Tests** - Isolated logic (mock external dependencies)
2. **Property Tests** - Hypothesis mathematical invariants
3. **Integration Tests** - REAL infrastructure (database/config/logging) - ❌ FORBIDDEN to mock
4. **End-to-End Tests** - Complete workflows
5. **Stress Tests** - Infrastructure limits (connection pools, rate limiters)
6. **Race Condition Tests** - Concurrent operations
7. **Performance Tests** - Latency/throughput benchmarks (Phase 5+)
8. **Chaos Tests** - Failure recovery scenarios (Phase 5+)

**Mock Usage Policy:**
- ✅ APPROPRIATE: External APIs, time, randomness, network
- ❌ FORBIDDEN: Internal infrastructure (database, config, logging, connection pools)

**Consequences:**
- **Positive:**
  - Prevents false confidence from mocks
  - Comprehensive coverage (8 types catch different bug categories)
  - Clear guidance (mock usage decision tree)
  - Phase-based implementation roadmap
- **Negative:**
  - Increased test execution time (integration/stress tests slower)
  - Steeper learning curve (Hypothesis, threading, stress testing)
  - More test infrastructure (db_pool, clean_test_data fixtures)
- **Neutral:**
  - Test type requirements matrix (REQ-TEST-012)
  - 8 test directories in tests/ structure

**References:**
- TESTING_STRATEGY_V3.1.md (1,462 lines)
- REQ-TEST-012 through REQ-TEST-019
- ADR-074 (Property-Based Testing)
- ADR-075 (Multi-Source Warning Governance)

---
## ADR Statistics

**Total ADRs:** 68
**Accepted (✅):** 39 (Phase 0-1.5 partial)
**Proposed (🔵):** 28 (Phase 0.7, 1, 2-10)
**Rejected (❌):** 0
**Superseded (⚠️):** 0

**By Phase:**
- Phase 0: 17 ADRs (100% accepted)
- Phase 0.5: 12 ADRs (100% accepted)
- Phase 1: 12 ADRs (6 accepted for DB completion + 6 planned for API best practices)
- Phase 1.5: 4 ADRs (100% accepted - property-based testing POC + schema standardization + no edge manager + 8 test type framework)
- Phase 0.6c: 5 ADRs (100% accepted - includes cross-platform standards)
- Phase 0.7: 6 ADRs (2 accepted: Python 3.14 compatibility + Branch Protection + 4 planned)
- Phase 2: 3 ADRs (0% - planned)
- Phase 3: 2 ADRs (0% - planned)
- Phase 4: 4 ADRs (0% - planned)
- Phase 5: 3 ADRs (0% - planned)

---

## Next Steps

1. **Update ARCHITECTURE_DECISIONS_V2.5** - Add formal ADR numbers to all decisions
2. **Document new ADRs** - As Phase 1-10 progresses
3. **Maintain index** - Update as decisions made/changed
4. **Link from guides** - Use ADR numbers in cross-references

---

**Document Version:** 1.12
**Created:** 2025-10-21
**Last Updated:** 2025-11-17
**Purpose:** Systematic architecture decision tracking and reference
**Critical Changes:**
- v1.10: Added ADR-046 for branch protection strategy (Phase 0.7 retroactive, GitHub branch protection with 6 required CI checks)
- v1.9: Added ADR-055 for production monitoring infrastructure (Sentry hybrid architecture)
- v1.8: Added ADR-078 through ADR-085 for Phases 6-9 analytics infrastructure
- v1.7: Added ADR-076 and ADR-077 for strategic research priorities
- v1.6: Added ADR-074 for property-based testing integration (Hypothesis framework POC complete)
- v1.5: Added ADR-054 for Python 3.14 compatibility (Ruff security rules instead of Bandit)

**For complete ADR details, see:** ARCHITECTURE_DECISIONS_V2.17.md

**END OF ADR INDEX V1.12**
