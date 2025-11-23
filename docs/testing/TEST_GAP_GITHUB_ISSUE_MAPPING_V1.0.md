# Test Gap & Priority GitHub Issue Mapping

---
**Version:** 1.0
**Created:** 2025-11-22
**Purpose:** Map all 15 identified high-priority issues to GitHub issues for tracking
**Audit Source:** COMPREHENSIVE_TEST_AUDIT_PHASE_1.5_V1.0.md
**Analysis Source:** Session 5 Priority Analysis (15 critical/high/medium issues)
**Total Issues:** 15 priorities mapped to GitHub issues #101-#129

---

## Executive Summary

**Total Priorities Identified:** 15 (2 CRITICAL, 5 HIGH, 6 MEDIUM, 2 LOW deferred)
**Total GitHub Issues Created:** 11 (Issues #124-#132 from audit/priorities, #101 from validation, #103 from deferred tasks)
**Total Existing GitHub Issues:** 20 (Issues #102-#121 from PHASE_1.5_DEFERRED_TASKS)
**Coverage:** 100% (all test gaps and priorities have trackable GitHub issues)

---

## 🔴 CRITICAL Priority (2 issues)

### 1. Fix Integration Test Mocks (4-6 hours)
**GitHub Issue:** [#124](https://github.com/mutantamoeba/precog/issues/124)
**Labels:** deferred-task, priority-critical, pattern-violation
**Audit Reference:** Section 5 - Critical Gap #1
**Violation:** REQ-TEST-013 (Pattern 13: Real Fixtures, Not Mocks)

**Files Affected:**
- `tests/integration/test_cli_database_integration.py` (uses `unittest.mock`)
- `tests/integration/test_kalshi_client_integration.py` (mocked API responses)

**Impact:** 77% false positive rate (Phase 1.5 lesson learned)

**Fix:**
- Replace mocks with recorded real API responses (VCR pattern)
- Use demo API with test account for integration tests
- Add real database fixtures (`db_pool`, `db_cursor`, `clean_test_data`)

---

### 2. Add E2E Tests for Critical Path (3-4 hours)
**GitHub Issue:** [#125](https://github.com/mutantamoeba/precog/issues/125)
**Labels:** deferred-task, priority-critical
**Audit Reference:** Section 5 - Critical Gap #2
**Requirement:** REQ-TEST-012 (8 test types required for Critical Path)

**Modules Affected:**
- `src/precog/api_connectors/kalshi_client.py` (97.91% coverage, missing E2E)
- `src/precog/api_connectors/kalshi_auth.py` (missing E2E)

**Test Type Compliance:** 1/8 types (12.5%) → Need 8/8 (100%)

**E2E Tests Needed:**
- Authentication flow: Load key → Generate signature → Get token → Refresh token
- Market fetch flow: Authenticate → API call → Parse → Convert to Decimal → Return TypedDict

---

## 🟡 HIGH Priority (5 issues)

### 3. Add Stress Tests for Infrastructure (4-6 hours)
**GitHub Issue:** [#126](https://github.com/mutantamoeba/precog/issues/126)
**Labels:** deferred-task, priority-high
**Audit Reference:** Section 5 - High Priority Gap #3
**Requirement:** REQ-TEST-012 (Stress tests REQUIRED for Infrastructure tier)

**Modules Affected:**
- `src/precog/config/config_loader.py` (99.21% coverage, no stress tests)
- `src/precog/database/connection.py` (81.82% coverage, no stress tests)
- `src/precog/utils/logger.py` (86.08% coverage, no stress tests)

**Stress Tests Needed:**
- **config_loader.py:** 100 concurrent threads, cache thread-safety, memory leak detection
- **connection.py:** 20 connections (exceeds pool size 10), 1000 rapid acquire/release cycles
- **logger.py:** 10,000 messages/second, 50 concurrent threads, 1 MB messages

---

### 4. Add Property Tests for API Layer (3-4 hours)
**GitHub Issue:** [#127](https://github.com/mutantamoeba/precog/issues/127)
**Labels:** deferred-task, priority-high
**Audit Reference:** Section 5 - High Priority Gap #4
**Pattern:** Pattern 10 (Property-Based Testing with Hypothesis)

**Modules Affected:**
- `src/precog/api_connectors/kalshi_client.py` (no property tests)
- `src/precog/api_connectors/kalshi_auth.py` (no property tests)

**Property Tests Needed:**
- Authentication signature invariants (deterministic, always valid)
- Rate limiting properties (never exceeds 100 req/min)
- Decimal conversion properties (all `*_dollars` fields → Decimal, 4 decimal places)

---

### 5. Fix 21 Validation Violations (3-4 hours)
**GitHub Issue:** [#101](https://github.com/mutantamoeba/precog/issues/101)
**Labels:** deferred-task, priority-high, pattern-violation
**Source:** PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-002)

**Violations:** 21 validation failures from pre-push hooks
- SCD Type 2 queries missing `row_current_ind` filters (24 queries total)
- Integration test files using mocks instead of real fixtures (2 files)

**Impact:** Critical pattern violations blocking Phase 2 start

---

### 6. Fix Mypy Test Type Hints Regression (5-7 hours)
**GitHub Issue:** [#131](https://github.com/mutantamoeba/precog/issues/131)
**Labels:** deferred-task, priority-high
**Priority:** HIGH
**Source:** warning_baseline.json, SESSION_HANDOFF.md

**Regression:** Mypy test type hints: 40 → 74 errors (+34 errors)

**Error Categories:**
- `dict | None` indexing errors (type narrowing needed)
- `Factory` type annotations (function vs type mismatch)
- `arg-type` mismatches (Decimal vs float, list vs tuple)

**Impact:** Offsets SESSION 4 warning reductions (net +6 instead of -28)

---

### 7. Add TypedDict Return Types for Manager Methods (2-3 hours)
**GitHub Issue:** [#103](https://github.com/mutantamoeba/precog/issues/103)
**Labels:** deferred-task, priority-high
**Source:** PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-004)

**Modules Affected:**
- `src/precog/trading/strategy_manager.py`
- `src/precog/analytics/model_manager.py`
- `src/precog/trading/position_manager.py`

**Impact:** Manager methods return `dict[str, Any]` instead of typed dictionaries

**Fix:** Create TypedDict classes for all manager return types (Strategy, Model, Position)

---

## 🟢 MEDIUM Priority (6 issues)

### 8. Add E2E Tests for Business Logic (6-8 hours)
**GitHub Issue:** [#128](https://github.com/mutantamoeba/precog/issues/128)
**Labels:** deferred-task, priority-medium
**Audit Reference:** Section 5 - Medium Priority Gap #5
**Requirement:** REQ-TEST-012 (E2E tests required for Business Logic tier)

**Modules Affected:**
- `src/precog/trading/strategy_manager.py` (86.59% coverage, no E2E)
- `src/precog/analytics/model_manager.py` (92.66% coverage, no E2E)
- `src/precog/trading/position_manager.py` (91.04% coverage, no E2E)

**E2E Tests Needed:**
- Strategy lifecycle: Create → Activate → A/B test → Deactivate → Archive
- Model lifecycle: Create → Train → Evaluate → Set active → Retirement
- Position lifecycle: Open → Price update → Trailing stop → Profit target → Close → P&L

---

### 9. Add Security Tests (4-6 hours)
**GitHub Issue:** [#129](https://github.com/mutantamoeba/precog/issues/129)
**Labels:** deferred-task, priority-medium, security
**Audit Reference:** Section 3.4 - Security Test Coverage

**Security Tests Missing:**
- SQL injection resistance (CRUD operations with malicious input)
- Secrets not logged (credentials never appear in logs)
- Connection string sanitization (passwords masked in errors)
- API key rotation (old keys rejected after rotation)

**Impact:** Vulnerabilities not tested before production deployment

---

### 10. Fix MASTER_INDEX Documentation Gaps (1.5 hours)
**GitHub Issue:** [#130](https://github.com/mutantamoeba/precog/issues/130)
**Labels:** deferred-task, priority-medium
**Priority:** MEDIUM
**Source:** validate_docs.py output

**Gaps Identified:**
- 29 missing documents (referenced but not found)
- 12 stale references (documents moved/renamed)

**Impact:** Documentation drift, broken cross-references

**Fix:** Run validate_docs.py, update all cross-references

---

### 11. Add list_strategies() Method (1-2 hours)
**GitHub Issue:** [#132](https://github.com/mutantamoeba/precog/issues/132)
**Labels:** deferred-task, priority-medium
**Priority:** MEDIUM
**Source:** User request, Session 5 analysis

**Current State:** strategy_manager.py missing flexible query method

**Existing:**
- `get_active_strategies()` - Returns only active (no flexibility)
- `get_strategies_by_name()` - Filters by name only

**Missing:** `list_strategies()` with optional filters (status, version, strategy_type)

**Pattern:** Mirror existing `list_models()` in model_manager.py (line 370)

**Fix:** Add `list_strategies(status=None, version=None, strategy_type=None)` to match model_manager API

---

### 12. Add Database Schema Validation Tests (3-4 hours)
**GitHub Issue:** [#102](https://github.com/mutantamoeba/precog/issues/102)
**Labels:** deferred-task, priority-high
**Source:** PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-003)

**Module:** `scripts/validate_schema_consistency.py`

**Tests Needed:**
- Schema consistency validation (25 tables match schema definition)
- Column type validation (Decimal vs float, timestamp vs datetime)
- Foreign key constraint validation (all FKs reference existing tables)

---

### 13. Automate Migration Testing (2 hours)
**GitHub Issue:** [#104](https://github.com/mutantamoeba/precog/issues/104)
**Labels:** deferred-task, priority-high
**Source:** PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-005)

**Current State:** Migrations applied manually, no automated testing

**Fix:** Create `scripts/test_migrations.py` to:
- Apply each migration sequentially (001 → 002 → ... → 023)
- Verify schema after each migration
- Test rollback functionality (if supported)

---

### 14. Standardize Database Connection Handling (30 minutes)
**GitHub Issue:** [#105](https://github.com/mutantamoeba/precog/issues/105)
**Labels:** deferred-task, priority-high
**Source:** PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-006)

**Inconsistency:** Some files use `get_connection()` directly, others import from different modules

**Fix:** Standardize all imports to `from precog.database.connection import get_connection`

---

### 15. Improve Error Messages with Context (1 hour)
**GitHub Issue:** [#106](https://github.com/mutantamoeba/precog/issues/106)
**Labels:** deferred-task, priority-medium
**Source:** PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-007)

**Current State:** Error messages lack context (e.g., "Invalid strategy" without strategy_id)

**Fix:** Add context to all error messages (include entity IDs, attempted values, validation constraints)

**Example:**
```python
# Before:
raise ValueError("Invalid strategy")

# After:
raise ValueError(f"Invalid strategy (strategy_id={strategy_id}, status='{status}', valid_statuses={VALID_STATUSES})")
```

---

## 🔵 LOW Priority (Deferred to Phase 3+)

### 16. Add Performance Tests (8-10 hours)
**Status:** DEFERRED to Phase 5
**Audit Reference:** Section 5 - Low Priority Gap #7

**Reason:** "Make it work, make it right, make it fast" - Premature optimization

**Deferred Until:** Phase 5 (Trading execution performance matters)

---

### 17. Add Chaos Tests (6-8 hours)
**Status:** DEFERRED to Phase 5
**Audit Reference:** Section 5 - Low Priority Gap #8

**Reason:** Resilience testing not critical until production deployment

**Deferred Until:** Phase 5 (Production deployment resilience)

---

## Summary Statistics

**Total Priorities:** 15 (17 including deferred)
**GitHub Issues Created:** 11 new issues (#124-#132, plus #101, #103)
**Existing GitHub Issues:** 20 issues (#102-#121 from deferred tasks)
**Coverage:** 100% (all test gaps and priorities have trackable GitHub issues)

**Effort Breakdown:**
- 🔴 CRITICAL: 7-10 hours (2 issues)
- 🟡 HIGH: 21-29 hours (5 issues)
- 🟢 MEDIUM: 21-27 hours (6 issues)
- 🔵 LOW: 14-18 hours (2 issues, deferred to Phase 5)

**Total Effort:** 49-66 hours (excluding deferred LOW priority)

**Phase 2 Prerequisites (CRITICAL only):** 7-10 hours
**Phase 2 Week 1 (CRITICAL + HIGH):** 28-39 hours
**Phase 2 Complete (CRITICAL + HIGH + MEDIUM):** 49-66 hours

---

## Issue Closure Workflow

**When closing GitHub issues:**

1. **Via PR (Preferred):**
   ```bash
   gh pr create --title "..." --body "Closes #124

   [PR description]"
   ```
   - GitHub auto-closes issue when PR merges
   - Update documentation status in PR (mark as Complete in deferred tasks doc)

2. **Manual Closure:**
   ```bash
   gh issue close 124 --comment "Fixed in commit abc1234. [Details]"
   ```
   - Update documentation manually after closure

3. **Reconciliation Check (Phase Completion):**
   ```bash
   bash scripts/reconcile_issue_tracking.sh
   ```
   - Verify GitHub issues match documentation status
   - Prevents "I thought we completed that" confusion

---

## Recommendation

**Phase 2 Start Protocol:**
1. ✅ Complete 2 CRITICAL issues (#124, #125) - 7-10 hours
2. ✅ Run Phase 2 Start Protocol (validate_phase_completion.py)
3. ✅ Create Phase 2 master todo list (include HIGH priority issues #126-#127, #101, #103)

**Phase 2 Week 1:**
- Complete 5 HIGH priority issues (21-29 hours)
- Begin 6 MEDIUM priority issues (21-27 hours)

**Phase 2 Complete:**
- All CRITICAL + HIGH + MEDIUM issues resolved (49-66 hours total)
- All test gaps from audit addressed
- All deferred tasks from Phase 1.5 completed

---

**END OF TEST_GAP_GITHUB_ISSUE_MAPPING_V1.0.md**
