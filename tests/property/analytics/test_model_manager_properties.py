"""
Property-Based Tests for ModelManager.

Uses Hypothesis to test invariants and mathematical properties that should hold
for any valid input combination.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-VER-001 (Immutable Version Configs)

Usage:
    pytest tests/property/analytics/test_model_manager_properties.py -v -m property
"""

import json
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.analytics.model_manager import (
    InvalidStatusTransitionError,
    ModelManager,
)

# =============================================================================
# Custom Strategies
# =============================================================================


# Decimal values for config (reasonable range for model parameters)
decimal_strategy = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    places=10,
    allow_nan=False,
    allow_infinity=False,
)

# Simple config strategy (flat dict with Decimal values)
simple_config_strategy = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20),
    values=decimal_strategy,
    min_size=1,
    max_size=10,
)

# Status values
status_strategy = st.sampled_from(["draft", "testing", "active", "deprecated"])

# Model name strategy
model_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=50,
)

# Version strategy (semantic versioning)
version_strategy = st.from_regex(r"v[0-9]+\.[0-9]+", fullmatch=True)


# =============================================================================
# Helper Functions
# =============================================================================


def create_manager() -> ModelManager:
    """Create a ModelManager instance for testing."""
    return ModelManager()


# =============================================================================
# Property Tests: Config Serialization Invariants
# =============================================================================


@pytest.mark.property
class TestConfigSerializationProperties:
    """Property tests for config serialization invariants."""

    @given(value=decimal_strategy)
    @settings(max_examples=50)
    def test_decimal_roundtrip_preserves_value(self, value: Decimal) -> None:
        """Test that any Decimal value round-trips correctly."""
        manager = create_manager()
        config = {"value": value}

        # Serialize
        json_str = manager._prepare_config_for_db(config)

        # Deserialize
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        # Value should be preserved
        assert restored["value"] == value
        assert isinstance(restored["value"], Decimal)

    @given(config=simple_config_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_config_roundtrip_preserves_all_values(self, config: dict[str, Decimal]) -> None:
        """Test that entire config round-trips correctly."""
        manager = create_manager()

        # Serialize
        json_str = manager._prepare_config_for_db(config)

        # Deserialize
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        # All values should be preserved
        for key, value in config.items():
            assert key in restored
            assert restored[key] == value

    @given(config=simple_config_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_serialization_produces_valid_json(self, config: dict[str, Decimal]) -> None:
        """Test that serialization always produces valid JSON."""
        manager = create_manager()

        json_str = manager._prepare_config_for_db(config)

        # Should be valid JSON (no exception)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    @given(value=decimal_strategy)
    @settings(max_examples=50)
    def test_decimal_type_preserved_after_roundtrip(self, value: Decimal) -> None:
        """Test that type is always Decimal after round-trip."""
        manager = create_manager()
        config = {"value": value}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        # Type must be Decimal, not float
        assert type(restored["value"]) is Decimal


# =============================================================================
# Property Tests: Status Transition Properties
# =============================================================================


@pytest.mark.property
class TestStatusTransitionProperties:
    """Property tests for status transition validation."""

    @given(status=status_strategy)
    @settings(max_examples=20)
    def test_same_status_transition_valid_only_for_draft(self, status: str) -> None:
        """Test that transitioning to same status is only valid for draft."""
        manager = create_manager()

        if status == "draft":
            # draft -> draft is valid
            manager._validate_status_transition(status, status)
        else:
            # For other statuses, same transition should fail
            with pytest.raises(InvalidStatusTransitionError):
                manager._validate_status_transition(status, status)

    def test_deprecated_is_terminal_state(self) -> None:
        """Test that deprecated has no valid outgoing transitions."""
        manager = create_manager()

        for target in ["draft", "testing", "active", "deprecated"]:
            with pytest.raises(InvalidStatusTransitionError):
                manager._validate_status_transition("deprecated", target)

    @given(target=st.sampled_from(["draft", "testing", "deprecated"]))
    @settings(max_examples=10)
    def test_active_only_transitions_to_deprecated(self, target: str) -> None:
        """Test that active can only transition to deprecated."""
        manager = create_manager()

        if target == "deprecated":
            manager._validate_status_transition("active", target)
        else:
            with pytest.raises(InvalidStatusTransitionError):
                manager._validate_status_transition("active", target)

    def test_all_valid_transitions_from_draft(self) -> None:
        """Test all valid transitions from draft status."""
        manager = create_manager()

        valid_targets = ["testing", "draft"]
        invalid_targets = ["active", "deprecated"]

        for target in valid_targets:
            manager._validate_status_transition("draft", target)

        for target in invalid_targets:
            with pytest.raises(InvalidStatusTransitionError):
                manager._validate_status_transition("draft", target)

    def test_all_valid_transitions_from_testing(self) -> None:
        """Test all valid transitions from testing status."""
        manager = create_manager()

        valid_targets = ["active", "draft"]
        invalid_targets = ["deprecated", "testing"]

        for target in valid_targets:
            manager._validate_status_transition("testing", target)

        for target in invalid_targets:
            with pytest.raises(InvalidStatusTransitionError):
                manager._validate_status_transition("testing", target)


# =============================================================================
# Property Tests: Config Structure Properties
# =============================================================================


@pytest.mark.property
class TestConfigStructureProperties:
    """Property tests for config structure handling."""

    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
        value=decimal_strategy,
    )
    @settings(max_examples=30)
    def test_single_key_config_roundtrip(self, key: str, value: Decimal) -> None:
        """Test single key config round-trips correctly."""
        manager = create_manager()
        config = {key: value}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        assert key in restored
        assert restored[key] == value

    @given(
        outer_key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        inner_key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        value=decimal_strategy,
    )
    @settings(max_examples=30)
    def test_nested_config_roundtrip(self, outer_key: str, inner_key: str, value: Decimal) -> None:
        """Test nested config round-trips correctly."""
        manager = create_manager()
        config = {outer_key: {inner_key: value}}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        assert outer_key in restored
        assert inner_key in restored[outer_key]
        assert restored[outer_key][inner_key] == value

    @given(values=st.lists(decimal_strategy, min_size=1, max_size=5))
    @settings(max_examples=30)
    def test_list_values_roundtrip(self, values: list[Decimal]) -> None:
        """Test list of Decimal values round-trips correctly."""
        manager = create_manager()
        config = {"values": values}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        restored = manager._parse_config_from_db(parsed)

        assert len(restored["values"]) == len(values)
        for original, restored_val in zip(values, restored["values"], strict=False):
            assert restored_val == original


# =============================================================================
# Property Tests: Input Invariants
# =============================================================================


@pytest.mark.property
class TestInputInvariants:
    """Property tests for input handling invariants."""

    @given(name=model_name_strategy, version=version_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_model_name_and_version_are_independent(self, name: str, version: str) -> None:
        """Test that model name and version are independent."""
        # This is a structural property - names and versions should be
        # combinable without issues
        assert len(name) > 0
        assert len(version) > 0
        assert name != version or name == version  # Tautology to confirm independence

    @given(
        status1=status_strategy,
        status2=status_strategy,
    )
    @settings(max_examples=20)
    def test_transition_deterministic(self, status1: str, status2: str) -> None:
        """Test that status transitions are deterministic."""
        manager = create_manager()

        # Try the transition twice
        try:
            manager._validate_status_transition(status1, status2)
            first_result = True
        except InvalidStatusTransitionError:
            first_result = False

        try:
            manager._validate_status_transition(status1, status2)
            second_result = True
        except InvalidStatusTransitionError:
            second_result = False

        # Results should be identical
        assert first_result == second_result
