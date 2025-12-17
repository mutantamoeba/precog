"""
NFL Data Py Source Adapter.

Provides access to NFL historical data through the nfl_data_py library.

nfl_data_py Library:
    A Python library that provides easy access to NFL data from nflfastR.
    Includes play-by-play data, schedules, rosters, and more.

    Installation: pip install nfl_data_py

    Repository: https://github.com/cooperdff/nfl_data_py
    Data Source: https://github.com/nflverse/nflfastR-data

Data Available:
    - Schedules (2000-present): Game dates, teams, final scores
    - Play-by-play (2000-present): Every play with details
    - Rosters (2000-present): Team rosters by season
    - Draft picks, combine data, etc.

Related:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from precog.database.seeding.sources.base_source import (
    APIBasedSourceMixin,
    BaseDataSource,
    DataSourceConnectionError,
    DataSourceError,
    GameRecord,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


# =============================================================================
# Team Code Mapping
# =============================================================================

# nfl_data_py uses different team codes in some cases
NFL_TEAM_CODE_MAPPING: dict[str, str] = {
    "LA": "LAR",  # nfl_data_py uses LA for Rams
    "JAC": "JAX",  # Jacksonville
    "LV": "LV",  # Las Vegas (correct)
    "OAK": "LV",  # Oakland -> Las Vegas
    "SD": "LAC",  # San Diego -> LA Chargers
    "STL": "LAR",  # St. Louis -> LA Rams
}


def normalize_nfl_team_code(code: str) -> str:
    """Normalize nfl_data_py team code to database format."""
    code = code.upper().strip()
    return NFL_TEAM_CODE_MAPPING.get(code, code)


class NFLDataPySource(APIBasedSourceMixin, BaseDataSource):
    """NFL Data Py historical data source.

    Loads NFL historical data using the nfl_data_py library.
    Provides schedules, game results, and other NFL data.

    Usage:
        >>> source = NFLDataPySource()
        >>> for game in source.load_games(seasons=[2023]):
        ...     print(f"{game['away_team_code']} @ {game['home_team_code']}")

    Attributes:
        source_name: "nfl_data_py"
        supported_sports: ["nfl"]

    Requirements:
        - nfl_data_py must be installed: pip install nfl_data_py

    Related:
        - ADR-106: Historical Data Collection Architecture
        - BaseDataSource: Abstract base class
    """

    source_name = "nfl_data_py"
    supported_sports: ClassVar[list[str]] = ["nfl"]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize NFL Data Py source.

        Args:
            **kwargs: Configuration options passed to base class

        Raises:
            DataSourceError: If nfl_data_py is not installed
        """
        super().__init__(**kwargs)
        self._nfl = None

    def _get_nfl_module(self):
        """Lazy load nfl_data_py module.

        Returns:
            The nfl_data_py module

        Raises:
            DataSourceError: If nfl_data_py is not installed
        """
        if self._nfl is None:
            try:
                import nfl_data_py as nfl

                self._nfl = nfl
            except ImportError as e:
                raise DataSourceError(
                    "nfl_data_py is not installed. Install with: pip install nfl_data_py"
                ) from e
        return self._nfl

    # -------------------------------------------------------------------------
    # Game Data Loading
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        **_kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load NFL game schedules and results.

        Uses nfl_data_py.import_schedules() to fetch game data.
        Returns completed games with final scores.

        Args:
            sport: Must be "nfl"
            seasons: List of seasons to load (e.g., [2022, 2023])
                     Default: current season only
            **kwargs: Additional options (unused)

        Yields:
            GameRecord for each completed game

        Raises:
            DataSourceConnectionError: If unable to fetch data

        Example:
            >>> source = NFLDataPySource()
            >>> games = list(source.load_games(seasons=[2023]))
            >>> len(games)
            272  # Regular season games
        """
        self._validate_sport(sport)

        if seasons is None:
            # Default to recent seasons
            current_year = datetime.now().year
            seasons = [current_year - 1, current_year]

        self._logger.info("Loading NFL games from nfl_data_py: seasons=%s", seasons)

        try:
            nfl = self._get_nfl_module()
            schedules = nfl.import_schedules(seasons)
        except Exception as e:
            raise DataSourceConnectionError(f"Failed to fetch NFL schedules: {e}") from e

        if schedules is None or len(schedules) == 0:
            self._logger.warning("No schedule data returned")
            return

        for _, row in schedules.iterrows():
            # Skip games without scores (not yet played)
            home_score = row.get("home_score")
            away_score = row.get("away_score")

            if home_score is None or away_score is None:
                continue

            # Parse date
            game_date_val = row.get("gameday")
            if game_date_val is None:
                continue

            # Convert to date object
            if hasattr(game_date_val, "date"):
                game_date = game_date_val.date()
            elif isinstance(game_date_val, str):
                try:
                    game_date = datetime.strptime(game_date_val, "%Y-%m-%d").date()  # noqa: DTZ007
                except ValueError:
                    continue
            else:
                continue

            # Get team codes
            home_team = normalize_nfl_team_code(str(row.get("home_team", "")))
            away_team = normalize_nfl_team_code(str(row.get("away_team", "")))

            if not home_team or not away_team:
                continue

            # Parse season
            season = int(row.get("season", 0))

            # Determine game type
            game_type_raw = str(row.get("game_type", "")).upper()
            is_playoff = game_type_raw not in ("REG", "")

            game_type: str | None = None
            if game_type_raw == "REG":
                game_type = "regular"
            elif game_type_raw == "WC":
                game_type = "wildcard"
            elif game_type_raw == "DIV":
                game_type = "divisional"
            elif game_type_raw == "CON":
                game_type = "conference"
            elif game_type_raw == "SB":
                game_type = "superbowl"
            elif game_type_raw:
                game_type = "playoff"

            # Check for neutral site
            location = str(row.get("location", ""))
            is_neutral_site = location.upper() == "NEUTRAL"

            # External game ID
            external_id = str(row.get("game_id", "")) or None

            yield GameRecord(
                sport="nfl",
                season=season,
                game_date=game_date,
                home_team_code=home_team,
                away_team_code=away_team,
                home_score=int(home_score),
                away_score=int(away_score),
                is_neutral_site=is_neutral_site,
                is_playoff=is_playoff,
                game_type=game_type,
                venue_name=str(row.get("stadium", "")) or None,
                source=self.source_name,
                source_file=None,
                external_game_id=external_id,
            )

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """nfl_data_py provides game/schedule data."""
        return True

    def supports_odds(self) -> bool:
        """nfl_data_py does NOT provide odds data directly."""
        return False

    def supports_elo(self) -> bool:
        """nfl_data_py does NOT provide Elo ratings."""
        return False
