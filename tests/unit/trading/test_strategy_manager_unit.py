"""
Unit Tests for Strategy Manager.

Tests the StrategyManager class helper methods and validation logic
in isolation (no database interactions).

Reference: TESTING_STRATEGY V3.2 - Unit tests for isolated components
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003, REQ-VER-004

Usage:
    pytest tests/unit/trading/test_strategy_manager_unit.py -v -m unit
"""

import json
from decimal import Decimal
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


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Create a sample strategy config with Decimal values."""
    return {
        "min_edge": Decimal("0.0500"),
        "max_position_size": Decimal("100.00"),
        "kelly_fraction": Decimal("0.2500"),
        "min_probability": Decimal("0.3000"),
        "max_probability": Decimal("0.7000"),
    }


@pytest.fixture
def nested_config() -> dict[str, Any]:
    """Create a nested config structure for testing."""
    return {
        "entry_rules": {
            "min_edge": Decimal("0.05"),
            "max_spread": Decimal("0.10"),
        },
        "exit_rules": {
            "trailing_stop": Decimal("0.02"),
            "take_profit": Decimal("0.15"),
        },
        "filters": [Decimal("0.30"), Decimal("0.70")],
    }


# =============================================================================
# Unit Tests: Config Preparation
# =============================================================================


@pytest.mark.unit
class TestConfigPreparation:
    """Unit tests for config preparation (Decimal -> JSON conversion)."""

    def test_prepare_simple_config(self, manager: StrategyManager, sample_config: dict) -> None:
        """Test preparing simple config with Decimal values."""
        result = manager._prepare_config_for_db(sample_config)

        # Should return JSON string
        assert isinstance(result, str)

        # Parse and verify values converted to strings
        parsed = json.loads(result)
        assert parsed["min_edge"] == "0.0500"
        assert parsed["max_position_size"] == "100.00"
        assert parsed["kelly_fraction"] == "0.2500"

    def test_prepare_nested_config(self, manager: StrategyManager, nested_config: dict) -> None:
        """Test preparing nested config structures."""
        result = manager._prepare_config_for_db(nested_config)

        parsed = json.loads(result)
        assert parsed["entry_rules"]["min_edge"] == "0.05"
        assert parsed["exit_rules"]["trailing_stop"] == "0.02"
        # Lists preserved
        assert parsed["filters"] == ["0.30", "0.70"]

    def test_prepare_empty_config(self, manager: StrategyManager) -> None:
        """Test preparing empty config."""
        result = manager._prepare_config_for_db({})

        parsed = json.loads(result)
        assert parsed == {}

    def test_prepare_config_preserves_non_decimal_types(self, manager: StrategyManager) -> None:
        """Test that non-Decimal types are preserved."""
        config = {
            "name": "test_strategy",
            "enabled": True,
            "count": 42,
            "price": Decimal("10.50"),
        }

        result = manager._prepare_config_for_db(config)
        parsed = json.loads(result)

        assert parsed["name"] == "test_strategy"
        assert parsed["enabled"] is True
        assert parsed["count"] == 42
        assert parsed["price"] == "10.50"


# =============================================================================
# Unit Tests: Config Parsing
# =============================================================================


@pytest.mark.unit
class TestConfigParsing:
    """Unit tests for config parsing (JSON -> Decimal conversion)."""

    def test_parse_simple_config(self, manager: StrategyManager) -> None:
        """Test parsing simple config with numeric strings."""
        config = {
            "min_edge": "0.0500",
            "max_position_size": "100.00",
        }

        result = manager._parse_config_from_db(config)

        assert result["min_edge"] == Decimal("0.0500")
        assert result["max_position_size"] == Decimal("100.00")

    def test_parse_nested_config(self, manager: StrategyManager) -> None:
        """Test parsing nested config structures."""
        config = {
            "entry_rules": {
                "min_edge": "0.05",
            },
            "exit_rules": {
                "trailing_stop": "0.02",
            },
        }

        result = manager._parse_config_from_db(config)

        assert result["entry_rules"]["min_edge"] == Decimal("0.05")
        assert result["exit_rules"]["trailing_stop"] == Decimal("0.02")

    def test_parse_config_with_non_numeric_strings(self, manager: StrategyManager) -> None:
        """Test that non-numeric strings are preserved."""
        config = {
            "strategy_name": "halftime_entry",
            "min_edge": "0.05",
        }

        result = manager._parse_config_from_db(config)

        assert result["strategy_name"] == "halftime_entry"  # Not converted
        assert result["min_edge"] == Decimal("0.05")  # Converted

    def test_parse_empty_config(self, manager: StrategyManager) -> None:
        """Test parsing empty config."""
        result = manager._parse_config_from_db({})
        assert result == {}


# =============================================================================
# Unit Tests: Status Transition Validation
# =============================================================================


@pytest.mark.unit
class TestStatusTransitionValidation:
    """Unit tests for status transition validation logic."""

    def test_valid_draft_to_testing(self, manager: StrategyManager) -> None:
        """Test valid transition: draft -> testing."""
        # Should not raise
        manager._validate_status_transition("draft", "testing")

    def test_valid_testing_to_active(self, manager: StrategyManager) -> None:
        """Test valid transition: testing -> active."""
        manager._validate_status_transition("testing", "active")

    def test_valid_active_to_inactive(self, manager: StrategyManager) -> None:
        """Test valid transition: active -> inactive."""
        manager._validate_status_transition("active", "inactive")

    def test_valid_inactive_to_deprecated(self, manager: StrategyManager) -> None:
        """Test valid transition: inactive -> deprecated."""
        manager._validate_status_transition("inactive", "deprecated")

    def test_valid_testing_to_draft_revert(self, manager: StrategyManager) -> None:
        """Test valid revert: testing -> draft."""
        manager._validate_status_transition("testing", "draft")

    def test_valid_inactive_to_active_reactivate(self, manager: StrategyManager) -> None:
        """Test valid reactivation: inactive -> active."""
        manager._validate_status_transition("inactive", "active")

    def test_invalid_deprecated_to_active(self, manager: StrategyManager) -> None:
        """Test invalid transition: deprecated -> active (terminal state)."""
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            manager._validate_status_transition("deprecated", "active")

        assert "deprecated" in str(exc_info.value)
        assert "active" in str(exc_info.value)

    def test_invalid_active_to_testing(self, manager: StrategyManager) -> None:
        """Test invalid transition: active -> testing (backwards)."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("active", "testing")

    def test_invalid_active_to_draft(self, manager: StrategyManager) -> None:
        """Test invalid transition: active -> draft (backwards)."""
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("active", "draft")

    def test_deprecated_is_terminal(self, manager: StrategyManager) -> None:
        """Test that deprecated is terminal (no transitions out)."""
        invalid_targets = ["draft", "testing", "active", "inactive"]
        for target in invalid_targets:
            with pytest.raises(InvalidStatusTransitionError):
                manager._validate_status_transition("deprecated", target)

    def test_same_status_transitions(self, manager: StrategyManager) -> None:
        """Test transition to same status (draft -> draft allowed)."""
        # draft -> draft is allowed
        manager._validate_status_transition("draft", "draft")

        # Others are not
        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("active", "active")


# =============================================================================
# Unit Tests: Exception Classes
# =============================================================================


@pytest.mark.unit
class TestExceptionClasses:
    """Unit tests for custom exception classes."""

    def test_immutability_error_message(self) -> None:
        """Test ImmutabilityError has proper message."""
        error = ImmutabilityError("Cannot modify immutable config")
        assert str(error) == "Cannot modify immutable config"
        assert isinstance(error, Exception)

    def test_invalid_status_transition_error_message(self) -> None:
        """Test InvalidStatusTransitionError has proper message."""
        error = InvalidStatusTransitionError("Invalid: draft -> active")
        assert str(error) == "Invalid: draft -> active"
        assert isinstance(error, Exception)


# =============================================================================
# Unit Tests: Manager Initialization
# =============================================================================


@pytest.mark.unit
class TestManagerInitialization:
    """Unit tests for StrategyManager initialization."""

    def test_manager_creation(self) -> None:
        """Test StrategyManager can be instantiated."""
        manager = StrategyManager()
        assert manager is not None

    def test_manager_has_no_update_config(self) -> None:
        """Test StrategyManager does not have config update method."""
        manager = StrategyManager()

        # Immutability enforcement: no way to update config
        assert not hasattr(manager, "update_config")
        assert not hasattr(manager, "modify_config")
        assert not hasattr(manager, "set_config")

    def test_manager_has_required_methods(self) -> None:
        """Test StrategyManager has all required methods."""
        manager = StrategyManager()

        # CRUD methods
        assert hasattr(manager, "create_strategy")
        assert hasattr(manager, "get_strategy")
        assert hasattr(manager, "get_strategies_by_name")
        assert hasattr(manager, "get_active_strategies")
        assert hasattr(manager, "list_strategies")

        # Update methods (mutable fields only)
        assert hasattr(manager, "update_status")
        assert hasattr(manager, "update_metrics")


# =============================================================================
# Unit Tests: Row to Dict Conversion
# =============================================================================


@pytest.mark.unit
class TestRowToDict:
    """Unit tests for database row to dictionary conversion."""

    def test_row_to_dict_basic(self, manager: StrategyManager) -> None:
        """Test basic row to dict conversion."""
        # Create mock cursor with description
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("config",),
        ]

        row = (1, "test_strategy", "1.0", {"min_edge": "0.05"})

        result = manager._row_to_dict(mock_cursor, row)

        assert result["strategy_id"] == 1
        assert result["strategy_name"] == "test_strategy"
        assert result["strategy_version"] == "1.0"
        assert result["config"]["min_edge"] == Decimal("0.05")

    def test_row_to_dict_with_none_config(self, manager: StrategyManager) -> None:
        """Test row to dict with None config."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("strategy_id",), ("config",)]

        row = (1, None)

        result = manager._row_to_dict(mock_cursor, row)

        assert result["strategy_id"] == 1
        assert result["config"] is None


# =============================================================================
# Unit Tests: Input Validation
# =============================================================================


@pytest.mark.unit
class TestInputValidation:
    """Unit tests for input validation in create_strategy."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_strategy_empty_config_raises(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test that empty config raises ValueError."""
        with pytest.raises(ValueError, match="config cannot be empty"):
            manager.create_strategy(
                strategy_name="test",
                strategy_version="1.0",
                strategy_type="value",
                config={},  # Empty config
            )

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_strategy_none_config_raises(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test that None config raises ValueError."""
        with pytest.raises(ValueError, match="config cannot be empty"):
            manager.create_strategy(
                strategy_name="test",
                strategy_version="1.0",
                strategy_type="value",
                config=None,  # type: ignore
            )

    @patch("precog.trading.strategy_manager.get_connection")
    def test_update_metrics_no_metrics_raises(
        self, mock_conn: MagicMock, manager: StrategyManager
    ) -> None:
        """Test that update_metrics with no metrics raises ValueError."""
        with pytest.raises(ValueError, match="At least one metric must be provided"):
            manager.update_metrics(strategy_id=1)


# =============================================================================
# Unit Tests: Decimal Round-Trip
# =============================================================================


@pytest.mark.unit
class TestDecimalRoundTrip:
    """Unit tests for Decimal precision through JSON serialization."""

    def test_decimal_round_trip(self, manager: StrategyManager) -> None:
        """Test Decimal values survive prepare -> parse round trip."""
        original = {
            "price": Decimal("0.0500"),
            "high_precision": Decimal("0.12345678901234567890"),
        }

        # Prepare for DB
        json_str = manager._prepare_config_for_db(original)
        parsed_json = json.loads(json_str)

        # Parse from DB
        result = manager._parse_config_from_db(parsed_json)

        assert result["price"] == original["price"]
        assert result["high_precision"] == original["high_precision"]

    def test_nested_decimal_round_trip(self, manager: StrategyManager) -> None:
        """Test nested Decimal values survive round trip."""
        original = {
            "rules": {
                "entry": Decimal("0.05"),
                "exit": Decimal("0.02"),
            }
        }

        json_str = manager._prepare_config_for_db(original)
        parsed_json = json.loads(json_str)
        result = manager._parse_config_from_db(parsed_json)

        assert result["rules"]["entry"] == Decimal("0.05")
        assert result["rules"]["exit"] == Decimal("0.02")
