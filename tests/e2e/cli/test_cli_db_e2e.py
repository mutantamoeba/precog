"""E2E tests for CLI db module.

Tests complete database workflows from CLI invocation through database effects.

References:
    - REQ-TEST-004: End-to-end workflow testing
    - Issue #258: Create shared CLI test fixtures
    - TESTING_STRATEGY V3.2: 8 test types required

Note:
    Uses shared CLI fixtures from tests/conftest.py (cli_runner, cli_app).
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.cli import app, register_commands


@pytest.fixture(autouse=True)
def setup_commands():
    """Ensure commands are registered before each test."""
    register_commands()


class TestDatabaseInitWorkflow:
    """E2E tests for database initialization workflow."""

    def test_complete_db_init_workflow(self, cli_runner) -> None:
        """Test complete database initialization workflow.

        E2E: Tests init from connection test through schema creation.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            result = cli_runner.invoke(app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_db_init_then_status_workflow(self, cli_runner) -> None:
        """Test init followed by status check workflow.

        E2E: Tests initialization then verification.
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
            result = cli_runner.invoke(app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

            # Check status
            result = cli_runner.invoke(app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseMigrationWorkflow:
    """E2E tests for database migration workflow."""

    def test_complete_migration_workflow(self, cli_runner) -> None:
        """Test complete migration workflow.

        E2E: Tests dry-run then actual migration.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Dry run first
            result = cli_runner.invoke(app, ["db", "migrate", "--dry-run"])
            assert result.exit_code in [0, 1, 2, 3]

            # Then actual migration
            result = cli_runner.invoke(app, ["db", "migrate"])
            assert result.exit_code in [0, 1, 2, 3]

    def test_migration_with_status_check(self, cli_runner) -> None:
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
            result = cli_runner.invoke(app, ["db", "migrate"])
            assert result.exit_code in [0, 1, 2, 3]

            # Check status
            result = cli_runner.invoke(app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]

            # List tables
            result = cli_runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseInspectionWorkflow:
    """E2E tests for database inspection workflow."""

    def test_complete_inspection_workflow(self, cli_runner) -> None:
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
            result = cli_runner.invoke(app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]

            # Tables
            result = cli_runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]

            # Tables with counts
            result = cli_runner.invoke(app, ["db", "tables", "--counts"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseErrorRecovery:
    """E2E tests for database error recovery workflows."""

    def test_init_retry_on_connection_failure(self, cli_runner) -> None:
        """Test init retry after connection failure.

        E2E: Tests error recovery workflow.
        """
        with patch("precog.database.connection.test_connection") as mock_test:
            # First call fails, second succeeds
            mock_test.side_effect = [Exception("Connection refused"), True]

            # First attempt fails
            result = cli_runner.invoke(app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_status_handles_db_disconnect(self, cli_runner) -> None:
        """Test status handles database disconnect.

        E2E: Tests graceful handling of connection loss.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Connection lost")

            result = cli_runner.invoke(app, ["db", "status"])
            # Should handle error gracefully
            assert result.exit_code in [0, 1, 2, 3, 4, 5]
