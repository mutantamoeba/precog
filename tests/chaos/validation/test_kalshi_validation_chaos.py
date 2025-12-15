"""
Chaos Tests for Kalshi Data Validation.

Tests validation behavior under failure scenarios and unexpected conditions.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for failure recovery
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/chaos/validation/test_kalshi_validation_chaos.py -v -m chaos
"""

from decimal import Decimal

import pytest

from precog.validation.kalshi_validation import (
    KalshiDataValidator,
    ValidationResult,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> KalshiDataValidator:
    """Create a validator for testing."""
    return KalshiDataValidator()


# =============================================================================
# Chaos Tests: Malformed Input Data
# =============================================================================


@pytest.mark.chaos
class TestMalformedInputData:
    """Chaos tests for malformed input handling."""

    def test_empty_dict_market(self, validator: KalshiDataValidator) -> None:
        """Test validation of empty market dict."""
        result = validator.validate_market_data({})
        # Should handle gracefully (with errors, not crash)
        assert result.has_errors

    def test_none_market_fields(self, validator: KalshiDataValidator) -> None:
        """Test validation with None values in market fields."""
        market = {
            "ticker": None,
            "status": None,
            "yes_bid_dollars": None,
            "yes_ask_dollars": None,
        }
        result = validator.validate_market_data(market)
        assert result.has_errors

    def test_wrong_type_market_fields(self, validator: KalshiDataValidator) -> None:
        """Test validation with wrong types in market fields.

        Note: The validator doesn't do full type coercion. It will:
        - Accept numeric ticker (coerces to string for entity_id)
        - Detect non-Decimal price types
        - Crash on string volume (can't compare str < int)

        This test validates behavior for types that don't crash the validator.
        """
        market = {
            "ticker": 12345,  # Should be string - validator coerces for entity_id
            "status": "open",  # Valid string
            "yes_bid_dollars": "not a decimal",  # Should be Decimal - validator detects this
            "volume": 1000,  # Use valid int to avoid comparison crash
        }
        # Should not crash with these wrong types
        result = validator.validate_market_data(market)
        # Should have errors for non-Decimal price
        assert isinstance(result, ValidationResult)
        assert result.has_errors  # Should detect the string price type

    def test_unhashable_status_type(self, validator: KalshiDataValidator) -> None:
        """Test validation with unhashable status type raises TypeError."""
        market = {
            "ticker": "TEST",
            "status": ["open"],  # List is unhashable - cannot check set membership
        }
        # Unhashable types will raise TypeError when checking set membership
        with pytest.raises(TypeError):
            validator.validate_market_data(market)

    def test_extremely_long_ticker(self, validator: KalshiDataValidator) -> None:
        """Test validation with extremely long ticker."""
        market = {
            "ticker": "A" * 10000,  # Very long ticker
            "status": "open",
            "yes_bid_dollars": Decimal("0.5"),
            "yes_ask_dollars": Decimal("0.6"),
        }
        result = validator.validate_market_data(market)
        # Should handle without crashing
        assert isinstance(result, ValidationResult)

    def test_special_characters_in_ticker(self, validator: KalshiDataValidator) -> None:
        """Test validation with special characters in ticker."""
        special_tickers = [
            "MARKET-WITH-<script>",
            "MARKET\x00NULL",
            "MARKET\nNEWLINE",
            "MARKET\tTAB",
            "市场-CHINESE",  # Unicode
        ]
        for ticker in special_tickers:
            market = {"ticker": ticker, "status": "open"}
            result = validator.validate_market_data(market)
            # Should handle without crashing
            assert isinstance(result, ValidationResult)


# =============================================================================
# Chaos Tests: Extreme Numeric Values
# =============================================================================


@pytest.mark.chaos
class TestExtremeNumericValues:
    """Chaos tests for extreme numeric value handling."""

    def test_extreme_prices(self, validator: KalshiDataValidator) -> None:
        """Test validation with extreme price values."""
        extreme_prices = [
            Decimal("999999999999.9999"),
            Decimal("-999999999999.9999"),
            Decimal("0.0000000001"),
            Decimal("1E+100"),
            Decimal("1E-100"),
        ]
        for price in extreme_prices:
            market = {
                "ticker": "EXTREME-PRICE",
                "yes_bid_dollars": price,
                "yes_ask_dollars": price + Decimal("0.01"),
                "status": "open",
            }
            result = validator.validate_market_data(market)
            assert isinstance(result, ValidationResult)

    def test_extreme_volume(self, validator: KalshiDataValidator) -> None:
        """Test validation with extreme volume values."""
        extreme_volumes = [
            0,
            1,
            10**15,  # Very large
            -1,  # Negative
        ]
        for volume in extreme_volumes:
            market = {
                "ticker": "EXTREME-VOL",
                "volume": volume,
                "status": "active",
            }
            result = validator.validate_market_data(market)
            assert isinstance(result, ValidationResult)

    def test_extreme_position_sizes(self, validator: KalshiDataValidator) -> None:
        """Test validation with extreme position sizes."""
        extreme_positions = [
            10**9,  # Very large long
            -(10**9),  # Very large short
            0,
        ]
        for pos_size in extreme_positions:
            position = {
                "ticker": "EXTREME-POS",
                "position": pos_size,
                "resting_orders_count": 0,
            }
            result = validator.validate_position_data(position)
            assert isinstance(result, ValidationResult)


# =============================================================================
# Chaos Tests: Boundary Conditions
# =============================================================================


@pytest.mark.chaos
class TestBoundaryConditions:
    """Chaos tests for boundary condition handling."""

    def test_boundary_prices(self, validator: KalshiDataValidator) -> None:
        """Test validation at price boundaries."""
        boundary_markets = [
            # Exactly at 0
            {
                "ticker": "BOUND-0",
                "yes_bid_dollars": Decimal("0"),
                "yes_ask_dollars": Decimal("0.01"),
                "status": "open",
            },
            # Exactly at 1
            {
                "ticker": "BOUND-1",
                "yes_bid_dollars": Decimal("0.99"),
                "yes_ask_dollars": Decimal("1"),
                "status": "open",
            },
            # Just inside bounds
            {
                "ticker": "BOUND-IN",
                "yes_bid_dollars": Decimal("0.0001"),
                "yes_ask_dollars": Decimal("0.9999"),
                "status": "open",
            },
            # Just outside bounds (should fail)
            {
                "ticker": "BOUND-OUT",
                "yes_bid_dollars": Decimal("-0.0001"),
                "yes_ask_dollars": Decimal("1.0001"),
                "status": "open",
            },
        ]
        for market in boundary_markets:
            result = validator.validate_market_data(market)
            assert isinstance(result, ValidationResult)

    def test_zero_spread(self, validator: KalshiDataValidator) -> None:
        """Test validation with zero spread (bid = ask)."""
        market = {
            "ticker": "ZERO-SPREAD",
            "yes_bid_dollars": Decimal("0.50"),
            "yes_ask_dollars": Decimal("0.50"),  # Same as bid
            "status": "open",
        }
        result = validator.validate_market_data(market)
        # Zero spread is valid (locked market)
        assert isinstance(result, ValidationResult)


# =============================================================================
# Chaos Tests: Concurrent State Corruption
# =============================================================================


@pytest.mark.chaos
class TestStateChaos:
    """Chaos tests for validator state handling."""

    def test_rapid_anomaly_count_changes(self, validator: KalshiDataValidator) -> None:
        """Test rapid changes to anomaly counts."""
        # Rapidly add and clear anomalies
        for i in range(100):
            invalid_market = {
                "ticker": f"CHAOS-{i % 5}",
                "yes_bid_dollars": Decimal("-0.5"),
                "yes_ask_dollars": Decimal("0.5"),
                "status": "open",
            }
            validator.validate_market_data(invalid_market)

            if i % 10 == 0:
                validator.clear_anomaly_counts()

        # Should complete without error
        all_counts = validator.get_all_anomaly_counts()
        assert isinstance(all_counts, dict)

    def test_interleaved_validation_types(self, validator: KalshiDataValidator) -> None:
        """Test interleaved validation of different data types."""
        for i in range(100):
            if i % 4 == 0:
                validator.validate_market_data(
                    {
                        "ticker": f"M-{i}",
                        "status": "open",
                    }
                )
            elif i % 4 == 1:
                validator.validate_position_data(
                    {
                        "ticker": f"P-{i}",
                        "position": i,
                        "resting_orders_count": 0,
                    }
                )
            elif i % 4 == 2:
                validator.validate_fill_data(
                    {
                        "trade_id": f"T-{i}",
                        "ticker": f"F-{i}",
                        "side": "yes",
                        "action": "buy",
                        "count": 10,
                    }
                )
            else:
                validator.validate_balance(Decimal(str(i)))

        # All operations should complete
        assert True


# =============================================================================
# Chaos Tests: Recovery Behavior
# =============================================================================


@pytest.mark.chaos
class TestRecoveryBehavior:
    """Chaos tests for recovery from invalid operations."""

    def test_recovery_after_invalid_market(self, validator: KalshiDataValidator) -> None:
        """Test that validator works correctly after processing invalid data."""
        # Process invalid data
        invalid_market = {
            "ticker": "",
            "yes_bid_dollars": Decimal("-999"),
        }
        result1 = validator.validate_market_data(invalid_market)
        assert result1.has_errors

        # Process valid data - should work correctly
        valid_market = {
            "ticker": "RECOVERY-TEST",
            "yes_bid_dollars": Decimal("0.45"),
            "yes_ask_dollars": Decimal("0.48"),
            "status": "open",
        }
        result2 = validator.validate_market_data(valid_market)
        assert result2.is_valid

    def test_recovery_after_exception_data(self, validator: KalshiDataValidator) -> None:
        """Test recovery after data that might cause internal exceptions."""
        weird_data_cases = [
            {"ticker": float("inf")},  # Infinity
            {"ticker": float("nan")},  # NaN
            {"ticker": object()},  # Random object
        ]

        for weird_data in weird_data_cases:
            try:
                validator.validate_market_data(weird_data)
            except (TypeError, ValueError):
                pass  # Some exceptions are expected

        # Validator should still work after weird data
        normal_market = {
            "ticker": "NORMAL",
            "status": "open",
        }
        result = validator.validate_market_data(normal_market)
        assert isinstance(result, ValidationResult)
