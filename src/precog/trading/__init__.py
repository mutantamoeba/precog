"""Trading module for Precog.

This module contains trading-related functionality including:
- Strategy management (versioned strategy configurations)
- Position management (lifecycle tracking, trailing stops)
- Risk management (position sizing, exposure limits)

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.5.md Phase 1.5
"""

from precog.trading.strategy_manager import StrategyManager

__all__ = ["StrategyManager"]
