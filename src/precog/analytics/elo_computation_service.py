"""
Elo Computation Service.

Computes Elo ratings from historical games and stores results in elo_calculation_log.
This is the orchestration layer that connects the EloEngine to the database.

Key Features:
    - Chronological game processing (required for Elo correctness)
    - Season-to-season rating regression (configurable)
    - Batch processing with progress tracking
    - Full audit trail in elo_calculation_log table
    - Support for incremental computation (skip already-processed games)

Design Decisions:
    - Pure Python implementation (no external dependencies beyond database)
    - Memory-efficient: Only track current ratings per team
    - Idempotent: Can re-run safely (uses UPSERT-like behavior)
    - All calculations use Decimal for precision (ADR-002)

Example Usage:
    >>> from precog.analytics.elo_computation_service import EloComputationService
    >>> from precog.database.connection import get_connection
    >>>
    >>> with get_connection() as conn:
    ...     service = EloComputationService(conn)
    ...     result = service.compute_ratings(sport="nfl", season=2020)
    ...     print(f"Processed {result.games_processed} games")

Reference: docs/guides/ELO_COMPUTATION_GUIDE_V1.1.md
Related ADR: ADR-109 (Elo Rating Computation Engine)
Related Requirements: REQ-ELO-001 through REQ-ELO-007

Created: 2025-12-26
Phase: 2.6 (Elo Rating Computation)
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from precog.analytics.elo_engine import (
    DEFAULT_INITIAL_RATING,
    EloEngine,
    EloUpdateResult,
)
from precog.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class TeamRatingState:
    """Current Elo rating state for a team.

    Attributes:
        rating: Current Elo rating
        games_played: Number of games played this computation run
        last_game_date: Date of most recent game
        peak_rating: Highest rating achieved
        lowest_rating: Lowest rating achieved
        initial_rating: Rating at start of computation
    """

    rating: Decimal
    games_played: int = 0
    last_game_date: date | None = None
    peak_rating: Decimal = field(default_factory=lambda: Decimal("1500"))
    lowest_rating: Decimal = field(default_factory=lambda: Decimal("1500"))
    initial_rating: Decimal = field(default_factory=lambda: Decimal("1500"))

    def __post_init__(self) -> None:
        """Initialize peak/lowest from current rating."""
        if self.peak_rating < self.rating:
            self.peak_rating = self.rating
        if self.lowest_rating > self.rating:
            self.lowest_rating = self.rating
        if self.initial_rating == Decimal("1500"):
            self.initial_rating = self.rating

    def update_after_game(self, new_rating: Decimal, game_date: date) -> None:
        """Update state after a game result.

        Args:
            new_rating: New Elo rating after the game
            game_date: Date of the game
        """
        self.rating = new_rating
        self.games_played += 1
        self.last_game_date = game_date

        if new_rating > self.peak_rating:
            self.peak_rating = new_rating
        if new_rating < self.lowest_rating:
            self.lowest_rating = new_rating


@dataclass
class ComputationResult:
    """Result of an Elo computation run.

    Attributes:
        sport: Sport processed
        seasons: Seasons processed
        games_processed: Number of games processed
        games_skipped: Number of games already computed (skipped)
        teams_updated: Number of unique teams with rating changes
        logs_inserted: Number of elo_calculation_log entries created
        duration_seconds: Time taken for computation
        errors: List of error messages (if any)
    """

    sport: str
    seasons: list[int]
    games_processed: int = 0
    games_skipped: int = 0
    teams_updated: int = 0
    logs_inserted: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sport": self.sport,
            "seasons": self.seasons,
            "games_processed": self.games_processed,
            "games_skipped": self.games_skipped,
            "teams_updated": self.teams_updated,
            "logs_inserted": self.logs_inserted,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
        }


# =============================================================================
# Elo Computation Service
# =============================================================================


class EloComputationService:
    """Service for computing Elo ratings from historical games.

    Educational Note:
        This service implements the FiveThirtyEight-style Elo rating system.
        Key properties:
        1. Games MUST be processed chronologically for correct ratings
        2. Ratings are zero-sum (points gained = points lost)
        3. Season boundaries trigger regression to mean

    Example:
        >>> from precog.database.connection import get_connection
        >>> with get_connection() as conn:
        ...     service = EloComputationService(conn)
        ...     result = service.compute_ratings(sport="nfl")
        ...     print(f"Computed {result.games_processed} games")
    """

    def __init__(
        self,
        conn: Any,
        initial_rating: Decimal = DEFAULT_INITIAL_RATING,
        apply_season_regression: bool = True,
        calculation_source: str = "bootstrap",
        calculation_version: str = "1.0",
    ) -> None:
        """Initialize the Elo computation service.

        Args:
            conn: Database connection (psycopg2 connection object)
            initial_rating: Starting Elo for new teams (default 1500)
            apply_season_regression: Whether to regress ratings at season boundaries
            calculation_source: Source label for audit trail
            calculation_version: Algorithm version for audit trail
        """
        self.conn = conn
        self.initial_rating = initial_rating
        self.apply_season_regression = apply_season_regression
        self.calculation_source = calculation_source
        self.calculation_version = calculation_version

        # Team ratings cache: sport -> team_code -> TeamRatingState
        self._ratings: dict[str, dict[str, TeamRatingState]] = {}

    def get_or_create_rating(self, sport: str, team_code: str) -> TeamRatingState:
        """Get current rating for a team, creating if not exists.

        Args:
            sport: Sport code (nfl, nba, etc.)
            team_code: Team abbreviation

        Returns:
            TeamRatingState for the team
        """
        if sport not in self._ratings:
            self._ratings[sport] = {}

        if team_code not in self._ratings[sport]:
            self._ratings[sport][team_code] = TeamRatingState(
                rating=self.initial_rating,
                initial_rating=self.initial_rating,
                peak_rating=self.initial_rating,
                lowest_rating=self.initial_rating,
            )

        return self._ratings[sport][team_code]

    def _fetch_historical_games(
        self,
        sport: str,
        seasons: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical games sorted chronologically.

        Args:
            sport: Sport code
            seasons: Optional list of seasons to filter

        Returns:
            List of game dictionaries sorted by date
        """
        cursor = self.conn.cursor()

        query = """
            SELECT
                historical_game_id,
                game_date,
                season,
                home_team_code,
                away_team_code,
                home_score,
                away_score,
                game_type,
                is_neutral_site
            FROM historical_games
            WHERE sport = %s
        """
        params: list[Any] = [sport]

        if seasons:
            query += " AND season = ANY(%s)"
            params.append(seasons)

        query += " ORDER BY game_date ASC, historical_game_id ASC"

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        games = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        logger.info(
            "fetched_games_for_elo",
            sport=sport,
            seasons=seasons,
            game_count=len(games),
        )

        return games

    def _get_already_computed_games(self, sport: str) -> set[int]:
        """Get set of historical_game_ids already computed.

        Args:
            sport: Sport code

        Returns:
            Set of historical_game_id values already in elo_calculation_log
        """
        cursor = self.conn.cursor()

        query = """
            SELECT historical_game_id
            FROM elo_calculation_log
            WHERE sport = %s AND historical_game_id IS NOT NULL
        """
        cursor.execute(query, [sport])

        return {row[0] for row in cursor.fetchall()}

    def _insert_elo_log(
        self,
        game: dict[str, Any],
        result: EloUpdateResult,
    ) -> None:
        """Insert an entry into elo_calculation_log.

        Args:
            game: Game dictionary from historical_games
            result: EloUpdateResult from the calculation
        """
        cursor = self.conn.cursor()

        query = """
            INSERT INTO elo_calculation_log (
                historical_game_id,
                sport,
                game_date,
                home_team_code,
                away_team_code,
                home_score,
                away_score,
                home_elo_before,
                away_elo_before,
                k_factor,
                home_advantage,
                mov_multiplier,
                home_expected,
                away_expected,
                home_actual,
                away_actual,
                home_elo_change,
                away_elo_change,
                home_elo_after,
                away_elo_after,
                calculation_source,
                calculation_version
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        # Determine sport from game data
        sport = game.get("sport") or self._current_sport

        params = [
            game["historical_game_id"],
            sport,
            game["game_date"],
            game["home_team_code"],
            game["away_team_code"],
            game["home_score"],
            game["away_score"],
            result.home_elo_before,
            result.away_elo_before,
            result.k_factor,
            result.home_advantage,
            result.mov_multiplier,
            result.home_expected,
            result.away_expected,
            result.home_actual,
            result.away_actual,
            result.home_elo_change,
            result.away_elo_change,
            result.home_elo_after,
            result.away_elo_after,
            self.calculation_source,
            self.calculation_version,
        ]

        cursor.execute(query, params)

    def compute_ratings(
        self,
        sport: str,
        seasons: list[int] | None = None,
        skip_computed: bool = True,
        commit_interval: int = 100,
    ) -> ComputationResult:
        """Compute Elo ratings for historical games.

        Educational Note:
            This method processes games chronologically to build up team ratings.
            Each game updates both teams' ratings based on the outcome.
            Results are stored in elo_calculation_log for audit trail.

        Args:
            sport: Sport code (nfl, nba, nhl, mlb)
            seasons: Optional list of seasons to process (default: all)
            skip_computed: If True, skip games already in elo_calculation_log
            commit_interval: Commit after this many games (for large datasets)

        Returns:
            ComputationResult with statistics

        Example:
            >>> result = service.compute_ratings(sport="nfl", seasons=[2019, 2020])
            >>> print(f"Processed {result.games_processed} games")
        """
        import time

        start_time = time.time()

        # Store current sport for log insertion
        self._current_sport = sport

        # Initialize result
        result = ComputationResult(
            sport=sport,
            seasons=seasons or [],
        )

        # Create Elo engine for this sport
        try:
            engine = EloEngine(sport)
        except ValueError as e:
            result.errors.append(str(e))
            return result

        # Fetch games
        games = self._fetch_historical_games(sport, seasons)
        if not games:
            logger.warning("no_games_found", sport=sport, seasons=seasons)
            result.duration_seconds = time.time() - start_time
            return result

        # If no seasons specified, extract from games
        if not result.seasons:
            result.seasons = sorted({g["season"] for g in games})

        # Get already computed games
        computed_ids: set[int] = set()
        if skip_computed:
            computed_ids = self._get_already_computed_games(sport)
            logger.info(
                "found_computed_games",
                sport=sport,
                count=len(computed_ids),
            )

        # Track current season for regression
        current_season: int | None = None

        # Process games chronologically
        for i, game in enumerate(games):
            game_id = game["historical_game_id"]

            # Skip if already computed
            if skip_computed and game_id in computed_ids:
                result.games_skipped += 1
                continue

            # Check for season boundary (apply regression)
            game_season = game["season"]
            if (
                current_season is not None
                and game_season != current_season
                and self.apply_season_regression
            ):
                self._apply_season_regression(sport, engine)
                logger.info(
                    "applied_season_regression",
                    sport=sport,
                    from_season=current_season,
                    to_season=game_season,
                )
            current_season = game_season

            # Get current ratings for both teams
            home_code = game["home_team_code"]
            away_code = game["away_team_code"]

            home_state = self.get_or_create_rating(sport, home_code)
            away_state = self.get_or_create_rating(sport, away_code)

            # Compute Elo update
            is_playoff = game.get("game_type", "regular") != "regular"
            is_neutral_site = game.get("is_neutral_site", False) or False

            elo_result = engine.update_ratings(
                home_elo=home_state.rating,
                away_elo=away_state.rating,
                home_score=game["home_score"],
                away_score=game["away_score"],
                is_playoff=is_playoff,
                neutral_site=is_neutral_site,
            )

            # Update team states
            home_state.update_after_game(elo_result.home_elo_after, game["game_date"])
            away_state.update_after_game(elo_result.away_elo_after, game["game_date"])

            # Insert log entry
            self._insert_elo_log(game, elo_result)
            result.games_processed += 1
            result.logs_inserted += 1

            # Commit periodically
            if result.games_processed % commit_interval == 0:
                self.conn.commit()
                logger.info(
                    "elo_computation_progress",
                    sport=sport,
                    processed=result.games_processed,
                    total=len(games),
                    pct=round(100 * result.games_processed / len(games), 1),
                )

        # Final commit
        self.conn.commit()

        # Count unique teams
        if sport in self._ratings:
            result.teams_updated = len(self._ratings[sport])

        result.duration_seconds = time.time() - start_time

        logger.info(
            "elo_computation_complete",
            sport=sport,
            games_processed=result.games_processed,
            games_skipped=result.games_skipped,
            teams=result.teams_updated,
            duration_s=round(result.duration_seconds, 2),
        )

        return result

    def _apply_season_regression(self, sport: str, engine: EloEngine) -> None:
        """Apply season-to-season regression for all teams in a sport.

        Args:
            sport: Sport code
            engine: EloEngine instance for this sport
        """
        if sport not in self._ratings:
            return

        for team_code, state in self._ratings[sport].items():
            old_rating = state.rating
            new_rating = engine.apply_season_regression(old_rating)
            state.rating = new_rating

    def get_team_ratings(self, sport: str) -> dict[str, Decimal]:
        """Get current ratings for all teams in a sport.

        Args:
            sport: Sport code

        Returns:
            Dictionary mapping team_code to current Elo rating
        """
        if sport not in self._ratings:
            return {}

        return {team_code: state.rating for team_code, state in self._ratings[sport].items()}

    def get_team_rating_details(self, sport: str) -> dict[str, dict[str, Any]]:
        """Get detailed rating info for all teams in a sport.

        Args:
            sport: Sport code

        Returns:
            Dictionary with team details (rating, games, peak, etc.)
        """
        if sport not in self._ratings:
            return {}

        return {
            team_code: {
                "rating": state.rating,
                "games_played": state.games_played,
                "initial_rating": state.initial_rating,
                "peak_rating": state.peak_rating,
                "lowest_rating": state.lowest_rating,
                "rating_change": (state.rating - state.initial_rating).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
            }
            for team_code, state in self._ratings[sport].items()
        }

    def clear_ratings_cache(self, sport: str | None = None) -> None:
        """Clear the in-memory ratings cache.

        Args:
            sport: If specified, only clear this sport. Otherwise clear all.
        """
        if sport:
            self._ratings.pop(sport, None)
        else:
            self._ratings.clear()


# =============================================================================
# Convenience Functions
# =============================================================================


def compute_elo_ratings(
    conn: Any,
    sport: str,
    seasons: list[int] | None = None,
    skip_computed: bool = True,
) -> ComputationResult:
    """Convenience function to compute Elo ratings.

    Args:
        conn: Database connection
        sport: Sport code
        seasons: Optional list of seasons
        skip_computed: Skip already-computed games

    Returns:
        ComputationResult with statistics
    """
    service = EloComputationService(conn)
    return service.compute_ratings(sport, seasons, skip_computed)


def get_elo_computation_stats(conn: Any) -> dict[str, Any]:
    """Get statistics about Elo computations in the database.

    Args:
        conn: Database connection

    Returns:
        Dictionary with computation statistics
    """
    cursor = conn.cursor()

    # Count by sport
    cursor.execute("""
        SELECT sport, COUNT(*) as count, MIN(game_date) as first_date, MAX(game_date) as last_date
        FROM elo_calculation_log
        GROUP BY sport
        ORDER BY sport
    """)

    by_sport = {}
    for row in cursor.fetchall():
        by_sport[row[0]] = {
            "count": row[1],
            "first_date": str(row[2]) if row[2] else None,
            "last_date": str(row[3]) if row[3] else None,
        }

    # Total count
    cursor.execute("SELECT COUNT(*) FROM elo_calculation_log")
    total = cursor.fetchone()[0]

    return {
        "total_calculations": total,
        "by_sport": by_sport,
    }
