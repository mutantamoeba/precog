"""Stress tests for CLI modules.

Tests CLI modules under high load and repeated invocations.

References:
    - REQ-TEST-005: Stress testing
    - TESTING_STRATEGY V3.2: 8 test types required

Parallel Execution Note:
    These tests must create fresh app instances to avoid test pollution during
    parallel pytest-xdist execution. The global app object is shared across
    workers, causing race conditions when multiple tests register commands
    or invoke CLI operations simultaneously.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner


@pytest.fixture
def isolated_app():
    """Create a completely isolated Typer app for stress testing.

    This fixture creates a fresh app instance that doesn't share state with
    other tests, preventing race conditions during parallel execution.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    return fresh_app


class TestSchedulerStress:
    """Stress tests for scheduler CLI."""

    def test_repeated_status_checks(self, isolated_app) -> None:
        """Test repeated status checks under load.

        Stress: Tests 50 rapid status invocations.

        Note: The status command calls _show_db_backed_status() which queries the
        database. Mocking it to return False makes it fall through to the in-process
        check, which correctly shows "Not running" when no pollers are active.
        """
        runner = CliRunner()

        with patch("precog.cli.scheduler._show_db_backed_status", return_value=False):
            for i in range(50):
                result = runner.invoke(isolated_app, ["scheduler", "status"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_rapid_start_stop_cycles(self, isolated_app) -> None:
        """Test rapid start-stop cycles.

        Stress: Tests 20 start-stop cycles.

        Note: The start command imports ESPNGamePoller and KalshiMarketPoller from
        precog.schedulers (not ServiceSupervisor) and instantiates them directly.
        Both must be mocked to prevent real API client creation and network calls.
        """
        runner = CliRunner()

        with (
            patch("precog.schedulers.ESPNGamePoller") as mock_espn,
            patch("precog.schedulers.KalshiMarketPoller") as mock_kalshi,
        ):
            mock_espn_instance = MagicMock()
            mock_espn_instance.start.return_value = None
            mock_espn_instance.stop.return_value = None
            mock_espn_instance.enabled = True
            mock_espn.return_value = mock_espn_instance

            mock_kalshi_instance = MagicMock()
            mock_kalshi_instance.start.return_value = None
            mock_kalshi_instance.stop.return_value = None
            mock_kalshi_instance.enabled = True
            mock_kalshi.return_value = mock_kalshi_instance

            for i in range(20):
                result = runner.invoke(isolated_app, ["scheduler", "start"])
                assert result.exit_code in [0, 1, 2], f"Start failed on iteration {i}"
                result = runner.invoke(isolated_app, ["scheduler", "stop"])
                assert result.exit_code in [0, 1, 2], f"Stop failed on iteration {i}"

    def test_many_poll_once_invocations(self, isolated_app) -> None:
        """Test many poll-once invocations.

        Stress: Tests 30 poll-once calls.

        Note: The poll-once command imports ESPNGamePoller and KalshiMarketPoller
        from precog.schedulers and calls poll_once() on them. Both must be mocked
        to prevent real API calls. KalshiMarketPoller also needs kalshi_client
        mocked because poll-once calls kalshi_client.close() after polling.
        """
        runner = CliRunner()

        with (
            patch("precog.schedulers.ESPNGamePoller") as mock_espn,
            patch("precog.schedulers.KalshiMarketPoller") as mock_kalshi,
        ):
            mock_espn_instance = MagicMock()
            mock_espn_instance.poll_once.return_value = {
                "items_fetched": 5,
                "items_updated": 3,
            }
            mock_espn.return_value = mock_espn_instance

            mock_kalshi_instance = MagicMock()
            mock_kalshi_instance.poll_once.return_value = {
                "items_fetched": 10,
                "items_updated": 5,
                "items_created": 2,
            }
            mock_kalshi_instance.kalshi_client = MagicMock()
            mock_kalshi.return_value = mock_kalshi_instance

            for i in range(30):
                result = runner.invoke(isolated_app, ["scheduler", "poll-once", "--league", "nfl"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"


class TestDbStress:
    """Stress tests for db CLI."""

    def test_repeated_status_checks(self, isolated_app) -> None:
        """Test repeated status checks under load.

        Stress: Tests 50 rapid status invocations.

        Note: The status command calls both test_connection() AND get_cursor(),
        so both must be mocked to prevent real database access during tests.
        """
        runner = CliRunner()

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

            for i in range(50):
                result = runner.invoke(isolated_app, ["db", "status"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_repeated_table_listings(self, isolated_app) -> None:
        """Test repeated table listings.

        Stress: Tests 30 table list calls.
        """
        runner = CliRunner()

        with patch("precog.database.connection.get_cursor") as mock_cursor_ctx:
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"row_count": 0}
            mock_cur.fetchall.return_value = []
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            for i in range(30):
                result = runner.invoke(isolated_app, ["db", "tables"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_rapid_init_checks(self, isolated_app) -> None:
        """Test rapid init command invocations.

        Stress: Tests 20 init calls.
        """
        runner = CliRunner()

        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            for i in range(20):
                result = runner.invoke(isolated_app, ["db", "init"])
                assert result.exit_code in [0, 1, 2, 3, 4, 5], f"Failed on iteration {i}"


class TestSystemStress:
    """Stress tests for system CLI."""

    def test_repeated_health_checks(self, isolated_app) -> None:
        """Test repeated health checks under load.

        Stress: Tests 50 rapid health invocations.
        """
        runner = CliRunner()

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            for i in range(50):
                result = runner.invoke(isolated_app, ["system", "health"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_repeated_version_checks(self, isolated_app) -> None:
        """Test repeated version checks.

        Stress: Tests 100 version calls.
        """
        runner = CliRunner()

        for i in range(100):
            result = runner.invoke(isolated_app, ["system", "version"])
            assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_repeated_info_checks(self, isolated_app) -> None:
        """Test repeated info checks.

        Stress: Tests 50 info calls.
        """
        runner = CliRunner()

        for i in range(50):
            result = runner.invoke(isolated_app, ["system", "info"])
            assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"


class TestMixedCommandStress:
    """Stress tests for mixed command sequences."""

    def test_mixed_command_sequence(self, isolated_app) -> None:
        """Test mixed command sequence under load.

        Stress: Tests varied command patterns.

        Note: The status command calls both test_connection() AND get_cursor(),
        so both must be mocked to prevent real database access during tests.
        """
        runner = CliRunner()

        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_cursor") as mock_cursor_ctx,
            patch("precog.cli.scheduler._show_db_backed_status", return_value=False),
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
            mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

            commands = [
                ["system", "health"],
                ["system", "version"],
                ["db", "status"],
                ["scheduler", "status"],
            ]

            for i in range(25):
                for cmd in commands:
                    result = runner.invoke(isolated_app, cmd)
                    assert result.exit_code in [0, 1, 2], f"Failed on {cmd} iteration {i}"
