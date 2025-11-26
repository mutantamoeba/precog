"""
Type definitions for Trading module responses.

Provides TypedDict definitions for all trading-related data structures
including strategy and position management responses.

All monetary and percentage fields use Decimal for precision (ADR-002).
All timestamps use ISO 8601 string format for consistency.

Design Pattern:
    TypedDict provides compile-time type checking without runtime overhead.
    This is the standard pattern for API/database response types in Precog.
    See api_connectors/types.py for the same pattern with Kalshi API responses.
    See analytics/types.py for analytics-related TypedDict classes.

Why TypedDict over Pydantic:
    - Zero runtime overhead (type hints are ignored at runtime)
    - Simpler for read-only data structures
    - Better IDE autocomplete
    - Easier to maintain
    Pydantic may be used in Phase 5+ for validation-heavy use cases.

Reference: docs/guides/DEVELOPMENT_PATTERNS_V1.5.md Pattern 6 (TypedDict)
Related ADR: ADR-002 (Decimal Precision for Monetary Values)
Related ADR: ADR-050 (TypedDict for API Responses)
Related Issue: #103 (TypedDict for manager return types)

Created: 2025-11-25
Phase: 1.5 (Foundation Validation)
GitHub Issue: #103
"""

from decimal import Decimal
from typing import Any, Literal, TypedDict

# =============================================================================
# Strategy Types
# =============================================================================


class StrategyConfig(TypedDict, total=False):
    """Strategy configuration parameters (stored as JSONB).

    Educational Note:
        Strategy configs are IMMUTABLE after creation. This TypedDict
        documents the expected structure but actual configs may vary
        by strategy type. All numeric values should be Decimal, not float.

    Example:
        >>> config: StrategyConfig = {
        ...     "min_edge": Decimal("0.05"),
        ...     "max_spread": Decimal("0.08"),
        ...     "max_position_size": 10,
        ...     "cooldown_minutes": 30
        ... }
    """

    min_edge: Decimal  # Minimum edge required to enter position
    max_spread: Decimal  # Maximum bid-ask spread allowed
    max_position_size: int  # Maximum contracts per position
    cooldown_minutes: int  # Wait time between trades on same market
    # Additional fields can be added per strategy type


class StrategyResponse(TypedDict):
    """Response from strategy manager CRUD operations.

    Used by: StrategyManager.create_strategy(), get_strategy(), update_status(), update_metrics()
    Source: strategies table in database

    Example:
        >>> strategy = manager.create_strategy(...)
        >>> print(f"Created {strategy['strategy_name']} {strategy['strategy_version']}")
        Created halftime_entry v1.0

    References:
        - REQ-VER-001: Immutable Version Configs
        - REQ-VER-002: Semantic Versioning
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.10.md (strategies table)
    """

    strategy_id: int  # Primary key (surrogate)
    strategy_name: str  # Strategy identifier (e.g., 'halftime_entry')
    strategy_version: str  # Semantic version (e.g., 'v1.0', 'v1.1')
    strategy_type: str  # Type code from strategy_types lookup table
    domain: str | None  # Market domain ('nfl', 'ncaaf', etc.) or None for multi-domain
    config: dict[str, Any]  # Strategy parameters (IMMUTABLE, Decimal values)
    description: str | None  # Human-readable description
    status: Literal["draft", "testing", "active", "inactive", "deprecated"]

    # Performance metrics (MUTABLE)
    paper_roi: Decimal | None  # Paper trading ROI
    live_roi: Decimal | None  # Live trading ROI
    paper_trades_count: int | None  # Number of paper trades
    live_trades_count: int | None  # Number of live trades

    # Timestamps
    created_at: str  # ISO 8601 creation timestamp
    created_by: str | None  # Creator identifier
    notes: str | None  # Additional notes

    # Optional fields from list_strategies (not always present)
    activated_at: str | None  # When status changed to active
    deactivated_at: str | None  # When status changed to inactive
    updated_at: str | None  # Last modification timestamp


class StrategyListResponse(TypedDict):
    """Response from strategy manager list operations.

    Used by: StrategyManager.list_strategies(), get_strategies_by_name(), get_active_strategies()

    Educational Note:
        List operations return multiple StrategyResponse items.
        This wrapper type can be extended with pagination metadata if needed.
    """

    strategies: list[StrategyResponse]
    count: int  # Total number of strategies matching filters


# =============================================================================
# Position Types
# =============================================================================


class TrailingStopConfig(TypedDict):
    """Trailing stop configuration parameters.

    Educational Note:
        Trailing stops activate when profit reaches activation_threshold,
        then follow price up by initial_distance. As profit increases,
        the distance tightens (controlled by tightening_rate) but never
        below floor_distance.

    Example:
        >>> config: TrailingStopConfig = {
        ...     "activation_threshold": Decimal("0.15"),
        ...     "initial_distance": Decimal("0.05"),
        ...     "tightening_rate": Decimal("0.10"),
        ...     "floor_distance": Decimal("0.02")
        ... }

    References:
        - REQ-TRAIL-001: Dynamic Trailing Stops
        - docs/guides/TRAILING_STOP_GUIDE_V1.0.md
    """

    activation_threshold: Decimal  # Profit threshold to activate trailing
    initial_distance: Decimal  # Initial stop distance from highest price
    tightening_rate: Decimal  # Rate to tighten stop as profit increases (0-1)
    floor_distance: Decimal  # Minimum stop distance (prevents over-tightening)


class TrailingStopState(TypedDict):
    """Current state of trailing stop for a position.

    Educational Note:
        This tracks the current state of the trailing stop including
        whether it's activated, the highest price seen, and the current
        stop price level.

    Example:
        >>> state: TrailingStopState = {
        ...     "config": {...},
        ...     "activated": True,
        ...     "activation_price": Decimal("0.65"),
        ...     "current_stop_price": Decimal("0.60"),
        ...     "highest_price": Decimal("0.75")
        ... }
    """

    config: TrailingStopConfig  # Original configuration
    activated: bool  # Whether trailing stop is active
    activation_price: Decimal | None  # Price when activated (None if not activated)
    current_stop_price: Decimal | None  # Current stop price level
    highest_price: Decimal | None  # Highest price seen since activation


class PositionResponse(TypedDict):
    """Response from position manager CRUD operations.

    Used by: PositionManager.open_position(), update_position(), close_position()
    Source: positions table in database (SCD Type 2)

    Educational Note:
        Positions use SCD Type 2 versioning - each price update creates a NEW row.
        The 'id' field is the surrogate key (changes with each version).
        The 'position_id' field is the business key (stays constant).

        IMPORTANT: When updating positions, use the RETURNED 'id' for subsequent
        operations, as it points to the NEW version.

    Example:
        >>> position = manager.open_position(...)
        >>> print(f"Position {position['position_id']} opened at {position['entry_price']}")
        Position POS-123 opened at 0.4975

    References:
        - REQ-RISK-001: Position Entry Validation
        - ADR-015: SCD Type 2 for Position History
        - ADR-089: Dual-Key Schema Pattern
        - docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md
    """

    # Keys (SCD Type 2 dual-key pattern)
    id: int  # Surrogate key (changes with each version)
    position_id: str  # Business key (format: 'POS-{id}', stays constant)

    # Trade attribution
    market_id: str  # Market identifier
    strategy_id: int  # Strategy that generated signal
    model_id: int  # Model that calculated probability

    # Position details
    side: Literal["YES", "NO"]  # Position side
    quantity: int  # Number of contracts
    entry_price: Decimal  # Entry price (0.01-0.99)
    current_price: Decimal | None  # Current market price
    target_price: Decimal | None  # Profit target price
    stop_loss_price: Decimal | None  # Stop loss price

    # P&L
    unrealized_pnl: Decimal | None  # Current unrealized P&L
    realized_pnl: Decimal | None  # Realized P&L (set on close)

    # Status
    status: Literal["open", "closed"]  # Position status
    exit_price: Decimal | None  # Exit price (set on close)
    exit_reason: str | None  # Reason for exit ('profit_target', 'stop_loss', etc.)

    # Trailing stop (JSONB)
    trailing_stop_state: TrailingStopState | None  # Trailing stop configuration and state

    # Metadata (JSONB)
    position_metadata: dict[str, Any] | None  # Optional metadata (edges, probabilities)

    # SCD Type 2 tracking
    row_current_ind: bool  # TRUE for current version, FALSE for historical


class PositionListResponse(TypedDict):
    """Response from position manager list operations.

    Used by: PositionManager.get_open_positions()
    """

    positions: list[PositionResponse]
    count: int  # Total number of positions


class PnLCalculation(TypedDict):
    """Result of P&L calculation.

    Used by: PositionManager.calculate_position_pnl()

    Educational Note:
        P&L calculation depends on position side:
        - YES: profit when price goes UP (pnl = quantity * (current - entry))
        - NO: profit when price goes DOWN (pnl = quantity * (entry - current))
    """

    entry_price: Decimal
    current_price: Decimal
    quantity: int
    side: Literal["YES", "NO"]
    pnl: Decimal  # Calculated P&L


# =============================================================================
# Model Types (from analytics module, re-exported for convenience)
# =============================================================================


class ModelResponse(TypedDict):
    """Response from model manager CRUD operations.

    Used by: ModelManager.create_model(), get_model(), update_status(), update_metrics()
    Source: probability_models table in database

    Example:
        >>> model = manager.create_model(...)
        >>> print(f"Created {model['model_name']} {model['model_version']}")
        Created elo_nfl v1.0

    References:
        - REQ-VER-001: Immutable Version Configs
        - REQ-VER-002: Semantic Versioning
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.10.md (probability_models table)
    """

    model_id: int  # Primary key
    model_name: str  # Model identifier (e.g., 'elo_nfl')
    model_version: str  # Semantic version (e.g., 'v1.0')
    model_class: str  # Model class code from model_classes lookup table
    domain: str | None  # Market domain or None for multi-domain
    config: dict[str, Any]  # Model parameters (IMMUTABLE, Decimal values)
    description: str | None  # Human-readable description
    status: Literal["draft", "testing", "active", "deprecated"]

    # Validation metrics (MUTABLE)
    validation_calibration: Decimal | None  # Brier score / log loss
    validation_accuracy: Decimal | None  # Overall accuracy
    validation_sample_size: int | None  # Number of predictions

    # Timestamps
    created_at: str  # ISO 8601 creation timestamp
    created_by: str | None  # Creator identifier
    notes: str | None  # Additional notes


class ModelListResponse(TypedDict):
    """Response from model manager list operations.

    Used by: ModelManager.list_models(), get_models_by_name(), get_active_models()
    """

    models: list[ModelResponse]
    count: int  # Total number of models


# =============================================================================
# Error Response Types
# =============================================================================


class ManagerError(TypedDict):
    """Standard error response from manager operations.

    Educational Note:
        All manager operations that fail should return consistent error
        information for logging and user feedback.
    """

    operation: str  # Operation that failed (e.g., 'create_strategy', 'update_position')
    error_type: str  # Error class name (e.g., 'ImmutabilityError', 'InvalidStatusTransitionError')
    message: str  # Human-readable error message
    context: dict[str, Any] | None  # Additional context (IDs, values that caused error)
