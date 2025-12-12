"""
Service Supervisor for Multi-Service Orchestration.

This module provides production-grade service management infrastructure
for coordinating multiple data collection event loops with health monitoring,
automatic restart, and metrics aggregation.

Components:
    ServiceSupervisor: Central manager for all services
    ServiceState: Runtime state tracking for managed services
    ServiceConfig: Configuration for individual services
    RunnerConfig: Global supervisor configuration
    EventLoopService: Protocol for services that can be managed
    Environment: Deployment environment enum

Design Patterns:
    - Supervisor Pattern: Central management of service lifecycle
    - Circuit Breaker: Stop restarting after repeated failures
    - Health Check: Periodic service health validation
    - Observer: Alert callbacks for error thresholds

Educational Note:
    Production services need more than just "start and run":
    1. What if a service crashes? (Auto-restart with backoff)
    2. What if it hangs? (Health checks with timeouts)
    3. What if it fails repeatedly? (Circuit breaker, alerting)
    4. How do we know it's healthy? (Metrics, logging)

    This supervisor handles all these concerns centrally.

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern)
Requirements: REQ-DATA-001, REQ-OBSERV-001
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast

from precog.schedulers.espn_game_poller import create_espn_poller
from precog.schedulers.kalshi_poller import create_kalshi_poller
from precog.schedulers.kalshi_websocket import create_websocket_handler

# Set up logging early for helper functions
logger = logging.getLogger(__name__)


def _has_kalshi_credentials(environment: "Environment") -> bool:
    """
    Check if Kalshi API credentials are configured.

    Uses the two-axis environment model credential naming convention:
    - Production environment: PROD_KALSHI_API_KEY
    - Other environments: {PRECOG_ENV}_KALSHI_API_KEY (defaults to DEV)

    This matches the pattern used in kalshi_client.py and kalshi_websocket.py.

    Args:
        environment: The deployment environment (affects credential prefix for prod)

    Returns:
        True if both API key and private key path are configured

    Reference: docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
    """
    # Determine credential prefix based on environment
    if environment == Environment.PRODUCTION:
        cred_prefix = "PROD"
    else:
        # Non-production: use PRECOG_ENV, default to DEV
        precog_env = os.getenv("PRECOG_ENV", "dev").upper()
        valid_prefixes = {"DEV", "TEST", "STAGING"}
        cred_prefix = precog_env if precog_env in valid_prefixes else "DEV"

    api_key = os.getenv(f"{cred_prefix}_KALSHI_API_KEY")
    key_path = os.getenv(f"{cred_prefix}_KALSHI_PRIVATE_KEY_PATH")

    has_creds = bool(api_key and key_path)

    if not has_creds:
        logger.debug(
            "Kalshi credentials not found: %s_KALSHI_API_KEY=%s, %s_KALSHI_PRIVATE_KEY_PATH=%s",
            cred_prefix,
            "set" if api_key else "not set",
            cred_prefix,
            "set" if key_path else "not set",
        )

    return has_creds


# =============================================================================
# Configuration Enums and Dataclasses
# =============================================================================


class Environment(Enum):
    """
    Deployment environment for the supervisor.

    Determines logging format, default poll intervals, and behavior.

    Educational Note:
        Environment-aware configuration enables:
        - Development: Verbose logging, shorter intervals for testing
        - Staging: Production-like but with extra debugging
        - Production: JSON logging for aggregators, optimized intervals
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ServiceConfig:
    """
    Configuration for a single managed service.

    Attributes:
        name: Human-readable service name
        enabled: Whether to start this service
        poll_interval: Seconds between polls (for polling services)
        max_retries: Maximum restart attempts before giving up
        retry_delay: Base delay between restart attempts (exponential backoff)
        alert_threshold: Error count threshold before triggering alerts

    Educational Note:
        Each service can have independent configuration, allowing:
        - Critical services: Low alert threshold, many retries
        - Background services: Higher tolerance for errors
        - Development: Shorter intervals for faster feedback
    """

    name: str
    enabled: bool = True
    poll_interval: int = 15
    max_retries: int = 3
    retry_delay: int = 5
    alert_threshold: int = 5


@dataclass
class RunnerConfig:
    """
    Global configuration for the ServiceSupervisor.

    Attributes:
        environment: Deployment environment (development/staging/production)
        log_level: Logging verbosity (DEBUG/INFO/WARNING/ERROR)
        log_dir: Directory for log files
        log_max_bytes: Maximum log file size before rotation
        log_backup_count: Number of rotated log files to keep
        health_check_interval: Seconds between health checks
        metrics_interval: Seconds between metrics output
        services: Per-service configuration

    Educational Note:
        Centralized configuration makes it easy to:
        - Tune behavior per environment
        - Override defaults via CLI or environment variables
        - Validate configuration at startup
    """

    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5
    health_check_interval: int = 60
    metrics_interval: int = 300
    services: dict[str, ServiceConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize default services if none provided."""
        if not self.services:
            self.services = {
                "espn": ServiceConfig(name="ESPN Game Poller", poll_interval=15),
                "kalshi_rest": ServiceConfig(name="Kalshi REST Poller", poll_interval=30),
                "kalshi_ws": ServiceConfig(name="Kalshi WebSocket", enabled=False),
            }


# =============================================================================
# Service Protocol and State
# =============================================================================


class EventLoopService(Protocol):
    """
    Protocol defining the interface for managed services.

    All data collection services must implement this interface to be
    managed by the ServiceSupervisor. This enables uniform management
    of heterogeneous services (polling, streaming, etc.).

    Methods:
        start: Begin service operation
        stop: Gracefully stop the service
        is_running: Check if service is currently active
        get_stats: Retrieve service metrics

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

    Attributes:
        service: The service instance (implements EventLoopService)
        config: Service configuration
        started_at: When the service was last started
        last_health_check: When health was last verified
        error_count: Total errors encountered
        restart_count: Number of times restarted
        consecutive_failures: Failures since last success (for backoff)
        last_error: Most recent error message
        healthy: Current health status

    Educational Note:
        Separating state from the service itself allows:
        - Tracking metrics across restarts
        - Making restart decisions based on history
        - Debugging without modifying service code
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

    Provides centralized management of service lifecycle with health monitoring,
    automatic restart, and metrics aggregation.

    Responsibilities:
        1. Service lifecycle management (start, stop, restart)
        2. Health monitoring and alerting
        3. Metrics aggregation
        4. Graceful shutdown coordination

    Design Pattern:
        This implements the Supervisor pattern with these sub-patterns:
        - Circuit Breaker: Stop restarting after repeated failures
        - Health Check: Periodic service health validation
        - Observer: Alert callbacks for error thresholds

    Example:
        >>> config = RunnerConfig(environment=Environment.DEVELOPMENT)
        >>> supervisor = ServiceSupervisor(config)
        >>> supervisor.add_service("espn", espn_service, espn_config)
        >>> supervisor.start_all()
        >>> # ... services running ...
        >>> supervisor.stop_all()

    Reference: ADR-100 (Service Supervisor Pattern)
    Requirements: REQ-DATA-001, REQ-OBSERV-001
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
        self._alert_callbacks: list[Callable[[str, str, dict[str, Any]], None]] = []

    @property
    def is_running(self) -> bool:
        """Check if supervisor is running."""
        return self._start_time is not None and not self._shutdown_event.is_set()

    @property
    def uptime_seconds(self) -> float:
        """Get supervisor uptime in seconds."""
        if self._start_time is None:
            return 0.0
        return (datetime.now(UTC) - self._start_time).total_seconds()

    def register_alert_callback(self, callback: Callable[[str, str, dict[str, Any]], None]) -> None:
        """
        Register callback for alert notifications.

        Args:
            callback: Function(service_name, message, context) to call on alerts

        Educational Note:
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
            name: Service identifier (used for logging and metrics)
            service: Service instance implementing EventLoopService
            config: Service configuration
        """
        self.services[name] = ServiceState(service=service, config=config)
        self.logger.info("Registered service: %s", name)

    def remove_service(self, name: str) -> bool:
        """
        Remove a service from management.

        Args:
            name: Service identifier

        Returns:
            True if service was removed, False if not found
        """
        if name in self.services:
            state = self.services.pop(name)
            if state.service and state.service.is_running():
                state.service.stop()
            self.logger.info("Removed service: %s", name)
            return True
        return False

    def start_all(self) -> None:
        """
        Start all registered services.

        Starts each service in order, with error isolation.
        Failed services are marked unhealthy but don't block others.
        """
        self._start_time = datetime.now(UTC)
        self._shutdown_event.clear()

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
        self._health_thread = threading.Thread(
            target=self._health_check_loop, daemon=True, name="health-checker"
        )
        self._health_thread.start()

        # Start metrics thread
        self._metrics_thread = threading.Thread(
            target=self._metrics_loop, daemon=True, name="metrics-reporter"
        )
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

        uptime = self.uptime_seconds
        self.logger.info(
            "Data Collection Service stopped (uptime=%.1fs)",
            uptime,
            extra={"event": "supervisor_stop", "uptime_seconds": uptime},
        )
        self._start_time = None

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
        """Attempt to restart a failed service with exponential backoff."""
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
        aggregate = self.get_aggregate_metrics()

        self.logger.info(
            "Metrics: healthy=%d/%d, errors=%d, restarts=%d, uptime=%.0fs",
            aggregate["services_healthy"],
            aggregate["services_total"],
            aggregate["total_errors"],
            aggregate["total_restarts"],
            aggregate["uptime_seconds"],
            extra={
                "event": "metrics",
                "metrics": aggregate,
                "uptime_seconds": aggregate["uptime_seconds"],
            },
        )

    def get_aggregate_metrics(self) -> dict[str, Any]:
        """
        Get aggregate metrics across all services.

        Returns:
            Dictionary with metrics including uptime, service counts,
            error totals, restart totals, and per-service stats.
        """
        aggregate: dict[str, Any] = {
            "uptime_seconds": self.uptime_seconds,
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
                    "stats": (state.service.get_stats() if state.service.is_running() else {}),
                }

        return aggregate

    def wait_for_shutdown(self) -> None:
        """Block until shutdown signal received."""
        self._shutdown_event.wait()

    def trigger_shutdown(self) -> None:
        """Programmatically trigger shutdown (useful for testing)."""
        self._shutdown_event.set()


# =============================================================================
# Service Factory
# =============================================================================


def create_services(
    config: RunnerConfig, enabled_services: set[str] | None = None
) -> dict[str, tuple[EventLoopService, ServiceConfig]]:
    """
    Create service instances based on configuration.

    Factory function that creates the appropriate service instances
    based on the runner configuration and enabled services.

    Args:
        config: Runner configuration
        enabled_services: Set of service names to enable (None = all)

    Returns:
        Dict mapping service name to (service, config) tuple

    Educational Note:
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
                espn_service = create_espn_poller(
                    leagues=["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"],
                    poll_interval=svc_config.poll_interval,
                )
                services[name] = (cast("EventLoopService", espn_service), svc_config)
                logger.info("Created ESPN Game Poller (interval=%ds)", svc_config.poll_interval)

            elif name == "kalshi_rest":
                # Check for Kalshi credentials using two-axis naming convention
                if _has_kalshi_credentials(config.environment):
                    kalshi_rest_service = create_kalshi_poller(
                        series_tickers=["KXNFLGAME"],
                        poll_interval=svc_config.poll_interval,
                    )
                    services[name] = (
                        cast("EventLoopService", kalshi_rest_service),
                        svc_config,
                    )
                    logger.info(
                        "Created Kalshi REST Poller (interval=%ds)",
                        svc_config.poll_interval,
                    )
                else:
                    logger.warning("Kalshi API credentials not found, skipping REST poller")
                    svc_config.enabled = False

            elif name == "kalshi_ws":
                # WebSocket for real-time updates
                if _has_kalshi_credentials(config.environment):
                    kalshi_ws_service = create_websocket_handler(
                        environment=(
                            "demo" if config.environment != Environment.PRODUCTION else "prod"
                        )
                    )
                    services[name] = (
                        cast("EventLoopService", kalshi_ws_service),
                        svc_config,
                    )
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


def create_supervisor(
    environment: str = "development",
    enabled_services: set[str] | None = None,
    poll_interval: int = 15,
    health_check_interval: int = 60,
    metrics_interval: int = 300,
) -> ServiceSupervisor:
    """
    Create and configure a ServiceSupervisor with services.

    Convenience factory function for creating a fully configured
    supervisor ready to start.

    Args:
        environment: Deployment environment (development/staging/production)
        enabled_services: Set of services to enable (None = all)
        poll_interval: Default poll interval for services
        health_check_interval: Seconds between health checks
        metrics_interval: Seconds between metrics output

    Returns:
        Configured ServiceSupervisor with services registered

    Example:
        >>> supervisor = create_supervisor(
        ...     environment="development",
        ...     enabled_services={"espn"},
        ...     poll_interval=30
        ... )
        >>> supervisor.start_all()
    """
    # Build configuration
    config = RunnerConfig(
        environment=Environment(environment),
        health_check_interval=health_check_interval,
        metrics_interval=metrics_interval,
    )

    # Update poll intervals
    for svc_config in config.services.values():
        svc_config.poll_interval = poll_interval

    # Create services
    services = create_services(config, enabled_services)

    # Create supervisor
    supervisor = ServiceSupervisor(config)

    # Register services
    for name, (service, svc_config) in services.items():
        supervisor.add_service(name, service, svc_config)

    return supervisor
