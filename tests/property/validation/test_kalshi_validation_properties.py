"""
Property-Based Tests for Kalshi Data Validation.

Uses Hypothesis to test validation invariants that should hold for any valid input.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/property/validation/test_kalshi_validation_properties.py -v -m property
"""

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.validation.kalshi_validation import (
    KalshiDataValidator,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Valid price strategy (0 to 1, Decimal)
valid_price_strategy = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Invalid price strategy (negative or > 1)
invalid_price_strategy = st.one_of(
    st.decimals(
        min_value=Decimal("-100"),
        max_value=Decimal("-0.0001"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
    st.decimals(
        min_value=Decimal("1.0001"),
        max_value=Decimal("100"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
)

# Valid volume strategy (non-negative integers)
volume_strategy = st.integers(min_value=0, max_value=1000000)

# Ticker strategy
ticker_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Nd")),
    min_size=5,
    max_size=20,
)

# Market status strategy (valid Kalshi statuses)
status_strategy = st.sampled_from(["open", "closed", "settled"])


# =============================================================================
# Helper Functions
# =============================================================================


def create_validator() -> KalshiDataValidator:
    """Create a validator instance (avoids fixture issues with Hypothesis)."""
    return KalshiDataValidator()


# =============================================================================
# Property Tests: ValidationResult Invariants
# =============================================================================


@pytest.mark.property
class TestValidationResultProperties:
    """Property tests for ValidationResult invariants."""

    @given(
        num_errors=st.integers(min_value=0, max_value=10),
        num_warnings=st.integers(min_value=0, max_value=10),
        num_infos=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=50)
    def test_issue_counts_match(self, num_errors: int, num_warnings: int, num_infos: int) -> None:
        """Issue counts should match added issues."""
        result = ValidationResult(entity_id="test123")

        for i in range(num_errors):
            result.add_error(f"field{i}", f"error{i}")
        for i in range(num_warnings):
            result.add_warning(f"field{i}", f"warning{i}")
        for i in range(num_infos):
            result.add_info(f"field{i}", f"info{i}")

        assert len(result.errors) == num_errors
        assert len(result.warnings) == num_warnings
        assert len(result.issues) == num_errors + num_warnings + num_infos

    @given(num_errors=st.integers(min_value=0, max_value=10))
    @settings(max_examples=30)
    def test_is_valid_iff_no_errors(self, num_errors: int) -> None:
        """Result is valid if and only if no errors."""
        result = ValidationResult()

        for i in range(num_errors):
            result.add_error(f"field{i}", f"error{i}")

        # Add some warnings (shouldn't affect validity)
        for i in range(3):
            result.add_warning(f"wfield{i}", f"warning{i}")

        assert result.is_valid == (num_errors == 0)
        assert result.has_errors == (num_errors > 0)

    @given(entity_id=st.text(min_size=1, max_size=30))
    @settings(max_examples=30)
    def test_entity_id_preserved(self, entity_id: str) -> None:
        """Entity ID should be preserved in result."""
        result = ValidationResult(entity_id=entity_id)
        assert result.entity_id == entity_id


# =============================================================================
# Property Tests: Price Validation Invariants
# =============================================================================


@pytest.mark.property
class TestPriceValidationProperties:
    """Property tests for price validation invariants."""

    @given(price=valid_price_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_prices_always_pass(self, price: Decimal) -> None:
        """Prices in [0, 1] should always pass validation."""
        validator = create_validator()
        result = ValidationResult(entity_id="test")
        is_valid = validator.validate_price(price, "test_field", result)

        assert is_valid
        assert not result.has_errors

    @given(price=invalid_price_strategy)
    @settings(max_examples=30)
    def test_invalid_prices_always_fail(self, price: Decimal) -> None:
        """Prices outside [0, 1] should always fail."""
        validator = create_validator()
        result = ValidationResult(entity_id="test")
        is_valid = validator.validate_price(price, "test_field", result)

        assert not is_valid
        assert result.has_errors


# =============================================================================
# Property Tests: Spread Validation Invariants
# =============================================================================


@pytest.mark.property
class TestSpreadValidationProperties:
    """Property tests for bid-ask spread validation invariants."""

    @given(
        bid=valid_price_strategy,
        ask=valid_price_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_spread_when_bid_less_than_ask(self, bid: Decimal, ask: Decimal) -> None:
        """Valid spread when bid < ask."""
        # Only test when bid < ask
        if bid < ask:
            validator = create_validator()
            result = ValidationResult(entity_id="test")
            validator.validate_spread(bid, ask, result)

            # No crossed market error (may have spread warnings)
            assert not any("Crossed" in e.message for e in result.errors)

    @given(
        bid=valid_price_strategy,
    )
    @settings(max_examples=30)
    def test_crossed_market_always_fails(self, bid: Decimal) -> None:
        """Crossed market (bid > ask) should always fail."""
        validator = create_validator()
        # Make ask less than bid
        ask = bid - Decimal("0.01") if bid > Decimal("0.01") else Decimal("0")

        if bid > ask:
            result = ValidationResult(entity_id="test")
            validator.validate_spread(bid, ask, result)
            assert result.has_errors
            assert any("Crossed" in e.message for e in result.errors)


# =============================================================================
# Property Tests: Market Data Validation Invariants
# =============================================================================


@pytest.mark.property
class TestMarketDataValidationProperties:
    """Property tests for market data validation invariants."""

    @given(
        ticker=ticker_strategy,
        yes_bid=valid_price_strategy,
        yes_ask=valid_price_strategy,
        volume=volume_strategy,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_market_data_structure(
        self, ticker: str, yes_bid: Decimal, yes_ask: Decimal, volume: int
    ) -> None:
        """Valid market data should pass basic structure validation."""
        validator = create_validator()

        # Ensure bid < ask
        actual_bid = yes_bid if yes_bid < yes_ask else yes_ask - Decimal("0.01")
        actual_ask = yes_ask

        market = {
            "ticker": ticker,
            "yes_bid_dollars": actual_bid if actual_bid >= Decimal("0") else Decimal("0"),
            "yes_ask_dollars": actual_ask,
            "no_bid_dollars": Decimal("1") - actual_ask,
            "no_ask_dollars": Decimal("1") - actual_bid
            if actual_bid >= Decimal("0")
            else Decimal("1"),
            "volume": volume,
            "status": "open",
        }

        result = validator.validate_market_data(market)
        # Should be valid (no errors) - may have warnings for wide spreads
        assert result.is_valid

    @given(ticker=st.just(""))
    @settings(max_examples=5)
    def test_empty_ticker_always_fails(self, ticker: str) -> None:
        """Empty ticker should always fail."""
        validator = create_validator()
        market = {"ticker": ticker, "status": "open"}

        result = validator.validate_market_data(market)
        assert result.has_errors
        assert any("ticker" in e.field.lower() for e in result.errors)


# =============================================================================
# Property Tests: Position Data Validation Invariants
# =============================================================================


@pytest.mark.property
class TestPositionDataValidationProperties:
    """Property tests for position data validation invariants."""

    @given(
        position=st.integers(min_value=-1000, max_value=1000),
        avg_price=valid_price_strategy,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_position_with_decimal_price(self, position: int, avg_price: Decimal) -> None:
        """Position with valid Decimal price should pass."""
        validator = create_validator()

        pos_data = {
            "ticker": "TEST-TICKER",
            "position": position,
            "market_exposure": abs(position) * avg_price,
            "resting_orders_count": 0,
        }

        result = validator.validate_position_data(pos_data)
        assert result.is_valid

    @given(ticker=st.just(""))
    @settings(max_examples=5)
    def test_empty_ticker_always_fails_position(self, ticker: str) -> None:
        """Empty ticker should always fail for position data."""
        validator = create_validator()
        position = {"ticker": ticker, "position": 10}

        result = validator.validate_position_data(position)
        assert result.has_errors


# =============================================================================
# Property Tests: Balance Validation Invariants
# =============================================================================


@pytest.mark.property
class TestBalanceValidationProperties:
    """Property tests for balance validation invariants."""

    @given(
        balance=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("1000000"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=30)
    def test_valid_balance_always_passes(self, balance: Decimal) -> None:
        """Non-negative Decimal balance should always pass."""
        validator = create_validator()
        result = validator.validate_balance(balance)

        assert result.is_valid
        assert not result.has_errors

    @given(
        negative_balance=st.decimals(
            min_value=Decimal("-1000000"),
            max_value=Decimal("-0.01"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=30)
    def test_negative_balance_always_fails(self, negative_balance: Decimal) -> None:
        """Negative balance should always fail."""
        validator = create_validator()
        result = validator.validate_balance(negative_balance)

        assert not result.is_valid
        assert result.has_errors

    def test_none_balance_always_fails(self) -> None:
        """None balance should always fail."""
        validator = create_validator()
        result = validator.validate_balance(None)

        assert not result.is_valid
        assert result.has_errors


# =============================================================================
# Property Tests: Anomaly Tracking Invariants
# =============================================================================


@pytest.mark.property
class TestAnomalyTrackingProperties:
    """Property tests for anomaly tracking invariants."""

    @given(num_validations=st.integers(min_value=1, max_value=10))
    @settings(max_examples=20)
    def test_anomaly_count_accumulates(self, num_validations: int) -> None:
        """Anomaly counts should accumulate across validations."""
        validator = create_validator()

        market = {
            "ticker": "test123",
            "yes_bid_dollars": Decimal("-0.5"),  # Invalid - will cause error
            "yes_ask_dollars": Decimal("0.5"),
            "status": "open",
        }

        for _ in range(num_validations):
            validator.validate_market_data(market)

        count = validator.get_anomaly_count("test123")
        assert count >= num_validations

    @given(
        identifiers=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Nd", "Lu")),
                min_size=5,
                max_size=10,
            ),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_clear_resets_all_counts(self, identifiers: list[str]) -> None:
        """Clear should reset counts for all identifiers."""
        validator = create_validator()

        # Add anomalies for multiple markets
        for identifier in identifiers:
            market = {
                "ticker": identifier,
                "yes_bid_dollars": Decimal("-0.5"),  # Invalid
                "yes_ask_dollars": Decimal("0.5"),
                "status": "open",
            }
            validator.validate_market_data(market)

        # Clear all
        validator.clear_anomaly_counts()

        # All counts should be zero
        for identifier in identifiers:
            assert validator.get_anomaly_count(identifier) == 0


# =============================================================================
# Property Tests: ValidationIssue Invariants
# =============================================================================


@pytest.mark.property
class TestValidationIssueProperties:
    """Property tests for ValidationIssue invariants."""

    @given(
        level=st.sampled_from(list(ValidationLevel)),
        field_name=st.text(min_size=1, max_size=20),
        message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=30)
    def test_issue_fields_preserved(
        self, level: ValidationLevel, field_name: str, message: str
    ) -> None:
        """Issue fields should be preserved correctly."""
        issue = ValidationIssue(
            level=level,
            field=field_name,
            message=message,
        )

        assert issue.level == level
        assert issue.field == field_name
        assert issue.message == message


# =============================================================================
# Property Tests: Validation Determinism
# =============================================================================


@pytest.mark.property
class TestValidationDeterminism:
    """Property tests for validation determinism."""

    @given(
        balance=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("10000"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=30)
    def test_balance_validation_deterministic(self, balance: Decimal) -> None:
        """Same input should produce same validation result."""
        validator1 = create_validator()
        validator2 = create_validator()

        result1 = validator1.validate_balance(balance)
        result2 = validator2.validate_balance(balance)

        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)
        assert len(result1.warnings) == len(result2.warnings)
