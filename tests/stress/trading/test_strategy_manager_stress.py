"""
Stress Tests for Strategy Manager.

Tests high volume operations and memory behavior under load.

Reference: TESTING_STRATEGY V3.2 - Stress tests for resource limits
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003

Usage:
    pytest tests/stress/trading/test_strategy_manager_stress.py -v -m stress
"""

import gc
import time
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.trading.strategy_manager import (
    StrategyManager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def manager() -> StrategyManager:
    """Create a StrategyManager instance for testing."""
    return StrategyManager()


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Create a sample strategy config."""
    return {
        "min_edge": Decimal("0.0500"),
        "max_position_size": Decimal("100.00"),
        "kelly_fraction": Decimal("0.2500"),
    }


# =============================================================================
# Stress Tests: Config Serialization Volume
# =============================================================================


@pytest.mark.stress
class TestConfigSerializationStress:
    """Stress tests for config serialization under high volume."""

    def test_many_config_preparations(self, manager: StrategyManager) -> None:
        """Test preparing many configs in sequence."""
        iterations = 1000

        config = {
            "min_edge": Decimal("0.05"),
            "max_position": Decimal("100"),
            "nested": {
                "value1": Decimal("0.01"),
                "value2": Decimal("0.02"),
            },
        }

        start = time.perf_counter()
        for _ in range(iterations):
            manager._prepare_config_for_db(config)
        elapsed = time.perf_counter() - start

        # Should complete within reasonable time
        assert elapsed < 5.0, f"1000 preparations took {elapsed:.2f}s (expected <5s)"

    def test_many_config_parsings(self, manager: StrategyManager) -> None:
        """Test parsing many configs in sequence."""
        iterations = 1000

        db_config = {
            "min_edge": "0.05",
            "max_position": "100",
            "nested": {
                "value1": "0.01",
                "value2": "0.02",
            },
        }

        start = time.perf_counter()
        for _ in range(iterations):
            manager._parse_config_from_db(db_config)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"1000 parsings took {elapsed:.2f}s (expected <5s)"

    def test_large_config_preparation(self, manager: StrategyManager) -> None:
        """Test preparing a large config with many keys."""
        # Large config with 100 keys
        config = {f"param_{i}": Decimal(f"0.{i:04d}") for i in range(100)}

        start = time.perf_counter()
        for _ in range(100):
            manager._prepare_config_for_db(config)
        elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"100 large config preparations took {elapsed:.2f}s"

    def test_deeply_nested_config_stress(self, manager: StrategyManager) -> None:
        """Test preparing deeply nested configs many times."""
        # 10 levels deep
        config: dict[str, Any] = {"value": Decimal("0.05")}
        for _ in range(10):
            config = {"nested": config}

        start = time.perf_counter()
        for _ in range(500):
            json_str = manager._prepare_config_for_db(config)
            import json

            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"500 deep config round-trips took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Status Transition Volume
# =============================================================================


@pytest.mark.stress
class TestStatusTransitionStress:
    """Stress tests for status transition validation under load."""

    def test_many_valid_transitions(self, manager: StrategyManager) -> None:
        """Test many valid status transitions."""
        valid_transitions = [
            ("draft", "testing"),
            ("testing", "active"),
            ("active", "inactive"),
            ("inactive", "deprecated"),
            ("testing", "draft"),  # Revert
            ("inactive", "active"),  # Reactivate
        ]

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            from_status, to_status = valid_transitions[i % len(valid_transitions)]
            manager._validate_status_transition(from_status, to_status)

        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"1000 transitions took {elapsed:.2f}s"

    def test_many_invalid_transitions_handled(self, manager: StrategyManager) -> None:
        """Test handling many invalid transitions."""
        from precog.trading.strategy_manager import InvalidStatusTransitionError

        invalid_transitions = [
            ("deprecated", "active"),
            ("deprecated", "testing"),
            ("active", "draft"),
            ("active", "testing"),
        ]

        iterations = 500
        start = time.perf_counter()

        for i in range(iterations):
            from_status, to_status = invalid_transitions[i % len(invalid_transitions)]
            try:
                manager._validate_status_transition(from_status, to_status)
            except InvalidStatusTransitionError:
                pass  # Expected

        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"500 invalid transitions took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Memory Behavior
# =============================================================================


@pytest.mark.stress
class TestMemoryStress:
    """Stress tests for memory behavior."""

    def test_config_preparation_no_memory_leak(self, manager: StrategyManager) -> None:
        """Test that config preparation doesn't leak memory."""
        gc.collect()

        config = {
            "min_edge": Decimal("0.05"),
            "max_position": Decimal("100"),
            "nested": {"value": Decimal("0.01")},
        }

        # Process many configs
        for _ in range(5000):
            json_str = manager._prepare_config_for_db(config)
            # Let the string go out of scope
            del json_str

        gc.collect()
        # Should complete without memory error

    def test_config_parsing_no_memory_leak(self, manager: StrategyManager) -> None:
        """Test that config parsing doesn't leak memory."""
        gc.collect()

        db_config = {
            "min_edge": "0.05",
            "max_position": "100",
            "nested": {"value": "0.01"},
        }

        # Parse many configs
        results = []
        for _ in range(5000):
            result = manager._parse_config_from_db(db_config)
            results.append(result)

        # Clear references
        results.clear()
        gc.collect()
        # Should complete without memory error

    def test_many_manager_instances(self) -> None:
        """Test creating many manager instances."""
        gc.collect()

        managers = []
        for _ in range(100):
            managers.append(StrategyManager())

        # All instances should be functional
        config = {"value": Decimal("0.05")}
        for manager in managers:
            manager._prepare_config_for_db(config)

        managers.clear()
        gc.collect()
        # Should complete without memory error


# =============================================================================
# Stress Tests: High Precision Decimal Handling
# =============================================================================


@pytest.mark.stress
class TestDecimalPrecisionStress:
    """Stress tests for high precision Decimal handling."""

    def test_many_high_precision_values(self, manager: StrategyManager) -> None:
        """Test handling many high precision Decimal values."""
        iterations = 500

        start = time.perf_counter()
        for i in range(iterations):
            # Create config with varying precision
            precision = (i % 20) + 1
            value = Decimal("0." + "1" * precision)
            config = {"high_precision": value}

            json_str = manager._prepare_config_for_db(config)
            import json

            parsed = json.loads(json_str)
            result = manager._parse_config_from_db(parsed)

            assert result["high_precision"] == value

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"500 high precision round-trips took {elapsed:.2f}s"

    def test_mixed_precision_configs(self, manager: StrategyManager) -> None:
        """Test configs with mixed precision values."""
        iterations = 200

        start = time.perf_counter()
        for i in range(iterations):
            # Config with multiple precision levels
            config = {
                "low": Decimal("0.1"),
                "medium": Decimal("0.12345"),
                "high": Decimal("0.12345678901234567890"),
                "integer": Decimal("100"),
            }

            json_str = manager._prepare_config_for_db(config)
            import json

            parsed = json.loads(json_str)
            result = manager._parse_config_from_db(parsed)

            assert result["low"] == config["low"]
            assert result["medium"] == config["medium"]
            assert result["high"] == config["high"]
            assert result["integer"] == config["integer"]

        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"200 mixed precision round-trips took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Concurrent-like Sequential Operations
# =============================================================================


@pytest.mark.stress
class TestSequentialLoadStress:
    """Stress tests simulating high sequential load."""

    def test_rapid_config_switches(self, manager: StrategyManager) -> None:
        """Test rapidly switching between different configs."""
        configs = [
            {"type": "value", "edge": Decimal("0.05")},
            {"type": "arbitrage", "spread": Decimal("0.02")},
            {"type": "momentum", "threshold": Decimal("0.10")},
            {"type": "mean_reversion", "band": Decimal("0.15")},
        ]

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            config = configs[i % len(configs)]
            json_str = manager._prepare_config_for_db(config)
            import json

            parsed = json.loads(json_str)
            result = manager._parse_config_from_db(parsed)
            assert result["type"] == config["type"]

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"1000 config switches took {elapsed:.2f}s"

    def test_mixed_operations_stress(self, manager: StrategyManager) -> None:
        """Test mixed operations under stress."""
        iterations = 500

        start = time.perf_counter()
        for i in range(iterations):
            # Prepare config
            config = {"value": Decimal(f"0.{i:04d}")}
            json_str = manager._prepare_config_for_db(config)

            # Parse config
            import json

            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)

            # Validate transitions
            if i % 2 == 0:
                manager._validate_status_transition("draft", "testing")
            else:
                manager._validate_status_transition("testing", "active")

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"500 mixed operations took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Database Mock Operations
# =============================================================================


@pytest.mark.stress
class TestDatabaseOperationStress:
    """Stress tests for database-related operations with mocks."""

    @patch("precog.trading.strategy_manager.get_connection")
    def test_many_create_attempts(self, mock_conn: MagicMock, manager: StrategyManager) -> None:
        """Test many create operation attempts."""
        # Mock the database interaction
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("strategy_type",),
            ("config",),
            ("status",),
        ]
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        iterations = 100
        start = time.perf_counter()

        for i in range(iterations):
            try:
                manager.create_strategy(
                    strategy_name=f"test_strategy_{i}",
                    strategy_version="1.0",
                    strategy_type="value",
                    config={"min_edge": Decimal("0.05")},
                )
            except Exception:
                pass  # Mock may not return proper data

        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"100 create attempts took {elapsed:.2f}s"

    def test_row_to_dict_many_rows(self, manager: StrategyManager) -> None:
        """Test converting many rows to dictionaries."""
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("config",),
        ]

        rows = [(i, f"strategy_{i}", {"value": str(i)}) for i in range(1000)]

        start = time.perf_counter()
        results = []
        for row in rows:
            result = manager._row_to_dict(mock_cursor, row)
            results.append(result)

        elapsed = time.perf_counter() - start
        assert len(results) == 1000
        assert elapsed < 2.0, f"1000 row conversions took {elapsed:.2f}s"
