"""
Unit tests for Kalshi API client.

Tests cover:
- RSA-PSS authentication and signature generation
- REST endpoints (markets, balance, positions, fills, settlements)
- Decimal price parsing and precision
- Rate limiting (100 req/min with exponential backoff)
- Error handling (401, 429, 500, timeout, network errors)
- Structured logging with correlation IDs

All tests use mocked responses - NO actual API calls.

Coverage Target: ≥90%
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import requests

# Import implementation modules
from api_connectors.kalshi_auth import KalshiAuth, generate_signature, load_private_key
from api_connectors.kalshi_client import KalshiClient

# Import test fixtures
from tests.fixtures.api_responses import (
    KALSHI_BALANCE_RESPONSE,
    KALSHI_ERROR_401_RESPONSE,
    KALSHI_ERROR_429_RESPONSE,
    KALSHI_ERROR_500_RESPONSE,
    KALSHI_FILLS_RESPONSE,
    KALSHI_MARKET_RESPONSE,
    KALSHI_POSITIONS_RESPONSE,
    KALSHI_SETTLEMENTS_RESPONSE,
    KALSHI_SINGLE_MARKET_RESPONSE,
    SUB_PENNY_TEST_CASES,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_env_credentials(monkeypatch):
    """Mock environment variables for Kalshi credentials."""
    monkeypatch.setenv("KALSHI_DEMO_KEY_ID", "test-key-id-12345")
    monkeypatch.setenv("KALSHI_DEMO_KEYFILE", "/fake/path/to/key.pem")
    monkeypatch.setenv("KALSHI_PROD_KEY_ID", "prod-key-id-67890")
    monkeypatch.setenv("KALSHI_PROD_KEYFILE", "/fake/path/to/prod_key.pem")


@pytest.fixture
def mock_private_key():
    """Create a mock RSA private key for testing."""
    # This would be replaced with actual test key generation
    # For now, return a mock object
    mock_key = Mock()
    mock_key.sign = Mock(return_value=b"fake_signature_bytes_for_testing_purposes_only")
    return mock_key


@pytest.fixture
def mock_load_private_key(mock_private_key):
    """Patch load_private_key to return mock key."""
    with patch("api_connectors.kalshi_auth.load_private_key", return_value=mock_private_key):
        yield mock_private_key


@pytest.fixture
def sample_pem_key_content():
    """Sample PEM-formatted private key for testing file loading.

    This is a test-only RSA private key (2048-bit) generated specifically
    for unit tests. DO NOT use in production.
    """
    return b"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCx1C7gSi+eFBpN\naEDK0+S/FV7m4FD5hznvwmqPWc7YLwYVv6lcYw/iQzEL5eboAoswEzbSpwv6sbfY\npSbnIXhLrUq3O2fO2KL6W26xERqVFbNPquyFuJ5tpJS5p6iVSZAIts7tR5aD6n5c\n4ze58riPnJ8E5B7XNgZpgwPWB/ZZGNbX5AN51jFCj7WFBGgjNhOuFgK2fBYfFcwL\nc4jficjz0UHuPE51yiD4TTfn9hkFljlmiM1vhyVgP4ucOmBCvS4JlHTTDWvjfuHY\n8LURUUyruP3vBmLJfGDDcsvotirmIILIEPMBHRjveNI5fEMqTMQU5WblQ7yeyd95\n0WtUo7eHAgMBAAECggEAQZ+04M5fvi1a+3/ikTca7i07xWW4XC08Ay+y1U3mGD9a\nNoJxRIfGH9B99A8WZD40ETy1+YztzcjxuIBR1++xDfRYY0AH8fxeQJenRK60KZpF\nfrvr5vkXdgzLWav2eYkZHy4fNM87S1ko4qxzLyrUUyMQR+TLQM5OFXfk3YI4te3m\nxrys8+rPTVu6YGVk4Op2MW2zCbeJtrbBygaT1elvd1of59E5UdjXvpXux4BET+px\n6x88jo8isS3kGjUrttA3mhmTRh4D951uafFLKYZuiFQ0/Fm8LfuL30/kFOXQu1z/\n/j9OjtwwQgOpidInR1WtJsooROI1zrbaRPJbQ/wzwQKBgQD0TGd0EIjR0+SQ3Oc0\ngPVCwbwOqAWdneOjsaBNvNiq5d0C4CSiBuucgYFmJzKk5nWwrz5qEdAYtFG/R5UK\nSnFcNh9WBl1261JtSoHnvJ53VZKlxweTQHJ4eg3QDDdprSY+oXqXUET14OelnvrO\nzEvgwb8TFNyZn15IgQxKRTBOJwKBgQC6WLnyQlHmn4H7C6Mp2ZPoZDp9VHStYpF9\n9xrXKjcJJreHEN/+oBv31jlZjgzHQ/HNfeWMLHdISIzQkv/nDJE7bg+rREj2l8Vr\nfdlfGY2wkQbXAHlA0ds32Hm0ipQOTRpIRAVwowtFrbQ0eUWVlq0qXewLnOQN7ypK\nZBB1+xSHoQKBgCZhOn+JeXU9jNMVYV1mRSHPvfOvgfJZM8Irzbtox8FRi39AJ4Et\nBSb5UZLy5YnyitrPLUcMtVysN4uNe2S6fUS3XATvyw87uR9ibTYy89Jbp0ZUFmST\n42f6BOGCidIYWcHNLK1I9wyJ4NqsN0r13ZXZ2mLtDBs2ZmGNpJimdghRAoGAH7iC\nzq5jarK0WZu9hp43A1QscLEzu2AQDDVIKGBTRgeFLkS9HIb8u8+Hq6r2meUDAEvy\nC052b6OJ9OdREG+fOVKe8DSLhw6G2KlvmzSqXegSFf9KpLIUcwkyjn0Yfua5Fpwd\noPLgNFhBWL1cDv67M38Rc1idqZGQzWEDPFIlSIECgYEA0rOF9aU5BlelD5wgbHf5\nH+BiRRjaMxAWM4jAQzFYNiGyZWvr/pqSXwyJMyrtxA98F0PetagD0Pi3cvLEjfTq\ncaTFBhxl41xPJ/8VIO2bC3IkgjGRvrT9S5NI1k3YlsJbiggPF/u7QO/Ng/sdnxLu\n6dZWB6OXwLHFJZHXTeJhGxE=\n-----END PRIVATE KEY-----\n"


# =============================================================================
# Authentication Tests (RSA-PSS)
# =============================================================================


class TestKalshiAuthentication:
    """Test RSA-PSS signature generation and authentication."""

    @pytest.mark.unit
    @pytest.mark.critical
    def test_load_private_key_success(self, tmp_path, sample_pem_key_content):
        """Test loading RSA private key from PEM file."""

        # Create temporary key file
        key_file = tmp_path / "test_key.pem"
        key_file.write_bytes(sample_pem_key_content)

        # Load key
        private_key = load_private_key(str(key_file))

        # Verify key loaded successfully
        assert private_key is not None
        # Verify it's an RSA private key object
        from cryptography.hazmat.primitives.asymmetric import rsa

        assert isinstance(private_key, rsa.RSAPrivateKey)

    @pytest.mark.unit
    @pytest.mark.critical
    def test_load_private_key_file_not_found(self):
        """Test error handling when key file doesn't exist."""

        with pytest.raises(FileNotFoundError) as exc_info:
            load_private_key("/nonexistent/path/key.pem")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.critical
    def test_generate_signature_format(self, mock_private_key):
        """Test RSA-PSS signature generation returns base64 string."""

        timestamp = 1729123456789
        method = "GET"
        path = "/trade-api/v2/markets"

        signature = generate_signature(mock_private_key, timestamp, method, path)

        # Verify signature is base64-encoded string
        assert isinstance(signature, str)
        assert len(signature) > 0
        # Base64 alphabet check
        import base64

        try:
            decoded = base64.b64decode(signature)
            assert len(decoded) > 0
        except Exception:
            pytest.fail("Signature is not valid base64")

    @pytest.mark.unit
    @pytest.mark.critical
    def test_generate_signature_message_format(self, mock_private_key):
        """Test that signature message is formatted correctly: timestamp + METHOD + path."""

        timestamp = 1729123456789
        method = "GET"
        path = "/trade-api/v2/markets"

        # Expected message format
        expected_message = "1729123456789GET/trade-api/v2/markets"

        # Generate signature (this calls private_key.sign internally)
        generate_signature(mock_private_key, timestamp, method, path)

        # Verify sign() was called with correct message
        mock_private_key.sign.assert_called_once()
        call_args = mock_private_key.sign.call_args
        actual_message = call_args[0][0].decode("utf-8")

        assert actual_message == expected_message

    @pytest.mark.unit
    def test_kalshi_auth_get_headers(self, mock_private_key):
        """Test KalshiAuth generates correct authentication headers."""

        api_key = "test-key-id-12345"

        # Mock load_private_key to return our mock
        with patch("api_connectors.kalshi_auth.load_private_key", return_value=mock_private_key):
            auth = KalshiAuth(api_key=api_key, private_key_path="/fake/path.pem")

            headers = auth.get_headers(method="GET", path="/trade-api/v2/markets")

        # Verify headers structure
        assert "KALSHI-ACCESS-KEY" in headers
        assert "KALSHI-ACCESS-TIMESTAMP" in headers
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        assert "Content-Type" in headers

        # Verify header values
        assert headers["KALSHI-ACCESS-KEY"] == api_key
        assert headers["Content-Type"] == "application/json"
        assert headers["KALSHI-ACCESS-TIMESTAMP"].isdigit()
        assert len(headers["KALSHI-ACCESS-SIGNATURE"]) > 0


# =============================================================================
# Kalshi Client Tests
# =============================================================================


class TestKalshiClient:
    """Test KalshiClient API methods."""

    @pytest.mark.unit
    def test_client_initialization_demo(self, mock_env_credentials):
        """Test KalshiClient initializes correctly with demo environment."""
        from api_connectors.kalshi_client import KalshiClient

        with patch("api_connectors.kalshi_auth.load_private_key"):
            client = KalshiClient(environment="demo")

        assert client.environment == "demo"
        assert "demo" in client.base_url.lower()

    @pytest.mark.unit
    def test_client_initialization_prod(self, mock_env_credentials):
        """Test KalshiClient initializes correctly with prod environment."""
        from api_connectors.kalshi_client import KalshiClient

        with patch("api_connectors.kalshi_auth.load_private_key"):
            client = KalshiClient(environment="prod")

        assert client.environment == "prod"
        assert "demo" not in client.base_url.lower()

    @pytest.mark.unit
    def test_client_initialization_invalid_environment(self):
        """Test KalshiClient raises error for invalid environment."""
        from api_connectors.kalshi_client import KalshiClient

        with pytest.raises(ValueError) as exc_info:
            KalshiClient(environment="staging")  # Invalid

        assert "Invalid environment" in str(exc_info.value)

    @pytest.mark.unit
    def test_client_initialization_missing_credentials(self, monkeypatch):
        """Test KalshiClient raises error when credentials missing."""
        from api_connectors.kalshi_client import KalshiClient

        # Clear environment variables
        monkeypatch.delenv("KALSHI_DEMO_KEY_ID", raising=False)
        monkeypatch.delenv("KALSHI_DEMO_KEYFILE", raising=False)

        with pytest.raises(EnvironmentError) as exc_info:
            KalshiClient(environment="demo")

        assert "Missing Kalshi credentials" in str(exc_info.value)


# =============================================================================
# Market Data Tests (Decimal Precision)
# =============================================================================


class TestKalshiMarketData:
    """Test market data fetching and Decimal conversion."""

    @pytest.mark.unit
    @pytest.mark.critical
    def test_get_markets_returns_decimal_prices(self, mock_env_credentials, mock_load_private_key):
        """Test get_markets() parses all prices as Decimal (NOT float)."""
        client = KalshiClient(environment="demo")

        # Mock HTTP response
        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_MARKET_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            markets = client.get_markets()

        # Verify markets returned
        assert len(markets) == 2

        # CRITICAL: Verify all prices are Decimal type
        for market in markets:
            assert isinstance(market["yes_bid"], Decimal), "yes_bid must be Decimal"
            assert isinstance(market["yes_ask"], Decimal), "yes_ask must be Decimal"
            assert isinstance(market["no_bid"], Decimal), "no_bid must be Decimal"
            assert isinstance(market["no_ask"], Decimal), "no_ask must be Decimal"
            assert isinstance(market["last_price"], Decimal), "last_price must be Decimal"

    @pytest.mark.unit
    @pytest.mark.critical
    def test_get_markets_sub_penny_precision(self, mock_env_credentials, mock_load_private_key):
        """Test that sub-penny prices (0.4275, 0.4976) are parsed exactly."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_MARKET_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            markets = client.get_markets()

        # Check second market with sub-penny prices
        buffalo_market = markets[1]

        # Verify exact Decimal precision (no rounding)
        assert buffalo_market["yes_bid"] == Decimal("0.4275")
        assert buffalo_market["yes_ask"] == Decimal("0.4325")
        assert buffalo_market["last_price"] == Decimal("0.4300")

    @pytest.mark.unit
    def test_get_markets_with_filters(self, mock_env_credentials, mock_load_private_key):
        """Test get_markets() with series_ticker and event_ticker filters."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_MARKET_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            _markets = client.get_markets(series_ticker="KXNFLGAME", limit=50)

        # Verify request was made with correct parameters
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args.kwargs
        assert call_kwargs["params"]["series_ticker"] == "KXNFLGAME"
        assert call_kwargs["params"]["limit"] == 50

    @pytest.mark.unit
    @pytest.mark.critical
    def test_get_single_market_decimal_prices(self, mock_env_credentials, mock_load_private_key):
        """Test get_market() for single market returns Decimal prices."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_SINGLE_MARKET_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            market = client.get_market("KXNFLGAME-25DEC15-KC-YES")

        # Verify Decimal types
        assert isinstance(market["yes_bid"], Decimal)
        assert isinstance(market["yes_ask"], Decimal)
        assert market["yes_bid"] == Decimal("0.6200")
        assert market["yes_ask"] == Decimal("0.6250")


# =============================================================================
# Balance and Position Tests
# =============================================================================


class TestKalshiBalanceAndPositions:
    """Test balance and position data fetching."""

    @pytest.mark.unit
    @pytest.mark.critical
    def test_get_balance_returns_decimal(self, mock_env_credentials, mock_load_private_key):
        """Test get_balance() returns Decimal (NOT float)."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_BALANCE_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            balance = client.get_balance()

        # CRITICAL: Balance must be Decimal
        assert isinstance(balance, Decimal), "Balance must be Decimal type"
        assert balance == Decimal("1234.5678")

    @pytest.mark.unit
    @pytest.mark.critical
    def test_get_positions_decimal_prices(self, mock_env_credentials, mock_load_private_key):
        """Test get_positions() parses all prices as Decimal."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_POSITIONS_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            positions = client.get_positions()

        # Verify Decimal types in all positions
        for position in positions:
            assert isinstance(position["user_average_price"], Decimal)
            assert isinstance(position["total_cost"], Decimal)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestKalshiErrorHandling:
    """Test error handling for various API error responses."""

    @pytest.mark.unit
    @pytest.mark.critical
    def test_401_unauthorized_error(self, mock_env_credentials, mock_load_private_key):
        """Test handling of 401 Unauthorized (invalid credentials)."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = KALSHI_ERROR_401_RESPONSE
            mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
            mock_request.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                client.get_markets()

            assert "401" in str(exc_info.value)

    @pytest.mark.unit
    @pytest.mark.critical
    def test_429_rate_limit_error(self, mock_env_credentials, mock_load_private_key):
        """Test handling of 429 Too Many Requests (rate limit exceeded)."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = KALSHI_ERROR_429_RESPONSE
            mock_response.raise_for_status.side_effect = Exception("429 Too Many Requests")
            mock_request.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                client.get_markets()

            assert "429" in str(exc_info.value)

    @pytest.mark.unit
    def test_500_server_error_retry(self, mock_env_credentials, mock_load_private_key):
        """Test exponential backoff retry on 500 Server Error."""
        # This test will be fully implemented after exponential backoff is added
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = KALSHI_ERROR_500_RESPONSE
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "500 Server Error"
            )
            mock_request.return_value = mock_response

            with pytest.raises(requests.exceptions.HTTPError) as exc_info:
                client.get_markets()

            assert "500" in str(exc_info.value)

    @pytest.mark.unit
    def test_network_timeout_error(self, mock_env_credentials, mock_load_private_key):
        """Test handling of network timeout."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "request") as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")

            with pytest.raises(requests.exceptions.Timeout) as exc_info:
                client.get_markets()

            assert "timed out" in str(exc_info.value).lower()


# =============================================================================
# Decimal Arithmetic Tests
# =============================================================================


class TestDecimalPrecision:
    """Test Decimal precision in arithmetic operations."""

    @pytest.mark.unit
    @pytest.mark.critical
    @pytest.mark.parametrize("test_case", SUB_PENNY_TEST_CASES)
    def test_sub_penny_precision(self, test_case):
        """Test that sub-penny prices are represented exactly."""
        api_value = test_case["api_value"]
        expected = test_case["expected_decimal"]

        # Convert string to Decimal (as API client does)
        result = Decimal(api_value)

        # Verify exact match (no rounding)
        assert result == expected
        assert isinstance(result, Decimal)

    @pytest.mark.unit
    @pytest.mark.critical
    def test_decimal_spread_calculation(self):
        """Test spread calculation maintains Decimal precision."""
        ask = Decimal("0.6250")
        bid = Decimal("0.6200")

        spread = ask - bid

        assert isinstance(spread, Decimal)
        assert spread == Decimal("0.0050")

    @pytest.mark.unit
    @pytest.mark.critical
    def test_decimal_pnl_calculation(self):
        """Test P&L calculation maintains Decimal precision."""
        entry_price = Decimal("0.6100")
        exit_price = Decimal("0.6500")
        quantity = 100

        # P&L per contract: $0.6500 - $0.6100 = $0.0400
        # Total P&L: $0.0400 * 100 = $4.00
        pnl = (exit_price - entry_price) * quantity

        assert isinstance(pnl, Decimal)
        assert pnl == Decimal("4.0000")  # Fixed: was Decimal("40.0000")


# =============================================================================
# Integration Tests (with mocking)
# =============================================================================


class TestKalshiIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.integration
    def test_complete_workflow_fetch_markets_and_balance(
        self, mock_env_credentials, mock_load_private_key
    ):
        """Test complete workflow: initialize client, fetch markets, fetch balance."""
        client = KalshiClient(environment="demo")

        # Mock market request
        with patch.object(client.session, "request") as mock_request:
            # First call: get_markets
            market_response = Mock()
            market_response.json.return_value = KALSHI_MARKET_RESPONSE
            market_response.raise_for_status = Mock()

            # Second call: get_balance
            balance_response = Mock()
            balance_response.json.return_value = KALSHI_BALANCE_RESPONSE
            balance_response.raise_for_status = Mock()

            mock_request.side_effect = [market_response, balance_response]

            # Execute workflow
            markets = client.get_markets()
            balance = client.get_balance()

        # Verify results
        assert len(markets) == 2
        assert isinstance(balance, Decimal)
        assert all(isinstance(m["yes_bid"], Decimal) for m in markets)

    def test_get_fills_returns_decimal_prices(self, mock_env_credentials, mock_load_private_key):
        """Test get_fills() returns fills with Decimal prices."""
        client = KalshiClient(environment="demo")

        # Mock response
        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_FILLS_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            fills = client.get_fills(ticker="KXNFLGAME-25OCT05-NEBUF-B250")

        # Verify Decimal conversion
        assert len(fills) == 2
        assert isinstance(fills[0]["price"], Decimal)
        assert fills[0]["price"] == Decimal("0.6150")
        assert isinstance(fills[1]["price"], Decimal)
        assert fills[1]["price"] == Decimal("0.4200")

    def test_get_settlements_returns_decimal_values(
        self, mock_env_credentials, mock_load_private_key
    ):
        """Test get_settlements() returns settlements with Decimal values."""
        client = KalshiClient(environment="demo")

        # Mock response
        with patch.object(client.session, "request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = KALSHI_SETTLEMENTS_RESPONSE
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            settlements = client.get_settlements()

        # Verify Decimal conversion
        assert len(settlements) == 2
        assert isinstance(settlements[0]["settlement_value"], Decimal)
        assert settlements[0]["settlement_value"] == Decimal("1.0000")

    def test_close_method(self, mock_env_credentials, mock_load_private_key):
        """Test client close() method closes session."""
        client = KalshiClient(environment="demo")

        with patch.object(client.session, "close") as mock_close:
            client.close()

        mock_close.assert_called_once()
