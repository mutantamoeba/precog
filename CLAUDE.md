# Precog Project Context for Claude Code

---
**Version:** 1.21
**Created:** 2025-10-28
**Last Updated:** 2025-11-16
**Purpose:** Main source of truth for project context, architecture, and development workflow
**Target Audience:** Claude Code AI assistant in all sessions
**Changes in V1.21:**
- **SESSION_HANDOFF.md Workflow Clarity** - Clarified that SESSION_HANDOFF.md is a historical record, not a task planner
- **Added explicit warnings** in "Quick Session Start" Step 1 and Step 2 to verify current state from git/GitHub
- **Problem Addressed:** AI assistants incorrectly using old SESSION_HANDOFF.md documents to determine pending tasks
- **Solution:** Emphasize verifying actual current state (gh issue list, git status) before starting work
- **Updated "Quick Session End"** Step 1 to clarify SESSION_HANDOFF.md is written at END to document completed work
- **Real-world trigger:** Multiple instances of completing tasks DEF-P1-001 through DEF-P1-007, then incorrectly listing them as pending again
- Total changes: ~30 lines of clarifying text + warnings
**Changes in V1.20:**
- **Parallel Branch Update Pattern** - Added efficient workflow for merging multiple PRs with branch protection enabled
- Documents pattern discovered during Phase 1.5 completion work (PRs #79, #80, #81, #82)
- **Problem Addressed:** "Require up-to-date" branch protection blocks merging after each PR merge, requiring repeated updates
- **Solution:** Update ALL PR branches in parallel FIRST, wait for CI, THEN merge sequentially
- **Time Savings:** 10-15 min with 3+ PRs (5-7 min parallel vs 15-20 min sequential)
- Added to Section 3 "During Development Quick Reference" → "Merging Multiple PRs Efficiently"
- Explains tradeoffs: Keep rule (recommended), Disable rule (risky), Merge Queue (not available free tier)
- Total addition: ~40 lines explaining parallel update workflow pattern
**Changes in V1.19:**
- **Issue Tracking Protocol** - Added standardized issue closure protocol to "During Development" section
- **Reconciliation Script** - Created scripts/reconcile_issue_tracking.sh (270 lines) to verify GitHub issues match documentation status
- **Three-Method Approach**: Closing via PR (preferred, auto-closes issue), manual closure (with comment), reconciliation check (phase completion)
- **Dual-Tracking Consistency**: Prevents "I thought we completed that" confusion by maintaining GitHub + documentation synchronization
- **Audit Trail**: Clear tracking of which PR/commit closed each issue
- Total addition: ~320 lines (script: 270, CLAUDE.md: 50)
**Changes in V1.18:**
- **CLAUDE.md Size Reduction - Section 3 (80%)** - Reduced Section 3 from ~700 lines to ~140 lines (~560 line reduction)
- **Extracted SESSION_WORKFLOW_GUIDE_V1.0.md** - All detailed session workflows moved to comprehensive guide
- **Added "When to Read the Complete Guide" section** - Clear triggers for when full workflows are needed (starting phases, recovery, multi-session coordination)
- **Preserved essential quick reference** - Quick session start, development commands, session end workflows remain in CLAUDE.md
- **Context budget optimization** - Frees ~560 lines (~7,000 tokens) for additional code context in conversations
- **Follows V1.16 extraction pattern** - Concise summary + prominent link to extracted guide
- Total: Section 3 condensed from ~700 lines to ~140 lines (80% reduction, following V1.16 extraction pattern)
**Changes in V1.17:**
- **Added Multi-Session Coordination section** - Comprehensive 7-step protocol for running multiple Claude Code sessions simultaneously
- Documents session-specific branch naming (feature/X-sessionA, docs/Y-sessionB)
- Foundation document coordination protocol (one session at a time for MASTER_REQUIREMENTS, ARCHITECTURE_DECISIONS, etc.)
- Prevention strategies: Check for active sessions (`gh pr list`, `git branch -r`), use `git stash` instead of `git reset --hard`
- Conflict resolution workflow for version number collisions (V2.13→V2.14 from both sessions)
- Communication via git (draft PRs, early pushes, WIP commits)
- Real-world example from 2025-11-15 multi-session coordination (CLI Windows compatibility + Codecov/Sentry docs)
- Total addition: ~150 lines of multi-session coordination protocols
**Changes in V1.16:**
- **CLAUDE.md Size Reduction (48.7%)** - Reduced from 3,723 lines to 1,909 lines (~1,814 line reduction)
- **Created DEVELOPMENT_PATTERNS_V1.2.md** (1,200+ lines) - Extracted all 10 critical patterns with comprehensive code examples from CLAUDE.md
- **Created DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md** (850+ lines) - Extracted document cohesion workflows, update cascade rules, validation checklists
- **Replaced detailed sections with concise summaries** - Critical Patterns section now 55 lines (was 1,100 lines), Document Cohesion section now 47 lines (was 820 lines)
- **Preserved all cross-references** - All ADR, REQ, and file path references maintained in extracted documents
- **Context budget optimization** - Reduced CLAUDE.md from ~45,000 tokens (~23% of 200K budget) to ~23,000 tokens (~11.5% of budget)
- Enables faster session starts and leaves more room for code context in AI conversations
- Both extracted guides provide comprehensive reference documentation with full examples and educational content
**Changes in V1.15:**
- **Automated Template Enforcement (Phase 0.7c)** - Created 2 enforcement scripts that run in pre-commit/pre-push hooks
- **Created validate_code_quality.py** (314 lines) - Enforces CODE_REVIEW_TEMPLATE: module coverage ≥80%, REQ-XXX-NNN test coverage, educational docstrings (WARNING)
- **Created validate_security_patterns.py** (413 lines) - Enforces SECURITY_REVIEW_CHECKLIST: API auth, hardcoded secrets (FAIL), encryption/logging (WARNING)
- **Updated pre-commit hooks** - Added 2 new hooks: code-review-basics (REQ traceability), decimal-precision-check (Pattern 1 enforcement)
- **Updated pre-push hooks** - Added steps 6/7 (code quality) and 7/7 (security patterns) for comprehensive template enforcement
- Defense in Depth architecture: pre-commit (fast ~2-5s) → pre-push (thorough ~60-90s) → CI/CD (comprehensive ~2-5min)
- Cross-platform compatibility: All scripts use ASCII output (no Unicode) for Windows cp1252 compatibility
- Total addition: ~750 lines of automated template enforcement infrastructure
**Changes in V1.14:**
- **Created CODE_REVIEW_TEMPLATE_V1.0.md** - Universal code review checklist for PRs, feature implementations, and phase completions
- **Created INFRASTRUCTURE_REVIEW_TEMPLATE_V1.0.md** - Infrastructure and DevOps review template for deployment readiness
- **Enhanced SECURITY_REVIEW_CHECKLIST.md V1.0 → V1.1** - Added 4 new sections (API Security, Data Protection, Compliance, Incident Response)
- All three templates now reference **DEVELOPMENT_PHILOSOPHY_V1.1.md** with specific section callouts
- CODE_REVIEW_TEMPLATE references 7 philosophy sections (TDD, DID, DDD, Explicit Over Clever, Security by Default, Anti-Patterns, Test Coverage Accountability)
- INFRASTRUCTURE_REVIEW_TEMPLATE references 4 philosophy sections (Defense in Depth, Fail-Safe Defaults, Maintenance Visibility, Security by Default)
- SECURITY_REVIEW_CHECKLIST references 2 philosophy sections (Security by Default, Defense in Depth with 3-layer credential validation)
- Templates consolidate scattered guidance from CLAUDE.md, DEVELOPMENT_PHASES, Perplexity AI recommendations into standardized checklists
- Updated Critical References section to include new templates
- Total addition: ~1700 lines of comprehensive review infrastructure (CODE_REVIEW: 484 lines, INFRASTRUCTURE_REVIEW: 600 lines, SECURITY_REVIEW enhancement: 600 lines)
**Changes in V1.13:**
- **Added Section 3.1: Recovering from Interrupted Session** - Comprehensive 4-step recovery workflow for session interruptions
- Documents git status checking, recent work review, test validation, and workflow resumption
- Includes common recovery scenarios table with 4 patterns (interrupted during coding, after commit, during PR, after merge)
- Provides detailed example recovery from actual 2025-11-09 context limit interruption during Phase 1.5 integration tests
- Total addition: ~100 lines of session recovery patterns
**Changes in V1.12:**
- **Added Pattern 9: Multi-Source Warning Governance (MANDATORY)** - Comprehensive governance across pytest + validate_docs + code quality tools
- Documents discovery of 388 untracked warnings (90% blind spot from initial pytest-only governance)
- Establishes 429-warning baseline locked across 3 validation sources (pytest: 41, validate_docs: 388, code quality: 0)
- Classifies warnings: 182 actionable, 231 informational, 16 expected, 4 upstream
- Implements zero-regression policy via check_warning_debt.py (multi-source validation)
- Adds pre-push hook integration (Step 4) for local enforcement
- Documents governance policy: baseline locked, zero tolerance, phased reduction targets (Phase 1.5: -60, Phase 2: -182 total to zero)
- Provides example workflow, acceptable baseline update criteria, common mistakes
- Cross-references ADR-075, WARNING_DEBT_TRACKER.md, warning_baseline.json
- **Renumbered existing Pattern 9 (Property-Based Testing) → Pattern 10** for clarity
- Total addition: ~200 lines of warning governance patterns
**Changes in V1.11:**
- **Added Pattern 9: Property-Based Testing with Hypothesis (ALWAYS for Trading Logic)** - Comprehensive guide for writing property tests across all critical trading logic
- Documents proof-of-concept completion (26 tests, 2600+ test cases, 0 failures, 3.32s execution)
- Provides side-by-side comparison: example-based testing (5-10 cases) vs. property-based testing (thousands of auto-generated cases)
- Includes "ALWAYS Use Property Tests For" section covering 4 categories: mathematical invariants, business rules, state transitions, data validation
- Documents 3 custom Hypothesis strategies for trading domain (probability, bid_ask_spread, price_series)
- Demonstrates Hypothesis shrinking with concrete example (edge=0.473821 → edge=0.5)
- Provides decision table: when to use property tests vs. example tests (9 scenarios)
- Includes quick start guide (4 steps), common pitfalls (2 examples), performance considerations
- Cross-references Pattern 1 (Decimal Precision), Pattern 7 (Educational Docstrings), ADR-074, REQ-TEST-008 through REQ-TEST-011
- Total addition: ~235 lines of property-based testing patterns and guidance
**Changes in V1.10:**
- **Added Pattern 8: Configuration File Synchronization (CRITICAL)** - Comprehensive guide to prevent configuration drift across 4 layers (tool configs, pipeline configs, application configs, documentation)
- Documents the Bandit → Ruff migration issue we just fixed (orphaned `[tool.bandit]` in pyproject.toml caused 200+ errors)
- Provides migration checklists for 3 common scenarios: tool migration, requirement changes, new validation rules
- Explains YAML configuration validation (Check #9 in validate_docs.py) - already checking all 7 config/*.yaml files for float contamination
- Adds Decimal safety guidance for YAML files (use string format "0.05" not float 0.05)
- Includes configuration migration template with 4-layer checklist
- Provides common drift scenarios table and prevention strategies
- Total addition: ~200 lines of configuration management patterns
**Changes in V1.9:**
- **Implemented DEF-003: GitHub Branch Protection Rules** - Configured comprehensive branch protection for `main` branch via GitHub API
- **Added "Branch Protection & Pull Request Workflow" section** - Documents third layer of defense (pre-commit → pre-push → CI/CD → branch protection)
- Branch protection enforces: require PRs, require 6 CI status checks to pass, require up-to-date branches, require conversation resolution, no force pushes, no deletions, applies to administrators
- Pull request workflow documented: create feature branch, commit (pre-commit hooks), push (pre-push hooks), create PR, wait for CI, merge when green
- PR best practices: small focused PRs, descriptive titles, link to requirements, test locally first, watch CI results
- Repository changed from private to public to enable branch protection via API
- Completes three-layer local + remote validation: pre-commit (2-5s, checks + partial auto-fix) → pre-push (30-60s, tests) → CI/CD (2-5min, coverage) → branch protection (enforced merge gate)
**Changes in V1.8:**
- **Implemented DEF-002: Pre-Push Hooks Setup** - Created .git/hooks/pre-push script with 4 validation steps (quick validation, unit tests, full type checking, security scan)
- **Added "Pre-Push Hooks" section** - Documents second layer of defense, runs automatically on `git push`, ~30-60 second validation, includes tests (first time tests run in local workflow)
- Pre-push hooks provide comprehensive validation before code reaches GitHub: all pre-commit checks + unit tests + full codebase type checking + deep security scan
- Reduces CI failures by 80-90% (catches test failures locally before CI)
- Completes two-layer local validation strategy: pre-commit (fast, no tests) → pre-push (thorough, with tests) → CI/CD (comprehensive, multi-platform)
**Changes in V1.7:**
- **Implemented DEF-001: Pre-Commit Hooks Setup** - Installed pre-commit framework (v4.0.1) with 12 comprehensive checks
- **Updated "Before Committing Code" section** - Documents automatic pre-commit hooks workflow, 12 checks (Ruff, Mypy, security, formatting, line endings), auto-fix capabilities, manual testing commands, bypass instructions
- Pre-commit hooks run automatically on `git commit` with ~2-5 second feedback (vs 2+ minutes for CI)
- Auto-fixes: line endings (CRLF→LF), trailing whitespace, end-of-file newlines
- Check-only (no auto-fix): code formatting (Ruff --check), linting, type checking
- Blocks commits for: formatting issues, linting errors, type errors, hardcoded credentials, large files, merge conflicts
- Reduces CI failures by 60-70% through early detection
**Changes in V1.6:**
- Changed session archiving from `docs/sessions/` (committed) to `_sessions/` (local-only, excluded from git)
- Added `docs/sessions/` to .gitignore to prevent repository bloat from session archives
- Updated Section 3 "Ending a Session" Step 0 to use local `_sessions/` folder
- Historical session archives (2025-10-28 through 2025-11-05) remain in git history at `docs/sessions/`
- Rationale: Session archives are ephemeral documentation; git commit messages + foundation docs provide permanent context
**Changes in V1.5:**
- Created `docs/guides/` folder for implementation guides (addresses documentation discoverability issue)
- Moved 5 implementation guides from supplementary/ and configuration/ to docs/guides/
- Updated Section 6 "Implementation Guides" to list all 5 guides (added CONFIGURATION_GUIDE and POSTGRESQL_SETUP_GUIDE)
- Updated MASTER_INDEX V2.8 → V2.9 (5 location changes)
- Aligns documentation structure with Section 6 references (previously referenced non-existent folder)
**Changes in V1.4:**
- Added session history archiving workflow to Section 3 (Ending a Session - Step 0)
- Extracted 7 historical SESSION_HANDOFF.md versions from git history to docs/sessions/
- Preserves full session history with date-stamped archives before overwriting
**Changes in V1.3:**
- Updated all version references to reflect Phase 1 API best practices documentation (PART 0-1 updates)
- MASTER_REQUIREMENTS V2.8 → V2.10 (added REQ-API-007, REQ-OBSERV-001, REQ-SEC-009, REQ-VALIDATION-004)
- ARCHITECTURE_DECISIONS V2.7 → V2.9 (added ADR-047 through ADR-052 for API integration best practices)
- MASTER_INDEX V2.6 → V2.8 (added PHASE_1_TEST_PLAN and PHASE_0.7_DEFERRED_TASKS)
- Updated Quick Reference and Documentation Structure sections with current document versions
**Changes in V1.2:**
- Added Deferred Tasks Workflow to Phase Completion Protocol Step 6 (Section 9)
- Documents multi-location strategy for tracking non-blocking tasks deferred to future phases
- Added numbering convention (DEF-001, etc.), priority levels, and documentation locations
- Updated Current Status for Phase 0.7 completion
- Updated references to DEVELOPMENT_PHASES V1.4
**Changes in V1.1:**
- Added Rule 6: Planning Future Work (Section 5)
- Added Status Field Usage Standards (Section 5)
- Added validation commands to Quick Reference (Section 10)
- Updated Phase Completion Protocol with validate_all.sh (Section 9)
- Updated Current Status for Phase 0.6c completion
---

## 🎯 What This Document Does

This is **THE single source of truth** for working on Precog. Read this file at the start of every session along with `SESSION_HANDOFF.md` to get fully caught up in <5 minutes.

**This document contains:**
- Project architecture and current status
- Critical patterns (Decimal precision, versioning, security)
- **Document cohesion and consistency guidelines** (CRITICAL)
- Development workflow and handoff process
- Common tasks and troubleshooting
- Quick reference to all documentation

**What you need to read each session:**
1. **CLAUDE.md** (this file) - Comprehensive project context
2. **SESSION_HANDOFF.md** - What happened recently, what's next

That's it! No need to hunt through multiple status documents.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Current Status](#current-status)
3. [Session Handoff Workflow](#session-handoff-workflow)
4. [Critical Patterns](#critical-patterns)
5. [Document Cohesion & Consistency](#document-cohesion--consistency) ⚠️ **CRITICAL**
6. [Documentation Structure](#documentation-structure)
7. [Common Tasks](#common-tasks)
8. [Security Guidelines](#security-guidelines)
9. [Phase Completion Protocol](#phase-completion-protocol)
10. [Quick Reference](#quick-reference)

---

## 📖 Project Overview

### What is Precog?

**Precog** is a modular Python application that identifies and executes positive expected value (EV+) trading opportunities on prediction markets.

**How it works:**
1. Fetches live market prices from APIs (Kalshi, eventually Polymarket)
2. Calculates true win probabilities using versioned ML models
3. Identifies edges where market price < true probability
4. Executes trades automatically with risk management
5. Monitors positions with dynamic trailing stops
6. Exits strategically based on 10-condition priority hierarchy

**Initial Focus:** Kalshi platform, NFL/NCAAF markets
**Future Expansion:** Multiple sports, non-sports markets, multiple platforms

### Tech Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL 15+ with `DECIMAL(10,4)` precision (CRITICAL)
- **ORM:** SQLAlchemy + psycopg2
- **Testing:** pytest (>80% coverage required)
- **Configuration:** YAML files + `.env` for secrets
- **CLI:** Typer framework
- **APIs:** Kalshi (RSA-PSS auth), ESPN, Balldontlie

### Key Principles

1. **Safety First:** Multiple layers of risk management, decimal precision
2. **Version Everything:** Immutable strategy and model versions for A/B testing
3. **Test Everything:** 80%+ coverage, comprehensive test suite
4. **Document Everything:** Every decision has ADR, every change tracked
5. **Keep Documents in Sync:** When requirements change, cascade updates through all affected docs
6. **Secure Everything:** Zero credentials in code, comprehensive security reviews

---

## 🚦 Current Status

### Phase Progress

**Current Phase:** Phase 1 (Database & API Connectivity)
**Phase 1 Status:** 50% complete

**✅ Completed:**
- **Phase 0:** Foundation & Documentation (100%)
- **Phase 0.5:** Foundation Enhancement - Versioning, trailing stops (100%)
- **Phase 0.6:** Documentation Correction & Security Hardening (100%)
- **Phase 0.6c:** Validation & Testing Infrastructure (100%)
- **Phase 0.7:** CI/CD Integration & Advanced Testing (100%)
- **Phase 1 (Partial):** Database schema V1.7, migrations 001-010, Kalshi API client (100%), CLI commands (80% - API fetching only)

**🔵 In Progress:**
- **Phase 1 (Remaining):** CLI database integration (Phase 1.5), config loader expansion, integration testing

**📋 Planned:**
- **Phase 1.5:** Strategy Manager, Model Manager, Position Manager
- **Phase 2+:** See `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

---

## 🚨 CRITICAL: Pre-Commit Protocol (MANDATORY)

**⚠️ READ THIS SECTION BEFORE EVERY `git commit` ⚠️**

### You MUST Run These 4 Checks - NO EXCEPTIONS

**Before staging files with `git add`, run:**

**□ Step 1/4: Run Tests**
```bash
python -m pytest tests/ -v
```
**Expected:** All tests passing
**If FAIL:** Fix tests BEFORE committing. Do not use `--no-verify`.

**□ Step 2/4: Security Scan**
```bash
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'
```
**Expected:** No matches (or only docstring examples with "test-key-id" / "example-key")
**If MATCH:** Remove ALL hardcoded credentials. Use `os.getenv()` instead.

**□ Step 3/4: Check .env File**
```bash
git diff --cached --name-only | grep "\.env$" && echo "❌ .env STAGED!" || echo "✅ No .env"
```
**Expected:** "✅ No .env"
**If "❌ .env STAGED!":** Run `git reset HEAD .env` immediately

**□ Step 4/4: Quick Validation**
```bash
./scripts/validate_quick.sh
```
**Expected:** All checks pass (~3 seconds)
**If FAIL:** Fix linting/docs errors before committing

---

**✅ ALL 4 PASS** → Safe to commit:
```bash
git add <files>
git commit -m "Your commit message"
```

**❌ ANY FAIL** → FIX FIRST, then re-run all 4 checks

---

### Permanent Solution: Pre-Commit Hooks

**Status:** Ready to install (`.pre-commit-config.yaml` exists, framework in requirements.txt)

**To install (do this once):**
```bash
# Install pre-commit framework
pip install pre-commit

# Install git hooks
pre-commit install

# Test hooks on all files
pre-commit run --all-files
```

**After installation:** Git will automatically run all 4 checks before EVERY commit.
- Hooks will BLOCK commits that fail security/quality checks
- To bypass (ONLY in emergencies): `git commit --no-verify`

**Deferred Task:** DEF-001 in `docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.0.md`

---

## 📋 Phase Task Visibility System

**⚠️ READ AT START OF EVERY PHASE ⚠️**

### Problem: Task Blindness

Tasks get overlooked because they're scattered across multiple documents:
- Deferred tasks in `docs/utility/PHASE_*_DEFERRED_TASKS_V1.0.md`
- Phase checklist in `DEVELOPMENT_PHASES_V1.4.md`
- Requirements in `MASTER_REQUIREMENTS_V2.10.md`
- ADRs in `ARCHITECTURE_DECISIONS_V2.10.md`

### Solution: 3-Step Phase Start Protocol

**At the START of every new phase, follow this exact sequence:**

#### Step 1: Check Deferred Tasks (5 min)

```bash
# Find all deferred task documents
find docs/utility -name "PHASE_*_DEFERRED_TASKS*.md"

# Read each document, extract tasks for CURRENT phase
# Example: If starting Phase 1, find all tasks with "Target Phase: 1" or "0.8"
```

**Create checklist:**
```markdown
## Phase 1 Deferred Tasks (from Phase 0.7)
- [ ] DEF-001: Pre-commit hooks setup (2 hours, 🟡 High)
- [ ] DEF-002: Pre-push hooks setup (1 hour, 🟡 High)
- [ ] DEF-003: Branch protection rules (30 min, 🟢 Medium)
- [ ] DEF-004: Line ending edge cases (1 hour, 🟢 Medium)
- [ ] DEF-008: Database schema validation script (3-4 hours, 🟡 High)
```

#### Step 2: Check Phase Prerequisites (5 min)

Open `DEVELOPMENT_PHASES_V1.4.md`, find current phase section.

**Check:**
- [ ] **Dependencies met?** (e.g., "Requires Phase 0.7: 100% complete ✅")
- [ ] **Test planning checklist exists?** ("Before Starting This Phase - TEST PLANNING CHECKLIST")
- [ ] **Tasks clearly listed?** (numbered task list in phase section)
- [ ] **Coverage targets exist for ALL deliverables?** (Extract deliverables → Verify each has explicit coverage target)
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

### Prevention: Update SESSION_HANDOFF Template

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

### What Works Right Now

```bash
# Database connection and CRUD operations
python scripts/test_db_connection.py  # ✅ Works

# All tests
python -m pytest tests/ -v  # ✅ 66/66 passing, 87% coverage

# Database migrations
python scripts/apply_migration_v1.5.py  # ✅ Works

# Validation & Testing (Phase 0.6c)
./scripts/validate_quick.sh  # ✅ Works (~3 sec - code quality + docs)
./scripts/validate_all.sh    # ✅ Works (~60 sec - full validation)
./scripts/test_fast.sh       # ✅ Works (~5 sec - unit tests only)
./scripts/test_full.sh       # ✅ Works (~30 sec - all tests + coverage)
python scripts/validate_docs.py  # ✅ Works (documentation validation)
python scripts/fix_docs.py       # ✅ Works (auto-fix doc issues)
```

### What Doesn't Work Yet

```bash
# API integration - Not implemented
python main.py fetch-balance  # ❌ Not implemented

# CLI commands - Not implemented
python main.py fetch-markets  # ❌ Not implemented

# Trading - Not implemented (Phase 5)
python main.py execute-trades  # ❌ Not implemented
```

### Repository Structure

**Note:** Migrated to src/ layout on 2025-11-14 (PEP 517/518 best practices)

```
precog-repo/
├── ✅ src/precog/                # Main package (modern src layout)
│   ├── __init__.py              # ✅ Package initialization
│   ├── api_connectors/          # ✅ API clients (Kalshi, ESPN, etc.)
│   │   ├── kalshi_client.py     # ✅ Complete (97.91% coverage)
│   │   ├── kalshi_auth.py       # ✅ RSA-PSS authentication
│   │   ├── rate_limiter.py      # ✅ Token bucket rate limiting
│   │   └── types.py             # ✅ TypedDict response types
│   ├── config/                  # ✅ YAML configuration files
│   │   ├── config_loader.py     # ✅ Complete (98.97% coverage)
│   │   └── *.yaml               # ✅ 7 configuration files
│   ├── database/                # ✅ Database layer
│   │   ├── connection.py        # ✅ Connection pooling (81.82% coverage)
│   │   ├── crud_operations.py   # ✅ CRUD operations (86.01% coverage)
│   │   ├── initialization.py    # ✅ Schema initialization
│   │   ├── migrations/          # ✅ Migrations 001-010
│   │   └── seeds/               # ✅ NFL team Elo data
│   └── utils/                   # ✅ Utilities
│       └── logger.py            # ✅ Structured logging (86.08% coverage)
├── ✅ tests/                     # Test suite (348 tests passing)
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── property/                # Property-based tests (Hypothesis)
├── ✅ scripts/                   # Utility scripts
│   ├── migrate_imports.py       # ✅ Import migration automation
│   ├── check_warning_debt.py    # ✅ Warning governance
│   └── validate_*.py            # ✅ Validation scripts
├── ✅ docs/                      # Comprehensive documentation
│   ├── foundation/              # Core requirements, architecture
│   ├── guides/                  # Implementation guides
│   ├── supplementary/           # Detailed specifications
│   └── utility/                 # Process documents
├── ✅ main.py                    # CLI entry point (Typer)
├── ✅ pyproject.toml             # Package configuration (PEP 517/518)
├── ✅ CLAUDE.md                  # This file!
└── ✅ SESSION_HANDOFF.md         # Current session status
```

**Import Example (after src/ layout migration):**
```python
# New import style (src/precog/ layout)
from precog.api_connectors import KalshiClient
from precog.config import ConfigLoader
from precog.database import get_connection
from precog.utils import get_logger
```

---

## 🔄 Session Handoff Workflow

**⚠️ COMPLETE REFERENCE:** See `docs/utility/SESSION_WORKFLOW_GUIDE_V1.0.md` for comprehensive session workflows.

This section provides quick reference for common session tasks. For detailed workflows including phase start protocols, git safety procedures, recovery patterns, multi-session coordination, and deferred task tracking, see the complete guide.

### When to Read the Complete Guide

**Always read SESSION_WORKFLOW_GUIDE when:**
- 🚨 **Starting a new phase** (Phase start protocol with 3-step checklist)
- 🚨 **Recovering from session interruption** (4-step recovery workflow)
- 🚨 **Multiple sessions active** (7-step multi-session coordination protocol)
- 🚨 **Phase transitions** (comprehensive phase completion checklist)
- 📋 **Managing deferred tasks** (dual-tracking system with GitHub issues)

**This quick reference is sufficient for:**
- Starting routine development sessions
- Standard commit/push workflows
- Ending sessions with handoff updates

### Quick Session Start (5 minutes)

**Step 1: Read Project Context**
1. **CLAUDE.md** (this file) - Project overview, patterns, status
2. **SESSION_HANDOFF.md** - Recent work context (HISTORICAL RECORD, not a task list)

⚠️ **CRITICAL:** SESSION_HANDOFF.md shows what was done recently, but tasks listed as "Next Session Priorities" may have been completed after the handoff was written. **Always verify current state from git/GitHub in Step 2** before starting work.

**Step 2: Verify Current State (MANDATORY)**
```bash
# Check branch and status
git branch --show-current
git status

# Check open issues (verify what's actually pending)
gh issue list --state open --label deferred-task

# Check open PRs
gh pr list --state open

# Check for unpushed work
git branch -vv | grep ahead || echo "All up-to-date"
```

⚠️ **Why:** SESSION_HANDOFF.md may list tasks as "Next Session Priorities" that were already completed. Verify actual current state from GitHub (source of truth) before starting work.

**Step 3: Check Phase Prerequisites**
- Verify current phase in DEVELOPMENT_PHASES_V1.4.md
- **IF STARTING NEW PHASE:** Read SESSION_WORKFLOW_GUIDE Section 2 (Phase Start Protocol)
- **IF RESUMING WORK:** Create todo list with TodoWrite

### During Development Quick Reference

**Pre-commit Hooks (Automatic):**
- Run on `git commit` automatically (~2-5 seconds)
- Auto-fix: line endings (CRLF→LF), trailing whitespace, end-of-file newlines
- Check-only (no auto-fix): code formatting (Ruff), linting, type checking
- Block: formatting issues, linting errors, type errors, hardcoded credentials
- 14 checks including Pattern 1 (Decimal precision) enforcement
- **To fix formatting:** Run `python -m ruff format .` manually before committing

**Pre-push Hooks (Automatic):**
- Run on `git push` automatically (~30-60 seconds)
- 8 validation steps including tests, security, coverage
- Reduces CI failures by 80-90%

**Branch Protection (GitHub):**
- Direct pushes to `main` blocked (must use PRs)
- 6 required CI checks must pass before merge
- **"Require up-to-date" rule enabled:** PRs must be current with main before merging
- Workflow: feature branch → commit → push → create PR → wait for CI → merge

**Merging Multiple PRs Efficiently:**

When you have multiple PRs ready to merge, use this pattern to save time (avoids repeated sequential updates):

```bash
# 1. Update ALL PR branches in parallel (BEFORE merging any):
for branch in test/improve-coverage-initialization docs/phase-workflow-automation-enhancements docs/issue-tracking-protocol; do
  (git checkout $branch && git fetch origin main && git merge origin/main && git push origin $branch) &
done
wait

# 2. Wait for CI checks to complete on ALL branches (~2-3 min)
# Check status: gh pr checks 79 && gh pr checks 80 && gh pr checks 81

# 3. Merge sequentially (all branches already up-to-date, no further updates needed):
gh pr merge 79 --squash
gh pr merge 80 --squash
gh pr merge 81 --squash
```

**Why This Pattern Matters:**
- **"Require up-to-date" rule:** After each merge, main advances → other PRs become out-of-date
- **Sequential approach:** Update PR #1 → merge → Update PR #2 → merge → Update PR #3 → merge (15-20 min)
- **Parallel approach:** Update ALL PRs first → merge ALL sequentially (5-7 min)
- **Time savings:** ~10-15 min with 3+ PRs

**Tradeoffs:**
- **Keep rule enabled (recommended for production):** Prevents "worked alone, broken together" bugs
- **Disable rule (faster but riskier):** Allows merging outdated branches, possible integration issues
- **GitHub Merge Queue (not available on free tier):** Automates this pattern

**Manual Commands (Optional):**
```bash
# Fix code formatting (if pre-commit hook reports formatting issues)
python -m ruff format .

# Run tests
python -m pytest tests/ -v

# Check coverage
python -m pytest tests/ --cov=. --cov-report=term-missing

# Security scan
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'
```

**Issue Tracking Protocol:**

When closing GitHub issues, follow this standardized protocol to maintain tracking consistency:

**1. Closing via PR (Preferred Method):**
```bash
# In PR description, include one of these keywords:
# - "Closes #123"
# - "Fixes #123"
# - "Resolves #123"

# Example PR description:
gh pr create --title "Add retry logic to API client" --body "
Implements exponential backoff with configurable max retries.

Closes #37

**Testing:**
- Added 5 new tests for retry scenarios
- All 25 API client tests passing
"
```

When PR merges, GitHub automatically:
- Closes the linked issue
- Adds comment linking issue → PR
- **You must also:** Update documentation status in the PR (e.g., mark issue as Complete in PHASE_X_DEFERRED_TASKS)

**2. Closing Manually (When No PR):**
```bash
# Close with explanatory comment
gh issue close 42 --comment "Completed in commit abc1234. Updated database schema to include retry_count field."

# Then update documentation
# Example: Mark DEF-P1-008 as Complete in docs/utility/PHASE_1_PR_REVIEW_DEFERRED_TASKS_V1.0.md
```

**3. Reconciliation Check (Phase Completion):**
```bash
# Run at end of phase to verify synchronization
bash scripts/reconcile_issue_tracking.sh

# Outputs:
# - Issues closed in GitHub but marked "Open" in docs → Update docs
# - Issues open in GitHub but marked "Complete" in docs → Close issue or revert docs
```

**Why This Matters:**
- Prevents "I thought we completed that" confusion
- Maintains dual-tracking consistency (GitHub + documentation)
- Provides clear audit trail (which PR/commit closed each issue)

### Quick Session End (10 minutes)

**Step 1: Update SESSION_HANDOFF.md**
- **Purpose:** Record what was accomplished THIS session (historical record, not task planner)
- Document completed work, current status
- **Next priorities:** Suggest based on verified current state (gh issue list, phase objectives)
- ⚠️ **Do NOT copy "Next Session Priorities" from old handoff** - determine them fresh from actual state
- Include test results, phase progress percentage
- List modified files

**Step 2: Commit Changes**
```bash
git add .
git commit -m "Descriptive commit message

- Detail 1
- Detail 2
- Detail 3

Phase X: Y% → Z% complete

Co-authored-by: Claude <noreply@anthropic.com>"
```

**Step 3: Push to Feature Branch**
```bash
# Verify NOT on main
BRANCH=$(git branch --show-current)
echo "Current branch: $BRANCH"

# Push to feature branch
git push origin $BRANCH

# Create PR if ready
gh pr create --title "..." --body "..."
```

### Special Situations → Read Complete Guide

**Session interrupted mid-work?**
→ Read SESSION_WORKFLOW_GUIDE Section 5 (Recovering from Interrupted Sessions)

**Multiple sessions running?**
→ Read SESSION_WORKFLOW_GUIDE Section 6 (Multi-Session Coordination)

**Phase complete?**
→ Read PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md (10-step assessment)

**Tasks deferred to next phase?**
→ Read SESSION_WORKFLOW_GUIDE Section 9 (Deferred Task Tracking)

### Updating CLAUDE.md (Only When Needed)

**Update this file ONLY when:**
- Major architecture changes (new patterns, tech stack changes)
- Phase transitions (Phase 1 → Phase 2)
- Critical patterns change (e.g., new security requirements)
- Status section needs major updates (>20% phase progress)

**Don't update for:**
- Every session (that's what SESSION_HANDOFF is for)
- Minor code changes
- Bug fixes
- Test additions

**When you do update:**
1. Increment version in header (1.0 → 1.1)
2. Add "Changes in vX.Y" section
3. Update relevant sections
4. Keep history at bottom

---

## 🏗️ Critical Development Patterns

**⚠️ COMPLETE REFERENCE:** See `docs/guides/DEVELOPMENT_PATTERNS_V1.2.md` for comprehensive patterns with code examples.

This section provides quick reference to the 10 critical patterns. For full details, code examples showing ✅ CORRECT vs ❌ WRONG usage, and cross-references to ADRs/REQs, see the complete guide.

### Pattern Quick Reference

1. **Decimal Precision (NEVER USE FLOAT)**
   - Use `Decimal("0.4975")` for all prices/probabilities
   - ❌ NEVER: `price = 0.4975` (float)
   - Reference: Pattern 1 in DEVELOPMENT_PATTERNS_V1.2.md

2. **Dual Versioning System**
   - SCD Type 2 for markets/positions (`row_current_ind`)
   - Immutable versions for strategies/models (`version` field)
   - Reference: Pattern 2 in DEVELOPMENT_PATTERNS_V1.2.md

3. **Trade Attribution**
   - Every trade links to exact `strategy_id` and `model_id`
   - Reference: Pattern 3 in DEVELOPMENT_PATTERNS_V1.2.md

4. **Security (NO CREDENTIALS IN CODE)**
   - All credentials from `os.getenv()`, never hardcoded
   - Pre-commit hooks scan for secrets
   - Reference: Pattern 4 in DEVELOPMENT_PATTERNS_V1.2.md

5. **Cross-Platform Compatibility**
   - ASCII output for console (Windows cp1252 compatibility)
   - Explicit UTF-8 for file I/O
   - Reference: Pattern 5 in DEVELOPMENT_PATTERNS_V1.2.md

6. **TypedDict for API Responses**
   - Compile-time type safety, zero runtime overhead
   - Use until Phase 5+ (then Pydantic)
   - Reference: Pattern 6 in DEVELOPMENT_PATTERNS_V1.2.md

7. **Educational Docstrings (ALWAYS)**
   - Description + Args/Returns + Educational Note + Examples + References
   - Reference: Pattern 7 in DEVELOPMENT_PATTERNS_V1.2.md

8. **Configuration File Synchronization**
   - 4-layer config system must stay synchronized
   - Tool → Pipeline → Application → Documentation
   - Reference: Pattern 8 in DEVELOPMENT_PATTERNS_V1.2.md

9. **Multi-Source Warning Governance**
   - Track warnings across pytest, validate_docs, Ruff, Mypy
   - Locked baseline: 312 warnings (zero regression policy)
   - Reference: Pattern 9 in DEVELOPMENT_PATTERNS_V1.2.md

10. **Property-Based Testing with Hypothesis**
    - Test mathematical invariants with generated inputs
    - 100+ cases per property
    - Reference: Pattern 10 in DEVELOPMENT_PATTERNS_V1.2.md

---

## 📑 Document Cohesion & Consistency

**⚠️ COMPLETE REFERENCE:** See `docs/utility/DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md` for comprehensive workflow documentation.

This section provides critical principles for maintaining documentation consistency. For full update cascade rules, validation checklists, and common update patterns, see the complete guide.

### Key Principles

**The Problem:** When you add a requirement, ADR, or complete a task, **multiple documents need updating**. Miss one → documentation drift → bugs and confusion.

**The Solution:** Follow the **Update Cascade Rules** (documented in DOCUMENTATION_WORKFLOW_GUIDE):

1. **Adding Requirements** → Update MASTER_REQUIREMENTS, REQUIREMENT_INDEX, DEVELOPMENT_PHASES, and MASTER_INDEX
2. **Adding ADRs** → Update ARCHITECTURE_DECISIONS, ADR_INDEX, related requirements, and MASTER_INDEX
3. **Creating Supplementary Specs** → Reference in MASTER_REQUIREMENTS/ARCHITECTURE_DECISIONS, add to MASTER_INDEX
4. **Renaming/Moving Documents** → Use `git mv`, update ALL references, update MASTER_INDEX
5. **Completing Phase Tasks** → Mark complete in DEVELOPMENT_PHASES, update requirement statuses, update indexes
6. **Planning Future Work** → Add to DEVELOPMENT_PHASES, create REQs/ADRs if needed, update indexes

### Todo List Best Practices

**⚠️ CRITICAL:** When creating new requirements or ADRs, create **SEPARATE todo items** for EACH location:

**✅ CORRECT:**
```markdown
Creating REQ-TEST-012 through REQ-TEST-019:
- [ ] Create in TEST_REQUIREMENTS_COMPREHENSIVE
- [ ] Add to MASTER_REQUIREMENTS (V2.15→V2.16)
- [ ] Add to REQUIREMENT_INDEX (113→121)
- [ ] Update MASTER_INDEX (2 entries)
- [ ] Update cross-references (find V2.15 refs)
```

**❌ WRONG:**
```markdown
- [ ] Create REQ-TEST-012 through REQ-TEST-019
```

**Why:** Single todo creates false completion. Phase 1.5 lesson: Marked todo complete after creating spec, nearly forgot MASTER_REQUIREMENTS + REQUIREMENT_INDEX updates. Only caught by user question.

**Multi-Layer Defense:**
1. **Layer 1 (Best):** Granular todos prevent forgetting
2. **Layer 2:** User/reviewer questions catch oversights
3. **Layer 3:** Pre-commit validation catches orphaned requirements

**Full templates and examples:** DOCUMENTATION_WORKFLOW_GUIDE Section "Todo List Best Practices"

### Status Field Standards

Use consistent status indicators:
- **🔵 Planned** - Documented but not started
- **🟡 In Progress** - Currently being worked on
- **✅ Complete** - Implemented and tested
- **⏸️ Paused** - Blocked or deferred
- **❌ Rejected** - Considered but decided against
- **📦 Archived** - Superseded

### Before Committing Documentation Changes

Run this **validation checklist**:

1. ✅ **Quick Checks** (2 min) - Cross-references valid? Version numbers consistent? MASTER_INDEX accurate?
2. ✅ **Requirement Consistency** (5 min) - Requirements in both MASTER_REQUIREMENTS and REQUIREMENT_INDEX?
3. ✅ **ADR Consistency** (5 min) - ADRs in both ARCHITECTURE_DECISIONS and ADR_INDEX? Sequentially numbered?
4. ✅ **Supplementary Spec Consistency** (5 min) - All specs referenced? In MASTER_INDEX?

**Validation Script:** `python scripts/validate_doc_consistency.py` (see DOCUMENTATION_WORKFLOW_GUIDE for template)

**Key Principle:** Documentation is code. Treat it with the same rigor as your Python code. Every change must maintain consistency across the entire documentation set.

**Full Reference:** `docs/utility/DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md` for complete workflows, examples, and validation templates.

---

## 📚 Documentation Structure

### Quick Navigation

**Need project context?**
- **START HERE:** `CLAUDE.md` (this file)

**Need recent updates?**
- `SESSION_HANDOFF.md`

**Need requirements?**
- `docs/foundation/MASTER_REQUIREMENTS_V2.10.md`
- `docs/foundation/REQUIREMENT_INDEX.md`

**Need architecture decisions?**
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.9.md`
- `docs/foundation/ADR_INDEX.md`

**Need phase information?**
- `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

**Need implementation details?**
- Database: `docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md`
- API: `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md`
- Versioning: `docs/guides/VERSIONING_GUIDE_V1.0.md`
- Trailing Stops: `docs/guides/TRAILING_STOP_GUIDE_V1.0.md`
- Position Management: `docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md`

**Need to find any document?**
- `docs/foundation/MASTER_INDEX_V2.8.md`

### Foundation Documents (Authoritative)

**Location:** `docs/foundation/`

1. **MASTER_INDEX_V2.8.md** - Complete document inventory
2. **MASTER_REQUIREMENTS_V2.10.md** - All requirements with REQ IDs
3. **ARCHITECTURE_DECISIONS_V2.9.md** - All ADRs (001-052)
4. **PROJECT_OVERVIEW_V1.3.md** - System architecture
5. **DEVELOPMENT_PHASES_V1.4.md** - Roadmap and phases
6. **REQUIREMENT_INDEX.md** - Searchable requirement catalog
7. **ADR_INDEX.md** - Searchable ADR catalog
8. **GLOSSARY.md** - Terminology reference

### Implementation Guides

**Location:** `docs/guides/`

1. **CONFIGURATION_GUIDE_V3.1.md** - YAML configuration reference (START HERE)
2. **VERSIONING_GUIDE_V1.0.md** - Strategy/model versioning
3. **TRAILING_STOP_GUIDE_V1.0.md** - Trailing stop implementation
4. **POSITION_MANAGEMENT_GUIDE_V1.0.md** - Position lifecycle
5. **POSTGRESQL_SETUP_GUIDE.md** - Database setup (Windows/Linux/Mac)

### API & Integration

**Location:** `docs/api-integration/`

1. **API_INTEGRATION_GUIDE_V2.0.md** - Kalshi/ESPN/Balldontlie APIs
2. **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md** ⚠️ **CRITICAL - PRINT THIS**

### Database

**Location:** `docs/database/`

1. **DATABASE_SCHEMA_SUMMARY_V1.7.md** - Complete schema (25 tables)
2. **DATABASE_TABLES_REFERENCE.md** - Quick lookup

### Process & Utility

**Location:** `docs/utility/`

1. **Handoff_Protocol_V1.1.md** - Phase completion (8-step assessment)
2. **SECURITY_REVIEW_CHECKLIST.md** - Pre-commit security checks
3. **VERSION_HEADERS_GUIDE_V2.1.md** - Document versioning

---

## 🔧 Common Tasks

### Task 1: Implement New Feature

**Example: Add Kalshi API client**

```python
"""
Kalshi API Client

Handles authentication, rate limiting, and API requests.
ALL prices parsed as Decimal from *_dollars fields.

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related ADR: ADR-005 (RSA-PSS Authentication)
Related REQ: REQ-API-001 (Kalshi API Integration)
"""
from decimal import Decimal
import os
from typing import Dict
import requests

class KalshiClient:
    """Kalshi API client with RSA-PSS authentication."""

    def __init__(self):
        # ✅ Load from environment
        self.api_key = os.getenv('KALSHI_API_KEY')
        self.api_secret = os.getenv('KALSHI_API_SECRET')
        self.base_url = os.getenv('KALSHI_BASE_URL')

        if not all([self.api_key, self.api_secret, self.base_url]):
            raise ValueError("Kalshi credentials not found")

    def get_balance(self) -> Decimal:
        """Fetch account balance.

        Returns:
            Account balance as Decimal

        Raises:
            requests.HTTPError: If API request fails
        """
        response = self._make_request('/portfolio/balance')
        # ✅ Parse as Decimal
        return Decimal(str(response['balance_dollars']))
```

**Create tests:**
```python
# tests/test_kalshi_client.py
import pytest
from decimal import Decimal
from api_connectors.kalshi_client import KalshiClient

def test_get_balance_returns_decimal(mock_kalshi_api):
    """Verify balance is Decimal, not float."""
    client = KalshiClient()
    balance = client.get_balance()

    assert isinstance(balance, Decimal)
    assert balance == Decimal("1234.5678")
```

**Update documentation:**
1. Mark REQ-API-001 as complete
2. Update REQUIREMENT_INDEX
3. Update DEVELOPMENT_PHASES tasks
4. Update SESSION_HANDOFF

**Run tests:**
```bash
python -m pytest tests/test_kalshi_client.py -v
python -m pytest tests/ --cov=api_connectors
```

---

### Task 6: Validate Implementation Against Requirements (MANDATORY)

**WHY:** Prevent "implementation complete but requirements not met" gaps. This validation should run BEFORE marking any feature complete.

**When to run:**
- Before marking any REQ as ✅ Complete
- Before marking any phase deliverable as done
- After implementing significant functionality (API client, database layer, trading logic)

**Step 1: Identify Relevant Requirements**

```bash
# Find all requirements for current phase
grep "Phase: 1" docs/foundation/MASTER_REQUIREMENTS*.md

# Find all ADRs for current phase
grep "Phase:** 1" docs/foundation/ARCHITECTURE_DECISIONS*.md
```

**Step 2: Validate Each Requirement**

For each REQ-XXX-NNN in scope:

```markdown
**Validation Checklist:**

- [ ] **Requirement exists in code?**
  - Find implementing function/class
  - Verify functionality matches requirement description

- [ ] **Tests exist for requirement?**
  - Search tests for requirement coverage
  - Verify all requirement scenarios tested

- [ ] **ADRs followed?**
  - Check implementation matches architectural decisions
  - Verify no deviations without documented reason

- [ ] **Documentation updated?**
  - Requirement marked complete in MASTER_REQUIREMENTS
  - REQUIREMENT_INDEX updated
  - DEVELOPMENT_PHASES task marked complete
```

**Step 3: Run Validation Commands**

```bash
# 1. Check requirement coverage
python scripts/validate_requirements_coverage.py  # Phase 0.8 future task

# 2. Verify all tests passing
python -m pytest tests/ -v

# 3. Check coverage threshold
python -m pytest tests/ --cov=api_connectors --cov-fail-under=80

# 4. Verify type safety
python -m mypy api_connectors/

# 5. Check code quality
python -m ruff check .
```

**Example: Validating REQ-API-001 (Kalshi API Integration)**

```markdown
**REQ-API-001 Validation:**

✅ **Implementation exists:**
- File: api_connectors/kalshi_client.py
- Class: KalshiClient
- Methods: get_markets(), get_positions(), get_balance(), etc.

✅ **Tests exist:**
- File: tests/unit/api_connectors/test_kalshi_client.py
- Coverage: 27/27 tests passing (87.24% coverage)
- Scenarios tested:
  - [x] RSA-PSS authentication
  - [x] Rate limiting (100 req/min)
  - [x] Exponential backoff
  - [x] Decimal price conversion
  - [x] Error handling (4xx, 5xx)
  - [x] TypedDict return types

✅ **ADRs followed:**
- ADR-002: Decimal precision ✅ (all prices use Decimal)
- ADR-047: RSA-PSS authentication ✅ (implemented in kalshi_auth.py)
- ADR-048: Rate limiting ✅ (100 req/min with token bucket)
- ADR-049: Exponential backoff ✅ (max 3 retries, 1s/2s/4s delays)
- ADR-050: TypedDict responses ✅ (17 TypedDict classes in types.py)

✅ **Documentation updated:**
- MASTER_REQUIREMENTS V2.10: REQ-API-001 status = ✅ Complete
- REQUIREMENT_INDEX: REQ-API-001 status = ✅ Complete
- DEVELOPMENT_PHASES V1.4: Phase 1 API tasks marked complete

**RESULT:** REQ-API-001 VALIDATED ✅
```

**Step 4: Identify Gaps**

If validation finds gaps:

```markdown
**Gap Identified:**
- **Requirement:** REQ-API-007 (Retry-After header handling)
- **Status:** Implemented but not tested
- **Gap:** No test for 429 error with Retry-After header
- **Action:** Add test_handle_429_with_retry_after() to test suite
- **Priority:** 🔴 Critical (must fix before marking complete)
```

**Step 5: Document Validation**

Add to SESSION_HANDOFF.md:

```markdown
## Implementation Validation

**Requirements Validated:**
- ✅ REQ-API-001: Kalshi API Integration
- ✅ REQ-API-002: RSA-PSS Authentication
- ✅ REQ-API-003: Rate Limiting
- ⚠️ REQ-API-007: Retry-After handling (test gap identified)

**Gaps Found:** 1 (REQ-API-007 test coverage)
**Gaps Resolved:** 1 (added test_handle_429_with_retry_after)

**Validation Status:** ✅ PASS (all requirements met)
```

**Reference:**
- MASTER_REQUIREMENTS_V2.10.md - All requirements
- ARCHITECTURE_DECISIONS_V2.10.md - All ADRs
- DEVELOPMENT_PHASES_V1.4.md - Phase deliverables
- Phase Completion Protocol (Section 9) - 8-step assessment

**Automation (Future - Phase 0.8):**

Create `scripts/validate_requirements_coverage.py` to automate validation:

```python
"""
Validate all requirements have implementation and tests.

Checks:
1. Each REQ-XXX-NNN in MASTER_REQUIREMENTS has:
   - Implementation (code file reference)
   - Tests (test file with coverage)
   - Documentation (marked complete when done)
"""
```

---

## 🔒 Security Guidelines

### Pre-Commit Security Scan (MANDATORY)

**Run BEFORE EVERY COMMIT:**

```bash
# 1. Search for hardcoded credentials
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'

# 2. Check for connection strings with passwords
git grep -E "(postgres://|mysql://).*:.*@"

# 3. Verify .env not staged
git diff --cached --name-only | grep "\.env$"

# 4. Run tests
python -m pytest tests/ -v
```

**If ANY fail, DO NOT COMMIT until fixed.**

### What NEVER to Commit

**Files:**
- `.env` (only `.env.template` allowed)
- `_keys/*` (private keys, certificates)
- `*.pem`, `*.key`, `*.p12`, `*.pfx`
- `*.dump`, `*.sql.bak` (database backups with data)

**Patterns:**
```python
# ❌ NEVER
password = "mypassword"
api_key = "sk_live_abc123"
```

### Security Checklist Document

**Full checklist:** `docs/utility/SECURITY_REVIEW_CHECKLIST.md`

---

## 🎯 Phase Completion Protocol

**At the end of EVERY phase**, run this **10-Step Assessment** (~50 minutes total):

---

### Step 1: Deliverable Completeness (10 min)

- [ ] All planned documents for phase created?
- [ ] All planned code modules implemented?
- [ ] All documents have correct version headers?
- [ ] All documents have correct filenames (with versions)?
- [ ] All cross-references working?
- [ ] All code examples tested?
- [ ] All tests written and passing?
- [ ] **All modules have coverage targets AND met targets?**
  ```bash
  # Run coverage report and compare to documented targets
  python -m pytest tests/ --cov=. --cov-report=term

  # Example validation:
  # - kalshi_client.py: 93.19% (target 90%+) ✅ PASS
  # - config_loader.py: 98.97% (target 85%+) ✅ PASS
  # - crud_operations.py: 91.26% (target 87%+) ✅ PASS
  # - connection.py: 81.44% (target 80%+) ✅ PASS
  # - logger.py: 87.84% (target 80%+) ✅ PASS
  #
  # If ANY module below target → NOT COMPLETE
  ```

**Output:** List of deliverables with ✅/❌ status + coverage verification report

---

### Step 2: Internal Consistency (5 min)

- [ ] Terminology consistent across all docs? (check GLOSSARY)
- [ ] Technical details match? (e.g., decimal pricing everywhere)
- [ ] Design decisions aligned?
- [ ] No contradictions between documents?
- [ ] Version numbers logical and sequential?
- [ ] Requirements and implementation match?

**Output:** List of any inconsistencies found + resolution plan

---

### Step 3: Dependency Verification (5 min)

- [ ] All document cross-references valid?
- [ ] All external dependencies identified and documented?
- [ ] Next phase blockers identified?
- [ ] API contracts documented?
- [ ] Data flow diagrams current?
- [ ] All imports in code resolve correctly?

**Output:** Dependency map with any missing items flagged

---

### Step 4: Quality Standards (5 min)

- [ ] Spell check completed on all docs?
- [ ] Grammar check completed?
- [ ] Format consistency (headers, bullets, tables)?
- [ ] Code syntax highlighting correct in docs?
- [ ] All links working (no 404s)?
- [ ] Code follows project style (type hints, docstrings)?

**Output:** Quality checklist with pass/fail

---

### Step 5: Testing & Validation (3 min)

- [ ] All tests passing? (`pytest tests/ -v`)
- [ ] Coverage meets threshold? (>80%)
- [ ] Sample data provided where relevant?
- [ ] Configuration examples included?
- [ ] Error handling documented and tested?
- [ ] Edge cases identified and tested?

**Output:** Test summary with coverage percentage

---

### Step 6: Gaps & Risks (2 min)

- [ ] Technical debt documented?
- [ ] Known issues logged with severity?
- [ ] Future improvements identified?
- [ ] Risk mitigation strategies noted?
- [ ] Performance concerns documented?
- [ ] **Deferred tasks documented?** (see Deferred Tasks Workflow below)

**Output:** Risk register with mitigation plans

#### Deferred Tasks Workflow

**When to create a deferred tasks document:**
- Phase identified tasks that are **important but not blocking** for next phase
- Tasks would take >2 hours total implementation time
- Tasks are infrastructure/tooling improvements (not core features)

**Multi-Location Documentation Strategy:**

1. **Create detailed document in utility/**
   - Filename: `PHASE_N.N_DEFERRED_TASKS_V1.0.md`
   - Include: Task IDs (DEF-001, etc.), rationale, implementation details, timeline, success metrics
   - Example: `docs/utility/PHASE_0.7_DEFERRED_TASKS_V1.0.md`

2. **Add summary to DEVELOPMENT_PHASES**
   - Add "Deferred Tasks" subsection at end of phase (before phase separator)
   - List high-priority vs. low-priority tasks
   - Include task IDs, time estimates, rationale
   - Reference detailed document: `📋 Detailed Documentation: docs/utility/PHASE_N.N_DEFERRED_TASKS_V1.0.md`

3. **Update MASTER_INDEX**
   - Add entry for deferred tasks document
   - Category: Utility document

4. **MANDATORY: Create requirements for critical infrastructure** ⚠️
   - **Critical infrastructure MUST have formal REQ-CICD-*/REQ-TOOL-* requirements**
   - Examples requiring REQs: pre-commit hooks, pre-push hooks, branch protection, CI/CD pipelines
   - Documentation/process tasks do NOT need REQs (DEF-XXX only)
   - **Decision Tree:** See `PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md` Step 6 for complete decision tree covering:
     - Critical Infrastructure → REQ-CICD-XXX or REQ-TOOL-XXX
     - Database Features → REQ-DB-XXX
     - API Integration → REQ-API-XXX
     - Testing Infrastructure → REQ-TEST-XXX
     - Security Enhancements → REQ-SEC-XXX
     - Documentation/Process → No REQ needed
   - **Why:** Audit traceability, consistency enforcement, prevents gaps (Phase 1 lesson learned)

**Deferred Task Numbering Convention:**
- `DEF-001`, `DEF-002`, etc. (sequential within phase)
- Phase-specific (Phase 0.7 deferred tasks: DEF-001 through DEF-007)

**Priority Levels:**
- 🟡 **High:** Should be implemented in next phase (Phase 0.8)
- 🟢 **Medium:** Implement within 2-3 phases
- 🔵 **Low:** Nice-to-have, implement as time allows

**Example Deferred Tasks:**
- Pre-commit hooks (prevents CI failures locally)
- Pre-push hooks (catches issues before CI)
- Branch protection rules (enforces PR workflow)
- Line ending edge cases (cosmetic CI issues)
- Additional security checks (non-blocking)

**When NOT to defer:**
- Blocking issues (prevents next phase from starting)
- Security vulnerabilities (must fix immediately)
- Data corruption risks (must fix immediately)
- Core feature requirements (belongs in phase, not deferred)

---

### Step 7: AI Code Review Analysis (10 min)

**Purpose:** Analyze Claude Code's PR review comments from phase to identify improvements and learning opportunities

**Quick Checklist:**
- [ ] **⚠️ VERIFY PR COVERAGE FIRST** - Identify first/last PR numbers for phase, ensure ALL PRs analyzed (no gaps)
  - Phase 1 lesson learned: Only analyzed 5/26 PRs (19% coverage) → missed 80% of AI feedback
  - **Red flag:** Analyzing only recent PRs (#22-#27) when phase started at PR #2 (recency bias)
  - Must document justification for any skipped PRs (e.g., merged before phase, documentation-only)
- [ ] Collect AI review comments from all phase PRs
- [ ] Categorize by priority (🔴 Critical, 🟡 High, 🟢 Medium, 🔵 Low)
- [ ] Triage actions (Fix immediately, Defer, Reject with rationale)
- [ ] Document decisions and identify patterns

**How to verify PR coverage:**
```bash
# List ALL PRs from phase start date
gh pr list --state merged --search "merged:>=2025-10-28" --limit 50 --json number,title,mergedAt

# Identify range: First PR = #2, Last PR = #28 → Must analyze ALL 27 PRs
# Document any skipped PRs with justification
```

**Output:** AI review triage report documenting suggestions (implemented/deferred/rejected) with rationale

**Full details:** `docs/utility/PHASE_COMPLETION_ASSESSMENT_PROTOCOL_V1.0.md` Step 7 (includes PR coverage verification checklist)

---

### Step 8: Archive & Version Management (5 min)

- [ ] Old document versions archived to `_archive/`?
- [ ] MASTER_INDEX updated with new versions?
- [ ] REQUIREMENT_INDEX updated (if requirements changed)?
- [ ] ADR_INDEX updated (if ADRs added)?
- [ ] DEVELOPMENT_PHASES updated (tasks marked complete)?
- [ ] All version numbers incremented correctly?

**Output:** Version audit report

---

### Step 9: Security Review (5 min) ⚠️ **CRITICAL**

**Hardcoded Credentials Check:**
```bash
# Search for hardcoded passwords, API keys, tokens
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' '*.sql'

# Search for connection strings with embedded passwords
git grep -E "(postgres://|mysql://).*:.*@" -- '*'
```

**Expected Result:** No matches (or only `os.getenv()` lines)

**Manual Checklist:**
- [ ] No hardcoded passwords in source code?
- [ ] No API keys in configuration files?
- [ ] All credentials loaded from environment variables?
- [ ] `.env` file in `.gitignore` (not committed)?
- [ ] `_keys/` folder in `.gitignore`?
- [ ] No sensitive files in git history?
- [ ] All scripts use `os.getenv()` for credentials?

**If ANY security issues found:**
1. ⚠️ **STOP immediately** - Do NOT proceed to next phase
2. Fix all security issues
3. Rotate compromised credentials
4. Re-run security scan
5. Update `.gitignore` if needed

**Output:** Security scan report with ✅ PASS or ❌ FAIL + remediation

---

### Step 10: Performance Profiling (Phase 5+ Only) ⚡ **OPTIONAL**

**When to profile:**
- **Phase 5+ ONLY:** Trading execution, order walking, position monitoring
- **NOT Phase 1-4:** Infrastructure, data processing, API integration

**Why defer optimization:**
- "Make it work, make it right, make it fast" - in that order
- Premature optimization wastes time on wrong bottlenecks
- Phase 1-4 focus: Correctness, type safety, test coverage
- Phase 5+ focus: Speed (when trading performance matters)

**Profiling Tools:**
```bash
# 1. Profile critical trading paths with cProfile
python -m cProfile -o profile.stats main.py execute-trades

# 2. Visualize with snakeviz (install: pip install snakeviz)
snakeviz profile.stats

# 3. Look for hotspots (functions taking >10% total time)
python -m pstats profile.stats
>>> sort time
>>> stats 20
```

**Only optimize if:**
- [ ] Bottleneck identified (single function >10% total execution time)
- [ ] Impacts trading performance (missed opportunities, slow exits)
- [ ] Simple optimization available (caching, vectorization, batch processing)
- [ ] Optimization doesn't sacrifice correctness or readability

**Common optimizations (Phase 5+):**
- **Caching:** Memoize expensive calculations (Elo ratings, model features)
- **Vectorization:** Use NumPy/Pandas for batch operations
- **Database:** Add indexes on frequently queried columns
- **API:** Batch requests instead of individual calls
- **WebSocket:** Use for live data instead of polling

**What NOT to optimize:**
- Database connection pooling (Phase 1-4: single connection is fine)
- API rate limiting (Phase 1-4: 100 req/min is sufficient)
- Code formatting/linting (zero performance impact)
- Test execution time (unless >5 minutes)

**Example Decision Matrix:**

| Scenario | Phase 1-4 | Phase 5+ | Optimize? |
|----------|-----------|----------|-----------|
| API request takes 200ms | ✅ OK | ✅ OK | ❌ No - network latency normal |
| Database query takes 50ms | ✅ OK | ✅ OK | ❌ No - reasonable for complex query |
| Model prediction takes 2s | ✅ OK | ⚠️ Slow | ✅ Yes - could miss trade opportunities |
| Order execution takes 500ms | N/A | ⚠️ Slow | ✅ Yes - price may move in 500ms |
| Position check takes 100ms | ✅ OK | ⚠️ Slow | ✅ Yes - runs every second in Phase 5 |

**Output:** Performance profile report with optimization recommendations (Phase 5+ only)

**Reference:**
- ADR-TBD (Performance Optimization Strategy) - Phase 5+
- "Premature optimization is the root of all evil" - Donald Knuth

---

### Assessment Output

**Create:** `docs/phase-completion/PHASE_N_COMPLETION_REPORT.md`

**Template:**
```markdown
# Phase N Completion Report

**Phase:** Phase N - [Name]
**Assessment Date:** YYYY-MM-DD
**Assessed By:** [Name/Claude]
**Status:** ✅ PASS / ⚠️ PASS WITH ISSUES / ❌ FAIL

---

## Assessment Summary

| Step | Status | Issues | Notes |
|------|--------|--------|-------|
| 1. Deliverable Completeness | ✅ | 0 | All deliverables complete |
| 2. Internal Consistency | ✅ | 0 | No contradictions found |
| 3. Dependency Verification | ✅ | 0 | All dependencies documented |
| 4. Quality Standards | ✅ | 0 | Quality checks passed |
| 5. Testing & Validation | ✅ | 0 | 66/66 tests passing, 87% coverage |
| 6. Gaps & Risks | ✅ | 2 | 2 minor risks documented |
| 7. AI Code Review Analysis | ✅ | 0 | 5 suggestions triaged |
| 8. Archive & Version Management | ✅ | 0 | All versions updated |
| 9. Security Review | ✅ | 0 | No credentials in code |

---

## Detailed Findings

### Step 1: Deliverable Completeness
[Details...]

### Step 2: Internal Consistency
[Details...]

[... continue for all 9 steps ...]

---

## Known Issues & Risks

1. **[Issue name]** (Severity: Low/Medium/High)
   - **Description:** [...]
   - **Impact:** [...]
   - **Mitigation:** [...]

---

## Recommendation

☐ **APPROVE** - Proceed to next phase
☐ **APPROVE WITH CONDITIONS** - Proceed with noted issues tracked
☐ **REJECT** - Address critical issues before proceeding

**Next Phase Prerequisites:**
- [List any prerequisites for starting next phase]

---

**Sign-off:** [Name] - [Date]
```

---

### Quick Completion Checklist

**Use this for rapid end-of-session validation (not full phase completion):**

- [ ] Tests passing?
- [ ] Security scan clean?
- [ ] SESSION_HANDOFF.md updated?
- [ ] CLAUDE.md updated (if major progress)?
- [ ] All new files committed?
- [ ] No hardcoded credentials?

**Time:** ~5 minutes

---

## 📎 Quick Reference

### Essential Reading Order

**Every Session:**
1. `CLAUDE.md` (this file)
2. `SESSION_HANDOFF.md`

**When Starting Phase:**
3. `docs/foundation/DEVELOPMENT_PHASES_V1.4.md`

**When Implementing:**
4. Relevant guides from `docs/guides/`
5. Relevant specs from `docs/supplementary/`

### Key Commands

```bash
# Validation & Testing (Phase 0.6c+0.7c)
./scripts/validate_all.sh      # Complete validation (60s) - run before commits
./scripts/validate_quick.sh    # Fast validation (3s) - run during development
./scripts/test_full.sh         # All tests + coverage (30s)
./scripts/test_fast.sh         # Unit tests only (5s)

# Template Enforcement (Phase 0.7c)
python scripts/validate_code_quality.py    # CODE_REVIEW_TEMPLATE enforcement (≥80% coverage, REQ tests)
python scripts/validate_security_patterns.py  # SECURITY_REVIEW_CHECKLIST enforcement (API auth, secrets)

# Code Quality
ruff check .           # Linting
ruff check --fix .     # Linting with auto-fix
ruff format .          # Code formatting
mypy .                 # Type checking

# Documentation
python scripts/validate_docs.py  # Doc consistency validation
python scripts/fix_docs.py       # Auto-fix doc issues

# Testing (direct pytest)
pytest tests/ -v                              # All tests
pytest tests/unit/ -v                         # Unit tests only
pytest --cov=. --cov-report=html             # With coverage

# Database
python scripts/test_db_connection.py  # Test connection

# Security
git grep -E "password\s*=" -- '*.py'  # Scan for hardcoded credentials
```

### Critical References

**Decimal Precision:**
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`
- ADR-002 in ARCHITECTURE_DECISIONS

**Versioning:**
- `docs/guides/VERSIONING_GUIDE_V1.0.md`
- ADR-018, ADR-019, ADR-020 in ARCHITECTURE_DECISIONS

**Security:**
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md`
- Pre-commit scan commands above

**Database:**
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md`
- `docs/database/DATABASE_TABLES_REFERENCE.md`

**API Integration:**
- `docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md`

**Validation & Testing (Phase 0.6c):**
- `docs/foundation/TESTING_STRATEGY_V2.0.md` - Comprehensive testing infrastructure
- `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Code quality & doc validation
- `pyproject.toml` - Ruff, mypy, pytest configuration
- `scripts/validate_all.sh` - Complete validation suite

**Development Patterns:**
- `docs/guides/DEVELOPMENT_PATTERNS_V1.2.md` - Complete guide to 10 critical patterns with code examples
- Section 4 above: Pattern Quick Reference (condensed)
- Patterns: Decimal Precision, Versioning, Trade Attribution, Security, Cross-Platform, TypedDict, Educational Docstrings, Config Sync, Warning Governance, Property-Based Testing

**Document Consistency:**
- `docs/utility/DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md` - Complete workflow guide for documentation maintenance
- Section 5 above: Document Cohesion & Consistency (condensed)
- Update Cascade Rules (6 rules), Validation Checklists, Common Update Patterns

**Code Review & Quality Assurance:**
- `docs/utility/CODE_REVIEW_TEMPLATE_V1.0.md` - Universal code review checklist (7 categories: Requirements, Testing, Quality, Security, Documentation, Performance, Error Handling)
- `docs/utility/INFRASTRUCTURE_REVIEW_TEMPLATE_V1.0.md` - Infrastructure and DevOps review template (7 categories: CI/CD, Deployment, Scalability, Monitoring, Disaster Recovery, Security Infrastructure, Compliance)
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md` V1.1 - Enhanced security review with API security, data protection, compliance, and incident response
- All templates reference `docs/foundation/DEVELOPMENT_PHILOSOPHY_V1.1.md` for core principles

---

## 🚨 Common Mistakes to Avoid

### ❌ NEVER Do These

1. **Use float for prices:** `price = 0.4975` ❌
2. **Modify immutable configs:** `strategy.config = {...}` ❌
3. **Query without row_current_ind:** `query(Position).all()` ❌
4. **Hardcode credentials:** `password = "..."` ❌
5. **Skip tests:** `git commit --no-verify` ❌
6. **Commit without security scan** ❌
7. **Update one doc without updating related docs** ❌
8. **Add requirement without updating REQUIREMENT_INDEX** ❌
9. **Add ADR without updating ADR_INDEX** ❌
10. **Rename file without updating all references** ❌
11. **Use float in YAML configs:** `min_edge: 0.05` ❌ (use string: `"0.05"`)
12. **Update one config layer without updating all 4 layers** ❌ (causes config drift)

### ✅ ALWAYS Do These

1. **Use Decimal for prices:** `price = Decimal("0.4975")` ✅
2. **Create new version for config changes:** `v1.1 = Strategy(...)` ✅
3. **Filter by row_current_ind:** `filter(row_current_ind == True)` ✅
4. **Use environment variables:** `os.getenv('PASSWORD')` ✅
5. **Run tests before commit:** `pytest tests/ -v` ✅
6. **Run security scan before commit** ✅
7. **Follow Update Cascade Rules when changing docs** ✅
8. **Update REQUIREMENT_INDEX when adding REQ** ✅
9. **Update ADR_INDEX when adding ADR** ✅
10. **Update all references when renaming files** ✅
11. **Use string format in YAML configs:** `min_edge: "0.05"` ✅ (prevents float contamination)
12. **Update all 4 config layers together atomically** ✅ (prevents config drift)

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.19 | 2025-11-15 | **Issue Tracking Protocol** - Added standardized issue closure protocol to "During Development" section; Created scripts/reconcile_issue_tracking.sh (270 lines) to verify GitHub issues match documentation status; Three-method approach (PR auto-close, manual closure, reconciliation check); Prevents "I thought we completed that" confusion; Maintains dual-tracking consistency (GitHub + documentation); Total addition: ~320 lines |
| 1.18 | 2025-11-15 | **CLAUDE.md Size Reduction - Section 3 (80%)** - Reduced Section 3 from ~700 lines to ~140 lines; Extracted SESSION_WORKFLOW_GUIDE_V1.0.md; Added "When to Read the Complete Guide" section; Context budget optimization: ~7,000 tokens freed |
| 1.17 | 2025-11-15 | **Multi-Session Coordination** - Added comprehensive 7-step protocol for running multiple Claude Code sessions simultaneously (~150 lines); Session-specific branch naming (feature/X-sessionA); Foundation document coordination (one session at a time); Prevention strategies (git stash vs git reset --hard); Conflict resolution for version collisions; Communication via draft PRs; Real-world example from 2025-11-15 multi-session work |
| 1.16 | 2025-11-13 | **CLAUDE.md Size Reduction (48.7%)** - Reduced from 3,723 lines to 1,909 lines (~1,814 line reduction); Created DEVELOPMENT_PATTERNS_V1.2.md (1,200+ lines) extracting all 10 critical patterns; Created DOCUMENTATION_WORKFLOW_GUIDE_V1.0.md (850+ lines) extracting document cohesion workflows; Replaced detailed sections with concise summaries + references; Context budget optimization: ~45,000 tokens → ~23,000 tokens (~50% reduction) |
| 1.15 | 2025-11-09 | Automated Template Enforcement (Phase 0.7c) - Created validate_code_quality.py (314 lines) and validate_security_patterns.py (413 lines); Updated pre-commit hooks (2 new hooks: code-review-basics, decimal-precision-check); Updated pre-push hooks (added steps 6/7 and 7/7 for template enforcement); Defense in Depth architecture: pre-commit (~2-5s) → pre-push (~60-90s) → CI/CD (~2-5min); Total addition: ~750 lines of automated enforcement infrastructure |
| 1.14 | 2025-11-09 | Created CODE_REVIEW_TEMPLATE_V1.0.md (484 lines, 7-category universal checklist), INFRASTRUCTURE_REVIEW_TEMPLATE_V1.0.md (600 lines, 7-category DevOps review), enhanced SECURITY_REVIEW_CHECKLIST.md V1.0→V1.1 (600 lines, added 4 sections); all templates reference DEVELOPMENT_PHILOSOPHY_V1.1.md with specific section callouts; added Code Review & Quality Assurance section to Critical References; consolidates scattered guidance into standardized review infrastructure |
| 1.13 | 2025-11-09 | Added Section 3.1: Recovering from Interrupted Session with 4-step recovery workflow (git status check, recent work review, test validation, workflow resumption); includes common recovery scenarios table; provides detailed example from 2025-11-09 context limit interruption during Phase 1.5 integration tests |
| 1.8 | 2025-11-07 | Implemented DEF-002 (Pre-Push Hooks Setup); created .git/hooks/pre-push with 4 validation steps (quick validation, unit tests, full type checking, security scan); added "Pre-Push Hooks" section; second layer of defense with tests; reduces CI failures 80-90% |
| 1.7 | 2025-11-07 | Implemented DEF-001 (Pre-Commit Hooks Setup); installed pre-commit framework v4.0.1; updated "Before Committing Code" section with automatic hooks workflow (12 checks: Ruff, Mypy, security, formatting, line endings); auto-fixes formatting/whitespace; reduces CI failures 60-70% |
| 1.6 | 2025-11-05 | Changed session archiving from docs/sessions/ (committed) to _sessions/ (local-only); added docs/sessions/ to .gitignore; updated Section 3 Step 0 workflow; prevents repository bloat while preserving local context |
| 1.5 | 2025-11-05 | Created docs/guides/ folder and moved 5 implementation guides (CONFIGURATION, VERSIONING, TRAILING_STOP, POSITION_MANAGEMENT, POSTGRESQL_SETUP); updated Section 6 and MASTER_INDEX V2.8→V2.9; aligns docs structure with Section 6 references; addresses discoverability issue |
| 1.4 | 2025-11-05 | Added session history archiving workflow (Section 3 Step 0); extracted 7 historical SESSION_HANDOFF.md versions from git history to docs/sessions/; preserves full session history with date-stamped archives |
| 1.3 | 2025-11-04 | Updated all version references: MASTER_REQUIREMENTS V2.8→V2.10, ARCHITECTURE_DECISIONS V2.7→V2.9, MASTER_INDEX V2.6→V2.8; reflects Phase 1 API best practices documentation (ADR-047 through ADR-052, REQ-API-007, REQ-OBSERV-001, REQ-SEC-009, REQ-VALIDATION-004) |
| 1.2 | 2025-10-31 | Added Deferred Tasks Workflow to Phase Completion Protocol; multi-location documentation strategy; updated for Phase 0.7 completion; updated references to DEVELOPMENT_PHASES V1.4 |
| 1.1 | 2025-10-29 | Added Rule 6: Planning Future Work; Status Field Usage Standards; validation commands to Quick Reference; updated Phase Completion Protocol with validate_all.sh; Phase 0.6c completion updates |
| 1.0 | 2025-10-28 | Initial creation - Streamlined handoff workflow, added comprehensive Document Cohesion & Consistency section, removed PROJECT_STATUS and DOCUMENT_MAINTENANCE_LOG overhead, fixed API_INTEGRATION_GUIDE reference to V2.0 |

---

## 📋 Summary: Your Session Workflow

**Start Session (5 min):**
1. Read `CLAUDE.md` (this file)
2. Read `SESSION_HANDOFF.md`
3. Create TodoList

**During Session:**
1. Follow critical patterns (Decimal, Versioning, Security)
2. Follow Document Cohesion rules when updating docs
3. Write tests (>80% coverage)
4. Update todos frequently

**Before Commit:**
1. Run tests: `pytest tests/ -v`
2. Run security scan: `git grep "password\s*=" '*.py'`
3. **Run consistency validation if docs changed**
4. Check coverage: `pytest --cov`

**End Session (10 min):**
0. Archive `SESSION_HANDOFF.md` to `docs/sessions/` (preserves history)
1. Update `SESSION_HANDOFF.md`
2. Commit with descriptive message (list all doc updates)
3. Push to remote

**Phase Complete:**
1. Run 8-step assessment
2. Create completion report
3. Update `CLAUDE.md` status if major changes

---

**That's it! Two files to read, clear patterns to follow, strong document cohesion discipline, comprehensive security checks. You're ready to code.**

---

**END OF CLAUDE.md V1.6**
- always use descriptive variable names
- Always document deferred tasks appropriately in requirements, architural, and project development phases documentation
