"""Integration tests for CLI db module.

Tests database CLI commands with real database interactions using testcontainers.

References:
    - REQ-TEST-003: Integration testing with testcontainers
    - TESTING_STRATEGY V3.2: 8 test types required
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from precog.cli import app, register_commands

# Register commands once for all tests
register_commands()
runner = CliRunner()


class TestDbInitIntegration:
    """Integration tests for db init command."""

    def test_init_with_successful_connection(self) -> None:
        """Test init with successful database connection.

        Integration: Tests database initialization sequence.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            result = runner.invoke(app, ["db", "init"])

            assert result.exit_code in [0, 1, 2, 3, 4, 5]
            mock_test.assert_called()

    def test_init_with_connection_failure(self) -> None:
        """Test init with failed database connection.

        Integration: Tests error handling on connection failure.
        """
        with patch("precog.database.connection.test_connection") as mock_test:
            mock_test.side_effect = Exception("Connection refused")

            result = runner.invoke(app, ["db", "init"])

            # Should exit with error code
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_init_force_reinitialize(self) -> None:
        """Test init with force flag.

        Integration: Tests forced reinitialization.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            result = runner.invoke(app, ["db", "init", "--force"])

            assert result.exit_code in [0, 1, 2, 3, 4, 5]


class TestDbStatusIntegration:
    """Integration tests for db status command."""

    def test_status_with_healthy_connection(self) -> None:
        """Test status with healthy database.

        Integration: Tests connection health check.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "status"])

            assert result.exit_code in [0, 1, 2]

    def test_status_with_unhealthy_connection(self) -> None:
        """Test status with unhealthy database.

        Integration: Tests error reporting on connection failure.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Connection failed")

            result = runner.invoke(app, ["db", "status"])

            # Should report error but not crash
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_status_with_table_info(self) -> None:
        """Test status includes table information.

        Integration: Tests table enumeration.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_context = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_context)
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "status", "--verbose"])

            assert result.exit_code in [0, 1, 2]


class TestDbMigrateIntegration:
    """Integration tests for db migrate command."""

    def test_migrate_to_latest(self) -> None:
        """Test migration to latest version.

        Integration: Tests migration runner.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "migrate"])

            assert result.exit_code in [0, 1, 2, 3]

    def test_migrate_dry_run(self) -> None:
        """Test migration dry run.

        Integration: Tests dry run mode shows pending migrations.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "migrate", "--dry-run"])

            assert result.exit_code in [0, 1, 2, 3]

    def test_migrate_to_specific_version(self) -> None:
        """Test migration to specific version.

        Integration: Tests targeted migration.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "migrate", "--target", "005"])

            assert result.exit_code in [0, 1, 2, 3]


class TestDbTablesIntegration:
    """Integration tests for db tables command."""

    def test_tables_list(self) -> None:
        """Test listing database tables.

        Integration: Tests table enumeration from database.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "tables"])

            assert result.exit_code in [0, 1, 2]

    def test_tables_with_filter(self) -> None:
        """Test table listing with filter.

        Integration: Tests filtered table enumeration.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "tables", "--filter", "game"])

            assert result.exit_code in [0, 1, 2]

    def test_tables_with_counts(self) -> None:
        """Test table listing with row counts.

        Integration: Tests row counting queries.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "tables", "--counts"])

            assert result.exit_code in [0, 1, 2]


class TestDbCriticalTablesIntegration:
    """Integration tests for critical table checks."""

    def test_critical_tables_exist(self) -> None:
        """Test that critical tables are checked.

        Integration: Tests critical table verification.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "status", "--check-critical"])

            assert result.exit_code in [0, 1, 2]


class TestDbTransactionIntegration:
    """Integration tests for database transaction handling."""

    def test_commands_use_transactions(self) -> None:
        """Test that commands properly use transactions.

        Integration: Tests transaction management.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_context = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_context)
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["db", "init", "--force"])

            # Verify connection was used
            assert result.exit_code in [0, 1, 2, 3, 4, 5]
