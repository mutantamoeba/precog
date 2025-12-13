"""
Stress tests for service_supervisor module.

Tests high-volume operations to validate behavior under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest

from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceState,
    ServiceSupervisor,
)

pytestmark = [pytest.mark.stress]


class MockService:
    """Mock service for testing."""

    def __init__(self) -> None:
        self._running = False
        self._stats: dict[str, Any] = {"errors": 0, "calls": 0}
        self._lock = threading.Lock()

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return self._stats.copy()

    def increment_calls(self) -> None:
        with self._lock:
            self._stats["calls"] += 1


class TestServiceRegistrationStress:
    """Stress tests for service registration."""

    def test_rapid_service_registration(self) -> None:
        """Test rapid service registration."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        for i in range(200):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        assert len(supervisor.services) == 200

    def test_concurrent_service_registration(self) -> None:
        """Test concurrent service registration."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)
        lock = threading.Lock()
        registered = []

        def register(index: int) -> None:
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{index}")
            supervisor.add_service(f"svc_{index}", service, svc_config)
            with lock:
                registered.append(index)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(register, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(registered) == 100
        assert len(supervisor.services) == 100

    def test_sustained_add_remove_cycles(self) -> None:
        """Test sustained add/remove cycles."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        for i in range(500):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i % 10}")
            supervisor.add_service(f"svc_{i % 10}", service, svc_config)

            if i % 2 == 0:
                supervisor.remove_service(f"svc_{i % 10}")

        # Some services should remain
        assert len(supervisor.services) >= 0


class TestServiceStartStopStress:
    """Stress tests for service start/stop operations."""

    def test_rapid_start_stop_cycles(self) -> None:
        """Test rapid start/stop cycles."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,  # Long interval to not interfere
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        # Add some services
        for i in range(5):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}", enabled=True)
            supervisor.add_service(f"svc_{i}", service, svc_config)

        # Rapid start/stop cycles
        for _ in range(20):
            supervisor.start_all()
            supervisor.stop_all()

        # Final check - all should be stopped
        for state in supervisor.services.values():
            if state.service:
                assert not state.service.is_running()

    def test_concurrent_metrics_requests(self) -> None:
        """Test concurrent metrics requests."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        # Add services
        for i in range(10):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        results = []
        lock = threading.Lock()

        def get_metrics() -> dict[str, Any]:
            metrics = supervisor.get_aggregate_metrics()
            with lock:
                results.append(metrics)
            return metrics

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(get_metrics) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100
        # All should have same service count
        assert all(m["services_total"] == 10 for m in results)


class TestAlertCallbackStress:
    """Stress tests for alert callbacks."""

    def test_concurrent_alert_callback_registration(self) -> None:
        """Test concurrent alert callback registration."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)
        lock = threading.Lock()
        registered = []

        def register_callback(index: int) -> None:
            def callback(name: str, msg: str, ctx: dict) -> None:
                pass

            supervisor.register_alert_callback(callback)
            with lock:
                registered.append(index)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(register_callback, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(registered) == 50
        assert len(supervisor._alert_callbacks) == 50

    def test_rapid_alert_triggering(self) -> None:
        """Test rapid alert triggering."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        alerts_received = []
        lock = threading.Lock()

        def alert_handler(name: str, msg: str, ctx: dict) -> None:
            with lock:
                alerts_received.append((name, msg))

        supervisor.register_alert_callback(alert_handler)

        # Trigger many alerts rapidly
        for i in range(100):
            supervisor._trigger_alert(f"service_{i}", f"Alert {i}", {"index": i})

        assert len(alerts_received) == 100


class TestServiceStateStress:
    """Stress tests for ServiceState operations."""

    def test_concurrent_state_updates(self) -> None:
        """Test concurrent state updates."""
        state = ServiceState()
        state.service = MockService()
        lock = threading.Lock()
        updates = []

        def update_state(index: int) -> None:
            state.error_count = index
            state.restart_count = index % 10
            state.healthy = index % 2 == 0
            with lock:
                updates.append(index)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(update_state, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(updates) == 100


class TestRunnerConfigStress:
    """Stress tests for RunnerConfig."""

    def test_rapid_config_creation(self) -> None:
        """Test rapid config creation."""
        configs = []

        for i in range(500):
            config = RunnerConfig(
                environment=Environment.DEVELOPMENT,
                health_check_interval=60 + i,
                metrics_interval=300 + i,
            )
            configs.append(config)

        assert len(configs) == 500
        # All should have unique intervals
        intervals = [c.health_check_interval for c in configs]
        assert len(set(intervals)) == 500

    def test_concurrent_config_creation(self) -> None:
        """Test concurrent config creation."""
        configs = []
        lock = threading.Lock()

        def create_config(index: int) -> RunnerConfig:
            config = RunnerConfig(
                environment=Environment.STAGING,
                health_check_interval=index,
            )
            with lock:
                configs.append(config)
            return config

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_config, i) for i in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(configs) == 100
