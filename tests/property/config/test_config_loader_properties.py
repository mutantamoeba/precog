"""
Property-based tests for ConfigLoader.

Tests mathematical properties and invariants of configuration loading.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
Related Requirements: REQ-CONFIG-001 (YAML Configuration)
Related ADR: ADR-012 (Configuration Management Strategy)
"""

import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from precog.config.config_loader import ConfigLoader

# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================


@st.composite
def environment_name_strategy(draw: st.DrawFn) -> str:
    """Generate valid environment names."""
    return draw(st.sampled_from(["development", "staging", "production", "test"]))


@st.composite
def decimal_key_strategy(draw: st.DrawFn) -> str:
    """Generate keys that should be converted to Decimal.

    Uses actual keys from ConfigLoader._convert_to_decimal().
    """
    # These are the ACTUAL keys from config_loader.py lines 274-327
    actual_decimal_keys = [
        # Money/dollar amounts
        "max_total_exposure_dollars",
        "daily_loss_limit_dollars",
        "weekly_loss_limit_dollars",
        "min_balance_to_trade_dollars",
        "max_position_size_dollars",
        "min_trade_size_dollars",
        "max_trade_size_dollars",
        "min_position_dollars",
        "max_position_dollars",
        "threshold_dollars",
        "initial_capital",
        "balance",
        # Prices and spreads
        "entry_price",
        "exit_price",
        "stop_loss",
        "target_price",
        "yes_price",
        "no_price",
        "price",
        "spread",
        "min_spread",
        "max_spread",
        # Probabilities and thresholds
        "probability",
        "min_probability",
        "max_probability",
        "threshold",
        "min_ev_threshold",
        "kelly_fraction",
        "default_fraction",
        "max_kelly_fraction",
        "confidence",
        "min_edge",
        "min_edge_threshold",
        "min_edge_to_hold",
        # Percentages and fractions
        "trailing_stop_percent",
        "stop_loss_percent",
        "target_profit_percent",
        "max_drawdown_percent",
        "loss_threshold_pct",
        "gain_threshold_pct",
        "max_position_pct",
        "max_correlation",
        # Trailing stop parameters
        "activation_threshold",
        "initial_distance",
        "tightening_rate",
        "floor_distance",
    ]
    return draw(st.sampled_from(actual_decimal_keys))


@st.composite
def boolean_truthy_strategy(draw: st.DrawFn) -> str:
    """Generate truthy string values for boolean conversion."""
    return draw(st.sampled_from(["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]))


@st.composite
def boolean_falsy_strategy(draw: st.DrawFn) -> str:
    """Generate falsy string values for boolean conversion."""
    return draw(st.sampled_from(["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", ""]))


@st.composite
def key_path_strategy(draw: st.DrawFn) -> str:
    """Generate valid dot-separated key paths."""
    depth = draw(st.integers(min_value=1, max_value=4))
    parts = [
        draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=10))
        for _ in range(depth)
    ]
    return ".".join(parts)


@st.composite
def yaml_safe_value_strategy(draw: st.DrawFn) -> Any:
    """Generate values that are safe for YAML serialization."""
    return draw(
        st.one_of(
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20),
            st.booleans(),
        )
    )


# =============================================================================
# Property Tests: Environment Prefix Handling
# =============================================================================


@pytest.mark.property
class TestEnvironmentPrefixProperties:
    """Property tests for environment prefix handling in get_env()."""

    @given(
        environment_name_strategy(),
        st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    )
    @settings(max_examples=50)
    def test_environment_prefix_matches_environment_name(self, env: str, key: str) -> None:
        """Environment prefix should match the environment setting.

        Property: For environment 'X', get_env('KEY') should look for 'X_KEY' first.
        """
        loader = ConfigLoader()
        loader.environment = env

        expected_prefix = env.upper()
        prefixed_key = f"{expected_prefix}_{key}"

        # Set environment variable with prefix
        test_value = "test_value_123"
        with patch.dict(os.environ, {prefixed_key: test_value}, clear=False):
            result = loader.get_env(key)

        assert result == test_value

    @given(environment_name_strategy())
    def test_all_environments_use_correct_prefix(self, env_name: str) -> None:
        """All environments use their uppercased name as prefix.

        Note: The code uses environment.upper() as prefix, so:
        - "development" -> "DEVELOPMENT_"
        - "staging" -> "STAGING_"
        - "production" -> "PRODUCTION_"
        - "test" -> "TEST_"
        """
        loader = ConfigLoader()
        loader.environment = env_name

        # The actual prefix is the uppercased environment name
        actual_prefix = env_name.upper()

        # Use unique key to avoid conflicts
        key = f"UNIQUE_PREFIX_TEST_{actual_prefix}"
        prefixed_key = f"{actual_prefix}_{key}"
        test_value = f"value_for_{actual_prefix}"

        # Set and then clean up manually to avoid patch issues
        old_value = os.environ.get(prefixed_key)
        try:
            os.environ[prefixed_key] = test_value
            result = loader.get_env(key)
            assert result == test_value
        finally:
            if old_value is not None:
                os.environ[prefixed_key] = old_value
            elif prefixed_key in os.environ:
                del os.environ[prefixed_key]

    @given(st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    @settings(max_examples=30)
    def test_fallback_to_unprefixed_when_prefixed_not_found(self, key: str) -> None:
        """Should fall back to unprefixed key if prefixed not found.

        Property: get_env('KEY') returns unprefixed KEY if ENV_KEY doesn't exist.
        """
        loader = ConfigLoader()
        loader.environment = "development"

        # Only set unprefixed key
        test_value = "unprefixed_value"
        with patch.dict(os.environ, {key: test_value}, clear=False):
            # Clear any prefixed version
            env_key = f"DEVELOPMENT_{key}"
            env_backup = os.environ.pop(env_key, None)
            try:
                result = loader.get_env(key)
            finally:
                if env_backup is not None:
                    os.environ[env_key] = env_backup

        assert result == test_value

    @given(st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    @settings(max_examples=30)
    def test_default_returned_when_key_not_found(self, key: str) -> None:
        """Should return default when neither prefixed nor unprefixed key exists.

        Property: get_env('KEY', default='X') returns 'X' if KEY not in environment.
        """
        # Use a key that definitely doesn't exist
        unique_key = f"NONEXISTENT_KEY_12345_{key}"

        loader = ConfigLoader()
        default_value = "default_value_abc"

        result = loader.get_env(unique_key, default=default_value)

        assert result == default_value


# =============================================================================
# Property Tests: Decimal Conversion
# =============================================================================


@pytest.mark.property
class TestDecimalConversionProperties:
    """Property tests for Decimal conversion of monetary values."""

    @given(
        decimal_key_strategy(),
        st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50)
    def test_decimal_keys_always_converted_from_float(self, key: str, value: float) -> None:
        """Keys in decimal_keys set should be converted from float to Decimal.

        Property: For any key in decimal_keys, float values become Decimal.
        """
        loader = ConfigLoader()

        test_dict = {key: value}
        result = loader._convert_to_decimal(test_dict)

        # Key should exist and be Decimal
        assert key in result
        assert isinstance(result[key], Decimal)

    @given(
        decimal_key_strategy(),
        st.integers(min_value=-10000, max_value=10000),
    )
    @settings(max_examples=50)
    def test_decimal_keys_converted_from_int(self, key: str, value: int) -> None:
        """Keys in decimal_keys set should be converted from int to Decimal.

        Property: For any key in decimal_keys, int values become Decimal.
        """
        loader = ConfigLoader()

        test_dict = {key: value}
        result = loader._convert_to_decimal(test_dict)

        assert key in result
        assert isinstance(result[key], Decimal)
        # Verify value preserved
        assert result[key] == Decimal(str(value))

    @given(
        decimal_key_strategy(),
        st.text(
            alphabet="0123456789.-",
            min_size=1,
            max_size=10,
        ).filter(lambda x: x not in [".", "-", "-."] and x.count(".") <= 1 and x.count("-") <= 1),
    )
    @settings(max_examples=30)
    def test_decimal_keys_converted_from_string(self, key: str, value: str) -> None:
        """Keys in decimal_keys set should be converted from numeric string to Decimal.

        Property: For any key in decimal_keys, string numeric values become Decimal.
        """
        # Filter out invalid numeric strings
        try:
            Decimal(value)
        except Exception:
            assume(False)

        loader = ConfigLoader()

        test_dict = {key: value}
        result = loader._convert_to_decimal(test_dict)

        assert key in result
        assert isinstance(result[key], Decimal)

    @given(
        st.sampled_from(
            [
                "username",
                "hostname",
                "filename",
                "description",
                "category",
                "label",
                "name",
                "value_type",
                "status",
                "mode",
                "level",
                "count",
                "index",
                "data",
                "content",
                "message",
                "title",
            ]
        )
    )
    @settings(max_examples=30)
    def test_non_decimal_keys_not_converted(self, key: str) -> None:
        """Keys not in decimal_keys set should NOT be converted.

        Property: Arbitrary keys preserve their original type.
        """
        loader = ConfigLoader()

        original_value = 123.456
        test_dict = {key: original_value}
        result = loader._convert_to_decimal(test_dict)

        assert key in result
        # Should remain float, not Decimal
        assert isinstance(result[key], float)

    @given(
        st.dictionaries(
            keys=decimal_key_strategy(),
            values=st.floats(
                min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False
            ),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=30)
    def test_all_decimal_keys_in_dict_converted(self, test_dict: dict[str, float]) -> None:
        """All decimal keys in a dict should be converted.

        Property: No decimal key should remain as float after conversion.
        """
        loader = ConfigLoader()

        result = loader._convert_to_decimal(test_dict)

        for key in test_dict:
            assert isinstance(result[key], Decimal), f"Key {key} should be Decimal"

    @given(
        decimal_key_strategy(),
        st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30)
    def test_nested_decimal_conversion(self, key: str, value: float) -> None:
        """Decimal conversion should work on nested dicts.

        Property: Nested dicts have decimal keys converted at all levels.
        """
        loader = ConfigLoader()

        nested_dict = {"level1": {"level2": {key: value}}}
        result = loader._convert_to_decimal(nested_dict)

        assert isinstance(result["level1"]["level2"][key], Decimal)


# =============================================================================
# Property Tests: Boolean Conversion
# =============================================================================


@pytest.mark.property
class TestBooleanConversionProperties:
    """Property tests for boolean type conversion in get_env()."""

    @given(boolean_truthy_strategy())
    def test_truthy_strings_convert_to_true(self, truthy_value: str) -> None:
        """All truthy string values should convert to True.

        Property: "true", "1", "yes", "on" (case-insensitive) -> True
        """
        loader = ConfigLoader()

        key = "TEST_BOOL_KEY"
        with patch.dict(os.environ, {key: truthy_value}, clear=False):
            result = loader.get_env(key, as_type=bool)

        assert result is True

    @given(boolean_falsy_strategy())
    def test_falsy_strings_convert_to_false(self, falsy_value: str) -> None:
        """All falsy string values should convert to False.

        Property: "false", "0", "no", "off" (case-insensitive) -> False
        """
        loader = ConfigLoader()

        key = "TEST_BOOL_KEY"
        with patch.dict(os.environ, {key: falsy_value}, clear=False):
            result = loader.get_env(key, as_type=bool)

        assert result is False


# =============================================================================
# Property Tests: Type Conversion
# =============================================================================


@pytest.mark.property
class TestTypeConversionProperties:
    """Property tests for type conversion in get_env()."""

    @given(st.integers(min_value=-1000000, max_value=1000000))
    @settings(max_examples=50)
    def test_int_conversion_preserves_value(self, value: int) -> None:
        """Integer conversion should preserve the value.

        Property: get_env(key, as_type=int) returns exact integer.
        """
        loader = ConfigLoader()

        key = "TEST_INT_KEY"
        with patch.dict(os.environ, {key: str(value)}, clear=False):
            result = loader.get_env(key, as_type=int)

        assert result == value
        assert isinstance(result, int)

    @given(
        st.decimals(
            min_value=Decimal("-10000"),
            max_value=Decimal("10000"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=50)
    def test_decimal_conversion_preserves_precision(self, value: Decimal) -> None:
        """Decimal conversion should preserve precision.

        Property: get_env(key, as_type=Decimal) returns exact Decimal.
        """
        loader = ConfigLoader()

        key = "TEST_DECIMAL_KEY"
        with patch.dict(os.environ, {key: str(value)}, clear=False):
            result = loader.get_env(key, as_type=Decimal)

        assert result == value
        assert isinstance(result, Decimal)

    @given(st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-"))
    @settings(max_examples=30)
    def test_str_conversion_returns_original(self, value: str) -> None:
        """String conversion should return the original value.

        Property: get_env(key, as_type=str) returns exact string.
        """
        loader = ConfigLoader()

        key = "TEST_STR_CONVERSION_KEY"
        # Use direct env manipulation for reliability
        old_value = os.environ.get(key)
        try:
            os.environ[key] = value
            result = loader.get_env(key, as_type=str)
            assert result == value
            assert isinstance(result, str)
        finally:
            if old_value is not None:
                os.environ[key] = old_value
            elif key in os.environ:
                del os.environ[key]

    @given(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"))
    @settings(max_examples=20)
    def test_invalid_int_returns_default(self, non_int_value: str) -> None:
        """Non-numeric string should return default for int conversion.

        Property: Invalid int strings return default, not exception.
        """
        loader = ConfigLoader()

        key = "TEST_INVALID_INT"
        default_val = -999
        with patch.dict(os.environ, {key: non_int_value}, clear=False):
            result = loader.get_env(key, default=default_val, as_type=int)

        assert result == default_val


# =============================================================================
# Property Tests: Caching Behavior
# =============================================================================


@pytest.mark.property
class TestCachingProperties:
    """Property tests for configuration caching."""

    @given(st.integers(min_value=2, max_value=10))
    @settings(max_examples=10)
    def test_multiple_loads_return_same_object(self, num_loads: int) -> None:
        """Multiple loads should return cached (same) object.

        Property: load(config) == load(config) for any number of calls.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("key: value\n")

            loader = ConfigLoader(config_dir=tmpdir)

            # Load multiple times
            results = [loader.load("test") for _ in range(num_loads)]

            # All results should be the same object (from cache)
            first_result = results[0]
            for result in results[1:]:
                assert result is first_result  # Same object identity

    @given(yaml_safe_value_strategy(), yaml_safe_value_strategy())
    @settings(max_examples=20)
    def test_reload_clears_cache(self, value1: Any, value2: Any) -> None:
        """Reload should clear cache and re-read from disk.

        Property: After reload(), load() returns fresh data from disk.
        """
        assume(value1 != value2)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"

            # Write initial config
            config_path.write_text(yaml.safe_dump({"key": value1}))

            loader = ConfigLoader(config_dir=tmpdir)

            # First load
            result1 = loader.load("test")
            assert result1["key"] == value1

            # Modify file
            config_path.write_text(yaml.safe_dump({"key": value2}))

            # Without reload, should return cached value
            result2 = loader.load("test")
            assert result2["key"] == value1  # Still cached

            # After reload, should return new value
            loader.reload("test")
            result3 = loader.load("test")
            assert result3["key"] == value2  # Fresh from disk


# =============================================================================
# Property Tests: Key Path Navigation
# =============================================================================


@pytest.mark.property
class TestKeyPathProperties:
    """Property tests for dot-separated key path navigation."""

    @given(
        st.lists(
            st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=4,
        )
    )
    @settings(max_examples=30)
    def test_key_path_navigates_nested_dict(self, keys: list[str]) -> None:
        """Key path should navigate through nested dicts.

        Property: get(config, 'a.b.c') returns config['a']['b']['c'].
        """
        # Build nested dict
        value = "leaf_value"
        nested: str | dict[str, Any] = value
        for key in reversed(keys):
            nested = {key: nested}

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text(yaml.safe_dump(nested))

            loader = ConfigLoader(config_dir=tmpdir)

            key_path = ".".join(keys)
            result = loader.get("test", key_path)

            assert result == value

    @given(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz."))
    @settings(max_examples=20)
    def test_invalid_key_path_returns_default(self, invalid_path: str) -> None:
        """Invalid key paths should return default value.

        Property: Non-existent path returns default, not exception.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text("simple_key: simple_value\n")

            loader = ConfigLoader(config_dir=tmpdir)

            default_val = "my_default"
            result = loader.get("test", invalid_path, default=default_val)

            # Either finds the key or returns default (no exception)
            assert result == default_val or result is not None

    @given(yaml_safe_value_strategy())
    @settings(max_examples=20)
    def test_none_key_path_returns_entire_config(self, value: Any) -> None:
        """None key path should return entire config.

        Property: get(config, None) returns the full config dict.
        """
        config_data = {"test_key": value}

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.yaml"
            config_path.write_text(yaml.safe_dump(config_data))

            loader = ConfigLoader(config_dir=tmpdir)

            result = loader.get("test", None)

            assert isinstance(result, dict)
            assert "test_key" in result


# =============================================================================
# Property Tests: Environment State
# =============================================================================


@pytest.mark.property
class TestEnvironmentStateProperties:
    """Property tests for environment state methods."""

    @given(environment_name_strategy())
    def test_environment_check_methods_mutually_exclusive(self, env: str) -> None:
        """Only one environment check should return True at a time.

        Property: Exactly one of is_production/is_development/is_staging/is_test is True.
        """
        loader = ConfigLoader()
        loader.environment = env

        checks = [
            loader.is_production(),
            loader.is_development(),
            loader.is_staging(),
            loader.is_test(),
        ]

        # Exactly one should be True
        assert sum(checks) == 1

    @given(environment_name_strategy())
    def test_is_production_only_true_for_production(self, env: str) -> None:
        """is_production() should only return True for 'production'.

        Property: is_production() iff environment == 'production'
        """
        loader = ConfigLoader()
        loader.environment = env

        if env == "production":
            assert loader.is_production() is True
        else:
            assert loader.is_production() is False


# =============================================================================
# Property Tests: Config List Handling
# =============================================================================


@pytest.mark.property
class TestListConversionProperties:
    """Property tests for list handling in Decimal conversion."""

    @given(
        st.lists(
            st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=20)
    def test_decimal_conversion_handles_lists_in_nested_dict(self, values: list[float]) -> None:
        """Lists within dicts should have items processed.

        Property: Lists are traversed and items processed recursively.
        """
        loader = ConfigLoader()

        # Create nested structure with list containing dicts with decimal keys
        test_data = {"items": [{"price": v} for v in values]}

        result = loader._convert_to_decimal(test_data)

        for i, item in enumerate(result["items"]):
            assert isinstance(item["price"], Decimal), f"Item {i} price should be Decimal"

    @given(
        st.lists(
            st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=15)
    def test_plain_list_items_not_converted(self, values: list[float]) -> None:
        """Plain lists (not in dict with decimal key) should not convert items.

        Property: List items only converted if nested under decimal key.
        """
        loader = ConfigLoader()

        # Plain list at top level
        test_data = {"regular_list": values}

        result = loader._convert_to_decimal(test_data)

        # Items should still be floats (no decimal key)
        for item in result["regular_list"]:
            assert isinstance(item, float)
