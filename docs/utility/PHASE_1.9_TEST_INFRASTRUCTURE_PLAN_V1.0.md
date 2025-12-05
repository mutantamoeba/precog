# Phase 1.9: Test Infrastructure & Process Hardening

**Version:** 1.0
**Date:** 2025-11-30
**Status:** BLOCKING - Must complete before Phase 2
**GitHub Issue:** #165
**Estimated Effort:** ~93 hours (~3 weeks at 30h/week)

---

## Executive Summary

Phase 1.9 is a **blocking phase** that addresses critical issues in the testing infrastructure:

| Issue | Count | Impact |
|-------|-------|--------|
| FAILED tests | 2 | 🔴 Real bugs in production code |
| SKIPPED tests | 33 | ⚠️ Tests not executing |
| XFAIL tests | 5 | ⚠️ Known gaps accepted |
| Missing test types | 10/11 modules | 🔴 Incomplete coverage |

**User Priorities (verbatim):**
1. All 8 test types EXECUTED prior to push
2. All issues fixed - no skips without explicit permission
3. Avoid quick fixes and tech debt
4. Efficient, non-redundant testing process

---

## Current State Analysis

### Test Results Snapshot (2025-11-30)

```
Total: 1,196 tests
├── PASSED:  1,156 (96.7%)
├── FAILED:     2 (0.2%)
├── SKIPPED:   33 (2.8%)
└── XFAIL:      5 (0.4%)
```

### Root Causes Identified

#### 1. Process Gap: No Enforcement

| Problem | Current State | Required State |
|---------|--------------|----------------|
| Pre-push tests | Unit + Property only | All 8 types |
| CI continue-on-error | `true` (failures ignored) | `false` (strict) |
| Windows vs Linux CI | Different test suites | Identical |
| Skip tracking | None | Explicit approval |

#### 2. Infrastructure Gap: Missing Prerequisites

| Problem | Details | Fix |
|---------|---------|-----|
| Kalshi E2E credentials | Wrong variable names | Update test file |
| Schema validation | `game_states` missing columns | Run migration |
| Performance tests | Directory doesn't exist | Create framework |

#### 3. Coverage Gap: Test Types Not Implemented

| Module | Missing Types |
|--------|--------------|
| kalshi_client | stress, race, performance, chaos |
| kalshi_auth | stress, race, performance, chaos |
| kalshi_poller | stress, race, performance, chaos |
| kalshi_websocket | stress, race, performance, chaos |
| market_data_manager | performance |
| model_manager | performance |
| espn_client | performance |
| config_loader | integration, e2e, performance |
| connection | property, integration, e2e, performance |
| logger | property, integration, e2e, performance |
| crud_operations | ✅ Complete (only passing module) |

---

## Detailed Problem Analysis

### Failed Tests (2)

#### 1. test_scd_type2_columns_exist

**Location:** `tests/integration/database/test_migration_idempotency.py`

**Error:**
```
AssertionError: SCD Type 2 column 'row_end_ts' missing from 'game_states'
```

**Root Cause:** `game_states` table doesn't have SCD Type 2 columns

**Fix:** Either:
- Add migration to add columns to `game_states`
- OR update test to exclude `game_states` from SCD Type 2 validation

**Recommended:** Add migration (proper fix)

---

#### 2. test_not_null_constraint_on_required_fields

**Location:** `tests/property/test_database_crud_properties.py`

**Error:**
```
FlakyFailure: Falsified on the first call but did not on a subsequent one
DID NOT RAISE any of (<class 'psycopg2.IntegrityError'>, <class 'TypeError'>)
```

**Root Cause:** Test expects NOT NULL constraint on `ticker` field, but database allows NULL

**Fix:** Either:
- Add NOT NULL constraint to market ticker
- OR fix test to match actual schema

**Recommended:** Verify schema intention, fix accordingly

---

### Skipped Tests Analysis (33)

#### Category A: Kalshi E2E - Wrong Credential Variables (15 tests)

**Location:** `tests/e2e/api_connectors/test_kalshi_e2e.py`

**Problem:**
```python
# Current (WRONG):
pytest.mark.skipif(
    not os.getenv("KALSHI_DEMO_KEY_ID") or not os.getenv("KALSHI_DEMO_KEYFILE"),
    reason="Kalshi demo credentials not configured in .env",
)

# .env has (CORRECT):
DEV_KALSHI_API_KEY=75b4b76e-d191-4855-b219-5c31cdcba1c8
DEV_KALSHI_PRIVATE_KEY_PATH=_keys/kalshi_demo_private.pem
```

**Fix:** Update test file to use correct variable names:
```python
pytest.mark.skipif(
    not os.getenv("DEV_KALSHI_API_KEY") or not os.getenv("DEV_KALSHI_PRIVATE_KEY_PATH"),
    reason="Kalshi dev credentials not configured in .env (DEV_KALSHI_API_KEY, DEV_KALSHI_PRIVATE_KEY_PATH)",
)
```

**Estimated Time:** 2 hours

---

#### Category B: CLI Database Integration (4 tests)

**Location:** `tests/integration/cli/test_cli_database_integration.py`

**Tests:**
1. `test_fetch_balance_updates_with_scd_type2`
2. `test_fetch_markets_upsert_pattern`
3. `test_fetch_settlements_creates_records_and_updates_market_status`
4. `test_fetch_settlements_empty_response`

**Skip Reason:** "SCD Type 2 test infrastructure not ready"

**Fix:** Implement SCD Type 2 test infrastructure or update tests

**Estimated Time:** 6 hours

---

#### Category C: ESPN Tests (3 tests)

**Tests:**
1. `test_situation_data_valid_when_present` - No live NFL games
2. `test_real_nfl_scoreboard_fetch` - Missing VCR cassette
3. `test_real_ncaaf_scoreboard_fetch` - Missing VCR cassette

**Fix:**
- Create VCR cassettes for API responses
- Use conditional skip for "no live games" (acceptable)

**Estimated Time:** 4 hours

---

#### Category D: Error Handling Tests (7 tests)

**Location:** `tests/test_error_handling.py`

**Tests and Skip Reasons:**
1. `test_connection_pool_exhaustion` - Pool exhaustion test
2. `test_database_connection_failure_and_reconnection` - Cannot reinitialize
3. `test_config_loader_invalid_yaml_syntax` - Reloading not supported
4. `test_config_loader_missing_environment_variable` - Reloading not supported
5. `test_config_loader_invalid_data_type` - Reloading not supported
6. `test_logger_file_permission_error` - Tests globally
7. `test_logger_disk_full_simulation` - Tests globally

**Fix:** These tests require infrastructure changes or are testing future features

**Estimated Time:** 6 hours

---

#### Category E: Other Skipped (4 tests)

| Test | Reason | Fix |
|------|--------|-----|
| `test_apply_migrations_path_traversal` | Symlink test not applicable on Windows | Acceptable conditional skip |
| `test_error_handling_invalid_model_type` | Unknown | Investigate |
| `test_old_api_key_rejected_after_rotation` | API key rotation test | Implement or defer |
| `test_crud_operation_with_null_violation` | No NOT NULL constraint | Fix schema or test |

---

### XFAIL Tests Analysis (5)

| Test | Reason | Resolution |
|------|--------|------------|
| `test_http_basic_auth_masked_in_request_logs` | REQ-SEC-009 not implemented - Phase 3+ | Convert to tracked issue |
| `test_reload_under_concurrent_reads` | ConfigLoader not thread-safe | Convert to tracked issue |
| 3 connection pool tests | Reset/isolation issues | Fix tests or convert to issues |

**Decision Required:** For each XFAIL, either:
1. Implement the feature (fix the underlying issue)
2. Convert to tracked GitHub issue with explicit approval

---

## Implementation Plan

### Week 1: Process Hardening + Quick Wins

#### Day 1-2: Process Foundation (8h)

- [ ] **A.1** Define test execution policy document (2h)
  - Document: Which tests run when (pre-commit, pre-push, CI)
  - Document: Approval process for any skips
  - Document: Success criteria for each stage

- [ ] **A.2** Update pre-push to run ALL 8 test types (4h)
  - Modify `.git/hooks/pre-push`
  - Run: unit, property, integration, e2e, stress, race, performance, chaos
  - Set `PRECOG_ENV=test`
  - Add timeout handling for long-running tests

- [ ] **D.1-D.3** Database environment integration (2h)
  - Verify all tests use `PRECOG_ENV=test`
  - Update CI to set `PRECOG_ENV`

#### Day 3-4: CI Alignment (6h)

- [ ] **A.3** Remove `continue-on-error` from CI (2h)
  - Remove from `integration-tests` job
  - Remove from `test-type-coverage` job
  - Verify pipeline fails on any test failure

- [ ] **A.4** Align Windows and Linux CI (3h)
  - Analyze current differences
  - Update `test` job to run identical tests
  - Add integration/property tests to Windows

- [ ] **A.5** Create skip approval workflow (1h)
  - GitHub issue template for skip requests
  - Labeling convention

#### Day 5: Quick Wins (7h)

- [ ] **B.2** Fix Kalshi E2E credential variables (2h)
  - Update `tests/e2e/api_connectors/test_kalshi_e2e.py`
  - Change `KALSHI_DEMO_KEY_ID` → `DEV_KALSHI_API_KEY`
  - Change `KALSHI_DEMO_KEYFILE` → `DEV_KALSHI_PRIVATE_KEY_PATH`
  - Verify all 15 tests now run

- [ ] **B.1** Fix 2 FAILED tests (4h)
  - Fix `test_scd_type2_columns_exist` (schema migration or test update)
  - Fix `test_not_null_constraint_on_required_fields` (schema or test)

- [ ] Verify: Run full test suite (1h)

---

### Week 2: Infrastructure Fixes + Performance Framework

#### Day 1-2: Remaining Skipped Tests (10h)

- [ ] **B.3** Fix ESPN E2E tests (4h)
  - Create VCR cassettes for NFL/NCAAF endpoints
  - Update tests to use cassettes

- [ ] **B.4** Fix CLI database integration tests (6h)
  - Implement SCD Type 2 test infrastructure
  - OR update tests to match current infrastructure

#### Day 3: Error Handling Tests (6h)

- [ ] **B.5** Fix error handling tests (6h)
  - Analyze each test's requirements
  - Fix or convert to tracked issues

#### Day 4-5: XFAIL Resolution + Performance Framework (8h)

- [ ] **B.6** Resolve XFAIL tests (4h)
  - Create GitHub issues for deferred features
  - Remove XFAIL markers (tests become tracked issues)

- [ ] **C.1** Create performance test framework (4h)
  - Create `tests/performance/` directory
  - Create `conftest.py` with timing fixtures
  - Create template for performance tests
  - Add `@pytest.mark.performance` registration

---

### Week 3: Complete Test Type Coverage

#### Day 1-2: Performance Tests (16h)

- [ ] **C.2** Performance tests for all 11 modules (16h)
  - 11 modules × ~1.5h each
  - Focus on response time, throughput, memory

#### Day 3-4: Stress/Race/Chaos Tests (12h)

- [ ] **C.3** Critical module stress tests (12h)
  - kalshi_client: stress, race, chaos (3h)
  - kalshi_auth: stress, race, chaos (3h)
  - kalshi_poller: stress, race, chaos (3h)
  - kalshi_websocket: stress, race, chaos (3h)

#### Day 5: Remaining Coverage + Validation (8h)

- [ ] **C.4** Infrastructure module tests (4h)
  - config_loader: integration, e2e (2h)
  - connection, logger: integration, e2e (2h)

- [ ] **C.5** Property tests for connection/logger (2h)

- [ ] Final validation (2h)
  - Run full test suite
  - Verify 0 skipped, 0 xfail, 0 failed
  - Run audit script in strict mode
  - Document completion

---

## Pre-Push Hook Target Configuration

```bash
# .git/hooks/pre-push - Target State

# Step 2: ALL 8 Test Types (with timing optimization)
{
    run_parallel_check 2 "All Test Types" \
        bash -c "
            PRECOG_ENV=test python -m pytest tests/unit/ -v --no-cov --tb=short -x -n auto &&
            PRECOG_ENV=test python -m pytest tests/property/ -v --no-cov --tb=short -x &&
            PRECOG_ENV=test python -m pytest tests/integration/ -v --no-cov --tb=short -x &&
            PRECOG_ENV=test python -m pytest tests/e2e/ -v --no-cov --tb=short -x &&
            PRECOG_ENV=test python -m pytest tests/stress/ -v --no-cov --tb=short -x &&
            PRECOG_ENV=test python -m pytest tests/performance/ -v --no-cov --tb=short -x &&
            PRECOG_ENV=test python -m pytest tests/chaos/ -v --no-cov --tb=short -x
        "
} &
```

**Estimated Time:** ~5-8 minutes (parallelized where safe)

---

## CI Target Configuration

```yaml
# .github/workflows/ci.yml - Target State

test:
  name: Tests (Python ${{ matrix.python-version }} on ${{ matrix.os }})
  runs-on: ${{ matrix.os }}
  strategy:
    matrix:
      os: [ubuntu-latest, windows-latest]
      python-version: ['3.12', '3.13', '3.14']
    fail-fast: false

  env:
    PRECOG_ENV: test

  steps:
    # ... setup steps ...

    - name: Run ALL test types
      run: |
        python -m pytest tests/unit/ tests/property/ -v -n auto
        python -m pytest tests/integration/ tests/e2e/ -v
        python -m pytest tests/stress/ tests/performance/ tests/chaos/ -v
      # NO continue-on-error - failures MUST block

integration-tests:
  # ... same pattern, NO continue-on-error ...
```

---

## Success Criteria Checklist

Before Phase 1.9 is considered complete:

- [ ] **Process:**
  - [ ] Pre-push runs all 8 test types
  - [ ] CI runs all 8 test types on Windows AND Linux
  - [ ] `continue-on-error: true` removed from all CI jobs
  - [ ] `PRECOG_ENV=test` set in all test contexts

- [ ] **Test Results:**
  - [ ] 0 FAILED tests
  - [ ] 0 SKIPPED tests (without approved GitHub issue)
  - [ ] 0 XFAIL tests (without approved GitHub issue)

- [ ] **Test Coverage:**
  - [ ] 11/11 modules passing `audit_test_type_coverage.py --strict`
  - [ ] All 8 test types present for all modules:
    - [ ] unit
    - [ ] property
    - [ ] integration
    - [ ] e2e
    - [ ] stress
    - [ ] race
    - [ ] performance
    - [ ] chaos

- [ ] **Documentation:**
  - [ ] Test execution policy document created
  - [ ] Skip approval process documented
  - [ ] Phase 1.9 completion report created

---

## References

- **GitHub Issue:** #165 (Phase 1.9: Test Infrastructure & Process Hardening)
- **Testing Strategy:** docs/foundation/TESTING_STRATEGY_V3.3.md
- **Database Environment:** docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
- **Audit Script:** scripts/audit_test_type_coverage.py
- **Pre-push Hook:** .git/hooks/pre-push
- **CI Workflow:** .github/workflows/ci.yml

---

**END OF PHASE_1.9_TEST_INFRASTRUCTURE_PLAN_V1.0.md**
