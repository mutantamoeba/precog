"""
NHL API Source Adapter.

Provides access to NHL historical data through the nhl-api-py library.

nhl-api-py Library:
    A Python library for fetching data from the official NHL API,
    providing game schedules, results, player stats, and team info.

    Installation: pip install nhl-api-py
    Repository: https://github.com/coreyjs/nhl-api-py

Key Data Available:
    - Game schedules and results (1917-present)
    - Player stats (goals, assists, points, etc.)
    - Team stats and standings
    - Playoff brackets

NHL Season Structure:
    NHL seasons span two calendar years (e.g., 2023-24 season).
    The season year is the starting year (2023 for 2023-24).
    - Regular season: October-April (~82 games per team)
    - Playoffs: April-June (best-of-7 series)
    - Stanley Cup Final: June

Related:
    - ADR-109: Elo Rating Computation Engine Architecture
    - Issue #273: Multi-sport Elo computation
    - team_history.py: NHL team relocation mappings
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from precog.database.seeding.sources.base_source import (
    APIBasedSourceMixin,
    BaseDataSource,
    DataSourceError,
    GameRecord,
)
from precog.database.seeding.team_history import resolve_team_code

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


# =============================================================================
# Team Code Mapping
# =============================================================================

# NHL API uses team abbreviations that may differ from our standard codes
NHL_API_TEAM_CODES: dict[str, str] = {
    # Team relocations handled by team_history.py
    # These are just abbreviation variants
    "PHX": "ARI",  # Phoenix Coyotes -> Arizona
    "ATL": "WPG",  # Atlanta Thrashers -> Winnipeg Jets (current)
    "HFD": "CAR",  # Hartford Whalers -> Carolina Hurricanes
    "QUE": "COL",  # Quebec Nordiques -> Colorado Avalanche
    "MNS": "DAL",  # Minnesota North Stars -> Dallas Stars
    "KCS": "NJD",  # Kansas City Scouts -> Colorado Rockies -> New Jersey Devils
    "CLR": "NJD",  # Colorado Rockies -> New Jersey Devils
    "AFM": "CGY",  # Atlanta Flames -> Calgary Flames
    # Abbreviation variants
    "SJS": "SJ",  # San Jose Sharks (NHL uses SJS, some sources use SJ)
    "TBL": "TB",  # Tampa Bay Lightning
    "LAK": "LA",  # Los Angeles Kings
    "NJD": "NJ",  # New Jersey Devils
    "WSH": "WAS",  # Washington Capitals
    # The old Winnipeg Jets (1972-1996) became Arizona Coyotes
    # The current Winnipeg Jets (2011-present) came from Atlanta Thrashers
    "WIN": "ARI",  # Old Winnipeg -> Arizona (use WPG for current Jets)
}


def normalize_nhl_team_code(code: str) -> str:
    """Normalize NHL team code to database format.

    Uses the unified team history module for relocation mappings,
    plus NHL API-specific abbreviation corrections.

    Args:
        code: Team code from NHL API

    Returns:
        Normalized team code for database lookup

    Example:
        >>> normalize_nhl_team_code("HFD")
        'CAR'
        >>> normalize_nhl_team_code("TOR")
        'TOR'
    """
    code = code.upper().strip()

    # First check NHL API-specific mappings
    if code in NHL_API_TEAM_CODES:
        return NHL_API_TEAM_CODES[code]

    # Then use unified team history for relocations
    return resolve_team_code("nhl", code)


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_nhl_date(date_str: str | None) -> datetime | None:
    """Parse NHL API date string to datetime.

    NHL API returns dates in ISO format.

    Args:
        date_str: Date string from NHL API

    Returns:
        Parsed datetime or None
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)  # noqa: DTZ007
        except ValueError:
            continue

    logger.warning("Could not parse NHL date: %s", date_str)
    return None


def _to_decimal(value: Any, precision: str = "0.0001") -> Decimal | None:
    """Convert a value to Decimal with specified precision."""
    if value is None:
        return None

    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return None

        dec = Decimal(str(value))
        return dec.quantize(Decimal(precision), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError):
        return None


# =============================================================================
# NHL API Source Adapter
# =============================================================================


class NHLApiSource(APIBasedSourceMixin, BaseDataSource):
    """NHL API historical data source.

    Loads NHL game data using the nhl-api-py library.
    Provides game schedules, results, and basic statistics.

    Usage:
        >>> source = NHLApiSource()
        >>> for game in source.load_games(seasons=[2023]):
        ...     print(f"{game['away_team_code']} @ {game['home_team_code']}")

    Attributes:
        source_name: "nhl_api"
        supported_sports: ["nhl"]

    Rate Limiting:
        The NHL API is relatively permissive but we still include
        delays to be respectful and avoid potential rate limits.

    Requirements:
        - nhl-api-py must be installed: pip install nhl-api-py

    Related:
        - ADR-109: Elo Rating Computation Engine
        - Issue #273: Multi-sport Elo computation
    """

    source_name = "nhl_api"
    supported_sports: ClassVar[list[str]] = ["nhl"]

    # Rate limiting: Be respectful of NHL API
    REQUEST_DELAY = 0.3  # 300ms between requests

    def __init__(self, **kwargs: Any) -> None:
        """Initialize NHL API source.

        Args:
            **kwargs: Configuration options passed to base class

        Raises:
            DataSourceError: If nhl-api-py is not installed
        """
        super().__init__(**kwargs)
        self._nhl_client = None
        self._last_request_time = 0.0

    def _get_nhl_client(self) -> Any:
        """Lazy load NHL API client.

        Returns:
            The NHL API client instance

        Raises:
            DataSourceError: If nhl-api-py is not installed
        """
        if self._nhl_client is None:
            try:
                from nhlpy import NHLClient

                self._nhl_client = NHLClient()
            except ImportError as e:
                raise DataSourceError(
                    "nhl-api-py is not installed. Install with: pip install nhl-api-py"
                ) from e
        return self._nhl_client

    def _rate_limit_wait(self) -> None:
        """Wait if necessary to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    # -------------------------------------------------------------------------
    # Game Data Loading
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nhl",
        seasons: list[int] | None = None,
        **_kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load NHL game schedules and results.

        Uses the NHL API to fetch game data.
        Returns completed games with final scores.

        Args:
            sport: Must be "nhl"
            seasons: List of seasons to load (e.g., [2022, 2023])
                     Season year is the start year (2023 = 2023-24 season)
                     Default: last 2 seasons
            **kwargs: Additional options (unused)

        Yields:
            GameRecord for each completed game

        Raises:
            DataSourceConnectionError: If unable to fetch data

        Example:
            >>> source = NHLApiSource()
            >>> games = list(source.load_games(seasons=[2023]))
            >>> len(games)
            ~1312  # Regular season games (82 games x 32 teams / 2)

        Educational Note:
            NHL seasons run October through April for regular season,
            with playoffs running April through June.
        """
        self._validate_sport(sport)

        if seasons is None:
            current_year = datetime.now().year
            # NHL season starts in October
            if datetime.now().month < 10:
                current_year -= 1
            seasons = [current_year - 1, current_year]

        self._logger.info("Loading NHL games from NHL API: seasons=%s", seasons)

        try:
            client = self._get_nhl_client()
        except DataSourceError:
            raise

        for season in seasons:
            # Format season string as NHL API expects
            season_str = f"{season}{season + 1}"  # e.g., "20232024"
            self._logger.info("Fetching season %d-%d", season, season + 1)

            # Fetch regular season schedule
            yield from self._fetch_season_games(client, season, season_str, "02")

            # Fetch playoff games
            yield from self._fetch_season_games(client, season, season_str, "03")

    def _fetch_season_games(
        self,
        client: Any,
        season: int,
        season_str: str,
        game_type: str,
    ) -> Iterator[GameRecord]:
        """Fetch games for a specific season and game type.

        Args:
            client: NHL API client
            season: Season start year
            season_str: Season string (e.g., "20232024")
            game_type: "02" for regular season, "03" for playoffs

        Yields:
            GameRecord for each completed game
        """
        is_playoff = game_type == "03"
        game_type_name = "playoffs" if is_playoff else "regular season"

        try:
            self._rate_limit_wait()

            # Use the schedule endpoint
            # The nhl-api-py library provides schedule access
            schedule = client.schedule.get_schedule(season=season_str)

            if not schedule:
                self._logger.warning("No schedule data for %s %s", season_str, game_type_name)
                return

            # Parse schedule data
            # Structure depends on nhl-api-py version
            games = schedule.get("dates", []) if isinstance(schedule, dict) else []

            for date_entry in games:
                date_games = date_entry.get("games", [])
                for game in date_games:
                    try:
                        game_record = self._parse_game(game, season, is_playoff)
                        if game_record:
                            yield game_record
                    except Exception as e:
                        self._logger.warning("Error parsing game: %s", e)
                        continue

        except Exception as e:
            self._logger.error("Failed to fetch %s for %s: %s", game_type_name, season_str, e)
            # Don't raise for individual seasons, continue with others

    def _parse_game(
        self,
        game: dict[str, Any],
        season: int,
        is_playoff: bool,
    ) -> GameRecord | None:
        """Parse a single game from NHL API response.

        Args:
            game: Game data dict from API
            season: Season year
            is_playoff: Whether this is a playoff game

        Returns:
            GameRecord or None if game is incomplete
        """
        # Check game status - only process completed games
        game_state = game.get("gameState", "")
        if game_state not in ("FINAL", "OFF"):
            return None

        # Get teams
        home_team_data = game.get("homeTeam", {})
        away_team_data = game.get("awayTeam", {})

        home_team_abbrev = home_team_data.get("abbrev", "")
        away_team_abbrev = away_team_data.get("abbrev", "")

        if not home_team_abbrev or not away_team_abbrev:
            return None

        home_team = normalize_nhl_team_code(home_team_abbrev)
        away_team = normalize_nhl_team_code(away_team_abbrev)

        # Get scores
        home_score = home_team_data.get("score")
        away_score = away_team_data.get("score")

        if home_score is None or away_score is None:
            return None

        # Get game date
        game_date_str = game.get("gameDate")
        game_date_dt = _parse_nhl_date(game_date_str)
        if not game_date_dt:
            return None

        game_date = game_date_dt.date()

        # External game ID
        external_id = str(game.get("id", "")) or None

        # Venue
        venue = game.get("venue", {})
        venue_name = venue.get("default") if isinstance(venue, dict) else None

        return GameRecord(
            sport="nhl",
            season=season,
            game_date=game_date,
            home_team_code=home_team,
            away_team_code=away_team,
            home_score=int(home_score),
            away_score=int(away_score),
            is_neutral_site=False,  # NHL rarely plays neutral site games
            is_playoff=is_playoff,
            game_type="playoff" if is_playoff else "regular",
            venue_name=venue_name,
            source=self.source_name,
            source_file=None,
            external_game_id=external_id,
        )

    # -------------------------------------------------------------------------
    # Season Data
    # -------------------------------------------------------------------------

    def get_available_seasons(self) -> list[int]:
        """Get list of seasons available from NHL API.

        Returns:
            List of season start years (e.g., [1917, 1918, ..., 2023])

        Educational Note:
            The NHL was founded in 1917, making it the oldest
            of the four major North American pro sports leagues.
            However, complete game data is only available for
            more recent seasons through the modern API.
        """
        current_year = datetime.now().year
        if datetime.now().month < 10:
            current_year -= 1

        # Reliable data from modern era (expansion era onward)
        # Pre-1967 data may be incomplete
        return list(range(1967, current_year + 1))

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """NHL API provides game/schedule data."""
        return True

    def supports_odds(self) -> bool:
        """NHL API does NOT provide odds data."""
        return False

    def supports_elo(self) -> bool:
        """NHL API does NOT provide Elo ratings (we compute our own)."""
        return False

    def supports_stats(self) -> bool:
        """NHL API provides stats but we haven't implemented the method yet."""
        return False  # TODO: Implement load_stats() in future

    def supports_rankings(self) -> bool:
        """NHL API provides standings but not rankings."""
        return False
