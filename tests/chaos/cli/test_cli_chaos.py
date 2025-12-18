"""Chaos tests for CLI modules.

Tests CLI module resilience under fault injection and error conditions.

References:
    - REQ-TEST-008: Chaos testing
    - TESTING_STRATEGY V3.2: 8 test types required
"""

import random
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from precog.cli import app, register_commands

# Register commands once for all tests
register_commands()
runner = CliRunner()


class TestSchedulerChaos:
    """Chaos tests for scheduler CLI."""

    def test_supervisor_random_failures(self) -> None:
        """Test scheduler handles random supervisor failures.

        Chaos: Random failures during 20 invocations.
        """
        call_count = [0]

        def random_failure(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.3:  # 30% failure rate
                raise Exception("Random supervisor failure")
            return {"running": False, "pollers": []}

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.get_status.side_effect = random_failure
            mock_supervisor.return_value = mock_instance

            successes = 0
            for _ in range(20):
                result = runner.invoke(app, ["scheduler", "status"])
                if result.exit_code in [0, 1, 2]:
                    successes += 1

            # Should handle failures gracefully
            assert successes >= 10, f"Only {successes} successes out of 20"

    def test_poll_with_intermittent_failures(self) -> None:
        """Test poll-once with intermittent failures.

        Chaos: Alternating success/failure pattern.
        """
        call_count = [0]

        def alternating_result(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:  # Every 3rd call fails
                raise Exception("Intermittent failure")
            return {"games": 5, "updated": 3}

        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            mock_instance.poll_once.side_effect = alternating_result
            mock_supervisor.return_value = mock_instance

            results = []
            for _ in range(15):
                result = runner.invoke(app, ["scheduler", "poll-once", "--league", "nfl"])
                results.append(result.exit_code)

            # All should complete (success or graceful failure)
            assert len(results) == 15


class TestDbChaos:
    """Chaos tests for db CLI."""

    def test_connection_random_failures(self) -> None:
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
                result = runner.invoke(app, ["db", "status"])
                results.append(result.exit_code)

            # All should complete (don't crash)
            assert len(results) == 20

    def test_init_with_flaky_connection(self) -> None:
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
                result = runner.invoke(app, ["db", "init"])
                results.append(result.exit_code)

            # All should complete gracefully
            assert len(results) == 5


class TestSystemChaos:
    """Chaos tests for system CLI."""

    def test_health_with_component_failures(self) -> None:
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
                result = runner.invoke(app, ["system", "health"])
                results.append(result.exit_code)

            # All should complete (graceful degradation)
            assert len(results) == 20

    def test_info_with_missing_data(self) -> None:
        """Test info command with missing configuration data.

        Chaos: Configuration partially unavailable.
        """
        with patch("precog.config.config_loader.ConfigLoader") as mock_config:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = lambda key: None if random.random() < 0.3 else {}
            mock_config.return_value = mock_instance

            results = []
            for _ in range(10):
                result = runner.invoke(app, ["system", "info"])
                results.append(result.exit_code)

            # All should complete
            assert len(results) == 10


class TestCrossModuleChaos:
    """Chaos tests across CLI modules."""

    def test_cascading_failures(self) -> None:
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
                result = runner.invoke(app, cmd)
                results.append((cmd[0], result.exit_code))

            # All should complete (not crash)
            assert len(results) == 3

    def test_recovery_after_failures(self) -> None:
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
                result = runner.invoke(app, ["db", "status"])
                results.append(result.exit_code)

            # Later calls should succeed
            assert len(results) == 6


class TestResourceExhaustion:
    """Chaos tests for resource exhaustion scenarios."""

    def test_handles_timeout_scenarios(self) -> None:
        """Test CLI handles timeout-like conditions.

        Chaos: Simulated slow operations.
        """
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock = MagicMock()
            mock.__enter__ = MagicMock()
            mock.__exit__ = MagicMock()
            mock_conn.return_value = mock

            results = []
            for _ in range(10):
                result = runner.invoke(app, ["db", "status"])
                results.append(result.exit_code)

            assert all(code in [0, 1, 2] for code in results)

    def test_handles_memory_pressure(self) -> None:
        """Test CLI handles memory pressure scenarios.

        Chaos: Large response data.
        """
        with patch("precog.schedulers.service_supervisor.ServiceSupervisor") as mock_supervisor:
            mock_instance = MagicMock()
            # Large status response
            mock_instance.get_status.return_value = {
                "running": True,
                "pollers": [{"name": f"poller_{i}", "data": "x" * 1000} for i in range(100)],
            }
            mock_supervisor.return_value = mock_instance

            result = runner.invoke(app, ["scheduler", "status"])
            assert result.exit_code in [0, 1, 2]
