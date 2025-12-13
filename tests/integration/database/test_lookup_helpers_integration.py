"""
Integration tests for lookup_helpers module.

Tests interaction between lookup functions and database layer.

Reference: TESTING_STRATEGY_V3.2.md Section "Integration Tests"
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.lookup_helpers import (
    add_model_class,
    add_strategy_type,
    get_model_classes,
    get_strategy_types,
    get_strategy_types_by_category,
    validate_model_class,
    validate_strategy_type,
)

pytestmark = [pytest.mark.integration]


class TestStrategyTypesIntegration:
    """Integration tests for strategy type functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_get_types_with_ordering(self, mock_fetch: MagicMock) -> None:
        """Verify types are returned in display_order."""
        mock_fetch.return_value = [
            {"strategy_type_code": "first", "display_order": 1, "category": "a"},
            {"strategy_type_code": "second", "display_order": 2, "category": "a"},
            {"strategy_type_code": "third", "display_order": 3, "category": "b"},
        ]

        result = get_strategy_types()

        assert result[0]["strategy_type_code"] == "first"
        assert result[-1]["strategy_type_code"] == "third"

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_category_grouping_maintains_order(self, mock_fetch: MagicMock) -> None:
        """Verify order is maintained within categories."""
        mock_fetch.return_value = [
            {"strategy_type_code": "a1", "display_order": 1, "category": "alpha"},
            {"strategy_type_code": "a2", "display_order": 2, "category": "alpha"},
            {"strategy_type_code": "b1", "display_order": 3, "category": "beta"},
        ]

        result = get_strategy_types_by_category()

        assert list(result["alpha"][0]["strategy_type_code"]) == list("a1")
        assert list(result["alpha"][1]["strategy_type_code"]) == list("a2")


class TestModelClassesIntegration:
    """Integration tests for model class functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_get_classes_with_complexity(self, mock_fetch: MagicMock) -> None:
        """Verify classes include complexity information."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "complexity_level": "simple", "category": "stat"},
            {"model_class_code": "ml", "complexity_level": "advanced", "category": "ml"},
        ]

        result = get_model_classes()

        assert result[0]["complexity_level"] == "simple"
        assert result[1]["complexity_level"] == "advanced"


class TestValidationIntegration:
    """Integration tests for validation functions."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_strategy_type_active_check(self, mock_fetch: MagicMock) -> None:
        """Verify active_only affects validation query."""
        mock_fetch.return_value = {"exists": True}

        # Default (active_only=True)
        validate_strategy_type("value")
        call1 = mock_fetch.call_args_list[0][0][0]

        # active_only=False
        validate_strategy_type("value", active_only=False)
        call2 = mock_fetch.call_args_list[1][0][0]

        assert "is_active = TRUE" in call1
        assert "is_active = TRUE" not in call2

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_model_class_active_check(self, mock_fetch: MagicMock) -> None:
        """Verify active_only affects validation query."""
        mock_fetch.return_value = {"exists": True}

        # Default (active_only=True)
        validate_model_class("elo")
        call1 = mock_fetch.call_args_list[0][0][0]

        # active_only=False
        validate_model_class("elo", active_only=False)
        call2 = mock_fetch.call_args_list[1][0][0]

        assert "is_active = TRUE" in call1
        assert "is_active = TRUE" not in call2


class TestAddFunctionsIntegration:
    """Integration tests for add functions."""

    @patch("precog.database.connection.get_cursor")
    def test_add_strategy_type_returns_inserted_row(self, mock_get_cursor: MagicMock) -> None:
        """Verify add_strategy_type returns inserted data."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "strategy_type_code": "test",
            "display_name": "Test Strategy",
            "description": "Test description",
            "category": "directional",
            "display_order": 100,
            "is_active": True,
        }
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = add_strategy_type(
            code="test",
            display_name="Test Strategy",
            description="Test description",
            category="directional",
            display_order=100,
        )

        assert result["strategy_type_code"] == "test"
        assert result["display_name"] == "Test Strategy"

    @patch("precog.database.connection.get_cursor")
    def test_add_model_class_returns_inserted_row(self, mock_get_cursor: MagicMock) -> None:
        """Verify add_model_class returns inserted data."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "model_class_code": "test",
            "display_name": "Test Model",
            "description": "Test description",
            "category": "statistical",
            "complexity_level": "simple",
            "display_order": 100,
            "is_active": True,
        }
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = add_model_class(
            code="test",
            display_name="Test Model",
            description="Test description",
            category="statistical",
            complexity_level="simple",
            display_order=100,
        )

        assert result["model_class_code"] == "test"
        assert result["complexity_level"] == "simple"
