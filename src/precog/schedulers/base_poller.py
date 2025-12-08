"""
Base Poller Abstract Class for Data Collection Services.

This module provides the BasePoller abstract base class that defines the common
interface and shared functionality for all polling-based data collection services.

Design Pattern:
    Template Method Pattern - BasePoller defines the skeleton of the polling algorithm,
    with concrete implementations providing specific polling logic.

Key Features:
    - APScheduler-based job scheduling (BackgroundScheduler)
    - Thread-safe statistics tracking
    - Graceful shutdown handling
    - Signal handler registration
    - EventLoopService Protocol compliance for ServiceSupervisor

Naming Convention:
    All pollers follow the pattern: {Platform}{Entity}Poller
    - KalshiPricePoller: Polls Kalshi for market prices
    - ESPNGamePoller: Polls ESPN for game states
    - Future: PolymarketPricePoller, etc.

Educational Note:
    Abstract base classes (ABCs) in Python serve two purposes:
    1. Define a contract that subclasses must implement
    2. Provide shared functionality to reduce code duplication

    The @abstractmethod decorator forces subclasses to implement specific methods,
    while concrete methods in the base class provide reusable functionality.

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-100 (Service Supervisor Pattern)
Requirements: REQ-DATA-001, REQ-OBSERV-001
"""

import logging
import signal
import sys
import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar, TypedDict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# =============================================================================
# Type Definitions
# =============================================================================


class PollerStats(TypedDict):
    """
    Base statistics for all pollers.

    All pollers track these common metrics. Subclasses may extend
    with additional stats specific to their data source.
    """

    polls_completed: int
    items_fetched: int
    items_updated: int
    items_created: int
    errors: int
    last_poll: str | None
    last_error: str | None


# =============================================================================
# Base Poller Abstract Class
# =============================================================================


class BasePoller(ABC):
    """
    Abstract base class for all polling-based data collection services.

    Provides common functionality for APScheduler-based polling with
    thread-safe statistics tracking and graceful shutdown.

    Subclasses must implement:
        - _poll_once(): Execute a single poll cycle
        - _get_job_name(): Return human-readable job name

    Subclasses may override:
        - _on_start(): Called after scheduler starts
        - _on_stop(): Called before scheduler stops
        - _create_initial_stats(): Return initial stats dict

    Attributes:
        poll_interval: Seconds between polls
        min_poll_interval: Minimum allowed interval (class variable)

    Example:
        >>> class MyPoller(BasePoller):
        ...     MIN_POLL_INTERVAL = 10
        ...
        ...     def _poll_once(self) -> dict[str, int]:
        ...         # Fetch and process data
        ...         return {"items_fetched": 5, "items_updated": 3}
        ...
        ...     def _get_job_name(self) -> str:
        ...         return "My Data Poll"

    Reference: ADR-100 (Service Supervisor Pattern)
    """

    # Subclasses should override these class variables
    MIN_POLL_INTERVAL: ClassVar[int] = 5  # seconds
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 15  # seconds

    def __init__(
        self,
        poll_interval: int | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize the base poller.

        Args:
            poll_interval: Seconds between polls. Uses DEFAULT_POLL_INTERVAL if None.
            logger: Logger instance. Creates module logger if None.

        Raises:
            ValueError: If poll_interval < MIN_POLL_INTERVAL.
        """
        effective_interval = poll_interval or self.DEFAULT_POLL_INTERVAL

        if effective_interval < self.MIN_POLL_INTERVAL:
            raise ValueError(
                f"poll_interval must be at least {self.MIN_POLL_INTERVAL} seconds. "
                f"Got {effective_interval}."
            )

        self.poll_interval = effective_interval
        self.logger = logger or logging.getLogger(self.__class__.__module__)

        # Internal state
        self._scheduler: BackgroundScheduler | None = None
        self._enabled = False
        self._lock = threading.Lock()
        self._stats = self._create_initial_stats()

    def _create_initial_stats(self) -> PollerStats:
        """
        Create initial statistics dictionary.

        Override in subclasses to add additional stats fields.

        Returns:
            Initial stats with all counters at zero.
        """
        return PollerStats(
            polls_completed=0,
            items_fetched=0,
            items_updated=0,
            items_created=0,
            errors=0,
            last_poll=None,
            last_error=None,
        )

    # =========================================================================
    # EventLoopService Protocol Implementation
    # =========================================================================

    @property
    def enabled(self) -> bool:
        """Whether the poller is currently running."""
        return self._enabled

    def is_running(self) -> bool:
        """
        Check if the poller is currently running.

        Implements EventLoopService Protocol for ServiceSupervisor compatibility.

        Returns:
            True if poller is running, False otherwise.
        """
        return self._enabled

    @property
    def stats(self) -> PollerStats:
        """Current statistics about polling activity (copy)."""
        with self._lock:
            return PollerStats(**self._stats)

    def get_stats(self) -> dict[str, Any]:
        """
        Get current statistics as a dictionary.

        Implements EventLoopService Protocol for ServiceSupervisor compatibility.

        Returns:
            Dictionary with polling statistics.
        """
        with self._lock:
            return dict(self._stats)

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def start(self) -> None:
        """
        Start the polling scheduler.

        Initializes APScheduler and begins polling at the configured interval.
        Runs in a background thread, allowing the calling code to continue.

        Raises:
            RuntimeError: If already started.

        Educational Note:
            We use BackgroundScheduler (not BlockingScheduler) because we want
            the calling code to continue executing. The scheduler manages its
            own thread pool for job execution.
        """
        with self._lock:
            if self._enabled:
                raise RuntimeError(f"{self.__class__.__name__} is already running")

            self._scheduler = BackgroundScheduler(
                job_defaults={
                    "coalesce": True,  # Combine missed runs into one
                    "max_instances": 1,  # Only one poll job at a time
                    "misfire_grace_time": 60,  # Grace period for late jobs
                }
            )

            self._scheduler.add_job(
                self._poll_wrapper,
                IntervalTrigger(seconds=self.poll_interval),
                id=f"poll_{self.__class__.__name__.lower()}",
                name=self._get_job_name(),
                replace_existing=True,
            )

            self._scheduler.start()
            self._enabled = True

        self.logger.info(
            "%s started - polling every %d seconds",
            self.__class__.__name__,
            self.poll_interval,
        )

        # Hook for subclass initialization
        self._on_start()

        # Run initial poll immediately
        self._poll_wrapper()

    def stop(self, wait: bool = True) -> None:
        """
        Stop the polling scheduler.

        Args:
            wait: If True, wait for running jobs to complete before returning.

        Educational Note:
            The 'wait' parameter ensures clean shutdown. Setting it to True
            ensures any in-progress database operations complete before the
            scheduler terminates.
        """
        with self._lock:
            if not self._enabled:
                self.logger.warning("%s is not running", self.__class__.__name__)
                return

            # Hook for subclass cleanup
            self._on_stop()

            if self._scheduler:
                self._scheduler.shutdown(wait=wait)
                self._scheduler = None

            self._enabled = False

        self.logger.info("%s stopped", self.__class__.__name__)

    # =========================================================================
    # Abstract Methods (Subclasses Must Implement)
    # =========================================================================

    @abstractmethod
    def _poll_once(self) -> dict[str, int]:
        """
        Execute a single poll cycle.

        Subclasses implement this to fetch data from their source and
        update the database.

        Returns:
            Dictionary with counts: items_fetched, items_updated, items_created

        Raises:
            Any exception from the polling operation (will be caught and logged).
        """
        ...

    @abstractmethod
    def _get_job_name(self) -> str:
        """
        Return human-readable name for the polling job.

        Used in scheduler job registration and logging.

        Returns:
            Job name string (e.g., "Kalshi Market Price Poll").
        """
        ...

    # =========================================================================
    # Hook Methods (Subclasses May Override)
    # =========================================================================

    def _on_start(self) -> None:  # noqa: B027
        """
        Called after scheduler starts.

        Override to perform additional initialization (e.g., API client setup).
        This is an intentional empty hook for subclasses.
        """

    def _on_stop(self) -> None:  # noqa: B027
        """
        Called before scheduler stops.

        Override to perform cleanup (e.g., close API connections).
        This is an intentional empty hook for subclasses.
        """

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _poll_wrapper(self) -> None:
        """
        Wrapper around _poll_once that handles errors and updates stats.

        This is the method registered with APScheduler. It calls the
        abstract _poll_once() method and handles any exceptions.
        """
        start_time = datetime.now(UTC)

        try:
            result = self._poll_once()

            with self._lock:
                self._stats["polls_completed"] += 1
                self._stats["items_fetched"] += result.get("items_fetched", 0)
                self._stats["items_updated"] += result.get("items_updated", 0)
                self._stats["items_created"] += result.get("items_created", 0)
                self._stats["last_poll"] = start_time.isoformat()

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            self.logger.debug(
                "Poll completed: fetched=%d, updated=%d, created=%d in %.2fs",
                result.get("items_fetched", 0),
                result.get("items_updated", 0),
                result.get("items_created", 0),
                elapsed,
            )

        except Exception as e:
            self.logger.exception("Error in poll cycle: %s", e)
            with self._lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)

    def poll_once(self) -> dict[str, int]:
        """
        Execute a single poll cycle manually.

        Useful for testing or on-demand updates outside the scheduled interval.

        Returns:
            Dictionary with counts: items_fetched, items_updated, items_created
        """
        return self._poll_once()

    def setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.

        Registers handlers for SIGINT (Ctrl+C) and SIGTERM to ensure
        clean shutdown of the scheduler.

        Educational Note:
            Signal handlers are important for production services.
            Without them, Ctrl+C might leave database connections open
            or API sessions active.
        """

        def shutdown_handler(signum: int, frame: Any) -> None:
            self.logger.info("Received signal %d, shutting down...", signum)
            self.stop(wait=True)
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        self.logger.debug("Signal handlers registered")
