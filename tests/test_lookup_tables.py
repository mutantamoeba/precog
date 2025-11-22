"""Tests for lookup tables (strategy_types, model_classes).

This module tests the lookup table infrastructure created in Migration 023,
including query functions, validation, grouping, and FK constraint enforcement.

Educational Note:
    Lookup tables replace CHECK constraints for business enums, providing:
    - No migrations needed to add new values (just INSERT)
    - Rich metadata storage (display_name, description, category)
    - UI-friendly queries for dropdowns
    - Flexible extensibility

References:
    - Migration 023: Creates strategy_types and model_classes lookup tables
    - docs/database/LOOKUP_TABLES_DESIGN.md: Complete design specification
    - ADR-093: Lookup Tables for Business Enums (to be created)
    - REQ-DB-015: Strategy Type Lookup Table (to be created)
    - REQ-DB-016: Model Class Lookup Table (to be created)

Phase: 1.5 (Foundation Validation)
"""

import psycopg2
import pytest

from precog.analytics.model_manager import ModelManager
from precog.database.lookup_helpers import (
    add_model_class,
    add_strategy_type,
    get_model_classes,
    get_model_classes_by_category,
    get_model_classes_by_complexity,
    get_strategy_types,
    get_strategy_types_by_category,
    get_valid_model_classes,
    get_valid_strategy_types,
    validate_model_class,
    validate_strategy_type,
)
from precog.trading.strategy_manager import StrategyManager

# =============================================================================
# LOOKUP TABLE VERIFICATION TESTS
# =============================================================================


def test_strategy_types_table_contains_all_initial_values():
    """Verify all 4 initial strategy types exist in correct order.

    Educational Note:
        Migration 023 seeds 4 initial strategy types:
        - value (directional)
        - arbitrage (arbitrage)
        - momentum (directional)
        - mean_reversion (directional)

    References:
        - Migration 023: Initial seed data
        - LOOKUP_TABLES_DESIGN.md Section 3: Migration Plan
    """
    types = get_strategy_types(active_only=False)
    codes = [t["strategy_type_code"] for t in types]

    assert codes == ["value", "arbitrage", "momentum", "mean_reversion"]

    # Verify all are active by default
    for strategy_type in types:
        assert strategy_type["is_active"] is True


def test_model_classes_table_contains_all_initial_values():
    """Verify all 7 initial model classes exist in correct order.

    Educational Note:
        Migration 023 seeds 7 initial model classes:
        - elo (statistical, simple)
        - ensemble (hybrid, moderate)
        - ml (machine_learning, moderate)
        - hybrid (hybrid, moderate)
        - regression (statistical, simple)
        - neural_net (machine_learning, advanced)
        - baseline (baseline, simple)

    References:
        - Migration 023: Initial seed data
        - LOOKUP_TABLES_DESIGN.md Section 3: Migration Plan
    """
    classes = get_model_classes(active_only=False)
    codes = [c["model_class_code"] for c in classes]

    assert codes == ["elo", "ensemble", "ml", "hybrid", "regression", "neural_net", "baseline"]

    # Verify all are active by default
    for model_class in classes:
        assert model_class["is_active"] is True


def test_strategy_types_have_required_metadata():
    """Verify strategy types have all required metadata fields.

    Educational Note:
        Lookup tables store rich metadata beyond just the code value.
        This enables UI-friendly dropdowns with descriptions and categories.

    References:
        - LOOKUP_TABLES_DESIGN.md Section 2.1: schema design
    """
    types = get_strategy_types()

    assert len(types) == 4

    for strategy_type in types:
        # Required fields
        assert "strategy_type_code" in strategy_type
        assert "display_name" in strategy_type
        assert "description" in strategy_type
        assert "category" in strategy_type
        assert "display_order" in strategy_type
        assert "is_active" in strategy_type

        # Verify types
        assert isinstance(strategy_type["strategy_type_code"], str)
        assert isinstance(strategy_type["display_name"], str)
        assert isinstance(strategy_type["description"], str)
        assert isinstance(strategy_type["category"], str)
        assert isinstance(strategy_type["display_order"], int)
        assert isinstance(strategy_type["is_active"], bool)


def test_model_classes_have_required_metadata():
    """Verify model classes have all required metadata fields including complexity_level.

    Educational Note:
        Model classes include complexity_level ('simple', 'moderate', 'advanced')
        for progressive disclosure in UI (show simple models first).

    References:
        - LOOKUP_TABLES_DESIGN.md Section 2.2: schema design
    """
    classes = get_model_classes()

    assert len(classes) == 7

    for model_class in classes:
        # Required fields
        assert "model_class_code" in model_class
        assert "display_name" in model_class
        assert "description" in model_class
        assert "category" in model_class
        assert "complexity_level" in model_class
        assert "display_order" in model_class
        assert "is_active" in model_class

        # Verify types
        assert isinstance(model_class["model_class_code"], str)
        assert isinstance(model_class["display_name"], str)
        assert isinstance(model_class["description"], str)
        assert isinstance(model_class["category"], str)
        assert isinstance(model_class["complexity_level"], str)
        assert isinstance(model_class["display_order"], int)
        assert isinstance(model_class["is_active"], bool)


# =============================================================================
# QUERY FUNCTION TESTS
# =============================================================================


def test_get_strategy_types_returns_active_only_by_default():
    """Verify get_strategy_types returns only active types by default.

    Educational Note:
        Active-only filtering allows deprecating strategy types without deletion.
        Disabled types remain in database for historical reference.
    """
    types = get_strategy_types(active_only=True)

    # All 4 initial types are active
    assert len(types) == 4

    for strategy_type in types:
        assert strategy_type["is_active"] is True


def test_get_strategy_types_can_return_inactive():
    """Verify get_strategy_types can return all types including inactive."""
    types = get_strategy_types(active_only=False)

    # Should return all types (currently all 4 are active)
    assert len(types) == 4


def test_get_model_classes_returns_active_only_by_default():
    """Verify get_model_classes returns only active classes by default."""
    classes = get_model_classes(active_only=True)

    # All 7 initial classes are active
    assert len(classes) == 7

    for model_class in classes:
        assert model_class["is_active"] is True


def test_get_model_classes_can_return_inactive():
    """Verify get_model_classes can return all classes including inactive."""
    classes = get_model_classes(active_only=False)

    # Should return all classes (currently all 7 are active)
    assert len(classes) == 7


# =============================================================================
# GROUPING FUNCTION TESTS
# =============================================================================


def test_get_strategy_types_by_category():
    """Verify grouping strategy types by category.

    Educational Note:
        Category grouping enables organized UI presentation with category headers.
        Example UI: "Directional Strategies", "Arbitrage Strategies", etc.

    References:
        - LOOKUP_TABLES_DESIGN.md Section 5: UI Integration Examples
    """
    by_category = get_strategy_types_by_category()

    # Should have 2 categories: directional, arbitrage
    assert "directional" in by_category
    assert "arbitrage" in by_category

    # Directional should have 3 strategies: value, momentum, mean_reversion
    directional = by_category["directional"]
    directional_codes = [s["strategy_type_code"] for s in directional]
    assert set(directional_codes) == {"value", "momentum", "mean_reversion"}

    # Arbitrage should have 1 strategy: arbitrage
    arbitrage = by_category["arbitrage"]
    assert len(arbitrage) == 1
    assert arbitrage[0]["strategy_type_code"] == "arbitrage"


def test_get_model_classes_by_category():
    """Verify grouping model classes by category.

    Educational Note:
        Model categories: statistical, machine_learning, hybrid, baseline.
        Enables organized presentation of different modeling approaches.
    """
    by_category = get_model_classes_by_category()

    # Should have 4 categories
    assert "statistical" in by_category
    assert "machine_learning" in by_category
    assert "hybrid" in by_category
    assert "baseline" in by_category

    # Statistical: elo, regression
    statistical = by_category["statistical"]
    statistical_codes = [m["model_class_code"] for m in statistical]
    assert set(statistical_codes) == {"elo", "regression"}

    # Machine learning: ml, neural_net
    ml = by_category["machine_learning"]
    ml_codes = [m["model_class_code"] for m in ml]
    assert set(ml_codes) == {"ml", "neural_net"}

    # Hybrid: ensemble, hybrid
    hybrid = by_category["hybrid"]
    hybrid_codes = [m["model_class_code"] for m in hybrid]
    assert set(hybrid_codes) == {"ensemble", "hybrid"}

    # Baseline: baseline
    baseline = by_category["baseline"]
    assert len(baseline) == 1
    assert baseline[0]["model_class_code"] == "baseline"


def test_get_model_classes_by_complexity():
    """Verify grouping model classes by complexity level.

    Educational Note:
        Complexity levels: simple, moderate, advanced.
        Enables progressive disclosure in UI (show simple models first).
    """
    by_complexity = get_model_classes_by_complexity()

    # Should have 3 complexity levels
    assert "simple" in by_complexity
    assert "moderate" in by_complexity
    assert "advanced" in by_complexity

    # Simple: elo, regression, baseline
    simple = by_complexity["simple"]
    simple_codes = [m["model_class_code"] for m in simple]
    assert set(simple_codes) == {"elo", "regression", "baseline"}

    # Moderate: ensemble, ml, hybrid
    moderate = by_complexity["moderate"]
    moderate_codes = [m["model_class_code"] for m in moderate]
    assert set(moderate_codes) == {"ensemble", "ml", "hybrid"}

    # Advanced: neural_net
    advanced = by_complexity["advanced"]
    assert len(advanced) == 1
    assert advanced[0]["model_class_code"] == "neural_net"


# =============================================================================
# VALIDATION FUNCTION TESTS
# =============================================================================


def test_validate_strategy_type_with_valid_codes():
    """Verify validation accepts all valid strategy type codes."""
    assert validate_strategy_type("value") is True
    assert validate_strategy_type("arbitrage") is True
    assert validate_strategy_type("momentum") is True
    assert validate_strategy_type("mean_reversion") is True


def test_validate_strategy_type_with_invalid_code():
    """Verify validation rejects invalid strategy type codes."""
    assert validate_strategy_type("invalid_type") is False
    assert validate_strategy_type("hedging") is False  # Not seeded yet
    assert validate_strategy_type("") is False
    assert validate_strategy_type("VALUE") is False  # Case sensitive


def test_validate_model_class_with_valid_codes():
    """Verify validation accepts all valid model class codes."""
    assert validate_model_class("elo") is True
    assert validate_model_class("ensemble") is True
    assert validate_model_class("ml") is True
    assert validate_model_class("hybrid") is True
    assert validate_model_class("regression") is True
    assert validate_model_class("neural_net") is True
    assert validate_model_class("baseline") is True


def test_validate_model_class_with_invalid_code():
    """Verify validation rejects invalid model class codes."""
    assert validate_model_class("invalid_class") is False
    assert validate_model_class("xgboost") is False  # Not seeded yet
    assert validate_model_class("") is False
    assert validate_model_class("ELO") is False  # Case sensitive


def test_get_valid_strategy_types():
    """Verify helper returns list of valid strategy type codes.

    Educational Note:
        Useful for generating helpful error messages when validation fails.
        Example: "Invalid type. Valid types: value, arbitrage, momentum, mean_reversion"
    """
    valid_types = get_valid_strategy_types()

    assert isinstance(valid_types, list)
    assert len(valid_types) == 4
    assert set(valid_types) == {"value", "arbitrage", "momentum", "mean_reversion"}


def test_get_valid_model_classes():
    """Verify helper returns list of valid model class codes.

    Educational Note:
        Useful for generating helpful error messages when validation fails.
    """
    valid_classes = get_valid_model_classes()

    assert isinstance(valid_classes, list)
    assert len(valid_classes) == 7
    assert set(valid_classes) == {
        "elo",
        "ensemble",
        "ml",
        "hybrid",
        "regression",
        "neural_net",
        "baseline",
    }


# =============================================================================
# FOREIGN KEY CONSTRAINT ENFORCEMENT TESTS
# =============================================================================


def test_invalid_strategy_type_raises_foreign_key_error():
    """Verify FK constraint prevents invalid strategy_type in strategies table.

    Educational Note:
        This is the power of lookup tables - FK constraint provides better
        error messages than CHECK constraint ("violates foreign key constraint"
        includes the referenced table name).

    References:
        - Migration 023: Adds FK constraint fk_strategies_strategy_type
        - LOOKUP_TABLES_DESIGN.md Section 8: Testing Requirements
    """
    manager = StrategyManager()

    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        manager.create_strategy(
            strategy_name="test_invalid_type",
            strategy_version="v1.0",
            strategy_type="invalid_type",  # ← Not in lookup table
            domain="nfl",
            config={"test": True},
        )


def test_invalid_model_class_raises_foreign_key_error():
    """Verify FK constraint prevents invalid model_class in probability_models table.

    Educational Note:
        FK constraint validates model_class against model_classes lookup table.

    References:
        - Migration 023: Adds FK constraint fk_probability_models_model_class
    """
    manager = ModelManager()

    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        manager.create_model(
            model_name="test_invalid_class",
            model_version="v1.0",
            model_class="invalid_class",  # ← Not in lookup table
            domain="nfl",
            config={"test": True},
        )


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================


def test_add_strategy_type(db_cleanup):
    """Verify adding new strategy type without migration.

    Educational Note:
        This is the PRIMARY BENEFIT of lookup tables - add new enum values
        via INSERT without schema migrations!

    References:
        - LOOKUP_TABLES_DESIGN.md Section 4: Future Extensibility Examples
    """
    # Add new strategy type
    result = add_strategy_type(
        code="hedging",
        display_name="Hedging Strategy",
        description="Risk management through offsetting positions",
        category="risk_management",
        display_order=50,
    )

    # Verify returned data
    assert result["strategy_type_code"] == "hedging"
    assert result["display_name"] == "Hedging Strategy"
    assert result["category"] == "risk_management"
    assert result["is_active"] is True

    # Verify validation now accepts new type
    assert validate_strategy_type("hedging") is True

    # Verify it appears in query results
    types = get_strategy_types()
    hedging = next((t for t in types if t["strategy_type_code"] == "hedging"), None)
    assert hedging is not None


def test_add_model_class(db_cleanup):
    """Verify adding new model class without migration.

    Educational Note:
        No migration needed! Just INSERT new model class and it's immediately
        available for use in probability_models table.
    """
    # Add new model class
    result = add_model_class(
        code="xgboost",
        display_name="XGBoost",
        description="Gradient boosting decision trees with regularization",
        category="machine_learning",
        complexity_level="advanced",
        display_order=65,
    )

    # Verify returned data
    assert result["model_class_code"] == "xgboost"
    assert result["display_name"] == "XGBoost"
    assert result["category"] == "machine_learning"
    assert result["complexity_level"] == "advanced"
    assert result["is_active"] is True

    # Verify validation now accepts new class
    assert validate_model_class("xgboost") is True

    # Verify it appears in query results
    classes = get_model_classes()
    xgboost = next((c for c in classes if c["model_class_code"] == "xgboost"), None)
    assert xgboost is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_create_strategy_with_all_valid_types():
    """Test creating strategies with each valid strategy_type.

    Educational Note:
        Verifies that FK constraint accepts all seeded strategy types.
        This is a smoke test for the migration and lookup table setup.

    References:
        - LOOKUP_TABLES_DESIGN.md Section 8.2: Integration Tests
    """
    manager = StrategyManager()

    # Clean up any existing test strategies first
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM strategies WHERE strategy_name LIKE 'test_%'")

    for strategy_type in ["value", "arbitrage", "momentum", "mean_reversion"]:
        strategy = manager.create_strategy(
            strategy_name=f"test_{strategy_type}",
            strategy_version="v1.0",
            strategy_type=strategy_type,
            domain="nfl",
            config={"test": True},
        )
        assert strategy["strategy_type"] == strategy_type
        assert strategy["domain"] == "nfl"


def test_create_model_with_all_valid_classes():
    """Test creating models with each valid model_class.

    Educational Note:
        Verifies that FK constraint accepts all seeded model classes.
    """
    manager = ModelManager()

    # Clean up any existing test models first
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM probability_models WHERE model_name LIKE 'test_%'")

    for model_class in ["elo", "ensemble", "ml", "hybrid", "regression", "neural_net", "baseline"]:
        model = manager.create_model(
            model_name=f"test_{model_class}",
            model_version="v1.0",
            model_class=model_class,
            domain="nfl",
            config={"test": True},
        )
        assert model["model_class"] == model_class
        assert model["domain"] == "nfl"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def db_cleanup(request):
    """Clean up test data added to lookup tables.

    Educational Note:
        Lookup tables should remain clean between tests. This fixture
        removes any test data added during test execution.

    Yields:
        None

    Cleanup:
        Deletes strategy types with code starting with 'test_' or 'hedging'
        Deletes model classes with code starting with 'test_' or 'xgboost'
    """
    yield

    # Cleanup after test
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cur:
        # Delete test strategy types
        cur.execute(
            "DELETE FROM strategy_types WHERE strategy_type_code LIKE 'test_%' OR strategy_type_code = 'hedging'"
        )

        # Delete test model classes
        cur.execute(
            "DELETE FROM model_classes WHERE model_class_code LIKE 'test_%' OR model_class_code = 'xgboost'"
        )
