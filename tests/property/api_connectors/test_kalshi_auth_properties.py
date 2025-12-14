"""
Property-based Tests for KalshiAuth Module.

Tests mathematical properties and invariants of the Kalshi authentication system
using Hypothesis to generate diverse test inputs.

Reference: TESTING_STRATEGY V3.2 - Property tests for all business logic
Related Requirements: REQ-API-002 (RSA-PSS Authentication)
Related ADR: ADR-047 (RSA-PSS Authentication Pattern)

Usage:
    pytest tests/property/api_connectors/test_kalshi_auth_properties.py -v -m property
"""

import base64
import string
import time
from unittest.mock import MagicMock

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from precog.api_connectors.kalshi_auth import (
    KalshiAuth,
    generate_signature,
)

# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================


@st.composite
def valid_timestamp_strategy(draw: st.DrawFn) -> int:
    """Generate valid timestamps in milliseconds."""
    # Reasonable range: year 2020 to 2030
    min_ts = 1577836800000  # Jan 1, 2020
    max_ts = 1893456000000  # Jan 1, 2030
    return draw(st.integers(min_value=min_ts, max_value=max_ts))


@st.composite
def http_method_strategy(draw: st.DrawFn) -> str:
    """Generate valid HTTP methods."""
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    return draw(st.sampled_from(methods))


@st.composite
def http_method_any_case_strategy(draw: st.DrawFn) -> str:
    """Generate HTTP methods in any case (upper, lower, mixed)."""
    methods = ["get", "GET", "Get", "post", "POST", "Post", "delete", "DELETE"]
    return draw(st.sampled_from(methods))


@st.composite
def api_path_strategy(draw: st.DrawFn) -> str:
    """Generate valid API paths."""
    prefixes = ["/trade-api/v2", "/trade-api/v1", "/api/v1"]
    endpoints = [
        "/markets",
        "/portfolio/balance",
        "/portfolio/positions",
        "/portfolio/orders",
        "/events",
        "/series",
    ]
    prefix = draw(st.sampled_from(prefixes))
    endpoint = draw(st.sampled_from(endpoints))
    return prefix + endpoint


@st.composite
def api_path_with_query_strategy(draw: st.DrawFn) -> str:
    """Generate API paths with query parameters."""
    base_path = draw(api_path_strategy())
    params = ["limit=100", "cursor=abc123", "status=active", "ticker=TEST"]
    num_params = draw(st.integers(min_value=0, max_value=3))

    if num_params == 0:
        return base_path

    selected_params = draw(
        st.lists(st.sampled_from(params), min_size=1, max_size=num_params, unique=True)
    )
    return f"{base_path}?{'&'.join(selected_params)}"


@st.composite
def api_key_strategy(draw: st.DrawFn) -> str:
    """Generate valid-looking API keys (UUID-like)."""
    segments = [
        draw(st.text(alphabet=string.hexdigits.lower(), min_size=8, max_size=8)),
        draw(st.text(alphabet=string.hexdigits.lower(), min_size=4, max_size=4)),
        draw(st.text(alphabet=string.hexdigits.lower(), min_size=4, max_size=4)),
        draw(st.text(alphabet=string.hexdigits.lower(), min_size=4, max_size=4)),
        draw(st.text(alphabet=string.hexdigits.lower(), min_size=12, max_size=12)),
    ]
    return "-".join(segments)


# =============================================================================
# Property Tests: Signature Generation
# =============================================================================


@pytest.mark.property
class TestSignatureProperties:
    """Property tests for signature generation invariants."""

    @given(valid_timestamp_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=50)
    def test_signature_always_base64_encoded(self, timestamp: int, method: str, path: str) -> None:
        """Signature is always valid base64.

        Property: For any valid inputs, output is valid base64 string.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"test_signature_bytes"

        signature = generate_signature(
            private_key=mock_key,
            timestamp=timestamp,
            method=method,
            path=path,
        )

        # Should not raise on decode
        decoded = base64.b64decode(signature)
        assert isinstance(decoded, bytes)
        assert len(decoded) > 0

    @given(valid_timestamp_strategy(), http_method_any_case_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_method_always_uppercased_in_message(
        self, timestamp: int, method: str, path: str
    ) -> None:
        """Method is always uppercased in signature message.

        Property: For any case of method input, message contains uppercase method.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=timestamp,
            method=method,
            path=path,
        )

        call_args = mock_key.sign.call_args
        message = call_args[0][0].decode("utf-8")

        # Message should contain uppercase method
        assert method.upper() in message
        # If method was not already uppercase, lowercase should not appear
        if method != method.upper():
            assert method not in message

    @given(valid_timestamp_strategy(), http_method_strategy(), api_path_with_query_strategy())
    @settings(max_examples=30)
    def test_path_preserved_exactly(self, timestamp: int, method: str, path: str) -> None:
        """Path is preserved exactly in signature message.

        Property: Path including query params appears unchanged in message.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=timestamp,
            method=method,
            path=path,
        )

        call_args = mock_key.sign.call_args
        message = call_args[0][0].decode("utf-8")

        # Path should appear exactly as provided
        assert path in message

    @given(valid_timestamp_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_message_format_timestamp_method_path(
        self, timestamp: int, method: str, path: str
    ) -> None:
        """Message format is exactly: timestamp + method + path.

        Property: No delimiters, spaces, or extra characters.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        generate_signature(
            private_key=mock_key,
            timestamp=timestamp,
            method=method,
            path=path,
        )

        call_args = mock_key.sign.call_args
        message = call_args[0][0].decode("utf-8")

        expected = f"{timestamp}{method.upper()}{path}"
        assert message == expected


# =============================================================================
# Property Tests: Header Generation
# =============================================================================


@pytest.mark.property
class TestHeaderProperties:
    """Property tests for header generation invariants."""

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_headers_always_contain_required_keys(
        self, api_key: str, method: str, path: str
    ) -> None:
        """Headers always contain all required keys.

        Property: Every header dict has ACCESS-KEY, TIMESTAMP, SIGNATURE, Content-Type.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        headers = auth.get_headers(method, path)

        required_keys = [
            "KALSHI-ACCESS-KEY",
            "KALSHI-ACCESS-TIMESTAMP",
            "KALSHI-ACCESS-SIGNATURE",
            "Content-Type",
        ]

        for key in required_keys:
            assert key in headers

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_access_key_matches_api_key(self, api_key: str, method: str, path: str) -> None:
        """KALSHI-ACCESS-KEY always matches provided api_key.

        Property: Header value equals constructor argument exactly.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        headers = auth.get_headers(method, path)

        assert headers["KALSHI-ACCESS-KEY"] == api_key

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_timestamp_is_valid_milliseconds(self, api_key: str, method: str, path: str) -> None:
        """Timestamp is valid milliseconds since epoch.

        Property: Timestamp is reasonable (between 2020 and now+1min).
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        before = int(time.time() * 1000)
        headers = auth.get_headers(method, path)
        after = int(time.time() * 1000)

        timestamp = int(headers["KALSHI-ACCESS-TIMESTAMP"])

        # Timestamp should be between before and after
        assert before <= timestamp <= after

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_timestamp_is_string_type(self, api_key: str, method: str, path: str) -> None:
        """Timestamp header value is string type.

        Property: Per Kalshi API spec, timestamp is string not int.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        headers = auth.get_headers(method, path)

        assert isinstance(headers["KALSHI-ACCESS-TIMESTAMP"], str)

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_signature_is_valid_base64(self, api_key: str, method: str, path: str) -> None:
        """Signature header is valid base64 string.

        Property: Signature can be decoded without error.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"test_signature_bytes"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        headers = auth.get_headers(method, path)

        signature = headers["KALSHI-ACCESS-SIGNATURE"]
        # Should not raise
        decoded = base64.b64decode(signature)
        assert len(decoded) > 0

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=30)
    def test_content_type_always_json(self, api_key: str, method: str, path: str) -> None:
        """Content-Type is always application/json.

        Property: Content-Type header is constant.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        headers = auth.get_headers(method, path)

        assert headers["Content-Type"] == "application/json"


# =============================================================================
# Property Tests: Token Expiry
# =============================================================================


@pytest.mark.property
class TestTokenExpiryProperties:
    """Property tests for token expiry logic."""

    @given(st.integers(min_value=1, max_value=1000000))
    @settings(max_examples=30)
    def test_token_expired_when_past_expiry(self, ms_past: int) -> None:
        """Token is expired when current time >= expiry.

        Property: For any positive ms past expiry, is_token_expired() == True.
        """
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        current = int(time.time() * 1000)
        auth.token = "some-token"
        auth.token_expiry = current - ms_past  # In the past

        assert auth.is_token_expired() is True

    @given(st.integers(min_value=1000, max_value=3600000))
    @settings(max_examples=30)
    def test_token_valid_when_before_expiry(self, ms_until: int) -> None:
        """Token is valid when current time < expiry.

        Property: For any time before expiry, is_token_expired() == False.
        """
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        current = int(time.time() * 1000)
        auth.token = "some-token"
        auth.token_expiry = current + ms_until  # In the future

        assert auth.is_token_expired() is False


# =============================================================================
# Property Tests: Initialization Invariants
# =============================================================================


@pytest.mark.property
class TestInitializationProperties:
    """Property tests for initialization invariants."""

    @given(api_key_strategy())
    @settings(max_examples=20)
    def test_api_key_stored_unchanged(self, api_key: str) -> None:
        """API key is stored exactly as provided.

        Property: auth.api_key == constructor argument.
        """
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        assert auth.api_key == api_key

    @given(st.text(min_size=5, max_size=100, alphabet=string.printable))
    @settings(max_examples=20)
    def test_private_key_path_stored_unchanged(self, path: str) -> None:
        """Private key path is stored exactly as provided.

        Property: auth.private_key_path == constructor argument.
        """
        # Filter out paths that might cause issues
        assume("\n" not in path and "\r" not in path and "\x00" not in path)

        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key="key",
            private_key_path=path,
            key_loader=lambda p: mock_key,
        )

        assert auth.private_key_path == path

    @given(api_key_strategy())
    @settings(max_examples=20)
    def test_initial_token_state_none(self, api_key: str) -> None:
        """Initial token state is always None.

        Property: New auth instance has token == None.
        """
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        assert auth.token is None
        assert auth.token_expiry is None

    @given(api_key_strategy())
    @settings(max_examples=20)
    def test_key_loader_receives_exact_path(self, api_key: str) -> None:
        """Key loader receives exact path from constructor.

        Property: Loader called with exact private_key_path argument.
        """
        mock_key = MagicMock()
        received_path = []

        def tracking_loader(path: str):
            received_path.append(path)
            return mock_key

        KalshiAuth(
            api_key=api_key,
            private_key_path="/custom/path/key.pem",
            key_loader=tracking_loader,
        )

        assert len(received_path) == 1
        assert received_path[0] == "/custom/path/key.pem"


# =============================================================================
# Property Tests: Idempotency
# =============================================================================


@pytest.mark.property
class TestIdempotencyProperties:
    """Property tests for idempotent operations."""

    @given(api_key_strategy(), http_method_strategy(), api_path_strategy())
    @settings(max_examples=20)
    def test_get_headers_does_not_mutate_state(self, api_key: str, method: str, path: str) -> None:
        """get_headers does not mutate internal state.

        Property: Calling get_headers multiple times doesn't change auth state.
        """
        mock_key = MagicMock()
        mock_key.sign.return_value = b"sig"

        auth = KalshiAuth(
            api_key=api_key,
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )

        # Record initial state
        initial_api_key = auth.api_key
        initial_path = auth.private_key_path
        initial_token = auth.token
        initial_expiry = auth.token_expiry

        # Call get_headers multiple times
        for _ in range(5):
            auth.get_headers(method, path)

        # State should be unchanged
        assert auth.api_key == initial_api_key
        assert auth.private_key_path == initial_path
        assert auth.token == initial_token
        assert auth.token_expiry == initial_expiry

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=10)
    def test_is_token_expired_idempotent(self, call_count: int) -> None:
        """is_token_expired is idempotent.

        Property: Multiple calls return same result (for fixed time).
        """
        mock_key = MagicMock()
        auth = KalshiAuth(
            api_key="key",
            private_key_path="/path",
            key_loader=lambda p: mock_key,
        )
        auth.token = "token"
        auth.token_expiry = int(time.time() * 1000) + 60000  # 60s future

        results = [auth.is_token_expired() for _ in range(call_count)]

        # All results should be the same
        assert all(r == results[0] for r in results)
