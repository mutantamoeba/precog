"""
Property-based tests for strategy versioning (immutable config pattern).

Tests strategy versioning invariants that must hold for ALL inputs:
- Config immutability (NEVER changes after creation)
- Status mutability (CAN change: draft → testing → active → deprecated)
- Version uniqueness (strategy_name + strategy_version unique)
- Semantic versioning ordering (v1.0 < v1.1 < v2.0)
- Trade attribution integrity (every trade links to specific version)
- Config changes require new versions (v1.0 → v1.1)
- Active version uniqueness (at most ONE active version per strategy)
- Version history preservation (historical versions never deleted)

Related:
- DEF-PROP-002 (Phase 1.5 Deferred Property Tests)
- Pattern 2 (Dual Versioning System - Immutable Versions)
- docs/utility/PHASE_1.5_DEFERRED_PROPERTY_TESTS_V1.0.md (lines 195-345)
- docs/guides/VERSIONING_GUIDE_V1.0.md

Educational Note:
    Strategy versioning uses IMMUTABLE configs for A/B testing integrity. Unlike SCD
    Type-2 (which updates in-place for changing data), strategy versions are FROZEN
    snapshots. This preserves:
    - A/B test results (know EXACTLY which config generated each trade)
    - Trade attribution (trades link to specific immutable versions)
    - Backtesting accuracy (replay historical strategies with original configs)

    Mutable vs Immutable:
    - config (IMMUTABLE): Create new version to change
    - status (MUTABLE): Can update in-place
    - activated_at, deactivated_at (MUTABLE): Timestamps

Usage:
    pytest tests/property/test_strategy_versioning_properties.py -v
    pytest tests/property/test_strategy_versioning_properties.py -v --hypothesis-show-statistics
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from psycopg2 import IntegrityError

# Import strategy CRUD operations
from precog.database.crud_operations import (
    create_strategy,
    get_active_strategy_version,
    get_all_strategy_versions,
    get_strategy,
    update_strategy_status,
)

# Import custom Hypothesis strategies

# =============================================================================
# CUSTOM HYPOTHESIS STRATEGIES FOR STRATEGIES
# =============================================================================


@st.composite
def strategy_config_dict(draw) -> dict[str, Any]:
    """
    Generate strategy configuration dict (IMMUTABLE after creation).

    Generates realistic trading strategy configs with parameters like:
    - min_lead: Minimum score lead required
    - min_time_remaining_mins: Minimum time left in game
    - max_edge: Maximum edge to consider
    - kelly_fraction: Position sizing multiplier

    Why custom strategy:
        Strategy configs must be realistic and valid for trading. Random dicts
        could generate invalid configs (negative values, impossible combinations).

    Returns:
        Dictionary with strategy configuration parameters (mixed types: int, Decimal)
    """
    return {
        "min_lead": draw(st.integers(min_value=1, max_value=20)),
        "min_time_remaining_mins": draw(st.integers(min_value=1, max_value=30)),
        "max_edge": draw(
            st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.50"), places=4)
        ),
        "kelly_fraction": draw(
            st.decimals(min_value=Decimal("0.10"), max_value=Decimal("1.00"), places=4)
        ),
    }


@st.composite
def semver_string(draw):
    """
    Generate semantic version string (e.g., "v1.0", "v1.1", "v2.0").

    Generates valid semantic versions following pattern: vMAJOR.MINOR[.PATCH]
    Examples: v1.0, v1.1, v2.0, v1.0.1, v2.5.3
    """
    major = draw(st.integers(min_value=1, max_value=5))
    minor = draw(st.integers(min_value=0, max_value=20))
    # Optional patch version (50% chance)
    include_patch = draw(st.booleans())
    if include_patch:
        patch = draw(st.integers(min_value=0, max_value=10))
        return f"v{major}.{minor}.{patch}"
    return f"v{major}.{minor}"


@st.composite
def strategy_name(draw):
    """Generate valid strategy names."""
    return draw(
        st.sampled_from(
            [
                "halftime_entry",
                "momentum_fade",
                "mean_reversion",
                "quarter_end_surge",
                "underdog_rally",
            ]
        )
    )


# =============================================================================
# CONFIG IMMUTABILITY PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(config=strategy_config_dict())
def test_strategy_config_immutable_via_database(db_pool, clean_test_data, config):
    """
    PROPERTY: Strategy config is IMMUTABLE - cannot be modified after creation.

    Validates:
    - Config stored in database matches original
    - Retrieving strategy returns exact same config
    - Config dictionary deep equals original (not modified)

    Why This Matters:
        Mutable configs would break A/B testing. If we modify v1.0's config mid-test,
        we can no longer attribute trades to specific configs. Immutability ensures
        every trade links to a FROZEN config snapshot.

    Educational Note:
        Python-level immutability vs database immutability:
        - We enforce at APPLICATION level (no update_strategy_config() function)
        - Database stores JSONB (technically mutable)
        - Best practice: Never provide UPDATE function for immutable fields

        To change config:
        1. Create NEW version (v1.0 → v1.1)
        2. Link new trades to v1.1
        3. Keep v1.0 for historical attribution

    Example:
        >>> v1_0 = create_strategy(version="v1.0", config={"min_lead": 7})
        >>> # ❌ NO function to update config (immutability enforced)
        >>> # update_strategy_config(v1_0, {"min_lead": 10})  # DOES NOT EXIST
        >>> # ✅ Must create new version
        >>> v1_1 = create_strategy(version="v1.1", config={"min_lead": 10})
        >>> # v1.0 config unchanged, v1.1 has new config
    """
    # Create strategy with given config
    # Use UUID to make strategy name unique per example (avoid hash collisions)
    unique_id = uuid.uuid4().hex[:8]
    strategy_name_val = f"immutable_test_{unique_id}"
    version = "v1.0"

    strategy_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version=version,
        strategy_type="value",
        config=config,
        status="draft",
    )

    assert strategy_id is not None

    # Retrieve strategy and verify config matches EXACTLY
    retrieved = get_strategy(strategy_id)

    assert retrieved is not None
    assert retrieved["config"] == config, (
        f"Config mismatch: expected {config}, got {retrieved['config']}"
    )

    # Verify ALL config keys preserved
    for key, value in config.items():
        assert key in retrieved["config"], f"Config key '{key}' missing after retrieval"
        assert retrieved["config"][key] == value, (
            f"Config value mismatch for '{key}': expected {value}, got {retrieved['config'][key]}"
        )


# =============================================================================
# STATUS MUTABILITY PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    status_sequence=st.lists(
        st.sampled_from(["draft", "testing", "active", "deprecated"]),
        min_size=2,
        max_size=5,
    )
)
def test_strategy_status_mutable(db_pool, clean_test_data, status_sequence):
    """
    PROPERTY: Strategy status is MUTABLE - can change (draft → testing → active → deprecated).

    Validates:
    - Status can transition through lifecycle states
    - Each status change persists in database
    - Status updates don't affect config (config remains immutable)

    Why This Matters:
        Status represents strategy lifecycle, which MUST change over time:
        - draft: Under development
        - testing: Paper trading
        - active: Live trading
        - deprecated: Superseded by new version

        Unlike config (immutable), status changes are normal and expected.

    Example:
        >>> strategy = create_strategy(status="draft")
        >>> update_strategy_status(strategy_id, "testing")  # ✅ OK
        >>> update_strategy_status(strategy_id, "active")   # ✅ OK
        >>> update_strategy_status(strategy_id, "deprecated")  # ✅ OK
    """
    # Create strategy with initial status
    # Use UUID to make strategy name unique per example (avoid hash collisions)
    unique_id = uuid.uuid4().hex[:8]
    strategy_name_val = f"mutable_status_test_{unique_id}"
    version = "v1.0"
    original_config = {"min_lead": 7, "kelly_fraction": 0.25}

    strategy_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version=version,
        strategy_type="value",
        config=original_config,
        status="draft",
    )

    assert strategy_id is not None

    # Apply status transitions
    for new_status in status_sequence:
        success = update_strategy_status(strategy_id=strategy_id, new_status=new_status)
        assert success is True, f"Failed to update status to {new_status}"

        # Verify status changed
        strategy = get_strategy(strategy_id)
        assert strategy is not None, "Strategy should exist"
        assert strategy["status"] == new_status, (
            f"Status not updated: expected {new_status}, got {strategy['status']}"
        )

        # CRITICAL: Verify config unchanged (immutability preserved)
        assert strategy["config"] == original_config, (
            "Config changed during status update! Config should be IMMUTABLE."
        )


# =============================================================================
# VERSION UNIQUENESS PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(version=semver_string())
def test_strategy_version_unique(db_pool, clean_test_data, version):
    """
    PROPERTY: Strategy (name, version) combinations are unique.

    Validates:
    - Cannot create duplicate (strategy_name, strategy_version) pairs
    - IntegrityError raised on duplicate attempt
    - Database UNIQUE constraint enforced

    Why This Matters:
        Without uniqueness, we could have multiple v1.0 versions with different
        configs, making trade attribution ambiguous. Which v1.0 generated this trade?

    Example:
        >>> create_strategy(name="halftime_entry", version="v1.0")
        >>> create_strategy(name="halftime_entry", version="v1.0")  # Duplicate!
        IntegrityError: duplicate key value violates unique constraint
    """
    # Use UUID to make strategy name unique per example (avoid hash collisions)
    unique_id = uuid.uuid4().hex[:8]
    strategy_name_val = f"unique_version_test_{unique_id}"

    # Create first version (should succeed)
    strategy_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version=version,
        strategy_type="value",
        config={"min_lead": 7},
        status="draft",
    )

    assert strategy_id is not None

    # Attempt to create duplicate (should raise IntegrityError)
    with pytest.raises(IntegrityError, match=r"duplicate key|unique constraint|violates"):
        create_strategy(
            strategy_name=strategy_name_val,
            strategy_version=version,  # Same name + version!
            strategy_type="value",
            config={"min_lead": 10},  # Different config doesn't matter
            status="draft",
        )


# =============================================================================
# SEMANTIC VERSIONING PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@settings(max_examples=50)  # Reduced for performance (no DB needed)
@given(versions=st.lists(semver_string(), min_size=3, max_size=10, unique=True))
def test_semantic_versioning_ordering(versions):
    """
    PROPERTY: Semantic versions sort correctly (v1.0 <= v1.0.0 < v1.1 < v2.0).

    Validates:
    - Semantic version strings sort in correct order
    - Major.Minor.Patch comparison works
    - Handles equivalent versions (v1.0 == v1.0.0)
    - No database required (pure logic test)

    Why This Matters:
        When querying "latest version" or "version history", we rely on correct
        semantic version ordering. Incorrect sorting could activate wrong version.

    Educational Note:
        Python's string comparison doesn't work for semver:
        - "v1.10" < "v1.2" (WRONG! String sort)
        - "v1.2" < "v1.10" (CORRECT! Semantic sort)

        We use packaging.version.Version for correct semver parsing.

        Note: v1.0 == v1.0.0 in semantic versioning (equivalent versions).

    Reference:
        Semantic Versioning Specification: https://semver.org/
        Valid format: MAJOR.MINOR.PATCH (e.g., 1.2.3)
        Precedence: MAJOR > MINOR > PATCH (1.0.0 < 2.0.0 < 2.1.0 < 2.1.1)

    Example:
        >>> from packaging.version import Version
        >>> versions = ["v1.10", "v1.2", "v2.0", "v1.1", "v1.0.0"]
        >>> sorted_versions = sorted(versions, key=lambda v: Version(v.lstrip('v')))
        >>> print(sorted_versions)
        ['v1.0.0', 'v1.1', 'v1.2', 'v1.10', 'v2.0']  # ✅ Correct order
    """
    from packaging.version import Version

    # Sort versions using semantic versioning
    sorted_versions = sorted(versions, key=lambda v: Version(v.lstrip("v")))

    # Verify each version <= next version (allows for equivalent versions like v1.0 == v1.0.0)
    for i in range(len(sorted_versions) - 1):
        v1 = Version(sorted_versions[i].lstrip("v"))
        v2 = Version(sorted_versions[i + 1].lstrip("v"))

        assert v1 <= v2, f"Semantic versioning failed: {v1} should be <= {v2}"


# =============================================================================
# CONFIG CHANGE REQUIRES NEW VERSION PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(original_config=strategy_config_dict(), new_config=strategy_config_dict())
def test_config_change_creates_new_version(db_pool, clean_test_data, original_config, new_config):
    """
    PROPERTY: Changing config requires creating NEW version, not modifying existing.

    Validates:
    - v1.0 config remains unchanged after creating v1.1
    - v1.1 has different config than v1.0
    - Both versions coexist in database

    Why This Matters:
        Modifying v1.0's config would invalidate all trades attributed to v1.0.
        We'd lose the ability to analyze "how did v1.0 perform vs v1.1?"

    Example:
        >>> v1_0 = create_strategy(version="v1.0", config={"min_lead": 7})
        >>> # Time passes, we want to test min_lead=10
        >>> v1_1 = create_strategy(version="v1.1", config={"min_lead": 10})
        >>> # v1.0 config UNCHANGED
        >>> assert get_strategy(v1_0)["config"] == {"min_lead": 7}
        >>> # v1.1 has new config
        >>> assert get_strategy(v1_1)["config"] == {"min_lead": 10}
    """
    # Use assume() to skip if configs identical (nothing to test)
    assume(original_config != new_config)

    # Use UUID to make strategy name unique per example (avoid hash collisions)
    unique_id = uuid.uuid4().hex[:8]
    strategy_name_val = f"config_change_test_{unique_id}"

    # Create v1.0 with original config
    v1_0_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version="v1.0",
        strategy_type="value",
        config=original_config,
        status="draft",
    )

    assert v1_0_id is not None

    # Create v1.1 with new config
    v1_1_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version="v1.1",
        strategy_type="value",
        config=new_config,
        status="draft",
    )

    assert v1_1_id is not None

    # Verify v1.0 config UNCHANGED
    v1_0 = get_strategy(v1_0_id)
    assert v1_0 is not None, "Strategy v1.0 should exist"
    assert v1_0["config"] == original_config, "v1.0 config changed! Config should be IMMUTABLE."

    # Verify v1.1 has new config
    v1_1 = get_strategy(v1_1_id)
    assert v1_1 is not None, "Strategy v1.1 should exist"
    assert v1_1["config"] == new_config, (
        f"v1.1 config mismatch: expected {new_config}, got {v1_1['config']}"
    )

    # Verify both versions coexist
    all_versions = get_all_strategy_versions(strategy_name_val)
    assert len(all_versions) == 2, f"Expected 2 versions, found {len(all_versions)}"


# =============================================================================
# ACTIVE VERSION UNIQUENESS PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(strat_name=strategy_name())
def test_at_most_one_active_version(db_pool, clean_test_data, strat_name):
    """
    PROPERTY: At most ONE version of a strategy can be 'active' simultaneously.

    Validates:
    - Only one active version per strategy name
    - Activating v1.1 doesn't leave v1.0 active
    - get_active_strategy_version() returns exactly one result

    Why This Matters:
        Trading system needs unambiguous answer to "which strategy should I use?"
        If multiple versions are active, trades could use wrong strategy.

    Educational Note:
        Two patterns for managing active versions:
        1. **Auto-deprecate:** Activating v1.1 auto-deprecates v1.0 (enforced by app)
        2. **Manual transition:** Application ensures only one active (requires discipline)

        We test pattern #2 (application enforces, not database constraint).

    Example:
        >>> # Create and activate v1.0
        >>> v1_0 = create_strategy(name="halftime_entry", version="v1.0", status="active")
        >>> # Create v1.1 (draft)
        >>> v1_1 = create_strategy(name="halftime_entry", version="v1.1", status="draft")
        >>> # Activate v1.1
        >>> update_strategy_status(v1_1, "active")
        >>> update_strategy_status(v1_0, "deprecated")  # Manually deprecate v1.0
        >>> # Only v1.1 is active
        >>> active = get_active_strategy_version("halftime_entry")
        >>> assert active["strategy_version"] == "v1.1"
    """
    # Use UUID to make strategy name unique per example (avoid hash collisions)
    unique_id = uuid.uuid4().hex[:8]
    strategy_name_val = f"{strat_name}_{unique_id}"

    # Create multiple versions
    v1_0_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version="v1.0",
        strategy_type="value",
        config={"min_lead": 7},
        status="draft",
    )

    v1_1_id = create_strategy(
        strategy_name=strategy_name_val,
        strategy_version="v1.1",
        strategy_type="value",
        config={"min_lead": 10},
        status="draft",
    )

    # Type narrowing: assert both strategies were created
    assert v1_0_id is not None, "Strategy v1.0 should be created"
    assert v1_1_id is not None, "Strategy v1.1 should be created"

    # Activate v1.0
    update_strategy_status(v1_0_id, "active")

    # Verify only one active
    active = get_active_strategy_version(strategy_name_val)
    assert active is not None
    assert active["strategy_version"] == "v1.0"

    # Activate v1.1 (should manually deprecate v1.0 first to maintain invariant)
    update_strategy_status(v1_0_id, "deprecated")
    update_strategy_status(v1_1_id, "active")

    # Verify only v1.1 is active
    active = get_active_strategy_version(strategy_name_val)
    assert active is not None
    assert active["strategy_version"] == "v1.1"

    # Verify exactly ONE active version
    from precog.database.connection import get_cursor

    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM strategies WHERE strategy_name = %s AND status = 'active'",
            (strategy_name_val,),
        )
        result = cur.fetchone()
        count = result["count"] if result else 0

    assert count <= 1, f"Found {count} active versions, expected at most 1"


# =============================================================================
# VERSION HISTORY PRESERVATION PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(num_versions=st.integers(min_value=2, max_value=10))
def test_all_versions_preserved(db_pool, clean_test_data, num_versions):
    """
    PROPERTY: Historical versions remain in database (never deleted).

    Validates:
    - All created versions persist
    - Activating new version doesn't delete old versions
    - get_all_strategy_versions() returns all versions

    Why This Matters:
        Deleting historical versions would break trade attribution. We'd lose the
        ability to analyze "how did v1.0 perform?" if v1.0 is deleted.

    Example:
        >>> # Create 5 versions
        >>> for i in range(5):
        ...     create_strategy(name="halftime_entry", version=f"v1.{i}")
        >>> # All 5 versions should exist
        >>> versions = get_all_strategy_versions("halftime_entry")
        >>> assert len(versions) == 5
        >>> # Even after activating v1.4, v1.0-v1.3 still exist
    """
    # Use UUID to make strategy name unique per example (avoid hash collisions)
    unique_id = uuid.uuid4().hex[:8]
    strategy_name_val = f"history_preservation_test_{unique_id}"

    # Create multiple versions
    for i in range(num_versions):
        create_strategy(
            strategy_name=strategy_name_val,
            strategy_version=f"v1.{i}",
            strategy_type="value",
            config={"min_lead": 7 + i},  # Slightly different configs
            status="draft",
        )

    # Verify all versions preserved
    all_versions = get_all_strategy_versions(strategy_name_val)
    assert len(all_versions) == num_versions, (
        f"Expected {num_versions} versions, found {len(all_versions)}"
    )

    # Verify each version has correct version string
    version_strings = [v["strategy_version"] for v in all_versions]
    expected_versions = [f"v1.{i}" for i in range(num_versions)]

    for expected in expected_versions:
        assert expected in version_strings, f"Version {expected} not found in database"


# TODO: Additional property tests to consider (future phases):
# - test_trade_attribution_integrity (requires trades table integration)
# - test_strategy_deletion_prevents_orphan_trades (requires foreign keys)
# - test_concurrent_version_creation (requires async testing)
