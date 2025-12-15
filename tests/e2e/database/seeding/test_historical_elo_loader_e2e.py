"""
End-to-End Tests for Historical Elo Loader.

Tests complete workflows from CSV parsing to database insertion.

Reference: TESTING_STRATEGY V3.2 - E2E tests for critical paths
Related Requirements: REQ-DATA-003, Issue #208

Usage:
    pytest tests/e2e/database/seeding/test_historical_elo_loader_e2e.py -v -m e2e
"""

import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.historical_elo_loader import (
    bulk_insert_historical_elo,
    parse_fivethirtyeight_csv,
    parse_simple_csv,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fivethirtyeight_csv_file() -> Path:
    """Create a realistic FiveThirtyEight CSV file for E2E testing."""
    content = """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,elo_prob1,elo_prob2,elo1_post,elo2_post,qbelo1_pre,qbelo2_pre,qb1,qb2,qb1_value_pre,qb2_value_pre
2023-09-07,2023,0,,KC,DET,1624.09,1545.23,0.63,0.37,1635.59,1533.73,1711.05,1612.63,Patrick Mahomes,Jared Goff,86.96,67.40
2023-09-10,2023,0,,BUF,NYJ,1618.75,1496.89,0.70,0.30,1592.35,1523.29,1666.92,1484.34,Josh Allen,Aaron Rodgers,48.17,-12.55
2023-09-10,2023,0,,SF,PIT,1612.44,1489.67,0.69,0.31,1628.94,1473.17,1654.32,1501.45,Brock Purdy,Kenny Pickett,41.88,11.78
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def simple_csv_file() -> Path:
    """Create a simple CSV file for E2E testing."""
    content = """team_code,date,season,elo_rating,qb_adjusted_elo,qb_name
KC,2023-09-07,2023,1624.09,1711.05,Patrick Mahomes
BUF,2023-09-10,2023,1618.75,1666.92,Josh Allen
SF,2023-09-10,2023,1612.44,1654.32,Brock Purdy
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


# =============================================================================
# E2E Tests: FiveThirtyEight CSV Workflow
# =============================================================================


@pytest.mark.e2e
class TestFiveThirtyEightWorkflow:
    """E2E tests for FiveThirtyEight CSV import workflow."""

    def test_parse_and_count_records(self, fivethirtyeight_csv_file: Path) -> None:
        """Test parsing FiveThirtyEight CSV produces correct record count."""
        records = list(parse_fivethirtyeight_csv(fivethirtyeight_csv_file))

        # 3 games * 2 teams per game = 6 records
        assert len(records) == 6

    def test_parse_and_verify_decimal_precision(self, fivethirtyeight_csv_file: Path) -> None:
        """Test parsed records maintain Decimal precision."""
        records = list(parse_fivethirtyeight_csv(fivethirtyeight_csv_file))

        for record in records:
            assert isinstance(record["elo_rating"], Decimal)
            if record["qb_adjusted_elo"]:
                assert isinstance(record["qb_adjusted_elo"], Decimal)

    def test_parse_and_verify_team_normalization(self, fivethirtyeight_csv_file: Path) -> None:
        """Test team codes are normalized during parsing."""
        records = list(parse_fivethirtyeight_csv(fivethirtyeight_csv_file))

        team_codes = [r["team_code"] for r in records]
        # All team codes should be uppercase
        for code in team_codes:
            assert code == code.upper()

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_full_import_workflow(
        self,
        mock_flush: MagicMock,
        mock_get_team: MagicMock,
        fivethirtyeight_csv_file: Path,
    ) -> None:
        """Test complete workflow: parse -> bulk insert."""
        mock_get_team.return_value = 1  # All teams found
        mock_flush.return_value = 6  # All records inserted

        # Parse CSV
        records = parse_fivethirtyeight_csv(fivethirtyeight_csv_file)

        # Bulk insert
        result = bulk_insert_historical_elo(records)

        assert result.records_processed == 6
        assert result.errors == 0


# =============================================================================
# E2E Tests: Simple CSV Workflow
# =============================================================================


@pytest.mark.e2e
class TestSimpleCSVWorkflow:
    """E2E tests for simple CSV import workflow."""

    def test_parse_and_count_records(self, simple_csv_file: Path) -> None:
        """Test parsing simple CSV produces correct record count."""
        records = list(parse_simple_csv(simple_csv_file, sport="nfl"))

        assert len(records) == 3

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_full_import_workflow(
        self,
        mock_flush: MagicMock,
        mock_get_team: MagicMock,
        simple_csv_file: Path,
    ) -> None:
        """Test complete workflow with simple CSV."""
        mock_get_team.return_value = 1
        mock_flush.return_value = 3

        records = parse_simple_csv(simple_csv_file, sport="nfl")
        result = bulk_insert_historical_elo(records)

        assert result.records_processed == 3


# =============================================================================
# E2E Tests: Season Filtering Workflow
# =============================================================================


@pytest.mark.e2e
class TestSeasonFilteringWorkflow:
    """E2E tests for season-filtered import workflows."""

    def test_filter_by_single_season(self, fivethirtyeight_csv_file: Path) -> None:
        """Test filtering to single season."""
        records = list(parse_fivethirtyeight_csv(fivethirtyeight_csv_file, seasons=[2023]))

        for record in records:
            assert record["season"] == 2023

    def test_filter_excludes_other_seasons(self, fivethirtyeight_csv_file: Path) -> None:
        """Test filtering excludes non-matching seasons."""
        records = list(parse_fivethirtyeight_csv(fivethirtyeight_csv_file, seasons=[2024]))

        # No 2024 data in our fixture
        assert len(records) == 0
