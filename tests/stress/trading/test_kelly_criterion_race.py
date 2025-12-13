"""
Race condition tests for kelly_criterion module.

Tests for race conditions in concurrent operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading
from decimal import Decimal

import pytest

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)

pytestmark = [pytest.mark.race]


class TestCalculateKellySizeRace:
    """Race condition tests for calculate_kelly_size function."""

    def test_concurrent_calculations_consistent(self) -> None:
        """Verify concurrent calculations return consistent results."""
        results = []
        errors = []
        lock = threading.Lock()

        # Use same inputs for all threads
        edge = Decimal("0.10")
        kelly_fraction = Decimal("0.25")
        bankroll = Decimal("10000")
        expected = Decimal("250")

        def calculate() -> None:
            try:
                result = calculate_kelly_size(
                    edge=edge,
                    kelly_fraction=kelly_fraction,
                    bankroll=bankroll,
                )
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=calculate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        # All results should be identical
        assert all(r == expected for r in results)

    def test_concurrent_calculations_no_corruption(self) -> None:
        """Verify concurrent calculations don't corrupt shared state."""
        results = []
        errors = []
        lock = threading.Lock()

        def calculate(edge_val: str) -> None:
            try:
                result = calculate_kelly_size(
                    edge=Decimal(edge_val),
                    kelly_fraction=Decimal("0.25"),
                    bankroll=Decimal("10000"),
                )
                with lock:
                    results.append((edge_val, result))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=calculate, args=(f"0.{i:02d}",)) for i in range(1, 51)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 50


class TestCalculateEdgeRace:
    """Race condition tests for calculate_edge function."""

    def test_concurrent_edge_calculations_consistent(self) -> None:
        """Verify concurrent edge calculations are consistent."""
        results = []
        errors = []
        lock = threading.Lock()

        true_prob = Decimal("0.60")
        market_price = Decimal("0.50")
        expected = Decimal("0.10")

        def calculate() -> None:
            try:
                result = calculate_edge(
                    true_probability=true_prob,
                    market_price=market_price,
                )
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=calculate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r == expected for r in results)


class TestCalculateOptimalPositionRace:
    """Race condition tests for calculate_optimal_position function."""

    def test_concurrent_optimal_position_consistent(self) -> None:
        """Verify concurrent optimal position calculations are consistent."""
        results = []
        errors = []
        lock = threading.Lock()

        true_prob = Decimal("0.65")
        market_price = Decimal("0.55")
        bankroll = Decimal("10000")
        kelly_fraction = Decimal("0.25")

        def calculate() -> None:
            try:
                result = calculate_optimal_position(
                    true_probability=true_prob,
                    market_price=market_price,
                    bankroll=bankroll,
                    kelly_fraction=kelly_fraction,
                )
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=calculate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        # All results should be identical
        first_result = results[0]
        assert all(r == first_result for r in results)


class TestMixedOperationsRace:
    """Race condition tests for mixed operations."""

    def test_concurrent_edge_and_kelly_calculations(self) -> None:
        """Verify concurrent edge and kelly calculations are independent."""
        edge_results = []
        kelly_results = []
        errors = []
        lock = threading.Lock()

        def calculate_edge_only() -> None:
            try:
                result = calculate_edge(
                    true_probability=Decimal("0.60"),
                    market_price=Decimal("0.50"),
                )
                with lock:
                    edge_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        def calculate_kelly_only() -> None:
            try:
                result = calculate_kelly_size(
                    edge=Decimal("0.10"),
                    kelly_fraction=Decimal("0.25"),
                    bankroll=Decimal("10000"),
                )
                with lock:
                    kelly_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(100):
            if i % 2 == 0:
                threads.append(threading.Thread(target=calculate_edge_only))
            else:
                threads.append(threading.Thread(target=calculate_kelly_only))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(edge_results) == 50
        assert len(kelly_results) == 50

        # All edge results should be identical
        assert all(r == Decimal("0.10") for r in edge_results)
        # All kelly results should be identical
        assert all(r == Decimal("250") for r in kelly_results)


class TestValidationRace:
    """Race condition tests for input validation."""

    def test_concurrent_invalid_inputs_no_crash(self) -> None:
        """Verify concurrent invalid inputs don't crash."""
        errors_caught = []
        unexpected_errors = []
        lock = threading.Lock()

        def try_invalid_kelly_fraction() -> None:
            try:
                calculate_kelly_size(
                    edge=Decimal("0.10"),
                    kelly_fraction=Decimal("1.5"),  # Invalid
                    bankroll=Decimal("10000"),
                )
            except ValueError:
                with lock:
                    errors_caught.append("kelly")
            except Exception as e:
                with lock:
                    unexpected_errors.append(e)

        def try_invalid_bankroll() -> None:
            try:
                calculate_kelly_size(
                    edge=Decimal("0.10"),
                    kelly_fraction=Decimal("0.25"),
                    bankroll=Decimal("-1000"),  # Invalid
                )
            except ValueError:
                with lock:
                    errors_caught.append("bankroll")
            except Exception as e:
                with lock:
                    unexpected_errors.append(e)

        threads = []
        for i in range(50):
            if i % 2 == 0:
                threads.append(threading.Thread(target=try_invalid_kelly_fraction))
            else:
                threads.append(threading.Thread(target=try_invalid_bankroll))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(unexpected_errors) == 0, f"Unexpected errors: {unexpected_errors}"
        assert len(errors_caught) == 50  # All should raise ValueError
