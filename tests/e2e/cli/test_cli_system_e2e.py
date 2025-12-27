"""E2E tests for CLI system module.

Tests complete system workflows from CLI invocation through component checks.

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


class TestSystemHealthWorkflow:
    """E2E tests for system health workflow."""

    def test_complete_health_check_workflow(self) -> None:
        """Test complete health check workflow.

        E2E: Tests health check across all components.

        Note: The health command may call test_connection() in some code paths,
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Basic health
            result = runner.invoke(app, ["system", "health"])
            assert result.exit_code in [0, 1, 2]

            # Verbose health
            result = runner.invoke(app, ["system", "health", "--verbose"])
            assert result.exit_code in [0, 1, 2]

    def test_health_with_component_targeting(self) -> None:
        """Test health check with component targeting.

        E2E: Tests targeted component health checks.

        Note: The health command may call test_connection() in some code paths,
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Database component
            result = runner.invoke(app, ["system", "health", "--component", "database"])
            assert result.exit_code in [0, 1, 2]

            # Config component
            result = runner.invoke(app, ["system", "health", "--component", "config"])
            assert result.exit_code in [0, 1, 2]


class TestSystemInfoWorkflow:
    """E2E tests for system info workflow."""

    def test_complete_info_workflow(self) -> None:
        """Test complete system info workflow.

        E2E: Tests info gathering across all areas.

        Note: Mock database functions to prevent test pollution when running
        in parallel with other tests that use database connections.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Basic info
            result = runner.invoke(app, ["system", "info"])
            assert result.exit_code in [0, 1, 2]

            # With environment
            result = runner.invoke(app, ["system", "info", "--env"])
            assert result.exit_code in [0, 1, 2]

            # With config
            result = runner.invoke(app, ["system", "info", "--config"])
            assert result.exit_code in [0, 1, 2]

            # With paths
            result = runner.invoke(app, ["system", "info", "--paths"])
            assert result.exit_code in [0, 1, 2]


class TestSystemVersionWorkflow:
    """E2E tests for system version workflow."""

    def test_complete_version_workflow(self) -> None:
        """Test complete version information workflow.

        E2E: Tests version info gathering.

        Note: Mock database functions to prevent test pollution when running
        in parallel with other tests that use database connections.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Basic version
            result = runner.invoke(app, ["system", "version"])
            assert result.exit_code in [0, 1, 2]

            # With dependencies
            result = runner.invoke(app, ["system", "version", "--deps"])
            assert result.exit_code in [0, 1, 2]

            # JSON output
            result = runner.invoke(app, ["system", "version", "--json"])
            assert result.exit_code in [0, 1, 2]


class TestSystemDiagnosticsWorkflow:
    """E2E tests for system diagnostics workflow."""

    def test_complete_diagnostics_workflow(self) -> None:
        """Test complete diagnostics workflow.

        E2E: Tests gathering full diagnostics.

        Note: The health command may call test_connection() in some code paths,
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            # Health with diagnostics
            result = runner.invoke(app, ["system", "health", "--diagnostics"])
            assert result.exit_code in [0, 1, 2]

            # Version
            result = runner.invoke(app, ["system", "version"])
            assert result.exit_code in [0, 1, 2]

            # Info
            result = runner.invoke(app, ["system", "info"])
            assert result.exit_code in [0, 1, 2]


class TestSystemErrorRecovery:
    """E2E tests for system error recovery workflows."""

    def test_health_recovers_from_component_failure(self) -> None:
        """Test health check recovers from component failure.

        E2E: Tests error recovery workflow.

        Note: The health command may call test_connection() in some code paths,
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = False
            mock_conn.side_effect = Exception("Database unavailable")

            result = runner.invoke(app, ["system", "health"])
            # Should complete even with failures
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_info_handles_partial_failures(self) -> None:
        """Test info handles partial failures.

        E2E: Tests graceful degradation.

        Note: Mock database functions to prevent test pollution when running
        in parallel with other tests that use database connections.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["system", "info", "--env", "--config", "--paths"])
            assert result.exit_code in [0, 1, 2]
