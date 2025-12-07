"""
Live game state polling service using APScheduler.

This module provides the MarketUpdater class that polls ESPN APIs at configurable
intervals and syncs game states to the database using SCD Type 2 versioning.

Key Features:
- APScheduler-based polling (configurable 15-60 second intervals)
- Conditional polling (only runs when games are active)
- Multi-league support (NFL, NCAAF, NBA, NCAAB, NHL, WNBA)
- Error recovery with logging
- Clean shutdown handling
- Thread-safe operation

Educational Notes:
------------------
APScheduler vs alternatives:
    - APScheduler: Production-grade, supports persistence, cron, intervals
    - schedule library: Simpler but less robust, no persistence
    - asyncio: Good for async code, but we're using sync database operations

Polling Strategy:
    - 15 seconds: Default for live games (captures most score changes)
    - 60 seconds: Reduced rate when no games active (saves API calls)
    - 0 seconds: Paused when outside game windows

SCD Type 2 benefits:
    - Every score change creates a new row (full game history)
    - Enables ML training on score progression
    - Provides audit trail for trading decisions

Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
Related Requirements:
    - Phase 2: Live Data Integration
    - REQ-DATA-001: Game State Data Collection
"""

import logging
import signal
import sys
import threading
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar, TypedDict

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from precog.api_connectors.espn_client import (
    ESPNAPIError,
    ESPNClient,
    ESPNGameFull,
    ESPNTeamInfo,
    ESPNVenueInfo,
)
from precog.database.crud_operations import (
    create_venue,
    get_live_games,
    get_team_by_espn_id,
    upsert_game_state,
)

# Set up logging
logger = logging.getLogger(__name__)


class _UpdaterStats(TypedDict):
    """Type definition for updater statistics."""

    polls_completed: int
    games_updated: int
    errors: int
    last_poll: str | None
    last_error: str | None


class MarketUpdater:
    """
    Live game state polling service.

    Polls ESPN APIs at regular intervals and syncs game states to the database.
    Uses APScheduler for reliable job scheduling with automatic retry on errors.

    Attributes:
        leagues: List of leagues to poll (default: ["nfl", "ncaaf"])
        poll_interval: Seconds between polls when games active (default: 15)
        idle_interval: Seconds between checks when no games active (default: 60)
        enabled: Whether polling is currently enabled

    Usage:
        >>> # Basic usage
        >>> updater = MarketUpdater()
        >>> updater.start()
        >>> # ... polling runs in background ...
        >>> updater.stop()
        >>>
        >>> # Custom configuration
        >>> updater = MarketUpdater(
        ...     leagues=["nfl", "nba"],
        ...     poll_interval=30,
        ...     idle_interval=120
        ... )
        >>> updater.start()

    Educational Note:
        The updater uses a BackgroundScheduler which runs jobs in a thread pool.
        This allows the main application to continue running while polls happen
        in the background. The scheduler handles job execution, retries, and
        timing automatically.

    Reference: Phase 2 Live Data Integration
    """

    # Default configuration
    DEFAULT_LEAGUES: ClassVar[list[str]] = ["nfl", "ncaaf"]
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 15  # seconds
    DEFAULT_IDLE_INTERVAL: ClassVar[int] = 60  # seconds

    # Game status mappings
    LIVE_STATUSES: ClassVar[set[str]] = {"in", "in_progress", "halftime"}
    COMPLETED_STATUSES: ClassVar[set[str]] = {"post", "final", "final/ot"}
    SCHEDULED_STATUSES: ClassVar[set[str]] = {"pre", "scheduled"}

    def __init__(
        self,
        leagues: list[str] | None = None,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        idle_interval: int = DEFAULT_IDLE_INTERVAL,
        espn_client: ESPNClient | None = None,
        persist_jobs: bool = False,
        job_store_url: str | None = None,
    ) -> None:
        """
        Initialize the MarketUpdater.

        Args:
            leagues: List of leagues to poll. Defaults to NFL and NCAAF.
            poll_interval: Seconds between polls when games are active.
            idle_interval: Seconds between checks when no games active.
            espn_client: Optional ESPNClient instance (for testing/mocking).
            persist_jobs: If True, persist scheduled jobs to database.
            job_store_url: SQLAlchemy URL for job store (required if persist_jobs=True).

        Raises:
            ValueError: If poll_interval < 5 or idle_interval < 15.
            ValueError: If persist_jobs=True but job_store_url not provided.

        Educational Note:
            Job persistence enables the scheduler to survive restarts. When enabled,
            scheduled jobs are stored in a SQLite/PostgreSQL database and restored
            when the scheduler starts again. This is important for production
            deployments where you don't want to miss polls during restarts.
        """
        if poll_interval < 5:
            raise ValueError("poll_interval must be at least 5 seconds")
        if idle_interval < 15:
            raise ValueError("idle_interval must be at least 15 seconds")
        if persist_jobs and not job_store_url:
            raise ValueError("job_store_url required when persist_jobs=True")

        self.leagues = leagues or self.DEFAULT_LEAGUES.copy()
        self.poll_interval = poll_interval
        self.idle_interval = idle_interval
        self.espn_client = espn_client or ESPNClient()
        self.persist_jobs = persist_jobs
        self.job_store_url = job_store_url

        # State tracking
        self._scheduler: BackgroundScheduler | None = None
        self._enabled = False
        self._lock = threading.Lock()
        self._stats: _UpdaterStats = {
            "polls_completed": 0,
            "games_updated": 0,
            "errors": 0,
            "last_poll": None,
            "last_error": None,
        }

        logger.info(
            "MarketUpdater initialized: leagues=%s, poll_interval=%ds, idle_interval=%ds, "
            "persist_jobs=%s",
            self.leagues,
            self.poll_interval,
            self.idle_interval,
            self.persist_jobs,
        )

    @property
    def enabled(self) -> bool:
        """Whether the updater is currently running."""
        return self._enabled

    @property
    def stats(self) -> _UpdaterStats:
        """Current statistics about polling activity."""
        with self._lock:
            return self._stats.copy()

    def start(self) -> None:
        """
        Start the polling scheduler.

        Initializes APScheduler and begins polling at the configured interval.
        The scheduler runs in a background thread, allowing the main program
        to continue execution.

        Raises:
            RuntimeError: If already started.

        Educational Note:
            We use BackgroundScheduler instead of BlockingScheduler because
            we want the calling code to continue executing. The scheduler
            manages its own thread pool for job execution.

            When job persistence is enabled via persist_jobs=True, jobs are
            stored in a SQLite/PostgreSQL database. This means:
            - Jobs survive scheduler restarts
            - Missed executions are tracked and handled
            - Multiple scheduler instances can share the same job store
        """
        with self._lock:
            if self._enabled:
                raise RuntimeError("MarketUpdater is already running")

            # Configure job stores if persistence is enabled
            jobstores = {}
            if self.persist_jobs and self.job_store_url:
                jobstores["default"] = SQLAlchemyJobStore(url=self.job_store_url)
                logger.info("Job persistence enabled with SQLAlchemy store")

            self._scheduler = BackgroundScheduler(
                jobstores=jobstores,
                job_defaults={
                    "coalesce": True,  # Combine missed runs into one
                    "max_instances": 1,  # Only one poll job at a time
                    "misfire_grace_time": 30,  # Grace period for late jobs
                },
            )

            # Add the polling job
            self._scheduler.add_job(
                self._poll_all_leagues,
                IntervalTrigger(seconds=self.poll_interval),
                id="poll_espn",
                name="ESPN Game State Poll",
                replace_existing=True,
            )

            self._scheduler.start()
            self._enabled = True

        logger.info("MarketUpdater started - polling every %d seconds", self.poll_interval)

        # Run initial poll immediately
        self._poll_all_leagues()

    def stop(self, wait: bool = True) -> None:
        """
        Stop the polling scheduler.

        Args:
            wait: If True, wait for running jobs to complete before returning.

        Educational Note:
            The 'wait' parameter is important for clean shutdown. Setting it
            to True ensures any in-progress database operations complete
            before the scheduler terminates.
        """
        with self._lock:
            if not self._enabled:
                logger.warning("MarketUpdater is not running")
                return

            if self._scheduler:
                self._scheduler.shutdown(wait=wait)
                self._scheduler = None

            self._enabled = False

        logger.info("MarketUpdater stopped")

    def poll_once(self, leagues: list[str] | None = None) -> dict[str, int]:
        """
        Execute a single poll cycle manually.

        Useful for testing or on-demand updates outside the scheduled interval.

        Args:
            leagues: Optional list of leagues to poll. Defaults to configured leagues.

        Returns:
            Dictionary with counts: {"games_fetched": N, "games_updated": M}
        """
        target_leagues = leagues or self.leagues
        total_fetched = 0
        total_updated = 0

        for league in target_leagues:
            fetched, updated = self._poll_league(league)
            total_fetched += fetched
            total_updated += updated

        return {"games_fetched": total_fetched, "games_updated": total_updated}

    def refresh_scoreboards(
        self,
        leagues: list[str] | None = None,
        active_only: bool = True,
    ) -> dict[str, Any]:
        """
        Refresh ESPN scoreboard data for specified leagues.

        This is the primary method for fetching live game data from ESPN.
        Unlike poll_once() which is a generic polling method, refresh_scoreboards()
        specifically targets ESPN scoreboard data and provides more detailed results.

        Args:
            leagues: List of leagues to refresh. Defaults to configured leagues.
            active_only: If True, only fetch scoreboards for leagues with active games.
                        Saves API calls when no games are currently in progress.

        Returns:
            Dictionary with detailed results:
            {
                "leagues_polled": ["nfl", "ncaaf"],
                "games_by_league": {"nfl": 5, "ncaaf": 8},
                "total_games_fetched": 13,
                "total_games_updated": 10,
                "active_games": 3,
                "timestamp": "2025-12-07T20:00:00+00:00",
                "elapsed_seconds": 1.25
            }

        Usage:
            >>> updater = MarketUpdater(leagues=["nfl", "ncaaf"])
            >>> result = updater.refresh_scoreboards()
            >>> print(f"Updated {result['total_games_updated']} games")

        Educational Note:
            This method is designed for on-demand scoreboard refresh, which is
            useful for:
            - CLI commands that need current game data
            - Pre-trade verification of game states
            - Manual updates outside the scheduled polling interval
            - Testing and debugging scoreboard data flow
        """
        start_time = datetime.now(UTC)
        target_leagues = leagues or self.leagues

        # If active_only, filter to leagues with active games in database
        if active_only:
            active_leagues = []
            for league in target_leagues:
                if get_live_games(league=league):
                    active_leagues.append(league)
            # If no active games found, still poll all leagues to discover new games
            if active_leagues:
                target_leagues = active_leagues
                logger.debug("Active games found in: %s", active_leagues)
            else:
                logger.debug("No active games found, polling all configured leagues")

        games_by_league: dict[str, int] = {}
        total_fetched = 0
        total_updated = 0
        active_count = 0

        for league in target_leagues:
            try:
                fetched, updated = self._poll_league(league)
                games_by_league[league] = fetched
                total_fetched += fetched
                total_updated += updated

                # Count currently active games
                live = get_live_games(league=league)
                active_count += len(live) if live else 0

            except ESPNAPIError as e:
                logger.warning("ESPN API error for %s: %s", league, e)
                games_by_league[league] = 0
            except Exception as e:
                logger.error("Error refreshing %s scoreboard: %s", league, e)
                games_by_league[league] = 0

        elapsed = (datetime.now(UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "leagues_polled": target_leagues,
            "games_by_league": games_by_league,
            "total_games_fetched": total_fetched,
            "total_games_updated": total_updated,
            "active_games": active_count,
            "timestamp": start_time.isoformat(),
            "elapsed_seconds": round(elapsed, 3),
        }

        logger.info(
            "Scoreboard refresh complete: %d leagues, %d games fetched, %d updated in %.2fs",
            len(target_leagues),
            total_fetched,
            total_updated,
            elapsed,
        )

        return result

    def _poll_all_leagues(self) -> None:
        """
        Poll all configured leagues and update game states.

        This is the main scheduled job that runs at each interval.
        Handles errors gracefully to prevent scheduler job failures.
        """
        start_time = datetime.now(UTC)
        total_updated = 0

        try:
            for league in self.leagues:
                try:
                    _, updated = self._poll_league(league)
                    total_updated += updated
                except Exception as e:
                    # Log but don't re-raise - allow other leagues to continue
                    logger.error("Error polling %s: %s", league, e)
                    with self._lock:
                        self._stats["errors"] += 1
                        self._stats["last_error"] = str(e)

            with self._lock:
                self._stats["polls_completed"] += 1
                self._stats["games_updated"] += total_updated
                self._stats["last_poll"] = start_time.isoformat()

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            logger.debug(
                "Poll completed: %d games updated in %.2fs",
                total_updated,
                elapsed,
            )

        except Exception as e:
            logger.exception("Unexpected error in poll cycle: %s", e)
            with self._lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)

    def _poll_league(self, league: str) -> tuple[int, int]:
        """
        Poll a single league and update game states.

        Uses the normalized ESPNGameFull TypedDict structure for type safety
        and better alignment with the database schema.

        Args:
            league: League code (nfl, ncaaf, nba, etc.)

        Returns:
            Tuple of (games_fetched, games_updated)

        Raises:
            ESPNAPIError: If API request fails after retries.

        Educational Note:
            This method uses get_scoreboard() which returns ESPNGameFull
            (the normalized format) with:
            - Better type safety with nested TypedDicts
            - Clear separation of metadata vs dynamic state
            - Direct mapping to database schema
        """
        logger.debug("Polling %s scoreboard", league.upper())

        try:
            # Use scoreboard API - returns ESPNGameFull TypedDicts
            games = self.espn_client.get_scoreboard(league)
        except ESPNAPIError as e:
            logger.warning("ESPN API error for %s: %s", league, e)
            raise

        games_updated = 0
        for game in games:
            try:
                if self._sync_game_to_db(game, league):
                    games_updated += 1
            except Exception as e:
                event_id = game.get("metadata", {}).get("espn_event_id", "unknown")
                logger.error("Error syncing game %s: %s", event_id, e)

        logger.debug(
            "%s: fetched %d games, updated %d",
            league.upper(),
            len(games),
            games_updated,
        )

        return len(games), games_updated

    def _sync_game_to_db(self, game: ESPNGameFull, league: str) -> bool:
        """
        Sync a single game state to the database.

        Handles:
        - Team ID lookups (ESPN ID -> database ID)
        - Venue creation/lookup
        - Game state upsert with SCD Type 2

        Args:
            game: Game data in normalized ESPNGameFull format
            league: League code for team lookups

        Returns:
            True if game was updated, False if skipped

        Educational Note:
            ESPNGameFull has two main sections:
            - metadata: Static game info (teams, venue, broadcast)
            - state: Dynamic game state (scores, clock, situation)

            This maps cleanly to our database schema where metadata
            goes to various lookup tables and state goes to game_states
            with SCD Type 2 versioning.
        """
        metadata = game.get("metadata", {})
        state = game.get("state", {})

        espn_event_id = metadata.get("espn_event_id")
        if not espn_event_id:
            logger.warning("Game missing espn_event_id, skipping")
            return False

        # Extract team info from normalized structure
        home_team_info: ESPNTeamInfo = metadata.get("home_team", {})
        away_team_info: ESPNTeamInfo = metadata.get("away_team", {})

        # Look up team IDs
        home_team_id = self._get_db_team_id(
            home_team_info.get("espn_team_id"),
            league,
            home_team_info.get("team_code"),
        )
        away_team_id = self._get_db_team_id(
            away_team_info.get("espn_team_id"),
            league,
            away_team_info.get("team_code"),
        )

        # Handle venue from normalized structure
        venue_info: ESPNVenueInfo = metadata.get("venue", {})
        venue_id = self._ensure_venue_normalized(venue_info)

        # Parse game date
        game_date = None
        game_date_str = metadata.get("game_date")
        if game_date_str:
            try:
                game_date = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError) as e:
                logger.warning("Could not parse game_date: %s", e)

        # Get situation from state (already in correct format)
        situation_data = state.get("situation", {})
        situation = dict(situation_data) if situation_data else {}

        # Convert clock_seconds to Decimal for database
        clock_seconds = None
        clock_val = state.get("clock_seconds")
        if clock_val is not None:
            clock_seconds = Decimal(str(clock_val))

        # Upsert game state (SCD Type 2 handles versioning)
        upsert_game_state(
            espn_event_id=espn_event_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            venue_id=venue_id,
            home_score=state.get("home_score", 0),
            away_score=state.get("away_score", 0),
            period=state.get("period", 0),
            clock_seconds=clock_seconds,
            clock_display=state.get("clock_display"),
            game_status=self._normalize_game_status(state.get("game_status", "pre")),
            game_date=game_date,
            broadcast=metadata.get("broadcast"),
            neutral_site=metadata.get("neutral_site", False),
            season_type=str(metadata.get("season_type")) if metadata.get("season_type") else None,
            week_number=metadata.get("week_number"),
            league=league,
            situation=situation,
            linescores=state.get("linescores"),
        )

        return True

    def _get_db_team_id(
        self, espn_team_id: str | None, league: str, team_code: str | None
    ) -> int | None:
        """
        Look up database team_id from ESPN team_id.

        Args:
            espn_team_id: ESPN's team identifier
            league: League code for disambiguation
            team_code: Team abbreviation (fallback for logging)

        Returns:
            Database team_id, or None if not found
        """
        if not espn_team_id:
            return None

        team = get_team_by_espn_id(espn_team_id, league)
        if team:
            return int(team["team_id"])

        logger.warning(
            "Team not found: espn_id=%s, league=%s, code=%s",
            espn_team_id,
            league,
            team_code,
        )
        return None

    def _ensure_venue_normalized(self, venue_info: ESPNVenueInfo) -> int | None:
        """
        Ensure venue exists in database using normalized ESPNVenueInfo.

        Args:
            venue_info: Venue data in ESPNVenueInfo TypedDict format

        Returns:
            venue_id if venue exists/created, None otherwise

        Educational Note:
            ESPNVenueInfo is a normalized TypedDict with explicit fields:
            - espn_venue_id: ESPN's venue identifier
            - venue_name: Full venue name
            - city, state: Location
            - capacity, indoor: Venue characteristics

            This is cleaner than extracting from a flat game dict.
        """
        venue_name = venue_info.get("venue_name")
        if not venue_name:
            return None

        try:
            return create_venue(
                espn_venue_id=venue_info.get("espn_venue_id", venue_name),
                venue_name=venue_name,
                city=venue_info.get("city"),
                state=venue_info.get("state"),
                capacity=venue_info.get("capacity"),
                indoor=venue_info.get("indoor", False),
            )
        except Exception as e:
            logger.warning("Could not create/get venue %s: %s", venue_name, e)
            return None

    def _normalize_game_status(self, status: str) -> str:
        """
        Normalize ESPN game status to standard values.

        ESPN uses various status strings that we normalize to:
        - 'pre': Game not started
        - 'in_progress': Game in play
        - 'halftime': Halftime break
        - 'final': Game completed

        Args:
            status: Raw status from ESPN API

        Returns:
            Normalized status string
        """
        status_lower = status.lower() if status else "pre"

        if status_lower in ("pre", "scheduled"):
            return "pre"
        if status_lower in ("in", "in_progress"):
            return "in_progress"
        if status_lower == "halftime":
            return "halftime"
        if status_lower in ("post", "final", "final/ot", "final/2ot"):
            return "final"
        logger.debug("Unknown game status: %s, defaulting to 'pre'", status)
        return "pre"

    def has_active_games(self) -> bool:
        """
        Check if there are any currently active games in the database.

        Used for conditional polling - if no games are active, we can
        reduce polling frequency to save API calls.

        Returns:
            True if any games are in 'in_progress' or 'halftime' status
        """
        for league in self.leagues:
            live = get_live_games(league=league)
            if live:
                return True
        return False

    def setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.

        Registers handlers for SIGINT (Ctrl+C) and SIGTERM to ensure
        clean shutdown of the scheduler.

        Educational Note:
            Signal handlers are important for production services.
            Without them, a Ctrl+C might leave database connections
            open or jobs in an inconsistent state.
        """

        def shutdown_handler(signum: int, frame: Any) -> None:
            logger.info("Received signal %d, shutting down...", signum)
            self.stop(wait=True)
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
        logger.debug("Signal handlers registered")


# =============================================================================
# Convenience Functions
# =============================================================================


def create_market_updater(
    leagues: list[str] | None = None,
    poll_interval: int = 15,
    idle_interval: int = 60,
    persist_jobs: bool = False,
    job_store_url: str | None = None,
) -> MarketUpdater:
    """
    Factory function to create a configured MarketUpdater.

    Args:
        leagues: Leagues to poll (default: ["nfl", "ncaaf"])
        poll_interval: Seconds between polls when active (default: 15)
        idle_interval: Seconds between polls when idle (default: 60)
        persist_jobs: If True, persist scheduled jobs to database.
        job_store_url: SQLAlchemy URL for job store (required if persist_jobs=True).

    Returns:
        Configured MarketUpdater instance

    Example:
        >>> # Basic usage
        >>> updater = create_market_updater(leagues=["nfl", "nba"])
        >>> updater.start()
        >>>
        >>> # With job persistence (survives restarts)
        >>> updater = create_market_updater(
        ...     leagues=["nfl"],
        ...     persist_jobs=True,
        ...     job_store_url="sqlite:///jobs.db"
        ... )

    Educational Note:
        Job persistence is recommended for production deployments. Without it,
        if the process restarts, all scheduled jobs are lost and must be
        re-created. With persistence, jobs are stored in SQLite or PostgreSQL
        and automatically restored on restart.
    """
    return MarketUpdater(
        leagues=leagues,
        poll_interval=poll_interval,
        idle_interval=idle_interval,
        persist_jobs=persist_jobs,
        job_store_url=job_store_url,
    )


def run_single_poll(leagues: list[str] | None = None) -> dict[str, int]:
    """
    Execute a single poll without starting the scheduler.

    Useful for CLI commands or on-demand updates.

    Args:
        leagues: Leagues to poll (default: ["nfl", "ncaaf"])

    Returns:
        Dictionary with {"games_fetched": N, "games_updated": M}

    Example:
        >>> result = run_single_poll(["nfl"])
        >>> print(f"Updated {result['games_updated']} games")
    """
    updater = MarketUpdater(leagues=leagues)
    return updater.poll_once()


def refresh_all_scoreboards(
    leagues: list[str] | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    Refresh ESPN scoreboard data for specified leagues.

    Convenience function that creates a MarketUpdater and calls refresh_scoreboards().
    Useful for CLI commands and one-off data refreshes.

    Args:
        leagues: Leagues to refresh (default: ["nfl", "ncaaf"])
        active_only: If True, only refresh leagues with active games.

    Returns:
        Dictionary with detailed results:
        {
            "leagues_polled": ["nfl", "ncaaf"],
            "games_by_league": {"nfl": 5, "ncaaf": 8},
            "total_games_fetched": 13,
            "total_games_updated": 10,
            "active_games": 3,
            "timestamp": "2025-12-07T20:00:00+00:00",
            "elapsed_seconds": 1.25
        }

    Example:
        >>> result = refresh_all_scoreboards(["nfl"])
        >>> print(f"Active games: {result['active_games']}")
        >>> print(f"Updated in {result['elapsed_seconds']}s")
    """
    updater = MarketUpdater(leagues=leagues)
    return updater.refresh_scoreboards(active_only=active_only)
