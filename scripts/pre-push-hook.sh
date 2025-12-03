#!/bin/bash
# Pre-push hook - Phase 1.9 ENHANCED (ALL 8 TEST TYPES - MANDATORY)
# Runs comprehensive validation before pushing to remote
#
# This hook runs automatically on 'git push' and performs:
# 1. Quick validation (code quality + documentation) - SEQUENTIAL
# 2-11. Advanced checks (tests, types, security, warnings, patterns) - PARALLEL
#
# Speed: ~3-5 minutes (Step 2 runs ALL 8 test types per Phase 1.9 requirement)
# Bypass: git push --no-verify (ONLY during Phase 1.9 fix work with approval)
#
# **PHASE 1.9 REQUIREMENT (Issue #165):**
# ALL 8 test types MUST run and PASS before push:
#   - unit, property, integration, e2e, stress, chaos, security, performance
# NO tests skipped without explicit approval
# NO quick fixes or tech debt
#
# **PARALLELIZATION STRATEGY:**
# - Step 0 (branch check): MUST run first (safety)
# - Step 1 (quick validation): MUST run second (catches syntax errors)
# - Steps 2-11: Run in parallel (all independent)
#   - Step 2: ALL 8 Test Types (3-5 min) # MANDATORY per Phase 1.9
#   - Step 3: Type checking (20s)
#   - Step 4: Security scan (10s)
#   - Step 5: Warning governance (30s)
#   - Step 6: Code quality (20s)
#   - Step 7: Security patterns (10s)
#   - Step 8: SCD Type 2 queries (15s)  # Pattern 2 enforcement
#   - Step 9: Property tests (20s)      # Pattern 10 enforcement
#   - Step 10: Test fixtures (10s)      # Pattern 13 enforcement
#   - Step 11: Test type coverage (5s)  # TESTING_STRATEGY V3.2 enforcement

echo ""
echo "🔍 Running pre-push validation checks (PARALLELIZED)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# DO NOT use "set -e" when running parallel processes
# We need to manually check exit codes

# Change to repository root (in case hook is run from subdirectory)
cd "$(git rev-parse --show-toplevel)"

# ==============================================================================
# STEP 0: Branch Name Verification (MUST BE FIRST - SEQUENTIAL)
# ==============================================================================
echo "🌿 [0/11] Verifying branch name convention..."
current_branch=$(git rev-parse --abbrev-ref HEAD)

# CRITICAL: Block direct pushes to main (branch protection policy)
if [[ "$current_branch" == "main" ]]; then
  echo "❌ ERROR: Cannot push directly to main branch!"
  echo ""
  echo "Branch protection policy requires feature branch workflow:"
  echo "  1. git checkout -b feature/your-feature-name"
  echo "  2. git push -u origin feature/your-feature-name"
  echo "  3. gh pr create --title \"...\" --body \"...\""
  echo "  4. Wait for CI to pass, then merge PR"
  echo ""
  echo "To bypass (NOT RECOMMENDED - CI will still block): git push --no-verify"
  exit 1
fi

# Verify feature branch naming convention
if [[ ! "$current_branch" =~ ^(feature/|bugfix/|refactor/|docs/|test/).*$ ]]; then
  echo "❌ ERROR: Branch name '$current_branch' doesn't follow convention"
  echo ""
  echo "Required format:"
  echo "  - feature/descriptive-name    (new features)"
  echo "  - bugfix/issue-number-desc    (bug fixes)"
  echo "  - refactor/what-being-changed (refactoring)"
  echo "  - docs/what-documenting       (documentation)"
  echo "  - test/what-testing           (test additions)"
  echo ""
  echo "Example: feature/kalshi-api-client"
  echo ""
  echo "To bypass (emergency only): git push --no-verify"
  exit 1
fi
echo "✅ Branch name follows convention: $current_branch"
echo ""

# ==============================================================================
# STEP 1: Quick Validation (MUST RUN BEFORE PARALLEL CHECKS - SEQUENTIAL)
# ==============================================================================
echo "📋 [1/11] Running quick validation (Ruff + docs)..."
if bash scripts/validate_quick.sh; then
    echo "✅ Quick validation passed"
else
    echo "❌ Quick validation failed"
    echo ""
    echo "Fix issues above, then try pushing again."
    echo "To bypass (NOT RECOMMENDED): git push --no-verify"
    exit 1
fi

echo ""
echo "⚡ Starting parallel validation (steps 2-11)..."
echo "   This will take ~3-5 minutes (Step 2 runs ALL 8 test types per Phase 1.9)"
echo ""

# ==============================================================================
# STEPS 2-10: PARALLEL EXECUTION
# ==============================================================================

# Create temp directory for parallel output
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Background process tracking
declare -A PIDS
declare -A OUTPUTS
declare -A NAMES

# Helper function to run check in background
run_parallel_check() {
    local step_num=$1
    local step_name=$2
    local output_file="$TEMP_DIR/step_${step_num}.txt"

    # Capture output to file, return exit code
    shift 2
    "$@" > "$output_file" 2>&1
    echo $? > "$output_file.exit"
}

# ==============================================================================
# STEP 2: ALL 8 Test Types - Phase 1.9 MANDATORY (Issue #165)
# ==============================================================================
# Runs ALL 8 test types as required by Phase 1.9 and TESTING_STRATEGY V3.2:
#   - unit: 409 tests (parallel - no DB)
#   - property: 101 tests (parallel - no DB)
#   - integration: 175 tests (sequential - uses DB)
#   - e2e: 134 tests (sequential - uses DB)
#   - stress: 59 tests (sequential - uses DB)
#   - chaos: 25 tests (sequential - uses DB)
#   - security: 69 tests (sequential - uses DB)
#   - performance: 8 tests (sequential - uses DB)
#
# REQUIREMENTS (per Issue #165):
#   1. ALL tests must pass (no failures)
#   2. NO tests skipped without explicit approval
#   3. NO quick fixes or tech debt
#   4. Test isolation must be proper (transactions, cleanup fixtures)
#
# STRATEGY (matches CI configuration):
#   - Unit/property tests run in PARALLEL (-n auto): Fast, all mocked, no DB conflicts
#   - Database tests run SEQUENTIALLY (-p no:xdist): Reliable, avoids deadlocks
#   - Total time: ~2 min (vs 5 min all-sequential, vs 47s all-parallel-with-errors)
#
# If tests fail due to database contamination, FIX THE ROOT CAUSE:
#   - Add proper transaction-based isolation
#   - Add cleanup fixtures
#   - Fix missing foreign key dependencies
#   - DO NOT reduce test scope
{
    run_parallel_check 2 "All 8 Test Types" bash -c '
        # Stage 1: Unit tests (parallel, no DB)
        echo "=== Stage 1/3: Unit Tests (parallel) ==="
        python -m pytest tests/unit/ -v --no-cov --tb=short -n auto || exit 1

        # Stage 2: Non-DB property tests (parallel)
        echo ""
        echo "=== Stage 2/3: Property Tests - Non-DB (parallel) ==="
        python -m pytest tests/property/api_connectors/ tests/property/test_config_validation_properties.py tests/property/test_edge_detection_properties.py tests/property/test_kelly_criterion_properties.py tests/property/test_strategy_versioning_properties.py tests/property/utils/ tests/property/schedulers/ -v --no-cov --tb=short -n auto --ignore=tests/property/database/ --ignore=tests/property/test_crud_operations_properties.py --ignore=tests/property/test_database_crud_properties.py || exit 1

        # Stage 3: Database tests + DB property tests (sequential)
        echo ""
        echo "=== Stage 3/3: Database Tests + DB Property Tests (sequential) ==="
        python -m pytest tests/property/database/ tests/property/test_crud_operations_properties.py tests/property/test_database_crud_properties.py tests/integration/ tests/e2e/ tests/security/ tests/stress/ tests/chaos/ tests/performance/ -v --no-cov --tb=short -p no:xdist || exit 1
    '
} &
PIDS[2]=$!
NAMES[2]="🧪 All 8 Test Types (1196 tests - hybrid parallel/sequential)"
OUTPUTS[2]="$TEMP_DIR/step_2.txt"

# ==============================================================================
# STEP 3: Type Checking (PARALLEL)
# ==============================================================================
{
    run_parallel_check 3 "Type Checking" \
        python -m mypy . --exclude 'tests/' --exclude '_archive/' --exclude 'venv/' --exclude '.venv/' --ignore-missing-imports
} &
PIDS[3]=$!
NAMES[3]="🔍 Type Checking (Mypy)"
OUTPUTS[3]="$TEMP_DIR/step_3.txt"

# ==============================================================================
# STEP 4: Security Scan (PARALLEL)
# ==============================================================================
{
    run_parallel_check 4 "Security Scan" \
        python -m ruff check --select S --ignore S101,S112,S607,S603 --exclude 'tests/' --exclude '_archive/' --exclude 'venv/' --quiet .
} &
PIDS[4]=$!
NAMES[4]="🔒 Security Scan (Ruff S-rules)"
OUTPUTS[4]="$TEMP_DIR/step_4.txt"

# ==============================================================================
# STEP 5: Warning Governance (PARALLEL - SLOWEST ~30s)
# ==============================================================================
{
    run_parallel_check 5 "Warning Governance" \
        python scripts/check_warning_debt.py
} &
PIDS[5]=$!
NAMES[5]="⚠️  Warning Governance"
OUTPUTS[5]="$TEMP_DIR/step_5.txt"

# ==============================================================================
# STEP 6: Code Quality (PARALLEL)
# ==============================================================================
{
    run_parallel_check 6 "Code Quality" \
        python scripts/validate_code_quality.py
} &
PIDS[6]=$!
NAMES[6]="📋 Code Quality (CODE_REVIEW_TEMPLATE)"
OUTPUTS[6]="$TEMP_DIR/step_6.txt"

# ==============================================================================
# STEP 7: Security Patterns (PARALLEL)
# ==============================================================================
{
    run_parallel_check 7 "Security Patterns" \
        python scripts/validate_security_patterns.py
} &
PIDS[7]=$!
NAMES[7]="🔒 Security Patterns (SECURITY_REVIEW_CHECKLIST)"
OUTPUTS[7]="$TEMP_DIR/step_7.txt"

# ==============================================================================
# STEP 8: SCD Type 2 Query Validation (PARALLEL) - NEW
# ==============================================================================
{
    run_parallel_check 8 "SCD Type 2 Queries" \
        python scripts/validate_scd_queries.py
} &
PIDS[8]=$!
NAMES[8]="📊 SCD Type 2 Queries (Pattern 2)"
OUTPUTS[8]="$TEMP_DIR/step_8.txt"

# ==============================================================================
# STEP 9: Property Test Coverage (PARALLEL) - NEW
# ==============================================================================
{
    run_parallel_check 9 "Property Tests" \
        python scripts/validate_property_tests.py
} &
PIDS[9]=$!
NAMES[9]="🔬 Property Tests (Pattern 10)"
OUTPUTS[9]="$TEMP_DIR/step_9.txt"

# ==============================================================================
# STEP 10: Test Fixture Validation (PARALLEL) - NEW
# ==============================================================================
{
    run_parallel_check 10 "Test Fixtures" \
        python scripts/validate_test_fixtures.py
} &
PIDS[10]=$!
NAMES[10]="🧪 Test Fixtures (Pattern 13)"
OUTPUTS[10]="$TEMP_DIR/step_10.txt"

# ==============================================================================
# STEP 11: Test Type Coverage Audit (PARALLEL) - V3.2 STRICT ENFORCEMENT
# ==============================================================================
# Phase 1.9 (Issue #165) REQUIRES --strict mode:
#   - ALL 11 modules must have ALL 8 test types
#   - NO exceptions without explicit approval
#   - This is blocking work that must be completed
#
# If this fails, FIX THE MISSING TEST TYPES - do not change to --summary
{
    run_parallel_check 11 "Test Type Coverage" \
        python scripts/audit_test_type_coverage.py --strict
} &
PIDS[11]=$!
NAMES[11]="📊 Test Type Coverage STRICT (TESTING_STRATEGY V3.2)"
OUTPUTS[11]="$TEMP_DIR/step_11.txt"

# ==============================================================================
# WAIT FOR ALL PARALLEL PROCESSES TO COMPLETE
# ==============================================================================

echo "⏳ Waiting for all checks to complete..."
echo ""

# Wait for all background processes
for step in 2 3 4 5 6 7 8 9 10 11; do
    wait ${PIDS[$step]}
done

# ==============================================================================
# CHECK EXIT CODES AND DISPLAY RESULTS
# ==============================================================================

FAILED_CHECKS=()
ALL_PASSED=true

for step in 2 3 4 5 6 7 8 9 10 11; do
    exit_code=$(cat "${OUTPUTS[$step]}.exit")

    if [ "$exit_code" -eq 0 ]; then
        echo "✅ [${step}/11] ${NAMES[$step]} - PASSED"
    else
        echo "❌ [${step}/11] ${NAMES[$step]} - FAILED"
        FAILED_CHECKS+=($step)
        ALL_PASSED=false
    fi
done

echo ""

# ==============================================================================
# REPORT FAILURES (IF ANY)
# ==============================================================================

if [ "$ALL_PASSED" = false ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ ${#FAILED_CHECKS[@]} check(s) failed!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    for step in "${FAILED_CHECKS[@]}"; do
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "❌ ${NAMES[$step]} - OUTPUT:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        cat "${OUTPUTS[$step]}"
        echo ""
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Fix failed checks above, then try pushing again."
    echo "To bypass (NOT RECOMMENDED): git push --no-verify"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Cleanup
    rm -rf "$TEMP_DIR"
    exit 1
fi

# ==============================================================================
# SUCCESS!
# ==============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All pre-push checks passed! Pushing to remote..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚡ Phase 1.9 pre-push validation complete!"
echo "   ALL 11 checks passed including ALL 8 test types (1196 tests)"
echo ""

# Cleanup
rm -rf "$TEMP_DIR"
