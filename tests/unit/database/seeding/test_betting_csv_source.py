"""
Unit Tests for Betting CSV Data Source Adapter.

Tests the BettingCSVSource class for loading historical betting odds
from CSV files (e.g., NFL Betting Data from slieb74/NFL-Betting-Data).

Tests follow the project's testing patterns:
- Pattern 1: Decimal precision (spreads/totals use Decimal)
- Pattern 7: Educational docstrings
- Temp files for CSV fixture data

Related:
- ADR-106: Historical Data Collection Architecture
- Issue #229: Expanded Historical Data Sources
- Migration 0007: historical_odds table

Usage:
    pytest tests/unit/database/seeding/test_betting_csv_source.py -v
"""

import tempfile
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from precog.database.seeding.sources.base_source import DataSourceConfigError
from precog.database.seeding.sources.betting_csv import (
    BettingCSVSource,
    normalize_team_name_to_code,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def betting_csv_content() -> str:
    """Sample NFL betting CSV content.

    Educational Note:
        This CSV format comes from slieb74/NFL-Betting-Data on GitHub/Kaggle.
        Key columns:
        - team_home/team_away: Full team names
        - spread_favorite: Point spread (negative for favorite)
        - team_favorite_id: Which team is favored
        - over_under_line: Total line
    """
    return """schedule_date,schedule_season,schedule_week,team_home,team_away,team_favorite_id,spread_favorite,over_under_line,score_home,score_away,home_favorite,favorite_covered,over_under_result
09/07/2023,2023,1,Kansas City Chiefs,Detroit Lions,KC,-3.5,53.5,21,20,1,1,under
09/10/2023,2023,1,Buffalo Bills,New York Jets,BUF,-6.5,42.0,22,16,1,1,under
09/10/2023,2023,1,Cleveland Browns,Cincinnati Bengals,CIN,-3.0,46.5,24,3,0,0,under
01/13/2024,2023,WildCard,Dallas Cowboys,Green Bay Packers,DAL,-7.0,49.5,32,48,1,0,over
"""


@pytest.fixture
def betting_csv_file(betting_csv_content: str) -> Path:
    """Create a temporary betting CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(betting_csv_content)
        return Path(f.name)


@pytest.fixture
def betting_csv_dir(betting_csv_content: str) -> Iterator[Path]:
    """Create a temp directory with properly named betting CSV.

    Educational Note:
        BettingCSVSource expects files named nfl_betting.csv by default.
        This fixture creates the file with the correct name.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "nfl_betting.csv"
        csv_path.write_text(betting_csv_content, encoding="utf-8")
        yield Path(temp_dir)


# =============================================================================
# TEAM NAME MAPPING TESTS
# =============================================================================


class TestTeamNameMapping:
    """Test suite for NFL team name to code mapping."""

    def test_current_team_name_mapping(self) -> None:
        """Verify current team names map to correct codes."""
        assert normalize_team_name_to_code("Kansas City Chiefs") == "KC"
        assert normalize_team_name_to_code("Buffalo Bills") == "BUF"
        assert normalize_team_name_to_code("New York Giants") == "NYG"
        assert normalize_team_name_to_code("New York Jets") == "NYJ"
        assert normalize_team_name_to_code("Los Angeles Chargers") == "LAC"
        assert normalize_team_name_to_code("Los Angeles Rams") == "LAR"

    def test_historical_team_name_mapping(self) -> None:
        """Verify historical team names map to current codes.

        Educational Note:
            NFL teams have relocated and renamed over the years.
            Historical data will have old names that need to map
            to current team codes:
            - Oakland Raiders -> LV (Las Vegas Raiders)
            - San Diego Chargers -> LAC (Los Angeles Chargers)
            - Washington Redskins -> WAS (Washington Commanders)
        """
        # Relocated teams
        assert normalize_team_name_to_code("Oakland Raiders") == "LV"
        assert normalize_team_name_to_code("San Diego Chargers") == "LAC"
        assert normalize_team_name_to_code("St. Louis Rams") == "LAR"
        assert normalize_team_name_to_code("Baltimore Colts") == "IND"

        # Renamed teams
        assert normalize_team_name_to_code("Washington Redskins") == "WAS"
        assert normalize_team_name_to_code("Washington Football Team") == "WAS"
        assert normalize_team_name_to_code("Washington Commanders") == "WAS"

    def test_unknown_team_returns_none(self) -> None:
        """Verify unknown team names return None."""
        assert normalize_team_name_to_code("Unknown Team") is None
        assert normalize_team_name_to_code("") is None
        assert normalize_team_name_to_code("Not A Team") is None

    def test_whitespace_handling(self) -> None:
        """Verify whitespace is stripped from team names."""
        assert normalize_team_name_to_code("  Kansas City Chiefs  ") == "KC"
        assert normalize_team_name_to_code("\tBuffalo Bills\n") == "BUF"

    def test_all_32_current_teams_mapped(self) -> None:
        """Verify all 32 current NFL teams are in the mapping.

        Educational Note:
            As of 2024, the NFL has 32 teams. This test ensures
            we haven't missed any current teams in the mapping.
        """
        current_teams = [
            "Arizona Cardinals",
            "Atlanta Falcons",
            "Baltimore Ravens",
            "Buffalo Bills",
            "Carolina Panthers",
            "Chicago Bears",
            "Cincinnati Bengals",
            "Cleveland Browns",
            "Dallas Cowboys",
            "Denver Broncos",
            "Detroit Lions",
            "Green Bay Packers",
            "Houston Texans",
            "Indianapolis Colts",
            "Jacksonville Jaguars",
            "Kansas City Chiefs",
            "Las Vegas Raiders",
            "Los Angeles Chargers",
            "Los Angeles Rams",
            "Miami Dolphins",
            "Minnesota Vikings",
            "New England Patriots",
            "New Orleans Saints",
            "New York Giants",
            "New York Jets",
            "Philadelphia Eagles",
            "Pittsburgh Steelers",
            "San Francisco 49ers",
            "Seattle Seahawks",
            "Tampa Bay Buccaneers",
            "Tennessee Titans",
            "Washington Commanders",
        ]

        for team in current_teams:
            code = normalize_team_name_to_code(team)
            assert code is not None, f"Missing mapping for: {team}"
            assert len(code) <= 3, f"Invalid code for {team}: {code}"


# =============================================================================
# BETTING CSV SOURCE INITIALIZATION TESTS
# =============================================================================


class TestBettingCSVSourceInit:
    """Test suite for BettingCSVSource initialization."""

    def test_source_name_is_betting_csv(self) -> None:
        """Verify source name is set correctly."""
        source = BettingCSVSource()
        assert source.source_name == "betting_csv"
        assert source.name == "betting_csv"

    def test_supported_sports_includes_nfl(self) -> None:
        """Verify NFL is in supported sports."""
        source = BettingCSVSource()
        assert "nfl" in source.supported_sports
        assert source.supports_sport("nfl")
        assert source.supports_sport("NFL")  # Case-insensitive

    def test_unsupported_sport_fails(self) -> None:
        """Verify unsupported sport raises error."""
        source = BettingCSVSource()
        assert not source.supports_sport("nba")
        assert not source.supports_sport("mlb")

    def test_default_data_dir(self) -> None:
        """Verify default data directory is set."""
        source = BettingCSVSource()
        assert source.data_dir == Path("data/historical")

    def test_custom_data_dir(self) -> None:
        """Verify custom data directory is used."""
        custom_dir = Path("/custom/data")
        source = BettingCSVSource(data_dir=custom_dir)
        assert source.data_dir == custom_dir

    def test_capabilities(self) -> None:
        """Verify capability methods return correct values."""
        source = BettingCSVSource()
        assert source.supports_games() is True
        assert source.supports_odds() is True
        assert source.supports_elo() is False


# =============================================================================
# ODDS LOADING TESTS
# =============================================================================


class TestBettingCSVLoadOdds:
    """Test suite for load_odds functionality."""

    def test_load_odds_returns_iterator(self, betting_csv_file: Path) -> None:
        """Verify load_odds returns an iterator."""
        source = BettingCSVSource()
        result = source.load_odds(file_path=betting_csv_file)
        assert hasattr(result, "__iter__")

    def test_load_odds_parses_all_records(self, betting_csv_file: Path) -> None:
        """Verify all valid records are parsed."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))
        assert len(odds) == 4  # 4 games in fixture

    def test_load_odds_team_codes_correct(self, betting_csv_file: Path) -> None:
        """Verify team names are converted to codes."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # First game: KC vs DET
        assert odds[0]["home_team_code"] == "KC"
        assert odds[0]["away_team_code"] == "DET"

        # Second game: BUF vs NYJ
        assert odds[1]["home_team_code"] == "BUF"
        assert odds[1]["away_team_code"] == "NYJ"

    def test_load_odds_spread_uses_decimal(self, betting_csv_file: Path) -> None:
        """Verify spreads use Decimal, not float.

        Educational Note:
            Pattern 1 (Decimal Precision) - All betting values must
            use Decimal to avoid floating-point errors that could
            affect CLV calculations.
        """
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # KC was home favorite at -3.5
        assert isinstance(odds[0]["spread_home_close"], Decimal)
        assert odds[0]["spread_home_close"] == Decimal("-3.5")

    def test_load_odds_total_uses_decimal(self, betting_csv_file: Path) -> None:
        """Verify totals use Decimal, not float."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        assert isinstance(odds[0]["total_close"], Decimal)
        assert odds[0]["total_close"] == Decimal("53.5")

    def test_load_odds_spread_conversion_home_favorite(self, betting_csv_file: Path) -> None:
        """Verify spread is correct when home team is favorite.

        Educational Note:
            The CSV has spread_favorite (e.g., -3.5) and home_favorite (1/0).
            When home_favorite=1, spread_home_close should be negative
            (home is favored by that amount).
        """
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # KC vs DET: KC was home and favorite at -3.5
        kc_odds = odds[0]
        assert kc_odds["home_team_code"] == "KC"
        assert kc_odds["spread_home_close"] == Decimal("-3.5")

    def test_load_odds_spread_conversion_away_favorite(self, betting_csv_file: Path) -> None:
        """Verify spread is flipped when away team is favorite.

        Educational Note:
            When home_favorite=0, the spread needs to be flipped.
            If spread_favorite=-3.0 and away is favorite,
            spread_home_close should be +3.0 (home is underdog).
        """
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # CLE vs CIN: CIN (away) was favorite at -3.0
        cle_odds = odds[2]
        assert cle_odds["home_team_code"] == "CLE"
        assert cle_odds["away_team_code"] == "CIN"
        # Since CIN (away) was favorite at -3.0, CLE (home) spread is +3.0
        assert cle_odds["spread_home_close"] == Decimal("3.0")

    def test_load_odds_home_covered_home_favorite(self, betting_csv_file: Path) -> None:
        """Verify home_covered when home team was favorite.

        Educational Note:
            If home was favorite and favorite_covered=1, then home_covered=True.
            KC -3.5 won 21-20 (margin=1), didn't cover -3.5, but fixture says covered.
        """
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # KC vs DET: home_favorite=1, favorite_covered=1
        assert odds[0]["home_covered"] is True

    def test_load_odds_home_covered_away_favorite(self, betting_csv_file: Path) -> None:
        """Verify home_covered when away team was favorite.

        Educational Note:
            If away was favorite and favorite_covered=0, then home_covered=True
            (because home (underdog) covered by favorite not covering).
        """
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # CLE vs CIN: home_favorite=0, favorite_covered=0
        # CIN was favorite and didn't cover, so home (CLE) covered
        assert odds[2]["home_covered"] is True

    def test_load_odds_game_went_over(self, betting_csv_file: Path) -> None:
        """Verify game_went_over is parsed correctly."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        # KC vs DET: over_under_result=under
        assert odds[0]["game_went_over"] is False

        # DAL vs GB: over_under_result=over
        assert odds[3]["game_went_over"] is True

    def test_load_odds_date_parsing(self, betting_csv_file: Path) -> None:
        """Verify dates are parsed correctly."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        assert odds[0]["game_date"] == date(2023, 9, 7)
        assert odds[1]["game_date"] == date(2023, 9, 10)
        assert odds[3]["game_date"] == date(2024, 1, 13)

    def test_load_odds_season_filter(self, betting_csv_file: Path) -> None:
        """Verify season filtering works."""
        source = BettingCSVSource()

        # Filter to 2023 only (excludes the 2024 playoff game)
        # Note: schedule_season is still 2023 for the playoff game in our fixture
        odds = list(source.load_odds(file_path=betting_csv_file, seasons=[2023]))
        assert len(odds) == 4  # All games in fixture are 2023 season

    def test_load_odds_source_metadata(self, betting_csv_file: Path) -> None:
        """Verify source metadata is set correctly."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))

        assert odds[0]["source"] == "betting_csv"
        assert odds[0]["source_file"] == betting_csv_file.name
        assert odds[0]["sportsbook"] == "consensus"

    def test_load_odds_validates_sport(self, betting_csv_file: Path) -> None:
        """Verify unsupported sport raises error."""
        source = BettingCSVSource()

        with pytest.raises(DataSourceConfigError) as exc_info:
            list(source.load_odds(sport="nba", file_path=betting_csv_file))

        assert "nba" in str(exc_info.value).lower()
        assert "not supported" in str(exc_info.value).lower()


# =============================================================================
# GAMES LOADING TESTS
# =============================================================================


class TestBettingCSVLoadGames:
    """Test suite for load_games functionality."""

    def test_load_games_returns_iterator(self, betting_csv_file: Path) -> None:
        """Verify load_games returns an iterator."""
        source = BettingCSVSource()
        result = source.load_games(file_path=betting_csv_file)
        assert hasattr(result, "__iter__")

    def test_load_games_parses_all_records(self, betting_csv_file: Path) -> None:
        """Verify all valid records are parsed."""
        source = BettingCSVSource()
        games = list(source.load_games(file_path=betting_csv_file))
        assert len(games) == 4

    def test_load_games_scores_correct(self, betting_csv_file: Path) -> None:
        """Verify scores are parsed correctly."""
        source = BettingCSVSource()
        games = list(source.load_games(file_path=betting_csv_file))

        # KC vs DET: 21-20
        assert games[0]["home_score"] == 21
        assert games[0]["away_score"] == 20

        # DAL vs GB: 32-48
        assert games[3]["home_score"] == 32
        assert games[3]["away_score"] == 48

    def test_load_games_playoff_detection(self, betting_csv_file: Path) -> None:
        """Verify playoff games are detected correctly."""
        source = BettingCSVSource()
        games = list(source.load_games(file_path=betting_csv_file))

        # Regular season games
        assert games[0]["is_playoff"] is False
        assert games[0]["game_type"] == "regular"

        # Wildcard playoff game
        assert games[3]["is_playoff"] is True
        assert games[3]["game_type"] == "playoff"

    def test_load_games_source_metadata(self, betting_csv_file: Path) -> None:
        """Verify source metadata is set correctly."""
        source = BettingCSVSource()
        games = list(source.load_games(file_path=betting_csv_file))

        assert games[0]["source"] == "betting_csv"
        assert games[0]["source_file"] == betting_csv_file.name


# =============================================================================
# FILE PATH HANDLING TESTS
# =============================================================================


class TestBettingCSVFilePaths:
    """Test suite for file path handling."""

    def test_missing_file_raises_error(self) -> None:
        """Verify missing file raises DataSourceConfigError."""
        source = BettingCSVSource(data_dir=Path("/nonexistent"))

        with pytest.raises(DataSourceConfigError) as exc_info:
            list(source.load_odds())

        assert "not found" in str(exc_info.value).lower()

    def test_explicit_file_path_works(self, betting_csv_file: Path) -> None:
        """Verify explicit file_path parameter works."""
        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=betting_csv_file))
        assert len(odds) == 4

    def test_default_file_from_data_dir(self, betting_csv_dir: Path) -> None:
        """Verify default file lookup works with proper directory."""
        source = BettingCSVSource(data_dir=betting_csv_dir)
        odds = list(source.load_odds())
        assert len(odds) == 4


# =============================================================================
# EDGE CASES
# =============================================================================


class TestBettingCSVEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_csv_returns_empty(self) -> None:
        """Verify empty CSV returns empty iterator."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            # Just header, no data
            f.write(
                "schedule_date,schedule_season,team_home,team_away,"
                "spread_favorite,over_under_line\n"
            )
            csv_path = Path(f.name)

        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=csv_path))
        assert len(odds) == 0

    def test_unknown_team_skipped(self) -> None:
        """Verify rows with unknown teams are skipped."""
        csv_content = """schedule_date,schedule_season,team_home,team_away,spread_favorite,over_under_line,home_favorite
09/07/2023,2023,Unknown Team,Detroit Lions,-3.5,53.5,1
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=csv_path))
        assert len(odds) == 0  # Unknown team skipped

    def test_invalid_date_skipped(self) -> None:
        """Verify rows with invalid dates are skipped."""
        csv_content = """schedule_date,schedule_season,team_home,team_away,spread_favorite,over_under_line,home_favorite
invalid_date,2023,Kansas City Chiefs,Detroit Lions,-3.5,53.5,1
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=csv_path))
        assert len(odds) == 0  # Invalid date skipped

    def test_iso_date_format_works(self) -> None:
        """Verify ISO date format (YYYY-MM-DD) is also supported."""
        csv_content = """schedule_date,schedule_season,team_home,team_away,spread_favorite,over_under_line,home_favorite,favorite_covered
2023-09-07,2023,Kansas City Chiefs,Detroit Lions,-3.5,53.5,1,1
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            csv_path = Path(f.name)

        source = BettingCSVSource()
        odds = list(source.load_odds(file_path=csv_path))
        assert len(odds) == 1
        assert odds[0]["game_date"] == date(2023, 9, 7)
