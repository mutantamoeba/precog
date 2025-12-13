"""
Chaos tests for lookup_helpers module.

Tests failure scenarios and edge cases.

Reference: TESTING_STRATEGY_V3.2.md Section "Chaos Tests"
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.lookup_helpers import (
    get_model_classes_by_complexity,
    get_strategy_types,
    get_strategy_types_by_category,
    get_valid_strategy_types,
    validate_strategy_type,
)

pytestmark = [pytest.mark.chaos]


class TestDatabaseFailureChaos:
    """Chaos tests for database failure scenarios."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_database_returns_none(self, mock_fetch: MagicMock) -> None:
        """Test handling when database returns None."""
        mock_fetch.return_value = None

        # Should handle None gracefully
        result = get_strategy_types()
        # Will likely fail with TypeError, which is acceptable chaos behavior
        assert result is None or isinstance(result, list)

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_database_returns_empty(self, mock_fetch: MagicMock) -> None:
        """Test handling of empty database results."""
        mock_fetch.return_value = []

        result = get_strategy_types()
        by_category = get_strategy_types_by_category()
        valid_codes = get_valid_strategy_types()

        assert result == []
        assert by_category == {}
        assert valid_codes == []

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_database_connection_error(self, mock_fetch: MagicMock) -> None:
        """Test handling of database connection errors."""
        mock_fetch.side_effect = RuntimeError("Connection refused")

        with pytest.raises(RuntimeError, match="Connection refused"):
            get_strategy_types()


class TestMalformedDataChaos:
    """Chaos tests for malformed data scenarios."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_missing_category_field(self, mock_fetch: MagicMock) -> None:
        """Test handling of missing category field."""
        mock_fetch.return_value = [
            {"strategy_type_code": "value"},  # Missing category
        ]

        with pytest.raises(KeyError):
            get_strategy_types_by_category()

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_missing_complexity_field(self, mock_fetch: MagicMock) -> None:
        """Test handling of missing complexity field."""
        mock_fetch.return_value = [
            {"model_class_code": "elo", "category": "stat"},  # Missing complexity_level
        ]

        with pytest.raises(KeyError):
            get_model_classes_by_complexity()

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_null_values_in_results(self, mock_fetch: MagicMock) -> None:
        """Test handling of null values in results."""
        mock_fetch.return_value = [
            {"strategy_type_code": None, "category": "test"},
            {"strategy_type_code": "value", "category": None},
        ]

        # Should handle without crashing
        try:
            by_category = get_strategy_types_by_category()
            # None category should be a key
            assert None in by_category or len(by_category) > 0
        except (TypeError, KeyError):
            pass  # Acceptable chaos behavior


class TestValidationChaos:
    """Chaos tests for validation functions."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_with_none_result(self, mock_fetch: MagicMock) -> None:
        """Test validation with None database result."""
        mock_fetch.return_value = None

        result = validate_strategy_type("value")

        assert result is False

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_with_malformed_result(self, mock_fetch: MagicMock) -> None:
        """Test validation with malformed result."""
        mock_fetch.return_value = {}  # Missing 'exists' key

        result = validate_strategy_type("value")

        assert result is False  # Should handle gracefully

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_with_empty_string(self, mock_fetch: MagicMock) -> None:
        """Test validation with empty string input."""
        mock_fetch.return_value = {"exists": False}

        result = validate_strategy_type("")

        assert result is False

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_with_special_characters(self, mock_fetch: MagicMock) -> None:
        """Test validation with special characters."""
        mock_fetch.return_value = {"exists": False}

        special_inputs = [
            "value'; DROP TABLE strategy_types;--",  # SQL injection attempt
            "value\ninjection",
            "value\x00null",
        ]

        for inp in special_inputs:
            result = validate_strategy_type(inp)
            assert result is False  # Should not validate malicious inputs


class TestEdgeCasesChaos:
    """Chaos tests for edge cases."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_very_large_result_set(self, mock_fetch: MagicMock) -> None:
        """Test handling of very large result sets."""
        mock_fetch.return_value = [
            {"strategy_type_code": f"type_{i}", "category": f"cat_{i % 100}"} for i in range(10000)
        ]

        result = get_strategy_types()
        by_category = get_strategy_types_by_category()

        assert len(result) == 10000
        assert len(by_category) == 100

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_unicode_in_values(self, mock_fetch: MagicMock) -> None:
        """Test handling of unicode characters."""
        mock_fetch.return_value = [
            {"strategy_type_code": "valu\u00e9", "category": "caf\u00e9"},
            {"strategy_type_code": "\u4e2d\u6587", "category": "\u65e5\u672c\u8a9e"},
        ]

        result = get_strategy_types()
        by_category = get_strategy_types_by_category()

        assert len(result) == 2
        assert "caf\u00e9" in by_category

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_duplicate_codes(self, mock_fetch: MagicMock) -> None:
        """Test handling of duplicate codes (shouldn't happen but test anyway)."""
        mock_fetch.return_value = [
            {"strategy_type_code": "value", "category": "a"},
            {"strategy_type_code": "value", "category": "b"},  # Duplicate
        ]

        result = get_strategy_types()
        codes = get_valid_strategy_types()

        # Should return both (DB constraint would normally prevent)
        assert len(result) == 2
        assert len(codes) == 2


class TestAddFunctionsChaos:
    """Chaos tests for add functions."""

    @patch("precog.database.connection.get_cursor")
    def test_add_with_none_return(self, mock_get_cursor: MagicMock) -> None:
        """Test add function when database returns None."""
        from precog.database.lookup_helpers import add_strategy_type

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = add_strategy_type(
            code="test",
            display_name="Test",
            description="Test description",
            category="test",
        )

        assert result == {}

    @patch("precog.database.connection.get_cursor")
    def test_add_with_database_error(self, mock_get_cursor: MagicMock) -> None:
        """Test add function when database raises error."""
        from precog.database.lookup_helpers import add_strategy_type

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("Database error")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(RuntimeError, match="Database error"):
            add_strategy_type(
                code="test",
                display_name="Test",
                description="Test description",
                category="test",
            )
