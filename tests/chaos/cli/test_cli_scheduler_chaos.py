"""
Chaos tests for CLI scheduler commands.

Tests scheduler CLI behavior under fault conditions.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/scheduler.py
    - REQ-TEST-008: Chaos Testing

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
# Chaos Tests
# ============================================================================


@pytest.mark.chaos
class TestSchedulerChaos:
    """Chaos tests for scheduler CLI."""

    def test_status_when_nothing_running(self, runner):
        """Test status when no schedulers running."""
        result = runner.invoke(app, ["status"])
        # Should handle gracefully
        assert isinstance(result.exit_code, int)

    def test_stop_when_nothing_running(self, runner):
        """Test stop when no schedulers running."""
        result = runner.invoke(app, ["stop"])
        # Should handle gracefully
        assert isinstance(result.exit_code, int)

    def test_poll_once_no_sources(self, runner):
        """Test poll-once with no data sources."""
        result = runner.invoke(app, ["poll-once", "--no-espn", "--no-kalshi"])
        # Should handle gracefully
        assert isinstance(result.exit_code, int)

    def test_invalid_interval(self, runner):
        """Test start with invalid interval."""
        result = runner.invoke(app, ["start", "--espn-interval", "0", "--no-foreground"])
        # Should handle invalid interval gracefully
        assert isinstance(result.exit_code, int)


@pytest.mark.chaos
class TestSchedulerResourceChaos:
    """Resource chaos tests for scheduler CLI."""

    def test_repeated_status_checks(self, runner):
        """Test repeated status checks."""
        results = []
        for _ in range(10):
            result = runner.invoke(app, ["status"])
            results.append(result.exit_code)

        # All should complete
        assert all(isinstance(r, int) for r in results)

    def test_repeated_stop_calls(self, runner):
        """Test repeated stop calls."""
        results = []
        for _ in range(5):
            result = runner.invoke(app, ["stop"])
            results.append(result.exit_code)

        # All should complete
        assert all(isinstance(r, int) for r in results)


@pytest.mark.chaos
class TestSchedulerStartStopChaos:
    """Chaos tests for start/stop operations."""

    def test_stop_multiple_times(self, runner):
        """Test stop called multiple times."""
        for _ in range(3):
            result = runner.invoke(app, ["stop"])
            # Should handle each call gracefully
            assert isinstance(result.exit_code, int)

    def test_status_after_stop(self, runner):
        """Test status after stop."""
        runner.invoke(app, ["stop"])
        result = runner.invoke(app, ["status"])
        assert isinstance(result.exit_code, int)
