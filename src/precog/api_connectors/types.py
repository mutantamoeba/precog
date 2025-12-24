"""
Type definitions for Kalshi API responses.

Provides TypedDict definitions for all API response structures to enable
type checking and IDE autocomplete.

All price fields in API responses are strings (e.g., "0.6250") which should
be converted to Decimal in the client implementation.

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related ADR: ADR-002 (Decimal Precision for Monetary Values)
"""

from decimal import Decimal
from typing import Literal, TypedDict

# =============================================================================
# Market Response Types
# =============================================================================


class MarketData(TypedDict):
    """Single market data from Kalshi API."""

    ticker: str
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    open_time: str  # ISO 8601 format
    close_time: str
    expiration_time: str
    status: Literal["open", "closed", "settled"]
    can_close_early: bool
    result: Literal["yes", "no"] | None
    # Price fields as strings (will be converted to Decimal)
    yes_bid: str
    yes_ask: str
    no_bid: str
    no_ask: str
    last_price: str
    volume: int
    open_interest: int
    liquidity: int


class MarketsResponse(TypedDict):
    """Response from /markets endpoint."""

    markets: list[MarketData]
    cursor: str | None  # Pagination cursor


class SingleMarketResponse(TypedDict):
    """Response from /markets/{ticker} endpoint."""

    market: MarketData


# =============================================================================
# Balance Response Type
# =============================================================================


class BalanceResponse(TypedDict):
    """Response from /portfolio/balance endpoint."""

    balance: str  # String format with 4 decimal places (e.g., "1234.5678")


# =============================================================================
# Position Response Types
# =============================================================================


class PositionData(TypedDict):
    """Single position data from Kalshi API."""

    ticker: str
    market_ticker: str
    position: int  # Number of contracts
    side: Literal["yes", "no"]
    user_average_price: str  # Average entry price
    realized_pnl: str
    total_cost: str
    fees_paid: str
    resting_order_count: int


class PositionsResponse(TypedDict):
    """Response from /portfolio/positions endpoint."""

    positions: list[PositionData]
    cursor: str | None


# =============================================================================
# Fill Response Types
# =============================================================================


class FillData(TypedDict):
    """Single fill (trade execution) from Kalshi API."""

    order_id: str
    trade_id: str
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    count: int
    price: str  # Execution price
    created_time: str
    is_taker: bool


class FillsResponse(TypedDict):
    """Response from /portfolio/fills endpoint."""

    fills: list[FillData]
    cursor: str | None


# =============================================================================
# Settlement Response Types
# =============================================================================


class SettlementData(TypedDict):
    """Single settlement data from Kalshi API."""

    ticker: str
    market_result: Literal["yes", "no"]
    settlement_value: str  # "1.0000" for win, "0.0000" for loss
    settled_time: str
    revenue: str  # Total payout
    total_fees: str


class SettlementsResponse(TypedDict):
    """Response from /portfolio/settlements endpoint."""

    settlements: list[SettlementData]


# =============================================================================
# Error Response Types
# =============================================================================


class ErrorResponse(TypedDict):
    """Standard error response from Kalshi API."""

    code: str
    message: str
    details: str


class RateLimitErrorResponse(ErrorResponse):
    """429 rate limit error with retry information."""

    retry_after: int  # Seconds to wait


# =============================================================================
# Processed Response Types (After Decimal Conversion)
# =============================================================================


class ProcessedMarketData(TypedDict, total=False):
    """Market data after Decimal conversion (for internal use).

    The Kalshi API returns dual-format pricing:
    - Legacy integer cent fields (yes_bid, yes_ask, etc.)
    - Sub-penny dollar string fields (*_dollars suffix)

    After processing, the *_dollars fields are converted to Decimal
    for sub-penny precision while legacy cent fields remain as int.

    Using total=False because different API endpoints return different
    subsets of fields (e.g., some don't include liquidity_dollars).
    """

    # Required string fields (always present)
    ticker: str
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    open_time: str
    close_time: str
    expiration_time: str
    status: Literal["open", "closed", "settled"]
    can_close_early: bool
    result: Literal["yes", "no"] | None

    # Legacy integer cent fields (kept as-is from API)
    yes_bid: int
    yes_ask: int
    no_bid: int
    no_ask: int
    last_price: int
    volume: int
    open_interest: int
    liquidity: int

    # Sub-penny Decimal fields (*_dollars suffix - converted to Decimal)
    yes_bid_dollars: Decimal
    yes_ask_dollars: Decimal
    no_bid_dollars: Decimal
    no_ask_dollars: Decimal
    last_price_dollars: Decimal
    liquidity_dollars: Decimal


class ProcessedPositionData(TypedDict):
    """Position data after Decimal conversion (for internal use)."""

    ticker: str
    market_ticker: str
    position: int
    side: Literal["yes", "no"]
    user_average_price: Decimal
    realized_pnl: Decimal
    total_cost: Decimal
    fees_paid: Decimal
    resting_order_count: int


class ProcessedFillData(TypedDict, total=False):
    """Fill data after Decimal conversion (for internal use).

    The Kalshi API returns dual-format pricing for fills:
    - Legacy integer cent fields (yes_price, no_price)
    - Sub-penny dollar string fields (*_fixed suffix)

    After processing, the *_fixed fields are converted to Decimal
    for sub-penny precision.

    Using total=False because different API endpoints return different
    subsets of fields.
    """

    order_id: str
    trade_id: str
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    count: int
    created_time: str
    is_taker: bool

    # Legacy integer cent fields
    price: float  # Legacy float - AVOID using
    yes_price: int
    no_price: int

    # Sub-penny Decimal fields (*_fixed suffix - converted to Decimal)
    yes_price_fixed: Decimal
    no_price_fixed: Decimal


class ProcessedSettlementData(TypedDict):
    """Settlement data after Decimal conversion (for internal use)."""

    ticker: str
    market_result: Literal["yes", "no"]
    settlement_value: Decimal
    settled_time: str
    revenue: Decimal
    total_fees: Decimal


# =============================================================================
# Order Types (for place_order, cancel_order, get_orders)
# =============================================================================


class OrderData(TypedDict, total=False):
    """Order data from Kalshi API after processing.

    Educational Note:
        Order Lifecycle:
        1. "resting" - Order placed, waiting in order book
        2. "pending" - Order being processed (rare to see)
        3. "executed" - Fully filled
        4. "canceled" - User canceled or expired

        Key Fields:
        - side: "yes" or "no" (which outcome you're betting on)
        - action: "buy" or "sell" (entering or exiting a position)
        - type: "limit" (specify price) or "market" (take best available)

    Reference: docs/guides/KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md
    """

    # Order identification
    order_id: str
    user_id: str
    client_order_id: str  # User-provided ID for tracking

    # Market and order details
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    type: Literal["limit", "market"]

    # Order status
    status: Literal["resting", "pending", "executed", "canceled"]

    # Pricing (Decimal after conversion)
    yes_price: int  # Legacy cents (1-99)
    no_price: int  # Legacy cents (1-99)
    yes_price_dollars: Decimal  # Sub-penny (e.g., 0.6275)
    no_price_dollars: Decimal  # Sub-penny

    # Fill information
    initial_count: int  # Original order size
    remaining_count: int  # Still unfilled
    fill_count: int  # How many filled

    # Costs and fees (Decimal after conversion)
    taker_fees: Decimal
    maker_fees: Decimal
    taker_fill_cost: Decimal
    maker_fill_cost: Decimal

    # Timestamps
    created_time: str
    expiration_time: str
    last_update_time: str

    # Execution details
    queue_position: int
    time_in_force: Literal["fill_or_kill", "good_till_canceled", "immediate_or_cancel"]


class OrderCreateRequest(TypedDict, total=False):
    """Request body for creating an order via POST /portfolio/orders.

    Required fields: ticker, side, action, count
    Price: Exactly one of yes_price, no_price, yes_price_dollars, no_price_dollars

    Educational Note:
        Kalshi Pricing Convention:
        - yes_price + no_price always equals 100 cents ($1.00)
        - If YES is $0.65, NO is automatically $0.35
        - Use *_dollars fields for sub-penny precision (0.6275)

        Order Types:
        - limit: Specify exact price (may not fill immediately)
        - market: Take best available price (fills immediately but costs more)

        Time In Force:
        - good_till_canceled: Stays in book until filled or canceled
        - fill_or_kill: Fill entire order immediately or cancel all
        - immediate_or_cancel: Fill what you can immediately, cancel rest

    Reference: docs/api-integration/KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md
    """

    # Required fields
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    count: int  # Number of contracts (min: 1)

    # Price specification (exactly one required for limit orders)
    yes_price: int  # Integer cents 1-99
    no_price: int  # Integer cents 1-99
    yes_price_dollars: str  # Sub-penny string "0.6275"
    no_price_dollars: str  # Sub-penny string "0.3725"

    # Optional fields
    type: Literal["limit", "market"]  # Default: limit
    client_order_id: str  # Custom tracking ID
    time_in_force: Literal["fill_or_kill", "good_till_canceled", "immediate_or_cancel"]
    expiration_ts: int  # Unix timestamp for order expiry
    post_only: bool  # Only add to book, never take (maker-only)
    reduce_only: bool  # Only reduce existing position
    buy_max_cost: int  # Max cost in cents (enables FOK behavior)
    self_trade_prevention_type: Literal["taker_at_cross", "maker"]


class OrderResponse(TypedDict):
    """Response from POST /portfolio/orders."""

    order: OrderData


# =============================================================================
# Series Types (for get_series)
# =============================================================================


class SeriesData(TypedDict, total=False):
    """Series data from Kalshi API.

    A series groups related markets (e.g., KXNFLGAME contains all NFL game markets).

    Educational Note:
        Series Hierarchy:
        - Category (e.g., "sports")
          └── Series (e.g., "KXNFLGAME")
              └── Events (e.g., "KXNFLGAME-25DEC15")
                  └── Markets (e.g., "KXNFLGAME-25DEC15-KC-YES")

        The series ticker is used to filter markets in get_markets(series_ticker=...).
    """

    ticker: str  # e.g., "KXNFLGAME"
    title: str  # e.g., "NFL Game Markets"
    category: str  # e.g., "sports"
    tags: list[str]  # e.g., ["nfl", "football", "american_football"]
    frequency: str  # e.g., "daily", "weekly", "event"
    expected_expiration_time: str  # When markets typically expire
    settlement_timer_seconds: int  # How long after expiry until settlement


class SeriesResponse(TypedDict):
    """Response from GET /series endpoint."""

    series: list[SeriesData]
    cursor: str | None
