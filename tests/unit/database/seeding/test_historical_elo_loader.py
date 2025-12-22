"""
Unit Tests for Historical Elo Loader.

Comprehensive test coverage for the historical_elo_loader module including:
- Team code normalization (FiveThirtyEight -> database format)
- FiveThirtyEight CSV parsing
- Simple CSV parsing
- Database operations (mocked)
- Bulk insert batching logic

Tests follow the project's testing patterns:
- Pattern 1: Decimal precision (all Elo ratings use Decimal)
- Pattern 4: Security (no real credentials)
- Pattern 7: Educational docstrings
- Antipattern 4: Mock Isolation (typed fixtures match real returns)

Related:
- Issue #208: Historical Data Seeding
- Migration 030: Create historical_elo table
- REQ-DATA-003: Multi-Sport Team Support

Usage:
    pytest tests/unit/database/seeding/test_historical_elo_loader.py -v
    pytest tests/unit/database/seeding/test_historical_elo_loader.py -v -m unit
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.historical_elo_loader import (
    TEAM_CODE_MAPPING,
    HistoricalEloRecord,
    LoadResult,
    bulk_insert_historical_elo,
    normalize_team_code,
    parse_fivethirtyeight_csv,
    parse_simple_csv,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def fivethirtyeight_csv_content() -> str:
    """Sample FiveThirtyEight NFL Elo CSV content.

    Educational Note:
        FiveThirtyEight CSV format has game-by-game data with both teams.
        Each row contains pre-game and post-game Elo ratings for both teams,
        along with QB-adjusted ratings for NFL.
    """
    return """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,elo_prob1,elo_prob2,elo1_post,elo2_post,qbelo1_pre,qbelo2_pre,qb1,qb2,qb1_value_pre,qb2_value_pre
2023-09-07,2023,0,,KC,DET,1624.09,1545.23,0.63,0.37,1635.59,1533.73,1711.05,1612.63,Patrick Mahomes,Jared Goff,86.96,67.40
2023-09-10,2023,0,,BUF,NYJ,1618.75,1496.89,0.70,0.30,1592.35,1523.29,1666.92,1484.34,Josh Allen,Aaron Rodgers,48.17,-12.55
2023-09-10,2023,0,,WSH,ARI,1421.50,1388.25,0.53,0.47,1399.88,1409.87,1443.81,1415.07,Sam Howell,Kyler Murray,22.31,26.82
2024-01-07,2024,0,w,KC,MIA,1648.32,1573.88,0.62,0.38,1665.71,1556.49,1698.45,1621.05,Patrick Mahomes,Tua Tagovailoa,50.13,47.17
"""


@pytest.fixture
def simple_csv_content() -> str:
    """Sample simple CSV with team, date, rating columns.

    Educational Note:
        Simple CSV format is for custom Elo calculations or data from
        other sources that don't follow FiveThirtyEight format.
    """
    return """team_code,date,season,elo_rating,qb_adjusted_elo,qb_name
KC,2023-09-07,2023,1624.09,1711.05,Patrick Mahomes
DET,2023-09-07,2023,1545.23,1612.63,Jared Goff
BUF,2023-09-10,2023,1618.75,1666.92,Josh Allen
NYJ,2023-09-10,2023,1496.89,1484.34,Aaron Rodgers
"""


@pytest.fixture
def temp_fivethirtyeight_csv(fivethirtyeight_csv_content: str) -> Path:
    """Create a temporary FiveThirtyEight CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(fivethirtyeight_csv_content)
        return Path(f.name)


@pytest.fixture
def temp_simple_csv(simple_csv_content: str) -> Path:
    """Create a temporary simple CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(simple_csv_content)
        return Path(f.name)


# =============================================================================
# TEAM CODE NORMALIZATION TESTS
# =============================================================================


class TestNormalizeTeamCode:
    """Tests for team code normalization from external sources."""

    def test_normalize_unchanged_codes(self):
        """Verify common codes that don't need mapping.

        Educational Note:
            Most team codes match between FiveThirtyEight and our database.
            Only historical relocations/renames need explicit mapping.
        """
        unchanged = ["KC", "BUF", "NYJ", "DET", "LAR", "SF", "NE", "DAL"]
        for code in unchanged:
            assert normalize_team_code(code) == code

    def test_normalize_washington_code(self):
        """Verify Washington team code mapping.

        Educational Note:
            Washington has used multiple names: Redskins, Football Team, Commanders.
            FiveThirtyEight uses WSH, we use WAS.
        """
        assert normalize_team_code("WSH") == "WAS"
        assert normalize_team_code("wsh") == "WAS"  # Case insensitive

    def test_normalize_raiders_code(self):
        """Verify Raiders team code mapping (Oakland -> Las Vegas)."""
        assert normalize_team_code("OAK") == "LV"
        assert normalize_team_code("oak") == "LV"

    def test_normalize_chargers_code(self):
        """Verify Chargers team code mapping (San Diego -> LA)."""
        assert normalize_team_code("SD") == "LAC"
        assert normalize_team_code("sd") == "LAC"

    def test_normalize_rams_code(self):
        """Verify Rams team code mapping (St. Louis -> LA)."""
        assert normalize_team_code("STL") == "LAR"
        assert normalize_team_code("stl") == "LAR"

    def test_normalize_case_insensitive(self):
        """Verify normalization handles mixed case."""
        assert normalize_team_code("kc") == "KC"
        assert normalize_team_code("Kc") == "KC"
        assert normalize_team_code("KC") == "KC"

    def test_team_code_mapping_completeness(self):
        """Verify known relocations are in the mapping.

        Educational Note:
            This test documents which team relocations we handle.
            Add to this list when teams relocate.
        """
        expected_mappings = {"WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
        for source, target in expected_mappings.items():
            assert source in TEAM_CODE_MAPPING
            assert TEAM_CODE_MAPPING[source] == target


# =============================================================================
# LOAD RESULT TESTS
# =============================================================================


class TestLoadResult:
    """Tests for LoadResult dataclass."""

    def test_default_values(self):
        """Verify LoadResult initializes with zeros."""
        result = LoadResult()
        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert result.records_updated == 0
        assert result.records_skipped == 0
        assert result.errors == 0
        assert result.error_messages == []

    def test_error_messages_initialization(self):
        """Verify error_messages defaults to empty list.

        Educational Note:
            BatchInsertResult (now aliased as LoadResult) uses failed_records
            internally and exposes error_messages as a compatibility property.
        """
        result = LoadResult(total_records=10)
        assert result.error_messages is not None
        assert isinstance(result.error_messages, list)
        assert len(result.error_messages) == 0

    def test_custom_values(self):
        """Verify LoadResult/BatchInsertResult accepts custom values.

        Educational Note:
            LoadResult is now an alias for BatchInsertResult with compatibility
            properties. Use new field names (total_records, successful) but
            old names (records_processed, records_inserted) work for reads.
        """
        result = LoadResult(
            total_records=100,
            successful=90,
            skipped=10,
            failed=2,
        )
        # Add some failures to test error_messages
        result.add_failure(0, {"id": 1}, ValueError("Error 1"))
        result.add_failure(1, {"id": 2}, ValueError("Error 2"))

        # Test both new and compatibility property names
        assert result.total_records == 100
        assert result.records_processed == 100  # Compatibility alias
        assert result.successful == 90
        assert result.records_inserted == 90  # Compatibility alias
        assert result.skipped == 10
        assert result.records_skipped == 10  # Compatibility alias
        assert result.failed == 4  # 2 initial + 2 added
        assert result.errors == 4  # Compatibility alias
        assert len(result.error_messages) == 2  # From add_failure calls


# =============================================================================
# FIVETHIRTYEIGHT CSV PARSING TESTS
# =============================================================================


class TestParseFivethirtyeightCSV:
    """Tests for FiveThirtyEight CSV parsing."""

    def test_parse_basic_records(self, temp_fivethirtyeight_csv: Path):
        """Verify basic CSV parsing extracts all team records.

        Educational Note:
            Each game row produces TWO records (one for each team).
            A 4-game CSV should produce 8 records.
        """
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv))

        # 4 games * 2 teams = 8 records
        assert len(records) == 8

    def test_parse_season_filter(self, temp_fivethirtyeight_csv: Path):
        """Verify season filtering works correctly."""
        # Filter to 2023 only (3 games)
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv, seasons=[2023]))
        assert len(records) == 6  # 3 games * 2 teams

        # Filter to 2024 only (1 game)
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv, seasons=[2024]))
        assert len(records) == 2  # 1 game * 2 teams

    def test_parse_elo_ratings_as_decimal(self, temp_fivethirtyeight_csv: Path):
        """Verify Elo ratings are parsed as Decimal, not float.

        Educational Note:
            Pattern 1 (Decimal Precision) requires ALL prices and ratings
            to use Decimal to prevent floating-point errors.
        """
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv))

        for record in records:
            assert isinstance(record["elo_rating"], Decimal)
            if record["qb_adjusted_elo"]:
                assert isinstance(record["qb_adjusted_elo"], Decimal)
            if record["qb_value"]:
                assert isinstance(record["qb_value"], Decimal)

    def test_parse_specific_values(self, temp_fivethirtyeight_csv: Path):
        """Verify specific values are parsed correctly."""
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv))

        # Find KC record from first game
        kc_records = [r for r in records if r["team_code"] == "KC"]
        assert len(kc_records) >= 1

        kc_2023 = next(r for r in kc_records if r["season"] == 2023)
        assert kc_2023["elo_rating"] == Decimal("1624.09")
        assert kc_2023["qb_adjusted_elo"] == Decimal("1711.05")
        assert kc_2023["qb_name"] == "Patrick Mahomes"
        assert kc_2023["source"] == "fivethirtyeight"

    def test_parse_team_code_normalization(self, temp_fivethirtyeight_csv: Path):
        """Verify team codes are normalized during parsing.

        Educational Note:
            WSH in CSV should become WAS in parsed records.
        """
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv))

        # Find Washington record (should be WAS, not WSH)
        team_codes = [r["team_code"] for r in records]
        assert "WAS" in team_codes
        assert "WSH" not in team_codes

    def test_parse_date_format(self, temp_fivethirtyeight_csv: Path):
        """Verify dates are parsed to date objects."""
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv))

        for record in records:
            assert isinstance(record["rating_date"], date)

        # Check specific date
        kc_records = [r for r in records if r["team_code"] == "KC"]
        dates = [r["rating_date"] for r in kc_records]
        assert date(2023, 9, 7) in dates

    def test_parse_source_file_tracking(self, temp_fivethirtyeight_csv: Path):
        """Verify source file name is tracked in records."""
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv))

        for record in records:
            assert record["source_file"] is not None
            assert record["source_file"].endswith(".csv")


# =============================================================================
# SIMPLE CSV PARSING TESTS
# =============================================================================


class TestParseSimpleCSV:
    """Tests for simple CSV parsing."""

    def test_parse_basic_records(self, temp_simple_csv: Path):
        """Verify basic CSV parsing works."""
        records = list(parse_simple_csv(temp_simple_csv, sport="nfl"))

        assert len(records) == 4

    def test_parse_custom_source(self, temp_simple_csv: Path):
        """Verify custom source is applied to records."""
        records = list(parse_simple_csv(temp_simple_csv, sport="nfl", source="kaggle"))

        for record in records:
            assert record["source"] == "kaggle"

    def test_parse_sport_assignment(self, temp_simple_csv: Path):
        """Verify sport is assigned to all records."""
        records = list(parse_simple_csv(temp_simple_csv, sport="nba"))

        for record in records:
            assert record["sport"] == "nba"

    def test_parse_elo_as_decimal(self, temp_simple_csv: Path):
        """Verify Elo ratings are Decimal."""
        records = list(parse_simple_csv(temp_simple_csv, sport="nfl"))

        for record in records:
            assert isinstance(record["elo_rating"], Decimal)


# =============================================================================
# HISTORICAL ELO RECORD TYPE TESTS
# =============================================================================


class TestHistoricalEloRecord:
    """Tests for HistoricalEloRecord TypedDict structure."""

    def test_record_has_required_fields(self):
        """Verify HistoricalEloRecord has all required fields.

        Educational Note:
            TypedDict provides compile-time type checking for dictionary
            structures. This test documents the expected structure.
        """
        record: HistoricalEloRecord = {
            "team_code": "KC",
            "sport": "nfl",
            "season": 2023,
            "rating_date": date(2023, 9, 7),
            "elo_rating": Decimal("1624.09"),
            "qb_adjusted_elo": Decimal("1711.05"),
            "qb_name": "Patrick Mahomes",
            "qb_value": Decimal("86.96"),
            "source": "fivethirtyeight",
            "source_file": "nfl_elo.csv",
        }

        assert record["team_code"] == "KC"
        assert record["sport"] == "nfl"
        assert record["season"] == 2023
        assert record["rating_date"] == date(2023, 9, 7)
        assert record["elo_rating"] == Decimal("1624.09")
        assert record["qb_adjusted_elo"] == Decimal("1711.05")
        assert record["qb_name"] == "Patrick Mahomes"

    def test_record_optional_fields(self):
        """Verify optional fields can be None."""
        record: HistoricalEloRecord = {
            "team_code": "KC",
            "sport": "nba",  # NBA doesn't have QB adjustments
            "season": 2023,
            "rating_date": date(2023, 10, 24),
            "elo_rating": Decimal("1550.00"),
            "qb_adjusted_elo": None,
            "qb_name": None,
            "qb_value": None,
            "source": "calculated",
            "source_file": None,
        }

        assert record["qb_adjusted_elo"] is None
        assert record["qb_name"] is None
        assert record["qb_value"] is None
        assert record["source_file"] is None


# =============================================================================
# BULK INSERT TESTS (WITH MOCKED DATABASE)
# =============================================================================


class TestBulkInsertHistoricalElo:
    """Tests for bulk insert functionality with mocked database."""

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_counts_processed(self, mock_flush: MagicMock, mock_get_team: MagicMock):
        """Verify processed count is accurate."""
        mock_get_team.return_value = 1  # All teams found
        mock_flush.return_value = 5  # Simulate 5 inserts

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
            for _ in range(5)
        ]

        result = bulk_insert_historical_elo(iter(records))

        assert result.records_processed == 5

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_skips_unknown_teams_in_skip_mode(
        self, mock_flush: MagicMock, mock_get_team: MagicMock
    ):
        """Verify unknown teams are skipped in SKIP error mode.

        Educational Note:
            In SKIP mode, if a team_code doesn't exist in the teams table,
            the record is skipped rather than causing an error.
        """
        from precog.database.seeding.batch_result import ErrorHandlingMode

        mock_get_team.return_value = None  # Team not found
        mock_flush.return_value = 0

        records = [
            HistoricalEloRecord(
                team_code="UNKNOWN",
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
            for _ in range(3)
        ]

        result = bulk_insert_historical_elo(iter(records), error_mode=ErrorHandlingMode.SKIP)

        assert result.records_processed == 3
        assert result.records_skipped == 3
        assert result.records_inserted == 0

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    def test_bulk_insert_fails_on_unknown_team_in_fail_mode(self, mock_get_team: MagicMock):
        """Verify unknown teams raise error in FAIL mode (default).

        Educational Note:
            In FAIL mode (default), the first error stops processing and
            raises an exception. This ensures transactional integrity.
        """
        import pytest

        from precog.database.seeding.batch_result import ErrorHandlingMode

        mock_get_team.return_value = None  # Team not found

        records = [
            HistoricalEloRecord(
                team_code="UNKNOWN",
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
        ]

        with pytest.raises(ValueError, match="Team not found"):
            bulk_insert_historical_elo(iter(records), error_mode=ErrorHandlingMode.FAIL)

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_collects_unknown_teams_in_collect_mode(
        self, mock_flush: MagicMock, mock_get_team: MagicMock
    ):
        """Verify unknown teams are tracked in COLLECT error mode.

        Educational Note:
            In COLLECT mode, all records are processed and failures are
            collected with details for later analysis.
        """
        from precog.database.seeding.batch_result import ErrorHandlingMode

        mock_get_team.return_value = None  # Team not found
        mock_flush.return_value = 0

        records = [
            HistoricalEloRecord(
                team_code="UNKNOWN",
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
            for _ in range(3)
        ]

        result = bulk_insert_historical_elo(iter(records), error_mode=ErrorHandlingMode.COLLECT)

        assert result.records_processed == 3
        assert result.failed == 3
        assert len(result.failed_records) == 3
        # Verify failure details are captured
        assert result.failed_records[0].error_type == "ValueError"
        assert "Team not found" in result.failed_records[0].error_message
        assert result.failed_records[0].context == "team_lookup"

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_caches_team_lookups(self, mock_flush: MagicMock, mock_get_team: MagicMock):
        """Verify team lookups are cached to minimize DB queries.

        Educational Note:
            For large datasets (100k+ records), querying team_id for each
            record would be slow. Caching ensures each (team_code, sport)
            combination is looked up only once.
        """
        mock_get_team.return_value = 1
        mock_flush.return_value = 10

        # 10 records for same team
        records = [
            HistoricalEloRecord(
                team_code="KC",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 9, i + 1),
                elo_rating=Decimal("1600.00"),
                qb_adjusted_elo=None,
                qb_name=None,
                qb_value=None,
                source="test",
                source_file=None,
            )
            for i in range(10)
        ]

        bulk_insert_historical_elo(iter(records))

        # Should only call get_team_id_by_code ONCE for KC/nfl
        assert mock_get_team.call_count == 1

    @patch("precog.database.seeding.historical_elo_loader.get_team_id_by_code")
    @patch("precog.database.seeding.historical_elo_loader._flush_batch")
    def test_bulk_insert_batching(self, mock_flush: MagicMock, mock_get_team: MagicMock):
        """Verify records are batched correctly.

        Educational Note:
            Large datasets should be inserted in batches to avoid
            memory issues and improve transaction performance.
        """
        mock_get_team.return_value = 1
        mock_flush.return_value = 100

        # 250 records with batch_size=100 should result in 3 flush calls
        records = [
            HistoricalEloRecord(
                team_code="KC",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 1, 1),
                elo_rating=Decimal("1600.00"),
                qb_adjusted_elo=None,
                qb_name=None,
                qb_value=None,
                source="test",
                source_file=None,
            )
            for _ in range(250)
        ]

        bulk_insert_historical_elo(iter(records), batch_size=100)

        # 250 / 100 = 2 full batches + 1 partial batch = 3 calls
        assert mock_flush.call_count == 3


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_csv(self):
        """Verify empty CSV returns empty iterator."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("date,season,team1,team2,elo1_pre,elo2_pre\n")
            csv_path = Path(f.name)

        records = list(parse_fivethirtyeight_csv(csv_path))
        assert len(records) == 0

    def test_malformed_date_skipped(self):
        """Verify rows with invalid dates are skipped.

        Educational Note:
            Data quality issues (malformed dates, invalid numbers) should
            be logged and skipped rather than crashing the entire load.
        """
        content = """date,season,team1,team2,elo1_pre,elo2_pre
not-a-date,2023,KC,DET,1624.09,1545.23
2023-09-07,2023,BUF,NYJ,1618.75,1496.89
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            csv_path = Path(f.name)

        records = list(parse_fivethirtyeight_csv(csv_path))

        # Only valid row should be parsed (2 teams)
        assert len(records) == 2

    def test_missing_elo_rating_skipped(self):
        """Verify rows missing Elo ratings are skipped."""
        content = """date,season,team1,team2,elo1_pre,elo2_pre
2023-09-07,2023,KC,,1624.09,
2023-09-10,2023,BUF,NYJ,1618.75,1496.89
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            csv_path = Path(f.name)

        records = list(parse_fivethirtyeight_csv(csv_path))

        # First row missing team2 and elo2, second row valid
        # KC from first row + BUF and NYJ from second row = 3 records
        assert len(records) == 3

    def test_nonexistent_season_filter(self, temp_fivethirtyeight_csv: Path):
        """Verify filtering to nonexistent season returns empty."""
        records = list(parse_fivethirtyeight_csv(temp_fivethirtyeight_csv, seasons=[1999]))
        assert len(records) == 0


# =============================================================================
# INTEGRATION-READY TESTS (Can be extended for integration testing)
# =============================================================================


class TestCSVFormats:
    """Tests documenting expected CSV format variations."""

    def test_fivethirtyeight_required_columns(self):
        """Document required columns for FiveThirtyEight format.

        Educational Note:
            This test documents the minimum required columns for
            FiveThirtyEight CSV parsing. Missing columns will cause
            records to be skipped with warnings.
        """
        required_columns = {
            "date",  # Game date (YYYY-MM-DD)
            "season",  # Season year
            "team1",  # Home team abbreviation
            "team2",  # Away team abbreviation
            "elo1_pre",  # Home team pre-game Elo
            "elo2_pre",  # Away team pre-game Elo
        }
        # This documents the contract - actual validation is in the parser
        assert len(required_columns) == 6

    def test_simple_csv_required_columns(self):
        """Document required columns for simple CSV format."""
        required_columns = {
            "team_code",  # Team abbreviation
            "date",  # Rating date (YYYY-MM-DD)
            "season",  # Season year
            "elo_rating",  # Elo rating value
        }
        assert len(required_columns) == 4
