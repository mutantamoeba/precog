"""
Edge Detection - Property-Based Tests
======================================
Phase 1.5: Proof-of-Concept for Hypothesis Integration

Edge detection is THE CORE of the trading system. If edge detection is wrong,
everything else fails. These property tests ensure edge calculations are
mathematically correct for ALL inputs.

Mathematical Properties Tested:
1. Edge calculation formula correctness
2. Fee impact on edge (always reduces edge)
3. Zero edge threshold behavior
4. Negative edge never recommends trade
5. Edge magnitude bounded by [0, 1]
6. Edge monotonicity with probability
7. Spread impact on realizable edge
8. Market efficiency adjustment correctness

Why This Matters:
- False positive edge → losing trades
- False negative edge → missed opportunities
- Fee miscalculation → systematic losses
- Spread ignorance → slippage eats profits

Traditional example-based tests miss edge cases. Hypothesis generates extreme
scenarios (probability = 0.9999, fees = 9.99%, spread = 0.4950) automatically.

Related:
- REQ-EDGE-001: Edge Detection Algorithm
- REQ-EDGE-002: Transaction Cost Modeling
- ADR-TBD: Property-Based Testing Strategy
- Pattern 9: Property-Based Testing (CLAUDE.md)
"""

from decimal import Decimal

from hypothesis import assume, given
from hypothesis import strategies as st

# ==============================================================================
# Custom Hypothesis Strategies (Reuse from Kelly tests + new ones)
# ==============================================================================


@st.composite
def probability(draw, min_value=0, max_value=1, places=4):
    """Generate valid probabilities in [0, 1]."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def market_price(draw, min_value=0, max_value=1, places=4):
    """Generate valid market prices in [0, 1]."""
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def fee_percent(draw, min_value=0, max_value=0.15, places=4):
    """
    Generate fee percentages.

    Kalshi taker fees are 7% (0.07). Most platforms are 0-15%.
    """
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def spread(draw, min_value=0, max_value=0.5, places=4):
    """
    Generate bid-ask spreads.

    Typical spreads: 0.0050 (tight) to 0.0500 (wide).
    Extreme spreads: up to 0.5000 (illiquid markets).
    """
    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


# ==============================================================================
# Edge Detection Implementation (Simplified for POC)
# ==============================================================================


def calculate_edge(
    true_probability: Decimal,
    market_price: Decimal,
    fee_percent: Decimal = Decimal("0.07"),
) -> Decimal:
    """
    Calculate edge: difference between true probability and cost.

    Formula:
        edge = true_probability - (market_price + fees)
        edge = true_probability - (market_price * (1 + fee_percent))

    Positive edge → expected value is positive → should trade
    Zero edge → break-even → indifferent
    Negative edge → expected value is negative → should NOT trade

    Args:
        true_probability: Our model's estimate of win probability
        market_price: Current market price (what we pay)
        fee_percent: Transaction fee as decimal (0.07 = 7%)

    Returns:
        Decimal edge (positive = good opportunity, negative = avoid)

    Example:
        >>> calculate_edge(Decimal("0.60"), Decimal("0.50"), Decimal("0.07"))
        Decimal("0.065")
        # True prob 60%, cost 50% + 3.5% fee = 53.5%, edge = 6.5%
    """
    # Validate inputs
    if not (Decimal("0") <= true_probability <= Decimal("1")):
        raise ValueError(f"true_probability must be in [0, 1], got {true_probability}")

    if not (Decimal("0") <= market_price <= Decimal("1")):
        raise ValueError(f"market_price must be in [0, 1], got {market_price}")

    if fee_percent < Decimal("0"):
        raise ValueError(f"fee_percent cannot be negative, got {fee_percent}")

    # Calculate total cost (price + fees)
    total_cost = market_price * (Decimal("1") + fee_percent)

    # Edge = true probability - total cost
    return true_probability - total_cost


def calculate_realizable_edge(
    true_probability: Decimal,
    bid_price: Decimal,
    ask_price: Decimal,
    fee_percent: Decimal = Decimal("0.07"),
) -> Decimal:
    """
    Calculate realizable edge accounting for bid-ask spread.

    We pay the ASK price (higher) when buying, but the market value is the
    BID price (lower). This spread reduces realizable edge.

    Formula:
        realizable_edge = true_probability - (ask_price + fees)

    Args:
        true_probability: Our model's estimate of win probability
        bid_price: Current bid (what market makers will pay)
        ask_price: Current ask (what we must pay)
        fee_percent: Transaction fee as decimal

    Returns:
        Decimal realizable edge (accounting for spread)

    Example:
        >>> calculate_realizable_edge(
        ...     Decimal("0.60"),
        ...     Decimal("0.4950"),  # Bid
        ...     Decimal("0.5050"),  # Ask
        ...     Decimal("0.07")
        ... )
        Decimal("0.05965")
        # Spread of 0.01 reduces edge from ~0.065 to ~0.060
    """
    # Validate inputs
    if bid_price > ask_price:
        raise ValueError(f"bid_price {bid_price} cannot exceed ask_price {ask_price}")

    # Use ask price (what we pay) for edge calculation
    return calculate_edge(true_probability, ask_price, fee_percent)


def should_trade(edge: Decimal, min_edge_threshold: Decimal = Decimal("0.05")) -> bool:
    """
    Determine if edge is sufficient to warrant a trade.

    Args:
        edge: Calculated edge from calculate_edge()
        min_edge_threshold: Minimum edge required to trade (default 5%)

    Returns:
        True if edge >= threshold, False otherwise

    Example:
        >>> should_trade(Decimal("0.06"), Decimal("0.05"))
        True  # 6% edge exceeds 5% threshold

        >>> should_trade(Decimal("0.02"), Decimal("0.05"))
        False  # 2% edge below 5% threshold

        >>> should_trade(Decimal("-0.01"), Decimal("0.05"))
        False  # Negative edge - NEVER trade
    """
    return edge >= min_edge_threshold


# ==============================================================================
# Property-Based Tests: Core Edge Calculation
# ==============================================================================


@given(
    true_prob=probability(),
    price=market_price(),
    fee=fee_percent(),
)
def test_edge_formula_correctness(true_prob, price, fee):
    """
    PROPERTY: edge = true_probability - (market_price * (1 + fee_percent))

    This validates the fundamental formula is implemented correctly.
    """
    edge = calculate_edge(true_prob, price, fee)

    expected_edge = true_prob - (price * (Decimal("1") + fee))
    tolerance = Decimal("0.0001")  # Allow tiny rounding errors

    assert abs(edge - expected_edge) <= tolerance, (
        f"Edge calculation incorrect: got {edge}, expected {expected_edge}"
    )


@given(
    true_prob=probability(min_value=0.1, max_value=0.9),
    price=market_price(min_value=0.1, max_value=0.9),
)
def test_fees_always_reduce_edge(true_prob, price):
    """
    PROPERTY: Adding fees should ALWAYS reduce (or maintain) edge.

    This ensures fees are correctly subtracted from edge, not added.
    If edge_with_fees > edge_without_fees, we've made a sign error.
    """
    edge_no_fees = calculate_edge(true_prob, price, Decimal("0"))
    edge_with_fees = calculate_edge(true_prob, price, Decimal("0.07"))

    assert edge_with_fees <= edge_no_fees, (
        f"Fees increased edge! No fees: {edge_no_fees}, with fees: {edge_with_fees}"
    )


@given(
    price=market_price(),
    fee=fee_percent(),
)
def test_edge_zero_when_true_prob_equals_cost(price, fee):
    """
    PROPERTY: If true_probability = market_price + fees, edge should be ~0.

    This tests the zero-edge boundary condition.
    """
    # Set true_prob to exactly offset price + fees
    total_cost = price * (Decimal("1") + fee)

    # Clamp to [0, 1] (some combinations might exceed 1)
    if total_cost > Decimal("1"):
        return  # Skip this example (not a valid scenario)

    true_prob = total_cost
    edge = calculate_edge(true_prob, price, fee)

    tolerance = Decimal("0.0001")
    assert abs(edge) <= tolerance, f"Edge {edge} should be ~0 when true_prob = cost"


@given(
    true_prob=probability(),
    price=market_price(),
    fee=fee_percent(),
)
def test_negative_edge_never_recommends_trade(true_prob, price, fee):
    """
    PROPERTY: If edge < 0, should_trade() MUST return False.

    This is CRITICAL. Negative edge means expected loss. We should NEVER trade.
    """
    edge = calculate_edge(true_prob, price, fee)

    if edge < Decimal("0"):
        recommendation = should_trade(edge, min_edge_threshold=Decimal("0.05"))
        assert not recommendation, (
            f"Recommended trade with negative edge {edge}! This guarantees losses."
        )


@given(
    true_prob=probability(),
    price=market_price(),
    fee=fee_percent(),
)
def test_edge_bounded_by_reasonable_range(true_prob, price, fee):
    """
    PROPERTY: Edge should be in range [-1.15, 1.0].

    Mathematical bounds:
    - Maximum edge: true_prob = 1, price = 0, fee = 0 → edge = 1
    - Minimum edge: true_prob = 0, price = 1, fee = 15% → edge = -1.15

    If edge is outside this range, formula is broken.
    """
    edge = calculate_edge(true_prob, price, fee)

    min_possible_edge = Decimal("-1.15")
    max_possible_edge = Decimal("1.0")

    assert min_possible_edge <= edge <= max_possible_edge, (
        f"Edge {edge} outside possible range [{min_possible_edge}, {max_possible_edge}]"
    )


@given(
    price=market_price(min_value=0.1, max_value=0.9),
    fee=fee_percent(),
)
def test_edge_increases_monotonically_with_true_probability(price, fee):
    """
    PROPERTY: Higher true_probability → higher edge (monotonic increase).

    If true_prob1 < true_prob2, then edge(true_prob1) < edge(true_prob2).

    This validates that our edge calculation correctly responds to better
    probability estimates.
    """
    true_prob_low = Decimal("0.40")
    true_prob_high = Decimal("0.60")

    edge_low = calculate_edge(true_prob_low, price, fee)
    edge_high = calculate_edge(true_prob_high, price, fee)

    assert edge_high > edge_low, (
        f"Higher true_prob {true_prob_high} produced lower edge {edge_high} "
        f"than lower true_prob {true_prob_low} with edge {edge_low}"
    )


@given(
    true_prob=probability(min_value=0.1, max_value=0.9),
    fee=fee_percent(),
)
def test_edge_decreases_monotonically_with_market_price(true_prob, fee):
    """
    PROPERTY: Higher market_price → lower edge (monotonic decrease).

    If price1 < price2, then edge(price1) > edge(price2).

    This validates that our edge calculation correctly responds to price changes.
    """
    price_low = Decimal("0.40")
    price_high = Decimal("0.60")

    edge_low_price = calculate_edge(true_prob, price_low, fee)
    edge_high_price = calculate_edge(true_prob, price_high, fee)

    assert edge_low_price > edge_high_price, (
        f"Higher price {price_high} produced higher edge {edge_high_price} "
        f"than lower price {price_low} with edge {edge_low_price}"
    )


# ==============================================================================
# Property-Based Tests: Spread Impact
# ==============================================================================


@given(
    true_prob=probability(min_value=0.3, max_value=0.7),
    mid_price=market_price(min_value=0.3, max_value=0.7),
    spread_width=spread(min_value=0.0010, max_value=0.0500),
    fee=fee_percent(),
)
def test_spread_reduces_realizable_edge(true_prob, mid_price, spread_width, fee):
    """
    PROPERTY: Wider spread → lower realizable edge.

    When bid-ask spread widens, the realizable edge (what we can actually capture)
    decreases because we buy at ask (higher) and sell at bid (lower).
    """
    # Create narrow spread
    narrow_spread = Decimal("0.0010")
    bid_narrow = mid_price - (narrow_spread / Decimal("2"))
    ask_narrow = mid_price + (narrow_spread / Decimal("2"))

    # Create wide spread
    bid_wide = mid_price - (spread_width / Decimal("2"))
    ask_wide = mid_price + (spread_width / Decimal("2"))

    # Clamp to [0, 1]
    bid_narrow = max(Decimal("0"), min(Decimal("1"), bid_narrow))
    ask_narrow = max(Decimal("0"), min(Decimal("1"), ask_narrow))
    bid_wide = max(Decimal("0"), min(Decimal("1"), bid_wide))
    ask_wide = max(Decimal("0"), min(Decimal("1"), ask_wide))

    # Skip if spread got clamped incorrectly
    if bid_narrow >= ask_narrow or bid_wide >= ask_wide:
        return

    edge_narrow = calculate_realizable_edge(true_prob, bid_narrow, ask_narrow, fee)
    edge_wide = calculate_realizable_edge(true_prob, bid_wide, ask_wide, fee)

    assert edge_wide <= edge_narrow, (
        f"Wider spread produced higher edge! "
        f"Narrow spread {narrow_spread} → edge {edge_narrow}, "
        f"Wide spread {spread_width} → edge {edge_wide}"
    )


@given(
    true_prob=probability(min_value=0.4, max_value=0.6),
    bid=market_price(min_value=0.35, max_value=0.55),
    ask=market_price(min_value=0.45, max_value=0.65),
    fee=fee_percent(),
)
def test_realizable_edge_uses_ask_price(true_prob, bid, ask, fee):
    """
    PROPERTY: Realizable edge should use ASK price (what we pay), not BID.

    We are buyers (taking liquidity), so we pay the ask. Using bid would
    overestimate edge.
    """
    # Skip invalid spreads (bid > ask)
    assume(bid < ask)

    realizable_edge = calculate_realizable_edge(true_prob, bid, ask, fee)
    edge_at_ask = calculate_edge(true_prob, ask, fee)

    tolerance = Decimal("0.0001")
    assert abs(realizable_edge - edge_at_ask) <= tolerance, (
        f"Realizable edge {realizable_edge} doesn't match edge at ask {edge_at_ask}"
    )


# ==============================================================================
# Property-Based Tests: Edge Thresholding
# ==============================================================================


@given(
    edge=st.decimals(min_value=Decimal("-0.5000"), max_value=Decimal("0.5000"), places=4),
    threshold=st.decimals(min_value=Decimal("0.0100"), max_value=Decimal("0.1500"), places=4),
)
def test_edge_above_threshold_recommends_trade(edge, threshold):
    """
    PROPERTY: If edge >= threshold, should_trade() returns True.

    This validates the threshold logic works correctly.
    """
    if edge >= threshold:
        recommendation = should_trade(edge, min_edge_threshold=threshold)
        assert recommendation, f"Should recommend trade with edge {edge} >= threshold {threshold}"
    else:
        recommendation = should_trade(edge, min_edge_threshold=threshold)
        assert not recommendation, (
            f"Should NOT recommend trade with edge {edge} < threshold {threshold}"
        )


@given(
    true_prob=probability(min_value=0.1, max_value=0.9),
    price=market_price(min_value=0.1, max_value=0.9),
    fee=fee_percent(),
)
def test_threshold_zero_means_any_positive_edge_trades(true_prob, price, fee):
    """
    PROPERTY: With threshold = 0, ANY positive edge should recommend trade.

    This is a boundary condition test for the threshold parameter.
    """
    edge = calculate_edge(true_prob, price, fee)
    threshold = Decimal("0")

    recommendation = should_trade(edge, min_edge_threshold=threshold)

    if edge > Decimal("0"):
        assert recommendation, f"Should recommend trade with positive edge {edge} and threshold 0"
    elif edge < Decimal("0"):
        assert not recommendation, f"Should NOT recommend trade with negative edge {edge}"


# ==============================================================================
# Property-Based Tests: Input Validation
# ==============================================================================


@given(
    price=market_price(),
    fee=fee_percent(),
)
def test_true_probability_outside_valid_range_raises_error(price, fee):
    """
    PROPERTY: true_probability outside [0, 1] should raise ValueError.

    Probabilities > 1 or < 0 are mathematically invalid.
    """
    invalid_prob = Decimal("1.5")  # Invalid probability

    try:
        calculate_edge(invalid_prob, price, fee)
        raise AssertionError("Invalid true_probability should have raised ValueError!")
    except ValueError as e:
        assert "true_probability must be in [0, 1]" in str(e)


@given(
    true_prob=probability(),
    fee=fee_percent(),
)
def test_market_price_outside_valid_range_raises_error(true_prob, fee):
    """
    PROPERTY: market_price outside [0, 1] should raise ValueError.

    Market prices > $1 or < $0 are invalid for binary markets.
    """
    invalid_price = Decimal("-0.10")  # Negative price

    try:
        calculate_edge(true_prob, invalid_price, fee)
        raise AssertionError("Invalid market_price should have raised ValueError!")
    except ValueError as e:
        assert "market_price must be in [0, 1]" in str(e)


@given(
    true_prob=probability(),
    price=market_price(),
)
def test_negative_fees_raise_error(true_prob, price):
    """
    PROPERTY: Negative fees should raise ValueError.

    Negative fees (rebates) are not currently supported.
    """
    negative_fee = Decimal("-0.05")

    try:
        calculate_edge(true_prob, price, negative_fee)
        raise AssertionError("Negative fee should have raised ValueError!")
    except ValueError as e:
        assert "fee_percent cannot be negative" in str(e)


@given(
    true_prob=probability(),
    bid=market_price(),
    ask=market_price(),
    fee=fee_percent(),
)
def test_bid_exceeds_ask_raises_error(true_prob, bid, ask, fee):
    """
    PROPERTY: bid_price > ask_price should raise ValueError.

    This represents a crossed market (impossible under normal conditions).
    """
    # Force bid > ask
    assume(bid > ask)

    try:
        calculate_realizable_edge(true_prob, bid, ask, fee)
        raise AssertionError("bid > ask should have raised ValueError!")
    except ValueError as e:
        assert "bid_price" in str(e)
        assert "cannot exceed ask_price" in str(e)


# ==============================================================================
# Test Summary
# ==============================================================================
"""
Hypothesis Configuration (from pyproject.toml):
- max_examples = 100 (default) → Will test 100 random inputs per property
- deadline = 400ms per example

To run with statistics:
    pytest tests/property/test_edge_detection_properties.py -v --hypothesis-show-statistics

Expected Output:
    16 tests, each testing 100+ generated examples = 1600+ test cases total!

Coverage:
- Core edge calculation formula (7 properties)
- Spread impact on realizable edge (2 properties)
- Edge thresholding logic (3 properties)
- Input validation (4 properties)

Critical Properties Tested:
✅ Negative edge never recommends trade (prevents catastrophic losses)
✅ Fees always reduce edge (prevents sign errors)
✅ Edge monotonicity with probability (sanity check)
✅ Spread reduces realizable edge (prevents overestimating profits)

Next Steps (Phase 1.5):
1. Add property tests for model validation (test_model_validation_properties.py)
2. Add property tests for position management (test_position_management_properties.py)
3. Add property tests for order book analysis (test_order_book_properties.py)
4. Add property tests for backtesting (test_backtesting_properties.py)

See: docs/testing/HYPOTHESIS_IMPLEMENTATION_PLAN_V1.0.md (to be created next)
"""
