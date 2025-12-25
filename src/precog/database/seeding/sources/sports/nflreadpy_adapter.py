"""
NFLReadPy Source Adapter.

Provides access to NFL historical data and EPA metrics through the nflreadpy library.

nflreadpy Library:
    A Python port of the popular R package nflreadr, providing access to
    NFL data from the nflverse ecosystem.

    Installation: pip install nflreadpy
    Documentation: https://nflreadpy.nflverse.com/
    Repository: https://github.com/nflverse/nflreadpy

Key Differences from nfl_data_py:
    - Uses Polars DataFrames (not pandas) for better performance
    - Actively maintained (nfl_data_py was archived September 2025)
    - Same data sources via nflverse-data GitHub repositories
    - Function names: load_* instead of import_*

Data Available:
    - Schedules (1999-present): Game dates, teams, final scores
    - Play-by-play (1999-present): Every play with EPA metrics (372 columns)
    - Player stats, team stats, rosters, snap counts, etc.

EPA (Expected Points Added):
    EPA is the most predictive publicly available NFL metric.
    It's pre-computed in nflreadpy's load_pbp() function:
    - epa: Expected points added per play
    - qb_epa: QB-attributed EPA
    - pass_epa: Passing EPA
    - rush_epa: Rushing EPA

Related:
    - ADR-109: Elo Rating Computation Engine Architecture
    - REQ-ELO-003: EPA Integration from nflreadpy
    - Migration 0013: historical_epa table
    - ELO_COMPUTATION_GUIDE_V1.1.md: EPA methodology
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

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
# EPA Record Type Definition
# =============================================================================


class EPARecord(TypedDict):
    """EPA metrics record for a team in a specific week.

    Matches the historical_epa table schema from Migration 0013.
    All EPA values are Decimal for precision (ADR-002).

    Educational Note:
        EPA (Expected Points Added) measures how much each play
        improves a team's expected points. Positive EPA = good play,
        negative EPA = bad play. We aggregate to team-level weekly.
    """

    team_id: int | None  # FK to teams table (resolved later)
    team_name: str  # Team name for lookup
    team_code: str  # 2-3 letter abbreviation
    season: int  # NFL season year
    week: int | None  # Week number (1-18, None for season total)
    off_epa_per_play: Decimal | None
    pass_epa_per_play: Decimal | None
    rush_epa_per_play: Decimal | None
    def_epa_per_play: Decimal | None
    def_pass_epa_per_play: Decimal | None
    def_rush_epa_per_play: Decimal | None
    epa_differential: Decimal | None
    games_played: int
    source: str


# =============================================================================
# Team Code Mapping
# =============================================================================

# nflreadpy-specific team code mappings
# These handle abbreviation differences from standard codes
NFLREADPY_TEAM_CODES: dict[str, str] = {
    "JAC": "JAX",  # Jacksonville uses JAC in some contexts
    "LA": "LAR",  # LA Rams (not historical LA Raiders)
    "LV": "LVR",  # Las Vegas Raiders (post-2020 move)
    "OAK": "LVR",  # Oakland Raiders → Las Vegas
    "SD": "LAC",  # San Diego → LA Chargers
    "STL": "LAR",  # St. Louis → LA Rams
}


def normalize_nflreadpy_team_code(code: str) -> str:
    """Normalize nflreadpy team code to database format.

    Uses the unified team history module for relocation mappings,
    plus nflreadpy-specific abbreviation corrections.

    Args:
        code: Team code from nflreadpy

    Returns:
        Normalized team code for database lookup

    Example:
        >>> normalize_nflreadpy_team_code("JAC")
        'JAX'
        >>> normalize_nflreadpy_team_code("KC")
        'KC'
    """
    code = code.upper().strip()

    # First check nflreadpy-specific mappings
    if code in NFLREADPY_TEAM_CODES:
        return NFLREADPY_TEAM_CODES[code]

    # Then use unified team history for relocations
    return resolve_team_code("nfl", code)


# =============================================================================
# Helper Functions
# =============================================================================


def _to_decimal(value: Any, precision: str = "0.0001") -> Decimal | None:
    """Convert a value to Decimal with specified precision.

    Args:
        value: Value to convert (float, int, str, or None)
        precision: Decimal precision string

    Returns:
        Decimal value or None if conversion fails

    Educational Note:
        Always use Decimal for financial/statistical calculations
        to avoid floating-point precision errors (ADR-002).
    """
    if value is None:
        return None

    try:
        # Handle numpy/polars null values
        import math

        if isinstance(value, float) and math.isnan(value):
            return None

        dec = Decimal(str(value))
        return dec.quantize(Decimal(precision), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError):
        return None


# =============================================================================
# NFLReadPy Source Adapter
# =============================================================================


class NFLReadPySource(APIBasedSourceMixin, BaseDataSource):
    """NFLReadPy historical data source with EPA support.

    Loads NFL historical data and EPA metrics using the nflreadpy library.
    Provides schedules, game results, play-by-play data, and team EPA aggregates.

    Usage:
        >>> source = NFLReadPySource()
        >>> for game in source.load_games(seasons=[2023]):
        ...     print(f"{game['away_team_code']} @ {game['home_team_code']}")

        >>> for epa in source.load_epa(season=2023, week=1):
        ...     print(f"{epa['team_code']}: {epa['off_epa_per_play']}")

    Attributes:
        source_name: "nflreadpy"
        supported_sports: ["nfl"]

    Requirements:
        - nflreadpy must be installed: pip install nflreadpy
        - polars is required (nflreadpy dependency)

    Related:
        - ADR-109: Elo Rating Computation Engine
        - REQ-ELO-003: EPA Integration
        - ELO_COMPUTATION_GUIDE_V1.1.md
    """

    source_name = "nflreadpy"
    supported_sports: ClassVar[list[str]] = ["nfl"]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize NFLReadPy source.

        Args:
            **kwargs: Configuration options passed to base class

        Raises:
            DataSourceError: If nflreadpy is not installed
        """
        super().__init__(**kwargs)
        self._nfl = None

    def _get_nfl_module(self) -> Any:
        """Lazy load nflreadpy module.

        Returns:
            The nflreadpy module

        Raises:
            DataSourceError: If nflreadpy is not installed
        """
        if self._nfl is None:
            try:
                import nflreadpy as nfl

                self._nfl = nfl
            except ImportError as e:
                raise DataSourceError(
                    "nflreadpy is not installed. Install with: pip install nflreadpy"
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

        Uses nflreadpy.load_schedules() to fetch game data.
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
            >>> source = NFLReadPySource()
            >>> games = list(source.load_games(seasons=[2023]))
            >>> len(games)
            272  # Regular season games
        """
        self._validate_sport(sport)

        if seasons is None:
            current_year = datetime.now().year
            seasons = [current_year - 1, current_year]

        self._logger.info("Loading NFL games from nflreadpy: seasons=%s", seasons)

        try:
            nfl = self._get_nfl_module()
            # nflreadpy returns Polars DataFrame
            schedules_pl = nfl.load_schedules(seasons)
            # Convert to list of dicts for iteration
            schedules = schedules_pl.to_dicts()
        except Exception as e:
            raise DataSourceConnectionError(f"Failed to fetch NFL schedules: {e}") from e

        if not schedules:
            self._logger.warning("No schedule data returned")
            return

        for row in schedules:
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
            home_team = normalize_nflreadpy_team_code(str(row.get("home_team", "")))
            away_team = normalize_nflreadpy_team_code(str(row.get("away_team", "")))

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
    # EPA Data Loading
    # -------------------------------------------------------------------------

    def load_epa(
        self,
        season: int,
        week: int | None = None,
    ) -> Iterator[EPARecord]:
        """Load team-level EPA metrics from play-by-play data.

        Aggregates EPA from play-by-play data to team-week level.
        EPA is pre-computed in nflreadpy's load_pbp() function.

        Args:
            season: NFL season year (1999-present)
            week: Specific week (1-18), or None for all weeks

        Yields:
            EPARecord for each team-week combination

        Raises:
            DataSourceConnectionError: If unable to fetch data

        Example:
            >>> source = NFLReadPySource()
            >>> epa_data = list(source.load_epa(season=2023, week=1))
            >>> len(epa_data)
            32  # One record per team

        Educational Note:
            EPA (Expected Points Added) is calculated by nflfastR/nflverse
            using a sophisticated expected points model. We aggregate
            per-play EPA to team-level weekly metrics for Elo enhancement.
        """
        self._logger.info("Loading EPA data: season=%d, week=%s", season, week)

        try:
            nfl = self._get_nfl_module()
            # Load play-by-play with EPA (Polars DataFrame)
            pbp_pl = nfl.load_pbp([season])
        except Exception as e:
            raise DataSourceConnectionError(f"Failed to fetch PBP data: {e}") from e

        if pbp_pl is None or len(pbp_pl) == 0:
            self._logger.warning("No PBP data returned for season %d", season)
            return

        # Filter by week if specified
        if week is not None:
            pbp_pl = pbp_pl.filter(pbp_pl["week"] == week)

        # Get unique team-week combinations
        try:
            # Use Polars for aggregation
            import polars as pl

            # Aggregate offensive EPA by posteam (team with possession)
            off_epa = (
                pbp_pl.filter(pl.col("posteam").is_not_null())
                .group_by(["posteam", "week"])
                .agg(
                    [
                        pl.col("epa").mean().alias("off_epa_per_play"),
                        pl.col("epa")
                        .filter(pl.col("play_type") == "pass")
                        .mean()
                        .alias("pass_epa_per_play"),
                        pl.col("epa")
                        .filter(pl.col("play_type") == "run")
                        .mean()
                        .alias("rush_epa_per_play"),
                        pl.col("game_id").n_unique().alias("games_played"),
                    ]
                )
            )

            # Aggregate defensive EPA by defteam
            def_epa = (
                pbp_pl.filter(pl.col("defteam").is_not_null())
                .group_by(["defteam", "week"])
                .agg(
                    [
                        pl.col("epa").mean().alias("def_epa_per_play"),
                        pl.col("epa")
                        .filter(pl.col("play_type") == "pass")
                        .mean()
                        .alias("def_pass_epa_per_play"),
                        pl.col("epa")
                        .filter(pl.col("play_type") == "run")
                        .mean()
                        .alias("def_rush_epa_per_play"),
                    ]
                )
            )

            # Join offensive and defensive EPA
            combined = off_epa.join(
                def_epa,
                left_on=["posteam", "week"],
                right_on=["defteam", "week"],
                how="outer",
            )

            # Convert to dicts for iteration
            records = combined.to_dicts()

        except Exception as e:
            self._logger.error("Failed to aggregate EPA: %s", e)
            raise DataSourceConnectionError(f"EPA aggregation failed: {e}") from e

        for row in records:
            team_code = row.get("posteam") or row.get("defteam")
            if not team_code:
                continue

            team_code = normalize_nflreadpy_team_code(str(team_code))
            week_num = row.get("week")

            # Calculate EPA differential
            off_epa_val = _to_decimal(row.get("off_epa_per_play"))
            def_epa_val = _to_decimal(row.get("def_epa_per_play"))

            epa_diff: Decimal | None = None
            if off_epa_val is not None and def_epa_val is not None:
                # Offensive - Defensive (lower defensive is better)
                epa_diff = off_epa_val - def_epa_val

            yield EPARecord(
                team_id=None,  # Resolved later during database insert
                team_name="",  # Resolved later
                team_code=team_code,
                season=season,
                week=int(week_num) if week_num is not None else None,
                off_epa_per_play=off_epa_val,
                pass_epa_per_play=_to_decimal(row.get("pass_epa_per_play")),
                rush_epa_per_play=_to_decimal(row.get("rush_epa_per_play")),
                def_epa_per_play=def_epa_val,
                def_pass_epa_per_play=_to_decimal(row.get("def_pass_epa_per_play")),
                def_rush_epa_per_play=_to_decimal(row.get("def_rush_epa_per_play")),
                epa_differential=epa_diff,
                games_played=int(row.get("games_played", 1)),
                source=self.source_name,
            )

    def load_season_epa(self, season: int) -> Iterator[EPARecord]:
        """Load season-level EPA aggregates for all teams.

        Aggregates EPA across all weeks of the season for each team.

        Args:
            season: NFL season year

        Yields:
            EPARecord for each team (season total)

        Example:
            >>> source = NFLReadPySource()
            >>> season_epa = list(source.load_season_epa(2023))
            >>> len(season_epa)
            32  # One record per team
        """
        self._logger.info("Loading season EPA: season=%d", season)

        # Load all weekly EPA
        weekly_epa = list(self.load_epa(season=season, week=None))

        if not weekly_epa:
            return

        # Aggregate by team
        team_totals: dict[str, dict[str, Any]] = {}

        for record in weekly_epa:
            team_code = record["team_code"]
            if team_code not in team_totals:
                team_totals[team_code] = {
                    "off_epa_sum": Decimal("0"),
                    "pass_epa_sum": Decimal("0"),
                    "rush_epa_sum": Decimal("0"),
                    "def_epa_sum": Decimal("0"),
                    "def_pass_epa_sum": Decimal("0"),
                    "def_rush_epa_sum": Decimal("0"),
                    "games": 0,
                    "off_count": 0,
                    "pass_count": 0,
                    "rush_count": 0,
                    "def_count": 0,
                    "def_pass_count": 0,
                    "def_rush_count": 0,
                }

            totals = team_totals[team_code]
            totals["games"] += record["games_played"]

            # Sum EPA values (with null handling)
            if record["off_epa_per_play"] is not None:
                totals["off_epa_sum"] += record["off_epa_per_play"]
                totals["off_count"] += 1
            if record["pass_epa_per_play"] is not None:
                totals["pass_epa_sum"] += record["pass_epa_per_play"]
                totals["pass_count"] += 1
            if record["rush_epa_per_play"] is not None:
                totals["rush_epa_sum"] += record["rush_epa_per_play"]
                totals["rush_count"] += 1
            if record["def_epa_per_play"] is not None:
                totals["def_epa_sum"] += record["def_epa_per_play"]
                totals["def_count"] += 1
            if record["def_pass_epa_per_play"] is not None:
                totals["def_pass_epa_sum"] += record["def_pass_epa_per_play"]
                totals["def_pass_count"] += 1
            if record["def_rush_epa_per_play"] is not None:
                totals["def_rush_epa_sum"] += record["def_rush_epa_per_play"]
                totals["def_rush_count"] += 1

        # Calculate averages
        for team_code, totals in team_totals.items():
            off_epa = (
                (totals["off_epa_sum"] / totals["off_count"]).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
                if totals["off_count"] > 0
                else None
            )
            def_epa = (
                (totals["def_epa_sum"] / totals["def_count"]).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
                if totals["def_count"] > 0
                else None
            )

            epa_diff = off_epa - def_epa if off_epa and def_epa else None

            yield EPARecord(
                team_id=None,
                team_name="",
                team_code=team_code,
                season=season,
                week=None,  # Season total
                off_epa_per_play=off_epa,
                pass_epa_per_play=(
                    (totals["pass_epa_sum"] / totals["pass_count"]).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                    if totals["pass_count"] > 0
                    else None
                ),
                rush_epa_per_play=(
                    (totals["rush_epa_sum"] / totals["rush_count"]).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                    if totals["rush_count"] > 0
                    else None
                ),
                def_epa_per_play=def_epa,
                def_pass_epa_per_play=(
                    (totals["def_pass_epa_sum"] / totals["def_pass_count"]).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                    if totals["def_pass_count"] > 0
                    else None
                ),
                def_rush_epa_per_play=(
                    (totals["def_rush_epa_sum"] / totals["def_rush_count"]).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                    if totals["def_rush_count"] > 0
                    else None
                ),
                epa_differential=epa_diff,
                games_played=totals["games"],
                source=self.source_name,
            )

    # -------------------------------------------------------------------------
    # Capability Overrides
    # -------------------------------------------------------------------------

    def supports_games(self) -> bool:
        """nflreadpy provides game/schedule data."""
        return True

    def supports_odds(self) -> bool:
        """nflreadpy does NOT provide odds data directly."""
        return False

    def supports_elo(self) -> bool:
        """nflreadpy does NOT provide Elo ratings (we compute our own)."""
        return False

    def supports_epa(self) -> bool:
        """nflreadpy provides EPA metrics via play-by-play data."""
        return True
