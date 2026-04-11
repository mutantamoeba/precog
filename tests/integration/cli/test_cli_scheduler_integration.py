"""Integration tests for CLI scheduler module.

Tests scheduler CLI commands with real service interactions where possible,
using mocks only for external dependencies.

References:
    - REQ-TEST-003: Integration testing with testcontainers
    - TESTING_STRATEGY V3.2: 8 test types required
    - Issue #764: scheduler CLI factory-vs-class mock anti-pattern

Mock Level Notes (#764):
    The CLI's ``scheduler start`` supervised path calls the
    ``create_supervisor`` factory function, not the
    ``ServiceSupervisor`` class directly. The factory itself
    constructs real Kalshi and ESPN pollers, rate limiters, and
    circuit breakers before instantiating the supervisor. Patching
    ``ServiceSupervisor`` the class is the wrong level of indirection
    -- it leaves all of the real poller setup intact, which means
    real network calls fire on every test. The factory is the
    correct mock target.

    For ``status``, the CLI does NOT call create_supervisor at all;
    it calls ``_show_db_backed_status`` which queries the
    ``scheduler_status`` table via
    ``precog.database.crud_schedulers.list_scheduler_services``. To
    keep ``status`` tests hermetic we patch
    ``_show_db_backed_status`` directly.

    For ``poll-once``, the CLI imports ``ESPNGamePoller`` and
    ``KalshiMarketPoller`` from ``precog.schedulers`` at function-call
    time and instantiates them directly -- it does not go through
    ``create_supervisor``. We patch the package-level re-exports.

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


def _make_supervised_mock_supervisor() -> MagicMock:
    """Build a supervisor mock that behaves correctly in non-foreground mode."""
    mock_supervisor = MagicMock()
    mock_supervisor.is_running = True
    mock_supervisor.start_all.return_value = None
    mock_supervisor.stop_all.return_value = None
    mock_supervisor.get_aggregate_metrics.return_value = {
        "uptime_seconds": 0,
        "services_healthy": 1,
        "services_total": 1,
        "total_restarts": 0,
        "total_errors": 0,
        "per_service": {},
    }
    return mock_supervisor


class TestSchedulerStartIntegration:
    """Integration tests for scheduler start command (supervised path)."""

    def test_start_scheduler_with_valid_config(self, isolated_app) -> None:
        """Test starting scheduler with valid configuration via supervised path."""
        runner = CliRunner()

        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock_supervisor()

            result = runner.invoke(
                isolated_app,
                ["scheduler", "start", "--supervised", "--no-espn"],
            )

            assert result.exit_code == 0, (
                f"start should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()

    def test_start_scheduler_with_custom_interval(self, isolated_app) -> None:
        """Test starting scheduler with custom poll interval via supervised path.

        Verifies the ``--kalshi-interval`` value propagates to the
        ``create_supervisor`` factory as ``kalshi_poll_interval``.
        """
        runner = CliRunner()

        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock_supervisor()

            result = runner.invoke(
                isolated_app,
                [
                    "scheduler",
                    "start",
                    "--supervised",
                    "--no-espn",
                    "--kalshi-interval",
                    "30",
                ],
            )

            assert result.exit_code == 0, (
                f"start should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()
            call_kwargs = mock_create_supervisor.call_args.kwargs
            assert call_kwargs.get("kalshi_poll_interval") == 30

    def test_start_multiple_pollers(self, isolated_app) -> None:
        """Test starting scheduler with multiple pollers (ESPN + Kalshi)."""
        runner = CliRunner()

        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock_supervisor()

            result = runner.invoke(
                isolated_app,
                ["scheduler", "start", "--supervised"],
            )

            assert result.exit_code == 0, (
                f"start should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()
            call_kwargs = mock_create_supervisor.call_args.kwargs
            assert call_kwargs.get("enabled_services") == {"espn", "kalshi_rest"}


class TestSchedulerStopIntegration:
    """Integration tests for scheduler stop command.

    Note: ``scheduler stop`` accesses module-global references in
    ``precog.cli.scheduler`` (``_supervisor``, ``_espn_updater``,
    ``_kalshi_poller``). With no prior start, those are None and stop
    is a no-op -- no real I/O. We don't need supervisor mocks here;
    we test the no-op happy path behavior.
    """

    def test_stop_running_scheduler(self, isolated_app) -> None:
        """Test stopping a scheduler that has a supervisor in module state.

        Pre-populates the module-global ``_supervisor`` so stop has
        something to stop. Asserts the supervisor's ``stop_all`` was
        called -- the actual contract of the stop command in
        supervised mode.
        """
        from precog.cli import scheduler as scheduler_module

        mock_supervisor = MagicMock()
        mock_supervisor.is_running = True
        mock_supervisor.stop_all.return_value = None
        mock_supervisor.get_aggregate_metrics.return_value = {
            "uptime_seconds": 5,
            "total_restarts": 0,
            "total_errors": 0,
        }

        original_supervisor = scheduler_module._supervisor
        scheduler_module._supervisor = mock_supervisor
        try:
            runner = CliRunner()
            result = runner.invoke(isolated_app, ["scheduler", "stop"])

            assert result.exit_code == 0, (
                f"stop should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_supervisor.stop_all.assert_called_once()
        finally:
            scheduler_module._supervisor = original_supervisor

    def test_stop_not_running_scheduler(self, isolated_app) -> None:
        """Test stopping when scheduler is not running.

        With all module globals None, stop is a no-op and prints
        "No schedulers were running". Asserts exit code 0 and the
        no-op message.
        """
        from precog.cli import scheduler as scheduler_module

        # Force all globals to None to ensure clean no-op state.
        original_supervisor = scheduler_module._supervisor
        original_espn = scheduler_module._espn_updater
        original_kalshi = scheduler_module._kalshi_poller
        scheduler_module._supervisor = None
        scheduler_module._espn_updater = None
        scheduler_module._kalshi_poller = None
        try:
            runner = CliRunner()
            result = runner.invoke(isolated_app, ["scheduler", "stop"])

            assert result.exit_code == 0, (
                f"stop should exit 0; got {result.exit_code}: {result.output}"
            )
            assert "No schedulers were running" in result.output
        finally:
            scheduler_module._supervisor = original_supervisor
            scheduler_module._espn_updater = original_espn
            scheduler_module._kalshi_poller = original_kalshi


class TestSchedulerStatusIntegration:
    """Integration tests for scheduler status command.

    The ``status`` command does NOT call ``create_supervisor``. It
    calls ``_show_db_backed_status`` which queries
    ``list_scheduler_services``. We patch
    ``_show_db_backed_status`` directly so the test is hermetic.
    """

    def test_status_with_running_scheduler(self, isolated_app) -> None:
        """Test status when database reports a running scheduler service."""
        runner = CliRunner()

        with patch("precog.cli.scheduler._show_db_backed_status", return_value=True) as mock_status:
            result = runner.invoke(isolated_app, ["scheduler", "status"])

            assert result.exit_code == 0, (
                f"status should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_status.assert_called_once()

    def test_status_falls_back_to_in_process(self, isolated_app) -> None:
        """Test status falls back to in-process check when DB has no entries.

        Replaces the original ``test_status_output_formats`` test, which
        was passing ``--format`` -- a flag the status command does not
        accept. The original test exercised only the Typer parser
        rejecting an unknown option, with mocks that never ran.
        """
        runner = CliRunner()

        with patch(
            "precog.cli.scheduler._show_db_backed_status", return_value=False
        ) as mock_status:
            result = runner.invoke(isolated_app, ["scheduler", "status"])

            assert result.exit_code == 0, (
                f"status should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_status.assert_called_once()


class TestSchedulerPollOnceIntegration:
    """Integration tests for scheduler poll-once command.

    poll-once instantiates ``ESPNGamePoller`` and
    ``KalshiMarketPoller`` directly -- it does not use the supervisor
    factory. Patch them at the package re-export path so the
    function-scoped imports inside ``poll_once`` pick up the mocks.
    """

    def test_poll_once_nfl(self, isolated_app) -> None:
        """Test single poll for NFL games."""
        runner = CliRunner()

        with (
            patch("precog.schedulers.ESPNGamePoller") as mock_espn_cls,
            patch("precog.schedulers.KalshiMarketPoller") as mock_kalshi_cls,
        ):
            mock_espn = MagicMock()
            mock_espn.poll_once.return_value = {
                "items_fetched": 5,
                "items_updated": 3,
            }
            mock_espn_cls.return_value = mock_espn

            mock_kalshi = MagicMock()
            mock_kalshi.poll_once.return_value = {
                "items_fetched": 10,
                "items_updated": 8,
                "items_created": 2,
            }
            mock_kalshi.kalshi_client = MagicMock()
            mock_kalshi_cls.return_value = mock_kalshi

            result = runner.invoke(
                isolated_app,
                ["scheduler", "poll-once", "--leagues", "nfl"],
            )

            assert result.exit_code == 0, (
                f"poll-once should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_espn.poll_once.assert_called_once()
            mock_kalshi.poll_once.assert_called_once()

    def test_poll_once_espn_only(self, isolated_app) -> None:
        """Test single poll for ESPN only (no Kalshi).

        Replaces the original ``test_poll_once_with_save`` test, which
        passed a ``--save`` flag the command does not accept.
        """
        runner = CliRunner()

        with (
            patch("precog.schedulers.ESPNGamePoller") as mock_espn_cls,
            patch("precog.schedulers.KalshiMarketPoller") as mock_kalshi_cls,
        ):
            mock_espn = MagicMock()
            mock_espn.poll_once.return_value = {
                "items_fetched": 3,
                "items_updated": 3,
            }
            mock_espn_cls.return_value = mock_espn

            result = runner.invoke(
                isolated_app,
                ["scheduler", "poll-once", "--leagues", "nfl", "--no-kalshi"],
            )

            assert result.exit_code == 0, (
                f"poll-once should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_espn.poll_once.assert_called_once()
            mock_kalshi_cls.assert_not_called()

    def test_poll_once_multiple_leagues(self, isolated_app) -> None:
        """Test poll-once for multiple leagues (single comma-separated arg)."""
        runner = CliRunner()

        with (
            patch("precog.schedulers.ESPNGamePoller") as mock_espn_cls,
            patch("precog.schedulers.KalshiMarketPoller") as mock_kalshi_cls,
        ):
            mock_espn = MagicMock()
            mock_espn.poll_once.return_value = {
                "items_fetched": 10,
                "items_updated": 8,
            }
            mock_espn_cls.return_value = mock_espn

            mock_kalshi = MagicMock()
            mock_kalshi.poll_once.return_value = {
                "items_fetched": 20,
                "items_updated": 12,
                "items_created": 3,
            }
            mock_kalshi.kalshi_client = MagicMock()
            mock_kalshi_cls.return_value = mock_kalshi

            result = runner.invoke(
                isolated_app,
                ["scheduler", "poll-once", "--leagues", "nfl,nba"],
            )

            assert result.exit_code == 0, (
                f"poll-once should exit 0; got {result.exit_code}: {result.output}"
            )
            # ESPNGamePoller should be constructed with both leagues
            call_kwargs = mock_espn_cls.call_args.kwargs
            assert call_kwargs.get("leagues") == ["nfl", "nba"]


class TestSchedulerConfigIntegration:
    """Integration tests for scheduler configuration handling."""

    def test_scheduler_respects_supervised_path(self, isolated_app) -> None:
        """Test the supervised path runs end-to-end via the factory.

        Replaces the original ``test_scheduler_respects_config_file``,
        which patched ``ServiceSupervisor`` (wrong level) AND
        ``ConfigLoader`` at a path that the CLI never imports. The
        original test was exercising only the Typer parser; the
        mocks were never reached.
        """
        runner = CliRunner()

        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock_supervisor()

            result = runner.invoke(
                isolated_app,
                ["scheduler", "start", "--supervised"],
            )

            assert result.exit_code == 0, (
                f"start should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()

    def test_scheduler_environment_override(self, isolated_app) -> None:
        """Test scheduler with environment variable overrides.

        Sets ``PRECOG_POLL_INTERVAL=45`` and verifies the supervised
        start still completes cleanly. The CLI does not currently
        consume this env var (it would have to thread through Typer
        defaults), but we keep the test as a regression guard for
        any future env-var integration that should not break the
        supervised path.
        """
        runner = CliRunner()

        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
            patch.dict("os.environ", {"PRECOG_POLL_INTERVAL": "45"}),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock_supervisor()

            result = runner.invoke(
                isolated_app,
                ["scheduler", "start", "--supervised"],
            )

            assert result.exit_code == 0, (
                f"start should exit 0; got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()
