"""
Integration tests for DataCollectorService (service_runner) module.

Integration tests verify that the DataCollectorService works correctly with
real (or realistic mock) dependencies, focusing on inter-component interactions
rather than isolated unit behavior.

Test Categories:
    1. PID File Lifecycle - Full PID file management flow
    2. Supervisor Integration - DataCollectorService with ServiceSupervisor
    3. Configuration Flow - Config propagation from CLI to services
    4. Logging Integration - Logging setup and file creation
    5. Platform Detection - Cross-platform path handling

Educational Note:
    Integration tests for service runners focus on:
    - File system operations: PID files, log files
    - Component integration: Service wrapping supervisor
    - Configuration flow: CLI args to service config to supervisor
    - Realistic timing: Actual delays (but shorter than production)

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern)
Requirements: REQ-DATA-001, REQ-OBSERV-001, REQ-TEST-002
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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

pytestmark = [pytest.mark.integration]


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_service_factory():
    """Create a factory for mock services."""

    def factory(name: str = "mock"):
        mock = MagicMock()
        mock.is_running.return_value = True
        mock.get_stats.return_value = {"polls_completed": 0, "errors": 0}
        return mock

    return factory


# =============================================================================
# PID File Lifecycle Integration Tests
# =============================================================================


class TestPIDFileLifecycle:
    """Integration tests for complete PID file lifecycle.

    Educational Note:
        PID file lifecycle includes:
        1. Check for existing PID (avoid duplicate instances)
        2. Write PID on startup
        3. Read PID for status checks
        4. Remove PID on shutdown
    """

    def test_full_pid_file_lifecycle(self, temp_dir: Path) -> None:
        """Verify complete PID file lifecycle: create, read, remove."""
        pid_file = temp_dir / "test.pid"

        # 1. Initially, no PID file
        assert not pid_file.exists()
        assert read_pid_file(pid_file) is None

        # 2. Write PID
        write_pid_file(pid_file)
        assert pid_file.exists()

        # 3. Read PID back
        pid = read_pid_file(pid_file)
        assert pid == os.getpid()

        # 4. Remove PID
        remove_pid_file(pid_file)
        assert not pid_file.exists()
        assert read_pid_file(pid_file) is None

    def test_pid_file_survives_multiple_reads(self, temp_dir: Path) -> None:
        """Verify PID file can be read multiple times."""
        pid_file = temp_dir / "test.pid"
        write_pid_file(pid_file)

        # Multiple reads should return same value
        for _ in range(5):
            assert read_pid_file(pid_file) == os.getpid()

        remove_pid_file(pid_file)

    def test_pid_file_creates_parent_directory(self, temp_dir: Path) -> None:
        """Verify PID file creation creates parent directories."""
        nested_pid = temp_dir / "nested" / "deep" / "test.pid"

        assert not nested_pid.parent.exists()
        write_pid_file(nested_pid)
        assert nested_pid.exists()
        assert read_pid_file(nested_pid) == os.getpid()

    def test_stale_pid_detection(self, temp_dir: Path) -> None:
        """Verify stale PID detection (process not running)."""
        pid_file = temp_dir / "stale.pid"

        # Write a fake PID that definitely isn't running
        # Use a very high PID unlikely to exist
        pid_file.write_text("9999999")

        pid = read_pid_file(pid_file)
        assert pid == 9999999
        assert not is_process_running(pid)

    def test_current_process_detection(self) -> None:
        """Verify current process is detected as running."""
        current_pid = os.getpid()
        assert is_process_running(current_pid)


# =============================================================================
# Configuration Flow Integration Tests
# =============================================================================


class TestConfigurationFlow:
    """Integration tests for configuration flow.

    Educational Note:
        Configuration flows from:
        CLI args -> DataCollectorService -> ServiceSupervisor -> Individual pollers

        Tests verify configuration values propagate correctly.
    """

    def test_service_stores_configuration(self) -> None:
        """Verify DataCollectorService stores configuration correctly."""
        service = DataCollectorService(
            espn_enabled=True,
            kalshi_enabled=False,
            espn_interval=30,
            kalshi_interval=60,
            health_interval=120,
            metrics_interval=300,
            leagues=["nfl", "nba"],
            debug=True,
        )

        assert service.espn_enabled is True
        assert service.kalshi_enabled is False
        assert service.espn_interval == 30
        assert service.kalshi_interval == 60
        assert service.health_interval == 120
        assert service.metrics_interval == 300
        assert service.leagues == ["nfl", "nba"]
        assert service.debug is True

    def test_default_leagues_populated(self) -> None:
        """Verify default leagues are populated when None provided."""
        service = DataCollectorService(leagues=None)
        assert len(service.leagues) > 0
        assert "nfl" in service.leagues

    def test_configuration_propagates_to_supervisor(self) -> None:
        """Verify configuration propagates to supervisor creation.

        Educational Note:
            When _create_supervisor is called, it should use
            the configuration values set on the service.
        """
        service = DataCollectorService(
            espn_enabled=True,
            kalshi_enabled=False,
            espn_interval=25,
            kalshi_interval=50,
            health_interval=100,
            metrics_interval=200,
        )

        # Mock pollers to avoid network calls
        with patch("precog.runners.service_runner.create_espn_poller") as mock_espn:
            mock_espn.return_value = MagicMock()

            supervisor = service._create_supervisor()

            # Verify supervisor config uses service values
            assert supervisor.config.health_check_interval == 100
            assert supervisor.config.metrics_interval == 200


# =============================================================================
# Logging Integration Tests
# =============================================================================


class TestLoggingIntegration:
    """Integration tests for logging setup.

    Educational Note:
        Logging integration tests verify:
        - Log directory creation
        - Log file creation
        - Handler configuration
        - Level propagation
    """

    def test_log_dir_path_is_valid(self) -> None:
        """Verify get_log_dir returns a valid path."""
        log_dir = get_log_dir()
        assert isinstance(log_dir, Path)

    def test_pid_file_path_is_valid(self) -> None:
        """Verify get_pid_file returns a valid path."""
        pid_file = get_pid_file()
        assert isinstance(pid_file, Path)
        assert pid_file.suffix == ".pid"

    def test_setup_logging_creates_log_file(self) -> None:
        """Verify setup_logging creates log file.

        Educational Note:
            On Windows, file handlers keep the log file locked.
            We clean up handlers to avoid PermissionError.
        """
        import logging

        with tempfile.TemporaryDirectory() as tmpdir:
            from precog.runners.service_runner import setup_logging

            logger = setup_logging(Path(tmpdir), debug=True)

            try:
                assert logger is not None
                # Log file should have been created
                log_files = list(Path(tmpdir).glob("*.log"))
                assert len(log_files) >= 1
            finally:
                # Clean up handlers to release file locks (Windows)
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)
                # Also clean root logger
                root_logger = logging.getLogger()
                for handler in root_logger.handlers[:]:
                    if hasattr(handler, "baseFilename") and tmpdir in str(
                        getattr(handler, "baseFilename", "")
                    ):
                        handler.close()
                        root_logger.removeHandler(handler)

    def test_debug_mode_sets_debug_level(self) -> None:
        """Verify debug=True sets DEBUG log level.

        Educational Note:
            On Windows, file handlers keep the log file locked.
            We clean up handlers to avoid PermissionError.
            The setup_logging function sets level on root logger.
        """
        import logging

        with tempfile.TemporaryDirectory() as tmpdir:
            from precog.runners.service_runner import setup_logging

            logger = setup_logging(Path(tmpdir), debug=True)
            root_logger = logging.getLogger()

            try:
                # Check that DEBUG level is set somewhere (logger, root, or handlers)
                # setup_logging sets level on root logger, not on returned logger
                debug_level_found = (
                    logger.level == logging.DEBUG
                    or root_logger.level == logging.DEBUG
                    or any(h.level == logging.DEBUG for h in logger.handlers)
                    or any(h.level == logging.DEBUG for h in root_logger.handlers)
                )
                assert debug_level_found, "Debug level should be set on logger or root"
            finally:
                # Clean up handlers to release file locks (Windows)
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)
                # Also clean root logger
                for handler in root_logger.handlers[:]:
                    if hasattr(handler, "baseFilename") and tmpdir in str(
                        getattr(handler, "baseFilename", "")
                    ):
                        handler.close()
                        root_logger.removeHandler(handler)


# =============================================================================
# Service State Integration Tests
# =============================================================================


class TestServiceStateIntegration:
    """Integration tests for service state management.

    Educational Note:
        Service state tests verify:
        - Initial state is correct
        - State transitions happen correctly
        - State is consistent across operations
    """

    def test_service_initial_state(self) -> None:
        """Verify DataCollectorService initializes with correct state."""
        service = DataCollectorService()

        assert service._shutdown_requested is False
        assert service.supervisor is None
        assert service.logger is None

    def test_service_has_valid_paths_after_init(self) -> None:
        """Verify service has valid paths after initialization."""
        service = DataCollectorService()

        assert isinstance(service.pid_file, Path)
        assert isinstance(service.log_dir, Path)
        assert service.pid_file.suffix == ".pid"


# =============================================================================
# Status Check Integration Tests
# =============================================================================


class TestStatusCheckIntegration:
    """Integration tests for service status checking.

    Educational Note:
        Status checks allow external monitoring to verify
        service health without disrupting operation.
    """

    def test_status_reports_not_running_without_pid(self, temp_dir: Path) -> None:
        """Verify status reports not running when no PID file."""
        service = DataCollectorService()
        service.pid_file = temp_dir / "nonexistent.pid"

        # Should return 1 (not running)
        with patch("builtins.print"):
            result = service.status()

        assert result == 1

    def test_status_reports_stale_pid(self, temp_dir: Path) -> None:
        """Verify status reports stale PID correctly."""
        service = DataCollectorService()
        pid_file = temp_dir / "stale.pid"

        # Write a stale PID
        pid_file.write_text("9999999")
        service.pid_file = pid_file

        with patch("builtins.print") as mock_print:
            result = service.status()

        assert result == 1
        # Should mention "NOT RUNNING" or "stale"
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("NOT RUNNING" in str(call) or "stale" in str(call) for call in calls)


# =============================================================================
# Stop Command Integration Tests
# =============================================================================


class TestStopCommandIntegration:
    """Integration tests for service stop command.

    Educational Note:
        Stop command tests verify:
        - Graceful shutdown signal delivery
        - PID file cleanup
        - Error handling for various scenarios
    """

    def test_stop_handles_no_pid_file(self, temp_dir: Path) -> None:
        """Verify stop handles missing PID file gracefully."""
        service = DataCollectorService()
        service.pid_file = temp_dir / "nonexistent.pid"

        with patch("builtins.print"):
            result = service.stop()

        assert result == 1  # Error code for not running

    def test_stop_removes_stale_pid(self, temp_dir: Path) -> None:
        """Verify stop removes stale PID file."""
        service = DataCollectorService()
        pid_file = temp_dir / "stale.pid"

        # Write a stale PID
        pid_file.write_text("9999999")
        service.pid_file = pid_file

        with patch("builtins.print"):
            result = service.stop()

        # Should succeed (stale PID cleaned up)
        assert result == 0
        assert not pid_file.exists()


# =============================================================================
# Platform Integration Tests
# =============================================================================


class TestPlatformIntegration:
    """Integration tests for cross-platform behavior.

    Educational Note:
        Platform integration tests verify:
        - Correct path selection per platform
        - Platform-specific APIs work correctly
        - Fallbacks when platform features unavailable
    """

    def test_platform_paths_contain_precog(self) -> None:
        """Verify platform paths contain precog identifier."""
        pid_path = get_pid_file()
        path_str = str(pid_path).lower()

        assert "precog" in path_str or "var/run" in path_str

    def test_is_process_running_returns_bool(self) -> None:
        """Verify is_process_running always returns boolean."""
        # Test with current PID
        assert isinstance(is_process_running(os.getpid()), bool)

        # Test with invalid PID
        assert isinstance(is_process_running(9999999), bool)

        # Test with edge cases
        assert isinstance(is_process_running(0), bool)
        assert isinstance(is_process_running(1), bool)


# =============================================================================
# Signal Handler Integration Tests
# =============================================================================


class TestSignalHandlerIntegration:
    """Integration tests for signal handling.

    Educational Note:
        Signal handlers must:
        - Not raise exceptions
        - Set shutdown flag
        - Trigger supervisor stop
    """

    def test_signal_handler_sets_shutdown_flag(self) -> None:
        """Verify signal handler sets shutdown flag."""
        import signal

        service = DataCollectorService()

        # Manually call the signal handler
        service._signal_handler(signal.SIGTERM, None)

        assert service._shutdown_requested is True

    def test_signal_handler_with_logger(self) -> None:
        """Verify signal handler works with logger set."""
        import signal

        service = DataCollectorService()
        service.logger = MagicMock()

        service._signal_handler(signal.SIGINT, None)

        assert service._shutdown_requested is True
        service.logger.info.assert_called()

    def test_signal_handler_stops_supervisor(self) -> None:
        """Verify signal handler stops supervisor if running."""
        import signal

        service = DataCollectorService()
        mock_supervisor = MagicMock()
        service.supervisor = mock_supervisor

        service._signal_handler(signal.SIGTERM, None)

        mock_supervisor.stop_all.assert_called_once()


# =============================================================================
# Startup Validation Integration Tests
# =============================================================================


class TestStartupValidationIntegration:
    """Integration tests for startup validation.

    Educational Note:
        Startup validation prevents running with invalid configuration:
        - Environment config must load
        - Database must be accessible
        - Required modules must be importable
    """

    @patch("precog.runners.service_runner.load_environment_config")
    def test_validation_fails_on_env_error(self, mock_load: MagicMock) -> None:
        """Verify validation fails when environment config fails."""
        mock_load.side_effect = Exception("Config error")

        service = DataCollectorService()
        service.logger = MagicMock()

        result = service._validate_startup()

        assert result is False
        service.logger.error.assert_called()

    @patch("precog.runners.service_runner.load_environment_config")
    @patch("precog.database.connection.test_connection")
    def test_validation_fails_on_db_error(
        self, mock_test_conn: MagicMock, mock_load: MagicMock
    ) -> None:
        """Verify validation fails when database unavailable."""
        mock_load.return_value = MagicMock(
            app_env=MagicMock(value="development"),
            database_name="test_db",
        )
        mock_test_conn.return_value = False

        service = DataCollectorService()
        service.logger = MagicMock()

        result = service._validate_startup()

        assert result is False
        # Should log database error
        error_calls = [str(c) for c in service.logger.error.call_args_list]
        assert any(
            "database" in str(c).lower() or "connection" in str(c).lower() for c in error_calls
        )

    @patch("precog.runners.service_runner.load_environment_config")
    @patch("precog.database.connection.test_connection")
    def test_validation_passes_with_valid_config(
        self, mock_test_conn: MagicMock, mock_load: MagicMock
    ) -> None:
        """Verify validation passes with valid configuration."""
        mock_load.return_value = MagicMock(
            app_env=MagicMock(value="development"),
            database_name="test_db",
        )
        mock_test_conn.return_value = True

        service = DataCollectorService(
            espn_enabled=False,  # Skip ESPN module check
            kalshi_enabled=False,  # Skip Kalshi credential check
        )
        service.logger = MagicMock()

        result = service._validate_startup()

        assert result is True
        service.logger.info.assert_called()
