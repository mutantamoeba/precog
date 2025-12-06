# Comprehensive Test Requirements

**Version:** 2.1
**Date:** 2025-11-30
**Purpose:** Establish testing standards for all Precog modules
**Triggered By:** TDD Failure Root Cause Analysis (Strategy Manager tests insufficient)
**Changes in V2.1:**
- **Added REQ-TEST-020 through REQ-TEST-024** - Test Isolation Requirements from Phase 1.9 lessons learned
- **REQ-TEST-020:** Transaction-Based Test Isolation (savepoint pattern)
- **REQ-TEST-021:** Foreign Key Dependency Chain Management
- **REQ-TEST-022:** Cleanup Fixture Ordering (reverse FK order)
- **REQ-TEST-023:** Parallel Execution Safety (worker prefixes)
- **REQ-TEST-024:** SCD Type 2 Test Isolation
- **Cross-references TEST_ISOLATION_PATTERNS_V1.1.md** for detailed implementation patterns
**Changes in V2.0:**
- **All 8 Test Types Now MANDATORY** - Removed N/A, OPT, P5+ designations
- **Synced with TESTING_STRATEGY_V3.4** - Both documents now have identical requirements
- **Validation via Phase 2C** - CRUD tests uncovered 3 critical bugs proving all test types needed
- **Lesson Learned:** Phase 2C race condition bug would have been caught by Race tests if they weren't OPT

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

All modules MUST have comprehensive test coverage across ALL 8 test types. No exceptions, no deferrals.

**V2.0 Mandate:** Every module, regardless of phase or category, requires all 8 test types.

**Test Type Matrix (V2.0 - All Required):**

| Module Type | Unit | Property | Integration | E2E | Stress | Race | Performance | Chaos |
|-------------|------|----------|-------------|-----|--------|------|-------------|-------|
| **Manager Layer** (Strategy, Model, Position) | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ |
| **Database Layer** (connection, CRUD, init) | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ |
| **API Layer** (Kalshi, ESPN, auth) | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ |
| **Config/Logger** (utils) | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ |
| **Trading Execution** (Phase 5) | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ | ✅ REQ |

Legend:
- ✅ REQ = Required (ALL test types mandatory for ALL modules)

**Acceptance Criteria:**

- [ ] All modules have ALL 8 test types (Unit, Property, Integration, E2E, Stress, Race, Performance, Chaos)
- [ ] Test coverage dashboard shows test type breakdown per module
- [ ] CI/CD pipeline enforces ALL 8 test types for EVERY module
- [ ] Pre-push hooks execute ALL 8 test types (not just unit tests)
- [ ] `scripts/audit_test_type_coverage.py --strict` passes

**Rationale:**

**V2.0 Rationale: All 8 test types required for ALL modules.**

Previous approach (V1.0) had tiered requirements based on "risk profiles." This failed in Phase 2C when:
- Race condition bug in `upsert_game_state()` would have been caught by Race tests
- Race tests were marked "OPT" for Database Layer
- Bug made it to integration testing, causing transaction failures

**Lessons Learned:**
- "Low-risk" modules can have high-impact bugs
- Race conditions exist everywhere concurrent operations happen
- Performance issues in "utility" modules cascade to critical paths
- Chaos testing reveals recovery bugs in ALL infrastructure

**Universal Test Type Benefits:**
- **Unit:** Validates isolated logic
- **Property:** Catches edge cases via generated inputs
- **Integration:** Validates component interactions
- **E2E:** Validates complete workflows
- **Stress:** Reveals resource exhaustion issues
- **Race:** Catches concurrent access bugs
- **Performance:** Establishes latency baselines
- **Chaos:** Validates failure recovery

**Reference:** ADR-076 (Test Type Categories), TESTING_STRATEGY_V3.4

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

## REQ-TEST-020: Transaction-Based Test Isolation

**Priority:** 🔴 CRITICAL
**Phase:** 1.9+
**Status:** 🔵 Planned
**Added:** V2.1 (Phase 1.9 lessons learned)

**Requirement:**

All database tests MUST use transaction-based isolation with PostgreSQL savepoints to guarantee complete data isolation:

**Pattern: Savepoint-Based Isolation**

```python
@pytest.fixture
def isolated_transaction(db_pool):
    """
    Provide fully isolated transaction with guaranteed rollback.

    Uses savepoint to ensure complete isolation even if test commits.

    Educational Note:
        PostgreSQL savepoints create nested transaction boundaries.
        ROLLBACK TO SAVEPOINT undoes ALL changes since savepoint,
        regardless of intermediate commits within the savepoint.
    """
    conn = db_pool.getconn()
    cursor = conn.cursor()

    # Create savepoint for complete isolation
    cursor.execute("SAVEPOINT test_isolation_point")

    try:
        yield cursor
    finally:
        # ALWAYS rollback to savepoint - undoes ALL test changes
        cursor.execute("ROLLBACK TO SAVEPOINT test_isolation_point")
        cursor.execute("RELEASE SAVEPOINT test_isolation_point")
        cursor.close()
        db_pool.putconn(conn)
```

**Anti-Pattern (FORBIDDEN):**

```python
# ❌ WRONG - Commits without isolation
def test_create_market(db_cursor):
    db_cursor.execute("INSERT INTO markets ...")
    db_cursor.connection.commit()  # Data persists to next test!
```

**Acceptance Criteria:**

- [ ] `isolated_transaction` fixture added to conftest.py
- [ ] All database tests use savepoint-based isolation
- [ ] No test data persists after test completion
- [ ] Tests pass regardless of execution order

**Rationale:**

Without transaction isolation, test data persists and causes:
- UniqueViolation errors on subsequent runs
- False positives (test passes due to leftover data)
- False negatives (test fails due to conflicting data)

**Reference:** TEST_ISOLATION_PATTERNS_V1.1.md - Pattern 1

---

## REQ-TEST-021: Foreign Key Dependency Chain Management

**Priority:** 🔴 CRITICAL
**Phase:** 1.9+
**Status:** 🔵 Planned
**Added:** V2.1 (Phase 1.9 lessons learned)

**Requirement:**

Test fixtures creating records with FK dependencies MUST create the complete dependency chain in correct order:

**FK Dependency Chain (Create Order):**

```
platforms (ROOT)
    |
    +-- series
    |       |
    |       +-- events
    |               |
    |               +-- markets
    |               |       |
    |               |       +-- positions → trades
    |               |       +-- edges
    |               |       +-- settlements
    |               |
    |               +-- game_states
```

**Pattern: Complete Hierarchy Fixture**

```python
@pytest.fixture
def complete_test_hierarchy(db_cursor, worker_prefix):
    """
    Create complete FK dependency chain for testing.

    FK Chain (must create in this order):
        platforms -> series -> events -> markets -> game_states
                                      -> positions -> trades
    """
    # 1. Platform (root of FK chain)
    db_cursor.execute("""
        INSERT INTO platforms (platform_id, platform_type, display_name, status)
        VALUES (%s, 'trading', 'Test Platform', 'active')
        ON CONFLICT (platform_id) DO NOTHING
    """, (f"{worker_prefix}-PLATFORM",))

    # 2. Series (references platform)
    db_cursor.execute("""
        INSERT INTO series (series_id, platform_id, external_id, category, title)
        VALUES (%s, %s, %s, 'sports', 'Test Series')
        ON CONFLICT (series_id) DO NOTHING
    """, (f"{worker_prefix}-SERIES", f"{worker_prefix}-PLATFORM", f"{worker_prefix}-EXT-SERIES"))

    # 3. Event (references platform and series)
    # ... continue for full chain
```

**Anti-Pattern (FORBIDDEN):**

```python
# ❌ WRONG - Assumes event exists (FK violation!)
def test_create_game_state():
    create_game_state(event_id="TEST-EVENT")  # Parent may not exist!
```

**Acceptance Criteria:**

- [ ] `complete_test_hierarchy` fixture added to conftest.py
- [ ] All tests requiring FK parents use hierarchy fixture
- [ ] ON CONFLICT handling for idempotent setup
- [ ] No ForeignKeyViolation errors in test runs

**Rationale:**

Missing parent records cause ForeignKeyViolation errors that are:
- Intermittent (depend on test execution order)
- Hard to debug (error message doesn't indicate missing parent)
- Cascade failures (one missing parent breaks many tests)

**Reference:** TEST_ISOLATION_PATTERNS_V1.1.md - Pattern 2

---

## REQ-TEST-022: Cleanup Fixture Ordering

**Priority:** 🔴 CRITICAL
**Phase:** 1.9+
**Status:** 🔵 Planned
**Added:** V2.1 (Phase 1.9 lessons learned)

**Requirement:**

Test cleanup MUST delete records in reverse FK dependency order (children before parents):

**Delete Order (Children First, Parents Last):**

```
1. trades          (leaf - references positions, markets)
2. positions       (references markets, strategies, models)
3. settlements     (references markets)
4. edges           (references markets, probability_matrices)
5. game_states     (references events)
6. markets         (references events)
7. events          (references series)
8. series          (references platforms)
9. strategies      (no FK children in tests)
10. probability_models (no FK children in tests)
11. platforms      (ROOT - delete last)
```

**Pattern: Ordered Cleanup**

```python
def cleanup_test_data(db_cursor, prefix: str):
    """
    Clean up test data in correct FK order.

    Educational Note:
        PostgreSQL enforces FK constraints on DELETE.
        Deleting a parent with existing children causes:
        - FK violation error if ON DELETE RESTRICT (default)
        - Cascade delete if ON DELETE CASCADE (dangerous!)
    """
    # Child tables first (leaf nodes in FK tree)
    db_cursor.execute("DELETE FROM trades WHERE market_id LIKE %s", (f"{prefix}%",))
    db_cursor.execute("DELETE FROM positions WHERE market_id LIKE %s", (f"{prefix}%",))
    db_cursor.execute("DELETE FROM settlements WHERE market_id LIKE %s", (f"{prefix}%",))
    db_cursor.execute("DELETE FROM edges WHERE market_id LIKE %s", (f"{prefix}%",))
    db_cursor.execute("DELETE FROM game_states WHERE event_id LIKE %s", (f"{prefix}%",))

    # Intermediate tables
    db_cursor.execute("DELETE FROM markets WHERE market_id LIKE %s", (f"{prefix}%",))
    db_cursor.execute("DELETE FROM events WHERE event_id LIKE %s", (f"{prefix}%",))
    db_cursor.execute("DELETE FROM series WHERE series_id LIKE %s", (f"{prefix}%",))

    # Root tables last
    db_cursor.execute("DELETE FROM platforms WHERE platform_id LIKE %s", (f"{prefix}%",))

    db_cursor.connection.commit()
```

**Anti-Pattern (FORBIDDEN):**

```python
# ❌ WRONG - Delete parents before children (FK violation!)
db_cursor.execute("DELETE FROM events WHERE ...")  # FK violation!
db_cursor.execute("DELETE FROM game_states WHERE ...")
```

**Acceptance Criteria:**

- [ ] Cleanup function follows reverse FK order
- [ ] All fixture teardowns use ordered cleanup
- [ ] No ForeignKeyViolation during teardown
- [ ] Tests pass when run repeatedly

**Rationale:**

Wrong delete order causes:
- ForeignKeyViolation during teardown
- Orphaned data (cleanup aborts mid-way)
- Test pollution from incomplete cleanup

**Reference:** TEST_ISOLATION_PATTERNS_V1.1.md - Pattern 3

---

## REQ-TEST-023: Parallel Execution Safety

**Priority:** 🟡 HIGH
**Phase:** 1.9+
**Status:** 🔵 Planned
**Added:** V2.1 (Phase 1.9 lessons learned)

**Requirement:**

Tests running in parallel (pytest-xdist) MUST use worker-specific data identifiers to prevent collisions:

**Pattern: Worker-Prefixed Test Data**

```python
import os

def get_test_prefix() -> str:
    """
    Get worker-specific prefix for test data isolation.

    In parallel execution (pytest-xdist), each worker gets unique prefix:
    - Worker 0: TEST-GW0-
    - Worker 1: TEST-GW1-
    - Single worker: TEST-MASTER-

    Educational Note:
        pytest-xdist sets PYTEST_XDIST_WORKER environment variable.
        Values are 'gw0', 'gw1', etc. for each worker process.
    """
    worker = os.environ.get('PYTEST_XDIST_WORKER', 'master')
    return f"TEST-{worker.upper()}"


@pytest.fixture
def worker_prefix():
    """Provide worker-specific test data prefix."""
    return get_test_prefix()


def test_create_market(worker_prefix, db_cursor):
    """Test using worker-specific ID."""
    market_id = f"{worker_prefix}-NFL-KC-BUF"  # e.g., TEST-GW0-NFL-KC-BUF
    # No collision with other workers
```

**Anti-Pattern (FORBIDDEN):**

```python
# ❌ WRONG - Hardcoded ID causes collision in parallel
market_id = "TEST-NFL-KC-BUF"  # Worker 0 and Worker 1 both use this!
```

**Acceptance Criteria:**

- [ ] `worker_prefix` fixture added to conftest.py
- [ ] All test data IDs use worker prefix
- [ ] No UniqueViolation in parallel runs
- [ ] No deadlocks between workers
- [ ] Tests pass with `pytest -n auto`

**Rationale:**

Parallel workers sharing IDs cause:
- UniqueViolation on concurrent inserts
- Deadlocks when workers lock same rows
- Race conditions with unpredictable results

**Reference:** TEST_ISOLATION_PATTERNS_V1.1.md - Pattern 4

---

## REQ-TEST-024: SCD Type 2 Test Isolation

**Priority:** 🟡 HIGH
**Phase:** 1.9+
**Status:** 🔵 Planned
**Added:** V2.1 (Phase 1.9 lessons learned)

**Requirement:**

Tests modifying SCD Type 2 records (row_current_ind flag) MUST use isolated test data to prevent state leakage:

**SCD Type 2 Invariant:**
> For any (entity_id), exactly ONE row has `row_current_ind = TRUE`

**Pattern: Isolated SCD Test Data**

```python
@pytest.fixture
def isolated_scd_test(db_cursor, worker_prefix):
    """
    Create isolated SCD Type 2 test data.

    Tests modifying row_current_ind MUST:
        1. Use unique entity IDs (worker-prefixed + UUID)
        2. Clean up ALL versions (current AND historical)
        3. Not assume any pre-existing state
    """
    market_id = f"{worker_prefix}-SCD-TEST-{uuid.uuid4().hex[:8]}"

    # Create initial version (current)
    db_cursor.execute("""
        INSERT INTO markets (
            market_id, platform_id, event_id, external_id, ticker, title,
            yes_price, no_price, market_type, status, row_current_ind
        ) VALUES (
            %s, 'test_platform', 'TEST-EVENT', %s, %s, 'SCD Test Market',
            0.5000, 0.5000, 'binary', 'open', TRUE
        )
    """, (market_id, f"{market_id}-ext", market_id))

    db_cursor.connection.commit()

    yield {'market_id': market_id}

    # Cleanup: Delete ALL versions (current AND historical)
    db_cursor.execute("DELETE FROM markets WHERE market_id = %s", (market_id,))
    db_cursor.connection.commit()
```

**Anti-Pattern (FORBIDDEN):**

```python
# ❌ WRONG - Shared market_id leaks state between tests
market_id = "TEST-MARKET-001"

def test_a():
    # Sets row_current_ind = FALSE for old version
    update_market_price(market_id, new_price)

def test_b():
    # Expects only ONE current row - fails if test_a ran first!
    result = get_current_market(market_id)
```

**Acceptance Criteria:**

- [ ] SCD Type 2 tests use UUID-based entity IDs
- [ ] Cleanup removes ALL versions (not just current)
- [ ] Tests pass regardless of execution order
- [ ] SCD Type 2 invariant validated after each test

**Rationale:**

SCD Type 2 state leakage causes:
- "More than one current row" assertion failures
- Historical versions from other tests polluting results
- Unpredictable test failures based on execution order

**Reference:** TEST_ISOLATION_PATTERNS_V1.1.md - Pattern 5

---

## Implementation Priorities

**Phase 1.5 (Immediate):**
1. ✅ REQ-TEST-012: Test Type Coverage (documented)
2. ✅ REQ-TEST-013: Mock Usage Restrictions (documented)
3. ✅ REQ-TEST-014: Test Fixture Usage (documented)
4. ✅ REQ-TEST-015: Coverage Percentage Standards (documented)
5. 🔵 REQ-TEST-016: Stress Tests (implementation pending)
6. 🔵 REQ-TEST-017: Integration Tests (implementation pending)

**Phase 1.9 (Test Infrastructure - BLOCKING):**
7. 🔵 REQ-TEST-020: Transaction-Based Test Isolation (implementation pending)
8. 🔵 REQ-TEST-021: FK Dependency Chain Management (implementation pending)
9. 🔵 REQ-TEST-022: Cleanup Fixture Ordering (implementation pending)
10. 🔵 REQ-TEST-023: Parallel Execution Safety (implementation pending)
11. 🔵 REQ-TEST-024: SCD Type 2 Test Isolation (implementation pending)

**Phase 2+:**
12. ✅ REQ-TEST-018: Property Tests (Hypothesis implemented in Phase 0.7)
13. 🔵 REQ-TEST-019: E2E Tests (Phase 2+)

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
- `docs/foundation/TESTING_STRATEGY_V3.4.md` - Comprehensive testing strategy with 8 test types
- `docs/testing/TEST_ISOLATION_PATTERNS_V1.1.md` - Detailed patterns for test isolation (Phase 1.9)
- `docs/foundation/MASTER_REQUIREMENTS_V2.20.md` - Master requirements document

**Related ADRs:**
- ADR-074: Property-Based Testing with Hypothesis
- ADR-076: Test Type Categories

**Related Patterns:**
- Pattern 10: Property-Based Testing with Hypothesis
- TEST_ISOLATION_PATTERNS Patterns 1-5: Test isolation patterns for database tests

---

**Sign-off:** Claude Code - 2025-11-30

**Note:** REQ-TEST-020 through REQ-TEST-024 added in V2.1 based on Phase 1.9 lessons learned.
Implementation is tracked in Issue #165 (Phase 1.9 Test Infrastructure Plan - BLOCKING).

---

**END OF TEST_REQUIREMENTS_COMPREHENSIVE_V2.1.md**
