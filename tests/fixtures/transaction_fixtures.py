"""
Transaction-Based Test Isolation Fixtures (Issue #171 - Layer 1).

Provides PostgreSQL transaction rollback for test isolation with ~0ms overhead.
Each test runs in a transaction that gets rolled back automatically, ensuring
clean database state without expensive DELETE/INSERT cleanup cycles.

Why Transaction Rollback?
    Traditional test cleanup uses DELETE statements before/after each test:
    - DELETE FROM trades WHERE market_id LIKE 'TEST-%'  (~5-50ms per table)
    - With 10+ tables, cleanup takes 50-500ms per test
    - 500 tests x 100ms = 50 seconds wasted on cleanup alone

    Transaction rollback provides equivalent isolation at ~0ms overhead:
    - BEGIN at test start
    - Test executes normally (INSERT, UPDATE, etc.)
    - ROLLBACK at test end (discards ALL changes instantly)
    - No disk I/O for cleanup - just memory state reset

Performance Comparison:
    | Approach           | Overhead/Test | 500 Tests | Notes                    |
    |-------------------|---------------|-----------|--------------------------|
    | DELETE cleanup    | 50-500ms      | 25-250s   | Current approach         |
    | Transaction rollback | ~0ms       | ~0s       | This approach (Layer 1)  |
    | Testcontainers    | 10-15s        | N/A       | Reserved for stress tests|

Isolation Guarantees:
    - FULL isolation: Each test sees clean database state
    - ACID compliance: PostgreSQL transactions are fully ACID
    - Concurrent safe: Each test gets its own connection/transaction
    - No state leakage: Changes discarded even if test crashes

When NOT to Use Transaction Rollback:
    1. Tests that verify COMMIT behavior (e.g., testing connection.commit())
    2. Tests that span multiple connections (multi-process/multi-thread)
    3. Tests that intentionally test rollback behavior
    4. Stress tests that exhaust connection pools (use testcontainers instead)

Usage:
    @pytest.fixture
    def my_test_data(db_transaction):
        '''Test data created inside transaction - auto-rolled-back.'''
        cursor = db_transaction
        cursor.execute("INSERT INTO markets ...")
        yield cursor
        # No cleanup needed - transaction rolled back automatically

    def test_something(db_transaction):
        '''Test using transaction isolation.'''
        cursor = db_transaction
        cursor.execute("INSERT INTO trades ...")
        # Changes automatically discarded after test

References:
    - Issue #171: Implement hybrid test isolation strategy
    - ADR-057: Testcontainers for Database Test Isolation (Layer 3)
    - Pattern 28: CI-Safe Stress Testing (DEVELOPMENT_PATTERNS_V1.17.md)
    - PostgreSQL SAVEPOINT documentation for nested transaction support

Phase: 2 (Test Infrastructure Improvements)
GitHub Issue: #171
"""

from collections.abc import Generator
from typing import Any

import psycopg2
import pytest
from psycopg2 import extras

from precog.database.connection import get_connection, release_connection


@pytest.fixture
def db_transaction() -> Generator[psycopg2.extensions.cursor, None, None]:
    """
    Provide database cursor with automatic transaction rollback.

    This fixture wraps each test in a transaction that is ALWAYS rolled back,
    regardless of test success or failure. This provides zero-overhead test
    isolation without expensive DELETE cleanup operations.

    Scope: function - new transaction for each test

    Yields:
        RealDictCursor with automatic rollback on teardown

    Example:
        def test_create_market(db_transaction):
            '''Test creates data that is automatically cleaned up.'''
            cursor = db_transaction
            cursor.execute(
                "INSERT INTO markets (market_id, ...) VALUES (%s, ...)",
                ("TEST-MKT-001", ...)
            )
            # Changes automatically rolled back after test

    Educational Note:
        The key insight is that PostgreSQL transactions are cheap to start
        and ROLLBACK is almost instant (just discards uncommitted changes).
        This makes transaction-based isolation 100-1000x faster than
        DELETE-based cleanup for most test scenarios.

        Compare:
        - DELETE FROM markets WHERE market_id LIKE 'TEST-%'  # Scans table, logs changes
        - ROLLBACK  # Instant, no I/O

    Warning:
        Tests using this fixture should NOT call connection.commit()
        as this would persist changes. Use db_cursor_commit fixture instead
        for tests that need to verify commit behavior.
    """
    conn = get_connection()

    # Start explicit transaction
    conn.autocommit = False

    # Create cursor with dict factory for easier assertions
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

    try:
        yield cursor
    finally:
        # ALWAYS rollback - this is the key to transaction isolation
        try:
            conn.rollback()
        except Exception:
            pass  # Connection may already be closed
        finally:
            cursor.close()
            release_connection(conn)


@pytest.fixture
def db_transaction_with_setup(
    db_transaction: psycopg2.extensions.cursor,
) -> Generator[psycopg2.extensions.cursor, None, None]:
    """
    Transaction fixture with standard test data pre-loaded.

    Provides the same transaction rollback isolation as db_transaction,
    but also creates standard test fixtures (platform, series, event, strategy, model)
    that are commonly needed by tests.

    This replaces the heavyweight clean_test_data fixture which uses DELETE statements.

    Scope: function - new transaction with fresh test data for each test

    Yields:
        RealDictCursor with test data already inserted

    Example:
        def test_create_position(db_transaction_with_setup):
            '''Test has access to test platform, event, strategy, model.'''
            cursor = db_transaction_with_setup
            # test_platform, TEST-SERIES-NFL, TEST-EVT-NFL-KC-BUF already exist
            cursor.execute(
                "INSERT INTO positions (market_id, strategy_id, ...) VALUES (%s, %s, ...)",
                ("MKT-TEST-001", 99901, ...)
            )
            # All changes (including setup data) rolled back after test

    Educational Note:
        By creating test data INSIDE the transaction, we eliminate the need
        for ON CONFLICT DO NOTHING clauses and complex cleanup logic.
        Each test gets identical, fresh test data automatically.
    """
    cursor = db_transaction

    # Create test platform (ON CONFLICT to handle pre-existing data)
    cursor.execute("""
        INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
        VALUES ('test_platform', 'trading', 'Test Platform', 'https://test.example.com', 'active')
        ON CONFLICT (platform_id) DO NOTHING
    """)

    # Create test series
    cursor.execute("""
        INSERT INTO series (series_id, platform_id, external_id, title, category)
        VALUES ('TEST-SERIES-NFL', 'test_platform', 'TEST-EXT-SERIES', 'Test NFL Series', 'sports')
        ON CONFLICT (series_id) DO NOTHING
    """)

    # Create test event
    cursor.execute("""
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
        VALUES ('TEST-EVT-NFL-KC-BUF', 'test_platform', 'TEST-SERIES-NFL', 'TEST-EXT-EVT', 'sports', 'Test Event: KC vs BUF', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
    """)

    # Create additional test event for compatibility
    cursor.execute("""
        INSERT INTO events (event_id, platform_id, series_id, external_id, category, title, status)
        VALUES ('TEST-EVT', 'test_platform', 'TEST-SERIES-NFL', 'TEST-EVT-2', 'sports', 'Test Event 2', 'scheduled')
        ON CONFLICT (event_id) DO NOTHING
    """)

    # Create test strategy (high ID to avoid SERIAL collision)
    cursor.execute("""
        INSERT INTO strategies (strategy_id, strategy_name, strategy_version, strategy_type, config, status)
        VALUES (99901, 'test_strategy', 'v1.0', 'value', '{"test": true}', 'active')
        ON CONFLICT (strategy_id) DO NOTHING
    """)

    # Create test probability model (high ID to avoid SERIAL collision)
    cursor.execute("""
        INSERT INTO probability_models (model_id, model_name, model_version, model_class, config, status)
        VALUES (99901, 'test_model', 'v1.0', 'elo', '{"test": true}', 'active')
        ON CONFLICT (model_id) DO NOTHING
    """)

    yield cursor  # noqa: PT022 - yield required for Generator type
    # Rollback handled by parent fixture (db_transaction)


@pytest.fixture
def db_savepoint(
    db_transaction: psycopg2.extensions.cursor,
) -> Generator[tuple[psycopg2.extensions.cursor, Any], None, None]:
    """
    Provide nested savepoint within transaction for sub-test isolation.

    Useful for tests that need to verify rollback behavior or need
    multiple isolated "sub-tests" within a single test function.

    Scope: function

    Yields:
        Tuple of (cursor, savepoint_manager) where savepoint_manager provides
        create_savepoint() and rollback_to_savepoint() methods

    Example:
        def test_rollback_behavior(db_savepoint):
            '''Test that verifies application rollback logic.'''
            cursor, savepoints = db_savepoint

            # Create savepoint before operation
            sp1 = savepoints.create("before_insert")

            cursor.execute("INSERT INTO markets ...")

            # Rollback to savepoint (simulating error recovery)
            savepoints.rollback_to(sp1)

            # Verify insert was rolled back
            cursor.execute("SELECT COUNT(*) FROM markets WHERE ...")
            assert cursor.fetchone()['count'] == 0

    Educational Note:
        PostgreSQL SAVEPOINTs enable nested transactions. This is useful for:
        1. Testing rollback behavior in application code
        2. Isolating sub-operations within a larger test
        3. Implementing "try/catch" patterns in SQL

        The outer transaction (from db_transaction) still rolls back everything
        at the end, so even savepoint operations are cleaned up.
    """

    class SavepointManager:
        """Helper class for managing PostgreSQL savepoints."""

        def __init__(self, cursor: psycopg2.extensions.cursor):
            self._cursor = cursor
            self._savepoint_counter = 0

        def create(self, name: str | None = None) -> str:
            """Create a savepoint and return its name."""
            if name is None:
                self._savepoint_counter += 1
                name = f"sp_{self._savepoint_counter}"
            self._cursor.execute(f"SAVEPOINT {name}")
            return name

        def rollback_to(self, name: str) -> None:
            """Rollback to a named savepoint."""
            self._cursor.execute(f"ROLLBACK TO SAVEPOINT {name}")

        def release(self, name: str) -> None:
            """Release a savepoint (makes it permanent within transaction)."""
            self._cursor.execute(f"RELEASE SAVEPOINT {name}")

    cursor = db_transaction
    manager = SavepointManager(cursor)

    yield cursor, manager  # noqa: PT022 - yield required for Generator type
    # Rollback handled by parent fixture


# Re-export for easy importing
__all__ = [
    "db_savepoint",
    "db_transaction",
    "db_transaction_with_setup",
]
