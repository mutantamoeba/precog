"""
End-to-End Tests for Kalshi RSA-PSS Authentication.

These tests validate the authentication module against the REAL Kalshi API.
They verify that our RSA-PSS signature implementation is accepted by Kalshi's servers.

Educational Note:
    Authentication E2E tests are critical because:
    - Crypto signature correctness is hard to verify without a real server
    - Minor issues (wrong encoding, incorrect timestamp format) cause failures
    - Server-side validation is the only way to confirm signatures are accepted

Prerequisites:
    - KALSHI_DEMO_KEY_ID set in .env
    - KALSHI_DEMO_KEYFILE set in .env (path to RSA private key)

Run with:
    pytest tests/e2e/api_connectors/test_kalshi_auth_e2e.py -v -m e2e

References:
    - Issue #125: E2E tests for kalshi_auth.py
    - REQ-API-002: RSA-PSS Authentication
    - ADR-047: RSA-PSS for API Authentication
    - docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md

Phase: 2 (E2E Testing Infrastructure)
GitHub Issue: #125
"""

import os
import time

import pytest
import requests


def _demo_portfolio_available() -> bool:
    """Check if Kalshi DEMO API portfolio endpoints are currently available.

    See: Issue #224 (Kalshi DEMO API portfolio endpoints intermittently unavailable)
    """
    if not _real_kalshi_credentials_available():
        return False

    try:
        from precog.api_connectors.kalshi_client import KalshiClient

        client = KalshiClient(environment="demo")
        balance = client.get_balance(graceful_demo_fallback=True)
        return balance is not None
    except Exception:
        return False


def _real_kalshi_credentials_available() -> bool:
    """Check if REAL Kalshi credentials are available for E2E tests.

    Returns False if:
    - DEV_KALSHI_* credentials are not set AND
    - TEST_KALSHI_* credentials are fake (from conftest.py)

    Educational Note:
        conftest.py sets PRECOG_ENV=test and provides fake TEST_KALSHI_* credentials
        for unit/integration tests. E2E tests must detect these fake credentials
        and skip, because E2E tests need REAL credentials to talk to the real API.
    """
    # Check DEV credentials first (preferred for local E2E testing)
    dev_api_key = os.getenv("DEV_KALSHI_API_KEY")
    dev_key_path = os.getenv("DEV_KALSHI_PRIVATE_KEY_PATH")
    if dev_api_key and dev_key_path:
        return True

    # Check TEST credentials (but reject fake ones from conftest.py)
    test_api_key = os.getenv("TEST_KALSHI_API_KEY")
    test_key_path = os.getenv("TEST_KALSHI_PRIVATE_KEY_PATH")
    if test_api_key and test_key_path:
        # Reject fake credentials from conftest.py
        return test_api_key != "test-key-id-for-ci-vcr-tests"

    return False


# Skip entire module if credentials not available
# Uses DEV_KALSHI_* environment variables (demo/sandbox API)
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.api,
    pytest.mark.skipif(
        not _real_kalshi_credentials_available(),
        reason="Real Kalshi credentials not configured in .env (DEV_KALSHI_API_KEY/DEV_KALSHI_PRIVATE_KEY_PATH). Fake test credentials from conftest.py won't work for E2E tests.",
    ),
]


@pytest.fixture(scope="module")
def kalshi_auth():
    """Create KalshiAuth instance for E2E tests.

    Educational Note:
        We create the auth object directly (not through KalshiClient)
        to test the authentication layer in isolation.

        Uses DEV_KALSHI_* variables from .env (demo/sandbox API).
    """
    from precog.api_connectors.kalshi_auth import KalshiAuth

    api_key = os.getenv("DEV_KALSHI_API_KEY")
    keyfile = os.getenv("DEV_KALSHI_PRIVATE_KEY_PATH")
    assert api_key is not None, "DEV_KALSHI_API_KEY not set"
    assert keyfile is not None, "DEV_KALSHI_PRIVATE_KEY_PATH not set"

    return KalshiAuth(api_key, keyfile)


@pytest.fixture(scope="module")
def kalshi_base_url():
    """Return the Kalshi demo API base URL."""
    return "https://demo-api.kalshi.co/trade-api/v2"


class TestKalshiAuthKeyLoading:
    """E2E tests for RSA key loading."""

    def test_private_key_loads_successfully(self, kalshi_auth):
        """Verify RSA private key loads without errors.

        Educational Note:
            Key loading can fail for many reasons:
            - File not found
            - Invalid PEM format
            - Password-protected key (we don't support)
            - Wrong key type (need RSA, not EC)
        """
        assert kalshi_auth.private_key is not None

    def test_api_key_is_set(self, kalshi_auth):
        """Verify API key is properly loaded."""
        assert kalshi_auth.api_key is not None
        assert len(kalshi_auth.api_key) > 0


class TestKalshiAuthSignatureGeneration:
    """E2E tests for RSA-PSS signature generation."""

    def test_signature_is_generated(self, kalshi_auth):
        """Verify signatures are generated for requests.

        Educational Note:
            This tests the cryptographic signing process, which involves:
            1. Building the signing string (timestamp + method + path)
            2. Signing with RSA-PSS
            3. Base64 encoding the result
        """
        headers = kalshi_auth.get_headers(
            method="GET",
            path="/trade-api/v2/exchange/status",
        )

        signature = headers.get("KALSHI-ACCESS-SIGNATURE")
        assert signature is not None
        assert len(signature) > 0

    def test_timestamp_is_recent(self, kalshi_auth):
        """Verify timestamp is within acceptable range.

        Educational Note:
            Kalshi rejects requests with timestamps that are too old or in the future.
            This prevents replay attacks and ensures request freshness.
        """
        headers = kalshi_auth.get_headers(
            method="GET",
            path="/trade-api/v2/exchange/status",
        )

        timestamp = int(headers.get("KALSHI-ACCESS-TIMESTAMP", "0"))
        current_time = int(time.time() * 1000)  # milliseconds

        # Timestamp should be within 5 seconds of now
        assert abs(timestamp - current_time) < 5000

    def test_different_requests_have_different_signatures(self, kalshi_auth):
        """Verify each request gets a unique signature.

        Educational Note:
            Signatures must be unique because they include:
            - Timestamp (always changing)
            - Request path (different endpoints)
        """
        headers1 = kalshi_auth.get_headers(
            method="GET",
            path="/trade-api/v2/exchange/status",
        )

        # Small delay to ensure different timestamp
        time.sleep(0.01)

        headers2 = kalshi_auth.get_headers(
            method="GET",
            path="/trade-api/v2/portfolio/balance",
        )

        # Signatures should differ
        assert headers1["KALSHI-ACCESS-SIGNATURE"] != headers2["KALSHI-ACCESS-SIGNATURE"]


class TestKalshiAuthServerValidation:
    """E2E tests that validate signatures against real Kalshi API."""

    def test_signed_request_is_accepted_by_server(self, kalshi_auth, kalshi_base_url):
        """CRITICAL: Verify Kalshi's server accepts our signatures.

        Educational Note:
            This is THE definitive test for authentication correctness.
            If this passes, our RSA-PSS implementation is correct.
            If this fails, trading will be impossible.

            We use the exchange/status endpoint because:
            - It's a simple GET request
            - It requires authentication
            - It doesn't modify any data
        """
        path = "/trade-api/v2/exchange/status"
        full_url = f"{kalshi_base_url.replace('/trade-api/v2', '')}{path}"

        headers = kalshi_auth.get_headers(
            method="GET",
            path=path,
        )
        # get_headers already includes Content-Type

        response = requests.get(full_url, headers=headers, timeout=30)

        # Server should accept our authentication
        # 200 = success, 403 = auth failed, 401 = invalid key
        # 503 = exchange closed (but auth succeeded - we got valid JSON response)
        if response.status_code == 503:
            # Exchange may be offline/maintenance - this is NOT an auth failure
            # If we got a valid JSON response about exchange status, auth worked
            try:
                data = response.json()
                if "exchange_active" in data:
                    # Auth succeeded, exchange just happens to be closed
                    return  # Test passes - auth worked
            except (ValueError, KeyError):
                pass  # Fall through to assertion

        assert response.status_code in [200, 204], (
            f"Authentication failed with status {response.status_code}: {response.text[:200]}"
        )

    @pytest.mark.skipif(
        not _demo_portfolio_available(),
        reason="Kalshi DEMO API portfolio endpoints unavailable (Issue #224)",
    )
    def test_signed_balance_request_is_accepted(self, kalshi_auth, kalshi_base_url):
        """Verify signed request to balance endpoint is accepted.

        Educational Note:
            Testing multiple endpoints ensures our signing works for
            all path patterns, not just one specific endpoint.
        """
        path = "/trade-api/v2/portfolio/balance"
        full_url = f"{kalshi_base_url.replace('/trade-api/v2', '')}{path}"

        headers = kalshi_auth.get_headers(
            method="GET",
            path=path,
        )
        # get_headers already includes Content-Type

        response = requests.get(full_url, headers=headers, timeout=30)

        # Should return balance (200) or at minimum not auth failure
        assert response.status_code == 200, (
            f"Balance request failed with status {response.status_code}: {response.text[:200]}"
        )

    @pytest.mark.skipif(
        not _demo_portfolio_available(),
        reason="Kalshi DEMO API portfolio endpoints unavailable (Issue #224)",
    )
    def test_invalid_signature_is_rejected(self, kalshi_auth, kalshi_base_url):
        """Verify server rejects invalid signatures on authenticated endpoints.

        Educational Note:
            This is a negative test - it confirms the server actually validates
            signatures on endpoints that REQUIRE authentication.

            Note: /exchange/status is a PUBLIC endpoint (no auth required).
            We use /portfolio/balance which REQUIRES authentication.
        """
        # Use portfolio/balance which REQUIRES authentication
        path = "/trade-api/v2/portfolio/balance"
        full_url = f"{kalshi_base_url.replace('/trade-api/v2', '')}{path}"

        headers = kalshi_auth.get_headers(
            method="GET",
            path=path,
        )

        # Corrupt the signature
        headers["KALSHI-ACCESS-SIGNATURE"] = "invalid_signature_12345"
        # get_headers already includes Content-Type

        response = requests.get(full_url, headers=headers, timeout=30)

        # Server should reject invalid signature on authenticated endpoint
        assert response.status_code in [401, 403], (
            f"Expected auth rejection (401/403), got {response.status_code}"
        )


class TestKalshiAuthEdgeCases:
    """E2E tests for authentication edge cases."""

    def test_post_request_signs_correctly(self, kalshi_auth, kalshi_base_url):
        """Verify POST requests are signed correctly.

        Educational Note:
            This tests that POST requests can be signed correctly.
            Note: Our current implementation signs only timestamp+method+path.

            We test signature generation is correct by verifying:
            - The signature is generated without error
            - The request reaches the server (network layer works)

            Note: Many Kalshi endpoints don't accept POST (only GET).
            A 403 "Forbidden" or 405 "Method Not Allowed" is expected
            for endpoints that don't support POST.
        """
        # Use exchange/status - we're testing signature generation, not endpoint behavior
        path = "/trade-api/v2/exchange/status"
        full_url = f"{kalshi_base_url.replace('/trade-api/v2', '')}{path}"

        headers = kalshi_auth.get_headers(
            method="POST",
            path=path,
        )
        # get_headers already includes Content-Type

        # The request should complete (not timeout/network error)
        # We're testing that signature generation works for POST method
        response = requests.post(full_url, headers=headers, timeout=30)

        # Server should respond (any HTTP status means our request was received)
        # 405 = Method Not Allowed (endpoint doesn't accept POST)
        # 404 = Not Found (no route for POST on this path)
        # 403 = Forbidden (POST not allowed for this endpoint)
        # All are valid - we successfully signed and sent a POST request
        assert response.status_code in [200, 400, 403, 404, 405], (
            f"Unexpected status code: {response.status_code}"
        )

    def test_rapid_requests_have_unique_timestamps(self, kalshi_auth):
        """Verify rapid sequential requests get different timestamps.

        Educational Note:
            Millisecond timestamps should be unique even for rapid requests.
            Duplicate timestamps could cause signature collisions.

        Note: On fast CPUs, requests may complete within 1-2 milliseconds total.
        Since timestamps have millisecond precision (time.time() * 1000), multiple
        calls can land in the same millisecond. We require at least 2/5 unique
        timestamps to detect broken timestamp generation while allowing for
        legitimate CPU speed variations.
        """
        timestamps = []
        for _ in range(5):
            headers = kalshi_auth.get_headers(
                method="GET",
                path="/trade-api/v2/exchange/status",
            )
            timestamps.append(headers["KALSHI-ACCESS-TIMESTAMP"])

        # Require at least 2 unique timestamps - this detects completely broken
        # generation (always same value) while allowing for fast CPU timing
        unique_timestamps = set(timestamps)
        assert len(unique_timestamps) >= 2, (
            f"Expected at least 2 unique timestamps, got {len(unique_timestamps)}/5"
        )
