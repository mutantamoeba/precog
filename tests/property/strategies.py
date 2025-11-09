"""
Custom Hypothesis Strategies for Trading Domain
================================================

Reusable Hypothesis strategies for property-based testing of trading logic.

These strategies generate domain-valid inputs for:
- Market prices (Decimal, not float)
- Probabilities ([0, 1] range)
- Edge values (difference between true probability and market price)
- Kelly fractions (position sizing multiplier)
- Bankroll amounts (account balance)
- Bid-ask spreads (bid < ask constraint)

Usage:
    from tests.property.strategies import decimal_price, probability

    @given(price=decimal_price())
    def test_price_property(price):
        assert 0 <= price <= 1

Why Custom Strategies?
- Generate **domain-valid** inputs only (no wasted test cases on negative prices)
- Encode constraints once, reuse everywhere (bid < ask, probability ∈ [0, 1])
- Improve Hypothesis shrinking (finds minimal failing examples faster)
- Document domain assumptions (probabilities are Decimal, not float)

Related:
- Pattern 10: Property-Based Testing (CLAUDE.md)
- REQ-TEST-008: Property-Based Testing Framework
"""

from decimal import Decimal

from hypothesis import strategies as st


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

    Example:
        >>> from hypothesis import given
        >>> from tests.property.strategies import decimal_price
        >>>
        >>> @given(price=decimal_price())
        >>> def test_price_bounds(price):
        ...     assert Decimal("0") <= price <= Decimal("1")
    """
    # Convert to Decimal if not already
    if not isinstance(min_value, Decimal):
        min_value = Decimal(str(min_value))
    if not isinstance(max_value, Decimal):
        max_value = Decimal(str(max_value))

    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def probability(draw, min_value=0, max_value=1, places=4):
    """
    Generate valid probabilities as Decimal.

    Alias for decimal_price() with semantic name.
    Use this when generating true win probabilities (not market prices).

    Args:
        min_value: Minimum probability (default 0)
        max_value: Maximum probability (default 1)
        places: Decimal places

    Returns:
        Decimal probability in range [0, 1]

    Example:
        >>> @given(prob=probability())
        >>> def test_probability_bounds(prob):
        ...     assert Decimal("0") <= prob <= Decimal("1")
    """
    return draw(decimal_price(min_value=min_value, max_value=max_value, places=places))


@st.composite
def edge_value(draw, min_value=-0.5, max_value=0.5, places=4):
    """
    Generate edge values (difference between true probability and market price).

    Edge = True Probability - Market Price
    - Positive edge: favorable bet (true probability higher than market price)
    - Negative edge: unfavorable bet (true probability lower than market price)
    - Zero edge: fair bet (no advantage)

    Args:
        min_value: Minimum edge (default -0.5 = severely negative)
        max_value: Maximum edge (default 0.5 = highly positive)
        places: Decimal places

    Returns:
        Decimal edge in range [min_value, max_value]

    Example:
        >>> @given(edge=edge_value())
        >>> def test_negative_edge_no_trade(edge):
        ...     if edge < 0:
        ...         position = calculate_kelly_size(edge, Decimal("0.25"), Decimal("10000"))
        ...         assert position == Decimal("0")  # Don't bet on negative edge
    """
    # Convert to Decimal
    if not isinstance(min_value, Decimal):
        min_value = Decimal(str(min_value))
    if not isinstance(max_value, Decimal):
        max_value = Decimal(str(max_value))

    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def kelly_fraction(draw, min_value=0, max_value=1, places=2):
    """
    Generate Kelly fraction (position sizing multiplier).

    Kelly fraction is a risk management parameter:
    - 0.0: No position (conservative)
    - 0.25: Quarter Kelly (typical for aggressive trading)
    - 0.5: Half Kelly (balanced risk/reward)
    - 1.0: Full Kelly (maximum growth rate, high risk)

    Args:
        min_value: Minimum fraction (default 0 = no position)
        max_value: Maximum fraction (default 1 = full Kelly)
        places: Decimal places

    Returns:
        Decimal Kelly fraction in range [0, 1]

    Example:
        >>> @given(kelly_frac=kelly_fraction())
        >>> def test_kelly_reduces_position(kelly_frac):
        ...     full = calculate_kelly_size(edge=0.1, kelly_frac=1.0, bankroll=10000)
        ...     reduced = calculate_kelly_size(edge=0.1, kelly_frac=kelly_frac, bankroll=10000)
        ...     assert reduced <= full  # Lower fraction = smaller position
    """
    # Convert to Decimal
    if not isinstance(min_value, Decimal):
        min_value = Decimal(str(min_value))
    if not isinstance(max_value, Decimal):
        max_value = Decimal(str(max_value))

    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def bankroll_amount(draw, min_value=100, max_value=100000, places=2):
    """
    Generate bankroll amounts (account balance).

    Args:
        min_value: Minimum bankroll (default $100)
        max_value: Maximum bankroll (default $100,000)
        places: Decimal places (default 2 for cents precision)

    Returns:
        Decimal bankroll in range [$100, $100,000]

    Example:
        >>> @given(bankroll=bankroll_amount())
        >>> def test_position_never_exceeds_bankroll(bankroll):
        ...     position = calculate_kelly_size(edge=0.5, kelly_frac=1.0, bankroll=bankroll)
        ...     assert position <= bankroll  # Critical invariant
    """
    # Convert to Decimal
    if not isinstance(min_value, Decimal):
        min_value = Decimal(str(min_value))
    if not isinstance(max_value, Decimal):
        max_value = Decimal(str(max_value))

    return draw(st.decimals(min_value=min_value, max_value=max_value, places=places))


@st.composite
def bid_ask_spread(draw, min_spread=0.0001, max_spread=0.05):
    """
    Generate realistic bid-ask spreads with bid < ask constraint.

    Market microstructure constraint: Bid price must always be < Ask price.
    This strategy generates valid (bid, ask) tuples.

    Args:
        min_spread: Minimum spread (default 0.0001 = 1 basis point)
        max_spread: Maximum spread (default 0.05 = 5% spread)

    Returns:
        Tuple[Decimal, Decimal]: (bid, ask) where bid < ask

    Example:
        >>> @given(spread=bid_ask_spread())
        >>> def test_bid_less_than_ask(spread):
        ...     bid, ask = spread
        ...     assert bid < ask  # Market microstructure invariant
    """
    # Generate bid price [0, 0.99]
    bid = draw(st.decimals(min_value=Decimal("0"), max_value=Decimal("0.99"), places=4))

    # Convert spread bounds to Decimal
    if not isinstance(min_spread, Decimal):
        min_spread = Decimal(str(min_spread))
    if not isinstance(max_spread, Decimal):
        max_spread = Decimal(str(max_spread))

    # Generate spread
    spread = draw(st.decimals(min_value=min_spread, max_value=max_spread, places=4))

    # Calculate ask (cap at 1.0)
    ask = min(bid + spread, Decimal("1.0"))

    return (bid, ask)


@st.composite
def price_series(draw, length=10, volatility=Decimal("0.05")):
    """
    Generate realistic price movement series.

    Simulates market price evolution over time with bounded volatility.
    Useful for testing trailing stop algorithms, price walking, etc.

    Args:
        length: Number of price points (default 10)
        volatility: Maximum price change per step (default 0.05 = 5%)

    Returns:
        List[Decimal]: Price series of specified length

    Example:
        >>> @given(prices=price_series(length=20, volatility=Decimal("0.03")))
        >>> def test_trailing_stop_only_tightens(prices):
        ...     stops = []
        ...     for price in prices:
        ...         new_stop = calculate_trailing_stop(price)
        ...         if stops:
        ...             assert new_stop >= stops[-1]  # Never loosens
        ...         stops.append(new_stop)
    """
    # Convert volatility to Decimal
    if not isinstance(volatility, Decimal):
        volatility = Decimal(str(volatility))

    # Generate starting price [0.40, 0.60] (mid-range)
    start_price = draw(st.decimals(min_value=Decimal("0.40"), max_value=Decimal("0.60"), places=4))

    prices = [start_price]

    for _ in range(length - 1):
        # Generate price change [-volatility, +volatility]
        change = draw(st.decimals(min_value=-volatility, max_value=volatility, places=4))

        # Calculate new price (bounded [0.01, 0.99])
        new_price = prices[-1] + change
        new_price = max(Decimal("0.01"), min(Decimal("0.99"), new_price))

        prices.append(new_price)

    return prices
