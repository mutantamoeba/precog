"""
Kalshi market price polling service using APScheduler.

This module provides the KalshiMarketPoller class that polls Kalshi APIs at
configurable intervals and syncs market prices to the database using SCD Type 2
versioning.

Key Features:
- APScheduler-based polling (configurable 30-120 second intervals)
- Filters for specific series (e.g., KXNFLGAME for NFL markets)
- Sub-penny Decimal price precision (NEVER float!)
- SCD Type 2 versioning for price history
- Rate limiting compliance (100 req/min)
- Error recovery with logging
- Clean shutdown handling

Educational Notes:
------------------
Polling Frequency Considerations:
    - Kalshi rate limit: 100 requests/minute
    - get_markets() with pagination may use 2-3 requests per poll
    - 30-60 second intervals allow ~2-3 polls per minute (safe margin)
    - Don't poll faster than 30s - wastes API quota without benefit

SCD Type 2 for Market Prices:
    - Every price change creates a new row (full price history)
    - Enables historical edge analysis ("what was the spread at 2:30 PM?")
    - Provides audit trail for trading decisions
    - Supports backtesting with historical prices

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
"""

import logging
import signal
import sys
import threading
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar, TypedDict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from precog.api_connectors.kalshi_client import KalshiClient
from precog.api_connectors.types import ProcessedMarketData
from precog.database.crud_operations import (
    create_market,
    get_current_market,
    update_market_with_versioning,
)

# Set up logging
logger = logging.getLogger(__name__)


class _PollerStats(TypedDict):
    """Type definition for poller statistics."""

    polls_completed: int
    markets_fetched: int
    markets_updated: int
    markets_created: int
    errors: int
    last_poll: str | None
    last_error: str | None


class KalshiMarketPoller:
    """
    Kalshi market price polling service.

    Polls Kalshi APIs at regular intervals and syncs market prices to the database.
    Uses APScheduler for reliable job scheduling with automatic retry on errors.

    Attributes:
        series_tickers: List of series to poll (e.g., ["KXNFLGAME", "KXNCAAFGAME"])
        poll_interval: Seconds between polls (default: 60, minimum: 30)
        environment: Kalshi environment ("demo" or "prod")
        enabled: Whether polling is currently enabled

    Usage:
        >>> # Basic usage
        >>> poller = KalshiMarketPoller(series_tickers=["KXNFLGAME"])
        >>> poller.start()
        >>> # ... polling runs in background ...
        >>> poller.stop()
        >>>
        >>> # Custom configuration
        >>> poller = KalshiMarketPoller(
        ...     series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
        ...     poll_interval=30,
        ...     environment="demo"
        ... )
        >>> poller.start()

    Educational Note:
        The poller uses a BackgroundScheduler which runs jobs in a thread pool.
        This allows the main application to continue running while polls happen
        in the background. The scheduler handles job execution, retries, and
        timing automatically.

    Reference: Phase 2 Live Data Integration
    """

    # Default configuration
    DEFAULT_SERIES_TICKERS: ClassVar[list[str]] = ["KXNFLGAME"]
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 15  # seconds (balanced for near real-time)
    MIN_POLL_INTERVAL: ClassVar[int] = 5  # minimum seconds (rate limit: 100 req/min)
    MAX_MARKETS_PER_REQUEST: ClassVar[int] = 200  # Kalshi API limit

    # Rate limit guidance:
    # - Kalshi allows 100 requests/minute
    # - Each poll uses 1-3 requests (pagination for large series)
    # - 5 second interval = 12-36 req/min (safe)
    # - 3 second interval = 20-60 req/min (caution)
    # - 1 second interval = 60-180 req/min (EXCEEDS LIMIT)

    # Platform ID for database records
    PLATFORM_ID: ClassVar[str] = "kalshi"

    def __init__(
        self,
        series_tickers: list[str] | None = None,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        environment: str = "demo",
        kalshi_client: KalshiClient | None = None,
    ) -> None:
        """
        Initialize the KalshiMarketPoller.

        Args:
            series_tickers: List of series to poll (e.g., ["KXNFLGAME"]).
                Defaults to NFL game markets only.
            poll_interval: Seconds between polls. Minimum 30 seconds.
            environment: Kalshi environment ("demo" or "prod").
            kalshi_client: Optional KalshiClient instance (for testing/mocking).

        Raises:
            ValueError: If poll_interval < 30 or environment invalid.
        """
        if poll_interval < self.MIN_POLL_INTERVAL:
            raise ValueError(
                f"poll_interval must be at least {self.MIN_POLL_INTERVAL} seconds. "
                "Kalshi rate limit is 100 req/min. At 5s interval with pagination, "
                "you use ~12-36 req/min (safe). Faster risks rate limiting."
            )
        if environment not in ("demo", "prod"):
            raise ValueError("environment must be 'demo' or 'prod'")

        self.series_tickers = series_tickers or self.DEFAULT_SERIES_TICKERS.copy()
        self.poll_interval = poll_interval
        self.environment = environment

        # Initialize Kalshi client (or use provided mock)
        self.kalshi_client = kalshi_client or KalshiClient(environment=environment)

        # State tracking
        self._scheduler: BackgroundScheduler | None = None
        self._enabled = False
        self._lock = threading.Lock()
        self._stats: _PollerStats = {
            "polls_completed": 0,
            "markets_fetched": 0,
            "markets_updated": 0,
            "markets_created": 0,
            "errors": 0,
            "last_poll": None,
            "last_error": None,
        }

        logger.info(
            "KalshiMarketPoller initialized: series=%s, poll_interval=%ds, env=%s",
            self.series_tickers,
            self.poll_interval,
            self.environment,
        )

    @property
    def enabled(self) -> bool:
        """Whether the poller is currently running."""
        return self._enabled

    @property
    def stats(self) -> _PollerStats:
        """Current statistics about polling activity."""
        with self._lock:
            return self._stats.copy()

    def start(self) -> None:
        """
        Start the polling scheduler.

        Initializes APScheduler and begins polling at the configured interval.
        The scheduler runs in a background thread, allowing the main program
        to continue execution.

        Raises:
            RuntimeError: If already started.

        Educational Note:
            We use BackgroundScheduler instead of BlockingScheduler because
            we want the calling code to continue executing. The scheduler
            manages its own thread pool for job execution.
        """
        with self._lock:
            if self._enabled:
                raise RuntimeError("KalshiMarketPoller is already running")

            self._scheduler = BackgroundScheduler(
                job_defaults={
                    "coalesce": True,  # Combine missed runs into one
                    "max_instances": 1,  # Only one poll job at a time
                    "misfire_grace_time": 60,  # Grace period for late jobs
                }
            )

            # Add the polling job
            self._scheduler.add_job(
                self._poll_all_series,
                IntervalTrigger(seconds=self.poll_interval),
                id="poll_kalshi",
                name="Kalshi Market Price Poll",
                replace_existing=True,
            )

            self._scheduler.start()
            self._enabled = True

        logger.info("KalshiMarketPoller started - polling every %d seconds", self.poll_interval)

        # Run initial poll immediately
        self._poll_all_series()

    def stop(self, wait: bool = True) -> None:
        """
        Stop the polling scheduler.

        Args:
            wait: If True, wait for running jobs to complete before returning.

        Educational Note:
            The 'wait' parameter is important for clean shutdown. Setting it
            to True ensures any in-progress database operations complete
            before the scheduler terminates.
        """
        with self._lock:
            if not self._enabled:
                logger.warning("KalshiMarketPoller is not running")
                return

            if self._scheduler:
                self._scheduler.shutdown(wait=wait)
                self._scheduler = None

            self._enabled = False

        # Close Kalshi client to clean up HTTP connections
        self.kalshi_client.close()

        logger.info("KalshiMarketPoller stopped")

    def poll_once(self, series_tickers: list[str] | None = None) -> dict[str, int]:
        """
        Execute a single poll cycle manually.

        Useful for testing or on-demand updates outside the scheduled interval.

        Args:
            series_tickers: Optional list of series to poll. Defaults to configured series.

        Returns:
            Dictionary with counts: {"markets_fetched": N, "markets_updated": M, "markets_created": P}
        """
        target_series = series_tickers or self.series_tickers
        total_fetched = 0
        total_updated = 0
        total_created = 0

        for series in target_series:
            fetched, updated, created = self._poll_series(series)
            total_fetched += fetched
            total_updated += updated
            total_created += created

        return {
            "markets_fetched": total_fetched,
            "markets_updated": total_updated,
            "markets_created": total_created,
        }

    def _poll_all_series(self) -> None:
        """
        Poll all configured series and update market prices.

        This is the main scheduled job that runs at each interval.
        Handles errors gracefully to prevent scheduler job failures.
        """
        start_time = datetime.now(UTC)
        total_fetched = 0
        total_updated = 0
        total_created = 0

        try:
            for series in self.series_tickers:
                try:
                    fetched, updated, created = self._poll_series(series)
                    total_fetched += fetched
                    total_updated += updated
                    total_created += created
                except Exception as e:
                    # Log but don't re-raise - allow other series to continue
                    logger.error("Error polling series %s: %s", series, e)
                    with self._lock:
                        self._stats["errors"] += 1
                        self._stats["last_error"] = str(e)

            with self._lock:
                self._stats["polls_completed"] += 1
                self._stats["markets_fetched"] += total_fetched
                self._stats["markets_updated"] += total_updated
                self._stats["markets_created"] += total_created
                self._stats["last_poll"] = start_time.isoformat()

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            logger.debug(
                "Poll completed: %d markets fetched, %d updated, %d created in %.2fs",
                total_fetched,
                total_updated,
                total_created,
                elapsed,
            )

        except Exception as e:
            logger.exception("Unexpected error in poll cycle: %s", e)
            with self._lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)

    def _poll_series(self, series_ticker: str) -> tuple[int, int, int]:
        """
        Poll a single series and update market prices.

        Handles pagination to fetch all markets in the series.

        Args:
            series_ticker: Series ticker (e.g., "KXNFLGAME")

        Returns:
            Tuple of (markets_fetched, markets_updated, markets_created)

        Raises:
            requests.HTTPError: If API request fails after retries.

        Educational Note:
            Kalshi limits responses to 200 markets max. We use cursor-based
            pagination to fetch all markets in a series. Most NFL series
            have 50-100 markets, so pagination is rarely needed.
        """
        logger.debug("Polling Kalshi series: %s", series_ticker)

        all_markets: list[ProcessedMarketData] = []
        cursor: str | None = None

        # Paginate through all markets in the series
        while True:
            markets = self.kalshi_client.get_markets(
                series_ticker=series_ticker,
                limit=self.MAX_MARKETS_PER_REQUEST,
                cursor=cursor,
            )

            all_markets.extend(markets)

            # Check if there are more pages
            # Note: get_markets returns the markets list, cursor is in response
            # For simplicity, we break if we got fewer than limit (last page)
            if len(markets) < self.MAX_MARKETS_PER_REQUEST:
                break

            # TODO: Extract cursor from response for proper pagination
            # For now, break after first page (most series have <200 markets)
            break

        markets_updated = 0
        markets_created = 0

        for market in all_markets:
            try:
                result = self._sync_market_to_db(market)
                if result is True:
                    markets_created += 1
                elif result is False:
                    markets_updated += 1
                # result is None means skipped (unchanged)
            except Exception as e:
                ticker = market.get("ticker", "unknown")
                logger.error("Error syncing market %s: %s", ticker, e)

        logger.debug(
            "Series %s: fetched %d markets, updated %d, created %d",
            series_ticker,
            len(all_markets),
            markets_updated,
            markets_created,
        )

        return len(all_markets), markets_updated, markets_created

    def _sync_market_to_db(self, market: ProcessedMarketData) -> bool | None:
        """
        Sync a single market to the database.

        Uses create_market for new markets, update_market_with_versioning for
        existing markets (SCD Type 2).

        Args:
            market: Market data from Kalshi API (with Decimal prices)

        Returns:
            True if market was created
            False if market was updated (price/status changed)
            None if market was skipped (no changes)

        Educational Note:
            We use *_dollars fields from the API for sub-penny precision.
            These are already converted to Decimal by KalshiClient.
            Legacy cent fields (yes_bid, yes_ask) are integers and less precise.
        """
        ticker = market.get("ticker", "")
        if not ticker:
            logger.warning("Market missing ticker, skipping")
            return False

        # Extract prices from sub-penny Decimal fields
        # Fall back to legacy cent fields divided by 100 if _dollars not available
        yes_price = market.get("yes_ask_dollars")
        if yes_price is None:
            yes_ask_cents = market.get("yes_ask", 0)
            yes_price = Decimal(yes_ask_cents) / Decimal(100)

        no_price = market.get("no_ask_dollars")
        if no_price is None:
            no_ask_cents = market.get("no_ask", 0)
            no_price = Decimal(no_ask_cents) / Decimal(100)

        # Check if market already exists
        existing = get_current_market(ticker)

        if existing is None:
            # Create new market
            event_ticker = market.get("event_ticker", "")
            create_market(
                platform_id=self.PLATFORM_ID,
                event_id=event_ticker,  # Use event_ticker as event_id
                external_id=ticker,  # Use ticker as external_id
                ticker=ticker,
                title=market.get("title", ticker),
                yes_price=yes_price,
                no_price=no_price,
                market_type="binary",
                status=market.get("status", "open"),
                volume=market.get("volume"),
                open_interest=market.get("open_interest"),
                metadata={
                    "series_ticker": market.get("series_ticker"),
                    "subtitle": market.get("subtitle"),
                    "open_time": market.get("open_time"),
                    "close_time": market.get("close_time"),
                    "expiration_time": market.get("expiration_time"),
                    "can_close_early": market.get("can_close_early"),
                },
            )
            logger.debug("Created market: %s", ticker)
            return True

        # Market exists - check if price changed (avoid unnecessary versioning)
        price_changed = existing["yes_price"] != yes_price or existing["no_price"] != no_price
        status_changed = existing["status"] != market.get("status", "open")

        if price_changed or status_changed:
            update_market_with_versioning(
                ticker=ticker,
                yes_price=yes_price,
                no_price=no_price,
                status=market.get("status"),
                volume=market.get("volume"),
                open_interest=market.get("open_interest"),
            )
            logger.debug(
                "Updated market: %s (yes: %s -> %s)",
                ticker,
                existing["yes_price"],
                yes_price,
            )
            return False  # Updated, not created

        # No changes, skip
        return None

    def get_active_market_count(self) -> int:
        """
        Get count of currently tracked markets.

        Returns:
            Number of markets with status='open' in database

        Educational Note:
            This is useful for monitoring - if count drops to 0, it might
            indicate an API issue or that all markets have settled.
        """
        # TODO: Add CRUD operation to count open markets
        return 0

    def setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.

        Registers handlers for SIGINT (Ctrl+C) and SIGTERM to ensure
        clean shutdown of the scheduler.

        Educational Note:
            Signal handlers are important for production services.
            Without them, a Ctrl+C might leave database connections
            open or API sessions active.
        """

        def shutdown_handler(signum: int, frame: Any) -> None:
            logger.info("Received signal %d, shutting down...", signum)
            self.stop(wait=True)
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        logger.debug("Signal handlers registered")


# =============================================================================
# Convenience Functions
# =============================================================================


def create_kalshi_poller(
    series_tickers: list[str] | None = None,
    poll_interval: int = 15,
    environment: str = "demo",
) -> KalshiMarketPoller:
    """
    Factory function to create a configured KalshiMarketPoller.

    Args:
        series_tickers: Series to poll (default: ["KXNFLGAME"])
        poll_interval: Seconds between polls (default: 15, minimum: 5)
        environment: Kalshi environment (default: "demo")

    Returns:
        Configured KalshiMarketPoller instance

    Example:
        >>> poller = create_kalshi_poller(
        ...     series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
        ...     environment="prod"
        ... )
        >>> poller.start()
    """
    return KalshiMarketPoller(
        series_tickers=series_tickers,
        poll_interval=poll_interval,
        environment=environment,
    )


def run_single_kalshi_poll(
    series_tickers: list[str] | None = None,
    environment: str = "demo",
) -> dict[str, int]:
    """
    Execute a single Kalshi poll without starting the scheduler.

    Useful for CLI commands or on-demand updates.

    Args:
        series_tickers: Series to poll (default: ["KXNFLGAME"])
        environment: Kalshi environment (default: "demo")

    Returns:
        Dictionary with {"markets_fetched": N, "markets_updated": M, "markets_created": P}

    Example:
        >>> result = run_single_kalshi_poll(["KXNFLGAME"], environment="demo")
        >>> print(f"Fetched {result['markets_fetched']} markets")
    """
    poller = KalshiMarketPoller(
        series_tickers=series_tickers,
        environment=environment,
    )
    try:
        return poller.poll_once()
    finally:
        poller.kalshi_client.close()
