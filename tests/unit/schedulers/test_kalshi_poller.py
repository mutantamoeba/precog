"""
Unit tests for Kalshi Market Poller.

Tests cover:
- Initialization and parameter validation
- Start/stop lifecycle management
- Stats tracking
- Poll logic with mocked API responses
- Database syncing with mocked CRUD operations
- Error handling and recovery

All tests use mocked responses - NO actual API calls or database operations.

Coverage Target: ≥85%
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from precog.schedulers.kalshi_poller import (
    KalshiMarketPoller,
    create_kalshi_poller,
    run_single_kalshi_poll,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_kalshi_client():
    """Create a mock KalshiClient for testing."""
    mock_client = Mock()
    mock_client.get_markets.return_value = []
    mock_client.close = Mock()
    return mock_client


@pytest.fixture
def mock_market_data():
    """Sample market data from Kalshi API (already Decimal-converted)."""
    return {
        "ticker": "KXNFLGAME-25NOV29-NEBUF-B250",
        "event_ticker": "KXNFLGAME-25NOV29-NEBUF",
        "series_ticker": "KXNFLGAME",
        "title": "Bills win by 25+ points?",
        "subtitle": "Buffalo Bills vs New England Patriots",
        "open_time": "2025-11-29T12:00:00Z",
        "close_time": "2025-11-29T20:00:00Z",
        "expiration_time": "2025-11-30T00:00:00Z",
        "status": "open",
        "can_close_early": True,
        "result": None,
        "yes_bid": 45,
        "yes_ask": 48,
        "no_bid": 52,
        "no_ask": 55,
        "yes_bid_dollars": Decimal("0.4500"),
        "yes_ask_dollars": Decimal("0.4800"),
        "no_bid_dollars": Decimal("0.5200"),
        "no_ask_dollars": Decimal("0.5500"),
        "last_price_dollars": Decimal("0.4700"),
        "volume": 1500,
        "open_interest": 800,
        "liquidity": 5000,
    }


@pytest.fixture
def mock_market_data_list(mock_market_data):
    """List of sample market data for testing."""
    market2 = mock_market_data.copy()
    market2["ticker"] = "KXNFLGAME-25NOV29-NEBUF-B210"
    market2["title"] = "Bills win by 21+ points?"
    market2["yes_ask_dollars"] = Decimal("0.3200")
    market2["no_ask_dollars"] = Decimal("0.6800")

    return [mock_market_data, market2]


@pytest.fixture
def poller_with_mock_client(mock_kalshi_client):
    """Create KalshiMarketPoller with mocked client."""
    return KalshiMarketPoller(
        series_tickers=["KXNFLGAME"],
        poll_interval=30,
        environment="demo",
        kalshi_client=mock_kalshi_client,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestKalshiMarketPollerInit:
    """Test KalshiMarketPoller initialization."""

    @pytest.mark.unit
    def test_init_with_defaults(self, mock_kalshi_client):
        """Test initialization with default parameters."""
        poller = KalshiMarketPoller(kalshi_client=mock_kalshi_client)

        assert poller.series_tickers == ["KXNFLGAME"]
        assert poller.poll_interval == 15  # Default: 15 seconds for near real-time
        assert poller.environment == "demo"
        assert poller.enabled is False

    @pytest.mark.unit
    def test_init_with_custom_series(self, mock_kalshi_client):
        """Test initialization with custom series tickers."""
        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
            kalshi_client=mock_kalshi_client,
        )

        assert poller.series_tickers == ["KXNFLGAME", "KXNCAAFGAME"]

    @pytest.mark.unit
    def test_init_with_custom_interval(self, mock_kalshi_client):
        """Test initialization with custom poll interval."""
        poller = KalshiMarketPoller(
            poll_interval=45,
            kalshi_client=mock_kalshi_client,
        )

        assert poller.poll_interval == 45

    @pytest.mark.unit
    def test_init_rejects_low_interval(self, mock_kalshi_client):
        """Test that poll_interval below minimum is rejected."""
        with pytest.raises(ValueError, match="at least 5 seconds"):
            KalshiMarketPoller(poll_interval=3, kalshi_client=mock_kalshi_client)

    @pytest.mark.unit
    def test_init_rejects_invalid_environment(self, mock_kalshi_client):
        """Test that invalid environment is rejected."""
        with pytest.raises(ValueError, match="must be 'demo' or 'prod'"):
            KalshiMarketPoller(environment="staging", kalshi_client=mock_kalshi_client)

    @pytest.mark.unit
    def test_init_stats_are_zeroed(self, mock_kalshi_client):
        """Test that initial stats are all zero."""
        poller = KalshiMarketPoller(kalshi_client=mock_kalshi_client)

        stats = poller.stats
        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0
        assert stats["last_poll"] is None
        assert stats["last_error"] is None


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestKalshiMarketPollerLifecycle:
    """Test start/stop lifecycle management."""

    @pytest.mark.unit
    def test_start_sets_enabled(self, poller_with_mock_client):
        """Test that start() sets enabled to True."""
        with patch.object(poller_with_mock_client, "_poll_wrapper"):
            poller_with_mock_client.start()
            assert poller_with_mock_client.enabled is True
            poller_with_mock_client.stop()

    @pytest.mark.unit
    def test_start_twice_raises_error(self, poller_with_mock_client):
        """Test that calling start() twice raises RuntimeError."""
        with patch.object(poller_with_mock_client, "_poll_wrapper"):
            poller_with_mock_client.start()

            with pytest.raises(RuntimeError, match="already running"):
                poller_with_mock_client.start()

            poller_with_mock_client.stop()

    @pytest.mark.unit
    def test_stop_sets_disabled(self, poller_with_mock_client):
        """Test that stop() sets enabled to False."""
        with patch.object(poller_with_mock_client, "_poll_wrapper"):
            poller_with_mock_client.start()
            poller_with_mock_client.stop()
            assert poller_with_mock_client.enabled is False

    @pytest.mark.unit
    def test_stop_when_not_running_logs_warning(self, poller_with_mock_client, caplog):
        """Test that stop() when not running logs warning."""
        poller_with_mock_client.stop()
        assert "not running" in caplog.text.lower()

    @pytest.mark.unit
    def test_stop_closes_kalshi_client(self, poller_with_mock_client):
        """Test that stop() closes the Kalshi client."""
        with patch.object(poller_with_mock_client, "_poll_wrapper"):
            poller_with_mock_client.start()
            poller_with_mock_client.stop()

            poller_with_mock_client.kalshi_client.close.assert_called_once()


# =============================================================================
# Poll Logic Tests
# =============================================================================


class TestKalshiMarketPollerPolling:
    """Test polling logic."""

    @pytest.mark.unit
    def test_poll_once_returns_counts(self, poller_with_mock_client, mock_market_data_list):
        """Test that poll_once returns correct counts."""
        poller_with_mock_client.kalshi_client.get_markets.return_value = mock_market_data_list

        with (
            patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None),
            patch("precog.schedulers.kalshi_poller.create_market", return_value="MKT-123"),
        ):
            result = poller_with_mock_client.poll_once()

            assert result["items_fetched"] == 2
            assert result["items_created"] == 2
            assert result["items_updated"] == 0

    @pytest.mark.unit
    def test_poll_once_updates_existing_markets(self, poller_with_mock_client, mock_market_data):
        """Test that poll_once updates existing markets."""
        poller_with_mock_client.kalshi_client.get_markets.return_value = [mock_market_data]

        existing_market = {
            "ticker": mock_market_data["ticker"],
            "yes_price": Decimal("0.4000"),  # Different price
            "no_price": Decimal("0.6000"),
            "status": "open",
        }

        with (
            patch(
                "precog.schedulers.kalshi_poller.get_current_market",
                return_value=existing_market,
            ),
            patch(
                "precog.schedulers.kalshi_poller.update_market_with_versioning",
                return_value=1,
            ),
        ):
            result = poller_with_mock_client.poll_once()

            assert result["items_fetched"] == 1
            assert result["items_updated"] == 1
            assert result["items_created"] == 0

    @pytest.mark.unit
    def test_poll_once_skips_unchanged_markets(self, poller_with_mock_client, mock_market_data):
        """Test that poll_once skips markets with unchanged prices."""
        poller_with_mock_client.kalshi_client.get_markets.return_value = [mock_market_data]

        # Same prices as mock_market_data
        existing_market = {
            "ticker": mock_market_data["ticker"],
            "yes_price": Decimal("0.4800"),  # Same as yes_ask_dollars
            "no_price": Decimal("0.5500"),  # Same as no_ask_dollars
            "status": "open",
        }

        with (
            patch(
                "precog.schedulers.kalshi_poller.get_current_market",
                return_value=existing_market,
            ),
            patch("precog.schedulers.kalshi_poller.update_market_with_versioning") as mock_update,
        ):
            result = poller_with_mock_client.poll_once()

            # Should not call update since prices haven't changed
            mock_update.assert_not_called()
            assert result["items_updated"] == 0

    @pytest.mark.unit
    def test_poll_updates_stats(self, poller_with_mock_client, mock_market_data_list):
        """Test that polling updates stats correctly."""
        poller_with_mock_client.kalshi_client.get_markets.return_value = mock_market_data_list

        with (
            patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None),
            patch("precog.schedulers.kalshi_poller.create_market", return_value="MKT-123"),
        ):
            poller_with_mock_client._poll_wrapper()

            stats = poller_with_mock_client.stats
            assert stats["polls_completed"] == 1
            assert stats["items_fetched"] == 2
            assert stats["items_created"] == 2
            assert stats["last_poll"] is not None

    @pytest.mark.unit
    def test_poll_handles_api_error(self, poller_with_mock_client):
        """Test that polling handles API errors gracefully."""
        poller_with_mock_client.kalshi_client.get_markets.side_effect = Exception("API Error")

        # Should not raise, just log error
        poller_with_mock_client._poll_wrapper()

        stats = poller_with_mock_client.stats
        assert stats["errors"] == 1
        assert "API Error" in stats["last_error"]


# =============================================================================
# Database Sync Tests
# =============================================================================


class TestKalshiMarketPollerSync:
    """Test database synchronization logic."""

    @pytest.mark.unit
    def test_sync_creates_new_market(self, poller_with_mock_client, mock_market_data):
        """Test that _sync_market_to_db creates new market."""
        with (
            patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None),
            patch(
                "precog.schedulers.kalshi_poller.create_market", return_value="MKT-123"
            ) as mock_create,
        ):
            was_created = poller_with_mock_client._sync_market_to_db(mock_market_data)

            assert was_created is True
            mock_create.assert_called_once()

            # Verify create_market was called with correct Decimal prices
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["yes_price"] == Decimal("0.4800")
            assert call_kwargs["no_price"] == Decimal("0.5500")

    @pytest.mark.unit
    def test_sync_updates_existing_market(self, poller_with_mock_client, mock_market_data):
        """Test that _sync_market_to_db updates existing market."""
        existing = {
            "ticker": mock_market_data["ticker"],
            "yes_price": Decimal("0.4000"),
            "no_price": Decimal("0.6000"),
            "status": "open",
        }

        with (
            patch("precog.schedulers.kalshi_poller.get_current_market", return_value=existing),
            patch(
                "precog.schedulers.kalshi_poller.update_market_with_versioning",
                return_value=1,
            ) as mock_update,
        ):
            was_created = poller_with_mock_client._sync_market_to_db(mock_market_data)

            assert was_created is False
            mock_update.assert_called_once()

    @pytest.mark.unit
    def test_sync_skips_market_without_ticker(self, poller_with_mock_client):
        """Test that _sync_market_to_db skips market without ticker."""
        market_without_ticker = {"title": "Some market", "yes_ask_dollars": Decimal("0.50")}

        result = poller_with_mock_client._sync_market_to_db(market_without_ticker)

        assert result is False

    @pytest.mark.unit
    def test_sync_uses_legacy_prices_when_dollars_missing(self, poller_with_mock_client):
        """Test fallback to legacy cent prices when _dollars fields missing."""
        market_legacy = {
            "ticker": "KXNFLGAME-TEST",
            "event_ticker": "KXNFLGAME-EVENT",
            "title": "Test Market",
            "yes_ask": 65,  # 65 cents = 0.65
            "no_ask": 35,  # 35 cents = 0.35
            "status": "open",
            # No *_dollars fields
        }

        with (
            patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None),
            patch(
                "precog.schedulers.kalshi_poller.create_market", return_value="MKT-123"
            ) as mock_create,
        ):
            poller_with_mock_client._sync_market_to_db(market_legacy)

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["yes_price"] == Decimal("0.65")
            assert call_kwargs["no_price"] == Decimal("0.35")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestKalshiPollerFactoryFunctions:
    """Test convenience factory functions."""

    @pytest.mark.unit
    def test_create_kalshi_poller_defaults(self):
        """Test create_kalshi_poller with defaults."""
        with patch("precog.schedulers.kalshi_poller.KalshiClient") as mock_client_class:
            mock_client_class.return_value = Mock()

            poller = create_kalshi_poller()

            assert poller.series_tickers == ["KXNFLGAME"]
            assert poller.poll_interval == 15  # Default: 15 seconds
            assert poller.environment == "demo"

    @pytest.mark.unit
    def test_create_kalshi_poller_custom(self):
        """Test create_kalshi_poller with custom parameters."""
        with patch("precog.schedulers.kalshi_poller.KalshiClient") as mock_client_class:
            mock_client_class.return_value = Mock()

            poller = create_kalshi_poller(
                series_tickers=["KXNCAAFGAME"],
                poll_interval=45,
                environment="prod",
            )

            assert poller.series_tickers == ["KXNCAAFGAME"]
            assert poller.poll_interval == 45
            assert poller.environment == "prod"

    @pytest.mark.unit
    def test_run_single_kalshi_poll(self, mock_kalshi_client):
        """Test run_single_kalshi_poll executes one poll."""
        with (
            patch(
                "precog.schedulers.kalshi_poller.KalshiClient",
                return_value=mock_kalshi_client,
            ),
            patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None),
            patch("precog.schedulers.kalshi_poller.create_market", return_value="MKT-123"),
        ):
            mock_kalshi_client.get_markets.return_value = [
                {"ticker": "TEST-MARKET", "event_ticker": "TEST", "title": "Test"}
            ]

            result = run_single_kalshi_poll(["KXNFLGAME"], environment="demo")

            assert "items_fetched" in result
            mock_kalshi_client.close.assert_called_once()


# =============================================================================
# Signal Handler Tests
# =============================================================================


class TestKalshiPollerSignalHandlers:
    """Test signal handler setup."""

    @pytest.mark.unit
    def test_setup_signal_handlers(self, poller_with_mock_client):
        """Test that setup_signal_handlers doesn't raise."""
        with patch("signal.signal"):
            # Should not raise
            poller_with_mock_client.setup_signal_handlers()
