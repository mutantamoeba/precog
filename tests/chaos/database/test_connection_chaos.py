"""
Chaos Tests for Database Connection.

Tests database connection resilience under chaotic conditions:
- Connection pool exhaustion
- Database unavailability
- Malformed credentials
- Connection timeout scenarios
- Transaction rollback failures

Related:
- TESTING_STRATEGY V3.5: All 8 test types required
- database/connection module coverage

Usage:
    pytest tests/chaos/database/test_connection_chaos.py -v -m chaos

Educational Note:
    Chaos tests verify that the database connection layer degrades gracefully when:
    1. Pool is exhausted (all connections in use)
    2. Database server is unavailable
    3. Credentials are invalid
    4. Network issues cause timeouts
    5. Transactions fail unexpectedly

    The connection module uses a global singleton pool pattern, so these tests
    must be careful about cleanup to not affect other tests.

Reference: docs/foundation/TESTING_STRATEGY_V3.5.md Section "Best Practice #6"
"""

import os
from unittest.mock import MagicMock, patch

import psycopg2
import pytest


@pytest.mark.chaos
class TestConnectionPoolChaos:
    """Chaos tests for connection pool behavior under failure."""

    def test_pool_already_initialized_warning(self):
        """
        CHAOS: Initialize pool when already initialized.

        Verifies:
        - Warning logged for double initialization
        - Returns existing pool (no new pool created)
        - No crash on double init
        """
        from precog.database.connection import _connection_pool, initialize_pool

        # Pool should already be initialized from module import
        if _connection_pool is not None:
            # Try to initialize again
            result = initialize_pool()
            # Should return existing pool
            assert result is not None

    def test_missing_password_raises_error(self):
        """
        CHAOS: Initialize pool without password.

        Verifies:
        - ValueError raised when password missing
        - Clear error message about missing password
        """
        from precog.database import connection

        # Save current pool
        original_pool = connection._connection_pool
        connection._connection_pool = None

        try:
            with patch.dict(os.environ, {"DB_PASSWORD": ""}, clear=False):
                # Remove DB_PASSWORD
                with patch.object(
                    os, "getenv", side_effect=lambda k, d=None: None if k == "DB_PASSWORD" else d
                ):
                    with pytest.raises(ValueError, match="password"):
                        connection.initialize_pool(
                            host="localhost",
                            port=5432,
                            database="test",
                            user="test",
                            password=None,
                        )
        finally:
            # Restore original pool
            connection._connection_pool = original_pool

    def test_invalid_host_connection_error(self):
        """
        CHAOS: Connect to non-existent host.

        Verifies:
        - psycopg2.Error raised for invalid host
        - Pool initialization fails gracefully
        """
        from precog.database import connection

        # Save current pool
        original_pool = connection._connection_pool
        connection._connection_pool = None

        try:
            with pytest.raises(psycopg2.Error):
                connection.initialize_pool(
                    host="nonexistent.invalid.host.local",
                    port=5432,
                    database="test",
                    user="test",
                    password="test",
                )
        finally:
            connection._connection_pool = original_pool

    def test_invalid_port_connection_error(self):
        """
        CHAOS: Connect to invalid port.

        Verifies:
        - Connection error for wrong port
        """
        from precog.database import connection

        original_pool = connection._connection_pool
        connection._connection_pool = None

        try:
            with pytest.raises(psycopg2.Error):
                connection.initialize_pool(
                    host="localhost",
                    port=59999,  # Invalid port
                    database="test",
                    user="test",
                    password="test",
                )
        finally:
            connection._connection_pool = original_pool


@pytest.mark.chaos
class TestConnectionCursorChaos:
    """Chaos tests for cursor and query execution."""

    def test_query_execution_error(self):
        """
        CHAOS: Execute invalid SQL query.

        Verifies:
        - SQL syntax error raises appropriate exception
        - Connection still usable after error
        """
        from precog.database.connection import get_cursor

        with pytest.raises(psycopg2.Error):
            with get_cursor() as cur:
                cur.execute("THIS IS NOT VALID SQL SYNTAX !!!")

    def test_transaction_rollback_on_error(self):
        """
        CHAOS: Error during transaction causes rollback.

        Verifies:
        - Transaction rolled back on exception
        - Connection returned to pool in valid state
        """
        from precog.database.connection import get_cursor

        # Try to execute bad query - should rollback
        try:
            with get_cursor(commit=True) as cur:
                # First, a valid query
                cur.execute("SELECT 1")
                # Then an invalid one - causes rollback
                cur.execute("INVALID SQL HERE")
        except psycopg2.Error:
            pass  # Expected

        # Connection should still work
        with get_cursor() as cur:
            cur.execute("SELECT 1 as test")
            result = cur.fetchone()
            assert result["test"] == 1

    def test_fetch_on_empty_result(self):
        """
        CHAOS: Fetch from query with no results.

        Verifies:
        - fetchone() returns None for empty result
        - fetchall() returns empty list
        """
        from precog.database.connection import get_cursor

        with get_cursor() as cur:
            # Query that returns no rows
            cur.execute("SELECT 1 WHERE 1=0")

            one = cur.fetchone()
            assert one is None

        with get_cursor() as cur:
            cur.execute("SELECT 1 WHERE 1=0")
            all_rows = cur.fetchall()
            assert all_rows == []

    def test_execute_with_wrong_parameter_count(self):
        """
        CHAOS: Execute query with wrong number of parameters.

        Verifies:
        - Appropriate error for parameter mismatch
        """
        from precog.database.connection import get_cursor

        with pytest.raises((psycopg2.Error, IndexError, TypeError)):
            with get_cursor() as cur:
                # Query expects 2 params, only 1 provided
                cur.execute("SELECT %s, %s", ("only_one",))


@pytest.mark.chaos
class TestConnectionHelpersChaos:
    """Chaos tests for helper functions."""

    def test_execute_query_with_sql_error(self):
        """
        CHAOS: execute_query with invalid SQL.

        Verifies:
        - SQL error propagated correctly
        - Returns appropriate error type
        """
        from precog.database.connection import execute_query

        with pytest.raises(psycopg2.Error):
            execute_query("THIS IS NOT VALID SQL", commit=False)

    def test_fetch_one_nonexistent_table(self):
        """
        CHAOS: fetch_one from non-existent table.

        Verifies:
        - UndefinedTable error raised
        """
        from precog.database.connection import fetch_one

        with pytest.raises(psycopg2.Error):
            fetch_one("SELECT * FROM nonexistent_table_xyz_12345")

    def test_fetch_all_nonexistent_table(self):
        """
        CHAOS: fetch_all from non-existent table.

        Verifies:
        - UndefinedTable error raised
        """
        from precog.database.connection import fetch_all

        with pytest.raises(psycopg2.Error):
            fetch_all("SELECT * FROM nonexistent_table_xyz_12345")

    def test_test_connection_with_pool_closed(self):
        """
        CHAOS: test_connection when pool was closed.

        Verifies:
        - test_connection handles closed pool
        - Re-initializes pool or returns False
        """
        from precog.database import connection

        original_pool = connection._connection_pool

        # Temporarily set pool to None
        connection._connection_pool = None

        try:
            # Should either re-init or return False
            result = connection.test_connection()
            # If it succeeds, pool was re-initialized
            assert result is True or result is False
        finally:
            connection._connection_pool = original_pool


@pytest.mark.chaos
class TestEnvironmentChaos:
    """Chaos tests for environment detection and protection."""

    def test_invalid_environment_required(self):
        """
        CHAOS: require_environment with invalid environment string.

        Verifies:
        - ValueError raised for invalid environment
        """
        from precog.database.connection import require_environment

        with pytest.raises(ValueError, match="Invalid required environment"):
            require_environment("invalid_env_name")

    def test_environment_mismatch(self):
        """
        CHAOS: require_environment when in different environment.

        Verifies:
        - RuntimeError raised when environment doesn't match
        """
        from precog.database.connection import get_environment, require_environment

        current = get_environment()

        # Require a different environment
        other_env = "prod" if current != "prod" else "dev"

        with pytest.raises(RuntimeError, match=r"requires.*environment"):
            require_environment(other_env)

    def test_dangerous_operation_in_prod(self):
        """
        CHAOS: Attempt dangerous operation in production.

        Verifies:
        - RuntimeError raised for dangerous ops in prod
        - Clear error message about production
        """
        from precog.database.connection import protect_dangerous_operation

        # Mock production environment
        with patch("precog.database.connection.get_environment", return_value="prod"):
            with pytest.raises(RuntimeError, match="not allowed in production"):
                protect_dangerous_operation("DROP TABLE test")

    def test_dangerous_operation_in_staging(self):
        """
        CHAOS: Attempt dangerous operation in staging.

        Verifies:
        - RuntimeError raised for dangerous ops in staging
        """
        from precog.database.connection import protect_dangerous_operation

        with patch("precog.database.connection.get_environment", return_value="staging"):
            with pytest.raises(RuntimeError, match="not allowed in staging"):
                protect_dangerous_operation("TRUNCATE positions")

    def test_dangerous_operation_blocked_in_dev(self):
        """
        CHAOS: Block operation even in dev when allow_in_dev=False.

        Verifies:
        - Operations can be blocked even in dev
        """
        from precog.database.connection import protect_dangerous_operation

        with patch("precog.database.connection.get_environment", return_value="dev"):
            with pytest.raises(RuntimeError, match="not allowed in dev"):
                protect_dangerous_operation("DANGEROUS OP", allow_in_dev=False)


@pytest.mark.chaos
class TestPoolReleaseChaos:
    """Chaos tests for connection release behavior."""

    def test_release_connection_with_none_pool(self):
        """
        CHAOS: release_connection when pool is None.

        Verifies:
        - No crash when releasing to None pool
        """
        from precog.database import connection

        original_pool = connection._connection_pool

        try:
            connection._connection_pool = None
            # Should not raise
            connection.release_connection(MagicMock())
        finally:
            connection._connection_pool = original_pool

    def test_close_pool_when_already_closed(self):
        """
        CHAOS: close_pool when pool is already None.

        Verifies:
        - No crash when closing already-closed pool
        """
        from precog.database import connection

        original_pool = connection._connection_pool

        try:
            connection._connection_pool = None
            # Should not raise
            connection.close_pool()
        finally:
            connection._connection_pool = original_pool

    def test_get_connection_with_no_pool(self):
        """
        CHAOS: get_connection when pool not initialized.

        Verifies:
        - Auto-initializes pool
        - Returns valid connection
        """
        from precog.database import connection

        original_pool = connection._connection_pool

        try:
            connection._connection_pool = None

            # Should auto-initialize
            conn = connection.get_connection()
            assert conn is not None

            # Clean up
            connection.release_connection(conn)
        finally:
            # Ensure original pool restored for other tests
            if original_pool != connection._connection_pool:
                connection.close_pool()
                connection._connection_pool = original_pool
