"""
Unit Tests for Order CRUD Operations (Migration 0025).

Tests the order lifecycle CRUD functions: create, get, update status,
record fills, cancel, and query open orders. Validates terminal state
guard, overfill protection, Decimal enforcement, and enum validation.

Related:
- Migration 0025: create_orders
- ADR-002: Decimal Precision for All Financial Data
- issue336_council_findings.md: UNANIMOUS Option 2 (separate orders table)
- Glokta findings #1-#5

Usage:
    pytest tests/unit/database/test_crud_orders.py -v
    pytest tests/unit/database/test_crud_orders.py -v -m unit
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_orders import (
    KALSHI_STATUS_MAP,
    cancel_order,
    create_order,
    get_open_orders,
    get_order_by_external_id,
    get_order_by_id,
    update_order_fill,
    update_order_status,
)

# =============================================================================
# HELPERS
# =============================================================================


def _mock_cursor_context(mock_get_cursor, mock_cursor=None):
    """Set up mock_get_cursor to return a context manager yielding mock_cursor."""
    if mock_cursor is None:
        mock_cursor = MagicMock()
    mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


def _default_order_kwargs():
    """Return minimal valid kwargs for create_order.

    Includes ``execution_environment="paper"`` because as of the #622+#686
    synthesis PR, ``create_order`` requires this parameter with no Python
    default. Tests use 'paper' as the canonical default — see
    conftest.sample_position_data for rationale. Tests that need a
    different value should construct their own dict or strip the key
    before passing.
    """
    return {
        "platform_id": "kalshi",
        "external_order_id": "abc-123",
        "market_id": 42,
        "side": "yes",
        "action": "buy",
        "requested_price": Decimal("0.5500"),
        "requested_quantity": 10,
        "execution_environment": "paper",
    }


# =============================================================================
# CREATE ORDER TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateOrder:
    """Unit tests for create_order function."""

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_returns_surrogate_id(self, mock_get_cursor):
        """Test create_order returns the integer surrogate PK."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 7}

        result = create_order(**_default_order_kwargs())

        assert result == 7

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_sets_remaining_equals_requested(self, mock_get_cursor):
        """Test that remaining_quantity is set to requested_quantity on insert."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        create_order(**_default_order_kwargs())

        insert_call = mock_cursor.execute.call_args_list[0]
        insert_params = insert_call[0][1]
        # requested_quantity=10 should appear twice: once for requested, once for remaining
        # Find the requested_quantity and remaining_quantity positions
        # In params tuple: index 13 = requested_quantity, index 14 = remaining_quantity
        assert insert_params[13] == 10  # requested_quantity
        assert insert_params[14] == 10  # remaining_quantity = requested_quantity

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_sets_status_submitted(self, mock_get_cursor):
        """Test that new orders default to status='submitted'."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        create_order(**_default_order_kwargs())

        insert_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "'submitted'" in insert_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_decimal_price(self, mock_get_cursor):
        """Test that float values are rejected for requested_price."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["requested_price"] = 0.55  # float -- should raise

        with pytest.raises(TypeError, match="requested_price must be Decimal"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_side(self, mock_get_cursor):
        """Test that invalid side values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["side"] = "maybe"

        with pytest.raises(ValueError, match="side must be one of"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_action(self, mock_get_cursor):
        """Test that invalid action values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["action"] = "hold"

        with pytest.raises(ValueError, match="action must be one of"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_order_type(self, mock_get_cursor):
        """Test that invalid order_type values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["order_type"] = "stop_limit"

        with pytest.raises(ValueError, match="order_type must be one of"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_time_in_force(self, mock_get_cursor):
        """Test that invalid time_in_force values are rejected."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["time_in_force"] = "day"

        with pytest.raises(ValueError, match="time_in_force must be one of"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_execution_environment(self, mock_get_cursor):
        """Test that invalid execution_environment values are rejected (Glokta #5)."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["execution_environment"] = "staging"

        with pytest.raises(ValueError, match="execution_environment must be one of"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_validates_trade_source(self, mock_get_cursor):
        """Test that invalid trade_source values are rejected (Glokta #5)."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_order_kwargs()
        kwargs["trade_source"] = "bot"

        with pytest.raises(ValueError, match="trade_source must be one of"):
            create_order(**kwargs)

    @patch("precog.database.crud_orders.get_cursor")
    def test_create_order_with_all_optional_fields(self, mock_get_cursor):
        """Test create_order with every optional parameter provided."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 99}

        result = create_order(
            platform_id="kalshi",
            external_order_id="xyz-789",
            market_id=42,
            side="no",
            action="sell",
            requested_price=Decimal("0.4500"),
            requested_quantity=5,
            order_type="limit",
            time_in_force="fill_or_kill",
            strategy_id=1,
            model_id=2,
            edge_id=3,
            position_id=4,
            client_order_id="my-tracking-id",
            execution_environment="paper",
            trade_source="manual",
            order_metadata={"source": "test"},
            orderbook_snapshot_id=7,
        )

        assert result == 99
        # orderbook_snapshot_id is appended last in the params tuple (see
        # migration 0063 + crud_orders.create_order params ordering). Index
        # 18 = 19th element (0-indexed), the final slot.
        insert_params = mock_cursor.execute.call_args_list[0][0][1]
        assert insert_params[18] == 7, (
            "create_order must pass orderbook_snapshot_id as the final positional "
            f"param; got params[18]={insert_params[18]!r}"
        )


# =============================================================================
# GET ORDER BY ID TESTS
# =============================================================================


@pytest.mark.unit
class TestGetOrderById:
    """Unit tests for get_order_by_id function."""

    @patch("precog.database.crud_orders.fetch_one")
    def test_get_order_by_id_found(self, mock_fetch_one):
        """Test retrieving an existing order by PK."""
        mock_fetch_one.return_value = {"id": 42, "status": "submitted"}

        result = get_order_by_id(42)

        assert result is not None
        assert result["id"] == 42
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_orders.fetch_one")
    def test_get_order_by_id_not_found(self, mock_fetch_one):
        """Test retrieving a non-existent order returns None."""
        mock_fetch_one.return_value = None

        result = get_order_by_id(999)

        assert result is None


# =============================================================================
# GET ORDER BY EXTERNAL ID TESTS
# =============================================================================


@pytest.mark.unit
class TestGetOrderByExternalId:
    """Unit tests for get_order_by_external_id function."""

    @patch("precog.database.crud_orders.fetch_one")
    def test_get_order_by_external_id_found(self, mock_fetch_one):
        """Test retrieving an order by platform + external_order_id."""
        mock_fetch_one.return_value = {"id": 42, "external_order_id": "abc-123"}

        result = get_order_by_external_id("kalshi", "abc-123")

        assert result is not None
        assert result["external_order_id"] == "abc-123"
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_orders.fetch_one")
    def test_get_order_by_external_id_not_found(self, mock_fetch_one):
        """Test retrieving a non-existent external order returns None."""
        mock_fetch_one.return_value = None

        result = get_order_by_external_id("kalshi", "nonexistent")

        assert result is None


# =============================================================================
# UPDATE ORDER STATUS TESTS
# =============================================================================


@pytest.mark.unit
class TestUpdateOrderStatus:
    """Unit tests for update_order_status function."""

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_valid_transition(self, mock_get_cursor):
        """Test a valid status transition returns True."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        result = update_order_status(42, "resting")

        assert result is True

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_terminal_guard_filled(self, mock_get_cursor):
        """Test that filled orders cannot be updated (Glokta #1)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0  # WHERE clause rejects terminal status

        result = update_order_status(42, "resting")

        assert result is False
        # Verify WHERE clause includes terminal state guard
        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "NOT IN ('filled', 'cancelled', 'expired')" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_terminal_guard_cancelled(self, mock_get_cursor):
        """Test that cancelled orders cannot be updated (Glokta #1)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = update_order_status(42, "submitted")

        assert result is False

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_terminal_guard_expired(self, mock_get_cursor):
        """Test that expired orders cannot be updated (Glokta #1)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = update_order_status(42, "submitted")

        assert result is False

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_sets_filled_at(self, mock_get_cursor):
        """Test that transitioning to 'filled' sets filled_at = NOW()."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_status(42, "filled")

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "filled_at = NOW()" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_sets_cancelled_at_for_cancelled(self, mock_get_cursor):
        """Test that transitioning to 'cancelled' sets cancelled_at = NOW()."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_status(42, "cancelled")

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "cancelled_at = NOW()" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_sets_cancelled_at_for_expired(self, mock_get_cursor):
        """Test that transitioning to 'expired' sets cancelled_at (Glokta #2)."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_status(42, "expired")

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "cancelled_at = NOW()" in execute_sql

    def test_update_status_rejects_invalid_status(self):
        """Test that invalid status values raise ValueError."""
        with pytest.raises(ValueError, match="new_status must be one of"):
            update_order_status(42, "unknown_status")

    @patch("precog.database.crud_orders.get_cursor")
    def test_update_status_always_sets_updated_at(self, mock_get_cursor):
        """Test that updated_at = NOW() is always set."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_status(42, "resting")

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "updated_at = NOW()" in execute_sql


# =============================================================================
# UPDATE ORDER FILL TESTS
# =============================================================================


@pytest.mark.unit
class TestUpdateOrderFill:
    """Unit tests for update_order_fill function."""

    @patch("precog.database.crud_orders.get_cursor")
    def test_fill_increments_quantities(self, mock_get_cursor):
        """Test that fill SQL increments filled and decrements remaining."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        result = update_order_fill(42, 5, Decimal("0.5500"))

        assert result is True
        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "filled_quantity = filled_quantity +" in execute_sql
        assert "remaining_quantity = remaining_quantity -" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_fill_sets_partial_fill_or_filled_status(self, mock_get_cursor):
        """Test that fill SQL uses CASE to set partial_fill or filled."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_fill(42, 5, Decimal("0.5500"))

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "'partial_fill'" in execute_sql
        assert "'filled'" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_fill_computes_weighted_average_price(self, mock_get_cursor):
        """Test that fill SQL computes weighted average fill price."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_fill(42, 5, Decimal("0.5500"))

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "average_fill_price" in execute_sql
        assert "COALESCE" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_fill_overfill_protection(self, mock_get_cursor):
        """Test that WHERE clause prevents overfilling."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0  # WHERE remaining >= fill_qty fails

        result = update_order_fill(42, 100, Decimal("0.5500"))

        assert result is False
        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "remaining_quantity >=" in execute_sql

    def test_fill_validates_fill_quantity_positive(self):
        """Test that fill_quantity <= 0 raises ValueError (Glokta #3)."""
        with pytest.raises(ValueError, match="fill_quantity must be > 0"):
            update_order_fill(42, 0, Decimal("0.5500"))

    def test_fill_validates_fill_quantity_negative(self):
        """Test that negative fill_quantity raises ValueError."""
        with pytest.raises(ValueError, match="fill_quantity must be > 0"):
            update_order_fill(42, -1, Decimal("0.5500"))

    def test_fill_validates_decimal_price(self):
        """Test that float fill_price is rejected."""
        with pytest.raises(TypeError, match="fill_price must be Decimal"):
            update_order_fill(42, 5, 0.55)

    def test_fill_validates_decimal_fees(self):
        """Test that float fees are rejected."""
        with pytest.raises(TypeError, match="fees must be Decimal"):
            update_order_fill(42, 5, Decimal("0.5500"), 0.01)

    @patch("precog.database.crud_orders.get_cursor")
    def test_fill_terminal_state_guard(self, mock_get_cursor):
        """Test that fills on terminal orders are rejected."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_fill(42, 5, Decimal("0.5500"))

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "NOT IN ('filled', 'cancelled', 'expired')" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_fill_sets_filled_at_when_fully_filled(self, mock_get_cursor):
        """Test that filled_at is set when remaining reaches zero."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        update_order_fill(42, 10, Decimal("0.5500"))

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "filled_at" in execute_sql


# =============================================================================
# CANCEL ORDER TESTS
# =============================================================================


@pytest.mark.unit
class TestCancelOrder:
    """Unit tests for cancel_order function."""

    @patch("precog.database.crud_orders.get_cursor")
    def test_cancel_success(self, mock_get_cursor):
        """Test cancelling an open order returns True."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        result = cancel_order(42)

        assert result is True
        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "'cancelled'" in execute_sql
        assert "cancelled_at = NOW()" in execute_sql

    @patch("precog.database.crud_orders.get_cursor")
    def test_cancel_rejects_already_filled(self, mock_get_cursor):
        """Test that already-filled orders cannot be cancelled."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = cancel_order(42)

        assert result is False

    @patch("precog.database.crud_orders.get_cursor")
    def test_cancel_rejects_already_cancelled(self, mock_get_cursor):
        """Test that already-cancelled orders return False."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 0

        result = cancel_order(42)

        assert result is False

    @patch("precog.database.crud_orders.get_cursor")
    def test_cancel_only_allows_active_statuses(self, mock_get_cursor):
        """Test that WHERE clause only targets cancellable statuses."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.rowcount = 1

        cancel_order(42)

        execute_sql = mock_cursor.execute.call_args[0][0]
        assert "'submitted'" in execute_sql
        assert "'resting'" in execute_sql
        assert "'pending'" in execute_sql
        assert "'partial_fill'" in execute_sql


# =============================================================================
# GET OPEN ORDERS TESTS
# =============================================================================


@pytest.mark.unit
class TestGetOpenOrders:
    """Unit tests for get_open_orders function."""

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_filters_active_statuses(self, mock_fetch_all):
        """Test that query filters for active statuses only."""
        mock_fetch_all.return_value = []

        get_open_orders()

        query = mock_fetch_all.call_args[0][0]
        assert "'submitted'" in query
        assert "'resting'" in query
        assert "'pending'" in query
        assert "'partial_fill'" in query

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_strategy_filter(self, mock_fetch_all):
        """Test filtering by strategy_id."""
        mock_fetch_all.return_value = []

        get_open_orders(strategy_id=1)

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "strategy_id = %s" in query
        assert 1 in params

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_environment_filter(self, mock_fetch_all):
        """Test filtering by execution_environment."""
        mock_fetch_all.return_value = []

        get_open_orders(execution_environment="paper")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "execution_environment = %s" in query
        assert "paper" in params

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_market_filter(self, mock_fetch_all):
        """Test filtering by market_id."""
        mock_fetch_all.return_value = []

        get_open_orders(market_id=42)

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "market_id = %s" in query
        assert 42 in params

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_default_limit(self, mock_fetch_all):
        """Test that default limit of 100 is applied."""
        mock_fetch_all.return_value = []

        get_open_orders()

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_custom_limit(self, mock_fetch_all):
        """Test passing a custom limit."""
        mock_fetch_all.return_value = []

        get_open_orders(limit=25)

        params = mock_fetch_all.call_args[0][1]
        assert 25 in params

    @patch("precog.database.crud_orders.fetch_all")
    def test_get_open_orders_returns_list(self, mock_fetch_all):
        """Test that result is a list of dicts."""
        mock_fetch_all.return_value = [
            {"id": 1, "status": "submitted"},
            {"id": 2, "status": "resting"},
        ]

        result = get_open_orders()

        assert len(result) == 2
        assert result[0]["id"] == 1


# =============================================================================
# KALSHI STATUS MAP TESTS
# =============================================================================


@pytest.mark.unit
class TestKalshiStatusMap:
    """Unit tests for the KALSHI_STATUS_MAP constant (Glokta #4)."""

    def test_executed_maps_to_filled(self):
        """Test Kalshi 'executed' maps to our 'filled'."""
        assert KALSHI_STATUS_MAP["executed"] == "filled"

    def test_canceled_maps_to_cancelled(self):
        """Test Kalshi 'canceled' (one l) maps to our 'cancelled' (two l's)."""
        assert KALSHI_STATUS_MAP["canceled"] == "cancelled"

    def test_unknown_status_passthrough(self):
        """Test that unknown statuses pass through with .get() default."""
        result = KALSHI_STATUS_MAP.get("resting", "resting")
        assert result == "resting"
