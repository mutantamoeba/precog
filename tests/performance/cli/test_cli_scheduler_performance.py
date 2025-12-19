"""
Performance tests for CLI scheduler commands.

Tests scheduler CLI response times and throughput.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/scheduler.py
    - REQ-TEST-007: Performance Testing

Coverage Target: 85%+ for cli/scheduler.py (critical tier)
"""

import statistics
import time

import pytest
from typer.testing import CliRunner

from precog.cli.scheduler import app


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.performance
class TestSchedulerPerformance:
    """Performance tests for scheduler CLI."""

    def test_help_response_time(self, runner):
        """Test help command response time."""
        times = []
        iterations = 20

        for _ in range(iterations):
            start = time.perf_counter()
            runner.invoke(app, ["--help"])
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p50 = statistics.median(times)
        p95 = sorted(times)[int(iterations * 0.95)]
        p99 = sorted(times)[int(iterations * 0.99)]

        # Help should be very fast
        assert p50 < 200, f"p50={p50}ms exceeds 200ms"
        assert p95 < 500, f"p95={p95}ms exceeds 500ms"
        assert p99 < 1000, f"p99={p99}ms exceeds 1000ms"

    def test_status_response_time(self, runner):
        """Test status command response time."""
        times = []
        iterations = 10

        for _ in range(iterations):
            start = time.perf_counter()
            runner.invoke(app, ["status"])
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p50 = statistics.median(times)
        p95 = sorted(times)[int(iterations * 0.95)]

        # Status should be reasonably fast
        assert p50 < 500, f"p50={p50}ms exceeds 500ms"
        assert p95 < 1000, f"p95={p95}ms exceeds 1000ms"


@pytest.mark.performance
class TestSchedulerThroughput:
    """Throughput tests for scheduler CLI."""

    def test_help_throughput(self, runner):
        """Test help command throughput."""
        duration = 2  # seconds
        count = 0
        start = time.perf_counter()

        while time.perf_counter() - start < duration:
            runner.invoke(app, ["--help"])
            count += 1

        throughput = count / duration
        # Should handle many help requests per second
        assert throughput > 3, f"Throughput {throughput:.1f}/s below 3/s"
