"""
Integration tests for MarketDataManager.

Tests the hybrid orchestrator with realistic mocked dependencies, verifying
that the poller and WebSocket sources work together correctly.

Integration tests focus on:
    1. Source coordination - How polling and WebSocket interact
    2. Failover behavior - Switching between sources when one fails
    3. Data consistency - Cache updates from both sources
    4. Lifecycle management - Start/stop affecting both sources
    5. Statistics aggregation - Combined stats from both sources

Educational Note:
    Integration tests for hybrid data managers verify that multiple data sources
    coordinate properly. Unlike unit tests that isolate each component, integration
    tests verify the orchestration logic works with realistic (mocked) dependencies.

Reference: Phase 2 Live Data Integration
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
Related ADRs:
    - ADR-100: Service Supervisor Pattern
"""

import threading
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.kalshi_websocket import ConnectionState
from precog.schedulers.market_data_manager import (
    DataSourceStatus,
    MarketDataManager,
    create_market_data_manager,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_poller_class():
    """Create a mock KalshiMarketPoller class that returns mock instances."""
    with patch("precog.schedulers.market_data_manager.KalshiMarketPoller") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.enabled = False
        mock_instance.poll_once.return_value = {
            "markets_fetched": 10,
            "markets_updated": 5,
            "markets_created": 5,
        }
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


@pytest.fixture
def mock_websocket_class():
    """Create a mock KalshiWebSocketHandler class that returns mock instances."""
    with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.enabled = False
        mock_instance.state = ConnectionState.DISCONNECTED
        mock_instance.callbacks = []

        # Store callback when add_callback is called
        def add_callback(cb):
            mock_instance.callbacks.append(cb)

        mock_instance.add_callback.side_effect = add_callback
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


@pytest.fixture
def integrated_manager(mock_poller_class, mock_websocket_class):
    """Create a manager with both mocked sources for integration testing."""
    mock_poller_cls, mock_poller = mock_poller_class
    mock_ws_cls, mock_ws = mock_websocket_class

    manager = MarketDataManager(
        environment="demo",
        series_tickers=["KXNFLGAME"],
        enable_websocket=True,
        enable_polling=True,
    )

    yield {
        "manager": manager,
        "poller_cls": mock_poller_cls,
        "poller": mock_poller,
        "ws_cls": mock_ws_cls,
        "ws": mock_ws,
    }

    # Cleanup
    if manager.enabled:
        manager.stop(wait=False)


# =============================================================================
# Source Coordination Tests
# =============================================================================


class TestSourceCoordination:
    """Integration tests for polling and WebSocket coordination."""

    def test_start_initializes_both_sources(self, integrated_manager) -> None:
        """Verify start() initializes both polling and WebSocket sources."""
        manager = integrated_manager["manager"]
        mock_poller = integrated_manager["poller"]
        mock_ws = integrated_manager["ws"]

        manager.start()

        # Poller should have been created and started
        integrated_manager["poller_cls"].assert_called_once()
        mock_poller.poll_once.assert_called_once()  # Initial sync
        mock_poller.start.assert_called_once()

        # WebSocket should have been created and started
        integrated_manager["ws_cls"].assert_called_once()
        mock_ws.start.assert_called_once()

    def test_start_polling_first_for_initial_sync(self, integrated_manager) -> None:
        """Verify polling runs first for initial data sync before WebSocket."""
        call_order = []

        mock_poller = integrated_manager["poller"]
        mock_ws = integrated_manager["ws"]

        # Track call order - use function to track and return
        def poll_side_effect() -> dict[str, int]:
            call_order.append("poll")
            return {"markets_fetched": 10, "markets_updated": 5, "markets_created": 5}

        mock_poller.poll_once.side_effect = poll_side_effect
        mock_poller.start.side_effect = lambda: call_order.append("poller_start")
        mock_ws.start.side_effect = lambda: call_order.append("ws_start")

        integrated_manager["manager"].start()

        # Poll should happen before WebSocket start
        assert call_order.index("poll") < call_order.index("ws_start")

    def test_websocket_callback_registered(self, integrated_manager) -> None:
        """Verify WebSocket callback is registered for price updates."""
        manager = integrated_manager["manager"]
        mock_ws = integrated_manager["ws"]

        manager.start()

        # Callback should be registered
        mock_ws.add_callback.assert_called_once()

    def test_stop_stops_both_sources(self, integrated_manager) -> None:
        """Verify stop() cleanly shuts down both sources."""
        manager = integrated_manager["manager"]
        mock_poller = integrated_manager["poller"]
        mock_ws = integrated_manager["ws"]

        manager.start()
        manager.stop()

        # Both should be stopped
        mock_ws.stop.assert_called_once_with(wait=True)
        mock_poller.stop.assert_called_once_with(wait=True)

    def test_stop_websocket_before_polling(self, integrated_manager) -> None:
        """Verify WebSocket stops before polling (faster shutdown)."""
        call_order = []

        mock_poller = integrated_manager["poller"]
        mock_ws = integrated_manager["ws"]

        mock_ws.stop.side_effect = lambda wait=True: call_order.append("ws_stop")
        mock_poller.stop.side_effect = lambda wait=True: call_order.append("poller_stop")

        integrated_manager["manager"].start()
        integrated_manager["manager"].stop()

        # WebSocket should stop first
        assert call_order.index("ws_stop") < call_order.index("poller_stop")


# =============================================================================
# Failover Behavior Tests
# =============================================================================


class TestFailoverBehavior:
    """Integration tests for source failover behavior."""

    def test_primary_source_websocket_when_both_enabled(self, integrated_manager) -> None:
        """Verify WebSocket is primary when both sources enabled."""
        manager = integrated_manager["manager"]

        assert manager._primary_source == "websocket"

    def test_primary_source_polling_when_websocket_disabled(self) -> None:
        """Verify polling is primary when WebSocket disabled."""
        with patch("precog.schedulers.market_data_manager.KalshiMarketPoller") as mock_cls:
            mock_cls.return_value = MagicMock()
            mock_cls.return_value.poll_once.return_value = {
                "markets_fetched": 0,
                "markets_updated": 0,
                "markets_created": 0,
            }

            manager = MarketDataManager(
                environment="demo",
                enable_websocket=False,
                enable_polling=True,
            )

            assert manager._primary_source == "polling"

    def test_websocket_update_switches_primary_to_websocket(self, integrated_manager) -> None:
        """Verify WebSocket update switches primary source from polling."""
        manager = integrated_manager["manager"]

        # Start with polling as primary (simulating WebSocket disconnect)
        manager._primary_source = "polling"
        manager.start()

        # Simulate WebSocket update (reconnection)
        manager._on_websocket_update("TEST-TICKER", Decimal("0.50"), Decimal("0.50"))

        assert manager._primary_source == "websocket"

    def test_stats_track_primary_source_changes(self, integrated_manager) -> None:
        """Verify statistics track primary source changes."""
        manager = integrated_manager["manager"]

        # Start with polling primary
        manager._primary_source = "polling"
        manager.start()

        stats_before = manager.stats
        assert stats_before["primary_source"] == "polling"

        # WebSocket update switches primary
        manager._on_websocket_update("TEST", Decimal("0.50"), Decimal("0.50"))

        stats_after = manager.stats
        assert stats_after["primary_source"] == "websocket"


# =============================================================================
# Data Consistency Tests
# =============================================================================


class TestDataConsistency:
    """Integration tests for data consistency across sources."""

    def test_websocket_updates_cache(self, integrated_manager) -> None:
        """Verify WebSocket updates populate price cache."""
        manager = integrated_manager["manager"]
        manager.start()

        # Simulate WebSocket update
        manager._on_websocket_update(
            ticker="KXNFLGAME-25NOV21-DEN",
            yes_price=Decimal("0.65"),
            no_price=Decimal("0.35"),
        )

        price = manager.get_current_price("KXNFLGAME-25NOV21-DEN")
        assert price is not None
        assert price["source"] == "websocket"
        assert price["yes_price"] == Decimal("0.65")

    def test_multiple_websocket_updates_update_cache(self, integrated_manager) -> None:
        """Verify multiple WebSocket updates correctly update cache."""
        manager = integrated_manager["manager"]
        manager.start()

        # First update
        manager._on_websocket_update("TICKER-A", Decimal("0.50"), Decimal("0.50"))

        # Second update (same ticker, different price)
        manager._on_websocket_update("TICKER-A", Decimal("0.60"), Decimal("0.40"))

        price = manager.get_current_price("TICKER-A")
        assert price["yes_price"] == Decimal("0.60")

    def test_cache_isolated_per_ticker(self, integrated_manager) -> None:
        """Verify cache maintains separate entries per ticker."""
        manager = integrated_manager["manager"]
        manager.start()

        # Update two different tickers
        manager._on_websocket_update("TICKER-A", Decimal("0.60"), Decimal("0.40"))
        manager._on_websocket_update("TICKER-B", Decimal("0.70"), Decimal("0.30"))

        price_a = manager.get_current_price("TICKER-A")
        price_b = manager.get_current_price("TICKER-B")

        assert price_a["yes_price"] == Decimal("0.60")
        assert price_b["yes_price"] == Decimal("0.70")


# =============================================================================
# Lifecycle Management Tests
# =============================================================================


class TestLifecycleManagement:
    """Integration tests for manager lifecycle."""

    def test_full_lifecycle_start_stop(self, integrated_manager) -> None:
        """Verify full lifecycle: create -> start -> operate -> stop."""
        manager = integrated_manager["manager"]

        # Initially not enabled
        assert not manager.enabled

        # Start
        manager.start()
        assert manager.enabled

        # Operate (simulate update)
        manager._on_websocket_update("TEST", Decimal("0.50"), Decimal("0.50"))
        assert manager.get_current_price("TEST") is not None

        # Stop
        manager.stop()
        assert not manager.enabled

    def test_double_start_raises_error(self, integrated_manager) -> None:
        """Verify starting twice raises RuntimeError."""
        manager = integrated_manager["manager"]

        manager.start()

        with pytest.raises(RuntimeError, match="already running"):
            manager.start()

    def test_stop_when_not_running_is_safe(self, integrated_manager) -> None:
        """Verify stopping when not running is safe (no crash)."""
        manager = integrated_manager["manager"]

        # Should not raise
        manager.stop()
        assert not manager.enabled

    def test_restart_after_stop(self, integrated_manager) -> None:
        """Verify manager can restart after stopping."""
        manager = integrated_manager["manager"]
        mock_poller = integrated_manager["poller"]
        mock_ws = integrated_manager["ws"]

        # First cycle
        manager.start()
        manager.stop()

        # Reset mocks for second cycle
        mock_poller.reset_mock()
        mock_ws.reset_mock()

        # Recreate internal state for restart
        manager._poller = None
        manager._websocket = None

        # Second cycle
        manager.start()
        assert manager.enabled


# =============================================================================
# Statistics Aggregation Tests
# =============================================================================


class TestStatisticsAggregation:
    """Integration tests for statistics tracking across sources."""

    def test_initial_sync_updates_polling_stats(self, integrated_manager) -> None:
        """Verify initial sync updates polling statistics."""
        manager = integrated_manager["manager"]

        manager.start()

        stats = manager.stats
        assert stats["polling_updates"] == 10  # From mock poll_once return value
        assert stats["last_poll_update"] is not None

    def test_websocket_updates_increment_stats(self, integrated_manager) -> None:
        """Verify WebSocket updates increment statistics."""
        manager = integrated_manager["manager"]
        manager.start()

        # Multiple updates
        for i in range(5):
            manager._on_websocket_update(f"TICKER-{i}", Decimal("0.50"), Decimal("0.50"))

        stats = manager.stats
        assert stats["websocket_updates"] == 5
        assert stats["last_websocket_update"] is not None

    def test_stats_include_source_statuses(self, integrated_manager) -> None:
        """Verify statistics include both source statuses."""
        manager = integrated_manager["manager"]
        mock_poller = integrated_manager["poller"]
        mock_ws = integrated_manager["ws"]

        # Set up source states
        mock_poller.enabled = True
        mock_ws.state = ConnectionState.CONNECTED

        manager._poller = mock_poller
        manager._websocket = mock_ws
        manager._enabled = True

        stats = manager.stats
        assert stats["websocket_status"] == "active"
        assert stats["polling_status"] == "active"

    def test_stats_thread_safe(self, integrated_manager) -> None:
        """Verify statistics access is thread-safe."""
        manager = integrated_manager["manager"]
        manager.start()

        results = []
        errors = []

        def update_and_read():
            try:
                for i in range(10):
                    manager._on_websocket_update(f"T-{i}", Decimal("0.50"), Decimal("0.50"))
                    stats = manager.stats
                    results.append(stats["websocket_updates"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_and_read) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 30


# =============================================================================
# Callback Integration Tests
# =============================================================================


class TestCallbackIntegration:
    """Integration tests for callback system with both sources."""

    def test_callbacks_fired_on_websocket_updates(self, integrated_manager) -> None:
        """Verify callbacks fire when WebSocket updates arrive."""
        manager = integrated_manager["manager"]
        callback_data = []

        def callback(ticker, yes, no):
            callback_data.append((ticker, yes, no))

        manager.add_price_callback(callback)
        manager.start()

        # Simulate update
        manager._on_websocket_update("TEST-TICKER", Decimal("0.65"), Decimal("0.35"))

        assert len(callback_data) == 1
        assert callback_data[0] == ("TEST-TICKER", Decimal("0.65"), Decimal("0.35"))

    def test_multiple_callbacks_all_fired(self, integrated_manager) -> None:
        """Verify all registered callbacks are fired."""
        manager = integrated_manager["manager"]
        callback_counts = {"cb1": 0, "cb2": 0, "cb3": 0}

        manager.add_price_callback(
            lambda t, y, n: callback_counts.__setitem__("cb1", callback_counts["cb1"] + 1)
        )
        manager.add_price_callback(
            lambda t, y, n: callback_counts.__setitem__("cb2", callback_counts["cb2"] + 1)
        )
        manager.add_price_callback(
            lambda t, y, n: callback_counts.__setitem__("cb3", callback_counts["cb3"] + 1)
        )

        manager.start()
        manager._on_websocket_update("TEST", Decimal("0.50"), Decimal("0.50"))

        assert callback_counts["cb1"] == 1
        assert callback_counts["cb2"] == 1
        assert callback_counts["cb3"] == 1

    def test_callback_error_isolation(self, integrated_manager) -> None:
        """Verify one callback error doesn't affect others."""
        manager = integrated_manager["manager"]
        callback_data = []

        def bad_callback(t, y, n):
            raise ValueError("Test error")

        def good_callback(t, y, n):
            callback_data.append(t)

        manager.add_price_callback(bad_callback)
        manager.add_price_callback(good_callback)
        manager.start()

        # Should not raise, good callback should still run
        manager._on_websocket_update("TEST", Decimal("0.50"), Decimal("0.50"))

        assert "TEST" in callback_data


# =============================================================================
# Subscription Integration Tests
# =============================================================================


class TestSubscriptionIntegration:
    """Integration tests for market subscription across sources."""

    def test_subscribe_before_start(self, integrated_manager) -> None:
        """Verify subscriptions before start are stored."""
        manager = integrated_manager["manager"]

        manager.subscribe_markets(["TICKER-A", "TICKER-B"])

        assert "TICKER-A" in manager.market_tickers
        assert "TICKER-B" in manager.market_tickers

    def test_subscribe_after_start_forwards_to_websocket(self, integrated_manager) -> None:
        """Verify subscriptions after start are forwarded to WebSocket."""
        manager = integrated_manager["manager"]
        mock_ws = integrated_manager["ws"]

        manager.start()
        mock_ws.enabled = True

        manager.subscribe_markets(["TICKER-NEW"])

        mock_ws.subscribe.assert_called_with(["TICKER-NEW"])


# =============================================================================
# Factory Function Integration Tests
# =============================================================================


class TestFactoryFunctionIntegration:
    """Integration tests for create_market_data_manager factory."""

    def test_factory_creates_working_manager(self, mock_poller_class, mock_websocket_class) -> None:
        """Verify factory creates a fully functional manager."""
        manager = create_market_data_manager(
            environment="demo",
            series_tickers=["KXNFLGAME"],
            enable_websocket=True,
            enable_polling=True,
        )

        # Verify it's properly configured
        assert manager.environment == "demo"
        assert manager.series_tickers == ["KXNFLGAME"]

        # Verify it can start
        manager.start()
        assert manager.enabled

        manager.stop()

    def test_factory_polling_only_mode(self) -> None:
        """Verify factory creates polling-only manager."""
        with patch("precog.schedulers.market_data_manager.KalshiMarketPoller") as mock_cls:
            mock_cls.return_value = MagicMock()
            mock_cls.return_value.poll_once.return_value = {
                "markets_fetched": 0,
                "markets_updated": 0,
                "markets_created": 0,
            }

            manager = create_market_data_manager(
                enable_websocket=False,
                enable_polling=True,
            )

            assert manager.enable_websocket is False
            assert manager.enable_polling is True


# =============================================================================
# Force Poll Integration Tests
# =============================================================================


class TestForcePollIntegration:
    """Integration tests for force_poll functionality."""

    def test_force_poll_calls_poller(self, integrated_manager) -> None:
        """Verify force_poll triggers immediate poll cycle."""
        manager = integrated_manager["manager"]
        mock_poller = integrated_manager["poller"]

        manager.start()
        mock_poller.poll_once.reset_mock()

        result = manager.force_poll()

        mock_poller.poll_once.assert_called_once()
        assert result["markets_fetched"] == 10

    def test_force_poll_updates_stats(self, integrated_manager) -> None:
        """Verify force_poll updates statistics."""
        manager = integrated_manager["manager"]

        manager.start()
        initial_updates = manager.stats["polling_updates"]

        manager.force_poll()

        assert manager.stats["polling_updates"] > initial_updates

    def test_force_poll_when_polling_disabled_raises(self) -> None:
        """Verify force_poll raises when polling disabled."""
        with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler"):
            manager = MarketDataManager(
                environment="demo",
                enable_websocket=True,
                enable_polling=False,
            )

            with pytest.raises(RuntimeError, match="not enabled"):
                manager.force_poll()


# =============================================================================
# Data Source Status Integration Tests
# =============================================================================


class TestDataSourceStatusIntegration:
    """Integration tests for data source status reporting."""

    def test_status_reflects_connection_state(self, integrated_manager) -> None:
        """Verify status accurately reflects connection states."""
        manager = integrated_manager["manager"]
        mock_ws = integrated_manager["ws"]
        mock_poller = integrated_manager["poller"]

        manager.start()

        # Test connected state
        mock_ws.state = ConnectionState.CONNECTED
        mock_poller.enabled = True
        manager._websocket = mock_ws
        manager._poller = mock_poller

        assert manager.get_websocket_status() == DataSourceStatus.ACTIVE
        assert manager.get_polling_status() == DataSourceStatus.ACTIVE

    def test_status_reflects_reconnecting_state(self, integrated_manager) -> None:
        """Verify status shows degraded during reconnection."""
        manager = integrated_manager["manager"]
        mock_ws = integrated_manager["ws"]

        manager.start()
        mock_ws.state = ConnectionState.RECONNECTING
        manager._websocket = mock_ws

        assert manager.get_websocket_status() == DataSourceStatus.DEGRADED

    def test_status_reflects_disconnected_state(self, integrated_manager) -> None:
        """Verify status shows offline when disconnected."""
        manager = integrated_manager["manager"]
        mock_ws = integrated_manager["ws"]
        mock_poller = integrated_manager["poller"]

        manager.start()
        mock_ws.state = ConnectionState.DISCONNECTED
        mock_poller.enabled = False
        manager._websocket = mock_ws
        manager._poller = mock_poller

        assert manager.get_websocket_status() == DataSourceStatus.OFFLINE
        assert manager.get_polling_status() == DataSourceStatus.OFFLINE
