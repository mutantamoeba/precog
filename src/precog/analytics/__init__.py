"""Analytics module for Precog.

This module contains analytics-related functionality including:
- Probability model management (versioned model configurations)
- Model validation and calibration
- Performance metrics tracking
- TypedDict definitions for analytics responses

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.5.md Phase 1.5
"""

from precog.analytics.model_manager import (
    ImmutabilityError,
    InvalidStatusTransitionError,
    ModelManager,
)
from precog.analytics.types import (
    DailyPnLSummary,
    ModelCalibrationBucket,
    ModelPerformanceMetrics,
    PeriodPerformanceSummary,
    PortfolioSnapshot,
    PositionSummary,
    StrategyComparisonResult,
    StrategyPerformanceMetrics,
)

__all__ = [
    "DailyPnLSummary",
    "ImmutabilityError",
    "InvalidStatusTransitionError",
    "ModelCalibrationBucket",
    "ModelManager",
    "ModelPerformanceMetrics",
    "PeriodPerformanceSummary",
    "PortfolioSnapshot",
    "PositionSummary",
    "StrategyComparisonResult",
    "StrategyPerformanceMetrics",
]
