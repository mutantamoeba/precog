"""
Property-based tests for lookup_helpers module.

Tests invariants and properties using Hypothesis.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.database.lookup_helpers import (
    get_model_classes_by_category,
    get_model_classes_by_complexity,
    get_strategy_types_by_category,
    get_valid_model_classes,
    get_valid_strategy_types,
)

pytestmark = [pytest.mark.property]


class TestStrategyTypesProperties:
    """Property tests for strategy type functions."""

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "strategy_type_code": st.text(min_size=1, max_size=20),
                    "display_name": st.text(min_size=1, max_size=50),
                    "category": st.sampled_from(["directional", "arbitrage", "risk_management"]),
                }
            ),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_by_category_preserves_all_types(self, types: list) -> None:
        """All input types should appear in grouped output."""
        with patch("precog.database.lookup_helpers.fetch_all") as mock:
            mock.return_value = types

            result = get_strategy_types_by_category()

            # Count total items in all categories
            total = sum(len(v) for v in result.values())
            assert total == len(types)

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "strategy_type_code": st.text(min_size=1, max_size=20),
                }
            ),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_valid_types_returns_all_codes(self, types: list) -> None:
        """get_valid_strategy_types returns all codes from input."""
        with patch("precog.database.lookup_helpers.fetch_all") as mock:
            mock.return_value = types

            result = get_valid_strategy_types()

            assert len(result) == len(types)
            for t in types:
                assert t["strategy_type_code"] in result


class TestModelClassesProperties:
    """Property tests for model class functions."""

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "model_class_code": st.text(min_size=1, max_size=20),
                    "display_name": st.text(min_size=1, max_size=50),
                    "category": st.sampled_from(["statistical", "machine_learning", "hybrid"]),
                    "complexity_level": st.sampled_from(["simple", "moderate", "advanced"]),
                }
            ),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_by_category_preserves_all_classes(self, classes: list) -> None:
        """All input classes should appear in grouped output."""
        with patch("precog.database.lookup_helpers.fetch_all") as mock:
            mock.return_value = classes

            result = get_model_classes_by_category()

            total = sum(len(v) for v in result.values())
            assert total == len(classes)

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "model_class_code": st.text(min_size=1, max_size=20),
                    "display_name": st.text(min_size=1, max_size=50),
                    "category": st.sampled_from(["statistical", "machine_learning"]),
                    "complexity_level": st.sampled_from(["simple", "moderate", "advanced"]),
                }
            ),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_by_complexity_preserves_all_classes(self, classes: list) -> None:
        """All input classes should appear in complexity-grouped output."""
        with patch("precog.database.lookup_helpers.fetch_all") as mock:
            mock.return_value = classes

            result = get_model_classes_by_complexity()

            total = sum(len(v) for v in result.values())
            assert total == len(classes)

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "model_class_code": st.text(min_size=1, max_size=20),
                }
            ),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_valid_classes_returns_all_codes(self, classes: list) -> None:
        """get_valid_model_classes returns all codes from input."""
        with patch("precog.database.lookup_helpers.fetch_all") as mock:
            mock.return_value = classes

            result = get_valid_model_classes()

            assert len(result) == len(classes)
            for c in classes:
                assert c["model_class_code"] in result


class TestCategoryGroupingProperties:
    """Property tests for category grouping invariants."""

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "strategy_type_code": st.text(min_size=1, max_size=20),
                    "category": st.text(min_size=1, max_size=20),
                }
            ),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=20)
    def test_category_keys_match_input_categories(self, types: list) -> None:
        """Output categories should match unique input categories."""
        with patch("precog.database.lookup_helpers.fetch_all") as mock:
            mock.return_value = types

            result = get_strategy_types_by_category()

            input_categories = {t["category"] for t in types}
            assert set(result.keys()) == input_categories
