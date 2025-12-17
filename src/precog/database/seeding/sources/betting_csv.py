"""
Betting CSV Historical Data Source Adapter.

Loads historical betting lines from CSV files such as the NFL Betting Data
dataset from Kaggle/GitHub.

Data Format (NFL Betting Data):
    - schedule_date: Game date (MM/DD/YYYY)
    - schedule_season: Season year
    - team_home, team_away: Full team names
    - team_favorite_id: Team code of favorite
    - spread_favorite: Point spread for favorite (negative)
    - over_under_line: Total line
    - score_home, score_away: Final scores
    - favorite_covered: 1 if favorite covered
    - over_under_result: "over" or "under"

Data Sources:
    - slieb74/NFL-Betting-Data (GitHub): 9,655 NFL games (1967-present)
    - Kaggle NFL datasets: Various formats

Related:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources
    - Migration 0007: historical_odds table
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from precog.database.seeding.sources.base_source import (
    BaseDataSource,
    DataSourceConfigError,
    FileBasedSourceMixin,
    GameRecord,
    OddsRecord,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Team Name to Code Mapping
# =============================================================================

# NFL team full names -> team codes
NFL_TEAM_NAME_TO_CODE: dict[str, str] = {
    # Current teams
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
    # Historical team names/locations
    "Oakland Raiders": "LV",  # Moved to Las Vegas 2020
    "San Diego Chargers": "LAC",  # Moved to LA 2017
    "St. Louis Rams": "LAR",  # Moved to LA 2016
    "Houston Oilers": "TEN",  # Became Tennessee Titans
    "Tennessee Oilers": "TEN",  # Transition name
    "Baltimore Colts": "IND",  # Moved to Indianapolis 1984
    "Washington Redskins": "WAS",  # Renamed 2020
    "Washington Football Team": "WAS",  # Renamed 2022
    "Phoenix Cardinals": "ARI",  # Renamed 1994
    "St. Louis Cardinals": "ARI",  # Moved to Phoenix 1988
    "Boston Patriots": "NE",  # Renamed 1971
    "Los Angeles Raiders": "LV",  # Now Las Vegas
}


def normalize_team_name_to_code(team_name: str) -> str | None:
    """Convert full team name to team code.

    Args:
        team_name: Full team name (e.g., "Kansas City Chiefs")

    Returns:
        Team code (e.g., "KC") or None if not found
    """
    return NFL_TEAM_NAME_TO_CODE.get(team_name.strip())


class BettingCSVSource(FileBasedSourceMixin, BaseDataSource):
    """Betting CSV historical data source.

    Loads historical betting lines (spreads, totals) from CSV files.
    Supports the NFL Betting Data format from slieb74/NFL-Betting-Data.

    CSV Format Expected:
        - schedule_date: MM/DD/YYYY
        - schedule_season: Season year
        - team_home, team_away: Full team names
        - spread_favorite: Spread (negative for favorite)
        - over_under_line: Total line
        - score_home, score_away: Final scores
        - favorite_covered: 1/0
        - over_under_result: "over"/"under"

    Usage:
        >>> source = BettingCSVSource(data_dir=Path("data/historical"))
        >>> for odds in source.load_odds(sport="nfl", seasons=[2023]):
        ...     print(f"{odds['home_team_code']}: {odds['spread_home_close']}")

    Attributes:
        source_name: "betting_csv"
        supported_sports: ["nfl"]  # Currently NFL only

    Related:
        - ADR-106: Historical Data Collection Architecture
        - Migration 0007: historical_odds table
    """

    source_name = "betting_csv"
    supported_sports: ClassVar[list[str]] = ["nfl"]

    DEFAULT_FILES: ClassVar[dict[str, str]] = {
        "nfl": "nfl_betting.csv",
    }

    def __init__(
        self,
        data_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Betting CSV source.

        Args:
            data_dir: Directory containing betting CSV files
            **kwargs: Additional configuration
        """
        super().__init__(data_dir=data_dir, **kwargs)

    def _get_file_path(self, sport: str) -> Path:
        """Get the CSV file path for a sport."""
        filename = self.DEFAULT_FILES.get(sport.lower())
        if not filename:
            raise DataSourceConfigError(f"No betting data file for sport: {sport}")

        file_path = self.get_file_path(filename)
        self._validate_file_path(file_path)
        return file_path

    def _parse_date(self, date_str: str) -> date | None:
        """Parse date from various formats.

        Supports:
            - MM/DD/YYYY (NFL betting format)
            - YYYY-MM-DD (ISO format)
        """
        for fmt in ["%m/%d/%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(date_str, fmt).date()  # noqa: DTZ007
            except ValueError:
                continue
        return None

    # -------------------------------------------------------------------------
    # Odds Data Loading
    # -------------------------------------------------------------------------

    def load_odds(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        file_path: Path | None = None,
        **_kwargs: Any,
    ) -> Iterator[OddsRecord]:
        """Load historical odds from betting CSV.

        The NFL Betting Data format has:
        - spread_favorite: The spread (e.g., -13.5)
        - team_favorite_id: Which team is favored
        - over_under_line: The total

        We convert this to home team spread format.

        Args:
            sport: Sport code (nfl)
            seasons: Filter to specific seasons (None = all)
            file_path: Override CSV file path
            **kwargs: Additional options

        Yields:
            OddsRecord for each game's odds
        """
        self._validate_sport(sport)
        csv_path = file_path or self._get_file_path(sport)
        source_file = csv_path.name

        self._logger.info(
            "Loading betting odds: sport=%s, file=%s, seasons=%s", sport, csv_path, seasons
        )

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Parse season
                try:
                    season = int(row.get("schedule_season", "0"))
                except ValueError:
                    continue

                if seasons and season not in seasons:
                    continue

                # Parse date
                date_str = row.get("schedule_date", "")
                game_date = self._parse_date(date_str)
                if not game_date:
                    self._logger.warning("Invalid date: %s", date_str)
                    continue

                # Get team codes from full names
                home_name = row.get("team_home", "")
                away_name = row.get("team_away", "")
                home_team_code = normalize_team_name_to_code(home_name)
                away_team_code = normalize_team_name_to_code(away_name)

                if not home_team_code or not away_team_code:
                    self._logger.warning("Unknown team: home=%s, away=%s", home_name, away_name)
                    continue

                # Parse spread (convert to home team perspective)
                spread_favorite = row.get("spread_favorite", "")
                favorite_id = row.get("team_favorite_id", "")
                home_favorite = row.get("home_favorite", "")

                spread_home: Decimal | None = None
                if spread_favorite:
                    try:
                        spread_val = Decimal(spread_favorite)
                        # If home is favorite, spread is negative
                        # If away is favorite, flip the spread for home perspective
                        if home_favorite == "1" or favorite_id == home_team_code:
                            spread_home = spread_val  # Already home perspective
                        else:
                            spread_home = -spread_val  # Flip for home
                    except (ValueError, TypeError):
                        pass

                # Parse total
                total_line = row.get("over_under_line", "")
                total: Decimal | None = None
                if total_line:
                    try:
                        total = Decimal(total_line)
                    except (ValueError, TypeError):
                        pass

                # Parse results
                favorite_covered = row.get("favorite_covered", "")
                over_under_result = row.get("over_under_result", "")

                # Determine if home covered (depends on who was favorite)
                home_covered: bool | None = None
                if favorite_covered:
                    if home_favorite == "1" or favorite_id == home_team_code:
                        home_covered = favorite_covered == "1"
                    else:
                        # Away was favorite, so home covered = favorite didn't
                        home_covered = favorite_covered != "1"

                game_went_over = over_under_result.lower() == "over" if over_under_result else None

                yield OddsRecord(
                    sport=sport,
                    game_date=game_date,
                    home_team_code=home_team_code,
                    away_team_code=away_team_code,
                    sportsbook="consensus",  # Historical data is usually consensus
                    spread_home_open=None,  # Only have closing line
                    spread_home_close=spread_home,
                    spread_home_odds_open=None,
                    spread_home_odds_close=-110,  # Standard juice assumed
                    moneyline_home_open=None,
                    moneyline_home_close=None,  # Not in this dataset
                    moneyline_away_open=None,
                    moneyline_away_close=None,
                    total_open=None,
                    total_close=total,
                    over_odds_open=None,
                    over_odds_close=-110,  # Standard juice assumed
                    home_covered=home_covered,
                    game_went_over=game_went_over,
                    source=self.source_name,
                    source_file=source_file,
                )

    # -------------------------------------------------------------------------
    # Game Data Loading (from betting CSV)
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        file_path: Path | None = None,
        **_kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load game results from betting CSV.

        Betting CSVs often include final scores, so we can extract
        game results as well as odds.

        Args:
            sport: Sport code
            seasons: Filter to specific seasons
            file_path: Override CSV file path
            **kwargs: Additional options

        Yields:
            GameRecord for each game
        """
        self._validate_sport(sport)
        csv_path = file_path or self._get_file_path(sport)
        source_file = csv_path.name

        self._logger.info(
            "Loading games from betting CSV: sport=%s, file=%s, seasons=%s",
            sport,
            csv_path,
            seasons,
        )

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Parse season
                try:
                    season = int(row.get("schedule_season", "0"))
                except ValueError:
                    continue

                if seasons and season not in seasons:
                    continue

                # Parse date
                date_str = row.get("schedule_date", "")
                game_date = self._parse_date(date_str)
                if not game_date:
                    continue

                # Get team codes
                home_name = row.get("team_home", "")
                away_name = row.get("team_away", "")
                home_team_code = normalize_team_name_to_code(home_name)
                away_team_code = normalize_team_name_to_code(away_name)

                if not home_team_code or not away_team_code:
                    continue

                # Parse scores
                try:
                    score_home = row.get("score_home", "")
                    score_away = row.get("score_away", "")
                    home_score = int(score_home) if score_home else None
                    away_score = int(score_away) if score_away else None
                except ValueError:
                    home_score = None
                    away_score = None

                # Determine if playoff (week >= 18 or schedule_week contains "playoff")
                week = row.get("schedule_week", "")
                is_playoff = False
                try:
                    week_num = int(week)
                    is_playoff = week_num >= 18  # Regular season is weeks 1-17
                except ValueError:
                    if "playoff" in week.lower() or "wild" in week.lower():
                        is_playoff = True

                yield GameRecord(
                    sport=sport,
                    season=season,
                    game_date=game_date,
                    home_team_code=home_team_code,
                    away_team_code=away_team_code,
                    home_score=home_score,
                    away_score=away_score,
                    is_neutral_site=False,  # Regular games
                    is_playoff=is_playoff,
                    game_type="playoff" if is_playoff else "regular",
                    venue_name=None,
                    source=self.source_name,
                    source_file=source_file,
                    external_game_id=None,
                )

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """Betting CSV can provide game results."""
        return True

    def supports_odds(self) -> bool:
        """Betting CSV primarily provides odds data."""
        return True

    def supports_elo(self) -> bool:
        """Betting CSV does NOT provide Elo data."""
        return False
