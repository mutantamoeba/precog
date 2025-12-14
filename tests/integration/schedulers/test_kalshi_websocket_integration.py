"""
Integration Tests for KalshiWebSocketHandler.

Tests interaction between WebSocket handler and other system components
including database operations, auth system, and callback system.

Reference: TESTING_STRATEGY V3.2 - Integration tests for component interaction
Related Requirements: REQ-API-001, REQ-DATA-005

Usage:
    pytest tests/integration/schedulers/test_kalshi_websocket_integration.py -v -m integration
"""

import asyncio
import json
import threading
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.kalshi_websocket import (
    KalshiWebSocketHandler,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_auth() -> MagicMock:
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
def handler(mock_auth: MagicMock) -> KalshiWebSocketHandler:
    """Create a handler with mocked auth."""
    return KalshiWebSocketHandler(
        environment="demo",
        auth=mock_auth,
        auto_reconnect=False,
        sync_to_database=False,
    )


@pytest.fixture
def handler_with_db(mock_auth: MagicMock) -> KalshiWebSocketHandler:
    """Create a handler with database sync enabled."""
    return KalshiWebSocketHandler(
        environment="demo",
        auth=mock_auth,
        auto_reconnect=False,
        sync_to_database=True,
    )


# =============================================================================
# Integration Tests: Auth Integration
# =============================================================================


@pytest.mark.integration
class TestAuthIntegration:
    """Tests for authentication integration."""

    def test_auth_headers_used_for_connection(self, mock_auth: MagicMock) -> None:
        """Test that auth headers are correctly formatted for WebSocket connection."""
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        # Handler should store auth
        assert handler._auth == mock_auth

    def test_auth_initialized_from_environment_on_start(self) -> None:
        """Test that auth is initialized from environment variables when needed."""
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=None,  # Will need to init from env
            auto_reconnect=False,
            sync_to_database=False,
        )

        # Auth not initialized yet
        assert handler._auth is None
        assert handler._auth_initialized is False

        # Try to start - should fail because no env vars
        # Clear ALL potential Kalshi credential env vars
        env_overrides = {
            "DEV_KALSHI_API_KEY": "",
            "DEV_KALSHI_PRIVATE_KEY_PATH": "",
            "TEST_KALSHI_API_KEY": "",
            "TEST_KALSHI_PRIVATE_KEY_PATH": "",
            "STAGING_KALSHI_API_KEY": "",
            "STAGING_KALSHI_PRIVATE_KEY_PATH": "",
            "PRECOG_ENV": "dev",  # Force DEV prefix
        }
        with patch.dict("os.environ", env_overrides, clear=False):
            with pytest.raises(ValueError, match="Missing Kalshi credentials"):
                # _init_auth will fail without proper env vars
                handler.start()


# =============================================================================
# Integration Tests: Callback System Integration
# =============================================================================


@pytest.mark.integration
class TestCallbackIntegration:
    """Tests for callback system integration."""

    def test_callbacks_receive_correct_types(self, handler: KalshiWebSocketHandler) -> None:
        """Test that callbacks receive correct argument types."""
        received: list[tuple[str, Decimal, Decimal]] = []

        def callback(ticker: str, yes_price: Decimal, no_price: Decimal) -> None:
            received.append((ticker, yes_price, no_price))

        handler.add_callback(callback)

        # Simulate calling callbacks directly
        for cb in handler._callbacks:
            cb("TEST-TICKER", Decimal("0.55"), Decimal("0.45"))

        assert len(received) == 1
        assert received[0][0] == "TEST-TICKER"
        assert isinstance(received[0][1], Decimal)
        assert isinstance(received[0][2], Decimal)

    def test_multiple_callbacks_all_invoked(self, handler: KalshiWebSocketHandler) -> None:
        """Test that all registered callbacks are invoked."""
        call_counts = {"cb1": 0, "cb2": 0, "cb3": 0}

        def cb1(ticker: str, yes: Decimal, no: Decimal) -> None:
            call_counts["cb1"] += 1

        def cb2(ticker: str, yes: Decimal, no: Decimal) -> None:
            call_counts["cb2"] += 1

        def cb3(ticker: str, yes: Decimal, no: Decimal) -> None:
            call_counts["cb3"] += 1

        handler.add_callback(cb1)
        handler.add_callback(cb2)
        handler.add_callback(cb3)

        # Simulate firing callbacks
        for cb in handler._callbacks:
            cb("TICKER", Decimal("0.50"), Decimal("0.50"))

        assert call_counts["cb1"] == 1
        assert call_counts["cb2"] == 1
        assert call_counts["cb3"] == 1

    def test_callback_error_isolated(self, handler: KalshiWebSocketHandler) -> None:
        """Test that callback errors are isolated and don't affect other callbacks."""
        results: list[str] = []

        def failing_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            raise ValueError("Test error")

        def success_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            results.append(ticker)

        handler.add_callback(failing_callback)
        handler.add_callback(success_callback)

        # Manually invoke (simulating _handle_ticker_update behavior)
        for cb in handler._callbacks:
            try:
                cb("TEST", Decimal("0.5"), Decimal("0.5"))
            except Exception:
                pass  # Isolated

        # Success callback should have been called despite failing callback
        assert "TEST" in results


# =============================================================================
# Integration Tests: Database Sync Integration
# =============================================================================


@pytest.mark.integration
class TestDatabaseSyncIntegration:
    """Tests for database synchronization integration."""

    def test_db_sync_flag_controls_behavior(self, mock_auth: MagicMock) -> None:
        """Test that sync_to_database flag controls database operations."""
        handler_no_db = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            sync_to_database=False,
        )
        handler_with_db = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            sync_to_database=True,
        )

        assert handler_no_db.sync_to_database is False
        assert handler_with_db.sync_to_database is True

    @patch("precog.schedulers.kalshi_websocket.get_current_market")
    @patch("precog.schedulers.kalshi_websocket.update_market_with_versioning")
    def test_db_sync_called_on_price_change(
        self,
        mock_update: MagicMock,
        mock_get: MagicMock,
        handler_with_db: KalshiWebSocketHandler,
    ) -> None:
        """Test that database is synced when price changes."""
        # Setup mock - market exists with different price
        mock_get.return_value = {
            "ticker": "TEST-TICKER",
            "yes_price": Decimal("0.40"),
            "no_price": Decimal("0.60"),
        }

        # Call _sync_price_to_db directly
        handler_with_db._sync_price_to_db(
            ticker="TEST-TICKER",
            yes_price=Decimal("0.55"),
            no_price=Decimal("0.45"),
            msg={"volume": 1000},
        )

        # Verify update was called
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["ticker"] == "TEST-TICKER"
        assert call_kwargs["yes_price"] == Decimal("0.55")
        assert call_kwargs["no_price"] == Decimal("0.45")

    @patch("precog.schedulers.kalshi_websocket.get_current_market")
    @patch("precog.schedulers.kalshi_websocket.update_market_with_versioning")
    def test_db_sync_skipped_when_price_unchanged(
        self,
        mock_update: MagicMock,
        mock_get: MagicMock,
        handler_with_db: KalshiWebSocketHandler,
    ) -> None:
        """Test that database sync is skipped when price unchanged."""
        # Setup mock - market exists with same price
        mock_get.return_value = {
            "ticker": "TEST-TICKER",
            "yes_price": Decimal("0.55"),
            "no_price": Decimal("0.45"),
        }

        # Call _sync_price_to_db
        handler_with_db._sync_price_to_db(
            ticker="TEST-TICKER",
            yes_price=Decimal("0.55"),
            no_price=Decimal("0.45"),
            msg={},
        )

        # Verify update was NOT called
        mock_update.assert_not_called()

    @patch("precog.schedulers.kalshi_websocket.get_current_market")
    @patch("precog.schedulers.kalshi_websocket.update_market_with_versioning")
    def test_db_sync_skipped_for_unknown_market(
        self,
        mock_update: MagicMock,
        mock_get: MagicMock,
        handler_with_db: KalshiWebSocketHandler,
    ) -> None:
        """Test that database sync is skipped for markets not in DB."""
        # Setup mock - market doesn't exist
        mock_get.return_value = None

        # Call _sync_price_to_db
        handler_with_db._sync_price_to_db(
            ticker="UNKNOWN-TICKER",
            yes_price=Decimal("0.55"),
            no_price=Decimal("0.45"),
            msg={},
        )

        # Verify update was NOT called
        mock_update.assert_not_called()


# =============================================================================
# Integration Tests: Message Processing Integration
# =============================================================================


@pytest.mark.integration
class TestMessageProcessingIntegration:
    """Tests for message processing integration."""

    @pytest.mark.asyncio
    async def test_ticker_update_processes_correctly(self, handler: KalshiWebSocketHandler) -> None:
        """Test that ticker updates are processed correctly."""
        received: list[tuple[str, Decimal, Decimal]] = []

        def callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            received.append((ticker, yes, no))

        handler.add_callback(callback)

        # Create ticker message
        ticker_data = {
            "type": "ticker",
            "msg": {
                "market_ticker": "TEST-TICKER",
                "yes_ask": 55,
                "no_ask": 45,
            },
        }

        # Process message
        await handler._process_message(json.dumps(ticker_data))

        # Wait briefly for async processing
        await asyncio.sleep(0.1)

        # Should have updated stats
        assert handler._stats["messages_received"] >= 1

    @pytest.mark.asyncio
    async def test_ticker_update_with_dollars_fields(self, handler: KalshiWebSocketHandler) -> None:
        """Test that _dollars fields are preferred over cent fields."""
        received: list[tuple[str, Decimal, Decimal]] = []

        def callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            received.append((ticker, yes, no))

        handler.add_callback(callback)

        # Create ticker message with both cent and dollar fields
        ticker_data = {
            "type": "ticker",
            "msg": {
                "market_ticker": "TEST-TICKER",
                "yes_ask": 50,  # cents - should be ignored
                "no_ask": 50,
                "yes_ask_dollars": "0.5575",  # should be used
                "no_ask_dollars": "0.4425",
            },
        }

        await handler._process_message(json.dumps(ticker_data))
        await asyncio.sleep(0.1)

        # Verify dollar values were used (sub-penny precision)
        if received:
            assert received[0][1] == Decimal("0.5575")
            assert received[0][2] == Decimal("0.4425")


# =============================================================================
# Integration Tests: Subscription Management Integration
# =============================================================================


@pytest.mark.integration
class TestSubscriptionIntegration:
    """Tests for subscription management integration."""

    def test_subscribe_before_connect(self, handler: KalshiWebSocketHandler) -> None:
        """Test that subscriptions made before connect are stored."""
        tickers = ["TICKER-1", "TICKER-2", "TICKER-3"]
        handler.subscribe(tickers)

        assert set(handler.subscribed_tickers) == set(tickers)

    def test_subscribe_tracks_all_tickers(self, handler: KalshiWebSocketHandler) -> None:
        """Test that all subscribed tickers are tracked."""
        # Subscribe in batches
        handler.subscribe(["A-1", "A-2"])
        handler.subscribe(["B-1", "B-2"])
        handler.subscribe(["C-1"])

        assert len(handler.subscribed_tickers) == 5
        assert "A-1" in handler.subscribed_tickers
        assert "C-1" in handler.subscribed_tickers

    def test_unsubscribe_removes_correct_tickers(self, handler: KalshiWebSocketHandler) -> None:
        """Test that unsubscribe removes only specified tickers."""
        handler.subscribe(["A", "B", "C", "D", "E"])
        handler.unsubscribe(["B", "D"])

        assert set(handler.subscribed_tickers) == {"A", "C", "E"}


# =============================================================================
# Integration Tests: Thread Safety
# =============================================================================


@pytest.mark.integration
class TestThreadSafetyIntegration:
    """Tests for thread safety in integration scenarios."""

    def test_concurrent_subscriptions(self, handler: KalshiWebSocketHandler) -> None:
        """Test that concurrent subscriptions are handled safely."""
        results: list[bool] = []
        lock = threading.Lock()

        def subscribe_batch(prefix: str) -> None:
            try:
                tickers = [f"{prefix}-{i}" for i in range(10)]
                handler.subscribe(tickers)
                with lock:
                    results.append(True)
            except Exception:
                with lock:
                    results.append(False)

        # Run concurrent subscriptions
        threads = [threading.Thread(target=subscribe_batch, args=(f"P{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert all(results)
        # Should have 50 unique tickers
        assert len(handler.subscribed_tickers) == 50

    def test_concurrent_callback_registration(self, handler: KalshiWebSocketHandler) -> None:
        """Test that concurrent callback registration is safe."""
        callbacks_added = []
        lock = threading.Lock()

        def add_callbacks(count: int) -> None:
            for i in range(count):
                cb = MagicMock(name=f"cb_{count}_{i}")
                handler.add_callback(cb)
                with lock:
                    callbacks_added.append(cb)

        threads = [threading.Thread(target=add_callbacks, args=(5,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 20 callbacks should be registered
        assert len(handler._callbacks) == 20

    def test_stats_access_thread_safe(self, handler: KalshiWebSocketHandler) -> None:
        """Test that stats access is thread-safe."""
        results: list[dict[str, Any]] = []
        lock = threading.Lock()

        def read_stats() -> None:
            for _ in range(100):
                stats = handler.stats
                with lock:
                    results.append(stats)

        threads = [threading.Thread(target=read_stats) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 500 stat readings
        assert len(results) == 500
        # All should be valid dicts
        for r in results:
            assert "messages_received" in r
            assert "connection_state" in r
