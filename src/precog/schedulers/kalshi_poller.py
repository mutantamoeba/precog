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
    update_bracket_counts,
    update_event_game_id,
    update_market_with_versioning,
)
from precog.matching.event_game_matcher import EventGameMatcher
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

    # Service registry metadata (read by ServiceSupervisor at registration)
    SERVICE_KEY: ClassVar[str] = "kalshi_rest"
    HEALTH_COMPONENT: ClassVar[str] = "kalshi_api"
    BREAKER_TYPE: ClassVar[str] = "api_failures"

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

    # Registry refresh: at most once every N polls (at 15s interval,
    # 40 polls = ~10 minutes). Prevents excessive DB queries on every
    # unknown code encounter.
    REGISTRY_REFRESH_INTERVAL: ClassVar[int] = 40

    # Validation frequency: run full market validation every N polls.
    # At 15s interval, 10 polls = ~2.5 minutes. Validation checks all
    # markets per series (~7K+) so running every cycle is wasteful.
    VALIDATION_INTERVAL: ClassVar[int] = 10

    # Backfill frequency: run matching backfill every N polls.
    # At 15s interval, 40 polls = ~10 minutes. Backfill scans all
    # unlinked events so running every cycle is wasteful.
    BACKFILL_INTERVAL: ClassVar[int] = 40

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

        # Event-to-game matcher (Issue #462). Matches Kalshi events to ESPN
        # games by parsing team codes from event tickers. The registry is
        # loaded lazily on first poll cycle to avoid startup DB dependency.
        self._event_game_matcher: EventGameMatcher | None = None
        self._matcher_loaded: bool = False

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

        # Matching stats: track how well event-to-game linking is performing.
        # Cumulative counts reset only on poller restart.
        self._matching_stats: dict[str, int] = {
            "matching_matched": 0,
            "matching_parse_fail": 0,
            "matching_no_code": 0,
            "matching_no_game": 0,
            "matching_backfill_linked": 0,
            "matching_backfill_runs": 0,
            "matching_backfill_errors": 0,
            "matching_registry_refreshes": 0,
        }

        # Rate-limit registry refresh: track poll count since last refresh.
        # Refresh at most once every REGISTRY_REFRESH_INTERVAL polls.
        # Thread safety: all three counters are only accessed from _poll_once()
        # thread (APScheduler max_instances=1 guarantees no concurrent execution).
        self._polls_since_registry_refresh: int = 0
        self._polls_since_validation: int = self.VALIDATION_INTERVAL  # Run on first poll
        self._polls_since_backfill: int = 0
        self._should_validate: bool = False  # Set per-cycle in _poll_once

        logger.info(
            "KalshiMarketPoller initialized: series=%s, poll_interval=%ds, env=%s",
            self.series_tickers,
            self.poll_interval,
            self.environment,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get stats including validation and matching counters."""
        with self._lock:
            stats = dict(self._stats)
            stats.update(self._validation_stats)
            stats.update(self._matching_stats)
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

        # Determine which periodic tasks should run this cycle.
        # Counters are incremented here; checked in _poll_series (validation)
        # and below (backfill). Both reset to 0 when they fire.
        self._polls_since_validation += 1
        self._should_validate = self._polls_since_validation >= self.VALIDATION_INTERVAL
        if self._should_validate:
            self._polls_since_validation = 0

        self._polls_since_backfill += 1

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

        # Post-poll batch: recompute bracket_count for all markets.
        # bracket_count = number of markets sharing the same parent event.
        # Only rows where the value actually changed are written.
        try:
            bracket_updated = update_bracket_counts()
            if bracket_updated:
                logger.debug("Updated bracket_count for %d markets", bracket_updated)
        except Exception as e:
            logger.warning("Failed to update bracket counts: %s", e)

        # Post-poll batch: attempt to link unmatched events to games.
        # Rate-limited: only runs every BACKFILL_INTERVAL polls (~10 min).
        # Non-blocking: errors are logged but never stop polling.
        if self._polls_since_backfill >= self.BACKFILL_INTERVAL:
            self._polls_since_backfill = 0
            self._run_matching_backfill()

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
                k: v
                for k, v in {
                    "settlement_sources": series_data.get("settlement_sources"),
                    "contract_terms_url": series_data.get("contract_terms_url"),
                    "expected_expiration_time": series_data.get("expected_expiration_time"),
                    "settlement_timer_seconds": series_data.get("settlement_timer_seconds"),
                }.items()
                if v is not None
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

        # Post-poll batch: recompute bracket_count for all markets.
        try:
            bracket_updated = update_bracket_counts()
            if bracket_updated:
                logger.debug("Updated bracket_count for %d markets", bracket_updated)
        except Exception as e:
            logger.warning("Failed to update bracket counts: %s", e)

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
        # Rate-limited via self._should_validate (set in _poll_once every VALIDATION_INTERVAL polls).
        # Wrapped in try/except: a validator bug must NEVER prevent market syncing.
        if self._should_validate:
            try:
                validation_results = self._validator.validate_markets(
                    cast("list[dict[str, Any]]", all_markets)
                )
                error_count = sum(1 for r in validation_results if r.has_errors)
                warning_count = sum(
                    1 for r in validation_results if r.has_warnings and not r.has_errors
                )
                valid_count = len(all_markets) - error_count

                # Build warning type breakdown by field (#485)
                warning_breakdown: dict[str, int] = {}
                if warning_count:
                    for vr in validation_results:
                        for issue in vr.warnings:
                            warning_breakdown[issue.field] = (
                                warning_breakdown.get(issue.field, 0) + 1
                            )
                warning_detail = (
                    " ("
                    + ", ".join(
                        f"{f}={c}"
                        for f, c in sorted(warning_breakdown.items(), key=lambda x: -x[1])
                    )
                    + ")"
                    if warning_breakdown
                    else ""
                )

                # Log individual issues with anomaly deduplication.
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

                # Error rate escalation
                total_checked = len(all_markets)
                error_rate = error_count / total_checked if total_checked > 0 else 0.0

                if error_rate >= self.VALIDATION_ERROR_RATE:
                    logger.error(
                        "Validation [%s]: ERROR RATE %.1f%% - %d/%d markets failed "
                        "(%d errors, %d warnings%s) [ACTION: investigate data source]",
                        series_ticker,
                        error_rate * 100,
                        error_count,
                        total_checked,
                        error_count,
                        warning_count,
                        warning_detail,
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
                    logger.warning(
                        "Validation [%s]: error rate %.1f%% - %d/%d markets failed "
                        "(%d errors, %d warnings%s)",
                        series_ticker,
                        error_rate * 100,
                        error_count,
                        total_checked,
                        error_count,
                        warning_count,
                        warning_detail,
                    )
                elif error_count or warning_count:
                    logger.info(
                        "Validation [%s]: %d markets checked, %d valid, %d errors, %d warnings%s",
                        series_ticker,
                        total_checked,
                        valid_count,
                        error_count,
                        warning_count,
                        warning_detail,
                    )
                else:
                    logger.debug(
                        "Validation [%s]: %d markets checked, all valid",
                        series_ticker,
                        total_checked,
                    )

                # Track validation stats
                with self._lock:
                    self._validation_stats["validation_errors"] += error_count
                    self._validation_stats["validation_warnings"] += warning_count
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

    # =========================================================================
    # Event-to-Game Matching (Issue #462)
    # =========================================================================

    def _ensure_matcher_loaded(self) -> None:
        """Initialize and load the event-game matcher on first use.

        Lazy initialization avoids DB queries during __init__ (which may
        run before the DB is ready). The registry is loaded once and
        cached for the lifetime of the poller. Periodic refreshes are
        handled by _maybe_refresh_registry().
        """
        if self._matcher_loaded:
            self._maybe_refresh_registry()
            return

        try:
            self._event_game_matcher = EventGameMatcher()
            self._event_game_matcher.registry.load()
            self._matcher_loaded = True
            self._polls_since_registry_refresh = 0
            logger.info("Event-game matcher loaded successfully")
        except Exception:
            logger.warning(
                "Failed to load event-game matcher — events will not be linked to games this cycle",
                exc_info=True,
            )
            self._event_game_matcher = None
            # Don't set _matcher_loaded so we retry next cycle

    def _maybe_refresh_registry(self) -> None:
        """Refresh the team code registry if it's stale or has unknown codes.

        Rate-limited: checks at most once every REGISTRY_REFRESH_INTERVAL
        polls to avoid excessive DB queries. Refreshes when:
        - The registry reports needs_refresh() (age or unknown codes)
        - Enough polls have elapsed since last refresh

        Non-blocking: errors are logged but never stop polling.
        """
        if self._event_game_matcher is None:
            return

        self._polls_since_registry_refresh += 1
        if self._polls_since_registry_refresh < self.REGISTRY_REFRESH_INTERVAL:
            return

        registry = self._event_game_matcher.registry
        if not registry.needs_refresh():
            # Reset counter even if no refresh needed, to avoid
            # checking needs_refresh() on every poll after interval.
            self._polls_since_registry_refresh = 0
            return

        try:
            unknown_before = len(registry.unknown_codes_seen)
            registry.load()
            self._polls_since_registry_refresh = 0
            with self._lock:
                self._matching_stats["matching_registry_refreshes"] += 1
            logger.info(
                "Registry refreshed (had %d unknown codes)",
                unknown_before,
            )
        except Exception:
            logger.warning(
                "Failed to refresh team code registry (non-blocking)",
                exc_info=True,
            )

    def _run_matching_backfill(self) -> None:
        """Attempt to link events with game_id=NULL to games.

        Called after each poll cycle. Non-blocking: errors are logged
        but never stop the polling loop.

        Updates matching stats with the count of newly linked events.
        """
        self._ensure_matcher_loaded()
        if self._event_game_matcher is None:
            return

        try:
            linked = self._event_game_matcher.backfill_unlinked_events()
            with self._lock:
                self._matching_stats["matching_backfill_linked"] += linked
                self._matching_stats["matching_backfill_runs"] += 1
            if linked:
                logger.info("Matching backfill linked %d events", linked)
        except Exception:
            logger.warning(
                "Matching backfill failed (non-blocking)",
                exc_info=True,
            )
            with self._lock:
                self._matching_stats["matching_backfill_errors"] += 1

    def _match_event_to_game(self, event_ticker: str, title: str | None = None) -> int | None:
        """Try to match a Kalshi event to an ESPN game.

        Lazily initializes the matcher on first call. Returns None if
        matching fails or the matcher is unavailable (non-blocking).
        Tracks per-event match results for monitoring stats.

        Args:
            event_ticker: Kalshi event ticker (e.g., "KXNFLGAME-26JAN18HOUNE")
            title: Optional event title for fallback matching.

        Returns:
            games.id if matched, None otherwise.
        """
        self._ensure_matcher_loaded()
        if self._event_game_matcher is None:
            return None

        try:
            game_id, reason = self._event_game_matcher.match_event_with_reason(
                event_ticker, title=title
            )

            # Track categorized result under self._lock for thread safety
            stat_key = f"matching_{reason.value}"
            with self._lock:
                if stat_key in self._matching_stats:
                    self._matching_stats[stat_key] += 1

            return game_id
        except Exception:
            logger.debug(
                "Event matching failed for %s (non-blocking)",
                event_ticker,
                exc_info=True,
            )
            return None

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

        # Extract bid prices, last trade price, and liquidity (migration 0021 columns).
        # Same fallback pattern: try _dollars first, fall back to cents/100.
        yes_bid_price = market.get("yes_bid_dollars")
        if yes_bid_price is None:
            yes_bid_cents = market.get("yes_bid")
            if yes_bid_cents is not None:
                yes_bid_price = Decimal(yes_bid_cents) / Decimal(100)

        no_bid_price = market.get("no_bid_dollars")
        if no_bid_price is None:
            no_bid_cents = market.get("no_bid")
            if no_bid_cents is not None:
                no_bid_price = Decimal(no_bid_cents) / Decimal(100)

        last_price = market.get("last_price_dollars")
        if last_price is None:
            last_price_cents = market.get("last_price")
            if last_price_cents is not None:
                last_price = Decimal(last_price_cents) / Decimal(100)

        # Liquidity: try _dollars first (Decimal), fall back to integer dollar amount.
        liquidity = market.get("liquidity_dollars")
        if liquidity is None:
            raw_liquidity = market.get("liquidity")
            liquidity = Decimal(raw_liquidity) if raw_liquidity is not None else None

        # Spread = yes_ask - yes_bid (when both are available and bid > 0).
        # If yes_bid is None or 0, spread is unknowable.
        spread: Decimal | None = None
        if yes_bid_price is not None and yes_bid_price > 0:
            spread = yes_price - yes_bid_price

        # Compute series/subcategory and enrichment columns for both
        # create and update paths (migration 0033).
        # Use the passed series_ticker parameter, fall back to market dict if available
        effective_series = series_ticker or market.get("series_ticker", "")

        # Determine subcategory from series ticker (e.g., KXNFLGAME -> "nfl")
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

        # Enrichment columns (migration 0033, renamed in 0037)
        # subcategory is already lowercase (e.g., "nfl", "nba") — passed directly
        # to create_market/update_market_with_versioning as subcategory parameter.
        source_url = (
            f"https://kalshi.com/markets/{effective_series.lower()}/{ticker}"
            if effective_series
            else None
        )
        # Parse outcome_label from ticker: last segment after "-"
        # e.g. "KXNFLGAME-26-KC" -> "KC", but skip if all-digit
        ticker_parts = ticker.split("-")
        outcome_label = (
            ticker_parts[-1] if len(ticker_parts) > 1 and not ticker_parts[-1].isdigit() else None
        )

        # Check if market already exists
        existing = get_current_market(ticker)

        if existing is None:
            # Create new market - first ensure the event exists
            event_ticker = market.get("event_ticker", "")

            # Default to 'sports' for game-related series, 'other' for unknown
            category = "sports"  # Most Kalshi markets we poll are sports

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

                    # Attempt event-to-game matching (Issue #462)
                    # Try to match this event to an ESPN game BEFORE creation
                    # so game_id can be passed to create_event().
                    game_id = self._match_event_to_game(event_ticker, market.get("title"))

                    event_pk, _created = get_or_create_event(
                        event_id=event_ticker,
                        platform_id=self.PLATFORM_ID,
                        external_id=event_ticker,
                        category=category,
                        title=market.get("title", event_ticker),
                        series_internal_id=series_pk,  # Integer FK to series(id)
                        subcategory=subcategory,
                        game_id=game_id,  # Link to games table (may be None)
                        # Event time proxies from market-level fields.
                        # Uses the FIRST market seen in the event (subsequent
                        # markets hit the _event_id_map cache and skip creation).
                        start_time=market.get("open_time"),
                        end_time=market.get("expiration_time"),
                        # We only poll active markets, so new events are live.
                        # Settlement detection (Task 5) transitions to 'final'.
                        status="live",
                        metadata={
                            "series_ticker": effective_series,
                        },
                    )
                    # Cache the integer PK for subsequent markets in the same event
                    self._event_id_map[event_ticker] = event_pk

                    # If event already existed with game_id=NULL and we found a
                    # match, update it now (handles the TODO in get_or_create_event)
                    if not _created and game_id is not None:
                        update_event_game_id(event_pk, game_id)

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
                spread=spread,
                yes_bid_price=yes_bid_price,
                no_bid_price=no_bid_price,
                last_price=last_price,
                liquidity=liquidity,
                subtitle=market.get("subtitle"),
                open_time=market.get("open_time"),
                close_time=market.get("close_time"),
                expiration_time=market.get("expiration_time"),
                subcategory=subcategory,
                source_url=source_url,
                outcome_label=outcome_label,
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
                spread=spread,
                yes_bid_price=yes_bid_price,
                no_bid_price=no_bid_price,
                last_price=last_price,
                liquidity=liquidity,
                subtitle=market.get("subtitle"),
                open_time=market.get("open_time"),
                close_time=market.get("close_time"),
                expiration_time=market.get("expiration_time"),
                subcategory=subcategory,
                source_url=source_url,
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
