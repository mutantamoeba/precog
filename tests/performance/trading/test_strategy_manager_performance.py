"""
Performance Tests for Strategy Manager.

Tests latency thresholds and throughput requirements.

Reference: TESTING_STRATEGY V3.2 - Performance tests for latency/throughput
Related Requirements: REQ-VER-001, REQ-VER-002, REQ-VER-003

Usage:
    pytest tests/performance/trading/test_strategy_manager_performance.py -v -m performance
"""

import json
import time
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from precog.trading.strategy_manager import (
    InvalidStatusTransitionError,
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
def simple_config() -> dict[str, Any]:
    """Simple config for basic tests."""
    return {"min_edge": Decimal("0.05")}


@pytest.fixture
def complex_config() -> dict[str, Any]:
    """Complex config with nested structures."""
    return {
        "entry_rules": {
            "min_edge": Decimal("0.05"),
            "max_spread": Decimal("0.10"),
            "filters": [Decimal("0.30"), Decimal("0.70")],
        },
        "exit_rules": {
            "trailing_stop": Decimal("0.02"),
            "take_profit": Decimal("0.15"),
        },
        "risk_params": {
            "kelly_fraction": Decimal("0.25"),
            "max_position": Decimal("100.00"),
        },
    }


# =============================================================================
# Performance Tests: Config Preparation Latency
# =============================================================================


@pytest.mark.performance
class TestConfigPreparationLatency:
    """Performance tests for config preparation latency."""

    def test_simple_config_preparation_latency(
        self, manager: StrategyManager, simple_config: dict[str, Any]
    ) -> None:
        """Test simple config preparation meets latency threshold."""
        # Warm up
        for _ in range(10):
            manager._prepare_config_for_db(simple_config)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            manager._prepare_config_for_db(simple_config)
            latency = (time.perf_counter() - start) * 1000  # ms
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]
        p99_latency = sorted(latencies)[98]

        # Simple config should be very fast
        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"
        assert p95_latency < 1.0, f"P95 latency {p95_latency:.3f}ms exceeds 1.0ms"
        assert p99_latency < 2.0, f"P99 latency {p99_latency:.3f}ms exceeds 2.0ms"

    def test_complex_config_preparation_latency(
        self, manager: StrategyManager, complex_config: dict[str, Any]
    ) -> None:
        """Test complex config preparation meets latency threshold."""
        # Warm up
        for _ in range(10):
            manager._prepare_config_for_db(complex_config)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            manager._prepare_config_for_db(complex_config)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]

        # Complex config should still be fast
        assert avg_latency < 1.0, f"Average latency {avg_latency:.3f}ms exceeds 1.0ms"
        assert p95_latency < 2.0, f"P95 latency {p95_latency:.3f}ms exceeds 2.0ms"

    def test_large_config_preparation_latency(self, manager: StrategyManager) -> None:
        """Test large config preparation latency."""
        # Config with 50 keys
        large_config = {f"param_{i}": Decimal(f"0.{i:04d}") for i in range(50)}

        # Warm up
        for _ in range(5):
            manager._prepare_config_for_db(large_config)

        # Measure
        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            manager._prepare_config_for_db(large_config)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Large config should still be reasonable
        assert avg_latency < 5.0, f"Average latency {avg_latency:.3f}ms exceeds 5.0ms"


# =============================================================================
# Performance Tests: Config Parsing Latency
# =============================================================================


@pytest.mark.performance
class TestConfigParsingLatency:
    """Performance tests for config parsing latency."""

    def test_simple_config_parsing_latency(self, manager: StrategyManager) -> None:
        """Test simple config parsing meets latency threshold."""
        db_config = {"min_edge": "0.05"}

        # Warm up
        for _ in range(10):
            manager._parse_config_from_db(db_config)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            manager._parse_config_from_db(db_config)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]

        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"
        assert p95_latency < 1.0, f"P95 latency {p95_latency:.3f}ms exceeds 1.0ms"

    def test_complex_config_parsing_latency(self, manager: StrategyManager) -> None:
        """Test complex config parsing meets latency threshold."""
        db_config = {
            "entry_rules": {
                "min_edge": "0.05",
                "max_spread": "0.10",
            },
            "exit_rules": {
                "trailing_stop": "0.02",
                "take_profit": "0.15",
            },
        }

        # Warm up
        for _ in range(10):
            manager._parse_config_from_db(db_config)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            manager._parse_config_from_db(db_config)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency < 1.0, f"Average latency {avg_latency:.3f}ms exceeds 1.0ms"


# =============================================================================
# Performance Tests: Status Validation Latency
# =============================================================================


@pytest.mark.performance
class TestStatusValidationLatency:
    """Performance tests for status transition validation latency."""

    def test_valid_transition_latency(self, manager: StrategyManager) -> None:
        """Test valid status transition validation latency."""
        # Warm up
        for _ in range(10):
            manager._validate_status_transition("draft", "testing")

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            manager._validate_status_transition("draft", "testing")
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Status validation should be very fast
        assert avg_latency < 0.1, f"Average latency {avg_latency:.3f}ms exceeds 0.1ms"

    def test_invalid_transition_latency(self, manager: StrategyManager) -> None:
        """Test invalid status transition exception latency."""
        # Warm up
        for _ in range(10):
            try:
                manager._validate_status_transition("deprecated", "active")
            except InvalidStatusTransitionError:
                pass

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            try:
                manager._validate_status_transition("deprecated", "active")
            except InvalidStatusTransitionError:
                pass
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Exception handling should still be fast
        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"


# =============================================================================
# Performance Tests: Throughput
# =============================================================================


@pytest.mark.performance
class TestThroughput:
    """Performance tests for operation throughput."""

    def test_config_preparation_throughput(
        self, manager: StrategyManager, simple_config: dict[str, Any]
    ) -> None:
        """Test config preparation throughput."""
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            manager._prepare_config_for_db(simple_config)
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        # Should handle at least 5000 preparations per second
        assert throughput > 5000, f"Throughput {throughput:.0f}/s below 5000/s"

    def test_config_parsing_throughput(self, manager: StrategyManager) -> None:
        """Test config parsing throughput."""
        db_config = {"min_edge": "0.05", "max_position": "100"}
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            manager._parse_config_from_db(db_config)
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        assert throughput > 5000, f"Throughput {throughput:.0f}/s below 5000/s"

    def test_status_validation_throughput(self, manager: StrategyManager) -> None:
        """Test status validation throughput."""
        iterations = 5000

        start = time.perf_counter()
        for _ in range(iterations):
            manager._validate_status_transition("draft", "testing")
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        # Status validation should be very fast
        assert throughput > 50000, f"Throughput {throughput:.0f}/s below 50000/s"

    def test_round_trip_throughput(
        self, manager: StrategyManager, simple_config: dict[str, Any]
    ) -> None:
        """Test full prepare -> parse round trip throughput."""
        iterations = 500

        start = time.perf_counter()
        for _ in range(iterations):
            json_str = manager._prepare_config_for_db(simple_config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        # Round trip should be reasonably fast
        assert throughput > 2000, f"Throughput {throughput:.0f}/s below 2000/s"


# =============================================================================
# Performance Tests: Row Conversion
# =============================================================================


@pytest.mark.performance
class TestRowConversionPerformance:
    """Performance tests for row to dict conversion."""

    def test_row_conversion_latency(self, manager: StrategyManager) -> None:
        """Test row to dict conversion latency."""
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("strategy_version",),
            ("config",),
        ]
        row = (1, "test_strategy", "1.0", {"min_edge": "0.05"})

        # Warm up
        for _ in range(10):
            manager._row_to_dict(mock_cursor, row)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            manager._row_to_dict(mock_cursor, row)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"

    def test_row_conversion_throughput(self, manager: StrategyManager) -> None:
        """Test row to dict conversion throughput."""
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("strategy_id",),
            ("strategy_name",),
            ("config",),
        ]
        row = (1, "test_strategy", {"min_edge": "0.05"})
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            manager._row_to_dict(mock_cursor, row)
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        assert throughput > 10000, f"Throughput {throughput:.0f}/s below 10000/s"


# =============================================================================
# Performance Tests: Mixed Operations
# =============================================================================


@pytest.mark.performance
class TestMixedOperationsPerformance:
    """Performance tests for mixed operation patterns."""

    def test_typical_workflow_latency(
        self, manager: StrategyManager, complex_config: dict[str, Any]
    ) -> None:
        """Test typical workflow (prepare, validate, parse) latency."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("strategy_id",), ("config",)]
        row = (1, {"min_edge": "0.05"})

        # Warm up
        for _ in range(5):
            manager._prepare_config_for_db(complex_config)
            manager._validate_status_transition("draft", "testing")
            manager._row_to_dict(mock_cursor, row)

        # Measure full workflow
        latencies = []
        for _ in range(50):
            start = time.perf_counter()

            # Typical workflow steps
            json_str = manager._prepare_config_for_db(complex_config)
            manager._validate_status_transition("draft", "testing")
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
            manager._row_to_dict(mock_cursor, row)

            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Full workflow should be under 5ms
        assert avg_latency < 5.0, f"Average workflow latency {avg_latency:.3f}ms exceeds 5.0ms"

    def test_batch_processing_performance(self, manager: StrategyManager) -> None:
        """Test batch processing of multiple strategies."""
        configs = [
            {
                "name": f"strategy_{i}",
                "min_edge": Decimal(f"0.0{i % 10}"),
                "max_position": Decimal(f"{(i + 1) * 10}"),
            }
            for i in range(100)
        ]

        start = time.perf_counter()

        for config in configs:
            # Simulate batch processing workflow
            json_str = manager._prepare_config_for_db(config)
            manager._validate_status_transition("draft", "testing")
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)

        elapsed = time.perf_counter() - start

        # 100 strategies should process quickly
        per_strategy = elapsed / 100 * 1000  # ms per strategy

        assert per_strategy < 2.0, f"Per-strategy time {per_strategy:.3f}ms exceeds 2.0ms"
        assert elapsed < 1.0, f"Total batch time {elapsed:.3f}s exceeds 1.0s"


# =============================================================================
# Performance Tests: Decimal Handling
# =============================================================================


@pytest.mark.performance
class TestDecimalHandlingPerformance:
    """Performance tests for Decimal handling."""

    def test_high_precision_decimal_latency(self, manager: StrategyManager) -> None:
        """Test high precision Decimal handling latency."""
        config = {
            "high_precision": Decimal("0.12345678901234567890"),
            "normal": Decimal("0.05"),
        }

        # Warm up
        for _ in range(10):
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # High precision shouldn't significantly impact performance
        assert avg_latency < 1.0, f"Average latency {avg_latency:.3f}ms exceeds 1.0ms"

    def test_many_decimal_fields_performance(self, manager: StrategyManager) -> None:
        """Test performance with many Decimal fields."""
        # Config with 20 Decimal fields
        config = {f"decimal_{i}": Decimal(f"0.{i:04d}") for i in range(20)}

        # Warm up
        for _ in range(5):
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)

        # Measure
        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            json_str = manager._prepare_config_for_db(config)
            parsed = json.loads(json_str)
            manager._parse_config_from_db(parsed)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency < 2.0, f"Average latency {avg_latency:.3f}ms exceeds 2.0ms"
