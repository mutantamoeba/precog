# Development Philosophy

---
**Version:** 1.3
**Created:** 2025-11-07
**Last Updated:** 2025-11-17
**Changes in V1.3:**
- **Added Section 1 Subsection: Test Quality - When Tests Pass But Aren't Sufficient** - Comprehensive lessons learned from Phase 1.5 TDD failure
- Documents real-world example: Strategy Manager 17/17 tests passing but 13/17 failed with real database (77% failure rate)
- Root cause: over-reliance on mocks, small test suite false confidence, tests written after implementation
- 6 lessons learned: (1) Mock sparingly integrate thoroughly, (2) Use test infrastructure (conftest.py), (3) Write tests BEFORE implementation, (4) Need 8 test types not just unit tests, (5) Stress test critical resources, (6) Coverage % ≠ test quality
- Includes anti-pattern examples (mocking internal infrastructure), correct patterns (real database fixtures), test review checklist, red flags
- Cross-references: TEST_REQUIREMENTS_COMPREHENSIVE_V2.1.md (REQ-TEST-012 through REQ-TEST-019), TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md, TESTING_GAPS_ANALYSIS.md
**Changes in V1.2:**
- **Added Section 10: Security-First Testing** - Comprehensive principle for testing WITH security validations (not around them)
- Documents "tests validate security works correctly, not that code works when security disabled"
- Real-world example from PR #79 (9/25 tests failing → 25/25 passing after fixing fixtures to comply with path traversal protection)
- Includes rules: never bypass security in tests, validate security boundaries, fix tests when security breaks them
- Integration with development workflow (phase planning, during development, PR review, phase completion)
- Cross-references: Pattern 4 (Security), Pattern 12 (Test Fixture Security Compliance), SECURITY_REVIEW_CHECKLIST, PR #76 (CWE-22 protection), PR #79 (test fixture updates)
- Renumbered Section 10 → Section 11 (Anti-Patterns to Avoid)
- Renumbered Section 11 → Section 12 (Test Coverage Accountability)
**Changes in V1.1:**
- **ANTI-PATTERNS SECTION ADDED:** New Section 11 - Anti-Patterns to Avoid (7 anti-patterns documented)
- Added real examples from Phase 1 test coverage work (Partial Thoroughness, Percentage Point Blindness, etc.)
- Added Anti-Pattern Detection Checklist (run before marking work complete)
- Added "Option B Development Approach" subsection (Test-Driven vs Feature-Driven)
- Updated Summary Checklist to include anti-pattern awareness
- Added validation workflows and prevention strategies for each anti-pattern
**Purpose:** Core principles guiding Precog development
**Target Audience:** All developers working on Precog
**Status:** ✅ Active - Follow in ALL development work
---

## Overview

This document defines the foundational development principles for Precog. These principles guide **every decision** from architecture to implementation to documentation.

**Why This Document Matters:**
- **Consistency:** All developers follow the same patterns
- **Quality:** Principles prevent common mistakes
- **Onboarding:** New developers understand "the Precog way"
- **Decision-Making:** When in doubt, refer to these principles

**How to Use:**
1. **Before implementation:** Review relevant principles
2. **During code review:** Check adherence to principles
3. **Before phase completion:** Validate all principles followed
4. **When making decisions:** Consult philosophy for guidance

---

## Table of Contents

1. [Test-Driven Development (TDD)](#1-test-driven-development-tdd)
2. [Defense in Depth (DID)](#2-defense-in-depth-did) ⚠️ **CORE PRINCIPLE**
3. [Documentation-Driven Development (DDD)](#3-documentation-driven-development-ddd)
4. [Data-Driven Design](#4-data-driven-design)
5. [Fail-Safe Defaults](#5-fail-safe-defaults)
6. [Explicit Over Clever](#6-explicit-over-clever)
7. [Cross-Document Consistency](#7-cross-document-consistency)
8. [Maintenance Visibility](#8-maintenance-visibility)
9. [Security by Default](#9-security-by-default)
10. [Security-First Testing](#10-security-first-testing) ⚠️ **NEW**
11. [Anti-Patterns to Avoid](#11-anti-patterns-to-avoid-)
12. [Test Coverage Accountability](#12-test-coverage-accountability)
13. [Summary Checklist](#summary-philosophy-checklist)

---

## 1. Test-Driven Development (TDD)

### The Red-Green-Refactor Cycle

**Philosophy:** Write tests BEFORE implementation. Tests are specifications.

**The Cycle:**
1. **🔴 RED** - Write failing test that describes desired behavior
2. **🟢 GREEN** - Write minimal code to make test pass
3. **🔵 REFACTOR** - Improve code quality without changing behavior

**Why This Matters:**
- **Tests document intent** - Show what SHOULD happen
- **Catches regressions immediately** - Know when you break something
- **Forces modular design** - Testable code is better code
- **80%+ coverage required** - Not negotiable

**Example Workflow:**

```python
# 🔴 RED: Write test first (describes what we want)
def test_kalshi_balance_returns_decimal():
    """Balance must be Decimal for sub-penny precision."""
    client = KalshiClient()
    balance = client.get_balance()

    assert isinstance(balance, Decimal)  # FAILS - not implemented yet
    assert balance == Decimal("1234.5678")

# 🟢 GREEN: Implement minimal solution
def get_balance(self) -> Decimal:
    """Fetch account balance from Kalshi API."""
    response = self._make_request('/portfolio/balance')
    return Decimal(str(response['balance_dollars']))  # PASSES

# 🔵 REFACTOR: Improve (error handling, logging, caching)
def get_balance(self) -> Decimal:
    """
    Fetch account balance from Kalshi API.

    Returns:
        Decimal: Account balance in dollars (e.g., Decimal("1234.5678"))

    Raises:
        RequestException: If API request fails

    Example:
        >>> client = KalshiClient()
        >>> balance = client.get_balance()
        >>> print(f"Balance: ${balance}")
        Balance: $1234.5678
    """
    try:
        response = self._make_request('/portfolio/balance')
        balance = Decimal(str(response['balance_dollars']))
        logger.info(f"Account balance fetched: ${balance}")
        return balance
    except RequestException as e:
        logger.error(f"Failed to fetch balance: {e}")
        raise
```

**Coverage Requirements:**
- **≥80% overall coverage** (measured by pytest-cov)
- **100% for critical paths** (financial calculations, trading logic)
- **100% for security code** (authentication, credential handling)

---

### Coverage-Driven Development (CDD)

**Philosophy:** When inheriting untested code or when TDD wasn't followed, use coverage gaps to guide test creation.

**Complementary to TDD, not replacement:**
- **TDD:** Tests before code (green field)
- **CDD:** Coverage report drives test creation (legacy code, retrofitting)

**The CDD Workflow:**

```bash
# Step 1: Run coverage report
pytest --cov=api_connectors --cov-report=term-missing

# Output shows gaps:
api_connectors/kalshi_client.py   81.68%   Missing: 267-279, 320, 364

# Step 2: Examine uncovered code
# Lines 267-279: Handle 429 rate limit with Retry-After header

# Step 3: Ask "What scenario exercises this?"
# Answer: API returns 429 with Retry-After: 60 header

# Step 4: Write test for that scenario
def test_handle_429_with_retry_after():
    """Test 429 rate limit handling with Retry-After header."""
    # Mock response with 429 status and Retry-After header
    # Verify rate limiter updated with retry_after value
    # Verify exception raised (don't auto-retry)

# Step 5: Re-run coverage
pytest --cov=api_connectors --cov-report=term-missing
# Lines 267-279 now covered ✅
```

**When to Use CDD:**
- [ ] Inheriting code without tests
- [ ] Retrofitting tests to reach coverage targets
- [ ] TDD wasn't followed initially (fixing coverage gaps)
- [ ] Post-implementation test hardening

**When NOT to Use CDD:**
- ❌ Green field development (use TDD instead)
- ❌ As primary development approach (TDD is primary, CDD is remediation)
- ❌ To justify skipping TDD ("we'll add tests later via CDD")

---

### Prioritized Test Coverage Sprint

**Philosophy:** When multiple modules need coverage improvement, prioritize by business criticality and gap size.

**Prioritization Matrix:**

```
High Business Criticality + Large Gap = Priority 1 (do first)
High Business Criticality + Small Gap = Priority 2
Low Business Criticality + Large Gap = Priority 3
Low Business Criticality + Small Gap = Priority 4 (do last)
```

**Real Example (Phase 1):**

```
Priority 1: Kalshi API client (90% target, 81.68% current = 8.32 point gap, CRITICAL path)
Priority 2: Kalshi Auth (90% target, 80.95% current = 9.05 point gap, CRITICAL security)
Priority 3: Config loader (85% target, 21.35% current = 63.65 point gap, HIGH priority)
Priority 4: Database CRUD (87% target, 13.59% current = 73.41 point gap, HIGH priority)
Priority 5: Database connection (80% target, 35.05% current = 44.95 point gap, MEDIUM)
Priority 6: CLI (85% target, 0% current = 85 point gap, MEDIUM priority)
```

**Why This Order:**
1. **Critical paths first** - API/Auth are blocking dependencies for all features
2. **Large gaps later** - Config/DB/CLI have bigger gaps but lower immediate impact
3. **Sequential value** - Each priority delivers working, tested subsystem
4. **Morale boost** - Quick wins (Priorities 1-2) build momentum

**Outcome:**
- ✅ Priority 1 complete: Kalshi API 93.19% (EXCEEDS 90% target)
- ✅ Priority 2 complete: Kalshi Auth 100% (EXCEEDS 90% target)
- 🟡 Priorities 3-6 pending

---

### Systematic Coverage Gap Analysis

**Philosophy:** Convert abstract coverage percentages into concrete, actionable test tasks.

**The Translation Process:**

```
Step 1: Coverage Report
┌──────────────────────────────────────────────────────┐
│ kalshi_client.py: 81.68% coverage                    │
│ Target: 90%                                          │
│ Gap: 8.32 percentage points                          │
└──────────────────────────────────────────────────────┘

Step 2: Translate to Lines/Branches
┌──────────────────────────────────────────────────────┐
│ Gap breakdown:                                       │
│ - 21 lines uncovered                                 │
│ - 12 partial branches uncovered                      │
│ - Total: 33 coverage points missing                  │
└──────────────────────────────────────────────────────┘

Step 3: Group by Functionality
┌──────────────────────────────────────────────────────┐
│ Missing coverage categories:                         │
│ 1. Optional parameters (14 lines) → 7 tests         │
│ 2. Error handling (6 lines) → 2 tests               │
│ 3. Edge cases (13 branches) → 5 tests               │
│ Total: 14 tests needed to close gap                  │
└──────────────────────────────────────────────────────┘

Step 4: Actionable Tasks
┌──────────────────────────────────────────────────────┐
│ ✅ Write 7 tests for optional parameters             │
│ ✅ Write 2 tests for error handling                  │
│ ✅ Write 5 tests for edge cases                      │
│ = 14 tests total (closes 8.32 point gap)             │
└──────────────────────────────────────────────────────┘
```

**Key Insight:**
- "8.32 percentage points below target" = vague, hard to act on
- "14 specific tests needed" = concrete, achievable goal

**Tools:**
```bash
# Generate detailed coverage report with missing lines
pytest --cov=module --cov-report=term-missing --cov-branch

# Output shows exactly what's uncovered:
Missing: 267-279, 320, 364
BrPart: 414->416, 521->523, 569->571 (partial branches)
```

---

### Test Quality: When Tests Pass But Aren't Sufficient

**Philosophy:** "Tests passing" ≠ "Tests sufficient" ≠ "Code works correctly"

**The Problem (Phase 1.5 Discovery):**

Strategy Manager had 17/17 tests passing (100% test pass rate) but critical connection pool bugs went undetected. When tests were refactored to use real database fixtures instead of mocks, 13/17 tests failed (77% failure rate).

**Root Cause:**
- Tests used mocks instead of real database fixtures → bypassed integration bugs
- Small test suite (17 tests) gave false confidence → didn't stress connection pool
- Tests written AFTER implementation → confirmation bias (tested what was built, not what was needed)

**Lessons Learned:**

**1. Mock Sparingly, Integrate Thoroughly**

**When mocks are appropriate:**
- ✅ External APIs (Kalshi, ESPN) - expensive/rate-limited
- ✅ Time-dependent code (`datetime.now()`)
- ✅ Random number generation
- ✅ File I/O in some cases

**When mocks are NOT appropriate:**
- ❌ Database (use test database with fixtures)
- ❌ Internal application logic
- ❌ Configuration loading (use test configs)
- ❌ Logging (use test logger)

**Anti-Pattern Example:**
```python
# ❌ WRONG - Mocking internal infrastructure
@patch("precog.trading.strategy_manager.get_connection")
def test_create_strategy(mock_get_connection, mock_connection):
    mock_get_connection.return_value = mock_connection
    mock_cursor.fetchone.return_value = (1, "strategy_v1", ...)

    manager = StrategyManager()
    result = manager.create_strategy(...)  # Never hits real database!
    assert result["strategy_id"] == 1  # ✅ Test passes
    # But connection pool leak exists - NOT CAUGHT!
```

**Correct Pattern:**
```python
# ✅ CORRECT - Using real database with test fixtures
def test_create_strategy(clean_test_data, manager, strategy_factory):
    """Test creating strategy with real database."""
    result = manager.create_strategy(**strategy_factory)

    assert result["strategy_id"] is not None
    # Uses real database → catches connection pool leak immediately
```

**2. Use Test Infrastructure (conftest.py Fixtures)**

**ALWAYS use established test fixtures:**
- ✅ `clean_test_data` - Cleans database before/after each test
- ✅ `db_pool` - Connection pool with automatic cleanup
- ✅ `db_cursor` - Database cursor with automatic rollback
- ❌ NEVER create `mock_connection` or `mock_cursor` fixtures

**Why:** Test infrastructure exists to prevent bugs. Bypassing it = reinventing wheel poorly.

**3. Write Tests BEFORE Implementation (True TDD)**

**WRONG workflow:**
1. Write implementation first
2. Write tests second
3. Tests designed to match what was built (confirmation bias)
4. Bugs in implementation → tests designed around bugs

**CORRECT workflow:**
1. Write test first (describes what SHOULD happen)
2. Run test → RED (implementation doesn't exist yet)
3. Write minimal implementation to pass test
4. Run test → GREEN
5. Refactor
6. Implementation designed to pass tests = testable design

**4. Need Multiple Test Types (Not Just Unit Tests)**

**Required test types for trading applications:**

| Test Type | Purpose | Example | When Required |
|-----------|---------|---------|---------------|
| **Unit** | Isolated function logic | `test_calculate_kelly()` | Always |
| **Property** | Mathematical invariants | `test_decimal_precision()` | Math-heavy modules |
| **Integration** | Real database + config | `test_manager_database()` | All managers |
| **E2E** | Complete workflows | `test_trading_lifecycle()` | Phase 5+ |
| **Stress** | Infrastructure limits | `test_pool_exhaustion()` | Critical resources |
| **Race** | Concurrent operations | `test_concurrent_updates()` | Multi-threaded |
| **Performance** | Latency/throughput | `test_order_latency()` | Phase 5+ |
| **Chaos** | Failure recovery | `test_db_failure()` | Phase 5+ |

**5. Stress Test Critical Resources**

**For trading applications, MUST test infrastructure limits:**
- ✅ Connection pools (10+ concurrent connections, pool exhaustion recovery)
- ✅ API rate limits (100+ requests/min, rate limit handling)
- ✅ Database transactions (concurrent updates, deadlock detection)
- ✅ Memory usage (24-hour stress runs, leak detection)

**Example stress test:**
```python
def test_connection_pool_concurrent_stress(db_pool):
    """Test 20 concurrent strategy creates (exceeds maxconn=5)."""
    import concurrent.futures

    def create_strategy(i):
        manager = StrategyManager()
        return manager.create_strategy(strategy_name=f"stress_{i}", ...)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(create_strategy, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20  # All succeeded
    # If connection pool leak → this test FAILS (pool exhausted)
```

**6. Coverage Percentage ≠ Test Quality**

**Aggregate coverage can mask critical gaps:**
- Overall: 86.25% coverage ✅ (looks good)
- But Model Manager: 25.75% ❌ (target: ≥85%)
- But Strategy Manager: 19.96% ❌ (target: ≥85%)

**Measure test QUALITY, not just QUANTITY:**
- ✅ Do tests use real infrastructure (not mocks)?
- ✅ Do tests cover edge cases (not just happy path)?
- ✅ Do tests cover failure modes (what happens when X fails)?
- ✅ Do tests validate business logic (not just "did we call the function")?
- ✅ Are tests written BEFORE implementation (TDD)?

**Prevention Strategies:**

**Test Review Checklist (run before marking work complete):**
- [ ] Tests use real infrastructure (database, not mocks)?
- [ ] Tests use fixtures from conftest.py (`clean_test_data`, `db_pool`)?
- [ ] Tests cover happy path AND edge cases?
- [ ] Tests cover failure modes (what happens when X fails)?
- [ ] Coverage percentage ≥ target for this module?
- [ ] Tests written BEFORE implementation (TDD)?
- [ ] Multiple test types present (unit, integration, property, stress)?

**Red Flags:**
- Coverage decreasing (regression)
- Manager modules <85% coverage
- Infrastructure modules <80% coverage
- No integration tests for new feature
- Only mocks, no real infrastructure tests
- Large test suite but low coverage (tests not comprehensive)

---

**Related Documents:**
- `docs/foundation/TESTING_STRATEGY_V3.6.md` (will be updated to V3.0)
- `docs/foundation/TEST_REQUIREMENTS_COMPREHENSIVE_V2.1.md` - REQ-TEST-012 through REQ-TEST-019
- `docs/utility/TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md` - Detailed post-mortem
- `TESTING_GAPS_ANALYSIS.md` - Current test coverage gaps
- `CLAUDE.md` Section 7 (Common Tasks - Task 1)
**Related Documents:**
- `docs/foundation/TESTING_STRATEGY_V3.6.md`
- `CLAUDE.md` Section 7 (Common Tasks - Task 1)

---

## 2. Defense in Depth (DID)

### Multiple Independent Validation Layers

**Philosophy:** Never rely on a single layer of validation. Multiple independent checks at different stages catch different error types.

⚠️ **CORE PRINCIPLE:** This is foundational to Precog's quality and security architecture.

**Why Defense in Depth:**
- **No single point of failure** - If one layer misses an issue, others catch it
- **Different layers catch different issues** - Syntax errors vs logic errors vs security issues
- **Early layers are fast** - Instant feedback for common issues
- **Later layers are thorough** - Comprehensive checks before deployment
- **Cost-effective** - Catch issues early (seconds) vs late (hours/days)

---

### Layer Architecture

**The 4-Layer Validation Strategy:**

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Pre-Commit Hooks (~2-5 seconds)                    │
│ - 12 automated checks on every commit                       │
│ - Auto-fixes: formatting, whitespace, line endings          │
│ - Blocks: linting errors, type errors, credentials          │
│ - Catches: 60-70% of issues                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Pre-Push Hooks (~30-60 seconds)                    │
│ - 5 comprehensive validation steps before push              │
│ - Includes: Unit tests, full type checking, security scan   │
│ - Blocks: Test failures, type errors, security issues       │
│ - Catches: 80-90% of issues (first time tests run locally)  │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: CI/CD Pipeline (~2-5 minutes)                      │
│ - Full test matrix (Python 3.12/3.13/3.14, Ubuntu/Windows)  │
│ - 6 required status checks for PR merge                     │
│ - Blocks: PR merge until all checks pass                    │
│ - Catches: 99%+ of issues (comprehensive multi-platform)    │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Branch Protection (~instant gate)                  │
│ - Enforces PR workflow, no direct commits to main           │
│ - Requires all CI checks passing before merge               │
│ - Requires conversation resolution                          │
│ - Final enforcement gate (cannot be bypassed)               │
└─────────────────────────────────────────────────────────────┘
```

---

### Defense in Depth Examples

#### Example 1: Decimal Precision (4 Layers)

**Why 4 layers:** Float precision loss would cause financial calculation errors.

```python
# Layer 1: Type hints (caught by mypy in pre-commit)
def calculate_profit(entry_price: Decimal, exit_price: Decimal) -> Decimal:
    return exit_price - entry_price  # mypy ensures Decimal types

# Layer 2: Database schema (DECIMAL(10,4) enforced)
CREATE TABLE trades (
    entry_price DECIMAL(10, 4) NOT NULL,  -- PostgreSQL type check
    exit_price DECIMAL(10, 4) NOT NULL
);

# Layer 3: Validation script (schema consistency check)
price_columns = {
    'trades': ['entry_price', 'exit_price']  # Script validates DECIMAL(10,4)
}

# Layer 4: Runtime validation (TypedDict + assertions)
class Trade(TypedDict):
    entry_price: Decimal  # TypedDict enforces type
    exit_price: Decimal

def record_trade(trade: Trade):
    assert isinstance(trade['entry_price'], Decimal), "Price must be Decimal"
```

**Result:** Float values caught at FOUR different points before causing errors.

---

#### Example 2: Security (3 Layers)

**Why 3 layers:** Hardcoded credentials would leak sensitive data.

```bash
# Layer 1: Pre-commit security scan (instant, blocks commit)
git add config.py  # Contains: password = "mypass123"
git commit
# → Hook blocks commit: "ERROR: Found hardcoded credentials!"

# Layer 2: Pre-push security scan (comprehensive, blocks push)
git push
# → Step 4: Security Scan runs Bandit
# → Bandit detects hardcoded password
# → Push blocked

# Layer 3: CI/CD security scan (recorded proof)
# → GitHub Actions runs security-scan job
# → Fails with detailed report
# → PR cannot be merged (branch protection enforces)
```

**Result:** No way to merge hardcoded credentials into main branch.

---

#### Example 3: Documentation Consistency (3 Layers)

**Why 3 layers:** Documentation drift causes confusion and implementation errors.

```bash
# Layer 1: Manual review (phase completion protocol Step 3)
# Developer checks: "Does code match docs?"

# Layer 2: Automated validation (validate_docs.py)
python scripts/validate_docs.py
# → Checks: Cross-references, version consistency, missing docs
# → Runs in pre-push hooks

# Layer 3: Update cascade rules (CLAUDE.md Section 5)
# → When adding REQ-XXX-NNN:
#    1. Add to MASTER_REQUIREMENTS
#    2. Add to REQUIREMENT_INDEX
#    3. Add to DEVELOPMENT_PHASES
#    4. Update MASTER_INDEX
# → Multiple documents prevent single-doc drift
```

**Result:** Documentation stays synchronized across all foundation docs.

---

### When to Apply Defense in Depth

**Always apply multiple layers for:**
- ✅ **Financial calculations** (Decimal precision, trade attribution)
- ✅ **Security-critical code** (credentials, authentication, SQL injection)
- ✅ **Data integrity** (database schema, SCD Type 2, foreign keys)
- ✅ **Configuration validation** (YAML syntax, required fields, type checking)
- ✅ **Documentation consistency** (cross-references, versioning, requirements)

**Single layer acceptable for:**
- ❌ **Trivial utilities** (string formatting, date parsing)
- ❌ **Internal tools** (scripts for manual use only)
- ❌ **Temporary debugging** (console logging, test fixtures)

---

### Cost-Benefit Analysis

| Layer | Time | What It Catches | When It Runs | Bypassable? |
|-------|------|-----------------|--------------|-------------|
| **Pre-Commit** | 2-5s | Syntax, formatting, basic security | Every commit | Yes (`--no-verify`) |
| **Pre-Push** | 30-60s | Tests, types, comprehensive security | Every push | Yes (`--no-verify`) |
| **CI/CD** | 2-5min | Multi-platform, integration, coverage | Every push (GitHub) | No (recorded) |
| **Branch Protection** | 0s | PR workflow, CI pass requirement | PR merge | No (enforced) |

**Key Insight:**
- **Layer 1+2 are bypassable** (local developer control) but provide instant feedback
- **Layer 3+4 are NOT bypassable** (final enforcement) but slower
- **Together:** Fast feedback + guaranteed enforcement = best of both worlds

---

### Defense in Depth Checklist

Before marking any feature complete, verify defense in depth:

- [ ] **Multiple validation layers implemented?**
  - [ ] Early layer (pre-commit/pre-push) for fast feedback?
  - [ ] Late layer (CI/CD) for comprehensive enforcement?
  - [ ] Runtime layer (assertions, type checks) as last resort?

- [ ] **Each layer checks different aspects?**
  - [ ] Syntax/formatting in pre-commit?
  - [ ] Tests/types in pre-push?
  - [ ] Multi-platform/integration in CI?

- [ ] **No single point of failure?**
  - [ ] If one layer disabled, do others still catch issues?
  - [ ] If local checks bypassed, does CI catch it?

- [ ] **Appropriate for criticality?**
  - [ ] Financial code has 4+ layers?
  - [ ] Security code has 3+ layers?
  - [ ] Non-critical code has 2+ layers?

**Related Documents:**
- `CLAUDE.md` Section 3.1-3.3 (Pre-commit, Pre-push, Branch protection workflows)
- `.pre-commit-config.yaml` - Layer 1 configuration
- `.git/hooks/pre-push` - Layer 2 configuration
- `.github/workflows/ci.yml` - Layer 3 configuration
- `docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md` - Layer 4 configuration

---

## 3. Documentation-Driven Development (DDD)

### Document Before Implementing

**Philosophy:** Requirements and architecture decisions PRECEDE code. No code without docs.

**The Workflow:**
1. **REQUIREMENTS** - Add REQ-XXX-NNN to MASTER_REQUIREMENTS
2. **ARCHITECTURE** - Add ADR-XXX to ARCHITECTURE_DECISIONS
3. **SPECIFICATION** - Create supplementary spec (if complex)
4. **IMPLEMENTATION** - Write code that fulfills documented requirements
5. **UPDATE** - Mark REQ/ADR as complete, update indexes

**Why This Matters:**
- **Prevents "we built the wrong thing"** - Requirements clear upfront
- **Makes requirements traceable** - Every line of code → REQ-XXX-NNN
- **Enables accurate impact analysis** - Know what depends on what
- **Prevents documentation drift** - Docs lead, code follows

**Example: Adding New API Client**

```markdown
## STEP 1: Add Requirement (MASTER_REQUIREMENTS)

**REQ-API-008: Polymarket API Integration**
- **Phase:** 3
- **Priority:** 🟡 High
- **Status:** 🔵 Planned
- **Description:** Integrate Polymarket API for market data fetching
  - REST endpoints: /markets, /events, /positions
  - WebSocket for live updates
  - Rate limiting: 60 req/min
  - Authentication: API key
- **Related:** ADR-055 (Polymarket Auth Strategy)

## STEP 2: Add Architecture Decision (ARCHITECTURE_DECISIONS)

### ADR-055: Polymarket Authentication Strategy

**Decision #55**
**Phase:** 3
**Status:** 🔵 Planned

**Decision:** Use API key authentication for Polymarket (not OAuth)

**Rationale:**
- Polymarket API uses simple API key auth
- Simpler than OAuth (no token refresh needed)
- Consistent with Kalshi pattern (API key in headers)

**Implementation:**
- API key in .env: `POLYMARKET_API_KEY`
- Header: `Authorization: Bearer {api_key}`

**Related Requirements:** REQ-API-008

## STEP 3: Update Indexes

Add to REQUIREMENT_INDEX:
| REQ-API-008 | Polymarket API Integration | 3 | High | 🔵 Planned |

Add to ADR_INDEX:
| ADR-055 | Polymarket Authentication | 3 | 🔵 Planned | 🟡 High |

## STEP 4: NOW Write Code

```python
# polymarket_client.py - Implementation follows documented requirements
class PolymarketClient:
    """
    Polymarket API client.

    Implements REQ-API-008: Polymarket API Integration
    Uses ADR-055: API key authentication strategy
    """
    def __init__(self):
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        # ... implementation
```

## STEP 5: Mark Complete

Update MASTER_REQUIREMENTS:
- REQ-API-008 status: 🔵 Planned → ✅ Complete

Update REQUIREMENT_INDEX:
| REQ-API-008 | Polymarket API Integration | 3 | High | ✅ Complete |

Update DEVELOPMENT_PHASES:
- [✅] Polymarket API client implementation
```

**Related Documents:**
- `CLAUDE.md` Section 5 (Document Cohesion & Consistency)
- `CLAUDE.md` Section 7 (Common Tasks - Update Cascade Rules)

---

## 4. Data-Driven Design

### Configuration Over Code

**Philosophy:** Make data structures explicit, visible, and maintainable. Prefer dicts/lists over hard-coded logic.

**Why This Matters:**
- **Easy to update** - Change data, not code
- **Maintenance time visible** - "5 minutes per table" documented
- **Junior developers can contribute** - Update list, not rewrite logic
- **Self-documenting** - Structure shows intent

**Good Example (Data-Driven):**

```python
# ✅ Configuration explicit and maintainable
price_columns = {
    'markets': ['yes_bid', 'yes_ask', 'no_bid', 'no_ask'],
    'positions': ['entry_price', 'exit_price', 'current_price'],
    'trades': ['price', 'fill_price'],
    'edges': ['edge_probability'],
    # Future tables: Add here when implementing new price-related tables
    # Example:
    # 'portfolio': ['total_value', 'cash_balance'],  # Phase 5
}

def validate_decimal_precision(table_name: str) -> bool:
    """Validate price columns are DECIMAL(10,4)."""
    if table_name not in price_columns:
        return True  # Skip validation for non-price tables (fail-safe)

    columns_to_check = price_columns[table_name]

    for col_name in columns_to_check:
        # ... validation logic (SAME for all tables)
        column_type = get_column_type(table_name, col_name)
        if column_type != "DECIMAL(10,4)":
            errors.append(f"{table_name}.{col_name}: Expected DECIMAL(10,4), got {column_type}")

    return len(errors) == 0
```

**Bad Example (Logic-Driven):**

```python
# ❌ Hard-coded logic requires code changes for every table
def validate_decimal_precision(table_name: str) -> bool:
    """Validate price columns are DECIMAL(10,4)."""
    if table_name == 'markets':
        columns_to_check = ['yes_bid', 'yes_ask', 'no_bid', 'no_ask']
        for col_name in columns_to_check:
            # ... validation logic (DUPLICATED per table)
    elif table_name == 'positions':
        columns_to_check = ['entry_price', 'exit_price', 'current_price']
        for col_name in columns_to_check:
            # ... validation logic (DUPLICATED again)
    elif table_name == 'trades':
        columns_to_check = ['price', 'fill_price']
        for col_name in columns_to_check:
            # ... validation logic (DUPLICATED yet again)
    # ... repeat for EVERY table (unmaintainable!)
```

**When to Use Data-Driven Design:**
- ✅ **Validation rules** (lists of columns, tables, required fields)
- ✅ **Configuration mappings** (API endpoints, error codes)
- ✅ **Feature flags** (enable/disable functionality)
- ✅ **Test fixtures** (sample data, mock responses)
- ✅ **Database schemas** (table lists, column lists)

**When NOT to Use:**
- ❌ **Complex business logic** (multi-step calculations)
- ❌ **Stateful algorithms** (trading strategies, exit conditions)
- ❌ **Dynamic behavior** (behavior changes based on runtime data)

**Reference:** `scripts/validate_schema_consistency.py` (lines 247-409) - Excellent example of data-driven validation

---

## 5. Fail-Safe Defaults

### Graceful Degradation Over Crashes

**Philosophy:** Validation scripts should skip gracefully, not crash. Better to warn than to block.

**Why This Matters:**
- **Development continues** - Incomplete validation doesn't block work
- **Clear errors explain HOW to fix** - Not just "failed"
- **Manual maintenance doesn't break automation** - Can update incrementally
- **Progressive enhancement** - Add checks over time

**Example (Fail-Safe Validation):**

```python
def validate_price_columns(table_name: str) -> tuple[bool, list[str]]:
    """
    Validate price columns are DECIMAL(10,4).

    Fail-safe design:
    - Skip if table not in price_columns dict (maybe not a price table)
    - Skip if table doesn't exist in database (maybe not created yet)
    - Only fail if table EXISTS and has WRONG precision (actual error)
    """
    # Fail-safe #1: Skip if not a known price table
    if table_name not in price_columns:
        logger.debug(f"Skipping {table_name} - not in price_columns dict")
        return True, []  # Success (skipped)

    # Fail-safe #2: Skip if table doesn't exist yet
    columns = get_table_columns(table_name)
    if not columns:
        logger.warning(f"Table {table_name} not found - skipping validation")
        return True, []  # Success (skipped)

    # Only fail if table EXISTS and column type is WRONG
    errors = []
    for col_name in price_columns[table_name]:
        col_info = get_column_info(table_name, col_name)

        # Fail-safe #3: Skip if column doesn't exist (maybe not added yet)
        if not col_info:
            logger.warning(f"{table_name}.{col_name} not found - skipping")
            continue

        # NOW check precision (only fail if wrong type)
        if col_info['data_type'] != 'numeric' or col_info['precision'] != 10:
            errors.append(f"{table_name}.{col_name}: Expected DECIMAL(10,4), got {col_info['data_type']}")

    if errors:
        for error in errors:
            logger.error(error)
        return False, errors
    else:
        logger.info(f"{table_name}: All price columns are DECIMAL(10,4) ✓")
        return True, []
```

**Result:**
- ✅ Validation runs even if schema incomplete
- ✅ Skips gracefully when data missing
- ✅ Only fails when actual type mismatch found
- ✅ Clear logs explain what was checked and why

**Related:** All validation scripts (`validate_schema_consistency.py`, `validate_docs.py`)

---

## 6. Explicit Over Clever

### Code Clarity Trumps Brevity

**Philosophy:** Write code that's obvious, not code that's short. Favor verbose clarity over terse cleverness.

**Why This Matters:**
- **Onboarding time reduced** - New developers understand immediately
- **Bugs easier to spot** - Logic is visible
- **Maintenance easier** - No "what does this do?" moments
- **Performance rarely matters** - For business logic (not hot loops)

**Good Example (Explicit):**

```python
def is_market_tradeable(market: Market) -> bool:
    """
    Check if market can be traded.

    A market is tradeable if ALL conditions met:
    1. Status is "open"
    2. Close time is in the future
    3. Volume is ≥100 contracts

    Returns:
        True if tradeable, False otherwise (with logged reason)
    """
    if market.status != "open":
        logger.info(f"Market {market.ticker} not tradeable - status is {market.status} (expected 'open')")
        return False

    if market.close_time < datetime.now():
        logger.info(f"Market {market.ticker} not tradeable - already closed at {market.close_time}")
        return False

    if market.volume < 100:
        logger.info(f"Market {market.ticker} not tradeable - low volume ({market.volume} contracts, need ≥100)")
        return False

    logger.info(f"Market {market.ticker} is tradeable ✓")
    return True
```

**Bad Example (Clever):**

```python
def is_market_tradeable(m):
    """Check if market can be traded."""
    return m.status == "open" and m.close_time > datetime.now() and m.volume >= 100
    # Which condition failed? No idea! No logging. Impossible to debug.
```

**When Verbosity Matters:**
- ✅ **Validation logic** - Explicit checks with clear error messages
- ✅ **Error handling** - Detailed try/except blocks
- ✅ **Financial calculations** - Every step visible and commented
- ✅ **Security-critical code** - No magic, no cleverness

**When Brevity Okay:**
- ✅ **Simple getters/setters** - `def get_price(self): return self.price`
- ✅ **List comprehensions** (if readable) - `[x for x in items if x.active]`
- ✅ **Standard library idioms** - `with open(...) as f:`

---

## 7. Cross-Document Consistency

### Single Source of Truth for Everything

**Philosophy:** Every piece of information has ONE canonical location. Updates cascade to dependent docs.

**Why This Matters:**
- **No contradictions** - Avoids "which doc is correct?"
- **Changes propagate systematically** - Update cascade rules prevent drift
- **Makes onboarding reliable** - Docs don't contradict each other
- **Enables automation** - Consistency checks can be automated

**The Workflow (Adding Requirement):**

```markdown
1. **Canonical:** MASTER_REQUIREMENTS_V2.17.md
   Add REQ-XXX-NNN here FIRST

2. **Cascade to:**
   - REQUIREMENT_INDEX.md (add to table)
   - DEVELOPMENT_PHASES_V1.10.md (add to phase tasks)
   - MASTER_INDEX_V2.11.md (update version if renamed)
   - SESSION_HANDOFF.md (document change)

3. **Validate:**
   python scripts/validate_docs.py  # Checks consistency

4. **DO NOT skip any step!**
```

**Example (Adding REQ-CLI-007):**

```markdown
Step 1: Add to MASTER_REQUIREMENTS V2.10 → V2.11
**REQ-CLI-007: Market Filtering Command**
- Phase: 2
- Priority: High
- Description: CLI command to filter markets by criteria

Step 2: Add to REQUIREMENT_INDEX
| REQ-CLI-007 | Market Filtering Command | 2 | High | 🔵 Planned |

Step 3: Add to DEVELOPMENT_PHASES Phase 2 tasks
- [ ] CLI command: `main.py filter-markets --sport NFL --min-volume 1000`

Step 4: Update MASTER_INDEX
| MASTER_REQUIREMENTS_V2.11.md | ✅ | v2.11 | ... | UPDATED from V2.10 |

Step 5: Update SESSION_HANDOFF
## This Session Completed
- ✅ Added REQ-CLI-007 for market filtering (Phase 2 planning)
```

**Related Documents:**
- `CLAUDE.md` Section 5 (Document Cohesion & Consistency)
- `CLAUDE.md` Section 5 (Update Cascade Rules)

---

## 8. Maintenance Visibility

### Document Maintenance Burden Explicitly

**Philosophy:** Every manual update should have time estimate and clear instructions. No "figure it out" maintenance.

**Why This Matters:**
- **Realistic effort estimation** - Know how long updates take
- **Junior developers can contribute** - Clear instructions provided
- **Prevents "I forgot to update X"** - Explicit reminders
- **Makes automation decisions data-driven** - "5 min manual" vs "2 hours to automate"

**Example: Validation Script Maintenance Guide**

```python
"""
MAINTENANCE GUIDE:
==================
When adding NEW tables with price/probability columns:
1. Add table_name to price_columns dict below
2. List all price/probability column names for that table
3. Tag with phase number for tracking (e.g., # Phase 3)
4. Run validation: python scripts/validate_schema_consistency.py

Maintenance time: ~5 minutes per new price table

Example:
    price_columns = {
        'markets': ['yes_bid', 'yes_ask', ...],  # Phase 1
        'odds_history': ['historical_odds'],      # Phase 3
        'portfolio': ['total_value'],             # Phase 5
    }

When to update:
- Adding new table with DECIMAL columns
- Adding price/probability column to existing table
- Implementing Phase 3, 4, or 5 financial features

How to test:
    python scripts/validate_schema_consistency.py
    # Expected: All price tables pass DECIMAL(10,4) check
"""

# CONFIGURATION: Price/probability columns by table
price_columns = {
    'markets': ['yes_bid', 'yes_ask', 'no_bid', 'no_ask'],
    'positions': ['entry_price', 'exit_price', 'current_price'],
    'trades': ['price', 'fill_price'],
    # Future tables: Add here (5 min per table)
}
```

**Where to Add Maintenance Guides:**
- ✅ **Validation scripts** - Which lists/dicts to update
- ✅ **Configuration files** - Which sections need updates
- ✅ **Database migrations** - Which validations to run
- ✅ **Documentation templates** - Which sections to customize

**Related:** All validation scripts have comprehensive maintenance guides

---

## 9. Security by Default

### No Credentials in Code, Ever

**Philosophy:** Zero tolerance for hardcoded secrets. Environment variables for all credentials.

**Why This Matters:**
- **Prevents accidental credential leaks** - Git history doesn't expose secrets
- **Enables per-environment configuration** - Dev/staging/prod use different creds
- **Makes credential rotation safe** - Update .env, don't touch code
- **Meets security compliance requirements** - SOC2, PCI-DSS, etc.

**Always Use Environment Variables:**

```python
# ✅ CORRECT: Environment variables
import os
from dotenv import load_dotenv

load_dotenv()

db_password = os.getenv('DB_PASSWORD')
api_key = os.environ['KALSHI_API_KEY']  # Raises KeyError if missing (fail-fast)

# Validate credentials exist
if not db_password:
    raise ValueError("DB_PASSWORD environment variable not set")

# Use in connection string
db_url = f"postgresql://user:{db_password}@localhost:5432/dbname"
```

**Never Hardcode:**

```python
# ❌ NEVER: Hardcoded credentials
password = "mypassword123"
api_key = "sk_live_abc123xyz"
db_url = "postgresql://user:password123@localhost/db"
```

**Pre-Commit Security Scan (Mandatory):**

```bash
# Runs automatically on every commit (pre-commit hook)
git add config.py
git commit -m "Update config"

# Hook runs security scan:
git grep -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{5,}['\"]" -- '*.py'

# If matches found:
# ❌ ERROR: Found potential hardcoded credentials!
# Commit blocked.

# Expected result:
# ✅ No hardcoded credentials detected
# Commit allowed.
```

**Defense in Depth (3 Layers):**
1. **Pre-commit hook** - Blocks commit with hardcoded credentials
2. **Pre-push hook** - Bandit security scan (comprehensive)
3. **CI/CD** - Security scan job (recorded proof)

**Related Documents:**
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md`
- `CLAUDE.md` Section 8 (Security Guidelines)
- `CLAUDE.md` Section 4 - Pattern 4 (Security)

---

## 10. Security-First Testing

**Core Belief:** Tests validate that security works correctly, not that code works when security is disabled.

**Rationale:**
Security validations are not optional features that can be toggled off for testing convenience. They are critical safeguards that must be validated as part of normal test execution.

**Problem Prevented:**
- Tests pass with `git commit --no-verify` (bypassing pre-commit hooks)
- Tests use mocked security validations that never execute
- Production security fails silently because tests never exercised it

**Solution:**
Tests must work WITH security validations, not around them. If security breaks tests, fix tests (not security).

### Rules

**1. Never Bypass Security in Tests**

❌ **WRONG:**
```bash
# Bypassing pre-commit hooks to make tests pass
git commit --no-verify -m "Add tests (skipping security scan)"

# Mocking out security validation
@patch('precog.database.initialization.Path.is_relative_to')
def test_apply_schema(mock_is_relative):
    mock_is_relative.return_value = True  # Always pass security check
    # Test never validates path traversal protection!
```

✅ **CORRECT:**
```bash
# Fix tests to comply with security requirements
# Update fixtures to use project-relative paths

# Test WITH security validation (not mocked)
def test_apply_schema_rejects_external_files():
    """Verify path traversal protection works."""
    external_file = "/tmp/malicious.sql"
    success, error = apply_schema("postgresql://localhost/test", external_file)

    assert success is False
    assert "must be within project directory" in error
```

**2. Tests Should Validate Security Boundaries**

✅ **Security validations should have explicit tests:**

```python
def test_path_traversal_protection():
    """Verify files outside project are rejected (CWE-22)."""
    external_file = "/etc/passwd"
    success, error = apply_schema(DB_URL, external_file)
    assert success is False
    assert "Security" in error

def test_file_extension_validation():
    """Verify only .sql files are accepted."""
    txt_file = "tests/.tmp/schema.txt"  # Within project, wrong extension
    success, error = apply_schema(DB_URL, txt_file)
    assert success is False
    assert ".sql file" in error

def test_credential_scanning():
    """Verify pre-commit hook blocks hardcoded credentials."""
    # This test would run git grep for hardcoded secrets
    result = subprocess.run(
        ["git", "grep", "-E", "password\\s*=\\s*['\"]"],
        capture_output=True
    )
    assert result.returncode != 0  # No matches = security passing
```

**3. When Security Breaks Tests, Fix Tests (Not Security)**

**Example from PR #79:**

**Problem:**
- PR #76 added path traversal protection to `apply_schema()`
- Security validation: `schema_path.is_relative_to(project_root)`
- 9 tests failed: fixtures used `tmp_path` (system temp outside project)
- Error: "Security: Schema file must be within project directory"

**❌ WRONG Fix (disable security):**
```python
# DON'T DO THIS
if os.getenv("TESTING"):
    # Skip path traversal check during tests
    pass
else:
    if not schema_path.is_relative_to(project_root):
        return False, "Security error"
```

**✅ CORRECT Fix (update tests):**
```python
# Update fixtures to create files within project
@pytest.fixture
def temp_schema_file() -> Generator[str, None, None]:
    """Create file in tests/.tmp/ (within project)."""
    project_root = Path.cwd()
    temp_dir = project_root / "tests" / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    schema_file = temp_dir / f"test_schema_{uuid.uuid4().hex[:8]}.sql"
    schema_file.write_text("CREATE TABLE test (id INT);")

    try:
        yield str(schema_file)
    finally:
        schema_file.unlink()
```

### Integration with Development Workflow

**Phase Planning:**
- [ ] Identify security requirements for phase (authentication, authorization, input validation)
- [ ] Plan security tests BEFORE implementing features
- [ ] Document security validations in ADRs (e.g., ADR-076: Path Traversal Protection)

**During Development:**
- [ ] Write security tests first (TDD for security)
- [ ] Run security scan before every commit: `git grep "password\s*="`
- [ ] Ensure pre-commit hooks are installed: `pre-commit install`

**PR Review:**
- [ ] Security validations have explicit tests?
- [ ] Tests don't mock out security checks?
- [ ] No `--no-verify` or `TESTING` bypasses in code?

**Phase Completion:**
- [ ] Run full security scan: `./scripts/validate_quick.sh`
- [ ] Review SECURITY_REVIEW_CHECKLIST.md
- [ ] Verify no credentials in code: `git grep -E "(password|secret|api_key)"`

### Real-World Impact

**PR #79 Results:**
- **Before:** 9/25 tests failing (fixtures violated security)
- **After:** 25/25 tests passing (fixtures comply with security)
- **Coverage:** 68.32% → 89.11% (+20.79pp)
- **Security:** Path traversal protection working correctly

**Lesson:** Fixing tests to work with security (not disabling security) resulted in:
1. Higher test coverage (security paths now tested)
2. Confidence in security validations (actually exercised in tests)
3. Better fixtures (project-relative, reusable pattern)

### Anti-Patterns to Avoid

**❌ Don't:**
- Use `git commit --no-verify` except in absolute emergencies
- Mock out security validations in tests
- Add `if os.getenv("TESTING")` bypasses to production code
- Disable pre-commit hooks "temporarily" (you'll forget to re-enable)

**✅ Do:**
- Update tests to comply with security requirements
- Write explicit tests for security validations
- Run pre-commit hooks on every commit (automatic after `pre-commit install`)
- Treat security failures as bugs (fix immediately, don't bypass)

### Cross-References
- **Pattern 4:** Security (NO CREDENTIALS IN CODE)
- **Pattern 12:** Test Fixture Security Compliance
- **SECURITY_REVIEW_CHECKLIST.md:** Comprehensive security validation checklist
- **PR #76:** Path traversal protection implementation (CWE-22)
- **PR #79:** Test fixture updates for security compliance

---

## 11. Anti-Patterns to Avoid ⚠️

### Common Development Traps

**Philosophy:** Awareness of anti-patterns prevents mistakes. Document what NOT to do as clearly as what TO do.

**Why This Matters:**
- **Anti-patterns are subtle** - Easy to fall into without realizing
- **Prevention > Remediation** - Catching anti-patterns early saves time
- **Explicit warnings help** - "Don't do X" is clearer than implying it
- **Common traps are predictable** - Same mistakes happen repeatedly

---

### Anti-Pattern 1: Partial Thoroughness

**Description:** Assuming work is "complete enough" without checking against explicit targets.

**Real Example from Phase 1:**
```
❌ BAD: "Kalshi API has 81.68% coverage - that's pretty good!"
✅ GOOD: "Kalshi API target is 90%. Current 81.68% = 8.32 points below. Need 14 more tests."

Why it matters:
- 8.32 percentage points = 21 lines + 12 partial branches uncovered
- Small percentage gaps can represent significant functional gaps
- "Pretty good" != "meets requirement"
```

**How to Detect:**
- [ ] Compare coverage % to explicit target (not "feels good enough")
- [ ] Check absolute number of uncovered lines (not just percentage)
- [ ] Look at partial branch coverage (branches often hide edge cases)
- [ ] Verify ALL success criteria met (not just most)

**Prevention Checklist:**
- [ ] Every module has explicit coverage target (not implicit)
- [ ] Targets documented in test planning checklist
- [ ] Coverage report shows uncovered lines (not just percentage)
- [ ] Success criteria use ≥ operator (not ~roughly)

**Validation:**
```bash
# ❌ BAD: Vague check
pytest --cov
# "81% coverage - looks good!"

# ✅ GOOD: Target-driven check
pytest --cov=api_connectors --cov-fail-under=90
# FAILED: Coverage 81.68% < 90% → 14 more tests needed
```

---

### Anti-Pattern 2: Percentage Point Blindness

**Description:** Not realizing small percentage differences represent significant uncovered code.

**Real Example:**
```
Phase 1 Coverage Analysis:
- Kalshi API: 81.68% vs 90% target
- Gap: 8.32 percentage points (sounds small)
- Reality: 21 lines + 12 partial branches uncovered
- Missing scenarios: 429 rate limit edge cases, max retries fallback, Decimal warning logs
```

**Why Percentages Mislead:**
- 90% coverage of 100-line module = 10 lines uncovered
- 90% coverage of 1000-line module = 100 lines uncovered
- Same percentage, 10x difference in uncovered code!

**How to Detect:**
- [ ] Check `Missing` column in coverage report (line numbers)
- [ ] Check `BrPart` column (partial branch coverage)
- [ ] Count uncovered scenarios (not just lines)
- [ ] Ask: "What functionality is missing?"

**Prevention:**
```python
# Add to pyproject.toml to show missing lines by default
[tool.pytest.ini_options]
addopts = [
    "--cov=.",
    "--cov-report=term-missing",  # Shows line numbers!
    "--cov-branch",               # Track branch coverage
]
```

---

### Anti-Pattern 3: Coverage Complacency

**Description:** Checking coverage once when work starts, never rechecking as code evolves.

**Real Example:**
```
Session 1: "Kalshi API at 81.68% - good start!"
Session 2-5: Add features, refactor code, no coverage checks
Session 6: "Wait, coverage is now 65%? When did that happen?"
```

**Why This Happens:**
- Coverage tracked manually (not automated)
- Focus on features, not tests
- Assume "if tests pass, coverage is fine"
- No coverage gates in CI/CD

**How to Detect:**
- [ ] Coverage % decreased since last session?
- [ ] New code added without tests?
- [ ] Tests passing but coverage report not checked?
- [ ] CI/CD doesn't fail on coverage drop?

**Prevention (Defense in Depth):**
1. **Pre-commit:** Run coverage report locally before commit
2. **Pre-push:** Coverage check in pre-push hook
3. **CI/CD:** `--cov-fail-under=80` gate (blocks merge if <80%)
4. **Phase completion:** Full coverage audit before marking phase complete

**Automation:**
```yaml
# .github/workflows/ci.yml
- name: Test with coverage
  run: |
    pytest --cov=. --cov-fail-under=80
    # CI fails if coverage <80% (can't merge!)
```

---

### Anti-Pattern 4: Test Planning After Code

**Description:** Writing implementation first, then figuring out how to test it later.

**Why This Fails:**
- Code not designed for testability
- Hard to mock tightly-coupled dependencies
- Edge cases discovered too late
- Tests become brittle (test implementation, not behavior)

**Real Example:**
```python
# ❌ BAD: Code first, tests later
# Step 1: Implement feature
def process_trade(trade_data: dict):
    # 200 lines of complex logic with database, API, calculations mixed together
    # (Hard to test - tightly coupled!)
    pass

# Step 2: Try to write tests (struggle to mock everything)

# ✅ GOOD: Tests first (TDD)
# Step 1: Write test describing behavior
def test_process_trade_rejects_invalid_price():
    """Trade with price=0 should be rejected."""
    with pytest.raises(ValueError, match="Price must be >0"):
        process_trade({"price": 0})

# Step 2: Implement minimal solution
def process_trade(trade_data: dict):
    if trade_data["price"] <= 0:
        raise ValueError("Price must be >0")
    # (Easy to test - clear behavior!)
```

**Prevention:**
- [ ] Complete test planning checklist BEFORE writing code
- [ ] Write test first (red), then implementation (green), then refactor (blue)
- [ ] If test is hard to write, redesign interface
- [ ] Reject PRs without corresponding tests

---

### Anti-Pattern 5: Spot Checking vs. Systematic Validation

**Description:** Checking one or two modules instead of validating all modules against targets.

**Real Example:**
```
# ❌ BAD: Spot check
"I checked Kalshi API - 81.68% coverage. Ship it!"

# Missing checks:
- Config loader: 21.35% (needs 85%+) ← 63.65 points below target!
- Database CRUD: 13.59% (needs 87%+) ← 73.41 points below target!
- Database connection: 35.05% (needs 80%+) ← 44.95 points below target!
- CLI: 0% (needs 85%+) ← Not even started!

# ✅ GOOD: Systematic validation
"Checked ALL Phase 1 modules against targets. Found 4 gaps. See Priority 3-6 tasks."
```

**How to Detect:**
- [ ] Coverage report shows overall % only (not per-module)?
- [ ] Only checked "main" module (ignored utilities, config, DB)?
- [ ] Success criteria lists multiple modules but only validated one?
- [ ] Didn't check integration tests (only unit tests)?

**Prevention:**
```bash
# Generate per-module coverage report
pytest --cov=. --cov-report=term-missing

# Checklist approach (from test planning):
- [ ] api_connectors/kalshi_client.py: ≥90% (current: 93.19% ✅)
- [ ] api_connectors/kalshi_auth.py: ≥90% (current: 100% ✅)
- [ ] config/config_loader.py: ≥85% (current: 21.35% ❌)
- [ ] database/crud_operations.py: ≥87% (current: 13.59% ❌)
- [ ] database/connection.py: ≥80% (current: 35.05% ❌)
- [ ] main.py (CLI): ≥85% (current: Not measured ❌)
```

---

### Anti-Pattern 6: "Partially Complete" Means "Good Enough"

**Description:** Resuming work on partially-complete phase without validating assumptions.

**Real Example:**
```
# Assumption: "Phase 1 API work is partially complete with 81.68% coverage"
# Reality check:
- Overall Phase 1 coverage: 49.49% (BELOW 80% threshold by 30.51 points!)
- Critical gaps: Config loader 21.35%, Database 13-35%, CLI 0%
- If we'd started Phase 2 without checking: Technical debt explosion!
```

**Why This Happens:**
- Assume previous session did comprehensive work
- Don't re-validate targets when resuming
- "Partially complete" sounds positive (hides gaps)
- Focus on new work (ignore unfinished old work)

**How to Detect:**
- [ ] Phase marked "50% complete" but coverage targets not verified?
- [ ] Resuming work after break without running full test suite?
- [ ] Test planning checklist has unchecked boxes?
- [ ] No coverage report in previous SESSION_HANDOFF?

**Prevention (CLAUDE.md Step 2a):**
```markdown
**Step 2a: Verify Phase Prerequisites (MANDATORY)**
- ⚠️ BEFORE CONTINUING ANY PHASE WORK: Check DEVELOPMENT_PHASES for current phase's Dependencies section
- Verify ALL "Requires Phase X: 100% complete" dependencies are met
- Check previous phase is marked ✅ Complete in DEVELOPMENT_PHASES
- **IF RESUMING PARTIALLY-COMPLETE PHASE:**
  - Re-run full test suite: `pytest --cov=.`
  - Compare coverage to targets (per-module, not overall)
  - Check test planning checklist status (what's unchecked?)
  - Identify gaps BEFORE continuing implementation
```

---

### Anti-Pattern 7: Ignoring Test Planning Checklists

**Description:** Skipping the "Before Starting This Phase" test planning checklist and jumping to code.

**Real Example:**
```
# ❌ BAD workflow:
1. See "Phase 1: Build API client"
2. Start coding immediately
3. Write some tests after (if time allows)
4. Mark phase complete

Result: 49.49% coverage, critical gaps in config/database/CLI

# ✅ GOOD workflow:
1. Read "Before Starting This Phase - TEST PLANNING CHECKLIST"
2. Complete 8 sections BEFORE writing code:
   - Requirements analysis
   - Test categories needed
   - Test infrastructure updates
   - Critical test scenarios
   - Performance baselines
   - Security test scenarios
   - Edge cases to test
   - Success criteria
3. THEN start implementation (with clear targets)
4. Validate ALL success criteria before marking complete

Result: 80%+ coverage, all gaps identified upfront
```

**How to Detect:**
- [ ] Phase started without completing test planning checklist?
- [ ] No test fixtures/factories created before implementation?
- [ ] Critical scenarios not listed before coding?
- [ ] Success criteria vague ("good coverage") instead of specific (≥90%)?

**Prevention:**
- [ ] Mark test planning checklist as MANDATORY (blocking)
- [ ] Require checklist completion in SESSION_HANDOFF before coding
- [ ] Add test planning time to phase estimates (2-4 hours)
- [ ] Code reviews verify checklist was completed

---

### Anti-Pattern 8: "Tests Pass = Good Coverage" Fallacy

**Description:** Assuming that because all tests pass, coverage must be sufficient.

**Why This Is Dangerous:**
- Tests can all pass with 30-50% coverage (uncovered code never executed)
- Passing tests only validate tested paths (not untested paths)
- Ship with large portions of code untested, unvalidated
- Edge cases, error handlers, fallback logic completely uncovered

**Real Example:**

```bash
# ❌ FALSE SENSE OF SECURITY
$ pytest
================================================
45 passed in 7.7s ✅
================================================
# Looks great! Ship it!

# BUT...
$ pytest --cov
================================================
45 passed in 7.7s

Coverage: 53.29% ⚠️ BELOW 80% threshold by 26.71 points!
================================================

# Reality:
- 287 lines uncovered (46.71% of code NEVER tested!)
- Config loader: 21.35% (critical config precedence logic untested)
- Database CRUD: 13.59% (SQL injection prevention untested)
- Error handling paths: 0% (what happens when things fail?)
```

**How to Detect:**
- [ ] "All tests passing" celebrated without checking coverage?
- [ ] Coverage report not run before marking feature complete?
- [ ] No coverage gates in CI/CD (tests pass, coverage ignored)?
- [ ] Coverage metrics not tracked in SESSION_HANDOFF?

**Prevention (Defense in Depth):**

```bash
# 1. Pre-push hook: Check coverage before pushing
pytest --cov=. --cov-fail-under=80
# Blocks push if coverage <80%

# 2. CI/CD: Automated coverage gate
# In .github/workflows/ci.yml:
- name: Test with coverage
  run: |
    pytest --cov=. --cov-fail-under=80
    # CI fails if <80% (can't merge PR!)

# 3. Phase completion: Mandatory coverage audit
- [ ] Overall coverage ≥80%?
- [ ] All critical modules meet targets?
- [ ] Coverage report in SESSION_HANDOFF?
```

**Key Insight:**
- ✅ "Tests pass" = Code that IS tested works correctly
- ❌ "Tests pass" ≠ All code is tested
- ✅ "Tests pass + 80% coverage" = Comprehensive validation

---

### Anti-Pattern 9: Branch Coverage Neglect

**Description:** Focusing only on line coverage while ignoring branch coverage (partial branches uncovered).

**Why Branches Matter:**
- **Line coverage:** Did we execute this line?
- **Branch coverage:** Did we test all outcomes of conditionals?
- Branches often represent edge cases, error paths, validation logic

**Real Example (Phase 1 Kalshi API):**

```python
# Before branch coverage attention:
Line coverage: 81.68% (looks good!)
Branch coverage: 12 partial branches uncovered (hidden problem!)

# What those 12 branches represented:
if status_code == 429:
    retry_after_str = response.headers.get("Retry-After")
    if retry_after_str:  # ← Branch 1: What if Retry-After present?
        retry_after_int = int(retry_after_str)  # ← Never tested!
    # Branch 2: What if Retry-After absent? ← Also never tested!
```

**Coverage Report Shows:**

```
Name                         Stmts   Miss  Branch  BrPart   Cover
----------------------------------------------------------------
kalshi_client.py               143      9      48      12   81.68%
                                                    ^^^^
                                            12 partial branches!
```

**How to Detect:**
- [ ] Coverage report shows `BrPart` column (partial branches)?
- [ ] Focused on `Cover %` without looking at `BrPart` number?
- [ ] Line coverage high (>80%) but branch coverage low?
- [ ] Tests for happy path only (no error/edge case tests)?

**Prevention:**

```bash
# Always check branch coverage
pytest --cov=. --cov-report=term-missing --cov-branch

# Focus on BrPart column:
Name                  Stmts  Miss  Branch  BrPart   Cover
--------------------------------------------------------
kalshi_client.py        143     9      48      12   81.68%
                                              ^^^
                                        12 branches partially tested!

# For each partial branch, ask:
# - What condition is this?
# - What happens when True? (tested?)
# - What happens when False? (tested?)
# - Which path is uncovered?
```

**Targeting Branch Coverage:**

```python
# ❌ BAD: Only tests happy path
def test_get_markets_success():
    """Test get_markets() returns markets."""
    markets = client.get_markets()
    assert len(markets) > 0  # Only tests successful path!

# ✅ GOOD: Tests both branches
def test_get_markets_success():
    """Test get_markets() returns markets."""
    markets = client.get_markets()
    assert len(markets) > 0

def test_get_markets_with_event_ticker():
    """Test get_markets() with event_ticker filter."""
    # Tests if event_ticker branch
    markets = client.get_markets(event_ticker="NFLGAME")
    # Verifies event_ticker parameter passed correctly

def test_get_markets_without_event_ticker():
    """Test get_markets() without event_ticker (default behavior)."""
    # Tests else branch (no event_ticker)
    markets = client.get_markets()
    # Verifies default behavior when parameter absent
```

---

### Anti-Pattern 10: Coverage Target Negotiation

**Description:** Lowering coverage targets instead of writing tests when hitting target is difficult.

**The Slippery Slope:**

```
Week 1: "80% coverage is the target"
Week 2: "80% is hard to hit, let's aim for 75%"
Week 4: "75% is still challenging, 70% is more realistic"
Week 8: "70% seems arbitrary, 60% is plenty"
Result: 50% coverage, massive technical debt
```

**Why This Happens:**
- Writing tests for complex code is hard
- Deadline pressure makes shortcuts tempting
- "Good enough" mindset creeps in
- No one challenges the negotiation

**Real Example:**

```
# Situation: Database CRUD at 13.59% coverage
Developer: "87% target is unrealistic. This code is hard to test. Let's lower it to 50%."

# ❌ BAD: Negotiate target down
New target: 50% (easy to hit, but leaves 50% untested!)

# ✅ GOOD: Ask WHY it's hard to test
- Is code tightly coupled? → Refactor for testability
- Missing test fixtures? → Create factories
- Complex setup? → Simplify or document setup steps
- Don't know how to mock? → Learn mocking patterns

# Outcome:
- Refactored for testability → Better code design
- Created test fixtures → Reusable test infrastructure
- Hit 87% target → Comprehensive coverage
```

**How to Detect:**
- [ ] Coverage target discussion focuses on "lowering bar" vs "how to reach it"?
- [ ] Justifications like "this code is special/hard to test"?
- [ ] Targets differ across similar modules (inconsistent standards)?
- [ ] Coverage targets decreasing over time?

**Prevention:**

```markdown
# Make targets NON-NEGOTIABLE requirements (not suggestions)

## MASTER_REQUIREMENTS (REQ-TEST-002):
**Requirement:** All modules MUST meet coverage targets:
- Critical modules (API, auth, trading): ≥90%
- High priority (config, database): ≥85%
- Standard modules: ≥80%

**Status:** 🔴 MANDATORY - Cannot mark phase complete without meeting targets

**Rationale:** Targets are based on risk analysis, not arbitrary numbers
```

**If hitting target is genuinely impossible:**
1. **Document why** (e.g., third-party library code, OS-specific code)
2. **Get explicit approval** (don't silently lower target)
3. **Add to exceptions list** (with justification and mitigation)
4. **Time-box reassessment** (revisit in 6 months)

**Key Insight:**
- Targets are REQUIREMENTS (like "code must compile")
- If target is hard to hit, code likely needs refactoring
- Lowering targets = technical debt accumulation

---

### Anti-Pattern 11: Test Inflation Without Value

**Description:** Writing trivial tests just to inflate coverage numbers without testing meaningful behavior.

**Why This Defeats the Purpose:**
- Coverage number goes up
- Code quality doesn't improve
- False sense of security
- Maintenance burden (useless tests require maintenance too)

**Examples of Valueless Tests:**

```python
# ❌ BAD: Tests implementation detail (not behavior)
def test_function_exists():
    """Test that calculate_profit function exists."""
    assert callable(calculate_profit)
    # Useless! If function doesn't exist, code won't even import.

# ❌ BAD: Tests Python language feature (not our code)
def test_dict_has_keys():
    """Test that dict has expected keys."""
    market_data = {"ticker": "TEST", "price": 0.50}
    assert "ticker" in market_data
    # Useless! Tests Python dict behavior, not our logic.

# ❌ BAD: Tests trivial getter (no logic to test)
def test_get_ticker_returns_ticker():
    """Test get_ticker() returns ticker."""
    market = Market(ticker="TEST")
    assert market.get_ticker() == "TEST"
    # Useless! Getter has no logic, just returns attribute.

# ❌ BAD: Mock everything, test nothing
def test_process_trade_calls_functions(mocker):
    """Test process_trade calls expected functions."""
    mocker.patch('module.validate_price')
    mocker.patch('module.execute_trade')
    mocker.patch('module.log_trade')

    process_trade({"price": 0.50})

    # Just verifies functions were called, not WHAT they did
    # If logic is wrong, test still passes!
```

**Examples of Valuable Tests:**

```python
# ✅ GOOD: Tests actual behavior
def test_calculate_profit_with_valid_prices():
    """Profit = (exit_price - entry_price) * quantity."""
    profit = calculate_profit(
        entry_price=Decimal("0.50"),
        exit_price=Decimal("0.75"),
        quantity=100
    )
    # Tests actual calculation logic
    assert profit == Decimal("25.00")

# ✅ GOOD: Tests validation logic
def test_calculate_profit_rejects_negative_quantity():
    """Negative quantity should raise ValueError."""
    with pytest.raises(ValueError, match="Quantity must be positive"):
        calculate_profit(
            entry_price=Decimal("0.50"),
            exit_price=Decimal("0.75"),
            quantity=-100  # Invalid input
        )
    # Tests edge case/error handling

# ✅ GOOD: Tests business rule
def test_process_trade_below_min_profit_threshold_skipped():
    """Trades with profit <$5 should be skipped (not worth fees)."""
    result = process_trade({
        "entry_price": Decimal("0.50"),
        "exit_price": Decimal("0.51"),  # Only $1 profit
        "quantity": 100
    })
    assert result.status == "skipped"
    assert result.reason == "profit_below_threshold"
    # Tests actual business logic
```

**How to Detect:**
- [ ] Test just calls function, asserts it doesn't crash?
- [ ] Test verifies function was called (but not what it returned)?
- [ ] Test checks object exists (but not its behavior)?
- [ ] Test duplicates functionality (tests same thing multiple ways)?
- [ ] Test name describes WHAT function does, not WHAT SHOULD HAPPEN?

**Prevention:**

```markdown
# Code Review Checklist:
- [ ] Every test has clear "GIVEN-WHEN-THEN" structure?
- [ ] Test name describes expected behavior (not implementation)?
- [ ] Test would catch a bug if logic changed incorrectly?
- [ ] Test verifies OUTPUT/BEHAVIOR (not just function called)?
- [ ] Removing this test would reduce confidence in code?

# If answer is "NO" to any → Test is probably valueless
```

**Key Insight:**
- **Goal:** Test behavior, not implementation
- **Good test:** Fails when behavior breaks, passes when behavior correct
- **Bad test:** Passes even when behavior broken (because mocks hide bugs)

---

### Anti-Pattern Detection Checklist

**Run this before marking any work "complete":**

- [ ] **Partial Thoroughness:** All modules checked against explicit targets (not "feels good")?
- [ ] **Percentage Point Blindness:** Checked uncovered line count (not just percentage)?
- [ ] **Coverage Complacency:** Re-ran coverage report (not relying on old data)?
- [ ] **Test Planning After Code:** Tests written BEFORE implementation (TDD followed)?
- [ ] **Spot Checking:** ALL modules validated (not just main module)?
- [ ] **Partial Complete Assumption:** Re-validated targets when resuming work?
- [ ] **Checklist Ignored:** Test planning checklist completed BEFORE coding?

**If ANY box unchecked → Work is NOT complete. Fix anti-pattern first.**

---

### Prevention: Option B Development Approach

**When choosing between:**
- **Option A:** Continue with new features, fix coverage gaps later
- **Option B:** Fix coverage gaps NOW, then continue with structured approach

**ALWAYS choose Option B:**
- Prevents technical debt accumulation
- Ensures foundation is solid before building on it
- Catches gaps early (cheaper to fix)
- Structured development reduces rework

**Real Decision (Phase 1):**
```
User asked: "Should we continue with config loader or fix Kalshi coverage gaps first?"

❌ Option A (Feature-Driven): Continue to config loader, fix Kalshi later
- Risk: Coverage gaps grow, technical debt accumulates
- Result: Phase ends with 50% coverage, needs Phase 1.5 to fix

✅ Option B (Test-Driven): Fix Kalshi gaps NOW, then config loader
- Benefit: Solid foundation, coverage targets met incrementally
- Result: Kalshi API 93.19% ✅, Auth 100% ✅, ready for next priority
```

---

## 12. Test Coverage Accountability

### Every Deliverable Must Have Explicit Coverage Target

**Philosophy:** Every Phase N deliverable MUST have an explicit, documented test coverage target. No module ships without a coverage goal.

**Why This Matters:**
- **Prevents "forgot to test" scenarios** - Coverage targets force test planning
- **Enables progress tracking** - Know exactly how much testing remains
- **Catches gaps during planning** - Not at the end when it's expensive to fix
- **Creates accountability** - Target is explicit, achievement is measurable

**Coverage Target Tiers:**

```python
# Infrastructure modules (connection pools, loggers, config loaders)
INFRASTRUCTURE_TARGET = 80  # ≥80% coverage

# Business logic (CRUD operations, trading logic, position management)
BUSINESS_LOGIC_TARGET = 85  # ≥85% coverage

# Critical path (API auth, order execution, risk management)
CRITICAL_PATH_TARGET = 90  # ≥90% coverage
```

**Pattern: Deliverable → Coverage Target Mapping**

When adding a Phase N deliverable to DEVELOPMENT_PHASES:

1. **Identify module type** (infrastructure / business logic / critical path)
2. **Assign coverage target** based on tier
3. **Document in "Critical Module Coverage Targets" section**
4. **Track in todo list** during implementation

**Example: Phase 1 Coverage Targets**

```markdown
### Critical Module Coverage Targets (Phase 1)

**API Connectors (Critical Path):** ≥90%
- kalshi_client.py: Target 90%+
- kalshi_auth.py: Target 90%+
- rate_limiter.py: Target 90%+

**Configuration (Infrastructure):** ≥80%
- config_loader.py: Target 85%+ (higher due to complexity)

**Database (Business Logic):** ≥85%
- crud_operations.py: Target 87%+ (higher due to financial data)
- connection.py: Target 80%+

**Utilities (Infrastructure):** ≥80%
- logger.py: Target 80%+
```

**Validation Checkpoints:**

**At Phase Start (Proactive):**
- Extract ALL deliverables from phase task list
- Verify EACH has explicit coverage target
- If missing → Add target BEFORE starting implementation

**During Implementation (Continuous):**
- Track coverage in todo list
- Run coverage reports frequently
- Update targets if scope changes

**At Phase Completion (Retrospective):**
- Verify ALL modules met or exceeded targets
- Document final coverage in completion report
- Identify modules that need Phase N+1 improvements

**Common Mistake: "We'll add tests later"**

```markdown
❌ WRONG: Defer test coverage to "Phase 1.5"
- Phase 1: 50% coverage, "we'll fix it later"
- Phase 1.5: Scrambling to retrofit tests
- Result: Technical debt, low confidence in code

✅ CORRECT: Meet targets incrementally
- Priority 1: API client to 90%+ → Tests written → Target met
- Priority 2: Config loader to 85%+ → Tests written → Target met
- Priority 3: Database to 87%+ → Tests written → Target met
- Result: Phase 1 ends with 94.71% coverage, high confidence
```

**Real Example (Phase 1):**

Logger module was Phase 1 deliverable but missing from coverage targets checklist. Discovered when user asked: "Why doesn't logger have a coverage target?"

**Prevention (3-Layer Defense):**
1. **Phase Start:** Validate deliverables → coverage targets mapping
2. **Documentation:** Add this section (Pattern 10)
3. **Phase Completion:** Verify all modules met targets

**Related Documents:**
- `CLAUDE.md` Section 3, Step 2 (Phase start coverage validation)
- `CLAUDE.md` Section 9, Step 1 (Phase completion coverage verification)
- `DEVELOPMENT_PHASES_V1.10.md` (Phase-specific coverage targets)

---

## Summary: Philosophy Checklist

Before marking any feature complete, validate ALL principles followed:

- [ ] **TDD:** Tests written before implementation? (80%+ coverage)
- [ ] **DID:** Multiple validation layers implemented? (pre-commit + pre-push + CI)
- [ ] **DDD:** Requirements/ADRs documented before code? (REQ-XXX-NNN, ADR-XXX)
- [ ] **Data-Driven:** Configuration externalized (not hard-coded)?
- [ ] **Fail-Safe:** Validation scripts skip gracefully (don't crash)?
- [ ] **Explicit:** Code clarity prioritized over brevity?
- [ ] **Consistent:** All dependent docs updated? (follow cascade rules)?
- [ ] **Maintainable:** Maintenance guides written? (time estimates provided)
- [ ] **Secure:** No hardcoded credentials? (all in .env)
- [ ] **Coverage Targets:** All deliverables have explicit coverage targets? (deliverable → target mapping validated)
- [ ] **Anti-Patterns Avoided:** Ran Anti-Pattern Detection Checklist? ⚠️ **NEW**

**If ANY box unchecked → Feature NOT complete.**

---

## Related Documentation

**Testing & Validation:**
- `docs/foundation/TESTING_STRATEGY_V3.6.md` - Testing infrastructure
- `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Code quality

**Process & Workflow:**
- `CLAUDE.md` Section 3 (Session Handoff Workflow)
- `CLAUDE.md` Section 4 (Critical Patterns)
- `CLAUDE.md` Section 5 (Document Cohesion & Consistency)
- `CLAUDE.md` Section 8 (Security Guidelines)
- `CLAUDE.md` Section 9 (Phase Completion Protocol)

**Validation Configuration:**
- `.pre-commit-config.yaml` - Pre-commit hooks (Layer 1)
- `.git/hooks/pre-push` - Pre-push hooks (Layer 2)
- `.github/workflows/ci.yml` - CI/CD pipeline (Layer 3)
- `docs/utility/GITHUB_BRANCH_PROTECTION_CONFIG.md` - Branch protection (Layer 4)

**Security:**
- `docs/utility/SECURITY_REVIEW_CHECKLIST.md` - Pre-commit security checklist

---

**END OF DOCUMENT**
