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


class KalshiClient:
    """
    High-level Kalshi API client.

    Manages:
    - Authentication and token lifecycle
    - API requests with retry logic
    - Response parsing and Decimal conversion
    - Error handling

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

    Educational Note:
        Always develop against "demo" first!
        Demo environment:
        - Uses fake money
        - Identical API to production
        - Safe place to test and learn

        Only switch to "prod" when you're confident your code works.

    Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
    """

    # API base URLs
    BASE_URLS: ClassVar[dict[str, str]] = {
        "demo": "https://demo-api.kalshi.co/trade-api/v2",
        "prod": "https://api.elections.kalshi.com/trade-api/v2",
    }

    def __init__(self, environment: str = "demo"):
        """
        Initialize Kalshi client.

        Args:
            environment: "demo" or "prod"

        Raises:
            ValueError: If environment invalid
            EnvironmentError: If required env vars missing

        Example:
            >>> client = KalshiClient(environment="demo")
        """
        if environment not in ["demo", "prod"]:
            raise ValueError(f"Invalid environment: {environment}. Must be 'demo' or 'prod'")

        self.environment = environment
        self.base_url = self.BASE_URLS[environment]

        # Load credentials from environment
        key_env_var = f"KALSHI_{environment.upper()}_KEY_ID"
        keyfile_env_var = f"KALSHI_{environment.upper()}_KEYFILE"

        api_key = os.getenv(key_env_var)
        keyfile_path = os.getenv(keyfile_env_var)

        if not api_key or not keyfile_path:
            raise OSError(
                f"Missing Kalshi credentials. Please set {key_env_var} and "
                f"{keyfile_env_var} in .env file.\n"
                f"See docs/guides/CONFIGURATION_GUIDE_V3.1.md for setup instructions."
            )

        # Initialize authentication
        self.auth = KalshiAuth(api_key, keyfile_path)

        # Session for connection pooling (more efficient)
        self.session = requests.Session()

        # Rate limiting (100 requests per minute for Kalshi)
        self.rate_limiter = RateLimiter(requests_per_minute=100)

        logger.info(
            f"KalshiClient initialized for {environment} environment",
            extra={"environment": environment, "base_url": self.base_url},
        )

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

    def get_balance(self) -> Decimal:
        """
        Fetch account balance.

        Returns:
            Account balance as Decimal

        Raises:
            requests.HTTPError: If API request fails

        Example:
            >>> client = KalshiClient("demo")
            >>> balance = client.get_balance()
            >>> print(f"Account balance: ${balance}")
            Account balance: $1234.5678

        Educational Note:
            Demo environment starts with fake balance (usually $10,000).
            Production environment shows your real account balance.

        Reference: REQ-CLI-002 (Balance Fetch Command)
        Related: REQ-SYS-003 (Decimal Precision)
        """
        response = self._make_request("GET", "/portfolio/balance")

        # Parse balance as Decimal
        balance_str = response.get("balance", "0")
        balance = Decimal(str(balance_str))

        logger.info(f"Fetched balance: ${balance}", extra={"balance": str(balance)})

        return balance

    def get_positions(
        self, status: str | None = None, ticker: str | None = None
    ) -> list[ProcessedPositionData]:
        """
        Get current positions.

        Args:
            status: Filter by status ("open" or "closed")
            ticker: Filter by market ticker

        Returns:
            List of position dictionaries with Decimal prices

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

        response = self._make_request("GET", "/portfolio/positions", params=params)
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

    def close(self) -> None:
        """
        Close the client and clean up resources.

        Example:
            >>> client = KalshiClient("demo")
            >>> try:
            ...     markets = client.get_markets()
            ... finally:
            ...     client.close()
        """
        self.session.close()
        logger.info("KalshiClient closed")
