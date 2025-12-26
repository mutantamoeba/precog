"""
pybaseball Source Adapter.

Provides access to MLB historical data through the pybaseball library.

pybaseball Library:
    A Python library for fetching baseball data from multiple sources:
    - Baseball Reference (bbref)
    - FanGraphs
    - Retrosheet
    - Statcast (pitch-by-pitch data)

    Installation: pip install pybaseball
    Repository: https://github.com/jldbc/pybaseball

Key Data Available:
    - Game schedules and results (1871-present via retrosheet)
    - Player stats (batting, pitching, fielding)
    - Team stats and standings
    - Statcast data (2015-present)

MLB Season Structure:
    MLB seasons are single calendar years (e.g., 2023 season).
    - Spring training: February-March
    - Regular season: April-September (~162 games per team)
    - Postseason: October (Wild Card, Division Series, LCS, World Series)

Related:
    - ADR-109: Elo Rating Computation Engine Architecture
    - Issue #273: Multi-sport Elo computation
    - team_history.py: MLB team relocation mappings
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

# pybaseball uses team abbreviations from Baseball Reference
# Map any variations to our standard codes
PYBASEBALL_TEAM_CODES: dict[str, str] = {
    # Current teams with abbreviation variants
    "WSN": "WAS",  # Washington Nationals
    "WSH": "WAS",  # Washington Nationals
    "CHW": "CWS",  # Chicago White Sox
    "CHA": "CWS",  # Chicago White Sox (American League)
    "CHN": "CHC",  # Chicago Cubs (National League)
    "KCR": "KC",  # Kansas City Royals
    "KCA": "KC",  # Kansas City Royals
    "SDP": "SD",  # San Diego Padres
    "SFG": "SF",  # San Francisco Giants
    "TBR": "TB",  # Tampa Bay Rays
    "TBA": "TB",  # Tampa Bay Rays
    "FLA": "MIA",  # Florida Marlins -> Miami Marlins (2012)
    "ANA": "LAA",  # Anaheim Angels -> Los Angeles Angels
    "CAL": "LAA",  # California Angels -> Los Angeles Angels
    "LAA": "LAA",  # Los Angeles Angels
    "NYA": "NYY",  # New York Yankees (American League)
    "NYN": "NYM",  # New York Mets (National League)
    # Historical relocations handled by team_history.py
    "MON": "WAS",  # Montreal Expos -> Washington Nationals
    "BRO": "LAD",  # Brooklyn Dodgers -> Los Angeles Dodgers
    "NYG": "SF",  # New York Giants -> San Francisco Giants
    "PHA": "OAK",  # Philadelphia Athletics -> Oakland
    "BSN": "ATL",  # Boston Braves -> Atlanta
    "MLN": "ATL",  # Milwaukee Braves -> Atlanta
    "WS1": "MIN",  # Washington Senators (1st) -> Minnesota Twins
    "WS2": "TEX",  # Washington Senators (2nd) -> Texas Rangers
    "SLB": "BAL",  # St. Louis Browns -> Baltimore Orioles
    "SEP": "MIL",  # Seattle Pilots -> Milwaukee Brewers
}


def normalize_mlb_team_code(code: str) -> str:
    """Normalize MLB team code to database format.

    Uses the unified team history module for relocation mappings,
    plus pybaseball-specific abbreviation corrections.

    Args:
        code: Team code from pybaseball

    Returns:
        Normalized team code for database lookup

    Example:
        >>> normalize_mlb_team_code("NYA")
        'NYY'
        >>> normalize_mlb_team_code("BOS")
        'BOS'
    """
    code = code.upper().strip()

    # First check pybaseball-specific mappings
    if code in PYBASEBALL_TEAM_CODES:
        return PYBASEBALL_TEAM_CODES[code]

    # Then use unified team history for relocations
    return resolve_team_code("mlb", code)


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_mlb_date(date_val: Any) -> datetime | None:
    """Parse MLB date to datetime.

    pybaseball returns dates in various formats depending on the source.

    Args:
        date_val: Date value from pybaseball (string, datetime, or pandas Timestamp)

    Returns:
        Parsed datetime or None
    """
    if date_val is None:
        return None

    # Handle pandas Timestamp
    if hasattr(date_val, "to_pydatetime"):
        result: datetime = date_val.to_pydatetime()
        return result

    if isinstance(date_val, datetime):
        return date_val

    if not isinstance(date_val, str):
        date_val = str(date_val)

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_val, fmt)  # noqa: DTZ007
        except ValueError:
            continue

    logger.warning("Could not parse MLB date: %s", date_val)
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
# pybaseball Source Adapter
# =============================================================================


class PybaseballSource(APIBasedSourceMixin, BaseDataSource):
    """pybaseball historical data source.

    Loads MLB game data using the pybaseball library.
    Provides game schedules, results, and comprehensive statistics.

    Usage:
        >>> source = PybaseballSource()
        >>> for game in source.load_games(seasons=[2023]):
        ...     print(f"{game['away_team_code']} @ {game['home_team_code']}")

    Attributes:
        source_name: "pybaseball"
        supported_sports: ["mlb"]

    Rate Limiting:
        pybaseball caches data locally after first fetch, making
        subsequent requests very fast. We include minimal delays
        for initial fetches to be respectful of data sources.

    Requirements:
        - pybaseball must be installed: pip install pybaseball

    Related:
        - ADR-109: Elo Rating Computation Engine
        - Issue #273: Multi-sport Elo computation
    """

    source_name = "pybaseball"
    supported_sports: ClassVar[list[str]] = ["mlb"]

    # Rate limiting: pybaseball caches data, so minimal delays needed
    REQUEST_DELAY = 0.2  # 200ms between requests

    def __init__(self, **kwargs: Any) -> None:
        """Initialize pybaseball source.

        Args:
            **kwargs: Configuration options passed to base class

        Raises:
            DataSourceError: If pybaseball is not installed
        """
        super().__init__(**kwargs)
        self._pybaseball = None
        self._last_request_time = 0.0

    def _get_pybaseball_module(self) -> Any:
        """Lazy load pybaseball module.

        Returns:
            The pybaseball module

        Raises:
            DataSourceError: If pybaseball is not installed
        """
        if self._pybaseball is None:
            try:
                import pybaseball

                # Enable caching for better performance
                pybaseball.cache.enable()
                self._pybaseball = pybaseball
            except ImportError as e:
                raise DataSourceError(
                    "pybaseball is not installed. Install with: pip install pybaseball"
                ) from e
        return self._pybaseball

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
        sport: str = "mlb",
        seasons: list[int] | None = None,
        **_kwargs: Any,
    ) -> Iterator[GameRecord]:
        """Load MLB game schedules and results.

        Uses pybaseball's schedule_and_record function to fetch game data.
        Returns completed games with final scores.

        Args:
            sport: Must be "mlb"
            seasons: List of seasons to load (e.g., [2022, 2023])
                     Default: last 2 seasons
            **kwargs: Additional options (unused)

        Yields:
            GameRecord for each completed game

        Raises:
            DataSourceConnectionError: If unable to fetch data

        Example:
            >>> source = PybaseballSource()
            >>> games = list(source.load_games(seasons=[2023]))
            >>> len(games)
            ~2430  # Regular season games (162 games x 30 teams / 2)

        Educational Note:
            MLB has the longest regular season of the major sports,
            with 162 games per team (compared to 82 for NBA/NHL, 17 for NFL).
            This provides rich data for Elo computation.
        """
        self._validate_sport(sport)

        if seasons is None:
            current_year = datetime.now().year
            # MLB season is April-October; if before April, use previous year
            if datetime.now().month < 4:
                current_year -= 1
            seasons = [current_year - 1, current_year]

        self._logger.info("Loading MLB games from pybaseball: seasons=%s", seasons)

        try:
            pybb = self._get_pybaseball_module()
        except DataSourceError:
            raise

        for season in seasons:
            self._logger.info("Fetching MLB season %d", season)

            # Get list of all teams for this season
            teams = self._get_teams_for_season(season)

            # Track games we've already seen (to avoid duplicates)
            seen_games: set[str] = set()

            for team in teams:
                try:
                    self._rate_limit_wait()

                    # Fetch schedule for this team
                    schedule = pybb.schedule_and_record(season, team)

                    if schedule is None or len(schedule) == 0:
                        self._logger.debug("No schedule for %s in %d", team, season)
                        continue

                    # Iterate through games
                    for _, row in schedule.iterrows():
                        game_record = self._parse_schedule_row(row, season, seen_games)
                        if game_record:
                            yield game_record

                except Exception as e:
                    self._logger.warning("Error fetching %s for %d: %s", team, season, e)
                    continue

    def _get_teams_for_season(self, season: int) -> list[str]:
        """Get list of MLB team abbreviations for a given season.

        Args:
            season: Season year

        Returns:
            List of team abbreviations

        Educational Note:
            MLB has had 30 teams since 1998 (Arizona and Tampa Bay expansion).
            Historical seasons may have fewer teams.
        """
        # Current 30 MLB teams (as of 2020+)
        current_teams = [
            "ARI",
            "ATL",
            "BAL",
            "BOS",
            "CHC",
            "CWS",
            "CIN",
            "CLE",
            "COL",
            "DET",
            "HOU",
            "KC",
            "LAA",
            "LAD",
            "MIA",
            "MIL",
            "MIN",
            "NYM",
            "NYY",
            "OAK",
            "PHI",
            "PIT",
            "SD",
            "SEA",
            "SF",
            "STL",
            "TB",
            "TEX",
            "TOR",
            "WAS",
        ]

        # For modern era (1998+), return all 30 teams
        if season >= 1998:
            return current_teams

        # For older seasons, we'd need to adjust for expansion/contraction
        # For now, return current teams (pybaseball will handle missing data)
        return current_teams

    def _parse_schedule_row(
        self,
        row: Any,
        season: int,
        seen_games: set[str],
    ) -> GameRecord | None:
        """Parse a schedule row from pybaseball.

        Args:
            row: Row from schedule DataFrame
            season: Season year
            seen_games: Set of game IDs already processed

        Returns:
            GameRecord or None if game should be skipped

        Educational Note:
            We only emit home games to avoid duplicates, since each game
            appears in both teams' schedules.
        """
        # Only process home games to avoid duplicates
        home_away = str(row.get("Home_Away", ""))
        if home_away.upper() not in ("H", "HOME", ""):
            return None

        # Get opponent
        opp = str(row.get("Opp", ""))
        if not opp:
            return None

        # Get the team from the Tm column (if available) or infer from context
        team_code = str(row.get("Tm", ""))
        if not team_code:
            # If no Tm column, this might be a team-specific schedule
            # where we already know the team
            return None

        # Skip if this appears to be an away game (starts with @)
        if opp.startswith("@"):
            return None

        home_team = normalize_mlb_team_code(team_code)
        away_team = normalize_mlb_team_code(opp.replace("@", "").strip())

        # Create unique game ID for deduplication
        game_date_val = row.get("Date")
        game_date_dt = _parse_mlb_date(game_date_val)
        if not game_date_dt:
            return None

        game_date = game_date_dt.date()
        game_id = f"{game_date}_{away_team}_{home_team}"

        if game_id in seen_games:
            return None
        seen_games.add(game_id)

        # Get scores
        runs = row.get("R")  # Team's runs
        runs_allowed = row.get("RA")  # Opponent's runs

        if runs is None or runs_allowed is None:
            return None

        try:
            home_score = int(runs)
            away_score = int(runs_allowed)
        except (ValueError, TypeError):
            return None

        # Determine if playoff
        # Look for playoff indicator in game number or other fields
        gm = str(row.get("Gm#", ""))
        is_playoff = False
        if gm:
            # Regular season games are numbered; playoff games might have different format
            try:
                game_num = int(gm)
                # MLB regular season is 162 games
                is_playoff = game_num > 162
            except ValueError:
                # Non-numeric game number might indicate playoff
                is_playoff = any(x in gm.upper() for x in ["WC", "DS", "CS", "WS"])

        return GameRecord(
            sport="mlb",
            season=season,
            game_date=game_date,
            home_team_code=home_team,
            away_team_code=away_team,
            home_score=home_score,
            away_score=away_score,
            is_neutral_site=False,
            is_playoff=is_playoff,
            game_type="playoff" if is_playoff else "regular",
            venue_name=None,  # Not readily available in schedule
            source=self.source_name,
            source_file=None,
            external_game_id=game_id,
        )

    # -------------------------------------------------------------------------
    # Alternative Game Loading (Retrosheet)
    # -------------------------------------------------------------------------

    def load_games_retrosheet(
        self,
        seasons: list[int] | None = None,
    ) -> Iterator[GameRecord]:
        """Load MLB games from Retrosheet game logs.

        This is an alternative to schedule_and_record that uses
        Retrosheet's comprehensive game logs.

        Args:
            seasons: List of seasons to load

        Yields:
            GameRecord for each completed game

        Educational Note:
            Retrosheet provides the most comprehensive historical
            baseball data, going back to 1871. It includes detailed
            play-by-play data in addition to game results.
        """
        if seasons is None:
            current_year = datetime.now().year
            if datetime.now().month < 4:
                current_year -= 1
            seasons = [current_year]

        try:
            pybb = self._get_pybaseball_module()
        except DataSourceError:
            raise

        for season in seasons:
            self._logger.info("Fetching Retrosheet game logs for %d", season)

            try:
                self._rate_limit_wait()
                game_logs = pybb.retrosheet.season_game_logs(season)

                if game_logs is None or len(game_logs) == 0:
                    self._logger.warning("No Retrosheet data for %d", season)
                    continue

                for _, row in game_logs.iterrows():
                    game_record = self._parse_retrosheet_row(row, season)
                    if game_record:
                        yield game_record

            except Exception as e:
                self._logger.warning("Error fetching Retrosheet for %d: %s", season, e)
                continue

    def _parse_retrosheet_row(
        self,
        row: Any,
        season: int,
    ) -> GameRecord | None:
        """Parse a Retrosheet game log row.

        Args:
            row: Row from Retrosheet DataFrame
            season: Season year

        Returns:
            GameRecord or None
        """
        # Retrosheet has detailed column names
        home_team = str(row.get("Home", ""))
        away_team = str(row.get("Away", ""))

        if not home_team or not away_team:
            return None

        home_team = normalize_mlb_team_code(home_team)
        away_team = normalize_mlb_team_code(away_team)

        # Get date
        date_val = row.get("Date")
        game_date_dt = _parse_mlb_date(date_val)
        if not game_date_dt:
            return None

        game_date = game_date_dt.date()

        # Get scores
        home_score = row.get("HomeRuns")
        away_score = row.get("AwayRuns")

        if home_score is None or away_score is None:
            return None

        try:
            home_score = int(home_score)
            away_score = int(away_score)
        except (ValueError, TypeError):
            return None

        # External game ID
        external_id = str(row.get("GameID", "")) or f"{game_date}_{away_team}_{home_team}"

        return GameRecord(
            sport="mlb",
            season=season,
            game_date=game_date,
            home_team_code=home_team,
            away_team_code=away_team,
            home_score=home_score,
            away_score=away_score,
            is_neutral_site=False,
            is_playoff=False,  # Would need additional logic to determine
            game_type="regular",
            venue_name=None,
            source=f"{self.source_name}:retrosheet",
            source_file=None,
            external_game_id=external_id,
        )

    # -------------------------------------------------------------------------
    # Season Data
    # -------------------------------------------------------------------------

    def get_available_seasons(self) -> list[int]:
        """Get list of seasons available from pybaseball.

        Returns:
            List of season years (e.g., [1871, 1872, ..., 2023])

        Educational Note:
            Professional baseball dates back to 1871 with the
            National Association. The National League was founded
            in 1876, and the American League in 1901.
            Modern era (integration) began in 1947.
        """
        current_year = datetime.now().year
        if datetime.now().month < 4:
            current_year -= 1

        # Retrosheet has data from 1871, but we focus on modern era
        return list(range(1901, current_year + 1))

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """pybaseball provides game/schedule data."""
        return True

    def supports_odds(self) -> bool:
        """pybaseball does NOT provide odds data."""
        return False

    def supports_elo(self) -> bool:
        """pybaseball does NOT provide Elo ratings (we compute our own)."""
        return False

    def supports_stats(self) -> bool:
        """pybaseball provides extensive stats but we haven't implemented yet."""
        return False  # TODO: Implement load_stats() in future

    def supports_rankings(self) -> bool:
        """pybaseball provides standings but not rankings."""
        return False
