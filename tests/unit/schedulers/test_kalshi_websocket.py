"""
Unit tests for KalshiWebSocketHandler.

Tests the WebSocket handler for Kalshi real-time market data streaming.
Uses mocking to test without actual WebSocket connections.

Test Categories:
- Initialization and configuration
- State management (connect, disconnect, reconnect)
- Subscription management
- Message processing (ticker updates, orderbook deltas)
- Callback system
- Database synchronization
- Error handling and reconnection

Reference: Phase 2 Live Data Integration
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from precog.schedulers.kalshi_websocket import (
    ConnectionState,
    KalshiWebSocketHandler,
    create_websocket_handler,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_auth():
    """Create a mock KalshiAuth instance."""
    auth = MagicMock()
    auth.get_headers.return_value = {
        "KALSHI-ACCESS-KEY": "test-api-key",
        "KALSHI-ACCESS-TIMESTAMP": "1234567890000",
        "KALSHI-ACCESS-SIGNATURE": "test-signature",
        "Content-Type": "application/json",
    }
    return auth


@pytest.fixture
def handler(mock_auth):
    """Create a handler with mocked auth (not started)."""
    return KalshiWebSocketHandler(
        environment="demo",
        auth=mock_auth,
        auto_reconnect=False,
        sync_to_database=False,
    )


@pytest.fixture
def handler_with_db(mock_auth):
    """Create a handler with database sync enabled."""
    return KalshiWebSocketHandler(
        environment="demo",
        auth=mock_auth,
        auto_reconnect=False,
        sync_to_database=True,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Tests for KalshiWebSocketHandler initialization."""

    def test_default_initialization(self, mock_auth):
        """Test handler initializes with default settings."""
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
        )

        assert handler.environment == "demo"
        assert handler.state == ConnectionState.DISCONNECTED
        assert handler.enabled is False
        assert handler.subscribed_tickers == []
        assert handler.auto_reconnect is True
        assert handler.sync_to_database is True

    def test_demo_environment_url(self, mock_auth):
        """Test demo environment uses correct WebSocket URL."""
        handler = KalshiWebSocketHandler(environment="demo", auth=mock_auth)
        assert handler.ws_url == "wss://demo-api.kalshi.co/trade-api/ws/v2"

    def test_prod_environment_url(self, mock_auth):
        """Test prod environment uses correct WebSocket URL."""
        handler = KalshiWebSocketHandler(environment="prod", auth=mock_auth)
        assert handler.ws_url == "wss://api.elections.kalshi.com/trade-api/ws/v2"

    def test_invalid_environment_raises(self, mock_auth):
        """Test invalid environment raises ValueError."""
        with pytest.raises(ValueError, match="environment must be 'demo' or 'prod'"):
            KalshiWebSocketHandler(environment="invalid", auth=mock_auth)

    def test_custom_settings(self, mock_auth):
        """Test handler accepts custom settings."""
        handler = KalshiWebSocketHandler(
            environment="prod",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        assert handler.environment == "prod"
        assert handler.auto_reconnect is False
        assert handler.sync_to_database is False

    def test_initial_stats(self, handler):
        """Test initial statistics are zero."""
        stats = handler.stats

        assert stats["messages_received"] == 0
        assert stats["price_updates"] == 0
        assert stats["reconnections"] == 0
        assert stats["errors"] == 0
        assert stats["last_message"] is None
        assert stats["last_error"] is None
        assert stats["connection_state"] == "disconnected"


# =============================================================================
# Subscription Tests
# =============================================================================


class TestSubscriptions:
    """Tests for subscription management."""

    def test_subscribe_adds_tickers(self, handler):
        """Test subscribe adds tickers to subscription list."""
        handler.subscribe(["TICKER-A", "TICKER-B"])

        assert set(handler.subscribed_tickers) == {"TICKER-A", "TICKER-B"}

    def test_subscribe_deduplicates(self, handler):
        """Test subscribe doesn't add duplicate tickers."""
        handler.subscribe(["TICKER-A", "TICKER-B"])
        handler.subscribe(["TICKER-B", "TICKER-C"])

        assert set(handler.subscribed_tickers) == {"TICKER-A", "TICKER-B", "TICKER-C"}

    def test_unsubscribe_removes_tickers(self, handler):
        """Test unsubscribe removes tickers from list."""
        handler.subscribe(["TICKER-A", "TICKER-B", "TICKER-C"])
        handler.unsubscribe(["TICKER-B"])

        assert set(handler.subscribed_tickers) == {"TICKER-A", "TICKER-C"}

    def test_unsubscribe_nonexistent_is_safe(self, handler):
        """Test unsubscribe non-existent ticker is safe."""
        handler.subscribe(["TICKER-A"])
        handler.unsubscribe(["TICKER-NONEXISTENT"])

        assert handler.subscribed_tickers == ["TICKER-A"]


# =============================================================================
# Callback Tests
# =============================================================================


class TestCallbacks:
    """Tests for callback management."""

    def test_add_callback(self, handler):
        """Test adding a callback."""
        callback = MagicMock()
        handler.add_callback(callback)

        assert callback in handler._callbacks

    def test_remove_callback(self, handler):
        """Test removing a callback."""
        callback = MagicMock()
        handler.add_callback(callback)
        handler.remove_callback(callback)

        assert callback not in handler._callbacks

    def test_remove_nonexistent_callback_is_safe(self, handler):
        """Test removing non-existent callback is safe."""
        callback = MagicMock()
        handler.remove_callback(callback)  # Should not raise

    def test_multiple_callbacks(self, handler):
        """Test multiple callbacks can be added."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        handler.add_callback(callback1)
        handler.add_callback(callback2)

        assert len(handler._callbacks) == 2


# =============================================================================
# Message Processing Tests
# =============================================================================


class TestMessageProcessing:
    """Tests for WebSocket message processing."""

    @pytest.mark.asyncio
    async def test_ticker_update_fires_callback(self, handler):
        """Test ticker update message fires registered callbacks."""
        callback = MagicMock()
        handler.add_callback(callback)

        # Simulate ticker update message
        message = json.dumps(
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "yes_ask_dollars": "0.65",
                    "no_ask_dollars": "0.35",
                    "yes_bid_dollars": "0.64",
                    "no_bid_dollars": "0.34",
                },
            }
        )

        await handler._process_message(message)

        # Callback should be called with correct values
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "TEST-TICKER"
        assert args[1] == Decimal("0.65")
        assert args[2] == Decimal("0.35")

    @pytest.mark.asyncio
    async def test_ticker_update_increments_stats(self, handler):
        """Test ticker update increments statistics."""
        message = json.dumps(
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "yes_ask_dollars": "0.50",
                    "no_ask_dollars": "0.50",
                },
            }
        )

        await handler._process_message(message)

        stats = handler.stats
        assert stats["messages_received"] == 1
        assert stats["price_updates"] == 1

    @pytest.mark.asyncio
    async def test_ticker_update_uses_cents_fallback(self, handler):
        """Test ticker update falls back to cents if dollars not available."""
        callback = MagicMock()
        handler.add_callback(callback)

        # Message with cents but no dollars
        message = json.dumps(
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "yes_ask": 65,  # 65 cents
                    "no_ask": 35,  # 35 cents
                },
            }
        )

        await handler._process_message(message)

        args = callback.call_args[0]
        assert args[1] == Decimal("0.65")
        assert args[2] == Decimal("0.35")

    @pytest.mark.asyncio
    async def test_orderbook_delta_processed(self, handler):
        """Test orderbook delta message is processed."""
        message = json.dumps(
            {
                "type": "orderbook_delta",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "side": "yes",
                    "price": 65,
                    "delta": 100,
                },
            }
        )

        await handler._process_message(message)

        # Should increment message count but not price updates
        stats = handler.stats
        assert stats["messages_received"] == 1
        assert stats["price_updates"] == 0

    @pytest.mark.asyncio
    async def test_subscription_confirmation(self, handler):
        """Test subscription confirmation is handled."""
        message = json.dumps(
            {
                "type": "subscribed",
                "msg": "Subscribed to ticker channel",
            }
        )

        await handler._process_message(message)

        stats = handler.stats
        assert stats["messages_received"] == 1
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_error_message_tracked(self, handler):
        """Test error messages are tracked in stats."""
        message = json.dumps(
            {
                "type": "error",
                "msg": "Invalid ticker",
            }
        )

        await handler._process_message(message)

        stats = handler.stats
        assert stats["messages_received"] == 1
        assert stats["errors"] == 1
        assert stats["last_error"] == "Invalid ticker"

    @pytest.mark.asyncio
    async def test_invalid_json_handled(self, handler):
        """Test invalid JSON message is handled gracefully."""
        await handler._process_message("not valid json")

        stats = handler.stats
        assert stats["messages_received"] == 1
        # Should not crash

    @pytest.mark.asyncio
    async def test_callback_error_doesnt_crash(self, handler):
        """Test callback error doesn't crash message processing."""
        callback = MagicMock(side_effect=ValueError("Test error"))
        handler.add_callback(callback)

        message = json.dumps(
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "yes_ask_dollars": "0.50",
                    "no_ask_dollars": "0.50",
                },
            }
        )

        # Should not raise
        await handler._process_message(message)


# =============================================================================
# Database Sync Tests
# =============================================================================


class TestDatabaseSync:
    """Tests for database synchronization."""

    def test_sync_price_to_db_updates_existing(self, handler_with_db):
        """Test price sync updates existing market."""
        with patch("precog.schedulers.kalshi_websocket.get_current_market") as mock_get:
            with patch(
                "precog.schedulers.kalshi_websocket.update_market_with_versioning"
            ) as mock_update:
                # Existing market with different price
                mock_get.return_value = {
                    "ticker": "TEST-TICKER",
                    "yes_price": Decimal("0.60"),
                    "no_price": Decimal("0.40"),
                }

                handler_with_db._sync_price_to_db(
                    ticker="TEST-TICKER",
                    yes_price=Decimal("0.65"),
                    no_price=Decimal("0.35"),
                    msg={"volume": 1000},
                )

                mock_update.assert_called_once_with(
                    ticker="TEST-TICKER",
                    yes_price=Decimal("0.65"),
                    no_price=Decimal("0.35"),
                    volume=1000,
                    open_interest=None,
                )

    def test_sync_price_to_db_skips_unchanged(self, handler_with_db):
        """Test price sync skips if price unchanged."""
        with patch("precog.schedulers.kalshi_websocket.get_current_market") as mock_get:
            with patch(
                "precog.schedulers.kalshi_websocket.update_market_with_versioning"
            ) as mock_update:
                # Same price as existing
                mock_get.return_value = {
                    "ticker": "TEST-TICKER",
                    "yes_price": Decimal("0.65"),
                    "no_price": Decimal("0.35"),
                }

                handler_with_db._sync_price_to_db(
                    ticker="TEST-TICKER",
                    yes_price=Decimal("0.65"),
                    no_price=Decimal("0.35"),
                    msg={},
                )

                mock_update.assert_not_called()

    def test_sync_price_to_db_skips_nonexistent(self, handler_with_db):
        """Test price sync skips if market doesn't exist."""
        with patch("precog.schedulers.kalshi_websocket.get_current_market") as mock_get:
            with patch(
                "precog.schedulers.kalshi_websocket.update_market_with_versioning"
            ) as mock_update:
                mock_get.return_value = None  # Market not in database

                handler_with_db._sync_price_to_db(
                    ticker="UNKNOWN-TICKER",
                    yes_price=Decimal("0.50"),
                    no_price=Decimal("0.50"),
                    msg={},
                )

                mock_update.assert_not_called()


# =============================================================================
# State Management Tests
# =============================================================================


class TestStateManagement:
    """Tests for connection state management."""

    def test_initial_state_disconnected(self, handler):
        """Test handler starts in disconnected state."""
        assert handler.state == ConnectionState.DISCONNECTED
        assert handler.enabled is False

    def test_stop_when_not_running_warns(self, handler):
        """Test stop when not running logs warning but doesn't crash."""
        handler.stop()  # Should not raise
        assert handler.state == ConnectionState.DISCONNECTED

    def test_start_when_already_running_raises(self, handler, mock_auth):
        """Test starting when already running raises error."""
        # Simulate running state
        handler._enabled = True

        with pytest.raises(RuntimeError, match="already running"):
            handler.start()

    def test_stats_include_connection_state(self, handler):
        """Test stats include current connection state."""
        stats = handler.stats
        assert stats["connection_state"] == "disconnected"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_websocket_handler factory function."""

    def test_creates_handler_with_defaults(self):
        """Test factory creates handler with default settings."""
        with patch.object(KalshiWebSocketHandler, "__init__", return_value=None):
            handler = create_websocket_handler()

            # Verify init was called (mock prevents actual initialization)
            assert handler is not None

    def test_creates_handler_with_custom_settings(self):
        """Test factory passes custom settings to handler."""
        with patch.object(KalshiWebSocketHandler, "__init__", return_value=None) as mock_init:
            create_websocket_handler(
                environment="prod",
                auto_reconnect=False,
                sync_to_database=False,
            )

            mock_init.assert_called_once_with(
                environment="prod",
                auto_reconnect=False,
                sync_to_database=False,
            )


# =============================================================================
# Connection State Enum Tests
# =============================================================================


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_all_states_have_values(self):
        """Test all connection states have string values."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.CLOSED.value == "closed"


# =============================================================================
# Integration-like Tests (with mocked WebSocket)
# =============================================================================


class TestMockedWebSocket:
    """Tests with mocked WebSocket connection."""

    @pytest.mark.asyncio
    async def test_send_subscribe_command(self, handler):
        """Test subscribe command format is correct."""
        handler._websocket = AsyncMock()
        handler._state = ConnectionState.CONNECTED

        await handler._send_subscribe(["TICKER-A", "TICKER-B"])

        # Verify command was sent
        handler._websocket.send.assert_called_once()
        call_args = handler._websocket.send.call_args[0][0]
        command = json.loads(call_args)

        assert command["cmd"] == "subscribe"
        assert "ticker" in command["params"]["channels"]
        assert "orderbook_delta" in command["params"]["channels"]
        assert set(command["params"]["market_tickers"]) == {"TICKER-A", "TICKER-B"}

    @pytest.mark.asyncio
    async def test_send_unsubscribe_command(self, handler):
        """Test unsubscribe command format is correct."""
        handler._websocket = AsyncMock()
        handler._state = ConnectionState.CONNECTED

        await handler._send_unsubscribe(["TICKER-A"])

        handler._websocket.send.assert_called_once()
        call_args = handler._websocket.send.call_args[0][0]
        command = json.loads(call_args)

        assert command["cmd"] == "unsubscribe"
        assert command["params"]["market_tickers"] == ["TICKER-A"]

    @pytest.mark.asyncio
    async def test_close_connection(self, handler):
        """Test close connection calls websocket close."""
        mock_ws = AsyncMock()
        handler._websocket = mock_ws

        await handler._close_connection()

        # Verify close was called on the websocket
        mock_ws.close.assert_called_once()
        # Verify handler cleared the websocket reference
        assert handler._websocket is None


# =============================================================================
# Decimal Precision Tests (Pattern 1)
# =============================================================================


class TestDecimalPrecision:
    """Tests ensuring Decimal precision is maintained."""

    @pytest.mark.asyncio
    async def test_sub_penny_precision_preserved(self, handler):
        """Test sub-penny precision is preserved from WebSocket updates."""
        callback = MagicMock()
        handler.add_callback(callback)

        # Sub-penny prices (common for Kalshi)
        message = json.dumps(
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "yes_ask_dollars": "0.4975",
                    "no_ask_dollars": "0.5025",
                },
            }
        )

        await handler._process_message(message)

        args = callback.call_args[0]
        assert args[1] == Decimal("0.4975")
        assert args[2] == Decimal("0.5025")
        assert isinstance(args[1], Decimal)
        assert isinstance(args[2], Decimal)

    @pytest.mark.asyncio
    async def test_never_uses_float(self, handler):
        """Test prices are never converted to float."""
        callback = MagicMock()
        handler.add_callback(callback)

        message = json.dumps(
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "TEST-TICKER",
                    "yes_ask_dollars": "0.333333",
                    "no_ask_dollars": "0.666667",
                },
            }
        )

        await handler._process_message(message)

        args = callback.call_args[0]
        # Verify no float contamination
        assert not isinstance(args[1], float)
        assert not isinstance(args[2], float)
        # Verify exact Decimal representation
        assert args[1] == Decimal("0.333333")
        assert args[2] == Decimal("0.666667")
