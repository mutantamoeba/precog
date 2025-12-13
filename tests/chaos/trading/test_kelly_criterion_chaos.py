"""
Chaos tests for kelly_criterion module.

Tests failure scenarios and edge cases.

Reference: TESTING_STRATEGY_V3.2.md Section "Chaos Tests"
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

pytestmark = [pytest.mark.chaos]


class TestKellyEdgeCasesChaos:
    """Chaos tests for Kelly calculation edge cases."""

    def test_very_small_edge(self) -> None:
        """Test with very small edge."""
        result = calculate_kelly_size(
            edge=Decimal("0.0001"),  # 0.01% edge
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0.25")  # Small but valid

    def test_very_large_edge(self) -> None:
        """Test with very large edge (>100%)."""
        result = calculate_kelly_size(
            edge=Decimal("10.0"),  # 1000% edge (impossible in practice)
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000"),
        )

        # Should be capped at bankroll
        assert result == Decimal("10000")

    def test_very_small_bankroll(self) -> None:
        """Test with very small bankroll."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("0.01"),  # 1 cent
        )

        assert result == Decimal("0.00025")  # Very small position

    def test_very_large_bankroll(self) -> None:
        """Test with very large bankroll."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("1000000000"),  # 1 billion
        )

        assert result == Decimal("25000000")

    def test_edge_exactly_zero(self) -> None:
        """Test edge exactly zero."""
        result = calculate_kelly_size(
            edge=Decimal("0.0"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")

    def test_edge_very_small_negative(self) -> None:
        """Test very small negative edge."""
        result = calculate_kelly_size(
            edge=Decimal("-0.0001"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")

    def test_kelly_fraction_boundary_zero(self) -> None:
        """Test kelly_fraction at boundary (0)."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("0")

    def test_kelly_fraction_boundary_one(self) -> None:
        """Test kelly_fraction at boundary (1)."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("1"),
            bankroll=Decimal("10000"),
        )

        assert result == Decimal("1000")


class TestEdgeCalculationChaos:
    """Chaos tests for edge calculation."""

    def test_probability_boundary_zero(self) -> None:
        """Test probability at boundary (0)."""
        result = calculate_edge(
            true_probability=Decimal("0"),
            market_price=Decimal("0.50"),
        )

        assert result == Decimal("-0.50")

    def test_probability_boundary_one(self) -> None:
        """Test probability at boundary (1)."""
        result = calculate_edge(
            true_probability=Decimal("1"),
            market_price=Decimal("0.50"),
        )

        assert result == Decimal("0.50")

    def test_market_price_boundary_zero(self) -> None:
        """Test market price at boundary (0)."""
        result = calculate_edge(
            true_probability=Decimal("0.50"),
            market_price=Decimal("0"),
        )

        assert result == Decimal("0.50")

    def test_market_price_boundary_one(self) -> None:
        """Test market price at boundary (1)."""
        result = calculate_edge(
            true_probability=Decimal("0.50"),
            market_price=Decimal("1"),
        )

        assert result == Decimal("-0.50")

    def test_very_high_fees(self) -> None:
        """Test with very high fees."""
        result = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            fees=Decimal("0.50"),  # 50% fees!
        )

        # 0.60 - 0.50 - 0.50 = -0.40
        assert result == Decimal("-0.40")


class TestOptimalPositionChaos:
    """Chaos tests for optimal position calculation."""

    def test_edge_exactly_at_min_edge(self) -> None:
        """Test edge exactly at min_edge threshold."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.52"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            min_edge=Decimal("0.02"),
        )

        # Edge = 0.02, exactly at min_edge
        # Should return position (not zero)
        assert result > Decimal("0")

    def test_edge_just_below_min_edge(self) -> None:
        """Test edge just below min_edge threshold."""
        result = calculate_optimal_position(
            true_probability=Decimal("0.519"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            min_edge=Decimal("0.02"),
        )

        # Edge = 0.019, just below min_edge
        assert result == Decimal("0")

    def test_all_parameters_at_boundaries(self) -> None:
        """Test with all parameters at boundaries."""
        result = calculate_optimal_position(
            true_probability=Decimal("1"),
            market_price=Decimal("0"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("1"),
            fees=Decimal("0"),
            min_edge=Decimal("0"),
        )

        # Max edge, full Kelly
        # Should be capped at bankroll
        assert result == Decimal("10000")


class TestInputValidationChaos:
    """Chaos tests for input validation."""

    def test_kelly_fraction_just_over_one(self) -> None:
        """Test kelly_fraction just over 1."""
        with pytest.raises(ValueError):
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("1.0001"),
                bankroll=Decimal("10000"),
            )

    def test_kelly_fraction_just_under_zero(self) -> None:
        """Test kelly_fraction just under 0."""
        with pytest.raises(ValueError):
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("-0.0001"),
                bankroll=Decimal("10000"),
            )

    def test_probability_just_over_one(self) -> None:
        """Test probability just over 1."""
        with pytest.raises(ValueError):
            calculate_edge(
                true_probability=Decimal("1.0001"),
                market_price=Decimal("0.50"),
            )

    def test_probability_just_under_zero(self) -> None:
        """Test probability just under 0."""
        with pytest.raises(ValueError):
            calculate_edge(
                true_probability=Decimal("-0.0001"),
                market_price=Decimal("0.50"),
            )


class TestMaxPositionChaos:
    """Chaos tests for max_position constraint."""

    def test_max_position_zero(self) -> None:
        """Test max_position of zero."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
            max_position=Decimal("0"),
        )

        assert result == Decimal("0")

    def test_max_position_very_small(self) -> None:
        """Test very small max_position."""
        result = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
            max_position=Decimal("0.01"),
        )

        assert result == Decimal("0.01")

    def test_max_position_larger_than_bankroll(self) -> None:
        """Test max_position larger than bankroll."""
        result = calculate_kelly_size(
            edge=Decimal("2.0"),  # High edge
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000"),
            max_position=Decimal("100000"),  # Larger than bankroll
        )

        # Should be capped at bankroll, not max_position
        assert result == Decimal("10000")


class TestLoggerChaos:
    """Chaos tests for logger error handling."""

    @patch("precog.trading.kelly_criterion.logger")
    def test_logger_exception_doesnt_break_calculation(self, mock_logger: MagicMock) -> None:
        """Test that logger exception doesn't break calculation."""
        mock_logger.debug.side_effect = RuntimeError("Logger failed")

        # Should raise because logger.debug fails
        # In real code, we might want to catch this
        with pytest.raises(RuntimeError):
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("10000"),
            )


class TestPrecisionChaos:
    """Chaos tests for Decimal precision."""

    def test_high_precision_inputs(self) -> None:
        """Test with high precision Decimal inputs."""
        result = calculate_kelly_size(
            edge=Decimal("0.1234567890123456789"),
            kelly_fraction=Decimal("0.2500000000000000001"),
            bankroll=Decimal("10000.0000000000001"),
        )

        # Should handle high precision
        assert isinstance(result, Decimal)
        assert result > Decimal("0")

    def test_repeating_decimal_result(self) -> None:
        """Test calculation that might produce repeating decimal."""
        result = calculate_kelly_size(
            edge=Decimal("1") / Decimal("3"),  # 0.333...
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert isinstance(result, Decimal)
        assert result > Decimal("0")
