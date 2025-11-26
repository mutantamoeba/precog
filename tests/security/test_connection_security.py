"""
Security tests for connection string sanitization and API key rotation.

This test suite verifies:
1. Database connection strings mask passwords in all error paths
2. API key rotation properly rejects old keys
3. Token expiry triggers re-authentication

**TDD NOTICE**: Tests requiring logger credential masking are marked @pytest.mark.skip
until the logger sanitization functionality is implemented.

Related Issue: GitHub Issue #129 (Security Tests)
Related Pattern: Pattern 4 (Security - NO CREDENTIALS IN CODE)
Related Requirement: REQ-SEC-009 (Connection Security)
"""

import os
from unittest.mock import Mock, patch

import pytest
import requests

from precog.api_connectors.kalshi_client import KalshiClient

# Skip marker for credential masking tests - not implemented yet
CREDENTIAL_MASKING_SKIP = pytest.mark.skip(
    reason="TDD Test: Logger credential masking not yet implemented. "
    "Tests define required behavior for Phase 2+ implementation."
)

# =============================================================================
# Test Credentials (FAKE - for testing only)
# =============================================================================

FAKE_DB_PASSWORD = "SuperSecretDB_Pass123!"
FAKE_OLD_API_KEY = "old-api-key-abc123-expired"
FAKE_NEW_API_KEY = "new-api-key-xyz789-valid"


# =============================================================================
# Test 1: Connection String Sanitization (TDD - SKIPPED)
# =============================================================================


@CREDENTIAL_MASKING_SKIP
def test_connection_timeout_masks_password_in_error(monkeypatch) -> None:
    """
    TDD Test: Verify connection timeout errors mask password in connection string.

    **Security Guarantee**: Network timeout errors must sanitize connection strings.

    This test is skipped until logger credential masking is implemented.
    """


@CREDENTIAL_MASKING_SKIP
def test_invalid_database_name_masks_password_in_error(monkeypatch) -> None:
    """
    TDD Test: Verify invalid database name errors mask password.

    **Security Guarantee**: Database name errors must sanitize connection strings.

    This test is skipped until logger credential masking is implemented.
    """


@CREDENTIAL_MASKING_SKIP
def test_authentication_failed_masks_password_in_error(monkeypatch) -> None:
    """
    TDD Test: Verify authentication failed errors mask password.

    **Security Guarantee**: Auth failure errors must sanitize connection strings.

    This test is skipped until logger credential masking is implemented.
    """


# =============================================================================
# Test 2: API Key Rotation (ENABLED - uses mock infrastructure)
# =============================================================================


@pytest.mark.skip(reason="Requires Kalshi API credentials configured in .env")
def test_old_api_key_rejected_after_rotation(monkeypatch) -> None:
    """
    Verify that old API keys are properly rejected after rotation.

    **Security Guarantee**: Rotated API keys must be invalid immediately.

    This test requires actual Kalshi demo credentials to verify API key rotation.
    Skip if credentials not available.

    Educational Note:
        API key rotation workflow:
        1. Generate new API key in Kalshi dashboard
        2. Update application with new key
        3. Old key should immediately return 401 Unauthorized
        4. No grace period - old keys are invalid immediately

    Args:
        monkeypatch: Pytest fixture for environment variable mocking

    Expected Result:
        - Old API key returns 401 Unauthorized
        - New API key returns 200 OK
        - No data returned for old key
    """
    # Test requires actual API credentials


# =============================================================================
# Test 3: Environment Variable Leak Prevention (TDD - SKIPPED)
# =============================================================================


@CREDENTIAL_MASKING_SKIP
def test_environment_variables_not_leaked_in_stack_traces(monkeypatch) -> None:
    """
    TDD Test: Verify environment variables with credentials don't leak in stack traces.

    **Security Guarantee**: os.environ values must not appear in logged exceptions.

    This test is skipped until logger credential masking is implemented.
    """


@CREDENTIAL_MASKING_SKIP
def test_http_basic_auth_masked_in_request_logs(monkeypatch) -> None:
    """
    TDD Test: Verify HTTP Basic Auth headers are masked in request logs.

    **Security Guarantee**: Authorization headers must be masked in logs.

    This test is skipped until logger credential masking is implemented.
    """


# =============================================================================
# Test 4: Token Expiry Handling (ENABLED - unit test with mocks)
# =============================================================================


def test_kalshi_auth_token_expiry_triggers_reauth() -> None:
    """
    Verify that expired tokens trigger re-authentication.

    **Security Guarantee**: Expired tokens must be refreshed, not reused.

    This test verifies the is_token_expired() logic using mocks.
    Does not require actual API credentials.

    Educational Note:
        Token expiry handling:
        1. Check token expiry before each API call
        2. If expired, automatically re-authenticate
        3. Log token refresh events (without exposing token value)

    Expected Result:
        - is_token_expired() returns True when expiry in past
        - is_token_expired() returns False when expiry in future
        - Token refresh triggers new authentication
    """
    import time

    from precog.api_connectors.kalshi_auth import KalshiAuth

    with patch("precog.api_connectors.kalshi_auth.load_private_key") as mock_load:
        # Setup mock private key
        mock_key = Mock()
        mock_key.sign = Mock(return_value=b"fake_signature")
        mock_load.return_value = mock_key

        auth = KalshiAuth(api_key="test-key", private_key_path="/fake/path.pem")

        # Test 1: No token set - should be expired
        assert auth.is_token_expired() is True, "Missing token should be expired"

        # Test 2: Token with expiry in past - should be expired
        auth.token = "test-token"
        auth.token_expiry = int((time.time() - 3600) * 1000)  # 1 hour ago
        assert auth.is_token_expired() is True, "Past expiry should be expired"

        # Test 3: Token with expiry in future - should NOT be expired
        auth.token_expiry = int((time.time() + 3600) * 1000)  # 1 hour from now
        assert auth.is_token_expired() is False, "Future expiry should not be expired"


def test_kalshi_client_handles_401_gracefully() -> None:
    """
    Verify KalshiClient properly handles 401 Unauthorized errors.

    **Security Guarantee**: 401 errors must not leak credentials in error messages.

    This test verifies error handling using mocks.

    Educational Note:
        Proper 401 handling:
        1. Catch 401 response
        2. Clear cached token (force re-auth on next request)
        3. Log event WITHOUT exposing credentials
        4. Raise descriptive exception

    Expected Result:
        - 401 response raises appropriate exception
        - Error message describes the issue
        - No credentials in exception message
    """
    with patch("precog.api_connectors.kalshi_auth.load_private_key") as mock_load:
        # Setup mock private key
        mock_key = Mock()
        mock_key.sign = Mock(return_value=b"fake_signature")
        mock_load.return_value = mock_key

        with patch.dict(
            os.environ,
            {
                "KALSHI_DEMO_KEY_ID": "test-key-id",
                "KALSHI_DEMO_KEYFILE": "/fake/path.pem",
            },
        ):
            client = KalshiClient(environment="demo")

            # Mock 401 response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"error": "Unauthorized"}
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock_response
            )

            with patch.object(client.session, "request", return_value=mock_response):
                # Attempt to get balance (will fail with 401)
                with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                    client._make_request("GET", "/portfolio/balance")

                # Verify error response is 401
                assert exc_info.value.response.status_code == 401

                # Verify no credentials in exception message
                error_str = str(exc_info.value)
                assert "test-key-id" not in error_str
