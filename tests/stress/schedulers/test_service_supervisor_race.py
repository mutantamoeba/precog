"""
Race condition tests for service_supervisor module.

Tests for race conditions in concurrent operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading
from typing import Any

import pytest

from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceState,
    ServiceSupervisor,
)

pytestmark = [pytest.mark.race]


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


class TestServiceRegistrationRace:
    """Race condition tests for service registration."""

    def test_concurrent_add_remove_same_service(self) -> None:
        """Verify concurrent add/remove of same service is safe."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)
        errors = []
        lock = threading.Lock()

        def add_service() -> None:
            try:
                for _ in range(50):
                    service = MockService()
                    svc_config = ServiceConfig(name="shared")
                    supervisor.add_service("shared", service, svc_config)
            except Exception as e:
                with lock:
                    errors.append(e)

        def remove_service() -> None:
            try:
                for _ in range(50):
                    supervisor.remove_service("shared")
            except Exception as e:
                with lock:
                    errors.append(e)

        adder = threading.Thread(target=add_service)
        remover = threading.Thread(target=remove_service)

        adder.start()
        remover.start()
        adder.join()
        remover.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"

    def test_concurrent_registration_no_corruption(self) -> None:
        """Verify concurrent registration doesn't corrupt services dict."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)
        errors = []
        lock = threading.Lock()

        def register(prefix: str) -> None:
            try:
                for i in range(50):
                    service = MockService()
                    svc_config = ServiceConfig(name=f"{prefix}_{i}")
                    supervisor.add_service(f"{prefix}_{i}", service, svc_config)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=register, args=(f"t{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # Should have 5 * 50 = 250 services
        assert len(supervisor.services) == 250


class TestMetricsRace:
    """Race condition tests for metrics operations."""

    def test_concurrent_metrics_during_state_changes(self) -> None:
        """Verify metrics collection during state changes is safe."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        # Add services
        for i in range(10):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        errors = []
        metrics_results = []
        lock = threading.Lock()

        def collect_metrics() -> None:
            try:
                for _ in range(50):
                    result = supervisor.get_aggregate_metrics()
                    with lock:
                        metrics_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        def modify_state() -> None:
            try:
                for i in range(50):
                    # Modify service states
                    for name, state in supervisor.services.items():
                        state.error_count = i
                        state.healthy = i % 2 == 0
            except Exception as e:
                with lock:
                    errors.append(e)

        collector = threading.Thread(target=collect_metrics)
        modifier = threading.Thread(target=modify_state)

        collector.start()
        modifier.start()
        collector.join()
        modifier.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(metrics_results) == 50


class TestAlertCallbackRace:
    """Race condition tests for alert callbacks."""

    def test_concurrent_callback_registration_and_triggering(self) -> None:
        """Verify concurrent registration and triggering is safe."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)
        errors = []
        alerts_triggered = []
        lock = threading.Lock()

        def register_callbacks() -> None:
            try:
                for i in range(50):

                    def callback(name: str, msg: str, ctx: dict, idx: int = i) -> None:
                        with lock:
                            alerts_triggered.append((idx, name))

                    supervisor.register_alert_callback(callback)
            except Exception as e:
                with lock:
                    errors.append(e)

        def trigger_alerts() -> None:
            try:
                for i in range(50):
                    supervisor._trigger_alert(f"service_{i}", f"Alert {i}", {})
            except Exception as e:
                with lock:
                    errors.append(e)

        registrar = threading.Thread(target=register_callbacks)
        triggerer = threading.Thread(target=trigger_alerts)

        registrar.start()
        triggerer.start()
        registrar.join()
        triggerer.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestShutdownRace:
    """Race condition tests for shutdown operations."""

    def test_concurrent_shutdown_requests(self) -> None:
        """Verify concurrent shutdown requests are safe."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)

        # Add services
        for i in range(5):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        supervisor.start_all()

        errors = []
        lock = threading.Lock()

        def request_shutdown() -> None:
            try:
                supervisor.trigger_shutdown()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=request_shutdown) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        supervisor.stop_all()

        assert len(errors) == 0, f"Race condition errors: {errors}"

    def test_stop_during_start(self) -> None:
        """Verify stopping during start is safe."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        errors = []
        lock = threading.Lock()

        def run_cycle() -> None:
            try:
                supervisor = ServiceSupervisor(config)
                for i in range(3):
                    service = MockService()
                    svc_config = ServiceConfig(name=f"service_{i}")
                    supervisor.add_service(f"svc_{i}", service, svc_config)

                def start_services() -> None:
                    try:
                        supervisor.start_all()
                    except Exception:
                        pass

                def stop_services() -> None:
                    try:
                        supervisor.stop_all()
                    except Exception:
                        pass

                starter = threading.Thread(target=start_services)
                stopper = threading.Thread(target=stop_services)

                starter.start()
                stopper.start()
                starter.join()
                stopper.join()

            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=run_cycle) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestServiceStateRace:
    """Race condition tests for ServiceState."""

    def test_concurrent_state_reads_writes(self) -> None:
        """Verify concurrent state reads/writes are safe."""
        state = ServiceState()
        state.service = MockService()
        errors = []
        lock = threading.Lock()

        def write_state() -> None:
            try:
                for i in range(100):
                    state.error_count = i
                    state.restart_count = i % 10
                    state.healthy = i % 2 == 0
                    state.consecutive_failures = i % 5
            except Exception as e:
                with lock:
                    errors.append(e)

        def read_state() -> None:
            try:
                for _ in range(100):
                    _ = state.error_count
                    _ = state.restart_count
                    _ = state.healthy
                    _ = state.consecutive_failures
            except Exception as e:
                with lock:
                    errors.append(e)

        writer = threading.Thread(target=write_state)
        reader = threading.Thread(target=read_state)

        writer.start()
        reader.start()
        writer.join()
        reader.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestUptimeRace:
    """Race condition tests for uptime calculations."""

    def test_concurrent_uptime_queries(self) -> None:
        """Verify concurrent uptime queries are safe."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)
        supervisor.start_all()

        results = []
        errors = []
        lock = threading.Lock()

        def query_uptime() -> None:
            try:
                for _ in range(50):
                    uptime = supervisor.uptime_seconds
                    with lock:
                        results.append(uptime)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=query_uptime) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        supervisor.stop_all()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 500
        # All uptimes should be non-negative
        assert all(u >= 0 for u in results)
