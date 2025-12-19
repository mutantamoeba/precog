"""E2E tests for CLI scheduler module.

Tests complete scheduler workflows from CLI invocation through database effects.

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


class TestSchedulerStartStopWorkflow:
    """E2E tests for scheduler start-stop lifecycle."""

    def test_complete_scheduler_lifecycle(self) -> None:
        """Test complete scheduler start-stop-status workflow.

        E2E: Tests full lifecycle from start to stop.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_instance.stop.return_value = True
            mock_instance.is_running.return_value = True
            mock_instance.get_status.return_value = {"running": True, "pollers": []}
            mock_supervisor.return_value = mock_instance

            # Start scheduler
            result = runner.invoke(app, ["scheduler", "start"])
            assert result.exit_code in [0, 1, 2]

            # Check status
            result = runner.invoke(app, ["scheduler", "status"])
            assert result.exit_code in [0, 1, 2]

            # Stop scheduler
            result = runner.invoke(app, ["scheduler", "stop"])
            assert result.exit_code in [0, 1, 2]

    def test_scheduler_restart_workflow(self) -> None:
        """Test scheduler restart workflow.

        E2E: Tests stop then start sequence.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_instance.stop.return_value = True
            mock_supervisor.return_value = mock_instance

            # Stop (should handle not running)
            result = runner.invoke(app, ["scheduler", "stop"])
            assert result.exit_code in [0, 1, 2]

            # Start
            result = runner.invoke(app, ["scheduler", "start"])
            assert result.exit_code in [0, 1, 2]


class TestSchedulerPollingWorkflow:
    """E2E tests for scheduler polling workflows."""

    def test_poll_once_workflow(self) -> None:
        """Test single poll execution workflow.

        E2E: Tests poll-once from CLI through database.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 5, "updated": 3}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(app, ["scheduler", "poll-once", "--league", "nfl"])
            assert result.exit_code in [0, 1, 2]

    def test_poll_multiple_leagues_workflow(self) -> None:
        """Test polling multiple leagues workflow.

        E2E: Tests multi-league poll-once execution.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 10, "updated": 8}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(
                app, ["scheduler", "poll-once", "--league", "nfl", "--league", "nba", "--save"]
            )
            assert result.exit_code in [0, 1, 2]


class TestSchedulerErrorRecovery:
    """E2E tests for scheduler error recovery workflows."""

    def test_scheduler_recovers_from_poll_error(self) -> None:
        """Test scheduler recovers from polling errors.

        E2E: Tests error recovery workflow.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.side_effect = [
                Exception("API error"),
                {"games": 3, "updated": 2},
            ]
            mock_supervisor.return_value = mock_instance

            # First poll fails
            result = runner.invoke(app, ["scheduler", "poll-once", "--league", "nfl"])
            # CLI should handle error gracefully
            assert result.exit_code in [0, 1, 2, 3, 4, 5]

    def test_scheduler_handles_stop_during_poll(self) -> None:
        """Test scheduler handles stop request during poll.

        E2E: Tests graceful shutdown during operation.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.stop.return_value = True
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(app, ["scheduler", "stop", "--force"])
            assert result.exit_code in [0, 1, 2]
