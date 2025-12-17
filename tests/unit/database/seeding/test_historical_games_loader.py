"""
Unit Tests for Historical Games Loader.

Tests the CSV parsing and data transformation functions for loading
historical game results into the database.

Related Requirements:
    - REQ-DATA-006: Historical Games Data Seeding
    - REQ-DATA-008: Data Source Adapter Architecture

Related Architecture:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources

Usage:
    pytest tests/unit/database/seeding/test_historical_games_loader.py -v
"""

import tempfile
from datetime import date
from pathlib import Path

from precog.database.seeding.historical_games_loader import (
    HistoricalGameRecord,
    LoadResult,
    parse_fivethirtyeight_games_csv,
    parse_simple_games_csv,
)

# =============================================================================
# LoadResult Tests
# =============================================================================


class TestLoadResult:
    """Test suite for LoadResult dataclass."""

    def test_default_values(self) -> None:
        """Verify LoadResult initializes with zero counts."""
        result = LoadResult()
        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert result.records_updated == 0
        assert result.records_skipped == 0
        assert result.errors == 0
        assert result.error_messages == []

    def test_custom_initialization(self) -> None:
        """Verify LoadResult accepts custom values."""
        result = LoadResult(
            records_processed=100,
            records_inserted=90,
            records_updated=5,
            records_skipped=3,
            errors=2,
            error_messages=["Error 1", "Error 2"],
        )
        assert result.records_processed == 100
        assert result.records_inserted == 90
        assert result.records_updated == 5
        assert result.records_skipped == 3
        assert result.errors == 2
        assert len(result.error_messages) == 2


# =============================================================================
# CSV Parser Tests
# =============================================================================


class TestParseFivethirtyeightGamesCsv:
    """Test suite for FiveThirtyEight CSV parser."""

    def test_parse_valid_csv(self) -> None:
        """Verify parser handles valid FiveThirtyEight format."""
        csv_content = """date,season,team1,team2,score1,score2,neutral,playoff
2023-09-07,2023,KC,DET,21,20,0,0
2023-09-10,2023,SF,PIT,30,7,0,0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            records = list(parse_fivethirtyeight_games_csv(temp_path, sport="nfl"))

            assert len(records) == 2

            # Check first record
            assert records[0]["sport"] == "nfl"
            assert records[0]["season"] == 2023
            assert records[0]["game_date"] == date(2023, 9, 7)
            assert records[0]["home_score"] == 21
            assert records[0]["away_score"] == 20
            assert records[0]["is_neutral_site"] is False
            assert records[0]["is_playoff"] is False
            assert records[0]["source"] == "fivethirtyeight"
        finally:
            temp_path.unlink()

    def test_parse_with_season_filter(self) -> None:
        """Verify parser respects season filter."""
        csv_content = """date,season,team1,team2,score1,score2,neutral,playoff
2022-09-08,2022,BUF,LAR,31,10,0,0
2023-09-07,2023,KC,DET,21,20,0,0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            records = list(parse_fivethirtyeight_games_csv(temp_path, sport="nfl", seasons=[2023]))
            assert len(records) == 1
            assert records[0]["season"] == 2023
        finally:
            temp_path.unlink()

    def test_parse_playoff_game(self) -> None:
        """Verify parser handles playoff game flag."""
        csv_content = """date,season,team1,team2,score1,score2,neutral,playoff
2024-01-14,2023,KC,MIA,26,7,0,1
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            records = list(parse_fivethirtyeight_games_csv(temp_path, sport="nfl"))
            assert len(records) == 1
            assert records[0]["is_playoff"] is True
            assert records[0]["game_type"] == "playoff"
        finally:
            temp_path.unlink()


class TestParseSimpleGamesCsv:
    """Test suite for simple CSV parser."""

    def test_parse_valid_simple_csv(self) -> None:
        """Verify parser handles simple CSV format."""
        csv_content = """game_date,season,home_team_code,away_team_code,home_score,away_score
2023-09-07,2023,KC,DET,21,20
2023-09-10,2023,SF,PIT,30,7
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            records = list(parse_simple_games_csv(temp_path, sport="nfl"))

            assert len(records) == 2
            assert records[0]["sport"] == "nfl"
            assert records[0]["home_team_code"] == "KC"
            assert records[0]["away_team_code"] == "DET"
            assert records[0]["source"] == "imported"
        finally:
            temp_path.unlink()


# =============================================================================
# TypedDict Structure Tests
# =============================================================================


class TestHistoricalGameRecord:
    """Test suite for HistoricalGameRecord TypedDict."""

    def test_record_has_required_fields(self) -> None:
        """Verify HistoricalGameRecord has all required fields."""
        record: HistoricalGameRecord = {
            "sport": "nfl",
            "season": 2023,
            "game_date": date(2023, 9, 7),
            "home_team_code": "KC",
            "away_team_code": "DET",
            "home_score": 21,
            "away_score": 20,
            "is_neutral_site": False,
            "is_playoff": False,
            "game_type": "regular",
            "venue_name": "GEHA Field",
            "source": "fivethirtyeight",
            "source_file": "nfl_elo.csv",
            "external_game_id": None,
        }

        assert record["sport"] == "nfl"
        assert record["season"] == 2023
        assert record["home_team_code"] == "KC"
        assert record["home_score"] == 21
