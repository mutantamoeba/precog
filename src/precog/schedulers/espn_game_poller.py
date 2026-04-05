"""
ESPN game state polling service extending BasePoller.

This module provides the ESPNGamePoller class that polls ESPN APIs at configurable
intervals and syncs game states to the database using SCD Type 2 versioning.

Key Features:
- Extends BasePoller for consistent APScheduler-based polling
- Multi-league support (NFL, NCAAF, NBA, NCAAB, NHL, WNBA)
- Per-league adaptive polling to stay under ESPN's 250 req/hr rate limit
- Two polling states per league: DISCOVERY (900s) and TRACKING (30s)
- Dynamic throttling when 3+ leagues are tracking simultaneously
- Optional job persistence via SQLAlchemy
- SCD Type 2 versioning for game state history
- Error recovery with logging
- Clean shutdown handling

Naming Convention:
    {Platform}{Entity}Poller pattern:
    - ESPNGamePoller: Polls ESPN for game states
    - KalshiMarketPoller: Polls Kalshi for market prices (see kalshi_poller.py)

Educational Notes:
------------------
Per-League Adaptive Polling:
    Each league is polled independently with its own interval based on game activity:
    - DISCOVERY (900s): Default. Slow check for upcoming/live games. 4 leagues = 16 req/hr.
    - TRACKING (30s): Active when live games detected. 1 league = 120 req/hr.
    - Dynamic throttle: If 3+ leagues TRACKING, increase to 60s each to stay under 250 req/hr.

    State transitions (driven by ESPN scoreboard response):
    - DISCOVERY -> TRACKING: Any game has status "in" (in_progress) or "halftime"
    - TRACKING -> DISCOVERY: ALL games have status "final" or "pre" (none live)

    Rate budget math:
    - 1 league TRACKING: 120 + 12 (3 idle) = 132 req/hr
    - 2 leagues TRACKING: 240 + 8 (2 idle) = 248 req/hr (under 250)
    - 3+ leagues TRACKING: Throttle to 60s = 180 + 4 = 184 req/hr (safe margin)

SCD Type 2 for Game States:
    - Every score change creates a new row (full game history)
    - Enables ML training on score progression
    - Provides audit trail for trading decisions
    - Supports backtesting with historical game states

Reference: docs/guides/ESPN_DATA_MODEL_V1.0.md
Related Requirements:
    - REQ-DATA-001: Game State Data Collection
    - Phase 2: Live Data Integration
Related ADR: ADR-100 (Service Supervisor Pattern)
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from precog.api_connectors.espn_client import (
    ESPNAPIError,
    ESPNClient,
    ESPNGameFull,
    ESPNTeamInfo,
    ESPNVenueInfo,
    extract_espn_odds,
)
from precog.database.crud_game_states import (
    LEAGUE_SPORT_CATEGORY,
    get_live_games,
    get_or_create_game,
    update_game_result,
    upsert_game_odds,
    upsert_game_state,
)
from precog.database.crud_teams import (
    create_venue,
    get_team_by_espn_id,
)
from precog.schedulers.base_poller import BasePoller

# Set up logging
logger = logging.getLogger(__name__)

# =============================================================================
# Per-League Polling State Constants
# =============================================================================

# Polling states for per-league adaptive polling
LEAGUE_STATE_DISCOVERY = "discovery"
LEAGUE_STATE_TRACKING = "tracking"


class GameSyncReason(str, Enum):
    """Categorized outcomes for ESPN game-to-DB sync operations (#476).

    Mirrors the MatchReason pattern in event_game_matcher.py. Used for
    failure categorization metrics in system_health reporting.

    Categories:
        SYNCED: Game state written to DB (new SCD row created)
        UNCHANGED: Game state identical to current — no new row needed
        MISSING_EVENT_ID: espn_event_id not in game metadata
        GAME_DIMENSION_FAILED: games table upsert threw an exception
        STATE_UPSERT_FAILED: game_states SCD upsert threw an exception
        API_ERROR: ESPN API returned an error for this league poll
    """

    SYNCED = "synced"
    UNCHANGED = "unchanged"
    MISSING_EVENT_ID = "missing_event_id"
    GAME_DIMENSION_FAILED = "game_dimension_failed"
    STATE_UPSERT_FAILED = "state_upsert_failed"
    API_ERROR = "api_error"


class ESPNGamePoller(BasePoller):
    """
    ESPN game state polling service.

    Polls ESPN APIs at regular intervals and syncs game states to the database.
    Extends BasePoller for consistent APScheduler-based polling with health monitoring.

    Attributes:
        leagues: List of leagues to poll (default: ["nfl", "ncaaf"])
        poll_interval: Seconds between polls when games active (default: 30)
        idle_interval: Seconds between checks when no games active (default: 300)
        persist_jobs: Whether to persist scheduled jobs to database
        enabled: Whether polling is currently enabled

    Usage:
        >>> # Basic usage
        >>> poller = ESPNGamePoller()
        >>> poller.start()
        >>> # ... polling runs in background ...
        >>> poller.stop()
        >>>
        >>> # Custom configuration
        >>> poller = ESPNGamePoller(
        ...     leagues=["nfl", "nba"],
        ...     poll_interval=30,
        ...     idle_interval=120
        ... )
        >>> poller.start()
        >>>
        >>> # With job persistence (survives restarts)
        >>> poller = ESPNGamePoller(
        ...     leagues=["nfl"],
        ...     persist_jobs=True,
        ...     job_store_url="sqlite:///jobs.db"
        ... )

    Educational Note:
        The poller uses BasePoller's BackgroundScheduler which runs jobs in a
        thread pool. This allows the main application to continue running while
        polls happen in the background. The scheduler handles job execution,
        retries, and timing automatically.

        Job persistence (via persist_jobs=True) enables the scheduler to survive
        restarts - scheduled jobs are stored in SQLite/PostgreSQL and restored
        automatically.

    Reference: Phase 2.5 Live Data Collection Service
    Related: ADR-100 (Service Supervisor Pattern)
    """

    # Service registry metadata (read by ServiceSupervisor at registration)
    SERVICE_KEY: ClassVar[str] = "espn"
    HEALTH_COMPONENT: ClassVar[str] = "espn_api"
    BREAKER_TYPE: ClassVar[str] = "data_stale"

    # Class-level configuration
    MIN_POLL_INTERVAL: ClassVar[int] = 15  # seconds (floor to protect ESPN budget)
    DEFAULT_POLL_INTERVAL: ClassVar[int] = 30  # seconds (live games; ~2,160 req/day active)
    DEFAULT_IDLE_INTERVAL: ClassVar[int] = 300  # seconds (no games; ~648 req/day idle)
    DEFAULT_LEAGUES: ClassVar[list[str]] = ["nfl", "ncaaf", "nba", "nhl"]

    # Per-league adaptive polling constants
    DEFAULT_TRACKING_INTERVAL: ClassVar[int] = 30  # seconds (per-league, live games)
    DEFAULT_DISCOVERY_INTERVAL: ClassVar[int] = 900  # seconds (per-league, no live games)
    DEFAULT_MAX_THROTTLED_INTERVAL: ClassVar[int] = 60  # never throttle slower than this
    LEAGUE_STAGGER_OFFSET: ClassVar[int] = 15  # seconds between league job starts
    HEARTBEAT_TRACKING_EVERY_N: ClassVar[int] = 20  # heartbeat every N quiet tracking polls

    # ESPN rate limit budget (configurable via constructor or YAML)
    DEFAULT_RATE_BUDGET: ClassVar[int] = 250  # requests per hour

    # Game status mappings
    LIVE_STATUSES: ClassVar[set[str]] = {"in", "in_progress", "halftime"}
    COMPLETED_STATUSES: ClassVar[set[str]] = {"post", "final", "final/ot"}
    SCHEDULED_STATUSES: ClassVar[set[str]] = {"pre", "scheduled"}

    def __init__(
        self,
        leagues: list[str] | None = None,
        poll_interval: int | None = None,
        idle_interval: int | None = None,
        espn_client: ESPNClient | None = None,
        persist_jobs: bool = False,
        job_store_url: str | None = None,
        adaptive_polling: bool = True,
        validate_teams_on_start: bool = True,
        rate_budget_per_hour: int | None = None,
        max_throttled_interval: int | None = None,
        priority_calculator: Any | None = None,
    ) -> None:
        """
        Initialize the ESPNGamePoller.

        Args:
            leagues: List of leagues to poll. Defaults to NFL, NCAAF, NBA, and NHL.
            poll_interval: Seconds between polls when games are active.
            idle_interval: Seconds between checks when no games active.
            espn_client: Optional ESPNClient instance (for testing/mocking).
            persist_jobs: If True, persist scheduled jobs to database.
            job_store_url: SQLAlchemy URL for job store (required if persist_jobs=True).
            adaptive_polling: If True, dynamically adjust poll interval based on
                game activity (poll_interval when active, idle_interval when idle).
                Default True. (Issue #234)
            validate_teams_on_start: If True, validate ESPN team IDs against the
                database at startup. Mismatches are logged as warnings but do not
                prevent the poller from starting. Default True.

        Raises:
            ValueError: If poll_interval < 15 or idle_interval < 15.
            ValueError: If persist_jobs=True but job_store_url not provided.

        Educational Note:
            Per-league polling (vs single-interval polling):
            - Old approach: Single job polls ALL leagues at one interval.
              4 leagues * 30s = 480 req/hr (exceeds 250 limit!)
            - New approach: Each league has its own job and interval.
              DISCOVERY leagues poll at 900s, TRACKING leagues at 30s.
              Budget math ensures we stay under 250 req/hr.

            Adaptive polling (Issue #234) is a subset of per-league polling:
            each league transitions independently between DISCOVERY and TRACKING.
        """
        effective_idle = idle_interval or self.DEFAULT_IDLE_INTERVAL
        if effective_idle < 15:
            raise ValueError("idle_interval must be at least 15 seconds")
        if persist_jobs and not job_store_url:
            raise ValueError("job_store_url required when persist_jobs=True")

        # Initialize base class (handles scheduler, stats, etc.)
        super().__init__(poll_interval=poll_interval, logger=logger)

        # ESPN-specific configuration
        self.leagues = leagues or self.DEFAULT_LEAGUES.copy()
        self.idle_interval = effective_idle
        self.persist_jobs = persist_jobs
        self.job_store_url = job_store_url
        self.adaptive_polling = adaptive_polling
        self.validate_teams_on_start = validate_teams_on_start

        # Rate budget and throttle computation (C18 JC-4 / #560)
        self.rate_budget_per_hour = (
            rate_budget_per_hour if rate_budget_per_hour is not None else self.DEFAULT_RATE_BUDGET
        )
        self.max_throttled_interval = (
            max_throttled_interval
            if max_throttled_interval is not None
            else self.DEFAULT_MAX_THROTTLED_INTERVAL
        )
        if self.rate_budget_per_hour < 1:
            raise ValueError(f"rate_budget_per_hour must be >= 1, got {self.rate_budget_per_hour}")
        if self.max_throttled_interval < 15:
            raise ValueError(
                f"max_throttled_interval must be >= 15, got {self.max_throttled_interval}"
            )
        tracking_interval = self.poll_interval or self.DEFAULT_TRACKING_INTERVAL
        discovery_overhead = len(self.leagues) * (3600 // self.DEFAULT_DISCOVERY_INTERVAL)
        available_for_tracking = max(0, self.rate_budget_per_hour - discovery_overhead)
        req_per_league_tracking = 3600 // tracking_interval if tracking_interval <= 3600 else 1
        self._max_concurrent_full_speed = max(
            1,
            available_for_tracking // req_per_league_tracking if req_per_league_tracking > 0 else 1,
        )

        # Per-league polling state (protected by self._lock from BasePoller)
        # Maps league code -> LEAGUE_STATE_DISCOVERY or LEAGUE_STATE_TRACKING
        self._league_states: dict[str, str] = dict.fromkeys(self.leagues, LEAGUE_STATE_DISCOVERY)
        # Maps league code -> consecutive silent poll count (for heartbeat logging)
        self._league_silent_counts: dict[str, int] = dict.fromkeys(self.leagues, 0)
        # Maps league code -> current interval in seconds for that league
        self._league_intervals: dict[str, int] = dict.fromkeys(
            self.leagues, self.DEFAULT_DISCOVERY_INTERVAL
        )

        # Priority-based adaptive polling (#560)
        # Stores last scoreboard games per league for priority calculation
        self._league_last_games: dict[str, list[ESPNGameFull]] = {}
        # Optional priority calculator for non-uniform throttling
        self._priority_calculator = priority_calculator

        # Track last validation time for dedup guard (Part F)
        self._last_validation_time: float = 0.0

        # Sync stats: categorized outcomes for P41 failure monitoring (#476).
        # Mirrors Kalshi's _matching_stats pattern. Cumulative, reset on restart.
        self._sync_stats: dict[str, int] = {f"sync_{reason.value}": 0 for reason in GameSyncReason}

        # Initialize ESPN client (or use provided mock)
        self.espn_client = espn_client or ESPNClient()

        logger.info(
            "ESPNGamePoller initialized: leagues=%s, poll_interval=%ds, "
            "idle_interval=%ds, persist_jobs=%s, adaptive_polling=%s",
            self.leagues,
            self.poll_interval,
            self.idle_interval,
            self.persist_jobs,
            self.adaptive_polling,
        )

    def _get_job_name(self) -> str:
        """Return human-readable name for the polling job."""
        return "ESPN Game State Poll"

    def get_stats(self) -> dict[str, Any]:
        """Return polling stats merged with sync categorization (#476)."""
        with self._lock:
            stats = dict(self._stats)
            stats.update(self._sync_stats)
            return stats

    def _record_sync(self, reason: GameSyncReason) -> None:
        """Increment a categorized sync outcome counter."""
        with self._lock:
            self._sync_stats[f"sync_{reason.value}"] += 1

    def _poll_once(self) -> dict[str, int]:
        """
        Execute a single poll cycle for all configured leagues.

        Returns:
            Dictionary with counts: items_fetched, items_updated, items_created
        """
        total_fetched = 0
        total_updated = 0
        total_created = 0  # ESPN uses upsert, so created = 0 for now

        for league in self.leagues:
            try:
                fetched, updated = self._poll_league(league)
                total_fetched += fetched
                total_updated += updated
            except Exception as e:
                # Log but don't re-raise - allow other leagues to continue
                logger.error("Error polling %s: %s", league, e)
                with self._lock:
                    self._stats["errors"] += 1
                    self._stats["last_error"] = str(e)

        return {
            "items_fetched": total_fetched,
            "items_updated": total_updated,
            "items_created": total_created,
        }

    def start(self) -> None:
        """
        Start the polling scheduler with optional job persistence.

        Overrides BasePoller.start() to add job persistence support
        via SQLAlchemy job store. Creates separate APScheduler jobs for
        each league with staggered offsets to avoid request bursts.

        Raises:
            RuntimeError: If already started.

        Educational Note:
            Per-league polling creates one APScheduler job per league, each with
            its own interval. Jobs are staggered by LEAGUE_STAGGER_OFFSET seconds
            (default 15s) to distribute API calls evenly across time. This prevents
            bursts where all leagues fire simultaneously.

            Example with 4 leagues (NFL, NCAAF, NBA, NHL):
            - NFL starts at t+0s, NCAAF at t+15s, NBA at t+30s, NHL at t+45s
            - Each starts in DISCOVERY state (900s interval)
            - When a league detects live games, it transitions to TRACKING (30s)
        """
        with self._lock:
            if self._enabled:
                raise RuntimeError(f"{self.__class__.__name__} is already running")

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
                    "misfire_grace_time": 60,  # Grace period for late jobs
                },
            )

            # Per-league mode: create one job per league with staggered starts
            now = datetime.now(UTC)
            for idx, league in enumerate(self.leagues):
                initial_interval = self.DEFAULT_DISCOVERY_INTERVAL
                job_id = self._league_job_id(league)
                stagger_seconds = idx * self.LEAGUE_STAGGER_OFFSET
                start_time = now + timedelta(seconds=initial_interval + stagger_seconds)

                self._scheduler.add_job(
                    self._poll_league_wrapper,
                    IntervalTrigger(seconds=initial_interval, start_date=start_time),
                    id=job_id,
                    name=f"ESPN {league.upper()} Poll",
                    replace_existing=True,
                    args=[league],
                )

                logger.info(
                    "Added per-league job: %s (interval=%ds, stagger=%ds)",
                    league.upper(),
                    initial_interval,
                    stagger_seconds,
                )

            # Periodic team validation job (6hr interval).
            # Re-validates ESPN team IDs during long soak tests to catch
            # any data drift without requiring a restart.
            if self.validate_teams_on_start:
                validation_interval = 21600  # 6 hours in seconds
                self._scheduler.add_job(
                    self._periodic_team_validation,
                    IntervalTrigger(seconds=validation_interval),
                    id="espn_team_validation",
                    name="ESPN Team ID Periodic Validation",
                    replace_existing=True,
                )
                logger.info(
                    "Added periodic team validation job (interval=%ds / %dh)",
                    validation_interval,
                    validation_interval // 3600,
                )

            self._scheduler.start()
            self._enabled = True

        # Register in class-level registry for cleanup (Issue #292).
        # ESPNGamePoller overrides start() without calling super().start(),
        # so we must register explicitly here.
        with BasePoller._registry_lock:
            BasePoller._active_pollers.add(self)

        logger.info(
            "%s started - per-league polling for %d leagues",
            self.__class__.__name__,
            len(self.leagues),
        )

        # Hook for subclass initialization
        self._on_start()

        # Run initial poll AFTER releasing the lock and starting the scheduler.
        # _poll_league_wrapper needs self._lock, so this MUST be outside the
        # with self._lock block above (threading.Lock is non-reentrant).
        for league in self.leagues:
            self._poll_league_wrapper(league)

    def _on_start(self) -> None:
        """Run startup validation of ESPN team IDs if configured.

        Educational Note:
            Team ID validation is wrapped in try/except to ensure that
            network errors or database issues during validation never
            prevent the poller from starting. Validation is informational
            -- mismatches are logged as warnings for investigation.

        Related:
            - precog.api_connectors.espn_team_validator.validate_espn_teams
        """
        if not self.validate_teams_on_start:
            return

        try:
            from precog.api_connectors.espn_team_validator import validate_espn_teams

            logger.info("Running ESPN team ID validation at startup...")
            results = validate_espn_teams(
                leagues=self.leagues,
                auto_correct=True,
            )
            self._last_validation_time = time.monotonic()
            if results["total_mismatches"] > 0:
                logger.warning(
                    "ESPN team ID validation found %d mismatches "
                    "across %d leagues (auto-correct enabled). Review warnings above.",
                    results["total_mismatches"],
                    len(results["leagues"]),
                )
            else:
                logger.info(
                    "ESPN team ID validation passed: %d teams checked, no mismatches",
                    results["total_checked"],
                )
        except Exception as e:
            # Never let validation failure prevent the poller from starting
            logger.warning("ESPN team ID validation failed (non-fatal): %s", e)

    def _periodic_team_validation(self) -> None:
        """Run periodic ESPN team ID validation (called by APScheduler).

        Skips execution if the last validation (startup or periodic) happened
        less than 10 minutes ago, to avoid redundant work when the poller
        was recently started or restarted.

        Educational Note:
            This method is registered as an APScheduler interval job with a
            6-hour interval. It uses auto_correct=True so any ESPN ID drift
            detected during long soak tests is fixed automatically without
            requiring a restart. The 10-minute dedup guard prevents the first
            periodic run from duplicating the startup validation.

        Related:
            - _on_start() (startup validation)
            - validate_espn_teams() in espn_team_validator.py
        """
        # Dedup guard: skip if validated recently (within 10 minutes)
        elapsed = time.monotonic() - self._last_validation_time
        if elapsed < 600:  # 600 seconds = 10 minutes
            logger.debug(
                "Skipping periodic team validation: last run %.0fs ago (< 600s)",
                elapsed,
            )
            return

        try:
            from precog.api_connectors.espn_team_validator import validate_espn_teams

            logger.info("Running periodic ESPN team ID validation...")
            results = validate_espn_teams(
                leagues=self.leagues,
                auto_correct=True,
            )
            self._last_validation_time = time.monotonic()

            if results["total_mismatches"] > 0:
                logger.warning(
                    "Periodic validation found %d ESPN ID mismatches "
                    "across %d leagues (auto-corrected). Review warnings above.",
                    results["total_mismatches"],
                    len(results["leagues"]),
                )
            else:
                logger.info(
                    "Periodic validation passed: %d teams checked, no mismatches",
                    results["total_checked"],
                )
        except Exception as e:
            # Never let validation failure crash the scheduler
            logger.warning("Periodic ESPN team validation failed (non-fatal): %s", e)

    def _on_stop(self) -> None:
        """Clean up ESPN client on stop."""
        # ESPNClient uses requests Session, but doesn't need explicit cleanup
        # This hook is here for consistency with other pollers

    # =========================================================================
    # Per-League Polling Methods
    # =========================================================================

    def _league_job_id(self, league: str) -> str:
        """
        Generate unique APScheduler job ID for a league.

        Args:
            league: League code (nfl, ncaaf, etc.)

        Returns:
            Unique job ID string.
        """
        return f"poll_espn_{league}"

    def _poll_league_wrapper(self, league: str) -> None:
        """
        Execute a single poll for one league and evaluate state transition.

        Polls one league,
        updates stats, then evaluates whether the league should transition between
        DISCOVERY and TRACKING states.

        Args:
            league: League code to poll.

        Educational Note:
            Each league job calls this method independently. After polling,
            we check the scoreboard response for live games. If any game
            has a live status, the league transitions to TRACKING (fast polling).
            If all games are pre/final, it transitions back to DISCOVERY (slow).

            The state evaluation uses the scoreboard API response directly
            (not the database), making it the source of truth for transitions.
        """
        start_time = datetime.now(UTC)

        try:
            # Poll the league and get games for state evaluation
            games = self.espn_client.get_scoreboard(league)
            games_updated = 0
            sync_errors = 0
            for game in games:
                try:
                    if self._sync_game_to_db(game, league):
                        games_updated += 1
                        self._record_sync(GameSyncReason.SYNCED)
                    else:
                        self._record_sync(GameSyncReason.UNCHANGED)
                except Exception as e:
                    sync_errors += 1
                    self._record_sync(GameSyncReason.STATE_UPSERT_FAILED)
                    event_id = game.get("metadata", {}).get("espn_event_id", "unknown")
                    logger.error("Error syncing game %s: %s", event_id, e)

            with self._lock:
                self._stats["polls_completed"] += 1
                self._stats["items_fetched"] += len(games)
                self._stats["items_updated"] += games_updated
                self._stats["errors"] += sync_errors
                self._stats["last_poll"] = start_time.isoformat()

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if games_updated:
                # Changes detected - log at INFO and reset silent counter
                logger.info(
                    "ESPN %s poll completed: fetched=%d, updated=%d in %.2fs",
                    league.upper(),
                    len(games),
                    games_updated,
                    elapsed,
                )
                with self._lock:
                    self._league_silent_counts[league] = 0
            else:
                # No changes - behavior depends on polling state
                with self._lock:
                    league_state = self._league_states.get(league, LEAGUE_STATE_DISCOVERY)
                if league_state == LEAGUE_STATE_DISCOVERY:
                    # Discovery polls are rare (~4/league/hour) - always INFO
                    logger.info(
                        "ESPN %s discovery: %d games on scoreboard, none changed in %.2fs",
                        league.upper(),
                        len(games),
                        elapsed,
                    )
                else:
                    # Tracking mode - counter-based heartbeat
                    # Atomic check-and-reset under single lock to avoid TOCTOU race
                    with self._lock:
                        self._league_silent_counts[league] = (
                            self._league_silent_counts.get(league, 0) + 1
                        )
                        silent_count = self._league_silent_counts[league]
                        should_heartbeat = silent_count >= self.HEARTBEAT_TRACKING_EVERY_N
                        if should_heartbeat:
                            self._league_silent_counts[league] = 0
                    if should_heartbeat:
                        logger.info(
                            "ESPN %s heartbeat: %d quiet polls (tracking, %d games on scoreboard)",
                            league.upper(),
                            silent_count,
                            len(games),
                        )
                    else:
                        logger.debug(
                            "ESPN %s poll completed: fetched=%d, updated=%d in %.2fs",
                            league.upper(),
                            len(games),
                            games_updated,
                            elapsed,
                        )

            # Evaluate league state from scoreboard response
            self._evaluate_league_state(league, games)

        except ESPNAPIError as e:
            logger.warning("ESPN API error for %s: %s", league, e)
            self._record_sync(GameSyncReason.API_ERROR)
            with self._lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)
        except Exception as e:
            logger.exception("Error in %s poll cycle: %s", league.upper(), e)
            self._record_sync(GameSyncReason.API_ERROR)
            with self._lock:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)

    def _evaluate_league_state(self, league: str, games: list[ESPNGameFull]) -> None:
        """
        Evaluate and transition a league's polling state based on scoreboard data.

        Uses the raw ESPN scoreboard response (not DB) as the source of truth.
        Transitions:
        - DISCOVERY -> TRACKING: Any game has a live status
        - TRACKING -> DISCOVERY: All games are pre/final (none live)

        After transitioning, recalculates all league intervals to handle
        throttling when 3+ leagues are simultaneously tracking.

        Args:
            league: League code that was just polled.
            games: List of ESPNGameFull dicts from the scoreboard response.

        Educational Note:
            We check the raw game_status from the ESPN response (before
            normalization) against LIVE_STATUSES. This is intentional:
            the scoreboard response is the most current source of truth,
            and we want to transition to TRACKING as soon as ESPN reports
            a live game, not after we've written to the DB.
        """
        has_live = self._scoreboard_has_live_games(games)

        pending_reschedules: list[tuple[str, int, int, str, int]] = []

        with self._lock:
            # Store latest games for priority-based throttle calculation (#560)
            self._league_last_games[league] = games

            if league not in self._league_states:
                logger.warning("Unknown league '%s' in state evaluation, ignoring", league)
                return

            old_state = self._league_states[league]

            new_state = LEAGUE_STATE_TRACKING if has_live else LEAGUE_STATE_DISCOVERY

            if old_state == new_state:
                # No state transition, but if priority calculator is active,
                # recalculate intervals every poll cycle so game-phase urgency
                # updates as games progress (Q1 → Q4, etc). Without this,
                # intervals computed at TRACKING entry never change. (#560)
                if self._priority_calculator is not None and old_state == LEAGUE_STATE_TRACKING:
                    pending_reschedules = self._recalculate_league_intervals()
                else:
                    return  # No transition, no priority calculator — nothing to do
            else:
                # State transition — always recalculate
                self._league_states[league] = new_state

                # Clean up stale game cache on TRACKING → DISCOVERY
                if new_state == LEAGUE_STATE_DISCOVERY and league in self._league_last_games:
                    del self._league_last_games[league]

                logger.info(
                    "League %s state transition: %s -> %s",
                    league.upper(),
                    old_state,
                    new_state,
                )

                # Recalculate intervals and collect reschedule ops (execute outside lock)
                pending_reschedules = self._recalculate_league_intervals()

        # Execute reschedules OUTSIDE the lock to avoid deadlock with APScheduler
        for job_id, old_interval, new_interval, state, tracking_count in pending_reschedules:
            try:
                if self._scheduler is None:
                    continue
                self._scheduler.reschedule_job(
                    job_id,
                    trigger=IntervalTrigger(seconds=new_interval),
                )
                logger.info(
                    "Rescheduled %s: %ds -> %ds (state=%s, tracking_leagues=%d)",
                    job_id,
                    old_interval,
                    new_interval,
                    state,
                    tracking_count,
                )
            except Exception as e:
                logger.warning("Failed to reschedule %s job: %s", job_id, e)

    def _scoreboard_has_live_games(self, games: list[ESPNGameFull]) -> bool:
        """
        Check if any game in a scoreboard response has a live status.

        Args:
            games: List of ESPNGameFull dicts from get_scoreboard().

        Returns:
            True if any game has a status in LIVE_STATUSES.
        """
        for game in games:
            state = game.get("state", {})
            game_status = state.get("game_status", "pre")
            if isinstance(game_status, str) and game_status.lower() in self.LIVE_STATUSES:
                return True
        return False

    def _recalculate_league_intervals(self) -> list[tuple[str, int, int, str, int]]:
        """
        Recalculate intervals for all leagues based on current states.

        Must be called with self._lock held. Returns pending reschedule
        operations to be executed OUTSIDE the lock (avoids deadlock with
        APScheduler's internal lock).

        When more leagues are tracking than can run at full speed, excess
        leagues are throttled. Throttle interval is computed from the rate
        budget, not hardcoded. Capped at max_throttled_interval (default 60s).

        Returns:
            List of (job_id, old_interval, new_interval, state, tracking_count)
            tuples for jobs that need rescheduling.

        Educational Note:
            Rate budget math (computed, not hardcoded — #560):
            - rate_budget_per_hour: configurable (default 250, can increase to 500+)
            - discovery_overhead: len(leagues) * (3600/900) = ~16 req/hr for 4 leagues
            - available_for_tracking: budget - discovery_overhead
            - max_concurrent_full_speed: available / (3600 / tracking_interval)

            Example at 500 req/hr, 15s tracking:
            - discovery overhead: 4 * 4 = 16 req/hr
            - available: 484 req/hr
            - full speed: 3600/15 = 240 req/hr per league
            - max at full speed: 484/240 = 2 leagues
            - overflow leagues: throttled to share remaining budget
            - throttled interval: capped at max_throttled_interval (60s)
        """
        tracking_count = sum(1 for s in self._league_states.values() if s == LEAGUE_STATE_TRACKING)
        base_interval = self.poll_interval or self.DEFAULT_TRACKING_INTERVAL

        # Determine whether throttling is needed
        needs_throttle = tracking_count > self._max_concurrent_full_speed and tracking_count > 0

        # Budget available for tracking = total - discovery overhead
        discovery_count = len(self.leagues) - tracking_count
        discovery_budget = discovery_count * (3600 // self.DEFAULT_DISCOVERY_INTERVAL)
        available_for_tracking = max(0, self.rate_budget_per_hour - discovery_budget)

        # Per-league interval map for tracking leagues (uniform or priority-based)
        priority_intervals: dict[str, int] | None = None

        if needs_throttle and self._priority_calculator is not None:
            # Priority-based allocation (#560): higher-priority leagues poll faster
            try:
                tracking_leagues = [
                    lg
                    for lg in self.leagues
                    if self._league_states.get(lg) == LEAGUE_STATE_TRACKING
                ]
                priority_intervals = self._priority_calculator.allocate_budget(
                    tracking_leagues=tracking_leagues,
                    budget_available=available_for_tracking,
                    base_interval=base_interval,
                    max_throttled_interval=self.max_throttled_interval,
                    league_games=self._league_last_games,
                )
                if priority_intervals is not None:
                    logger.info(
                        "Priority-based throttle: %s (tracking=%d, budget=%d req/hr)",
                        {lg: f"{iv}s" for lg, iv in priority_intervals.items()},
                        tracking_count,
                        available_for_tracking,
                    )
            except Exception:
                logger.warning(
                    "Priority allocation failed, falling back to uniform throttle",
                    exc_info=True,
                )
                priority_intervals = None

        # Compute uniform tracking interval (used when no priority calculator
        # or as fallback when priority allocation fails)
        if needs_throttle:
            per_league_budget = (
                available_for_tracking // tracking_count if tracking_count > 0 else 0
            )

            if per_league_budget > 0:
                computed_interval = max(base_interval, 3600 // per_league_budget)
            else:
                computed_interval = self.max_throttled_interval

            # Cap: never slower than max_throttled_interval, never faster than base
            uniform_tracking_interval = min(computed_interval, self.max_throttled_interval)
            uniform_tracking_interval = max(uniform_tracking_interval, base_interval)
        else:
            uniform_tracking_interval = base_interval  # no throttling needed

        pending: list[tuple[str, int, int, str, int]] = []

        for league in self.leagues:
            state = self._league_states.get(league, LEAGUE_STATE_DISCOVERY)
            if state == LEAGUE_STATE_TRACKING:
                # Use priority-based interval if available, else uniform
                if priority_intervals is not None and league in priority_intervals:
                    new_interval = priority_intervals[league]
                else:
                    new_interval = uniform_tracking_interval
            else:
                new_interval = self.DEFAULT_DISCOVERY_INTERVAL

            old_interval = self._league_intervals.get(league, self.DEFAULT_DISCOVERY_INTERVAL)
            self._league_intervals[league] = new_interval

            # Collect reschedule ops (executed outside lock by caller)
            if old_interval != new_interval and self._scheduler and self._enabled:
                job_id = self._league_job_id(league)
                pending.append((job_id, old_interval, new_interval, state, tracking_count))

        # Validate rate budget
        total_req_hr = sum(3600 / iv for iv in self._league_intervals.values())
        if total_req_hr > self.rate_budget_per_hour:
            logger.warning(
                "Rate budget exceeded: %d req/hr > %d limit (tracking=%d leagues)",
                total_req_hr,
                self.rate_budget_per_hour,
                tracking_count,
            )

        return pending

    def get_league_states(self) -> dict[str, str]:
        """
        Get the current polling state for each league.

        Returns:
            Dictionary mapping league code to state string
            (LEAGUE_STATE_DISCOVERY or LEAGUE_STATE_TRACKING).

        Thread-safe: acquires self._lock.
        """
        with self._lock:
            return dict(self._league_states)

    def get_league_intervals(self) -> dict[str, int]:
        """
        Get the current polling interval for each league.

        Returns:
            Dictionary mapping league code to interval in seconds.

        Thread-safe: acquires self._lock.
        """
        with self._lock:
            return dict(self._league_intervals)

    def get_current_interval(self) -> int:
        """
        Get the current polling interval.

        Returns the minimum interval across all leagues (i.e., the fastest
        polling rate currently in effect).

        Returns:
            Current interval in seconds.

        Useful for monitoring and debugging adaptive polling behavior.
        """
        with self._lock:
            if self._league_intervals:
                return min(self._league_intervals.values())
        return self.DEFAULT_DISCOVERY_INTERVAL

    def poll_once(self, leagues: list[str] | None = None) -> dict[str, int]:
        """
        Execute a single poll cycle manually.

        Useful for testing or on-demand updates outside the scheduled interval.

        Args:
            leagues: Optional list of leagues to poll. Defaults to configured leagues.

        Returns:
            Dictionary with counts: {"items_fetched": N, "items_updated": M, "items_created": P}
        """
        target_leagues = leagues or self.leagues
        total_fetched = 0
        total_updated = 0

        for league in target_leagues:
            fetched, updated = self._poll_league(league)
            total_fetched += fetched
            total_updated += updated

        return {
            "items_fetched": total_fetched,
            "items_updated": total_updated,
            "items_created": 0,  # ESPN uses upsert
        }

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
            >>> poller = ESPNGamePoller(leagues=["nfl", "ncaaf"])
            >>> result = poller.refresh_scoreboards()
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

        # Demote no-change refreshes to DEBUG to reduce steady-state noise
        log_fn = logger.info if total_updated else logger.debug
        log_fn(
            "Scoreboard refresh complete: %d leagues, %d games fetched, %d updated in %.2fs",
            len(target_leagues),
            total_fetched,
            total_updated,
            elapsed,
        )

        return result

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

        logger.info(
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
            self._record_sync(GameSyncReason.MISSING_EVENT_ID)
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

        # Derive season from game_date (calendar year)
        game_season = game_date.year if game_date else None
        game_season_type = str(metadata.get("season_type")) if metadata.get("season_type") else None
        game_week_number = metadata.get("week_number")
        normalized_status = self._normalize_game_status(state.get("game_status", "pre"))

        # Create or update the games dimension row (idempotent)
        game_id = None
        if game_date and home_team_info.get("team_code") and away_team_info.get("team_code"):
            try:
                game_id = get_or_create_game(
                    sport=LEAGUE_SPORT_CATEGORY.get(league, league),
                    game_date=game_date.date() if hasattr(game_date, "date") else game_date,
                    home_team_code=home_team_info.get("team_code", ""),
                    away_team_code=away_team_info.get("team_code", ""),
                    season=game_season,
                    league=league,
                    season_type=game_season_type,
                    week_number=game_week_number,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    venue_id=venue_id,
                    venue_name=venue_info.get("venue_name"),
                    neutral_site=metadata.get("neutral_site", False),
                    espn_event_id=espn_event_id,
                    game_status=normalized_status,
                    game_time=game_date,
                    data_source="espn_poller",
                    attendance=metadata.get("attendance"),
                )
            except Exception:
                self._record_sync(GameSyncReason.GAME_DIMENSION_FAILED)
                logger.warning(
                    "Failed to upsert games dimension row for %s",
                    espn_event_id,
                    exc_info=True,
                )

        # Upsert game state (SCD Type 2 handles versioning)
        # Returns new row ID if state changed, or existing ID/None if unchanged
        result_id = upsert_game_state(
            espn_event_id=espn_event_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            venue_id=venue_id,
            home_score=state.get("home_score", 0),
            away_score=state.get("away_score", 0),
            period=state.get("period", 0),
            clock_seconds=clock_seconds,
            clock_display=state.get("clock_display"),
            game_status=normalized_status,
            game_date=game_date,
            broadcast=metadata.get("broadcast"),
            neutral_site=metadata.get("neutral_site", False),
            season_type=game_season_type,
            week_number=game_week_number,
            league=league,
            situation=situation,
            linescores=state.get("linescores"),
            game_id=game_id,
        )

        # Update final result in games dimension if game is complete
        if game_id and normalized_status in ("final", "final_ot"):
            try:
                update_game_result(
                    game_id=game_id,
                    home_score=state.get("home_score", 0),
                    away_score=state.get("away_score", 0),
                )
            except Exception:
                logger.warning(
                    "Failed to update game result for game_id=%s",
                    game_id,
                    exc_info=True,
                )

        # Extract and upsert DraftKings odds (if available).
        # Wrapped in try/except — odds failure NEVER blocks game state sync.
        if game_id:
            try:
                self._extract_and_upsert_odds(
                    game=game,
                    game_id=game_id,
                    league=league,
                    game_date=game_date,
                    home_team_code=home_team_info.get("team_code"),
                    away_team_code=away_team_info.get("team_code"),
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                )
            except Exception:
                logger.warning(
                    "Odds extraction failed for game_id=%s (non-blocking)",
                    game_id,
                    exc_info=True,
                )

        # upsert returns None when skip_if_unchanged=True and no meaningful
        # state change was detected (score, period, status, situation unchanged).
        # Only count as "updated" when a new SCD row was actually created.
        return result_id is not None

    def _extract_and_upsert_odds(
        self,
        game: ESPNGameFull,
        game_id: int,
        league: str,
        game_date: Any | None = None,
        home_team_code: str | None = None,
        away_team_code: str | None = None,
        home_team_id: int | None = None,
        away_team_id: int | None = None,
    ) -> None:
        """Extract DraftKings odds from ESPN data and upsert to game_odds.

        Called from _sync_game_to_db after game dimension upsert succeeds.
        Uses extract_espn_odds() to parse the raw competition odds, then
        upsert_game_odds() with SCD Type 2 versioning.

        Args:
            game: ESPNGameFull with metadata.odds populated
            game_id: FK to games.id
            league: League code (nfl, nba, etc.)
            game_date: Game date for the odds row
            home_team_code: Home team abbreviation
            away_team_code: Away team abbreviation

        Educational Note:
            This is intentionally fire-and-forget. If ESPN doesn't provide
            odds (some games don't have them), we silently skip. If parsing
            fails, we log at debug level and move on. Game state sync is
            always the priority.

        Reference:
            - Issue #533: ESPN DraftKings odds extraction
        """
        metadata = game.get("metadata", {})
        odds_list = metadata.get("odds", [])
        if not odds_list:
            return

        # Build a minimal competition-like dict for extract_espn_odds
        fake_competition: dict[str, Any] = {"odds": odds_list}
        parsed = extract_espn_odds(fake_competition)
        if parsed is None:
            return

        # Map league to sport for the game_odds table
        sport = LEAGUE_SPORT_CATEGORY.get(league, league)

        # Upsert with SCD Type 2
        resolved_date = (
            game_date.date() if game_date is not None and hasattr(game_date, "date") else game_date
        )
        upsert_game_odds(
            game_id=game_id,
            sport=sport,
            sportsbook="draftkings",
            game_date=resolved_date,
            home_team_code=home_team_code,
            away_team_code=away_team_code,
            spread_home_open=parsed.get("spread_home_open"),
            spread_home_close=parsed.get("spread_home_close"),
            spread_home_odds_open=parsed.get("spread_home_odds_open"),
            spread_home_odds_close=parsed.get("spread_home_odds_close"),
            spread_away_odds_open=parsed.get("spread_away_odds_open"),
            spread_away_odds_close=parsed.get("spread_away_odds_close"),
            moneyline_home_open=parsed.get("moneyline_home_open"),
            moneyline_home_close=parsed.get("moneyline_home_close"),
            moneyline_away_open=parsed.get("moneyline_away_open"),
            moneyline_away_close=parsed.get("moneyline_away_close"),
            total_open=parsed.get("total_open"),
            total_close=parsed.get("total_close"),
            over_odds_open=parsed.get("over_odds_open"),
            over_odds_close=parsed.get("over_odds_close"),
            under_odds_open=parsed.get("under_odds_open"),
            under_odds_close=parsed.get("under_odds_close"),
            home_favorite=parsed.get("home_favorite"),
            away_favorite=parsed.get("away_favorite"),
            home_favorite_at_open=parsed.get("home_favorite_at_open"),
            away_favorite_at_open=parsed.get("away_favorite_at_open"),
            details_text=parsed.get("details"),
            source="espn_poller",
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )

        logger.debug(
            "Odds upserted for game_id=%s: %s",
            game_id,
            parsed.get("details", "no details"),
        )

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


# =============================================================================
# Convenience Functions
# =============================================================================


def create_espn_poller(
    leagues: list[str] | None = None,
    poll_interval: int = 30,
    idle_interval: int = 300,
    persist_jobs: bool = False,
    job_store_url: str | None = None,
) -> ESPNGamePoller:
    """
    Factory function to create a configured ESPNGamePoller.

    Args:
        leagues: Leagues to poll (default: ["nfl", "ncaaf"])
        poll_interval: Seconds between polls when active (default: 60)
        idle_interval: Seconds between polls when idle (default: 300)
        persist_jobs: If True, persist scheduled jobs to database.
        job_store_url: SQLAlchemy URL for job store (required if persist_jobs=True).

    Returns:
        Configured ESPNGamePoller instance

    Example:
        >>> # Basic usage
        >>> poller = create_espn_poller(leagues=["nfl", "nba"])
        >>> poller.start()
        >>>
        >>> # With job persistence (survives restarts)
        >>> poller = create_espn_poller(
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
    return ESPNGamePoller(
        leagues=leagues,
        poll_interval=poll_interval,
        idle_interval=idle_interval,
        persist_jobs=persist_jobs,
        job_store_url=job_store_url,
    )


def run_single_espn_poll(leagues: list[str] | None = None) -> dict[str, int]:
    """
    Execute a single ESPN poll without starting the scheduler.

    Useful for CLI commands or on-demand updates.

    Args:
        leagues: Leagues to poll (default: ["nfl", "ncaaf"])

    Returns:
        Dictionary with {"items_fetched": N, "items_updated": M, "items_created": P}

    Example:
        >>> result = run_single_espn_poll(["nfl"])
        >>> print(f"Updated {result['items_updated']} games")
    """
    poller = ESPNGamePoller(leagues=leagues)
    return poller.poll_once()


def refresh_all_scoreboards(
    leagues: list[str] | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    Refresh ESPN scoreboard data for specified leagues.

    Convenience function that creates an ESPNGamePoller and calls refresh_scoreboards().
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
    poller = ESPNGamePoller(leagues=leagues)
    return poller.refresh_scoreboards(active_only=active_only)
