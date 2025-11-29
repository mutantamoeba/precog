"""
Unit tests for MarketDataManager.

Tests the hybrid orchestrator that coordinates polling and WebSocket sources.
Uses mocking to test without actual API connections.

Test Categories:
- Initialization and configuration
- Source management (start/stop)
- Price caching and retrieval
- Callback system
- Failover behavior
- Statistics tracking

Reference: Phase 2 Live Data Integration
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-DATA-005: Market Price Data Collection
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.kalshi_websocket import ConnectionState
from precog.schedulers.market_data_manager import (
    DataSourceStatus,
    MarketDataManager,
    create_market_data_manager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_poller():
    """Create a mock KalshiMarketPoller."""
    poller = MagicMock()
    poller.enabled = False
    poller.poll_once.return_value = {
        "markets_fetched": 10,
        "markets_updated": 5,
        "markets_created": 5,
    }
    return poller


@pytest.fixture
def mock_websocket():
    """Create a mock KalshiWebSocketHandler."""
    ws = MagicMock()
    ws.enabled = False
    ws.state = ConnectionState.DISCONNECTED
    return ws


@pytest.fixture
def manager():
    """Create a manager with both sources disabled for testing."""
    # We need at least one source, so we'll patch during tests
    with patch("precog.schedulers.market_data_manager.KalshiMarketPoller") as mock_poller_cls:
        with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler") as mock_ws_cls:
            mock_poller_cls.return_value = MagicMock()
            mock_poller_cls.return_value.poll_once.return_value = {
                "markets_fetched": 0,
                "markets_updated": 0,
                "markets_created": 0,
            }
            mock_ws_cls.return_value = MagicMock()
            mock_ws_cls.return_value.state = ConnectionState.DISCONNECTED

            mgr = MarketDataManager(
                environment="demo",
                series_tickers=["KXNFLGAME"],
                enable_websocket=True,
                enable_polling=True,
            )
            yield mgr


@pytest.fixture
def manager_polling_only():
    """Create a manager with only polling enabled."""
    with patch("precog.schedulers.market_data_manager.KalshiMarketPoller") as mock_poller_cls:
        mock_poller_cls.return_value = MagicMock()
        mock_poller_cls.return_value.poll_once.return_value = {
            "markets_fetched": 0,
            "markets_updated": 0,
            "markets_created": 0,
        }

        mgr = MarketDataManager(
            environment="demo",
            enable_websocket=False,
            enable_polling=True,
        )
        yield mgr


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Tests for MarketDataManager initialization."""

    def test_default_initialization(self, manager):
        """Test manager initializes with default settings."""
        assert manager.environment == "demo"
        assert manager.series_tickers == ["KXNFLGAME"]
        assert manager.enable_websocket is True
        assert manager.enable_polling is True
        assert manager.enabled is False

    def test_custom_series_tickers(self):
        """Test manager accepts custom series tickers."""
        with patch("precog.schedulers.market_data_manager.KalshiMarketPoller"):
            with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler"):
                mgr = MarketDataManager(
                    environment="demo",
                    series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
                )
                assert mgr.series_tickers == ["KXNFLGAME", "KXNCAAFGAME"]

    def test_invalid_environment_raises(self):
        """Test invalid environment raises ValueError."""
        with pytest.raises(ValueError, match="environment must be"):
            MarketDataManager(environment="invalid")

    def test_both_sources_disabled_raises(self):
        """Test disabling both sources raises ValueError."""
        with pytest.raises(ValueError, match="At least one data source"):
            MarketDataManager(
                environment="demo",
                enable_websocket=False,
                enable_polling=False,
            )

    def test_polling_only_mode(self, manager_polling_only):
        """Test manager works with only polling enabled."""
        assert manager_polling_only.enable_websocket is False
        assert manager_polling_only.enable_polling is True

    def test_websocket_only_mode(self):
        """Test manager works with only WebSocket enabled."""
        with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler"):
            mgr = MarketDataManager(
                environment="demo",
                enable_websocket=True,
                enable_polling=False,
            )
            assert mgr.enable_websocket is True
            assert mgr.enable_polling is False

    def test_initial_stats(self, manager):
        """Test initial statistics are zero."""
        stats = manager.stats

        assert stats["websocket_updates"] == 0
        assert stats["polling_updates"] == 0
        assert stats["failovers"] == 0
        assert stats["validation_mismatches"] == 0
        assert stats["last_websocket_update"] is None
        assert stats["last_poll_update"] is None


# =============================================================================
# Callback Tests
# =============================================================================


class TestCallbacks:
    """Tests for callback management."""

    def test_add_callback(self, manager):
        """Test adding a callback."""
        callback = MagicMock()
        manager.add_price_callback(callback)

        assert callback in manager._callbacks

    def test_remove_callback(self, manager):
        """Test removing a callback."""
        callback = MagicMock()
        manager.add_price_callback(callback)
        manager.remove_price_callback(callback)

        assert callback not in manager._callbacks

    def test_remove_nonexistent_callback_is_safe(self, manager):
        """Test removing non-existent callback is safe."""
        callback = MagicMock()
        manager.remove_price_callback(callback)  # Should not raise

    def test_callback_fired_on_websocket_update(self, manager):
        """Test callback is fired when WebSocket update received."""
        callback = MagicMock()
        manager.add_price_callback(callback)

        # Simulate WebSocket update
        manager._on_websocket_update(
            ticker="TEST-TICKER",
            yes_price=Decimal("0.65"),
            no_price=Decimal("0.35"),
        )

        callback.assert_called_once_with(
            "TEST-TICKER",
            Decimal("0.65"),
            Decimal("0.35"),
        )

    def test_callback_error_doesnt_crash(self, manager):
        """Test callback error doesn't crash update processing."""
        callback = MagicMock(side_effect=ValueError("Test error"))
        manager.add_price_callback(callback)

        # Should not raise
        manager._on_websocket_update(
            ticker="TEST-TICKER",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
        )


# =============================================================================
# Price Cache Tests
# =============================================================================


class TestPriceCache:
    """Tests for price caching."""

    def test_cache_update_on_websocket(self, manager):
        """Test cache is updated on WebSocket update."""
        manager._on_websocket_update(
            ticker="TEST-TICKER",
            yes_price=Decimal("0.65"),
            no_price=Decimal("0.35"),
        )

        price = manager.get_current_price("TEST-TICKER")
        assert price is not None
        assert price["ticker"] == "TEST-TICKER"
        assert price["yes_price"] == Decimal("0.65")
        assert price["no_price"] == Decimal("0.35")
        assert price["source"] == "websocket"

    def test_get_nonexistent_price_returns_none(self, manager):
        """Test getting non-existent ticker returns None."""
        price = manager.get_current_price("NONEXISTENT")
        assert price is None

    def test_get_all_prices(self, manager):
        """Test getting all cached prices."""
        # Add some prices
        manager._on_websocket_update("TICKER-A", Decimal("0.60"), Decimal("0.40"))
        manager._on_websocket_update("TICKER-B", Decimal("0.70"), Decimal("0.30"))

        prices = manager.get_all_prices()
        assert len(prices) == 2
        assert "TICKER-A" in prices
        assert "TICKER-B" in prices

    def test_stale_detection(self, manager):
        """Test stale data detection."""
        # Add a price
        manager._on_websocket_update("TEST-TICKER", Decimal("0.50"), Decimal("0.50"))

        # Get price (should not be stale)
        price = manager.get_current_price("TEST-TICKER")
        assert price is not None
        assert price["is_stale"] is False

        # Manually set old timestamp to test staleness
        with manager._cache_lock:
            old_time = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
            manager._price_cache["TEST-TICKER"]["timestamp"] = old_time

        # Get price again (should be stale)
        price = manager.get_current_price("TEST-TICKER")
        assert price is not None
        assert price["is_stale"] is True


# =============================================================================
# Subscription Tests
# =============================================================================


class TestSubscriptions:
    """Tests for market subscription."""

    def test_subscribe_markets(self, manager):
        """Test subscribing to markets."""
        manager.subscribe_markets(["TICKER-A", "TICKER-B"])

        assert "TICKER-A" in manager.market_tickers
        assert "TICKER-B" in manager.market_tickers

    def test_subscribe_forwards_to_websocket(self, manager):
        """Test subscribe forwards to WebSocket when active."""
        manager._websocket = MagicMock()
        manager._websocket.enabled = True

        manager.subscribe_markets(["TICKER-A"])

        manager._websocket.subscribe.assert_called_once_with(["TICKER-A"])


# =============================================================================
# State Management Tests
# =============================================================================


class TestStateManagement:
    """Tests for start/stop and state management."""

    def test_initial_state_not_enabled(self, manager):
        """Test manager starts in disabled state."""
        assert manager.enabled is False

    def test_start_enables_manager(self, manager):
        """Test start enables the manager."""
        manager.start()
        assert manager.enabled is True

    def test_start_when_already_running_raises(self, manager):
        """Test starting when already running raises error."""
        manager.start()

        with pytest.raises(RuntimeError, match="already running"):
            manager.start()

    def test_stop_when_not_running_warns(self, manager):
        """Test stop when not running logs warning but doesn't crash."""
        manager.stop()  # Should not raise
        assert manager.enabled is False

    def test_stop_disables_manager(self, manager):
        """Test stop disables the manager."""
        manager.start()
        manager.stop()

        assert manager.enabled is False


# =============================================================================
# Data Source Status Tests
# =============================================================================


class TestDataSourceStatus:
    """Tests for data source status checking."""

    def test_websocket_status_offline_when_none(self, manager):
        """Test WebSocket status is offline when not initialized."""
        manager._websocket = None
        assert manager.get_websocket_status() == DataSourceStatus.OFFLINE

    def test_websocket_status_active_when_connected(self, manager):
        """Test WebSocket status is active when connected."""
        manager._websocket = MagicMock()
        manager._websocket.state = ConnectionState.CONNECTED

        assert manager.get_websocket_status() == DataSourceStatus.ACTIVE

    def test_websocket_status_degraded_when_reconnecting(self, manager):
        """Test WebSocket status is degraded when reconnecting."""
        manager._websocket = MagicMock()
        manager._websocket.state = ConnectionState.RECONNECTING

        assert manager.get_websocket_status() == DataSourceStatus.DEGRADED

    def test_polling_status_offline_when_none(self, manager):
        """Test polling status is offline when not initialized."""
        manager._poller = None
        assert manager.get_polling_status() == DataSourceStatus.OFFLINE

    def test_polling_status_active_when_enabled(self, manager):
        """Test polling status is active when enabled."""
        manager._poller = MagicMock()
        manager._poller.enabled = True

        assert manager.get_polling_status() == DataSourceStatus.ACTIVE


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    def test_websocket_update_increments_stats(self, manager):
        """Test WebSocket update increments statistics."""
        manager._on_websocket_update("TEST", Decimal("0.50"), Decimal("0.50"))

        stats = manager.stats
        assert stats["websocket_updates"] == 1
        assert stats["last_websocket_update"] is not None

    def test_primary_source_switches_to_websocket(self, manager):
        """Test primary source switches to websocket on update."""
        # Start with polling as primary (websocket not connected)
        manager._primary_source = "polling"

        # WebSocket update should switch to websocket
        manager._on_websocket_update("TEST", Decimal("0.50"), Decimal("0.50"))

        assert manager._primary_source == "websocket"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_market_data_manager factory function."""

    def test_creates_manager_with_defaults(self):
        """Test factory creates manager with default settings."""
        with patch("precog.schedulers.market_data_manager.KalshiMarketPoller"):
            with patch("precog.schedulers.market_data_manager.KalshiWebSocketHandler"):
                mgr = create_market_data_manager()

                assert mgr.environment == "demo"
                assert mgr.enable_websocket is True
                assert mgr.enable_polling is True

    def test_creates_manager_with_custom_settings(self):
        """Test factory passes custom settings to manager."""
        with patch("precog.schedulers.market_data_manager.KalshiMarketPoller"):
            mgr = create_market_data_manager(
                environment="prod",
                series_tickers=["CUSTOM"],
                enable_websocket=False,
                enable_polling=True,
            )

            assert mgr.environment == "prod"
            assert mgr.series_tickers == ["CUSTOM"]
            assert mgr.enable_websocket is False


# =============================================================================
# Decimal Precision Tests (Pattern 1)
# =============================================================================


class TestDecimalPrecision:
    """Tests ensuring Decimal precision is maintained."""

    def test_prices_stored_as_decimal(self, manager):
        """Test prices are stored as Decimal in cache."""
        manager._on_websocket_update(
            ticker="TEST",
            yes_price=Decimal("0.4975"),
            no_price=Decimal("0.5025"),
        )

        price = manager.get_current_price("TEST")
        assert price is not None
        assert isinstance(price["yes_price"], Decimal)
        assert isinstance(price["no_price"], Decimal)
        assert price["yes_price"] == Decimal("0.4975")
        assert price["no_price"] == Decimal("0.5025")

    def test_sub_penny_precision_preserved(self, manager):
        """Test sub-penny precision is preserved."""
        # Use typical Kalshi sub-penny prices
        manager._on_websocket_update(
            ticker="TEST",
            yes_price=Decimal("0.3333"),
            no_price=Decimal("0.6667"),
        )

        price = manager.get_current_price("TEST")
        assert price is not None
        assert price["yes_price"] == Decimal("0.3333")
        assert price["no_price"] == Decimal("0.6667")


# =============================================================================
# DataSourceStatus Enum Tests
# =============================================================================


class TestDataSourceStatusEnum:
    """Tests for DataSourceStatus enum."""

    def test_all_statuses_have_values(self):
        """Test all statuses have string values."""
        assert DataSourceStatus.ACTIVE.value == "active"
        assert DataSourceStatus.DEGRADED.value == "degraded"
        assert DataSourceStatus.OFFLINE.value == "offline"
