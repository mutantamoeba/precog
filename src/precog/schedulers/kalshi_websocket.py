"""
Kalshi WebSocket handler for real-time market data streaming.

This module provides the KalshiWebSocketHandler class that maintains a persistent
WebSocket connection to Kalshi for real-time price updates, complementing the
polling-based KalshiMarketPoller.

Key Features:
- Real-time price updates (<1 second latency)
- Automatic reconnection with exponential backoff
- Same RSA-PSS authentication as REST API
- Subscribes to ticker and orderbook channels
- SCD Type 2 versioning for price history
- Thread-safe callback system for price updates

Hybrid Architecture:
-------------------
This WebSocket handler is designed to work alongside KalshiMarketPoller:

    ┌─────────────────────────────────────────────────────────┐
    │                 MarketDataManager                       │
    │  (Orchestrates polling + WebSocket, handles failover)   │
    └─────────────┬───────────────────────────┬───────────────┘
                  │                           │
    ┌─────────────▼─────────────┐ ┌───────────▼─────────────┐
    │   KalshiMarketPoller      │ │  KalshiWebSocketHandler │
    │   (REST API polling)      │ │  (Real-time streaming)  │
    │   - Initial sync          │ │  - Sub-second updates   │
    │   - Fallback if WS fails  │ │  - Primary data source  │
    │   - Periodic validation   │ │  - Orderbook depth      │
    └───────────────────────────┘ └───────────────────────────┘

Why Hybrid?
    - WebSocket provides real-time updates (critical for edge detection)
    - Polling provides reliability (WebSocket may disconnect)
    - Polling validates WebSocket data (detect missed messages)
    - Initial sync via polling (don't wait for WS updates)

WebSocket Channels:
    - ticker: Price updates for subscribed markets
    - orderbook_delta: Orderbook changes (bids/asks added/removed)
    - trade: Trade executions (useful for volume tracking)
    - fill: User's own fill notifications (for position tracking)

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
Related ADRs:
    - ADR-047: RSA-PSS Authentication Pattern
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar, TypedDict

from precog.api_connectors.kalshi_auth import KalshiAuth
from precog.database.crud_operations import (
    get_current_market,
    update_market_with_versioning,
)

# Set up logging
logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class ConnectionState(Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class _WebSocketStats(TypedDict):
    """Type definition for WebSocket statistics."""

    messages_received: int
    price_updates: int
    reconnections: int
    errors: int
    last_message: str | None
    last_error: str | None
    connection_state: str
    uptime_seconds: float


class TickerUpdate(TypedDict):
    """Type definition for ticker channel updates."""

    market_ticker: str
    yes_bid: int  # cents
    yes_ask: int  # cents
    no_bid: int  # cents
    no_ask: int  # cents
    yes_bid_dollars: str | None  # sub-penny
    yes_ask_dollars: str | None  # sub-penny
    no_bid_dollars: str | None  # sub-penny
    no_ask_dollars: str | None  # sub-penny
    last_price: int | None  # cents
    volume: int | None
    open_interest: int | None


class OrderbookDelta(TypedDict):
    """Type definition for orderbook delta updates."""

    market_ticker: str
    side: str  # "yes" or "no"
    price: int  # cents
    delta: int  # quantity change (positive = add, negative = remove)


# =============================================================================
# WebSocket Handler
# =============================================================================


class KalshiWebSocketHandler:
    """
    Kalshi WebSocket handler for real-time market data.

    Maintains a persistent WebSocket connection to Kalshi for real-time price
    updates. Designed to work alongside KalshiMarketPoller in a hybrid architecture.

    Attributes:
        environment: Kalshi environment ("demo" or "prod")
        subscribed_tickers: List of market tickers to subscribe to
        state: Current connection state
        enabled: Whether the handler is active

    Usage:
        >>> # Basic usage with callback
        >>> def on_price_update(ticker: str, yes_price: Decimal, no_price: Decimal):
        ...     print(f"{ticker}: YES=${yes_price}, NO=${no_price}")
        ...
        >>> handler = KalshiWebSocketHandler(environment="demo")
        >>> handler.add_callback(on_price_update)
        >>> handler.subscribe(["INXD-25AUXA-T64", "INXD-25AUXA-T65"])
        >>> handler.start()
        >>> # ... real-time updates flow to callback ...
        >>> handler.stop()

    Educational Notes:
        WebSocket vs REST:
        - REST (polling): Request -> Response -> Wait -> Repeat
        - WebSocket: Connect once -> Server pushes updates continuously

        This is like the difference between:
        - Checking your mailbox every hour (polling)
        - Having a doorbell that rings when mail arrives (WebSocket)

        For trading, sub-second updates matter because:
        - Market prices can move quickly
        - Edge opportunities may be brief
        - Late data = missed trades or bad fills

    Reference: Phase 2 Live Data Integration
    """

    # WebSocket endpoints
    DEMO_WS_URL: ClassVar[str] = "wss://demo-api.kalshi.co/trade-api/ws/v2"
    PROD_WS_URL: ClassVar[str] = "wss://api.elections.kalshi.com/trade-api/ws/v2"

    # Connection settings
    HEARTBEAT_INTERVAL: ClassVar[int] = 10  # seconds (Kalshi pings every 10s)
    RECONNECT_BASE_DELAY: ClassVar[float] = 1.0  # seconds
    RECONNECT_MAX_DELAY: ClassVar[float] = 60.0  # seconds
    RECONNECT_MAX_ATTEMPTS: ClassVar[int] = 10  # before giving up

    def __init__(
        self,
        environment: str = "demo",
        auth: KalshiAuth | None = None,
        auto_reconnect: bool = True,
        sync_to_database: bool = True,
    ) -> None:
        """
        Initialize the KalshiWebSocketHandler.

        Args:
            environment: Kalshi environment ("demo" or "prod")
            auth: Optional KalshiAuth instance (for testing/mocking).
                If not provided, will be created from environment variables.
            auto_reconnect: Whether to automatically reconnect on disconnect.
            sync_to_database: Whether to sync price updates to database.

        Raises:
            ValueError: If environment is invalid.
        """
        if environment not in ("demo", "prod"):
            raise ValueError("environment must be 'demo' or 'prod'")

        self.environment = environment
        self.ws_url = self.DEMO_WS_URL if environment == "demo" else self.PROD_WS_URL
        self.auto_reconnect = auto_reconnect
        self.sync_to_database = sync_to_database

        # Authentication (deferred initialization)
        self._auth = auth
        self._auth_initialized = auth is not None

        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._websocket: Any = None  # websockets.WebSocketClientProtocol
        self._enabled = False
        self._lock = threading.Lock()

        # Event loop for async operations
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

        # Subscriptions and callbacks
        self._subscribed_tickers: set[str] = set()
        self._callbacks: list[Callable[[str, Decimal, Decimal], None]] = []

        # Statistics
        self._stats: _WebSocketStats = {
            "messages_received": 0,
            "price_updates": 0,
            "reconnections": 0,
            "errors": 0,
            "last_message": None,
            "last_error": None,
            "connection_state": self._state.value,
            "uptime_seconds": 0.0,
        }
        self._connect_time: float | None = None

        # Reconnection tracking
        self._reconnect_attempts = 0
        self._reconnect_delay = self.RECONNECT_BASE_DELAY

        logger.info(
            "KalshiWebSocketHandler initialized: env=%s, ws_url=%s",
            self.environment,
            self.ws_url,
        )

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def enabled(self) -> bool:
        """Whether the handler is active."""
        return self._enabled

    @property
    def subscribed_tickers(self) -> list[str]:
        """List of currently subscribed market tickers."""
        return list(self._subscribed_tickers)

    @property
    def stats(self) -> _WebSocketStats:
        """Current statistics about WebSocket activity."""
        with self._lock:
            stats = self._stats.copy()
            stats["connection_state"] = self._state.value
            if self._connect_time and self._state == ConnectionState.CONNECTED:
                stats["uptime_seconds"] = time.time() - self._connect_time
            return stats

    def add_callback(self, callback: Callable[[str, Decimal, Decimal], None]) -> None:
        """
        Add a callback for price updates.

        Callbacks receive (ticker, yes_price, no_price) on each update.

        Args:
            callback: Function to call on price updates.

        Example:
            >>> def my_callback(ticker: str, yes: Decimal, no: Decimal):
            ...     print(f"{ticker}: YES={yes}, NO={no}")
            >>> handler.add_callback(my_callback)
        """
        self._callbacks.append(callback)
        callback_name = getattr(callback, "__name__", repr(callback))
        logger.debug("Added price update callback: %s", callback_name)

    def remove_callback(self, callback: Callable[[str, Decimal, Decimal], None]) -> None:
        """Remove a previously added callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            callback_name = getattr(callback, "__name__", repr(callback))
            logger.debug("Removed price update callback: %s", callback_name)

    def subscribe(self, tickers: list[str]) -> None:
        """
        Subscribe to market tickers.

        Can be called before or after start(). If connected, sends subscription
        immediately. Otherwise, stores for subscription after connect.

        Args:
            tickers: List of market tickers to subscribe to.

        Example:
            >>> handler.subscribe(["INXD-25AUXA-T64", "INXD-25AUXA-T65"])
        """
        new_tickers = set(tickers) - self._subscribed_tickers
        self._subscribed_tickers.update(tickers)

        if new_tickers and self._state == ConnectionState.CONNECTED and self._loop:
            # Send subscription command if already connected
            asyncio.run_coroutine_threadsafe(self._send_subscribe(list(new_tickers)), self._loop)

        logger.info(
            "Subscribed to %d tickers (total: %d)", len(new_tickers), len(self._subscribed_tickers)
        )

    def unsubscribe(self, tickers: list[str]) -> None:
        """
        Unsubscribe from market tickers.

        Args:
            tickers: List of market tickers to unsubscribe from.
        """
        removed_tickers = set(tickers) & self._subscribed_tickers
        self._subscribed_tickers -= set(tickers)

        if removed_tickers and self._state == ConnectionState.CONNECTED and self._loop:
            # Send unsubscribe command if connected
            asyncio.run_coroutine_threadsafe(
                self._send_unsubscribe(list(removed_tickers)), self._loop
            )

        logger.info("Unsubscribed from %d tickers", len(removed_tickers))

    def start(self) -> None:
        """
        Start the WebSocket handler.

        Initializes authentication, creates event loop in background thread,
        and connects to Kalshi WebSocket.

        Raises:
            RuntimeError: If already started.
            ValueError: If authentication not configured.
        """
        with self._lock:
            if self._enabled:
                raise RuntimeError("KalshiWebSocketHandler is already running")

            # Initialize auth if not provided
            if not self._auth_initialized:
                self._init_auth()

            self._enabled = True
            self._state = ConnectionState.CONNECTING

        # Start event loop in background thread
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

        logger.info("KalshiWebSocketHandler started")

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        Stop the WebSocket handler.

        Args:
            wait: If True, wait for clean disconnect.
            timeout: Maximum seconds to wait for shutdown.
        """
        with self._lock:
            if not self._enabled:
                logger.warning("KalshiWebSocketHandler is not running")
                return

            self._enabled = False
            self._state = ConnectionState.CLOSED

        # Signal event loop to stop
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._close_connection(), self._loop)

            if wait and self._thread:
                self._thread.join(timeout=timeout)

        logger.info("KalshiWebSocketHandler stopped")

    def _init_auth(self) -> None:
        """
        Initialize authentication from environment variables.

        Uses DATABASE_ENVIRONMENT_STRATEGY naming convention:
        - prod -> PROD_KALSHI_API_KEY / PROD_KALSHI_PRIVATE_KEY_PATH
        - demo -> {PRECOG_ENV}_KALSHI_* (DEV, TEST, or STAGING based on PRECOG_ENV)

        Raises:
            ValueError: If required environment variables not set.
        """
        import os

        # Get environment-specific credentials using DATABASE_ENVIRONMENT_STRATEGY naming
        # See: docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
        if self.environment == "prod":
            cred_prefix = "PROD"
        else:
            # Demo environment: use PRECOG_ENV, default to DEV
            precog_env = os.getenv("PRECOG_ENV", "dev").upper()
            valid_prefixes = {"DEV", "TEST", "STAGING"}
            cred_prefix = precog_env if precog_env in valid_prefixes else "DEV"

        api_key = os.getenv(f"{cred_prefix}_KALSHI_API_KEY")
        key_file = os.getenv(f"{cred_prefix}_KALSHI_PRIVATE_KEY_PATH")

        if not api_key or not key_file:
            raise ValueError(
                f"Missing Kalshi credentials. Set {cred_prefix}_KALSHI_API_KEY and "
                f"{cred_prefix}_KALSHI_PRIVATE_KEY_PATH environment variables.\n"
                f"Current PRECOG_ENV={os.getenv('PRECOG_ENV', 'dev')}"
            )

        self._auth = KalshiAuth(api_key=api_key, private_key_path=key_file)
        self._auth_initialized = True
        logger.debug("Authentication initialized for %s environment", self.environment)

    def _run_event_loop(self) -> None:
        """Run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._connection_loop())
        except Exception as e:
            logger.exception("Event loop error: %s", e)
        finally:
            self._loop.close()
            self._loop = None

    async def _connection_loop(self) -> None:
        """
        Main connection loop with automatic reconnection.

        Handles initial connection and reconnection on disconnect.
        Uses exponential backoff for reconnection delays.
        """
        while self._enabled:
            try:
                await self._connect_and_run()
            except Exception as e:
                with self._lock:
                    self._stats["errors"] += 1
                    self._stats["last_error"] = str(e)

                # Check if we should reconnect (also handles case where stop() was called)
                # Note: _enabled can be changed by stop() in another thread
                should_reconnect = (
                    self._enabled
                    and self.auto_reconnect
                    and self._reconnect_attempts < self.RECONNECT_MAX_ATTEMPTS
                )

                if should_reconnect:
                    self._state = ConnectionState.RECONNECTING
                    self._reconnect_attempts += 1
                    with self._lock:
                        self._stats["reconnections"] += 1

                    logger.warning(
                        "Connection lost, reconnecting in %.1fs (attempt %d/%d): %s",
                        self._reconnect_delay,
                        self._reconnect_attempts,
                        self.RECONNECT_MAX_ATTEMPTS,
                        e,
                    )

                    await asyncio.sleep(self._reconnect_delay)
                    # Exponential backoff
                    self._reconnect_delay = min(self._reconnect_delay * 2, self.RECONNECT_MAX_DELAY)
                else:
                    logger.error("Max reconnection attempts reached, giving up: %s", e)
                    self._state = ConnectionState.DISCONNECTED
                    return

        self._state = ConnectionState.CLOSED

    async def _connect_and_run(self) -> None:
        """
        Connect to WebSocket and process messages.

        Educational Note:
            The websockets library handles:
            - TCP connection establishment
            - TLS/SSL handshake (for wss://)
            - WebSocket handshake (HTTP upgrade)
            - Frame encoding/decoding
            - Ping/pong heartbeat (automatic)
        """
        try:
            import websockets
        except ImportError as e:
            raise ImportError(
                "websockets library not installed. Run: pip install websockets"
            ) from e

        # Verify auth is initialized
        if self._auth is None:
            raise ValueError(
                "Authentication not initialized. Call start() first or provide auth in constructor."
            )

        # Generate authentication headers
        path = "/trade-api/ws/v2"
        headers = self._auth.get_headers(method="GET", path=path)

        # Build connection URL with auth params
        # Kalshi accepts auth as query params for WebSocket
        auth_params = (
            f"?api_key={headers['KALSHI-ACCESS-KEY']}"
            f"&timestamp={headers['KALSHI-ACCESS-TIMESTAMP']}"
            f"&signature={headers['KALSHI-ACCESS-SIGNATURE']}"
        )
        full_url = self.ws_url + auth_params

        logger.debug("Connecting to WebSocket: %s", self.ws_url)

        async with websockets.connect(
            full_url,
            ping_interval=self.HEARTBEAT_INTERVAL,
            ping_timeout=self.HEARTBEAT_INTERVAL * 2,
            close_timeout=5,
        ) as websocket:
            self._websocket = websocket
            self._state = ConnectionState.CONNECTED
            self._connect_time = time.time()
            self._reconnect_attempts = 0
            self._reconnect_delay = self.RECONNECT_BASE_DELAY

            logger.info("WebSocket connected to %s", self.ws_url)

            # Subscribe to stored tickers
            if self._subscribed_tickers:
                await self._send_subscribe(list(self._subscribed_tickers))

            # Process messages until disconnect
            async for message in websocket:
                if not self._enabled:
                    break
                # WebSocket messages can be str or bytes
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                await self._process_message(message)

    async def _send_subscribe(self, tickers: list[str]) -> None:
        """
        Send subscription command for tickers.

        Kalshi WebSocket command format:
            {"id": 1, "cmd": "subscribe", "params": {"channels": ["ticker"], "market_tickers": [...]}}
        """
        if not self._websocket:
            return

        command = {
            "id": int(time.time() * 1000),  # Unique ID
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker", "orderbook_delta"],
                "market_tickers": tickers,
            },
        }

        await self._websocket.send(json.dumps(command))
        logger.debug("Sent subscribe command for %d tickers", len(tickers))

    async def _send_unsubscribe(self, tickers: list[str]) -> None:
        """Send unsubscribe command for tickers."""
        if not self._websocket:
            return

        command = {
            "id": int(time.time() * 1000),
            "cmd": "unsubscribe",
            "params": {
                "channels": ["ticker", "orderbook_delta"],
                "market_tickers": tickers,
            },
        }

        await self._websocket.send(json.dumps(command))
        logger.debug("Sent unsubscribe command for %d tickers", len(tickers))

    async def _process_message(self, message: str) -> None:
        """
        Process incoming WebSocket message.

        Messages can be:
        - Subscription confirmations
        - Ticker updates
        - Orderbook deltas
        - Error responses
        """
        with self._lock:
            self._stats["messages_received"] += 1
            self._stats["last_message"] = datetime.now(UTC).isoformat()

        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON message: %s", e)
            return

        # Handle different message types
        msg_type = data.get("type")

        if msg_type == "ticker":
            await self._handle_ticker_update(data)
        elif msg_type == "orderbook_delta":
            await self._handle_orderbook_delta(data)
        elif msg_type == "subscribed":
            logger.debug("Subscription confirmed: %s", data.get("msg"))
        elif msg_type == "error":
            logger.error("WebSocket error: %s", data.get("msg"))
            with self._lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = data.get("msg")
        else:
            logger.debug("Unknown message type: %s", msg_type)

    async def _handle_ticker_update(self, data: dict[str, Any]) -> None:
        """
        Handle ticker channel update.

        Ticker updates contain current bid/ask prices for a market.
        Uses sub-penny *_dollars fields when available.
        """
        ticker = data.get("msg", {}).get("market_ticker")
        if not ticker:
            return

        msg = data.get("msg", {})

        # Extract prices - prefer sub-penny _dollars fields
        yes_ask_str = msg.get("yes_ask_dollars")
        no_ask_str = msg.get("no_ask_dollars")

        if yes_ask_str is not None:
            yes_price = Decimal(yes_ask_str)
        else:
            yes_price = Decimal(msg.get("yes_ask", 0)) / Decimal(100)

        if no_ask_str is not None:
            no_price = Decimal(no_ask_str)
        else:
            no_price = Decimal(msg.get("no_ask", 0)) / Decimal(100)

        with self._lock:
            self._stats["price_updates"] += 1

        # Fire callbacks
        for callback in self._callbacks:
            try:
                callback(ticker, yes_price, no_price)
            except Exception as e:
                logger.error("Callback error: %s", e)

        # Sync to database if enabled
        if self.sync_to_database:
            await asyncio.to_thread(self._sync_price_to_db, ticker, yes_price, no_price, msg)

        logger.debug(
            "Ticker update: %s YES=$%s NO=$%s",
            ticker,
            yes_price,
            no_price,
        )

    async def _handle_orderbook_delta(self, data: dict[str, Any]) -> None:
        """
        Handle orderbook delta update.

        Orderbook deltas show changes to the order book (bids/asks added/removed).
        Useful for market depth analysis but not directly used for price updates.
        """
        # For now, just log orderbook deltas
        # Full orderbook tracking is planned for Phase 3
        ticker = data.get("msg", {}).get("market_ticker")
        logger.debug("Orderbook delta for %s", ticker)

    def _sync_price_to_db(
        self,
        ticker: str,
        yes_price: Decimal,
        no_price: Decimal,
        msg: dict[str, Any],
    ) -> None:
        """
        Sync price update to database.

        Uses SCD Type 2 versioning - creates new row if price changed.

        Args:
            ticker: Market ticker
            yes_price: Current YES ask price
            no_price: Current NO ask price
            msg: Full message data for additional fields
        """
        try:
            # Check if market exists and price changed
            existing = get_current_market(ticker)
            if existing is None:
                # Market not in database - skip (poller handles creation)
                logger.debug("Market %s not in database, skipping WS update", ticker)
                return

            price_changed = existing["yes_price"] != yes_price or existing["no_price"] != no_price

            if price_changed:
                update_market_with_versioning(
                    ticker=ticker,
                    yes_price=yes_price,
                    no_price=no_price,
                    volume=msg.get("volume"),
                    open_interest=msg.get("open_interest"),
                )
                logger.debug(
                    "Updated market via WS: %s (yes: %s -> %s)",
                    ticker,
                    existing["yes_price"],
                    yes_price,
                )
        except Exception as e:
            logger.error("Database sync error for %s: %s", ticker, e)

    async def _close_connection(self) -> None:
        """Close WebSocket connection gracefully."""
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.warning("Error closing WebSocket: %s", e)
            finally:
                self._websocket = None


# =============================================================================
# Convenience Functions
# =============================================================================


def create_websocket_handler(
    environment: str = "demo",
    auto_reconnect: bool = True,
    sync_to_database: bool = True,
) -> KalshiWebSocketHandler:
    """
    Factory function to create a configured KalshiWebSocketHandler.

    Args:
        environment: Kalshi environment ("demo" or "prod")
        auto_reconnect: Whether to automatically reconnect on disconnect.
        sync_to_database: Whether to sync price updates to database.

    Returns:
        Configured KalshiWebSocketHandler instance

    Example:
        >>> handler = create_websocket_handler(environment="demo")
        >>> handler.subscribe(["INXD-25AUXA-T64"])
        >>> handler.start()
    """
    return KalshiWebSocketHandler(
        environment=environment,
        auto_reconnect=auto_reconnect,
        sync_to_database=sync_to_database,
    )
