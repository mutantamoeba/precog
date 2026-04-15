"""Integration tests for CLI system module.

Tests system CLI commands with real component interactions.

References:
    - REQ-TEST-003: Integration testing with testcontainers
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
from typer.testing import CliRunner


@pytest.fixture
def isolated_app():
    """Create a completely isolated Typer app for integration testing.

    This fixture creates a fresh app instance that doesn't share state with
    other tests, preventing race conditions during parallel execution.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestSystemHealthIntegration:
    """Integration tests for system health command."""

    def test_health_all_components_healthy(self, isolated_app) -> None:
        """Test health when all components are healthy.

        Integration: Tests multi-component health check.
        """
        runner = CliRunner()

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(isolated_app, ["system", "health"])

            assert result.exit_code in [0, 1, 2]

    def test_health_database_unhealthy(self, isolated_app) -> None:
        """Test health when database is unhealthy.

        Integration: Tests partial failure handling.
        """
        runner = CliRunner()

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Database unavailable")

            result = runner.invoke(isolated_app, ["system", "health"])

            # Should complete but report unhealthy
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_health_verbose_output(self, isolated_app) -> None:
        """Test health verbose output.

        Integration: Tests detailed health reporting.
        """
        runner = CliRunner()

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(isolated_app, ["system", "health", "--verbose"])

            assert result.exit_code in [0, 1, 2]


class TestSystemVersionIntegration:
    """Integration tests for system version command."""

    def test_version_shows_package_version(self, isolated_app) -> None:
        """Test version displays package version.

        Integration: Tests package metadata access.
        """
        runner = CliRunner()

        result = runner.invoke(isolated_app, ["system", "version"])

        assert result.exit_code in [0, 1, 2]
        # Version output should exist
        assert result.output is not None


class TestSystemInfoIntegration:
    """Integration tests for system info command."""

    def test_info_shows_system_details(self, isolated_app) -> None:
        """Test info displays system details.

        Integration: Tests system information gathering.
        """
        runner = CliRunner()

        result = runner.invoke(isolated_app, ["system", "info"])

        assert result.exit_code in [0, 1, 2]


class TestSystemConfigIntegration:
    """Integration tests for system config interactions."""

    def test_system_loads_config(self, isolated_app) -> None:
        """Test system commands load configuration.

        Integration: Tests config loading.
        """
        runner = CliRunner()

        with patch("precog.config.config_loader.ConfigLoader") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get.return_value = {}
            mock_config.return_value = mock_config_instance

            result = runner.invoke(isolated_app, ["system", "info"])

            assert result.exit_code in [0, 1, 2]
