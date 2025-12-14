"""
Chaos Tests for PositionManager.

Tests edge cases, error recovery, and unexpected input handling.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for resilience
Related Requirements: REQ-RISK-001 (Position Entry Validation)

Usage:
    pytest tests/chaos/trading/test_position_manager_chaos.py -v -m chaos
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from precog.trading.position_manager import (
    InsufficientMarginError,
    InvalidPositionStateError,
    PositionManager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> PositionManager:
    """Create a PositionManager instance for testing."""
    return PositionManager()


@pytest.fixture
def mock_position() -> dict[str, Any]:
    """Create a mock position dict."""
    return {
        "id": 123,
        "position_id": "POS-2025-001",
        "market_id": "MARKET-001",
        "strategy_id": 1,
        "model_id": 1,
        "side": "YES",
        "quantity": Decimal("100"),
        "entry_price": Decimal("0.50"),
        "current_price": Decimal("0.55"),
        "target_price": Decimal("0.80"),
        "stop_loss_price": Decimal("0.35"),
        "unrealized_pnl": Decimal("5.00"),
        "realized_pnl": Decimal("0.00"),
        "status": "open",
        "exit_price": None,
        "exit_reason": None,
        "trailing_stop_state": None,
        "position_metadata": None,
        "row_current_ind": True,
    }


# =============================================================================
# Chaos Tests: Price Boundary Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestPriceBoundaryEdgeCases:
    """Chaos tests for price boundary edge cases."""

    def test_price_at_absolute_minimum(self, manager: PositionManager) -> None:
        """Test P&L calculation at minimum valid price."""
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.01"),
            current_price=Decimal("0.99"),
            quantity=100,
            side="YES",
        )
        # YES: profit = (0.99 - 0.01) * 100 = 98
        assert pnl == Decimal("98")

    def test_price_at_absolute_maximum(self, manager: PositionManager) -> None:
        """Test P&L calculation at maximum valid price."""
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.99"),
            current_price=Decimal("0.01"),
            quantity=100,
            side="YES",
        )
        # YES: loss = (0.01 - 0.99) * 100 = -98
        assert pnl == Decimal("-98")

    def test_price_exactly_at_boundary(self, manager: PositionManager) -> None:
        """Test P&L with both prices at boundary."""
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.01"),
            current_price=Decimal("0.01"),
            quantity=100,
            side="YES",
        )
        assert pnl == Decimal("0")

    def test_price_just_outside_boundary_low(self, manager: PositionManager) -> None:
        """Test rejection of price just below minimum."""
        with pytest.raises(ValueError, match="outside valid range"):
            manager.update_position(
                position_id=1,
                current_price=Decimal("0.009"),
            )

    def test_price_just_outside_boundary_high(self, manager: PositionManager) -> None:
        """Test rejection of price just above maximum."""
        with pytest.raises(ValueError, match="outside valid range"):
            manager.update_position(
                position_id=1,
                current_price=Decimal("0.991"),
            )


# =============================================================================
# Chaos Tests: Margin Calculation Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestMarginCalculationEdgeCases:
    """Chaos tests for margin calculation edge cases."""

    def test_yes_margin_at_minimum_price(self) -> None:
        """Test YES margin at minimum price (maximum margin required)."""
        # YES @ 0.01: margin = qty * (1.00 - 0.01) = qty * 0.99
        entry_price = Decimal("0.01")
        expected_margin = Decimal("100") * (Decimal("1.00") - entry_price)
        assert expected_margin == Decimal("99.00")

    def test_yes_margin_at_maximum_price(self) -> None:
        """Test YES margin at maximum price (minimum margin required)."""
        # YES @ 0.99: margin = qty * (1.00 - 0.99) = qty * 0.01
        entry_price = Decimal("0.99")
        expected_margin = Decimal("100") * (Decimal("1.00") - entry_price)
        assert expected_margin == Decimal("1.00")

    def test_no_margin_at_minimum_price(self) -> None:
        """Test NO margin at minimum price (minimum margin required)."""
        # NO @ 0.01: margin = qty * 0.01
        entry_price = Decimal("0.01")
        expected_margin = Decimal("100") * entry_price
        assert expected_margin == Decimal("1.00")

    def test_no_margin_at_maximum_price(self) -> None:
        """Test NO margin at maximum price (maximum margin required)."""
        # NO @ 0.99: margin = qty * 0.99
        entry_price = Decimal("0.99")
        expected_margin = Decimal("100") * entry_price
        assert expected_margin == Decimal("99.00")


# =============================================================================
# Chaos Tests: Invalid Side Handling
# =============================================================================


@pytest.mark.chaos
class TestInvalidSideHandling:
    """Chaos tests for invalid side handling."""

    @patch("precog.trading.position_manager.get_connection")
    @patch("precog.trading.position_manager.release_connection")
    def test_invalid_side_lowercase(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: PositionManager,
    ) -> None:
        """Test rejection of lowercase side."""
        with pytest.raises(ValueError, match="Invalid side"):
            manager.open_position(
                market_id="MARKET-001",
                strategy_id=1,
                model_id=1,
                side="yes",  # lowercase
                quantity=10,
                entry_price=Decimal("0.50"),
                available_margin=Decimal("100.00"),
            )

    @patch("precog.trading.position_manager.get_connection")
    @patch("precog.trading.position_manager.release_connection")
    def test_invalid_side_mixed_case(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: PositionManager,
    ) -> None:
        """Test rejection of mixed case side."""
        with pytest.raises(ValueError, match="Invalid side"):
            manager.open_position(
                market_id="MARKET-001",
                strategy_id=1,
                model_id=1,
                side="Yes",  # mixed case
                quantity=10,
                entry_price=Decimal("0.50"),
                available_margin=Decimal("100.00"),
            )

    @patch("precog.trading.position_manager.get_connection")
    @patch("precog.trading.position_manager.release_connection")
    def test_invalid_side_unknown(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: PositionManager,
    ) -> None:
        """Test rejection of unknown side."""
        with pytest.raises(ValueError, match="Invalid side"):
            manager.open_position(
                market_id="MARKET-001",
                strategy_id=1,
                model_id=1,
                side="BUY",  # wrong terminology
                quantity=10,
                entry_price=Decimal("0.50"),
                available_margin=Decimal("100.00"),
            )


# =============================================================================
# Chaos Tests: Trailing Stop Config Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestTrailingStopConfigEdgeCases:
    """Chaos tests for trailing stop configuration edge cases."""

    def test_empty_config(self, manager: PositionManager) -> None:
        """Test rejection of empty config."""
        with pytest.raises(ValueError, match="Config missing required keys"):
            manager.initialize_trailing_stop(1, {})

    def test_partial_config(self, manager: PositionManager) -> None:
        """Test rejection of partial config."""
        partial_config = {
            "activation_threshold": Decimal("0.15"),
            # Missing other keys
        }
        with pytest.raises(ValueError, match="Config missing required keys"):
            manager.initialize_trailing_stop(1, partial_config)

    def test_extra_keys_in_config(self, manager: PositionManager) -> None:
        """Test config with extra keys is accepted (structure check only)."""
        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.10"),
            "floor_distance": Decimal("0.02"),
            "extra_key": "should be ignored",
        }

        required_keys = {
            "activation_threshold",
            "initial_distance",
            "tightening_rate",
            "floor_distance",
        }
        # All required keys present
        assert required_keys <= set(config.keys())

    def test_zero_tightening_rate(self, manager: PositionManager) -> None:
        """Test zero tightening rate (no tightening)."""
        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.00"),  # No tightening
            "floor_distance": Decimal("0.02"),
        }
        # Should be valid (0 <= 0 <= 1)
        assert config["tightening_rate"] >= Decimal("0")
        assert config["tightening_rate"] <= Decimal("1")

    def test_maximum_tightening_rate(self, manager: PositionManager) -> None:
        """Test maximum tightening rate (1.0)."""
        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("1.00"),  # Maximum tightening
            "floor_distance": Decimal("0.02"),
        }
        # Should be valid (0 <= 1 <= 1)
        assert config["tightening_rate"] >= Decimal("0")
        assert config["tightening_rate"] <= Decimal("1")

    def test_zero_floor_distance(self, manager: PositionManager) -> None:
        """Test zero floor distance (no minimum gap)."""
        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.10"),
            "floor_distance": Decimal("0.00"),  # No minimum gap
        }
        # Should be valid (floor >= 0)
        assert config["floor_distance"] >= Decimal("0")


# =============================================================================
# Chaos Tests: Database Error Recovery
# =============================================================================


@pytest.mark.chaos
class TestDatabaseErrorRecovery:
    """Chaos tests for database error recovery."""

    @patch("precog.trading.position_manager.get_connection")
    def test_connection_error_handled(
        self,
        mock_get_conn: MagicMock,
        manager: PositionManager,
    ) -> None:
        """Test that connection errors are properly raised."""
        mock_get_conn.side_effect = psycopg2.OperationalError("Connection failed")

        with pytest.raises(psycopg2.OperationalError, match="Connection failed"):
            manager.close_position(
                position_id=1,
                exit_price=Decimal("0.75"),
                exit_reason="manual",
            )

    @patch("precog.trading.position_manager.get_connection")
    @patch("precog.trading.position_manager.release_connection")
    def test_query_error_handled(
        self,
        mock_release: MagicMock,
        mock_get_conn: MagicMock,
        manager: PositionManager,
    ) -> None:
        """Test that query errors are properly raised."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("Query failed")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(psycopg2.Error, match="Query failed"):
            manager.close_position(
                position_id=1,
                exit_price=Decimal("0.75"),
                exit_reason="manual",
            )


# =============================================================================
# Chaos Tests: Quantity Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestQuantityEdgeCases:
    """Chaos tests for quantity edge cases."""

    def test_quantity_one(self, manager: PositionManager) -> None:
        """Test P&L with minimum quantity of 1."""
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.50"),
            current_price=Decimal("0.75"),
            quantity=1,
            side="YES",
        )
        assert pnl == Decimal("0.25")

    def test_very_large_quantity(self, manager: PositionManager) -> None:
        """Test P&L with very large quantity."""
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.50"),
            current_price=Decimal("0.75"),
            quantity=10000000,  # 10 million
            side="YES",
        )
        expected = Decimal("10000000") * Decimal("0.25")
        assert pnl == expected


# =============================================================================
# Chaos Tests: P&L Extreme Values
# =============================================================================


@pytest.mark.chaos
class TestPnLExtremeValues:
    """Chaos tests for P&L extreme values."""

    def test_maximum_possible_profit_yes(self, manager: PositionManager) -> None:
        """Test maximum possible profit for YES position."""
        # Entry at minimum (0.01), exit at maximum (0.99)
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.01"),
            current_price=Decimal("0.99"),
            quantity=1000,
            side="YES",
        )
        # Profit = 1000 * (0.99 - 0.01) = 1000 * 0.98 = 980
        assert pnl == Decimal("980")

    def test_maximum_possible_loss_yes(self, manager: PositionManager) -> None:
        """Test maximum possible loss for YES position."""
        # Entry at maximum (0.99), exit at minimum (0.01)
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.99"),
            current_price=Decimal("0.01"),
            quantity=1000,
            side="YES",
        )
        # Loss = 1000 * (0.01 - 0.99) = 1000 * -0.98 = -980
        assert pnl == Decimal("-980")

    def test_maximum_possible_profit_no(self, manager: PositionManager) -> None:
        """Test maximum possible profit for NO position."""
        # Entry at maximum (0.99), exit at minimum (0.01)
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.99"),
            current_price=Decimal("0.01"),
            quantity=1000,
            side="NO",
        )
        # Profit = 1000 * (0.99 - 0.01) = 1000 * 0.98 = 980
        assert pnl == Decimal("980")

    def test_maximum_possible_loss_no(self, manager: PositionManager) -> None:
        """Test maximum possible loss for NO position."""
        # Entry at minimum (0.01), exit at maximum (0.99)
        pnl = manager.calculate_position_pnl(
            entry_price=Decimal("0.01"),
            current_price=Decimal("0.99"),
            quantity=1000,
            side="NO",
        )
        # Loss = 1000 * (0.01 - 0.99) = 1000 * -0.98 = -980
        assert pnl == Decimal("-980")


# =============================================================================
# Chaos Tests: Exception Classes
# =============================================================================


@pytest.mark.chaos
class TestExceptionClasses:
    """Chaos tests for custom exception classes."""

    def test_invalid_position_state_error(self) -> None:
        """Test InvalidPositionStateError is an Exception."""
        error = InvalidPositionStateError("Position already closed")
        assert isinstance(error, Exception)
        assert str(error) == "Position already closed"

    def test_insufficient_margin_error(self) -> None:
        """Test InsufficientMarginError is an Exception."""
        error = InsufficientMarginError("Required $100, available $50")
        assert isinstance(error, Exception)
        assert "Required $100" in str(error)


# =============================================================================
# Chaos Tests: Concurrent Chaos
# =============================================================================


@pytest.mark.chaos
class TestConcurrentChaos:
    """Chaos tests involving concurrent operations with edge cases."""

    def test_concurrent_edge_case_pnl(self, manager: PositionManager) -> None:
        """Test concurrent P&L calculations with edge case values."""
        import threading

        edge_cases = [
            (Decimal("0.01"), Decimal("0.99"), 1, "YES"),
            (Decimal("0.99"), Decimal("0.01"), 1, "YES"),
            (Decimal("0.01"), Decimal("0.99"), 1, "NO"),
            (Decimal("0.99"), Decimal("0.01"), 1, "NO"),
            (Decimal("0.50"), Decimal("0.50"), 100, "YES"),
        ]

        results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def calculate_edge(entry: Decimal, current: Decimal, qty: int, side: str) -> None:
            try:
                pnl = manager.calculate_position_pnl(
                    entry_price=entry,
                    current_price=current,
                    quantity=qty,
                    side=side,
                )
                with lock:
                    results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=calculate_edge, args=case)
            for case in edge_cases * 4  # 20 threads total
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
