"""
Unit tests for kelly_criterion module.

Tests individual functions with mocked dependencies.

Reference: TESTING_STRATEGY_V3.2.md Section "Unit Tests"
"""

from decimal import Decimal

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

pytestmark = [pytest.mark.unit]


class TestCalculateKellySize:
    """Unit tests for calculate_kelly_size function."""

    def test_basic_kelly_calculation(self) -> None:
        """Test basic Kelly calculation with valid inputs."""
        result = calculate_kelly_size(
            edge=Decimal("0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("125.00")

    def test_zero_edge_returns_zero(self) -> None:
        """Test that zero edge returns zero position."""
        result = calculate_kelly_size(
            edge=Decimal("0"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")

    def test_negative_edge_returns_zero(self) -> None:
        """Test that negative edge returns zero position."""
        result = calculate_kelly_size(
            edge=Decimal("-0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")

    def test_full_kelly(self) -> None:
        """Test full Kelly (fraction=1.0)."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("1000")

    def test_half_kelly(self) -> None:
        """Test half Kelly (fraction=0.5)."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.5"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("500")

    def test_zero_kelly_fraction_returns_zero(self) -> None:
        """Test zero Kelly fraction returns zero position."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")

    def test_zero_bankroll_returns_zero(self) -> None:
        """Test zero bankroll returns zero position."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("0"),
        )

        assert result == Decimal("0")

    def test_position_capped_at_bankroll(self) -> None:
        """Test position is capped at bankroll."""
        # With 100% edge and full Kelly, position would be > bankroll
        result = calculate_kelly_size(
            edge=Decimal("2.0"),  # 200% edge
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("10000")  # Capped at bankroll

    def test_position_capped_at_max_position(self) -> None:
        """Test position is capped at max_position."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000"),
            max_position=Decimal("500"),
        )

        assert result == Decimal("500")

    def test_invalid_kelly_fraction_raises_error(self) -> None:
        """Test invalid kelly_fraction raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("1.5"),  # Invalid
                bankroll=Decimal("10000"),
            )

        assert "kelly_fraction must be in [0, 1]" in str(exc_info.value)

    def test_negative_kelly_fraction_raises_error(self) -> None:
        """Test negative kelly_fraction raises ValueError."""
        with pytest.raises(ValueError):
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("-0.5"),
                bankroll=Decimal("10000"),
            )

    def test_negative_bankroll_raises_error(self) -> None:
        """Test negative bankroll raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("-1000"),
            )

        assert "bankroll cannot be negative" in str(exc_info.value)


class TestCalculateEdge:
    """Unit tests for calculate_edge function."""

    def test_basic_edge_calculation(self) -> None:
        """Test basic edge calculation."""
        result = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
        )

        assert result == Decimal("0.10")

    def test_edge_with_fees(self) -> None:
        """Test edge calculation with fees."""
        result = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            fees=Decimal("0.01"),
        )

        assert result == Decimal("0.09")

    def test_negative_edge(self) -> None:
        """Test negative edge (bad trade)."""
        result = calculate_edge(
            true_probability=Decimal("0.40"),
            market_price=Decimal("0.50"),
        )

        assert result == Decimal("-0.10")

    def test_zero_edge(self) -> None:
        """Test zero edge (fair price)."""
        result = calculate_edge(
            true_probability=Decimal("0.50"),
            market_price=Decimal("0.50"),
        )

        assert result == Decimal("0")

    def test_invalid_true_probability_raises_error(self) -> None:
        """Test invalid true_probability raises ValueError."""
        with pytest.raises(ValueError):
            calculate_edge(
                true_probability=Decimal("1.5"),  # Invalid
                market_price=Decimal("0.50"),
            )

    def test_negative_probability_raises_error(self) -> None:
        """Test negative probability raises ValueError."""
        with pytest.raises(ValueError):
            calculate_edge(
                true_probability=Decimal("-0.1"),
                market_price=Decimal("0.50"),
            )

    def test_invalid_market_price_raises_error(self) -> None:
        """Test invalid market_price raises ValueError."""
        with pytest.raises(ValueError):
            calculate_edge(
                true_probability=Decimal("0.60"),
                market_price=Decimal("1.5"),  # Invalid
            )

    def test_negative_fees_raises_error(self) -> None:
        """Test negative fees raises ValueError."""
        with pytest.raises(ValueError):
            calculate_edge(
                true_probability=Decimal("0.60"),
                market_price=Decimal("0.50"),
                fees=Decimal("-0.01"),
            )


class TestCalculateOptimalPosition:
    """Unit tests for calculate_optimal_position function."""

    def test_basic_optimal_position(self) -> None:
        """Test basic optimal position calculation."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.65"),
            market_price=Decimal("0.55"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01"),
        )

        # Edge = 0.65 - 0.55 - 0.01 = 0.09
        # Position = 0.09 * 0.25 * 10000 = 225
        assert result == Decimal("225")

    def test_edge_below_min_edge_returns_zero(self) -> None:
        """Test edge below min_edge returns zero."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.51"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            min_edge=Decimal("0.02"),  # Edge is only 0.01
        )

        assert result == Decimal("0")

    def test_negative_edge_returns_zero(self) -> None:
        """Test negative edge returns zero."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.40"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
        )

        assert result == Decimal("0")

    def test_with_max_position(self) -> None:
        """Test with max_position constraint."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.70"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            max_position=Decimal("100"),
        )

        assert result == Decimal("100")

    def test_default_kelly_fraction(self) -> None:
        """Test default kelly_fraction is 0.25."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
        )

        # Edge = 0.10, Position = 0.10 * 0.25 * 10000 = 250
        assert result == Decimal("250")

    def test_default_min_edge(self) -> None:
        """Test default min_edge is 0.02."""
        # Edge of 0.015 should return zero with default min_edge=0.02
        result = calculate_optimal_position(
            true_probability=Decimal("0.515"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")
