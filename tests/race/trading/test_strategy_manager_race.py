"""
Race Condition Tests for Strategy Manager.

Tests thread safety and concurrent access patterns.

Reference: TESTING_STRATEGY V3.2 - Race tests for concurrency
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003

Usage:
    pytest tests/race/trading/test_strategy_manager_race.py -v -m race
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from precog.trading.strategy_manager import (
    InvalidStatusTransitionError,
    StrategyManager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> StrategyManager:
    """Create a StrategyManager instance for testing."""
    return StrategyManager()


# =============================================================================
# Race Tests: Concurrent Config Operations
# =============================================================================


@pytest.mark.race
class TestConcurrentConfigOperations:
    """Race tests for concurrent config preparation/parsing."""

    def test_concurrent_config_preparations(self, manager: StrategyManager) -> None:
        """Test concurrent config preparation is thread-safe."""
        configs = [{"type": f"strategy_{i}", "value": Decimal(f"0.{i:04d}")} for i in range(100)]

        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def prepare_config(config: dict[str, Any]) -> None:
            try:
                result = manager._prepare_config_for_db(config)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Run preparations concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(prepare_config, config) for config in configs]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 100

    def test_concurrent_config_parsings(self, manager: StrategyManager) -> None:
        """Test concurrent config parsing is thread-safe."""
        db_configs = [{"type": f"strategy_{i}", "value": f"0.{i:04d}"} for i in range(100)]

        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def parse_config(config: dict[str, Any]) -> None:
            try:
                result = manager._parse_config_from_db(config)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(parse_config, config) for config in db_configs]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 100

    def test_concurrent_round_trips(self, manager: StrategyManager) -> None:
        """Test concurrent prepare -> parse round trips."""
        import json

        configs = [{"id": i, "value": Decimal(f"0.{i:04d}")} for i in range(50)]

        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def round_trip(config: dict[str, Any]) -> None:
            try:
                json_str = manager._prepare_config_for_db(config)
                parsed = json.loads(json_str)
                result = manager._parse_config_from_db(parsed)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(round_trip, config) for config in configs]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 50


# =============================================================================
# Race Tests: Concurrent Status Validation
# =============================================================================


@pytest.mark.race
class TestConcurrentStatusValidation:
    """Race tests for concurrent status transition validation."""

    def test_concurrent_valid_transitions(self, manager: StrategyManager) -> None:
        """Test concurrent valid status transition validations."""
        transitions = [
            ("draft", "testing"),
            ("testing", "active"),
            ("active", "inactive"),
            ("inactive", "deprecated"),
        ] * 25  # 100 total transitions

        results: list[bool] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_transition(from_status: str, to_status: str) -> None:
            try:
                manager._validate_status_transition(from_status, to_status)
                with lock:
                    results.append(True)
            except InvalidStatusTransitionError:
                with lock:
                    results.append(False)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(validate_transition, from_s, to_s) for from_s, to_s in transitions
            ]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 100
        assert all(results), "All valid transitions should succeed"

    def test_concurrent_mixed_transitions(self, manager: StrategyManager) -> None:
        """Test concurrent mix of valid and invalid transitions."""
        valid_transitions = [
            ("draft", "testing"),
            ("testing", "active"),
        ] * 25

        invalid_transitions = [
            ("deprecated", "active"),
            ("active", "draft"),
        ] * 25

        all_transitions = valid_transitions + invalid_transitions

        valid_count = 0
        invalid_count = 0
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_transition(from_status: str, to_status: str) -> None:
            nonlocal valid_count, invalid_count
            try:
                manager._validate_status_transition(from_status, to_status)
                with lock:
                    valid_count += 1
            except InvalidStatusTransitionError:
                with lock:
                    invalid_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(validate_transition, from_s, to_s)
                for from_s, to_s in all_transitions
            ]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert valid_count == 50, f"Expected 50 valid, got {valid_count}"
        assert invalid_count == 50, f"Expected 50 invalid, got {invalid_count}"


# =============================================================================
# Race Tests: Multiple Manager Instances
# =============================================================================


@pytest.mark.race
class TestMultipleManagerInstances:
    """Race tests for multiple manager instances."""

    def test_independent_manager_operations(self) -> None:
        """Test multiple manager instances operate independently."""
        managers = [StrategyManager() for _ in range(10)]
        configs = [{"manager": i, "value": Decimal(f"0.{i:04d}")} for i in range(10)]

        results: list[tuple[int, str]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def operate_manager(idx: int) -> None:
            try:
                manager = managers[idx]
                config = configs[idx]
                json_str = manager._prepare_config_for_db(config)
                with lock:
                    results.append((idx, json_str))
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(operate_manager, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 10

        # Verify each result contains expected manager index
        for idx, json_str in results:
            assert f'"manager": {idx}' in json_str

    def test_concurrent_manager_creation_and_use(self) -> None:
        """Test creating and using managers concurrently."""
        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_and_use(idx: int) -> None:
            try:
                # Create manager in thread
                manager = StrategyManager()
                config = {"thread": idx, "value": Decimal("0.05")}
                json_str = manager._prepare_config_for_db(config)
                with lock:
                    results.append(json_str)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_and_use, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 50


# =============================================================================
# Race Tests: Row Conversion
# =============================================================================


@pytest.mark.race
class TestConcurrentRowConversion:
    """Race tests for concurrent row to dict conversion."""

    def test_concurrent_row_conversions(self, manager: StrategyManager) -> None:
        """Test concurrent _row_to_dict calls."""
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("config",),
        ]

        rows = [(i, f"strategy_{i}", {"value": str(i)}) for i in range(100)]

        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def convert_row(row: tuple[Any, ...]) -> None:
            try:
                result = manager._row_to_dict(mock_cursor, row)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(convert_row, row) for row in rows]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 100


# =============================================================================
# Race Tests: Interleaved Operations
# =============================================================================


@pytest.mark.race
class TestInterleavedOperations:
    """Race tests for interleaved different operations."""

    def test_interleaved_prepare_parse_validate(self, manager: StrategyManager) -> None:
        """Test interleaved prepare, parse, and validate operations."""

        operations_completed: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def prepare_op() -> None:
            try:
                config = {"value": Decimal("0.05")}
                manager._prepare_config_for_db(config)
                with lock:
                    operations_completed.append("prepare")
            except Exception as e:
                with lock:
                    errors.append(e)

        def parse_op() -> None:
            try:
                db_config = {"value": "0.05"}
                manager._parse_config_from_db(db_config)
                with lock:
                    operations_completed.append("parse")
            except Exception as e:
                with lock:
                    errors.append(e)

        def validate_op() -> None:
            try:
                manager._validate_status_transition("draft", "testing")
                with lock:
                    operations_completed.append("validate")
            except Exception as e:
                with lock:
                    errors.append(e)

        # Submit mixed operations
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for _ in range(30):
                futures.append(executor.submit(prepare_op))
                futures.append(executor.submit(parse_op))
                futures.append(executor.submit(validate_op))

            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(operations_completed) == 90
        assert operations_completed.count("prepare") == 30
        assert operations_completed.count("parse") == 30
        assert operations_completed.count("validate") == 30

    def test_rapid_alternating_operations(self, manager: StrategyManager) -> None:
        """Test rapid alternation between operations."""
        import json

        results: list[Any] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def alternating_ops(idx: int) -> None:
            try:
                for _ in range(10):
                    if idx % 2 == 0:
                        config = {"idx": idx, "value": Decimal("0.05")}
                        json_str = manager._prepare_config_for_db(config)
                        parsed = json.loads(json_str)
                        manager._parse_config_from_db(parsed)
                    else:
                        manager._validate_status_transition("draft", "testing")
                        manager._validate_status_transition("testing", "active")

                with lock:
                    results.append(idx)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(alternating_ops, i) for i in range(20)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 20


# =============================================================================
# Race Tests: Data Consistency
# =============================================================================


@pytest.mark.race
class TestDataConsistency:
    """Race tests verifying data consistency under concurrency."""

    def test_decimal_precision_consistency(self, manager: StrategyManager) -> None:
        """Test Decimal precision is consistent under concurrent access."""
        import json

        test_value = Decimal("0.12345678901234567890")
        config = {"precision_test": test_value}

        results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def round_trip_check() -> None:
            try:
                json_str = manager._prepare_config_for_db(config)
                parsed = json.loads(json_str)
                result = manager._parse_config_from_db(parsed)

                with lock:
                    results.append(result["precision_test"])
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(round_trip_check) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 50

        # All results should have exact same value
        for result in results:
            assert result == test_value, f"Precision lost: {result} != {test_value}"

    def test_config_key_order_consistency(self, manager: StrategyManager) -> None:
        """Test config key order is consistent under concurrent access."""

        config = {
            "a": Decimal("0.1"),
            "b": Decimal("0.2"),
            "c": Decimal("0.3"),
        }

        json_results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def serialize() -> None:
            try:
                json_str = manager._prepare_config_for_db(config)
                with lock:
                    json_results.append(json_str)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(serialize) for _ in range(50)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(json_results) == 50

        # All JSON strings should be identical (deterministic serialization)
        first = json_results[0]
        for json_str in json_results:
            assert json_str == first, "Serialization not deterministic"
