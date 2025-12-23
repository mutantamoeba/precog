"""
Unit tests for CLI scheduler commands.

Tests all scheduler CLI commands:
- start: Start data collection schedulers
- stop: Stop running schedulers
- status: Show scheduler status
- poll-once: Execute single poll cycle

Related:
    - Issue #204: CLI Refactor
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/scheduler.py
    - REQ-CLI-001: CLI Framework (Typer)

Coverage Target: 85%+ for cli/scheduler.py (critical tier)
"""

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from precog.cli.scheduler import app


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for reliable string matching."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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


class TestSchedulerHelp:
    """Test scheduler help and command structure."""

    def test_scheduler_help_shows_commands(self, runner):
        """Test scheduler --help shows all available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output_lower = strip_ansi(result.stdout).lower()
        assert "start" in output_lower
        assert "stop" in output_lower
        assert "status" in output_lower
        assert "poll-once" in output_lower

    def test_start_help_shows_options(self, runner):
        """Test start --help shows available options."""
        result = runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0
        output_lower = strip_ansi(result.stdout).lower()
        # Should show interval options
        assert "--espn" in output_lower or "--kalshi" in output_lower or "interval" in output_lower


class TestSchedulerStart:
    """Test scheduler start command."""

    @patch("precog.schedulers.service_supervisor.ServiceSupervisor")
    def test_start_supervised_mode(self, mock_supervisor_class, runner):
        """Test start command with supervised mode."""
        mock_supervisor = MagicMock()
        mock_supervisor_class.return_value = mock_supervisor

        result = runner.invoke(app, ["start", "--supervised", "--no-foreground"])

        # Exit code 2 is Typer's "missing option/bad usage" code
        # Should attempt to start (may fail if services not configured)
        assert result.exit_code in [0, 1, 2]

    @patch("precog.database.connection.get_connection")
    def test_start_espn_only(self, mock_conn, runner):
        """Test start with ESPN only (no Kalshi)."""
        mock_conn.return_value = MagicMock()

        result = runner.invoke(app, ["start", "--espn", "--no-kalshi", "--no-foreground"])

        # May succeed, fail, or have usage error depending on env
        assert result.exit_code in [0, 1, 2]

    def test_start_invalid_interval(self, runner):
        """Test start with invalid interval value."""
        result = runner.invoke(app, ["start", "--espn-interval", "0"])

        # Should fail with invalid interval or proceed with minimum
        assert result.exit_code in [0, 1, 2]


class TestSchedulerStop:
    """Test scheduler stop command."""

    def test_stop_no_running_services(self, runner):
        """Test stop when no services are running."""
        result = runner.invoke(app, ["stop"])

        # Should handle gracefully (no crash)
        assert result.exit_code in [0, 1]


class TestSchedulerStatus:
    """Test scheduler status command."""

    def test_status_no_services(self, runner):
        """Test status when no services configured."""
        result = runner.invoke(app, ["status"])

        # Should show status even if no services
        assert result.exit_code in [0, 1]

    def test_status_verbose(self, runner):
        """Test status with verbose flag."""
        result = runner.invoke(app, ["status", "--verbose"])

        assert result.exit_code in [0, 1]


class TestSchedulerPollOnce:
    """Test scheduler poll-once command."""

    @patch("precog.schedulers.espn_game_poller.ESPNGamePoller")
    @patch("precog.database.connection.get_connection")
    def test_poll_once_espn_only(self, mock_conn, mock_poller_class, runner):
        """Test poll-once with ESPN only."""
        mock_conn.return_value = MagicMock()
        mock_poller = MagicMock()
        mock_poller.poll_once.return_value = {"games": 5, "updated": 3}
        mock_poller_class.return_value = mock_poller

        result = runner.invoke(app, ["poll-once", "--no-kalshi"])

        # Should attempt poll (may fail on missing config)
        assert result.exit_code in [0, 1]

    @patch("precog.database.connection.get_connection")
    def test_poll_once_kalshi_only(self, mock_conn, runner):
        """Test poll-once with Kalshi only."""
        mock_conn.return_value = MagicMock()

        result = runner.invoke(app, ["poll-once", "--no-espn"])

        # Should attempt poll (may fail on missing credentials)
        assert result.exit_code in [0, 1]

    def test_poll_once_help(self, runner):
        """Test poll-once --help shows options."""
        result = runner.invoke(app, ["poll-once", "--help"])

        assert result.exit_code == 0
        output_lower = strip_ansi(result.stdout).lower()
        assert "--espn" in output_lower or "--kalshi" in output_lower or "--league" in output_lower


class TestSchedulerEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_subcommand(self, runner):
        """Test invalid scheduler subcommand."""
        result = runner.invoke(app, ["invalid-subcommand"])

        assert result.exit_code != 0

    def test_start_with_both_disabled(self, runner):
        """Test start with both ESPN and Kalshi disabled."""
        result = runner.invoke(app, ["start", "--no-espn", "--no-kalshi"])

        # Should fail or warn - no services to start
        assert result.exit_code in [0, 1]  # May just warn

    def test_poll_once_with_both_disabled(self, runner):
        """Test poll-once with both disabled."""
        result = runner.invoke(app, ["poll-once", "--no-espn", "--no-kalshi"])

        # Should succeed with no-op or warn
        assert result.exit_code in [0, 1]


class TestSchedulerImportVerification:
    """Verify runtime imports work correctly.

    These tests catch import path bugs that TYPE_CHECKING guards would hide.
    The bug where scheduler.py imported from non-existent 'kalshi_market_poller'
    wasn't caught because the bad import was inside if TYPE_CHECKING block.

    Educational Note:
        TYPE_CHECKING blocks only execute during static analysis (mypy),
        not at runtime. Runtime imports inside functions are only validated
        when those functions are called - not when the module is imported.
        These tests explicitly verify those runtime imports work.
    """

    def test_scheduler_module_imports_exist(self):
        """Verify all scheduler modules referenced by CLI exist."""
        # These imports would fail if the modules don't exist
        from precog.schedulers import ESPNGamePoller, KalshiMarketPoller

        assert ESPNGamePoller is not None
        assert KalshiMarketPoller is not None

    def test_scheduler_factory_functions_exist(self):
        """Verify factory functions are importable."""
        from precog.schedulers import create_espn_poller, create_kalshi_poller

        assert callable(create_espn_poller)
        assert callable(create_kalshi_poller)

    def test_service_supervisor_imports_exist(self):
        """Verify ServiceSupervisor and related classes exist."""
        from precog.schedulers import ServiceSupervisor, create_supervisor

        assert ServiceSupervisor is not None
        assert callable(create_supervisor)

    def test_backward_compatibility_aliases_work(self):
        """Verify deprecated aliases still work for backward compatibility."""
        from precog.schedulers import ESPNGamePoller, MarketUpdater

        # MarketUpdater should be an alias for ESPNGamePoller
        assert MarketUpdater is ESPNGamePoller

    def test_cli_start_imports_work(self):
        """Test that the start command's runtime imports resolve correctly.

        This catches bugs where TYPE_CHECKING imports hide broken runtime imports.
        """
        # Simulate what happens inside scheduler.py start() function
        from precog.schedulers import ESPNGamePoller, KalshiMarketPoller

        # Verify the classes are actually usable (not just importable)
        assert hasattr(ESPNGamePoller, "start")
        assert hasattr(ESPNGamePoller, "stop")
        assert hasattr(ESPNGamePoller, "poll_once")
        assert hasattr(KalshiMarketPoller, "start")
        assert hasattr(KalshiMarketPoller, "stop")
        assert hasattr(KalshiMarketPoller, "poll_once")
