"""
End-to-end tests for KalshiClient.

Tests complete workflows for the Kalshi API client, verifying that all
components work together correctly from initialization through data retrieval.

E2E Test Scenarios:
    1. Complete client lifecycle - Initialize, authenticate, fetch data, close
    2. Market data workflows - Get markets, filter by series, pagination
    3. Portfolio workflows - Balance, positions, fills, settlements
    4. Error recovery - Retry logic, rate limiting handling
    5. Decimal precision - Prices maintain precision through all operations

Educational Note:
    E2E tests for API clients verify complete user workflows work correctly.
    They use mocked HTTP responses to simulate realistic API interactions
    without requiring actual API credentials or network access.

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-API-002: RSA-PSS Authentication
    - REQ-SYS-003: Decimal Precision for Prices
Related ADRs:
    - ADR-048: Decimal-First Response Parsing
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests

from precog.api_connectors.kalshi_client import KalshiClient
from precog.api_connectors.rate_limiter import RateLimiter

pytestmark = [pytest.mark.e2e]


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_auth():
    """Create mock authentication that returns valid headers."""
    auth = MagicMock()
    auth.get_headers.return_value = {
        "Authorization": "Bearer mock-token",
        "Content-Type": "application/json",
    }
    return auth


@pytest.fixture
def mock_session():
    """Create mock session for HTTP requests."""
    return MagicMock(spec=requests.Session)


@pytest.fixture
def mock_rate_limiter():
    """Create mock rate limiter that doesn't block."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.wait_if_needed.return_value = None
    return limiter


@pytest.fixture
def client(mock_auth, mock_session, mock_rate_limiter):
    """Create KalshiClient with mocked dependencies."""
    return KalshiClient(
        environment="demo",
        auth=mock_auth,
        session=mock_session,
        rate_limiter=mock_rate_limiter,
    )


def create_mock_response(data: dict, status_code: int = 200):
    """Helper to create mock HTTP responses."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    response.text = json.dumps(data)
    response.headers = {}

    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"HTTP Error: {status_code}")
    else:
        response.raise_for_status.return_value = None

    return response


# =============================================================================
# Client Lifecycle Tests
# =============================================================================


class TestClientLifecycle:
    """E2E tests for complete client lifecycle."""

    def test_initialize_authenticate_fetch_close(self, mock_auth, mock_rate_limiter) -> None:
        """Test complete lifecycle: init -> auth -> fetch -> close."""
        # Create real session that we'll mock
        with patch.object(requests, "Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            # Setup market response
            mock_session.request.return_value = create_mock_response(
                {
                    "markets": [
                        {
                            "ticker": "TEST-MARKET-1",
                            "yes_ask_dollars": "0.6500",
                            "yes_bid_dollars": "0.6400",
                        }
                    ]
                }
            )

            # 1. Initialize
            client = KalshiClient(
                environment="demo",
                auth=mock_auth,
                rate_limiter=mock_rate_limiter,
            )

            # 2. Authenticate (implicit in get_markets)
            # 3. Fetch data
            markets = client.get_markets()

            # Verify auth was called
            mock_auth.get_headers.assert_called()

            # Verify data received
            assert len(markets) == 1
            assert markets[0]["ticker"] == "TEST-MARKET-1"

            # 4. Close
            client.close()
            mock_session.close.assert_called_once()

    def test_multiple_operations_same_client(self, client, mock_session) -> None:
        """Test multiple operations with same client instance."""
        # Setup responses for multiple calls
        mock_session.request.side_effect = [
            create_mock_response({"balance": "1000.00"}),
            create_mock_response({"markets": [{"ticker": "M1", "yes_ask_dollars": "0.50"}]}),
            create_mock_response({"positions": [{"ticker": "M1", "position": 10}]}),
        ]

        # Multiple operations
        balance = client.get_balance()
        markets = client.get_markets()
        positions = client.get_positions()

        # Verify all succeeded
        assert balance == Decimal("1000.00")
        assert len(markets) == 1
        assert len(positions) == 1

        # Verify session reused (3 calls on same session)
        assert mock_session.request.call_count == 3


# =============================================================================
# Market Data Workflow Tests
# =============================================================================


class TestMarketDataWorkflows:
    """E2E tests for market data retrieval workflows."""

    def test_get_markets_with_series_filter(self, client, mock_session) -> None:
        """Test fetching markets filtered by series ticker."""
        mock_session.request.return_value = create_mock_response(
            {
                "markets": [
                    {"ticker": "KXNFLGAME-DEN", "yes_ask_dollars": "0.65"},
                    {"ticker": "KXNFLGAME-KC", "yes_ask_dollars": "0.55"},
                ]
            }
        )

        markets = client.get_markets(series_ticker="KXNFLGAME")

        # Verify request params
        call_args = mock_session.request.call_args
        assert "KXNFLGAME" in str(call_args)

        # Verify results
        assert len(markets) == 2
        assert all("KXNFLGAME" in m["ticker"] for m in markets)

    def test_get_markets_pagination_workflow(self, client, mock_session) -> None:
        """Test paginated market fetching workflow."""
        # First page
        mock_session.request.side_effect = [
            create_mock_response(
                {
                    "markets": [{"ticker": f"M{i}", "yes_ask_dollars": "0.50"} for i in range(100)],
                    "cursor": "next_page_cursor",
                }
            ),
            create_mock_response(
                {
                    "markets": [
                        {"ticker": f"M{i}", "yes_ask_dollars": "0.50"} for i in range(100, 150)
                    ],
                }
            ),
        ]

        # Fetch first page
        page1 = client.get_markets(limit=100)
        assert len(page1) == 100

        # Fetch second page
        page2 = client.get_markets(limit=100, cursor="next_page_cursor")
        assert len(page2) == 50

        # Total markets retrieved
        assert len(page1) + len(page2) == 150

    def test_get_single_market_details(self, client, mock_session) -> None:
        """Test fetching single market with full details."""
        mock_session.request.return_value = create_mock_response(
            {
                "market": {
                    "ticker": "KXNFLGAME-DEN-W",
                    "title": "Denver Broncos Win",
                    "status": "active",
                    "yes_ask_dollars": "0.6500",
                    "yes_bid_dollars": "0.6400",
                    "no_ask_dollars": "0.3600",
                    "no_bid_dollars": "0.3500",
                    "volume": 10000,
                }
            }
        )

        market = client.get_market("KXNFLGAME-DEN-W")

        assert market["ticker"] == "KXNFLGAME-DEN-W"
        assert market["yes_ask_dollars"] == Decimal("0.6500")
        assert market["no_ask_dollars"] == Decimal("0.3600")


# =============================================================================
# Portfolio Workflow Tests
# =============================================================================


class TestPortfolioWorkflows:
    """E2E tests for portfolio data retrieval workflows."""

    def test_complete_portfolio_overview(self, client, mock_session) -> None:
        """Test fetching complete portfolio overview."""
        mock_session.request.side_effect = [
            # Balance
            create_mock_response({"balance": "5000.00"}),
            # Open positions
            create_mock_response(
                {
                    "positions": [
                        {
                            "ticker": "M1",
                            "position": 100,
                            "user_average_price": "0.4500",
                            "realized_pnl": "0.00",
                        },
                        {
                            "ticker": "M2",
                            "position": -50,
                            "user_average_price": "0.6000",
                            "realized_pnl": "25.00",
                        },
                    ]
                }
            ),
            # Recent fills
            create_mock_response(
                {
                    "fills": [
                        {
                            "ticker": "M1",
                            "count": 50,
                            "yes_price_fixed": "0.4500",
                            "side": "yes",
                        }
                    ]
                }
            ),
        ]

        # Get portfolio overview
        balance = client.get_balance()
        positions = client.get_positions(status="open")
        fills = client.get_fills(limit=10)

        # Verify complete overview
        assert balance == Decimal("5000.00")
        assert len(positions) == 2
        assert len(fills) == 1

        # Verify Decimal precision maintained
        assert positions[0]["user_average_price"] == Decimal("0.4500")
        assert fills[0]["yes_price_fixed"] == Decimal("0.4500")

    def test_filter_positions_by_status(self, client, mock_session) -> None:
        """Test filtering positions by status."""
        mock_session.request.return_value = create_mock_response(
            {
                "positions": [
                    {"ticker": "M1", "position": 100, "status": "open"},
                ]
            }
        )

        open_positions = client.get_positions(status="open")

        # Verify filter applied
        call_args = mock_session.request.call_args
        assert "open" in str(call_args)

        assert len(open_positions) == 1

    def test_get_settlements_workflow(self, client, mock_session) -> None:
        """Test fetching settlement history."""
        mock_session.request.return_value = create_mock_response(
            {
                "settlements": [
                    {
                        "ticker": "M1",
                        "market_result": "yes",
                        "settlement_value": "1.00",
                        "revenue": "50.00",
                    },
                    {
                        "ticker": "M2",
                        "market_result": "no",
                        "settlement_value": "0.00",
                        "revenue": "-25.00",
                    },
                ]
            }
        )

        settlements = client.get_settlements()

        assert len(settlements) == 2
        assert settlements[0]["settlement_value"] == Decimal("1.00")
        assert settlements[1]["revenue"] == Decimal("-25.00")


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """E2E tests for error handling and recovery."""

    def test_retry_on_server_error(self, client, mock_session) -> None:
        """Test automatic retry on 5xx server errors."""
        # First two calls fail, third succeeds
        mock_session.request.side_effect = [
            create_mock_response({"error": "Server Error"}, 500),
            create_mock_response({"error": "Server Error"}, 503),
            create_mock_response({"balance": "1000.00"}),
        ]

        # Patch time.sleep to speed up test
        with patch("time.sleep"):
            balance = client.get_balance()

        assert balance == Decimal("1000.00")
        assert mock_session.request.call_count == 3

    def test_no_retry_on_client_error(self, client, mock_session) -> None:
        """Test no retry on 4xx client errors."""
        mock_session.request.return_value = create_mock_response({"error": "Bad Request"}, 400)

        with pytest.raises(requests.HTTPError):
            client.get_balance()

        # Should only try once (no retry)
        assert mock_session.request.call_count == 1

    def test_rate_limit_handling(self, client, mock_session, mock_rate_limiter) -> None:
        """Test rate limit error triggers limiter handling."""
        response = create_mock_response({"error": "Rate limited"}, 429)
        response.headers = {"Retry-After": "60"}
        mock_session.request.return_value = response

        with pytest.raises(requests.HTTPError):
            client.get_markets()

        # Rate limiter should be notified
        mock_rate_limiter.handle_rate_limit_error.assert_called()


# =============================================================================
# Decimal Precision Tests
# =============================================================================


class TestDecimalPrecisionE2E:
    """E2E tests for Decimal precision throughout workflows."""

    def test_market_prices_decimal_precision(self, client, mock_session) -> None:
        """Test market prices maintain Decimal precision."""
        mock_session.request.return_value = create_mock_response(
            {
                "markets": [
                    {
                        "ticker": "TEST",
                        "yes_ask_dollars": "0.4975",  # Sub-penny price
                        "yes_bid_dollars": "0.4925",
                        "no_ask_dollars": "0.5075",
                        "no_bid_dollars": "0.5025",
                    }
                ]
            }
        )

        markets = client.get_markets()
        market = markets[0]

        # All prices should be Decimal
        assert isinstance(market["yes_ask_dollars"], Decimal)
        assert isinstance(market["yes_bid_dollars"], Decimal)
        assert isinstance(market["no_ask_dollars"], Decimal)
        assert isinstance(market["no_bid_dollars"], Decimal)

        # Exact values preserved
        assert market["yes_ask_dollars"] == Decimal("0.4975")
        assert market["no_ask_dollars"] == Decimal("0.5075")

    def test_position_prices_decimal_precision(self, client, mock_session) -> None:
        """Test position prices maintain Decimal precision."""
        mock_session.request.return_value = create_mock_response(
            {
                "positions": [
                    {
                        "ticker": "TEST",
                        "position": 100,
                        "user_average_price": "0.3333",  # Repeating decimal
                        "realized_pnl": "12.5678",
                        "total_cost": "33.33",
                    }
                ]
            }
        )

        positions = client.get_positions()
        position = positions[0]

        # Exact precision preserved
        assert position["user_average_price"] == Decimal("0.3333")
        assert position["realized_pnl"] == Decimal("12.5678")
        assert position["total_cost"] == Decimal("33.33")

    def test_fill_prices_decimal_precision(self, client, mock_session) -> None:
        """Test fill prices maintain Decimal precision."""
        mock_session.request.return_value = create_mock_response(
            {
                "fills": [
                    {
                        "ticker": "TEST",
                        "count": 10,
                        "yes_price_fixed": "0.9600",  # Fill uses _fixed suffix
                        "no_price_fixed": "0.0400",
                    }
                ]
            }
        )

        fills = client.get_fills()
        fill = fills[0]

        assert fill["yes_price_fixed"] == Decimal("0.9600")
        assert fill["no_price_fixed"] == Decimal("0.0400")

    def test_balance_decimal_precision(self, client, mock_session) -> None:
        """Test balance maintains Decimal precision."""
        mock_session.request.return_value = create_mock_response({"balance": "12345.6789"})

        balance = client.get_balance()

        assert isinstance(balance, Decimal)
        assert balance == Decimal("12345.6789")


# =============================================================================
# Environment Configuration Tests
# =============================================================================


class TestEnvironmentConfiguration:
    """E2E tests for environment configuration."""

    def test_demo_environment_uses_demo_url(self, mock_auth, mock_rate_limiter) -> None:
        """Test demo environment uses correct API URL."""
        with patch.object(requests, "Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            mock_session.request.return_value = create_mock_response({"balance": "100"})

            client = KalshiClient(
                environment="demo",
                auth=mock_auth,
                rate_limiter=mock_rate_limiter,
            )

            client.get_balance()

            # Verify demo URL used
            call_args = mock_session.request.call_args
            assert "demo-api.kalshi.co" in str(call_args)

    def test_prod_environment_uses_prod_url(self, mock_auth, mock_rate_limiter) -> None:
        """Test prod environment uses correct API URL."""
        with patch.object(requests, "Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            mock_session.request.return_value = create_mock_response({"balance": "100"})

            client = KalshiClient(
                environment="prod",
                auth=mock_auth,
                rate_limiter=mock_rate_limiter,
            )

            client.get_balance()

            # Verify prod URL used
            call_args = mock_session.request.call_args
            assert "api.elections.kalshi.com" in str(call_args)

    def test_invalid_environment_raises(self, mock_auth, mock_rate_limiter) -> None:
        """Test invalid environment raises ValueError."""
        with pytest.raises(ValueError, match="Invalid environment"):
            KalshiClient(
                environment="staging",
                auth=mock_auth,
                rate_limiter=mock_rate_limiter,
            )


# =============================================================================
# Authentication Flow Tests
# =============================================================================


class TestAuthenticationFlow:
    """E2E tests for authentication flow."""

    def test_auth_headers_included_in_requests(self, client, mock_session, mock_auth) -> None:
        """Test authentication headers are included in all requests."""
        mock_session.request.return_value = create_mock_response({"balance": "100"})

        client.get_balance()

        # Verify headers were fetched from auth
        mock_auth.get_headers.assert_called_once()

        # Verify headers were passed to request
        call_args = mock_session.request.call_args
        assert "headers" in call_args.kwargs

    def test_fresh_headers_for_each_request(self, client, mock_session, mock_auth) -> None:
        """Test fresh auth headers generated for each request."""
        mock_session.request.return_value = create_mock_response({"balance": "100"})

        # Multiple requests
        client.get_balance()
        client.get_balance()
        client.get_balance()

        # Auth should be called for each request
        assert mock_auth.get_headers.call_count == 3
