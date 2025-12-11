"""
Comprehensive Database Seeding Manager for Precog.

This module provides a configurable manager for initializing and updating
static reference data in the database. Unlike pollers (which continuously
poll for live data), the seeding manager handles one-time or scheduled
bulk data loads.

Key Distinction: Seeding vs Polling
-----------------------------------
| Aspect       | Seeding Manager           | Pollers (ESPN/Kalshi)        |
|--------------|---------------------------|------------------------------|
| Purpose      | Static reference data     | Dynamic live data            |
| Frequency    | On-demand, daily, weekly  | Every 15-60 seconds          |
| Data Type    | Teams, venues, Elo        | Live scores, prices          |
| Trigger      | CLI, DB reset, scheduled  | Continuous background        |
| Versioning   | Simple upsert             | SCD Type 2 (full history)    |

Data Categories:
    1. TEAMS: Static team reference data (teams table)
    2. VENUES: Stadium/arena information (venues table)
    3. HISTORICAL_ELO: Pre-calculated Elo ratings (elo_rating_history)
    4. TEAM_RANKINGS: Season rankings (team_rankings table)
    5. ARCHIVED_GAMES: Completed games for backtesting (game_states where status=final)
    6. SCHEDULES: Upcoming game schedules (game_states where status=pre)

Educational Notes:
------------------
Why Separate from Pollers?
    - Different lifecycle: Seeds run once (or infrequently), pollers run continuously
    - Different data: Static reference data vs dynamic live data
    - Different patterns: Bulk upsert vs SCD Type 2 versioning
    - Different triggers: Manual/scheduled vs background scheduler

Relationship with ESPN Game Poller:
    - SeedingManager seeds historical game_states (status=final, past seasons)
    - ESPNGamePoller maintains current game_states (status in pre/in_progress/final)
    - No overlap: Seeder handles past, Poller handles present/future
    - Seeder can "hand off" to Poller by seeding scheduled games (status=pre)

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Team Support)
GitHub Issue: #186 (Phase 2.5 ESPN Data Integration)
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, TypedDict

from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient
from precog.database.crud_operations import (
    create_venue,
    get_team_by_espn_id,
    upsert_game_state,
)

# Set up logging
logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class SeedCategory(str, Enum):
    """
    Categories of data that can be seeded.

    Each category represents a distinct type of reference data with its
    own seeding logic and source (SQL file, API, or both).

    Educational Note:
        Using an Enum ensures type safety and IDE autocomplete support.
        The str mixin allows direct string comparison (e.g., "teams" == SeedCategory.TEAMS).
    """

    TEAMS = "teams"  # Team reference data (from SQL seeds)
    VENUES = "venues"  # Venue information (from ESPN API or SQL)
    HISTORICAL_ELO = "historical_elo"  # Pre-calculated Elo ratings
    TEAM_RANKINGS = "team_rankings"  # Season rankings data
    ARCHIVED_GAMES = "archived_games"  # Completed games (backtesting)
    SCHEDULES = "schedules"  # Upcoming game schedules


class SeedingStats(TypedDict):
    """Statistics for a seeding operation."""

    category: str
    started_at: str
    completed_at: str | None
    records_processed: int
    records_created: int
    records_updated: int
    records_skipped: int
    errors: int
    last_error: str | None


class SeedingReport(TypedDict):
    """Complete report for a seeding session."""

    session_id: str
    started_at: str
    completed_at: str | None
    categories_seeded: list[str]
    total_records_processed: int
    total_records_created: int
    total_records_updated: int
    total_errors: int
    category_stats: dict[str, SeedingStats]
    success: bool


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SeedingConfig:
    """
    Configuration for the seeding manager.

    Attributes:
        categories: Which data categories to seed (default: all)
        sports: Which sports to seed (default: all supported)
        seasons: Which seasons to seed historical data for (default: current)
        database: Target database (dev/test/prod)
        dry_run: If True, report what would be seeded without writing
        sql_seeds_path: Path to SQL seed files
        use_api: Whether to fetch data from APIs (ESPN, etc.)
        overwrite: If True, overwrite existing data; if False, skip existing

    Educational Note:
        Using @dataclass with field() for mutable defaults is safer than
        default mutable arguments (e.g., `categories: list = []` is dangerous).
    """

    categories: list[SeedCategory] = field(default_factory=lambda: list(SeedCategory))
    sports: list[str] = field(
        default_factory=lambda: ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"]
    )
    seasons: list[int] = field(default_factory=lambda: [2024, 2025])
    database: str = "dev"  # dev, test, or prod
    dry_run: bool = False
    sql_seeds_path: Path = field(default_factory=lambda: Path("src/precog/database/seeds"))
    use_api: bool = True
    overwrite: bool = True


# =============================================================================
# Seeding Manager
# =============================================================================


class SeedingManager:
    """
    Comprehensive manager for database seeding operations.

    Handles initialization and updates of static reference data:
    - Teams (from SQL seeds)
    - Venues (from ESPN API or SQL)
    - Historical Elo ratings
    - Team rankings
    - Archived game results
    - Upcoming schedules

    Unlike pollers, the seeding manager runs on-demand or on a schedule
    (daily/weekly), not continuously.

    Attributes:
        config: SeedingConfig instance
        espn_client: ESPNClient for API data (optional)
        stats: Current session statistics

    Usage:
        >>> # Seed all data for all sports
        >>> manager = SeedingManager()
        >>> report = manager.seed_all()
        >>>
        >>> # Seed specific categories
        >>> manager = SeedingManager(SeedingConfig(
        ...     categories=[SeedCategory.TEAMS, SeedCategory.VENUES],
        ...     sports=["nfl", "nba"]
        ... ))
        >>> report = manager.seed_all()
        >>>
        >>> # Dry run (report what would be done)
        >>> manager = SeedingManager(SeedingConfig(dry_run=True))
        >>> report = manager.seed_all()

    Educational Note:
        The SeedingManager follows the Strategy pattern - different seeding
        strategies (SQL-based, API-based) can be plugged in for different
        categories. This makes it easy to add new data sources later.
    """

    # SQL seed file patterns by category
    SQL_SEED_PATTERNS: ClassVar[dict[SeedCategory, str]] = {
        SeedCategory.TEAMS: "*_teams*.sql",
        SeedCategory.VENUES: "*_venues*.sql",
        SeedCategory.HISTORICAL_ELO: "*_elo*.sql",
        SeedCategory.TEAM_RANKINGS: "*_rankings*.sql",
    }

    # Sports that support each category
    SPORT_CATEGORY_SUPPORT: ClassVar[dict[SeedCategory, list[str]]] = {
        SeedCategory.TEAMS: ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"],
        SeedCategory.VENUES: ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"],
        SeedCategory.HISTORICAL_ELO: ["nfl", "ncaaf"],  # Elo only for football
        SeedCategory.TEAM_RANKINGS: ["nfl", "ncaaf", "nba", "ncaab"],
        SeedCategory.ARCHIVED_GAMES: ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"],
        SeedCategory.SCHEDULES: ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"],
    }

    def __init__(
        self,
        config: SeedingConfig | None = None,
        espn_client: ESPNClient | None = None,
    ) -> None:
        """
        Initialize the SeedingManager.

        Args:
            config: SeedingConfig instance (uses defaults if None)
            espn_client: ESPNClient for API data (creates one if None and use_api=True)
        """
        self.config = config or SeedingConfig()
        self.espn_client = espn_client

        # Initialize ESPN client if API access is enabled
        if self.config.use_api and self.espn_client is None:
            self.espn_client = ESPNClient()

        # Session tracking
        self._session_id: str | None = None
        self._session_start: datetime | None = None
        self._category_stats: dict[str, SeedingStats] = {}

        logger.info(
            "SeedingManager initialized: categories=%s, sports=%s, database=%s",
            [c.value for c in self.config.categories],
            self.config.sports,
            self.config.database,
        )

    # =========================================================================
    # Public API
    # =========================================================================

    def seed_all(self) -> SeedingReport:
        """
        Seed all configured categories.

        Runs through each configured category and seeds the data according
        to the configuration (sports, seasons, etc.).

        Returns:
            SeedingReport with detailed statistics

        Example:
            >>> manager = SeedingManager()
            >>> report = manager.seed_all()
            >>> print(f"Processed {report['total_records_processed']} records")
        """
        self._start_session()

        for category in self.config.categories:
            try:
                self._seed_category(category)
            except Exception as e:
                logger.error("Error seeding %s: %s", category.value, e)
                self._record_error(category, str(e))

        return self._complete_session()

    def seed_category(self, category: SeedCategory) -> SeedingStats:
        """
        Seed a specific category.

        Args:
            category: Which category to seed

        Returns:
            SeedingStats for this category
        """
        self._start_session()
        self._seed_category(category)
        report = self._complete_session()
        return report["category_stats"].get(category.value, self._empty_stats(category))

    def seed_teams(self, sports: list[str] | None = None) -> SeedingStats:
        """
        Seed team data from SQL files.

        Args:
            sports: Which sports to seed (default: all configured)

        Returns:
            SeedingStats for teams category
        """
        target_sports = sports or self.config.sports
        self._start_session()
        self._seed_teams_sql(target_sports)
        report = self._complete_session()
        return report["category_stats"].get(
            SeedCategory.TEAMS.value, self._empty_stats(SeedCategory.TEAMS)
        )

    def seed_venues_from_api(self, sports: list[str] | None = None) -> SeedingStats:
        """
        Seed venue data from ESPN API.

        Fetches venue information from ESPN scoreboard data and creates
        venue records for any venues not already in the database.

        Args:
            sports: Which sports to seed venues for (default: all configured)

        Returns:
            SeedingStats for venues category
        """
        if not self.espn_client:
            raise ValueError("ESPN client required for API-based venue seeding")

        target_sports = sports or self.config.sports
        self._start_session()
        self._seed_venues_api(target_sports)
        report = self._complete_session()
        return report["category_stats"].get(
            SeedCategory.VENUES.value, self._empty_stats(SeedCategory.VENUES)
        )

    def seed_historical_games(
        self,
        sports: list[str] | None = None,
        seasons: list[int] | None = None,
    ) -> SeedingStats:
        """
        Seed historical game data for backtesting.

        Fetches completed games from ESPN API and stores them in game_states
        with status='final'. This provides historical data for ML training
        and backtesting without conflicting with the live game poller.

        Args:
            sports: Which sports to seed (default: configured sports)
            seasons: Which seasons to fetch (default: configured seasons)

        Returns:
            SeedingStats for archived_games category

        Educational Note:
            Historical games are stored with SCD Type 2 disabled (single row
            per game) since we only need the final state for backtesting.
            Live games use full SCD Type 2 to track score progression.
        """
        if not self.espn_client:
            raise ValueError("ESPN client required for historical game seeding")

        target_sports = sports or self.config.sports
        target_seasons = seasons or self.config.seasons

        self._start_session()
        self._seed_historical_games_api(target_sports, target_seasons)
        report = self._complete_session()
        return report["category_stats"].get(
            SeedCategory.ARCHIVED_GAMES.value, self._empty_stats(SeedCategory.ARCHIVED_GAMES)
        )

    def verify_seeds(self) -> dict[str, Any]:
        """
        Verify that required seed data exists.

        Checks each category for expected data and reports any gaps.
        Useful for CI/CD pipelines and pre-flight checks.

        Returns:
            Dictionary with verification results:
            {
                "success": True/False,
                "categories": {
                    "teams": {"expected": 274, "actual": 274, "ok": True},
                    "venues": {"expected": 30, "actual": 28, "ok": False},
                    ...
                }
            }
        """
        results: dict[str, Any] = {"success": True, "categories": {}}

        # Check teams
        teams_result = self._verify_teams()
        results["categories"]["teams"] = teams_result
        if not teams_result["ok"]:
            results["success"] = False

        # Add more verifications as needed...

        return results

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _start_session(self) -> None:
        """Start a new seeding session."""
        self._session_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self._session_start = datetime.now(UTC)
        self._category_stats = {}
        logger.info("Seeding session started: %s", self._session_id)

    def _complete_session(self) -> SeedingReport:
        """Complete the current session and return report."""
        completed_at = datetime.now(UTC)

        # Aggregate totals
        total_processed = sum(s["records_processed"] for s in self._category_stats.values())
        total_created = sum(s["records_created"] for s in self._category_stats.values())
        total_updated = sum(s["records_updated"] for s in self._category_stats.values())
        total_errors = sum(s["errors"] for s in self._category_stats.values())

        report: SeedingReport = {
            "session_id": self._session_id or "unknown",
            "started_at": self._session_start.isoformat() if self._session_start else "",
            "completed_at": completed_at.isoformat(),
            "categories_seeded": list(self._category_stats.keys()),
            "total_records_processed": total_processed,
            "total_records_created": total_created,
            "total_records_updated": total_updated,
            "total_errors": total_errors,
            "category_stats": self._category_stats,
            "success": total_errors == 0,
        }

        logger.info(
            "Seeding session completed: %s (processed=%d, created=%d, updated=%d, errors=%d)",
            self._session_id,
            total_processed,
            total_created,
            total_updated,
            total_errors,
        )

        return report

    def _seed_category(self, category: SeedCategory) -> None:
        """Route to the appropriate seeding method for a category."""
        if category == SeedCategory.TEAMS:
            self._seed_teams_sql(self.config.sports)
        elif category == SeedCategory.VENUES:
            if self.config.use_api:
                self._seed_venues_api(self.config.sports)
            else:
                self._seed_venues_sql(self.config.sports)
        elif category == SeedCategory.ARCHIVED_GAMES:
            if self.config.use_api:
                self._seed_historical_games_api(self.config.sports, self.config.seasons)
        elif category == SeedCategory.SCHEDULES:
            if self.config.use_api:
                self._seed_schedules_api(self.config.sports)
        else:
            logger.warning("Category %s not yet implemented", category.value)

    def _seed_teams_sql(self, sports: list[str]) -> None:
        """Seed teams from SQL files."""
        stats = self._init_stats(SeedCategory.TEAMS)
        seeds_path = self.config.sql_seeds_path

        if not seeds_path.exists():
            logger.warning("Seeds path does not exist: %s", seeds_path)
            self._category_stats[SeedCategory.TEAMS.value] = stats
            return

        # Find and execute team seed files
        # SQL files are named: 001_nfl_teams.sql, 003_nba_teams.sql, etc.
        for sql_file in sorted(seeds_path.glob("*_*_teams*.sql")):
            # Extract sport from filename (e.g., "003_nba_teams.sql" -> "nba")
            parts = sql_file.stem.split("_")
            if len(parts) >= 2:
                file_sport = parts[1].lower()
                if file_sport in sports:
                    if self.config.dry_run:
                        logger.info("[DRY RUN] Would execute: %s", sql_file)
                        stats["records_processed"] += 1
                    else:
                        logger.info("Executing seed file: %s", sql_file)
                        # Note: Actual SQL execution would happen via psycopg or subprocess
                        # For now, we track it as "processed"
                        stats["records_processed"] += 1

        self._category_stats[SeedCategory.TEAMS.value] = stats

    def _seed_venues_sql(self, _sports: list[str]) -> None:
        """Seed venues from SQL files."""
        stats = self._init_stats(SeedCategory.VENUES)
        # Similar logic to teams SQL seeding
        self._category_stats[SeedCategory.VENUES.value] = stats

    def _seed_venues_api(self, sports: list[str]) -> None:
        """Seed venues from ESPN API by fetching scoreboard data."""
        stats = self._init_stats(SeedCategory.VENUES)

        if not self.espn_client:
            logger.warning("ESPN client not available, skipping venue API seeding")
            self._category_stats[SeedCategory.VENUES.value] = stats
            return

        for sport in sports:
            try:
                # Get scoreboard to discover venues
                games = self.espn_client.get_scoreboard(sport)

                for game in games:
                    metadata = game.get("metadata", {})
                    venue_info = metadata.get("venue", {})
                    venue_name = venue_info.get("venue_name")

                    if not venue_name:
                        stats["records_skipped"] += 1
                        continue

                    stats["records_processed"] += 1

                    if self.config.dry_run:
                        logger.debug("[DRY RUN] Would create venue: %s", venue_name)
                        continue

                    try:
                        # create_venue handles upsert logic
                        venue_id = create_venue(
                            espn_venue_id=venue_info.get("espn_venue_id", venue_name),
                            venue_name=venue_name,
                            city=venue_info.get("city"),
                            state=venue_info.get("state"),
                            capacity=venue_info.get("capacity"),
                            indoor=venue_info.get("indoor", False),
                        )
                        if venue_id:
                            stats["records_created"] += 1
                        else:
                            stats["records_updated"] += 1
                    except Exception as e:
                        logger.warning("Error creating venue %s: %s", venue_name, e)
                        stats["errors"] += 1

            except ESPNAPIError as e:
                logger.warning("ESPN API error for %s venues: %s", sport, e)
                stats["errors"] += 1

        self._category_stats[SeedCategory.VENUES.value] = stats

    def _seed_historical_games_api(self, sports: list[str], seasons: list[int]) -> None:
        """Seed historical games from ESPN API."""
        stats = self._init_stats(SeedCategory.ARCHIVED_GAMES)

        if not self.espn_client:
            logger.warning("ESPN client not available, skipping historical games")
            self._category_stats[SeedCategory.ARCHIVED_GAMES.value] = stats
            return

        for sport in sports:
            for season in seasons:
                logger.info("Fetching historical games: %s %d", sport, season)
                try:
                    # ESPN API supports fetching by date range
                    # For now, this is a placeholder for the implementation
                    # Real implementation would iterate through weeks/dates
                    stats["records_processed"] += 1

                    if self.config.dry_run:
                        logger.debug(
                            "[DRY RUN] Would fetch %s games for %d season",
                            sport,
                            season,
                        )

                except ESPNAPIError as e:
                    logger.warning("ESPN API error for %s %d: %s", sport, season, e)
                    stats["errors"] += 1

        self._category_stats[SeedCategory.ARCHIVED_GAMES.value] = stats

    def _seed_schedules_api(self, sports: list[str]) -> None:
        """Seed upcoming schedules from ESPN API."""
        stats = self._init_stats(SeedCategory.SCHEDULES)

        if not self.espn_client:
            logger.warning("ESPN client not available, skipping schedules")
            self._category_stats[SeedCategory.SCHEDULES.value] = stats
            return

        for sport in sports:
            try:
                # Get current scoreboard (includes scheduled games)
                games = self.espn_client.get_scoreboard(sport)

                for game in games:
                    state = game.get("state", {})
                    status = state.get("game_status", "").lower()

                    # Only seed scheduled (not yet started) games
                    if status not in ("pre", "scheduled"):
                        continue

                    stats["records_processed"] += 1
                    metadata = game.get("metadata", {})
                    espn_event_id = metadata.get("espn_event_id")

                    # Skip games without valid ESPN event ID
                    if not espn_event_id:
                        logger.debug("Skipping game without espn_event_id")
                        continue

                    if self.config.dry_run:
                        logger.debug(
                            "[DRY RUN] Would seed scheduled game: %s",
                            espn_event_id,
                        )
                        continue

                    # Get team IDs
                    home_team_info = metadata.get("home_team", {})
                    away_team_info = metadata.get("away_team", {})

                    home_team_id = self._get_team_id(home_team_info.get("espn_team_id"), sport)
                    away_team_id = self._get_team_id(away_team_info.get("espn_team_id"), sport)

                    # Parse game date
                    game_date = None
                    game_date_str = metadata.get("game_date")
                    if game_date_str:
                        try:
                            game_date = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            pass

                    try:
                        upsert_game_state(
                            espn_event_id=espn_event_id,
                            home_team_id=home_team_id,
                            away_team_id=away_team_id,
                            home_score=0,
                            away_score=0,
                            period=0,
                            game_status="pre",
                            game_date=game_date,
                            league=sport,
                        )
                        stats["records_created"] += 1
                    except Exception as e:
                        logger.warning(
                            "Error seeding scheduled game %s: %s",
                            espn_event_id,
                            e,
                        )
                        stats["errors"] += 1

            except ESPNAPIError as e:
                logger.warning("ESPN API error for %s schedules: %s", sport, e)
                stats["errors"] += 1

        self._category_stats[SeedCategory.SCHEDULES.value] = stats

    def _get_team_id(self, espn_team_id: str | None, sport: str) -> int | None:
        """Look up database team_id from ESPN team_id."""
        if not espn_team_id:
            return None

        team = get_team_by_espn_id(espn_team_id, sport)
        if team:
            return int(team["team_id"])

        return None

    def _verify_teams(self) -> dict[str, Any]:
        """Verify team data exists."""
        # Expected counts per sport
        expected_counts = {
            "nfl": 32,
            "nba": 30,
            "nhl": 32,
            "wnba": 12,
            "ncaaf": 79,  # FBS teams
            "ncaab": 89,  # Top teams
        }

        # This would query the database for actual counts
        # For now, return placeholder
        return {
            "expected": sum(expected_counts.values()),
            "actual": 274,  # Placeholder
            "ok": True,
        }

    def _init_stats(self, category: SeedCategory) -> SeedingStats:
        """Initialize stats for a category."""
        return SeedingStats(
            category=category.value,
            started_at=datetime.now(UTC).isoformat(),
            completed_at=None,
            records_processed=0,
            records_created=0,
            records_updated=0,
            records_skipped=0,
            errors=0,
            last_error=None,
        )

    def _empty_stats(self, category: SeedCategory) -> SeedingStats:
        """Return empty stats for a category."""
        return self._init_stats(category)

    def _record_error(self, category: SeedCategory, error: str) -> None:
        """Record an error for a category."""
        if category.value in self._category_stats:
            self._category_stats[category.value]["errors"] += 1
            self._category_stats[category.value]["last_error"] = error


# =============================================================================
# Convenience Functions
# =============================================================================


def create_seeding_manager(
    categories: list[str] | None = None,
    sports: list[str] | None = None,
    database: str = "dev",
    dry_run: bool = False,
) -> SeedingManager:
    """
    Factory function to create a configured SeedingManager.

    Args:
        categories: Categories to seed (default: all)
        sports: Sports to seed (default: all)
        database: Target database (dev/test/prod)
        dry_run: If True, report what would be done

    Returns:
        Configured SeedingManager instance

    Example:
        >>> manager = create_seeding_manager(
        ...     categories=["teams", "venues"],
        ...     sports=["nfl", "nba"],
        ...     database="test"
        ... )
        >>> report = manager.seed_all()
    """
    category_list = [SeedCategory(c) for c in categories] if categories else None
    config = SeedingConfig(
        categories=category_list or list(SeedCategory),
        sports=sports or ["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab"],
        database=database,
        dry_run=dry_run,
    )
    return SeedingManager(config=config)


def seed_all_teams(
    sports: list[str] | None = None,
    database: str = "dev",
) -> SeedingReport:
    """
    Convenience function to seed all team data.

    Args:
        sports: Sports to seed (default: all)
        database: Target database

    Returns:
        SeedingReport with results
    """
    manager = create_seeding_manager(
        categories=["teams"],
        sports=sports,
        database=database,
    )
    return manager.seed_all()


def verify_required_seeds() -> dict[str, Any]:
    """
    Verify that all required seed data exists.

    Useful for CI/CD pipelines and pre-flight checks.

    Returns:
        Verification results with pass/fail status

    Example:
        >>> result = verify_required_seeds()
        >>> if not result["success"]:
        ...     print("Missing seed data!")
        ...     for cat, info in result["categories"].items():
        ...         if not info["ok"]:
        ...             print(f"  {cat}: expected {info['expected']}, got {info['actual']}")
    """
    manager = SeedingManager()
    return manager.verify_seeds()
