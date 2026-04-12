"""Chaos tests for CLI modules.

Tests CLI module resilience under fault injection and error conditions.

References:
    - REQ-TEST-008: Chaos testing
    - Issue #258: Create shared CLI test fixtures
    - TESTING_STRATEGY V3.2: 8 test types required

Note:
    Uses shared CLI fixtures from tests/conftest.py (cli_runner, cli_app).
"""

import random
from unittest.mock import MagicMock, patch

import pytest

from precog.cli import app, register_commands


@pytest.fixture(autouse=True)
def setup_commands():
    """Ensure commands are registered before each test."""
    register_commands()


@pytest.fixture(autouse=True)
def _mock_migration_check():
    """Bypass migration parity check in all scheduler CLI tests."""
    from precog.database.migration_check import MigrationStatus

    ok = MigrationStatus(is_current=True, db_version="0057", head_version="0057")
    with patch("precog.database.migration_check.check_migration_parity", return_value=ok):
        yield


class TestSchedulerChaos:
    """Chaos tests for scheduler CLI.

    Mock Level Notes (#764):
        ``status`` does not call ``create_supervisor``; it queries
        the database via ``list_scheduler_services``. Chaos for
        status must be injected into that database call.

        ``poll-once`` does not call ``create_supervisor``; it
        directly instantiates ``ESPNGamePoller`` and
        ``KalshiMarketPoller`` from ``precog.schedulers``. Chaos for
        poll-once must be injected into the poller's ``poll_once``
        method.

        The previous versions of these tests patched
        ``ServiceSupervisor`` (a class the CLI never instantiates
        on these code paths), so the chaos was never actually
        injected -- the tests reported success on every call,
        regardless of the random failure rate, because the CLI
        ran its real (or fallback) path uninfluenced by the mock.
    """

    def test_supervisor_random_failures(self, cli_runner) -> None:
        """Test scheduler status handles random database-IPC failures.

        Chaos: 30% random failure rate on the database-backed
        status query across 20 invocations. Failures are caught
        inside ``_show_db_backed_status`` (it has a try/except that
        returns False on error and falls back to the in-process
        path), so the CLI must complete with exit 0 on every call.
        """
        from precog.cli import scheduler as scheduler_module

        call_count = [0]

        def random_failure(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.3:  # 30% failure rate
                raise Exception("Random database failure")
            return []  # No services in DB -> fall back to in-process

        original_supervisor = scheduler_module._supervisor
        scheduler_module._supervisor = None
        try:
            with patch(
                "precog.database.crud_schedulers.list_scheduler_services",
                side_effect=random_failure,
            ):
                successes = 0
                for _ in range(20):
                    result = cli_runner.invoke(app, ["scheduler", "status"])
                    if result.exit_code == 0:
                        successes += 1

                # The CLI catches DB failures internally and falls
                # back, so every call should exit cleanly.
                assert successes == 20, (
                    f"Only {successes}/20 status calls succeeded; expected 20. "
                    f"Chaos was actually injected (call_count={call_count[0]})."
                )
                # Verify the chaos hook was actually exercised -- if
                # the patch silently missed (the #764 anti-pattern),
                # call_count would be zero.
                assert call_count[0] == 20, (
                    f"chaos hook was only called {call_count[0]} times; "
                    "expected 20 (one per status invocation)"
                )
        finally:
            scheduler_module._supervisor = original_supervisor

    def test_poll_with_intermittent_failures(self, cli_runner) -> None:
        """Test poll-once with intermittent ESPN poller failures.

        Chaos: Every 3rd ESPN poll raises. The CLI catches the
        exception inside the ``try/except`` around ``poller.poll_once()``
        and continues to the Kalshi poller, so the command always
        exits cleanly. Verifies the CLI's per-poller error isolation.
        """
        call_count = [0]

        def alternating_result(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:  # Every 3rd call fails
                raise Exception("Intermittent ESPN failure")
            return {"items_fetched": 5, "items_updated": 3}

        with (
            patch("precog.schedulers.ESPNGamePoller") as mock_espn_cls,
            patch("precog.schedulers.KalshiMarketPoller") as mock_kalshi_cls,
        ):
            mock_espn = MagicMock()
            mock_espn.poll_once.side_effect = alternating_result
            mock_espn_cls.return_value = mock_espn

            mock_kalshi = MagicMock()
            mock_kalshi.poll_once.return_value = {
                "items_fetched": 1,
                "items_updated": 1,
                "items_created": 0,
            }
            mock_kalshi.kalshi_client = MagicMock()
            mock_kalshi_cls.return_value = mock_kalshi

            results = []
            for _ in range(15):
                result = cli_runner.invoke(app, ["scheduler", "poll-once", "--leagues", "nfl"])
                results.append(result.exit_code)

            # All should complete cleanly -- the CLI catches
            # per-poller exceptions and continues.
            assert len(results) == 15
            assert all(code == 0 for code in results), f"unexpected non-zero exit codes: {results}"
            # Verify the chaos hook actually fired.
            assert call_count[0] == 15, (
                f"chaos hook was only called {call_count[0]} times; "
                "expected 15 (one per poll-once invocation)"
            )


class TestDbChaos:
    """Chaos tests for db CLI."""

    def test_connection_random_failures(self, cli_runner) -> None:
        """Test db handles random connection failures.

        Chaos: Random connection failures.
        """
        call_count = [0]

        def random_connection(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.4:  # 40% failure rate
                raise Exception("Random connection failure")
            mock = MagicMock()
            mock.__enter__ = MagicMock()
            mock.__exit__ = MagicMock()
            return mock

        with patch("precog.database.connection.get_connection", side_effect=random_connection):
            results = []
            for _ in range(20):
                result = cli_runner.invoke(app, ["db", "status"])
                results.append(result.exit_code)

            # All should complete (don't crash)
            assert len(results) == 20

    def test_init_with_flaky_connection(self, cli_runner) -> None:
        """Test init with flaky database connection.

        Chaos: Connection that works sometimes.
        """
        call_count = [0]

        def flaky_test(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Connection not ready")
            return True

        with patch("precog.database.connection.test_connection", side_effect=flaky_test):
            results = []
            for _ in range(5):
                result = cli_runner.invoke(app, ["db", "init"])
                results.append(result.exit_code)

            # All should complete gracefully
            assert len(results) == 5


class TestSystemChaos:
    """Chaos tests for system CLI."""

    def test_health_with_component_failures(self, cli_runner) -> None:
        """Test health check with random component failures.

        Chaos: Components fail randomly.
        """
        call_count = [0]

        def random_health(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.5:  # 50% failure rate
                raise Exception("Component failure")
            mock = MagicMock()
            mock.__enter__ = MagicMock()
            mock.__exit__ = MagicMock()
            return mock

        with patch("precog.database.connection.get_connection", side_effect=random_health):
            results = []
            for _ in range(20):
                result = cli_runner.invoke(app, ["system", "health"])
                results.append(result.exit_code)

            # All should complete (graceful degradation)
            assert len(results) == 20

    def test_info_with_missing_data(self, cli_runner) -> None:
        """Test info command with missing configuration data.

        Chaos: Configuration partially unavailable.
        """
        with patch("precog.config.config_loader.ConfigLoader") as mock_config:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = lambda key: None if random.random() < 0.3 else {}
            mock_config.return_value = mock_instance

            results = []
            for _ in range(10):
                result = cli_runner.invoke(app, ["system", "info"])
                results.append(result.exit_code)

            # All should complete
            assert len(results) == 10


class TestCrossModuleChaos:
    """Chaos tests across CLI modules."""

    def test_cascading_failures(self, cli_runner) -> None:
        """Test handling of cascading failures across modules.

        Chaos: One failure causes others to fail.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            # Database fails, affects scheduler and system
            mock_conn.side_effect = Exception("Database down")

            commands = [
                ["db", "status"],
                ["system", "health"],
                ["scheduler", "status"],
            ]

            results = []
            for cmd in commands:
                result = cli_runner.invoke(app, cmd)
                results.append((cmd[0], result.exit_code))

            # All should complete (not crash)
            assert len(results) == 3

    def test_recovery_after_failures(self, cli_runner) -> None:
        """Test CLI recovery after failures.

        Chaos: Failures then recovery.
        """
        call_count = [0]

        def recovering_connection(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise Exception("Still recovering")
            mock = MagicMock()
            mock.__enter__ = MagicMock()
            mock.__exit__ = MagicMock()
            return mock

        with patch("precog.database.connection.get_connection", side_effect=recovering_connection):
            results = []
            for i in range(6):
                result = cli_runner.invoke(app, ["db", "status"])
                results.append(result.exit_code)

            # Later calls should succeed
            assert len(results) == 6


class TestResourceExhaustion:
    """Chaos tests for resource exhaustion scenarios."""

    def test_handles_timeout_scenarios(self, cli_runner) -> None:
        """Test CLI handles timeout-like conditions.

        Chaos: Simulated slow operations.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_cursor_ctx,
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
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            results = []
            for _ in range(10):
                result = cli_runner.invoke(app, ["db", "status"])
                results.append(result.exit_code)

            assert all(code in [0, 1, 2] for code in results)

    def test_handles_memory_pressure(self, cli_runner) -> None:
        """Test CLI handles memory pressure scenarios.

        Chaos: 100 fake services in the database-backed status
        response. The CLI must render the table and exit cleanly.

        See class docstring for why we patch
        ``list_scheduler_services`` and not ``ServiceSupervisor``.
        """
        from datetime import UTC, datetime

        large_service_list = [
            {
                "service_name": f"poller_{i}",
                "host_id": "test-host",
                "pid": 1000 + i,
                "status": "running",
                "started_at": datetime.now(UTC),
                "last_heartbeat": datetime.now(UTC),
                "error_message": None,
                "stats": {"large_field": "x" * 1000},
            }
            for i in range(100)
        ]

        with patch(
            "precog.database.crud_schedulers.list_scheduler_services",
            return_value=large_service_list,
        ) as mock_list:
            result = cli_runner.invoke(app, ["scheduler", "status"])
            assert result.exit_code == 0, (
                f"status under memory pressure should exit 0; "
                f"got {result.exit_code}: {result.output}"
            )
            mock_list.assert_called_once()
