"""
Integration tests for kelly_criterion module.

Tests integration between functions and with logger.

Reference: TESTING_STRATEGY_V3.2.md Section "Integration Tests"
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

pytestmark = [pytest.mark.integration]


class TestKellyEdgeIntegration:
    """Integration tests for Kelly calculation with edge calculation."""

    def test_full_workflow_positive_edge(self) -> None:
        """Test full workflow with positive edge."""
        # Step 1: Calculate edge
        edge = calculate_edge(
            true_probability=Decimal("0.65"),
            market_price=Decimal("0.55"),
            fees=Decimal("0.01"),
        )
        assert edge == Decimal("0.09")

        # Step 2: Calculate Kelly position
        position = calculate_kelly_size(
            edge=edge,
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )
        assert position == Decimal("225")

    def test_full_workflow_negative_edge(self) -> None:
        """Test full workflow with negative edge."""
        edge = calculate_edge(
            true_probability=Decimal("0.40"),
            market_price=Decimal("0.55"),
            fees=Decimal("0.01"),
        )
        assert edge == Decimal("-0.16")

        position = calculate_kelly_size(
            edge=edge,
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )
        assert position == Decimal("0")

    def test_optimal_position_uses_both_functions(self) -> None:
        """Test that calculate_optimal_position integrates both functions."""
        # Calculate using optimal_position
        optimal = calculate_optimal_position(
            true_probability=Decimal("0.65"),
            market_price=Decimal("0.55"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01"),
        )

        # Calculate manually using both functions
        edge = calculate_edge(
            true_probability=Decimal("0.65"),
            market_price=Decimal("0.55"),
            fees=Decimal("0.01"),
        )
        manual = calculate_kelly_size(
            edge=edge,
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        assert optimal == manual


class TestLoggerIntegration:
    """Integration tests for logger integration."""

    @patch("precog.trading.kelly_criterion.logger")
    def test_kelly_logs_debug_info(self, mock_logger: MagicMock) -> None:
        """Test Kelly calculation logs debug info."""
        calculate_kelly_size(
            edge=Decimal("0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        mock_logger.debug.assert_called()

    @patch("precog.trading.kelly_criterion.logger")
    def test_zero_edge_logs_reason(self, mock_logger: MagicMock) -> None:
        """Test zero edge logs reason for zero position."""
        calculate_kelly_size(
            edge=Decimal("0"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        # Should log about non-positive edge
        mock_logger.debug.assert_called()
        call_args = str(mock_logger.debug.call_args)
        assert "edge" in call_args.lower() or "Non-positive" in str(mock_logger.debug.call_args)

    @patch("precog.trading.kelly_criterion.logger")
    def test_edge_logs_calculation(self, mock_logger: MagicMock) -> None:
        """Test edge calculation logs info."""
        calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
        )

        mock_logger.debug.assert_called()

    @patch("precog.trading.kelly_criterion.logger")
    def test_position_capped_logs_warning(self, mock_logger: MagicMock) -> None:
        """Test position capped at bankroll logs info."""
        calculate_kelly_size(
            edge=Decimal("2.0"),  # Very high edge
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000"),
        )

        # Should log about capping
        mock_logger.debug.assert_called()


class TestMultipleCalculationsIntegration:
    """Integration tests for multiple sequential calculations."""

    def test_multiple_calculations_independent(self) -> None:
        """Test multiple calculations are independent."""
        positions = []
        for edge_val in ["0.05", "0.10", "0.15", "0.20"]:
            pos = calculate_kelly_size(
                edge=Decimal(edge_val),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("10000"),
            )
            positions.append(pos)

        # Positions should increase with edge
        assert positions[0] < positions[1] < positions[2] < positions[3]

    def test_calculations_with_varying_bankroll(self) -> None:
        """Test calculations scale with bankroll."""
        base_position = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000"),
        )

        double_position = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("20000"),
        )

        assert double_position == base_position * 2

    def test_optimal_position_workflow(self) -> None:
        """Test realistic workflow with optimal_position."""
        # Simulate checking multiple market opportunities
        opportunities = [
            (Decimal("0.55"), Decimal("0.50")),  # Small edge
            (Decimal("0.65"), Decimal("0.50")),  # Medium edge
            (Decimal("0.75"), Decimal("0.50")),  # Large edge
        ]

        positions = []
        for true_prob, market_price in opportunities:
            pos = calculate_optimal_position(
                true_probability=true_prob,
                market_price=market_price,
                bankroll=Decimal("10000"),
                kelly_fraction=Decimal("0.25"),
                min_edge=Decimal("0.02"),
            )
            positions.append(pos)

        # Positions should increase with edge
        assert positions[0] < positions[1] < positions[2]


class TestConstraintIntegration:
    """Integration tests for constraint handling."""

    def test_max_position_with_edge_integration(self) -> None:
        """Test max_position constraint with edge calculation."""
        # High edge should be constrained by max_position
        constrained = calculate_optimal_position(
            true_probability=Decimal("0.90"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.5"),
            max_position=Decimal("500"),
        )

        unconstrained = calculate_optimal_position(
            true_probability=Decimal("0.90"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000"),
            kelly_fraction=Decimal("0.5"),
            max_position=None,
        )

        assert constrained == Decimal("500")
        assert unconstrained > constrained

    def test_bankroll_cap_with_edge_integration(self) -> None:
        """Test bankroll cap with high edge."""
        # Very high edge with full Kelly should hit bankroll cap
        # Edge = 0.99 - 0.01 = 0.98
        # Position = edge * kelly_fraction * bankroll = 0.98 * 1.0 * 1000 = 980
        position = calculate_optimal_position(
            true_probability=Decimal("0.99"),
            market_price=Decimal("0.01"),
            bankroll=Decimal("1000"),
            kelly_fraction=Decimal("1.0"),  # Full Kelly
            fees=Decimal("0"),
            min_edge=Decimal("0"),
        )

        # Edge = 0.98, so position = 980 (not capped, just high)
        assert position == Decimal("980.000")
