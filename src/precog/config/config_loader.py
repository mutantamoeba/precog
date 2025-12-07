"""
Configuration loader with YAML support and environment-aware .env loading.

Configuration Hierarchy (Priority Order):
-----------------------------------------
1. **YAML files** (config/*.yaml) - Base defaults for all environments
2. **Environment variables** (.env file) - Overrides YAML (secrets, env-specific values)
3. **Command-line arguments** - Highest priority (not yet implemented)

This 3-tier hierarchy allows:
- **Version control** for base configs (YAML files checked into git)
- **Secret management** for credentials (.env file in .gitignore)
- **Runtime overrides** for testing (CLI args override everything)

7 YAML Configuration Files:
---------------------------
- **trading.yaml**: Core trading parameters (max exposure, kelly fraction)
- **trade_strategies.yaml**: Strategy configurations (versions, parameters)
- **position_management.yaml**: Position and risk management (stop losses, position sizing)
- **probability_models.yaml**: Model configurations (Elo ratings, ensemble weights)
- **markets.yaml**: Market-specific settings (NFL, NBA, election markets)
- **data_sources.yaml**: API endpoints (Kalshi, ESPN, balldontlie)
- **system.yaml**: System-level settings (logging, database, performance)

Multi-Environment Support:
--------------------------
Environment variables use automatic prefixes based on ENVIRONMENT variable:
- **DEV_*** prefix for development (local laptop)
- **STAGING_*** prefix for staging (pre-production testing)
- **PROD_*** prefix for production (live trading!)
- **TEST_*** prefix for test (pytest fixtures)

Example - Different database hosts per environment:
  .env file:
    ENVIRONMENT=development
    DEV_DB_HOST=localhost
    STAGING_DB_HOST=staging.precog.internal
    PROD_DB_HOST=prod.precog.internal

  loader.get_env('DB_HOST')  # Returns 'localhost' (DEV_DB_HOST)

  # Change to production:
  ENVIRONMENT=production
  loader.get_env('DB_HOST')  # Returns 'prod.precog.internal' (PROD_DB_HOST)

Security Architecture:
---------------------
**CRITICAL: NEVER put secrets in YAML files!**

Why This Matters:
- YAML files are checked into git (version control)
- Git history is permanent (even after deleting files)
- Anyone with repo access sees all secrets
- Leaked API keys = unauthorized trading with YOUR money

Secrets ALWAYS go in .env file (.gitignore prevents git commits):
- ✅ CORRECT: PROD_KALSHI_API_KEY=sk_live_xxx  (in .env)
- ❌ WRONG: kalshi_api_key: sk_live_xxx  (in YAML)

See: docs/utility/SECURITY_REVIEW_CHECKLIST.md for pre-commit security scan

Decimal Precision (CRITICAL for Money):
---------------------------------------
All monetary values automatically converted from float -> Decimal:
- Prevents floating-point errors (0.1 + 0.2 ≠ 0.3 in float!)
- Kalshi uses sub-penny pricing ($0.4975) - MUST be exact
- Financial calculations require precision to the penny

Auto-converted keys (see _convert_to_decimal):
- *_dollars, *_price, *_spread -> Decimal
- probability, threshold, *_percent -> Decimal
- See full list in _convert_to_decimal() method (200+ lines)

Caching Strategy:
----------------
Configurations cached after first load for performance:
- First load: Read YAML from disk (~5-10ms)
- Subsequent loads: Return cached dict (<0.1ms)
- Call reload() to force re-read from disk

Reference: docs/guides/CONFIGURATION_GUIDE_V3.1.md
Related Requirements: REQ-CONFIG-001 (YAML Configuration), REQ-SEC-009 (Credential Management)
Related ADR: ADR-012 (Configuration Management Strategy), ADR-002 (Decimal Precision)
"""

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

import yaml
from dotenv import load_dotenv

from precog.utils.logger import get_logger

logger = get_logger(__name__)


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

        logger.debug(f"ConfigLoader initialized with config_dir: {self.config_dir}")

        # Load environment variables from .env file
        load_dotenv()
        logger.debug("Loaded environment variables from .env file")

        # Get current environment (development, staging, production, test)
        self.environment = os.getenv("ENVIRONMENT", "development")
        logger.debug(f"Environment set to: {self.environment}")

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
        logger.debug(f"Looking for env var '{prefixed_key}': {'found' if value else 'not found'}")

        # Fall back to unprefixed variable (for backward compatibility)
        if value is None:
            value = os.getenv(key)
            if value is not None:
                logger.debug(f"Fallback to unprefixed '{key}': found")

        # Return default if not found
        if value is None:
            logger.debug(f"Env var '{key}' not found, using default: {default}")
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
            except (ValueError, TypeError, InvalidOperation):
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
            }

        if isinstance(obj, dict):
            return {
                key: (
                    Decimal(str(value))
                    if key in keys_to_convert and isinstance(value, (int, float, str))
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

        # Check cache first (use get() for thread-safety - single atomic operation
        # instead of `if key in dict` + `dict[key]` which can race with reload())
        cache_key = config_name.replace(".yaml", "")
        cached = self.configs.get(cache_key)
        if cached is not None:
            logger.debug(f"Config '{cache_key}' loaded from cache")
            return cached

        # Load from file
        file_path = self.config_dir / config_name
        logger.debug(f"Loading config file: {file_path}")
        if not file_path.exists():
            msg = f"Config file not found: {file_path}"
            logger.debug(f"Config file not found: {file_path}")
            raise FileNotFoundError(msg)

        with open(file_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.debug(
            f"Parsed YAML config '{config_name}' with {len(config) if config else 0} top-level keys"
        )

        # Convert money/price values to Decimal
        if convert_decimals:
            config = self._convert_to_decimal(config)
            logger.debug(f"Converted monetary values to Decimal for '{config_name}'")

        # Cache the result
        self.configs[cache_key] = config
        logger.debug(f"Cached config '{cache_key}'")
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
                    logger.warning(f"Config file not found: {config_file} (skipping)")
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing {config_file}: {e}")
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
        # Load config if not cached (use get() for thread-safety)
        config = self.configs.get(config_name)
        if config is None:
            try:
                config = self.load(config_name)
            except FileNotFoundError:
                logger.debug(f"Config '{config_name}' not found, returning default: {default}")
                return default

        # If no key path, return entire config
        if key_path is None:
            logger.debug(f"Returning entire config for '{config_name}'")
            return config

        # Navigate nested keys
        keys = key_path.split(".")
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.debug(
                    f"Key path '{key_path}' not found in '{config_name}', returning default: {default}"
                )
                return default

        logger.debug(f"Retrieved '{config_name}.{key_path}' = {value}")
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
            logger.debug(f"Cleared cache for config '{config_name}'")
        else:
            # Clear entire cache
            self.configs.clear()
            logger.debug("Cleared entire config cache")

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
                logger.info(f"{config_file} loaded successfully")
            except FileNotFoundError:
                logger.error(f"{config_file} not found")
                all_valid = False
            except yaml.YAMLError as e:
                logger.error(f"{config_file} has YAML errors: {e}")
                all_valid = False
            except Exception as e:
                logger.error(f"{config_file} failed to load: {e}")
                all_valid = False

        return all_valid

    def get_active_strategy_version(self, strategy_name: str) -> dict[str, Any] | None:
        """
        Get active version configuration for a strategy.

        This method queries the database for the active version of a strategy
        and returns its configuration. If no active version exists in the database,
        returns None (YAML config is just a template, not runtime config).

        Args:
            strategy_name: Strategy identifier (e.g., 'halftime_entry')

        Returns:
            Strategy configuration dict from database, or None if no active version

        Educational Note:
            **Configuration Hierarchy:**
            1. Database (active version) = Source of truth (immutable, versioned)
            2. YAML files = Templates for creating new versions

            Why database takes precedence?
            - Strategies use IMMUTABLE versions (ADR-018)
            - Each version has frozen config in database
            - YAML is template, NOT runtime config

            Example flow:
            1. YAML has template: halftime_entry with default min_edge: "0.06"
            2. Create v1.0 in database: min_edge = Decimal("0.06")
            3. Create v1.1 in database: min_edge = Decimal("0.08") (better backtest)
            4. Set v1.1 to 'active' status
            5. This method returns v1.1 config (min_edge = Decimal("0.08"))

        References:
            - REQ-VER-001: Immutable Version Configs
            - REQ-VER-004: Version Lifecycle Management
            - ADR-018: Immutable Strategy Versions
            - Pattern 2 (CLAUDE.md): Dual Versioning System

        Example:
            >>> loader = ConfigLoader()
            >>> halftime_config = loader.get_active_strategy_version('halftime_entry')
            >>> if halftime_config:
            ...     print(halftime_config['min_edge'])  # Decimal("0.08")
            ... else:
            ...     print("No active version in database")
        """
        # Import here to avoid circular dependency
        from precog.trading.strategy_manager import StrategyManager

        manager = StrategyManager()

        # Get all active strategies
        active_strategies = manager.get_active_strategies()

        # Filter by strategy_name
        matching_strategies = [s for s in active_strategies if s["strategy_name"] == strategy_name]

        if not matching_strategies:
            logger.warning(
                f"No active version found for strategy '{strategy_name}' in database",
                extra={"strategy_name": strategy_name},
            )
            return None

        if len(matching_strategies) > 1:
            # Multiple active versions (A/B testing scenario)
            # Return highest version number (most recent)
            matching_strategies.sort(key=lambda s: s["strategy_version"], reverse=True)
            logger.info(
                f"Multiple active versions for '{strategy_name}', returning latest: "
                f"{matching_strategies[0]['strategy_version']}",
                extra={"strategy_name": strategy_name, "count": len(matching_strategies)},
            )

        strategy = matching_strategies[0]
        logger.info(
            f"Retrieved active strategy config: {strategy_name} {strategy['strategy_version']}",
            extra={
                "strategy_id": strategy["strategy_id"],
                "version": strategy["strategy_version"],
                "status": strategy["status"],
            },
        )

        # Return complete strategy dict (includes config, status, metrics, etc.)
        return strategy

    def get_active_model_version(self, model_name: str) -> dict[str, Any] | None:
        """
        Get active version configuration for a probability model.

        This method queries the database for the active version of a model
        and returns its configuration. If no active version exists in the database,
        returns None (YAML config is just a template, not runtime config).

        Args:
            model_name: Model identifier (e.g., 'elo_nfl')

        Returns:
            Model configuration dict from database, or None if no active version

        Educational Note:
            **Model Versioning Pattern:**
            Models follow same immutability pattern as strategies (ADR-019).
            Each version has frozen config for A/B testing and attribution.

            Example: elo_nfl_v1.0 (k_factor=32) vs elo_nfl_v1.1 (k_factor=35)
            - Both can be 'active' simultaneously (A/B testing)
            - Each trade records which model_id was used
            - Enables comparing: "Did v1.1 improve accuracy?"

        References:
            - REQ-VER-001: Immutable Version Configs
            - REQ-VER-005: A/B Testing Support
            - ADR-019: Semantic Versioning for Models
            - Pattern 2 (CLAUDE.md): Dual Versioning System

        Example:
            >>> loader = ConfigLoader()
            >>> elo_config = loader.get_active_model_version('elo_nfl')
            >>> if elo_config:
            ...     print(elo_config['config']['k_factor'])  # Decimal("35")
            ... else:
            ...     print("No active version in database")
        """
        # Import here to avoid circular dependency
        from precog.analytics.model_manager import ModelManager

        manager = ModelManager()

        # Get all active models
        active_models = manager.get_active_models()

        # Filter by model_name
        matching_models = [m for m in active_models if m["model_name"] == model_name]

        if not matching_models:
            logger.warning(
                f"No active version found for model '{model_name}' in database",
                extra={"model_name": model_name},
            )
            return None

        if len(matching_models) > 1:
            # Multiple active versions (A/B testing scenario)
            # Return highest version number (most recent)
            matching_models.sort(key=lambda m: m["model_version"], reverse=True)
            logger.info(
                f"Multiple active versions for '{model_name}', returning latest: "
                f"{matching_models[0]['model_version']}",
                extra={"model_name": model_name, "count": len(matching_models)},
            )

        model = matching_models[0]
        logger.info(
            f"Retrieved active model config: {model_name} {model['model_version']}",
            extra={
                "model_id": model["model_id"],
                "version": model["model_version"],
                "status": model["status"],
            },
        )

        # Return complete model dict (includes config, status, metrics, etc.)
        return model

    def get_trailing_stop_config(self, strategy_name: str | None = None) -> dict[str, Any]:
        """
        Get trailing stop configuration for a strategy.

        This method retrieves trailing stop parameters from position_management.yaml.
        If strategy_name is provided, returns strategy-specific overrides merged with
        defaults. Otherwise, returns default trailing stop config.

        Args:
            strategy_name: Optional strategy identifier for strategy-specific overrides

        Returns:
            Trailing stop configuration dict

        Educational Note:
            **Trailing Stop Architecture:**
            Trailing stops protect profits by adjusting stop-loss as price moves favorably.

            Example: Buy YES at $0.52, set trailing stop:
            - activation_threshold: "0.15" (activate when 15¢ profit)
            - distance: "0.05" (trail 5¢ below highest price)

            Price movement:
            1. $0.52 -> $0.67 (+15¢) -> Trailing stop activates at $0.62
            2. $0.67 -> $0.75 (+23¢) -> Trailing stop moves to $0.70
            3. $0.75 -> $0.72 (-3¢) -> Triggered! Sell at $0.72 (20¢ profit locked in)

            Configuration layers:
            1. Default: position_management.yaml -> trailing_stops
            2. Strategy-specific: position_management.yaml -> trailing_stops -> strategies -> {strategy_name}

        References:
            - REQ-RISK-003: Trailing Stop Loss
            - ADR-025: Trailing Stop Implementation
            - docs/guides/TRAILING_STOP_GUIDE_V1.0.md

        Example:
            >>> loader = ConfigLoader()
            >>> # Get default config
            >>> default = loader.get_trailing_stop_config()
            >>> print(default['activation_threshold'])  # Decimal("0.15")
            >>>
            >>> # Get strategy-specific config
            >>> halftime = loader.get_trailing_stop_config('halftime_entry')
            >>> print(halftime['activation_threshold'])  # Decimal("0.10") (override)
        """
        # Load position management config
        pos_mgmt = self.load("position_management")

        # Get default trailing stop config
        trailing_stops = pos_mgmt.get("trailing_stops", {})
        default_config = trailing_stops.get("default", {})

        if not default_config:
            logger.warning("No default trailing_stops config found in position_management.yaml")
            return {}

        # If no strategy specified, return default
        if strategy_name is None:
            return dict(default_config) if isinstance(default_config, dict) else {}

        # Get strategy-specific overrides
        strategy_overrides = trailing_stops.get("strategies", {}).get(strategy_name, {})

        if not strategy_overrides:
            logger.info(
                f"No strategy-specific trailing stop config for '{strategy_name}', using defaults",
                extra={"strategy_name": strategy_name},
            )
            return dict(default_config) if isinstance(default_config, dict) else {}

        # Merge: strategy overrides take precedence
        merged_config = {**default_config, **strategy_overrides}

        logger.info(
            f"Merged trailing stop config for strategy '{strategy_name}'",
            extra={
                "strategy_name": strategy_name,
                "overrides": list(strategy_overrides.keys()),
            },
        )

        return merged_config


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
