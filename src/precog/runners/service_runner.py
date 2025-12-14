"""
Data Collection Service Runner.

Production-grade service management for data collection services (ESPN game polling,
Kalshi market polling). Wraps ServiceSupervisor with proper signal handling, PID
management, logging, and startup validation.

Why This Module Exists:
    While ServiceSupervisor handles the core service management logic, production
    deployments need additional features:
    1. PID file management for process supervision
    2. Graceful shutdown on system signals (SIGTERM, SIGINT)
    3. Startup validation before entering main loop
    4. Status reporting for monitoring systems
    5. Cross-platform support (Windows/Linux)

Usage:
    # From CLI (recommended):
    python main.py run-services
    python main.py run-services --stop
    python main.py run-services --status

    # Programmatic:
    from precog.runners import DataCollectorService
    service = DataCollectorService(espn_enabled=True, kalshi_enabled=True)
    exit_code = service.start()

Exit Codes:
    0: Clean shutdown
    1: Startup error
    2: Runtime error
    3: Already running

Reference:
    - Issue #193: Phase 2.5 Live Data Collection Service
    - docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
    - ADR-100: Service Supervisor Pattern

Requirements: REQ-DATA-001, REQ-OBSERV-001
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from precog.config.environment import load_environment_config
from precog.schedulers.espn_game_poller import create_espn_poller
from precog.schedulers.kalshi_poller import create_kalshi_poller
from precog.schedulers.service_supervisor import (
    Environment,
    RunnerConfig,
    ServiceConfig,
    ServiceSupervisor,
)

# =============================================================================
# Constants
# =============================================================================

DEFAULT_PID_FILE = Path("/var/run/precog/data_collector.pid")
DEFAULT_LOG_DIR = Path("/var/log/precog")
WINDOWS_PID_FILE = Path.home() / ".precog" / "data_collector.pid"
WINDOWS_LOG_DIR = Path.home() / ".precog" / "logs"

# Service configuration defaults
DEFAULT_ESPN_INTERVAL = 15  # seconds
DEFAULT_KALSHI_INTERVAL = 30  # seconds
DEFAULT_HEALTH_CHECK_INTERVAL = 60  # seconds
DEFAULT_METRICS_INTERVAL = 300  # 5 minutes

DEFAULT_LEAGUES = ["nfl", "nba", "nhl", "ncaaf", "ncaab"]


# =============================================================================
# Platform Helper Functions
# =============================================================================


def get_pid_file() -> Path:
    """
    Get platform-appropriate PID file path.

    Returns:
        Path to PID file location

    Educational Note:
        PID files store the process ID of a running daemon, allowing:
        1. Detection of already-running instances
        2. Targeted signal delivery for graceful shutdown
        3. Process monitoring by external tools (systemd, monit)

    Platform Behavior:
        - Windows: ~/.precog/data_collector.pid
        - Linux: /var/run/precog/data_collector.pid (if writable)
                 ~/.precog/data_collector.pid (fallback)
    """
    if sys.platform == "win32":
        pid_dir = WINDOWS_PID_FILE.parent
        pid_dir.mkdir(parents=True, exist_ok=True)
        return WINDOWS_PID_FILE
    else:  # noqa: RET505 - intentional for platform branching clarity
        # Linux/macOS: Use /var/run if available and writable
        if DEFAULT_PID_FILE.parent.exists():
            try:
                test_file = DEFAULT_PID_FILE.parent / ".test_write"
                test_file.touch()
                test_file.unlink()
                return DEFAULT_PID_FILE
            except PermissionError:
                pass

        # Fall back to user directory
        fallback = Path.home() / ".precog" / "data_collector.pid"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def get_log_dir() -> Path:
    """
    Get platform-appropriate log directory.

    Returns:
        Path to log directory

    Platform Behavior:
        - Windows: ~/.precog/logs/
        - Linux: /var/log/precog/ (if writable)
                 ~/.precog/logs/ (fallback)
    """
    if sys.platform == "win32":
        WINDOWS_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return WINDOWS_LOG_DIR
    else:  # noqa: RET505 - intentional for platform branching clarity
        if DEFAULT_LOG_DIR.exists():
            try:
                test_file = DEFAULT_LOG_DIR / ".test_write"
                test_file.touch()
                test_file.unlink()
                return DEFAULT_LOG_DIR
            except PermissionError:
                pass

        fallback = Path.home() / ".precog" / "logs"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def write_pid_file(pid_file: Path) -> None:
    """Write current PID to file."""
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))


def read_pid_file(pid_file: Path) -> int | None:
    """
    Read PID from file.

    Args:
        pid_file: Path to PID file

    Returns:
        PID as integer, or None if not found/invalid
    """
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def remove_pid_file(pid_file: Path) -> None:
    """Remove PID file if it exists."""
    try:
        pid_file.unlink(missing_ok=True)
    except OSError:
        pass


def is_process_running(pid: int) -> bool:
    """
    Check if a process with given PID is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise

    Educational Note:
        Uses platform-specific APIs:
        - Windows: OpenProcess with SYNCHRONIZE access
        - Unix: kill(pid, 0) - signal 0 tests if process exists
    """
    # PIDs must be positive (negative PIDs are invalid or have special meaning)
    # - PID 0: kernel scheduler on Linux, invalid on Windows
    # - PID -1: special "all processes" on Unix, invalid on Windows
    # - PID < -1: process group IDs on Unix, invalid on Windows
    if pid <= 0:
        return False

    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        synchronize = 0x00100000
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:  # noqa: RET505 - intentional for platform branching clarity
        # Unix: kill with signal 0 tests process existence
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def setup_logging(log_dir: Path, debug: bool = False) -> logging.Logger:
    """
    Set up logging for the data collector service.

    Args:
        log_dir: Directory for log files
        debug: Enable debug logging

    Returns:
        Configured logger instance

    Educational Note:
        Production logging differs from development:
        1. File-based with rotation for persistence
        2. Both file and console handlers for flexibility
        3. Structured format for log aggregation tools
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_file = log_dir / f"data_collector_{datetime.now():%Y-%m-%d}.log"

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Get precog logger
    logger = logging.getLogger("precog.data_collector")
    logger.info("Logging initialized: %s", log_file)

    return logger


# =============================================================================
# Data Collector Service
# =============================================================================


class DataCollectorService:
    """
    Production-grade data collection service manager.

    Wraps the ServiceSupervisor with additional production features:
    - PID file management for process supervision
    - Signal handling for graceful shutdown
    - Startup validation (database, credentials, modules)
    - Status reporting

    Educational Note:
        This class follows the "wrapper" pattern - it adds production
        concerns around the core ServiceSupervisor without modifying it.
        This separation keeps the core simple and testable while allowing
        deployment-specific features.

    Example:
        >>> service = DataCollectorService()
        >>> exit_code = service.start()  # Blocks until shutdown signal

        >>> # Or check status
        >>> service.status()

        >>> # Or stop running instance
        >>> service.stop()

    Attributes:
        espn_enabled: Whether ESPN polling is enabled
        kalshi_enabled: Whether Kalshi polling is enabled
        espn_interval: ESPN poll interval in seconds
        kalshi_interval: Kalshi poll interval in seconds
        leagues: List of leagues to poll
        debug: Whether debug logging is enabled

    Reference: Issue #193, REQ-DATA-001
    """

    def __init__(
        self,
        *,
        espn_enabled: bool = True,
        kalshi_enabled: bool = True,
        espn_interval: int = DEFAULT_ESPN_INTERVAL,
        kalshi_interval: int = DEFAULT_KALSHI_INTERVAL,
        health_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
        metrics_interval: int = DEFAULT_METRICS_INTERVAL,
        leagues: list[str] | None = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize the data collector service.

        Args:
            espn_enabled: Enable ESPN game polling
            kalshi_enabled: Enable Kalshi market polling
            espn_interval: ESPN poll interval in seconds
            kalshi_interval: Kalshi poll interval in seconds
            health_interval: Health check interval in seconds
            metrics_interval: Metrics reporting interval in seconds
            leagues: List of leagues to poll (default: all configured)
            debug: Enable debug logging
        """
        self.espn_enabled = espn_enabled
        self.kalshi_enabled = kalshi_enabled
        self.espn_interval = espn_interval
        self.kalshi_interval = kalshi_interval
        self.health_interval = health_interval
        self.metrics_interval = metrics_interval
        self.leagues = leagues or DEFAULT_LEAGUES.copy()
        self.debug = debug

        self.pid_file = get_pid_file()
        self.log_dir = get_log_dir()
        self.logger: logging.Logger | None = None
        self.supervisor: ServiceSupervisor | None = None
        self._shutdown_requested: bool = False

    def _setup_signal_handlers(self) -> None:
        """
        Register signal handlers for graceful shutdown.

        Educational Note:
            Signal handlers allow external processes (init system, user)
            to request graceful shutdown. We handle:
            - SIGTERM: Termination request (systemd default)
            - SIGINT: Keyboard interrupt (Ctrl+C)
            - SIGHUP: Terminal hangup (optional, Unix only)
        """
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._signal_handler)

    def _signal_handler(self, signum: int, _frame: Any) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        if self.logger:
            self.logger.info("Received %s, initiating graceful shutdown...", sig_name)
        self._shutdown_requested = True
        if self.supervisor:
            self.supervisor.stop_all()

    def _validate_startup(self) -> bool:
        """
        Validate system is ready for data collection.

        Returns:
            True if all validations pass, False otherwise

        Checks:
            1. Environment configuration loadable
            2. Database connection available
            3. Required modules installed
            4. API credentials valid (for live mode)

        Educational Note:
            Fail-fast validation prevents the service from starting
            in a broken state. Better to fail immediately with a clear
            error than to start and fail mid-operation.
        """
        if self.logger:
            self.logger.info("Running startup validation...")

        # Load environment config
        try:
            env_config = load_environment_config()
            if self.logger:
                self.logger.info(
                    "Environment: %s, Database: %s",
                    env_config.app_env.value,
                    env_config.database_name,
                )
        except Exception as e:
            if self.logger:
                self.logger.error("Failed to load environment config: %s", e)
            return False

        # Test database connection
        try:
            from precog.database.connection import test_connection

            if not test_connection():
                if self.logger:
                    self.logger.error("Database connection test failed")
                return False
            if self.logger:
                self.logger.info("Database connection: OK")
        except Exception as e:
            if self.logger:
                self.logger.error("Database connection failed: %s", e)
            return False

        # Validate ESPN module if enabled
        if self.espn_enabled:
            import importlib.util

            spec = importlib.util.find_spec("precog.api_connectors.espn_client")
            if spec is None:
                if self.logger:
                    self.logger.error("ESPN client module not found")
                return False
            if self.logger:
                self.logger.info("ESPN client: OK")

        # Validate Kalshi credentials if enabled in live mode
        if self.kalshi_enabled:
            kalshi_mode = os.getenv("KALSHI_MODE", "demo")
            if self.logger:
                self.logger.info("Kalshi mode: %s", kalshi_mode)

            if kalshi_mode == "live":
                key_id = os.getenv("KALSHI_KEY_ID")
                key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
                if not key_id or not key_path:
                    if self.logger:
                        self.logger.error(
                            "Kalshi live mode requires KALSHI_KEY_ID and KALSHI_PRIVATE_KEY_PATH"
                        )
                    return False
                if not Path(key_path).exists():
                    if self.logger:
                        self.logger.error("Kalshi private key not found: %s", key_path)
                    return False

        if self.logger:
            self.logger.info("Startup validation: PASSED")
        return True

    def _create_supervisor(self) -> ServiceSupervisor:
        """
        Create and configure the service supervisor.

        Returns:
            Configured ServiceSupervisor instance

        Educational Note:
            This method creates the ServiceSupervisor and configures
            it with the appropriate services based on user settings.
            The supervisor handles the actual service lifecycle.
        """
        # Determine environment
        env_str = os.getenv("PRECOG_ENV", "dev")
        env_map = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "staging": Environment.STAGING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION,
        }
        environment = env_map.get(env_str, Environment.DEVELOPMENT)

        # Create runner config
        runner_config = RunnerConfig(
            environment=environment,
            health_check_interval=self.health_interval,
            metrics_interval=self.metrics_interval,
        )

        supervisor = ServiceSupervisor(runner_config)

        # Add ESPN poller if enabled
        if self.espn_enabled:
            espn_poller = create_espn_poller(
                leagues=self.leagues,
                poll_interval=self.espn_interval,
            )
            espn_config = ServiceConfig(
                name="espn_game_poller",
                enabled=True,
                poll_interval=self.espn_interval,
                max_retries=5,
                retry_delay=10,
                alert_threshold=3,
            )
            supervisor.add_service("espn", espn_poller, espn_config)

        # Add Kalshi poller if enabled
        if self.kalshi_enabled:
            kalshi_poller = create_kalshi_poller(
                poll_interval=self.kalshi_interval,
            )
            kalshi_config = ServiceConfig(
                name="kalshi_market_poller",
                enabled=True,
                poll_interval=self.kalshi_interval,
                max_retries=3,
                retry_delay=15,
                alert_threshold=5,
            )
            supervisor.add_service("kalshi", kalshi_poller, kalshi_config)

        return supervisor

    def start(self) -> int:
        """
        Start the data collection service.

        Returns:
            Exit code:
            - 0: Clean shutdown
            - 1: Startup error
            - 3: Already running

        This method blocks until shutdown is requested via signal.

        Educational Note:
            The main loop is simple: sleep and check for shutdown flag.
            Actual work is done by ServiceSupervisor in background threads.
            This allows the main thread to respond quickly to signals.
        """
        # Setup logging
        self.logger = setup_logging(self.log_dir, self.debug)
        self.logger.info("=" * 60)
        self.logger.info("Precog Data Collection Service Starting")
        self.logger.info("=" * 60)

        # Check if already running
        existing_pid = read_pid_file(self.pid_file)
        if existing_pid and is_process_running(existing_pid):
            self.logger.error(
                "Service already running (PID %d). Use --stop to stop it.",
                existing_pid,
            )
            return 3

        # Write PID file
        write_pid_file(self.pid_file)
        atexit.register(remove_pid_file, self.pid_file)

        # Setup signal handlers
        self._setup_signal_handlers()

        # Validate startup
        if not self._validate_startup():
            self.logger.error("Startup validation failed. Exiting.")
            return 1

        # Create and start supervisor
        try:
            self.supervisor = self._create_supervisor()
            self.supervisor.start_all()
        except Exception as e:
            self.logger.error("Failed to start services: %s", e)
            return 1

        self.logger.info("Data collection started. Press Ctrl+C to stop.")
        self.logger.info(
            "ESPN: %s (every %ds), Kalshi: %s (every %ds)",
            "enabled" if self.espn_enabled else "disabled",
            self.espn_interval,
            "enabled" if self.kalshi_enabled else "disabled",
            self.kalshi_interval,
        )
        self.logger.info("Leagues: %s", ", ".join(self.leagues))

        # Main loop - wait for shutdown
        try:
            while not self._shutdown_requested:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

        # Shutdown
        self.logger.info("Shutting down services...")
        if self.supervisor:
            self.supervisor.stop_all()

        self.logger.info("Data collection service stopped.")
        return 0

    def stop(self) -> int:
        """
        Stop a running data collector service.

        Returns:
            Exit code:
            - 0: Successfully stopped
            - 1: Error stopping service

        Educational Note:
            This method finds the running process via PID file and sends
            SIGTERM for graceful shutdown. If the process doesn't stop
            within 30 seconds, SIGKILL is sent (Unix only).
        """
        pid = read_pid_file(self.pid_file)
        if not pid:
            print("No PID file found. Service may not be running.")
            return 1

        if not is_process_running(pid):
            print(f"Process {pid} is not running. Removing stale PID file.")
            remove_pid_file(self.pid_file)
            return 0

        print(f"Sending SIGTERM to process {pid}...")
        try:
            if sys.platform == "win32":
                import ctypes

                kernel32 = ctypes.windll.kernel32
                process_terminate = 0x0001
                handle = kernel32.OpenProcess(process_terminate, False, pid)
                if handle:
                    kernel32.TerminateProcess(handle, 0)
                    kernel32.CloseHandle(handle)
            else:
                os.kill(pid, signal.SIGTERM)

            # Wait for process to stop (30 second timeout)
            for _ in range(30):
                time.sleep(1)
                if not is_process_running(pid):
                    print("Service stopped successfully.")
                    remove_pid_file(self.pid_file)
                    return 0

            print(f"Process {pid} did not stop gracefully. Force killing...")
            if sys.platform != "win32":
                os.kill(pid, signal.SIGKILL)
            remove_pid_file(self.pid_file)
            return 0

        except Exception as e:
            print(f"Failed to stop service: {e}")
            return 1

    def status(self) -> int:
        """
        Check status of data collector service.

        Returns:
            Exit code:
            - 0: Service is running
            - 1: Service is not running
        """
        pid = read_pid_file(self.pid_file)
        if not pid:
            print("Status: NOT RUNNING (no PID file)")
            return 1

        if is_process_running(pid):
            print(f"Status: RUNNING (PID {pid})")
            print(f"PID file: {self.pid_file}")
            return 0

        print(f"Status: NOT RUNNING (stale PID {pid})")
        return 1
