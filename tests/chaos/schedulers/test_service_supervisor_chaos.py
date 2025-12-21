"""
Chaos tests for service_supervisor module.

Tests failure scenarios and edge cases.

Reference: TESTING_STRATEGY_V3.2.md Section "Chaos Tests"
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceState,
    ServiceSupervisor,
)

pytestmark = [pytest.mark.chaos]


class MockService:
    """Mock service for testing."""

    def __init__(self, fail_on_start: bool = False, fail_on_stop: bool = False) -> None:
        self._running = False
        self._stats: dict[str, Any] = {"errors": 0}
        self._fail_on_start = fail_on_start
        self._fail_on_stop = fail_on_stop

    def start(self) -> None:
        if self._fail_on_start:
            raise RuntimeError("Service start failed")
        self._running = True

    def stop(self) -> None:
        if self._fail_on_stop:
            raise RuntimeError("Service stop failed")
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict[str, Any]:
        return self._stats.copy()


class TestServiceFailureChaos:
    """Chaos tests for service failure scenarios."""

    def test_service_start_failure(self) -> None:
        """Test handling of service start failure."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        # Add a service that fails on start
        failing_service = MockService(fail_on_start=True)
        svc_config = ServiceConfig(name="failing", enabled=True)
        supervisor.add_service("failing", failing_service, svc_config)

        # Start should not raise
        supervisor.start_all()

        # Service should be marked unhealthy
        state = supervisor.services["failing"]
        assert state.healthy is False
        assert state.consecutive_failures > 0

        supervisor.stop_all()

    def test_service_stop_failure(self) -> None:
        """Test handling of service stop failure."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        # Add a service that fails on stop
        failing_service = MockService(fail_on_stop=True)
        failing_service._running = True  # Pretend it's running
        svc_config = ServiceConfig(name="failing", enabled=True)
        supervisor.add_service("failing", failing_service, svc_config)

        # Stop should not raise (errors are logged)
        supervisor.stop_all()

    def test_all_services_fail(self) -> None:
        """Test handling when all services fail to start."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        # Add multiple failing services
        for i in range(5):
            failing_service = MockService(fail_on_start=True)
            svc_config = ServiceConfig(name=f"failing_{i}", enabled=True)
            supervisor.add_service(f"failing_{i}", failing_service, svc_config)

        # Start should not raise
        supervisor.start_all()

        # All should be unhealthy
        for name, state in supervisor.services.items():
            assert state.healthy is False

        supervisor.stop_all()


class TestAlertCallbackChaos:
    """Chaos tests for alert callbacks."""

    def test_alert_callback_raises_exception(self) -> None:
        """Test handling when alert callback raises exception."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        def failing_callback(name: str, msg: str, ctx: dict) -> None:
            raise RuntimeError("Callback failed")

        supervisor.register_alert_callback(failing_callback)

        # Should not raise, error is logged
        supervisor._trigger_alert("test", "Test alert", {})

    def test_multiple_callbacks_some_fail(self) -> None:
        """Test handling when some callbacks fail."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)
        successful_calls = []

        def failing_callback(name: str, msg: str, ctx: dict) -> None:
            raise RuntimeError("Callback failed")

        def successful_callback(name: str, msg: str, ctx: dict) -> None:
            successful_calls.append((name, msg))

        supervisor.register_alert_callback(failing_callback)
        supervisor.register_alert_callback(successful_callback)
        supervisor.register_alert_callback(failing_callback)
        supervisor.register_alert_callback(successful_callback)

        # Should continue to other callbacks despite failures
        supervisor._trigger_alert("test", "Test alert", {})

        assert len(successful_calls) == 2


class TestConfigurationChaos:
    """Chaos tests for configuration edge cases."""

    def test_empty_services_config(self) -> None:
        """Test supervisor with no services."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
            services={},  # Empty services
        )
        supervisor = ServiceSupervisor(config)

        # Should work with no services
        supervisor.start_all()
        metrics = supervisor.get_aggregate_metrics()
        assert metrics["services_total"] == 0
        supervisor.stop_all()

    def test_zero_intervals(self) -> None:
        """Test config with zero intervals."""
        # Zero intervals should be allowed (though not recommended)
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=0,
            metrics_interval=0,
        )
        ServiceSupervisor(config)

        assert config.health_check_interval == 0
        assert config.metrics_interval == 0

    def test_negative_intervals(self) -> None:
        """Test config with negative intervals (edge case)."""
        # Negative intervals are technically allowed by dataclass
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=-1,
            metrics_interval=-1,
        )
        ServiceSupervisor(config)

        assert config.health_check_interval == -1


class TestServiceStateChaos:
    """Chaos tests for ServiceState edge cases."""

    def test_state_with_none_service(self) -> None:
        """Test ServiceState with None service."""
        state = ServiceState(service=None, config=None)

        assert state.service is None
        assert state.config is None
        assert state.healthy is True  # Default

    def test_state_with_none_config(self) -> None:
        """Test ServiceState with None config."""
        service = MockService()
        state = ServiceState(service=service, config=None)

        assert state.service is not None
        assert state.config is None


class TestRemoveServiceChaos:
    """Chaos tests for service removal."""

    def test_remove_nonexistent_service(self) -> None:
        """Test removing nonexistent service."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        result = supervisor.remove_service("nonexistent")

        assert result is False

    def test_remove_running_service(self) -> None:
        """Test removing a running service."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        service = MockService()
        service._running = True
        svc_config = ServiceConfig(name="test", enabled=True)
        supervisor.add_service("test", service, svc_config)

        result = supervisor.remove_service("test")

        assert result is True
        assert not service._running  # Service should be stopped


class TestHealthCheckChaos:
    """Chaos tests for health check scenarios."""

    def test_check_health_with_disabled_service(self) -> None:
        """Test health check with disabled service."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        service = MockService()
        svc_config = ServiceConfig(name="disabled", enabled=False)
        supervisor.add_service("disabled", service, svc_config)

        state = supervisor.services["disabled"]

        # Health check should skip disabled services
        supervisor._check_service_health("disabled", state)

        # State should be unchanged (defaults)
        assert state.healthy is True

    def test_check_health_with_none_service(self) -> None:
        """Test health check with None service."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        state = ServiceState(service=None, config=ServiceConfig(name="none"))
        supervisor.services["none"] = state

        # Should not raise
        supervisor._check_service_health("none", state)


class TestMetricsChaos:
    """Chaos tests for metrics scenarios."""

    def test_metrics_with_stopped_services(self) -> None:
        """Test metrics when services are stopped."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        service = MockService()
        service._running = False
        svc_config = ServiceConfig(name="stopped", enabled=True)
        supervisor.add_service("stopped", service, svc_config)

        metrics = supervisor.get_aggregate_metrics()

        assert metrics["services_total"] == 1
        # Stopped services don't contribute stats
        assert metrics["per_service"]["stopped"]["stats"] == {}

    def test_metrics_with_exception_in_get_stats(self) -> None:
        """Test metrics when get_stats raises exception."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        service = MockService()
        service._running = True
        object.__setattr__(service, "get_stats", MagicMock(side_effect=RuntimeError("Stats error")))
        svc_config = ServiceConfig(name="broken", enabled=True)
        supervisor.add_service("broken", service, svc_config)

        # Should handle gracefully
        try:
            metrics = supervisor.get_aggregate_metrics()
            # Either returns without stats or raises
            assert "per_service" in metrics
        except RuntimeError:
            pass  # Also acceptable


class TestShutdownChaos:
    """Chaos tests for shutdown scenarios."""

    def test_shutdown_before_start(self) -> None:
        """Test shutdown before services started."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        service = MockService()
        svc_config = ServiceConfig(name="test", enabled=True)
        supervisor.add_service("test", service, svc_config)

        # Should not raise
        supervisor.stop_all()

    def test_double_shutdown(self) -> None:
        """Test calling shutdown twice."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        service = MockService()
        svc_config = ServiceConfig(name="test", enabled=True)
        supervisor.add_service("test", service, svc_config)

        supervisor.start_all()
        supervisor.stop_all()
        supervisor.stop_all()  # Second call should not raise

    def test_trigger_shutdown_multiple_times(self) -> None:
        """Test triggering shutdown multiple times."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        supervisor.start_all()

        # Multiple triggers should be safe
        for _ in range(10):
            supervisor.trigger_shutdown()

        assert supervisor._shutdown_event.is_set()

        supervisor.stop_all()
