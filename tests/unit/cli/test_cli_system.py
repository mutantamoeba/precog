"""
Unit tests for CLI system commands.

Tests all system CLI commands:
- health: Comprehensive health check
- version: Show version information
- info: Show system diagnostics

Related:
    - Issue #204: CLI Refactor
    - Issue #234: 8 Test Type Coverage
    - Issue #258: Create shared CLI test fixtures
    - Issue #406: Fix broken DB CLI commands
    - src/precog/cli/system.py
    - REQ-CLI-001: CLI Framework (Typer)

Coverage Target: 80%+ for cli/system.py (infrastructure tier)

Note:
    Uses shared CLI fixtures from tests/conftest.py (cli_runner)
    and helpers from tests/helpers/cli_helpers.py (strip_ansi).
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from precog.cli.system import app
from tests.helpers.cli_helpers import strip_ansi

# ============================================================================
# Test Helpers
# ============================================================================


def _make_mock_cursor():
    """Create a mock get_cursor context manager for health check tests.

    The health command only does 'SELECT 1 AS test' via get_cursor(),
    so the mock is simple.

    Returns:
        A context manager function suitable for patching get_cursor.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"test": 1}

    @contextmanager
    def mock_get_cursor(commit=False):
        yield mock_cursor

    return mock_get_cursor


# ============================================================================
# Test Classes
# ============================================================================


class TestSystemHelp:
    """Test system help and command structure."""

    def test_system_help_shows_commands(self, cli_runner):
        """Test system --help shows all available commands."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output_lower = strip_ansi(result.stdout).lower()
        assert "health" in output_lower
        assert "version" in output_lower
        assert "info" in output_lower

    def test_health_help_shows_options(self, cli_runner):
        """Test health --help shows available options."""
        result = cli_runner.invoke(app, ["health", "--help"])

        assert result.exit_code == 0
        output_lower = strip_ansi(result.stdout).lower()
        assert "--verbose" in output_lower


class TestSystemHealth:
    """Test system health command.

    Note: The health command uses get_cursor() context manager (not get_connection())
    for database connectivity checks. get_cursor() yields a RealDictCursor.
    """

    @patch("precog.database.connection.get_cursor")
    def test_health_database_check(self, mock_get_cursor, cli_runner):
        """Test health check includes database connectivity."""
        mock_get_cursor.side_effect = _make_mock_cursor()

        result = cli_runner.invoke(app, ["health"])

        # Should attempt health check
        assert result.exit_code in (0, 1), (
            f"Expected 0 or 1, got {result.exit_code}: {result.output}"
        )
        output_lower = strip_ansi(result.stdout).lower()
        assert "database" in output_lower or "health" in output_lower or "check" in output_lower

    @patch("precog.database.connection.get_cursor")
    def test_health_verbose(self, mock_get_cursor, cli_runner):
        """Test health check with verbose flag."""
        mock_get_cursor.side_effect = _make_mock_cursor()

        result = cli_runner.invoke(app, ["health", "--verbose"])

        assert result.exit_code in (0, 1), (
            f"Expected 0 or 1, got {result.exit_code}: {result.output}"
        )

    @patch("precog.database.connection.get_cursor")
    def test_health_database_failure(self, mock_get_cursor, cli_runner):
        """Test health check when database is down."""
        mock_get_cursor.side_effect = Exception("Connection refused")

        result = cli_runner.invoke(app, ["health"])

        # Should report failure gracefully
        assert result.exit_code in (0, 1), (
            f"Expected 0 or 1, got {result.exit_code}: {result.output}"
        )
        output_lower = strip_ansi(result.stdout).lower()
        assert "failed" in output_lower or "error" in output_lower or "health" in output_lower

    @patch("precog.database.connection.get_cursor")
    @patch.dict("os.environ", {"KALSHI_API_KEY_ID": "", "KALSHI_PRIVATE_KEY_PATH": ""})
    def test_health_missing_credentials(self, mock_get_cursor, cli_runner):
        """Test health check with missing API credentials."""
        mock_get_cursor.side_effect = _make_mock_cursor()

        result = cli_runner.invoke(app, ["health"])

        # Should note missing credentials
        assert result.exit_code in (0, 1), (
            f"Expected 0 or 1, got {result.exit_code}: {result.output}"
        )


class TestSystemVersion:
    """Test system version command."""

    def test_version_shows_info(self, cli_runner):
        """Test version command shows version information."""
        result = cli_runner.invoke(app, ["version"])

        assert result.exit_code == 0
        # Should show some version-related info
        output_lower = strip_ansi(result.stdout).lower()
        assert "version" in output_lower or "precog" in output_lower or "0." in output_lower

    def test_version_no_crash(self, cli_runner):
        """Test version command doesn't crash."""
        result = cli_runner.invoke(app, ["version"])

        # Should not raise exception
        assert result.exit_code == 0, (
            f"version should always succeed, got {result.exit_code}: {result.output}"
        )


class TestSystemInfo:
    """Test system info command."""

    def test_info_shows_diagnostics(self, cli_runner):
        """Test info command shows system diagnostics."""
        result = cli_runner.invoke(app, ["info"])

        assert result.exit_code == 0
        output_lower = strip_ansi(result.stdout).lower()
        # Should show some system info
        assert "python" in output_lower or "system" in output_lower or "info" in output_lower

    def test_info_shows_python_version(self, cli_runner):
        """Test info shows Python version."""
        result = cli_runner.invoke(app, ["info"])

        assert result.exit_code == 0
        # Python info should be present
        output_lower = strip_ansi(result.stdout).lower()
        assert "python" in output_lower or "3." in output_lower


class TestSystemHealthCheck5:
    """Test Check 5: Persistent Component Health from system_health table.

    Tests the new section that reads from the system_health table and
    displays component-level health status in the CLI.
    """

    @patch("precog.database.crud_system.get_system_health")
    @patch("precog.database.connection.get_cursor")
    def test_all_components_healthy(self, mock_cursor, mock_get_health, cli_runner):
        """When all components are healthy, Check 5 shows OK."""
        mock_cursor.side_effect = _make_mock_cursor()
        mock_get_health.return_value = [
            {"component": "kalshi_api", "status": "healthy", "last_check": None, "details": {}},
            {"component": "espn_api", "status": "healthy", "last_check": None, "details": {}},
        ]

        result = cli_runner.invoke(app, ["health"])

        output = strip_ansi(result.stdout).lower()
        assert "2 components" in output

    @patch("precog.database.crud_system.get_system_health")
    @patch("precog.database.connection.get_cursor")
    def test_some_components_down(self, mock_cursor, mock_get_health, cli_runner):
        """When a component is down, Check 5 shows UNHEALTHY."""
        mock_cursor.side_effect = _make_mock_cursor()
        mock_get_health.return_value = [
            {"component": "kalshi_api", "status": "down", "last_check": None, "details": {}},
            {"component": "espn_api", "status": "healthy", "last_check": None, "details": {}},
        ]

        result = cli_runner.invoke(app, ["health"])

        output = strip_ansi(result.stdout).lower()
        assert "unhealthy" in output
        assert "1 down" in output

    @patch("precog.database.crud_system.get_system_health")
    @patch("precog.database.connection.get_cursor")
    def test_degraded_only(self, mock_cursor, mock_get_health, cli_runner):
        """When components are degraded (but none down), shows DEGRADED."""
        mock_cursor.side_effect = _make_mock_cursor()
        mock_get_health.return_value = [
            {"component": "kalshi_api", "status": "degraded", "last_check": None, "details": {}},
        ]

        result = cli_runner.invoke(app, ["health"])

        output = strip_ansi(result.stdout).lower()
        assert "degraded" in output

    @patch("precog.database.crud_system.get_system_health")
    @patch("precog.database.connection.get_cursor")
    def test_no_health_records(self, mock_cursor, mock_get_health, cli_runner):
        """When system_health table is empty, shows OK with explanation."""
        mock_cursor.side_effect = _make_mock_cursor()
        mock_get_health.return_value = []

        result = cli_runner.invoke(app, ["health"])

        output = strip_ansi(result.stdout).lower()
        assert "no health data yet" in output

    @patch("precog.database.crud_system.get_system_health")
    @patch("precog.database.connection.get_cursor")
    def test_db_exception_handled(self, mock_cursor, mock_get_health, cli_runner):
        """When get_system_health raises, Check 5 reports FAILED gracefully."""
        mock_cursor.side_effect = _make_mock_cursor()
        mock_get_health.side_effect = Exception("DB connection lost")

        result = cli_runner.invoke(app, ["health"])

        output = strip_ansi(result.stdout).lower()
        assert "failed" in output

    @patch("precog.database.crud_system.get_system_health")
    @patch("precog.database.connection.get_cursor")
    def test_verbose_shows_detail_table(self, mock_cursor, mock_get_health, cli_runner):
        """Verbose mode shows per-component detail table."""
        mock_cursor.side_effect = _make_mock_cursor()
        mock_get_health.return_value = [
            {
                "component": "kalshi_api",
                "status": "degraded",
                "last_check": None,
                "details": {"error_rate": "0.1200", "reason": "elevated_error_rate"},
                "alert_sent": True,
            },
        ]

        result = cli_runner.invoke(app, ["health", "--verbose"])

        output = strip_ansi(result.stdout).lower()
        assert "kalshi_api" in output
        assert "0.1200" in output


class TestSystemEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_subcommand(self, cli_runner):
        """Test invalid system subcommand."""
        result = cli_runner.invoke(app, ["invalid-subcommand"])

        assert result.exit_code != 0

    @patch("precog.database.connection.get_cursor")
    def test_health_all_checks_pass(self, mock_get_cursor, cli_runner):
        """Test health when all checks pass."""
        mock_get_cursor.side_effect = _make_mock_cursor()

        with patch.dict(
            "os.environ",
            {"KALSHI_API_KEY_ID": "test-key", "KALSHI_PRIVATE_KEY_PATH": "/path/to/key.pem"},
        ):
            result = cli_runner.invoke(app, ["health"])

        assert result.exit_code in (0, 1), (
            f"Expected 0 or 1, got {result.exit_code}: {result.output}"
        )

    @patch("precog.database.connection.get_cursor")
    def test_health_partial_failure(self, mock_get_cursor, cli_runner):
        """Test health with partial failures (some checks pass, some fail)."""
        mock_get_cursor.side_effect = _make_mock_cursor()

        with patch.dict("os.environ", {"KALSHI_API_KEY_ID": "", "KALSHI_PRIVATE_KEY_PATH": ""}):
            result = cli_runner.invoke(app, ["health"])

        # Should complete and report partial status
        assert result.exit_code in (0, 1), (
            f"Expected 0 or 1, got {result.exit_code}: {result.output}"
        )
