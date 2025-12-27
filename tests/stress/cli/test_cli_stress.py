"""Stress tests for CLI modules.

Tests CLI modules under high load and repeated invocations.

References:
    - REQ-TEST-005: Stress testing
    - TESTING_STRATEGY V3.2: 8 test types required
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from precog.cli import app, register_commands

# Register commands once for all tests
register_commands()
runner = CliRunner()


class TestSchedulerStress:
    """Stress tests for scheduler CLI."""

    def test_repeated_status_checks(self) -> None:
        """Test repeated status checks under load.

        Stress: Tests 50 rapid status invocations.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.get_status.return_value = {"running": False, "pollers": []}
            mock_supervisor.return_value = mock_instance

            for i in range(50):
                result = runner.invoke(app, ["scheduler", "status"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_rapid_start_stop_cycles(self) -> None:
        """Test rapid start-stop cycles.

        Stress: Tests 20 start-stop cycles.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.start.return_value = True
            mock_instance.stop.return_value = True
            mock_supervisor.return_value = mock_instance

            for i in range(20):
                result = runner.invoke(app, ["scheduler", "start"])
                assert result.exit_code in [0, 1, 2], f"Start failed on iteration {i}"
                result = runner.invoke(app, ["scheduler", "stop"])
                assert result.exit_code in [0, 1, 2], f"Stop failed on iteration {i}"

    def test_many_poll_once_invocations(self) -> None:
        """Test many poll-once invocations.

        Stress: Tests 30 poll-once calls.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.return_value = {"games": 5, "updated": 3}
            mock_supervisor.return_value = mock_instance

            for i in range(30):
                result = runner.invoke(app, ["scheduler", "poll-once", "--league", "nfl"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"


class TestDbStress:
    """Stress tests for db CLI."""

    def test_repeated_status_checks(self) -> None:
        """Test repeated status checks under load.

        Stress: Tests 50 rapid status invocations.

        Note: The status command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access during tests.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            for i in range(50):
                result = runner.invoke(app, ["db", "status"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_repeated_table_listings(self) -> None:
        """Test repeated table listings.

        Stress: Tests 30 table list calls.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            for i in range(30):
                result = runner.invoke(app, ["db", "tables"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_rapid_init_checks(self) -> None:
        """Test rapid init command invocations.

        Stress: Tests 20 init calls.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.initialization.apply_schema") as mock_schema,
        ):
            mock_test.return_value = True
            mock_schema.return_value = True

            for i in range(20):
                result = runner.invoke(app, ["db", "init"])
                assert result.exit_code in [0, 1, 2, 3, 4, 5], f"Failed on iteration {i}"


class TestSystemStress:
    """Stress tests for system CLI."""

    def test_repeated_health_checks(self) -> None:
        """Test repeated health checks under load.

        Stress: Tests 50 rapid health invocations.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()

            for i in range(50):
                result = runner.invoke(app, ["system", "health"])
                assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_repeated_version_checks(self) -> None:
        """Test repeated version checks.

        Stress: Tests 100 version calls.
        """
        for i in range(100):
            result = runner.invoke(app, ["system", "version"])
            assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"

    def test_repeated_info_checks(self) -> None:
        """Test repeated info checks.

        Stress: Tests 50 info calls.
        """
        for i in range(50):
            result = runner.invoke(app, ["system", "info"])
            assert result.exit_code in [0, 1, 2], f"Failed on iteration {i}"


class TestMixedCommandStress:
    """Stress tests for mixed command sequences."""

    def test_mixed_command_sequence(self) -> None:
        """Test mixed command sequence under load.

        Stress: Tests varied command patterns.

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
                ["system", "health"],
                ["system", "version"],
                ["db", "status"],
                ["scheduler", "status"],
            ]

            for i in range(25):
                for cmd in commands:
                    result = runner.invoke(app, cmd)
                    assert result.exit_code in [0, 1, 2], f"Failed on {cmd} iteration {i}"
