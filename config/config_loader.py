"""
Configuration loader with YAML support and environment-aware .env loading.

Loads 7 YAML configuration files:
- trading.yaml: Core trading parameters
- trade_strategies.yaml: Strategy configurations
- position_management.yaml: Position and risk management
- probability_models.yaml: Probability model configurations
- markets.yaml: Market-specific settings
- data_sources.yaml: API and data source credentials
- system.yaml: System-level settings

ALSO loads environment variables from .env file with multi-environment support:
- DEV_* prefix for development environment
- STAGING_* prefix for staging environment
- PROD_* prefix for production environment
- TEST_* prefix for test environment

IMPORTANT: Money/price values automatically converted to Decimal to prevent
floating-point precision errors.
"""

import os
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """
    Load and manage YAML configuration files.

    All monetary values are automatically converted to Decimal for precision.
    Configurations are cached after first load for performance.
    """

    def __init__(self, config_dir: str | Path | None = None):
        """
        Initialize configuration loader.

        Args:
            config_dir: Path to config directory (defaults to ./config)
        """
        if config_dir is None:
            # Default to config directory relative to this file
            self.config_dir = Path(__file__).parent
        else:
            self.config_dir = Path(config_dir)
        self.configs: dict[str, dict[str, Any]] = {}

        # Load environment variables from .env file
        load_dotenv()

        # Get current environment (development, staging, production, test)
        self.environment = os.getenv("ENVIRONMENT", "development")

        # List of all configuration files
        self.config_files = [
            "trading.yaml",
            "trade_strategies.yaml",
            "position_management.yaml",
            "probability_models.yaml",
            "markets.yaml",
            "data_sources.yaml",
            "system.yaml",
        ]

    def get_env(self, key: str, default: Any = None, as_type: type = str) -> Any:
        """
        Get environment variable with automatic environment prefix handling.

        Automatically prefixes the key with current environment (DEV_, STAGING_, PROD_, TEST_)
        and falls back to unprefixed version if not found.

        Args:
            key: Environment variable name (without prefix)
            default: Default value if not found
            as_type: Type to convert the value to (str, int, bool, Decimal)

        Returns:
            Environment variable value converted to specified type

        Example:
            >>> # With ENVIRONMENT=development:
            >>> loader = ConfigLoader()
            >>> db_host = loader.get_env('DB_HOST')  # Looks for DEV_DB_HOST
            >>> 'localhost'
            >>>
            >>> db_port = loader.get_env('DB_PORT', as_type=int)
            >>> 5432
            >>>
            >>> # With ENVIRONMENT=production:
            >>> loader = ConfigLoader()
            >>> loader.environment = 'production'
            >>> db_host = loader.get_env('DB_HOST')  # Looks for PROD_DB_HOST
        """
        # Try environment-specific prefixed variable first
        env_prefix = self.environment.upper()
        prefixed_key = f"{env_prefix}_{key}"
        value = os.getenv(prefixed_key)

        # Fall back to unprefixed variable (for backward compatibility)
        if value is None:
            value = os.getenv(key)

        # Return default if not found
        if value is None:
            return default

        # Convert to requested type
        if as_type == bool:
            return value.lower() in ("true", "1", "yes", "on")
        if as_type == int:
            try:
                return int(value)
            except ValueError:
                return default
        elif as_type == Decimal:
            try:
                return Decimal(str(value))
            except (ValueError, TypeError):
                return default
        else:
            return value

    def get_db_config(self) -> dict[str, Any]:
        """
        Get database configuration from environment variables.

        Returns:
            Dictionary with database connection parameters

        Example:
            >>> loader = ConfigLoader()
            >>> db_config = loader.get_db_config()
            >>> print(db_config)
            {'host': 'localhost', 'port': 5432, 'database': 'precog_dev', ...}
        """
        return {
            "host": self.get_env("DB_HOST", "localhost"),
            "port": self.get_env("DB_PORT", 5432, as_type=int),
            "database": self.get_env("DB_NAME", "precog_dev"),
            "user": self.get_env("DB_USER", "postgres"),
            "password": self.get_env("DB_PASSWORD"),
        }

    def get_kalshi_config(self) -> dict[str, Any]:
        """
        Get Kalshi API configuration from environment variables.

        Returns:
            Dictionary with Kalshi API parameters

        Example:
            >>> loader = ConfigLoader()
            >>> kalshi_config = loader.get_kalshi_config()
            >>> print(kalshi_config['base_url'])
            'https://demo-api.kalshi.co'
        """
        return {
            "api_key": self.get_env("KALSHI_API_KEY"),
            "private_key_path": self.get_env(
                "KALSHI_PRIVATE_KEY_PATH", "_keys/kalshi_demo_private.pem"
            ),
            "base_url": self.get_env("KALSHI_BASE_URL", "https://demo-api.kalshi.co"),
        }

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == "staging"

    def is_test(self) -> bool:
        """Check if running in test environment."""
        return self.environment == "test"

    def _convert_to_decimal(self, obj: Any, keys_to_convert: set | None = None) -> Any:
        """
        Recursively convert float values to Decimal for specified keys.

        Args:
            obj: Object to process (dict, list, or scalar)
            keys_to_convert: Set of keys that should be Decimal

        Returns:
            Object with floats converted to Decimal where appropriate
        """
        # Default keys that should be Decimal (money, prices, probabilities)
        if keys_to_convert is None:
            keys_to_convert = {
                # Money/dollar amounts
                "max_total_exposure_dollars",
                "daily_loss_limit_dollars",
                "weekly_loss_limit_dollars",
                "min_balance_to_trade_dollars",
                "max_position_size_dollars",
                "min_trade_size_dollars",
                "max_trade_size_dollars",
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
                "max_kelly_fraction",
                "confidence",
                "min_edge",
                # Percentages
                "trailing_stop_percent",
                "stop_loss_percent",
                "target_profit_percent",
                "max_drawdown_percent",
            }

        if isinstance(obj, dict):
            return {
                key: (
                    Decimal(str(value))
                    if key in keys_to_convert and isinstance(value, int | float)
                    else self._convert_to_decimal(value, keys_to_convert)
                )
                for key, value in obj.items()
            }
        if isinstance(obj, list):
            return [self._convert_to_decimal(item, keys_to_convert) for item in obj]
        return obj

    def load(self, config_name: str, convert_decimals: bool = True) -> dict[str, Any]:
        """
        Load a specific configuration file.

        Args:
            config_name: Name of config file (without .yaml extension)
            convert_decimals: Whether to convert money/price values to Decimal

        Returns:
            Dictionary with configuration data

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails

        Example:
            >>> loader = ConfigLoader()
            >>> trading_config = loader.load('trading')
            >>> print(trading_config['account']['max_total_exposure_dollars'])
            Decimal('10000.00')
        """
        # Add .yaml extension if not present
        if not config_name.endswith(".yaml"):
            config_name = f"{config_name}.yaml"

        # Check cache first
        cache_key = config_name.replace(".yaml", "")
        if cache_key in self.configs:
            return self.configs[cache_key]

        # Load from file
        file_path = self.config_dir / config_name
        if not file_path.exists():
            msg = f"Config file not found: {file_path}"
            raise FileNotFoundError(msg)

        with open(file_path) as f:
            config = yaml.safe_load(f)

        # Convert money/price values to Decimal
        if convert_decimals:
            config = self._convert_to_decimal(config)

        # Cache the result
        self.configs[cache_key] = config
        return cast("dict[str, Any]", config)

    def load_all(self, convert_decimals: bool = True) -> dict[str, dict[str, Any]]:
        """
        Load all configuration files.

        Args:
            convert_decimals: Whether to convert money/price values to Decimal

        Returns:
            Dictionary mapping config names to their data

        Example:
            >>> loader = ConfigLoader()
            >>> all_configs = loader.load_all()
            >>> print(all_configs.keys())
            dict_keys(['trading', 'trade_strategies', 'position_management', ...])
        """
        for config_file in self.config_files:
            config_name = config_file.replace(".yaml", "")
            if config_name not in self.configs:
                try:
                    self.load(config_file, convert_decimals=convert_decimals)
                except FileNotFoundError:
                    print(f"[WARNING] Config file not found: {config_file} (skipping)")
                except yaml.YAMLError as e:
                    print(f"[ERROR] Error parsing {config_file}: {e}")
                    raise

        return self.configs

    def get(self, config_name: str, key_path: str | None = None, default: Any = None) -> Any:
        """
        Get configuration value with optional nested key access.

        Args:
            config_name: Name of config file (without .yaml)
            key_path: Dot-separated path to nested key (e.g., 'account.max_total_exposure_dollars')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> loader = ConfigLoader()
            >>> max_exposure = loader.get('trading', 'account.max_total_exposure_dollars')
            >>> print(max_exposure)
            Decimal('10000.00')

            >>> environment = loader.get('trading', 'environment', default='demo')
            >>> print(environment)
            'demo'
        """
        # Load config if not cached
        if config_name not in self.configs:
            try:
                self.load(config_name)
            except FileNotFoundError:
                return default

        config = self.configs[config_name]

        # If no key path, return entire config
        if key_path is None:
            return config

        # Navigate nested keys
        keys = key_path.split(".")
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def reload(self, config_name: str | None = None):
        """
        Reload configuration from disk (clears cache).

        Args:
            config_name: Specific config to reload, or None to reload all

        Example:
            >>> loader = ConfigLoader()
            >>> loader.reload('trading')  # Reload just trading.yaml
            >>> loader.reload()  # Reload all configs
        """
        if config_name:
            # Remove specific config from cache
            config_name = config_name.replace(".yaml", "")
            self.configs.pop(config_name, None)
        else:
            # Clear entire cache
            self.configs.clear()

    def validate_required_configs(self) -> bool:
        """
        Verify all required config files exist and are loadable.

        Returns:
            True if all configs valid, False otherwise

        Example:
            >>> loader = ConfigLoader()
            >>> if loader.validate_required_configs():
            ...     print("All configs valid!")
        """
        all_valid = True

        for config_file in self.config_files:
            config_file.replace(".yaml", "")
            try:
                self.load(config_file)
                print(f"[OK] {config_file} loaded successfully")
            except FileNotFoundError:
                print(f"[ERROR] {config_file} not found")
                all_valid = False
            except yaml.YAMLError as e:
                print(f"[ERROR] {config_file} has YAML errors: {e}")
                all_valid = False
            except Exception as e:
                print(f"[ERROR] {config_file} failed to load: {e}")
                all_valid = False

        return all_valid


# Global config loader instance
config = ConfigLoader()


# Convenience functions for common access patterns
def get_trading_config() -> dict[str, Any]:
    """Get trading configuration."""
    return config.load("trading")


def get_strategy_config(strategy_name: str) -> dict[str, Any] | None:
    """
    Get configuration for a specific strategy.

    Args:
        strategy_name: Name of the strategy (e.g., 'halftime_entry')

    Returns:
        Strategy configuration dict, or None if not found
    """
    strategies = config.load("trade_strategies")
    return cast("dict[str, Any] | None", strategies.get("strategies", {}).get(strategy_name))


def get_model_config(model_name: str) -> dict[str, Any] | None:
    """
    Get configuration for a specific probability model.

    Args:
        model_name: Name of the model (e.g., 'live_elo')

    Returns:
        Model configuration dict, or None if not found
    """
    models = config.load("probability_models")
    return cast("dict[str, Any] | None", models.get("models", {}).get(model_name))


def get_market_config(market_type: str) -> dict[str, Any] | None:
    """
    Get configuration for a specific market type.

    Args:
        market_type: Market type (e.g., 'nfl', 'nba')

    Returns:
        Market configuration dict, or None if not found
    """
    markets = config.load("markets")
    return cast("dict[str, Any] | None", markets.get("markets", {}).get(market_type))


# ============================================================================
# Environment Variable Convenience Functions
# ============================================================================


def get_db_config() -> dict[str, Any]:
    """
    Get database configuration for current environment.

    Returns:
        Database connection parameters

    Example:
        >>> from config.config_loader import get_db_config
        >>> db_config = get_db_config()
        >>> conn = psycopg2.connect(**db_config)
    """
    return config.get_db_config()


def get_kalshi_config() -> dict[str, Any]:
    """
    Get Kalshi API configuration for current environment.

    Returns:
        Kalshi API parameters

    Example:
        >>> from config.config_loader import get_kalshi_config
        >>> kalshi_config = get_kalshi_config()
        >>> api_key = kalshi_config['api_key']
    """
    return config.get_kalshi_config()


def get_env(key: str, default: Any = None, as_type: type = str) -> Any:
    """
    Get environment variable with automatic prefix handling.

    Args:
        key: Variable name (without environment prefix)
        default: Default value if not found
        as_type: Type to convert to (str, int, bool, Decimal)

    Returns:
        Environment variable value

    Example:
        >>> from config.config_loader import get_env
        >>> log_level = get_env('LOG_LEVEL', 'INFO')
        >>> max_exposure = get_env('MAX_TOTAL_EXPOSURE', as_type=Decimal)
    """
    return config.get_env(key, default, as_type)


def get_environment() -> str:
    """
    Get current environment name.

    Returns:
        'development', 'staging', 'production', or 'test'

    Example:
        >>> from config.config_loader import get_environment
        >>> if get_environment() == 'production':
        ...     enable_live_trading()
    """
    return config.environment


def is_production() -> bool:
    """Check if running in production environment."""
    return config.is_production()


def is_development() -> bool:
    """Check if running in development environment."""
    return config.is_development()


def is_staging() -> bool:
    """Check if running in staging environment."""
    return config.is_staging()


def is_test() -> bool:
    """Check if running in test environment."""
    return config.is_test()
