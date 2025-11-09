# Warning Debt Tracker

**Version:** 1.1
**Created:** 2025-11-08
**Last Updated:** 2025-11-09
**Purpose:** Track and manage technical debt in the form of warnings across the codebase
**Related:** Phase 1.5 Warning Governance, Zero-Regression Policy
**Changes in V1.1:** Baseline updated (429→312, -117 warnings), YAML warnings eliminated, ADR warnings reclassified (informational→actionable)

---

## Overview

This document tracks all warnings in the codebase (test warnings, deprecation warnings, resource warnings, etc.) to prevent technical debt accumulation through warning fatigue.

**Why This Matters:**
- **Warning Fatigue:** Once warnings appear, developers ignore them → Real warnings get missed → Bugs in production
- **Multiplicative Effect:** 1 bug × 248 tests = 248 warnings (noise drowns signal)
- **Zero-Warning Policy:** New warnings block PRs → Forces immediate action → Prevents debt accumulation

**Warning Governance Model (UPDATED 2025-11-09):**
1. **Baseline:** 312 warnings (was 429, -117 improvement = -27%)
2. **Zero Regression:** New warnings → pre-push hooks FAIL → THREE OPTIONS:
   - **Option A:** Fix immediately (recommended)
   - **Option B:** Defer with tracking (create WARN-XXX entry + update baseline)
   - **Option C:** Update baseline only (NOT recommended - only for upstream/false positives)
3. **Active Reduction:** Each phase targets 80-100 warning fixes (Phase 1.5: -117 ✅)
4. **All Baseline Warnings Tracked:** 312 warnings = 7 WARN-XXX entries (WARN-001 through WARN-007)
5. **Zero Target:** Goal is <100 warnings by Phase 2 completion

---

## Current Baseline (2025-11-09)

**Total Warnings:** 312 (was 429, -117 improvement)
**Warning Sources:** pytest (32) + validate_docs (280) + code quality (0)
**Test Suite:** 323 passed, 9 skipped
**Last Measured:** 2025-11-09T15:30:00Z
**Major Changes:** YAML float warnings ELIMINATED (111→0), pytest warnings reduced (41→32), ADR warnings RECLASSIFIED (informational→actionable)

### Breakdown by Category

| Category | Count | Severity | Priority | Target Phase | Est. Fix Time | Source |
|----------|-------|----------|----------|--------------|---------------|--------|
| **Documentation Validation (validate_docs.py)** | **280** (was 388) | | | | | |
| ADR Non-Sequential Numbering | 231 | 🟡 Medium | **Actionable** ⚠️ | 2.0 | 4-6 hours | validate_docs.py |
| YAML Float Literals | 0 | - | **FIXED** ✅ | DONE | - | validate_docs.py |
| MASTER_INDEX Missing Docs | 29 (was 27) | 🟡 Medium | Medium | 1.5 | 1 hour | validate_docs.py |
| MASTER_INDEX Deleted Docs | 12 (was 11) | 🟡 Medium | Low | 1.5 | 30 min | validate_docs.py |
| MASTER_INDEX Planned Docs | 8 | 🟢 Low | **Expected** | N/A | N/A | validate_docs.py |
| **Test Warnings (pytest)** | **32** (was 41) | | | | | |
| Hypothesis Decimal Precision | 17 (was 19) | 🟡 Low | Medium | 1.5 | 2-3 hours | pytest |
| ResourceWarning (Unclosed Files) | 11 (was 13) | 🟡 Medium | **High** | 1.5 | 1 hour | pytest |
| pytest-asyncio Deprecation | 4 | 🟡 Medium | Low | N/A (upstream) | N/A | pytest |
| structlog UserWarning | 1 | 🟢 Low | Low | DONE | - | pytest |
| **Actionable Warnings** | **313** (was 182) | - | - | **1.5-2.0** | **~13 hours** | Both |

**Breakdown by Actionability (UPDATED 2025-11-09):**
- **Informational:** 0 (was 231 - ADR warnings RECLASSIFIED to actionable)
- **Expected (intentional):** 8 (planned docs only)
- **Upstream (not our code):** 4 (pytest-asyncio - will fix when dependency updates)
- **Actionable (must fix or defer):** 313 (was 182, +131 from ADR reclassification - ALL tracked as WARN-XXX below)

**Three Warning Sources:**
1. **pytest warnings (41)**: Test execution warnings (`python -m pytest -W default`)
2. **validate_docs warnings (388)**: Documentation validation (`python scripts/validate_docs.py`)
   - YAML float literals (111)
   - ADR non-sequential (231 - informational)
   - MASTER_INDEX issues (46 total)
3. **Code quality (0)**: Ruff and Mypy (`bash scripts/validate_quick.sh`) - all fixed ✅

---

## Deferred Warning Fixes

### WARN-001: Fix ResourceWarning - Unclosed File Handles (🔴 HIGH PRIORITY)

**Status:** 🔵 Planned (Phase 1.5)
**Category:** resource_warning_unclosed_files
**Count:** 13 warnings
**Severity:** 🟡 Medium (file handle leaks in tests)
**Priority:** 🔴 High (affects all logger tests)

**Description:**
13 tests create `FileHandler` objects that aren't explicitly closed, causing ResourceWarnings:
```
utils/logger.py:194: ResourceWarning: unclosed file <_io.TextIOWrapper
  name='...precog_2025-11-08.log' mode='a' encoding='utf-8'>
```

**Root Cause:**
`logging.basicConfig()` creates FileHandler but test teardown doesn't close it.

**Impact:**
- Tests leak file handles (OS cleans up on process exit, but not ideal)
- Noise in test output (13 warnings)
- Could cause issues with file locking on Windows

**Proposed Fix:**
**Option A:** Add explicit handler cleanup in test teardown
```python
@pytest.fixture(scope="function")
def temp_logger(tmp_path):
    log_dir = tmp_path / "logs"
    logger = setup_logging(log_dir=str(log_dir))
    yield logger
    # Cleanup all handlers
    for handler in logging.root.handlers[:]:
        handler.close()
        logging.root.removeHandler(handler)
```

**Option B:** Refactor `setup_logging()` to use context manager
```python
@contextmanager
def logging_context(log_dir="logs"):
    logger = setup_logging(log_dir=log_dir)
    try:
        yield logger
    finally:
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
```

**Acceptance Criteria:**
- ✅ Zero ResourceWarnings in `python -m pytest tests/ -v -W default`
- ✅ All 248 tests still passing
- ✅ File handles properly closed (verified with `lsof` on Linux or Process Explorer on Windows)

**Estimate:** 1 hour
**Target Phase:** 1.5
**Assigned To:** TBD

---

### WARN-002: Fix Hypothesis Decimal Precision Warnings (🟡 MEDIUM PRIORITY)

**Status:** 🔵 Planned (Phase 1.5)
**Category:** hypothesis_decimal_precision
**Count:** 19 warnings
**Severity:** 🟢 Low (cosmetic - tests still work)
**Priority:** 🟡 Medium (affects property tests)

**Description:**
19 warnings from Hypothesis property tests using float min/max values that cannot be exactly represented as Decimals:
```
hypothesis/strategies/_internal/core.py:1776: HypothesisDeprecationWarning:
  0.1 cannot be exactly represented as a decimal with places=2
```

**Root Cause:**
Using `decimals(min_value=0.1, max_value=0.9, places=4)` - Hypothesis converts float 0.1 to Decimal, but 0.1 is not exactly representable in binary floating point.

**Current Code (tests/test_decimal_properties.py):**
```python
@given(
    price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4),
    spread=st.decimals(min_value=0.0001, max_value=0.0100, places=4),  # ← Float!
)
```

**Impact:**
- Noise in test output (19 warnings)
- No functional impact (Decimal precision still validated correctly)
- Hypothesis deprecation warning (may become error in future versions)

**Proposed Fix:**
Use `Decimal('0.0001')` instead of float `0.0001`:
```python
@given(
    price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=4),
    spread=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("0.0100"), places=4),
)
```

**Files to Update:**
- `tests/test_decimal_properties.py` (all `@given` decorators with decimals strategy)

**Acceptance Criteria:**
- ✅ Zero Hypothesis deprecation warnings
- ✅ All property tests still passing (100 examples per test)
- ✅ Decimal precision still validated (no loss of test coverage)

**Estimate:** 2-3 hours (find all instances, update, verify tests)
**Target Phase:** 1.5
**Assigned To:** TBD

---

### WARN-003: Remove format_exc_info Processor (🟢 LOW PRIORITY)

**Status:** 🔵 Planned (Phase 1.5)
**Category:** structlog_format_exc_info
**Count:** 1 warning
**Severity:** 🟢 Low (cosmetic)
**Priority:** 🟢 Low (not affecting functionality)

**Description:**
structlog suggests removing `format_exc_info` processor when using `ConsoleRenderer`:
```
structlog/stdlib.py:1160: UserWarning: Remove `format_exc_info` from your
  processor chain if you want pretty exceptions.
```

**Root Cause:**
Both `format_exc_info` and `ConsoleRenderer` handle exception formatting, causing redundancy.

**Current Code (utils/logger.py lines 199-210):**
```python
shared_processors = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,  # ← Remove this
]
```

**Impact:**
- 1 warning in test output
- No functional impact (exceptions still render correctly)
- `ConsoleRenderer` handles exception formatting when `format_exc_info` is absent

**Proposed Fix:**
Remove `structlog.processors.format_exc_info` from `shared_processors`:
```python
shared_processors = [
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    # Removed: format_exc_info (ConsoleRenderer handles exception formatting)
]
```

**Acceptance Criteria:**
- ✅ Zero structlog UserWarnings
- ✅ Exceptions still render correctly in console output
- ✅ Exception formatting still works in file output (JSON)

**Estimate:** 15 minutes
**Target Phase:** 1.5
**Assigned To:** TBD

---

### WARN-004: Convert YAML Float Literals to String Format (🟢 LOW PRIORITY)

**Status:** 🔵 Planned (Phase 1.5)
**Category:** yaml_float_literals
**Count:** 111 warnings
**Severity:** 🟢 Low (best practice, not broken)
**Priority:** 🟢 Low (no functional impact)

**Description:**
111 warnings from `validate_docs.py` about YAML config files using float literals instead of string format for Decimal-converted values:
```
[WARN] markets.yaml: Float detected in Decimal field 'kelly_fraction': 0.25
  RECOMMENDATION: Change to string format: kelly_fraction: "0.25"
```

**Root Cause:**
YAML files use float literals for precision-critical values:
```yaml
# Current (causes warning):
kelly_fraction: 0.25
max_spread: 0.05
min_edge: 0.06

# Recommended (no warning):
kelly_fraction: "0.25"
max_spread: "0.05"
min_edge: "0.06"
```

**Impact:**
- Warnings in documentation validation output (111 warnings)
- No functional impact (config_loader._convert_to_decimal() handles both formats)
- Potential float representation edge cases (0.1 as float ≠ 0.1 as string)

**Why It Matters (Decimal Precision):**
- Float literals: `0.1` in YAML → Python float `0.1` → Decimal("0.1000000000000000055511151231257827021181583404541015625")
- String literals: `"0.1"` in YAML → Python string "0.1" → Decimal("0.1") (exact)
- config_loader uses `Decimal(str(value))` which handles floats, but strings are safer

**Proposed Fix:**
Update 111 float values across 7 YAML files:
- `config/markets.yaml` (50 values)
- `config/position_management.yaml` (67 values)
- `config/probability_models.yaml` (58 values)
- `config/trade_strategies.yaml` (40 values)
- `config/trading.yaml` (26 values)
- `config/data_sources.yaml` (4 values)
- `config/system.yaml` (0 values - no issues)

**Implementation:**
```bash
# Option A: Manual (tedious but safe)
# Edit each file, wrap float values in quotes

# Option B: Automated (faster but needs validation)
python scripts/fix_yaml_floats.py  # Convert all float literals to strings
python -m pytest tests/test_config_loader.py  # Verify no regressions
python scripts/validate_docs.py  # Confirm 111 → 0 warnings
```

**Acceptance Criteria:**
- ✅ Zero float literal warnings from `validate_docs.py`
- ✅ All 48 config_loader tests still passing
- ✅ Config values remain identical after conversion
- ✅ No change in Decimal precision (verified with property tests)

**Estimate:** 2-3 hours
**Target Phase:** 1.5
**Assigned To:** TBD

---

### WARN-005: Update MASTER_INDEX with Missing Docs (🟡 MEDIUM PRIORITY)

**Status:** 🔵 Planned (Phase 1.5)
**Category:** master_index_missing
**Count:** 27 warnings
**Severity:** 🟡 Medium (discoverability issues)
**Priority:** 🟡 Medium (documentation consistency)

**Description:**
27 documents exist in the repository but are not listed in MASTER_INDEX:
- CLAUDE_CODE_HANDOFF_UPDATED_V1_0.md
- PHASE_0.7_DEFERRED_TASKS_V1.3.md
- VERSION_HEADERS_GUIDE_V2_1.md
- ... (24 more docs)

**Root Cause:**
Documents were created but MASTER_INDEX was not updated to include them.

**Impact:**
- Reduced discoverability (users don't know these docs exist)
- Documentation inconsistency
- Harder to find relevant specifications

**Proposed Fix:**
Add missing documents to MASTER_INDEX with appropriate metadata:
```markdown
| DOC_NAME_VX.X.md | ✅ | vX.X | `/docs/category/` | Priority | Phase | Status | Description |
```

**Acceptance Criteria:**
- ✅ All 27 documents added to MASTER_INDEX
- ✅ Zero "documents exist but not in MASTER_INDEX" warnings from validate_docs.py
- ✅ Verify all entries have correct metadata (version, location, status)

**Estimate:** 1 hour
**Target Phase:** 1.5
**Assigned To:** TBD

---

### WARN-006: Clean Up MASTER_INDEX Deleted Docs (🟡 LOW PRIORITY)

**Status:** 🔵 Planned (Phase 1.5)
**Category:** master_index_deleted
**Count:** 11 warnings
**Severity:** 🟡 Medium (broken references)
**Priority:** 🟢 Low (cleanup task)

**Description:**
11 documents are listed in MASTER_INDEX but no longer exist in the repository:
- BACKTESTING_PROTOCOL_V1.0.md
- DEPLOYMENT_GUIDE_V1.0.md
- KELLY_CRITERION_GUIDE_V1.0.md
- ... (8 more docs)

**Root Cause:**
Documents were deleted or moved to _archive/ but MASTER_INDEX entries were not removed.

**Impact:**
- Broken references in MASTER_INDEX
- Confusion when users try to find these docs
- Stale documentation index

**Proposed Fix:**
Remove or archive entries for deleted documents:
```markdown
# Option 1: Remove entirely (if superseded)
# Delete row from MASTER_INDEX

# Option 2: Mark as archived (if historical value)
| DOC_NAME_VX.X.md | 📦 | vX.X | `/docs/_archive/` | ... | 📦 Archived |
```

**Acceptance Criteria:**
- ✅ All 11 deleted documents removed from MASTER_INDEX or marked as archived
- ✅ Zero "documents listed but no longer exist" warnings from validate_docs.py
- ✅ Add notes explaining why documents were removed/archived

**Estimate:** 30 minutes
**Target Phase:** 1.5
**Assigned To:** TBD

---

### WARN-007: ADR Non-Sequential Numbering (ℹ️ INFORMATIONAL)

**Status:** ℹ️ Informational (Not Actionable)
**Category:** adr_non_sequential
**Count:** 231 warnings
**Severity:** 🟢 Low (informational only)
**Priority:** ℹ️ Informational (expected behavior)

**Description:**
231 ADR numbers are missing from the sequence (ADR-001 through ADR-300), but only 72 ADRs exist.

**Why Informational:**
- ADR numbers are assigned sequentially during planning, but not all planned ADRs are implemented
- Missing numbers represent:
  - Rejected proposals (decided not to implement)
  - Deferred decisions (future phases)
  - Placeholder numbers for future use
- This is EXPECTED behavior - ADR numbering allows gaps by design

**Impact:**
- None - this is by design
- Gaps in numbering are acceptable and intentional

**No Fix Required:**
ADR numbering does NOT need to be sequential. Gaps are expected and documented.

**Acceptance Criteria:**
- N/A - this is informational only
- Document this as expected behavior in ARCHITECTURE_DECISIONS header

**Estimate:** N/A (no fix needed)
**Target Phase:** N/A
**Assigned To:** N/A

---

## Non-Actionable Warnings (Upstream Dependencies)

### pytest-asyncio Deprecation Warnings (4 warnings)

**Status:** ⏸️ Deferred (Waiting for upstream fix)
**Source:** `pytest-asyncio` plugin
**Count:** 4 warnings
**Severity:** 🟡 Medium (will break in Python 3.16)

**Warnings:**
1. `asyncio.iscoroutinefunction` deprecated (3 locations in plugin.py)
2. `asyncio.get_event_loop_policy` deprecated (1 location in plugin.py)

**Why Deferred:**
- Not our code (pytest-asyncio dependency)
- Will be fixed when pytest-asyncio updates for Python 3.16 compatibility
- Python 3.16 release: ~2026 (1+ year away)

**Action:** Monitor pytest-asyncio releases, update when fixed

---

### Coverage Warning: No Contexts Measured (1 warning)

**Status:** ⏸️ Expected (Intentional - Not Using Coverage Contexts)
**Source:** `coverage.html`
**Count:** 1 warning
**Severity:** 🟢 Low (informational)

**Warning:**
```
CoverageWarning: No contexts were measured
```

**Why Expected:**
- We're not using coverage contexts (dynamic_context feature)
- This is intentional - contexts are for advanced coverage tracking (per-test coverage)
- Not needed for current workflow

**Action:** None (suppress warning or ignore)

---

## Warning Governance Policy

### Enforcement Rules

1. **Baseline Locked:** 429 warnings (as of 2025-11-08)
   - pytest: 41 warnings
   - validate_docs: 388 warnings (231 informational + 157 actionable)
   - Code quality (Ruff, Mypy): 0 warnings ✅
2. **No Regression:** New warnings → CI fails → Must fix before merge
3. **Baseline Updates:** Require explicit approval + documentation in this file
4. **Phase Targets:** Each phase reduces actionable warnings by 20-30
5. **Zero Goal:** Target 0 actionable warnings by Phase 2 completion

### Measurement Commands

**Run Full Warning Scan (ALL sources):**
```bash
# 1. pytest warnings
python -m pytest tests/ -v -W default --tb=no 2>&1 | tee pytest_warnings.txt

# 2. validate_docs warnings
python scripts/validate_docs.py 2>&1 | tee validate_docs_warnings.txt

# 3. Code quality (should be 0)
bash scripts/validate_quick.sh 2>&1 | tee validation_output.txt
```

**Check Warning Count (comprehensive):**
```bash
python scripts/check_warning_debt.py
# Checks ALL sources: pytest + validate_docs + code quality
# Exit 0 if count <= baseline (429)
# Exit 1 if count > baseline (regression detected)
```

**Categorize Warnings:**
```bash
# pytest warnings by category
grep -E "(DeprecationWarning|ResourceWarning|UserWarning|HypothesisDeprecationWarning)" pytest_warnings.txt | sort | uniq -c

# validate_docs warnings by category
grep "\[WARN\]" validate_docs_warnings.txt | wc -l
```

### CI Integration (Phase 0.7+ Future)

**Pre-Push Hook:**
```bash
# Run warning check before push
python scripts/check_warning_debt.py
# Blocks push if warnings increased
```

**GitHub Actions:**
```yaml
- name: Warning Debt Check
  run: python scripts/check_warning_debt.py
  # Fails if warnings > baseline
```

---

## Phase Reduction Plan

### Phase 1.5 (Next Phase)
**Target:** Reduce from 41 → 8 warnings (-33 warnings)
**Fixes:**
- ✅ WARN-001: Fix ResourceWarnings (13 → 0)
- ✅ WARN-002: Fix Hypothesis warnings (19 → 0)
- ✅ WARN-003: Remove format_exc_info (1 → 0)

**Remaining:** 8 warnings (5 upstream dependencies + 3 expected)

### Phase 2
**Target:** Reduce from 8 → 5 warnings (-3 warnings)
**Approach:** Suppress expected warnings explicitly
- Suppress coverage "No contexts" warning (1 → 0)
- Keep pytest-asyncio warnings until upstream fix (5 remain)

### Phase 3+
**Target:** Reduce from 5 → 0 warnings
**Blocked By:** pytest-asyncio update for Python 3.16 compatibility
**Monitor:** pytest-asyncio releases, update when available

---

## Update Protocol

**When adding new warnings to baseline:**

1. **Document reason** in this file (new section under "Deferred Warning Fixes")
2. **Update `scripts/warning_baseline.json`** with new count
3. **Commit with explanation** in commit message
4. **Link to REQ/ADR** if warning is from intentional design decision

**Example Commit Message:**
```
Update warning baseline: 41 → 43 warnings (+2)

Added 2 new warnings from hypothesis property tests for Kelly Criterion:
- WARN-004: Kelly fraction calculation precision warnings

Reason: New property tests added in Phase 1.5 for risk management.
Target fix: Phase 2 (2-3 hours to refactor Kelly tests with Decimal)

Updated:
- scripts/warning_baseline.json (41 → 43)
- docs/utility/WARNING_DEBT_TRACKER.md (WARN-004 section)
```

---

## Related Documentation

- **Baseline File:** `scripts/warning_baseline.json`
- **Validation Script:** `scripts/check_warning_debt.py`
- **Phase Completion Protocol:** `docs/utility/PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md`
- **Testing Strategy:** `docs/foundation/TESTING_STRATEGY_V2.0.md`

---

**END OF DOCUMENT**
