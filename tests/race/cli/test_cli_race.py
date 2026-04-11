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


def _mock_cursor_ctx():
    """Create a properly configured get_cursor mock for DB/system CLI tests."""
    mock_cursor_ctx = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {
        "version": "PostgreSQL 15.0",
        "current_database": "precog_test",
        "table_count": 0,
        "exists": False,
        "row_count": 0,
        "test": 1,
    }
    mock_cur.fetchall.return_value = []
    mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor_ctx


class TestSchedulerRace:
    """Race condition tests for scheduler CLI."""

    def test_rapid_sequential_status_checks(self, isolated_app) -> None:
        """Test rapid sequential status check invocations.

        Race: Tests 10 rapid status calls in sequence. Verifies the
        status command's module-global access (``_supervisor``,
        ``_show_db_backed_status``) does not develop inconsistent
        state across rapid calls.

        Mock note (#764): patches ``_show_db_backed_status``, the
        actual code path the status command takes. The previous
        version patched ``ServiceSupervisor``, which the status
        command never instantiates -- so the test was either
        making real DB calls (if ``list_scheduler_services`` worked)
        or hitting the in-process fallback. Either way, the mock
        was a no-op.
        """
        runner = CliRunner()
        results = []

        with patch("precog.cli.scheduler._show_db_backed_status", return_value=True) as mock_status:
            start = time.perf_counter()
            for _ in range(10):
                result = runner.invoke(isolated_app, ["scheduler", "status"])
                results.append(result.exit_code)
            elapsed = time.perf_counter() - start

            assert len(results) == 10
            assert all(code == 0 for code in results), f"unexpected exit codes: {results}"
            assert mock_status.call_count == 10, (
                f"_show_db_backed_status called {mock_status.call_count} times; expected 10"
            )
            # All 10 calls should complete in reasonable time
            assert elapsed < 30.0, f"10 calls took {elapsed:.2f}s"

    def test_rapid_alternating_start_stop(self, isolated_app) -> None:
        """Test rapid alternating start and stop requests.

        Race: Tests alternating start/stop calls on the non-supervised code path.

        Note: This test drives the NON-supervised code path (no --supervised flag),
        where the CLI directly instantiates ESPNGamePoller / KalshiMarketPoller from
        precog.schedulers. Both must be mocked at the package level to prevent
        real API client creation. This is distinct from the supervised path which
        requires patching create_supervisor (see test_cli_scheduler_e2e.py for
        that pattern).
        """
        runner = CliRunner()
        results = []

        mock_poller = MagicMock()
        mock_poller.start.return_value = None
        mock_poller.stop.return_value = None

        with (
            patch("precog.schedulers.ESPNGamePoller", return_value=mock_poller) as mock_espn,
            patch("precog.schedulers.KalshiMarketPoller", return_value=mock_poller) as mock_kalshi,
        ):
            for i in range(5):
                result = runner.invoke(isolated_app, ["scheduler", "start"])
                results.append(("start", result.exit_code))
                result = runner.invoke(isolated_app, ["scheduler", "stop"])
                results.append(("stop", result.exit_code))

            assert len(results) == 10
            for label, code in results:
                assert code == 0, f"{label} returned exit {code} (expected 0)"

            assert mock_espn.call_count == 5, (
                f"ESPNGamePoller constructor called {mock_espn.call_count} times, expected 5 — "
                "mock is a no-op if count is 0"
            )
            assert mock_kalshi.call_count == 5, (
                f"KalshiMarketPoller constructor called {mock_kalshi.call_count} times, expected 5"
            )


class TestDbRace:
    """Race condition tests for db CLI."""

    def test_rapid_sequential_status_checks(self, isolated_app) -> None:
        """Test rapid sequential database status checks.

        Race: Tests 10 rapid status calls in sequence.

        Note: The status command calls both test_connection() AND get_cursor(),
        so both must be mocked to prevent real database access during tests.
        """
        runner = CliRunner()
        results = []

        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_ctx,
        ):
            mock_test.return_value = True
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {
                "version": "PostgreSQL 15.0",
                "current_database": "precog_test",
                "table_count": 0,
                "exists": False,
                "test": 1,
            }
            mock_cur.fetchall.return_value = []
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

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
        runner = CliRunner()
        results = []

        with patch("precog.database.connection.get_cursor") as mock_ctx:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"row_count": 0}
            mock_cur.fetchall.return_value = []
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

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
        runner = CliRunner()
        results = []

        with patch("precog.database.connection.get_cursor") as mock_ctx:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"test": 1}
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

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
        runner = CliRunner()
        results = []

        with patch("precog.database.connection.get_cursor") as mock_ctx:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"test": 1}
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

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
        Verifies that interleaved access does not develop
        inconsistent module-global state.

        Mock note (#764): scheduler status patches
        ``_show_db_backed_status`` (the real code path) and is
        held to strict exit 0. The db/system commands are out of
        scope for #764 -- they have their own "missing critical
        tables -> exit 1" behavior under partial mocks that is
        unrelated to the scheduler retrofit. Their assertions
        remain intentionally loose; tightening them would require
        a separate audit of db/system CLI mock fidelity.
        """
        runner = CliRunner()
        scheduler_results = []
        other_results = []

        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_ctx,
            patch(
                "precog.cli.scheduler._show_db_backed_status", return_value=True
            ) as mock_sched_status,
        ):
            mock_test.return_value = True
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {
                "version": "PostgreSQL 15.0",
                "current_database": "precog_test",
                "table_count": 0,
                "exists": False,
                "row_count": 0,
                "test": 1,
            }
            mock_cur.fetchall.return_value = []
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

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
                    if name == "scheduler":
                        scheduler_results.append(result.exit_code)
                    else:
                        other_results.append((name, result.exit_code))

            # scheduler status fired 3 times -- verify the mock was hit
            assert mock_sched_status.call_count == 3, (
                f"_show_db_backed_status called {mock_sched_status.call_count} times; expected 3"
            )
            # Scheduler is the #764 in-scope path: strict exit 0.
            assert all(code == 0 for code in scheduler_results), (
                f"scheduler status exit codes: {scheduler_results}; expected all 0"
            )
            # db/system are out of scope (#764): just require they
            # don't crash with an unhandled exception.
            assert len(other_results) == 12  # 4 non-scheduler commands * 3 rounds
            assert all(code in [0, 1, 2] for _, code in other_results), (
                f"unexpected exit codes from db/system: {other_results}"
            )

    def test_state_isolation_between_modules(self, isolated_app) -> None:
        """Test that module state doesn't leak between rapid calls.

        Race: Verifies isolation between different CLI modules. Module-
        global state in ``precog.cli.scheduler`` is not touched by
        the ``status`` code path when ``_show_db_backed_status``
        returns True, so the scheduler module remains in a clean
        state across calls.
        """
        runner = CliRunner()

        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_ctx,
            patch(
                "precog.cli.scheduler._show_db_backed_status", return_value=True
            ) as mock_sched_status,
        ):
            mock_test.return_value = True
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {
                "version": "PostgreSQL 15.0",
                "current_database": "precog_test",
                "table_count": 0,
                "exists": False,
                "row_count": 0,
                "test": 1,
            }
            mock_cur.fetchall.return_value = []
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            # Rapid interleaved calls. Scheduler is the #764 in-scope
            # path and is held to strict exit 0; db/system have their
            # own "missing critical tables -> exit 1" behavior under
            # partial mocks that is out of scope for this retrofit.
            for _ in range(5):
                # Call scheduler -- the #764 in-scope path
                r1 = runner.invoke(isolated_app, ["scheduler", "status"])
                assert r1.exit_code == 0, (
                    f"scheduler status should exit 0; got {r1.exit_code}: {r1.output}"
                )

                # Immediately call db (out of scope: just require no crash)
                r2 = runner.invoke(isolated_app, ["db", "status"])
                assert r2.exit_code in [0, 1, 2]

                # Immediately call system (out of scope: just require no crash)
                r3 = runner.invoke(isolated_app, ["system", "health"])
                assert r3.exit_code in [0, 1, 2]

            assert mock_sched_status.call_count == 5, (
                f"_show_db_backed_status called {mock_sched_status.call_count} times; expected 5"
            )
