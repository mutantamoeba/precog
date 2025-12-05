"""
Unit tests for Position Manager.

Tests the PositionManager class which manages position lifecycle from entry
to exit with risk management and P&L tracking.

Reference: docs/testing/PHASE_1.5_TEST_PLAN_V1.0.md
Related Requirements: REQ-RISK-001, REQ-RISK-002, REQ-RISK-003, REQ-RISK-004, REQ-EXEC-001
Related ADRs: ADR-015, ADR-089 (SCD Type 2 dual-key schema)
"""

import uuid
from decimal import Decimal

import pytest

from precog.database.connection import get_connection, release_connection
from precog.database.crud_operations import create_strategy
from precog.trading.position_manager import (
    InsufficientMarginError,
    PositionManager,
)

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def position_params(db_cursor, clean_test_data):
    """Fixture providing valid position parameters with required FKs.

    Creates strategy and model records that positions can reference.

    Returns:
        Dictionary with valid position parameters using Decimal types

    Educational Note:
        - Creates real FK dependencies (strategy_id, model_id) in database
        - All prices/probabilities use Decimal (Pattern 1)
        - Follows Kalshi pricing cheat sheet ([0.01, 0.99] range)

    Example:
        >>> params = position_params
        >>> params["entry_price"]
        Decimal('0.4975')
    """
    # Generate unique names to avoid UNIQUE constraint violations across tests
    unique_suffix = str(uuid.uuid4())[:8]

    # Create strategy (required FK for positions)
    strategy_id = create_strategy(
        strategy_name=f"test_strategy_{unique_suffix}",
        strategy_version="v1.0",
        strategy_type="value",  # HOW you trade (trading methodology)
        subcategory="nfl",  # Maps to 'domain' column (market type)
        config={"min_edge": Decimal("0.05")},
    )

    # Create model (required FK for positions)
    # Note: Using direct SQL since create_model doesn't exist in crud_operations yet
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO probability_models (
                    model_name, model_version, model_class, domain, config, status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING model_id
                """,
                (
                    f"test_model_{unique_suffix}",
                    "v1.0",
                    "elo",
                    "nfl",
                    '{"k_factor": "32.0"}',
                    "active",
                ),
            )
            model_id = cur.fetchone()[0]

            # Create test markets (required for get_current_positions() JOIN)
            # Multiple markets needed for filtering tests
            markets_to_create = [
                ("MKT-NFL-TEST-001", "MKT-TEST-001", "Test Market: KC to beat BUF"),
                ("MKT-NFL-001", "MKT-001", "Test Market 1"),
                ("MKT-NFL-002", "MKT-002", "Test Market 2"),
                ("MKT-NFL-003", "MKT-003", "Test Market 3"),
            ]

            for market_id, external_id, title in markets_to_create:
                cur.execute(
                    """
                    INSERT INTO markets (
                        market_id, platform_id, event_id, external_id, ticker, title,
                        yes_price, no_price, market_type, status, volume, open_interest, row_current_ind
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        market_id,
                        "test_platform",
                        "TEST-EVT-NFL-KC-BUF",
                        external_id,
                        market_id,
                        title,
                        Decimal("0.5200"),
                        Decimal("0.4800"),
                        "binary",
                        "open",
                        1000,
                        500,
                        True,
                    ),
                )
            conn.commit()
    finally:
        release_connection(conn)

    return {
        "market_id": "MKT-NFL-TEST-001",
        "strategy_id": strategy_id,
        "model_id": model_id,
        "side": "YES",
        "quantity": 10,
        "entry_price": Decimal("0.4975"),  # YES @ 49.75%
        "target_price": Decimal("0.7500"),  # Target @ 75%
        "stop_loss_price": Decimal("0.3500"),  # Stop @ 35%
        "available_margin": Decimal("1000.00"),  # Sufficient margin
    }


# Database fixtures imported from conftest.py:
# - db_pool: Session-scoped connection pool
# - db_cursor: Function-scoped cursor with automatic rollback
# - clean_test_data: Cleans test data before/after each test
#
# Educational Note (ADR-088):
#   - ❌ FORBIDDEN: Mocking get_connection(), database, config, logging
#   - ✅ REQUIRED: Use REAL infrastructure fixtures
#   - Position Manager wraps CRUD operations, must test with real DB


# ============================================================================
# OPEN POSITION TESTS
# ============================================================================


def test_open_position_success(db_pool, db_cursor, clean_test_data, position_params):
    """Test opening position with valid parameters and sufficient margin.

    Note:
        db_pool fixture ensures real database infrastructure is used
        (Pattern 13 - no mocking connections in integration tests).

    Educational Note:
        - Required margin for YES @ 0.4975, qty 10:
          margin = 10 * (1.00 - 0.4975) = 10 * 0.5025 = $5.0250
        - Available margin ($1000) >> required ($5.0250) ✅
        - Returns dict with surrogate id (int) and business key (str 'POS-{id}')
    """
    manager = PositionManager()

    position = manager.open_position(**position_params)

    # Verify returned position has correct structure
    assert isinstance(position, dict)
    assert "id" in position  # Surrogate key
    assert "position_id" in position  # Business key
    assert isinstance(position["id"], int)
    assert position["position_id"].startswith("POS-")  # Format: POS-{id}

    # Verify position data
    assert position["market_id"] == position_params["market_id"]
    assert position["strategy_id"] == position_params["strategy_id"]
    assert position["model_id"] == position_params["model_id"]
    assert position["side"] == position_params["side"]
    assert position["quantity"] == position_params["quantity"]
    assert position["entry_price"] == position_params["entry_price"]
    assert position["status"] == "open"
    assert position["row_current_ind"] is True  # SCD Type 2 current version

    # Verify risk parameters
    assert position["target_price"] == position_params["target_price"]
    assert position["stop_loss_price"] == position_params["stop_loss_price"]


def test_open_position_insufficient_margin_yes(db_cursor, clean_test_data, position_params):
    """Test opening YES position with insufficient margin raises error.

    Educational Note:
        - YES position margin = quantity * (1.00 - entry_price)
        - Entry $0.75, qty 10: margin = 10 * 0.25 = $2.50
        - Available $1.00 < required $2.50 -> should FAIL
    """
    manager = PositionManager()

    # Modify params: YES @ 0.75, available margin too low
    position_params["entry_price"] = Decimal("0.7500")
    position_params["available_margin"] = Decimal("1.00")  # Need $2.50, have $1.00

    with pytest.raises(InsufficientMarginError, match=r"Required margin.*available"):
        manager.open_position(**position_params)


def test_open_position_insufficient_margin_no(db_cursor, clean_test_data, position_params):
    """Test opening NO position with insufficient margin raises error.

    Educational Note:
        - NO position margin = quantity * entry_price
        - Entry $0.25, qty 10: margin = 10 * 0.25 = $2.50
        - Available $1.00 < required $2.50 -> should FAIL
    """
    manager = PositionManager()

    # Modify params: NO @ 0.25, available margin too low
    position_params["side"] = "NO"
    position_params["entry_price"] = Decimal("0.2500")
    position_params["available_margin"] = Decimal("1.00")  # Need $2.50, have $1.00

    with pytest.raises(InsufficientMarginError, match=r"Required margin.*available"):
        manager.open_position(**position_params)


def test_open_position_invalid_price_too_low(db_cursor, clean_test_data, position_params):
    """Test opening position with entry_price < 0.01 raises ValueError.

    Educational Note:
        - Kalshi contract prices must be in range [0.01, 0.99]
        - Prices outside this range are invalid (settlement always $0.00 or $1.00)
    """
    manager = PositionManager()

    position_params["entry_price"] = Decimal("0.0050")  # Below minimum (0.01)

    with pytest.raises(ValueError, match="outside valid range"):
        manager.open_position(**position_params)


def test_open_position_invalid_price_too_high(db_cursor, clean_test_data, position_params):
    """Test opening position with entry_price > 0.99 raises ValueError."""
    manager = PositionManager()

    position_params["entry_price"] = Decimal("0.9950")  # Above maximum (0.99)

    with pytest.raises(ValueError, match="outside valid range"):
        manager.open_position(**position_params)


def test_open_position_invalid_side(db_cursor, clean_test_data, position_params):
    """Test opening position with invalid side raises ValueError.

    Educational Note:
        - Only 'YES' and 'NO' sides are valid for Kalshi binary markets
        - Other values like 'BUY', 'SELL', 'LONG' are not valid
    """
    manager = PositionManager()

    position_params["side"] = "LONG"  # Invalid, should be 'YES' or 'NO'

    with pytest.raises(ValueError, match="Invalid side"):
        manager.open_position(**position_params)


# ============================================================================
# UPDATE POSITION TESTS
# ============================================================================


def test_update_position_creates_new_version(db_cursor, clean_test_data, position_params):
    """Test updating position price creates new SCD Type 2 version.

    Educational Note:
        - SCD Type 2 pattern: UPDATE creates NEW row, marks old row non-current
        - Old version: row_current_ind = FALSE (archived)
        - New version: row_current_ind = TRUE (current)
        - Surrogate id CHANGES (old id -> new id)
        - Business key STAYS SAME (position_id copied to new version)
    """
    manager = PositionManager()

    # Open position
    position = manager.open_position(**position_params)
    old_id = position["id"]
    business_key = position["position_id"]

    # Update price (creates new version)
    updated_position = manager.update_position(
        position_id=old_id,  # Use old surrogate id
        current_price=Decimal("0.5200"),  # Price went up
    )

    # Verify new version created
    assert updated_position["id"] != old_id  # NEW surrogate id
    assert updated_position["position_id"] == business_key  # SAME business key
    assert updated_position["current_price"] == Decimal("0.5200")
    assert updated_position["row_current_ind"] is True

    # Verify unrealized P&L calculated
    # YES position: P&L = quantity * (current_price - entry_price)
    # P&L = 10 * (0.5200 - 0.4975) = 10 * 0.0225 = $0.2250
    expected_pnl = Decimal("0.2250")
    assert updated_position["unrealized_pnl"] == expected_pnl


def test_update_position_multiple_updates(db_cursor, clean_test_data, position_params):
    """Test multiple price updates create correct version history.

    Educational Note:
        - Each update creates NEW version with NEW surrogate id
        - Only latest version has row_current_ind = TRUE
        - All old versions have row_current_ind = FALSE
        - Business key stays constant across all versions
    """
    manager = PositionManager()

    # Open position
    position = manager.open_position(**position_params)
    business_key = position["position_id"]

    # Update 1: Price goes up to 0.52
    v1 = manager.update_position(position_id=position["id"], current_price=Decimal("0.5200"))
    assert v1["position_id"] == business_key

    # Update 2: Price goes up to 0.55
    v2 = manager.update_position(position_id=v1["id"], current_price=Decimal("0.5500"))
    assert v2["position_id"] == business_key
    assert v2["id"] != v1["id"]  # Different surrogate ids

    # Update 3: Price goes down to 0.50
    v3 = manager.update_position(position_id=v2["id"], current_price=Decimal("0.5000"))
    assert v3["position_id"] == business_key
    assert v3["id"] != v2["id"]  # Different surrogate ids

    # Verify final P&L
    # P&L = 10 * (0.5000 - 0.4975) = 10 * 0.0025 = $0.0250
    assert v3["unrealized_pnl"] == Decimal("0.0250")


def test_update_position_invalid_price(db_cursor, clean_test_data, position_params):
    """Test updating position with invalid price raises ValueError."""
    manager = PositionManager()

    position = manager.open_position(**position_params)

    # Try to update with price > 0.99
    with pytest.raises(ValueError, match="outside valid range"):
        manager.update_position(position_id=position["id"], current_price=Decimal("1.0000"))


# ============================================================================
# CLOSE POSITION TESTS
# ============================================================================


def test_close_position_profit_target(db_cursor, clean_test_data, position_params):
    """Test closing position at profit target calculates realized P&L.

    Educational Note:
        - Closing creates final SCD Type 2 version with status='closed'
        - realized_pnl populated (was NULL for open positions)
        - unrealized_pnl becomes NULL (position no longer has unrealized P&L)
        - exit_reason tracked for performance analysis
    """
    manager = PositionManager()

    # Open position
    position = manager.open_position(**position_params)

    # Close at profit target
    closed_position = manager.close_position(
        position_id=position["id"],
        exit_price=Decimal("0.7500"),  # Hit target
        exit_reason="profit_target",
    )

    # Verify closed state
    assert closed_position["status"] == "closed"
    assert closed_position["position_id"] == position["position_id"]  # Same business key
    assert closed_position["id"] != position["id"]  # Different surrogate id

    # Verify realized P&L
    # YES position: P&L = quantity * (exit_price - entry_price)
    # P&L = 10 * (0.7500 - 0.4975) = 10 * 0.2525 = $2.5250
    assert closed_position["realized_pnl"] == Decimal("2.5250")
    assert closed_position["unrealized_pnl"] is None  # No longer unrealized

    # Verify exit details
    assert closed_position["current_price"] == Decimal("0.7500")
    # Note: exit_reason not stored in positions table, recorded in position_exits table


def test_close_position_stop_loss(db_cursor, clean_test_data, position_params):
    """Test closing position at stop loss calculates negative P&L."""
    manager = PositionManager()

    # Open position
    position = manager.open_position(**position_params)

    # Close at stop loss
    closed_position = manager.close_position(
        position_id=position["id"],
        exit_price=Decimal("0.3500"),  # Hit stop
        exit_reason="stop_loss",
    )

    # Verify realized P&L (loss)
    # YES position: P&L = quantity * (exit_price - entry_price)
    # P&L = 10 * (0.3500 - 0.4975) = 10 * (-0.1475) = -$1.4750
    assert closed_position["realized_pnl"] == Decimal("-1.4750")
    assert closed_position["status"] == "closed"


def test_close_position_invalid_price(db_cursor, clean_test_data, position_params):
    """Test closing position with invalid exit price raises ValueError."""
    manager = PositionManager()

    position = manager.open_position(**position_params)

    # Try to close with price < 0.01
    with pytest.raises(ValueError, match="outside valid range"):
        manager.close_position(
            position_id=position["id"],
            exit_price=Decimal("0.0050"),
            exit_reason="manual",
        )


# ============================================================================
# GET OPEN POSITIONS TESTS
# ============================================================================


def test_get_open_positions_all(db_cursor, clean_test_data, position_params):
    """Test retrieving all open positions returns only current versions.

    Educational Note:
        - get_open_positions() automatically filters row_current_ind = TRUE
        - Only returns positions with status='open'
        - Excludes closed positions and historical versions
    """
    manager = PositionManager()

    # Open 3 positions
    manager.open_position(**position_params)
    manager.open_position(**{**position_params, "market_id": "MKT-NFL-002"})
    manager.open_position(**{**position_params, "market_id": "MKT-NFL-003"})

    # Get all open positions
    positions = manager.get_open_positions()

    assert len(positions) == 3
    assert all(p["status"] == "open" for p in positions)
    assert all(p["row_current_ind"] is True for p in positions)


def test_get_open_positions_filter_by_market(db_cursor, clean_test_data, position_params):
    """Test filtering open positions by market_id."""
    manager = PositionManager()

    # Open positions in different markets
    manager.open_position(**{**position_params, "market_id": "MKT-NFL-001"})
    manager.open_position(**{**position_params, "market_id": "MKT-NFL-002"})
    manager.open_position(**{**position_params, "market_id": "MKT-NFL-001"})

    # Filter by market
    positions = manager.get_open_positions(market_id="MKT-NFL-001")

    assert len(positions) == 2
    assert all(p["market_id"] == "MKT-NFL-001" for p in positions)


def test_get_open_positions_filter_by_strategy(db_cursor, clean_test_data, position_params):
    """Test filtering open positions by strategy_id."""
    manager = PositionManager()

    # Create second strategy
    strategy_id_2 = create_strategy(
        strategy_name="test_strategy_2",
        strategy_version="v1.0",
        strategy_type="arbitrage",
        subcategory="nfl",
        config={"spread_threshold": Decimal("0.02")},
    )

    # Open positions with different strategies
    manager.open_position(**position_params)  # strategy_id from fixture
    manager.open_position(**{**position_params, "strategy_id": strategy_id_2})
    manager.open_position(**position_params)  # strategy_id from fixture

    # Filter by strategy
    positions = manager.get_open_positions(strategy_id=position_params["strategy_id"])

    assert len(positions) == 2
    assert all(p["strategy_id"] == position_params["strategy_id"] for p in positions)


def test_get_open_positions_excludes_closed(db_cursor, clean_test_data, position_params):
    """Test get_open_positions excludes closed positions.

    Educational Note:
        - Closed positions have status='closed', should NOT be returned
        - Only status='open' + row_current_ind=TRUE should be included
    """
    manager = PositionManager()

    # Open 3 positions
    p1 = manager.open_position(**position_params)
    p2 = manager.open_position(**{**position_params, "market_id": "MKT-NFL-002"})
    p3 = manager.open_position(**{**position_params, "market_id": "MKT-NFL-003"})

    # Close one position
    manager.close_position(
        position_id=p2["id"],
        exit_price=Decimal("0.5500"),
        exit_reason="manual",
    )

    # Get open positions (should exclude closed p2)
    positions = manager.get_open_positions()

    assert len(positions) == 2
    position_ids = [p["id"] for p in positions]
    assert p1["id"] in position_ids
    assert p3["id"] in position_ids
    assert p2["id"] not in position_ids  # Closed position excluded


# ============================================================================
# P&L CALCULATION TESTS
# ============================================================================


def test_calculate_pnl_yes_profit(db_cursor, clean_test_data):
    """Test P&L calculation for YES position with profit.

    Educational Note:
        - YES position profits when price goes UP
        - Formula: P&L = quantity * (current_price - entry_price)
        - Example: Entry $0.50, Current $0.75, Qty 10
          P&L = 10 * ($0.75 - $0.50) = $2.50
    """
    manager = PositionManager()

    pnl = manager.calculate_position_pnl(
        entry_price=Decimal("0.5000"),
        current_price=Decimal("0.7500"),
        quantity=10,
        side="YES",
    )

    assert pnl == Decimal("2.5000")  # $2.50 profit


def test_calculate_pnl_yes_loss(db_cursor, clean_test_data):
    """Test P&L calculation for YES position with loss."""
    manager = PositionManager()

    pnl = manager.calculate_position_pnl(
        entry_price=Decimal("0.7500"),
        current_price=Decimal("0.5000"),
        quantity=10,
        side="YES",
    )

    assert pnl == Decimal("-2.5000")  # $2.50 loss


def test_calculate_pnl_no_profit(db_cursor, clean_test_data):
    """Test P&L calculation for NO position with profit.

    Educational Note:
        - NO position profits when price goes DOWN
        - Formula: P&L = quantity * (entry_price - current_price)
        - Example: Entry $0.75, Current $0.50, Qty 10
          P&L = 10 * ($0.75 - $0.50) = $2.50
    """
    manager = PositionManager()

    pnl = manager.calculate_position_pnl(
        entry_price=Decimal("0.7500"),
        current_price=Decimal("0.5000"),
        quantity=10,
        side="NO",
    )

    assert pnl == Decimal("2.5000")  # $2.50 profit


def test_calculate_pnl_no_loss(db_cursor, clean_test_data):
    """Test P&L calculation for NO position with loss."""
    manager = PositionManager()

    pnl = manager.calculate_position_pnl(
        entry_price=Decimal("0.5000"),
        current_price=Decimal("0.7500"),
        quantity=10,
        side="NO",
    )

    assert pnl == Decimal("-2.5000")  # $2.50 loss


def test_calculate_pnl_breakeven(db_cursor, clean_test_data):
    """Test P&L calculation when price unchanged (breakeven)."""
    manager = PositionManager()

    pnl = manager.calculate_position_pnl(
        entry_price=Decimal("0.5000"),
        current_price=Decimal("0.5000"),
        quantity=10,
        side="YES",
    )

    assert pnl == Decimal("0.0000")  # Breakeven


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_complete_position_lifecycle(db_cursor, clean_test_data, position_params):
    """Test complete position lifecycle: open -> update -> update -> close.

    Educational Note:
        - Demonstrates SCD Type 2 versioning in action
        - Each operation creates new version with new surrogate id
        - Business key stays constant throughout lifecycle
        - Final version has all history preserved in archived versions
    """
    manager = PositionManager()

    # Step 1: Open position
    position = manager.open_position(**position_params)
    assert position["status"] == "open"
    assert position["entry_price"] == Decimal("0.4975")
    business_key = position["position_id"]

    # Step 2: First price update (price goes up)
    v1 = manager.update_position(position_id=position["id"], current_price=Decimal("0.5200"))
    assert v1["position_id"] == business_key
    assert v1["unrealized_pnl"] == Decimal("0.2250")  # 10 * (0.52 - 0.4975) = $0.225

    # Step 3: Second price update (price goes higher)
    v2 = manager.update_position(position_id=v1["id"], current_price=Decimal("0.6000"))
    assert v2["position_id"] == business_key
    assert v2["unrealized_pnl"] == Decimal("1.0250")  # 10 * (0.60 - 0.4975) = $1.025

    # Step 4: Close position at profit
    final = manager.close_position(
        position_id=v2["id"],
        exit_price=Decimal("0.7000"),
        exit_reason="profit_target",
    )
    assert final["position_id"] == business_key
    assert final["status"] == "closed"
    assert final["realized_pnl"] == Decimal("2.0250")  # 10 * (0.70 - 0.4975) = $2.025

    # Verify only final version is current
    positions = manager.get_open_positions()
    assert len(positions) == 0  # No open positions (final version is closed)


def test_margin_calculation_yes_vs_no(db_cursor, clean_test_data, position_params):
    """Test margin requirements differ for YES vs NO positions.

    Educational Note:
        - YES margin: quantity * (1.00 - entry_price)
        - NO margin: quantity * entry_price
        - At entry_price = 0.50: Both require $5.00 margin (symmetric)
        - At entry_price = 0.75: YES needs $2.50, NO needs $7.50 (asymmetric)
    """
    manager = PositionManager()

    # Test YES position at 0.75
    yes_params = {
        **position_params,
        "side": "YES",
        "entry_price": Decimal("0.7500"),
        "available_margin": Decimal("3.00"),  # Need $2.50 -> should PASS
    }
    yes_position = manager.open_position(**yes_params)
    assert yes_position["side"] == "YES"

    # Test NO position at 0.75 with same margin should FAIL
    no_params = {
        **position_params,
        "market_id": "MKT-NFL-002",  # Different market
        "side": "NO",
        "entry_price": Decimal("0.7500"),
        "available_margin": Decimal("3.00"),  # Need $7.50 -> should FAIL
    }
    with pytest.raises(InsufficientMarginError):
        manager.open_position(**no_params)
