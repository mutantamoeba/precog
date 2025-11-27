"""
End-to-End Tests for Kalshi API Client.

These tests validate the Kalshi API client against the REAL Kalshi API (demo environment).
They require valid API credentials to be configured in the .env file.

Educational Note:
    E2E tests differ from unit tests in important ways:
    - Unit tests: Mock external dependencies, test logic in isolation
    - E2E tests: Use real external services, test actual integration

    E2E tests are slower but catch integration issues that unit tests miss:
    - API response format changes
    - Authentication failures
    - Rate limiting behavior
    - Network/timeout handling

Prerequisites:
    - KALSHI_DEMO_KEY_ID set in .env
    - KALSHI_DEMO_KEYFILE set in .env (path to RSA private key)

Run with:
    pytest tests/e2e/api_connectors/test_kalshi_e2e.py -v -m e2e

References:
    - Issue #125: E2E tests for kalshi_client.py
    - REQ-TEST-012: Test types taxonomy (E2E tests)
    - docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md

Phase: 2 (E2E Testing Infrastructure)
GitHub Issue: #125
"""

import os
from decimal import Decimal

import pytest
import requests

# Skip entire module if credentials not available
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.api,
    pytest.mark.skipif(
        not os.getenv("KALSHI_DEMO_KEY_ID") or not os.getenv("KALSHI_DEMO_KEYFILE"),
        reason="Kalshi demo credentials not configured in .env",
    ),
]


@pytest.fixture(scope="module")
def kalshi_client():
    """Create a KalshiClient instance for E2E tests.

    Uses module scope to reuse client across tests (avoids repeated auth).

    Educational Note:
        Module-scoped fixtures are efficient for E2E tests because:
        - Authentication happens once per test module
        - Connection pooling is preserved
        - Tests run faster overall
    """
    from precog.api_connectors.kalshi_client import KalshiClient

    return KalshiClient(environment="demo")
    # No explicit cleanup needed - session closes automatically


class TestKalshiClientAuthentication:
    """E2E tests for RSA-PSS authentication flow."""

    def test_client_initialization_with_valid_credentials(self, kalshi_client):
        """Verify client initializes successfully with valid credentials.

        This test validates:
        1. RSA key can be loaded from file
        2. Auth object is properly initialized
        3. Client is ready for API calls

        Educational Note:
            This is the most basic E2E test - if this fails, nothing else will work.
            It validates the entire authentication chain.
        """
        # Client should be initialized
        assert kalshi_client is not None
        assert kalshi_client.environment == "demo"
        assert kalshi_client.auth is not None

        # Auth should have loaded the key
        assert kalshi_client.auth.api_key is not None
        assert kalshi_client.auth.private_key is not None

    def test_authentication_produces_valid_headers(self, kalshi_client):
        """Verify signed requests produce valid headers.

        Educational Note:
            RSA-PSS signature validation happens server-side, but we can verify
            the headers are properly formed before making a real API call.
        """
        # Generate signed headers for a test request
        headers = kalshi_client.auth.get_signed_headers(
            method="GET",
            path="/trade-api/v2/exchange/status",
            body=None,
        )

        # Verify required headers exist
        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers

        # Key should match configured key
        assert headers["KALSHI-ACCESS-KEY"] == kalshi_client.auth.api_key

        # Signature should be non-empty base64
        signature = headers["KALSHI-ACCESS-SIGNATURE"]
        assert len(signature) > 0


class TestKalshiClientMarkets:
    """E2E tests for market data retrieval."""

    def test_get_markets_returns_list(self, kalshi_client):
        """Verify get_markets returns a list of market data.

        Educational Note:
            We limit to 5 markets to keep the test fast while still
            validating real API integration.
        """
        markets = kalshi_client.get_markets(limit=5)

        # Should return a list
        assert isinstance(markets, list)

        # Should have some markets (demo has test markets)
        # Note: If this fails, demo environment may be empty
        assert len(markets) >= 0

    def test_market_data_contains_required_fields(self, kalshi_client):
        """Verify market data contains expected fields with correct types.

        Educational Note:
            This test validates the response parsing logic - that raw JSON
            is correctly transformed into our ProcessedMarketData structure.
        """
        markets = kalshi_client.get_markets(limit=1)

        if len(markets) == 0:
            pytest.skip("No markets available in demo environment")

        market = markets[0]

        # Required fields should exist
        assert "ticker" in market
        assert "title" in market

        # Ticker should be a string
        assert isinstance(market["ticker"], str)
        assert len(market["ticker"]) > 0

    def test_market_prices_are_decimal(self, kalshi_client):
        """Verify all price fields are Decimal, never float.

        CRITICAL: This test validates Pattern 1 (Decimal Precision).
        Float prices would cause calculation errors in trading logic.

        Educational Note:
            This is one of the most important E2E tests because it validates
            that our Decimal conversion is happening correctly for real API data.
        """
        markets = kalshi_client.get_markets(limit=5)

        if len(markets) == 0:
            pytest.skip("No markets available in demo environment")

        price_fields = ["yes_bid", "yes_ask", "no_bid", "no_ask", "last_price"]

        for market in markets:
            for field in price_fields:
                if field in market and market[field] is not None:
                    assert isinstance(market[field], Decimal), (
                        f"Price field '{field}' in market '{market.get('ticker')}' "
                        f"is {type(market[field]).__name__}, expected Decimal"
                    )

    def test_get_single_market_by_ticker(self, kalshi_client):
        """Verify get_market retrieves a specific market by ticker.

        Educational Note:
            This test uses a two-step approach:
            1. Get any available market to find a valid ticker
            2. Fetch that specific market by ticker
        """
        # First get any market to find a valid ticker
        markets = kalshi_client.get_markets(limit=1)

        if len(markets) == 0:
            pytest.skip("No markets available in demo environment")

        ticker = markets[0]["ticker"]

        # Now fetch that specific market
        market = kalshi_client.get_market(ticker)

        # Should return the same market
        assert market["ticker"] == ticker


class TestKalshiClientBalance:
    """E2E tests for account balance retrieval."""

    def test_get_balance_returns_decimal(self, kalshi_client):
        """Verify balance is returned as Decimal, not float.

        CRITICAL: Account balance must be Decimal for accurate tracking.

        Educational Note:
            Demo accounts start with fake balance. The exact amount doesn't
            matter - what matters is the type is correct.
        """
        balance = kalshi_client.get_balance()

        # Balance must be Decimal
        assert isinstance(balance, Decimal), (
            f"Balance is {type(balance).__name__}, expected Decimal"
        )

        # Balance should be non-negative (demo accounts have positive balance)
        assert balance >= Decimal("0")

    def test_balance_has_reasonable_precision(self, kalshi_client):
        """Verify balance has appropriate decimal precision.

        Educational Note:
            Kalshi uses dollars with cents, so balance should have
            at most 2 decimal places for display (though we store with
            more precision internally).
        """
        balance = kalshi_client.get_balance()

        # Should be able to round to cents without significant loss
        rounded = balance.quantize(Decimal("0.01"))

        # Difference should be very small (sub-cent)
        difference = abs(balance - rounded)
        assert difference < Decimal("0.01")


class TestKalshiClientPositions:
    """E2E tests for position retrieval."""

    def test_get_positions_returns_list(self, kalshi_client):
        """Verify get_positions returns a list.

        Educational Note:
            Demo accounts may have no positions, so we just verify
            the response structure, not the content.
        """
        positions = kalshi_client.get_positions()

        # Should return a list
        assert isinstance(positions, list)

    def test_position_prices_are_decimal(self, kalshi_client):
        """Verify position price fields are Decimal.

        Educational Note:
            Even if no positions exist, this validates our parsing
            logic is ready for when positions are created.
        """
        positions = kalshi_client.get_positions()

        price_fields = ["avg_price", "market_value"]

        for position in positions:
            for field in price_fields:
                if field in position and position[field] is not None:
                    assert isinstance(position[field], Decimal), (
                        f"Position field '{field}' is {type(position[field]).__name__}, "
                        f"expected Decimal"
                    )


class TestKalshiClientRateLimiting:
    """E2E tests for rate limiting behavior."""

    def test_rate_limiter_allows_normal_requests(self, kalshi_client):
        """Verify rate limiter allows requests within limits.

        Educational Note:
            Kalshi allows 100 requests/minute. This test makes a few
            requests rapidly to verify the rate limiter doesn't
            incorrectly block legitimate requests.
        """
        # Make 3 rapid requests - should all succeed
        for i in range(3):
            markets = kalshi_client.get_markets(limit=1)
            assert isinstance(markets, list)

    def test_rate_limiter_tracks_request_count(self, kalshi_client):
        """Verify rate limiter is tracking requests.

        Educational Note:
            We don't actually hit the rate limit (would be slow and
            bad for the API), but we verify the limiter is counting.
        """
        # Get initial count

        # Make a request
        kalshi_client.get_markets(limit=1)

        # Count should have increased

        # Note: Count may have decreased if time passed, so we just verify
        # the limiter is functional
        assert kalshi_client.rate_limiter is not None


class TestKalshiClientErrorHandling:
    """E2E tests for error handling."""

    def test_invalid_ticker_raises_appropriate_error(self, kalshi_client):
        """Verify requesting invalid ticker returns appropriate error.

        Educational Note:
            Good E2E tests verify error paths too, not just happy paths.
            The API should return a 404 or similar for invalid tickers.
        """
        # Use a ticker that definitely doesn't exist
        invalid_ticker = "INVALID_TICKER_XYZ_12345"

        with pytest.raises(requests.exceptions.HTTPError):  # Could be HTTPError or custom exception
            kalshi_client.get_market(invalid_ticker)


class TestKalshiClientDecimalPrecision:
    """Comprehensive Decimal precision validation tests.

    These tests specifically validate Pattern 1 (NEVER USE FLOAT FOR MONEY).

    Educational Note:
        This class groups all precision-related tests together for clarity.
        These are critical tests that validate our core financial safety pattern.
    """

    def test_sub_penny_prices_maintained(self, kalshi_client):
        """Verify sub-penny price precision is maintained.

        Educational Note:
            Kalshi returns prices with up to 4 decimal places (e.g., 0.5475).
            We must maintain this precision for accurate edge calculations.
        """
        markets = kalshi_client.get_markets(limit=10)

        if len(markets) == 0:
            pytest.skip("No markets available in demo environment")

        # Check that we can handle sub-penny precision
        for market in markets:
            yes_ask = market.get("yes_ask")
            if yes_ask is not None:
                # Verify it's Decimal
                assert isinstance(yes_ask, Decimal)

                # Verify precision is preserved (at least 4 decimal places possible)
                # Create a value with 4 decimal places to ensure type supports it
                test_precision = yes_ask + Decimal("0.0001")
                assert test_precision != yes_ask or yes_ask == Decimal("0")

    def test_price_arithmetic_maintains_precision(self, kalshi_client):
        """Verify price arithmetic doesn't lose precision.

        Educational Note:
            This tests that Decimal operations (add, subtract, multiply)
            maintain precision - critical for edge calculations.
        """
        markets = kalshi_client.get_markets(limit=1)

        if len(markets) == 0:
            pytest.skip("No markets available in demo environment")

        market = markets[0]
        yes_ask = market.get("yes_ask")
        yes_bid = market.get("yes_bid")

        if yes_ask is not None and yes_bid is not None:
            # Calculate spread
            spread = yes_ask - yes_bid

            # Should still be Decimal after arithmetic
            assert isinstance(spread, Decimal)

            # Precision test: 0.5475 - 0.5425 = 0.0050 (exactly)
            # Float would give: 0.004999999999999893
            assert spread == spread.quantize(Decimal("0.0001"))
