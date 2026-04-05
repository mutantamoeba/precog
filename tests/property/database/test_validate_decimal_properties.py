"""
Property-based tests for validate_decimal runtime type enforcement.

Tests invariants that should hold for any input to validate_decimal():
1. Decimal inputs always pass (identity property)
2. Non-Decimal inputs always raise TypeError (rejection property)
3. The returned value equals the input (no mutation)
4. Error messages contain the parameter name (debuggability)

Reference: TESTING_STRATEGY V3.9 - Property tests for business logic
Related: Pattern 1 (Decimal Precision) in CLAUDE.md
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.database.crud_shared import validate_decimal

pytestmark = [pytest.mark.property]


# =============================================================================
# Custom Strategies
# =============================================================================

# Valid Decimal values (realistic trading/price domain)
decimal_strategy = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Price-range Decimals (0 to 1, sub-penny precision)
price_decimal_strategy = st.decimals(
    min_value=Decimal("0.0001"),
    max_value=Decimal("0.9999"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Non-Decimal types that should be rejected
non_decimal_strategy = (
    st.floats(allow_nan=False, allow_infinity=False)
    | st.integers()
    | st.text(max_size=20)
    | st.none()
    | st.booleans()
    | st.lists(st.integers(), max_size=3)
)

# Parameter names
param_name_strategy = st.sampled_from(
    [
        "yes_ask_price",
        "no_bid_price",
        "edge",
        "probability",
        "clock_seconds",
        "min_edge",
    ]
)


# =============================================================================
# Property Tests: Identity (Decimal in = Decimal out)
# =============================================================================


@pytest.mark.property
class TestValidateDecimalIdentity:
    """Property: validate_decimal(Decimal_value) always returns the same value."""

    @given(value=decimal_strategy, param_name=param_name_strategy)
    @settings(max_examples=200)
    def test_decimal_passes_through_unchanged(self, value: Decimal, param_name: str) -> None:
        """Any Decimal value passes validation and is returned unchanged."""
        result = validate_decimal(value, param_name)
        assert result == value
        assert result is value  # Same object, not a copy

    @given(value=price_decimal_strategy)
    @settings(max_examples=100)
    def test_price_range_decimals_pass(self, value: Decimal) -> None:
        """Price-range Decimals (0.0001-0.9999) always pass."""
        result = validate_decimal(value, "price")
        assert result == value

    def test_zero_decimal_passes(self) -> None:
        """Decimal("0") passes validation."""
        assert validate_decimal(Decimal("0"), "value") == Decimal("0")

    def test_negative_decimal_passes(self) -> None:
        """Negative Decimal passes (validation is type-only, not range)."""
        assert validate_decimal(Decimal("-1.5"), "value") == Decimal("-1.5")


# =============================================================================
# Property Tests: Rejection (non-Decimal always raises TypeError)
# =============================================================================


@pytest.mark.property
class TestValidateDecimalRejection:
    """Property: validate_decimal(non_Decimal) always raises TypeError."""

    @given(value=non_decimal_strategy, param_name=param_name_strategy)
    @settings(max_examples=200)
    def test_non_decimal_always_rejected(self, value: object, param_name: str) -> None:
        """Any non-Decimal value raises TypeError."""
        with pytest.raises(TypeError):
            validate_decimal(value, param_name)

    @given(value=st.floats(allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_float_always_rejected(self, value: float) -> None:
        """Float values are always rejected, even when numerically equivalent."""
        with pytest.raises(TypeError, match="must be Decimal"):
            validate_decimal(value, "price")

    @given(value=st.integers())
    @settings(max_examples=50)
    def test_int_always_rejected(self, value: int) -> None:
        """Integer values are always rejected (must use Decimal explicitly)."""
        with pytest.raises(TypeError, match="must be Decimal"):
            validate_decimal(value, "count")


# =============================================================================
# Property Tests: Error Message Quality
# =============================================================================


@pytest.mark.property
class TestValidateDecimalErrorMessages:
    """Property: error messages always contain the parameter name and type guidance."""

    @given(param_name=param_name_strategy)
    @settings(max_examples=50)
    def test_error_contains_param_name(self, param_name: str) -> None:
        """TypeError message includes the parameter name for debuggability."""
        with pytest.raises(TypeError, match=param_name):
            validate_decimal(0.5, param_name)

    @given(value=st.floats(min_value=0.01, max_value=0.99, allow_nan=False))
    @settings(max_examples=50)
    def test_error_contains_type_name(self, value: float) -> None:
        """TypeError message includes 'float' so the developer knows what went wrong."""
        with pytest.raises(TypeError, match="float"):
            validate_decimal(value, "price")

    def test_error_contains_pattern_reference(self) -> None:
        """TypeError message references Pattern 1 in CLAUDE.md."""
        with pytest.raises(TypeError, match="Pattern 1"):
            validate_decimal(0.5, "price")
