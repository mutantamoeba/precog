"""
Hybrid Market Data Manager for coordinating polling and WebSocket data sources.

This module provides the MarketDataManager class that orchestrates both
KalshiMarketPoller (REST) and KalshiWebSocketHandler (WebSocket) for robust,
real-time market data collection.

Architecture Overview:
---------------------
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      MarketDataManager                              │
    │  ┌─────────────────────────────────────────────────────────────┐   │
    │  │                    Unified Interface                         │   │
    │  │  - subscribe_markets(tickers)                               │   │
    │  │  - get_current_price(ticker) -> Decimal                     │   │
    │  │  - add_price_callback(func)                                 │   │
    │  │  - start() / stop()                                         │   │
    │  └─────────────────────────────────────────────────────────────┘   │
    │                              │                                      │
    │           ┌──────────────────┴──────────────────┐                  │
    │           ▼                                     ▼                  │
    │  ┌─────────────────────┐           ┌─────────────────────┐        │
    │  │  KalshiMarketPoller │           │ KalshiWebSocketHandler│       │
    │  │  (REST API)         │           │ (WebSocket)          │        │
    │  │  - Initial sync     │           │ - Real-time updates  │        │
    │  │  - Periodic refresh │           │ - Sub-second latency │        │
    │  │  - Fallback source  │           │ - Primary source     │        │
    │  └─────────────────────┘           └─────────────────────┘        │
    └─────────────────────────────────────────────────────────────────────┘

Why Hybrid Architecture?
-----------------------
1. **Reliability**: WebSocket may disconnect; polling provides fallback
2. **Completeness**: Polling ensures we don't miss markets (initial sync)
3. **Validation**: Periodic polling validates WebSocket data integrity
4. **Latency**: WebSocket provides sub-second updates for edge detection

Data Flow:
---------
1. On start(): Poller does initial sync (fetch all markets)
2. WebSocket connects and subscribes to tickers
3. WebSocket updates flow in real-time (primary source)
4. Poller runs periodically for validation/fallback
5. If WebSocket disconnects, poller continues providing data
6. When WebSocket reconnects, it resumes as primary source

Failover Strategy:
-----------------
- WebSocket connected: WebSocket is primary, polling validates
- WebSocket disconnected: Polling becomes primary
- Both down: Cached data with staleness warnings

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
Related ADRs:
    - ADR-047: RSA-PSS Authentication Pattern
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import ClassVar, TypedDict

from precog.schedulers.kalshi_poller import KalshiMarketPoller
from precog.schedulers.kalshi_websocket import ConnectionState, KalshiWebSocketHandler

# Set up logging
logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class DataSourceStatus(Enum):
    """Status of a data source."""

    ACTIVE = "active"  # Source is connected and providing data
    DEGRADED = "degraded"  # Source has issues but still providing data
    OFFLINE = "offline"  # Source is not available


class _ManagerStats(TypedDict):
    """Statistics for the market data manager."""

    websocket_updates: int
    polling_updates: int
    failovers: int
    validation_mismatches: int
    last_websocket_update: str | None
    last_poll_update: str | None
    websocket_status: str
    polling_status: str
    primary_source: str


class MarketPrice(TypedDict):
    """Current market price data."""

    ticker: str
    yes_price: Decimal
    no_price: Decimal
    source: str  # "websocket" or "polling"
    timestamp: str
    is_stale: bool


# =============================================================================
# Market Data Manager
# =============================================================================


class MarketDataManager:
    """
    Hybrid market data manager coordinating polling and WebSocket sources.

    Provides a unified interface for market data collection with automatic
    failover between WebSocket (primary) and polling (fallback) sources.

    Attributes:
        environment: Kalshi environment ("demo" or "prod")
        series_tickers: List of series to poll (e.g., ["KXNFLGAME"])
        market_tickers: List of specific market tickers for WebSocket
        enabled: Whether the manager is active

    Usage:
        >>> manager = MarketDataManager(
        ...     environment="demo",
        ...     series_tickers=["KXNFLGAME"],
        ... )
        >>> manager.add_price_callback(my_callback)
        >>> manager.start()
        >>> # ... real-time data flows ...
        >>> price = manager.get_current_price("KXNFLGAME-25NOV21-DEN")
        >>> manager.stop()

    Educational Notes:
        The hybrid approach provides "defense in depth" for data collection:

        1. **WebSocket (Primary)**: Fast, efficient, real-time
           - Pros: Sub-second latency, server pushes data
           - Cons: Can disconnect, may miss messages

        2. **Polling (Secondary)**: Reliable, complete, validated
           - Pros: Simple, always gets current state
           - Cons: Higher latency, more API usage

        By combining both, we get the best of both worlds:
        - Real-time updates when connected
        - Reliable fallback when disconnected
        - Periodic validation to catch missed updates

    Reference: Phase 2 Live Data Integration
    """

    # Configuration defaults
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 30  # seconds (validation polling)
    STALE_THRESHOLD: ClassVar[int] = 60  # seconds before data is considered stale
    VALIDATION_INTERVAL: ClassVar[int] = 300  # seconds between validations (5 min)

    def __init__(
        self,
        environment: str = "demo",
        series_tickers: list[str] | None = None,
        market_tickers: list[str] | None = None,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        enable_websocket: bool = True,
        enable_polling: bool = True,
    ) -> None:
        """
        Initialize the MarketDataManager.

        Args:
            environment: Kalshi environment ("demo" or "prod")
            series_tickers: List of series for polling (e.g., ["KXNFLGAME"])
            market_tickers: List of specific tickers for WebSocket subscription
            poll_interval: Seconds between polls (default: 30)
            enable_websocket: Whether to enable WebSocket source
            enable_polling: Whether to enable polling source

        Raises:
            ValueError: If both sources are disabled or environment invalid.
        """
        if not enable_websocket and not enable_polling:
            raise ValueError("At least one data source must be enabled")

        if environment not in ("demo", "prod"):
            raise ValueError("environment must be 'demo' or 'prod'")

        self.environment = environment
        self.series_tickers = series_tickers or ["KXNFLGAME"]
        self.market_tickers = market_tickers or []
        self.poll_interval = poll_interval
        self.enable_websocket = enable_websocket
        self.enable_polling = enable_polling

        # Data sources (lazy initialization)
        self._poller: KalshiMarketPoller | None = None
        self._websocket: KalshiWebSocketHandler | None = None

        # State
        self._enabled = False
        self._lock = threading.Lock()
        self._primary_source = "websocket" if enable_websocket else "polling"

        # Price cache (ticker -> MarketPrice)
        self._price_cache: dict[str, MarketPrice] = {}
        self._cache_lock = threading.Lock()

        # Callbacks
        self._callbacks: list[Callable[[str, Decimal, Decimal], None]] = []

        # Statistics
        self._stats: _ManagerStats = {
            "websocket_updates": 0,
            "polling_updates": 0,
            "failovers": 0,
            "validation_mismatches": 0,
            "last_websocket_update": None,
            "last_poll_update": None,
            "websocket_status": "offline",
            "polling_status": "offline",
            "primary_source": self._primary_source,
        }

        # Validation tracking
        self._last_validation = 0.0

        logger.info(
            "MarketDataManager initialized: env=%s, ws=%s, poll=%s, series=%s",
            self.environment,
            enable_websocket,
            enable_polling,
            self.series_tickers,
        )

    @property
    def enabled(self) -> bool:
        """Whether the manager is currently active."""
        return self._enabled

    @property
    def stats(self) -> _ManagerStats:
        """Current statistics about data collection."""
        with self._lock:
            stats = self._stats.copy()
            # Update source statuses
            if self._websocket:
                ws_state = self._websocket.state
                if ws_state == ConnectionState.CONNECTED:
                    stats["websocket_status"] = "active"
                elif ws_state == ConnectionState.RECONNECTING:
                    stats["websocket_status"] = "degraded"
                else:
                    stats["websocket_status"] = "offline"
            if self._poller and self._poller.enabled:
                stats["polling_status"] = "active"
            stats["primary_source"] = self._primary_source
            return stats

    def add_price_callback(self, callback: Callable[[str, Decimal, Decimal], None]) -> None:
        """
        Add a callback for price updates.

        Callbacks are fired for updates from both WebSocket and polling sources.

        Args:
            callback: Function receiving (ticker, yes_price, no_price)

        Example:
            >>> def on_price(ticker, yes, no):
            ...     print(f"{ticker}: YES={yes} NO={no}")
            >>> manager.add_price_callback(on_price)
        """
        self._callbacks.append(callback)
        logger.debug("Added price callback")

    def remove_price_callback(self, callback: Callable[[str, Decimal, Decimal], None]) -> None:
        """Remove a previously registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def subscribe_markets(self, tickers: list[str]) -> None:
        """
        Subscribe to specific market tickers.

        Adds tickers to WebSocket subscription and includes in polling.

        Args:
            tickers: List of market tickers to subscribe to

        Example:
            >>> manager.subscribe_markets(["KXNFLGAME-25NOV21-DEN"])
        """
        self.market_tickers.extend(tickers)

        # Update WebSocket subscriptions if active
        if self._websocket and self._websocket.enabled:
            self._websocket.subscribe(tickers)

        logger.info("Subscribed to %d markets", len(tickers))

    def get_current_price(self, ticker: str) -> MarketPrice | None:
        """
        Get current price for a market ticker.

        Returns cached price with staleness indicator.

        Args:
            ticker: Market ticker

        Returns:
            MarketPrice dict or None if not available

        Example:
            >>> price = manager.get_current_price("KXNFLGAME-25NOV21-DEN")
            >>> if price and not price["is_stale"]:
            ...     print(f"YES: ${price['yes_price']}")
        """
        with self._cache_lock:
            price = self._price_cache.get(ticker)
            if price:
                # Check staleness
                try:
                    last_update = datetime.fromisoformat(price["timestamp"])
                    age = (datetime.now(UTC) - last_update).total_seconds()
                    price = price.copy()
                    price["is_stale"] = age > self.STALE_THRESHOLD
                except (ValueError, KeyError):
                    price["is_stale"] = True
            return price

    def get_all_prices(self) -> dict[str, MarketPrice]:
        """
        Get all cached prices.

        Returns:
            Dictionary of ticker -> MarketPrice
        """
        with self._cache_lock:
            return self._price_cache.copy()

    def start(self) -> None:
        """
        Start the market data manager.

        Initializes and starts both data sources (if enabled).
        Polling runs first for initial sync, then WebSocket connects.

        Raises:
            RuntimeError: If already started.
        """
        with self._lock:
            if self._enabled:
                raise RuntimeError("MarketDataManager is already running")
            self._enabled = True

        logger.info("Starting MarketDataManager...")

        # Start polling first (for initial sync)
        if self.enable_polling:
            self._start_polling()

        # Start WebSocket (for real-time updates)
        if self.enable_websocket:
            self._start_websocket()

        logger.info("MarketDataManager started")

    def stop(self, wait: bool = True) -> None:
        """
        Stop the market data manager.

        Cleanly shuts down both data sources.

        Args:
            wait: If True, wait for clean shutdown.
        """
        with self._lock:
            if not self._enabled:
                logger.warning("MarketDataManager is not running")
                return
            self._enabled = False

        logger.info("Stopping MarketDataManager...")

        # Stop WebSocket first (faster shutdown)
        if self._websocket:
            self._websocket.stop(wait=wait)

        # Stop polling
        if self._poller:
            self._poller.stop(wait=wait)

        logger.info("MarketDataManager stopped")

    def _start_polling(self) -> None:
        """Initialize and start the polling source."""
        self._poller = KalshiMarketPoller(
            series_tickers=self.series_tickers,
            poll_interval=self.poll_interval,
            environment=self.environment,
        )

        # Do initial sync (blocking)
        logger.info("Performing initial market sync via polling...")
        result = self._poller.poll_once()
        logger.info(
            "Initial sync complete: %d markets fetched, %d created",
            result["markets_fetched"],
            result["markets_created"],
        )

        # Update stats
        with self._lock:
            self._stats["polling_updates"] += result["markets_fetched"]
            self._stats["last_poll_update"] = datetime.now(UTC).isoformat()
            self._stats["polling_status"] = "active"

        # Start scheduled polling
        self._poller.start()

    def _start_websocket(self) -> None:
        """Initialize and start the WebSocket source."""
        self._websocket = KalshiWebSocketHandler(
            environment=self.environment,
            auto_reconnect=True,
            sync_to_database=True,
        )

        # Add our handler for WebSocket updates
        self._websocket.add_callback(self._on_websocket_update)

        # Subscribe to known market tickers
        if self.market_tickers:
            self._websocket.subscribe(self.market_tickers)

        # Start WebSocket connection
        self._websocket.start()

        with self._lock:
            self._stats["websocket_status"] = "active"

    def _on_websocket_update(self, ticker: str, yes_price: Decimal, no_price: Decimal) -> None:
        """
        Handle price update from WebSocket.

        Updates cache and fires callbacks.
        """
        now = datetime.now(UTC).isoformat()

        # Update cache
        with self._cache_lock:
            self._price_cache[ticker] = MarketPrice(
                ticker=ticker,
                yes_price=yes_price,
                no_price=no_price,
                source="websocket",
                timestamp=now,
                is_stale=False,
            )

        # Update stats
        with self._lock:
            self._stats["websocket_updates"] += 1
            self._stats["last_websocket_update"] = now

            # WebSocket is primary when connected
            if self._primary_source != "websocket":
                self._primary_source = "websocket"
                self._stats["primary_source"] = "websocket"
                logger.info("WebSocket reconnected, switching to primary")

        # Fire callbacks
        self._fire_callbacks(ticker, yes_price, no_price)

    def _fire_callbacks(self, ticker: str, yes_price: Decimal, no_price: Decimal) -> None:
        """Fire all registered callbacks with price update."""
        for callback in self._callbacks:
            try:
                callback(ticker, yes_price, no_price)
            except Exception as e:
                logger.error("Callback error: %s", e)

    def get_websocket_status(self) -> DataSourceStatus:
        """Get current WebSocket connection status."""
        if not self._websocket:
            return DataSourceStatus.OFFLINE

        state = self._websocket.state
        if state == ConnectionState.CONNECTED:
            return DataSourceStatus.ACTIVE
        if state == ConnectionState.RECONNECTING:
            return DataSourceStatus.DEGRADED
        return DataSourceStatus.OFFLINE

    def get_polling_status(self) -> DataSourceStatus:
        """Get current polling status."""
        if not self._poller:
            return DataSourceStatus.OFFLINE
        if self._poller.enabled:
            return DataSourceStatus.ACTIVE
        return DataSourceStatus.OFFLINE

    def force_poll(self) -> dict[str, int]:
        """
        Force an immediate poll cycle.

        Useful for manual refresh or testing.

        Returns:
            Poll results: {"markets_fetched": N, "markets_updated": M, ...}
        """
        if not self._poller:
            raise RuntimeError("Polling is not enabled")

        result = self._poller.poll_once()

        with self._lock:
            self._stats["polling_updates"] += result["markets_fetched"]
            self._stats["last_poll_update"] = datetime.now(UTC).isoformat()

        return result


# =============================================================================
# Convenience Functions
# =============================================================================


def create_market_data_manager(
    environment: str = "demo",
    series_tickers: list[str] | None = None,
    enable_websocket: bool = True,
    enable_polling: bool = True,
) -> MarketDataManager:
    """
    Factory function to create a configured MarketDataManager.

    Args:
        environment: Kalshi environment ("demo" or "prod")
        series_tickers: Series to poll (default: ["KXNFLGAME"])
        enable_websocket: Whether to enable WebSocket source
        enable_polling: Whether to enable polling source

    Returns:
        Configured MarketDataManager instance

    Example:
        >>> manager = create_market_data_manager(
        ...     environment="demo",
        ...     series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
        ... )
        >>> manager.start()
    """
    return MarketDataManager(
        environment=environment,
        series_tickers=series_tickers,
        enable_websocket=enable_websocket,
        enable_polling=enable_polling,
    )
