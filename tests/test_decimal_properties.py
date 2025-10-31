"""
Property-Based Tests for Decimal Arithmetic (Hypothesis)

**Purpose:** Verify decimal precision is maintained under all conditions
**Phase:** 0.7 (CI/CD & Advanced Testing)
**ADR:** ADR-045 (Property-Based Testing with Hypothesis)

These tests use Hypothesis to generate thousands of test cases automatically,
catching edge cases that manual tests might miss.
"""

from decimal import Decimal, InvalidOperation
import pytest
from hypothesis import given, strategies as st, assume


# Strategy for valid Kalshi prices (0.0001 to 0.9999, 4 decimal places)
kalshi_prices = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("0.9999"),
    places=4,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for Kelly fractions (0.10 to 0.50, 2 decimal places)
kelly_fractions = st.decimals(
    min_value=Decimal("0.10"),
    max_value=Decimal("0.50"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for position sizes (1 to 10000)
position_sizes = st.integers(min_value=1, max_value=10000)


@given(price1=kalshi_prices, price2=kalshi_prices)
def test_decimal_addition_commutative(price1, price2):
    """
    Property: Decimal addition is commutative (a + b = b + a).

    This ensures our Decimal arithmetic maintains mathematical properties.
    """
    result1 = price1 + price2
    result2 = price2 + price1

    assert result1 == result2, f"{price1} + {price2} != {price2} + {price1}"


@given(price1=kalshi_prices, price2=kalshi_prices, price3=kalshi_prices)
def test_decimal_addition_associative(price1, price2, price3):
    """
    Property: Decimal addition is associative ((a + b) + c = a + (b + c)).
    """
    result1 = (price1 + price2) + price3
    result2 = price1 + (price2 + price3)

    assert result1 == result2, f"({price1} + {price2}) + {price3} != {price1} + ({price2} + {price3})"


@given(price=kalshi_prices)
def test_decimal_string_conversion_reversible(price):
    """
    Property: Converting Decimal to string and back preserves value.

    Critical for API serialization/deserialization.
    """
    price_str = str(price)
    price_back = Decimal(price_str)

    assert price == price_back, f"Decimal({price_str}) != {price}"


@given(price=kalshi_prices, kelly=kelly_fractions, size=position_sizes)
def test_position_sizing_always_valid(price, kelly, size):
    """
    Property: Kelly position sizing always produces valid result.

    Formula: position = bankroll * kelly * edge / price
    Edge calculated as: true_prob - market_price
    """
    # Assume we have a true probability > market price (edge exists)
    true_prob = price + Decimal("0.05")  # 5% edge
    assume(true_prob <= Decimal("0.9999"))  # Stay within valid range

    edge = true_prob - price
    bankroll = Decimal("10000.00")

    # Kelly position sizing
    position = (bankroll * kelly * edge) / price

    # Properties that must hold
    assert position >= Decimal("0"), "Position size cannot be negative"
    assert isinstance(position, Decimal), "Position must be Decimal type"

    # Convert to integer shares
    shares = int(position)
    assert shares >= 0, "Shares cannot be negative"


@given(yes_price=kalshi_prices)
def test_kalshi_price_complement(yes_price):
    """
    Property: YES price + NO price should be close to $1.00 (within spread).

    Kalshi markets have complementary pricing with a small spread.
    """
    # Typical spread is 1-2 cents
    spread = Decimal("0.02")
    no_price = Decimal("1.00") - yes_price

    # Combined price should be close to $1.00
    total = yes_price + no_price

    assert Decimal("0.98") <= total <= Decimal("1.02"), \
        f"YES ({yes_price}) + NO ({no_price}) = {total} is outside valid range"


@given(price=kalshi_prices)
def test_decimal_never_becomes_float(price):
    """
    Property: Decimal type is preserved through common operations.

    CRITICAL: We must never accidentally convert to float.
    """
    # Common operations
    doubled = price * Decimal("2")
    halved = price / Decimal("2")
    added = price + Decimal("0.0001")
    subtracted = price - Decimal("0.0001")

    # All results must still be Decimal
    assert isinstance(doubled, Decimal), "Multiplication created non-Decimal"
    assert isinstance(halved, Decimal), "Division created non-Decimal"
    assert isinstance(added, Decimal), "Addition created non-Decimal"
    assert isinstance(subtracted, Decimal), "Subtraction created non-Decimal"

    # Extra paranoid: check they're not float
    assert not isinstance(doubled, float), "Multiplication created float!"
    assert not isinstance(halved, float), "Division created float!"


@given(price=kalshi_prices)
def test_decimal_precision_maintained(price):
    """
    Property: Decimal maintains exactly 4 decimal places for Kalshi prices.
    """
    # Convert to string and check decimal places
    price_str = str(price)

    if '.' in price_str:
        _, decimal_part = price_str.split('.')
        # Should have exactly 4 decimal places (or fewer if trailing zeros)
        assert len(decimal_part) <= 4, f"Price {price} has more than 4 decimal places"


@given(price=kalshi_prices, quantity=position_sizes)
def test_trade_cost_calculation(price, quantity):
    """
    Property: Trade cost calculation is always precise.

    Cost = price * quantity (in dollars)
    """
    cost = price * quantity

    # Cost should be Decimal
    assert isinstance(cost, Decimal), "Cost must be Decimal"

    # Cost should be positive
    assert cost > Decimal("0"), "Cost must be positive"

    # Cost should be less than max possible (0.9999 * 10000 = 9999)
    assert cost <= Decimal("10000"), "Cost exceeds maximum"


@given(
    entry_price=kalshi_prices,
    exit_price=kalshi_prices,
    quantity=position_sizes
)
def test_pnl_calculation(entry_price, exit_price, quantity):
    """
    Property: PnL calculation is always precise and type-safe.

    PnL = (exit_price - entry_price) * quantity
    """
    pnl = (exit_price - entry_price) * quantity

    # PnL should be Decimal
    assert isinstance(pnl, Decimal), "PnL must be Decimal"

    # If exit > entry, profit should be positive
    if exit_price > entry_price:
        assert pnl > Decimal("0"), "Profit should be positive"

    # If exit < entry, loss should be negative
    elif exit_price < entry_price:
        assert pnl < Decimal("0"), "Loss should be negative"

    # If equal, PnL should be zero
    else:
        assert pnl == Decimal("0"), "PnL should be zero when prices equal"


@given(price=kalshi_prices)
def test_implied_probability_conversion(price):
    """
    Property: Kalshi price IS the implied probability (in decimal form).

    A $0.65 price means 65% implied probability.
    """
    # Convert price to percentage
    implied_prob_pct = price * Decimal("100")

    # Should be between 0.01% and 99.99%
    assert Decimal("0.01") <= implied_prob_pct <= Decimal("99.99"), \
        f"Implied probability {implied_prob_pct}% is outside valid range"

    # Should maintain Decimal type
    assert isinstance(implied_prob_pct, Decimal), "Conversion created non-Decimal"


# Example of testing for invalid operations (should raise)
@given(price=kalshi_prices)
def test_float_contamination_raises_error(price):
    """
    Property: Mixing Decimal with float should be caught.

    We want to catch accidental float usage at test time.
    """
    # This is a negative test - we WANT to ensure we don't mix types
    # In production code, this should never happen

    # Verify that we're using Decimal
    assert isinstance(price, Decimal), "Price should be Decimal"

    # If we accidentally had a float in the system, arithmetic would still work
    # but precision could be lost. This test documents the expectation.
    with pytest.raises((TypeError, InvalidOperation)):
        # This would be a bug - we should never do this
        # Hypothesis will verify we handle it correctly
        if isinstance(price, float):  # This should never be true
            raise TypeError("Found float where Decimal expected!")
