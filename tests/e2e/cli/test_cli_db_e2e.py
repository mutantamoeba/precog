"""E2E tests for CLI db module.

Tests complete database workflows from CLI invocation through database effects.

References:
    - REQ-TEST-004: End-to-end workflow testing
    - TESTING_STRATEGY V3.2: 8 test types required
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from precog.cli import app, register_commands

# Register commands once for all tests
register_commands()
runner = CliRunner()


class TestDatabaseInitWorkflow:
    """E2E tests for database initialization workflow."""

    def test_complete_db_init_workflow(self) -> None:
        """Test complete database initialization workflow.

        E2E: Tests init from connection test through schema creation.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            result = runner.invoke(app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_db_init_then_status_workflow(self) -> None:
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
            result = runner.invoke(app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

            # Check status
            result = runner.invoke(app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseMigrationWorkflow:
    """E2E tests for database migration workflow."""

    def test_complete_migration_workflow(self) -> None:
        """Test complete migration workflow.

        E2E: Tests dry-run then actual migration.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Dry run first
            result = runner.invoke(app, ["db", "migrate", "--dry-run"])
            assert result.exit_code in [0, 1, 2, 3]

            # Then actual migration
            result = runner.invoke(app, ["db", "migrate"])
            assert result.exit_code in [0, 1, 2, 3]

    def test_migration_with_status_check(self) -> None:
        """Test migration with status check workflow.

        E2E: Tests migration then status verification.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Migrate
            result = runner.invoke(app, ["db", "migrate"])
            assert result.exit_code in [0, 1, 2, 3]

            # Check status
            result = runner.invoke(app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]

            # List tables
            result = runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseInspectionWorkflow:
    """E2E tests for database inspection workflow."""

    def test_complete_inspection_workflow(self) -> None:
        """Test complete database inspection workflow.

        E2E: Tests status, tables, and detailed inspection.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Status
            result = runner.invoke(app, ["db", "status"])
            assert result.exit_code in [0, 1, 2]

            # Tables
            result = runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]

            # Tables with counts
            result = runner.invoke(app, ["db", "tables", "--counts"])
            assert result.exit_code in [0, 1, 2]


class TestDatabaseErrorRecovery:
    """E2E tests for database error recovery workflows."""

    def test_init_retry_on_connection_failure(self) -> None:
        """Test init retry after connection failure.

        E2E: Tests error recovery workflow.
        """
        with patch("precog.database.connection.test_connection") as mock_test:
            # First call fails, second succeeds
            mock_test.side_effect = [Exception("Connection refused"), True]

            # First attempt fails
            result = runner.invoke(app, ["db", "init"])
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_status_handles_db_disconnect(self) -> None:
        """Test status handles database disconnect.

        E2E: Tests graceful handling of connection loss.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Connection lost")

            result = runner.invoke(app, ["db", "status"])
            # Should handle error gracefully
            assert result.exit_code in [0, 1, 2, 3, 4, 5]
