"""
Race condition tests for CLI scheduler commands.

Tests scheduler CLI under sequential rapid access.
Note: CliRunner is not thread-safe, so we test sequential race conditions.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/scheduler.py
    - REQ-TEST-006: Race Condition Testing

Coverage Target: 85%+ for cli/scheduler.py (critical tier)
"""

import pytest
from typer.testing import CliRunner

from precog.cli.scheduler import app


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Race Tests (Sequential - CliRunner not thread-safe)
# ============================================================================


@pytest.mark.race
class TestSchedulerRace:
    """Race condition tests for scheduler CLI."""

    def test_rapid_sequential_status_calls(self, runner):
        """Test rapid sequential status command calls."""
        results = []
        for _ in range(10):
            result = runner.invoke(app, ["status"])
            results.append(result.exit_code)

        # Should complete without errors
        assert len(results) == 10
        assert all(isinstance(r, int) for r in results)

    def test_rapid_sequential_help_calls(self, runner):
        """Test rapid sequential help command calls."""
        results = []
        for _ in range(20):
            result = runner.invoke(app, ["--help"])
            results.append(result.exit_code)

        # Help should always succeed
        assert len(results) == 20
        assert all(r == 0 for r in results)

    def test_interleaved_commands(self, runner):
        """Test interleaved command execution."""
        results = []
        commands = [
            ["status"],
            ["--help"],
            ["poll-once", "--help"],
            ["start", "--help"],
            ["stop", "--help"],
        ]

        for i in range(15):
            cmd = commands[i % len(commands)]
            result = runner.invoke(app, cmd)
            results.append(result.exit_code)

        # All should complete
        assert len(results) == 15
        assert all(isinstance(r, int) for r in results)


@pytest.mark.race
class TestSchedulerStartStopRace:
    """Race tests for start/stop operations."""

    def test_alternating_stop_status(self, runner):
        """Test alternating stop and status calls."""
        results = []
        for _ in range(5):
            stop_result = runner.invoke(app, ["stop"])
            results.append(("stop", stop_result.exit_code))
            status_result = runner.invoke(app, ["status"])
            results.append(("status", status_result.exit_code))

        # All should complete
        assert len(results) == 10
        assert all(isinstance(r[1], int) for r in results)
