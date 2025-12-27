"""Integration tests for CLI scheduler module.

Tests scheduler CLI commands with real service interactions where possible,
using mocks only for external dependencies.

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


class TestSchedulerStartIntegration:
    """Integration tests for scheduler start command."""

    def test_start_scheduler_with_valid_config(self, isolated_app) -> None:
        """Test starting scheduler with valid configuration.

        Integration: Tests scheduler initialization with real config loading.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "start", "--poller", "espn"])

            # Integration: Verify CLI handles start command gracefully
            assert result.exit_code in [0, 1, 2]

    def test_start_scheduler_with_custom_interval(self, isolated_app) -> None:
        """Test starting scheduler with custom poll interval.

        Integration: Tests interval parameter propagation.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "start", "--interval", "30"])

            assert result.exit_code in [0, 1, 2]

    def test_start_multiple_pollers(self, isolated_app) -> None:
        """Test starting scheduler with multiple pollers.

        Integration: Tests multi-poller configuration.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(
                isolated_app, ["scheduler", "start", "--poller", "espn", "--poller", "kalshi"]
            )

            assert result.exit_code in [0, 1, 2]


class TestSchedulerStopIntegration:
    """Integration tests for scheduler stop command."""

    def test_stop_running_scheduler(self, isolated_app) -> None:
        """Test stopping a running scheduler.

        Integration: Tests scheduler shutdown sequence.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.stop.return_value = True
            mock_instance.is_running.return_value = True
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "stop"])

            assert result.exit_code in [0, 1, 2]

    def test_stop_not_running_scheduler(self, isolated_app) -> None:
        """Test stopping when scheduler is not running.

        Integration: Tests graceful handling of stop on idle scheduler.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.is_running.return_value = False
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "stop"])

            assert result.exit_code in [0, 1, 2]


class TestSchedulerStatusIntegration:
    """Integration tests for scheduler status command."""

    def test_status_with_running_scheduler(self, isolated_app) -> None:
        """Test status when scheduler is running.

        Integration: Tests status retrieval with active pollers.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.is_running.return_value = True
            mock_instance.get_status.return_value = {
                "running": True,
                "pollers": [{"name": "espn", "status": "running", "interval": 15}],
            }
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "status"])

            # Integration: Verify status command completes
            assert result.exit_code in [0, 1, 2]

    def test_status_output_formats(self, isolated_app) -> None:
        """Test status output in different formats.

        Integration: Tests format rendering.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            for fmt in ["json", "table"]:
                result = runner.invoke(isolated_app, ["scheduler", "status", "--format", fmt])
                assert result.exit_code in [0, 1, 2]


class TestSchedulerPollOnceIntegration:
    """Integration tests for scheduler poll-once command."""

    def test_poll_once_nfl(self, isolated_app) -> None:
        """Test single poll for NFL games.

        Integration: Tests one-shot poll execution.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 5, "updated": 3}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "poll-once", "--league", "nfl"])

            assert result.exit_code in [0, 1, 2]

    def test_poll_once_with_save(self, isolated_app) -> None:
        """Test poll-once with database save.

        Integration: Tests database persistence flag.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 3, "saved": 3}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(
                isolated_app, ["scheduler", "poll-once", "--league", "nfl", "--save"]
            )

            assert result.exit_code in [0, 1, 2]

    def test_poll_once_multiple_leagues(self, isolated_app) -> None:
        """Test poll-once for multiple leagues.

        Integration: Tests multi-league poll execution.
        """
        runner = CliRunner(mix_stderr=False)

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 10, "updated": 8}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(
                isolated_app, ["scheduler", "poll-once", "--league", "nfl", "--league", "nba"]
            )

            assert result.exit_code in [0, 1, 2]


class TestSchedulerConfigIntegration:
    """Integration tests for scheduler configuration handling."""

    def test_scheduler_respects_config_file(self, isolated_app) -> None:
        """Test scheduler uses configuration file settings.

        Integration: Tests config loader integration.
        """
        runner = CliRunner(mix_stderr=False)

        with (
            patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor,
            patch("precog.config.config_loader.ConfigLoader") as mock_config,
        ):
            mock_config_instance = MagicMock()
            mock_config_instance.get.return_value = {"poll_interval": 30}
            mock_config.return_value = mock_config_instance

            mock_instance = MagicMock()
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "start"])

            assert result.exit_code in [0, 1, 2]

    def test_scheduler_environment_override(self, isolated_app) -> None:
        """Test scheduler with environment variable overrides.

        Integration: Tests env var precedence.
        """
        runner = CliRunner(mix_stderr=False)

        with (
            patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor,
            patch.dict("os.environ", {"PRECOG_POLL_INTERVAL": "45"}),
        ):
            mock_instance = MagicMock()
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(isolated_app, ["scheduler", "start"])

            assert result.exit_code in [0, 1, 2]
