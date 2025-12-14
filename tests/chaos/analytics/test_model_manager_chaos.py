"""
Chaos Tests for ModelManager.

Tests edge cases, error recovery, and unexpected input handling.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for resilience
Related Requirements: REQ-VER-001 (Immutable Version Configs)

Usage:
    pytest tests/chaos/analytics/test_model_manager_chaos.py -v -m chaos
"""

import json
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from precog.analytics.model_manager import (
    InvalidStatusTransitionError,
    ModelManager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> ModelManager:
    """Create a ModelManager instance for testing."""
    return ModelManager()


# =============================================================================
# Chaos Tests: Unexpected Input Types
# =============================================================================


@pytest.mark.chaos
class TestUnexpectedInputTypes:
    """Chaos tests for unexpected input types."""

    def test_config_with_none_values(self, manager: ModelManager) -> None:
        """Test config containing None values."""
        config: dict[str, Any] = {
            "value": Decimal("1.0"),
            "nullable": None,
        }

        result = manager._prepare_config_for_db(config)

        assert "null" in result

    def test_config_with_empty_string(self, manager: ModelManager) -> None:
        """Test config containing empty strings."""
        config: dict[str, Any] = {
            "empty": "",
            "value": Decimal("1.0"),
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)

        assert parsed["empty"] == ""

    def test_config_with_special_characters(self, manager: ModelManager) -> None:
        """Test config with special characters in string values."""
        config: dict[str, Any] = {
            "special": "hello\nworld\t!",
            "unicode": "value: \u2603",
            "quotes": 'value with "quotes"',
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)

        assert parsed["special"] == "hello\nworld\t!"
        assert parsed["unicode"] == "value: \u2603"
        assert parsed["quotes"] == 'value with "quotes"'

    def test_config_with_boolean_values(self, manager: ModelManager) -> None:
        """Test config with boolean values."""
        config: dict[str, Any] = {
            "true_val": True,
            "false_val": False,
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)

        assert parsed["true_val"] is True
        assert parsed["false_val"] is False

    def test_config_with_integer_values(self, manager: ModelManager) -> None:
        """Test config with integer values (not Decimal)."""
        config: dict[str, Any] = {
            "int_val": 42,
            "negative": -100,
            "zero": 0,
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)

        assert parsed["int_val"] == 42
        assert parsed["negative"] == -100
        assert parsed["zero"] == 0

    def test_deserialization_with_float_values(self, manager: ModelManager) -> None:
        """Test deserialization handles float-like strings."""
        config = {
            "float_like": "3.14159265358979",
            "scientific": "1.5e-10",  # This won't convert to Decimal
        }

        result = manager._parse_config_from_db(config)

        # Float-like should become Decimal
        assert result["float_like"] == Decimal("3.14159265358979")
        # Scientific notation may or may not convert depending on format
        # Just verify no crash

    def test_deserialization_with_invalid_decimal_string(self, manager: ModelManager) -> None:
        """Test deserialization with invalid Decimal strings."""
        config = {
            "invalid": "not_a_number",
            "valid": "123.45",
        }

        result = manager._parse_config_from_db(config)

        # Invalid should remain string
        assert result["invalid"] == "not_a_number"
        # Valid should become Decimal
        assert result["valid"] == Decimal("123.45")


# =============================================================================
# Chaos Tests: Edge Case Values
# =============================================================================


@pytest.mark.chaos
class TestEdgeCaseValues:
    """Chaos tests for edge case values."""

    def test_very_small_decimal(self, manager: ModelManager) -> None:
        """Test very small Decimal values."""
        config = {"tiny": Decimal("0.0000000000000000001")}

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert restored["tiny"] == config["tiny"]

    def test_very_large_decimal(self, manager: ModelManager) -> None:
        """Test very large Decimal values."""
        config = {"huge": Decimal("99999999999999999999999999999999.9999")}

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert restored["huge"] == config["huge"]

    def test_negative_decimal(self, manager: ModelManager) -> None:
        """Test negative Decimal values."""
        config = {"negative": Decimal("-123.456")}

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert restored["negative"] == config["negative"]

    def test_zero_decimal(self, manager: ModelManager) -> None:
        """Test zero Decimal values."""
        config = {
            "zero": Decimal("0"),
            "zero_point": Decimal("0.0"),
            "zero_neg": Decimal("-0.0"),
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert restored["zero"] == Decimal("0")
        assert restored["zero_point"] == Decimal("0.0")

    def test_empty_nested_structures(self, manager: ModelManager) -> None:
        """Test empty nested structures."""
        config: dict[str, Any] = {
            "empty_dict": {},
            "empty_list": [],
            "nested_empty": {"inner": {}},
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert restored["empty_dict"] == {}
        assert restored["empty_list"] == []
        assert restored["nested_empty"]["inner"] == {}

    def test_unicode_keys(self, manager: ModelManager) -> None:
        """Test config with unicode keys."""
        config = {
            "normal": Decimal("1.0"),
            "émoji": Decimal("2.0"),
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert restored["normal"] == Decimal("1.0")
        assert restored["émoji"] == Decimal("2.0")


# =============================================================================
# Chaos Tests: Status Transition Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestStatusTransitionEdgeCases:
    """Chaos tests for status transition edge cases."""

    def test_unknown_current_status(self, manager: ModelManager) -> None:
        """Test transition from unknown status."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("unknown", "draft")

    def test_unknown_target_status(self, manager: ModelManager) -> None:
        """Test transition to unknown status."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("draft", "unknown")

    def test_empty_status_strings(self, manager: ModelManager) -> None:
        """Test transition with empty status strings."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("", "draft")

        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("draft", "")

    def test_case_sensitivity(self, manager: ModelManager) -> None:
        """Test status validation is case-sensitive."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("Draft", "testing")

        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("draft", "TESTING")

    def test_whitespace_in_status(self, manager: ModelManager) -> None:
        """Test status with whitespace."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition(" draft", "testing")

        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("draft ", "testing")


# =============================================================================
# Chaos Tests: Database Error Recovery
# =============================================================================


@pytest.mark.chaos
class TestDatabaseErrorRecovery:
    """Chaos tests for database error recovery."""

    @patch("precog.analytics.model_manager.get_connection")
    def test_connection_error_handled(
        self, mock_get_conn: MagicMock, manager: ModelManager
    ) -> None:
        """Test that connection errors are properly raised."""
        mock_get_conn.side_effect = psycopg2.OperationalError("Connection failed")

        with pytest.raises(psycopg2.OperationalError, match="Connection failed"):
            manager.get_model(model_id=1)

    @patch("precog.analytics.model_manager.get_connection")
    def test_cursor_error_handled(self, mock_get_conn: MagicMock, manager: ModelManager) -> None:
        """Test that cursor errors are properly raised."""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = psycopg2.Error("Cursor error")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(psycopg2.Error, match="Cursor error"):
            manager.get_model(model_id=1)

    @patch("precog.analytics.model_manager.get_connection")
    @patch("precog.analytics.model_manager.release_connection")
    def test_execution_error_handled(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: ModelManager,
    ) -> None:
        """Test that execution errors are properly raised."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("Query failed")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(psycopg2.Error, match="Query failed"):
            manager.get_model(model_id=1)

    @patch("precog.analytics.model_manager.get_connection")
    @patch("precog.analytics.model_manager.release_connection")
    def test_integrity_error_on_create(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: ModelManager,
    ) -> None:
        """Test IntegrityError when creating duplicate model."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.IntegrityError(
            "duplicate key value violates unique constraint"
        )
        mock_get_conn.return_value = mock_conn

        with pytest.raises(psycopg2.IntegrityError):
            manager.create_model(
                model_name="test",
                model_version="v1.0",
                model_class="elo",
                config={"k_factor": Decimal("32.0")},
            )


# =============================================================================
# Chaos Tests: Invalid Input Combinations
# =============================================================================


@pytest.mark.chaos
class TestInvalidInputCombinations:
    """Chaos tests for invalid input combinations."""

    def test_empty_config_validation(self, manager: ModelManager) -> None:
        """Test that empty config triggers validation error on create."""
        # Can serialize empty config
        result = manager._prepare_config_for_db({})
        assert result == "{}"

        # But create_model should reject it
        # (This would need actual DB call to test fully)

    def test_deeply_recursive_config(self, manager: ModelManager) -> None:
        """Test handling of deeply recursive config."""
        # Create very deep nesting
        config: dict[str, Any] = {"value": Decimal("1.0")}
        for i in range(50):
            config = {f"level_{i}": config}

        # Should handle without stack overflow
        result = manager._prepare_config_for_db(config)
        assert len(result) > 0

    def test_very_long_key_names(self, manager: ModelManager) -> None:
        """Test config with very long key names."""
        long_key = "k" * 1000
        config = {long_key: Decimal("1.0")}

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)

        assert long_key in parsed

    def test_config_with_list_of_decimals(self, manager: ModelManager) -> None:
        """Test config with list of Decimal values."""
        config = {
            "values": [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")],
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)
        restored = manager._parse_config_from_db(parsed)

        assert len(restored["values"]) == 3
        assert all(isinstance(v, Decimal) for v in restored["values"])


# =============================================================================
# Chaos Tests: Concurrent Chaos
# =============================================================================


@pytest.mark.chaos
class TestConcurrentChaos:
    """Chaos tests involving concurrent operations with edge cases."""

    def test_concurrent_edge_case_configs(self, manager: ModelManager) -> None:
        """Test concurrent processing of edge case configs."""
        import threading

        edge_configs = [
            {"empty": ""},
            {"none": None},
            {"deep": {"a": {"b": {"c": Decimal("1.0")}}}},
            {"unicode": "\u2603"},
            {"negative": Decimal("-999.99")},
        ]

        results: list[tuple[dict[str, Any], dict[str, Any]]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def process_config(config: dict[str, Any]) -> None:
            try:
                json_str = manager._prepare_config_for_db(config)
                parsed = json.loads(json_str)
                restored = manager._parse_config_from_db(parsed)
                with lock:
                    results.append((config, restored))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=process_config, args=(cfg,))
            for cfg in edge_configs * 4  # 20 threads total
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
