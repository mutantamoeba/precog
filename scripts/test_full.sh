#!/bin/bash
# test_full.sh - Run full test suite with coverage
# Phase 0.6c - Testing Infrastructure
# Usage: ./scripts/test_full.sh

set -e  # Exit on error

echo "=========================================="
echo "Full Test Suite with Coverage"
echo "=========================================="
echo ""

# Create timestamp for this run
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S 2>/dev/null || echo "latest")
RESULT_DIR="test_results/$TIMESTAMP"

# Create result directory
mkdir -p "$RESULT_DIR" 2>/dev/null || true

echo "Test results will be saved to: $RESULT_DIR"
echo ""

# Run all tests with coverage
python -m pytest tests/ -v \
    --cov=. \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml \
    --html="$RESULT_DIR/pytest_report.html" \
    --self-contained-html \
    | tee "$RESULT_DIR/test_output.log" || true

# Update latest symlink (if on Unix-like system)
if command -v ln &> /dev/null; then
    rm -f test_results/latest 2>/dev/null || true
    ln -sf "$TIMESTAMP" test_results/latest 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "Test Results:"
echo "  - Report: $RESULT_DIR/pytest_report.html"
echo "  - Coverage: htmlcov/index.html"
echo "  - Log: $RESULT_DIR/test_output.log"
echo "=========================================="
