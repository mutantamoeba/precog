# Testing Strategy V3.3

**Document Type:** Foundation
**Status:** ✅ Active
**Version:** 3.3
**Created:** 2025-10-23
**Last Updated:** 2025-11-30
**Changes in V3.3:**
- **Test Isolation Patterns Section (NEW)** - Added comprehensive test isolation requirements based on Phase 1.9 findings
- **5 Isolation Patterns Documented** - Transaction-based isolation, FK dependency chain, cleanup ordering, parallel safety, SCD Type 2 isolation
- **Root Cause Analysis** - Documents why 12+ tests failed in Phase 1.9 (DB state contamination, FK violations, cleanup order issues)
- **Cross-Reference** - Links to detailed TEST_ISOLATION_PATTERNS_V1.0.md in `/docs/testing/`
- **Updated TOC** - Added Section 9.5: Test Isolation Patterns
**Changes in V3.2:**
- **All 8 Test Types Now MANDATORY** - All modules must have all 8 test types regardless of phase
- **Removed Phase-Based Test Type Deferral** - All test types required from Phase 1 onwards
- **Updated Tier Requirements Matrix** - Critical Path, Business Logic, and Infrastructure ALL require 8 test types
- **Added test type coverage audit script** - `scripts/audit_test_type_coverage.py` enforces requirements
- **Pre-push hook integration** - Test type coverage check added to pre-push validation (step 8)
- **Why This Change:** Phase 2 MarketDataManager revealed testing gaps. Performance/chaos tests deferred to Phase 5+ left critical infrastructure under-tested.
**Changes in V3.1:**
- **Enhanced Coverage Tier Classification** - Updated tier framework based on TDD/security/accuracy emphasis
- **Position Manager**: Business Logic (85%) → Critical Path (90%)
  - Rationale: Handles money (P&L tracking), real-time decisions (exit hierarchy), high blast radius (affects ALL positions)
- **Kalshi Client**: Integration Points (75%) → Critical Path (90%)
  - Rationale: Handles money (trade execution), security (API auth)
  - Current coverage: 97.91% (already exceeds new target)
- **ESPN Client**: Removed from critical path (remains 75%)
  - Rationale: Read-only data fetching, no money/security impact
- **Added Risk-Based Classification Framework**:
  - Clear decision criteria: Financial impact, security impact, real-time impact, blast radius
  - Classification examples table showing WHY modules are in each tier
  - Rationales for EACH module in coverage targets table
- **Emphasis on TDD Philosophy**: Coverage targets now explicitly tied to risk factors (money, security, real-time)
**Changes in V3.0:**
- **Comprehensive 8 Test Type Framework** - Expanded from 4 test categories to 8 comprehensive test types addressing Phase 1.5 TDD failure root cause
- **Test Type Coverage Requirements (REQ-TEST-012)** - Matrix of module tier × test type coverage (Critical Path needs all 8, Infrastructure needs 5)
- **Mock Usage Restrictions (REQ-TEST-013)** - Explicit guidance on when mocks are APPROPRIATE (external APIs, time) vs. FORBIDDEN (database, internal logic, config)
- **Integration Testing Philosophy** - "Test with REAL infrastructure, not mocks" - database, config, logging fixtures from conftest.py required
- **Property-Based Testing with Hypothesis (REQ-TEST-018)** - Mathematical invariant testing, 100+ auto-generated test cases per property
- **End-to-End Testing Requirements (REQ-TEST-019)** - Complete workflow testing (fetch → analyze → execute → monitor → exit)
- **Stress Testing Requirements (REQ-TEST-016)** - Infrastructure limit testing (connection pool exhaustion, API rate limits, concurrent operations)
- **Race Condition Testing** - Concurrent operation validation with threading/multiprocessing
- **Performance Testing** - Latency/throughput benchmarks (Phase 5+)
- **Chaos Testing** - Failure recovery scenarios (Phase 5+)
- **Phase-Based Test Type Roadmap** - When each test type becomes required (Phases 1-5)
- **Test Type Decision Tree** - "Which test types do I need for this module?" flowchart
- **Real-World Examples** - Concrete examples from Strategy Manager refactoring (17 tests, all mocked → 13/17 failed with real DB)
- **Cross-References** - REQ-TEST-012 through REQ-TEST-019, ADR-076, Pattern 13 (Test Coverage Quality), TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md
**Changes in V2.1:**
- Added Coverage Target Workflow section with tier-based target framework
- PR description template for coverage improvements
- CI/CD enforcement strategy
- Phase completion review checklist
**Changes in V2.0:**
- PHASE 0.6C major expansion with implementation details
- Added Configuration, Test Organization, Test Factories sections
- Added Test Execution Scripts, Parallel Execution, Debugging sections

**Owner:** Development Team
**Applies to:** All Phases (0.6c - 10)

---

## Executive Summary

This document defines the **comprehensive testing strategy** for the Precog trading system across all development phases. It covers both strategy (what/why) and implementation (how) for testing infrastructure.

**Phase 1.5 Update:** Expanded to include 8 test type framework addressing TDD failure root cause. Over-reliance on mocks created false confidence by testing "did we call the right function?" instead of "does the system work correctly?". This version establishes when mocks are appropriate (external APIs, time) vs. forbidden (database, internal logic, config).

**Key Requirements:**
- ✅ Minimum 80% code coverage (project-wide)
- ✅ All tests pass before merge/deploy
- ✅ Critical tests marked and monitored
- ✅ Automated testing in CI/CD pipeline (Phase 0.7)
- ✅ Test factories for consistent test data
- ✅ Organized test structure (unit/integration/fixtures)
- ✅ **8 test types applied based on module tier** (NEW - REQ-TEST-012)
- ✅ **Mock usage restricted to external dependencies only** (NEW - REQ-TEST-013)
- ✅ **Integration tests use REAL infrastructure** (NEW - REQ-TEST-014)

---

## Table of Contents

1. [Testing Framework](#testing-framework)
2. [Configuration](#configuration)
3. [Test Organization](#test-organization)
4. [Test Categories (8 Types)](#test-categories) ⭐ **UPDATED**
5. [When to Use Mocks vs. Real Infrastructure](#when-to-use-mocks-vs-real-infrastructure) ⭐ **NEW**
6. [Test Type Requirements Matrix](#test-type-requirements-matrix) ⭐ **NEW**
7. [Phase-Based Test Type Roadmap](#phase-based-test-type-roadmap) ⭐ **NEW**
8. [Test Factories](#test-factories)
9. [Test Fixtures](#test-fixtures)
10. [Test Isolation Patterns](#test-isolation-patterns) ⭐ **NEW V3.3**
11. [Coverage Requirements](#coverage-requirements)
12. [Running Tests](#running-tests)
13. [Test Execution Scripts](#test-execution-scripts)
14. [Parallel Execution](#parallel-execution)
15. [Critical Test Scenarios](#critical-test-scenarios)
16. [Debugging Tests](#debugging-tests)
17. [Best Practices](#best-practices)
18. [CI/CD Integration](#cicd-integration)
19. [Future Enhancements](#future-enhancements)

---

## Testing Framework

### Core Tools

**Test Runner:** pytest 8.4+
- **Why:** Industry standard, powerful fixtures, excellent plugin ecosystem
- **Config:** `pyproject.toml` (Phase 0.6c+)
- **Plugins:** pytest-cov, pytest-asyncio, pytest-mock, pytest-xdist, pytest-html

**Coverage Tool:** pytest-cov 5.1+
- **Why:** Integrated with pytest, supports HTML reports
- **Minimum:** 80% coverage across all modules
- **Reports:** `htmlcov/` (HTML), `coverage.xml` (CI/CD)

**Test Data:** factory-boy 3.3+ + faker 30.8+
- **Why:** Consistent, realistic test data generation
- **Location:** `tests/fixtures/factories.py`

**Property Testing:** Hypothesis 6.98+
- **Why:** Auto-generates edge cases, shrinks failures to minimal examples
- **Coverage:** 100+ test cases per property (vs. 5-10 manual examples)
- **Reference:** REQ-TEST-018, Pattern 10

**Code Quality:** ruff 0.8+ (formatter + linter) + mypy 1.12+ (type checker)
- **Why:** Fast, comprehensive, modern tooling
- **Integration:** Runs before tests in validate_all.sh

---

## Configuration

### pyproject.toml

All test configuration centralized in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"

addopts = [
    "-v",                             # Verbose output
    "--strict-markers",               # Enforce marker registration
    "--cov=.",                        # Coverage on all code
    "--cov-report=term-missing",      # Show missing lines
    "--cov-report=html:htmlcov",      # HTML coverage report
    "--cov-fail-under=80",            # FAIL if coverage < 80%
    "--html=test_results/latest/pytest_report.html",
]

markers = [
    "unit: Fast unit tests",
    "property: Property-based tests (Hypothesis)",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "stress: Stress tests",
    "race: Race condition tests",
    "performance: Performance benchmarks",
    "chaos: Chaos engineering tests",
    "slow: Slow tests",
    "critical: Critical tests",
    "database: Tests requiring database",
    "api: Tests requiring API access",
]

[tool.coverage.run]
source = ["."]
omit = [
    "tests/*",
    ".venv/*",
    "scripts/*",
    "*/migrations/*",
]
branch = true  # Measure branch coverage

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80.0
```

**Benefits:**
- Single source of truth for test configuration
- No separate pytest.ini file
- Integrated with other tools (ruff, mypy)

---

## Test Organization

### Directory Structure (Phase 0.6c+)

```
tests/
├── unit/                  # Fast unit tests (no external dependencies)
│   ├── __init__.py
│   ├── test_decimal_precision.py
│   ├── test_versioning.py
│   └── test_utilities.py
│
├── property/              # Property-based tests (Hypothesis) ⭐ NEW
│   ├── __init__.py
│   ├── test_decimal_properties.py
│   ├── test_probability_properties.py
│   └── test_edge_properties.py
│
├── integration/           # Integration tests (database, APIs, files)
│   ├── __init__.py
│   ├── test_database_crud.py
│   ├── test_api_client.py
│   ├── test_strategy_manager.py  # Real DB, NO mocks
│   └── test_position_lifecycle.py
│
├── e2e/                   # End-to-end workflow tests ⭐ NEW
│   ├── __init__.py
│   └── test_trading_workflow.py
│
├── stress/                # Stress and race condition tests ⭐ NEW
│   ├── __init__.py
│   ├── test_connection_pool.py
│   └── test_concurrent_operations.py
│
├── fixtures/              # Shared fixtures and test data factories
│   ├── __init__.py
│   ├── factories.py       # factory-boy test data factories
│   └── sample_data.py     # Static sample data (if needed)
│
├── conftest.py            # Pytest configuration and shared fixtures
└── README.md              # Quick testing guide
```

**Migration from Flat Structure:**

Old (Phase 0-1):
```
tests/
├── test_database_connection.py
├── test_crud_operations.py
├── test_config_loader.py
└── ...
```

New (Phase 1.5+):
- Move unit tests → `tests/unit/`
- Create property tests → `tests/property/`
- Move integration tests → `tests/integration/`
- Create E2E tests → `tests/e2e/`
- Create stress tests → `tests/stress/`
- Create `tests/fixtures/` for test data

**Why This Structure:**
- ✅ Clear separation of test types (8 types, not 2)
- ✅ Easier to run fast tests during development
- ✅ Scales better as test suite grows (Phase 5: 1000+ tests expected)
- ✅ Standard industry pattern
- ✅ Phase-based test type adoption (unit/property/integration first, E2E/stress later)

---

## Test Categories

**Phase 1.5 Update:** Expanded from 4 test categories to 8 comprehensive test types to address TDD failure root cause.

**The 8 Test Types:**
1. **Unit Tests** - Isolated function logic (fast)
2. **Property Tests** - Mathematical invariants with Hypothesis (auto-generated edge cases)
3. **Integration Tests** - Components with REAL infrastructure (database, config, logging) - NOT mocks
4. **End-to-End Tests** - Complete user workflows (fetch → analyze → execute → monitor → exit)
5. **Stress Tests** - Infrastructure limits (connection pool exhaustion, API rate limits, concurrent operations)
6. **Race Condition Tests** - Concurrent operation validation
7. **Performance Tests** - Latency/throughput benchmarks (Phase 5+)
8. **Chaos Tests** - Failure recovery scenarios (Phase 5+)

**Reference:** REQ-TEST-012 (Test Type Coverage Requirements)

---

### 1. Unit Tests

**Purpose:** Test individual functions in isolation
**Location:** `tests/unit/`
**Marker:** `@pytest.mark.unit`
**Speed:** Fast (<0.1s per test)
**Phase:** 1+ (all phases)

**Characteristics:**
- No database connections
- No file I/O (use temp directories)
- No network calls
- Pure function testing
- Mock external dependencies ONLY (APIs, time, network)

**Example:**
```python
# tests/unit/test_decimal_precision.py
import pytest
from decimal import Decimal
from precog.utils.decimal_utils import decimal_to_string

@pytest.mark.unit
def test_decimal_serializer():
    """Test Decimal to string conversion preserves precision."""
    result = decimal_to_string(Decimal('0.5200'))
    assert result == '0.5200'
    assert isinstance(result, str)

@pytest.mark.unit
def test_decimal_edge_cases():
    """Test Decimal serialization with edge case values."""
    assert decimal_to_string(Decimal('0.0001')) == '0.0001'
    assert decimal_to_string(Decimal('0.9999')) == '0.9999'
    assert decimal_to_string(Decimal('0.4275')) == '0.4275'
```

**Run unit tests only:**
```bash
pytest tests/unit/ -v
# OR
pytest -m unit
```

**When to Use:**
- Testing pure functions (input → output, no side effects)
- Testing algorithms (edge detection, Kelly sizing, Elo calculations)
- Testing data transformations (Decimal conversions, JSON serialization)
- Testing validation logic (price ranges, quantity limits)

**Coverage Target:** ≥80% (infrastructure tier)

---

### 2. Property Tests (Hypothesis)

**Purpose:** Test mathematical invariants with auto-generated inputs
**Location:** `tests/property/`
**Marker:** `@pytest.mark.property`
**Speed:** Medium (0.1s - 1s per property, runs 100+ examples)
**Phase:** 1+ (all trading logic modules)

**Characteristics:**
- Uses Hypothesis framework for input generation
- 100+ test cases auto-generated per property
- Shrinks failures to minimal reproducible example
- Tests mathematical properties, not specific examples
- Discovers edge cases humans miss

**Example:**
```python
# tests/property/test_edge_properties.py
import pytest
from hypothesis import given, strategies as st
from decimal import Decimal
from precog.analytics.edge_detection import calculate_edge

@pytest.mark.property
@given(
    true_prob=st.decimals(min_value='0.01', max_value='0.99', places=4),
    market_price=st.decimals(min_value='0.01', max_value='0.99', places=4)
)
def test_edge_calculation_commutative(true_prob, market_price):
    """
    Edge calculation should satisfy commutative property.

    Mathematical invariant: edge(p, m) = -(edge(1-p, 1-m))

    Educational Note:
    Property-based testing discovers edge cases like:
    - true_prob=0.5000, market_price=0.5001 (minimal edge)
    - true_prob=0.9999, market_price=0.0001 (maximal edge)
    - true_prob=0.0100, market_price=0.0100 (zero edge)

    Hypothesis auto-generates 100+ test cases and shrinks failures.
    """
    edge_yes = calculate_edge(true_prob, market_price)
    edge_no = calculate_edge(Decimal('1.0000') - true_prob,
                            Decimal('1.0000') - market_price)

    # Mathematical invariant
    assert abs(edge_yes + edge_no) < Decimal('0.0001')

@pytest.mark.property
@given(
    bid=st.decimals(min_value='0.0001', max_value='0.9998', places=4),
    ask=st.decimals(min_value='0.0002', max_value='0.9999', places=4)
)
def test_bid_ask_spread_always_positive(bid, ask):
    """
    Bid-ask spread must always be non-negative.

    Property: spread = ask - bid ≥ 0

    This property test will discover if our validation allows:
    - Crossed markets (bid > ask)
    - Negative spreads
    - Zero spreads (valid, but rare)
    """
    if ask >= bid:  # Hypothesis will generate both valid and invalid
        spread = ask - bid
        assert spread >= Decimal('0.0000')
    # Invalid markets (bid > ask) should be rejected by validation
```

**Run property tests only:**
```bash
pytest tests/property/ -v
# OR
pytest -m property
```

**When to Use:**
- Testing mathematical invariants (commutative, associative, distributive properties)
- Testing business rules that hold for ALL inputs (bid ≤ ask, edge = true_prob - market_price)
- Testing state transitions (position states, order states)
- Testing data validation (price ranges, quantity constraints)

**Coverage Target:** ≥85% (business logic tier)

**Reference:** REQ-TEST-018, Pattern 10 (Property-Based Testing), ADR-074

**Real-World Example:**
Phase 1.5 property tests discovered:
- 26 property tests → 2,600+ auto-generated test cases
- Hypothesis shrunk failure: `edge=0.473821` → minimal `edge=0.5000`
- 3.32s execution time (100 examples × 26 properties)
- Zero failures (properties hold for all generated inputs)

---

### 3. Integration Tests

**Purpose:** Test components working together with REAL infrastructure
**Location:** `tests/integration/`
**Marker:** `@pytest.mark.integration`
**Speed:** Medium (0.1s - 2s per test)
**Phase:** 1+ (all phases)

**⚠️ CRITICAL: NO MOCKS FOR INTERNAL INFRASTRUCTURE**

**Phase 1.5 Lesson Learned:**
Strategy Manager tests used mocks for `get_connection()` and passed 17/17 tests. When refactored to use real database fixtures, 13/17 tests failed (77% failure rate). Mocking internal infrastructure creates false confidence.

**Characteristics:**
- **Database:** Use test database with `clean_test_data` fixture (NOT mocks)
- **Configuration:** Use test YAML files (NOT mocks)
- **Logging:** Use test logger with temp directory (NOT mocks)
- **Connection pooling:** Use `db_pool` fixture with real pool (NOT mocks)
- **External APIs:** Mock is APPROPRIATE (Kalshi, ESPN - expensive, flaky, rate-limited)
- Tests real connections and integration points
- Verifies components work together correctly

**Example (CORRECT - Real Infrastructure):**
```python
# tests/integration/test_strategy_manager.py
import pytest
from decimal import Decimal
from precog.trading.strategy_manager import StrategyManager

@pytest.mark.integration
@pytest.mark.database
def test_strategy_manager_crud(db_pool, db_cursor, clean_test_data):
    """
    Test Strategy Manager with REAL database, NOT mocks.

    Phase 1.5 Lesson: This test FAILED when refactored from mocks.
    Mocking get_connection() hid connection pool leak bug.

    Educational Note:
    Integration tests MUST use:
    - db_pool fixture (real connection pool)
    - db_cursor fixture (real database cursor)
    - clean_test_data fixture (real cleanup)

    NOT:
    - @patch('get_connection')  # ❌ FORBIDDEN
    - mock_connection fixture   # ❌ FORBIDDEN
    """
    manager = StrategyManager(db_pool)

    # Create strategy with REAL database insert
    strategy_id = manager.create_strategy(
        strategy_name="halftime_entry",
        strategy_version="v1.0",
        config_data={"min_edge": Decimal("0.05")}
    )

    # Retrieve with REAL database query
    strategy = manager.get_strategy(strategy_id)

    # Verify REAL data integrity
    assert strategy is not None
    assert strategy['strategy_name'] == "halftime_entry"
    assert isinstance(strategy['config_data']['min_edge'], Decimal)

@pytest.mark.integration
@pytest.mark.database
def test_strategy_manager_connection_pool_leak(db_pool, clean_test_data):
    """
    Test that Strategy Manager doesn't leak connections.

    This bug was HIDDEN by mocks. Real database fixtures exposed it.

    Verifies:
    - Connections returned to pool after use
    - Pool size doesn't grow unbounded
    - No OperationalError after 100+ operations
    """
    manager = StrategyManager(db_pool)

    # Perform 100 CRUD operations (would exhaust pool if leak exists)
    for i in range(100):
        strategy_id = manager.create_strategy(
            strategy_name=f"test_strategy_{i}",
            strategy_version="v1.0",
            config_data={"min_edge": Decimal("0.05")}
        )
        strategy = manager.get_strategy(strategy_id)
        assert strategy is not None

    # If no exception raised, connection pool is healthy
```

**Example (WRONG - Mocked Infrastructure):**
```python
# ❌ DO NOT DO THIS
from unittest.mock import patch, MagicMock

@pytest.mark.integration  # ❌ Not really integration if mocked!
@patch('precog.database.connection.get_connection')  # ❌ FORBIDDEN
def test_strategy_manager_crud_WRONG(mock_get_connection):
    """
    ❌ WRONG: Mocking internal infrastructure creates false confidence.

    Problems:
    1. Doesn't test real database interactions
    2. Doesn't catch connection pool leaks
    3. Doesn't verify Decimal type preservation
    4. Tests "did we call get_connection?" not "does it work?"
    """
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn

    manager = StrategyManager()
    strategy_id = manager.create_strategy(...)

    # This test PASSED in Phase 1, but code was BROKEN
    mock_get_connection.assert_called_once()  # ❌ Useless assertion
```

**Run integration tests only:**
```bash
pytest tests/integration/ -v
# OR
pytest -m integration
```

**When to Use:**
- Testing manager classes (StrategyManager, ModelManager, PositionManager)
- Testing database CRUD operations
- Testing configuration loading
- Testing API client integrations (with mocked external APIs)
- Testing multi-component workflows

**Coverage Target:** ≥85% (business logic tier)

**Reference:** REQ-TEST-013 (Mock Usage Restrictions), REQ-TEST-014 (Test Fixture Usage), REQ-TEST-017 (Integration Test Requirements)

---

### 4. End-to-End Tests

**Purpose:** Test complete user workflows from start to finish
**Location:** `tests/e2e/`
**Marker:** `@pytest.mark.e2e`
**Speed:** Slow (5s - 30s per test)
**Phase:** 2+ (once multiple components integrated)

**Characteristics:**
- Tests entire system workflow
- Multiple components working together
- Real database, real config, real logging
- Mock external APIs only (Kalshi, ESPN)
- Simulates actual user scenarios

**Example:**
```python
# tests/e2e/test_trading_workflow.py
import pytest
from decimal import Decimal
from unittest.mock import patch
from precog.trading.trading_orchestrator import TradingOrchestrator

@pytest.mark.e2e
@pytest.mark.database
@patch('precog.api_connectors.kalshi_client.KalshiClient')  # ✅ Mock external API
@patch('precog.api_connectors.espn_client.ESPNClient')      # ✅ Mock external API
def test_complete_trading_workflow(
    mock_espn, mock_kalshi, db_pool, clean_test_data, test_logger
):
    """
    Test complete trading workflow: fetch → analyze → execute → monitor → exit.

    Workflow:
    1. Fetch live markets from Kalshi (mocked)
    2. Fetch game state from ESPN (mocked)
    3. Calculate win probabilities (REAL model)
    4. Detect edges (REAL analytics)
    5. Execute trades if edge > threshold (REAL execution logic)
    6. Monitor position (REAL position manager)
    7. Exit on condition (REAL exit evaluator)

    Educational Note:
    End-to-end tests verify complete workflows work correctly.
    Mock ONLY external dependencies (APIs, network).
    Use REAL internal components (database, models, analytics).
    """
    # ARRANGE: Mock external API responses
    mock_kalshi.get_markets.return_value = [
        {
            'ticker': 'NFL-KC-BUF-YES',
            'yes_bid': Decimal('0.5500'),
            'yes_ask': Decimal('0.5600'),
        }
    ]

    mock_espn.get_game_state.return_value = {
        'home_team': 'KC',
        'away_team': 'BUF',
        'home_score': 14,
        'away_score': 10,
        'period': 2,
        'time_remaining': '8:32',
    }

    # ACT: Run complete workflow
    orchestrator = TradingOrchestrator(db_pool, test_logger)
    results = orchestrator.run_trading_cycle()

    # ASSERT: Verify workflow completed successfully
    assert results['markets_fetched'] == 1
    assert results['edges_detected'] >= 0
    assert results['trades_executed'] >= 0
    assert results['positions_monitored'] >= 0

    # Verify database state (REAL data)
    from precog.database.crud_operations import get_all_positions
    positions = get_all_positions(db_pool)
    # Positions should exist if trades executed
    if results['trades_executed'] > 0:
        assert len(positions) > 0
```

**Run E2E tests only:**
```bash
pytest tests/e2e/ -v
# OR
pytest -m e2e
```

**When to Use:**
- Testing complete trading workflows (Phase 5+)
- Testing multi-component interactions
- Testing system-level scenarios
- Validating user stories and acceptance criteria

**Coverage Target:** ≥75% (integration points tier)

**Reference:** REQ-TEST-019 (End-to-End Test Requirements)

---

### 5. Stress Tests

**Purpose:** Test infrastructure limits and concurrent operations
**Location:** `tests/stress/`
**Marker:** `@pytest.mark.stress`
**Speed:** Slow (10s - 60s per test)
**Phase:** 1.5+ (infrastructure modules)

**Characteristics:**
- Tests connection pool exhaustion
- Tests API rate limit handling
- Tests concurrent database operations
- Tests system behavior under heavy load
- Identifies bottlenecks and resource leaks

**Example:**
```python
# tests/stress/test_connection_pool.py
import pytest
import threading
from decimal import Decimal
from precog.database.crud_operations import create_market

@pytest.mark.stress
@pytest.mark.database
def test_connection_pool_exhaustion(db_pool, clean_test_data):
    """
    Test connection pool behavior under concurrent load.

    Scenario:
    - Connection pool has max 10 connections
    - Spawn 50 threads, each tries to insert 10 markets
    - Total: 500 database operations competing for 10 connections

    Verifies:
    - Connection pool doesn't crash
    - Connections are reused correctly
    - No connection leaks
    - Graceful handling of pool exhaustion

    Educational Note:
    Stress tests reveal concurrency bugs that unit tests miss.
    This test discovered connection pool leak in Phase 1.5.
    """
    errors = []

    def create_markets_concurrently(thread_id):
        try:
            for i in range(10):
                market_id = create_market(
                    db_pool,
                    ticker=f"TEST-STRESS-T{thread_id}-M{i}",
                    yes_bid=Decimal("0.5000"),
                    yes_ask=Decimal("0.5100"),
                )
                assert market_id is not None
        except Exception as e:
            errors.append((thread_id, e))

    # Spawn 50 threads
    threads = []
    for i in range(50):
        thread = threading.Thread(target=create_markets_concurrently, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # ASSERT: No errors, all operations succeeded
    assert len(errors) == 0, f"Errors: {errors}"

@pytest.mark.stress
@pytest.mark.slow
def test_api_rate_limit_handling(mock_kalshi_client):
    """
    Test API rate limiter under heavy concurrent load.

    Scenario:
    - Kalshi allows 100 requests/minute
    - Spawn 10 threads, each makes 20 requests (200 total)
    - Rate limiter should throttle to ≤100 req/min

    Verifies:
    - Rate limiter enforces limits
    - No 429 errors from API
    - Requests queued correctly
    - Backoff/retry logic works
    """
    # Test implementation...
    pass
```

**Run stress tests only:**
```bash
pytest tests/stress/ -v
# OR
pytest -m stress
```

**When to Use:**
- Testing connection pool behavior (Phase 1+)
- Testing API rate limit handling (Phase 1+)
- Testing concurrent trading operations (Phase 5+)
- Testing system scalability

**Coverage Target:** ≥80% (infrastructure tier)

**Reference:** REQ-TEST-016 (Stress Test Requirements)

---

### 6. Race Condition Tests

**Purpose:** Test concurrent operation safety
**Location:** `tests/stress/`
**Marker:** `@pytest.mark.race`
**Speed:** Medium (1s - 5s per test)
**Phase:** 1.5+ (concurrent operations)

**Characteristics:**
- Tests thread safety
- Tests lock contention
- Tests atomic operations
- Identifies race conditions in shared state

**Example:**
```python
# tests/stress/test_race_conditions.py
import pytest
import threading
from decimal import Decimal
from precog.trading.position_manager import PositionManager

@pytest.mark.race
@pytest.mark.database
def test_concurrent_position_updates_no_race(db_pool, clean_test_data):
    """
    Test concurrent position updates don't create race conditions.

    Scenario:
    - Create position with quantity=100
    - Spawn 10 threads, each increments quantity by 10
    - Final quantity should be 200 (100 + 10*10)

    Race Condition Failure:
    - Without proper locking, final quantity might be <200
    - Lost updates if threads read/write simultaneously

    Verifies:
    - Database-level locking (SELECT FOR UPDATE)
    - Application-level locking (threading.Lock)
    - Atomic increment operations
    """
    manager = PositionManager(db_pool)

    # Create initial position
    position_id = manager.create_position(
        ticker="TEST-RACE",
        side="YES",
        quantity=100,
        avg_entry_price=Decimal("0.5000"),
    )

    def increment_quantity(thread_id):
        manager.update_position_quantity(position_id, delta=10)

    # Spawn 10 threads
    threads = []
    for i in range(10):
        thread = threading.Thread(target=increment_quantity, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # ASSERT: Final quantity = 100 + 10*10 = 200
    position = manager.get_position(position_id)
    assert position['quantity'] == 200
```

**Run race condition tests only:**
```bash
pytest -m race -v
```

**When to Use:**
- Testing concurrent database writes (Phase 1+)
- Testing concurrent position updates (Phase 5+)
- Testing shared state access
- Testing lock implementations

**Coverage Target:** ≥85% (business logic tier)

---

### 7. Performance Tests

**Purpose:** Benchmark latency and throughput
**Location:** `tests/stress/`
**Marker:** `@pytest.mark.performance`
**Speed:** Medium (1s - 10s per test)
**Phase:** 5+ (trading execution)

**Characteristics:**
- Measures execution time
- Establishes performance baselines
- Detects performance regressions
- Identifies optimization opportunities

**Example:**
```python
# tests/stress/test_performance.py
import pytest
import time
from decimal import Decimal
from precog.trading.execution_engine import ExecutionEngine

@pytest.mark.performance
@pytest.mark.slow
def test_order_execution_latency(db_pool, mock_kalshi_client):
    """
    Benchmark order execution latency.

    Baseline:
    - Order execution should complete in <500ms
    - Critical for avoiding price movement

    Measures:
    - Time from "execute order" to "order confirmed"
    - Includes: API request, response parsing, database write

    Regression Threshold:
    - ±10% from baseline (450ms - 550ms acceptable)
    """
    engine = ExecutionEngine(db_pool, mock_kalshi_client)

    latencies = []
    for i in range(100):
        start = time.perf_counter()

        order_id = engine.execute_order(
            ticker="TEST-PERF",
            side="YES",
            quantity=10,
            price=Decimal("0.5000"),
        )

        end = time.perf_counter()
        latencies.append(end - start)

    # Calculate statistics
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[95]
    p99_latency = sorted(latencies)[99]

    # ASSERT: Performance targets met
    assert avg_latency < 0.500, f"Avg latency {avg_latency:.3f}s > 500ms"
    assert p95_latency < 0.800, f"P95 latency {p95_latency:.3f}s > 800ms"
    assert p99_latency < 1.000, f"P99 latency {p99_latency:.3f}s > 1s"
```

**Run performance tests only:**
```bash
pytest -m performance -v
```

**When to Use:**
- Testing order execution latency (Phase 5+)
- Testing price update latency (Phase 5+)
- Testing model prediction speed (Phase 4+)
- Establishing performance baselines

**Coverage Target:** N/A (performance benchmarks, not coverage)

**Reference:** REQ-TEST-007 (Performance Test Requirements - Phase 0.7)

---

### 8. Chaos Tests

**Purpose:** Test failure recovery and resilience
**Location:** `tests/stress/`
**Marker:** `@pytest.mark.chaos`
**Speed:** Slow (10s - 60s per test)
**Phase:** 5+ (production readiness)

**Characteristics:**
- Simulates infrastructure failures
- Tests graceful degradation
- Tests error recovery
- Validates disaster recovery procedures

**Example:**
```python
# tests/stress/test_chaos.py
import pytest
from decimal import Decimal
from precog.trading.trading_orchestrator import TradingOrchestrator

@pytest.mark.chaos
@pytest.mark.slow
def test_database_connection_loss_recovery(db_pool, test_logger):
    """
    Test system recovery after database connection loss.

    Chaos Scenario:
    1. System running normally
    2. Database connection lost (simulated)
    3. System attempts reconnection with exponential backoff
    4. System recovers automatically

    Verifies:
    - Connection loss detected
    - Retry logic executes
    - Exponential backoff (1s, 2s, 4s, 8s delays)
    - System recovers within 30s
    - No data loss during outage
    """
    orchestrator = TradingOrchestrator(db_pool, test_logger)

    # Run trading cycle normally
    results_before = orchestrator.run_trading_cycle()
    assert results_before['status'] == 'success'

    # Simulate database connection loss
    # (Implementation depends on connection pool design)
    # ...

    # System should recover automatically
    results_after = orchestrator.run_trading_cycle()
    assert results_after['status'] == 'success'

    # Verify no data loss
    # ...
```

**Run chaos tests only:**
```bash
pytest -m chaos -v
```

**When to Use:**
- Testing disaster recovery (Phase 5+)
- Testing graceful degradation (Phase 5+)
- Testing system resilience
- Pre-production validation

**Coverage Target:** N/A (resilience testing, not coverage)

---

## When to Use Mocks vs. Real Infrastructure

**Phase 1.5 Critical Lesson:** Mocking internal infrastructure creates false confidence. Over-reliance on mocks led to 77% test failure rate when refactored to real database fixtures.

**Reference:** REQ-TEST-013 (Mock Usage Restrictions)

---

### ✅ Mocks are APPROPRIATE for:

**1. External APIs** (Kalshi, ESPN, Polymarket)
- **Why:** Expensive, rate-limited, flaky, require network access
- **Example:**
```python
@patch('precog.api_connectors.kalshi_client.KalshiClient')
def test_edge_detection_with_mocked_api(mock_kalshi):
    """✅ CORRECT: Mock external API (Kalshi)."""
    mock_kalshi.get_market.return_value = {
        'ticker': 'NFL-KC-BUF-YES',
        'yes_bid': Decimal('0.5500'),
    }
    # Test edge detection logic
```

**2. Time-Dependent Code** (`datetime.now()`, `time.sleep()`)
- **Why:** Non-deterministic, difficult to test time-sensitive logic
- **Example:**
```python
@patch('precog.utils.time_utils.datetime')
def test_position_holding_time(mock_datetime):
    """✅ CORRECT: Mock time for deterministic tests."""
    mock_datetime.now.return_value = datetime(2025, 11, 17, 10, 0, 0)
    # Test position holding time calculation
```

**3. Random Number Generation** (`random.random()`, `uuid.uuid4()`)
- **Why:** Non-deterministic, need reproducible tests
- **Example:**
```python
@patch('uuid.uuid4')
def test_trade_id_generation(mock_uuid):
    """✅ CORRECT: Mock UUID for deterministic tests."""
    mock_uuid.return_value = 'test-trade-id-123'
    # Test trade ID generation logic
```

**4. Network Requests** (HTTP clients, WebSockets)
- **Why:** Expensive, unreliable, require external services
- **Example:**
```python
@patch('requests.get')
def test_espn_api_client(mock_get):
    """✅ CORRECT: Mock network request."""
    mock_get.return_value.json.return_value = {'game_id': '12345'}
    # Test ESPN API client logic
```

**5. File I/O in Some Cases** (when testing error handling, not core functionality)
- **Why:** Can use temp directories for real I/O, mock only for error simulation
- **Example:**
```python
@patch('builtins.open', side_effect=PermissionError)
def test_config_file_permission_error(mock_open):
    """✅ CORRECT: Mock file I/O to simulate permission error."""
    with pytest.raises(PermissionError):
        ConfigLoader.load_config('config.yaml')
```

---

### ❌ Mocks are FORBIDDEN for:

**1. Database** (MUST use test database with `clean_test_data` fixture)
- **Why:** Mocking database hides connection leaks, type coercion bugs, SQL errors
- **Example:**
```python
# ❌ WRONG
@patch('precog.database.connection.get_connection')
def test_strategy_manager_WRONG(mock_get_connection):
    """❌ FORBIDDEN: Mocking database hides bugs."""
    mock_conn = MagicMock()
    mock_get_connection.return_value = mock_conn
    # This test will PASS even if code is BROKEN

# ✅ CORRECT
@pytest.mark.integration
def test_strategy_manager_CORRECT(db_pool, db_cursor, clean_test_data):
    """✅ CORRECT: Use real database fixtures."""
    manager = StrategyManager(db_pool)
    # This test will FAIL if connection pool leaks
```

**2. Internal Application Logic** (strategy manager, model manager, position manager)
- **Why:** These are the components we're testing, mocking defeats the purpose
- **Example:**
```python
# ❌ WRONG
@patch('precog.trading.strategy_manager.StrategyManager.create_strategy')
def test_trading_orchestrator_WRONG(mock_create_strategy):
    """❌ FORBIDDEN: Mocking internal logic defeats testing."""
    mock_create_strategy.return_value = 123
    # This doesn't test if StrategyManager actually works

# ✅ CORRECT
def test_trading_orchestrator_CORRECT(db_pool, clean_test_data):
    """✅ CORRECT: Use real internal components."""
    orchestrator = TradingOrchestrator(db_pool)
    # This tests if StrategyManager integration actually works
```

**3. Configuration Loading** (MUST use test configs, not mocks)
- **Why:** Mocking config hides YAML parsing errors, type conversion bugs
- **Example:**
```python
# ❌ WRONG
@patch('precog.config.config_loader.ConfigLoader.load_config')
def test_config_WRONG(mock_load_config):
    """❌ FORBIDDEN: Mocking config hides YAML errors."""
    mock_load_config.return_value = {'min_edge': 0.05}  # ❌ float, not Decimal!
    # This test will PASS even if config has float contamination

# ✅ CORRECT
def test_config_CORRECT(temp_config_dir):
    """✅ CORRECT: Use real test config files."""
    config = ConfigLoader.load_config('test_config.yaml')
    # This test will FAIL if config has float instead of Decimal
    assert isinstance(config['min_edge'], Decimal)
```

**4. Logging** (MUST use test logger, capture output)
- **Why:** Mocking logger hides logging errors, missing log statements
- **Example:**
```python
# ❌ WRONG
@patch('precog.utils.logger.get_logger')
def test_logging_WRONG(mock_get_logger):
    """❌ FORBIDDEN: Mocking logger hides logging errors."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    # This doesn't test if logging actually works

# ✅ CORRECT
def test_logging_CORRECT(test_logger, caplog):
    """✅ CORRECT: Use real test logger, capture output."""
    logger = test_logger
    logger.info("Test message")
    assert "Test message" in caplog.text
```

**5. Connection Pooling** (MUST use `db_pool` fixture with real pool)
- **Why:** Mocking pool hides connection leaks, resource exhaustion
- **Example:**
```python
# ❌ WRONG
@patch('precog.database.connection.get_pool')
def test_pool_WRONG(mock_get_pool):
    """❌ FORBIDDEN: Mocking connection pool hides leaks."""
    mock_pool = MagicMock()
    mock_get_pool.return_value = mock_pool
    # This test will PASS even if connections leak

# ✅ CORRECT
def test_pool_CORRECT(db_pool):
    """✅ CORRECT: Use real connection pool fixture."""
    # Perform 100 operations (would fail if pool leaks)
    for i in range(100):
        with db_pool.getconn() as conn:
            # Do database work
            pass
```

**6. Any Infrastructure We Control** (our code, our database, our config files)
- **Why:** We control this infrastructure, so we can provide real test fixtures
- **Rule of Thumb:** If you can provide a test fixture, DON'T mock it

---

### Decision Tree: Should I Mock This?

```
Is it an external dependency (API, network, time)?
├─ YES → ✅ Mock is APPROPRIATE
└─ NO → Is it infrastructure we control?
    ├─ YES → ❌ Mock is FORBIDDEN (use test fixtures)
    └─ NO → ✅ Mock is APPROPRIATE (external system)
```

**Examples:**
- Kalshi API → External dependency → ✅ Mock
- Our database → We control it → ❌ Use test database
- ESPN API → External dependency → ✅ Mock
- Our config files → We control them → ❌ Use test YAML files
- `datetime.now()` → Non-deterministic → ✅ Mock
- Our logging → We control it → ❌ Use test logger fixture
- `random.random()` → Non-deterministic → ✅ Mock
- Our connection pool → We control it → ❌ Use `db_pool` fixture

---

### Enforcement

**Pre-Commit Code Review Checks:**
```bash
# Check for forbidden mock patterns
git grep "@patch('precog.database" -- tests/
git grep "@patch('precog.config" -- tests/
git grep "mock_connection" -- tests/
git grep "mock_pool" -- tests/
```

**Test Review Checklist (Pattern 13):**
- [ ] Tests use real infrastructure? (database, config, logging)
- [ ] Mocks used only for external dependencies? (APIs, time, network)
- [ ] Integration tests use `clean_test_data` fixture?
- [ ] No `@patch` decorators for internal infrastructure?

**Reference:** REQ-TEST-013 (Mock Usage Restrictions), Pattern 13 (Test Coverage Quality)

---

## Test Type Requirements Matrix

**Reference:** REQ-TEST-012 (Test Type Coverage Requirements)

This matrix defines which test types are required for each module tier:

| Module Tier | Unit | Property | Integration | E2E | Stress | Race | Performance | Chaos |
|-------------|------|----------|-------------|-----|--------|------|-------------|-------|
| **Critical Path** (≥90% coverage) | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Business Logic** (≥85% coverage) | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Infrastructure** (≥80% coverage) | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |

**⚠️ V3.2 UPDATE: All 8 Test Types Now Required for ALL Tiers**

**Why This Change (Lessons Learned from Phase 2):**
- **Performance tests deferred to Phase 5+** → Critical path latency issues discovered in production, not testing
- **Chaos tests deferred to Phase 5+** → Failure recovery bugs in MarketDataManager found during integration, not testing
- **Race tests optional for Infrastructure** → Connection pool race conditions discovered in stress testing, not earlier
- **Prevention:** All 8 test types from Phase 1 catches issues before they become expensive to fix

**Enforcement:**
```bash
# Run test type coverage audit
python scripts/audit_test_type_coverage.py --strict

# Pre-push hook automatically runs this check (step 8)
```

**Legacy Reference (V3.1 - Now Deprecated):**
- Business Logic previously: 6 types (stress/race optional, performance/chaos N/A)
- Infrastructure previously: 4 types (property/e2e/performance/chaos N/A)
- Integration Points previously: 3 types

**Legend:**
- ✅ **Required:** Must have tests of this type - enforced by audit script

---

### Module Tier Examples

**Critical Path (≥90% coverage, all 8 test types):**
- API authentication (kalshi_auth.py)
- Trade execution (execution_engine.py)
- Risk management (risk_manager.py)
- Position monitoring (position_monitor.py)

**Business Logic (≥85% coverage, 6 test types):**
- CRUD operations (crud_operations.py)
- Model predictions (probability_model.py)
- Edge detection (edge_detector.py)
- Kelly sizing (kelly_calculator.py)
- Strategy Manager (strategy_manager.py)
- Model Manager (model_manager.py)
- Position Manager (position_manager.py)

**Infrastructure (≥80% coverage, 3 test types):**
- Logger (logger.py)
- Config loader (config_loader.py)
- Connection pooling (connection.py)
- Rate limiting (rate_limiter.py)

**Integration Points (≥75% coverage, 3 test types):**
- API clients (kalshi_client.py, espn_client.py)
- Database migrations (migrations/)
- File parsers (schedule_parser.py)

---

### Decision Tree: Which Test Types Do I Need?

**Step 1: Identify Module Tier**
- Is it user-facing, financial, or security-critical? → **Critical Path**
- Is it core domain logic or calculations? → **Business Logic**
- Is it supporting utilities or infrastructure? → **Infrastructure**
- Is it an external API wrapper or I/O? → **Integration Points**

**Step 2: Apply Test Type Requirements**
- Critical Path → All 8 test types
- Business Logic → 6 test types (unit, property, integration, E2E, stress optional, race optional)
- Infrastructure → 3 test types (unit, integration, stress)
- Integration Points → 3 test types (unit, integration, E2E)

**Step 3: Verify Coverage Targets**
- Critical Path ≥90%
- Business Logic ≥85%
- Infrastructure ≥80%
- Integration Points ≥75%

**Example: strategy_manager.py**
1. **Tier:** Business Logic (core domain logic)
2. **Required Tests:**
   - ✅ Unit tests (test individual methods)
   - ✅ Property tests (test mathematical invariants like "metrics always ≥0")
   - ✅ Integration tests (test with REAL database, NOT mocks)
   - ✅ E2E tests (test as part of trading workflow)
   - ⚠️ Stress tests (optional - concurrent strategy updates)
   - ⚠️ Race tests (optional - concurrent metric updates)
3. **Coverage Target:** ≥85%

---

## Phase-Based Test Type Roadmap

**⚠️ V3.2 UPDATE: ALL 8 Test Types Required from Phase 1 Onwards**

This section defines when each test type becomes required across development phases.

**Reference:** REQ-TEST-012 (Test Type Coverage Requirements)

| Test Type | Phase 1 | Phase 1.5 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|-----------|---------|-----------|---------|---------|---------|---------|
| **Unit** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Property** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Integration** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **End-to-End** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Stress** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Race** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Performance** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| **Chaos** | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |

**Why All 8 Types from Phase 1?**
- **Cost of fixing bugs increases exponentially** with each phase (10x Phase 2, 100x Phase 5)
- **Performance/chaos issues are architectural** - harder to fix later
- **Race conditions in infrastructure** propagate to all dependent code
- **Phase 2 lesson:** MarketDataManager performance and chaos issues were found late because tests were "optional"

**Enforcement:**
- Pre-push hook runs `audit_test_type_coverage.py --strict`
- CI/CD blocks PRs missing required test types
- Phase completion protocol Step 5 validates test type coverage

---

### Phase 1: Database & API Connectivity

**Required Test Types:** Unit, Integration
**Coverage Target:** ≥80% (project-wide)

**Focus:**
- Unit tests for utilities (decimal conversions, logging)
- Integration tests for database (CRUD operations with real DB)
- Integration tests for API clients (with mocked external APIs)

**Example Modules:**
- connection.py: Unit + Integration (connection pool)
- crud_operations.py: Unit + Integration (with real database)
- kalshi_client.py: Unit + Integration (with mocked Kalshi API)
- config_loader.py: Unit + Integration (with test YAML files)

---

### Phase 1.5: Manager Layer (Current Phase)

**Required Test Types:** Unit, Property, Integration, Stress
**Coverage Target:** ≥85% (business logic tier)

**Focus:**
- Property tests for mathematical invariants (edge calculation, Kelly sizing)
- Integration tests with REAL database (NO mocks for internal infrastructure)
- Stress tests for connection pool exhaustion

**Example Modules:**
- strategy_manager.py: Unit + Property + Integration + Stress
- model_manager.py: Unit + Property + Integration
- position_manager.py: Unit + Property + Integration + Stress

**Phase 1.5 Lesson:** Property tests discovered 26 invariants tested with 2,600+ auto-generated cases. Integration tests with real DB exposed 77% failure rate when refactored from mocks.

---

### Phase 2: Live Data Integration

**Required Test Types:** Unit, Property, Integration, Stress
**Optional:** End-to-End

**Focus:**
- Integration tests for ESPN/Balldontlie clients
- Stress tests for API rate limit handling
- End-to-end tests for schedule loading → database update workflows

**Example Modules:**
- espn_client.py: Unit + Integration + Stress (rate limiting)
- schedule_loader.py: Unit + Integration + E2E (schedule → database)

---

### Phase 3: Async Processing

**Required Test Types:** Unit, Property, Integration, E2E, Stress, Race

**Focus:**
- Race condition tests for concurrent WebSocket handlers
- Stress tests for concurrent position updates
- End-to-end tests for live data → price update workflows

**Example Modules:**
- websocket_handler.py: Unit + Integration + Race + Stress
- async_processor.py: Unit + Integration + E2E + Race

---

### Phase 4: Odds & Ensemble

**Required Test Types:** Unit, Property, Integration, E2E, Stress, Race

**Focus:**
- Property tests for model prediction invariants
- End-to-end tests for model training → prediction workflows
- Stress tests for model prediction throughput

**Example Modules:**
- probability_model.py: Unit + Property + Integration + E2E
- ensemble_aggregator.py: Unit + Property + Integration + Stress

---

### Phase 5: Trading Execution

**Required Test Types:** ALL 8 (Unit, Property, Integration, E2E, Stress, Race, Performance, Chaos)

**Focus:**
- Performance tests for order execution latency (<500ms)
- Chaos tests for disaster recovery (database outage, API downtime)
- End-to-end tests for complete trading workflows

**Example Modules:**
- execution_engine.py: ALL 8 test types (critical path, ≥90% coverage)
- position_monitor.py: ALL 8 test types (critical path)
- exit_evaluator.py: ALL 8 test types (critical path)
- trading_orchestrator.py: ALL 8 test types (critical path)

---

## Test Factories

### Using factory-boy for Test Data

Test factories provide consistent, realistic test data:

**Location:** `tests/fixtures/factories.py`

**Available Factories:**
- `MarketDataFactory` - Market data (prices, volume, status)
- `PositionDataFactory` - Position data (side, quantity, P&L)
- `TradeDataFactory` - Trade data (orders, executions)
- `StrategyDataFactory` - Strategy configurations
- `ProbabilityModelDataFactory` - Probability model configs
- `GameStateDataFactory` - Game state (scores, time, period)
- `DecimalEdgeCaseFactory` - Edge case decimal prices

### Basic Usage

```python
from tests.fixtures.factories import MarketDataFactory, PositionDataFactory

def test_position_pnl():
    """Test position P&L calculation."""
    # Create test market with defaults
    market = MarketDataFactory()

    # Create with custom values
    market = MarketDataFactory(
        ticker="TEST-NFL-KC-BUF-YES",
        yes_bid=Decimal("0.7500")
    )

    # Create multiple
    markets = MarketDataFactory.create_batch(5)

    # Create related data
    position = PositionDataFactory(
        ticker=market['ticker'],
        avg_entry_price=Decimal("0.5000"),
        current_price=market['yes_bid'],
        quantity=100
    )

    # Test
    expected_pnl = (Decimal("0.7500") - Decimal("0.5000")) * 100
    assert position['unrealized_pnl'] == expected_pnl
```

### Edge Case Testing

```python
from tests.fixtures.factories import DecimalEdgeCaseFactory

@pytest.mark.unit
def test_price_validation_edge_cases():
    """Test price validation with edge case values."""
    edge_cases = DecimalEdgeCaseFactory.edge_cases()

    for case in edge_cases:
        price = case['price']
        assert validate_price(price) is True
```

### Helper Functions

```python
from tests.fixtures.factories import (
    create_test_market_with_position,
    create_versioned_strategies
)

def test_market_and_position():
    """Test market with associated position."""
    market, position = create_test_market_with_position()
    assert position['ticker'] == market['ticker']

def test_strategy_versioning():
    """Test multiple versions of same strategy."""
    strategies = create_versioned_strategies("halftime_entry", 3)
    assert len(strategies) == 3
    assert strategies[0]['strategy_version'] == "v1.0"
    assert strategies[2]['strategy_version'] == "v1.2"
    assert strategies[2]['status'] == "active"  # Latest is active
    assert strategies[0]['status'] == "deprecated"  # Old is deprecated
```

---

## Test Fixtures

**Location:** `tests/conftest.py`

### Database Fixtures

**`db_pool` (session scope):**
- Creates connection pool once per test session
- Shared across all tests
- Cleanup after all tests complete
- **REQUIRED for integration tests (REQ-TEST-014)**

**`db_cursor` (function scope):**
- Provides fresh cursor for each test
- Auto-rollback after test (no pollution)
- Use for database tests
- **REQUIRED for integration tests (REQ-TEST-014)**

**`clean_test_data` (function scope):**
- Cleans up test records before/after each test
- Deletes records with ticker starting with 'TEST-'
- Ensures test isolation
- **REQUIRED for integration tests (REQ-TEST-014)**

**Example Usage:**
```python
@pytest.mark.integration
@pytest.mark.database
def test_strategy_manager(db_pool, db_cursor, clean_test_data):
    """
    ✅ CORRECT: Uses all 3 mandatory database fixtures.

    - db_pool: Real connection pool (NOT mocked)
    - db_cursor: Real database cursor (NOT mocked)
    - clean_test_data: Ensures test isolation (deletes TEST-* records)
    """
    manager = StrategyManager(db_pool)
    # Test implementation...
```

### Config & Logger Fixtures

**`temp_config_dir`:**
- Temporary directory for test configs
- Auto-cleanup after test

**`test_logger`:**
- Logger instance writing to temp directory
- No pollution of production logs

---

## Test Isolation Patterns

**Added in V3.3** - Based on Phase 1.9 findings where 12+ tests failed due to database state contamination.

**Full Documentation:** See `docs/testing/TEST_ISOLATION_PATTERNS_V1.0.md` for comprehensive patterns and code examples.

### Why Test Isolation Matters (Phase 1.9 Lessons)

Phase 1.9 discovered that test failures were caused by **database state contamination**, not actual bugs:

| Root Cause | Example | Impact |
|------------|---------|--------|
| Incomplete transaction rollback | Commit without rollback | Data persists between tests |
| Foreign key dependency gaps | Delete market before trades | ForeignKeyViolation errors |
| Cleanup order violations | Delete platform before events | Cascade failures |
| Parallel worker interference | Worker 1 inserts while Worker 2 deletes | Race conditions, deadlocks |
| SCD Type 2 state leakage | `row_current_ind=TRUE` not reset | Query returns wrong "current" record |

### Required Isolation Patterns (5 Patterns)

**Pattern 1: Transaction-Based Isolation (MANDATORY)**
```python
@pytest.fixture
def isolated_transaction(db_pool):
    """Use savepoints for clean rollback."""
    conn = db_pool.getconn()
    cursor = conn.cursor()
    cursor.execute("SAVEPOINT test_isolation_point")
    try:
        yield cursor
    finally:
        cursor.execute("ROLLBACK TO SAVEPOINT test_isolation_point")
        cursor.execute("RELEASE SAVEPOINT test_isolation_point")
        cursor.close()
        db_pool.putconn(conn)
```

**Pattern 2: Foreign Key Dependency Chain (MANDATORY)**

Clean up in REVERSE dependency order:
```
trades → settlements → positions → edges → markets →
game_states → events → series → platforms
```

**Pattern 3: Cleanup Fixture Ordering (MANDATORY)**
- Use `yield` in fixtures
- Cleanup runs in reverse fixture order
- Ensure FK-safe deletion sequence

**Pattern 4: Parallel Execution Safety (MANDATORY for pytest-xdist)**
- Use worker-specific prefixes: `TEST-{worker_id}-{uuid}`
- Never use global test identifiers across workers
- Isolate database connections per worker

**Pattern 5: SCD Type 2 Isolation (MANDATORY for versioned tables)**
- Reset `row_current_ind=TRUE` after each test
- Use unique identifiers per test for versioned records
- Clean both historical and current records

### Quick Reference Table

| Scenario | Pattern Required | Implementation |
|----------|------------------|----------------|
| Database test | Pattern 1 (Transactions) | Use `isolated_transaction` fixture |
| Test with FK dependencies | Pattern 2 (FK Chain) | Cleanup in reverse order |
| Fixture with cleanup | Pattern 3 (Ordering) | Use `yield` with cleanup after |
| Parallel test execution | Pattern 4 (Worker Safety) | Worker-specific prefixes |
| SCD Type 2 tables | Pattern 5 (SCD Isolation) | Reset `row_current_ind` |

### Cross-References

- **Full Documentation:** `docs/testing/TEST_ISOLATION_PATTERNS_V1.0.md`
- **Related Requirements:** REQ-TEST-014 (Integration tests use real infrastructure)
- **Related ADRs:** ADR-018/019/020 (Dual Versioning), ADR-076 (Testing Strategy)
- **Implementation:** `tests/conftest.py` (fixtures to be updated in Phase 1.9 Part B)

---

## Coverage Requirements

### Minimum Coverage: 80%

**Enforced by:** pyproject.toml `fail_under = 80.0`
**Command:** `pytest --cov --cov-fail-under=80`

### Per-Module Targets (Updated Phase 1.5 - TDD/Security/Accuracy Emphasis)

**Classification Rationale:**
- **Critical Path (90%+)**: Handles money, security, or real-time decisions (high blast radius)
- **Business Logic (85%+)**: Core domain logic, moderate complexity (medium blast radius)
- **Infrastructure (80%+)**: Support code, well-tested libraries (low blast radius)

| Module | Tier | Target | Critical | Rationale |
|--------|------|--------|----------|-----------|
| `execution_engine.py` | Critical Path | 90%+ | ✅ Yes | **💰 Handles money**: Order execution, real trading |
| `position_monitor.py` | Critical Path | 90%+ | ✅ Yes | **💰 Handles money + 🎯 Real-time**: Exit decisions every second |
| `position_manager.py` | Critical Path | 90%+ | ✅ Yes | **💰 Handles money + 🎯 Real-time**: P&L tracking, trailing stops, 10-condition exit hierarchy |
| `kalshi_auth.py` | Critical Path | 90%+ | ✅ Yes | **🔒 Security**: RSA-PSS authentication, API access control |
| `kalshi_client.py` | Critical Path | 90%+ | ✅ Yes | **💰 Handles money + 🔒 Security**: Trade execution, account balance, API auth |
| `strategy_manager.py` | Business Logic | 85%+ | ✅ Yes | Config storage, status transitions (no real-time decisions) |
| `model_manager.py` | Business Logic | 85%+ | ✅ Yes | Config storage, validation metrics (no real-time decisions) |
| `crud_operations.py` | Business Logic | 85%+ | ✅ Yes | Data access layer, SCD Type 2 logic |
| `connection.py` | Infrastructure | 80%+ | 🟡 Medium | Database pooling, uses well-tested psycopg2 library |
| `config_loader.py` | Infrastructure | 80%+ | 🟡 Medium | YAML loading, uses well-tested PyYAML library |
| `logger.py` | Infrastructure | 80%+ | 🟡 Medium | Logging wrapper, uses well-tested logging library |
| `rate_limiter.py` | Infrastructure | 80%+ | 🟡 Medium | Token bucket rate limiting, non-critical if fails |
| `espn_client.py` | Infrastructure | 75%+ | 🟡 Medium | External API wrapper, read-only data fetching |

**Key Changes from Previous Version:**
1. **Position Manager**: Business Logic (85%) → Critical Path (90%)
   - **Reason**: Handles real money (P&L), real-time exit decisions, trailing stops
   - **Impact**: Bug in exit logic = lose money, bug in trailing stop = miss profits
   - **Blast Radius**: Affects EVERY open position (100+ positions in production)

2. **Kalshi Client**: Integration Points (75%) → Critical Path (90%)
   - **Reason**: Handles money (trade execution, balance), security (API auth)
   - **Current Coverage**: 97.91% (already exceeds 90% target)
   - **Impact**: Bug in execution = wrong trade, bug in auth = unauthorized access

3. **Removed ESPN Client from Critical Path**:
   - **Reason**: Read-only data fetching, no money/security impact
   - **Failure Mode**: Stale data (graceful degradation), not financial loss

### Coverage Reports

```bash
# Terminal summary with missing lines
pytest --cov --cov-report=term-missing

# HTML report (browsable)
pytest --cov --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov --cov-report=xml
# Generates coverage.xml
```

**Coverage enforcement:**
- ❌ Build fails if coverage < 80%
- ⚠️ Warning if coverage drops from previous run
- ✅ CI/CD uploads coverage to Codecov (Phase 0.7)

---

## Coverage Target Workflow

This section documents the systematic process for setting, tracking, and validating module coverage targets throughout development phases.

### Rationale

Coverage targets prevent "implementation complete but under-tested" scenarios. By setting explicit targets during phase planning, we ensure testing is prioritized equal to implementation.

**Problem Prevented:**
- Phase 1 completed with 68% initialization.py coverage (target: 90%)
- 22pp gap discovered during phase completion review
- Retroactive test writing is harder than test-driven development

**Solution:**
Explicit targets set during planning, tracked during implementation, validated during PR review.

### 1. Set Module Targets (During Phase Planning)

**Tier-Based Target Framework (TDD/Security/Accuracy Emphasis):**

| Module Tier | Coverage Target | Risk Factors | Blast Radius | Examples |
|-------------|----------------|--------------|--------------|----------|
| **Critical Path** | ≥90% | **💰 Handles money**, **🔒 Security**, **🎯 Real-time decisions** | HIGH - Affects ALL users/positions | Trade execution, position manager, API auth, Kalshi client |
| **Business Logic** | ≥85% | Core domain logic, moderate complexity | MEDIUM - Affects specific features | CRUD operations, strategy/model managers, edge detection |
| **Infrastructure** | ≥80% | Support code, uses well-tested libraries | LOW - Graceful degradation | Logger, config loader, connection pooling, rate limiting |

**Key Decision Criteria:**

**Critical Path (90%+)** - Requires ALL of:
- **Financial Impact**: Handles money (trades, balances, P&L) OR
- **Security Impact**: Handles authentication, authorization, credentials OR
- **Real-Time Impact**: Makes time-sensitive decisions (exits, entries)
- **Blast Radius**: Bug affects multiple users/positions simultaneously

**Business Logic (85%+)** - Requires:
- Core domain logic (not infrastructure)
- Moderate complexity (not trivial wrappers)
- Medium blast radius (affects specific features, not all users)

**Infrastructure (80%+)** - Characteristics:
- Support code (logging, config, connections)
- Uses well-tested third-party libraries (psycopg2, PyYAML)
- Low blast radius (graceful degradation if fails)

**Classification Examples:**

| Module | Why Critical Path (90%) | Why NOT Lower Tier |
|--------|-------------------------|-------------------|
| `position_manager.py` | 💰 Handles money (P&L tracking) + 🎯 Real-time (exit decisions every second) + Blast radius (affects ALL positions) | NOT Business Logic: Real-time decisions, not just config storage |
| `kalshi_client.py` | 💰 Handles money (trade execution) + 🔒 Security (API auth) | NOT Infrastructure: Executes trades, not just API wrapper |
| `execution_engine.py` | 💰 Handles money (order execution) + 🎯 Real-time (price walking, circuit breakers) | NOT Business Logic: Direct financial transactions |

| Module | Why Business Logic (85%) | Why NOT Higher Tier |
|--------|--------------------------|-------------------|
| `strategy_manager.py` | Core domain logic (strategy lifecycle), moderate complexity | NOT Critical Path: No real-time decisions, just config storage |
| `model_manager.py` | Core domain logic (model lifecycle), moderate complexity | NOT Critical Path: No real-time decisions, just validation metrics |
| `crud_operations.py` | Core domain logic (data access), SCD Type 2 complexity | NOT Critical Path: No direct financial transactions |

**Document Targets in DEVELOPMENT_PHASES:**

```markdown
### Phase 1: Database & API Connectivity

**Critical Module Coverage Targets:**
- initialization.py: ≥90% (critical infrastructure - database setup)
- crud_operations.py: ≥87% (business logic - data access)
- connection.py: ≥80% (infrastructure - connection pooling)
- kalshi_client.py: ≥90% (critical path - API authentication)
- kalshi_auth.py: ≥90% (critical path - RSA-PSS signing)
- rate_limiter.py: ≥80% (infrastructure - rate limit enforcement)
```

**Why Document in DEVELOPMENT_PHASES:**
- Visible during phase planning (not hidden in test configs)
- Reviewable in Phase Completion Protocol
- Easy to verify: "Are all deliverables listed? Do all have targets?"

### 2. Track Coverage Improvement (During Development)

**PR Description Template for Coverage Improvements:**

```markdown
## Coverage Changes

| Module | Before | After | Change | Target | Gap |
|--------|--------|-------|--------|--------|-----|
| initialization.py | 68.32% | 89.11% | +20.79pp | 90% | -0.89pp ✅ |
| crud_operations.py | 84.19% | 97.86% | +13.67pp | 87% | +10.86pp ✅ |

**Missing Coverage:** 7 lines
- Line 94: Path traversal error return (tested, may be branch coverage issue)
- Lines 180-181: Non-.sql migration file (edge case, low ROI)
- Lines 190-191: Migration outside project (edge case, documented security risk)
- Lines 194-195: Non-existent migration file (edge case, error already tested)

**Justification:** Remaining gaps are edge cases with low risk and high implementation cost. Coverage within 1pp of target is acceptable.
```

**What to Include:**
1. **Baseline → Current:** Show improvement trajectory
2. **Target vs. Actual:** Explicit gap calculation
3. **Missing Lines:** Document what's uncovered and why
4. **Justification:** Explain acceptable gaps

### 3. Validate Coverage (During PR Review)

**Review Checklist:**

- [ ] Does module meet documented target? (±1pp acceptable)
- [ ] Are all missing lines documented with justification?
- [ ] Do tests cover critical paths (happy path + error cases)?
- [ ] Are edge cases identified (even if not tested)?

**CI/CD Enforcement:**

```yaml
# .github/workflows/test.yml
- name: Check Coverage
  run: |
    pytest tests/ --cov=src/precog --cov-report=term --cov-fail-under=80
    # Overall project minimum: 80%
    # Per-module targets enforced in PR review
```

**Why Not Enforce Per-Module in CI:**
- Modules under development may be below target (work in progress)
- False positives from import-only modules (100% with no tests)
- CI enforces overall minimum (80%), humans enforce module targets

### 4. Acceptable Gap Criteria

**When is gap ≤1pp acceptable?**

- ✅ **Edge Cases:** Lines that test rare error conditions
  - Example: `FileNotFoundError` when migration file deleted mid-execution
- ✅ **Platform-Specific:** Code for Windows/Mac that's tested on Linux
  - Example: Windows registry access on Linux CI
- ✅ **External Dependencies:** Mocking OS/network would be complex
  - Example: Testing actual SIGTERM handler behavior
- ✅ **Diminishing Returns:** Cost to test > benefit
  - Example: 50 lines of boilerplate error formatting

**When is gap NOT acceptable?**

- ❌ **Happy Path Untested:** Main functionality has no tests
- ❌ **Security Validations:** Authentication, authorization, input validation
- ❌ **Financial Calculations:** Edge detection, kelly sizing, profit/loss
- ❌ **Data Integrity:** Database writes, SCD Type 2 updates

**Document in PR:**
```markdown
**Acceptable Gap Justification:**
Gap: 0.89pp (7 uncovered lines out of 782 total)

Uncovered lines are edge cases:
- Lines 180-181: Non-.sql migration file (validated in apply_schema, redundant check)
- Lines 190-191: Migration file outside project (path traversal attack - won't occur in practice)
- Lines 194-195: Migration file disappears during execution (race condition - unlikely)

All critical paths tested:
✅ Schema validation (lines 24-45, 100% coverage)
✅ Schema application (lines 48-125, 95% coverage)
✅ Migration application (lines 127-213, 88% coverage)
✅ Table validation (lines 216-279, 100% coverage)
```

### 5. Phase Completion Review

**Coverage Validation in Phase Completion Protocol Step 5:**

```bash
# Check all modules meet documented targets
python -m pytest tests/ --cov=src/precog --cov-report=term-missing

# Compare to DEVELOPMENT_PHASES targets
grep "≥" docs/foundation/DEVELOPMENT_PHASES_V1.7.md

# Verify gaps documented in PR descriptions
gh pr list --state merged --search "merged:>=2025-11-01"
```

**Deliverable Checklist:**
- [ ] All modules listed in DEVELOPMENT_PHASES have coverage targets?
- [ ] All targets met (±1pp acceptable with justification)?
- [ ] All gaps documented in PR descriptions?
- [ ] Next phase targets set for new modules?

### Example: Phase 1 Coverage Validation

**DEVELOPMENT_PHASES Targets (Phase 1):**
- initialization.py: ≥90%
- crud_operations.py: ≥87%
- connection.py: ≥80%

**Actual Coverage (Phase 1 Complete):**
```
initialization.py     89.11%  (target: 90%, gap: -0.89pp ✅)
crud_operations.py    97.86%  (target: 87%, gap: +10.86pp ✅)
connection.py         81.82%  (target: 80%, gap: +1.82pp ✅)
```

**Verdict:** ✅ All modules meet or exceed targets

**Next Phase Targets (Phase 2):**
- schedule_loader.py: ≥85% (business logic - NFL/NCAAF schedule parsing)
- espn_client.py: ≥80% (infrastructure - ESPN API client)
- balldontlie_client.py: ≥80% (infrastructure - Balldontlie API client)

### Anti-Patterns to Avoid

**❌ Don't:**
- Set arbitrary targets without tier-based rationale
- Accept large gaps (>5pp) without documentation
- Skip coverage validation in phase completion
- Add tests after implementation just to hit target (test-after-code)

**✅ Do:**
- Set targets during planning based on module tier
- Document all gaps with specific line numbers and justification
- Track coverage improvement in PR descriptions
- Write tests before/during implementation (TDD/test-driven)

### Cross-References
- **DEVELOPMENT_PHASES_V1.7.md:** Phase-specific module targets
- **Phase Completion Protocol (CLAUDE.md Step 5):** Coverage validation checklist
- **Pattern 10:** Property-Based Testing (achieving high coverage with generated inputs)
- **DEVELOPMENT_PHILOSOPHY_V1.3.md:** Test-Driven Development principle

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_decimal_precision.py

# Run specific test
pytest tests/unit/test_decimal_precision.py::test_decimal_edge_cases

# Run with verbose output
pytest -v

# Run with extra verbose output (show full diff)
pytest -vv
```

### By Category (Updated for 8 Types)

```bash
# Run only unit tests (fast)
pytest -m unit

# Run only property tests (Hypothesis)
pytest -m property

# Run only integration tests
pytest -m integration

# Run only end-to-end tests
pytest -m e2e

# Run only stress tests
pytest -m stress

# Run only race condition tests
pytest -m race

# Run only performance tests
pytest -m performance

# Run only chaos tests
pytest -m chaos

# Run only critical tests
pytest -m critical

# Skip slow tests
pytest -m "not slow"

# Run database tests only
pytest -m database

# Combine markers
pytest -m "unit and not slow"
pytest -m "integration or e2e"
```

### By Directory

```bash
# Run all unit tests
pytest tests/unit/

# Run all property tests
pytest tests/property/

# Run all integration tests
pytest tests/integration/

# Run all E2E tests
pytest tests/e2e/

# Run all stress tests
pytest tests/stress/

# Run specific directory
pytest tests/integration/database/
```

### With Coverage

```bash
# Run with coverage
pytest --cov

# Run with coverage report
pytest --cov --cov-report=html

# Run specific module coverage
pytest --cov=database tests/integration/
```

---

## Test Execution Scripts

### Quick Reference

| Script | Purpose | Duration | Use Case |
|--------|---------|----------|----------|
| `test_fast.sh` | Unit tests only | ~5 sec | During development |
| `test_full.sh` | All tests + coverage | ~30 sec | Before commit |
| `validate_quick.sh` | Code quality + docs | ~3 sec | Rapid feedback |
| `validate_all.sh` | Everything | ~60 sec | Before push |

### test_fast.sh

**Purpose:** Quick feedback during development
**Location:** `scripts/test_fast.sh`

```bash
./scripts/test_fast.sh
```

**What it runs:**
- Unit tests only (`tests/unit/`)
- No coverage report
- Fast (~5 seconds)

**When to use:**
- During active development
- After small code changes
- TDD workflow (red-green-refactor)

---

### test_full.sh

**Purpose:** Complete test suite with coverage
**Location:** `scripts/test_full.sh`

```bash
./scripts/test_full.sh
```

**What it runs:**
- All tests (unit + property + integration + e2e + stress)
- Full coverage report (HTML + XML)
- Saves results to `test_results/TIMESTAMP/`
- ~30 seconds

**When to use:**
- Before committing
- Before creating pull request
- End of development session

**Output:**
- HTML report: `test_results/latest/pytest_report.html`
- Coverage: `htmlcov/index.html`
- Log: `test_results/latest/test_output.log`

---

### validate_quick.sh

**Purpose:** Fast code quality validation
**Location:** `scripts/validate_quick.sh`

```bash
./scripts/validate_quick.sh
```

**What it runs:**
1. Ruff linting
2. Ruff formatting check
3. Mypy type checking
4. Documentation validation
- ~3 seconds

**When to use:**
- Every few minutes during development
- Before running tests
- Quick sanity check

---

### validate_all.sh

**Purpose:** Complete validation suite
**Location:** `scripts/validate_all.sh`

```bash
./scripts/validate_all.sh
```

**What it runs:**
1. validate_quick.sh (code quality + docs)
2. test_full.sh (all tests + coverage)
3. Security scan (hardcoded credentials)
- ~60 seconds

**When to use:**
- Before committing (MANDATORY)
- Before pushing to remote
- Phase completion
- Pre-deployment

**Exit codes:**
- 0 = All checks passed
- 1 = Validation failed

---

## Parallel Execution

### Using pytest-xdist

Run tests in parallel for faster execution:

```bash
# Run on 4 CPUs
pytest -n 4

# Run on all available CPUs
pytest -n auto

# Parallel with coverage
pytest -n auto --cov
```

**Benefits:**
- 2-4x faster test execution
- Better CPU utilization
- Same test isolation

**When to use:**
- Large test suites (>100 tests)
- CI/CD pipelines
- Before major commits

**Note:** Some integration tests may need serialization (use `@pytest.mark.serial` if needed)

---

## Critical Test Scenarios

### 1. Decimal Precision Tests

**Why Critical:** Float errors cause incorrect trade calculations

**Test Coverage:**
- ✅ Market prices stored as Decimal
- ✅ Position prices stored as Decimal
- ✅ Config values converted to Decimal
- ✅ Logs serialize Decimal to string (not float)

**Example Test:**
```python
@pytest.mark.critical
def test_decimal_not_float(db_pool, clean_test_data):
    """
    CRITICAL: Verify prices are Decimal, NOT float.

    Float errors cause incorrect trade calculations.
    """
    from tests.fixtures.factories import MarketDataFactory
    from precog.database.crud_operations import create_market, get_current_market

    market_data = MarketDataFactory()
    market_id = create_market(db_pool, **market_data)
    market = get_current_market(db_pool, market_data['ticker'])

    # CRITICAL: Must be Decimal, NOT float
    assert isinstance(market['yes_bid'], Decimal)
    assert not isinstance(market['yes_bid'], float)
```

---

### 2. SCD Type 2 Versioning Tests

**Why Critical:** Historical data integrity for auditing/compliance

**Test Coverage:**
- ✅ Old records marked `row_current_ind = FALSE`
- ✅ New records marked `row_current_ind = TRUE`
- ✅ `row_end_ts` set on old records
- ✅ History queryable

**Example Test:**
```python
@pytest.mark.critical
@pytest.mark.integration
def test_scd_type2_versioning(db_pool, clean_test_data):
    """Verify SCD Type 2 creates history correctly."""
    from tests.fixtures.factories import MarketDataFactory
    from precog.database.crud_operations import create_market, update_market_with_versioning, get_market_history

    # Create initial market
    market_data = MarketDataFactory(ticker="TEST-NFL-VERSIONING")
    create_market(db_pool, **market_data)

    # Update market (should create new version)
    update_market_with_versioning(
        db_pool,
        ticker="TEST-NFL-VERSIONING",
        yes_bid=Decimal("0.6000")
    )

    # Verify history
    history = get_market_history(db_pool, "TEST-NFL-VERSIONING")
    assert len(history) == 2

    # Current version
    current = [m for m in history if m['row_current_ind'] is True][0]
    assert current['yes_bid'] == Decimal("0.6000")

    # Historical version
    historical = [m for m in history if m['row_current_ind'] is False][0]
    assert historical['yes_bid'] == Decimal("0.5000")  # Original
    assert historical['row_end_ts'] is not None
```

---

### 3. Error Handling Tests (Phase 1.5+)

**Why Critical:** System resilience under failure conditions
**Test File:** `tests/integration/test_error_handling.py`
**Impact:** +3% coverage (87% → 90%)

**Test Coverage:**
- ✅ Connection pool exhaustion
- ✅ Database connection loss/reconnection
- ✅ Transaction rollback on failure
- ✅ Invalid YAML syntax
- ✅ Missing config files
- ✅ Missing environment variables
- ✅ Invalid data types
- ✅ Logger file permission errors
- ✅ NULL constraint violations
- ✅ Foreign key violations

**Rationale:** Initial tests focused on happy paths. Error handling tests validate graceful degradation and clear error messages.

---

### 4. SQL Injection Prevention Tests

**Why Critical:** Security vulnerability could corrupt database

**Test Coverage:**
- ✅ Parameterized queries block injection
- ✅ User input safely escaped
- ✅ No string concatenation in SQL

**Example Test:**
```python
@pytest.mark.critical
@pytest.mark.integration
def test_sql_injection_blocked(db_pool):
    """Verify SQL injection attempts are blocked."""
    from precog.database.crud_operations import fetch_one

    malicious = "'; DROP TABLE markets; --"

    # Attempt injection (should be safely escaped)
    result = fetch_one(db_pool, "SELECT %s as value", (malicious,))

    assert result['value'] == malicious  # Safely escaped

    # Verify table still exists
    tables = fetch_all(
        db_pool,
        "SELECT * FROM information_schema.tables WHERE table_name='markets'"
    )
    assert len(tables) == 1  # Table not dropped
```

---

### 5. Trade Attribution Tests

**Why Critical:** Required for A/B testing and performance analysis

**Test Coverage:**
- ✅ Every trade has `strategy_id`
- ✅ Every trade has `model_id`
- ✅ Foreign keys enforced
- ✅ Attribution queryable

---

## Debugging Tests

### Show Detailed Output

```bash
# Extra verbose (show full diff)
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Show full traceback
pytest --tb=long
```

### Stop at First Failure

```bash
# Stop at first failure
pytest -x

# Stop after N failures
pytest --maxfail=3
```

### Drop into Debugger

```bash
# Drop into pdb on failure
pytest --pdb

# Drop into pdb at start of test
pytest --trace
```

### Show Test Duration

```bash
# Show slowest 10 tests
pytest --durations=10

# Show all test durations
pytest --durations=0
```

### Logging During Tests

```bash
# Show all log output
pytest --log-cli-level=DEBUG

# Show INFO and above
pytest --log-cli-level=INFO
```

### Run Specific Failed Tests

```bash
# Run only last failed tests
pytest --lf

# Run failed tests first, then others
pytest --ff
```

---

## Best Practices

### 1. Test Naming Convention

**Convention:** `test_<what>_<scenario>`

**Good:**
- ✅ `test_create_market_with_decimal_precision`
- ✅ `test_update_market_scd_type2_versioning`
- ✅ `test_sql_injection_blocked`

**Bad:**
- ❌ `test_1`
- ❌ `test_market`
- ❌ `test_it_works`

---

### 2. Test Isolation

**Principle:** Tests should not affect each other

**How:**
- Use `clean_test_data` fixture
- Use test data with 'TEST-' prefix
- Rollback transactions after test
- Use temporary directories

---

### 3. Test Documentation

**Every test needs a docstring:**

```python
def test_decimal_precision():
    """
    Test that market prices stored as Decimal, NOT float.

    CRITICAL: Float errors cause incorrect trade calculations.
    This test ensures DECIMAL(10,4) type preserved.
    """
    # Test code...
```

---

### 4. Arrange-Act-Assert Pattern

```python
def test_create_position():
    # ARRANGE: Set up test data
    market = MarketDataFactory(ticker="TEST-NFL")

    # ACT: Perform action
    position_id = create_position(
        db_pool,
        ticker=market['ticker'],
        side="YES",
        quantity=100
    )

    # ASSERT: Verify results
    position = get_position(db_pool, position_id)
    assert position is not None
    assert position['ticker'] == market['ticker']
```

---

### 5. Test Edge Cases

**Always test:**
- ✅ Minimum values (0.0001)
- ✅ Maximum values (0.9999)
- ✅ Sub-penny precision (0.4275)
- ✅ Empty inputs
- ✅ None values
- ✅ Error conditions

---

## CI/CD Integration

### Pre-Commit Checks (Local)

**Before every commit:**
```bash
./scripts/validate_all.sh
```

**What it checks:**
- Code linting (ruff)
- Code formatting (ruff)
- Type checking (mypy)
- Documentation validation
- All tests passing
- Coverage ≥80%
- No hardcoded credentials

---

### Pre-Push Checks (Local)

**Before every push:**
```bash
./scripts/validate_all.sh
pytest -m "not slow"  # Skip slow tests locally
```

---

### Automated CI/CD (Phase 0.7 - Planned)

**GitHub Actions workflow runs on:**
- Every push to main
- Every pull request
- Scheduled nightly

**Workflow:**
1. Install dependencies
2. Run `validate_all.sh`
3. Upload coverage to Codecov
4. Upload test results as artifacts
5. Block merge if validation fails

**See:** Phase 0.7 Future Enhancements

---

## Future Enhancements

### Phase 0.7: CI/CD Integration (Planned)

**GitHub Actions Workflow:**
- Automated validation on push/PR
- Coverage reporting to Codecov
- Branch protection enforcement
- Status badges on README

**Expected Benefits:**
- Zero manual validation errors
- Team collaboration ready
- Historical quality metrics
- Public quality signals (badges)

**Prerequisites:** Phase 0.6c validation suite operational

**Reference:** REQ-CICD-001, REQ-CICD-002, REQ-CICD-003

---

### Phase 0.7: Advanced Testing (Planned)

#### Performance Benchmarking

**Tool:** pytest-benchmark
**Purpose:** Detect performance regressions

**Example:**
```python
@pytest.mark.benchmark
def test_crud_create_performance(benchmark):
    """Benchmark market creation."""
    result = benchmark(create_market, **sample_market_data)
    assert result is not None
    # Baseline: <10ms
    # Regression threshold: +10%
```

**Target Operations:**
- Database CRUD operations (<10ms each)
- API client requests (<100ms)
- Complex queries (<50ms)

**Reference:** REQ-TEST-007, ADR-052

---

#### Security Testing

**Tools:**
- Bandit (Python security linter)
- Safety (dependency vulnerability scanner)

**Integration:** CI/CD pipeline blocks merge on critical findings

**Example:**
```bash
# In CI/CD workflow
bandit -r . -ll  # High/Medium severity only
safety check --full-report
```

**Reference:** REQ-TEST-008, ADR-053

---

#### Mutation Testing

**Tool:** mutpy
**Purpose:** Validate test suite quality

**Concept:** Mutpy changes code (e.g., `>` to `>=`). Good tests catch mutations.

**Example:**
```bash
# Run mutation testing on database module
mut.py --target database/ --unit-test tests/unit/test_database*.py
```

**Target:** >80% mutation score on critical modules

**Reference:** REQ-TEST-009, ADR-054

---

## Adding Tests for New Features

### Checklist

When adding new feature in any phase:

- [ ] Write unit tests for new functions
- [ ] Write property tests for mathematical invariants (if applicable)
- [ ] Write integration tests with REAL infrastructure (database, config, logging)
- [ ] Add critical tests for trading logic
- [ ] Write stress tests for concurrent operations (if applicable)
- [ ] Write E2E tests for complete workflows (Phase 2+)
- [ ] Update factories if new models added
- [ ] Run full test suite: `pytest`
- [ ] Verify coverage: `pytest --cov`
- [ ] Update this document if new patterns emerge

---

### Example Workflow (TDD)

1. **Write failing test first**
```python
def test_new_feature():
    """Test new feature behavior."""
    result = new_function(input_data)
    assert result == expected_output
```

2. **Run test (should fail)**
```bash
pytest tests/unit/test_new_feature.py -v
```

3. **Implement feature**
```python
def new_function(input_data):
    # Implementation...
    return output
```

4. **Run test (should pass)**
```bash
pytest tests/unit/test_new_feature.py -v
```

5. **Verify coverage**
```bash
pytest --cov=module tests/unit/test_new_feature.py
```

6. **Refactor if needed**

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.0 | 2025-11-17 | **Comprehensive 8 Test Type Framework** - Expanded from 4 to 8 test types; Added mock usage restrictions (REQ-TEST-013); Added test type requirements matrix; Added phase-based roadmap; Enhanced integration testing philosophy ("test with REAL infrastructure, not mocks"); Added property-based testing with Hypothesis; Added E2E, stress, race, performance, chaos testing categories; Real-world examples from Strategy Manager refactoring |
| 2.1 | 2025-11-15 | Added Coverage Target Workflow section with tier-based targets and PR templates |
| 2.0 | 2025-10-29 | Major expansion with implementation details (Phase 0.6c) |
| 1.1 | 2025-10-24 | Added error handling test section (Phase 1.5) |
| 1.0 | 2025-10-23 | Initial testing strategy document |

---

## References

- **Configuration:** `pyproject.toml` - Test, coverage, ruff, mypy config
- **Fixtures:** `tests/conftest.py` - Shared fixtures (db_pool, db_cursor, clean_test_data REQUIRED)
- **Factories:** `tests/fixtures/factories.py` - Test data factories
- **Scripts:** `scripts/test_*.sh`, `scripts/validate_*.sh` - Execution scripts
- **Requirements:** `docs/foundation/MASTER_REQUIREMENTS_V2.19.md` - REQ-TEST-012 through REQ-TEST-019
- **ADRs:** `docs/foundation/ARCHITECTURE_DECISIONS_V2.25.md` - ADR-074, ADR-076 (Test Type Categories)
- **Patterns:** `docs/guides/DEVELOPMENT_PATTERNS_V1.14.md` - Pattern 13 (Test Coverage Quality), Pattern 26 (Resource Cleanup), Pattern 27 (Dependency Injection)
- **Root Cause Analysis:** `docs/utility/TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md` - Phase 1.5 TDD failure lessons learned
- **Validation:** `docs/foundation/VALIDATION_LINTING_ARCHITECTURE_V1.0.md` - Overall quality infrastructure

---

**END OF TESTING_STRATEGY_V3.0.md**
