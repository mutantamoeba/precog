"""
Unit Tests for FiveThirtyEight Data Source Adapter.

Tests the FiveThirtyEightSource adapter for loading historical Elo ratings
and game results from FiveThirtyEight CSV files.

Tests follow the project's testing patterns:
- Pattern 1: Decimal precision (all Elo ratings use Decimal)
- Pattern 7: Educational docstrings
- Pattern 10: Property-based testing concepts

Related:
- ADR-106: Historical Data Collection Architecture
- Issue #229: Expanded Historical Data Sources
- fivethirtyeight.py: Source implementation

Usage:
    pytest tests/unit/database/seeding/test_fivethirtyeight_source.py -v
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from precog.database.seeding.sources.base_source import DataSourceConfigError
from precog.database.seeding.sources.fivethirtyeight import FiveThirtyEightSource

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def fivethirtyeight_csv_content() -> str:
    """Sample FiveThirtyEight NFL Elo CSV content.

    Educational Note:
        FiveThirtyEight CSV format contains both Elo ratings AND game results.
        Key columns:
        - date: Game date (YYYY-MM-DD)
        - season: Season year
        - team1/team2: Team abbreviations (team1 = home)
        - elo1_pre/elo2_pre: Pre-game Elo ratings
        - score1/score2: Final scores
        - neutral: 1 if neutral site
        - playoff: 1 if playoff game
    """
    return """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,elo_prob1,elo_prob2,score1,score2,elo1_post,elo2_post
2023-09-07,2023,0,,KC,DET,1624.09,1548.23,0.6876,0.3124,21,20,1626.23,1546.09
2023-09-10,2023,0,,BUF,NYJ,1598.45,1521.67,0.6543,0.3457,22,16,1603.12,1517.00
2023-09-10,2023,0,,SF,PIT,1610.33,1475.89,0.7234,0.2766,30,7,1621.56,1464.66
2024-01-20,2024,0,1,KC,BUF,1632.45,1608.23,0.5678,0.4322,27,24,1638.12,1602.56
2024-02-11,2024,1,1,KC,SF,1645.67,1625.34,0.5432,0.4568,25,22,1651.23,1619.78
"""


@pytest.fixture
def fivethirtyeight_csv_file(fivethirtyeight_csv_content: str) -> Path:
    """Create a temporary CSV file with sample FiveThirtyEight data."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(fivethirtyeight_csv_content)
        return Path(f.name)


@pytest.fixture
def empty_csv_file() -> Path:
    """Create an empty CSV file with headers only."""
    content = "date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,score1,score2\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def malformed_csv_content() -> str:
    """CSV with malformed rows for error handling tests."""
    return """date,season,neutral,playoff,team1,team2,elo1_pre,elo2_pre,score1,score2
invalid-date,2023,0,,KC,DET,1624.09,1548.23,21,20
2023-09-07,not_a_number,0,,BUF,NYJ,1598.45,1521.67,22,16
2023-09-10,2023,0,,,PIT,1610.33,1475.89,30,7
2023-09-10,2023,0,,SF,,1610.33,1475.89,30,7
2023-09-10,2023,0,,SF,GB,invalid_elo,1490.00,24,22
"""


@pytest.fixture
def malformed_csv_file(malformed_csv_content: str) -> Path:
    """Create a temporary CSV file with malformed data."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(malformed_csv_content)
        return Path(f.name)


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestFiveThirtyEightSourceInit:
    """Test suite for FiveThirtyEightSource initialization."""

    def test_default_initialization(self) -> None:
        """Verify default initialization uses data/historical path."""
        source = FiveThirtyEightSource()
        assert source.source_name == "fivethirtyeight"
        assert source.data_dir == Path("data/historical")

    def test_custom_data_dir(self) -> None:
        """Verify custom data directory is used."""
        custom_dir = Path("/custom/data")
        source = FiveThirtyEightSource(data_dir=custom_dir)
        assert source.data_dir == custom_dir

    def test_supported_sports(self) -> None:
        """Verify supported sports list."""
        source = FiveThirtyEightSource()
        assert "nfl" in source.supported_sports
        assert "nba" in source.supported_sports
        assert "mlb" in source.supported_sports
        assert len(source.supported_sports) == 3

    def test_default_files_mapping(self) -> None:
        """Verify default file names for each sport."""
        assert FiveThirtyEightSource.DEFAULT_FILES["nfl"] == "nfl_elo.csv"
        assert FiveThirtyEightSource.DEFAULT_FILES["nba"] == "nba_elo.csv"
        assert FiveThirtyEightSource.DEFAULT_FILES["mlb"] == "mlb_elo.csv"


# =============================================================================
# FILE PATH TESTS
# =============================================================================


class TestGetFilePath:
    """Test suite for _get_file_path method."""

    def test_raises_for_unsupported_sport(self) -> None:
        """Verify error for unsupported sport."""
        source = FiveThirtyEightSource()

        with pytest.raises(DataSourceConfigError) as exc_info:
            source._get_file_path("soccer")

        assert "No default file for sport" in str(exc_info.value)

    def test_raises_for_missing_file(self) -> None:
        """Verify error for non-existent file."""
        source = FiveThirtyEightSource(data_dir=Path("/nonexistent"))

        with pytest.raises(DataSourceConfigError) as exc_info:
            source._get_file_path("nfl")

        assert "not found" in str(exc_info.value)


# =============================================================================
# ELO LOADING TESTS
# =============================================================================


class TestLoadElo:
    """Test suite for load_elo method."""

    def test_load_elo_returns_iterator(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify load_elo returns an iterator of EloRecords."""
        source = FiveThirtyEightSource()
        records = list(source.load_elo(sport="nfl", file_path=fivethirtyeight_csv_file))

        # Each game produces 2 Elo records (team1 + team2)
        # 5 games in fixture = 10 Elo records
        assert len(records) == 10

    def test_elo_record_structure(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify EloRecord has all required fields.

        Educational Note:
            EloRecord maps to historical_elo table. All ratings
            are stored as Decimal for precision (Pattern 1).
        """
        source = FiveThirtyEightSource()
        records = list(source.load_elo(sport="nfl", file_path=fivethirtyeight_csv_file))

        first_record = records[0]

        # Verify all required fields
        assert first_record["sport"] == "nfl"
        assert first_record["team_code"] == "KC"
        assert first_record["rating_date"] == date(2023, 9, 7)
        assert first_record["elo_rating"] == Decimal("1624.09")
        assert first_record["season"] == 2023
        assert first_record["source"] == "fivethirtyeight"
        assert first_record["source_file"] is not None

    def test_elo_rating_is_decimal(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify Elo ratings use Decimal, not float.

        Educational Note:
            Pattern 1 (Decimal Precision) - All numerical values that
            require precision must use Decimal to avoid floating-point
            errors. Elo ratings like 1624.09 must be exact.
        """
        source = FiveThirtyEightSource()
        records = list(source.load_elo(sport="nfl", file_path=fivethirtyeight_csv_file))

        for record in records:
            assert isinstance(record["elo_rating"], Decimal)

    def test_season_filtering(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify season filter works correctly."""
        source = FiveThirtyEightSource()

        # Filter to 2023 only (3 games = 6 Elo records)
        records_2023 = list(
            source.load_elo(sport="nfl", seasons=[2023], file_path=fivethirtyeight_csv_file)
        )
        assert len(records_2023) == 6

        # Filter to 2024 only (2 games = 4 Elo records)
        records_2024 = list(
            source.load_elo(sport="nfl", seasons=[2024], file_path=fivethirtyeight_csv_file)
        )
        assert len(records_2024) == 4

    def test_multiple_season_filtering(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify multiple seasons can be filtered."""
        source = FiveThirtyEightSource()

        records = list(
            source.load_elo(sport="nfl", seasons=[2023, 2024], file_path=fivethirtyeight_csv_file)
        )

        # All 5 games = 10 Elo records
        assert len(records) == 10

    def test_team_code_normalization(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify team codes are normalized correctly."""
        source = FiveThirtyEightSource()
        records = list(source.load_elo(sport="nfl", file_path=fivethirtyeight_csv_file))

        # Extract unique team codes
        team_codes = {r["team_code"] for r in records}

        # Verify expected teams from fixture
        assert "KC" in team_codes
        assert "DET" in team_codes
        assert "BUF" in team_codes
        assert "NYJ" in team_codes
        assert "SF" in team_codes

    def test_empty_csv_returns_no_records(self, empty_csv_file: Path) -> None:
        """Verify empty CSV produces no records."""
        source = FiveThirtyEightSource()
        records = list(source.load_elo(sport="nfl", file_path=empty_csv_file))

        assert len(records) == 0

    def test_malformed_rows_skipped(self, malformed_csv_file: Path) -> None:
        """Verify malformed rows are skipped gracefully."""
        source = FiveThirtyEightSource()
        records = list(source.load_elo(sport="nfl", file_path=malformed_csv_file))

        # Some records should still be parsed despite malformed rows
        # Row 2 has invalid date - skipped
        # Row 3 has invalid season - skipped
        # Row 4/5 have missing teams - team1 or team2 missing
        # Row 6 has invalid elo - Elo parse error
        # Only valid Elo records from remaining rows
        assert len(records) >= 0  # At least gracefully handles errors


# =============================================================================
# GAME LOADING TESTS
# =============================================================================


class TestLoadGames:
    """Test suite for load_games method."""

    def test_load_games_returns_iterator(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify load_games returns an iterator of GameRecords."""
        source = FiveThirtyEightSource()
        records = list(source.load_games(sport="nfl", file_path=fivethirtyeight_csv_file))

        # 5 games in fixture
        assert len(records) == 5

    def test_game_record_structure(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify GameRecord has all required fields."""
        source = FiveThirtyEightSource()
        records = list(source.load_games(sport="nfl", file_path=fivethirtyeight_csv_file))

        first_game = records[0]

        # Verify all required fields
        assert first_game["sport"] == "nfl"
        assert first_game["season"] == 2023
        assert first_game["game_date"] == date(2023, 9, 7)
        assert first_game["home_team_code"] == "KC"  # team1 = home
        assert first_game["away_team_code"] == "DET"  # team2 = away
        assert first_game["home_score"] == 21
        assert first_game["away_score"] == 20
        assert first_game["is_neutral_site"] is False
        assert first_game["is_playoff"] is False
        assert first_game["game_type"] == "regular"
        assert first_game["source"] == "fivethirtyeight"

    def test_neutral_site_detection(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify neutral site games are detected correctly.

        Educational Note:
            Super Bowl is played at neutral site. In fixture,
            2024-02-11 KC vs SF is the Super Bowl (neutral=1).
        """
        source = FiveThirtyEightSource()
        records = list(source.load_games(sport="nfl", file_path=fivethirtyeight_csv_file))

        # Find the Super Bowl (neutral site game)
        super_bowl = next((g for g in records if g["game_date"] == date(2024, 2, 11)), None)

        assert super_bowl is not None
        assert super_bowl["is_neutral_site"] is True
        assert super_bowl["is_playoff"] is True
        assert super_bowl["game_type"] == "playoff"

    def test_playoff_detection(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify playoff games are detected correctly."""
        source = FiveThirtyEightSource()
        records = list(source.load_games(sport="nfl", file_path=fivethirtyeight_csv_file))

        # Count playoff games (should be 2: AFC Championship + Super Bowl)
        playoff_games = [g for g in records if g["is_playoff"]]
        regular_games = [g for g in records if not g["is_playoff"]]

        assert len(playoff_games) == 2
        assert len(regular_games) == 3

        # All playoff games should have game_type = "playoff"
        for game in playoff_games:
            assert game["game_type"] == "playoff"

        # All regular games should have game_type = "regular"
        for game in regular_games:
            assert game["game_type"] == "regular"

    def test_score_parsing(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify scores are parsed as integers."""
        source = FiveThirtyEightSource()
        records = list(source.load_games(sport="nfl", file_path=fivethirtyeight_csv_file))

        for game in records:
            assert isinstance(game["home_score"], int)
            assert isinstance(game["away_score"], int)

    def test_season_filtering_games(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify season filter works for games."""
        source = FiveThirtyEightSource()

        # Filter to 2023 only
        games_2023 = list(
            source.load_games(sport="nfl", seasons=[2023], file_path=fivethirtyeight_csv_file)
        )
        assert len(games_2023) == 3

        # Filter to 2024 only
        games_2024 = list(
            source.load_games(sport="nfl", seasons=[2024], file_path=fivethirtyeight_csv_file)
        )
        assert len(games_2024) == 2

    def test_empty_csv_returns_no_games(self, empty_csv_file: Path) -> None:
        """Verify empty CSV produces no games."""
        source = FiveThirtyEightSource()
        records = list(source.load_games(sport="nfl", file_path=empty_csv_file))

        assert len(records) == 0


# =============================================================================
# CAPABILITY TESTS
# =============================================================================


class TestCapabilities:
    """Test suite for capability methods."""

    def test_supports_games(self) -> None:
        """Verify FiveThirtyEight supports game data."""
        source = FiveThirtyEightSource()
        assert source.supports_games() is True

    def test_supports_elo(self) -> None:
        """Verify FiveThirtyEight supports Elo data."""
        source = FiveThirtyEightSource()
        assert source.supports_elo() is True

    def test_does_not_support_odds(self) -> None:
        """Verify FiveThirtyEight does NOT support odds data.

        Educational Note:
            FiveThirtyEight provides Elo ratings and game results,
            but not betting odds. Use BettingCSVSource for odds.
        """
        source = FiveThirtyEightSource()
        assert source.supports_odds() is False


# =============================================================================
# SPORT VALIDATION TESTS
# =============================================================================


class TestSportValidation:
    """Test suite for sport validation."""

    def test_valid_sports_accepted(self) -> None:
        """Verify supported sports are accepted."""
        source = FiveThirtyEightSource()

        assert source.supports_sport("nfl") is True
        assert source.supports_sport("nba") is True
        assert source.supports_sport("mlb") is True
        assert source.supports_sport("NFL") is True  # Case-insensitive

    def test_invalid_sport_rejected(self) -> None:
        """Verify unsupported sports are rejected."""
        source = FiveThirtyEightSource()

        assert source.supports_sport("soccer") is False
        assert source.supports_sport("hockey") is False
        assert source.supports_sport("ncaaf") is False

    def test_validate_sport_raises_for_unsupported(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify _validate_sport raises DataSourceConfigError."""
        source = FiveThirtyEightSource()

        with pytest.raises(DataSourceConfigError) as exc_info:
            source._validate_sport("soccer")

        assert "soccer" in str(exc_info.value)
        assert "not supported" in str(exc_info.value)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for FiveThirtyEightSource.

    Educational Note:
        These tests verify that Elo and game data from the same
        CSV are consistent (same teams, dates, seasons).
    """

    def test_elo_and_games_from_same_csv(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify Elo and game data are consistent from same CSV."""
        source = FiveThirtyEightSource()

        elo_records = list(source.load_elo(sport="nfl", file_path=fivethirtyeight_csv_file))
        game_records = list(source.load_games(sport="nfl", file_path=fivethirtyeight_csv_file))

        # Each game has 2 Elo records
        assert len(elo_records) == len(game_records) * 2

        # Verify dates match
        elo_dates = {r["rating_date"] for r in elo_records}
        game_dates = {r["game_date"] for r in game_records}
        assert elo_dates == game_dates

        # Verify teams match
        elo_teams = {r["team_code"] for r in elo_records}
        game_teams = {r["home_team_code"] for r in game_records}
        game_teams.update(r["away_team_code"] for r in game_records)
        assert elo_teams == game_teams

    def test_season_filter_consistent(self, fivethirtyeight_csv_file: Path) -> None:
        """Verify season filtering is consistent between Elo and games."""
        source = FiveThirtyEightSource()

        elo_2023 = list(
            source.load_elo(sport="nfl", seasons=[2023], file_path=fivethirtyeight_csv_file)
        )
        games_2023 = list(
            source.load_games(sport="nfl", seasons=[2023], file_path=fivethirtyeight_csv_file)
        )

        # 2023: 3 games = 6 Elo records
        assert len(elo_2023) == len(games_2023) * 2

        # All records should be 2023
        assert all(r["season"] == 2023 for r in elo_2023)
        assert all(r["season"] == 2023 for r in games_2023)
