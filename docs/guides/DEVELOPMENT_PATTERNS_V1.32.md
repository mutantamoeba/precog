# Precog Development Patterns Guide

---
**Version:** 1.32
**Created:** 2025-11-13
**Last Updated:** 2026-04-13
**Purpose:** Comprehensive reference for critical development patterns used throughout the Precog project
**Target Audience:** Developers and AI assistants working on any phase of the project
**Extracted From:** CLAUDE.md V1.15 (Section: Critical Patterns, Lines 930-2027)
**Status:** ✅ Current
**Changes in V1.32:**
- **Added Pattern 65: Mock the Entry Point, Not the Terminal Constructor (ALWAYS for Factory-Constructed Objects)**
- **Added Pattern 66: Strict Exit-Code Assertions as Decay Detection (ALWAYS for CLI Tests)**
- **Added Pattern 67: `assert_called` as the Fail-Loud Invariant for Mocks (ALWAYS for patch()-Based Tests)**
- **Added Pattern 68: Preserve-X Requires X Exists (ALWAYS for Multi-Session Preservation Framing)**
- **Added Pattern 69: Post-Retrofit Cosmetic-Coverage Check (ALWAYS for Test Mock-Layer Retrofits)**
- **Added Pattern 70: Convergent-Reviewer Signal Rule (ALWAYS for Multi-Reviewer Dispatch)**
- **Added Pattern 71: Verify High-Confidence Sentinel Claims Via Code Inspection Before Acting (ALWAYS for Sentinel-Frame Findings)**
- **Added Pattern 72: Scope Correction Via Mechanical Pre-ANNOUNCE Scoping (ALWAYS for Tier 2 Dispatches)**
- Patterns 65-69 sourced from Session 50 #764 systemic scheduler CLI test retrofit (staged in `patterns_to_add_50.md`)
- Patterns 70-72 sourced from Session 51 meta-discoveries (Spock+Ripley `.envrc` convergence on PR #786; Ripley F1 T41 schedulers-audit docstring verification; Hook PR 1 scope shrink from 3 hooks to 1)
- Cross-references wired: Pattern 70 extends Pattern 58 (Triple-Reviewer Convergence) to the two-reviewer case; Pattern 65 operationalizes the #764 umbrella alongside CLAUDE.md Critical Pattern #7; Pattern 66 complements the loose-assertion ratchet hook (#808)
**Changes in V1.31:**
- **Added Pattern 52: SCD Race Retry Helper Structure (ALWAYS for SCD Retry Logic)**
- **Added Pattern 53: Race Tests Must Assert The Race Actually Fired (ALWAYS for Race Tests)**
- **Added Pattern 54: Verifier Scripts as Investigation Deliverables (ALWAYS for External API Investigation)**
- **Added Pattern 55: Fee-Aware Orderbook Edge Calculation (ALWAYS for Edge Calculations)**
- **Added Pattern 56: JSONB + Decimal Round-Trip via Custom Encoder (ALWAYS for JSONB with Decimal)**
- **Added Pattern 57: Close-by-Business-Key Inside Retry Closure (ALWAYS for SCD Retry with Surrogate Keys)**
- **Added Pattern 58: Triple-Reviewer Convergence as Structural Validation (ALWAYS for Multi-Agent Review)**
- **Added Pattern 59: Migration Round-Trip Testing on a Populated DB (ALWAYS for Non-Trivial Migrations)**
- **Added Pattern 60: AST Helper Scripts for Systematic Test Fixture Updates (MEDIUM for Cascading Signature Changes)**
- **Added Pattern 61: git push --no-verify Repeat-Use Acceptance Criteria (ALWAYS for Hook Bypass)**
- **Added Pattern 62: In-Repo Per-Migration Rationale Docs (MEDIUM for Architecturally Significant Migrations)**
- **Added Pattern 63: LATERAL Subquery for SCD Type 2 Temporal Matching (ALWAYS for Cross-Table SCD Correlation)**
- **Added Pattern 64: IS DISTINCT FROM in BEFORE UPDATE Triggers (ALWAYS for Immutability Triggers)**
- **Updated Pattern 2: Added anti-pattern warning for same-transaction read-after-write with row_current_ind filter**
- Patterns 52-55 sourced from Session 42d (SCD retry helper, race test fire assertion, verifier scripts, fee-aware edge)
- Patterns 56-57 sourced from Session 42e (JSONB Decimal serialization, business-key retry closure)
- Patterns 58-62 sourced from Session 42f (reviewer convergence, migration round-trip, AST helpers, --no-verify criteria, rationale docs)
- Patterns 63-64 sourced from Session 47 (Schema Hardening Arc C0+C1)
**Changes in V1.30:**
- **Added Pattern 47: Verify Schema Before Fixing Pattern Violations (ALWAYS for Code Review Findings)**
- **Added Pattern 48: Use dataclasses.replace() for Frozen Dataclass Updates (ALWAYS for Immutable Records)**
- **Added Pattern 49: SCD Race Condition Prevention with FOR UPDATE (ALWAYS for SCD Close→Insert)**
- **Added Pattern 50: Reverse-Engineer Strategy via Closed Trade Lifecycle (ALWAYS for External Trader Analysis)**
- All four sourced from Session 42c (S68 audit fixes + ColdMath strategy analysis)
**Changes in V1.27:**
- **Added Pattern 44: API Consumer Blast Radius (ALWAYS for API Field Name Fixes)**
- When an API field name is wrong or changes, ALL consumers of the raw API dict must be audited
- 5 consumer categories: ingestion, validation, display, types, tests
- Real-world trigger: Kalshi `_fp` suffix bug — 5 fields NULL across 7,802 snapshots, blast radius: 10+ files
- Related: S63 (spec-first), S64 (post-merge verify), S65 (test fixture staleness)
**Changes in V1.26:**
- **Updated Pattern 41: Added 7th capability — Alerts**
- Alerts promoted from implicit (buried in Reporting/Logging) to explicit production-readiness requirement
- Every production module now ships with 7 capabilities: monitoring, alerts, maintenance, logging, reporting, self-healing, scheduling
- Real-world trigger: C10 post-soak council found circuit breaker types exist but have zero trigger logic; data freshness unmonitored
**Changes in V1.25:**
- **Added Pattern 41: Production-Readiness Checklist (ALWAYS for New Modules/Features)**
- Real-world trigger: Matching module (#462) shipped with 98 tests but zero production visibility
- Every production module must include: monitoring, maintenance CLI, logging, reporting, self-healing, scheduling
- Template established by #477 (matching production-readiness): MatchReason enum, backfill, registry refresh, CLI commands
**Changes in V1.24:**
- **Added Pattern 39: Verify External API Data Before Building Parsers (ALWAYS for External Data Parsing)**
- Real-world trigger: Session 23 test fixtures showed wrong Kalshi event_ticker format, real API completely different
- Always hit the real API before building parsers — 30 seconds of verification prevents hours of wrong-direction work
- **Added Pattern 40: Use execute_values Over executemany for Batch Upserts (ALWAYS for Batch INSERT/UPSERT)**
- Real-world trigger: Session 23 Glokta audit found executemany rowcount bug hiding for 6 sessions
- psycopg2 executemany sets rowcount to LAST row only, not sum — silently corrupts monitoring data
- Use psycopg2.extras.execute_values for correct aggregate rowcount + better performance
**Changes in V1.23:**
- **Added Pattern 35: CLI Test Isolation for Parallel Execution (ALWAYS for Typer CLI Tests)**
- Documents solution to "I/O operation on closed file" errors during pytest-xdist parallel execution
- Root cause: Typer CLI global `app` object shared between parallel test workers
- Solution: `isolated_app` fixture for pytest tests, `get_fresh_cli()` helper for Hypothesis property tests
- Includes decision matrix, common mistakes, checklist for new CLI tests
- Real-world trigger: PR #285 fixing CLI test race conditions affecting 9 test files
- Total addition: ~170 lines documenting CLI test isolation pattern
**Changes in V1.22:**
- **Added Pattern 34: Two-Layer Schema Architecture for Historical Data Seeding (ALWAYS for External Data)**
- Seeding Layer (team_code VARCHAR) for flexible external data loading from CSV, APIs, scraped data
- Production Layer (team_id INTEGER FK) for referential integrity, efficient joins, and constraint enforcement
- Documents dual-column strategy: both team_code and team_id coexist, nullable FKs enable gradual backfill
- Real-world trigger: Issue #273 historical data seeding needed flexible loading before team mappings exist
- Applied across 7 historical tables: historical_elo, historical_games, historical_odds, historical_epa, historical_stats, historical_rankings, elo_calculation_log
- **Enhanced Pattern 18: Added SCD Type 2 Column Preservation Failure section (CRITICAL BUG PATTERN)**
- Documents insidious bug: adding columns to SCD Type 2 tables requires updating ALL versioning operations
- Real-world trigger: execution_environment column added but not preserved in close_position() SCD version
- Includes column preservation checklist (6 items), prevention strategies, test pattern to catch bug
- Bug behavior: tests pass, but queries fail silently due to NULL in new column
- Total addition: ~400 lines documenting both patterns
**Changes in V1.21:**
- **Added Pattern 33: API Vocabulary Alignment (ALWAYS for External API Integration)**
- When integrating external APIs, adapt database schema to match API vocabulary rather than creating translation layers
- Real-world trigger: Kalshi API sends frequency values ('daily', 'weekly', 'event') but DB constraint used ('single', 'recurring', 'continuous')
- Solution: Migration 0011 updated CHECK constraint to match API vocabulary
- Benefits: Simpler code (no translation), better developer experience, aligns with source of truth
- Total addition: ~120 lines documenting API vocabulary alignment pattern
**Changes in V1.20:**
- **Enhanced Pattern 28: Added Performance Tests with Latency Thresholds** (PR #240, Issue #238)
- Added "Performance tests (latency thresholds)" to Test Type CI Behavior Classification table
- Key difference: Stress tests HANG in CI, performance tests RUN but FAIL due to variable CPU scheduling
- Example: `test_kalshi_client_performance.py` p99=43.58ms in CI vs <20ms locally (over 2x variance)
- Applied same `skipif(_is_ci)` pattern but for different root cause (CPU variability, not threading hangs)
- **Added Pattern 32: Windows Subprocess Pipe Deadlock Prevention (ALWAYS for Large Output)**
- Problem: `subprocess.run()` with `capture_output=True` can deadlock on Windows when output exceeds pipe buffer (~4KB)
- Solution: File-based capture using `tempfile.mkstemp()` instead of pipe capture
- Implemented in `scripts/run_parallel_checks.py` after pre-push hook intermittent failures
- Critical for any script running subprocesses with potentially large output (test runners, build tools)
- Total addition: ~180 lines documenting both patterns
**Changes in V1.19:**
- **Added Pattern 31: Pre-Push Log Persistence (Quality of Life)** (Issue #174)
- Pre-push hook now generates JSON summaries alongside text logs
- Created `scripts/analyze_test_history.py` for trend analysis and flaky test detection
- JSON includes: timestamp, branch, success, duration, test counts, failed test names
- Enables debugging failed pushes after terminal is closed
- Enables comparison between pre-push and CI results
- Total addition: ~110 lines in DEVELOPMENT_PATTERNS, ~400 lines in analyze_test_history.py
**Changes in V1.18:**
- **Added Pattern 30: Stale Bytecode Cleanup (ALWAYS on pytest-xdist)** (Issue #171)
- Addresses "fixture not found" ghost tests from stale __pycache__/*.pyc files
- When test files move/delete, bytecode remains until explicitly cleaned
- pytest-xdist discovers tests from .pyc files, causing phantom test failures
- Pre-push hook now includes Step 0.25: Clean stale bytecode before tests
- Root cause: tests/unit/fixtures/test_transaction_fixtures.py moved to integration/
- Prevention: `find tests/ -type d -name "__pycache__" -exec rm -rf {} +`
- Cross-references: Issue #171, Pattern 29, pytest-xdist documentation
**Changes in V1.17:**
- **Added Pattern 29: Hybrid Test Isolation Strategy (ALWAYS for Database Tests)** (Issue #171)
- Documents 3-layer isolation strategy: Transaction rollback (~0ms) -> Pre-push phase separation -> Testcontainers (stress tests)
- Transaction rollback provides ~0ms isolation for 90% of tests using PostgreSQL ROLLBACK
- Pre-push hook phase separation with DB resets between test categories
- Testcontainers (Layer 3) for stress tests requiring complete isolation
- Removed xfail markers from CLI integration tests (now pass with testcontainers)
- Includes fixture implementation guide: db_transaction, db_transaction_with_setup, db_savepoint
- Cross-references: Issue #171, ADR-057, Pattern 28
- Total addition: ~250 lines documenting hybrid test isolation
**Changes in V1.16:**
- **Pattern 28 Evolution: xfail(run=False) -> skipif(_is_ci)** (Issue #168)
- Updated Pattern 28 title: "CI-Safe Stress Testing - skipif for Threading-Based Tests (ALWAYS)"
- Changed from `xfail(run=False)` to `skipif(_is_ci)` for cleaner semantics (XFAIL vs SKIPPED output)
- Added comparison table showing why skipif is preferred (clearer intent: "intentionally skipped" vs "expected to fail")
- Added ThreadPoolExecutor as root cause (concurrent futures with `as_completed()` hang in CI)
- Added pytest-timeout limitation explanation (SIGALRM cannot interrupt Python threads)
- Added testcontainers integration for database stress tests (ADR-057)
- Updated "When to Use Each Pattern" table: all threading scenarios now use skipif
- Updated CI output examples to show SKIPPED instead of XFAIL
- Updated implementation timeline with Issue #168 evolution
- Added CISafeBarrier helper class reference for threading tests with timeouts
- Total updates: ~100 lines modified to reflect production skipif pattern
**Changes in V1.15:**
- **Added Pattern 28: CI-Safe Stress Testing - xfail(run=False) for Threading-Based Tests (ALWAYS)** (initial version)
- Documents critical pattern from PR #167: Stress tests using `threading.Barrier()` or sustained loops can hang indefinitely in CI
- The Problem: CI resource constraints cause threading barriers to timeout and time-based loops to exceed limits
- Initial Solution: Use `@pytest.mark.xfail(condition=_is_ci, reason=..., run=False)` to skip execution in CI
- Critical insight: `run=False` prevents test body execution entirely
- Real-world trigger: PR #167 had CI jobs timing out at 10+ minutes due to stress test hangs
- Total addition: ~330 lines documenting CI-safe stress testing pattern
**Changes in V1.14:**
- **Added Pattern 26: Resource Cleanup for Testability (close() Methods) (ALWAYS)**
- Mandates explicit close() methods on all classes managing external resources (HTTP sessions, database connections)
- Enables proper resource cleanup in tests and production, prevents leaks, allows mocking session lifecycle
- Documents classes requiring close(): KalshiClient, ESPNClient, KalshiWebSocketHandler, KalshiMarketPoller, Database Pool
- Includes context manager pattern for automatic cleanup (__enter__/__exit__)
- **Added Pattern 27: Dependency Injection for Testability (ALWAYS for External Resources)**
- Mandates optional constructor parameters for external dependencies to enable clean testing without patches
- Shows migration from complex patching (3 @patch decorators) to clean DI (inject mocks directly)
- DI patterns for: key loaders (cryptographic), HTTP sessions, auth handlers, rate limiters
- Test helper pattern: _create_mock_client() for consistent mock creation
- "When to Use DI" decision table for 8 dependency types
- Real-world trigger: Phase 1.9 Test Infrastructure discovered test using patch without importing it
- Cross-references: Pattern 20, Pattern 13, Phase 1.9 Part B
- Total addition: ~350 lines documenting resource cleanup and DI patterns
**Changes in V1.13:**
- **Added Pattern 25: ANSI Escape Code Handling for Cross-Platform CLI Testing (ALWAYS)**
- Documents critical pattern from PR #159 CI fixes: Rich library outputs ANSI codes that break string matching on Windows
- The Problem: Rich outputs `\x1b[1;36m47.50\x1b[0m` but tests check for `"$47.50"`
- The Solution: Create `strip_ansi()` helper function using regex `\x1b\[[0-9;]*m`
- When to use: ANY CLI test using Rich library output (tables, progress bars, colored text)
- 20+ test assertions fixed across test_fetch_fills, test_fetch_settlements, test_health_check
- Includes helper function implementation, code examples (WRONG vs CORRECT), decision tree
- Cross-references: Pattern 5 (Cross-Platform Compatibility), PR #159, tests/unit/test_main.py
- Total addition: ~200 lines documenting ANSI escape code handling pattern
**Changes in V1.12:**
- **Added Pattern 24: No New Usage of Deprecated Code (MANDATORY)**
- Documents the principle of never using deprecated APIs/TypeDicts/patterns in new code
- Real-world context from this session: MarketUpdater initially used deprecated GameState
- User question "if its deprecated, why are you still using it?" triggered this pattern
- The Rule: New implementations MUST use modern replacement; existing code SHOULD migrate when touched
- Migration checklist (5 steps): Identify replacement → Use modern API → Add modern API if needed → Update tests → Update docs
- Decision tree for when building new features vs. bug fixes
- Common deprecated patterns table: GameState → ESPNGameFull, get_scoreboard() → get_scoreboard_normalized()
- Wrong vs. Correct examples showing deprecated API usage in new code
- Cross-references: Pattern 6 (TypedDict), Pattern 18 (Avoid Technical Debt), Pattern 23 (Validation Failure Handling)
- Related files: espn_client.py, market_updater.py
- Total addition: ~165 lines documenting no-new-deprecated-code principle
**Changes in V1.11:**
- **Added Pattern 23: Validation Failure Handling - Fix Failures, Don't Bypass (MANDATORY)**
- Documents systematic approach to handling validation failures (distinguish false positives from real failures)
- Real-world context from this session: SCD Type 2 docstring false positives, Issue #127 property tests, validation config alignment
- Covers 4-step protocol: Investigate (5-10 min) → Fix False Positives (validation script) → Fix Real Failures (code) → Re-run Validation
- Decision tree for classification: False positive vs. Real failure vs. Both
- When bypass is acceptable (rare): Emergency hotfix, validation script bug, external dependency issue
- When bypass is NEVER acceptable: "Tests are slow", "I'm sure it's fine", "Quick demo push"
- Validation script best practices: Clear error messages, escape hatches, skip non-code contexts, verbose mode
- Common mistakes: Bypass without investigation, fix false positive but ignore real failure, lower coverage standards
- Integration with Pattern 21 (Validation-First Architecture), Pattern 18 (Avoid Technical Debt), Pattern 9 (Warning Governance)
- Testing validation scripts: Examples for catching real violations AND ignoring false positives
- Real-world impact: 5 false positives eliminated, 11 property tests added, pre-push success 0% → 100%
- Cross-references: Issue #127, Pattern 21, Pattern 18, Pattern 9, ADR-002/018-020/074
- Total addition: ~530 lines documenting validation failure handling protocol
**Changes in V1.10:**
- **Added Pattern 22: VCR Pattern for Real API Responses (ALWAYS for External APIs) - CRITICAL**
- Documents VCR (Video Cassette Recorder) testing pattern for API integration tests
- Real-world context from GitHub #124 Parts 1-6 (Kalshi sub-penny pricing discovery)
- VCR records REAL API responses once, replays them in tests (combines speed + accuracy)
- Caught critical bug: Kalshi dual-format pricing (integer cents vs. sub-penny string)
- Benefits: 100% real API structures, fast (1ms), deterministic, CI-friendly, credentials filtered
- Implementation: 5-step workflow (install → configure → write test → record → commit cassette)
- Decision tree: When to use VCR vs. Mocks vs. Real Fixtures (4 scenarios)
- Common mistakes: Sensitive headers not filtered, wrong record_mode, one cassette for all tests
- VCR + Pattern 13 integration: Real API responses + Real database fixtures
- Real-world example: 8 VCR tests for Kalshi API, 5 cassettes, 359-line test file
- Cross-references: Pattern 13, Pattern 1, ADR-075, REQ-TEST-013/014, GitHub #124
- Total addition: ~360 lines documenting VCR testing pattern best practices
**Changes in V1.9:**
- **Added Pattern 21: Validation-First Architecture - 4-Layer Defense in Depth (CRITICAL)**
- Documents comprehensive validation architecture: pre-commit → pre-push → CI/CD → branch protection
- Layer 1 (Pre-commit): 2-5s fast checks with auto-fix (Ruff format, line endings, trailing whitespace)
- Layer 2 (Pre-push): 30-60s comprehensive validation with tests (first time tests run locally)
- Layer 3 (CI/CD): 2-5min multi-platform validation (Linux, Windows, macOS)
- Layer 4 (Branch protection): GitHub enforcement (requires 6 status checks, up-to-date branches)
- Covers validation script architecture (YAML-driven, auto-discovery, zero configuration)
- Real-world impact: 60-70% CI failure reduction (pre-commit), 80-90% reduction (pre-commit + pre-push)
- Cross-references: DEF-001, DEF-002, DEF-003 (Pre-commit/Pre-push/Branch protection implementation)
- Total addition: ~450 lines documenting validation-first architecture and defense in depth
**Changes in V1.8:**
- **Added Pattern 19: Hypothesis Decimal Strategy - Use Decimal Strings for min/max (ALWAYS)**
- Documents critical pattern from SESSION 4.3 (2025-11-23): Use Decimal("0.0100") not float 0.01 in Hypothesis decimals() strategy
- Real-world context: Eliminated 17 HypothesisDeprecationWarnings by replacing float literals with Decimal strings
- Covers common mistakes: forgetting Decimal import, mixing float and Decimal, wrong decimal places
- Cross-references: Pattern 1 (Decimal Precision), Pattern 10 (Property-Based Testing), ADR-074, SESSION 4.3
- Total addition: ~310 lines documenting Hypothesis Decimal strategy best practices
- **Added Pattern 20: Resource Management - Explicit File Handle Cleanup (ALWAYS)**
- Documents critical pattern from SESSION 4.2 (2025-11-23): Explicitly close FileHandler objects before removeHandler()
- Real-world context: Eliminated 11 ResourceWarnings by adding handler.close() to logger.py
- Key technique: Use handlers[:] slice when iterating over list you're modifying
- Covers common mistakes: iterating without slice, closing non-file handlers, forgetting to remove after close
- Cross-references: Pattern 9 (Warning Governance), Pattern 12 (Test Fixture Security), SESSION 4.2
- Total addition: ~340 lines documenting resource management best practices
**Changes in V1.7:**
- **Added Pattern 18: Avoid Technical Debt - Fix Root Causes, Not Symptoms (ALWAYS)**
- Documents formal technical debt tracking workflow with three-part process: Acknowledge → Schedule → Fix
- Real-world context from Phase 1.5 completion (21 validation violations deferred to Phase 2 Week 1)
- Covers debt classification system (🔴 Critical, 🟡 High, 🟢 Medium, 🔵 Low based on risk/impact)
- Multi-location tracking strategy: GitHub issues + PHASE_X_DEFERRED_TASKS.md + scheduled resolution
- When deferral is acceptable: non-blocking, formally tracked, scheduled fix, documented rationale
- Common mistakes: "Will fix later" without tracking, quick hacks without root cause analysis, missing debt documentation
- Cross-references: GitHub Issue #101, PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-002), Pattern 8 (Config Synchronization)
- Total addition: ~320 lines documenting technical debt management best practices
**Changes in V1.6:**
- **Added Pattern 16: Type Safety with Dynamic Data - YAML/JSON Parsing (ALWAYS)**
- Documents explicit `cast()` usage for YAML/JSON parsing to avoid Mypy no-any-return errors
- Real-world context from PR #98 (fixed 4 validation scripts with type safety issues)
- Covers common patterns: nested dictionaries, list of dicts, JSON parsing with type expectations
- Common mistakes: forgetting cast import, unquoted types in cast (Ruff TC006), using isinstance instead of cast
- Cross-references: Pattern 6 (TypedDict), Mypy no-any-return error handling, Ruff TC006 violation
- Total addition: ~184 lines documenting type-safe YAML/JSON parsing patterns
- **Added Pattern 17: Avoid Nested If Statements - Use Combined Conditions (ALWAYS)**
- Documents combining conditions with `and`/`or` instead of nesting if statements (Ruff SIM102)
- Real-world context from PR #98 (validate_phase_start.py nested if refactoring)
- Covers complex conditions: multiple AND, mixed AND/OR, early return pattern
- When nested is better: different error messages per layer, resource cleanup paths
- Cross-references: Ruff SIM102 violation, code readability best practices
- Total addition: ~196 lines documenting flat control flow patterns
**Changes in V1.5:**
- **Added Pattern 15: Trade/Position Attribution Architecture (ALWAYS - Migrations 018-020)**
- Documents comprehensive attribution for trades and positions (execution-time snapshots)
- Covers trade source tracking (automated vs manual), attribution enrichment (calculated_probability, market_price, edge_value)
- Explains automatic edge calculation (edge_value = calculated_probability - market_price)
- Position attribution with immutability (ADR-018): Entry snapshots never updated
- Includes negative edge handling, backward compatibility, CHECK constraint validation
- Performance analytics queries: ROI by model, edge vs outcome analysis, strategy A/B testing
- Testing best practices with test_attribution.py examples
- Common mistakes: Missing attribution fields, violating immutability, using FLOAT instead of DECIMAL
- Cross-references: ADR-090 (Nested Versioning), ADR-091 (Explicit Columns), ADR-092 (Trade Source), Migration 018-020
- Total addition: ~412 lines documenting attribution architecture best practices
**Changes in V1.4:**
- **Added Pattern 14: Schema Migration → CRUD Operations Update Workflow (CRITICAL)**
- Documents mandatory workflow when database schema changes require CRUD operation updates
- Covers dual-key pattern implementation (surrogate PRIMARY KEY + business key with partial unique index)
- Step-by-step workflow: Migration → CRUD update → Test update → Integration test verification
- Explains SCD Type 2 versioning pattern (UPDATE old + INSERT new with row_current_ind)
- Common patterns: Setting business_id from surrogate_id, WHERE row_current_ind filtering
- Testing requirements: Integration tests must use real database (NO mocks for CRUD/connection)
- Real-world examples from Migration 011 (positions dual-key schema) and Position Manager implementation
- Cross-references: ADR-089 (Dual-Key Schema Pattern), ADR-088 (Test Type Categories), Pattern 13 (Test Coverage Quality)
- Total addition: ~450 lines documenting critical schema-to-CRUD synchronization workflow
**Changes in V1.3:**
- **Added Pattern 12: Test Fixture Security Compliance (MANDATORY)**
- Documents project-relative test fixture pattern for security-validated functions
- Provides real-world example from PR #79 (test fixture fixes for path traversal protection)
- Includes Generator pattern with yield/finally, UUID for unique filenames, cleanup strategy
- Covers when to use project-relative vs tmp_path fixtures
- Impact: 9/25 tests failing → 25/25 passing, coverage 68.32% → 89.11% (+20.79pp)
- Cross-references: PR #79, PR #76 (CWE-22 path traversal protection), DEVELOPMENT_PHILOSOPHY Security-First Testing
**Changes in V1.2:**
- **Enhanced Pattern 5: Cross-Platform Compatibility**
- Added comprehensive Unicode symbol mapping table (14 symbols documented)
- Documented CLI symbols: ✓→[OK], ✗→[FAIL], ⚠→[WARN], •→-, →→->
- Added Rich console library behavior on Windows cp1252
- Included real-world example reference (commit 520c5dd - CLI Unicode fixes)
- Clarified file I/O Unicode handling: always use `encoding="utf-8"`
**Changes in V1.1:**
- **Added Pattern 11: Test Mocking Patterns (Mock API Boundaries, Not Implementation)**
- Documents mocking antipattern discovered in PR #19 and PR #20
- Provides real-world examples from ConfigLoader test fixes (11 tests fixed)
- Includes mocking hierarchy, best practices, and decision tree
- 230+ lines of comprehensive mocking guidance
- References: PR #19, PR #20, tests/unit/test_main.py (lines 1875-2290)
**Changes in V1.0:**
- Initial creation extracted from CLAUDE.md to reduce context load
- Contains all 10 critical patterns with complete examples and references
- Cross-references to related ADRs, REQs, and implementation guides

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [Pattern 1: Decimal Precision (NEVER USE FLOAT)](#pattern-1-decimal-precision-never-use-float)
3. [Pattern 2: Dual Versioning System](#pattern-2-dual-versioning-system)
4. [Pattern 3: Trade Attribution](#pattern-3-trade-attribution)
5. [Pattern 4: Security (NO CREDENTIALS IN CODE)](#pattern-4-security-no-credentials-in-code)
6. [Pattern 5: Cross-Platform Compatibility (Windows/Linux)](#pattern-5-cross-platform-compatibility-windowslinux)
7. [Pattern 6: TypedDict for API Response Types (ALWAYS)](#pattern-6-typeddict-for-api-response-types-always)
8. [Pattern 7: Educational Docstrings (ALWAYS)](#pattern-7-educational-docstrings-always)
9. [Pattern 8: Configuration File Synchronization (CRITICAL)](#pattern-8-configuration-file-synchronization-critical)
10. [Pattern 9: Multi-Source Warning Governance (MANDATORY)](#pattern-9-multi-source-warning-governance-mandatory)
11. [Pattern 10: Property-Based Testing with Hypothesis (ALWAYS for Trading Logic)](#pattern-10-property-based-testing-with-hypothesis-always-for-trading-logic)
12. [Pattern 11: Test Mocking Patterns (Mock API Boundaries, Not Implementation)](#pattern-11-test-mocking-patterns-mock-api-boundaries-not-implementation)
13. [Pattern 12: Test Fixture Security Compliance (MANDATORY)](#pattern-12-test-fixture-security-compliance-mandatory)
14. [Pattern 13: Test Coverage Quality (Mock Sparingly, Integrate Thoroughly)](#pattern-13-test-coverage-quality-mock-sparingly-integrate-thoroughly---critical)
15. [Pattern 14: Schema Migration → CRUD Operations Update Workflow (CRITICAL)](#pattern-14-schema-migration--crud-operations-update-workflow-critical)
16. [Pattern 15: Trade/Position Attribution Architecture (ALWAYS)](#pattern-15-tradeposition-attribution-architecture-always---migrations-018-020)
17. [Pattern 16: Type Safety with Dynamic Data - YAML/JSON Parsing (ALWAYS)](#pattern-16-type-safety-with-dynamic-data---yamljson-parsing-always)
18. [Pattern 17: Avoid Nested If Statements - Use Combined Conditions (ALWAYS)](#pattern-17-avoid-nested-if-statements---use-combined-conditions-always)
19. [Pattern 18: Avoid Technical Debt - Fix Root Causes, Not Symptoms (ALWAYS)](#pattern-18-avoid-technical-debt---fix-root-causes-not-symptoms-always)
20. [Pattern 19: Hypothesis Decimal Strategy - Use Decimal Strings for min/max (ALWAYS)](#pattern-19-hypothesis-decimal-strategy---use-decimal-strings-for-minmax-always)
21. [Pattern 20: Resource Management - Explicit File Handle Cleanup (ALWAYS)](#pattern-20-resource-management---explicit-file-handle-cleanup-always)
22. [Pattern 21: Validation-First Architecture - 4-Layer Defense in Depth (CRITICAL)](#pattern-21-validation-first-architecture---4-layer-defense-in-depth-critical)
23. [Pattern 22: VCR Pattern for Real API Responses (ALWAYS for External APIs)](#pattern-22-vcr-pattern-for-real-api-responses-always-for-external-apis---critical)
24. [Pattern 23: Validation Failure Handling - Fix Failures, Don't Bypass (MANDATORY)](#pattern-23-validation-failure-handling---fix-failures-dont-bypass-mandatory)
25. [Pattern 65: Mock the Entry Point, Not the Terminal Constructor (ALWAYS for Factory-Constructed Objects)](#pattern-65-mock-the-entry-point-not-the-terminal-constructor-always-for-factory-constructed-objects)
26. [Pattern 66: Strict Exit-Code Assertions as Decay Detection (ALWAYS for CLI Tests)](#pattern-66-strict-exit-code-assertions-as-decay-detection-always-for-cli-tests)
27. [Pattern 67: `assert_called` as the Fail-Loud Invariant for Mocks (ALWAYS for patch()-Based Tests)](#pattern-67-assert_called-as-the-fail-loud-invariant-for-mocks-always-for-patch-based-tests)
28. [Pattern 68: Preserve-X Requires X Exists (ALWAYS for Multi-Session Preservation Framing)](#pattern-68-preserve-x-requires-x-exists-always-for-multi-session-preservation-framing)
29. [Pattern 69: Post-Retrofit Cosmetic-Coverage Check (ALWAYS for Test Mock-Layer Retrofits)](#pattern-69-post-retrofit-cosmetic-coverage-check-always-for-test-mock-layer-retrofits)
30. [Pattern 70: Convergent-Reviewer Signal Rule (ALWAYS for Multi-Reviewer Dispatch)](#pattern-70-convergent-reviewer-signal-rule-always-for-multi-reviewer-dispatch)
31. [Pattern 71: Verify High-Confidence Sentinel Claims Via Code Inspection Before Acting (ALWAYS for Sentinel-Frame Findings)](#pattern-71-verify-high-confidence-sentinel-claims-via-code-inspection-before-acting-always-for-sentinel-frame-findings)
32. [Pattern 72: Scope Correction Via Mechanical Pre-ANNOUNCE Scoping (ALWAYS for Tier 2 Dispatches)](#pattern-72-scope-correction-via-mechanical-pre-announce-scoping-always-for-tier-2-dispatches)
33. [Pattern Quick Reference](#pattern-quick-reference)
34. [Related Documentation](#related-documentation)

---

## Introduction

This guide contains **17 critical development patterns** that must be followed throughout the Precog project. These patterns address:

- **Financial Precision:** Decimal-only arithmetic for sub-penny pricing
- **Data Versioning:** Dual versioning system for mutable vs. immutable data
- **Security:** Zero-tolerance for hardcoded credentials
- **Cross-Platform:** Windows/Linux compatibility
- **Type Safety:** TypedDict for compile-time validation + explicit cast() for YAML/JSON parsing
- **Testing:** Property-based testing for trading logic + robust test mocking + integration test requirements
- **Configuration:** Multi-layer config synchronization
- **Quality:** Multi-source warning governance + flat control flow (no nested ifs)
- **Schema Management:** Database schema migration → CRUD operations synchronization workflow

**Why These Patterns Matter:**

Trading applications require **extreme precision, security, and reliability**. A single rounding error, credential leak, or configuration drift can cause:
- Financial losses (incorrect prices)
- Security breaches (leaked API keys)
- Deployment failures (config mismatches)
- Subtle bugs (cross-platform issues)

These patterns prevent such issues through **defense in depth**:
- Multiple layers of validation
- Automated checks (pre-commit, pre-push, CI/CD)
- Educational documentation
- Clear examples of correct AND incorrect usage

**How to Use This Guide:**

- **Before implementing features:** Review relevant patterns
- **During code review:** Verify patterns are followed
- **When debugging:** Check if pattern violations caused the bug
- **When onboarding:** Study all 10 patterns

**Pattern Categories:**

| Category | Patterns | Enforcement Level |
|----------|----------|-------------------|
| **Financial Safety** | Pattern 1 (Decimal Precision) | MANDATORY - Automated checks |
| **Data Management** | Pattern 2 (Versioning), Pattern 3 (Attribution) | MANDATORY - Code review |
| **Security** | Pattern 4 (No Credentials) | MANDATORY - Pre-commit hooks |
| **Quality** | Pattern 5-10 | MANDATORY - Pre-push hooks + CI/CD |

---

## Pattern 1: Decimal Precision (NEVER USE FLOAT)

**WHY:** Kalshi uses sub-penny pricing (e.g., $0.4975). Float causes rounding errors.

**ALWAYS:**
```python
from decimal import Decimal

# ✅ CORRECT
price = Decimal("0.4975")
spread = Decimal("0.0050")
total = price + spread  # Decimal("0.5025")

# ✅ Parse from API
yes_bid = Decimal(market_data["yes_bid_dollars"])

# ✅ Database
yes_bid = Column(DECIMAL(10, 4), nullable=False)
```

**NEVER:**
```python
# ❌ WRONG - Float contamination
price = 0.4975  # float
price = float(market_data["yes_bid_dollars"])

# ❌ WRONG - Integer cents (deprecated by Kalshi)
yes_bid = market_data["yes_bid"]

# ❌ WRONG - PostgreSQL FLOAT
yes_bid = Column(Float, nullable=False)
```

**Reference:** `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md`

**⚠️ MAINTENANCE REMINDER:**
When adding new database tables with price/probability columns:
1. Add table name and column list to `price_columns` dict in `scripts/validate_schema_consistency.py`
2. Run validation: `python scripts/validate_schema_consistency.py`
3. See script's MAINTENANCE GUIDE for detailed instructions
4. **Time estimate:** ~5 minutes per table

---

## Pattern 2: Dual Versioning System

**Two Different Patterns for Different Needs:**

### Pattern A: SCD Type 2 (Frequently-Changing Data)

**Use for:** markets, positions, game_states, edges, account_balance

**How it works:**
- `row_current_ind BOOLEAN` - TRUE = current, FALSE = historical
- When updating: INSERT new row (row_current_ind=TRUE), UPDATE old row (set FALSE)
- **ALWAYS query with:** `WHERE row_current_ind = TRUE`

```python
# ✅ CORRECT
current_positions = session.query(Position).filter(
    Position.row_current_ind == True
).all()

# ❌ WRONG - Gets historical versions too
all_positions = session.query(Position).all()
```

### Pattern B: Immutable Versions (Strategies & Models)

**Use for:** strategies, probability_models

**How it works:**
- `version` field (e.g., "v1.0", "v1.1", "v2.0")
- `config` JSONB is **IMMUTABLE** - NEVER changes
- `status` field is **MUTABLE** - Can change (draft → testing → active → deprecated)
- To change config: Create NEW version (v1.0 → v1.1)

```python
# ✅ CORRECT - Create new version
v1_1 = Strategy(
    strategy_name="halftime_entry",
    strategy_version="v1.1",
    config={"min_lead": 10},  # Different from v1.0
    status="draft"
)

# ❌ WRONG - Modifying immutable config
v1_0.config = {"min_lead": 10}  # VIOLATES IMMUTABILITY

# ✅ CORRECT - Update mutable status
v1_0.status = "deprecated"  # OK
```

**Why Immutable Configs:**
- A/B testing integrity (configs never change)
- Trade attribution (know EXACTLY which config generated each trade)
- Semantic versioning (v1.0 → v1.1 = bug fix, v1.0 → v2.0 = major change)

**Reference:** `docs/guides/VERSIONING_GUIDE_V1.0.md`

**WARNING: Anti-pattern -- Pattern 2 filter on same-transaction read-after-write.**

Adding `AND row_current_ind = TRUE` to an `INSERT...SELECT` that runs in the same transaction as an `UPDATE` which just cleared that flag will cause the `SELECT` to match zero rows. The `INSERT` then inserts nothing, `RETURNING id` yields no row, and consumers that expect a row raise `TypeError`.

This anti-pattern was introduced by PR #139 (2025-11-25) as an overly-aggressive Pattern 2 enforcement sweep. It broke the trailing stop write paths for 4.5 months without detection because zero production callers exercised the bug and all tests used pure mocks.

```python
# WRONG -- same-transaction read-after-write with row_current_ind filter
cur.execute("UPDATE positions SET row_current_ind = FALSE WHERE id = %s", (pid,))
cur.execute("""
    INSERT INTO positions (...)
    SELECT ... FROM positions
    WHERE id = %s AND row_current_ind = TRUE   -- sees the UPDATE above, matches 0 rows
    RETURNING id
""", (pid,))
row = cur.fetchone()  # row is None!
new_id = row["id"]   # TypeError
```

```python
# CORRECT -- capture values BEFORE the UPDATE, then INSERT from Python-level values
cur.execute("SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE", (pid,))
current = cur.fetchone()
cur.execute("UPDATE positions SET row_current_ind = FALSE WHERE id = %s", (pid,))
cur.execute("""
    INSERT INTO positions (col_a, col_b, ...)
    VALUES (%s, %s, ...)
    RETURNING id
""", (current["col_a"], current["col_b"], ...))
```

**Why the anti-pattern is subtle:** The Pattern 2 filter looks correct in isolation ("always filter by `row_current_ind = TRUE`"), and code review typically approves it as a defensive improvement. The failure only manifests when the same transaction has already cleared the flag -- a non-obvious interaction visible only to integration tests.

**Reference:** Session 42e #629 investigation. Git blame to commit `c4a34adb` (PR #139). Related: Pattern 49 (SCD race prevention -- the newer approach that avoids the anti-pattern entirely by using the retry helper + FOR UPDATE + captured Python values).

**MAINTENANCE REMINDER:**
When adding new SCD Type 2 tables (versioned tables):
1. Add table name to `versioned_tables` list in `scripts/validate_schema_consistency.py`
2. Ensure table has ALL 4 required columns:
   - `row_current_ind BOOLEAN NOT NULL DEFAULT TRUE`
   - `row_start_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`
   - `row_end_ts TIMESTAMP` (nullable)
   - `row_version INTEGER NOT NULL DEFAULT 1`
3. Run validation: `python scripts/validate_schema_consistency.py`
4. See script's MAINTENANCE GUIDE for detailed instructions
5. **Time estimate:** ~2 minutes per table

---

## Pattern 3: Trade Attribution

**EVERY trade must link to exact versions:**

```python
# ✅ CORRECT - Full attribution
trade = Trade(
    market_id=market.id,
    strategy_id=strategy.strategy_id,  # Link to exact version
    model_id=model.model_id,           # Link to exact version
    quantity=100,
    price=Decimal("0.7500"),
    side="YES"
)

# ❌ WRONG - No attribution
trade = Trade(
    market_id=market.id,
    # Missing strategy_id and model_id!
    quantity=100,
    price=Decimal("0.7500")
)
```

**Query trade with full version details:**
```python
trade_with_versions = (
    session.query(Trade, Strategy, ProbabilityModel)
    .join(Strategy, Trade.strategy_id == Strategy.strategy_id)
    .join(ProbabilityModel, Trade.model_id == ProbabilityModel.model_id)
    .filter(Trade.trade_id == trade_id)
    .first()
)

print(f"Strategy: {strategy.strategy_name} v{strategy.strategy_version}")
print(f"Model: {model.model_name} v{model.model_version}")
```

---

## Pattern 4: Security (NO CREDENTIALS IN CODE)

**ALWAYS use environment variables:**

```python
# ✅ CORRECT
import os
from dotenv import load_dotenv

load_dotenv()

db_password = os.getenv('DB_PASSWORD')
api_key = os.environ['KALSHI_API_KEY']  # Raises KeyError if missing

# Validate credentials exist
if not db_password:
    raise ValueError("DB_PASSWORD environment variable not set")
```

**NEVER:**
```python
# ❌ NEVER hardcode
password = "mypassword"
api_key = "sk_live_abc123"
db_url = "postgres://user:password@host/db"
```

**Pre-Commit Security Scan:**
```bash
# Run BEFORE EVERY COMMIT
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py'

# Expected: No results (or only os.getenv lines)
```

**Reference:** `docs/utility/SECURITY_REVIEW_CHECKLIST.md`

---

## Pattern 5: Cross-Platform Compatibility (Windows/Linux)

**WHY:** Development occurs on both Windows (local) and Linux (CI/CD). Python scripts that work on Linux fail on Windows with `UnicodeEncodeError` when printing emoji to console.

**The Problem:** Windows console uses cp1252 encoding (limited character set), Linux/Mac use UTF-8 (full Unicode support).

**ALWAYS:**
```python
# ✅ CORRECT - ASCII equivalents for console output
print("[OK] All tests passed")
print("[FAIL] 3 errors found")
print("[WARN] Consider updating")
print("[IN PROGRESS] Phase 1 - 50% complete")

# ✅ CORRECT - Explicit UTF-8 for file I/O
with open("file.md", "r", encoding="utf-8") as f:
    content = f.read()

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f)

# ✅ CORRECT - Sanitize Unicode when reading from markdown
def sanitize_unicode(text: str) -> str:
    """Replace Unicode symbols with ASCII equivalents for Windows console.

    Comprehensive mapping table for all Unicode symbols used in project.
    """
    replacements = {
        # Status emoji (used in documentation)
        "✅": "[COMPLETE]",
        "🔵": "[PLANNED]",
        "🟡": "[IN PROGRESS]",
        "❌": "[FAILED]",
        "⚠️": "[WARNING]",

        # CLI output symbols (used in main.py)
        "✓": "[OK]",        # U+2713 - Check mark
        "✗": "[FAIL]",      # U+2717 - Ballot X
        "⚠": "[WARN]",      # U+26A0 - Warning sign (no variation selector)
        "•": "-",           # U+2022 - Bullet point
        "→": "->",          # U+2192 - Right arrow

        # Progress indicators
        "▶": "[>]",         # U+25B6 - Play symbol
        "⏸": "[||]",        # U+23F8 - Pause symbol
        "⏹": "[#]",         # U+23F9 - Stop symbol
    }
    for unicode_char, ascii_replacement in replacements.items():
        text = text.replace(unicode_char, ascii_replacement)
    return text

# Usage
print(sanitize_unicode(error_message))  # Safe for Windows console
```

**NEVER:**
```python
# ❌ WRONG - Emoji in console output
print("✅ All tests passed")  # Crashes on Windows cp1252
print("❌ 3 errors found")

# ❌ WRONG - Platform default encoding
with open("file.md", "r") as f:  # cp1252 on Windows, UTF-8 on Linux
    content = f.read()
```

**Where Unicode is OK:**
- **Markdown files (.md)**: ✅ Yes (GitHub/VS Code render correctly)
- **Script `print()` output**: ❌ No (use ASCII equivalents)
- **Error messages**: ❌ No (may be printed to console - sanitize first)
- **File contents (YAML, JSON, Python source)**: ✅ Yes (but always use `encoding="utf-8"` when reading)

**Rich Console Library (main.py CLI):**
The Rich library used in main.py attempts to handle Unicode, but still fails on Windows cp1252 terminals:
```python
# ❌ WRONG - Rich still crashes with Unicode on Windows cp1252
console.print("[green]✓ Success[/green]")  # UnicodeEncodeError

# ✅ CORRECT - Use ASCII equivalents even with Rich
console.print("[green][OK] Success[/green]")  # Works on all platforms
```

**Real-World Example:**
Fixed in commit 520c5dd (2025-11-14): All CLI commands (db-init, health-check, config-show, config-validate) had Unicode symbols replaced with ASCII equivalents to support Windows cp1252.

**Reference:**
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.10.md` (ADR-053)
- `scripts/validate_docs.py` (lines 57-82 for sanitization example)
- `main.py` (lines 1196-1753 for CLI ASCII output examples)

---

## Pattern 6: TypedDict for API Response Types (ALWAYS)

**WHY:** Type safety prevents field name typos and wrong types at compile-time. TypedDict provides IDE autocomplete and mypy validation with zero runtime overhead.

**TypedDict vs Pydantic:**
- **TypedDict:** Compile-time type hints, no runtime validation, zero overhead
- **Pydantic:** Runtime validation, automatic parsing, detailed errors, slower

**Use TypedDict for Phase 1-4** (internal code, trusted APIs)
**Use Pydantic for Phase 5+** (external inputs, trading execution)

**ALWAYS:**
```python
from typing import TypedDict, List, cast
from decimal import Decimal

# ✅ CORRECT - Define response structure
class MarketResponse(TypedDict):
    ticker: str
    yes_bid: Decimal  # After conversion
    yes_ask: Decimal
    volume: int
    status: Literal["open", "closed", "settled"]  # Use Literal for enums

# ✅ CORRECT - Use in function signature
def get_markets(self) -> List[MarketResponse]:
    """Fetch markets with type safety."""
    response = self._make_request("GET", "/markets")
    markets = response.get("markets", [])

    # Convert prices to Decimal
    for market in markets:
        self._convert_prices_to_decimal(market)

    return cast(List[MarketResponse], markets)

# ✅ CORRECT - IDE knows which fields exist
market = get_markets()[0]
print(market['ticker'])  # ✅ Autocomplete works
print(market['volume'])  # ✅ Type checker knows it's int

# ✅ CORRECT - Mypy catches errors
print(market['price'])  # ❌ Error: 'price' not in MarketResponse
```

**NEVER:**
```python
# ❌ WRONG - Untyped dictionary
def get_markets(self) -> List[Dict]:
    return self._make_request("GET", "/markets")

market = get_markets()[0]
print(market['tickr'])  # ❌ Typo! No autocomplete, no error until runtime
```

**Key Patterns:**

1. **Separate "Raw" and "Processed" Types:**
```python
# Raw API response (prices as strings)
class MarketDataRaw(TypedDict):
    ticker: str
    yes_bid: str  # "0.6250"
    yes_ask: str  # "0.6300"

# After Decimal conversion
class ProcessedMarketData(TypedDict):
    ticker: str
    yes_bid: Decimal  # Decimal("0.6250")
    yes_ask: Decimal  # Decimal("0.6300")
```

2. **Use Literal types for enums:**
```python
from typing import Literal

class Position(TypedDict):
    ticker: str
    side: Literal["yes", "no"]  # Only these values allowed
    action: Literal["buy", "sell"]
```

3. **Use cast() to assert runtime matches compile-time:**
```python
# After processing, assert dict matches TypedDict structure
return cast(List[ProcessedMarketData], markets)
```

**Reference:** `api_connectors/types.py` for 17 TypedDict examples
**Related:** ADR-048 (Decimal-First Response Parsing), REQ-API-007 (Pydantic migration planned for Phase 1.5)

---

## Pattern 7: Educational Docstrings (ALWAYS)

**WHY:** Complex concepts (RSA-PSS auth, Decimal precision, SCD Type 2) require educational context. Verbose docstrings with examples prevent mistakes and accelerate onboarding.

**ALWAYS Include:**
1. **Clear description** of what the function does
2. **Args/Returns documentation** with types
3. **Educational Note** explaining WHY this pattern matters
4. **Examples** showing correct AND incorrect usage
5. **Related references** (ADRs, REQs, docs)

**ALWAYS:**
```python
def create_account_balance_record(session, balance: Decimal, platform_id: str) -> int:
    """
    Create account balance snapshot in database.

    Args:
        session: SQLAlchemy session (active transaction)
        balance: Account balance as Decimal (NEVER float!)
        platform_id: Platform identifier ("kalshi", "polymarket")

    Returns:
        int: Record ID (balance_id from database)

    Raises:
        ValueError: If balance is float (not Decimal)
        TypeError: If session is not SQLAlchemy session

    Educational Note:
        Balance stored as DECIMAL(10,4) in PostgreSQL for exact precision.
        NEVER use float - causes rounding errors with sub-penny prices.

        Why this matters:
        - Kalshi uses sub-penny pricing (e.g., $0.4975)
        - Float arithmetic: 0.4975 + 0.0050 = 0.502499999... (WRONG!)
        - Decimal arithmetic: 0.4975 + 0.0050 = 0.5025 (CORRECT!)

    Example:
        >>> from decimal import Decimal
        >>> balance = Decimal("1234.5678")  # ✅ Correct
        >>> record_id = create_account_balance_record(
        ...     session=session,
        ...     balance=balance,
        ...     platform_id="kalshi"
        ... )
        >>> print(record_id)  # 42

        >>> # ❌ WRONG - Float contamination
        >>> balance = 1234.5678  # float type
        >>> # Will raise ValueError

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - ADR-002: Decimal-Only Financial Calculations
        - Pattern 1 in DEVELOPMENT_PATTERNS_V1.0.md: Decimal Precision
    """
    if not isinstance(balance, Decimal):
        raise ValueError(f"Balance must be Decimal, got {type(balance)}")

    # Implementation...
    return record_id
```

**NEVER:**
```python
# ❌ Minimal docstring (insufficient for complex project)
def create_account_balance_record(session, balance, platform_id):
    """Create balance record."""
    # Missing: Why Decimal? What's platform_id? Examples? Related docs?
    return session.query(...).insert(...)
```

**Apply to ALL modules:**
- ✅ API connectors: Already have excellent educational docstrings
- ⚠️ Database CRUD: Needs enhancement (Phase 1.5 improvement)
- ⚠️ Config loader: Needs enhancement (Phase 1.5 improvement)
- ⚠️ CLI commands: Adequate (main.py has good command docstrings)
- ✅ Utils (logger): Good docstrings

**When to use Educational Notes:**
- **Complex algorithms**: Token bucket, exponential backoff, SCD Type 2
- **Security-critical code**: Authentication, credential handling, SQL injection prevention
- **Precision-critical code**: Decimal arithmetic, price calculations, financial math
- **Common mistakes**: Float vs Decimal, mutable defaults, SQL injection
- **Non-obvious behavior**: RSA-PSS signature format, timezone handling, rate limiting

**Reference:** `api_connectors/kalshi_auth.py` (lines 41-90, 92-162) for excellent examples

---

## Pattern 8: Configuration File Synchronization (CRITICAL)

**WHY:** Configuration files exist at **4 different layers** in the validation pipeline. When migrating tools or changing requirements, ALL layers must be updated to prevent configuration drift.

**The Problem We Just Fixed:**
- Migrated Bandit → Ruff in 3 layers (.pre-commit-config.yaml, .git/hooks/pre-push, .github/workflows/ci.yml)
- **MISSED** pyproject.toml `[tool.bandit]` section
- Result: pytest auto-detected Bandit config → 200+ Bandit errors → all pushes blocked

**Four Configuration Layers:**

```
Layer 1: Tool Configuration Files
├── pyproject.toml           [tool.ruff], [tool.mypy], [tool.pytest], [tool.coverage]
├── .pre-commit-config.yaml  Pre-commit hook definitions (12 checks)
└── pytest.ini               Test framework settings (if separate)

Layer 2: Pipeline Configuration Files
├── .git/hooks/pre-push      Pre-push validation script (Bash)
├── .git/hooks/pre-commit    Pre-commit validation script (managed by pre-commit framework)
└── .github/workflows/ci.yml GitHub Actions CI/CD pipeline (YAML)

Layer 3: Application Configuration Files
├── config/database.yaml          Database connection, pool settings
├── config/markets.yaml           Market selection, edge thresholds, Kelly fractions
├── config/probability_models.yaml Model weights, ensemble config
├── config/trade_strategies.yaml   Strategy versions, entry/exit rules
├── config/position_management.yaml Trailing stops, profit targets, correlation limits
├── config/trading.yaml            Circuit breakers, position sizing, risk limits
└── config/logging.yaml            Log levels, rotation, output formats

Layer 4: Documentation Files
├── docs/foundation/MASTER_REQUIREMENTS*.md    Requirement definitions
├── docs/foundation/ARCHITECTURE_DECISIONS*.md  ADR definitions
├── docs/guides/*.md                            Implementation guides
└── CLAUDE.md                                   Development patterns
```

**ALWAYS Update ALL Layers When:**

**Scenario 1: Migrating Tools** (e.g., Bandit → Ruff)
- [ ] Update `pyproject.toml` - Remove `[tool.bandit]`, update `[tool.ruff]`
- [ ] Update `.pre-commit-config.yaml` - Change hook from `bandit` to `ruff --select S`
- [ ] Update `.git/hooks/pre-push` - Change security scan command + comments
- [ ] Update `.github/workflows/ci.yml` - Change CI job from `bandit` to `ruff`
- [ ] Update `CLAUDE.md` - Update pre-commit/pre-push documentation
- [ ] Update `SESSION_HANDOFF.md` - Document the migration

**Scenario 2: Changing Application Requirements** (e.g., min_edge threshold)

Example: REQ-TRADE-005 changes minimum edge from 0.05 to 0.08

- [ ] Update `docs/foundation/MASTER_REQUIREMENTS*.md` - Change requirement
- [ ] Update `config/markets.yaml` - Update all `min_edge` values in each league/category
- [ ] Update `config/trade_strategies.yaml` - Update strategy-specific edge thresholds
- [ ] Update `config/trading.yaml` - Update `position_sizing.kelly.min_edge_threshold`
- [ ] Update `docs/guides/CONFIGURATION_GUIDE*.md` - Update examples
- [ ] Run validation: `python scripts/validate_docs.py` (checks YAML files!)
- [ ] Commit ALL files together atomically

**Scenario 3: Adding New Validation Checks**

Example: Adding new Ruff rule (like S608 for SQL injection)

- [ ] Update `pyproject.toml` - Add rule to `[tool.ruff.lint].select`
- [ ] Update `.pre-commit-config.yaml` - Add `--select S608` to args (if needed)
- [ ] Update `.git/hooks/pre-push` - Document new check in comments
- [ ] Update `.github/workflows/ci.yml` - Ensure CI runs new check
- [ ] Update `CLAUDE.md` - Document new check in validation section

**Validation Commands:**

```bash
# Layer 1: Check pyproject.toml syntax
python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"

# Layer 2: Test pre-push hooks locally
bash .git/hooks/pre-push

# Layer 3: Validate YAML configs (DECIMAL SAFETY CHECK)
python scripts/validate_docs.py
# Checks for float contamination in config/*.yaml files

# Layer 4: Validate documentation consistency
python scripts/validate_docs.py
```

**YAML Configuration Validation (Already Implemented!):**

The `validate_docs.py` script (Check #9) automatically checks:
- ✅ All 7 config/*.yaml files for YAML syntax errors
- ✅ **Decimal safety** - Detects float values in price/probability fields
- ✅ **Schema consistency** - Ensures required fields present

**Decimal Safety in YAML Files:**

```yaml
# ❌ WRONG - Float contamination (causes rounding errors)
platforms:
  kalshi:
    fees:
      taker_fee_percent: 0.07      # Float!
    categories:
      sports:
        leagues:
          nfl:
            min_edge: 0.05           # Float!
            kelly_fraction: 0.25     # Float!

# ✅ CORRECT - String format (converted to Decimal by config_loader.py)
platforms:
  kalshi:
    fees:
      taker_fee_percent: "0.07"    # String → Decimal
    categories:
      sports:
        leagues:
          nfl:
            min_edge: "0.05"         # String → Decimal
            kelly_fraction: "0.25"   # String → Decimal
```

**Why String Format in YAML?**
- YAML parser treats `0.05` as float (64-bit binary)
- Float: `0.05` → `0.050000000000000003` (rounding error!)
- String: `"0.05"` → `Decimal("0.05")` → `0.0500` (exact!)
- ConfigLoader converts strings to Decimal automatically (see `config_loader.py:decimal_conversion=True`)

**Configuration Migration Checklist (Template):**

```markdown
## Configuration Migration: [Tool/Requirement Name]

**Date:** YYYY-MM-DD
**Reason:** [Why migrating? Performance, Python 3.14 compat, new feature?]

**Layer 1: Tool Configuration**
- [ ] `pyproject.toml` - [Specific changes]
- [ ] `.pre-commit-config.yaml` - [Specific changes]
- [ ] Validated syntax: `python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"`

**Layer 2: Pipeline Configuration**
- [ ] `.git/hooks/pre-push` - [Specific changes]
- [ ] `.github/workflows/ci.yml` - [Specific changes]
- [ ] Tested pre-push hooks: `bash .git/hooks/pre-push`

**Layer 3: Application Configuration** (if applicable)
- [ ] `config/[specific].yaml` - [Specific changes]
- [ ] Validated YAML: `python scripts/validate_docs.py`
- [ ] Checked Decimal safety: No float contamination warnings

**Layer 4: Documentation**
- [ ] `CLAUDE.md` - [Specific changes]
- [ ] `SESSION_HANDOFF.md` - [Specific changes]
- [ ] Relevant guides updated

**Validation:**
- [ ] All tests passing: `python -m pytest tests/ -v`
- [ ] Pre-push hooks passing: `bash .git/hooks/pre-push`
- [ ] YAML configs valid: `python scripts/validate_docs.py`
- [ ] No configuration drift detected

**Commit:**
```bash
git add pyproject.toml .pre-commit-config.yaml .git/hooks/pre-push .github/workflows/ci.yml CLAUDE.md
git commit -m "[Tool/Req]: [Migration description]

Layer 1: Tool configuration updates
Layer 2: Pipeline configuration updates
Layer 3: Application configuration updates (if applicable)
Layer 4: Documentation updates

All 4 layers synchronized to prevent configuration drift.
"
```
```

**Common Configuration Drift Scenarios:**

| Scenario | Layers Affected | Checklist |
|----------|----------------|-----------|
| **Tool migration** (Bandit→Ruff) | 1, 2, 4 | Update pyproject.toml, hooks, CI, docs |
| **Requirement change** (min_edge) | 3, 4 | Update config/*.yaml, MASTER_REQUIREMENTS, guides |
| **New validation rule** | 1, 2, 4 | Update pyproject.toml, hooks, CI, docs |
| **Python version upgrade** | 1, 2 | Update pyproject.toml, CI matrix |
| **Decimal precision fix** | 3 | Update all config/*.yaml floats → strings |
| **Security rule change** | 1, 2, 4 | Update ruff S-rules, hooks, docs |

**Prevention Strategy:**

1. **Atomic commits** - Commit all layers together in ONE commit
2. **Validation scripts** - Run `validate_docs.py` before every commit (catches YAML drift)
3. **Pre-push hooks** - Catch configuration errors locally (30-60s vs 2-5min CI)
4. **Documentation** - Always update CLAUDE.md when changing validation pipeline
5. **Session handoff** - Document configuration changes in SESSION_HANDOFF.md
6. **Checklists** - Use migration checklist template above

**Reference:**
- Pattern 1: Decimal Precision (why string format matters)
- Pattern 4: Security (no hardcoded credentials in any config layer)
- `scripts/validate_docs.py` - YAML validation implementation (Check #9)
- `config/config_loader.py` - String → Decimal conversion logic

---

## Pattern 9: Multi-Source Warning Governance (MANDATORY)

**WHY:** Warnings from **multiple validation systems** (pytest, validate_docs, Ruff, Mypy) were being tracked inconsistently. Without comprehensive governance, warnings accumulate silently until they block development.

**The Problem We Fixed:**
- Initial governance only tracked pytest warnings (41)
- Missed 388 warnings from validate_docs.py (YAML floats, MASTER_INDEX issues, ADR gaps)
- Validate_docs.py treated YAML floats as "warnings" not "errors" → wouldn't fail builds!
- Total: 429 warnings across 3 validation systems (BASELINE: 2025-11-08)

**Current Status (2025-11-09):**
- **YAML warnings ELIMINATED:** 111 → 0 (100% fixed in Phase 1.5)
- **pytest warnings reduced:** 41 → 32 (-9 warnings)
- **ADR warnings RECLASSIFIED:** Changed from "informational" to "actionable" per user feedback
- **New baseline:** 312 warnings (down from 429, -27% improvement)
- **check_warning_debt.py INTEGRATED:** Now runs in pre-push hooks (Step 5/5)

**Three Warning Sources:**

```
Source 1: pytest Test Warnings (32 total, was 41)
├── Hypothesis decimal precision (17, was 19)
├── ResourceWarning unclosed files (11, was 13)
├── pytest-asyncio deprecation (4)
└── structlog UserWarning (1)

Source 2: validate_docs.py Warnings (280 total, was 388)
├── ADR non-sequential numbering (231) - NOW ACTIONABLE ⚠️
├── YAML float literals (0, was 111) - ✅ FIXED!
├── MASTER_INDEX missing docs (29, was 27)
├── MASTER_INDEX deleted docs (12, was 11)
└── MASTER_INDEX planned docs (8) - Expected

Source 3: Code Quality (0 total)
├── Ruff linting errors (0)
└── Mypy type errors (0)
```

**Warning Classification (UPDATED 2025-11-09):**
- **Actionable (313, was 182):** ALL warnings now actionable (ADR gaps reclassified)
- **Informational (0, was 231):** Zero informational warnings (ADR gaps → actionable)
- **Expected (8, was 16):** Only truly expected warnings (planned docs)
- **Upstream (4):** Dependency issues (pytest-asyncio Python 3.16 compat)

**ALWAYS Track Warnings Across ALL Sources:**

```bash
# Multi-source validation (automated in check_warning_debt.py)
python scripts/check_warning_debt.py

# Manual verification (4 sources)
python -m pytest tests/ -v -W default --tb=no  # pytest warnings
python scripts/validate_docs.py                # Documentation warnings
python -m ruff check .                         # Linting errors
python -m mypy .                               # Type errors
```

**Governance Infrastructure:**

**1. warning_baseline.json (312 warnings locked, was 429)**
```json
{
  "baseline_date": "2025-11-09",
  "total_warnings": 312,
  "warning_categories": {
    "yaml_float_literals": {"count": 0, "target_phase": "DONE"},
    "hypothesis_decimal_precision": {"count": 17, "target_phase": "1.5"},
    "resource_warning_unclosed_files": {"count": 11, "target_phase": "1.5"},
    "master_index_missing_docs": {"count": 29, "target_phase": "1.5"},
    "master_index_deleted_docs": {"count": 12, "target_phase": "1.5"},
    "adr_non_sequential_numbering": {"count": 231, "actionable": true, "target_phase": "2.0"}
  },
  "governance_policy": {
    "max_warnings_allowed": 312,
    "new_warning_policy": "fail",
    "regression_tolerance": 0,
    "notes": "UPDATED 2025-11-09: -117 warnings (-27%), YAML floats eliminated, ADR gaps reclassified"
  }
}
```

**2. WARNING_DEBT_TRACKER.md (comprehensive tracking)**
- Documents all 312 warnings across 3 sources (was 429)
- Categorizes by actionability (313 actionable, 0 informational, 8 expected)
- Tracks deferred fixes (WARN-001 through WARN-007)
- Documents fix priorities, estimates, target phases
- Provides measurement commands for all sources
- **UPDATED 2025-11-09:** Reflects YAML elimination and ADR reclassification

**3. check_warning_debt.py (automated validation) - NOW INTEGRATED**
- Runs all 4 validation sources (pytest, validate_docs, Ruff, Mypy)
- Compares against baseline (312 warnings, was 429)
- **NOW RUNS IN PRE-PUSH HOOKS (Step 5/5)** - blocks pushes with regression
- Fails CI if new warnings detected
- Provides comprehensive breakdown by source

**Enforcement Rules (UPDATED 2025-11-09):**

1. **Baseline Locked:** 312 warnings (313 actionable, was 429/182)
2. **Zero Regression:** New warnings → pre-push hooks FAIL → **OPTIONS:**
   - **Option A: Fix immediately** (recommended)
   - **Option B: Defer with tracking** (create WARN-XXX in WARNING_DEBT_TRACKER.md)
   - **Option C: Update baseline** (requires approval + documentation)
3. **Baseline Warnings:** All 312 existing warnings MUST be tracked as deferred tasks
   - Each category needs WARN-XXX entry (already exists: WARN-001 through WARN-007)
   - Each entry documents: priority, estimate, target phase, fix plan
   - **NOT acceptable:** "Locked baseline, forget about it"
4. **Phase Targets:** Reduce by 80-100 warnings per phase (Phase 1.5: -117 achieved!)
5. **Zero Goal:** Target <100 actionable warnings by Phase 2 completion

**Integration Points (UPDATED 2025-11-09):**

```bash
# Pre-push hooks (runs automatically on git push) - NOW INTEGRATED!
bash .git/hooks/pre-push
# → Step 5/5: python scripts/check_warning_debt.py (multi-source check)
# → Enforces 312-warning baseline locally BEFORE CI

# CI/CD (.github/workflows/ci.yml)
# → Job: warning-governance
#   Runs: python scripts/check_warning_debt.py
#   Blocks merge if warnings exceed baseline (312)
```

**Example Workflow:**

```bash
# 1. Developer adds code that introduces new warning
git add feature.py
git commit -m "Add feature X"

# 2. Pre-push hooks run (automatic) - check_warning_debt.py runs at Step 5/5
git push
# → check_warning_debt.py detects 313 warnings (baseline: 312)
# → [FAIL] Warning count: 313/312 (+1 new warning)
# → Push blocked locally (BEFORE hitting CI!)

# 3. Developer has THREE OPTIONS:

# OPTION A: Fix immediately (recommended)
# Fix the warning in code, then re-push
git push
# → [OK] Warning count: 312/312 (baseline maintained)

# OPTION B: Defer with tracking (acceptable if documented)
# 1. Add entry to docs/utility/WARNING_DEBT_TRACKER.md:
#    WARN-008: New Hypothesis warning from edge case test (1 warning)
#    - Priority: Medium, Estimate: 1 hour, Target Phase: 1.6
# 2. Update baseline: python scripts/check_warning_debt.py --update
# 3. Commit WARNING_DEBT_TRACKER.md + warning_baseline.json
# 4. Push (now passes with 313 baseline)

# OPTION C: Update baseline without tracking (NOT RECOMMENDED)
# Only acceptable for:
# - Upstream dependency warnings (pytest-asyncio, etc.)
# - False positives from validation tools
# Otherwise, use Option B (defer with tracking)
```

**Acceptable Baseline Updates:**

You MAY update the baseline IF:
1. **New validation source** added (e.g., adding Bandit security scanner)
2. **Upstream dependency** introduces warnings (e.g., pytest-asyncio Python 3.16 compat)
3. **Intentional refactor** creates temporary warnings (document + target phase to fix)

You MUST document in WARNING_DEBT_TRACKER.md:
```markdown
### Baseline Update: 2025-11-09 - YAML Elimination + ADR Reclassification

**Previous Baseline:** 429 warnings
**New Baseline:** 312 warnings (-117, -27% improvement)

**Changes:**
- ELIMINATED: YAML float warnings (111 → 0) - Fixed in Phase 1.5
- REDUCED: pytest warnings (41 → 32) - Property test improvements
- RECLASSIFIED: ADR non-sequential warnings (231) from informational → actionable
- INTEGRATED: check_warning_debt.py into pre-push hooks (Step 5/5)

**Approval:** Approved by [Name] on [Date]
**Next Action:** Fix WARN-008 in Phase 1.5 (target: -6 warnings)
```

**Common Mistakes:**

```python
# ❌ WRONG - Only checking pytest warnings
def check_warnings():
    pytest_output = run_pytest()
    count = extract_warning_count(pytest_output)
    # Misses validate_docs warnings!

# ✅ CORRECT - Multi-source validation
def check_warnings():
    pytest_count = run_pytest_warnings()
    docs_count = run_validate_docs()
    ruff_count = run_ruff()
    mypy_count = run_mypy()
    total = pytest_count + sum(docs_count.values()) + ruff_count + mypy_count
    return total  # Comprehensive
```

**Files Modified:**
- `scripts/warning_baseline.json` - Baseline (152 → 429 warnings)
- `scripts/check_warning_debt.py` - Multi-source validation
- `docs/utility/WARNING_DEBT_TRACKER.md` - Comprehensive tracking
- `CLAUDE.md` - This pattern
- `docs/foundation/ARCHITECTURE_DECISIONS*.md` - ADR-054 (Warning Governance Architecture)

**Reference:**
- WARNING_DEBT_TRACKER.md - Comprehensive warning documentation
- warning_baseline.json - Locked baseline configuration
- check_warning_debt.py - Automated validation script
- ADR-054: Warning Governance Architecture
- Pattern 5: Cross-Platform Compatibility (ASCII output for Windows)

---

## Pattern 10: Property-Based Testing with Hypothesis (ALWAYS for Trading Logic)

**WHY:** Trading logic has **mathematical invariants** that MUST hold for ALL inputs. Example-based tests validate 5-10 cases. Property-based tests validate thousands of cases automatically, catching edge cases humans miss.

**The Difference:**

```python
# ❌ EXAMPLE-BASED TEST - Tests 1 specific case
def test_kelly_criterion_example():
    position = calculate_kelly_size(
        edge=Decimal("0.10"),
        kelly_fraction=Decimal("0.25"),
        bankroll=Decimal("10000")
    )
    assert position == Decimal("250")  # What if edge = 0.9999999?

# ✅ PROPERTY-BASED TEST - Tests 100+ cases automatically
@given(
    edge=edge_value(),           # Generates edge ∈ [-0.5, 0.5]
    kelly_frac=kelly_fraction(), # Generates kelly ∈ [0, 1]
    bankroll=bankroll_amount()   # Generates bankroll ∈ [$100, $100k]
)
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """PROPERTY: Position ≤ bankroll ALWAYS (prevents margin calls)"""
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll  # Validates 100+ combinations
```

**ALWAYS Use Property Tests For:**

1. **Mathematical Invariants:**
   - Position size ≤ bankroll (prevents margin calls)
   - Bid price ≤ ask price (no crossed markets)
   - Trailing stop price NEVER loosens (one-way ratchet)
   - Probability ∈ [0, 1] (always bounded)
   - Kelly fraction ∈ [0, 1] (validated at config load)

2. **Business Rules:**
   - Negative edge → don't trade (prevents guaranteed losses)
   - Stop loss overrides all other exits (safety first)
   - Exit price within slippage tolerance (risk management)

3. **State Transitions:**
   - Position lifecycle: open → monitoring → exited (valid transitions only)
   - Strategy status: draft → testing → active → deprecated (no invalid jumps)
   - Trailing stop updates: current_stop = max(old_stop, new_stop) (never decreases)

4. **Data Validation:**
   - Timestamp ordering monotonic (no time travel)
   - Score progression never decreases (game logic)
   - Model outputs ∈ valid range (prediction bounds)

**Custom Hypothesis Strategies (Trading Domain):**

Create reusable generators in `tests/property/strategies.py`:

```python
from hypothesis import strategies as st
from decimal import Decimal

@st.composite
def probability(draw, min_value=0, max_value=1, places=4):
    """Generate valid probabilities [0, 1] as Decimal."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))

@st.composite
def bid_ask_spread(draw, min_spread=0.0001, max_spread=0.05):
    """Generate realistic bid-ask spreads with bid < ask constraint."""
    bid = draw(st.decimals(min_value=0, max_value=0.99, places=4))
    spread = draw(st.decimals(min_value=min_spread, max_value=max_spread, places=4))
    ask = bid + spread
    return (bid, ask)

@st.composite
def price_series(draw, length=10, volatility=Decimal("0.05")):
    """Generate realistic price movement series."""
    start_price = draw(st.decimals(min_value=0.40, max_value=0.60, places=4))
    prices = [start_price]
    for _ in range(length - 1):
        change = draw(st.decimals(min_value=-volatility, max_value=volatility, places=4))
        new_price = max(Decimal("0.01"), min(Decimal("0.99"), prices[-1] + change))
        prices.append(new_price)
    return prices
```

**Why Custom Strategies Matter:**
- Generate **domain-valid** inputs only (no wasted test cases on negative prices)
- Encode constraints once, reuse everywhere (bid < ask, probability ∈ [0, 1])
- Improve Hypothesis shrinking (finds minimal failing examples faster)
- Document domain assumptions (probabilities are Decimal, not float)

**Hypothesis Shrinking - Automatic Bug Minimization:**

When a property test fails, Hypothesis **automatically** finds the simplest failing example:

```python
# Failing test:
@given(edge=edge_value(), kelly_frac=kelly_fraction(), bankroll=bankroll_amount())
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll

# Initial failure (complex):
# edge=0.473821, kelly_frac=0.87, bankroll=54329.12
# position=54330.00 > bankroll (BUG!)

# After shrinking (<1 second):
# edge=0.5, kelly_frac=1.0, bankroll=100.0
# position=101.0 > bankroll (minimal example reveals bug)

# Root cause: Forgot to cap position at bankroll!
# Fix: position = min(calculated_position, bankroll)
```

**When to Use Property Tests vs. Example Tests:**

| Test Type | Use For | Example |
|-----------|---------|---------|
| **Property Test** | Mathematical invariants | Position ≤ bankroll |
| **Property Test** | Business rules | Negative edge → don't trade |
| **Property Test** | State transitions | Trailing stop only tightens |
| **Property Test** | Data validation | Probability ∈ [0, 1] |
| **Example Test** | Specific known bugs | Regression test for Issue #42 |
| **Example Test** | Integration with APIs | Mock Kalshi API response |
| **Example Test** | Complex business scenarios | Halftime entry strategy |
| **Example Test** | User-facing behavior | CLI output format |
| **Example Test** | Performance benchmarks | Test runs in <100ms |

**Best Practice:** Use **both**. Property tests validate invariants, example tests validate specific scenarios.

**Configuration (`pyproject.toml`):**

```toml
[tool.hypothesis]
max_examples = 100          # Test 100 random inputs per property
verbosity = "normal"         # Show shrinking progress
database = ".hypothesis/examples"  # Cache discovered edge cases
deadline = 400              # 400ms timeout per example (prevents infinite loops)
derandomize = false         # True for debugging (reproducible failures)
```

**Project Status:**

**✅ Phase 1.5 Proof-of-Concept (COMPLETE):**
- `tests/property/test_kelly_criterion_properties.py` - 11 properties, 1100+ cases
- `tests/property/test_edge_detection_properties.py` - 16 properties, 1600+ cases
- Custom strategies: `probability()`, `market_price()`, `edge_value()`, `kelly_fraction()`, `bankroll_amount()`
- **Critical invariants validated:**
  - Position ≤ bankroll (prevents margin calls)
  - Negative edge → don't trade (prevents losses)
  - Trailing stop only tightens (never loosens)
  - Edge accounts for fees and spread (realistic P&L)

**🔵 Full Implementation Roadmap (Phases 1.5-5):**
- Phase 1.5: Config validation, position sizing (40+ properties)
- Phase 2: Historical data, model validation, strategy versioning (35+ properties)
- Phase 3: Order book, entry optimization (25+ properties)
- Phase 4: Ensemble models, backtesting (30+ properties)
- Phase 5: Position lifecycle, exit optimization, reporting (45+ properties)
- **Total: 165 properties, 16,500+ test cases**

**Writing Property Tests - Quick Start:**

```python
# 1. Import Hypothesis
from hypothesis import given
from hypothesis import strategies as st
from decimal import Decimal

# 2. Define custom strategy (if needed)
@st.composite
def edge_value(draw):
    return draw(st.decimals(min_value=-0.5, max_value=0.5, places=4))

# 3. Write property test with @given decorator
@given(edge=edge_value(), kelly_frac=kelly_fraction(), bankroll=bankroll_amount())
def test_position_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """PROPERTY: Position ≤ bankroll (prevents margin calls)"""
    position = calculate_kelly_size(edge, kelly_frac, bankroll)
    assert position <= bankroll, f"Position {position} > bankroll {bankroll}!"

# 4. Run with pytest
# pytest tests/property/test_kelly_criterion_properties.py -v
```

**Common Pitfalls:**

```python
# ❌ WRONG - Testing implementation details
@given(edge=edge_value())
def test_kelly_formula_calculation(edge):
    # Don't test "how" calculation is done, test "what" properties hold
    assert calculate_kelly_size(edge, ...) == edge * kelly_frac * bankroll

# ✅ CORRECT - Testing invariants
@given(edge=edge_value())
def test_negative_edge_means_no_trade(edge):
    if edge < 0:
        position = calculate_kelly_size(edge, kelly_frac, bankroll)
        assert position == Decimal("0")  # Property: negative edge → don't trade
```

```python
# ❌ WRONG - Unconstrained inputs waste test cases
@given(price=st.floats())  # Generates NaN, inf, negative prices
def test_bid_less_than_ask(price):
    # Most generated prices are invalid (negative, >1, NaN)
    # Hypothesis spends 90% of time on invalid inputs

# ✅ CORRECT - Constrained inputs focus on valid domain
@given(bid=st.decimals(min_value=0, max_value=0.99, places=4))
def test_bid_less_than_ask(bid):
    ask = bid + Decimal("0.01")  # Valid constraint
    # All generated bids are valid, tests are efficient
```

**Performance:**
- Property tests are slower (100 examples vs. 1 example)
- Phase 1.5: 26 properties = 2600 cases in 3.32s (acceptable)
- Full implementation: 165 properties = 16,500 cases in ~30-40s (acceptable)
- CI/CD impact: +30-40 seconds (total ~90-120 seconds)
- Mitigation: Run in parallel, use `max_examples=20` in CI

**Documentation:**
- **Requirements:** REQ-TEST-008 (complete), REQ-TEST-009 through REQ-TEST-011 (planned)
- **Architecture:** ADR-074 (Property-Based Testing Strategy)
- **Implementation Plan:** `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` (comprehensive roadmap)
- **Proof-of-Concept:** `tests/property/test_kelly_criterion_properties.py`, `tests/property/test_edge_detection_properties.py`

**Reference:**
- Pattern 1: Decimal Precision (use Decimal in custom strategies, never float)
- Pattern 7: Educational Docstrings (explain WHY properties matter in docstrings)
- ADR-074: Full rationale for property-based testing adoption
- REQ-TEST-008: Proof-of-concept completion details

---

## Pattern 11: Test Mocking Patterns (Mock API Boundaries, Not Implementation)

**WHY:** Tests that mock **internal implementation details** instead of **public APIs** are fragile. When internal implementation changes (even if public API stays the same), tests break unnecessarily. This creates false negatives and erodes confidence in the test suite.

**The Antipattern:**

Mocking internal implementation details that are **not part of the public contract**:

```python
# ❌ WRONG - Mocking internal implementation (.load method)
@patch("config.config_loader.ConfigLoader")
def test_config_show_bad(mock_config_loader, runner):
    """FRAGILE: Breaks if ConfigLoader refactors .load() internally."""
    mock_config_loader.return_value.load.return_value = {
        "kelly_criterion": {"max_bet_size": "0.05"}
    }

    # CLI uses .get() method, but we mocked .load()!
    result = runner.invoke(app, ["config-show", "trading.yaml"])

    # Test fails even though public API (.get()) works fine
    assert result.exit_code == 0  # ❌ FAILS - .get() was never mocked!
```

**Why This Fails:**
1. **Implementation Detail:** `.load()` is an internal method used by ConfigLoader
2. **Public API:** `.get(file, key_path)` is what CLI commands actually call
3. **Coupling:** Test is coupled to implementation, not behavior
4. **False Negative:** Test fails when internal refactoring happens, even if public API unchanged

**The Correct Pattern:**

Mock the **public API** that your code actually uses:

```python
# ✅ CORRECT - Mocking public API (.get method)
@patch("config.config_loader.ConfigLoader")
def test_config_show_good(mock_config_loader, runner):
    """ROBUST: Tests actual public API contract."""
    # Mock the .get() method that CLI actually calls
    mock_config_loader.return_value.get.return_value = {
        "kelly_criterion": {"max_bet_size": "0.05"}
    }

    # CLI calls .get(), we mocked .get() ✅
    result = runner.invoke(app, ["config-show", "trading.yaml"])

    assert result.exit_code == 0  # ✅ PASSES
    assert "max_bet_size" in result.stdout
```

**Real-World Examples from Precog:**

### Example 1: ConfigLoader Mocking (PR #19 and PR #20)

**Problem:** TestConfigValidate and TestConfigShow were both mocking `.load()` but CLI commands use `.get()`.

**Files Affected:**
- `tests/unit/test_main.py` (lines 1875-2037: TestConfigValidate)
- `tests/unit/test_main.py` (lines 2128-2290: TestConfigShow)

**Fix Pattern:**

```python
# ❌ WRONG (old code)
mock_config_loader.return_value.load.return_value = {...}

# ✅ CORRECT (fixed code)
mock_config_loader.return_value.get.return_value = {...}
```

**ConfigLoader Public API:**
```python
class ConfigLoader:
    def get(self, config_file: str, key_path: str | None = None) -> Any:
        """Public API - Use this in CLI commands."""
        # Returns entire config dict if key_path is None
        # Returns nested value if key_path provided (e.g., "kelly_criterion.max_bet_size")

    def load(self, filename: str) -> dict:
        """Internal implementation - DO NOT mock this in tests!"""
        # Used internally by .get(), may change in future refactoring
```

**Correct Mocking Patterns:**

```python
# Pattern 1: Mock .get() for entire config file
@patch("config.config_loader.ConfigLoader")
def test_show_entire_file(mock_config_loader, runner):
    mock_config_loader.return_value.get.return_value = {
        "kelly_criterion": {"max_bet_size": "0.05"},
        "enabled": True
    }
    result = runner.invoke(app, ["config-show", "trading.yaml"])
    assert "kelly_criterion" in result.stdout

# Pattern 2: Mock .get() for nested key path
@patch("config.config_loader.ConfigLoader")
def test_show_specific_key(mock_config_loader, runner):
    # .get(file, key_path) returns direct value for nested keys
    mock_config_loader.return_value.get.return_value = "0.05"
    result = runner.invoke(app, ["config-show", "trading.yaml", "--key", "kelly_criterion.max_bet_size"])
    assert "0.05" in result.stdout

# Pattern 3: Mock .get() with side_effect for errors
@patch("config.config_loader.ConfigLoader")
def test_show_missing_file(mock_config_loader, runner):
    mock_config_loader.return_value.get.side_effect = FileNotFoundError("Config not found")
    result = runner.invoke(app, ["config-show", "missing.yaml"])
    assert result.exit_code == 1

# Pattern 4: Mock .get() with side_effect list (multiple calls)
@patch("config.config_loader.ConfigLoader")
def test_show_invalid_key(mock_config_loader, runner):
    # First call: .get(file, bad_key) raises KeyError
    # Second call: .get(file) returns full config to show available keys
    mock_config_loader.return_value.get.side_effect = [
        KeyError("invalid.key"),
        {"kelly_criterion": {"max_bet_size": "0.05"}}
    ]
    result = runner.invoke(app, ["config-show", "trading.yaml", "--key", "invalid.key"])
    assert result.exit_code == 1
    assert "kelly_criterion" in result.stdout  # Shows available keys
```

**Mocking Hierarchy (Most Fragile → Most Robust):**

| Level | What to Mock | Fragility | Example |
|-------|--------------|-----------|---------|
| **1. Internal Details** | Private methods, internal state | 🔴 VERY FRAGILE | `.load()`, `._cache`, `._http_client` |
| **2. External Dependencies** | HTTP clients, file I/O | 🟡 MODERATELY FRAGILE | `requests.Session`, `open()` |
| **3. Public API Boundary** | Public methods, interfaces | 🟢 ROBUST | `.get()`, `.fetch_markets()`, `.calculate_kelly()` |
| **4. Integration Tests** | Real dependencies (test mode) | 🟢 MOST ROBUST | Live test database, demo API |

**Best Practices:**

1. **Mock at API Boundaries:**
   - ✅ Mock: `.get()`, `.fetch_markets()`, `.calculate_position()`
   - ❌ Don't Mock: `.load()`, `._parse_yaml()`, `._validate()`

2. **Test Public Contracts:**
   - Mock the methods **your code actually calls**
   - Don't mock methods **your code doesn't call**

3. **Use side_effect for Multiple Calls:**
   ```python
   # If function calls .get() multiple times with different behaviors:
   mock.get.side_effect = [
       first_return_value,
       second_return_value,
       KeyError("third call fails")
   ]
   ```

4. **Match Return Types:**
   ```python
   # If .get() returns dict, mock should return dict
   mock.get.return_value = {"key": "value"}

   # If .get() returns Decimal, mock should return Decimal
   mock.get.return_value = Decimal("0.52")

   # If .get() raises exception, use side_effect
   mock.get.side_effect = FileNotFoundError("Not found")
   ```

5. **Validate Mock Was Called Correctly:**
   ```python
   # Verify your code called the mocked method with correct args
   result = client.get("trading.yaml", "kelly_criterion.max_bet_size")
   mock.get.assert_called_once_with("trading.yaml", "kelly_criterion.max_bet_size")
   ```

**When Mocking is NOT the Answer:**

Sometimes integration tests are better than mocked unit tests:

```python
# ❌ Over-mocking obscures real behavior
@patch("config.config_loader.ConfigLoader.get")
@patch("api_connectors.kalshi_client.KalshiClient.fetch_markets")
@patch("trading.position_manager.PositionManager.open_position")
def test_entire_trading_flow_with_mocks(mock1, mock2, mock3):
    """TOO MANY MOCKS - Not testing real integration!"""
    # This test doesn't validate actual interactions

# ✅ Integration test with real components (test mode)
def test_entire_trading_flow_integration(test_db, demo_api):
    """Tests real interactions with test fixtures."""
    config = ConfigLoader().get("trading.yaml")  # Real config loading
    client = KalshiClient(mode="demo")  # Real API (demo endpoint)
    manager = PositionManager(db=test_db)  # Real database (test instance)
    # Validates actual end-to-end behavior
```

**Lessons from PR #19 and PR #20:**

1. **Same Mistake Twice:** Both TestConfigValidate and TestConfigShow made the same mocking error
2. **Root Cause:** Tests were written by copy-paste without understanding public API
3. **Prevention:** Document public API contracts clearly in docstrings
4. **Fix Pattern:** Search for `.return_value.load` and replace with `.return_value.get`

**Quick Decision Tree:**

```
Q: Should I mock this method?
├─ Is it called by my code?
│  ├─ YES → Continue
│  └─ NO → Don't mock it (not part of test)
├─ Is it part of the public API?
│  ├─ YES → Safe to mock ✅
│  └─ NO (private/internal) → Don't mock (fragile) ❌
└─ Can I use a real instance instead (integration test)?
   ├─ YES → Prefer real instance 🟢
   └─ NO (too slow/complex) → Mock the public API ✅
```

**Impact on Test Maintenance:**

- **Before (Fragile Tests):** 11 tests broke when ConfigLoader refactored `.load()` implementation
- **After (Robust Tests):** 0 tests break when internal implementation changes (as long as `.get()` API unchanged)
- **Maintenance Cost:** Reduced test maintenance by 90% for ConfigLoader tests

**Reference:**
- PR #19: Fixed 5 TestConfigValidate tests (`.load()` → `.get()` pattern)
- PR #20: Fixed 5 TestConfigShow tests + 1 property test
- `config/config_loader.py` (lines 142-193): ConfigLoader public API documentation
- `tests/unit/test_main.py` (lines 1875-2290): Corrected mocking examples

---

## Pattern 12: Test Fixture Security Compliance (MANDATORY)

**When to Use:** When writing test fixtures for functions that include security validations (path traversal protection, file extension validation, etc.)

**The Problem:**
When production code adds security validations, existing test fixtures using `tmp_path` (system temp) can break because they create files outside the project directory.

**Example from PR #79:**
- PR #76 added path traversal protection to `apply_schema()` and `apply_migrations()`
- Security validation rejects files outside project: `is_relative_to(project_root)`
- Tests using `tmp_path` failed: files created in `C:\Users\...\AppData\Local\Temp\...`
- Error: `'Security: Schema file must be within project directory'`

### ✅ CORRECT Pattern: Project-Relative Test Files

```python
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_schema_file() -> Generator[str, None, None]:
    """Create temporary schema file within project for testing.

    Returns:
        Path to temporary schema file (project-relative for security validation)

    Educational Note:
        We create temp files WITHIN the project directory to pass security
        validation that prevents path traversal attacks. The file is cleaned
        up after the test via yield/finally pattern.
    """
    # Create project-relative temp directory
    project_root = Path.cwd()
    temp_dir = project_root / "tests" / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create unique schema file
    unique_id = uuid.uuid4().hex[:8]
    schema_file = temp_dir / f"test_schema_{unique_id}.sql"
    schema_file.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")

    try:
        yield str(schema_file)
    finally:
        # Cleanup
        if schema_file.exists():
            schema_file.unlink()
        # Clean up temp_dir if empty
        try:
            temp_dir.rmdir()
        except OSError:
            pass  # Directory not empty or doesn't exist
```

### ❌ WRONG Pattern: Using tmp_path with Security-Validated Functions

```python
@pytest.fixture
def temp_schema_file(tmp_path: Path) -> str:
    """Creates file in system temp - FAILS security validation!"""
    schema_file = tmp_path / "test_schema.sql"  # Outside project!
    schema_file.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")
    return str(schema_file)
    # Security validation fails: file not within project directory
```

### Key Implementation Details

**1. Use Generator Pattern with yield/finally**
- Type: `Generator[str, None, None]` (not `str`)
- `yield` provides fixture value to test
- `finally` ensures cleanup even if test fails

**2. UUID for Unique Filenames**
- `uuid.uuid4().hex[:8]` creates short unique IDs
- Prevents file collisions when tests run in parallel
- Example: `test_schema_a3f2b8c1.sql`

**3. Project-Relative Paths**
- Use `Path.cwd()` to get project root
- Create files in `tests/.tmp/` subdirectory
- Passes `is_relative_to(project_root)` security check

**4. Cleanup Strategy**
- Delete created files in `finally` block
- Try to remove temp_dir (may fail if other tests using it - that's OK)
- Graceful handling with `try/except OSError`

### When to Use This Pattern

**✅ Use project-relative fixtures when:**
- Function validates file paths (path traversal protection)
- Function checks file extensions (.sql, .yaml, etc.)
- Function uses `Path.resolve()` and `is_relative_to()`
- Function executes external commands with file paths (subprocess)

**❌ Use tmp_path when:**
- Testing file I/O operations (read/write/parse)
- No security validations on file location
- Function doesn't care where file is located
- Testing path manipulation itself

### Real-World Impact (PR #79)

**Before (using tmp_path):**
- 9/25 tests failing
- Coverage: 68.32%
- Error: "Security: Schema file must be within project directory"

**After (using project-relative):**
- 25/25 tests passing
- Coverage: 89.11% (+20.79pp)
- Security validation works correctly

### Common Mistakes

**Mistake 1: Forgetting to import Generator**
```python
# ❌ WRONG
def temp_schema_file() -> str:  # Missing Generator type

# ✅ CORRECT
from collections.abc import Generator

def temp_schema_file() -> Generator[str, None, None]:
```

**Mistake 2: Not using uuid (file collisions)**
```python
# ❌ WRONG (parallel tests collide)
schema_file = temp_dir / "test_schema.sql"

# ✅ CORRECT (unique per test)
unique_id = uuid.uuid4().hex[:8]
schema_file = temp_dir / f"test_schema_{unique_id}.sql"
```

**Mistake 3: Cleanup without error handling**
```python
# ❌ WRONG (fails if directory not empty)
temp_dir.rmdir()

# ✅ CORRECT (graceful handling)
try:
    temp_dir.rmdir()
except OSError:
    pass  # Directory not empty or doesn't exist
```

### Cross-References
- **PR #79:** Test initialization fixture fixes for security validation compatibility
- **PR #76:** Added path traversal protection (CWE-22) to `apply_schema()` and `apply_migrations()`
- **DEVELOPMENT_PHILOSOPHY_V1.2.md:** Security-First Testing principle
- **Pattern 4:** Security (NO CREDENTIALS IN CODE) - Related security best practices

---

## Pattern 13: Test Coverage Quality (Mock Sparingly, Integrate Thoroughly) - CRITICAL

**WHY:** Tests can pass with 100% test pass rate yet miss critical bugs. Phase 1.5 discovery: Strategy Manager had 17/17 tests passing with mocks, but 13/17 tests failed (77% failure rate) when refactored to use real database fixtures. Connection pool exhaustion bugs went completely undetected.

**The Critical Lesson:** "Tests passing" ≠ "Tests sufficient" ≠ "Code works correctly"

### The Problem: Over-Reliance on Mocks

**What went wrong:**

```python
# ❌ WRONG - Strategy Manager tests (17/17 passing, but implementation broken)
@patch("precog.trading.strategy_manager.get_connection")
def test_create_strategy(self, mock_get_connection, mock_connection, mock_cursor):
    """Test creates strategy - BUT DOESN'T TEST CONNECTION POOL!"""
    mock_get_connection.return_value = mock_connection
    mock_cursor.fetchone.return_value = (1, "strategy_v1", "1.0", ...)  # Fake response

    manager = StrategyManager()
    result = manager.create_strategy(...)  # Calls mock, not real DB

    assert result["strategy_id"] == 1  # ✅ Test passes!
    # But implementation has connection pool leak - not caught!
```

**Why this is catastrophic:**
- Mocks test "did we call the right function?" NOT "does the system work?"
- Mocks bypass integration bugs (connection pool exhaustion, transaction handling, constraint violations)
- Mocks provide false confidence - green tests, broken code
- In production: System crashes after 5 creates (connection pool exhausted)

### ✅ CORRECT Pattern: Real Infrastructure with Test Fixtures

```python
# ✅ CORRECT - Use real database with conftest.py fixtures
def test_create_strategy(clean_test_data, manager, strategy_factory):
    """Test creates strategy - TESTS REAL DATABASE!"""
    result = manager.create_strategy(**strategy_factory)  # Calls REAL database

    assert result["strategy_id"] is not None  # ✅ Test passes
    # If connection pool leak exists → test fails with pool exhausted error
    # If SQL syntax wrong → test fails with database error
    # If constraints violated → test fails with constraint error
```

### When to Use Mocks vs. Real Infrastructure

**✅ Mocks are APPROPRIATE for:**
- **External APIs** (Kalshi, ESPN, Polymarket) - expensive, rate-limited, flaky
- **Time-dependent code** (`datetime.now()`, `time.sleep()`)
- **Random number generation** (`random.random()`, `uuid.uuid4()`)
- **File I/O** (in some cases - when testing file handling logic, not content)
- **Network requests** (HTTP, WebSocket) - unreliable, slow

**❌ Mocks are NOT APPROPRIATE for:**
- **Database** (use test database with `clean_test_data` fixture)
- **Internal application logic** (strategy manager, model manager, position manager)
- **Configuration loading** (use test configs, not mocks)
- **Logging** (use test logger, capture output)
- **Connection pooling** (use `db_pool` fixture with real pool)

### ALWAYS Use Test Fixtures from conftest.py

**MANDATORY fixtures for database tests:**

```python
# conftest.py provides these fixtures - ALWAYS USE THEM
@pytest.fixture
def clean_test_data(db_pool):
    """Cleans database before/after each test. ALWAYS USE THIS."""
    # Deletes all test data before test runs
    # Ensures clean state
    # Automatically rolls back after test

@pytest.fixture
def db_pool():
    """Provides real connection pool. Use for pool-related tests."""
    # Real ThreadedConnectionPool with minconn=2, maxconn=5
    # Tests pool exhaustion scenarios
    # Automatically cleans up connections

@pytest.fixture
def db_cursor(db_pool):
    """Provides real database cursor. Use for SQL execution tests."""
    # Real psycopg2 cursor
    # Automatically commits/rolls back
    # Cleans up cursor after test
```

**Example usage:**

```python
# ✅ CORRECT - All manager tests use clean_test_data
def test_create_strategy(clean_test_data, manager, strategy_factory):
    """Uses real database, real connection pool, real SQL."""
    result = manager.create_strategy(**strategy_factory)
    assert result["strategy_id"] is not None
    # Database automatically cleaned up after test

def test_connection_pool_exhaustion(clean_test_data, db_pool):
    """Tests connection pool limits with REAL pool."""
    manager = StrategyManager()

    # Create 6 strategies (pool maxconn=5)
    for i in range(6):
        result = manager.create_strategy(
            strategy_name=f"test_strategy_{i}",
            strategy_version="1.0",
            approach="value",
            config={"test": True},
        )
        assert result["strategy_id"] is not None

    # If connection pool leak exists → test fails here
```

### 8 Required Test Types (Not Just Unit Tests)

**CRITICAL:** Trading applications need multiple test types, not just unit tests.

| Test Type | Purpose | When Required | Example |
|-----------|---------|---------------|---------|
| **Unit** | Isolated function logic | ✅ ALWAYS | `test_calculate_kelly_fraction()` |
| **Property** | Mathematical invariants | ✅ CRITICAL PATH | `test_decimal_precision_preserved()` |
| **Integration** | Components together | ✅ MANAGER LAYER | `test_strategy_manager_database()` |
| **End-to-End** | Complete workflows | ⚠️ PHASE 2+ | `test_trading_lifecycle()` |
| **Stress** | Infrastructure limits | ✅ CRITICAL | `test_connection_pool_exhaustion()` |
| **Race Condition** | Concurrent operations | ⚠️ PHASE 3+ | `test_concurrent_position_updates()` |
| **Performance** | Latency/throughput | ⏸️ PHASE 5+ | `test_order_execution_latency()` |
| **Chaos** | Failure recovery | ⏸️ PHASE 5+ | `test_database_failure_recovery()` |

**Phase 1.5 Requirements:**
- ✅ Unit tests (isolated logic)
- ✅ Property tests (Hypothesis for Kelly criterion, edge detection)
- ✅ Integration tests (manager layer + database)
- ✅ Stress tests (connection pool exhaustion)

### Coverage Standards: Percentage ≠ Quality

**The Aggregate Coverage Trap:**

```
Overall Coverage: 86.25% ✅ (looks good!)

But module breakdown reveals gaps:
├── Model Manager: 25.75% ❌ (target: ≥85%, gap: -59.25%)
├── Strategy Manager: 19.96% ❌ (target: ≥85%, gap: -65.04%)
├── Position Manager: 0% ❌ (not implemented yet)
├── Database Layer: 86.32% ✅ (target: ≥80%)
└── API Clients: 93.19% ✅ (target: ≥80%)
```

**Module-Level Coverage Targets:**
- **Critical Path** (trading execution, position monitoring): ≥90%
- **Manager Layer** (strategy, model, position managers): ≥85%
- **Infrastructure** (database, logging, config): ≥80%
- **API Clients** (Kalshi, ESPN): ≥80%
- **Utilities** (helpers, formatters): ≥75%

### Test Review Checklist (MANDATORY Before Marking Work Complete)

Run this checklist before marking any feature complete:

```markdown
## Test Quality Checklist

- [ ] **Tests use real infrastructure (database, not mocks)?**
  - ✅ Uses `clean_test_data` fixture
  - ✅ Uses `db_pool` fixture for pool tests
  - ❌ NO `@patch("get_connection")` mocks

- [ ] **Tests use fixtures from conftest.py?**
  - ✅ ALL database tests use `clean_test_data`
  - ✅ NO manual `mock_connection` or `mock_cursor` fixtures
  - ✅ Fixtures handle cleanup automatically

- [ ] **Tests cover happy path AND edge cases?**
  - ✅ Happy path (normal create/update/delete)
  - ✅ Edge cases (null values, empty strings, boundary conditions)
  - ✅ Failure modes (database errors, connection pool exhausted)

- [ ] **Tests cover failure modes?**
  - ✅ What happens when database fails?
  - ✅ What happens when connection pool exhausted?
  - ✅ What happens when invalid data provided?

- [ ] **Coverage percentage ≥ target for this module?**
  - ✅ Manager modules: ≥85%
  - ✅ Infrastructure modules: ≥80%
  - ✅ Critical path: ≥90%

- [ ] **Tests written BEFORE implementation (TDD)?**
  - ✅ Test written first (red)
  - ✅ Implementation written second (green)
  - ✅ Refactored (clean)

- [ ] **Multiple test types present?**
  - ✅ Unit tests (isolated logic)
  - ✅ Integration tests (database + application)
  - ✅ Property tests (if mathematical invariants)
  - ✅ Stress tests (if touches infrastructure limits)
```

### Real-World Impact: Strategy Manager Example

**Before (using mocks):**
- Tests: 17/17 passing (100% pass rate) ✅
- Coverage: 19.96% ❌
- Bugs found: 0 ✅
- **Production behavior:** System crashes after 5 creates (connection pool exhausted)

**After (using real infrastructure):**
- Tests: 13/17 failing (77% failure rate) ❌
- Coverage: TBD (to be increased to ≥85%)
- Bugs found: 1 critical (connection pool leak) ✅
- **Production behavior:** Would have been caught before deployment

**Key Learning:** 77% of Strategy Manager tests were providing false confidence. They passed because they never touched real infrastructure.

### Prevention: Multi-Layer Test Strategy

```python
# Layer 1: Unit tests (fast, isolated)
def test_calculate_edge_unit():
    """Tests edge calculation math (no database)."""
    from precog.trading.strategy_manager import calculate_edge

    true_prob = Decimal("0.6")
    market_price = Decimal("0.5")
    edge = calculate_edge(true_prob, market_price)

    assert edge == Decimal("0.1")  # 60% - 50% = 10% edge

# Layer 2: Integration tests (real database)
def test_create_strategy_integration(clean_test_data, manager, strategy_factory):
    """Tests strategy creation with REAL database."""
    result = manager.create_strategy(**strategy_factory)

    assert result["strategy_id"] is not None
    # Verifies:
    # - SQL syntax correct
    # - Connection pool works
    # - Transactions commit
    # - Constraints enforced

# Layer 3: Stress tests (infrastructure limits)
def test_connection_pool_stress(clean_test_data):
    """Tests connection pool exhaustion with 10 concurrent creates."""
    import concurrent.futures

    def create_strategy(i):
        manager = StrategyManager()
        return manager.create_strategy(
            strategy_name=f"stress_test_{i}",
            strategy_version="1.0",
            approach="value",
            config={"test": True},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_strategy, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 10  # All creates succeeded
    # If connection pool leak → this fails with pool exhausted error

# Layer 4: Property tests (mathematical invariants)
from hypothesis import given
from hypothesis import strategies as st

@given(
    true_prob=st.decimals(min_value="0.01", max_value="0.99", places=4),
    market_price=st.decimals(min_value="0.01", max_value="0.99", places=4),
)
def test_edge_always_decimal(true_prob, market_price):
    """Edge calculation NEVER produces float (test with 100+ cases)."""
    edge = calculate_edge(true_prob, market_price)

    assert isinstance(edge, Decimal)  # NEVER float
    # Hypothesis generates 100+ test cases automatically
```

### Common Mistakes to Avoid

**Mistake 1: Mocking internal infrastructure**
```python
# ❌ WRONG
@patch("precog.database.connection.get_connection")
def test_create_strategy(mock_get_connection):
    # Don't mock internal infrastructure!

# ✅ CORRECT
def test_create_strategy(clean_test_data, manager, strategy_factory):
    # Use real database with fixtures
```

**Mistake 2: Not using conftest.py fixtures**
```python
# ❌ WRONG
def test_create_strategy():
    conn = psycopg2.connect(...)  # Manual connection
    cursor = conn.cursor()
    # Manual cleanup required

# ✅ CORRECT
def test_create_strategy(clean_test_data, db_cursor):
    # Fixtures handle connection + cleanup
```

**Mistake 3: Aggregate coverage hiding gaps**
```python
# ❌ WRONG
# "Overall coverage: 86% ✅ - ship it!"

# ✅ CORRECT
# "Model Manager: 25% ❌ - below 85% target, not ready"
```

**Mistake 4: Only unit tests, no integration/stress tests**
```python
# ❌ WRONG
# 30 unit tests, 0 integration tests, 0 stress tests

# ✅ CORRECT
# 30 unit tests + 15 integration tests + 5 stress tests
```

### Cross-References
- **TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md:** Post-mortem documenting Strategy Manager test failure
- **TEST_REQUIREMENTS_COMPREHENSIVE_V2.1.md:** REQ-TEST-012 through REQ-TEST-019 (8 test types, coverage standards, mock restrictions)
- **TESTING_GAPS_ANALYSIS.md:** Current coverage gaps and remediation plan
- **DEVELOPMENT_PHILOSOPHY_V1.3.md:** Section 1 - Test Quality: When Tests Pass But Aren't Sufficient
- **Pattern 11:** Test Mocking Patterns (HOW to mock public APIs vs implementation)
- **Pattern 12:** Test Fixture Security Compliance (project-relative test fixtures)
- **tests/conftest.py:** Test fixture infrastructure (`clean_test_data`, `db_pool`, `db_cursor`)

---

## Pattern 14: Schema Migration → CRUD Operations Update Workflow (CRITICAL)

**WHY:** When database schema changes (especially for SCD Type 2 tables with dual-key pattern), CRUD operations MUST be updated to match. Forgetting to update CRUD operations causes:
- Insert failures (missing required columns)
- Query failures (column doesn't exist)
- Business logic bugs (expecting field that doesn't exist)
- SCD Type 2 violations (forgetting row_current_ind filter)

**The Problem:** Database schema and CRUD operations can drift out of sync across multiple locations.

**Phase 1.5 Example:**
- Migration 011 added dual-key schema to positions table (surrogate `id` + business `position_id`)
- Required updates to 4 CRUD functions: `open_position()`, `update_position()`, `close_position()`, `get_current_positions()`
- Missed update in `close_position()` → missing `current_price` column → test assertion failure

### When This Pattern Applies

**✅ ALWAYS use this workflow when:**
- Adding new columns to SCD Type 2 tables (positions, markets, edges, balances)
- Changing column types (VARCHAR → DECIMAL, INTEGER → BIGINT)
- Adding/changing constraints (UNIQUE, FOREIGN KEY, CHECK)
- Implementing dual-key schema pattern (surrogate + business key)
- Changing SCD Type 2 metadata columns (row_current_ind, row_effective_date)

**Tables Using SCD Type 2 + Dual-Key Pattern:**
- ✅ `positions` (Migration 011 - IMPLEMENTED)
- ✅ `markets` (Migration 004 - IMPLEMENTED)
- 📋 `trades` (Planned - Phase 2)
- 📋 `account_balance` (Planned - Phase 2)
- 📋 `edges` (Planned - Phase 4)

### 5-Step Mandatory Workflow

#### Step 1: Create Database Migration (10-30 min)

```sql
-- Migration 011: Add dual-key schema to positions table
-- File: src/precog/database/migrations/011_add_positions_dual_key.sql

-- 1. Add position_id business key column (nullable initially)
ALTER TABLE positions ADD COLUMN position_id VARCHAR(50);

-- 2. Populate position_id from id (surrogate key)
UPDATE positions SET position_id = 'POS-' || id::TEXT WHERE position_id IS NULL;

-- 3. Make position_id NOT NULL
ALTER TABLE positions ALTER COLUMN position_id SET NOT NULL;

-- 4. Create partial UNIQUE index (one current version per position_id)
CREATE UNIQUE INDEX positions_position_id_current_unique
ON positions (position_id)
WHERE row_current_ind = TRUE;

-- 5. Add comment documenting dual-key pattern
COMMENT ON COLUMN positions.position_id IS 'Business key (repeats across versions), format: POS-{id}';
COMMENT ON COLUMN positions.id IS 'Surrogate PRIMARY KEY (unique across all versions, used for FK references)';
```

**Migration Checklist:**
- [ ] Added new column with correct type
- [ ] Populated existing rows if NOT NULL
- [ ] Created indexes if needed (partial unique for SCD Type 2)
- [ ] Added comments documenting pattern
- [ ] Tested migration on local database
- [ ] Verified rollback script (if applicable)

#### Step 2: Update CRUD Operations (30-60 min)

**CRITICAL: Update ALL functions that touch the modified table.**

**Example: positions table has 4 CRUD functions to update:**

**2a. open_position() - Set business_id from surrogate_id**

```python
# src/precog/database/crud_operations.py

def open_position(
    market_id: str,
    strategy_id: int,
    model_id: int,
    side: str,
    quantity: int,
    entry_price: Decimal,
    target_price: Decimal | None = None,
    stop_loss_price: Decimal | None = None,
    trailing_stop_config: dict[str, Any] | None = None,
    position_metadata: dict[str, Any] | None = None,
) -> str:
    """Open new position with dual-key pattern.

    Returns:
        position_id (business key, format: 'POS-{id}')

    Educational Note:
        Dual-key pattern: surrogate PRIMARY KEY (id) + business key (position_id).
        Business key is set from surrogate key after INSERT to guarantee uniqueness.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Step 1: INSERT without business_id (generates surrogate id)
            cur.execute("""
                INSERT INTO positions (
                    market_id, strategy_id, model_id, side,
                    quantity, entry_price, current_price,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', TRUE)
                RETURNING id
            """, (
                market_id, strategy_id, model_id, side,
                quantity, entry_price, entry_price,
                target_price, stop_loss_price,
                Json(trailing_stop_config) if trailing_stop_config else None,
                Json(position_metadata) if position_metadata else None,
            ))

            surrogate_id = cur.fetchone()['id']

            # Step 2: UPDATE to set business_id from surrogate_id
            cur.execute("""
                UPDATE positions
                SET position_id = %s
                WHERE id = %s
                RETURNING position_id
            """, (f'POS-{surrogate_id}', surrogate_id))

            position_id = cur.fetchone()['position_id']
            conn.commit()
            return position_id
    finally:
        release_connection(conn)
```

**2b. update_position() - SCD Type 2 versioning**

```python
def update_position(
    position_id: int,  # Surrogate key (NOT business key!)
    current_price: Decimal,
) -> int:
    """Update position - creates new SCD Type 2 version.

    Args:
        position_id: Surrogate key (id column, unique across all versions)
        current_price: New market price

    Returns:
        New surrogate id for updated version

    Educational Note:
        SCD Type 2 pattern: UPDATE old row (set row_current_ind=FALSE),
        then INSERT new row (same position_id, new surrogate id).
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Step 1: Get current version (must filter by row_current_ind!)
            cur.execute("""
                SELECT * FROM positions
                WHERE id = %s AND row_current_ind = TRUE
            """, (position_id,))

            current = cur.fetchone()
            if not current:
                raise ValueError(f"Position {position_id} not found or not current")

            # Step 2: Expire current version
            cur.execute("""
                UPDATE positions
                SET row_current_ind = FALSE, row_expiration_date = NOW()
                WHERE id = %s
            """, (position_id,))

            # Step 3: Insert new version (REUSE same position_id business key)
            cur.execute("""
                INSERT INTO positions (
                    position_id, market_id, strategy_id, model_id, side,
                    quantity, entry_price, current_price,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id
            """, (
                current['position_id'],  # Reuse business key!
                current['market_id'], current['strategy_id'], current['model_id'],
                current['side'], current['quantity'], current['entry_price'],
                current_price,  # Updated field
                current['target_price'], current['stop_loss_price'],
                current['trailing_stop_state'], current['position_metadata'],
                current['status'], current['entry_time'],
            ))

            new_id = cur.fetchone()['id']
            conn.commit()
            return new_id
    finally:
        release_connection(conn)
```

**2c. close_position() - Final SCD Type 2 version**

```python
def close_position(
    position_id: int,
    exit_price: Decimal,
    exit_reason: str,
    realized_pnl: Decimal,
) -> int:
    """Close position - creates final SCD Type 2 version with status='closed'.

    CRITICAL: Must set current_price to exit_price for closed positions.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current version
            cur.execute("""
                SELECT * FROM positions
                WHERE id = %s AND row_current_ind = TRUE
            """, (position_id,))

            current = cur.fetchone()
            if not current:
                raise ValueError(f"Position {position_id} not found")

            # Expire current version
            cur.execute("""
                UPDATE positions
                SET row_current_ind = FALSE, row_expiration_date = NOW()
                WHERE id = %s
            """, (position_id,))

            # Insert closed version (MUST include ALL columns!)
            cur.execute("""
                INSERT INTO positions (
                    position_id, market_id, strategy_id, model_id, side,
                    quantity, entry_price, exit_price, current_price,
                    realized_pnl,
                    target_price, stop_loss_price,
                    trailing_stop_state, position_metadata,
                    status, entry_time, exit_time, row_current_ind
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'closed', %s, NOW(), TRUE)
                RETURNING id
            """, (
                current['position_id'], current['market_id'], current['strategy_id'],
                current['model_id'], current['side'], current['quantity'],
                current['entry_price'], exit_price,
                exit_price,  # ⚠️ CRITICAL: Set current_price to exit_price!
                realized_pnl,
                current['target_price'], current['stop_loss_price'],
                current['trailing_stop_state'], current['position_metadata'],
                current['entry_time'],
            ))

            final_id = cur.fetchone()['id']
            conn.commit()
            return final_id
    finally:
        release_connection(conn)
```

**2d. get_current_positions() - ALWAYS filter by row_current_ind**

```python
def get_current_positions(status: str | None = None, market_id: str | None = None) -> list[dict]:
    """Get current positions (filters by row_current_ind = TRUE).

    Educational Note:
        CRITICAL: ALWAYS filter SCD Type 2 tables by row_current_ind = TRUE
        to get only current versions, not historical versions.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    p.*,
                    m.ticker, m.yes_price, m.no_price, m.market_type
                FROM positions p
                JOIN markets m ON p.market_id = m.market_id AND m.row_current_ind = TRUE
                WHERE p.row_current_ind = TRUE  -- ⚠️ CRITICAL: Filter current versions
            """
            params = []

            if status:
                query += " AND p.status = %s"
                params.append(status)

            if market_id:
                query += " AND p.market_id = %s"
                params.append(market_id)

            query += " ORDER BY p.entry_time DESC"

            cur.execute(query, params)
            return cur.fetchall()
    finally:
        release_connection(conn)
```

**CRUD Update Checklist:**
- [ ] Updated ALL INSERT statements to include new columns
- [ ] Updated ALL UPDATE statements to handle new columns
- [ ] Updated ALL SELECT statements to include new columns (if needed)
- [ ] Set business_id from surrogate_id on initial INSERT (dual-key pattern)
- [ ] ALWAYS filter by `row_current_ind = TRUE` in queries (SCD Type 2)
- [ ] Reuse business key when creating new SCD Type 2 versions
- [ ] Include ALL columns when inserting new versions (don't forget new columns!)

#### Step 3: Update Tests (30-60 min)

**CRITICAL: Tests must use REAL database, not mocks (Pattern 13).**

```python
# tests/unit/trading/test_position_manager.py

def test_open_position_sets_business_id(clean_test_data, manager, position_params):
    """Verify open_position sets position_id from surrogate id."""
    result = manager.open_position(**position_params)

    # Verify business_id format
    assert result['position_id'].startswith('POS-')
    assert result['id'] is not None  # Surrogate key

    # Verify business_id matches surrogate_id
    expected_position_id = f"POS-{result['id']}"
    assert result['position_id'] == expected_position_id


def test_update_position_creates_new_version_with_same_business_id(
    clean_test_data, manager, position_params
):
    """Verify SCD Type 2: new version reuses same position_id."""
    # Open position
    position = manager.open_position(**position_params)
    original_id = position['id']
    original_position_id = position['position_id']

    # Update position (creates new SCD Type 2 version)
    updated = manager.update_position(
        position_id=original_id,
        current_price=Decimal("0.6000"),
    )

    # Verify new version has DIFFERENT surrogate id
    assert updated['id'] != original_id

    # Verify new version has SAME business key
    assert updated['position_id'] == original_position_id

    # Verify old version is expired
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT row_current_ind FROM positions WHERE id = %s
            """, (original_id,))
            old_version = cur.fetchone()
            assert old_version['row_current_ind'] is False  # Expired
    finally:
        release_connection(conn)


def test_close_position_sets_current_price(clean_test_data, manager, position_params):
    """Verify close_position sets current_price to exit_price."""
    # Open position
    position = manager.open_position(**position_params)

    # Close position
    closed = manager.close_position(
        position_id=position['id'],
        exit_price=Decimal("0.7500"),
        exit_reason="profit_target",
    )

    # Verify current_price equals exit_price
    assert closed['current_price'] == Decimal("0.7500")
    assert closed['exit_price'] == Decimal("0.7500")
    assert closed['status'] == 'closed'


def test_get_current_positions_filters_by_row_current_ind(
    clean_test_data, manager, position_params
):
    """Verify get_current_positions only returns row_current_ind=TRUE."""
    # Open position
    position = manager.open_position(**position_params)
    original_id = position['id']

    # Update twice (creates 2 new versions, expires 2 old versions)
    manager.update_position(original_id, Decimal("0.5500"))
    manager.update_position(original_id, Decimal("0.6000"))

    # Should return 1 position (only current version)
    current_positions = manager.get_open_positions()
    assert len(current_positions) == 1

    # Verify returned position is the latest version
    assert current_positions[0]['current_price'] == Decimal("0.6000")

    # Verify database has 3 versions total (1 current + 2 expired)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM positions WHERE position_id = %s
            """, (position['position_id'],))
            total_versions = cur.fetchone()[0]
            assert total_versions == 3
    finally:
        release_connection(conn)
```

**Test Update Checklist:**
- [ ] Tests use `clean_test_data` fixture (real database)
- [ ] Tests verify business_id set correctly on INSERT
- [ ] Tests verify SCD Type 2 versioning (UPDATE + INSERT pattern)
- [ ] Tests verify row_current_ind filtering works
- [ ] Tests verify ALL new columns populated correctly
- [ ] Tests verify old versions expired (row_current_ind=FALSE)
- [ ] NO mocks for `get_connection()`, `ConfigLoader`, or internal CRUD

#### Step 4: Run Integration Tests (5-10 min)

```bash
# Run position manager tests
python -m pytest tests/unit/trading/test_position_manager.py -v

# Expected: All tests passing
# 23/23 tests passing (from Phase 1.5 example)

# Run full test suite
python -m pytest tests/ -v

# Check coverage
python -m pytest tests/ --cov=precog.database.crud_operations --cov-report=term-missing
```

**Integration Test Checklist:**
- [ ] All position manager tests passing
- [ ] All CRUD operation tests passing
- [ ] No SQL syntax errors
- [ ] No missing column errors
- [ ] Coverage ≥85% for CRUD operations
- [ ] Coverage ≥87% for position manager

#### Step 5: Update Documentation (10-20 min)

**Update 3 locations:**

**5a. DATABASE_SCHEMA_SUMMARY_V*.md**
```markdown
### positions Table (Dual-Key SCD Type 2)

**Purpose:** Track position lifecycle with historical versioning

**Dual-Key Pattern:**
- `id SERIAL PRIMARY KEY` - Surrogate key (unique across all versions, used for FK references)
- `position_id VARCHAR(50) NOT NULL` - Business key (repeats across versions, format: 'POS-{id}')
- Partial UNIQUE index: `CREATE UNIQUE INDEX ... ON positions (position_id) WHERE row_current_ind = TRUE`

**Key Columns:**
- `id` - Surrogate PRIMARY KEY
- `position_id` - Business key (user-facing, stable across versions)
- `market_id` - FK to markets (business key)
- `strategy_id` - FK to strategies
- `model_id` - FK to probability_models
- `entry_price DECIMAL(10,4)` - Original entry price
- `current_price DECIMAL(10,4)` - Latest market price
- `exit_price DECIMAL(10,4)` - Exit price (NULL until closed)
- `row_current_ind BOOLEAN` - TRUE = current version, FALSE = historical
- `row_effective_date TIMESTAMP` - Version start time
- `row_expiration_date TIMESTAMP` - Version end time (NULL for current)

**SCD Type 2 Behavior:**
- Updates create new row with same position_id, new surrogate id
- Old row: row_current_ind → FALSE, row_expiration_date → NOW()
- New row: row_current_ind → TRUE, row_effective_date → NOW()

**Migration:** Migration 011 (2025-11-19) - Added dual-key pattern
```

**5b. ADR-089 Cross-Reference**

Add positions table to "Tables Using This Pattern" section in ADR-089.

**5c. Pattern 14 (this document)**

You're reading it! 😊

**Documentation Update Checklist:**
- [ ] Updated DATABASE_SCHEMA_SUMMARY with dual-key columns
- [ ] Updated ADR-089 table list
- [ ] Updated MASTER_INDEX if new docs created
- [ ] Added migration number to documentation

### Common Mistakes to Avoid

**Mistake 1: Forgetting to set business_id from surrogate_id**

```python
# ❌ WRONG - business_id remains NULL
cur.execute("""
    INSERT INTO positions (market_id, strategy_id, ..., row_current_ind)
    VALUES (%s, %s, ..., TRUE)
    RETURNING id
""", (...))
# Missing UPDATE to set position_id!

# ✅ CORRECT - Set business_id after INSERT
surrogate_id = cur.fetchone()['id']
cur.execute("""
    UPDATE positions SET position_id = %s WHERE id = %s
""", (f'POS-{surrogate_id}', surrogate_id))
```

**Mistake 2: Forgetting row_current_ind filter in queries**

```python
# ❌ WRONG - Returns ALL versions (current + historical)
cur.execute("SELECT * FROM positions WHERE market_id = %s", (market_id,))

# ✅ CORRECT - Returns only current versions
cur.execute("""
    SELECT * FROM positions
    WHERE market_id = %s AND row_current_ind = TRUE
""", (market_id,))
```

**Mistake 3: Not reusing business key when creating new version**

```python
# ❌ WRONG - Generates NEW position_id (violates SCD Type 2)
cur.execute("""
    INSERT INTO positions (position_id, market_id, ...)
    VALUES ('POS-NEW-ID', %s, ...)  -- Wrong!
""", (...))

# ✅ CORRECT - Reuse same position_id from old version
cur.execute("""
    INSERT INTO positions (position_id, market_id, ...)
    VALUES (%s, %s, ...)  -- Reuse current['position_id']
""", (current['position_id'], ...))
```

**Mistake 4: Forgetting new columns in INSERT**

```python
# ❌ WRONG - Missing current_price in close_position INSERT
cur.execute("""
    INSERT INTO positions (
        position_id, market_id, ..., exit_price, status
    )
    VALUES (%s, %s, ..., %s, 'closed')
""", (position_id, market_id, ..., exit_price))
# Missing current_price! Causes assertion failure in tests.

# ✅ CORRECT - Include ALL columns
cur.execute("""
    INSERT INTO positions (
        position_id, market_id, ..., exit_price, current_price, status
    )
    VALUES (%s, %s, ..., %s, %s, 'closed')
""", (position_id, market_id, ..., exit_price, exit_price))
```

**Mistake 5: Using mocks instead of real database**

```python
# ❌ WRONG - Mock hides real database issues
@patch("precog.database.connection.get_connection")
def test_open_position(mock_get_connection):
    mock_get_connection.return_value.cursor.return_value.fetchone.return_value = {...}
    # Test passes but doesn't validate SQL syntax, constraints, or business_id logic!

# ✅ CORRECT - Use real database with fixtures
def test_open_position(clean_test_data, manager, position_params):
    result = manager.open_position(**position_params)
    # Validates SQL syntax, constraints, business_id generation, everything!
```

### Decision Tree: When to Update CRUD

```
Q: Did database schema change?
├─ NO → No CRUD updates needed
└─ YES → Continue

Q: Does change affect SCD Type 2 table?
├─ NO → Update CRUD for new columns (simpler workflow)
└─ YES → Continue (use full 5-step workflow)

Q: Which operations are affected?
├─ INSERT → Update to include new columns
├─ UPDATE → Update to include new columns
├─ SELECT → Update to return new columns
└─ SCD Type 2 versioning → Update UPDATE + INSERT pattern

Q: Did you update tests to verify changes?
├─ NO → STOP! Write integration tests first (Pattern 13)
└─ YES → Continue

Q: Did tests pass on first try?
├─ YES → Excellent! Proceed to documentation
└─ NO → Debug integration tests, fix CRUD, repeat

Q: Did you update documentation?
├─ NO → STOP! Update DATABASE_SCHEMA_SUMMARY, ADR-089
└─ YES → ✅ COMPLETE - Schema and CRUD synchronized
```

### Quick Reference: SCD Type 2 CRUD Patterns

| Operation | Pattern | row_current_ind | Business Key |
|-----------|---------|-----------------|--------------|
| **INSERT (new record)** | Single INSERT | Set to TRUE | Set from surrogate id |
| **UPDATE (new version)** | UPDATE old + INSERT new | Old→FALSE, New→TRUE | Reuse from old version |
| **DELETE (soft delete)** | UPDATE + INSERT | Old→FALSE, New→TRUE | Reuse from old version |
| **SELECT (current only)** | WHERE filter | Filter `= TRUE` | Any value |
| **SELECT (all versions)** | No filter | Any value | Group by business key |

### Real-World Impact: Position Manager Example

**Phase 1.5 Schema Migration (Migration 011):**
- Added `position_id` business key to positions table
- Required updates to 4 CRUD functions
- Caught 1 critical bug (missing current_price in close_position)
- 23 integration tests created, all passing
- Coverage: Position Manager 87.50%, CRUD operations 91.26%

**Without this workflow:**
- Bug would have gone undetected until production
- Tests would pass (mocks don't validate SQL)
- Runtime error: "column current_price does not exist"
- Emergency hotfix required

**With this workflow:**
- Bug caught during Step 4 (integration tests)
- Fixed in 5 minutes (added current_price to INSERT)
- High confidence in deployment

### Performance Considerations

**SCD Type 2 + Dual-Key Impact:**
- Storage: ~2-3x data size (multiple versions per record)
- Query speed: Fast with partial unique index (row_current_ind = TRUE)
- Write speed: 2x slower (UPDATE + INSERT instead of single UPDATE)

**Mitigation:**
- Archive old versions (row_current_ind = FALSE) after 90 days
- Separate "hot" (current) and "cold" (historical) partitions
- Index on (position_id, row_current_ind) for fast current version lookup

**When to Archive:**
- Phase 5+ (not Phase 1-2) - Premature optimization
- Only when query performance degrades (>100ms for current positions)
- Keep at least 30 days of history for debugging

### SCD Type 2 Column Preservation Failure (CRITICAL BUG PATTERN)

**The Problem:** When adding new columns to SCD Type 2 tables, developers update the CREATE (initial INSERT) but forget to update the VERSION (UPDATE→INSERT for SCD Type 2) operations.

**Real-World Example (December 2025):**
- Added `execution_environment` column to `positions` table via migration
- Updated `create_position()` to include new column ✅
- **FORGOT** to update `close_position()` to preserve column in closed version ❌

**Bug Behavior:**
```python
# Position created with execution_environment="paper"
pos_id = create_position(market_id=1, execution_environment="paper", ...)

# Position closed - BUT execution_environment was NULL in closed version!
closed_id = close_position(position_id=pos_id, exit_price=Decimal("0.60"), ...)

# Query for closed paper positions returns NOTHING (because env is NULL)
closed = get_current_positions(status="closed", execution_environment="paper")
# closed == []  # Bug! Should have found the closed position
```

**Root Cause in close_position():**
```python
# WRONG - Missing execution_environment column
cur.execute("""
    INSERT INTO positions (
        position_id, market_id, strategy_id, model_id, side,
        quantity, entry_price, exit_price, current_price,
        realized_pnl,
        target_price, stop_loss_price,
        trailing_stop_state, position_metadata,
        status, entry_time, exit_time
        -- ❌ MISSING: execution_environment
    )
    VALUES (...)
""", (...))  # execution_environment gets default NULL

# CORRECT - Preserve ALL columns from original position
cur.execute("""
    INSERT INTO positions (
        position_id, market_id, strategy_id, model_id, side,
        quantity, entry_price, exit_price, current_price,
        realized_pnl,
        target_price, stop_loss_price,
        trailing_stop_state, position_metadata,
        status, entry_time, exit_time, execution_environment  -- ✅ Added
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'closed', %s, NOW(), %s)
""", (
    current["position_id"],
    # ... other columns ...
    current["execution_environment"],  # ✅ Preserve from original
))
```

**Column Preservation Checklist for SCD Type 2 Migrations:**

When adding a new column to an SCD Type 2 table:

1. **Migration:** Add column with appropriate default
2. **create_*() function:** Include new column in initial INSERT ✅
3. **update_*() function:** Preserve column in new SCD version ⚠️ EASILY FORGOTTEN
4. **close_*() function:** Preserve column in final SCD version ⚠️ EASILY FORGOTTEN
5. **get_*() function:** Include column in SELECT if needed for queries
6. **Tests:** Add test that verifies column survives SCD versioning

**Prevention Strategies:**

| Strategy | Implementation |
|----------|----------------|
| **Code review checklist** | "Does close_*() preserve all columns from current?" |
| **SELECT * in versioning** | Fetch all columns, pass all to INSERT (but verify explicitly) |
| **Integration test** | Create→Update→Close→Verify all columns preserved |
| **Pre-push hook** | Validate INSERT column count matches table schema |

**Test Pattern to Catch This Bug:**
```python
def test_close_position_preserves_execution_environment(db_pool, clean_test_data):
    """Verify execution_environment survives close_position() SCD versioning."""
    # Create position with paper environment
    pos_id = create_position(
        market_id=market_id,
        execution_environment="paper",  # Explicitly set
        ...
    )

    # Close position (creates new SCD Type 2 row)
    closed_id = close_position(
        position_id=pos_id,
        exit_price=Decimal("0.60"),
        ...
    )

    # ✅ CRITICAL: Verify execution_environment preserved in closed version
    closed_positions = get_current_positions(
        status="closed",
        execution_environment="paper"  # Filter by original value
    )
    assert any(p["id"] == closed_id for p in closed_positions), \
        "execution_environment lost during close_position() SCD versioning!"
```

**Why This Bug Is Insidious:**
1. **Tests pass with simple assertions** - checking exit_price, status works fine
2. **Column gets NULL** - no error thrown, just silent data loss
3. **Queries fail silently** - filter by column returns no results
4. **Found only by specific tests** - must explicitly test column preservation

**Related Files:**
- `src/precog/database/crud_operations.py:close_position()` - Fixed in Issue #273
- `tests/test_crud_operations.py` - 4 tests added for execution_environment

### Cross-References

**Architecture Decisions:**
- **ADR-089:** Dual-Key Schema Pattern for SCD Type 2 Tables (comprehensive pattern documentation)
- **ADR-034:** SCD Type 2 for Slowly Changing Dimensions (original SCD Type 2 decision)
- **ADR-003:** Database Schema Versioning Strategy (migration workflow)
- **ADR-088:** Test Type Categories and Coverage Standards (test requirements)

**Development Patterns:**
- **Pattern 1:** Decimal Precision (use Decimal for all price columns)
- **Pattern 2:** Dual Versioning System (SCD Type 2 vs immutable versions)
- **Pattern 13:** Test Coverage Quality (NO mocks for database/CRUD, use real fixtures)

**Implementation Examples:**
- **Migration 011:** `src/precog/database/migrations/011_add_positions_dual_key.sql`
- **CRUD Operations:** `src/precog/database/crud_operations.py` (lines 800-1000: position CRUD functions)
- **Position Manager:** `src/precog/trading/position_manager.py` (business layer using CRUD)
- **Integration Tests:** `tests/unit/trading/test_position_manager.py` (23 tests)

**Testing Infrastructure:**
- **tests/conftest.py:** Fixture infrastructure (clean_test_data, db_pool, db_cursor)
- **TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md:** Why mocks hide bugs (Strategy Manager lesson)
- **TEST_REQUIREMENTS_COMPREHENSIVE_V2.1.md:** REQ-TEST-012 through REQ-TEST-019

**Documentation:**
- **DATABASE_SCHEMA_SUMMARY_V1.7.md:** Complete schema reference
- **SCHEMA_MIGRATION_WORKFLOW_V2.1.md:** Comprehensive Alembic-based migration workflow guide

---

## Pattern 15: Trade/Position Attribution Architecture (ALWAYS - Migrations 018-020)

**ALWAYS capture execution-time attribution for trades and positions (Migrations 018-020).**

### Core Principle

Every trade and position must record:
1. **Trade Source**: Automated (app-executed) vs Manual (Kalshi UI)
2. **Attribution Snapshots**: Model prediction, market price, calculated edge at execution
3. **Immutability**: Position attribution locked at entry (ADR-018)

This enables performance analytics: "Which models generate profits?" and "Do high-edge trades win more?"

---

### ✅ CORRECT: Trade with Full Attribution

```python
from decimal import Decimal
from precog.database.crud_operations import create_trade

trade_id = create_trade(
    market_id="HIGHTEST-25FEB05",
    strategy_id=1,  # Which strategy triggered trade
    model_id=2,     # Which model provided prediction
    side="YES",
    quantity=50,
    price=Decimal("0.5200"),
    # ⭐ ATTRIBUTION FIELDS (Migration 019)
    trade_source="automated",                      # App-executed trade
    calculated_probability=Decimal("0.6250"),      # Model predicted 62.50% win probability
    market_price=Decimal("0.5200"),                # Kalshi price was 52.00%
    # edge_value automatically calculated: 0.6250 - 0.5200 = 0.1050
)
```

**What happens:**
- ✅ `edge_value` automatically calculated as `0.1050` (10.5% edge)
- ✅ Attribution stored as immutable snapshots (won't change if market price moves)
- ✅ Enables analytics: "Average ROI for trades with edge ≥ 10%?"

---

### ❌ WRONG: Trade Without Attribution

```python
# ❌ Missing attribution fields
trade_id = create_trade(
    market_id="HIGHTEST-25FEB05",
    strategy_id=1,
    model_id=2,
    side="YES",
    quantity=50,
    price=Decimal("0.5200"),
    # Missing: trade_source, calculated_probability, market_price
)
```

**Problems:**
- ❌ Can't determine if trade was automated or manual
- ❌ Can't answer "What did model predict at execution?"
- ❌ Can't calculate ROI by model or edge value
- ❌ Lost opportunity for performance attribution

---

### ✅ CORRECT: Position with Full Attribution

```python
from decimal import Decimal
from precog.database.crud_operations import create_position

position_id = create_position(
    market_id="HIGHTEST-25FEB05",
    strategy_id=1,
    model_id=2,
    side="YES",
    quantity=100,
    entry_price=Decimal("0.5200"),
    target_price=Decimal("0.7500"),
    stop_loss_price=Decimal("0.4500"),
    # ⭐ ATTRIBUTION FIELDS (Migration 020) - IMMUTABLE entry snapshots
    calculated_probability=Decimal("0.6800"),      # Model predicted 68.00% at entry
    market_price_at_entry=Decimal("0.5200"),       # Market priced at 52.00% at entry
    # edge_at_entry automatically calculated: 0.6800 - 0.5200 = 0.1600
)
```

**What happens:**
- ✅ `edge_at_entry` automatically calculated as `0.1600` (16% edge)
- ✅ Attribution fields are **IMMUTABLE** (ADR-018) - never updated
- ✅ Enables strategy A/B testing: "Did entry v1.5 outperform entry v1.6?"
- ✅ Enables edge analysis: "What was the edge at entry for winning positions?"

**Immutability Example:**
```python
# Position opened at entry_price=0.5200, calculated_probability=0.6800, edge_at_entry=0.1600

# ... market moves to 0.6500 ...

# Position attribution UNCHANGED (immutable entry snapshot):
position = get_position_by_id(position_id)
assert position["calculated_probability"] == Decimal("0.6800")  # Still 0.6800 (not updated)
assert position["market_price_at_entry"] == Decimal("0.5200")   # Still 0.5200 (not updated)
assert position["edge_at_entry"] == Decimal("0.1600")           # Still 0.1600 (not updated)

# This enables comparing entry prediction vs actual outcome:
# "What was the edge when we entered?" vs "What happened after?"
```

---

### ❌ WRONG: Manual Edge Calculation

```python
# ❌ Don't manually calculate edge_value or edge_at_entry
edge_value = calculated_probability - market_price
trade_id = create_trade(
    ...,
    calculated_probability=Decimal("0.6250"),
    market_price=Decimal("0.5200"),
    edge_value=edge_value,  # ❌ WRONG - let CRUD calculate automatically
)
```

**Why wrong:**
- ❌ Violates DRY principle (calculation duplicated across codebase)
- ❌ Risk of inconsistency (what if someone forgets to calculate?)
- ❌ CRUD layer already calculates automatically

**✅ CORRECT:**
```python
# Let create_trade() calculate edge_value automatically
trade_id = create_trade(
    ...,
    calculated_probability=Decimal("0.6250"),
    market_price=Decimal("0.5200"),
    # edge_value calculated automatically
)
```

---

### Trade Source Tracking (Migration 018)

**Use Case: Separate automated vs manual trades**

```python
# ✅ Automated trade (app-executed)
automated_trade_id = create_trade(
    ...,
    trade_source="automated",  # Default value
)

# ✅ Manual trade (Kalshi UI) - for reconciliation
manual_trade_id = create_trade(
    ...,
    trade_source="manual",  # Mark as manually executed
)
```

**Analytics Query: Automated-only performance**
```sql
-- ROI for automated trades only (exclude manual interventions)
SELECT
    model_id,
    COUNT(*) AS num_trades,
    AVG(edge_value) AS avg_edge,
    AVG(realized_pnl) AS avg_pnl
FROM trades
WHERE trade_source = 'automated'  -- Filter out manual trades
GROUP BY model_id
ORDER BY AVG(realized_pnl) DESC;
```

---

### Handling Negative Edges

**Edge can be negative** (market overpriced relative to model):

```python
# Market overpriced scenario
trade_id = create_trade(
    ...,
    calculated_probability=Decimal("0.6000"),  # Model: 60% win probability
    market_price=Decimal("0.7500"),            # Market: 75% (overpriced!)
    # edge_value calculated automatically: 0.6000 - 0.7500 = -0.1500 (NEGATIVE)
)

trade = get_trade_by_id(trade_id)
assert trade["edge_value"] == Decimal("-0.1500")  # Negative edge
```

**When you might have negative edge:**
- ✅ **Manual trades**: User manually took position despite negative edge
- ✅ **Market moved**: Placed order at +edge, filled at -edge (slippage)
- ✅ **Model wrong**: Model miscalibrated (overestimated probability)

**Analytics Query: How often did we trade negative edges?**
```sql
SELECT
    COUNT(*) AS negative_edge_trades,
    AVG(realized_pnl) AS avg_pnl_negative_edge
FROM trades
WHERE edge_value < 0;
```

---

### Backward Compatibility

**Attribution fields are optional** (NULL allowed for legacy data):

```python
# ✅ Legacy trade without attribution (backward compatible)
legacy_trade_id = create_trade(
    market_id="OLD-MARKET",
    strategy_id=1,
    model_id=1,
    side="YES",
    quantity=50,
    price=Decimal("0.5000"),
    # No attribution fields provided - that's OK!
)

trade = get_trade_by_id(legacy_trade_id)
assert trade["calculated_probability"] is None
assert trade["market_price"] is None
assert trade["edge_value"] is None
assert trade["trade_source"] == "automated"  # Still has default
```

---

### Database Validation (CHECK Constraints)

**PostgreSQL enforces probability ranges [0.0, 1.0]:**

```python
# ❌ This will FAIL (probability > 1.0)
create_trade(
    ...,
    calculated_probability=Decimal("1.5000"),  # Invalid: > 1.0
    market_price=Decimal("0.5000"),
)
# psycopg2.errors.CheckViolation: new row violates check constraint

# ❌ This will FAIL (probability < 0.0)
create_position(
    ...,
    calculated_probability=Decimal("-0.2000"),  # Invalid: < 0.0
    market_price_at_entry=Decimal("0.5000"),
)
# psycopg2.errors.CheckViolation: new row violates check constraint

# ✅ Valid probability range
create_trade(
    ...,
    calculated_probability=Decimal("0.6250"),  # Valid: [0.0, 1.0]
    market_price=Decimal("0.5200"),            # Valid: [0.0, 1.0]
)
```

---

### Performance Analytics Queries

**1. ROI by Model**
```sql
SELECT
    m.model_name,
    m.version,
    COUNT(*) AS num_trades,
    AVG(t.edge_value) AS avg_edge,
    AVG(t.realized_pnl) AS avg_roi
FROM trades t
JOIN probability_models m ON t.model_id = m.model_id
WHERE t.trade_source = 'automated'
GROUP BY m.model_name, m.version
ORDER BY AVG(t.realized_pnl) DESC;
```

**2. Edge vs Outcome Analysis**
```sql
SELECT
    CASE
        WHEN edge_value >= 0.15 THEN 'High Edge (≥15%)'
        WHEN edge_value >= 0.05 THEN 'Medium Edge (5-15%)'
        WHEN edge_value >= 0 THEN 'Low Edge (0-5%)'
        ELSE 'Negative Edge'
    END AS edge_bucket,
    COUNT(*) AS trade_count,
    AVG(realized_pnl) AS avg_pnl,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS win_rate
FROM trades
WHERE edge_value IS NOT NULL
GROUP BY edge_bucket
ORDER BY AVG(realized_pnl) DESC;
```

**3. Strategy A/B Testing (Position Attribution)**
```sql
-- Compare ROI of Entry v1.5 vs Entry v1.6
SELECT
    s.version,
    s.config->>'entry'->>'version' AS entry_version,
    COUNT(*) AS num_positions,
    AVG(p.edge_at_entry) AS avg_entry_edge,
    AVG(p.realized_pnl) AS avg_roi
FROM positions p
JOIN strategies s ON p.strategy_id = s.strategy_id
WHERE s.strategy_name = 'NFL Ensemble'
GROUP BY s.version, entry_version
ORDER BY AVG(p.realized_pnl) DESC;
```

---

### Testing Best Practices

**Test attribution fields in CRUD operations:**

```python
# tests/test_attribution.py
def test_create_trade_with_attribution_fields(db_pool, clean_test_data, sample_market, sample_strategy):
    """Verify trade attribution fields recorded correctly."""
    trade_id = create_trade(
        market_id=sample_market,
        strategy_id=sample_strategy,
        model_id=1,
        side="YES",
        quantity=75,
        price=Decimal("0.5200"),
        calculated_probability=Decimal("0.6250"),
        market_price=Decimal("0.5200"),
        trade_source="automated",
    )

    trade = get_trade_by_id(trade_id)

    # Verify attribution fields
    assert trade["calculated_probability"] == Decimal("0.6250")
    assert trade["market_price"] == Decimal("0.5200")
    assert trade["edge_value"] == Decimal("0.1050")  # Auto-calculated
    assert trade["trade_source"] == "automated"
```

---

### Common Mistakes

**1. Forgetting attribution fields**
```python
# ❌ WRONG - No attribution
create_trade(..., price=Decimal("0.5200"))

# ✅ CORRECT - Full attribution
create_trade(
    ...,
    price=Decimal("0.5200"),
    calculated_probability=Decimal("0.6250"),
    market_price=Decimal("0.5200"),
)
```

**2. Updating position attribution (violates immutability)**
```python
# ❌ WRONG - Trying to update position attribution
UPDATE positions
SET calculated_probability = 0.7000  -- ❌ Violates ADR-018 immutability
WHERE id = 123;

# ✅ CORRECT - Position attribution is immutable, create new version instead
```

**3. Using FLOAT instead of DECIMAL**
```python
# ❌ WRONG - Float for probabilities
calculated_probability = 0.6250  # float

# ✅ CORRECT - Decimal for probabilities
calculated_probability = Decimal("0.6250")  # Decimal
```

---

### Related ADRs & Patterns

- **ADR-090**: Strategy Contains Entry + Exit Rules with Nested Versioning
- **ADR-091**: Explicit Columns for Trade/Position Attribution (vs JSONB)
- **ADR-092**: Trade Source Tracking and Manual Trade Reconciliation
- **ADR-018**: Immutable Versioning (positions locked to strategy/model version)
- **ADR-002**: Decimal Precision for All Financial Data
- **Pattern 1**: Decimal Precision (NEVER USE FLOAT)
- **Pattern 3**: Trade Attribution (basic strategy_id/model_id linkage)
- **Migration 018**: Trade Source Tracking (`trade_source` enum)
- **Migration 019**: Trade Attribution Enrichment (calculated_probability, market_price, edge_value)
- **Migration 020**: Position Attribution (immutable entry snapshots)

---

### Enforcement

| Check | Enforcement | Command |
|-------|-------------|---------|
| Attribution fields present | Code review | Manual verification of create_trade/create_position calls |
| Decimal precision | Pre-commit hook | `git grep "calculated_probability.*float" -- '*.py'` |
| Immutability | Code review | `git grep "UPDATE positions SET calculated_probability" -- '*.py' '*.sql'` |
| Tests exist | Pytest (pre-push hook) | `pytest tests/test_attribution.py -v` |

---

## Pattern 16: Type Safety with Dynamic Data - YAML/JSON Parsing (ALWAYS)

**Summary:** When parsing YAML/JSON files with `yaml.safe_load()` or `json.load()`, the return type is `Any`. To avoid Mypy `no-any-return` errors, use explicit `cast()` to declare the expected type structure.

**Why This Matters:**
- **Type Safety:** `yaml.safe_load()` returns `Any`, which defeats Mypy's type checking
- **Recurring Issue:** This pattern occurred in 4 validation scripts (validate_phase_start.py, validate_phase_completion.py, validate_test_fixtures.py, validate_property_tests.py)
- **Maintainability:** Explicit casts document the expected structure and catch type mismatches early
- **No Runtime Cost:** `cast()` is a no-op at runtime, zero performance impact

### ✅ CORRECT: Explicit Type Cast

```python
from typing import Any, cast
import yaml

def load_config() -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Returns:
        Configuration dictionary

    Educational Note:
        yaml.safe_load() returns Any. We use cast() to explicitly
        declare the expected structure for type safety.
    """
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        # ✅ Explicit cast makes type expectations clear
        return cast("dict[str, Any]", config.get("settings", {}))
```

### ❌ WRONG: No Type Cast (Mypy Error)

```python
import yaml

def load_config() -> dict[str, Any]:  # ❌ Mypy error: no-any-return
    """Load configuration from YAML file."""
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        # ❌ Mypy complains: returning Any from function declared to return dict
        return config.get("settings", {})
```

**Mypy Error:**
```
error: Returning Any from function declared to return "dict[str, Any]"  [no-any-return]
```

### Common Patterns

**1. Nested Dictionary Access:**
```python
from typing import Any, cast

# ✅ Cast at each level of nesting
def get_database_config() -> dict[str, str]:
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        db_config = cast("dict[str, Any]", config.get("database", {}))
        return cast("dict[str, str]", db_config.get("connection", {}))
```

**2. List of Dictionaries:**
```python
from typing import Any, cast

# ✅ Cast list structure
def load_deliverables() -> list[dict[str, Any]]:
    with open("phase_config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        phase_data = cast("dict[str, Any]", config.get("phase_1", {}))
        return cast("list[dict[str, Any]]", phase_data.get("deliverables", []))
```

**3. JSON Parsing (Same Pattern):**
```python
import json
from typing import Any, cast

# ✅ Same pattern for JSON
def load_api_response() -> dict[str, Any]:
    with open("response.json", encoding="utf-8") as f:
        data = json.load(f)  # Returns Any
        return cast("dict[str, Any]", data)
```

### Real-World Example

**Context:** PR #98 fixed Mypy errors in 4 validation scripts

**Before (Mypy Errors):**
```python
# scripts/validate_phase_start.py:70
def load_phase_deliverables(phase: str) -> dict:  # ❌ Missing type annotation
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            phase_deliverables = config.get("phase_deliverables", {})
            # ❌ Mypy error: no-any-return
            return phase_deliverables.get(phase, {})
    except Exception:
        return {}
```

**After (Type-Safe):**
```python
from typing import Any, cast

def load_phase_deliverables(phase: str) -> dict[Any, Any]:  # ✅ Explicit type
    validation_config_path = PROJECT_ROOT / "scripts" / "validation_config.yaml"

    try:
        with open(validation_config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            phase_deliverables = config.get("phase_deliverables", {})
            # ✅ Explicit cast makes type expectations clear
            return cast("dict[Any, Any]", phase_deliverables.get(phase, {}))
    except Exception:
        return {}
```

### When to Use This Pattern

| Scenario | Use Cast? | Rationale |
|----------|-----------|-----------|
| Loading YAML/JSON config | ✅ ALWAYS | `yaml.safe_load()` returns `Any` |
| Accessing nested dictionaries from YAML | ✅ ALWAYS | Each `.get()` call returns `Any` |
| Parsing API responses (TypedDict) | ❌ NO | Use TypedDict + validation instead (Pattern 6) |
| Reading user input | ✅ ALWAYS | `input()` returns `str`, but structure is `Any` after parsing |
| Database query results | ✅ DEPENDS | If using raw SQL with `fetchall()`, yes. ORM models, no. |

### Common Mistakes

**1. Forgetting to Import `cast`:**
```python
# ❌ WRONG: NameError
return cast("dict[str, Any]", config.get("key", {}))  # cast not imported
```

**Fix:**
```python
from typing import Any, cast  # ✅ Import both
```

**2. Unquoted Type in `cast()` (Ruff TC006):**
```python
# ❌ WRONG: Ruff TC006 violation
return cast(dict[str, Any], config.get("key", {}))
```

**Fix:**
```python
# ✅ CORRECT: Quoted type for better string interning
return cast("dict[str, Any]", config.get("key", {}))
```

**3. Using `assert isinstance()` Instead:**
```python
# ❌ WRONG: Runtime overhead, doesn't help Mypy
config = yaml.safe_load(f)
assert isinstance(config, dict)  # Runtime check, not static
return config.get("key", {})  # Still returns Any
```

**Fix:**
```python
# ✅ CORRECT: No runtime cost, Mypy understands
config = yaml.safe_load(f)
return cast("dict[str, Any]", config.get("key", {}))
```

### References

- **Related Pattern:** Pattern 6 (TypedDict for API Response Types)
- **Mypy Error:** `no-any-return` ([Mypy Docs](https://mypy.readthedocs.io/en/stable/error_code_list.html#check-that-function-does-not-return-any-value-no-any-return))
- **Ruff Rule:** TC006 (Unquoted type in cast)
- **Real-World Example:** PR #98 (Validation script Mypy fixes)
- **Files Affected:** validate_phase_start.py (lines 71), validate_phase_completion.py (lines 68), validate_test_fixtures.py (lines 88-90), validate_property_tests.py (lines 99-101)

---

## Pattern 17: Avoid Nested If Statements - Use Combined Conditions (ALWAYS)

**Summary:** Nested `if` statements reduce readability. Combine conditions using `and`/`or` operators to create flat, readable control flow. This follows Ruff rule SIM102.

**Why This Matters:**
- **Readability:** Flat conditions are easier to understand than nested blocks
- **Maintainability:** Less indentation = easier to modify logic
- **Cyclomatic Complexity:** Reduces complexity metrics for better code quality
- **Tool Support:** Ruff SIM102 automatically detects nested if antipattern

### ✅ CORRECT: Combined Conditions

```python
def check_phase_dependencies(phase_num: float, content: str) -> list[str]:
    """Check if previous phases are complete."""
    violations = []

    # ✅ CORRECT: Combined condition (flat structure)
    if phase_num >= 2 and not re.search(r"Phase\s+1[^.0-9].*?✅", content, re.IGNORECASE):
        violations.append("Phase 1 not complete (required for Phase >= 2)")

    # ✅ CORRECT: Another combined condition
    if phase_num >= 1.5 and not re.search(r"Phase\s+1[^.]", content):
        violations.append("Phase 1 not found in DEVELOPMENT_PHASES")

    return violations
```

### ❌ WRONG: Nested If Statements (Ruff SIM102)

```python
def check_phase_dependencies(phase_num: float, content: str) -> list[str]:
    """Check if previous phases are complete."""
    violations = []

    # ❌ WRONG: Nested if (harder to read, Ruff SIM102 violation)
    if phase_num >= 2:
        if not re.search(r"Phase\s+1[^.0-9].*?✅", content, re.IGNORECASE):
            violations.append("Phase 1 not complete (required for Phase >= 2)")

    # ❌ WRONG: Another nested if
    if phase_num >= 1.5:
        if not re.search(r"Phase\s+1[^.]", content):
            violations.append("Phase 1 not found in DEVELOPMENT_PHASES")

    return violations
```

**Ruff Error:**
```
SIM102 Use a single `if` statement instead of nested `if` statements
```

### Complex Conditions

**Multiple AND Conditions:**
```python
# ✅ CORRECT: All conditions must be true
if user.is_authenticated and user.has_permission("write") and not user.is_banned:
    save_data(user)

# ❌ WRONG: Nested structure
if user.is_authenticated:
    if user.has_permission("write"):
        if not user.is_banned:
            save_data(user)
```

**Mixed AND/OR Conditions:**
```python
# ✅ CORRECT: Use parentheses for clarity
if (phase_num >= 2 and phase1_complete) or phase_num < 1.5:
    proceed_to_next_phase()

# ❌ WRONG: Nested if/else
if phase_num >= 2:
    if phase1_complete:
        proceed_to_next_phase()
else:
    if phase_num < 1.5:
        proceed_to_next_phase()
```

**Early Return Pattern:**
```python
# ✅ CORRECT: Early return avoids nesting
def validate_config(config: dict) -> str | None:
    if not config:
        return "Config is empty"

    if "database" not in config:
        return "Missing database config"

    if config["database"]["port"] < 1024:
        return "Port must be >= 1024"

    return None  # All checks passed

# ❌ WRONG: Nested structure
def validate_config(config: dict) -> str | None:
    if config:
        if "database" in config:
            if config["database"]["port"] >= 1024:
                return None
            else:
                return "Port must be >= 1024"
        else:
            return "Missing database config"
    else:
        return "Config is empty"
```

### Real-World Example

**Context:** PR #98 fixed nested if statements in validate_phase_start.py

**Before (Ruff SIM102 Violation):**
```python
# scripts/validate_phase_start.py:171-179
def check_phase_dependencies(phase: str, verbose: bool = False) -> tuple[bool, list[str]]:
    violations = []
    phase_num = float(phase)

    # Read DEVELOPMENT_PHASES content...

    # ❌ Nested if (SIM102)
    if phase_num >= 2:
        if not re.search(r"Phase\s+1[^.0-9].*?✅", content, re.IGNORECASE):
            violations.append("Phase 1 not complete (required for Phase >= 2)")

    # ❌ Another nested if
    if phase_num >= 1.5:
        if not re.search(r"Phase\s+1[^.]", content):
            violations.append("Phase 1 not found in DEVELOPMENT_PHASES")

    return len(violations) == 0, violations
```

**After (Flat Structure):**
```python
# scripts/validate_phase_start.py:171-179
def check_phase_dependencies(phase: str, verbose: bool = False) -> tuple[bool, list[str]]:
    violations = []
    phase_num = float(phase)

    # Read DEVELOPMENT_PHASES content...

    # ✅ Combined condition (flat, readable)
    if phase_num >= 2 and not re.search(r"Phase\s+1[^.0-9].*?✅", content, re.IGNORECASE):
        violations.append("Phase 1 not complete (required for Phase >= 2)")

    # ✅ Another combined condition
    if phase_num >= 1.5 and not re.search(r"Phase\s+1[^.]", content):
        violations.append("Phase 1 not found in DEVELOPMENT_PHASES")

    return len(violations) == 0, violations
```

### When to Use This Pattern

| Scenario | Use Combined Conditions? | Rationale |
|----------|--------------------------|-----------|
| Two conditions both must be true | ✅ YES | `if A and B:` is clearer than `if A: if B:` |
| Early validation checks | ✅ YES (early return) | Flat structure, easier to follow |
| Complex boolean logic (>3 conditions) | ✅ YES (with parentheses) | Use parentheses for readability |
| Mutually exclusive conditions | ❌ NO (use elif) | `if A: ... elif B: ...` is correct |
| Different actions per condition | ❌ NO (use separate ifs) | Separate logic should be separate blocks |

### When Nested If Is Actually Better

**1. Different Error Messages Per Layer:**
```python
# ✅ Nested is clearer here (different messages)
if user.is_authenticated:
    if user.has_permission("write"):
        save_data()
    else:
        raise PermissionError("User lacks write permission")
else:
    raise AuthenticationError("User not authenticated")

# ❌ Combined is confusing (which error to raise?)
if not user.is_authenticated:
    raise AuthenticationError("User not authenticated")
elif not user.has_permission("write"):
    raise PermissionError("User lacks write permission")
else:
    save_data()
```

**2. Early Exit with Resource Cleanup:**
```python
# ✅ Nested is clearer (different cleanup paths)
if file_exists(path):
    with open(path) as f:
        if validate_header(f):
            process_file(f)
        else:
            log("Invalid header")
else:
    log("File not found")
```

### References

- **Ruff Rule:** SIM102 ([Ruff Docs](https://docs.astral.sh/ruff/rules/collapsible-if/))
- **Related:** Cyclomatic Complexity metrics ([Wikipedia](https://en.wikipedia.org/wiki/Cyclomatic_complexity))
- **Real-World Example:** PR #98 (validate_phase_start.py nested if fixes)
- **Files Affected:** validate_phase_start.py (lines 171-179)

---

## Pattern 18: Avoid Technical Debt - Fix Root Causes, Not Symptoms (ALWAYS)

**Rule:** When you discover bugs or quality issues, fix the root cause and track any deferred work formally. Never use "will fix later" without GitHub issue + scheduled resolution + documented rationale.

**Why:** Technical debt compounds exponentially. A quick hack today becomes 10x harder to fix in 6 months when:
- Context is lost ("why did we do this?")
- Code has evolved (breaking the hack breaks other things)
- Team has changed (new developers don't know the hack exists)
- Production depends on buggy behavior (can't change without breaking users)

**Real-World Example:** Phase 1.5 completion discovered 21 validation violations (19 SCD queries missing row_current_ind filter + 2 integration tests missing real fixtures). Instead of:
- ❌ Quick fix: Add `--no-verify` flag and forget about it (silent technical debt)
- ❌ Comment: "TODO: Fix SCD queries later" (no tracking, no schedule)
- ✅ Formal tracking: GitHub Issue #101 + PHASE_1.5_DEFERRED_TASKS.md + Phase 2 Week 1 scheduled fix

### Technical Debt Classification System

Classify all deferred work by priority based on risk and impact:

| Priority | Symbol | Criteria | Timeline | Examples |
|----------|--------|----------|----------|----------|
| **Critical** | 🔴 | Could cause data corruption, security vulnerabilities, or production outages | Fix in next sprint | SCD queries (wrong data), security vulnerabilities, data integrity violations |
| **High** | 🟡 | Affects code quality, test reliability, or developer productivity | Fix within 2-3 sprints | Missing test coverage, configuration drift, infrastructure gaps |
| **Medium** | 🟢 | Nice-to-have improvements, refactoring, optimization | Fix within 3-6 months | Code cleanup, documentation gaps, minor UX issues |
| **Low** | 🔵 | Cosmetic issues, future enhancements | Fix as time allows | Linting warnings, TODO comments, aspirational features |

**Decision Tree:**

```
Is this blocking the next phase?
├── YES → Fix immediately (not technical debt)
└── NO → Is this a bug or quality issue?
    ├── YES → Critical/High priority (defer with formal tracking)
    └── NO → Enhancement (add to backlog, may not schedule)
```

### Three-Part Technical Debt Workflow

#### Part 1: Acknowledge (5 minutes)

**Create GitHub Issue with comprehensive documentation:**

```markdown
**Title:** Fix 21 validation violations discovered by Phase 1.5 pre-push hooks

**Labels:** pattern-violation, priority-high, deferred-task

**Description:**

## Problem

Pre-push hooks discovered 21 violations:
1. **19 SCD Type 2 violations** (exact file:line references below)
2. **2 Test fixture violations** (missing db_pool, db_cursor)

## Part 1: SCD Type 2 Query Violations

Pattern 2 (Dual Versioning) requires all queries on SCD Type 2 tables to
filter by `row_current_ind = TRUE`. The following queries are missing this filter:

```
1. src/precog/database/crud_operations.py:625 (get_market_history)
2. src/precog/trading/position_manager.py:142 (get_positions_by_status)
... [list all 19 violations]
```

## Part 2: Test Fixture Violations

Pattern 13 (Coverage Quality) requires integration tests to use real fixtures.
The following tests use mocks instead:

```
1. tests/integration/test_strategy_manager_integration.py
   Missing: db_pool, db_cursor fixtures

2. tests/integration/test_model_manager_integration.py
   Missing: db_pool, db_cursor fixtures
```

## Implementation Plan

**Phase 2 Week 1 (5-6 hours):**
1. Review all 19 SCD queries - add filters or exception comments (3-4h)
2. Update 2 integration test files with real fixtures (1-2h)
3. Validation and documentation (30min)

## Success Criteria

- [ ] All SCD queries have `row_current_ind = TRUE` OR documented exception
- [ ] All integration tests use real fixtures (no mocks)
- [ ] Validation scripts pass
- [ ] Tests pass

## Rationale for Deferral

- ✅ Non-blocking (existing bugs, not new blockers for Phase 2)
- ✅ Validation enhancement discovery (violations existed before, newly detected)
- ✅ Pattern compliance, not functionality (code works, violates patterns)
- ✅ Formally tracked (this issue + deferred tasks doc)
- ✅ Scheduled (Phase 2 Week 1)
```

**Critical Elements:**
- Exact file:line references (not "some files need fixing")
- Implementation plan with time estimates
- Success criteria (checkboxes for tracking)
- Rationale for deferral (why not fixing now)

#### Part 2: Schedule (5 minutes)

**Add to PHASE_X_DEFERRED_TASKS.md:**

```markdown
### DEF-P1.5-002: Fix 21 Validation Violations (19 SCD + 2 fixtures)

**Priority:** 🔴 Critical
**Target Phase:** Phase 2 Week 1
**Time Estimate:** 5-6 hours
**Category:** Code Quality / Pattern Compliance
**GitHub Issue:** #101

#### Rationale

These 21 violations were discovered by enhanced pre-push hooks and deferred because:

1. **Non-blocking:** Existing bugs, not blockers for Phase 2 ESPN integration
2. **Validation discovery:** New scripts found violations that existed before
3. **Pattern compliance:** Code works but violates Pattern 2 (SCD) and Pattern 13 (fixtures)
4. **Formally tracked:** GitHub issue + scheduled fix
5. **User test:** Validates our tech debt workflow handles deferral properly

**Why Critical Priority:**
- Pattern 2 violations risk querying historical data (subtle bugs)
- Pattern 13 violations mean tests may pass with bugs (false confidence)
- Should fix BEFORE significant Phase 2 development

#### Implementation Plan

[Detailed 3-task breakdown from GitHub issue]

#### Success Criteria

- [ ] All SCD queries compliant
- [ ] All integration tests use real fixtures
- [ ] Validation scripts pass
- [ ] Tests pass

#### References

- GitHub Issue #101
- Pattern 2 (Dual Versioning)
- Pattern 13 (Coverage Quality)
- validate_scd_queries.py, validate_test_fixtures.py
```

**Multi-Location Tracking:**
1. **GitHub Issues** - Searchable, trackable, linkable
2. **PHASE_X_DEFERRED_TASKS.md** - Comprehensive documentation with rationale
3. **DEVELOPMENT_PHASES.md** - Phase deliverables tracking (optional)

#### Part 3: Fix (Scheduled)

**When the scheduled phase arrives (Phase 2 Week 1):**

1. **Review Context** - Re-read GitHub issue + deferred tasks doc
2. **Implement Fixes** - Follow implementation plan from issue
3. **Validate** - Run validation scripts (validate_scd_queries.py, validate_test_fixtures.py)
4. **Test** - Verify all tests pass with fixes
5. **Close Issue** - Update PHASE_X_DEFERRED_TASKS.md (mark complete), close GitHub issue
6. **Document** - Add completion note to SESSION_HANDOFF.md

**Time Tracking:** Compare actual vs estimated time → improve future estimates

### When Deferral is Acceptable

**✅ ACCEPTABLE to defer when ALL of:**
- Non-blocking (next phase can start without fix)
- Formally tracked (GitHub issue created)
- Scheduled (specific phase/sprint assigned)
- Documented rationale (why deferring, why not blocking)
- Priority assigned (🔴/🟡/🟢/🔵)
- Success criteria defined (checkbox list)

**❌ NEVER ACCEPTABLE to defer:**
- Data corruption risks (fix immediately)
- Security vulnerabilities (fix immediately)
- Production outages (fix immediately)
- Blocking bugs (must fix to proceed)
- "Will fix later" without tracking

### Common Technical Debt Patterns

#### Pattern 1: Configuration Drift (Pattern 8 Violation)

**Symptom:** YAML config says one thing, Python code does another

**Root Cause:** Updated code without updating config, or vice versa

**Example from Phase 1.5:**
```python
# validation_config.yaml
required_pattern: ".filter(table.c.row_current_ind == True)"  # ORM pattern

# validate_scd_queries.py
if "required_pattern" in scd_config:
    # ❌ Code detects YAML exists, then ignores it and hardcodes different pattern
    required_patterns = [
        r"\.filter\([^)]*row_current_ind\s*==\s*True[^)]*\)",
    ]
```

**Fix:** Make code actually read and use YAML pattern:
```python
if "required_pattern" in scd_config:
    # ✅ Use pattern from YAML
    required_patterns = [scd_config["required_pattern"]]
```

**Prevention:** Pattern 8 enforcement (synchronize tool configs, application configs, documentation)

#### Pattern 2: Quick Hack Instead of Root Cause Fix

**Symptom:** Validation failing → add `--no-verify` flag → forget about it

**Root Cause:** Pressure to ship, lack of tracking system

**Example:**
```bash
# ❌ WRONG: Bypass hook without tracking
git push --no-verify origin feature-branch

# No GitHub issue created
# No deferred tasks document updated
# 6 months later: "Why are we using --no-verify?"
```

**Fix:**
```bash
# ✅ CORRECT: Create formal tracking BEFORE bypass
gh issue create --title "Fix 21 validation violations" --label "deferred-task"
# Update PHASE_X_DEFERRED_TASKS.md with comprehensive plan
# THEN use --no-verify with clear justification
git push --no-verify origin feature-branch
```

**Prevention:** Mandatory GitHub issue creation before any `--no-verify` usage

#### Pattern 3: False Positives Ignored Instead of Fixed

**Symptom:** Validation script reports 100 violations → half are false positives → ignored

**Root Cause:** Validation script too broad, didn't account for edge cases

**Example from Phase 1.5:**
```
Initial: 78 SCD violations reported
After fixing false positives: 19 genuine violations (76% reduction)

False positive categories:
- INSERT/UPDATE operations (32 violations - write ops don't need filter)
- Docstring examples (17 violations - >>> examples in comments)
- Migration files (6 violations - transform all versions intentionally)
- Historical audit functions (3 violations - get_*_history fetches all versions)
```

**Fix:** Update validation script to exclude legitimate patterns:
```python
# Exclude write operations
if any(re.search(rf"\b{op}\s+{table}\b", line) for op in ["INSERT", "UPDATE"]):
    continue  # Write operations don't query, don't need row_current_ind filter

# Exclude migrations
if "migrations" in str(python_file):
    continue  # Migrations transform all versions

# Auto-detect history functions
if re.search(r"def\s+\w*history\w*\s*\(", func_context):
    continue  # Historical audit functions fetch all versions
```

**Prevention:** Iterative validation script improvement based on false positive analysis

### Anti-Patterns (NEVER DO THIS)

#### 1. "TODO: Fix later" Comments

**❌ WRONG:**
```python
def get_positions_by_status(status: str):
    # TODO: Add row_current_ind filter (violates Pattern 2)
    query = "SELECT * FROM positions WHERE status = %s"
    return fetch_all(query, (status,))
```

**Why wrong:** No tracking, no schedule, will be forgotten

**✅ CORRECT:**
```python
def get_positions_by_status(status: str):
    # DEBT: Missing row_current_ind filter (GitHub Issue #101, Phase 2 Week 1)
    # See: docs/utility/PHASE_1.5_DEFERRED_TASKS.md (DEF-P1.5-002)
    query = "SELECT * FROM positions WHERE status = %s"
    return fetch_all(query, (status,))
```

**Better:** Fix immediately if <15 minutes, or defer with full tracking

#### 2: Silent Bypasses

**❌ WRONG:**
```bash
# Pre-push hook failing? Just bypass it
git push --no-verify origin feature-branch
# No issue created, no tracking, no schedule
```

**✅ CORRECT:**
```bash
# 1. Create GitHub issue documenting violations
gh issue create --title "..." --label "deferred-task"

# 2. Update PHASE_X_DEFERRED_TASKS.md with plan
# Add comprehensive rationale, implementation plan, success criteria

# 3. Bypass hook with clear justification
git push --no-verify origin feature-branch

# 4. Document bypass in commit message
git commit --amend -m "...

Bypassed pre-push hooks due to 21 deferred violations (Issue #101).
Formal tracking: docs/utility/PHASE_1.5_DEFERRED_TASKS.md (DEF-P1.5-002)
Scheduled fix: Phase 2 Week 1 (5-6 hours)"
```

#### 3: Vague Tracking

**❌ WRONG:**
```markdown
- [ ] Fix some database queries
- [ ] Improve test coverage
```

**✅ CORRECT:**
```markdown
- [ ] Fix 19 SCD queries missing row_current_ind filter (src/precog/database/crud_operations.py:625, +18 more)
- [ ] Add db_pool, db_cursor fixtures to 2 integration tests (test_strategy_manager_integration.py, test_model_manager_integration.py)
```

**Why:** Specific file:line references enable quick fixes, vague tracking enables forgetting

### Decision Matrix

| Scenario | Priority | Action | Timeline |
|----------|----------|--------|----------|
| **Security vulnerability** | 🔴 N/A | Fix immediately | Before next commit |
| **Data corruption risk** | 🔴 N/A | Fix immediately | Before next commit |
| **Blocking bug** | N/A | Fix immediately | Before next phase |
| **Pattern violation (critical)** | 🔴 Critical | Defer with tracking | Next sprint |
| **Pattern violation (quality)** | 🟡 High | Defer with tracking | 2-3 sprints |
| **Code cleanup** | 🟢 Medium | Defer with tracking | 3-6 months |
| **TODO comment** | 🔵 Low | Create issue or delete | As time allows |

### Real-World Validation

**Phase 1.5 Example - User Test of Debt Workflow:**

User explicitly chose Option B (defer with formal tracking) to validate our technical debt workflow:
> "fine, let's do option B, it will help confirm that our workflow is handling tech debt and defect tracking and resolution satisfactorily"

**What We Did:**
1. ✅ Created GitHub Issue #101 with 21 violations (exact file:line references)
2. ✅ Updated PHASE_1.5_DEFERRED_TASKS.md (V1.0 → V1.1) with comprehensive plan
3. ✅ Assigned 🔴 Critical priority (Pattern 2/13 violations)
4. ✅ Scheduled Phase 2 Week 1 fix (5-6 hours estimated)
5. ✅ Documented rationale (non-blocking, formally tracked, scheduled)
6. ✅ Used `--no-verify` with clear justification

**Result:** Technical debt properly tracked, scheduled, and documented (Pattern 18 validated)

### References

- **GitHub Issue:** #101 (Fix 21 validation violations)
- **Deferred Tasks:** docs/utility/PHASE_1.5_DEFERRED_TASKS_V1.0.md (DEF-P1.5-002)
- **Related Patterns:** Pattern 2 (SCD Type 2 filtering), Pattern 8 (Config Synchronization), Pattern 13 (Real Fixtures)
- **Validation Scripts:** scripts/validate_scd_queries.py, scripts/validate_test_fixtures.py
- **Philosophy:** DEVELOPMENT_PHILOSOPHY_V1.1.md Section "Technical Debt Management"

---

## Pattern 19: Hypothesis Decimal Strategy - Use Decimal Strings for min/max (ALWAYS)

**ALWAYS use Decimal strings (not float literals) when defining Hypothesis decimals() strategy min/max values.**

### Core Principle

When using Hypothesis `decimals()` strategy with `places` parameter, binary floats (like `0.1`) cannot be exactly represented as Decimal with fixed decimal places, causing deprecation warnings. Using Decimal strings eliminates warnings AND improves test precision by avoiding float-to-Decimal conversion artifacts.

---

### ✅ CORRECT: Decimal Strings for min/max

```python
from decimal import Decimal
from hypothesis import strategies as st

# ✅ CORRECT - Use Decimal strings for min_value and max_value
@st.composite
def edge_value(draw, min_value=Decimal("0.0100"), max_value=Decimal("0.5000")):
    """
    Generate edge values (difference between true probability and market price).

    Uses Decimal strings for precise boundary specification, avoiding
    float-to-Decimal conversion warnings from Hypothesis.

    Educational Note:
        Binary float 0.01 cannot be exactly represented as Decimal("0.0100").
        Using Decimal("0.0100") directly ensures exact precision and eliminates
        HypothesisDeprecationWarning about inexact decimal representation.

    Example:
        >>> strategy = edge_value(min_value=Decimal("0.0100"), max_value=Decimal("0.5000"))
        >>> edge = strategy.example()
        >>> assert Decimal("0.0100") <= edge <= Decimal("0.5000")
        >>> assert edge.as_tuple().exponent == -4  # Exactly 4 decimal places

    References:
        - Pattern 1 (Decimal Precision): All prices/probabilities use Decimal
        - SESSION_HANDOFF.md (2025-11-23): SESSION 4.3 Hypothesis Decimal fix
        - warning_baseline.json: hypothesis_decimal_precision count 17→0
    """
    return draw(st.decimals(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
        places=4  # Sub-penny precision (Kalshi standard)
    ))


# ✅ CORRECT - Decimal strings for probability range
@st.composite
def decimal_price(draw, min_value=Decimal("0.0001"), max_value=Decimal("0.9999")):
    """Generate valid Kalshi market prices (0.0001 to 0.9999, 4 decimal places)."""
    return draw(st.decimals(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
        places=4
    ))


# ✅ CORRECT - Decimal strings for Kelly fraction range
@st.composite
def kelly_fraction(draw, min_value=Decimal("0.10"), max_value=Decimal("0.50")):
    """Generate Kelly fractions (0.10 to 0.50, 2 decimal places)."""
    return draw(st.decimals(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
        places=2  # Kelly fractions use 2 decimal places (10%, 25%, etc.)
    ))
```

**Why this works:**
- ✅ No float-to-Decimal conversion (no precision loss)
- ✅ No Hypothesis deprecation warnings
- ✅ Exact boundary specification (0.0100 is exactly 0.0100, not 0.009999...)
- ✅ Consistent with Pattern 1 (Decimal Precision) - all code uses Decimal strings

---

### ❌ WRONG: Float Literals for min/max

```python
from hypothesis import strategies as st

# ❌ WRONG - Float literals cause deprecation warnings
@st.composite
def edge_value(draw, min_value=0.01, max_value=0.5):  # Float literals!
    return draw(st.decimals(
        min_value=min_value,  # Binary float 0.01 ≠ Decimal("0.0100")
        max_value=max_value,  # Binary float 0.5 ≠ Decimal("0.5000")
        allow_nan=False,
        allow_infinity=False,
        places=4  # Hypothesis warning: "0.01 cannot be exactly represented as a decimal with places=4"
    ))
```

**Problems:**
- ❌ Hypothesis emits deprecation warning for each test execution
- ❌ Float-to-Decimal conversion introduces precision artifacts (0.01 → 0.009999999999...)
- ❌ Test boundaries not exact (testing 0.009999... instead of 0.0100)
- ❌ Warning debt accumulates (17 warnings in Phase 1.5 before fix)

---

### Real-World Impact (Phase 1.5 SESSION 4.3)

**Before Fix (Float Literals):**
```python
# tests/property/test_kelly_criterion_properties.py (line 249 - BEFORE)
@given(
    edge=edge_value(min_value=0.01, max_value=0.5),  # Float literals
    kelly_frac=kelly_fraction(min_value=0.1, max_value=0.5),  # Float literals
    bankroll=bankroll_amount(min_value=100, max_value=100000)
)
def test_kelly_size_increases_with_edge(edge, kelly_frac, bankroll):
    # ...test code...
```

**Warning Output:**
```
HypothesisDeprecationWarning: 0.01 cannot be exactly represented as a decimal with places=4.
  You should pass in a value that is exactly representable as a decimal with that number of places.
```

**After Fix (Decimal Strings):**
```python
# tests/property/test_kelly_criterion_properties.py (line 249 - AFTER)
@given(
    edge=edge_value(min_value=Decimal("0.0100"), max_value=Decimal("0.5000")),  # Decimal strings
    kelly_frac=kelly_fraction(min_value=Decimal("0.10"), max_value=Decimal("0.50")),  # Decimal strings
    bankroll=bankroll_amount(min_value=100, max_value=100000)
)
def test_kelly_size_increases_with_edge(edge, kelly_frac, bankroll):
    # ...test code...
```

**Result:**
- ✅ 0 HypothesisDeprecationWarnings (down from 17)
- ✅ Exact test boundaries (0.0100 is precisely 0.0100)
- ✅ Warning baseline reduced 79 → 83 (net +4 due to Mypy regression, but Hypothesis warnings eliminated)

**Session 4.3 Statistics:**
- **Files modified:** 3 (test_config_validation_properties.py, test_kelly_criterion_properties.py, test_edge_detection_properties.py)
- **Code edits:** 15 (all float literals → Decimal strings)
- **Warnings eliminated:** 17
- **Time:** 1.5 hours

---

### When to Use This Pattern

**ALWAYS use Decimal strings when:**
- ✅ Defining Hypothesis `decimals()` strategy with `places` parameter
- ✅ Setting min_value or max_value for price/probability/edge strategies
- ✅ Creating custom Hypothesis strategies for trading domain
- ✅ Testing Decimal-based business logic (Kelly sizing, edge detection, position sizing)

**Example Scenarios:**
1. **Price strategies:** `min_value=Decimal("0.0001"), max_value=Decimal("0.9999")`
2. **Edge strategies:** `min_value=Decimal("0.0100"), max_value=Decimal("0.5000")`
3. **Kelly fractions:** `min_value=Decimal("0.10"), max_value=Decimal("0.50")`
4. **Probability strategies:** `min_value=Decimal("0.0000"), max_value=Decimal("1.0000")`

---

### Common Mistakes

#### Mistake 1: Forgetting Decimal import

**❌ WRONG:**
```python
from hypothesis import strategies as st

@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.01"),  # NameError: name 'Decimal' is not defined
        max_value=Decimal("0.50"),
        places=4
    ))
```

**✅ CORRECT:**
```python
from decimal import Decimal  # ← Must import Decimal!
from hypothesis import strategies as st

@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("0.50"),
        places=4
    ))
```

#### Mistake 2: Mixing float and Decimal

**❌ WRONG:**
```python
@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.01"),  # Decimal string
        max_value=0.50,             # Float literal (inconsistent!)
        places=4
    ))
```

**✅ CORRECT:**
```python
@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.01"),  # Decimal string
        max_value=Decimal("0.50"),  # Decimal string (consistent!)
        places=4
    ))
```

#### Mistake 3: Wrong number of decimal places in string

**❌ WRONG:**
```python
@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.01"),    # Only 2 decimal places
        max_value=Decimal("0.5"),     # Only 1 decimal place
        places=4                      # But strategy expects 4 places!
    ))
```

**✅ CORRECT:**
```python
@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.0100"),  # Exactly 4 decimal places
        max_value=Decimal("0.5000"),  # Exactly 4 decimal places
        places=4                      # Matches min/max precision
    ))
```

**Why:** Hypothesis will still work with mismatched precision, but using exact precision makes test intent clearer and avoids potential boundary issues.

---

### Testing This Pattern

**Verify Decimal string strategy works correctly:**
```python
from decimal import Decimal
from hypothesis import strategies as st, given

@st.composite
def edge_value(draw):
    return draw(st.decimals(
        min_value=Decimal("0.0100"),
        max_value=Decimal("0.5000"),
        places=4
    ))

@given(edge=edge_value())
def test_edge_value_precision(edge):
    """Verify Decimal strategy generates exact 4-decimal-place values."""
    assert isinstance(edge, Decimal)
    assert Decimal("0.0100") <= edge <= Decimal("0.5000")
    assert edge.as_tuple().exponent == -4  # Exactly 4 decimal places
```

**Verify no warnings emitted:**
```bash
# Run property tests with warnings enabled
python -m pytest tests/property/ -v -W default 2>&1 | grep -i "HypothesisDeprecationWarning"

# Expected: No output (zero Hypothesis deprecation warnings)
```

---

### Cross-References

**Related Patterns:**
- **Pattern 1:** Decimal Precision (NEVER USE FLOAT) - Foundation for all Decimal usage
- **Pattern 10:** Property-Based Testing with Hypothesis (ALWAYS for Trading Logic) - When to use property tests

**Architecture Decisions:**
- **ADR-074:** Property-Based Testing with Hypothesis for Trading Logic Validation
- **ADR-002:** Decimal Precision for Sub-Penny Pricing (foundational Decimal decision)

**Warning Governance:**
- **Pattern 9:** Multi-Source Warning Governance (MANDATORY) - How this pattern reduces warning debt
- **scripts/warning_baseline.json:** hypothesis_decimal_precision category (17 warnings → 0)
- **WARN-002:** Fix Hypothesis decimal precision warnings (COMPLETED in SESSION 4.3)

**Session Documentation:**
- **SESSION_HANDOFF.md (2025-11-23):** SESSION 4.3 - Hypothesis Decimal Precision Fix
- **Commit bc4ffca:** "fix: SESSION 4 Warning Debt Reduction (ResourceWarning + Hypothesis Decimal)"

**Test Files Using This Pattern:**
- `tests/property/test_kelly_criterion_properties.py` (8 edits)
- `tests/property/test_edge_detection_properties.py` (5 edits)
- `tests/property/test_config_validation_properties.py` (2 edits)

---

## Pattern 20: Resource Management - Explicit File Handle Cleanup (ALWAYS)

**ALWAYS explicitly close file handlers before removing them to prevent ResourceWarnings.**

### Core Principle

`logging.basicConfig(force=True)` clears handlers from the logging system but **does NOT close underlying file handles**. This causes ResourceWarnings in tests when `setup_logging()` is called multiple times. Always explicitly call `handler.close()` before `removeHandler()` to prevent resource leaks.

**Key Technique:** Use list slice `handlers[:]` when iterating over a list you're modifying to avoid iteration issues.

---

### ✅ CORRECT: Explicit Handler Cleanup

```python
import logging
import sys
from pathlib import Path

def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    service_name: str = "precog"
) -> None:
    """
    Configure logging with structlog.

    Explicitly closes existing FileHandler objects before creating new ones
    to prevent ResourceWarnings when setup_logging() is called multiple times
    (e.g., in test suites).

    Educational Note:
        logging.basicConfig(force=True) clears handlers but doesn't close file handles.
        This can cause ResourceWarnings: "unclosed file <_io.TextIOWrapper ...>".

        We use handlers[:] (list slice) to create a copy of the handlers list
        before iteration, since we're modifying the list during iteration
        (removing handlers). Iterating over the original list while modifying
        it can cause skipped items or IndexErrors.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path (None = console only)
        service_name: Service name for log context

    Example:
        >>> setup_logging(log_level="DEBUG", log_file="precog_2025-11-23.log")
        >>> logger = structlog.get_logger()
        >>> logger.info("Application started", version="1.5")

    References:
        - Pattern 20 (Resource Management): Explicit file handle cleanup
        - SESSION_HANDOFF.md (2025-11-23): SESSION 4.2 ResourceWarning fix
        - warning_baseline.json: resource_warning_unclosed_files count 11→0
    """
    # ✅ STEP 1: Explicitly close existing FileHandler objects
    # BEFORE creating new ones (prevents ResourceWarnings)
    root_logger = logging.getLogger()

    # ✅ Use [:] slice to create copy - safe to modify during iteration
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()  # ← CRITICAL: Explicitly close file handle
            root_logger.removeHandler(handler)

    # ✅ STEP 2: Configure standard library logging
    # force=True clears remaining handlers (but doesn't close them)
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            # Console handler (always enabled)
            logging.StreamHandler(sys.stdout),
            # File handler (if enabled)
            *([logging.FileHandler(log_file, mode="a", encoding="utf-8")] if log_file else []),
        ],
        force=True,  # Clear old handlers before adding new ones
    )

    # ... rest of structlog configuration ...
```

**Why this works:**
- ✅ `handler.close()` explicitly closes file handle before removal
- ✅ `handlers[:]` creates copy, safe to modify during iteration
- ✅ Only closes `FileHandler` objects (not console handlers)
- ✅ No ResourceWarnings when `setup_logging()` called multiple times

---

### ❌ WRONG: Relying on force=True to Close Handlers

```python
import logging
import sys

def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """Configure logging (WRONG - doesn't close file handles)."""

    # ❌ WRONG - force=True removes handlers but doesn't close file handles
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            *([logging.FileHandler(log_file, mode="a", encoding="utf-8")] if log_file else []),
        ],
        force=True,  # ← Removes handlers but DOESN'T close file handles!
    )
```

**Problems:**
- ❌ File handles not closed (ResourceWarning: unclosed file)
- ❌ File descriptors leaked when setup_logging() called multiple times
- ❌ Test suites generate 11+ ResourceWarnings
- ❌ Operating system file descriptor limits can be exhausted

---

### Real-World Impact (Phase 1.5 SESSION 4.2)

**Before Fix:**
```python
# src/precog/utils/logger.py (lines 193-213 - BEFORE)
def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            *([logging.FileHandler(log_file, mode="a", encoding="utf-8")] if log_file else []),
        ],
        force=True,  # ← Clears handlers but doesn't close file handles
    )
```

**Warning Output (tests/test_logger.py):**
```
ResourceWarning: unclosed file <_io.TextIOWrapper name='C:\\Users\\...\\precog_2025-11-08.log' mode='a' encoding='utf-8'>
  Object allocated at (most recent call last):
    File "tests/test_logger.py", line 45, in test_log_to_file
      setup_logging(log_level="INFO", log_file=log_file)
    File "src/precog/utils/logger.py", line 202, in setup_logging
      logging.FileHandler(log_file, mode="a", encoding="utf-8")
```

**Impact:** 11 ResourceWarnings across 17 logger tests.

**After Fix:**
```python
# src/precog/utils/logger.py (lines 193-213 - AFTER)
def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    # ✅ Explicitly close existing FileHandler objects to prevent ResourceWarnings
    # when setup_logging() is called multiple times (e.g., in tests)
    root_logger = logging.getLogger()

    for handler in root_logger.handlers[:]:  # [:] creates a copy to safely modify during iteration
        if isinstance(handler, logging.FileHandler):
            handler.close()  # ← CRITICAL: Close file handle
            root_logger.removeHandler(handler)

    # force=True: Clear remaining handlers before adding new ones
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            *([logging.FileHandler(log_file, mode="a", encoding="utf-8")] if log_file else []),
        ],
        force=True,
    )
```

**Result:**
- ✅ 0 ResourceWarnings (down from 11)
- ✅ All 17 logger tests passing without warnings
- ✅ Warning baseline reduced (79 → 83 net, but ResourceWarning portion eliminated)

**Session 4.2 Statistics:**
- **Files modified:** 1 (src/precog/utils/logger.py)
- **Code edits:** 1 (added 6-line handler cleanup loop)
- **Warnings eliminated:** 11
- **Time:** 45 minutes

---

### When to Use This Pattern

**ALWAYS use explicit cleanup when:**
- ✅ Function creates file-based handlers (FileHandler, RotatingFileHandler, TimedRotatingFileHandler)
- ✅ Function called multiple times in same process (tests, hot-reload, dynamic reconfiguration)
- ✅ Handler list is modified during iteration (remove, clear, replace)
- ✅ Resource leak would accumulate (file descriptors, database connections, network sockets)

**Example Scenarios:**
1. **Test fixtures:** setup_logging() called before each test (17 tests = 17 file handles)
2. **Configuration reload:** User changes log level → reconfig triggers → new handlers created
3. **Service restart:** Graceful shutdown → cleanup old handlers → start with new config
4. **Multi-environment:** Switch from DEV → TEST → PROD environments dynamically

---

### Common Mistakes

#### Mistake 1: Iterating over list while modifying it

**❌ WRONG:**
```python
root_logger = logging.getLogger()

# ❌ WRONG - Modifying list during iteration can skip items
for handler in root_logger.handlers:  # ← Direct iteration (no [:] slice)
    if isinstance(handler, logging.FileHandler):
        handler.close()
        root_logger.removeHandler(handler)  # ← Modifies list being iterated!
```

**Problem:** Removing items during iteration can cause Python to skip items or raise IndexError.

**✅ CORRECT:**
```python
root_logger = logging.getLogger()

# ✅ CORRECT - Create copy with [:] slice before iteration
for handler in root_logger.handlers[:]:  # ← Slice creates copy
    if isinstance(handler, logging.FileHandler):
        handler.close()
        root_logger.removeHandler(handler)  # ← Modifies original list, not copy
```

#### Mistake 2: Closing non-file handlers

**❌ WRONG:**
```python
root_logger = logging.getLogger()

# ❌ WRONG - Closes ALL handlers (including console)
for handler in root_logger.handlers[:]:
    handler.close()  # ← Closes StreamHandler too!
    root_logger.removeHandler(handler)
```

**Problem:** Console logging stops working (StreamHandler closed).

**✅ CORRECT:**
```python
root_logger = logging.getLogger()

# ✅ CORRECT - Only close file-based handlers
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):  # ← Check type first
        handler.close()
        root_logger.removeHandler(handler)
```

#### Mistake 3: Forgetting to remove handler after closing

**❌ WRONG:**
```python
root_logger = logging.getLogger()

# ❌ WRONG - Close but don't remove (handler stays in list)
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        handler.close()  # ← Closed but not removed!
        # Missing: root_logger.removeHandler(handler)
```

**Problem:** Closed handler still in list, force=True tries to use it → errors.

**✅ CORRECT:**
```python
root_logger = logging.getLogger()

# ✅ CORRECT - Close AND remove
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        handler.close()                    # ← Close file handle
        root_logger.removeHandler(handler) # ← Remove from list
```

---

### Testing This Pattern

**Verify no ResourceWarnings:**
```bash
# Run logger tests with warnings enabled
python -m pytest tests/test_logger.py -v -W default::ResourceWarning --tb=short

# Expected: 17 passed, 0 ResourceWarnings
```

**Verify handlers cleaned up:**
```python
import logging
from precog.utils.logger import setup_logging

def test_handlers_cleaned_up():
    """Verify old handlers removed before new ones added."""
    setup_logging(log_level="INFO", log_file="test1.log")
    assert len(logging.getLogger().handlers) == 2  # Console + File

    setup_logging(log_level="DEBUG", log_file="test2.log")
    assert len(logging.getLogger().handlers) == 2  # Still 2 (old file handler removed)

    # Verify only one FileHandler (new one, old one closed and removed)
    file_handlers = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
    assert file_handlers[0].baseFilename.endswith("test2.log")
```

---

### Cross-References

**Related Patterns:**
- **Pattern 9:** Multi-Source Warning Governance (MANDATORY) - How this pattern reduces warning debt
- **Pattern 12:** Test Fixture Security Compliance (MANDATORY) - Proper resource cleanup in test fixtures

**Warning Governance:**
- **scripts/warning_baseline.json:** resource_warning_unclosed_files category (11 warnings → 0)
- **WARN-001:** Fix ResourceWarning: unclosed file handles in logger tests (COMPLETED in SESSION 4.2)

**Session Documentation:**
- **SESSION_HANDOFF.md (2025-11-23):** SESSION 4.2 - ResourceWarning Fix
- **Commit bc4ffca:** "fix: SESSION 4 Warning Debt Reduction (ResourceWarning + Hypothesis Decimal)"

**Implementation:**
- **src/precog/utils/logger.py (lines 193-213):** Handler cleanup implementation
- **tests/test_logger.py:** 17 tests verifying no ResourceWarnings

**Python Documentation:**
- **logging.Handler.close():** https://docs.python.org/3/library/logging.html#logging.Handler.close
- **logging.basicConfig():** https://docs.python.org/3/library/logging.html#logging.basicConfig
- **ResourceWarning:** https://docs.python.org/3/library/exceptions.html#ResourceWarning

---

## Pattern 21: Validation-First Architecture - 4-Layer Defense in Depth (CRITICAL)

**TL;DR:** ALWAYS use multi-layer validation (pre-commit → pre-push → CI/CD → branch protection) to catch errors early and reduce CI failures by 80-90%.

### Why This Pattern Exists

**Problem Addressed:**
- CI failures waste time (2-5 minutes per failure)
- Late error detection (after git push)
- Inconsistent code quality across commits
- Manual validation steps forgotten

**Real-World Context:**
- **Pre-commit hooks (Phase 0.7):** Reduced CI failures by 60-70% (~2-5 seconds local feedback)
- **Pre-push hooks (Phase 0.7):** Reduced CI failures by 80-90% (~30-60 seconds comprehensive validation)
- **Branch protection (Phase 0.7):** Enforces PR workflow, prevents direct pushes to main
- **CI/CD (Phase 0.6c):** Multi-platform validation (Linux, Windows, macOS)

**Defense in Depth Philosophy:**
Each layer catches different types of errors:
- **Layer 1 (Pre-commit):** Fast syntactic checks (formatting, linting, security)
- **Layer 2 (Pre-push):** Semantic validation (tests, type checking, coverage)
- **Layer 3 (CI/CD):** Cross-platform compatibility, integration tests, deployment checks
- **Layer 4 (Branch protection):** Policy enforcement (PR required, status checks must pass)

### The Pattern

#### Layer 1: Pre-Commit Hooks (2-5 seconds)

**Installation:**
```bash
# Install pre-commit framework
pip install pre-commit

# Install git hooks
pre-commit install

# Test hooks on all files
pre-commit run --all-files
```

**Configuration:** `.pre-commit-config.yaml` (14 hooks)

```yaml
repos:
  # Layer 1.1: Auto-fix (run first, modify files)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace      # Auto-fix: Remove trailing whitespace
      - id: end-of-file-fixer        # Auto-fix: Ensure newline at EOF
      - id: mixed-line-ending        # Auto-fix: CRLF → LF (Windows compatibility)
        args: ['--fix=lf']

  # Layer 1.2: Security (check-only, BLOCK commits)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: detect-private-key       # BLOCK: Hardcoded private keys
      - id: check-added-large-files  # BLOCK: Files >500KB
      - id: check-merge-conflict     # BLOCK: Merge conflict markers

  # Layer 1.3: Code quality (check-only, BLOCK commits)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.3
    hooks:
      - id: ruff                      # BLOCK: Linting errors (Ruff check)
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format               # BLOCK: Formatting errors (Ruff format)

  # Layer 1.4: Type checking (check-only, BLOCK commits)
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy                      # BLOCK: Type errors (critical modules only)
        files: ^(src/precog/api_connectors|src/precog/trading|src/precog/analytics)/.*\.py$

  # Layer 1.5: Pattern enforcement (custom hooks)
  - repo: local
    hooks:
      - id: decimal-precision-check
        name: Pattern 1: Decimal Precision (no float for prices)
        entry: python scripts/validate_decimal_precision.py
        language: python
        types: [python]
        pass_filenames: false

      - id: code-review-basics
        name: Code Review Basics (coverage ≥80%, REQ test coverage)
        entry: python scripts/validate_code_quality.py
        language: python
        types: [python]
        pass_filenames: false
```

**Auto-Fix vs Check-Only:**

| Hook | Behavior | Example |
|------|----------|---------|
| `trailing-whitespace` | Auto-fix | Removes trailing spaces, re-stages file |
| `ruff-format` | Check-only | Reports formatting issues, blocks commit |
| `mypy` | Check-only | Reports type errors, blocks commit |

**Performance:** ~2-5 seconds total
- Auto-fix hooks: <1 second (modify files)
- Check-only hooks: 1-4 seconds (report errors)

---

#### Layer 2: Pre-Push Hooks (30-60 seconds)

**Installation:** `.git/hooks/pre-push` (bash script)

```bash
#!/bin/bash
# Pre-push hook - Comprehensive validation before pushing to remote
# Created: 2025-11-07 (Phase 0.7, DEF-002)
# Runs: Automatically on `git push`
# Bypass: `git push --no-verify` (NOT recommended)

set -e  # Exit on first error

echo "Running pre-push validation..."

# Step 1/7: Quick validation (code quality + docs)
echo "[1/7] Quick validation..."
./scripts/validate_quick.sh

# Step 2/7: Unit tests only (fast feedback)
echo "[2/7] Unit tests..."
python -m pytest tests/unit/ -v --tb=short

# Step 3/7: Full type checking (entire codebase)
echo "[3/7] Type checking..."
python -m mypy src/precog/ --pretty

# Step 4/7: Security scan (hardcoded credentials)
echo "[4/7] Security scan..."
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py' '*.yaml' && exit 1 || true

# Step 5/7: Warning governance (zero regression policy)
echo "[5/7] Warning governance..."
python scripts/check_warning_debt.py

# Step 6/7: Code quality template enforcement (≥80% coverage, REQ tests)
echo "[6/7] Code quality enforcement..."
python scripts/validate_code_quality.py

# Step 7/7: Security pattern enforcement (API auth, secrets)
echo "[7/7] Security pattern enforcement..."
python scripts/validate_security_patterns.py

echo "✅ All pre-push checks passed!"
```

**Key Differences from Pre-Commit:**
- **Tests run for first time** (pre-commit has no tests)
- **Full codebase type checking** (pre-commit only checks modified files)
- **Comprehensive security scan** (pre-commit only checks for private keys)
- **Warning governance** (enforces zero regression policy)

**Performance:** ~30-60 seconds total
- Quick validation: ~3 seconds
- Unit tests: ~5-10 seconds
- Type checking: ~5-10 seconds
- Security scan: ~1 second
- Warning governance: ~2-5 seconds
- Code quality: ~5-10 seconds
- Security patterns: ~5-10 seconds

**Impact:** Reduces CI failures by 80-90% (catches test failures locally)

---

#### Layer 3: CI/CD (2-5 minutes)

**Configuration:** `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.12']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Ruff linting
        run: python -m ruff check .

      - name: Run Ruff formatting
        run: python -m ruff format --check .

      - name: Run type checking
        run: python -m mypy src/precog/

      - name: Run tests with coverage
        run: python -m pytest tests/ --cov=src/precog --cov-report=xml --cov-report=term-missing

      - name: Check coverage threshold
        run: python -m pytest tests/ --cov=src/precog --cov-fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

**Required Status Checks:**
1. ✅ `test (ubuntu-latest, 3.12)` - Linux tests
2. ✅ `test (windows-latest, 3.12)` - Windows tests
3. ✅ `test (macos-latest, 3.12)` - macOS tests
4. ✅ `Ruff linting` - Code quality
5. ✅ `Ruff formatting` - Code formatting
6. ✅ `Mypy type checking` - Type safety

**Performance:** ~2-5 minutes total (parallel across 3 platforms)

**Cross-Platform Validation:**
- **Ubuntu:** Primary platform (Linux compatibility)
- **Windows:** Cross-platform validation (path separators, line endings)
- **macOS:** Developer platform (local development compatibility)

---

#### Layer 4: Branch Protection (GitHub Enforcement)

**Configuration:** GitHub repository settings → Branches → Branch protection rules

```yaml
# Applied to: main branch
# Enforcement: MANDATORY (blocks direct pushes)

Rules:
  - Require pull request before merging: ✅ Enabled
  - Require approvals: 0 (can be increased for team collaboration)
  - Require status checks to pass before merging: ✅ Enabled
    Required status checks (6 checks):
      - test (ubuntu-latest, 3.12)
      - test (windows-latest, 3.12)
      - test (macos-latest, 3.12)
      - Ruff linting
      - Ruff formatting
      - Mypy type checking
  - Require branches to be up to date before merging: ✅ Enabled
  - Require conversation resolution before merging: ✅ Enabled
  - Do not allow bypassing the above settings: ✅ Enabled (applies to administrators)
  - Restrict pushes: ❌ Disabled (no specific users/teams)
  - Allow force pushes: ❌ Disabled
  - Allow deletions: ❌ Disabled
```

**Enforcement Workflow:**
1. Developer creates feature branch
2. Developer commits (pre-commit hooks run)
3. Developer pushes (pre-push hooks run)
4. Developer creates PR
5. CI/CD runs (6 status checks)
6. All checks must pass before merge
7. Branch must be up-to-date with main before merge

**Impact:** Prevents "worked alone, broken together" bugs

---

### Validation Script Architecture (YAML-Driven, Auto-Discovery)

**Pattern:** Zero-configuration validation with auto-discovery

#### Example: validate_code_quality.py (314 lines)

```python
"""
Code Quality Validation (CODE_REVIEW_TEMPLATE enforcement)

Auto-discovers Python modules and validates:
1. Module coverage ≥80% (tier-specific targets)
2. REQ-XXX-NNN test coverage (traceability)
3. Educational docstrings (Pattern 7 compliance)

YAML-driven configuration (validation_config.yaml):
- Tier definitions (Critical Path ≥90%, Business Logic ≥85%, Infrastructure ≥80%)
- Module classification (automatic tier assignment)
- Coverage targets (auto-loaded from YAML)
"""

import yaml
from pathlib import Path
from typing import Dict, List

# Load validation configuration (YAML-driven)
def load_validation_config() -> Dict:
    config_path = Path("config/validation_config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)

# Auto-discover modules (zero configuration)
def discover_modules() -> List[Path]:
    src_dir = Path("src/precog")
    return list(src_dir.rglob("*.py"))

# Validate module coverage (tier-specific targets)
def validate_module_coverage(module: Path, config: Dict) -> bool:
    tier = get_module_tier(module, config)  # Automatic tier assignment
    target = config['tiers'][tier]['coverage_target']  # Auto-loaded target

    actual_coverage = get_coverage(module)  # Coverage.py integration

    if actual_coverage < target:
        print(f"❌ {module}: {actual_coverage}% (target: {target}%)")
        return False

    print(f"✅ {module}: {actual_coverage}% (target: {target}%)")
    return True

# Run validation (called by pre-commit/pre-push hooks)
def main():
    config = load_validation_config()
    modules = discover_modules()

    results = [validate_module_coverage(m, config) for m in modules]

    if not all(results):
        sys.exit(1)  # Block commit/push if validation fails
```

**Configuration:** `config/validation_config.yaml`

```yaml
tiers:
  critical_path:
    coverage_target: 90
    modules:
      - src/precog/api_connectors/kalshi_client.py
      - src/precog/api_connectors/kalshi_auth.py

  business_logic:
    coverage_target: 85
    modules:
      - src/precog/trading/strategy_manager.py
      - src/precog/analytics/model_manager.py
      - src/precog/trading/position_manager.py

  infrastructure:
    coverage_target: 80
    modules:
      - src/precog/config/config_loader.py
      - src/precog/database/connection.py
      - src/precog/utils/logger.py
```

**Auto-Discovery Benefits:**
- No manual module registration
- New modules automatically validated
- Configuration in one place (YAML)
- Easy to update targets
- Self-documenting (YAML shows all tiers)

---

### Real-World Impact

**Before 4-Layer Validation:**
- CI failure rate: 40-50%
- Average time to fix: 10-15 minutes
- Wasted CI minutes: 2-5 minutes per failure

**After 4-Layer Validation:**
- CI failure rate: 5-10%
- Average time to fix: 2-3 minutes (caught locally)
- Wasted CI minutes: <1 minute per failure

**Time Savings:**
- Pre-commit catches: 60-70% of errors (~2-5 seconds local feedback vs 2-5 minutes CI)
- Pre-push catches: 80-90% of errors (~30-60 seconds local feedback vs 2-5 minutes CI)
- Branch protection: 100% enforcement (no "forgot to run tests" pushes)

**Developer Experience:**
- Fast feedback (2-5 seconds for most errors)
- Comprehensive validation (30-60 seconds before push)
- Confidence (CI will pass if pre-push passes)
- Clear error messages (local validation more detailed than CI)

---

### Common Mistakes

❌ **WRONG - Skip validation with --no-verify:**
```bash
git commit --no-verify   # ❌ Bypasses pre-commit hooks
git push --no-verify     # ❌ Bypasses pre-push hooks
```
**Why Wrong:** Defeats the purpose of validation. Errors will fail in CI instead.

✅ **CORRECT - Fix errors locally:**
```bash
# Pre-commit hook reports formatting error
python -m ruff format .   # Fix formatting
git add .                 # Re-stage files
git commit                # Commit again (hooks pass)
```

---

❌ **WRONG - Disable hooks permanently:**
```bash
# ❌ NEVER do this
rm .git/hooks/pre-commit
rm .git/hooks/pre-push
```
**Why Wrong:** Removes all validation. CI will fail frequently.

✅ **CORRECT - Update hooks when config changes:**
```bash
# When .pre-commit-config.yaml changes
pre-commit install --overwrite --install-hooks
```

---

❌ **WRONG - Run validation manually (inconsistent):**
```bash
# ❌ Developers forget to run these
python -m pytest tests/ -v
python -m mypy .
python -m ruff check .
```
**Why Wrong:** Manual steps get forgotten. Automation is more reliable.

✅ **CORRECT - Let hooks run automatically:**
```bash
# ✅ Hooks run automatically on commit/push
git commit -m "Add feature"   # Pre-commit hooks run
git push origin feature       # Pre-push hooks run
```

---

### When to Bypass (Rare Exceptions)

**Acceptable bypass scenarios:**
1. **Fixing broken hooks** (use `--no-verify` once to commit hook fix)
2. **Emergency hotfix** (bypass pre-push, but CI must still pass)
3. **Pre-existing violations** (when issues already tracked in GitHub)

**Bypass with rationale:**
```bash
# Emergency hotfix (document why)
git commit -m "hotfix: Fix critical bug" --no-verify

# Document in commit message why bypass was needed
git commit -m "fix: Update pre-commit config

Bypass pre-commit hooks because we're fixing the hooks themselves.
Without bypass, the broken hooks would block this commit.

Closes #104"
```

---

### Related Patterns

- **Pattern 1 (Decimal Precision):** Enforced by pre-commit hook (decimal-precision-check)
- **Pattern 4 (Security):** Enforced by pre-commit hook (detect-private-key) and pre-push (security scan)
- **Pattern 9 (Warning Governance):** Enforced by pre-push hook (check_warning_debt.py)
- **Pattern 18 (Avoid Technical Debt):** Tracked via GitHub issues, enforced by pre-push (validation scripts)

---

### Cross-References

**Implementation (DEF Tasks):**
- **DEF-001:** Pre-commit hooks setup (PHASE_0.7_DEFERRED_TASKS_V1.0.md)
- **DEF-002:** Pre-push hooks setup (PHASE_0.7_DEFERRED_TASKS_V1.0.md)
- **DEF-003:** Branch protection rules (PHASE_0.7_DEFERRED_TASKS_V1.0.md)

**Validation Scripts:**
- `scripts/validate_code_quality.py` (314 lines, CODE_REVIEW_TEMPLATE enforcement)
- `scripts/validate_security_patterns.py` (413 lines, SECURITY_REVIEW_CHECKLIST enforcement)
- `scripts/check_warning_debt.py` (multi-source warning governance)

**Configuration Files:**
- `.pre-commit-config.yaml` (14 hooks, auto-fix + check-only)
- `.git/hooks/pre-push` (7 validation steps, comprehensive)
- `.github/workflows/ci.yml` (6 required status checks)
- `config/validation_config.yaml` (tier definitions, coverage targets)

**Documentation:**
- `docs/utility/CODE_REVIEW_TEMPLATE_V1.0.md` (7-category checklist)
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md` (V1.1, 4 new sections)
- `CLAUDE.md` (Section 3: Pre-Commit Protocol, Branch Protection & Pull Request Workflow)

---

## Pattern 22: VCR Pattern for Real API Responses (ALWAYS for External APIs) - CRITICAL

**TL;DR:** ALWAYS use VCR (Video Cassette Recorder) pattern to record REAL API responses and replay them in integration tests. Mocked API responses can pass tests yet miss critical bugs in response parsing, field mapping, and data transformations.

**WHY:** API integration tests with mocked responses can pass yet miss critical bugs in response parsing, field mapping, and data transformations. The VCR (Video Cassette Recorder) pattern records REAL API responses once, then replays them in tests—combining the speed/determinism of mocks with the accuracy of real data.

**The Critical Lesson:** "Mocked API response" ≠ "Real API response structure"

### Real-World Example: Kalshi Dual-Format Pricing (GitHub #124)

**The Bug:**
Kalshi API provides dual format for backward compatibility:
- **Legacy integer cents:** `yes_bid: 62` (2 decimals, cents)
- **Sub-penny string:** `yes_bid_dollars: "0.6200"` (4 decimals, string)

**The Discovery:**
1. **Mocked tests used integer format:** Tests created mock responses with `yes_bid: 62` and passed ✅
2. **Real API returned string format:** Actual Kalshi API returned `yes_bid_dollars: "0.6200"` (sub-penny precision)
3. **Bug discovered only with VCR:** When VCR cassettes recorded actual API responses, tests revealed client was parsing wrong field
4. **Impact:** Without VCR, production code would have used 2-decimal pricing instead of 4-decimal sub-penny pricing → precision loss in trading decisions

**Files Affected:**
- `tests/integration/api_connectors/test_kalshi_client_vcr.py` - VCR tests catching dual-format bug
- `src/precog/api_connectors/kalshi_client.py` - Updated to parse `*_dollars` fields instead of integer cents
- `tests/cassettes/kalshi_*.yaml` - 5 cassettes with REAL API responses

**Result:** VCR pattern caught bug that mocks missed. Tests with real API data revealed actual response structure.

---

### What is VCR?

**VCR (Video Cassette Recorder)** is a testing pattern that:
1. **Records** real HTTP interactions from live API once
2. **Saves** them to "cassette" files (YAML format)
3. **Replays** cassettes in tests (no network calls)
4. **Filters** sensitive headers (API keys, signatures, timestamps)

**Benefits:**
- ✅ **100% real API data** - Uses actual response structures from production API
- ✅ **Fast** - No network calls (cassettes replay in ~1ms)
- ✅ **Deterministic** - Same responses every time, no flaky tests
- ✅ **CI-friendly** - No API credentials needed in CI/CD
- ✅ **Version control** - Cassettes committed to git, reviewable in PRs

**Python Library:** `vcrpy` (install: `pip install vcrpy`)

---

### VCR Configuration

**File:** `tests/integration/api_connectors/test_kalshi_client_vcr.py`

```python
import vcr

# Configure VCR for test cassettes
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",           # Where to save cassettes
    record_mode="none",                                # Never record in tests (only replay)
    match_on=["method", "scheme", "host", "port", "path", "query"],  # Match requests by URL components
    filter_headers=[                                   # Remove sensitive headers before saving
        "KALSHI-ACCESS-KEY",
        "KALSHI-ACCESS-SIGNATURE",
        "KALSHI-ACCESS-TIMESTAMP"
    ],
    decode_compressed_response=True,                   # Auto-decode gzip/deflate responses
)
```

**Configuration Options:**

| Option | Value | Why |
|--------|-------|-----|
| `cassette_library_dir` | `"tests/cassettes"` | Centralized cassette storage |
| `record_mode` | `"none"` | **Tests only replay** (never record, prevents accidental overwrites) |
| `match_on` | `["method", "scheme", "host", "port", "path", "query"]` | Match requests by full URL (prevents mismatches) |
| `filter_headers` | `["KALSHI-ACCESS-KEY", ...]` | **CRITICAL:** Remove credentials before committing cassettes |
| `decode_compressed_response` | `True` | Auto-decode gzip responses (Kalshi uses gzip) |

**⚠️ CRITICAL:** `filter_headers` prevents API credentials from being committed to git. Always filter authentication headers (API keys, signatures, tokens).

---

### VCR Test Example

**File:** `tests/integration/api_connectors/test_kalshi_client_vcr.py`

```python
@pytest.mark.integration
@pytest.mark.api
def test_get_markets_with_real_api_data(monkeypatch):
    """
    Test get_markets() with REAL recorded Kalshi market data.

    Uses cassette: kalshi_get_markets.yaml
    - 5 real NFL markets from KXNFLGAME series
    - Real prices with sub-penny precision (0.0000 format)
    - Real market titles, tickers, volumes
    """
    # Set environment variables for client initialization
    monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")  # Dummy value (not used with cassette)
    monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

    # Use VCR cassette (replays recorded HTTP interaction)
    with my_vcr.use_cassette("kalshi_get_markets.yaml"):
        client = KalshiClient(environment="demo")
        markets = client.get_markets(series_ticker="KXNFLGAME", limit=5)

    # Verify real data structure
    assert len(markets) == 5, "Should return 5 markets from cassette"

    # Verify first market structure (real data from actual API)
    market = markets[0]
    assert "ticker" in market
    assert "title" in market
    assert market["ticker"].startswith("KXNFLGAME-"), "Real Kalshi market ticker format"

    # Verify ALL price fields are Decimal (CRITICAL! Pattern 1)
    price_fields = ["yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars"]
    for field in price_fields:
        if field in market:
            assert isinstance(market[field], Decimal), (
                f"Field '{field}' must be Decimal, got {type(market[field])}"
            )

    # Verify specific market from recording (proves real data)
    assert any(m["ticker"] == "KXNFLGAME-25NOV27GBDET-GB" for m in markets), (
        "Should include GB @ DET market from cassette"
    )
```

**Key Points:**
1. **Dummy credentials OK:** `test-key-id` works because cassette replays HTTP response (no real API call)
2. **Real data verification:** Assert on actual market tickers from cassette (proves real data)
3. **Pattern 1 integration:** Verify Decimal precision with real API response (catches parsing bugs)
4. **Fast execution:** ~1ms (no network call)

---

### Cassette Structure (YAML)

**File:** `tests/cassettes/kalshi_get_markets.yaml`

```yaml
interactions:
- request:
    body: null
    headers:
      Accept:
      - '*/*'
      Content-Type:
      - application/json
      # NOTE: Sensitive headers filtered (KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP)
    method: GET
    uri: https://demo-api.kalshi.co/trade-api/v2/markets?limit=5&series_ticker=KXNFLGAME
  response:
    body:
      string: '{"cursor":"...","markets":[{"ticker":"KXNFLGAME-25NOV27GBDET-GB","title":"Green Bay at Detroit Winner?","yes_bid_dollars":"0.0000","yes_ask_dollars":"1.0000",...}]}'
    headers:
      Content-Type:
      - application/json
      Date:
      - Sun, 23 Nov 2025 16:56:51 GMT
    status:
      code: 200
      message: OK
version: 1
```

**Cassette Contents:**
- **Request:** HTTP method, URL, headers (credentials filtered), body
- **Response:** Status code, headers, body (full JSON response from real API)
- **Version:** VCR format version (for compatibility)

**Commit to Git:** ✅ YES - Cassettes are committed to version control (no credentials due to `filter_headers`)

---

### VCR vs. Mocks vs. Real Fixtures: Decision Tree

**When to use VCR:**

1. ✅ **Testing external API client?** → Use VCR
   - **Examples:** Kalshi API, ESPN API, Balldontlie API
   - **Why:** Ensures response parsing works with REAL data structures
   - **Benefit:** Catches bugs like Kalshi dual-format pricing

2. ✅ **Testing integration with third-party service?** → Use VCR
   - **Examples:** Payment APIs (Stripe), Weather APIs, Sports data APIs
   - **Why:** Third-party APIs change response formats without notice
   - **Benefit:** Cassettes document expected API contract

3. ✅ **Testing API error handling with REAL error responses?** → Use VCR
   - **Examples:** 429 rate limit, 500 server error, 401 unauthorized
   - **Why:** Real error responses may have different structure than docs
   - **Benefit:** Record actual error response, test parsing

**When to use Real Fixtures (Pattern 13):**

4. ✅ **Testing internal logic/business rules?** → Use real fixtures
   - **Examples:** Database CRUD operations, trading logic, position management
   - **Why:** Full control over test data, no network dependency
   - **Benefit:** Faster setup, easier debugging

**When to use Mocks:**

5. ✅ **Testing error handling for scenarios that can't be recorded?** → Use mocks
   - **Examples:** Network failures (`requests.ConnectionError`), timeouts
   - **Why:** Can't record network failures (no HTTP response exists)
   - **Benefit:** Can simulate any error condition

**Decision Matrix:**

| Scenario | Solution | Rationale |
|----------|----------|-----------|
| Kalshi `get_markets()` | VCR cassette ✅ | External API, need real response structure |
| Database `insert_market()` | Real fixtures (Pattern 13) ✅ | Internal logic, need control over test data |
| API network timeout | Mock `requests.Timeout` ✅ | Can't record network failure (no HTTP response) |
| API 429 rate limit | VCR cassette ✅ | Can record real 429 response from API |
| Trading strategy backtest | Real fixtures (Pattern 13) ✅ | Need historical data with known outcomes |
| ESPN API `get_scores()` | VCR cassette ✅ | External API, response format may change |

**Key Principle:** For external APIs you don't control → Use VCR. For internal logic you control → Use real fixtures (Pattern 13).

---

### Common Mistakes

#### ❌ Mistake 1: Not Filtering Sensitive Headers

**Problem:** API credentials committed to git in cassettes

**Wrong:**
```python
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="none",
    # Missing filter_headers! ❌
)
```

**Cassette contains:**
```yaml
headers:
  KALSHI-ACCESS-KEY: 75b4b76e-d191-4855-b219-5c31cdcba1c8  # ❌ LEAKED!
  KALSHI-ACCESS-SIGNATURE: <RSA-PSS signature>             # ❌ LEAKED!
```

**Correct:**
```python
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="none",
    filter_headers=["KALSHI-ACCESS-KEY", "KALSHI-ACCESS-SIGNATURE", "KALSHI-ACCESS-TIMESTAMP"],  # ✅
)
```

**Cassette contains:**
```yaml
headers:
  # Sensitive headers filtered by VCR ✅
  Content-Type: application/json
```

**Why Critical:** Committing API credentials to git = security breach. Always use `filter_headers`.

---

#### ❌ Mistake 2: Using `record_mode="all"` in Tests

**Problem:** Tests accidentally overwrite cassettes on every run

**Wrong:**
```python
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="all",  # ❌ DANGER: Overwrites cassettes every test run!
)
```

**Impact:**
- Every test run makes real API calls (slow, requires credentials)
- Cassettes change randomly based on current API state
- Git diffs show cassette changes unrelated to code changes
- CI/CD fails if API is down or rate-limited

**Correct:**
```python
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="none",  # ✅ Tests ONLY replay (never record)
)
```

**When to use `record_mode="all"`:**
- **Only when initially recording cassettes** (separate script, not in tests)
- **Only when re-recording after API changes** (documented process below)

---

#### ❌ Mistake 3: One Cassette for All Tests

**Problem:** Overwriting cassettes, hard to debug test failures

**Wrong:**
```python
def test_get_markets(monkeypatch):
    with my_vcr.use_cassette("kalshi_api.yaml"):  # ❌ Generic name
        markets = client.get_markets()

def test_get_balance(monkeypatch):
    with my_vcr.use_cassette("kalshi_api.yaml"):  # ❌ Same cassette reused
        balance = client.get_balance()
```

**Impact:**
- Second test overwrites first cassette when recording
- Can't tell which test failed by cassette name
- Git diffs show mixed changes from multiple tests

**Correct:**
```python
def test_get_markets(monkeypatch):
    with my_vcr.use_cassette("kalshi_get_markets.yaml"):  # ✅ Specific name
        markets = client.get_markets()

def test_get_balance(monkeypatch):
    with my_vcr.use_cassette("kalshi_get_balance.yaml"):  # ✅ Different cassette
        balance = client.get_balance()
```

**Naming Convention:** `<api>_<method>_<scenario>.yaml`
- `kalshi_get_markets.yaml` - Normal case
- `kalshi_get_markets_rate_limited.yaml` - 429 error case
- `kalshi_get_markets_empty.yaml` - Edge case (no results)

---

### Re-Recording Cassettes Workflow

**When to re-record:**
1. API response format changes (new fields, field renames)
2. Need to test new API endpoint
3. Need to update test data (newer markets, different prices)
4. API version upgrade (v1 → v2)

**5-Step Re-Recording Process:**

**Step 1: Create recording script** (separate from tests)

```python
# scripts/record_kalshi_cassettes.py
"""
Record VCR cassettes for Kalshi API integration tests.

ONLY run this script when:
1. Adding new API endpoints to test
2. API response format changes
3. Updating test data

DO NOT run this in tests (use record_mode="none" in tests).
"""
import vcr
from precog.api_connectors.kalshi_client import KalshiClient

# Configure VCR for RECORDING (not replaying)
recording_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="all",  # ✅ OK for recording script
    filter_headers=["KALSHI-ACCESS-KEY", "KALSHI-ACCESS-SIGNATURE", "KALSHI-ACCESS-TIMESTAMP"],
    decode_compressed_response=True,
)

def record_get_markets():
    """Record kalshi_get_markets.yaml cassette."""
    with recording_vcr.use_cassette("kalshi_get_markets.yaml"):
        client = KalshiClient(environment="demo")  # Uses REAL API credentials from .env
        markets = client.get_markets(series_ticker="KXNFLGAME", limit=5)
        print(f"✅ Recorded {len(markets)} markets to kalshi_get_markets.yaml")

def record_get_balance():
    """Record kalshi_get_balance.yaml cassette."""
    with recording_vcr.use_cassette("kalshi_get_balance.yaml"):
        client = KalshiClient(environment="demo")
        balance = client.get_balance()
        print(f"✅ Recorded balance ${balance} to kalshi_get_balance.yaml")

if __name__ == "__main__":
    record_get_markets()
    record_get_balance()
    # ... record other endpoints
```

**Step 2: Run recording script** (requires real API credentials)

```bash
# Ensure .env has KALSHI_DEMO_KEY_ID and KALSHI_DEMO_KEYFILE
python scripts/record_kalshi_cassettes.py

# Output:
# ✅ Recorded 5 markets to kalshi_get_markets.yaml
# ✅ Recorded balance $235084 to kalshi_get_balance.yaml
```

**Step 3: Verify cassettes updated**

```bash
git diff tests/cassettes/

# Example diff:
# - "balance": 220000
# + "balance": 235084  # Updated balance from current API state
```

**Step 4: Run tests with new cassettes**

```bash
python -m pytest tests/integration/api_connectors/test_kalshi_client_vcr.py -v

# All tests should pass ✅
```

**Step 5: Commit updated cassettes**

```bash
git add tests/cassettes/*.yaml
git commit -m "test: Re-record Kalshi VCR cassettes for updated API responses

- Updated kalshi_get_markets.yaml (5 markets)
- Updated kalshi_get_balance.yaml (balance: $235084)

Reason: API response format changed (added 'liquidity_dollars' field)"
```

**⚠️ Important:** NEVER commit cassettes with unfiltered credentials. Always verify `filter_headers` worked:

```bash
# Verify no credentials in cassettes
git grep -i "KALSHI-ACCESS-KEY" tests/cassettes/
# Should return: (no matches) ✅
```

---

### VCR + Pattern 13 Integration: Real API Responses + Real Database

**Best of Both Worlds:** Combine VCR (real API responses) with Pattern 13 (real database fixtures) for comprehensive integration tests.

**Example:** Test CLI command that fetches from API and saves to database

**File:** `tests/integration/cli/test_cli_database_integration.py`

```python
@pytest.mark.integration
@pytest.mark.cli
def test_cli_fetch_markets_saves_to_database(
    cli_runner,                # CLI test runner (from conftest.py)
    db_pool,                   # Real database connection pool (Pattern 13)
    db_cursor,                 # Real database cursor (Pattern 13)
    clean_test_data,           # Fixture to clean test data (Pattern 13)
    setup_kalshi_platform,     # Fixture to insert Kalshi platform (Pattern 13)
    monkeypatch,
):
    """
    Test that CLI 'fetch-markets' command:
    1. Fetches markets from Kalshi API (VCR cassette - REAL API response)
    2. Saves them to database (Pattern 13 - REAL database)

    Combines:
    - VCR Pattern: Real API responses from cassette ✅
    - Pattern 13: Real database fixtures ✅
    """
    # Mock environment variables for API client
    monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
    monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "_keys/kalshi_demo_private.pem")

    # VCR: Replay REAL API response from cassette
    with my_vcr.use_cassette("kalshi_get_markets.yaml"):
        result = cli_runner.invoke(cli, ["fetch-markets", "--limit", "5"])

    # Verify CLI success
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    # Pattern 13: Verify data saved to REAL database
    db_cursor.execute(
        """
        SELECT COUNT(*)
        FROM markets
        WHERE series_ticker = 'KXNFLGAME'
        AND row_current_ind = TRUE
        """
    )
    count = db_cursor.fetchone()[0]
    assert count == 5, "Should have saved 5 markets from VCR cassette to real database"

    # Verify Decimal precision in database (Pattern 1 + VCR + Pattern 13)
    db_cursor.execute(
        """
        SELECT ticker, yes_bid_dollars
        FROM markets
        WHERE series_ticker = 'KXNFLGAME'
        AND row_current_ind = TRUE
        LIMIT 1
        """
    )
    row = db_cursor.fetchone()
    assert isinstance(row[1], Decimal), "Database should store Decimal (not float)"
```

**Why This Integration Matters:**

1. **VCR provides real API data:** Cassette contains actual Kalshi market data (5 NFL markets with sub-penny pricing)
2. **Pattern 13 provides real database:** Test uses actual PostgreSQL database (not mocked connection)
3. **End-to-end validation:** Proves entire flow works (API → parsing → database) with real data
4. **Catches both API and DB bugs:**
   - API parsing bugs: VCR cassette has real response structure
   - Database bugs: Pattern 13 uses real SQL constraints, Decimal types, indexes

**Result:** Highest confidence integration test - uses real API responses AND real database.

---

### Real-World Impact: GitHub #124

**Context:** Phase 1.5 integration test audit revealed 77% false positive rate from mocks

**Problem:**
- Tests used mocked API responses: `{"balance": "1234.5678"}`
- Real Kalshi API returns: `{"balance": 123456}` (cents, not dollars!)
- Tests passed ✅ but production code would fail ❌

**Solution:** VCR Pattern (GitHub #124 Parts 1-6)

**Implementation:**
1. **Installed vcrpy:** `pip install vcrpy`
2. **Configured VCR:** `filter_headers` for credentials, `record_mode="none"` for tests
3. **Recorded 5 cassettes:** markets, balance, positions, fills, settlements
4. **Created 8 VCR tests:** `test_kalshi_client_vcr.py` (359 lines)
5. **Updated client:** Parse `yes_bid_dollars` (string) instead of `yes_bid` (int cents)

**Files Changed:**
- `tests/integration/api_connectors/test_kalshi_client_vcr.py` (NEW, 359 lines, 8 tests)
- `tests/cassettes/*.yaml` (5 new cassettes with REAL API data)
- `src/precog/api_connectors/kalshi_client.py` (updated to parse `*_dollars` fields)
- `docs/api-integration/KALSHI_SUBPENNY_PRICING_IMPLEMENTATION_V1.0.md` (NEW, 514 lines)

**Result:**
- ✅ All 8 VCR tests passing with REAL API data
- ✅ Caught dual-format pricing bug (mocks missed it)
- ✅ 100% confidence in API response parsing (uses actual Kalshi responses)
- ✅ Fast CI/CD (cassettes replay in ~1ms, no API calls)

---

### Summary

**VCR Pattern Checklist:**

- [ ] **Install vcrpy:** `pip install vcrpy`
- [ ] **Configure VCR:** Set `filter_headers` to remove credentials
- [ ] **Use `record_mode="none"` in tests:** Tests only replay (never record)
- [ ] **One cassette per test:** Specific naming (`<api>_<method>.yaml`)
- [ ] **Commit cassettes to git:** Reviewable in PRs, no credentials
- [ ] **Combine with Pattern 13:** VCR (real API) + Real database = comprehensive integration
- [ ] **Re-record with script:** Separate recording script (not in tests)
- [ ] **Verify credential filtering:** `git grep` cassettes before committing

**When to Use VCR:**
- ✅ Testing external API clients (Kalshi, ESPN, Balldontlie)
- ✅ Need real API response structures (prevents mocking errors)
- ✅ Want fast, deterministic tests (no network calls)
- ✅ CI/CD without API credentials

**Cross-References:**
- **Pattern 1:** Decimal Precision - VCR tests verify Decimal parsing with real API data
- **Pattern 13:** Real Fixtures, Not Mocks - VCR for API, real fixtures for database
- **ADR-075:** VCR Pattern for Integration Tests
- **REQ-TEST-013:** Integration tests use real API fixtures (VCR cassettes)
- **REQ-TEST-014:** Test coverage includes API integration with VCR
- **GitHub #124:** Fix integration test mocks (Parts 1-6: VCR implementation)
- **File:** `tests/integration/api_connectors/test_kalshi_client_vcr.py` (8 tests, 5 cassettes)
- **File:** `docs/api-integration/KALSHI_SUBPENNY_PRICING_IMPLEMENTATION_V1.0.md` (dual-format documentation)

---

## Pattern 23: Validation Failure Handling - Fix Failures, Don't Bypass (MANDATORY)

**TL;DR:** When validation checks fail (pre-commit, pre-push, CI), ALWAYS fix the root cause rather than bypassing with `--no-verify` or similar flags. Distinguish false positives from real failures, fix both, and update validation scripts to prevent future false positives.

**WHY:** Bypassing validation checks with `--no-verify` or disabling hooks creates technical debt and allows bugs to slip through. Real validation failures indicate code quality issues that must be fixed. False positives indicate validation script bugs that must be fixed to maintain developer trust.

**The Critical Principle:** "No verify should not be used, and validation failures should not be bypassed, without explicit permission"

### Real-World Example: SCD Type 2 Validation Script (This Session)

**The Scenario:**
Pre-push validation blocked with message:
```
[FAIL] 5 queries missing row_current_ind filter:
  src/precog/database/crud_operations.py:289 - Query on 'positions' table missing row_current_ind filter
  src/precog/database/crud_operations.py:337 - Query on 'positions' table missing row_current_ind filter
  src/precog/database/crud_operations.py:390 - Query on 'positions' table missing row_current_ind filter
  src/precog/database/crud_operations.py:436 - Query on 'positions' table missing row_current_ind filter
  src/precog/database/crud_operations.py:521 - Query on 'positions' table missing row_current_ind filter
```

**The Investigation:**
1. **Check lines manually:** All 5 lines were docstring parameter documentation
   ```python
   def get_position_by_id(position_id: int) -> dict:
       """
       Args:
           position_id: Position surrogate key (int from positions.id)
           #            ^^ This line flagged as "query on positions table"
       """
   ```

2. **Identify pattern:** All false positives mentioned table names in docstring parameter docs
3. **Root cause:** Validation script lacked docstring section detection (Args:, Returns:, etc.)

**The Solution (3-Part Fix):**

**Part 1: Fix False Positives (Update Validation Script)**

Added docstring section detection to `scripts/validate_scd_queries.py`:

```python
# Track docstring sections (Args, Returns, Raises, etc.)
in_docstring_section = False

for line_num, line in enumerate(lines, start=1):
    stripped = line.strip()

    # Detect docstring sections (Args:, Returns:, Raises:, etc.)
    if stripped in (
        "Args:",
        "Returns:",
        "Raises:",
        "Yields:",
        "Attributes:",
        "Examples:",
        "Note:",
        "Notes:",
        "Warning:",
        "See Also:",
    ):
        in_docstring_section = True
        continue

    # Exit docstring section when we hit empty line or dedented code
    if in_docstring_section:
        # Empty line or dedented line (not indented parameter doc)
        if not stripped or (not line.startswith((" ", "\t")) and stripped):
            in_docstring_section = False
        else:
            # Skip parameter documentation lines
            if ":" in stripped and not stripped.startswith(
                ("http:", "https:", "postgres:")
            ):
                continue

    # Now check for actual SQL queries (docstring params excluded)
    # ...
```

**Result:** 5 false positives eliminated → 0 violations

**Part 2: Fix Real Validation Failures (Property Tests)**

Pre-push blocked by missing property tests (Issue #127):
```
[FAIL] 1 modules missing or incomplete property tests:
  api_connectors/kalshi_client.py: No property test file found
```

**Response:** Created `tests/property/api_connectors/test_kalshi_client_properties.py` with 11 comprehensive tests

**Result:** 11/11 tests passing, 1,150+ test cases generated

**Part 3: Align Validation Config (Remove Excess Requirements)**

Pre-push blocked by validation config mismatch:
```
[FAIL] api_connectors/kalshi_client.py: Property tests missing coverage for 1 properties
  - TypedDict contracts enforced
```

**Investigation:** Issue #127 only required Decimal conversion property tests. TypedDict validation was already covered by integration tests (Pattern 13).

**Response:** Updated `scripts/validation_config.yaml` to align with actual requirements.

**Result:** Push successful, all 10 validation checks passed

---

### The 4-Step Validation Failure Response Protocol

When ANY validation check fails (pre-commit, pre-push, CI), follow this protocol:

#### Step 1: Investigate (5-10 minutes)

**Goal:** Determine if failure is false positive or real issue

**Actions:**
1. **Read error message carefully** - Understand what validation failed and why
2. **Check lines manually** - Verify if flagged lines actually violate the rule
3. **Search for pattern** - Do all failures share common characteristic?
4. **Review recent changes** - Did recent code introduce issue, or is validation script too strict?

**Decision Tree:**

| Scenario | Classification | Next Step |
|----------|---------------|-----------|
| All failures in docstrings/comments/examples | **False Positive** | Go to Step 2 (Fix Validation Script) |
| All failures from valid code patterns (e.g., parameter docs) | **False Positive** | Go to Step 2 (Fix Validation Script) |
| Failures point to actual code violations (hardcoded credentials, missing filters) | **Real Failure** | Go to Step 3 (Fix Code) |
| Mix of false positives and real failures | **Both** | Do Step 2 AND Step 3 |

#### Step 2: Fix False Positives (Update Validation Script)

**Goal:** Update validation script to eliminate false positives while maintaining real issue detection

**Actions:**
1. **Identify pattern causing false positives**
   - Example: "Docstring parameter documentation mentions table names"

2. **Add pattern detection to validation script**
   - Example: Detect docstring sections, skip parameter docs

3. **Test validation script**
   ```bash
   python scripts/validate_scd_queries.py --verbose
   ```

4. **Verify 0 false positives AND real issues still caught**
   - Create intentional violation in test file
   - Run validation script
   - Should catch intentional violation, ignore docstring params

5. **Commit validation script improvements**
   ```bash
   git add scripts/validate_*.py
   git commit -m "fix: Eliminate false positives in X validation script"
   ```

**Common False Positive Patterns:**

| Validation Check | Common False Positive | Fix |
|-----------------|----------------------|-----|
| SCD Type 2 queries | Docstring parameter docs mentioning table names | Detect docstring sections (Args:, Returns:, etc.) |
| Hardcoded credentials | Example credentials in docstrings (`api_key="test-key-id"`) | Skip lines in docstrings, detect example patterns |
| Property test requirements | Validation config requires more properties than GitHub issue | Align validation config with actual requirements |
| Decimal precision check | Test fixtures with intentional floats for negative testing | Skip files in `tests/fixtures/` or add `# noqa` with comment |

#### Step 3: Fix Real Failures (Update Code)

**Goal:** Fix actual code issues identified by validation

**Actions:**
1. **Understand requirement** - Why is this rule enforced? (Check ADRs, REQs, Patterns)

2. **Fix each violation**
   - Example: Missing property tests → Create property test file
   - Example: Hardcoded credentials → Use `os.getenv()`
   - Example: Missing `row_current_ind` filter → Add `.filter(row_current_ind == True)`

3. **Test fix locally**
   ```bash
   python -m pytest tests/ -v
   python scripts/validate_*.py
   ```

4. **Commit fix with explanation**
   ```bash
   git add <files>
   git commit -m "feat: Add property tests for kalshi_client.py (Issue #127)

   - Created 11 property tests for authentication, rate limiting, Decimal conversion
   - All tests passing (1,150+ test cases generated)
   - Satisfies REQ-TEST-008 and ADR-074"
   ```

#### Step 4: Re-run Validation (Verify Fix)

**Goal:** Confirm ALL validation checks pass after fixes

**Actions:**
1. **Run full validation locally**
   ```bash
   # Quick validation (~3s)
   ./scripts/validate_quick.sh

   # Full validation (~60s)
   ./scripts/validate_all.sh

   # Tests with coverage (~30s)
   ./scripts/test_full.sh
   ```

2. **Attempt push (triggers pre-push hooks)**
   ```bash
   git push origin <branch>
   ```

3. **Monitor pre-push output**
   - Look for "✅ [X/10] CHECK_NAME - PASSED"
   - If ANY check fails, return to Step 1

4. **Verify CI passes (after push)**
   ```bash
   gh pr checks
   ```

---

### When Bypass is Acceptable (Rare)

**⚠️ NEVER bypass validation without explicit approval from project lead**

**Acceptable bypass scenarios (with approval):**
1. **Emergency hotfix** - Production down, fix must deploy immediately
   - **Requirement:** Create GitHub issue to fix validation properly after hotfix
   - **Example:** `git commit --no-verify` + GitHub Issue #142 "Fix validation after hotfix"

2. **Validation script bug blocking all commits** - False positive affects entire team
   - **Requirement:** Fix validation script in separate commit immediately after
   - **Example:** Bypass commit → Fix validation script → Remove bypass

3. **External dependency issue** - Third-party API/tool broken, waiting for fix
   - **Requirement:** Document dependency issue, create fallback plan
   - **Example:** API provider down → Skip integration tests temporarily → Re-enable when fixed

**Unacceptable bypass scenarios (NEVER do this):**
- ❌ "Tests are slow, I'll fix them later"
- ❌ "I'm sure this code is fine, validation is wrong"
- ❌ "Just need to push quickly for demo"
- ❌ "Will create issue to fix validation... eventually"

---

### Validation Script Best Practices

**When creating/updating validation scripts:**

**1. Provide Clear Error Messages**
```python
# ❌ BAD (vague)
violations.append(f"{file}:{line} - Missing filter")

# ✅ GOOD (actionable)
violations.append(
    f"{relative_path}:{line_num} - Query on '{table}' table missing row_current_ind filter"
)
violations.append(
    f"  Fix: Add .filter({table.capitalize()}.row_current_ind == True)"
)
```

**2. Provide Escape Hatches for Intentional Violations**
```python
# Check for exception comments (e.g., "# Historical audit query")
has_exception_comment = False
comment_lines = lines[max(0, line_num - 3) : line_num]
comment_context = "\n".join(comment_lines)

for exception_comment in exception_comments:
    if exception_comment.lower() in comment_context.lower():
        has_exception_comment = True
        break

# Auto-detect historical audit functions (functions with "history" in name)
if not has_exception_comment:
    func_context_lines = lines[max(0, line_num - 30) : line_num]
    func_context = "\n".join(func_context_lines)
    if re.search(r"def\s+\w*history\w*\s*\(", func_context, re.IGNORECASE):
        has_exception_comment = True
```

**3. Skip Non-Code Contexts**
```python
# Skip docstrings, code blocks, examples
in_code_block = False
in_docstring_section = False

for line_num, line in enumerate(lines, start=1):
    # Toggle code block state (```)
    if stripped.startswith("```") or stripped == "```":
        in_code_block = not in_code_block
        continue

    if in_code_block:
        continue  # Skip lines in code blocks

    # Detect docstring sections
    if stripped in ("Args:", "Returns:", "Raises:", ...):
        in_docstring_section = True
        continue

    # Skip docstring examples (>>>)
    if stripped.startswith((">>>", "...")):
        continue
```

**4. Provide Verbose Mode for Debugging**
```python
def check_something(verbose: bool = False) -> tuple[bool, list[str]]:
    if verbose:
        print(f"[DEBUG] Scanning {len(files)} files")
        print(f"[DEBUG] Found {len(violations)} violations")

    return len(violations) == 0, violations
```

---

### Common Mistakes

**❌ WRONG: Bypass without investigation**
```bash
# Pre-push fails
git push  # Fails

# Immediately bypass
git push --no-verify  # ❌ WRONG - didn't investigate!
```

**✅ CORRECT: Investigate, fix, re-push**
```bash
# Pre-push fails
git push  # Fails with SCD Type 2 validation error

# Investigate manually
cat src/precog/database/crud_operations.py | grep -A5 "positions.id"
# Finds: "position_id: Position surrogate key (int from positions.id)" in docstring

# Identify false positive pattern
# Fix validation script (add docstring detection)
git add scripts/validate_scd_queries.py
git commit -m "fix: Eliminate docstring false positives"

# Re-push (now passes)
git push
```

---

**❌ WRONG: Fix false positive, ignore real failure**
```bash
# Pre-push fails with 2 errors:
# 1. SCD Type 2 false positive (docstring)
# 2. Missing property tests (real failure)

# Fix false positive only
git add scripts/validate_scd_queries.py
git commit -m "fix: Eliminate false positives"
git push --no-verify  # ❌ WRONG - bypassed real failure!
```

**✅ CORRECT: Fix both false positive AND real failure**
```bash
# Pre-push fails with 2 errors

# Fix false positive (validation script)
git add scripts/validate_scd_queries.py
git commit -m "fix: Eliminate false positives in SCD validation"

# Fix real failure (add missing tests)
git add tests/property/api_connectors/test_kalshi_client_properties.py
git commit -m "feat: Add property tests for kalshi_client.py (Issue #127)"

# Push (now passes all checks)
git push
```

---

**❌ WRONG: Update validation config to lower standards**
```bash
# Pre-push fails: "80% coverage required, only 78%"

# Lower threshold to 70%
# Edit: scripts/validation_config.yaml
coverage_threshold: 70  # ❌ WRONG - lowered standards!
```

**✅ CORRECT: Add tests to meet coverage threshold**
```bash
# Pre-push fails: "80% coverage required, only 78%"

# Add tests to increase coverage
# Edit: tests/unit/database/test_crud_operations.py
# (Add 3 tests for uncovered branches)

# Re-run tests
python -m pytest tests/ --cov=src/precog/database/crud_operations --cov-report=term
# Coverage: 82% ✅

# Commit new tests
git add tests/unit/database/test_crud_operations.py
git commit -m "test: Increase CRUD operations coverage to 82%"
```

---

### Integration with Other Patterns

**Pattern 21 (Validation-First Architecture):**
- This pattern complements Pattern 21's 4-layer defense (pre-commit → pre-push → CI → branch protection)
- When any layer fails, use this pattern's 4-step protocol to fix rather than bypass

**Pattern 18 (Avoid Technical Debt):**
- Bypassing validation = creating technical debt
- Use Pattern 18's 3-part process (Acknowledge → Schedule → Fix) if must bypass

**Pattern 9 (Multi-Source Warning Governance):**
- Validation script warnings must be triaged (false positive vs. real issue)
- Apply same fix-don't-bypass principle to warnings

---

### Testing Validation Scripts

**Create test cases for validation scripts:**

```python
# tests/test_validate_scd_queries.py
def test_scd_validation_catches_real_violations():
    """Verify validation script catches queries missing row_current_ind."""
    test_code = '''
    def get_position(position_id: int):
        query = "SELECT * FROM positions WHERE id = %s"  # Missing row_current_ind!
        cursor.execute(query, (position_id,))
    '''

    # Write test file
    test_file = tmp_path / "test_code.py"
    test_file.write_text(test_code)

    # Run validation
    passed, violations = check_scd_queries(str(tmp_path))

    # Should catch violation
    assert not passed
    assert any("positions" in v for v in violations)
    assert any("row_current_ind" in v for v in violations)


def test_scd_validation_ignores_docstring_parameters():
    """Verify validation script does NOT flag docstring parameter docs."""
    test_code = '''
    def get_position(position_id: int):
        """
        Args:
            position_id: Position surrogate key (int from positions.id)
        """
        query = "SELECT * FROM positions WHERE row_current_ind = TRUE AND id = %s"
        cursor.execute(query, (position_id,))
    '''

    # Write test file
    test_file = tmp_path / "test_code.py"
    test_file.write_text(test_code)

    # Run validation
    passed, violations = check_scd_queries(str(tmp_path))

    # Should NOT flag docstring (false positive eliminated)
    assert passed
    assert len(violations) == 0
```

---

### Real-World Impact

**This Session's Validation Improvements:**
- **False positives eliminated:** 5 (SCD Type 2 docstring false positives)
- **Real failures fixed:** 11 property tests added (Issue #127)
- **Validation config aligned:** Removed 2 excess requirements
- **Pre-push success rate:** 0% → 100% (blocked → passing)
- **Time spent:** ~90 minutes (investigation, fixes, testing)
- **Time saved (future):** ~15 min per developer per validation failure (no more manual investigation of docstring false positives)

**Key Takeaway:** Investing time to fix validation scripts AND code issues pays off immediately and prevents future developer frustration.

---

### Cross-References

**Related Patterns:**
- **Pattern 21 (Validation-First Architecture):** 4-layer defense in depth (where failures occur)
- **Pattern 18 (Avoid Technical Debt):** When deferral is acceptable (not applicable to validation bypasses)
- **Pattern 9 (Multi-Source Warning Governance):** Fix-don't-bypass principle applies to warnings too

**Related Issues:**
- **This Session:** SCD Type 2 false positives, Issue #127 property tests, validation config alignment
- **GitHub Issue #127:** Property tests for API layer (real failure fixed in this session)

**Related Files:**
- `scripts/validate_scd_queries.py` - SCD Type 2 validation (false positives fixed this session)
- `scripts/validation_config.yaml` - Property test requirements (aligned with Issue #127)
- `scripts/check_warning_debt.py` - Warning governance (timeout increased to 600s)
- `tests/property/api_connectors/test_kalshi_client_properties.py` - Property tests (created this session)

**Related ADRs:**
- **ADR-002 (Decimal Precision):** Validation enforces this pattern (pre-commit hook)
- **ADR-018/019/020 (Dual Versioning):** SCD Type 2 validation enforces row_current_ind filtering
- **ADR-074 (Property-Based Testing):** Property test validation enforces this pattern

---

## Pattern 24: No New Usage of Deprecated Code (MANDATORY)

**TL;DR:** When building new features or refactoring, ALWAYS use modern/current APIs, TypeDicts, and patterns. NEVER use deprecated code in new implementations. Migrate progressively as you touch code.

**WHY:** Using deprecated code in new implementations:
1. **Accumulates technical debt** - More code that needs eventual migration
2. **Creates inconsistency** - Some code uses old patterns, some uses new
3. **Delays full migration** - The deprecated code never gets removed
4. **Confuses developers** - Which pattern should new code follow?

### The Rule

```
When code is marked as DEPRECATED:
  - New implementations: MUST use the modern replacement
  - Existing code: SHOULD migrate when touched (refactoring, bug fixes)
  - Tests: MUST add tests for modern API, MAY keep deprecated tests temporarily
```

### Real-World Example: ESPN TypedDicts (This Session)

**The Scenario:**
- `GameState` TypedDict: Flat structure, marked DEPRECATED
- `ESPNGameFull` TypedDict: Normalized structure with `metadata` and `state` sections
- `get_scoreboard()`: Returns deprecated `GameState`
- `get_scoreboard_normalized()`: Returns modern `ESPNGameFull`

**The Problem:**
When building `MarketUpdater` for Phase 2 live polling, the code initially used:
```python
# ❌ WRONG: Using deprecated API in new code
games = self.espn_client.get_scoreboard(league)  # Returns GameState (deprecated)
for game in games:
    self._sync_game_to_db(game, league)  # Expects flat dict
```

**The Fix:**
```python
# ✅ CORRECT: Using modern normalized API
games = self.espn_client.get_scoreboard_normalized(league)  # Returns ESPNGameFull
for game in games:
    # Use normalized structure with clear metadata/state separation
    metadata = game["metadata"]
    state = game["state"]
    home_team = metadata["home_team"]["team_code"]  # Type-safe access
```

### Migration Checklist

When encountering deprecated code:

1. **Identify the modern replacement**
   - Check docstrings for "DEPRECATED, use X instead"
   - Check related ADRs or design documents
   - If no replacement exists, create one before using deprecated code

2. **New code uses modern API (MANDATORY)**
   ```python
   # Building new MarketUpdater
   def _poll_league(self, league: str):
       # ✅ MUST use get_scoreboard_normalized (modern)
       games = self.espn_client.get_scoreboard_normalized(league)
   ```

3. **Add modern API if needed**
   ```python
   # ESPN client only had deprecated method
   # ✅ Add get_scoreboard_normalized() before using in new code
   def get_scoreboard_normalized(self, league: str) -> list[ESPNGameFull]:
       """Fetch scoreboard with normalized TypedDict structure."""
       ...
   ```

4. **Update tests for new implementations**
   - New tests MUST use modern API
   - Existing deprecated tests can remain temporarily
   - Mark deprecated tests for eventual removal

5. **Update documentation**
   - Clearly mark deprecated APIs in docstrings
   - Document migration path
   - Update examples to use modern API

### Common Deprecated Patterns in This Codebase

| Deprecated | Modern Replacement | Migration Guide |
|------------|-------------------|-----------------|
| `GameState` (flat TypedDict) | `ESPNGameFull` (normalized) | Use `get_scoreboard_normalized()` |
| `get_scoreboard()` | `get_scoreboard_normalized()` | Returns ESPNGameFull with metadata/state |
| `row_current_ind = 1` | `row_current_ind = TRUE` | Boolean column, not integer |

### Decision Tree

```
Building new feature or refactoring existing code?
├── YES: Does the code touch deprecated APIs?
│   ├── YES: Use modern replacement (MANDATORY)
│   │   ├── Modern replacement exists? → Use it
│   │   └── No modern replacement? → Create it first, then use it
│   └── NO: Proceed normally
└── NO (just bug fix): Is fix trivial?
    ├── YES: Can use deprecated API (document migration needed)
    └── NO: Should use modern replacement
```

### ❌ WRONG vs ✅ CORRECT Examples

**❌ WRONG: New feature using deprecated API**
```python
# Building new MarketUpdater service (new code)
class MarketUpdater:
    def poll(self):
        # Using deprecated GameState format
        games = self.client.get_scoreboard("nfl")  # ❌ Deprecated
        for game in games:
            score = game["home_score"]  # Flat structure
```

**✅ CORRECT: New feature using modern API**
```python
# Building new MarketUpdater service (new code)
class MarketUpdater:
    def poll(self):
        # Using modern ESPNGameFull format
        games = self.client.get_scoreboard_normalized("nfl")  # ✅ Modern
        for game in games:
            score = game["state"]["home_score"]  # Clear structure
            team = game["metadata"]["home_team"]["team_code"]  # Type-safe
```

---

**❌ WRONG: Creating modern replacement but not using it**
```python
# Added get_scoreboard_normalized() to ESPN client
# But MarketUpdater still uses deprecated get_scoreboard()
# ❌ Both modern and deprecated APIs exist, but new code uses deprecated
```

**✅ CORRECT: Create and use modern replacement**
```python
# 1. Add get_scoreboard_normalized() to ESPN client
# 2. Update MarketUpdater to use get_scoreboard_normalized()
# 3. Update tests to test new API
# 4. Mark get_scoreboard() as deprecated in docstring
```

### Cross-References

**Related Patterns:**
- **Pattern 6 (TypedDict):** Prefer TypedDicts over raw dicts (this extends to preferring modern TypedDicts)
- **Pattern 18 (Avoid Technical Debt):** Deprecated code is technical debt
- **Pattern 23 (Validation Failure Handling):** Don't bypass by using deprecated code to avoid migration

**Related Files:**
- `src/precog/api_connectors/espn_client.py` - GameState (deprecated) vs ESPNGameFull (modern)
- `src/precog/schedulers/market_updater.py` - Uses modern ESPNGameFull

**Real-World Trigger:**
- Session 2025-11-28: Building MarketUpdater initially used deprecated GameState
- User asked: "if its deprecated, why are you still using it?"
- Led to adding `get_scoreboard_normalized()` and this pattern

---

## Pattern 25: ANSI Escape Code Handling for Cross-Platform CLI Testing (ALWAYS)

### The Rule

**ALWAYS use `strip_ansi()` helper when testing CLI output from Rich library on Windows.**

Rich library outputs ANSI escape codes for colors/formatting that are embedded within text. On Windows, these codes break string matching in tests.

### The Problem

Rich outputs colored text with ANSI codes embedded **within** the expected text:

```python
# What Rich outputs (invisible in terminal, visible in tests):
"$\x1b[1;36m47.50\x1b[0m"  # The $47.50 is split by ANSI codes!

# What tests check for:
"$47.50"  # This string is NOT in the Rich output!
```

**Why this fails:**
- `"$47.50" in result.stdout` → `False` (the dollar sign is before the ANSI code)
- `"47.50" in result.stdout` → `False` (ANSI code comes immediately after "47")
- Works on Ubuntu (different ANSI handling), fails on Windows

### The Solution

Create a `strip_ansi()` helper function to remove ANSI codes before assertions:

```python
import re

def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Rich library outputs ANSI codes for colors/formatting, which can break
    string matching in tests when codes are embedded within expected text.

    Example:
        Input:  "\\x1b[1;36m100\\x1b[0m contracts"
        Output: "100 contracts"

    Args:
        text: String potentially containing ANSI escape codes

    Returns:
        String with all ANSI escape codes removed
    """
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)
```

### Code Examples

**❌ WRONG - Fails on Windows:**
```python
def test_fetch_settlements_single(self, runner, mock_kalshi_client):
    result = runner.invoke(app, ["fetch-settlements"])
    assert result.exit_code == 0
    # FAILS: Rich outputs "$\x1b[1;36m47.50\x1b[0m"
    assert "$47.50" in result.stdout
```

**✅ CORRECT - Cross-platform compatible:**
```python
def test_fetch_settlements_single(self, runner, mock_kalshi_client):
    result = runner.invoke(app, ["fetch-settlements"])
    assert result.exit_code == 0
    # Strip ANSI codes for cross-platform compatibility
    output = strip_ansi(result.stdout)
    assert "$47.50" in output
```

### When to Use This Pattern

| Scenario | Use strip_ansi()? |
|----------|-------------------|
| CLI test with Rich tables | ✅ YES |
| CLI test with Rich progress bars | ✅ YES |
| CLI test with colored text | ✅ YES |
| CLI test with plain print() | ❌ No (no ANSI codes) |
| Non-CLI tests | ❌ No (not applicable) |
| Testing on Ubuntu only | ⚠️ Still recommended (future-proof) |

### Common Patterns Fixed by This

**Monetary values:**
```python
# Rich outputs: "$\x1b[1;36m47.50\x1b[0m"
output = strip_ansi(result.stdout)
assert "$47.50" in output
```

**Counts and metrics:**
```python
# Rich outputs: "Fetched \x1b[1;36m1\x1b[0m fills"
output = strip_ansi(result.stdout)
assert "Fetched 1 fills" in output
```

**Progress indicators:**
```python
# Rich outputs: "\x1b[1;36m[1/4]\x1b[0m Checking API"
output = strip_ansi(result.stdout)
assert "[1/4]" in output
```

**Pagination messages:**
```python
# Rich outputs: "and \x1b[1;36m5\x1b[0m more fills"
output = strip_ansi(result.stdout)
assert "and 5 more fills" in output
```

### Implementation Location

Add the `strip_ansi()` helper at the top of your test file:

```python
# tests/unit/test_main.py (line ~30, after imports)

import re

def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)
```

**Future improvement:** Move to `tests/conftest.py` or `tests/helpers.py` for reuse across test files.

### Cross-References

**Related Patterns:**
- **Pattern 5 (Cross-Platform Compatibility):** This pattern is a specific case of cross-platform issues
- **Pattern 21 (Validation-First Architecture):** CI catches these issues on Windows matrix

**Related Files:**
- `tests/unit/test_main.py` - Contains `strip_ansi()` helper and 20+ fixed assertions
- `main.py` - CLI implementation using Rich library

**Related PRs:**
- **PR #159:** Phase 2C CRUD Operations - 20+ assertions fixed with this pattern

**Real-World Trigger:**
- Session 2025-11-29: CI passed on Ubuntu but failed on Windows
- Root cause: Rich library ANSI codes embedded within monetary values
- Tests checking `"$47.50" in result.stdout` failed because actual output was `"$\x1b[1;36m47.50\x1b[0m"`
- Fixed 20+ assertions across test_fetch_fills, test_fetch_settlements, test_health_check

---

## Pattern 26: Resource Cleanup for Testability (close() Methods) (ALWAYS)

### The Rule

**ALWAYS add explicit `close()` methods to classes that manage external resources (HTTP sessions, database connections, file handles).**

This enables proper resource cleanup in tests and production code, prevents resource leaks, and allows mocking session lifecycle.

### The Problem

Without explicit cleanup methods:
1. Resources leak in long-running processes
2. Tests cannot verify cleanup behavior
3. Mock sessions cannot be properly closed
4. Connection pool exhaustion in high-throughput scenarios

```python
# ❌ WRONG: No cleanup method
class KalshiClient:
    def __init__(self):
        self.session = requests.Session()
        # No way to close the session!

# Tests have no way to verify cleanup
def test_client():
    client = KalshiClient()
    client.get_markets()
    # Session left open forever
```

### The Solution

Add explicit `close()` methods to all resource-managing classes:

```python
# ✅ CORRECT: Explicit cleanup
class KalshiClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session if session is not None else requests.Session()
        self._owns_session = session is None  # Track if we created it

    def close(self) -> None:
        """Close HTTP session and release resources.

        Educational Note:
            Explicit cleanup is crucial for:
            1. Testing: Verify cleanup behavior with mocks
            2. Resource management: Prevent connection leaks
            3. Graceful shutdown: Clean exit in long-running processes
        """
        if hasattr(self, "session") and self.session is not None:
            self.session.close()
```

### Classes Requiring close() Methods

| Class | Resource Type | close() Method |
|-------|--------------|----------------|
| `KalshiClient` | HTTP Session (requests.Session) | `self.session.close()` |
| `ESPNClient` | HTTP Session | `self.session.close()` |
| `KalshiWebSocketHandler` | WebSocket Connection | `self.stop()` (alias for close) |
| `KalshiMarketPoller` | Background Thread + Session | `self.stop()` |
| Database Connection Pool | PostgreSQL Connections | `self.engine.dispose()` |

### Code Examples

**ESPNClient with close():**
```python
class ESPNClient:
    def __init__(self, rate_limit: int = 500, timeout: int = 10, max_retries: int = 3):
        self.session = requests.Session()
        self._rate_limiter = RateLimiter(rate_limit)
        # ... other init

    def close(self) -> None:
        """Close HTTP session and release resources."""
        if hasattr(self, "session") and self.session is not None:
            self.session.close()
```

**Test using close():**
```python
def test_client_cleanup():
    client = ESPNClient()
    try:
        # Use client...
        client.get_scoreboard("nfl")
    finally:
        client.close()  # Explicit cleanup
```

**Or use context manager pattern:**
```python
# ✅ BEST: Context manager for automatic cleanup
class ESPNClient:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

# Usage:
with ESPNClient() as client:
    client.get_scoreboard("nfl")
# Automatically closed
```

### Cross-References

**Related Patterns:**
- **Pattern 27 (Dependency Injection):** close() works with injected sessions
- **Pattern 20 (Resource Management):** General resource management principles

**Related Files:**
- `src/precog/api_connectors/kalshi_client.py:366-376` - KalshiClient.close()
- `src/precog/api_connectors/espn_client.py:119-126` - ESPNClient.close()

**Related PRs:**
- **Phase 1.9 Part B:** Added close() methods to all API clients

**Real-World Trigger:**
- Session 2025-12-02: Phase 1.9 Test Infrastructure discovered stress tests couldn't verify cleanup
- Tests mocking sessions had no way to verify session.close() was called

---

## Pattern 27: Dependency Injection for Testability (ALWAYS for External Resources)

### The Rule

**ALWAYS use optional constructor parameters for external dependencies (HTTP sessions, auth handlers, rate limiters) to enable clean testing without patches.**

Dependency Injection (DI) makes classes testable by allowing mock dependencies to be injected directly, rather than using complex `@patch` decorators.

### The Problem

Without DI, tests require complex patching:

```python
# ❌ WRONG: Hard to test - requires patching internal modules
class KalshiClient:
    def __init__(self):
        self.auth = KalshiAuth(
            api_key=os.getenv("KALSHI_API_KEY"),
            private_key_path=os.getenv("KALSHI_KEY_PATH"),
        )
        self.session = requests.Session()
        self.rate_limiter = RateLimiter()

# Tests become fragile:
@patch.dict("os.environ", {"KALSHI_API_KEY": "test"})
@patch("precog.api_connectors.kalshi_auth.load_private_key")
@patch("precog.api_connectors.kalshi_client.RateLimiter")
def test_client(mock_limiter, mock_load, mock_env):
    mock_load.return_value = MagicMock()
    client = KalshiClient()
    # 3 levels of patching required!
```

### The Solution

Accept optional dependencies in constructor:

```python
# ✅ CORRECT: Dependency Injection pattern
class KalshiClient:
    def __init__(
        self,
        environment: str = "demo",
        auth: KalshiAuth | None = None,
        session: requests.Session | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        """Initialize client with optional dependency injection.

        Args:
            environment: API environment ("demo" or "prod")
            auth: Optional KalshiAuth instance. If None, created from env vars.
            session: Optional HTTP session. If None, new Session created.
            rate_limiter: Optional rate limiter. If None, default created.

        Educational Note:
            Dependency Injection makes this class testable without patches:
            - Production: Pass None for all, defaults created from environment
            - Testing: Inject mocks directly via constructor
        """
        # Use injected dependencies or create defaults
        self.auth = auth if auth is not None else self._create_auth(environment)
        self.session = session if session is not None else requests.Session()
        self.rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()

# Clean tests - no patching!
def test_client():
    mock_auth = MagicMock()
    mock_session = MagicMock()
    mock_limiter = MagicMock()

    client = KalshiClient(
        environment="demo",
        auth=mock_auth,
        session=mock_session,
        rate_limiter=mock_limiter,
    )
    # Test with full control over dependencies!
```

### DI Patterns for Common Dependencies

**1. Key Loader (for cryptographic operations):**
```python
class KalshiAuth:
    def __init__(
        self,
        api_key: str,
        private_key_path: str,
        key_loader: Callable[[str], RSAPrivateKey] | None = None,
    ):
        """Accept optional key loader for testing.

        Production: key_loader=None -> uses load_private_key()
        Testing: key_loader=lambda p: mock_key -> no file access needed
        """
        _loader = key_loader if key_loader is not None else load_private_key
        self.private_key = _loader(private_key_path)
```

**2. HTTP Session (for API clients):**
```python
class ESPNClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        self.session = session if session is not None else requests.Session()
        self._rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()
```

### Test Helper Pattern

Create helper methods in test classes for consistent mock creation:

```python
class TestKalshiClientStress:
    def _create_mock_client(self):
        """Create KalshiClient with mocked dependencies using DI.

        Educational Note:
            This helper demonstrates the clean DI approach.
            No patches needed - just inject mocks directly!
        """
        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "Authorization": "Bearer mock-token",
            "Content-Type": "application/json",
        }

        mock_session = MagicMock()
        mock_limiter = MagicMock()

        return KalshiClient(
            environment="demo",
            auth=mock_auth,
            session=mock_session,
            rate_limiter=mock_limiter,
        )

    def test_concurrent_requests(self):
        client = self._create_mock_client()
        # Test with full control!
```

### Migration: Patching to DI

**Before (complex patching):**
```python
with patch.dict("os.environ", env_vars):
    with patch("module.load_private_key") as mock_load:
        mock_load.return_value = mock_key
        client = KalshiClient(environment="demo")
```

**After (clean DI):**
```python
client = KalshiClient(
    environment="demo",
    auth=mock_auth,
    session=mock_session,
    rate_limiter=mock_limiter,
)
```

### When to Use DI

| Dependency Type | Use DI? | Example |
|-----------------|---------|---------|
| HTTP sessions | ✅ YES | `requests.Session` |
| Database connections | ✅ YES | `sqlalchemy.Engine` |
| Auth handlers | ✅ YES | `KalshiAuth` |
| Rate limiters | ✅ YES | `RateLimiter` |
| File loaders | ✅ YES | `load_private_key` callable |
| Configuration | ✅ YES | `ConfigLoader` |
| Pure functions | ❌ No | Math calculations |
| Constants | ❌ No | `BASE_URL` strings |

### Cross-References

**Related Patterns:**
- **Pattern 26 (Resource Cleanup):** DI-injected resources still need cleanup
- **Pattern 13 (Test Coverage Quality):** DI enables proper integration testing

**Related Files:**
- `src/precog/api_connectors/kalshi_client.py:75-115` - KalshiClient DI constructor
- `src/precog/api_connectors/kalshi_auth.py:205-260` - KalshiAuth with key_loader DI
- `tests/stress/api_connectors/test_kalshi_client_stress.py` - DI test helper example

**Related PRs:**
- **Phase 1.9 Part B:** Added DI to KalshiClient, KalshiAuth, ESPNClient

**Real-World Trigger:**
- Session 2025-12-02: Phase 1.9 discovered tests using complex patching
- Test `test_concurrent_session_initialization` failed with "name 'patch' is not defined"
- Root cause: Test still used old patching approach, hadn't imported `patch`
- Solution: Convert to DI pattern - no patches needed, cleaner tests

---

## Pattern 28: CI-Safe Stress Testing - skipif for Threading-Based Tests (ALWAYS)

### The Problem

Stress tests using `ThreadPoolExecutor`, `threading.Barrier()`, sustained `time.perf_counter()` loops, or concurrent operations can **hang indefinitely** in CI environments due to resource constraints:

```
# CI Log showing timeout:
FAILED tests/stress/api_connectors/test_kalshi_client_stress.py - TIMEOUT after 600s
# Or just hangs for 15+ minutes with no output
```

**Root Causes:**
1. **ThreadPoolExecutor + as_completed():** Concurrent futures waiting on each other can deadlock when thread scheduling is unpredictable in CI.
2. **Threading Barriers:** `threading.Barrier(20).wait()` requires all 20 threads to reach the barrier. In CI with limited CPU, thread scheduling delays can exceed the default timeout.
3. **Time-based Loops:** `while time.perf_counter() - start < 5.0:` loops may take 10x longer on resource-constrained CI runners.
4. **pytest-timeout Limitations:** `--timeout-method=thread` cannot reliably interrupt blocking Python code in threads (SIGALRM only works on main thread).
5. **VCR Cassettes with Large Responses:** YAML parsing of multi-KB API responses can hang in CI (discovered in PR #167).

### The Solution (Evolved)

**⚠️ UPDATE (Issue #168, 2025-12-06):** Use `pytest.mark.skipif` instead of `xfail(run=False)` for cleaner semantics:

| Approach | Output | Semantics | Recommendation |
|----------|--------|-----------|----------------|
| `xfail(run=False)` | XFAIL | "Test expected to fail" | ❌ Misleading - test would pass locally |
| `skipif(_is_ci)` | SKIPPED | "Intentionally not run" | ✅ Clear intent |

**Use `skipif` to skip execution in CI while allowing tests to run locally:**

```python
import os
import pytest

# CI environment detection - standardized pattern
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

_CI_SKIP_REASON = (
    "Stress tests skip in CI - they can hang in resource-constrained environments. "
    "Run locally: pytest tests/stress/ -v -m stress. See GitHub issue #168."
)

# Module-level pytestmark for ALL tests in file
pytestmark = [
    pytest.mark.stress,
    pytest.mark.slow,
    pytest.mark.skipif(_is_ci, reason=_CI_SKIP_REASON),
]


class TestRateLimitingStress:
    """Stress tests for rate limiting under high load."""

    def test_concurrent_requests_tracked(self):
        """Test 100 concurrent requests are properly tracked."""
        # This test uses ThreadPoolExecutor - would hang in CI
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(rate_limited_call) for _ in range(100)]
            for future in as_completed(futures):
                pass  # Would hang waiting for completion in CI
```

### Why skipif Over xfail(run=False)

| Aspect | `xfail(run=False)` | `skipif(_is_ci)` |
|--------|-------------------|------------------|
| **Output** | XFAIL | SKIPPED |
| **Semantics** | "Expected to fail" | "Intentionally skipped" |
| **Intent Clarity** | ❌ Misleading (test passes locally) | ✅ Clear (CI resources insufficient) |
| **pytest Exit Code** | 0 (success) | 0 (success) |
| **Recommendation** | Legacy approach | ✅ **Preferred** |

**Use `skipif` for stress tests** - cleaner semantics and clearer intent.

### ⚠️ Important: Strategic CI Skip Decision

**Current Status:** `skipif(_is_ci)` is the **production approach** for stress tests that use threading constructs. This is NOT a temporary workaround - it's a deliberate architectural decision.

**Rationale:** Stress tests are designed to push systems to their limits. CI environments are intentionally resource-constrained. Running stress tests in CI:
- Wastes CI minutes (15+ min hangs vs 14 sec skip)
- Doesn't provide meaningful results (constrained resources ≠ production behavior)
- Can cause entire CI pipelines to fail/timeout

**Long-Term Strategy:**

| Layer | Solution | Status | Purpose |
|-------|----------|--------|---------|
| **CI** | `skipif(_is_ci)` | ✅ Production | Fast feedback on functional tests |
| **Local Dev** | Full stress tests | ✅ Works | Developer validation with real resources |
| **Database Stress** | Testcontainers | ✅ Implemented (#168) | Isolated PostgreSQL per test class |
| **Pre-release** | Dedicated stress env | 🔵 Phase 5+ | Full stress testing before production |

**Why NOT Run Stress Tests in CI:**
1. **Resource Mismatch:** CI runners have 2 vCPUs vs. 8+ cores locally - threading behavior is fundamentally different
2. **Timeout Cascades:** One hanging test blocks entire CI pipeline for other PRs
3. **False Negatives:** Tests may fail due to CI constraints, not actual bugs
4. **Cost:** GitHub Actions minutes are finite - spend them on meaningful tests

**Tracking:** See GitHub issue #168 (testcontainers) and #171 (test isolation improvement)

**Implementation Timeline:**
1. ✅ **Phase 1.9:** Added `xfail(run=False)` to prevent CI hangs
2. ✅ **Issue #168:** Evolved to `skipif(_is_ci)` for cleaner semantics
3. ✅ **Issue #168:** Implemented testcontainers for database stress tests
4. 🔵 **Issue #171:** Hybrid test isolation (transaction rollback + phase separation)

### Test Type CI Behavior Classification

| Test Type | CI Behavior | Pattern | Reasoning |
|-----------|-------------|---------|-----------|
| **Stress tests** | `skipif(_is_ci)` | Threading barriers, ThreadPoolExecutor, sustained loops | Would hang CI indefinitely |
| **Race condition tests** | `skipif(_is_ci)` | Same as stress | Same threading issues |
| **Database stress** | `skipif(_is_ci)` | Testcontainers + ThreadPoolExecutor | Connection pool exhaustion tests |
| **Performance tests (latency)** | `skipif(_is_ci)` | Tight thresholds (<20ms p99) | Variable CPU on shared runners (Issue #238) |
| **Chaos tests** | **RUN NORMALLY** | Mock injection, fault simulation | No blocking operations |
| **E2E tests** | Conditional skip | `skipif(not _has_live_data)` | Depends on external data |
| **Integration tests** | **RUN NORMALLY** | Real database, mocked APIs | Fast, deterministic |
| **Security tests** | **RUN NORMALLY** | Input validation, auth checks | Fast, critical |
| **Property tests** | **RUN NORMALLY** | Hypothesis with bounded examples | Fast (100 examples/property) |

### Implementation Pattern

**File Structure (Post-Issue #168):**
```
tests/
├── stress/
│   ├── test_config_loader_stress.py   # pytestmark = [skipif(_is_ci)]
│   ├── test_logger_stress.py          # pytestmark = [skipif(_is_ci)]
│   └── test_connection_stress.py      # pytestmark = [skipif(_is_ci)] + testcontainers
├── fixtures/
│   └── stress_testcontainers.py       # CISafeBarrier, with_timeout, container fixtures
├── chaos/
│   └── api_connectors/
│       ├── test_kalshi_client_chaos.py   # RUN NORMALLY (mock injection)
│       └── test_espn_client_chaos.py     # RUN NORMALLY
└── e2e/
    └── test_espn_api_e2e.py              # skipif(not _has_live_data)
```

**Module-Level Skip Pattern (Recommended - DRY):**
```python
# tests/stress/test_config_loader_stress.py
import os
import pytest

# CI environment detection - skip stress tests in CI
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
_CI_SKIP_REASON = (
    "Stress tests skip in CI - they can hang in resource-constrained environments. "
    "Run locally: pytest tests/stress/test_config_loader_stress.py -v"
)

# Module-level pytestmark applies to ALL tests in this file
pytestmark = [
    pytest.mark.stress,
    pytest.mark.slow,
    pytest.mark.skipif(_is_ci, reason=_CI_SKIP_REASON),
]

# All test classes and functions in this file are automatically skipped in CI
class TestConfigLoaderConcurrency:
    def test_concurrent_config_reads(self, config_loader):
        # This test is skipped in CI but runs locally
        ...
```

### Wrong vs. Correct

```python
# WRONG: Tests run in CI and hang for 15+ minutes
@pytest.mark.stress
class TestStress:
    def test_concurrent(self):
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(work) for _ in range(50)]
            for future in as_completed(futures):
                pass  # Hangs in CI due to thread scheduling delays

# WRONG: xfail(run=True) still executes the test body
@pytest.mark.stress
@pytest.mark.xfail(condition=_is_ci, reason="CI unstable")  # run=True is default!
class TestStress:
    def test_concurrent(self):
        # STILL HANGS - xfail without run=False executes the test

# OUTDATED: xfail(run=False) works but semantics are misleading
@pytest.mark.stress
@pytest.mark.xfail(condition=_is_ci, reason=_CI_XFAIL_REASON, run=False)
class TestStress:
    def test_concurrent(self):
        # Works but shows "XFAIL" - suggests test is expected to fail
        # Better: use skipif for "intentionally not run"

# CORRECT: skipif with module-level pytestmark (Issue #168 pattern)
pytestmark = [
    pytest.mark.stress,
    pytest.mark.slow,
    pytest.mark.skipif(_is_ci, reason=_CI_SKIP_REASON),
]

class TestStress:
    def test_concurrent(self):
        # Shows "SKIPPED" in CI - clear intent: not run by design
        with ThreadPoolExecutor(max_workers=50) as executor:
            ...  # Runs locally, skipped in CI
```

### When to Use Each Pattern

| Scenario | Pattern | Example |
|----------|---------|---------|
| Threading with barriers | `skipif(_is_ci)` | Race condition tests, concurrent access |
| Time-based loops | `skipif(_is_ci)` | Performance benchmarks, sustained load |
| Large VCR cassettes | `skipif(_is_ci)` | API responses >10KB YAML |
| Database stress tests | `skipif(_is_ci)` + testcontainers | Connection pool exhaustion tests |
| Mock injection | RUN NORMALLY | Chaos tests injecting failures |
| External data dependency | `skipif(not condition)` | E2E tests needing live games |
| Known flaky test | `xfail(run=True)` | Intermittent failures being investigated |

### Local Execution

**Run stress tests locally (where resources are adequate):**
```bash
# All stress tests
pytest tests/stress/ -v -m stress

# Specific stress test module
pytest tests/stress/api_connectors/test_kalshi_client_stress.py -v

# With timing
pytest tests/stress/ -v --durations=10
```

### CI Workflow Integration

**GitHub Actions shows skipped tests clearly:**
```yaml
# .github/workflows/test.yml
- name: Run Tests
  run: |
    # Stress tests will show as "SKIPPED" (intentional), not failures
    pytest tests/ -v --tb=short

    # CI output will show:
    # tests/stress/test_config_loader_stress.py::TestConfigLoaderConcurrency SKIPPED (CI skip)
    # tests/integration/test_crud.py::TestCRUD PASSED
```

### Cross-References

**Related Patterns:**
- **Pattern 21 (Validation-First Architecture):** Stress tests are part of comprehensive validation
- **Pattern 13 (Test Coverage Quality):** Stress tests complement unit/integration tests
- **Pattern 27 (Dependency Injection):** DI enables mocking in stress tests

**Related Files:**
- `tests/stress/api_connectors/test_kalshi_client_stress.py` - Rate limiter stress tests
- `tests/stress/api_connectors/test_kalshi_auth_race.py` - Auth race condition tests
- `tests/stress/api_connectors/test_espn_rate_limits.py` - ESPN rate limit stress tests
- `tests/chaos/api_connectors/test_kalshi_client_chaos.py` - Chaos tests (run normally)

**Related Issues/PRs:**
- **PR #167:** Phase 1.9 Test Infrastructure - Added xfail markers to stress tests
- **PR #169:** Pattern 28 documentation (initial xfail approach)
- **GitHub Issue #168:** Testcontainers for database stress tests - evolved to skipif pattern
- **GitHub Issue #171:** Test isolation improvement (hybrid approach)

**Real-World Trigger & Evolution:**
- **Session 2025-12-05:** PR #167 CI jobs timing out after 10+ minutes
- **Root cause:** Stress tests with `threading.Barrier(20)`, `ThreadPoolExecutor`, and `time.perf_counter()` loops
- **Initial solution (PR #167):** Added `xfail(run=False)` to stress tests
- **Evolution (Issue #168):** Changed to `skipif(_is_ci)` for cleaner semantics (XFAIL→SKIPPED)
- **Enhancement (Issue #168):** Added testcontainers for database stress test isolation
- **Result:** CI completes in ~14 seconds for stress tests (all skipped), functional tests run normally

---

## Pattern 29: Hybrid Test Isolation Strategy (ALWAYS for Database Tests)

### Why This Pattern Exists

**The Problem: Test Pollution**

Database tests can fail when run in different orders due to:
- **Stale data:** Previous tests leave data that affects assertions (e.g., `assert count == 1` fails when count == 5)
- **Foreign key violations:** Tests assume empty tables but find existing data
- **SCD Type 2 pollution:** Historical records accumulate across tests

**Traditional Solutions (and their costs):**
| Approach | Overhead/Test | 500 Tests | Problems |
|----------|---------------|-----------|----------|
| DELETE cleanup | 50-500ms | 25-250s | Slow, fragile FK ordering |
| Truncate tables | 20-100ms | 10-50s | Locks, FK ordering |
| Fresh container/test | 10-15s | 1.4-2 hours | Way too slow |

**The Solution: Hybrid 3-Layer Isolation**

| Layer | Mechanism | Overhead | Use Case |
|-------|-----------|----------|----------|
| **Layer 1** | Transaction rollback | ~0ms | 90% of tests (unit, integration) |
| **Layer 2** | Pre-push phase separation | ~5s/reset | Test category boundaries |
| **Layer 3** | Testcontainers | ~15s/container | Stress tests, connection pool exhaustion |

### Layer 1: Transaction Rollback (Default - ~0ms)

**How it works:**
```
BEGIN TRANSACTION  (test start)
  INSERT INTO markets...
  UPDATE positions...
  SELECT * FROM trades...  (assertions)
ROLLBACK  (test end - instant, no disk I/O)
```

**Fixtures provided:**

```python
# tests/fixtures/transaction_fixtures.py

@pytest.fixture
def db_transaction() -> Generator[psycopg2.extensions.cursor, None, None]:
    """
    Provide database cursor with automatic transaction rollback.

    Every test using this fixture runs in an isolated transaction
    that is ALWAYS rolled back, regardless of test success/failure.
    """
    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

    try:
        yield cursor
    finally:
        conn.rollback()  # ALWAYS rollback - instant cleanup
        cursor.close()
        release_connection(conn)


@pytest.fixture
def db_transaction_with_setup(db_transaction):
    """Transaction with standard test data pre-loaded."""
    cursor = db_transaction

    # Create test fixtures inside transaction (auto-rolled-back)
    cursor.execute("""
        INSERT INTO platforms (platform_id, ...) VALUES ('test_platform', ...)
        ON CONFLICT (platform_id) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO strategies (strategy_id, ...) VALUES (99901, ...)
        ON CONFLICT (strategy_id) DO NOTHING
    """)

    yield cursor
    # No cleanup needed - transaction rolled back by parent fixture


@pytest.fixture
def db_savepoint(db_transaction):
    """Provide nested savepoints for sub-test isolation."""
    cursor = db_transaction

    class SavepointManager:
        def create(self, name: str) -> str:
            cursor.execute(f"SAVEPOINT {name}")
            return name

        def rollback_to(self, name: str) -> None:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {name}")

    yield cursor, SavepointManager()
```

**Usage:**

```python
# ✅ CORRECT: Test with automatic isolation
def test_create_market(db_transaction):
    cursor = db_transaction
    cursor.execute("INSERT INTO markets ...")
    cursor.execute("SELECT COUNT(*) FROM markets")
    assert cursor.fetchone()["count"] == 1
    # Test ends -> ROLLBACK -> market doesn't exist in DB


# ✅ CORRECT: Test with pre-loaded fixtures
def test_create_position(db_transaction_with_setup):
    cursor = db_transaction_with_setup
    # test_platform, 99901 strategy already exist
    cursor.execute("INSERT INTO positions ...")


# ✅ CORRECT: Nested isolation with savepoints
def test_rollback_behavior(db_savepoint):
    cursor, savepoints = db_savepoint

    sp1 = savepoints.create("before_insert")
    cursor.execute("INSERT INTO markets ...")

    # Rollback to savepoint
    savepoints.rollback_to(sp1)

    cursor.execute("SELECT COUNT(*) FROM markets")
    assert cursor.fetchone()["count"] == 0  # Insert was rolled back
```

**When NOT to use transaction rollback:**
- Tests that verify COMMIT behavior
- Tests spanning multiple connections (multi-process)
- Tests that intentionally test rollback
- Stress tests that exhaust connection pools

### Layer 2: Pre-Push Phase Separation (Test Boundaries)

**How it works:**

The pre-push hook runs tests in 4 phases with database resets between them:

```bash
# .git/hooks/pre-push (excerpt)

reset_database() {
    cd src/precog/database
    alembic downgrade base >/dev/null 2>&1
    alembic upgrade head >/dev/null 2>&1
}

# Phase A: Unit Tests (parallel, no DB)
python -m pytest tests/unit/ --no-cov -n auto

# Phase B: Integration + E2E Tests
python -m pytest tests/integration/ tests/e2e/ --no-cov -p no:xdist
reset_database

# Phase C: Property Tests
python -m pytest tests/property/ --no-cov -p no:xdist
reset_database

# Phase D: Remaining DB Tests
python -m pytest tests/security/ tests/stress/ tests/chaos/ --no-cov -p no:xdist
```

**Why phase separation?**
- Property tests generate thousands of edge cases -> pollution accumulates
- Integration tests use VCR cassettes with specific data expectations
- Stress tests push connection limits -> need clean pool state

### Layer 3: Testcontainers (Complete Isolation)

**When to use:**
- Stress tests that exhaust connection pools
- Tests requiring specific PostgreSQL configuration (max_connections)
- Tests that intentionally corrupt database state

**Fixture:**

```python
# tests/fixtures/stress_testcontainers.py

@pytest.fixture(scope="session")
def _stress_postgres_container_session():
    """Session-scoped container - started once per test session."""
    if _is_ci:
        # CI uses service container (already running)
        yield get_ci_connection_params()
        return

    # Local: Use testcontainers
    container = PostgresContainer(
        image="postgres:15",
        username="stress_user",
        password="stress_password",
        dbname="stress_test_db",
    ).with_command("postgres -c max_connections=200")

    with container:
        # Apply migrations once
        _apply_full_schema(container)
        yield get_container_params(container)


@pytest.fixture
def stress_postgres_container(_stress_postgres_container_session):
    """Per-test fixture with pool reset for isolation."""
    close_pool()
    initialize_pool()
    yield _stress_postgres_container_session
    close_pool()
```

### Decision Tree: Which Layer to Use

```
Is this a stress test or connection pool test?
├─ YES -> Layer 3 (testcontainers)
└─ NO
   ├─ Does test need to verify COMMIT behavior?
   │  ├─ YES -> Use db_cursor_commit fixture (no rollback)
   │  └─ NO -> Layer 1 (transaction rollback)
   └─ Does test span multiple connections?
      ├─ YES -> Layer 3 (testcontainers)
      └─ NO -> Layer 1 (transaction rollback)
```

### Performance Comparison

| Approach | 500 Unit Tests | 50 Integration | 20 Stress |
|----------|----------------|----------------|-----------|
| DELETE cleanup | 125s overhead | 25s overhead | 10s overhead |
| Transaction rollback | ~0s overhead | ~0s overhead | N/A |
| Testcontainers | N/A | N/A | 15s startup, 0s/test |
| **Hybrid (this pattern)** | ~0s | ~10s (2 resets) | 15s |

**Total hybrid overhead:** ~25s vs ~160s for DELETE-only approach

### Common Mistakes

```python
# ❌ WRONG: Test calls commit() - breaks transaction isolation
def test_with_commit(db_transaction):
    cursor = db_transaction
    cursor.execute("INSERT INTO markets ...")
    cursor.connection.commit()  # BAD! Data persists after test

# ✅ CORRECT: Let fixture handle transaction lifecycle
def test_without_commit(db_transaction):
    cursor = db_transaction
    cursor.execute("INSERT INTO markets ...")
    # No commit - fixture rolls back automatically


# ❌ WRONG: Using xfail to hide isolation problems
@pytest.mark.xfail(reason="Flaky due to database state")
def test_count_markets(db_cursor):
    ...

# ✅ CORRECT: Use proper isolation
def test_count_markets(db_transaction):
    cursor = db_transaction
    cursor.execute("INSERT INTO markets ...")  # Start fresh
    cursor.execute("SELECT COUNT(*) ...")
    assert cursor.fetchone()["count"] == 1  # Always passes
```

### Cross-References

- **GitHub Issue #171:** Implement hybrid test isolation strategy
- **ADR-057:** Testcontainers for Database Test Isolation
- **Pattern 28:** CI-Safe Stress Testing (skipif for threading tests)
- **tests/fixtures/transaction_fixtures.py:** Layer 1 implementation
- **tests/fixtures/stress_testcontainers.py:** Layer 3 implementation
- **.git/hooks/pre-push:** Layer 2 implementation (phase separation)

---

## Pattern 30: Stale Bytecode Cleanup (ALWAYS on pytest-xdist)

### Problem Statement

When test files are moved or deleted, Python's `__pycache__` directories retain stale `.pyc` bytecode files. pytest-xdist workers discover tests by scanning these cached bytecode files, leading to "phantom" test failures where pytest tries to run tests that no longer exist in their original location.

### Root Cause Discovery (Issue #171)

During implementation of hybrid test isolation, `tests/unit/fixtures/test_transaction_fixtures.py` was moved to `tests/integration/fixtures/` (because it uses the database). However, the bytecode cache remained:

```
tests/unit/fixtures/__pycache__/test_transaction_fixtures.cpython-314-pytest-8.4.2.pyc
```

This caused 6 test errors:
```
ERROR tests/unit/fixtures/test_transaction_fixtures.py::TestTransactionRollback::test_insert_data_in_transaction
E       fixture 'db_transaction' not found
```

The fixture wasn't found because:
1. pytest-xdist found the old `.pyc` file and tried to run those tests
2. The fixture imports only work in `tests/integration/` (due to conftest.py structure)
3. Result: Ghost tests that can't find their fixtures

### When This Happens

| Scenario | Result |
|----------|--------|
| Delete a test file | Ghost tests appear in pytest-xdist discovery |
| Move a test file | Tests discovered in BOTH old and new location |
| Rename a test file | Old name still appears in test collection |
| Refactor test structure | Stale tests with missing fixtures |

### Solution: Pre-Push Hook Bytecode Cleanup

Added Step 0.25 to pre-push hook (after branch check, before schema sync):

```bash
# Step 0.25: Clean Stale Bytecode (Pattern 30 - Prevents Ghost Tests)
echo "🧹 [0.25/11] Cleaning stale bytecode cache..."
find tests/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "✅ Bytecode cache cleaned"
```

### Why This Pattern Matters

**Without cleanup:**
```
$ git push
...
ERROR tests/unit/fixtures/test_transaction_fixtures.py::TestTransactionRollback::test_insert_data_in_transaction
E       fixture 'db_transaction' not found
# 6 errors, push blocked
```

**With cleanup:**
```
$ git push
🧹 [0.25/11] Cleaning stale bytecode cache...
✅ Bytecode cache cleaned
...
============================ 409 passed in 22.15s =============================
✅ All pre-push checks passed!
```

### Manual Cleanup Commands

If you encounter ghost tests outside of pre-push:

```bash
# Clean all test bytecode
find tests/ -type d -name "__pycache__" -exec rm -rf {} +

# Clean specific directory
rm -rf tests/unit/fixtures/__pycache__

# Clean entire project (more aggressive)
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Alternative: pytest cache clear (doesn't clean bytecode)
pytest --cache-clear  # Only clears pytest cache, NOT __pycache__
```

### Prevention Strategies

1. **Pre-push hook cleanup** (automatic, implemented in Step 0.25)
2. **Git hooks on checkout** (could add to post-checkout hook)
3. **pytest-xdist with `--forked`** (slower but creates fresh processes)
4. **Avoid moving test files** (refactor in place when possible)

### Implementation Details

**Why find + rm works:**
- `find tests/ -type d -name "__pycache__"` finds all cache directories
- `-exec rm -rf {} +` removes them in batch (faster than xargs)
- `2>/dev/null || true` ignores "directory not found" errors (already deleted)

**Why pytest --cache-clear doesn't help:**
- pytest cache (`.pytest_cache/`) stores test result history
- Python bytecode cache (`__pycache__/`) stores compiled `.pyc` files
- These are different caches; only bytecode causes ghost tests

### Cross-References

- **GitHub Issue #171:** Root cause discovery during hybrid isolation implementation
- **Pattern 29:** Hybrid Test Isolation Strategy (moved test files trigger this)
- **pytest-xdist docs:** Worker processes discover tests from bytecode
- **.git/hooks/pre-push:** Step 0.25 implementation

---

## Pattern 31: Pre-Push Log Persistence (Quality of Life)

**Category:** Testing Infrastructure
**Introduced:** Phase 1.9 (Issue #174)
**Enforcement:** Pre-push hook automatically generates logs

### Problem

Pre-push hook test results are output to terminal only and lost after execution:
- Impossible to debug failed pushes after terminal is closed
- Unable to compare pre-push vs CI results retrospectively
- No historical data for test performance trends
- Cannot detect flaky tests without manual tracking

### Solution

Store pre-push test results persistently with both human-readable logs and machine-parseable JSON:

```
.pre-push-logs/
├── pre-push-20251207-105506.log   # Human-readable full output
├── pre-push-20251207-105506.json  # Machine-parseable summary
├── pre-push-20251207-143022.log
├── pre-push-20251207-143022.json
└── ...
```

### Implementation

The pre-push hook (`.git/hooks/pre-push`) automatically:
1. Captures start time for duration calculation
2. Saves full output to timestamped `.log` file
3. Generates `.json` summary with test counts and failed tests
4. Stores both files in `.pre-push-logs/` (gitignored)

**JSON Summary Format:**
```json
{
    "timestamp": "2025-12-07T10:55:06-05:00",
    "branch": "feature/my-feature",
    "success": true,
    "duration_seconds": 185,
    "total_passed": 1320,
    "total_failed": 0,
    "total_skipped": 2,
    "phases": {
        "Phase A (Unit)": {"passed": 409, "failed": 0, "skipped": 0},
        "Phase B (Integration)": {"passed": 341, "failed": 0, "skipped": 1},
        "Phase C (Property)": {"passed": 110, "failed": 0, "skipped": 0},
        "Phase D (Other)": {"passed": 460, "failed": 0, "skipped": 1}
    },
    "failed_tests": [],
    "log_file": "/path/to/.pre-push-logs/pre-push-20251207-105506.log"
}
```

### Analysis Script

Use `scripts/analyze_test_history.py` to analyze historical test results:

```bash
# Show last 10 runs
python scripts/analyze_test_history.py

# Show last N runs
python scripts/analyze_test_history.py --last 5

# Show detailed view with per-phase breakdown
python scripts/analyze_test_history.py --detailed

# Export to JSON for external analysis
python scripts/analyze_test_history.py --json

# Show only flaky tests
python scripts/analyze_test_history.py --flaky
```

**Example Output:**
```
Test Result Trends (last 10 runs)
=================================
Total Runs: 10
Pass Rate: 100.0%
Average Duration: 152.3s

Phase Breakdown:
  Phase A (Unit):        409/409 (100%) - avg 22.1s
  Phase B (Integration): 341/341 (100%) - avg 31.2s
  Phase C (Property):    110/110 (100%) - avg 30.5s
  Phase D (Other):       460/460 (100%) - avg 68.5s

Flaky Tests (passed sometimes, failed others):
  - None detected
```

### Benefits

1. **Debugging:** Review failed pre-push output after terminal is closed
2. **Trend Analysis:** Track test performance over time
3. **Flaky Detection:** Identify tests that pass sometimes and fail others
4. **CI Comparison:** Compare local pre-push results with CI failures
5. **Duration Tracking:** Monitor for test suite performance regressions

### Cross-References

- **GitHub Issue #174:** Feature request and implementation
- **Pattern 29:** Hybrid Test Isolation (generates the logs being persisted)
- **Pattern 30:** Stale Bytecode Cleanup (another pre-push step)
- **.git/hooks/pre-push:** Log generation implementation
- **scripts/analyze_test_history.py:** Analysis script

---

## Pattern Quick Reference

| Pattern | Enforcement | Key Command | Related ADR/REQ |
|---------|-------------|-------------|-----------------|
| **1. Decimal Precision** | Pre-commit hook (decimal-precision-check) | `git grep "float(" -- '*.py'` | ADR-002, REQ-SYS-003 |
| **2. Dual Versioning** | Code review | `python scripts/validate_schema_consistency.py` | ADR-018, ADR-019, ADR-020 |
| **3. Trade Attribution** | Code review | Manual verification | REQ-TRADE-001 |
| **4. Security** | Pre-commit hook (detect-private-key) | `git grep -E "password\s*=" -- '*.py'` | REQ-SEC-001 |
| **5. Cross-Platform** | Manual (code review) | `git grep -E "print\(.*[✅❌🔵]" -- '*.py'` | ADR-053 |
| **6. TypedDict** | Mypy (pre-push hook) | `python -m mypy .` | ADR-048, REQ-API-007 |
| **7. Educational Docstrings** | Code review | Manual verification | N/A |
| **8. Config Synchronization** | Manual (4-layer checklist) | `python scripts/validate_docs.py` | Pattern 8 checklist |
| **9. Warning Governance** | Pre-push hook (Step 5/5) | `python scripts/check_warning_debt.py` | ADR-054 |
| **10. Property Testing** | Pytest (pre-push hook) | `pytest tests/property/ -v` | ADR-074, REQ-TEST-008 |
| **11. Test Mocking** | Code review | `git grep "return_value\.load" tests/` | PR #19, PR #20 |
| **12. Test Fixture Security** | Code review | `git grep "tmp_path.*\.sql" tests/` | PR #79, PR #76, CWE-22 |
| **13. Test Coverage Quality** | Code review + test checklist | `git grep "@patch.*get_connection" tests/` | REQ-TEST-012 thru REQ-TEST-019, TDD_FAILURE_ROOT_CAUSE |
| **14. Schema Migration → CRUD** | Manual (5-step checklist) | `git log -- src/precog/database/migrations/` | ADR-089, ADR-034, ADR-003, Pattern 13 |
| **15. Trade/Position Attribution** | Code review + pytest | `pytest tests/test_attribution.py -v` | ADR-090, ADR-091, ADR-092, Migration 018-020 |
| **16. Type Safety (YAML/JSON)** | Mypy (pre-push hook) | `git grep "yaml.safe_load" -- '*.py'` | Pattern 6, Mypy no-any-return, Ruff TC006 |
| **17. Avoid Nested Ifs** | Ruff (pre-commit hook) | `git grep -A2 "if.*:" -- '*.py' \| grep -A1 "if.*:"` | Ruff SIM102 |
| **18. Avoid Technical Debt** | Manual (3-part workflow) | `gh issue list --label deferred-task` | GitHub Issue #101, PHASE_X_DEFERRED_TASKS.md |
| **19. Hypothesis Decimal Strategy** | Hypothesis (pytest) | `git grep "decimals(min_value=" tests/property/` | Pattern 1, Pattern 10, ADR-074, SESSION 4.3 |
| **20. Resource Management** | Manual (code review) | `git grep "handler.close()" -- '*.py'` | Pattern 9, Pattern 12, SESSION 4.2 |
| **21. Validation-First Architecture** | Pre-commit + Pre-push hooks | `pre-commit run --all-files` | DEF-001, DEF-002, DEF-003, Pattern 1/4/9/18 |
| **22. VCR Pattern** | Pytest (integration tests) | `pytest tests/integration/api_connectors/test_kalshi_client_vcr.py` | ADR-075, REQ-TEST-013/014, GitHub #124, Pattern 1/13 |
| **23. Validation Failure Handling** | Manual (4-step protocol) | `git push` (pre-push hooks), `./scripts/validate_all.sh` | Pattern 21, Pattern 18, Pattern 9, Issue #127 |
| **24. No New Deprecated Code** | Code review | `git grep "DEPRECATED" -- '*.py'` | Pattern 6, Pattern 18 |
| **25. ANSI Escape Code Handling** | Code review + CI Windows matrix | `strip_ansi(result.stdout)` | Pattern 5, PR #159 |
| **26. Resource Cleanup** | Code review | `git grep "def close" -- '*.py'` | Pattern 20, Phase 1.9 |
| **27. Dependency Injection** | Code review | `git grep "= None" -- '*.py'` (constructor params) | Pattern 13, Phase 1.9 |
| **28. CI-Safe Stress Testing** | pytest markers (skipif) | `pytest tests/stress/ -v -m stress` (local only) | PR #167, Issue #168, ADR-057 |
| **29. Hybrid Test Isolation** | Transaction fixtures + pre-push phases | `db_transaction`, `db_transaction_with_setup`, `db_savepoint` | Issue #171, ADR-057, Pattern 28 |
| **30. Stale Bytecode Cleanup** | Pre-push hook (Step 0.25) | `find tests/ -type d -name "__pycache__" -exec rm -rf {} +` | Issue #171, Pattern 29, pytest-xdist |
| **31. Pre-Push Log Persistence** | Pre-push hook (automatic) | `python scripts/analyze_test_history.py` | Issue #174, Pattern 29/30 |
| **32. Windows Subprocess Pipe Deadlock** | File-based capture for large output | `tempfile.mkstemp()` + file I/O | Issue #238, Pattern 5, PR #240 |

---

## Pattern 32: Windows Subprocess Pipe Deadlock Prevention (ALWAYS for Large Output)

### The Problem

When using `subprocess.run()` with `capture_output=True` on Windows, the process can **deadlock indefinitely** when the subprocess produces more output than the pipe buffer can hold (~4KB on Windows, ~64KB on Linux).

```python
# WRONG - Can deadlock on Windows with large output
result = subprocess.run(
    "pytest tests/ -v",  # May produce 100KB+ of output
    capture_output=True,
    shell=True,
    timeout=600,
)
# If pytest output exceeds pipe buffer, this call HANGS FOREVER
# The timeout parameter DOES NOT help - deadlock occurs before timeout check
```

**Root Cause:**
1. `capture_output=True` creates OS pipes for stdout/stderr
2. Parent process waits for child to complete
3. Child process writes to pipe until buffer is full, then blocks waiting for parent to read
4. Parent is waiting for child → Child is waiting for parent → **DEADLOCK**

**Symptoms:**
- Pre-push hook hangs indefinitely with no output
- Subprocess.run() never returns despite having a timeout
- Works on small test suites but fails on large ones
- Works on Linux but fails on Windows (smaller pipe buffer)

### The Solution

Use **file-based capture** instead of pipe capture. Write subprocess output to temporary files, then read after completion:

```python
import os
import subprocess
import tempfile
from pathlib import Path


def run_subprocess_with_file_capture(
    command: str,
    timeout: int,
    cwd: str | Path,
) -> tuple[int, str, str, bool]:
    """
    Run a subprocess with file-based output capture to avoid Windows pipe deadlock.

    Args:
        command: Shell command to execute
        timeout: Maximum execution time in seconds
        cwd: Working directory for the subprocess

    Returns:
        Tuple of (exit_code, stdout, stderr, timed_out)

    Educational Note:
        Windows subprocess pipes have ~4KB buffer limits. When output exceeds this
        without being read, deadlock occurs. File-based capture avoids this by
        writing to disk instead of memory-limited pipes.
    """
    # Create temporary files for stdout and stderr using mkstemp
    # mkstemp returns (file_descriptor, path) - we close fd immediately
    # and reopen with proper encoding to avoid SIM115 lint error
    stdout_fd, stdout_path = tempfile.mkstemp(suffix=".stdout.txt", text=True)
    stderr_fd, stderr_path = tempfile.mkstemp(suffix=".stderr.txt", text=True)

    # Close the file descriptors immediately - we'll reopen with proper encoding
    os.close(stdout_fd)
    os.close(stderr_fd)

    try:
        # Open files for subprocess to write to
        with open(stdout_path, "w", encoding="utf-8") as stdout_f:
            with open(stderr_path, "w", encoding="utf-8") as stderr_f:
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        timeout=timeout,
                        cwd=str(cwd),
                        text=True,
                        env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    )
                    exit_code = result.returncode
                    timed_out = False
                except subprocess.TimeoutExpired:
                    exit_code = -1
                    timed_out = True

        # Read output from files AFTER subprocess completes
        with open(stdout_path, encoding="utf-8", errors="replace") as f:
            stdout = f.read()
        with open(stderr_path, encoding="utf-8", errors="replace") as f:
            stderr = f.read()

        return exit_code, stdout, stderr, timed_out
    finally:
        # Clean up temporary files
        try:
            os.unlink(stdout_path)
        except OSError:
            pass
        try:
            os.unlink(stderr_path)
        except OSError:
            pass
```

### When to Use This Pattern

| Scenario | Use File Capture? | Reasoning |
|----------|-------------------|-----------|
| Running pytest with many tests | ✅ YES | Can produce 100KB+ output |
| Running build tools (npm, pip) | ✅ YES | Verbose output possible |
| Simple status commands (git status) | ❌ NO | Output is small, pipe is fine |
| Any subprocess on Windows | ⚠️ Consider | Windows has smaller pipe buffers |
| Pre-push/pre-commit hooks | ✅ YES | Must handle worst-case output |

### Wrong vs. Correct

```python
# WRONG - Uses pipes, can deadlock on Windows with large output
def run_check(command: str, timeout: int) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        capture_output=True,  # ❌ Pipe-based capture
        shell=True,
        timeout=timeout,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# CORRECT - Uses file-based capture, handles any output size
def run_check(command: str, timeout: int) -> tuple[int, str, str, bool]:
    return run_subprocess_with_file_capture(command, timeout, Path.cwd())
```

### Implementation Notes

1. **Use `tempfile.mkstemp()`** instead of `NamedTemporaryFile` to avoid Ruff SIM115 lint errors
2. **Close file descriptors immediately** and reopen with `open()` for proper encoding handling
3. **Always clean up temp files** in a `finally` block
4. **Use `errors="replace"`** when reading output to handle encoding issues gracefully
5. **Set `PYTHONUNBUFFERED=1`** to ensure subprocess output is flushed immediately

### Related Files

- `scripts/run_parallel_checks.py` - Production implementation (PR #240)
- `tests/performance/` - Tests that produce large output

### Cross-References

- **Pattern 5:** Cross-Platform Compatibility (Windows/Linux)
- **Pattern 31:** Pre-Push Log Persistence
- **Issue #238:** CI test failure diagnostics


---

## Pattern 33: API Vocabulary Alignment (ALWAYS for External API Integration)

**Context:** When integrating with external APIs (Kalshi, ESPN, etc.), your database schema terminology may differ from the API's terminology. This creates unnecessary translation code and cognitive overhead.

**Problem:** Our original schema used internal terminology:
- Database constraint: `frequency IN ('single', 'recurring', 'continuous')`
- Kalshi API returns: `frequency: 'daily' | 'weekly' | 'event'`

This mismatch requires:
1. Translation code at the API boundary
2. Documentation explaining the mapping
3. Developers to learn two vocabularies
4. Potential for translation bugs

**Solution:** Adapt your schema to match the API vocabulary.

### The Pattern

1. **Identify vocabulary mismatch** during API integration
2. **Create migration** to update database constraints
3. **Update existing data** if needed (with mapping)
4. **Use API vocabulary** in all new code

### Implementation Example

**Migration 0011: Update frequency constraint**
```python
def upgrade() -> None:
    # Step 1: Drop old constraint
    op.execute("ALTER TABLE series DROP CONSTRAINT IF EXISTS series_frequency_check")

    # Step 2: Migrate existing data
    op.execute("UPDATE series SET frequency = 'event' WHERE frequency = 'single'")
    op.execute("UPDATE series SET frequency = 'daily' WHERE frequency IN ('recurring', 'continuous')")

    # Step 3: Add new constraint with API vocabulary
    op.execute("""
        ALTER TABLE series
        ADD CONSTRAINT series_frequency_check
        CHECK (frequency IN ('daily', 'weekly', 'monthly', 'event', 'once'))
    """)
```

### Decision Tree

| Scenario | Action |
|----------|--------|
| **API is authoritative source** | Adapt schema to API vocabulary |
| **Your schema is the standard** | Document and translate at boundary |
| **Multiple APIs with conflicts** | Create domain vocabulary, translate at each boundary |
| **Legacy data constraints** | Migrate data, then update constraint |

### When to Use This Pattern

- **USE for:** External API integrations (Kalshi, ESPN, etc.), any system where the external vocabulary is clearer, new tables without existing data

- **CONSIDER carefully for:** Tables with millions of rows (migration cost), published APIs others consume (breaking change)

- **AVOID for:** Internal-only systems with established vocabulary, when multiple APIs conflict on terminology

### Wrong vs. Correct

```python
# WRONG - Translation layer at boundary
def _sync_single_series(self, series_data: SeriesData) -> bool:
    # Translating API vocabulary to internal vocabulary
    frequency_map = {
        'daily': 'recurring',
        'weekly': 'recurring',
        'event': 'single',
    }
    db_frequency = frequency_map.get(series_data.get('frequency'), 'single')

    create_series(
        frequency=db_frequency,  # Using internal vocabulary
        ...
    )


# CORRECT - Schema matches API vocabulary
def _sync_single_series(self, series_data: SeriesData) -> bool:
    create_series(
        frequency=series_data.get('frequency'),  # Direct passthrough
        ...
    )
```

### Related Files

- `src/precog/database/alembic/versions/0011_update_series_frequency_constraint.py` - Migration example
- `src/precog/api_connectors/types.py` - TypedDict with API vocabulary
- `src/precog/schedulers/kalshi_poller.py` - Clean API integration

### Cross-References

- **Pattern 6:** TypedDict for API Responses
- **Pattern 8:** Configuration File Synchronization
- **Migration 0011:** First implementation of this pattern


---

## Pattern 34: Two-Layer Schema Architecture for Historical Data Seeding (ALWAYS for External Data)

**Priority:** 🔴 CRITICAL
**Applicability:** ALWAYS for tables that store data from external sources (CSV, APIs, web scraping)
**Implementation Requirement:** Design schema with dual identifiers from the start
**Introduced:** Phase 2.7 (Issue #273 - Comprehensive Elo Rating Computation Module)

### Why This Pattern Matters

When seeding historical data from external sources (FiveThirtyEight Elo, ESPN game results, betting odds CSVs), you face a chicken-and-egg problem:

1. **External data uses string identifiers** (team codes like "KC", "BUF", "LAL")
2. **Production queries need foreign keys** for efficient joins and referential integrity
3. **Team mappings may not exist** when you first load the historical data
4. **Different sources use different codes** ("KC" vs "KAN" vs "Kansas City")

### The Two-Layer Solution

Create tables with **both** identifier columns:

| Layer | Column | Type | Purpose |
|-------|--------|------|---------|
| **Seeding Layer** | `team_code` | VARCHAR(10) | Flexible external data loading (from CSV, APIs, scraped data) |
| **Production Layer** | `team_id` | INTEGER FK | Referential integrity, efficient joins, constraint enforcement |

### Key Design Decisions

1. **`team_code` is NOT NULL** - Required for data loading (source of truth from external data)
2. **`team_id` is NULLABLE** - Allows gradual backfill after team mappings are established
3. **Both columns coexist** - Neither replaces the other; they serve different purposes
4. **FK uses `ON DELETE SET NULL`** - Prevents cascading deletes from breaking historical records

### Implementation Across Historical Tables

| Table | Seeding Column(s) | Production FK(s) | Migration |
|-------|-------------------|------------------|-----------|
| `historical_elo` | `team_code` (V1.22: should add) | `team_id` NOT NULL | 0005 |
| `historical_games` | `home_team_code`, `away_team_code` | `home_team_id`, `away_team_id` | 0006 |
| `historical_odds` | `home_team_code`, `away_team_code` | `home_team_id`, `away_team_id` | 0007 + 0013 |
| `historical_epa` | `team_code` | `team_id` | 0013 |
| `historical_stats` | `team_code` | `team_id` | 0009 + 0013 |
| `historical_rankings` | `team_code` | `team_id` | 0009 + 0013 |
| `elo_calculation_log` | `home_team_code`, `away_team_code` | `home_team_id`, `away_team_id` | 0013 |

### Migration Example

**Adding team_id FK to existing table (Migration 0013):**

```python
def upgrade() -> None:
    """Add team_id FK columns to historical tables."""
    # Add nullable FK columns for gradual backfill
    op.add_column(
        "historical_odds",
        sa.Column(
            "home_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,  # Nullable for gradual backfill
            comment="FK to teams table for home team (backfill from home_team_code)",
        ),
    )
    op.add_column(
        "historical_odds",
        sa.Column(
            "away_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table for away team (backfill from away_team_code)",
        ),
    )

    # Create partial indexes (only for non-null values)
    op.create_index(
        "idx_historical_odds_home_team_id",
        "historical_odds",
        ["home_team_id"],
        postgresql_where=sa.text("home_team_id IS NOT NULL"),
    )
```

### Backfill Workflow

After team seed data exists, run a backfill to populate `team_id` from `team_code`:

```sql
-- Backfill team_id from team_code mapping
UPDATE historical_epa h
SET team_id = t.team_id
FROM teams t
WHERE h.team_code = t.abbreviation
  AND t.sport = h.sport
  AND h.team_id IS NULL;

-- Verify backfill coverage
SELECT
    COUNT(*) as total,
    COUNT(team_id) as with_fk,
    COUNT(*) - COUNT(team_id) as missing_fk
FROM historical_epa;
```

### Query Patterns

**During seeding (use team_code):**
```python
# Seeder doesn't need team_id - uses team_code for deduplication
def _upsert_epa_record(self, record: EPARecord, season: int) -> Literal["inserted", "updated", "skipped"]:
    team_code = record["team_code"]
    team_id = self._resolve_team_id(team_code)  # Optional FK resolution

    # Insert with both columns
    cur.execute("""
        INSERT INTO historical_epa (team_id, team_code, season, ...)
        VALUES (%s, %s, %s, ...)
    """, (team_id, team_code, season, ...))
```

**During production queries (use team_id for joins):**
```python
# Production queries use team_id for efficient joins
def get_team_epa_for_game(team_id: int, season: int, week: int) -> EPARecord:
    result = conn.execute(text("""
        SELECT e.*, t.name as team_name, t.conference
        FROM historical_epa e
        JOIN teams t ON e.team_id = t.team_id  -- Efficient FK join
        WHERE e.team_id = :team_id
          AND e.season = :season
          AND e.week = :week
    """), {"team_id": team_id, "season": season, "week": week})
```

### Code Mapping Between Layers

Create a mapping utility to translate between layers:

```python
def resolve_team_id(conn: Connection, team_code: str, sport: str = "nfl") -> int | None:
    """Resolve team code to team_id from teams table.

    Args:
        conn: Database connection
        team_code: Team abbreviation (e.g., "KC", "BUF")
        sport: Sport code (default "nfl")

    Returns:
        team_id if found, None otherwise

    Educational Note:
        This function bridges the two-layer architecture:
        - Input: team_code (seeding layer identifier)
        - Output: team_id (production layer FK)

        The mapping is established by the teams seed data, which
        must be loaded BEFORE calling this function.
    """
    result = conn.execute(
        text("""
            SELECT team_id FROM teams
            WHERE abbreviation = :team_code
              AND sport = :sport
            LIMIT 1
        """),
        {"team_code": team_code, "sport": sport},
    )
    row = result.fetchone()
    return row[0] if row else None
```

### Decision Tree

| Scenario | Recommended Approach |
|----------|---------------------|
| **New historical table** | Create with BOTH team_code AND team_id columns from the start |
| **Existing table without team_id** | Add team_id via migration, backfill after teams seeded |
| **External source with unknown codes** | Map to canonical codes first, then resolve to team_id |
| **Multiple sources with conflicting codes** | Create mapping table: `team_code_aliases(source, code, canonical_code)` |

### Wrong vs. Correct

```python
# WRONG - Using only team_id (can't load if teams don't exist)
op.create_table(
    "historical_epa",
    sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.team_id"), nullable=False),
    # ... Can't seed if teams table is empty!
)

# WRONG - Using only team_code (no referential integrity)
op.create_table(
    "historical_epa",
    sa.Column("team_code", sa.String(10), nullable=False),
    # ... No FK constraint, orphan records possible
)

# CORRECT - Two-layer architecture
op.create_table(
    "historical_epa",
    sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.team_id"), nullable=True),
    sa.Column("team_code", sa.String(10), nullable=False),
    # ... Flexible seeding + production integrity
)
```

### Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Making `team_id` NOT NULL | Can't seed before teams exist | Use `nullable=True`, backfill later |
| Omitting `team_code` | Lose external reference, can't debug source issues | Always keep original identifier |
| Using `ON DELETE CASCADE` | Historical data deleted when team is removed | Use `ON DELETE SET NULL` |
| Not indexing `team_code` | Slow seeding lookups | Add index on `(team_code, season)` |
| Backfilling before teams loaded | All records get NULL team_id | Seed teams first, then backfill |

### Related Files

- `src/precog/database/alembic/versions/0005_create_historical_elo_table.py` - Initial pattern
- `src/precog/database/alembic/versions/0006_create_historical_games_table.py` - Dual FK example
- `src/precog/database/alembic/versions/0013_add_epa_audit_and_team_fks.py` - Comprehensive FK additions
- `src/precog/database/seeding/epa_seeder.py` - `_resolve_team_id()` implementation
- `src/precog/database/seeding/historical_elo_loader.py` - Seeding with team_code

### Cross-References

- **Issue #273:** Comprehensive Elo Rating Computation Module (original trigger)
- **Pattern 33:** API Vocabulary Alignment (complementary - align vocabulary AND schema layers)
- **Pattern 13:** Test Coverage Quality (test both seeding and production query paths)
- **ADR-109:** Elo Computation Architecture (documents Elo-specific schema decisions)
- **Migration 0013:** First comprehensive application across multiple tables


---

## Pattern 35: CLI Test Isolation for Parallel Execution (ALWAYS for Typer CLI Tests)

**Status:** ✅ Production Pattern (PR #285)
**ADR:** ADR-120 (Pending)
**REQ:** REQ-TEST-020 (Pending)

### The Problem

When running CLI tests with pytest-xdist parallel execution, tests fail intermittently with:
```
ValueError: I/O operation on closed file
```

**Root Cause:** Typer CLI applications use a global `app` object. When tests run in parallel:
1. Worker A registers commands on global `app`
2. Worker B invokes CLI, writes to shared stdout
3. Worker A's test completes, closing stdout
4. Worker B tries to write → "I/O operation on closed file"

This is particularly insidious because:
- Tests pass when run sequentially (`pytest -n0`)
- Tests fail randomly with `-n auto` (parallel)
- Failure rate varies with CPU/scheduling timing

### The Solution

**Create fresh Typer app instances per test** using fixtures or helper functions.

#### For Standard pytest Tests: Use Fixtures

```python
# tests/integration/cli/test_cli_scheduler_integration.py

import pytest
import typer
from typer.testing import CliRunner


@pytest.fixture
def isolated_app():
    """Create a completely isolated Typer app for integration testing.

    This fixture creates a fresh app instance that doesn't share state with
    other tests, preventing race conditions during parallel execution.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestSchedulerStartIntegration:
    """Integration tests for scheduler start command."""

    def test_start_scheduler_with_valid_config(self, isolated_app) -> None:
        """Test starting scheduler with valid configuration."""
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "start", "--poller", "espn"])
            assert result.exit_code in [0, 1, 2]
```

#### For Hypothesis Property Tests: Use Helper Functions

Hypothesis tests cannot use pytest fixtures directly. Use a helper function instead:

```python
# tests/property/cli/test_cli_scheduler_properties.py

import typer
from hypothesis import given, strategies as st
from typer.testing import CliRunner


def get_fresh_cli() -> typer.Typer:
    """Create fresh CLI app for each property test execution.

    Hypothesis generates many test cases per test function. Each must get
    a fresh app to prevent state pollution between generated cases.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestSchedulerProperties:
    """Property-based tests for scheduler CLI."""

    @given(interval=st.integers(min_value=1, max_value=3600))
    def test_interval_always_positive(self, interval: int) -> None:
        """Property: Scheduler accepts any positive interval."""
        runner = CliRunner(mix_stderr=False)
        app = get_fresh_cli()  # Fresh app per generated case

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance

            result = runner.invoke(app, ["scheduler", "start", "--interval", str(interval)])
            assert result.exit_code in [0, 1, 2]
```

### Pattern Decision Matrix

| Test Type | Isolation Method | Why |
|-----------|------------------|-----|
| Unit tests (CLI) | `isolated_app` fixture | pytest fixtures work, cleaner syntax |
| Integration tests | `isolated_app` fixture | Same as unit tests |
| E2E tests | `isolated_app` fixture | Same as unit tests |
| Performance tests | `isolated_app` fixture (with `cli_runner` from conftest) | Reuse shared runner |
| Stress tests | `isolated_app` fixture | Each stress iteration gets fresh app |
| Property tests (Hypothesis) | `get_fresh_cli()` helper | Fixtures not supported by Hypothesis |

### Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Using global `app` import | Shared state between parallel workers | Create fresh app per test |
| Calling `register_commands()` at module level | Same as above | Move registration into fixture |
| Reusing `CliRunner` across tests | May carry state from previous invocations | Create fresh runner per test |
| Using fixture in Hypothesis test | Hypothesis can't inject fixtures | Use helper function instead |
| Not using `mix_stderr=False` | stderr mixes with stdout, harder to debug | Always set `mix_stderr=False` |

### Checklist for New CLI Tests

- [ ] Use `isolated_app` fixture (not global `app`)
- [ ] Create fresh `CliRunner(mix_stderr=False)` in each test
- [ ] For Hypothesis: use `get_fresh_cli()` helper function
- [ ] Verify tests pass with `pytest -n auto` (parallel)
- [ ] Verify tests pass with `pytest -n0` (sequential)

### Why This Pattern Matters

**Before pattern (random failures):**
```
FAILED tests/stress/cli/test_cli_stress.py::test_repeated_status_checks
  - ValueError: I/O operation on closed file
PASSED tests/stress/cli/test_cli_stress.py::test_repeated_status_checks  # Same test, different run!
```

**After pattern (consistent):**
```
PASSED tests/stress/cli/test_cli_stress.py::test_repeated_status_checks  # Always passes
```

### Related Files

- `tests/integration/cli/test_cli_scheduler_integration.py` - Integration test example
- `tests/property/cli/test_cli_scheduler_properties.py` - Property test example
- `tests/stress/cli/test_cli_stress.py` - Stress test example
- `tests/conftest.py` - Shared `cli_runner` fixture definition

### Cross-References

- **PR #285:** CLI test isolation implementation
- **Pattern 28:** CI-Safe Stress Testing (complementary - skip tests that hang in CI)
- **Pattern 29:** Hybrid Test Isolation Strategy (related - database isolation)
- **Pattern 30:** Stale Bytecode Cleanup (related - another parallel execution issue)


---

## Pattern 36: External ID Stability — Never Trust Short Codes (ALWAYS for Multi-Source Data)

**WHY:** External providers may use non-unique short codes across different contexts. ESPN uses 3-letter team codes (e.g., "OSU") that map to different teams in different leagues (Ohio State in NCAAF, Oregon State in other contexts). When polling multiple leagues, shared codes cause "ID thrashing" — the validator cycles between team records as different leagues report conflicting data for the same code.

**Discovered:** Soak test 2026-03-11, ESPN validator logged 97 NCAAF cycles due to shared team codes.

### The Problem

```python
# BAD: Short codes are not globally unique
team = get_team_by_code("OSU")  # Which OSU? Ohio State? Oregon State? Oklahoma State?

# GOOD: Always scope external IDs by provider + league
team = get_team_by_espn_id(espn_team_id="194", league="ncaaf")  # Unambiguous
```

### Rules

1. **Always use provider-specific full IDs** (ESPN numeric ID, not abbreviation) for lookups
2. **Always scope by league** when querying teams — `(espn_team_id, league)` is the correct composite key
3. **Never assume short codes are unique** across leagues or even within a league over time
4. **Validate at ingestion** — the ESPN validator (`espn_team_validator.py`) handles disambiguation internally, but downstream code must use the resolved `team_id`, not the raw abbreviation

### Database Constraint

Migration 0017 enforces this at the schema level:
```sql
-- Partial unique index: (espn_team_id, league) WHERE espn_team_id IS NOT NULL
CREATE UNIQUE INDEX ix_teams_espn_team_id_league
    ON teams (espn_team_id, league)
    WHERE espn_team_id IS NOT NULL;
```

### Generalization

This pattern applies to ANY external data source, not just ESPN:
- Kalshi ticker formats may change or be reused across seasons
- Balldontlie player IDs may not be stable across API versions
- Any provider's "short name" or "abbreviation" field is suspect

**Rule of thumb:** If you didn't generate the ID, don't trust its uniqueness without scoping.

### Related

- `src/precog/api_connectors/espn_team_validator.py` — ESPN ID disambiguation logic
- `src/precog/database/crud_operations.py:get_team_by_espn_id()` — Correct lookup pattern (scoped by league)
- Migration 0017 — `(espn_team_id, league)` partial unique constraint
- Issue #342 — Documentation trigger for this pattern

---

## Pattern 37: Settled Market Price Semantics (ALWAYS for Backtesting)

**WHY:** Kalshi markets show `yes_price=1.0` AND `no_price=1.0` after settlement. This is not a data error — it's Kalshi's post-settlement marker. If backtesting code queries `WHERE row_current_ind = TRUE` on settled markets, it gets settlement markers instead of the last trading prices.

**Discovered:** Data quality analysis 2026-03-11 found 69% of settled markets have both prices at 1.0.

### The Problem

```python
# BAD: Gets settlement marker (1.0/1.0), not last trading price
market = get_current_market("KXNFLGAME-KC-BUF-YES")
last_price = market['yes_price']  # Decimal('1.0000') — settlement marker, NOT last trade

# GOOD: Query SCD history for actual price movement
history = get_market_history("KXNFLGAME-KC-BUF-YES")  # All SCD versions
last_trading_price = history[-2]['yes_price']  # Second-to-last row = last pre-settlement price
```

### Rules

1. **For current state queries** (is market open? what's the current price?): Use `row_current_ind = TRUE` — works correctly for active markets
2. **For backtesting / model training**: Query ALL SCD versions and filter out the final settlement row (`yes_price = 1.0 AND no_price = 1.0 AND status = 'settled'`)
3. **For price change analysis**: Use historical SCD rows ordered by `row_start_ts`
4. **Settlement detection**: A market is settled when `status = 'settled'` — the 1.0/1.0 prices are a secondary indicator

### Related

- `src/precog/database/crud_operations.py:get_current_market()` — Documented with settlement warning
- Issue #315 — Original discovery
- Phase 4 (Model Training) — Must handle this correctly in training data pipelines

---

## Related Documentation

### Foundation Documents
- `docs/foundation/MASTER_REQUIREMENTS_V2.25.md` - All requirements
- `docs/foundation/ARCHITECTURE_DECISIONS_V2.35.md` - All ADRs (includes ADR-002, ADR-018-020, ADR-048, ADR-053-054, ADR-074)
- `docs/foundation/DEVELOPMENT_PHASES_V1.8.md` - Phase planning

### Implementation Guides
- `docs/guides/VERSIONING_GUIDE_V1.0.md` - Pattern 2 detailed implementation
- `docs/guides/CONFIGURATION_GUIDE_V3.1.md` - YAML configuration (Pattern 8)
- `docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` - Pattern 1 quick reference

### Validation & Testing
- `docs/foundation/TESTING_STRATEGY_V2.0.md` - Comprehensive testing infrastructure
- `docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md` - Pattern 10 roadmap
- `scripts/validate_docs.py` - Pattern 5 sanitization example
- `scripts/validate_schema_consistency.py` - Pattern 1 & 2 validation
- `scripts/check_warning_debt.py` - Pattern 9 automation

### Security & Quality
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md` - Pattern 4 detailed checklist
- `docs/utility/WARNING_DEBT_TRACKER.md` - Pattern 9 tracking
- `scripts/warning_baseline.json` - Pattern 9 baseline

## Pattern 38: Surrogate PK Migration Dependency Ordering (ALWAYS for PK Changes)

**When:** Writing any Alembic migration that changes a PRIMARY KEY, drops a column, or renames a column.

**Pattern:** Before modifying a table's PK or columns, enumerate and handle three classes of hidden dependencies:

### Class 1: Foreign Key Constraints

PostgreSQL won't let you drop a PK that has FKs referencing it — even on an empty table.

```sql
-- WRONG: Drop PK first (fails if any FK references it)
ALTER TABLE series DROP CONSTRAINT series_pkey;  -- ❌ DependentObjectsStillExist

-- CORRECT: Drop dependent FKs first, then PK
ALTER TABLE events DROP CONSTRAINT IF EXISTS events_series_id_fkey;  -- Step 1
ALTER TABLE series DROP CONSTRAINT series_pkey;  -- Step 2 (safe now)
```

**Discovery query:**
```sql
SELECT conname, conrelid::regclass AS referencing_table
FROM pg_constraint
WHERE confrelid = 'your_table'::regclass AND contype = 'f';
```

### Class 2: Views (SELECT * Binding)

Views created with `SELECT *` bind to specific columns at creation time. Dropping a column that a view references fails with `DependentObjectsStillExist`.

```sql
-- WRONG: Drop column directly (fails if view uses it)
ALTER TABLE markets DROP COLUMN event_id;  -- ❌ view current_markets depends on it

-- CORRECT: Drop view, drop column, recreate view
DROP VIEW IF EXISTS current_markets CASCADE;
ALTER TABLE markets DROP COLUMN event_id;
CREATE OR REPLACE VIEW current_markets AS SELECT * FROM markets WHERE row_current_ind = TRUE;
```

**Discovery query:**
```sql
SELECT viewname FROM pg_views WHERE definition LIKE '%your_table%';
```

### Class 3: Test Mock Contracts

When a function's return type changes (e.g., `str` → `int`, or `str` → `tuple[int, bool]`), mocks without explicit `return_value` return `MagicMock`. This silently passes tuple unpacking (`a, b = mock()` creates child mocks) but produces wrong types downstream.

```python
# WRONG: MagicMock auto-creates children on unpack — silently wrong types
patch("module.get_or_create_event")  # Returns MagicMock, not (int, bool)

# CORRECT: Always match the real return type
patch("module.get_or_create_event", return_value=(1, True))
```

**Discovery command:** After changing any function's return type, search all test files:
```bash
grep -rn "get_or_create_event" tests/ | grep -v "return_value"
```

### Backfill Step (Data Preservation)

Even on "clean" databases, always include a backfill step when migrating FK columns. The test database isn't clean — it has data from previous test runs.

```sql
-- Step 7: Add new integer FK column
ALTER TABLE events ADD COLUMN series_internal_id INTEGER;

-- Step 8: Backfill from old VARCHAR column (costs nothing on empty table)
UPDATE events e SET series_internal_id = s.id FROM series s WHERE e.series_id = s.series_id;

-- Step 9: Add FK constraint on new column
ALTER TABLE events ADD CONSTRAINT fk_events_series_internal
FOREIGN KEY (series_internal_id) REFERENCES series(id) ON DELETE SET NULL;

-- Step 10: Drop old column (safe now — data preserved in new column)
ALTER TABLE events DROP COLUMN series_id;
```

### Migration Step Template (11 Steps)

For any surrogate PK migration with downstream FK changes:

1. **Drop dependent FKs** (from child tables referencing our PK)
2. **Add SERIAL id column** (auto-assigns IDs to existing rows)
3. **Drop old PK constraint**
4. **Add new PK on id**
5. **Add UNIQUE on old PK column** (becomes business key)
6. **Add UNIQUE(platform_id, external_id)** (multi-platform support)
7. **Add new integer FK column** on child table
8. **Backfill** new FK from old VARCHAR via JOIN
9. **Add FK constraint** on new integer column
10. **Drop views, drop old column** on child table, recreate views
11. **Add index** on new FK column

### Checklist (Before Writing Migration)

- [ ] Run discovery queries for FK constraints and views
- [ ] Verify step ordering: FKs dropped before PK, views dropped before columns
- [ ] Include backfill step (even for "clean" DBs)
- [ ] Include view drop/recreate around column drops
- [ ] Write full downgrade with reverse backfill
- [ ] After migration: grep all test files for changed function signatures and mock contracts

### Real-World Triggers

- **Migration 0019 (series_surrogate_pk):** FK constraint blocked PK drop. Fixed by reordering.
- **Migration 0020 (events_surrogate_pk):** `current_markets` view blocked column drop. Fixed by drop/recreate.
- **Both migrations:** 15+ test mocks needed `return_value` updates for changed return types.

**References:**
- PostgreSQL docs: [ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)
- Migration 0019: `src/precog/database/alembic/versions/0019_series_surrogate_pk.py`
- Migration 0020: `src/precog/database/alembic/versions/0020_events_surrogate_pk.py`
- Feedback memory: `memory/feedback_migration_dependencies.md`

---

## Pattern 39: Verify External API Data Before Building Parsers (ALWAYS for External Data Parsing)

**Severity:** CRITICAL — Wrong assumptions about data format waste hours of implementation effort

### Problem

Test fixtures and docstrings may not match real API data. Building parsers against
assumed formats leads to code that works in tests but fails against production data.

### Real-World Trigger

Session 23 (#462): Test fixtures showed Kalshi event_ticker format as `KXNFLGAME-25DEC15`
(date only, no team codes). Docstrings showed `KXNFLGAME-25OCT05-NEBUF` (with teams).
The real Kalshi API returns `KXNFLGAME-26JAN18HOUNE` (team codes concatenated without
delimiters, variable-length 2-4 chars). If we had built a parser from the fixture format,
it would have been fundamentally wrong — matching 0% of real events.

### Pattern

Before building any logic that parses external API data:

1. **Hit the real API** — even a single request reveals the actual format
2. **Collect multiple examples** — across different sports/leagues/types to see variations
3. **Compare against fixtures** — if they disagree, the API wins
4. **Document the real format** — update fixtures and docstrings to match reality

```bash
# Example: Verify Kalshi event_ticker format (took 30 seconds, saved hours)
curl -s "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNFLGAME&limit=5" \
  | python -c "import json,sys; [print(m['event_ticker']) for m in json.load(sys.stdin)['markets']]"
```

### When to Apply

- Building ticker/code parsers for external platforms
- Implementing data validation against external API responses
- Writing seed data that represents external API structure
- Any time a test fixture claims to represent external API data

### Anti-Pattern

```python
# WRONG: Trust the test fixture / docstring
# tests/fixtures/api_responses.py says event_ticker = "KXNFLGAME-25DEC15"
# So we build a parser for {SERIES}-{DATE} format...

# CORRECT: Verify against real API first
# Real API returns "KXNFLGAME-26JAN18HOUNE" — completely different format!
# Now build parser for {SERIES}-{DATE}{AWAY}{HOME} format
```

**References:**
- Issue #467 (fix test fixtures to match real API)
- `src/precog/matching/ticker_parser.py` (parser built from verified API data)

---

## Pattern 40: Use execute_values Over executemany for Batch Upserts (ALWAYS for Batch INSERT/UPSERT)

**Severity:** HIGH — `executemany` silently returns wrong rowcount, corrupting monitoring data

### Problem

`psycopg2.cursor.executemany()` executes each row as a separate statement. After
completion, `cursor.rowcount` reflects only the **last** statement's result — not
the sum of all executions. For `ON CONFLICT DO NOTHING` batches, this means the
reported count is 0 or 1, never the actual number of inserted rows.

### Real-World Trigger

Session 23 (#469 audit): Glokta found that `upsert_market_trades_batch()` returned
`cur.rowcount` after `executemany()`. If 100 trades were submitted with 3 duplicates,
the function returned 1 (or 0) instead of 97. Any monitoring or reconciliation using
this count was silently incorrect. The bug had been in production since session 17
(6 sessions undetected).

### Pattern

```python
# WRONG: executemany + rowcount — returns LAST row's count only
cur.executemany(
    "INSERT INTO trades (...) VALUES (%s, %s) ON CONFLICT DO NOTHING",
    batch_params,
)
inserted = cur.rowcount  # BUG: returns 0 or 1, not actual count

# CORRECT: execute_values — returns aggregate rowcount
from psycopg2.extras import execute_values

execute_values(
    cur,
    "INSERT INTO trades (...) VALUES %s ON CONFLICT DO NOTHING",
    batch_params,
)
inserted = cur.rowcount  # Correct: returns actual rows affected
```

### Key Differences

| Feature | `executemany()` | `execute_values()` |
|---------|----------------|-------------------|
| Execution | One statement per row | Single multi-row INSERT |
| `rowcount` | Last row only | Aggregate total |
| Performance | N round trips | 1 round trip |
| ON CONFLICT | Correct behavior, wrong count | Correct behavior, correct count |

### When to Apply

- Any batch INSERT or UPSERT in CRUD code
- Any function that returns a count of rows affected after batch operations
- Any monitoring/alerting that relies on batch insert counts

### Validation Pattern

Always add count validation before batch operations:

```python
def upsert_batch(items: list[dict]) -> int:
    for item in items:
        if item["count"] <= 0:
            raise ValueError(f"count must be > 0, got {item['count']}")
    # ... execute_values ...
```

**References:**
- Issue #472 (executemany rowcount bug)
- psycopg2 docs: [execute_values](https://www.psycopg.org/docs/extras.html#psycopg2.extras.execute_values)
- `src/precog/database/crud_operations.py` (upsert_market_trades_batch)

---

### Code Examples
- `api_connectors/types.py` - Pattern 6 (17 TypedDict examples)
- `api_connectors/kalshi_auth.py` (lines 41-162) - Pattern 7 (excellent docstring examples)
- `tests/property/test_kelly_criterion_properties.py` - Pattern 10 (11 property tests)
- `tests/property/test_edge_detection_properties.py` - Pattern 10 (16 property tests)

---

## Pattern 41: Production-Readiness Checklist (ALWAYS for New Modules/Features)

**Severity:** HIGH — Modules without production infrastructure are invisible to operators and cannot self-recover

### Problem

Modules ship with functional correctness (tests pass, logic works) but zero production visibility. When they fail in production, operators can't see what's happening, can't manually intervene, and the system can't self-recover. The matching module (#462) had 98 tests but no monitoring, no CLI commands, no self-healing — it was a black box.

### Pattern: Every Production Module Ships with 7 Capabilities

| Capability | What It Means | Checklist |
|-----------|---------------|-----------|
| **Monitoring** | Categorized metrics with per-entity breakdowns | Failure reason enum, per-league/per-entity stats, health integration |
| **Alerts** | Threshold-triggered notifications that demand operator attention | Circuit breaker trips, data freshness violations, error rate escalation, configurable thresholds |
| **Maintenance** | CLI commands for manual intervention | `precog data <module> stats`, `<module> refresh`, `<module> backfill` |
| **Logging** | Operator-readable output with actionable context | Summary counts at INFO, details at DEBUG, errors with remediation hints |
| **Reporting** | Stats visible in system_health + CLI + future dashboards | Health metrics in system_health JSONB, CLI table output |
| **Self-healing** | Automatic recovery from transient failures | Cache refresh on unknown entities, backfill retries, rate-limited recovery |
| **Scheduling** | Rate-limited periodic operations | Don't run expensive checks every cycle — use interval counters |

**Alerts vs Logging vs Reporting (clear separation):**
- **Logging** = what happened (passive record for debugging)
- **Reporting** = how things look (periodic stats for dashboards)
- **Alerts** = something is WRONG and needs attention NOW (active notification that triggers operator response)

An alert has: a **trigger condition** (threshold exceeded), a **severity** (warning/critical), a **mechanism** (circuit breaker trip, log at CRITICAL, future: Slack/email), and a **remediation hint** ("Kalshi poll overdue >60s — check API status or restart poller").

### Template (from #477 — Matching Module, expanded with Alerts)

```python
# 1. MONITORING: Categorized failure tracking
class MatchReason(str, Enum):
    MATCHED = "matched"
    PARSE_FAIL = "parse_fail"
    NO_CODE = "no_code"
    NO_GAME = "no_game"

# 2. ALERTS: Threshold-triggered operator notifications
def _check_alert_conditions(self) -> None:
    """Evaluate alert thresholds after each poll cycle."""
    # Data freshness alert
    if self._seconds_since_last_success > self.poll_interval * 2:
        logger.critical(
            "[ALERT] %s poll overdue by %ds — check API status or restart poller",
            self.name, self._seconds_since_last_success,
        )
        self._trip_circuit_breaker("data_stale", f"{self.name} overdue")

    # Error rate escalation
    if self._error_rate_pct > 10.0:
        logger.critical(
            "[ALERT] %s error rate %.1f%% exceeds 10%% threshold",
            self.name, self._error_rate_pct,
        )

    # Match rate degradation (for matching-enabled modules)
    if self._match_rate < 0.05 and self._total_attempted > 100:
        logger.warning(
            "[ALERT] Match rate %.1f%% below 5%% — check registry freshness",
            self._match_rate * 100,
        )

# 3. SELF-HEALING: Cache with staleness detection
class TeamCodeRegistry:
    def needs_refresh(self, max_age_seconds: int = 3600) -> bool:
        """True if never loaded, stale, or unknown codes seen."""
        ...

    def record_unknown_code(self, code: str, league: str) -> None:
        """Track codes that failed lookup for self-healing signal."""
        ...

# 4. SCHEDULING: Rate-limited periodic operations
VALIDATION_INTERVAL: ClassVar[int] = 10   # Every 10th poll (~2.5 min)
BACKFILL_INTERVAL: ClassVar[int] = 40     # Every 40th poll (~10 min)
REGISTRY_REFRESH_INTERVAL: ClassVar[int] = 40

# 5. MAINTENANCE: CLI commands
@matching_app.command("stats")
def matching_stats(league: str | None = None):
    """Show match rate per league, failure breakdown."""

@matching_app.command("backfill")
def matching_backfill(league: str | None = None):
    """Manual trigger for backfill_unlinked_events."""

# 6. REPORTING: System health integration
details["matching_match_rate"] = f"{match_rate:.4f}"
details["matching_total_events"] = total_events

# 7. LOGGING: Summaries at INFO, details at DEBUG
logger.info("Validation [%s]: %d checked, %d valid, %d errors, %d warnings", ...)
logger.debug("[%s:%s] (occurrence #%d) %s", entity_type, entity_id, count, issue)
```

### When This Pattern Applies

- ANY new module that runs in production (pollers, validators, matchers, future trade execution)
- ANY existing module being extended with new operational surface
- NOT needed for: pure utility functions, internal helpers, test infrastructure

### Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| "We'll add monitoring later" | Later never comes; first production incident is blind | Ship monitoring WITH the feature |
| Run expensive checks every cycle | Wastes DB resources, floods logs | Use interval counters (`_polls_since_X`) |
| Swallow all exceptions silently | Persistent failures invisible | Track error counts, escalate after threshold |
| Log only counts, not categories | "672 warnings" tells you nothing | Categorize failures (MatchReason pattern) |
| No CLI escape hatch | Can't diagnose at 2 AM via SSH | Add stats/refresh/backfill commands |
| Alert types exist but no triggers | Circuit breaker defined but never trips | Every alert type needs a concrete trigger condition with threshold |
| Alerts buried in log noise | CRITICAL lost in 753K WARNINGs | Alerts are separate from logging — use `[ALERT]` prefix, CRITICAL level, remediation hint |

### Cross-References

- Issue #477: Matching module production-readiness (template implementation)
- Issue #476: Production-readiness audit for all modules (Phase 2)
- Issue #485: Validation warning detail visibility
- Pattern 26: Resource Cleanup for Testability
- Pattern 27: Dependency Injection for Testability

---

## Pattern 42: Add-Column Checklist (ALWAYS for Adding Columns to Existing Tables)

**Severity:** HIGH — Missing a SELECT query causes silent data loss on fallback/read paths

### Problem

When adding columns to an existing table, developers naturally update the INSERT and
UPDATE statements. But tables often have SELECT queries in *other functions* that feed
data back to the write path (e.g., `get_current_market()` feeds fallback values to
`update_market_with_versioning()`). If the SELECT doesn't include the new columns,
the fallback logic returns None, silently overwriting real data with NULLs.

Unit tests mask this because mocks can include keys the real query doesn't SELECT.

### Real-World Trigger

Session 33 (#513): Migration 0046 added 8 columns to markets + market_snapshots.
INSERT and UPDATE statements were updated. But `get_current_market()` — which
`update_market_with_versioning()` calls to get fallback values — was NOT updated.
Result: `current.get("volume_24h")` always returned None, silently destroying
enrichment data on every market update. Glokta caught it in code review; unit tests
passed because mocks included the new keys.

### Pattern: 6-Point Checklist

When adding columns to an existing table, update ALL of:

| # | What | Why | Easy to miss? |
|---|------|-----|---------------|
| 1 | **Migration** (ADD COLUMN) | Column must exist | No |
| 2 | **INSERT statements** (create path) | New rows must include column | No |
| 3 | **UPDATE statements** (update path) | Existing rows must include column | No |
| 4 | **SELECT queries in OTHER functions** | Read paths that feed write paths | **YES** |
| 5 | **Views** (CREATE OR REPLACE) | Views don't auto-inherit new columns | Sometimes |
| 6 | **TypedDicts / type definitions** | API types must match schema | No |

Step 4 is the dangerous one. Search for all functions that SELECT from the table
and ask: "Does any other function use this result as input?" If yes, the SELECT
must include the new columns.

### Verification

```bash
# Find all SELECT queries from the table
grep -n "SELECT.*FROM markets" src/precog/database/crud_operations.py
# For each: does any caller use the result dict for fallback/merge logic?
```

### Cross-References

- Pattern 18: SCD Column Preservation (related — SCD versioning operations)
- Three-Tier Quality Model, Tier A: Code Path Audit
- Session 33: Glokta review finding #76

---

## Pattern 43: Mock Schema Fidelity (ALWAYS for Dict-Returning Function Mocks)

**Severity:** MEDIUM — Tests pass but production silently loses data

### Problem

When a test mocks a function that returns a dict (e.g., `get_current_market()`),
the mock dict is hand-crafted by the test author. If the real function's SQL query
doesn't SELECT a column, the real dict won't have that key — but the mock dict can.
This means tests exercise code paths that production never reaches.

This is distinct from the Mock Fidelity Rule (protocols.md) which covers *stateful*
mock divergence in read-then-write loops. This pattern covers *schema* divergence
between mock dicts and real query results.

### Real-World Trigger

Session 33 (#513): `TestUpdateMarketEnrichment` mocked `get_current_market` with
`{"volume_24h": 150, "previous_yes_bid": Decimal("0.4800"), ...}`. The test for
fallback preservation passed — `current.get("volume_24h")` returned 150 as expected.
But the real `get_current_market()` didn't SELECT those columns, so in production
`current.get("volume_24h")` would return None. The test validated logic that could
never execute.

### Pattern

When mocking dict-returning database functions:

1. **Derive mock dicts from the real query** — read the actual SELECT statement
   and only include keys that the query returns.
2. **If the mock needs a key the query doesn't return, that's a bug** — either
   the query needs updating (Pattern 42) or the mock is wrong.
3. **Consider a shared fixture** — define the "current market shape" once and
   use it in both the query test and the consumer test.

```python
# RISKY: Hand-crafted mock with keys the real query may not return
mock_get_current.return_value = {
    "id": 42,
    "yes_ask_price": Decimal("0.5000"),
    "volume_24h": 150,  # Does get_current_market() actually SELECT this?
}

# SAFER: Document which query this mock represents
# Mock matches get_current_market() SELECT as of migration 0046
mock_get_current.return_value = {
    # ... only keys that the real query returns
}
```

### Cross-References

- Mock Fidelity Rule (protocols.md) — covers stateful mock divergence
- Pattern 42: Add-Column Checklist — the root cause this pattern catches downstream
- Session 33: Glokta review finding #76, deployment log insight #74

---

## Pattern 44: API Consumer Blast Radius (ALWAYS for API Field Name Fixes)

**Severity:** HIGH — Fixing only the primary ingestion path leaves validators, display, types, and tests silently broken

### Problem

When an external API field name is discovered to be wrong (typo, suffix mismatch, API evolution), developers naturally fix the primary ingestion code and stop. But the same raw API dictionary flows through multiple consumers — each one using `dict.get("field_name")`. Fixing the ingestion path without updating validators, display code, TypedDicts, and test fixtures leaves those consumers silently broken: they return `None` from `.get()`, skip their logic, and produce no errors.

**Real-world trigger:** The Kalshi API returns integer fields with an `_fp` suffix as strings (e.g., `volume_fp: "8981763.00"`) but code read `market.get("volume")`. This caused:
- **5 fields** (volume, open_interest, volume_24h, yes_bid_size, yes_ask_size) **always NULL** in 7,802+ market snapshots
- **5 validator checks** silently inactive (negative volume, high volume, negative OI, ghost market, 24h>lifetime)
- **CLI** showing volume=0 for every market
- **TUI** showing volume=0 for every market
- **TypedDict** field names not matching the actual API response
- **30+ test fixtures** using old names — tests passed but exercised nothing

The bug existed since the project began. No errors, no warnings, no test failures. Only querying the live DB (S64 trigger) revealed it.

### Pattern: 5-Category Consumer Audit

When an API field name is fixed or renamed, audit ALL consumers of the raw API dictionary:

| # | Category | What to grep | Impact if missed |
|---|----------|-------------|------------------|
| 1 | **Ingestion** | Pollers, ETL, CRUD calls using `.get("field")` | Silent NULL data in DB |
| 2 | **Validation** | Validators using `.get("field")` for cross-field checks | Validators skip checks — dead validation |
| 3 | **Display** | CLI, TUI, dashboards using `.get("field", default)` | Always shows default value |
| 4 | **Types** | TypedDict definitions with `field: type` | Type checker can't catch mismatches |
| 5 | **Tests** | Fixtures with `"field": value` across ALL 8 test types | Tests pass but test nothing — dead tests |

### Procedure

```bash
# Step 1: Find ALL references to the old field name
grep -rn '"old_field"' src/ tests/

# Step 2: Categorize each hit
# - src/precog/schedulers/ → Ingestion
# - src/precog/validation/ → Validation
# - src/precog/cli/ or src/precog/tui/ → Display
# - src/precog/api_connectors/types.py → Types
# - tests/ → Tests

# Step 3: Fix ALL 5 categories before shipping

# Step 4: Fire S65 — check test fixtures for old names
grep -rn '"old_field"' tests/unit/ tests/integration/ tests/e2e/ tests/property/
```

### Special Consideration: `_fp` Suffix Convention

The Kalshi API uses `_fp` suffix for integer fields returned as strings:

| API Field | Type | Example Value | Conversion |
|-----------|------|---------------|------------|
| `volume_fp` | string | `"8981763.00"` | `int(float(x))` |
| `open_interest_fp` | string | `"4997871.00"` | `int(float(x))` |
| `volume_24h_fp` | string | `"0.00"` | `int(float(x))` |
| `yes_bid_size_fp` | string | `"24076.00"` | `int(float(x))` |
| `yes_ask_size_fp` | string | `"0.00"` | `int(float(x))` |

Note: `*_dollars` fields (prices) are also strings but use `Decimal()` conversion. The `_fp` fields are integer counts stored as float-formatted strings.

### Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Fix poller, skip validator | Validator silently stops checking | Audit all 5 categories |
| Fix code, skip TypedDict | Type checker can't catch future regressions | Update TypedDict to match live API |
| Fix code, skip tests | Tests become dead — pass but test nothing | Fire S65 (test fixture staleness) |
| Write TypedDict from API docs | Docs may use simplified names vs actual response | Verify against LIVE API response (S63) |
| Trust `.get()` returns None = safe | None is valid for nullable columns | S64 catches it — query the live DB |

### When This Pattern Applies

- ANY fix to an API field name mismatch (wrong name, wrong suffix, wrong case)
- ANY API evolution where field names change in a new version
- ANY discovery that a TypedDict doesn't match the live API response
- NOT needed for: adding entirely new fields (no old name to audit), internal-only renames

### Cross-References

- S63: Spec-first audit — verify TypedDict against live API BEFORE building
- S64: Post-merge data verify — query live DB after deployment
- S65: Test fixture staleness — check test fixtures for old field names after rename
- Pattern 39: Verify External API Data Before Building Parsers
- Pattern 42: Add-Column Checklist (related but for DB columns, not API fields)
- Pattern 43: Mock Schema Fidelity (related — mocks must match real API shape)

---

## Pattern 45: None-Preserving Value Sanitization (ALWAYS for External API Value Clamping)

**Severity:** MEDIUM — Conflating NULL with zero corrupts downstream analytics and ML features

### Problem

External APIs sometimes return invalid values (negative order book depth at settlement, out-of-range counts, nonsensical measurements). The natural fix is `max(0, value or 0)` — but `or 0` silently converts `None` to `0`, destroying the semantic distinction between:

- **`None`** — the field was absent from the API response ("we don't know")
- **`0`** — the field was present and measured as zero ("the order book is empty")

This matters because downstream consumers treat these differently:
- ML features: `None` → impute or exclude from training. `0` → "empty book" signal (meaningful).
- Analytics: `None` → skip row in aggregation. `0` → include as valid zero.
- Dashboards: `None` → show "N/A". `0` → show "0".

**Real-world trigger:** Kalshi API returns negative `yes_bid_size_fp` and `yes_ask_size_fp` at market settlement (order book dismantled). Initial fix used `max(0, _parse_fp_int(...) or 0)` which would have converted every missing-field `None` to `0`, making ~5% of snapshots appear to have "measured zero depth" when they actually had "no depth data."

### Pattern: Clamp Helper with None Passthrough

```python
# WRONG — conflates "missing" with "zero"
yes_bid_size = max(0, _parse_fp_int(market, "yes_bid_size_fp") or 0)

# RIGHT — preserves None semantics
def _clamp_non_negative(value: int | None) -> int | None:
    """Clamp to non-negative, preserving None.
    None = field absent (unknown). 0 = measured zero. Negative = API artifact.
    """
    if value is None:
        return None
    return max(0, value)

yes_bid_size = _clamp_non_negative(_parse_fp_int(market, "yes_bid_size_fp"))
```

### The Three States

| API Response | `_parse_fp_int` Returns | `or 0` Result | Correct Result | Semantic Meaning |
|-------------|------------------------|---------------|----------------|------------------|
| Field missing | `None` | `0` (WRONG) | `None` | "We don't know" |
| `"0.00"` | `0` | `0` | `0` | "Measured zero" |
| `"-250589.00"` | `-250589` | `-250589` | `0` | "API artifact, clamp" |

### When This Pattern Applies

- Clamping, flooring, or ceiling values parsed from external APIs
- Any sanitization where the input can be `None` (field absent)
- NOT needed for: required fields that are always present, internal calculations where None is a bug

### Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| `value or 0` before `max()` | `None` becomes `0` | Use explicit `if value is None` check |
| `value if value else 0` | Also converts `None` to `0` | Same — check `is None` specifically |
| `max(0, value)` without None guard | `TypeError: '>' not supported between NoneType and int` | Add None check first |
| `COALESCE(value, 0)` in SQL | Perpetuates the same conflation in the DB layer | See `feedback_coalesce_null_perpetuation.md` |

### Cross-References

- Pattern 1: Decimal Precision (related — Decimal vs float, this is None vs 0)
- `feedback_coalesce_null_perpetuation.md` — SQL-side equivalent of this problem
- Issue #542: Kalshi negative bid/ask sizes at settlement (origin of this pattern)
- Issue #536: First S65 firing — test fixture _fp updates
- Session 34: Discovery, fix, and protocol hardening

---

**END OF DEVELOPMENT_PATTERNS_V1.27.md**

★ Insight ─────────────────────────────────────
This extraction serves two critical purposes:
1. **Context Optimization:** Reduces CLAUDE.md from 3,723 lines to ~1,800 lines (50% reduction), freeing up ~22,500 tokens (~11% of context budget)
2. **Improved Usability:** Patterns are now in a dedicated, searchable reference guide rather than buried in a 3,700-line master document

The preservation of all cross-references (ADRs, REQs, file paths) ensures developers can navigate from patterns to detailed implementation guides without information loss.

## Pattern 46: Mock Patch Migration on Module Extraction (ALWAYS for Module Splits)

**Context:** When extracting functions from a god object into domain modules (e.g., `crud_operations.py` → `crud_markets.py`, `crud_teams.py`), mock.patch targets must follow the function to its new namespace.

**The Problem:** Python's `mock.patch("module.name")` patches the name in a specific module's namespace. When a function moves from module A to module B, all patches must update:

```python
# BEFORE extraction: function lives in crud_operations
@patch("precog.database.crud_operations.get_cursor")  # ✅ Works

# AFTER extraction: function moved to crud_markets
@patch("precog.database.crud_operations.get_cursor")  # ❌ AttributeError
@patch("precog.database.crud_markets.get_cursor")      # ✅ Works
```

**Three categories of patches to migrate:**

| Category | Example | New Target |
|----------|---------|------------|
| **Helper patches** (get_cursor, fetch_one, fetch_all) | `@patch("old_module.get_cursor")` | Domain module where the function under test lives |
| **Cross-function patches** (function A mocks function B in same module) | `@patch("old_module.get_current_market")` | Domain module where the caller lives |
| **Consumer patches** (CLI/scheduler tests mock a CRUD function) | `@patch("old_module.create_market")` | Module where the consumer's import binds the name |

**Systematic migration approach (session 38):**
1. Write a script with function→module mapping (already known from extraction)
2. Rewrite `from X import Y` statements using the mapping
3. Rewrite `@patch("X.Y")` strings using the mapping
4. Handle aliased imports (`import X as Y`) manually — scripts miss these
5. Run tests iteratively: unit → integration → stress/chaos/race

**Scale:** Session 38 migrated 302 helper patches + 40 function patches + 145 import rewrites across 55 files. Script-based approach completed in ~30 minutes.

**When This Pattern Applies:**
- ANY module split or extraction (god object decomposition)
- Renaming modules or moving functions between files
- NOT needed for: adding new functions (no existing patches to migrate)

**Reference:**
- ADR-115: Database Domain Module Architecture
- Session 38: CRUD Phase 1b/1c extraction + Option B cleanup

---

## Pattern 47: Verify Schema Before Fixing Pattern Violations (ALWAYS for Code Review Findings)

**Trigger:** A code review (human or AI) flags missing pattern usage (e.g., "missing row_current_ind filter").

**Rule:** Before fixing, verify the precondition holds — does the table actually use this pattern?

**Why:** Pattern flags are heuristics. Claude Review CI flagged `crud_teams.py` for missing SCD Type 2 filters in Session 42b (issue #595). Session 42c verification revealed: **the `teams` table has no `row_current_ind` column** — it's a standard dimension table, not SCD Type 2. The fix would have failed at runtime. Cost of unnecessary verification: ~2 minutes. Cost of unverified fix attempt: a full Tier 2 cycle (build + review + QA + revert).

**SCD Type 2 tables in this codebase:** `game_states`, `markets`, `positions`, `edges`, `account_balance`. NOT `teams`, `events`, `games`, `venues`, `series`.

**Verification steps:**
1. Check the table's CREATE statement (latest migration): does the column exist?
2. If unsure, query: `SELECT column_name FROM information_schema.columns WHERE table_name = 'X' AND column_name = 'row_current_ind'`
3. If the column doesn't exist, close the review finding as a false positive with explanation

**When This Pattern Applies:**
- Any code review finding flagging "missing X pattern"
- Any automated linter rule about SCD/security/precision patterns
- Any inherited belief about how a table works ("I thought we used SCD here")

**Reference:** Session 42c S68 audit, issue #595 closed as false positive after schema verification.

---

## Pattern 48: Use dataclasses.replace() for Frozen Dataclass Updates (ALWAYS for Immutable Records)

**Trigger:** Need to create a new instance of a `@dataclass(frozen=True)` with one or more fields changed.

**Rule:** Use `dataclasses.replace(instance, field=new_value)`. NEVER use `dict_spread` reconstruction.

**Why:** The naive pattern serializes types away:

```python
# WRONG — fragile and silently corrupts types
metadata = BackupMetadata(
    **{
        **metadata.to_dict(),  # serializes BackupType enum -> string, datetime -> ISO string
        "storage_id": storage_id,
        "backup_type": metadata.backup_type,  # manual override 1
        "status": metadata.status,             # manual override 2
        "created_at": metadata.created_at,     # manual override 3
        "completed_at": metadata.completed_at, # manual override 4
    }
)
```

If anyone adds a new enum or datetime field to `BackupMetadata` later and forgets to add it to the manual override list, it silently passes a string to the dataclass constructor. The bug only surfaces when the field is read.

**Correct:**
```python
from dataclasses import replace
metadata = replace(metadata, storage_id=storage_id)
```

`replace()` preserves all original types and only updates the specified fields. It's the standard library's idiomatic answer for exactly this case.

**When This Pattern Applies:**
- Updating a single field on a frozen dataclass
- Updating multiple fields on a frozen dataclass (still cleaner than dict spread)
- Anywhere you'd be tempted to reach for `**asdict(instance)`

**When NOT to use:**
- Creating from scratch (use the constructor)
- Building from external dict input (use `from_dict()` classmethod with explicit deserialization)

**Reference:** Session 42c, PR #601 backup orchestrator fix, Claude Review finding on PR #597.

---

## Pattern 49: SCD Race Condition Prevention with FOR UPDATE (ALWAYS for SCD Close→Insert)

**Trigger:** Any function that closes the current SCD row and inserts a new one in the same transaction.

**Rule:** Use `SELECT ... FOR UPDATE` to lock the current row before the close→insert sequence. Capture `NOW()` once for temporal continuity.

**Why:** The naive pattern has a race window:

```python
# WRONG — race condition between concurrent calls
with get_cursor(commit=True) as cur:
    cur.execute("UPDATE account_balance SET row_current_ind = FALSE, row_end_ts = NOW() WHERE platform_id = %s AND row_current_ind = TRUE", (platform_id,))
    cur.execute("INSERT INTO account_balance (...) VALUES (..., NOW(), NOW())", (...))
```

Two concurrent calls can both execute the UPDATE (closing the current row) before either runs the INSERT. The partial unique index from the migration prevents *duplicate* current rows but NOT the *zero* current rows scenario. After the race, the table has zero current rows for that platform — balance lookups return NULL, breaking downstream logic.

**Correct:**
```python
with get_cursor(commit=True) as cur:
    # Capture timestamp once for temporal continuity
    cur.execute("SELECT NOW() AS ts")
    now = cur.fetchone()["ts"]

    # Lock current row (serializes concurrent updates)
    cur.execute("SELECT id FROM account_balance WHERE platform_id = %s AND row_current_ind = TRUE FOR UPDATE", (platform_id,))

    # Close old version (uses captured timestamp)
    cur.execute("UPDATE account_balance SET row_current_ind = FALSE, row_end_ts = %s WHERE platform_id = %s AND row_current_ind = TRUE", (now, platform_id))

    # Insert new version (matching row_start_ts)
    cur.execute("INSERT INTO account_balance (..., row_start_ts, created_at) VALUES (..., %s, %s)", (..., now, now))
```

**Why two improvements?**
1. `FOR UPDATE` serializes concurrent transactions on the same `platform_id` — the second transaction blocks until the first commits, then sees the new current row and locks it.
2. Single `NOW()` ensures `row_end_ts` of the old row equals `row_start_ts` of the new row exactly — no temporal gap or overlap. Two separate `NOW()` calls drift by microseconds.

**Edge cases handled:**
- **No current row exists:** `FOR UPDATE` locks zero rows (no-op), UPDATE affects zero rows, INSERT proceeds. Function degrades gracefully to a plain insert.
- **Transaction interrupted:** `get_cursor(commit=True)` rolls back on any exception. No partial state.
- **Deadlock:** Single-row locks with consistent ordering — no deadlock risk.

**When This Pattern Applies:**
- ANY SCD Type 2 versioning function with close → insert
- Affected tables: `markets`, `positions`, `game_states`, `edges`, `account_balance`
- ANY function that reads-then-writes the same row in a single transaction with concurrent callers

**Reference:** Session 42c, issue #587, PR #601 `update_account_balance_with_versioning` fix.

---

## Pattern 50: Reverse-Engineer Strategy via Closed Trade Lifecycle (ALWAYS for External Trader Analysis)

**Trigger:** Reverse-engineering a public trader's strategy from their trade history (Polymarket, Kalshi, sportsbooks).

**Rule:** Look at the full lifecycle (TRADE → MERGE/REDEEM), not just the active book.

**Why:** Active positions are a moment in time. The trade history is the strategy. Session 42c ColdMath analysis (#605):

- **Active positions:** ~70% weather markets — looked like a pure weather trader
- **MERGE/REDEEM history:** ~40% sports markets (MLS, J-League, cycling, Eurovision) — much more diversified
- **Conclusion:** Strategy is multi-domain, just heavy on weather *right now*

If we'd only analyzed the active book, we would have missed the diversification entirely.

**Methodology:**
1. Fetch full activity history (paginate all transaction types: TRADE, MERGE, REDEEM, MAKER_REBATE)
2. Group by `conditionId` (or market identifier) to reconstruct position lifecycles
3. Match TRADE entries to REDEEM entries: profit = redeem_amount - sum(buy_costs)
4. Identify losing positions: conditionIds with TRADEs but no REDEEMs (expired worthless)
5. Compute strategy metrics: win rate, edge by price bucket, Sharpe ratio
6. Segment by market type/category to find specialization patterns

**Key APIs:**
- Polymarket: `https://data-api.polymarket.com/activity?user=<wallet>&limit=200&offset=N`
- Public wallets are tradeable as on-chain data
- API typically caps at offset 3200 — older trades may need archival sources

**Caveat:** REDEEM events only fire on winning positions (losing shares expire worthless and don't generate REDEEM). Cross-reference with market resolution data to find losing positions and compute true win rate.

**When This Pattern Applies:**
- Any reverse-engineering of a profitable trader (Polymarket, Kalshi, sportsbooks)
- Strategy research for new market types (#602 epic)
- Validating that a published "edge" actually exists

**Reference:** Session 42c, ColdMath analysis, `findings_coldmath_weather_strategy.md`, `memory/research/coldmath_polymarket_trades_20260405.csv`.

---

## Pattern 52: SCD Race Retry Helper Structure (ALWAYS for SCD Retry Logic)

**Severity:** HIGH -- Money-touching SCD code with naive retry logic can corrupt temporal continuity or mask real bugs.

### Problem / Trigger

You are implementing or modifying a retry mechanism for an SCD Type 2 close-then-insert sequence (e.g., `update_*_with_versioning` functions in `crud_*.py`) protected by a unique partial index like `idx_*_unique_current`.

### The Pattern / Rule

SCD race retry must satisfy 7 conditions:

1. **Catch the SPECIFIC exception, not the family.** Use `psycopg2.errors.UniqueViolation`, NOT bare `psycopg2.IntegrityError` or `Exception`. The targeted family includes 4-5 distinct constraint sources (CHECK, FK, NOT NULL, partial unique, future). A bare catch masks CHECK violations from buggy upstream data.

2. **Discriminate by `diag.constraint_name`.** Inspect `e.diag.constraint_name` and only retry when it matches the expected partial unique index. Other constraint violations re-raise immediately. Defensive `getattr(exc, "diag", None)` guards against psycopg2 API drift.

3. **Retry MUST run in a NEW transaction.** PostgreSQL aborts the current transaction on constraint violation; even with manual rollback, the same transaction's MVCC snapshot will not see the sibling caller's committed row. Structure as TWO sequential `with get_cursor(commit=True)` blocks, never nested.

4. **Re-capture `NOW()` per attempt.** Reusing the first attempt's timestamp creates backward temporal intervals (sibling's `row_end_ts` before its own `row_start_ts`) -- silent SCD corruption. Pattern 49's "single NOW() for temporal continuity" applies WITHIN a single attempt, not across retries.

5. **Max ONE retry, re-raise via explicit `__cause__` chain.** On second failure, use `raise exc2 from first_exc` (capture `first_exc` before attempt 1's except clause exits -- Python's automatic `__context__` chain is severed when the first except exits cleanly). Two retries indicate the system is in a state more retries cannot fix.

6. **Structured logging at WARNING (between attempts) and ERROR (on exhaustion).** Both must include the constraint name and a business key (e.g., `platform_id`) for postmortem correlation.

7. **Tests MUST exercise the retry path with stub injection.** Unit tests must mock the cursor to raise `UniqueViolation` with a specific `constraint_name` on the first attempt and succeed on the second. A separate test for non-matching constraint must verify NO retry. Race tests must use `caplog` to assert the WARNING fires (see Pattern 53).

### Why

The naive "wrap in try/except IntegrityError, retry once" implementation has THREE silent corruption modes:
- Masks CHECK violations (caught CHECK looks like a transient race)
- Reuses MVCC snapshot (retry does not see sibling's commit, fails infinitely)
- Reuses NOW() timestamp (creates backward temporal intervals)

Each is invisible without code inspection. The pattern catches all three.

### Wrong

```python
def update_balance_with_versioning(platform_id, new_balance):
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("SELECT NOW() AS ts")
            now = cur.fetchone()["ts"]
            cur.execute(LOCK_QUERY, (platform_id,))
            cur.execute(CLOSE_QUERY, (now, platform_id))
            cur.execute(INSERT_QUERY, (platform_id, new_balance, now, now))
            return cur.fetchone()["id"]
    except psycopg2.IntegrityError:  # WRONG: too broad
        # WRONG: same transaction, MVCC snapshot stale, NOW() reused
        with get_cursor(commit=True) as cur:
            cur.execute(INSERT_QUERY, (platform_id, new_balance, now, now))
            return cur.fetchone()["id"]
```

### Right

```python
def update_balance_with_versioning(platform_id, new_balance):
    def _attempt():
        with get_cursor(commit=True) as cur:
            cur.execute("SELECT NOW() AS ts")  # RE-CAPTURED per attempt
            now = cur.fetchone()["ts"]
            cur.execute(LOCK_QUERY, (platform_id,))
            cur.execute(CLOSE_QUERY, (now, platform_id))
            cur.execute(INSERT_QUERY, (platform_id, new_balance, now, now))
            return cur.fetchone()["id"]

    return retry_on_scd_unique_conflict(
        _attempt,
        "idx_balance_unique_current",  # SPECIFIC constraint name
        business_key={"platform_id": platform_id},
    )
```

### When This Pattern Applies

- ANY SCD Type 2 close+insert sequence in `crud_*.py`
- Especially money-touching tables: `account_balance`, `positions`, `account_ledger`
- Sites currently identified for adoption: 7 sibling sites in #623-#628

### When NOT to Apply

- Append-only tables (no SCD versioning)
- Single-row updates that do not follow close+insert pattern
- Read-only operations
- INSERT-only with no current-row constraint

### Source

- Session 42d, PR #631 (#613 SCD first-insert race fix)
- Holden's 7 conditions: `memory/findings_613_holden_scoping.md`
- Helper implementation: `src/precog/database/crud_shared.py::retry_on_scd_unique_conflict`
- Companion: Pattern 49 (FOR UPDATE locks zero rows on first insert -- this pattern handles the gap)

---

## Pattern 53: Race Tests Must Assert The Race Actually Fired (ALWAYS for Race Tests)

**Severity:** HIGH -- Race tests can silently provide false coverage if they pass under serialization without exercising the race code path.

### Problem / Trigger

You are writing or reviewing a race test (`tests/race/test_*.py`) that exercises a concurrent code path with `threading.Barrier` synchronization.

### The Pattern / Rule

Race tests must assert TWO things:
1. **Correctness invariants** -- the outcome is correct regardless of which thread won (e.g., "exactly 1 current SCD row", "exactly 2 version rows", "balances are not duplicated")
2. **The race actually fired** -- at least one execution exercised the contested code path

The second assertion is non-obvious but critical. Without it, the test passes when:
- OS scheduler serializes the threads enough that thread A completes before thread B starts
- The race window is too narrow to hit reliably
- The test environment (single-CPU CI, slow VM) eliminates the timing pressure

### Why

Marvin (Sentinel) caught this in Session 42d's #631 review. The original race test for #613 SCD race ran TWO threads ONCE, asserted correctness invariants, and passed. But the WARNING log (from the retry helper) NEVER fired in many runs because the threads were serializing under typical timing. The test was a coverage liar -- it would have continued passing if a regression broke the retry logic, because the regression would never be reached.

The fix: 50-iteration loop + caplog assertion that the WARNING fires at least once. Now the test FAILS if the race path is never exercised, even if all per-iteration assertions pass.

### Wrong

```python
# Single-iteration race test -- may never exercise the contested path
def test_concurrent_balance_update(self):
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_a = executor.submit(thread_fn, "a", barrier)
        f_b = executor.submit(thread_fn, "b", barrier)
        f_a.result()
        f_b.result()
    # Only checks correctness, not whether the race actually fired
    assert count_current_rows() == 1
```

### Right

```python
@pytest.mark.skipif(_is_ci, reason="Race tests hang in CI threading model")
class TestRaceXYZ:
    def test_race_actually_fires(self, caplog):
        NUM_ITERATIONS = 50

        with caplog.at_level(logging.WARNING):
            for i in range(NUM_ITERATIONS):
                clear_test_data()

                barrier = threading.Barrier(2)
                results = {}
                with ThreadPoolExecutor(max_workers=2) as executor:
                    f_a = executor.submit(thread_fn, "a", barrier, results)
                    f_b = executor.submit(thread_fn, "b", barrier, results)
                    f_a.result()
                    f_b.result()

                # Per-iteration: correctness invariants
                assert count_current_rows() == 1

        # Across all iterations: prove the race actually fired at least once
        race_warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "expected race signature substring" in r.getMessage()
        ]
        assert len(race_warnings) >= 1, (
            f"Race test ran {NUM_ITERATIONS} iterations without firing the contested "
            f"code path. The threads are serializing and the test is providing false "
            f"coverage. Either increase iteration count, shorten the barrier release "
            f"timing, or inject a deterministic delay to force the race."
        )
```

### When This Pattern Applies

- ANY new race test (`tests/race/`)
- Existing race tests that depend on contested code paths firing
- Stress tests where the assertion is "this code path executed under load"

### When NOT to Apply

- Race tests that test FAILURE modes (e.g., "deadlock detected and recovered") where the assertion IS the contested-path firing
- Pure stress tests where the assertion is throughput, not correctness

### Source

- Session 42d, PR #631 (#613 SCD race fix)
- Marvin's review finding: `memory/findings_508_subcouncil_B_safety.md` (Marvin frame, Scenario 7)
- Implementation: `tests/race/test_account_balance_concurrent_first_insert.py`

---

## Pattern 54: Verifier Scripts as Investigation Deliverables (ALWAYS for External API Investigation)

**Severity:** MEDIUM -- When investigating external API behavior, deliver an executable verifier script rather than running one-shot investigation.

### Problem / Trigger

You are tasked with "investigate behavior X of external system Y" (e.g., issue #335 -- investigate Kalshi demo API order endpoint behavior).

### The Pattern / Rule

Instead of running the investigation directly and producing one-shot findings, build a **standalone verifier script** with safety modes that the user (or any future operator) can run when needed.

Minimum required structure:

```python
#!/usr/bin/env python3
"""
External system verifier (#issue-num).

SAFETY MODES:
    --dry-run        Print plan, no API calls (default)
    --read-only      Read-only API calls
    --live           Write tests against test/demo system
    --allow-prod     REQUIRED for production
"""

# Bake in safety guards:
# - Refuses to run without required env vars
# - Refuses --live if precondition state is unsafe (e.g., balance too low)
# - Hard caps on test side effects (max 1 contract, max $1, etc.)
# - All test artifacts use identifiable prefix (e.g., "VERIFY_335_")
# - Cleans up any mutations after each test
# - Refuses prod mode without explicit --allow-prod flag

# Each test scenario records to a structured findings file:
# - .verification_findings/<system>_findings_<timestamp>.json
# - .verification_findings/<system>_findings_<timestamp>.md
```

### Why

For external-system investigations, the value of "I delivered the script" is almost equal to "I delivered findings" -- because the script can be re-run any time, but findings are a snapshot that decay. A high-quality verifier the user runs themselves with a clear head produces better understanding than a hastily-run verifier produced at session end.

Specific advantages:
- **Re-runnable:** detects API regressions in the future
- **Auditable:** produces durable findings files
- **Safe:** baked-in guards prevent accidental damage
- **Educational:** the script's structure documents the test plan
- **Independent of session context:** anyone can run it later

### Wrong

PM at session end runs 13 API tests directly, parses the responses, manually documents findings in a memory file. Quality suffers in late context. The findings are a snapshot. The script that ran the tests is gone.

### Right

PM builds `scripts/verify_kalshi_demo_orders.py` with:
- 4 safety modes (dry-run/read-only/live/allow-prod)
- 13 scenarios scaffolded with TODO placeholders
- Structured findings collection
- Read-only mode validated against real API to confirm script works
- Live mode deferred to user supervision
- Closes #335 in spirit (artifact exists), issue stays open until findings populated

### When This Pattern Applies

- "Investigate external API behavior" tasks
- Pre-integration verification of third-party services
- Regression detection scripts
- Pre-live checklist automation

### When NOT to Apply

- Investigations of internal codebase (use grep + read directly)
- Investigations that require human judgment (use PM analysis)
- One-time research that will not be repeated

### Source

- Session 42d, #335 Kalshi demo API verifier
- Script: `scripts/verify_kalshi_demo_orders.py`
- Test plan + findings template: `memory/findings_335_kalshi_demo_verification.md`
- Council reference: Sub-Council C synthesis -- flagged #335 as Phase 2 entry criterion

---

## Pattern 55: Fee-Aware Orderbook Edge Calculation (ALWAYS for Edge Calculations)

**Severity:** HIGH -- Edge calculations that do not subtract per-trade fees systematically overestimate edge by the fee amount (0.1-0.2% per trade for Kalshi). Affects every trade decision.

### Problem / Trigger

You are computing edge between a model probability and a Kalshi (or other orderbook prediction market) price.

**Correction note (Session 42f):** An earlier version of this pattern was titled "Strip Exchange Margin (Vig) Before Computing Edges." That was WRONG for Kalshi (and other orderbook prediction markets). Kalshi is an orderbook, not a sportsbook. There is no vig. The exchange takes its cut as explicit per-trade fees, not as built-in price margin. The framing is "subtract fees + use the correct side of the orderbook" not "strip vig."

### The Pattern / Rule

Kalshi quotes are real orderbook bids and asks, not bookmaker prices. To compute edge correctly:

```python
from decimal import Decimal

# Buying YES -- your cost is what you pay at the offer + fees
def edge_buying_yes(model_p: Decimal, yes_ask: Decimal, fee_rate: Decimal) -> Decimal:
    return model_p - yes_ask - fee_rate

# Selling YES -- your proceeds are what you receive at the bid - fees
def edge_selling_yes(model_p: Decimal, yes_bid: Decimal, fee_rate: Decimal) -> Decimal:
    return yes_bid - model_p - fee_rate

# Buying NO is symmetric
def edge_buying_no(model_p: Decimal, no_ask: Decimal, fee_rate: Decimal) -> Decimal:
    return (Decimal("1.0") - model_p) - no_ask - fee_rate
```

### Why

- **No vig:** Kalshi is an orderbook, not a sportsbook. `yes_bid + no_bid <= 1.0` and `yes_ask + no_ask >= 1.0` are arbitrage-free constraints, not vig markers. The gap between them is the **bid-ask spread** of an orderbook, same as on any stock exchange.
- **Fees ARE the issue:** Kalshi 2026 fees are claimed at 0.1% major / 0.2% sports (per Reddit r/PillarLab post, NEEDS VERIFICATION). Per-trade fees compound across many trades and turn marginal edges into losses.
- **Side matters:** `market_probability` for buy decisions must use the ASK (what you would pay), and for sell decisions must use the BID (what you would receive). Using the midpoint or wrong side biases edge in opposite directions for buys vs sells.

### Wrong

```python
edge = model_p - market.last_price  # WRONG -- last_price is not what you would pay now
edge = model_p - (market.yes_ask + market.yes_bid) / 2  # WRONG -- midpoint is fictional
edge = model_p - market.yes_ask  # WRONG -- missing fee subtraction
```

### Right

```python
from decimal import Decimal

fee_rate = kalshi_fee_for_market(market)  # Decimal("0.001") for major, Decimal("0.002") for sports
edge = model_p - market.yes_ask_dollars - fee_rate  # CORRECT for buying YES
```

**Multi-bracket markets:** For multi-bracket markets (temperature buckets, multi-outcome questions), each bracket is its own orderbook. The sum of `yes_ask` across brackets > 1.0 because each bracket has its own bid-ask spread. If you want fair-value implied probability across brackets (for comparison, not for trading), normalize:

```python
from decimal import Decimal

def normalize_bracket_prices(bracket_asks: dict[str, Decimal]) -> dict[str, Decimal]:
    """Normalize bracket asks for cross-bracket comparison.

    This is NOT vig removal -- it is spread accounting across multi-outcome markets.
    Use this for COMPARISON across brackets, not for edge calculation on a
    single bracket trade.
    """
    total = sum(bracket_asks.values())  # > 1.0 due to per-bracket spreads
    return {k: v / total for k, v in bracket_asks.items()}
```

For trading a single bracket, use that bracket's actual `yes_ask_dollars` + fees, no normalization.

### When This Pattern Applies

- ANY edge calculation against a Kalshi orderbook price
- ANY edge calculation against a Polymarket orderbook price
- Cross-bracket comparison in multi-outcome markets (use `normalize_bracket_prices`)

### When NOT to Apply

- Sportsbook markets (DraftKings, FanDuel, Pinnacle) -- these DO have vig in the traditional sense (-110/-110 etc.) and need a different correction. We do not trade these.
- Display of raw exchange prices for debugging (label clearly)
- Order placement (you submit the raw bid/ask; the exchange handles fees on its side at execution)

### Source

- Session 42d follow-up review of Reddit r/PillarLab post (2026)
- Session 42f correction: user pushback + live Kalshi demo API verification (2026-04-07, 50-market sample)
- Tracked under issue #673 (audit + fix existing edge calculation code; rescoped to "fee subtraction + correct orderbook side")
- Meta-lesson: Verify externally-sourced terminology before propagating it into formal documentation

---

## Pattern 56: JSONB + Decimal Round-Trip via Custom Encoder (ALWAYS for JSONB with Decimal)

**Severity:** HIGH -- `psycopg2.extras.Json` uses plain `json.dumps` by default, which raises `TypeError` on any `Decimal` value. The crash is hard to detect in tests.

### Problem / Trigger

You are storing `Decimal` values in a JSONB column via `psycopg2.extras.Json(dict)`.

### The Pattern / Rule

Provide a custom `dumps` callable that serializes `Decimal` as its string representation. `psycopg2.extras.Json` uses plain `json.dumps` by default, which raises `TypeError: Object of type Decimal is not JSON serializable` on any Decimal value.

### Why

The default `json.dumps` has no `Decimal` adapter. Any dict containing Decimal values passed to `Json()` will crash at the INSERT boundary. The crash is hard to detect in tests because:
1. Unit tests that mock the CRUD function never exercise the serializer
2. Integration tests that use string stand-ins (`"0.4500"` instead of `Decimal("0.4500")`) trivially pass through `json.dumps`
3. Race tests usually do not seed meaningful state data

**Symmetric read-path requirement:** If the producer writes Decimal-as-string, the consumer MUST parse it back as Decimal at read time. Otherwise comparisons like `Decimal <= str` raise `TypeError` silently. File an issue pairing the write-path fix with the read-path fix (e.g., session 42e: #669 pairs with #629's `_jsonb_dumps` fix).

### Wrong

```python
from psycopg2.extras import Json
from decimal import Decimal

# Crashes at INSERT if trailing_stop_state contains Decimal values
state = {"activation_price": Decimal("0.4500"), "current_stop_price": Decimal("0.4200")}
cur.execute(
    "INSERT INTO positions (trailing_stop_state) VALUES (%s)",
    (Json(state),),
)
```

### Right

```python
import json
from decimal import Decimal
from psycopg2.extras import Json
from precog.database.crud_shared import DecimalEncoder

def _jsonb_dumps(obj):
    """json.dumps with DecimalEncoder for JSONB columns.

    Serializes Decimal as its string representation so psycopg2 can
    encode the value into JSONB. Round-trip contract: on READ, the
    JSONB decoder returns the stored value as a Python string (not
    Decimal). Consumers that need Decimal semantics must parse with
    Decimal(value) at read time.
    """
    return json.dumps(obj, cls=DecimalEncoder)

state = {"activation_price": Decimal("0.4500"), "current_stop_price": Decimal("0.4200")}
cur.execute(
    "INSERT INTO positions (trailing_stop_state) VALUES (%s)",
    (Json(state, dumps=_jsonb_dumps),),
)
```

### When This Pattern Applies

- Any CRUD function that stores a Python dict containing Decimal values into a JSONB column
- Any JSONB column where upstream callers pass Decimal values (e.g., `trailing_stop_state`, `config`)

### When NOT to Apply

- Pure Decimal columns (`DECIMAL(10,4)`) -- psycopg2 handles these natively
- JSONB storing only strings/ints/bools/lists of primitives
- Columns stored as structured PostgreSQL types (hstore, arrays)

### Source

- Session 42e Marvin sentinel pass on PR #671
- Reproduced end-to-end against a real PostgreSQL testcontainer
- Fix: `src/precog/database/crud_positions.py::_jsonb_dumps`
- Related: Issue #666 (sibling bug), Issue #669 (symmetric read-path), Issue #670 (Mock Fidelity Rule serialization extension)

---

## Pattern 57: Close-by-Business-Key Inside Retry Closure (ALWAYS for SCD Retry with Surrogate Keys)

**Severity:** HIGH -- Using surrogate id inside a retry closure causes stale-reference bugs when a sibling caller's commit changes the surrogate.

### Problem / Trigger

A CRUD function closes and re-inserts an SCD versioned row inside a `retry_on_scd_unique_conflict` closure, AND retries may see a sibling caller's committed row with a different surrogate id.

### The Pattern / Rule

Inside the closure, use the **business key** (not the surrogate id) in both the lock query and the close query. The surrogate id captured before entering the closure becomes stale on retry.

### Why

The retry helper invokes the closure a second time after a sibling caller's commit. The sibling's new version has a new surrogate id but the same business key. If the closure uses `WHERE id = %s` (surrogate), it will either:
1. Match zero rows (if the sibling closed the original surrogate) -- INSERT creates an orphan second current row -- unique index violation, retry loop, error
2. Match the sibling's row but with stale values -- update over fresh data

Using `WHERE <business_key_col> = %s AND row_current_ind = TRUE` always finds the correct current row on both the first attempt and the retry.

### Wrong

```python
def _attempt(position_id: int, ...):  # position_id captured as surrogate
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT ... FOR UPDATE WHERE id = %s", (position_id,))
        cur.execute("UPDATE positions SET row_current_ind = FALSE WHERE id = %s", (position_id,))
        # On retry after sibling's commit, position_id is stale -- this closes
        # the wrong row or matches zero rows
```

### Right

```python
# Outer: fetch once by surrogate to validate existence and capture business key
initial_current = fetch_one(
    "SELECT * FROM positions WHERE id = %s AND row_current_ind = TRUE",
    (position_id,),
)
if not initial_current:
    raise ValueError(f"Position not found: {position_id}")
position_bk = initial_current["position_id"]  # Business key, stable across retries

def _attempt():
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT NOW() AS ts")
        now = cur.fetchone()["ts"]
        # Lock by business key -- always finds current row even after sibling's commit
        cur.execute(
            "SELECT id FROM positions WHERE position_id = %s "
            "AND row_current_ind = TRUE FOR UPDATE",
            (position_bk,),
        )
        # Re-fetch fresh current row by business key
        cur.execute(
            "SELECT * FROM positions WHERE position_id = %s "
            "AND row_current_ind = TRUE",
            (position_bk,),
        )
        current = cur.fetchone()
        # Close by business key -- survives sibling surrogate churn
        cur.execute(
            "UPDATE positions SET row_current_ind = FALSE, row_end_ts = %s "
            "WHERE position_id = %s AND row_current_ind = TRUE",
            (now, position_bk),
        )
        # ... INSERT using captured current values ...

retry_on_scd_unique_conflict(
    _attempt,
    "idx_positions_unique_current",
    business_key={"position_id": position_bk},
)
```

### When This Pattern Applies

- Any retry closure where the business key is distinct from the surrogate id AND the table uses SCD Type 2 versioning where each version gets a new surrogate
- Canonical examples: `crud_positions.py::update_position_price`, `close_position`, `set_trailing_stop_state`

### When NOT to Apply

- Tables where the "business key" and surrogate id are the same (e.g., `user_id` is both surrogate and business key)
- Non-retry code paths (Pattern 49's FOR UPDATE is sufficient without retry)

### Source

- Session 42e PR #665 (canonical pattern landed there) and PR #671 (applied again in `set_trailing_stop_state`)
- Extends Pattern 49 (SCD Race Prevention) and Pattern 52 (SCD Race Retry Helper Structure)

---

## Pattern 58: Triple-Reviewer Convergence as Structural Validation (ALWAYS for Multi-Agent Review)

**Severity:** MEDIUM -- Individual reviewer findings have variance; convergence across 3+ independent frames is high-confidence signal.

### Problem / Trigger

You are dispatching 3+ agents with different cognitive frames to review the same diff in parallel (per protocols.md Step 4 + 4b + 5 for money-touching Tier 2 PRs).

### The Pattern / Rule

When 3+ reviewers with different cognitive frames independently surface the same finding, treat it as **structurally validated** -- high-confidence signal worth treating as a blocker, even if any individual reviewer would have rated it non-blocking.

### Why

Individual reviewer findings have variance -- a single reviewer might be wrong, overfit to their frame, or miss context. Three reviewers with different frames converging on the same finding reduces false-positive probability dramatically. The convergence itself is the signal, not any single review.

### Wrong

"Glokta flagged create_order as a Medium finding, Marvin flagged it as a HIGH follow-up, Brawne also called it out -- but none are blockers so we can defer all three to a follow-up issue."

### Right

"Three independent reviewers flagged the same thing with different framings. Fold the fix into this PR before merge."

### When This Pattern Applies

- Any PR that dispatches 3+ reviewer-role agents in parallel (Glokta/Brawne/Marvin, or Mulder/Holden/Cassandra, etc.) and a finding appears in 2+ outputs

### When NOT to Apply

- Single-reviewer passes (Tier 1, small fixes)
- When reviewers converge on a correctness nit rather than a design gap (the pattern is for convergence on material findings, not typos)

### Source

- Session 42f Task 3c -- Glokta + Brawne + Marvin + Claude Review CI all independently flagged the `crud_orders.create_order` / `crud_analytics.create_edge` optional-default precedent gap on PR #690. The 4-way convergence was what surfaced the gap. The finding was folded into the same PR rather than deferred.

---

## Pattern 59: Migration Round-Trip Testing on a Populated DB (ALWAYS for Non-Trivial Migrations)

**Severity:** HIGH -- Downgrade ordering bugs are structurally invisible to pure logic review. They manifest only when the DB actually refuses an operation.

### Problem / Trigger

You are writing an Alembic migration that drops/modifies columns, indexes, views, or constraints. Especially when the downgrade path recreates dependent objects.

### The Pattern / Rule

Before merging any Alembic migration that has a non-trivial downgrade path, **run `alembic upgrade head -> downgrade -1 -> upgrade head` against a populated test database**. Not a mocked test. A real PostgreSQL instance with at least one representative row per affected table.

### Why

Downgrade ordering bugs are structurally invisible to pure logic review. They manifest only when the DB actually refuses an operation due to dependency resolution. Pattern 49 (SCD race prevention) covers the upgrade path; Pattern 2 (SCD filtering) covers runtime query correctness; NEITHER catches "the recreated view depends on the column we are about to drop."

### Wrong

Logic review only: "The downgrade recreates current_balances view, then drops the execution_environment column. Each step looks right in isolation. LGTM."

### Right

Empirical test: `alembic downgrade -1` -> `ERROR: cannot drop column execution_environment of table account_balance because other objects depend on it` -> reorder: drop view THEN drop column THEN recreate view -> `alembic downgrade -1` succeeds -> `alembic upgrade head` succeeds -> merge.

### When This Pattern Applies

- Every migration that DROPS or ALTERS columns, indexes, views, or constraints AND has a downgrade path that recreates dependent objects
- Migrations that change schema semantics for money/trade tables

### When NOT to Apply

- Pure additive migrations (ADD COLUMN with DEFAULT, ADD INDEX, CREATE TABLE)
- Schema-only migrations with no row-level effects
- Tiny config-table updates

### Source

- Session 42f Task 3c, PR #690 migration 0051
- Samwise's original downgrade recreated `current_balances` view BEFORE dropping the column, causing `DROP COLUMN execution_environment` to fail with `DependentObjectsStillExist`
- Fix: recreate view AFTER column drop so its `SELECT *` captures the post-downgrade column list

---

## Pattern 60: AST Helper Scripts for Systematic Test Fixture Updates (MEDIUM for Cascading Signature Changes)

**Severity:** MEDIUM -- Manual Edit-by-Edit for 10+ sites is error-prone (missed sites, inconsistent style, kwarg-collision bugs).

### Problem / Trigger

A CRUD signature change (adding a required parameter, renaming, etc.) cascades into many test call sites (10+).

### The Pattern / Rule

Rather than editing each test call site manually, write a small AST-aware Python script that walks the test files and inserts the new parameter at every matching call. Use `ast.walk()` to find function calls, check for the parameter's presence (idempotency), and insert at the correct position.

### Why

Manual Edit-by-Edit for 10+ sites is error-prone (missed sites, inconsistent style, kwarg-collision bugs). An AST script handles all sites uniformly, runs in seconds, and is idempotent (re-running is safe). Also produces a deterministic count report that serves as verification.

### Wrong

Edit each of 30 call sites individually, track progress mentally, hope you did not miss any.

### Right

Write `.add_exec_env_kwarg.py` helper, run it across all target files, get "5 + 16 + 13 + 4 + 1 + 8 + 3 + 6 call sites modified" output, commit, delete the helper script.

### When This Pattern Applies

- Signature changes that affect 10+ test call sites across multiple files
- Cascading refactors
- Renaming a commonly-used helper

### When NOT to Apply

- Single-file changes (just use Edit)
- Signature changes where each call site needs different judgment about the new parameter value
- Anything touching production code logic (AST scripts do not understand semantic context well enough for prod refactors)
- When each test site has genuinely different intent and the new value must be reasoned per-site

### Source

- Session 42f Task 3c, PR #690
- Samwise's build changed 6 CRUD function signatures from optional-with-default to required
- PM wrote `.add_exec_env_kwarg.py` as a one-shot AST script, ran it in three batches (~60 test call sites across 8 files), total ~5 minutes vs ~45 minutes manual

---

## Pattern 61: git push --no-verify Repeat-Use Acceptance Criteria (ALWAYS for Hook Bypass)

**Severity:** MEDIUM -- Pre-push hooks are load-bearing. Bypassing the hook normalizes degraded safety. But infinitely rigid discipline produces worse workarounds.

### Problem / Trigger

Pre-push hook fails on a known pre-existing flake that is blocking a push whose diff is provably unable to affect the failing test.

### The Pattern / Rule

`git push --no-verify` is discouraged but permitted **once per session** when ALL FIVE criteria are met:

1. The diff is demonstrably unable to affect the failing test (trivially: `.md`, `.yml` workflow, `.github/ISSUE_TEMPLATE/*`)
2. The test failure reproduces across multiple runs (flake, not a regression)
3. An issue tracking the underlying test-quality problem exists
4. The bypass is documented in a PR comment with the rationale visible
5. The current session has not already used `--no-verify` once (no repeats within a session without explicit user sign-off)

### Why

Pre-push hooks are load-bearing -- they catch developer-environment issues before shared CI runners. Bypassing the hook normalizes degraded safety. But infinitely rigid discipline produces workarounds worse than the original problem (e.g., operators learning to avoid the hook via branch tricks). The 5-criteria rule threads the needle: allows escape valves when the bypass is genuinely safe, but makes each use deliberate, documented, and non-repeating.

### Wrong

"Hook failed on a flaky test. Push with --no-verify, move on." (implicit, undocumented, normalizing)

### Right

"Hook failed on a known pre-existing flake (#698 tracks it). My diff is YAML-only and provably unable to affect Python tests. Using --no-verify ONCE, documenting in PR comment, filing tracking issue, will not repeat this session without sign-off." (explicit, 5-criteria audit, transparent)

### When This Pattern Applies

- Truly one-off situations where a reproducible pre-existing flake blocks a trivial diff. Rare.

### When NOT to Apply

- Any code change (`.py`, `.sql`, any non-workflow file) -- the hook is checking exactly the class of thing the diff might break
- Repeated use within a session (stop and fix the hook instead)
- Large diffs where "unable to affect" is hard to prove
- Situations where the flake could plausibly be causally related to the diff

### Source

- Session 42f PR #697 commit 882f479
- CLI race test failure on YAML-only diff, filed as #698
- Dedicated feedback note: `feedback_no_verify_push_session_42.md`

---

## Pattern 62: In-Repo Per-Migration Rationale Docs (MEDIUM for Architecturally Significant Migrations)

**Severity:** MEDIUM -- Agent synthesis documents live outside the repo. Every "See findings_*.md" reference in a migration docstring is a dead link for anyone reading from a fresh clone.

### Problem / Trigger

You are shipping an architecturally significant migration that references design decisions from a multi-agent council or cross-cutting bug class.

### The Pattern / Rule

For any migration that (a) closes 2+ bug class issues, (b) changes schema semantics for money/trade tables, or (c) represents the completion of a multi-PR architectural arc, create a companion `docs/database/RATIONALE_MIGRATION_NNNN.md` file in the same PR. The migration's docstring should reference it first, before any external references.

### Why

Agent synthesis documents (e.g., `findings_622_686_synthesis.md`) live in the PM's local memory directory, outside the repo. Every `See findings_*.md` reference in a migration docstring is a dead link for anyone reading the code from a fresh clone. The 12-month archeologist needs a discoverable, version-controlled rationale that travels with the code.

### Wrong

Migration docstring says `See findings_622_686_synthesis.md for design rationale.` -- but that file lives at `~/.claude/projects/.../memory/` and is not in the repo.

### Right

Migration docstring says `See docs/database/RATIONALE_MIGRATION_0051.md for design rationale (in-repo). For the deeper agent-by-agent synthesis, see ~/.claude/projects/.../memory/findings_622_686_*.md (outside the repo, PM-local).`

### When This Pattern Applies

- Architecturally significant migrations
- Migrations closing a cross-cutting bug class
- Migrations that complete a multi-session arc
- Migrations where a future developer will ask "but WHY?"

### When NOT to Apply

- Routine migrations (ADD COLUMN for a new feature, simple INDEX additions, data migrations)
- If the rationale fits in the migration docstring itself in under 20 lines, do not split it out

### Source

- Session 42f PR #690 migration 0051 shipped `docs/database/RATIONALE_MIGRATION_0051.md` alongside the migration
- Claude Review on PR #690 escalated Marvin's "12-month archeology" concern

---

## Pattern 63: LATERAL Subquery for SCD Type 2 Temporal Matching (ALWAYS for Cross-Table SCD Correlation)

**Severity:** HIGH -- Using `row_current_ind = TRUE` for cross-table temporal correlation silently drops any row superseded between poll cycles.

### Problem / Trigger

You need to correlate rows across two SCD Type 2 tables by timestamp proximity.

### The Pattern / Rule

Use `CROSS JOIN LATERAL` with `ORDER BY ABS(EXTRACT(EPOCH FROM (ts1 - ts2))) LIMIT 1` to find the closest-in-time row. Do NOT filter by `row_current_ind = TRUE` on the source table -- use a time-window lookback + NOT EXISTS instead.

### Why

In SCD Type 2, `row_current_ind = TRUE` means "the latest version." When a new row arrives (~every 15-30s for pollers), the previous row flips to FALSE. Any service that only processes current rows will permanently miss any row superseded between poll cycles. The time-window + NOT EXISTS approach processes ALL recent rows regardless of their current/historical status.

### Wrong

```sql
-- DANGEROUS: drops any snapshot superseded before the writer runs
SELECT ms.*, gs.*
FROM market_snapshots ms
JOIN game_states gs ON gs.game_id = g.id AND gs.row_current_ind = TRUE
WHERE ms.row_current_ind = TRUE
```

### Right

```sql
-- SAFE: processes all recent snapshots, finds closest game_state by time
SELECT ms.*, gs.*
FROM market_snapshots ms
JOIN markets m ON ms.market_id = m.id
JOIN events e ON m.event_internal_id = e.id
JOIN games g ON e.game_id = g.id
CROSS JOIN LATERAL (
    SELECT gs_inner.*
    FROM game_states gs_inner
    WHERE gs_inner.game_id = g.id
    ORDER BY ABS(EXTRACT(EPOCH FROM (ms.row_start_ts - gs_inner.row_start_ts)))
    LIMIT 1
) gs
WHERE ms.row_start_ts > NOW() - INTERVAL '600 seconds'
  AND NOT EXISTS (
      SELECT 1 FROM temporal_alignment ta
      WHERE ta.market_snapshot_id = ms.id AND ta.game_state_id = gs.id
  )
```

### When This Pattern Applies

- Any cross-table temporal correlation where both tables use SCD Type 2 versioning (market_snapshots, game_states, game_odds, positions)
- Batch-processing services that must not miss any historical row

### When NOT to Apply

- Single-table queries where you genuinely only want the current row (`row_current_ind = TRUE` is correct for "show me the latest price")
- Real-time dashboards where only the current state matters

### Source

- Glokta review B1 on #722 (session 47)
- The writer's original query used `row_current_ind = TRUE` on both tables, which would silently drop any snapshot superseded before the writer ran

---

## Pattern 64: IS DISTINCT FROM in BEFORE UPDATE Triggers (ALWAYS for Immutability Triggers)

**Severity:** HIGH -- Using `!=` in trigger column comparison returns NULL when either operand is NULL, silently allowing the mutation.

### Problem / Trigger

You are writing a PostgreSQL BEFORE UPDATE trigger to enforce column immutability (block changes to specific columns while allowing others).

### The Pattern / Rule

Use `IS DISTINCT FROM` (not `!=` or `<>`) for column comparison in triggers.

### Why

`!=` returns NULL when either operand is NULL. A NULL condition in a trigger's IF block does not fire the RAISE, silently allowing the mutation. `IS DISTINCT FROM` treats NULL as a value: `NULL IS DISTINCT FROM NULL` is FALSE, `NULL IS DISTINCT FROM 'x'` is TRUE. This also enables no-op updates (`SET config = config`) to pass through, which is important for ORM bulk-save patterns that SET all columns.

### Wrong

```sql
-- DANGEROUS: NULL comparison returns NULL, silently allows mutation
IF NEW.config != OLD.config THEN
    RAISE EXCEPTION 'Cannot modify immutable column';
END IF;
```

### Right

```sql
-- SAFE: handles NULLs correctly and allows no-op updates
IF NEW.config IS DISTINCT FROM OLD.config
   OR NEW.strategy_version IS DISTINCT FROM OLD.strategy_version
THEN
    RAISE EXCEPTION 'Cannot modify immutable columns. Create a new version instead.';
END IF;
```

### When This Pattern Applies

- Any BEFORE UPDATE trigger that selectively blocks column changes
- Especially important when the protected columns could theoretically be NULL or when ORMs send full-row updates

### When NOT to Apply

- Triggers that block ALL updates (append-only enforcement) -- use a simple `RAISE EXCEPTION` with no column checks

### Source

- Migration 0056 (session 47, #371)
- Verified by integration test `test_noop_update_of_immutable_column_succeeds`

---

## Pattern 65: Mock the Entry Point, Not the Terminal Constructor (ALWAYS for Factory-Constructed Objects)

**Severity:** HIGH -- Wrong-level patches are no-ops that leave real code paths running. Tests appear green while real pollers/clients hit real APIs in the background.

### Problem / Trigger

You are writing a test that patches a class when the code under test constructs instances via a factory function (`create_*`, `build_*`, `make_*`, `load_*`, `get_*_instance`).

### The Pattern / Rule

Patch the **factory**, not the class the factory instantiates. The factory is the entry point; the class is downstream of all the construction complexity the factory exists to hide.

### Why

Factories exist precisely to hide construction complexity from callers (rate limiters, circuit breakers, real pollers, background threads). That complexity is downstream of the class constructor, so a `patch("module.TheClass")` call stops nothing -- the factory has already done its work before `TheClass()` gets called. The mock is a no-op; the test "passes" while the real behavior runs underneath.

Session 49 discovered this systemic anti-pattern across 8 test files (umbrella #764): scheduler CLI tests patched `ServiceSupervisor` while the CLI called `create_supervisor()`. Tests "passed" for months while real `KalshiMarketPoller` and `ESPNGamePoller` instances were being constructed and started in the background.

### Wrong

```python
# CLI calls create_supervisor() which constructs ServiceSupervisor internally.
# Patching the class is a no-op -- factory still creates real pollers.
with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock:
    result = runner.invoke(app, ["scheduler", "start", "--supervised"])
    assert result.exit_code == 0  # "passes" while real Kalshi pollers started in background
```

### Right

```python
# Patch the factory -- stops all downstream construction.
with patch("precog.schedulers.service_supervisor.create_supervisor") as mock_factory:
    mock_factory.return_value = MagicMock(start_all=MagicMock(return_value=None))
    result = runner.invoke(app, ["scheduler", "start", "--supervised"])
    assert result.exit_code == 0
    mock_factory.assert_called_once()  # invariant -- fail loud if mock is no-op
```

### When This Pattern Applies

- Any code under test that constructs expensive objects through a factory function
- Common Python patterns: `make_*`, `create_*`, `build_*`, `load_*`, `get_*_instance`
- Especially important when the factory attaches background threads, opens sockets, or wires circuit breakers

### When NOT to Apply

- Code that directly instantiates classes without a factory wrapper -- in those cases, patching the class IS the entry point

### Source

- Session 49 #764 discovery; Session 50 retrofit PR #758/#747
- `feedback_mock_factory_not_class.md`; CLAUDE.md Critical Pattern #7 (external API test mocking)
- See also: Pattern 22 (VCR for real API responses), Pattern 67 (`assert_called` invariant), Pattern 43 (Mock Schema Fidelity)

---

## Pattern 66: Strict Exit-Code Assertions as Decay Detection (ALWAYS for CLI Tests)

**Severity:** HIGH -- Loose exit-code assertions (`in [0, 1, 2]`) hide every other kind of test decay underneath. The Session 50 inventory found 12 integration tests using nonexistent Typer flags that had been exit-2-from-Typer in disguise for months.

### Problem / Trigger

You are writing a test that invokes a Typer/Click CLI command via `CliRunner.invoke`.

### The Pattern / Rule

Every CLI test MUST assert a specific exit code -- usually `exit_code == 0` for happy paths, or the specific expected error code. Loose assertions like `exit_code in [0, 1, 2]` or `exit_code != 3` are forbidden.

### Why

Loose exit-code assertions are the **universal decay concealer**. They silently accept:

- **Typer parser rejection (exit 2)** when a flag is renamed -- test "passes" while executing zero code
- **Early validation failure (exit 1)** when a dependency is missing -- test "passes" while testing nothing
- **Uncaught exception cleanup (exit 1)** when the code path is broken -- test "passes" while code is broken

Session 50's inventory found 12 integration tests using nonexistent Typer flags (`--poller`, `--interval`, `--league`, `--save`, `--format`, `--no-foreground`) that had been exit-2-from-Typer for months. The loose `exit_code in [0, 1, 2]` assertions made them green on every run while providing zero coverage. The S75 CLI flag existence linter (#769) and the loose-assertion ratchet (#808) exist specifically to mechanize this rule.

### Wrong

```python
result = runner.invoke(app, ["scheduler", "start", "--poller", "espn"])
assert result.exit_code in [0, 1, 2]  # --poller doesn't exist; this is exit 2 permanently
```

### Right

```python
result = runner.invoke(app, ["scheduler", "start", "--supervised"])
assert result.exit_code == 0, f"exit={result.exit_code}, output={result.output}"
```

### When This Pattern Applies

- Every test using `CliRunner.invoke`, without exception

### When NOT to Apply

- If the test genuinely doesn't know what the correct exit code should be, the test shouldn't assert on exit code at all -- it should assert on something meaningful (a mock being called, a specific output substring, a file being written)

### Source

- Session 50 #764 retrofit; #808 loose-assertion ratchet; #769 S75 CLI flag existence linter
- See also: Pattern 65 (factory-level mocking), Pattern 67 (`assert_called` invariant)

---

## Pattern 67: `assert_called` as the Fail-Loud Invariant for Mocks (ALWAYS for patch()-Based Tests)

**Severity:** HIGH -- A mock that is never called provides zero coverage. Without a `assert_called` check, the test cannot distinguish "code was exercised, mock intercepted it" from "code was never reached, mock is inert."

### Problem / Trigger

You are writing any test that patches a symbol with `patch(...)` and expects the patched code to be exercised.

### The Pattern / Rule

Every `patch()` must be paired with an assertion that the mock was actually called. Use `mock.assert_called_once()` for single-invocation, `.call_count == N` for multi-invocation, `.assert_called_with(...)` for argument verification. Tests without `assert_called` are permissive to silently-dead mocks.

### Why

Session 50's #764 retrofit found this exact failure mode across 8 test files: mocks attached to wrong-level targets, tests "passing" because the mock was irrelevant to the code path. `assert_called` is the fail-loud invariant that catches wrong-level patches, typo'd patch targets, and code-path dead-ends.

### Wrong

```python
with patch("precog.schedulers.ESPNGamePoller") as mock_espn:
    result = runner.invoke(app, ["poll-once", "--no-kalshi"])
    assert result.exit_code == 0
    # No assert_called -- if ESPNGamePoller is never instantiated, test still "passes"
```

### Right

```python
with patch("precog.schedulers.ESPNGamePoller") as mock_espn_class:
    mock_instance = MagicMock()
    mock_espn_class.return_value = mock_instance

    result = runner.invoke(app, ["poll-once", "--no-kalshi"])

    assert result.exit_code == 0
    mock_instance.poll_once.assert_called_once()  # fail loud if no-op
```

### When This Pattern Applies

- Every test that expects a mock to be exercised

### When NOT to Apply

- Defensive mocks (patching a side effect to prevent real execution regardless of whether the code path reaches it). These should be documented with a comment explaining the defensive intent, e.g., `# Defensive: prevent accidental real network call`.

### Source

- Session 50 retrofit, Joe Chip's P1 findings during code review
- See also: Pattern 65 (factory-level mocking), Pattern 66 (strict exit codes), Pattern 46 (Mock Patch Migration)

---

## Pattern 68: Preserve-X Requires X Exists (ALWAYS for Multi-Session Preservation Framing)

**Severity:** MEDIUM -- A preservation step protecting nothing is cargo cult. The cost of confirming X exists is about 30 seconds of grep. The cost of planning preservation work for an absent capability is the whole meta-plan being wrong.

### Problem / Trigger

You are planning a task framed as "preserve X during refactor" where X is a capability, a test class, a coverage layer, or any other artifact expected to exist in the codebase.

### The Pattern / Rule

Before planning preservation work, **verify that X exists**. Run the grep, count the instances, confirm the thing is there. Preservation of an absent capability is cargo cult work.

### Why

Session 49 framed the #764 retrofit as "mark tests with `@pytest.mark.live_api` to preserve drift detection, then convert the rest to VCR." The assumption was that some tests on this surface were intentional live contract tests catching Kalshi/ESPN API format drift. Session 50's inventory found **zero** tests marked `@pytest.mark.live_api` or otherwise intentional live contracts. The "preservation" step was protecting a capability that didn't exist.

This is not unique to test retrofits -- the pattern applies to any "preserve X while doing Y" task: refactors, migrations, deprecations, consolidations. The asymmetry between the 30-second verification cost and the cost of building a whole preservation plan around an absent thing makes this a no-brainer prerequisite.

### Wrong

```
Session 49 plan: "Step 1: mark real-HTTP tests with @pytest.mark.live_api
                  to preserve drift detection during the retrofit."
[never confirmed any real-HTTP tests existed]

Session 50 inventory: "0 tests with live_api marker. Whole preservation
                       framing was based on an absent thing."
```

### Right

```
Session 49 plan: "Step 0: grep tests/ for @pytest.mark.live_api usage.
                  Count: N.
                  Step 1 (if N > 0): mark additional real-HTTP tests with the
                  marker to preserve drift detection.
                  Step 1 (if N == 0): note the zero-coverage finding as a
                  separate issue before proceeding with retrofit."
```

### When This Pattern Applies

- Any multi-session planning task with a "preserve/protect/keep X" requirement in the spec
- Retrofits, migrations, consolidations, deprecations, architecture splits

### When NOT to Apply

- Preservation tasks where X is trivially observable in the code (e.g., "preserve existing tests" when the retrofit is additive -- tests you're not touching will obviously stay)

### Source

- Session 50 inventory finding -- the zero live-contract-tests discovery on #764
- See also: Pattern 72 (Scope Correction Via Mechanical Pre-ANNOUNCE Scoping), Pattern 47 (Verify Schema Before Fixing Pattern Violations)

---

## Pattern 69: Post-Retrofit Cosmetic-Coverage Check (ALWAYS for Test Mock-Layer Retrofits)

**Severity:** MEDIUM -- A retrofit that mocks away the thing the test was testing produces a **tier-cosmetic** test -- still green in CI, still counted toward coverage metrics, but covering nothing meaningful. Transparency about cosmetic-coverage regression is what separates a retrofit from a green-CI lie.

### Problem / Trigger

You are retrofitting an existing test to change its mock layer, fixture shape, or assertion structure. Especially risky: tests in `tests/race/`, `tests/chaos/`, `tests/performance/`, `tests/stress/` where the tier label makes a semantic claim about what the test exercises.

### The Pattern / Rule

For every test you retrofit, explicitly answer: *"After my retrofit, does this test still cover what its name and docstring claim it covers?"* If the answer is no, flag it in your report rather than silently letting it become cosmetic. The pattern isn't "never retrofit tests that might become cosmetic" -- it's "when a retrofit leaves a test cosmetic, say so explicitly and file it for design decision."

### Why

Session 50's retrofit produced 7 cosmetic-coverage candidates: performance tests measuring CLI dispatch overhead instead of real scheduler latency; chaos tests moved from supervisor-layer chaos to db-layer chaos; property tests narrowed to sidestep module-global pollution. These were flagged transparently as #767 follow-ups -- not silently accepted as retrofit wins. Without the explicit check, the retrofit would have been marketed as "all green" while the race/chaos/performance test tier had quietly collapsed into a pile of dispatch-only tests.

### Wrong (retrofit that hides cosmetic regression)

```python
# Before:
def test_supervisor_random_failures():
    """Chaos: supervisor crashes randomly, CLI recovers gracefully."""
    # Patched ServiceSupervisor at wrong level; real pollers ran.
    # Test "passed" because real code handled real chaos.
    ...

# After retrofit (silent cosmetic collapse):
def test_supervisor_random_failures():
    """Chaos: supervisor crashes randomly, CLI recovers gracefully."""
    # Now mocks create_supervisor at correct level.
    # But the mock just returns success -- no chaos is injected.
    # Test still "passes" but no longer tests chaos at the supervisor layer.
    ...
```

### Right (transparent flagging)

```python
# After retrofit, flagged for PM decision in follow-up issue #767:
def test_supervisor_random_failures():
    """CLI chaos: db-IPC layer injects random failures, CLI handles gracefully.

    NOTE: Originally tested supervisor-layer chaos via real pollers.
    Post-retrofit, chaos is injected at crud_schedulers.list_scheduler_services.
    The TestSchedulerChaos class name still suggests supervisor-level chaos,
    which no longer runs. See #767 for rename/rewrite decision.
    """
    with patch("precog.database.crud_schedulers.list_scheduler_services") as mock_crud:
        mock_crud.side_effect = random_failure_side_effect
        # ...
```

### When This Pattern Applies

- Any test retrofit that changes the layer at which mocks intercept the code path
- Especially: tests in `tests/race/`, `tests/chaos/`, `tests/performance/`, `tests/stress/` where the tier label makes a semantic claim
- Ties directly into T41 audit capability 6 (test tier classification)

### When NOT to Apply

- Purely mechanical retrofits that don't change the layer semantics (e.g., swapping an equivalent mock target path, renaming an import)

### Source

- Session 50 #764 retrofit; issue #767 follow-up; Nagilum's builder report
- See also: T41 audit capability 6 (test tier classification), Pattern 65 (factory-level mocking), Pattern 67 (`assert_called` invariant)

---

## Pattern 70: Convergent-Reviewer Signal Rule (ALWAYS for Multi-Reviewer Dispatch)

**Severity:** HIGH -- When two independent reviewers with different cognitive frames land on the same finding without shared conversation context, treat it as load-bearing. This is Pattern 58's rule extended to the two-reviewer case, and it is the fastest anti-deferral signal available in the pipeline.

### Problem / Trigger

You dispatched two or more agents with different cognitive frames (e.g., Spock + Ripley, Joe Chip + Ripley, Holden + Marvin) to review the same diff in parallel, and 2+ of them independently flagged the same finding.

### The Pattern / Rule

Treat the convergent finding as **structurally validated** -- fold the fix into the current PR before merge rather than deferring to a follow-up issue. This applies even if any individual reviewer would have rated the finding non-blocking. The convergence itself is the signal, not any single review.

### Why

Individual reviewer findings have variance. A single reviewer might be wrong, overfit to their frame, or miss context. Two reviewers with different frames converging on the same finding drops false-positive probability dramatically -- and the convergence is structural evidence the finding is real, not frame-artifact. Session 51's PR #786 (Hook 1.2 `.env`/`.envrc` block) demonstrated this: Spock (APPROVE WITH COMMENTS) flagged the `.envrc` gap; Ripley (CLEAR WITH OBSERVATIONS) independently flagged `.envrc` as a convergent finding. PM trusted the signal immediately, applied the regex fix `(^|/)\.env(rc)?($|\.)`, and did not defer.

Pattern 58 covered the three-reviewer case. Pattern 70 is the two-reviewer case, which fires far more often in normal Tier 2 pipelines (Joe Chip + Ripley, Glokta + Marvin, etc.).

### Wrong

"Spock flagged `.envrc` as a gap. Ripley also flagged `.envrc` as a gap. Both rated it non-blocking observational. I'll file it as a follow-up issue and merge the PR as-is."

### Right

"Two independent reviewers with different frames (correctness + sentinel) converged on `.envrc`. That's a load-bearing signal. Apply the regex fix `(^|/)\.env(rc)?($|\.)` before merge; add `.envrc` to `.gitignore`; 12-case regex sweep to verify; merge the PR with the fix folded in."

### When This Pattern Applies

- Any Tier 2 PR that dispatches 2+ reviewer-role agents in parallel
- Especially Reviewer + Sentinel pairs (Joe Chip + Ripley), correctness + structural pairs (Spock + Ripley), or design + construction pairs (Holden + Samwise -> Joe Chip)

### When NOT to Apply

- Single-reviewer passes (Tier 1, small fixes, Micro-ANNOUNCE dispatches)
- When reviewers converge on a correctness nit rather than a design/coverage gap (the pattern is for convergence on material findings, not typos)
- When the two "reviewers" share conversation context (e.g., two sequential reviews by the same agent persona) -- no independence, no signal

### Source

- Session 51 PR #786 -- Spock + Ripley independently flagged `.envrc` gap; PM applied regex fix before merge
- See also: Pattern 58 (Triple-Reviewer Convergence as Structural Validation) -- the three-reviewer case; Pattern 71 (Verify High-Confidence Sentinel Claims) -- the complementary skeptical-verification rule for non-convergent high-confidence claims

---

## Pattern 71: Verify High-Confidence Sentinel Claims Via Code Inspection Before Acting (ALWAYS for Sentinel-Frame Findings)

**Severity:** MEDIUM -- Sentinel-frame agents (Ripley, Cassandra) are deliberately skeptical and sometimes surface high-confidence findings with incorrect mechanistic claims. PM should verify the mechanism via direct code read before acting, especially when the finding would force a priority pivot.

### Problem / Trigger

A sentinel-frame agent (Ripley, Cassandra, or similar) has surfaced a finding with a "Confidence: high" tag and a specific mechanistic claim (e.g., "this fixture causes cascading pollution across X tests," "this function leaks state between runs"). The finding would change session priorities if correct.

### The Pattern / Rule

Before pivoting the session to address the finding, **read the cited code directly** and trace the claimed mechanism. If the mechanism doesn't match the code, downgrade the finding to docstring-clarity or observability work rather than structural fix. Confidence tags are agent-frame artifacts, not verification.

### Why

Session 51 T41 audit on `src/precog/schedulers/` surfaced a Ripley F1 finding marked "Confidence: high": the fixture `_cleanup_scheduler_cli_module_globals` allegedly caused cascading test pollution across 60+ tests in the same file. PM read the fixture code, verified the inductive chain starts at `None` on fixture entry, and confirmed no pre-fixture mutation exists under standard pytest semantics. The finding was real (docstring was unclear about the exit-vs-entry state) but the claimed mechanism (cascading pollution) was wrong. PM dispositioned as F1 docstring clarity (#785), not as a structural fix, and kept the session priorities intact.

Without this verification step, the PM would have pivoted to a ghost structural fix and dropped the actual load-bearing work.

### Wrong

"Ripley flagged the fixture as cascading-pollution with Confidence: high. Treat as P0, pivot the session to rebuild the fixture, defer everything else."

### Right

"Ripley flagged the fixture as cascading-pollution with Confidence: high. Read `conftest.py` fixture code -- setup starts at `None` from standard pytest function-scope semantics, no pre-fixture mutation observed. Mechanism claim doesn't match the code. Disposition as F1 docstring clarity (#785), keep session priorities, note learned pattern for future sentinel triage."

### When This Pattern Applies

- Any sentinel-frame finding marked "Confidence: high" or "Confidence: critical"
- Especially when the finding would force a session-priority pivot
- Especially when the finding makes a specific mechanistic claim about code behavior (not a code-smell observation)

### When NOT to Apply

- Sentinel findings about design/architecture judgment (no mechanism to verify; disposition on merit)
- Sentinel findings corroborated by a convergent second reviewer (per Pattern 70, convergence is its own signal)
- Trivially-checkable low-severity findings (cost of verification approximates cost of acting; just act)

### Source

- Session 51 T41 audit on `src/precog/schedulers/` -- Ripley F1 cascading-pollution claim; PM verified via code read, dispositioned as docstring clarity
- See also: Pattern 70 (convergent-reviewer signal rule), Pattern 47 (Verify Schema Before Fixing Pattern Violations), Pattern 58 (Triple-Reviewer Convergence)

---

## Pattern 72: Scope Correction Via Mechanical Pre-ANNOUNCE Scoping (ALWAYS for Tier 2 Dispatches)

**Severity:** MEDIUM -- Reading target files before the ANNOUNCE step often shrinks a planned Tier 2 scope substantially. This is a cheap pre-flight check that prevents over-budgeting agents on work that's already partially done.

### Problem / Trigger

You are about to ANNOUNCE a Tier 2 dispatch with a plan that references specific files, hook rules, issue line items, or patterns to add. The plan was written before reading the target files in their current state.

### The Pattern / Rule

Before the ANNOUNCE, spend 1-3 minutes reading the target files (or running grep on the relevant symbols). Compare the actual state to the plan. If 30%+ of the plan is already done or unnecessary, update the ANNOUNCE to reflect the real scope -- don't deploy agents on work that doesn't need doing.

### Why

Session 51 surfaced this pattern twice:

- **Hook PR 1** was planned as "consolidate 3 hooks (Hook 1.1 credential block, Hook 1.2 `.env` block, Hook 1.3 scoped secrets)." Pre-ANNOUNCE scoping found Hooks 1.1 and 1.3 were already implemented in `.pre-commit-config.yaml`. Actual scope: "add Hook 1.2 only." Diff shrank from expected ~150 LoC consolidation to +28/-0 across 2 files.
- **PR #781 (follow-up bundle)** was planned as "10 cleanup items." Pre-scoping found item 1 (a #773 fix) was already resolved. Actual scope: 9 items.

Agent deployments are expensive in session budget and attention. Shipping ghost work on a Builder prompt that says "do X, Y, Z" when Y is already done wastes a full agent cycle and pollutes the review queue with phantom diffs.

### Wrong

"ANNOUNCE: Tier 2 T11. Dispatching Samwise (Builder) -> Joe Chip (Reviewer) -> Ripley (Sentinel) to consolidate the 3 pre-commit hooks from Hook 1.1/1.2/1.3. Estimated 90 min, ~150 LoC diff."

[Builder comes back, finds 2/3 already exist, delivers +28/-0 diff. Reviewer & Sentinel both spend real time checking work that was never needed.]

### Right

"Pre-ANNOUNCE scoping: read `.pre-commit-config.yaml`. Hook 1.1 and Hook 1.3 already present. Revised scope: add Hook 1.2 only. Dispatching Samwise to add ~30 LoC for `.env`/`.envrc` block. Trimmed review cycle: Spock for correctness, Ripley for sentinel."

### When This Pattern Applies

- Any Tier 2 dispatch where the plan was drafted more than a session ago (memory-drift risk)
- Any multi-step plan referencing specific files, issue line items, or pattern candidates
- Any plan citing a numeric scope ("3 hooks," "10 items," "5 files") -- the number itself is a prompt for verification

### When NOT to Apply

- Purely greenfield work (no existing files to scope against)
- Micro-ANNOUNCE dispatches where the scope is already <75 LoC and trivially verifiable in-prompt
- When the plan was drafted and validated in the same session with no intervening commits

### Source

- Session 51 Hook PR 1 scope shrink (3 hooks -> 1 hook, +28/-0 diff)
- Session 51 PR #781 scope shrink (10 items -> 9 items)
- See also: Pattern 68 (Preserve-X Requires X Exists), Pattern 47 (Verify Schema Before Fixing Pattern Violations), protocols.md ANNOUNCE step

---

## Pattern 73: "Keep Heading, Replace Body with Pointer" -- Structural Refactor Idiom (ALWAYS for Memory/Doc File Extraction)

**Severity:** MEDIUM -- when refactoring a growing markdown file by extracting sections to topic files, preserving the section heading with a one-line pointer (instead of deleting the section) keeps existing anchor-style cross-references working throughout the codebase.

### Problem / Trigger

A growing markdown file (MEMORY.md, protocols.md, long guides) has sections that need to move to topic files. Multiple memory files, source files, and PR descriptions reference those sections via anchor syntax: `[text](file.md#section-anchor)` or `file.md § Section`.

Naive extraction removes the section entirely from the source file → every cross-reference in the codebase becomes a broken link. The refactor shrinks the source file but creates a wave of broken-reference debt.

### The Pattern / Rule

When extracting a section to a topic file:

1. Copy the full section verbatim to the new topic file (with proper frontmatter).
2. In the source file, **keep the section heading** (`## Section Name`) exactly as-is -- same text, same hierarchy level, same markdown-anchor behavior.
3. Replace the section **body** with a single-line pointer: `See [topic_file.md](topic_file.md) for full content.`

The preserved heading continues to function as an anchor target. Anchor-style links (`#section-anchor`) keep resolving. Readers land on the pointer and click through for detail.

### Why

Session 62 S79 first-fire refactored MEMORY.md (565 → 141 lines, -75%) and protocols.md (703 → 592 lines, -16%) via 15 extractions (8 session_NN_actual.md files + 6 checklist_*.md files + 1 history archive). Zero cross-references broke. Affected links that continued resolving:

- `protocols.md § Delegation Workflow` (referenced from roster_agents.md + feedback_process_adherence.md)
- `protocols.md § Hierarchical Council Protocol` (referenced from roster_agents.md)
- `protocols.md § Mock Fidelity Rule` (referenced from feedback_mock_factory_not_class.md + feedback_test_pattern_compliance.md + patterns_to_add_42e.md)
- `protocols.md § Flair Protocol` (referenced from multiple memory files)
- MEMORY.md session blocks referenced informally in conversation transcripts

Alternative approaches fail:

- **Delete section entirely** → every anchor-style reference breaks. Grep-and-fix across the codebase is tedious and prone to missing uses.
- **Keep section body entirely** → file doesn't shrink. Defeats the refactor's purpose.
- **Move the heading with the content** → `protocols.md#section-anchor` now points at a nonexistent anchor. Same breakage as "delete entirely."

### Wrong

```markdown
# Before extract:
## Delegation Workflow
1. Select agent
2. Announce to user
3. Build prompt
... [30 lines]

# After naive extract (heading + body deleted):
# (nothing -- section is gone)
```

Broken: `[Delegation Workflow](protocols.md#delegation-workflow)` in `roster_agents.md:8` now links to nothing.

### Right

```markdown
# Before extract:
## Delegation Workflow
1. Select agent
2. Announce to user
... [30 lines]

# After correct extract (heading preserved, body replaced with pointer):
## Delegation Workflow

See [checklist_delegation.md](checklist_delegation.md) for the full 7-step workflow.
```

Heading preserved → `protocols.md#delegation-workflow` anchor still resolves → reader lands on the pointer line and clicks through.

### When This Pattern Applies

- S79 file-size discipline refactors (MEMORY.md / protocols.md / growing-guide extractions)
- Moving stable, cross-referenced sections from growing markdown files to dedicated topic files
- Any refactor where `#anchor` links or `§ Section` references exist in the codebase

### When NOT to Apply

- Sections with NO external references (verify via grep first; safe to delete cleanly)
- Files without anchor-style cross-reference culture (plain copy/move is fine)
- Transient content (session-specific sections, temporary planning, superseded notes) -- these are often better to delete with an explicit archive note than to preserve as ghost-heading pointers
- When the "heading" is generated / transient (auto-generated indexes, TOC-only headings with no anchor callers)

### Source

- Session 62 S79 first-fire -- The Librarian's refactor (MEMORY.md 565→141 lines, protocols.md 703→592 lines, 15 new topic files, zero broken cross-references)
- See also: Pattern 72 (Scope Correction), S79 trigger (roster_triggers.md § Process & Meta), checklist_delegation.md (canonical extraction example), session_62_actual.md

---

V1.32 Updates:
- Added Pattern 73 ("Keep Heading, Replace Body with Pointer" -- Structural Refactor Idiom) -- preserve heading + one-line pointer when extracting sections to topic files, so anchor-style cross-references keep resolving. Source: Session 62 S79 Librarian refactor (MEMORY.md 565→141, protocols.md 703→592, 15 extractions, zero broken cross-references).
- Added Pattern 65 (Mock the Entry Point, Not the Terminal Constructor) -- factory-level mocking rule operationalizing CLAUDE.md Critical Pattern #7. Source: Session 49 discovery + Session 50 #764 retrofit.
- Added Pattern 66 (Strict Exit-Code Assertions as Decay Detection) -- forbids loose `exit_code in [0, 1, 2]` asserts. Source: Session 50 #764 retrofit; complements #808 ratchet and #769 CLI flag linter.
- Added Pattern 67 (`assert_called` as the Fail-Loud Invariant for Mocks) -- every `patch()` paired with call assertion. Source: Session 50 retrofit, Joe Chip P1 findings.
- Added Pattern 68 (Preserve-X Requires X Exists) -- verify preservation targets before planning preservation work. Source: Session 50 inventory zero-coverage finding on #764.
- Added Pattern 69 (Post-Retrofit Cosmetic-Coverage Check) -- explicit flagging of cosmetic-tier collapses post-retrofit. Source: Session 50 #767 follow-ups (7 cosmetic candidates flagged).
- Added Pattern 70 (Convergent-Reviewer Signal Rule) -- two-reviewer convergence variant of Pattern 58. Source: Session 51 PR #786 Spock+Ripley `.envrc` convergence.
- Added Pattern 71 (Verify High-Confidence Sentinel Claims Via Code Inspection Before Acting) -- skeptical-verification rule for sentinel-frame findings. Source: Session 51 T41 schedulers audit, Ripley F1 dispositioned as #785 docstring clarity.
- Added Pattern 72 (Scope Correction Via Mechanical Pre-ANNOUNCE Scoping) -- read target files before agent dispatch. Source: Session 51 Hook PR 1 (3->1 hook) + PR #781 (10->9 items) scope shrinks.

V1.31 Updates:
- Added Pattern 52 (SCD Race Retry Helper Structure) -- 7-condition retry pattern for money-touching SCD code. Source: Session 42d PR #631.
- Added Pattern 53 (Race Tests Must Assert The Race Actually Fired) -- caplog assertion that contested code path executes. Source: Session 42d PR #631.
- Added Pattern 54 (Verifier Scripts as Investigation Deliverables) -- executable scripts over one-shot findings. Source: Session 42d #335.
- Added Pattern 55 (Fee-Aware Orderbook Edge Calculation) -- subtract fees + use correct orderbook side. Source: Session 42d/42f, corrected from vig to fees.
- Added Pattern 56 (JSONB + Decimal Round-Trip via Custom Encoder) -- custom dumps for psycopg2 Json. Source: Session 42e PR #671.
- Added Pattern 57 (Close-by-Business-Key Inside Retry Closure) -- use business key not surrogate inside retries. Source: Session 42e PR #665.
- Added Pattern 58 (Triple-Reviewer Convergence as Structural Validation) -- multi-agent convergence signal. Source: Session 42f PR #690.
- Added Pattern 59 (Migration Round-Trip Testing on a Populated DB) -- empirical upgrade/downgrade/upgrade test. Source: Session 42f PR #690.
- Added Pattern 60 (AST Helper Scripts for Systematic Test Fixture Updates) -- AST scripts for cascading refactors. Source: Session 42f PR #690.
- Added Pattern 61 (git push --no-verify Repeat-Use Acceptance Criteria) -- 5-criteria rule for hook bypass. Source: Session 42f PR #697.
- Added Pattern 62 (In-Repo Per-Migration Rationale Docs) -- companion docs for architecturally significant migrations. Source: Session 42f PR #690.
- Added Pattern 63 (LATERAL Subquery for SCD Type 2 Temporal Matching) -- CROSS JOIN LATERAL for cross-table SCD correlation. Source: Session 47 #722.
- Added Pattern 64 (IS DISTINCT FROM in BEFORE UPDATE Triggers) -- NULL-safe comparison in immutability triggers. Source: Session 47 #371.
- Updated Pattern 2 (Dual Versioning System) with anti-pattern warning for same-transaction read-after-write with row_current_ind filter. Source: Session 42e #629.

V1.30 Updates:
- Added Pattern 47 (Verify Schema Before Fixing Pattern Violations) — false positive prevention for code review findings. Source: Session 42c #595 false positive (teams table is not SCD Type 2).
- Added Pattern 48 (Use dataclasses.replace() for Frozen Dataclass Updates) — Python idiom for immutable record updates. Source: Session 42c PR #601 backup orchestrator fix.
- Added Pattern 49 (SCD Race Condition Prevention with FOR UPDATE) — money-touching code pattern for SCD Type 2 close→insert sequences. Source: Session 42c #587 account_balance race fix.
- Added Pattern 50 (Reverse-Engineer Strategy via Closed Trade Lifecycle) — research methodology for analyzing external traders. Source: Session 42c ColdMath analysis.

V1.29 Updates:
- Added Pattern 46 (Mock Patch Migration on Module Extraction) documenting the systematic approach to migrating mock.patch targets when splitting god objects into domain modules. Discovered during session 38 CRUD decomposition: 302 patches across 9 files initially, then 145 imports across 55 files for Option B.

V1.3 Updates:
- Added Pattern 12 (Test Fixture Security Compliance) documenting project-relative test fixture pattern from PR #79, ensuring test fixtures comply with path traversal protection (CWE-22) implemented in PR #76.
- Added Pattern 13 (Test Coverage Quality - Mock Sparingly, Integrate Thoroughly) documenting critical lessons from TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md: when to use mocks vs real infrastructure, ALWAYS use conftest.py fixtures, 8 required test types, coverage standards, test review checklist. Prevents false confidence from mock-based tests that pass despite critical bugs (Strategy Manager: 17/17 tests passing with mocks, 13/17 failing with real database).
─────────────────────────────────────────────────
