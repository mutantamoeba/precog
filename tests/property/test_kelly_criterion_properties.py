"""
Kelly Criterion Position Sizing - Property-Based Tests
=======================================================
Phase 1.5: Proof-of-Concept for Hypothesis Integration

These tests validate mathematical invariants that MUST hold for ALL inputs.
Property-based testing generates thousands of test cases automatically.

Mathematical Properties Tested:
1. Position size never exceeds bankroll
2. Position size is always non-negative
3. Zero edge → zero position
4. Negative edge → zero position (should not bet)
5. Kelly fraction reduces position size proportionally
6. Position size scales linearly with bankroll
7. Position size increases monotonically with edge

Why This Matters:
- Kelly criterion bugs can cause catastrophic losses
- Oversized positions violate risk management
- Negative edge trades guarantee losses over time
- Traditional example-based tests miss edge cases (edge = 0.9999999?)

Hypothesis generates edge cases humans wouldn't think to test.

Related:
- REQ-TRADE-001: Kelly Criterion Position Sizing
- ADR-TBD: Property-Based Testing Strategy
- Pattern 9: Property-Based Testing (CLAUDE.md)
"""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

# ==============================================================================
# Custom Hypothesis Strategies for Trading Domain
# ==============================================================================


@st.composite
def decimal_price(draw, min_value=0, max_value=1, places=4):
    """
    Generate valid market prices as Decimal.

    Args:
        min_value: Minimum price (default 0 = $0.00)
        max_value: Maximum price (default 1 = $1.00)
        places: Decimal places (default 4 for sub-penny precision)

    Returns:
        Decimal price in range [min_value, max_value]
    """
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def edge_value(draw, min_value=-0.5, max_value=0.5, places=4):
    """
    Generate edge values (difference between true probability and market price).

    Args:
        min_value: Minimum edge (default -0.5 = severely negative)
        max_value: Maximum edge (default 0.5 = highly positive)
        places: Decimal places

    Returns:
        Decimal edge in range [min_value, max_value]
    """
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def kelly_fraction(draw, min_value=0, max_value=1, places=2):
    """
    Generate Kelly fraction (position sizing multiplier).

    Args:
        min_value: Minimum fraction (default 0 = no position)
        max_value: Maximum fraction (default 1 = full Kelly)
        places: Decimal places

    Returns:
        Decimal Kelly fraction in range [0, 1]
    """
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def bankroll_amount(draw, min_value=100, max_value=100000, places=2):
    """
    Generate bankroll amounts.

    Args:
        min_value: Minimum bankroll (default $100)
        max_value: Maximum bankroll (default $100,000)
        places: Decimal places

    Returns:
        Decimal bankroll in range [min_value, max_value]
    """
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


# ==============================================================================
# Import Production Implementation
# ==============================================================================

# Production implementation moved to src/precog/trading/kelly_criterion.py
# This import ensures property tests validate the ACTUAL production code
from precog.trading.kelly_criterion import calculate_kelly_size  # noqa: E402

# ==============================================================================
# Property-Based Tests
# ==============================================================================


@given(
    edge=edge_value(),
    kelly_frac=kelly_fraction(),
    bankroll=bankroll_amount(),
)
def test_position_size_never_exceeds_bankroll(edge, kelly_frac, bankroll):
    """
    PROPERTY: Position size MUST NEVER exceed bankroll.

    This is a CRITICAL safety constraint. Violating this means betting more
    than you have, which would cause margin calls or rejected orders.

    Hypothesis will test thousands of (edge, kelly_frac, bankroll) combinations
    to ensure this invariant ALWAYS holds.
    """
    position_size = calculate_kelly_size(edge, kelly_frac, bankroll)

    assert position_size <= bankroll, f"Position {position_size} exceeds bankroll {bankroll}!"


@given(
    edge=edge_value(),
    kelly_frac=kelly_fraction(),
    bankroll=bankroll_amount(),
)
def test_position_size_always_non_negative(edge, kelly_frac, bankroll):
    """
    PROPERTY: Position size must be >= 0.

    Negative position sizes are nonsensical (you either bet or you don't).

    This tests that our position sizing logic never produces negative values,
    even with negative edges or extreme inputs.
    """
    position_size = calculate_kelly_size(edge, kelly_frac, bankroll)

    assert position_size >= Decimal("0"), f"Position size {position_size} is negative!"


@given(
    kelly_frac=kelly_fraction(),
    bankroll=bankroll_amount(),
)
def test_zero_edge_means_zero_position(kelly_frac, bankroll):
    """
    PROPERTY: Zero edge → zero position size.

    If there's no edge (fair bet), Kelly criterion says don't bet.

    This ensures we're not taking positions when expected value is zero.
    """
    edge = Decimal("0")
    position_size = calculate_kelly_size(edge, kelly_frac, bankroll)

    assert position_size == Decimal("0"), f"Non-zero position {position_size} with zero edge!"


@given(
    edge=edge_value(
        min_value=Decimal("-0.5000"), max_value=Decimal("-0.0100")
    ),  # Only negative edges
    kelly_frac=kelly_fraction(),
    bankroll=bankroll_amount(),
)
def test_negative_edge_means_zero_position(edge, kelly_frac, bankroll):
    """
    PROPERTY: Negative edge → zero position size.

    If edge is negative (market price > true probability), we should NEVER bet.
    Doing so guarantees losses over time.

    This is the MOST CRITICAL property for avoiding catastrophic losses.
    """
    position_size = calculate_kelly_size(edge, kelly_frac, bankroll)

    assert position_size == Decimal("0"), (
        f"Non-zero position {position_size} with negative edge {edge}!"
    )


@given(
    edge=edge_value(
        min_value=Decimal("0.0100"), max_value=Decimal("0.5000")
    ),  # Only positive edges
    bankroll=bankroll_amount(),
)
def test_kelly_fraction_reduces_position_proportionally(edge, bankroll):
    """
    PROPERTY: Halving kelly_fraction should halve position size.

    This tests the linearity of Kelly fraction scaling.

    If full Kelly (1.0) produces position X, then half Kelly (0.5) should
    produce position X/2.
    """
    full_kelly = Decimal("1.0")
    half_kelly = Decimal("0.5")

    full_position = calculate_kelly_size(edge, full_kelly, bankroll)
    half_position = calculate_kelly_size(edge, half_kelly, bankroll)

    # Allow small rounding errors (±0.01)
    expected_half = full_position / Decimal("2")
    tolerance = Decimal("0.01")

    assert abs(half_position - expected_half) <= tolerance, (
        f"Half Kelly position {half_position} != Full Kelly {full_position} / 2 "
        f"(expected ~{expected_half})"
    )


@given(
    edge=edge_value(
        min_value=Decimal("0.0100"), max_value=Decimal("0.5000")
    ),  # Only positive edges
    kelly_frac=kelly_fraction(min_value=Decimal("0.10"), max_value=Decimal("0.50")),  # Exclude zero
)
def test_position_size_scales_linearly_with_bankroll(edge, kelly_frac):
    """
    PROPERTY: Doubling bankroll should double position size.

    This tests the linearity of bankroll scaling.

    If bankroll B produces position X, then bankroll 2B should produce
    position 2X (assuming no max_position constraint).
    """
    bankroll_1 = Decimal("1000")
    bankroll_2 = Decimal("2000")

    position_1 = calculate_kelly_size(edge, kelly_frac, bankroll_1)
    position_2 = calculate_kelly_size(edge, kelly_frac, bankroll_2)

    # Allow small rounding errors
    expected_double = position_1 * Decimal("2")
    tolerance = Decimal("0.01")

    assert abs(position_2 - expected_double) <= tolerance, (
        f"Double bankroll position {position_2} != 2 * original {position_1} "
        f"(expected ~{expected_double})"
    )


@given(
    kelly_frac=kelly_fraction(min_value=Decimal("0.10"), max_value=Decimal("0.50")),
    bankroll=bankroll_amount(),
)
def test_position_increases_monotonically_with_edge(kelly_frac, bankroll):
    """
    PROPERTY: Increasing edge should increase (or maintain) position size.

    If edge1 < edge2, then position(edge1) <= position(edge2).

    This tests that our position sizing logic correctly responds to
    better opportunities.
    """
    edge_low = Decimal("0.05")
    edge_high = Decimal("0.10")

    position_low = calculate_kelly_size(edge_low, kelly_frac, bankroll)
    position_high = calculate_kelly_size(edge_high, kelly_frac, bankroll)

    assert position_high >= position_low, (
        f"Higher edge {edge_high} produced smaller position {position_high} "
        f"than lower edge {edge_low} with position {position_low}"
    )


@given(
    edge=edge_value(min_value=Decimal("0.0100"), max_value=Decimal("0.5000")),
    kelly_frac=kelly_fraction(),
    bankroll=bankroll_amount(),
    max_pos=bankroll_amount(min_value=Decimal("10.00"), max_value=Decimal("500.00")),
)
def test_max_position_constraint_respected(edge, kelly_frac, bankroll, max_pos):
    """
    PROPERTY: Position size never exceeds max_position limit.

    Risk management often imposes maximum position sizes to limit exposure.

    This ensures that even when Kelly formula suggests large bet, we respect
    the max_position constraint.
    """
    position_size = calculate_kelly_size(edge, kelly_frac, bankroll, max_position=max_pos)

    assert position_size <= max_pos, f"Position {position_size} exceeds max_position {max_pos}!"


@given(
    bankroll=bankroll_amount(),
)
def test_kelly_fraction_outside_valid_range_raises_error(bankroll):
    """
    PROPERTY: kelly_fraction outside [0, 1] should raise ValueError.

    Kelly fractions > 1 (over-betting) or < 0 (nonsensical) should be rejected
    at the configuration level.
    """
    edge = Decimal("0.10")
    invalid_fraction = Decimal("1.5")  # Over-betting

    try:
        calculate_kelly_size(edge, invalid_fraction, bankroll)
        # If we reach here, test failed - should have raised ValueError
        raise AssertionError(f"kelly_fraction {invalid_fraction} should have raised ValueError!")
    except ValueError as e:
        # Expected - test passes
        assert "kelly_fraction must be in [0, 1]" in str(e)


@given(
    edge=edge_value(),
    kelly_frac=kelly_fraction(),
)
def test_negative_bankroll_raises_error(edge, kelly_frac):
    """
    PROPERTY: Negative bankroll should raise ValueError.

    Cannot have negative capital (debt-funded trading not supported).
    """
    negative_bankroll = Decimal("-1000")

    try:
        calculate_kelly_size(edge, kelly_frac, negative_bankroll)
        raise AssertionError("Negative bankroll should have raised ValueError!")
    except ValueError as e:
        assert "bankroll cannot be negative" in str(e)


# ==============================================================================
# Statistical Properties (Advanced)
# ==============================================================================


@given(
    edge=edge_value(min_value=Decimal("0.0100"), max_value=Decimal("0.3000")),
    kelly_frac=kelly_fraction(min_value=Decimal("0.20"), max_value=Decimal("0.50")),
    bankroll=bankroll_amount(min_value=Decimal("1000.00"), max_value=Decimal("10000.00")),
)
def test_position_size_reasonable_bounds(edge, kelly_frac, bankroll):
    """
    PROPERTY: Position size should be "reasonable" relative to edge.

    For typical edges (1-30%) and conservative Kelly fractions (20-50%),
    position sizes should be a reasonable percentage of bankroll.

    This is a sanity check - if position = 99% of bankroll with edge = 1%,
    something is very wrong.
    """
    position_size = calculate_kelly_size(edge, kelly_frac, bankroll)

    # Position as percentage of bankroll
    position_pct = (position_size / bankroll) if bankroll > 0 else Decimal("0")

    # Heuristic: Position should be roughly edge * kelly_fraction
    expected_pct = edge * kelly_frac
    tolerance_multiplier = Decimal("1.5")  # Allow 50% deviation

    assert position_pct <= expected_pct * tolerance_multiplier, (
        f"Position {position_size} ({position_pct * 100}% of bankroll) seems too large "
        f"for edge {edge} ({edge * 100}%) and Kelly fraction {kelly_frac}"
    )


# ==============================================================================
# Test Summary
# ==============================================================================
"""
Hypothesis Configuration (from pyproject.toml):
- max_examples = 100 (default) → Will test 100 random inputs per property
- deadline = 400ms per example
- verbosity = "normal"

To run with statistics:
    pytest tests/property/test_kelly_criterion_properties.py -v --hypothesis-show-statistics

Expected Output:
    11 tests, each testing 100+ generated examples = 1100+ test cases total!

Coverage:
- 11 properties tested
- Edge cases automatically discovered by Hypothesis
- Constraint violations caught before production

Next Steps (Phase 1.5):
1. Add property tests for edge detection (test_edge_detection_properties.py)
2. Add property tests for model validation (test_model_validation_properties.py)
3. Add property tests for order book analysis (test_order_book_properties.py)
4. Add property tests for position management (test_position_management_properties.py)

See: docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md (to be created)
"""
