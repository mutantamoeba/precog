# Session Workflow Guide

---
**Version:** 1.1
**Created:** 2025-11-15
**Last Updated:** 2025-11-29
**Purpose:** Comprehensive guide to session workflows, phase transitions, and task tracking
**Target Audience:** Claude Code AI assistant in all sessions
**Extracted From:** CLAUDE.md V1.17 Section 3 (following V1.16 extraction pattern)
**Status:** ✅ Current
**Changes in V1.1:**
- **Added Section 3: Pre-Planning Test Coverage Checklist (MANDATORY)** - Enforces TESTING_STRATEGY V3.2 8-test-type requirement before todo list creation
- **Root Cause:** Phase 2C planning failure - only 2/8 test types included in todo list
- **Solution:** Mandatory checklist requiring `audit_test_type_coverage.py` run + explicit 8-test-type verification
- **Renumbered sections 3-9 → 4-10** to accommodate new section

---

## Table of Contents

1. [Starting a New Session](#1-starting-a-new-session)
2. [Phase Start Protocol](#2-phase-start-protocol)
3. [Pre-Planning Test Coverage Checklist (MANDATORY)](#3-pre-planning-test-coverage-checklist-mandatory) ⭐ **NEW**
4. [During Development](#4-during-development)
5. [Git Safety Protocols](#5-git-safety-protocols)
6. [Recovering from Interrupted Sessions](#6-recovering-from-interrupted-sessions)
7. [Multi-Session Coordination](#7-multi-session-coordination)
8. [Ending a Session](#8-ending-a-session)
9. [Phase Transitions](#9-phase-transitions)
10. [Deferred Task Tracking (Dual-System)](#10-deferred-task-tracking-dual-system)

---

## 1. Starting a New Session

**⏱️ Time Required:** 5 minutes

### Step 1: Read Project Context (2 minutes)

**Read these two files in order:**
1. **CLAUDE.md** - Project overview, critical patterns, current status
2. **SESSION_HANDOFF.md** - Recent work, immediate next steps

**Why These Two?**
- CLAUDE.md provides permanent project context (architecture, patterns, workflows)
- SESSION_HANDOFF.md provides ephemeral session context (what just happened, what's next)
- Together they give complete picture in <5 minutes

### Step 2: Git Status Check (1 minute) - MANDATORY

**⚠️ BEFORE doing ANY work, run these safety checks:**

```bash
# 1. Check current branch
BRANCH=$(git branch --show-current)
echo "Current branch: $BRANCH"

# 2. Check for uncommitted changes
git status

# 3. Check for unpushed commits on current branch
git log origin/$BRANCH..HEAD --oneline 2>/dev/null || echo "Branch not yet on remote"

# 4. Check for unpushed commits on ALL local branches
echo "Branches with unpushed commits:"
git branch -vv | grep ahead || echo "All branches up-to-date"

# 5. Check for unmerged work on remote feature branches
echo "Remote feature branches (may have unmerged work):"
git branch -r | grep -E "origin/(feature|bugfix|refactor|docs|test)/" || echo "No remote feature branches"
```

**What to look for:**
- ✅ **Clean working tree** - "nothing to commit, working tree clean"
- ✅ **On feature branch** - NOT on main (branch protection blocks direct pushes)
- ⚠️ **Uncommitted changes** - Review with `git diff`, complete and commit before starting new work
- ⚠️ **Unpushed commits** - Push to origin before starting new work
- ⚠️ **Remote feature branches** - May have unmerged work from previous sessions (check with `gh pr list`)

**If uncommitted/unpushed work found:**
1. Review changes: `git diff` (unstaged) and `git diff --cached` (staged)
2. Commit: `git commit -m "Description"`
3. Push: `git push origin $(git branch --show-current)`
4. Create PR if needed: `gh pr create --title "..." --body "..."`

### Step 3: Check Current Phase (1 minute)

**Verify:**
- [ ] What phase are we in? (Check DEVELOPMENT_PHASES_V1.4.md if unclear)
- [ ] What's blocking vs. nice-to-have?
- [ ] Any phase dependencies that must be met?

### Step 4: Check Phase Prerequisites (1 minute) - MANDATORY

**⚠️ BEFORE CONTINUING ANY PHASE WORK:** Check DEVELOPMENT_PHASES for current phase's Dependencies section

- [ ] Verify ALL "Requires Phase X: 100% complete" dependencies are met
- [ ] Check that previous phase is marked ✅ Complete in DEVELOPMENT_PHASES
- [ ] **If dependencies NOT met:** STOP and complete prerequisite phase first

**⚠️ IF STARTING NEW PHASE:** Complete "Before Starting This Phase - TEST PLANNING CHECKLIST" from DEVELOPMENT_PHASES before writing any production code

**⚠️ IF RESUMING PARTIALLY-COMPLETE PHASE:**
- [ ] Verify test planning checklist was completed
- [ ] If NOT completed: Complete it now before continuing any work
- [ ] If partially done: Update checklist for remaining work and document what testing exists for completed work
- [ ] **Critical:** Don't skip this - partially-complete phases are where test gaps hide!

**Example - Phase 1:**
```bash
# Phase 1 Dependencies: Requires Phase 0.7: 100% complete
# Check: Is Phase 0.7 marked ✅ Complete in DEVELOPMENT_PHASES?
# If NO → Must complete Phase 0.7 before starting Phase 1
# If YES → Can proceed with Phase 1 test planning checklist
```

### Step 5: Create Todo List (1 minute)

```python
# Use TodoWrite tool to track progress
TodoWrite([
    {"content": "Implement Kalshi API auth", "status": "in_progress", "activeForm": "Implementing Kalshi API auth"},
    {"content": "Add rate limiting", "status": "pending", "activeForm": "Adding rate limiting"},
    {"content": "Write API tests", "status": "pending", "activeForm": "Writing API tests"}
])
```

**Best Practices:**
- Create specific, actionable items
- Mark exactly ONE task as `in_progress` at a time
- Update status immediately upon completion
- Break complex tasks into smaller todos

---

## 2. Phase Start Protocol

**⏱️ Time Required:** 15-20 minutes

**When to use:** At the START of every new phase (not at resume of existing phase)

### The Problem: Task Blindness

Tasks get overlooked because they're scattered across multiple documents:
- Deferred tasks in `docs/utility/PHASE_*_DEFERRED_TASKS_V1.0.md`
- Phase checklist in `DEVELOPMENT_PHASES_V1.4.md`
- Requirements in `MASTER_REQUIREMENTS_V2.17.md`
- ADRs in `ARCHITECTURE_DECISIONS_V2.15.md`

### 3-Step Protocol (MANDATORY)

#### Step 1: Check Deferred Tasks (5 min)

```bash
# Find all deferred task documents
find docs/utility -name "PHASE_*_DEFERRED_TASKS*.md"

# Check GitHub issues for deferred tasks
gh issue list --label "deferred-task,phase-1.5"
```

**Create checklist from BOTH sources (documentation + GitHub):**

```markdown
## Phase 1 Deferred Tasks (from Phase 0.7)
- [ ] DEF-001: Pre-commit hooks setup (2 hours, 🟡 High) - Issue #45
- [ ] DEF-002: Pre-push hooks setup (1 hour, 🟡 High) - Issue #46
- [ ] DEF-003: Branch protection rules (30 min, 🟢 Medium) - Issue #47
- [ ] DEF-004: Line ending edge cases (1 hour, 🟢 Medium) - Issue #48
- [ ] DEF-008: Database schema validation script (3-4 hours, 🟡 High) - Issue #52
```

**Why dual sources?**
- **Documentation:** Provides context, rationale, implementation details
- **GitHub Issues:** Provides visibility, persistence, filtering capability
- **Together:** Ensures tasks aren't forgotten

#### Step 2: Check Phase Prerequisites (5 min)

Open `DEVELOPMENT_PHASES_V1.4.md`, find current phase section.

**Check:**
- [ ] **Dependencies met?** (e.g., "Requires Phase 0.7: 100% complete ✅")
- [ ] **Test planning checklist exists?** ("Before Starting This Phase - TEST PLANNING CHECKLIST")
- [ ] **Tasks clearly listed?** (numbered task list in phase section)
- [ ] **Coverage targets exist for ALL deliverables?** (Extract deliverables → Verify each has explicit coverage target)

**Coverage target validation:**
```bash
# Example validation:
# 1. List deliverables from DEVELOPMENT_PHASES Phase N task list
# 2. Check "Critical Module Coverage Targets" section has target for EACH
# 3. If missing → Add coverage target BEFORE starting implementation
#
# Common tiers:
# - Infrastructure (logger, config, connection): ≥80%
# - Business logic (CRUD, trading, position): ≥85%
# - Critical path (API auth, execution, risk): ≥90%
```

**If test planning checklist exists:**
```markdown
## Phase 1 Test Planning Checklist (MANDATORY - BEFORE CODE)
- [ ] Requirements analysis (15 min)
- [ ] Test categories needed (10 min)
- [ ] Test infrastructure updates (30 min)
- [ ] Critical test scenarios (20 min)
- [ ] Performance baselines (10 min)
- [ ] Security test scenarios (10 min)
- [ ] Edge cases to test (15 min)
- [ ] Success criteria (10 min)
```

**STOP:** Do NOT write production code until test planning complete!

#### Step 3: Create Master Todo List (10 min)

Combine Steps 1 and 2 into ONE master todo list using TodoWrite:

```python
TodoWrite([
    # Deferred tasks first (usually infrastructure)
    {"content": "DEF-001: Install pre-commit hooks (2h)", "status": "pending", "activeForm": "Installing pre-commit hooks"},
    {"content": "DEF-002: Install pre-push hooks (1h)", "status": "pending", "activeForm": "Installing pre-push hooks"},

    # Test planning checklist second (MANDATORY before code)
    {"content": "Complete Phase 1 test planning checklist (2h)", "status": "pending", "activeForm": "Completing Phase 1 test planning checklist"},

    # Phase tasks third (implementation)
    {"content": "Implement Kalshi API client (8h)", "status": "pending", "activeForm": "Implementing Kalshi API client"},
    {"content": "Implement CLI commands (6h)", "status": "pending", "activeForm": "Implementing CLI commands"},
    # ... more tasks
])
```

### Phase 1 Example: What We Missed

**Deferred tasks for Phase 1 (from Phase 0.7):**
- DEF-001: Pre-commit hooks setup (🟡 High priority, target Phase 0.8/1)
- DEF-002: Pre-push hooks setup (🟡 High priority)
- DEF-008: Database schema validation script (🟡 High priority, 3-4 hours)

**Test planning checklist (from DEVELOPMENT_PHASES lines 442-518):**
- [ ] Requirements analysis
- [ ] Test infrastructure updates (API fixtures, CLI factories)
- [ ] Critical test scenarios
- [ ] Performance baselines
- [ ] Security test scenarios
- [ ] Edge cases
- [ ] Success criteria

**We DID:** Implemented Kalshi API client, CLI commands
**We MISSED:** Deferred tasks, test planning checklist

### Prevention: Phase Task Visibility

Add this to the top of `SESSION_HANDOFF.md`:

```markdown
## 🔍 Phase Checklist Status

**Current Phase:** Phase 1
**Deferred Tasks Completed:** 0/5 (DEF-001, DEF-002, DEF-003, DEF-004, DEF-008)
**Test Planning Checklist:** ⚠️ NOT STARTED (MANDATORY BEFORE CODE!)
**Phase Tasks Completed:** 2/6 (API client ✅, CLI ✅, Config loader pending)
```

This makes task status **visible at every session start**.

---

## 3. Pre-Planning Test Coverage Checklist (MANDATORY)

**⏱️ Time Required:** 5 minutes

**When to use:** BEFORE creating any todo list for phase work, feature implementation, or CRUD operations.

### The Problem: Incomplete Test Planning

**Root Cause (Phase 2C, 2025-11-29):**
- Todo list created with only 2/8 test types (unit + integration)
- Missing: property, e2e, stress, race, performance, chaos tests
- TESTING_STRATEGY V3.2 requires ALL 8 test types for ALL modules
- **Result:** Would have created test coverage gaps requiring rework

**Why This Happens:**
- Planning focuses on implementation, testing becomes afterthought
- Easy to forget test types when not explicitly checked
- No automated enforcement at planning stage (only at pre-push/CI)

### The Solution: Mandatory Pre-Planning Checklist

**⚠️ BEFORE creating any todo list, complete this checklist:**

#### Step 1: Run Test Type Audit (1 minute)

```bash
# Check current test type coverage gaps
python scripts/audit_test_type_coverage.py --summary
```

**Expected Output:**
```
======================================================================
TEST TYPE COVERAGE AUDIT SUMMARY
======================================================================

Modules analyzed: 11
Passing: 0
Failing: 11
```

**What to look for:**
- Which modules are missing which test types
- Current baseline to compare against after implementation

#### Step 2: Review TESTING_STRATEGY Requirements (2 minutes)

**TESTING_STRATEGY V3.2 requires ALL 8 test types for ALL tiers:**

| Test Type | Marker | Purpose |
|-----------|--------|---------|
| **Unit** | `@pytest.mark.unit` | Isolated function logic |
| **Property** | `@pytest.mark.property` | Hypothesis invariants (100+ cases) |
| **Integration** | `@pytest.mark.integration` | REAL database, no mocks |
| **E2E** | `@pytest.mark.e2e` | Complete workflows |
| **Stress** | `@pytest.mark.stress` | Connection pool, rate limits |
| **Race** | `@pytest.mark.race` | Concurrent operations |
| **Performance** | `@pytest.mark.performance` | Latency benchmarks |
| **Chaos** | `@pytest.mark.chaos` | Failure recovery |

**Reference:** `docs/foundation/TESTING_STRATEGY_V3.3.md`

#### Step 3: Verify Todo Includes All 8 Test Types (2 minutes)

**Before finalizing your todo list, verify it includes:**

- [ ] Unit tests (`@pytest.mark.unit`) - isolated logic
- [ ] Property tests (`@pytest.mark.property`) - Hypothesis invariants
- [ ] Integration tests (`@pytest.mark.integration`) - real DB, no mocks
- [ ] E2E tests (`@pytest.mark.e2e`) - complete workflows
- [ ] Stress tests (`@pytest.mark.stress`) - load testing
- [ ] Race tests (`@pytest.mark.race`) - concurrency
- [ ] Performance tests (`@pytest.mark.performance`) - benchmarks
- [ ] Chaos tests (`@pytest.mark.chaos`) - failure recovery

**Example: Correct Todo List for CRUD Implementation**

```python
TodoWrite([
    # Implementation
    {"content": "Implement venues CRUD", "status": "pending", ...},
    {"content": "Implement game_states CRUD (SCD Type 2)", "status": "pending", ...},

    # ALL 8 Test Types (MANDATORY)
    {"content": "Write UNIT tests (pytest.mark.unit)", "status": "pending", ...},
    {"content": "Write PROPERTY tests (Hypothesis)", "status": "pending", ...},
    {"content": "Write INTEGRATION tests (real DB)", "status": "pending", ...},
    {"content": "Write E2E tests (complete workflows)", "status": "pending", ...},
    {"content": "Write STRESS tests (load testing)", "status": "pending", ...},
    {"content": "Write RACE tests (concurrency)", "status": "pending", ...},
    {"content": "Write PERFORMANCE tests (benchmarks)", "status": "pending", ...},
    {"content": "Write CHAOS tests (failure recovery)", "status": "pending", ...},

    # Validation
    {"content": "Run audit_test_type_coverage.py --strict", "status": "pending", ...},
])
```

### Defense in Depth

This checklist is the **first layer** of test coverage enforcement:

| Layer | When | Tool | Action |
|-------|------|------|--------|
| **1. Pre-Planning** | Before todo list | This checklist | Ensures 8 test types planned |
| **2. Pre-Push** | On `git push` | `audit_test_type_coverage.py` | Warns about missing types |
| **3. CI/CD** | On PR | `test-type-coverage` job | Blocks merge if types missing |

**Key Insight:** Catching gaps at planning stage saves hours of rework vs. catching at CI stage.

### Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│ PRE-PLANNING CHECKLIST (before any todo list creation)     │
├─────────────────────────────────────────────────────────────┤
│ □ Run: python scripts/audit_test_type_coverage.py --summary│
│ □ Review: TESTING_STRATEGY_V3.3.md 8-test-type requirement │
│ □ Verify todo includes ALL 8 test types:                   │
│   □ unit    □ property    □ integration   □ e2e            │
│   □ stress  □ race        □ performance   □ chaos          │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. During Development

### Track Progress Continuously

- Update todo status frequently (mark completed immediately)
- Keep only ONE task as `in_progress` at a time
- Break complex tasks into smaller todos
- Use TodoWrite tool after major milestones

### Before Committing Code

See **Section 4: Git Safety Protocols** for complete pre-commit checklist.

**Quick checklist:**
- [ ] All tests passing
- [ ] Security scan clean
- [ ] Pre-commit hooks will pass (or run manually)
- [ ] No .env file staged

---

## 5. Git Safety Protocols

### Pre-Commit Hooks (Automatic)

Pre-commit hooks are installed and run automatically on `git commit`. They will:
- **Auto-fix** formatting, line endings, trailing whitespace
- **Block commit** if linting, type checking, or security issues found
- **Fast feedback** (~2-5 seconds)

```bash
# Hooks run automatically on commit (no action needed)
git add .
git commit -m "message"
# → Hooks run automatically: Ruff, Mypy, security scan, formatting

# Manual testing (optional, but recommended for large changes)
python -m pre_commit run --all-files  # Run all hooks manually

# Bypass hooks (EMERGENCY ONLY - NOT RECOMMENDED)
git commit --no-verify
```

**What the hooks check:**
1. ✅ Ruff linter (code quality)
2. ✅ Ruff formatter (auto-fix formatting)
3. ✅ Mypy type checking
4. ✅ Security scan (hardcoded credentials)
5. ✅ **Code review basics** (REQ-XXX-NNN traceability - WARNING ONLY)
6. ✅ **Decimal precision check** (Pattern 1 enforcement - BLOCKS float usage in financial code)
7. ✅ Trailing whitespace (auto-fix)
8. ✅ End-of-file newlines (auto-fix)
9. ✅ Mixed line endings (auto-fix CRLF→LF)
10. ✅ Large files check (>1MB)
11. ✅ Merge conflict markers
12. ✅ YAML/JSON syntax validation
13. ✅ Python AST validation
14. ✅ Debug statements (pdb, breakpoint)

### Pre-Push Hooks (Automatic - Parallelized Phase 1.5)

Pre-push hooks are installed and run automatically on `git push`. They provide a **second layer of defense**:
- **All pre-commit checks** (runs again on entire codebase)
- **Unit tests** (fast tests only - config_loader, logger)
- **Full type checking** (entire codebase, not just changed files)
- **Deep security scan** (Ruff security rules)
- **Parallelized for speed** (~30-40 seconds vs. sequential 103s)

```bash
# Hooks run automatically on push (no action needed)
# ⚠️ CRITICAL: NEVER push to main! Use feature branches.
git push origin feature/my-feature
# → Pre-push hooks run (7 validation steps, ~30-40s PARALLELIZED)
# → Step 0/7: Branch name convention check (blocks push to main)
# → Step 1/7: Quick validation (Ruff + docs)
# → Steps 2-7/7: PARALLEL execution (tests, types, security, warnings, quality, patterns)

# Bypass hooks (EMERGENCY ONLY - NOT RECOMMENDED)
git push --no-verify
```

**What the pre-push hooks check (Steps 2-7 run in PARALLEL):**
1. 🌿 **Branch name convention** - Verifies feature/, bugfix/, refactor/, docs/, test/ naming
2. 📋 **Quick validation** - validate_quick.sh (Ruff, docs, ~3 sec)
3. 🧪 **Unit tests** (PARALLEL) - pytest test_config_loader.py test_logger.py (~10 sec)
4. 🔍 **Type checking** (PARALLEL) - mypy on entire codebase (~20 sec)
5. 🔒 **Security scan** (PARALLEL) - Ruff security rules (--select S, ~10 sec)
6. ⚠️  **Warning governance** (PARALLEL) - check_warning_debt.py (multi-source baseline, ~30 sec - SLOWEST)
7. 📋 **Code quality validation** (PARALLEL) - validate_code_quality.py (≥80% coverage, REQ test coverage, ~20 sec)
8. 🔒 **Security pattern validation** (PARALLEL) - validate_security_patterns.py (API auth, hardcoded secrets, ~10 sec)

**Why parallelization?**
- **Sequential (old):** Steps run one after another = 103 seconds total
- **Parallel (new):** Steps 2-7 run simultaneously = ~30-40 seconds total (limited by slowest check)
- **Performance gain:** 68% faster (saves ~70 seconds per push)

**How it works:**
- Steps 0-1 run sequentially (safety checks + quick validation)
- Steps 2-7 run in parallel using bash background processes
- All output captured to temp files
- Results reported after all checks complete
- If any check fails, full output displayed for debugging

### Before Pushing (CRITICAL - 2 minutes)

**⚠️ Run this checklist BEFORE `git push` to prevent common mistakes:**

```bash
# Safety Check Script - Run before EVERY push
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 Pre-Push Safety Checklist"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Verify NOT on main branch
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ]; then
    echo "❌ ERROR: On main branch! Create feature branch first."
    echo "  git checkout -b feature/your-feature-name"
    exit 1
else
    echo "✅ On branch: $BRANCH"
fi

# 2. Verify all changes committed
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  WARNING: Uncommitted changes detected!"
    echo ""
    git status --short
    echo ""
    echo "Commit changes before pushing:"
    echo "  git add ."
    echo "  git commit -m \"Description\""
    exit 1
else
    echo "✅ All changes committed"
fi

# 3. Verify tests pass (quick check)
echo "🧪 Running fast tests..."
if python -m pytest tests/ -v --tb=short -q 2>&1 | tail -10; then
    echo "✅ Tests passing"
else
    echo "❌ Tests failing - fix before pushing"
    exit 1
fi

# 4. Ready to push
echo ""
echo "✅ All safety checks passed!"
echo "Ready to push to origin/$BRANCH"
echo ""
echo "Next steps:"
echo "  git push origin $BRANCH"
echo "  gh pr create --title \"...\" --body \"...\""
```

**Quick version (if you're confident):**

```bash
# Quick 3-step check
git branch --show-current | grep -v "^main$" && \
git diff-index --quiet HEAD -- && \
python -m pytest tests/ -v --tb=short -q && \
git push origin $(git branch --show-current)
```

**Common mistakes this prevents:**
- ❌ Attempting to push to main (branch protection blocks it, but fails late)
- ❌ Forgetting uncommitted changes (creates confusion later)
- ❌ Pushing broken tests (fails CI, wastes time)

### Branch Protection & Pull Request Workflow (GitHub)

The `main` branch is protected and **cannot be pushed to directly**. All changes must go through pull requests (PRs) with CI checks passing.

**Branch Protection Rules (Configured):**
- ✅ **Require pull requests** - Direct pushes to `main` blocked
- ✅ **Require CI to pass** - 6 status checks must succeed
- ✅ **Require up-to-date branches** - Must merge latest `main` before merging PR
- ✅ **Require conversation resolution** - All review comments must be resolved
- ✅ **No force pushes** - Prevents history rewriting
- ✅ **No deletions** - Prevents accidental branch deletion
- ✅ **Applies to administrators** - Rules enforce for everyone

**Pull Request Workflow:**

```bash
# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Make changes and commit (pre-commit hooks run)
git add .
git commit -m "Implement feature X"

# 3. Push to feature branch (pre-push hooks run - PARALLELIZED ~30-40s)
git push origin feature/my-feature

# 4. Create PR via GitHub CLI or web UI
gh pr create --title "Add feature X" --body "Description of changes"

# 5. Wait for CI checks to pass (2-5 minutes)
#    - All 6 status checks must succeed
#    - Fix any failures and push updates
#    - CI re-runs automatically on new commits

# 6. Merge PR (once CI passes)
gh pr merge --squash  # Squash merge (recommended)
# OR: Merge via GitHub web UI

# 7. Delete feature branch (cleanup)
gh pr close --delete-branch
```

**PR Best Practices:**
- **Small, focused PRs** - Easier to review, faster to merge
- **Descriptive titles** - Clearly state what the PR does
- **Link to issues/requirements** - Reference REQ-XXX, ADR-XXX, or DEF-XXX IDs
- **Test locally first** - Pre-push hooks catch most issues before CI
- **Watch CI results** - Fix failures quickly

**If CI fails:**
```bash
# View CI logs
gh pr checks

# Fix issues locally
# ... make fixes ...

# Commit and push (CI re-runs automatically)
git commit -am "Fix CI failures"
git push
```

---

## 6. Recovering from Interrupted Sessions

**⏱️ Time Required:** 5 minutes

**When to use:** Session interruption due to context limit, crash, network issue, or other disruption during active development work.

### Step 1: Check Git Status (1 min)

```bash
# Identify uncommitted changes and current branch
git status
git branch --show-current
```

**What to look for:**
- Uncommitted changes (modified, staged, untracked files)
- Current branch (feature/, bugfix/, etc.)
- Untracked files that should be committed

### Step 2: Review Recent Work (2 min)

```bash
# Check recent commits to understand what was completed
git log --oneline -10

# Check if PR exists for current branch
gh pr list --head $(git branch --show-current)
```

**What to verify:**
- Last commit message indicates completed work
- Understand what was in progress vs. completed
- Check if PR already exists (avoid creating duplicates)

### Step 3: Validate Tests Still Pass (1 min)

```bash
# Quick test validation to ensure recovered state is clean
python -m pytest tests/ -v --tb=short
```

**Why:** Interrupted sessions may have left code in partially-working state. Verify tests pass before continuing.

### Step 4: Resume Normal Workflow (1 min)

Based on git status findings:

**If uncommitted changes exist:**
1. Review changes: `git diff` (unstaged) and `git diff --cached` (staged)
2. Complete the work or commit as-is
3. Follow normal "During Development" workflow from this point

**If no uncommitted changes:**
1. Check SESSION_HANDOFF.md for next priorities
2. Create new todo list with TodoWrite
3. Begin next task

**If PR exists but not merged:**
1. Check CI status: `gh pr view <PR#> --json statusCheckRollup`
2. If CI passing: Merge PR
3. If CI failing: Fix issues and push updates
4. After merge: `git checkout main && git pull`

### Common Recovery Scenarios

| Scenario | Git Status | Action |
|----------|------------|--------|
| **Interrupted during coding** | Modified files, no commit | Review changes, complete work, commit |
| **Interrupted after commit** | Clean working tree | Check if pushed; if not, push now |
| **Interrupted during PR** | Clean, but PR exists | Check CI status, merge if passing |
| **Interrupted after merge** | On feature branch | Switch to main, pull latest |

### Example Recovery

```bash
# Scenario: Session interrupted while committing test updates
$ git status
# On branch feature/integration-tests
# Changes not staged for commit:
#   modified: pytest.ini
#   modified: tests/fixtures/api_responses.py
# Untracked files:
#   tests/integration/api_connectors/__init__.py

# Step 1: Review changes
$ git diff pytest.ini  # Verify changes are intentional

# Step 2: Stage and commit
$ git add pytest.ini tests/fixtures/api_responses.py tests/integration/api_connectors/__init__.py
$ git commit -m "Add api marker and fix test expectations"

# Step 3: Check for existing PR
$ gh pr list --head feature/integration-tests
# PR #12 exists

# Step 4: Push and update PR
$ git push origin feature/integration-tests
$ gh pr edit 12 --body "Updated description"

# Step 5: Check CI and merge
$ gh pr view 12 --json statusCheckRollup
# All checks passing → merge
$ gh pr merge 12 --squash --delete-branch
```

**Reference:** This pattern was successfully used to recover from context limit interruption on 2025-11-09 during Phase 1.5 integration test session.

---

## 7. Multi-Session Coordination

**⏱️ Time Required:** 10 minutes (initial setup), ongoing awareness

**When to use:** Multiple Claude Code sessions working on the same repository simultaneously (e.g., one session on CLI features, another on documentation).

### The Problem

Multi-session work creates conflicts when both sessions modify the same files (especially foundation docs like MASTER_REQUIREMENTS, ARCHITECTURE_DECISIONS) or push to main without coordination.

### Prevention Strategy (7 Steps)

#### Step 1: Session-Specific Branch Naming (MANDATORY)

Each session MUST work on clearly-named feature branches that indicate the session's focus:

```bash
# Session A (working on CLI features):
git checkout -b feature/cli-database-integration-sessionA

# Session B (working on observability docs):
git checkout -b docs/codecov-sentry-integration-sessionB

# Session C (working on test infrastructure):
git checkout -b test/property-based-testing-sessionC
```

**Why:** Makes it immediately obvious which branch belongs to which session, preventing accidental pushes to wrong branches.

#### Step 2: Check for Active Sessions Before Starting

```bash
# 1. Check for active feature branches on remote
git fetch
git branch -r | grep -E "origin/(feature|bugfix|refactor|docs|test)/"

# 2. Check for open PRs
gh pr list

# 3. Check for uncommitted/staged changes (might be from another session)
git status
```

**If you find active sessions:**
- Note which branch they're working on
- Check which files they've modified: `git diff origin/main...origin/<their-branch> --name-only`
- **Avoid modifying the same files** until their PR is merged

#### Step 3: Foundation Document Coordination (CRITICAL)

**Foundation docs** (MASTER_REQUIREMENTS, ARCHITECTURE_DECISIONS, DEVELOPMENT_PHASES, MASTER_INDEX) are high-conflict files.

**Rule:** Only ONE session should update foundation docs at a time.

**Protocol:**
1. **Before modifying foundation docs:**
   - Check if other sessions have open PRs: `gh pr list`
   - If yes: Wait for their PR to merge OR coordinate with user
   - If no: Proceed, but create PR quickly

2. **If you discover another session's uncommitted changes to foundation docs:**
   - Use `git stash` to save them: `git stash save "Foundation docs from other session"`
   - DO NOT use `git reset --hard` (destroys their work!)
   - Wait for other session to commit and create PR
   - After their PR merges: `git pull` and re-apply your stash if needed

#### Step 4: Communication via Git

**Leave breadcrumbs for other sessions:**

```bash
# If working on long-running feature, push early and often:
git push origin feature/my-feature-sessionA

# Create draft PR to signal work in progress:
gh pr create --draft --title "[WIP] Feature X" --body "Session A working on this"

# When pausing work, commit with clear message:
git commit -m "WIP: Half-done implementation (Session A pausing, will resume)"
```

#### Step 5: Conflict Resolution When Multiple Sessions Commit

**Scenario:** Session A commits `MASTER_REQUIREMENTS V2.13 → V2.14` (adds REQ-X), Session B commits `MASTER_REQUIREMENTS V2.13 → V2.14` (adds REQ-Y).

**Problem:** Both incremented to V2.14, but with different content!

**Solution:**
1. First session to merge wins (their V2.14 goes to main)
2. Second session must:
   - Pull latest: `git pull origin main`
   - Resolve conflict: Change their version to V2.15
   - Merge both changes: REQ-X (from first session) + REQ-Y (from second session)
   - Update version header: V2.14 → V2.15
   - Push again

#### Step 6: What NOT To Do (Common Mistakes)

❌ **NEVER push directly to main** - Always use feature branches + PRs
❌ **NEVER use `git reset --hard`** when other sessions are active - Use `git stash` instead
❌ **NEVER assume you're the only session** - Always check `git status` and `gh pr list` first
❌ **NEVER modify foundation docs without checking for conflicts** - Check open PRs first
❌ **NEVER bypass pre-push hooks with `--no-verify`** - Hooks prevent multi-session conflicts

#### Step 7: Recovery from Multi-Session Conflicts

**If you discover conflicts:**

```bash
# 1. Save your work
git stash save "My session work - conflicts with other session"

# 2. Pull latest from main
git checkout main
git pull

# 3. Create new branch with updated base
git checkout -b feature/my-feature-v2

# 4. Re-apply your work
git stash pop

# 5. Resolve conflicts manually
# 6. Test, commit, push, create PR
```

### Best Practices Summary

✅ **Session-specific branch names** (feature/X-sessionA, docs/Y-sessionB)
✅ **Check for active sessions before starting** (`gh pr list`, `git branch -r`)
✅ **Coordinate on foundation docs** (one session at a time)
✅ **Use `git stash` to save others' work** (never `git reset --hard`)
✅ **Push early and often** (signals work in progress)
✅ **Create draft PRs** (shows other sessions what you're working on)

### Real-World Example (2025-11-15)

- Session A: Working on CLI Windows compatibility
- Session B: Working on Codecov/Sentry documentation
- **Conflict:** Both modified `MASTER_REQUIREMENTS V2.13 → V2.14`
- **Resolution:** Session A stashed changes, waited for Session B to create PR, will sync after merge

**Reference:** This pattern emerged from 2025-11-15 multi-session coordination during Phase 1 completion.

---

## 8. Ending a Session

**⏱️ Time Required:** 10 minutes

### Step 0: Archive Current SESSION_HANDOFF.md

```bash
# Archive current session handoff before overwriting (local-only, not committed)
cp SESSION_HANDOFF.md "_sessions/SESSION_HANDOFF_$(date +%Y-%m-%d).md"

# Note: _sessions/ is in .gitignore (local archives, not committed to git)
# Historical archives (2025-10-28 through 2025-11-05) remain in docs/sessions/ git history
```

**Why:** Preserves session context locally during active development. Archives are local-only (excluded from git) to prevent repository bloat. Git commit messages and foundation documents provide permanent context.

### Step 1: Update SESSION_HANDOFF.md (5 minutes)

Use this structure:

```markdown
# Session Handoff

**Session Date:** 2025-10-XX
**Phase:** Phase 1 (50% → 65%)
**Duration:** X hours

## This Session Completed
- ✅ Implemented Kalshi API authentication
- ✅ Added rate limiting (100 req/min)
- ✅ Created 15 API client tests (all passing)

## Previous Session Completed
- ✅ Database schema V1.7
- ✅ All migrations applied
- ✅ Tests passing (66/66)

## Current Status
- **Tests:** 81/81 passing (89% coverage)
- **Blockers:** None
- **Phase Progress:** Phase 1 at 65%

## Next Session Priorities
1. Implement CLI commands with Typer
2. Add config loader (YAML + .env)
3. Write integration tests (live demo API)

## Files Modified
- Created: `api_connectors/kalshi_client.py`
- Created: `tests/test_kalshi_client.py`
- Updated: `requirements.txt` (added requests)

## Validation Script Updates (if applicable)
- [ ] Schema validation updated? (new price/versioned tables added to `validate_schema_consistency.py`)
- [ ] Documentation validation updated? (new doc types added to `validate_docs.py`)
- [ ] Test coverage config updated? (new modules added)
- [ ] All validation scripts tested successfully?

## Notes
- API auth uses RSA-PSS (not HMAC-SHA256)
- All prices parsed as Decimal from *_dollars fields
- Rate limiter working correctly
```

### Step 2: Commit Changes (3 minutes)

```bash
git add .
git commit -m "Implement Kalshi API client with RSA-PSS auth

- Add api_connectors/kalshi_client.py
- Implement authentication, rate limiting, error handling
- Parse all prices as Decimal from *_dollars fields
- Add 15 unit tests with mock responses (all passing)
- Coverage: 87% → 89%

Phase 1: 50% → 65% complete

Co-authored-by: Claude <noreply@anthropic.com>"
```

### Step 3: Verify Branch and Push to Remote (2 minutes)

```bash
# CRITICAL: Verify NOT on main branch (branch protection will block push to main)
BRANCH=$(git branch --show-current)
echo "Current branch: $BRANCH"

# If on main, create feature branch first!
if [ "$BRANCH" = "main" ]; then
    echo "❌ ERROR: On main branch! Create feature branch first:"
    echo "  git checkout -b feature/your-feature-name"
    exit 1
fi

# Push to current feature branch
git push origin $BRANCH

# Then create PR (see Branch Protection & Pull Request Workflow section)
# gh pr create --title "..." --body "..."
```

---

## 9. Phase Transitions

**⏱️ Time Required:** 50 minutes (10-step assessment)

**When to use:** At the end of EVERY phase

See `docs/utility/PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md` for complete 10-step protocol.

**Quick summary:**
1. Deliverable Completeness (10 min) - All deliverables created, coverage targets met?
2. Internal Consistency (5 min) - Terminology, technical details aligned?
3. Dependency Verification (5 min) - All cross-references valid?
4. Quality Standards (5 min) - Spell check, format consistency?
5. Testing & Validation (3 min) - Tests passing, coverage >80%?
6. Gaps & Risks (2 min) - Technical debt documented, deferred tasks created?
7. AI Code Review Analysis (10 min) - Claude review comments analyzed and triaged?
8. Archive & Version Management (5 min) - Old versions archived, MASTER_INDEX updated?
9. Security Review (5 min) - No hardcoded credentials, all secrets in env?
10. Next Phase Test Planning (10 min) - Test planning checklist completed for next phase?

**Output:** Create `docs/phase-completion/PHASE_N_COMPLETION_REPORT.md`

---

## 10. Deferred Task Tracking (Dual-System)

**⏱️ Time Required:** Ongoing (2-5 minutes per task)

### 10.1 The Problem: Lost Tasks

**Observation:** Tasks get forgotten when tracked in documentation only.

**Example from Phase 0.7:**
- Phase 0.7 created 7 deferred tasks (DEF-001 through DEF-007)
- Only 3 implemented in Phase 1 (DEF-001, DEF-002, DEF-003)
- 4 remain unaddressed (DEF-004 through DEF-007)

**Root cause:** Documentation-only tracking relies on human memory. Developers must:
1. Remember to check PHASE_X_DEFERRED_TASKS.md at phase start
2. Parse through task descriptions to find relevant ones
3. Manually track completion status

### 10.2 Dual-Tracking Solution

**Layer 1: Documentation** - `PHASE_X_DEFERRED_TASKS_V1.0.md`
- **Purpose:** Provides context, rationale, implementation details
- **Format:** Markdown document with DEF-XXX IDs
- **Location:** `docs/utility/`
- **Example:** DEF-001 includes background, acceptance criteria, time estimate, dependencies

**Layer 2: GitHub Issues** - One issue per task
- **Purpose:** Provides visibility, persistence, filtering capability
- **Format:** GitHub issue with labels and milestone
- **Labels:** `deferred-task`, `phase-X`, `priority-high/medium/low`
- **Example:** Issue #45 for DEF-001 with link to documentation

**Bi-directional Links:**
- Documentation → Issue numbers (`**GitHub Issue:** #45`)
- Issue → Documentation lines (`See docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.4.md lines 139-223`)

### 10.3 Why Dual-Tracking Works

| Feature | Documentation Only | GitHub Issues Only | Dual-Tracking |
|---------|-------------------|-------------------|---------------|
| **Context & Rationale** | ✅ Excellent | ❌ Limited (text fields) | ✅ Best of both |
| **Visibility** | ⚠️ Requires reading doc | ✅ Excellent (dashboard) | ✅ Excellent |
| **Persistence** | ✅ Good (git history) | ✅ Good (issue tracker) | ✅ Excellent |
| **Filtering** | ❌ Manual grep | ✅ Labels, milestones | ✅ Multiple methods |
| **Reminders** | ❌ Must remember to check | ✅ Email, notifications | ✅ Multiple channels |
| **Search** | ⚠️ Text search only | ✅ Issue search | ✅ Both methods |
| **Effort to Create** | 🟢 Low (markdown) | 🟢 Low (gh CLI) | 🟡 Medium (both) |
| **Effort to Maintain** | 🟢 Low (git commit) | 🟡 Medium (close issues) | 🟡 Medium (sync both) |

**Key Insight:** Documentation provides depth, GitHub provides breadth. Together they ensure tasks aren't forgotten.

### 10.4 Creating Deferred Tasks (Step-by-Step)

**When a task is deferred during phase work:**

#### Step 1: Document in PHASE_X_DEFERRED_TASKS.md (3 minutes)

```markdown
## DEF-P1-015: Fix Float Usage in Property Tests

**Priority:** 🔴 Critical
**Target Phase:** Phase 1.5
**Time Estimate:** 30 minutes
**GitHub Issue:** #89
**Source:** PR #13 AI review
**Created:** 2025-11-15

### Description
test_strategy_versioning_properties.py uses st.floats() instead of st.decimals()
Violates Pattern 1: Decimal Precision for Financial Data

### Rationale
Property-based tests should use same types as production code (Decimal, not float).
Float precision errors can mask bugs in Decimal-based logic.

### Implementation
Replace in test_strategy_versioning_properties.py line 79:

```python
# WRONG (current)
"max_edge": draw(st.floats(min_value=0.05, max_value=0.50)),

# CORRECT
from decimal import Decimal
"max_edge": draw(st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.50"), places=4)),
```

### Acceptance Criteria
- [ ] All st.floats() replaced with st.decimals() in property tests
- [ ] Import Decimal from decimal module
- [ ] Tests still pass (100+ generated cases)
- [ ] Pattern 1 compliance verified

### Dependencies
- None (standalone fix)

### Related
- Pattern 1: Decimal Precision (DEVELOPMENT_PATTERNS_V1.2.md)
- ADR-002: Decimal for Financial Calculations
- PR #13: Hypothesis Integration (AI review comment)
```

#### Step 2: Create GitHub Issue (2 minutes)

```bash
# Create issue via GitHub CLI
gh issue create \
  --title "DEF-P1-015: Fix Float Usage in Property Tests" \
  --body "**Priority:** 🔴 Critical
**Target Phase:** Phase 1.5
**Time Estimate:** 30 minutes

Replace st.floats() with st.decimals() in property tests to comply with Pattern 1 (Decimal Precision).

**Documentation:** See docs/utility/PHASE_1_DEFERRED_TASKS_V1.0.md lines 450-495

**Source:** PR #13 AI review" \
  --label "deferred-task" \
  --label "phase-1.5" \
  --label "priority-critical"

# Output: Created issue #89
```

#### Step 3: Add Bi-Directional Links (1 minute)

**Update documentation with issue number:**
```markdown
**GitHub Issue:** #89
```

**Update issue with documentation reference:**
```bash
gh issue edit 89 --body "**Priority:** 🔴 Critical
**Target Phase:** Phase 1.5
**Time Estimate:** 30 minutes

Replace st.floats() with st.decimals() in property tests to comply with Pattern 1 (Decimal Precision).

**Documentation:** See docs/utility/PHASE_1_DEFERRED_TASKS_V1.0.md lines 450-495

**Source:** PR #13 AI review"
```

### 10.5 Phase Start Protocol Integration

**At the START of every phase, check BOTH sources:**

```bash
# 1. Find deferred task documents
find docs/utility -name "PHASE_*_DEFERRED_TASKS*.md"

# 2. Check GitHub issues for this phase
gh issue list --label "deferred-task,phase-1.5"

# 3. Create combined todo list
TodoWrite([
    {"content": "DEF-001: Pre-commit hooks (2h) - Issue #45", "status": "pending"},
    {"content": "DEF-P1-015: Fix float usage (30min) - Issue #89", "status": "pending"},
    # ... more tasks
])
```

### 10.6 Phase Completion Protocol Integration

**Step 6 of Phase Completion Protocol now includes:**

- [ ] **Create GitHub issues for all deferred tasks** (not just document them)
- [ ] **Add labels:** deferred-task, phase-X, priority-X
- [ ] **Add bi-directional links** (documentation ↔ issues)
- [ ] **Verify issue visibility:** `gh issue list --label "deferred-task"`

**Prevents future task loss** by ensuring dual-tracking is set up before phase ends.

### 10.7 Closing Deferred Tasks

**When task is completed:**

```bash
# 1. Update documentation (mark as complete)
# In PHASE_X_DEFERRED_TASKS.md, change:
**Status:** ⏸️ Deferred → **Status:** ✅ Complete (Phase 1.5, 2025-11-20)

# 2. Close GitHub issue
gh issue close 89 --comment "Completed in Phase 1.5. All st.floats() replaced with st.decimals(). See commit abc123."

# 3. Reference in SESSION_HANDOFF
## This Session Completed
- ✅ DEF-P1-015: Fixed float usage in property tests (Issue #89 closed)
```

### 10.8 Example: Phase 1 Deferred Tasks

**Created during PR analysis (2025-11-15):**

- **Critical (3 tasks):**
  - DEF-P1-011: Fix float usage in property tests - Issue #87
  - DEF-P1-012: Add tests for database/initialization.py - Issue #88
  - DEF-P1-013: Path sanitization for security - Issue #89

- **High (8 tasks):**
  - DEF-P1-001: Branch protection verification script - Issue #90
  - DEF-P1-002: ADR-054 creation - Issue #91
  - ... (6 more)

**All tracked via dual-system:**
- Documentation: `docs/utility/PHASE_1_DEFERRED_TASKS_V1.0.md`
- GitHub: 45 issues with labels `deferred-task`, `phase-1.5`, `priority-X`

**Result:** Zero lost tasks. All visible at phase start via `gh issue list`.

---

## Summary

This guide provides comprehensive workflows for:
1. ✅ **Starting sessions** - 5-minute checklist with git safety, phase check, todo list
2. ✅ **Phase starts** - 15-minute protocol ensuring no tasks missed (deferred + test planning)
3. ✅ **Pre-planning checklist** - 5-minute test coverage verification (ALL 8 test types) ⭐ **NEW**
4. ✅ **Development** - Continuous progress tracking with TodoWrite
5. ✅ **Git safety** - Pre-commit, pre-push (parallelized!), branch protection
6. ✅ **Recovery** - 5-minute protocol for interrupted sessions
7. ✅ **Multi-session** - 7-step coordination preventing conflicts
8. ✅ **Ending sessions** - 10-minute handoff with SESSION_HANDOFF.md update
9. ✅ **Phase transitions** - 50-minute 10-step assessment protocol
10. ✅ **Deferred tasks** - Dual-tracking system (documentation + GitHub) ensuring no task loss

**Key References:**
- CLAUDE.md - Project overview and critical patterns
- SESSION_HANDOFF.md - Recent work and next steps
- DEVELOPMENT_PHASES_V1.4.md - Phase objectives and prerequisites
- PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md - 10-step phase completion

---

**END OF SESSION_WORKFLOW_GUIDE_V1.1**
