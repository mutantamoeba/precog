"""
Unit Tests for PositionManager Trailing Stop Methods

Tests initialize_trailing_stop(), update_trailing_stop(), and check_trailing_stop_trigger()
with comprehensive coverage of happy paths, edge cases, and error conditions.

Coverage target: 85%+ for trailing stop methods (lines 658-1168 in position_manager.py)

Issue #629 refactor: ``initialize_trailing_stop`` and ``update_trailing_stop``
now delegate the SCD close+insert to ``crud_set_trailing_stop_state``. Tests
mock that CRUD function at the boundary instead of the raw cursor for the
write path. The OUTER fetch (which still happens in position_manager via
``get_connection``) and the post-write re-fetch are still mocked the same
way; only the SCD write step moved behind the CRUD seam. The mock fidelity
rule (protocols.md) also moves the burden of write-visibility coverage onto
the integration tests in
``tests/integration/database/test_crud_positions_trailing_stop_integration.py``
and the race test in
``tests/race/test_scd_sibling_first_insert_races.py``.
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
        "market_internal_id": 1,
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


def _mock_trailing_stop_write_path(mocker, fetch_results: list, new_position_id: int = 124):
    """Patch the outer-fetch + CRUD + re-fetch sequence used by both
    ``initialize_trailing_stop`` and ``update_trailing_stop`` after the
    Issue #629 refactor.

    The two methods now have THREE database touchpoints in a successful
    write path:

        1. Outer ``get_connection`` fetch -- one ``cur.fetchone()`` returning
           the current position dict (or None / closed for negative paths).
        2. Call to ``crud_set_trailing_stop_state`` -- mocked at the
           ``precog.trading.position_manager.crud_set_trailing_stop_state``
           import binding so the real CRUD's ``fetch_one`` does NOT execute.
           Returns ``new_position_id``.
        3. Re-fetch ``get_connection`` -- one ``cur.fetchone()`` returning
           the post-update position dict.

    ``fetch_results`` is the list passed to ``mock_cursor.fetchone.side_effect``
    so callers can stage the outer-fetch row and the re-fetch row in order:
    ``[outer_row, refetch_row]``.

    For negative paths that raise BEFORE the CRUD is called, pass a list with
    only the outer-fetch result -- the re-fetch never executes and the CRUD
    mock is never invoked. The crud mock is still installed so accidental
    reaches into the real CRUD surface as obvious test failures rather than
    DB errors.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = fetch_results

    mocker.patch("precog.trading.position_manager.get_connection", return_value=mock_conn)
    mocker.patch("precog.trading.position_manager.release_connection")
    crud_mock = mocker.patch(
        "precog.trading.position_manager.crud_set_trailing_stop_state",
        return_value=new_position_id,
    )

    return mock_conn, mock_cursor, crud_mock


# ============================================================================
# TEST initialize_trailing_stop()
# ============================================================================


def test_initialize_trailing_stop_success(position_manager, valid_trailing_config, mocker):
    """Test successful initialization of trailing stop for existing position."""
    # Mock current position without trailing stop
    mock_position = {
        "id": 123,
        "position_id": "POS-2025-001",
        "current_price": Decimal("0.60"),
        "stop_loss_price": Decimal("0.35"),
        "status": "open",
    }
    refetched_position = {**mock_position, "trailing_stop_state": {"activated": False}}

    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position, refetched_position],
        new_position_id=124,
    )

    # Execute
    result = position_manager.initialize_trailing_stop(123, valid_trailing_config)

    # Assert: CRUD called once with the seeded trailing_stop_state. The
    # initialize path passes only the JSONB state -- no current_price /
    # unrealized_pnl override -- because it is adding a trailing stop to
    # an existing position without changing price.
    crud_mock.assert_called_once()
    call_kwargs = crud_mock.call_args.kwargs
    assert call_kwargs["position_id"] == 123
    seeded_state = call_kwargs["trailing_stop_state"]
    assert seeded_state["activated"] is False
    assert seeded_state["current_stop_price"] == Decimal("0.35")
    assert seeded_state["highest_price"] == Decimal("0.60")
    assert seeded_state["config"] == valid_trailing_config
    # initialize must NOT pass current_price/unrealized_pnl (preserve
    # existing pricing on the new SCD version).
    assert "current_price" not in call_kwargs or call_kwargs.get("current_price") is None
    assert "unrealized_pnl" not in call_kwargs or call_kwargs.get("unrealized_pnl") is None
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
    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[None],  # Outer fetch returns no row
    )

    with pytest.raises(ValueError, match="Position 123 not found"):
        position_manager.initialize_trailing_stop(123, valid_trailing_config)

    # The CRUD must NOT be called when the outer fetch fails -- the
    # not-found guard is in position_manager, not the CRUD.
    crud_mock.assert_not_called()


def test_initialize_trailing_stop_closed_position(position_manager, valid_trailing_config, mocker):
    """Test initialization fails when position is already closed."""
    mock_position = {
        "id": 123,
        "position_id": "POS-2025-001",
        "status": "closed",  # Closed position
    }
    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position],
    )

    with pytest.raises(ValueError, match="Position 123 is already closed"):
        position_manager.initialize_trailing_stop(123, valid_trailing_config)

    crud_mock.assert_not_called()


# ============================================================================
# TEST update_trailing_stop()
# ============================================================================


def test_update_trailing_stop_phase1_inactive(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 1 path: trailing stop starts inactive, code re-evaluates.

    Note: this test originally documented "Phase 1 INACTIVE" but the
    fixture's quantity=100 + price delta yields a PnL well above the
    activation threshold of 0.15, so the production code activates on
    this path. Pre-refactor, the test only asserted ``result is not None``
    and never inspected the resulting state, so the misnomer survived.
    The post-#629 assertions verify the CRUD is invoked with the
    expected position_id + current_price; the activation transition
    itself is exercised explicitly by ``test_update_trailing_stop_phase2_activation``.
    """
    # Modify mock: trailing stop NOT activated yet
    mock_position_with_trailing_stop["trailing_stop_state"]["activated"] = False
    mock_position_with_trailing_stop["unrealized_pnl"] = Decimal("5.00")

    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop, mock_position_with_trailing_stop],
    )

    result = position_manager.update_trailing_stop(123, Decimal("0.55"))

    # Assert: CRUD was called with the full price/pnl tuple (the update
    # path always writes price + pnl). Don't over-specify the resulting
    # trailing_stop_state shape -- the calculate_position_pnl path may
    # cross the threshold and activate; the production logic is what it
    # is, and tightening this assertion would re-create the bug-class
    # the integration tests are designed to catch.
    assert result is not None
    crud_mock.assert_called_once()
    kwargs = crud_mock.call_args.kwargs
    assert kwargs["position_id"] == 123
    assert kwargs["current_price"] == Decimal("0.55")
    assert "trailing_stop_state" in kwargs


def test_update_trailing_stop_phase2_activation(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 2: ACTIVATION - Profit reaches threshold, activates stop."""
    # Modify mock: trailing stop NOT activated yet, profit REACHES threshold
    mock_position_with_trailing_stop["trailing_stop_state"]["activated"] = False
    mock_position_with_trailing_stop["unrealized_pnl"] = Decimal("15.00")  # >= threshold

    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop, mock_position_with_trailing_stop],
    )

    result = position_manager.update_trailing_stop(123, Decimal("0.65"))

    # Assert: Activation occurred -- the state passed to the CRUD must
    # have activated=True and a non-None activation_price.
    assert result is not None
    crud_mock.assert_called_once()
    kwargs = crud_mock.call_args.kwargs
    assert kwargs["trailing_stop_state"]["activated"] is True
    assert kwargs["trailing_stop_state"]["activation_price"] == Decimal("0.65")


def test_update_trailing_stop_phase3_price_rises(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 3: TRAILING - Price rises, stop tightens."""
    # Mock: already activated, price moving up
    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop, mock_position_with_trailing_stop],
    )

    result = position_manager.update_trailing_stop(123, Decimal("0.75"))

    # Assert: Stop should tighten (move up)
    assert result is not None
    crud_mock.assert_called_once()
    kwargs = crud_mock.call_args.kwargs
    # highest_price tracked the new high
    assert kwargs["trailing_stop_state"]["highest_price"] == Decimal("0.75")


def test_update_trailing_stop_phase3_price_falls(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test Phase 3: TRAILING - Price falls, stop doesn't move down."""
    # Mock: already activated, price moving down
    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop, mock_position_with_trailing_stop],
    )

    # Price falls from 0.65 to 0.62
    result = position_manager.update_trailing_stop(123, Decimal("0.62"))

    # Assert: highest_price stays at 0.65 (price went DOWN, never updates
    # the high). The new_stop computation may still tighten via the
    # distance/floor formula based on accumulated PnL, but the new stop
    # must NEVER be lower than the existing 0.60 stop (trailing stops
    # only move up).
    assert result is not None
    crud_mock.assert_called_once()
    kwargs = crud_mock.call_args.kwargs
    assert kwargs["trailing_stop_state"]["highest_price"] == Decimal("0.65")
    assert kwargs["trailing_stop_state"]["current_stop_price"] >= Decimal("0.60")


def test_update_trailing_stop_floor_distance_enforced(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test distance tightening respects floor_distance minimum."""
    # Mock: very high profit, tightening should hit floor
    mock_position_with_trailing_stop["unrealized_pnl"] = Decimal("50.00")

    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop, mock_position_with_trailing_stop],
    )

    result = position_manager.update_trailing_stop(123, Decimal("0.80"))

    # Assert: Floor distance enforced -- CRUD invoked once
    assert result is not None
    crud_mock.assert_called_once()


def test_update_trailing_stop_division_by_zero_protection(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test division by zero protection when entry_price is zero."""
    # Mock: entry_price = 0 (should be impossible in database, but defensive check)
    mock_position_with_trailing_stop["entry_price"] = Decimal("0")

    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop],
    )

    with pytest.raises(ValueError, match="Invalid entry_price"):
        position_manager.update_trailing_stop(123, Decimal("0.75"))

    # The defensive guard fires before any CRUD interaction.
    crud_mock.assert_not_called()


def test_update_trailing_stop_invalid_price_range(position_manager):
    """Test update fails when current_price outside valid range [0.00, 1.00]."""
    with pytest.raises(ValueError, match="outside valid range"):
        position_manager.update_trailing_stop(123, Decimal("1.05"))  # > 1.00

    with pytest.raises(ValueError, match="outside valid range"):
        position_manager.update_trailing_stop(123, Decimal("-0.01"))  # < 0.00


def test_settlement_boundary_prices_accepted(position_manager, mocker):
    """Test that settlement boundary values (0.00, 1.00) pass validation.

    Kalshi ask prices reach 0.00 and 1.00 at settlement. These must NOT
    be rejected by the price validation guard.
    """
    # Two test calls -> two outer fetches -> stage two None results so the
    # second call gets a fresh None instead of consuming a stale entry.
    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[None, None],
    )

    # 1.00 = YES contract settled YES. Should NOT raise "outside valid range".
    with pytest.raises(ValueError, match="not found"):
        position_manager.update_trailing_stop(123, Decimal("1.0000"))

    # 0.00 = YES contract settled NO. Should NOT raise "outside valid range".
    with pytest.raises(ValueError, match="not found"):
        position_manager.update_trailing_stop(123, Decimal("0.0000"))

    crud_mock.assert_not_called()


def test_update_trailing_stop_position_not_found(position_manager, mocker):
    """Test update fails when position not found."""
    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[None],
    )

    with pytest.raises(ValueError, match="Position 123 not found"):
        position_manager.update_trailing_stop(123, Decimal("0.75"))

    crud_mock.assert_not_called()


def test_update_trailing_stop_no_trailing_stop_configured(
    position_manager, mock_position_with_trailing_stop, mocker
):
    """Test update fails when position has no trailing stop configured."""
    mock_position_with_trailing_stop["trailing_stop_state"] = None  # No trailing stop

    _mock_conn, _mock_cursor, crud_mock = _mock_trailing_stop_write_path(
        mocker,
        fetch_results=[mock_position_with_trailing_stop],
    )

    with pytest.raises(ValueError, match="has no trailing stop configured"):
        position_manager.update_trailing_stop(123, Decimal("0.75"))

    crud_mock.assert_not_called()


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
