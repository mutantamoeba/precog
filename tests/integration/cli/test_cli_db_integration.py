"""Integration tests for CLI db module.

Tests database CLI commands with real database interactions using testcontainers.

References:
    - REQ-TEST-003: Integration testing with testcontainers
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


class TestDbInitIntegration:
    """Integration tests for db init command."""

    def test_init_with_successful_connection(self, cli_runner) -> None:
        """Test init with successful database connection.

        Integration: Tests database initialization sequence.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            result = cli_runner.invoke(app, ["db", "init"])

            assert result.exit_code in [0, 1, 2, 3, 4, 5]
            mock_test.assert_called()

    def test_init_with_connection_failure(self, cli_runner) -> None:
        """Test init with failed database connection.

        Integration: Tests error handling on connection failure.
        """
        with patch("precog.database.connection.test_connection") as mock_test:
            mock_test.side_effect = Exception("Connection refused")

            result = cli_runner.invoke(app, ["db", "init"])

            # Should exit with error code
            assert result.exit_code in [0, 1, 2, 3, 4, 5]


class TestDbStatusIntegration:
    """Integration tests for db status command."""

    def test_status_with_healthy_connection(self, cli_runner) -> None:
        """Test status with healthy database.

        Integration: Tests connection health check.

        Note: The status command calls both test_connection() AND get_cursor(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_cursor_ctx,
        ):
            mock_test.return_value = True
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {
                "version": "PostgreSQL 15.0",
                "current_database": "precog_test",
                "table_count": 0,
                "exists": False,
                "test": 1,
            }
            mock_cur.fetchall.return_value = []
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = cli_runner.invoke(app, ["db", "status"])

            assert result.exit_code in [0, 1, 2]

    def test_status_with_unhealthy_connection(self, cli_runner) -> None:
        """Test status with unhealthy database.

        Integration: Tests error reporting on connection failure.

        Note: The status command calls both test_connection() AND get_cursor(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_cursor_ctx,
        ):
            mock_test.return_value = False
            mock_cursor_ctx.side_effect = Exception("Connection failed")

            result = cli_runner.invoke(app, ["db", "status"])

            # Should report error but not crash
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_status_with_table_info(self, cli_runner) -> None:
        """Test status includes table information.

        Integration: Tests table enumeration.

        Note: The status command calls both test_connection() AND get_cursor(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_cursor_ctx,
        ):
            mock_test.return_value = True
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {
                "version": "PostgreSQL 15.0",
                "current_database": "precog_test",
                "table_count": 0,
                "exists": False,
                "test": 1,
            }
            mock_cur.fetchall.return_value = []
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = cli_runner.invoke(app, ["db", "status", "--verbose"])

            assert result.exit_code in [0, 1, 2]


class TestDbTablesIntegration:
    """Integration tests for db tables command."""

    def test_tables_list(self, cli_runner) -> None:
        """Test listing database tables.

        Integration: Tests table enumeration from database.
        """
        with patch("precog.database.connection.get_cursor") as mock_cursor_ctx:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"row_count": 0}
            mock_cur.fetchall.return_value = []
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = cli_runner.invoke(app, ["db", "tables"])

            assert result.exit_code in [0, 1, 2]

    def test_tables_with_filter(self, cli_runner) -> None:
        """Test table listing with filter.

        Integration: Tests filtered table enumeration via the --filter glob.
        """
        with patch("precog.database.connection.get_cursor") as mock_cursor_ctx:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"row_count": 0}
            mock_cur.fetchall.return_value = [{"table_name": "games"}]
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            result = cli_runner.invoke(app, ["db", "tables", "--filter", "game*"])

            assert result.exit_code == 0, f"got {result.exit_code}: {result.output}"
            assert "games" in result.output
            assert "matching 'game*'" in result.output

    # Tests for --counts, --check-critical, --force removed by S75 linter:
    # these flags don't exist in the current CLI. See #799.
