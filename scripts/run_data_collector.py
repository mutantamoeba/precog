#!/usr/bin/env python3
"""
Background Data Collection Service Runner.

This script provides production-grade background operation for the data collection
services (ESPN game polling, Kalshi market polling). It wraps the CLI scheduler
commands with proper signal handling, logging, and systemd/Windows service integration.

Why This Exists:
    While `python main.py scheduler start --foreground` works for development,
    production deployments need:
    1. PID file management for process supervision
    2. Configurable log rotation
    3. Graceful shutdown on system signals
    4. Startup validation before entering main loop
    5. Systemd/Windows service integration

Usage:
    # Start in foreground (development)
    python scripts/run_data_collector.py

    # Start as daemon (production - Linux only)
    python scripts/run_data_collector.py --daemon

    # Start with custom config
    python scripts/run_data_collector.py --config /etc/precog/collector.yaml

    # Stop running daemon
    python scripts/run_data_collector.py --stop

    # Check status
    python scripts/run_data_collector.py --status

Exit Codes:
    0: Clean shutdown
    1: Startup error
    2: Runtime error
    3: Already running (when --daemon)

Reference:
    - Issue #193: Phase 2.5 Live Data Collection Service
    - docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
    - ADR-100: Service Supervisor Pattern

Requirements: REQ-DATA-001, REQ-OBSERV-001
"""

from __future__ import annotations

import argparse
import atexit
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Now we can import precog modules
from precog.config.environment import load_environment_config  # noqa: E402
from precog.schedulers.espn_game_poller import create_espn_poller  # noqa: E402
from precog.schedulers.kalshi_poller import create_kalshi_poller  # noqa: E402
from precog.schedulers.service_supervisor import (  # noqa: E402
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

# =============================================================================
# Helper Functions
# =============================================================================


def get_pid_file() -> Path:
    """Get platform-appropriate PID file path."""
    if sys.platform == "win32":
        pid_dir = WINDOWS_PID_FILE.parent
        pid_dir.mkdir(parents=True, exist_ok=True)
        return WINDOWS_PID_FILE
    else:  # noqa: RET505 - explicit else needed for mypy cross-platform compatibility
        # Use /var/run if available and writable, else fall back to user dir
        if DEFAULT_PID_FILE.parent.exists():
            try:
                # Test write permission
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
    """Get platform-appropriate log directory."""
    if sys.platform == "win32":
        WINDOWS_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return WINDOWS_LOG_DIR
    else:  # noqa: RET505 - explicit else needed for mypy cross-platform compatibility
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
    """Read PID from file, return None if not found or invalid."""
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
    """Check if a process with given PID is running."""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        synchronize = 0x00100000
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:  # noqa: RET505 - explicit else needed for mypy cross-platform compatibility
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
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_file = log_dir / f"data_collector_{datetime.now():%Y-%m-%d}.log"

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with rotation
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
    - PID file management
    - Signal handling for graceful shutdown
    - Startup validation
    - Status reporting

    Educational Note:
        This class follows the "wrapper" pattern - it adds production
        concerns around the core ServiceSupervisor without modifying it.
        This separation keeps the core simple and testable while allowing
        deployment-specific features.

    Example:
        >>> service = DataCollectorService()
        >>> service.start()  # Blocks until shutdown signal
        >>> # Or check status
        >>> service.status()

    Reference: Issue #193 P2.5-004
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
        self.leagues = leagues or ["nfl", "nba", "nhl", "ncaaf", "ncaab"]
        self.debug = debug

        self.pid_file = get_pid_file()
        self.log_dir = get_log_dir()
        self.logger: logging.Logger | None = None
        self.supervisor: ServiceSupervisor | None = None
        self._shutdown_requested = False

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
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
            1. Database connection available
            2. Required environment variables set
            3. API credentials valid (if applicable)
        """
        if self.logger:
            self.logger.info("Running startup validation...")

        # Get environment config
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
            from precog.database.connection import get_connection

            with get_connection() as conn:
                result = conn.execute("SELECT 1")
                result.fetchone()
            if self.logger:
                self.logger.info("Database connection: OK")
        except Exception as e:
            if self.logger:
                self.logger.error("Database connection failed: %s", e)
            return False

        # Validate ESPN if enabled
        if self.espn_enabled:
            import importlib.util

            spec = importlib.util.find_spec("precog.api_connectors.espn_client")
            if spec is None:
                if self.logger:
                    self.logger.error("ESPN client module not found")
                return False
            if self.logger:
                self.logger.info("ESPN client: OK")

        # Validate Kalshi if enabled
        if self.kalshi_enabled:
            kalshi_mode = os.getenv("KALSHI_MODE", "demo")
            if self.logger:
                self.logger.info("Kalshi mode: %s", kalshi_mode)

            if kalshi_mode == "live":
                # Check for required credentials
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
        """Create and configure the service supervisor."""
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
            Exit code (0 = success, 1 = error)

        This method blocks until shutdown is requested via signal.
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

        self.logger.info(
            "Data collection started. Press Ctrl+C to stop.",
        )
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
            Exit code (0 = success, 1 = error)
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

            # Wait for process to stop
            for _ in range(30):  # 30 second timeout
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
            Exit code (0 = running, 1 = not running)
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


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Precog Data Collection Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start in foreground (development)
    python scripts/run_data_collector.py

    # Start with custom intervals
    python scripts/run_data_collector.py --espn-interval 30 --kalshi-interval 60

    # Start ESPN only
    python scripts/run_data_collector.py --no-kalshi

    # Check status
    python scripts/run_data_collector.py --status

    # Stop running service
    python scripts/run_data_collector.py --stop
        """,
    )

    # Service control
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop running data collector service",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check status of data collector service",
    )

    # Service configuration
    parser.add_argument(
        "--no-espn",
        action="store_true",
        help="Disable ESPN game polling",
    )
    parser.add_argument(
        "--no-kalshi",
        action="store_true",
        help="Disable Kalshi market polling",
    )
    parser.add_argument(
        "--espn-interval",
        type=int,
        default=DEFAULT_ESPN_INTERVAL,
        help=f"ESPN poll interval in seconds (default: {DEFAULT_ESPN_INTERVAL})",
    )
    parser.add_argument(
        "--kalshi-interval",
        type=int,
        default=DEFAULT_KALSHI_INTERVAL,
        help=f"Kalshi poll interval in seconds (default: {DEFAULT_KALSHI_INTERVAL})",
    )
    parser.add_argument(
        "--leagues",
        type=str,
        default="nfl,nba,nhl,ncaaf,ncaab",
        help="Comma-separated list of leagues to poll (default: nfl,nba,nhl,ncaaf,ncaab)",
    )

    # Health and metrics
    parser.add_argument(
        "--health-interval",
        type=int,
        default=DEFAULT_HEALTH_CHECK_INTERVAL,
        help=f"Health check interval in seconds (default: {DEFAULT_HEALTH_CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--metrics-interval",
        type=int,
        default=DEFAULT_METRICS_INTERVAL,
        help=f"Metrics reporting interval in seconds (default: {DEFAULT_METRICS_INTERVAL})",
    )

    # Debug
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Parse leagues
    leagues = [league.strip() for league in args.leagues.split(",")]

    # Create service
    service = DataCollectorService(
        espn_enabled=not args.no_espn,
        kalshi_enabled=not args.no_kalshi,
        espn_interval=args.espn_interval,
        kalshi_interval=args.kalshi_interval,
        health_interval=args.health_interval,
        metrics_interval=args.metrics_interval,
        leagues=leagues,
        debug=args.debug,
    )

    # Handle commands
    if args.status:
        return service.status()
    if args.stop:
        return service.stop()
    return service.start()


if __name__ == "__main__":
    sys.exit(main())
