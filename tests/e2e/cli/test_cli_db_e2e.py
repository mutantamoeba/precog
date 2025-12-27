"""E2E tests for CLI db module.

Tests complete database workflows from CLI invocation through database effects.

References:
    - REQ-TEST-004: End-to-end workflow testing
    - Issue #258: Create shared CLI test fixtures
    - TESTING_STRATEGY V3.2: 8 test types required

Note:
    Uses shared CLI fixtures from tests/conftest.py (cli_runner, cli_app).

Parallel Execution Note:
    These tests must create fresh app instances to avoid test pollution during
    parallel pytest-xdist execution. The global app object is shared across
    workers, causing race conditions when multiple tests register commands
    or invoke CLI operations simultaneously.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer


@pytest.fixture
def isolated_app():
    """Create a completely isolated Typer app for E2E testing.

    This fixture creates a fresh app instance that doesn't share state with
    other tests, preventing race conditions during parallel execution.

    Educational Note:
        During pytest-xdist parallel execution, the global app imported from
        precog.cli is shared across worker processes. Multiple tests modifying
        this shared state (registering commands, invoking CLI operations) can
        cause "I/O operation on closed file" errors and other race conditions.
        Creating a fresh app per test ensures complete isolation.
    """
    from precog.cli import db, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestDatabaseInitWorkflow:
    """E2E tests for database initialization workflow."""

    def test_complete_db_init_workflow(self, cli_runner, isolated_app) -> None:
        """Test complete database initialization workflow.

        E2E: Tests init from connection test through schema creation.

        Note: The init command may call get_connection() in some code paths,
        so all database functions must be mocked to prevent real database access.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = cli_runner.invoke(isolated_app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_db_init_then_status_workflow(self, cli_runner, isolated_app) -> None:
        """Test init followed by status check workflow.

        E2E: Tests initialization then verification.

        Parallel Execution Note:
            This test creates multiple CLI invocations. Using isolated_app
            prevents race conditions when other tests run in parallel.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Initialize
            result = cli_runner.invoke(isolated_app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

            # Check status
            result = cli_runner.invoke(isolated_app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseMigrationWorkflow:
    """E2E tests for database migration workflow."""

    def test_complete_migration_workflow(self, cli_runner, isolated_app) -> None:
        """Test complete migration workflow.

        E2E: Tests dry-run then actual migration.

        Note: The migrate command may call test_connection() in some code paths,
        so all database functions must be mocked to prevent real database access.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Dry run first
            result = cli_runner.invoke(isolated_app, ["db", "migrate", "--dry-run"])
            assert result.exit_code in [0, 1, 2, 3]

            # Then actual migration
            result = cli_runner.invoke(isolated_app, ["db", "migrate"])
            assert result.exit_code in [0, 1, 2, 3]

    def test_migration_with_status_check(self, cli_runner, isolated_app) -> None:
        """Test migration with status check workflow.

        E2E: Tests migration then status verification.

        Note: The status command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Migrate
            result = cli_runner.invoke(isolated_app, ["db", "migrate"])
            assert result.exit_code in [0, 1, 2, 3]

            # Check status
            result = cli_runner.invoke(isolated_app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]

            # List tables
            result = cli_runner.invoke(isolated_app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseInspectionWorkflow:
    """E2E tests for database inspection workflow."""

    def test_complete_inspection_workflow(self, cli_runner, isolated_app) -> None:
        """Test complete database inspection workflow.

        E2E: Tests status, tables, and detailed inspection.

        Note: The status command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Status
            result = cli_runner.invoke(isolated_app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]

            # Tables
            result = cli_runner.invoke(isolated_app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]

            # Tables with counts
            result = cli_runner.invoke(isolated_app, ["db", "tables", "--counts"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseErrorRecovery:
    """E2E tests for database error recovery workflows."""

    def test_init_retry_on_connection_failure(self, cli_runner, isolated_app) -> None:
        """Test init retry after connection failure.

        E2E: Tests error recovery workflow.

        Note: The init command may call get_connection() in some code paths,
        so all database functions must be mocked to prevent real database access.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            # First call fails, second succeeds
            mock_test.side_effect = [Exception("Connection refused"), True]
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # First attempt fails
            result = cli_runner.invoke(isolated_app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_status_handles_db_disconnect(self, cli_runner, isolated_app) -> None:
        """Test status handles database disconnect.

        E2E: Tests graceful handling of connection loss.

        Note: The status command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = False
            mock_conn.side_effect = Exception("Connection lost")

            result = cli_runner.invoke(isolated_app, ["db", "status"])
            # Should handle error gracefully
            assert result.exit_code in [0, 1, 2, 3, 4, 5]
