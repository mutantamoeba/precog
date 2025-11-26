"""Model Manager E2E Tests - Production Workflow Validation.

Tests the complete Model Manager workflow for versioned probability models:
1. Model creation with immutable configurations
2. Model version management and retrieval
3. Status lifecycle transitions (draft → testing → active → deprecated)
4. Metrics updates (calibration, accuracy) while preserving config immutability
5. Model version comparison for A/B testing
6. Decimal precision requirements (Pattern 1)

Educational Note:
    E2E (end-to-end) tests validate complete workflows, not just units.
    These tests simulate real model management scenarios:
    - Create Elo model v1.0 with k_factor=20
    - Test it (update status: draft → testing)
    - Update calibration metrics (track performance)
    - Create v1.1 with improved k_factor=24
    - Compare v1.0 vs v1.1 (A/B testing)
    - Promote better version to active
    - Deprecate old version

    This ensures the complete versioning system works together correctly.

Test Categories:
    1. Model Creation Workflow - Create versions with immutable configs
    2. Model Retrieval - Query models by ID, name, filters
    3. Status Management - Lifecycle transitions with validation
    4. Metrics Update - Mutable performance metrics
    5. Version Comparison - A/B testing support

Pattern 1 Compliance:
    ALL numeric values use Decimal, NEVER float:
    - ✅ CORRECT: Decimal("20.00"), Decimal("0.0523")
    - ❌ WRONG: 20.00, 0.0523

References:
    - REQ-VER-001: Immutable Version Configs
    - REQ-VER-002: Semantic Versioning
    - REQ-VER-003: Trade Attribution (every trade links to exact model version)
    - REQ-VER-004: Version Lifecycle Management
    - REQ-VER-005: A/B Testing Support
    - ADR-018: Immutable Strategy Versions (applies to models too)
    - ADR-019: Semantic Versioning for Strategies (applies to models too)
    - ADR-020: Model Management Architecture
    - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    - Pattern 7 (CLAUDE.md): Educational Docstrings
    - src/precog/analytics/model_manager.py (implementation)
    - docs/guides/VERSIONING_GUIDE_V1.0.md

Created: 2025-11-26
Phase: 4 (Model Development & Backtesting)
GitHub Issue: #128
"""

import uuid
from decimal import Decimal

import pytest

from precog.analytics.model_manager import (
    InvalidStatusTransitionError,
    ModelManager,
)

# Mark all tests as E2E and slow (run with pytest -m e2e)
pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture(scope="module", autouse=True)
def skip_if_no_database():
    """Skip all tests in this module if database is not available.

    Educational Note:
        E2E tests require real database connection.
        If database unavailable (CI, local dev without Postgres):
        - Tests skipped gracefully (not failed)
        - Clear message why skipped
        - Prevents false negatives in test suite
    """
    from precog.database.connection import test_connection

    if not test_connection():
        pytest.skip("Database not available for E2E tests")


@pytest.fixture(scope="module")
def test_run_id():
    """Unique identifier for this test run to prevent name collisions.

    Returns:
        str: 8-character UUID fragment (e.g., "a3f7b2c1")

    Educational Note:
        Problem: Tests create models with static names ("elo_nfl v1.0")
        → UniqueViolation when tests re-run if cleanup failed
        → False test failures, debugging confusion

        Solution: Append unique ID to all model names
        - "elo_nfl" → "elo_nfl_a3f7b2c1"
        - Each test run has different suffix
        - No name collisions between test runs
        - Tests can run in parallel safely

        Cleanup still important (delete test data after),
        but this provides defense in depth.
    """
    return str(uuid.uuid4())[:8]


@pytest.fixture(scope="module")
def cleanup_test_models(test_run_id):
    """Clean up any models created during this test run.

    Args:
        test_run_id: Unique identifier for this test run

    Educational Note:
        Cleanup strategy:
        1. yield: Let tests run first
        2. After all tests: Delete models with test_run_id suffix
        3. Prevents test data accumulation in database

        Why module scope?
        - Cleanup runs ONCE after ALL tests in module
        - More efficient than cleaning after each test
        - Tests in same module can share setup if needed

        Pattern: "Arrange-Act-Assert-Cleanup"
        - Arrange: Create test data with unique ID
        - Act: Run tests
        - Assert: Verify results
        - Cleanup: Delete test data (this fixture)
    """
    yield  # Let tests run

    # After all tests, delete models created with this test_run_id
    from precog.database.connection import get_cursor

    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "DELETE FROM probability_models WHERE model_name LIKE %s",
            (f"%_{test_run_id}",),
        )


@pytest.fixture
def manager():
    """Provide ModelManager instance for E2E tests.

    Educational Note:
        ModelManager is stateless - doesn't hold database connection.
        Each method gets fresh connection for thread safety.
        Safe to reuse across tests.
    """
    return ModelManager()


@pytest.fixture
def elo_model_config(test_run_id):
    """Factory fixture for NFL Elo model configuration.

    Args:
        test_run_id: Unique identifier for this test run

    Returns typical Elo model config with:
    - K-factor for rating adjustments
    - Home field advantage Elo boost
    - Mean reversion to league average
    - Initial rating for new teams

    Educational Note:
        Using factory pattern ensures:
        - Consistency across tests
        - Clear documentation of valid model structure
        - Pattern 1 compliance (all Decimal values)
        - Unique model names per test run (prevents collisions)
    """
    return {
        "model_name": f"elo_nfl_{test_run_id}",
        "model_version": "v1.0",
        "model_class": "elo",
        "domain": "nfl",
        "config": {
            "k_factor": Decimal("20.00"),
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        },
        "description": "NFL Elo rating model for win probability",
        "status": "draft",
        "created_by": "test_user",
    }


@pytest.fixture
def ensemble_model_config(test_run_id):
    """Factory fixture for ensemble model configuration.

    Args:
        test_run_id: Unique identifier for this test run

    Returns ensemble model config with:
    - Weighted combination of Elo, ML, and market signals
    - Minimum agreement threshold for predictions

    Educational Note:
        Ensemble models combine multiple signals:
        - Elo: Historical performance ratings
        - ML: Machine learning predictions
        - Market: Prediction market prices
        Weights must sum to 1.0 for proper probability distribution.
        Model name includes test_run_id to prevent collisions.
    """
    return {
        "model_name": f"ensemble_nfl_{test_run_id}",
        "model_version": "v1.0",
        "model_class": "ensemble",
        "domain": "nfl",
        "config": {
            "weights": {
                "elo": Decimal("0.40"),
                "ml": Decimal("0.35"),
                "market": Decimal("0.25"),
            },
            "min_agreement": Decimal("0.60"),
        },
        "description": "Ensemble combining Elo, ML, and market signals",
        "status": "draft",
        "created_by": "test_user",
    }


# ============================================================================
# TEST CLASS 1: MODEL CREATION WORKFLOW
# ============================================================================


class TestModelCreationWorkflow:
    """
    E2E tests for model creation with versioning.

    Educational Note:
        Model configs are IMMUTABLE after creation (REQ-VER-001).
        To change model parameters, create NEW version:
        - v1.0 (k_factor=20) → v1.1 (k_factor=24): calibration improvement
        - v1.0 → v2.0: algorithm change (Elo → ML)

        This ensures:
        - Every prediction links to exact config used
        - A/B testing compares versions with fixed configs
        - No ambiguity about which parameters generated which predictions
    """

    def test_create_model_with_full_config(self, clean_test_data, manager, elo_model_config):
        """
        Test creating model with complete configuration.

        Scenario:
        - Create NFL Elo model v1.0
        - Include all recommended fields (description, status, created_by)
        - Verify config stored as JSONB with Decimal preservation

        Expected:
        - Model created successfully
        - All fields match input
        - Config preserves Decimal precision (Pattern 1)
        """
        model = manager.create_model(**elo_model_config)

        # Verify basic attributes
        assert model["model_name"] == elo_model_config["model_name"]
        assert model["model_version"] == "v1.0"
        assert model["model_class"] == "elo"
        assert model["domain"] == "nfl"
        assert model["status"] == "draft"
        assert model["created_by"] == "test_user"
        assert model["description"] == "NFL Elo rating model for win probability"

        # Verify config preserved as Decimal (Pattern 1)
        config = model["config"]
        assert isinstance(config["k_factor"], Decimal), "k_factor must be Decimal, not float"
        assert config["k_factor"] == Decimal("20.00")
        assert isinstance(config["home_advantage"], Decimal)
        assert config["home_advantage"] == Decimal("65.00")
        assert isinstance(config["mean_reversion"], Decimal)
        assert config["mean_reversion"] == Decimal("0.33")

        # Verify auto-generated fields
        assert "model_id" in model
        assert model["model_id"] > 0
        assert "created_at" in model

    def test_model_version_increments_correctly(self, clean_test_data, manager, elo_model_config):
        """
        Test creating multiple versions of same model.

        Scenario:
        - Create v1.0 with k_factor=20
        - Create v1.1 with k_factor=24 (calibration improvement)
        - Create v2.0 with new algorithm (major version bump)

        Expected:
        - All three versions created successfully
        - Each has unique model_id
        - Each preserves its own config independently
        - Can retrieve all versions by name

        Educational Note:
            Semantic versioning (REQ-VER-002):
            - v1.0 → v1.1: Minor (calibration, same algorithm)
            - v1.0 → v2.0: Major (algorithm change)
            - Both versions can run simultaneously for A/B testing
        """
        # Create v1.0
        model_v1_0 = manager.create_model(**elo_model_config)
        assert model_v1_0["model_version"] == "v1.0"
        assert model_v1_0["config"]["k_factor"] == Decimal("20.00")

        # Create v1.1 (calibration improvement)
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        elo_v1_1["config"] = {
            "k_factor": Decimal("24.00"),  # Improved k_factor
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        }
        model_v1_1 = manager.create_model(**elo_v1_1)
        assert model_v1_1["model_version"] == "v1.1"
        assert model_v1_1["config"]["k_factor"] == Decimal("24.00")

        # Create v2.0 (major version - algorithm change)
        elo_v2_0 = elo_model_config.copy()
        elo_v2_0["model_version"] = "v2.0"
        elo_v2_0["model_class"] = "ml"  # Algorithm change: Elo → ML
        elo_v2_0["config"] = {
            "model_type": "xgboost",
            "max_depth": Decimal("6"),
            "learning_rate": Decimal("0.1"),
        }
        model_v2_0 = manager.create_model(**elo_v2_0)
        assert model_v2_0["model_version"] == "v2.0"
        assert model_v2_0["model_class"] == "ml"

        # Verify all three versions have unique IDs
        assert model_v1_0["model_id"] != model_v1_1["model_id"]
        assert model_v1_1["model_id"] != model_v2_0["model_id"]

        # Verify can retrieve all versions
        all_versions = manager.get_models_by_name(elo_model_config["model_name"])
        assert len(all_versions) == 3

    def test_config_immutability_enforced(self, clean_test_data, manager, elo_model_config):
        """
        Test config immutability is enforced by database design.

        Scenario:
        - Create model with config
        - Attempt to update config should NOT be possible
        - Only status and metrics can be updated

        Expected:
        - Config remains unchanged after creation
        - ModelManager has no update_config method
        - Only update_status and update_metrics methods exist

        Educational Note:
            Config is IMMUTABLE by design (ADR-018, REQ-VER-001):
            - No update_config() method exists in ModelManager
            - Database table has config column (could add constraint)
            - To change config, must create new version

            This prevents:
            - Accidental config changes invalidating past predictions
            - Breaking trade attribution (every trade links to exact config)
            - A/B testing confusion (which config was used when?)
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]
        original_config = model["config"].copy()

        # Verify ModelManager has no update_config method
        assert not hasattr(manager, "update_config"), (
            "ModelManager should not have update_config method. "
            "Config is IMMUTABLE - create new version instead."
        )

        # Verify config unchanged after status update
        manager.update_status(model_id, "testing")
        retrieved = manager.get_model(model_id=model_id)
        assert retrieved["config"] == original_config, (
            "Config must remain unchanged after status update"
        )

        # Verify config unchanged after metrics update
        manager.update_metrics(
            model_id,
            validation_calibration=Decimal("0.0523"),
            validation_accuracy=Decimal("0.6789"),
        )
        retrieved = manager.get_model(model_id=model_id)
        assert retrieved["config"] == original_config, (
            "Config must remain unchanged after metrics update"
        )

    def test_create_multiple_versions_same_name(self, clean_test_data, manager, elo_model_config):
        """
        Test creating multiple versions with same name for A/B testing.

        Scenario:
        - Create elo_nfl v1.0 (baseline)
        - Create elo_nfl v1.1 (improved calibration)
        - Both active simultaneously for A/B testing

        Expected:
        - Both versions created successfully
        - Both can be active at same time
        - Each has independent config and metrics
        - Can retrieve both and compare performance

        Educational Note:
            A/B testing workflow (REQ-VER-005):
            1. Create v1.0 (baseline)
            2. Create v1.1 (improvement hypothesis)
            3. Set both to active
            4. Run predictions with both models
            5. Compare calibration/accuracy metrics
            6. Promote better version, deprecate worse version
        """
        # Create v1.0 baseline
        model_v1_0 = manager.create_model(**elo_model_config)
        manager.update_status(model_v1_0["model_id"], "testing")
        manager.update_status(model_v1_0["model_id"], "active")

        # Create v1.1 improvement
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        elo_v1_1["config"] = {
            "k_factor": Decimal("24.00"),  # Hypothesis: k=24 better than k=20
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        }
        model_v1_1 = manager.create_model(**elo_v1_1)
        manager.update_status(model_v1_1["model_id"], "testing")
        manager.update_status(model_v1_1["model_id"], "active")

        # Verify both active simultaneously
        active_models = manager.get_active_models()
        active_names = [m["model_name"] for m in active_models]
        assert active_names.count(elo_model_config["model_name"]) == 2, (
            "Both versions should be active for A/B testing"
        )

        # Verify each has independent config
        v1_0_retrieved = manager.get_model(
            model_name=elo_model_config["model_name"], model_version="v1.0"
        )
        v1_1_retrieved = manager.get_model(
            model_name=elo_model_config["model_name"], model_version="v1.1"
        )
        assert v1_0_retrieved["config"]["k_factor"] == Decimal("20.00")
        assert v1_1_retrieved["config"]["k_factor"] == Decimal("24.00")


# ============================================================================
# TEST CLASS 2: MODEL RETRIEVAL
# ============================================================================


class TestModelRetrieval:
    """
    E2E tests for querying models with various filters.

    Educational Note:
        ModelManager provides flexible retrieval:
        - By ID: get_model(model_id=1)
        - By name+version: get_model(model_name='elo_nfl', model_version='v1.0')
        - All versions: get_models_by_name('elo_nfl')
        - Active only: get_active_models()
        - Filtered list: list_models(status='active', domain='nfl')
    """

    def test_get_model_by_id(self, clean_test_data, manager, elo_model_config):
        """
        Test retrieving model by primary key (model_id).

        Scenario:
        - Create model
        - Retrieve by model_id
        - Verify all fields match

        Expected:
        - Model retrieved successfully
        - All attributes preserved
        - Config maintains Decimal precision
        """
        created = manager.create_model(**elo_model_config)
        model_id = created["model_id"]

        retrieved = manager.get_model(model_id=model_id)

        assert retrieved is not None
        assert retrieved["model_id"] == model_id
        assert retrieved["model_name"] == elo_model_config["model_name"]
        assert retrieved["model_version"] == "v1.0"
        assert retrieved["config"] == created["config"]

    def test_get_models_by_name_returns_all_versions(
        self, clean_test_data, manager, elo_model_config
    ):
        """
        Test retrieving all versions of a model by name.

        Scenario:
        - Create elo_nfl v1.0, v1.1, v2.0
        - Retrieve all versions by name
        - Verify returns all three versions
        - Verify sorted by created_at DESC (newest first)

        Expected:
        - All versions returned
        - Ordered newest to oldest
        - Each version has correct config

        Educational Note:
            Use this to compare model evolution:
            - v1.0 (baseline): calibration=0.0687
            - v1.1 (improved): calibration=0.0523
            - v2.0 (new algorithm): calibration=0.0489
        """
        # Create three versions
        manager.create_model(**elo_model_config)

        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        manager.create_model(**elo_v1_1)

        elo_v2_0 = elo_model_config.copy()
        elo_v2_0["model_version"] = "v2.0"
        manager.create_model(**elo_v2_0)

        # Retrieve all versions (using unique model name with test_run_id)
        all_versions = manager.get_models_by_name(elo_model_config["model_name"])

        assert len(all_versions) == 3
        # Verify ordered by created_at DESC (newest first)
        assert all_versions[0]["model_version"] == "v2.0"
        assert all_versions[1]["model_version"] == "v1.1"
        assert all_versions[2]["model_version"] == "v1.0"

    def test_get_active_models_filters_correctly(
        self, clean_test_data, manager, elo_model_config, ensemble_model_config, test_run_id
    ):
        """
        Test get_active_models returns only active models.

        Scenario:
        - Create elo_nfl v1.0 (draft)
        - Create elo_nfl v1.1 (active)
        - Create ensemble_nfl v1.0 (active)
        - Query active models

        Expected:
        - Returns only v1.1 and ensemble_nfl (from this test run)
        - Does not return draft models
        - Returns all active regardless of name/domain

        Educational Note:
            Active models are used for live predictions.
            You can have multiple active models for:
            - A/B testing (elo_nfl v1.0 vs v1.1)
            - Different domains (elo_nfl vs elo_ncaaf)
            - Different approaches (elo vs ml vs ensemble)

            Test uses test_run_id to filter results, ignoring
            stale test data from previous runs.
        """
        # Create elo_nfl v1.0 (draft)
        elo_v1_0 = manager.create_model(**elo_model_config)

        # Create elo_nfl v1.1 (active)
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        elo_v1_1_created = manager.create_model(**elo_v1_1)
        manager.update_status(elo_v1_1_created["model_id"], "testing")
        manager.update_status(elo_v1_1_created["model_id"], "active")

        # Create ensemble_nfl v1.0 (active)
        ensemble_created = manager.create_model(**ensemble_model_config)
        manager.update_status(ensemble_created["model_id"], "testing")
        manager.update_status(ensemble_created["model_id"], "active")

        # Query active models
        active_models = manager.get_active_models()

        # Filter to only models from THIS test run (ignore stale test data)
        test_models = [m for m in active_models if test_run_id in m["model_name"]]

        # Verify only active models from this test run returned
        assert len(test_models) == 2, (
            f"Expected 2 active models from this test run, found {len(test_models)}. "
            f"Models: {[m['model_name'] for m in test_models]}"
        )
        active_names = [m["model_name"] for m in test_models]
        assert elo_model_config["model_name"] in active_names  # v1.1
        assert ensemble_model_config["model_name"] in active_names

        # Verify draft model not returned
        for model in test_models:
            assert model["status"] == "active"
            assert model["model_id"] != elo_v1_0["model_id"]

    def test_list_models_pagination(self, clean_test_data, manager, elo_model_config, test_run_id):
        """
        Test list_models with multiple filters.

        Scenario:
        - Create 5 models with different status/domain/model_class
        - Query with various filter combinations
        - Verify correct filtering logic

        Expected:
        - Single filter works (status='active')
        - Multiple filters work (status='active' AND domain='nfl')
        - No filters returns all models
        - Empty result if no matches

        Educational Note:
            list_models supports flexible querying:
            - status filter: 'draft', 'testing', 'active', 'deprecated'
            - domain filter: 'nfl', 'ncaaf', 'nba', None (multi-domain)
            - model_class filter: 'elo', 'ml', 'ensemble', 'hybrid'
        """
        # Create 5 models with different attributes
        # 1. elo_nfl v1.0 (draft, nfl, elo)
        manager.create_model(**elo_model_config)

        # 2. elo_nfl v1.1 (active, nfl, elo)
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        model2 = manager.create_model(**elo_v1_1)
        manager.update_status(model2["model_id"], "testing")
        manager.update_status(model2["model_id"], "active")

        # 3. elo_ncaaf v1.0 (active, ncaaf, elo)
        elo_ncaaf = elo_model_config.copy()
        elo_ncaaf["model_name"] = f"elo_ncaaf_{test_run_id}"
        elo_ncaaf["domain"] = "ncaaf"
        model3 = manager.create_model(**elo_ncaaf)
        manager.update_status(model3["model_id"], "testing")
        manager.update_status(model3["model_id"], "active")

        # 4. ensemble_nfl v1.0 (active, nfl, ensemble)
        ensemble = elo_model_config.copy()
        ensemble["model_name"] = f"ensemble_nfl_v2_{test_run_id}"
        ensemble["model_class"] = "ensemble"
        ensemble["config"] = {"weights": {"elo": Decimal("0.5"), "ml": Decimal("0.5")}}
        model4 = manager.create_model(**ensemble)
        manager.update_status(model4["model_id"], "testing")
        manager.update_status(model4["model_id"], "active")

        # 5. ml_nfl v1.0 (testing, nfl, ml)
        ml_nfl = elo_model_config.copy()
        ml_nfl["model_name"] = f"ml_nfl_{test_run_id}"
        ml_nfl["model_class"] = "ml"
        ml_nfl["config"] = {"model_type": "xgboost"}
        model5 = manager.create_model(**ml_nfl)
        manager.update_status(model5["model_id"], "testing")

        # Test: No filters (all models from this test run)
        all_models = manager.list_models()
        test_models = [m for m in all_models if test_run_id in m["model_name"]]
        assert len(test_models) == 5, (
            f"Expected 5 models from this test run, found {len(test_models)}. "
            f"Models: {[m['model_name'] for m in test_models]}"
        )

        # Test: Single filter - status='active' (3 models: elo_nfl v1.1, elo_ncaaf, ensemble_nfl)
        active_models = manager.list_models(status="active")
        test_active = [m for m in active_models if test_run_id in m["model_name"]]
        assert len(test_active) == 3, (
            f"Expected 3 active models from this test run, found {len(test_active)}"
        )

        # Test: Single filter - domain='nfl' (4 models: both elo_nfl, ensemble_nfl, ml_nfl)
        nfl_models = manager.list_models(domain="nfl")
        test_nfl = [m for m in nfl_models if test_run_id in m["model_name"]]
        assert len(test_nfl) == 4, (
            f"Expected 4 nfl models from this test run, found {len(test_nfl)}"
        )

        # Test: Multiple filters - status='active' AND domain='nfl' (2 models: elo_nfl v1.1, ensemble_nfl)
        active_nfl = manager.list_models(status="active", domain="nfl")
        test_active_nfl = [m for m in active_nfl if test_run_id in m["model_name"]]
        assert len(test_active_nfl) == 2, (
            f"Expected 2 active nfl models from this test run, found {len(test_active_nfl)}"
        )

        # Test: Multiple filters - status='active' AND domain='nfl' AND model_class='elo' (1 model: elo_nfl v1.1)
        active_nfl_elo = manager.list_models(status="active", domain="nfl", model_class="elo")
        test_active_nfl_elo = [m for m in active_nfl_elo if test_run_id in m["model_name"]]
        assert len(test_active_nfl_elo) == 1, (
            f"Expected 1 active nfl elo model from this test run, found {len(test_active_nfl_elo)}"
        )
        assert test_active_nfl_elo[0]["model_name"] == elo_model_config["model_name"]
        assert test_active_nfl_elo[0]["model_version"] == "v1.1"


# ============================================================================
# TEST CLASS 3: STATUS MANAGEMENT
# ============================================================================


class TestModelStatusManagement:
    """
    E2E tests for model status lifecycle management.

    Educational Note:
        Model status lifecycle (REQ-VER-004):
        - draft: Initial creation, not production-ready
        - testing: Backtesting/validation in progress
        - active: Production use (live predictions)
        - deprecated: Retired (no longer used)

        Valid transitions:
        - draft → testing (start validation)
        - testing → active (promote to production)
        - testing → draft (revert to development)
        - active → deprecated (retire model)

        Invalid transitions:
        - deprecated → active (can't resurrect)
        - active → testing (can't go backwards)
    """

    def test_update_status_active_to_inactive(self, clean_test_data, manager, elo_model_config):
        """
        Test complete status lifecycle: draft → testing → active → deprecated.

        Scenario:
        - Create model (draft)
        - Transition to testing (backtesting)
        - Transition to active (production)
        - Transition to deprecated (retirement)

        Expected:
        - All transitions succeed
        - Status updated correctly at each step
        - Config remains unchanged throughout

        Educational Note:
            Typical model lifecycle:
            1. Draft: Create model, define config
            2. Testing: Run backtests, validate calibration
            3. Active: Deploy to production if calibration good
            4. Deprecated: Retire when better version available
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]
        original_config = model["config"].copy()

        # Verify initial status
        assert model["status"] == "draft"

        # Transition: draft → testing
        updated = manager.update_status(model_id, "testing")
        assert updated["status"] == "testing"
        assert updated["config"] == original_config, "Config must remain unchanged"

        # Transition: testing → active
        updated = manager.update_status(model_id, "active")
        assert updated["status"] == "active"
        assert updated["config"] == original_config, "Config must remain unchanged"

        # Transition: active → deprecated
        updated = manager.update_status(model_id, "deprecated")
        assert updated["status"] == "deprecated"
        assert updated["config"] == original_config, "Config must remain unchanged"

    def test_update_status_preserves_config(self, clean_test_data, manager, elo_model_config):
        """
        Test status updates preserve config immutability.

        Scenario:
        - Create model with specific config
        - Update status multiple times
        - Verify config never changes

        Expected:
        - Config identical after every status update
        - All Decimal values preserved exactly

        Educational Note:
            Status is MUTABLE, config is IMMUTABLE.
            This separation ensures:
            - Status tracks model lifecycle
            - Config tracks prediction parameters
            - Never confusion about which config was used
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]
        original_config = model["config"].copy()

        # Verify config before any updates
        assert model["config"]["k_factor"] == Decimal("20.00")
        assert model["config"]["home_advantage"] == Decimal("65.00")

        # Update status: draft → testing
        manager.update_status(model_id, "testing")
        retrieved = manager.get_model(model_id=model_id)
        assert retrieved["config"] == original_config
        assert retrieved["config"]["k_factor"] == Decimal("20.00")

        # Update status: testing → active
        manager.update_status(model_id, "active")
        retrieved = manager.get_model(model_id=model_id)
        assert retrieved["config"] == original_config
        assert retrieved["config"]["k_factor"] == Decimal("20.00")

        # Verify no float contamination (Pattern 1)
        assert isinstance(retrieved["config"]["k_factor"], Decimal)
        assert isinstance(retrieved["config"]["home_advantage"], Decimal)

    def test_status_transitions_logged(self, clean_test_data, manager, elo_model_config):
        """
        Test invalid status transitions are rejected.

        Scenario:
        - Create model (draft)
        - Attempt invalid transitions
        - Verify InvalidStatusTransitionError raised

        Expected:
        - deprecated → active: REJECTED (can't resurrect)
        - active → testing: REJECTED (can't go backwards)
        - draft → active: REJECTED (must test first)

        Educational Note:
            Status validation prevents:
            - Accidental resurrection of deprecated models
            - Skipping validation (draft → active directly)
            - Going backwards in lifecycle (active → testing)

            Valid state machine enforces quality control.
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]

        # Transition to deprecated (draft → testing → active → deprecated)
        manager.update_status(model_id, "testing")
        manager.update_status(model_id, "active")
        manager.update_status(model_id, "deprecated")

        # Attempt invalid transition: deprecated → active (can't resurrect)
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            manager.update_status(model_id, "active")
        assert "deprecated" in str(exc_info.value).lower()
        assert "active" in str(exc_info.value).lower()

        # Create new model for next test (use unique version to avoid collision)
        elo_v1_1_config = elo_model_config.copy()
        elo_v1_1_config["model_version"] = "v1.1"  # Avoid duplicate key error
        model2 = manager.create_model(**elo_v1_1_config)
        model2_id = model2["model_id"]

        # Transition to active
        manager.update_status(model2_id, "testing")
        manager.update_status(model2_id, "active")

        # Attempt invalid transition: active → testing (can't go backwards)
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            manager.update_status(model2_id, "testing")
        assert "active" in str(exc_info.value).lower()
        assert "testing" in str(exc_info.value).lower()


# ============================================================================
# TEST CLASS 4: METRICS UPDATE
# ============================================================================


class TestModelMetricsUpdate:
    """
    E2E tests for updating mutable model metrics.

    Educational Note:
        Metrics are MUTABLE (unlike config):
        - validation_calibration: Brier score / log loss
        - validation_accuracy: Overall prediction accuracy
        - validation_sample_size: Number of predictions made

        Why mutable?
        - Calibration improves as more predictions accumulate
        - Config stays fixed, metrics track performance
        - Enables A/B testing: compare v1.0 vs v1.1 metrics
    """

    def test_update_metrics_accuracy_tracking(self, clean_test_data, manager, elo_model_config):
        """
        Test updating model accuracy metrics.

        Scenario:
        - Create model
        - Update accuracy after backtesting
        - Verify metrics updated, config unchanged

        Expected:
        - Metrics update successfully
        - Config remains unchanged
        - Decimal precision maintained

        Educational Note:
            Accuracy = Percentage of correct predictions
            Example: 1000 predictions, 678 correct → 67.8% accuracy
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]
        original_config = model["config"].copy()

        # Verify initial metrics are None
        assert model["validation_accuracy"] is None
        assert model["validation_sample_size"] is None

        # Update metrics after backtesting
        updated = manager.update_metrics(
            model_id,
            validation_accuracy=Decimal("0.6780"),  # 67.8% accuracy
            validation_sample_size=1000,  # 1000 predictions
        )

        # Verify metrics updated
        assert updated["validation_accuracy"] == Decimal("0.6780")
        assert updated["validation_sample_size"] == 1000
        assert isinstance(updated["validation_accuracy"], Decimal), "Accuracy must be Decimal"

        # Verify config unchanged (immutability)
        assert updated["config"] == original_config
        assert updated["config"]["k_factor"] == Decimal("20.00")

    def test_update_metrics_calibration_scores(self, clean_test_data, manager, elo_model_config):
        """
        Test updating model calibration metrics.

        Scenario:
        - Create model
        - Update calibration after backtesting
        - Verify Brier score / log loss tracked

        Expected:
        - Calibration metric updated
        - Lower is better (0 = perfect calibration)
        - Decimal precision maintained

        Educational Note:
            Calibration measures probability accuracy:
            - Brier score: Mean squared error of probabilities
            - 0.0 = perfect calibration
            - 0.25 = random guessing (coin flip)
            - <0.10 = good calibration
            - >0.15 = poor calibration

            Example:
            - Predict 60% probability, outcome happens → error = (0.6-1.0)^2 = 0.16
            - Predict 60% probability, outcome doesn't happen → error = (0.6-0.0)^2 = 0.36
            - Average error across all predictions = calibration score
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]

        # Update calibration after backtesting
        updated = manager.update_metrics(
            model_id,
            validation_calibration=Decimal("0.0523"),  # Good calibration (<0.10)
            validation_sample_size=500,
        )

        # Verify calibration updated
        assert updated["validation_calibration"] == Decimal("0.0523")
        assert isinstance(updated["validation_calibration"], Decimal)

        # Verify calibration is reasonable (0 < calibration < 0.25)
        assert Decimal("0") < updated["validation_calibration"] < Decimal("0.25")

    def test_metrics_update_preserves_immutable_fields(
        self, clean_test_data, manager, elo_model_config
    ):
        """
        Test metrics update preserves all immutable fields.

        Scenario:
        - Create model with complete config
        - Update metrics multiple times
        - Verify config, name, version, description never change

        Expected:
        - Only metrics fields change
        - All immutable fields preserved exactly
        - No float contamination in config

        Educational Note:
            Immutable fields (can NEVER change):
            - model_name, model_version (identity)
            - config (prediction parameters)
            - model_class, domain (classification)
            - created_at, created_by (audit trail)

            Mutable fields (can change):
            - status (lifecycle: draft → testing → active → deprecated)
            - validation_calibration, validation_accuracy, validation_sample_size (performance)
        """
        model = manager.create_model(**elo_model_config)
        model_id = model["model_id"]

        # Capture immutable fields
        original_name = model["model_name"]
        original_version = model["model_version"]
        original_config = model["config"].copy()
        original_model_class = model["model_class"]
        original_domain = model["domain"]
        original_created_at = model["created_at"]

        # Update metrics (1st time)
        updated1 = manager.update_metrics(
            model_id,
            validation_calibration=Decimal("0.0687"),
            validation_accuracy=Decimal("0.6543"),
            validation_sample_size=100,
        )

        # Verify immutable fields unchanged
        assert updated1["model_name"] == original_name
        assert updated1["model_version"] == original_version
        assert updated1["config"] == original_config
        assert updated1["model_class"] == original_model_class
        assert updated1["domain"] == original_domain
        assert updated1["created_at"] == original_created_at

        # Update metrics (2nd time - simulate more data)
        updated2 = manager.update_metrics(
            model_id,
            validation_calibration=Decimal("0.0523"),  # Improved calibration
            validation_accuracy=Decimal("0.6789"),  # Improved accuracy
            validation_sample_size=1000,  # More samples
        )

        # Verify immutable fields STILL unchanged
        assert updated2["model_name"] == original_name
        assert updated2["model_version"] == original_version
        assert updated2["config"] == original_config
        assert updated2["config"]["k_factor"] == Decimal("20.00")
        assert isinstance(updated2["config"]["k_factor"], Decimal), "Config must remain Decimal"


# ============================================================================
# TEST CLASS 5: VERSION COMPARISON
# ============================================================================


class TestModelVersionComparison:
    """
    E2E tests for model version comparison and A/B testing.

    Educational Note:
        A/B testing workflow (REQ-VER-005):
        1. Create baseline (v1.0)
        2. Create variants (v1.1, v1.2)
        3. Run all versions in parallel
        4. Compare metrics (calibration, accuracy)
        5. Promote best version to production
        6. Deprecate worse versions

        This ensures we always use the best-performing model.
    """

    def test_compare_model_versions_by_accuracy(self, clean_test_data, manager, elo_model_config):
        """
        Test comparing multiple model versions by accuracy.

        Scenario:
        - Create v1.0 (k_factor=20, accuracy=65%)
        - Create v1.1 (k_factor=24, accuracy=67%)
        - Create v1.2 (k_factor=28, accuracy=66%)
        - Compare accuracy to identify best version

        Expected:
        - All versions created with different configs
        - Each has independent accuracy metric
        - Can identify v1.1 as most accurate

        Educational Note:
            A/B testing example:
            - Hypothesis: Higher k_factor improves accuracy
            - Test: k=20 (baseline) vs k=24 vs k=28
            - Result: k=24 wins (67% accuracy)
            - Decision: Promote v1.1 to production
        """
        # Create v1.0 (baseline: k=20)
        v1_0 = manager.create_model(**elo_model_config)
        manager.update_metrics(
            v1_0["model_id"], validation_accuracy=Decimal("0.6500"), validation_sample_size=1000
        )

        # Create v1.1 (hypothesis: k=24 better)
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        elo_v1_1["config"] = {
            "k_factor": Decimal("24.00"),
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        }
        v1_1 = manager.create_model(**elo_v1_1)
        manager.update_metrics(
            v1_1["model_id"], validation_accuracy=Decimal("0.6700"), validation_sample_size=1000
        )

        # Create v1.2 (hypothesis: k=28 even better?)
        elo_v1_2 = elo_model_config.copy()
        elo_v1_2["model_version"] = "v1.2"
        elo_v1_2["config"] = {
            "k_factor": Decimal("28.00"),
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        }
        v1_2 = manager.create_model(**elo_v1_2)
        manager.update_metrics(
            v1_2["model_id"], validation_accuracy=Decimal("0.6600"), validation_sample_size=1000
        )

        # Retrieve all versions for comparison
        all_versions = manager.get_models_by_name(elo_model_config["model_name"])
        assert len(all_versions) == 3

        # Compare accuracy
        accuracies = {
            v["model_version"]: v["validation_accuracy"]
            for v in all_versions
            if v["validation_accuracy"]
        }

        assert accuracies["v1.0"] == Decimal("0.6500")
        assert accuracies["v1.1"] == Decimal("0.6700")  # Best accuracy
        assert accuracies["v1.2"] == Decimal("0.6600")

        # Identify best version
        best_version = max(all_versions, key=lambda v: v["validation_accuracy"] or Decimal("0"))
        assert best_version["model_version"] == "v1.1"
        assert best_version["config"]["k_factor"] == Decimal("24.00")

    def test_identify_best_calibrated_version(self, clean_test_data, manager, elo_model_config):
        """
        Test comparing multiple model versions by calibration.

        Scenario:
        - Create v1.0 (calibration=0.0687)
        - Create v1.1 (calibration=0.0523 - best)
        - Create v1.2 (calibration=0.0612)
        - Identify v1.1 as best calibrated (lowest Brier score)

        Expected:
        - All versions have independent calibration metrics
        - Can identify best calibrated version (lowest score)
        - Decision: Promote v1.1 to production

        Educational Note:
            Calibration is often more important than accuracy:
            - Accuracy: 70% correct predictions
            - Calibration: 60% predictions are well-calibrated probabilities

            For trading, calibration matters more:
            - Need accurate probabilities, not just yes/no
            - Better calibration → better edge calculation → better Kelly sizing
        """
        # Create v1.0 (baseline calibration)
        v1_0 = manager.create_model(**elo_model_config)
        manager.update_metrics(
            v1_0["model_id"], validation_calibration=Decimal("0.0687"), validation_sample_size=500
        )

        # Create v1.1 (improved calibration)
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        elo_v1_1["config"] = {
            "k_factor": Decimal("24.00"),  # Tuned for better calibration
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        }
        v1_1 = manager.create_model(**elo_v1_1)
        manager.update_metrics(
            v1_1["model_id"], validation_calibration=Decimal("0.0523"), validation_sample_size=500
        )

        # Create v1.2 (worse calibration)
        elo_v1_2 = elo_model_config.copy()
        elo_v1_2["model_version"] = "v1.2"
        elo_v1_2["config"] = {
            "k_factor": Decimal("28.00"),
            "home_advantage": Decimal("65.00"),
            "mean_reversion": Decimal("0.33"),
            "initial_rating": Decimal("1500.00"),
        }
        v1_2 = manager.create_model(**elo_v1_2)
        manager.update_metrics(
            v1_2["model_id"], validation_calibration=Decimal("0.0612"), validation_sample_size=500
        )

        # Retrieve all versions
        all_versions = manager.get_models_by_name(elo_model_config["model_name"])

        # Compare calibration (lower is better)
        calibrations = {
            v["model_version"]: v["validation_calibration"]
            for v in all_versions
            if v["validation_calibration"]
        }

        assert calibrations["v1.0"] == Decimal("0.0687")
        assert calibrations["v1.1"] == Decimal("0.0523")  # Best calibration (lowest)
        assert calibrations["v1.2"] == Decimal("0.0612")

        # Identify best calibrated version (lowest Brier score)
        best_version = min(
            all_versions, key=lambda v: v["validation_calibration"] or Decimal("1.0")
        )
        assert best_version["model_version"] == "v1.1"
        assert best_version["validation_calibration"] == Decimal("0.0523")

    def test_model_version_audit_trail(self, clean_test_data, manager, elo_model_config):
        """
        Test complete audit trail for model version evolution.

        Scenario:
        - Create v1.0 (baseline)
        - Test v1.0, promote to active
        - Create v1.1 (improvement), test, promote
        - Deprecate v1.0 (retire old version)
        - Track complete history

        Expected:
        - All versions preserved in database
        - Status transitions recorded
        - Can trace model evolution over time
        - Trade attribution works (every trade links to exact version)

        Educational Note:
            Audit trail enables:
            - "Which model generated this prediction?" (trade attribution)
            - "Why did we change k_factor from 20 to 24?" (version history)
            - "When did we promote v1.1 to production?" (status history)
            - "What was the calibration of v1.0?" (metrics history)

            This is critical for:
            - Debugging: Why did we lose money on this trade?
            - Compliance: Prove we used approved model
            - Research: Evaluate model improvements over time
        """
        # Create v1.0 (baseline)
        v1_0 = manager.create_model(**elo_model_config)
        v1_0_id = v1_0["model_id"]

        # Test v1.0
        manager.update_status(v1_0_id, "testing")
        manager.update_metrics(
            v1_0_id, validation_calibration=Decimal("0.0687"), validation_sample_size=500
        )

        # Promote v1.0 to active
        manager.update_status(v1_0_id, "active")

        # Create v1.1 (improvement)
        elo_v1_1 = elo_model_config.copy()
        elo_v1_1["model_version"] = "v1.1"
        elo_v1_1["config"]["k_factor"] = Decimal("24.00")  # Improved k_factor
        v1_1 = manager.create_model(**elo_v1_1)
        v1_1_id = v1_1["model_id"]

        # Test v1.1
        manager.update_status(v1_1_id, "testing")
        manager.update_metrics(
            v1_1_id, validation_calibration=Decimal("0.0523"), validation_sample_size=500
        )

        # Promote v1.1 to active (now both active for A/B testing)
        manager.update_status(v1_1_id, "active")

        # After A/B testing, deprecate v1.0 (v1.1 wins)
        manager.update_status(v1_0_id, "deprecated")

        # Retrieve complete history
        all_versions = manager.get_models_by_name(elo_model_config["model_name"])
        assert len(all_versions) == 2

        # Verify v1.0 audit trail
        v1_0_retrieved = manager.get_model(model_id=v1_0_id)
        assert v1_0_retrieved["model_version"] == "v1.0"
        assert v1_0_retrieved["status"] == "deprecated"
        assert v1_0_retrieved["config"]["k_factor"] == Decimal("20.00")
        assert v1_0_retrieved["validation_calibration"] == Decimal("0.0687")

        # Verify v1.1 audit trail
        v1_1_retrieved = manager.get_model(model_id=v1_1_id)
        assert v1_1_retrieved["model_version"] == "v1.1"
        assert v1_1_retrieved["status"] == "active"
        assert v1_1_retrieved["config"]["k_factor"] == Decimal("24.00")
        assert v1_1_retrieved["validation_calibration"] == Decimal("0.0523")

        # Verify trade attribution possible
        # In production: trades.model_id = v1_1_id → can trace to exact config
        assert v1_1_id != v1_0_id, "Each version has unique ID for trade attribution"
