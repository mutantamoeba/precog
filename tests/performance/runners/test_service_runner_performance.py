"""
Performance tests for service_runner module.

Validates latency and throughput requirements.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from precog.runners.service_runner import (
    DataCollectorService,
    get_log_dir,
    get_pid_file,
    is_process_running,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)

pytestmark = [pytest.mark.performance]


class TestPidFilePerformance:
    """Performance benchmarks for PID file operations."""

    def test_write_pid_file_latency(self, tmp_path: Path) -> None:
        """Test PID file write latency."""
        pid_file = tmp_path / "test.pid"

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            write_pid_file(pid_file)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            pid_file.unlink()

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <10ms on average
        assert avg_latency < 0.01, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_read_pid_file_latency(self, tmp_path: Path) -> None:
        """Test PID file read latency."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            read_pid_file(pid_file)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <5ms on average
        assert avg_latency < 0.005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_remove_pid_file_latency(self, tmp_path: Path) -> None:
        """Test PID file removal latency."""
        latencies = []
        for _ in range(100):
            pid_file = tmp_path / f"test_{_}.pid"
            pid_file.write_text("12345")

            start = time.perf_counter()
            remove_pid_file(pid_file)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <10ms on average
        assert avg_latency < 0.01, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_pid_file_throughput(self, tmp_path: Path) -> None:
        """Test PID file operations throughput."""
        pid_file = tmp_path / "test.pid"

        start = time.perf_counter()
        count = 0
        for _ in range(500):
            write_pid_file(pid_file)
            read_pid_file(pid_file)
            remove_pid_file(pid_file)
            count += 3  # 3 operations per cycle
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 500 ops/sec
        assert throughput > 500, f"Throughput {throughput:.0f} ops/sec too low"


class TestProcessCheckPerformance:
    """Performance benchmarks for process checking."""

    def test_is_process_running_latency(self) -> None:
        """Test process existence check latency."""
        import os

        current_pid = os.getpid()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            is_process_running(current_pid)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <5ms on average
        assert avg_latency < 0.005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_process_check_throughput(self) -> None:
        """Test process checking throughput."""
        import os

        current_pid = os.getpid()

        start = time.perf_counter()
        count = 0
        for _ in range(1000):
            is_process_running(current_pid)
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 1000 checks/sec
        assert throughput > 1000, f"Throughput {throughput:.0f} ops/sec too low"


class TestPathFunctionsPerformance:
    """Performance benchmarks for path helper functions."""

    @patch("sys.platform", "win32")
    def test_get_pid_file_latency_windows(self) -> None:
        """Test PID file path resolution latency on Windows."""
        latencies = []
        for _ in range(100):
            with patch.object(Path, "mkdir", return_value=None):
                start = time.perf_counter()
                get_pid_file()
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <1ms on average
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    @patch("sys.platform", "linux")
    def test_get_log_dir_latency_linux(self) -> None:
        """Test log directory resolution latency on Linux."""
        latencies = []
        for _ in range(100):
            with (
                patch.object(Path, "exists", return_value=False),
                patch.object(Path, "mkdir", return_value=None),
            ):
                start = time.perf_counter()
                get_log_dir()
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <1ms on average
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"


class TestServiceInstantiationPerformance:
    """Performance benchmarks for service instantiation."""

    def test_service_instantiation_latency(self) -> None:
        """Test service instantiation latency."""
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            DataCollectorService(
                espn_enabled=True,
                kalshi_enabled=True,
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <10ms on average
        assert avg_latency < 0.01, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_service_instantiation_throughput(self) -> None:
        """Test service instantiation throughput."""
        start = time.perf_counter()
        count = 0
        for _ in range(500):
            DataCollectorService(
                espn_enabled=True,
                kalshi_enabled=False,
            )
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 100 instantiations/sec
        assert throughput > 100, f"Throughput {throughput:.0f} ops/sec too low"


class TestServiceStatusPerformance:
    """Performance benchmarks for service status checking."""

    def test_status_check_latency(self, tmp_path: Path) -> None:
        """Test status check latency."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            service.status()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <20ms on average
        assert avg_latency < 0.02, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_status_check_with_pid_file_latency(self, tmp_path: Path) -> None:
        """Test status check latency with PID file present."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"
        service.pid_file.write_text("99999")  # Non-existent PID

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            service.status()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <20ms on average
        assert avg_latency < 0.02, f"Average latency {avg_latency * 1000:.3f}ms too high"
