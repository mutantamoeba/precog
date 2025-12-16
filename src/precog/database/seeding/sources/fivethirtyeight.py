"""
FiveThirtyEight Historical Data Source Adapter.

Provides access to FiveThirtyEight's historical Elo ratings and game results
for NFL, NBA, and MLB through CSV file parsing.

Data Available:
    - NFL Elo (1920-present): Game-by-game Elo with QB adjustments
    - NBA Elo (1946-present): Game-by-game Elo ratings
    - MLB Elo (1871-present): Game-by-game Elo ratings

Data Files:
    FiveThirtyEight Elo CSVs contain both Elo ratings AND game results:
    - date: Game date (YYYY-MM-DD)
    - season: Season year
    - team1, team2: Team abbreviations
    - elo1_pre, elo2_pre: Pre-game Elo ratings
    - score1, score2: Final scores (game results)
    - neutral: 1 if neutral site
    - playoff: 1 if playoff game

    This source extracts both Elo and game data from the same CSV.

File Sources:
    - Original API: https://projects.fivethirtyeight.com/nfl-api/nfl_elo.csv
      (Note: API defunct as of 2024, use archived copies)
    - GitHub archive: https://github.com/fivethirtyeight/nfl-elo-game

Related:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources
    - historical_elo_loader.py: Original Elo-specific loader
    - historical_games_loader.py: Original games-specific loader
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, ClassVar

# Import team code mapping from existing Elo loader
from precog.database.seeding.historical_elo_loader import (
    normalize_team_code,
)
from precog.database.seeding.sources.base_source import (
    BaseDataSource,
    DataSourceConfigError,
    EloRecord,
    FileBasedSourceMixin,
    GameRecord,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


class FiveThirtyEightSource(FileBasedSourceMixin, BaseDataSource):
    """FiveThirtyEight historical data source.

    Loads historical Elo ratings and game results from FiveThirtyEight
    CSV files for NFL, NBA, and MLB.

    Design Note:
        FiveThirtyEight stores Elo AND game data in the same CSV.
        The same file can be used to load either data type:
        - load_elo(): Extracts elo1_pre, elo2_pre columns
        - load_games(): Extracts score1, score2 columns

    Usage:
        >>> source = FiveThirtyEightSource(data_dir=Path("data/historical"))
        >>> # Load Elo ratings
        >>> for elo in source.load_elo(sport="nfl", seasons=[2023]):
        ...     print(f"{elo['team_code']}: {elo['elo_rating']}")
        >>> # Load game results
        >>> for game in source.load_games(sport="nfl", seasons=[2023]):
        ...     print(f"{game['home_team_code']} vs {game['away_team_code']}")

    Attributes:
        source_name: "fivethirtyeight"
        supported_sports: ["nfl", "nba", "mlb"]

    Related:
        - ADR-106: Historical Data Collection Architecture
        - historical_elo_loader.py: Uses same TEAM_CODE_MAPPING
    """

    source_name = "fivethirtyeight"
    supported_sports: ClassVar[list[str]] = ["nfl", "nba", "mlb"]

    # Default filenames by sport
    DEFAULT_FILES: ClassVar[dict[str, str]] = {
        "nfl": "nfl_elo.csv",
        "nba": "nba_elo.csv",
        "mlb": "mlb_elo.csv",
    }

    def __init__(
        self,
        data_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize FiveThirtyEight source.

        Args:
            data_dir: Directory containing FiveThirtyEight CSV files
                      Default: data/historical/
            **kwargs: Additional configuration
        """
        super().__init__(data_dir=data_dir, **kwargs)

    def _get_file_path(self, sport: str) -> Path:
        """Get the CSV file path for a sport.

        Args:
            sport: Sport code (nfl, nba, mlb)

        Returns:
            Path to the CSV file

        Raises:
            DataSourceConfigError: If file not found
        """
        filename = self.DEFAULT_FILES.get(sport.lower())
        if not filename:
            raise DataSourceConfigError(f"No default file for sport: {sport}")

        file_path = self.get_file_path(filename)
        self._validate_file_path(file_path)
        return file_path

    # -------------------------------------------------------------------------
    # Elo Data Loading
    # -------------------------------------------------------------------------

    def load_elo(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        file_path: Path | None = None,
        **_kwargs: Any,
    ) -> Iterator[EloRecord]:
        """Load historical Elo ratings from FiveThirtyEight CSV.

        Extracts pre-game Elo ratings (elo1_pre, elo2_pre) for each team
        from each game row. Each game yields two Elo records.

        Args:
            sport: Sport code (nfl, nba, mlb)
            seasons: Filter to specific seasons (None = all)
            file_path: Override CSV file path (default: auto-detect)
            **kwargs: Additional options (unused)

        Yields:
            EloRecord for each team in each game

        Example:
            >>> source = FiveThirtyEightSource()
            >>> for elo in source.load_elo("nfl", seasons=[2023]):
            ...     print(f"{elo['team_code']}: {elo['elo_rating']}")
        """
        self._validate_sport(sport)
        csv_path = file_path or self._get_file_path(sport)
        source_file = csv_path.name

        self._logger.info(
            "Loading FiveThirtyEight Elo: sport=%s, file=%s, seasons=%s", sport, csv_path, seasons
        )

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Parse season and filter
                try:
                    season = int(row.get("season", "0"))
                except ValueError:
                    continue

                if seasons and season not in seasons:
                    continue

                # Parse date
                try:
                    date_str = row.get("date", "")
                    rating_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
                except ValueError:
                    self._logger.warning("Invalid date in row: %s", row)
                    continue

                # Team 1 Elo
                team1_code = normalize_team_code(row.get("team1", ""))
                elo1_pre = row.get("elo1_pre") or row.get("elo1", "")

                if team1_code and elo1_pre:
                    try:
                        yield EloRecord(
                            sport=sport,
                            team_code=team1_code,
                            rating_date=rating_date,
                            elo_rating=Decimal(elo1_pre),
                            season=season,
                            source=self.source_name,
                            source_file=source_file,
                        )
                    except (ValueError, TypeError, InvalidOperation) as e:
                        self._logger.warning("Error parsing team1 Elo: %s - %s", row, e)

                # Team 2 Elo
                team2_code = normalize_team_code(row.get("team2", ""))
                elo2_pre = row.get("elo2_pre") or row.get("elo2", "")

                if team2_code and elo2_pre:
                    try:
                        yield EloRecord(
                            sport=sport,
                            team_code=team2_code,
                            rating_date=rating_date,
                            elo_rating=Decimal(elo2_pre),
                            season=season,
                            source=self.source_name,
                            source_file=source_file,
                        )
                    except (ValueError, TypeError, InvalidOperation) as e:
                        self._logger.warning("Error parsing team2 Elo: %s - %s", row, e)

    # -------------------------------------------------------------------------
    # Game Data Loading
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        file_path: Path | None = None,
        **_kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load historical game results from FiveThirtyEight CSV.

        Extracts game scores (score1, score2) and metadata from each row.
        FiveThirtyEight convention: team1 = home, team2 = away.

        Args:
            sport: Sport code (nfl, nba, mlb)
            seasons: Filter to specific seasons (None = all)
            file_path: Override CSV file path (default: auto-detect)
            **kwargs: Additional options (unused)

        Yields:
            GameRecord for each game

        Example:
            >>> source = FiveThirtyEightSource()
            >>> for game in source.load_games("nfl", seasons=[2023]):
            ...     print(f"{game['away_team_code']} @ {game['home_team_code']}")
        """
        self._validate_sport(sport)
        csv_path = file_path or self._get_file_path(sport)
        source_file = csv_path.name

        self._logger.info(
            "Loading FiveThirtyEight games: sport=%s, file=%s, seasons=%s", sport, csv_path, seasons
        )

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Parse season and filter
                try:
                    season = int(row.get("season", "0"))
                except ValueError:
                    continue

                if seasons and season not in seasons:
                    continue

                # Parse date
                try:
                    date_str = row.get("date", "")
                    game_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
                except ValueError:
                    self._logger.warning("Invalid date in row: %s", row)
                    continue

                # Extract team codes (team1 = home, team2 = away by convention)
                home_team_code = normalize_team_code(row.get("team1", ""))
                away_team_code = normalize_team_code(row.get("team2", ""))

                if not home_team_code or not away_team_code:
                    self._logger.warning("Missing team codes in row: %s", row)
                    continue

                # Parse scores
                try:
                    score1 = row.get("score1", "")
                    score2 = row.get("score2", "")
                    home_score = int(score1) if score1 else None
                    away_score = int(score2) if score2 else None
                except ValueError:
                    home_score = None
                    away_score = None

                # Parse game context
                neutral_str = row.get("neutral", "0")
                playoff_str = row.get("playoff", "0")
                is_neutral_site = neutral_str == "1"
                is_playoff = playoff_str == "1"

                # Determine game type
                game_type: str | None = "playoff" if is_playoff else "regular"

                yield GameRecord(
                    sport=sport,
                    season=season,
                    game_date=game_date,
                    home_team_code=home_team_code,
                    away_team_code=away_team_code,
                    home_score=home_score,
                    away_score=away_score,
                    is_neutral_site=is_neutral_site,
                    is_playoff=is_playoff,
                    game_type=game_type,
                    venue_name=None,
                    source=self.source_name,
                    source_file=source_file,
                    external_game_id=None,
                )

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """FiveThirtyEight supports game data."""
        return True

    def supports_elo(self) -> bool:
        """FiveThirtyEight supports Elo data."""
        return True

    def supports_odds(self) -> bool:
        """FiveThirtyEight does NOT provide odds data."""
        return False
