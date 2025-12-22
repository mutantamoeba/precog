"""
NFL Data Py Source Adapter.

Provides access to NFL player and team statistics through the nfl_data_py
library, which wraps nflverse data repositories.

Data Available:
    - Weekly player stats (passing, rushing, receiving, defense)
    - Seasonal player stats (aggregated)
    - Team stats (offense and defense)
    - Rosters (player metadata)
    - Schedules (game data with scores)
    - Play-by-play (detailed game action)

Data Source:
    nfl_data_py is a Python wrapper for nflverse datasets hosted on GitHub:
    - GitHub: https://github.com/nflverse/nfl_data_py
    - Data: https://github.com/nflverse/nfldata

Design Notes:
    - Uses nfl_data_py library (already in requirements)
    - Implements StatsRecord loading for player/team statistics
    - Stats stored as JSONB for flexible schema across stat categories
    - Week 0 represents preseason, Week 18+ is postseason
    - Player IDs are from nflverse GSIS format

Related:
    - Issue #236: StatsRecord/RankingRecord Infrastructure
    - ADR-106: Historical Data Collection Architecture
    - base_source.py: StatsRecord TypedDict definition
    - Migration 0009: historical_stats and historical_rankings tables

Educational Note:
    nfl_data_py uses pandas DataFrames internally, which we convert to
    Iterator[StatsRecord] for memory-efficient processing. This allows
    loading seasons one at a time rather than loading entire datasets
    into memory. The JSONB stats field enables storing different stat
    schemas (passing vs rushing vs receiving) without schema changes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from precog.database.seeding.sources.base_source import (
    BaseDataSource,
    DataSourceConfigError,
    StatsRecord,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


# Lazy import nfl_data_py to avoid import errors if not installed
def _get_nfl_data_py() -> Any:
    """Lazy import nfl_data_py module.

    Returns:
        nfl_data_py module

    Raises:
        DataSourceConfigError: If nfl_data_py is not installed
    """
    try:
        import nfl_data_py as nfl

        return nfl
    except ImportError as e:
        raise DataSourceConfigError(
            "nfl_data_py not installed. Install with: pip install nfl_data_py"
        ) from e


class NFLDataPySource(BaseDataSource):
    """NFL Data Py source adapter.

    Loads NFL player and team statistics using the nfl_data_py library.
    Implements the BaseDataSource interface for consistent data loading.

    Usage:
        >>> source = NFLDataPySource()
        >>> # Load weekly player stats
        >>> for stat in source.load_stats(stat_type="weekly", seasons=[2023]):
        ...     print(f"{stat['player_name']}: {stat['stat_category']}")
        >>> # Load team stats
        >>> for stat in source.load_stats(stat_type="team", seasons=[2023]):
        ...     print(f"{stat['team_code']}: {stat['stat_category']}")

    Stat Types:
        - "weekly": Per-week player statistics
        - "seasonal": Season-total player statistics
        - "team": Team-level offensive/defensive stats

    Stat Categories:
        - "passing": Completions, attempts, yards, TDs, INTs
        - "rushing": Carries, yards, TDs, fumbles
        - "receiving": Targets, receptions, yards, TDs
        - "team_offense": Team offensive totals
        - "team_defense": Team defensive totals

    Attributes:
        source_name: "nfl_data_py"
        supported_sports: ["nfl"]

    Related:
        - nfl_data_py docs: https://github.com/nflverse/nfl_data_py
        - StatsRecord: TypedDict for stat records
    """

    source_name = "nfl_data_py"
    supported_sports: ClassVar[list[str]] = ["nfl"]

    # Stat category mappings
    PASSING_STATS: ClassVar[list[str]] = [
        "completions",
        "attempts",
        "passing_yards",
        "passing_tds",
        "interceptions",
        "sacks",
        "sack_yards",
        "passing_air_yards",
        "passing_yards_after_catch",
        "passing_first_downs",
        "passing_epa",
        "passer_rating",
        "pacr",
    ]

    RUSHING_STATS: ClassVar[list[str]] = [
        "carries",
        "rushing_yards",
        "rushing_tds",
        "rushing_fumbles",
        "rushing_fumbles_lost",
        "rushing_first_downs",
        "rushing_epa",
    ]

    RECEIVING_STATS: ClassVar[list[str]] = [
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "receiving_fumbles",
        "receiving_fumbles_lost",
        "receiving_air_yards",
        "receiving_yards_after_catch",
        "receiving_first_downs",
        "receiving_epa",
        "target_share",
        "racr",
    ]

    def __init__(
        self,
        data_dir: Path | None = None,
        cache_enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize NFL Data Py source.

        Args:
            data_dir: Directory for caching downloaded data (optional)
            cache_enabled: Whether to cache downloaded data
            **kwargs: Additional configuration
        """
        super().__init__(**kwargs)
        self._data_dir = data_dir
        self._cache_enabled = cache_enabled
        self._nfl: Any = None  # Lazy-loaded module

    @property
    def nfl(self) -> Any:
        """Lazy-load nfl_data_py module.

        Returns:
            nfl_data_py module
        """
        if self._nfl is None:
            self._nfl = _get_nfl_data_py()
        return self._nfl

    # -------------------------------------------------------------------------
    # Stats Data Loading
    # -------------------------------------------------------------------------

    def load_stats(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        stat_type: str = "weekly",
        **kwargs: Any,
    ) -> Iterator[StatsRecord]:
        """Load player/team statistics from nfl_data_py.

        Args:
            sport: Must be "nfl" for this source
            seasons: List of seasons to load (default: current year)
            stat_type: Type of stats:
                - "weekly": Per-week player stats (default)
                - "seasonal": Season-total player stats
                - "team": Team-level stats
            **kwargs: Additional options:
                - include_postseason: Include playoff weeks (default: True)

        Yields:
            StatsRecord for each player/team stat row

        Raises:
            DataSourceConfigError: If sport is not "nfl"

        Example:
            >>> source = NFLDataPySource()
            >>> for stat in source.load_stats(seasons=[2023], stat_type="weekly"):
            ...     if stat['stat_category'] == 'passing':
            ...         print(f"{stat['player_name']}: {stat['stats']['passing_yards']} yards")
        """
        self._validate_sport(sport)

        if seasons is None:
            from datetime import datetime

            current_year = datetime.now().year
            seasons = [current_year]

        self._logger.info("Loading NFL stats: type=%s, seasons=%s", stat_type, seasons)

        if stat_type == "weekly":
            yield from self._load_weekly_stats(seasons, **kwargs)
        elif stat_type == "seasonal":
            yield from self._load_seasonal_stats(seasons, **kwargs)
        elif stat_type == "team":
            yield from self._load_team_stats(seasons, **kwargs)
        else:
            raise DataSourceConfigError(
                f"Unknown stat_type: {stat_type}. Valid options: weekly, seasonal, team"
            )

    def _load_weekly_stats(
        self,
        seasons: list[int],
        include_postseason: bool = True,
        **_kwargs: Any,
    ) -> Iterator[StatsRecord]:
        """Load weekly player statistics.

        Args:
            seasons: Seasons to load
            include_postseason: Include playoff weeks
            **_kwargs: Unused

        Yields:
            StatsRecord for each player-week combination
        """
        try:
            df = self.nfl.import_weekly_data(seasons)
        except Exception as e:
            self._logger.error("Failed to load weekly stats: %s", e)
            return

        if df is None or df.empty:
            self._logger.warning("No weekly stats found for seasons: %s", seasons)
            return

        self._logger.info("Processing %d weekly stat rows", len(df))

        for _, row in df.iterrows():
            # Filter postseason if requested
            week = int(row.get("week", 0))
            if not include_postseason and week > 17:
                continue

            player_id = str(row.get("player_id", "")) or None
            player_name = str(row.get("player_name", "")) or None
            team_code = str(row.get("recent_team", "")) or None
            season = int(row.get("season", 0))

            # Skip rows without player info
            if not player_id and not player_name:
                continue

            # Extract stats by category and yield separate records
            # This allows querying by stat category
            for category, stat_fields in [
                ("passing", self.PASSING_STATS),
                ("rushing", self.RUSHING_STATS),
                ("receiving", self.RECEIVING_STATS),
            ]:
                stats = self._extract_stats(row, stat_fields)
                if stats:  # Only yield if player has stats in this category
                    yield StatsRecord(
                        sport="nfl",
                        season=season,
                        week=week,
                        team_code=team_code,
                        player_id=player_id,
                        player_name=player_name,
                        stat_category=category,
                        stats=stats,
                        source=self.source_name,
                        source_file=None,
                    )

    def _load_seasonal_stats(
        self,
        seasons: list[int],
        **_kwargs: Any,
    ) -> Iterator[StatsRecord]:
        """Load seasonal aggregated player statistics.

        Args:
            seasons: Seasons to load
            **_kwargs: Unused

        Yields:
            StatsRecord for each player-season combination
        """
        try:
            df = self.nfl.import_seasonal_data(seasons)
        except Exception as e:
            self._logger.error("Failed to load seasonal stats: %s", e)
            return

        if df is None or df.empty:
            self._logger.warning("No seasonal stats found for seasons: %s", seasons)
            return

        self._logger.info("Processing %d seasonal stat rows", len(df))

        for _, row in df.iterrows():
            player_id = str(row.get("player_id", "")) or None
            player_name = str(row.get("player_name", "")) or None
            team_code = str(row.get("recent_team", "")) or None
            season = int(row.get("season", 0))

            if not player_id and not player_name:
                continue

            # Extract stats by category
            for category, stat_fields in [
                ("passing", self.PASSING_STATS),
                ("rushing", self.RUSHING_STATS),
                ("receiving", self.RECEIVING_STATS),
            ]:
                stats = self._extract_stats(row, stat_fields)
                if stats:
                    yield StatsRecord(
                        sport="nfl",
                        season=season,
                        week=None,  # Seasonal stats don't have week
                        team_code=team_code,
                        player_id=player_id,
                        player_name=player_name,
                        stat_category=category,
                        stats=stats,
                        source=self.source_name,
                        source_file=None,
                    )

    def _load_team_stats(
        self,
        seasons: list[int],
        **_kwargs: Any,
    ) -> Iterator[StatsRecord]:
        """Load team-level statistics.

        Uses nfl_data_py's team descriptions which include
        seasonal team stats.

        Args:
            seasons: Seasons to load
            **_kwargs: Unused

        Yields:
            StatsRecord for each team-season combination
        """
        try:
            # Team descriptions include seasonal team stats
            df = self.nfl.import_team_desc()
        except Exception as e:
            self._logger.error("Failed to load team stats: %s", e)
            return

        if df is None or df.empty:
            self._logger.warning("No team data found")
            return

        # Team descriptions don't have season-specific stats
        # For team stats, we use schedule data aggregated
        try:
            schedules = self.nfl.import_schedules(seasons)
        except Exception as e:
            self._logger.error("Failed to load schedules for team stats: %s", e)
            return

        if schedules is None or schedules.empty:
            return

        # Aggregate team stats from schedules
        for season in seasons:
            season_games = schedules[schedules["season"] == season]
            if season_games.empty:
                continue

            # Get unique teams
            home_teams = set(season_games["home_team"].dropna().unique())
            away_teams = set(season_games["away_team"].dropna().unique())
            all_teams = home_teams | away_teams

            for team_code in all_teams:
                if not team_code:
                    continue

                # Home games
                home_games = season_games[season_games["home_team"] == team_code]
                # Away games
                away_games = season_games[season_games["away_team"] == team_code]

                # Calculate offensive stats
                home_points = home_games["home_score"].sum()
                away_points = away_games["away_score"].sum()
                total_points_for = (home_points or 0) + (away_points or 0)

                # Calculate defensive stats
                home_points_allowed = home_games["away_score"].sum()
                away_points_allowed = away_games["home_score"].sum()
                total_points_against = (home_points_allowed or 0) + (away_points_allowed or 0)

                # Game counts
                games_played = len(home_games) + len(away_games)
                home_wins = len(home_games[home_games["home_score"] > home_games["away_score"]])
                away_wins = len(away_games[away_games["away_score"] > away_games["home_score"]])

                # Yield team offense stats
                yield StatsRecord(
                    sport="nfl",
                    season=season,
                    week=None,
                    team_code=str(team_code),
                    player_id=None,
                    player_name=None,
                    stat_category="team_offense",
                    stats={
                        "games_played": games_played,
                        "total_points": int(total_points_for),
                        "points_per_game": round(total_points_for / games_played, 2)
                        if games_played
                        else 0,
                        "home_wins": home_wins,
                        "away_wins": away_wins,
                        "total_wins": home_wins + away_wins,
                    },
                    source=self.source_name,
                    source_file=None,
                )

                # Yield team defense stats
                yield StatsRecord(
                    sport="nfl",
                    season=season,
                    week=None,
                    team_code=str(team_code),
                    player_id=None,
                    player_name=None,
                    stat_category="team_defense",
                    stats={
                        "games_played": games_played,
                        "total_points_allowed": int(total_points_against),
                        "points_allowed_per_game": round(total_points_against / games_played, 2)
                        if games_played
                        else 0,
                    },
                    source=self.source_name,
                    source_file=None,
                )

    def _extract_stats(self, row: Any, stat_fields: list[str]) -> dict[str, Any]:
        """Extract stat fields from a DataFrame row.

        Only includes fields that have non-null, non-zero values.

        Args:
            row: pandas DataFrame row
            stat_fields: List of field names to extract

        Returns:
            Dictionary of stat name to value (only non-empty stats)
        """
        stats: dict[str, Any] = {}
        for field in stat_fields:
            value = row.get(field)
            # Skip null/empty values
            if value is None:
                continue
            # Handle pandas NA
            try:
                import pandas as pd

                if pd.isna(value):
                    continue
            except (ImportError, TypeError):
                pass
            # Skip zero values for cleaner data
            if isinstance(value, (int, float)) and value == 0:
                continue
            # Convert numpy types to Python types
            if hasattr(value, "item"):
                value = value.item()
            stats[field] = value
        return stats

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_stats(self) -> bool:
        """NFL Data Py supports player/team stats."""
        return True

    def supports_rankings(self) -> bool:
        """NFL Data Py does NOT support rankings data."""
        return False

    def supports_games(self) -> bool:
        """NFL Data Py supports game schedules/scores."""
        return True

    def supports_elo(self) -> bool:
        """NFL Data Py does NOT provide Elo data."""
        return False

    def supports_odds(self) -> bool:
        """NFL Data Py does NOT provide odds data."""
        return False

    # -------------------------------------------------------------------------
    # Additional Data Loading (from BaseDataSource interface)
    # -------------------------------------------------------------------------

    def load_games(
        self,
        sport: str = "nfl",
        seasons: list[int] | None = None,
        **_kwargs: Any,
    ) -> Iterator[Any]:
        """Load NFL game schedules/results.

        Args:
            sport: Must be "nfl"
            seasons: Seasons to load
            **kwargs: Additional options

        Yields:
            GameRecord for each game

        Note:
            This is a basic implementation. For full GameRecord support,
            consider using the schedule data more comprehensively.
        """
        from precog.database.seeding.sources.base_source import GameRecord

        self._validate_sport(sport)

        if seasons is None:
            from datetime import datetime

            seasons = [datetime.now().year]

        try:
            df = self.nfl.import_schedules(seasons)
        except Exception as e:
            self._logger.error("Failed to load schedules: %s", e)
            return

        if df is None or df.empty:
            return

        for _, row in df.iterrows():
            game_date_str = row.get("gameday")
            if game_date_str is None:
                continue

            from datetime import date

            try:
                # date.fromisoformat is cleaner for YYYY-MM-DD format
                game_date = date.fromisoformat(str(game_date_str))
            except ValueError:
                continue

            yield GameRecord(
                sport="nfl",
                season=int(row.get("season", 0)),
                game_date=game_date,
                home_team_code=str(row.get("home_team", "")),
                away_team_code=str(row.get("away_team", "")),
                home_score=int(row["home_score"]) if row.get("home_score") is not None else None,
                away_score=int(row["away_score"]) if row.get("away_score") is not None else None,
                is_neutral_site=False,
                is_playoff=str(row.get("game_type", "")).lower() in ("post", "playoff"),
                game_type=str(row.get("game_type", "REG")),
                venue_name=str(row.get("stadium", "")) or None,
                source=self.source_name,
                source_file=None,
                external_game_id=str(row.get("game_id", "")) or None,
            )
