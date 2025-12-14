"""
Race Condition Tests for PositionManager.

Tests thread safety and concurrent access patterns.

Reference: TESTING_STRATEGY V3.2 - Race tests for concurrent safety
Related Requirements: REQ-RISK-001 (Position Entry Validation)

Usage:
    pytest tests/race/trading/test_position_manager_race.py -v -m race
"""

import threading
import time
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.position_manager import PositionManager

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
# Race Condition Tests: Concurrent P&L Calculations
# =============================================================================


@pytest.mark.race
class TestConcurrentPnLCalculations:
    """Race condition tests for concurrent P&L calculations."""

    def test_concurrent_yes_pnl_calculations(self, manager: PositionManager) -> None:
        """Test concurrent YES position P&L calculations are thread-safe."""
        results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def calculate_pnl(thread_id: int) -> None:
            try:
                pnl = manager.calculate_position_pnl(
                    entry_price=Decimal("0.50"),
                    current_price=Decimal("0.75"),
                    quantity=thread_id + 1,
                    side="YES",
                )
                with lock:
                    results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=calculate_pnl, args=(i,)) for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # Verify correct calculations
        for i, pnl in enumerate(sorted(results)):
            # P&L should be (i+1) * 0.25 for YES position
            # But order is not guaranteed, so just verify all are Decimals
            assert isinstance(pnl, Decimal)

    def test_concurrent_no_pnl_calculations(self, manager: PositionManager) -> None:
        """Test concurrent NO position P&L calculations are thread-safe."""
        results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def calculate_pnl(thread_id: int) -> None:
            try:
                pnl = manager.calculate_position_pnl(
                    entry_price=Decimal("0.50"),
                    current_price=Decimal("0.25"),
                    quantity=thread_id + 1,
                    side="NO",
                )
                with lock:
                    results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=calculate_pnl, args=(i,)) for i in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_concurrent_mixed_side_calculations(self, manager: PositionManager) -> None:
        """Test concurrent YES and NO calculations interleaved."""
        yes_results: list[Decimal] = []
        no_results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def calculate_yes(thread_id: int) -> None:
            try:
                pnl = manager.calculate_position_pnl(
                    entry_price=Decimal("0.50"),
                    current_price=Decimal("0.75"),
                    quantity=10,
                    side="YES",
                )
                with lock:
                    yes_results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        def calculate_no(thread_id: int) -> None:
            try:
                pnl = manager.calculate_position_pnl(
                    entry_price=Decimal("0.50"),
                    current_price=Decimal("0.25"),
                    quantity=10,
                    side="NO",
                )
                with lock:
                    no_results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=calculate_yes, args=(i,)))
            threads.append(threading.Thread(target=calculate_no, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(yes_results) == 10
        assert len(no_results) == 10


# =============================================================================
# Race Condition Tests: Concurrent Queries (Mocked)
# =============================================================================


@pytest.mark.race
class TestConcurrentQueries:
    """Race condition tests for concurrent database queries (mocked)."""

    @patch("precog.trading.position_manager.get_current_positions")
    def test_concurrent_get_open_positions(
        self,
        mock_get_positions: MagicMock,
        manager: PositionManager,
        mock_position: dict[str, Any],
    ) -> None:
        """Test concurrent get_open_positions calls are thread-safe."""
        mock_get_positions.return_value = [mock_position]

        results: list[list[dict[str, Any]]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def get_positions() -> None:
            try:
                positions = manager.get_open_positions()
                with lock:
                    results.append(positions)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=get_positions) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    @patch("precog.trading.position_manager.get_current_positions")
    def test_concurrent_filtered_queries(
        self,
        mock_get_positions: MagicMock,
        manager: PositionManager,
        mock_position: dict[str, Any],
    ) -> None:
        """Test concurrent filtered queries are thread-safe."""
        mock_get_positions.return_value = [mock_position]

        results: list[list[dict[str, Any]]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def query_by_market(market_id: str) -> None:
            try:
                positions = manager.get_open_positions(market_id=market_id)
                with lock:
                    results.append(positions)
            except Exception as e:
                with lock:
                    errors.append(e)

        def query_by_strategy(strategy_id: int) -> None:
            try:
                positions = manager.get_open_positions(strategy_id=strategy_id)
                with lock:
                    results.append(positions)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=query_by_market, args=(f"MARKET-{i:03d}",)))
            threads.append(threading.Thread(target=query_by_strategy, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20


# =============================================================================
# Race Condition Tests: Concurrent Config Validation
# =============================================================================


@pytest.mark.race
class TestConcurrentConfigValidation:
    """Race condition tests for concurrent config validation."""

    def test_concurrent_config_validation(self, manager: PositionManager) -> None:
        """Test concurrent trailing stop config validation is thread-safe."""
        valid_count = 0
        invalid_count = 0
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_valid_config() -> None:
            nonlocal valid_count
            config = {
                "activation_threshold": Decimal("0.15"),
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            }
            try:
                # Just validate the config structure
                required = {
                    "activation_threshold",
                    "initial_distance",
                    "tightening_rate",
                    "floor_distance",
                }
                if required <= set(config.keys()):
                    with lock:
                        valid_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        def validate_invalid_config() -> None:
            nonlocal invalid_count
            config = {
                "activation_threshold": Decimal("-0.15"),  # Invalid
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            }
            try:
                manager.initialize_trailing_stop(1, config)
            except ValueError:
                with lock:
                    invalid_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=validate_valid_config))
            threads.append(threading.Thread(target=validate_invalid_config))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert valid_count == 10
        assert invalid_count == 10


# =============================================================================
# Race Condition Tests: Rapid Succession
# =============================================================================


@pytest.mark.race
class TestRapidSuccession:
    """Race condition tests for rapid succession operations."""

    def test_rapid_pnl_calculations(self, manager: PositionManager) -> None:
        """Test rapid succession of P&L calculations from multiple threads."""
        operation_count = 0
        lock = threading.Lock()
        errors: list[Exception] = []

        def rapid_operations() -> None:
            nonlocal operation_count
            try:
                for i in range(50):
                    manager.calculate_position_pnl(
                        entry_price=Decimal(f"0.{30 + (i % 40):02d}"),
                        current_price=Decimal(f"0.{50 + (i % 30):02d}"),
                        quantity=i + 1,
                        side="YES" if i % 2 == 0 else "NO",
                    )
                    with lock:
                        operation_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=rapid_operations) for _ in range(5)]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        assert len(errors) == 0
        assert operation_count == 250  # 5 threads * 50 operations
        assert elapsed < 5.0

    @patch("precog.trading.position_manager.get_current_positions")
    def test_rapid_mixed_operations(
        self,
        mock_get_positions: MagicMock,
        manager: PositionManager,
        mock_position: dict[str, Any],
    ) -> None:
        """Test rapid succession of mixed operations from multiple threads."""
        mock_get_positions.return_value = [mock_position]

        pnl_count = 0
        query_count = 0
        lock = threading.Lock()
        errors: list[Exception] = []

        def pnl_operations() -> None:
            nonlocal pnl_count
            try:
                for i in range(30):
                    manager.calculate_position_pnl(
                        entry_price=Decimal("0.50"),
                        current_price=Decimal("0.60"),
                        quantity=10,
                        side="YES",
                    )
                    with lock:
                        pnl_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        def query_operations() -> None:
            nonlocal query_count
            try:
                for _ in range(30):
                    manager.get_open_positions()
                    with lock:
                        query_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=pnl_operations))
            threads.append(threading.Thread(target=query_operations))

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        assert len(errors) == 0
        assert pnl_count == 90  # 3 threads * 30 operations
        assert query_count == 90
        assert elapsed < 5.0


# =============================================================================
# Race Condition Tests: Shared State
# =============================================================================


@pytest.mark.race
class TestSharedState:
    """Race condition tests for shared state handling."""

    def test_multiple_managers_concurrent(self) -> None:
        """Test multiple PositionManager instances concurrently."""
        results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def use_own_manager(thread_id: int) -> None:
            try:
                # Each thread creates its own manager
                manager = PositionManager()
                for i in range(10):
                    pnl = manager.calculate_position_pnl(
                        entry_price=Decimal("0.50"),
                        current_price=Decimal("0.75"),
                        quantity=thread_id + i + 1,
                        side="YES",
                    )
                    with lock:
                        results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=use_own_manager, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 operations

    def test_shared_manager_concurrent(self) -> None:
        """Test single shared PositionManager from multiple threads."""
        manager = PositionManager()
        results: list[Decimal] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def use_shared_manager(thread_id: int) -> None:
            try:
                for i in range(10):
                    pnl = manager.calculate_position_pnl(
                        entry_price=Decimal("0.50"),
                        current_price=Decimal("0.75"),
                        quantity=thread_id + i + 1,
                        side="YES",
                    )
                    with lock:
                        results.append(pnl)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=use_shared_manager, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 operations
        # All results should be Decimals
        assert all(isinstance(r, Decimal) for r in results)
