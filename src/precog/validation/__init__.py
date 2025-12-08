"""
Validation module for Precog data quality checks.

This module provides validation utilities to ensure data quality for:
- ESPN game state data (scores, clocks, situations)
- Team and venue metadata
- API response validation

Key Components:
    ESPNDataValidator: Validates ESPN game state data
    ValidationResult: Structured result object for validation outcomes
    ValidationLevel: Severity levels (ERROR, WARNING, INFO)

Usage:
    >>> from precog.validation import ESPNDataValidator, ValidationLevel
    >>> validator = ESPNDataValidator()
    >>> result = validator.validate_game_state(game_state_data)
    >>> if result.has_errors:
    ...     print(f"Errors: {result.errors}")

Reference: docs/foundation/DEVELOPMENT_PHASES_V1.9.md Phase 2
Related: Issue #186 (P2-004: Data Quality Validation)
"""

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationLevel,
    ValidationResult,
    create_validator,
)

__all__ = [
    "ESPNDataValidator",
    "ValidationLevel",
    "ValidationResult",
    "create_validator",
]
