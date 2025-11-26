"""
Kelly Criterion Position Sizing - Production Implementation.

Provides the calculate_kelly_size function for optimal position sizing
based on the Kelly Criterion.

Educational Note:
    The Kelly Criterion calculates the optimal bet size to maximize
    long-term geometric growth rate. It balances risk and reward:
    - Too small bets → suboptimal growth
    - Too large bets → increased ruin probability

    In practice, we use "fractional Kelly" (e.g., 0.25 = quarter Kelly)
    to reduce variance while maintaining positive expected growth.

Mathematical Background:
    Full Kelly: f* = edge / odds
    Where:
    - f* = fraction of bankroll to bet
    - edge = probability of winning - probability implied by odds
    - odds = amount won per unit bet

    For binary markets (Kalshi):
    - edge = true_prob - market_price
    - Simplified: position = edge * kelly_fraction * bankroll

References:
    - REQ-TRADE-001: Kelly Criterion Position Sizing
    - ADR-TBD: Property-Based Testing Strategy
    - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    - tests/property/test_kelly_criterion_properties.py (11 property tests)

Created: 2025-11-25
Phase: 1.5 (Foundation Validation)
GitHub Issue: #41
"""

from decimal import Decimal

from precog.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_kelly_size(
    edge: Decimal,
    kelly_fraction: Decimal,
    bankroll: Decimal,
    max_position: Decimal | None = None,
) -> Decimal:
    """
    Calculate position size using Kelly criterion.

    Formula: position = (edge * kelly_fraction * bankroll)

    Constraints:
    - If edge <= 0: position = 0 (never bet against yourself)
    - If position > bankroll: position = bankroll (can't bet more than you have)
    - If position > max_position: position = max_position (risk limit)

    Args:
        edge: Expected value advantage (true_prob - market_price - fees)
            Must be Decimal, NEVER float.
        kelly_fraction: Multiplier to reduce Kelly bet (0.25 = quarter Kelly).
            Must be in [0, 1].
        bankroll: Total capital available. Must be non-negative.
        max_position: Optional maximum position size (risk management limit).

    Returns:
        Decimal position size in dollars. Always non-negative.

    Raises:
        ValueError: If kelly_fraction not in [0, 1]
        ValueError: If bankroll < 0

    Educational Note:
        **Why fractional Kelly?**

        Full Kelly (kelly_fraction=1.0) maximizes long-term growth but has
        VERY high variance. A bad streak can lose 50%+ of bankroll.

        Fractional Kelly reduces variance dramatically:
        - 0.25 (quarter Kelly): 75% reduction in volatility
        - 0.50 (half Kelly): 50% reduction in volatility
        - 1.00 (full Kelly): Maximum growth, maximum variance

        For Precog, we recommend 0.25 (quarter Kelly) as the default.

        **Why zero position for non-positive edge?**

        If edge <= 0, the expected value of the bet is zero or negative.
        Betting on negative edge guarantees losses over time:
        - edge = 0: Fair bet (break even in long run)
        - edge < 0: House advantage (losing proposition)

        The Kelly formula would produce negative position size for negative edge,
        which is nonsensical. We return 0 instead.

    Example:
        >>> from decimal import Decimal
        >>> from precog.trading.kelly_criterion import calculate_kelly_size
        >>>
        >>> # Quarter Kelly with 5% edge and $10,000 bankroll
        >>> position = calculate_kelly_size(
        ...     edge=Decimal("0.05"),
        ...     kelly_fraction=Decimal("0.25"),
        ...     bankroll=Decimal("10000.00")
        ... )
        >>> print(f"Position size: ${position}")
        Position size: $125.00
        >>>
        >>> # Negative edge = no position
        >>> position = calculate_kelly_size(
        ...     edge=Decimal("-0.10"),
        ...     kelly_fraction=Decimal("0.25"),
        ...     bankroll=Decimal("10000.00")
        ... )
        >>> assert position == Decimal("0")

    Property Tests:
        This function has 11 property-based tests validating:
        1. Position never exceeds bankroll (safety invariant)
        2. Position always non-negative
        3. Zero edge → zero position
        4. Negative edge → zero position (CRITICAL)
        5. Kelly fraction reduces position proportionally
        6. Position scales linearly with bankroll
        7. Position increases monotonically with edge
        8. max_position constraint respected
        9. Invalid kelly_fraction raises ValueError
        10. Negative bankroll raises ValueError
        11. Reasonable bounds for typical inputs

        See: tests/property/test_kelly_criterion_properties.py

    References:
        - REQ-TRADE-001: Kelly Criterion Position Sizing
        - REQ-SYS-003: Decimal Precision (ALWAYS use Decimal for prices)
        - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    """
    # Input validation
    if not (Decimal("0") <= kelly_fraction <= Decimal("1")):
        raise ValueError(f"kelly_fraction must be in [0, 1], got {kelly_fraction}")

    if bankroll < Decimal("0"):
        raise ValueError(f"bankroll cannot be negative, got {bankroll}")

    # Never bet on non-positive edge
    if edge <= Decimal("0"):
        logger.debug(
            f"Non-positive edge {edge}, returning zero position",
            extra={"edge": str(edge), "reason": "non_positive_edge"},
        )
        return Decimal("0")

    # Calculate Kelly position: position = edge * kelly_fraction * bankroll
    position = edge * kelly_fraction * bankroll

    # Apply constraints

    # Constraint 1: Position cannot exceed bankroll
    if position > bankroll:
        logger.debug(
            f"Position {position} capped at bankroll {bankroll}",
            extra={"original_position": str(position), "bankroll": str(bankroll)},
        )
        position = bankroll

    # Constraint 2: Position cannot exceed max_position (if specified)
    if max_position is not None and position > max_position:
        logger.debug(
            f"Position {position} capped at max_position {max_position}",
            extra={"original_position": str(position), "max_position": str(max_position)},
        )
        position = max_position

    # Constraint 3: Position cannot be negative (defensive programming)
    if position < Decimal("0"):
        position = Decimal("0")

    logger.debug(
        f"Kelly position calculated: {position}",
        extra={
            "edge": str(edge),
            "kelly_fraction": str(kelly_fraction),
            "bankroll": str(bankroll),
            "position": str(position),
        },
    )

    return position


def calculate_edge(
    true_probability: Decimal,
    market_price: Decimal,
    fees: Decimal = Decimal("0"),
) -> Decimal:
    """
    Calculate edge from true probability and market price.

    Edge = True Probability - Market Price - Fees

    Args:
        true_probability: Estimated true probability of YES outcome (0-1).
        market_price: Current market price (YES price) (0-1).
        fees: Transaction costs as decimal (e.g., 0.01 = 1%).

    Returns:
        Decimal edge value. Positive = favorable, negative = unfavorable.

    Educational Note:
        **Understanding Edge:**

        Edge represents the expected profit per dollar bet:
        - edge = 0.05 → Expect to make $0.05 per $1 bet
        - edge = -0.10 → Expect to lose $0.10 per $1 bet

        **Example:**
        - True probability: 60%
        - Market price: 50 cents (implies 50% probability)
        - Edge = 0.60 - 0.50 = 0.10 (10% edge)

        A 10% edge means you expect to win $0.10 for every $1 bet.

        **Including Fees:**
        - Kalshi charges ~1-2% per transaction
        - Edge after fees = 0.10 - 0.02 = 0.08
        - Fees reduce edge, making fewer trades profitable

    Example:
        >>> from decimal import Decimal
        >>> from precog.trading.kelly_criterion import calculate_edge
        >>>
        >>> edge = calculate_edge(
        ...     true_probability=Decimal("0.60"),
        ...     market_price=Decimal("0.50"),
        ...     fees=Decimal("0.01")
        ... )
        >>> print(f"Edge: {edge:.2%}")
        Edge: 9.00%

    References:
        - REQ-TRADE-002: Edge Calculation
        - docs/guides/EDGE_CALCULATION_GUIDE_V1.0.md
    """
    # Validation
    if not (Decimal("0") <= true_probability <= Decimal("1")):
        raise ValueError(f"true_probability must be in [0, 1], got {true_probability}")

    if not (Decimal("0") <= market_price <= Decimal("1")):
        raise ValueError(f"market_price must be in [0, 1], got {market_price}")

    if fees < Decimal("0"):
        raise ValueError(f"fees cannot be negative, got {fees}")

    edge = true_probability - market_price - fees

    logger.debug(
        f"Edge calculated: {edge}",
        extra={
            "true_probability": str(true_probability),
            "market_price": str(market_price),
            "fees": str(fees),
            "edge": str(edge),
        },
    )

    return edge


def calculate_optimal_position(
    true_probability: Decimal,
    market_price: Decimal,
    bankroll: Decimal,
    kelly_fraction: Decimal = Decimal("0.25"),
    fees: Decimal = Decimal("0"),
    max_position: Decimal | None = None,
    min_edge: Decimal = Decimal("0.02"),
) -> Decimal:
    """
    Calculate optimal position size given probability and market price.

    Convenience function that combines calculate_edge and calculate_kelly_size.

    Args:
        true_probability: Estimated true probability of YES outcome.
        market_price: Current market price (YES price).
        bankroll: Total capital available.
        kelly_fraction: Kelly multiplier (default 0.25 = quarter Kelly).
        fees: Transaction costs as decimal.
        max_position: Optional maximum position size.
        min_edge: Minimum edge required to take position (default 2%).

    Returns:
        Decimal position size in dollars.

    Educational Note:
        **Why min_edge?**

        Small edges (e.g., 0.5%) are often within model error bounds.
        Setting min_edge = 2% ensures we only trade when edge is
        statistically significant.

        **Typical min_edge values:**
        - 0.01 (1%): Very aggressive, high trade frequency
        - 0.02 (2%): Moderate, good balance of frequency and edge
        - 0.05 (5%): Conservative, fewer but higher-quality trades

    Example:
        >>> from decimal import Decimal
        >>> from precog.trading.kelly_criterion import calculate_optimal_position
        >>>
        >>> # Calculate position for a trade opportunity
        >>> position = calculate_optimal_position(
        ...     true_probability=Decimal("0.65"),
        ...     market_price=Decimal("0.55"),
        ...     bankroll=Decimal("10000.00"),
        ...     kelly_fraction=Decimal("0.25"),
        ...     fees=Decimal("0.01"),
        ...     min_edge=Decimal("0.02")
        ... )
        >>> print(f"Position size: ${position}")
        Position size: $225.00

    References:
        - REQ-TRADE-001: Kelly Criterion Position Sizing
        - REQ-TRADE-002: Edge Calculation
    """
    # Calculate edge
    edge = calculate_edge(true_probability, market_price, fees)

    # Check minimum edge threshold
    if edge < min_edge:
        logger.debug(
            f"Edge {edge} below minimum threshold {min_edge}, returning zero position",
            extra={"edge": str(edge), "min_edge": str(min_edge)},
        )
        return Decimal("0")

    # Calculate Kelly position
    return calculate_kelly_size(
        edge=edge,
        kelly_fraction=kelly_fraction,
        bankroll=bankroll,
        max_position=max_position,
    )
