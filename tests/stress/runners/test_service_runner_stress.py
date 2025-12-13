"""
Stress tests for service_runner module.

Tests high-volume operations to validate behavior under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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

pytestmark = [pytest.mark.stress]


class TestPidFileStress:
    """Stress tests for PID file operations."""

    def test_concurrent_pid_file_writes(self, tmp_path: Path) -> None:
        """Test concurrent PID file writes."""
        pid_file = tmp_path / "test.pid"
        results = []
        lock = threading.Lock()

        def write_pid() -> None:
            pid_file.write_text(str(threading.current_thread().ident))
            content = pid_file.read_text()
            with lock:
                results.append(content)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(write_pid) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        # All writes should complete
        assert len(results) == 100
        # File should contain valid content
        assert pid_file.read_text().isdigit() or pid_file.read_text().strip().isdigit()

    def test_concurrent_pid_file_reads(self, tmp_path: Path) -> None:
        """Test concurrent PID file reads."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")

        results = []
        lock = threading.Lock()

        def read_pid() -> int | None:
            result = read_pid_file(pid_file)
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(read_pid) for _ in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200
        assert all(r == 12345 for r in results)

    def test_rapid_write_read_cycles(self, tmp_path: Path) -> None:
        """Test rapid write/read cycles."""
        pid_file = tmp_path / "test.pid"

        for i in range(500):
            write_pid_file(pid_file)
            result = read_pid_file(pid_file)
            assert result is not None
            remove_pid_file(pid_file)

        assert not pid_file.exists()


class TestProcessCheckStress:
    """Stress tests for process checking."""

    def test_concurrent_process_checks(self) -> None:
        """Test concurrent process existence checks."""
        import os

        current_pid = os.getpid()
        results = []
        lock = threading.Lock()

        def check_process() -> bool:
            result = is_process_running(current_pid)
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(check_process) for _ in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200
        assert all(r is True for r in results)

    def test_sustained_process_checks(self) -> None:
        """Test sustained process checking."""
        import os

        current_pid = os.getpid()

        for _ in range(1000):
            result = is_process_running(current_pid)
            assert result is True


class TestPathFunctionsStress:
    """Stress tests for path helper functions."""

    @patch("sys.platform", "win32")
    def test_concurrent_get_pid_file_windows(self) -> None:
        """Test concurrent PID file path resolution on Windows."""
        results = []
        lock = threading.Lock()

        def get_path() -> Path:
            # Use mock to avoid file system operations
            with patch.object(Path, "mkdir", return_value=None):
                result = get_pid_file()
                with lock:
                    results.append(result)
                return result

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(get_path) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100
        # All should return same path
        assert len({str(r) for r in results}) == 1

    @patch("sys.platform", "linux")
    def test_concurrent_get_log_dir_linux(self) -> None:
        """Test concurrent log directory resolution on Linux."""
        results = []
        lock = threading.Lock()

        def get_path() -> Path:
            with (
                patch.object(Path, "exists", return_value=False),
                patch.object(Path, "mkdir", return_value=None),
            ):
                result = get_log_dir()
                with lock:
                    results.append(result)
                return result

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(get_path) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100


class TestDataCollectorServiceStress:
    """Stress tests for DataCollectorService."""

    def test_rapid_service_instantiation(self) -> None:
        """Test rapid service instantiation."""
        services = []

        for _ in range(100):
            service = DataCollectorService(
                espn_enabled=True,
                kalshi_enabled=False,
            )
            services.append(service)

        assert len(services) == 100
        assert all(s.espn_enabled is True for s in services)
        assert all(s.kalshi_enabled is False for s in services)

    def test_concurrent_service_instantiation(self) -> None:
        """Test concurrent service instantiation."""
        results = []
        lock = threading.Lock()

        def create_service() -> DataCollectorService:
            service = DataCollectorService(
                espn_enabled=True,
                kalshi_enabled=True,
            )
            with lock:
                results.append(service)
            return service

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_service) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 50

    def test_concurrent_status_checks(self, tmp_path: Path) -> None:
        """Test concurrent status checks."""
        results = []
        lock = threading.Lock()

        def check_status() -> int:
            service = DataCollectorService()
            # Override PID file to use temp
            service.pid_file = tmp_path / "test.pid"
            result = service.status()
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check_status) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 50
        # All should return 1 (not running - no PID file)
        assert all(r == 1 for r in results)
