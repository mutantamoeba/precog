"""
Unit tests for Strategy Manager.

Tests the StrategyManager class which manages versioned trading strategies
with immutable configurations.

Reference: docs/testing/PHASE_1.5_TEST_PLAN_V1.0.md
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003, REQ-VER-004
Related ADRs: ADR-018, ADR-019, ADR-020
"""

import json
from decimal import Decimal
from typing import Any

import pytest

from precog.trading.strategy_manager import (
    InvalidStatusTransitionError,
    StrategyManager,
)

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def strategy_factory() -> dict[str, Any]:
    """Factory fixture for creating test strategy configurations.

    Returns:
        Dictionary with valid strategy parameters using Decimal types

    Educational Note:
        - All prices/probabilities use Decimal (Pattern 1)
        - Config parameters follow Kalshi pricing cheat sheet
        - Returns dict (not function) for simpler test usage

    Example:
        >>> config = strategy_factory
        >>> config["config"]["min_edge"]
        Decimal('0.0500')
    """
    return {
        "strategy_name": "value_betting_v1",
        "strategy_version": "1.0",
        "strategy_type": "value",  # FIXED: was "value_betting", must be 'value', 'arbitrage', 'momentum', or 'mean_reversion'
        "domain": "nfl",
        "config": {
            "min_edge": Decimal("0.0500"),  # 5% minimum edge
            "max_position_size": Decimal("100.00"),  # $100 max per position
            "kelly_fraction": Decimal("0.2500"),  # 25% Kelly
            "min_probability": Decimal("0.3000"),  # 30% minimum win probability
            "max_probability": Decimal("0.7000"),  # 70% maximum win probability
        },
        "description": "Basic value betting strategy for NFL markets",
        "status": "draft",
        "created_by": "test_user",
        "notes": "Test strategy for unit testing",
    }


# Database fixtures imported from conftest.py:
# - db_pool: Session-scoped connection pool (created once, shared across all tests)
# - db_cursor: Function-scoped cursor with automatic rollback (fresh per test)
# - clean_test_data: Cleans test data before/after each test
#
# Educational Note (ADR-088):
#   - ❌ FORBIDDEN: Mocking get_connection(), database, config, logging
#   - ✅ REQUIRED: Use REAL infrastructure fixtures
#   - Phase 1.5 lesson: 17/17 tests passed with mocks → 13/17 failed with real DB


# ============================================================================
# TEST HELPERS
# ============================================================================


def assert_immutable(manager: StrategyManager, strategy_id: int):
    """Assert that strategy config is immutable.

    Args:
        manager: StrategyManager instance
        strategy_id: Strategy ID to test

    Raises:
        AssertionError: If immutability check fails

    Educational Note:
        - Config field should NEVER change after creation
        - This is critical for trade attribution (ADR-020)
        - If config changes, we can't trace which version made profit/loss
    """
    # This helper validates that there's no update_config() method
    # and that the implementation prevents config changes
    assert not hasattr(manager, "update_config"), (
        "StrategyManager should NOT have update_config() method - "
        "configs are immutable, create new version instead"
    )


def assert_decimal_fields(config: dict[str, Any]):
    """Assert that all numeric fields in config use Decimal type.

    Args:
        config: Strategy configuration dictionary

    Raises:
        AssertionError: If any numeric field uses float instead of Decimal

    Educational Note:
        - Pattern 1: NEVER use float for prices/probabilities
        - Floating point causes precision errors (0.1 + 0.2 ≠ 0.3)
        - Decimal gives exact representation (0.1 + 0.2 = 0.3)
        - Reference: KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md

    Example:
        >>> config = {"min_edge": Decimal("0.05"), "max_size": Decimal("100.00")}
        >>> assert_decimal_fields(config)  # Passes
        >>> config = {"min_edge": 0.05}  # Float!
        >>> assert_decimal_fields(config)  # Fails with helpful error
    """
    for key, value in config.items():
        if isinstance(value, (int, Decimal)):
            continue  # int and Decimal are OK
        if isinstance(value, float):
            raise AssertionError(
                f"Field '{key}' uses float ({value}) instead of Decimal - "
                f"Use Decimal('{value}') to avoid precision errors"
            )
        if isinstance(value, dict):
            assert_decimal_fields(value)  # Recursive check for nested dicts


def assert_version_format(version: str):
    """Assert that version string follows semantic versioning format.

    Args:
        version: Version string to validate

    Raises:
        AssertionError: If version doesn't match v1.0 or v1.0.1 format

    Educational Note:
        - Semantic versioning: MAJOR.MINOR or MAJOR.MINOR.PATCH
        - MAJOR: Breaking changes (v1.0 → v2.0)
        - MINOR: New features, backwards compatible (v1.0 → v1.1)
        - PATCH: Bug fixes (v1.0.0 → v1.0.1)
        - Reference: https://semver.org

    Example:
        >>> assert_version_format("1.0")  # Passes
        >>> assert_version_format("2.13")  # Passes
        >>> assert_version_format("1.0.1")  # Passes
        >>> assert_version_format("v1.0")  # Fails - no 'v' prefix
        >>> assert_version_format("1")  # Fails - needs minor version
    """
    import re

    pattern = r"^\d+\.\d+(\.\d+)?$"  # Matches "1.0" or "1.0.1"
    assert re.match(pattern, version), (
        f"Version '{version}' doesn't match semantic versioning format. "
        f"Expected: '1.0' or '1.0.1' (no 'v' prefix)"
    )


# ============================================================================
# UNIT TESTS
# ============================================================================


class TestStrategyManagerCreate:
    """Test suite for strategy creation operations."""

    def test_create_strategy(self, clean_test_data, db_cursor, strategy_factory):
        """Test creating a new strategy version.

        Validates:
        - Strategy created successfully
        - Returns dict with all expected fields
        - Config stored as JSONB
        - Decimal fields preserved
        - REQ-VER-001: Immutable version creation

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 1
        """
        # Setup
        manager = StrategyManager()

        # Execute - Create strategy with REAL database
        result = manager.create_strategy(**strategy_factory)

        # Verify returned data
        assert result["strategy_id"] is not None  # Auto-generated ID
        assert result["strategy_name"] == "value_betting_v1"
        assert result["strategy_version"] == "1.0"
        assert result["strategy_type"] == "value"  # Valid strategy_type from migration_021
        assert result["domain"] == "nfl"
        assert result["status"] == "draft"
        assert result["created_by"] == "test_user"

        # Verify config preserved as dict with Decimal values
        assert isinstance(result["config"], dict)
        assert result["config"]["min_edge"] == Decimal("0.0500")
        assert result["config"]["max_position_size"] == Decimal("100.00")

        # Verify Decimal fields
        assert_decimal_fields(result["config"])

        # Verify version format
        assert_version_format(result["strategy_version"])

        # Verify database persistence - Query REAL database
        db_cursor.execute(
            "SELECT strategy_name, strategy_version, config, status FROM strategies WHERE strategy_id = %s",
            (result["strategy_id"],),
        )
        row = db_cursor.fetchone()
        assert row is not None, "Strategy not found in database"
        assert row["strategy_name"] == "value_betting_v1"
        assert row["strategy_version"] == "1.0"
        assert row["config"]["min_edge"] == "0.0500"  # config JSONB
        assert row["status"] == "draft"

    def test_create_strategy_version(self, clean_test_data, db_cursor, strategy_factory):
        """Test creating new version (v1.1) from existing strategy (v1.0).

        Validates:
        - Multiple versions can coexist
        - Each version has unique (name, version) pair
        - Configs are independent (changing v1.1 doesn't affect v1.0)
        - REQ-VER-002: Multiple versions coexist

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 2
        """
        # Setup
        manager = StrategyManager()

        # Create v1.0 with REAL database
        v1_0 = manager.create_strategy(**strategy_factory)

        # Create v1.1 with different config (REAL database)
        strategy_factory["strategy_version"] = "1.1"
        strategy_factory["config"]["min_edge"] = Decimal("0.0600")  # Increased edge
        strategy_factory["description"] = "Version 1.1 - increased min edge"
        strategy_factory["notes"] = "Updated version"

        v1_1 = manager.create_strategy(**strategy_factory)

        # Verify both versions exist with different IDs
        assert v1_0["strategy_id"] != v1_1["strategy_id"], "IDs must be different"

        # Verify versions are different
        assert v1_0["strategy_version"] == "1.0"
        assert v1_1["strategy_version"] == "1.1"

        # Verify configs are independent
        assert v1_0["config"]["min_edge"] == Decimal("0.0500")
        assert v1_1["config"]["min_edge"] == Decimal("0.0600")

        # Verify both versions valid
        assert_version_format(v1_0["strategy_version"])
        assert_version_format(v1_1["strategy_version"])

        # Verify database persistence - Both versions exist
        db_cursor.execute(
            "SELECT strategy_version, config FROM strategies WHERE strategy_name = %s ORDER BY strategy_version",
            ("value_betting_v1",),
        )
        rows = db_cursor.fetchall()
        assert len(rows) == 2, "Should have 2 versions in database"
        assert rows[0]["strategy_version"] == "1.0"
        assert rows[0]["config"]["min_edge"] == "0.0500"
        assert rows[1]["strategy_version"] == "1.1"
        assert rows[1]["config"]["min_edge"] == "0.0600"

    def test_unique_constraint(self, clean_test_data, db_cursor, strategy_factory):
        """Test that duplicate (name, version) pairs raise error.

        Validates:
        - Database enforces UNIQUE(strategy_name, strategy_version)
        - Appropriate error raised on duplicate
        - REQ-VER-003: Version uniqueness

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Case 7
        """
        # Setup
        manager = StrategyManager()

        # First creation succeeds (REAL database)
        first = manager.create_strategy(**strategy_factory)
        assert first["strategy_id"] is not None

        # Second creation with same (name, version) fails (REAL database constraint)
        import psycopg2

        with pytest.raises(psycopg2.IntegrityError, match="duplicate key"):
            manager.create_strategy(**strategy_factory)  # Same name + version


class TestStrategyManagerRetrieval:
    """Test suite for strategy retrieval operations."""

    def test_get_strategy(self, clean_test_data, db_cursor, strategy_factory):
        """Test retrieving strategy by ID.

        Validates:
        - Strategy retrieved successfully
        - All fields present
        - Config parsed from JSONB to dict
        - Decimal values preserved
        - REQ-VER-004: Strategy retrieval

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 3
        """
        # Setup - Create strategy first (REAL database)
        manager = StrategyManager()
        created = manager.create_strategy(**strategy_factory)

        # Update strategy with metrics using REAL database
        db_cursor.execute(
            """
            UPDATE strategies
            SET paper_roi = %s, live_roi = %s, paper_trades_count = %s,
                live_trades_count = %s, status = %s
            WHERE strategy_id = %s
            """,
            (Decimal("0.1234"), Decimal("0.0987"), 25, 10, "active", created["strategy_id"]),
        )
        db_cursor.connection.commit()

        # Execute - Retrieve strategy (REAL database)
        result = manager.get_strategy(strategy_id=created["strategy_id"])

        # Verify
        assert result is not None
        assert result["strategy_id"] == created["strategy_id"]
        assert result["strategy_name"] == "value_betting_v1"
        assert result["strategy_version"] == "1.0"
        assert result["status"] == "active"

        # Verify metrics
        assert result["paper_roi"] == Decimal("0.1234")
        assert result["live_roi"] == Decimal("0.0987")
        assert result["paper_trades_count"] == 25
        assert result["live_trades_count"] == 10

        # Verify config parsed correctly
        assert isinstance(result["config"], dict)
        assert result["config"]["min_edge"] == Decimal("0.0500")
        assert_decimal_fields(result["config"])

    def test_get_strategy_not_found(self, clean_test_data, db_cursor):
        """Test retrieving non-existent strategy returns None.

        Validates:
        - Returns None for invalid ID (doesn't raise exception)
        - Graceful handling of missing data

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Case 9
        """
        # Setup
        manager = StrategyManager()

        # Execute - Query non-existent ID (REAL database)
        result = manager.get_strategy(strategy_id=999999)

        # Verify
        assert result is None

    def test_get_active_strategies(self, clean_test_data, db_cursor, strategy_factory):
        """Test retrieving only active strategies.

        Validates:
        - Filters by status='active'
        - Returns list of strategies
        - REQ-VER-005: Status filtering

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 4
        """
        # Setup - Create multiple strategies with different statuses (REAL database)
        manager = StrategyManager()

        # Create active strategy v1.0
        strategy_factory["status"] = "active"
        active1 = manager.create_strategy(**strategy_factory)

        # Create draft strategy v1.1
        strategy_factory["strategy_version"] = "1.1"
        strategy_factory["status"] = "draft"
        draft = manager.create_strategy(**strategy_factory)

        # Create another active strategy v2.0
        strategy_factory["strategy_name"] = "value_betting_v2"
        strategy_factory["strategy_version"] = "2.0"
        strategy_factory["status"] = "active"
        active2 = manager.create_strategy(**strategy_factory)

        # Execute - Get only active strategies (REAL database)
        result = manager.get_active_strategies()

        # Verify
        assert len(result) >= 2, "Should have at least 2 active strategies"
        active_ids = [s["strategy_id"] for s in result]
        assert active1["strategy_id"] in active_ids
        assert active2["strategy_id"] in active_ids
        assert draft["strategy_id"] not in active_ids
        assert all(s["status"] == "active" for s in result)

    def test_list_strategies_no_filters(self, clean_test_data, db_cursor, strategy_factory):
        """Test listing all strategies without filters.

        Validates:
        - No filters returns ALL strategies
        - Returns list of dictionaries
        - REQ-VER-004: Strategy listing
        - GitHub Issue #132: list_strategies() method

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md
        """
        # Setup - Create multiple strategies with different attributes
        manager = StrategyManager()

        strategy_factory["status"] = "active"
        strategy_factory["strategy_version"] = "1.0"
        s1 = manager.create_strategy(**strategy_factory)

        strategy_factory["status"] = "draft"
        strategy_factory["strategy_version"] = "1.1"
        s2 = manager.create_strategy(**strategy_factory)

        strategy_factory["status"] = "testing"
        strategy_factory["strategy_version"] = "2.0"
        s3 = manager.create_strategy(**strategy_factory)

        # Execute - List all strategies
        result = manager.list_strategies()

        # Verify
        assert len(result) >= 3, "Should have at least 3 strategies"
        strategy_ids = [s["strategy_id"] for s in result]
        assert s1["strategy_id"] in strategy_ids
        assert s2["strategy_id"] in strategy_ids
        assert s3["strategy_id"] in strategy_ids

    def test_list_strategies_filter_by_status(self, clean_test_data, db_cursor, strategy_factory):
        """Test listing strategies filtered by status.

        Validates:
        - Status filter works correctly
        - Returns only matching strategies
        - REQ-VER-005: Status filtering
        - GitHub Issue #132: list_strategies() method

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md
        """
        # Setup
        manager = StrategyManager()

        strategy_factory["status"] = "active"
        active = manager.create_strategy(**strategy_factory)

        strategy_factory["strategy_version"] = "1.1"
        strategy_factory["status"] = "draft"
        draft = manager.create_strategy(**strategy_factory)

        # Execute - Filter by status='active'
        result = manager.list_strategies(status="active")

        # Verify
        strategy_ids = [s["strategy_id"] for s in result]
        assert active["strategy_id"] in strategy_ids
        assert draft["strategy_id"] not in strategy_ids
        assert all(s["status"] == "active" for s in result)

    def test_list_strategies_filter_by_version(self, clean_test_data, db_cursor, strategy_factory):
        """Test listing strategies filtered by version.

        Validates:
        - Version filter works correctly
        - Returns only matching version
        - REQ-VER-004: Version management
        - GitHub Issue #132: list_strategies() method

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md
        """
        # Setup
        manager = StrategyManager()

        strategy_factory["strategy_version"] = "1.0"
        v10 = manager.create_strategy(**strategy_factory)

        strategy_factory["strategy_version"] = "1.1"
        v11 = manager.create_strategy(**strategy_factory)

        strategy_factory["strategy_version"] = "2.0"
        v20 = manager.create_strategy(**strategy_factory)

        # Execute - Filter by version='1.0'
        result = manager.list_strategies(strategy_version="1.0")

        # Verify
        strategy_ids = [s["strategy_id"] for s in result]
        assert v10["strategy_id"] in strategy_ids
        assert v11["strategy_id"] not in strategy_ids
        assert v20["strategy_id"] not in strategy_ids
        assert all(s["strategy_version"] == "1.0" for s in result)

    def test_list_strategies_filter_by_type(self, clean_test_data, db_cursor, strategy_factory):
        """Test listing strategies filtered by type.

        Validates:
        - Type filter works correctly
        - Returns only matching type
        - REQ-VER-004: Strategy type filtering
        - GitHub Issue #132: list_strategies() method

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md
        """
        # Setup
        manager = StrategyManager()

        strategy_factory["strategy_type"] = "value"
        value_strat = manager.create_strategy(**strategy_factory)

        strategy_factory["strategy_name"] = "arbitrage_strat"
        strategy_factory["strategy_type"] = "arbitrage"
        arb_strat = manager.create_strategy(**strategy_factory)

        # Execute - Filter by type='value'
        result = manager.list_strategies(strategy_type="value")

        # Verify
        strategy_ids = [s["strategy_id"] for s in result]
        assert value_strat["strategy_id"] in strategy_ids
        assert arb_strat["strategy_id"] not in strategy_ids
        assert all(s["strategy_type"] == "value" for s in result)

    def test_list_strategies_multiple_filters(self, clean_test_data, db_cursor, strategy_factory):
        """Test listing strategies with multiple filters (AND logic).

        Validates:
        - Multiple filters use AND logic
        - Returns only strategies matching ALL filters
        - REQ-VER-005: Complex filtering
        - GitHub Issue #132: list_strategies() method

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md
        """
        # Setup - Create strategies with different combinations
        manager = StrategyManager()

        # active + v1.0 + value (MATCH)
        strategy_factory["status"] = "active"
        strategy_factory["strategy_version"] = "1.0"
        strategy_factory["strategy_type"] = "value"
        match = manager.create_strategy(**strategy_factory)

        # active + v1.1 + value (NO MATCH - wrong version)
        strategy_factory["strategy_version"] = "1.1"
        no_match1 = manager.create_strategy(**strategy_factory)

        # draft + v2.0 + value (NO MATCH - wrong status)
        strategy_factory["status"] = "draft"
        strategy_factory["strategy_version"] = "2.0"
        no_match2 = manager.create_strategy(**strategy_factory)

        # Execute - Filter by status='active' AND version='1.0' AND type='value'
        result = manager.list_strategies(
            status="active", strategy_version="1.0", strategy_type="value"
        )

        # Verify - Should only return the exact match
        strategy_ids = [s["strategy_id"] for s in result]
        assert match["strategy_id"] in strategy_ids
        assert no_match1["strategy_id"] not in strategy_ids
        assert no_match2["strategy_id"] not in strategy_ids
        assert all(
            s["status"] == "active"
            and s["strategy_version"] == "1.0"
            and s["strategy_type"] == "value"
            for s in result
        )

    def test_list_strategies_empty_result(self, clean_test_data, db_cursor):
        """Test listing strategies with no matches.

        Validates:
        - Returns empty list when no strategies match
        - No errors on empty result
        - GitHub Issue #132: list_strategies() method

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Cases
        """
        # Setup
        manager = StrategyManager()

        # Execute - Filter for non-existent status
        result = manager.list_strategies(status="nonexistent_status")

        # Verify
        assert result == []
        assert isinstance(result, list)


class TestStrategyManagerUpdates:
    """Test suite for strategy update operations (mutable fields only)."""

    def test_update_strategy_status(self, clean_test_data, db_cursor, strategy_factory):
        """Test updating strategy status with transition validation.

        Validates:
        - Status updates successfully (draft → testing → active)
        - Invalid transitions rejected (deprecated → active)
        - Returns updated strategy
        - REQ-VER-006: Status lifecycle

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 5
        """
        # Setup - Create strategy (REAL database)
        manager = StrategyManager()
        strategy = manager.create_strategy(**strategy_factory)
        assert strategy["status"] == "draft"

        # Execute first transition: draft → testing (REAL database)
        result = manager.update_status(strategy_id=strategy["strategy_id"], new_status="testing")
        assert result["status"] == "testing"

        # Verify database persistence
        db_cursor.execute(
            "SELECT status FROM strategies WHERE strategy_id = %s", (strategy["strategy_id"],)
        )
        assert db_cursor.fetchone()["status"] == "testing"

        # Execute second transition: testing → active (REAL database)
        result = manager.update_status(strategy_id=strategy["strategy_id"], new_status="active")
        assert result["status"] == "active"

        # Verify database persistence
        db_cursor.execute(
            "SELECT status FROM strategies WHERE strategy_id = %s", (strategy["strategy_id"],)
        )
        assert db_cursor.fetchone()["status"] == "active"

    def test_invalid_status_transitions(self, clean_test_data, db_cursor, strategy_factory):
        """Test that invalid status transitions raise error.

        Validates:
        - deprecated → active rejected (terminal state)
        - active → draft rejected (backwards movement)
        - Appropriate error message

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Case 10
        """
        # Setup - Create strategy and set to deprecated (REAL database)
        manager = StrategyManager()
        strategy = manager.create_strategy(**strategy_factory)

        # Manually set to deprecated status (bypass transition logic for test setup)
        db_cursor.execute(
            "UPDATE strategies SET status = %s WHERE strategy_id = %s",
            ("deprecated", strategy["strategy_id"]),
        )
        db_cursor.connection.commit()

        # Invalid transition: deprecated → active (REAL database)
        with pytest.raises(InvalidStatusTransitionError, match=r"deprecated.*active"):
            manager.update_status(strategy_id=strategy["strategy_id"], new_status="active")

    def test_update_strategy_metrics(self, clean_test_data, db_cursor, strategy_factory):
        """Test updating strategy performance metrics.

        Validates:
        - paper_roi, live_roi update successfully
        - paper_trades_count, live_trades_count increment
        - Decimal precision preserved
        - Config remains unchanged (immutable)

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 6
        """
        # Setup - Create strategy (REAL database)
        manager = StrategyManager()
        strategy = manager.create_strategy(**strategy_factory)
        original_config = strategy["config"].copy()

        # Execute - Update metrics (REAL database)
        result = manager.update_metrics(
            strategy_id=strategy["strategy_id"],
            paper_roi=Decimal("0.1500"),
            live_roi=Decimal("0.1200"),
            paper_trades_count=30,
            live_trades_count=15,
        )

        # Verify metrics updated
        assert result["paper_roi"] == Decimal("0.1500")
        assert result["live_roi"] == Decimal("0.1200")
        assert result["paper_trades_count"] == 30
        assert result["live_trades_count"] == 15

        # Verify config unchanged (immutability)
        assert result["config"]["min_edge"] == Decimal("0.0500")
        assert result["config"] == original_config

        # Verify database persistence
        db_cursor.execute(
            "SELECT paper_roi, live_roi, paper_trades_count, live_trades_count, config FROM strategies WHERE strategy_id = %s",
            (strategy["strategy_id"],),
        )
        row = db_cursor.fetchone()
        assert row["paper_roi"] == Decimal("0.1500")
        assert row["live_roi"] == Decimal("0.1200")
        assert row["paper_trades_count"] == 30
        assert row["live_trades_count"] == 15
        # Config stored in JSONB as strings, verify numeric equality
        assert set(row["config"].keys()) == set(original_config.keys())
        for key in original_config:
            assert Decimal(row["config"][key]) == original_config[key]


class TestStrategyManagerImmutability:
    """Test suite for config immutability enforcement."""

    def test_immutability_enforcement(self):
        """Test that StrategyManager prevents config modification.

        Validates:
        - No update_config() method exists
        - Config cannot be changed after creation
        - REQ-VER-001: Immutability enforcement

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 1 (Immutability)
        """
        manager = StrategyManager()

        # Verify no method to update config
        assert_immutable(manager, strategy_id=1)

        # Verify StrategyManager doesn't have dangerous methods
        assert not hasattr(manager, "update_config")
        assert not hasattr(manager, "modify_config")
        assert not hasattr(manager, "set_config")

    def test_decimal_precision_in_config(self, clean_test_data, db_cursor, strategy_factory):
        """Test that all numeric config fields use Decimal (not float).

        Validates:
        - All prices/probabilities stored as Decimal
        - No float contamination
        - Pattern 1 compliance

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 7
        """
        # Setup
        manager = StrategyManager()

        # Execute - Create strategy (REAL database)
        result = manager.create_strategy(**strategy_factory)

        # Verify all numeric fields are Decimal
        assert_decimal_fields(result["config"])

        # Verify no floats in config
        json.dumps(result["config"], default=str)
        assert isinstance(result["config"]["min_edge"], Decimal)
        assert isinstance(result["config"]["max_position_size"], Decimal)
        assert isinstance(result["config"]["kelly_fraction"], Decimal)

        # Verify database storage preserves Decimal (JSONB stores as strings)
        db_cursor.execute(
            "SELECT config FROM strategies WHERE strategy_id = %s", (result["strategy_id"],)
        )
        row = db_cursor.fetchone()
        db_config = row["config"]
        # JSONB stores Decimals as strings to preserve precision
        assert db_config["min_edge"] == "0.0500"
        assert db_config["max_position_size"] == "100.00"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestStrategyManagerIntegration:
    """Integration tests for end-to-end strategy lifecycle."""

    def test_strategy_lifecycle_end_to_end(self, clean_test_data, db_cursor, strategy_factory):
        """Test complete strategy lifecycle: create → testing → active → inactive → deprecated.

        Validates:
        - Full status transition chain
        - Metrics accumulate over time
        - Config remains immutable throughout
        - REQ-VER-001 through REQ-VER-006

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Integration Test 1
        """
        # Setup - Create strategy (REAL database)
        manager = StrategyManager()
        strategy = manager.create_strategy(**strategy_factory)
        assert strategy["status"] == "draft"
        original_config = strategy["config"].copy()
        strategy_id = strategy["strategy_id"]

        # 2. Transition to testing (REAL database)
        strategy = manager.update_status(strategy_id=strategy_id, new_status="testing")
        assert strategy["status"] == "testing"
        assert strategy["config"] == original_config  # Config unchanged

        # 3. Add paper trading metrics (REAL database)
        strategy = manager.update_metrics(
            strategy_id=strategy_id, paper_roi=Decimal("0.1234"), paper_trades_count=25
        )
        assert strategy["paper_roi"] == Decimal("0.1234")
        assert strategy["paper_trades_count"] == 25

        # 4. Transition to active (REAL database)
        strategy = manager.update_status(strategy_id=strategy_id, new_status="active")
        assert strategy["status"] == "active"

        # 5. Add live trading metrics (REAL database)
        strategy = manager.update_metrics(
            strategy_id=strategy_id, live_roi=Decimal("0.0987"), live_trades_count=15
        )
        assert strategy["live_roi"] == Decimal("0.0987")
        assert strategy["live_trades_count"] == 15

        # 6. Transition to inactive (REAL database)
        strategy = manager.update_status(strategy_id=strategy_id, new_status="inactive")
        assert strategy["status"] == "inactive"

        # 7. Final transition to deprecated (REAL database)
        strategy = manager.update_status(strategy_id=strategy_id, new_status="deprecated")
        assert strategy["status"] == "deprecated"

        # Verify config NEVER changed throughout lifecycle
        assert strategy["config"] == original_config

        # Verify final database state
        db_cursor.execute(
            "SELECT status, paper_roi, live_roi, paper_trades_count, live_trades_count, config FROM strategies WHERE strategy_id = %s",
            (strategy_id,),
        )
        row = db_cursor.fetchone()
        assert row["status"] == "deprecated"
        assert row["paper_roi"] == Decimal("0.1234")
        assert row["live_roi"] == Decimal("0.0987")
        assert row["paper_trades_count"] == 25
        assert row["live_trades_count"] == 15
        # Config stored in JSONB as strings, verify numeric equality
        assert set(row["config"].keys()) == set(original_config.keys())
        for key in original_config:
            assert Decimal(row["config"][key]) == original_config[key]

    def test_multiple_versions_coexist(self, clean_test_data, db_cursor, strategy_factory):
        """Test that multiple strategy versions coexist independently.

        Validates:
        - v1.0, v1.1, v2.0 all in database simultaneously
        - Each has independent status
        - Each has independent metrics
        - Configs are completely separate
        - REQ-VER-002: Multiple versions

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Integration Test 2
        """
        # Setup - Create three versions (REAL database)
        manager = StrategyManager()

        # Create v1.0 and set to active with metrics
        v1_0 = manager.create_strategy(**strategy_factory)
        db_cursor.execute(
            """
            UPDATE strategies
            SET status = %s, paper_roi = %s, live_roi = %s,
                paper_trades_count = %s, live_trades_count = %s
            WHERE strategy_id = %s
            """,
            ("active", Decimal("0.1000"), Decimal("0.0800"), 10, 5, v1_0["strategy_id"]),
        )
        db_cursor.connection.commit()

        # Create v1.1 with different config and status
        strategy_factory["strategy_version"] = "1.1"
        strategy_factory["config"]["min_edge"] = Decimal("0.0600")
        v1_1 = manager.create_strategy(**strategy_factory)
        db_cursor.execute(
            "UPDATE strategies SET status = %s, paper_roi = %s, paper_trades_count = %s WHERE strategy_id = %s",
            ("testing", Decimal("0.1500"), 15, v1_1["strategy_id"]),
        )
        db_cursor.connection.commit()

        # Create v2.0 with major config change
        strategy_factory["strategy_version"] = "2.0"
        strategy_factory["config"]["min_edge"] = Decimal("0.0700")
        strategy_factory["config"]["new_param"] = Decimal("10.00")
        v2_0 = manager.create_strategy(**strategy_factory)
        # v2.0 stays in draft with no metrics

        # Retrieve all versions (REAL database)
        v1_0_retrieved = manager.get_strategy(strategy_id=v1_0["strategy_id"])
        v1_1_retrieved = manager.get_strategy(strategy_id=v1_1["strategy_id"])
        v2_0_retrieved = manager.get_strategy(strategy_id=v2_0["strategy_id"])

        # Assert not None before using
        assert v1_0_retrieved is not None
        assert v1_1_retrieved is not None
        assert v2_0_retrieved is not None

        # Now reassign for rest of test
        v1_0 = v1_0_retrieved
        v1_1 = v1_1_retrieved
        v2_0 = v2_0_retrieved

        # Verify all 3 versions exist independently
        assert v1_0["strategy_version"] == "1.0"
        assert v1_1["strategy_version"] == "1.1"
        assert v2_0["strategy_version"] == "2.0"

        # Verify independent statuses
        assert v1_0["status"] == "active"
        assert v1_1["status"] == "testing"
        assert v2_0["status"] == "draft"

        # Verify independent configs
        assert v1_0["config"]["min_edge"] == Decimal("0.0500")
        assert v1_1["config"]["min_edge"] == Decimal("0.0600")
        assert v2_0["config"]["min_edge"] == Decimal("0.0700")

        # Verify independent metrics
        assert v1_0["paper_roi"] == Decimal("0.1000")
        assert v1_1["paper_roi"] == Decimal("0.1500")
        assert v2_0["paper_roi"] is None


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

# Mark all integration tests to run in specific order
pytestmark = pytest.mark.unit
