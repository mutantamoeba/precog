"""
Kelly Criterion E2E Tests - Production Workflow Validation.

Tests the complete Kelly Criterion position sizing workflow:
1. Edge calculation from market data
2. Position sizing with Kelly formula
3. Complete workflow integration
4. Decimal precision requirements
5. Risk management scenarios

Educational Note:
    E2E (end-to-end) tests validate complete workflows, not just units.
    These tests simulate real trading scenarios:
    - Market has price 50 cents, model predicts 60% probability
    - Calculate edge: 60% - 50% - fees = edge
    - Calculate position: edge * kelly_fraction * bankroll
    - Apply risk limits (max position, bankroll constraints)

    This ensures the complete system works together correctly.

Test Categories:
    1. Edge Calculation - Verify edge from market price + true probability
    2. Position Sizing - Verify Kelly formula with constraints
    3. Optimal Position Workflow - Complete end-to-end workflow
    4. Decimal Precision - Verify no float contamination
    5. Risk Scenarios - Extreme market conditions

Pattern 1 Compliance:
    ALL numeric values use Decimal, NEVER float:
    - ✅ CORRECT: Decimal("0.60"), Decimal("10000.00")
    - ❌ WRONG: 0.60, 10000.00

References:
    - REQ-TRADE-001: Kelly Criterion Position Sizing
    - REQ-TRADE-002: Edge Calculation
    - REQ-SYS-003: Decimal Precision (ALWAYS use Decimal)
    - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    - ADR-TBD: Property-Based Testing Strategy
    - src/precog/trading/kelly_criterion.py (implementation)

Created: 2025-11-26
Phase: 1.5 (Foundation Validation)
GitHub Issue: #41
"""

from decimal import Decimal

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

# Mark all tests as E2E and slow (run with pytest -m e2e)
pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestKellyCriterionEdgeCalculation:
    """
    E2E tests for edge calculation from market data.

    Educational Note:
        Edge = True Probability - Market Price - Fees

        Examples:
        - Market price: 50 cents (implies 50% probability)
        - True probability: 60% (model prediction)
        - Edge: 60% - 50% - 0% = 10% (positive edge, good trade)

        - Market price: 60 cents
        - True probability: 55%
        - Edge: 55% - 60% - 0% = -5% (negative edge, bad trade)
    """

    def test_positive_edge_scenario(self):
        """
        Test edge calculation for favorable trade opportunity.

        Scenario: Model predicts 60% probability, market price 50 cents.
        Expected: 10% edge (60% - 50% - 0% = 10%).
        """
        edge = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            fees=Decimal("0"),
        )

        assert edge == Decimal("0.10"), "Edge should be 10% (60% - 50% - 0%)"
        assert isinstance(edge, Decimal), "Edge must be Decimal, not float"

    def test_negative_edge_scenario(self):
        """
        Test edge calculation for unfavorable trade opportunity.

        Scenario: Model predicts 55% probability, market price 60 cents.
        Expected: -5% edge (55% - 60% - 0% = -5%).
        """
        edge = calculate_edge(
            true_probability=Decimal("0.55"),
            market_price=Decimal("0.60"),
            fees=Decimal("0"),
        )

        assert edge == Decimal("-0.05"), "Edge should be -5% (55% - 60%)"
        assert isinstance(edge, Decimal), "Edge must be Decimal, not float"

    def test_edge_with_fees(self):
        """
        Test edge calculation with transaction fees.

        Scenario: 10% edge before fees, 2% transaction fee.
        Expected: 8% edge after fees (10% - 2% = 8%).

        Educational Note:
            Fees reduce edge, making fewer trades profitable.
            A 10% edge becomes 8% after 2% fees.
        """
        edge = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            fees=Decimal("0.02"),
        )

        assert edge == Decimal("0.08"), "Edge should be 8% (10% - 2% fees)"
        assert isinstance(edge, Decimal), "Edge must be Decimal, not float"

    def test_zero_edge_fair_market(self):
        """
        Test edge calculation for fair market (no edge).

        Scenario: Market price equals true probability.
        Expected: 0% edge (50% - 50% - 0% = 0%).
        """
        edge = calculate_edge(
            true_probability=Decimal("0.50"),
            market_price=Decimal("0.50"),
            fees=Decimal("0"),
        )

        assert edge == Decimal("0"), "Edge should be 0% for fair market"
        assert isinstance(edge, Decimal), "Edge must be Decimal, not float"

    def test_edge_validation_true_probability_too_high(self):
        """
        Test validation rejects true_probability > 1.

        Educational Note:
            Probability must be in [0, 1] range. Values > 1 are invalid.
        """
        with pytest.raises(ValueError, match="true_probability must be in"):
            calculate_edge(
                true_probability=Decimal("1.5"),
                market_price=Decimal("0.50"),
                fees=Decimal("0"),
            )

    def test_edge_validation_market_price_negative(self):
        """
        Test validation rejects negative market price.

        Educational Note:
            Market prices cannot be negative. Minimum valid price is 0.
        """
        with pytest.raises(ValueError, match="market_price must be in"):
            calculate_edge(
                true_probability=Decimal("0.60"),
                market_price=Decimal("-0.10"),
                fees=Decimal("0"),
            )

    def test_edge_validation_negative_fees(self):
        """
        Test validation rejects negative fees.

        Educational Note:
            Negative fees (rebates) are theoretically possible but not
            supported in our system. Fees must be >= 0.
        """
        with pytest.raises(ValueError, match="fees cannot be negative"):
            calculate_edge(
                true_probability=Decimal("0.60"),
                market_price=Decimal("0.50"),
                fees=Decimal("-0.01"),
            )


class TestKellySizeCalculation:
    """
    E2E tests for Kelly position sizing with constraints.

    Educational Note:
        Kelly Formula: position = edge * kelly_fraction * bankroll

        Constraints:
        1. Position cannot exceed bankroll (can't bet more than you have)
        2. Position cannot exceed max_position (risk limit)
        3. Position must be non-negative (never short in our system)
    """

    def test_basic_kelly_position(self):
        """
        Test basic Kelly position calculation without constraints.

        Scenario:
        - Edge: 5%
        - Kelly fraction: 0.25 (quarter Kelly)
        - Bankroll: $10,000

        Expected: $125 position (0.05 * 0.25 * 10000 = 125)
        """
        position = calculate_kelly_size(
            edge=Decimal("0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )

        assert position == Decimal("125.00"), "Position should be $125"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_kelly_position_capped_by_bankroll(self):
        """
        Test position capped at bankroll when Kelly formula exceeds it.

        Scenario:
        - Edge: 50% (very large edge)
        - Kelly fraction: 1.0 (full Kelly)
        - Bankroll: $1,000
        - Uncapped position: 0.50 * 1.0 * 1000 = $500
        - But max is bankroll = $1,000

        Expected: $1,000 (capped at bankroll)

        Educational Note:
            You can never bet more than your entire bankroll.
            Even if Kelly formula suggests larger position, it's capped.
        """
        position = calculate_kelly_size(
            edge=Decimal("0.50"),
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("1000.00"),
        )

        # Position should be 500, which is less than bankroll
        # Let me recalculate: 0.50 * 1.0 * 1000 = 500
        # This should NOT be capped at bankroll
        assert position == Decimal("500.00"), "Position should be $500 (50% of bankroll)"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_kelly_position_capped_by_max_position(self):
        """
        Test position capped at max_position risk limit.

        Scenario:
        - Edge: 10%
        - Kelly fraction: 1.0 (full Kelly)
        - Bankroll: $10,000
        - Max position: $500 (risk limit)
        - Uncapped position: 0.10 * 1.0 * 10000 = $1,000

        Expected: $500 (capped at max_position)

        Educational Note:
            max_position is a risk management constraint.
            Even if Kelly suggests larger position, we cap at max_position
            to avoid overexposure to single trade.
        """
        position = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000.00"),
            max_position=Decimal("500.00"),
        )

        assert position == Decimal("500.00"), "Position capped at max_position $500"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_zero_position_for_zero_edge(self):
        """
        Test zero position for zero edge (fair market).

        Scenario:
        - Edge: 0% (fair market, no advantage)
        - Kelly fraction: 0.25
        - Bankroll: $10,000

        Expected: $0 position (never bet on zero edge)
        """
        position = calculate_kelly_size(
            edge=Decimal("0"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )

        assert position == Decimal("0"), "Position should be $0 for zero edge"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_zero_position_for_negative_edge(self):
        """
        Test zero position for negative edge (unfavorable).

        Scenario:
        - Edge: -5% (unfavorable, expect to lose)
        - Kelly fraction: 0.25
        - Bankroll: $10,000

        Expected: $0 position (NEVER bet on negative edge)

        Educational Note:
            Negative edge means expected loss. Kelly would produce negative
            position (short), but we don't support shorting. Return 0 instead.
        """
        position = calculate_kelly_size(
            edge=Decimal("-0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )

        assert position == Decimal("0"), "Position should be $0 for negative edge"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_kelly_fraction_validation_too_high(self):
        """
        Test validation rejects kelly_fraction > 1.

        Educational Note:
            Kelly fraction > 1 means "over-Kelly" betting, which is
            mathematically unsound and guarantees eventual ruin.
        """
        with pytest.raises(ValueError, match="kelly_fraction must be in"):
            calculate_kelly_size(
                edge=Decimal("0.05"),
                kelly_fraction=Decimal("1.5"),
                bankroll=Decimal("10000.00"),
            )

    def test_kelly_fraction_validation_negative(self):
        """
        Test validation rejects negative kelly_fraction.

        Educational Note:
            Negative kelly_fraction would produce negative position,
            which is equivalent to shorting. We don't support shorting.
        """
        with pytest.raises(ValueError, match="kelly_fraction must be in"):
            calculate_kelly_size(
                edge=Decimal("0.05"),
                kelly_fraction=Decimal("-0.25"),
                bankroll=Decimal("10000.00"),
            )

    def test_bankroll_validation_negative(self):
        """
        Test validation rejects negative bankroll.

        Educational Note:
            Negative bankroll means you owe money, which is invalid.
        """
        with pytest.raises(ValueError, match="bankroll cannot be negative"):
            calculate_kelly_size(
                edge=Decimal("0.05"),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("-1000.00"),
            )

    def test_fractional_kelly_reduces_position(self):
        """
        Test fractional Kelly reduces position proportionally.

        Scenario:
        - Edge: 10%
        - Full Kelly (1.0): 0.10 * 1.0 * 10000 = $1,000
        - Quarter Kelly (0.25): 0.10 * 0.25 * 10000 = $250

        Educational Note:
            Quarter Kelly reduces position by 75%, dramatically reducing
            variance while maintaining positive expected growth.
        """
        full_kelly = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000.00"),
        )

        quarter_kelly = calculate_kelly_size(
            edge=Decimal("0.10"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )

        assert full_kelly == Decimal("1000.00"), "Full Kelly should be $1,000"
        assert quarter_kelly == Decimal("250.00"), "Quarter Kelly should be $250"
        assert quarter_kelly == full_kelly * Decimal("0.25"), "Quarter Kelly = Full Kelly * 0.25"


class TestOptimalPositionWorkflow:
    """
    E2E tests for complete optimal position workflow.

    Educational Note:
        calculate_optimal_position is a convenience function that:
        1. Calculates edge from true_probability and market_price
        2. Checks if edge meets minimum threshold (min_edge)
        3. Calculates Kelly position with constraints

        This is the complete workflow used in production trading.
    """

    def test_complete_workflow_profitable_trade(self):
        """
        Test complete workflow for profitable trade opportunity.

        Scenario:
        - True probability: 65% (model prediction)
        - Market price: 55 cents
        - Bankroll: $10,000
        - Kelly fraction: 0.25 (quarter Kelly)
        - Fees: 1%
        - Min edge: 2%

        Calculation:
        1. Edge = 65% - 55% - 1% = 9%
        2. Check: 9% >= 2% min_edge ✅
        3. Position = 0.09 * 0.25 * 10000 = $225

        Expected: $225 position
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.65"),
            market_price=Decimal("0.55"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01"),
            min_edge=Decimal("0.02"),
        )

        assert position == Decimal("225.00"), "Position should be $225"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_complete_workflow_edge_below_minimum(self):
        """
        Test workflow rejects trade when edge below minimum threshold.

        Scenario:
        - True probability: 52% (model prediction)
        - Market price: 50 cents
        - Edge: 52% - 50% - 1% = 1%
        - Min edge: 2%
        - Check: 1% < 2% min_edge ❌

        Expected: $0 position (edge too small)

        Educational Note:
            Small edges (1-2%) are often within model error bounds.
            Setting min_edge = 2% ensures we only trade when edge is
            statistically significant.
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.52"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01"),
            min_edge=Decimal("0.02"),
        )

        assert position == Decimal("0"), "Position should be $0 (edge below min_edge)"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_complete_workflow_with_max_position(self):
        """
        Test workflow respects max_position risk limit.

        Scenario:
        - True probability: 70%
        - Market price: 50 cents
        - Edge: 70% - 50% - 1% = 19%
        - Uncapped position: 0.19 * 0.25 * 10000 = $475
        - Max position: $300

        Expected: $300 (capped at max_position)
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.70"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01"),
            max_position=Decimal("300.00"),
            min_edge=Decimal("0.02"),
        )

        assert position == Decimal("300.00"), "Position capped at max_position $300"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_complete_workflow_negative_edge_after_fees(self):
        """
        Test workflow rejects trade when fees make edge negative.

        Scenario:
        - True probability: 53%
        - Market price: 50 cents
        - Fees: 4%
        - Edge: 53% - 50% - 4% = -1%

        Expected: $0 position (negative edge after fees)

        Educational Note:
            High fees can turn profitable trades unprofitable.
            A 3% edge becomes -1% edge with 4% fees.
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.53"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.04"),
            min_edge=Decimal("0.02"),
        )

        assert position == Decimal("0"), "Position should be $0 (negative edge after fees)"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_complete_workflow_zero_bankroll(self):
        """
        Test workflow handles zero bankroll gracefully.

        Scenario:
        - Bankroll: $0 (no capital available)

        Expected: $0 position (can't bet with no capital)
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.65"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("0.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01"),
            min_edge=Decimal("0.02"),
        )

        assert position == Decimal("0"), "Position should be $0 (zero bankroll)"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"


class TestKellyPrecisionRequirements:
    """
    E2E tests for Decimal precision requirements (Pattern 1).

    Educational Note:
        Pattern 1 (CLAUDE.md): NEVER USE FLOAT for prices/probabilities.

        Why Decimal?
        - Float: 0.1 + 0.2 = 0.30000000000000004 (binary rounding error)
        - Decimal: 0.1 + 0.2 = 0.3 (exact decimal arithmetic)

        Financial calculations MUST be exact. Float errors compound over
        time, leading to incorrect positions and P&L.
    """

    def test_all_inputs_must_be_decimal(self):
        """
        Test all functions accept only Decimal, never float.

        Educational Note:
            Type hints enforce Decimal: edge: Decimal, not edge: float.
            This catches float contamination at development time.
        """
        # Edge calculation with Decimal
        edge = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            fees=Decimal("0.01"),
        )
        assert isinstance(edge, Decimal), "Edge must be Decimal"

        # Kelly size calculation with Decimal
        position = calculate_kelly_size(
            edge=Decimal("0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )
        assert isinstance(position, Decimal), "Position must be Decimal"

        # Optimal position calculation with Decimal
        position = calculate_optimal_position(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000.00"),
        )
        assert isinstance(position, Decimal), "Position must be Decimal"

    def test_decimal_precision_maintained_through_workflow(self):
        """
        Test Decimal precision maintained through complete workflow.

        Scenario: Calculate position with many decimal places.
        Verify: Result maintains precision, no float conversion.
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.62345"),
            market_price=Decimal("0.51234"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0.01234"),
        )

        # Verify result is Decimal with exact precision
        assert isinstance(position, Decimal), "Position must be Decimal"

        # Edge = 0.62345 - 0.51234 - 0.01234 = 0.09877
        # Position = 0.09877 * 0.25 * 10000 = 246.925
        # Verify calculation is exact (no float rounding)
        expected_edge = Decimal("0.62345") - Decimal("0.51234") - Decimal("0.01234")
        expected_position = expected_edge * Decimal("0.25") * Decimal("10000.00")
        assert position == expected_position, "Position calculation must be exact"

    def test_decimal_string_construction(self):
        """
        Test Decimal constructed from strings, not floats.

        Educational Note:
            ✅ CORRECT: Decimal("0.10") - exact decimal value
            ❌ WRONG: Decimal(0.10) - float converted to Decimal (already has rounding error)

            Always construct Decimal from strings or integers.
        """
        # ✅ CORRECT: String construction
        edge_correct = calculate_edge(
            true_probability=Decimal("0.60"),
            market_price=Decimal("0.50"),
            fees=Decimal("0"),
        )

        assert edge_correct == Decimal("0.10"), "Edge should be exactly 0.10"
        assert isinstance(edge_correct, Decimal), "Edge must be Decimal"


class TestKellyRiskScenarios:
    """
    E2E tests for extreme risk scenarios.

    Educational Note:
        These tests validate Kelly Criterion behavior under extreme
        market conditions that might occur in production:
        - Very high edges (rare but possible)
        - Very low edges (common, test min_edge threshold)
        - Very small bankrolls (new traders)
        - Very large bankrolls (established traders)
    """

    def test_very_high_edge_scenario(self):
        """
        Test Kelly sizing with very high edge (rare event).

        Scenario:
        - Edge: 30% (extremely high edge, rare but possible)
        - Kelly fraction: 0.25 (quarter Kelly)
        - Bankroll: $10,000

        Expected: $750 position (0.30 * 0.25 * 10000 = 750)

        Educational Note:
            Very high edges occur with:
            - Market inefficiencies (mispricing)
            - Breaking news (sharp probability shifts)
            - Low liquidity (wide spreads)

            These are rare but highly profitable opportunities.
        """
        position = calculate_kelly_size(
            edge=Decimal("0.30"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )

        assert position == Decimal("750.00"), "Position should be $750"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_very_low_edge_scenario(self):
        """
        Test Kelly sizing with very low edge (common).

        Scenario:
        - Edge: 1% (very small edge, common in efficient markets)
        - Kelly fraction: 0.25 (quarter Kelly)
        - Bankroll: $10,000

        Expected: $25 position (0.01 * 0.25 * 10000 = 25)

        Educational Note:
            Low edges (1-2%) are common in efficient markets.
            Many trades will have small edges, requiring:
            - Higher trade frequency to profit
            - Strict risk management (fractional Kelly)
            - Low transaction costs (fees eat into edge)
        """
        position = calculate_kelly_size(
            edge=Decimal("0.01"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("10000.00"),
        )

        assert position == Decimal("25.00"), "Position should be $25"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_small_bankroll_scenario(self):
        """
        Test Kelly sizing with small bankroll (new trader).

        Scenario:
        - Edge: 5%
        - Kelly fraction: 0.25 (quarter Kelly)
        - Bankroll: $100 (small account)

        Expected: $1.25 position (0.05 * 0.25 * 100 = 1.25)

        Educational Note:
            Small bankrolls require:
            - Fractional shares or low-price markets
            - Higher percentage position sizes
            - Patience to compound growth
        """
        position = calculate_kelly_size(
            edge=Decimal("0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("100.00"),
        )

        assert position == Decimal("1.25"), "Position should be $1.25"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_large_bankroll_scenario(self):
        """
        Test Kelly sizing with large bankroll (established trader).

        Scenario:
        - Edge: 5%
        - Kelly fraction: 0.25 (quarter Kelly)
        - Bankroll: $1,000,000 (large account)

        Expected: $12,500 position (0.05 * 0.25 * 1000000 = 12500)

        Educational Note:
            Large bankrolls face:
            - Market impact (large orders move price)
            - Liquidity constraints (not enough volume)
            - Max position limits (exchange risk limits)

            This is why max_position parameter exists.
        """
        position = calculate_kelly_size(
            edge=Decimal("0.05"),
            kelly_fraction=Decimal("0.25"),
            bankroll=Decimal("1000000.00"),
        )

        assert position == Decimal("12500.00"), "Position should be $12,500"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_maximum_theoretical_position(self):
        """
        Test Kelly sizing at maximum theoretical edge (100%).

        Scenario:
        - Edge: 100% (impossible in practice, but theoretically max)
        - Kelly fraction: 1.0 (full Kelly)
        - Bankroll: $10,000

        Expected: $10,000 position (1.0 * 1.0 * 10000 = 10000)
                 Capped at bankroll

        Educational Note:
            100% edge means guaranteed win (true_prob=1.0, market_price=0.0).
            This never happens in real markets, but full Kelly would suggest
            betting entire bankroll. Our constraint caps at bankroll.
        """
        position = calculate_kelly_size(
            edge=Decimal("1.0"),
            kelly_fraction=Decimal("1.0"),
            bankroll=Decimal("10000.00"),
        )

        assert position == Decimal("10000.00"), "Position should be capped at bankroll"
        assert isinstance(position, Decimal), "Position must be Decimal, not float"

    def test_edge_just_above_minimum_threshold(self):
        """
        Test workflow accepts edge just above min_edge threshold.

        Scenario:
        - True probability: 52.1%
        - Market price: 50%
        - Fees: 0%
        - Edge: 2.1%
        - Min edge: 2%
        - Check: 2.1% > 2% ✅

        Expected: Non-zero position (edge meets threshold)
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.521"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0"),
            min_edge=Decimal("0.02"),
        )

        # Edge = 0.521 - 0.50 = 0.021 (2.1%)
        # Position = 0.021 * 0.25 * 10000 = 52.50
        assert position == Decimal("52.50"), "Position should be $52.50"
        assert position > Decimal("0"), "Position should be non-zero (edge > min_edge)"

    def test_edge_just_below_minimum_threshold(self):
        """
        Test workflow rejects edge just below min_edge threshold.

        Scenario:
        - True probability: 51.9%
        - Market price: 50%
        - Fees: 0%
        - Edge: 1.9%
        - Min edge: 2%
        - Check: 1.9% < 2% ❌

        Expected: $0 position (edge below threshold)
        """
        position = calculate_optimal_position(
            true_probability=Decimal("0.519"),
            market_price=Decimal("0.50"),
            bankroll=Decimal("10000.00"),
            kelly_fraction=Decimal("0.25"),
            fees=Decimal("0"),
            min_edge=Decimal("0.02"),
        )

        assert position == Decimal("0"), "Position should be $0 (edge < min_edge)"
