"""
Sample API responses for mocking external APIs.

This module provides realistic sample responses for:
- Kalshi API (markets, balance, positions, fills, settlements)
- Error responses (401, 429, 500, etc.)

All price values in Kalshi responses use string format for dollar amounts,
which will be parsed to Decimal in the actual client implementation.

Usage in tests:
    from tests.fixtures.api_responses import KALSHI_MARKET_RESPONSE

    @mock.patch('requests.Session.request')
    def test_get_markets(mock_request):
        mock_request.return_value.json.return_value = KALSHI_MARKET_RESPONSE
        # Test implementation
"""

from decimal import Decimal

# =============================================================================
# Kalshi API Responses
# =============================================================================

KALSHI_MARKET_RESPONSE = {
    "markets": [
        {
            "ticker": "KXNFLGAME-25DEC15-KC-YES",
            "event_ticker": "KXNFLGAME-25DEC15",
            "series_ticker": "KXNFLGAME",
            "title": "Will Kansas City win against Cleveland on Dec 15?",
            "subtitle": "Kansas City Chiefs to win",
            "open_time": "2025-12-01T00:00:00Z",
            "close_time": "2025-12-15T17:00:00Z",
            "expiration_time": "2025-12-15T22:00:00Z",
            "status": "open",
            "can_close_early": False,
            "result": None,
            # Kalshi dual format: legacy integer cents + sub-penny string dollars
            "yes_bid": 62,  # Legacy: integer cents
            "yes_bid_dollars": "0.6200",  # Sub-penny: string dollars
            "yes_ask": 63,
            "yes_ask_dollars": "0.6250",
            "no_bid": 38,
            "no_bid_dollars": "0.3750",
            "no_ask": 38,
            "no_ask_dollars": "0.3800",
            "last_price": 62,
            "last_price_dollars": "0.6225",
            "volume": 15420,
            "open_interest": 8750,
            "liquidity": 125000,
            "liquidity_dollars": "1250.0000",
        },
        {
            "ticker": "KXNFLGAME-25DEC15-BUF-YES",
            "event_ticker": "KXNFLGAME-25DEC15",
            "series_ticker": "KXNFLGAME",
            "title": "Will Buffalo win against Detroit on Dec 15?",
            "subtitle": "Buffalo Bills to win",
            "open_time": "2025-12-01T00:00:00Z",
            "close_time": "2025-12-15T17:00:00Z",
            "expiration_time": "2025-12-15T22:00:00Z",
            "status": "open",
            "can_close_early": False,
            "result": None,
            # Sub-penny pricing example (critical test case)
            "yes_bid": 43,  # Legacy: integer cents (rounded)
            "yes_bid_dollars": "0.4275",  # Sub-penny: exact value
            "yes_ask": 43,
            "yes_ask_dollars": "0.4325",
            "no_bid": 57,
            "no_bid_dollars": "0.5675",
            "no_ask": 57,
            "no_ask_dollars": "0.5725",
            "last_price": 43,
            "last_price_dollars": "0.4300",
            "volume": 8920,
            "open_interest": 4560,
            "liquidity": 87500,
            "liquidity_dollars": "875.0000",
        },
    ],
    "cursor": "next_page_token_abc123",  # Pagination cursor
}

KALSHI_SINGLE_MARKET_RESPONSE = {
    "market": {
        "ticker": "KXNFLGAME-25DEC15-KC-YES",
        "event_ticker": "KXNFLGAME-25DEC15",
        "series_ticker": "KXNFLGAME",
        "title": "Will Kansas City win against Cleveland on Dec 15?",
        "subtitle": "Kansas City Chiefs to win",
        "open_time": "2025-12-01T00:00:00Z",
        "close_time": "2025-12-15T17:00:00Z",
        "expiration_time": "2025-12-15T22:00:00Z",
        "status": "open",
        "can_close_early": False,
        "result": None,
        # Kalshi dual format: legacy integer cents + sub-penny string dollars
        "yes_bid": 62,  # Legacy: integer cents
        "yes_bid_dollars": "0.6200",  # Sub-penny: string dollars
        "yes_ask": 63,
        "yes_ask_dollars": "0.6250",
        "no_bid": 37,
        "no_bid_dollars": "0.3750",
        "no_ask": 38,
        "no_ask_dollars": "0.3800",
        "last_price": 62,
        "last_price_dollars": "0.6225",
        "volume": 15420,
        "open_interest": 8750,
        "liquidity": 125000,
        "liquidity_dollars": "1250.0000",
    }
}

KALSHI_BALANCE_RESPONSE = {
    "balance": "1234.5678"  # String format with 4 decimal places
}

KALSHI_POSITIONS_RESPONSE = {
    "positions": [
        {
            "ticker": "KXNFLGAME-25DEC15-KC-YES",
            "market_ticker": "KXNFLGAME-25DEC15-KC-YES",
            "position": 100,  # Number of contracts
            "side": "yes",
            "user_average_price": "0.6100",  # Average entry price
            "realized_pnl": "0.0000",
            "total_cost": "61.0000",
            "fees_paid": "1.2200",
            "resting_order_count": 0,
        },
        {
            "ticker": "KXNFLGAME-25DEC15-BUF-YES",
            "market_ticker": "KXNFLGAME-25DEC15-BUF-YES",
            "position": 50,
            "side": "yes",
            "user_average_price": "0.4200",
            "realized_pnl": "5.0000",
            "total_cost": "21.0000",
            "fees_paid": "0.4200",
            "resting_order_count": 1,
        },
    ]
}

KALSHI_FILLS_RESPONSE = {
    "fills": [
        {
            "order_id": "order_123abc",
            "trade_id": "trade_456def",
            "ticker": "KXNFLGAME-25DEC15-KC-YES",
            "side": "yes",
            "action": "buy",
            "count": 50,
            "price": 0.6150,  # Legacy: float (AVOID!)
            "yes_price": 62,  # Legacy: integer cents
            "no_price": 38,
            "yes_price_fixed": "0.6200",  # Sub-penny: string dollars
            "no_price_fixed": "0.3800",
            "created_time": "2025-12-10T14:23:45Z",
            "is_taker": True,
        },
        {
            "order_id": "order_789ghi",
            "trade_id": "trade_012jkl",
            "ticker": "KXNFLGAME-25DEC15-BUF-YES",
            "side": "yes",
            "action": "buy",
            "count": 50,
            "price": 0.4200,  # Legacy: float (AVOID!)
            "yes_price": 42,  # Legacy: integer cents
            "no_price": 58,
            "yes_price_fixed": "0.4200",  # Sub-penny: string dollars
            "no_price_fixed": "0.5800",
            "created_time": "2025-12-10T15:10:22Z",
            "is_taker": False,
        },
    ],
    "cursor": None,  # No more pages
}

KALSHI_SETTLEMENTS_RESPONSE = {
    "settlements": [
        {
            "ticker": "KXNFLGAME-25DEC08-KC-YES",
            "market_result": "yes",  # Market resolved YES
            "settlement_value": "1.0000",  # Full dollar payout
            "settled_time": "2025-12-08T23:30:00Z",
            "revenue": "100.0000",  # 100 contracts * $1.00
            "total_fees": "2.0000",
        },
        {
            "ticker": "KXNFLGAME-25DEC08-BUF-YES",
            "market_result": "no",  # Market resolved NO
            "settlement_value": "0.0000",  # Worthless
            "settled_time": "2025-12-08T23:45:00Z",
            "revenue": "0.0000",
            "total_fees": "0.0000",
        },
    ]
}

# =============================================================================
# Kalshi Error Responses
# =============================================================================

KALSHI_ERROR_401_RESPONSE = {
    "code": "unauthorized",
    "message": "Invalid signature or expired token",
    "details": "Authentication failed. Please check your API key and signature.",
}

KALSHI_ERROR_429_RESPONSE = {
    "code": "rate_limit_exceeded",
    "message": "Too many requests",
    "details": "You have exceeded the rate limit of 100 requests per minute.",
    "retry_after": 30,  # Seconds to wait before retry
}

KALSHI_ERROR_500_RESPONSE = {
    "code": "internal_server_error",
    "message": "Internal server error",
    "details": "An unexpected error occurred. Please try again later.",
}

KALSHI_ERROR_400_RESPONSE = {
    "code": "bad_request",
    "message": "Invalid request parameters",
    "details": "The 'series_ticker' parameter is required.",
}

# =============================================================================
# Expected Parsed Results (After Decimal Conversion)
# =============================================================================

EXPECTED_MARKET_DATA = {
    "ticker": "KXNFLGAME-25DEC15-KC-YES",
    "yes_bid": Decimal("0.6200"),
    "yes_ask": Decimal("0.6250"),
    "no_bid": Decimal("0.3750"),
    "no_ask": Decimal("0.3800"),
    "last_price": Decimal("0.6225"),
}

EXPECTED_BALANCE = Decimal("1234.5678")

EXPECTED_POSITION_DATA = {
    "ticker": "KXNFLGAME-25DEC15-KC-YES",
    "position": 100,
    "user_average_price": Decimal("0.6100"),
    "total_cost": Decimal("61.0000"),
}

# =============================================================================
# Sub-Penny Precision Test Cases (CRITICAL)
# =============================================================================

SUB_PENNY_TEST_CASES = [
    {"api_value": "0.4275", "expected_decimal": Decimal("0.4275")},
    {"api_value": "0.4976", "expected_decimal": Decimal("0.4976")},
    {"api_value": "0.0001", "expected_decimal": Decimal("0.0001")},
    {"api_value": "0.9999", "expected_decimal": Decimal("0.9999")},
    {"api_value": "0.5000", "expected_decimal": Decimal("0.5000")},
]

# =============================================================================
# Arithmetic Precision Test Cases
# =============================================================================

DECIMAL_ARITHMETIC_TESTS = [
    {
        "operation": "spread",
        "ask": Decimal("0.6250"),
        "bid": Decimal("0.6200"),
        "expected_result": Decimal("0.0050"),
    },
    {
        "operation": "pnl",
        "entry_price": Decimal("0.6100"),
        "exit_price": Decimal("0.6500"),
        "quantity": 100,
        "expected_result": Decimal("4.0000"),  # (0.6500 - 0.6100) * 100 = 0.04 * 100
    },
    {
        "operation": "edge",
        "true_prob": Decimal("0.7000"),
        "market_price": Decimal("0.6200"),
        "expected_result": Decimal("0.0800"),  # 0.7000 - 0.6200
    },
]
