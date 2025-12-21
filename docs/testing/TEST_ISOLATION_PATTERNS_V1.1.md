# Test Isolation Patterns

**Version:** 1.1
**Date:** 2025-12-06
**Status:** Active
**Created:** Phase 1.9 Test Infrastructure (Issue #165)
**Purpose:** Document patterns for proper test isolation to prevent database state contamination
**Changes in V1.1:**
- **Added Pattern 6: CI-Safe ThreadPoolExecutor Isolation** (Issue #168)
- Documents threading tests that hang in CI due to resource constraints
- Solution: `pytest.mark.skipif(_is_ci)` for ThreadPoolExecutor/threading.Barrier tests
- Helper classes: CISafeBarrier, with_timeout decorator
- Reference: Pattern 28 (DEVELOPMENT_PATTERNS_V1.20.md)

---

## Executive Summary

This document captures **critical patterns** for test isolation discovered during Phase 1.9 test infrastructure work. These patterns address the root causes of test failures related to database state contamination, race conditions in parallel execution, and foreign key dependency issues.

**Key Principle:** Tests must be **completely independent** - they should pass regardless of:
- Execution order
- Parallel execution (pytest-xdist)
- Previous test failures
- Database state from other test sessions

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Root Causes Identified](#root-causes-identified)
3. [Pattern 1: Transaction-Based Isolation](#pattern-1-transaction-based-isolation)
4. [Pattern 2: Foreign Key Dependency Chain](#pattern-2-foreign-key-dependency-chain)
5. [Pattern 3: Cleanup Fixture Ordering](#pattern-3-cleanup-fixture-ordering)
6. [Pattern 4: Parallel Execution Safety](#pattern-4-parallel-execution-safety)
7. [Pattern 5: SCD Type 2 Test Isolation](#pattern-5-scd-type-2-test-isolation)
8. [Pattern 6: CI-Safe ThreadPoolExecutor Isolation](#pattern-6-ci-safe-threadpoolexecutor-isolation)
9. [Implementation Checklist](#implementation-checklist)
10. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
11. [References](#references)

---

## Problem Statement

### Phase 1.9 Test Failures (Before Fix)

Running `python -m pytest tests/ -v` with pytest-xdist parallelization revealed:
- **12 failed tests** (down from 25+ after initial fixes)
- **18 skipped tests**
- **5 xfailed tests**
- **2 errors**

**Root symptoms:**
```
FAILED tests/integration/database/test_crud_operations_integration.py::test_upsert_game_state_creates_history
FAILED tests/property/test_crud_operations_properties.py::test_scd_type2_at_most_one_current_row
FAILED tests/stress/test_crud_operations_stress.py::test_rapid_game_state_updates
ERROR tests/integration/database/test_crud_operations_integration.py::TestGameStateIntegration::test_get_game_state_history_orders_by_timestamp
```

**Error types observed:**
```python
# UniqueViolation - Database state contamination
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint

# ForeignKeyViolation - Missing parent records
psycopg2.errors.ForeignKeyViolation: insert or update on table "game_states" violates foreign key constraint

# Deadlock - Race condition between parallel workers
psycopg2.errors.DeadlockDetected: deadlock detected
```

---

## Root Causes Identified

### Root Cause 1: Incomplete Transaction Rollback

**Issue:** The `db_cursor` fixture uses `commit=False` but some tests call `cursor.connection.commit()` explicitly, persisting test data.

**Evidence:** Test data from one test visible in subsequent tests.

**Solution:** Transaction-based isolation with explicit savepoints.

### Root Cause 2: Foreign Key Dependency Chain Gaps

**Issue:** Tests creating `game_states` records need parent records in this order:
```
platforms -> series -> events -> game_states
```

But fixtures don't always create the full chain, or tests assume records exist from other tests.

**Evidence:** ForeignKeyViolation errors when running tests in isolation.

**Solution:** Complete FK chain in fixtures with ON CONFLICT handling.

### Root Cause 3: Parallel Worker Interference

**Issue:** pytest-xdist spawns multiple workers (32 by default). All workers share the same database.

**Evidence:** Deadlock errors, UniqueViolation on concurrent inserts.

**Solution:** Worker-specific test data prefixes (e.g., `TEST-WORKER-0-*`).

### Root Cause 4: Cleanup Order Violations

**Issue:** Cleanup deletes parent records before child records, violating FK constraints.

**Evidence:** Constraint violations during test teardown.

**Solution:** Delete in reverse FK order (children first, parents last).

### Root Cause 5: SCD Type 2 State Leakage

**Issue:** Tests updating `row_current_ind` flags affect other tests expecting specific current records.

**Evidence:** SCD Type 2 property tests failing with "more than one current row".

**Solution:** Isolated test data with unique identifiers per test.

---

## Pattern 1: Transaction-Based Isolation

### Current Problem

```python
# Current fixture - does NOT guarantee rollback
@pytest.fixture
def db_cursor(db_pool):
    with get_cursor(commit=False) as cur:
        yield cur
        # Rollback happens in finally block... but does it always work?
```

### Recommended Pattern

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

### Usage

```python
def test_game_state_update(isolated_transaction):
    """Test updates game state using isolated transaction."""
    cursor = isolated_transaction

    # All changes within this test are automatically rolled back
    cursor.execute("INSERT INTO game_states ...")
    cursor.execute("UPDATE game_states ...")

    # No explicit cleanup needed - savepoint rollback handles it
```

### Benefits

- **Guaranteed isolation:** No test data persists regardless of commits
- **No cleanup code:** Savepoint rollback handles everything
- **Fast:** No DELETE statements needed
- **Safe:** Cannot accidentally pollute database

---

## Pattern 2: Foreign Key Dependency Chain

### Current Problem

```python
# Missing parent records cause FK violations
@pytest.fixture
def clean_test_data(db_cursor):
    # Creates platform and event, but what about series?
    # What about the specific event_id needed for game_states?
```

### Recommended Pattern

```python
@pytest.fixture
def complete_test_hierarchy(db_cursor):
    """
    Create complete FK dependency chain for testing.

    FK Chain (must create in this order):
        platforms -> series -> events -> markets -> game_states
                                      -> positions -> trades

    Uses worker-specific prefixes for parallel safety.
    """
    # Get worker ID for parallel safety (default: 'master' for single worker)
    worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'master')
    prefix = f"TEST-{worker_id.upper()}"

    # 1. Platform (root of FK chain)
    db_cursor.execute("""
        INSERT INTO platforms (platform_id, platform_type, display_name, status)
        VALUES (%s, 'trading', 'Test Platform', 'active')
        ON CONFLICT (platform_id) DO NOTHING
    """, (f"{prefix}-PLATFORM",))

    # 2. Series (references platform)
    db_cursor.execute("""
        INSERT INTO series (series_id, platform_id, external_id, category, title)
        VALUES (%s, %s, %s, 'sports', 'Test Series')
        ON CONFLICT (series_id) DO NOTHING
    """, (f"{prefix}-SERIES", f"{prefix}-PLATFORM", f"{prefix}-EXT-SERIES"))

    # 3. Event (references platform and series)
    db_cursor.execute("""
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
        VALUES (%s, %s, %s, %s, 'sports', 'Test Event', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
    """, (f"{prefix}-EVENT", f"{prefix}-PLATFORM", f"{prefix}-SERIES", f"{prefix}-EXT-EVENT"))

    db_cursor.connection.commit()

    yield {
        'platform_id': f"{prefix}-PLATFORM",
        'series_id': f"{prefix}-SERIES",
        'event_id': f"{prefix}-EVENT",
        'prefix': prefix,
    }

    # Cleanup in reverse FK order (see Pattern 3)
```

### Usage

```python
def test_game_state_with_full_hierarchy(complete_test_hierarchy, db_cursor):
    """Test using complete FK chain."""
    event_id = complete_test_hierarchy['event_id']
    prefix = complete_test_hierarchy['prefix']

    # Safe to create game_state - parent event exists
    db_cursor.execute("""
        INSERT INTO game_states (event_id, sport, home_team, away_team, status)
        VALUES (%s, 'nfl', 'KC', 'BUF', 'scheduled')
    """, (event_id,))
```

---

## Pattern 3: Cleanup Fixture Ordering

### Current Problem

```python
# WRONG: Deletes parents before children
db_cursor.execute("DELETE FROM events WHERE ...")  # FK violation!
db_cursor.execute("DELETE FROM game_states WHERE ...")
```

### Recommended Pattern

```python
def cleanup_test_data(db_cursor, prefix: str):
    """
    Clean up test data in correct FK order.

    Delete Order (children first, parents last):
        1. trades (references positions, markets)
        2. positions (references markets, strategies, models)
        3. settlements (references markets)
        4. edges (references markets, probability_matrices)
        5. game_states (references events)
        6. markets (references events)
        7. events (references series)
        8. series (references platforms)
        9. strategies (no FK children in our tests)
        10. probability_models (no FK children in our tests)
        11. platforms (root - delete last)

    Educational Note:
        PostgreSQL enforces FK constraints on DELETE.
        Deleting a parent with existing children causes:
        - FK violation error if ON DELETE RESTRICT (default)
        - Cascade delete if ON DELETE CASCADE (dangerous in tests!)
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

### Visual: FK Dependency Tree

```
platforms (ROOT)
    |
    +-- series
    |       |
    |       +-- events
    |               |
    |               +-- markets
    |               |       |
    |               |       +-- positions
    |               |       |       |
    |               |       |       +-- trades
    |               |       |
    |               |       +-- edges
    |               |       |
    |               |       +-- settlements
    |               |
    |               +-- game_states
    |
    +-- account_balance

DELETE ORDER: Bottom-up (trades -> positions -> ... -> platforms)
CREATE ORDER: Top-down (platforms -> ... -> trades)
```

---

## Pattern 4: Parallel Execution Safety

### Current Problem

```python
# All workers use same test data IDs - collisions!
market_id = "TEST-NFL-KC-BUF"  # Worker 0 and Worker 1 both use this
```

### Recommended Pattern

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
        Without xdist, variable is not set (single process).
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

### Parallel Test Database Strategies

**Strategy A: Shared Database, Worker-Prefixed Data (Recommended)**
- Single database, each worker uses unique data prefix
- Pro: Simple setup, no extra databases
- Con: Must be disciplined about prefixes

**Strategy B: Worker-Specific Databases**
- Each worker gets own database (precog_test_gw0, precog_test_gw1)
- Pro: Complete isolation
- Con: Complex setup, more resources

**Strategy C: Transaction-Based Isolation (Preferred)**
- Each test runs in transaction, rolled back at end
- Pro: No cleanup needed, fastest
- Con: Cannot test commit behavior

### pytest-xdist Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
# Limit workers to prevent resource exhaustion
# -n auto: Use all CPUs
# -n 4: Use exactly 4 workers
addopts = ["-n", "auto"]

# Or disable parallel for database tests
# pytest tests/integration/ -n 0
```

---

## Pattern 5: SCD Type 2 Test Isolation

### Current Problem

```python
# Test A sets row_current_ind = FALSE for old row
# Test B expects only one current row
# Test B fails if Test A's data leaks
```

### Recommended Pattern

```python
@pytest.fixture
def isolated_scd_test(db_cursor, worker_prefix):
    """
    Create isolated SCD Type 2 test data.

    SCD Type 2 Invariant:
        For any (entity_id), exactly ONE row has row_current_ind = TRUE

    Tests modifying row_current_ind MUST:
        1. Use unique entity IDs (worker-prefixed)
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
    db_cursor.execute(
        "DELETE FROM markets WHERE market_id = %s",
        (market_id,)
    )
    db_cursor.connection.commit()


def test_scd_type2_update_creates_history(isolated_scd_test, db_cursor):
    """Test SCD Type 2 update with complete isolation."""
    market_id = isolated_scd_test['market_id']

    # Update (should create new version, mark old as historical)
    db_cursor.execute("""
        -- Mark current as historical
        UPDATE markets
        SET row_current_ind = FALSE, row_end_ts = NOW()
        WHERE market_id = %s AND row_current_ind = TRUE
    """, (market_id,))

    # Insert new current version
    db_cursor.execute("""
        INSERT INTO markets (
            market_id, platform_id, event_id, external_id, ticker, title,
            yes_price, no_price, market_type, status, row_current_ind
        ) VALUES (
            %s, 'test_platform', 'TEST-EVENT', %s, %s, 'SCD Test Market',
            0.6000, 0.4000, 'binary', 'open', TRUE
        )
    """, (market_id, f"{market_id}-ext-v2", market_id))

    # Verify SCD Type 2 invariant
    result = db_cursor.execute("""
        SELECT COUNT(*) as current_count
        FROM markets
        WHERE market_id = %s AND row_current_ind = TRUE
    """, (market_id,))
    row = result.fetchone()
    assert row['current_count'] == 1, "SCD Type 2 violation: more than one current row"
```

---

## Implementation Checklist

### Phase 1.9 Test Isolation Fixes

- [ ] **Update conftest.py fixtures:**
  - [ ] Add `isolated_transaction` fixture using savepoints
  - [ ] Add `complete_test_hierarchy` fixture for FK chain
  - [ ] Add `worker_prefix` fixture for parallel safety
  - [ ] Update `clean_test_data` with correct delete order

- [ ] **Fix game_state tests:**
  - [ ] Create proper event parent records
  - [ ] Use worker-specific event IDs
  - [ ] Add proper cleanup in fixture teardown

- [ ] **Fix SCD Type 2 tests:**
  - [ ] Use UUID-based market IDs for isolation
  - [ ] Clean up ALL versions (not just current)
  - [ ] Add isolation fixture for SCD tests

- [ ] **Fix stress tests:**
  - [ ] Use worker-prefixed IDs in concurrent tests
  - [ ] Add proper transaction boundaries
  - [ ] Handle deadlock with retry logic

- [ ] **Update pytest configuration:**
  - [ ] Limit parallel workers if needed
  - [ ] Add marker for tests requiring isolation
  - [ ] Configure database tests to run sequentially if needed

---

## Anti-Patterns to Avoid

### 1. Hardcoded Test IDs

```python
# WRONG: Hardcoded ID causes collision in parallel
market_id = "TEST-NFL-KC-BUF"

# CORRECT: Worker-prefixed ID
market_id = f"{worker_prefix}-NFL-KC-BUF"
```

### 2. Assuming Database State

```python
# WRONG: Assumes event exists
def test_create_game_state():
    create_game_state(event_id="TEST-EVENT")  # May not exist!

# CORRECT: Fixture ensures parents exist
def test_create_game_state(complete_test_hierarchy):
    event_id = complete_test_hierarchy['event_id']
    create_game_state(event_id=event_id)  # Guaranteed to exist
```

### 3. Shared Mutable State

```python
# WRONG: Module-level state shared between tests
TEST_COUNTER = 0

def test_a():
    global TEST_COUNTER
    TEST_COUNTER += 1  # Affects test_b!

# CORRECT: Test-local state via fixtures
@pytest.fixture
def counter():
    return {'value': 0}

def test_a(counter):
    counter['value'] += 1  # Isolated to this test
```

### 4. Commit Without Cleanup

```python
# WRONG: Commits without cleanup
def test_create_market(db_cursor):
    db_cursor.execute("INSERT INTO markets ...")
    db_cursor.connection.commit()  # Data persists!

# CORRECT: Use savepoint isolation
def test_create_market(isolated_transaction):
    isolated_transaction.execute("INSERT INTO markets ...")
    # Automatically rolled back via savepoint
```

### 5. Wrong Delete Order

```python
# WRONG: Delete parents before children
db_cursor.execute("DELETE FROM events WHERE ...")  # FK violation!
db_cursor.execute("DELETE FROM game_states WHERE ...")

# CORRECT: Delete children before parents
db_cursor.execute("DELETE FROM game_states WHERE ...")
db_cursor.execute("DELETE FROM events WHERE ...")
```

---

## Pattern 6: CI-Safe ThreadPoolExecutor Isolation

### Problem

Tests using `ThreadPoolExecutor`, `threading.Barrier()`, or sustained `time.perf_counter()` loops **hang indefinitely** in CI environments due to resource constraints:

```
# CI Log showing timeout:
FAILED tests/stress/test_connection_stress.py::test_concurrent - TIMEOUT after 600s
# Or just hangs for 15+ minutes with no output
```

**Root Causes:**
1. **ThreadPoolExecutor + as_completed():** Concurrent futures waiting on each other deadlock with unpredictable thread scheduling in CI
2. **Threading Barriers:** `threading.Barrier(20).wait()` requires all 20 threads to arrive - CI scheduling delays cause timeouts
3. **pytest-timeout Limitations:** `--timeout-method=thread` cannot interrupt blocking Python code in threads (SIGALRM only works on main thread)
4. **Resource Constraints:** CI runners have 2 vCPUs vs 8+ cores locally - threading behavior is fundamentally different

### Solution

Use `pytest.mark.skipif(_is_ci)` to skip threading-heavy tests in CI:

```python
import os
import pytest

# CI environment detection - standardized pattern
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

_CI_SKIP_REASON = (
    "Stress tests skip in CI - they can hang in resource-constrained environments. "
    "Run locally: pytest tests/stress/ -v -m stress"
)

# Module-level pytestmark for ALL tests in file
pytestmark = [
    pytest.mark.stress,
    pytest.mark.slow,
    pytest.mark.skipif(_is_ci, reason=_CI_SKIP_REASON),
]


class TestConnectionPoolStress:
    def test_concurrent_connections(self, stress_postgres_container):
        """Skipped in CI, runs locally with adequate resources."""
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(use_connection) for _ in range(50)]
            for future in as_completed(futures):
                pass  # Would hang in CI
```

### Helper Classes

**CISafeBarrier (tests/fixtures/stress_testcontainers.py):**

```python
class CISafeBarrier:
    """Thread barrier with timeout support for CI-safe synchronization."""

    def __init__(self, parties: int, timeout: float = 10.0):
        self._barrier = threading.Barrier(parties)
        self._timeout = timeout

    def wait(self, timeout: float | None = None) -> int:
        """Wait with timeout - raises TimeoutError instead of hanging."""
        effective_timeout = timeout if timeout is not None else self._timeout
        try:
            return self._barrier.wait(timeout=effective_timeout)
        except threading.BrokenBarrierError:
            raise TimeoutError(
                f"CISafeBarrier timed out after {effective_timeout}s"
            ) from None
```

**with_timeout Decorator:**

```python
def with_timeout(timeout_seconds: float = 30.0):
    """Decorator for stress tests that need thread-safe timeouts."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_seconds)
                except FuturesTimeoutError:
                    raise TimeoutError(
                        f"Test exceeded {timeout_seconds}s timeout"
                    ) from None
        return wrapper
    return decorator
```

### When to Apply

| Test Type | CI Behavior | Pattern |
|-----------|-------------|---------|
| **ThreadPoolExecutor tests** | Skip in CI | `skipif(_is_ci)` |
| **threading.Barrier tests** | Skip in CI | `skipif(_is_ci)` |
| **time.perf_counter loops** | Skip in CI | `skipif(_is_ci)` |
| **Connection pool stress** | Skip in CI | `skipif(_is_ci)` + testcontainers |
| **Unit tests** | Run normally | No skip |
| **Integration tests** | Run normally | No skip |
| **Chaos tests (mock injection)** | Run normally | No skip |

### Reference

- **Pattern 28:** DEVELOPMENT_PATTERNS_V1.20.md (comprehensive threading CI patterns)
- **Issue #168:** Testcontainers for database stress tests
- **ADR-057:** Testcontainers for Database Test Isolation
- **tests/fixtures/stress_testcontainers.py:** CISafeBarrier, with_timeout implementation

---

## References

**Related Documents:**
- `docs/foundation/TESTING_STRATEGY_V3.8.md` - Test type requirements
- `docs/foundation/TEST_REQUIREMENTS_COMPREHENSIVE_V2.1.md` - REQ-TEST-012 through REQ-TEST-019
- `docs/database/DATABASE_SCHEMA_SUMMARY_V1.7.md` - FK constraint definitions
- `tests/conftest.py` - Current fixture implementations

**Related Issues:**
- Issue #165: Phase 1.9 Test Infrastructure Plan (BLOCKING)
- Issue #168: Testcontainers for Database Stress Tests (Pattern 6)
- Issue #155: Test Type Coverage Gaps (57h effort)

**Related ADRs:**
- ADR-076: Test Type Categories
- ADR-xxx: Test Isolation Patterns (to be created)

**PostgreSQL Documentation:**
- [SAVEPOINT](https://www.postgresql.org/docs/15/sql-savepoint.html)
- [Transaction Isolation](https://www.postgresql.org/docs/15/transaction-iso.html)
- [Foreign Key Constraints](https://www.postgresql.org/docs/15/ddl-constraints.html#DDL-CONSTRAINTS-FK)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-30 | Initial document capturing Phase 1.9 lessons learned |

---

**END OF TEST_ISOLATION_PATTERNS_V1.0.md**
