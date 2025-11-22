"""Lookup Table Helper Functions.

This module provides helper functions for querying and validating against
lookup tables (strategy_types, model_classes).

Educational Note:
    Lookup tables replace CHECK constraints for business enums, providing:
    - No migrations needed to add new values (just INSERT)
    - Rich metadata storage (display_name, description, category)
    - UI-friendly queries for dropdowns
    - Flexible extensibility (add fields without schema changes)

References:
    - Migration 023: Creates strategy_types and model_classes lookup tables
    - ADR-093: Lookup Tables for Business Enums
    - REQ-DB-015: Strategy Type Lookup Table
    - REQ-DB-016: Model Class Lookup Table
    - docs/database/LOOKUP_TABLES_DESIGN.md: Complete design specification

Phase: 1.5 (Foundation Validation)
"""

from typing import Any

from precog.database.connection import fetch_all, fetch_one
from precog.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# STRATEGY TYPES QUERIES
# =============================================================================


def get_strategy_types(active_only: bool = True) -> list[dict[str, Any]]:
    """Get all strategy types with metadata.

    Args:
        active_only: If True, only return active strategy types (default: True)

    Returns:
        List of strategy type dicts with keys:
        - strategy_type_code: Code identifier ('value', 'arbitrage', etc.)
        - display_name: Human-readable name ('Value Trading', 'Arbitrage')
        - description: Full description text
        - category: Grouping category ('directional', 'arbitrage', 'risk_management')
        - display_order: UI sort order (lower = first)
        - is_active: Whether this type is currently active

    Educational Note:
        Use this for UI dropdowns, documentation generation, and validation.
        The display_order field controls how options appear in dropdowns.

    Example:
        >>> types = get_strategy_types()
        >>> for t in types:
        ...     print(f"{t['display_name']}: {t['description'][:50]}...")
        Value Trading: Exploit market mispricing by identifying edges...
        Arbitrage: Cross-platform arbitrage opportunities with...
    """
    where_clause = "WHERE is_active = TRUE" if active_only else ""
    query = f"""
        SELECT
            strategy_type_code,
            display_name,
            description,
            category,
            display_order,
            is_active,
            icon_name,
            help_text
        FROM strategy_types
        {where_clause}
        ORDER BY display_order
    """
    return fetch_all(query)


def get_strategy_types_by_category(active_only: bool = True) -> dict[str, list[dict[str, Any]]]:
    """Get strategy types grouped by category.

    Args:
        active_only: If True, only return active strategy types (default: True)

    Returns:
        Dict mapping category names to lists of strategy type dicts.
        Example: {'directional': [...], 'arbitrage': [...]}

    Educational Note:
        Useful for organized UI presentation with category headers.

    Example:
        >>> by_category = get_strategy_types_by_category()
        >>> for category, types in by_category.items():
        ...     print(f"\n{category.upper()}:")
        ...     for t in types:
        ...         print(f"  - {t['display_name']}")
        DIRECTIONAL:
          - Value Trading
          - Momentum Trading
        ARBITRAGE:
          - Arbitrage
    """
    types = get_strategy_types(active_only=active_only)
    by_category: dict[str, list[dict[str, Any]]] = {}

    for strategy_type in types:
        category = strategy_type["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(strategy_type)

    return by_category


def validate_strategy_type(strategy_type: str, active_only: bool = True) -> bool:
    """Check if strategy_type is valid and optionally active.

    Args:
        strategy_type: Strategy type code to validate ('value', 'arbitrage', etc.)
        active_only: If True, only validate against active types (default: True)

    Returns:
        True if valid (and active if active_only=True), False otherwise

    Educational Note:
        Use this for validation before INSERT to get better error messages
        than relying on FK constraint violation.

    Example:
        >>> validate_strategy_type('value')
        True
        >>> validate_strategy_type('invalid_type')
        False
    """
    where_clause = "AND is_active = TRUE" if active_only else ""
    query = f"""
        SELECT EXISTS(
            SELECT 1
            FROM strategy_types
            WHERE strategy_type_code = %s {where_clause}
        )
    """
    result = fetch_one(query, (strategy_type,))
    return bool(result["exists"]) if result else False


def get_valid_strategy_types(active_only: bool = True) -> list[str]:
    """Get list of valid strategy type codes.

    Args:
        active_only: If True, only return active codes (default: True)

    Returns:
        List of strategy type codes (e.g., ['value', 'arbitrage', 'momentum'])

    Educational Note:
        Use this for generating helpful error messages when validation fails.

    Example:
        >>> valid_types = get_valid_strategy_types()
        >>> if user_input not in valid_types:
        ...     raise ValueError(f"Invalid type. Valid types: {', '.join(valid_types)}")
    """
    types = get_strategy_types(active_only=active_only)
    return [t["strategy_type_code"] for t in types]


# =============================================================================
# MODEL CLASSES QUERIES
# =============================================================================


def get_model_classes(active_only: bool = True) -> list[dict[str, Any]]:
    """Get all model classes with metadata.

    Args:
        active_only: If True, only return active model classes (default: True)

    Returns:
        List of model class dicts with keys:
        - model_class_code: Code identifier ('elo', 'ensemble', etc.)
        - display_name: Human-readable name ('Elo Rating System', 'Ensemble Model')
        - description: Full description text
        - category: Grouping category ('statistical', 'machine_learning', 'hybrid', 'baseline')
        - complexity_level: Complexity indicator ('simple', 'moderate', 'advanced')
        - display_order: UI sort order (lower = first)
        - is_active: Whether this class is currently active

    Educational Note:
        Use this for UI dropdowns, model documentation, and complexity filtering.

    Example:
        >>> classes = get_model_classes()
        >>> simple_models = [c for c in classes if c['complexity_level'] == 'simple']
        >>> for m in simple_models:
        ...     print(f"{m['display_name']} ({m['category']})")
        Elo Rating System (statistical)
        Statistical Regression (statistical)
        Baseline Model (baseline)
    """
    where_clause = "WHERE is_active = TRUE" if active_only else ""
    query = f"""
        SELECT
            model_class_code,
            display_name,
            description,
            category,
            complexity_level,
            display_order,
            is_active,
            icon_name,
            help_text
        FROM model_classes
        {where_clause}
        ORDER BY display_order
    """
    return fetch_all(query)


def get_model_classes_by_category(active_only: bool = True) -> dict[str, list[dict[str, Any]]]:
    """Get model classes grouped by category.

    Args:
        active_only: If True, only return active model classes (default: True)

    Returns:
        Dict mapping category names to lists of model class dicts.
        Example: {'statistical': [...], 'machine_learning': [...]}

    Educational Note:
        Useful for organized UI presentation with category headers.

    Example:
        >>> by_category = get_model_classes_by_category()
        >>> for category, classes in by_category.items():
        ...     print(f"\n{category.upper()}:")
        ...     for c in classes:
        ...         print(f"  - {c['display_name']} [{c['complexity_level']}]")
        STATISTICAL:
          - Elo Rating System [simple]
          - Statistical Regression [simple]
    """
    classes = get_model_classes(active_only=active_only)
    by_category: dict[str, list[dict[str, Any]]] = {}

    for model_class in classes:
        category = model_class["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(model_class)

    return by_category


def get_model_classes_by_complexity(active_only: bool = True) -> dict[str, list[dict[str, Any]]]:
    """Get model classes grouped by complexity level.

    Args:
        active_only: If True, only return active model classes (default: True)

    Returns:
        Dict mapping complexity levels to lists of model class dicts.
        Example: {'simple': [...], 'moderate': [...], 'advanced': [...]}

    Educational Note:
        Useful for progressive disclosure in UI (show simple models first).

    Example:
        >>> by_complexity = get_model_classes_by_complexity()
        >>> print("Beginner-friendly models:")
        >>> for model in by_complexity['simple']:
        ...     print(f"  - {model['display_name']}")
        Beginner-friendly models:
          - Elo Rating System
          - Statistical Regression
          - Baseline Model
    """
    classes = get_model_classes(active_only=active_only)
    by_complexity: dict[str, list[dict[str, Any]]] = {}

    for model_class in classes:
        complexity = model_class["complexity_level"]
        if complexity not in by_complexity:
            by_complexity[complexity] = []
        by_complexity[complexity].append(model_class)

    return by_complexity


def validate_model_class(model_class: str, active_only: bool = True) -> bool:
    """Check if model_class is valid and optionally active.

    Args:
        model_class: Model class code to validate ('elo', 'ensemble', etc.)
        active_only: If True, only validate against active classes (default: True)

    Returns:
        True if valid (and active if active_only=True), False otherwise

    Educational Note:
        Use this for validation before INSERT to get better error messages
        than relying on FK constraint violation.

    Example:
        >>> validate_model_class('elo')
        True
        >>> validate_model_class('invalid_class')
        False
    """
    where_clause = "AND is_active = TRUE" if active_only else ""
    query = f"""
        SELECT EXISTS(
            SELECT 1
            FROM model_classes
            WHERE model_class_code = %s {where_clause}
        )
    """
    result = fetch_one(query, (model_class,))
    return bool(result["exists"]) if result else False


def get_valid_model_classes(active_only: bool = True) -> list[str]:
    """Get list of valid model class codes.

    Args:
        active_only: If True, only return active codes (default: True)

    Returns:
        List of model class codes (e.g., ['elo', 'ensemble', 'ml', ...])

    Educational Note:
        Use this for generating helpful error messages when validation fails.

    Example:
        >>> valid_classes = get_valid_model_classes()
        >>> if user_input not in valid_classes:
        ...     raise ValueError(f"Invalid class. Valid classes: {', '.join(valid_classes)}")
    """
    classes = get_model_classes(active_only=active_only)
    return [c["model_class_code"] for c in classes]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def add_strategy_type(
    code: str,
    display_name: str,
    description: str,
    category: str,
    display_order: int | None = None,
    icon_name: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    """Add new strategy type to lookup table (no migration required!).

    Args:
        code: Strategy type code (e.g., 'hedging', 'contrarian')
        display_name: Human-readable name (e.g., 'Hedging Strategy')
        description: Full description text
        category: Category ('directional', 'arbitrage', 'risk_management', 'event_driven')
        display_order: UI sort order (default: 999)
        icon_name: Icon identifier for UI (optional)
        help_text: Extended help for tooltips (optional)

    Returns:
        Dict with inserted row data

    Educational Note:
        This is the power of lookup tables - add new values without migrations!

    Example:
        >>> add_strategy_type(
        ...     code='hedging',
        ...     display_name='Hedging Strategy',
        ...     description='Risk management through offsetting positions',
        ...     category='risk_management',
        ...     display_order=50
        ... )
    """
    from precog.database.connection import get_cursor

    display_order = display_order if display_order is not None else 999

    query = """
        INSERT INTO strategy_types (
            strategy_type_code, display_name, description, category,
            display_order, icon_name, help_text
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING
            strategy_type_code, display_name, description, category,
            display_order, is_active, icon_name, help_text, created_at
    """

    with get_cursor(commit=True) as cur:
        cur.execute(
            query, (code, display_name, description, category, display_order, icon_name, help_text)
        )
        row = cur.fetchone()

        logger.info(f"Added strategy type: {code} ({display_name})")

        # Row is already a dict from RealDictCursor
        return dict(row) if row else {}


def add_model_class(
    code: str,
    display_name: str,
    description: str,
    category: str,
    complexity_level: str,
    display_order: int | None = None,
    icon_name: str | None = None,
    help_text: str | None = None,
) -> dict[str, Any]:
    """Add new model class to lookup table (no migration required!).

    Args:
        code: Model class code (e.g., 'xgboost', 'lstm')
        display_name: Human-readable name (e.g., 'XGBoost', 'LSTM Neural Network')
        description: Full description text
        category: Category ('statistical', 'machine_learning', 'hybrid', 'baseline')
        complexity_level: Complexity ('simple', 'moderate', 'advanced')
        display_order: UI sort order (default: 999)
        icon_name: Icon identifier for UI (optional)
        help_text: Extended help for tooltips (optional)

    Returns:
        Dict with inserted row data

    Educational Note:
        No migration needed! Just INSERT new model class and it's immediately available.

    Example:
        >>> add_model_class(
        ...     code='xgboost',
        ...     display_name='XGBoost',
        ...     description='Gradient boosting decision trees with regularization',
        ...     category='machine_learning',
        ...     complexity_level='advanced',
        ...     display_order=65
        ... )
    """
    from precog.database.connection import get_cursor

    display_order = display_order if display_order is not None else 999

    query = """
        INSERT INTO model_classes (
            model_class_code, display_name, description, category,
            complexity_level, display_order, icon_name, help_text
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            model_class_code, display_name, description, category,
            complexity_level, display_order, is_active, icon_name, help_text, created_at
    """

    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                code,
                display_name,
                description,
                category,
                complexity_level,
                display_order,
                icon_name,
                help_text,
            ),
        )
        row = cur.fetchone()

        logger.info(f"Added model class: {code} ({display_name})")

        # Row is already a dict from RealDictCursor
        return dict(row) if row else {}
