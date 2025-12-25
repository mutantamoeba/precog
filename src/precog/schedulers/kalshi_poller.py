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
from precog.api_connectors.types import ProcessedMarketData, SeriesData
from precog.database.crud_operations import (
    create_market,
    get_current_market,
    get_or_create_event,
    get_or_create_series,
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

    def sync_series(self, series_tickers: list[str] | None = None) -> dict[str, int]:
        """
        Sync series data from Kalshi API to database.

        This should be called before syncing markets to ensure series records
        exist in the database (required for foreign key relationships in events).

        Args:
            series_tickers: Optional list of specific series to sync.
                If None, fetches all sports series from the API.

        Returns:
            Dictionary with counts: {"series_fetched": N, "series_created": M, "series_updated": P}

        Educational Note:
            Kalshi's data hierarchy is: Series → Events → Markets
            - Series: Groups of related markets (e.g., "NFL Game Markets")
            - Events: Specific occurrences (e.g., "Chiefs vs Seahawks - Dec 22")
            - Markets: Tradeable outcomes (e.g., "Chiefs to win")

            We sync series first because:
            1. Events reference series (events.series_id → series.series_id)
            2. Markets reference events (markets.event_id → events.event_id)
            3. Without series records, FK constraints would fail

            The tags field is particularly valuable for sport filtering:
            - ["Football"] → NFL, NCAAF
            - ["Basketball"] → NBA, NCAAB, NCAAW
            - ["Hockey"] → NHL

        Reference:
            - Migration 0010: Added tags column with GIN index
            - src/precog/database/crud_operations.py (get_or_create_series)
        """
        logger.debug("Syncing series data from Kalshi API")

        series_fetched = 0
        series_created = 0
        series_updated = 0

        try:
            # Fetch series from API
            if series_tickers:
                # Fetch specific series by ticker
                api_series_list = []
                for ticker in series_tickers:
                    fetched_series = self.kalshi_client.get_series(limit=100)
                    # Filter to matching ticker
                    for s in fetched_series:
                        if s.get("ticker") == ticker:
                            api_series_list.append(s)
                            break
            else:
                # Fetch all sports series (using our configured sports)
                api_series_list = self.kalshi_client.get_sports_series()

            series_fetched = len(api_series_list)
            logger.debug("Fetched %d series from Kalshi API", series_fetched)

            # Sync each series to database
            for series_item in api_series_list:
                try:
                    result = self._sync_single_series(series_item)
                    if result is True:
                        series_created += 1
                    elif result is False:
                        series_updated += 1
                except Exception as e:
                    s_ticker = series_item.get("ticker", "unknown")
                    logger.error("Error syncing series %s: %s", s_ticker, e)

        except Exception as e:
            logger.error("Error fetching series from API: %s", e)

        logger.info(
            "Series sync complete: fetched=%d, created=%d, updated=%d",
            series_fetched,
            series_created,
            series_updated,
        )

        return {
            "series_fetched": series_fetched,
            "series_created": series_created,
            "series_updated": series_updated,
        }

    def _sync_single_series(self, series_data: SeriesData) -> bool | None:
        """
        Sync a single series to the database.

        Args:
            series_data: Series data from Kalshi API

        Returns:
            True if series was created
            False if series was updated
            None if series was skipped (no changes)

        Educational Note:
            The category mapping is important because Kalshi's API uses
            descriptive categories like "Sports" but our DB constraint
            requires lowercase values: 'sports', 'politics', etc.
        """
        ticker = series_data.get("ticker", "")
        if not ticker:
            logger.warning("Series missing ticker, skipping")
            return None

        # Map Kalshi category to database category (lowercase)
        api_category = series_data.get("category", "other")
        db_category = api_category.lower() if api_category else "other"

        # Ensure category matches DB constraint
        valid_categories = {"sports", "politics", "entertainment", "economics", "weather", "other"}
        if db_category not in valid_categories:
            db_category = "other"

        # Extract tags (important for sport filtering)
        tags = series_data.get("tags", [])

        # Determine subcategory from tags or ticker
        subcategory = None
        if tags:
            if "Football" in tags:
                if "NFL" in ticker.upper():
                    subcategory = "nfl"
                elif "NCAAF" in ticker.upper():
                    subcategory = "ncaaf"
            elif "Basketball" in tags:
                if "NBA" in ticker.upper():
                    subcategory = "nba"
                elif "NCAAB" in ticker.upper():
                    subcategory = "ncaab"
                elif "NCAAW" in ticker.upper():
                    subcategory = "ncaaw"
            elif "Hockey" in tags:
                subcategory = "nhl"

        # Use get_or_create_series with update_if_exists=True to keep data fresh
        _, created = get_or_create_series(
            series_id=ticker,
            platform_id=self.PLATFORM_ID,
            external_id=ticker,
            category=db_category,
            title=series_data.get("title", ticker),
            subcategory=subcategory,
            frequency=series_data.get("frequency"),
            tags=tags if tags else None,
            metadata={
                "settlement_sources": series_data.get("settlement_sources"),
                "contract_terms_url": series_data.get("contract_terms_url"),
            },
            update_if_exists=True,
        )

        if created:
            logger.debug("Created series: %s", ticker)
            return True
        logger.debug("Updated series: %s", ticker)
        return False

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
                # Pass series_ticker explicitly - the API response may not include it
                result = self._sync_market_to_db(market, series_ticker=series_ticker)
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

    def _sync_market_to_db(
        self, market: ProcessedMarketData, series_ticker: str = ""
    ) -> bool | None:
        """
        Sync a single market to the database.

        Uses create_market for new markets, update_market_with_versioning for
        existing markets (SCD Type 2).

        Args:
            market: Market data from Kalshi API (with Decimal prices)
            series_ticker: Series ticker (e.g., "KXNFLGAME") - must be passed
                explicitly because the Kalshi API response doesn't include it
                in the market object (it's only a filter parameter).

        Returns:
            True if market was created
            False if market was updated (price/status changed)
            None if market was skipped (no changes)

        Educational Note:
            We use *_dollars fields from the API for sub-penny precision.
            These are already converted to Decimal by KalshiClient.
            Legacy cent fields (yes_bid, yes_ask) are integers and less precise.

            The series_ticker must be passed explicitly because:
            - Kalshi API accepts series_ticker as a query filter parameter
            - But the market objects in the response don't include series_ticker
            - So market.get("series_ticker") would return empty string
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
            # Use the passed series_ticker parameter, fall back to market dict if available
            effective_series = series_ticker or market.get("series_ticker", "")

            # Determine category from series ticker (e.g., KXNFLGAME -> sports/nfl)
            # Default to 'sports' for game-related series, 'other' for unknown
            category = "sports"  # Most Kalshi markets we poll are sports
            subcategory = None
            if "NFL" in effective_series.upper():
                subcategory = "nfl"
            elif "NCAAF" in effective_series.upper():
                subcategory = "ncaaf"
            elif "NBA" in effective_series.upper():
                subcategory = "nba"
            elif "NHL" in effective_series.upper():
                subcategory = "nhl"
            elif "MLB" in effective_series.upper():
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
                    series_id=effective_series,  # Link event to its series (e.g., KXNFLGAME)
                    subcategory=subcategory,
                    metadata={
                        "series_ticker": effective_series,
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
                    "series_ticker": effective_series,
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
