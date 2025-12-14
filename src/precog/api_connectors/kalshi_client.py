"""
Complete Kalshi API client with RSA-PSS authentication.

This module provides a high-level interface to Kalshi's prediction market API.
All price values are returned as Python Decimal types for precision.

Key Features:
- RSA-PSS authentication
- Automatic token refresh (tokens expire after 30 minutes)
- Rate limiting protection
- Decimal price handling (NEVER use float for money!)
- Comprehensive error handling
- Logging for debugging

Educational Notes:
------------------
API Design Pattern: This follows the "client" pattern:
1. Create client object (handles auth, config)
2. Call methods (get_markets, place_order, etc.)
3. Client handles all HTTP details, retries, errors
4. You just work with clean Python objects

This is much easier than making raw requests.get() calls everywhere!

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related Requirements:
    - REQ-API-001: Kalshi API Integration
    - REQ-API-002: RSA-PSS Authentication
    - REQ-API-005: API Rate Limit Management
    - REQ-API-006: API Error Handling
    - REQ-SYS-003: Decimal Precision for Prices
"""

import logging
import os
import time
from decimal import Decimal
from typing import Any, ClassVar, cast
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from precog.config.environment import MarketMode, get_market_mode

from .kalshi_auth import KalshiAuth
from .rate_limiter import RateLimiter
from .types import (
    ProcessedFillData,
    ProcessedMarketData,
    ProcessedPositionData,
    ProcessedSettlementData,
)

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


class KalshiDemoUnavailableError(Exception):
    """
    Raised when Kalshi DEMO environment portfolio endpoints are unavailable.

    The Kalshi DEMO API occasionally experiences issues with its 'query-exchange'
    service, causing 500 errors on portfolio-related endpoints (/portfolio/balance,
    /portfolio/positions) while other endpoints (/markets, /orders) work fine.

    This exception allows callers to handle DEMO unavailability gracefully,
    for example by:
    - Falling back to cached values
    - Returning placeholder data for testing
    - Logging and continuing with other operations

    Educational Note:
        DEMO and PROD are separate environments with separate credentials.
        DEMO issues do NOT affect PROD trading capability.

    Reference: GitHub Issue tracking Kalshi DEMO instability
    """


class KalshiClient:
    """
    High-level Kalshi API client.

    Manages:
    - Authentication and token lifecycle
    - API requests with retry logic
    - Response parsing and Decimal conversion
    - Error handling
    - Resource cleanup (session close)

    Usage:
        >>> # Initialize
        >>> client = KalshiClient(environment="demo")
        >>>
        >>> # Get markets
        >>> markets = client.get_markets(series_ticker="KXNFLGAME")
        >>>
        >>> # All prices are Decimal objects
        >>> for market in markets:
        ...     print(f"Yes ask: ${market['yes_ask']}")  # Decimal('0.6500')
        >>>
        >>> # Cleanup when done
        >>> client.close()

    Testing Usage (Dependency Injection):
        >>> mock_auth = MagicMock()
        >>> mock_session = MagicMock()
        >>> mock_limiter = MagicMock()
        >>> client = KalshiClient(
        ...     environment="demo",
        ...     auth=mock_auth,
        ...     session=mock_session,
        ...     rate_limiter=mock_limiter
        ... )

    Educational Note:
        Always develop against "demo" first!
        Demo environment:
        - Uses fake money
        - Identical API to production
        - Safe place to test and learn

        Only switch to "prod" when you're confident your code works.

        This class uses dependency injection for auth, session, and rate_limiter,
        making it fully testable without actual API credentials or network access.
        See Pattern 12 (Dependency Injection) in DEVELOPMENT_PATTERNS.

    Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
    """

    # API base URLs
    BASE_URLS: ClassVar[dict[str, str]] = {
        "demo": "https://demo-api.kalshi.co/trade-api/v2",
        "prod": "https://api.elections.kalshi.com/trade-api/v2",
    }

    def __init__(
        self,
        environment: str | None = None,
        auth: KalshiAuth | None = None,
        session: requests.Session | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        """
        Initialize Kalshi client.

        Args:
            environment: "demo" or "prod" (DEPRECATED: use KALSHI_MODE env var).
                         If None (default), reads from KALSHI_MODE environment variable.
                         Explicit value overrides KALSHI_MODE for backwards compatibility.
            auth: Optional KalshiAuth instance. If not provided, creates one
                  from environment variables. Useful for testing to inject mocks.
            session: Optional requests.Session. If not provided, creates new one.
                     Useful for testing to inject mock sessions.
            rate_limiter: Optional RateLimiter. If not provided, creates one with
                          100 req/min limit. Useful for testing to inject mocks.

        Raises:
            ValueError: If environment invalid
            EnvironmentError: If required env vars missing (when auth not provided)

        Example:
            >>> # Preferred: use KALSHI_MODE environment variable
            >>> # export KALSHI_MODE=demo
            >>> client = KalshiClient()  # Reads from KALSHI_MODE
            >>>
            >>> # Legacy: explicit environment parameter (deprecated)
            >>> client = KalshiClient(environment="demo")

        Testing Example:
            >>> mock_auth = MagicMock()
            >>> client = KalshiClient(
            ...     environment="demo",
            ...     auth=mock_auth,
            ...     session=MagicMock(),
            ...     rate_limiter=MagicMock()
            ... )

        Educational Note:
            The optional auth/session/rate_limiter parameters implement
            Dependency Injection (DI):
            - Production: Parameters are None, so we create real instances
            - Testing: Inject mocks, avoiding real credentials/network
            This makes the class testable without environment setup.

            Environment Resolution (Two-Axis Model):
            - If `environment` parameter provided: Use it directly (backwards compatible)
            - If `environment` is None: Read from KALSHI_MODE env var
            - KALSHI_MODE values: "demo" (default) or "live"

            See: docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
        """
        # Resolve environment from parameter or KALSHI_MODE env var
        if environment is not None:
            # Explicit parameter (backwards compatibility)
            if environment not in ["demo", "prod"]:
                raise ValueError(f"Invalid environment: {environment}. Must be 'demo' or 'prod'")
            resolved_env = environment
        else:
            # Use centralized market mode (two-axis model)
            market_mode = get_market_mode("kalshi")
            # Map MarketMode to API environment
            resolved_env = "demo" if market_mode == MarketMode.DEMO else "prod"
            logger.debug(f"Resolved Kalshi environment from KALSHI_MODE: {resolved_env}")

        self.environment = resolved_env
        self.base_url = self.BASE_URLS[resolved_env]

        # Use injected dependencies or create defaults
        if auth is not None:
            self.auth = auth
        else:
            # Load credentials from environment using DATABASE_ENVIRONMENT_STRATEGY naming
            # See: docs/guides/DATABASE_ENVIRONMENT_STRATEGY_V1.0.md
            #
            # Credential prefix mapping:
            # - "prod" environment -> PROD_KALSHI_* (production Kalshi API)
            # - "demo" environment -> {PRECOG_ENV}_KALSHI_* (demo Kalshi API)
            #   - PRECOG_ENV=dev -> DEV_KALSHI_*
            #   - PRECOG_ENV=test -> TEST_KALSHI_*
            #   - PRECOG_ENV=staging -> STAGING_KALSHI_*
            if environment == "prod":
                cred_prefix = "PROD"
            else:
                # Demo environment: use PRECOG_ENV, default to DEV
                precog_env = os.getenv("PRECOG_ENV", "dev").upper()
                # Map to valid credential prefixes
                valid_prefixes = {"DEV", "TEST", "STAGING"}
                cred_prefix = precog_env if precog_env in valid_prefixes else "DEV"

            key_env_var = f"{cred_prefix}_KALSHI_API_KEY"
            keyfile_env_var = f"{cred_prefix}_KALSHI_PRIVATE_KEY_PATH"

            api_key = os.getenv(key_env_var)
            keyfile_path = os.getenv(keyfile_env_var)

            if not api_key or not keyfile_path:
                raise OSError(
                    f"Missing Kalshi credentials. Please set {key_env_var} and "
                    f"{keyfile_env_var} in .env file.\n"
                    f"Current PRECOG_ENV={os.getenv('PRECOG_ENV', 'dev')}, credential prefix={cred_prefix}\n"
                    f"See docs/guides/CONFIGURATION_GUIDE_V3.1.md for setup instructions."
                )

            # Initialize authentication
            self.auth = KalshiAuth(api_key, keyfile_path)

        # Session for connection pooling (more efficient)
        self.session = session if session is not None else requests.Session()

        # Rate limiting (100 requests per minute for Kalshi)
        self.rate_limiter = (
            rate_limiter if rate_limiter is not None else RateLimiter(requests_per_minute=100)
        )

        logger.info(
            f"KalshiClient initialized for {environment} environment",
            extra={"environment": environment, "base_url": self.base_url},
        )

    def close(self) -> None:
        """
        Close the HTTP session and release resources.

        Should be called when the client is no longer needed to properly
        clean up connection pools and prevent resource leaks.

        Usage:
            >>> client = KalshiClient(environment="demo")
            >>> try:
            ...     markets = client.get_markets()
            ... finally:
            ...     client.close()

        Educational Note:
            Resource cleanup is important for long-running applications.
            The requests.Session maintains a connection pool that should
            be explicitly closed when no longer needed.

        Reference: Pattern 11 (Resource Cleanup) - DEVELOPMENT_PATTERNS
        """
        if hasattr(self, "session") and self.session:
            self.session.close()
            logger.debug("KalshiClient session closed")

    def _make_request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_data: dict | None = None,
        max_retries: int = 3,
    ) -> dict:
        """
        Make authenticated API request with exponential backoff retry logic.

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API endpoint path (without base URL)
            params: Query parameters (for GET requests)
            json_data: JSON body (for POST requests)
            max_retries: Maximum retry attempts for 5xx errors (default 3)

        Returns:
            Response data as dictionary

        Raises:
            requests.HTTPError: If request fails after all retries
            requests.Timeout: If request times out
            requests.RequestException: For other request failures

        Educational Notes:
            Exponential Backoff:
            - Retry 1: Wait 1 second (2^0)
            - Retry 2: Wait 2 seconds (2^1)
            - Retry 3: Wait 4 seconds (2^2)

            Why Exponential Backoff?
            - Gives server time to recover from transient issues
            - Reduces load on server during outages
            - Each retry waits longer, increasing chance of success

            5xx Errors (Server Errors):
            - 500 Internal Server Error
            - 502 Bad Gateway
            - 503 Service Unavailable
            - 504 Gateway Timeout
            These are transient - server might recover, so we retry.

            4xx Errors (Client Errors):
            - 400 Bad Request
            - 401 Unauthorized
            - 403 Forbidden
            - 404 Not Found
            These won't fix themselves - retrying won't help, so we don't retry.

        Reference: ADR-050 (Exponential Backoff Strategy)
        Related: REQ-API-006 (API Error Handling)
        """
        url = f"{self.base_url}{path}"

        # Extract full path for signature (must include /trade-api/v2 prefix)
        # The signature is computed over the full path, not just the endpoint path
        # Example: /trade-api/v2/portfolio/balance (not just /portfolio/balance)
        full_path = urlparse(url).path

        # Retry loop with exponential backoff
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                # Get fresh authentication headers for each attempt
                # CRITICAL: Must pass full path including /trade-api/v2 for correct signature
                headers = self.auth.get_headers(method=method, path=full_path)

                # Log request (without sensitive headers)
                if attempt == 0:
                    logger.debug(
                        f"API Request: {method} {path}",
                        extra={
                            "method": method,
                            "path": path,
                            "params": params,
                            "has_json_data": json_data is not None,
                        },
                    )
                else:
                    logger.info(
                        f"API Retry {attempt}/{max_retries}: {method} {path}",
                        extra={
                            "method": method,
                            "path": path,
                            "attempt": attempt,
                            "max_retries": max_retries,
                        },
                    )

                # Rate limiting: Wait if needed to comply with API limits
                self.rate_limiter.wait_if_needed()

                # Make request
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                    timeout=30,  # 30 second timeout (ADR-050)
                )

                # Raise exception if request failed
                response.raise_for_status()

                # Log success
                logger.debug(
                    f"API Response: {response.status_code}",
                    extra={"status_code": response.status_code, "path": path, "attempt": attempt},
                )

                return cast("dict[Any, Any]", response.json())

            except requests.exceptions.Timeout:
                logger.error(
                    f"Request timeout for {path} (attempt {attempt + 1}/{max_retries + 1})",
                    extra={"path": path, "attempt": attempt},
                )
                # Don't retry on timeout - let caller decide
                raise

            except requests.exceptions.HTTPError:
                status_code = response.status_code

                # Handle rate limit errors (429)
                if status_code == 429:
                    retry_after_str = response.headers.get("Retry-After")
                    retry_after_int: int | None = None
                    if retry_after_str:
                        retry_after_int = int(retry_after_str)

                    logger.warning(
                        f"Rate limit (429) exceeded for {path}",
                        extra={"path": path, "retry_after": retry_after_int},
                    )

                    self.rate_limiter.handle_rate_limit_error(retry_after=retry_after_int)
                    # Don't retry automatically - let caller decide
                    raise

                # Retry on 5xx errors (server errors)
                if 500 <= status_code < 600 and attempt < max_retries:
                    # Calculate exponential backoff delay: 1s, 2s, 4s
                    delay = 2**attempt

                    logger.warning(
                        f"Server error {status_code} for {path}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})",
                        extra={
                            "status_code": status_code,
                            "path": path,
                            "attempt": attempt,
                            "delay_seconds": delay,
                        },
                    )

                    time.sleep(delay)
                    continue  # Retry

                # Don't retry on 4xx errors (client errors) or if max retries reached
                logger.error(
                    f"HTTP error {status_code} for {path}",
                    extra={
                        "status_code": status_code,
                        "path": path,
                        "response_body": response.text,
                        "attempt": attempt,
                    },
                )
                raise

            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Request failed for {path}: {e}",
                    extra={"path": path, "error": str(e), "attempt": attempt},
                )
                raise

        # Should never reach here, but just in case
        raise requests.exceptions.RetryError(f"Max retries ({max_retries}) exceeded for {path}")

    def _convert_prices_to_decimal(self, data: dict) -> None:
        """
        Convert all price fields in dictionary from string to Decimal.

        Modifies data in-place. Parses Kalshi's sub-penny price fields with 4 decimal
        precision. Kalshi provides dual format for backward compatibility:
        - Legacy: yes_bid (integer cents: 0, 100)
        - Sub-penny: yes_bid_dollars (string: "0.0000", "1.0000")

        We parse the *_dollars/*_fixed fields for sub-penny precision.

        Args:
            data: Dictionary potentially containing price fields

        Educational Note:
            Kalshi API Sub-Penny Pricing (Nov 2025):
            - Market endpoints: Use *_dollars suffix (yes_bid_dollars: "0.4275")
            - Fill endpoints: Use *_fixed suffix (yes_price_fixed: "0.9600")
            - Portfolio endpoints: Use integer cents (balance: 235084)

            We MUST use *_dollars/*_fixed fields for 4 decimal precision.
            Float would cause rounding errors (0.04 + 0.96 = 1.0000000000000002).

        Reference:
            - docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md
            - https://docs.kalshi.com/getting_started/subpenny_pricing
        Related: REQ-SYS-003 (Decimal Precision for Prices)
        """
        price_fields = [
            # Market price fields (sub-penny format: *_dollars suffix)
            "yes_bid_dollars",
            "yes_ask_dollars",
            "no_bid_dollars",
            "no_ask_dollars",
            "last_price_dollars",
            "previous_price_dollars",
            "previous_yes_bid_dollars",
            "previous_yes_ask_dollars",
            # Fill price fields (sub-penny format: *_fixed suffix)
            "yes_price_fixed",
            "no_price_fixed",
            # Other market fields with *_dollars suffix
            "liquidity_dollars",
            "notional_value_dollars",
            # Position/portfolio fields (various formats)
            "user_average_price",
            "realized_pnl",
            "total_cost",
            "fees_paid",
            "settlement_value",
            "revenue",
            "total_fees",
            "balance",  # Integer cents (no _dollars variant)
        ]

        for field in price_fields:
            if field in data and data[field] is not None:
                try:
                    # Convert string to Decimal
                    # Use str() to ensure we're converting from string, not float
                    data[field] = Decimal(str(data[field]))
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Failed to convert {field} to Decimal: {data[field]}",
                        extra={"field": field, "value": data[field], "error": str(e)},
                    )

    def get_markets(
        self,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> list[ProcessedMarketData]:
        """
        Get list of markets with price data.

        Args:
            series_ticker: Filter by series (e.g., "KXNFLGAME")
            event_ticker: Filter by event (e.g., "KXNFLGAME-25OCT05-NEBUF")
            limit: Max markets to return (default 100, max 200)
            cursor: Pagination cursor for next page

        Returns:
            List of market dictionaries with Decimal prices

        Example:
            >>> client = KalshiClient("demo")
            >>> markets = client.get_markets(series_ticker="KXNFLGAME")
            >>> for market in markets:
            ...     print(f"{market['ticker']}: ${market['yes_ask']}")

        Educational Notes:
            Pagination: Kalshi limits responses to 200 markets max.
            If more exist, response includes a 'cursor'.
            Pass that cursor to next call to get next page.

            This is like "turning pages" in search results:
            Page 1: limit=100, cursor=None -> returns markets 1-100
            Page 2: limit=100, cursor="abc123" -> returns markets 101-200
            Page 3: limit=100, cursor="def456" -> returns markets 201-300

            Keep calling until response has no cursor (you're done).

        Reference: REQ-API-001 (Kalshi API Integration)
        Related: ADR-048 (Decimal-First Response Parsing)
        """
        params: dict[str, Any] = {"limit": limit}

        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if cursor:
            params["cursor"] = cursor

        response = self._make_request("GET", "/markets", params=params)

        markets = response.get("markets", [])

        # Convert all prices to Decimal (CRITICAL for precision!)
        for market in markets:
            self._convert_prices_to_decimal(market)

        logger.info(
            f"Fetched {len(markets)} markets",
            extra={
                "count": len(markets),
                "series_ticker": series_ticker,
                "has_more": "cursor" in response,
            },
        )

        return cast("list[ProcessedMarketData]", markets)

    def get_market(self, ticker: str) -> ProcessedMarketData:
        """
        Get details for single market.

        Args:
            ticker: Market ticker (e.g., "KXNFLGAME-25OCT05-NEBUF-B250")

        Returns:
            Market dictionary with Decimal prices

        Example:
            >>> client = KalshiClient("demo")
            >>> market = client.get_market("KXNFLGAME-25OCT05-NEBUF-B250")
            >>> print(f"Yes ask: ${market['yes_ask']}")
            Yes ask: $0.6500

        Reference: REQ-API-001 (Kalshi API Integration)
        """
        response = self._make_request("GET", f"/markets/{ticker}")
        market = response.get("market", {})

        # Convert prices to Decimal
        self._convert_prices_to_decimal(market)

        logger.info(f"Fetched market: {ticker}", extra={"ticker": ticker})

        return cast("ProcessedMarketData", market)

    def get_balance(self, graceful_demo_fallback: bool = False) -> Decimal | None:
        """
        Fetch account cash balance in dollars.

        Args:
            graceful_demo_fallback: If True and running in DEMO environment,
                return None instead of raising on 500 errors. Useful for testing
                when DEMO API has issues. Default False (raises on error).

        Returns:
            Account cash balance as Decimal (in dollars), or None if
            graceful_demo_fallback is True and DEMO API is unavailable.

        Raises:
            requests.HTTPError: If API request fails (unless graceful_demo_fallback)
            KalshiDemoUnavailableError: If DEMO API unavailable and not graceful

        Example:
            >>> client = KalshiClient("demo")
            >>> balance = client.get_balance()
            >>> print(f"Account balance: ${balance}")
            Account balance: $659.02
            >>>
            >>> # Graceful fallback for testing
            >>> balance = client.get_balance(graceful_demo_fallback=True)
            >>> if balance is None:
            ...     print("DEMO API unavailable, using cached value")

        Educational Note:
            The Kalshi API returns balance in CENTS (integer).
            We convert to dollars by dividing by 100.
            Demo environment starts with fake balance (usually $10,000).
            Production environment shows your real account balance.

            The DEMO environment occasionally has issues with its 'query-exchange'
            service. Use graceful_demo_fallback=True to handle this gracefully.

        Reference: REQ-CLI-002 (Balance Fetch Command)
        Related: REQ-SYS-003 (Decimal Precision)
        """
        try:
            response = self._make_request("GET", "/portfolio/balance")
        except requests.HTTPError as e:
            if (
                self.environment == "demo"
                and e.response is not None
                and e.response.status_code == 500
            ):
                if graceful_demo_fallback:
                    logger.warning(
                        "DEMO API /portfolio/balance unavailable (500 error), returning None",
                        extra={"environment": self.environment},
                    )
                    return None
                raise KalshiDemoUnavailableError(
                    "Kalshi DEMO API portfolio endpoints are currently unavailable. "
                    "Use graceful_demo_fallback=True to handle gracefully."
                ) from e
            raise

        # Parse balance as Decimal - API returns cents, convert to dollars
        balance_cents = Decimal(str(response.get("balance", "0")))
        balance_dollars = balance_cents / Decimal("100")

        logger.info(
            f"Fetched balance: ${balance_dollars:.2f}",
            extra={"balance_cents": str(balance_cents), "balance_dollars": str(balance_dollars)},
        )

        return balance_dollars

    def get_portfolio_value(
        self, graceful_demo_fallback: bool = False
    ) -> dict[str, Decimal] | None:
        """
        Fetch complete portfolio value including cash balance and positions.

        Args:
            graceful_demo_fallback: If True and running in DEMO environment,
                return None instead of raising on 500 errors.

        Returns:
            Dictionary with 'balance' (cash) and 'portfolio_value' (total) in dollars,
            or None if graceful_demo_fallback is True and DEMO API is unavailable.

        Raises:
            requests.HTTPError: If API request fails (unless graceful_demo_fallback)
            KalshiDemoUnavailableError: If DEMO API unavailable and not graceful

        Example:
            >>> client = KalshiClient("prod")
            >>> portfolio = client.get_portfolio_value()
            >>> print(f"Cash: ${portfolio['balance']}, Total: ${portfolio['portfolio_value']}")
            Cash: $659.02, Total: $1727.81

        Educational Note:
            - balance: Available cash (not tied up in positions)
            - portfolio_value: Total value including open positions
            Both values are returned by Kalshi in cents, converted to dollars here.

        Reference: REQ-CLI-002 (Balance Fetch Command)
        """
        try:
            response = self._make_request("GET", "/portfolio/balance")
        except requests.HTTPError as e:
            if (
                self.environment == "demo"
                and e.response is not None
                and e.response.status_code == 500
            ):
                if graceful_demo_fallback:
                    logger.warning(
                        "DEMO API /portfolio/balance unavailable (500 error), returning None",
                        extra={"environment": self.environment},
                    )
                    return None
                raise KalshiDemoUnavailableError(
                    "Kalshi DEMO API portfolio endpoints are currently unavailable. "
                    "Use graceful_demo_fallback=True to handle gracefully."
                ) from e
            raise

        # API returns cents, convert to dollars
        balance_cents = Decimal(str(response.get("balance", "0")))
        portfolio_cents = Decimal(str(response.get("portfolio_value", "0")))

        result = {
            "balance": balance_cents / Decimal("100"),
            "portfolio_value": portfolio_cents / Decimal("100"),
        }

        logger.info(
            f"Fetched portfolio: cash=${result['balance']:.2f}, total=${result['portfolio_value']:.2f}",
            extra={
                "balance": str(result["balance"]),
                "portfolio_value": str(result["portfolio_value"]),
            },
        )

        return result

    def get_positions(
        self,
        status: str | None = None,
        ticker: str | None = None,
        graceful_demo_fallback: bool = False,
    ) -> list[ProcessedPositionData] | None:
        """
        Get current positions.

        Args:
            status: Filter by status ("open" or "closed")
            ticker: Filter by market ticker
            graceful_demo_fallback: If True and running in DEMO environment,
                return None instead of raising on 500 errors.

        Returns:
            List of position dictionaries with Decimal prices, or None if
            graceful_demo_fallback is True and DEMO API is unavailable.

        Raises:
            requests.HTTPError: If API request fails (unless graceful_demo_fallback)
            KalshiDemoUnavailableError: If DEMO API unavailable and not graceful

        Example:
            >>> client = KalshiClient("demo")
            >>> positions = client.get_positions(status="open")
            >>> for pos in positions:
            ...     print(f"{pos['ticker']}: {pos['position']} contracts @ ${pos['user_average_price']}")

        Reference: REQ-CLI-003 (Positions Fetch Command)
        """
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if ticker:
            params["ticker"] = ticker

        try:
            response = self._make_request("GET", "/portfolio/positions", params=params)
        except requests.HTTPError as e:
            if (
                self.environment == "demo"
                and e.response is not None
                and e.response.status_code == 500
            ):
                if graceful_demo_fallback:
                    logger.warning(
                        "DEMO API /portfolio/positions unavailable (500 error), returning None",
                        extra={"environment": self.environment},
                    )
                    return None
                raise KalshiDemoUnavailableError(
                    "Kalshi DEMO API portfolio endpoints are currently unavailable. "
                    "Use graceful_demo_fallback=True to handle gracefully."
                ) from e
            raise

        positions = response.get("positions", [])

        # Convert prices to Decimal
        for position in positions:
            self._convert_prices_to_decimal(position)

        logger.info(
            f"Fetched {len(positions)} positions", extra={"count": len(positions), "status": status}
        )

        return cast("list[ProcessedPositionData]", positions)

    def get_fills(
        self,
        ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> list[ProcessedFillData]:
        """
        Get trade fills (executed orders).

        Args:
            ticker: Filter by market ticker
            min_ts: Minimum timestamp (Unix milliseconds)
            max_ts: Maximum timestamp (Unix milliseconds)
            limit: Max fills to return (default 100)
            cursor: Pagination cursor

        Returns:
            List of fill dictionaries with Decimal prices

        Example:
            >>> client = KalshiClient("demo")
            >>> fills = client.get_fills(ticker="KXNFLGAME-25OCT05-NEBUF-B250")
            >>> for fill in fills:
            ...     print(f"Filled {fill['count']} @ ${fill['price']}")

        Reference: REQ-CLI-004 (Fills Fetch Command)
        """
        params: dict[str, Any] = {"limit": limit}

        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        if cursor:
            params["cursor"] = cursor

        response = self._make_request("GET", "/portfolio/fills", params=params)
        fills = response.get("fills", [])

        # Convert prices to Decimal
        for fill in fills:
            self._convert_prices_to_decimal(fill)

        logger.info(f"Fetched {len(fills)} fills", extra={"count": len(fills)})

        return cast("list[ProcessedFillData]", fills)

    def get_settlements(
        self, ticker: str | None = None, limit: int = 100, cursor: str | None = None
    ) -> list[ProcessedSettlementData]:
        """
        Get market settlements.

        Args:
            ticker: Filter by market ticker
            limit: Max settlements to return (default 100)
            cursor: Pagination cursor

        Returns:
            List of settlement dictionaries with Decimal values

        Example:
            >>> client = KalshiClient("demo")
            >>> settlements = client.get_settlements()
            >>> for settlement in settlements:
            ...     print(f"{settlement['ticker']}: {settlement['market_result']}")

        Reference: REQ-CLI-005 (Settlements Fetch Command)
        """
        params: dict[str, Any] = {"limit": limit}

        if ticker:
            params["ticker"] = ticker
        if cursor:
            params["cursor"] = cursor

        response = self._make_request("GET", "/portfolio/settlements", params=params)
        settlements = response.get("settlements", [])

        # Convert values to Decimal
        for settlement in settlements:
            self._convert_prices_to_decimal(settlement)

        logger.info(f"Fetched {len(settlements)} settlements", extra={"count": len(settlements)})

        return cast("list[ProcessedSettlementData]", settlements)
