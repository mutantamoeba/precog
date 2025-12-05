"""E2E Tests for Strategy Manager - Versioned Trading Strategy Management.

This module provides comprehensive end-to-end tests for the StrategyManager,
validating the complete lifecycle of versioned trading strategies with immutable
configurations.

Educational Note:
    E2E tests validate the full workflow from creation -> retrieval -> status updates
    -> metrics tracking. Unlike unit tests that mock dependencies, these tests
    validate:
    - Database operations (mocked connections)
    - JSONB config serialization/deserialization
    - Decimal precision preservation across database round-trips
    - Version immutability enforcement
    - Status transition validation
    - A/B testing support (multiple active versions)

    These tests mirror real-world usage patterns:
    - Creating strategy v1.0, testing it, activating it
    - Creating v1.1 with different config for A/B testing
    - Comparing performance metrics between versions
    - Managing strategy lifecycle (draft -> testing -> active -> deprecated)

References:
    - Issue #128: Complete Phase 1.5 foundation validation
    - Phase 4: Strategy and Model Managers (advance implementation)
    - REQ-VER-001: Immutable Version Configs
    - REQ-VER-002: Semantic Versioning
    - REQ-VER-003: Trade Attribution (100% of trades link to exact versions)
    - REQ-VER-004: Version Lifecycle Management
    - REQ-VER-005: A/B Testing Support
    - ADR-018: Immutable Strategy Versions
    - ADR-019: Semantic Versioning for Strategies
    - ADR-020: Trade Attribution Pattern
    - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    - docs/guides/VERSIONING_GUIDE_V1.0.md
    - docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.0.md

Coverage Target: 18+ tests across 5 test classes
"""

import json
import re
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.strategy_manager import (
    InvalidStatusTransitionError,
    StrategyManager,
)

# Mark all tests as E2E and slow
pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestStrategyCreationWorkflow:
    """E2E tests for strategy creation and versioning workflows.

    Educational Note:
        These tests validate the complete strategy creation workflow:
        - Creating initial version (v1.0)
        - Creating subsequent versions (v1.1, v2.0)
        - Config immutability enforcement
        - Decimal precision preservation
        - JSONB serialization/deserialization
        - Version uniqueness constraints

        Real-world scenario:
        1. Create halftime_entry v1.0 with min_edge=0.05
        2. Backtest shows 0.05 too risky -> create v1.1 with min_edge=0.10
        3. Both versions preserved for trade attribution
    """

    def test_create_strategy_with_full_config(self):
        """Verify strategy creation with complete config preserves all Decimal values.

        Educational Note:
            This test validates the CRITICAL Pattern 1 requirement:
            ALL prices/probabilities MUST use Decimal, NEVER float.

            Config contains multiple Decimal values:
            - min_edge: Minimum edge threshold
            - max_spread: Maximum bid-ask spread
            - position_size: Position size in dollars

            Database round-trip must preserve exact precision:
            Decimal("0.05") -> JSONB storage -> Decimal("0.05") (not 0.04999999)

        References:
            - REQ-SYS-003: Decimal Precision Enforcement
            - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
        """
        manager = StrategyManager()

        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock cursor.description for _row_to_dict
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock database response with JSONB config (string values)
        mock_cursor.fetchone.return_value = (
            1,  # strategy_id
            "halftime_entry",  # strategy_name
            "v1.0",  # strategy_version
            "value",  # strategy_type
            "nfl",  # domain
            {
                "min_edge": "0.05",
                "max_spread": "0.08",
                "position_size": "100.00",
            },  # config (JSONB, strings)
            "Enter at halftime when leading by 7+ points",  # description
            "draft",  # status
            None,  # paper_roi
            None,  # live_roi
            0,  # paper_trades_count
            0,  # live_trades_count
            "2025-11-26T10:00:00",  # created_at
            "test_user",  # created_by
            "Initial version",  # notes
        )

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            # Create strategy with Decimal config
            config = {
                "min_edge": Decimal("0.05"),
                "max_spread": Decimal("0.08"),
                "position_size": Decimal("100.00"),
            }

            strategy = manager.create_strategy(
                strategy_name="halftime_entry",
                strategy_version="v1.0",
                strategy_type="value",
                domain="nfl",
                config=config,
                description="Enter at halftime when leading by 7+ points",
                status="draft",
                created_by="test_user",
                notes="Initial version",
            )

        # Verify strategy created
        assert strategy["strategy_id"] == 1
        assert strategy["strategy_name"] == "halftime_entry"
        assert strategy["strategy_version"] == "v1.0"
        assert strategy["strategy_type"] == "value"
        assert strategy["domain"] == "nfl"

        # CRITICAL: Verify Decimal precision preserved
        assert isinstance(strategy["config"]["min_edge"], Decimal)
        assert strategy["config"]["min_edge"] == Decimal("0.05")
        assert isinstance(strategy["config"]["max_spread"], Decimal)
        assert strategy["config"]["max_spread"] == Decimal("0.08")
        assert isinstance(strategy["config"]["position_size"], Decimal)
        assert strategy["config"]["position_size"] == Decimal("100.00")

        # Verify other fields
        assert strategy["description"] == "Enter at halftime when leading by 7+ points"
        assert strategy["status"] == "draft"
        assert strategy["created_by"] == "test_user"
        assert strategy["notes"] == "Initial version"

        # Verify database INSERT called with JSONB string
        insert_call = mock_cursor.execute.call_args[0]
        assert "INSERT INTO strategies" in insert_call[0]

        # Verify config converted to JSONB string
        config_jsonb = insert_call[1][4]  # 5th parameter (config)
        config_parsed = json.loads(config_jsonb)
        assert config_parsed["min_edge"] == "0.05"  # Stored as string
        assert config_parsed["max_spread"] == "0.08"
        assert config_parsed["position_size"] == "100.00"

    def test_strategy_version_increments_correctly(self):
        """Verify multiple versions of same strategy can coexist.

        Educational Note:
            Versioning enables A/B testing and trade attribution.
            Same strategy name, different versions, different configs.

            Example workflow:
            - Create halftime_entry v1.0 (min_edge=0.05)
            - Test shows too aggressive -> create v1.1 (min_edge=0.10)
            - Both versions exist simultaneously
            - Trades link to exact version used

        References:
            - REQ-VER-002: Semantic Versioning
            - REQ-VER-005: A/B Testing Support
        """
        manager = StrategyManager()

        # Mock database for v1.0 creation
        mock_conn_v1 = MagicMock()
        mock_cursor_v1 = MagicMock()
        mock_conn_v1.cursor.return_value = mock_cursor_v1

        mock_cursor_v1.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        mock_cursor_v1.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            {"min_edge": "0.05"},
            "Initial version",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch(
                "precog.trading.strategy_manager.get_connection",
                return_value=mock_conn_v1,
            ),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            v1_0 = manager.create_strategy(
                strategy_name="halftime_entry",
                strategy_version="v1.0",
                strategy_type="value",
                domain="nfl",
                config={"min_edge": Decimal("0.05")},
                description="Initial version",
            )

        assert v1_0["strategy_version"] == "v1.0"
        assert v1_0["config"]["min_edge"] == Decimal("0.05")

        # Mock database for v1.1 creation
        mock_conn_v1_1 = MagicMock()
        mock_cursor_v1_1 = MagicMock()
        mock_conn_v1_1.cursor.return_value = mock_cursor_v1_1

        mock_cursor_v1_1.description = mock_cursor_v1.description
        mock_cursor_v1_1.fetchone.return_value = (
            2,
            "halftime_entry",
            "v1.1",
            "value",
            "nfl",
            {"min_edge": "0.10"},
            "Increased min_edge based on backtest",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-26T11:00:00",
            "test_user",
            None,
        )

        with (
            patch(
                "precog.trading.strategy_manager.get_connection",
                return_value=mock_conn_v1_1,
            ),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            v1_1 = manager.create_strategy(
                strategy_name="halftime_entry",
                strategy_version="v1.1",
                strategy_type="value",
                domain="nfl",
                config={"min_edge": Decimal("0.10")},
                description="Increased min_edge based on backtest",
            )

        # Verify v1.1 created successfully
        assert v1_1["strategy_id"] == 2
        assert v1_1["strategy_version"] == "v1.1"
        assert v1_1["config"]["min_edge"] == Decimal("0.10")

        # Verify versions are different
        assert v1_0["strategy_id"] != v1_1["strategy_id"]
        assert v1_0["strategy_version"] != v1_1["strategy_version"]
        assert v1_0["config"]["min_edge"] != v1_1["config"]["min_edge"]

    def test_config_immutability_enforced(self):
        """Verify config cannot be modified after creation.

        Educational Note:
            Config immutability is CRITICAL for trade attribution.
            If we allowed modifying configs, we wouldn't know which config
            generated which trades.

            Example problem if configs were mutable:
            - Create v1.0 with min_edge=0.05
            - Execute 100 trades
            - Change min_edge to 0.10
            - Which trades used 0.05? Which used 0.10? UNKNOWN!

            Solution: Configs are IMMUTABLE. Create new version instead.

        References:
            - REQ-VER-001: Immutable Version Configs
            - ADR-018: Immutable Strategy Versions
        """
        # This test documents the ABSENCE of update_config() method
        manager = StrategyManager()

        # Verify update_config() method does NOT exist
        assert not hasattr(manager, "update_config"), (
            "StrategyManager MUST NOT have update_config() method - "
            "configs are IMMUTABLE. Create new version instead."
        )

        # Document correct workflow: Create new version
        # (This is tested in test_strategy_version_increments_correctly)
        # Instead of: manager.update_config(id, new_config)  # ❌ NOT ALLOWED
        # Do this:    manager.create_strategy(..., version="v1.1")  # ✅ CORRECT

    def test_create_multiple_versions_same_name(self):
        """Verify multiple versions of same strategy support A/B testing.

        Educational Note:
            A/B testing requires running multiple strategy versions simultaneously.
            Each version has:
            - Same strategy_name (e.g., "halftime_entry")
            - Different strategy_version (v1.0, v1.1, v2.0)
            - Different configs
            - Independent metrics (paper_roi, live_roi)

            This enables comparing performance:
            - v1.0 ROI: 12%
            - v1.1 ROI: 15%
            - Winner: v1.1 -> promote to production

        References:
            - REQ-VER-005: A/B Testing Support
        """
        manager = StrategyManager()

        versions = []
        for i, (version, min_edge) in enumerate(
            [("v1.0", "0.05"), ("v1.1", "0.08"), ("v2.0", "0.10")], start=1
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            mock_cursor.description = [
                ("strategy_id",),
                ("strategy_name",),
                ("strategy_version",),
                ("strategy_type",),
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

            mock_cursor.fetchone.return_value = (
                i,
                "halftime_entry",
                version,
                "value",
                "nfl",
                {"min_edge": min_edge},
                f"Version {version}",
                "draft",
                None,
                None,
                0,
                0,
                f"2025-11-26T{10 + i}:00:00",
                "test_user",
                None,
            )

            with (
                patch(
                    "precog.trading.strategy_manager.get_connection",
                    return_value=mock_conn,
                ),
                patch("precog.trading.strategy_manager.release_connection"),
            ):
                strategy = manager.create_strategy(
                    strategy_name="halftime_entry",
                    strategy_version=version,
                    strategy_type="value",
                    domain="nfl",
                    config={"min_edge": Decimal(min_edge)},
                    description=f"Version {version}",
                )
                versions.append(strategy)

        # Verify all versions created
        assert len(versions) == 3

        # Verify all have same name but different versions
        assert all(s["strategy_name"] == "halftime_entry" for s in versions)
        assert versions[0]["strategy_version"] == "v1.0"
        assert versions[1]["strategy_version"] == "v1.1"
        assert versions[2]["strategy_version"] == "v2.0"

        # Verify different configs
        assert versions[0]["config"]["min_edge"] == Decimal("0.05")
        assert versions[1]["config"]["min_edge"] == Decimal("0.08")
        assert versions[2]["config"]["min_edge"] == Decimal("0.10")

        # Verify different IDs
        assert versions[0]["strategy_id"] == 1
        assert versions[1]["strategy_id"] == 2
        assert versions[2]["strategy_id"] == 3


class TestStrategyRetrieval:
    """E2E tests for strategy retrieval and querying.

    Educational Note:
        Retrieval tests validate the complete query workflow:
        - Get single strategy by ID
        - Get all versions of a strategy by name
        - Filter by status (active, testing, draft)
        - Pagination and filtering

        Real-world scenario:
        - Production needs all active strategies -> get_active_strategies()
        - Analyst wants v1.0 vs v1.1 comparison -> get_strategies_by_name()
        - CLI shows strategy details -> get_strategy(id)
    """

    def test_get_strategy_by_id(self):
        """Verify retrieval of single strategy preserves all fields.

        Educational Note:
            Single strategy retrieval is the most common operation.
            Used for:
            - Trade attribution (get strategy config for trade)
            - Status checks (is strategy still active?)
            - Metrics display (show ROI in dashboard)

        References:
            - REQ-VER-003: Trade Attribution
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        mock_cursor.fetchone.return_value = (
            42,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            {"min_edge": "0.05", "max_spread": "0.08"},
            "Test strategy",
            "active",
            "0.15",  # paper_roi as string (Decimal in DB)
            "0.12",  # live_roi as string
            100,
            50,
            "2025-11-26T10:00:00",
            "test_user",
            "Test notes",
        )

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategy = manager.get_strategy(42)

        # Verify all fields
        assert strategy is not None
        assert strategy["strategy_id"] == 42
        assert strategy["strategy_name"] == "halftime_entry"
        assert strategy["strategy_version"] == "v1.0"
        assert strategy["strategy_type"] == "value"
        assert strategy["domain"] == "nfl"
        assert strategy["status"] == "active"

        # Verify config Decimal conversion
        assert isinstance(strategy["config"]["min_edge"], Decimal)
        assert strategy["config"]["min_edge"] == Decimal("0.05")
        assert isinstance(strategy["config"]["max_spread"], Decimal)
        assert strategy["config"]["max_spread"] == Decimal("0.08")

        # Verify metrics (returned as strings from DB, not converted to Decimal here)
        assert strategy["paper_roi"] == "0.15"
        assert strategy["live_roi"] == "0.12"
        assert strategy["paper_trades_count"] == 100
        assert strategy["live_trades_count"] == 50

        # Verify SELECT query
        select_call = mock_cursor.execute.call_args[0]
        assert "SELECT" in select_call[0]
        assert "FROM strategies" in select_call[0]
        assert "WHERE strategy_id = %s" in select_call[0]
        assert select_call[1] == (42,)

    def test_get_strategies_by_name_returns_all_versions(self):
        """Verify retrieval of all versions ordered by version DESC.

        Educational Note:
            Getting all versions enables:
            - Version history analysis (what changed between v1.0 and v2.0?)
            - A/B testing comparison (which version performs better?)
            - Audit trail (when was v1.1 created?)

            Results ordered DESC (newest first) for convenience:
            - v2.0 (latest)
            - v1.1
            - v1.0 (oldest)

        References:
            - REQ-VER-005: A/B Testing Support
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock 3 versions (returned in DESC order: v2.0, v1.1, v1.0)
        mock_cursor.fetchall.return_value = [
            (
                3,
                "halftime_entry",
                "v2.0",
                "value",
                "nfl",
                {"min_edge": "0.10"},
                "Major update",
                "testing",
                None,
                None,
                0,
                0,
                "2025-11-26T12:00:00",
                "test_user",
                None,
            ),
            (
                2,
                "halftime_entry",
                "v1.1",
                "value",
                "nfl",
                {"min_edge": "0.08"},
                "Minor update",
                "active",
                "0.15",
                "0.12",
                100,
                50,
                "2025-11-26T11:00:00",
                "test_user",
                None,
            ),
            (
                1,
                "halftime_entry",
                "v1.0",
                "value",
                "nfl",
                {"min_edge": "0.05"},
                "Initial version",
                "inactive",
                "0.10",
                "0.08",
                200,
                100,
                "2025-11-26T10:00:00",
                "test_user",
                None,
            ),
        ]

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategies = manager.get_strategies_by_name("halftime_entry")

        # Verify all 3 versions returned
        assert len(strategies) == 3

        # Verify ordered DESC (newest first)
        assert strategies[0]["strategy_version"] == "v2.0"
        assert strategies[1]["strategy_version"] == "v1.1"
        assert strategies[2]["strategy_version"] == "v1.0"

        # Verify all same name
        assert all(s["strategy_name"] == "halftime_entry" for s in strategies)

        # Verify different configs
        assert strategies[0]["config"]["min_edge"] == Decimal("0.10")
        assert strategies[1]["config"]["min_edge"] == Decimal("0.08")
        assert strategies[2]["config"]["min_edge"] == Decimal("0.05")

        # Verify different statuses
        assert strategies[0]["status"] == "testing"
        assert strategies[1]["status"] == "active"
        assert strategies[2]["status"] == "inactive"

        # Verify SELECT query
        select_call = mock_cursor.execute.call_args[0]
        assert "WHERE strategy_name = %s" in select_call[0]
        assert "ORDER BY strategy_version DESC" in select_call[0]

    def test_get_active_strategies_filters_correctly(self):
        """Verify filtering by status='active' returns only active strategies.

        Educational Note:
            Production trading only uses active strategies.
            Other statuses:
            - draft: Under development (not used)
            - testing: Paper trading only
            - inactive: Temporarily disabled
            - deprecated: Permanently retired

        References:
            - REQ-VER-004: Version Lifecycle Management
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock 2 active strategies (different strategies, both active)
        mock_cursor.fetchall.return_value = [
            (
                1,
                "halftime_entry",
                "v1.1",
                "value",
                "nfl",
                {"min_edge": "0.08"},
                "Active strategy 1",
                "active",
                "0.15",
                "0.12",
                100,
                50,
                "2025-11-26T10:00:00",
                "test_user",
                None,
            ),
            (
                2,
                "momentum_fade",
                "v2.0",
                "momentum",
                "nfl",
                {"window": "300"},
                "Active strategy 2",
                "active",
                "0.18",
                "0.14",
                150,
                75,
                "2025-11-26T11:00:00",
                "test_user",
                None,
            ),
        ]

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategies = manager.get_active_strategies()

        # Verify only active strategies returned
        assert len(strategies) == 2
        assert all(s["status"] == "active" for s in strategies)

        # Verify different strategies
        assert strategies[0]["strategy_name"] == "halftime_entry"
        assert strategies[1]["strategy_name"] == "momentum_fade"

        # Verify SELECT query uses partial index
        select_call = mock_cursor.execute.call_args[0]
        assert "WHERE status = 'active'" in select_call[0]
        assert "ORDER BY strategy_name, strategy_version" in select_call[0]

    def test_list_strategies_pagination(self):
        """Verify list_strategies() supports flexible filtering.

        Educational Note:
            list_strategies() provides flexible querying:
            - Filter by status (active, testing, draft, etc.)
            - Filter by version (v1.0, v1.1, etc.)
            - Filter by type (value, arbitrage, momentum, etc.)
            - Multiple filters combine with AND logic

            This enables:
            - "Show all active value strategies"
            - "Show all v1.0 strategies"
            - "Show all testing strategies"

        References:
            - GitHub Issue #132: Add list_strategies() method
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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
            ("activated_at",),
            ("deactivated_at",),
            ("updated_at",),
        ]

        # Mock filtered results: status='active' AND strategy_type='value'
        mock_cursor.fetchall.return_value = [
            (
                1,
                "halftime_entry",
                "v1.1",
                "value",
                "nfl",
                {"min_edge": "0.08"},
                "Active value strategy",
                "active",
                "0.15",
                "0.12",
                100,
                50,
                "2025-11-26T10:00:00",
                "test_user",
                None,
                "2025-11-26T10:00:00",
                None,
                "2025-11-26T10:00:00",
            ),
        ]

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategies = manager.list_strategies(status="active", strategy_type="value")

        # Verify filtering works
        assert len(strategies) == 1
        assert strategies[0]["status"] == "active"
        assert strategies[0]["strategy_type"] == "value"

        # Verify SELECT query uses WHERE clause with AND
        select_call = mock_cursor.execute.call_args[0]
        assert "WHERE status = %s AND strategy_type = %s" in select_call[0]
        assert select_call[1] == ["active", "value"]


class TestStrategyStatusManagement:
    """E2E tests for strategy status transitions and lifecycle.

    Educational Note:
        Status management validates the strategy lifecycle state machine:
        - draft -> testing -> active (forward progression)
        - active -> inactive -> deprecated (retirement)
        - testing -> draft (revert to development)

        Invalid transitions raise InvalidStatusTransitionError:
        - deprecated -> active (can't reactivate deprecated)
        - active -> testing (can't go backwards)

        Real-world scenario:
        1. Create v1.0 (status=draft)
        2. Complete development -> update_status('testing')
        3. Paper trading looks good -> update_status('active')
        4. Strategy underperforms -> update_status('inactive')
        5. Strategy obsolete -> update_status('deprecated')

    References:
        - REQ-VER-004: Version Lifecycle Management
    """

    def test_update_status_active_to_inactive(self):
        """Verify valid status transition: active -> inactive.

        Educational Note:
            Transitioning active -> inactive is common when:
            - Strategy underperforms (ROI below threshold)
            - Market conditions change (strategy no longer effective)
            - Risk management (reduce exposure)

            Strategy can be reactivated later: inactive -> active
        """
        manager = StrategyManager()

        # Mock get_strategy() call (to check current status)
        mock_conn_get = MagicMock()
        mock_cursor_get = MagicMock()
        mock_conn_get.cursor.return_value = mock_cursor_get

        mock_cursor_get.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        mock_cursor_get.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            {"min_edge": "0.05"},
            "Test strategy",
            "active",  # Current status
            "0.15",
            "0.12",
            100,
            50,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        # Mock update_status() call
        mock_conn_update = MagicMock()
        mock_cursor_update = MagicMock()
        mock_conn_update.cursor.return_value = mock_cursor_update

        mock_cursor_update.description = mock_cursor_get.description
        mock_cursor_update.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            {"min_edge": "0.05"},
            "Test strategy",
            "inactive",  # New status
            "0.15",
            "0.12",
            100,
            50,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch(
                "precog.trading.strategy_manager.get_connection",
                side_effect=[mock_conn_get, mock_conn_update],
            ),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategy = manager.update_status(1, "inactive")

        # Verify status updated
        assert strategy["status"] == "inactive"
        assert strategy["strategy_id"] == 1

        # Verify UPDATE query
        update_call = mock_cursor_update.execute.call_args[0]
        assert "UPDATE strategies" in update_call[0]
        assert "SET status = %s" in update_call[0]
        assert "WHERE strategy_id = %s" in update_call[0]
        assert update_call[1] == ("inactive", 1)

    def test_update_status_preserves_config(self):
        """Verify status update does NOT modify config (immutability).

        Educational Note:
            Status is MUTABLE, config is IMMUTABLE.
            Updating status should NEVER touch config field.

            This test ensures UPDATE query only modifies status column,
            leaving config unchanged.

        References:
            - REQ-VER-001: Immutable Version Configs
        """
        manager = StrategyManager()

        # Mock get_strategy() call
        mock_conn_get = MagicMock()
        mock_cursor_get = MagicMock()
        mock_conn_get.cursor.return_value = mock_cursor_get

        mock_cursor_get.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        original_config = {"min_edge": "0.05", "max_spread": "0.08"}

        mock_cursor_get.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            original_config,
            "Test strategy",
            "draft",
            None,
            None,
            0,
            0,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        # Mock update_status() call
        mock_conn_update = MagicMock()
        mock_cursor_update = MagicMock()
        mock_conn_update.cursor.return_value = mock_cursor_update

        mock_cursor_update.description = mock_cursor_get.description
        mock_cursor_update.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            original_config,  # Config unchanged!
            "Test strategy",
            "testing",  # Status changed
            None,
            None,
            0,
            0,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch(
                "precog.trading.strategy_manager.get_connection",
                side_effect=[mock_conn_get, mock_conn_update],
            ),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategy = manager.update_status(1, "testing")

        # Verify status updated
        assert strategy["status"] == "testing"

        # CRITICAL: Verify config UNCHANGED
        assert strategy["config"]["min_edge"] == Decimal("0.05")
        assert strategy["config"]["max_spread"] == Decimal("0.08")

        # Verify UPDATE query only modifies status
        update_call = mock_cursor_update.execute.call_args[0]
        assert "SET status = %s" in update_call[0]
        # Extract SET clause and verify config is NOT being modified
        set_match = re.search(r"SET\s+(.*?)\s+WHERE", update_call[0], re.DOTALL | re.IGNORECASE)
        assert set_match, "UPDATE should have SET ... WHERE pattern"
        set_clause = set_match.group(1)
        assert "config" not in set_clause.lower(), "Config should NOT be modified in SET clause"

    def test_status_transitions_logged(self):
        """Verify invalid status transition raises error.

        Educational Note:
            Invalid transitions prevent logical errors:
            - deprecated -> active: Deprecated strategies are retired permanently
            - active -> testing: Can't demote active to testing (create new version)

            Valid transitions follow state machine:
            - draft -> testing -> active (forward)
            - active -> inactive -> deprecated (retirement)
            - testing -> draft (revert)

        References:
            - REQ-VER-004: Version Lifecycle Management
        """
        manager = StrategyManager()

        # Mock get_strategy() call (deprecated status)
        mock_conn_get = MagicMock()
        mock_cursor_get = MagicMock()
        mock_conn_get.cursor.return_value = mock_cursor_get

        mock_cursor_get.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        mock_cursor_get.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            {"min_edge": "0.05"},
            "Test strategy",
            "deprecated",  # Terminal status
            "0.10",
            "0.08",
            200,
            100,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch(
                "precog.trading.strategy_manager.get_connection",
                return_value=mock_conn_get,
            ),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            # Attempt invalid transition: deprecated -> active
            with pytest.raises(InvalidStatusTransitionError) as exc_info:
                manager.update_status(1, "active")

        # Verify error message
        assert "Invalid transition: deprecated -> active" in str(exc_info.value)
        assert "Valid transitions from deprecated: []" in str(exc_info.value)


class TestStrategyMetricsUpdate:
    """E2E tests for mutable metrics updates.

    Educational Note:
        Metrics tests validate the separation of MUTABLE and IMMUTABLE fields:
        - MUTABLE: status, paper_roi, live_roi, paper_trades_count, live_trades_count
        - IMMUTABLE: config, strategy_name, strategy_version, strategy_type

        Metrics accumulate as trades execute:
        - After 10 trades: paper_roi=0.05, paper_trades_count=10
        - After 20 trades: paper_roi=0.08, paper_trades_count=20
        - After 30 trades: paper_roi=0.12, paper_trades_count=30

        Config NEVER changes during this process!

    References:
        - REQ-VER-001: Immutable Version Configs
        - REQ-VER-005: A/B Testing Support (compare metrics between versions)
    """

    def test_update_metrics_total_trades(self):
        """Verify updating trade count preserves all other fields.

        Educational Note:
            Trade count increments as strategy executes:
            - Initial: paper_trades_count=0
            - After batch 1: paper_trades_count=10
            - After batch 2: paper_trades_count=20

            This test verifies ONLY trade count changes, nothing else.
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock updated strategy with new trade count
        mock_cursor.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            {"min_edge": "0.05"},  # Config unchanged
            "Test strategy",
            "active",  # Status unchanged
            "0.15",  # ROI unchanged
            None,
            42,  # paper_trades_count CHANGED
            0,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategy = manager.update_metrics(1, paper_trades_count=42)

        # Verify trade count updated
        assert strategy["paper_trades_count"] == 42

        # Verify other fields unchanged
        assert strategy["config"]["min_edge"] == Decimal("0.05")
        assert strategy["status"] == "active"
        assert strategy["paper_roi"] == "0.15"

        # Verify UPDATE query
        update_call = mock_cursor.execute.call_args[0]
        assert "UPDATE strategies" in update_call[0]
        assert "SET paper_trades_count = %s" in update_call[0]
        assert "WHERE strategy_id = %s" in update_call[0]

    def test_update_metrics_pnl_tracking(self):
        """Verify updating ROI metrics preserves config immutability.

        Educational Note:
            ROI (Return on Investment) tracks strategy performance:
            - paper_roi: ROI from paper trading (testing)
            - live_roi: ROI from live trading (production)

            ROI updates frequently (after each trade batch).
            Config NEVER updates (immutable).

        References:
            - REQ-VER-005: A/B Testing Support
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        original_config = {"min_edge": "0.05", "max_spread": "0.08"}

        # Mock updated strategy with new ROI
        mock_cursor.fetchone.return_value = (
            1,
            "halftime_entry",
            "v1.0",
            "value",
            "nfl",
            original_config,  # Config unchanged!
            "Test strategy",
            "active",
            "0.18",  # paper_roi CHANGED
            "0.15",  # live_roi CHANGED
            100,
            50,
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategy = manager.update_metrics(
                1, paper_roi=Decimal("0.18"), live_roi=Decimal("0.15")
            )

        # Verify ROI updated
        assert strategy["paper_roi"] == "0.18"
        assert strategy["live_roi"] == "0.15"

        # CRITICAL: Verify config unchanged
        assert strategy["config"]["min_edge"] == Decimal("0.05")
        assert strategy["config"]["max_spread"] == Decimal("0.08")

        # Verify UPDATE query updates ONLY metrics
        update_call = mock_cursor.execute.call_args[0]
        assert "SET paper_roi = %s, live_roi = %s" in update_call[0]
        # Extract SET clause and verify config is NOT being modified
        set_match = re.search(r"SET\s+(.*?)\s+WHERE", update_call[0], re.DOTALL | re.IGNORECASE)
        assert set_match, "UPDATE should have SET ... WHERE pattern"
        set_clause = set_match.group(1)
        assert "config" not in set_clause.lower(), "Config should NOT be modified in SET clause"

    def test_metrics_update_preserves_immutable_fields(self):
        """Verify metrics update NEVER touches config, name, version, type.

        Educational Note:
            This test documents the separation of concerns:
            - MUTABLE: Metrics accumulate (roi, trade counts)
            - IMMUTABLE: Identity never changes (name, version, type, config)

            Why? Trade attribution requires knowing EXACTLY which config
            generated which ROI. If config could change, attribution breaks.

        References:
            - REQ-VER-001: Immutable Version Configs
            - REQ-VER-003: Trade Attribution
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        original_config = {
            "min_edge": "0.05",
            "max_spread": "0.08",
            "position_size": "100.00",
        }

        # Mock updated strategy
        mock_cursor.fetchone.return_value = (
            1,
            "halftime_entry",  # Name unchanged
            "v1.0",  # Version unchanged
            "value",  # Type unchanged
            "nfl",  # Domain unchanged
            original_config,  # Config unchanged!
            "Test strategy",
            "active",
            "0.20",  # paper_roi CHANGED
            "0.18",  # live_roi CHANGED
            150,  # paper_trades_count CHANGED
            75,  # live_trades_count CHANGED
            "2025-11-26T10:00:00",
            "test_user",
            None,
        )

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            strategy = manager.update_metrics(
                1,
                paper_roi=Decimal("0.20"),
                live_roi=Decimal("0.18"),
                paper_trades_count=150,
                live_trades_count=75,
            )

        # Verify metrics updated
        assert strategy["paper_roi"] == "0.20"
        assert strategy["live_roi"] == "0.18"
        assert strategy["paper_trades_count"] == 150
        assert strategy["live_trades_count"] == 75

        # CRITICAL: Verify immutable fields UNCHANGED
        assert strategy["strategy_name"] == "halftime_entry"
        assert strategy["strategy_version"] == "v1.0"
        assert strategy["strategy_type"] == "value"
        assert strategy["domain"] == "nfl"
        assert strategy["config"]["min_edge"] == Decimal("0.05")
        assert strategy["config"]["max_spread"] == Decimal("0.08")
        assert strategy["config"]["position_size"] == Decimal("100.00")

        # Verify UPDATE query updates ONLY mutable fields
        update_call = mock_cursor.execute.call_args[0]
        assert (
            "SET paper_roi = %s, live_roi = %s, paper_trades_count = %s, live_trades_count = %s"
            in update_call[0]
        )

        # Extract SET clause and verify immutable fields NOT in SET clause
        set_match = re.search(r"SET\s+(.*?)\s+WHERE", update_call[0], re.DOTALL | re.IGNORECASE)
        assert set_match, "UPDATE should have SET ... WHERE pattern"
        set_clause = set_match.group(1)
        assert "strategy_name" not in set_clause.lower(), (
            "strategy_name should NOT be in SET clause"
        )
        assert "strategy_version" not in set_clause.lower(), (
            "strategy_version should NOT be in SET clause"
        )
        assert "strategy_type" not in set_clause.lower(), (
            "strategy_type should NOT be in SET clause"
        )
        assert "config" not in set_clause.lower(), "Config should NOT be modified in SET clause"


class TestStrategyVersionComparison:
    """E2E tests for A/B testing and version comparison.

    Educational Note:
        Version comparison enables A/B testing:
        - Run v1.0 and v1.1 simultaneously
        - Compare metrics after N trades
        - Identify best performing version
        - Audit trail of version evolution

        Real-world scenario:
        1. Create halftime_entry v1.0 (min_edge=0.05)
        2. Create halftime_entry v1.1 (min_edge=0.08)
        3. Both active, execute trades
        4. After 100 trades each:
           - v1.0: paper_roi=0.12, 80 winning trades
           - v1.1: paper_roi=0.15, 75 winning trades
        5. Winner: v1.1 (higher ROI despite fewer trades)
        6. Promote v1.1 to production, deprecate v1.0

    References:
        - REQ-VER-005: A/B Testing Support
        - ADR-019: Semantic Versioning for Strategies
    """

    def test_compare_strategy_versions_by_metrics(self):
        """Verify multiple versions can coexist with independent metrics.

        Educational Note:
            A/B testing requires:
            - Same strategy name (e.g., 'halftime_entry')
            - Different versions (v1.0, v1.1, v2.0)
            - Independent metrics (each version tracks own ROI/trades)

            This enables comparing performance:
            - Which version has higher ROI?
            - Which version trades more frequently?
            - Which version has better risk-adjusted returns?

        References:
            - REQ-VER-005: A/B Testing Support
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock 3 versions with different metrics
        mock_cursor.fetchall.return_value = [
            (
                3,
                "halftime_entry",
                "v2.0",
                "value",
                "nfl",
                {"min_edge": "0.10"},
                "Latest version",
                "active",
                "0.18",  # Best ROI
                "0.16",
                50,  # Fewest trades (most selective)
                25,
                "2025-11-26T12:00:00",
                "test_user",
                None,
            ),
            (
                2,
                "halftime_entry",
                "v1.1",
                "value",
                "nfl",
                {"min_edge": "0.08"},
                "Minor update",
                "active",
                "0.15",  # Medium ROI
                "0.12",
                100,  # Medium trades
                50,
                "2025-11-26T11:00:00",
                "test_user",
                None,
            ),
            (
                1,
                "halftime_entry",
                "v1.0",
                "value",
                "nfl",
                {"min_edge": "0.05"},
                "Initial version",
                "active",
                "0.10",  # Lowest ROI
                "0.08",
                200,  # Most trades (least selective)
                100,
                "2025-11-26T10:00:00",
                "test_user",
                None,
            ),
        ]

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            versions = manager.get_strategies_by_name("halftime_entry")

        # Verify 3 versions returned
        assert len(versions) == 3

        # Verify independent metrics
        assert versions[0]["paper_roi"] == "0.18"  # v2.0
        assert versions[1]["paper_roi"] == "0.15"  # v1.1
        assert versions[2]["paper_roi"] == "0.10"  # v1.0

        # Verify trade counts differ
        assert versions[0]["paper_trades_count"] == 50  # v2.0 (most selective)
        assert versions[1]["paper_trades_count"] == 100  # v1.1
        assert versions[2]["paper_trades_count"] == 200  # v1.0 (least selective)

        # Verify configs differ
        assert versions[0]["config"]["min_edge"] == Decimal("0.10")  # v2.0
        assert versions[1]["config"]["min_edge"] == Decimal("0.08")  # v1.1
        assert versions[2]["config"]["min_edge"] == Decimal("0.05")  # v1.0

    def test_identify_best_performing_version(self):
        """Verify identifying best version by ROI.

        Educational Note:
            After A/B testing period, identify winner:
            1. Get all versions of strategy
            2. Compare paper_roi across versions
            3. Select version with highest ROI
            4. Promote to production (status='active')
            5. Deprecate underperforming versions

            This test simulates finding the best version.

        References:
            - REQ-VER-005: A/B Testing Support
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock 3 versions (ordered by version DESC)
        mock_cursor.fetchall.return_value = [
            (
                3,
                "halftime_entry",
                "v2.0",
                "value",
                "nfl",
                {"min_edge": "0.10"},
                "Latest version",
                "active",
                "0.22",  # BEST ROI (winner!)
                "0.20",
                75,
                40,
                "2025-11-26T12:00:00",
                "test_user",
                None,
            ),
            (
                2,
                "halftime_entry",
                "v1.1",
                "value",
                "nfl",
                {"min_edge": "0.08"},
                "Minor update",
                "active",
                "0.15",
                "0.12",
                100,
                50,
                "2025-11-26T11:00:00",
                "test_user",
                None,
            ),
            (
                1,
                "halftime_entry",
                "v1.0",
                "value",
                "nfl",
                {"min_edge": "0.05"},
                "Initial version",
                "active",
                "0.10",
                "0.08",
                200,
                100,
                "2025-11-26T10:00:00",
                "test_user",
                None,
            ),
        ]

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            versions = manager.get_strategies_by_name("halftime_entry")

        # Identify best version by paper_roi
        best_version = max(versions, key=lambda v: Decimal(v["paper_roi"] or "0"))

        # Verify best version identified
        assert best_version["strategy_version"] == "v2.0"
        assert best_version["paper_roi"] == "0.22"
        assert best_version["config"]["min_edge"] == Decimal("0.10")

        # Verify all versions present for comparison
        assert len(versions) == 3
        assert all(v["strategy_name"] == "halftime_entry" for v in versions)

    def test_strategy_version_audit_trail(self):
        """Verify version history provides complete audit trail.

        Educational Note:
            Audit trail answers critical questions:
            - When was v1.1 created?
            - Who created v2.0?
            - What config changed between v1.0 and v1.1?
            - How many trades did each version execute?

            Complete history enables:
            - Performance analysis over time
            - Config tuning decisions (what worked, what didn't)
            - Accountability (who made changes)

        References:
            - REQ-VER-002: Semantic Versioning
            - ADR-018: Immutable Strategy Versions
        """
        manager = StrategyManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
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

        # Mock complete version history
        mock_cursor.fetchall.return_value = [
            (
                3,
                "halftime_entry",
                "v2.0",
                "value",
                "nfl",
                {"min_edge": "0.10", "max_spread": "0.06"},
                "Major config overhaul",
                "active",
                "0.22",
                "0.20",
                75,
                40,
                "2025-11-26T12:00:00",
                "alice",
                "Tightened spread based on slippage analysis",
            ),
            (
                2,
                "halftime_entry",
                "v1.1",
                "value",
                "nfl",
                {"min_edge": "0.08", "max_spread": "0.08"},
                "Increased min_edge",
                "inactive",
                "0.15",
                "0.12",
                100,
                50,
                "2025-11-26T11:00:00",
                "bob",
                "Reduced false positives by raising edge threshold",
            ),
            (
                1,
                "halftime_entry",
                "v1.0",
                "value",
                "nfl",
                {"min_edge": "0.05", "max_spread": "0.08"},
                "Initial version",
                "deprecated",
                "0.10",
                "0.08",
                200,
                100,
                "2025-11-26T10:00:00",
                "alice",
                "Initial implementation",
            ),
        ]

        with (
            patch("precog.trading.strategy_manager.get_connection", return_value=mock_conn),
            patch("precog.trading.strategy_manager.release_connection"),
        ):
            history = manager.get_strategies_by_name("halftime_entry")

        # Verify complete audit trail
        assert len(history) == 3

        # Verify version progression
        assert history[0]["strategy_version"] == "v2.0"
        assert history[1]["strategy_version"] == "v1.1"
        assert history[2]["strategy_version"] == "v1.0"

        # Verify creators tracked
        assert history[0]["created_by"] == "alice"
        assert history[1]["created_by"] == "bob"
        assert history[2]["created_by"] == "alice"

        # Verify creation timestamps
        assert history[0]["created_at"] == "2025-11-26T12:00:00"
        assert history[1]["created_at"] == "2025-11-26T11:00:00"
        assert history[2]["created_at"] == "2025-11-26T10:00:00"

        # Verify config evolution
        assert history[0]["config"]["min_edge"] == Decimal("0.10")  # v2.0
        assert history[1]["config"]["min_edge"] == Decimal("0.08")  # v1.1
        assert history[2]["config"]["min_edge"] == Decimal("0.05")  # v1.0

        # Verify status lifecycle
        assert history[0]["status"] == "active"  # v2.0 (current)
        assert history[1]["status"] == "inactive"  # v1.1 (retired)
        assert history[2]["status"] == "deprecated"  # v1.0 (obsolete)

        # Verify notes document rationale
        assert "Tightened spread" in history[0]["notes"]
        assert "Reduced false positives" in history[1]["notes"]
        assert "Initial implementation" in history[2]["notes"]
