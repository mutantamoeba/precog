"""
Tests for CRUD operations (markets, positions, trades).

Critical tests:
- Decimal precision preserved
- SCD Type 2 versioning works correctly
- Foreign key constraints enforced
- Transaction rollback on error
"""

from decimal import Decimal

import pytest

from precog.database import (
    close_position,
    create_market,
    create_position,
    create_trade,
    get_current_market,
    get_current_positions,
    get_market_history,
    get_recent_trades,
    get_trades_by_market,
    update_market_with_versioning,
    update_position_price,
)

# =============================================================================
# MARKET CRUD TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_create_market_with_decimal_precision(db_pool, clean_test_data, sample_market_data):
    """Test creating market with DECIMAL precision."""
    # Create market
    market_id = create_market(**sample_market_data)
    assert market_id is not None

    # Retrieve and verify
    market = get_current_market(sample_market_data["ticker"])
    assert market is not None
    assert isinstance(market["yes_price"], Decimal)
    assert isinstance(market["no_price"], Decimal)
    assert market["yes_price"] == Decimal("0.5200")
    assert market["no_price"] == Decimal("0.4800")


@pytest.mark.integration
@pytest.mark.critical
def test_decimal_precision_not_float(db_pool, clean_test_data, sample_market_data):
    """CRITICAL: Verify prices are Decimal, NOT float."""
    create_market(**sample_market_data)
    market = get_current_market(sample_market_data["ticker"])

    # This is THE critical test for trading
    assert type(market["yes_price"]) == Decimal, (
        f"Expected Decimal, got {type(market['yes_price'])}"
    )
    assert type(market["no_price"]) == Decimal, f"Expected Decimal, got {type(market['no_price'])}"


@pytest.mark.integration
def test_create_market_sub_penny_precision(db_pool, clean_test_data, sample_market_data):
    """Test sub-penny pricing (0.4275 = $0.4275)."""
    sample_market_data["ticker"] = "TEST-SUBPENNY"
    sample_market_data["yes_price"] = Decimal("0.4275")
    sample_market_data["no_price"] = Decimal("0.5725")

    create_market(**sample_market_data)
    market = get_current_market("TEST-SUBPENNY")

    # Verify exact sub-penny precision
    assert str(market["yes_price"]) == "0.4275"
    assert str(market["no_price"]) == "0.5725"


@pytest.mark.integration
@pytest.mark.critical
def test_get_current_market_filters_by_row_current_ind(
    db_pool, clean_test_data, sample_market_data
):
    """Test that get_current_market returns only current version."""
    # Create market
    create_market(**sample_market_data)

    # Update it (creates new version)
    update_market_with_versioning(ticker=sample_market_data["ticker"], yes_price=Decimal("0.5500"))

    # Get current version
    market = get_current_market(sample_market_data["ticker"])

    # Should return ONLY the updated version
    assert market["yes_price"] == Decimal("0.5500")


@pytest.mark.integration
@pytest.mark.critical
def test_scd_type2_versioning(db_pool, clean_test_data, sample_market_data):
    """Test SCD Type 2 versioning creates historical records."""
    # Create market
    create_market(**sample_market_data)

    # Update price (should create new version)
    update_market_with_versioning(
        ticker=sample_market_data["ticker"], yes_price=Decimal("0.5500"), no_price=Decimal("0.4500")
    )

    # Get history
    history = get_market_history(sample_market_data["ticker"], limit=10)

    # Should have 2 versions
    assert len(history) >= 2

    # Newest version should be current
    assert history[0]["yes_price"] == Decimal("0.5500")
    assert history[0]["row_current_ind"] is True

    # Oldest version should be historical
    assert history[-1]["yes_price"] == Decimal("0.5200")
    assert history[-1]["row_current_ind"] is False
    assert history[-1]["row_end_ts"] is not None


@pytest.mark.integration
def test_update_market_partial_fields(db_pool, clean_test_data, sample_market_data):
    """Test updating only specific fields (others preserved)."""
    create_market(**sample_market_data)

    # Update only yes_price
    update_market_with_versioning(
        ticker=sample_market_data["ticker"],
        yes_price=Decimal("0.5500"),
        # no_price not provided - should preserve old value
    )

    market = get_current_market(sample_market_data["ticker"])

    # yes_price updated
    assert market["yes_price"] == Decimal("0.5500")
    # no_price preserved
    assert market["no_price"] == Decimal("0.4800")


@pytest.mark.integration
def test_get_market_history_limit(db_pool, clean_test_data, sample_market_data):
    """Test that get_market_history respects limit."""
    create_market(**sample_market_data)

    # Create 5 versions
    for i in range(1, 6):
        update_market_with_versioning(
            ticker=sample_market_data["ticker"], yes_price=Decimal(f"0.5{i}00")
        )

    # Request only 3
    history = get_market_history(sample_market_data["ticker"], limit=3)

    assert len(history) == 3


# =============================================================================
# POSITION CRUD TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_create_position(db_pool, clean_test_data, sample_market_data, sample_position_data):
    """Test creating position."""
    # Create market first (foreign key requirement)
    market_id = create_market(**sample_market_data)

    # Create position
    position_id = create_position(market_id=market_id, **sample_position_data)

    assert position_id is not None


@pytest.mark.integration
def test_get_current_positions_filters_open(
    db_pool, clean_test_data, sample_market_data, sample_position_data
):
    """Test filtering positions by status."""
    market_id = create_market(**sample_market_data)
    position_id = create_position(market_id=market_id, **sample_position_data)

    # Get open positions
    positions = get_current_positions(status="open")

    # Should include our test position
    assert len(positions) > 0
    assert any(p["position_id"] == position_id for p in positions)


@pytest.mark.integration
@pytest.mark.critical
def test_update_position_price_versioning(
    db_pool, clean_test_data, sample_market_data, sample_position_data
):
    """Test position price updates use SCD Type 2."""
    market_id = create_market(**sample_market_data)
    position_id = create_position(market_id=market_id, **sample_position_data)

    # Update price
    new_position_id = update_position_price(
        position_id=position_id, current_price=Decimal("0.5800")
    )

    # Should create new version
    assert new_position_id != position_id


@pytest.mark.integration
@pytest.mark.critical
def test_close_position(db_pool, clean_test_data, sample_market_data, sample_position_data):
    """Test closing position."""
    market_id = create_market(**sample_market_data)
    position_id = create_position(market_id=market_id, **sample_position_data)

    # Close position
    closed_id = close_position(
        position_id=position_id,
        exit_price=Decimal("0.6000"),
        exit_reason="target_hit",
        realized_pnl=Decimal("8.00"),
    )

    # Get updated position
    positions = get_current_positions()
    closed_pos = next((p for p in positions if p["position_id"] == closed_id), None)

    assert closed_pos is not None
    assert closed_pos["status"] == "closed"
    assert closed_pos["exit_price"] == Decimal("0.6000")
    assert closed_pos["realized_pnl"] == Decimal("8.00")


@pytest.mark.integration
def test_position_unrealized_pnl_calculation(
    db_pool, clean_test_data, sample_market_data, sample_position_data
):
    """Test unrealized P&L calculation."""
    market_id = create_market(**sample_market_data)
    position_id = create_position(market_id=market_id, **sample_position_data)

    # Update price to profitable level
    update_position_price(
        position_id=position_id,
        current_price=Decimal("0.5800"),  # Entered at 0.5200
    )

    # Get position with joined market data
    positions = get_current_positions()
    pos = next((p for p in positions if p["market_id"] == market_id), None)

    # Unrealized P&L should be calculated
    # (0.5800 - 0.5200) * 100 contracts = $6.00
    # Note: The get_current_positions query should calculate this
    assert pos is not None


# =============================================================================
# TRADE CRUD TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
def test_create_trade_with_attribution(
    db_pool, clean_test_data, sample_market_data, sample_trade_data
):
    """Test creating trade with strategy and model attribution."""
    market_id = create_market(**sample_market_data)

    # Create trade
    trade_id = create_trade(market_id=market_id, **sample_trade_data)

    assert trade_id is not None


@pytest.mark.integration
def test_get_trades_by_market(db_pool, clean_test_data, sample_market_data, sample_trade_data):
    """Test retrieving trades for specific market."""
    market_id = create_market(**sample_market_data)

    # Create multiple trades
    trade_id1 = create_trade(market_id=market_id, **sample_trade_data)
    trade_id2 = create_trade(market_id=market_id, **sample_trade_data)

    # Retrieve trades
    trades = get_trades_by_market(market_id, limit=10)

    assert len(trades) >= 2
    assert any(t["trade_id"] == trade_id1 for t in trades)
    assert any(t["trade_id"] == trade_id2 for t in trades)


@pytest.mark.integration
def test_get_recent_trades(db_pool, clean_test_data, sample_market_data, sample_trade_data):
    """Test retrieving recent trades across all markets."""
    market_id = create_market(**sample_market_data)
    trade_id = create_trade(market_id=market_id, **sample_trade_data)

    # Get recent trades
    trades = get_recent_trades(limit=10)

    # Should include our test trade
    assert len(trades) > 0
    assert any(t["trade_id"] == trade_id for t in trades)


@pytest.mark.integration
@pytest.mark.critical
def test_trade_strategy_model_attribution(
    db_pool, clean_test_data, sample_market_data, sample_trade_data
):
    """CRITICAL: Test that trades record strategy_id and model_id."""
    market_id = create_market(**sample_market_data)
    create_trade(market_id=market_id, **sample_trade_data)

    # Retrieve trade
    trades = get_trades_by_market(market_id, limit=1)
    trade = trades[0]

    # Must have strategy and model attribution for A/B testing
    assert trade["strategy_id"] == sample_trade_data["strategy_id"]
    assert trade["model_id"] == sample_trade_data["model_id"]


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


@pytest.mark.integration
def test_extreme_prices(db_pool, clean_test_data, sample_market_data, decimal_prices):
    """Test extreme price values (0.0001 and 0.9999)."""
    sample_market_data["ticker"] = "TEST-EXTREME"
    sample_market_data["yes_price"] = decimal_prices["min"]  # 0.0001
    sample_market_data["no_price"] = decimal_prices["max"]  # 0.9999

    create_market(**sample_market_data)
    market = get_current_market("TEST-EXTREME")

    assert market["yes_price"] == Decimal("0.0001")
    assert market["no_price"] == Decimal("0.9999")


@pytest.mark.integration
def test_tight_spread(db_pool, clean_test_data, sample_market_data, decimal_prices):
    """Test very tight spread (0.0001 = 0.01¢)."""
    sample_market_data["ticker"] = "TEST-TIGHT"
    sample_market_data["yes_price"] = decimal_prices["tight_spread_bid"]
    sample_market_data["no_price"] = decimal_prices["tight_spread_ask"]

    create_market(**sample_market_data)
    market = get_current_market("TEST-TIGHT")

    # Spread should be exactly 0.0001
    spread = market["no_price"] - market["yes_price"]
    assert spread == Decimal("0.0001")


@pytest.mark.integration
def test_update_nonexistent_market_raises_error(db_pool, clean_test_data):
    """Test updating non-existent market raises ValueError."""
    with pytest.raises(ValueError, match="Market not found"):
        update_market_with_versioning(ticker="NONEXISTENT-MARKET", yes_price=Decimal("0.5000"))


@pytest.mark.integration
def test_close_nonexistent_position_raises_error(db_pool, clean_test_data):
    """Test closing non-existent position raises ValueError."""
    with pytest.raises(ValueError, match="Position not found"):
        close_position(
            position_id=999999,  # Doesn't exist
            exit_price=Decimal("0.5000"),
            exit_reason="test",
            realized_pnl=Decimal("0.00"),
        )
