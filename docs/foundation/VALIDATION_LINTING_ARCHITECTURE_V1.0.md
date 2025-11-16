# Validation & Linting Architecture V1.0

**Document Type:** Foundation
**Status:** ✅ Active
**Version:** 1.0
**Created:** 2025-10-29
**Phase:** 0.6c (Documentation Quality & Tooling)
**Owner:** Development Team
**Applies to:** All Phases (0.6c - 10)

---

## Executive Summary

This document defines the **Validation & Linting Architecture** for Precog - a comprehensive suite of automated tools to ensure quality and consistency across **both code and documentation**.

**Philosophy:** Treat documentation with the same rigor as code. Automate validation to prevent drift.

**Key Components:**
- **Ruff:** Code formatter + linter (replaces black + flake8)
- **Mypy:** Type checker
- **validate_docs.py:** Documentation consistency validator
- **Shell scripts:** Layered validation (quick 3s, full 60s)
- **Phase Completion integration:** Objective quality gates

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Code Quality (Ruff + Mypy)](#code-quality-ruff--mypy)
3. [Documentation Validation](#documentation-validation)
4. [Validation Scripts](#validation-scripts)
5. [Integration & Workflow](#integration--workflow)
6. [Phase Completion Protocol](#phase-completion-protocol)
7. [Future Enhancements](#future-enhancements)

---

## Architecture Overview

### Three-Tier Validation

```
┌─────────────────────────────────────────────────────────┐
│               VALIDATION ARCHITECTURE                    │
└─────────────────────────────────────────────────────────┘

Tier 1: Code Quality (Python)
    ├─ Ruff (formatter + linter) - 10-100x faster than flake8
    └─ Mypy (type checking) - Catch type errors before runtime

Tier 2: Documentation Validation (Markdown)
    ├─ validate_docs.py - ADR consistency, REQ consistency
    ├─ validate_docs.py - MASTER_INDEX accuracy
    └─ fix_docs.py - Auto-fix simple issues

Tier 3: Integration
    ├─ validate_quick.sh - Fast feedback (3 sec)
    ├─ validate_all.sh - Complete validation (60 sec)
    └─ Phase Completion Protocol - Objective quality gates
```

### Design Principles

1. **Layered Execution:** Fast validation (3s) for development, comprehensive (60s) for commits
2. **Auto-Fix Capability:** Ruff and fix_docs.py auto-fix most issues
3. **Fail Fast:** Exit on first error for rapid feedback
4. **Documentation as Code:** Same rigor for docs as for code

---

## Code Quality (Ruff + Mypy)

### Ruff: Modern Code Quality Tool

**Replaces:** black (formatter) + flake8 (linter) + isort (import sorting) + 50+ other tools

**Why Ruff:**
- **10-100x faster** than flake8 (written in Rust)
- **Single tool** for formatting + linting
- **Auto-fix** capability for most issues
- **Industry standard** (2024+)
- **Active development** (monthly releases)

#### Ruff Configuration

**Location:** `pyproject.toml`

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "DTZ",    # flake8-datetimez
    # ... 20+ more rule sets
]

ignore = [
    "E501",   # Line too long (handled by formatter)
]

fixable = ["ALL"]  # Allow auto-fixes

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports
"tests/**/*.py" = ["S101"]  # Allow assert statements
```

#### Ruff Usage

```bash
# Check code (linting)
ruff check .

# Check and auto-fix
ruff check --fix .

# Format code
ruff format .

# Check formatting without changing files
ruff format --check .
```

**Integration:**
- Runs automatically in `validate_quick.sh`
- Runs before tests in `validate_all.sh`
- Fast (~1 second for entire codebase)

---

### Mypy: Static Type Checking

**Purpose:** Catch type errors before runtime

#### Mypy Configuration

**Location:** `pyproject.toml`

```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
check_untyped_defs = true
disallow_untyped_defs = false  # Start permissive, tighten later
show_error_codes = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # Tests can be less strict
```

#### Mypy Usage

```bash
# Type check all code
mypy .

# Check specific module
mypy database/

# Show error codes
mypy --show-error-codes .
```

**Benefits:**
- Catch type mismatches before runtime
- Better IDE autocomplete
- Self-documenting code (type hints)
- Easier refactoring

---

## Documentation Validation

### validate_docs.py: Automated Consistency Checker

**Location:** `scripts/validate_docs.py`

**Purpose:** Prevent document drift by validating paired documents stay synchronized

#### Validation Checks

**1. ADR Consistency**
- All ADRs in ARCHITECTURE_DECISIONS appear in ADR_INDEX
- All ADRs in ADR_INDEX appear in ARCHITECTURE_DECISIONS
- No duplicate ADR numbers
- Sequential numbering (warns on gaps)

**2. Requirement Consistency**
- All REQ-XXX-NNN in MASTER_REQUIREMENTS appear in REQUIREMENT_INDEX
- All REQ-XXX-NNN in REQUIREMENT_INDEX appear in MASTER_REQUIREMENTS
- Status fields match

**3. MASTER_INDEX Accuracy**
- All listed documents exist at stated location
- Version in filename matches version in MASTER_INDEX
- No unlisted documents exist (warns)

**4. Cross-Reference Validation**
- All `*.md` references point to existing files
- No broken links in foundation documents

**5. Version Header Validation**
- All documents have version headers
- Version in filename matches version in header

#### Usage

```bash
# Run all validation checks
python scripts/validate_docs.py

# Auto-fix simple issues
python scripts/fix_docs.py

# Dry-run (show what would be fixed)
python scripts/fix_docs.py --dry-run
```

#### Example Output

```
==========================================================
Documentation Validation Suite - Phase 0.6c
==========================================================

Running validation checks...

✅ ADR Consistency (47 ADRs)
✅ Requirement Consistency (127 requirements)
⚠️  MASTER_INDEX Validation (89 docs listed)
   ⚠️  3 documents exist but not in MASTER_INDEX: ...
✅ Cross-Reference Validation
✅ Version Header Validation (89 docs checked)

==========================================================
✅ ALL VALIDATION CHECKS PASSED (4/5 passed, 1 warning)
==========================================================
```

---

### fix_docs.py: Automated Fixer

**Location:** `scripts/fix_docs.py`

**Purpose:** Auto-fix simple documentation issues

#### Auto-Fixable Issues

1. **Version header mismatches**
   - Filename: `MASTER_REQUIREMENTS_V2.15.md`
   - Header: `Version: 2.11`
   - Fix: Update header to `2.11`

2. **Missing documents in MASTER_INDEX**
   - Reports unlisted documents (manual addition recommended)

#### Non-Auto-Fixable (Require Human Judgment)

- ADR number conflicts
- Content contradictions
- Broken cross-references (which document is correct?)
- Missing ADR/requirement content

#### Usage

```bash
# Fix issues
python scripts/fix_docs.py

# Dry-run (see what would be fixed)
python scripts/fix_docs.py --dry-run
```

---

## Validation Scripts

### validate_quick.sh: Fast Validation

**Duration:** ~3 seconds
**Use Case:** During active development (every 2-5 minutes)

**What it runs:**
1. Ruff linting (`ruff check .`)
2. Ruff formatting check (`ruff format --check .`)
3. Mypy type checking (`mypy .`)
4. Documentation validation (`python scripts/validate_docs.py`)

**When to use:**
- After making code changes
- Before running tests
- Quick sanity check

**Example:**
```bash
./scripts/validate_quick.sh

# Output:
========================================
Quick Validation (Code Quality + Docs)
========================================

1. Ruff Linting
---------------
  ✅ Ruff lint: No issues

2. Ruff Formatting
------------------
  ✅ Ruff format: All code properly formatted

3. Mypy Type Checking
---------------------
  ✅ Mypy: No type errors

4. Documentation Validation
---------------------------
  ✅ Documentation: All checks passed

========================================
✅ QUICK VALIDATION PASSED
========================================
```

---

### test_fast.sh: Unit Tests Only

**Duration:** ~5 seconds
**Use Case:** TDD workflow, rapid feedback

**What it runs:**
- Unit tests only (`tests/unit/`)
- No coverage report

**When to use:**
- During TDD (red-green-refactor)
- After small code changes
- Rapid iteration

---

### test_full.sh: Complete Test Suite

**Duration:** ~30 seconds
**Use Case:** Before commits

**What it runs:**
- All tests (unit + integration)
- Full coverage report (HTML + XML)
- Saves results to `test_results/TIMESTAMP/`

**When to use:**
- Before committing
- End of development session
- Before creating PR

**Output:**
- `test_results/latest/pytest_report.html`
- `htmlcov/index.html`
- `coverage.xml`

---

### validate_all.sh: Complete Validation

**Duration:** ~60 seconds
**Use Case:** Before commits, phase completion

**What it runs:**
1. **validate_quick.sh** - Code quality + docs
2. **test_full.sh** - All tests + coverage
3. **Security scan** - Hardcoded credentials check

**Security Checks:**
```bash
# Search for hardcoded passwords, API keys, tokens
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]"

# Search for connection strings with embedded passwords
git grep -E "(postgres://|mysql://).*:.*@"

# Check .env file not staged
git diff --cached --name-only | grep "\.env$"
```

**When to use:**
- **MANDATORY before every commit**
- Before pushing to remote
- Phase completion
- Pre-deployment

**Exit codes:**
- 0 = All checks passed (safe to commit)
- 1 = Validation failed (fix before committing)

**Example:**
```bash
./scripts/validate_all.sh

# Output:
==========================================
Precog Complete Validation Suite
==========================================

PART 1: Code Quality & Documentation
=====================================
  ✅ Quick validation passed

PART 2: Full Test Suite
========================
  ✅ All tests passed (81/81, 89% coverage)

PART 3: Security Scan
=====================
  ✅ No hardcoded credentials found
  ✅ No connection strings with embedded passwords
  ✅ .env file not staged

==========================================
✅ ALL VALIDATION CHECKS PASSED
==========================================

Ready to commit! 🎉
```

---

## Integration & Workflow

### Developer Workflow

```
┌─────────────────────────────────────────────────────────┐
│                  DEVELOPMENT WORKFLOW                    │
└─────────────────────────────────────────────────────────┘

During Development (Fast Feedback - every 2-5 minutes)
    │
    ├─> validate_quick.sh (~3 sec)
    │   ├── ruff check --fix .
    │   ├── ruff format .
    │   ├── mypy .
    │   └── python scripts/validate_docs.py
    │
    └─> test_fast.sh (~5 sec)
        └── pytest tests/unit/ -v

Before Commit (Comprehensive - every commit)
    │
    └─> validate_all.sh (~60 sec)
        ├── validate_quick.sh
        ├── test_full.sh
        └── Security scan

Before Push (Extra Thorough)
    │
    └─> validate_all.sh
        └── Manual review of changes

CI/CD (Automated on push - Phase 0.7)
    │
    └─> GitHub Actions
        ├── validate_all.sh
        ├── Upload coverage to Codecov
        └── Block merge if fails
```

---

### Validation Decision Tree

```
Code Change Made
    │
    ├─ Minor change (1-2 lines)?
    │   └─> validate_quick.sh (3s)
    │
    ├─ Significant change (new function)?
    │   ├─> validate_quick.sh (3s)
    │   └─> test_fast.sh (5s)
    │
    ├─ Ready to commit?
    │   └─> validate_all.sh (60s) ← MANDATORY
    │
    └─ Phase complete?
        └─> validate_all.sh + Phase Completion Protocol
```

---

## Phase Completion Protocol

### Updated Step 5: Testing & Validation

**Old (Pre-0.6c):**
```bash
# Manual checks
pytest tests/ -v
pytest --cov --cov-fail-under=80
```

**New (Phase 0.6c+):**
```bash
# Single command, comprehensive validation
./scripts/validate_all.sh
```

**What validate_all.sh checks:**
- ✅ Code linting (ruff)
- ✅ Code formatting (ruff)
- ✅ Type checking (mypy)
- ✅ Documentation consistency (ADRs, REQs, MASTER_INDEX)
- ✅ Cross-references valid
- ✅ Version headers consistent
- ✅ All tests passing
- ✅ Coverage ≥80%
- ✅ No hardcoded credentials
- ✅ .env not staged

**If validation fails:**
1. ⚠️ **DO NOT proceed to next phase**
2. Review validation report
3. Run auto-fixers:
   - `ruff check --fix .`
   - `ruff format .`
   - `python scripts/fix_docs.py`
4. Manually fix non-auto-fixable issues
5. Re-run `validate_all.sh` until all checks pass

---

### Phase Completion Checklist

**Step 5: Testing & Validation (8 min)**

- [ ] Run `./scripts/validate_all.sh`
  - [ ] Code quality passing (ruff, mypy)
  - [ ] Documentation validation passing
  - [ ] All tests passing (81/81 or current count)
  - [ ] Coverage ≥80%
  - [ ] Security scan clean

**If ANY check fails:**
- ❌ Phase NOT complete
- 🔧 Fix issues
- 🔄 Re-validate

**Only when ALL checks pass:**
- ✅ Phase ready for completion
- 📋 Proceed to Phase Completion Report

---

## Future Enhancements

### Phase 0.7: CI/CD Integration (Planned)

**GitHub Actions Workflow:**

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.12
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run validation suite
        run: ./scripts/validate_all.sh

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

**Benefits:**
- ✅ Automated validation on every push
- ✅ Coverage tracking over time
- ✅ Block merge if validation fails
- ✅ Team collaboration ready

**Reference:** REQ-CICD-001, ADR-052

---

### Phase 0.7: Advanced Validation (Planned)

#### Semantic Documentation Validation

Beyond syntax, check semantics:
- REQ-XXX-NNN status matches implementation
- ADR-XXX decisions match code architecture
- DEVELOPMENT_PHASES progress accurate

#### Dependency Analysis

Validate Python imports vs requirements.txt:
```python
# Find all imports
# Compare with requirements.txt
# Report missing dependencies
```

#### Documentation Spell-Check

Integrate spell-checking into validation:
```bash
# Check all markdown files
aspell check docs/**/*.md
```

#### Security Scanning Integration

**Tools:**
- Bandit (Python security linter)
- Safety (dependency vulnerability scanner)

**Integration:**
```bash
# In validate_all.sh
bandit -r . -ll
safety check
```

**Reference:** REQ-TEST-008, ADR-053

---

## Validation Metrics

Track validation health over time:

```json
{
    "date": "2025-10-29",
    "code_quality": {
        "ruff_issues": 0,
        "mypy_errors": 0
    },
    "documentation": {
        "adr_issues": 0,
        "requirement_issues": 0,
        "master_index_issues": 0,
        "broken_links": 0
    },
    "tests": {
        "passing": 81,
        "failing": 0,
        "coverage_pct": 89.2
    },
    "validation_duration_sec": 62.4,
    "overall_status": "PASS"
}
```

**Visualization (Future):**
- Track issues over time (should trend toward zero)
- Coverage percentage (should trend toward 100%)
- Validation run time (optimize if >90 seconds)

---

## Benefits

### For Code

**Ruff:**
- ✅ 10-100x faster than flake8
- ✅ Consistent style across codebase
- ✅ Auto-fix most issues
- ✅ Catch bugs early (flake8-bugbear rules)

**Mypy:**
- ✅ Catch type errors before runtime
- ✅ Better IDE autocomplete
- ✅ Self-documenting code
- ✅ Safer refactoring

### For Documentation

**validate_docs.py:**
- ✅ Prevent document drift
- ✅ Paired documents stay synchronized
- ✅ MASTER_INDEX always accurate
- ✅ No broken cross-references

**fix_docs.py:**
- ✅ Auto-fix simple issues
- ✅ Save manual work
- ✅ Consistency maintained

### For Project

**Validation Scripts:**
- ✅ Objective quality gates ("validation passes" = ready)
- ✅ Fast feedback during development (3s)
- ✅ Comprehensive before commits (60s)
- ✅ Less time debugging inconsistencies
- ✅ More time building features

---

## Configuration Files

### pyproject.toml (Complete Configuration)

**Single file contains:**
- Ruff configuration (formatter + linter)
- Mypy configuration (type checking)
- Pytest configuration (testing)
- Coverage configuration (thresholds)

**Location:** `C:\Users\emtol\repos\precog-repo\pyproject.toml`

**Size:** ~300 lines
**Scope:** All code quality tools

---

### .gitignore (Updated for Phase 0.6c)

**Added:**
```
# Ruff cache
.ruff_cache/

# Mypy cache
.mypy_cache/

# Test results (keep history.json, ignore timestamped runs)
test_results/*/
!test_results/README.md

# Coverage reports
coverage.xml
```

---

## Commands Quick Reference

### Code Quality

```bash
# Ruff - Linting
ruff check .                    # Check code
ruff check --fix .              # Check and auto-fix

# Ruff - Formatting
ruff format .                   # Format code
ruff format --check .           # Check formatting

# Mypy - Type Checking
mypy .                          # Type check all code
mypy --show-error-codes .       # Show error codes
```

### Documentation

```bash
# Validation
python scripts/validate_docs.py

# Auto-Fix
python scripts/fix_docs.py
python scripts/fix_docs.py --dry-run
```

### Testing

```bash
# Fast (unit tests only)
./scripts/test_fast.sh          # ~5 seconds

# Full (all tests + coverage)
./scripts/test_full.sh          # ~30 seconds
```

### Validation

```bash
# Quick (code quality + docs)
./scripts/validate_quick.sh     # ~3 seconds

# Complete (everything)
./scripts/validate_all.sh       # ~60 seconds
```

---

## Troubleshooting

### Ruff Issues

**Problem:** Ruff reports formatting issues
**Solution:**
```bash
ruff format .  # Auto-formats all code
```

**Problem:** Ruff reports linting issues
**Solution:**
```bash
ruff check --fix .  # Auto-fixes most issues
ruff check .        # Show remaining issues
```

### Mypy Issues

**Problem:** Mypy reports type errors
**Solution:**
- Add type hints to function signatures
- Use `# type: ignore` for false positives (sparingly)
- Check pyproject.toml for strictness settings

### Documentation Validation Issues

**Problem:** ADR-XXX missing from ADR_INDEX
**Solution:**
- Add to ADR_INDEX manually
- Follow Update Cascade Rule 2 (CLAUDE.md Section 5)

**Problem:** Version mismatch (filename vs header)
**Solution:**
```bash
python scripts/fix_docs.py  # Auto-fixes version mismatches
```

### Test Failures

**Problem:** Tests failing in validate_all.sh
**Solution:**
```bash
# Run tests directly to see detailed output
pytest tests/ -vv

# Run specific failing test
pytest tests/unit/test_specific.py -vv

# Debug with pdb
pytest tests/unit/test_specific.py --pdb
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-29 | Initial creation (Phase 0.6c) |

---

## Related Documents

- **Testing:** `TESTING_STRATEGY_V2.1.md` - Comprehensive testing infrastructure
- **Requirements:** `MASTER_REQUIREMENTS_V2.15.md` - REQ-VALIDATION-001, REQ-VALIDATION-002
- **ADRs:** `ARCHITECTURE_DECISIONS_V2.15.md` - ADR-048 (Ruff), ADR-050 (Doc Validation), ADR-051 (Layered Validation), ADR-054 (Bandit→Ruff Migration), ADR-075 (Multi-Source Warning Governance), ADR-076 (Dynamic Ensemble Weights), ADR-077 (Strategy vs Method Separation)
- **Process:** `CLAUDE.md V1.1` - Section 5 (Document Cohesion), Section 9 (Phase Completion Protocol)
- **Configuration:** `pyproject.toml` - All tool configurations

---

**END OF VALIDATION_LINTING_ARCHITECTURE_V1.0.md**
