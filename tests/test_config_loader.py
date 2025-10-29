"""
Tests for YAML configuration loader.

Critical tests:
- YAML files load correctly
- Decimal conversion works
- Float values NOT used for money/prices
- Nested key access works
- Missing configs handled gracefully
"""

import pytest
from decimal import Decimal
from pathlib import Path
import yaml

from config.config_loader import ConfigLoader


@pytest.mark.unit
def test_config_loader_initialization(temp_config_dir):
    """Test ConfigLoader initializes with custom directory."""
    loader = ConfigLoader(config_dir=str(temp_config_dir))
    assert loader.config_dir == temp_config_dir


@pytest.mark.unit
def test_load_yaml_file(config_loader):
    """Test loading a YAML file."""
    config = config_loader.load('test_config')
    assert config is not None
    assert 'trading' in config


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
    config = loader.load('money_test', convert_decimals=True)

    # Money fields should be Decimal
    assert type(config['max_position_size_dollars']) == Decimal
    assert type(config['min_ev_threshold']) == Decimal
    assert type(config['kelly_fraction']) == Decimal

    # Non-money fields should be original types
    assert type(config['some_integer']) == int
    assert type(config['some_string']) == str


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
    config = loader.load('precision_test', convert_decimals=True)

    # Verify exact string representation (no rounding)
    assert str(config['price']) == '0.5200' or str(config['price']) == '0.52'
    assert str(config['sub_penny']) == '0.4275'
    assert str(config['tight_spread']) == '0.0001'


@pytest.mark.unit
def test_no_decimal_conversion_when_disabled(temp_config_dir):
    """Test that conversion can be disabled."""
    config_file = temp_config_dir / "float_test.yaml"
    config_file.write_text("""
max_position_size_dollars: 1000.00
""")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    config = loader.load('float_test', convert_decimals=False)

    # Should be float when conversion disabled
    assert type(config['max_position_size_dollars']) == float


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
    config = loader.load('nested_test', convert_decimals=True)

    # Nested dicts
    assert type(config['account']['max_total_exposure_dollars']) == Decimal
    assert type(config['account']['daily_loss_limit_dollars']) == Decimal

    # Nested lists
    assert type(config['strategies'][0]['min_ev_threshold']) == Decimal
    assert type(config['strategies'][1]['min_ev_threshold']) == Decimal


@pytest.mark.unit
def test_config_caching(config_loader):
    """Test that configs are cached after first load."""
    # Load twice
    config1 = config_loader.load('test_config')
    config2 = config_loader.load('test_config')

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
    value = loader.get('nested_access', 'trading.account.max_exposure')
    assert value == Decimal('10000.00')


@pytest.mark.unit
def test_get_with_default_value(config_loader):
    """Test that get() returns default for missing keys."""
    value = config_loader.get('nonexistent_config', 'some.key', default='default_value')
    assert value == 'default_value'


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
    value = loader.get('partial', 'trading.missing.key', default=None)
    assert value is None


@pytest.mark.unit
def test_reload_clears_cache(temp_config_dir):
    """Test that reload() clears cache."""
    config_file = temp_config_dir / "reload_test.yaml"
    config_file.write_text("value: 1")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    # Load config
    config1 = loader.load('reload_test', convert_decimals=False)
    assert config1['value'] == 1

    # Modify file
    config_file.write_text("value: 2")

    # Load again (should be cached)
    config2 = loader.load('reload_test', convert_decimals=False)
    assert config2['value'] == 1  # Still old value

    # Reload and load again
    loader.reload('reload_test')
    config3 = loader.load('reload_test', convert_decimals=False)
    assert config3['value'] == 2  # New value


@pytest.mark.unit
def test_load_all_configs(temp_config_dir):
    """Test loading multiple configs at once."""
    # Create multiple config files
    (temp_config_dir / "config1.yaml").write_text("key1: value1")
    (temp_config_dir / "config2.yaml").write_text("key2: value2")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ['config1.yaml', 'config2.yaml']

    configs = loader.load_all(convert_decimals=False)

    assert 'config1' in configs
    assert 'config2' in configs
    assert configs['config1']['key1'] == 'value1'
    assert configs['config2']['key2'] == 'value2'


@pytest.mark.unit
def test_missing_config_file_raises_error(config_loader):
    """Test that loading missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        config_loader.load('nonexistent_file')


@pytest.mark.unit
def test_invalid_yaml_raises_error(temp_config_dir):
    """Test that invalid YAML raises YAMLError."""
    config_file = temp_config_dir / "invalid.yaml"
    # Create actually invalid YAML (tabs are not allowed for indentation)
    config_file.write_text("key: value\n\tinvalid: tab indentation")

    loader = ConfigLoader(config_dir=str(temp_config_dir))

    with pytest.raises(yaml.YAMLError):
        loader.load('invalid')


@pytest.mark.integration
def test_load_real_trading_config():
    """Integration test: Load real trading.yaml config."""
    loader = ConfigLoader()  # Use default config directory

    try:
        config = loader.load('trading')

        # Verify expected structure
        assert 'account' in config
        assert 'max_total_exposure_dollars' in config['account']

        # Verify Decimal conversion
        assert type(config['account']['max_total_exposure_dollars']) == Decimal

    except FileNotFoundError:
        pytest.skip("trading.yaml not found in config directory")


@pytest.mark.unit
def test_validate_required_configs(temp_config_dir):
    """Test validate_required_configs() method."""
    # Create some required configs
    (temp_config_dir / "trading.yaml").write_text("key: value")
    (temp_config_dir / "system.yaml").write_text("key: value")

    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ['trading.yaml', 'system.yaml']

    # Should pass validation
    result = loader.validate_required_configs()
    assert result is True


@pytest.mark.unit
def test_validate_required_configs_fails_on_missing(temp_config_dir):
    """Test validation fails when configs missing."""
    loader = ConfigLoader(config_dir=str(temp_config_dir))
    loader.config_files = ['missing1.yaml', 'missing2.yaml']

    # Should fail validation
    result = loader.validate_required_configs()
    assert result is False
