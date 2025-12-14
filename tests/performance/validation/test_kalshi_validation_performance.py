"""
Performance Tests for Kalshi Data Validation.

Tests validation latency and throughput benchmarks.

Reference: TESTING_STRATEGY V3.2 - Performance tests for latency/throughput
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/performance/validation/test_kalshi_validation_performance.py -v -m performance
"""

import statistics
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
        "ticker": f"PERF-MARKET-{index:05d}",
        "status": "open",
        "yes_bid_dollars": Decimal("0.45"),
        "yes_ask_dollars": Decimal("0.48"),
        "no_bid_dollars": Decimal("0.52"),
        "no_ask_dollars": Decimal("0.55"),
        "volume": 1000,
        "open_interest": 500,
    }


# =============================================================================
# Performance Tests: Single Validation Latency
# =============================================================================


@pytest.mark.performance
class TestSingleValidationLatency:
    """Performance tests for single validation operation latency."""

    def test_market_validation_latency(self, validator: KalshiDataValidator) -> None:
        """Test market validation latency under 1ms."""
        market = create_market(0)
        latencies = []

        # Warm-up
        for _ in range(100):
            validator.validate_market_data(market)

        # Measure
        for _ in range(1000):
            start = time.perf_counter()
            validator.validate_market_data(market)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]

        # Average should be under 0.5ms, p99 under 2ms
        assert avg_latency < 0.5, f"Average latency too high: {avg_latency:.3f}ms"
        assert p99_latency < 2.0, f"P99 latency too high: {p99_latency:.3f}ms"

    def test_position_validation_latency(self, validator: KalshiDataValidator) -> None:
        """Test position validation latency."""
        position = {
            "ticker": "PERF-POS",
            "position": 100,
            "resting_orders_count": 0,
        }
        latencies = []

        # Warm-up
        for _ in range(100):
            validator.validate_position_data(position)

        # Measure
        for _ in range(1000):
            start = time.perf_counter()
            validator.validate_position_data(position)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        assert avg_latency < 0.5, f"Average latency too high: {avg_latency:.3f}ms"

    def test_balance_validation_latency(self, validator: KalshiDataValidator) -> None:
        """Test balance validation latency (should be very fast)."""
        balance = Decimal("5000.00")
        latencies = []

        # Warm-up
        for _ in range(100):
            validator.validate_balance(balance)

        # Measure
        for _ in range(1000):
            start = time.perf_counter()
            validator.validate_balance(balance)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        # Balance validation should be very fast (< 0.1ms)
        assert avg_latency < 0.1, f"Balance validation too slow: {avg_latency:.3f}ms"


# =============================================================================
# Performance Tests: Batch Validation Throughput
# =============================================================================


@pytest.mark.performance
class TestBatchValidationThroughput:
    """Performance tests for batch validation throughput."""

    def test_batch_market_throughput(self, validator: KalshiDataValidator) -> None:
        """Test markets validated per second."""
        markets = [create_market(i) for i in range(1000)]

        # Warm-up
        validator.validate_markets(markets[:100])

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            validator.validate_markets(markets)
        elapsed = time.perf_counter() - start

        total_validations = 10 * 1000
        throughput = total_validations / elapsed

        # Should achieve at least 10,000 validations per second
        assert throughput > 10000, f"Throughput too low: {throughput:.0f}/s"

    def test_batch_position_throughput(self, validator: KalshiDataValidator) -> None:
        """Test positions validated per second."""
        positions = [
            {"ticker": f"POS-{i}", "position": i, "resting_orders_count": 0} for i in range(1000)
        ]

        # Measure
        start = time.perf_counter()
        for _ in range(10):
            validator.validate_positions(positions)
        elapsed = time.perf_counter() - start

        throughput = (10 * 1000) / elapsed
        assert throughput > 10000, f"Position throughput too low: {throughput:.0f}/s"


# =============================================================================
# Performance Tests: Summary Generation
# =============================================================================


@pytest.mark.performance
class TestSummaryPerformance:
    """Performance tests for summary generation."""

    def test_summary_generation_speed(self, validator: KalshiDataValidator) -> None:
        """Test summary generation performance."""
        markets = [create_market(i) for i in range(1000)]
        results = validator.validate_markets(markets)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validator.get_validation_summary(results)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        # Summary of 1000 results should take < 5ms
        assert avg_latency < 5.0, f"Summary generation too slow: {avg_latency:.3f}ms"


# =============================================================================
# Performance Tests: Anomaly Tracking Overhead
# =============================================================================


@pytest.mark.performance
class TestAnomalyTrackingOverhead:
    """Performance tests for anomaly tracking overhead."""

    def test_valid_vs_invalid_validation_performance(self, validator: KalshiDataValidator) -> None:
        """Test that invalid data validation has minimal overhead vs valid data."""
        valid_market = create_market(0)
        invalid_market = {
            "ticker": "INVALID-MARKET",
            "yes_bid_dollars": Decimal("-0.5"),  # Invalid
            "yes_ask_dollars": Decimal("0.5"),
            "status": "open",
        }

        # Measure valid data
        start = time.perf_counter()
        for _ in range(10000):
            validator.validate_market_data(valid_market)
        time_valid = time.perf_counter() - start

        # Clear anomaly counts to reset state
        validator.clear_anomaly_counts()

        # Measure invalid data (triggers anomaly tracking)
        start = time.perf_counter()
        for _ in range(10000):
            validator.validate_market_data(invalid_market)
        time_invalid = time.perf_counter() - start

        # Invalid validation should add < 50% overhead (more lenient due to error processing)
        if time_valid > 0:
            overhead = (time_invalid - time_valid) / time_valid
            assert overhead < 0.50, f"Invalid data overhead too high: {overhead:.1%}"


# =============================================================================
# Performance Tests: Latency Stability
# =============================================================================


@pytest.mark.performance
class TestLatencyStability:
    """Performance tests for latency stability over time."""

    def test_latency_stability_over_iterations(self, validator: KalshiDataValidator) -> None:
        """Test that validation latency remains stable."""
        market = create_market(0)

        # Collect latencies in batches
        batch_averages = []
        for batch in range(10):
            latencies = []
            for _ in range(1000):
                start = time.perf_counter()
                validator.validate_market_data(market)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
            batch_averages.append(statistics.mean(latencies))

        # Check that batches have similar averages (stable performance)
        min_avg = min(batch_averages)
        max_avg = max(batch_averages)

        # Max should not be more than 3x min (allowing for some variance)
        assert max_avg < min_avg * 3, f"Latency unstable: min={min_avg:.3f}ms, max={max_avg:.3f}ms"
