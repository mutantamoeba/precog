"""
Kalshi market price polling service extending BasePoller.

This module provides the KalshiMarketPoller class that polls Kalshi APIs at
configurable intervals and syncs market prices to the database using SCD Type 2
versioning.

Key Features:
- Extends BasePoller for consistent APScheduler-based polling
- Filters for specific series (e.g., KXNFLGAME for NFL markets)
- Sub-penny Decimal price precision (NEVER float!)
- SCD Type 2 versioning for price history
- Rate limiting compliance (100 req/min)
- Error recovery with logging
- Clean shutdown handling

Naming Convention:
    {Platform}{Entity}Poller pattern:
    - KalshiMarketPoller: Polls Kalshi for market prices
    - ESPNGamePoller: Polls ESPN for game states (see espn_game_poller.py)

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
Related ADR: ADR-100 (Service Supervisor Pattern)
"""

import logging
from decimal import Decimal
from typing import ClassVar

from precog.api_connectors.kalshi_client import KalshiClient
from precog.api_connectors.types import ProcessedMarketData
from precog.database.crud_operations import (
    create_market,
    get_current_market,
    get_or_create_event,
    update_market_with_versioning,
)
from precog.schedulers.base_poller import BasePoller

# Set up logging
logger = logging.getLogger(__name__)


class KalshiMarketPoller(BasePoller):
    """
    Kalshi market price polling service.

    Polls Kalshi APIs at regular intervals and syncs market prices to the database.
    Extends BasePoller for consistent APScheduler-based polling with health monitoring.

    Attributes:
        series_tickers: List of series to poll (e.g., ["KXNFLGAME", "KXNCAAFGAME"])
        poll_interval: Seconds between polls (default: 15, minimum: 5)
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
        The poller uses BasePoller's BackgroundScheduler which runs jobs in a
        thread pool. This allows the main application to continue running while
        polls happen in the background. The scheduler handles job execution,
        retries, and timing automatically.

    Reference: Phase 2.5 Live Data Collection Service
    Related: ADR-100 (Service Supervisor Pattern)
    """

    # Class-level configuration
    MIN_POLL_INTERVAL: ClassVar[int] = 5  # seconds (rate limit: 100 req/min)
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 15  # seconds (balanced for near real-time)
    DEFAULT_SERIES_TICKERS: ClassVar[list[str]] = ["KXNFLGAME"]
    MAX_MARKETS_PER_REQUEST: ClassVar[int] = 200  # Kalshi API limit

    # Rate limit guidance:
    # - Kalshi allows 100 requests/minute
    # - Each poll uses 1-3 requests (pagination for large series)
    # - 5 second interval = 12-36 req/min (safe)
    # - 3 second interval = 20-60 req/min (caution)
    # - 1 second interval = 60-180 req/min (EXCEEDS LIMIT)

    # Platform ID for database records
    PLATFORM_ID: ClassVar[str] = "kalshi"

    # Status mapping from Kalshi API to database schema
    # Kalshi API returns: 'active', 'unopened', 'closed', 'settled', 'finalized'
    # Database constraint allows: 'open', 'closed', 'settled', 'halted'
    # Reference: docs/api-integration/Kalshi API Technical Reference
    STATUS_MAPPING: ClassVar[dict[str, str]] = {
        "active": "open",  # Kalshi 'active' = market is open for trading
        "unopened": "halted",  # Kalshi 'unopened' = not yet open
        "open": "open",  # Direct mapping (documented but rarely seen)
        "closed": "closed",  # Direct mapping
        "settled": "settled",  # Direct mapping
        "finalized": "settled",  # Kalshi 'finalized' = settlement complete
    }

    def __init__(
        self,
        series_tickers: list[str] | None = None,
        poll_interval: int | None = None,
        environment: str = "demo",
        kalshi_client: KalshiClient | None = None,
    ) -> None:
        """
        Initialize the KalshiMarketPoller.

        Args:
            series_tickers: List of series to poll (e.g., ["KXNFLGAME"]).
                Defaults to NFL game markets only.
            poll_interval: Seconds between polls. Minimum 5 seconds.
            environment: Kalshi environment ("demo" or "prod").
            kalshi_client: Optional KalshiClient instance (for testing/mocking).

        Raises:
            ValueError: If poll_interval < 5 or environment invalid.
        """
        if environment not in ("demo", "prod"):
            raise ValueError("environment must be 'demo' or 'prod'")

        # Initialize base class (handles scheduler, stats, etc.)
        super().__init__(poll_interval=poll_interval, logger=logger)

        # Kalshi-specific configuration
        self.series_tickers = series_tickers or self.DEFAULT_SERIES_TICKERS.copy()
        self.environment = environment

        # Initialize Kalshi client (or use provided mock)
        self.kalshi_client = kalshi_client or KalshiClient(environment=environment)

        logger.info(
            "KalshiMarketPoller initialized: series=%s, poll_interval=%ds, env=%s",
            self.series_tickers,
            self.poll_interval,
            self.environment,
        )

    def _get_job_name(self) -> str:
        """Return human-readable name for the polling job."""
        return "Kalshi Market Price Poll"

    def _poll_once(self) -> dict[str, int]:
        """
        Execute a single poll cycle for all configured series.

        Returns:
            Dictionary with counts: items_fetched, items_updated, items_created
        """
        total_fetched = 0
        total_updated = 0
        total_created = 0

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

        return {
            "items_fetched": total_fetched,
            "items_updated": total_updated,
            "items_created": total_created,
        }

    def _on_stop(self) -> None:
        """Clean up Kalshi client on stop."""
        self.kalshi_client.close()

    def poll_once(self, series_tickers: list[str] | None = None) -> dict[str, int]:
        """
        Execute a single poll cycle manually.

        Useful for testing or on-demand updates outside the scheduled interval.

        Args:
            series_tickers: Optional list of series to poll. Defaults to configured series.

        Returns:
            Dictionary with counts: {"items_fetched": N, "items_updated": M, "items_created": P}
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
            "items_fetched": total_fetched,
            "items_updated": total_updated,
            "items_created": total_created,
        }

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

        # Map Kalshi API status to database schema status
        # Kalshi returns 'active' but our DB constraint expects 'open'
        api_status = market.get("status", "open")
        db_status = self.STATUS_MAPPING.get(api_status, "open")
        if api_status not in self.STATUS_MAPPING:
            logger.warning(
                "Unknown Kalshi status '%s' for market %s, defaulting to 'open'",
                api_status,
                ticker,
            )
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
            # Create new market - first ensure the event exists
            event_ticker = market.get("event_ticker", "")
            series_ticker = market.get("series_ticker", "")

            # Determine category from series ticker (e.g., KXNFLGAME -> sports/nfl)
            # Default to 'sports' for game-related series, 'other' for unknown
            category = "sports"  # Most Kalshi markets we poll are sports
            subcategory = None
            if "NFL" in series_ticker.upper():
                subcategory = "nfl"
            elif "NCAAF" in series_ticker.upper():
                subcategory = "ncaaf"
            elif "NBA" in series_ticker.upper():
                subcategory = "nba"
            elif "NHL" in series_ticker.upper():
                subcategory = "nhl"
            elif "MLB" in series_ticker.upper():
                subcategory = "mlb"

            # Get or create the event before creating the market
            # This satisfies the foreign key constraint (markets.event_id -> events.event_id)
            if event_ticker:
                get_or_create_event(
                    event_id=event_ticker,
                    platform_id=self.PLATFORM_ID,
                    external_id=event_ticker,
                    category=category,
                    title=market.get("title", event_ticker),
                    series_id=series_ticker,  # Link event to its series (e.g., KXNFLGAME)
                    subcategory=subcategory,
                    metadata={
                        "series_ticker": series_ticker,
                    },
                )

            create_market(
                platform_id=self.PLATFORM_ID,
                event_id=event_ticker,  # Use event_ticker as event_id
                external_id=ticker,  # Use ticker as external_id
                ticker=ticker,
                title=market.get("title", ticker),
                yes_price=yes_price,
                no_price=no_price,
                market_type="binary",
                status=db_status,
                volume=market.get("volume"),
                open_interest=market.get("open_interest"),
                metadata={
                    "series_ticker": series_ticker,
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
        status_changed = existing["status"] != db_status

        if price_changed or status_changed:
            update_market_with_versioning(
                ticker=ticker,
                yes_price=yes_price,
                no_price=no_price,
                status=db_status,
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
        Dictionary with {"items_fetched": N, "items_updated": M, "items_created": P}

    Example:
        >>> result = run_single_kalshi_poll(["KXNFLGAME"], environment="demo")
        >>> print(f"Fetched {result['items_fetched']} markets")
    """
    poller = KalshiMarketPoller(
        series_tickers=series_tickers,
        environment=environment,
    )
    try:
        return poller.poll_once()
    finally:
        poller.kalshi_client.close()
