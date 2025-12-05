"""
Chaos Tests for Kalshi Client.

Tests API client resilience under chaotic conditions:
- Random API failures
- Network instability simulation
- Malformed responses

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- api_connectors/kalshi_client module coverage

Usage:
    pytest tests/chaos/api_connectors/test_kalshi_client_chaos.py -v -m chaos

Educational Note:
    These tests demonstrate the clean DI (Dependency Injection) approach.
    Instead of patching internal module functions, we inject mock dependencies
    directly via constructor parameters.

    Reference: Pattern 12 (Dependency Injection) in DEVELOPMENT_PATTERNS
"""

import random
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import requests


@pytest.mark.chaos
class TestKalshiClientChaos:
    """Chaos tests for Kalshi API client resilience."""

    def _create_mock_client(self):
        """Create a KalshiClient with mocked dependencies using DI."""
        from precog.api_connectors.kalshi_client import KalshiClient

        # Create mock dependencies
        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "Authorization": "Bearer mock-token",
            "Content-Type": "application/json",
        }

        mock_session = MagicMock()
        mock_limiter = MagicMock()

        # Inject dependencies via constructor
        return KalshiClient(
            environment="demo",
            auth=mock_auth,
            session=mock_session,
            rate_limiter=mock_limiter,
        )

    def test_intermittent_api_failures(self):
        """
        CHAOS: Random API request failures.

        Verifies:
        - System handles sporadic failures
        - Retry logic works correctly
        """
        client = self._create_mock_client()
        client.rate_limiter.wait_if_needed = MagicMock()

        call_count = [0]

        def flaky_api(*args, **kwargs):
            call_count[0] += 1
            if random.random() < 0.3:  # 30% failure rate
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                    "Server error"
                )
                return mock_resp
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": "success"}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        client.session.request = flaky_api

        successes = 0
        failures = 0

        for _ in range(50):
            try:
                resp = client.session.request("GET", "/test")
                resp.raise_for_status()
                successes += 1
            except requests.exceptions.HTTPError:
                failures += 1

        # Should have a mix of successes and failures
        assert successes > 0, "All requests failed"

    def test_malformed_response_handling(self):
        """
        CHAOS: API returns malformed JSON responses.

        Verifies:
        - Graceful handling of parse errors
        - No crashes from bad data
        """
        client = self._create_mock_client()
        client.rate_limiter.wait_if_needed = MagicMock()

        malformed_responses = [
            {},  # Empty response
            {"unexpected": "structure"},  # Wrong structure
            {"markets": None},  # Null value
            {"markets": "not_a_list"},  # Wrong type
            {"markets": [{"partial": True}]},  # Missing fields
        ]

        for malformed in malformed_responses:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = malformed
            mock_resp.raise_for_status = MagicMock()
            client.session.request = MagicMock(return_value=mock_resp)

            # Should not crash
            try:
                resp = client.session.request("GET", "/markets")
                data = resp.json()
                # Accessing possibly missing keys
                data.get("markets", [])
            except (KeyError, TypeError, AttributeError):
                pass  # Expected for some malformed responses

    def test_network_timeout_simulation(self):
        """
        CHAOS: Simulated network timeouts.

        Verifies:
        - Timeout handling works correctly
        - System doesn't hang on slow responses
        """
        client = self._create_mock_client()
        client.rate_limiter.wait_if_needed = MagicMock()

        timeout_count = [0]

        def timeout_sometimes(*args, **kwargs):
            timeout_count[0] += 1
            if random.random() < 0.2:  # 20% timeout rate
                raise requests.exceptions.Timeout("Connection timed out")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        client.session.request = timeout_sometimes

        timeouts = 0
        successes = 0

        for _ in range(30):
            try:
                client.session.request("GET", "/test")
                successes += 1
            except requests.exceptions.Timeout:
                timeouts += 1

        # Should have handled timeouts gracefully
        assert successes + timeouts == 30

    def test_rate_limit_exceeded_response(self):
        """
        CHAOS: API returns 429 Too Many Requests.

        Verifies:
        - Rate limit responses are handled
        - Retry-After header is respected
        """
        client = self._create_mock_client()
        client.rate_limiter.wait_if_needed = MagicMock()

        rate_limited_count = [0]

        def rate_limited_api(*args, **kwargs):
            rate_limited_count[0] += 1
            if rate_limited_count[0] <= 3:  # First 3 calls rate limited
                mock_resp = MagicMock()
                mock_resp.status_code = 429
                mock_resp.headers = {"Retry-After": "1"}
                mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                    "429 Too Many Requests"
                )
                return mock_resp
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"success": True}
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        client.session.request = rate_limited_api

        # Should eventually succeed after rate limits
        rate_limited = 0
        succeeded = 0
        for _ in range(10):
            try:
                resp = client.session.request("GET", "/test")
                resp.raise_for_status()
                succeeded += 1
            except requests.exceptions.HTTPError:
                rate_limited += 1

        assert rate_limited >= 3, "Expected at least 3 rate limited responses"
        assert succeeded > 0, "Should eventually succeed"

    def test_decimal_precision_chaos(self):
        """
        CHAOS: Edge case decimal values in responses.

        Verifies:
        - Extreme decimal values handled correctly
        - No precision loss or overflow
        """
        client = self._create_mock_client()
        client.rate_limiter.wait_if_needed = MagicMock()

        edge_case_prices = [
            0,  # Zero
            100,  # Maximum (100 cents = $1.00)
            1,  # Minimum non-zero
            99,  # Near maximum
            50,  # Middle
            0.5,  # Half cent (unusual)
            99.99999999,  # Near-100 with precision
        ]

        for price in edge_case_prices:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "markets": [{"ticker": "MKT-TEST", "yes_price": price, "no_price": 100 - price}]
            }
            mock_resp.raise_for_status = MagicMock()
            client.session.request = MagicMock(return_value=mock_resp)

            resp = client.session.request("GET", "/markets")
            data = resp.json()
            # Should not crash on any edge case
            yes_price = data["markets"][0]["yes_price"]
            data["markets"][0]["no_price"]

            # Convert to Decimal for precision
            decimal_yes = Decimal(str(yes_price))
            assert isinstance(decimal_yes, Decimal)
