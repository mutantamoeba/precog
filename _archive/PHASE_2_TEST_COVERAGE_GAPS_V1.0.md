# Phase 2 Test Coverage Gaps

---
**Version:** 1.0
**Created:** 2025-11-28
**Last Updated:** 2025-11-28
**Purpose:** Document missing test types per TESTING_STRATEGY_V3.3 mandatory requirements
**Reference:** TESTING_STRATEGY_V3.3.md - All 8 test types required for ALL modules
---

## Overview

Following the TESTING_STRATEGY_V3.3 update requiring all 8 test types for all modules regardless of tier, this document tracks the test coverage gaps identified during Phase 2 completion.

**Audit Command:** `python scripts/audit_test_type_coverage.py --summary`

**Current Status:** 0/11 tracked modules passing (all have gaps)

---

## The 8 Required Test Types

| # | Type | Directory | Purpose |
|---|------|-----------|---------|
| 1 | Unit | tests/unit/ | Isolated function logic |
| 2 | Property | tests/property/ | Mathematical invariants (Hypothesis) |
| 3 | Integration | tests/integration/ | Real infrastructure interactions |
| 4 | E2E | tests/e2e/ | Complete workflows |
| 5 | Stress | tests/stress/ | Infrastructure limits |
| 6 | Race | tests/stress/ @pytest.mark.race | Concurrent operation validation |
| 7 | Performance | tests/performance/ | Latency/throughput benchmarks |
| 8 | Chaos | tests/stress/ @pytest.mark.chaos | Failure recovery scenarios |

---

## Critical Path Modules (90%+ Coverage Required)

### 1. kalshi_client (api_connectors)

**Tier:** Critical
**Present:** unit, property, integration, e2e
**Missing:** stress, race, performance, chaos

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| stress | MISSING | HIGH | 2h | Rate limit behavior under load |
| race | MISSING | HIGH | 2h | Concurrent API request handling |
| performance | MISSING | MEDIUM | 1h | API response latency benchmarks |
| chaos | MISSING | MEDIUM | 2h | Network failure recovery |

### 2. kalshi_auth (api_connectors)

**Tier:** Critical
**Present:** unit, property, integration, e2e
**Missing:** stress, race, performance, chaos

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| stress | MISSING | HIGH | 2h | Auth under high throughput |
| race | MISSING | HIGH | 2h | Concurrent signature generation |
| performance | MISSING | MEDIUM | 1h | Signature latency (RSA-PSS) |
| chaos | MISSING | MEDIUM | 2h | Key rotation, auth failures |

### 3. kalshi_poller (schedulers)

**Tier:** Critical
**Present:** unit, property, integration, e2e
**Missing:** stress, race, performance, chaos

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| stress | MISSING | HIGH | 2h | High-frequency polling |
| race | MISSING | HIGH | 2h | Concurrent poll requests |
| performance | MISSING | MEDIUM | 1h | Poll cycle timing |
| chaos | MISSING | MEDIUM | 2h | API unavailable scenarios |

### 4. kalshi_websocket (schedulers)

**Tier:** Critical
**Present:** unit, property, integration, e2e
**Missing:** stress, race, performance, chaos

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| stress | MISSING | HIGH | 2h | Message throughput limits |
| race | MISSING | HIGH | 2h | Concurrent message handling |
| performance | MISSING | MEDIUM | 1h | Message processing latency |
| chaos | MISSING | HIGH | 2h | Connection drop/reconnect |

### 5. market_data_manager (schedulers)

**Tier:** Critical
**Present:** unit, property, e2e, stress, race, chaos
**Missing:** integration, performance

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| integration | MISSING | HIGH | 2h | Real DB + WebSocket integration |
| performance | MISSING | MEDIUM | 1h | Cache lookup latency |

---

## Business Logic Modules (85%+ Coverage Required)

### 6. model_manager (analytics)

**Tier:** Business
**Present:** unit, property, e2e, stress, race, chaos
**Missing:** integration, performance

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| integration | MISSING | MEDIUM | 2h | Real model persistence |
| performance | MISSING | LOW | 1h | Model evaluation timing |

### 7. crud_operations (database)

**Tier:** Business
**Present:** unit, property
**Missing:** integration, e2e, stress, race, performance, chaos

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| integration | MISSING | HIGH | 2h | Real DB transaction tests |
| e2e | MISSING | MEDIUM | 2h | Full CRUD workflows |
| stress | MISSING | HIGH | 2h | High-volume inserts/updates |
| race | MISSING | HIGH | 2h | Concurrent writes |
| performance | MISSING | MEDIUM | 1h | Query latency benchmarks |
| chaos | MISSING | MEDIUM | 2h | DB connection failures |

---

## Infrastructure Modules (80%+ Coverage Required)

### 8. espn_client (api_connectors)

**Tier:** Infrastructure
**Present:** unit, property, integration, e2e, stress, race, chaos
**Missing:** performance

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| performance | MISSING | LOW | 1h | API response latency |

### 9. config_loader (config)

**Tier:** Infrastructure
**Present:** unit, property, stress, race, chaos
**Missing:** integration, e2e, performance

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| integration | MISSING | MEDIUM | 1h | Real file system tests |
| e2e | MISSING | LOW | 1h | Full config loading workflow |
| performance | MISSING | LOW | 0.5h | Config parse timing |

### 10. connection (database)

**Tier:** Infrastructure
**Present:** unit, stress, race, chaos
**Missing:** property, integration, e2e, performance

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| property | MISSING | MEDIUM | 1h | Connection pool invariants |
| integration | MISSING | HIGH | 1h | Real PostgreSQL connections |
| e2e | MISSING | LOW | 1h | Full connection lifecycle |
| performance | MISSING | LOW | 0.5h | Connection latency |

### 11. logger (utils)

**Tier:** Infrastructure
**Present:** unit, stress, race, chaos
**Missing:** property, integration, e2e, performance

| Test Type | Status | Priority | Effort | Notes |
|-----------|--------|----------|--------|-------|
| property | MISSING | LOW | 1h | Log format invariants |
| integration | MISSING | LOW | 1h | Real file logging |
| e2e | MISSING | LOW | 1h | Full logging workflow |
| performance | MISSING | LOW | 0.5h | Log write latency |

---

## Summary Statistics

### Gap Analysis by Test Type

| Test Type | Modules Missing | Priority |
|-----------|-----------------|----------|
| performance | 11/11 (100%) | Most Common Gap |
| integration | 7/11 (64%) | |
| stress | 5/11 (45%) | |
| race | 5/11 (45%) | |
| chaos | 5/11 (45%) | |
| e2e | 5/11 (45%) | |
| property | 2/11 (18%) | |
| unit | 0/11 (0%) | All covered |

### Effort Estimation

| Priority | Test Count | Estimated Hours |
|----------|------------|-----------------|
| HIGH | 16 tests | ~32 hours |
| MEDIUM | 12 tests | ~16 hours |
| LOW | 11 tests | ~9 hours |
| **TOTAL** | **39 tests** | **~57 hours** |

---

## Recommended Implementation Order

### Phase 2.1 - Critical Path Stress/Race Tests (16h)

1. **kalshi_client stress/race** - Rate limiting under load
2. **kalshi_auth stress/race** - Concurrent auth signature generation
3. **kalshi_poller stress/race** - High-frequency polling behavior
4. **kalshi_websocket stress/race/chaos** - Connection stability

### Phase 2.2 - Database Robustness (12h)

5. **crud_operations stress/race** - Concurrent database writes
6. **crud_operations integration** - Real DB transaction tests
7. **connection integration** - Real PostgreSQL connection tests

### Phase 2.3 - Performance Baseline (8h)

8. Create `tests/performance/` directory structure
9. Add `@pytest.mark.performance` marker
10. Implement latency benchmarks for all 11 modules

### Phase 2.4 - Remaining Gaps (21h)

11. Missing integration tests
12. Missing e2e tests
13. Missing property tests (connection, logger)
14. Missing chaos tests for critical path

---

## Enforcement Timeline

| Milestone | Date | Action |
|-----------|------|--------|
| Monitoring | 2025-11-28 | Audit script runs in pre-push (Step 11) - informational |
| Warning | 2025-12-15 | Add `--strict` to pre-push to warn on gaps |
| Blocking | 2026-01-01 | Gaps block pushes to main |

---

## Related Documents

- `docs/foundation/TESTING_STRATEGY_V3.3.md` - All 8 test types mandatory
- `scripts/audit_test_type_coverage.py` - Automated gap detection
- `.git/hooks/pre-push` - Step 11 runs audit automatically

---

**END OF DOCUMENT**
