"""
End-to-End Tests for KalshiWebSocketHandler.

Tests complete workflows including initialization, connection simulation,
message processing, and shutdown sequences.

Reference: TESTING_STRATEGY V3.2 - E2E tests for critical workflows
Related Requirements: REQ-API-001, REQ-DATA-005

Usage:
    pytest tests/e2e/schedulers/test_kalshi_websocket_e2e.py -v -m e2e
"""

import json
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

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


# =============================================================================
# E2E Tests: Complete Lifecycle
# =============================================================================


@pytest.mark.e2e
class TestCompleteLifecycle:
    """E2E tests for complete handler lifecycle."""

    def test_create_subscribe_flow(self, mock_auth: MagicMock) -> None:
        """Test complete create-subscribe-check flow."""
        # Create handler
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        # Initial state
        assert handler.state == ConnectionState.DISCONNECTED
        assert handler.enabled is False
        assert handler.subscribed_tickers == []

        # Subscribe to tickers
        tickers = ["INXD-25AUXA-T64", "INXD-25AUXA-T65", "INXD-25AUXA-T66"]
        handler.subscribe(tickers)

        # Verify subscriptions stored
        assert set(handler.subscribed_tickers) == set(tickers)

        # Add callback
        received_updates: list[tuple[str, Decimal, Decimal]] = []

        def on_price(ticker: str, yes: Decimal, no: Decimal) -> None:
            received_updates.append((ticker, yes, no))

        handler.add_callback(on_price)

        # Verify callback registered
        assert len(handler._callbacks) == 1

    def test_factory_function_creates_valid_handler(self) -> None:
        """Test that factory function creates properly configured handler."""
        with patch.object(KalshiWebSocketHandler, "_init_auth"):
            handler = create_websocket_handler(
                environment="demo",
                auto_reconnect=True,
                sync_to_database=False,
            )

            assert handler.environment == "demo"
            assert handler.auto_reconnect is True
            assert handler.sync_to_database is False
            assert handler.state == ConnectionState.DISCONNECTED

    def test_prod_environment_configuration(self, mock_auth: MagicMock) -> None:
        """Test production environment configuration."""
        handler = KalshiWebSocketHandler(
            environment="prod",
            auth=mock_auth,
            auto_reconnect=True,
            sync_to_database=True,
        )

        assert handler.environment == "prod"
        assert "elections.kalshi" in handler.ws_url
        assert handler.auto_reconnect is True


# =============================================================================
# E2E Tests: Subscription Workflows
# =============================================================================


@pytest.mark.e2e
class TestSubscriptionWorkflows:
    """E2E tests for subscription management workflows."""

    def test_batch_subscribe_unsubscribe_workflow(self, handler: KalshiWebSocketHandler) -> None:
        """Test complete subscribe-unsubscribe workflow."""
        # Start with empty
        assert handler.subscribed_tickers == []

        # Subscribe batch 1
        batch1 = ["TICKER-A1", "TICKER-A2", "TICKER-A3"]
        handler.subscribe(batch1)
        assert set(handler.subscribed_tickers) == set(batch1)

        # Subscribe batch 2
        batch2 = ["TICKER-B1", "TICKER-B2"]
        handler.subscribe(batch2)
        assert len(handler.subscribed_tickers) == 5

        # Unsubscribe partial
        handler.unsubscribe(["TICKER-A1", "TICKER-B1"])
        assert "TICKER-A1" not in handler.subscribed_tickers
        assert "TICKER-B1" not in handler.subscribed_tickers
        assert "TICKER-A2" in handler.subscribed_tickers

        # Unsubscribe remaining
        handler.unsubscribe(list(handler.subscribed_tickers))
        assert handler.subscribed_tickers == []

    def test_duplicate_subscription_handling(self, handler: KalshiWebSocketHandler) -> None:
        """Test that duplicate subscriptions are handled correctly."""
        tickers = ["TICKER-1", "TICKER-2", "TICKER-3"]

        # Subscribe same tickers multiple times
        handler.subscribe(tickers)
        handler.subscribe(tickers)
        handler.subscribe(["TICKER-1", "TICKER-2"])
        handler.subscribe(["TICKER-3", "TICKER-4"])

        # Should have 4 unique tickers
        assert len(handler.subscribed_tickers) == 4
        assert set(handler.subscribed_tickers) == {"TICKER-1", "TICKER-2", "TICKER-3", "TICKER-4"}


# =============================================================================
# E2E Tests: Callback Workflows
# =============================================================================


@pytest.mark.e2e
class TestCallbackWorkflows:
    """E2E tests for callback management workflows."""

    def test_multiple_callbacks_workflow(self, handler: KalshiWebSocketHandler) -> None:
        """Test workflow with multiple callbacks."""
        # Track all updates across callbacks
        logger_updates: list[str] = []
        db_updates: list[tuple[str, Decimal, Decimal]] = []
        alert_updates: list[str] = []

        def logger_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            logger_updates.append(f"{ticker}: YES={yes}, NO={no}")

        def db_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            db_updates.append((ticker, yes, no))

        def alert_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            if yes > Decimal("0.90") or yes < Decimal("0.10"):
                alert_updates.append(f"ALERT: {ticker} at extreme price")

        # Register callbacks
        handler.add_callback(logger_callback)
        handler.add_callback(db_callback)
        handler.add_callback(alert_callback)

        # Simulate price updates
        test_data = [
            ("TICKER-1", Decimal("0.55"), Decimal("0.45")),
            ("TICKER-2", Decimal("0.95"), Decimal("0.05")),  # Extreme
            ("TICKER-3", Decimal("0.08"), Decimal("0.92")),  # Extreme
        ]

        for ticker, yes, no in test_data:
            for cb in handler._callbacks:
                cb(ticker, yes, no)

        # Verify all callbacks received updates
        assert len(logger_updates) == 3
        assert len(db_updates) == 3
        assert len(alert_updates) == 2  # Only extreme prices

    def test_callback_add_remove_workflow(self, handler: KalshiWebSocketHandler) -> None:
        """Test adding and removing callbacks dynamically."""
        call_tracker: dict[str, int] = {}

        def create_callback(name: str) -> Any:
            call_tracker[name] = 0

            def cb(ticker: str, yes: Decimal, no: Decimal) -> None:
                call_tracker[name] += 1

            cb.__name__ = name
            return cb

        # Add callbacks
        cb1 = create_callback("cb1")
        cb2 = create_callback("cb2")
        cb3 = create_callback("cb3")

        handler.add_callback(cb1)
        handler.add_callback(cb2)
        handler.add_callback(cb3)

        # Fire first update
        for cb in handler._callbacks:
            cb("T1", Decimal("0.5"), Decimal("0.5"))

        assert call_tracker == {"cb1": 1, "cb2": 1, "cb3": 1}

        # Remove middle callback
        handler.remove_callback(cb2)

        # Fire second update
        for cb in handler._callbacks:
            cb("T2", Decimal("0.5"), Decimal("0.5"))

        assert call_tracker == {"cb1": 2, "cb2": 1, "cb3": 2}


# =============================================================================
# E2E Tests: Message Processing Workflows
# =============================================================================


@pytest.mark.e2e
class TestMessageProcessingWorkflows:
    """E2E tests for message processing workflows."""

    @pytest.mark.asyncio
    async def test_complete_message_processing_pipeline(
        self, handler: KalshiWebSocketHandler
    ) -> None:
        """Test complete message processing from JSON to callback."""
        received: list[tuple[str, Decimal, Decimal]] = []

        def callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            received.append((ticker, yes, no))

        handler.add_callback(callback)

        # Process various message types
        messages = [
            # Subscription confirmation
            {"type": "subscribed", "msg": "Subscribed to ticker channel"},
            # Ticker updates
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "INXD-25AUXA-T64",
                    "yes_ask": 55,
                    "no_ask": 45,
                },
            },
            {
                "type": "ticker",
                "msg": {
                    "market_ticker": "INXD-25AUXA-T65",
                    "yes_ask_dollars": "0.6234",
                    "no_ask_dollars": "0.3766",
                },
            },
            # Orderbook delta
            {
                "type": "orderbook_delta",
                "msg": {
                    "market_ticker": "INXD-25AUXA-T64",
                    "side": "yes",
                    "price": 55,
                    "delta": 100,
                },
            },
        ]

        for msg in messages:
            await handler._process_message(json.dumps(msg))

        # Should have received 2 ticker updates
        assert len(received) == 2

        # Verify stats updated
        assert handler._stats["messages_received"] == 4
        assert handler._stats["price_updates"] == 2

    @pytest.mark.asyncio
    async def test_invalid_message_handling(self, handler: KalshiWebSocketHandler) -> None:
        """Test handling of invalid messages."""
        handler._stats["errors"]

        # Process invalid JSON
        await handler._process_message("not valid json {{{")

        # Error count shouldn't increase for invalid JSON (just logged)
        # But messages_received should increase
        assert handler._stats["messages_received"] >= 1

        # Process unknown message type
        await handler._process_message(json.dumps({"type": "unknown"}))

        # Should process without error
        assert handler._stats["messages_received"] >= 2


# =============================================================================
# E2E Tests: Statistics Workflows
# =============================================================================


@pytest.mark.e2e
class TestStatisticsWorkflows:
    """E2E tests for statistics tracking workflows."""

    @pytest.mark.asyncio
    async def test_stats_accumulation_workflow(self, handler: KalshiWebSocketHandler) -> None:
        """Test statistics accumulation over time."""
        # Initial stats
        initial_stats = handler.stats
        assert initial_stats["messages_received"] == 0
        assert initial_stats["price_updates"] == 0

        # Process some messages
        for i in range(10):
            ticker_msg = {
                "type": "ticker",
                "msg": {
                    "market_ticker": f"TICKER-{i}",
                    "yes_ask": 50 + i,
                    "no_ask": 50 - i,
                },
            }
            await handler._process_message(json.dumps(ticker_msg))

        # Check accumulated stats
        final_stats = handler.stats
        assert final_stats["messages_received"] == 10
        assert final_stats["price_updates"] == 10
        assert final_stats["last_message"] is not None

    def test_stats_snapshot_isolation(self, handler: KalshiWebSocketHandler) -> None:
        """Test that stats snapshots are isolated from internal state."""
        stats1 = handler.stats
        stats2 = handler.stats

        # Modify first snapshot
        stats1["messages_received"] = 999

        # Second snapshot should be unaffected
        assert stats2["messages_received"] == 0

        # Internal state should be unaffected
        assert handler._stats["messages_received"] == 0


# =============================================================================
# E2E Tests: Error Recovery Workflows
# =============================================================================


@pytest.mark.e2e
class TestErrorRecoveryWorkflows:
    """E2E tests for error handling and recovery workflows."""

    @pytest.mark.asyncio
    async def test_callback_error_recovery(self, handler: KalshiWebSocketHandler) -> None:
        """Test recovery from callback errors."""
        success_count = [0]

        def failing_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            raise RuntimeError("Callback failed")

        def success_callback(ticker: str, yes: Decimal, no: Decimal) -> None:
            success_count[0] += 1

        handler.add_callback(failing_callback)
        handler.add_callback(success_callback)

        # Process message - callbacks called manually for this test
        # In production, _handle_ticker_update catches callback errors
        for cb in handler._callbacks:
            try:
                cb("TEST", Decimal("0.5"), Decimal("0.5"))
            except Exception:
                pass

        # Success callback should have been called
        assert success_count[0] == 1

    def test_stats_update_after_errors(self, handler: KalshiWebSocketHandler) -> None:
        """Test that stats are updated correctly after errors."""
        # Manually set error stats
        handler._stats["errors"] = 5
        handler._stats["last_error"] = "Test error"

        stats = handler.stats
        assert stats["errors"] == 5
        assert stats["last_error"] == "Test error"


# =============================================================================
# E2E Tests: State Management Workflows
# =============================================================================


@pytest.mark.e2e
class TestStateManagementWorkflows:
    """E2E tests for state management workflows."""

    def test_state_transitions_workflow(self, handler: KalshiWebSocketHandler) -> None:
        """Test state transitions through handler lifecycle."""
        # Initial state
        assert handler.state == ConnectionState.DISCONNECTED
        assert handler.enabled is False
        assert handler.is_running() is False

        # Simulate state changes that would happen during connection
        handler._state = ConnectionState.CONNECTING
        assert handler.state == ConnectionState.CONNECTING

        handler._state = ConnectionState.CONNECTED
        handler._enabled = True
        assert handler.state == ConnectionState.CONNECTED
        assert handler.is_running() is True

        # Simulate disconnect
        handler._state = ConnectionState.RECONNECTING
        assert handler.state == ConnectionState.RECONNECTING

        handler._state = ConnectionState.DISCONNECTED
        handler._enabled = False
        assert handler.is_running() is False

    def test_get_stats_protocol_method(self, handler: KalshiWebSocketHandler) -> None:
        """Test get_stats() method for protocol compliance."""
        # get_stats is used by ServiceSupervisor
        stats = handler.get_stats()

        assert isinstance(stats, dict)
        assert "messages_received" in stats
        assert "price_updates" in stats
        assert "connection_state" in stats


# =============================================================================
# E2E Tests: Complete Configuration Scenarios
# =============================================================================


@pytest.mark.e2e
class TestConfigurationScenarios:
    """E2E tests for various configuration scenarios."""

    def test_minimal_configuration(self, mock_auth: MagicMock) -> None:
        """Test handler with minimal configuration."""
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
        )

        assert handler.environment == "demo"
        assert handler.auto_reconnect is True  # default
        assert handler.sync_to_database is True  # default

    def test_disabled_features_configuration(self, mock_auth: MagicMock) -> None:
        """Test handler with all optional features disabled."""
        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        assert handler.auto_reconnect is False
        assert handler.sync_to_database is False

    def test_invalid_environment_rejected(self, mock_auth: MagicMock) -> None:
        """Test that invalid environment is rejected."""
        with pytest.raises(ValueError, match="must be 'demo' or 'prod'"):
            KalshiWebSocketHandler(
                environment="invalid",
                auth=mock_auth,
            )
