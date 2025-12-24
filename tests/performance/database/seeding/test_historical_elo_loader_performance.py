"""
Performance Tests for Historical Elo Loader.

Tests latency and throughput for Elo data operations.

Reference: TESTING_STRATEGY V3.2 - Performance tests for latency/throughput
Related Requirements: REQ-DATA-003, Issue #208

Usage:
    pytest tests/performance/database/seeding/test_historical_elo_loader_performance.py -v -m performance
"""

import statistics
import tempfile
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    LoadResult,
    bulk_insert_historical_elo,
    normalize_team_code,
    parse_fivethirtyeight_csv,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_csv_file() -> Path:
    """Create a sample CSV file for performance testing."""
    content = """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,elo_prob1,elo_prob2,elo1_post,elo2_post,qbelo1_pre,qbelo2_pre,qb1,qb2,qb1_value_pre,qb2_value_pre
2023-09-07,2023,0,,KC,DET,1624.09,1545.23,0.63,0.37,1635.59,1533.73,1711.05,1612.63,Patrick Mahomes,Jared Goff,86.96,67.40
2023-09-10,2023,0,,BUF,NYJ,1618.75,1496.89,0.70,0.30,1592.35,1523.29,1666.92,1484.34,Josh Allen,Aaron Rodgers,48.17,-12.55
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


# =============================================================================
# Performance Tests: Team Code Normalization Latency
# =============================================================================


@pytest.mark.performance
class TestNormalizationLatency:
    """Performance tests for team code normalization latency."""

    def test_simple_normalization_latency(self) -> None:
        """Test simple normalization meets latency threshold."""
        iterations = 1000
        latencies_us: list[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            normalize_team_code("KC")
            elapsed = (time.perf_counter() - start) * 1_000_000  # microseconds
            latencies_us.append(elapsed)

        avg_latency = statistics.mean(latencies_us)
        p99_latency = sorted(latencies_us)[int(iterations * 0.99)]

        # Normalization should be very fast (< 10 microseconds)
        assert avg_latency < 50, f"Avg latency {avg_latency:.3f}us exceeds 50us"
        assert p99_latency < 100, f"P99 latency {p99_latency:.3f}us exceeds 100us"

    def test_mapping_normalization_latency(self) -> None:
        """Test normalization with mapping meets latency threshold."""
        iterations = 1000
        latencies_us: list[float] = []

        # Test codes that require mapping
        codes = ["WSH", "OAK", "SD", "STL"]

        for i in range(iterations):
            code = codes[i % len(codes)]
            start = time.perf_counter()
            normalize_team_code(code)
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies_us.append(elapsed)

        avg_latency = statistics.mean(latencies_us)
        p99_latency = sorted(latencies_us)[int(iterations * 0.99)]

        assert avg_latency < 50, f"Avg latency {avg_latency:.3f}us exceeds 50us"
        assert p99_latency < 100, f"P99 latency {p99_latency:.3f}us exceeds 100us"


# =============================================================================
# Performance Tests: Record Creation Latency
# =============================================================================


@pytest.mark.performance
class TestRecordCreationLatency:
    """Performance tests for record creation latency."""

    def test_record_creation_latency(self) -> None:
        """Test HistoricalEloRecord creation meets latency threshold."""
        iterations = 1000
        latencies_us: list[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            record = HistoricalEloRecord(
                team_code="KC",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 9, 7),
                elo_rating=Decimal("1624.09"),
                qb_adjusted_elo=Decimal("1711.05"),
                qb_name="Patrick Mahomes",
                qb_value=Decimal("86.96"),
                source="test",
                source_file="test.csv",
            )
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies_us.append(elapsed)
            del record  # Prevent memory accumulation

        avg_latency = statistics.mean(latencies_us)
        p99_latency = sorted(latencies_us)[int(iterations * 0.99)]

        # Record creation should be fast
        assert avg_latency < 100, f"Avg latency {avg_latency:.3f}us exceeds 100us"
        assert p99_latency < 500, f"P99 latency {p99_latency:.3f}us exceeds 500us"


# =============================================================================
# Performance Tests: CSV Parsing Throughput
# =============================================================================


@pytest.mark.performance
class TestCSVParsingThroughput:
    """Performance tests for CSV parsing throughput."""

    def test_csv_parsing_throughput(self, sample_csv_file: Path) -> None:
        """Test CSV parsing throughput meets threshold."""
        iterations = 100
        records_per_iteration = 4  # 2 games * 2 teams

        start = time.perf_counter()
        for _ in range(iterations):
            list(parse_fivethirtyeight_csv(sample_csv_file))
        elapsed = time.perf_counter() - start

        total_records = iterations * records_per_iteration
        throughput = total_records / elapsed

        # Should process at least 100 records per second
        assert throughput > 100, f"Throughput {throughput:.1f} rec/s below 100 rec/s"


# =============================================================================
# Performance Tests: LoadResult Creation Latency
# =============================================================================


@pytest.mark.performance
class TestLoadResultLatency:
    """Performance tests for LoadResult creation latency.

    Educational Note:
        Issue #255 unified LoadResult with BatchInsertResult. These tests
        verify that the new BatchInsertResult dataclass maintains acceptable
        creation latency for high-throughput batch operations.
    """

    def test_load_result_creation_latency(self) -> None:
        """Test LoadResult creation meets latency threshold.

        Note: LoadResult is now an alias for BatchInsertResult (Issue #255).
        Uses new BatchInsertResult API parameters.
        """
        iterations = 1000
        latencies_us: list[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            result = LoadResult(
                total_records=1000,
                successful=900,
                skipped=50,
                failed=5,
            )
            # Add some failures to simulate real-world usage
            result.add_failure(0, {"index": 0}, ValueError("Error 1"))
            result.add_failure(1, {"index": 1}, ValueError("Error 2"))
            elapsed = (time.perf_counter() - start) * 1_000_000
            latencies_us.append(elapsed)
            del result

        avg_latency = statistics.mean(latencies_us)
        p99_latency = sorted(latencies_us)[int(iterations * 0.99)]

        # Slightly relaxed thresholds due to add_failure() calls
        assert avg_latency < 100, f"Avg latency {avg_latency:.3f}us exceeds 100us"
        assert p99_latency < 300, f"P99 latency {p99_latency:.3f}us exceeds 300us"


# =============================================================================
# Performance Tests: Bulk Insert Throughput
# =============================================================================


@pytest.mark.performance
class TestBulkInsertThroughput:
    """Performance tests for bulk insert throughput."""

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_throughput(self, mock_flush: MagicMock, mock_get_team: MagicMock) -> None:
        """Test bulk insert throughput meets threshold."""
        mock_get_team.return_value = 1
        mock_flush.return_value = 100

        # Generate records
        record_count = 1000
        records = [
            HistoricalEloRecord(
                team_code="KC",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 9, 7),
                elo_rating=Decimal("1624.09"),
                qb_adjusted_elo=None,
                qb_name=None,
                qb_value=None,
                source="test",
                source_file=None,
            )
            for _ in range(record_count)
        ]

        start = time.perf_counter()
        result = bulk_insert_historical_elo(iter(records), batch_size=100)
        elapsed = time.perf_counter() - start

        throughput = record_count / elapsed

        assert result.records_processed == record_count
        # Should process at least 1000 records per second
        assert throughput > 1000, f"Throughput {throughput:.1f} rec/s below 1000 rec/s"
