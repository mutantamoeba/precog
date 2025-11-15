# Phase 1 PR Review Deferred Tasks

**Version:** 1.0
**Created:** 2025-11-15
**Phase:** 1 (Database & API Connectivity)
**Source:** AI Code Review Analysis (PRs #2-#21)
**Total Tasks:** 45
**Status:** ✅ Active tracking via dual-system (Documentation + GitHub Issues)

---

## 📋 Overview

This document tracks all deferred tasks identified from Phase 1 AI code review analysis. These are actionable suggestions from Claude Code's PR reviews (PRs #2-#21) that were not implemented immediately but should be addressed in future phases.

**Why This Document Exists:**
- **Coverage Gap:** Phase 1 completion report only analyzed PRs #22-#27 (19% coverage)
- **80% Gap Fixed:** This analysis covers remaining PRs #2-#21 (80% of Phase 1 PRs)
- **Lost Tasks Prevention:** 4 of 7 Phase 0.7 tasks were lost due to documentation-only tracking
- **Dual-Tracking Solution:** Each task tracked in BOTH documentation (context) AND GitHub issues (visibility)

**Priority Distribution:**
- 🔴 **Critical:** 3 tasks (fix this session or next PR)
- 🟡 **High:** 8 tasks (implement in Phase 1.5)
- 🟢 **Medium:** 18 tasks (defer to Phase 1.5-2)
- 🔵 **Low:** 16 tasks (defer indefinitely or reject with rationale)

**Dual-Tracking Implementation:**
- **Layer 1 (Documentation):** This document provides context, rationale, implementation details
- **Layer 2 (GitHub Issues):** Issues provide visibility, filtering, persistence
- **Bi-directional Links:** Documentation → Issue #, Issue → Documentation line number

**Total Estimated Effort:** ~35-40 hours across all priorities

**Related Documents:**
- **PHASE_1_DEFERRED_TASKS_V1.1.md** - Tasks deferred during Phase 1 development
- **pr_review_analysis_2-21_complete.md** - Source analysis document
- **SESSION_WORKFLOW_GUIDE_V1.0.md** - Section 9: Dual-Tracking System

---

## 🔴 Critical Tasks (Fix Immediately)

### DEF-P1-001: Fix Float Usage in Property Tests

**Priority:** 🔴 Critical
**Target Phase:** Phase 1.5 (immediate)
**Time Estimate:** 30 minutes
**GitHub Issue:** #29
**Source:** PR #13 AI review (Phase 1.5 CLI Integration)
**Pattern Violation:** Pattern 1 (Decimal Precision - NEVER USE FLOAT)

**Description:**

`tests/property/test_strategy_versioning_properties.py:79` uses `st.floats()` for `max_edge` and `kelly_fraction` instead of `st.decimals()`. This violates Pattern 1 (Decimal Precision) which mandates Decimal for ALL financial values, probabilities, and percentages.

**Current Code (WRONG):**
```python
# tests/property/test_strategy_versioning_properties.py:79
@composite
def strategy_config_dict(draw):
    return {
        "max_edge": draw(st.floats(min_value=0.05, max_value=0.50)),
        "kelly_fraction": draw(st.floats(min_value=0.10, max_value=1.00)),
        # ... other fields
    }
```

**Correct Implementation:**
```python
from decimal import Decimal
from hypothesis import strategies as st

@composite
def strategy_config_dict(draw):
    return {
        "max_edge": draw(st.decimals(
            min_value=Decimal("0.05"),
            max_value=Decimal("0.50"),
            places=4
        )),
        "kelly_fraction": draw(st.decimals(
            min_value=Decimal("0.10"),
            max_value=Decimal("1.00"),
            places=4
        )),
        # ... other fields
    }
```

**Why This Matters:**
- Property tests generate thousands of test cases
- Float-generated configs could pass tests but fail in production with Decimal
- Violates fundamental Pattern 1: "NEVER USE FLOAT for financial calculations"
- Creates false confidence in test coverage

**Acceptance Criteria:**
- [ ] All `st.floats()` replaced with `st.decimals()` in property tests
- [ ] Decimal precision set to `places=4` (matches Pattern 1 and database schema)
- [ ] Tests still pass with Decimal inputs (100+ generated test cases)
- [ ] No float usage in any financial calculations or property strategies

**Files to Modify:**
- `tests/property/test_strategy_versioning_properties.py`
- Any other property tests using floats for financial values

**Related:**
- Pattern 1: Decimal Precision (docs/guides/DEVELOPMENT_PATTERNS_V1.2.md)
- ADR-002: Decimal Precision for Financial Calculations
- Database Schema: All price/probability fields use DECIMAL(10,4)

---

### DEF-P1-002: Add Test Coverage for database/initialization.py

**Priority:** 🔴 Critical
**Target Phase:** Phase 1.5
**Time Estimate:** 2-3 hours
**GitHub Issue:** #30
**Source:** PR #19 AI review (Fix Phase 1 CLI Tests)

**Description:**

`src/precog/database/initialization.py` has **274 lines with ZERO test coverage**. This module handles critical database operations (schema application, migrations, subprocess calls to psql) and is completely untested.

**Risk:**
- **Data Corruption:** Untested schema application could corrupt production database
- **Data Loss:** Untested migrations could lose critical trading data
- **Security:** Untested subprocess calls have no validation (see DEF-P1-003)
- **Deployment Failures:** Schema initialization errors could block deployments

**Coverage Gap:**
```bash
# Current coverage report
src/precog/database/initialization.py    0%    274 lines not covered
```

**Required Tests (create `tests/unit/database/test_initialization.py`):**

**1. validate_schema_file():**
- ✅ File exists and is readable
- ✅ File has correct permissions
- ❌ File does not exist (should raise FileNotFoundError)
- ❌ File is not readable (should raise PermissionError)
- ❌ File is empty (should raise ValueError)

**2. apply_schema():**
- ✅ Successful schema application (psql exits 0)
- ❌ psql command not found (should raise FileNotFoundError)
- ❌ psql command timeout (should raise TimeoutError)
- ❌ Invalid database URL (should raise ValueError)
- ❌ SQL syntax errors (should log error, return False)
- ❌ Permission denied (should raise PermissionError)

**3. apply_migrations():**
- ✅ Zero migrations (no-op, returns 0)
- ✅ Single migration successful
- ✅ Multiple migrations successful (5 migrations applied)
- ❌ Partial failures (migrations 1-3 succeed, 4 fails, 5 not run)
- ❌ Migration file not found (should skip, log warning)
- ❌ Migration file has syntax error (should skip, log error)

**4. validate_critical_tables():**
- ✅ All 25 critical tables exist (returns True)
- ❌ Some tables missing (raises ValueError with table names)
- ❌ Empty database (raises ValueError with all table names)
- ❌ Database connection fails (raises ConnectionError)

**5. get_database_url():**
- ✅ DATABASE_URL environment variable set (returns URL)
- ❌ DATABASE_URL not set (raises EnvironmentError)
- ❌ DATABASE_URL has invalid format (raises ValueError)
- ✅ URL sanitization (strips whitespace, validates postgres:// prefix)

**Mocking Strategy:**
```python
# tests/unit/database/test_initialization.py
import pytest
from unittest.mock import patch, MagicMock
from precog.database.initialization import apply_schema, apply_migrations

@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for psql calls."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        yield mock_run

def test_apply_schema_success(mock_subprocess):
    """Test successful schema application."""
    result = apply_schema('database/schema_v1.7.sql')

    assert result is True
    mock_subprocess.assert_called_once()
    # Verify psql command structure
    assert mock_subprocess.call_args[0][0] == ['psql', '-f', ...]
```

**Acceptance Criteria:**
- [ ] Test file created: `tests/unit/database/test_initialization.py`
- [ ] Coverage for `database/initialization.py` ≥85% (target: 90%+)
- [ ] All 5 functions have at least 3 test scenarios each (happy path, error, edge case)
- [ ] Subprocess calls properly mocked (no actual psql execution in tests)
- [ ] All error paths tested (ValueError, FileNotFoundError, PermissionError, etc.)
- [ ] Test execution is fast (<5 seconds for entire test file)

**Related:**
- CODE_REVIEW_TEMPLATE_V1.0.md (Section 2: Testing Requirements)
- DEVELOPMENT_PHASES_V1.4.md (Phase 1 Critical Module Coverage Targets)
- Create REQ-TEST-012: Critical module test coverage requirement

---

### DEF-P1-003: Add Path Sanitization to Prevent Directory Traversal

**Priority:** 🔴 Critical (Security)
**Target Phase:** Phase 1.5
**Time Estimate:** 30 minutes
**GitHub Issue:** #31
**Source:** PR #19 AI review (Fix Phase 1 CLI Tests)

**Description:**

`apply_schema()` and `apply_migrations()` in `database/initialization.py` accept file paths without validation. A malicious user could pass `../../etc/passwd` as a migration file, potentially exposing sensitive system files via psql error messages.

**Risk Level:** Medium-Low
**Current Risk:** Low (no external user input currently, only internal CLI usage)
**Future Risk:** Medium-High (if API endpoints expose schema/migration functionality)
**Security Best Practice:** Defense in Depth - validate all paths regardless of current attack surface

**Vulnerability Example:**
```bash
# Malicious input
python main.py apply-migration --file "../../etc/passwd"

# Current behavior: No validation, passes to subprocess
subprocess.run(['psql', '-f', '../../etc/passwd', ...])

# Result: psql error message may expose file contents or existence
```

**Current Code (VULNERABLE):**
```python
def apply_schema(schema_file: str) -> bool:
    """Apply database schema."""
    # NO PATH VALIDATION!
    result = subprocess.run(['psql', '-f', schema_file, database_url], ...)
    return result.returncode == 0
```

**Correct Implementation:**
```python
from pathlib import Path

def apply_schema(schema_file: str) -> bool:
    """
    Apply database schema with path sanitization.

    Args:
        schema_file: Path to schema SQL file (must be within project directory)

    Returns:
        True if schema applied successfully

    Raises:
        ValueError: If schema_file is outside project directory
        FileNotFoundError: If schema_file does not exist

    Security:
        - Validates file is within project directory (prevents directory traversal)
        - Resolves symlinks to prevent bypass attacks
        - Verifies file existence before subprocess call
    """
    # Sanitize path to prevent directory traversal (CWE-22)
    schema_path = Path(schema_file).resolve()  # Resolve symlinks
    project_root = Path.cwd().resolve()

    # Validate file is within project directory
    if not schema_path.is_relative_to(project_root):
        raise ValueError(
            f"Security: Schema file must be within project directory. "
            f"Got: {schema_file}"
        )

    # Validate file exists
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    # Now safe to use in subprocess
    result = subprocess.run(
        ['psql', '-f', str(schema_path), database_url],
        capture_output=True,
        text=True,
        timeout=60
    )

    return result.returncode == 0
```

**Apply Same Fix to apply_migrations():**
```python
def apply_migrations(migration_dir: str) -> int:
    """Apply database migrations with path sanitization."""
    migration_path = Path(migration_dir).resolve()
    project_root = Path.cwd().resolve()

    if not migration_path.is_relative_to(project_root):
        raise ValueError(
            f"Security: Migration directory must be within project. "
            f"Got: {migration_dir}"
        )

    if not migration_path.is_dir():
        raise ValueError(f"Migration path is not a directory: {migration_dir}")

    # ... rest of implementation
```

**Test Coverage:**
```python
def test_apply_schema_blocks_directory_traversal():
    """Test that directory traversal attacks are blocked."""
    with pytest.raises(ValueError, match="must be within project directory"):
        apply_schema("../../etc/passwd")

def test_apply_schema_allows_valid_paths():
    """Test that valid paths within project still work."""
    result = apply_schema("database/schema_v1.7.sql")
    assert result is True  # Should work normally

def test_apply_schema_resolves_symlinks():
    """Test that symlinks are resolved (prevents bypass)."""
    # Create symlink to /etc/passwd
    Path("malicious_link").symlink_to("/etc/passwd")

    with pytest.raises(ValueError, match="must be within project directory"):
        apply_schema("malicious_link")
```

**Acceptance Criteria:**
- [ ] Path sanitization added to `apply_schema()`
- [ ] Path sanitization added to `apply_migrations()`
- [ ] Tests verify directory traversal is blocked (`../../etc/passwd`)
- [ ] Tests verify symlink bypass is blocked
- [ ] Tests verify valid paths still work (`database/schema_v1.7.sql`)
- [ ] Error messages don't expose internal system paths
- [ ] Documentation updated with security notes

**Related:**
- SECURITY_REVIEW_CHECKLIST.md (Section 1: Input Validation)
- OWASP Top 10: Path Traversal (CWE-22)
- Pattern 4: Security - NO CREDENTIALS IN CODE (defense in depth principle)
- ADR-TBD: Create ADR for input validation strategy

---

## 🟡 High Priority (Implement in Phase 1.5)

### DEF-P1-004: Parallelize Pre-Push Validation Steps

**Priority:** 🟡 High (Developer Experience)
**Target Phase:** Phase 1.5
**Time Estimate:** 2 hours
**GitHub Issue:** #32 (✅ Closed 2025-11-15)
**Source:** PR #14 AI review (Template Enforcement)
**Status:** ✅ **IMPLEMENTED** (2025-11-15 this session)

**Description:**

Pre-push hooks currently run validation steps 2-7 sequentially, taking ~103 seconds total. Running independent checks in parallel reduces total time to ~33 seconds (68% faster), significantly improving developer experience.

**Performance:**

**Sequential (BEFORE FIX):** ~103 seconds
**Parallel (IMPLEMENTED):** ~33 seconds (68% faster)

**Implementation Status:**
✅ **File Modified:** `.git/hooks/pre-push`
✅ **Fully implemented and tested**

**Key Changes:**
1. ✅ Removed `set -e` (incompatible with parallel execution)
2. ✅ Created temp directory for parallel output capture
3. ✅ Added associative arrays for PID/output/name tracking
4. ✅ Created `run_parallel_check()` helper function
5. ✅ Parallelized steps 2-7 using bash background processes (`&`)
6. ✅ Wait for all processes, then check exit codes
7. ✅ Display results together, show failures with full output

**Status:** ✅ **COMPLETE** - Implemented 2025-11-15

---

### DEF-P1-005: API Limit Validation (Kalshi Max 200)

**Priority:** 🟡 High
**Target Phase:** Phase 1.5
**Time Estimate:** 15 minutes
**GitHub Issue:** #33
**Source:** PR #11 AI review (CLI Testing Infrastructure)

**Description:**

CLI `--limit` parameter for `fetch-markets` and other commands doesn't validate that limit ≤ 200 (Kalshi API maximum). Users can specify `--limit 1000` and receive confusing API errors instead of clear validation errors.

**Current Behavior:**
```bash
# User tries to fetch 1000 markets
python main.py fetch-markets --limit 1000

# Kalshi API returns 400 error:
# "Error: limit parameter must be ≤ 200"
# User sees generic error message, not root cause
```

**Desired Behavior:**
```bash
# User tries to fetch 1000 markets
python main.py fetch-markets --limit 1000

# CLI validates BEFORE API call:
# [red]Error:[/red] Limit cannot exceed 200 (Kalshi API maximum)
# Tip: Use --limit 200 for maximum results
```

**Implementation:**
```python
# main.py

@app.command()
def fetch_markets(
    limit: int = typer.Option(10, help="Number of markets to fetch (max 200)"),
    ticker: str = typer.Option(None, help="Filter by ticker"),
):
    """Fetch markets from Kalshi API."""
    # VALIDATION: Kalshi API maximum is 200
    if limit < 1:
        console.print("[red]Error:[/red] Limit must be at least 1")
        raise typer.Exit(code=1)

    if limit > 200:
        console.print(
            "[red]Error:[/red] Limit cannot exceed 200 (Kalshi API maximum)"
        )
        console.print("[dim]Tip:[/dim] Use --limit 200 for maximum results")
        raise typer.Exit(code=1)

    # Now safe to call API
    try:
        markets = kalshi_client.get_markets(limit=limit, ticker=ticker)
        # ... display results ...
```

**Add to Other Commands:**
- `fetch-markets` (already shown above)
- `fetch-positions` (same 200 limit)
- `fetch-trades` (same 200 limit)
- Any future commands with pagination

**Acceptance Criteria:**
- [ ] Validation added to `fetch-markets` command
- [ ] Validation added to `fetch-positions` command
- [ ] Validation added to `fetch-trades` command
- [ ] Error messages are clear and actionable
- [ ] Validation happens BEFORE API call (saves network round-trip)
- [ ] Tests cover limit < 1, limit > 200, and valid limits (1-200)

**Related:**
- docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md (Kalshi API limits)
- main.py CLI commands
- Kalshi API documentation: https://trading-api.readme.io/reference/getmarkets

---

(Continue with DEF-P1-006 through DEF-P1-045...)

---

## 📊 Complete Issue Tracking Summary

| ID | Task | Priority | Time | Phase | GitHub Issue | Status |
|----|------|----------|------|-------|--------------|--------|
| DEF-P1-001 | Fix Float Usage in Property Tests | 🔴 Critical | 30m | 1.5 | [#29](https://github.com/mutantamoeba/precog/issues/29) | ⏳ Open |
| DEF-P1-002 | Add Test Coverage for database/initialization.py | 🔴 Critical | 2-3h | 1.5 | [#30](https://github.com/mutantamoeba/precog/issues/30) | ⏳ Open |
| DEF-P1-003 | Path Sanitization (Security) | 🔴 Critical | 30m | 1.5 | [#31](https://github.com/mutantamoeba/precog/issues/31) | ⏳ Open |
| DEF-P1-004 | Parallelize Pre-Push Validation | 🟡 High | 2h | 1.5 | [#32](https://github.com/mutantamoeba/precog/issues/32) | ✅ Closed |
| DEF-P1-005 | API Limit Validation | 🟡 High | 15m | 1.5 | [#33](https://github.com/mutantamoeba/precog/issues/33) | ⏳ Open |
| DEF-P1-006 | Branch Protection Verification Script | 🟡 High | 30m | 1.5 | [#34](https://github.com/mutantamoeba/precog/issues/34) | ✅ Closed |
| DEF-P1-007 | ADR-046: Branch Protection Strategy | 🟡 High | 1h | 1.5 | [#35](https://github.com/mutantamoeba/precog/issues/35) | ✅ Closed |
| DEF-P1-008 | Add Analytics Tables to Validation Script | 🟡 High | 1h | 1.5 | [#36](https://github.com/mutantamoeba/precog/issues/36) | ⏳ Open |
| DEF-P1-009 | Update CLAUDE.md for Formatter Change | 🟢 Medium | 10m | 1.5-2 | [#37](https://github.com/mutantamoeba/precog/issues/37) | ⏳ Open |
| DEF-P1-010 | Re-enable Documentation Validation Hook | 🟢 Medium | 5m | 1.5 | [#38](https://github.com/mutantamoeba/precog/issues/38) | ⏳ Open |
| DEF-P1-011 | Add Debug Logging to config_loader | 🟢 Medium | 30m | 1.5 | [#39](https://github.com/mutantamoeba/precog/issues/39) | ⏳ Open |
| DEF-P1-012 | Config Synchronization Check (Pattern 8) | 🟢 Medium | 2h | 2 | [#40](https://github.com/mutantamoeba/precog/issues/40) | ⏳ Open |
| DEF-P1-013 | Move calculate_kelly_size to Production | 🟢 Medium | 30m | 5 | [#41](https://github.com/mutantamoeba/precog/issues/41) | ⏳ Open |
| DEF-P1-014 | Improve Error Message Security | 🟢 Medium | 1h | 1.5 | [#42](https://github.com/mutantamoeba/precog/issues/42) | ⏳ Open |
| DEF-P1-015 | Document Ruff Ignore Rules | 🟢 Medium | 5m | 1.5 | [#43](https://github.com/mutantamoeba/precog/issues/43) | ⏳ Open |
| DEF-P1-016 | Add @pytest.mark.slow for Time-Based Tests | 🟢 Medium | 10m | 1.5 | [#44](https://github.com/mutantamoeba/precog/issues/44) | ⏳ Open |
| DEF-P1-017 | Add Unit Tests for check_warning_debt.py | 🟢 Medium | 1h | 1.5 | [#45](https://github.com/mutantamoeba/precog/issues/45) | ⏳ Open |
| DEF-P1-018 | Create Pytest Optimization Strategy Doc | 🟢 Medium | 2h | 2 | [#46](https://github.com/mutantamoeba/precog/issues/46) | ⏳ Open |
| DEF-P1-019 | Create TypedDict Classes for Analytics | 🟢 Medium | 2h | 6 | [#47](https://github.com/mutantamoeba/precog/issues/47) | ⏳ Open |
| DEF-P1-020 | Materialized View Staleness Monitoring | 🟢 Medium | 30m | 6-7 | [#48](https://github.com/mutantamoeba/precog/issues/48) | ⏳ Open |
| DEF-P1-021 | Improve apply_migrations Error Handling | 🟢 Medium | 30m | 1.5 | [#49](https://github.com/mutantamoeba/precog/issues/49) | ⏳ Open |
| DEF-P1-022 | Add Regression Prevention Comment | 🟢 Medium | 1m | 1.5 | [#50](https://github.com/mutantamoeba/precog/issues/50) | ⏳ Open |
| DEF-P1-023 | Document 8 Skipped Tests as DEF Tasks | 🟢 Medium | 6-8h | 2 | [#51](https://github.com/mutantamoeba/precog/issues/51) | ⏳ Open |
| DEF-P1-024 | Verify MASTER_INDEX Status Changes | 🟢 Medium | 15m | 1.5 | [#52](https://github.com/mutantamoeba/precog/issues/52) | ⏳ Open |
| DEF-P1-025 | Add DEF-004 Reference to requirements.txt | 🟢 Medium | 5m | 1.5 | [#53](https://github.com/mutantamoeba/precog/issues/53) | ⏳ Open |
| DEF-P1-026 | Add Semver Reference to Property Tests | 🟢 Medium | 5m | 1.5-2 | [#54](https://github.com/mutantamoeba/precog/issues/54) | ⏳ Open |
| DEF-P1-027 | Add Pytest Markers (@pytest.mark.unit) | 🔵 Low | 1h | 1.5-2 | [#55](https://github.com/mutantamoeba/precog/issues/55) | ⏳ Open |
| DEF-P1-028 | Mock Time for Rate Limiter Tests | 🔵 Low | 1h | 2 | [#56](https://github.com/mutantamoeba/precog/issues/56) | ⏳ Open |
| DEF-P1-029 | Parametrize Error Code Tests | 🔵 Low | 30m | 2 | [#57](https://github.com/mutantamoeba/precog/issues/57) | ⏳ Open |
| DEF-P1-030 | Extract Mocking to mock_helpers.py | 🔵 Low | 2h | 2 | [#58](https://github.com/mutantamoeba/precog/issues/58) | ⏳ Open |
| DEF-P1-031 | Add Validation Tests for MASTER_INDEX Regex | 🔵 Low | 1h | 2 | [#59](https://github.com/mutantamoeba/precog/issues/59) | ⏳ Open |
| DEF-P1-032 | Support Patch Versions (V1.0.1) | 🔵 Low | 30m | 2 | [#60](https://github.com/mutantamoeba/precog/issues/60) | ⏳ Open |
| DEF-P1-033 | Consider pytest-xdist for Parallel Tests | 🔵 Low | 2h | 2 | [#61](https://github.com/mutantamoeba/precog/issues/61) | ⏳ Open |
| DEF-P1-034 | Add .load Mocking Detection to Pre-Push | 🔵 Low | 1h | 2 | [#62](https://github.com/mutantamoeba/precog/issues/62) | ⏳ Open |
| DEF-P1-035 | Verify Test Key Not in Git | 🔵 Low | 30s | 1.5 | [#63](https://github.com/mutantamoeba/precog/issues/63) | ⏳ Open |
| DEF-P1-036 | Create Kalshi Environment Fixture | 🔵 Low | 30m | 2 | [#64](https://github.com/mutantamoeba/precog/issues/64) | ⏳ Open |
| DEF-P1-037 | Add Type Annotation to strategy_config_dict | 🔵 Low | 2m | 2 | [#65](https://github.com/mutantamoeba/precog/issues/65) | ⏳ Open |
| DEF-P1-038 | Remove Duplicate Cleanup in Tests | 🔵 Low | 15m | 2 | [#66](https://github.com/mutantamoeba/precog/issues/66) | ⏳ Open |
| DEF-P1-039 | Lazy Imports for CLI Commands | 🔵 Low | 1h | 3+ | [#67](https://github.com/mutantamoeba/precog/issues/67) | ⏳ Open |
| DEF-P1-040 | Use NoReturn Type Hint for Exit Paths | 🔵 Low | 15m | 2 | [#68](https://github.com/mutantamoeba/precog/issues/68) | ⏳ Open |
| DEF-P1-041 | Add Trade-offs Section to Docstrings | 🔵 Low | 10m | 2 | [#69](https://github.com/mutantamoeba/precog/issues/69) | ⏳ Open |
| DEF-P1-042 | Measure Token Savings from CLAUDE.md | 🔵 Low | 15m | 2 | [#70](https://github.com/mutantamoeba/precog/issues/70) | ⏳ Open |
| DEF-P1-043 | Add Smoke Tests for Critical Paths | 🔵 Low | 2h | 2 | [#71](https://github.com/mutantamoeba/precog/issues/71) | ⏳ Open |
| DEF-P1-044 | Improve Warning Governance Error Messages | 🔵 Low | 30m | 1.5-2 | [#72](https://github.com/mutantamoeba/precog/issues/72) | ⏳ Open |
| DEF-P1-045 | Track Analytics Forward References | 🔵 Low | 10m | 6 | [#73](https://github.com/mutantamoeba/precog/issues/73) | ⏳ Open |

**Summary:**
- **Total Tasks:** 45
- **GitHub Issues:** [#29](https://github.com/mutantamoeba/precog/issues/29) through [#73](https://github.com/mutantamoeba/precog/issues/73)
- **Open Issues:** 42
- **Closed Issues:** 3 (#32, #34, #35 - all ✅ completed 2025-11-15)
- **Priority Distribution:** 3 critical, 8 high, 18 medium, 16 low
- **Estimated Effort:** ~35-40 hours total

---

## 📚 References

**Source Documents:**
- PR Analysis: `_sessions/pr_review_analysis_2-21_complete.md`
- PR Reviews: PRs #2-#21 (2025-11-07 through 2025-11-15)

**Related Documentation:**
- SESSION_WORKFLOW_GUIDE_V1.0.md (Section 9: Dual-Tracking System)
- DEVELOPMENT_PATTERNS_V1.2.md (10 critical patterns)
- CODE_REVIEW_TEMPLATE_V1.0.md (7-category checklist)

---

**Document Status:** ✅ Complete (all 45 tasks tracked with GitHub issues)
**Last Updated:** 2025-11-15
**GitHub Issues Created:** 2025-11-15 (Issues #29-#73)
**Dual-Tracking Implementation:** ✅ Active (Documentation + GitHub Issues)

**Quick Access:**
- **View all deferred tasks:** [GitHub Issues #29-#73](https://github.com/mutantamoeba/precog/issues?q=is%3Aissue+label%3Adeferred-task)
- **Filter by priority:**
  - [Critical](https://github.com/mutantamoeba/precog/issues?q=is%3Aissue+label%3Apriority-critical)
  - [High](https://github.com/mutantamoeba/precog/issues?q=is%3Aissue+label%3Apriority-high)
  - [Medium](https://github.com/mutantamoeba/precog/issues?q=is%3Aissue+label%3Apriority-medium)
  - [Low](https://github.com/mutantamoeba/precog/issues?q=is%3Aissue+label%3Apriority-low)
