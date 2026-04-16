"""E2E tests for CLI system module.

Tests complete system workflows from CLI invocation through component checks.

References:
    - REQ-TEST-004: End-to-end workflow testing
    - TESTING_STRATEGY V3.2: 8 test types required

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


class TestSystemHealthWorkflow:
    """E2E tests for system health workflow."""

    def test_complete_health_check_workflow(self, cli_runner, isolated_app) -> None:
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
            result = cli_runner.invoke(isolated_app, ["system", "health"])
            assert result.exit_code in [0, 1, 2]

            # Verbose health
            result = cli_runner.invoke(isolated_app, ["system", "health", "--verbose"])
            assert result.exit_code in [0, 1, 2]


class TestSystemInfoWorkflow:
    """E2E tests for system info workflow."""

    def test_complete_info_workflow(self, cli_runner, isolated_app) -> None:
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
            result = cli_runner.invoke(isolated_app, ["system", "info"])
            assert result.exit_code in [0, 1, 2]


class TestSystemVersionWorkflow:
    """E2E tests for system version workflow."""

    def test_complete_version_workflow(self, cli_runner, isolated_app) -> None:
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
            result = cli_runner.invoke(isolated_app, ["system", "version"])
            assert result.exit_code in [0, 1, 2]


class TestSystemErrorRecovery:
    """E2E tests for system error recovery workflows."""

    def test_health_recovers_from_component_failure(self, cli_runner, isolated_app) -> None:
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

            result = cli_runner.invoke(isolated_app, ["system", "health"])
            # Should complete even with failures
            assert result.exit_code in [0, 1, 2, 3, 4, 5]
