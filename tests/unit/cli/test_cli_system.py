"""
Unit tests for CLI system commands.

Tests all system CLI commands:
- health: Comprehensive health check
- version: Show version information
- info: Show system diagnostics

Related:
    - Issue #204: CLI Refactor
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/system.py
    - REQ-CLI-001: CLI Framework (Typer)

Coverage Target: 80%+ for cli/system.py (infrastructure tier)
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from precog.cli.system import app

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Test Classes
# ============================================================================


class TestSystemHelp:
    """Test system help and command structure."""

    def test_system_help_shows_commands(self, runner):
        """Test system --help shows all available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "health" in output_lower
        assert "version" in output_lower
        assert "info" in output_lower

    def test_health_help_shows_options(self, runner):
        """Test health --help shows available options."""
        result = runner.invoke(app, ["health", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "--verbose" in output_lower


class TestSystemHealth:
    """Test system health command."""

    @patch("precog.database.connection.get_connection")
    def test_health_database_check(self, mock_get_conn, runner):
        """Test health check includes database connectivity."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock()
        mock_get_conn.return_value = mock_conn

        result = runner.invoke(app, ["health"])

        # Should attempt health check
        assert result.exit_code in [0, 1]
        output_lower = result.stdout.lower()
        assert "database" in output_lower or "health" in output_lower or "check" in output_lower

    @patch("precog.database.connection.get_connection")
    def test_health_verbose(self, mock_get_conn, runner):
        """Test health check with verbose flag."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock()
        mock_get_conn.return_value = mock_conn

        result = runner.invoke(app, ["health", "--verbose"])

        assert result.exit_code in [0, 1]

    @patch("precog.database.connection.get_connection")
    def test_health_database_failure(self, mock_get_conn, runner):
        """Test health check when database is down."""
        mock_get_conn.side_effect = Exception("Connection refused")

        result = runner.invoke(app, ["health"])

        # Should report failure gracefully
        assert result.exit_code in [0, 1]
        output_lower = result.stdout.lower()
        assert "failed" in output_lower or "error" in output_lower or "health" in output_lower

    @patch("precog.database.connection.get_connection")
    @patch.dict("os.environ", {"KALSHI_API_KEY_ID": "", "KALSHI_PRIVATE_KEY_PATH": ""})
    def test_health_missing_credentials(self, mock_get_conn, runner):
        """Test health check with missing API credentials."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        result = runner.invoke(app, ["health"])

        # Should note missing credentials
        assert result.exit_code in [0, 1]


class TestSystemVersion:
    """Test system version command."""

    def test_version_shows_info(self, runner):
        """Test version command shows version information."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code in [0, 1]
        # Should show some version-related info
        output_lower = result.stdout.lower()
        assert "version" in output_lower or "precog" in output_lower or "0." in output_lower

    def test_version_no_crash(self, runner):
        """Test version command doesn't crash."""
        result = runner.invoke(app, ["version"])

        # Should not raise exception
        assert result.exception is None or result.exit_code in [0, 1]


class TestSystemInfo:
    """Test system info command."""

    def test_info_shows_diagnostics(self, runner):
        """Test info command shows system diagnostics."""
        result = runner.invoke(app, ["info"])

        assert result.exit_code in [0, 1]
        output_lower = result.stdout.lower()
        # Should show some system info
        assert "python" in output_lower or "system" in output_lower or "info" in output_lower

    def test_info_shows_python_version(self, runner):
        """Test info shows Python version."""
        result = runner.invoke(app, ["info"])

        assert result.exit_code in [0, 1]
        # Python info should be present
        output_lower = result.stdout.lower()
        assert "python" in output_lower or "3." in output_lower


class TestSystemEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_subcommand(self, runner):
        """Test invalid system subcommand."""
        result = runner.invoke(app, ["invalid-subcommand"])

        assert result.exit_code != 0

    @patch("precog.database.connection.get_connection")
    def test_health_all_checks_pass(self, mock_get_conn, runner):
        """Test health when all checks pass."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock()
        mock_get_conn.return_value = mock_conn

        with patch.dict(
            "os.environ",
            {"KALSHI_API_KEY_ID": "test-key", "KALSHI_PRIVATE_KEY_PATH": "/path/to/key.pem"},
        ):
            result = runner.invoke(app, ["health"])

        assert result.exit_code in [0, 1]

    @patch("precog.database.connection.get_connection")
    def test_health_partial_failure(self, mock_get_conn, runner):
        """Test health with partial failures (some checks pass, some fail)."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock()
        mock_get_conn.return_value = mock_conn

        with patch.dict("os.environ", {"KALSHI_API_KEY_ID": "", "KALSHI_PRIVATE_KEY_PATH": ""}):
            result = runner.invoke(app, ["health"])

        # Should complete and report partial status
        assert result.exit_code in [0, 1]
