"""Analytics module for Precog.

This module contains analytics-related functionality including:
- Probability model management (versioned model configurations)
- Model validation and calibration
- Performance metrics tracking

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.5.md Phase 1.5
"""

from precog.analytics.model_manager import (
    ImmutabilityError,
    InvalidStatusTransitionError,
    ModelManager,
)

__all__ = ["ImmutabilityError", "InvalidStatusTransitionError", "ModelManager"]
