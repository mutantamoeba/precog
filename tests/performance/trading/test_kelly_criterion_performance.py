"""
Performance tests for kelly_criterion module.

Validates latency and throughput requirements.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time
from decimal import Decimal

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

pytestmark = [pytest.mark.performance]


class TestCalculateKellySizePerformance:
    """Performance benchmarks for calculate_kelly_size function."""

    def test_kelly_calculation_latency(self) -> None:
        """Test Kelly calculation latency."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("10000"),
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_kelly_calculation_throughput(self) -> None:
        """Test Kelly calculation throughput."""
        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            calculate_kelly_size(
                edge=Decimal("0.10"),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("10000"),
            )
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 10000 calculations/sec
        # Note: Lower threshold for Windows/CI compatibility
        assert throughput > 10000, f"Throughput {throughput:.0f} ops/sec too low"

    def test_kelly_with_constraints_latency(self) -> None:
        """Test Kelly calculation with constraints latency."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            calculate_kelly_size(
                edge=Decimal("0.50"),  # High edge to trigger constraints
                kelly_fraction=Decimal("1.0"),
                bankroll=Decimal("10000"),
                max_position=Decimal("500"),
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"


class TestCalculateEdgePerformance:
    """Performance benchmarks for calculate_edge function."""

    def test_edge_calculation_latency(self) -> None:
        """Test edge calculation latency."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            calculate_edge(
                true_probability=Decimal("0.60"),
                market_price=Decimal("0.50"),
                fees=Decimal("0.01"),
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.1ms on average
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_edge_calculation_throughput(self) -> None:
        """Test edge calculation throughput."""
        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            calculate_edge(
                true_probability=Decimal("0.60"),
                market_price=Decimal("0.50"),
            )
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 20000 calculations/sec
        # Note: Lower threshold for Windows/CI compatibility
        assert throughput > 20000, f"Throughput {throughput:.0f} ops/sec too low"


class TestCalculateOptimalPositionPerformance:
    """Performance benchmarks for calculate_optimal_position function."""

    def test_optimal_position_latency(self) -> None:
        """Test optimal position calculation latency."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            calculate_optimal_position(
                true_probability=Decimal("0.65"),
                market_price=Decimal("0.55"),
                bankroll=Decimal("10000"),
                kelly_fraction=Decimal("0.25"),
                fees=Decimal("0.01"),
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should complete in <0.2ms on average (includes both edge and kelly)
        assert avg_latency < 0.0002, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_optimal_position_throughput(self) -> None:
        """Test optimal position calculation throughput."""
        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            calculate_optimal_position(
                true_probability=Decimal("0.65"),
                market_price=Decimal("0.55"),
                bankroll=Decimal("10000"),
                kelly_fraction=Decimal("0.25"),
            )
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 10000 calculations/sec
        # Note: Lower threshold for Windows/CI compatibility
        assert throughput > 10000, f"Throughput {throughput:.0f} ops/sec too low"


class TestDecimalPerformance:
    """Performance tests specific to Decimal arithmetic."""

    def test_decimal_multiplication_latency(self) -> None:
        """Test Decimal multiplication performance (used in Kelly formula)."""
        edge = Decimal("0.10")
        kelly_fraction = Decimal("0.25")
        bankroll = Decimal("10000")

        latencies = []
        for _ in range(10000):
            start = time.perf_counter()
            _ = edge * kelly_fraction * bankroll
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Pure Decimal math should be very fast
        assert avg_latency < 0.00001, f"Average latency {avg_latency * 1000000:.3f}us too high"

    def test_decimal_comparison_latency(self) -> None:
        """Test Decimal comparison performance."""
        value = Decimal("500")
        bankroll = Decimal("10000")
        max_pos = Decimal("600")

        latencies = []
        for _ in range(10000):
            start = time.perf_counter()
            _ = value > bankroll
            _ = value > max_pos
            _ = value < Decimal("0")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Pure Decimal comparison should be very fast
        assert avg_latency < 0.00001, f"Average latency {avg_latency * 1000000:.3f}us too high"


class TestBatchCalculationPerformance:
    """Performance tests for batch calculations."""

    def test_batch_kelly_calculations(self) -> None:
        """Test batch Kelly calculations for multiple opportunities."""
        # Simulate analyzing 100 market opportunities
        opportunities = [(Decimal(f"0.{i + 50:02d}"), Decimal("0.50")) for i in range(50)]

        start = time.perf_counter()
        positions = []
        for true_prob, market_price in opportunities:
            edge = calculate_edge(
                true_probability=true_prob,
                market_price=market_price,
            )
            if edge > Decimal("0.02"):
                pos = calculate_kelly_size(
                    edge=edge,
                    kelly_fraction=Decimal("0.25"),
                    bankroll=Decimal("10000"),
                )
                positions.append(pos)
        elapsed = time.perf_counter() - start

        # Processing 50 opportunities should take <10ms
        assert elapsed < 0.01, f"Batch processing took {elapsed * 1000:.3f}ms"

    def test_portfolio_allocation_performance(self) -> None:
        """Test performance for portfolio allocation scenario."""
        # Simulate allocating across 10 positions
        allocations = []
        bankroll = Decimal("100000")

        start = time.perf_counter()
        for i in range(10):
            true_prob = Decimal(f"0.{55 + i}")
            market_price = Decimal(f"0.{50 + i // 2}")

            position = calculate_optimal_position(
                true_probability=true_prob,
                market_price=market_price,
                bankroll=bankroll / 10,  # Divide bankroll
                kelly_fraction=Decimal("0.25"),
                fees=Decimal("0.01"),
                max_position=Decimal("5000"),
                min_edge=Decimal("0.02"),
            )
            allocations.append(position)
        elapsed = time.perf_counter() - start

        # Portfolio allocation should be fast
        assert elapsed < 0.005, f"Portfolio allocation took {elapsed * 1000:.3f}ms"
