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
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast

from precog.database.crud_schedulers import (
    check_active_schedulers,
    cleanup_stale_schedulers,
    upsert_scheduler_status,
)
from precog.database.crud_system import (
    create_circuit_breaker_event,
    get_active_breakers,
    upsert_system_health,
)
from precog.schedulers.espn_game_poller import ESPNGamePoller, create_espn_poller
from precog.schedulers.kalshi_poller import KalshiMarketPoller, create_kalshi_poller
from precog.schedulers.kalshi_websocket import KalshiWebSocketHandler, create_websocket_handler

# Set up logging early for helper functions
logger = logging.getLogger(__name__)

# Service registry: maps service names to their health metadata.
# Built at import time from class variables on poller classes.
# Adding a new service requires only:
#   1. Add SERVICE_KEY, HEALTH_COMPONENT, BREAKER_TYPE class vars to the poller
#   2. Register the factory in SERVICE_FACTORIES (below create_services)
# No if/elif dispatch needed — the supervisor reads metadata from the registry.
#
# Values must match database constraints:
#   system_health.component: see SystemHealthComponent in crud_operations.py
#   circuit_breaker_events.breaker_type: ('daily_loss_limit', 'api_failures',
#       'data_stale', 'position_limit', 'manual')
SERVICE_TO_COMPONENT: dict[str, str] = {
    ESPNGamePoller.SERVICE_KEY: ESPNGamePoller.HEALTH_COMPONENT,
    KalshiMarketPoller.SERVICE_KEY: KalshiMarketPoller.HEALTH_COMPONENT,
    KalshiWebSocketHandler.SERVICE_KEY: KalshiWebSocketHandler.HEALTH_COMPONENT,
}
COMPONENT_TO_BREAKER_TYPE: dict[str, str] = {
    ESPNGamePoller.HEALTH_COMPONENT: ESPNGamePoller.BREAKER_TYPE,
    KalshiMarketPoller.HEALTH_COMPONENT: KalshiMarketPoller.BREAKER_TYPE,
    KalshiWebSocketHandler.HEALTH_COMPONENT: KalshiWebSocketHandler.BREAKER_TYPE,
}


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
                "espn": ServiceConfig(name="ESPN Game Poller", poll_interval=30),
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
    def host_id(self) -> str:
        """Get hostname for database status tracking."""
        return socket.gethostname()

    def _update_db_status(
        self,
        service_name: str,
        status: str,
        *,
        stats: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Update service status in database for cross-process IPC.

        This enables the `scheduler status` CLI command to query the current
        state of running services from any process.

        Args:
            service_name: Service identifier (e.g., 'espn', 'kalshi_rest')
            status: Service status ('starting', 'running', 'stopping', 'stopped', 'failed')
            stats: Optional service metrics
            config: Optional service configuration
            error_message: Optional error message for 'failed' status

        Educational Note:
            The database table approach solves the IPC problem where:
            - `scheduler start` runs in process A (long-running)
            - `scheduler status` runs in process B (one-shot query)
            - Process B can't see process A's in-memory state
            - Solution: Process A writes status to DB, process B reads from DB

        Reference:
            - Migration 0012: scheduler_status table
            - Issue #255: Scheduler status shows "not running"
        """
        try:
            upsert_scheduler_status(
                host_id=self.host_id,
                service_name=service_name,
                status=status,
                pid=os.getpid(),
                started_at=self._start_time,
                stats=stats,
                config=config,
                error_message=error_message,
            )
        except Exception as e:
            # Don't let DB errors crash the service - log and continue
            self.logger.warning(
                "Failed to update scheduler status in database: %s",
                e,
                extra={"service": service_name, "status": status},
            )

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

    def _check_startup_guard(self, force: bool = False) -> None:
        """
        Check for concurrent scheduler instances before starting.

        Prevents two supervisors from running against the same database,
        which would corrupt SCD Type 2 versioning (both read row_current_ind=TRUE,
        both archive, one silently wins).

        Steps:
            1. Clean stale entries (heartbeat expired = probably crashed)
            2. Check for truly active instances (heartbeat fresh)
            3. If active found and no --force: raise RuntimeError
            4. If active found and --force: warn and proceed

        Args:
            force: If True, override the guard and start anyway.

        Raises:
            RuntimeError: If active schedulers detected and force is False.

        Reference: Issue #363
        """
        stale_threshold = self.config.health_check_interval * 2

        # Step 1: Clean stale entries (crashed services that never said goodbye)
        try:
            stale_cleaned = cleanup_stale_schedulers(
                stale_threshold_seconds=stale_threshold,
            )
            if stale_cleaned:
                self.logger.warning(
                    "Startup guard: cleaned %d stale scheduler entries (assumed crashed)",
                    stale_cleaned,
                )
        except Exception as e:
            self.logger.warning("Startup guard: could not clean stale entries: %s", e)

        # Step 2: Check for active instances with fresh heartbeats
        try:
            active = check_active_schedulers(
                stale_threshold_seconds=stale_threshold,
            )
        except Exception as e:
            # If we can't check, log and allow startup (DB might be empty/new)
            self.logger.warning(
                "Startup guard: could not query active schedulers: %s. Proceeding.",
                e,
            )
            return

        if not active:
            self.logger.info("Startup guard: no active schedulers detected, proceeding")
            return

        # Active instances found — report details
        for svc in active:
            self.logger.warning(
                "Startup guard: active scheduler detected — "
                "host=%s service=%s pid=%s last_heartbeat=%s",
                svc.get("host_id"),
                svc.get("service_name"),
                svc.get("pid"),
                svc.get("last_heartbeat"),
            )

        if force:
            self.logger.warning(
                "Startup guard overridden (--force): %d active service(s) will be superseded",
                len(active),
            )
            return

        raise RuntimeError(
            f"Startup blocked: {len(active)} active scheduler(s) detected on database. "
            "Another instance may be running. Use --force to override."
        )

    def start_all(self, *, force: bool = False) -> None:
        """
        Start all registered services.

        Starts each service in order, with error isolation.
        Failed services are marked unhealthy but don't block others.

        Args:
            force: If True, override the concurrent startup guard.
        """
        # Check for concurrent instances before starting
        self._check_startup_guard(force=force)

        self._start_time = datetime.now(UTC)
        self._shutdown_event.clear()

        # Clean up old log files on startup
        from precog.utils.logger import cleanup_old_logs

        removed = cleanup_old_logs()
        if removed:
            self.logger.info("Cleaned up %d old log file(s)", removed)

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

        # Report 'starting' status to database
        self._update_db_status(name, "starting")

        state.service.start()
        state.started_at = datetime.now(UTC)
        state.healthy = True
        state.consecutive_failures = 0

        # Report 'running' status to database
        self._update_db_status(name, "running")

        self.logger.info(
            "Service started: %s",
            name,
            extra={"service": name, "event": "service_started"},
        )

    def stop_all(self) -> None:
        """
        Stop all services gracefully.

        Signals shutdown, then stops each service with timeout.
        Updates database status for each service to enable cross-process
        status queries to show accurate state.
        """
        self.logger.info("Shutting down all services...")
        self._shutdown_event.set()

        for name, state in self.services.items():
            try:
                if state.service and state.service.is_running():
                    self.logger.info("Stopping service: %s", name)
                    # Report 'stopping' status to database
                    self._update_db_status(name, "stopping")
                    state.service.stop()
                    # Report 'stopped' status to database
                    self._update_db_status(name, "stopped")
                    self.logger.info("Service stopped: %s", name)
                else:
                    # Mark as stopped even if not running (cleanup)
                    self._update_db_status(name, "stopped")
            except Exception as e:
                self.logger.error("Error stopping service %s: %s", name, e)
                # Report 'failed' status with error message
                self._update_db_status(name, "failed", error_message=str(e))

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
        """
        Check health of a single service and update database heartbeat.

        This method serves three purposes:
        1. Internal health monitoring (restart decisions, alerting)
        2. External status visibility (heartbeat updates for cross-process IPC)
        3. Persistent component health (system_health table for CLI visibility)

        The heartbeat update ensures that `scheduler status` can:
        - See current service state
        - Detect stale/crashed services (heartbeat older than threshold)
        - Display service-specific stats (polls, errors, etc.)

        Health Determination Thresholds:
        - healthy: running + error rate <5%
        - degraded: running + error rate 5-25%, OR last poll > 2x interval
        - down: not running, OR error rate >25%, OR no poll for >5x interval
        """
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

            # Report 'failed' status to database
            self._update_db_status(
                name,
                "failed",
                error_message=f"Service not running (consecutive_failures={state.consecutive_failures})",
            )

            # Persist 'down' to system_health table
            self._update_system_health(
                name,
                "down",
                {"reason": "not_running", "consecutive_failures": state.consecutive_failures},
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

        # Update heartbeat in database with current stats
        # This is the "lease renewal" that keeps the service marked as running
        self._update_db_status(name, "running", stats=stats)

        # Determine and persist component health to system_health table
        health_status, health_details = self._determine_health(name, state, stats)
        self._update_system_health(name, health_status, health_details)

    def _determine_health(
        self,
        name: str,
        state: ServiceState,
        stats: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """
        Determine component health status from service stats.

        Applies threshold-based rules to classify a running service as
        healthy, degraded, or down.

        Thresholds:
            - healthy: error rate <5%
            - degraded: error rate 5-25%, OR last successful poll > 2x interval
            - down: error rate >25%, OR no poll for >5x interval

        Args:
            name: Service identifier (e.g., 'espn', 'kalshi_rest')
            state: Current runtime state for the service
            stats: Latest stats dict from service.get_stats()

        Returns:
            Tuple of (status_string, details_dict) where status is one of
            'healthy', 'degraded', 'down'.

        Educational Note:
            Error rate is calculated as errors / total_polls. If total_polls
            is zero (service just started), we default to 'healthy' since
            there's no evidence of problems yet.
        """
        total_polls = stats.get("polls_completed", 0) or stats.get("polls", 0)
        total_errors = stats.get("errors", 0)
        last_successful_poll = stats.get("last_successful_poll")

        # Calculate error rate (avoid division by zero; default 0.0 = healthy)
        error_rate = total_errors / total_polls if total_polls > 0 else 0.0

        details: dict[str, Any] = {
            "service_name": name,
            "error_rate": f"{error_rate:.4f}",
            "total_polls": total_polls,
            "total_errors": total_errors,
        }

        # Check staleness: time since last successful poll vs poll interval
        poll_interval = state.config.poll_interval if state.config else 30
        poll_age_seconds: float | None = None

        if last_successful_poll is not None:
            try:
                if isinstance(last_successful_poll, str):
                    last_poll_dt = datetime.fromisoformat(last_successful_poll)
                else:
                    last_poll_dt = last_successful_poll
                poll_age_seconds = (datetime.now(UTC) - last_poll_dt).total_seconds()
                details["last_poll_age_seconds"] = int(poll_age_seconds)
            except (ValueError, TypeError):
                # Can't parse timestamp -- ignore staleness check
                pass

        # Apply thresholds: down > degraded > healthy
        # Down: error rate >25% OR no poll for >5x interval
        if error_rate > 0.25:
            return "down", {**details, "reason": "high_error_rate"}

        if poll_age_seconds is not None and poll_age_seconds > poll_interval * 5:
            return "down", {**details, "reason": "stale_no_poll_5x_interval"}

        # Degraded: error rate 5-25% OR last poll > 2x interval
        if error_rate >= 0.05:
            return "degraded", {**details, "reason": "elevated_error_rate"}

        if poll_age_seconds is not None and poll_age_seconds > poll_interval * 2:
            return "degraded", {**details, "reason": "stale_poll_2x_interval"}

        # Enrich details with matching stats for Kalshi service.
        # This makes matching health visible via the system_health table
        # without requiring a schema migration to add a new component.
        if name == "kalshi_rest":
            matching_matched = stats.get("matching_matched", 0)
            matching_total = (
                matching_matched
                + stats.get("matching_parse_fail", 0)
                + stats.get("matching_no_code", 0)
                + stats.get("matching_no_game", 0)
            )
            if matching_total > 0:
                # NOTE: float is intentional here -- this is a ratio of
                # integer counts, not a price or probability.
                match_rate = matching_matched / matching_total
                details["matching_match_rate"] = f"{match_rate:.4f}"
                details["matching_total_events"] = matching_total
                details["matching_backfill_linked"] = stats.get("matching_backfill_linked", 0)

        # Healthy: running with acceptable error rate
        return "healthy", details

    def _update_system_health(
        self,
        service_name: str,
        status: str,
        details: dict[str, Any],
    ) -> None:
        """
        Persist component health to the system_health table.

        Maps service names to system_health component names using
        SERVICE_TO_COMPONENT. Services without a mapping are skipped
        (safe default for unknown/future services).

        When a component transitions to "down", automatically trips the
        appropriate circuit breaker (data_stale for ESPN, api_failures
        for Kalshi/websocket). Only trips if no active breaker of that
        type already exists, preventing duplicate trips on repeated
        health checks that report "down".

        Args:
            service_name: Internal service identifier (e.g., 'espn')
            status: Health status ('healthy', 'degraded', 'down')
            details: Component-specific health details as JSONB

        Educational Note:
            This is the bridge between the supervisor's internal health
            monitoring and the persistent system_health table. The table
            makes health visible to the CLI and other processes. The
            circuit breaker auto-trip provides a safety net: if a component
            goes down, future trade execution (Phase 2) can check for active
            breakers before placing orders.
        """
        component = SERVICE_TO_COMPONENT.get(service_name)
        if component is None:
            self.logger.debug(
                "No system_health component mapping for service '%s', skipping",
                service_name,
            )
            return

        try:
            upsert_system_health(
                component=component,
                status=status,
                details=details,
                alert_sent=(status != "healthy"),
            )
        except Exception as e:
            # Don't let DB errors crash the health check loop
            self.logger.warning(
                "Failed to update system_health for %s: %s",
                component,
                e,
            )

        # Auto-trip circuit breaker on transition to "down"
        if status == "down":
            self._auto_trip_circuit_breaker(component, details)

    def _auto_trip_circuit_breaker(
        self,
        component: str,
        details: dict[str, Any],
    ) -> None:
        """
        Automatically trip a circuit breaker when a component goes down.

        Only trips if no active breaker of the same type already exists.
        This prevents duplicate breaker events on repeated health checks
        that continue to report "down".

        Args:
            component: system_health component name (e.g., 'espn_api')
            details: Health check details to include as trigger_value

        Educational Note:
            Circuit breakers are checked BEFORE trade execution (Phase 2).
            Auto-tripping on "down" ensures we never trade with stale data
            or broken API connections. Manual resolution via CLI is required
            to clear the breaker and resume trading.
        """
        breaker_type = COMPONENT_TO_BREAKER_TYPE.get(component)
        if breaker_type is None:
            return

        try:
            # Only trip if no active breaker of this type exists
            active = get_active_breakers(breaker_type=breaker_type)
            if active:
                self.logger.debug(
                    "Active %s breaker already exists (event_id=%s), skipping auto-trip",
                    breaker_type,
                    active[0].get("event_id"),
                )
                return

            event_id = create_circuit_breaker_event(
                breaker_type=breaker_type,
                trigger_value={"component": component, **details},
                notes=f"Auto-tripped: {component} health status is down",
            )
            self.logger.warning(
                "Circuit breaker auto-tripped: type=%s, component=%s, event_id=%s",
                breaker_type,
                component,
                event_id,
            )
        except Exception as e:
            # Don't let circuit breaker DB errors crash the health check loop
            self.logger.warning(
                "Failed to auto-trip circuit breaker for %s: %s",
                component,
                e,
            )

    def _attempt_restart(self, name: str, state: ServiceState) -> None:
        """
        Attempt to restart a failed service with exponential backoff.

        Updates database status throughout the restart lifecycle:
        - 'starting' when restart attempt begins
        - 'running' on successful restart
        - 'failed' if restart attempt fails
        """
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
            # Report 'starting' status before restart attempt
            self._update_db_status(name, "starting")

            state.service.start()
            state.restart_count += 1
            state.started_at = datetime.now(UTC)
            state.healthy = True
            state.consecutive_failures = 0

            # Report 'running' status on successful restart
            self._update_db_status(name, "running")

            self.logger.info("Service %s restarted successfully", name)
        except Exception as e:
            self.logger.error("Restart failed for %s: %s", name, e)
            state.last_error = str(e)

            # Report 'failed' status with error message
            self._update_db_status(name, "failed", error_message=str(e))

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
        """Collect and output aggregate metrics with per-service poll counts."""
        aggregate = self.get_aggregate_metrics()

        # Build per-service summary for operator visibility
        svc_parts = []
        for name, svc_data in aggregate.get("per_service", {}).items():
            stats = svc_data.get("stats", {})
            polls = stats.get("polls_completed", "?")
            errs = svc_data.get("error_count", 0)
            svc_parts.append(f"{name}={polls}polls/{errs}err")

        svc_summary = ", ".join(svc_parts) if svc_parts else "no services"

        self.logger.info(
            "Metrics: healthy=%d/%d, uptime=%.0fs | %s",
            aggregate["services_healthy"],
            aggregate["services_total"],
            aggregate["uptime_seconds"],
            svc_summary,
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
# Service Factory Registry
# =============================================================================


def _create_espn(
    config: RunnerConfig,
    leagues: list[str] | None = None,
    espn_poll_interval: int = 30,
    **_kwargs: Any,
) -> EventLoopService:
    """Factory for ESPN Game Poller."""
    return cast(
        "EventLoopService",
        create_espn_poller(
            leagues=leagues,
            poll_interval=espn_poll_interval,
        ),
    )


def _create_kalshi_rest(
    config: RunnerConfig,
    kalshi_env: str = "demo",
    series_tickers: list[str] | None = None,
    kalshi_poll_interval: int = 15,
    **_kwargs: Any,
) -> EventLoopService | None:
    """Factory for Kalshi REST Poller. Returns None if credentials missing."""
    if not _has_kalshi_credentials(config.environment):
        logging.getLogger("precog.factory").warning(
            "Kalshi API credentials not found, skipping REST poller"
        )
        return None
    return cast(
        "EventLoopService",
        create_kalshi_poller(
            series_tickers=series_tickers,
            poll_interval=kalshi_poll_interval,
            environment=kalshi_env,
        ),
    )


def _create_kalshi_ws(
    config: RunnerConfig,
    **_kwargs: Any,
) -> EventLoopService | None:
    """Factory for Kalshi WebSocket Handler. Returns None if credentials missing."""
    if not _has_kalshi_credentials(config.environment):
        logging.getLogger("precog.factory").warning(
            "Kalshi API credentials not found, skipping WebSocket"
        )
        return None
    return cast(
        "EventLoopService",
        create_websocket_handler(
            environment="demo" if config.environment != Environment.PRODUCTION else "prod"
        ),
    )


# Registry mapping service names to factory callables.
# To add a new service (e.g., Polymarket):
#   1. Add SERVICE_KEY/HEALTH_COMPONENT/BREAKER_TYPE class vars to the poller
#   2. Add the poller class to _REGISTRY_CLASSES (top of file)
#   3. Add a _create_<name> factory function
#   4. Register it here
SERVICE_FACTORIES: dict[str, Callable[..., EventLoopService | None]] = {
    "espn": _create_espn,
    "kalshi_rest": _create_kalshi_rest,
    "kalshi_ws": _create_kalshi_ws,
}


def create_services(
    config: RunnerConfig,
    enabled_services: set[str] | None = None,
    kalshi_env: str = "demo",
    leagues: list[str] | None = None,
    series_tickers: list[str] | None = None,
    espn_poll_interval: int = 30,
    kalshi_poll_interval: int = 15,
) -> dict[str, tuple[EventLoopService, ServiceConfig]]:
    """
    Create service instances based on configuration.

    Factory function that creates the appropriate service instances
    based on the runner configuration and enabled services.

    Args:
        config: Runner configuration
        enabled_services: Set of service names to enable (None = all)
        kalshi_env: Kalshi API environment (demo/prod)
        leagues: ESPN leagues to poll (None = use ESPNGamePoller defaults)
        series_tickers: Kalshi series to poll (None = use KalshiMarketPoller defaults)
        espn_poll_interval: ESPN poll interval in seconds
        kalshi_poll_interval: Kalshi poll interval in seconds

    Returns:
        Dict mapping service name to (service, config) tuple
    """
    services: dict[str, tuple[EventLoopService, ServiceConfig]] = {}
    logger = logging.getLogger("precog.factory")

    for name, svc_config in config.services.items():
        if enabled_services and name not in enabled_services:
            svc_config.enabled = False
            continue

        try:
            factory = SERVICE_FACTORIES.get(name)

            if factory is None:
                # Unknown or future service — skip silently
                logger.info("Service '%s' has no registered factory, skipping", name)
                svc_config.enabled = False
                continue

            service = factory(
                config=config,
                kalshi_env=kalshi_env,
                leagues=leagues,
                series_tickers=series_tickers,
                espn_poll_interval=espn_poll_interval,
                kalshi_poll_interval=kalshi_poll_interval,
            )

            if service is not None:
                services[name] = (service, svc_config)
                logger.info("Created service '%s'", name)
            else:
                svc_config.enabled = False

        except Exception as e:
            logger.error("Failed to create service %s: %s", name, e)
            svc_config.enabled = False

    return services


def create_supervisor(
    environment: str = "development",
    kalshi_env: str = "demo",
    enabled_services: set[str] | None = None,
    leagues: list[str] | None = None,
    series_tickers: list[str] | None = None,
    espn_poll_interval: int = 30,
    kalshi_poll_interval: int = 15,
    health_check_interval: int = 60,
    metrics_interval: int = 300,
) -> ServiceSupervisor:
    """
    Create and configure a ServiceSupervisor with services.

    Convenience factory function for creating a fully configured
    supervisor ready to start.

    Args:
        environment: Deployment environment (development/staging/production)
        kalshi_env: Kalshi API environment (demo/prod)
        enabled_services: Set of services to enable (None = all)
        leagues: ESPN leagues to poll (None = use ESPNGamePoller defaults)
        series_tickers: Kalshi series to poll (None = use KalshiMarketPoller defaults)
        espn_poll_interval: ESPN poll interval in seconds
        kalshi_poll_interval: Kalshi poll interval in seconds
        health_check_interval: Seconds between health checks
        metrics_interval: Seconds between metrics output

    Returns:
        Configured ServiceSupervisor with services registered

    Example:
        >>> supervisor = create_supervisor(
        ...     environment="development",
        ...     enabled_services={"espn"},
        ...     espn_poll_interval=30,
        ... )
        >>> supervisor.start_all()
    """
    # Build configuration
    config = RunnerConfig(
        environment=Environment(environment),
        health_check_interval=health_check_interval,
        metrics_interval=metrics_interval,
    )

    # Create services with user-specified parameters
    services = create_services(
        config,
        enabled_services,
        kalshi_env=kalshi_env,
        leagues=leagues,
        series_tickers=series_tickers,
        espn_poll_interval=espn_poll_interval,
        kalshi_poll_interval=kalshi_poll_interval,
    )

    # Create supervisor
    supervisor = ServiceSupervisor(config)

    # Register services
    for name, (service, svc_config) in services.items():
        supervisor.add_service(name, service, svc_config)

    return supervisor
