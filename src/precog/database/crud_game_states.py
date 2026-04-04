"""CRUD operations for game states, games dimension, and game odds.

Extracted from crud_operations.py during Phase 1c domain split.

Tables covered:
    - game_states: SCD Type 2 versioned live game state snapshots
    - games: Canonical game dimension table (ESPN-sourced)
    - game_odds: Pre-game and in-game odds from sportsbooks
"""

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor

logger = logging.getLogger(__name__)


TRACKED_SITUATION_KEYS: dict[str, list[str]] = {
    "football": [
        "possession",
        "down",
        "distance",
        "yard_line",
        "is_red_zone",
        "home_win_probability",
    ],
    "basketball": [
        "possession",
        "bonus",
        "possession_arrow",
        "home_fouls",
        "away_fouls",
        "home_win_probability",
    ],
    "hockey": [
        "home_powerplay",
        "away_powerplay",
        "home_win_probability",
    ],
}

# Maps league codes to sport categories
LEAGUE_SPORT_CATEGORY: dict[str, str] = {
    "nfl": "football",
    "ncaaf": "football",
    "nba": "basketball",
    "ncaab": "basketball",
    "wnba": "basketball",
    "ncaaw": "basketball",
    "nhl": "hockey",
    "mlb": "baseball",
    "mls": "soccer",
}


# =============================================================================
# GAME STATE OPERATIONS (Phase 2 - Live Data Integration, SCD Type 2)
# =============================================================================


def create_game_state(
    espn_event_id: str,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    venue_id: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    period: int = 0,
    clock_seconds: Decimal | None = None,
    clock_display: str | None = None,
    game_status: str = "pre",
    game_date: datetime | None = None,
    broadcast: str | None = None,
    neutral_site: bool = False,
    season_type: str | None = None,
    week_number: int | None = None,
    league: str | None = None,
    situation: dict | None = None,
    linescores: list | None = None,
    data_source: str = "espn",
    game_id: int | None = None,
) -> int:
    """
    Create initial game state record (row_current_ind = TRUE).

    Use this for NEW games only. For updates, use upsert_game_state()
    which handles SCD Type 2 versioning (closes old row, creates new).

    Args:
        espn_event_id: ESPN event identifier (natural key)
        home_team_id: Foreign key to teams.team_id for home team
        away_team_id: Foreign key to teams.team_id for away team
        venue_id: Foreign key to venues.venue_id
        home_score: Home team score
        away_score: Away team score
        period: Current period (0=pregame, 1-4=regulation, 5+=OT)
        clock_seconds: Seconds remaining in period
        clock_display: Human-readable clock (e.g., "5:32")
        game_status: Status ('pre', 'in_progress', 'halftime', 'final', etc.)
        game_date: Scheduled game start time
        broadcast: TV broadcast info
        neutral_site: TRUE for neutral venue games
        season_type: Season phase ('regular', 'playoff', 'bowl', etc.)
        week_number: Week number within season
        league: League code ('nfl', 'nba', etc.)
        situation: Sport-specific situation data (JSONB)
        linescores: Period-by-period scores (JSONB)
        data_source: Source of game data (default: 'espn')

    Returns:
        id (surrogate key) of newly created record

    Educational Note:
        Game states use SCD Type 2 for complete historical tracking:
        - Each score/clock change creates NEW row (old preserved)
        - row_current_ind = TRUE marks latest version
        - Enables replay: "What was the score at halftime?"
        - Critical for backtesting live trading strategies
        - ~190 updates per game = ~190 historical rows per game

        Key Structure:
        - id SERIAL (surrogate key) - returned by this function
        - espn_event_id (natural key) - used for SCD Type 2 versioning

    Example:
        >>> state_id = create_game_state(
        ...     espn_event_id="401547417",
        ...     home_team_id=1,
        ...     away_team_id=2,
        ...     venue_id=1,
        ...     game_status="pre",
        ...     game_date=datetime(2024, 11, 28, 16, 30),
        ...     league="nfl",
        ...     season_type="regular",
        ...     week_number=12
        ... )

    References:
        - REQ-DATA-001: Game State Data Collection (SCD Type 2)
        - ADR-029: ESPN Data Model with Normalized Schema
        - Pattern 2: Dual Versioning System (SCD Type 2)
    """
    insert_query = """
        INSERT INTO game_states (
            espn_event_id, home_team_id, away_team_id, venue_id,
            home_score, away_score, period, clock_seconds, clock_display,
            game_status, game_date, broadcast, neutral_site,
            season_type, week_number, league, situation, linescores,
            data_source, game_id, row_current_ind, row_start_ts
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, TRUE, NOW()
        )
        RETURNING id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            insert_query,
            (
                espn_event_id,
                home_team_id,
                away_team_id,
                venue_id,
                home_score,
                away_score,
                period,
                clock_seconds,
                clock_display,
                game_status,
                game_date,
                broadcast,
                neutral_site,
                season_type,
                week_number,
                league,
                json.dumps(situation) if situation else None,
                json.dumps(linescores) if linescores else None,
                data_source,
                game_id,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["id"])


def get_current_game_state(espn_event_id: str) -> dict[str, Any] | None:
    """
    Get current (latest) game state for an event.

    Args:
        espn_event_id: ESPN event identifier

    Returns:
        Dictionary with current game state, or None if not found

    Educational Note:
        Always query with row_current_ind = TRUE to get latest version.
        Without this filter, you may get historical rows with stale data.

    Example:
        >>> state = get_current_game_state("401547417")
        >>> if state:
        ...     print(f"{state['home_score']}-{state['away_score']} ({state['clock_display']})")
    """
    query = """
        SELECT gs.*,
               th.team_code AS home_team_code, th.team_name AS home_team_name,
               ta.team_code AS away_team_code, ta.team_name AS away_team_name,
               v.venue_name, v.city, v.state
        FROM game_states gs
        LEFT JOIN teams th ON gs.home_team_id = th.team_id
        LEFT JOIN teams ta ON gs.away_team_id = ta.team_id
        LEFT JOIN venues v ON gs.venue_id = v.venue_id
        WHERE gs.espn_event_id = %s
          AND gs.row_current_ind = TRUE
    """
    return fetch_one(query, (espn_event_id,))


def game_state_changed(
    current: dict[str, Any] | None,
    home_score: int,
    away_score: int,
    period: int,
    game_status: str,
    situation: dict | None = None,
    league: str | None = None,
) -> bool:
    """
    Check if game state has meaningfully changed from current database state.

    Used by upsert_game_state to avoid creating duplicate SCD Type 2 rows
    when game state hasn't changed. This reduces database bloat during
    high-frequency polling (e.g., every 15-30 seconds during live games).

    Sport-aware situation comparison:
        When league is provided, only sport-relevant situation keys are
        compared. This prevents high-frequency fields (e.g., foul counts
        in basketball, shot counts in hockey) from creating noisy SCD rows.

        If league is None or unrecognized, ALL situation keys are compared
        as a safe fallback (more rows is better than missing changes).

    Args:
        current: Current game state from database (None if no existing state)
        home_score: New home team score
        away_score: New away team score
        period: New period number
        game_status: New game status
        situation: New situation data (downs, possession, etc.)
        league: League code (e.g., "nfl", "nba", "nhl") for sport-aware
            situation filtering. None falls back to full comparison.

    Returns:
        True if state has changed and a new row should be created,
        False if state is the same and no update needed.

    Educational Note:
        We intentionally DO NOT compare clock_seconds or clock_display because:
        - Clock changes every few seconds during play
        - This would create ~1000+ rows per game instead of ~50-100
        - Score, period, status, and situation changes are what matter for trading

        We DO compare:
        - home_score, away_score: Core game state
        - period: Quarter/half transitions
        - game_status: Pre/in_progress/halftime/final transitions
        - situation: Sport-specific keys only (see TRACKED_SITUATION_KEYS)

    Example:
        >>> current = get_current_game_state("401547417")
        >>> if game_state_changed(current, 14, 7, 2, "in_progress", {"possession": "KC"}, league="nfl"):
        ...     upsert_game_state("401547417", home_score=14, ...)

    References:
        - Issue #234: State Change Detection requirement
        - Issue #397: Game states SCD noise tuning
        - REQ-DATA-001: Game State Data Collection
    """
    # No current state = always insert (new game)
    if current is None:
        return True

    # Compare core state fields
    if current.get("home_score") != home_score:
        return True
    if current.get("away_score") != away_score:
        return True
    if current.get("period") != period:
        return True
    if current.get("game_status") != game_status:
        return True

    # Compare situation (JSONB field) if provided
    # Only compare if new situation is provided - ignore if None
    if situation is not None:
        current_situation = current.get("situation") or {}

        # Determine which situation keys to compare based on sport
        sport_category = LEAGUE_SPORT_CATEGORY.get(league.lower()) if league else None
        tracked_keys = TRACKED_SITUATION_KEYS.get(sport_category) if sport_category else None

        if tracked_keys is not None:
            # Sport-aware: only compare tracked keys for this sport
            for key in tracked_keys:
                if situation.get(key) != current_situation.get(key):
                    return True
        else:
            # Unknown league or None: compare ALL situation keys (safe fallback)
            all_keys = set(situation.keys()) | set(current_situation.keys())
            for key in all_keys:
                if situation.get(key) != current_situation.get(key):
                    return True

    return False


def upsert_game_state(
    espn_event_id: str,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    venue_id: int | None = None,
    home_score: int = 0,
    away_score: int = 0,
    period: int = 0,
    clock_seconds: Decimal | None = None,
    clock_display: str | None = None,
    game_status: str = "pre",
    game_date: datetime | None = None,
    broadcast: str | None = None,
    neutral_site: bool = False,
    season_type: str | None = None,
    week_number: int | None = None,
    league: str | None = None,
    situation: dict | None = None,
    linescores: list | None = None,
    data_source: str = "espn",
    skip_if_unchanged: bool = True,
    game_id: int | None = None,
) -> int | None:
    """
    Insert or update game state with SCD Type 2 versioning.

    If game exists: closes current row (row_current_ind=FALSE) and inserts new.
    If game doesn't exist: creates new row with row_current_ind=TRUE.

    This is the primary function for updating live game data from ESPN API.

    Args:
        (same as create_game_state)
        data_source: Source of game data (default: 'espn')
        skip_if_unchanged: If True, skip update when state hasn't meaningfully
            changed (score, period, status, situation). Default True.
            Set to False to always create a new row (legacy behavior).

    Returns:
        id (surrogate key) of newly created record, or None if skipped due to
        no state change (when skip_if_unchanged=True).

    Educational Note:
        SCD Type 2 UPSERT pattern:
        1. Check if current row exists for espn_event_id
        2. If exists: UPDATE to close it (row_current_ind=FALSE, row_end_ts=NOW)
        3. INSERT new row with row_current_ind=TRUE

        State Change Detection (Issue #234):
        When skip_if_unchanged=True (default), we check if meaningful state has
        changed before creating a new row. This prevents database bloat from
        high-frequency polling (~1000 rows/game -> ~50-100 rows/game).

        "Meaningful" changes include: score, period, game_status, situation.
        Clock changes are intentionally ignored (changes every few seconds).

    Example:
        >>> # Update score during game
        >>> state_id = upsert_game_state(
        ...     espn_event_id="401547417",
        ...     home_score=7,
        ...     away_score=3,
        ...     period=1,
        ...     clock_display="5:32",
        ...     game_status="in_progress",
        ...     situation={"possession": "KC", "down": 2, "distance": 7}
        ... )
        >>> if state_id is None:
        ...     print("No state change - update skipped")

    References:
        - REQ-DATA-001: Game State Data Collection (SCD Type 2)
        - Issue #234: State Change Detection
        - Pattern 2: Dual Versioning System
    """
    # State change detection (Issue #234)
    # Check if meaningful state has changed before creating a new SCD row
    if skip_if_unchanged:
        current = get_current_game_state(espn_event_id)
        if not game_state_changed(
            current, home_score, away_score, period, game_status, situation, league=league
        ):
            # No meaningful change - return None to indicate skip
            return None

    # Use a SINGLE transaction for all operations to maintain atomicity
    # This ensures that if INSERT fails, the close is also rolled back
    #
    # Educational Note:
    #   SCD Type 2 upsert is a 2-step atomic operation:
    #   1. Close current row (row_current_ind = FALSE)
    #   2. Insert new row with row_current_ind = TRUE
    #   Both must succeed or both must fail (ACID transaction)

    close_query = """
        UPDATE game_states
        SET row_current_ind = FALSE,
            row_end_ts = NOW()
        WHERE espn_event_id = %s
          AND row_current_ind = TRUE
    """

    insert_query = """
        INSERT INTO game_states (
            espn_event_id, home_team_id, away_team_id, venue_id,
            home_score, away_score, period, clock_seconds, clock_display,
            game_status, game_date, broadcast, neutral_site,
            season_type, week_number, league, situation, linescores,
            data_source, game_id, row_current_ind, row_start_ts
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, TRUE, NOW()
        )
        RETURNING id
    """

    with get_cursor(commit=True) as cur:
        # Step 1: Close current row (if exists)
        cur.execute(close_query, (espn_event_id,))

        # Step 2: Insert new row
        cur.execute(
            insert_query,
            (
                espn_event_id,
                home_team_id,
                away_team_id,
                venue_id,
                home_score,
                away_score,
                period,
                clock_seconds,
                clock_display,
                game_status,
                game_date,
                broadcast,
                neutral_site,
                season_type,
                week_number,
                league,
                json.dumps(situation) if situation else None,
                json.dumps(linescores) if linescores else None,
                data_source,
                game_id,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["id"])


def get_game_state_history(espn_event_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    Get historical game state versions for an event.

    Returns all versions ordered by timestamp (newest first), useful for:
    - Reviewing game progression
    - Backtesting trading decisions
    - Debugging data pipeline issues

    Args:
        espn_event_id: ESPN event identifier
        limit: Maximum rows to return (default 100)

    Returns:
        List of game state records ordered by row_start_ts DESC

    Example:
        >>> history = get_game_state_history("401547417")
        >>> for state in history[:5]:
        ...     print(f"{state['row_start_ts']}: {state['home_score']}-{state['away_score']}")
    """
    query = """
        SELECT *
        FROM game_states
        WHERE espn_event_id = %s
        ORDER BY row_start_ts DESC
        LIMIT %s
    """
    return fetch_all(query, (espn_event_id, limit))


def get_live_games(
    league: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get all currently in-progress games with pagination.

    Args:
        league: Filter by league (optional)
        limit: Maximum number of games to return (default: 100)
        offset: Number of games to skip for pagination (default: 0)

    Returns:
        List of current game states for in-progress games

    Example:
        >>> games = get_live_games(league="nfl")
        >>> for g in games:
        ...     print(f"{g['home_team_code']} vs {g['away_team_code']}")
    """
    conditions = ["gs.row_current_ind = TRUE", "gs.game_status = 'in_progress'"]
    params: list[Any] = []

    if league:
        conditions.append("gs.league = %s")
        params.append(league)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT gs.*,
               th.team_code AS home_team_code, th.display_name AS home_team_name,
               ta.team_code AS away_team_code, ta.display_name AS away_team_name,
               v.venue_name
        FROM game_states gs
        LEFT JOIN teams th ON gs.home_team_id = th.team_id
        LEFT JOIN teams ta ON gs.away_team_id = ta.team_id
        LEFT JOIN venues v ON gs.venue_id = v.venue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY gs.game_date
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


def get_games_by_date(
    game_date: datetime,
    league: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Get all games scheduled for a specific date with pagination.

    Args:
        game_date: Date to query (time component ignored)
        league: Filter by league (optional)
        limit: Maximum number of games to return (default: 100)
        offset: Number of games to skip for pagination (default: 0)

    Returns:
        List of current game states for games on that date

    Example:
        >>> from datetime import datetime
        >>> games = get_games_by_date(datetime(2024, 11, 28), league="nfl")
        >>> for g in games:
        ...     print(f"{g['game_date']}: {g['home_team_code']} vs {g['away_team_code']}")
    """
    conditions = [
        "gs.row_current_ind = TRUE",
        "DATE(gs.game_date) = DATE(%s)",
    ]
    params: list[Any] = [game_date]

    if league:
        conditions.append("gs.league = %s")
        params.append(league)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT gs.*,
               th.team_code AS home_team_code, th.display_name AS home_team_name,
               ta.team_code AS away_team_code, ta.display_name AS away_team_name,
               v.venue_name
        FROM game_states gs
        LEFT JOIN teams th ON gs.home_team_id = th.team_id
        LEFT JOIN teams ta ON gs.away_team_id = ta.team_id
        LEFT JOIN venues v ON gs.venue_id = v.venue_id
        WHERE {" AND ".join(conditions)}
        ORDER BY gs.game_date, gs.league
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


# =============================================================================
# HISTORICAL STATS CRUD OPERATIONS
# =============================================================================
# Functions for historical_stats table (Migration 0009)
# Used for storing player/team statistics from external data sources
# =============================================================================


# =============================================================================
# Games Dimension CRUD (Migration 0035)
# =============================================================================


def get_or_create_game(
    sport: str,
    game_date: date,
    home_team_code: str,
    away_team_code: str,
    *,
    season: int | None = None,
    league: str | None = None,
    season_type: str | None = None,
    week_number: int | None = None,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    venue_id: int | None = None,
    venue_name: str | None = None,
    neutral_site: bool = False,
    is_playoff: bool = False,
    game_type: str | None = None,
    game_time: datetime | None = None,
    espn_event_id: str | None = None,
    external_game_id: str | None = None,
    game_status: str = "scheduled",
    data_source: str = "espn",
    home_score: int | None = None,
    away_score: int | None = None,
    source_file: str | None = None,
    attendance: int | None = None,
) -> int:
    """
    Insert or update a game in the games dimension table (idempotent).

    Uses ON CONFLICT on the natural key (sport, game_date, home_team_code,
    away_team_code) to upsert. On conflict, updates non-null fields via
    COALESCE to avoid overwriting good data with NULLs.

    Args:
        sport: Sport code ('nfl', 'nba', etc.)
        game_date: Date of the game
        home_team_code: Home team abbreviation (e.g., 'KC')
        away_team_code: Away team abbreviation (e.g., 'BAL')
        season: Season year (derived from game_date if not provided)
        league: League code (defaults to sport if not provided)
        season_type: Season phase ('regular', 'playoff', etc.)
        week_number: Week number within season
        home_team_id: FK to teams.team_id for home team
        away_team_id: FK to teams.team_id for away team
        venue_id: FK to venues.venue_id
        venue_name: Denormalized venue name
        neutral_site: True if neutral venue
        is_playoff: True if playoff game
        game_type: Game classification ('regular', 'playoff', etc.)
        game_time: Precise game start timestamp
        espn_event_id: ESPN event identifier for cross-source linking
        external_game_id: External game identifier
        game_status: Current status ('scheduled', 'final', etc.)
        data_source: Data provenance ('espn', 'fivethirtyeight', etc.)
        home_score: Home team final score
        away_score: Away team final score
        source_file: Source filename for file-based imports
        attendance: Game attendance

    Returns:
        id of the games row (created or existing)

    Example:
        >>> game_id = get_or_create_game(
        ...     sport="football",
        ...     game_date=date(2024, 9, 8),
        ...     home_team_code="KC",
        ...     away_team_code="BAL",
        ...     season=2024,
        ...     league="nfl",
        ...     espn_event_id="401547417",
        ...     game_status="final",
        ... )

    References:
        - Migration 0035: games dimension table
        - Issue #439: Games dimension unification
    """
    # Derive season from game_date year if not provided
    if season is None:
        season = game_date.year

    # League is required — sport values ("football") don't match league CHECK
    # constraint ("nfl"/"ncaaf"). All callers must pass league explicitly.
    if league is None:
        raise ValueError(
            f"league is required for get_or_create_game(). "
            f"sport='{sport}' cannot be used as league default after "
            f"Phase B rename. Pass league explicitly."
        )

    query = """
        INSERT INTO games (
            sport, game_date, home_team_code, away_team_code,
            season, league, season_type, week_number,
            home_team_id, away_team_id, venue_id, venue_name,
            neutral_site, is_playoff, game_type,
            game_time, espn_event_id, external_game_id,
            game_status, data_source,
            home_score, away_score, source_file, attendance
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (sport, game_date, home_team_code, away_team_code) DO UPDATE SET
            updated_at = NOW(),
            espn_event_id = COALESCE(EXCLUDED.espn_event_id, games.espn_event_id),
            game_status = CASE
                WHEN games.game_status IN ('final', 'final_ot') THEN games.game_status
                ELSE EXCLUDED.game_status
            END,
            home_team_id = COALESCE(EXCLUDED.home_team_id, games.home_team_id),
            away_team_id = COALESCE(EXCLUDED.away_team_id, games.away_team_id),
            venue_id = COALESCE(EXCLUDED.venue_id, games.venue_id),
            venue_name = COALESCE(EXCLUDED.venue_name, games.venue_name),
            season_type = COALESCE(EXCLUDED.season_type, games.season_type),
            week_number = COALESCE(EXCLUDED.week_number, games.week_number),
            game_time = COALESCE(EXCLUDED.game_time, games.game_time),
            neutral_site = EXCLUDED.neutral_site,
            is_playoff = EXCLUDED.is_playoff,
            game_type = COALESCE(EXCLUDED.game_type, games.game_type),
            home_score = COALESCE(EXCLUDED.home_score, games.home_score),
            away_score = COALESCE(EXCLUDED.away_score, games.away_score),
            data_source = EXCLUDED.data_source,
            source_file = COALESCE(EXCLUDED.source_file, games.source_file),
            attendance = COALESCE(EXCLUDED.attendance, games.attendance)
        RETURNING id
    """
    params = (
        sport,
        game_date,
        home_team_code,
        away_team_code,
        season,
        league,
        season_type,
        week_number,
        home_team_id,
        away_team_id,
        venue_id,
        venue_name,
        neutral_site,
        is_playoff,
        game_type,
        game_time,
        espn_event_id,
        external_game_id,
        game_status,
        data_source,
        home_score,
        away_score,
        source_file,
        attendance,
    )
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["id"])


def update_game_result(
    game_id: int,
    home_score: int,
    away_score: int,
) -> None:
    """
    Update final scores, margin, and result for a completed game.

    Called by the ESPN poller when game_status transitions to 'final' or
    'final_ot'. Computes actual_margin (home - away) and result
    ('home_win', 'away_win', 'draw') automatically.

    Args:
        game_id: Primary key of the games row
        home_score: Home team final score
        away_score: Away team final score

    Example:
        >>> update_game_result(game_id=42, home_score=27, away_score=20)
        # Sets actual_margin=7, result='home_win'

    References:
        - Migration 0035: games dimension table
    """
    # Compute derived fields
    actual_margin = home_score - away_score
    if home_score > away_score:
        result = "home_win"
    elif away_score > home_score:
        result = "away_win"
    else:
        result = "draw"

    query = """
        UPDATE games
        SET home_score = %s,
            away_score = %s,
            actual_margin = %s,
            result = %s,
            updated_at = NOW()
        WHERE id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (home_score, away_score, actual_margin, result, game_id))


def update_bracket_counts() -> int:
    """
    Batch-update bracket_count for all markets based on their parent event.

    bracket_count = number of markets sharing the same event_internal_id.
    Markets without an event_internal_id get bracket_count = NULL (not 0),
    since they have no parent event to count within.

    Only rows where the current bracket_count differs from the computed
    value (or is NULL when it shouldn't be) are updated, avoiding
    unnecessary writes.

    Returns:
        Number of market rows actually updated.

    Example:
        >>> from precog.database.crud_operations import update_bracket_counts
        >>> updated = update_bracket_counts()
        >>> print(f"Updated {updated} market bracket counts")
    """
    query = """
        WITH counts AS (
            SELECT event_internal_id, COUNT(*) AS cnt
            FROM markets
            WHERE event_internal_id IS NOT NULL
            GROUP BY event_internal_id
        )
        UPDATE markets m
        SET bracket_count = c.cnt,
            updated_at = NOW()
        FROM counts c
        WHERE m.event_internal_id = c.event_internal_id
          AND (m.bracket_count IS DISTINCT FROM c.cnt)
    """
    # Also null out bracket_count for markets with no event (shouldn't be 0)
    null_query = """
        UPDATE markets
        SET bracket_count = NULL,
            updated_at = NOW()
        WHERE event_internal_id IS NULL
          AND bracket_count IS NOT NULL
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query)
        updated_with_event: int = cur.rowcount
        cur.execute(null_query)
        updated_without_event: int = cur.rowcount
    return updated_with_event + updated_without_event


# =============================================================================
# TEAM KALSHI CODE OPERATIONS (Issue #462 - Event-to-Game Matching)
# =============================================================================
# These functions support matching Kalshi events to games by looking up
# teams via Kalshi-specific team codes (which may differ from ESPN codes).


def update_event_game_id(event_internal_id: int, game_id: int) -> bool:
    """Set game_id on an existing event. Returns True if updated.

    Links a Kalshi event to an ESPN game by setting the FK. This is
    called when the matching module finds a game for an event that was
    previously unlinked (game_id IS NULL).

    Args:
        event_internal_id: The events.id (integer surrogate PK)
        game_id: The games.id to link to

    Returns:
        True if the event was updated, False if event not found or
        already linked to this game.

    Example:
        >>> updated = update_event_game_id(event_pk=42, game_id=15)
        >>> if updated:
        ...     print("Event linked to game")

    Related:
        - Migration 0038: events.game_id FK to games(id)
        - Issue #462: Event-to-game matching
    """
    query = """
        UPDATE events
        SET game_id = %s, updated_at = NOW()
        WHERE id = %s AND (game_id IS NULL OR game_id != %s)
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (game_id, event_internal_id, game_id))
        return bool(cur.rowcount > 0)


def update_event(
    event_internal_id: int,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    status: str | None = None,
    result: dict | None = None,
    description: str | None = None,
) -> bool:
    """Update one or more fields on an existing event.

    Accepts the integer surrogate PK and only updates fields that are
    explicitly provided (non-None). Always bumps ``updated_at``.

    Args:
        event_internal_id: The events.id (integer surrogate PK).
        start_time: New start time (ISO 8601 string). PostgreSQL handles
            ISO string -> TIMESTAMPTZ conversion natively.
        end_time: New end time (ISO 8601 string).
        status: New status. Must be one of: 'scheduled', 'live', 'final',
            'cancelled', 'postponed' (validated against CHECK constraint).
        result: Settlement result as a dict. Serialized to JSONB via
            ``json.dumps()``, matching the pattern used for metadata in
            ``create_event()``.
        description: Updated description text.

    Returns:
        True if a row was updated, False if the event was not found.

    Raises:
        ValueError: If ``status`` is not a valid CHECK constraint value.

    Example:
        >>> updated = update_event(42, status="final", result={"winner": "yes"})
        >>> if updated:
        ...     print("Event settled")

    References:
        - events.status CHECK: ('scheduled', 'live', 'final', 'cancelled', 'postponed')
        - Task 5 (settlement detection) will call this to transition events.
        - Pattern follows ``update_event_game_id()`` above.
    """
    valid_statuses = {"scheduled", "live", "final", "cancelled", "postponed"}

    if status is not None and status not in valid_statuses:
        raise ValueError(
            f"Invalid event status '{status}'. Must be one of: {sorted(valid_statuses)}"
        )

    # Build SET clause dynamically — only include non-None fields
    set_parts: list[str] = []
    params: list[Any] = []

    if start_time is not None:
        set_parts.append("start_time = %s")
        params.append(start_time)
    if end_time is not None:
        set_parts.append("end_time = %s")
        params.append(end_time)
    if status is not None:
        set_parts.append("status = %s")
        params.append(status)
    if result is not None:
        set_parts.append("result = %s")
        params.append(json.dumps(result))
    if description is not None:
        set_parts.append("description = %s")
        params.append(description)

    if not set_parts:
        # Nothing to update — caller passed all None
        return False

    # Always bump updated_at
    set_parts.append("updated_at = NOW()")

    query = f"UPDATE events SET {', '.join(set_parts)} WHERE id = %s"  # noqa: S608
    params.append(event_internal_id)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        return bool(cur.rowcount > 0)


def check_event_fully_settled(event_internal_id: int) -> bool:
    """Check whether all markets in an event have settled.

    Uses a single aggregate query to count total markets and settled
    markets for the given event.  Returns True only when at least one
    market exists AND every market has ``status = 'settled'``.

    Args:
        event_internal_id: The events.id (integer surrogate PK).

    Returns:
        True if all markets in the event are settled (and at least one
        market exists).  False otherwise.

    Example:
        >>> if check_event_fully_settled(42):
        ...     update_event(42, status="final")

    References:
        - Task 5: Market settlement detection
        - Called by KalshiMarketPoller._sync_market_to_db after a market
          transitions to 'settled'.
    """
    query = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'settled') AS settled
        FROM markets
        WHERE event_internal_id = %s
    """
    result = fetch_one(query, (event_internal_id,))
    if result is None:
        return False
    total = int(result["total"])
    settled = int(result["settled"])
    return total > 0 and total == settled


def build_event_result(event_internal_id: int) -> dict[str, Any]:
    """Build a JSONB result summary from child markets' settlement values.

    Queries all markets for the given event and assembles a dict suitable
    for storing in ``events.result`` (JSONB column).  Settlement values
    are serialized as strings to preserve Decimal precision.

    Args:
        event_internal_id: The events.id (integer surrogate PK).

    Returns:
        Dict with structure::

            {
                "markets_total": 3,
                "markets_settled": 3,
                "outcomes": {
                    "TICKER-1": {"settlement_value": "1.0000"},
                    "TICKER-2": {"settlement_value": "0.0000"},
                    "TICKER-3": {"settlement_value": null}
                }
            }

        If no markets exist for the event, returns a dict with zero
        counts and an empty outcomes dict.

    Example:
        >>> result = build_event_result(42)
        >>> update_event(42, status="final", result=result)

    Educational Note:
        Settlement values are ``Decimal(10,4)`` in the database.  Storing
        them as strings in JSONB (e.g., ``"1.0000"``) avoids the float
        precision trap (``json.dumps(float(Decimal("0.3333")))`` loses
        precision).  Consumers parse back with ``Decimal(value)``.

    Reference:
        - Issue #513: Enrichment data gaps — event result population
        - check_event_fully_settled(): companion function
        - KalshiMarketPoller settlement propagation
    """
    query = """
        SELECT ticker, settlement_value, status
        FROM markets
        WHERE event_internal_id = %s
        ORDER BY ticker
    """
    rows = fetch_all(query, (event_internal_id,))

    markets_total = len(rows)
    markets_settled = sum(1 for r in rows if r["status"] == "settled")

    outcomes: dict[str, dict[str, str | None]] = {}
    for row in rows:
        sv = row["settlement_value"]
        outcomes[row["ticker"]] = {
            "settlement_value": str(sv) if sv is not None else None,
        }

    return {
        "markets_total": markets_total,
        "markets_settled": markets_settled,
        "outcomes": outcomes,
    }


def find_unlinked_sports_events(league: str | None = None) -> list[dict[str, Any]]:
    """Find events where game_id IS NULL and category='sports'.

    Used by EventGameMatcher.backfill_unlinked_events() to find events
    that need matching.

    Args:
        league: Optional subcategory/league filter (e.g., "nfl", "nba").

    Returns:
        List of event dicts with keys: id, external_id, title, subcategory.

    Example:
        >>> unlinked = find_unlinked_sports_events("nfl")
        >>> print(f"{len(unlinked)} NFL events need matching")

    Related:
        - EventGameMatcher.backfill_unlinked_events(): Primary consumer
        - Issue #462: Event-to-game matching
    """
    if league:
        query = """
            SELECT id, external_id, title, subcategory
            FROM events
            WHERE game_id IS NULL
              AND category = 'sports'
              AND subcategory = %s
            ORDER BY id
        """
        return fetch_all(query, (league,))

    query = """
        SELECT id, external_id, title, subcategory
        FROM events
        WHERE game_id IS NULL
          AND category = 'sports'
        ORDER BY id
    """
    return fetch_all(query)


def find_game_by_matchup(
    league: str,
    game_date: date,
    home_team_code: str,
    away_team_code: str,
) -> int | None:
    """Look up a game by league + date + team codes. Returns games.id or None.

    The games table natural key is (sport, game_date, home_team_code,
    away_team_code). This function maps from league to sport using the
    LEAGUE_SPORT_CATEGORY dict and queries by the natural key.

    Uses cascading date lookup to handle Kalshi ET vs ESPN UTC date offsets:
    1. Try exact date (most common)
    2. Try date+1 (late-night ET game → next day UTC)
    3. Try date-1 (early UTC → previous day ET)

    If +/-1 day returns multiple matches (e.g., back-to-back playoff games
    between the same teams on consecutive days), returns None to avoid
    linking to the wrong game. This is extremely rare but handled safely.

    Args:
        league: League code (e.g., "nfl", "nba", "ncaaf")
        game_date: Date of the game (from Kalshi ticker, Eastern Time)
        home_team_code: ESPN/canonical home team code (e.g., "KC")
        away_team_code: ESPN/canonical away team code (e.g., "BAL")

    Returns:
        games.id (integer) if found, None otherwise.

    Example:
        >>> from datetime import date
        >>> game_id = find_game_by_matchup(
        ...     league="nfl",
        ...     game_date=date(2026, 1, 18),
        ...     home_team_code="NE",
        ...     away_team_code="HOU",
        ... )

    Related:
        - Migration 0035: games dimension table with natural key
        - EventGameMatcher._find_game(): Primary consumer
        - Issue #462: Event-to-game matching
        - Issue #524: Fuzzy date matching for ET/UTC offset
    """
    # Map league to sport for the natural key query
    sport = LEAGUE_SPORT_CATEGORY.get(league)
    if sport is None:
        logger.warning(
            "Unknown league '%s' — cannot map to sport for game lookup",
            league,
        )
        return None

    exact_query = """
        SELECT id FROM games
        WHERE sport = %s
          AND game_date = %s
          AND home_team_code = %s
          AND away_team_code = %s
    """
    # 1. Try exact date first (most common, cheapest)
    result = fetch_one(exact_query, (sport, game_date, home_team_code, away_team_code))
    if result:
        return cast("int", result["id"])

    # 2. Try +/-1 day window (handles Kalshi ET vs ESPN UTC offset)
    #    Use a single query to find all matches in the 3-day window,
    #    then check for ambiguity.
    fuzzy_query = """
        SELECT id, game_date FROM games
        WHERE sport = %s
          AND game_date BETWEEN %s AND %s
          AND home_team_code = %s
          AND away_team_code = %s
    """
    day_before = game_date - timedelta(days=1)
    day_after = game_date + timedelta(days=1)
    results = fetch_all(
        fuzzy_query,
        (sport, day_before, day_after, home_team_code, away_team_code),
    )

    if len(results) == 1:
        # Exactly one match in the +/-1 day window — safe to link
        return cast("int", results[0]["id"])

    if len(results) > 1:
        # Multiple matches (e.g., back-to-back playoff games) — ambiguous
        logger.debug(
            "Ambiguous fuzzy date match: %s %s@%s on %s found %d games in +/-1d window",
            league,
            away_team_code,
            home_team_code,
            game_date,
            len(results),
        )

    return None


# =============================================================================
# Game Odds (ESPN DraftKings Odds) — SCD Type 2
# =============================================================================


def upsert_game_odds(
    game_id: int,
    sport: str,
    sportsbook: str,
    *,
    game_date: Any | None = None,
    home_team_code: str | None = None,
    away_team_code: str | None = None,
    spread_home_open: Any | None = None,
    spread_home_close: Any | None = None,
    spread_home_odds_open: int | None = None,
    spread_home_odds_close: int | None = None,
    spread_away_odds_open: int | None = None,
    spread_away_odds_close: int | None = None,
    moneyline_home_open: int | None = None,
    moneyline_home_close: int | None = None,
    moneyline_away_open: int | None = None,
    moneyline_away_close: int | None = None,
    total_open: Any | None = None,
    total_close: Any | None = None,
    over_odds_open: int | None = None,
    over_odds_close: int | None = None,
    under_odds_open: int | None = None,
    under_odds_close: int | None = None,
    home_favorite: bool | None = None,
    away_favorite: bool | None = None,
    home_favorite_at_open: bool | None = None,
    away_favorite_at_open: bool | None = None,
    details_text: str | None = None,
    source: str = "espn_poller",
    home_team_id: int | None = None,
    away_team_id: int | None = None,
) -> int | None:
    """Upsert game odds with SCD Type 2 versioning.

    Compares incoming close values against the current row. If any tracked
    value changed, the current row is closed (row_current_ind=FALSE) and a
    new version is inserted. If values are unchanged, only updated_at is bumped.

    Change detection fields (the "close" values that move during line movement):
        - spread_home_close
        - moneyline_home_close
        - moneyline_away_close
        - total_close

    Args:
        game_id: FK to games.id (required for ESPN poller path)
        sport: Sport code ('nfl', 'nba', etc.)
        sportsbook: Sportsbook name ('draftkings', 'consensus', etc.)
        game_date: Game date (for CSV import path, optional for ESPN)
        home_team_code: Home team abbreviation (for CSV import path)
        away_team_code: Away team abbreviation (for CSV import path)
        spread_home_*: Home point spread values (Decimal/NUMERIC(5,1))
        spread_home_odds_*: Home spread odds (American format integer)
        spread_away_odds_*: Away spread odds (American format integer)
        moneyline_*: Moneyline odds (American format integer)
        total_*: Over/under total line (Decimal/NUMERIC(5,1))
        over_odds_*, under_odds_*: Total line odds (American format integer)
        home_favorite, away_favorite: Current favorite flags
        home_favorite_at_open, away_favorite_at_open: Opening favorite flags
        details_text: Human-readable summary (e.g., "BOS -3.5")
        source: Data source identifier (default: 'espn_poller')

    Returns:
        The game_odds.id of the current/new row, or None on error.

    Educational Note:
        This follows the same SCD Type 2 pattern as update_market_with_versioning():
        1. Find current row (WHERE game_id = X AND sportsbook = Y AND row_current_ind = TRUE)
        2. Compare tracked fields
        3. If changed: close current row, insert new version
        4. If unchanged: just bump updated_at

    Reference:
        - Issue #533: ESPN DraftKings odds extraction
        - Migration 0048: game_odds table with SCD Type 2
        - update_market_with_versioning() for pattern reference
    """
    with get_cursor(commit=True) as cur:
        # Step 1: Find current row for this game+sportsbook
        cur.execute(
            """
            SELECT id, spread_home_close, moneyline_home_close,
                   moneyline_away_close, total_close
            FROM game_odds
            WHERE game_id = %s
              AND sportsbook = %s
              AND row_current_ind = TRUE
            """,
            (game_id, sportsbook),
        )
        current = cur.fetchone()

        if current is not None:
            # Step 2: Compare tracked fields for change detection
            # Convert DB Decimals to strings for safe comparison with incoming values
            def _eq(db_val: Any, new_val: Any) -> bool:
                """Compare DB value to new value, treating None == None."""
                if db_val is None and new_val is None:
                    return True
                if db_val is None or new_val is None:
                    return False
                return str(db_val) == str(new_val)

            changed = not all(
                [
                    _eq(current["spread_home_close"], spread_home_close),
                    _eq(current["moneyline_home_close"], moneyline_home_close),
                    _eq(current["moneyline_away_close"], moneyline_away_close),
                    _eq(current["total_close"], total_close),
                ]
            )

            if not changed:
                # No line movement -- just bump updated_at
                cur.execute(
                    "UPDATE game_odds SET updated_at = NOW() WHERE id = %s",
                    (current["id"],),
                )
                return cast("int", current["id"])

            # Step 3: Close current row (SCD Type 2)
            cur.execute(
                """
                UPDATE game_odds
                SET row_current_ind = FALSE,
                    row_end_ts = NOW()
                WHERE id = %s
                """,
                (current["id"],),
            )

        # Step 4: Insert new version
        cur.execute(
            """
            INSERT INTO game_odds (
                game_id, sport, game_date, home_team_code, away_team_code,
                sportsbook, source,
                spread_home_open, spread_home_close,
                spread_home_odds_open, spread_home_odds_close,
                spread_away_odds_open, spread_away_odds_close,
                moneyline_home_open, moneyline_home_close,
                moneyline_away_open, moneyline_away_close,
                total_open, total_close,
                over_odds_open, over_odds_close,
                under_odds_open, under_odds_close,
                home_favorite, away_favorite,
                home_favorite_at_open, away_favorite_at_open,
                details_text,
                home_team_id, away_team_id,
                row_current_ind, row_start_ts, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s,
                TRUE, NOW(), NOW()
            )
            RETURNING id
            """,
            (
                game_id,
                sport,
                game_date,
                home_team_code,
                away_team_code,
                sportsbook,
                source,
                spread_home_open,
                spread_home_close,
                spread_home_odds_open,
                spread_home_odds_close,
                spread_away_odds_open,
                spread_away_odds_close,
                moneyline_home_open,
                moneyline_home_close,
                moneyline_away_open,
                moneyline_away_close,
                total_open,
                total_close,
                over_odds_open,
                over_odds_close,
                under_odds_open,
                under_odds_close,
                home_favorite,
                away_favorite,
                home_favorite_at_open,
                away_favorite_at_open,
                details_text,
                home_team_id,
                away_team_id,
            ),
        )
        row = cur.fetchone()
        return cast("int", row["id"]) if row else None
