#!/bin/bash
# test_fast.sh - Run unit tests only (fast feedback during development)
# Phase 0.6c - Testing Infrastructure
# Usage: ./scripts/test_fast.sh

set -e  # Exit on error

echo "=========================================="
echo "Fast Test Suite (Unit Tests Only)"
echo "=========================================="
echo ""

# Run unit tests only (no coverage for speed)
python -m pytest tests/test_config_loader.py tests/test_logger.py -v --no-cov

echo ""
echo "[OK] Fast tests complete"
