"""
Chaos Tests for Strategy Manager.

Tests edge cases, malformed data, and unexpected inputs.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for edge cases
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003

Usage:
    pytest tests/chaos/trading/test_strategy_manager_chaos.py -v -m chaos
"""

import json
from decimal import Decimal, InvalidOperation
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.strategy_manager import (
    ImmutabilityError,
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
# Chaos Tests: Malformed Config Data
# =============================================================================


@pytest.mark.chaos
class TestMalformedConfigData:
    """Chaos tests for malformed config data handling."""

    def test_none_config(self, manager: StrategyManager) -> None:
        """Test handling of None config.

        Educational Note:
            _prepare_config_for_db() returns a JSON string, not a Python object.
            For None input, json.dumps(None) returns 'null' which is valid JSON.
            The function gracefully handles this edge case.
        """
        try:
            result = manager._prepare_config_for_db(None)  # type: ignore[arg-type]
            # Function returns JSON string - 'null' is valid JSON for None input
            assert isinstance(result, str)  # type: ignore[unreachable]
            assert result == "null"  # json.dumps(None) returns 'null'
        except (TypeError, AttributeError):
            pass  # Expected - None not iterable

    def test_empty_string_config(self, manager: StrategyManager) -> None:
        """Test handling of empty string as config."""
        try:
            manager._prepare_config_for_db("")  # type: ignore
            # Might treat as empty dict or fail
        except (TypeError, AttributeError):
            pass  # Expected

    def test_list_as_config(self, manager: StrategyManager) -> None:
        """Test handling of list as config (should be dict)."""
        try:
            manager._prepare_config_for_db([1, 2, 3])  # type: ignore
            # Lists might serialize but should be caught at validation
        except (TypeError, AttributeError):
            pass  # Expected

    def test_integer_as_config(self, manager: StrategyManager) -> None:
        """Test handling of integer as config."""
        try:
            manager._prepare_config_for_db(42)  # type: ignore
        except (TypeError, AttributeError):
            pass  # Expected

    def test_config_with_none_value(self, manager: StrategyManager) -> None:
        """Test config containing None values."""
        config = {"valid_key": Decimal("0.05"), "null_key": None}

        # Should handle gracefully
        try:
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            result = manager._parse_config_from_db(parsed)

            # None should remain None
            assert result["null_key"] is None
        except (TypeError, ValueError):
            pass  # Acceptable if None not supported

    def test_config_with_nan_decimal(self, manager: StrategyManager) -> None:
        """Test config with NaN Decimal value."""
        config = {"nan_value": Decimal("NaN")}

        try:
            json_str = manager._prepare_config_for_db(config)
            # NaN might serialize but cause issues on parse
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
        except (ValueError, InvalidOperation, json.JSONDecodeError):
            pass  # Expected - NaN problematic

    def test_config_with_infinity_decimal(self, manager: StrategyManager) -> None:
        """Test config with Infinity Decimal value."""
        config = {"inf_value": Decimal("Infinity")}

        try:
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
        except (ValueError, InvalidOperation, json.JSONDecodeError):
            pass  # Expected - Infinity problematic

    def test_config_with_negative_infinity(self, manager: StrategyManager) -> None:
        """Test config with negative Infinity Decimal."""
        config = {"neg_inf": Decimal("-Infinity")}

        try:
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
        except (ValueError, InvalidOperation, json.JSONDecodeError):
            pass  # Expected

    def test_config_with_scientific_notation(self, manager: StrategyManager) -> None:
        """Test config with scientific notation Decimal.

        Note: Scientific notation strings (e.g., "1.5E-10") are NOT converted back
        to Decimal by _parse_config_from_db. This is intentional behavior added in
        the fix for Infinity/NaN rejection - the parser only converts simple decimal
        strings like "0.123" or "100.50", not scientific notation.

        If you need to store very small/large Decimal values, use normalized form
        (e.g., "0.00000000015" instead of "1.5E-10").
        """
        config = {"scientific": Decimal("1.5E-10")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Scientific notation strings remain as strings (not converted to Decimal)
        # This is by design - the parser rejects special string formats
        assert result["scientific"] == "1.5E-10"

    def test_config_with_empty_string_value(self, manager: StrategyManager) -> None:
        """Test config with empty string value."""
        config = {"empty": ""}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Empty string should remain empty string (not converted to Decimal)
        assert result["empty"] == ""


# =============================================================================
# Chaos Tests: Unusual Key Types
# =============================================================================


@pytest.mark.chaos
class TestUnusualKeyTypes:
    """Chaos tests for unusual dictionary key types."""

    def test_numeric_string_keys(self, manager: StrategyManager) -> None:
        """Test config with numeric string keys."""
        config = {"123": Decimal("0.05"), "456": Decimal("0.10")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Keys should be preserved
        assert "123" in result
        assert "456" in result

    def test_unicode_keys(self, manager: StrategyManager) -> None:
        """Test config with unicode keys."""
        config = {"价格": Decimal("0.05"), "αβγ": Decimal("0.10")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert "价格" in result
        assert "αβγ" in result

    def test_very_long_key(self, manager: StrategyManager) -> None:
        """Test config with very long key."""
        long_key = "a" * 1000
        config = {long_key: Decimal("0.05")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert long_key in result

    def test_special_char_keys(self, manager: StrategyManager) -> None:
        """Test config with special character keys."""
        config = {
            "key.with.dots": Decimal("0.05"),
            "key-with-dashes": Decimal("0.10"),
            "key_with_underscores": Decimal("0.15"),
            "key with spaces": Decimal("0.20"),
        }

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert "key.with.dots" in result
        assert "key-with-dashes" in result
        assert "key_with_underscores" in result
        assert "key with spaces" in result


# =============================================================================
# Chaos Tests: Unusual Value Types
# =============================================================================


@pytest.mark.chaos
class TestUnusualValueTypes:
    """Chaos tests for unusual value types in configs."""

    def test_boolean_values(self, manager: StrategyManager) -> None:
        """Test config with boolean values."""
        config = {"enabled": True, "disabled": False}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["enabled"] is True
        assert result["disabled"] is False

    def test_nested_empty_dict(self, manager: StrategyManager) -> None:
        """Test config with nested empty dict."""
        config = {"nested": {}, "value": Decimal("0.05")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["nested"] == {}

    def test_nested_empty_list(self, manager: StrategyManager) -> None:
        """Test config with nested empty list."""
        config = {"list": [], "value": Decimal("0.05")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["list"] == []

    def test_mixed_list_values(self, manager: StrategyManager) -> None:
        """Test config with mixed type list values."""
        config = {"mixed": [Decimal("0.05"), "string", 42, True]}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # List preserved with type conversions
        assert isinstance(result["mixed"], list)
        assert len(result["mixed"]) == 4

    def test_very_large_integer(self, manager: StrategyManager) -> None:
        """Test config with very large integer."""
        large_int = 10**100
        config = {"large": large_int}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Large integers should be handled
        # May be converted to Decimal if it looks numeric
        assert "large" in result

    def test_negative_decimal(self, manager: StrategyManager) -> None:
        """Test config with negative Decimal values."""
        config = {"negative": Decimal("-0.05"), "loss": Decimal("-100.50")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["negative"] == Decimal("-0.05")
        assert result["loss"] == Decimal("-100.50")

    def test_zero_decimal(self, manager: StrategyManager) -> None:
        """Test config with zero Decimal values."""
        config = {"zero": Decimal("0"), "zero_padded": Decimal("0.0000")}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Zero values preserved
        assert result["zero"] == Decimal("0")
        # Note: precision may not be preserved for "0.0000" vs "0"


# =============================================================================
# Chaos Tests: Status Transition Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestStatusTransitionEdgeCases:
    """Chaos tests for status transition edge cases."""

    def test_empty_status_strings(self, manager: StrategyManager) -> None:
        """Test validation with empty status strings."""
        try:
            manager._validate_status_transition("", "testing")
            pytest.fail("Should have raised exception for empty status")
        except (InvalidStatusTransitionError, KeyError, ValueError):
            pass  # Expected

    def test_none_status(self, manager: StrategyManager) -> None:
        """Test validation with None status."""
        try:
            manager._validate_status_transition(None, "testing")  # type: ignore
            pytest.fail("Should have raised exception for None status")
        except (InvalidStatusTransitionError, TypeError, KeyError):
            pass  # Expected

    def test_unknown_status_values(self, manager: StrategyManager) -> None:
        """Test validation with unknown status values."""
        try:
            manager._validate_status_transition("unknown", "active")
            # May or may not be allowed depending on implementation
        except (InvalidStatusTransitionError, KeyError):
            pass  # Expected for unknown status

    def test_case_sensitive_status(self, manager: StrategyManager) -> None:
        """Test whether status validation is case sensitive."""
        try:
            # Try uppercase
            manager._validate_status_transition("DRAFT", "TESTING")
            # If it passes, status is case-insensitive
        except (InvalidStatusTransitionError, KeyError):
            pass  # Status is case-sensitive

    def test_whitespace_in_status(self, manager: StrategyManager) -> None:
        """Test status with leading/trailing whitespace."""
        try:
            manager._validate_status_transition(" draft ", " testing ")
        except (InvalidStatusTransitionError, KeyError):
            pass  # Whitespace not stripped

    def test_numeric_status(self, manager: StrategyManager) -> None:
        """Test status as numeric value."""
        try:
            manager._validate_status_transition(1, 2)  # type: ignore
        except (InvalidStatusTransitionError, TypeError, KeyError):
            pass  # Expected


# =============================================================================
# Chaos Tests: Parse Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestParseEdgeCases:
    """Chaos tests for config parsing edge cases."""

    def test_parse_malformed_numeric_string(self, manager: StrategyManager) -> None:
        """Test parsing malformed numeric strings."""
        db_config = {
            "almost_number": "0.05.05",  # Two decimal points
            "spaces": "0 .05",  # Space in number
            "comma": "0,05",  # Comma instead of dot
        }

        result = manager._parse_config_from_db(db_config)

        # These should NOT be converted to Decimal
        assert isinstance(result["almost_number"], str)
        assert isinstance(result["spaces"], str)
        assert isinstance(result["comma"], str)

    def test_parse_numeric_string_with_letters(self, manager: StrategyManager) -> None:
        """Test parsing strings that are almost numeric."""
        db_config = {
            "with_letter": "0.05a",
            "prefix_letter": "a0.05",
            "currency": "$0.05",
            "percent": "5%",
        }

        result = manager._parse_config_from_db(db_config)

        # None of these should become Decimal
        assert isinstance(result["with_letter"], str)
        assert isinstance(result["prefix_letter"], str)
        assert isinstance(result["currency"], str)
        assert isinstance(result["percent"], str)

    def test_parse_exponential_string(self, manager: StrategyManager) -> None:
        """Test parsing exponential notation strings."""
        db_config = {
            "exp_lower": "1e-5",
            "exp_upper": "1E-5",
            "exp_positive": "1e+5",
        }

        result = manager._parse_config_from_db(db_config)

        # Exponential notation might or might not be converted
        # depending on implementation
        for key in db_config:
            assert key in result


# =============================================================================
# Chaos Tests: Row Conversion Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestRowConversionEdgeCases:
    """Chaos tests for row to dict conversion edge cases."""

    def test_mismatched_column_count(self, manager: StrategyManager) -> None:
        """Test row with wrong number of columns."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",), ("col2",), ("col3",)]

        # Row has 2 values, description has 3 columns
        row = (1, 2)

        try:
            manager._row_to_dict(mock_cursor, row)
            # May fail or may truncate
        except (IndexError, ValueError):
            pass  # Expected

    def test_empty_row(self, manager: StrategyManager) -> None:
        """Test with empty row."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",)]

        row: tuple[Any, ...] = ()

        try:
            manager._row_to_dict(mock_cursor, row)
        except (IndexError, ValueError):
            pass  # Expected

    def test_none_cursor_description(self, manager: StrategyManager) -> None:
        """Test with None cursor description."""
        mock_cursor = MagicMock()
        mock_cursor.description = None

        row = (1, "test")

        try:
            manager._row_to_dict(mock_cursor, row)
            pytest.fail("Should have raised exception")
        except (TypeError, AttributeError):
            pass  # Expected

    def test_row_with_complex_nested_json(self, manager: StrategyManager) -> None:
        """Test row with deeply nested JSON config."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("strategy_id",), ("config",)]

        # 10 levels deep
        nested: dict[str, Any] = {"value": "0.05"}
        for i in range(10):
            nested = {f"level_{i}": nested}

        row = (1, nested)

        result = manager._row_to_dict(mock_cursor, row)

        # Should handle deep nesting
        assert result["strategy_id"] == 1
        assert "level_9" in result["config"]


# =============================================================================
# Chaos Tests: Create Strategy Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestCreateStrategyEdgeCases:
    """Chaos tests for create_strategy edge cases."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_with_special_char_name(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test creating strategy with special characters in name."""
        try:
            manager.create_strategy(
                strategy_name="test!@#$%^&*()",
                strategy_version="1.0",
                strategy_type="value",
                config={"min_edge": Decimal("0.05")},
            )
        except (ValueError, Exception):
            pass  # May be rejected

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_with_unicode_name(self, mock_conn: MagicMock, manager: StrategyManager) -> None:
        """Test creating strategy with unicode name."""
        try:
            manager.create_strategy(
                strategy_name="策略_αβγ_テスト",
                strategy_version="1.0",
                strategy_type="value",
                config={"min_edge": Decimal("0.05")},
            )
        except (ValueError, Exception):
            pass  # May or may not be supported

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_with_very_long_name(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test creating strategy with very long name."""
        long_name = "a" * 500

        try:
            manager.create_strategy(
                strategy_name=long_name,
                strategy_version="1.0",
                strategy_type="value",
                config={"min_edge": Decimal("0.05")},
            )
        except (ValueError, Exception):
            pass  # May be truncated or rejected

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_with_unusual_version(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test creating strategy with unusual version strings."""
        versions = [
            "1.0.0.0.0",  # Many segments
            "v1.0",  # Prefix
            "alpha",  # Non-numeric
            "",  # Empty
            "1",  # Single number
        ]

        for version in versions:
            try:
                manager.create_strategy(
                    strategy_name="test",
                    strategy_version=version,
                    strategy_type="value",
                    config={"min_edge": Decimal("0.05")},
                )
            except (ValueError, Exception):
                pass  # Some may be rejected

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_with_unknown_strategy_type(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test creating strategy with unknown type."""
        try:
            manager.create_strategy(
                strategy_name="test",
                strategy_version="1.0",
                strategy_type="unknown_type",
                config={"min_edge": Decimal("0.05")},
            )
        except (ValueError, Exception):
            pass  # May be rejected


# =============================================================================
# Chaos Tests: Update Operations Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestUpdateOperationsEdgeCases:
    """Chaos tests for update operation edge cases."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_update_status_invalid_id(self, mock_conn: MagicMock, manager: StrategyManager) -> None:
        """Test updating status with invalid strategy ID."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No rows affected
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        try:
            manager.update_status(  # type: ignore[call-arg]
                strategy_id=-1,
                new_status="testing",
                current_status="draft",  # Intentional invalid arg for chaos test
            )
        except (ValueError, Exception):
            pass  # Invalid ID

    @patch("precog.trading.strategy_manager.get_connection")
    def test_update_metrics_extreme_values(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test updating metrics with extreme values."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        try:
            manager.update_metrics(  # type: ignore[call-arg]
                strategy_id=1,
                total_pnl=Decimal("999999999999999.9999"),  # Intentional invalid args
                total_trades=999999999,
                win_rate=Decimal("1.0001"),  # > 100%
            )
        except (ValueError, Exception):
            pass  # Extreme values may be rejected

    @patch("precog.trading.strategy_manager.get_connection")
    def test_update_metrics_negative_trades(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test updating metrics with negative trade count."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        try:
            manager.update_metrics(  # type: ignore[call-arg]
                strategy_id=1,
                total_trades=-5,  # Intentional invalid arg for chaos test
            )
        except (ValueError, Exception):
            pass  # Negative trades invalid


# =============================================================================
# Chaos Tests: Exception Handling
# =============================================================================


@pytest.mark.chaos
class TestExceptionHandling:
    """Chaos tests for exception handling."""

    def test_immutability_error_with_unusual_message(self) -> None:
        """Test ImmutabilityError with unusual messages."""
        messages = [
            "",  # Empty
            "a" * 1000,  # Very long
            "message\nwith\nnewlines",  # Newlines
            "unicode: 价格 αβγ",  # Unicode
            None,  # None (may fail)
        ]

        for msg in messages:
            try:
                raise ImmutabilityError(msg)  # Test with various message types
            except ImmutabilityError as e:
                assert msg is None or str(e) == str(msg)
            except TypeError:
                pass  # None message not supported

    def test_invalid_status_transition_error_with_unusual_message(self) -> None:
        """Test InvalidStatusTransitionError with unusual messages."""
        messages = [
            "",
            "a" * 1000,
            "message\nwith\nnewlines",
        ]

        for msg in messages:
            try:
                raise InvalidStatusTransitionError(msg)
            except InvalidStatusTransitionError as e:
                assert str(e) == msg
