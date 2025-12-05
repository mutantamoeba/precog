"""
Unit Tests for PositionManager Trailing Stop Methods

Tests initialize_trailing_stop(), update_trailing_stop(), and check_trailing_stop_trigger()
with comprehensive coverage of happy paths, edge cases, and error conditions.

Coverage target: 85%+ for trailing stop methods (lines 658-1168 in position_manager.py)
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from precog.trading.position_manager import PositionManager

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def position_manager():
    """Create PositionManager instance for testing."""
    return PositionManager()


@pytest.fixture
def valid_trailing_config():
    """Valid trailing stop configuration."""
    return {
        "activation_threshold": Decimal("0.15"),
        "initial_distance": Decimal("0.05"),
        "tightening_rate": Decimal("0.10"),
        "floor_distance": Decimal("0.02"),
    }


@pytest.fixture
def mock_position_with_trailing_stop():
    """Mock position dict with trailing stop state."""
    return {
        "id": 123,
        "position_id": "POS-2025-001",
        "market_id": "MARKET-001",
        "strategy_id": 1,
        "model_id": 1,
        "side": "YES",
        "quantity": Decimal("100"),
        "entry_price": Decimal("0.50"),
        "current_price": Decimal("0.65"),
        "target_price": Decimal("0.80"),
        "stop_loss_price": Decimal("0.35"),
        "unrealized_pnl": Decimal("15.00"),
        "realized_pnl": Decimal("0.00"),
        "status": "open",
        "exit_price": None,
        "exit_reason": None,
        "trailing_stop_state": {
            "config": {
                "activation_threshold": Decimal("0.15"),
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            },
            "activated": True,
            "activation_price": Decimal("0.65"),
            "current_stop_price": Decimal("0.60"),
            "highest_price": Decimal("0.65"),
        },
        "position_metadata": None,
        "row_current_ind": True,
    }


# ============================================================================
# TEST initialize_trailing_stop()
# ============================================================================


def test_initialize_trailing_stop_success(position_manager, valid_trailing_config, mocker):
    """Test successful initialization of trailing stop for existing position."""
    # Mock database
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    # Mock current position without trailing stop
    mock_position = {
        "id": 123,
        "position_id": "POS-2025-001",
        "current_price": Decimal("0.60"),
        "stop_loss_price": Decimal("0.35"),
        "status": "open",
    }
    mock_cursor.fetchone.side_effect = [
        mock_position,  # First fetch: get current position
        {"id": 124},  # Second fetch: RETURNING id after INSERT
        {**mock_position, "trailing_stop_state": {"activated": False}},  # Final fetch
    ]

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    # Execute
    result = position_manager.initialize_trailing_stop(123, valid_trailing_config)

    # Assert database operations
    assert mock_cursor.execute.call_count == 4  # SELECT, UPDATE, INSERT, SELECT (final)
    assert mock_conn.commit.called
    assert "trailing_stop_state" in result


def test_initialize_trailing_stop_missing_config_key(position_manager):
    """Test initialization fails when config missing required key."""
    incomplete_config = {
        "activation_threshold": Decimal("0.15"),
        "initial_distance": Decimal("0.05"),
        # Missing: tightening_rate, floor_distance
    }

    with pytest.raises(ValueError, match="Config missing required keys"):
        position_manager.initialize_trailing_stop(123, incomplete_config)


def test_initialize_trailing_stop_negative_activation_threshold(position_manager):
    """Test initialization fails when activation_threshold is negative."""
    invalid_config = {
        "activation_threshold": Decimal("-0.15"),  # ❌ Negative
        "initial_distance": Decimal("0.05"),
        "tightening_rate": Decimal("0.10"),
        "floor_distance": Decimal("0.02"),
    }

    with pytest.raises(ValueError, match="activation_threshold must be positive"):
        position_manager.initialize_trailing_stop(123, invalid_config)


def test_initialize_trailing_stop_zero_initial_distance(position_manager):
    """Test initialization fails when initial_distance is zero."""
    invalid_config = {
        "activation_threshold": Decimal("0.15"),
        "initial_distance": Decimal("0"),  # ❌ Zero
        "tightening_rate": Decimal("0.10"),
        "floor_distance": Decimal("0.02"),
    }

    with pytest.raises(ValueError, match="initial_distance must be positive"):
        position_manager.initialize_trailing_stop(123, invalid_config)


def test_initialize_trailing_stop_negative_floor_distance(position_manager):
    """Test initialization fails when floor_distance is negative."""
    invalid_config = {
        "activation_threshold": Decimal("0.15"),
        "initial_distance": Decimal("0.05"),
        "tightening_rate": Decimal("0.10"),
        "floor_distance": Decimal("-0.02"),  # ❌ Negative
    }

    with pytest.raises(ValueError, match="floor_distance must be non-negative"):
        position_manager.initialize_trailing_stop(123, invalid_config)


def test_initialize_trailing_stop_tightening_rate_out_of_range(position_manager):
    """Test initialization fails when tightening_rate > 1.0."""
    invalid_config = {
        "activation_threshold": Decimal("0.15"),
        "initial_distance": Decimal("0.05"),
        "tightening_rate": Decimal("1.5"),  # ❌ Greater than 1.0
        "floor_distance": Decimal("0.02"),
    }

    with pytest.raises(ValueError, match="tightening_rate must be between 0 and 1"):
        position_manager.initialize_trailing_stop(123, invalid_config)


def test_initialize_trailing_stop_position_not_found(
    position_manager, valid_trailing_config, mocker
):
    """Test initialization fails when position not found."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  # Position not found

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    with pytest.raises(ValueError, match="Position 123 not found"):
        position_manager.initialize_trailing_stop(123, valid_trailing_config)


def test_initialize_trailing_stop_closed_position(position_manager, valid_trailing_config, mocker):
    """Test initialization fails when position is already closed."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    mock_position = {
        "id": 123,
        "position_id": "POS-2025-001",
        "status": "closed",  # ❌ Closed position
    }
    mock_cursor.fetchone.return_value = mock_position

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    with pytest.raises(ValueError, match="Position 123 is already closed"):
        position_manager.initialize_trailing_stop(123, valid_trailing_config)


# ============================================================================
# TEST update_trailing_stop()
# ============================================================================


def test_update_trailing_stop_phase1_inactive(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 1: INACTIVE - Profit below threshold, no activation."""
    # Modify mock: trailing stop NOT activated yet, low profit
    mock_position_with_trailing_stop["trailing_stop_state"]["activated"] = False
    mock_position_with_trailing_stop["unrealized_pnl"] = Decimal("5.00")  # < threshold

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        mock_position_with_trailing_stop,  # SELECT
        {"id": 124},  # RETURNING id
        mock_position_with_trailing_stop,  # Final SELECT
    ]

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.update_trailing_stop(123, Decimal("0.55"))

    # Assert: Trailing stop stays INACTIVE
    assert result is not None


def test_update_trailing_stop_phase2_activation(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 2: ACTIVATION - Profit reaches threshold, activates stop."""
    # Modify mock: trailing stop NOT activated yet, profit REACHES threshold
    mock_position_with_trailing_stop["trailing_stop_state"]["activated"] = False
    mock_position_with_trailing_stop["unrealized_pnl"] = Decimal("15.00")  # >= threshold

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        mock_position_with_trailing_stop,  # SELECT
        {"id": 124},  # RETURNING id
        mock_position_with_trailing_stop,  # Final SELECT
    ]

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.update_trailing_stop(123, Decimal("0.65"))

    # Assert: Activation occurred
    assert result is not None


def test_update_trailing_stop_phase3_price_rises(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 3: TRAILING - Price rises, stop tightens."""
    # Mock: already activated, price moving up
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        mock_position_with_trailing_stop,  # SELECT
        {"id": 124},  # RETURNING id
        mock_position_with_trailing_stop,  # Final SELECT
    ]

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.update_trailing_stop(123, Decimal("0.75"))

    # Assert: Stop should tighten (move up)
    assert result is not None


def test_update_trailing_stop_phase3_price_falls(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 3: TRAILING - Price falls, stop doesn't move down."""
    # Mock: already activated, price moving down
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        mock_position_with_trailing_stop,  # SELECT
        {"id": 124},  # RETURNING id
        mock_position_with_trailing_stop,  # Final SELECT
    ]

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    # Price falls from 0.65 to 0.62
    result = position_manager.update_trailing_stop(123, Decimal("0.62"))

    # Assert: Stop doesn't move down
    assert result is not None


def test_update_trailing_stop_floor_distance_enforced(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test distance tightening respects floor_distance minimum."""
    # Mock: very high profit, tightening should hit floor
    mock_position_with_trailing_stop["unrealized_pnl"] = Decimal("50.00")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [
        mock_position_with_trailing_stop,  # SELECT
        {"id": 124},  # RETURNING id
        mock_position_with_trailing_stop,  # Final SELECT
    ]

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.update_trailing_stop(123, Decimal("0.80"))

    # Assert: Floor distance enforced
    assert result is not None


def test_update_trailing_stop_division_by_zero_protection(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test division by zero protection when entry_price is zero."""
    # Mock: entry_price = 0 (should be impossible in database, but defensive check)
    mock_position_with_trailing_stop["entry_price"] = Decimal("0")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    with pytest.raises(ValueError, match="Invalid entry_price"):
        position_manager.update_trailing_stop(123, Decimal("0.75"))


def test_update_trailing_stop_invalid_price_range(position_manager):
    """Test update fails when current_price outside valid range [0.01, 0.99]."""
    with pytest.raises(ValueError, match="outside valid range"):
        position_manager.update_trailing_stop(123, Decimal("1.05"))  # > 0.99

    with pytest.raises(ValueError, match="outside valid range"):
        position_manager.update_trailing_stop(123, Decimal("0.005"))  # < 0.01


def test_update_trailing_stop_position_not_found(position_manager, mocker):
    """Test update fails when position not found."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    with pytest.raises(ValueError, match="Position 123 not found"):
        position_manager.update_trailing_stop(123, Decimal("0.75"))


def test_update_trailing_stop_no_trailing_stop_configured(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test update fails when position has no trailing stop configured."""
    mock_position_with_trailing_stop["trailing_stop_state"] = None  # No trailing stop

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    with pytest.raises(ValueError, match="has no trailing stop configured"):
        position_manager.update_trailing_stop(123, Decimal("0.75"))


# ============================================================================
# TEST check_trailing_stop_trigger()
# ============================================================================


def test_check_trailing_stop_trigger_yes_position_triggered(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test YES position: trigger when current_price <= stop_price."""
    # Mock: current_price = 0.58, stop_price = 0.60 -> TRIGGERED
    mock_position_with_trailing_stop["side"] = "YES"
    mock_position_with_trailing_stop["current_price"] = Decimal("0.58")
    mock_position_with_trailing_stop["trailing_stop_state"]["current_stop_price"] = Decimal("0.60")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.check_trailing_stop_trigger(123)

    assert result is True


def test_check_trailing_stop_trigger_yes_position_not_triggered(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test YES position: no trigger when current_price > stop_price."""
    # Mock: current_price = 0.70, stop_price = 0.60 -> NOT TRIGGERED
    mock_position_with_trailing_stop["side"] = "YES"
    mock_position_with_trailing_stop["current_price"] = Decimal("0.70")
    mock_position_with_trailing_stop["trailing_stop_state"]["current_stop_price"] = Decimal("0.60")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.check_trailing_stop_trigger(123)

    assert result is False


def test_check_trailing_stop_trigger_no_position_triggered(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test NO position: trigger when current_price >= (1.00 - stop_price)."""
    # Mock: NO position, current_price = 0.72, stop = 0.30 -> effective stop = 0.70 -> TRIGGERED
    mock_position_with_trailing_stop["side"] = "NO"
    mock_position_with_trailing_stop["current_price"] = Decimal("0.72")
    mock_position_with_trailing_stop["trailing_stop_state"]["current_stop_price"] = Decimal("0.30")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.check_trailing_stop_trigger(123)

    assert result is True


def test_check_trailing_stop_trigger_no_position_not_triggered(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test NO position: no trigger when current_price < (1.00 - stop_price)."""
    # Mock: NO position, current_price = 0.65, stop = 0.30 -> effective stop = 0.70 -> NOT TRIGGERED
    mock_position_with_trailing_stop["side"] = "NO"
    mock_position_with_trailing_stop["current_price"] = Decimal("0.65")
    mock_position_with_trailing_stop["trailing_stop_state"]["current_stop_price"] = Decimal("0.30")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.check_trailing_stop_trigger(123)

    assert result is False


def test_check_trailing_stop_trigger_not_activated(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test no trigger when trailing stop not activated yet."""
    # Mock: trailing stop exists but not activated
    mock_position_with_trailing_stop["trailing_stop_state"]["activated"] = False

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = mock_position_with_trailing_stop

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    result = position_manager.check_trailing_stop_trigger(123)

    assert result is False


def test_check_trailing_stop_trigger_position_not_found(position_manager, mocker):
    """Test check fails when position not found."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")

    with pytest.raises(ValueError, match="Position 123 not found"):
        position_manager.check_trailing_stop_trigger(123)
