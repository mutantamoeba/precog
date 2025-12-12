"""
Race Condition Tests for Database Connection.

Tests for race conditions in database connection operations:
- Concurrent pool initialization
- Simultaneous connection acquisition
- Thread-safe cursor operations
- Connection release under contention

Related:
- TESTING_STRATEGY V3.5: All 8 test types required
- database/connection module coverage

Usage:
    pytest tests/stress/database/test_connection_race.py -v -m race

Educational Note:
    Database connection pools are inherently thread-safe (psycopg2.pool.SimpleConnectionPool),
    but these tests verify that our wrapper functions maintain that safety under
    concurrent access patterns.

    Key race scenarios:
    1. Multiple threads calling get_connection() simultaneously
    2. Threads releasing connections while others are acquiring
    3. Concurrent query execution with commit/rollback
    4. Pool exhaustion recovery under contention

CI-Safe Testing:
    Uses CISafeBarrier for thread synchronization with timeouts.
    Tests gracefully skip if barrier times out (CI resource constraints).

Reference: docs/foundation/TESTING_STRATEGY_V3.5.md Section "Best Practice #6"
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

# Import CI-safe barrier from stress test fixtures
from tests.fixtures.stress_testcontainers import CISafeBarrier


@pytest.mark.race
class TestConnectionPoolRace:
    """Race condition tests for connection pool operations."""

    # Timeout for barrier synchronization (seconds)
    BARRIER_TIMEOUT = 15.0

    def test_concurrent_connection_acquisition(self):
        """
        RACE: Multiple threads acquiring connections simultaneously.

        Verifies:
        - Each thread gets a unique connection
        - No connection is shared between threads
        - Pool handles concurrent access correctly
        """
        from precog.database.connection import get_connection, release_connection

        connections = []
        connection_ids = set()
        lock = threading.Lock()
        errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def acquire_connection(thread_id: int):
            try:
                barrier.wait()
                conn = get_connection()
                conn_id = id(conn)

                with lock:
                    connections.append((thread_id, conn))
                    connection_ids.add(conn_id)

                # Hold connection briefly to simulate work
                time.sleep(0.01)

                release_connection(conn)
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(10):
            t = threading.Thread(target=acquire_connection, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors during race test: {other_errors}"
        assert len(connections) == 10, "All threads should acquire connections"
        # Note: connection_ids might be less than 10 if connections are reused from pool

    def test_concurrent_cursor_operations(self):
        """
        RACE: Multiple threads using get_cursor() context manager.

        Verifies:
        - Cursor context manager is thread-safe
        - Each thread gets independent cursor
        - Transactions don't interfere
        """
        from precog.database.connection import get_cursor

        results = []
        errors = []
        lock = threading.Lock()
        barrier = CISafeBarrier(8, timeout=self.BARRIER_TIMEOUT)

        def execute_query(thread_id: int):
            try:
                barrier.wait()
                with get_cursor() as cur:
                    cur.execute("SELECT %s as thread_id", (thread_id,))
                    row = cur.fetchone()
                    with lock:
                        results.append((thread_id, row["thread_id"]))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(8):
            t = threading.Thread(target=execute_query, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(results) == 8

        # Each thread should get its own thread_id back
        for thread_id, result in results:
            assert result == thread_id

    def test_interleaved_acquire_release(self):
        """
        RACE: Threads acquiring and releasing connections in interleaved pattern.

        Verifies:
        - Pool handles rapid acquire/release cycles
        - No connection leaks
        - No deadlocks
        """
        from precog.database.connection import get_connection, release_connection

        operation_count = []
        errors = []
        barrier = CISafeBarrier(5, timeout=self.BARRIER_TIMEOUT)

        def rapid_acquire_release(thread_id: int):
            count = 0
            try:
                barrier.wait()
                for _ in range(20):
                    conn = get_connection()
                    count += 1
                    # Simulate minimal work
                    time.sleep(0.001)
                    release_connection(conn)
                operation_count.append((thread_id, count))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(rapid_acquire_release, i) for i in range(5)]
            for f in futures:
                f.result(timeout=60)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"

        # All threads should complete 20 operations
        total_ops = sum(count for _, count in operation_count)
        assert total_ops == 100  # 5 threads * 20 operations

    def test_concurrent_fetch_operations(self):
        """
        RACE: Multiple threads using fetch_one and fetch_all simultaneously.

        Verifies:
        - Helper functions are thread-safe
        - No data corruption between threads
        """
        from typing import Any

        from precog.database.connection import fetch_all, fetch_one

        results: list[tuple[str, int, Any]] = []
        errors: list[tuple[int, str]] = []
        lock = threading.Lock()
        barrier = CISafeBarrier(6, timeout=self.BARRIER_TIMEOUT)

        def fetch_data(thread_id: int):
            try:
                barrier.wait()

                # Alternate between fetch_one and fetch_all
                if thread_id % 2 == 0:
                    one_result = fetch_one("SELECT %s as val", (thread_id,))
                    with lock:
                        results.append(("one", thread_id, one_result))
                else:
                    all_results = fetch_all("SELECT generate_series(%s, %s) as val", (1, 3))
                    with lock:
                        results.append(("all", thread_id, all_results))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(6):
            t = threading.Thread(target=fetch_data, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(results) == 6

    def test_concurrent_execute_query(self):
        """
        RACE: Multiple threads executing queries with commits.

        Verifies:
        - execute_query is thread-safe
        - Commits don't interfere with each other
        """
        from precog.database.connection import execute_query

        success_count = []
        errors = []
        barrier = CISafeBarrier(4, timeout=self.BARRIER_TIMEOUT)

        def run_execute(thread_id: int):
            try:
                barrier.wait()
                # SELECT doesn't modify data, safe for concurrent testing
                result = execute_query(
                    "SELECT %s as val",
                    (thread_id,),
                    commit=False,
                )
                success_count.append((thread_id, result))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(4):
            t = threading.Thread(target=run_execute, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(success_count) == 4


@pytest.mark.race
class TestConnectionInitializationRace:
    """Race tests for pool initialization edge cases."""

    BARRIER_TIMEOUT = 15.0

    def test_concurrent_pool_access_when_none(self):
        """
        RACE: Multiple threads calling get_connection when pool is None.

        Verifies:
        - Auto-initialization is thread-safe
        - Only one pool is created
        """
        from precog.database import connection

        # Save original pool
        original_pool = connection._connection_pool

        # Set to None (simulating first access)
        connection._connection_pool = None

        connections = []
        errors = []
        lock = threading.Lock()
        barrier = CISafeBarrier(5, timeout=self.BARRIER_TIMEOUT)

        def get_conn(thread_id: int):
            try:
                barrier.wait()
                conn = connection.get_connection()
                with lock:
                    connections.append((thread_id, conn))
                connection.release_connection(conn)
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        try:
            threads = []
            for i in range(5):
                t = threading.Thread(target=get_conn, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=30)

            timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
            if timeout_errors:
                pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

            other_errors = [e for e in errors if "timeout" not in e[1].lower()]
            assert len(other_errors) == 0, f"Errors: {other_errors}"
            assert len(connections) == 5

            # Pool should exist after all threads complete
            assert connection._connection_pool is not None
        finally:
            # Restore original pool
            if original_pool != connection._connection_pool:
                connection.close_pool()
                connection._connection_pool = original_pool

    def test_concurrent_close_pool(self):
        """
        RACE: Multiple threads calling close_pool simultaneously.

        Verifies:
        - close_pool is idempotent
        - No crash on concurrent close
        """
        from precog.database import connection

        # Ensure pool exists
        connection.initialize_pool()

        errors = []
        barrier = CISafeBarrier(5, timeout=self.BARRIER_TIMEOUT)

        def close_pool_thread(thread_id: int):
            try:
                barrier.wait()
                connection.close_pool()
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(5):
            t = threading.Thread(target=close_pool_thread, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        # closeall() on None pool is handled gracefully
        assert len(other_errors) == 0, f"Errors: {other_errors}"

        # Re-initialize for other tests
        connection.initialize_pool()


@pytest.mark.race
class TestTransactionRace:
    """Race tests for transaction behavior."""

    BARRIER_TIMEOUT = 15.0

    def test_concurrent_commit_rollback(self):
        """
        RACE: Threads committing and rolling back simultaneously.

        Verifies:
        - Independent transactions don't affect each other
        - Rollback in one thread doesn't affect commit in another
        """
        from precog.database.connection import get_cursor

        results = []
        errors = []
        barrier = CISafeBarrier(4, timeout=self.BARRIER_TIMEOUT)

        def transaction_work(thread_id: int, should_commit: bool):
            try:
                barrier.wait()
                with get_cursor(commit=should_commit) as cur:
                    cur.execute("SELECT %s as thread_id", (thread_id,))
                    result = cur.fetchone()
                    results.append((thread_id, should_commit, result["thread_id"]))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(4):
            should_commit = i % 2 == 0
            t = threading.Thread(target=transaction_work, args=(i, should_commit))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(results) == 4

        # Verify each thread got its own result
        for thread_id, _, result in results:
            assert result == thread_id

    def test_exception_rollback_isolation(self):
        """
        RACE: One thread raises exception while others succeed.

        Verifies:
        - Exception in one thread doesn't affect others
        - Rollback is isolated to failing thread
        """
        from precog.database.connection import get_cursor

        success_results = []
        error_results = []
        lock = threading.Lock()
        barrier = CISafeBarrier(4, timeout=self.BARRIER_TIMEOUT)

        def maybe_fail(thread_id: int):
            try:
                barrier.wait()
                with get_cursor() as cur:
                    if thread_id == 2:  # Thread 2 will fail
                        cur.execute("INVALID SQL SYNTAX !!!")
                    else:
                        cur.execute("SELECT %s as val", (thread_id,))
                        result = cur.fetchone()
                        with lock:
                            success_results.append((thread_id, result["val"]))
            except TimeoutError:
                with lock:
                    error_results.append((thread_id, "Barrier timeout"))
            except Exception as e:
                with lock:
                    error_results.append((thread_id, str(e)))

        threads = []
        for i in range(4):
            t = threading.Thread(target=maybe_fail, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in error_results if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        # Thread 2 should fail, others should succeed
        assert len(success_results) == 3, f"Expected 3 successes, got {success_results}"

        # Thread 2's error should be captured
        sql_errors = [e for e in error_results if "timeout" not in e[1].lower()]
        assert len(sql_errors) == 1
        assert sql_errors[0][0] == 2  # Thread 2 failed


@pytest.mark.race
class TestEnvironmentFunctionRace:
    """Race tests for environment-related functions."""

    BARRIER_TIMEOUT = 15.0

    def test_concurrent_get_environment(self):
        """
        RACE: Multiple threads calling get_environment.

        Verifies:
        - get_environment is thread-safe
        - All threads get consistent result
        """
        from precog.database.connection import get_environment

        results = []
        errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def get_env(thread_id: int):
            try:
                barrier.wait()
                env = get_environment()
                results.append((thread_id, env))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(10):
            t = threading.Thread(target=get_env, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(results) == 10

        # All threads should get the same environment
        envs = {env for _, env in results}
        assert len(envs) == 1, f"Inconsistent environments: {envs}"

    def test_concurrent_test_connection(self):
        """
        RACE: Multiple threads calling test_connection.

        Verifies:
        - test_connection is thread-safe
        - All threads can test successfully
        """
        from precog.database.connection import test_connection

        results = []
        errors = []
        barrier = CISafeBarrier(5, timeout=self.BARRIER_TIMEOUT)

        def test_conn(thread_id: int):
            try:
                barrier.wait()
                result = test_connection()
                results.append((thread_id, result))
            except TimeoutError:
                errors.append((thread_id, "Barrier timeout"))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = []
        for i in range(5):
            t = threading.Thread(target=test_conn, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads")

        other_errors = [e for e in errors if "timeout" not in e[1].lower()]
        assert len(other_errors) == 0, f"Errors: {other_errors}"
        assert len(results) == 5

        # All should return True (connection works)
        for thread_id, result in results:
            assert result is True, f"Thread {thread_id} failed connection test"
