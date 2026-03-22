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
- Rate limiting compliance (Kalshi Basic tier: 20 req/sec)
- Error recovery with logging
- Clean shutdown handling

Naming Convention:
    {Platform}{Entity}Poller pattern:
    - KalshiMarketPoller: Polls Kalshi for market prices
    - ESPNGamePoller: Polls ESPN for game states (see espn_game_poller.py)

Educational Notes:
------------------
Polling Frequency Considerations:
    - Kalshi Basic tier: 20 requests/second (1,200 req/min)
    - Reference: https://docs.kalshi.com/getting_started/rate_limits
    - fetch_all_markets() handles pagination internally (~25 requests per poll)
    - 15-second intervals with 4 series uses ~120 req/min (well under 1,200 limit)
    - Rate limiter (token bucket) enforces compliance automatically

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
from typing import Any, ClassVar, cast

from precog.api_connectors.kalshi_client import KalshiClient
from precog.api_connectors.types import ProcessedMarketData, SeriesData
from precog.database.crud_operations import (
    count_open_markets,
    create_alert,
    create_market,
    get_current_market,
    get_or_create_event,
    get_or_create_series,
    update_market_with_versioning,
)
from precog.schedulers.base_poller import BasePoller
from precog.validation.kalshi_validation import KalshiDataValidator

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
    MIN_POLL_INTERVAL: ClassVar[int] = 5  # seconds
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 15  # seconds (balanced for near real-time)
    DEFAULT_SERIES_TICKERS: ClassVar[list[str]] = [
        "KXNFLGAME",
        "KXNCAAFGAME",
        "KXNBAGAME",
        "KXNHLGAME",
    ]
    # Note: pagination is handled internally by fetch_all_markets()

    # Rate limit guidance (Kalshi Basic tier: 20 req/sec = 1,200 req/min):
    # - Each poll uses ~30 requests (series sync + pagination across 4 series)
    # - 15 second interval = ~120 req/min (10% of limit, very safe)
    # - 5 second interval = ~300 req/min (25% of limit, safe)
    # - Token bucket rate limiter enforces compliance automatically
    # - Reference: https://docs.kalshi.com/getting_started/rate_limits

    # Heartbeat logging: every N quiet polls, emit INFO instead of DEBUG
    # At 15s intervals, N=20 means a heartbeat every ~5 minutes
    HEARTBEAT_EVERY_N: ClassVar[int] = 20

    # Validation error rate thresholds for log-level escalation.
    # Below WARN: summary at INFO. Above WARN: summary at WARNING.
    # Above ERROR: summary at ERROR + alert written to DB.
    # NOTE: float is intentional here -- these are ratios of integer counts,
    # not prices, probabilities, or money values. Decimal not required.
    VALIDATION_WARN_RATE: ClassVar[float] = 0.10  # 10% error rate
    VALIDATION_ERROR_RATE: ClassVar[float] = 0.25  # 25% error rate

    # Platform ID for database records
    PLATFORM_ID: ClassVar[str] = "kalshi"

    # Status mapping from Kalshi API to database schema
    # Kalshi API returns: 'active', 'unopened', 'closed', 'settled', 'finalized', 'determined', 'initialized'
    # Database constraint allows: 'open', 'closed', 'settled', 'halted'
    # Reference: docs/api-integration/Kalshi API Technical Reference
    STATUS_MAPPING: ClassVar[dict[str, str]] = {
        "active": "open",  # Kalshi 'active' = market is open for trading
        "unopened": "halted",  # Kalshi 'unopened' = not yet open
        "open": "open",  # Direct mapping (documented but rarely seen)
        "closed": "closed",  # Direct mapping
        "settled": "settled",  # Direct mapping
        "finalized": "settled",  # Kalshi 'finalized' = settlement complete
        "determined": "closed",  # Kalshi 'determined' = outcome decided, awaiting settlement
        "initialized": "halted",  # Kalshi 'initialized' = market created, not yet open for trading
        "inactive": "closed",  # Kalshi 'inactive' = market no longer active (delisted or post-event)
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

        # Consecutive polls with no changes (for heartbeat logging)
        self._silent_poll_count: int = 0

        # Initialize Kalshi client (or use provided mock)
        self.kalshi_client = kalshi_client or KalshiClient(environment=environment)

        # Initialize data validator (instance-level, NOT module-level singleton,
        # because _anomaly_counts is stateful per-poller)
        self._validator = KalshiDataValidator()

        # Mapping of series ticker -> integer surrogate PK from series table.
        # Populated by sync_series(), consumed by _sync_market_to_db() when
        # creating events (events.series_internal_id FK).
        # See migration 0019: series now uses SERIAL PK instead of VARCHAR PK.
        self._series_id_map: dict[str, int] = {}

        # Mapping of event ticker -> integer surrogate PK from events table.
        # Populated by _sync_market_to_db() via get_or_create_event(), consumed
        # when creating markets (markets.event_internal_id FK).
        # See migration 0020: events now uses SERIAL PK instead of VARCHAR PK.
        self._event_id_map: dict[str, int] = {}

        # Validation stats tracked separately from PollerStats TypedDict
        # to avoid type contract violations. Merged in get_stats().
        # Includes both cumulative totals and per-cycle snapshots.
        self._validation_stats: dict[str, int | float] = {
            "validation_errors": 0,
            "validation_warnings": 0,
            # Per-cycle snapshots (Uhura recommendation: make stats interpretable)
            "validation_errors_last_cycle": 0,
            "validation_warnings_last_cycle": 0,
            "markets_checked_last_cycle": 0,
            "error_rate_pct_last_cycle": 0.0,
        }

        logger.info(
            "KalshiMarketPoller initialized: series=%s, poll_interval=%ds, env=%s",
            self.series_tickers,
            self.poll_interval,
            self.environment,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get stats including validation counters."""
        with self._lock:
            stats = dict(self._stats)
            stats.update(self._validation_stats)
            return stats

    def _get_job_name(self) -> str:
        """Return human-readable name for the polling job."""
        return "Kalshi Market Price Poll"

    def _poll_once(self) -> dict[str, int]:
        """
        Execute a single poll cycle for all configured series.

        Syncs series metadata first (required for FK constraints), then
        polls each series for market data.

        Returns:
            Dictionary with counts: items_fetched, items_updated, items_created

        Educational Note:
            Series records must exist in the database before events/markets
            can reference them via foreign keys. The sync_series() call
            ensures this prerequisite is met before any market sync attempts.
        """
        # Ensure series records exist before syncing markets (FK requirement)
        self.sync_series()

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

        # Heartbeat logging for operator visibility during quiet periods.
        # BasePoller._poll_wrapper() handles the standard INFO/DEBUG logging
        # for change/no-change polls, so we only manage the counter and
        # emit the heartbeat here to avoid double-logging.
        if total_updated or total_created:
            self._silent_poll_count = 0
        else:
            self._silent_poll_count += 1
            if self._silent_poll_count >= self.HEARTBEAT_EVERY_N:
                logger.info(
                    "Kalshi heartbeat: %d quiet polls across %d series (%d markets tracked)",
                    self._silent_poll_count,
                    len(self.series_tickers),
                    self.get_active_market_count(),
                )
                self._silent_poll_count = 0

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
            1. Events reference series (events.series_internal_id -> series.id)
            2. Markets reference events (markets.event_internal_id -> events.id)
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
                # Fetch all Sports series and filter to our target tickers.
                # Uses fetch_all_series() with cursor-chasing to ensure we get
                # every series without client-side truncation.
                all_sports = self.kalshi_client.fetch_all_series(category="Sports")
                target_set = set(series_tickers)
                api_series_list = [s for s in all_sports if s.get("ticker") in target_set]

                # For any tickers not found via API, create minimal series records
                # to satisfy FK constraints. This handles series that may be in a
                # different category or beyond pagination limits.
                found_tickers = {s.get("ticker") for s in api_series_list}
                for ticker in series_tickers:
                    if ticker not in found_tickers:
                        logger.info(
                            "Series %s not found in API listing, creating minimal record",
                            ticker,
                        )
                        api_series_list.append(
                            {
                                "ticker": ticker,
                                "title": ticker,
                                "category": "Sports",
                                "tags": [],
                            }
                        )
            else:
                # Fetch all sports series (using our configured sports)
                api_series_list = self.kalshi_client.get_sports_series()

            series_fetched = len(api_series_list)
            logger.debug("Fetched %d series from Kalshi API", series_fetched)

            # If API returned empty results, create fallback records from configured
            # series tickers to prevent FK constraint failures downstream
            if not api_series_list and self.series_tickers:
                logger.warning(
                    "API returned 0 series; creating fallback records for %d configured tickers",
                    len(self.series_tickers),
                )
                for ticker in self.series_tickers:
                    api_series_list.append(
                        {
                            "ticker": ticker,
                            "title": ticker,
                            "category": "Sports",
                            "tags": [],
                        }
                    )

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
            # Fallback: create minimal series records so FK constraints don't block
            # market sync. This ensures pollers work even when the API is unreachable.
            fallback_tickers = series_tickers or self.series_tickers
            if fallback_tickers:
                logger.warning(
                    "Creating fallback series records for %d tickers after API error",
                    len(fallback_tickers),
                )
                for ticker in fallback_tickers:
                    try:
                        self._sync_single_series(
                            {"ticker": ticker, "title": ticker, "category": "Sports", "tags": []}
                        )
                        series_created += 1
                    except Exception as fallback_err:
                        logger.error(
                            "Failed to create fallback series %s: %s", ticker, fallback_err
                        )

        # Demote to DEBUG when no series were created (steady-state)
        log_fn = logger.info if series_created else logger.debug
        log_fn(
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

        Side Effects:
            Updates self._series_id_map with ticker -> integer surrogate PK
            mapping for downstream use by _sync_market_to_db().

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

        # Use get_or_create_series with update_if_exists=True to keep data fresh.
        # Returns (integer_pk, created) — the integer PK is stored in
        # _series_id_map for downstream event creation (events.series_internal_id).
        series_pk, created = get_or_create_series(
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

        # Cache the ticker -> integer PK mapping for _sync_market_to_db
        self._series_id_map[ticker] = series_pk

        if created:
            logger.debug("Created series: %s (id=%d)", ticker, series_pk)
            return True
        logger.debug("Updated series: %s (id=%d)", ticker, series_pk)
        return False

    def poll_once(self, series_tickers: list[str] | None = None) -> dict[str, int]:
        """
        Execute a single poll cycle manually.

        Useful for testing or on-demand updates outside the scheduled interval.
        Syncs series metadata first to satisfy FK constraints.

        Args:
            series_tickers: Optional list of series to poll. Defaults to configured series.

        Returns:
            Dictionary with counts: {"items_fetched": N, "items_updated": M, "items_created": P}
        """
        target_series = series_tickers or self.series_tickers

        # Ensure series records exist before syncing markets (FK requirement)
        self.sync_series(target_series)

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
            Kalshi limits responses to 200 markets per page. We use
            fetch_all_markets() which handles cursor-based pagination
            internally, ensuring ALL markets are fetched regardless of
            how many pages exist.
        """
        logger.debug("Polling Kalshi series: %s", series_ticker)

        # Use fetch_all_markets() for guaranteed full pagination.
        # This handles cursor-chasing internally, returning ALL markets
        # regardless of how many pages exist.
        all_markets = self.kalshi_client.fetch_all_markets(
            series_tickers=[series_ticker],
        )

        # Validate fetched market data (soft validation — log issues, never block ingestion).
        # Runs on raw API data before any DB mapping or filtering.
        # Wrapped in try/except: a validator bug must NEVER prevent market syncing.
        try:
            validation_results = self._validator.validate_markets(
                cast("list[dict[str, Any]]", all_markets)
            )
            error_count = sum(1 for r in validation_results if r.has_errors)
            warning_count = sum(
                1 for r in validation_results if r.has_warnings and not r.has_errors
            )
            valid_count = len(all_markets) - error_count

            # Log individual issues with anomaly deduplication.
            # Errors always log. Warnings use threshold-based dedup
            # (1st, 10th, 100th occurrence) to prevent log flooding
            # from markets that repeatedly fail the same check.
            for vr in validation_results:
                if vr.has_errors:
                    vr.log_issues(logger)
                elif vr.has_warnings and self._validator.should_log_anomaly(vr.entity_id):
                    count = self._validator.get_anomaly_count(vr.entity_id)
                    for issue in vr.issues:
                        logger.debug(
                            "[%s:%s] (occurrence #%d) %s",
                            vr.entity_type,
                            vr.entity_id,
                            count,
                            issue,
                        )

            # Error rate escalation: escalate log level + write alert when
            # validation error rate exceeds thresholds.
            total_checked = len(all_markets)
            error_rate = error_count / total_checked if total_checked > 0 else 0.0

            if error_rate >= self.VALIDATION_ERROR_RATE:
                # Critical: >25% error rate — log ERROR + persist alert to DB
                logger.error(
                    "Validation [%s]: ERROR RATE %.1f%% - %d/%d markets failed "
                    "(%d errors, %d warnings) [ACTION: investigate data source]",
                    series_ticker,
                    error_rate * 100,
                    error_count,
                    total_checked,
                    error_count,
                    warning_count,
                )
                try:
                    create_alert(
                        alert_type="validation_error_rate",
                        severity="error",
                        message=(
                            f"Error rate {error_rate * 100:.1f}% exceeds "
                            f"{self.VALIDATION_ERROR_RATE * 100:.0f}% threshold "
                            f"({error_count}/{total_checked} markets)"
                        ),
                        source=f"kalshi_poller:{series_ticker}",
                    )
                except Exception as alert_err:
                    logger.debug("Failed to write alert to DB: %s", alert_err)
            elif error_rate >= self.VALIDATION_WARN_RATE:
                # Elevated: >10% error rate — log WARNING
                logger.warning(
                    "Validation [%s]: error rate %.1f%% - %d/%d markets failed "
                    "(%d errors, %d warnings)",
                    series_ticker,
                    error_rate * 100,
                    error_count,
                    total_checked,
                    error_count,
                    warning_count,
                )
            elif error_count or warning_count:
                # Normal issues: INFO summary
                logger.info(
                    "Validation [%s]: %d markets checked, %d valid, %d errors, %d warnings",
                    series_ticker,
                    total_checked,
                    valid_count,
                    error_count,
                    warning_count,
                )
            else:
                # All clean: DEBUG
                logger.debug(
                    "Validation [%s]: %d markets checked, all valid",
                    series_ticker,
                    total_checked,
                )

            # Track validation stats (separate dict, merged in get_stats)
            with self._lock:
                # Cumulative totals
                self._validation_stats["validation_errors"] += error_count
                self._validation_stats["validation_warnings"] += warning_count
                # Per-cycle snapshots (overwritten each cycle)
                self._validation_stats["validation_errors_last_cycle"] = error_count
                self._validation_stats["validation_warnings_last_cycle"] = warning_count
                self._validation_stats["markets_checked_last_cycle"] = total_checked
                self._validation_stats["error_rate_pct_last_cycle"] = round(error_rate * 100, 1)
        except Exception as e:
            logger.error(
                "Validation failed for series %s (ingestion continues): %s",
                series_ticker,
                e,
            )

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

        # Demote to DEBUG when nothing changed (steady-state)
        log_fn = logger.info if (markets_updated or markets_created) else logger.debug
        log_fn(
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
        db_status = self.STATUS_MAPPING.get(api_status, "halted")
        if api_status not in self.STATUS_MAPPING:
            logger.warning(
                "Unknown Kalshi status '%s' for market %s, defaulting to 'halted'",
                api_status,
                ticker,
            )
        if not ticker:
            logger.warning("Market missing ticker, skipping")
            return False

        # Extract prices from sub-penny Decimal fields
        # Fall back to legacy cent fields divided by 100 if _dollars not available
        #
        # yes_price = Kalshi YES ask price (cost to buy YES contract, NOT implied probability)
        # no_price = Kalshi NO ask price (cost to buy NO contract, NOT implied probability)
        # Note: yes_price + no_price > 1.0 is normal (ask prices include the spread).
        # At settlement, both yes_price and no_price can reach 1.0 (Pattern 37).
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

            # Get or create the event before creating the market.
            # This satisfies the FK constraint (markets.event_internal_id -> events.id).
            # get_or_create_event() returns (int_pk, created) per migration 0020.
            event_pk: int | None = None
            if event_ticker:
                # Check cache first to avoid redundant DB lookups
                if event_ticker in self._event_id_map:
                    event_pk = self._event_id_map[event_ticker]
                else:
                    # Look up integer surrogate PK for the series. The mapping is
                    # populated by sync_series() which runs before market polling.
                    series_pk = self._series_id_map.get(effective_series)
                    if effective_series and series_pk is None:
                        logger.warning(
                            "Series '%s' not in _series_id_map for event %s -- "
                            "event will have NULL series_internal_id",
                            effective_series,
                            event_ticker,
                        )

                    event_pk, _created = get_or_create_event(
                        event_id=event_ticker,
                        platform_id=self.PLATFORM_ID,
                        external_id=event_ticker,
                        category=category,
                        title=market.get("title", event_ticker),
                        series_internal_id=series_pk,  # Integer FK to series(id)
                        subcategory=subcategory,
                        metadata={
                            "series_ticker": effective_series,
                        },
                    )
                    # Cache the integer PK for subsequent markets in the same event
                    self._event_id_map[event_ticker] = event_pk

            # Migration 0022: create_market returns int PK
            # Migration 0033: subtitle, open_time, close_time, expiration_time
            # promoted from metadata JSONB to proper dimension columns.
            # can_close_early and series_ticker remain in metadata.
            create_market(
                platform_id=self.PLATFORM_ID,
                event_internal_id=event_pk,  # Integer FK to events(id)
                external_id=ticker,  # Use ticker as external_id
                ticker=ticker,
                title=market.get("title", ticker),
                yes_ask_price=yes_price,
                no_ask_price=no_price,
                market_type="binary",
                status=db_status,
                volume=market.get("volume"),
                open_interest=market.get("open_interest"),
                subtitle=market.get("subtitle"),
                open_time=market.get("open_time"),
                close_time=market.get("close_time"),
                expiration_time=market.get("expiration_time"),
                metadata={
                    k: v
                    for k, v in {
                        "series_ticker": effective_series,
                        "can_close_early": market.get("can_close_early"),
                    }.items()
                    if v is not None
                },
            )
            logger.debug("Created market: %s", ticker)
            return True

        # Market exists - check if price changed (avoid unnecessary versioning)
        # Migration 0021: column renamed from yes_price → yes_ask_price
        price_changed = (
            existing["yes_ask_price"] != yes_price or existing["no_ask_price"] != no_price
        )
        status_changed = existing["status"] != db_status

        if price_changed or status_changed:
            # Migration 0033: pass enrichment columns on update path too,
            # so lifecycle timestamps are refreshed when prices change.
            update_market_with_versioning(
                ticker=ticker,
                yes_ask_price=yes_price,
                no_ask_price=no_price,
                status=db_status,
                volume=market.get("volume"),
                open_interest=market.get("open_interest"),
                subtitle=market.get("subtitle"),
                open_time=market.get("open_time"),
                close_time=market.get("close_time"),
                expiration_time=market.get("expiration_time"),
            )
            logger.debug(
                "Updated market: %s (yes: %s -> %s)",
                ticker,
                existing["yes_ask_price"],
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
        try:
            return count_open_markets()
        except Exception as e:
            logger.error("Failed to get active market count: %s", e)
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
