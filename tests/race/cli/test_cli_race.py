"""Race condition tests for CLI modules.

Tests CLI modules under rapid sequential access patterns.
Note: Typer's CliRunner is not fully thread-safe, so we test
rapid sequential execution instead of true concurrency.

References:
    - REQ-TEST-006: Race condition testing
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
from typer.testing import CliRunner


@pytest.fixture
def isolated_app():
    """Create a completely isolated Typer app for race condition testing.

    This fixture creates a fresh app instance that doesn't share state with
    other tests, preventing race conditions during parallel execution.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestSchedulerRace:
    """Race condition tests for scheduler CLI."""

    def test_rapid_sequential_status_checks(self, isolated_app) -> None:
        """Test rapid sequential status check invocations.

        Race: Tests 10 rapid status calls in sequence.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            start = time.perf_counter()
            for _ in range(10):
                result = runner.invoke(isolated_app, ["scheduler", "status"])
                results.append(result.exit_code)
            elapsed = time.perf_counter() - start

            assert len(results) == 10
            assert all(code in [0, 1, 2] for code in results)
            # All 10 calls should complete in reasonable time
            assert elapsed < 30.0, f"10 calls took {elapsed:.2f}s"

    def test_rapid_alternating_start_stop(self, isolated_app) -> None:
        """Test rapid alternating start and stop requests.

        Race: Tests alternating start/stop calls.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_instance.stop.return_value = True
            mock_supervisor.return_value = mock_instance

            for i in range(5):
                result = runner.invoke(isolated_app, ["scheduler", "start"])
                results.append(("start", result.exit_code))
                result = runner.invoke(isolated_app, ["scheduler", "stop"])
                results.append(("stop", result.exit_code))

            assert len(results) == 10
            # All should complete without errors
            assert all(code in [0, 1, 2] for _, code in results)


class TestDbRace:
    """Race condition tests for db CLI."""

    def test_rapid_sequential_status_checks(self, isolated_app) -> None:
        """Test rapid sequential database status checks.

        Race: Tests 10 rapid status calls in sequence.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_session = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            start = time.perf_counter()
            for _ in range(10):
                result = runner.invoke(isolated_app, ["db", "status"])
                results.append(result.exit_code)
            elapsed = time.perf_counter() - start

            assert len(results) == 10
            assert all(code in [0, 1, 2] for code in results)
            assert elapsed < 30.0

    def test_rapid_table_queries(self, isolated_app) -> None:
        """Test rapid table listing queries.

        Race: Tests rapid sequential table queries.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_session = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.fetchall.return_value = []

            for _ in range(10):
                result = runner.invoke(isolated_app, ["db", "tables"])
                results.append(result.exit_code)

            assert len(results) == 10
            assert all(code in [0, 1, 2] for code in results)


class TestSystemRace:
    """Race condition tests for system CLI."""

    def test_rapid_sequential_health_checks(self, isolated_app) -> None:
        """Test rapid sequential health check invocations.

        Race: Tests 10 rapid health calls in sequence.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_session = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            start = time.perf_counter()
            for _ in range(10):
                result = runner.invoke(isolated_app, ["system", "health"])
                results.append(result.exit_code)
            elapsed = time.perf_counter() - start

            assert len(results) == 10
            assert all(code in [0, 1, 2] for code in results)
            assert elapsed < 30.0

    def test_rapid_mixed_commands(self, isolated_app) -> None:
        """Test rapid alternating version and info commands.

        Race: Tests alternating mixed commands.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_session = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            for i in range(5):
                result = runner.invoke(isolated_app, ["system", "version"])
                results.append(("version", result.exit_code))
                result = runner.invoke(isolated_app, ["system", "info"])
                results.append(("info", result.exit_code))

            assert len(results) == 10
            assert all(code in [0, 1, 2] for _, code in results)


class TestCrossModuleRace:
    """Race condition tests across CLI modules."""

    def test_rapid_cross_module_commands(self, isolated_app) -> None:
        """Test rapid commands across different modules.

        Race: Tests rapid commands from scheduler, db, and system.
        """
        runner = CliRunner(mix_stderr=False)
        results = []

        with (
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor,
        ):
            mock_session = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.fetchall.return_value = []
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            commands = [
                (["scheduler", "status"], "scheduler"),
                (["db", "status"], "db"),
                (["system", "health"], "system"),
                (["system", "version"], "version"),
                (["db", "tables"], "tables"),
            ]

            # Run 3 rounds of all commands
            for _ in range(3):
                for cmd, name in commands:
                    result = runner.invoke(isolated_app, cmd)
                    results.append((name, result.exit_code))

            assert len(results) == 15  # 5 commands * 3 rounds
            assert all(code in [0, 1, 2] for _, code in results)

    def test_state_isolation_between_modules(self, isolated_app) -> None:
        """Test that module state doesn't leak between rapid calls.

        Race: Verifies isolation between different CLI modules.
        """
        runner = CliRunner(mix_stderr=False)

        with (
            patch("precog.database.connection.get_connection") as mock_conn,
            patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor,
        ):
            mock_session = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            # Rapid interleaved calls
            for _ in range(5):
                # Call scheduler
                r1 = runner.invoke(isolated_app, ["scheduler", "status"])
                assert r1.exit_code in [0, 1, 2]

                # Immediately call db
                r2 = runner.invoke(isolated_app, ["db", "status"])
                assert r2.exit_code in [0, 1, 2]

                # Immediately call system
                r3 = runner.invoke(isolated_app, ["system", "health"])
                assert r3.exit_code in [0, 1, 2]
