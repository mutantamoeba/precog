#!/usr/bin/env bash
#
# Align the test DB schema to a target branch's alembic head.
#
# Wraps the 6-step manual recovery dance for test-DB-branch-drift, which
# the pre-push parity hook (#867) rejects pushes for. Drift recurred 2x
# in session 83 alone — this script makes recovery one command.
#
# Behavior:
#   - Read target branch's alembic head (canonical alembic mechanism).
#   - Read current test DB version via precog.database.migration_check.
#   - Three cases:
#       MATCH:   no-op success.
#       BEHIND:  switch to target -> `alembic upgrade head` -> done.
#       AHEAD:   detect (or accept --source-branch) which branch has the
#                higher migrations -> switch there -> `alembic downgrade
#                <target_head>` -> switch back to target.
#   - Always restores the original working branch on exit (success,
#     failure, signal) via trap. Refuses to run with a dirty working tree.
#
# Usage:
#   bash scripts/align_test_db.sh <target-branch> [--source-branch <name>]
#   bash scripts/align_test_db.sh --help
#
# Options:
#   <target-branch>           The branch whose alembic head the test DB
#                             should be aligned to (required).
#   --source-branch <name>    For the AHEAD case: branch to check out for
#                             the downgrade (so the higher-numbered
#                             migration files are present on disk).
#                             Default: auto-detect; prompts if ambiguous.
#   --help, -h                Show this help text and exit 0.
#
# Example:
#   bash scripts/align_test_db.sh main
#   bash scripts/align_test_db.sh feature/foo --source-branch feature/bar
#
# Exit Codes:
#   0 - Test DB now aligned with target branch's alembic head
#   1 - Recovery failed (alembic error, dirty tree, etc.)
#   2 - Bad usage (missing args, unknown flag)
#
# Reference:
#   Issue:  https://github.com/mutantamoeba/precog/issues/1102
#   Epic:   https://github.com/mutantamoeba/precog/issues/1071
#   Hook:   scripts/check_test_db_migration_parity.py (#867)
#   Helper: src/precog/database/migration_check.py (#792)

set -euo pipefail

# ---- ANSI color codes ------------------------------------------------------
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---- Globals ---------------------------------------------------------------
ORIGINAL_BRANCH=""
TARGET_BRANCH=""
SOURCE_BRANCH=""

# ---- Helpers ---------------------------------------------------------------

print_help() {
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

err() {
    echo -e "${RED}ERROR:${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}WARN:${NC} $*" >&2
}

info() {
    echo -e "${BLUE}INFO:${NC} $*"
}

ok() {
    echo -e "${GREEN}OK:${NC} $*"
}

restore_branch() {
    # Trap handler: restore the working branch the user started on.
    # Runs on success, failure, and signals. Best-effort — if the
    # checkout itself fails, log loudly but don't recurse.
    if [[ -z "${ORIGINAL_BRANCH}" ]]; then
        return 0
    fi
    local current
    current="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
    if [[ "${current}" == "${ORIGINAL_BRANCH}" ]]; then
        return 0
    fi
    echo ""
    info "Restoring original branch: ${ORIGINAL_BRANCH}"
    if ! git checkout --quiet "${ORIGINAL_BRANCH}" 2>/dev/null; then
        err "Could not restore branch ${ORIGINAL_BRANCH}. You are currently on: ${current}"
        err "Run: git checkout ${ORIGINAL_BRANCH}"
    fi
}

# ---- Argument parsing ------------------------------------------------------

if [[ $# -eq 0 ]]; then
    err "Missing required argument: <target-branch>"
    echo ""
    echo "Usage: bash scripts/align_test_db.sh <target-branch> [--source-branch <name>]"
    echo "       bash scripts/align_test_db.sh --help"
    exit 2
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            print_help
            ;;
        --source-branch)
            if [[ $# -lt 2 ]]; then
                err "--source-branch requires a branch name argument"
                exit 2
            fi
            SOURCE_BRANCH="$2"
            shift 2
            ;;
        -*)
            err "Unknown option: $1"
            echo "Usage: bash scripts/align_test_db.sh <target-branch> [--source-branch <name>]"
            exit 2
            ;;
        *)
            if [[ -n "${TARGET_BRANCH}" ]]; then
                err "Unexpected positional argument: $1 (target branch already set to ${TARGET_BRANCH})"
                exit 2
            fi
            TARGET_BRANCH="$1"
            shift
            ;;
    esac
done

if [[ -z "${TARGET_BRANCH}" ]]; then
    err "Missing required argument: <target-branch>"
    exit 2
fi

# ---- Pre-flight checks -----------------------------------------------------

# Must be inside the precog repo (alembic.ini at known path).
ALEMBIC_DIR_REL="src/precog/database"
if [[ ! -f "${ALEMBIC_DIR_REL}/alembic.ini" ]]; then
    err "Not in precog repo root: ${ALEMBIC_DIR_REL}/alembic.ini not found."
    err "Run from the repo root (where you usually run pytest)."
    exit 1
fi

# Must be in a git repo.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    err "Not in a git working tree."
    exit 1
fi

# Save original branch for restoration.
ORIGINAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${ORIGINAL_BRANCH}" == "HEAD" ]]; then
    err "In detached HEAD state. Check out a branch before running this script."
    exit 1
fi

# Working tree must be clean — checkouts would otherwise lose changes.
if ! git diff --quiet || ! git diff --cached --quiet; then
    err "Working tree is dirty. Commit or stash changes before running this script."
    err ""
    err "  git status"
    err "  git stash --include-untracked   # if you want to keep changes for later"
    exit 1
fi

# Target branch must exist locally.
if ! git rev-parse --verify --quiet "${TARGET_BRANCH}" >/dev/null; then
    err "Target branch does not exist locally: ${TARGET_BRANCH}"
    err "Try: git fetch origin ${TARGET_BRANCH} && git checkout ${TARGET_BRANCH}"
    exit 1
fi

# Install trap NOW that ORIGINAL_BRANCH is set.
trap restore_branch EXIT INT TERM

# ---- Read versions ---------------------------------------------------------

info "Original branch: ${ORIGINAL_BRANCH}"
info "Target branch:   ${TARGET_BRANCH}"
echo ""

# Test DB version: use the canonical Python helper (Pattern 73 — same path
# the pre-push parity hook uses). PRECOG_ENV=test forces test-DB credentials.
# precog's structlog config writes INFO logs to stdout, so we wrap the
# answer in a sentinel-prefixed line and grep it out, ignoring any other
# output. Stderr is captured separately for actionable error messages.
info "Reading test DB version via precog.database.migration_check..."
PY_OUT_FILE="$(mktemp)"
PY_ERR_FILE="$(mktemp)"
if ! PRECOG_ENV=test python -c "
from precog.database.migration_check import check_migration_parity
s = check_migration_parity()
if s.error and s.fatal:
    raise SystemExit('FATAL: ' + s.error)
if s.error:
    raise SystemExit('SKIP: ' + s.error)
print('ALIGN_TEST_DB_VERSION=' + (s.db_version or ''))
" >"${PY_OUT_FILE}" 2>"${PY_ERR_FILE}"; then
    err "Could not read test DB version:"
    cat "${PY_ERR_FILE}" >&2
    cat "${PY_OUT_FILE}" >&2
    rm -f "${PY_OUT_FILE}" "${PY_ERR_FILE}"
    exit 1
fi
TEST_DB_VERSION="$(grep '^ALIGN_TEST_DB_VERSION=' "${PY_OUT_FILE}" | head -n 1 | sed 's/^ALIGN_TEST_DB_VERSION=//' | tr -d '[:space:]')"
rm -f "${PY_OUT_FILE}" "${PY_ERR_FILE}"

if [[ -z "${TEST_DB_VERSION}" ]]; then
    err "Test DB has no alembic_version row — DB may be uninitialized."
    err "Run: PRECOG_ENV=test python -m alembic -c ${ALEMBIC_DIR_REL}/alembic.ini upgrade head"
    exit 1
fi
info "Test DB version: ${TEST_DB_VERSION}"

# Target branch head: check out target, ask alembic, leave there for now
# (the upgrade case will run from there anyway; trap restores at exit).
info "Reading target branch alembic head..."
git checkout --quiet "${TARGET_BRANCH}"

TARGET_HEAD="$(
    cd "${ALEMBIC_DIR_REL}" && PRECOG_ENV=test python -m alembic heads 2>/dev/null \
        | awk '/\(head\)/ {print $1; exit}'
)"

if [[ -z "${TARGET_HEAD}" ]]; then
    err "Could not read alembic head for target branch ${TARGET_BRANCH}."
    exit 1
fi
info "Target branch alembic head: ${TARGET_HEAD}"
echo ""

# ---- Decide and act --------------------------------------------------------

if [[ "${TEST_DB_VERSION}" == "${TARGET_HEAD}" ]]; then
    ok "Test DB already at target head ${TARGET_HEAD}. Nothing to do."
    exit 0
fi

# Compare numerically when both are pure-numeric migration ids
# (precog convention: NNNN). Fall back to string compare otherwise — in
# that case we cannot decide AHEAD vs BEHIND deterministically, so refuse.
if [[ "${TEST_DB_VERSION}" =~ ^[0-9]+$ ]] && [[ "${TARGET_HEAD}" =~ ^[0-9]+$ ]]; then
    if (( 10#${TEST_DB_VERSION} < 10#${TARGET_HEAD} )); then
        DIRECTION="behind"
    else
        DIRECTION="ahead"
    fi
else
    err "Non-numeric migration id detected (db=${TEST_DB_VERSION}, head=${TARGET_HEAD})."
    err "This script assumes the precog NNNN convention. Investigate manually."
    exit 1
fi

# -- BEHIND case: just upgrade ----------------------------------------------
if [[ "${DIRECTION}" == "behind" ]]; then
    info "Test DB is BEHIND target by $((10#${TARGET_HEAD} - 10#${TEST_DB_VERSION})) migration(s)."
    info "Upgrading test DB on branch ${TARGET_BRANCH}..."
    echo ""

    # We're already on TARGET_BRANCH from the head-read step above.
    if ! (cd "${ALEMBIC_DIR_REL}" && PRECOG_ENV=test python -m alembic upgrade head); then
        err "alembic upgrade head failed on branch ${TARGET_BRANCH}."
        exit 1
    fi
    echo ""
    ok "Test DB upgraded to ${TARGET_HEAD}."
    exit 0
fi

# -- AHEAD case: need a branch with the higher migration files --------------
info "Test DB is AHEAD of target (db=${TEST_DB_VERSION}, target=${TARGET_HEAD})."
info "Need a branch whose migration files include revision ${TEST_DB_VERSION} so alembic can downgrade."
echo ""

# We must leave TARGET_BRANCH (which has only up to ${TARGET_HEAD}) and
# go to a branch where revision ${TEST_DB_VERSION}'s file actually exists.
if [[ -n "${SOURCE_BRANCH}" ]]; then
    info "Using user-specified --source-branch ${SOURCE_BRANCH}"
    if ! git rev-parse --verify --quiet "${SOURCE_BRANCH}" >/dev/null; then
        err "Source branch does not exist locally: ${SOURCE_BRANCH}"
        exit 1
    fi
    DOWNGRADE_BRANCH="${SOURCE_BRANCH}"
else
    # Auto-detect: find branches that contain the migration file for ${TEST_DB_VERSION}.
    # We look for files matching ${TEST_DB_VERSION}_*.py in the alembic versions dir.
    info "Auto-detecting branch containing migration file ${TEST_DB_VERSION}_*.py..."
    CANDIDATES_FILE="$(mktemp)"
    # shellcheck disable=SC2064
    trap "rm -f '${CANDIDATES_FILE}'; restore_branch" EXIT INT TERM

    # Search local branches.
    while IFS= read -r br; do
        br="${br## }"
        br="${br#\* }"
        # Skip detached-HEAD entries from `git branch` output.
        if [[ "${br}" == "(HEAD"* ]] || [[ -z "${br}" ]]; then
            continue
        fi
        # Does this branch have the file?
        if git ls-tree -r --name-only "${br}" -- \
            "${ALEMBIC_DIR_REL}/alembic/versions/${TEST_DB_VERSION}_"*.py 2>/dev/null \
            | grep -q .; then
            echo "${br}" >> "${CANDIDATES_FILE}"
        fi
    done < <(git branch --format='%(refname:short)')

    CANDIDATE_COUNT="$(wc -l < "${CANDIDATES_FILE}" | tr -d ' ')"
    if [[ "${CANDIDATE_COUNT}" -eq 0 ]]; then
        err "No local branch contains a migration file matching ${TEST_DB_VERSION}_*.py."
        err "The test DB version came from somewhere — perhaps a remote-only branch?"
        err "Pass --source-branch <name> after fetching/checking out the right branch."
        exit 1
    fi

    if [[ "${CANDIDATE_COUNT}" -gt 1 ]]; then
        err "Multiple branches contain migration ${TEST_DB_VERSION}_*.py:"
        sed 's/^/  - /' "${CANDIDATES_FILE}" >&2
        err ""
        err "Re-run with --source-branch <name> to disambiguate."
        exit 1
    fi

    DOWNGRADE_BRANCH="$(head -n 1 "${CANDIDATES_FILE}")"
    info "Auto-detected source branch: ${DOWNGRADE_BRANCH}"
fi
echo ""

# Switch to the source branch and downgrade to TARGET_HEAD.
info "Switching to ${DOWNGRADE_BRANCH} for downgrade..."
git checkout --quiet "${DOWNGRADE_BRANCH}"

info "Running: alembic downgrade ${TARGET_HEAD}"
echo ""
if ! (cd "${ALEMBIC_DIR_REL}" && PRECOG_ENV=test python -m alembic downgrade "${TARGET_HEAD}"); then
    err "alembic downgrade ${TARGET_HEAD} failed on branch ${DOWNGRADE_BRANCH}."
    err "Test DB may be in a partially-downgraded state — investigate manually."
    exit 1
fi
echo ""
info "Downgrade complete. Switching to target branch ${TARGET_BRANCH}..."
git checkout --quiet "${TARGET_BRANCH}"

# Verify final state matches. Same sentinel pattern as the initial read.
FINAL_OUT_FILE="$(mktemp)"
PRECOG_ENV=test python -c "
from precog.database.migration_check import check_migration_parity
s = check_migration_parity()
print('ALIGN_TEST_DB_VERSION=' + (s.db_version or ''))
" >"${FINAL_OUT_FILE}" 2>/dev/null || true
FINAL_VERSION="$(grep '^ALIGN_TEST_DB_VERSION=' "${FINAL_OUT_FILE}" | head -n 1 | sed 's/^ALIGN_TEST_DB_VERSION=//' | tr -d '[:space:]')"
rm -f "${FINAL_OUT_FILE}"
if [[ "${FINAL_VERSION}" != "${TARGET_HEAD}" ]]; then
    err "Post-downgrade verification failed: test DB at ${FINAL_VERSION}, expected ${TARGET_HEAD}."
    exit 1
fi

echo ""
ok "Test DB downgraded to ${TARGET_HEAD}. Now on branch ${TARGET_BRANCH}."
# Note: trap will run, but current branch == TARGET_BRANCH may equal
# ORIGINAL_BRANCH (common when user runs this from the target branch).
exit 0
