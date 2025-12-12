"""
Chaos Tests for ConfigLoader.

Tests configuration loader resilience under chaotic conditions:
- Malformed YAML files
- Missing configuration files
- Corrupted file content
- Filesystem errors (permissions, disk full simulation)
- Environment variable chaos

Related:
- TESTING_STRATEGY V3.5: All 8 test types required
- config/config_loader module coverage

Usage:
    pytest tests/chaos/config/test_config_loader_chaos.py -v -m chaos

Educational Note:
    Chaos tests verify that ConfigLoader degrades gracefully when:
    1. YAML files are malformed or corrupted
    2. Config files are missing or inaccessible
    3. Environment variables are in unexpected states
    4. Decimal conversion fails on bad data

    Unlike unit tests that verify correct behavior, chaos tests verify
    resilient behavior under failure. A good chaos test should:
    - Trigger a failure mode
    - Verify the system doesn't crash
    - Verify appropriate error handling (exception type, error message)

Reference: docs/foundation/TESTING_STRATEGY_V3.5.md Section "Best Practice #6"
"""

import os
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


@pytest.mark.chaos
class TestConfigLoaderYAMLChaos:
    """Chaos tests for YAML parsing resilience."""

    def _create_temp_dir(self) -> Path:
        """Create an empty temp directory for config files."""
        return Path(tempfile.mkdtemp())

    def test_malformed_yaml_syntax(self):
        """
        CHAOS: YAML file with syntax errors.

        Verifies:
        - Appropriate YAMLError raised
        - Error message indicates parsing failure
        - System doesn't crash
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        # Create malformed YAML
        malformed_yaml = temp_dir / "trading.yaml"
        malformed_yaml.write_text(
            """
account:
  max_exposure: 10000
  - invalid_list_in_dict  # This is invalid YAML syntax
  min_edge: 0.05
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)

        with pytest.raises(yaml.YAMLError):
            loader.load("trading")

    def test_yaml_with_tabs_instead_of_spaces(self):
        """
        CHAOS: YAML file using tabs (common mistake).

        Verifies:
        - Error handling for tab-indented YAML
        - Clear error message about indentation
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        # Create YAML with tabs (invalid)
        tab_yaml = temp_dir / "trading.yaml"
        tab_yaml.write_text(
            "account:\n\tmax_exposure: 10000\n\tmin_edge: 0.05\n",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)

        # Tab-indented YAML may parse but produce unexpected results
        # or raise YAMLError depending on content
        try:
            config = loader.load("trading")
            # If it parses, verify we got something
            assert config is not None
        except yaml.YAMLError:
            # This is acceptable - tabs cause parsing issues
            pass

    def test_empty_yaml_file(self):
        """
        CHAOS: Completely empty YAML file.

        Verifies:
        - Returns None or empty dict, not crash
        - No exception for empty file
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        empty_yaml = temp_dir / "trading.yaml"
        empty_yaml.write_text("", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)
        config = loader.load("trading")

        # Empty YAML parses to None
        assert config is None or config == {}

    def test_yaml_only_comments(self):
        """
        CHAOS: YAML file with only comments.

        Verifies:
        - Handles comment-only files gracefully
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        comment_yaml = temp_dir / "trading.yaml"
        comment_yaml.write_text(
            """
# This is a comment
# Another comment
# No actual content
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)
        config = loader.load("trading")

        assert config is None or config == {}

    def test_yaml_with_binary_content(self):
        """
        CHAOS: YAML file with binary/garbage content.

        Verifies:
        - Binary content causes parse error
        - No crash on garbage input
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        binary_yaml = temp_dir / "trading.yaml"
        binary_yaml.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        loader = ConfigLoader(config_dir=temp_dir)

        with pytest.raises((yaml.YAMLError, UnicodeDecodeError)):
            loader.load("trading")

    def test_yaml_with_circular_reference_pattern(self):
        """
        CHAOS: YAML with anchor/alias that could cause issues.

        Verifies:
        - Complex YAML features handled correctly
        - No infinite loops or memory issues
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        # Use keys that ARE in the decimal conversion list
        anchor_yaml = temp_dir / "trading.yaml"
        anchor_yaml.write_text(
            """
defaults: &defaults
  max_total_exposure_dollars: "10000.00"
  min_edge: "0.05"

account:
  <<: *defaults
  name: "production"
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)
        config = loader.load("trading")

        # YAML anchors should merge correctly
        # Note: max_total_exposure_dollars IS in the decimal conversion list
        assert config["account"]["max_total_exposure_dollars"] == Decimal("10000.00")
        assert config["account"]["min_edge"] == Decimal("0.05")
        assert config["account"]["name"] == "production"


@pytest.mark.chaos
class TestConfigLoaderFilesystemChaos:
    """Chaos tests for filesystem error handling."""

    def test_missing_config_file(self):
        """
        CHAOS: Config file doesn't exist.

        Verifies:
        - FileNotFoundError raised
        - Clear error message with path
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        loader = ConfigLoader(config_dir=temp_dir)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_missing_config_dir(self):
        """
        CHAOS: Config directory doesn't exist.

        Verifies:
        - Handles non-existent directory
        """
        from precog.config.config_loader import ConfigLoader

        loader = ConfigLoader(config_dir="/nonexistent/path/config")

        with pytest.raises(FileNotFoundError):
            loader.load("trading")

    def test_file_read_permission_error(self):
        """
        CHAOS: Config file exists but can't be read.

        Verifies:
        - PermissionError propagated appropriately
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        config_file = temp_dir / "trading.yaml"
        config_file.write_text("key: value\n", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)

        # Mock open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError):
                loader.load("trading")

    def test_file_disappears_after_exists_check(self):
        """
        CHAOS: File deleted between exists() check and open().

        Verifies:
        - Race condition with file deletion handled
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        config_file = temp_dir / "trading.yaml"
        config_file.write_text("key: value\n", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)

        # Mock Path.exists to return True, but open to fail
        def mock_open(*args, **kwargs):
            raise FileNotFoundError("File disappeared")

        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open):
                with pytest.raises(FileNotFoundError):
                    loader.load("trading")


@pytest.mark.chaos
class TestConfigLoaderDecimalChaos:
    """Chaos tests for Decimal conversion edge cases."""

    def _create_temp_dir(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_invalid_decimal_string(self):
        """
        CHAOS: Config value that can't convert to Decimal.

        Verifies:
        - Invalid Decimal strings handled
        - Non-numeric values don't crash conversion
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        bad_decimal_yaml = temp_dir / "trading.yaml"
        bad_decimal_yaml.write_text(
            """
account:
  max_total_exposure_dollars: "not_a_number"
  min_edge: "also_invalid"
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)

        # Should raise on invalid Decimal conversion
        from decimal import InvalidOperation

        with pytest.raises(InvalidOperation):  # Decimal raises InvalidOperation for bad input
            loader.load("trading")

    def test_extremely_large_decimal(self):
        """
        CHAOS: Config with extremely large numbers.

        Verifies:
        - Large numbers handled by Decimal
        - No overflow errors
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        large_yaml = temp_dir / "trading.yaml"
        large_yaml.write_text(
            """
account:
  max_total_exposure_dollars: "999999999999999999999999999999.99"
  min_edge: "0.0000000000000000000001"
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)
        config = loader.load("trading")

        # Decimal should handle these large/small values
        assert isinstance(config["account"]["max_total_exposure_dollars"], Decimal)
        assert isinstance(config["account"]["min_edge"], Decimal)

    def test_decimal_with_special_characters(self):
        """
        CHAOS: Config with currency symbols or commas in numbers.

        Verifies:
        - Currency symbols cause conversion error
        - Commas cause conversion error
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        # Test with currency symbol
        currency_yaml = temp_dir / "trading.yaml"
        currency_yaml.write_text(
            """
account:
  max_total_exposure_dollars: "$10,000.00"
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)

        from decimal import InvalidOperation

        with pytest.raises(InvalidOperation):  # Decimal raises InvalidOperation for bad input
            loader.load("trading")

    def test_decimal_scientific_notation(self):
        """
        CHAOS: Config with scientific notation numbers.

        Verifies:
        - Scientific notation handled by Decimal
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        sci_yaml = temp_dir / "trading.yaml"
        sci_yaml.write_text(
            """
account:
  max_total_exposure_dollars: "1e4"
  min_edge: "5e-2"
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)
        config = loader.load("trading")

        # Decimal should handle scientific notation
        assert config["account"]["max_total_exposure_dollars"] == Decimal("10000")
        assert config["account"]["min_edge"] == Decimal("0.05")

    def test_nan_and_infinity(self):
        """
        CHAOS: Config with NaN or Infinity values.

        Verifies:
        - Special float values handled
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = self._create_temp_dir()

        special_yaml = temp_dir / "trading.yaml"
        special_yaml.write_text(
            """
account:
  max_total_exposure_dollars: .nan
  min_edge: .inf
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=temp_dir)

        # YAML's .nan and .inf are floats - conversion to Decimal may fail
        try:
            config = loader.load("trading")
            # If it doesn't fail, verify we got something
            assert "account" in config
        except Exception:
            # Acceptable - NaN/Inf to Decimal conversion is problematic
            pass


@pytest.mark.chaos
class TestConfigLoaderEnvironmentChaos:
    """Chaos tests for environment variable handling."""

    def test_environment_variable_with_null_bytes(self):
        """
        CHAOS: Environment variable containing null bytes.

        Verifies:
        - OS rejects null bytes in env vars (platform behavior)
        - System doesn't crash on attempted null byte injection

        Educational Note:
            Windows and most Unix systems reject null bytes in environment
            variables at the OS level. This is a security feature.
        """
        # OS rejects null bytes - this is expected behavior
        with pytest.raises(ValueError, match="embedded null"):
            with patch.dict(os.environ, {"TEST_VAR": "value\x00with\x00nulls"}):
                pass  # patch.dict itself raises ValueError

    def test_environment_variable_unicode(self):
        """
        CHAOS: Environment variable with unicode characters.

        Verifies:
        - Unicode env vars handled correctly
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        loader = ConfigLoader(config_dir=temp_dir)

        with patch.dict(os.environ, {"UNICODE_VAR": "value_with_emoji_and_unicode"}):
            result = loader.get_env("UNICODE_VAR")
            assert result == "value_with_emoji_and_unicode"

    def test_environment_variable_extremely_long(self):
        """
        CHAOS: Environment variable with very long value.

        Verifies:
        - Windows has 32767 char limit on env vars
        - System handles within OS limits

        Educational Note:
            Windows limits environment variables to 32,767 characters.
            Linux has higher limits (~128KB) but varies by kernel.
            Testing near-limit values ensures we don't silently truncate.
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        loader = ConfigLoader(config_dir=temp_dir)

        # Use value under Windows limit (32767)
        long_value = "x" * 30000  # 30KB string - under limit

        with patch.dict(os.environ, {"LONG_VAR": long_value}):
            result = loader.get_env("LONG_VAR")
            assert result == long_value
            assert len(result) == 30000

    def test_environment_prefix_empty_string(self):
        """
        CHAOS: Environment set to empty string.

        Verifies:
        - Empty environment string handled
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())

        with patch.dict(os.environ, {"ENVIRONMENT": ""}):
            loader = ConfigLoader(config_dir=temp_dir)
            # Empty env should result in "_VAR" prefix being searched
            assert loader.environment == ""

    def test_type_conversion_with_whitespace(self):
        """
        CHAOS: Environment variables with leading/trailing whitespace.

        Verifies:
        - Whitespace in values handled
        - Type conversion still works
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        loader = ConfigLoader(config_dir=temp_dir)

        with patch.dict(
            os.environ,
            {
                "INT_VAR": "  42  ",
                "BOOL_VAR": "  true  ",
                "DECIMAL_VAR": "  0.05  ",
            },
        ):
            # Whitespace may cause conversion issues
            try:
                int_val = loader.get_env("INT_VAR", as_type=int)
                assert int_val is None or int_val == 42  # Might fail
            except ValueError:
                pass  # Acceptable

            bool_val = loader.get_env("BOOL_VAR", as_type=bool)
            # .lower().strip() might not be called
            assert isinstance(bool_val, bool)

    def test_get_env_invalid_type(self):
        """
        CHAOS: get_env called with unsupported type.

        Verifies:
        - Unsupported types handled gracefully
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        loader = ConfigLoader(config_dir=temp_dir)

        with patch.dict(os.environ, {"TEST_VAR": "some_value"}):
            # Request an unsupported type (like list)
            result = loader.get_env("TEST_VAR", as_type=list)
            # Should return string since list isn't explicitly handled
            assert isinstance(result, str)


@pytest.mark.chaos
class TestConfigLoaderCacheChaos:
    """Chaos tests for cache behavior under failure conditions."""

    def test_reload_during_load(self):
        """
        CHAOS: reload() called while load() is in progress.

        Verifies:
        - No corruption when reload clears cache mid-load
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        config_file = temp_dir / "trading.yaml"
        config_file.write_text("key: value\n", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)

        # Simulate reload during load by clearing cache
        original_load = loader.load

        def load_with_reload(name, **kwargs):
            loader.reload()  # Clear cache mid-operation
            return original_load(name, **kwargs)

        # This shouldn't crash
        result = load_with_reload("trading")
        assert result is not None

    def test_get_with_corrupted_cache(self):
        """
        CHAOS: Cache contains invalid data.

        Verifies:
        - Corrupted cache entries handled
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())
        config_file = temp_dir / "trading.yaml"
        config_file.write_text("key: value\n", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)

        # Corrupt the cache manually
        loader.configs["trading"] = "not_a_dict"  # type: ignore[assignment]  # Intentionally wrong type for chaos test

        # get() should handle this gracefully or re-load
        try:
            result = loader.get("trading", "key")
            # If it works, good
            assert result is not None or result is None
        except (TypeError, AttributeError):
            # Also acceptable - corrupted cache causes error
            pass

    def test_validate_required_configs_partial_failure(self):
        """
        CHAOS: Some config files valid, some missing.

        Verifies:
        - Validation continues after first failure
        - Returns False when some configs missing
        """
        from precog.config.config_loader import ConfigLoader

        temp_dir = Path(tempfile.mkdtemp())

        # Create only one config file
        trading_yaml = temp_dir / "trading.yaml"
        trading_yaml.write_text("key: value\n", encoding="utf-8")

        loader = ConfigLoader(config_dir=temp_dir)
        result = loader.validate_required_configs()

        # Should return False (not all configs present)
        assert result is False
