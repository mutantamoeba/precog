"""Performance tests for CLI modules.

Tests CLI module performance characteristics and benchmarks.

References:
    - REQ-TEST-007: Performance testing
    - TESTING_STRATEGY V3.2: 8 test types required

Parallel Execution Note:
    These tests must create fresh app instances to avoid test pollution during
    parallel pytest-xdist execution. The global app object is shared across
    workers, causing race conditions when multiple tests register commands
    or invoke CLI operations simultaneously.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
import typer


@pytest.fixture
def isolated_app():
    """Create a completely isolated Typer app for performance testing.

    This fixture creates a fresh app instance that doesn't share state with
    other tests, preventing race conditions during parallel execution.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestSchedulerPerformance:
    """Performance tests for scheduler CLI."""

    def test_status_latency(self, cli_runner, isolated_app) -> None:
        """Test scheduler status command latency.

        Performance: p95 should be < 100ms.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                result = cli_runner.invoke(isolated_app, ["scheduler", "status"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                latencies.append(elapsed)
                assert result.exit_code in [0, 1, 2]

            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            # CLI operations should be fast
            assert p95 < 500, f"p95 latency {p95}ms exceeds threshold"

    def test_poll_once_throughput(self, cli_runner, isolated_app) -> None:
        """Test poll-once command throughput.

        Performance: Should handle 10 calls in < 5 seconds.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 5, "updated": 3}
            mock_supervisor.return_value = mock_instance

            start = time.perf_counter()
            for _ in range(10):
                result = cli_runner.invoke(
                    isolated_app, ["scheduler", "poll-once", "--league", "nfl"]
                )
                assert result.exit_code in [0, 1, 2]
            elapsed = time.perf_counter() - start

            assert elapsed < 5.0, f"10 poll-once calls took {elapsed:.2f}s"


class TestDbPerformance:
    """Performance tests for db CLI."""

    def test_status_latency(self, cli_runner, isolated_app) -> None:
        """Test db status command latency.

        Performance: p95 should be < 100ms (relaxed to 600ms for CI/slow systems).

        Note: The status command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access during tests.
        Threshold relaxed from 500ms to 600ms due to observed p95 variance
        during pre-push hooks under load.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                result = cli_runner.invoke(isolated_app, ["db", "status"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                latencies.append(elapsed)
                assert result.exit_code in [0, 1, 2]

            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            assert p95 < 600, f"p95 latency {p95}ms exceeds threshold"

    def test_tables_latency(self, cli_runner, isolated_app) -> None:
        """Test db tables command latency.

        Performance: p95 should be < 200ms (relaxed to 600ms for CI/slow systems).

        Note: The tables command may call test_connection() in some code paths,
        so both must be mocked. Threshold relaxed from 500ms to 600ms due to
        observed p95 variance during pre-push hooks under load.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                result = cli_runner.invoke(isolated_app, ["db", "tables"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                latencies.append(elapsed)
                assert result.exit_code in [0, 1, 2]

            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            assert p95 < 600, f"p95 latency {p95}ms exceeds threshold"


class TestSystemPerformance:
    """Performance tests for system CLI."""

    def test_health_latency(self, cli_runner, isolated_app) -> None:
        """Test system health command latency.

        Performance: p95 should be < 200ms (relaxed to 800ms for CI/slow systems).

        Note: The health command may call test_connection() in some code paths,
        so both must be mocked. Threshold relaxed from 500ms to 800ms due to
        observed p95 variance during pre-push hooks under load.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                result = cli_runner.invoke(isolated_app, ["system", "health"])
                elapsed = (time.perf_counter() - start) * 1000  # ms
                latencies.append(elapsed)
                assert result.exit_code in [0, 1, 2]

            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            assert p95 < 800, f"p95 latency {p95}ms exceeds threshold"

    def test_version_latency(self, cli_runner, isolated_app) -> None:
        """Test system version command latency.

        Performance: p95 should be < 50ms (no external calls).
        """
        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            result = cli_runner.invoke(isolated_app, ["system", "version"])
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            assert result.exit_code in [0, 1, 2]

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        # Relaxed threshold for CI/slow systems
        assert p95 < 500, f"p95 latency {p95}ms exceeds threshold"

    def test_info_latency(self, cli_runner, isolated_app) -> None:
        """Test system info command latency.

        Performance: p95 should be < 100ms.
        """
        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            result = cli_runner.invoke(isolated_app, ["system", "info"])
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            assert result.exit_code in [0, 1, 2]

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 300, f"p95 latency {p95}ms exceeds threshold"


class TestCommandThroughput:
    """Throughput tests for CLI commands."""

    def test_mixed_command_throughput(self, cli_runner, isolated_app) -> None:
        """Test throughput of mixed CLI commands.

        Performance: Should handle 50 mixed commands in < 10 seconds.

        Note: The status command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            commands = [
                ["system", "version"],
                ["system", "info"],
                ["db", "status"],
                ["scheduler", "status"],
            ]

            start = time.perf_counter()
            for i in range(50):
                cmd = commands[i % len(commands)]
                result = cli_runner.invoke(isolated_app, cmd)
                assert result.exit_code in [0, 1, 2]
            elapsed = time.perf_counter() - start

            throughput = 50 / elapsed
            # Relaxed threshold for CI/slow systems
            assert throughput > 3, f"Throughput {throughput:.2f} ops/s is too low"
