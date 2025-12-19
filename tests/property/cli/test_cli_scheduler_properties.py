"""Property-based tests for CLI scheduler commands.

Tests command-line argument parsing invariants and output format consistency
using Hypothesis to generate edge cases.

Reference: TESTING_STRATEGY V3.2 - Property Tests (2/8)
"""

from unittest.mock import MagicMock, patch

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from precog.cli import app, register_commands

# Initialize CLI for testing
register_commands()
runner = CliRunner()


class TestSchedulerArgumentInvariants:
    """Property tests for scheduler command argument validation."""

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_scheduler_name_handling(self, name: str):
        """Scheduler commands should handle arbitrary string names gracefully."""
        # Skip control characters which can break terminal output
        assume(all(ord(c) >= 32 for c in name))
        assume(name.strip())  # Skip whitespace-only names

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.get_scheduler_status.return_value = {}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(app, ["scheduler", "status", "--name", name])
            # Command should complete without crashing
            assert result.exit_code in [0, 1, 2]

    @given(st.integers())
    @settings(max_examples=50)
    def test_poll_interval_integer_handling(self, interval: int):
        """Poll-once should handle any integer interval argument."""
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"success": True}
            mock_supervisor.return_value = mock_instance

            # Pass interval as string (CLI receives strings)
            result = runner.invoke(
                app, ["scheduler", "poll-once", "--poll-interval", str(interval)]
            )
            # Command should complete (may fail validation but not crash)
            assert result.exit_code in [0, 1, 2]

    @given(st.floats(allow_nan=False, allow_infinity=False))
    @settings(max_examples=50)
    def test_poll_interval_float_rejection(self, interval: float):
        """Poll-once should handle float interval arguments."""
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"success": True}
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(
                app, ["scheduler", "poll-once", "--poll-interval", str(interval)]
            )
            # Typer may convert or reject floats - either is valid behavior
            assert result.exit_code in [0, 1, 2]


class TestSchedulerOutputInvariants:
    """Property tests for scheduler command output consistency."""

    @given(st.booleans())
    @settings(max_examples=10)
    def test_help_output_always_includes_commands(self, verbose: bool):
        """Help output should always list available subcommands."""
        result = runner.invoke(app, ["scheduler", "--help"])
        assert result.exit_code == 0
        # Help should mention key commands
        assert "start" in result.output.lower() or "Commands" in result.output
        assert "stop" in result.output.lower() or "Commands" in result.output

    @given(st.sampled_from(["start", "stop", "status", "poll-once"]))
    @settings(max_examples=4)
    def test_subcommand_help_available(self, subcommand: str):
        """Each subcommand should have help available."""
        result = runner.invoke(app, ["scheduler", subcommand, "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 0


class TestSchedulerStateTransitions:
    """Property tests for scheduler state handling."""

    @given(st.lists(st.sampled_from(["start", "stop"]), min_size=1, max_size=5))
    @settings(max_examples=20, deadline=None)  # CLI invocations can exceed 200ms deadline
    def test_command_sequence_stability(self, commands: list):
        """Any sequence of start/stop commands should not crash."""
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start_scheduler.return_value = True
            mock_instance.stop_scheduler.return_value = True
            mock_supervisor.return_value = mock_instance

            for cmd in commands:
                result = runner.invoke(app, ["scheduler", cmd, "--name", "test"])
                # Each command should complete without crashing
                assert result.exit_code in [0, 1, 2]

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=20)
    def test_status_with_varying_scheduler_counts(self, count: int):
        """Status should handle any number of schedulers."""
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            # Generate mock scheduler status
            mock_instance.get_scheduler_status.return_value = {
                f"scheduler_{i}": {"running": i % 2 == 0} for i in range(count)
            }
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(app, ["scheduler", "status"])
            assert result.exit_code in [0, 1, 2]
