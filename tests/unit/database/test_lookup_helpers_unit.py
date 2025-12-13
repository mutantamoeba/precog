"""
Unit tests for lookup_helpers module.

Tests individual functions in isolation with mocked database.

Reference: TESTING_STRATEGY_V3.2.md Section "Unit Tests"
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.lookup_helpers import (
    get_model_classes,
    get_model_classes_by_category,
    get_model_classes_by_complexity,
    get_strategy_types,
    get_strategy_types_by_category,
    get_valid_model_classes,
    get_valid_strategy_types,
    validate_model_class,
    validate_strategy_type,
)

pytestmark = [pytest.mark.unit]


class TestGetStrategyTypesUnit:
    """Unit tests for get_strategy_types function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_returns_strategy_types(self, mock_fetch: MagicMock) -> None:
        """Verify strategy types are returned from database."""
        mock_fetch.return_value = [
            {"strategy_type_code": "value", "display_name": "Value Trading"},
            {"strategy_type_code": "arbitrage", "display_name": "Arbitrage"},
        ]

        result = get_strategy_types()

        assert len(result) == 2
        assert result[0]["strategy_type_code"] == "value"

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_active_only_default_true(self, mock_fetch: MagicMock) -> None:
        """Verify active_only defaults to True."""
        mock_fetch.return_value = []

        get_strategy_types()

        # Should include WHERE is_active = TRUE
        call_args = mock_fetch.call_args[0][0]
        assert "is_active = TRUE" in call_args

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_active_only_false(self, mock_fetch: MagicMock) -> None:
        """Verify active_only=False returns all types."""
        mock_fetch.return_value = []

        get_strategy_types(active_only=False)

        # Should NOT include WHERE clause
        call_args = mock_fetch.call_args[0][0]
        assert "is_active = TRUE" not in call_args


class TestGetStrategyTypesByCategoryUnit:
    """Unit tests for get_strategy_types_by_category function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_groups_by_category(self, mock_fetch: MagicMock) -> None:
        """Verify types are grouped by category."""
        mock_fetch.return_value = [
            {"strategy_type_code": "value", "category": "directional"},
            {"strategy_type_code": "arbitrage", "category": "arbitrage"},
            {"strategy_type_code": "momentum", "category": "directional"},
        ]

        result = get_strategy_types_by_category()

        assert "directional" in result
        assert "arbitrage" in result
        assert len(result["directional"]) == 2
        assert len(result["arbitrage"]) == 1


class TestValidateStrategyTypeUnit:
    """Unit tests for validate_strategy_type function."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_returns_true_for_valid_type(self, mock_fetch: MagicMock) -> None:
        """Verify True returned for valid strategy type."""
        mock_fetch.return_value = {"exists": True}

        result = validate_strategy_type("value")

        assert result is True

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_returns_false_for_invalid_type(self, mock_fetch: MagicMock) -> None:
        """Verify False returned for invalid strategy type."""
        mock_fetch.return_value = {"exists": False}

        result = validate_strategy_type("invalid")

        assert result is False

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_returns_false_for_none_result(self, mock_fetch: MagicMock) -> None:
        """Verify False returned when fetch returns None."""
        mock_fetch.return_value = None

        result = validate_strategy_type("value")

        assert result is False


class TestGetValidStrategyTypesUnit:
    """Unit tests for get_valid_strategy_types function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_returns_code_list(self, mock_fetch: MagicMock) -> None:
        """Verify list of codes is returned."""
        mock_fetch.return_value = [
            {"strategy_type_code": "value", "display_name": "Value"},
            {"strategy_type_code": "arbitrage", "display_name": "Arbitrage"},
        ]

        result = get_valid_strategy_types()

        assert result == ["value", "arbitrage"]


class TestGetModelClassesUnit:
    """Unit tests for get_model_classes function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_returns_model_classes(self, mock_fetch: MagicMock) -> None:
        """Verify model classes are returned from database."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "display_name": "Elo Rating"},
            {"model_class_code": "ensemble", "display_name": "Ensemble"},
        ]

        result = get_model_classes()

        assert len(result) == 2
        assert result[0]["model_class_code"] == "elo"


class TestGetModelClassesByCategoryUnit:
    """Unit tests for get_model_classes_by_category function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_groups_by_category(self, mock_fetch: MagicMock) -> None:
        """Verify classes are grouped by category."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "category": "statistical"},
            {"model_class_code": "ml", "category": "machine_learning"},
        ]

        result = get_model_classes_by_category()

        assert "statistical" in result
        assert "machine_learning" in result


class TestGetModelClassesByComplexityUnit:
    """Unit tests for get_model_classes_by_complexity function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_groups_by_complexity(self, mock_fetch: MagicMock) -> None:
        """Verify classes are grouped by complexity level."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "complexity_level": "simple"},
            {"model_class_code": "ml", "complexity_level": "advanced"},
        ]

        result = get_model_classes_by_complexity()

        assert "simple" in result
        assert "advanced" in result


class TestValidateModelClassUnit:
    """Unit tests for validate_model_class function."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_returns_true_for_valid_class(self, mock_fetch: MagicMock) -> None:
        """Verify True returned for valid model class."""
        mock_fetch.return_value = {"exists": True}

        result = validate_model_class("elo")

        assert result is True

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_returns_false_for_invalid_class(self, mock_fetch: MagicMock) -> None:
        """Verify False returned for invalid model class."""
        mock_fetch.return_value = {"exists": False}

        result = validate_model_class("invalid")

        assert result is False


class TestGetValidModelClassesUnit:
    """Unit tests for get_valid_model_classes function."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_returns_code_list(self, mock_fetch: MagicMock) -> None:
        """Verify list of codes is returned."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "display_name": "Elo"},
            {"model_class_code": "ensemble", "display_name": "Ensemble"},
        ]

        result = get_valid_model_classes()

        assert result == ["elo", "ensemble"]
