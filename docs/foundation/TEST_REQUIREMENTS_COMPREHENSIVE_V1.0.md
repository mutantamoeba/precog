# Comprehensive Test Requirements

**Version:** 1.0
**Date:** 2025-11-17
**Purpose:** Establish testing standards for all Precog modules
**Triggered By:** TDD Failure Root Cause Analysis (Strategy Manager tests insufficient)

---

## Overview

This document establishes comprehensive testing requirements for the Precog trading system. These requirements address the critical gap identified in Phase 1.5: tests were insufficient despite passing, leading to undetected bugs.

**Key Principle:** "Tests passing" ≠ "Tests sufficient" ≠ "Code works"

---

## REQ-TEST-012: Test Type Coverage Requirements

**Priority:** 🔴 CRITICAL
**Phase:** 1.5+
**Status:** ✅ Complete (documented)

**Requirement:**

All modules MUST have appropriate test coverage across multiple test types. Not all modules need all test types, but all modules MUST have at minimum:

1. **Unit tests** (isolated function logic)
2. **Integration tests** (with real dependencies - database, config, logging)

**Test Type Matrix:**

| Module Type | Unit | Property | Integration | E2E | Stress | Race | Performance | Chaos |
|-------------|------|----------|-------------|-----|--------|------|-------------|-------|
| **Manager Layer** (Strategy, Model, Position) | ✅ REQ | ✅ REQ | ✅ REQ | ⚠️ OPT | ⚠️ OPT | ⚠️ OPT | ⏸️ P5+ | ⏸️ P5+ |
| **Database Layer** (connection, CRUD, init) | ✅ REQ | ✅ REQ | ✅ REQ | ❌ N/A | ✅ REQ | ⚠️ OPT | ⏸️ P5+ | ⏸️ P5+ |
| **API Layer** (Kalshi, ESPN, auth) | ✅ REQ | ⚠️ OPT | ⚠️ OPT | ❌ N/A | ⚠️ OPT | ❌ N/A | ⏸️ P5+ | ⏸️ P5+ |
| **Config/Logger** (utils) | ✅ REQ | ❌ N/A | ✅ REQ | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A |
| **Trading Execution** (Phase 5) | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ⚠️ OPT |

Legend:
- ✅ REQ = Required
- ⚠️ OPT = Optional (recommended)
- ❌ N/A = Not applicable
- ⏸️ P5+ = Deferred to Phase 5+

**Acceptance Criteria:**

- [ ] All manager modules have unit + integration + property tests
- [ ] All database modules have unit + integration + property + stress tests
- [ ] Test coverage dashboard shows test type breakdown per module
- [ ] CI/CD pipeline enforces minimum test types per module category

**Rationale:**

Different modules have different risk profiles:
- **Managers:** High complexity, business logic → need thorough testing
- **Database:** Critical infrastructure, connection pooling → need stress tests
- **API:** External dependency, rate limits → need integration tests
- **Config/Logger:** Simple utilities → unit + integration sufficient
- **Trading:** Financial risk → need ALL test types

**Reference:** ADR-076 (Test Type Categories)

---

## REQ-TEST-013: Mock Usage Restrictions

**Priority:** 🔴 CRITICAL
**Phase:** 1.5+
**Status:** ✅ Complete (documented)

**Requirement:**

Tests MUST use real infrastructure (database, config, logging) instead of mocks UNLESS the dependency is:
1. External and expensive (API calls, cloud services)
2. Time-dependent (`datetime.now()`)
3. Random/non-deterministic
4. Explicitly documented as requiring mocks

**Anti-Pattern (FORBIDDEN):**

```python
# ❌ WRONG - Mocking internal infrastructure
@patch("precog.database.connection.get_connection")
def test_create_strategy(mock_get_connection):
    mock_connection = MagicMock()
    mock_get_connection.return_value = mock_connection
    # ...
```

**Correct Pattern (REQUIRED):**

```python
# ✅ CORRECT - Using real database with test fixtures
def test_create_strategy(clean_test_data, manager, strategy_factory):
    result = manager.create_strategy(**strategy_factory)
    assert result["strategy_id"] is not None
```

**Acceptable Mock Usage:**

```python
# ✅ CORRECT - Mocking external API (expensive, rate-limited)
@patch("precog.api_connectors.kalshi_client.requests.post")
def test_place_order(mock_post):
    mock_post.return_value.json.return_value = {"order_id": "test123"}
    # ...

# ✅ CORRECT - Mocking time-dependent code
@patch("precog.utils.logger.datetime")
def test_log_timestamp(mock_datetime):
    mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0)
    # ...
```

**Acceptance Criteria:**

- [ ] No tests mock `get_connection()` or database connections
- [ ] No tests mock `ConfigLoader` or configuration loading
- [ ] No tests mock `get_logger()` or logging
- [ ] All manager tests use `clean_test_data` fixture
- [ ] All database tests use `db_pool` or `db_cursor` fixtures
- [ ] Code review checklist includes "Verify no inappropriate mocks"

**Rationale:**

Mocking internal infrastructure creates **false confidence**:
- Tests pass, but implementation has bugs
- Tests don't validate actual system behavior
- Tests tightly coupled to implementation details
- Integration bugs go undetected

**Reference:** TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md - Root Cause #1

---

## REQ-TEST-014: Test Fixture Usage Requirements

**Priority:** 🔴 CRITICAL
**Phase:** 1.5+
**Status:** ✅ Complete (documented)

**Requirement:**

All database tests MUST use fixtures from `tests/conftest.py`:

**Required Fixtures:**

1. **`db_pool`** - Session-scoped database connection pool
2. **`db_cursor`** - Function-scoped cursor with automatic rollback
3. **`clean_test_data`** - Function-scoped test data setup/cleanup

**Usage Pattern:**

```python
# ✅ CORRECT - Database test with proper fixtures
def test_create_model(clean_test_data, manager, model_factory):
    """Test model creation.

    Args:
        clean_test_data: Database cleanup fixture (ensures clean state)
        manager: ModelManager instance
        model_factory: Test data factory
    """
    model = manager.create_model(**model_factory)
    assert model["model_id"] is not None
    # cleanup happens automatically via clean_test_data fixture
```

**Forbidden Patterns:**

```python
# ❌ WRONG - Creating own connection (bypasses fixtures)
def test_create_model():
    conn = psycopg2.connect(...)  # Don't do this!
    # ...

# ❌ WRONG - No cleanup (pollutes database)
def test_create_model(manager):
    model = manager.create_model(...)
    # No cleanup → next test sees this data!
```

**Acceptance Criteria:**

- [ ] ALL database tests use `clean_test_data` fixture
- [ ] NO tests create connections manually (use fixtures)
- [ ] NO tests bypass cleanup (use fixtures)
- [ ] Test suite can run in any order (no interdependencies)
- [ ] Tests pass when run in parallel (`pytest -n auto`)

**Rationale:**

Test fixtures provide:
- **Isolation:** Each test gets clean database state
- **Cleanup:** Automatic cleanup prevents test pollution
- **Speed:** Reuses connection pool (faster than creating connections)
- **Reliability:** Tests don't depend on execution order

**Reference:** TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md - Root Cause #3

---

## REQ-TEST-015: Coverage Percentage Standards

**Priority:** 🔴 CRITICAL
**Phase:** 1.5+
**Status:** ✅ Complete (documented)

**Requirement:**

All modules MUST meet minimum coverage percentage thresholds:

**Coverage Tiers:**

| Module Category | Minimum Coverage | Rationale |
|-----------------|------------------|-----------|
| **Critical Path** (trading execution, position monitoring, exit evaluation) | ≥90% | Financial risk - bugs = lost money |
| **Manager Layer** (Strategy, Model, Position managers) | ≥85% | Business logic - core system functionality |
| **Infrastructure** (database, config, logging) | ≥80% | Foundation - must be reliable |
| **API Clients** (Kalshi, ESPN, external APIs) | ≥80% | External integration - failure impacts trading |
| **Utilities** (helpers, converters, validators) | ≥75% | Supporting code - lower risk |

**Current Status (Phase 1.5):**

| Module | Current Coverage | Target | Status |
|--------|------------------|--------|--------|
| kalshi_client.py | 93.19% | ≥80% | ✅ PASS |
| config_loader.py | 98.97% | ≥80% | ✅ PASS |
| connection.py | 81.82% | ≥80% | ✅ PASS |
| logger.py | 86.08% | ≥80% | ✅ PASS |
| crud_operations.py | 76.50% | ≥80% | ❌ FAIL (-3.5%) |
| model_manager.py | 25.75% | ≥85% | ❌ FAIL (-59.25%) |
| strategy_manager.py | 19.96% | ≥85% | ❌ FAIL (-65.04%) |

**Acceptance Criteria:**

- [ ] All modules meet minimum coverage thresholds
- [ ] CI/CD pipeline fails if coverage drops below threshold
- [ ] Coverage report generated with every test run
- [ ] Coverage trends tracked over time (no regressions)

**Rationale:**

Coverage percentage is **necessary but not sufficient**:
- High coverage ≠ good tests (can have 100% coverage with poor tests)
- Low coverage = definitely missing tests
- Combined with other requirements (REQ-TEST-012 through REQ-TEST-014), provides confidence

**Reference:** CLAUDE.md Section 9 - Phase Completion Protocol

---

## REQ-TEST-016: Stress Test Requirements for Infrastructure

**Priority:** 🟡 HIGH
**Phase:** 1.5+
**Status:** 🔵 Planned

**Requirement:**

Infrastructure components that manage limited resources MUST have stress tests:

**Components Requiring Stress Tests:**

1. **Database Connection Pool**
   - Test: 10+ concurrent connections
   - Test: Pool exhaustion recovery
   - Test: Connection leak detection
   - Target: maxconn=20+ (production-realistic)

2. **API Rate Limiting**
   - Test: 100+ requests/min (Kalshi limit)
   - Test: Rate limit backoff behavior
   - Test: Retry-After header handling
   - Target: Handle bursts without lockout

3. **Position Monitoring** (Phase 5)
   - Test: 100+ positions monitored simultaneously
   - Test: Update frequency (1 update/sec per position)
   - Test: Memory usage with large position counts
   - Target: <10MB per 100 positions

**Example Stress Test:**

```python
def test_connection_pool_concurrent_stress(db_pool):
    """Test connection pool with 20 concurrent connections."""
    import concurrent.futures

    def create_strategy(i):
        """Create strategy (requires connection)."""
        manager = StrategyManager()
        return manager.create_strategy(
            strategy_name=f"stress_test_{i}",
            strategy_version="1.0",
            approach="value",
            config={"test": True},
        )

    # Launch 20 concurrent creates (tests pool size)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(create_strategy, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Verify all succeeded (no pool exhaustion)
    assert len(results) == 20
    assert all(r["strategy_id"] is not None for r in results)
```

**Acceptance Criteria:**

- [ ] Connection pool stress test added (20+ concurrent connections)
- [ ] API rate limit stress test added (100+ req/min)
- [ ] Stress tests run in CI/CD (not just locally)
- [ ] Stress tests pass consistently (no flakiness)
- [ ] Stress test failures investigated immediately (infrastructure issue)

**Rationale:**

Infrastructure limits cause **production outages**:
- Connection pool exhaustion → can't create strategies/positions
- API rate limit exhaustion → locked out of platform for 60 seconds
- Memory exhaustion → system crashes

Stress tests catch these BEFORE production.

**Reference:** TESTING_GAPS_ANALYSIS.md - Connection Pool Testing

---

## REQ-TEST-017: Integration Test Requirements

**Priority:** 🟡 HIGH
**Phase:** 1.5+
**Status:** 🔵 Planned

**Requirement:**

Manager modules MUST have integration tests that validate interaction between components:

**Integration Test Categories:**

1. **Manager + Database**
   - Test: Strategy creation persists to database
   - Test: Model retrieval returns correct data
   - Test: Position updates reflected in database
   - Test: Transactions roll back on error

2. **Manager + Config**
   - Test: Manager uses config values correctly
   - Test: Config validation prevents invalid strategies
   - Test: Config changes require new version (immutability)

3. **Multi-Manager Integration**
   - Test: Strategy + Model + Position managers work together
   - Test: Create position referencing strategy + model (FK constraints)
   - Test: Trade attribution links to strategy + model

**Example Integration Test:**

```python
def test_strategy_model_position_integration(clean_test_data):
    """Test Strategy + Model + Position managers work together."""
    strategy_mgr = StrategyManager()
    model_mgr = ModelManager()
    position_mgr = PositionManager()  # Phase 1.5

    # Create strategy
    strategy = strategy_mgr.create_strategy(
        strategy_name="integration_test",
        strategy_version="1.0",
        approach="value",
        config={"min_edge": Decimal("0.05")},
    )

    # Create model
    model = model_mgr.create_model(
        model_name="integration_model",
        model_version="1.0",
        approach="elo",
        config={"k_factor": Decimal("20.00")},
    )

    # Create position (references strategy + model via FK)
    position = position_mgr.create_position(
        market_id="MKT-TEST-123",
        strategy_id=strategy["strategy_id"],
        model_id=model["model_id"],
        side="YES",
        quantity=100,
        entry_price=Decimal("0.5200"),
    )

    # Verify FK relationships work
    assert position["strategy_id"] == strategy["strategy_id"]
    assert position["model_id"] == model["model_id"]
```

**Acceptance Criteria:**

- [ ] Strategy + Model + Position integration tests added
- [ ] Manager + Database integration tests pass
- [ ] Manager + Config integration tests pass
- [ ] FK constraint violations caught by integration tests
- [ ] Transaction rollback tested (error handling)

**Rationale:**

Unit tests validate individual functions. Integration tests validate **system behavior**:
- Do FK constraints work?
- Do transactions roll back on error?
- Do managers work together correctly?

Integration bugs only appear when components interact.

**Reference:** TESTING_GAPS_ANALYSIS.md - Integration Tests

---

## REQ-TEST-018: Property-Based Test Requirements

**Priority:** 🟡 HIGH (for modules with mathematical invariants)
**Phase:** 1.5+
**Status:** ✅ Complete (Hypothesis implemented)

**Requirement:**

Modules with mathematical invariants MUST have property-based tests using Hypothesis:

**Modules Requiring Property Tests:**

1. **Decimal Precision** (Pattern 1)
   - Property: `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")`
   - Property: Round-trip conversion preserves precision
   - Test: 1000+ generated decimal values

2. **Kelly Criterion** (trading math)
   - Property: Kelly fraction ∈ [0, 1]
   - Property: Edge > 0 → positive Kelly fraction
   - Property: Edge ≤ 0 → zero Kelly fraction

3. **Elo Rating** (probability models)
   - Property: Win probability ∈ [0, 1]
   - Property: Rating difference → win probability monotonic
   - Property: Sum of win probabilities = 1.0 (binary markets)

4. **Position Sizing** (risk management)
   - Property: Position size ≤ max position size
   - Property: Position size ≥ 0
   - Property: Bankroll * Kelly fraction = position size

**Example Property Test:**

```python
from hypothesis import given, strategies as st

@given(
    edge=st.decimals(min_value="0.01", max_value="0.50", places=4),
    win_prob=st.decimals(min_value="0.01", max_value="0.99", places=4),
)
def test_kelly_fraction_properties(edge, win_prob):
    """Test Kelly fraction mathematical properties."""
    kelly = calculate_kelly_fraction(edge, win_prob)

    # Property 1: Kelly fraction ∈ [0, 1]
    assert Decimal("0") <= kelly <= Decimal("1")

    # Property 2: Positive edge → positive Kelly
    if edge > Decimal("0"):
        assert kelly > Decimal("0")

    # Property 3: Higher edge → higher Kelly (monotonicity)
    kelly_higher_edge = calculate_kelly_fraction(edge * 2, win_prob)
    assert kelly_higher_edge >= kelly
```

**Acceptance Criteria:**

- [ ] All mathematical functions have property tests
- [ ] Property tests generate 100+ test cases per property
- [ ] Property tests run in CI/CD (not just locally)
- [ ] Hypothesis shrinking enabled (minimal failing example)
- [ ] Custom strategies for trading domain (probabilities, prices, edges)

**Rationale:**

Example-based tests validate **specific cases**. Property tests validate **mathematical invariants** across thousands of generated inputs:
- Catches edge cases humans don't think of
- Validates behavior across entire input space
- Provides stronger confidence in mathematical correctness

**Reference:**
- CLAUDE.md Pattern 10 (Property-Based Testing with Hypothesis)
- ADR-074 (Property-Based Testing)
- REQ-TEST-008 through REQ-TEST-011

---

## REQ-TEST-019: End-to-End Test Requirements

**Priority:** 🟡 HIGH
**Phase:** 2+ (after core managers complete)
**Status:** 🔵 Planned

**Requirement:**

Complete user workflows MUST have end-to-end tests that validate the entire system:

**E2E Test Categories:**

1. **Trading Lifecycle** (Phase 5)
   - Fetch markets from Kalshi API
   - Calculate probabilities using Model Manager
   - Identify edges using Strategy Manager
   - Execute trades via API
   - Monitor positions via Position Manager
   - Exit positions based on conditions
   - Verify trade attribution (strategy_id, model_id)

2. **Strategy Lifecycle** (Phase 1.5)
   - Create strategy (draft status)
   - Update to testing status
   - Run backtests, update metrics
   - Promote to active status
   - Retire to deprecated status

3. **Model Lifecycle** (Phase 1.5)
   - Create model (draft status)
   - Update to testing status
   - Run validation, update calibration/accuracy
   - Promote to active status
   - Retire to deprecated status

**Example E2E Test:**

```python
@pytest.mark.e2e
def test_strategy_lifecycle_end_to_end(clean_test_data):
    """Test complete strategy lifecycle: draft → testing → active → deprecated."""
    manager = StrategyManager()

    # Create strategy (draft status)
    strategy = manager.create_strategy(
        strategy_name="e2e_strategy",
        strategy_version="1.0",
        approach="value",
        config={"min_edge": Decimal("0.05")},
        status="draft",
    )
    assert strategy["status"] == "draft"

    # Promote to testing
    updated = manager.update_status(
        strategy_id=strategy["strategy_id"],
        new_status="testing",
    )
    assert updated["status"] == "testing"

    # Update metrics (simulate backtesting)
    with_metrics = manager.update_metrics(
        strategy_id=strategy["strategy_id"],
        paper_roi=Decimal("0.1500"),
        paper_trades=100,
    )
    assert with_metrics["paper_roi"] == Decimal("0.1500")

    # Promote to active
    active = manager.update_status(
        strategy_id=strategy["strategy_id"],
        new_status="active",
    )
    assert active["status"] == "active"

    # Deprecate
    deprecated = manager.update_status(
        strategy_id=strategy["strategy_id"],
        new_status="deprecated",
    )
    assert deprecated["status"] == "deprecated"
```

**Acceptance Criteria:**

- [ ] Strategy lifecycle E2E test added
- [ ] Model lifecycle E2E test added
- [ ] Trading lifecycle E2E test added (Phase 5)
- [ ] E2E tests run in CI/CD (not just locally)
- [ ] E2E tests marked with `@pytest.mark.e2e` (can skip during development)

**Rationale:**

Unit/integration tests validate **components**. E2E tests validate **workflows**:
- Does the entire system work together?
- Can users complete their intended workflows?
- Are there gaps between components?

E2E tests provide **user-level confidence**.

**Reference:** TESTING_GAPS_ANALYSIS.md - End-to-End Tests

---

## Implementation Priorities

**Phase 1.5 (Immediate):**
1. ✅ REQ-TEST-012: Test Type Coverage (documented)
2. ✅ REQ-TEST-013: Mock Usage Restrictions (documented)
3. ✅ REQ-TEST-014: Test Fixture Usage (documented)
4. ✅ REQ-TEST-015: Coverage Percentage Standards (documented)
5. 🔵 REQ-TEST-016: Stress Tests (implementation pending)
6. 🔵 REQ-TEST-017: Integration Tests (implementation pending)

**Phase 2+:**
7. ✅ REQ-TEST-018: Property Tests (Hypothesis implemented in Phase 0.7)
8. 🔵 REQ-TEST-019: E2E Tests (Phase 2+)

---

## Success Metrics

**Before declaring testing strategy "complete":**

- [ ] All REQ-TEST-012 through REQ-TEST-019 requirements documented
- [ ] All Phase 1.5 requirements implemented
- [ ] All manager modules ≥85% coverage
- [ ] All infrastructure modules ≥80% coverage
- [ ] No inappropriate mocks in test suite
- [ ] All database tests use fixtures
- [ ] Stress tests passing (connection pool, API rate limits)
- [ ] Integration tests passing (multi-manager scenarios)
- [ ] CI/CD enforces all test requirements

---

## References

**Related Documents:**
- `docs/utility/TDD_FAILURE_ROOT_CAUSE_ANALYSIS_V1.0.md` - Why we need these requirements
- `TESTING_GAPS_ANALYSIS.md` - Current test coverage analysis
- `docs/foundation/TESTING_STRATEGY_V3.1.md` - Current version (will be updated to V3.0 with 8 test types)
- `docs/foundation/MASTER_REQUIREMENTS_V2.17.md` - Current version (will add these REQs in V2.16)

**Related ADRs:**
- ADR-074: Property-Based Testing with Hypothesis
- ADR-076: Test Type Categories (to be created)

**Related Patterns:**
- Pattern 10: Property-Based Testing with Hypothesis
- Pattern 11: Comprehensive Test Coverage (to be created)

---

**Sign-off:** Claude Code - 2025-11-17

**Note:** These requirements will be integrated into MASTER_REQUIREMENTS_V2.17.md (updating to V2.16) in next session.

---

**END OF TEST_REQUIREMENTS_COMPREHENSIVE_V1.0.md**
