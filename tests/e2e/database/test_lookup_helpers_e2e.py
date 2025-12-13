"""
End-to-End tests for lookup_helpers module.

Tests complete workflows with mocked database responses.

Reference: TESTING_STRATEGY_V3.2.md Section "E2E Tests"
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

pytestmark = [pytest.mark.e2e]


class TestStrategyTypeWorkflowE2E:
    """E2E tests for strategy type workflows."""

    @patch("precog.database.lookup_helpers.fetch_all")
    @patch("precog.database.lookup_helpers.fetch_one")
    def test_complete_strategy_type_workflow(
        self, mock_fetch_one: MagicMock, mock_fetch_all: MagicMock
    ) -> None:
        """Test complete workflow: list -> validate -> get valid codes."""
        # Setup mock data
        strategy_types = [
            {
                "strategy_type_code": "value",
                "display_name": "Value Trading",
                "description": "Exploit market mispricing",
                "category": "directional",
                "display_order": 1,
                "is_active": True,
            },
            {
                "strategy_type_code": "arbitrage",
                "display_name": "Arbitrage",
                "description": "Cross-platform arbitrage",
                "category": "arbitrage",
                "display_order": 2,
                "is_active": True,
            },
        ]
        mock_fetch_all.return_value = strategy_types
        mock_fetch_one.return_value = {"exists": True}

        # Step 1: Get all strategy types
        all_types = get_strategy_types()
        assert len(all_types) == 2

        # Step 2: Get types by category
        by_category = get_strategy_types_by_category()
        assert "directional" in by_category
        assert "arbitrage" in by_category

        # Step 3: Get valid codes
        valid_codes = get_valid_strategy_types()
        assert "value" in valid_codes
        assert "arbitrage" in valid_codes

        # Step 4: Validate a type
        is_valid = validate_strategy_type("value")
        assert is_valid is True


class TestModelClassWorkflowE2E:
    """E2E tests for model class workflows."""

    @patch("precog.database.lookup_helpers.fetch_all")
    @patch("precog.database.lookup_helpers.fetch_one")
    def test_complete_model_class_workflow(
        self, mock_fetch_one: MagicMock, mock_fetch_all: MagicMock
    ) -> None:
        """Test complete workflow: list -> filter -> validate."""
        # Setup mock data
        model_classes = [
            {
                "model_class_code": "elo",
                "display_name": "Elo Rating System",
                "description": "Chess-style rating system",
                "category": "statistical",
                "complexity_level": "simple",
                "display_order": 1,
                "is_active": True,
            },
            {
                "model_class_code": "ensemble",
                "display_name": "Ensemble Model",
                "description": "Multiple model combination",
                "category": "hybrid",
                "complexity_level": "advanced",
                "display_order": 2,
                "is_active": True,
            },
        ]
        mock_fetch_all.return_value = model_classes
        mock_fetch_one.return_value = {"exists": True}

        # Step 1: Get all model classes
        all_classes = get_model_classes()
        assert len(all_classes) == 2

        # Step 2: Get by category
        by_category = get_model_classes_by_category()
        assert "statistical" in by_category
        assert "hybrid" in by_category

        # Step 3: Get by complexity
        by_complexity = get_model_classes_by_complexity()
        assert "simple" in by_complexity
        assert "advanced" in by_complexity

        # Step 4: Get valid codes
        valid_codes = get_valid_model_classes()
        assert "elo" in valid_codes
        assert "ensemble" in valid_codes

        # Step 5: Validate a class
        is_valid = validate_model_class("elo")
        assert is_valid is True


class TestValidationWorkflowE2E:
    """E2E tests for validation workflows."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validation_workflow_valid_input(self, mock_fetch: MagicMock) -> None:
        """Test validation workflow for valid inputs."""
        mock_fetch.return_value = {"exists": True}

        # Both should validate successfully
        assert validate_strategy_type("value") is True
        assert validate_model_class("elo") is True

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validation_workflow_invalid_input(self, mock_fetch: MagicMock) -> None:
        """Test validation workflow for invalid inputs."""
        mock_fetch.return_value = {"exists": False}

        # Both should fail validation
        assert validate_strategy_type("nonexistent") is False
        assert validate_model_class("nonexistent") is False


class TestEmptyDatabaseE2E:
    """E2E tests for empty database scenarios."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_empty_strategy_types(self, mock_fetch: MagicMock) -> None:
        """Test handling of empty strategy types table."""
        mock_fetch.return_value = []

        types = get_strategy_types()
        by_category = get_strategy_types_by_category()
        valid_codes = get_valid_strategy_types()

        assert types == []
        assert by_category == {}
        assert valid_codes == []

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_empty_model_classes(self, mock_fetch: MagicMock) -> None:
        """Test handling of empty model classes table."""
        mock_fetch.return_value = []

        classes = get_model_classes()
        by_category = get_model_classes_by_category()
        by_complexity = get_model_classes_by_complexity()
        valid_codes = get_valid_model_classes()

        assert classes == []
        assert by_category == {}
        assert by_complexity == {}
        assert valid_codes == []
