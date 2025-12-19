"""
Performance tests for CLI system commands.

Tests system CLI response times and throughput.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/system.py
    - REQ-TEST-007: Performance Testing

Coverage Target: 80%+ for cli/system.py (infrastructure tier)
"""

import statistics
import time
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from precog.cli.system import app


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.performance
class TestSystemPerformance:
    """Performance tests for system CLI."""

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
        assert p50 < 100, f"p50={p50}ms exceeds 100ms"
        assert p95 < 200, f"p95={p95}ms exceeds 200ms"
        assert p99 < 500, f"p99={p99}ms exceeds 500ms"

    def test_version_response_time(self, runner):
        """Test version command response time."""
        times = []
        iterations = 30

        for _ in range(iterations):
            start = time.perf_counter()
            runner.invoke(app, ["version"])
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p50 = statistics.median(times)
        p95 = sorted(times)[int(iterations * 0.95)]
        p99 = sorted(times)[int(iterations * 0.99)]

        # Version should be very fast (no I/O)
        assert p50 < 50, f"p50={p50}ms exceeds 50ms"
        assert p95 < 100, f"p95={p95}ms exceeds 100ms"
        assert p99 < 200, f"p99={p99}ms exceeds 200ms"

    def test_health_response_time(self, runner):
        """Test health command response time."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            times = []
            iterations = 20

            for _ in range(iterations):
                start = time.perf_counter()
                runner.invoke(app, ["health"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                times.append(elapsed)

            p50 = statistics.median(times)
            p95 = sorted(times)[int(iterations * 0.95)]

            # Health should be reasonably fast
            assert p50 < 200, f"p50={p50}ms exceeds 200ms"
            assert p95 < 500, f"p95={p95}ms exceeds 500ms"

    def test_info_response_time(self, runner):
        """Test info command response time."""
        times = []
        iterations = 20

        for _ in range(iterations):
            start = time.perf_counter()
            runner.invoke(app, ["info"])
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        p50 = statistics.median(times)
        p95 = sorted(times)[int(iterations * 0.95)]

        # Info should be reasonably fast
        assert p50 < 200, f"p50={p50}ms exceeds 200ms"
        assert p95 < 500, f"p95={p95}ms exceeds 500ms"


@pytest.mark.performance
class TestSystemThroughput:
    """Throughput tests for system CLI."""

    def test_version_throughput(self, runner):
        """Test version command throughput."""
        duration = 2  # seconds
        count = 0
        start = time.perf_counter()

        while time.perf_counter() - start < duration:
            runner.invoke(app, ["version"])
            count += 1

        throughput = count / duration
        # Version should be very fast
        assert throughput > 10, f"Throughput {throughput:.1f}/s below 10/s"

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
        assert throughput > 5, f"Throughput {throughput:.1f}/s below 5/s"
