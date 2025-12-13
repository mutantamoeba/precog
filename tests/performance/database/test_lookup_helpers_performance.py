"""
Performance tests for lookup_helpers module.

Validates latency and throughput requirements.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from precog.database.lookup_helpers import (
    get_model_classes,
    get_model_classes_by_complexity,
    get_strategy_types,
    get_strategy_types_by_category,
    get_valid_model_classes,
    get_valid_strategy_types,
    validate_model_class,
    validate_strategy_type,
)

pytestmark = [pytest.mark.performance]


class TestStrategyTypesPerformance:
    """Performance benchmarks for strategy type functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_get_strategy_types_latency(self, mock_fetch: MagicMock) -> None:
        """Test get_strategy_types latency."""
        mock_fetch.return_value = [
            {"strategy_type_code": f"type_{i}", "category": "test"} for i in range(10)
        ]

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            get_strategy_types()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should be fast when DB is mocked
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_category_grouping_latency(self, mock_fetch: MagicMock) -> None:
        """Test category grouping latency."""
        mock_fetch.return_value = [
            {"strategy_type_code": f"type_{i}", "category": f"cat_{i % 5}"} for i in range(50)
        ]

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            get_strategy_types_by_category()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_get_strategy_types_throughput(self, mock_fetch: MagicMock) -> None:
        """Test get_strategy_types throughput."""
        mock_fetch.return_value = [
            {"strategy_type_code": f"type_{i}", "category": "test"} for i in range(10)
        ]

        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            get_strategy_types()
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 10k ops/sec with mocked DB
        assert throughput > 10000, f"Throughput {throughput:.0f} ops/sec too low"


class TestModelClassesPerformance:
    """Performance benchmarks for model class functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_get_model_classes_latency(self, mock_fetch: MagicMock) -> None:
        """Test get_model_classes latency."""
        mock_fetch.return_value = [
            {"model_class_code": f"class_{i}", "category": "test", "complexity_level": "simple"}
            for i in range(10)
        ]

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            get_model_classes()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_complexity_grouping_latency(self, mock_fetch: MagicMock) -> None:
        """Test complexity grouping latency."""
        complexities = ["simple", "moderate", "advanced"]
        mock_fetch.return_value = [
            {
                "model_class_code": f"class_{i}",
                "category": "test",
                "complexity_level": complexities[i % 3],
            }
            for i in range(50)
        ]

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            get_model_classes_by_complexity()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"


class TestValidationPerformance:
    """Performance benchmarks for validation functions."""

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_strategy_type_latency(self, mock_fetch: MagicMock) -> None:
        """Test validation latency."""
        mock_fetch.return_value = {"exists": True}

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            validate_strategy_type("value")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validate_model_class_latency(self, mock_fetch: MagicMock) -> None:
        """Test validation latency."""
        mock_fetch.return_value = {"exists": True}

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            validate_model_class("elo")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0005, f"Average latency {avg_latency * 1000:.3f}ms too high"

    @patch("precog.database.lookup_helpers.fetch_one")
    def test_validation_throughput(self, mock_fetch: MagicMock) -> None:
        """Test validation throughput."""
        mock_fetch.return_value = {"exists": True}

        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            validate_strategy_type("value")
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        assert throughput > 50000, f"Throughput {throughput:.0f} ops/sec too low"


class TestGetValidCodesPerformance:
    """Performance benchmarks for get_valid_* functions."""

    @patch("precog.database.lookup_helpers.fetch_all")
    def test_get_valid_codes_latency(self, mock_fetch: MagicMock) -> None:
        """Test valid codes retrieval latency."""
        mock_fetch.return_value = [
            {"strategy_type_code": f"type_{i}", "model_class_code": f"class_{i}"} for i in range(20)
        ]

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            get_valid_strategy_types()
            get_valid_model_classes()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.002, f"Average latency {avg_latency * 1000:.3f}ms too high"
