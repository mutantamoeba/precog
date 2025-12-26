"""Analytics module for Precog.

This module contains analytics-related functionality including:
- Probability model management (versioned model configurations)
- Model validation and calibration
- Performance metrics tracking
- TypedDict definitions for analytics responses
- Elo rating computation engine (FiveThirtyEight methodology)

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.5.md Phase 1.5
Reference: docs/guides/ELO_COMPUTATION_GUIDE_V1.1.md (Elo engine)
"""

from precog.analytics.elo_computation_service import (
    ComputationResult,
    EloComputationService,
    TeamRatingState,
    compute_elo_ratings,
    get_elo_computation_stats,
)
from precog.analytics.elo_engine import (
    DEFAULT_CARRYOVER_WEIGHT,
    DEFAULT_INITIAL_RATING,
    DEFAULT_REGRESSION_TARGET,
    ELO_DIVISOR,
    SPORT_CONFIGS,
    EloEngine,
    EloState,
    EloUpdateResult,
    Sport,
    SportConfig,
    elo_to_win_probability,
    get_elo_engine,
    win_probability_to_elo_difference,
)
from precog.analytics.model_manager import (
    ImmutabilityError,
    InvalidStatusTransitionError,
    ModelManager,
)
from precog.analytics.types import (
    DailyPnLSummary,
    EloHistoryEntry,
    EloRating,
    EloUpdateLog,
    EpaMetrics,
    ModelCalibrationBucket,
    ModelPerformanceMetrics,
    PeriodPerformanceSummary,
    PortfolioSnapshot,
    PositionSummary,
    StrategyComparisonResult,
    StrategyPerformanceMetrics,
    WinProbabilityPrediction,
)

__all__ = [
    # Elo Engine
    "DEFAULT_CARRYOVER_WEIGHT",
    "DEFAULT_INITIAL_RATING",
    "DEFAULT_REGRESSION_TARGET",
    "ELO_DIVISOR",
    "SPORT_CONFIGS",
    # Types - Performance
    "DailyPnLSummary",
    "EloEngine",
    # Types - Elo
    "EloHistoryEntry",
    "EloRating",
    "EloState",
    "EloUpdateLog",
    "EloUpdateResult",
    "EpaMetrics",
    # Model Manager
    "ImmutabilityError",
    "InvalidStatusTransitionError",
    "ModelCalibrationBucket",
    "ModelManager",
    "ModelPerformanceMetrics",
    "PeriodPerformanceSummary",
    "PortfolioSnapshot",
    "PositionSummary",
    "Sport",
    "SportConfig",
    "StrategyComparisonResult",
    "StrategyPerformanceMetrics",
    "WinProbabilityPrediction",
    "elo_to_win_probability",
    "get_elo_engine",
    "win_probability_to_elo_difference",
]
