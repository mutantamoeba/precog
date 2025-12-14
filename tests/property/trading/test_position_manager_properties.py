"""
Property-Based Tests for PositionManager.

Uses Hypothesis to test mathematical invariants that should hold for any valid input.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-RISK-001 (Position Entry Validation)

Usage:
    pytest tests/property/trading/test_position_manager_properties.py -v -m property
"""

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.trading.position_manager import PositionManager

# =============================================================================
# Custom Strategies
# =============================================================================


# Valid price range [0.01, 0.99]
price_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("0.99"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Quantity (positive integer)
quantity_strategy = st.integers(min_value=1, max_value=10000)

# Position side
side_strategy = st.sampled_from(["YES", "NO"])

# Margin amount (positive decimal)
margin_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# =============================================================================
# Helper Functions
# =============================================================================


def create_manager() -> PositionManager:
    """Create a PositionManager instance for testing."""
    return PositionManager()


# =============================================================================
# Property Tests: P&L Calculation Invariants
# =============================================================================


@pytest.mark.property
class TestPnLCalculationProperties:
    """Property tests for P&L calculation invariants."""

    @given(
        entry_price=price_strategy,
        current_price=price_strategy,
        quantity=quantity_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_yes_pnl_increases_with_price(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
    ) -> None:
        """Test YES position: P&L positive when price increases."""
        manager = create_manager()

        pnl = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
            side="YES",
        )

        if current_price > entry_price:
            assert pnl > 0, "YES position should profit when price rises"
        elif current_price < entry_price:
            assert pnl < 0, "YES position should lose when price falls"
        else:
            assert pnl == 0, "P&L should be zero when prices are equal"

    @given(
        entry_price=price_strategy,
        current_price=price_strategy,
        quantity=quantity_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_no_pnl_increases_with_price_drop(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
    ) -> None:
        """Test NO position: P&L positive when price decreases."""
        manager = create_manager()

        pnl = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
            side="NO",
        )

        if current_price < entry_price:
            assert pnl > 0, "NO position should profit when price falls"
        elif current_price > entry_price:
            assert pnl < 0, "NO position should lose when price rises"
        else:
            assert pnl == 0, "P&L should be zero when prices are equal"

    @given(
        entry_price=price_strategy,
        current_price=price_strategy,
        quantity=quantity_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_yes_no_pnl_are_opposite(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
    ) -> None:
        """Test YES and NO positions have opposite P&L for same price movement."""
        manager = create_manager()

        yes_pnl = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
            side="YES",
        )

        no_pnl = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
            side="NO",
        )

        # YES P&L + NO P&L = 0 (opposite directions)
        assert yes_pnl + no_pnl == 0, "YES and NO P&L should sum to zero"

    @given(
        entry_price=price_strategy,
        current_price=price_strategy,
        quantity=quantity_strategy,
        side=side_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_pnl_scales_with_quantity(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
        side: str,
    ) -> None:
        """Test P&L scales linearly with quantity."""
        manager = create_manager()

        pnl_single = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=1,
            side=side,
        )

        pnl_multiple = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
            side=side,
        )

        expected = pnl_single * Decimal(str(quantity))
        assert pnl_multiple == expected, "P&L should scale linearly with quantity"

    @given(
        price=price_strategy,
        quantity=quantity_strategy,
        side=side_strategy,
    )
    @settings(max_examples=30)
    def test_pnl_zero_when_prices_equal(
        self,
        price: Decimal,
        quantity: int,
        side: str,
    ) -> None:
        """Test P&L is zero when entry and current prices are equal."""
        manager = create_manager()

        pnl = manager.calculate_position_pnl(
            entry_price=price,
            current_price=price,
            quantity=quantity,
            side=side,
        )

        assert pnl == 0, "P&L should be zero when prices are equal"

    @given(
        entry_price=price_strategy,
        current_price=price_strategy,
        quantity=quantity_strategy,
        side=side_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_pnl_is_decimal_type(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
        side: str,
    ) -> None:
        """Test P&L always returns Decimal (never float)."""
        manager = create_manager()

        pnl = manager.calculate_position_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
            side=side,
        )

        assert isinstance(pnl, Decimal), "P&L should always be Decimal type"


# =============================================================================
# Property Tests: Margin Calculation Properties
# =============================================================================


@pytest.mark.property
class TestMarginCalculationProperties:
    """Property tests for margin calculation properties."""

    @given(
        entry_price=price_strategy,
        quantity=quantity_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_yes_margin_formula(
        self,
        entry_price: Decimal,
        quantity: int,
    ) -> None:
        """Test YES margin = quantity * (1.00 - entry_price)."""
        # YES margin formula
        expected_margin = Decimal(str(quantity)) * (Decimal("1.00") - entry_price)

        # Margin should be positive
        assert expected_margin > 0, "YES margin should always be positive"

        # Margin increases as price decreases
        # (cheaper contracts require more margin relative to potential win)

    @given(
        entry_price=price_strategy,
        quantity=quantity_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_no_margin_formula(
        self,
        entry_price: Decimal,
        quantity: int,
    ) -> None:
        """Test NO margin = quantity * entry_price."""
        # NO margin formula
        expected_margin = Decimal(str(quantity)) * entry_price

        # Margin should be positive
        assert expected_margin > 0, "NO margin should always be positive"

    @given(
        entry_price=price_strategy,
        quantity=quantity_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_yes_no_margin_sum_to_quantity(
        self,
        entry_price: Decimal,
        quantity: int,
    ) -> None:
        """Test YES margin + NO margin = quantity (total $1 per contract)."""
        yes_margin = Decimal(str(quantity)) * (Decimal("1.00") - entry_price)
        no_margin = Decimal(str(quantity)) * entry_price

        total = yes_margin + no_margin
        expected = Decimal(str(quantity))

        assert total == expected, "YES + NO margin should equal quantity"


# =============================================================================
# Property Tests: Price Validation Properties
# =============================================================================


@pytest.mark.property
class TestPriceValidationProperties:
    """Property tests for price validation properties."""

    @given(price=price_strategy)
    @settings(max_examples=30)
    def test_valid_price_range(self, price: Decimal) -> None:
        """Test valid prices are in range [0.01, 0.99]."""
        assert Decimal("0.01") <= price <= Decimal("0.99")

    @given(
        price=st.decimals(
            min_value=Decimal("1.00"),
            max_value=Decimal("10.00"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=30)
    def test_invalid_price_above_range(self, price: Decimal) -> None:
        """Test prices >= 1.00 are invalid."""
        manager = create_manager()

        with pytest.raises(ValueError, match="outside valid range"):
            manager.update_position(position_id=1, current_price=price)

    @given(
        price=st.decimals(
            min_value=Decimal("-1.00"),
            max_value=Decimal("0.009"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=30)
    def test_invalid_price_below_range(self, price: Decimal) -> None:
        """Test prices <= 0.00 are invalid."""
        manager = create_manager()

        with pytest.raises(ValueError, match="outside valid range"):
            manager.update_position(position_id=1, current_price=price)


# =============================================================================
# Property Tests: Trailing Stop Config Properties
# =============================================================================


@pytest.mark.property
class TestTrailingStopConfigProperties:
    """Property tests for trailing stop configuration properties."""

    @given(
        activation_threshold=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("1.00"),
            places=4,
        ),
        initial_distance=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("0.50"),
            places=4,
        ),
        tightening_rate=st.decimals(
            min_value=Decimal("0.00"),
            max_value=Decimal("1.00"),
            places=4,
        ),
        floor_distance=st.decimals(
            min_value=Decimal("0.00"),
            max_value=Decimal("0.20"),
            places=4,
        ),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_config_accepted(
        self,
        activation_threshold: Decimal,
        initial_distance: Decimal,
        tightening_rate: Decimal,
        floor_distance: Decimal,
    ) -> None:
        """Test valid trailing stop configs are structurally valid."""
        config = {
            "activation_threshold": activation_threshold,
            "initial_distance": initial_distance,
            "tightening_rate": tightening_rate,
            "floor_distance": floor_distance,
        }

        # All required keys present
        required_keys = {
            "activation_threshold",
            "initial_distance",
            "tightening_rate",
            "floor_distance",
        }
        assert required_keys <= set(config.keys())

        # All values are Decimal
        for key, value in config.items():
            assert isinstance(value, Decimal), f"{key} should be Decimal"

    @given(
        activation_threshold=st.decimals(
            min_value=Decimal("-1.00"),
            max_value=Decimal("0.00"),
            places=4,
        ),
    )
    @settings(max_examples=20)
    def test_negative_activation_threshold_rejected(
        self,
        activation_threshold: Decimal,
    ) -> None:
        """Test negative activation threshold is rejected."""
        manager = create_manager()

        config = {
            "activation_threshold": activation_threshold,
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.10"),
            "floor_distance": Decimal("0.02"),
        }

        with pytest.raises(ValueError, match="activation_threshold must be positive"):
            manager.initialize_trailing_stop(1, config)

    @given(
        tightening_rate=st.decimals(
            min_value=Decimal("1.01"),
            max_value=Decimal("10.00"),
            places=4,
        ),
    )
    @settings(max_examples=20)
    def test_tightening_rate_over_one_rejected(
        self,
        tightening_rate: Decimal,
    ) -> None:
        """Test tightening rate > 1.0 is rejected."""
        manager = create_manager()

        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": tightening_rate,
            "floor_distance": Decimal("0.02"),
        }

        with pytest.raises(ValueError, match="tightening_rate must be between 0 and 1"):
            manager.initialize_trailing_stop(1, config)
