"""
Unit tests for service_runner module.

Tests the DataCollectorService class and helper functions with mocked
dependencies to verify production service management logic.

Test Coverage:
    - Platform helper functions (PID file, log dir, process detection)
    - DataCollectorService initialization
    - Startup validation logic
    - Signal handling setup
    - Service lifecycle (start, stop, status)

Educational Note:
    These tests use extensive mocking because we're testing the "wrapper"
    logic around ServiceSupervisor, not the actual data collection. The
    ServiceSupervisor itself is tested in tests/unit/schedulers/.

Reference:
    - Issue #193: Phase 2.5 Live Data Collection Service
    - ADR-100: Service Supervisor Pattern
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.runners.service_runner import (
    DEFAULT_ESPN_INTERVAL,
    DEFAULT_HEALTH_CHECK_INTERVAL,
    DEFAULT_KALSHI_INTERVAL,
    DEFAULT_LEAGUES,
    DEFAULT_METRICS_INTERVAL,
    DataCollectorService,
    get_log_dir,
    get_pid_file,
    is_process_running,
    read_pid_file,
    remove_pid_file,
    setup_logging,
    write_pid_file,
)

# =============================================================================
# Helper Function Tests
# =============================================================================


@pytest.mark.unit
class TestPidFileHelpers:
    """Tests for PID file management functions."""

    def test_write_and_read_pid_file(self, tmp_path: Path) -> None:
        """Test writing and reading PID file."""
        pid_file = tmp_path / "test.pid"

        # Write PID
        with patch("os.getpid", return_value=12345):
            write_pid_file(pid_file)

        assert pid_file.exists()
        assert pid_file.read_text() == "12345"

        # Read PID
        result = read_pid_file(pid_file)
        assert result == 12345

    def test_read_pid_file_not_exists(self, tmp_path: Path) -> None:
        """Test reading non-existent PID file returns None."""
        pid_file = tmp_path / "nonexistent.pid"
        result = read_pid_file(pid_file)
        assert result is None

    def test_read_pid_file_invalid_content(self, tmp_path: Path) -> None:
        """Test reading PID file with invalid content returns None."""
        pid_file = tmp_path / "invalid.pid"
        pid_file.write_text("not-a-number")

        result = read_pid_file(pid_file)
        assert result is None

    def test_remove_pid_file(self, tmp_path: Path) -> None:
        """Test removing PID file."""
        pid_file = tmp_path / "remove.pid"
        pid_file.write_text("12345")

        assert pid_file.exists()
        remove_pid_file(pid_file)
        assert not pid_file.exists()

    def test_remove_pid_file_not_exists(self, tmp_path: Path) -> None:
        """Test removing non-existent PID file doesn't raise."""
        pid_file = tmp_path / "nonexistent.pid"
        # Should not raise
        remove_pid_file(pid_file)

    def test_get_pid_file_windows(self) -> None:
        """Test PID file path on Windows."""
        with patch("sys.platform", "win32"):
            with patch.object(Path, "mkdir"):
                result = get_pid_file()
                assert ".precog" in str(result)
                assert "data_collector.pid" in str(result)

    def test_get_pid_file_linux_fallback(self) -> None:
        """Test PID file path falls back to home dir on Linux when /var/run not writable."""
        with patch("sys.platform", "linux"):
            with patch.object(Path, "exists", return_value=False):
                with patch.object(Path, "mkdir"):
                    result = get_pid_file()
                    assert ".precog" in str(result)


@pytest.mark.unit
class TestLogDirHelpers:
    """Tests for log directory functions."""

    def test_get_log_dir_windows(self) -> None:
        """Test log directory on Windows."""
        with patch("sys.platform", "win32"):
            with patch.object(Path, "mkdir"):
                result = get_log_dir()
                assert ".precog" in str(result)
                assert "logs" in str(result)

    def test_get_log_dir_linux_fallback(self) -> None:
        """Test log directory falls back on Linux when /var/log not writable."""
        with patch("sys.platform", "linux"):
            with patch.object(Path, "exists", return_value=False):
                with patch.object(Path, "mkdir"):
                    result = get_log_dir()
                    assert ".precog" in str(result)


@pytest.mark.unit
class TestProcessDetection:
    """Tests for process detection functions."""

    def test_is_process_running_current_process(self) -> None:
        """Test detecting current process is running."""
        # Current process should always be running
        current_pid = os.getpid()
        assert is_process_running(current_pid) is True

    def test_is_process_running_invalid_pid(self) -> None:
        """Test detecting non-existent process."""
        # Use a PID that's very unlikely to exist
        assert is_process_running(999999999) is False


@pytest.mark.unit
class TestSetupLogging:
    """Tests for logging setup."""

    def test_setup_logging_creates_logger(self, tmp_path: Path) -> None:
        """Test that setup_logging creates a configured logger."""
        logger = setup_logging(tmp_path, debug=False)

        assert logger is not None
        assert logger.name == "precog.data_collector"

        # Verify log file was created
        log_files = list(tmp_path.glob("data_collector_*.log"))
        assert len(log_files) >= 1

    def test_setup_logging_debug_mode(self, tmp_path: Path) -> None:
        """Test that debug mode sets correct log level."""
        import logging

        logger = setup_logging(tmp_path, debug=True)
        # Debug mode should allow DEBUG level messages
        parent_level = logger.parent.level if logger.parent else logging.NOTSET
        assert logger.level <= logging.DEBUG or parent_level <= logging.DEBUG


# =============================================================================
# DataCollectorService Tests
# =============================================================================


@pytest.mark.unit
class TestDataCollectorServiceInit:
    """Tests for DataCollectorService initialization."""

    def test_default_initialization(self) -> None:
        """Test service initializes with default values."""
        service = DataCollectorService()

        assert service.espn_enabled is True
        assert service.kalshi_enabled is True
        assert service.espn_interval == DEFAULT_ESPN_INTERVAL
        assert service.kalshi_interval == DEFAULT_KALSHI_INTERVAL
        assert service.health_interval == DEFAULT_HEALTH_CHECK_INTERVAL
        assert service.metrics_interval == DEFAULT_METRICS_INTERVAL
        assert service.leagues == DEFAULT_LEAGUES
        assert service.debug is False
        assert service._shutdown_requested is False

    def test_custom_initialization(self) -> None:
        """Test service initializes with custom values."""
        custom_leagues = ["nfl", "nba"]
        service = DataCollectorService(
            espn_enabled=False,
            kalshi_enabled=True,
            espn_interval=30,
            kalshi_interval=60,
            health_interval=120,
            metrics_interval=600,
            leagues=custom_leagues,
            debug=True,
        )

        assert service.espn_enabled is False
        assert service.kalshi_enabled is True
        assert service.espn_interval == 30
        assert service.kalshi_interval == 60
        assert service.health_interval == 120
        assert service.metrics_interval == 600
        assert service.leagues == custom_leagues
        assert service.debug is True

    def test_leagues_default_copy(self) -> None:
        """Test that default leagues list is copied, not shared."""
        service1 = DataCollectorService()
        service2 = DataCollectorService()

        # Modifying one should not affect the other
        service1.leagues.append("test")
        assert "test" not in service2.leagues


@pytest.mark.unit
class TestDataCollectorServiceValidation:
    """Tests for startup validation logic."""

    def test_validate_startup_success(self) -> None:
        """Test successful startup validation."""
        service = DataCollectorService()
        service.logger = MagicMock()

        with patch("precog.runners.service_runner.load_environment_config") as mock_env:
            mock_env.return_value = MagicMock(
                app_env=MagicMock(value="development"),
                database_name="precog_test",
            )
            # Patch at the source module where test_connection is defined
            with patch("precog.database.connection.test_connection", return_value=True):
                result = service._validate_startup()

        assert result is True

    def test_validate_startup_env_config_failure(self) -> None:
        """Test validation fails when environment config fails."""
        service = DataCollectorService()
        service.logger = MagicMock()

        with patch(
            "precog.runners.service_runner.load_environment_config",
            side_effect=Exception("Config error"),
        ):
            result = service._validate_startup()

        assert result is False
        service.logger.error.assert_called()

    def test_validate_startup_db_failure(self) -> None:
        """Test validation fails when database connection fails."""
        service = DataCollectorService()
        service.logger = MagicMock()

        with patch("precog.runners.service_runner.load_environment_config") as mock_env:
            mock_env.return_value = MagicMock(
                app_env=MagicMock(value="development"),
                database_name="precog_test",
            )
            # Patch at the source module where test_connection is defined
            with patch("precog.database.connection.test_connection", return_value=False):
                result = service._validate_startup()

        assert result is False

    def test_validate_startup_kalshi_live_missing_credentials(self) -> None:
        """Test validation fails when Kalshi live mode lacks credentials."""
        service = DataCollectorService(kalshi_enabled=True)
        service.logger = MagicMock()

        with patch("precog.runners.service_runner.load_environment_config") as mock_env:
            mock_env.return_value = MagicMock(
                app_env=MagicMock(value="development"),
                database_name="precog_test",
            )
            # Patch at the source module where test_connection is defined
            with patch("precog.database.connection.test_connection", return_value=True):
                with patch.dict(os.environ, {"KALSHI_MODE": "live"}, clear=False):
                    # Remove credentials
                    with patch.dict(
                        os.environ,
                        {"KALSHI_KEY_ID": "", "KALSHI_PRIVATE_KEY_PATH": ""},
                        clear=False,
                    ):
                        result = service._validate_startup()

        assert result is False


@pytest.mark.unit
class TestDataCollectorServiceStatus:
    """Tests for service status checking."""

    def test_status_not_running_no_pid(self, tmp_path: Path, capsys) -> None:
        """Test status when no PID file exists."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "nonexistent.pid"

        result = service.status()

        assert result == 1
        captured = capsys.readouterr()
        assert "NOT RUNNING" in captured.out

    def test_status_running(self, tmp_path: Path, capsys) -> None:
        """Test status when service is running."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"

        # Write current process PID (which is running)
        service.pid_file.write_text(str(os.getpid()))

        result = service.status()

        assert result == 0
        captured = capsys.readouterr()
        assert "RUNNING" in captured.out

    def test_status_stale_pid(self, tmp_path: Path, capsys) -> None:
        """Test status when PID file exists but process not running."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"

        # Write a PID that doesn't exist
        service.pid_file.write_text("999999999")

        result = service.status()

        assert result == 1
        captured = capsys.readouterr()
        assert "NOT RUNNING" in captured.out
        assert "stale" in captured.out.lower()


@pytest.mark.unit
class TestDataCollectorServiceStop:
    """Tests for stopping the service."""

    def test_stop_no_pid_file(self, tmp_path: Path, capsys) -> None:
        """Test stop when no PID file exists."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "nonexistent.pid"

        result = service.stop()

        assert result == 1
        captured = capsys.readouterr()
        assert "No PID file found" in captured.out

    def test_stop_stale_pid(self, tmp_path: Path, capsys) -> None:
        """Test stop when PID file exists but process not running."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"
        service.pid_file.write_text("999999999")

        result = service.stop()

        assert result == 0
        captured = capsys.readouterr()
        assert "not running" in captured.out.lower()
        # PID file should be removed
        assert not service.pid_file.exists()


@pytest.mark.unit
class TestDataCollectorServiceSignalHandling:
    """Tests for signal handling setup."""

    def test_setup_signal_handlers(self) -> None:
        """Test that signal handlers are registered."""
        import signal

        service = DataCollectorService()

        with patch.object(signal, "signal") as mock_signal:
            service._setup_signal_handlers()

            # Should register SIGTERM and SIGINT at minimum
            calls = [call[0][0] for call in mock_signal.call_args_list]
            assert signal.SIGTERM in calls
            assert signal.SIGINT in calls

    def test_signal_handler_sets_shutdown_flag(self) -> None:
        """Test that signal handler sets shutdown flag."""
        import signal

        service = DataCollectorService()
        service.logger = MagicMock()
        service.supervisor = MagicMock()

        assert service._shutdown_requested is False

        # Simulate receiving SIGTERM
        service._signal_handler(signal.SIGTERM, None)

        assert service._shutdown_requested is True
        service.supervisor.stop_all.assert_called_once()  # type: ignore[unreachable]


@pytest.mark.unit
class TestDataCollectorServiceSupervisorCreation:
    """Tests for supervisor creation logic."""

    def test_create_supervisor_espn_only(self) -> None:
        """Test supervisor creation with ESPN only."""
        service = DataCollectorService(espn_enabled=True, kalshi_enabled=False)

        with patch("precog.runners.service_runner.create_espn_poller") as mock_espn:
            with patch("precog.runners.service_runner.create_kalshi_poller") as mock_kalshi:
                mock_espn.return_value = MagicMock()
                supervisor = service._create_supervisor()

                mock_espn.assert_called_once()
                mock_kalshi.assert_not_called()
                assert supervisor is not None

    def test_create_supervisor_kalshi_only(self) -> None:
        """Test supervisor creation with Kalshi only."""
        service = DataCollectorService(espn_enabled=False, kalshi_enabled=True)

        with patch("precog.runners.service_runner.create_espn_poller") as mock_espn:
            with patch("precog.runners.service_runner.create_kalshi_poller") as mock_kalshi:
                mock_kalshi.return_value = MagicMock()
                supervisor = service._create_supervisor()

                mock_espn.assert_not_called()
                mock_kalshi.assert_called_once()
                assert supervisor is not None

    def test_create_supervisor_both_services(self) -> None:
        """Test supervisor creation with both services."""
        service = DataCollectorService(espn_enabled=True, kalshi_enabled=True)

        with patch("precog.runners.service_runner.create_espn_poller") as mock_espn:
            with patch("precog.runners.service_runner.create_kalshi_poller") as mock_kalshi:
                mock_espn.return_value = MagicMock()
                mock_kalshi.return_value = MagicMock()
                supervisor = service._create_supervisor()

                mock_espn.assert_called_once()
                mock_kalshi.assert_called_once()
                assert supervisor is not None

    def test_create_supervisor_environment_mapping(self) -> None:
        """Test environment string is correctly mapped."""
        from precog.schedulers.service_supervisor import Environment

        service = DataCollectorService()

        test_cases = [
            ("dev", Environment.DEVELOPMENT),
            ("development", Environment.DEVELOPMENT),
            ("staging", Environment.STAGING),
            ("prod", Environment.PRODUCTION),
            ("production", Environment.PRODUCTION),
        ]

        for env_str, expected_env in test_cases:
            with patch.dict(os.environ, {"PRECOG_ENV": env_str}):
                with patch("precog.runners.service_runner.create_espn_poller") as mock_espn:
                    with patch("precog.runners.service_runner.create_kalshi_poller") as mock_kalshi:
                        mock_espn.return_value = MagicMock()
                        mock_kalshi.return_value = MagicMock()
                        supervisor = service._create_supervisor()
                        assert supervisor.config.environment == expected_env


@pytest.mark.unit
class TestDataCollectorServiceStart:
    """Tests for service start logic."""

    def test_start_already_running(self, tmp_path: Path) -> None:
        """Test start fails when service already running."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"
        service.log_dir = tmp_path

        # Write current process PID to simulate already running
        service.pid_file.write_text(str(os.getpid()))

        result = service.start()

        assert result == 3  # Already running exit code

    def test_start_validation_fails(self, tmp_path: Path) -> None:
        """Test start fails when validation fails."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"
        service.log_dir = tmp_path

        with patch.object(service, "_validate_startup", return_value=False):
            result = service.start()

        assert result == 1  # Startup error exit code
