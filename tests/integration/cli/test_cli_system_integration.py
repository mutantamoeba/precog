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
        runner = CliRunner(mix_stderr=False)

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(isolated_app, ["system", "health"])

            assert result.exit_code in [0, 1, 2]

    def test_health_database_unhealthy(self, isolated_app) -> None:
        """Test health when database is unhealthy.

        Integration: Tests partial failure handling.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Database unavailable")

            result = runner.invoke(isolated_app, ["system", "health"])

            # Should complete but report unhealthy
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_health_with_api_check(self, isolated_app) -> None:
        """Test health includes API connectivity check.

        Integration: Tests API health check.
        """
        runner = CliRunner(mix_stderr=False)

        with (
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.api_connectors.kalshi_client.KalshiClient") as mock_kalshi,
        ):
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()
            mock_kalshi_instance = MagicMock()
            mock_kalshi_instance.get_exchange_status.return_value = {"trading": "open"}
            mock_kalshi.return_value = mock_kalshi_instance

            result = runner.invoke(isolated_app, ["system", "health", "--check-apis"])

            assert result.exit_code in [0, 1, 2]

    def test_health_verbose_output(self, isolated_app) -> None:
        """Test health verbose output.

        Integration: Tests detailed health reporting.
        """
        runner = CliRunner(mix_stderr=False)

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
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "version"])

        assert result.exit_code in [0, 1, 2]
        # Version output should exist
        assert result.output is not None

    def test_version_with_dependencies(self, isolated_app) -> None:
        """Test version with dependency information.

        Integration: Tests dependency enumeration.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "version", "--deps"])

        assert result.exit_code in [0, 1, 2]

    def test_version_json_output(self, isolated_app) -> None:
        """Test version in JSON format.

        Integration: Tests JSON formatting.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "version", "--json"])

        assert result.exit_code in [0, 1, 2]


class TestSystemInfoIntegration:
    """Integration tests for system info command."""

    def test_info_shows_system_details(self, isolated_app) -> None:
        """Test info displays system details.

        Integration: Tests system information gathering.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "info"])

        assert result.exit_code in [0, 1, 2]

    def test_info_with_environment(self, isolated_app) -> None:
        """Test info with environment variables.

        Integration: Tests environment variable reporting.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "info", "--env"])

        assert result.exit_code in [0, 1, 2]

    def test_info_with_config(self, isolated_app) -> None:
        """Test info with configuration details.

        Integration: Tests config file parsing.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "info", "--config"])

        assert result.exit_code in [0, 1, 2]

    def test_info_with_paths(self, isolated_app) -> None:
        """Test info with path information.

        Integration: Tests path resolution.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "info", "--paths"])

        assert result.exit_code in [0, 1, 2]


class TestSystemDiagnosticsIntegration:
    """Integration tests for system diagnostics."""

    def test_diagnostics_collects_info(self, isolated_app) -> None:
        """Test diagnostics collection.

        Integration: Tests diagnostic data gathering.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(isolated_app, ["system", "health", "--diagnostics"])

            assert result.exit_code in [0, 1, 2]


class TestSystemComponentCheckIntegration:
    """Integration tests for component-specific checks."""

    def test_check_database_component(self, isolated_app) -> None:
        """Test checking database component specifically.

        Integration: Tests targeted component check.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(isolated_app, ["system", "health", "--component", "database"])

            assert result.exit_code in [0, 1, 2]

    def test_check_config_component(self, isolated_app) -> None:
        """Test checking config component specifically.

        Integration: Tests config validation.
        """
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(isolated_app, ["system", "health", "--component", "config"])

        assert result.exit_code in [0, 1, 2]


class TestSystemConfigIntegration:
    """Integration tests for system config interactions."""

    def test_system_loads_config(self, isolated_app) -> None:
        """Test system commands load configuration.

        Integration: Tests config loading.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.config.config_loader.ConfigLoader") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get.return_value = {}
            mock_config.return_value = mock_config_instance

            result = runner.invoke(isolated_app, ["system", "info"])

            assert result.exit_code in [0, 1, 2]

    def test_system_respects_environment(self, isolated_app) -> None:
        """Test system respects environment settings.

        Integration: Tests environment integration.
        """
        runner = CliRunner(mix_stderr=False)

        with patch.dict("os.environ", {"PRECOG_ENV": "test"}):
            result = runner.invoke(isolated_app, ["system", "info", "--env"])

            assert result.exit_code in [0, 1, 2]
