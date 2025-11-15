"""
Tests for YAML configuration loader.

Critical tests:
- YAML files load correctly
- Decimal conversion works
- Float values NOT used for money/prices
- Nested key access works
- Missing configs handled gracefully
"""

from decimal import Decimal

import pytest
import yaml

from precog.config.config_loader import ConfigLoader


@pytest.mark.unit
def test_config_loader_initialization(temp_config_dir):
    """Test ConfigLoader initializes with custom directory."""
    loader = ConfigLoader(config_dir=str(temp_config_dir))
    assert loader.config_dir == temp_config_dir


@pytest.mark.unit
def test_load_yaml_file(config_loader):
    """Test loading a YAML file."""
    config = config_loader.load("test_config")
    assert config is not None
    assert "trading" in config


@pytest.mark.unit
@pytest.mark.critical
def test_decimal_conversion(temp_config_dir):
    """CRITICAL: Test that money values convert to Decimal, NOT float."""
    # Create config with money values
    config_file = temp_config_dir / "money_test.yaml"
    config_file.write_text("""
max_position_size_dollars: 1000.00
min_ev_threshold: 0.05
kelly_fraction: 0.25
some_integer: 42
some_string: "hello"
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    config = loader.load("money_test", convert_decimals=True)

    # Money fields should be Decimal
    assert type(config["max_position_size_dollars"]) == Decimal
    assert type(config["min_ev_threshold"]) == Decimal
    assert type(config["kelly_fraction"]) == Decimal

    # Non-money fields should be original types
    assert type(config["some_integer"]) == int
    assert type(config["some_string"]) == str


@pytest.mark.unit
@pytest.mark.critical
def test_decimal_precision_preserved(temp_config_dir):
    """CRITICAL: Test exact Decimal precision (no float rounding)."""
    config_file = temp_config_dir / "precision_test.yaml"
    config_file.write_text("""
price: 0.5200
sub_penny: 0.4275
tight_spread: 0.0001
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    config = loader.load("precision_test", convert_decimals=True)

    # Verify exact string representation (no rounding)
    assert str(config["price"]) == "0.5200" or str(config["price"]) == "0.52"
    assert str(config["sub_penny"]) == "0.4275"
    assert str(config["tight_spread"]) == "0.0001"


@pytest.mark.unit
def test_no_decimal_conversion_when_disabled(temp_config_dir):
    """Test that conversion can be disabled."""
    config_file = temp_config_dir / "float_test.yaml"
    config_file.write_text("""
max_position_size_dollars: 1000.00
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    config = loader.load("float_test", convert_decimals=False)

    # Should be float when conversion disabled
    assert type(config["max_position_size_dollars"]) == float


@pytest.mark.unit
def test_nested_decimal_conversion(temp_config_dir):
    """Test Decimal conversion works in nested structures."""
    config_file = temp_config_dir / "nested_test.yaml"
    config_file.write_text("""
account:
  max_total_exposure_dollars: 10000.00
  daily_loss_limit_dollars: 500.00
strategies:
  - name: strategy1
    min_ev_threshold: 0.05
  - name: strategy2
    min_ev_threshold: 0.10
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    config = loader.load("nested_test", convert_decimals=True)

    # Nested dicts
    assert type(config["account"]["max_total_exposure_dollars"]) == Decimal
    assert type(config["account"]["daily_loss_limit_dollars"]) == Decimal

    # Nested lists
    assert type(config["strategies"][0]["min_ev_threshold"]) == Decimal
    assert type(config["strategies"][1]["min_ev_threshold"]) == Decimal


@pytest.mark.unit
def test_config_caching(config_loader):
    """Test that configs are cached after first load."""
    # Load twice
    config1 = config_loader.load("test_config")
    config2 = config_loader.load("test_config")

    # Should be same object (cached)
    assert config1 is config2


@pytest.mark.unit
def test_get_with_nested_key_path(temp_config_dir):
    """Test accessing nested config with dot notation."""
    config_file = temp_config_dir / "nested_access.yaml"
    config_file.write_text("""
trading:
  account:
    max_exposure: 10000.00
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    # Access nested key with dot notation
    value = loader.get("nested_access", "trading.account.max_exposure")
    assert value == Decimal("10000.00")


@pytest.mark.unit
def test_get_with_default_value(config_loader):
    """Test that get() returns default for missing keys."""
    value = config_loader.get("nonexistent_config", "some.key", default="default_value")
    assert value == "default_value"


@pytest.mark.unit
def test_get_missing_nested_key_returns_default(temp_config_dir):
    """Test that missing nested keys return default."""
    config_file = temp_config_dir / "partial.yaml"
    config_file.write_text("""
trading:
  account:
    max_exposure: 10000.00
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    # Access missing nested key
    value = loader.get("partial", "trading.missing.key", default=None)
    assert value is None


@pytest.mark.unit
def test_reload_clears_cache(temp_config_dir):
    """Test that reload() clears cache."""
    config_file = temp_config_dir / "reload_test.yaml"
    config_file.write_text("value: 1")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    # Load config
    config1 = loader.load("reload_test", convert_decimals=False)
    assert config1["value"] == 1

    # Modify file
    config_file.write_text("value: 2")

    # Load again (should be cached)
    config2 = loader.load("reload_test", convert_decimals=False)
    assert config2["value"] == 1  # Still old value

    # Reload and load again
    loader.reload("reload_test")
    config3 = loader.load("reload_test", convert_decimals=False)
    assert config3["value"] == 2  # New value


@pytest.mark.unit
def test_load_all_configs(temp_config_dir):
    """Test loading multiple configs at once."""
    # Create multiple config files
    (temp_config_dir / "config1.yaml").write_text("key1: value1")
    (temp_config_dir / "config2.yaml").write_text("key2: value2")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["config1.yaml", "config2.yaml"]

    configs = loader.load_all(convert_decimals=False)

    assert "config1" in configs
    assert "config2" in configs
    assert configs["config1"]["key1"] == "value1"
    assert configs["config2"]["key2"] == "value2"


@pytest.mark.unit
def test_missing_config_file_raises_error(config_loader):
    """Test that loading missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        config_loader.load("nonexistent_file")


@pytest.mark.unit
def test_invalid_yaml_raises_error(temp_config_dir):
    """Test that invalid YAML raises YAMLError."""
    config_file = temp_config_dir / "invalid.yaml"
    # Create actually invalid YAML (tabs are not allowed for indentation)
    config_file.write_text("key: value\n\tinvalid: tab indentation")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    with pytest.raises(yaml.YAMLError):
        loader.load("invalid")


@pytest.mark.integration
def test_load_real_trading_config():
    """Integration test: Load real trading.yaml config."""
    loader = ConfigLoader()  # Use default config directory

    try:
        config = loader.load("trading")

        # Verify expected structure
        assert "account" in config
        assert "max_total_exposure_dollars" in config["account"]

        # Verify Decimal conversion
        assert type(config["account"]["max_total_exposure_dollars"]) == Decimal

    except FileNotFoundError:
        pytest.skip("trading.yaml not found in config directory")


@pytest.mark.unit
def test_validate_required_configs(temp_config_dir):
    """Test validate_required_configs() method."""
    # Create some required configs
    (temp_config_dir / "trading.yaml").write_text("key: value")
    (temp_config_dir / "system.yaml").write_text("key: value")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["trading.yaml", "system.yaml"]

    # Should pass validation
    result = loader.validate_required_configs()
    assert result is True


@pytest.mark.unit
def test_validate_required_configs_fails_on_missing(temp_config_dir):
    """Test validation fails when configs missing."""
    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["missing1.yaml", "missing2.yaml"]

    # Should fail validation
    result = loader.validate_required_configs()
    assert result is False


# ============================================================================
# Environment Variable and Configuration Tests (Lines 164-248)
# ============================================================================


@pytest.mark.unit
def test_get_env_with_environment_prefix(monkeypatch):
    """Test get_env() uses environment-specific prefix (DEVELOPMENT_, PRODUCTION_, etc.)."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEVELOPMENT_DB_HOST", "localhost")
    monkeypatch.setenv("DEVELOPMENT_DB_PORT", "5432")

    loader = ConfigLoader()

    # Should get DEVELOPMENT_DB_HOST (with DEVELOPMENT_ prefix)
    db_host = loader.get_env("DB_HOST")
    assert db_host == "localhost"

    # Should get DEVELOPMENT_DB_PORT
    db_port = loader.get_env("DB_PORT")
    assert db_port == "5432"


@pytest.mark.unit
def test_get_env_fallback_to_unprefixed(monkeypatch):
    """Test get_env() falls back to unprefixed variable if prefixed not found."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    # Set unprefixed variable only (no DEV_ prefix)
    monkeypatch.setenv("LEGACY_VAR", "legacy_value")

    loader = ConfigLoader()

    # Should fall back to LEGACY_VAR (no DEV_LEGACY_VAR exists)
    value = loader.get_env("LEGACY_VAR")
    assert value == "legacy_value"


@pytest.mark.unit
def test_get_env_returns_default_when_not_found(monkeypatch):
    """Test get_env() returns default when variable not found."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    loader = ConfigLoader()

    # Variable doesn't exist, should return default
    value = loader.get_env("NONEXISTENT_VAR", default="default_value")
    assert value == "default_value"


@pytest.mark.unit
def test_get_env_bool_conversion(monkeypatch):
    """Test get_env() converts string to bool."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("TEST_ENABLE_FEATURE", "true")
    monkeypatch.setenv("TEST_DISABLE_FEATURE", "false")
    monkeypatch.setenv("TEST_NUMERIC_TRUE", "1")
    monkeypatch.setenv("TEST_WORD_YES", "yes")
    monkeypatch.setenv("TEST_WORD_ON", "on")

    loader = ConfigLoader()

    # Test various truthy values
    assert loader.get_env("ENABLE_FEATURE", as_type=bool) is True
    assert loader.get_env("NUMERIC_TRUE", as_type=bool) is True
    assert loader.get_env("WORD_YES", as_type=bool) is True
    assert loader.get_env("WORD_ON", as_type=bool) is True

    # Test falsy value
    assert loader.get_env("DISABLE_FEATURE", as_type=bool) is False


@pytest.mark.unit
def test_get_env_int_conversion(monkeypatch):
    """Test get_env() converts string to int."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEVELOPMENT_PORT", "5432")
    monkeypatch.setenv("DEVELOPMENT_INVALID_INT", "not_a_number")

    loader = ConfigLoader()

    # Valid int
    port = loader.get_env("PORT", as_type=int)
    assert port == 5432
    assert type(port) == int

    # Invalid int - should return default
    invalid = loader.get_env("INVALID_INT", default=8080, as_type=int)
    assert invalid == 8080


@pytest.mark.unit
def test_get_env_decimal_conversion(monkeypatch):
    """Test get_env() converts string to Decimal."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PRODUCTION_MAX_EXPOSURE", "10000.50")
    monkeypatch.setenv("PRODUCTION_INVALID_DECIMAL", "not_a_decimal")

    loader = ConfigLoader()

    # Valid Decimal
    max_exposure = loader.get_env("MAX_EXPOSURE", as_type=Decimal)
    assert max_exposure == Decimal("10000.50")
    assert type(max_exposure) == Decimal

    # Invalid Decimal - should return default
    invalid = loader.get_env("INVALID_DECIMAL", default=Decimal("0.00"), as_type=Decimal)
    assert invalid == Decimal("0.00")


@pytest.mark.unit
def test_get_db_config(monkeypatch):
    """Test get_db_config() returns database configuration dict."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEVELOPMENT_DB_HOST", "localhost")
    monkeypatch.setenv("DEVELOPMENT_DB_PORT", "5432")
    monkeypatch.setenv("DEVELOPMENT_DB_NAME", "precog_dev")
    monkeypatch.setenv("DEVELOPMENT_DB_USER", "postgres")
    monkeypatch.setenv("DEVELOPMENT_DB_PASSWORD", "test_password")

    loader = ConfigLoader()
    db_config = loader.get_db_config()

    assert db_config["host"] == "localhost"
    assert db_config["port"] == 5432  # Should be int
    assert db_config["database"] == "precog_dev"
    assert db_config["user"] == "postgres"
    assert db_config["password"] == "test_password"


@pytest.mark.unit
def test_get_kalshi_config(monkeypatch):
    """Test get_kalshi_config() returns Kalshi API configuration dict."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PRODUCTION_KALSHI_API_KEY", "sk_live_test123")
    monkeypatch.setenv("PRODUCTION_KALSHI_PRIVATE_KEY_PATH", "_keys/prod_private.pem")
    monkeypatch.setenv("PRODUCTION_KALSHI_BASE_URL", "https://api.kalshi.co")

    loader = ConfigLoader()
    kalshi_config = loader.get_kalshi_config()

    assert kalshi_config["api_key"] == "sk_live_test123"
    assert kalshi_config["private_key_path"] == "_keys/prod_private.pem"
    assert kalshi_config["base_url"] == "https://api.kalshi.co"


@pytest.mark.unit
def test_is_production(monkeypatch):
    """Test is_production() environment check."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    loader = ConfigLoader()
    assert loader.is_production() is True
    assert loader.is_development() is False
    assert loader.is_staging() is False
    assert loader.is_test() is False


@pytest.mark.unit
def test_is_development(monkeypatch):
    """Test is_development() environment check."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    loader = ConfigLoader()
    assert loader.is_development() is True
    assert loader.is_production() is False
    assert loader.is_staging() is False
    assert loader.is_test() is False


@pytest.mark.unit
def test_is_staging(monkeypatch):
    """Test is_staging() environment check."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    loader = ConfigLoader()
    assert loader.is_staging() is True
    assert loader.is_production() is False
    assert loader.is_development() is False
    assert loader.is_test() is False


@pytest.mark.unit
def test_is_test(monkeypatch):
    """Test is_test() environment check."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    loader = ConfigLoader()
    assert loader.is_test() is True
    assert loader.is_production() is False
    assert loader.is_development() is False
    assert loader.is_staging() is False


# ============================================================================
# Additional get() Method Tests (Lines 414, 424)
# ============================================================================


@pytest.mark.unit
def test_get_returns_entire_config_when_no_key_path(temp_config_dir):
    """Test get() returns entire config when key_path is None."""
    config_file = temp_config_dir / "full_config.yaml"
    config_file.write_text("""
trading:
  max_exposure: 10000
system:
  log_level: INFO
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    # Get entire config (no key_path)
    full_config = loader.get("full_config", key_path=None)

    assert "trading" in full_config
    assert "system" in full_config
    assert full_config["trading"]["max_exposure"] == Decimal("10000")
    assert full_config["system"]["log_level"] == "INFO"


@pytest.mark.unit
def test_get_returns_default_when_config_not_found_and_not_cached(config_loader):
    """Test get() returns default when config file not found and not cached."""
    # Config doesn't exist and isn't cached
    value = config_loader.get("totally_nonexistent_config", "some.key", default="fallback")
    assert value == "fallback"


# ============================================================================
# reload() Edge Case Test (Line 455)
# ============================================================================


@pytest.mark.unit
def test_reload_all_configs_clears_entire_cache(temp_config_dir):
    """Test reload() with no config_name clears entire cache."""
    # Create multiple config files
    (temp_config_dir / "config_a.yaml").write_text("value: A")
    (temp_config_dir / "config_b.yaml").write_text("value: B")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    # Load both configs
    loader.load("config_a", convert_decimals=False)
    loader.load("config_b", convert_decimals=False)

    assert "config_a" in loader.configs
    assert "config_b" in loader.configs

    # Reload all (no config_name specified)
    loader.reload()

    # Cache should be empty
    assert len(loader.configs) == 0


# ============================================================================
# validate_required_configs() Error Handling Tests (Lines 479-484)
# ============================================================================


@pytest.mark.unit
def test_validate_required_configs_handles_yaml_error(temp_config_dir):
    """Test validate_required_configs() handles YAMLError gracefully."""
    # Create invalid YAML file
    invalid_file = temp_config_dir / "invalid_yaml.yaml"
    invalid_file.write_text("key: value\n\tinvalid: tab indentation")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["invalid_yaml.yaml"]

    # Should return False and not crash
    result = loader.validate_required_configs()
    assert result is False


@pytest.mark.unit
def test_validate_required_configs_handles_generic_exception(temp_config_dir, monkeypatch):
    """Test validate_required_configs() handles generic exceptions gracefully."""
    # Create a config file that exists
    config_file = temp_config_dir / "test_exception.yaml"
    config_file.write_text("key: value")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["test_exception.yaml"]

    # Mock loader.load() to raise a generic exception
    def mock_load_with_exception(config_name, convert_decimals=True):
        raise RuntimeError("Simulated unexpected error")

    monkeypatch.setattr(loader, "load", mock_load_with_exception)

    # Should return False and not crash
    result = loader.validate_required_configs()
    assert result is False


# ============================================================================
# load_all() Error Handling Tests (Lines 383-387)
# ============================================================================


@pytest.mark.unit
def test_load_all_handles_file_not_found_with_warning(temp_config_dir):
    """Test load_all() handles FileNotFoundError with warning (doesn't crash)."""
    # Create one config, leave others missing
    (temp_config_dir / "exists.yaml").write_text("key: value")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["exists.yaml", "missing.yaml"]

    # Should not crash, should load what exists
    configs = loader.load_all(convert_decimals=False)

    assert "exists" in configs
    assert "missing" not in configs  # Skipped with warning


@pytest.mark.unit
def test_load_all_propagates_yaml_error(temp_config_dir):
    """Test load_all() propagates YAMLError (doesn't suppress)."""
    # Create invalid YAML file
    invalid_file = temp_config_dir / "bad_yaml.yaml"
    invalid_file.write_text("key: value\n\tinvalid: tab indentation")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ["bad_yaml.yaml"]

    # YAMLError should propagate (not suppressed)
    with pytest.raises(yaml.YAMLError):
        loader.load_all(convert_decimals=False)


# ============================================================================
# Global Convenience Function Tests (Lines 496, 509-510, 523-524, 537-538, 558, 573, 593, 608, 613, 618, 623, 628)
# ============================================================================


@pytest.mark.integration
def test_get_trading_config_global_function(monkeypatch):
    """Test get_trading_config() global convenience function."""
    # Use actual config directory (or skip if trading.yaml doesn't exist)
    import precog.config.config_loader as config_module

    try:
        trading_config = config_module.get_trading_config()

        # Verify expected structure
        assert trading_config is not None
        assert isinstance(trading_config, dict)

    except FileNotFoundError:
        pytest.skip("trading.yaml not found in config directory")


@pytest.mark.unit
def test_get_strategy_config_global_function(temp_config_dir, monkeypatch):
    """Test get_strategy_config() global convenience function."""
    # Create strategy config
    strategy_file = temp_config_dir / "trade_strategies.yaml"
    strategy_file.write_text("""
strategies:
  halftime_entry:
    min_ev_threshold: 0.05
    max_position_size_dollars: 1000
  momentum_fade:
    min_ev_threshold: 0.10
    max_position_size_dollars: 500
""")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    # Replace global config instance with one using temp directory
    original_config = config_module.config
    config_module.config = ConfigLoader(config_dir=str(temp_config_dir))

    try:
        # Test getting specific strategy
        strategy = config_module.get_strategy_config("halftime_entry")

        assert strategy is not None
        assert strategy["min_ev_threshold"] == Decimal("0.05")
        assert strategy["max_position_size_dollars"] == Decimal("1000")

        # Test getting nonexistent strategy
        nonexistent = config_module.get_strategy_config("nonexistent_strategy")
        assert nonexistent is None

    finally:
        # Restore original config
        config_module.config = original_config


@pytest.mark.unit
def test_get_model_config_global_function(temp_config_dir, monkeypatch):
    """Test get_model_config() global convenience function."""
    # Create model config
    model_file = temp_config_dir / "probability_models.yaml"
    model_file.write_text("""
models:
  live_elo:
    k_factor: 32
    reversion_rate: 0.03
  historical_baseline:
    lookback_days: 365
""")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    original_config = config_module.config
    config_module.config = ConfigLoader(config_dir=str(temp_config_dir))

    try:
        # Test getting specific model
        model = config_module.get_model_config("live_elo")

        assert model is not None
        assert model["k_factor"] == 32
        # Note: reversion_rate doesn't match auto-conversion patterns (*_dollars, probability, etc.)
        assert model["reversion_rate"] == 0.03  # Stays as float

        # Test getting nonexistent model
        nonexistent = config_module.get_model_config("nonexistent_model")
        assert nonexistent is None

    finally:
        config_module.config = original_config


@pytest.mark.unit
def test_get_market_config_global_function(temp_config_dir, monkeypatch):
    """Test get_market_config() global convenience function."""
    # Create market config
    market_file = temp_config_dir / "markets.yaml"
    market_file.write_text("""
markets:
  nfl:
    min_liquidity: 1000
    max_spread: 0.05
  nba:
    min_liquidity: 500
    max_spread: 0.10
""")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    original_config = config_module.config
    config_module.config = ConfigLoader(config_dir=str(temp_config_dir))

    try:
        # Test getting specific market
        market = config_module.get_market_config("nfl")

        assert market is not None
        assert market["min_liquidity"] == 1000
        assert market["max_spread"] == Decimal("0.05")

        # Test getting nonexistent market
        nonexistent = config_module.get_market_config("nonexistent_market")
        assert nonexistent is None

    finally:
        config_module.config = original_config


@pytest.mark.unit
def test_get_db_config_global_function(monkeypatch):
    """Test get_db_config() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("TEST_DB_HOST", "test_host")
    monkeypatch.setenv("TEST_DB_PORT", "5433")
    monkeypatch.setenv("TEST_DB_NAME", "test_db")
    monkeypatch.setenv("TEST_DB_USER", "test_user")
    monkeypatch.setenv("TEST_DB_PASSWORD", "test_pass")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    # Need to recreate config after monkeypatch
    config_module.config = ConfigLoader()

    db_config = config_module.get_db_config()

    assert db_config["host"] == "test_host"
    assert db_config["port"] == 5433
    assert db_config["database"] == "test_db"
    assert db_config["user"] == "test_user"
    assert db_config["password"] == "test_pass"


@pytest.mark.unit
def test_get_kalshi_config_global_function(monkeypatch):
    """Test get_kalshi_config() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("TEST_KALSHI_API_KEY", "test_key")
    monkeypatch.setenv("TEST_KALSHI_PRIVATE_KEY_PATH", "_keys/test.pem")
    monkeypatch.setenv("TEST_KALSHI_BASE_URL", "https://test-api.kalshi.co")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    # Need to recreate config after monkeypatch
    config_module.config = ConfigLoader()

    kalshi_config = config_module.get_kalshi_config()

    assert kalshi_config["api_key"] == "test_key"
    assert kalshi_config["private_key_path"] == "_keys/test.pem"
    assert kalshi_config["base_url"] == "https://test-api.kalshi.co"


@pytest.mark.unit
def test_get_env_global_function(monkeypatch):
    """Test get_env() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEVELOPMENT_TEST_VAR", "test_value")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    # Need to recreate config after monkeypatch
    config_module.config = ConfigLoader()

    value = config_module.get_env("TEST_VAR")
    assert value == "test_value"

    # Test with default
    nonexistent = config_module.get_env("NONEXISTENT", default="default_val")
    assert nonexistent == "default_val"


@pytest.mark.unit
def test_get_environment_global_function(monkeypatch):
    """Test get_environment() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "staging")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    # Need to recreate config after monkeypatch
    config_module.config = ConfigLoader()

    env = config_module.get_environment()
    assert env == "staging"


@pytest.mark.unit
def test_is_production_global_function(monkeypatch):
    """Test is_production() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    config_module.config = ConfigLoader()

    assert config_module.is_production() is True


@pytest.mark.unit
def test_is_development_global_function(monkeypatch):
    """Test is_development() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    config_module.config = ConfigLoader()

    assert config_module.is_development() is True


@pytest.mark.unit
def test_is_staging_global_function(monkeypatch):
    """Test is_staging() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "staging")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    config_module.config = ConfigLoader()

    assert config_module.is_staging() is True


@pytest.mark.unit
def test_is_test_global_function(monkeypatch):
    """Test is_test() global convenience function."""
    monkeypatch.setenv("ENVIRONMENT", "test")

    # Import and patch the global config instance
    import precog.config.config_loader as config_module

    config_module.config = ConfigLoader()

    assert config_module.is_test() is True
