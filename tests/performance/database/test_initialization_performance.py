"""
Performance tests for database initialization module.

Validates latency and throughput requirements.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.initialization import (
    apply_schema,
    get_database_url,
    validate_schema_file,
)

pytestmark = [pytest.mark.performance]


class TestValidateSchemaFilePerformance:
    """Performance benchmarks for schema validation."""

    def test_validation_latency(self, tmp_path: Path) -> None:
        """Test that schema validation is fast (<1ms)."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            validate_schema_file(str(schema))
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Should be very fast - just file existence check
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"
        assert max_latency < 0.01, f"Max latency {max_latency * 1000:.3f}ms too high"

    def test_nonexistent_file_latency(self) -> None:
        """Test that nonexistent file check is fast."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            validate_schema_file("nonexistent_file_xyz.sql")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_validation_throughput(self, tmp_path: Path) -> None:
        """Test validation throughput."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            validate_schema_file(str(schema))
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 10k ops/sec
        assert throughput > 10000, f"Throughput {throughput:.0f} ops/sec too low"


class TestApplySchemaPerformance:
    """Performance benchmarks for schema application."""

    @patch("precog.database.initialization.subprocess.run")
    def test_apply_schema_validation_latency(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test that pre-validation is fast."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            apply_schema("postgresql://localhost/test", str(schema))
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Most time is spent in subprocess, so allow more time
        assert avg_latency < 0.01, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_invalid_url_rejection_latency(self, tmp_path: Path) -> None:
        """Test that invalid URL rejection is fast."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            apply_schema("invalid-url", str(schema))
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should fail fast on invalid URL
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_nonexistent_file_rejection_latency(self) -> None:
        """Test that nonexistent file rejection is fast."""
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            apply_schema("postgresql://localhost/test", "nonexistent.sql")
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should fail fast on missing file
        assert avg_latency < 0.001, f"Average latency {avg_latency * 1000:.3f}ms too high"


class TestGetDatabaseUrlPerformance:
    """Performance benchmarks for URL retrieval."""

    def test_get_url_latency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that URL retrieval is fast."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        latencies = []
        for _ in range(10000):
            start = time.perf_counter()
            get_database_url()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should be very fast - just env lookup
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_get_url_throughput(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test URL retrieval throughput."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        start = time.perf_counter()
        count = 0
        for _ in range(100000):
            get_database_url()
            count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 100k ops/sec
        assert throughput > 100000, f"Throughput {throughput:.0f} ops/sec too low"

    def test_missing_url_latency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing URL check is fast."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        latencies = []
        for _ in range(10000):
            start = time.perf_counter()
            get_database_url()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"
