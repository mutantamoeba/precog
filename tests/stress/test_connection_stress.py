"""
Stress Tests for Database Connection Pooling.

These tests validate the database connection layer under high-load conditions:
- Connection pool exhaustion
- Rapid connect/disconnect cycles
- Concurrent query execution
- Connection leak detection

Educational Note:
    Database connection stress tests are critical because:
    - Connection leaks accumulate over time (hours/days)
    - Pool exhaustion causes cascading failures
    - Concurrent access reveals race conditions
    - Production load patterns differ from unit tests

Prerequisites:
    - PostgreSQL database available
    - DATABASE_URL or individual DB env vars configured

Run with:
    pytest tests/stress/test_connection_stress.py -v -m stress

References:
    - Issue #126: Stress tests for infrastructure
    - REQ-TEST-012: Test types taxonomy (Stress tests)
    - src/precog/database/connection.py

Phase: 4 (Stress Testing Infrastructure)
GitHub Issue: #126
"""

import gc
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from precog.database.connection import test_connection

# Skip if database not available
# Note: database marker is registered in pyproject.toml
pytestmark = [pytest.mark.stress, pytest.mark.slow, pytest.mark.database]


@pytest.fixture(scope="module", autouse=True)
def skip_if_no_database():
    """Skip all tests in this module if database is not available."""
    if not test_connection():
        pytest.skip("Database not available")


class TestConnectionPoolExhaustion:
    """Stress tests for connection pool behavior under exhaustion."""

    def test_pool_handles_many_concurrent_connections(self):
        """Test pool handles 50 concurrent connection requests.

        Educational Note:
            Connection pools have limited capacity. This test verifies
            the pool can handle high concurrency without failure.
        """
        from precog.database.connection import get_cursor

        num_connections = 50
        results = {"success": 0, "failure": 0}
        lock = threading.Lock()

        def use_connection():
            try:
                with get_cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    with lock:
                        if result:
                            results["success"] += 1
                        else:
                            results["failure"] += 1
            except Exception:
                with lock:
                    results["failure"] += 1

        with ThreadPoolExecutor(max_workers=num_connections) as executor:
            futures = [executor.submit(use_connection) for _ in range(num_connections)]
            for future in as_completed(futures):
                pass

        # Most connections should succeed
        assert results["success"] >= num_connections * 0.9, (
            f"Too many failures: {results['failure']}/{num_connections}"
        )

    def test_pool_queues_when_exhausted(self):
        """Test connections queue when pool is exhausted.

        Educational Note:
            When all pool connections are in use, new requests should
            queue and wait rather than failing immediately.
        """
        from precog.database.connection import get_cursor

        # Hold connections to simulate exhaustion
        held_cursors = []
        results = {"queued_success": 0}

        # Hold 5 connections
        for _ in range(5):
            cursor_context = get_cursor()
            cursor = cursor_context.__enter__()
            held_cursors.append((cursor_context, cursor))

        # Try to get another connection (should queue or fail gracefully)
        start_time = time.time()
        try:
            with get_cursor() as cursor:
                cursor.execute("SELECT 1")
                results["queued_success"] += 1
        except Exception:
            pass  # Expected if pool is truly exhausted
        wait_time = time.time() - start_time

        # Release held connections
        for ctx, _ in held_cursors:
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass

        # Either succeeded or waited (indicates pool behavior)
        assert results["queued_success"] == 1 or wait_time > 0.1


class TestConnectionRapidCycles:
    """Stress tests for rapid connection/disconnection cycles."""

    def test_rapid_connect_disconnect_cycles(self):
        """Test 1000 rapid connection cycles.

        Educational Note:
            Rapid cycling tests for:
            - Connection cleanup correctness
            - Resource leak on disconnect
            - Pool reclamation speed
        """
        from precog.database.connection import get_cursor

        num_cycles = 1000
        success_count = 0

        for _ in range(num_cycles):
            try:
                with get_cursor() as cursor:
                    cursor.execute("SELECT 1")
                    success_count += 1
            except Exception:
                pass

        # All cycles should succeed
        assert success_count == num_cycles, f"Only {success_count}/{num_cycles} cycles succeeded"

    def test_interleaved_connect_disconnect(self):
        """Test interleaved connect/disconnect patterns.

        Educational Note:
            Real applications often have overlapping connections.
            This pattern tests pool management under overlap.
        """
        from precog.database.connection import get_cursor

        # Start some connections, end some, start more
        active = []

        for i in range(20):
            # Start new connection
            ctx = get_cursor()
            cursor = ctx.__enter__()
            active.append((ctx, cursor))

            # Close every 3rd connection
            if i % 3 == 0 and active:
                old_ctx, _ = active.pop(0)
                old_ctx.__exit__(None, None, None)

        # Close remaining
        for ctx, _ in active:
            ctx.__exit__(None, None, None)

        # Verify pool is healthy after
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result is not None


class TestConcurrentQueryExecution:
    """Stress tests for concurrent query execution."""

    def test_concurrent_read_queries(self):
        """Test 50 concurrent read queries.

        Educational Note:
            Read queries should never interfere with each other.
            This tests for query isolation and result correctness.
        """
        from precog.database.connection import fetch_one

        num_queries = 50
        results = []

        def execute_query(query_id):
            result = fetch_one(f"SELECT {query_id} as value")
            return result["value"] if result else None

        with ThreadPoolExecutor(max_workers=num_queries) as executor:
            futures = {executor.submit(execute_query, i): i for i in range(num_queries)}
            for future in as_completed(futures):
                query_id = futures[future]
                result = future.result()
                results.append((query_id, result))

        # All queries should return correct values
        for query_id, result in results:
            assert result == query_id, f"Query {query_id} returned {result}"

    def test_concurrent_mixed_operations(self):
        """Test concurrent reads and writes.

        Educational Note:
            Mixed read/write workloads are common in production.
            This tests transaction isolation.
        """
        from precog.database.connection import execute_query, fetch_all, get_cursor

        # Create test table
        execute_query("""
            CREATE TABLE IF NOT EXISTS _stress_test_table (
                id SERIAL PRIMARY KEY,
                value INTEGER
            )
        """)

        try:
            results = {"reads": 0, "writes": 0}
            lock = threading.Lock()

            def read_operation():
                try:
                    fetch_all("SELECT * FROM _stress_test_table LIMIT 10")
                    with lock:
                        results["reads"] += 1
                except Exception:
                    pass

            def write_operation():
                try:
                    with get_cursor(commit=True) as cursor:
                        cursor.execute(
                            "INSERT INTO _stress_test_table (value) VALUES (%s)",
                            (1,),
                        )
                    with lock:
                        results["writes"] += 1
                except Exception:
                    pass

            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = []
                for i in range(30):
                    if i % 2 == 0:
                        futures.append(executor.submit(read_operation))
                    else:
                        futures.append(executor.submit(write_operation))

                for future in as_completed(futures):
                    pass

            # Both reads and writes should succeed
            assert results["reads"] > 10
            assert results["writes"] > 10

        finally:
            # Cleanup
            execute_query("DROP TABLE IF EXISTS _stress_test_table")


class TestConnectionLeakDetection:
    """Stress tests for connection leak detection."""

    def test_no_connection_leak_on_exception(self):
        """Test connections are returned to pool even on exception.

        Educational Note:
            Connection leaks often occur when exceptions happen
            inside a connection context. The context manager must
            ensure cleanup in all cases.
        """
        from precog.database.connection import get_cursor

        num_iterations = 100

        for _ in range(num_iterations):
            try:
                with get_cursor() as cursor:
                    cursor.execute("SELECT 1/0")  # Division by zero
            except Exception:
                pass  # Expected error

        # Pool should still work after many exceptions
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result is not None

    def test_connection_count_stable_over_time(self):
        """Test connection count doesn't grow over time.

        Educational Note:
            A stable connection count indicates no leaks.
            Growth over time indicates connections aren't being returned.
        """
        from precog.database.connection import get_cursor

        # Do many operations
        for _ in range(500):
            with get_cursor() as cursor:
                cursor.execute("SELECT 1")

        # Force garbage collection
        gc.collect()

        # Pool should be in healthy state
        # (If there were leaks, pool would be exhausted by now)
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result is not None


class TestConnectionTimeout:
    """Stress tests for connection timeout scenarios."""

    def test_handles_slow_queries_gracefully(self):
        """Test system handles slow queries without deadlock.

        Educational Note:
            Slow queries shouldn't block other operations.
            This tests for proper timeout handling.
        """
        from precog.database.connection import fetch_one, get_cursor

        def slow_query():
            # pg_sleep for 0.5 seconds
            with get_cursor() as cursor:
                cursor.execute("SELECT pg_sleep(0.5)")

        def fast_query():
            return fetch_one("SELECT 1 as value")

        with ThreadPoolExecutor(max_workers=10) as executor:
            # Start slow query
            slow_future = executor.submit(slow_query)

            # Fast queries should still work
            fast_futures = [executor.submit(fast_query) for _ in range(5)]

            # All fast queries should complete
            for f in fast_futures:
                result = f.result(timeout=2)
                assert result is not None

            # Slow query should also complete
            slow_future.result(timeout=5)
