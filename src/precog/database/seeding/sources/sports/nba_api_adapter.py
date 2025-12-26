"""
NBA API Source Adapter.

Provides access to NBA historical data through the nba_api library.

nba_api Library:
    A Python library for fetching data from stats.nba.com, providing
    comprehensive NBA and WNBA statistics, game data, and player info.

    Installation: pip install nba_api
    Repository: https://github.com/swar/nba_api

Key Data Available:
    - Game schedules and results (2000-present)
    - Player stats (box scores, season averages)
    - Team stats (seasonal, by game)
    - Standings and rankings

NBA Season Structure:
    NBA seasons span two calendar years (e.g., 2023-24 season).
    The season year is the starting year (2023 for 2023-24).
    - Regular season: October-April (~82 games per team)
    - Playoffs: April-June (best-of-7 series)
    - NBA Finals: June

Note on WNBA:
    While nba_api can fetch WNBA data, we focus on NBA for now.
    WNBA data would require a separate adapter with different team codes.

Related:
    - ADR-109: Elo Rating Computation Engine Architecture
    - Issue #273: Multi-sport Elo computation
    - team_history.py: NBA team relocation mappings
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
    DataSourceConnectionError,
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

# nba_api uses 3-letter abbreviations consistent with NBA official codes
# Map any variations to our standard codes
NBA_API_TEAM_CODES: dict[str, str] = {
    "PHX": "PHO",  # Phoenix uses PHX sometimes, we use PHO
    "NOR": "NOP",  # New Orleans Pelicans alternative
    "NOK": "NOP",  # New Orleans/Oklahoma City Hornets (2005-07 Katrina)
    "NOH": "NOP",  # New Orleans Hornets
    "CHA": "CHA",  # Charlotte (Bobcats/Hornets) - same code, different franchise
    "NJN": "BKN",  # New Jersey Nets -> Brooklyn
    "SEA": "OKC",  # Seattle SuperSonics -> Oklahoma City Thunder
    "VAN": "MEM",  # Vancouver Grizzlies -> Memphis
    "WSB": "WAS",  # Washington Bullets -> Wizards
    "KCK": "SAC",  # Kansas City Kings -> Sacramento
    "SDC": "LAC",  # San Diego Clippers -> LA
    "BUF": "LAC",  # Buffalo Braves -> SD -> LA Clippers
    "NOJ": "UTA",  # New Orleans Jazz -> Utah
}


def normalize_nba_team_code(code: str) -> str:
    """Normalize NBA team code to database format.

    Uses the unified team history module for relocation mappings,
    plus nba_api-specific abbreviation corrections.

    Args:
        code: Team code from nba_api

    Returns:
        Normalized team code for database lookup

    Example:
        >>> normalize_nba_team_code("SEA")
        'OKC'
        >>> normalize_nba_team_code("LAL")
        'LAL'
    """
    code = code.upper().strip()

    # First check nba_api-specific mappings
    if code in NBA_API_TEAM_CODES:
        return NBA_API_TEAM_CODES[code]

    # Then use unified team history for relocations
    return resolve_team_code("nba", code)


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_nba_date(date_str: str | None) -> datetime | None:
    """Parse NBA API date string to datetime.

    NBA API returns dates in various formats:
    - "2023-10-24T00:00:00" (ISO with time)
    - "2023-10-24" (ISO date only)
    - "OCT 24, 2023" (formatted)

    Args:
        date_str: Date string from NBA API

    Returns:
        Parsed datetime or None
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)  # noqa: DTZ007
        except ValueError:
            continue

    logger.warning("Could not parse NBA date: %s", date_str)
    return None


def _to_decimal(value: Any, precision: str = "0.0001") -> Decimal | None:
    """Convert a value to Decimal with specified precision.

    Args:
        value: Value to convert (float, int, str, or None)
        precision: Decimal precision string

    Returns:
        Decimal value or None if conversion fails
    """
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
# NBA API Source Adapter
# =============================================================================


class NBAApiSource(APIBasedSourceMixin, BaseDataSource):
    """NBA API historical data source.

    Loads NBA game data using the nba_api library.
    Provides game schedules, results, and basic statistics.

    Usage:
        >>> source = NBAApiSource()
        >>> for game in source.load_games(seasons=[2023]):
        ...     print(f"{game['away_team_code']} @ {game['home_team_code']}")

    Attributes:
        source_name: "nba_api"
        supported_sports: ["nba"]

    Rate Limiting:
        stats.nba.com has strict rate limits (~60 requests/minute).
        This adapter includes built-in delays to avoid being blocked.

    Requirements:
        - nba_api must be installed: pip install nba_api

    Related:
        - ADR-109: Elo Rating Computation Engine
        - Issue #273: Multi-sport Elo computation
    """

    source_name = "nba_api"
    supported_sports: ClassVar[list[str]] = ["nba"]

    # Rate limiting: stats.nba.com is strict
    REQUEST_DELAY = 0.6  # 600ms between requests to avoid blocks

    def __init__(self, **kwargs: Any) -> None:
        """Initialize NBA API source.

        Args:
            **kwargs: Configuration options passed to base class

        Raises:
            DataSourceError: If nba_api is not installed
        """
        super().__init__(**kwargs)
        self._endpoints = None
        self._last_request_time = 0.0

    def _get_endpoints_module(self) -> Any:
        """Lazy load nba_api endpoints module.

        Returns:
            The nba_api.stats.endpoints module

        Raises:
            DataSourceError: If nba_api is not installed
        """
        if self._endpoints is None:
            try:
                from nba_api.stats import endpoints

                self._endpoints = endpoints
            except ImportError as e:
                raise DataSourceError(
                    "nba_api is not installed. Install with: pip install nba_api"
                ) from e
        return self._endpoints

    def _rate_limit_wait(self) -> None:
        """Wait if necessary to respect rate limits.

        Educational Note:
            stats.nba.com has strict rate limiting. Exceeding limits
            results in temporary IP blocks. We use a simple delay
            between requests rather than token bucket for simplicity.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    # -------------------------------------------------------------------------
    # Game Data Loading
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nba",
        seasons: list[int] | None = None,
        **_kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load NBA game schedules and results.

        Uses nba_api's LeagueGameLog endpoint to fetch game data.
        Returns completed games with final scores.

        Args:
            sport: Must be "nba"
            seasons: List of seasons to load (e.g., [2022, 2023])
                     Season year is the start year (2023 = 2023-24 season)
                     Default: last 2 seasons
            **kwargs: Additional options (unused)

        Yields:
            GameRecord for each completed game

        Raises:
            DataSourceConnectionError: If unable to fetch data

        Example:
            >>> source = NBAApiSource()
            >>> games = list(source.load_games(seasons=[2023]))
            >>> len(games)
            ~1230  # Regular season games

        Educational Note:
            NBA API returns games from the perspective of each team,
            so each game appears twice (once for home, once for away).
            We deduplicate by only yielding when the record is for
            the home team (MATCHUP contains 'vs.').
        """
        self._validate_sport(sport)

        if seasons is None:
            current_year = datetime.now().year
            # NBA season spans two years; if we're before October, use previous year
            if datetime.now().month < 10:
                current_year -= 1
            seasons = [current_year - 1, current_year]

        self._logger.info("Loading NBA games from nba_api: seasons=%s", seasons)

        try:
            endpoints = self._get_endpoints_module()
        except DataSourceError:
            raise

        for season in seasons:
            # Format season string as NBA API expects (e.g., "2023-24")
            season_str = f"{season}-{str(season + 1)[-2:]}"
            self._logger.info("Fetching season %s", season_str)

            try:
                self._rate_limit_wait()
                game_log = endpoints.LeagueGameLog(
                    season=season_str,
                    season_type_all_star="Regular Season",
                    player_or_team_abbreviation="T",
                )
                data = game_log.get_dict()
            except Exception as e:
                self._logger.error("Failed to fetch season %s: %s", season_str, e)
                raise DataSourceConnectionError(
                    f"Failed to fetch NBA games for {season_str}: {e}"
                ) from e

            # Parse the response
            result_sets = data.get("resultSets", [])
            if not result_sets:
                self._logger.warning("No data returned for season %s", season_str)
                continue

            # Find the LeagueGameLog result set
            game_log_data = None
            for rs in result_sets:
                if rs.get("name") == "LeagueGameLog":
                    game_log_data = rs
                    break

            if not game_log_data:
                self._logger.warning("No LeagueGameLog in response for %s", season_str)
                continue

            headers = game_log_data.get("headers", [])
            rows = game_log_data.get("rowSet", [])

            # Build header index for column lookup
            header_idx = {h: i for i, h in enumerate(headers)}

            # Process rows
            for row in rows:
                try:
                    yield from self._parse_game_row(row, header_idx, season)
                except Exception as e:
                    self._logger.warning("Error parsing game row: %s", e)
                    continue

            # Also fetch playoffs for this season
            try:
                self._rate_limit_wait()
                playoff_log = endpoints.LeagueGameLog(
                    season=season_str,
                    season_type_all_star="Playoffs",
                    player_or_team_abbreviation="T",
                )
                playoff_data = playoff_log.get_dict()

                for rs in playoff_data.get("resultSets", []):
                    if rs.get("name") == "LeagueGameLog":
                        playoff_headers = rs.get("headers", [])
                        playoff_rows = rs.get("rowSet", [])
                        playoff_header_idx = {h: i for i, h in enumerate(playoff_headers)}

                        for row in playoff_rows:
                            try:
                                yield from self._parse_game_row(
                                    row, playoff_header_idx, season, is_playoff=True
                                )
                            except Exception as e:
                                self._logger.warning("Error parsing playoff row: %s", e)
                                continue
            except Exception as e:
                self._logger.warning("Failed to fetch playoffs for %s: %s", season_str, e)

    def _parse_game_row(
        self,
        row: list[Any],
        header_idx: dict[str, int],
        season: int,
        is_playoff: bool = False,
    ) -> Iterator[GameRecord]:
        """Parse a single game row from LeagueGameLog.

        Args:
            row: Row data from API response
            header_idx: Mapping of header names to indices
            season: Season year
            is_playoff: Whether this is a playoff game

        Yields:
            GameRecord if this row represents a home team record

        Educational Note:
            Each game appears twice in LeagueGameLog - once for each team.
            We only yield when MATCHUP contains 'vs.' (home team perspective).
            This prevents duplicate records in the database.
        """
        # Get matchup string (e.g., "LAL vs. GSW" or "LAL @ GSW")
        matchup_idx = header_idx.get("MATCHUP")
        if matchup_idx is None:
            return

        matchup = str(row[matchup_idx]) if matchup_idx < len(row) else ""

        # Only process home games (contains "vs.") to avoid duplicates
        if " vs. " not in matchup:
            return

        # Parse teams from matchup
        parts = matchup.split(" vs. ")
        if len(parts) != 2:
            return

        home_team_raw = parts[0].strip()
        away_team_raw = parts[1].strip()

        home_team = normalize_nba_team_code(home_team_raw)
        away_team = normalize_nba_team_code(away_team_raw)

        # Get game date
        game_date_idx = header_idx.get("GAME_DATE")
        if game_date_idx is None:
            return

        game_date_str = str(row[game_date_idx]) if game_date_idx < len(row) else None
        game_date_dt = _parse_nba_date(game_date_str)
        if not game_date_dt:
            return

        game_date = game_date_dt.date()

        # Get scores - home team score is PTS
        pts_idx = header_idx.get("PTS")
        home_score = int(row[pts_idx]) if pts_idx and pts_idx < len(row) and row[pts_idx] else None

        # Away score is calculated from plus_minus
        plus_minus_idx = header_idx.get("PLUS_MINUS")

        away_score: int | None = None
        if home_score is not None and plus_minus_idx is not None and plus_minus_idx < len(row):
            plus_minus = row[plus_minus_idx]
            if plus_minus is not None:
                # plus_minus = home_score - away_score
                away_score = home_score - int(plus_minus)

        # External game ID
        game_id_idx = header_idx.get("GAME_ID")
        external_id = str(row[game_id_idx]) if game_id_idx and game_id_idx < len(row) else None

        yield GameRecord(
            sport="nba",
            season=season,
            game_date=game_date,
            home_team_code=home_team,
            away_team_code=away_team,
            home_score=home_score,
            away_score=away_score,
            is_neutral_site=False,  # NBA rarely plays neutral site games
            is_playoff=is_playoff,
            game_type="playoff" if is_playoff else "regular",
            venue_name=None,  # LeagueGameLog doesn't include venue
            source=self.source_name,
            source_file=None,
            external_game_id=external_id,
        )

    # -------------------------------------------------------------------------
    # Season Data
    # -------------------------------------------------------------------------

    def get_available_seasons(self) -> list[int]:
        """Get list of seasons available from NBA API.

        Returns:
            List of season start years (e.g., [1996, 1997, ..., 2023])

        Educational Note:
            NBA API provides data from 1996-97 season onwards.
            Earlier seasons have limited or no data available.
        """
        current_year = datetime.now().year
        # NBA season starts in October
        if datetime.now().month < 10:
            current_year -= 1

        # NBA API has data from 1996-97 season onwards
        return list(range(1996, current_year + 1))

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """nba_api provides game/schedule data."""
        return True

    def supports_odds(self) -> bool:
        """nba_api does NOT provide odds data."""
        return False

    def supports_elo(self) -> bool:
        """nba_api does NOT provide Elo ratings (we compute our own)."""
        return False

    def supports_stats(self) -> bool:
        """nba_api provides stats but we haven't implemented the method yet."""
        return False  # TODO: Implement load_stats() in future

    def supports_rankings(self) -> bool:
        """nba_api can provide standings but not poll rankings."""
        return False
