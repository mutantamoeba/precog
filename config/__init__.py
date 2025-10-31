"""
Configuration package for Precog trading system.

Provides centralized access to all YAML configuration files.
All monetary values automatically converted to Decimal for precision.
"""

from .config_loader import (
    ConfigLoader,
    config,
    get_market_config,
    get_model_config,
    get_strategy_config,
    get_trading_config,
)

__all__ = [
    "ConfigLoader",
    "config",
    "get_market_config",
    "get_model_config",
    "get_strategy_config",
    "get_trading_config",
]
