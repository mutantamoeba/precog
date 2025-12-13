"""
Race condition tests for service_runner module.

Tests for race conditions in concurrent operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading
from pathlib import Path

import pytest

from precog.runners.service_runner import (
    DataCollectorService,
    is_process_running,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)

pytestmark = [pytest.mark.race]


class TestPidFileRace:
    """Race condition tests for PID file operations."""

    def test_concurrent_write_read_no_corruption(self, tmp_path: Path) -> None:
        """Verify concurrent write/read doesn't corrupt PID file."""
        pid_file = tmp_path / "test.pid"
        errors = []
        results = []
        lock = threading.Lock()

        def writer() -> None:
            try:
                write_pid_file(pid_file)
            except Exception as e:
                with lock:
                    errors.append(e)

        def reader() -> None:
            try:
                result = read_pid_file(pid_file)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Mix of writers and readers
        threads = []
        for i in range(100):
            t = threading.Thread(target=writer) if i % 3 == 0 else threading.Thread(target=reader)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"

    def test_concurrent_remove_no_double_delete(self, tmp_path: Path) -> None:
        """Verify concurrent removes don't cause double-delete errors."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")

        errors = []
        lock = threading.Lock()

        def remove() -> None:
            try:
                remove_pid_file(pid_file)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=remove) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise errors
        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert not pid_file.exists()

    def test_write_remove_race(self, tmp_path: Path) -> None:
        """Test race between write and remove operations."""
        pid_file = tmp_path / "test.pid"
        errors = []
        lock = threading.Lock()

        def write_and_read() -> None:
            try:
                write_pid_file(pid_file)
                # May get None if removed between write and read
                read_pid_file(pid_file)
            except Exception as e:
                with lock:
                    errors.append(e)

        def remove() -> None:
            try:
                remove_pid_file(pid_file)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(100):
            if i % 2 == 0:
                t = threading.Thread(target=write_and_read)
            else:
                t = threading.Thread(target=remove)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No crashes should occur
        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestProcessCheckRace:
    """Race condition tests for process checking."""

    def test_concurrent_process_checks_consistent(self) -> None:
        """Verify concurrent process checks return consistent results."""
        import os

        current_pid = os.getpid()
        results = []
        errors = []
        lock = threading.Lock()

        def check() -> None:
            try:
                result = is_process_running(current_pid)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        # All should be True for running process
        assert all(r is True for r in results)


class TestServiceStatusRace:
    """Race condition tests for service status checking."""

    def test_concurrent_status_checks_no_crash(self, tmp_path: Path) -> None:
        """Verify concurrent status checks don't crash."""
        errors = []
        results = []
        lock = threading.Lock()

        def check_status() -> None:
            try:
                service = DataCollectorService()
                service.pid_file = tmp_path / "test.pid"
                result = service.status()
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=check_status) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 50

    def test_status_with_changing_pid_file(self, tmp_path: Path) -> None:
        """Test status checking while PID file is being modified."""
        pid_file = tmp_path / "test.pid"
        errors = []
        results = []
        lock = threading.Lock()

        def modify_pid() -> None:
            try:
                for _ in range(20):
                    write_pid_file(pid_file)
                    remove_pid_file(pid_file)
            except Exception as e:
                with lock:
                    errors.append(e)

        def check_status() -> None:
            try:
                for _ in range(20):
                    service = DataCollectorService()
                    service.pid_file = pid_file
                    result = service.status()
                    with lock:
                        results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        modifier = threading.Thread(target=modify_pid)
        checker = threading.Thread(target=check_status)

        modifier.start()
        checker.start()
        modifier.join()
        checker.join()

        # Should not crash despite race
        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestServiceInstantiationRace:
    """Race condition tests for service instantiation."""

    def test_concurrent_instantiation_no_shared_state(self) -> None:
        """Verify concurrent instantiation doesn't share mutable state."""
        services = []
        errors = []
        lock = threading.Lock()

        def create_with_unique_config(index: int) -> None:
            try:
                service = DataCollectorService(
                    espn_interval=15 + index,
                    kalshi_interval=30 + index,
                    leagues=[f"league_{index}"],
                )
                with lock:
                    services.append(service)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=create_with_unique_config, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(services) == 50

        # Verify each service has unique config
        intervals = [s.espn_interval for s in services]
        assert len(set(intervals)) == 50  # All unique


class TestSignalHandlerRace:
    """Race condition tests for signal handler setup."""

    def test_concurrent_signal_handler_setup(self) -> None:
        """Verify concurrent signal handler setup is safe.

        Note: Signal handlers can only be set up in the main thread.
        This test verifies that the service gracefully handles being
        instantiated from non-main threads.
        """
        errors = []
        services = []
        lock = threading.Lock()

        def create_service() -> None:
            try:
                # Signal handlers can only be set in main thread
                # So we just verify service creation works from threads
                service = DataCollectorService()
                with lock:
                    services.append(service)
            except ValueError as e:
                # Expected for signal-related operations from non-main thread
                if "signal only works in main thread" in str(e):
                    with lock:
                        services.append(None)  # Record that we tried
                else:
                    with lock:
                        errors.append(e)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=create_service) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(services) == 20  # All threads completed
