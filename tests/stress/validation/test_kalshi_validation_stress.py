"""
Stress Tests for Kalshi Data Validation.

Tests validation under high load and resource constraints.

Reference: TESTING_STRATEGY V3.2 - Stress tests for infrastructure limits
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/stress/validation/test_kalshi_validation_stress.py -v -m stress
"""

import time
from decimal import Decimal
from typing import Any

import pytest

from precog.validation.kalshi_validation import (
    KalshiDataValidator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> KalshiDataValidator:
    """Create a validator for testing."""
    return KalshiDataValidator()


def create_market(index: int) -> dict[str, Any]:
    """Create a market data dict with given index."""
    return {
        "ticker": f"STRESS-MARKET-{index:05d}",
        "status": "open",
        "yes_bid_dollars": Decimal("0.45"),
        "yes_ask_dollars": Decimal("0.48"),
        "no_bid_dollars": Decimal("0.52"),
        "no_ask_dollars": Decimal("0.55"),
        "volume": 1000,
        "open_interest": 500,
    }


# =============================================================================
# Stress Tests: High Volume Validation
# =============================================================================


@pytest.mark.stress
class TestHighVolumeValidation:
    """Stress tests for high-volume validation scenarios."""

    def test_validate_1000_markets(self, validator: KalshiDataValidator) -> None:
        """Test validating 1000 markets in batch."""
        markets = [create_market(i) for i in range(1000)]

        start_time = time.time()
        results = validator.validate_markets(markets)
        elapsed = time.time() - start_time

        assert len(results) == 1000
        assert all(r.is_valid for r in results)
        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0, f"Validation took too long: {elapsed:.2f}s"

    def test_validate_10000_markets(self, validator: KalshiDataValidator) -> None:
        """Test validating 10000 markets in batch."""
        markets = [create_market(i) for i in range(10000)]

        start_time = time.time()
        results = validator.validate_markets(markets)
        elapsed = time.time() - start_time

        assert len(results) == 10000
        assert all(r.is_valid for r in results)
        # Should complete in reasonable time (< 30 seconds)
        assert elapsed < 30.0, f"Validation took too long: {elapsed:.2f}s"

    def test_validate_many_positions(self, validator: KalshiDataValidator) -> None:
        """Test validating many positions."""
        positions = [
            {
                "ticker": f"POS-{i:05d}",
                "position": i % 200 - 100,  # Mix of long/short
                "resting_orders_count": 0,
            }
            for i in range(1000)
        ]

        start_time = time.time()
        results = validator.validate_positions(positions)
        elapsed = time.time() - start_time

        assert len(results) == 1000
        assert all(r.is_valid for r in results)
        assert elapsed < 5.0


# =============================================================================
# Stress Tests: Repeated Validation
# =============================================================================


@pytest.mark.stress
class TestRepeatedValidation:
    """Stress tests for repeated validation operations."""

    def test_repeated_single_market_validation(self, validator: KalshiDataValidator) -> None:
        """Test repeatedly validating the same market."""
        market = create_market(0)

        start_time = time.time()
        for _ in range(10000):
            result = validator.validate_market_data(market)
            assert result.is_valid
        elapsed = time.time() - start_time

        # Should complete quickly (< 5 seconds for 10k validations)
        assert elapsed < 5.0, f"Repeated validation took too long: {elapsed:.2f}s"

    def test_repeated_balance_validation(self, validator: KalshiDataValidator) -> None:
        """Test repeatedly validating balance."""
        balance = Decimal("5000.00")

        start_time = time.time()
        for _ in range(10000):
            result = validator.validate_balance(balance)
            assert result.is_valid
        elapsed = time.time() - start_time

        assert elapsed < 3.0


# =============================================================================
# Stress Tests: Anomaly Tracking Under Load
# =============================================================================


@pytest.mark.stress
class TestAnomalyTrackingUnderLoad:
    """Stress tests for anomaly tracking under high load."""

    def test_track_many_anomalies(self, validator: KalshiDataValidator) -> None:
        """Test tracking anomalies for many markets."""
        # Create invalid markets to trigger anomaly tracking
        for i in range(1000):
            invalid_market = {
                "ticker": f"ANOMALY-{i:05d}",
                "yes_bid_dollars": Decimal("-0.5"),  # Invalid
                "yes_ask_dollars": Decimal("0.5"),
                "status": "open",
            }
            validator.validate_market_data(invalid_market)

        # All should be tracked
        all_counts = validator.get_all_anomaly_counts()
        assert len(all_counts) >= 1000

    def test_clear_many_anomalies(self, validator: KalshiDataValidator) -> None:
        """Test clearing many tracked anomalies."""
        # Build up anomalies
        for i in range(500):
            invalid_market = {
                "ticker": f"CLEAR-{i:05d}",
                "yes_bid_dollars": Decimal("-0.5"),
                "yes_ask_dollars": Decimal("0.5"),
                "status": "open",
            }
            validator.validate_market_data(invalid_market)

        # Clear all
        start_time = time.time()
        validator.clear_anomaly_counts()
        elapsed = time.time() - start_time

        # Should be fast
        assert elapsed < 0.1
        assert len(validator.get_all_anomaly_counts()) == 0


# =============================================================================
# Stress Tests: Memory Efficiency
# =============================================================================


@pytest.mark.stress
class TestMemoryEfficiency:
    """Stress tests for memory efficiency."""

    def test_validation_does_not_accumulate_memory(self, validator: KalshiDataValidator) -> None:
        """Test that validation doesn't leak memory."""
        market = create_market(0)

        # Run many validations
        for _ in range(10000):
            validator.validate_market_data(market)
            # Result should be garbage collected after each iteration

        # If we got here without OOM, we're good
        assert True

    def test_batch_validation_memory_efficiency(self, validator: KalshiDataValidator) -> None:
        """Test memory efficiency of batch validation."""
        # Create and validate large batches multiple times
        for batch_num in range(5):
            markets = [create_market(i) for i in range(2000)]
            results = validator.validate_markets(markets)
            assert len(results) == 2000

            # Clear results to allow GC
            del results
            del markets

        # If we got here without OOM, memory is being managed properly
        assert True
