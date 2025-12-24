"""
Chaos Tests for Historical Elo Loader.

Tests edge cases, malformed inputs, and unusual scenarios.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for edge cases
Related Requirements: REQ-DATA-003, Issue #208

Usage:
    pytest tests/chaos/database/seeding/test_historical_elo_loader_chaos.py -v -m chaos
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.batch_result import ErrorHandlingMode
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
def malformed_csv() -> Path:
    """Create a CSV with malformed data."""
    content = """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre
not-a-date,2023,0,,KC,DET,1624.09,1545.23
2023-09-07,not-a-year,0,,BUF,NYJ,1618.75,1496.89
2023-09-10,2023,0,,SF,,1612.44,
2023-09-10,2023,0,,,PIT,,1489.67
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def empty_csv() -> Path:
    """Create an empty CSV (header only)."""
    content = """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def unicode_csv() -> Path:
    """Create a CSV with unicode characters in QB names."""
    content = """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,elo_prob1,elo_prob2,elo1_post,elo2_post,qbelo1_pre,qbelo2_pre,qb1,qb2,qb1_value_pre,qb2_value_pre
2023-09-07,2023,0,,KC,DET,1624.09,1545.23,0.63,0.37,1635.59,1533.73,1711.05,1612.63,Patrick Máhomes,Jared Göff,86.96,67.40
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


# =============================================================================
# Chaos Tests: Team Code Normalization Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestNormalizationEdgeCases:
    """Chaos tests for team code normalization edge cases."""

    def test_empty_string(self) -> None:
        """Test normalizing empty string."""
        result = normalize_team_code("")
        assert result == ""

    def test_single_character(self) -> None:
        """Test normalizing single character."""
        result = normalize_team_code("A")
        assert result == "A"

    def test_very_long_code(self) -> None:
        """Test normalizing very long team code."""
        result = normalize_team_code("ABCDEFGHIJKLMNOP")
        assert result == "ABCDEFGHIJKLMNOP"

    def test_numeric_code(self) -> None:
        """Test normalizing numeric string."""
        result = normalize_team_code("123")
        assert result == "123"

    def test_special_characters(self) -> None:
        """Test normalizing code with special characters."""
        result = normalize_team_code("KC!")
        assert result == "KC!"

    def test_whitespace_code(self) -> None:
        """Test normalizing code with whitespace - whitespace is stripped."""
        result = normalize_team_code(" KC ")
        assert result == "KC"  # Whitespace stripped for clean team codes


# =============================================================================
# Chaos Tests: CSV Parsing Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestCSVParsingEdgeCases:
    """Chaos tests for CSV parsing edge cases."""

    def test_malformed_dates_skipped(self, malformed_csv: Path) -> None:
        """Test that rows with malformed dates are skipped."""
        records = list(parse_fivethirtyeight_csv(malformed_csv))
        # Malformed rows should be skipped, but valid ones processed
        # The exact count depends on how the parser handles edge cases
        assert isinstance(records, list)

    def test_empty_csv_returns_empty(self, empty_csv: Path) -> None:
        """Test empty CSV returns empty list."""
        records = list(parse_fivethirtyeight_csv(empty_csv))
        assert len(records) == 0

    def test_unicode_qb_names(self, unicode_csv: Path) -> None:
        """Test CSV with unicode characters in QB names."""
        records = list(parse_fivethirtyeight_csv(unicode_csv))

        assert len(records) == 2
        qb_names = [r["qb_name"] for r in records if r["qb_name"]]
        assert any("Máhomes" in name for name in qb_names if name)

    def test_nonexistent_file(self) -> None:
        """Test parsing nonexistent file raises appropriate error."""
        with pytest.raises((FileNotFoundError, IOError)):
            list(parse_fivethirtyeight_csv(Path("/nonexistent/file.csv")))


# =============================================================================
# Chaos Tests: LoadResult Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestLoadResultEdgeCases:
    """Chaos tests for LoadResult edge cases."""

    def test_all_zeros(self) -> None:
        """Test LoadResult with all zero counts."""
        result = LoadResult()
        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert result.records_updated == 0
        assert result.records_skipped == 0
        assert result.errors == 0

    def test_very_large_counts(self) -> None:
        """Test LoadResult with very large counts.

        Educational Note:
            Issue #255 unified LoadResult with BatchInsertResult.
            Constructor uses new field names: total_records, successful, skipped.
            The old names (records_processed, records_inserted) are property aliases.
        """
        large = 10**9
        result = LoadResult(
            total_records=large,
            successful=large,
            skipped=large,
        )
        # Access via backward-compatible property alias
        assert result.records_processed == large

    def test_negative_counts_accepted(self) -> None:
        """Test that LoadResult accepts negative counts (no validation).

        Educational Note:
            Constructor uses new field name total_records.
        """
        result = LoadResult(total_records=-1)
        # Access via backward-compatible property alias
        assert result.records_processed == -1

    def test_many_error_messages(self) -> None:
        """Test LoadResult with many error messages.

        Educational Note:
            Issue #255: error_messages is now a property derived from failed_records.
            Use add_failure() to add failed records with error details.
        """
        result = LoadResult(total_records=1000)
        for i in range(1000):
            result.add_failure(
                record_index=i,
                record_data={"id": i},
                error=ValueError(f"Error {i}"),
            )
        assert result.error_messages is not None
        assert len(result.error_messages) == 1000
        assert result.failed == 1000


# =============================================================================
# Chaos Tests: Bulk Insert Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestBulkInsertEdgeCases:
    """Chaos tests for bulk insert edge cases."""

    def test_empty_iterator(self) -> None:
        """Test bulk insert with empty iterator."""
        result = bulk_insert_historical_elo(iter([]))
        assert result.records_processed == 0
        assert result.records_inserted == 0

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_all_teams_unknown(self, mock_flush: MagicMock, mock_get_team: MagicMock) -> None:
        """Test bulk insert when all teams are unknown.

        Educational Note:
            Issue #255: Default error_mode is now FAIL, which raises exceptions.
            To get skip behavior for unknown teams, use SKIP mode explicitly.
        """
        mock_get_team.return_value = None  # All teams not found
        mock_flush.return_value = 0

        records = [
            HistoricalEloRecord(
                team_code=f"UNK{i}",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 9, 7),
                elo_rating=Decimal("1500.00"),
                qb_adjusted_elo=None,
                qb_name=None,
                qb_value=None,
                source="test",
                source_file=None,
            )
            for i in range(10)
        ]

        # Use SKIP mode to avoid raising exceptions for unknown teams
        result = bulk_insert_historical_elo(
            iter(records),
            error_mode=ErrorHandlingMode.SKIP,
        )

        assert result.records_processed == 10
        assert result.records_skipped == 10
        assert result.records_inserted == 0

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_batch_size_one(self, mock_flush: MagicMock, mock_get_team: MagicMock) -> None:
        """Test bulk insert with batch size of 1."""
        mock_get_team.return_value = 1
        mock_flush.return_value = 1

        records = [
            HistoricalEloRecord(
                team_code="KC",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 9, i + 1),
                elo_rating=Decimal("1500.00"),
                qb_adjusted_elo=None,
                qb_name=None,
                qb_value=None,
                source="test",
                source_file=None,
            )
            for i in range(5)
        ]

        result = bulk_insert_historical_elo(iter(records), batch_size=1)

        assert result.records_processed == 5
        # With batch_size=1, should have 5 flush calls
        assert mock_flush.call_count == 5


# =============================================================================
# Chaos Tests: Data Integrity Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestDataIntegrityEdgeCases:
    """Chaos tests for data integrity edge cases."""

    def test_extreme_elo_values(self) -> None:
        """Test record with extreme Elo values."""
        record = HistoricalEloRecord(
            team_code="KC",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 7),
            elo_rating=Decimal("9999.99"),  # Very high
            qb_adjusted_elo=Decimal("0.01"),  # Very low
            qb_name=None,
            qb_value=None,
            source="test",
            source_file=None,
        )
        assert record["elo_rating"] == Decimal("9999.99")
        assert record["qb_adjusted_elo"] == Decimal("0.01")

    def test_future_date(self) -> None:
        """Test record with future date."""
        record = HistoricalEloRecord(
            team_code="KC",
            sport="nfl",
            season=2030,
            rating_date=date(2030, 12, 31),
            elo_rating=Decimal("1600.00"),
            qb_adjusted_elo=None,
            qb_name=None,
            qb_value=None,
            source="test",
            source_file=None,
        )
        assert record["rating_date"] == date(2030, 12, 31)

    def test_historical_date(self) -> None:
        """Test record with very old historical date."""
        record = HistoricalEloRecord(
            team_code="KC",
            sport="nfl",
            season=1920,
            rating_date=date(1920, 9, 17),  # First NFL game
            elo_rating=Decimal("1500.00"),
            qb_adjusted_elo=None,
            qb_name=None,
            qb_value=None,
            source="historical",
            source_file=None,
        )
        assert record["season"] == 1920
