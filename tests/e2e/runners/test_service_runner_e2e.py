"""
End-to-End Tests for DataCollectorService.

These tests validate the complete service runner functionality including
PID file management, logging setup, and service lifecycle.

Educational Note:
    The service_runner.py module wraps ServiceSupervisor with production
    concerns (PID files, signals, logging). E2E tests verify these work
    correctly in the actual runtime environment without mocks.

    Key lesson: PID file and signal handling must be tested with real
    filesystem and process operations to catch platform-specific issues.

Prerequisites:
    - Write access to ~/.precog/ directory
    - PostgreSQL running (for startup validation)

Run with:
    pytest tests/e2e/runners/test_service_runner_e2e.py -v -m e2e

References:
    - Issue #217: Add missing modules to MODULE_TIERS audit
    - Issue #193: Phase 2.5 Live Data Collection Service
    - ADR-100: Service Supervisor Pattern

Phase: 2.5 (Service Infrastructure)
"""

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e]


class TestPIDFileManagement:
    """E2E tests for PID file operations.

    Educational Note:
        PID files are critical for service management - they prevent
        multiple instances and enable external process control. These
        tests verify the actual filesystem operations work correctly.
    """

    def test_write_and_read_pid_file(self, tmp_path: Path) -> None:
        """Verify PID file can be written and read back.

        Educational Note:
            This test uses a temp directory to avoid polluting the
            actual PID file location. The operations are identical
            to production usage.
        """
        from precog.runners.service_runner import read_pid_file, write_pid_file

        pid_file = tmp_path / "test.pid"

        # Write PID file
        write_pid_file(pid_file)

        # Read it back
        read_pid = read_pid_file(pid_file)

        assert read_pid is not None
        assert read_pid == os.getpid()

    def test_read_nonexistent_pid_file_returns_none(self, tmp_path: Path) -> None:
        """Verify reading nonexistent PID file returns None gracefully."""
        from precog.runners.service_runner import read_pid_file

        pid_file = tmp_path / "nonexistent.pid"

        result = read_pid_file(pid_file)

        assert result is None

    def test_remove_pid_file(self, tmp_path: Path) -> None:
        """Verify PID file removal works correctly."""
        from precog.runners.service_runner import remove_pid_file, write_pid_file

        pid_file = tmp_path / "test.pid"
        write_pid_file(pid_file)

        # Verify it exists
        assert pid_file.exists()

        # Remove it
        remove_pid_file(pid_file)

        # Verify it's gone
        assert not pid_file.exists()

    def test_remove_nonexistent_pid_file_no_error(self, tmp_path: Path) -> None:
        """Verify removing nonexistent PID file doesn't raise error."""
        from precog.runners.service_runner import remove_pid_file

        pid_file = tmp_path / "nonexistent.pid"

        # Should not raise
        remove_pid_file(pid_file)


class TestProcessDetection:
    """E2E tests for process detection functionality.

    Educational Note:
        Process detection uses platform-specific APIs (Windows vs Unix).
        E2E tests verify both code paths work on the current platform.
    """

    def test_is_process_running_detects_current_process(self) -> None:
        """Verify current process is detected as running."""
        from precog.runners.service_runner import is_process_running

        current_pid = os.getpid()

        result = is_process_running(current_pid)

        assert result is True, "Current process should be detected as running"

    def test_is_process_running_returns_false_for_invalid_pid(self) -> None:
        """Verify invalid PID returns False.

        Educational Note:
            Using a very high PID that's unlikely to exist. This tests
            the error handling path when the process doesn't exist.
        """
        from precog.runners.service_runner import is_process_running

        # Use a high PID that almost certainly doesn't exist
        invalid_pid = 99999999

        result = is_process_running(invalid_pid)

        assert result is False


class TestLoggingSetup:
    """E2E tests for logging configuration.

    Educational Note:
        Logging setup creates actual log files. E2E tests verify
        the files are created in the correct location with the
        correct format.
    """

    def test_setup_logging_creates_log_file(self, tmp_path: Path) -> None:
        """Verify logging setup creates a log file."""
        from precog.runners.service_runner import setup_logging

        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        logger = setup_logging(log_dir, debug=False)

        # Write a test message
        logger.info("Test log message")

        # Verify log file was created
        log_files = list(log_dir.glob("data_collector_*.log"))
        assert len(log_files) >= 1, "Log file should be created"

        # Verify content was written
        log_content = log_files[0].read_text()
        assert "Test log message" in log_content

    def test_setup_logging_debug_mode(self, tmp_path: Path) -> None:
        """Verify debug mode enables DEBUG level logging."""
        import logging

        from precog.runners.service_runner import setup_logging

        log_dir = tmp_path / "logs_debug"
        log_dir.mkdir()

        logger = setup_logging(log_dir, debug=True)

        # Logger should be at DEBUG level
        assert logger.getEffectiveLevel() <= logging.DEBUG


class TestPlatformPaths:
    """E2E tests for platform-specific path detection.

    Educational Note:
        The service uses different paths on Windows vs Unix.
        E2E tests verify the correct paths are returned.
    """

    def test_get_pid_file_returns_valid_path(self) -> None:
        """Verify get_pid_file returns a valid, writable path."""
        from precog.runners.service_runner import get_pid_file

        pid_file = get_pid_file()

        # Path should be a Path object
        assert isinstance(pid_file, Path)

        # Parent directory should exist or be creatable
        assert pid_file.parent.exists() or not pid_file.parent.parent.exists()

        # Verify we can write to the directory
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        test_file = pid_file.parent / ".test_write_access"
        try:
            test_file.touch()
            test_file.unlink()
            can_write = True
        except PermissionError:
            can_write = False

        assert can_write, f"Should have write access to {pid_file.parent}"

    def test_get_log_dir_returns_valid_path(self) -> None:
        """Verify get_log_dir returns a valid, writable path."""
        from precog.runners.service_runner import get_log_dir

        log_dir = get_log_dir()

        # Path should be a Path object
        assert isinstance(log_dir, Path)

        # Directory should exist or be creatable
        log_dir.mkdir(parents=True, exist_ok=True)
        assert log_dir.exists()

        # Verify we can write to it
        test_file = log_dir / ".test_write_access"
        try:
            test_file.touch()
            test_file.unlink()
            can_write = True
        except PermissionError:
            can_write = False

        assert can_write, f"Should have write access to {log_dir}"


class TestDataCollectorServiceCreation:
    """E2E tests for DataCollectorService instantiation.

    Educational Note:
        These tests verify the service can be created with various
        configurations without actually starting it (which would
        require full infrastructure).
    """

    def test_service_creation_with_defaults(self) -> None:
        """Verify service can be created with default settings."""
        from precog.runners.service_runner import DataCollectorService

        service = DataCollectorService()

        assert service.espn_enabled is True
        assert service.kalshi_enabled is True
        assert service.leagues == ["nfl", "nba", "nhl", "ncaaf", "ncaab"]

    def test_service_creation_espn_only(self) -> None:
        """Verify service can be created with ESPN only."""
        from precog.runners.service_runner import DataCollectorService

        service = DataCollectorService(
            espn_enabled=True,
            kalshi_enabled=False,
        )

        assert service.espn_enabled is True
        assert service.kalshi_enabled is False

    def test_service_creation_kalshi_only(self) -> None:
        """Verify service can be created with Kalshi only."""
        from precog.runners.service_runner import DataCollectorService

        service = DataCollectorService(
            espn_enabled=False,
            kalshi_enabled=True,
        )

        assert service.espn_enabled is False
        assert service.kalshi_enabled is True

    def test_service_creation_custom_intervals(self) -> None:
        """Verify service accepts custom poll intervals."""
        from precog.runners.service_runner import DataCollectorService

        service = DataCollectorService(
            espn_interval=30,
            kalshi_interval=60,
            health_interval=120,
            metrics_interval=600,
        )

        assert service.espn_interval == 30
        assert service.kalshi_interval == 60
        assert service.health_interval == 120
        assert service.metrics_interval == 600

    def test_service_creation_custom_leagues(self) -> None:
        """Verify service accepts custom league list."""
        from precog.runners.service_runner import DataCollectorService

        custom_leagues = ["nfl", "nba"]
        service = DataCollectorService(leagues=custom_leagues)

        assert service.leagues == custom_leagues

    def test_service_has_correct_pid_file_path(self) -> None:
        """Verify service uses platform-appropriate PID file path."""
        from precog.runners.service_runner import (
            DataCollectorService,
            get_pid_file,
        )

        service = DataCollectorService()

        expected_pid_file = get_pid_file()
        assert service.pid_file == expected_pid_file


class TestServiceStatus:
    """E2E tests for service status checking.

    Educational Note:
        Status checking involves reading PID files and checking
        process state. E2E tests verify the complete flow.
    """

    def test_status_returns_not_running_when_no_pid_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify status returns 'not running' when no PID file exists."""
        from precog.runners.service_runner import DataCollectorService

        # Patch get_pid_file to return path in tmp_path
        nonexistent_pid = tmp_path / "nonexistent.pid"
        monkeypatch.setattr(
            "precog.runners.service_runner.get_pid_file",
            lambda: nonexistent_pid,
        )

        service = DataCollectorService()
        service.pid_file = nonexistent_pid

        exit_code = service.status()

        assert exit_code == 1  # Not running

    def test_status_detects_stale_pid_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify status detects stale PID files (process not running)."""
        from precog.runners.service_runner import DataCollectorService

        # Create a PID file with a non-existent process
        stale_pid_file = tmp_path / "stale.pid"
        stale_pid_file.write_text("99999999")  # Very high PID, unlikely to exist

        service = DataCollectorService()
        service.pid_file = stale_pid_file

        exit_code = service.status()

        assert exit_code == 1  # Not running (stale)
