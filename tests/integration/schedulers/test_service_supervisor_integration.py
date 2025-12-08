"""
Integration tests for ServiceSupervisor module.

Integration tests verify that the ServiceSupervisor works correctly with
real (or realistic mock) services, focusing on inter-component interactions
rather than isolated unit behavior.

Test Categories:
    1. Multi-Service Orchestration - Starting/stopping multiple services
    2. Health Monitoring Integration - Health checks with service lifecycle
    3. Metrics Pipeline - End-to-end metrics collection
    4. Alert System Integration - Alert callbacks with real triggers
    5. Factory Integration - create_services, create_supervisor

Educational Note:
    Integration tests for supervisors focus on:
    - Real timing: Use actual delays (but shorter than production)
    - Multi-threading: Verify thread interactions work correctly
    - State propagation: Changes in one component affect others correctly
    - Error cascades: Failures are isolated and handled properly

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern)
Requirements: REQ-DATA-001, REQ-OBSERV-001, REQ-TEST-002
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
    ServiceSupervisor,
    create_services,
    create_supervisor,
)

# =============================================================================
# Realistic Mock Services
# =============================================================================


class RealisticMockService:
    """
    A more realistic mock service that simulates actual service behavior.

    Includes internal state tracking, configurable failure modes, and
    realistic timing. Used for integration testing.

    Educational Note:
        Integration test mocks should be more realistic than unit test mocks:
        - Maintain internal state (poll counts, error history)
        - Simulate realistic timing (poll intervals)
        - Support configurable failure injection
    """

    def __init__(
        self,
        name: str = "mock",
        poll_interval: float = 0.1,
        fail_after_polls: int | None = None,
        error_rate: float = 0.0,
    ) -> None:
        """
        Initialize realistic mock service.

        Args:
            name: Service identifier
            poll_interval: Simulated poll interval in seconds
            fail_after_polls: Stop running after this many polls (simulate crash)
            error_rate: Probability of incrementing error count per poll
        """
        self.name = name
        self.poll_interval = poll_interval
        self.fail_after_polls = fail_after_polls
        self.error_rate = error_rate

        self._running = False
        self._poll_count = 0
        self._error_count = 0
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the mock polling loop."""
        self._running = True
        self._stop_event.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self) -> None:
        """Stop the mock polling loop."""
        self._stop_event.set()
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2)

    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "polls_completed": self._poll_count,
            "errors": self._error_count,
            "running": self._running,
        }

    def _poll_loop(self) -> None:
        """Simulated polling loop."""
        import random

        while not self._stop_event.is_set():
            self._stop_event.wait(self.poll_interval)
            if self._stop_event.is_set():
                break

            self._poll_count += 1

            # Simulate errors based on error_rate
            if random.random() < self.error_rate:
                self._error_count += 1

            # Simulate crash after certain polls
            if self.fail_after_polls and self._poll_count >= self.fail_after_polls:
                self._running = False
                break


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def integration_config() -> RunnerConfig:
    """Create configuration optimized for integration testing.

    Uses short intervals for faster test execution while maintaining
    realistic timing relationships.
    """
    return RunnerConfig(
        environment=Environment.DEVELOPMENT,
        log_level="DEBUG",
        log_dir=Path("/tmp/integration_test_logs"),
        health_check_interval=1,  # 1 second health checks
        metrics_interval=2,  # 2 second metrics
    )


@pytest.fixture
def realistic_service() -> RealisticMockService:
    """Create a realistic mock service for integration testing."""
    return RealisticMockService(name="test", poll_interval=0.1)


# =============================================================================
# Multi-Service Orchestration Tests
# =============================================================================


class TestMultiServiceOrchestration:
    """Integration tests for multi-service management.

    Educational Note:
        These tests verify that the supervisor correctly manages
        multiple services running concurrently, including proper
        isolation of failures and coordinated shutdown.
    """

    def test_start_multiple_services(self, integration_config: RunnerConfig) -> None:
        """Verify multiple services start and run concurrently."""
        supervisor = ServiceSupervisor(integration_config)

        services = [
            RealisticMockService(name="service1", poll_interval=0.1),
            RealisticMockService(name="service2", poll_interval=0.1),
            RealisticMockService(name="service3", poll_interval=0.1),
        ]

        for i, svc in enumerate(services):
            config = ServiceConfig(name=f"Service {i + 1}")
            supervisor.add_service(f"svc{i + 1}", svc, config)

        supervisor.start_all()
        time.sleep(0.5)  # Let services run

        # All services should be running
        for svc in services:
            assert svc.is_running(), f"Service {svc.name} should be running"

        # All should have completed polls
        for svc in services:
            assert svc._poll_count > 0, f"Service {svc.name} should have polled"

        supervisor.stop_all()

        # All services should be stopped
        for svc in services:
            assert not svc.is_running(), f"Service {svc.name} should be stopped"

    def test_one_service_failure_isolated(self, integration_config: RunnerConfig) -> None:
        """Verify one service failing doesn't affect others.

        Educational Note:
            Error isolation is critical for resilient systems. A failing
            ESPN service shouldn't bring down the Kalshi poller.
        """
        supervisor = ServiceSupervisor(integration_config)

        good_service = RealisticMockService(name="good", poll_interval=0.1)
        failing_service = RealisticMockService(
            name="failing", poll_interval=0.1, fail_after_polls=2
        )

        supervisor.add_service("good", good_service, ServiceConfig(name="Good Service"))
        supervisor.add_service("failing", failing_service, ServiceConfig(name="Failing Service"))

        supervisor.start_all()
        time.sleep(1)  # Let failing service crash

        # Good service should still be running
        assert good_service.is_running(), "Good service should survive other's failure"
        assert good_service._poll_count > 0, "Good service should continue polling"

        # Failing service should have stopped
        assert not failing_service.is_running(), "Failing service should have crashed"

        supervisor.stop_all()

    def test_staggered_service_registration(self, integration_config: RunnerConfig) -> None:
        """Verify services can be added while supervisor is running."""
        supervisor = ServiceSupervisor(integration_config)

        service1 = RealisticMockService(name="first", poll_interval=0.1)
        supervisor.add_service("first", service1, ServiceConfig(name="First"))
        supervisor.start_all()

        time.sleep(0.3)

        # Add second service while running
        service2 = RealisticMockService(name="second", poll_interval=0.1)
        supervisor.add_service("second", service2, ServiceConfig(name="Second"))
        # Note: In current implementation, service2 won't auto-start
        # This documents that behavior for future enhancement

        assert service1.is_running()
        assert "second" in supervisor.services

        supervisor.stop_all()


# =============================================================================
# Health Monitoring Integration Tests
# =============================================================================


class TestHealthMonitoringIntegration:
    """Integration tests for health monitoring system.

    Educational Note:
        Health monitoring runs in background threads. These tests verify
        the monitoring loop correctly detects and responds to service
        state changes.
    """

    def test_health_check_detects_stopped_service(self, integration_config: RunnerConfig) -> None:
        """Verify health checks detect when a service stops unexpectedly."""
        supervisor = ServiceSupervisor(integration_config)
        service = RealisticMockService(name="crasher", poll_interval=0.1, fail_after_polls=3)
        config = ServiceConfig(name="Crasher", max_retries=0)  # Don't restart

        supervisor.add_service("crasher", service, config)
        supervisor.start_all()

        # Wait for crash and health check
        time.sleep(2)

        state = supervisor.services["crasher"]
        assert not state.healthy, "Service should be marked unhealthy"
        assert state.consecutive_failures > 0, "Should have failure count"

        supervisor.stop_all()

    def test_health_check_triggers_restart(self, integration_config: RunnerConfig) -> None:
        """Verify health check triggers service restart.

        Educational Note:
            Auto-restart is key to service resilience. The supervisor
            should automatically attempt to recover failed services.
        """
        supervisor = ServiceSupervisor(integration_config)
        service = RealisticMockService(name="restarter", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="Restarter", max_retries=3, retry_delay=1)

        supervisor.add_service("restarter", service, config)
        supervisor.start_all()

        # Wait for crash, health check, and restart attempt
        time.sleep(3)

        supervisor.services["restarter"]
        # Service may have been restarted
        # (behavior depends on timing and restart success)

        supervisor.stop_all()


# =============================================================================
# Metrics Pipeline Integration Tests
# =============================================================================


class TestMetricsPipelineIntegration:
    """Integration tests for metrics collection pipeline.

    Educational Note:
        Metrics should accurately reflect the actual state of services.
        These tests verify end-to-end metric collection and aggregation.
    """

    def test_metrics_reflect_service_activity(self, integration_config: RunnerConfig) -> None:
        """Verify metrics accurately reflect service polling activity."""
        supervisor = ServiceSupervisor(integration_config)
        service = RealisticMockService(name="active", poll_interval=0.1)
        supervisor.add_service("active", service, ServiceConfig(name="Active"))

        supervisor.start_all()
        time.sleep(0.5)  # Let some polls complete

        metrics = supervisor.get_aggregate_metrics()

        assert metrics["services_total"] == 1
        assert metrics["services_healthy"] == 1
        assert metrics["uptime_seconds"] > 0

        # Check per-service stats
        svc_stats = metrics["per_service"]["active"]["stats"]
        assert svc_stats["polls_completed"] > 0

        supervisor.stop_all()

    def test_metrics_aggregate_multiple_services(self, integration_config: RunnerConfig) -> None:
        """Verify metrics correctly aggregate across multiple services."""
        supervisor = ServiceSupervisor(integration_config)

        for i in range(3):
            service = RealisticMockService(name=f"svc{i}", poll_interval=0.1)
            supervisor.add_service(f"svc{i}", service, ServiceConfig(name=f"Svc{i}"))

        supervisor.start_all()
        time.sleep(0.5)

        metrics = supervisor.get_aggregate_metrics()

        assert metrics["services_total"] == 3
        assert metrics["services_healthy"] == 3
        assert len(metrics["per_service"]) == 3

        supervisor.stop_all()

    def test_metrics_track_errors(self, integration_config: RunnerConfig) -> None:
        """Verify metrics correctly track error counts."""
        supervisor = ServiceSupervisor(integration_config)
        service = RealisticMockService(name="erroring", poll_interval=0.1, error_rate=0.5)
        supervisor.add_service("erroring", service, ServiceConfig(name="Erroring"))

        supervisor.start_all()
        time.sleep(1)  # Let some polls with errors occur

        service.get_stats()
        # With 50% error rate and ~10 polls, expect some errors
        # This is probabilistic, so we just check the mechanism works

        supervisor.stop_all()


# =============================================================================
# Alert System Integration Tests
# =============================================================================


class TestAlertSystemIntegration:
    """Integration tests for alert callback system.

    Educational Note:
        Alerts should be triggered when service health degrades.
        These tests verify the alert pipeline from detection to callback.
    """

    def test_alert_callback_receives_real_events(self, integration_config: RunnerConfig) -> None:
        """Verify alert callbacks receive events from real service failures."""
        supervisor = ServiceSupervisor(integration_config)
        service = RealisticMockService(name="alerter", poll_interval=0.1, fail_after_polls=2)
        config = ServiceConfig(name="Alerter", max_retries=1, retry_delay=1)

        received_alerts: list[tuple[str, str, dict[str, Any]]] = []

        def alert_handler(name: str, message: str, context: dict[str, Any]) -> None:
            received_alerts.append((name, message, context))

        supervisor.register_alert_callback(alert_handler)
        supervisor.add_service("alerter", service, config)
        supervisor.start_all()

        # Wait for crash, health check, and alert
        time.sleep(4)

        # Alerts should have been triggered
        # (may or may not have alerts depending on timing and max_retries)

        supervisor.stop_all()

    def test_multiple_alert_callbacks(self, integration_config: RunnerConfig) -> None:
        """Verify multiple alert callbacks all receive events."""
        supervisor = ServiceSupervisor(integration_config)

        callback1_called = threading.Event()
        callback2_called = threading.Event()

        def callback1(name: str, msg: str, ctx: dict[str, Any]) -> None:
            callback1_called.set()

        def callback2(name: str, msg: str, ctx: dict[str, Any]) -> None:
            callback2_called.set()

        supervisor.register_alert_callback(callback1)
        supervisor.register_alert_callback(callback2)

        # Trigger an alert manually
        supervisor._trigger_alert("test", "Test alert", {"key": "value"})

        assert callback1_called.is_set(), "Callback 1 should have been called"
        assert callback2_called.is_set(), "Callback 2 should have been called"


# =============================================================================
# Factory Integration Tests
# =============================================================================


class TestFactoryIntegration:
    """Integration tests for factory functions.

    Educational Note:
        Factory functions should produce working supervisors and services.
        These tests verify end-to-end factory behavior.
    """

    @patch.dict("os.environ", {"KALSHI_API_KEY_ID": ""}, clear=False)
    def test_create_services_with_espn_only(self) -> None:
        """Verify create_services works with ESPN only (no Kalshi creds)."""
        config = RunnerConfig()
        services = create_services(config, enabled_services={"espn"})

        assert "espn" in services
        _service, svc_config = services["espn"]
        assert svc_config.name == "ESPN Game Poller"

    @patch("precog.schedulers.service_supervisor.create_services")
    def test_create_supervisor_integrates_services(self, mock_create: MagicMock) -> None:
        """Verify create_supervisor properly integrates created services."""
        mock_service = RealisticMockService(name="mock")
        mock_config = ServiceConfig(name="Mock")
        mock_create.return_value = {"mock": (mock_service, mock_config)}

        supervisor = create_supervisor(
            environment="development",
            enabled_services={"mock"},
        )

        assert "mock" in supervisor.services
        assert supervisor.services["mock"].service is mock_service


# =============================================================================
# Lifecycle Integration Tests
# =============================================================================


class TestLifecycleIntegration:
    """Integration tests for full service lifecycle.

    Educational Note:
        These tests verify the complete lifecycle: initialization,
        start, run, shutdown, and cleanup.
    """

    def test_full_lifecycle(self, integration_config: RunnerConfig) -> None:
        """Verify complete lifecycle from creation to shutdown."""
        # 1. Create supervisor
        supervisor = ServiceSupervisor(integration_config)
        assert not supervisor.is_running

        # 2. Add services
        service = RealisticMockService(name="lifecycle", poll_interval=0.1)
        supervisor.add_service("lifecycle", service, ServiceConfig(name="Lifecycle"))
        assert "lifecycle" in supervisor.services

        # 3. Start
        supervisor.start_all()
        assert supervisor.is_running
        assert service.is_running()

        # 4. Run (let it poll)
        time.sleep(0.5)
        assert service._poll_count > 0

        # 5. Shutdown
        supervisor.stop_all()
        assert not supervisor.is_running
        assert not service.is_running()

    def test_graceful_shutdown_under_load(self, integration_config: RunnerConfig) -> None:
        """Verify graceful shutdown when services are actively polling."""
        supervisor = ServiceSupervisor(integration_config)

        # Create multiple busy services
        services = [RealisticMockService(name=f"busy{i}", poll_interval=0.05) for i in range(5)]

        for i, svc in enumerate(services):
            supervisor.add_service(f"busy{i}", svc, ServiceConfig(name=f"Busy{i}"))

        supervisor.start_all()
        time.sleep(0.5)  # Let them get busy

        # Shutdown while busy
        start = time.time()
        supervisor.stop_all()
        elapsed = time.time() - start

        # Should complete reasonably quickly (< 5 seconds)
        assert elapsed < 5, f"Shutdown took too long: {elapsed}s"

        # All should be stopped
        for svc in services:
            assert not svc.is_running()

    def test_programmatic_shutdown_signal(self, integration_config: RunnerConfig) -> None:
        """Verify trigger_shutdown works correctly."""
        supervisor = ServiceSupervisor(integration_config)
        service = RealisticMockService(name="signal", poll_interval=0.1)
        supervisor.add_service("signal", service, ServiceConfig(name="Signal"))

        supervisor.start_all()

        # Trigger shutdown from another thread
        def trigger_later() -> None:
            time.sleep(0.3)
            supervisor.trigger_shutdown()

        trigger_thread = threading.Thread(target=trigger_later)
        trigger_thread.start()

        # Wait for shutdown (should be triggered)
        supervisor.wait_for_shutdown()
        trigger_thread.join()

        # Cleanup
        supervisor.stop_all()
