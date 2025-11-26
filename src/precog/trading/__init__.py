"""Trading module for Precog.

This module contains trading-related functionality including:
- Strategy management (versioned strategy configurations)
- Position management (lifecycle tracking, trailing stops)
- Risk management (position sizing, exposure limits)
- Kelly criterion position sizing (calculate_kelly_size, calculate_edge)
- TypedDict definitions for trading responses

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.5.md Phase 1.5
"""

from precog.trading.kelly_criterion import (
    calculate_edge,
    calculate_kelly_size,
    calculate_optimal_position,
)
from precog.trading.position_manager import (
    InsufficientMarginError,
    InvalidPositionStateError,
    PositionManager,
)
from precog.trading.strategy_manager import StrategyManager
from precog.trading.types import (
    ManagerError,
    ModelListResponse,
    ModelResponse,
    PnLCalculation,
    PositionListResponse,
    PositionResponse,
    StrategyConfig,
    StrategyListResponse,
    StrategyResponse,
    TrailingStopConfig,
    TrailingStopState,
)

__all__ = [
    "InsufficientMarginError",
    "InvalidPositionStateError",
    "ManagerError",
    "ModelListResponse",
    "ModelResponse",
    "PnLCalculation",
    "PositionListResponse",
    "PositionManager",
    "PositionResponse",
    "StrategyConfig",
    "StrategyListResponse",
    "StrategyManager",
    "StrategyResponse",
    "TrailingStopConfig",
    "TrailingStopState",
    "calculate_edge",
    "calculate_kelly_size",
    "calculate_optimal_position",
]
