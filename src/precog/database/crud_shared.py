"""
Shared constants, helpers, and type aliases used across CRUD domain modules.

Extracted from crud_operations.py during Phase 1a domain split to avoid
circular imports and provide a single source of truth for cross-cutting
definitions.

Contents:
    - ExecutionEnvironment: Literal type alias for order execution contexts
    - SystemHealthComponent: Literal type alias for system health monitoring
    - VALID_SYSTEM_HEALTH_COMPONENTS: Runtime frozenset for O(1) validation
    - DecimalEncoder: JSON encoder that preserves Decimal precision
    - _convert_config_strings_to_decimal(): Config restoration helper
    - validate_decimal(): Runtime Decimal type enforcement
"""

import json
from decimal import Decimal
from typing import Any, Literal

# Type alias for execution environment - matches database ENUM (Migration 0008)
# - 'live': Production trading with Kalshi Production API (real money)
# - 'paper': Integration testing with Kalshi Demo/Sandbox API (no real money)
# - 'backtest': Historical data simulation (no API calls)
ExecutionEnvironment = Literal["live", "paper", "backtest"]

# App-layer allowlist for system_health.component (ADR-114, Migration 0043).
# The PostgreSQL CHECK constraint was dropped in migration 0043 so new data
# sources can be added here without a schema migration. Add new components
# to this Literal and to VALID_SYSTEM_HEALTH_COMPONENTS below.
#
# Tier A components (active data sources):
#   - 'kalshi_api':      Kalshi prediction market API
#   - 'espn_api':        ESPN sports data API
#   - 'database':        PostgreSQL database connection
# Infrastructure components:
#   - 'edge_detector':   Edge detection engine
#   - 'trading_engine':  Trade execution engine
#   - 'websocket':       WebSocket connections
# Planned Tier A components (not yet active):
#   - 'polymarket_api':  Polymarket prediction market API
SystemHealthComponent = Literal[
    "kalshi_api",
    "polymarket_api",
    "espn_api",
    "database",
    "edge_detector",
    "trading_engine",
    "websocket",
]

# Runtime set for O(1) validation in upsert_system_health.
# Must stay in sync with the SystemHealthComponent Literal above.
VALID_SYSTEM_HEALTH_COMPONENTS: frozenset[str] = frozenset(
    SystemHealthComponent.__args__  # type: ignore[attr-defined]
)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts Decimal to string.

    This encoder is required because Python's json module doesn't natively
    support Decimal serialization. We convert Decimal to string to preserve
    precision (Pattern 1: NEVER USE FLOAT).

    Educational Note:
        Why not convert to float? Because float introduces rounding errors!
        Example:
            Decimal("0.4975") -> float -> 0.49750000000000005 ❌ WRONG
            Decimal("0.4975") -> str -> "0.4975" ✅ CORRECT

    Example:
        >>> config = {"max_edge": Decimal("0.05"), "kelly_fraction": Decimal("0.10")}
        >>> json.dumps(config, cls=DecimalEncoder)
        '{"max_edge": "0.05", "kelly_fraction": "0.10"}'

    Reference:
        - Pattern 1 (Decimal Precision): docs/guides/DEVELOPMENT_PATTERNS_V1.2.md
        - ADR-002: Decimal precision for all financial calculations
    """

    def default(self, obj: Any) -> Any:
        """Convert Decimal to string, otherwise use default encoding.

        Args:
            obj: Object to encode

        Returns:
            String representation for Decimal, default encoding for others
        """
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def _convert_config_strings_to_decimal(config: dict[str, Any]) -> dict[str, Any]:
    """Convert string values to Decimal for known financial fields.

    When configs are stored as JSON in the database, Decimal values are
    serialized as strings. This helper converts them back to Decimal objects
    for fields that should use Decimal precision (Pattern 1).

    Educational Note:
        We only convert specific known fields (max_edge, kelly_fraction, etc.)
        rather than converting all numeric-looking strings, because some
        fields like 'min_lead' should remain as integers.

    Args:
        config: Strategy config dict (may have string Decimal values)

    Returns:
        Config dict with Decimal values restored

    Example:
        >>> config = {"max_edge": "0.05", "kelly_fraction": "0.10", "min_lead": 5}
        >>> _convert_config_strings_to_decimal(config)
        {"max_edge": Decimal("0.05"), "kelly_fraction": Decimal("0.10"), "min_lead": 5}

    Reference:
        - Pattern 1 (Decimal Precision): docs/guides/DEVELOPMENT_PATTERNS_V1.2.md
        - ADR-002: Decimal precision for all financial calculations
    """
    # Fields that should be Decimal (financial calculations)
    decimal_fields = {
        "max_edge",
        "min_edge",
        "kelly_fraction",
        "max_position_size",
        "max_exposure",
        "stop_loss_threshold",
        "profit_target",
        "trailing_stop_activation",
        "trailing_stop_distance",
    }

    result = config.copy()
    for field in decimal_fields:
        if field in result and isinstance(result[field], str):
            result[field] = Decimal(result[field])

    return result


# =============================================================================
# TYPE VALIDATION HELPERS
# =============================================================================


def validate_decimal(value: Any, param_name: str) -> Decimal:
    """
    Validate that value is a Decimal type (runtime type enforcement).

    Args:
        value: Value to validate
        param_name: Parameter name for error message

    Returns:
        The value if it's a Decimal

    Raises:
        TypeError: If value is not a Decimal

    Educational Note:
        Python type hints (e.g., `price: Decimal`) are annotations only.
        They provide IDE autocomplete and mypy static analysis, but do NOT
        enforce types at runtime.

        Without runtime validation:
        >>> create_market(yes_ask_price=0.5)  # Executes (float contamination!)

        With runtime validation:
        >>> create_market(yes_ask_price=0.5)  # TypeError: yes_ask_price must be Decimal

        Why this matters:
        - Prevents float contamination (0.5 != Decimal("0.5"))
        - Ensures sub-penny precision preserved (0.4975 stored exactly)
        - Catches type errors early (at function call, not database INSERT)

    Example:
        >>> price = validate_decimal(Decimal("0.5200"), "yes_ask_price")
        >>> # Returns Decimal("0.5200")

        >>> price = validate_decimal(0.5200, "yes_ask_price")
        >>> # TypeError: yes_ask_price must be Decimal, got float
        >>> #    Use Decimal("0.5200"), not 0.5200
    """
    if not isinstance(value, Decimal):
        raise TypeError(
            f"{param_name} must be Decimal, got {type(value).__name__}. "
            f"Use Decimal('{value}'), not {value} ({type(value).__name__}). "
            f"See Pattern 1 in CLAUDE.md for Decimal precision guidance."
        )
    return value
