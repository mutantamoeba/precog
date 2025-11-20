"""Position Manager - Position Lifecycle Management.

This module manages position lifecycle from entry to exit with comprehensive
risk management and P&L tracking.

Educational Note:
    Positions use SCD Type 2 versioning for price/state history, NOT immutable
    versions like strategies/models. Every price update creates a NEW row with
    updated row_current_ind = TRUE (current version) and old row becomes FALSE.

    This allows tracking:
    - Price evolution over time
    - Unrealized P&L changes
    - Trailing stop activation points
    - Exit condition evaluations

References:
    - REQ-RISK-001: Position Entry Validation
    - REQ-RISK-002: Stop Loss Enforcement
    - REQ-RISK-003: Profit Target Management
    - REQ-RISK-004: Trailing Stop Implementation
    - REQ-EXEC-001: Trade Execution Workflow
    - ADR-015: SCD Type 2 for Position History (Migrations 015-017)
    - ADR-089: Dual-Key Schema Pattern (positions use surrogate id + business key)
    - docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md
    - docs/guides/TRAILING_STOP_GUIDE_V1.0.md
    - docs/database/DATABASE_SCHEMA_SUMMARY_V1.9.md (positions table)

Phase: 1.5 (Foundation Validation)
"""

from decimal import Decimal
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from precog.database.connection import get_connection, release_connection
from precog.database.crud_operations import (
    close_position as crud_close_position,
)
from precog.database.crud_operations import (
    create_position as crud_create_position,
)
from precog.database.crud_operations import (
    get_current_positions,
)
from precog.database.crud_operations import (
    update_position_price as crud_update_position_price,
)
from precog.utils.logger import get_logger

logger = get_logger(__name__)


class InvalidPositionStateError(Exception):
    """Raised when position is in invalid state for requested operation.

    Examples:
        - Trying to close position that's already closed
        - Trying to update price on closed position
        - Trying to execute trade when position doesn't exist
    """


class InsufficientMarginError(Exception):
    """Raised when account has insufficient margin to open position.

    Educational Note:
        Kalshi requires margin = quantity * ($1 - entry_price)
        Example: YES contract at $0.75 with 10 quantity:
            margin = 10 * ($1.00 - $0.75) = 10 * $0.25 = $2.50
    """


class PositionManager:
    """Manages position lifecycle with risk management and P&L tracking.

    This class provides high-level position management operations that wrap
    CRUD functions with additional business logic, validation, and logging.

    Educational Note:
        Position Manager vs CRUD Operations:

        **CRUD Operations** (database layer):
        - Low-level database operations (INSERT, UPDATE, SELECT)
        - Minimal validation (NOT NULL constraints, types)
        - No business logic
        - Used by: Position Manager, Strategy Manager, Model Manager

        **Position Manager** (business logic layer):
        - High-level position lifecycle management
        - Business rule validation (margin checks, risk limits)
        - P&L calculations
        - Integration with Strategy/Model managers
        - Comprehensive logging and error handling

        Think of it like building a house:
        - CRUD = hammer, saw, nails (tools)
        - Position Manager = architect + construction manager (orchestration)

    Usage:
        ```python
        manager = PositionManager()

        # Open position
        position = manager.open_position(
            market_id="KALSHI-NFL-001",
            strategy_id=42,
            model_id=7,
            side="YES",
            quantity=10,
            entry_price=Decimal("0.4975"),
            target_price=Decimal("0.7500"),
            stop_loss_price=Decimal("0.3500"),
            available_margin=Decimal("1000.00")
        )

        # Update position price (creates new SCD Type 2 version)
        manager.update_position(
            position_id=position["id"],  # Surrogate key, not business key!
            current_price=Decimal("0.5200")
        )

        # Close position
        manager.close_position(
            position_id=position["id"],
            exit_price=Decimal("0.5500"),
            exit_reason="profit_target"
        )
        ```

    Attributes:
        None (stateless, uses database connection from pool)

    Trade-offs:
        **Why wrap CRUD operations instead of calling them directly?**
        - Pros: Centralized business logic, comprehensive logging, easier testing,
                consistent error handling
        - Cons: Additional abstraction layer, potential performance overhead
        - Decision: Use Position Manager for all position operations in Phase 1.5+,
                   allows us to add risk checks/logging without changing call sites

    References:
        - docs/guides/POSITION_MANAGEMENT_GUIDE_V1.0.md - Complete position management patterns
        - docs/database/DATABASE_SCHEMA_SUMMARY_V1.9.md - positions table schema (dual-key structure)
    """

    def __init__(self):
        """Initialize Position Manager.

        Educational Note:
            Manager is stateless - doesn't hold database connection.
            Each method gets fresh connection from pool for thread safety.

            Why stateless?
            - Thread-safe (no shared state between concurrent calls)
            - Connection pool handles connection reuse efficiently
            - Simpler error handling (no cleanup in __del__)
        """

    def open_position(
        self,
        market_id: str,
        strategy_id: int,
        model_id: int,
        side: str,
        quantity: int,
        entry_price: Decimal,
        available_margin: Decimal,
        target_price: Decimal | None = None,
        stop_loss_price: Decimal | None = None,
        trailing_stop_config: dict[str, Any] | None = None,
        position_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Open new position with risk validation.

        Args:
            market_id: Market identifier (e.g., 'KALSHI-NFL-001')
            strategy_id: Strategy that generated this signal (trade attribution)
            model_id: Model that calculated probability (trade attribution)
            side: Position side ('YES' or 'NO')
            quantity: Number of contracts
            entry_price: Entry price (Decimal, NEVER float!)
            available_margin: Account's available margin for validation
            target_price: Optional profit target price
            stop_loss_price: Optional stop loss price
            trailing_stop_config: Optional trailing stop configuration
            position_metadata: Optional metadata (edges, probabilities, etc.)

        Returns:
            Dictionary containing created position with all fields including:
                - id: Surrogate primary key (int)
                - position_id: Business key (str, format: 'POS-{id}')
                - market_id, strategy_id, model_id (trade attribution)
                - side, quantity, entry_price
                - status: 'open'
                - row_current_ind: TRUE (current version)

        Raises:
            InsufficientMarginError: If available_margin < required_margin
            ValueError: If entry_price not in valid range [0.01, 0.99]
            psycopg2.IntegrityError: If market_id/strategy_id/model_id invalid FK

        Educational Note:
            **Kalshi Margin Calculation:**
            Required margin depends on position side:
            - YES position: margin = quantity * (1.00 - entry_price)
            - NO position: margin = quantity * entry_price

            Example:
                - YES @ $0.75, quantity 10: margin = 10 * 0.25 = $2.50
                - NO @ $0.75, quantity 10: margin = 10 * 0.75 = $7.50

            Why different? Because:
            - YES wins $1.00, loses (1.00 - entry_price)
            - NO wins (1.00 - entry_price), loses $1.00

            Maximum loss = margin requirement (Kalshi enforces this)

        References:
            - REQ-RISK-001: Position Entry Validation
            - REQ-SYS-003: Decimal Precision (ALWAYS use Decimal for prices)
            - Pattern 1 (CLAUDE.md): Decimal Precision - NEVER USE FLOAT
            - ADR-002: Decimal Precision for Prices
        """
        # Validation: Price range
        if not (Decimal("0.01") <= entry_price <= Decimal("0.99")):
            raise ValueError(f"Entry price {entry_price} outside valid range [0.01, 0.99]")

        # Validation: Side
        if side not in ("YES", "NO"):
            raise ValueError(f"Invalid side '{side}', must be 'YES' or 'NO'")

        # Calculate required margin
        if side == "YES":
            required_margin = Decimal(str(quantity)) * (Decimal("1.00") - entry_price)
        else:  # NO
            required_margin = Decimal(str(quantity)) * entry_price

        # Validation: Margin check
        if available_margin < required_margin:
            logger.warning(
                "Insufficient margin to open position",
                extra={
                    "required_margin": str(required_margin),
                    "available_margin": str(available_margin),
                    "market_id": market_id,
                    "side": side,
                    "quantity": quantity,
                    "entry_price": str(entry_price),
                },
            )
            raise InsufficientMarginError(
                f"Required margin {required_margin}, available {available_margin}"
            )

        # Prepare trailing stop state if config provided
        trailing_stop_state = None
        if trailing_stop_config:
            trailing_stop_state = {
                "config": trailing_stop_config,
                "activated": False,
                "activation_price": None,
                "current_stop_price": stop_loss_price,  # Initial stop = static stop loss
            }

        # Create position via CRUD
        try:
            position_id = crud_create_position(
                market_id=market_id,
                strategy_id=strategy_id,
                model_id=model_id,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                target_price=target_price,
                stop_loss_price=stop_loss_price,
                trailing_stop_state=trailing_stop_state,
                position_metadata=position_metadata,
            )

            # Fetch full position data
            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT * FROM positions
                        WHERE id = %s
                        """,
                        (position_id,),
                    )
                    position = cur.fetchone()

                logger.info(
                    f"Opened position {position['position_id']}",
                    extra={
                        "position_id": position_id,
                        "market_id": market_id,
                        "side": side,
                        "quantity": quantity,
                        "entry_price": str(entry_price),
                        "required_margin": str(required_margin),
                    },
                )

                return dict(position)

            finally:
                release_connection(conn)

        except psycopg2.IntegrityError as e:
            logger.error(
                "Failed to create position - foreign key violation",
                extra={
                    "market_id": market_id,
                    "strategy_id": strategy_id,
                    "model_id": model_id,
                    "error": str(e),
                },
            )
            raise

    def update_position(
        self,
        position_id: int,  # Surrogate key, NOT business key!
        current_price: Decimal,
    ) -> dict[str, Any]:
        """Update position price and calculate unrealized P&L.

        This method creates a NEW SCD Type 2 version of the position with updated
        current_price and unrealized_pnl. The old version gets row_current_ind = FALSE,
        new version gets row_current_ind = TRUE.

        Args:
            position_id: Position surrogate key (int from positions.id, NOT position_id business key!)
            current_price: New market price (Decimal, NEVER float!)

        Returns:
            Dictionary containing updated position (new version) with:
                - id: NEW surrogate key (different from input!)
                - position_id: SAME business key (copied from old version)
                - current_price: Updated price
                - unrealized_pnl: Calculated P&L
                - row_current_ind: TRUE (current version)

        Raises:
            ValueError: If position not found or already closed
            ValueError: If current_price outside valid range [0.01, 0.99]

        Educational Note:
            **SCD Type 2 Versioning:**
            When you call this method:
            1. Old version: row_current_ind TRUE → FALSE (archived)
            2. New version: INSERT with row_current_ind = TRUE (current)
            3. Surrogate id changes, business key stays the same

            Example:
                Before: id=123, position_id='POS-100', current_price=0.50, row_current_ind=TRUE
                After update to 0.55:
                    Old: id=123, position_id='POS-100', current_price=0.50, row_current_ind=FALSE
                    New: id=456, position_id='POS-100', current_price=0.55, row_current_ind=TRUE

            **IMPORTANT:** The returned id (456) is DIFFERENT from input (123)!
            Always use the NEW id for subsequent operations.

        References:
            - ADR-015: SCD Type 2 for Position History
            - ADR-089: Dual-Key Schema Pattern (surrogate id + business key)
            - Migrations 015-017: Dual-key structure implementation
        """
        # Validation: Price range
        if not (Decimal("0.01") <= current_price <= Decimal("0.99")):
            raise ValueError(f"Current price {current_price} outside valid range [0.01, 0.99]")

        # Update position via CRUD (creates new SCD Type 2 version)
        try:
            new_position_id = crud_update_position_price(
                position_id=position_id,  # Surrogate key
                current_price=current_price,
            )

            # Fetch full position data (new version)
            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT * FROM positions
                        WHERE id = %s
                        """,
                        (new_position_id,),
                    )
                    position = cur.fetchone()

                logger.info(
                    f"Updated position {position['position_id']} price",
                    extra={
                        "old_id": position_id,  # Old surrogate key
                        "new_id": new_position_id,  # New surrogate key
                        "business_key": position["position_id"],
                        "current_price": str(current_price),
                        "unrealized_pnl": str(position["unrealized_pnl"]),
                    },
                )

                return dict(position)

            finally:
                release_connection(conn)

        except ValueError as e:
            logger.error(
                "Failed to update position",
                extra={
                    "position_id": position_id,
                    "current_price": str(current_price),
                    "error": str(e),
                },
            )
            raise

    def close_position(
        self,
        position_id: int,  # Surrogate key, NOT business key!
        exit_price: Decimal,
        exit_reason: str,
    ) -> dict[str, Any]:
        """Close position and record final P&L.

        This method creates a NEW SCD Type 2 version with status='closed',
        current_price=exit_price, and realized_pnl calculated.

        Args:
            position_id: Position surrogate key (int from positions.id)
            exit_price: Exit execution price (Decimal, NEVER float!)
            exit_reason: Reason for exit ('profit_target', 'stop_loss', 'manual', etc.)

        Returns:
            Dictionary containing closed position (final version) with:
                - id: NEW surrogate key
                - position_id: SAME business key
                - status: 'closed'
                - current_price: exit_price
                - realized_pnl: Final P&L
                - row_current_ind: TRUE

        Raises:
            ValueError: If position not found or already closed
            ValueError: If exit_price outside valid range [0.01, 0.99]

        Educational Note:
            **Exit Reasons:**
            - 'profit_target': Hit target price
            - 'stop_loss': Hit stop loss price
            - 'trailing_stop': Trailing stop triggered
            - 'market_close': Market closed/settled
            - 'manual': Manual user exit
            - 'risk_limit': Risk management override

            Tracking exit reasons enables:
            - Strategy performance analysis (how often do we hit targets?)
            - Stop loss effectiveness analysis
            - Risk management validation

        References:
            - REQ-EXEC-002: Trade Execution Logging
            - REQ-RISK-002: Stop Loss Enforcement
            - REQ-RISK-003: Profit Target Management
        """
        # Validation: Price range
        if not (Decimal("0.01") <= exit_price <= Decimal("0.99")):
            raise ValueError(f"Exit price {exit_price} outside valid range [0.01, 0.99]")

        # Get current position data to calculate realized P&L
        conn = get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM positions
                    WHERE id = %s AND row_current_ind = TRUE
                    """,
                    (position_id,),
                )
                current_position = cur.fetchone()

                if not current_position:
                    raise ValueError(f"Position {position_id} not found or not current")

                if current_position["status"] == "closed":
                    raise ValueError(f"Position {position_id} is already closed")

                # Calculate realized P&L
                realized_pnl = self.calculate_position_pnl(
                    entry_price=current_position["entry_price"],
                    current_price=exit_price,
                    quantity=current_position["quantity"],
                    side=current_position["side"],
                )

        finally:
            release_connection(conn)

        # Close position via CRUD (creates final SCD Type 2 version)
        try:
            final_position_id = crud_close_position(
                position_id=position_id,
                exit_price=exit_price,
                exit_reason=exit_reason,
                realized_pnl=realized_pnl,
            )

            # Fetch full position data (final version)
            conn = get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT * FROM positions
                        WHERE id = %s
                        """,
                        (final_position_id,),
                    )
                    position = cur.fetchone()

                logger.info(
                    f"Closed position {position['position_id']}",
                    extra={
                        "old_id": position_id,
                        "final_id": final_position_id,
                        "business_key": position["position_id"],
                        "exit_price": str(exit_price),
                        "exit_reason": exit_reason,
                        "realized_pnl": str(position["realized_pnl"]),
                    },
                )

                return dict(position)

            finally:
                release_connection(conn)

        except ValueError as e:
            logger.error(
                "Failed to close position",
                extra={
                    "position_id": position_id,
                    "exit_price": str(exit_price),
                    "exit_reason": exit_reason,
                    "error": str(e),
                },
            )
            raise

    def get_open_positions(
        self,
        market_id: str | None = None,
        strategy_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve all open positions with optional filtering.

        Args:
            market_id: Optional market filter (business key string like 'MKT-123')
            strategy_id: Optional strategy filter (surrogate key int)

        Returns:
            List of dictionaries containing open positions (row_current_ind = TRUE only)

        Educational Note:
            **SCD Type 2 Query Pattern:**
            ALWAYS filter by row_current_ind = TRUE when querying positions,
            otherwise you'll get ALL historical versions (slow query, wrong results).

            Example:
                - Position POS-100 has 10 price updates → 10 rows in database
                - Query WITHOUT row_current_ind filter: Returns 10 rows (WRONG!)
                - Query WITH row_current_ind = TRUE: Returns 1 row (CORRECT!)

            CRUD operation get_current_positions() already includes this filter,
            so we can safely call it without worrying about historical versions.

            **Note on filtering:**
            CRUD function get_current_positions() only supports filtering by
            status and market_id (int). For strategy_id filtering, we get all
            open positions and filter in Python (acceptable for now since we
            won't have thousands of positions).

        References:
            - ADR-015: SCD Type 2 for Position History
            - Pattern 2 (CLAUDE.md): Dual Versioning System
        """
        # Get all open positions (status='open', row_current_ind=TRUE)
        # Note: CRUD function accepts market_id as int, but we receive str
        # For now, pass None for market_id filtering (we'll filter in Python)
        positions = get_current_positions(status="open", market_id=None)

        # Apply filters manually
        filtered = positions

        if market_id is not None:
            filtered = [p for p in filtered if p.get("market_id") == market_id]

        if strategy_id is not None:
            filtered = [p for p in filtered if p.get("strategy_id") == strategy_id]

        return filtered

    def calculate_position_pnl(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        quantity: int,
        side: str,
    ) -> Decimal:
        """Calculate unrealized P&L for position.

        Args:
            entry_price: Position entry price
            current_price: Current market price
            quantity: Number of contracts
            side: Position side ('YES' or 'NO')

        Returns:
            Unrealized P&L (Decimal)

        Educational Note:
            **P&L Calculation:**
            YES position:
                - Profit if price goes UP
                - P&L = quantity * (current_price - entry_price)
                - Example: Entry $0.50, Current $0.75, Qty 10
                  P&L = 10 * ($0.75 - $0.50) = 10 * $0.25 = $2.50

            NO position:
                - Profit if price goes DOWN
                - P&L = quantity * (entry_price - current_price)
                - Example: Entry $0.50, Current $0.25, Qty 10
                  P&L = 10 * ($0.50 - $0.25) = 10 * $0.25 = $2.50

            Why different? Because:
            - YES wins when market settles YES ($1.00)
            - NO wins when market settles NO ($0.00)
            - Current price reflects YES win probability

        References:
            - REQ-RISK-003: Profit Target Management
            - ADR-002: Decimal Precision for Prices
        """
        if side == "YES":
            pnl = Decimal(str(quantity)) * (current_price - entry_price)
        else:  # NO
            pnl = Decimal(str(quantity)) * (entry_price - current_price)

        return pnl
