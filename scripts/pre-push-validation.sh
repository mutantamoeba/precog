#!/bin/bash
# Pre-push hook - Full local gate (branch check + unit/integration/e2e + stress/chaos)
# CI handles: property, security, performance tests + doc validation
# Stress/chaos run HERE only (they hang on CI runners due to threading + 2 vCPUs)
#
# Runs:
#   0. Branch name verification
#   0.25. Stale bytecode cleanup
#   1. Unit tests (parallel, no DB)
#   2. Integration + E2E tests (sequential, needs DB)
#   3. Stress & Chaos tests (full suite, ~992 tests)
#
# Logging: Full verbose output goes to .pre-push-logs/ (retained 30 days).
#          Console shows only summaries and failures.
#
# Speed: ~9-10 minutes
# Bypass: git push --no-verify
# Full suite: python -m pytest tests/ -q --no-cov

START_TIME=$(date +%s)

# ==============================================================================
# STEP -1: Skip validation for branch deletions (git push --delete)
# ==============================================================================
# Pre-push hook receives lines on stdin: <local ref> <local sha> <remote ref> <remote sha>
# Branch deletions send a zero SHA as local_sha. Detect and skip.
while read local_ref local_sha remote_ref remote_sha; do
    if [[ "$local_sha" == "0000000000000000000000000000000000000000" ]]; then
        echo "Branch deletion detected — skipping pre-push validation."
        exit 0
    fi
done

echo ""
echo "Running pre-push validation..."
echo ""

cd "$(git rev-parse --show-toplevel)"

# ==============================================================================
# LOGGING SETUP: verbose output to file, summaries to console
# ==============================================================================
LOG_DIR=".pre-push-logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/pre-push-${TIMESTAMP}.log"

# Retention: remove logs older than 30 days
find "$LOG_DIR" -name "pre-push-*.log" -mtime +30 -delete 2>/dev/null || true
find "$LOG_DIR" -name "pre-push-*.json" -mtime +30 -delete 2>/dev/null || true

echo "Pre-push validation started at $(date)" > "$LOG_FILE"
echo "Branch: $(git rev-parse --abbrev-ref HEAD)" >> "$LOG_FILE"
echo "Commit: $(git rev-parse --short HEAD)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# run_step: runs a pytest command, logs full output, shows only summary/failures
# Usage: run_step "Step Name" pytest_args...
run_step() {
    local step_name="$1"
    shift
    local step_start=$(date +%s)

    echo "" >> "$LOG_FILE"
    echo "=== $step_name ===" >> "$LOG_FILE"
    echo "Command: python -m pytest $*" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # Run tests, capture full output to log, extract summary for console
    local output
    output=$(python -m pytest "$@" 2>&1)
    local exit_code=$?

    echo "$output" >> "$LOG_FILE"

    local step_end=$(date +%s)
    local step_duration=$((step_end - step_start))

    if [[ $exit_code -eq 0 ]]; then
        # Show only the summary line (last non-empty line with pass/skip counts)
        local summary
        summary=$(echo "$output" | grep -E "^=+ .+ =+$" | tail -1)
        if [[ -z "$summary" ]]; then
            # Fallback: grab last line with "passed"
            summary=$(echo "$output" | grep -E "passed" | tail -1)
        fi
        echo "  $step_name: PASSED (${step_duration}s) — $summary"
        echo "RESULT: PASSED (${step_duration}s)" >> "$LOG_FILE"
    else
        echo ""
        echo "  $step_name: FAILED"
        echo ""
        # Show failure details (short traceback + summary)
        echo "$output" | grep -E "^(FAILED|ERROR|E |    |tests/)" | head -30
        echo ""
        echo "$output" | grep -E "^=+ .+ =+$" | tail -1
        echo ""
        echo "Full output: $LOG_FILE"
        echo "RESULT: FAILED (${step_duration}s)" >> "$LOG_FILE"
        return 1
    fi
}

# ==============================================================================
# STEP 0: Branch Name Verification
# ==============================================================================
current_branch=$(git rev-parse --abbrev-ref HEAD)

if [[ "$current_branch" == "main" ]]; then
    echo "ERROR: Cannot push directly to main branch!"
    echo "Use feature branch workflow: git checkout -b feature/your-feature-name"
    exit 1
fi

if [[ ! "$current_branch" =~ ^(feature/|bugfix/|refactor/|docs/|test/).*$ ]]; then
    echo "ERROR: Branch name '$current_branch' doesn't follow convention"
    echo "Required: feature/, bugfix/, refactor/, docs/, or test/ prefix"
    exit 1
fi
echo "Branch OK: $current_branch"
echo ""

# ==============================================================================
# STEP 0.1: Set Test Environment (prevents running tests against dev/prod DB)
# ==============================================================================
export PRECOG_ENV=test

# ==============================================================================
# STEP 0.25: Clean Stale Bytecode (prevents ghost test discovery)
# ==============================================================================
find tests/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ==============================================================================
# STEP 1: Unit Tests (parallel, no DB)
# ==============================================================================
echo "Running tests (verbose output logged to $LOG_FILE)..."
echo ""
if ! run_step "Unit tests" tests/unit/ --no-cov --tb=short -n auto -q; then
    echo ""
    echo "Unit tests failed. Fix before pushing."
    exit 1
fi

# ==============================================================================
# STEP 2: Integration + E2E Tests (sequential, needs DB)
# ==============================================================================
if ! run_step "Integration + E2E" tests/integration/ tests/e2e/ --no-cov --tb=short -p no:xdist -q; then
    echo ""
    echo "Integration/E2E tests failed. Fix before pushing."
    exit 1
fi

# ==============================================================================
# STEP 3: Stress, Chaos & Race Tests (full suite, skipped in CI)
# ==============================================================================
# Stress/chaos/race tests use threading heavily and hang on CI runners (2 vCPUs).
# Pre-push is their only automated gate. CI only verifies collection.
# Runs all stress + chaos + race tests (~1100 tests, ~3 min).
if ! run_step "Stress + Chaos + Race" tests/stress/ tests/chaos/ tests/race/ --no-cov --tb=short -q --timeout=120 --timeout-method=thread; then
    echo ""
    echo "Stress/chaos/race tests failed. Fix before pushing."
    exit 1
fi

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

echo ""
echo "All pre-push checks passed! (${TOTAL_DURATION}s)"
echo "CI will run remaining tests (property, security, performance)."
echo "Full local suite: python -m pytest tests/ -q --no-cov"

echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "TOTAL: PASSED (${TOTAL_DURATION}s)" >> "$LOG_FILE"

exit 0
