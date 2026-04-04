"""
CRUD operations for orders.

Extracted from crud_operations.py during Phase 1a domain split.
Orders have zero cross-domain dependencies within crud_operations.py.

Tables covered:
    - orders (Migration 0025): Trading decisions with attribution, fill tracking,
      and terminal state guards.
"""

import json
import logging
from decimal import Decimal
from typing import cast

from .connection import fetch_all, fetch_one, get_cursor
from .crud_shared import ExecutionEnvironment, validate_decimal

logger = logging.getLogger(__name__)


# =============================================================================
# ORDER OPERATIONS
# =============================================================================
#
# Migration 0025: orders table with attribution, simplified trades table.
#   - Orders capture the trading DECISION (what, why, which strategy/model)
#   - Trades capture EXECUTION EVENTS (fills at the exchange)
#   - Attribution (strategy_id, model_id, edge_id, position_id) lives on
#     orders, NOT on trades. Trades inherit via FK JOIN.
#   - Orders are MUTABLE (status, fill quantities change). NOT SCD.
#   - Terminal state guard: filled/cancelled/expired cannot be resurrected.
#
# Kalshi API Status Mapping:
#   Kalshi uses "executed" (we use "filled") and "canceled" (we use "cancelled").
#   Use KALSHI_STATUS_MAP to translate before calling update_order_status().
# =============================================================================

# Kalshi API uses different status names than our internal model.
# Apply this mapping when ingesting order data from the Kalshi API:
#   kalshi_status = KALSHI_STATUS_MAP.get(api_status, api_status)
KALSHI_STATUS_MAP: dict[str, str] = {
    "executed": "filled",
    "canceled": "cancelled",
}

# Valid values for order enum-like fields (used in runtime validation)
_VALID_ORDER_SIDES = {"yes", "no"}
_VALID_ORDER_ACTIONS = {"buy", "sell"}
_VALID_ORDER_TYPES = {"market", "limit"}
_VALID_TIME_IN_FORCE = {"fill_or_kill", "good_till_canceled", "immediate_or_cancel"}
_VALID_EXEC_ENVS = {"live", "paper", "backtest"}
_VALID_TRADE_SOURCES = {"automated", "manual"}
_VALID_ORDER_STATUSES = {
    "submitted",
    "resting",
    "pending",
    "partial_fill",
    "filled",
    "cancelled",
    "expired",
}
_TERMINAL_ORDER_STATUSES = {"filled", "cancelled", "expired"}


def create_order(
    platform_id: str,
    external_order_id: str,
    market_internal_id: int,
    side: str,
    action: str,
    requested_price: Decimal,
    requested_quantity: int,
    order_type: str = "market",
    time_in_force: str = "good_till_canceled",
    strategy_id: int | None = None,
    model_id: int | None = None,
    edge_id: int | None = None,
    position_id: int | None = None,
    client_order_id: str | None = None,
    execution_environment: ExecutionEnvironment = "live",
    trade_source: str = "automated",
    order_metadata: dict | None = None,
) -> int:
    """
    Create a new order record.

    An order represents a trading DECISION: what was requested, why (attribution),
    and the current fill state. Orders are mutable -- status and fill quantities
    update as the exchange processes them.

    Args:
        platform_id: FK to platforms(platform_id), e.g. 'kalshi'
        external_order_id: Exchange-assigned order ID (unique per platform)
        market_internal_id: Integer FK to markets(id) surrogate PK
        side: 'yes' or 'no' (which outcome is being bet on)
        action: 'buy' or 'sell' (entering or exiting a position)
        requested_price: Limit price as DECIMAL(10,4) in [0, 1]
        requested_quantity: Number of contracts requested (> 0)
        order_type: 'market' or 'limit' (default 'market')
        time_in_force: 'fill_or_kill', 'good_till_canceled', or 'immediate_or_cancel'
        strategy_id: FK to strategies(strategy_id) for attribution
        model_id: FK to probability_models(model_id) for attribution
        edge_id: FK to edges(id) for attribution
        position_id: FK to positions(id) for attribution
        client_order_id: User-provided tracking ID
        execution_environment: 'live', 'paper', or 'backtest'
        trade_source: 'automated' or 'manual'
        order_metadata: Additional data stored as JSONB

    Returns:
        Integer surrogate PK (orders.id) of the newly created order.

    Raises:
        TypeError: If requested_price is not Decimal
        ValueError: If side, action, order_type, time_in_force,
            execution_environment, or trade_source has invalid value

    Educational Note:
        Kalshi Status Mapping:
            Kalshi API uses "executed" (we use "filled") and "canceled"
            (we use "cancelled" with double-l). When ingesting from Kalshi,
            translate via KALSHI_STATUS_MAP before calling:
                internal = KALSHI_STATUS_MAP.get(kalshi_status, kalshi_status)

        Attribution Design:
            Attribution lives on orders, not trades. To get a trade's strategy,
            JOIN trades.order_id -> orders.id -> orders.strategy_id. This avoids
            duplicating attribution across every fill event.

    Example:
        >>> order_pk = create_order(
        ...     platform_id='kalshi',
        ...     external_order_id='abc-123',
        ...     market_internal_id=42,
        ...     side='yes',
        ...     action='buy',
        ...     requested_price=Decimal("0.5500"),
        ...     requested_quantity=10,
        ...     strategy_id=1,
        ...     execution_environment='paper',
        ... )
        >>> # Returns surrogate id (e.g., 1)

    References:
        - Migration 0025: create_orders
        - issue336_council_findings.md: UNANIMOUS Option 2
    """
    # Runtime type validation (enforces Decimal precision)
    requested_price = validate_decimal(requested_price, "requested_price")

    # Runtime enum-like validation (Glokta finding #5)
    if side not in _VALID_ORDER_SIDES:
        raise ValueError(f"side must be one of {_VALID_ORDER_SIDES}, got '{side}'")
    if action not in _VALID_ORDER_ACTIONS:
        raise ValueError(f"action must be one of {_VALID_ORDER_ACTIONS}, got '{action}'")
    if order_type not in _VALID_ORDER_TYPES:
        raise ValueError(f"order_type must be one of {_VALID_ORDER_TYPES}, got '{order_type}'")
    if time_in_force not in _VALID_TIME_IN_FORCE:
        raise ValueError(
            f"time_in_force must be one of {_VALID_TIME_IN_FORCE}, got '{time_in_force}'"
        )
    if execution_environment not in _VALID_EXEC_ENVS:
        raise ValueError(
            f"execution_environment must be one of {_VALID_EXEC_ENVS}, "
            f"got '{execution_environment}'"
        )
    if trade_source not in _VALID_TRADE_SOURCES:
        raise ValueError(
            f"trade_source must be one of {_VALID_TRADE_SOURCES}, got '{trade_source}'"
        )

    insert_query = """
        INSERT INTO orders (
            platform_id, external_order_id, client_order_id,
            market_internal_id,
            strategy_id, model_id, edge_id, position_id,
            side, action, order_type, time_in_force,
            requested_price, requested_quantity,
            remaining_quantity, status,
            execution_environment, trade_source,
            order_metadata
        )
        VALUES (
            %s, %s, %s,
            %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, 'submitted',
            %s, %s,
            %s
        )
        RETURNING id
    """

    params = (
        platform_id,
        external_order_id,
        client_order_id,
        market_internal_id,
        strategy_id,
        model_id,
        edge_id,
        position_id,
        side,
        action,
        order_type,
        time_in_force,
        requested_price,
        requested_quantity,
        requested_quantity,  # remaining_quantity = requested_quantity initially
        execution_environment,
        trade_source,
        json.dumps(order_metadata) if order_metadata is not None else None,
    )

    with get_cursor(commit=True) as cur:
        cur.execute(insert_query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def get_order_by_id(order_pk: int) -> dict | None:
    """
    Retrieve an order by its surrogate primary key.

    Args:
        order_pk: Integer PK of the order (orders.id)

    Returns:
        Dictionary of column:value pairs, or None if not found.

    Example:
        >>> order = get_order_by_id(42)
        >>> if order:
        ...     print(order['status'], order['filled_quantity'])

    References:
        - Migration 0025: create_orders
    """
    return fetch_one("SELECT * FROM orders WHERE id = %s", (order_pk,))


def get_order_by_external_id(platform_id: str, external_order_id: str) -> dict | None:
    """
    Retrieve an order by its platform + external order ID (unique pair).

    This is the primary lookup path when processing order updates from the
    exchange API, since the exchange provides its own order ID.

    Args:
        platform_id: Platform identifier (e.g. 'kalshi')
        external_order_id: Exchange-assigned order ID

    Returns:
        Dictionary of column:value pairs, or None if not found.

    Example:
        >>> order = get_order_by_external_id('kalshi', 'abc-123')

    References:
        - Migration 0025: UNIQUE(platform_id, external_order_id)
    """
    return fetch_one(
        "SELECT * FROM orders WHERE platform_id = %s AND external_order_id = %s",
        (platform_id, external_order_id),
    )


def update_order_status(order_pk: int, new_status: str) -> bool:
    """
    Update an order's lifecycle status with terminal state guard.

    TERMINAL STATE GUARD (Glokta finding #1): Orders in terminal states
    (filled, cancelled, expired) CANNOT be updated. The WHERE clause rejects
    any attempt to resurrect a terminal order, preventing data corruption.

    Timestamp behavior:
        - filled -> sets filled_at = NOW()
        - cancelled -> sets cancelled_at = NOW()
        - expired -> sets cancelled_at = NOW() (Glokta finding #2: expiration
          is a cancellation variant)
        - All transitions -> sets updated_at = NOW()

    Kalshi Status Mapping:
        Kalshi API uses "executed" (= our "filled") and "canceled" (= our
        "cancelled"). Translate via KALSHI_STATUS_MAP before calling:
            internal = KALSHI_STATUS_MAP.get(kalshi_status, kalshi_status)
            update_order_status(pk, internal)

    Args:
        order_pk: Integer PK of the order
        new_status: Target status (must be in _VALID_ORDER_STATUSES)

    Returns:
        True if the order was updated, False if not found or in terminal state.

    Raises:
        ValueError: If new_status is not a valid order status

    Example:
        >>> success = update_order_status(42, 'resting')
        >>> # Terminal orders silently reject updates:
        >>> update_order_status(42, 'filled')  # True
        >>> update_order_status(42, 'resting')  # False (already terminal)

    References:
        - Migration 0025: create_orders
        - Glokta findings #1, #2, #4
    """
    if new_status not in _VALID_ORDER_STATUSES:
        raise ValueError(f"new_status must be one of {_VALID_ORDER_STATUSES}, got '{new_status}'")

    # Build timestamp updates based on target status
    extra_sets = ""
    if new_status == "filled":
        extra_sets = ", filled_at = NOW()"
    elif new_status in ("cancelled", "expired"):
        # Expired is a cancellation variant (Glokta finding #2)
        extra_sets = ", cancelled_at = NOW()"

    query = f"""
        UPDATE orders
        SET status = %s,
            updated_at = NOW(){extra_sets}
        WHERE id = %s
          AND status NOT IN ('filled', 'cancelled', 'expired')
    """  # noqa: S608 -- extra_sets is built from hardcoded literals, not user input

    with get_cursor(commit=True) as cur:
        cur.execute(query, (new_status, order_pk))
        return int(cur.rowcount or 0) > 0


def update_order_fill(
    order_pk: int,
    fill_quantity: int,
    fill_price: Decimal,
    fees: Decimal = Decimal("0.0000"),
) -> bool:
    """
    Record a fill event on an order (atomic quantity/price/fee update).

    Performs an atomic SQL update that:
    1. Increments filled_quantity by fill_quantity
    2. Decrements remaining_quantity by fill_quantity
    3. Computes weighted average fill price across all fills
    4. Accumulates total_fees
    5. Auto-sets status to 'partial_fill' or 'filled' based on remaining

    Overfill protection: WHERE remaining_quantity >= fill_quantity prevents
    recording more fills than the order requested.

    Terminal state guard: WHERE status NOT IN ('filled', 'cancelled', 'expired')
    prevents fills on already-terminal orders.

    Args:
        order_pk: Integer PK of the order
        fill_quantity: Number of contracts filled in this event (must be > 0)
        fill_price: Execution price as DECIMAL(10,4) in [0, 1]
        fees: Fees for this fill as DECIMAL(10,4) (default 0)

    Returns:
        True if the fill was recorded, False if order not found, already
        terminal, or fill_quantity exceeds remaining.

    Raises:
        TypeError: If fill_price or fees is not Decimal
        ValueError: If fill_quantity <= 0

    Educational Note:
        Weighted Average Price Formula:
            new_avg = (old_avg * old_filled + fill_price * fill_qty) /
                      (old_filled + fill_qty)
        The COALESCE handles the first fill where average_fill_price is NULL.

    Example:
        >>> # First fill: 5 of 10 contracts at 0.55
        >>> update_order_fill(42, 5, Decimal("0.5500"), Decimal("0.0100"))
        >>> # Second fill: remaining 5 at 0.56
        >>> update_order_fill(42, 5, Decimal("0.5600"), Decimal("0.0100"))
        >>> # Order is now 'filled' with average_fill_price ~= 0.5550

    References:
        - Migration 0025: create_orders
        - Glokta finding #3: fill_quantity validation
    """
    # Validate fill_quantity > 0 (Glokta finding #3)
    if fill_quantity <= 0:
        raise ValueError(f"fill_quantity must be > 0, got {fill_quantity}")

    # Runtime type validation (enforces Decimal precision)
    fill_price = validate_decimal(fill_price, "fill_price")
    fees = validate_decimal(fees, "fees")

    query = """
        UPDATE orders
        SET filled_quantity = filled_quantity + %s,
            remaining_quantity = remaining_quantity - %s,
            average_fill_price = (
                COALESCE(average_fill_price, 0) * filled_quantity + %s * %s
            ) / (filled_quantity + %s),
            total_fees = COALESCE(total_fees, 0) + %s,
            status = CASE
                WHEN remaining_quantity - %s = 0 THEN 'filled'
                ELSE 'partial_fill'
            END,
            filled_at = CASE
                WHEN remaining_quantity - %s = 0 THEN NOW()
                ELSE filled_at
            END,
            updated_at = NOW()
        WHERE id = %s
          AND remaining_quantity >= %s
          AND status NOT IN ('filled', 'cancelled', 'expired')
    """

    params = (
        fill_quantity,  # filled_quantity + %s
        fill_quantity,  # remaining_quantity - %s
        fill_price,  # average_fill_price numerator: fill_price * fill_qty
        fill_quantity,  # average_fill_price numerator: fill_price * fill_qty
        fill_quantity,  # average_fill_price denominator
        fees,  # total_fees + %s
        fill_quantity,  # CASE remaining - %s = 0 (status)
        fill_quantity,  # CASE remaining - %s = 0 (filled_at)
        order_pk,  # WHERE id = %s
        fill_quantity,  # WHERE remaining_quantity >= %s
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        return int(cur.rowcount or 0) > 0


def cancel_order(order_pk: int) -> bool:
    """
    Cancel an order if it is still in a cancellable state.

    Only orders with status IN ('submitted', 'resting', 'pending', 'partial_fill')
    can be cancelled. Already-filled, already-cancelled, and expired orders
    are silently rejected (returns False).

    Args:
        order_pk: Integer PK of the order

    Returns:
        True if the order was cancelled, False if not found or not cancellable.

    Example:
        >>> cancel_order(42)  # True if order was open
        >>> cancel_order(42)  # False (already cancelled)

    References:
        - Migration 0025: create_orders
    """
    query = """
        UPDATE orders
        SET status = 'cancelled',
            cancelled_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
          AND status IN ('submitted', 'resting', 'pending', 'partial_fill')
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (order_pk,))
        return int(cur.rowcount or 0) > 0


def get_open_orders(
    strategy_id: int | None = None,
    execution_environment: ExecutionEnvironment | None = None,
    market_internal_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query orders in active (non-terminal) statuses.

    Active statuses: submitted, resting, pending, partial_fill.
    Terminal statuses (excluded): filled, cancelled, expired.

    Args:
        strategy_id: Optional filter by strategy FK
        execution_environment: Optional filter by 'live', 'paper', or 'backtest'
        market_internal_id: Optional filter by market FK
        limit: Maximum rows to return (default 100)

    Returns:
        List of dictionaries, one per open order, ordered by created_at DESC.

    Example:
        >>> orders = get_open_orders(strategy_id=1, execution_environment='paper')
        >>> for o in orders:
        ...     print(o['external_order_id'], o['status'], o['remaining_quantity'])

    References:
        - Migration 0025: create_orders
    """
    query = """
        SELECT * FROM orders
        WHERE status IN ('submitted', 'resting', 'pending', 'partial_fill')
    """
    params: list = []

    if strategy_id is not None:
        query += " AND strategy_id = %s"
        params.append(strategy_id)

    if execution_environment is not None:
        query += " AND execution_environment = %s"
        params.append(execution_environment)

    if market_internal_id is not None:
        query += " AND market_internal_id = %s"
        params.append(market_internal_id)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    return fetch_all(query, tuple(params))
