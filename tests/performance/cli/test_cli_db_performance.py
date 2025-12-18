"""
Performance tests for CLI database commands.

Tests database CLI response times and throughput.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/db.py
    - REQ-TEST-007: Performance Testing

Coverage Target: 85%+ for cli/db.py (business tier)
"""

import statistics
import time
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from precog.cli.db import app


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.performance
class TestDbPerformance:
    """Performance tests for database CLI."""

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

    def test_status_response_time(self, runner):
        """Test status command response time."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            times = []
            iterations = 20

            for _ in range(iterations):
                start = time.perf_counter()
                runner.invoke(app, ["status"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                times.append(elapsed)

            p50 = statistics.median(times)
            p95 = sorted(times)[int(iterations * 0.95)]

            # Status should be reasonably fast
            assert p50 < 200, f"p50={p50}ms exceeds 200ms"
            assert p95 < 500, f"p95={p95}ms exceeds 500ms"

    def test_tables_response_time(self, runner):
        """Test tables command response time."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            cursor = MagicMock()
            conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            cursor.fetchall.return_value = [("games",), ("markets",)]

            times = []
            iterations = 20

            for _ in range(iterations):
                start = time.perf_counter()
                runner.invoke(app, ["tables"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                times.append(elapsed)

            p50 = statistics.median(times)
            p95 = sorted(times)[int(iterations * 0.95)]

            # Tables should be reasonably fast
            assert p50 < 200, f"p50={p50}ms exceeds 200ms"
            assert p95 < 500, f"p95={p95}ms exceeds 500ms"


@pytest.mark.performance
class TestDbThroughput:
    """Throughput tests for database CLI."""

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

    def test_status_throughput(self, runner):
        """Test status command throughput."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            duration = 2  # seconds
            count = 0
            start = time.perf_counter()

            while time.perf_counter() - start < duration:
                runner.invoke(app, ["status"])
                count += 1

            throughput = count / duration
            # Should handle reasonable status requests
            assert throughput > 3, f"Throughput {throughput:.1f}/s below 3/s"
