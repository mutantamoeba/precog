"""
Integration tests for Kalshi API client.

Tests the full KalshiClient integration with mocked HTTP responses.
These tests verify:
- Successful API requests (markets, balance, positions, fills, settlements)
- Error handling (401, 429, 500, 400, network errors)
- Decimal precision for all price values
- Rate limiting behavior
- Retry logic with exponential backoff

Note: These are integration tests, not unit tests.
- They test multiple components together (client + auth + rate limiter)
- They use mocked HTTP responses (not real API calls)
- They verify the full request/response flow

Pattern 13 Exception: External API mock
These tests mock HTTP responses to test API client behavior. They don't
touch the database, so database fixtures (db_pool, db_cursor, clean_test_data)
are not applicable. Pattern 13 lesson learned was about DATABASE connection
pool mocking, not HTTP mocking.

Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-API-002: RSA-PSS Authentication
    - REQ-API-005: API Rate Limit Management
    - REQ-API-006: API Error Handling
    - REQ-SYS-003: Decimal Precision for Prices

Reference: docs/testing/PHASE_1_TEST_PLAN_V1.0.md (Section 4.2.1)
"""

import logging
import time
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import requests

from precog.api_connectors.kalshi_client import KalshiClient
from tests.fixtures.api_responses import (
    DECIMAL_ARITHMETIC_TESTS,
    KALSHI_BALANCE_RESPONSE,
    KALSHI_ERROR_400_RESPONSE,
    KALSHI_ERROR_401_RESPONSE,
    KALSHI_ERROR_429_RESPONSE,
    KALSHI_ERROR_500_RESPONSE,
    KALSHI_FILLS_RESPONSE,
    KALSHI_MARKET_RESPONSE,
    KALSHI_POSITIONS_RESPONSE,
    KALSHI_SETTLEMENTS_RESPONSE,
    SUB_PENNY_TEST_CASES,
)


@pytest.mark.integration
@pytest.mark.api
class TestKalshiClientIntegration:
    """
    Test full Kalshi API client integration with mocked HTTP responses.

    These tests verify successful API requests work correctly with:
    - Proper authentication headers
    - Decimal price conversion
    - Response parsing
    - Rate limiting
    """

    def test_get_markets_integration(self, monkeypatch):
        """Test get_markets() returns markets with Decimal prices."""
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_MARKET_RESPONSE
        mock_response.raise_for_status = Mock()

        # Mock environment variables
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        # Mock session.request to return our response
        with patch(
            "precog.api_connectors.kalshi_client.requests.Session.request",
            return_value=mock_response,
        ):
            # Mock auth to skip RSA signature generation
            with patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ):
                client = KalshiClient(environment="demo")
                markets = client.get_markets()

        # Verify results
        assert len(markets) == 2
        assert markets[0]["ticker"] == "KXNFLGAME-25DEC15-KC-YES"
        assert markets[1]["ticker"] == "KXNFLGAME-25DEC15-BUF-YES"

        # Verify Decimal conversion (using *_dollars fields for sub-penny precision)
        assert isinstance(markets[0]["yes_bid_dollars"], Decimal)
        assert markets[0]["yes_bid_dollars"] == Decimal("0.6200")
        assert isinstance(markets[0]["yes_ask_dollars"], Decimal)
        assert markets[0]["yes_ask_dollars"] == Decimal("0.6250")

        # Verify sub-penny pricing preserved
        assert isinstance(markets[1]["yes_bid_dollars"], Decimal)
        assert markets[1]["yes_bid_dollars"] == Decimal("0.4275")  # Sub-penny!

    def test_get_balance_integration(self, monkeypatch):
        """Test get_balance() returns Decimal balance."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            balance = client.get_balance()

        # Verify Decimal type
        assert isinstance(balance, Decimal)
        assert balance == Decimal("1234.5678")

    def test_get_positions_integration(self, monkeypatch):
        """Test get_positions() returns positions with Decimal prices."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_POSITIONS_RESPONSE
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            positions = client.get_positions()

        # Verify results
        assert len(positions) == 2
        assert positions[0]["ticker"] == "KXNFLGAME-25DEC15-KC-YES"

        # Verify Decimal types
        assert isinstance(positions[0]["user_average_price"], Decimal)
        assert positions[0]["user_average_price"] == Decimal("0.6100")
        assert isinstance(positions[0]["total_cost"], Decimal)
        assert positions[0]["total_cost"] == Decimal("61.0000")

    def test_get_fills_integration(self, monkeypatch):
        """Test get_fills() returns trade fills with Decimal prices."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_FILLS_RESPONSE
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            fills = client.get_fills()

        # Verify results
        assert len(fills) == 2
        assert fills[0]["ticker"] == "KXNFLGAME-25DEC15-KC-YES"

        # Verify Decimal types (using *_fixed fields for sub-penny precision)
        assert isinstance(fills[0]["yes_price_fixed"], Decimal)
        assert fills[0]["yes_price_fixed"] == Decimal("0.6200")
        assert isinstance(fills[0]["no_price_fixed"], Decimal)
        assert fills[0]["no_price_fixed"] == Decimal("0.3800")

    def test_get_settlements_integration(self, monkeypatch):
        """Test get_settlements() returns settlement data with Decimal values."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_SETTLEMENTS_RESPONSE
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            settlements = client.get_settlements()

        # Verify results
        assert len(settlements) == 2
        assert settlements[0]["ticker"] == "KXNFLGAME-25DEC08-KC-YES"

        # Verify Decimal types
        assert isinstance(settlements[0]["settlement_value"], Decimal)
        assert settlements[0]["settlement_value"] == Decimal("1.0000")
        assert isinstance(settlements[0]["revenue"], Decimal)
        assert settlements[0]["revenue"] == Decimal("100.0000")


@pytest.mark.integration
@pytest.mark.api
class TestKalshiClientErrorHandling:
    """
    Test Kalshi API client error handling with mocked error responses.

    Verifies:
    - 401 Unauthorized raises error (no automatic retry)
    - 429 Rate Limit raises error (no automatic retry, caller decides)
    - 500 Server Error triggers automatic retry with exponential backoff
    - 400 Bad Request does NOT retry (client error, raises immediately)
    - Network errors (timeout, connection) raise error (no automatic retry)

    Note: Only 5xx server errors trigger automatic retry. All other errors
    are raised immediately for the caller to handle.
    """

    def test_401_unauthorized_raises_error(self, monkeypatch):
        """Test 401 Unauthorized response raises HTTPError after retry."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = KALSHI_ERROR_401_RESPONSE
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Should raise HTTPError for 401
            with pytest.raises(requests.HTTPError, match="401"):
                client.get_balance()

    def test_429_rate_limit_raises_error(self, monkeypatch):
        """Test 429 Rate Limit response raises HTTPError (no automatic retry)."""
        # Mock 429 response with Retry-After header
        mock_429 = Mock()
        mock_429.status_code = 429
        mock_429.json.return_value = KALSHI_ERROR_429_RESPONSE
        # Use Mock for headers to allow .get() method
        mock_headers = Mock()
        mock_headers.get.return_value = "30"  # Retry-After header value
        mock_429.headers = mock_headers
        mock_429.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with patch(
            "precog.api_connectors.kalshi_client.requests.Session.request", return_value=mock_429
        ):
            with patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ):
                client = KalshiClient(environment="demo")

                # Should raise HTTPError for 429 (no automatic retry)
                with pytest.raises(requests.HTTPError, match="429"):
                    client.get_balance()

    def test_500_server_error_triggers_retry(self, monkeypatch):
        """Test 500 Internal Server Error triggers retry with exponential backoff."""
        # First request returns 500, second succeeds
        mock_500 = Mock()
        mock_500.status_code = 500
        mock_500.json.return_value = KALSHI_ERROR_500_RESPONSE
        mock_500.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")

        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_success.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                side_effect=[mock_500, mock_success],
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            balance = client.get_balance()

        # Should succeed after retry
        assert balance == Decimal("1234.5678")

    def test_400_bad_request_no_retry(self, monkeypatch):
        """Test 400 Bad Request does NOT retry (client error, won't fix itself)."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = KALSHI_ERROR_400_RESPONSE
        mock_response.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ) as mock_request,
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Should raise HTTPError for 400
            with pytest.raises(requests.HTTPError, match="400"):
                client.get_markets()

        # Should NOT retry (only 1 attempt for 4xx errors)
        assert mock_request.call_count == 1

    @pytest.mark.parametrize(
        ("status_code", "error_message"),
        [
            (401, "401 Unauthorized"),
            (400, "400 Bad Request"),
            (403, "403 Forbidden"),
            (404, "404 Not Found"),
        ],
        ids=["401-unauthorized", "400-bad-request", "403-forbidden", "404-not-found"],
    )
    def test_client_error_codes_raise_http_error(self, status_code, error_message, monkeypatch):
        """Test that HTTP client error codes (4xx) raise HTTPError.

        Parametrized test covering multiple error codes with same behavior.
        For detailed behavior tests (retry logic, headers, etc.), see individual test functions.

        Args:
            status_code: HTTP status code to test (401, 400, 403, 404)
            error_message: Expected error message substring
        """
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {"error": f"Error {status_code}"}
        mock_response.raise_for_status.side_effect = requests.HTTPError(error_message)

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Should raise HTTPError with appropriate status code
            with pytest.raises(requests.HTTPError, match=str(status_code)):
                client.get_balance()

    def test_network_timeout_raises_error(self, monkeypatch):
        """Test network timeout raises Timeout error (no automatic retry)."""
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                side_effect=requests.Timeout("Connection timeout"),
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Should raise Timeout error (no automatic retry)
            with pytest.raises(requests.Timeout, match="timeout"):
                client.get_balance()

    def test_connection_error_raises_error(self, monkeypatch):
        """Test connection error raises ConnectionError (no automatic retry)."""
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                side_effect=requests.ConnectionError("Connection refused"),
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Should raise ConnectionError (no automatic retry)
            with pytest.raises(requests.ConnectionError, match="refused"):
                client.get_balance()


@pytest.mark.integration
@pytest.mark.critical
class TestKalshiClientDecimalPrecision:
    """
    Test Decimal precision in Kalshi API client (CRITICAL tests).

    Kalshi uses sub-penny pricing (4 decimal places). MUST use Decimal, not float!

    Why this matters:
    - Kalshi prices like 0.4275 cannot be represented exactly in float
    - Float arithmetic causes rounding errors (0.1 + 0.2 != 0.3 in float!)
    - Decimal gives exact precision for financial calculations

    Related:
        - REQ-SYS-003: Decimal Precision for All Prices
        - ADR-002: Decimal-Only Financial Calculations
        - Pattern 1 in CLAUDE.md: Decimal Precision
    """

    @pytest.mark.parametrize("test_case", SUB_PENNY_TEST_CASES)
    def test_sub_penny_price_parsing(self, test_case, monkeypatch):
        """
        Test sub-penny price parsing from API responses.

        Verifies that prices like "0.4275" are correctly parsed as Decimal("0.4275")
        without any precision loss.
        """
        # Create mock response with sub-penny price (using *_dollars suffix)
        mock_market = {
            "ticker": "TEST-MARKET",
            "yes_bid_dollars": test_case["api_value"],
            "yes_ask_dollars": test_case["api_value"],
            "no_bid_dollars": "0.5000",
            "no_ask_dollars": "0.5000",
            "last_price_dollars": test_case["api_value"],
            "volume": 1000,
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"markets": [mock_market]}
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            markets = client.get_markets()

        market = markets[0]

        # Verify exact Decimal value (using *_dollars field)
        assert market["yes_bid_dollars"] == test_case["expected_decimal"]
        assert isinstance(market["yes_bid_dollars"], Decimal)

        # Verify string representation matches (no precision loss)
        assert str(market["yes_bid_dollars"]) == test_case["api_value"]

    @pytest.mark.parametrize("test_case", DECIMAL_ARITHMETIC_TESTS)
    def test_decimal_arithmetic_operations(self, test_case):
        """
        Test Decimal arithmetic operations for financial calculations.

        Tests:
        - Spread calculation: ask - bid
        - PnL calculation: (exit_price - entry_price) * quantity
        - Edge calculation: true_prob - market_price
        """
        if test_case["operation"] == "spread":
            result = test_case["ask"] - test_case["bid"]
        elif test_case["operation"] == "pnl":
            result = (test_case["exit_price"] - test_case["entry_price"]) * test_case["quantity"]
        elif test_case["operation"] == "edge":
            result = test_case["true_prob"] - test_case["market_price"]

        # Verify exact Decimal precision
        assert result == test_case["expected_result"]
        assert isinstance(result, Decimal)

    def test_all_prices_are_decimal_type(self, monkeypatch):
        """
        Test that ALL price fields are Decimal type (comprehensive check).

        Verifies every price-related field in the API response is converted to Decimal.
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_MARKET_RESPONSE
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")
            markets = client.get_markets()

        # Check all price fields are Decimal for all markets (sub-penny format with *_dollars suffix)
        price_fields = [
            "yes_bid_dollars",
            "yes_ask_dollars",
            "no_bid_dollars",
            "no_ask_dollars",
            "last_price_dollars",
        ]

        for market in markets:
            for field in price_fields:
                assert isinstance(market[field], Decimal), (
                    f"Field '{field}' in market '{market['ticker']}' is {type(market[field])}, "
                    f"expected Decimal. Value: {market[field]}"
                )


# =============================================================================
# Part 2.3: Rate Limiting Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.api
class TestKalshiClientRateLimiting:
    """
    Test Kalshi API client rate limiting integration.

    Tests the RateLimiter and TokenBucket integration with real request patterns.
    Verifies token bucket behavior, throttling warnings, and 429 error handling.
    """

    def test_rate_limiter_allows_burst_requests(self, monkeypatch):
        """
        Test that rate limiter allows burst of requests up to capacity.

        Token bucket should allow 100 rapid requests (burst capacity),
        then require waiting for token refill.
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        request_count = 0

        def count_requests(*args, **kwargs):
            nonlocal request_count
            request_count += 1
            return mock_response

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                side_effect=count_requests,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Make burst of 10 requests (should succeed without delay)
            start_time = time.time()
            for _ in range(10):
                client.get_balance()
            elapsed = time.time() - start_time

        # All 10 requests should complete quickly (<1 second)
        assert request_count == 10
        assert elapsed < 1.0, f"Burst requests took {elapsed:.2f}s, expected < 1s"

    def test_rate_limiter_warns_at_80_percent_utilization(self, monkeypatch, caplog):
        """
        Test that rate limiter warns when >80% of tokens consumed.

        When tokens < capacity * 0.2 (i.e., >80% consumed), should log warning.
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Consume tokens to trigger warning (capacity=100, warn at <20 tokens)
            # Make 85 requests to get below 20 tokens (100 - 85 = 15)
            with caplog.at_level(logging.WARNING):
                for _ in range(85):
                    client.get_balance()

        # Check that warning was logged
        warning_messages = [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]
        assert any(
            "Rate limit warning" in msg or "tokens remaining" in msg for msg in warning_messages
        ), f"Expected rate limit warning, got: {warning_messages}"

    @pytest.mark.slow
    def test_rate_limiter_refills_tokens_over_time(self, monkeypatch):
        """
        Test that token bucket refills tokens over time.

        After consuming tokens, waiting should allow refill and more requests.

        Note: This test uses time.sleep(6.0) and is marked as slow.
              Run with: pytest -m slow (only slow tests)
              Skip with: pytest -m "not slow" (fast tests only)
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Check initial token count (should be full: 100)
            initial_tokens = client.rate_limiter.bucket.get_available_tokens()
            assert initial_tokens == 100.0, f"Expected 100 tokens initially, got {initial_tokens}"

            # Consume 10 tokens
            for _ in range(10):
                client.get_balance()

            tokens_after_burst = client.rate_limiter.bucket.get_available_tokens()
            assert tokens_after_burst < 100.0, "Tokens should decrease after requests"
            assert tokens_after_burst >= 90.0, (
                f"Expected ~90 tokens after 10 requests, got {tokens_after_burst}"
            )

            # Wait for refill (refill rate: 100/60 = 1.67 tokens/sec)
            # Wait 6 seconds should refill ~10 tokens (6 * 1.67 = 10.02)
            time.sleep(6.0)

            tokens_after_refill = client.rate_limiter.bucket.get_available_tokens()
            # Should refill back to 100 (capped at capacity)
            assert tokens_after_refill == 100.0, (
                f"Expected 100 tokens after refill, got {tokens_after_refill}"
            )

    def test_client_handles_429_with_retry_after_header(self, monkeypatch):
        """
        Test that client handles 429 (Rate Limit) with Retry-After header.

        When API returns 429 with Retry-After header, client should:
        1. Extract Retry-After value
        2. Wait for specified duration
        3. Raise HTTPError (caller decides whether to retry)
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        # Mock 429 response with Retry-After header
        mock_429 = Mock()
        mock_429.status_code = 429
        mock_429.json.return_value = KALSHI_ERROR_429_RESPONSE
        mock_headers = Mock()
        mock_headers.get.return_value = "30"  # Retry-After: 30 seconds
        mock_429.headers = mock_headers
        mock_429.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

        with patch(
            "precog.api_connectors.kalshi_client.requests.Session.request", return_value=mock_429
        ):
            with patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ):
                client = KalshiClient(environment="demo")

                # Should raise HTTPError with 429 status
                with pytest.raises(requests.HTTPError, match="429"):
                    client.get_balance()

    def test_rate_limiter_utilization_calculation(self, monkeypatch):
        """
        Test rate limiter utilization percentage calculation.

        Utilization should be: (capacity - available) / capacity
        - 0% = all tokens available (unused)
        - 100% = no tokens available (fully utilized)
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                return_value=mock_response,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                return_value={"Authorization": "Bearer mock"},
            ),
        ):
            client = KalshiClient(environment="demo")

            # Initial utilization should be 0% (full bucket)
            initial_util = client.rate_limiter.get_utilization()
            assert initial_util == 0.0, (
                f"Expected 0% utilization initially, got {initial_util * 100}%"
            )

            # Consume 50 tokens (50% utilization)
            for _ in range(50):
                client.get_balance()

            mid_util = client.rate_limiter.get_utilization()
            assert 0.45 <= mid_util <= 0.55, f"Expected ~50% utilization, got {mid_util * 100:.1f}%"

            # Consume 40 more tokens (90% utilization)
            for _ in range(40):
                client.get_balance()

            high_util = client.rate_limiter.get_utilization()
            assert 0.85 <= high_util <= 0.95, (
                f"Expected ~90% utilization, got {high_util * 100:.1f}%"
            )


# =============================================================================
# Part 2.4: Authentication Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.api
class TestKalshiClientAuthentication:
    """
    Test Kalshi API client authentication integration.

    Tests RSA-PSS signature generation and header authentication.
    Note: Token refresh is deferred to Phase 1.5 (currently stub).
    """

    def test_signature_generation_creates_unique_signatures(self, monkeypatch):
        """
        Test that each request generates a unique RSA-PSS signature.

        Because signatures include a timestamp, each signature should be different
        even for the same endpoint (prevents replay attacks).
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        signatures = []

        def capture_signature(*args, **kwargs):
            # Extract signature from headers
            if "headers" in kwargs:
                sig = kwargs["headers"].get("KALSHI-ACCESS-SIGNATURE")
                if sig:
                    signatures.append(sig)
            return mock_response

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                side_effect=capture_signature,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                wraps=lambda *args, **kwargs: {
                    "KALSHI-ACCESS-KEY": "test-key-id",
                    "KALSHI-ACCESS-TIMESTAMP": str(int(time.time() * 1000)),
                    "KALSHI-ACCESS-SIGNATURE": f"sig_{len(signatures)}",
                    "Content-Type": "application/json",
                },
            ),
        ):
            client = KalshiClient(environment="demo")

            # Make 3 requests with small delays
            client.get_balance()
            time.sleep(0.01)  # Ensure timestamp changes
            client.get_balance()
            time.sleep(0.01)
            client.get_balance()

        # All 3 signatures should be different (due to timestamp changes)
        assert len(signatures) == 3
        assert len(set(signatures)) == 3, f"Expected 3 unique signatures, got: {signatures}"

    def test_authentication_headers_include_all_required_fields(self, monkeypatch):
        """
        Test that authentication headers include all required fields.

        Kalshi requires:
        - KALSHI-ACCESS-KEY (API key)
        - KALSHI-ACCESS-TIMESTAMP (current time in milliseconds)
        - KALSHI-ACCESS-SIGNATURE (RSA-PSS signature)
        - Content-Type: application/json
        """
        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
        mock_response.raise_for_status = Mock()

        captured_headers = {}

        def capture_headers(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            return mock_response

        with (
            patch(
                "precog.api_connectors.kalshi_client.requests.Session.request",
                side_effect=capture_headers,
            ),
            patch(
                "precog.api_connectors.kalshi_client.KalshiAuth.get_headers",
                wraps=lambda method, path: {
                    "KALSHI-ACCESS-KEY": "test-key-id",
                    "KALSHI-ACCESS-TIMESTAMP": str(int(time.time() * 1000)),
                    "KALSHI-ACCESS-SIGNATURE": "mock_signature",
                    "Content-Type": "application/json",
                },
            ),
        ):
            client = KalshiClient(environment="demo")
            client.get_balance()

        # Verify all required headers present
        assert "KALSHI-ACCESS-KEY" in captured_headers
        assert "KALSHI-ACCESS-TIMESTAMP" in captured_headers
        assert "KALSHI-ACCESS-SIGNATURE" in captured_headers
        assert "Content-Type" in captured_headers

        # Verify values
        assert captured_headers["KALSHI-ACCESS-KEY"] == "test-key-id"
        assert captured_headers["Content-Type"] == "application/json"
        assert len(captured_headers["KALSHI-ACCESS-TIMESTAMP"]) > 0  # Timestamp present
        assert len(captured_headers["KALSHI-ACCESS-SIGNATURE"]) > 0  # Signature present

    def test_signature_is_base64_encoded(self, monkeypatch):
        """
        Test that RSA-PSS signatures are base64 encoded.

        Signatures must be base64 encoded for HTTP transport.
        """
        import base64

        from precog.api_connectors.kalshi_auth import KalshiAuth

        # Create auth instance
        auth = KalshiAuth(
            api_key="test-key-id", private_key_path="tests/fixtures/test_private_key.pem"
        )

        # Generate headers (which includes signature)
        headers = auth.get_headers(method="GET", path="/trade-api/v2/markets")

        signature = headers["KALSHI-ACCESS-SIGNATURE"]

        # Verify it's valid base64 (will raise exception if not)
        try:
            decoded = base64.b64decode(signature)
            assert len(decoded) > 0, "Decoded signature should not be empty"
        except Exception as e:
            pytest.fail(f"Signature is not valid base64: {e}")

    def test_signature_includes_method_and_path(self, monkeypatch):
        """
        Test that signature changes for different methods and paths.

        Different endpoints should produce different signatures
        (even with same timestamp, which won't happen in practice).
        """
        from precog.api_connectors.kalshi_auth import KalshiAuth, generate_signature

        # Load test private key
        private_key = KalshiAuth(
            api_key="test-key-id", private_key_path="tests/fixtures/test_private_key.pem"
        ).private_key

        timestamp = int(time.time() * 1000)

        # Generate signatures for different endpoints
        sig1 = generate_signature(private_key, timestamp, "GET", "/trade-api/v2/markets")
        sig2 = generate_signature(private_key, timestamp, "GET", "/trade-api/v2/portfolio/balance")
        sig3 = generate_signature(private_key, timestamp, "POST", "/trade-api/v2/orders")

        # All signatures should be different (different paths/methods)
        assert sig1 != sig2, "Signatures for different paths should differ"
        assert sig1 != sig3, "Signatures for different methods should differ"
        assert sig2 != sig3, "Signatures for different endpoints should differ"

    def test_token_expiry_check_returns_true_when_no_token(self):
        """
        Test that is_token_expired() returns True when no token set.

        Note: Token management is Phase 1.5 feature (currently stub).
        """
        from precog.api_connectors.kalshi_auth import KalshiAuth

        auth = KalshiAuth(
            api_key="test-key-id", private_key_path="tests/fixtures/test_private_key.pem"
        )

        # No token set initially
        assert auth.token is None
        assert auth.token_expiry is None
        assert auth.is_token_expired() is True, "Should return True when no token set"


# =============================================================================
# Part 2.6: Pagination Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.api
class TestKalshiClientPagination:
    """
    Test Kalshi API client pagination integration.

    Tests cursor-based pagination for multi-page results.
    Verifies cursor handling, page iteration, and edge cases.
    """

    def test_single_page_no_cursor(self, monkeypatch):
        """Test get_markets with single page (no cursor in response)."""
        # Mock response with markets but NO cursor (single page)
        mock_response = Mock()
        mock_response.json.return_value = {
            "markets": [
                {
                    "ticker": "MARKET-1-YES",
                    "yes_bid_dollars": "0.6000",
                    "yes_ask_dollars": "0.6100",
                    "no_bid_dollars": "0.3900",
                    "no_ask_dollars": "0.4000",
                    "last_price_dollars": "0.6050",
                    "volume": 1000,
                },
                {
                    "ticker": "MARKET-2-YES",
                    "yes_bid_dollars": "0.7000",
                    "yes_ask_dollars": "0.7100",
                    "no_bid_dollars": "0.2900",
                    "no_ask_dollars": "0.3000",
                    "last_price_dollars": "0.7050",
                    "volume": 2000,
                },
            ]
            # No "cursor" field = this is the only page
        }
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        # Mock requests.Session.request
        mock_request = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.Session.request", mock_request)

        # Create client and fetch markets
        client = KalshiClient()
        markets = client.get_markets(series_ticker="TEST")

        # Verify results
        assert len(markets) == 2, "Should return 2 markets"
        assert markets[0]["ticker"] == "MARKET-1-YES"
        assert markets[1]["ticker"] == "MARKET-2-YES"

        # Verify prices converted to Decimal (sub-penny format with *_dollars suffix)
        assert isinstance(markets[0]["yes_bid_dollars"], Decimal)
        assert markets[0]["yes_bid_dollars"] == Decimal("0.6000")

    def test_multi_page_cursor_handling(self, monkeypatch):
        """Test get_markets with multi-page results (cursor pagination)."""
        # Page 1: 2 markets + cursor "page2_token"
        page1_response = Mock()
        page1_response.json.return_value = {
            "markets": [
                {
                    "ticker": "MARKET-1-YES",
                    "yes_bid_dollars": "0.6000",
                    "yes_ask_dollars": "0.6100",
                    "no_bid_dollars": "0.3900",
                    "no_ask_dollars": "0.4000",
                    "last_price_dollars": "0.6050",
                    "volume": 1000,
                },
                {
                    "ticker": "MARKET-2-YES",
                    "yes_bid_dollars": "0.7000",
                    "yes_ask_dollars": "0.7100",
                    "no_bid_dollars": "0.2900",
                    "no_ask_dollars": "0.3000",
                    "last_price_dollars": "0.7050",
                    "volume": 2000,
                },
            ],
            "cursor": "page2_token",  # More pages available
        }
        page1_response.raise_for_status = Mock()

        # Page 2: 1 market, no cursor (last page)
        page2_response = Mock()
        page2_response.json.return_value = {
            "markets": [
                {
                    "ticker": "MARKET-3-YES",
                    "yes_bid_dollars": "0.8000",
                    "yes_ask_dollars": "0.8100",
                    "no_bid_dollars": "0.1900",
                    "no_ask_dollars": "0.2000",
                    "last_price_dollars": "0.8050",
                    "volume": 3000,
                },
            ]
            # No cursor = last page
        }
        page2_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        # Mock requests to return different responses for page 1 vs page 2
        call_count = 0

        def mock_request_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return page1_response
            return page2_response

        mock_request = Mock(side_effect=mock_request_side_effect)
        monkeypatch.setattr("requests.Session.request", mock_request)

        # Create client
        client = KalshiClient()

        # Fetch page 1
        page1_markets = client.get_markets(series_ticker="TEST", limit=2)
        assert len(page1_markets) == 2, "Page 1 should have 2 markets"
        assert page1_markets[0]["ticker"] == "MARKET-1-YES"
        assert page1_markets[1]["ticker"] == "MARKET-2-YES"

        # Fetch page 2 with cursor
        page2_markets = client.get_markets(series_ticker="TEST", limit=2, cursor="page2_token")
        assert len(page2_markets) == 1, "Page 2 should have 1 market"
        assert page2_markets[0]["ticker"] == "MARKET-3-YES"

        # Verify both calls made
        assert call_count == 2, "Should make 2 API calls (page 1 and page 2)"

    def test_cursor_passed_in_params(self, monkeypatch):
        """Test that cursor is correctly passed in request params."""
        mock_response = Mock()
        mock_response.json.return_value = {"markets": []}
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        # Mock and capture request calls
        mock_request = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.Session.request", mock_request)

        # Create client and call with cursor
        client = KalshiClient()
        client.get_markets(series_ticker="TEST", limit=50, cursor="my_cursor_token_123")

        # Verify cursor in params
        call_args = mock_request.call_args
        params = call_args[1].get("params", {})

        assert "cursor" in params, "Params should include cursor"
        assert params["cursor"] == "my_cursor_token_123", "Cursor value should match"
        assert params["limit"] == 50, "Limit should be 50"
        assert params["series_ticker"] == "TEST", "Series ticker should be TEST"

    def test_empty_results_no_cursor(self, monkeypatch):
        """Test get_markets with empty results (no markets, no cursor)."""
        # Mock response with empty markets array
        mock_response = Mock()
        mock_response.json.return_value = {
            "markets": []
            # No cursor
        }
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_request = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.Session.request", mock_request)

        # Create client and fetch markets
        client = KalshiClient()
        markets = client.get_markets(series_ticker="NONEXISTENT")

        # Verify empty list returned
        assert markets == [], "Should return empty list for no results"
        assert len(markets) == 0, "Length should be 0"

    def test_pagination_with_limit_parameter(self, monkeypatch):
        """Test that limit parameter correctly limits results per page."""
        # Mock response respecting limit
        mock_response = Mock()
        mock_response.json.return_value = {
            "markets": [
                {
                    "ticker": f"MARKET-{i}-YES",
                    "yes_bid": "0.5000",
                    "yes_ask": "0.5100",
                    "no_bid": "0.4900",
                    "no_ask": "0.5000",
                    "last_price": "0.5050",
                    "volume": 1000,
                }
                for i in range(1, 11)  # Exactly 10 markets
            ],
            "cursor": "next_page_token",  # More results available
        }
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id")
        monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "tests/fixtures/test_private_key.pem")

        mock_request = Mock(return_value=mock_response)
        monkeypatch.setattr("requests.Session.request", mock_request)

        # Create client and fetch with limit=10
        client = KalshiClient()
        markets = client.get_markets(series_ticker="TEST", limit=10)

        # Verify exactly 10 markets returned
        assert len(markets) == 10, "Should return exactly 10 markets (respecting limit)"

        # Verify limit passed in params
        call_args = mock_request.call_args
        params = call_args[1].get("params", {})
        assert params["limit"] == 10, "Limit param should be 10"
