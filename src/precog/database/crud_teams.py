"""CRUD operations for teams, venues, and external team codes.

Extracted from crud_operations.py during Phase 1b domain split.

Tables covered:
    - teams: Team master data with ESPN identifiers
    - venues: Game venues with ESPN venue IDs
    - team_rankings: Point-in-time ranking snapshots
    - external_team_codes: Cross-platform team identifier mapping
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

import psycopg2.errors

from .connection import fetch_all, fetch_one, get_cursor

logger = logging.getLogger(__name__)


# =============================================================================
# VENUE OPERATIONS (Phase 2 - Live Data Integration)
# =============================================================================


def create_venue(
    espn_venue_id: str,
    venue_name: str,
    city: str | None = None,
    state: str | None = None,
    capacity: int | None = None,
    indoor: bool = False,
) -> int:
    """
    Create new venue record (or update if ESPN venue ID exists).

    Venues are mutable entities - no SCD Type 2 versioning. Updates use
    simple UPDATE statements since venue data rarely changes and history
    is not needed for trading decisions.

    Args:
        espn_venue_id: ESPN unique venue identifier (e.g., "3622")
        venue_name: Full venue name (e.g., "GEHA Field at Arrowhead Stadium")
        city: City where venue is located
        state: State/province abbreviation or full name
        capacity: Maximum seating capacity
        indoor: TRUE for domed stadiums/indoor arenas

    Returns:
        venue_id of created/updated record

    Educational Note:
        Venues use UPSERT (INSERT ... ON CONFLICT UPDATE) because:
        - ESPN venue IDs are stable external identifiers
        - Venue data changes rarely (naming rights updates)
        - No need for historical versioning (not trading-relevant)
        - Simplifies data pipeline (always upsert, never check exists)

    Example:
        >>> venue_id = create_venue(
        ...     espn_venue_id="3622",
        ...     venue_name="GEHA Field at Arrowhead Stadium",
        ...     city="Kansas City",
        ...     state="Missouri",
        ...     capacity=76416,
        ...     indoor=False
        ... )

    References:
        - REQ-DATA-002: Venue Data Management
        - ADR-029: ESPN Data Model with Normalized Schema
    """
    # Normalize capacity: ESPN API sometimes returns 0 for unknown capacity
    # DB constraint requires capacity IS NULL OR capacity > 0
    if capacity is not None and capacity <= 0:
        capacity = None

    query = """
        INSERT INTO venues (
            espn_venue_id, venue_name, city, state, capacity, indoor
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (espn_venue_id) WHERE row_current_ind = TRUE
        DO UPDATE SET
            venue_name = EXCLUDED.venue_name,
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            capacity = EXCLUDED.capacity,
            indoor = EXCLUDED.indoor,
            updated_at = NOW()
        RETURNING venue_id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (espn_venue_id, venue_name, city, state, capacity, indoor))
        result = cur.fetchone()
        return cast("int", result["venue_id"])


def get_venue_by_espn_id(espn_venue_id: str) -> dict[str, Any] | None:
    """
    Get venue by ESPN venue ID.

    Args:
        espn_venue_id: ESPN unique venue identifier

    Returns:
        Dictionary with venue data, or None if not found

    Example:
        >>> venue = get_venue_by_espn_id("3622")
        >>> if venue:
        ...     print(f"{venue['venue_name']} - {venue['city']}, {venue['state']}")
    """
    query = """
        SELECT *
        FROM venues
        WHERE espn_venue_id = %s
    """
    return fetch_one(query, (espn_venue_id,))


def get_venue_by_id(venue_id: int) -> dict[str, Any] | None:
    """
    Get venue by internal venue_id.

    Args:
        venue_id: Internal venue ID

    Returns:
        Dictionary with venue data, or None if not found
    """
    query = """
        SELECT *
        FROM venues
        WHERE venue_id = %s
    """
    return fetch_one(query, (venue_id,))


# =============================================================================
# TEAM LOOKUP OPERATIONS
# =============================================================================
# These functions provide team lookup by various identifiers.
# Essential for the live polling service to map ESPN IDs to database IDs.


# =============================================================================
# TEAM LOOKUP OPERATIONS
# =============================================================================
# These functions provide team lookup by various identifiers.
# Essential for the live polling service to map ESPN IDs to database IDs.


def get_team_by_espn_id(espn_team_id: str, league: str | None = None) -> dict[str, Any] | None:
    """
    Get team by ESPN team ID and optional league filter.

    Educational Note:
        ESPN team IDs are unique per-league but NOT globally unique.
        For example, team ID "1" might exist in both NFL and NBA.
        Always provide the league parameter when you know it to ensure
        correct team matching.

    Args:
        espn_team_id: ESPN's unique team identifier (e.g., "12" for Chiefs)
        league: Optional league filter (nfl, ncaaf, nba, ncaab, nhl, wnba)
                Recommended to prevent cross-league mismatches.

    Returns:
        Dictionary with team data, or None if not found.
        Includes: team_id, team_code, team_name, display_name, espn_team_id,
                  conference, division, sport, league, current_elo

    Example:
        >>> team = get_team_by_espn_id("12", league="nfl")
        >>> if team:
        ...     print(f"{team['team_name']} ({team['team_code']})")
        ...     # Kansas City Chiefs (KC)

    Reference: REQ-DATA-003 (Multi-Sport Support)
    """
    if league:
        query = """
            SELECT *
            FROM teams
            WHERE espn_team_id = %s AND league = %s
        """
        return fetch_one(query, (espn_team_id, league))
    query = """
            SELECT *
            FROM teams
            WHERE espn_team_id = %s
        """
    return fetch_one(query, (espn_team_id,))


def create_team(
    team_code: str,
    team_name: str,
    display_name: str,
    sport: str,
    league: str,
    espn_team_id: str | None = None,
    current_elo_rating: Decimal | None = None,
    conference: str | None = None,
    division: str | None = None,
) -> int:
    """
    Create a new team record in the teams table.

    Uses a lookup-first strategy to find existing teams, then INSERT with
    try/except for UniqueViolation to handle race conditions. This approach
    works regardless of which unique constraints exist on the table.

    Lookup order:
        1. By (espn_team_id, league) if espn_team_id is provided
        2. By (team_code, sport, league) — ONLY when espn_team_id is None.
           When espn_team_id is provided but Step 1 finds no match, the team
           is genuinely new. Falling back to code lookup would match a
           DIFFERENT team with the same abbreviation (e.g., two "MISS" teams
           in NCAAF — Ole Miss and Mississippi State).

    Args:
        team_code: Abbreviation code (e.g., 'KC', 'BOS', 'TBL')
        team_name: Full team name (e.g., 'Kansas City Chiefs')
        display_name: Short display name (e.g., 'Chiefs')
        sport: Sport name for the sport column (e.g., 'football', 'basketball')
        league: League code for the league column (e.g., 'nfl', 'nba')
        espn_team_id: ESPN unique team identifier (e.g., '12')
        current_elo_rating: Elo rating from calibrated computation. None if not
            yet calculated. Do NOT pass a placeholder value (e.g., 1500) —
            use the EloEngine to compute real ratings from game results.
        conference: Conference name (e.g., 'AFC', 'Eastern')
        division: Division name (e.g., 'West', 'Atlantic')

    Returns:
        team_id of the created or existing team

    Educational Note:
        The teams table may have multiple unique constraints depending on
        migration state:
        - UNIQUE(team_code, sport) - legacy constraint (being phased out)
        - Partial UNIQUE(espn_team_id, league) WHERE espn_team_id IS NOT NULL
        - Partial UNIQUE(team_code, sport) for pro leagues only (migration 0018)
        This function avoids referencing any specific constraint in SQL,
        using lookup-first + try/except instead of ON CONFLICT.

    Example:
        >>> team_id = create_team(
        ...     team_code="KC",
        ...     team_name="Kansas City Chiefs",
        ...     display_name="Chiefs",
        ...     sport="football",
        ...     league="nfl",
        ...     espn_team_id="12",
        ...     conference="AFC",
        ...     division="West",
        ... )

    Related:
        - get_team_by_espn_id() (lookup by ESPN ID)
        - espn_team_validator._create_missing_team() (caller for auto-sync)
    """
    # Step 1: Look up existing team by ESPN ID (most specific identifier)
    if espn_team_id:
        existing = fetch_one(
            "SELECT team_id FROM teams WHERE espn_team_id = %s AND league = %s",
            (espn_team_id, league),
        )
        if existing:
            team_id = int(existing["team_id"] if isinstance(existing, dict) else existing[0])
            logger.debug(
                "Team found by ESPN ID: %s %s (espn_id=%s, team_id=%d)",
                league.upper(),
                team_code,
                espn_team_id,
                team_id,
            )
            return team_id

    # Step 2: Fall back to lookup by (team_code, sport, league)
    # ONLY when espn_team_id is not provided. When ESPN gives us a team_id
    # and Step 1 didn't find it, the team is genuinely new — the code
    # fallback would match a DIFFERENT team with the same abbreviation
    # (college sports have many code collisions, e.g., two "MISS" in NCAAF).
    if not espn_team_id:
        existing = fetch_one(
            "SELECT team_id FROM teams WHERE team_code = %s AND sport = %s AND league = %s",
            (team_code, sport, league),
        )
        if existing:
            team_id = int(existing["team_id"] if isinstance(existing, dict) else existing[0])
            logger.debug(
                "Team found by code: %s %s (team_id=%d)",
                league.upper(),
                team_code,
                team_id,
            )
            return team_id

    # Step 3: Team doesn't exist — INSERT it
    insert_query = """
        INSERT INTO teams (
            team_code, team_name, display_name, sport, league,
            espn_team_id, current_elo_rating, conference, division
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING team_id
    """
    params = (
        team_code,
        team_name,
        display_name,
        sport,
        league,
        espn_team_id,
        current_elo_rating,
        conference,
        division,
    )

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(insert_query, params)
            row = cur.fetchone()
            if row:
                team_id = int(row["team_id"] if isinstance(row, dict) else row[0])
                logger.info(
                    "Created team: %s %s (%s, espn_id=%s, team_id=%d)",
                    league.upper(),
                    team_code,
                    team_name,
                    espn_team_id,
                    team_id,
                )
                return team_id

    except psycopg2.errors.UniqueViolation:
        # Race condition: another process created this team between our
        # SELECT and INSERT. Look it up again to get the team_id.
        logger.warning(
            "UniqueViolation on team insert: %s %s (espn_id=%s, league=%s). "
            "Retrieving existing record.",
            league.upper(),
            team_code,
            espn_team_id,
            league,
        )
        # Try ESPN ID first, then team_code (same guard as Step 2)
        if espn_team_id:
            conflicting = fetch_one(
                "SELECT team_id FROM teams WHERE espn_team_id = %s AND league = %s",
                (espn_team_id, league),
            )
            if conflicting:
                return int(
                    conflicting["team_id"] if isinstance(conflicting, dict) else conflicting[0]
                )
        # Code fallback only when no ESPN ID — prevents same collision
        # bug as Step 2 (defense-in-depth, see #486)
        if not espn_team_id:
            conflicting = fetch_one(
                "SELECT team_id FROM teams WHERE team_code = %s AND sport = %s AND league = %s",
                (team_code, sport, league),
            )
            if conflicting:
                return int(
                    conflicting["team_id"] if isinstance(conflicting, dict) else conflicting[0]
                )

    # Should not reach here, but defensive
    raise ValueError(f"Failed to create or find team: {team_code} ({sport}/{league})")


# =============================================================================
# TEAM RANKING OPERATIONS (Phase 2 - Live Data Integration)
# =============================================================================


# =============================================================================
# TEAM RANKING OPERATIONS (Phase 2 - Live Data Integration)
# =============================================================================


def create_team_ranking(
    team_id: int,
    ranking_type: str,
    rank: int,
    season: int,
    ranking_date: datetime,
    week: int | None = None,
    points: int | None = None,
    first_place_votes: int | None = None,
    previous_rank: int | None = None,
) -> int:
    """
    Create new team ranking record.

    Rankings are append-only history - no SCD Type 2, no updates. Each
    week's ranking is a separate record. Use UPSERT to handle re-imports
    of the same week's rankings.

    Args:
        team_id: Foreign key to teams.team_id
        ranking_type: Type of ranking ('ap_poll', 'cfp', 'coaches_poll', etc.)
        rank: Numeric rank position (1 = best)
        season: Season year (e.g., 2024)
        ranking_date: Date ranking was released
        week: Week number (1-18), None for preseason/final
        points: Poll points (AP/Coaches)
        first_place_votes: Number of #1 votes
        previous_rank: Previous week's rank (None if was unranked)

    Returns:
        ranking_id of created/updated record

    Educational Note:
        Rankings use temporal validity (season + week) instead of SCD Type 2:
        - Each week's poll is a distinct point-in-time snapshot
        - No need to track intra-week changes (polls released weekly)
        - Simpler queries: "Get AP Poll week 12" vs "Get AP Poll at timestamp X"
        - History preserved naturally via (team, type, season, week) uniqueness

    Example:
        >>> ranking_id = create_team_ranking(
        ...     team_id=1,
        ...     ranking_type="ap_poll",
        ...     rank=3,
        ...     season=2024,
        ...     week=12,
        ...     ranking_date=datetime(2024, 11, 17),
        ...     points=1432,
        ...     first_place_votes=12
        ... )

    References:
        - REQ-DATA-004: Team Rankings Storage (Temporal Validity)
        - ADR-029: ESPN Data Model with Normalized Schema
    """
    query = """
        INSERT INTO team_rankings (
            team_id, ranking_type, rank, season, week, ranking_date,
            points, first_place_votes, previous_rank
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (team_id, ranking_type, season, week)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            ranking_date = EXCLUDED.ranking_date,
            points = EXCLUDED.points,
            first_place_votes = EXCLUDED.first_place_votes,
            previous_rank = EXCLUDED.previous_rank
        RETURNING ranking_id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                team_id,
                ranking_type,
                rank,
                season,
                week,
                ranking_date,
                points,
                first_place_votes,
                previous_rank,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["ranking_id"])


def get_team_rankings(
    team_id: int,
    ranking_type: str | None = None,
    season: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get ranking history for a team.

    Args:
        team_id: Team ID to lookup
        ranking_type: Filter by ranking type (optional)
        season: Filter by season (optional)

    Returns:
        List of ranking records ordered by season, week

    Example:
        >>> rankings = get_team_rankings(team_id=1, ranking_type="ap_poll", season=2024)
        >>> for r in rankings:
        ...     print(f"Week {r['week']}: #{r['rank']} ({r['points']} pts)")
    """
    conditions = ["team_id = %s"]
    params: list[Any] = [team_id]

    if ranking_type:
        conditions.append("ranking_type = %s")
        params.append(ranking_type)

    if season:
        conditions.append("season = %s")
        params.append(season)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM team_rankings
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, week DESC NULLS LAST
    """  # noqa: S608
    return fetch_all(query, tuple(params))


def get_current_rankings(
    ranking_type: str, season: int, week: int | None = None
) -> list[dict[str, Any]]:
    """
    Get current rankings for a ranking type.

    If week is not specified, returns the most recent week's rankings.

    Args:
        ranking_type: Type of ranking ('ap_poll', 'cfp', etc.)
        season: Season year
        week: Specific week (optional, defaults to latest)

    Returns:
        List of ranking records ordered by rank

    Example:
        >>> rankings = get_current_rankings("ap_poll", 2024)
        >>> for r in rankings[:5]:
        ...     print(f"#{r['rank']}: Team {r['team_id']} ({r['points']} pts)")
    """
    if week is None:
        # Get most recent week
        week_query = """
            SELECT MAX(week) as max_week
            FROM team_rankings
            WHERE ranking_type = %s AND season = %s
        """
        result = fetch_one(week_query, (ranking_type, season))
        if not result or result["max_week"] is None:
            return []
        week = result["max_week"]

    query = """
        SELECT tr.*, t.team_code, t.team_name, t.display_name
        FROM team_rankings tr
        JOIN teams t ON tr.team_id = t.team_id
        WHERE tr.ranking_type = %s
          AND tr.season = %s
          AND tr.week = %s
        ORDER BY tr.rank
    """
    return fetch_all(query, (ranking_type, season, week))


# =============================================================================
# GAME STATE OPERATIONS (Phase 2 - Live Data Integration, SCD Type 2)
# =============================================================================


# =============================================================================
# TEAM KALSHI CODE OPERATIONS (Issue #462 - Event-to-Game Matching)
# =============================================================================
# These functions support matching Kalshi events to games by looking up
# teams via Kalshi-specific team codes (which may differ from ESPN codes).


def get_team_by_kalshi_code(kalshi_code: str, league: str) -> dict[str, Any] | None:
    """Look up a team by its Kalshi platform team code and league.

    Kalshi uses slightly different team codes than ESPN for some teams
    (e.g., JAC vs JAX for Jacksonville). This function finds the team
    regardless of which code system is used.

    Search order:
        1. Check kalshi_team_code column (explicit mismatches)
        2. Check team_code column (most teams where codes match)

    Args:
        kalshi_code: Team code as used by Kalshi (e.g., "JAC", "HOU")
        league: League code (e.g., "nfl", "nba")

    Returns:
        Dictionary with team data, or None if not found.

    Example:
        >>> team = get_team_by_kalshi_code("JAC", "nfl")
        >>> if team:
        ...     print(f"{team['team_name']} ({team['team_code']})")
        ...     # Jacksonville Jaguars (JAX)

    Related:
        - Migration 0041: teams.kalshi_team_code column
        - Issue #462: Event-to-game matching
    """
    # First check explicit kalshi_team_code (mismatches like JAC -> JAX)
    query_kalshi = """
        SELECT * FROM teams
        WHERE kalshi_team_code = %s AND league = %s
    """
    result = fetch_one(query_kalshi, (kalshi_code, league))
    if result:
        return result

    # Fall back to team_code (most teams use same code on both platforms)
    query_code = """
        SELECT * FROM teams
        WHERE team_code = %s AND league = %s
    """
    return fetch_one(query_code, (kalshi_code, league))


def get_teams_with_kalshi_codes(league: str | None = None) -> list[dict[str, Any]]:
    """Get all teams for building the Kalshi team code registry.

    Returns all teams (or teams for a specific league) with their
    team_code, league, and kalshi_team_code. Used by TeamCodeRegistry
    to build its in-memory lookup cache.

    Args:
        league: Optional league filter. If None, returns all teams.

    Returns:
        List of team dicts with keys: team_id, team_code, league,
        kalshi_team_code (may be None), classification (may be None).

    Example:
        >>> teams = get_teams_with_kalshi_codes("nfl")
        >>> for t in teams:
        ...     kalshi = t['kalshi_team_code'] or t['team_code']
        ...     print(f"{kalshi} -> {t['team_code']}")

    Related:
        - TeamCodeRegistry.load(): Primary consumer
        - Issue #462: Event-to-game matching
    """
    if league:
        query = """
            SELECT team_id, team_code, league, kalshi_team_code, classification
            FROM teams
            WHERE league = %s
            ORDER BY team_code
        """
        return fetch_all(query, (league,))

    query = """
        SELECT team_id, team_code, league, kalshi_team_code, classification
        FROM teams
        ORDER BY league, team_code
    """
    return fetch_all(query)


# =============================================================================
# EXTERNAL TEAM CODES CRUD (Migration 0045)
# =============================================================================
# These functions manage the external_team_codes table, which maps team codes
# from external platforms (Kalshi, Polymarket, ESPN, etc.) to the canonical
# team_id in our teams table. This replaces the fragile in-memory collision
# resolution with a persistent, auditable, multi-source mapping.
#
# Related:
#   - Issue #516: External team codes table
#   - Migration 0045: CREATE TABLE external_team_codes
#   - TeamCodeRegistry.load_from_external_codes(): Primary consumer


def create_external_team_code(
    team_id: int,
    source: str,
    source_team_code: str,
    league: str,
    confidence: str = "heuristic",
    verified_at: str | None = None,
    notes: str | None = None,
) -> int:
    """Create a new external team code mapping.

    Maps a source platform's team code to a canonical team_id. For example,
    Kalshi's "JAC" in NFL maps to team_id for Jacksonville Jaguars.

    Args:
        team_id: FK to teams.team_id (the canonical team).
        source: Platform name ('kalshi', 'polymarket', 'espn', 'odds_api', 'cfbd').
        source_team_code: The code that platform uses for the team.
        league: League code ('nfl', 'nba', 'ncaaf', etc.).
        confidence: How the mapping was established.
            'exact' = verified by API or human check.
            'manual' = set by a human but not independently verified.
            'heuristic' = inferred (e.g., assumed Kalshi code = ESPN code).
        verified_at: ISO 8601 timestamp of when the mapping was verified.
            None if not yet verified.
        notes: Optional human-readable notes about this mapping.

    Returns:
        The new row's id (SERIAL PK).

    Raises:
        psycopg2.errors.UniqueViolation: If (source, source_team_code, league)
            already exists. Use upsert_external_team_code() for idempotent writes.
        psycopg2.errors.ForeignKeyViolation: If team_id does not exist in teams.

    Example:
        >>> code_id = create_external_team_code(
        ...     team_id=42,
        ...     source="kalshi",
        ...     source_team_code="JAC",
        ...     league="nfl",
        ...     confidence="manual",
        ...     notes="Kalshi uses JAC for Jacksonville, ESPN uses JAX",
        ... )
        >>> print(code_id)  # 1

    Related:
        - Issue #516: External team codes table
        - Migration 0045: CREATE TABLE external_team_codes
    """
    query = """
        INSERT INTO external_team_codes
            (team_id, source, source_team_code, league, confidence, verified_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (team_id, source, source_team_code, league, confidence, verified_at, notes),
        )
        row = cur.fetchone()
        return cast("int", row["id"])


def get_external_team_codes(
    source: str | None = None,
    league: str | None = None,
    team_id: int | None = None,
) -> list[dict[str, Any]]:
    """Get external team codes with optional filters.

    Returns all external team code mappings, optionally filtered by any
    combination of source, league, and team_id.

    Args:
        source: Filter by platform name (e.g., 'kalshi', 'espn').
        league: Filter by league code (e.g., 'nfl', 'ncaaf').
        team_id: Filter by canonical team_id.

    Returns:
        List of dicts with all columns from external_team_codes.
        Empty list if no matches.

    Example:
        >>> # All Kalshi NFL codes
        >>> codes = get_external_team_codes(source="kalshi", league="nfl")
        >>> len(codes)  # 32 (one per NFL team)

        >>> # All codes for a specific team
        >>> codes = get_external_team_codes(team_id=42)
        >>> for c in codes:
        ...     print(f"{c['source']}: {c['source_team_code']}")
        ...     # kalshi: JAC
        ...     # espn: JAX

    Related:
        - Issue #516: External team codes table
    """
    conditions: list[str] = []
    params: list[Any] = []

    if source is not None:
        conditions.append("source = %s")
        params.append(source)
    if league is not None:
        conditions.append("league = %s")
        params.append(league)
    if team_id is not None:
        conditions.append("team_id = %s")
        params.append(team_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT id, team_id, source, source_team_code, league,
               confidence, verified_at, notes, created_at, updated_at
        FROM external_team_codes
        {where_clause}
        ORDER BY source, league, source_team_code
    """  # noqa: S608
    return fetch_all(query, tuple(params) if params else None)


def find_team_by_external_code(
    source: str,
    source_team_code: str,
    league: str,
) -> dict[str, Any] | None:
    """Look up a team by its external platform code.

    The key lookup function: given a source platform's code and league,
    resolve to the canonical team row from the teams table. Joins
    external_team_codes with teams to return the full team record.

    Args:
        source: Platform name ('kalshi', 'polymarket', 'espn', etc.).
        source_team_code: The code that platform uses for the team.
        league: League code ('nfl', 'nba', 'ncaaf', etc.).

    Returns:
        Dictionary with the full team row (from teams table) plus the
        external code's confidence level, or None if no mapping exists.

    Example:
        >>> team = find_team_by_external_code("kalshi", "JAC", "nfl")
        >>> if team:
        ...     print(f"{team['team_name']} ({team['team_code']})")
        ...     # Jacksonville Jaguars (JAX)
        ...     print(f"Confidence: {team['confidence']}")
        ...     # Confidence: manual

    Related:
        - Issue #516: External team codes table
        - get_team_by_kalshi_code(): Legacy equivalent (teams table only)
    """
    query = """
        SELECT t.*, etc.confidence, etc.source_team_code AS external_code
        FROM external_team_codes etc
        JOIN teams t ON t.team_id = etc.team_id
        WHERE etc.source = %s
          AND etc.source_team_code = %s
          AND etc.league = %s
    """
    return fetch_one(query, (source, source_team_code, league))


def upsert_external_team_code(
    team_id: int,
    source: str,
    source_team_code: str,
    league: str,
    confidence: str = "heuristic",
    notes: str | None = None,
) -> int:
    """Insert or update an external team code mapping (idempotent).

    Uses PostgreSQL's INSERT ... ON CONFLICT ... DO UPDATE to either
    create a new mapping or update an existing one. The conflict key is
    (source, source_team_code, league).

    On conflict (existing mapping): updates team_id, confidence, notes,
    and updated_at. This allows bulk seeding to be run repeatedly without
    duplicates.

    Args:
        team_id: FK to teams.team_id (the canonical team).
        source: Platform name ('kalshi', 'polymarket', 'espn', etc.).
        source_team_code: The code that platform uses for the team.
        league: League code ('nfl', 'nba', 'ncaaf', etc.).
        confidence: How the mapping was established ('exact', 'manual',
            'heuristic').
        notes: Optional human-readable notes about this mapping.

    Returns:
        The row's id (either newly created or existing).

    Raises:
        psycopg2.errors.ForeignKeyViolation: If team_id does not exist.

    Example:
        >>> # First call creates the row
        >>> id1 = upsert_external_team_code(42, "kalshi", "JAC", "nfl", "manual")
        >>> # Second call updates (idempotent)
        >>> id2 = upsert_external_team_code(42, "kalshi", "JAC", "nfl", "exact")
        >>> assert id1 == id2  # Same row updated

    Related:
        - Issue #516: External team codes table
        - scripts/seed_external_team_codes.py: Primary consumer
    """
    query = """
        INSERT INTO external_team_codes
            (team_id, source, source_team_code, league, confidence, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source, source_team_code, league)
        DO UPDATE SET
            team_id = EXCLUDED.team_id,
            confidence = EXCLUDED.confidence,
            notes = EXCLUDED.notes,
            updated_at = NOW()
        RETURNING id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (team_id, source, source_team_code, league, confidence, notes))
        row = cur.fetchone()
        return cast("int", row["id"])


def delete_external_team_code(code_id: int) -> bool:
    """Delete an external team code mapping by its PK.

    Args:
        code_id: The external_team_codes.id to delete.

    Returns:
        True if a row was deleted, False if no row with that id existed.

    Example:
        >>> deleted = delete_external_team_code(42)
        >>> print(deleted)  # True

    Related:
        - Issue #516: External team codes table
    """
    query = "DELETE FROM external_team_codes WHERE id = %s"
    with get_cursor(commit=True) as cur:
        cur.execute(query, (code_id,))
        return bool(cur.rowcount > 0)


# =============================================================================
# Game Odds (ESPN DraftKings Odds) — SCD Type 2
# =============================================================================
