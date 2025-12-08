"""
Unit tests for ServiceSupervisor module.

Tests the production-grade service management infrastructure including
health monitoring, automatic restart, circuit breaker, and metrics aggregation.

Test Categories:
    1. Configuration Tests - Environment, ServiceConfig, RunnerConfig
    2. ServiceState Tests - State tracking for managed services
    3. ServiceSupervisor Core Tests - Lifecycle management
    4. Health Monitoring Tests - Health checks and alerts
    5. Auto-Restart Tests - Exponential backoff and circuit breaker
    6. Metrics Tests - Aggregation and output
    7. Factory Tests - create_services, create_supervisor

Educational Note:
    Unit tests for supervisor patterns focus on:
    - Isolation: Mock all external services
    - State verification: Check state transitions
    - Error paths: Verify graceful degradation
    - Thread safety: Use Events for synchronization

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern)
Requirements: REQ-DATA-001, REQ-OBSERV-001, REQ-TEST-001
"""

import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceState,
    ServiceSupervisor,
    create_services,
    create_supervisor,
)

# =============================================================================
# Test Fixtures
# =============================================================================


class MockService:
    """
    Mock service implementing EventLoopService protocol.

    Provides controllable behavior for testing supervisor logic
    without needing real services.

    Educational Note:
        Mock services should be configurable to simulate:
        - Normal operation (start/stop work)
        - Failures (start raises exception)
        - Errors (get_stats returns error counts)
        - Hangs (is_running returns False unexpectedly)
    """

    def __init__(
        self,
        fail_on_start: bool = False,
        error_count: int = 0,
        polls_completed: int = 0,
    ) -> None:
        """Initialize mock service with configurable behavior."""
        self._running = False
        self._fail_on_start = fail_on_start
        self._error_count = error_count
        self._polls_completed = polls_completed
        self._start_count = 0
        self._stop_count = 0

    def start(self) -> None:
        """Start the mock service."""
        self._start_count += 1
        if self._fail_on_start:
            raise RuntimeError("Simulated start failure")
        self._running = True

    def stop(self) -> None:
        """Stop the mock service."""
        self._stop_count += 1
        self._running = False

    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "errors": self._error_count,
            "polls_completed": self._polls_completed,
            "running": self._running,
        }

    def simulate_crash(self) -> None:
        """Simulate a service crash (for testing health checks)."""
        self._running = False

    def simulate_errors(self, count: int) -> None:
        """Add errors to the service (for testing alert thresholds)."""
        self._error_count += count


@pytest.fixture
def mock_service() -> MockService:
    """Create a standard mock service for testing."""
    return MockService()


@pytest.fixture
def failing_service() -> MockService:
    """Create a service that fails on start."""
    return MockService(fail_on_start=True)


@pytest.fixture
def service_config() -> ServiceConfig:
    """Create a standard service configuration."""
    return ServiceConfig(
        name="Test Service",
        enabled=True,
        poll_interval=15,
        max_retries=3,
        retry_delay=1,  # Short for testing
        alert_threshold=5,
    )


@pytest.fixture
def runner_config() -> RunnerConfig:
    """Create a runner configuration for testing."""
    return RunnerConfig(
        environment=Environment.DEVELOPMENT,
        log_level="DEBUG",
        log_dir=Path("/tmp/test_logs"),
        health_check_interval=1,  # Short for testing
        metrics_interval=1,  # Short for testing
    )


@pytest.fixture
def supervisor(runner_config: RunnerConfig) -> ServiceSupervisor:
    """Create a supervisor for testing."""
    return ServiceSupervisor(runner_config)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestEnvironment:
    """Tests for Environment enum.

    Educational Note:
        Environment-aware configuration enables different behaviors
        for development, staging, and production deployments.
    """

    def test_environment_values(self) -> None:
        """Verify all environment values are correct strings."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"

    def test_environment_from_string(self) -> None:
        """Verify environment can be created from string value."""
        assert Environment("development") == Environment.DEVELOPMENT
        assert Environment("staging") == Environment.STAGING
        assert Environment("production") == Environment.PRODUCTION

    def test_environment_invalid_value_raises(self) -> None:
        """Verify invalid environment value raises ValueError."""
        with pytest.raises(ValueError):
            Environment("invalid")


class TestServiceConfig:
    """Tests for ServiceConfig dataclass.

    Educational Note:
        Service configuration should have sensible defaults
        while allowing customization per service type.
    """

    def test_service_config_defaults(self) -> None:
        """Verify ServiceConfig has correct defaults."""
        config = ServiceConfig(name="test")
        assert config.name == "test"
        assert config.enabled is True
        assert config.poll_interval == 15
        assert config.max_retries == 3
        assert config.retry_delay == 5
        assert config.alert_threshold == 5

    def test_service_config_custom_values(self) -> None:
        """Verify ServiceConfig accepts custom values."""
        config = ServiceConfig(
            name="custom",
            enabled=False,
            poll_interval=30,
            max_retries=5,
            retry_delay=10,
            alert_threshold=10,
        )
        assert config.name == "custom"
        assert config.enabled is False
        assert config.poll_interval == 30
        assert config.max_retries == 5
        assert config.retry_delay == 10
        assert config.alert_threshold == 10


class TestRunnerConfig:
    """Tests for RunnerConfig dataclass.

    Educational Note:
        Runner configuration provides global settings that apply
        to all services, with per-service overrides possible.
    """

    def test_runner_config_defaults(self) -> None:
        """Verify RunnerConfig has correct defaults."""
        config = RunnerConfig()
        assert config.environment == Environment.DEVELOPMENT
        assert config.log_level == "INFO"
        assert config.log_dir == Path("logs")
        assert config.log_max_bytes == 10 * 1024 * 1024
        assert config.log_backup_count == 5
        assert config.health_check_interval == 60
        assert config.metrics_interval == 300

    def test_runner_config_default_services(self) -> None:
        """Verify RunnerConfig creates default services."""
        config = RunnerConfig()
        assert "espn" in config.services
        assert "kalshi_rest" in config.services
        assert "kalshi_ws" in config.services

    def test_runner_config_custom_services(self) -> None:
        """Verify RunnerConfig accepts custom services."""
        custom_services = {
            "custom": ServiceConfig(name="Custom Service"),
        }
        config = RunnerConfig(services=custom_services)
        assert "custom" in config.services
        assert "espn" not in config.services


# =============================================================================
# ServiceState Tests
# =============================================================================


class TestServiceState:
    """Tests for ServiceState dataclass.

    Educational Note:
        ServiceState tracks runtime information separately from
        the service itself, enabling restart without losing history.
    """

    def test_service_state_defaults(self) -> None:
        """Verify ServiceState has correct defaults."""
        state = ServiceState()
        assert state.service is None
        assert state.config is None
        assert state.started_at is None
        assert state.last_health_check is None
        assert state.error_count == 0
        assert state.restart_count == 0
        assert state.consecutive_failures == 0
        assert state.last_error is None
        assert state.healthy is True

    def test_service_state_with_service(self, mock_service: MockService) -> None:
        """Verify ServiceState can hold a service instance."""
        state = ServiceState(service=mock_service)
        assert state.service is mock_service

    def test_service_state_tracks_errors(self) -> None:
        """Verify ServiceState tracks error counts."""
        state = ServiceState(error_count=5)
        assert state.error_count == 5
        state.error_count += 1
        assert state.error_count == 6


# =============================================================================
# ServiceSupervisor Core Tests
# =============================================================================


class TestServiceSupervisorCore:
    """Tests for ServiceSupervisor core functionality.

    Educational Note:
        Core tests verify basic lifecycle operations work correctly
        in isolation, without threading or timing concerns.
    """

    def test_supervisor_initialization(self, runner_config: RunnerConfig) -> None:
        """Verify supervisor initializes correctly."""
        supervisor = ServiceSupervisor(runner_config)
        assert supervisor.config == runner_config
        assert len(supervisor.services) == 0
        assert supervisor.is_running is False
        assert supervisor.uptime_seconds == 0.0

    def test_add_service(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify services can be added to supervisor."""
        supervisor.add_service("test", mock_service, service_config)
        assert "test" in supervisor.services
        assert supervisor.services["test"].service is mock_service
        assert supervisor.services["test"].config is service_config

    def test_remove_service(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify services can be removed from supervisor."""
        supervisor.add_service("test", mock_service, service_config)
        result = supervisor.remove_service("test")
        assert result is True
        assert "test" not in supervisor.services

    def test_remove_nonexistent_service(self, supervisor: ServiceSupervisor) -> None:
        """Verify removing nonexistent service returns False."""
        result = supervisor.remove_service("nonexistent")
        assert result is False

    def test_remove_running_service_stops_it(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify removing a running service stops it first."""
        supervisor.add_service("test", mock_service, service_config)
        mock_service.start()
        assert mock_service.is_running()

        supervisor.remove_service("test")
        assert not mock_service.is_running()
        assert mock_service._stop_count == 1

    def test_is_running_property(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify is_running property tracks supervisor state."""
        supervisor.add_service("test", mock_service, service_config)
        assert supervisor.is_running is False

        supervisor.start_all()
        assert supervisor.is_running is True

        supervisor.stop_all()
        assert supervisor.is_running is False

    def test_uptime_seconds_increases(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify uptime_seconds increases while running."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()

        time.sleep(0.1)
        uptime = supervisor.uptime_seconds
        assert uptime > 0

        time.sleep(0.1)
        assert supervisor.uptime_seconds > uptime

        supervisor.stop_all()


class TestServiceSupervisorStartStop:
    """Tests for start/stop behavior.

    Educational Note:
        Start/stop tests verify proper service lifecycle management,
        including error isolation (one service failing shouldn't block others).
    """

    def test_start_all_starts_services(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify start_all starts all services."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()

        assert mock_service.is_running()
        assert mock_service._start_count == 1
        supervisor.stop_all()

    def test_start_all_skips_disabled_services(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
    ) -> None:
        """Verify start_all skips disabled services."""
        config = ServiceConfig(name="disabled", enabled=False)
        supervisor.add_service("test", mock_service, config)
        supervisor.start_all()

        assert not mock_service.is_running()
        assert mock_service._start_count == 0
        supervisor.stop_all()

    def test_start_all_isolates_failures(
        self, supervisor: ServiceSupervisor, service_config: ServiceConfig
    ) -> None:
        """Verify one service failure doesn't block others.

        Educational Note:
            Error isolation is critical for resilient systems.
            A failing ESPN poller shouldn't prevent Kalshi from starting.
        """
        good_service = MockService()
        bad_service = MockService(fail_on_start=True)

        supervisor.add_service("good", good_service, service_config)
        supervisor.add_service("bad", bad_service, service_config)

        supervisor.start_all()

        assert good_service.is_running()
        assert not bad_service.is_running()
        assert supervisor.services["bad"].healthy is False
        assert supervisor.services["bad"].last_error is not None
        supervisor.stop_all()

    def test_stop_all_stops_services(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify stop_all stops all services."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()
        assert mock_service.is_running()

        supervisor.stop_all()
        assert not mock_service.is_running()
        assert mock_service._stop_count == 1

    def test_stop_all_clears_uptime(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify stop_all clears uptime."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()
        time.sleep(0.1)
        assert supervisor.uptime_seconds > 0

        supervisor.stop_all()
        assert supervisor.uptime_seconds == 0


# =============================================================================
# Health Monitoring Tests
# =============================================================================


class TestHealthMonitoring:
    """Tests for health check functionality.

    Educational Note:
        Health monitoring runs in a background thread, checking each
        service periodically. Tests must be carefully synchronized
        to avoid race conditions.
    """

    def test_health_check_detects_crash(
        self, runner_config: RunnerConfig, service_config: ServiceConfig
    ) -> None:
        """Verify health check detects crashed service."""
        supervisor = ServiceSupervisor(runner_config)
        mock_service = MockService()
        supervisor.add_service("test", mock_service, service_config)

        supervisor.start_all()
        assert supervisor.services["test"].healthy is True

        # Simulate crash
        mock_service.simulate_crash()
        time.sleep(1.5)  # Wait for health check

        assert supervisor.services["test"].healthy is False
        assert supervisor.services["test"].consecutive_failures >= 1
        supervisor.stop_all()

    def test_health_check_updates_timestamp(
        self, runner_config: RunnerConfig, service_config: ServiceConfig
    ) -> None:
        """Verify health check updates last_health_check timestamp."""
        supervisor = ServiceSupervisor(runner_config)
        mock_service = MockService()
        supervisor.add_service("test", mock_service, service_config)

        supervisor.start_all()
        time.sleep(1.5)  # Wait for health check

        assert supervisor.services["test"].last_health_check is not None
        supervisor.stop_all()


# =============================================================================
# Auto-Restart Tests
# =============================================================================


class TestAutoRestart:
    """Tests for automatic restart with exponential backoff.

    Educational Note:
        Auto-restart implements exponential backoff to prevent
        rapid restart loops that could overwhelm the system.
        After max_retries, the circuit breaker activates.
    """

    def test_restart_after_crash(
        self, runner_config: RunnerConfig, service_config: ServiceConfig
    ) -> None:
        """Verify service is restarted after crash."""
        # Use very short intervals for testing
        service_config.retry_delay = 1  # 1 second base delay
        service_config.max_retries = 3

        supervisor = ServiceSupervisor(runner_config)
        mock_service = MockService()
        supervisor.add_service("test", mock_service, service_config)

        supervisor.start_all()
        assert mock_service._start_count == 1

        # Simulate crash
        mock_service.simulate_crash()
        # Wait for health check (1s interval) + retry delay (1s) + buffer
        time.sleep(4)

        # Service should have been restarted
        assert mock_service._start_count >= 2
        supervisor.stop_all()

    def test_circuit_breaker_after_max_retries(self, runner_config: RunnerConfig) -> None:
        """Verify circuit breaker stops restarts after max_retries.

        Educational Note:
            The circuit breaker pattern prevents infinite restart loops.
            After max_retries failures, the supervisor gives up and
            triggers an alert instead.

            Key Test Design: We must make the service FAIL on restart attempts,
            not just crash. If restart succeeds, consecutive_failures resets to 0
            and the circuit breaker never triggers.
        """
        config = ServiceConfig(
            name="test",
            max_retries=2,
            retry_delay=1,
            alert_threshold=1,
        )

        supervisor = ServiceSupervisor(runner_config)
        mock_service = MockService()
        supervisor.add_service("test", mock_service, config)

        # Record alerts
        alerts: list[tuple[str, str, dict[str, Any]]] = []
        supervisor.register_alert_callback(lambda name, msg, ctx: alerts.append((name, msg, ctx)))

        supervisor.start_all()
        assert mock_service._start_count == 1

        # Make subsequent restart attempts fail (this is the key!)
        # Without this, restart succeeds and consecutive_failures resets to 0
        mock_service._fail_on_start = True

        # Simulate crash - health check will try to restart, but it will fail
        mock_service.simulate_crash()

        # Wait for health check (1s) + multiple restart attempts with backoff
        # With max_retries=2 and retry_delay=1, we need:
        # - Health check detects crash (~1s)
        # - Attempt 1 fails (~1s delay)
        # - Attempt 2 fails (~2s delay with backoff)
        # - Attempt 3 fails, circuit breaker triggers
        time.sleep(6)

        # Should have stopped trying after max_retries (consecutive_failures >= 2)
        # Circuit breaker triggers AT max_retries, not after exceeding it
        state = supervisor.services["test"]
        assert state.consecutive_failures >= config.max_retries

        supervisor.stop_all()


# =============================================================================
# Alert Callback Tests
# =============================================================================


class TestAlertCallbacks:
    """Tests for alert callback functionality.

    Educational Note:
        Alert callbacks enable integration with external monitoring
        systems (Slack, PagerDuty, etc.) without coupling the
        supervisor to specific notification providers.
    """

    def test_register_alert_callback(self, supervisor: ServiceSupervisor) -> None:
        """Verify alert callbacks can be registered."""
        callback = MagicMock()
        supervisor.register_alert_callback(callback)
        assert callback in supervisor._alert_callbacks

    def test_alert_triggered_on_error_threshold(
        self, runner_config: RunnerConfig, service_config: ServiceConfig
    ) -> None:
        """Verify alert is triggered when error threshold exceeded."""
        service_config.alert_threshold = 3

        supervisor = ServiceSupervisor(runner_config)
        mock_service = MockService()
        supervisor.add_service("test", mock_service, service_config)

        alerts: list[tuple[str, str, dict[str, Any]]] = []
        supervisor.register_alert_callback(lambda name, msg, ctx: alerts.append((name, msg, ctx)))

        supervisor.start_all()

        # Add errors above threshold
        mock_service.simulate_errors(5)
        time.sleep(1.5)  # Wait for health check

        # Alert should have been triggered
        assert len(alerts) > 0
        assert alerts[0][0] == "test"
        supervisor.stop_all()

    def test_alert_callback_error_handled(
        self, supervisor: ServiceSupervisor, mock_service: MockService
    ) -> None:
        """Verify failing alert callback doesn't crash supervisor."""

        def failing_callback(name: str, msg: str, ctx: dict[str, Any]) -> None:
            raise RuntimeError("Callback failed!")

        supervisor.register_alert_callback(failing_callback)

        # This should not raise
        supervisor._trigger_alert("test", "Test alert", {})


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMetrics:
    """Tests for metrics aggregation.

    Educational Note:
        Metrics provide visibility into service health and performance.
        Aggregate metrics enable monitoring dashboards to track
        overall system health at a glance.
    """

    def test_get_aggregate_metrics_empty(self, supervisor: ServiceSupervisor) -> None:
        """Verify aggregate metrics with no services."""
        metrics = supervisor.get_aggregate_metrics()
        assert metrics["services_total"] == 0
        assert metrics["services_healthy"] == 0
        assert metrics["total_restarts"] == 0
        assert metrics["total_errors"] == 0

    def test_get_aggregate_metrics_with_services(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify aggregate metrics with services."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()

        metrics = supervisor.get_aggregate_metrics()
        assert metrics["services_total"] == 1
        assert metrics["services_healthy"] == 1
        assert metrics["uptime_seconds"] > 0
        assert "test" in metrics["per_service"]

        supervisor.stop_all()

    def test_aggregate_metrics_tracks_errors(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify aggregate metrics includes error counts."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.services["test"].error_count = 5

        metrics = supervisor.get_aggregate_metrics()
        assert metrics["total_errors"] == 5


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateServices:
    """Tests for create_services factory function.

    Educational Note:
        Factory functions centralize service creation, making it easy
        to add new services or mock services for testing.
    """

    @patch.dict("os.environ", {"KALSHI_API_KEY_ID": ""}, clear=False)
    def test_create_services_espn_only(self) -> None:
        """Verify create_services creates ESPN service when no Kalshi creds."""
        config = RunnerConfig()
        services = create_services(config, enabled_services={"espn"})

        assert "espn" in services
        assert "kalshi_rest" not in services
        assert "kalshi_ws" not in services

    def test_create_services_filters_by_enabled(self) -> None:
        """Verify create_services respects enabled_services filter."""
        config = RunnerConfig()
        services = create_services(config, enabled_services={"espn"})

        assert "espn" in services
        # Other services should be disabled
        assert config.services["kalshi_rest"].enabled is False
        assert config.services["kalshi_ws"].enabled is False


class TestCreateSupervisor:
    """Tests for create_supervisor factory function.

    Educational Note:
        The create_supervisor function provides a convenient way to
        create a fully configured supervisor in one call.
    """

    @patch("precog.schedulers.service_supervisor.create_services")
    def test_create_supervisor_with_defaults(self, mock_create_services: MagicMock) -> None:
        """Verify create_supervisor uses correct defaults."""
        mock_create_services.return_value = {}

        supervisor = create_supervisor()

        assert supervisor.config.environment == Environment.DEVELOPMENT
        assert supervisor.config.health_check_interval == 60
        assert supervisor.config.metrics_interval == 300

    @patch("precog.schedulers.service_supervisor.create_services")
    def test_create_supervisor_with_custom_values(self, mock_create_services: MagicMock) -> None:
        """Verify create_supervisor accepts custom values."""
        mock_create_services.return_value = {}

        supervisor = create_supervisor(
            environment="production",
            poll_interval=30,
            health_check_interval=120,
            metrics_interval=600,
        )

        assert supervisor.config.environment == Environment.PRODUCTION
        assert supervisor.config.health_check_interval == 120
        assert supervisor.config.metrics_interval == 600


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Tests for thread safety of supervisor operations.

    Educational Note:
        The supervisor uses multiple threads (health check, metrics).
        These tests verify that concurrent access doesn't cause
        race conditions or deadlocks.
    """

    def test_concurrent_get_metrics(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify concurrent metric access is safe."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()

        errors: list[Exception] = []

        def get_metrics_loop() -> None:
            try:
                for _ in range(100):
                    supervisor.get_aggregate_metrics()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_metrics_loop) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        supervisor.stop_all()
        assert len(errors) == 0

    def test_trigger_shutdown_from_thread(
        self,
        supervisor: ServiceSupervisor,
        mock_service: MockService,
        service_config: ServiceConfig,
    ) -> None:
        """Verify trigger_shutdown works from any thread."""
        supervisor.add_service("test", mock_service, service_config)
        supervisor.start_all()

        def shutdown_from_thread() -> None:
            time.sleep(0.5)
            supervisor.trigger_shutdown()

        shutdown_thread = threading.Thread(target=shutdown_from_thread)
        shutdown_thread.start()

        # This should return when shutdown is triggered
        supervisor.wait_for_shutdown()
        shutdown_thread.join()

        supervisor.stop_all()
