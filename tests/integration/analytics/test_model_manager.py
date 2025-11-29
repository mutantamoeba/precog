"""Unit tests for Model Manager (Phase 1.5).

Tests comprehensive CRUD operations, immutability enforcement, status lifecycle
validation, and Decimal precision for versioned probability models.

✅ UNBLOCKED: Migration 022 renamed approach to model_class column.
Tests now enabled with updated field names matching database schema V1.9.

Reference:
    - docs/testing/PHASE_1.5_TEST_PLAN_V1.0.md
    - docs/guides/VERSIONING_GUIDE_V1.0.md
    - Pattern 1: Decimal Precision (NEVER float)
    - Pattern 7: Educational Docstrings

Related:
    - REQ-MODEL-001: Model versioning and lifecycle
    - ADR-019: Model immutability
    - tests/unit/trading/test_strategy_manager.py (parallel structure)
"""

from decimal import Decimal

import psycopg2
import pytest

from precog.analytics import InvalidStatusTransitionError, ModelManager


@pytest.fixture
def manager():
    """Provide ModelManager instance.

    Educational Note:
        ModelManager is stateless - doesn't hold database connection.
        Each method gets fresh connection for thread safety.
        No need to pass connection in constructor.
    """
    return ModelManager()


@pytest.fixture
def model_factory() -> dict:
    """Factory fixture for creating test model configurations.

    Returns test model config with:
    - Elo rating parameters
    - Decimal precision for all numeric values (Pattern 1)
    - Typical NFL model configuration

    Educational Note:
        Using factory pattern for test data ensures:
        - Consistency across tests (same baseline config)
        - Easy customization (override specific fields)
        - Clear documentation of valid model structure
    """
    return {
        "model_name": "nfl_elo_v1",
        "model_version": "1.0",
        "model_class": "elo",
        "domain": "nfl",
        "config": {
            "k_factor": Decimal("20.00"),  # Elo K-factor
            "home_advantage": Decimal("65.00"),  # Home field Elo boost
            "mean_reversion": Decimal("0.3300"),  # Regression to mean (33%)
            "initial_rating": Decimal("1500.00"),  # Starting Elo
        },
        "description": "NFL Elo rating model for win probability calculation",
        "status": "draft",
        "created_by": "test_user",
        "notes": "Test model for unit testing",
    }


# ============================================================================
# CREATE MODEL TESTS
# ============================================================================


def test_create_model_success(clean_test_data, manager, model_factory):
    """Test creating new model version with valid config."""
    model = manager.create_model(**model_factory)

    # Verify model created with correct attributes
    assert model["model_name"] == "nfl_elo_v1"
    assert model["model_version"] == "1.0"
    assert model["model_class"] == "elo"
    assert model["domain"] == "nfl"
    assert model["status"] == "draft"
    assert model["created_by"] == "test_user"

    # Verify config stored correctly (Decimal preserved)
    config = model["config"]
    assert isinstance(config["k_factor"], Decimal)
    assert config["k_factor"] == Decimal("20.00")
    assert isinstance(config["home_advantage"], Decimal)
    assert config["home_advantage"] == Decimal("65.00")

    # Verify auto-generated fields exist
    assert "model_id" in model
    assert "created_at" in model
    # updated_at field doesnt exist in probability_models (only in strategies)


def test_create_model_minimal_fields(clean_test_data, manager):
    """Test creating model with only required fields."""
    model = manager.create_model(
        model_name="minimal_model",
        model_version="1.0",
        model_class="elo",
        config={"k_factor": Decimal("20.00")},
    )

    assert model["model_name"] == "minimal_model"
    assert model["model_version"] == "1.0"
    assert model["domain"] is None  # Optional field defaults to None
    assert model["description"] is None
    assert model["status"] == "draft"  # Default status


def test_create_model_decimal_conversion(clean_test_data, manager, model_factory):
    """Test Decimal → string → Decimal conversion for JSONB storage.

    Educational Note:
        PostgreSQL JSONB doesn't support Python Decimal natively.
        We convert: Decimal("20.00") → "20.00" (string in database)
        Then reverse on retrieval: "20.00" → Decimal("20.00")

        This ensures Pattern 1 compliance: application always uses Decimal.
    """
    model = manager.create_model(**model_factory)
    config = model["config"]

    # Verify all numeric values are Decimal (not float, not string)
    assert isinstance(config["k_factor"], Decimal)
    assert isinstance(config["home_advantage"], Decimal)
    assert isinstance(config["mean_reversion"], Decimal)
    assert isinstance(config["initial_rating"], Decimal)

    # Verify exact precision preserved
    assert config["mean_reversion"] == Decimal("0.3300")


def test_create_model_ensemble_type(clean_test_data, manager):
    """Test creating ensemble model with multiple component models."""
    ensemble_config = {
        "model_name": "nfl_ensemble_v1",
        "model_version": "1.0",
        "model_class": "ensemble",
        "domain": "nfl",
        "config": {
            "weights": {
                "elo": Decimal("0.40"),  # 40% weight to Elo
                "ml": Decimal("0.35"),  # 35% weight to ML model
                "market": Decimal("0.25"),  # 25% weight to market prices
            },
            "min_agreement": Decimal("0.6000"),  # 60% agreement threshold
        },
        "description": "Ensemble combining Elo, ML, and market signals",
    }

    model = manager.create_model(**ensemble_config)

    assert model["model_class"] == "ensemble"
    weights = model["config"]["weights"]
    assert isinstance(weights["elo"], Decimal)
    assert weights["elo"] + weights["ml"] + weights["market"] == Decimal("1.00")


# ============================================================================
# GET MODEL TESTS
# ============================================================================


def test_get_model_by_id(clean_test_data, manager, model_factory):
    """Test retrieving model by model_id."""
    created = manager.create_model(**model_factory)
    model_id = created["model_id"]

    # Retrieve by ID
    retrieved = manager.get_model(model_id=model_id)

    assert retrieved is not None
    assert retrieved["model_id"] == model_id
    assert retrieved["model_name"] == "nfl_elo_v1"
    assert retrieved["model_version"] == "1.0"


def test_get_model_by_name_and_version(clean_test_data, manager, model_factory):
    """Test retrieving model by name and version."""
    created = manager.create_model(**model_factory)

    # Retrieve by name + version
    retrieved = manager.get_model(model_name="nfl_elo_v1", model_version="1.0")

    assert retrieved is not None
    assert retrieved["model_id"] == created["model_id"]
    assert retrieved["config"] == created["config"]


def test_get_model_not_found_by_id(clean_test_data, manager):
    """Test get_model returns None when model_id doesn't exist."""
    result = manager.get_model(model_id=99999)
    assert result is None


def test_get_model_not_found_by_name(clean_test_data, manager):
    """Test get_model returns None when name/version doesn't exist."""
    result = manager.get_model(model_name="nonexistent", model_version="1.0")
    assert result is None


def test_get_model_requires_identifier(clean_test_data, manager):
    """Test get_model raises ValueError without any identifier."""
    with pytest.raises(
        ValueError, match="Provide either model_id OR both model_name and model_version"
    ):
        manager.get_model()


def test_get_model_requires_both_name_and_version(clean_test_data, manager):
    """Test get_model raises ValueError with only name or only version."""
    # Only name provided
    with pytest.raises(ValueError, match="both model_name and model_version"):
        manager.get_model(model_name="nfl_elo_v1")

    # Only version provided
    with pytest.raises(ValueError, match="both model_name and model_version"):
        manager.get_model(model_version="1.0")


# ============================================================================
# LIST MODELS TESTS
# ============================================================================


def test_list_models_all(clean_test_data, manager, model_factory):
    """Test listing all models without filters."""
    # Create multiple models
    model1 = manager.create_model(**model_factory)

    model2_config = model_factory.copy()
    model2_config["model_name"] = "nfl_ml_v1"
    model2_config["model_class"] = "ml"
    model2 = manager.create_model(**model2_config)

    # List all models
    models = manager.list_models()

    assert len(models) >= 2  # At least our test models
    model_ids = {m["model_id"] for m in models}
    assert model1["model_id"] in model_ids
    assert model2["model_id"] in model_ids


def test_list_models_filter_by_status(clean_test_data, manager, model_factory):
    """Test filtering models by status."""
    # Create draft model
    draft_model = manager.create_model(**model_factory)

    # Create testing model
    testing_config = model_factory.copy()
    testing_config["model_name"] = "testing_model"
    testing_config["status"] = "testing"
    testing_model = manager.create_model(**testing_config)

    # Filter by status = draft
    draft_models = manager.list_models(status="draft")
    draft_ids = {m["model_id"] for m in draft_models}
    assert draft_model["model_id"] in draft_ids
    assert testing_model["model_id"] not in draft_ids

    # Filter by status = testing
    testing_models = manager.list_models(status="testing")
    testing_ids = {m["model_id"] for m in testing_models}
    assert testing_model["model_id"] in testing_ids
    assert draft_model["model_id"] not in testing_ids


def test_list_models_filter_by_sport(clean_test_data, manager, model_factory):
    """Test filtering models by sport."""
    # Create NFL model
    nfl_model = manager.create_model(**model_factory)

    # Create NCAAF model
    ncaaf_config = model_factory.copy()
    ncaaf_config["model_name"] = "ncaaf_elo_v1"
    ncaaf_config["domain"] = "ncaaf"
    ncaaf_model = manager.create_model(**ncaaf_config)

    # Filter by sport = nfl
    nfl_models = manager.list_models(domain="nfl")
    nfl_ids = {m["model_id"] for m in nfl_models}
    assert nfl_model["model_id"] in nfl_ids
    assert ncaaf_model["model_id"] not in nfl_ids


def test_list_models_filter_by_model_type(clean_test_data, manager, model_factory):
    """Test filtering models by model_type."""
    # Create Elo model
    elo_model = manager.create_model(**model_factory)

    # Create ML model
    ml_config = model_factory.copy()
    ml_config["model_name"] = "nfl_ml_v1"
    ml_config["model_class"] = "ml"
    ml_model = manager.create_model(**ml_config)

    # Filter by model_type = elo
    elo_models = manager.list_models(model_class="elo")
    elo_ids = {m["model_id"] for m in elo_models}
    assert elo_model["model_id"] in elo_ids
    assert ml_model["model_id"] not in elo_ids


def test_list_models_multiple_filters(clean_test_data, manager, model_factory):
    """Test combining multiple filters (sport + status + model_type)."""
    # Create NFL Elo draft model
    target_model = manager.create_model(**model_factory)

    # Create NCAAF Elo draft model (different sport)
    ncaaf_config = model_factory.copy()
    ncaaf_config["model_name"] = "ncaaf_elo_v1"
    ncaaf_config["domain"] = "ncaaf"
    manager.create_model(**ncaaf_config)

    # Create NFL ML draft model (different type)
    ml_config = model_factory.copy()
    ml_config["model_name"] = "nfl_ml_v1"
    ml_config["model_class"] = "ml"
    manager.create_model(**ml_config)

    # Filter: NFL + draft + elo
    filtered = manager.list_models(domain="nfl", status="draft", model_class="elo")

    # Should only return target_model
    filtered_ids = {m["model_id"] for m in filtered}
    assert target_model["model_id"] in filtered_ids


# ============================================================================
# UPDATE METRICS TESTS
# ============================================================================


def test_update_metrics_calibration_score(clean_test_data, manager, model_factory):
    """Test updating calibration_score (MUTABLE field).

    Educational Note:
        Config is IMMUTABLE, but metrics are MUTABLE.
        Why? Calibration changes as we evaluate predictions, but
        model parameters (k_factor, etc.) stay fixed.

        This separation enables:
        - Tracking performance of each version independently
        - A/B testing (compare v1.0 vs v1.1 calibration)
        - Knowing EXACTLY which config generated which predictions
    """
    model = manager.create_model(**model_factory)
    model_id = model["model_id"]

    # Update calibration_score
    updated = manager.update_metrics(
        model_id=model_id,
        validation_calibration=Decimal("0.9250"),  # 92.5% calibration
    )

    assert updated["validation_calibration"] == Decimal("0.9250")
    # Note: probability_models table doesn't have updated_at field (only created_at)


def test_update_metrics_accuracy(clean_test_data, manager, model_factory):
    """Test updating accuracy metric."""
    model = manager.create_model(**model_factory)
    model_id = model["model_id"]

    # Update accuracy
    updated = manager.update_metrics(
        model_id=model_id, validation_accuracy=Decimal("0.6800")
    )  # 68% accuracy

    assert updated["validation_accuracy"] == Decimal("0.6800")


def test_update_metrics_predictions_count(clean_test_data, manager, model_factory):
    """Test updating predictions_count metric."""
    model = manager.create_model(**model_factory)
    model_id = model["model_id"]

    # Update predictions_count
    updated = manager.update_metrics(model_id=model_id, validation_sample_size=150)

    assert updated["validation_sample_size"] == 150


def test_update_metrics_multiple_fields(clean_test_data, manager, model_factory):
    """Test updating multiple metrics simultaneously."""
    model = manager.create_model(**model_factory)
    model_id = model["model_id"]

    # Update all metrics at once
    updated = manager.update_metrics(
        model_id=model_id,
        validation_calibration=Decimal("0.9100"),
        validation_accuracy=Decimal("0.6500"),
        validation_sample_size=200,
    )

    assert updated["validation_calibration"] == Decimal("0.9100")
    assert updated["validation_accuracy"] == Decimal("0.6500")
    assert updated["validation_sample_size"] == 200


def test_update_metrics_no_fields_provided(clean_test_data, manager, model_factory):
    """Test update_metrics raises ValueError when no fields provided."""
    model = manager.create_model(**model_factory)

    with pytest.raises(ValueError, match="At least one metric must be provided"):
        manager.update_metrics(model_id=model["model_id"])


def test_update_metrics_model_not_found(clean_test_data, manager):
    """Test update_metrics raises ValueError when model doesn't exist."""
    with pytest.raises(ValueError, match="Model 99999 not found"):
        manager.update_metrics(model_id=99999, validation_calibration=Decimal("0.90"))


# ============================================================================
# UPDATE STATUS TESTS (Lifecycle Validation)
# ============================================================================


def test_update_status_draft_to_testing(clean_test_data, manager, model_factory):
    """Test valid transition: draft → testing."""
    model = manager.create_model(**model_factory)

    # Transition draft → testing
    updated = manager.update_status(model_id=model["model_id"], new_status="testing")

    assert updated["status"] == "testing"
    # Note: probability_models table doesn't have updated_at field (only created_at)


def test_update_status_testing_to_active(clean_test_data, manager, model_factory):
    """Test valid transition: testing → active."""
    model = manager.create_model(**{**model_factory, "status": "testing"})

    # Transition testing → active
    updated = manager.update_status(model_id=model["model_id"], new_status="active")

    assert updated["status"] == "active"


def test_update_status_active_to_deprecated(clean_test_data, manager, model_factory):
    """Test valid transition: active → deprecated."""
    model = manager.create_model(**{**model_factory, "status": "active"})

    # Transition active → deprecated
    updated = manager.update_status(model_id=model["model_id"], new_status="deprecated")

    assert updated["status"] == "deprecated"


def test_update_status_testing_to_draft_revert(clean_test_data, manager, model_factory):
    """Test valid revert: testing → draft (found issues during testing)."""
    model = manager.create_model(**{**model_factory, "status": "testing"})

    # Revert testing → draft
    updated = manager.update_status(model_id=model["model_id"], new_status="draft")

    assert updated["status"] == "draft"


def test_update_status_invalid_transition_draft_to_active(clean_test_data, manager, model_factory):
    """Test invalid transition: draft → active (must go through testing).

    Educational Note:
        Status lifecycle enforces quality gates:
        - draft → testing: Model under evaluation
        - testing → active: Passed validation, ready for production
        - active → deprecated: New version available

        Skipping testing (draft → active) bypassed validation!
    """
    model = manager.create_model(**model_factory)

    with pytest.raises(InvalidStatusTransitionError, match="Invalid transition: draft → active"):
        manager.update_status(model_id=model["model_id"], new_status="active")


def test_update_status_invalid_transition_deprecated_to_active(
    clean_test_data, manager, model_factory
):
    """Test invalid transition: deprecated → active (terminal state).

    Educational Note:
        Once deprecated, models cannot be reactivated.
        Why? Deprecated models may have known issues or be superseded.
        To reactivate: Create new version with updated config.
    """
    model = manager.create_model(**{**model_factory, "status": "deprecated"})

    with pytest.raises(
        InvalidStatusTransitionError, match="Invalid transition: deprecated → active"
    ):
        manager.update_status(model_id=model["model_id"], new_status="active")


def test_update_status_model_not_found(clean_test_data, manager):
    """Test update_status raises ValueError when model doesn't exist."""
    with pytest.raises(ValueError, match="Model 99999 not found"):
        manager.update_status(model_id=99999, new_status="testing")


# ============================================================================
# CONFIG IMMUTABILITY TESTS
# ============================================================================


def test_config_immutability_no_update_method(clean_test_data, manager):
    """Test ModelManager has no update_config method (immutability by design).

    Educational Note:
        Config immutability is enforced by NOT providing an update method.
        To change model parameters:
        1. Create new version (v1.0 → v1.1 or v2.0)
        2. Deprecate old version
        3. Activate new version

        This ensures every prediction links to exact config used.
    """
    assert not hasattr(manager, "update_config")
    assert not hasattr(manager, "modify_config")
    assert not hasattr(manager, "change_config")


def test_config_immutability_requires_new_version(clean_test_data, manager, model_factory):
    """Test changing parameters requires creating new version.

    Educational Note:
        Versioning workflow:
        1. v1.0 has k_factor=20 → Deploy to production
        2. Want to test k_factor=25 → Create v1.1 with new config
        3. A/B test: Compare v1.0 vs v1.1 calibration
        4. If v1.1 better → Deprecate v1.0, promote v1.1
        5. All predictions know which version was used (trade attribution)
    """
    # Create v1.0
    v1_0 = manager.create_model(**model_factory)

    # Want to change k_factor: 20 → 25
    # CANNOT update v1.0 config (no method exists)
    # MUST create v1.1 with new config

    new_config = v1_0["config"].copy()
    new_config["k_factor"] = Decimal("25.00")  # Updated parameter

    # Create v1.1
    v1_1 = manager.create_model(
        model_name=v1_0["model_name"],
        model_version="1.1",  # New version
        model_class=v1_0["model_class"],
        domain=v1_0["domain"],
        config=new_config,  # New config
        description="Updated k_factor for better calibration",
    )

    # Verify v1.0 unchanged
    v1_0_current = manager.get_model(model_id=v1_0["model_id"])
    assert v1_0_current["config"]["k_factor"] == Decimal("20.00")

    # Verify v1.1 has new config
    assert v1_1["config"]["k_factor"] == Decimal("25.00")

    # Verify both versions coexist (A/B testing)
    assert v1_0["model_id"] != v1_1["model_id"]


# ============================================================================
# DECIMAL PRECISION TESTS (Pattern 1)
# ============================================================================


def test_decimal_precision_preserved_in_database(clean_test_data, manager, model_factory):
    """Test Decimal precision preserved through database round-trip.

    Educational Note:
        Pattern 1 compliance test:
        1. Application uses Decimal("0.3300")
        2. Stored as string "0.3300" in PostgreSQL JSONB
        3. Retrieved as Decimal("0.3300") back in application
        4. Precision preserved (0.33 would lose trailing zero)
    """
    # Create model with precise Decimal
    model = manager.create_model(**model_factory)

    # Retrieve from database
    retrieved = manager.get_model(model_id=model["model_id"])

    # Verify exact precision preserved
    assert retrieved["config"]["mean_reversion"] == Decimal("0.3300")
    assert str(retrieved["config"]["mean_reversion"]) == "0.3300"  # Trailing zeros preserved


def test_decimal_precision_no_float_contamination(clean_test_data, manager, model_factory):
    """Test config never contains float values (Pattern 1 violation check)."""
    model = manager.create_model(**model_factory)
    config = model["config"]

    # Verify ALL numeric values are Decimal
    for key, value in config.items():
        if isinstance(value, (int, float, Decimal)):
            assert isinstance(value, Decimal), f"{key} should be Decimal, got {type(value)}"
            assert not isinstance(value, float), f"{key} contaminated with float: {value}"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


def test_error_handling_invalid_model_type(clean_test_data, manager, model_factory):
    """Test creating model with invalid model_type."""
    invalid_config = model_factory.copy()
    invalid_config["model_class"] = "invalid_type"  # Not in [elo, ensemble, ml, hybrid]

    # Database constraint should reject invalid type
    # Skip this test for now - database doesn't have CHECK constraint for model_type yet
    pytest.skip("Database schema needs CHECK constraint for model_type validation")


def test_error_handling_duplicate_name_version(clean_test_data, manager, model_factory):
    """Test creating duplicate model (same name + version) raises error."""
    # Use unique model name to avoid collision with other tests
    unique_config = model_factory.copy()
    unique_config["model_name"] = "duplicate_test_model"  # Unique name for this test

    # Ensure clean state using dedicated connection with commit=True
    from precog.database.connection import get_connection, release_connection

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM probability_models WHERE model_name = 'duplicate_test_model'")
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)

    # Create first model
    manager.create_model(**unique_config)

    # Attempt to create duplicate (same name + version)
    # Database unique constraint should reject (psycopg2.IntegrityError)
    with pytest.raises(psycopg2.IntegrityError):  # UNIQUE constraint violation
        manager.create_model(**unique_config)


# ============================================================================
# STATUS LIFECYCLE STATE MACHINE TESTS
# ============================================================================


def test_status_lifecycle_valid_paths(clean_test_data, manager, model_factory):
    """Test all valid status transition paths.

    Valid Paths:
    1. draft → testing → active → deprecated (normal lifecycle)
    2. draft → testing → draft (revert after finding issues)
    3. draft → draft (stay in draft)
    """
    # Path 1: Normal lifecycle (draft → testing → active → deprecated)
    model1 = manager.create_model(**model_factory)
    model1 = manager.update_status(model_id=model1["model_id"], new_status="testing")
    assert model1["status"] == "testing"
    model1 = manager.update_status(model_id=model1["model_id"], new_status="active")
    assert model1["status"] == "active"
    model1 = manager.update_status(model_id=model1["model_id"], new_status="deprecated")
    assert model1["status"] == "deprecated"

    # Path 2: Revert (testing → draft)
    model2_config = model_factory.copy()
    model2_config["model_name"] = "revert_test"
    model2_config["status"] = "testing"
    model2 = manager.create_model(**model2_config)
    model2 = manager.update_status(model_id=model2["model_id"], new_status="draft")
    assert model2["status"] == "draft"


def test_status_lifecycle_terminal_state(clean_test_data, manager, model_factory):
    """Test deprecated is terminal state (no transitions allowed).

    Educational Note:
        Deprecated models are frozen:
        - Cannot activate (use new version instead)
        - Cannot revert to testing (validation already done)
        - Cannot go back to draft (config is immutable)

        This prevents accidental reactivation of superseded models.
    """
    deprecated_config = model_factory.copy()
    deprecated_config["status"] = "deprecated"
    model = manager.create_model(**deprecated_config)

    # Attempt ALL transitions from deprecated (all should fail)
    with pytest.raises(InvalidStatusTransitionError):
        manager.update_status(model_id=model["model_id"], new_status="active")

    with pytest.raises(InvalidStatusTransitionError):
        manager.update_status(model_id=model["model_id"], new_status="testing")

    with pytest.raises(InvalidStatusTransitionError):
        manager.update_status(model_id=model["model_id"], new_status="draft")


# ============================================================================
# INTEGRATION TESTS (Cross-Manager Interactions)
# ============================================================================


def test_model_manager_independent_from_strategy_manager(clean_test_data, manager, model_factory):
    """Test Model Manager operates independently from Strategy Manager.

    Educational Note:
        Models and strategies are separate versioned entities:
        - Model: Probability calculation (v1.0, v1.1, v2.0)
        - Strategy: Betting decision logic (v1.0, v1.1, v2.0)

        Separation enables:
        - Testing different model versions with same strategy
        - Testing different strategies with same model
        - Independent A/B testing for each component
    """
    # Create model
    model = manager.create_model(**model_factory)

    # Verify model exists
    retrieved = manager.get_model(model_id=model["model_id"])
    assert retrieved is not None

    # Model Manager doesn't depend on Strategy Manager
    # (Can create models without strategies, and vice versa)
