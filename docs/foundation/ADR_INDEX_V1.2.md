# Architecture Decision Record Index

---
**Version:** 1.2
**Last Updated:** 2025-10-29
**Status:** ✅ Current
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

### Phase 0.7: CI/CD & Advanced Testing (Planned)

| ADR | Title | Date | Status | Phase | Document |
|-----|-------|------|--------|-------|----------|
| ADR-042 | CI/CD Integration with GitHub Actions | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-043 | Security Testing Integration | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-044 | Mutation Testing Strategy | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.8 |
| ADR-045 | Property-Based Testing with Hypothesis | 2025-10-29 | 🔵 | 0.7 | ARCHITECTURE_DECISIONS_V2.8 |

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

## ADR Statistics

**Total ADRs:** 44
**Accepted (✅):** 33 (Phase 0-0.6c)
**Proposed (🔵):** 11+ (Phase 0.7, 1-10)
**Rejected (❌):** 0
**Superseded (⚠️):** 0

**By Phase:**
- Phase 0: 17 ADRs (100% accepted)
- Phase 0.5: 12 ADRs (100% accepted)
- Phase 1: 6 ADRs (100% accepted)
- Phase 0.6c: 4 ADRs (100% accepted)
- Phase 0.7: 4 ADRs (0% - planned)
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

**Document Version:** 1.2
**Created:** 2025-10-21
**Last Updated:** 2025-10-29
**Purpose:** Systematic architecture decision tracking and reference
**Critical Changes:**
- v1.2: Added 8 new ADRs (ADR-038 through ADR-045) for Phase 0.6c completion and Phase 0.7 planning

**For complete ADR details, see:** ARCHITECTURE_DECISIONS_V2.8.md

**END OF ADR INDEX V1.2**
