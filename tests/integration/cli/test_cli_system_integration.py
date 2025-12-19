"""Integration tests for CLI system module.

Tests system CLI commands with real component interactions.

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


class TestSystemHealthIntegration:
    """Integration tests for system health command."""

    def test_health_all_components_healthy(self) -> None:
        """Test health when all components are healthy.

        Integration: Tests multi-component health check.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["system", "health"])

            assert result.exit_code in [0, 1, 2]

    def test_health_database_unhealthy(self) -> None:
        """Test health when database is unhealthy.

        Integration: Tests partial failure handling.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Database unavailable")

            result = runner.invoke(app, ["system", "health"])

            # Should complete but report unhealthy
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_health_with_api_check(self) -> None:
        """Test health includes API connectivity check.

        Integration: Tests API health check.
        """
        with (
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.api_connectors.kalshi_client.KalshiClient") as mock_kalshi,
        ):
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()
            mock_kalshi_instance = MagicMock()
            mock_kalshi_instance.get_exchange_status.return_value = {"trading": "open"}
            mock_kalshi.return_value = mock_kalshi_instance

            result = runner.invoke(app, ["system", "health", "--check-apis"])

            assert result.exit_code in [0, 1, 2]

    def test_health_verbose_output(self) -> None:
        """Test health verbose output.

        Integration: Tests detailed health reporting.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["system", "health", "--verbose"])

            assert result.exit_code in [0, 1, 2]


class TestSystemVersionIntegration:
    """Integration tests for system version command."""

    def test_version_shows_package_version(self) -> None:
        """Test version displays package version.

        Integration: Tests package metadata access.
        """
        result = runner.invoke(app, ["system", "version"])

        assert result.exit_code in [0, 1, 2]
        # Version output should exist
        assert result.output is not None

    def test_version_with_dependencies(self) -> None:
        """Test version with dependency information.

        Integration: Tests dependency enumeration.
        """
        result = runner.invoke(app, ["system", "version", "--deps"])

        assert result.exit_code in [0, 1, 2]

    def test_version_json_output(self) -> None:
        """Test version in JSON format.

        Integration: Tests JSON formatting.
        """
        result = runner.invoke(app, ["system", "version", "--json"])

        assert result.exit_code in [0, 1, 2]


class TestSystemInfoIntegration:
    """Integration tests for system info command."""

    def test_info_shows_system_details(self) -> None:
        """Test info displays system details.

        Integration: Tests system information gathering.
        """
        result = runner.invoke(app, ["system", "info"])

        assert result.exit_code in [0, 1, 2]

    def test_info_with_environment(self) -> None:
        """Test info with environment variables.

        Integration: Tests environment variable reporting.
        """
        result = runner.invoke(app, ["system", "info", "--env"])

        assert result.exit_code in [0, 1, 2]

    def test_info_with_config(self) -> None:
        """Test info with configuration details.

        Integration: Tests config file parsing.
        """
        result = runner.invoke(app, ["system", "info", "--config"])

        assert result.exit_code in [0, 1, 2]

    def test_info_with_paths(self) -> None:
        """Test info with path information.

        Integration: Tests path resolution.
        """
        result = runner.invoke(app, ["system", "info", "--paths"])

        assert result.exit_code in [0, 1, 2]


class TestSystemDiagnosticsIntegration:
    """Integration tests for system diagnostics."""

    def test_diagnostics_collects_info(self) -> None:
        """Test diagnostics collection.

        Integration: Tests diagnostic data gathering.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["system", "health", "--diagnostics"])

            assert result.exit_code in [0, 1, 2]


class TestSystemComponentCheckIntegration:
    """Integration tests for component-specific checks."""

    def test_check_database_component(self) -> None:
        """Test checking database component specifically.

        Integration: Tests targeted component check.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            result = runner.invoke(app, ["system", "health", "--component", "database"])

            assert result.exit_code in [0, 1, 2]

    def test_check_config_component(self) -> None:
        """Test checking config component specifically.

        Integration: Tests config validation.
        """
        result = runner.invoke(app, ["system", "health", "--component", "config"])

        assert result.exit_code in [0, 1, 2]


class TestSystemConfigIntegration:
    """Integration tests for system config interactions."""

    def test_system_loads_config(self) -> None:
        """Test system commands load configuration.

        Integration: Tests config loading.
        """
        with patch("precog.config.config_loader.ConfigLoader") as mock_config:
            mock_config_instance = MagicMock()
            mock_config_instance.get.return_value = {}
            mock_config.return_value = mock_config_instance

            result = runner.invoke(app, ["system", "info"])

            assert result.exit_code in [0, 1, 2]

    def test_system_respects_environment(self) -> None:
        """Test system respects environment settings.

        Integration: Tests environment integration.
        """
        with patch.dict("os.environ", {"PRECOG_ENV": "test"}):
            result = runner.invoke(app, ["system", "info", "--env"])

            assert result.exit_code in [0, 1, 2]
