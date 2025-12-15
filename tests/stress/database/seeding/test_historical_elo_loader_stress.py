"""
Stress Tests for Historical Elo Loader.

Tests high volume operations and resource behavior under load.

Reference: TESTING_STRATEGY V3.2 - Stress tests for resource limits
Related Requirements: REQ-DATA-003, Issue #208

Usage:
    pytest tests/stress/database/seeding/test_historical_elo_loader_stress.py -v -m stress
"""

import gc
import tempfile
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    bulk_insert_historical_elo,
    normalize_team_code,
    parse_fivethirtyeight_csv,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def large_csv_file() -> Path:
    """Create a large CSV file with many records for stress testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        # Write header
        f.write(
            "date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,elo_prob1,elo_prob2,elo1_post,elo2_post,qbelo1_pre,qbelo2_pre,qb1,qb2,qb1_value_pre,qb2_value_pre\n"
        )

        # Generate 500 game rows (1000 team records)
        teams = ["KC", "BUF", "SF", "DAL", "PHI", "MIA", "NYJ", "DET", "LAR", "SEA"]
        for i in range(500):
            team1 = teams[i % len(teams)]
            team2 = teams[(i + 1) % len(teams)]
            day = (i % 28) + 1
            month = (i % 4) + 9  # Sept-Dec
            f.write(
                f"2023-{month:02d}-{day:02d},2023,0,,{team1},{team2},"
                f"1600.{i:02d},1500.{i:02d},0.60,0.40,1610.{i:02d},1490.{i:02d},"
                f"1650.{i:02d},1550.{i:02d},QB1,QB2,50.00,40.00\n"
            )

        return Path(f.name)


def generate_many_records(count: int) -> list[HistoricalEloRecord]:
    """Generate many HistoricalEloRecord instances for stress testing."""
    return [
        HistoricalEloRecord(
            team_code="KC",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, (i % 28) + 1),
            elo_rating=Decimal(f"1600.{i:02d}"),
            qb_adjusted_elo=Decimal(f"1700.{i:02d}") if i % 2 == 0 else None,
            qb_name="Patrick Mahomes" if i % 2 == 0 else None,
            qb_value=Decimal(f"80.{i:02d}") if i % 2 == 0 else None,
            source="stress_test",
            source_file=None,
        )
        for i in range(count)
    ]


# =============================================================================
# Stress Tests: Team Code Normalization Volume
# =============================================================================


@pytest.mark.stress
class TestTeamCodeNormalizationStress:
    """Stress tests for team code normalization."""

    def test_normalize_many_codes(self) -> None:
        """Test normalizing many team codes."""
        iterations = 10000
        codes = ["KC", "WSH", "OAK", "SD", "STL", "BUF", "nyj", "det", "LAR", "sf"]

        start = time.perf_counter()
        for i in range(iterations):
            normalize_team_code(codes[i % len(codes)])
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"10000 normalizations took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Record Generation Volume
# =============================================================================


@pytest.mark.stress
class TestRecordGenerationStress:
    """Stress tests for record generation and memory usage."""

    def test_generate_many_records(self) -> None:
        """Test generating many HistoricalEloRecord instances."""
        count = 10000

        gc.collect()
        start_time = time.perf_counter()
        records = generate_many_records(count)
        elapsed = time.perf_counter() - start_time

        assert len(records) == count
        assert elapsed < 5.0, f"Generating {count} records took {elapsed:.2f}s"

    def test_iterate_many_records(self) -> None:
        """Test iterating through many records."""
        count = 10000
        records = generate_many_records(count)

        start_time = time.perf_counter()
        total_elo = Decimal("0")
        for record in records:
            total_elo += record["elo_rating"]
        elapsed = time.perf_counter() - start_time

        assert elapsed < 2.0, f"Iterating {count} records took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: CSV Parsing Volume
# =============================================================================


@pytest.mark.stress
class TestCSVParsingStress:
    """Stress tests for CSV parsing performance."""

    def test_parse_large_csv(self, large_csv_file: Path) -> None:
        """Test parsing large CSV file."""
        start_time = time.perf_counter()
        records = list(parse_fivethirtyeight_csv(large_csv_file))
        elapsed = time.perf_counter() - start_time

        # 500 games * 2 teams = 1000 records
        assert len(records) == 1000
        assert elapsed < 5.0, f"Parsing 1000 records took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Bulk Insert Volume
# =============================================================================


@pytest.mark.stress
class TestBulkInsertStress:
    """Stress tests for bulk insert operations."""

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_many_records(
        self, mock_flush: MagicMock, mock_get_team: MagicMock
    ) -> None:
        """Test bulk inserting many records."""
        mock_get_team.return_value = 1
        mock_flush.return_value = 100  # Batch size

        records = generate_many_records(5000)

        start_time = time.perf_counter()
        result = bulk_insert_historical_elo(iter(records), batch_size=100)
        elapsed = time.perf_counter() - start_time

        assert result.records_processed == 5000
        assert elapsed < 5.0, f"Bulk insert of 5000 records took {elapsed:.2f}s"

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_varied_batch_sizes(
        self, mock_flush: MagicMock, mock_get_team: MagicMock
    ) -> None:
        """Test bulk insert with various batch sizes."""
        mock_get_team.return_value = 1

        for batch_size in [10, 100, 500, 1000]:
            mock_flush.return_value = batch_size
            records = generate_many_records(2000)

            start_time = time.perf_counter()
            result = bulk_insert_historical_elo(iter(records), batch_size=batch_size)
            elapsed = time.perf_counter() - start_time

            assert result.records_processed == 2000
            # Should complete in reasonable time regardless of batch size
            assert elapsed < 3.0, f"Batch size {batch_size} took {elapsed:.2f}s"
