"""
Race condition tests for lookup_helpers module.

Tests for race conditions in concurrent operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from precog.database.lookup_helpers import (
    get_model_classes_by_complexity,
    get_strategy_types,
    get_strategy_types_by_category,
    get_valid_model_classes,
    get_valid_strategy_types,
    validate_model_class,
    validate_strategy_type,
)

pytestmark = [pytest.mark.race]


class TestStrategyTypesRace:
    """Race condition tests for strategy type functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_concurrent_get_types_no_corruption(self, mock_fetch: MagicMock) -> None:
        """Verify concurrent queries don't corrupt results."""
        mock_fetch.return_value = [
            {"strategy_type_code": "value", "category": "directional"},
            {"strategy_type_code": "arbitrage", "category": "arbitrage"},
        ]

        results = []
        errors = []
        lock = threading.Lock()

        def query() -> None:
            try:
                result = get_strategy_types()
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=query) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        # All results should be identical
        assert all(len(r) == 2 for r in results)

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_concurrent_category_grouping_no_corruption(self, mock_fetch: MagicMock) -> None:
        """Verify concurrent grouping doesn't corrupt categories."""
        mock_fetch.return_value = [
            {"strategy_type_code": "a", "category": "cat1"},
            {"strategy_type_code": "b", "category": "cat2"},
            {"strategy_type_code": "c", "category": "cat1"},
        ]

        results = []
        errors = []
        lock = threading.Lock()

        def group() -> None:
            try:
                result = get_strategy_types_by_category()
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=group) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # All results should have same structure
        for r in results:
            assert len(r.get("cat1", [])) == 2
            assert len(r.get("cat2", [])) == 1


class TestModelClassesRace:
    """Race condition tests for model class functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_concurrent_get_classes_no_corruption(self, mock_fetch: MagicMock) -> None:
        """Verify concurrent queries don't corrupt results."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "category": "stat", "complexity_level": "simple"},
            {"model_class_code": "ml", "category": "ml", "complexity_level": "advanced"},
        ]

        results = []
        errors = []
        lock = threading.Lock()

        def query() -> None:
            try:
                from precog.database.lookup_helpers import get_model_classes

                result = get_model_classes()
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=query) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_concurrent_complexity_grouping_no_corruption(self, mock_fetch: MagicMock) -> None:
        """Verify concurrent complexity grouping doesn't corrupt."""
        mock_fetch.return_value = [
            {"model_class_code": "a", "category": "x", "complexity_level": "simple"},
            {"model_class_code": "b", "category": "y", "complexity_level": "advanced"},
        ]

        results = []
        errors = []
        lock = threading.Lock()

        def group() -> None:
            try:
                result = get_model_classes_by_complexity()
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=group) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestValidationRace:
    """Race condition tests for validation functions."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_concurrent_validation_consistent(self, mock_fetch: MagicMock) -> None:
        """Verify concurrent validation returns consistent results."""
        mock_fetch.return_value = {"exists": True}

        results = []
        errors = []
        lock = threading.Lock()

        def validate() -> None:
            try:
                r1 = validate_strategy_type("value")
                r2 = validate_model_class("elo")
                with lock:
                    results.append((r1, r2))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r == (True, True) for r in results)


class TestGetValidCodesRace:
    """Race condition tests for get_valid_* functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_concurrent_get_valid_codes_no_race(self, mock_fetch: MagicMock) -> None:
        """Verify concurrent valid code retrieval has no race conditions."""

        # Each function expects its own field, so provide proper data for both
        def mock_side_effect(query: str, *args: object, **kwargs: object) -> list[dict[str, str]]:
            if "strategy_type" in query.lower():
                return [
                    {"strategy_type_code": "type1"},
                    {"strategy_type_code": "type2"},
                ]
            if "model_class" in query.lower():
                return [
                    {"model_class_code": "class1"},
                    {"model_class_code": "class2"},
                ]
            return []

        mock_fetch.side_effect = mock_side_effect

        results = []
        errors = []
        lock = threading.Lock()

        def get_codes() -> None:
            try:
                strat = get_valid_strategy_types()
                model = get_valid_model_classes()
                with lock:
                    results.append((strat, model))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=get_codes) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 50
