#!/usr/bin/env python3
"""
Data Collection Service Runner - Phase 2.5 Live Data Collection.

This script provides a production-grade service runner for all Precog data
collection event loops with comprehensive logging, error handling, metrics,
and health monitoring.

Architecture:
-------------
The runner uses a plugin-based architecture for easy expansion:

1. **Current Event Loops (Phase 2.5):**
   - ESPN Game State Poller (MarketUpdater)
   - Kalshi Market Price Poller (KalshiMarketPoller)
   - Kalshi WebSocket Handler (KalshiWebSocketHandler)

2. **Future Event Loops (Phases 3-5):**
   - Edge Calculator (Phase 3)
   - Strategy Evaluator (Phase 4)
   - Trade Executor (Phase 5)
   - Position Manager (Phase 5)

Logging Strategy:
-----------------
- Rotating file logs with configurable retention
- JSON format for production (ELK/CloudWatch compatible)
- Human-readable format for development
- Structured fields: timestamp, level, service, event, context

Error Handling:
---------------
- Per-service error isolation (one failure doesn't crash others)
- Retry with exponential backoff for transient errors
- Circuit breaker pattern for persistent failures
- Alert thresholds with callback hooks

Health Monitoring:
------------------
- Periodic health check output (configurable interval)
- Metrics: polls_completed, errors, uptime, last_success
- Ready for external monitoring (Prometheus, CloudWatch)

Usage:
------
    # Start all data collectors
    python scripts/run_data_collector.py

    # Start specific services
    python scripts/run_data_collector.py --services espn,kalshi

    # Production mode with JSON logging
    python scripts/run_data_collector.py --env production

    # Custom poll interval
    python scripts/run_data_collector.py --poll-interval 30

Reference: Phase 2.5 - Live Data Collection Service
Related: docs/foundation/DEVELOPMENT_PHASES_V1.8.md
Requirements: REQ-DATA-001, REQ-OBSERV-001

Educational Note:
-----------------
This runner implements the "Supervisor" pattern commonly used in production
services. Each event loop runs independently, and the supervisor:
1. Monitors health of each service
2. Restarts failed services (with backoff)
3. Aggregates metrics across all services
4. Provides unified shutdown handling

This pattern is similar to systemd, supervisord, or Kubernetes pod management,
but at the application level for finer control.
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Protocol, cast

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from precog.schedulers import (
    create_kalshi_poller,
    create_market_updater,
    create_websocket_handler,
)

# =============================================================================
# Configuration
# =============================================================================


class Environment(Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ServiceConfig:
    """Configuration for a single service."""

    name: str
    enabled: bool = True
    poll_interval: int = 15
    max_retries: int = 3
    retry_delay: int = 5
    alert_threshold: int = 5  # Errors before alerting


@dataclass
class RunnerConfig:
    """Global runner configuration."""

    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_dir: Path = Path("logs")
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5
    health_check_interval: int = 60  # seconds
    metrics_interval: int = 300  # 5 minutes
    services: dict[str, ServiceConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize default services."""
        if not self.services:
            self.services = {
                "espn": ServiceConfig(name="ESPN Game Poller", poll_interval=15),
                "kalshi_rest": ServiceConfig(name="Kalshi REST Poller", poll_interval=30),
                "kalshi_ws": ServiceConfig(name="Kalshi WebSocket", enabled=False),
            }


# =============================================================================
# Logging Infrastructure
# =============================================================================


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.

    Produces structured logs compatible with:
    - AWS CloudWatch Logs Insights
    - Elasticsearch/Logstash (ELK Stack)
    - Datadog, Splunk, and other log aggregators

    Educational Note:
    -----------------
    Structured logging with JSON enables:
    1. Easy parsing and filtering in log aggregators
    2. Correlation across distributed services
    3. Custom dashboards and alerts based on fields
    4. Retention of context (user_id, request_id, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": getattr(record, "service", "data_collector"),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key in ["event", "context", "metrics", "error_count", "uptime_seconds"]:
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for development."""

    def __init__(self) -> None:
        """Initialize with readable format."""
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging(config: RunnerConfig) -> logging.Logger:
    """
    Configure logging based on environment.

    Args:
        config: Runner configuration

    Returns:
        Configured root logger

    Educational Note:
    -----------------
    We use a hierarchical logging setup:
    1. Root logger: Captures all logs
    2. Console handler: Always active, level depends on environment
    3. File handler: Rotating files, always INFO+
    4. JSON vs Human format: Based on environment
    """
    # Create log directory
    config.log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    logger = logging.getLogger("precog")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(
        logging.DEBUG if config.environment == Environment.DEVELOPMENT else logging.INFO
    )

    # File handler (rotating)
    file_handler = RotatingFileHandler(
        config.log_dir / "data_collector.log",
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
    )
    file_handler.setLevel(logging.INFO)

    # Choose formatter based on environment
    if config.environment == Environment.PRODUCTION:
        console_handler.setFormatter(JSONFormatter())
        file_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(HumanFormatter())
        file_handler.setFormatter(HumanFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# =============================================================================
# Service Protocol and Base Class
# =============================================================================


class EventLoopService(Protocol):
    """
    Protocol for event loop services.

    All data collection services must implement this interface.
    This enables the supervisor to manage heterogeneous services uniformly.

    Future services (Phase 3-5) should implement:
    - EdgeCalculator(EventLoopService)
    - StrategyEvaluator(EventLoopService)
    - TradeExecutor(EventLoopService)
    - PositionManager(EventLoopService)
    """

    def start(self) -> None:
        """Start the service."""
        ...

    def stop(self) -> None:
        """Stop the service gracefully."""
        ...

    def is_running(self) -> bool:
        """Check if service is running."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        ...


@dataclass
class ServiceState:
    """
    Runtime state for a managed service.

    Tracks health, errors, and restart history for each service.
    Used by the supervisor for monitoring and restart decisions.
    """

    service: EventLoopService | None = None
    config: ServiceConfig | None = None
    started_at: datetime | None = None
    last_health_check: datetime | None = None
    error_count: int = 0
    restart_count: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    healthy: bool = True


# =============================================================================
# Service Supervisor
# =============================================================================


class ServiceSupervisor:
    """
    Supervisor for managing multiple event loop services.

    Responsibilities:
    -----------------
    1. Service lifecycle management (start, stop, restart)
    2. Health monitoring and alerting
    3. Metrics aggregation
    4. Graceful shutdown coordination

    Design Pattern:
    ---------------
    This implements the Supervisor pattern with these sub-patterns:
    - Circuit Breaker: Stop restarting after repeated failures
    - Health Check: Periodic service health validation
    - Observer: Alert callbacks for error thresholds

    Educational Note:
    -----------------
    Production services need more than just "start and run":
    1. What if a service crashes? (Auto-restart with backoff)
    2. What if it hangs? (Health checks with timeouts)
    3. What if it fails repeatedly? (Circuit breaker, alerting)
    4. How do we know it's healthy? (Metrics, logging)

    This supervisor handles all these concerns centrally.
    """

    def __init__(self, config: RunnerConfig) -> None:
        """
        Initialize the supervisor.

        Args:
            config: Runner configuration
        """
        self.config = config
        self.logger = logging.getLogger("precog.supervisor")
        self.services: dict[str, ServiceState] = {}
        self._shutdown_event = threading.Event()
        self._health_thread: threading.Thread | None = None
        self._metrics_thread: threading.Thread | None = None
        self._start_time: datetime | None = None
        self._alert_callbacks: list[Callable[[str, str, dict], None]] = []

    def register_alert_callback(self, callback: Callable[[str, str, dict], None]) -> None:
        """
        Register callback for alert notifications.

        Args:
            callback: Function(service_name, message, context) to call on alerts

        Educational Note:
        -----------------
        Alert callbacks enable integration with:
        - Email notifications
        - Slack/Teams webhooks
        - PagerDuty/OpsGenie
        - Custom monitoring systems

        Deferred to Phase 3+: CloudWatch Alarms, ELK alerting
        """
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, service_name: str, message: str, context: dict[str, Any]) -> None:
        """Trigger all registered alert callbacks."""
        self.logger.warning(
            "ALERT: %s - %s",
            service_name,
            message,
            extra={"service": service_name, "context": context},
        )
        for callback in self._alert_callbacks:
            try:
                callback(service_name, message, context)
            except Exception as e:
                self.logger.error("Alert callback failed: %s", e)

    def add_service(self, name: str, service: EventLoopService, config: ServiceConfig) -> None:
        """
        Add a service to be managed.

        Args:
            name: Service identifier
            service: Service instance implementing EventLoopService
            config: Service configuration
        """
        self.services[name] = ServiceState(service=service, config=config)
        self.logger.info("Registered service: %s", name)

    def start_all(self) -> None:
        """
        Start all registered services.

        Starts each service in order, with error isolation.
        Failed services are marked unhealthy but don't block others.
        """
        self._start_time = datetime.now(UTC)
        self.logger.info(
            "Starting Data Collection Service (env=%s)",
            self.config.environment.value,
            extra={"event": "supervisor_start"},
        )

        for name, state in self.services.items():
            if state.config and not state.config.enabled:
                self.logger.info("Service %s is disabled, skipping", name)
                continue

            try:
                self._start_service(name, state)
            except Exception as e:
                self.logger.error(
                    "Failed to start service %s: %s",
                    name,
                    e,
                    extra={"service": name, "error": str(e)},
                )
                state.healthy = False
                state.last_error = str(e)
                state.consecutive_failures += 1

        # Start health monitoring thread
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

        # Start metrics thread
        self._metrics_thread = threading.Thread(target=self._metrics_loop, daemon=True)
        self._metrics_thread.start()

        self.logger.info(
            "All services started. Health check every %ds, metrics every %ds",
            self.config.health_check_interval,
            self.config.metrics_interval,
        )

    def _start_service(self, name: str, state: ServiceState) -> None:
        """Start a single service."""
        if state.service is None:
            raise ValueError(f"Service {name} has no instance")

        self.logger.info("Starting service: %s", name)
        state.service.start()
        state.started_at = datetime.now(UTC)
        state.healthy = True
        state.consecutive_failures = 0
        self.logger.info(
            "Service started: %s",
            name,
            extra={"service": name, "event": "service_started"},
        )

    def stop_all(self) -> None:
        """
        Stop all services gracefully.

        Signals shutdown, then stops each service with timeout.
        """
        self.logger.info("Shutting down all services...")
        self._shutdown_event.set()

        for name, state in self.services.items():
            try:
                if state.service and state.service.is_running():
                    self.logger.info("Stopping service: %s", name)
                    state.service.stop()
                    self.logger.info("Service stopped: %s", name)
            except Exception as e:
                self.logger.error("Error stopping service %s: %s", name, e)

        # Wait for monitoring threads
        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)
        if self._metrics_thread and self._metrics_thread.is_alive():
            self._metrics_thread.join(timeout=5)

        uptime = (datetime.now(UTC) - self._start_time).total_seconds() if self._start_time else 0
        self.logger.info(
            "Data Collection Service stopped (uptime=%.1fs)",
            uptime,
            extra={"event": "supervisor_stop", "uptime_seconds": uptime},
        )

    def _health_check_loop(self) -> None:
        """
        Periodic health check for all services.

        Checks each service's running state and error counts.
        Triggers alerts when thresholds exceeded.
        Attempts restarts for failed services (with backoff).
        """
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(self.config.health_check_interval)
            if self._shutdown_event.is_set():
                break

            for name, state in self.services.items():
                if state.service is None or (state.config and not state.config.enabled):
                    continue

                try:
                    self._check_service_health(name, state)
                except Exception as e:
                    self.logger.error("Health check failed for %s: %s", name, e)

    def _check_service_health(self, name: str, state: ServiceState) -> None:
        """Check health of a single service."""
        state.last_health_check = datetime.now(UTC)

        if state.service is None:
            return

        # Check if running
        if not state.service.is_running():
            state.healthy = False
            state.consecutive_failures += 1
            self.logger.warning(
                "Service %s is not running (failures=%d)",
                name,
                state.consecutive_failures,
            )

            # Attempt restart if under retry limit
            if state.config and state.consecutive_failures <= state.config.max_retries:
                self._attempt_restart(name, state)
            elif state.config:
                self._trigger_alert(
                    name,
                    f"Service failed {state.consecutive_failures} times, giving up",
                    {"restart_count": state.restart_count},
                )
            return

        # Check error counts
        stats = state.service.get_stats()
        current_errors = stats.get("errors", 0)

        if state.config and current_errors > state.error_count:
            new_errors = current_errors - state.error_count
            state.error_count = current_errors

            if new_errors >= state.config.alert_threshold:
                self._trigger_alert(
                    name,
                    f"{new_errors} errors in last health check interval",
                    {"total_errors": current_errors, "stats": stats},
                )

        state.healthy = True

    def _attempt_restart(self, name: str, state: ServiceState) -> None:
        """Attempt to restart a failed service."""
        if state.service is None or state.config is None:
            return

        delay = state.config.retry_delay * (2 ** (state.consecutive_failures - 1))
        self.logger.info(
            "Attempting restart of %s in %ds (attempt %d/%d)",
            name,
            delay,
            state.consecutive_failures,
            state.config.max_retries,
        )

        time.sleep(delay)

        try:
            state.service.start()
            state.restart_count += 1
            state.started_at = datetime.now(UTC)
            state.healthy = True
            state.consecutive_failures = 0
            self.logger.info("Service %s restarted successfully", name)
        except Exception as e:
            self.logger.error("Restart failed for %s: %s", name, e)
            state.last_error = str(e)

    def _metrics_loop(self) -> None:
        """
        Periodic metrics aggregation and output.

        Collects stats from all services and logs aggregate metrics.
        Ready for export to Prometheus, CloudWatch, etc.
        """
        while not self._shutdown_event.is_set():
            self._shutdown_event.wait(self.config.metrics_interval)
            if self._shutdown_event.is_set():
                break

            self._output_metrics()

    def _output_metrics(self) -> None:
        """Collect and output aggregate metrics."""
        uptime = (datetime.now(UTC) - self._start_time).total_seconds() if self._start_time else 0

        aggregate: dict[str, Any] = {
            "uptime_seconds": uptime,
            "services_total": len(self.services),
            "services_healthy": sum(1 for s in self.services.values() if s.healthy),
            "total_restarts": sum(s.restart_count for s in self.services.values()),
            "total_errors": sum(s.error_count for s in self.services.values()),
            "per_service": {},
        }

        for name, state in self.services.items():
            if state.service:
                aggregate["per_service"][name] = {
                    "healthy": state.healthy,
                    "restart_count": state.restart_count,
                    "error_count": state.error_count,
                    "stats": state.service.get_stats() if state.service.is_running() else {},
                }

        self.logger.info(
            "Metrics: healthy=%d/%d, errors=%d, restarts=%d, uptime=%.0fs",
            aggregate["services_healthy"],
            aggregate["services_total"],
            aggregate["total_errors"],
            aggregate["total_restarts"],
            uptime,
            extra={"event": "metrics", "metrics": aggregate, "uptime_seconds": uptime},
        )

    def wait_for_shutdown(self) -> None:
        """Block until shutdown signal received."""
        self._shutdown_event.wait()


# =============================================================================
# Service Factory
# =============================================================================


def create_services(
    config: RunnerConfig, enabled_services: set[str] | None = None
) -> dict[str, tuple[EventLoopService, ServiceConfig]]:
    """
    Create service instances based on configuration.

    Args:
        config: Runner configuration
        enabled_services: Set of service names to enable (None = all)

    Returns:
        Dict mapping service name to (service, config) tuple

    Educational Note:
    -----------------
    This factory pattern centralizes service creation, making it easy to:
    1. Add new services (just add a case)
    2. Configure services differently per environment
    3. Mock services for testing
    """
    services: dict[str, tuple[EventLoopService, ServiceConfig]] = {}
    logger = logging.getLogger("precog.factory")

    for name, svc_config in config.services.items():
        if enabled_services and name not in enabled_services:
            svc_config.enabled = False
            continue

        try:
            if name == "espn":
                espn_service = create_market_updater(
                    leagues=["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"],
                    poll_interval=svc_config.poll_interval,
                )
                services[name] = (cast("EventLoopService", espn_service), svc_config)
                logger.info("Created ESPN Game Poller (interval=%ds)", svc_config.poll_interval)

            elif name == "kalshi_rest":
                # Check for Kalshi credentials
                if os.getenv("KALSHI_API_KEY_ID"):
                    kalshi_rest_service = create_kalshi_poller(
                        series_tickers=["KXNFLGAME"],
                        poll_interval=svc_config.poll_interval,
                    )
                    services[name] = (cast("EventLoopService", kalshi_rest_service), svc_config)
                    logger.info(
                        "Created Kalshi REST Poller (interval=%ds)", svc_config.poll_interval
                    )
                else:
                    logger.warning("Kalshi API credentials not found, skipping REST poller")
                    svc_config.enabled = False

            elif name == "kalshi_ws":
                # WebSocket for real-time updates
                if os.getenv("KALSHI_API_KEY_ID"):
                    kalshi_ws_service = create_websocket_handler(
                        environment="demo"
                        if config.environment != Environment.PRODUCTION
                        else "prod"
                    )
                    services[name] = (cast("EventLoopService", kalshi_ws_service), svc_config)
                    logger.info("Created Kalshi WebSocket Handler")
                else:
                    logger.warning("Kalshi API credentials not found, skipping WebSocket")
                    svc_config.enabled = False

            # Future services (Phase 3-5) - placeholder
            elif name == "edge_calculator":
                logger.info("Edge Calculator service (Phase 3) - not yet implemented")
                svc_config.enabled = False

            elif name == "strategy_evaluator":
                logger.info("Strategy Evaluator service (Phase 4) - not yet implemented")
                svc_config.enabled = False

            elif name == "trade_executor":
                logger.info("Trade Executor service (Phase 5) - not yet implemented")
                svc_config.enabled = False

            elif name == "position_manager":
                logger.info("Position Manager service (Phase 5) - not yet implemented")
                svc_config.enabled = False

        except Exception as e:
            logger.error("Failed to create service %s: %s", name, e)
            svc_config.enabled = False

    return services


# =============================================================================
# Signal Handling
# =============================================================================


def setup_signal_handlers(supervisor: ServiceSupervisor) -> None:
    """
    Configure signal handlers for graceful shutdown.

    Handles:
    - SIGINT (Ctrl+C): Graceful shutdown
    - SIGTERM: Graceful shutdown (used by systemd, Docker, k8s)

    Educational Note:
    -----------------
    Proper signal handling is critical for production services:
    1. Allows in-progress operations to complete
    2. Ensures database connections are closed properly
    3. Prevents data corruption from abrupt termination
    4. Enables zero-downtime deployments
    """

    def signal_handler(signum: int, frame: Any) -> None:
        signame = signal.Signals(signum).name
        logging.getLogger("precog.signals").info("Received %s, initiating shutdown...", signame)
        supervisor.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


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
  # Start all data collectors in development mode
  python scripts/run_data_collector.py

  # Start only ESPN poller
  python scripts/run_data_collector.py --services espn

  # Production mode with JSON logging
  python scripts/run_data_collector.py --env production

  # Custom poll interval
  python scripts/run_data_collector.py --poll-interval 30
        """,
    )

    parser.add_argument(
        "--env",
        choices=["development", "staging", "production"],
        default="development",
        help="Deployment environment (default: development)",
    )

    parser.add_argument(
        "--services",
        type=str,
        default=None,
        help="Comma-separated list of services to run (default: all)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=15,
        help="Poll interval in seconds (default: 15)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("logs"),
        help="Directory for log files (default: logs/)",
    )

    parser.add_argument(
        "--health-interval",
        type=int,
        default=60,
        help="Health check interval in seconds (default: 60)",
    )

    parser.add_argument(
        "--metrics-interval",
        type=int,
        default=300,
        help="Metrics output interval in seconds (default: 300)",
    )

    return parser.parse_args()


def main() -> None:
    """
    Main entry point for the data collection service.

    Orchestrates:
    1. Configuration loading
    2. Logging setup
    3. Service creation
    4. Supervisor initialization
    5. Signal handler registration
    6. Service startup
    7. Wait for shutdown
    """
    args = parse_args()

    # Build configuration
    config = RunnerConfig(
        environment=Environment(args.env),
        log_level=args.log_level,
        log_dir=args.log_dir,
        health_check_interval=args.health_interval,
        metrics_interval=args.metrics_interval,
    )

    # Update poll intervals
    for svc_config in config.services.values():
        svc_config.poll_interval = args.poll_interval

    # Setup logging
    logger = setup_logging(config)
    logger.info(
        "Precog Data Collection Service starting...",
        extra={"event": "startup", "environment": args.env},
    )

    # Parse enabled services
    enabled_services = None
    if args.services:
        enabled_services = set(args.services.split(","))
        logger.info("Enabled services: %s", enabled_services)

    # Create services
    services = create_services(config, enabled_services)

    if not services:
        logger.error("No services created, exiting")
        sys.exit(1)

    # Create supervisor
    supervisor = ServiceSupervisor(config)

    # Register services
    for name, (service, svc_config) in services.items():
        supervisor.add_service(name, service, svc_config)

    # Setup signal handlers
    setup_signal_handlers(supervisor)

    # Start all services
    supervisor.start_all()

    # Wait for shutdown
    logger.info(
        "Data Collection Service running. Press Ctrl+C to stop.",
        extra={"event": "running"},
    )

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        supervisor.stop_all()


if __name__ == "__main__":
    main()
