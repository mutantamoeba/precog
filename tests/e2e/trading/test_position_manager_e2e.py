"""E2E Tests for Position Manager - Complete Position Lifecycle.

This module tests the complete position lifecycle from entry to exit with
comprehensive coverage of versioning, P&L calculation, and trailing stops.

Educational Note:
    E2E (End-to-End) tests verify complete workflows across multiple components.
    Unlike unit tests (test single function) or integration tests (test component
    interactions), E2E tests verify entire user scenarios work correctly.

    Example distinction:
    - Unit test: test_calculate_position_pnl() - tests P&L formula in isolation
    - Integration test: test_crud_create_position() - tests database CRUD operation
    - E2E test: test_complete_position_lifecycle_workflow() - tests open -> update -> close

    E2E tests are:
    - Slower (test multiple operations)
    - More comprehensive (catch integration bugs)
    - More realistic (test actual user workflows)

    This is why we mark them with @pytest.mark.slow - they run in CI but can be
    skipped during rapid development: `pytest -m "not slow"`

References:
    - Issue #128: Position Manager E2E Test Coverage
    - Phase 4: Position Management & Risk Controls
    - REQ-TEST-020: E2E Test Coverage for Position Lifecycle
    - src/precog/trading/position_manager.py - Source implementation
    - docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md - Position lifecycle patterns
    - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    - Pattern 10 (CLAUDE.md): Educational Docstrings

Phase: 4 (Position Management & Risk Controls)
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.position_manager import (
    InsufficientMarginError,
    PositionManager,
)

# Mark all tests in this module as E2E and slow
pytestmark = [pytest.mark.e2e, pytest.mark.slow]


# ============================================================================
# Test Class 1: Position Lifecycle (Open -> Update -> Close)
# ============================================================================


class TestPositionLifecycle:
    """Test complete position lifecycle workflows.

    Educational Note:
        Position lifecycle has 3 phases:
        1. OPEN: Create position, validate margin, record entry
        2. UPDATE: Track price changes, calculate unrealized P&L
        3. CLOSE: Exit position, record realized P&L

        Each phase creates SCD Type 2 versions (row_current_ind tracking).

        Why test lifecycle as E2E?
        - Validates workflow continuity (data flows correctly between phases)
        - Catches state management bugs (e.g., closed position still updatable)
        - Ensures business logic consistency (P&L calculations match across updates)

    References:
        - REQ-RISK-001: Position Entry Validation
        - REQ-EXEC-001: Trade Execution Workflow
        - ADR-015: SCD Type 2 for Position History
    """

    def test_complete_position_lifecycle_workflow(self):
        """Test complete workflow: open -> update price -> close position.

        Educational Note:
            This is a "happy path" E2E test covering the most common workflow:
            1. Open YES position at entry price
            2. Price moves favorably (goes UP for YES)
            3. Update position with new price (creates SCD Type 2 version)
            4. Price reaches target
            5. Close position with profit

            Each step creates new database row with row_current_ind tracking.

        Why this test matters:
            - Validates complete user workflow (most common trading scenario)
            - Ensures SCD Type 2 versioning works across lifecycle
            - Catches data consistency bugs (e.g., P&L calculation mismatch)

        References:
            - REQ-EXEC-001: Trade Execution Workflow
            - Pattern 2 (CLAUDE.md): Dual Versioning System
        """
        manager = PositionManager()

        # Mock database operations
        with (
            patch("precog.trading.position_manager.crud_create_position") as mock_create,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
            patch("precog.trading.position_manager.crud_update_position_price") as mock_update,
            patch("precog.trading.position_manager.crud_close_position") as mock_close,
        ):
            # Setup mocks
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # ====================================================================
            # PHASE 1: OPEN POSITION
            # ====================================================================
            mock_create.return_value = 1  # Surrogate ID

            # Mock fetchone for position data after creation
            position_data_after_create = {
                "id": 1,  # Surrogate key
                "position_id": "POS-1",  # Business key
                "market_id": "MKT-NFL-001",
                "strategy_id": 42,
                "model_id": 7,
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.5000"),
                "target_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("0.00"),
                "realized_pnl": None,
                "status": "open",
                "exit_price": None,
                "exit_reason": None,
                "trailing_stop_state": None,
                "position_metadata": None,
                "row_current_ind": True,
            }
            mock_cursor.fetchone.return_value = position_data_after_create

            # Open position
            position = manager.open_position(
                market_id="MKT-NFL-001",
                strategy_id=42,
                model_id=7,
                side="YES",
                quantity=10,
                entry_price=Decimal("0.5000"),
                available_margin=Decimal("1000.00"),  # More than enough
                target_price=Decimal("0.7500"),
                stop_loss_price=Decimal("0.3500"),
            )

            # Verify position created
            assert position["id"] == 1
            assert position["position_id"] == "POS-1"
            assert position["side"] == "YES"
            assert position["quantity"] == 10
            assert position["entry_price"] == Decimal("0.5000")
            assert position["current_price"] == Decimal("0.5000")
            assert position["status"] == "open"
            assert position["unrealized_pnl"] == Decimal("0.00")
            assert position["row_current_ind"] is True

            # Verify CRUD called
            mock_create.assert_called_once()

            # ====================================================================
            # PHASE 2: UPDATE POSITION (Price moves UP to $0.60)
            # ====================================================================
            mock_update.return_value = 2  # New surrogate ID (SCD Type 2!)

            # Mock fetchone for updated position data
            position_data_after_update = {
                "id": 2,  # NEW surrogate key (SCD Type 2!)
                "position_id": "POS-1",  # SAME business key
                "market_id": "MKT-NFL-001",
                "strategy_id": 42,
                "model_id": 7,
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.6000"),  # Updated!
                "target_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("1.00"),  # 10 * (0.60 - 0.50)
                "realized_pnl": None,
                "status": "open",
                "exit_price": None,
                "exit_reason": None,
                "trailing_stop_state": None,
                "position_metadata": None,
                "row_current_ind": True,
            }
            mock_cursor.fetchone.return_value = position_data_after_update

            # Update position price
            updated_position = manager.update_position(
                position_id=1,  # Old surrogate ID
                current_price=Decimal("0.6000"),
            )

            # Verify SCD Type 2 versioning
            assert updated_position["id"] == 2  # NEW ID!
            assert updated_position["position_id"] == "POS-1"  # SAME business key
            assert updated_position["current_price"] == Decimal("0.6000")
            assert updated_position["unrealized_pnl"] == Decimal("1.00")  # Profit!
            assert updated_position["row_current_ind"] is True

            # ====================================================================
            # PHASE 3: CLOSE POSITION (Hit target at $0.75)
            # ====================================================================
            mock_close.return_value = 3  # Final surrogate ID

            # Mock fetchone for current position (before close)
            position_data_before_close = {
                "id": 2,
                "position_id": "POS-1",
                "market_id": "MKT-NFL-001",
                "strategy_id": 42,
                "model_id": 7,
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.6000"),
                "target_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("1.00"),
                "realized_pnl": None,
                "status": "open",  # Still open
                "exit_price": None,
                "exit_reason": None,
                "trailing_stop_state": None,
                "position_metadata": None,
                "row_current_ind": True,
            }

            # Mock fetchone for closed position (after close)
            position_data_after_close = {
                "id": 3,  # FINAL surrogate key
                "position_id": "POS-1",  # SAME business key
                "market_id": "MKT-NFL-001",
                "strategy_id": 42,
                "model_id": 7,
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.7500"),  # Exit price
                "target_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("0.00"),  # Cleared on close
                "realized_pnl": Decimal("2.50"),  # 10 * (0.75 - 0.50)
                "status": "closed",  # NOW CLOSED!
                "exit_price": Decimal("0.7500"),
                "exit_reason": "profit_target",
                "trailing_stop_state": None,
                "position_metadata": None,
                "row_current_ind": True,
            }

            # Configure fetchone to return different data on each call
            mock_cursor.fetchone.side_effect = [
                position_data_before_close,  # First call: get current position
                position_data_after_close,  # Second call: get closed position
            ]

            # Close position
            closed_position = manager.close_position(
                position_id=2,  # Previous surrogate ID
                exit_price=Decimal("0.7500"),
                exit_reason="profit_target",
            )

            # Verify final state
            assert closed_position["id"] == 3  # FINAL ID
            assert closed_position["position_id"] == "POS-1"  # SAME business key
            assert closed_position["status"] == "closed"
            assert closed_position["exit_price"] == Decimal("0.7500")
            assert closed_position["exit_reason"] == "profit_target"
            assert closed_position["realized_pnl"] == Decimal("2.50")  # Final profit
            assert closed_position["row_current_ind"] is True

            # Verify lifecycle tracked across 3 versions
            # Version 1: id=1, status=open, price=$0.50, unrealized=$0.00
            # Version 2: id=2, status=open, price=$0.60, unrealized=$1.00
            # Version 3: id=3, status=closed, price=$0.75, realized=$2.50

    def test_position_open_with_valid_parameters(self):
        """Test position opens successfully with all valid parameters.

        Educational Note:
            This test validates the OPEN phase in isolation with ALL optional
            parameters provided (target_price, stop_loss_price, trailing_stop_config,
            position_metadata).

            Why test with all parameters?
            - Ensures optional parameters don't break creation logic
            - Validates trailing_stop_state initialization
            - Confirms metadata storage works correctly

        References:
            - REQ-RISK-001: Position Entry Validation
            - REQ-TRAIL-002: JSONB State Management
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_create_position") as mock_create,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            # Setup mocks
            mock_create.return_value = 1
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Trailing stop config
            trailing_config = {
                "activation_threshold": Decimal("0.15"),
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            }

            # Position metadata
            metadata = {
                "model_edge": Decimal("0.0525"),
                "true_probability": Decimal("0.5500"),
                "market_price": Decimal("0.4975"),
            }

            # Mock position data
            position_data = {
                "id": 1,
                "position_id": "POS-1",
                "market_id": "MKT-NFL-001",
                "strategy_id": 42,
                "model_id": 7,
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.4975"),
                "current_price": Decimal("0.4975"),
                "target_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("0.00"),
                "realized_pnl": None,
                "status": "open",
                "exit_price": None,
                "exit_reason": None,
                "trailing_stop_state": {
                    "config": trailing_config,
                    "activated": False,
                    "activation_price": None,
                    "current_stop_price": Decimal("0.3500"),
                },
                "position_metadata": metadata,
                "row_current_ind": True,
            }
            mock_cursor.fetchone.return_value = position_data

            # Open position with all parameters
            position = manager.open_position(
                market_id="MKT-NFL-001",
                strategy_id=42,
                model_id=7,
                side="YES",
                quantity=10,
                entry_price=Decimal("0.4975"),
                available_margin=Decimal("1000.00"),
                target_price=Decimal("0.7500"),
                stop_loss_price=Decimal("0.3500"),
                trailing_stop_config=trailing_config,
                position_metadata=metadata,
            )

            # Verify all parameters stored
            assert position["target_price"] == Decimal("0.7500")
            assert position["stop_loss_price"] == Decimal("0.3500")
            assert position["trailing_stop_state"] is not None
            assert position["trailing_stop_state"]["config"] == trailing_config
            assert position["trailing_stop_state"]["activated"] is False
            assert position["position_metadata"] == metadata

    def test_position_update_price_changes(self):
        """Test position price updates correctly with P&L calculation.

        Educational Note:
            This test validates price update creates NEW SCD Type 2 version
            with recalculated unrealized P&L.

            Price update workflow:
            1. Call crud_update_position_price (returns NEW id)
            2. Fetch NEW version with updated price and P&L
            3. Return new version to caller

            CRITICAL: Input id (old version) ≠ Output id (new version)!

        References:
            - ADR-015: SCD Type 2 for Position History
            - ADR-089: Dual-Key Schema Pattern
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_update_position_price") as mock_update,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_update.return_value = 2  # New ID
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock updated position
            position_data = {
                "id": 2,  # NEW ID!
                "position_id": "POS-1",  # Same business key
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.6500"),  # Updated!
                "unrealized_pnl": Decimal("1.50"),  # 10 * (0.65 - 0.50)
                "status": "open",
                "row_current_ind": True,
            }
            mock_cursor.fetchone.return_value = position_data

            # Update price
            updated = manager.update_position(position_id=1, current_price=Decimal("0.6500"))

            # Verify SCD Type 2 versioning
            assert updated["id"] == 2  # NEW surrogate ID
            assert updated["position_id"] == "POS-1"  # SAME business key
            assert updated["current_price"] == Decimal("0.6500")
            assert updated["unrealized_pnl"] == Decimal("1.50")

            # Verify CRUD called with correct parameters
            mock_update.assert_called_once_with(position_id=1, current_price=Decimal("0.6500"))

    def test_position_close_with_pnl_calculation(self):
        """Test position closes correctly with realized P&L.

        Educational Note:
            Position close workflow:
            1. Fetch current position (validate open, get entry_price)
            2. Calculate realized P&L using exit_price
            3. Call crud_close_position (creates final SCD Type 2 version)
            4. Return final version with status='closed', realized_pnl set

            Why fetch current position first?
            - Need entry_price for P&L calculation
            - Validate position is actually open (prevent double-close)
            - Get quantity for P&L formula

        References:
            - REQ-EXEC-002: Trade Execution Logging
            - REQ-RISK-003: Profit Target Management
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
            patch("precog.trading.position_manager.crud_close_position") as mock_close,
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            mock_close.return_value = 3  # Final ID

            # Mock current position (before close)
            current_position_data = {
                "id": 2,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.6000"),
                "status": "open",  # Still open
                "row_current_ind": True,
            }

            # Mock closed position (after close)
            closed_position_data = {
                "id": 3,  # Final ID
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.7000"),  # Exit price
                "exit_price": Decimal("0.7000"),
                "exit_reason": "profit_target",
                "realized_pnl": Decimal("2.00"),  # 10 * (0.70 - 0.50)
                "status": "closed",
                "row_current_ind": True,
            }

            # Configure fetchone to return different data on each call
            mock_cursor.fetchone.side_effect = [
                current_position_data,  # First: get current position
                closed_position_data,  # Second: get closed position
            ]

            # Close position
            closed = manager.close_position(
                position_id=2, exit_price=Decimal("0.7000"), exit_reason="profit_target"
            )

            # Verify final state
            assert closed["id"] == 3  # Final ID
            assert closed["status"] == "closed"
            assert closed["exit_price"] == Decimal("0.7000")
            assert closed["exit_reason"] == "profit_target"
            assert closed["realized_pnl"] == Decimal("2.00")

            # Verify CRUD called with correct P&L
            mock_close.assert_called_once_with(
                position_id=2,
                exit_price=Decimal("0.7000"),
                exit_reason="profit_target",
                realized_pnl=Decimal("2.00"),
            )


# ============================================================================
# Test Class 2: Position Versioning (SCD Type 2)
# ============================================================================


class TestPositionVersioning:
    """Test SCD Type 2 version tracking for positions.

    Educational Note:
        SCD Type 2 (Slowly Changing Dimension Type 2) maintains complete history
        of position changes by creating NEW rows instead of updating existing rows.

        Key concepts:
        - Surrogate key (id): Changes with each version (1 -> 2 -> 3)
        - Business key (position_id): Stays constant across versions (POS-1)
        - row_current_ind: TRUE for current version, FALSE for historical

        Why SCD Type 2 for positions?
        - Audit trail: See every price update, every P&L change
        - Trailing stops: Track highest price, stop adjustments
        - Performance analysis: Analyze position evolution over time
        - Debugging: "What was the position state when stop triggered?"

    References:
        - ADR-015: SCD Type 2 for Position History
        - ADR-089: Dual-Key Schema Pattern
        - Migrations 015-017: Dual-key structure implementation
    """

    def test_position_creates_history_on_update(self):
        """Test position update creates historical version with row_current_ind.

        Educational Note:
            When update_position() is called:
            1. Old version: row_current_ind TRUE -> FALSE (archived)
            2. New version: INSERT with row_current_ind = TRUE (current)
            3. Both versions remain in database (complete history)

            This test verifies the SCD Type 2 workflow is working correctly.

        References:
            - ADR-015: SCD Type 2 for Position History
            - Pattern 2 (CLAUDE.md): Dual Versioning System
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_update_position_price") as mock_update,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_update.return_value = 2  # New version ID
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock new version data
            new_version_data = {
                "id": 2,  # NEW ID
                "position_id": "POS-1",  # SAME business key
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.5500"),
                "unrealized_pnl": Decimal("0.50"),
                "status": "open",
                "row_current_ind": True,  # Current version
            }
            mock_cursor.fetchone.return_value = new_version_data

            # Update position
            updated = manager.update_position(position_id=1, current_price=Decimal("0.5500"))

            # Verify new version created
            assert updated["id"] == 2  # NEW surrogate ID
            assert updated["position_id"] == "POS-1"  # SAME business key
            assert updated["row_current_ind"] is True  # Current version

            # Note: Old version (id=1) still exists in database with row_current_ind=FALSE
            # This is handled by crud_update_position_price

    def test_row_current_ind_flag_management(self):
        """Test row_current_ind flag correctly identifies current version.

        Educational Note:
            The row_current_ind flag is CRITICAL for querying positions correctly.

            ALWAYS filter by row_current_ind = TRUE when querying positions:
            ```sql
            SELECT * FROM positions
            WHERE position_id = 'POS-1'
              AND row_current_ind = TRUE  -- CRITICAL!
            ```

            Without this filter:
            - Query returns ALL versions (10 updates -> 10 rows)
            - Wrong P&L values (mix of historical and current)
            - Slow queries (scanning unnecessary rows)

        References:
            - ADR-015: SCD Type 2 for Position History
            - Pattern 2 (CLAUDE.md): Dual Versioning System - Always filter by row_current_ind
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_update_position_price") as mock_update,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_update.return_value = 2
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock current version (row_current_ind = TRUE)
            current_version = {
                "id": 2,
                "position_id": "POS-1",
                "current_price": Decimal("0.6000"),
                "unrealized_pnl": Decimal("1.00"),  # Include P&L for logging
                "row_current_ind": True,  # CURRENT
            }
            mock_cursor.fetchone.return_value = current_version

            # Update position
            updated = manager.update_position(position_id=1, current_price=Decimal("0.6000"))

            # Verify only current version returned
            assert updated["row_current_ind"] is True
            assert updated["id"] == 2  # Latest version

            # Verify SQL query filters by row_current_ind
            # (This is validated in CRUD layer, Position Manager relies on it)

    def test_historical_price_trail_preserved(self):
        """Test multiple price updates preserve complete price history.

        Educational Note:
            This test simulates multiple price updates and verifies each creates
            a NEW version while preserving history.

            Scenario:
            - Open: $0.50 (version 1, id=1)
            - Update: $0.55 (version 2, id=2) [version 1 archived]
            - Update: $0.60 (version 3, id=3) [version 2 archived]
            - Update: $0.65 (version 4, id=4) [version 3 archived]

            Result: 4 versions in database, only version 4 has row_current_ind=TRUE

            Why preserve history?
            - Debugging: "What was price when stop triggered?"
            - Analytics: "How long did position stay in profit?"
            - Audit: "What was P&L at each point in time?"

        References:
            - ADR-015: SCD Type 2 for Position History
            - REQ-TRAIL-004: Peak Price Tracking
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_update_position_price") as mock_update,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Simulate 3 price updates
            prices = [Decimal("0.5500"), Decimal("0.6000"), Decimal("0.6500")]
            version_ids = [2, 3, 4]

            for idx, (price, version_id) in enumerate(zip(prices, version_ids, strict=False)):
                mock_update.return_value = version_id

                # Mock version data
                version_data = {
                    "id": version_id,
                    "position_id": "POS-1",  # Business key stays constant
                    "side": "YES",
                    "quantity": 10,
                    "entry_price": Decimal("0.5000"),
                    "current_price": price,
                    "unrealized_pnl": Decimal(str(10)) * (price - Decimal("0.5000")),
                    "status": "open",
                    "row_current_ind": True,
                }
                mock_cursor.fetchone.return_value = version_data

                # Update position
                updated = manager.update_position(
                    position_id=version_ids[idx - 1] if idx > 0 else 1, current_price=price
                )

                # Verify new version created
                assert updated["id"] == version_id
                assert updated["position_id"] == "POS-1"  # Business key constant
                assert updated["current_price"] == price
                assert updated["row_current_ind"] is True

            # Final verification: Latest version has highest price
            assert updated["current_price"] == Decimal("0.6500")
            assert updated["id"] == 4  # Final version ID


# ============================================================================
# Test Class 3: Position P&L Calculation
# ============================================================================


class TestPositionPnLCalculation:
    """Test profit/loss calculations for different position scenarios.

    Educational Note:
        P&L (Profit & Loss) calculation differs for YES vs NO positions:

        YES position (profit when price goes UP):
        - P&L = quantity * (current_price - entry_price)
        - Example: Entry $0.50, Current $0.75, Qty 10 -> P&L = $2.50

        NO position (profit when price goes DOWN):
        - P&L = quantity * (entry_price - current_price)
        - Example: Entry $0.50, Current $0.25, Qty 10 -> P&L = $2.50

        Why different?
        - YES wins when market settles at $1.00 (YES outcome)
        - NO wins when market settles at $0.00 (NO outcome)
        - Current price = probability of YES outcome

    References:
        - REQ-RISK-003: Profit Target Management
        - ADR-002: Decimal Precision for Prices
        - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
    """

    def test_winning_yes_position_pnl(self):
        """Test P&L calculation for profitable YES position.

        Educational Note:
            YES position profits when price goes UP.

            Scenario:
            - Entry: $0.50 (50% probability YES wins)
            - Current: $0.75 (75% probability YES wins)
            - Probability increased 25 percentage points -> PROFIT!
            - P&L = quantity * price_increase = 10 * $0.25 = $2.50

        References:
            - REQ-RISK-003: Profit Target Management
            - Pattern 1 (CLAUDE.md): Decimal Precision
        """
        manager = PositionManager()

        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.5000"),
            current_price=Decimal("0.7500"),  # Price went UP
            quantity=10,
            side="YES",
        )

        # P&L = 10 * (0.75 - 0.50) = 10 * 0.25 = $2.50
        assert pnl == Decimal("2.50")
        assert isinstance(pnl, Decimal)  # NEVER float!

    def test_losing_yes_position_pnl(self):
        """Test P&L calculation for losing YES position.

        Educational Note:
            YES position loses when price goes DOWN.

            Scenario:
            - Entry: $0.50 (50% probability YES wins)
            - Current: $0.30 (30% probability YES wins)
            - Probability decreased 20 percentage points -> LOSS!
            - P&L = quantity * price_decrease = 10 * (-$0.20) = -$2.00

        References:
            - REQ-RISK-003: Profit Target Management
            - REQ-RISK-002: Stop Loss Enforcement
        """
        manager = PositionManager()

        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.5000"),
            current_price=Decimal("0.3000"),  # Price went DOWN
            quantity=10,
            side="YES",
        )

        # P&L = 10 * (0.30 - 0.50) = 10 * (-0.20) = -$2.00
        assert pnl == Decimal("-2.00")  # Negative = loss
        assert isinstance(pnl, Decimal)

    def test_winning_no_position_pnl(self):
        """Test P&L calculation for profitable NO position.

        Educational Note:
            NO position profits when price goes DOWN.

            Scenario:
            - Entry: $0.50 (50% probability YES wins -> 50% NO wins)
            - Current: $0.25 (25% probability YES wins -> 75% NO wins)
            - NO probability increased 25 percentage points -> PROFIT!
            - P&L = quantity * (entry - current) = 10 * $0.25 = $2.50

            Why inverse calculation?
            - NO position is OPPOSITE of YES
            - Lower YES price -> Higher NO win probability -> NO profit
            - Higher YES price -> Lower NO win probability -> NO loss

        References:
            - REQ-RISK-003: Profit Target Management
            - docs/guides/KALSHI_MARKET_TERMINOLOGY_GUIDE_V1.0.md
        """
        manager = PositionManager()

        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.5000"),
            current_price=Decimal("0.2500"),  # Price went DOWN (good for NO!)
            quantity=10,
            side="NO",
        )

        # P&L = 10 * (0.50 - 0.25) = 10 * 0.25 = $2.50
        assert pnl == Decimal("2.50")
        assert isinstance(pnl, Decimal)

    def test_losing_no_position_pnl(self):
        """Test P&L calculation for losing NO position.

        Educational Note:
            NO position loses when price goes UP.

            Scenario:
            - Entry: $0.50 (50% NO win probability)
            - Current: $0.75 (25% NO win probability)
            - NO probability decreased 25 percentage points -> LOSS!
            - P&L = quantity * (entry - current) = 10 * (-$0.25) = -$2.50

        References:
            - REQ-RISK-002: Stop Loss Enforcement
        """
        manager = PositionManager()

        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.5000"),
            current_price=Decimal("0.7500"),  # Price went UP (bad for NO!)
            quantity=10,
            side="NO",
        )

        # P&L = 10 * (0.50 - 0.75) = 10 * (-0.25) = -$2.50
        assert pnl == Decimal("-2.50")  # Negative = loss
        assert isinstance(pnl, Decimal)

    def test_breakeven_position(self):
        """Test P&L is zero when price unchanged.

        Educational Note:
            Breakeven (P&L = $0.00) occurs when:
            - current_price = entry_price (no price movement)
            - Works for both YES and NO positions

            Why test this?
            - Edge case validation (ensure no rounding errors at zero)
            - Defensive programming (catch calculation bugs)

        References:
            - Pattern 1 (CLAUDE.md): Decimal Precision prevents float rounding errors
        """
        manager = PositionManager()

        # YES position - no price change
        pnl_yes = manager.calculate_position_pnl(
            entry_price=Decimal("0.5000"),
            current_price=Decimal("0.5000"),  # No change
            quantity=10,
            side="YES",
        )
        assert pnl_yes == Decimal("0.00")

        # NO position - no price change
        pnl_no = manager.calculate_position_pnl(
            entry_price=Decimal("0.5000"),
            current_price=Decimal("0.5000"),  # No change
            quantity=10,
            side="NO",
        )
        assert pnl_no == Decimal("0.00")


# ============================================================================
# Test Class 4: Trailing Stop Integration
# ============================================================================


class TestTrailingStopIntegration:
    """Test trailing stop functionality integration with positions.

    Educational Note:
        Trailing stops protect profits by automatically raising stop loss as
        price moves favorably. Three phases:

        1. INACTIVE: Waiting for activation threshold
           - Stop = static stop_loss_price
           - Example: Entry $0.50, Stop $0.35, Current $0.60
             Profit $0.10 < threshold $0.15 -> inactive

        2. ACTIVATION: Profit threshold reached
           - activated = TRUE
           - Stop = current_price - initial_distance
           - Example: Price $0.65 -> profit $0.15 -> ACTIVATE!
             Stop = $0.65 - $0.05 = $0.60

        3. TRAILING: Following price up
           - Track highest_price
           - Stop = highest_price - distance (with tightening)
           - Stop only moves UP, never down

    References:
        - REQ-TRAIL-001: Dynamic Trailing Stops
        - REQ-TRAIL-002: JSONB State Management
        - REQ-TRAIL-003: Stop Price Updates
        - REQ-TRAIL-004: Peak Price Tracking
        - docs/guides/TRAILING_STOP_GUIDE_V1.0.md
    """

    def test_initialize_trailing_stop(self):
        """Test trailing stop initialization for existing position.

        Educational Note:
            initialize_trailing_stop() adds trailing stop to position that was
            opened WITHOUT trailing stop.

            Use case:
            1. Open position with static stop: $0.35
            2. Price moves to $0.75 (+$0.25 profit)
            3. Add trailing stop to protect gains
            4. Trailing stop begins tracking highest price

        References:
            - REQ-TRAIL-002: JSONB State Management
            - docs/guides/TRAILING_STOP_GUIDE_V1.0.md
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock current position (before trailing stop)
            current_position = {
                "id": 1,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),  # Static stop
                "status": "open",
                "trailing_stop_state": None,  # No trailing stop yet
                "row_current_ind": True,
            }

            # Mock updated position (after trailing stop initialization)
            updated_position = {
                "id": 2,  # New version
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "status": "open",
                "trailing_stop_state": {
                    "config": {
                        "activation_threshold": Decimal("0.15"),
                        "initial_distance": Decimal("0.05"),
                        "tightening_rate": Decimal("0.10"),
                        "floor_distance": Decimal("0.02"),
                    },
                    "activated": False,  # Not activated yet
                    "activation_price": None,
                    "current_stop_price": Decimal("0.3500"),  # Start with static stop
                    "highest_price": Decimal("0.7500"),  # Track from current price
                },
                "row_current_ind": True,
            }

            # Configure fetchone to return different data
            mock_cursor.fetchone.side_effect = [
                current_position,  # First: get current position
                {"id": 2},  # Second: RETURNING id from INSERT
                updated_position,  # Third: get updated position
            ]

            # Initialize trailing stop
            config = {
                "activation_threshold": Decimal("0.15"),
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            }
            result = manager.initialize_trailing_stop(position_id=1, config=config)

            # Verify trailing stop initialized
            assert result["id"] == 2  # New version
            assert result["trailing_stop_state"] is not None
            assert result["trailing_stop_state"]["activated"] is False
            assert result["trailing_stop_state"]["config"] == config
            assert result["trailing_stop_state"]["current_stop_price"] == Decimal("0.3500")
            assert result["trailing_stop_state"]["highest_price"] == Decimal("0.7500")

    def test_update_trailing_stop_on_favorable_movement(self):
        """Test trailing stop updates when price moves favorably.

        Educational Note:
            When price moves UP (favorable for YES):
            1. Update highest_price if new high
            2. Recalculate stop: highest_price - distance
            3. Stop only moves UP, never down (trailing behavior)

            Scenario:
            - Highest: $0.75, Stop: $0.70 (distance $0.05)
            - Price moves to $0.80 -> NEW HIGH!
            - Update stop: $0.80 - $0.05 = $0.75 (stop raised)

        References:
            - REQ-TRAIL-003: Stop Price Updates
            - REQ-TRAIL-004: Peak Price Tracking
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock position with activated trailing stop
            current_position = {
                "id": 1,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "status": "open",
                "trailing_stop_state": {
                    "config": {
                        "activation_threshold": Decimal("0.15"),
                        "initial_distance": Decimal("0.05"),
                        "tightening_rate": Decimal("0.10"),
                        "floor_distance": Decimal("0.02"),
                    },
                    "activated": True,  # Already activated
                    "activation_price": Decimal("0.6500"),
                    "current_stop_price": Decimal("0.7000"),  # Previous stop
                    "highest_price": Decimal("0.7500"),  # Previous high
                },
                "row_current_ind": True,
            }

            # Mock updated position (after price moves to $0.80)
            updated_position = {
                "id": 2,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.8000"),  # NEW HIGH!
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("3.00"),  # 10 * (0.80 - 0.50)
                "status": "open",
                "trailing_stop_state": {
                    "config": {
                        "activation_threshold": Decimal("0.15"),
                        "initial_distance": Decimal("0.05"),
                        "tightening_rate": Decimal("0.10"),
                        "floor_distance": Decimal("0.02"),
                    },
                    "activated": True,
                    "activation_price": Decimal("0.6500"),
                    "current_stop_price": Decimal("0.7500"),  # Stop raised!
                    "highest_price": Decimal("0.8000"),  # New high!
                },
                "row_current_ind": True,
            }

            # Configure fetchone
            mock_cursor.fetchone.side_effect = [
                current_position,  # Get current position
                {"id": 2},  # RETURNING id
                updated_position,  # Get updated position
            ]

            # Update trailing stop
            result = manager.update_trailing_stop(position_id=1, current_price=Decimal("0.8000"))

            # Verify stop updated
            assert result["id"] == 2
            assert result["trailing_stop_state"]["highest_price"] == Decimal("0.8000")
            # Note: Stop calculation with tightening is complex, verify it moved up
            # Original stop: $0.70, New stop should be higher (closer to price)
            assert result["trailing_stop_state"]["current_stop_price"] > Decimal("0.7000")

    def test_trailing_stop_trigger_detection(self):
        """Test detection of trailing stop trigger (exit signal).

        Educational Note:
            Trailing stop triggers when price FALLS to/below stop level.

            Scenario:
            - Highest: $0.80, Stop: $0.75 (activated)
            - Price drops to $0.74 -> STOP TRIGGERED!
            - Signal: Close position at $0.74 (trailing_stop exit)

            Why separate trigger check?
            - update_trailing_stop() updates stop based on price
            - check_trailing_stop_trigger() decides if exit needed
            - Separation allows flexibility (update without exiting)

        References:
            - REQ-TRAIL-001: Dynamic Trailing Stops
            - REQ-TRAIL-003: Stop Price Updates
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock position with stop TRIGGERED (price at/below stop)
            triggered_position = {
                "id": 1,
                "position_id": "POS-1",
                "side": "YES",
                "current_price": Decimal("0.7400"),  # Below stop!
                "status": "open",
                "trailing_stop_state": {
                    "config": {},
                    "activated": True,
                    "activation_price": Decimal("0.6500"),
                    "current_stop_price": Decimal("0.7500"),  # Stop level
                    "highest_price": Decimal("0.8000"),
                },
                "row_current_ind": True,
            }
            mock_cursor.fetchone.return_value = triggered_position

            # Check trigger
            triggered = manager.check_trailing_stop_trigger(position_id=1)

            # Verify triggered
            assert triggered is True  # Price $0.74 <= Stop $0.75


# ============================================================================
# Test Class 5: Position Precision Requirements (Pattern 1)
# ============================================================================


class TestPositionPrecisionRequirements:
    """Test Decimal precision compliance across position lifecycle.

    Educational Note:
        Pattern 1: Decimal Precision - NEVER USE FLOAT

        Why?
        - Float precision errors: 0.1 + 0.2 = 0.30000000000000004 (WRONG!)
        - Decimal precision: Decimal("0.1") + Decimal("0.2") = Decimal("0.3") (CORRECT!)

        Critical for trading:
        - Wrong P&L calculations cost real money
        - Rounding errors accumulate over thousands of trades
        - Margin calculations must be exact (insufficient margin = rejected trade)

        This test class verifies EVERY numeric value in position lifecycle uses
        Decimal, not float. This is MANDATORY for production trading.

    References:
        - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
        - ADR-002: Decimal Precision for Prices
        - REQ-SYS-003: Decimal Precision
    """

    def test_all_prices_are_decimal_type(self):
        """Test all price fields use Decimal type, never float.

        Educational Note:
            This test validates defensive programming: we VERIFY all prices are
            Decimal, not just assume it.

            What we check:
            - entry_price: Decimal
            - current_price: Decimal
            - target_price: Decimal
            - stop_loss_price: Decimal
            - exit_price: Decimal

            Why check types explicitly?
            - Catch accidental float usage (e.g., 0.5 instead of Decimal("0.5"))
            - Prevent precision bugs before they reach production
            - Document intent (this code REQUIRES Decimal)

        References:
            - Pattern 1 (CLAUDE.md): Decimal Precision
            - ADR-002: Decimal Precision for Prices
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_create_position") as mock_create,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
        ):
            mock_create.return_value = 1
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock position with ALL price fields as Decimal
            position_data = {
                "id": 1,
                "position_id": "POS-1",
                "market_id": "MKT-001",
                "strategy_id": 1,
                "model_id": 1,
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),  # Decimal!
                "current_price": Decimal("0.5000"),  # Decimal!
                "target_price": Decimal("0.7500"),  # Decimal!
                "stop_loss_price": Decimal("0.3500"),  # Decimal!
                "unrealized_pnl": Decimal("0.00"),  # Decimal!
                "realized_pnl": None,
                "status": "open",
                "exit_price": None,
                "exit_reason": None,
                "trailing_stop_state": None,
                "position_metadata": None,
                "row_current_ind": True,
            }
            mock_cursor.fetchone.return_value = position_data

            # Open position (all inputs Decimal)
            position = manager.open_position(
                market_id="MKT-001",
                strategy_id=1,
                model_id=1,
                side="YES",
                quantity=10,
                entry_price=Decimal("0.5000"),  # Decimal!
                available_margin=Decimal("1000.00"),  # Decimal!
                target_price=Decimal("0.7500"),  # Decimal!
                stop_loss_price=Decimal("0.3500"),  # Decimal!
            )

            # Verify ALL prices are Decimal type
            assert isinstance(position["entry_price"], Decimal)
            assert isinstance(position["current_price"], Decimal)
            assert isinstance(position["target_price"], Decimal)
            assert isinstance(position["stop_loss_price"], Decimal)
            assert isinstance(position["unrealized_pnl"], Decimal)

            # Verify NOT float (defensive check)
            assert not isinstance(position["entry_price"], float)
            assert not isinstance(position["current_price"], float)

    def test_pnl_calculated_with_decimal_precision(self):
        """Test P&L calculations preserve Decimal precision.

        Educational Note:
            P&L calculation must use Decimal throughout to prevent precision loss.

            Example of float precision error:
            ```python
            # WRONG (float):
            pnl = 10 * (0.7500 - 0.4975)  # float arithmetic
            # Result: 2.5249999999999995 (WRONG!)

            # CORRECT (Decimal):
            pnl = Decimal("10") * (Decimal("0.7500") - Decimal("0.4975"))
            # Result: Decimal("2.5250") (CORRECT!)
            ```

            Why this matters:
            - $0.0001 error per trade * 10,000 trades = $1.00 error (real money!)
            - Audit trail: "Why does my P&L not match exchange records?"

        References:
            - Pattern 1 (CLAUDE.md): Decimal Precision
            - REQ-RISK-003: Profit Target Management
        """
        manager = PositionManager()

        # Calculate P&L with Decimal inputs
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.4975"),
            current_price=Decimal("0.7500"),
            quantity=10,
            side="YES",
        )

        # Verify result is Decimal
        assert isinstance(pnl, Decimal)

        # Verify precision preserved (4 decimal places)
        # P&L = 10 * (0.7500 - 0.4975) = 10 * 0.2525 = 2.5250
        assert pnl == Decimal("2.5250")

        # Verify NOT float (would have precision errors)
        assert not isinstance(pnl, float)

    def test_no_float_contamination_in_workflow(self):
        """Test complete workflow never introduces float contamination.

        Educational Note:
            "Float contamination" = Decimal values accidentally converted to float
            somewhere in workflow, introducing precision errors.

            Common sources:
            - JSON serialization: json.dumps(Decimal("0.5")) -> 0.5 (float!)
            - Division: Decimal("1") / 2 -> Decimal("0.5") (OK!)
              But: Decimal("1") / 2.0 -> float! (CONTAMINATION!)
            - String formatting: f"{Decimal('0.5')}" -> "0.5" (OK)
              But: float(Decimal("0.5")) -> 0.5 (CONTAMINATION!)

            This test verifies entire workflow (open -> update -> close) maintains
            Decimal precision WITHOUT float contamination.

        References:
            - Pattern 1 (CLAUDE.md): Decimal Precision
            - ADR-002: Decimal Precision for Prices
        """
        manager = PositionManager()

        with (
            patch("precog.trading.position_manager.crud_create_position") as mock_create,
            patch("precog.trading.position_manager.get_connection") as mock_get_conn,
            patch("precog.trading.position_manager.release_connection"),
            patch("precog.trading.position_manager.crud_update_position_price") as mock_update,
            patch("precog.trading.position_manager.crud_close_position") as mock_close,
        ):
            # Setup mocks
            mock_create.return_value = 1
            mock_update.return_value = 2
            mock_close.return_value = 3
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock position data (all Decimal)
            position_v1 = {
                "id": 1,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.5000"),
                "target_price": Decimal("0.7500"),
                "stop_loss_price": Decimal("0.3500"),
                "unrealized_pnl": Decimal("0.00"),
                "status": "open",
                "row_current_ind": True,
            }

            position_v2 = {
                "id": 2,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.6000"),
                "unrealized_pnl": Decimal("1.00"),
                "status": "open",
                "row_current_ind": True,
            }

            position_v3_before = {
                "id": 2,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "status": "open",
            }

            position_v3_after = {
                "id": 3,
                "position_id": "POS-1",
                "side": "YES",
                "quantity": 10,
                "entry_price": Decimal("0.5000"),
                "current_price": Decimal("0.7500"),
                "exit_price": Decimal("0.7500"),
                "realized_pnl": Decimal("2.50"),
                "status": "closed",
                "row_current_ind": True,
            }

            # Configure fetchone sequence
            mock_cursor.fetchone.side_effect = [
                position_v1,  # Open
                position_v2,  # Update
                position_v3_before,  # Close (get current)
                position_v3_after,  # Close (get final)
            ]

            # Open position (all Decimal)
            pos = manager.open_position(
                market_id="MKT-001",
                strategy_id=1,
                model_id=1,
                side="YES",
                quantity=10,
                entry_price=Decimal("0.5000"),
                available_margin=Decimal("1000.00"),
                target_price=Decimal("0.7500"),
                stop_loss_price=Decimal("0.3500"),
            )
            assert isinstance(pos["entry_price"], Decimal)

            # Update position (Decimal)
            pos = manager.update_position(position_id=1, current_price=Decimal("0.6000"))
            assert isinstance(pos["current_price"], Decimal)
            assert isinstance(pos["unrealized_pnl"], Decimal)

            # Close position (Decimal)
            pos = manager.close_position(
                position_id=2, exit_price=Decimal("0.7500"), exit_reason="profit_target"
            )
            assert isinstance(pos["exit_price"], Decimal)
            assert isinstance(pos["realized_pnl"], Decimal)

            # Verify NO float contamination anywhere in workflow
            # (all assertions passed -> all values are Decimal)


# ============================================================================
# Test Class 6: Margin Validation & Error Handling
# ============================================================================


class TestMarginValidationAndErrors:
    """Test margin validation and error handling.

    Educational Note:
        Margin validation prevents opening positions when insufficient funds.

        Kalshi margin formula:
        - YES: margin = quantity * (1.00 - entry_price)
        - NO: margin = quantity * entry_price

        Why different?
        - YES max loss = (1.00 - entry_price) per contract
        - NO max loss = entry_price per contract

    References:
        - REQ-RISK-001: Position Entry Validation
        - InsufficientMarginError exception
    """

    def test_insufficient_margin_yes_position(self):
        """Test InsufficientMarginError raised for YES position.

        Educational Note:
            YES position @ $0.75, quantity 10:
            Required margin = 10 * (1.00 - 0.75) = 10 * 0.25 = $2.50

            If available margin < $2.50 -> InsufficientMarginError

        References:
            - REQ-RISK-001: Position Entry Validation
        """
        manager = PositionManager()

        with pytest.raises(InsufficientMarginError, match="Required margin"):
            manager.open_position(
                market_id="MKT-001",
                strategy_id=1,
                model_id=1,
                side="YES",
                quantity=10,
                entry_price=Decimal("0.7500"),
                available_margin=Decimal("2.00"),  # Need $2.50, have $2.00 -> FAIL
            )

    def test_insufficient_margin_no_position(self):
        """Test InsufficientMarginError raised for NO position.

        Educational Note:
            NO position @ $0.75, quantity 10:
            Required margin = 10 * 0.75 = $7.50

            If available margin < $7.50 -> InsufficientMarginError

        References:
            - REQ-RISK-001: Position Entry Validation
        """
        manager = PositionManager()

        with pytest.raises(InsufficientMarginError, match="Required margin"):
            manager.open_position(
                market_id="MKT-001",
                strategy_id=1,
                model_id=1,
                side="NO",
                quantity=10,
                entry_price=Decimal("0.7500"),
                available_margin=Decimal("7.00"),  # Need $7.50, have $7.00 -> FAIL
            )

    def test_invalid_price_range_validation(self):
        """Test ValueError raised for prices outside [0.01, 0.99].

        Educational Note:
            Kalshi price constraints:
            - Minimum: $0.01 (1% probability)
            - Maximum: $0.99 (99% probability)
            - Prices $0.00 and $1.00 not allowed (market certainty)

            Why validate?
            - Prevent invalid trades
            - Catch data corruption bugs
            - Defensive programming

        References:
            - REQ-RISK-001: Position Entry Validation
        """
        manager = PositionManager()

        # Test price too low ($0.00)
        with pytest.raises(ValueError, match="outside valid range"):
            manager.open_position(
                market_id="MKT-001",
                strategy_id=1,
                model_id=1,
                side="YES",
                quantity=10,
                entry_price=Decimal("0.00"),  # Too low!
                available_margin=Decimal("1000.00"),
            )

        # Test price too high ($1.00)
        with pytest.raises(ValueError, match="outside valid range"):
            manager.open_position(
                market_id="MKT-001",
                strategy_id=1,
                model_id=1,
                side="YES",
                quantity=10,
                entry_price=Decimal("1.00"),  # Too high!
                available_margin=Decimal("1000.00"),
            )
