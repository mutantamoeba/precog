"""
Validation module for Precog data quality checks.

This module provides validation utilities to ensure data quality for:
- ESPN game state data (scores, clocks, situations)
- Kalshi market data (prices, positions, fills, settlements)
- Team and venue metadata
- API response validation

Key Components:
    ESPNDataValidator: Validates ESPN game state data
    KalshiDataValidator: Validates Kalshi API response data
    ValidationResult: Structured result object for validation outcomes
    ValidationLevel: Severity levels (ERROR, WARNING, INFO)
    ValidationIssue: Individual validation issue details

Usage:
    >>> from precog.validation import ESPNDataValidator, ValidationLevel
    >>> validator = ESPNDataValidator()
    >>> result = validator.validate_game_state(game_state_data)
    >>> if result.has_errors:
    ...     print(f"Errors: {result.errors}")

    >>> from precog.validation import KalshiDataValidator
    >>> validator = KalshiDataValidator()
    >>> result = validator.validate_market_data(market)
    >>> if result.has_errors:
    ...     print(f"Errors: {result.errors}")

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.9.md Phase 2
Related: Issue #186 (P2-004: Data Quality Validation)
Related: Issue #222 (Kalshi Validation Module)
"""

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationLevel,
    ValidationResult,
    create_validator,
)
from precog.validation.kalshi_validation import (
    KalshiDataValidator,
    ValidationIssue,
)
from precog.validation.kalshi_validation import (
    ValidationLevel as KalshiValidationLevel,
)
from precog.validation.kalshi_validation import (
    ValidationResult as KalshiValidationResult,
)

__all__ = [
    "ESPNDataValidator",
    "KalshiDataValidator",
    "KalshiValidationLevel",
    "KalshiValidationResult",
    "ValidationIssue",
    "ValidationLevel",
    "ValidationResult",
    "create_validator",
]
