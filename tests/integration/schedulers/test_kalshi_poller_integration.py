"""
Integration tests for KalshiMarketPoller.

Tests the integration between KalshiMarketPoller and its dependencies:
- KalshiClient (mocked for isolation)
- Database CRUD operations (mocked)
- BasePoller (real implementation)

Reference: TESTING_STRATEGY_V3.2.md Section "Integration Tests"
Related Requirements: REQ-API-001 (Kalshi API Integration), REQ-DATA-005 (Market Price Data Collection)
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.kalshi_poller import (
    KalshiMarketPoller,
    create_kalshi_poller,
    run_single_kalshi_poll,
)

pytestmark = [pytest.mark.integration]


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_kalshi_client() -> MagicMock:
    """Create a mock Kalshi client."""
    client = MagicMock()
    client.get_markets.return_value = []
    client.close = MagicMock()
    return client


@pytest.fixture
def sample_market_data() -> list[dict[str, Any]]:
    """Create sample market data for testing."""
    return [
        {
            "ticker": "KXNFLGAME-NFL-2025-01-15-KC-BUF",
            "title": "KC vs BUF: Who will win?",
            "status": "active",
            "yes_ask_dollars": Decimal("0.5525"),
            "no_ask_dollars": Decimal("0.4575"),
            "yes_bid_dollars": Decimal("0.5475"),
            "no_bid_dollars": Decimal("0.4525"),
            "event_ticker": "EVT-KC-BUF-2025",
            "series_ticker": "KXNFLGAME",
            "volume": 15000,
            "open_interest": 5000,
        },
        {
            "ticker": "KXNFLGAME-NFL-2025-01-15-DET-PHI",
            "title": "DET vs PHI: Who will win?",
            "status": "active",
            "yes_ask_dollars": Decimal("0.6125"),
            "no_ask_dollars": Decimal("0.3975"),
            "yes_bid_dollars": Decimal("0.6075"),
            "no_bid_dollars": Decimal("0.3925"),
            "event_ticker": "EVT-DET-PHI-2025",
            "series_ticker": "KXNFLGAME",
            "volume": 22000,
            "open_interest": 8000,
        },
    ]


@pytest.fixture
def poller_with_mock_client(mock_kalshi_client: MagicMock) -> KalshiMarketPoller:
    """Create a poller with mocked Kalshi client."""
    with patch("precog.schedulers.kalshi_poller.KalshiClient", return_value=mock_kalshi_client):
        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=15,
            environment="demo",
        )
        poller.kalshi_client = mock_kalshi_client
        return poller


# =============================================================================
# Integration Tests: Poller and KalshiClient
# =============================================================================


class TestPollerClientIntegration:
    """Integration tests for poller and Kalshi client interaction."""

    def test_poller_uses_client_for_market_fetch(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
    ) -> None:
        """Poller should use KalshiClient to fetch markets."""
        mock_kalshi_client.get_markets.return_value = sample_market_data

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
            with patch("precog.schedulers.kalshi_poller.create_market"):
                with patch("precog.schedulers.kalshi_poller.get_or_create_event"):
                    result = poller_with_mock_client.poll_once()

        # Verify client was called
        mock_kalshi_client.get_markets.assert_called()
        assert result["items_fetched"] == len(sample_market_data)

    def test_poller_calls_client_with_correct_series(
        self,
        mock_kalshi_client: MagicMock,
    ) -> None:
        """Poller should call client with configured series ticker."""
        target_series = ["KXNCAAFGAME"]

        with patch("precog.schedulers.kalshi_poller.KalshiClient", return_value=mock_kalshi_client):
            poller = KalshiMarketPoller(
                series_tickers=target_series,
                environment="demo",
            )
            poller.kalshi_client = mock_kalshi_client

            with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
                with patch("precog.schedulers.kalshi_poller.create_market"):
                    with patch("precog.schedulers.kalshi_poller.get_or_create_event"):
                        poller.poll_once()

        # Verify correct series was requested
        mock_kalshi_client.get_markets.assert_called_with(
            series_ticker="KXNCAAFGAME",
            limit=KalshiMarketPoller.MAX_MARKETS_PER_REQUEST,
            cursor=None,
        )

    def test_poller_closes_client_on_stop(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
    ) -> None:
        """Poller should close client connection on stop."""
        poller_with_mock_client._on_stop()

        mock_kalshi_client.close.assert_called_once()


# =============================================================================
# Integration Tests: Poller and Database
# =============================================================================


class TestPollerDatabaseIntegration:
    """Integration tests for poller and database operations."""

    def test_new_market_creates_event_and_market(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
    ) -> None:
        """New markets should create both event and market records."""
        mock_kalshi_client.get_markets.return_value = [sample_market_data[0]]

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
            with patch("precog.schedulers.kalshi_poller.create_market") as mock_create:
                with patch("precog.schedulers.kalshi_poller.get_or_create_event") as mock_event:
                    result = poller_with_mock_client.poll_once()

        # Verify event and market were created
        mock_event.assert_called_once()
        mock_create.assert_called_once()
        assert result["items_created"] == 1

    def test_existing_market_with_price_change_updates(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
    ) -> None:
        """Existing markets with price changes should be updated."""
        market = sample_market_data[0]
        mock_kalshi_client.get_markets.return_value = [market]

        # Existing market with different price
        existing = {
            "yes_price": Decimal("0.5000"),  # Different from 0.5525
            "no_price": Decimal("0.5000"),
            "status": "open",
        }

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=existing):
            with patch(
                "precog.schedulers.kalshi_poller.update_market_with_versioning"
            ) as mock_update:
                result = poller_with_mock_client.poll_once()

        mock_update.assert_called_once()
        assert result["items_updated"] == 1

    def test_existing_market_no_change_skipped(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
    ) -> None:
        """Existing markets with no changes should be skipped."""
        market = sample_market_data[0]
        mock_kalshi_client.get_markets.return_value = [market]

        # Existing market with same price and status
        existing = {
            "yes_price": Decimal("0.5525"),
            "no_price": Decimal("0.4575"),
            "status": "open",  # "active" maps to "open"
        }

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=existing):
            with patch(
                "precog.schedulers.kalshi_poller.update_market_with_versioning"
            ) as mock_update:
                result = poller_with_mock_client.poll_once()

        mock_update.assert_not_called()
        assert result["items_updated"] == 0
        assert result["items_created"] == 0

    def test_status_change_triggers_update(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
    ) -> None:
        """Status changes should trigger market update."""
        market = sample_market_data[0].copy()
        market["status"] = "closed"  # Changed status
        mock_kalshi_client.get_markets.return_value = [market]

        existing = {
            "yes_price": Decimal("0.5525"),  # Same price
            "no_price": Decimal("0.4575"),
            "status": "open",  # Different status
        }

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=existing):
            with patch(
                "precog.schedulers.kalshi_poller.update_market_with_versioning"
            ) as mock_update:
                poller_with_mock_client.poll_once()

        mock_update.assert_called_once()
        # Verify status was updated to 'closed'
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["status"] == "closed"


# =============================================================================
# Integration Tests: Multiple Series Polling
# =============================================================================


class TestMultipleSeriesIntegration:
    """Integration tests for polling multiple series."""

    def test_polls_all_configured_series(
        self,
        mock_kalshi_client: MagicMock,
    ) -> None:
        """Poller should poll all configured series."""
        series = ["KXNFLGAME", "KXNCAAFGAME", "KXNBAGAME"]

        with patch("precog.schedulers.kalshi_poller.KalshiClient", return_value=mock_kalshi_client):
            poller = KalshiMarketPoller(
                series_tickers=series,
                environment="demo",
            )
            poller.kalshi_client = mock_kalshi_client

            with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
                with patch("precog.schedulers.kalshi_poller.create_market"):
                    with patch("precog.schedulers.kalshi_poller.get_or_create_event"):
                        poller.poll_once()

        # Verify each series was polled
        assert mock_kalshi_client.get_markets.call_count == len(series)

        called_series = [
            call[1]["series_ticker"] for call in mock_kalshi_client.get_markets.call_args_list
        ]
        assert set(called_series) == set(series)

    def test_series_error_does_not_stop_other_series(
        self,
        mock_kalshi_client: MagicMock,
    ) -> None:
        """Error in one series should not prevent polling other series."""
        series = ["KXNFLGAME", "KXNCAAFGAME"]

        # First call fails, second succeeds
        mock_kalshi_client.get_markets.side_effect = [
            Exception("API Error"),
            [],  # Empty success
        ]

        with patch("precog.schedulers.kalshi_poller.KalshiClient", return_value=mock_kalshi_client):
            poller = KalshiMarketPoller(
                series_tickers=series,
                environment="demo",
            )
            poller.kalshi_client = mock_kalshi_client

            with patch("precog.schedulers.kalshi_poller.get_current_market"):
                # Should not raise, and should call both
                poller._poll_once()

        assert mock_kalshi_client.get_markets.call_count == 2


# =============================================================================
# Integration Tests: Status Mapping
# =============================================================================


class TestStatusMappingIntegration:
    """Integration tests for status mapping during sync."""

    @pytest.mark.parametrize(
        ("api_status", "expected_db_status"),
        [
            ("active", "open"),
            ("unopened", "halted"),
            ("closed", "closed"),
            ("settled", "settled"),
            ("finalized", "settled"),
        ],
    )
    def test_status_mapped_correctly_on_create(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
        api_status: str,
        expected_db_status: str,
    ) -> None:
        """API status should be mapped correctly when creating markets."""
        market = sample_market_data[0].copy()
        market["status"] = api_status
        mock_kalshi_client.get_markets.return_value = [market]

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
            with patch("precog.schedulers.kalshi_poller.create_market") as mock_create:
                with patch("precog.schedulers.kalshi_poller.get_or_create_event"):
                    poller_with_mock_client.poll_once()

        # Verify correct status was passed
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["status"] == expected_db_status


# =============================================================================
# Integration Tests: Factory and Convenience Functions
# =============================================================================


class TestFactoryFunctionIntegration:
    """Integration tests for factory and convenience functions."""

    def test_create_kalshi_poller_returns_configured_instance(self) -> None:
        """Factory should return properly configured poller."""
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            poller = create_kalshi_poller(
                series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
                poll_interval=30,
                environment="demo",
            )

        assert isinstance(poller, KalshiMarketPoller)
        assert poller.series_tickers == ["KXNFLGAME", "KXNCAAFGAME"]
        assert poller.poll_interval == 30
        assert poller.environment == "demo"

    def test_run_single_poll_creates_and_closes_poller(
        self,
        mock_kalshi_client: MagicMock,
    ) -> None:
        """Single poll should create poller, poll, and close client."""
        with patch("precog.schedulers.kalshi_poller.KalshiClient", return_value=mock_kalshi_client):
            with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
                with patch("precog.schedulers.kalshi_poller.create_market"):
                    with patch("precog.schedulers.kalshi_poller.get_or_create_event"):
                        result = run_single_kalshi_poll(
                            series_tickers=["KXNFLGAME"],
                            environment="demo",
                        )

        assert isinstance(result, dict)
        assert "items_fetched" in result
        mock_kalshi_client.close.assert_called_once()


# =============================================================================
# Integration Tests: Fallback Price Handling
# =============================================================================


class TestFallbackPriceIntegration:
    """Integration tests for fallback price handling."""

    def test_uses_cents_when_dollars_missing(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
    ) -> None:
        """Should use cents fields when dollars fields missing."""
        market = {
            "ticker": "KXNFLGAME-TEST",
            "title": "Test Market",
            "status": "active",
            "yes_ask": 55,  # 55 cents
            "no_ask": 45,  # 45 cents
            # No _dollars fields
            "event_ticker": "EVT-TEST",
            "series_ticker": "KXNFLGAME",
        }
        mock_kalshi_client.get_markets.return_value = [market]

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
            with patch("precog.schedulers.kalshi_poller.create_market") as mock_create:
                with patch("precog.schedulers.kalshi_poller.get_or_create_event"):
                    poller_with_mock_client.poll_once()

        call_kwargs = mock_create.call_args[1]
        # Should be converted: 55 cents = 0.55
        assert call_kwargs["yes_price"] == Decimal("0.55")
        assert call_kwargs["no_price"] == Decimal("0.45")


# =============================================================================
# Integration Tests: Event Creation
# =============================================================================


class TestEventCreationIntegration:
    """Integration tests for event creation during market sync."""

    def test_event_created_with_correct_category(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        sample_market_data: list[dict[str, Any]],
    ) -> None:
        """Events should be created with correct category."""
        mock_kalshi_client.get_markets.return_value = [sample_market_data[0]]

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
            with patch("precog.schedulers.kalshi_poller.create_market"):
                with patch("precog.schedulers.kalshi_poller.get_or_create_event") as mock_event:
                    poller_with_mock_client.poll_once()

        call_kwargs = mock_event.call_args[1]
        assert call_kwargs["category"] == "sports"
        assert call_kwargs["subcategory"] == "nfl"

    @pytest.mark.parametrize(
        ("series_ticker", "expected_subcategory"),
        [
            ("KXNFLGAME", "nfl"),
            ("KXNCAAFGAME", "ncaaf"),
            ("KXNBAGAME", "nba"),
            ("KXNHLGAME", "nhl"),
            ("KXMLBGAME", "mlb"),
            ("KXOTHER", None),
        ],
    )
    def test_subcategory_determined_from_series(
        self,
        poller_with_mock_client: KalshiMarketPoller,
        mock_kalshi_client: MagicMock,
        series_ticker: str,
        expected_subcategory: str | None,
    ) -> None:
        """Subcategory should be determined from series ticker."""
        market = {
            "ticker": f"{series_ticker}-TEST",
            "title": "Test",
            "status": "active",
            "yes_ask_dollars": Decimal("0.50"),
            "no_ask_dollars": Decimal("0.50"),
            "event_ticker": "EVT-TEST",
            "series_ticker": series_ticker,
        }
        mock_kalshi_client.get_markets.return_value = [market]

        with patch("precog.schedulers.kalshi_poller.get_current_market", return_value=None):
            with patch("precog.schedulers.kalshi_poller.create_market"):
                with patch("precog.schedulers.kalshi_poller.get_or_create_event") as mock_event:
                    poller_with_mock_client.poll_once()

        call_kwargs = mock_event.call_args[1]
        assert call_kwargs["subcategory"] == expected_subcategory


# =============================================================================
# Integration Tests: BasePoller Integration
# =============================================================================


class TestBasePollerIntegration:
    """Integration tests for BasePoller inheritance."""

    def test_inherits_stats_tracking(
        self,
        poller_with_mock_client: KalshiMarketPoller,
    ) -> None:
        """Poller should inherit stats tracking from BasePoller."""
        stats = poller_with_mock_client.get_stats()

        assert "polls_completed" in stats
        assert "errors" in stats
        assert "last_poll" in stats

    def test_inherits_running_state(
        self,
        poller_with_mock_client: KalshiMarketPoller,
    ) -> None:
        """Poller should inherit running state from BasePoller."""
        assert poller_with_mock_client.is_running() is False

    def test_inherits_poll_interval_validation(self) -> None:
        """Poller should inherit poll interval validation."""
        with patch("precog.schedulers.kalshi_poller.KalshiClient"):
            # Very low interval should raise ValueError
            with pytest.raises(ValueError, match="poll_interval must be at least"):
                KalshiMarketPoller(poll_interval=1, environment="demo")
