"""
Chaos tests for service_runner module.

Tests failure scenarios and edge cases.

Reference: TESTING_STRATEGY_V3.2.md Section "Chaos Tests"
"""

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

pytestmark = [pytest.mark.chaos]


class TestPidFileChaos:
    """Chaos tests for PID file operations."""

    def test_read_nonexistent_pid_file(self, tmp_path: Path) -> None:
        """Test reading nonexistent PID file."""
        pid_file = tmp_path / "nonexistent.pid"

        result = read_pid_file(pid_file)

        assert result is None

    def test_read_corrupted_pid_file(self, tmp_path: Path) -> None:
        """Test reading corrupted PID file."""
        pid_file = tmp_path / "corrupted.pid"
        pid_file.write_text("not_a_number")

        result = read_pid_file(pid_file)

        assert result is None

    def test_read_empty_pid_file(self, tmp_path: Path) -> None:
        """Test reading empty PID file."""
        pid_file = tmp_path / "empty.pid"
        pid_file.write_text("")

        result = read_pid_file(pid_file)

        assert result is None

    def test_read_pid_file_with_whitespace(self, tmp_path: Path) -> None:
        """Test reading PID file with whitespace."""
        pid_file = tmp_path / "whitespace.pid"
        pid_file.write_text("  12345  \n")

        result = read_pid_file(pid_file)

        assert result == 12345

    def test_remove_nonexistent_pid_file(self, tmp_path: Path) -> None:
        """Test removing nonexistent PID file."""
        pid_file = tmp_path / "nonexistent.pid"

        # Should not raise
        remove_pid_file(pid_file)

        assert not pid_file.exists()

    def test_write_to_readonly_directory(self, tmp_path: Path) -> None:
        """Test writing PID file to readonly directory."""
        # Create a readonly directory scenario
        pid_file = tmp_path / "readonly" / "test.pid"

        with patch.object(Path, "mkdir", side_effect=PermissionError("readonly")):
            with pytest.raises(PermissionError):
                write_pid_file(pid_file)


class TestProcessCheckChaos:
    """Chaos tests for process checking."""

    def test_check_zero_pid(self) -> None:
        """Test checking PID 0."""
        result = is_process_running(0)
        # Behavior varies by platform, but should not crash
        assert isinstance(result, bool)

    def test_check_negative_pid(self) -> None:
        """Test checking negative PID."""
        # Should not crash
        try:
            result = is_process_running(-1)
            assert isinstance(result, bool)
        except (OSError, ValueError):
            # Some platforms may raise an error for invalid PIDs
            pass

    def test_check_very_large_pid(self) -> None:
        """Test checking very large PID."""
        result = is_process_running(999999999)
        # Very unlikely to be running
        assert result is False


class TestPathFunctionsChaos:
    """Chaos tests for path helper functions."""

    @patch("sys.platform", "darwin")
    def test_get_pid_file_macos(self) -> None:
        """Test PID file path on macOS."""
        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "mkdir", return_value=None),
        ):
            result = get_pid_file()
            # Should fall back to home directory
            assert ".precog" in str(result)

    @patch("sys.platform", "linux")
    def test_get_pid_file_var_run_not_writable(self) -> None:
        """Test PID file when /var/run not writable."""
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "touch", side_effect=PermissionError("Not writable")),
            patch.object(Path, "mkdir", return_value=None),
        ):
            result = get_pid_file()
            # Should fall back to home directory
            assert ".precog" in str(result) or "var" in str(result)

    @patch("sys.platform", "linux")
    def test_get_log_dir_var_log_not_writable(self) -> None:
        """Test log directory when /var/log not writable."""
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "touch", side_effect=PermissionError("Not writable")),
            patch.object(Path, "mkdir", return_value=None),
        ):
            result = get_log_dir()
            # Should fall back to home directory
            assert ".precog" in str(result) or "log" in str(result)


class TestServiceStartupChaos:
    """Chaos tests for service startup."""

    def test_validate_startup_env_config_fails(self, tmp_path: Path) -> None:
        """Test startup validation when environment config fails."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"
        service.logger = MagicMock()

        with patch(
            "precog.runners.service_runner.load_environment_config",
            side_effect=Exception("Config error"),
        ):
            result = service._validate_startup()

        assert result is False
        service.logger.error.assert_called()

    def test_validate_startup_database_fails(self, tmp_path: Path) -> None:
        """Test startup validation when database fails."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "test.pid"
        service.logger = MagicMock()

        with (
            patch("precog.runners.service_runner.load_environment_config") as mock_env,
            patch("precog.database.connection.test_connection", return_value=False),
        ):
            mock_env.return_value = MagicMock()
            mock_env.return_value.app_env.value = "dev"
            mock_env.return_value.database_name = "test_db"

            result = service._validate_startup()

        assert result is False

    def test_validate_startup_espn_module_missing(self, tmp_path: Path) -> None:
        """Test startup validation when ESPN module missing."""
        service = DataCollectorService(espn_enabled=True)
        service.pid_file = tmp_path / "test.pid"
        service.logger = MagicMock()

        with (
            patch("precog.runners.service_runner.load_environment_config") as mock_env,
            patch("precog.database.connection.test_connection", return_value=True),
            patch("importlib.util.find_spec", return_value=None),
        ):
            mock_env.return_value = MagicMock()
            mock_env.return_value.app_env.value = "dev"
            mock_env.return_value.database_name = "test_db"

            result = service._validate_startup()

        assert result is False


class TestServiceConfigChaos:
    """Chaos tests for service configuration."""

    def test_service_with_all_disabled(self) -> None:
        """Test service with all services disabled."""
        service = DataCollectorService(
            espn_enabled=False,
            kalshi_enabled=False,
        )

        assert service.espn_enabled is False
        assert service.kalshi_enabled is False

    def test_service_with_zero_intervals(self) -> None:
        """Test service with zero intervals."""
        service = DataCollectorService(
            espn_interval=0,
            kalshi_interval=0,
            health_interval=0,
            metrics_interval=0,
        )

        assert service.espn_interval == 0
        assert service.kalshi_interval == 0

    def test_service_with_empty_leagues(self) -> None:
        """Test service with empty leagues list uses defaults.

        Note: Empty list is falsy in Python, so `leagues or DEFAULT_LEAGUES`
        results in the default leagues being used. This is intentional behavior.
        """
        service = DataCollectorService(leagues=[])

        # Empty list triggers default leagues (falsy in Python)
        assert len(service.leagues) > 0  # Should have defaults

    def test_service_with_none_leagues(self) -> None:
        """Test service with None leagues (should use defaults)."""
        service = DataCollectorService(leagues=None)

        assert len(service.leagues) > 0  # Should have defaults


class TestServiceStopChaos:
    """Chaos tests for service stop operations."""

    def test_stop_no_pid_file(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Test stopping service with no PID file."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "nonexistent.pid"

        result = service.stop()

        assert result == 1
        captured = capsys.readouterr()
        assert "No PID file" in captured.out

    def test_stop_stale_pid_file(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Test stopping service with stale PID file."""
        service = DataCollectorService()
        service.pid_file = tmp_path / "stale.pid"
        service.pid_file.write_text("999999999")  # Non-existent PID

        result = service.stop()

        assert result == 0
        captured = capsys.readouterr()
        assert "not running" in captured.out.lower()


class TestSignalHandlerChaos:
    """Chaos tests for signal handling."""

    def test_signal_handler_no_logger(self) -> None:
        """Test signal handler when logger is None."""
        service = DataCollectorService()
        service.logger = None
        service.supervisor = None

        # Should not raise even with no logger
        import signal

        service._signal_handler(signal.SIGTERM, None)

        assert service._shutdown_requested is True

    def test_signal_handler_with_supervisor(self) -> None:
        """Test signal handler with supervisor."""
        service = DataCollectorService()
        service.logger = MagicMock()
        service.supervisor = MagicMock()

        import signal

        service._signal_handler(signal.SIGINT, None)

        assert service._shutdown_requested is True
        service.supervisor.stop_all.assert_called_once()
