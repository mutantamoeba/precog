# Phase 0.7 Deferred Tasks

**Version:** 1.3
**Created:** 2025-10-31
**Last Updated:** 2025-11-08
**Phase:** 0.7 (CI/CD Infrastructure)
**Status:** ✅ COMPLETE - 8/8 tasks complete (ALL TASKS DONE)
**Changes in V1.3:**
- Updated DEF-002 Pre-Push Hook documentation to reflect Ruff security scanning (replaced outdated Bandit command reference)
- Updated branch protection status check description (Bandit & Safety → Ruff & Safety)
- Aligns documentation with ADR-054 (Ruff Security Rules Instead of Bandit for Python 3.14 Compatibility)
- No functional changes - actual pre-push hooks already using Ruff correctly
**Changes in V1.2:**
- Marked DEF-001 (Pre-Commit Hooks) as ✅ Complete (2025-11-07)
- Marked DEF-002 (Pre-Push Hooks) as ✅ Complete (2025-11-07)
- Marked DEF-005 (No print() Hook) as ✅ Complete (2025-11-07 - included in DEF-001)
- Marked DEF-006 (Merge Conflict Hook) as ✅ Complete (2025-11-07 - included in DEF-001)
- Marked DEF-007 (Branch Name Validation) as ✅ Complete (2025-11-07 - included in DEF-002)
- Marked DEF-008 (Database Schema Validation Script) as ✅ Complete (2025-11-07)
- **Phase 0.7 now 100% complete - all deferred tasks implemented**
**Changes in V1.1:**
- Marked DEF-003 (GitHub Branch Protection) as ✅ Complete (2025-11-07 via PR #2)
- Marked DEF-004 (Line Ending Fix) as ✅ Complete (2025-11-07 via PR #2/PR #3)
- Created comprehensive documentation: `GITHUB_BRANCH_PROTECTION_CONFIG.md`
- Added Status column to summary table

---

## Overview

This document tracks tasks that were identified during Phase 0.7 (CI/CD) but deferred to Phase 0.8 or later phases due to time constraints, priority, or dependencies. These tasks are **important but not blocking** for Phase 1 development to begin.

---

## Deferred Tasks Summary

| ID | Task | Priority | Estimated Effort | Target Phase | Status |
|----|------|----------|------------------|--------------|--------|
| DEF-001 | Pre-Commit Hooks Setup | 🟡 High | 2 hours | 0.8 | ✅ Complete (2025-11-07) |
| DEF-002 | Pre-Push Hooks Setup | 🟡 High | 1 hour | 0.8 | ✅ Complete (2025-11-07) |
| DEF-003 | GitHub Branch Protection Rules | 🟢 Medium | 30 min | 0.8 | ✅ Complete (2025-11-07) |
| DEF-004 | Line Ending Edge Case Fix | 🟢 Medium | 1 hour | 0.8 | ✅ Complete (2025-11-07) |
| DEF-005 | Pre-Commit Hook: No print() in Production | 🔵 Low | 30 min | 1+ | ✅ Complete (2025-11-07) |
| DEF-006 | Pre-Commit Hook: Check for Merge Conflicts | 🔵 Low | 15 min | 1+ | ✅ Complete (2025-11-07) |
| DEF-007 | Pre-Push Hook: Verify Branch Name Convention | 🔵 Low | 30 min | 1+ | ✅ Complete (2025-11-07) |
| DEF-008 | Database Schema Validation Script | 🟡 High | 3-4 hours | 0.8 | ✅ Complete (2025-11-07) |

---

## DEF-001: Pre-Commit Hooks Setup

### Description
Set up Git pre-commit hooks to auto-fix code issues **before each commit**, ensuring code is always formatted and linted correctly.

### Rationale
- Prevents "would reformat" errors in CI
- Catches issues immediately (no need to wait for CI)
- Faster developer feedback loop (~2 seconds vs ~2 minutes CI time)
- Reduces CI failures by 60-70%

### Implementation

**Step 1: Install pre-commit framework**
```bash
pip install pre-commit
echo "pre-commit==4.0.1  # Pre-commit hooks framework (Dec 2024)" >> requirements.txt
```

**Step 2: Create `.pre-commit-config.yaml`**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      # Run ruff linter with auto-fix
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      # Run ruff formatter
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      # Check for files with CRLF line endings
      - id: mixed-line-ending
        args: ['--fix=lf']
      # Remove trailing whitespace
      - id: trailing-whitespace
      # Ensure files end with newline
      - id: end-of-file-fixer
      # Check for large files (>500KB)
      - id: check-added-large-files
        args: ['--maxkb=500']
      # Check for merge conflict markers
      - id: check-merge-conflict
      # Check YAML syntax
      - id: check-yaml
      # Check JSON syntax
      - id: check-json

  - repo: local
    hooks:
      # Check for hardcoded credentials
      - id: check-secrets
        name: Check for hardcoded credentials
        entry: bash -c 'git diff --cached --name-only | xargs grep -E "(password|secret|api_key|token)\s*=\s*['\''"][^'\''\"]{5,}['\''"]" -- *.py && exit 1 || exit 0'
        language: system
        pass_filenames: false
```

**Step 3: Install hooks**
```bash
pre-commit install
```

**Step 4: Test hooks**
```bash
# Test on all files
pre-commit run --all-files

# Test on a single file
echo "test" >> test.py
git add test.py
git commit -m "test"  # Hooks will run automatically
```

### Benefits
- **Auto-fix**: Ruff will format and fix issues automatically
- **Fast**: Runs in ~2-5 seconds (only on changed files)
- **Consistent**: Everyone on team has same hooks

### Acceptance Criteria
- [ ] pre-commit installed and configured
- [ ] Hooks run automatically on `git commit`
- [ ] Test commit with unformatted code → hooks auto-fix it
- [ ] Document in CLAUDE.md under "Development Workflow"

---

## DEF-002: Pre-Push Hooks Setup

### Description
Set up Git pre-push hooks to run validation checks **before pushing to remote**, catching issues before CI runs.

### Rationale
- Runs more thorough checks than pre-commit (slower, but only on push)
- Catches type errors, security issues, test failures before CI
- Saves CI time and reduces failed CI runs
- Prevents embarrassing "oops forgot to run tests" pushes

### Implementation

**Create `.git/hooks/pre-push`**
```bash
#!/bin/bash
# Pre-push hook - Phase 0.7 Deferred Task DEF-002

echo "🔍 Running pre-push validation checks..."
echo ""

# Exit on any error
set -e

# 1. Run quick validation suite (code quality + docs)
echo "1/4 Running quick validation..."
bash scripts/validate_quick.sh

# 2. Run fast unit tests (not integration tests)
echo ""
echo "2/4 Running fast unit tests..."
python -m pytest tests/test_config_loader.py tests/test_logger.py -v --no-cov

# 3. Type check all code
echo ""
echo "3/4 Running type checks..."
python -m mypy . --exclude 'tests/' --exclude '_archive/' --ignore-missing-imports

# 4. Security scan
echo ""
echo "4/4 Running security scan..."
python -m ruff check --select S --ignore S101,S112,S607 --exclude 'tests/' --exclude '_archive/' --exclude 'venv/' --quiet .

echo ""
echo "✅ All pre-push checks passed! Pushing to remote..."
```

**Make executable:**
```bash
chmod +x .git/hooks/pre-push
```

### Benefits
- Runs full validation before push (~30-60 seconds)
- Catches 80% of issues that would fail in CI
- Much faster feedback than waiting for CI

### Bypassing (Emergency Use Only)
```bash
# Skip pre-push hooks if absolutely necessary
git push --no-verify
```

### Acceptance Criteria
- [ ] Pre-push hook installed in `.git/hooks/pre-push`
- [ ] Hooks run automatically on `git push`
- [ ] Test push with failing test → hook blocks push
- [ ] Document bypass command for emergencies
- [ ] Add setup instructions to CLAUDE.md

---

## DEF-003: GitHub Branch Protection Rules ✅ **COMPLETED**

**Completed:** 2025-11-07 via PR #2
**Documentation:** `docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md`

### Description
Configure GitHub branch protection rules to enforce code quality and prevent accidental pushes to `main`.

### Rationale
- Prevents direct pushes to main (forces PRs)
- Requires CI to pass before merging
- Requires code review before merging
- Prevents force pushes that could lose history

### Implementation ✅

**Configured via GitHub API on 2025-11-07**

Branch protection now active for `main` branch with the following settings:

**1. Basic Settings ✅**
- [x] Require a pull request before merging
- [x] Require approvals: 0 (solo development, but PRs mandatory)
- [x] Dismiss stale pull request approvals when new commits are pushed
- [ ] Require review from Code Owners (not using CODEOWNERS file)

**2. Status Checks ✅**
- [x] Require status checks to pass before merging
- [x] Require branches to be up to date before merging (strict: true)
- Required checks:
  - ✅ Pre-commit Validation (Ruff, Mypy, Security)
  - ✅ Security Scanning (Ruff & Safety)
  - ✅ Documentation Validation
  - ✅ Quick Validation Suite
  - ✅ CI Summary (aggregates all test matrix results)

**3. Protection Rules ✅**
- [x] Require conversation resolution before merging
- [ ] Require signed commits (not implemented - deferred)
- [ ] Require linear history (not enforced - squash merges preferred but not required)
- [ ] Require deployments to succeed (N/A for this project)

**4. Force Push ✅**
- [x] Do not allow force pushes
- [x] Do not allow deletions

**5. Rules Applied To ✅**
- Administrators: [x] Include administrators ⚠️ **CRITICAL: Even admins must use PRs**

### Final Configuration

Full configuration documented in `docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md` including:
- Exact JSON payload for reproduction
- GitHub CLI commands for re-applying settings
- Troubleshooting guide
- Security implications
- History of configuration changes

### Benefits
- ✅ Enforces code review process
- ✅ Prevents accidental commits to main
- ✅ Ensures all code passes CI before merging
- ✅ Maintains clean Git history
- ✅ Tested and verified working (PR #2, PR #3)

### Acceptance Criteria ✅ ALL COMPLETE
- [x] Branch protection rules configured for `main` ✅ Done 2025-11-07
- [x] Test: Try to push directly to main → blocked ✅ Verified working
- [x] Test: Create PR → can only merge after CI passes ✅ PR #2 and #3 both required passing CI
- [x] Document PR workflow in CLAUDE.md ✅ Already documented in CLAUDE.md
- [x] **BONUS:** Comprehensive configuration documentation created ✅ GITHUB_BRANCH_PROTECTION_CONFIG.md

---

## DEF-004: Line Ending Edge Case Fix

### Description
Resolve the persistent "would reformat" CI error for `tests/test_crud_operations.py` and `tests/test_decimal_properties.py` caused by line ending inconsistencies.

### Root Cause
- Files were committed with CRLF endings before `.gitattributes` was added
- `.gitattributes` only affects new commits, not existing files in repo history
- Windows `core.autocrlf=true` hides the issue locally but CI (Linux) sees CRLF
- Ruff on Linux detects CRLF as formatting issue: "Would reformat: tests/*.py"

### Current State
- ✅ `.gitattributes` added (prevents future issues)
- ✅ All code changes committed (Mypy, Ruff, security fixes complete)
- ❌ Two test files still have CRLF in Git repository
- ❌ CI validation suite fails due to these two files

### Solution

**Option A: Force re-commit those files (Recommended)**
```bash
# 1. Temporarily set core.autocrlf to false
git config core.autocrlf false

# 2. Re-checkout files from repo (will now show as CRLF)
git checkout HEAD -- tests/test_crud_operations.py tests/test_decimal_properties.py

# 3. Convert CRLF → LF manually
dos2unix tests/test_crud_operations.py tests/test_decimal_properties.py
# OR
python -c "import pathlib; [pathlib.Path(f).write_bytes(pathlib.Path(f).read_bytes().replace(b'\r\n', b'\n')) for f in ['tests/test_crud_operations.py', 'tests/test_decimal_properties.py']]"

# 4. Check status (should now show modified)
git status

# 5. Commit with LF endings
git add tests/test_crud_operations.py tests/test_decimal_properties.py
git commit -m "Fix line endings: Convert CRLF→LF in test files

- tests/test_crud_operations.py: CRLF → LF
- tests/test_decimal_properties.py: CRLF → LF
- Fixes persistent 'would reformat' CI error
- Aligns with .gitattributes rules (eol=lf)

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

# 6. Reset core.autocrlf to input (recommended setting)
git config core.autocrlf input

# 7. Push and verify CI passes
git push origin main
```

**Option B: Pre-commit hook will fix it (Automatic)**

Once DEF-001 (pre-commit hooks) is implemented, the `mixed-line-ending` hook will automatically fix any CRLF issues on the next commit that touches those files.

### Why This Wasn't Fixed in Phase 0.7

- Spent ~2 hours debugging line ending issues
- All actual code issues were fixed (Mypy, Ruff linting, security)
- Only cosmetic issue remaining (CRLF vs LF)
- Pre-commit hooks (DEF-001) will prevent this in future
- Not blocking Phase 1 development (tests still pass)

### Acceptance Criteria
- [ ] `python -m ruff format --check tests/` passes locally
- [ ] CI Quick Validation Suite passes (no "would reformat" errors)
- [ ] Verify files have LF: `git ls-files -z tests/*.py | xargs -0 file | grep CRLF` returns empty

---

## DEF-005: Pre-Commit Hook - No print() in Production Code

### Description
Add pre-commit hook to prevent `print()` statements in production code (only allow in scripts/).

### Rationale
- Production code should use structured logging (structlog)
- `print()` statements bypass logging infrastructure
- Difficult to control log levels with print()
- Can cause issues in production (stdout buffering, etc.)

### Implementation

**Add to `.pre-commit-config.yaml`:**
```yaml
  - repo: local
    hooks:
      - id: no-print-statements
        name: Check for print() in production code
        entry: bash -c 'git diff --cached --name-only | grep -E "(database|api_connectors|trading|analytics|utils|config)/.*\.py$" | xargs grep -n "print(" && echo "ERROR: Found print() in production code! Use logger.info() instead." && exit 1 || exit 0'
        language: system
        pass_filenames: false
```

### Exceptions
- `scripts/` - print() is OK (utility scripts)
- `tests/` - print() is OK (test output)
- Debug comments: `# print(variable)  # DEBUG` - OK if commented out

### Acceptance Criteria
- [ ] Hook blocks commits with print() in production code
- [ ] Hook allows print() in scripts/ and tests/
- [ ] Document in CLAUDE.md: "Use logger.info() not print()"

---

## DEF-006: Pre-Commit Hook - Check for Merge Conflicts

### Description
Add pre-commit hook to prevent committing files with merge conflict markers.

### Rationale
- Easy to accidentally commit files with `<<<<<<< HEAD` markers
- Breaks code compilation
- Embarrassing to have in Git history

### Implementation

**Already included in DEF-001:**
```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-merge-conflict
```

### Acceptance Criteria
- [ ] Hook blocks commits with `<<<<<<<`, `=======`, `>>>>>>>` markers
- [ ] Test: Create conflict, try to commit → blocked

---

## DEF-007: Pre-Push Hook - Verify Branch Name Convention

### Description
Add pre-push hook to enforce branch naming convention for feature branches.

### Rationale
- Consistent branch names improve organization
- Easier to find branches (by feature, bug fix, etc.)
- Integrates with project management tools (if used)

### Proposed Convention
```
feature/descriptive-name    # New features
bugfix/issue-number-desc    # Bug fixes
refactor/what-being-changed # Refactoring
docs/what-documenting       # Documentation
test/what-testing           # Test additions
```

### Implementation

**Add to `.git/hooks/pre-push`:**
```bash
# Check branch name convention
current_branch=$(git rev-parse --abbrev-ref HEAD)

if [[ ! "$current_branch" =~ ^(main|develop|feature/|bugfix/|refactor/|docs/|test/).*$ ]]; then
  echo "❌ ERROR: Branch name '$current_branch' doesn't follow convention"
  echo "Use: feature/, bugfix/, refactor/, docs/, or test/"
  echo "Example: feature/kalshi-api-client"
  echo ""
  echo "To bypass (emergency only): git push --no-verify"
  exit 1
fi
```

### Acceptance Criteria
- [ ] Hook blocks pushes from branches like "my-branch" or "test123"
- [ ] Hook allows "feature/add-api-client", "bugfix/fix-decimal-precision"
- [ ] Document convention in CLAUDE.md

---

## DEF-008: Database Schema Validation Script

### Description
Create automated validation script to ensure database schema consistency across documentation, implementation, requirements, and architectural decisions.

### Rationale
- Prevents schema drift between documentation and implementation
- Catches type mismatches early (e.g., FLOAT vs DECIMAL for prices)
- Validates compliance with requirements (REQ-DB-003, REQ-DB-004, REQ-DB-005)
- Validates compliance with ADRs (ADR-002 Decimal Precision, ADR-009 SCD Type 2)
- Ensures cross-document consistency (MASTER_REQUIREMENTS, DATABASE_SCHEMA_SUMMARY, actual database)
- Defense-in-depth: Pre-commit hooks + validate_all.sh + CI/CD

### Implementation

**Create:** `scripts/validate_schema_consistency.py`

The script will implement **8 validation levels**:

#### Level 1: Table Existence
```python
def validate_table_existence():
    """Verify all tables in DATABASE_SCHEMA_SUMMARY exist in database.

    Checks:
    - Parse table names from DATABASE_SCHEMA_SUMMARY_V1.7.md
    - Query PostgreSQL information_schema.tables
    - Flag tables documented but not implemented
    - Flag tables implemented but not documented
    """
```

#### Level 2: Column Consistency
```python
def validate_column_consistency():
    """Verify columns match between documentation and database.

    For each table, validate:
    - Column name matches
    - Data type matches
    - Nullable constraint matches
    - Default value matches (if specified)

    Example: markets.yes_bid should be DECIMAL(10,4) NOT NULL
    """
```

#### Level 3: Type Precision for Prices
```python
def validate_type_precision():
    """All price/probability columns MUST be DECIMAL(10,4).

    Validates REQ-DB-003 and ADR-002 compliance.

    Price columns (must be DECIMAL(10,4)):
    - markets: yes_bid, yes_ask, no_bid, no_ask, settlement_price
    - positions: entry_price, exit_price
    - trades: price, fill_price
    - edges: edge_probability
    - exit_evals: current_price, exit_threshold
    - account_balance: cash_balance, total_equity

    Errors to catch:
    - FLOAT/DOUBLE/REAL (precision loss)
    - NUMERIC without precision
    - INTEGER for prices (Kalshi uses sub-penny)
    """
```

#### Level 4: SCD Type 2 Compliance
```python
def validate_scd_type2_compliance():
    """Verify SCD Type 2 pattern implemented correctly.

    Validates REQ-DB-004 and ADR-009 compliance.

    Tables with versioning (row_current_ind):
    - markets
    - positions
    - game_states
    - edges
    - account_balance

    Required columns for SCD Type 2 tables:
    - row_current_ind BOOLEAN NOT NULL DEFAULT TRUE
    - row_effective_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    - row_expiration_date TIMESTAMP
    - row_version INTEGER NOT NULL DEFAULT 1

    Additional checks:
    - Index exists on (id, row_current_ind)
    - Index exists on row_effective_date
    - Check constraint: expiration_date IS NULL OR expiration_date > effective_date
    """
```

#### Level 5: Foreign Key Integrity
```python
def validate_foreign_keys():
    """Verify all documented foreign keys exist in database.

    For each foreign key in DATABASE_SCHEMA_SUMMARY:
    - Verify constraint exists in database
    - Verify referential integrity (CASCADE/RESTRICT)
    - Verify indexes exist on foreign key columns

    Example:
    - positions.market_id → markets.market_id
    - trades.strategy_id → strategies.strategy_id
    """
```

#### Level 6: Requirements Traceability
```python
def validate_req_db_003():
    """REQ-DB-003: DECIMAL(10,4) for Prices/Probabilities.

    Cross-reference:
    - MASTER_REQUIREMENTS_V2.9.md REQ-DB-003
    - DATABASE_SCHEMA_SUMMARY_V1.7.md
    - Actual database schema (information_schema)

    Ensure all price columns comply with requirement.
    """

def validate_req_db_004():
    """REQ-DB-004: SCD Type 2 Versioning Pattern.

    Cross-reference:
    - MASTER_REQUIREMENTS_V2.9.md REQ-DB-004
    - DATABASE_SCHEMA_SUMMARY_V1.7.md
    - Actual database schema

    Ensure pattern implemented correctly for all versioned tables.
    """

def validate_req_db_005():
    """REQ-DB-005: Immutable Strategy/Model Configs.

    Verify:
    - strategies.config is JSONB
    - probability_models.config is JSONB
    - No UPDATE triggers on config columns (immutability enforced by app logic)
    """
```

#### Level 7: ADR Compliance
```python
def validate_adr_002():
    """ADR-002: Decimal Precision (NEVER float for prices).

    Cross-reference:
    - ARCHITECTURE_DECISIONS_V2.7.md ADR-002
    - Actual database schema

    Verify NO columns use FLOAT/DOUBLE/REAL for monetary values.
    Acceptable types: DECIMAL(10,4), INTEGER (for quantities)
    """

def validate_adr_009():
    """ADR-009: SCD Type 2 Pattern with Indexes.

    Cross-reference:
    - ARCHITECTURE_DECISIONS_V2.7.md ADR-009
    - Actual database schema

    Verify:
    - All SCD Type 2 columns present
    - Required indexes exist
    - Default values correct
    - Check constraints present
    """
```

#### Level 8: Cross-Document Consistency
```python
def validate_cross_document_consistency():
    """Ensure documentation doesn't contradict itself.

    Checks:
    - Table count matches across docs
    - Column definitions match across docs
    - Data types consistent
    - Foreign keys consistent

    Documents to compare:
    - DATABASE_SCHEMA_SUMMARY_V1.7.md
    - DATABASE_TABLES_REFERENCE.md
    - MASTER_REQUIREMENTS_V2.9.md (REQ-DB-* requirements)
    - ARCHITECTURE_DECISIONS_V2.7.md (ADR-002, ADR-009)
    """
```

### Integration Options

**Option A: Add to validate_all.sh (RECOMMENDED)**
```bash
# In scripts/validate_all.sh, add after documentation validation:
echo "3/3 Running database schema validation..."
python scripts/validate_schema_consistency.py
```

**Option C: Add to Pre-Commit Hooks (RECOMMENDED)**
```yaml
# In .pre-commit-config.yaml:
  - repo: local
    hooks:
      - id: validate-schema
        name: Validate database schema consistency
        entry: python scripts/validate_schema_consistency.py
        language: system
        pass_filenames: false
        # Only run if schema files or migrations changed
        files: '(database/|docs/database/|migrations/)'
```

**Recommendation:** Implement BOTH (defense-in-depth)
- Pre-commit hook: Immediate feedback when schema files change
- validate_all.sh: Safety net, runs on every validation
- CI/CD: Final enforcement before merge

### Benefits
- **Catches drift early:** Prevents documentation from becoming stale
- **Validates compliance:** Ensures requirements and ADRs are followed
- **Type safety:** Catches dangerous FLOAT usage before production
- **Cross-doc consistency:** Ensures all docs tell the same story
- **Fast feedback:** Pre-commit hooks run in ~2-5 seconds

### Acceptance Criteria
- [ ] Script validates all 8 levels
- [ ] Integrated into validate_all.sh
- [ ] Integrated into pre-commit hooks (conditional on file changes)
- [ ] Comprehensive error messages (what's wrong, where, how to fix)
- [ ] Exit code 0 on pass, 1 on fail (for CI/CD)
- [ ] Document in CLAUDE.md under "Validation Workflow"
- [ ] Test with intentional schema mismatch (should catch it)

### Implementation Timeline
- Phase 0.8, estimated 3-4 hours
- Levels 1-7: Phase 0.8 (core validation)
- Level 8: Phase 0.8 or later (cross-doc consistency)

---

## Implementation Timeline

### Phase 0.8 (Estimated: 8-9 hours total)

**Week 1: Pre-Commit Infrastructure**
- [ ] DEF-001: Pre-commit hooks setup (2 hours)
  - Install pre-commit framework
  - Configure `.pre-commit-config.yaml`
  - Test on all files
  - Document in CLAUDE.md

- [ ] DEF-004: Line ending fix (1 hour)
  - Re-commit test files with LF
  - Verify CI passes
  - Validate pre-commit hooks catch future issues

**Week 2: Schema Validation and Pre-Push Hooks**
- [ ] DEF-008: Database schema validation script (3-4 hours)
  - Implement 8 validation levels
  - Integrate into validate_all.sh
  - Add to pre-commit hooks (conditional)
  - Test with intentional mismatches
  - Document in CLAUDE.md

- [ ] DEF-002: Pre-push hooks setup (1 hour)
  - Create pre-push script
  - Test validation checks
  - Document bypass procedure

- [ ] DEF-003: Branch protection rules (30 min)
  - Configure GitHub settings
  - Test PR workflow
  - Document in CLAUDE.md

### Phase 1+ (As Needed)
- [ ] DEF-005: No print() hook (30 min)
- [ ] DEF-006: Merge conflict hook (already done in DEF-001)
- [ ] DEF-007: Branch name convention (30 min)

---

## Success Metrics

### Pre-Commit Hooks (DEF-001)
- ✅ 0 "would reformat" errors in CI after implementation
- ✅ 50% reduction in CI failures due to linting/formatting
- ✅ <5 second hook execution time

### Pre-Push Hooks (DEF-002)
- ✅ 70% reduction in CI failures overall
- ✅ <60 second hook execution time
- ✅ Catches type errors before pushing

### Branch Protection (DEF-003)
- ✅ 0 direct pushes to main (all via PRs)
- ✅ All PRs require CI to pass
- ✅ Clean Git history (linear)

### Line Endings (DEF-004)
- ✅ All files use LF endings
- ✅ CI Quick Validation Suite passes
- ✅ No CRLF warnings in Git

---

## References

- **Pre-commit framework**: https://pre-commit.com/
- **Ruff pre-commit**: https://github.com/astral-sh/ruff-pre-commit
- **GitHub branch protection**: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- **Git hooks documentation**: https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks

---

## Notes

### Why These Are Deferred

1. **Not blocking Phase 1**: Database and API work can proceed without these
2. **CI already functional**: Current CI catches all issues (just slower)
3. **Time constraints**: Phase 0.7 focus was getting CI working, not perfecting it
4. **Learning opportunity**: Better to implement hooks after seeing real CI failures

### When to Re-Evaluate

- **After 10 commits to Phase 1**: If CI failures are frequent (>20%), prioritize DEF-001/002
- **Before adding team members**: Branch protection (DEF-003) becomes critical
- **After first production deployment**: Security hooks become higher priority

---

**END OF DEFERRED TASKS DOCUMENT**
