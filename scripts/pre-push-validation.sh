#!/bin/bash
# Pre-push hook - Full local gate (branch check + unit/integration/e2e + stress/chaos)
# CI handles: property, security, performance tests + doc validation
# Stress/chaos/race run HERE only (they hang on CI runners due to threading + 2 vCPUs)
#
# Runs:
#   0. Branch name verification
#   0.25. Stale bytecode cleanup
#   0.5. Fast paths (docs-only, test-only-unit, migration-only, config-only)
#   1+2+3. Test tiers IN PARALLEL (session 43):
#     - Unit tests (pytest-xdist, no DB)
#     - Integration + E2E tests (sequential, own testcontainer)
#     - Stress + Chaos + Race tests (sequential, own testcontainer)
#
# Parallelization safety (session 43 design):
#   Each test tier runs as a SEPARATE python -m pytest invocation, which means
#   each gets its own session-scoped testcontainer on a random port. Integration
#   uses `postgres_container` fixture with username=test_user; stress uses
#   `_stress_postgres_container_session` with username=stress_user. Running all
#   3 tiers in parallel spawns 3 independent Docker containers with zero
#   cross-tier DB contention. Historical contention from an earlier attempt
#   was from within-tier xdist (workers sharing a session container and racing
#   on tables) — that's why integration tests still use `-p no:xdist`.
#
# Logging: Each tier writes to its own log file; all are consolidated into
#          the main log file after completion. Console shows only summaries
#          and failures.
#
# Speed: ~8 minutes parallel (was ~14 min serial) — 47% faster
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
# LOGGING SETUP: per-tier log files, consolidated into main log after completion
# ==============================================================================
LOG_DIR=".pre-push-logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/pre-push-${TIMESTAMP}.log"
UNIT_LOG="$LOG_DIR/pre-push-${TIMESTAMP}-unit.log"
INT_LOG="$LOG_DIR/pre-push-${TIMESTAMP}-integration.log"
STRESS_LOG="$LOG_DIR/pre-push-${TIMESTAMP}-stress.log"

# Retention: remove logs older than 30 days
find "$LOG_DIR" -name "pre-push-*.log" -mtime +30 -delete 2>/dev/null || true
find "$LOG_DIR" -name "pre-push-*.json" -mtime +30 -delete 2>/dev/null || true

echo "Pre-push validation started at $(date)" > "$LOG_FILE"
echo "Branch: $(git rev-parse --abbrev-ref HEAD)" >> "$LOG_FILE"
echo "Commit: $(git rev-parse --short HEAD)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

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
# STEP 0.2: Test DB Migration Parity Check (#867)
# ==============================================================================
# A stale test DB can silently mask real test failures — S61 root cause,
# 8 files over months. Block the push if the test DB is behind alembic head.
# Graceful skip if the test DB is unreachable (contributors without a test DB
# are not blocked). Exit 2 = bug in migration_check itself (fail loudly so
# the developer sees the real error and fixes it).
python scripts/check_test_db_migration_parity.py
PARITY_EXIT=$?
if [[ $PARITY_EXIT -ne 0 ]]; then
    echo ""
    echo "Pre-push aborted by #867 test DB parity check (exit $PARITY_EXIT)."
    echo "Bypass (at your own risk): git push --no-verify"
    exit $PARITY_EXIT
fi

# ==============================================================================
# STEP 0.25: Clean Stale Bytecode (prevents ghost test discovery)
# ==============================================================================
find tests/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ==============================================================================
# STEP 0.5: Fast Path Detection
# ==============================================================================
# Extended from #616 (docs-only fast path) in session 43 to support three more
# categories of "safe to skip tiers" changes. Each fast path exits early OR
# narrows the tier set, skipping tiers that cannot be affected by the change.
#
# Priority order (most specific first):
#   1. Docs-only (#616): exits immediately, no test gate
#   2. Test-only-unit: only unit tier runs
#   3. Migration-only: only integration tier runs
#   4. Config-only: skip stress+chaos+race, run unit + integration
#   5. Default: all 3 tiers run in parallel
#
# Safety analysis per fast path is documented inline with each detection block.
#
# Override: SKIP_DOCS_FAST_PATH=1 git push  (forces full gate regardless)

# Get the list of files changed in this push using the same 3-strategy
# approach as the original docs fast path (#616).
CHANGED_FILES=""
if git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
    CHANGED_FILES=$(git diff --name-only @{u}..HEAD 2>/dev/null || true)
fi
if [[ -z "$CHANGED_FILES" ]]; then
    MERGE_BASE=$(git merge-base HEAD origin/main 2>/dev/null || true)
    if [[ -n "$MERGE_BASE" ]]; then
        CHANGED_FILES=$(git diff --name-only "$MERGE_BASE" HEAD 2>/dev/null || true)
    fi
fi
if [[ -z "$CHANGED_FILES" ]]; then
    CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || true)
fi

# Tier selection flags (default: run all 3)
RUN_UNIT=1
RUN_INT=1
RUN_STRESS=1
FAST_PATH_NAME=""

if [[ "${SKIP_DOCS_FAST_PATH:-0}" != "1" && -n "$CHANGED_FILES" ]]; then
    # -------------------------------------------------------------------------
    # Fast path 1: Docs-only (#616) — EXIT IMMEDIATELY
    # -------------------------------------------------------------------------
    # Strict extension/filename matching (directory prefix is irrelevant).
    # A .py file inside docs/ (e.g., a renamed module) MUST trigger the full
    # gate, even though its parent directory is "docs/".
    NON_DOCS=$(echo "$CHANGED_FILES" | grep -vE '(\.md$|\.txt$|\.rst$|^README$|^README\.[a-z]+$|^LICENSE$|^LICENSE\.[a-z]+$|^AUTHORS$|^CHANGELOG$|^CHANGELOG\.[a-z]+$)' | head -1 || true)
    if [[ -z "$NON_DOCS" ]]; then
        echo ""
        echo "Docs-only push detected (#616) — skipping test gate."
        echo ""
        echo "Changed files (all match docs patterns):"
        echo "$CHANGED_FILES" | sed 's/^/  /'
        echo ""
        echo "Pre-commit hooks already ran at commit time. Test gate adds no safety value here."
        echo "To force full gate: SKIP_DOCS_FAST_PATH=1 git push"
        echo ""
        END_TIME=$(date +%s)
        TOTAL_DURATION=$((END_TIME - START_TIME))
        echo "Pre-push fast path complete (${TOTAL_DURATION}s)."
        echo "" >> "$LOG_FILE"
        echo "DOCS-ONLY FAST PATH: PASSED (${TOTAL_DURATION}s)" >> "$LOG_FILE"
        exit 0
    fi

    # -------------------------------------------------------------------------
    # Fast path 2: Test-only-unit — only unit tier runs
    # -------------------------------------------------------------------------
    # If all changed files are under tests/unit/ (and NOT tests/conftest.py or
    # tests/fixtures/ which are shared across tiers), integration and stress
    # tiers cannot be affected. Run only the unit tier.
    #
    # Safety: unit tests are fully isolated (no DB), so a broken unit test
    # cannot contaminate integration or stress test state. Shared conftest
    # files (tests/conftest.py, tests/fixtures/*) are deliberately excluded
    # because they could affect all tiers.
    NOT_UNIT_ONLY=$(echo "$CHANGED_FILES" | grep -vE '^tests/unit/.*\.py$' | head -1 || true)
    if [[ -z "$NOT_UNIT_ONLY" ]]; then
        RUN_INT=0
        RUN_STRESS=0
        FAST_PATH_NAME="test-only-unit"
    else
        # ---------------------------------------------------------------------
        # Fast path 3: Migration-only — only integration tier runs
        # ---------------------------------------------------------------------
        # If all changed files are Alembic migration files or their
        # corresponding migration test files, only the integration tier is
        # relevant. Unit tests mock the DB and cannot see schema changes.
        # Stress/chaos/race tests use their own testcontainer with a
        # different container setup and don't exercise migration logic.
        #
        # Safety: a broken migration is caught by the integration tier's
        # testcontainer, which applies migrations from scratch. A migration
        # that drops a column referenced by a CRUD function would surface
        # as a CRUD integration test failure.
        NOT_MIGRATION=$(echo "$CHANGED_FILES" | grep -vE '^(src/precog/database/alembic/versions/.*\.py$|tests/integration/database/test_migration_.*\.py$)' | head -1 || true)
        if [[ -z "$NOT_MIGRATION" ]]; then
            RUN_UNIT=0
            RUN_STRESS=0
            FAST_PATH_NAME="migration-only"
        else
            # -----------------------------------------------------------------
            # Fast path 4: Config-only — skip stress+chaos+race
            # -----------------------------------------------------------------
            # If all changed files are YAML/TOML config files under
            # src/precog/config/, unit + integration are sufficient.
            # Stress/chaos/race test concurrency/failure modes, not config.
            #
            # DELIBERATELY EXCLUDES pyproject.toml and tool config files
            # (ruff.toml, etc.) at project root, because those can affect
            # dependency resolution, lint rules, test discovery, and pytest
            # markers — any of which could surface as stress-test regressions.
            # Only src/precog/config/*.{yaml,yml,toml} qualifies.
            NOT_CONFIG=$(echo "$CHANGED_FILES" | grep -vE '^src/precog/config/.*\.(ya?ml|toml)$' | head -1 || true)
            if [[ -z "$NOT_CONFIG" ]]; then
                RUN_STRESS=0
                FAST_PATH_NAME="config-only"
            fi
        fi
    fi
fi

if [[ -n "$FAST_PATH_NAME" ]]; then
    echo ""
    echo "Fast path: $FAST_PATH_NAME — narrowed tier selection"
    echo "  Unit tests:           $([ $RUN_UNIT -eq 1 ] && echo "RUN" || echo "SKIP")"
    echo "  Integration + E2E:    $([ $RUN_INT -eq 1 ] && echo "RUN" || echo "SKIP")"
    echo "  Stress + Chaos + Race: $([ $RUN_STRESS -eq 1 ] && echo "RUN" || echo "SKIP")"
    echo ""
    echo "  To force full gate:   SKIP_DOCS_FAST_PATH=1 git push"
    echo ""
fi

# ==============================================================================
# STEP 1+2+3: Run selected tiers IN PARALLEL
# ==============================================================================
# Each tier runs in a subshell that writes output to its own log file. After
# all tiers complete, we print per-tier summaries and consolidate logs.
#
# Subshell pattern: { start_time; pytest; exit_code; duration; exit $? } &
#   - Captures start time and duration inside the subshell
#   - Writes DURATION=N to the log file as the last line for later parsing
#   - The subshell's exit code propagates via wait $PID

echo "Running tests in parallel (per-tier logs in $LOG_DIR/pre-push-${TIMESTAMP}-*.log)..."
echo ""

UNIT_PID=""
INT_PID=""
STRESS_PID=""

if [[ $RUN_UNIT -eq 1 ]]; then
    {
        _start=$(date +%s)
        python -m pytest tests/unit/ --no-cov --tb=short -n auto -q > "$UNIT_LOG" 2>&1
        _exit=$?
        _end=$(date +%s)
        echo "" >> "$UNIT_LOG"
        echo "DURATION=$((_end - _start))" >> "$UNIT_LOG"
        exit $_exit
    } &
    UNIT_PID=$!
fi

if [[ $RUN_INT -eq 1 ]]; then
    {
        _start=$(date +%s)
        python -m pytest tests/integration/ tests/e2e/ --no-cov --tb=short -p no:xdist -q > "$INT_LOG" 2>&1
        _exit=$?
        _end=$(date +%s)
        echo "" >> "$INT_LOG"
        echo "DURATION=$((_end - _start))" >> "$INT_LOG"
        exit $_exit
    } &
    INT_PID=$!
fi

if [[ $RUN_STRESS -eq 1 ]]; then
    {
        _start=$(date +%s)
        python -m pytest tests/stress/ tests/chaos/ tests/race/ --no-cov --tb=short -q --timeout=120 --timeout-method=thread > "$STRESS_LOG" 2>&1
        _exit=$?
        _end=$(date +%s)
        echo "" >> "$STRESS_LOG"
        echo "DURATION=$((_end - _start))" >> "$STRESS_LOG"
        exit $_exit
    } &
    STRESS_PID=$!
fi

# Wait for all launched tiers
UNIT_EXIT=0
INT_EXIT=0
STRESS_EXIT=0

if [[ -n "$UNIT_PID" ]]; then
    wait "$UNIT_PID"
    UNIT_EXIT=$?
fi
if [[ -n "$INT_PID" ]]; then
    wait "$INT_PID"
    INT_EXIT=$?
fi
if [[ -n "$STRESS_PID" ]]; then
    wait "$STRESS_PID"
    STRESS_EXIT=$?
fi

# Print per-tier summaries (in a consistent order regardless of completion order)
print_tier_result() {
    local name="$1"
    local pid="$2"
    local exit_code="$3"
    local log_file="$4"

    if [[ -z "$pid" ]]; then
        echo "  $name: SKIPPED (fast path)"
        return
    fi

    local duration=""
    if [[ -f "$log_file" ]]; then
        duration=$(grep "^DURATION=" "$log_file" | tail -1 | cut -d= -f2)
    fi

    if [[ $exit_code -eq 0 ]]; then
        local summary=""
        if [[ -f "$log_file" ]]; then
            summary=$(grep -E "^=+ .+ =+$" "$log_file" | tail -1)
            [[ -z "$summary" ]] && summary=$(grep -E "passed" "$log_file" | tail -1)
        fi
        echo "  $name: PASSED (${duration}s) — $summary"
    else
        echo ""
        echo "  $name: FAILED (${duration}s)"
        echo ""
        if [[ -f "$log_file" ]]; then
            echo "  --- Failures from $name ---"
            grep -E "^(FAILED|ERROR|E |    |tests/)" "$log_file" | head -30 | sed 's/^/  /'
            grep -E "^=+ .+ =+$" "$log_file" | tail -1 | sed 's/^/  /'
            echo "  --- Full log: $log_file ---"
        fi
        echo ""
    fi
}

print_tier_result "Unit tests          " "$UNIT_PID" $UNIT_EXIT "$UNIT_LOG"
print_tier_result "Integration + E2E   " "$INT_PID" $INT_EXIT "$INT_LOG"
print_tier_result "Stress + Chaos + Race" "$STRESS_PID" $STRESS_EXIT "$STRESS_LOG"

# Consolidate per-tier logs into the main log file
{
    echo "" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    echo "PARALLEL TIER LOGS" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    for tier_log in "$UNIT_LOG" "$INT_LOG" "$STRESS_LOG"; do
        if [[ -f "$tier_log" ]]; then
            echo "" >> "$LOG_FILE"
            echo "--- $(basename "$tier_log") ---" >> "$LOG_FILE"
            cat "$tier_log" >> "$LOG_FILE"
        fi
    done
} 2>/dev/null || true

# Overall verdict: fail if any launched tier failed
if [[ $UNIT_EXIT -ne 0 || $INT_EXIT -ne 0 || $STRESS_EXIT -ne 0 ]]; then
    echo ""
    echo "One or more test tiers failed. See logs above."
    echo "Main log: $LOG_FILE"
    exit 1
fi

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))

echo ""
if [[ -n "$FAST_PATH_NAME" ]]; then
    echo "All pre-push checks passed! (${TOTAL_DURATION}s, fast path: $FAST_PATH_NAME)"
else
    echo "All pre-push checks passed! (${TOTAL_DURATION}s, all tiers in parallel)"
fi
echo "CI will run remaining tests (property, security, performance)."
echo "Full local suite: python -m pytest tests/ -q --no-cov"

echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "TOTAL: PASSED (${TOTAL_DURATION}s)" >> "$LOG_FILE"

exit 0
