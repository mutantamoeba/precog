"""
Property-Based Tests for Strategy Manager.

Uses Hypothesis to test strategy manager invariants and config handling.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003

Usage:
    pytest tests/property/trading/test_strategy_manager_properties.py -v -m property
"""

import json
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.trading.strategy_manager import (
    InvalidStatusTransitionError,
    StrategyManager,
)

# =============================================================================
# Custom Strategies
# =============================================================================


# Decimal strategies for trading values
decimal_strategy = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("1000.0"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy name strategy
strategy_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"),
    min_size=3,
    max_size=50,
).filter(lambda x: x[0].isalpha() if x else False)

# Version strategy (semantic versioning)
version_strategy = st.from_regex(r"[1-9][0-9]*\.[0-9]+(\.[0-9]+)?", fullmatch=True)

# Status strategy
status_strategy = st.sampled_from(["draft", "testing", "active", "inactive", "deprecated"])

# Strategy type strategy
strategy_type_strategy = st.sampled_from(["value", "arbitrage", "momentum", "mean_reversion"])


# =============================================================================
# Helper Functions
# =============================================================================


def create_manager() -> StrategyManager:
    """Create a StrategyManager instance (avoids fixture issues with Hypothesis)."""
    return StrategyManager()


# =============================================================================
# Property Tests: Config Serialization
# =============================================================================


@pytest.mark.property
class TestConfigSerializationProperties:
    """Property tests for config serialization invariants."""

    @given(
        value=decimal_strategy,
    )
    @settings(max_examples=50)
    def test_decimal_round_trip_preserves_value(self, value: Decimal) -> None:
        """Decimal values should survive JSON round-trip exactly."""
        manager = create_manager()

        config = {"price": value}

        # Prepare for DB
        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)

        # Parse from DB
        result = manager._parse_config_from_db(parsed)

        # Should be exact match
        assert result["price"] == value

    @given(
        values=st.lists(decimal_strategy, min_size=1, max_size=5),
    )
    @settings(max_examples=30)
    def test_decimal_list_round_trip(self, values: list[Decimal]) -> None:
        """List of Decimals should survive round-trip."""
        manager = create_manager()

        config = {"values": values}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["values"] == values

    @given(
        key=st.text(min_size=1, max_size=20).filter(str.isalpha),
        value=decimal_strategy,
    )
    @settings(max_examples=30)
    def test_nested_decimal_round_trip(self, key: str, value: Decimal) -> None:
        """Nested Decimal values should survive round-trip."""
        manager = create_manager()

        config = {"nested": {key: value}}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["nested"][key] == value


# =============================================================================
# Property Tests: Status Transitions
# =============================================================================


@pytest.mark.property
class TestStatusTransitionProperties:
    """Property tests for status transition invariants."""

    @given(status=status_strategy)
    @settings(max_examples=50)
    def test_deprecated_is_always_terminal(self, status: str) -> None:
        """Deprecated status cannot transition to any other status."""
        manager = create_manager()

        if status == "deprecated":
            # Skip - deprecated -> deprecated would need special handling
            return

        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("deprecated", status)

    @given(
        from_status=st.sampled_from(["draft", "testing"]),
    )
    @settings(max_examples=20)
    def test_forward_progression_allowed(self, from_status: str) -> None:
        """Forward status progression should be allowed."""
        manager = create_manager()

        if from_status == "draft":
            # draft -> testing should work
            manager._validate_status_transition("draft", "testing")
        elif from_status == "testing":
            # testing -> active should work
            manager._validate_status_transition("testing", "active")

    @given(
        target=st.sampled_from(["testing", "draft"]),
    )
    @settings(max_examples=20)
    def test_active_cannot_go_backwards(self, target: str) -> None:
        """Active status cannot transition backwards to testing or draft."""
        manager = create_manager()

        with pytest.raises(InvalidStatusTransitionError):
            manager._validate_status_transition("active", target)


# =============================================================================
# Property Tests: Config Structure
# =============================================================================


@pytest.mark.property
class TestConfigStructureProperties:
    """Property tests for config structure invariants."""

    @given(
        config=st.fixed_dictionaries(
            {
                "min_edge": decimal_strategy,
                "max_position": decimal_strategy,
            }
        )
    )
    @settings(max_examples=30)
    def test_config_keys_preserved(self, config: dict[str, Decimal]) -> None:
        """Config keys should be preserved through serialization."""
        manager = create_manager()

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert set(result.keys()) == set(config.keys())

    @given(
        str_value=st.text(min_size=1, max_size=50).filter(
            lambda x: not x.replace(".", "").replace("-", "").isdigit()
        ),
    )
    @settings(max_examples=30)
    def test_non_numeric_strings_preserved(self, str_value: str) -> None:
        """Non-numeric string values should not be converted to Decimal."""
        manager = create_manager()

        config = {"name": str_value}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Non-numeric strings should remain as strings
        assert result["name"] == str_value
        assert isinstance(result["name"], str)


# =============================================================================
# Property Tests: Precision Preservation
# =============================================================================


@pytest.mark.property
class TestPrecisionPreservationProperties:
    """Property tests for decimal precision preservation."""

    @given(
        precision=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30)
    def test_high_precision_decimals_preserved(self, precision: int) -> None:
        """High precision Decimal values should be preserved exactly."""
        manager = create_manager()

        # Create Decimal with specified precision
        value = Decimal("0." + "1" * precision)
        config = {"high_precision": value}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["high_precision"] == value

    @given(
        whole=st.integers(min_value=0, max_value=10000),
        decimal_places=st.integers(min_value=0, max_value=8),
    )
    @settings(max_examples=50)
    def test_various_decimal_formats_preserved(self, whole: int, decimal_places: int) -> None:
        """Various Decimal formats should be preserved."""
        manager = create_manager()

        if decimal_places > 0:
            value = Decimal(f"{whole}." + "5" * decimal_places)
        else:
            value = Decimal(str(whole))

        config = {"value": value}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        assert result["value"] == value


# =============================================================================
# Property Tests: Edge Cases
# =============================================================================


@pytest.mark.property
class TestEdgeCaseProperties:
    """Property tests for edge cases in config handling."""

    @given(
        depth=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_deeply_nested_configs_handled(self, depth: int) -> None:
        """Deeply nested configs should be handled correctly."""
        manager = create_manager()

        # Build nested config
        config: dict[str, Any] = {"value": Decimal("0.05")}
        for _ in range(depth):
            config = {"nested": config}

        json_str = manager._prepare_config_for_db(config)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Navigate to innermost value
        current = result
        for _ in range(depth):
            current = current["nested"]

        assert current["value"] == Decimal("0.05")

    @given(
        mixed_values=st.fixed_dictionaries(
            {
                "decimal": decimal_strategy,
                "int": st.integers(min_value=0, max_value=1000),
                "bool": st.booleans(),
                "str": st.text(min_size=1, max_size=20),
            }
        )
    )
    @settings(max_examples=30)
    def test_mixed_type_configs_handled(self, mixed_values: dict[str, Any]) -> None:
        """Configs with mixed types should be handled correctly."""
        manager = create_manager()

        json_str = manager._prepare_config_for_db(mixed_values)
        parsed = json.loads(json_str)
        result = manager._parse_config_from_db(parsed)

        # Decimal converted
        assert isinstance(result["decimal"], Decimal)
        # Int preserved (but numeric strings become Decimal)
        # Bool preserved
        assert result["bool"] == mixed_values["bool"]
        # Non-numeric string preserved
        if not mixed_values["str"].replace(".", "").replace("-", "").isdigit():
            assert result["str"] == mixed_values["str"]


# =============================================================================
# Property Tests: Determinism
# =============================================================================


@pytest.mark.property
class TestDeterminismProperties:
    """Property tests for deterministic behavior."""

    @given(
        config=st.fixed_dictionaries(
            {
                "a": decimal_strategy,
                "b": decimal_strategy,
            }
        )
    )
    @settings(max_examples=30)
    def test_serialization_deterministic(self, config: dict[str, Decimal]) -> None:
        """Same config should always produce same JSON."""
        manager = create_manager()

        json_str1 = manager._prepare_config_for_db(config)
        json_str2 = manager._prepare_config_for_db(config)

        # JSON strings should be identical
        assert json_str1 == json_str2

    @given(
        from_status=status_strategy,
        to_status=status_strategy,
    )
    @settings(max_examples=50)
    def test_transition_validation_deterministic(self, from_status: str, to_status: str) -> None:
        """Status transition validation should be deterministic."""
        manager1 = create_manager()
        manager2 = create_manager()

        result1 = None
        result2 = None

        try:
            manager1._validate_status_transition(from_status, to_status)
            result1 = True
        except InvalidStatusTransitionError:
            result1 = False

        try:
            manager2._validate_status_transition(from_status, to_status)
            result2 = True
        except InvalidStatusTransitionError:
            result2 = False

        assert result1 == result2
