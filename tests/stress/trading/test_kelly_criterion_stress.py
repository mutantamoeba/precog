"""
Stress tests for kelly_criterion module.

Tests high-volume operations to validate behavior under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

pytestmark = [pytest.mark.stress]


class TestCalculateKellySizeStress:
    """Stress tests for calculate_kelly_size function."""

    def test_rapid_kelly_calculations(self) -> None:
        """Test rapid sequential Kelly calculations."""
        for i in range(5000):
            edge = Decimal(f"0.{i % 99 + 1:02d}")  # 0.01 to 0.99
            result = calculate_kelly_size(
                edge=edge,
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("10000"),
            )
            assert result >= Decimal("0")

    def test_concurrent_kelly_calculations(self) -> None:
        """Test concurrent Kelly calculations."""
        results = []
        lock = threading.Lock()

        def calculate(edge_val: str) -> Decimal:
            result = calculate_kelly_size(
                edge=Decimal(edge_val),
                kelly_fraction=Decimal("0.25"),
                bankroll=Decimal("10000"),
            )
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(calculate, f"0.{i % 50 + 1:02d}") for i in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200
        assert all(r >= Decimal("0") for r in results)

    def test_sustained_calculations_with_varying_inputs(self) -> None:
        """Test sustained calculations with varying inputs."""
        bankrolls = [Decimal("1000"), Decimal("10000"), Decimal("100000")]
        kelly_fractions = [Decimal("0.1"), Decimal("0.25"), Decimal("0.5"), Decimal("1.0")]

        for _ in range(100):
            for bankroll in bankrolls:
                for kelly in kelly_fractions:
                    for edge in range(1, 20):
                        result = calculate_kelly_size(
                            edge=Decimal(f"0.{edge:02d}"),
                            kelly_fraction=kelly,
                            bankroll=bankroll,
                        )
                        assert result >= Decimal("0")
                        assert result <= bankroll


class TestCalculateEdgeStress:
    """Stress tests for calculate_edge function."""

    def test_rapid_edge_calculations(self) -> None:
        """Test rapid sequential edge calculations."""
        for i in range(5000):
            true_prob = Decimal(f"0.{(i % 99) + 1:02d}")
            market_price = Decimal("0.50")
            result = calculate_edge(
                true_probability=true_prob,
                market_price=market_price,
            )
            # Result should be in valid range
            assert result >= Decimal("-1")
            assert result <= Decimal("1")

    def test_concurrent_edge_calculations(self) -> None:
        """Test concurrent edge calculations."""
        results = []
        lock = threading.Lock()

        def calculate(prob_val: str) -> Decimal:
            result = calculate_edge(
                true_probability=Decimal(prob_val),
                market_price=Decimal("0.50"),
                fees=Decimal("0.01"),
            )
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(calculate, f"0.{(i % 99) + 1:02d}") for i in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200


class TestCalculateOptimalPositionStress:
    """Stress tests for calculate_optimal_position function."""

    def test_rapid_optimal_position_calculations(self) -> None:
        """Test rapid sequential optimal position calculations."""
        for i in range(2000):
            true_prob = Decimal(f"0.{(i % 49) + 51:02d}")  # 0.51 to 0.99
            market_price = Decimal("0.50")
            result = calculate_optimal_position(
                true_probability=true_prob,
                market_price=market_price,
                bankroll=Decimal("10000"),
                kelly_fraction=Decimal("0.25"),
            )
            assert result >= Decimal("0")

    def test_concurrent_optimal_position_calculations(self) -> None:
        """Test concurrent optimal position calculations."""
        results = []
        lock = threading.Lock()

        def calculate(prob_val: str) -> Decimal:
            result = calculate_optimal_position(
                true_probability=Decimal(prob_val),
                market_price=Decimal("0.50"),
                bankroll=Decimal("10000"),
                kelly_fraction=Decimal("0.25"),
            )
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(calculate, f"0.{(i % 49) + 51:02d}") for i in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200

    def test_full_workflow_stress(self) -> None:
        """Test full workflow under stress."""
        for _ in range(500):
            # Simulate market analysis
            markets = [
                (Decimal("0.55"), Decimal("0.50")),
                (Decimal("0.60"), Decimal("0.50")),
                (Decimal("0.70"), Decimal("0.60")),
            ]

            for true_prob, market_price in markets:
                position = calculate_optimal_position(
                    true_probability=true_prob,
                    market_price=market_price,
                    bankroll=Decimal("10000"),
                    kelly_fraction=Decimal("0.25"),
                    fees=Decimal("0.01"),
                    min_edge=Decimal("0.02"),
                )
                assert position >= Decimal("0")
                assert position <= Decimal("10000")


class TestConstraintStress:
    """Stress tests for constraint handling."""

    def test_max_position_constraint_stress(self) -> None:
        """Test max_position constraint under stress."""
        for i in range(1000):
            max_pos = Decimal(str((i % 100) + 100))  # 100 to 199
            result = calculate_kelly_size(
                edge=Decimal("0.50"),  # High edge
                kelly_fraction=Decimal("1.0"),
                bankroll=Decimal("10000"),
                max_position=max_pos,
            )
            assert result <= max_pos

    def test_bankroll_cap_stress(self) -> None:
        """Test bankroll cap under stress."""
        for i in range(1000):
            bankroll = Decimal(str((i % 1000) + 1000))
            result = calculate_kelly_size(
                edge=Decimal("2.0"),  # Very high edge
                kelly_fraction=Decimal("1.0"),
                bankroll=bankroll,
            )
            assert result <= bankroll
