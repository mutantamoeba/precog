"""
Race Condition Tests for Kalshi Data Validation.

Tests validation under concurrent access to detect race conditions.

Reference: TESTING_STRATEGY V3.2 - Race tests for concurrent operation validation
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/stress/validation/test_kalshi_validation_race.py -v -m race
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any

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


def create_market(index: int) -> dict[str, Any]:
    """Create a market data dict with given index."""
    return {
        "ticker": f"RACE-MARKET-{index:05d}",
        "status": "open",
        "yes_bid_dollars": Decimal("0.45"),
        "yes_ask_dollars": Decimal("0.48"),
        "no_bid_dollars": Decimal("0.52"),
        "no_ask_dollars": Decimal("0.55"),
        "volume": 1000,
    }


# =============================================================================
# Race Condition Tests: Concurrent Validation
# =============================================================================


@pytest.mark.race
class TestConcurrentValidation:
    """Race condition tests for concurrent validation operations."""

    def test_concurrent_market_validation(self, validator: KalshiDataValidator) -> None:
        """Test concurrent market validation from multiple threads."""
        results: list[ValidationResult] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_market(index: int) -> None:
            try:
                market = create_market(index)
                result = validator.validate_market_data(market)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Run 100 concurrent validations
        threads = []
        for i in range(100):
            t = threading.Thread(target=validate_market, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent validation: {errors}"
        assert len(results) == 100
        assert all(r.is_valid for r in results)

    def test_concurrent_position_validation(self, validator: KalshiDataValidator) -> None:
        """Test concurrent position validation."""
        results: list[ValidationResult] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_position(index: int) -> None:
            try:
                position = {
                    "ticker": f"POS-{index}",
                    "position": index % 100,
                    "resting_orders_count": 0,
                }
                result = validator.validate_position_data(position)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(50):
            t = threading.Thread(target=validate_position, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50
        assert all(r.is_valid for r in results)


# =============================================================================
# Race Condition Tests: Concurrent Anomaly Tracking
# =============================================================================


@pytest.mark.race
class TestConcurrentAnomalyTracking:
    """Race condition tests for concurrent anomaly tracking."""

    def test_concurrent_anomaly_updates(self, validator: KalshiDataValidator) -> None:
        """Test concurrent updates to anomaly counts."""
        errors: list[Exception] = []

        def trigger_anomaly(market_id: str) -> None:
            try:
                invalid_market = {
                    "ticker": market_id,
                    "yes_bid_dollars": Decimal("-0.5"),  # Invalid
                    "yes_ask_dollars": Decimal("0.5"),
                    "status": "open",
                }
                validator.validate_market_data(invalid_market)
            except Exception as e:
                errors.append(e)

        # Concurrent anomaly updates to SAME market
        threads = []
        for _ in range(50):
            t = threading.Thread(target=trigger_anomaly, args=("CONCURRENT-MARKET",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        # All 50 anomalies should be tracked
        count = validator.get_anomaly_count("CONCURRENT-MARKET")
        assert count >= 50

    def test_concurrent_anomaly_reads_and_writes(self, validator: KalshiDataValidator) -> None:
        """Test concurrent reads and writes to anomaly tracking."""
        errors: list[Exception] = []

        def read_or_write(index: int) -> None:
            try:
                if index % 2 == 0:
                    # Write
                    invalid_market = {
                        "ticker": f"RW-{index % 10}",
                        "yes_bid_dollars": Decimal("-0.5"),
                        "yes_ask_dollars": Decimal("0.5"),
                        "status": "open",
                    }
                    validator.validate_market_data(invalid_market)
                else:
                    # Read
                    validator.get_anomaly_count(f"RW-{index % 10}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(100):
            t = threading.Thread(target=read_or_write, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0


# =============================================================================
# Race Condition Tests: ThreadPoolExecutor
# =============================================================================


@pytest.mark.race
class TestThreadPoolValidation:
    """Race condition tests using ThreadPoolExecutor."""

    def test_thread_pool_market_validation(self, validator: KalshiDataValidator) -> None:
        """Test market validation using thread pool."""
        markets = [create_market(i) for i in range(100)]

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validator.validate_market_data, m) for m in markets]

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        assert len(results) == 100
        assert all(r.is_valid for r in results)

    def test_thread_pool_mixed_operations(self, validator: KalshiDataValidator) -> None:
        """Test mixed validation operations using thread pool."""
        operations: list[tuple[str, Any]] = []

        # Mix of market, position, and balance validations
        for i in range(30):
            operations.append(("market", create_market(i)))
            operations.append(
                ("position", {"ticker": f"POS-{i}", "position": i, "resting_orders_count": 0})
            )
            operations.append(("balance", Decimal(f"{1000 + i}.00")))

        def execute_operation(op: tuple[str, Any]) -> ValidationResult:
            op_type, data = op
            if op_type == "market":
                return validator.validate_market_data(data)
            if op_type == "position":
                return validator.validate_position_data(data)
            return validator.validate_balance(data)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(execute_operation, op) for op in operations]

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        assert len(results) == 90  # 30 * 3 operations
        assert all(r.is_valid for r in results)


# =============================================================================
# Race Condition Tests: Clear While Validating
# =============================================================================


@pytest.mark.race
class TestClearWhileValidating:
    """Race condition tests for clearing anomalies while validating."""

    def test_clear_during_validation(self, validator: KalshiDataValidator) -> None:
        """Test clearing anomaly counts during concurrent validation."""
        errors: list[Exception] = []
        validation_complete = threading.Event()

        def validate_many() -> None:
            try:
                for i in range(100):
                    invalid_market = {
                        "ticker": f"CLEAR-TEST-{i}",
                        "yes_bid_dollars": Decimal("-0.5"),
                        "yes_ask_dollars": Decimal("0.5"),
                        "status": "open",
                    }
                    validator.validate_market_data(invalid_market)
                validation_complete.set()
            except Exception as e:
                errors.append(e)

        def clear_periodically() -> None:
            try:
                for _ in range(10):
                    validator.clear_anomaly_counts()
                    threading.Event().wait(0.01)  # Small delay
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=validate_many)
        t2 = threading.Thread(target=clear_periodically)

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        # No errors should occur despite concurrent clear operations
        assert len(errors) == 0
