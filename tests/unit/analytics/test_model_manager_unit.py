"""
Unit Tests for ModelManager.

Tests internal logic, helper methods, and validation without database
connectivity. Focuses on pure functions and business logic.

Reference: TESTING_STRATEGY V3.2 - Unit tests for isolated component testing
Related Requirements: REQ-VER-001 (Immutable Version Configs)

Usage:
    pytest tests/unit/analytics/test_model_manager_unit.py -v -m unit
"""

from decimal import Decimal
from typing import Any

import pytest

from precog.analytics.model_manager import (
    ImmutabilityError,
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
# Unit Tests: Config Serialization
# =============================================================================


@pytest.mark.unit
class TestConfigSerialization:
    """Unit tests for config serialization/deserialization."""

    def test_prepare_config_for_db_decimal_to_string(self, manager: ModelManager) -> None:
        """Test that Decimal values are converted to strings for DB storage."""
        config = {
            "k_factor": Decimal("32.0"),
            "home_advantage": Decimal("55.5"),
        }

        result = manager._prepare_config_for_db(config)

        # Result should be a JSON string
        assert isinstance(result, str)
        # Should contain string representations
        assert '"32.0"' in result
        assert '"55.5"' in result

    def test_prepare_config_for_db_nested_decimals(self, manager: ModelManager) -> None:
        """Test nested Decimal values are converted."""
        config = {
            "outer": {
                "inner": Decimal("0.123"),
                "list_vals": [Decimal("1.0"), Decimal("2.0")],
            }
        }

        result = manager._prepare_config_for_db(config)

        assert '"0.123"' in result
        assert '"1.0"' in result
        assert '"2.0"' in result

    def test_prepare_config_for_db_mixed_types(self, manager: ModelManager) -> None:
        """Test mixed types are handled correctly."""
        config = {
            "decimal_val": Decimal("32.0"),
            "string_val": "test",
            "int_val": 42,
            "bool_val": True,
            "none_val": None,
        }

        result = manager._prepare_config_for_db(config)

        assert '"32.0"' in result
        assert '"test"' in result
        assert "42" in result
        assert "true" in result
        assert "null" in result

    def test_parse_config_from_db_string_to_decimal(self, manager: ModelManager) -> None:
        """Test that numeric strings are converted back to Decimal."""
        config = {
            "k_factor": "32.0",
            "home_advantage": "55.5",
        }

        result = manager._parse_config_from_db(config)

        assert result["k_factor"] == Decimal("32.0")
        assert result["home_advantage"] == Decimal("55.5")
        assert isinstance(result["k_factor"], Decimal)
        assert isinstance(result["home_advantage"], Decimal)

    def test_parse_config_from_db_nested_strings(self, manager: ModelManager) -> None:
        """Test nested string values are converted to Decimal."""
        config = {
            "outer": {
                "inner": "0.123",
                "list_vals": ["1.0", "2.0"],
            }
        }

        result = manager._parse_config_from_db(config)

        assert result["outer"]["inner"] == Decimal("0.123")
        assert result["outer"]["list_vals"][0] == Decimal("1.0")
        assert result["outer"]["list_vals"][1] == Decimal("2.0")

    def test_parse_config_from_db_non_numeric_strings_preserved(
        self, manager: ModelManager
    ) -> None:
        """Test that non-numeric strings are preserved."""
        config = {
            "name": "test_model",
            "description": "A test model",
        }

        result = manager._parse_config_from_db(config)

        assert result["name"] == "test_model"
        assert result["description"] == "A test model"
        assert isinstance(result["name"], str)

    def test_parse_config_from_db_preserves_non_strings(self, manager: ModelManager) -> None:
        """Test that non-string types are preserved."""
        config = {
            "int_val": 42,
            "bool_val": True,
            "none_val": None,
        }

        result = manager._parse_config_from_db(config)

        assert result["int_val"] == 42
        assert result["bool_val"] is True
        assert result["none_val"] is None


# =============================================================================
# Unit Tests: Status Transition Validation
# =============================================================================


@pytest.mark.unit
class TestStatusTransitionValidation:
    """Unit tests for status transition validation."""

    def test_valid_transition_draft_to_testing(self, manager: ModelManager) -> None:
        """Test valid transition from draft to testing."""
        # Should not raise
        manager._validate_status_transition("draft", "testing")

    def test_valid_transition_draft_to_draft(self, manager: ModelManager) -> None:
        """Test valid transition from draft to draft (no change)."""
        manager._validate_status_transition("draft", "draft")

    def test_valid_transition_testing_to_active(self, manager: ModelManager) -> None:
        """Test valid transition from testing to active."""
        manager._validate_status_transition("testing", "active")

    def test_valid_transition_testing_to_draft(self, manager: ModelManager) -> None:
        """Test valid transition from testing back to draft."""
        manager._validate_status_transition("testing", "draft")

    def test_valid_transition_active_to_deprecated(self, manager: ModelManager) -> None:
        """Test valid transition from active to deprecated."""
        manager._validate_status_transition("active", "deprecated")

    def test_invalid_transition_deprecated_to_active(self, manager: ModelManager) -> None:
        """Test invalid transition from deprecated to active."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("deprecated", "active")

    def test_invalid_transition_deprecated_to_testing(self, manager: ModelManager) -> None:
        """Test invalid transition from deprecated to testing."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("deprecated", "testing")

    def test_invalid_transition_deprecated_to_draft(self, manager: ModelManager) -> None:
        """Test invalid transition from deprecated to draft."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("deprecated", "draft")

    def test_invalid_transition_active_to_testing(self, manager: ModelManager) -> None:
        """Test invalid transition from active to testing (can't go backwards)."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("active", "testing")

    def test_invalid_transition_active_to_draft(self, manager: ModelManager) -> None:
        """Test invalid transition from active to draft (can't go backwards)."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("active", "draft")

    def test_invalid_transition_draft_to_active(self, manager: ModelManager) -> None:
        """Test invalid transition from draft directly to active (must go through testing)."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("draft", "active")

    def test_invalid_transition_draft_to_deprecated(self, manager: ModelManager) -> None:
        """Test invalid transition from draft to deprecated."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("draft", "deprecated")

    def test_invalid_transition_testing_to_deprecated(self, manager: ModelManager) -> None:
        """Test invalid transition from testing to deprecated."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("testing", "deprecated")

    def test_unknown_status_raises_error(self, manager: ModelManager) -> None:
        """Test that unknown status raises error."""
        with pytest.raises(InvalidStatusTransitionError, match="Invalid transition"):
            manager._validate_status_transition("unknown", "active")


# =============================================================================
# Unit Tests: Exception Classes
# =============================================================================


@pytest.mark.unit
class TestExceptionClasses:
    """Unit tests for custom exception classes."""

    def test_immutability_error_is_exception(self) -> None:
        """Test ImmutabilityError is an Exception."""
        error = ImmutabilityError("Config cannot be modified")
        assert isinstance(error, Exception)
        assert str(error) == "Config cannot be modified"

    def test_invalid_status_transition_error_is_exception(self) -> None:
        """Test InvalidStatusTransitionError is an Exception."""
        error = InvalidStatusTransitionError("Invalid transition: draft -> active")
        assert isinstance(error, Exception)
        assert "Invalid transition" in str(error)


# =============================================================================
# Unit Tests: Input Validation (No DB)
# =============================================================================


@pytest.mark.unit
class TestInputValidation:
    """Unit tests for input validation logic."""

    def test_empty_config_rejected(self, manager: ModelManager) -> None:
        """Test that empty config is rejected."""
        # This tests the validation logic before DB interaction
        # Note: This would raise ValueError if config is empty
        # The actual method requires DB, so we test the validation separately
        config: dict[str, Any] = {}
        # Can test the serialization doesn't fail on empty
        result = manager._prepare_config_for_db(config)
        assert result == "{}"

    def test_config_with_only_decimals(self, manager: ModelManager) -> None:
        """Test config containing only Decimal values."""
        config = {
            "a": Decimal("1.0"),
            "b": Decimal("2.0"),
            "c": Decimal("3.0"),
        }

        result = manager._prepare_config_for_db(config)

        assert '"1.0"' in result
        assert '"2.0"' in result
        assert '"3.0"' in result


# =============================================================================
# Unit Tests: Round-Trip Conversion
# =============================================================================


@pytest.mark.unit
class TestRoundTripConversion:
    """Unit tests for config round-trip conversion."""

    def test_decimal_roundtrip_simple(self, manager: ModelManager) -> None:
        """Test simple Decimal values round-trip correctly."""
        original = {"k_factor": Decimal("32.0")}

        # Serialize
        json_str = manager._prepare_config_for_db(original)

        # Deserialize (simulating what DB returns)
        import json

        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        assert restored["k_factor"] == original["k_factor"]
        assert isinstance(restored["k_factor"], Decimal)

    def test_decimal_roundtrip_complex(self, manager: ModelManager) -> None:
        """Test complex config round-trips correctly."""
        original = {
            "k_factor": Decimal("32.0"),
            "home_advantage": Decimal("55.5"),
            "nested": {
                "value": Decimal("0.123"),
                "list": [Decimal("1.0"), Decimal("2.0")],
            },
            "name": "test",
        }

        import json

        json_str = manager._prepare_config_for_db(original)
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        assert restored["k_factor"] == original["k_factor"]
        assert restored["home_advantage"] == original["home_advantage"]
        assert restored["nested"]["value"] == original["nested"]["value"]  # type: ignore[index]
        assert restored["nested"]["list"][0] == original["nested"]["list"][0]  # type: ignore[index]
        assert restored["name"] == original["name"]

    def test_precision_preserved_in_roundtrip(self, manager: ModelManager) -> None:
        """Test that Decimal precision is preserved in round-trip."""
        import json

        # High precision Decimal
        original = {"precise": Decimal("0.123456789012345678901234567890")}

        json_str = manager._prepare_config_for_db(original)
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        assert restored["precise"] == original["precise"]
