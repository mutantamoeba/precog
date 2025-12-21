"""
End-to-end tests for MarketDataManager.

Tests complete workflows from configuration through data collection, verifying
the hybrid data manager works correctly as a full system.

E2E Test Scenarios:
    1. Full startup workflow - Configure, start, collect data, stop
    2. Failover scenarios - WebSocket disconnect/reconnect
    3. Real-time data flow - Callbacks receive updates
    4. Multi-ticker management - Subscribe and track multiple markets
    5. Graceful shutdown - Clean termination with data preservation

Educational Note:
    E2E tests for data managers verify complete user workflows work correctly.
    They test scenarios that a production system would encounter, including:
    - Configuration through public API
    - Data flowing through all layers
    - Error recovery and failover
    - Clean shutdown

Reference: Phase 2 Live Data Integration
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
Related ADRs:
    - ADR-100: Service Supervisor Pattern
"""

import threading
from decimal import Decimal
from unittest.mock import patch

import pytest

from precog.schedulers.kalshi_websocket import ConnectionState
from precog.schedulers.market_data_manager import (
    DataSourceStatus,
    MarketDataManager,
    create_market_data_manager,
)

pytestmark = [pytest.mark.e2e]


# =============================================================================
# Test Helpers
# =============================================================================


class MockPollerForE2E:
    """Enhanced mock poller that simulates realistic behavior."""

    def __init__(self):
        self.enabled = False
        self.poll_count = 0
        self.markets_data = []

    def poll_once(self):
        self.poll_count += 1
        return {
            "markets_fetched": 10,
            "markets_updated": 5,
            "markets_created": 5,
        }

    def start(self):
        self.enabled = True

    def stop(self, wait=True):
        self.enabled = False


class MockWebSocketForE2E:
    """Enhanced mock WebSocket that simulates realistic behavior."""

    def __init__(self):
        self.enabled = False
        self.state = ConnectionState.DISCONNECTED
        self.callbacks = []
        self.subscriptions = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def subscribe(self, tickers):
        self.subscriptions.extend(tickers)

    def start(self):
        self.enabled = True
        self.state = ConnectionState.CONNECTED

    def stop(self, wait=True):
        self.enabled = False
        self.state = ConnectionState.DISCONNECTED

    def simulate_price_update(self, ticker, yes_price, no_price):
        """Simulate a price update from the WebSocket."""
        for callback in self.callbacks:
            callback(ticker, yes_price, no_price)

    def simulate_disconnect(self):
        """Simulate WebSocket disconnection."""
        self.state = ConnectionState.DISCONNECTED

    def simulate_reconnect(self):
        """Simulate WebSocket reconnection."""
        self.state = ConnectionState.CONNECTED


# =============================================================================
# E2E Workflow Tests
# =============================================================================


class TestFullStartupWorkflow:
    """E2E tests for complete startup workflow."""

    def test_full_startup_to_data_collection(self) -> None:
        """Test complete workflow: create -> configure -> start -> collect data."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                # Step 1: Create manager
                manager = create_market_data_manager(
                    environment="demo",
                    series_tickers=["KXNFLGAME"],
                )

                # Step 2: Configure callbacks
                received_updates = []

                def on_price(ticker, yes, no):
                    received_updates.append((ticker, yes, no))

                manager.add_price_callback(on_price)

                # Step 3: Start manager
                manager.start()

                # Verify initial state
                assert manager.enabled
                assert mock_poller.enabled
                assert mock_ws.enabled
                assert mock_poller.poll_count == 1  # Initial sync

                # Step 4: Simulate data collection
                mock_ws.simulate_price_update("KXNFLGAME-DEN", Decimal("0.65"), Decimal("0.35"))
                mock_ws.simulate_price_update("KXNFLGAME-KC", Decimal("0.55"), Decimal("0.45"))

                # Verify data received
                assert len(received_updates) == 2
                assert ("KXNFLGAME-DEN", Decimal("0.65"), Decimal("0.35")) in received_updates

                # Step 5: Get prices via API
                price = manager.get_current_price("KXNFLGAME-DEN")
                assert price is not None
                assert price["yes_price"] == Decimal("0.65")

                # Step 6: Clean shutdown
                manager.stop()
                assert not manager.enabled

    def test_startup_with_existing_subscriptions(self) -> None:
        """Test startup with pre-configured market subscriptions."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                # Create with initial market tickers
                manager = MarketDataManager(
                    environment="demo",
                    series_tickers=["KXNFLGAME"],
                    market_tickers=["SPECIFIC-TICKER-1", "SPECIFIC-TICKER-2"],
                )

                manager.start()

                # Verify subscriptions were forwarded
                assert "SPECIFIC-TICKER-1" in mock_ws.subscriptions
                assert "SPECIFIC-TICKER-2" in mock_ws.subscriptions

                manager.stop()


class TestFailoverScenarios:
    """E2E tests for failover between data sources."""

    def test_websocket_disconnect_polling_continues(self) -> None:
        """Test polling continues when WebSocket disconnects."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Verify WebSocket connected
                assert manager.get_websocket_status() == DataSourceStatus.ACTIVE

                # Simulate disconnect
                mock_ws.simulate_disconnect()

                # Polling should still be active
                assert manager.get_polling_status() == DataSourceStatus.ACTIVE

                # WebSocket should show offline
                assert manager.get_websocket_status() == DataSourceStatus.OFFLINE

                # Force poll should still work
                result = manager.force_poll()
                assert result["markets_fetched"] == 10

                manager.stop()

    def test_websocket_reconnection_resumes_primary(self) -> None:
        """Test WebSocket becomes primary again after reconnection."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Start with polling as primary (simulating prior disconnect)
                manager._primary_source = "polling"

                # Simulate reconnection with data
                mock_ws.simulate_reconnect()
                mock_ws.simulate_price_update("TEST", Decimal("0.50"), Decimal("0.50"))

                # WebSocket should now be primary
                assert manager._primary_source == "websocket"

                manager.stop()

    def test_polling_only_mode_works_independently(self) -> None:
        """Test polling-only mode works when WebSocket disabled."""
        mock_poller = MockPollerForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            manager = MarketDataManager(
                environment="demo",
                enable_websocket=False,
                enable_polling=True,
            )

            manager.start()

            # Only polling should be available
            assert manager.get_polling_status() == DataSourceStatus.ACTIVE
            assert manager.get_websocket_status() == DataSourceStatus.OFFLINE

            # Force poll should work
            result = manager.force_poll()
            assert result["markets_fetched"] == 10

            manager.stop()


class TestRealtimeDataFlow:
    """E2E tests for real-time data flow through callbacks."""

    def test_high_frequency_updates_processed(self) -> None:
        """Test high-frequency price updates are all processed."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()

                update_count = 0
                lock = threading.Lock()

                def on_price(ticker, yes, no):
                    nonlocal update_count
                    with lock:
                        update_count += 1

                manager.add_price_callback(on_price)
                manager.start()

                # Simulate rapid updates (100 updates)
                for i in range(100):
                    price = Decimal(str(0.50 + i * 0.001))
                    mock_ws.simulate_price_update(f"TICKER-{i % 10}", price, Decimal("1") - price)

                # All updates should be processed
                assert update_count == 100

                manager.stop()

    def test_multiple_callbacks_independent(self) -> None:
        """Test multiple callbacks operate independently."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()

                callback_1_data = []
                callback_2_data = []

                def callback_1(t, y, n):
                    callback_1_data.append(("cb1", t, float(y)))

                def callback_2(t, y, n):
                    callback_2_data.append(("cb2", t, float(y)))

                manager.add_price_callback(callback_1)
                manager.add_price_callback(callback_2)
                manager.start()

                mock_ws.simulate_price_update("TEST", Decimal("0.75"), Decimal("0.25"))

                # Both should receive the update
                assert len(callback_1_data) == 1
                assert len(callback_2_data) == 1
                assert callback_1_data[0][2] == 0.75
                assert callback_2_data[0][2] == 0.75

                manager.stop()

    def test_callback_error_doesnt_stop_others(self) -> None:
        """Test callback error doesn't prevent other callbacks."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()

                successful_calls = []

                def bad_callback(t, y, n):
                    raise ValueError("Intentional error")

                def good_callback(t, y, n):
                    successful_calls.append(t)

                manager.add_price_callback(bad_callback)
                manager.add_price_callback(good_callback)
                manager.start()

                # Should not raise, good callback should still work
                mock_ws.simulate_price_update("TEST", Decimal("0.50"), Decimal("0.50"))

                assert "TEST" in successful_calls

                manager.stop()


class TestMultiTickerManagement:
    """E2E tests for managing multiple market tickers."""

    def test_track_multiple_markets_simultaneously(self) -> None:
        """Test tracking multiple markets at once."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Add prices for multiple markets
                markets = [
                    ("KXNFLGAME-DEN", Decimal("0.65"), Decimal("0.35")),
                    ("KXNFLGAME-KC", Decimal("0.55"), Decimal("0.45")),
                    ("KXNFLGAME-BUF", Decimal("0.70"), Decimal("0.30")),
                    ("KXNCAAFGAME-OSU", Decimal("0.80"), Decimal("0.20")),
                ]

                for ticker, yes, no in markets:
                    mock_ws.simulate_price_update(ticker, yes, no)

                # Verify all prices available
                all_prices = manager.get_all_prices()
                assert len(all_prices) == 4

                # Verify individual lookups
                for ticker, yes, no in markets:
                    price = manager.get_current_price(ticker)
                    assert price is not None
                    assert price["yes_price"] == yes

                manager.stop()

    def test_subscribe_new_markets_dynamically(self) -> None:
        """Test subscribing to new markets after start."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Subscribe to new markets dynamically
                manager.subscribe_markets(["NEW-MARKET-1", "NEW-MARKET-2"])

                # Verify subscriptions recorded
                assert "NEW-MARKET-1" in manager.market_tickers
                assert "NEW-MARKET-2" in manager.market_tickers

                # Verify forwarded to WebSocket
                assert "NEW-MARKET-1" in mock_ws.subscriptions

                manager.stop()

    def test_price_updates_isolated_per_ticker(self) -> None:
        """Test price updates don't affect other tickers."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Set initial prices
                mock_ws.simulate_price_update("TICKER-A", Decimal("0.60"), Decimal("0.40"))
                mock_ws.simulate_price_update("TICKER-B", Decimal("0.70"), Decimal("0.30"))

                # Update only TICKER-A
                mock_ws.simulate_price_update("TICKER-A", Decimal("0.65"), Decimal("0.35"))

                # TICKER-B should be unchanged
                price_a = manager.get_current_price("TICKER-A")
                price_b = manager.get_current_price("TICKER-B")

                assert price_a is not None
                assert price_b is not None
                assert price_a["yes_price"] == Decimal("0.65")  # Updated
                assert price_b["yes_price"] == Decimal("0.70")  # Unchanged

                manager.stop()


class TestGracefulShutdown:
    """E2E tests for graceful shutdown scenarios."""

    def test_shutdown_preserves_cached_data(self) -> None:
        """Test shutdown preserves cached price data."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Collect some data
                mock_ws.simulate_price_update("TEST-TICKER", Decimal("0.75"), Decimal("0.25"))

                # Stop manager
                manager.stop()

                # Cache should still be accessible (even after stop)
                price = manager.get_current_price("TEST-TICKER")
                assert price is not None
                assert price["yes_price"] == Decimal("0.75")

    def test_shutdown_stops_all_sources(self) -> None:
        """Test shutdown stops both WebSocket and polling."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                assert mock_poller.enabled
                assert mock_ws.enabled

                manager.stop()

                assert not mock_poller.enabled
                assert not mock_ws.enabled  # type: ignore[unreachable]

    def test_shutdown_under_load(self) -> None:
        """Test clean shutdown while receiving updates."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()

                update_count = 0

                def on_price(t, y, n):
                    nonlocal update_count
                    update_count += 1

                manager.add_price_callback(on_price)
                manager.start()

                # Generate some updates
                for i in range(50):
                    mock_ws.simulate_price_update(f"T-{i}", Decimal("0.50"), Decimal("0.50"))

                # Stop while potentially receiving updates
                manager.stop()

                # Should have processed updates before shutdown
                assert update_count >= 50
                assert not manager.enabled


class TestStatisticsTracking:
    """E2E tests for statistics tracking across full workflow."""

    def test_statistics_accumulate_over_lifecycle(self) -> None:
        """Test statistics accumulate correctly over manager lifecycle."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()

                # Initial stats
                initial_stats = manager.stats
                assert initial_stats["websocket_updates"] == 0
                assert initial_stats["polling_updates"] == 0

                manager.start()

                # After start (initial poll)
                post_start_stats = manager.stats
                assert post_start_stats["polling_updates"] == 10  # From initial sync

                # After WebSocket updates
                for i in range(5):
                    mock_ws.simulate_price_update(f"T-{i}", Decimal("0.50"), Decimal("0.50"))

                mid_stats = manager.stats
                assert mid_stats["websocket_updates"] == 5

                # After force poll
                manager.force_poll()

                final_stats = manager.stats
                assert final_stats["polling_updates"] == 20  # 10 initial + 10 force poll

                manager.stop()

    def test_statistics_show_correct_source_status(self) -> None:
        """Test statistics reflect correct source statuses."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Both active
                stats = manager.stats
                assert stats["websocket_status"] == "active"
                assert stats["polling_status"] == "active"

                # Simulate WebSocket disconnect
                mock_ws.simulate_disconnect()
                stats = manager.stats
                assert stats["websocket_status"] == "offline"
                assert stats["polling_status"] == "active"

                manager.stop()


class TestDecimalPrecisionE2E:
    """E2E tests for Decimal precision preservation (Pattern 1)."""

    def test_decimal_precision_through_full_workflow(self) -> None:
        """Test Decimal precision is maintained through entire data flow."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()

                received_prices = []

                def on_price(ticker, yes, no):
                    received_prices.append((ticker, yes, no))

                manager.add_price_callback(on_price)
                manager.start()

                # Use high-precision prices
                mock_ws.simulate_price_update(
                    "PRECISE-TICKER",
                    Decimal("0.4975"),
                    Decimal("0.5025"),
                )

                # Verify callback received Decimal
                assert len(received_prices) == 1
                _, yes, no = received_prices[0]
                assert isinstance(yes, Decimal)
                assert isinstance(no, Decimal)
                assert yes == Decimal("0.4975")

                # Verify cache stores Decimal
                price = manager.get_current_price("PRECISE-TICKER")
                assert price is not None
                assert isinstance(price["yes_price"], Decimal)
                assert price["yes_price"] == Decimal("0.4975")

                manager.stop()

    def test_sub_penny_precision_preserved(self) -> None:
        """Test sub-penny precision is preserved in all operations."""
        mock_poller = MockPollerForE2E()
        mock_ws = MockWebSocketForE2E()

        with patch(
            "precog.schedulers.market_data_manager.KalshiMarketPoller", return_value=mock_poller
        ):
            with patch(
                "precog.schedulers.market_data_manager.KalshiWebSocketHandler", return_value=mock_ws
            ):
                manager = create_market_data_manager()
                manager.start()

                # Sub-penny prices that would lose precision as float
                sub_penny_prices = [
                    Decimal("0.3333"),
                    Decimal("0.6667"),
                    Decimal("0.1111"),
                    Decimal("0.9999"),
                ]

                for i, price in enumerate(sub_penny_prices):
                    mock_ws.simulate_price_update(f"T-{i}", price, Decimal("1") - price)

                # Verify all preserved exactly
                for i, price in enumerate(sub_penny_prices):
                    cached = manager.get_current_price(f"T-{i}")
                    assert cached is not None
                    assert cached["yes_price"] == price

                manager.stop()
