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


class ProcessedMarketData(TypedDict):
    """Market data after Decimal conversion (for internal use)."""

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
    # Price fields as Decimal
    yes_bid: Decimal
    yes_ask: Decimal
    no_bid: Decimal
    no_ask: Decimal
    last_price: Decimal
    volume: int
    open_interest: int
    liquidity: int


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


class ProcessedFillData(TypedDict):
    """Fill data after Decimal conversion (for internal use)."""

    order_id: str
    trade_id: str
    ticker: str
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    count: int
    price: Decimal  # Execution price as Decimal
    created_time: str
    is_taker: bool


class ProcessedSettlementData(TypedDict):
    """Settlement data after Decimal conversion (for internal use)."""

    ticker: str
    market_result: Literal["yes", "no"]
    settlement_value: Decimal
    settled_time: str
    revenue: Decimal
    total_fees: Decimal
