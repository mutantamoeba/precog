"""
Integration Tests for KalshiAuth Module.

Tests interactions between KalshiAuth components and external dependencies.

Reference: TESTING_STRATEGY V3.2 - Integration tests for module interactions
Related Requirements: REQ-API-002 (RSA-PSS Authentication)
Related ADR: ADR-047 (RSA-PSS Authentication Pattern)

Usage:
    pytest tests/integration/api_connectors/test_kalshi_auth_integration.py -v -m integration
"""

import base64
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.api_connectors.kalshi_auth import (
    KalshiAuth,
    generate_signature,
    load_private_key,
)

# =============================================================================
# Integration Tests: Key Loading Integration
# =============================================================================


@pytest.mark.integration
class TestKeyLoadingIntegration:
    """Integration tests for private key loading."""

    def test_load_key_and_generate_signature(self, tmp_path) -> None:
        """Test integration between load_private_key and generate_signature.

        Creates a temporary RSA key, loads it, and generates signatures.
        """
        # Generate a real RSA key for testing
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Save to file
        key_path = tmp_path / "test_key.pem"
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Load and use for signature
        loaded_key = load_private_key(str(key_path))

        signature = generate_signature(
            private_key=loaded_key,
            timestamp=1234567890000,
            method="GET",
            path="/trade-api/v2/markets",
        )

        # Verify signature is valid base64
        decoded = base64.b64decode(signature)
        assert len(decoded) > 0

    def test_kalshi_auth_with_real_key_file(self, tmp_path) -> None:
        """Test KalshiAuth integration with real key file.

        Creates temporary RSA key and uses it with KalshiAuth.
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Generate key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        key_path = tmp_path / "kalshi_test_key.pem"
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Create KalshiAuth with real key
        auth = KalshiAuth(
            api_key="test-api-key-uuid",
            private_key_path=str(key_path),
        )

        # Generate headers
        headers = auth.get_headers("GET", "/trade-api/v2/markets")

        # Verify all components
        assert headers["KALSHI-ACCESS-KEY"] == "test-api-key-uuid"
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers

        # Verify signature is valid base64
        signature = headers["KALSHI-ACCESS-SIGNATURE"]
        decoded = base64.b64decode(signature)
        assert len(decoded) > 0


# =============================================================================
# Integration Tests: Header Generation Flow
# =============================================================================


@pytest.mark.integration
class TestHeaderGenerationIntegration:
    """Integration tests for complete header generation flow."""

    def _create_real_key_auth(self, tmp_path) -> tuple[KalshiAuth, Path]:
        """Create KalshiAuth with real RSA key."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        key_path = tmp_path / "test.pem"
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        auth = KalshiAuth(
            api_key="integration-test-key",
            private_key_path=str(key_path),
        )

        return auth, key_path

    def test_sequential_headers_have_different_timestamps(self, tmp_path) -> None:
        """Sequential header generations have increasing timestamps."""
        auth, _ = self._create_real_key_auth(tmp_path)

        headers1 = auth.get_headers("GET", "/test")
        time.sleep(0.01)  # Small delay
        headers2 = auth.get_headers("GET", "/test")

        ts1 = int(headers1["KALSHI-ACCESS-TIMESTAMP"])
        ts2 = int(headers2["KALSHI-ACCESS-TIMESTAMP"])

        assert ts2 >= ts1

    def test_different_paths_produce_different_signatures(self, tmp_path) -> None:
        """Different API paths produce different signatures."""
        auth, _ = self._create_real_key_auth(tmp_path)

        # Use same timestamp by mocking time
        with patch("precog.api_connectors.kalshi_auth.time.time") as mock_time:
            mock_time.return_value = 1234567.890

            headers1 = auth.get_headers("GET", "/trade-api/v2/markets")
            headers2 = auth.get_headers("GET", "/trade-api/v2/portfolio/balance")

        sig1 = headers1["KALSHI-ACCESS-SIGNATURE"]
        sig2 = headers2["KALSHI-ACCESS-SIGNATURE"]

        assert sig1 != sig2

    def test_different_methods_produce_different_signatures(self, tmp_path) -> None:
        """Different HTTP methods produce different signatures."""
        auth, _ = self._create_real_key_auth(tmp_path)

        with patch("precog.api_connectors.kalshi_auth.time.time") as mock_time:
            mock_time.return_value = 1234567.890

            headers_get = auth.get_headers("GET", "/test")
            headers_post = auth.get_headers("POST", "/test")

        sig_get = headers_get["KALSHI-ACCESS-SIGNATURE"]
        sig_post = headers_post["KALSHI-ACCESS-SIGNATURE"]

        assert sig_get != sig_post

    def test_headers_work_for_all_api_endpoints(self, tmp_path) -> None:
        """Headers generation works for all common API endpoints."""
        auth, _ = self._create_real_key_auth(tmp_path)

        endpoints = [
            ("GET", "/trade-api/v2/markets"),
            ("GET", "/trade-api/v2/portfolio/balance"),
            ("GET", "/trade-api/v2/portfolio/positions"),
            ("POST", "/trade-api/v2/portfolio/orders"),
            ("DELETE", "/trade-api/v2/portfolio/orders/abc123"),
            ("GET", "/trade-api/v2/events"),
            ("GET", "/trade-api/v2/series"),
        ]

        for method, path in endpoints:
            headers = auth.get_headers(method, path)

            assert "KALSHI-ACCESS-KEY" in headers
            assert "KALSHI-ACCESS-TIMESTAMP" in headers
            assert "KALSHI-ACCESS-SIGNATURE" in headers
            assert headers["Content-Type"] == "application/json"


# =============================================================================
# Integration Tests: Token Management
# =============================================================================


@pytest.mark.integration
class TestTokenManagementIntegration:
    """Integration tests for token management features."""

    def test_token_expiry_workflow(self) -> None:
        """Test complete token expiry check workflow."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        # Initially expired (no token)
        assert auth.is_token_expired() is True

        # Set valid token
        auth.token = "valid-token"
        auth.token_expiry = int(time.time() * 1000) + 60000  # 60s future

        assert auth.is_token_expired() is False

        # Simulate token expiry
        auth.token_expiry = int(time.time() * 1000) - 1000  # 1s ago

        assert auth.is_token_expired() is True

    def test_refresh_token_workflow(self) -> None:
        """Test token refresh workflow."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        # Token is expired
        assert auth.is_token_expired() is True

        # Call refresh (doesn't do much in Phase 1, but should not error)
        auth.refresh_token()

        # If token was set by another mechanism
        auth.token = "new-token"
        auth.token_expiry = int(time.time() * 1000) + 60000

        # Now valid
        assert auth.is_token_expired() is False

        # Refresh should skip (double-check pattern)
        auth.refresh_token()
        assert auth.token == "new-token"


# =============================================================================
# Integration Tests: Thread Safety
# =============================================================================


@pytest.mark.integration
class TestThreadSafetyIntegration:
    """Integration tests for thread-safe operations."""

    def test_concurrent_get_headers_with_real_key(self, tmp_path) -> None:
        """Multiple threads can generate headers with real key concurrently."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        key_path = tmp_path / "thread_test.pem"
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        auth = KalshiAuth(
            api_key="thread-test-key",
            private_key_path=str(key_path),
        )

        results = []
        errors = []

        def generate_headers(thread_id: int):
            try:
                for i in range(10):
                    headers = auth.get_headers("GET", f"/test/{thread_id}/{i}")
                    results.append(headers)
            except Exception as e:
                errors.append((thread_id, e))

        threads = [threading.Thread(target=generate_headers, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 iterations

    def test_concurrent_token_checks(self) -> None:
        """Multiple threads can check token expiry concurrently."""
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )
        auth.token = "test-token"
        auth.token_expiry = int(time.time() * 1000) + 60000

        results = []
        errors = []

        def check_expiry(thread_id: int):
            try:
                for _ in range(100):
                    result = auth.is_token_expired()
                    results.append(result)
            except Exception as e:
                errors.append((thread_id, e))

        threads = [threading.Thread(target=check_expiry, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 1000
        # All results should be False (token not expired)
        assert all(r is False for r in results)

    def test_concurrent_refresh_with_token_update(self) -> None:
        """Multiple threads calling refresh_token safely."""
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        errors = []
        refresh_count = [0]
        refresh_lock = threading.Lock()

        def attempt_refresh(thread_id: int):
            try:
                for _ in range(20):
                    auth.refresh_token()
                    with refresh_lock:
                        refresh_count[0] += 1
            except Exception as e:
                errors.append((thread_id, e))

        threads = [threading.Thread(target=attempt_refresh, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert refresh_count[0] == 100  # 5 threads * 20 iterations


# =============================================================================
# Integration Tests: Dependency Injection
# =============================================================================


@pytest.mark.integration
class TestDependencyInjectionIntegration:
    """Integration tests for dependency injection pattern."""

    def test_custom_key_loader_integration(self) -> None:
        """Custom key loader integrates correctly."""
        loaded_paths = []
        mock_key = MagicMock()
        mock_key.sign.return_value = b"custom_sig"

        def custom_loader(path: str):
            loaded_paths.append(path)
            return mock_key

        auth = KalshiAuth(
            api_key="di-test-key",
            private_key_path="/custom/path.pem",
            key_loader=custom_loader,
        )

        # Verify loader was called
        assert len(loaded_paths) == 1
        assert loaded_paths[0] == "/custom/path.pem"

        # Verify headers work
        headers = auth.get_headers("GET", "/test")
        assert headers["KALSHI-ACCESS-KEY"] == "di-test-key"

    def test_mock_key_for_testing(self) -> None:
        """Mock key pattern for unit testing works correctly."""
        mock_key = MagicMock()
        mock_key.sign.return_value = b"mock_signature_for_testing"

        auth = KalshiAuth(
            api_key="test-key",
            private_key_path="/fake/path",
            key_loader=lambda p: mock_key,
        )

        headers = auth.get_headers("POST", "/trade-api/v2/orders")

        # Verify mock was used
        mock_key.sign.assert_called()

        # Verify signature contains mock output
        decoded_sig = base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"])
        assert decoded_sig == b"mock_signature_for_testing"


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling across components."""

    def test_key_loading_error_propagates(self, tmp_path) -> None:
        """Key loading errors propagate correctly through KalshiAuth."""
        non_existent = tmp_path / "missing.pem"

        with pytest.raises(FileNotFoundError) as exc_info:
            KalshiAuth(
                api_key="key",
                private_key_path=str(non_existent),
            )

        assert "Private key not found" in str(exc_info.value)

    def test_invalid_key_format_error_propagates(self, tmp_path) -> None:
        """Invalid key format errors propagate correctly."""
        invalid_key = tmp_path / "invalid.pem"
        invalid_key.write_text("not a valid key")

        with pytest.raises(ValueError) as exc_info:
            KalshiAuth(
                api_key="key",
                private_key_path=str(invalid_key),
            )

        assert "Failed to load private key" in str(exc_info.value)


# =============================================================================
# Integration Tests: Real Cryptographic Operations
# =============================================================================


@pytest.mark.integration
class TestCryptographicIntegration:
    """Integration tests for actual cryptographic operations."""

    def test_signature_verification_with_public_key(self, tmp_path) -> None:
        """Generated signature can be verified with corresponding public key.

        This tests the cryptographic correctness of the signature generation.
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        # Generate key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()

        # Save private key
        key_path = tmp_path / "crypto_test.pem"
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Create auth and generate signature
        auth = KalshiAuth(
            api_key="crypto-test",
            private_key_path=str(key_path),
        )

        with patch("precog.api_connectors.kalshi_auth.time.time") as mock_time:
            mock_time.return_value = 1234567.890
            headers = auth.get_headers("GET", "/trade-api/v2/markets")

        # Extract signature and reconstruct message
        signature_b64 = headers["KALSHI-ACCESS-SIGNATURE"]
        signature_bytes = base64.b64decode(signature_b64)
        timestamp = headers["KALSHI-ACCESS-TIMESTAMP"]
        message = f"{timestamp}GET/trade-api/v2/markets".encode()

        # Verify signature with public key (should not raise)
        public_key.verify(
            signature_bytes,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )

    def test_different_keys_produce_invalid_verification(self, tmp_path) -> None:
        """Signature from one key cannot be verified with different key.

        This ensures signatures are actually tied to the specific key.
        """
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        # Generate two different key pairs
        private_key1 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key2 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key2 = private_key2.public_key()

        # Save first key
        key_path = tmp_path / "key1.pem"
        with open(key_path, "wb") as f:
            f.write(
                private_key1.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Create auth with first key
        auth = KalshiAuth(
            api_key="key1-test",
            private_key_path=str(key_path),
        )

        with patch("precog.api_connectors.kalshi_auth.time.time") as mock_time:
            mock_time.return_value = 1234567.890
            headers = auth.get_headers("GET", "/test")

        # Try to verify with second key's public key (should fail)
        signature_bytes = base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"])
        timestamp = headers["KALSHI-ACCESS-TIMESTAMP"]
        message = f"{timestamp}GET/test".encode()

        with pytest.raises(InvalidSignature):
            public_key2.verify(
                signature_bytes,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH,
                ),
                hashes.SHA256(),
            )
