"""
Configuration package for Precog trading system.

Provides centralized access to:
- YAML configuration files (ConfigLoader)
- Two-axis environment configuration (AppEnvironment, MarketMode)

All monetary values automatically converted to Decimal for precision.

Reference: docs/guides/ENVIRONMENT_CONFIGURATION_GUIDE_V1.0.md
"""

from .config_loader import (
    ConfigLoader,
    config,
    get_market_config,
    get_model_config,
    get_strategy_config,
    get_trading_config,
)
from .environment import (
    AppEnvironment,
    CombinationSafety,
    EnvironmentConfig,
    MarketMode,
    get_app_environment,
    get_database_name,
    get_market_mode,
    load_environment_config,
    require_app_environment,
    require_market_mode,
)

__all__ = [
    "AppEnvironment",
    "CombinationSafety",
    "ConfigLoader",
    "EnvironmentConfig",
    "MarketMode",
    "config",
    "get_app_environment",
    "get_database_name",
    "get_market_config",
    "get_market_mode",
    "get_model_config",
    "get_strategy_config",
    "get_trading_config",
    "load_environment_config",
    "require_app_environment",
    "require_market_mode",
]
