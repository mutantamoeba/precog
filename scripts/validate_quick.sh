#!/bin/bash
# validate_quick.sh - Quick validation (code quality only, no tests)
# Usage: ./scripts/validate_quick.sh
# Time: ~3-10 seconds (fast feedback during development)
#
# Test levels (run manually as needed):
#   Quick:  python -m pytest tests/unit/ -q --no-cov -n auto              (~30s)
#   Medium: python -m pytest tests/unit/ tests/integration/ tests/e2e/ -q --no-cov  (~60-90s, same as pre-push)
#   Full:   python -m pytest tests/ -q --no-cov                           (~3-5 min, same as CI)
#
# NOTE: Only checks tracked files (excludes untracked WIP files)
# This allows skeleton tests to exist without blocking commits/pushes

set -e  # Exit on first error

echo "=========================================="
echo "Quick Validation (Code Quality)"
echo "=========================================="
echo ""

# Track overall success
FAILED=0

# Get list of tracked Python files (excludes untracked WIP)
TRACKED_PY_FILES=$(git ls-files '*.py' | tr '\n' ' ')

# 1. Ruff - Code Linting (tracked files only)
echo "1. Ruff Linting"
echo "---------------"
if [ -n "$TRACKED_PY_FILES" ]; then
    if python -m ruff check $TRACKED_PY_FILES ; then
        echo "  [OK] Ruff lint: No issues"
    else
        echo "  [FAIL] Ruff lint: Issues found"
        echo "     Run: python -m ruff check --fix . (to auto-fix)"
        FAILED=1
    fi
else
    echo "  [OK] Ruff lint: No tracked Python files"
fi

echo ""

# 2. Ruff - Code Formatting (tracked files only)
echo "2. Ruff Formatting"
echo "------------------"
if [ -n "$TRACKED_PY_FILES" ]; then
    if python -m ruff format --check $TRACKED_PY_FILES ; then
        echo "  [OK] Ruff format: All code properly formatted"
    else
        echo "  [FAIL] Ruff format: Formatting issues found"
        echo "     Run: python -m ruff format . (to auto-fix)"
        FAILED=1
    fi
else
    echo "  [OK] Ruff format: No tracked Python files"
fi

echo ""

# 3. Mypy - Type Checking (with incremental caching)
# Caches in .mypy_cache/ - first run ~20-30s, subsequent ~5-10s
echo "3. Mypy Type Checking (incremental)"
echo "------------------------------------"
if python -m mypy . --incremental --cache-dir .mypy_cache --exclude 'tests/' --exclude '_archive/' --exclude 'venv/' --exclude '.venv/' --ignore-missing-imports ; then
    echo "  [OK] Mypy: No type errors"
else
    echo "  [FAIL] Mypy: Type errors found"
    FAILED=1
fi

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "[OK] QUICK VALIDATION PASSED"
    echo "=========================================="
    exit 0
else
    echo "[FAIL] QUICK VALIDATION FAILED"
    echo "Fix issues above before committing"
    echo "=========================================="
    exit 1
fi
