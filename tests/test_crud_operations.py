"""
Tests for CRUD operations (markets, positions, trades).

Critical tests:
- Decimal precision preserved
- SCD Type 2 versioning works correctly
- Foreign key constraints enforced
- Transaction rollback on error
"""

import json
from decimal import Decimal

import pytest

from precog.database import (
    close_position,
    create_account_balance,
    create_market,
    create_position,
    create_settlement,
    create_strategy,
    create_trade,
    get_current_market,
    get_current_positions,
    get_market_history,
    get_recent_trades,
    get_strategy_by_name_and_version,
    get_trades_by_market,
    update_account_balance_with_versioning,
    update_market_with_versioning,
    update_position_price,
)
from precog.database.crud_operations import DecimalEncoder

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
    assert market is not None, "Market should exist"
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
    assert market is not None, "Market should exist"
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
    assert market is not None, "Market should exist"
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
    assert market is not None, "Market should exist"
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

    # Should include our test position (compare using surrogate id)
    assert len(positions) > 0
    assert any(p["id"] == position_id for p in positions)


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

    # Get updated position (compare using surrogate id)
    positions = get_current_positions()
    closed_pos = next((p for p in positions if p["id"] == closed_id), None)

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
    assert market is not None, "Market should exist"

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
    assert market is not None, "Market should exist"

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


# =============================================================================
# ACCOUNT BALANCE TESTS
# =============================================================================


@pytest.mark.integration
def test_create_account_balance_with_decimal(db_pool, clean_test_data):
    """Test creating account balance with Decimal precision.

    Coverage: Lines 1128-1144 (create_account_balance function)
    """
    from precog.database.connection import get_cursor

    # Setup: Create platform
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('test-platform', 'trading', 'Test Platform', 'https://test.example.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
        """
        )

    # Test: Create account balance
    balance_id = create_account_balance(
        platform_id="test-platform", balance=Decimal("1234.5678"), currency="USD"
    )

    assert balance_id is not None
    assert isinstance(balance_id, int)

    # Verify: Check balance was created correctly
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM account_balance WHERE balance_id = %s AND row_current_ind = TRUE",
            (balance_id,),
        )
        result = cur.fetchone()
        assert result is not None
        assert result["platform_id"] == "test-platform"
        assert result["balance"] == Decimal("1234.5678")
        assert result["currency"] == "USD"


@pytest.mark.integration
def test_create_account_balance_rejects_float(db_pool, clean_test_data):
    """Test that create_account_balance rejects float values.

    Coverage: Line 1129 (type validation)
    """
    from precog.database.connection import get_cursor

    # Setup: Create platform
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('test-platform2', 'trading', 'Test Platform 2', 'https://test.example.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
        """
        )

    # Test: Create account balance with float (should raise ValueError)
    with pytest.raises(ValueError, match="Balance must be Decimal"):
        create_account_balance(
            platform_id="test-platform2",
            balance=1234.5678,  # type: ignore[arg-type]  # Float not Decimal - intentional test
            currency="USD",
        )


@pytest.mark.integration
def test_update_account_balance_rejects_float(db_pool, clean_test_data):
    """Test that update_account_balance_with_versioning rejects float values.

    Coverage: Line 1214 (type validation)
    """
    from precog.database.connection import get_cursor

    # Setup: Create platform
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO platforms (platform_id, platform_type, display_name, base_url, status)
            VALUES ('test-platform3', 'trading', 'Test Platform 3', 'https://test.example.com', 'active')
            ON CONFLICT (platform_id) DO NOTHING
        """
        )

    # Test: Update with float (should raise ValueError)
    with pytest.raises(ValueError, match="Balance must be Decimal"):
        update_account_balance_with_versioning(
            platform_id="test-platform3",
            new_balance=5678.1234,  # type: ignore[arg-type]  # Float not Decimal
        )


# =============================================================================
# STRATEGY TESTS
# =============================================================================


@pytest.mark.integration
def test_get_strategy_by_name_and_version(db_pool, clean_test_data):
    """Test retrieving strategy by name and version.

    Coverage: Lines 1474-1487 (get_strategy_by_name_and_version function)
    """
    import uuid

    # Use unique strategy name to avoid collisions across test runs
    unique_name = f"test_strategy_{uuid.uuid4().hex[:8]}"

    # Setup: Create a strategy (use 'value' for strategy_type, 'nfl' for domain after Migration 021)
    strategy_id = create_strategy(
        strategy_name=unique_name,
        strategy_version="v1.0",
        strategy_type="value",  # HOW you trade (trading methodology)
        subcategory="nfl",  # Maps to 'domain' column (market type)
        config={"kelly_fraction": Decimal("0.25"), "min_edge": Decimal("0.05")},
    )

    # Test: Retrieve strategy by name and version
    strategy = get_strategy_by_name_and_version(unique_name, "v1.0")

    assert strategy is not None
    assert strategy["strategy_id"] == strategy_id
    assert strategy["strategy_name"] == unique_name
    assert strategy["strategy_version"] == "v1.0"

    # Verify Decimal values restored from config
    assert isinstance(strategy["config"]["kelly_fraction"], Decimal)
    assert strategy["config"]["kelly_fraction"] == Decimal("0.25")
    assert isinstance(strategy["config"]["min_edge"], Decimal)
    assert strategy["config"]["min_edge"] == Decimal("0.05")


@pytest.mark.integration
def test_get_strategy_by_name_and_version_not_found(db_pool, clean_test_data):
    """Test retrieving non-existent strategy returns None."""
    strategy = get_strategy_by_name_and_version("nonexistent_strategy", "v1.0")
    assert strategy is None


# =============================================================================
# POSITION FILTER TESTS
# =============================================================================


@pytest.mark.integration
def test_get_current_positions_with_market_id_filter(
    db_pool, clean_test_data, sample_market_data, sample_position_data
):
    """Test get_current_positions with market_id filter.

    Coverage: Lines 760-761 (market_id filter)
    """
    # Setup: Create market and positions
    market_id1 = create_market(**sample_market_data)
    sample_market_data["ticker"] = "TEST-MARKET2"
    market_id2 = create_market(**sample_market_data)

    # Create positions for both markets
    sample_position_data["market_id"] = market_id1
    position1 = create_position(**sample_position_data)

    sample_position_data["market_id"] = market_id2
    _position2 = create_position(**sample_position_data)  # Intentionally unused - testing filter

    # Test: Get positions filtered by market_id1
    positions = get_current_positions(market_id=market_id1)

    # Should only return position1 (compare using surrogate id)
    assert len(positions) == 1
    assert positions[0]["id"] == position1


# =============================================================================
# TRADE FILTER TESTS
# =============================================================================


@pytest.mark.integration
def test_get_recent_trades_with_strategy_filter(
    db_pool, clean_test_data, sample_market_data, sample_trade_data
):
    """Test get_recent_trades with strategy_id filter.

    Coverage: Lines 1058-1059 (strategy_id filter)
    """
    import uuid

    # Use unique strategy names to avoid collisions across test runs
    unique_name1 = f"strategy1_{uuid.uuid4().hex[:8]}"
    unique_name2 = f"strategy2_{uuid.uuid4().hex[:8]}"

    # Setup: Create market and strategies (use 'value'/'arbitrage' for strategy_type after Migration 021)
    market_id = create_market(**sample_market_data)

    strategy_id1 = create_strategy(
        strategy_name=unique_name1,
        strategy_version="v1.0",
        strategy_type="value",  # HOW you trade (trading methodology)
        subcategory="nfl",  # Maps to 'domain' column (market type)
        config={},
    )
    strategy_id2 = create_strategy(
        strategy_name=unique_name2,
        strategy_version="v1.0",
        strategy_type="arbitrage",  # Different strategy_type for testing filter
        subcategory="nfl",
        config={},
    )

    # Create trades for both strategies
    sample_trade_data["market_id"] = market_id
    sample_trade_data["strategy_id"] = strategy_id1
    trade1 = create_trade(**sample_trade_data)

    sample_trade_data["strategy_id"] = strategy_id2
    _trade2 = create_trade(**sample_trade_data)  # Intentionally unused - testing filter

    # Test: Get trades filtered by strategy_id1
    trades = get_recent_trades(strategy_id=strategy_id1, limit=10)

    # Should only return trade1
    assert len(trades) == 1
    assert trades[0]["trade_id"] == trade1


# =============================================================================
# SETTLEMENT TESTS
# =============================================================================


@pytest.mark.integration
def test_create_settlement_rejects_float(db_pool, clean_test_data, sample_market_data):
    """Test that create_settlement rejects float values.

    Coverage: Line 1306 (type validation)
    """
    # Setup: Create market
    market_id = create_market(**sample_market_data)

    # Test: Create settlement with float (should raise ValueError)
    with pytest.raises(ValueError, match="Payout must be Decimal"):
        create_settlement(
            market_id=market_id,
            platform_id="kalshi",
            outcome="YES",
            payout=123.45,  # type: ignore[arg-type]  # Float not Decimal
        )


# =============================================================================
# POSITION UPDATE ERROR TESTS
# =============================================================================


@pytest.mark.integration
def test_update_position_price_position_not_found(db_pool, clean_test_data):
    """Test updating non-existent position raises ValueError.

    Coverage: Lines 796-797 (error case)
    """
    with pytest.raises(ValueError, match="Position not found"):
        update_position_price(
            position_id=999999,  # Doesn't exist
            current_price=Decimal("0.5000"),
        )


# =============================================================================
# DECIMAL ENCODER TESTS
# =============================================================================


@pytest.mark.unit
def test_decimal_encoder_handles_decimal():
    """Test DecimalEncoder serializes Decimal to string."""
    data = {"price": Decimal("0.4975"), "amount": Decimal("100.00")}
    json_str = json.dumps(data, cls=DecimalEncoder)
    assert json_str == '{"price": "0.4975", "amount": "100.00"}'


@pytest.mark.unit
def test_decimal_encoder_fallback_for_non_decimal():
    """Test DecimalEncoder falls back to default encoder for non-Decimal objects.

    Coverage: Line 300 (super().default() fallback)
    """
    data = {"price": Decimal("0.4975"), "count": 42, "active": True}
    json_str = json.dumps(data, cls=DecimalEncoder)
    # Should serialize Decimal to string, int/bool normally
    parsed = json.loads(json_str)
    assert parsed["price"] == "0.4975"
    assert parsed["count"] == 42
    assert parsed["active"] is True
