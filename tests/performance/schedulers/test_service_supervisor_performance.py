"""
Performance tests for service_supervisor module.

Validates latency and throughput requirements.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time
from typing import Any

import pytest

from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceSupervisor,
)

pytestmark = [pytest.mark.performance]


class MockService:
    """Mock service for testing."""

    def __init__(self) -> None:
        self._running = False
        self._stats: dict[str, Any] = {"errors": 0, "calls": 0}

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict[str, Any]:
        return self._stats.copy()


class TestServiceRegistrationPerformance:
    """Performance benchmarks for service registration."""

    def test_add_service_latency(self) -> None:
        """Test service registration latency."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        latencies = []
        for i in range(100):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")

            start = time.perf_counter()
            supervisor.add_service(f"svc_{i}", service, svc_config)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <1ms on average
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_remove_service_latency(self) -> None:
        """Test service removal latency."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        # Pre-register services
        for i in range(100):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        latencies = []
        for i in range(100):
            start = time.perf_counter()
            supervisor.remove_service(f"svc_{i}")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <1ms on average
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_service_registration_throughput(self) -> None:
        """Test service registration throughput."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        start = time.perf_counter()
        count = 0
        for i in range(1000):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 5000 registrations/sec
        assert throughput > 5000, f"Throughput {throughput:.0f} ops/sec too low"


class TestMetricsPerformance:
    """Performance benchmarks for metrics operations."""

    def test_get_aggregate_metrics_latency(self) -> None:
        """Test metrics aggregation latency."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        # Add services
        for i in range(50):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            supervisor.get_aggregate_metrics()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <5ms on average
        assert avg_latency < 0.005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_metrics_throughput(self) -> None:
        """Test metrics collection throughput."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        # Add services
        for i in range(20):
            service = MockService()
            svc_config = ServiceConfig(name=f"service_{i}")
            supervisor.add_service(f"svc_{i}", service, svc_config)

        start = time.perf_counter()
        count = 0
        for _ in range(5000):
            supervisor.get_aggregate_metrics()
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 1000 metrics calls/sec
        assert throughput > 1000, f"Throughput {throughput:.0f} ops/sec too low"


class TestConfigPerformance:
    """Performance benchmarks for configuration operations."""

    def test_runner_config_creation_latency(self) -> None:
        """Test RunnerConfig creation latency."""
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            RunnerConfig(
                environment=Environment.DEVELOPMENT,
                health_check_interval=60,
                metrics_interval=300,
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.5ms on average
        assert avg_latency < 0.0005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_service_config_creation_latency(self) -> None:
        """Test ServiceConfig creation latency."""
        latencies = []
        for i in range(100):
            start = time.perf_counter()
            ServiceConfig(
                name=f"service_{i}",
                enabled=True,
                poll_interval=15,
                max_retries=3,
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"


class TestSupervisorInstantiationPerformance:
    """Performance benchmarks for supervisor instantiation."""

    def test_supervisor_instantiation_latency(self) -> None:
        """Test supervisor instantiation latency."""
        latencies = []
        for _ in range(100):
            config = RunnerConfig(environment=Environment.DEVELOPMENT)
            start = time.perf_counter()
            ServiceSupervisor(config)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <1ms on average
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_supervisor_instantiation_throughput(self) -> None:
        """Test supervisor instantiation throughput."""
        start = time.perf_counter()
        count = 0
        for _ in range(500):
            config = RunnerConfig(environment=Environment.DEVELOPMENT)
            ServiceSupervisor(config)
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 500 instantiations/sec
        assert throughput > 500, f"Throughput {throughput:.0f} ops/sec too low"


class TestAlertPerformance:
    """Performance benchmarks for alert operations."""

    def test_alert_callback_registration_latency(self) -> None:
        """Test alert callback registration latency."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        latencies = []
        for _ in range(100):

            def callback(name: str, msg: str, ctx: dict) -> None:
                pass

            start = time.perf_counter()
            supervisor.register_alert_callback(callback)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_alert_trigger_latency_no_callbacks(self) -> None:
        """Test alert triggering latency with no callbacks."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        latencies = []
        for i in range(100):
            start = time.perf_counter()
            supervisor._trigger_alert(f"service_{i}", f"Alert {i}", {})
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <1ms on average
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_alert_trigger_latency_with_callbacks(self) -> None:
        """Test alert triggering latency with callbacks."""
        config = RunnerConfig(environment=Environment.DEVELOPMENT)
        supervisor = ServiceSupervisor(config)

        # Register 10 callbacks
        for _ in range(10):

            def callback(name: str, msg: str, ctx: dict) -> None:
                pass

            supervisor.register_alert_callback(callback)

        latencies = []
        for i in range(100):
            start = time.perf_counter()
            supervisor._trigger_alert(f"service_{i}", f"Alert {i}", {})
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <2ms on average
        assert avg_latency < 0.002, f"Average latency {avg_latency * 1000:.3f}ms too high"


class TestUptimePerformance:
    """Performance benchmarks for uptime calculations."""

    def test_uptime_query_latency(self) -> None:
        """Test uptime query latency."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)
        supervisor.start_all()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            _ = supervisor.uptime_seconds
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        supervisor.stop_all()

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_is_running_latency(self) -> None:
        """Test is_running query latency."""
        config = RunnerConfig(
            environment=Environment.DEVELOPMENT,
            health_check_interval=1000,
            metrics_interval=1000,
        )
        supervisor = ServiceSupervisor(config)
        supervisor.start_all()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            _ = supervisor.is_running
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        supervisor.stop_all()

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"
