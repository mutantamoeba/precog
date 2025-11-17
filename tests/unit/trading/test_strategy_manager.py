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
from unittest.mock import MagicMock, patch

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
        "approach": "value_betting",
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


@pytest.fixture
def mock_cursor():
    """Mock database cursor for testing.

    Returns:
        MagicMock cursor with common database operations

    Educational Note:
        - Mocks psycopg2 cursor interface
        - fetchone() returns single row tuple
        - fetchall() returns list of row tuples
        - description provides column metadata
    """
    cursor = MagicMock()
    cursor.description = [
        ("strategy_id",),
        ("strategy_name",),
        ("strategy_version",),
        ("approach",),
        ("domain",),
        ("config",),
        ("description",),
        ("status",),
        ("paper_roi",),
        ("live_roi",),
        ("paper_trades_count",),
        ("live_trades_count",),
        ("created_at",),
        ("created_by",),
        ("notes",),
    ]
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """Mock database connection for testing.

    Args:
        mock_cursor: Mocked cursor fixture

    Returns:
        MagicMock connection with cursor() method

    Educational Note:
        - Connection provides cursor factory
        - commit() and rollback() are no-ops in tests
        - Used with patch('precog.database.get_connection')
        - cursor() returns mock_cursor directly (not using context manager)
    """
    connection = MagicMock()
    connection.cursor.return_value = mock_cursor  # Direct return, not __enter__
    return connection


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

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_strategy(
        self, mock_get_connection, mock_connection, mock_cursor, strategy_factory
    ):
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
        mock_get_connection.return_value = mock_connection
        # Note: PostgreSQL returns JSONB as dict (psycopg2 automatic conversion)
        mock_cursor.fetchone.return_value = (
            1,  # strategy_id
            "value_betting_v1",  # strategy_name
            "1.0",  # strategy_version
            "value_betting",  # approach
            "nfl",  # domain
            {  # config (JSONB → dict, automatic conversion by psycopg2)
                "min_edge": "0.0500",
                "max_position_size": "100.00",
                "kelly_fraction": "0.2500",
                "min_probability": "0.3000",
                "max_probability": "0.7000",
            },
            "Basic value betting strategy for NFL markets",  # description
            "draft",  # status
            None,  # paper_roi
            None,  # live_roi
            0,  # paper_trades_count
            0,  # live_trades_count
            "2025-11-16 12:00:00",  # created_at
            "test_user",  # created_by
            "Test strategy for unit testing",  # notes
        )

        manager = StrategyManager()

        # Execute
        result = manager.create_strategy(**strategy_factory)

        # Verify
        assert result["strategy_id"] == 1
        assert result["strategy_name"] == "value_betting_v1"
        assert result["strategy_version"] == "1.0"
        assert result["approach"] == "value_betting"
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

        # Verify SQL execution
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO strategies" in sql
        assert "config" in sql  # JSONB field

    @patch("precog.trading.strategy_manager.get_connection")
    def test_create_strategy_version(
        self, mock_get_connection, mock_connection, mock_cursor, strategy_factory
    ):
        """Test creating new version (v1.1) from existing strategy (v1.0).

        Validates:
        - Multiple versions can coexist
        - Each version has unique (name, version) pair
        - Configs are independent (changing v1.1 doesn't affect v1.0)
        - REQ-VER-002: Multiple versions coexist

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 2
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        # First call: Create v1.0
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500", "max_position_size": "100.00"},
            "Version 1.0",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-16 12:00:00",
            "test_user",
            "Original version",
        )

        manager = StrategyManager()
        v1_0 = manager.create_strategy(**strategy_factory)

        # Second call: Create v1.1 with different config
        strategy_factory["strategy_version"] = "1.1"
        strategy_factory["config"]["min_edge"] = Decimal("0.0600")  # Increased edge
        strategy_factory["description"] = "Version 1.1 - increased min edge"
        strategy_factory["notes"] = "Updated version"

        mock_cursor.fetchone.return_value = (
            2,  # Different ID
            "value_betting_v1",
            "1.1",  # Different version
            "value_betting",
            "nfl",
            {"min_edge": "0.0600", "max_position_size": "100.00"},  # Different config
            "Version 1.1 - increased min edge",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-16 13:00:00",
            "test_user",
            "Updated version",
        )

        v1_1 = manager.create_strategy(**strategy_factory)

        # Verify both versions exist with different IDs
        assert v1_0["strategy_id"] == 1
        assert v1_1["strategy_id"] == 2

        # Verify versions are different
        assert v1_0["strategy_version"] == "1.0"
        assert v1_1["strategy_version"] == "1.1"

        # Verify configs are independent
        assert v1_0["config"]["min_edge"] == Decimal("0.0500")
        assert v1_1["config"]["min_edge"] == Decimal("0.0600")

        # Verify both versions valid
        assert_version_format(v1_0["strategy_version"])
        assert_version_format(v1_1["strategy_version"])

    @patch("precog.trading.strategy_manager.get_connection")
    def test_unique_constraint(
        self, mock_get_connection, mock_connection, mock_cursor, strategy_factory
    ):
        """Test that duplicate (name, version) pairs raise error.

        Validates:
        - Database enforces UNIQUE(strategy_name, strategy_version)
        - Appropriate error raised on duplicate
        - REQ-VER-003: Version uniqueness

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Case 7
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        # First creation succeeds
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},
            "Version 1.0",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-16 12:00:00",
            "test_user",
            "Original",
        )

        manager = StrategyManager()
        first = manager.create_strategy(**strategy_factory)
        assert first["strategy_id"] == 1

        # Second creation with same (name, version) fails
        import psycopg2

        mock_cursor.execute.side_effect = psycopg2.IntegrityError(
            "duplicate key value violates unique constraint"
        )

        with pytest.raises(psycopg2.IntegrityError, match="duplicate key"):
            manager.create_strategy(**strategy_factory)  # Same name + version


class TestStrategyManagerRetrieval:
    """Test suite for strategy retrieval operations."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_get_strategy(self, mock_get_connection, mock_connection, mock_cursor):
        """Test retrieving strategy by ID.

        Validates:
        - Strategy retrieved successfully
        - All fields present
        - Config parsed from JSONB to dict
        - Decimal values preserved
        - REQ-VER-004: Strategy retrieval

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 3
        """
        # Setup
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500", "max_position_size": "100.00"},
            "Test strategy",
            "active",
            Decimal("0.1234"),  # paper_roi
            Decimal("0.0987"),  # live_roi
            25,  # paper_trades_count
            10,  # live_trades_count
            "2025-11-16 12:00:00",
            "test_user",
            "Test notes",
        )

        manager = StrategyManager()

        # Execute
        result = manager.get_strategy(strategy_id=1)

        # Verify
        assert result is not None
        assert result["strategy_id"] == 1
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

        # Verify SQL execution
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "FROM strategies" in sql
        assert "WHERE strategy_id = %s" in sql

    @patch("precog.trading.strategy_manager.get_connection")
    def test_get_strategy_not_found(self, mock_get_connection, mock_connection, mock_cursor):
        """Test retrieving non-existent strategy returns None.

        Validates:
        - Returns None for invalid ID (doesn't raise exception)
        - Graceful handling of missing data

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Case 9
        """
        # Setup
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = None  # No rows found

        manager = StrategyManager()

        # Execute
        result = manager.get_strategy(strategy_id=999)

        # Verify
        assert result is None

    @patch("precog.trading.strategy_manager.get_connection")
    def test_get_active_strategies(self, mock_get_connection, mock_connection, mock_cursor):
        """Test retrieving only active strategies.

        Validates:
        - Filters by status='active'
        - Returns list of strategies
        - REQ-VER-005: Status filtering

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 4
        """
        # Setup
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchall.return_value = [
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Active strategy 1",
                "active",
                Decimal("0.1234"),
                None,
                10,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes 1",
            ),
            (
                3,
                "value_betting_v2",
                "2.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0600"},
                "Active strategy 2",
                "active",
                Decimal("0.0987"),
                Decimal("0.0654"),
                15,
                5,
                "2025-11-16 13:00:00",
                "test_user",
                "Notes 2",
            ),
        ]

        manager = StrategyManager()

        # Execute
        result = manager.get_active_strategies()

        # Verify
        assert len(result) == 2
        assert all(s["status"] == "active" for s in result)
        assert result[0]["strategy_id"] == 1
        assert result[1]["strategy_id"] == 3

        # Verify SQL execution
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "FROM strategies" in sql
        assert "status =" in sql  # Could be parameterized or hardcoded


class TestStrategyManagerUpdates:
    """Test suite for strategy update operations (mutable fields only)."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_update_strategy_status(self, mock_get_connection, mock_connection, mock_cursor):
        """Test updating strategy status with transition validation.

        Validates:
        - Status updates successfully (draft → testing → active)
        - Invalid transitions rejected (deprecated → active)
        - Returns updated strategy
        - REQ-VER-006: Status lifecycle

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 5
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        manager = StrategyManager()

        # Valid transition: draft → testing (2 fetchone calls)
        mock_cursor.fetchone.side_effect = [
            # First call: get current status (draft)
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "draft",
                None,
                None,
                0,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            # Second call: return updated strategy (testing)
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "testing",
                None,
                None,
                0,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            # Third call: get current status (testing) for next transition
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "testing",
                None,
                None,
                0,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            # Fourth call: return updated strategy (active)
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "active",
                None,
                None,
                0,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
        ]

        # Execute first transition: draft → testing
        result = manager.update_status(strategy_id=1, new_status="testing")
        assert result["status"] == "testing"

        # Execute second transition: testing → active
        result = manager.update_status(strategy_id=1, new_status="active")
        assert result["status"] == "active"

    @patch("precog.trading.strategy_manager.get_connection")
    def test_invalid_status_transitions(self, mock_get_connection, mock_connection, mock_cursor):
        """Test that invalid status transitions raise error.

        Validates:
        - deprecated → active rejected (terminal state)
        - active → draft rejected (backwards movement)
        - Appropriate error message

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Edge Case 10
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        # Current state: deprecated
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},
            "Test strategy",
            "deprecated",  # Terminal state
            None,
            None,
            0,
            0,
            "2025-11-16 12:00:00",
            "test_user",
            "Notes",
        )

        manager = StrategyManager()

        # Invalid transition: deprecated → active
        with pytest.raises(InvalidStatusTransitionError, match=r"deprecated.*active"):
            manager.update_status(strategy_id=1, new_status="active")

    @patch("precog.trading.strategy_manager.get_connection")
    def test_update_strategy_metrics(self, mock_get_connection, mock_connection, mock_cursor):
        """Test updating strategy performance metrics.

        Validates:
        - paper_roi, live_roi update successfully
        - paper_trades_count, live_trades_count increment
        - Decimal precision preserved
        - Config remains unchanged (immutable)

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 6
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        # Updated strategy with new metrics
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},  # Config unchanged
            "Test strategy",
            "active",
            Decimal("0.1500"),  # paper_roi updated
            Decimal("0.1200"),  # live_roi updated
            30,  # paper_trades_count updated
            15,  # live_trades_count updated
            "2025-11-16 12:00:00",
            "test_user",
            "Notes",
        )

        manager = StrategyManager()

        # Execute
        result = manager.update_metrics(
            strategy_id=1,
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

        # Verify SQL execution
        assert mock_cursor.execute.call_count >= 1


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

    @patch("precog.trading.strategy_manager.get_connection")
    def test_decimal_precision_in_config(
        self, mock_get_connection, mock_connection, mock_cursor, strategy_factory
    ):
        """Test that all numeric config fields use Decimal (not float).

        Validates:
        - All prices/probabilities stored as Decimal
        - No float contamination
        - Pattern 1 compliance

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Critical Scenario 7
        """
        # Setup
        mock_get_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {
                "min_edge": "0.0500",
                "max_position_size": "100.00",
                "kelly_fraction": "0.2500",
            },
            "Test strategy",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-16 12:00:00",
            "test_user",
            "Notes",
        )

        manager = StrategyManager()

        # Execute
        result = manager.create_strategy(**strategy_factory)

        # Verify all numeric fields are Decimal
        assert_decimal_fields(result["config"])

        # Verify no floats in config
        json.dumps(result["config"], default=str)
        assert isinstance(result["config"]["min_edge"], Decimal)
        assert isinstance(result["config"]["max_position_size"], Decimal)
        assert isinstance(result["config"]["kelly_fraction"], Decimal)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestStrategyManagerIntegration:
    """Integration tests for end-to-end strategy lifecycle."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_strategy_lifecycle_end_to_end(
        self, mock_get_connection, mock_connection, mock_cursor, strategy_factory
    ):
        """Test complete strategy lifecycle: create → testing → active → inactive → deprecated.

        Validates:
        - Full status transition chain
        - Metrics accumulate over time
        - Config remains immutable throughout
        - REQ-VER-001 through REQ-VER-006

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Integration Test 1
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        manager = StrategyManager()

        # 1. Create strategy (draft)
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},
            "Test strategy",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-16 12:00:00",
            "test_user",
            "Notes",
        )

        strategy = manager.create_strategy(**strategy_factory)
        assert strategy["status"] == "draft"
        original_config = strategy["config"].copy()

        # 2. Transition to testing
        mock_cursor.fetchone.side_effect = [
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "draft",
                None,
                None,
                0,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "testing",
                None,
                None,
                0,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
        ]

        strategy = manager.update_status(strategy_id=1, new_status="testing")
        assert strategy["status"] == "testing"
        assert strategy["config"] == original_config  # Config unchanged

        # 3. Add paper trading metrics
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},
            "Test strategy",
            "testing",
            Decimal("0.1234"),  # paper_roi
            None,
            25,  # paper_trades_count
            0,
            "2025-11-16 12:00:00",
            "test_user",
            "Notes",
        )

        strategy = manager.update_metrics(
            strategy_id=1, paper_roi=Decimal("0.1234"), paper_trades_count=25
        )
        assert strategy["paper_roi"] == Decimal("0.1234")
        assert strategy["paper_trades_count"] == 25

        # 4. Transition to active
        mock_cursor.fetchone.side_effect = [
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "testing",
                Decimal("0.1234"),
                None,
                25,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "active",
                Decimal("0.1234"),
                None,
                25,
                0,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
        ]

        strategy = manager.update_status(strategy_id=1, new_status="active")
        assert strategy["status"] == "active"

        # 5. Add live trading metrics
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},
            "Test strategy",
            "active",
            Decimal("0.1234"),
            Decimal("0.0987"),  # live_roi
            25,
            15,  # live_trades_count
            "2025-11-16 12:00:00",
            "test_user",
            "Notes",
        )

        strategy = manager.update_metrics(
            strategy_id=1, live_roi=Decimal("0.0987"), live_trades_count=15
        )
        assert strategy["live_roi"] == Decimal("0.0987")
        assert strategy["live_trades_count"] == 15

        # 6. Transition to inactive
        mock_cursor.fetchone.side_effect = [
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "active",
                Decimal("0.1234"),
                Decimal("0.0987"),
                25,
                15,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "inactive",
                Decimal("0.1234"),
                Decimal("0.0987"),
                25,
                15,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
        ]

        strategy = manager.update_status(strategy_id=1, new_status="inactive")
        assert strategy["status"] == "inactive"

        # 7. Final transition to deprecated
        mock_cursor.fetchone.side_effect = [
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "inactive",
                Decimal("0.1234"),
                Decimal("0.0987"),
                25,
                15,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
            (
                1,
                "value_betting_v1",
                "1.0",
                "value_betting",
                "nfl",
                {"min_edge": "0.0500"},
                "Test strategy",
                "deprecated",
                Decimal("0.1234"),
                Decimal("0.0987"),
                25,
                15,
                "2025-11-16 12:00:00",
                "test_user",
                "Notes",
            ),
        ]

        strategy = manager.update_status(strategy_id=1, new_status="deprecated")
        assert strategy["status"] == "deprecated"

        # Verify config NEVER changed throughout lifecycle
        assert strategy["config"] == original_config

    @patch("precog.trading.strategy_manager.get_connection")
    def test_multiple_versions_coexist(self, mock_get_connection, mock_connection, mock_cursor):
        """Test that multiple strategy versions coexist independently.

        Validates:
        - v1.0, v1.1, v2.0 all in database simultaneously
        - Each has independent status
        - Each has independent metrics
        - Configs are completely separate
        - REQ-VER-002: Multiple versions

        Reference: PHASE_1.5_TEST_PLAN_V1.0.md - Integration Test 2
        """
        # Setup
        mock_get_connection.return_value = mock_connection

        manager = StrategyManager()

        # Create v1.0
        mock_cursor.fetchone.return_value = (
            1,
            "value_betting_v1",
            "1.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0500"},
            "Version 1.0",
            "active",
            Decimal("0.1000"),
            Decimal("0.0800"),
            10,
            5,
            "2025-11-16 12:00:00",
            "test_user",
            "Original version",
        )

        v1_0 = manager.get_strategy(strategy_id=1)

        # Create v1.1
        mock_cursor.fetchone.return_value = (
            2,
            "value_betting_v1",
            "1.1",
            "value_betting",
            "nfl",
            {"min_edge": "0.0600"},  # Different config
            "Version 1.1",
            "testing",  # Different status
            Decimal("0.1500"),  # Different metrics
            None,
            15,
            0,
            "2025-11-16 13:00:00",
            "test_user",
            "Bug fix version",
        )

        v1_1 = manager.get_strategy(strategy_id=2)

        # Create v2.0
        mock_cursor.fetchone.return_value = (
            3,
            "value_betting_v1",
            "2.0",
            "value_betting",
            "nfl",
            {"min_edge": "0.0700", "new_param": "10.00"},  # Major change
            "Version 2.0",
            "draft",  # Different status
            None,  # No metrics yet
            None,
            0,
            0,
            "2025-11-16 14:00:00",
            "test_user",
            "Major rewrite",
        )

        v2_0 = manager.get_strategy(strategy_id=3)

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
