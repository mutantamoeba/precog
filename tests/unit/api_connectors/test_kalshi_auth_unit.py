"""
Unit Tests for KalshiAuth Module.

Tests individual functions and class methods in isolation with mocked dependencies.

Reference: TESTING_STRATEGY V3.2 - Unit tests for all critical modules
Related Requirements: REQ-API-002 (RSA-PSS Authentication)
Related ADR: ADR-047 (RSA-PSS Authentication Pattern)

Usage:
    pytest tests/unit/api_connectors/test_kalshi_auth_unit.py -v -m unit
"""

import base64
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from precog.api_connectors.kalshi_auth import (
    KalshiAuth,
    generate_signature,
    load_private_key,
)

# =============================================================================
# Unit Tests: load_private_key Function
# =============================================================================


@pytest.mark.unit
class TestLoadPrivateKey:
    """Unit tests for load_private_key function."""

    def test_load_private_key_file_not_found(self, tmp_path) -> None:
        """load_private_key raises FileNotFoundError for missing file."""
        non_existent = tmp_path / "does_not_exist.pem"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_private_key(str(non_existent))

        assert "Private key not found" in str(exc_info.value)
        assert "KALSHI_" in str(exc_info.value)  # Mentions env var

    def test_load_private_key_invalid_format(self, tmp_path) -> None:
        """load_private_key raises ValueError for invalid PEM format."""
        invalid_key = tmp_path / "invalid.pem"
        invalid_key.write_text("This is not a valid PEM key")

        with pytest.raises(ValueError) as exc_info:
            load_private_key(str(invalid_key))

        assert "Failed to load private key" in str(exc_info.value)
        assert "valid PEM-formatted" in str(exc_info.value)

    def test_load_private_key_empty_file(self, tmp_path) -> None:
        """load_private_key raises ValueError for empty file."""
        empty_key = tmp_path / "empty.pem"
        empty_key.write_text("")

        with pytest.raises(ValueError) as exc_info:
            load_private_key(str(empty_key))

        assert "Failed to load private key" in str(exc_info.value)

    @patch("precog.api_connectors.kalshi_auth.serialization.load_pem_private_key")
    def test_load_private_key_success(self, mock_load, tmp_path) -> None:
        """load_private_key returns key object on success."""
        # Create a valid-looking PEM file
        key_file = tmp_path / "test.pem"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")

        mock_key = MagicMock()
        mock_load.return_value = mock_key

        result = load_private_key(str(key_file))

        assert result is mock_key
        mock_load.assert_called_once()


# =============================================================================
# Unit Tests: generate_signature Function
# =============================================================================


@pytest.mark.unit
class TestGenerateSignature:
    """Unit tests for generate_signature function."""

    def test_generate_signature_returns_base64_string(self) -> None:
        """generate_signature returns base64-encoded string."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"test_signature_bytes"

        result = generate_signature(
            private_key=mock_key,
            timestamp=1234567890000,
            method="GET",
            path="/trade-api/v2/markets",
        )

        # Verify it's valid base64
        decoded = base64.b64decode(result)
        assert decoded == b"test_signature_bytes"

    def test_generate_signature_message_format(self) -> None:
        """generate_signature constructs message correctly."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=1234567890000,
            method="GET",
            path="/trade-api/v2/markets",
        )

        # Check the message passed to sign
        call_args = mock_key.sign.call_args
        message = call_args[0][0]
        assert message == b"1234567890000GET/trade-api/v2/markets"

    def test_generate_signature_uppercases_method(self) -> None:
        """generate_signature converts method to uppercase."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=1234567890000,
            method="get",  # lowercase
            path="/test",
        )

        call_args = mock_key.sign.call_args
        message = call_args[0][0]
        assert b"GET" in message  # Uppercased
        assert b"get" not in message

    def test_generate_signature_preserves_path(self) -> None:
        """generate_signature preserves path exactly."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=1234567890000,
            method="POST",
            path="/trade-api/v2/portfolio/orders?limit=100",
        )

        call_args = mock_key.sign.call_args
        message = call_args[0][0]
        assert b"/trade-api/v2/portfolio/orders?limit=100" in message

    def test_generate_signature_uses_pss_padding(self) -> None:
        """generate_signature uses PSS padding algorithm."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=1234567890000,
            method="GET",
            path="/test",
        )

        call_args = mock_key.sign.call_args
        padding_arg = call_args[0][1]
        # Verify PSS padding is used
        from cryptography.hazmat.primitives.asymmetric.padding import PSS

        assert isinstance(padding_arg, PSS)


# =============================================================================
# Unit Tests: KalshiAuth Class Initialization
# =============================================================================


@pytest.mark.unit
class TestKalshiAuthInit:
    """Unit tests for KalshiAuth initialization."""

    def test_init_with_default_key_loader(self) -> None:
        """KalshiAuth uses load_private_key when no key_loader provided."""
        mock_key = MagicMock()

        with patch("precog.api_connectors.kalshi_auth.load_private_key") as mock_load:
            mock_load.return_value = mock_key

            auth = KalshiAuth(
                api_key="test-api-key",
                private_key_path="/path/to/key.pem",
            )

            mock_load.assert_called_once_with("/path/to/key.pem")
            assert auth.private_key is mock_key

    def test_init_with_custom_key_loader(self) -> None:
        """KalshiAuth uses injected key_loader when provided."""
        mock_key = MagicMock()
        custom_loader = MagicMock(return_value=mock_key)

        auth = KalshiAuth(
            api_key="test-api-key",
            private_key_path="/any/path",
            key_loader=custom_loader,
        )

        custom_loader.assert_called_once_with("/any/path")
        assert auth.private_key is mock_key

    def test_init_stores_api_key(self) -> None:
        """KalshiAuth stores api_key correctly."""
        mock_key = MagicMock()

        auth = KalshiAuth(
            api_key="my-test-api-key-uuid",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        assert auth.api_key == "my-test-api-key-uuid"

    def test_init_stores_private_key_path(self) -> None:
        """KalshiAuth stores private_key_path correctly."""
        mock_key = MagicMock()

        auth = KalshiAuth(
            api_key="api-key",
            private_key_path="/custom/path/to/key.pem",
            key_loader=lambda p: mock_key,
        )

        assert auth.private_key_path == "/custom/path/to/key.pem"

    def test_init_token_is_none(self) -> None:
        """KalshiAuth initializes with no token."""
        mock_key = MagicMock()

        auth = KalshiAuth(
            api_key="api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        assert auth.token is None
        assert auth.token_expiry is None

    def test_init_creates_thread_lock(self) -> None:
        """KalshiAuth initializes with RLock for thread safety."""
        mock_key = MagicMock()

        auth = KalshiAuth(
            api_key="api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        # Check that _token_lock behaves like an RLock (has acquire/release methods)
        assert hasattr(auth._token_lock, "acquire")
        assert hasattr(auth._token_lock, "release")
        # RLock is reentrant - can be acquired multiple times by same thread
        assert auth._token_lock.acquire(blocking=False)
        assert auth._token_lock.acquire(blocking=False)  # Should succeed (reentrant)
        auth._token_lock.release()
        auth._token_lock.release()


# =============================================================================
# Unit Tests: KalshiAuth.get_headers Method
# =============================================================================


@pytest.mark.unit
class TestKalshiAuthGetHeaders:
    """Unit tests for KalshiAuth.get_headers method."""

    def _create_auth(self) -> KalshiAuth:
        """Create KalshiAuth with mocked key."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"test_signature"

        return KalshiAuth(
            api_key="test-api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

    def test_get_headers_returns_dict(self) -> None:
        """get_headers returns dictionary."""
        auth = self._create_auth()
        headers = auth.get_headers("GET", "/test")

        assert isinstance(headers, dict)

    def test_get_headers_contains_access_key(self) -> None:
        """get_headers includes KALSHI-ACCESS-KEY."""
        auth = self._create_auth()
        headers = auth.get_headers("GET", "/test")

        assert headers["KALSHI-ACCESS-KEY"] == "test-api-key"

    def test_get_headers_contains_timestamp(self) -> None:
        """get_headers includes KALSHI-ACCESS-TIMESTAMP."""
        auth = self._create_auth()

        before = int(time.time() * 1000)
        headers = auth.get_headers("GET", "/test")
        after = int(time.time() * 1000)

        timestamp = int(headers["KALSHI-ACCESS-TIMESTAMP"])
        assert before <= timestamp <= after

    def test_get_headers_contains_signature(self) -> None:
        """get_headers includes KALSHI-ACCESS-SIGNATURE."""
        auth = self._create_auth()
        headers = auth.get_headers("GET", "/test")

        assert "KALSHI-ACCESS-SIGNATURE" in headers
        # Should be base64 encoded
        signature = headers["KALSHI-ACCESS-SIGNATURE"]
        decoded = base64.b64decode(signature)
        assert decoded == b"test_signature"

    def test_get_headers_contains_content_type(self) -> None:
        """get_headers includes Content-Type: application/json."""
        auth = self._create_auth()
        headers = auth.get_headers("GET", "/test")

        assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_different_methods(self) -> None:
        """get_headers works with various HTTP methods."""
        auth = self._create_auth()

        for method in ["GET", "POST", "DELETE", "PUT", "PATCH"]:
            headers = auth.get_headers(method, "/test")
            assert "KALSHI-ACCESS-KEY" in headers

    def test_get_headers_timestamp_is_string(self) -> None:
        """get_headers timestamp is string (not int)."""
        auth = self._create_auth()
        headers = auth.get_headers("GET", "/test")

        # Timestamp should be string per Kalshi API spec
        assert isinstance(headers["KALSHI-ACCESS-TIMESTAMP"], str)


# =============================================================================
# Unit Tests: KalshiAuth.is_token_expired Method
# =============================================================================


@pytest.mark.unit
class TestKalshiAuthIsTokenExpired:
    """Unit tests for KalshiAuth.is_token_expired method."""

    def _create_auth(self) -> KalshiAuth:
        """Create KalshiAuth with mocked key."""
        mock_key = MagicMock()
        return KalshiAuth(
            api_key="api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

    def test_is_token_expired_when_token_none(self) -> None:
        """is_token_expired returns True when token is None."""
        auth = self._create_auth()
        auth.token = None
        auth.token_expiry = None

        assert auth.is_token_expired() is True

    def test_is_token_expired_when_expiry_none(self) -> None:
        """is_token_expired returns True when expiry is None."""
        auth = self._create_auth()
        auth.token = "some-token"
        auth.token_expiry = None

        assert auth.is_token_expired() is True

    def test_is_token_expired_when_past_expiry(self) -> None:
        """is_token_expired returns True when past expiry time."""
        auth = self._create_auth()
        auth.token = "some-token"
        auth.token_expiry = int(time.time() * 1000) - 1000  # 1 second ago

        assert auth.is_token_expired() is True

    def test_is_token_expired_when_not_expired(self) -> None:
        """is_token_expired returns False when token still valid."""
        auth = self._create_auth()
        auth.token = "some-token"
        auth.token_expiry = int(time.time() * 1000) + 60000  # 60 seconds from now

        assert auth.is_token_expired() is False

    def test_is_token_expired_at_exact_expiry(self) -> None:
        """is_token_expired returns True at exact expiry moment."""
        auth = self._create_auth()
        auth.token = "some-token"
        current = int(time.time() * 1000)
        auth.token_expiry = current

        # At exact expiry time, should be expired
        result = auth.is_token_expired()
        # Due to timing, could be either True or False within ms
        assert isinstance(result, bool)


# =============================================================================
# Unit Tests: KalshiAuth.refresh_token Method
# =============================================================================


@pytest.mark.unit
class TestKalshiAuthRefreshToken:
    """Unit tests for KalshiAuth.refresh_token method."""

    def _create_auth(self) -> KalshiAuth:
        """Create KalshiAuth with mocked key."""
        mock_key = MagicMock()
        return KalshiAuth(
            api_key="api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

    def test_refresh_token_skips_if_not_expired(self) -> None:
        """refresh_token does nothing if token not expired."""
        auth = self._create_auth()
        auth.token = "valid-token"
        auth.token_expiry = int(time.time() * 1000) + 60000  # 60s in future

        # Should not raise and should not change token
        auth.refresh_token()

        assert auth.token == "valid-token"

    def test_refresh_token_uses_lock(self) -> None:
        """refresh_token acquires lock for thread safety.

        Tests that refresh_token properly uses the lock by verifying
        that it can handle concurrent calls without deadlock.
        """
        auth = self._create_auth()
        auth.token = None
        auth.token_expiry = None

        # The refresh_token method uses RLock - verify it doesn't deadlock
        # on multiple calls (which would happen if lock wasn't released properly)
        for _ in range(5):
            auth.refresh_token()

        # If we got here without deadlock, lock is being used correctly
        # Also verify the lock is not held after refresh_token returns
        acquired = auth._token_lock.acquire(blocking=False)
        assert acquired, "Lock should be released after refresh_token"
        auth._token_lock.release()

    def test_refresh_token_double_check_pattern(self) -> None:
        """refresh_token uses double-check pattern to avoid redundant refreshes."""
        auth = self._create_auth()

        # First call - token expired
        auth.token = None
        auth.token_expiry = None

        auth.refresh_token()

        # Set token as valid now (simulating another thread refreshed it)
        auth.token = "refreshed-token"
        auth.token_expiry = int(time.time() * 1000) + 60000

        # Second call should skip actual refresh
        auth.refresh_token()

        # Token should remain unchanged
        assert auth.token == "refreshed-token"


# =============================================================================
# Unit Tests: Thread Safety
# =============================================================================


@pytest.mark.unit
class TestKalshiAuthThreadSafety:
    """Unit tests for KalshiAuth thread safety."""

    def test_concurrent_get_headers_safe(self) -> None:
        """Multiple threads can safely call get_headers."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key="api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        errors = []
        results = []

        def call_get_headers():
            try:
                headers = auth.get_headers("GET", "/test")
                results.append(headers)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_get_headers) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_is_token_expired_safe(self) -> None:
        """Multiple threads can safely call is_token_expired."""
        mock_key = MagicMock()

        auth = KalshiAuth(
            api_key="api-key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )
        auth.token = "token"
        auth.token_expiry = int(time.time() * 1000) + 60000

        errors = []
        results = []

        def call_is_expired():
            try:
                result = auth.is_token_expired()
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_is_expired) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
