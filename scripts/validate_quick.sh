#!/bin/bash
# validate_quick.sh - Quick validation (code quality + docs, no tests)
# Phase 0.6c - Validation Infrastructure
# Usage: ./scripts/validate_quick.sh
# Time: ~3 seconds (fast feedback during development)

set -e  # Exit on first error

echo "=========================================="
echo "Quick Validation (Code Quality + Docs)"
echo "=========================================="
echo ""

# Track overall success
FAILED=0

# 1. Ruff - Code Linting
echo "1. Ruff Linting"
echo "---------------"
if ruff check . ; then
    echo "  ✅ Ruff lint: No issues"
else
    echo "  ❌ Ruff lint: Issues found"
    echo "     Run: ruff check --fix . (to auto-fix)"
    FAILED=1
fi

echo ""

# 2. Ruff - Code Formatting
echo "2. Ruff Formatting"
echo "------------------"
if ruff format --check . ; then
    echo "  ✅ Ruff format: All code properly formatted"
else
    echo "  ❌ Ruff format: Formatting issues found"
    echo "     Run: ruff format . (to auto-fix)"
    FAILED=1
fi

echo ""

# 3. Mypy - Type Checking
echo "3. Mypy Type Checking"
echo "---------------------"
if mypy . ; then
    echo "  ✅ Mypy: No type errors"
else
    echo "  ❌ Mypy: Type errors found"
    FAILED=1
fi

echo ""

# 4. Documentation Validation
echo "4. Documentation Validation"
echo "---------------------------"
if python scripts/validate_docs.py ; then
    echo "  ✅ Documentation: All checks passed"
else
    echo "  ❌ Documentation: Issues found"
    echo "     Run: python scripts/fix_docs.py (to auto-fix some issues)"
    FAILED=1
fi

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "✅ QUICK VALIDATION PASSED"
    echo "=========================================="
    exit 0
else
    echo "❌ QUICK VALIDATION FAILED"
    echo "Fix issues above before committing"
    echo "=========================================="
    exit 1
fi
