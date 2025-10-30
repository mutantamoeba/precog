#!/bin/bash
# validate_all.sh - Complete validation suite (linting + docs + tests + security)
# Phase 0.6c - Validation Infrastructure
# Usage: ./scripts/validate_all.sh
# Time: ~60 seconds (run before commits and phase completion)

set -e  # Exit on first error

echo "=========================================="
echo "Precog Complete Validation Suite"
echo "=========================================="
echo ""

# Track overall success
FAILED=0

# PART 1: Quick Validation (Code Quality + Docs)
echo "PART 1: Code Quality & Documentation"
echo "====================================="
echo ""

if bash scripts/validate_quick.sh ; then
    echo "  [OK] Quick validation passed"
else
    echo "  [FAIL] Quick validation failed"
    FAILED=1
fi

echo ""
echo ""

# PART 2: Full Test Suite
echo "PART 2: Full Test Suite"
echo "========================"
echo ""

if bash scripts/test_full.sh ; then
    echo "  [OK] All tests passed"
else
    echo "  [FAIL] Tests failed"
    FAILED=1
fi

echo ""
echo ""

# PART 3: Security Scan
echo "PART 3: Security Scan"
echo "====================="
echo ""

echo "Scanning for hardcoded credentials..."

# Search for hardcoded passwords, API keys, tokens (exclude tests and scripts)
if git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql' ':!tests/' ':!scripts/' 2>/dev/null ; then
    echo "  [FAIL] SECURITY ISSUE: Hardcoded credentials found!"
    echo "     Remove hardcoded credentials and use environment variables"
    FAILED=1
else
    echo "  [OK] No hardcoded credentials found (tests/ and scripts/ excluded)"
fi

echo ""

# Check for connection strings with passwords (exclude tests and scripts)
if git grep -E "(postgres://|mysql://).*:.*@" -- '*.py' '*.yaml' ':!tests/' ':!scripts/' 2>/dev/null ; then
    echo "  [FAIL] SECURITY ISSUE: Connection strings with embedded passwords found!"
    FAILED=1
else
    echo "  [OK] No connection strings with embedded passwords (tests/ and scripts/ excluded)"
fi

echo ""

# Check .env file not staged
if git diff --cached --name-only 2>/dev/null | grep "\.env$" ; then
    echo "  [FAIL] SECURITY ISSUE: .env file is staged for commit!"
    echo "     Run: git reset HEAD .env"
    FAILED=1
else
    echo "  [OK] .env file not staged"
fi

echo ""
echo ""

# SUMMARY
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "[OK] ALL VALIDATION CHECKS PASSED"
    echo "=========================================="
    echo ""
    echo "Ready to commit!"
    exit 0
else
    echo "[FAIL] VALIDATION FAILED"
    echo "=========================================="
    echo ""
    echo "Fix issues above before committing."
    echo ""
    echo "Common fixes:"
    echo "  - Code formatting: python -m ruff format ."
    echo "  - Code linting: python -m ruff check --fix ."
    echo "  - Documentation: python scripts/fix_docs.py"
    echo "  - Security: Remove hardcoded credentials"
    exit 1
fi
