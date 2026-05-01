"""CRUD operations for Elo ratings and calculation logs.

Extracted from crud_operations.py during Phase 1c domain split.

Tables covered:
    - teams (elo_rating, classification columns): Team Elo state
    - elo_calculation_log: Audit trail for Elo rating changes
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, cast

from .connection import fetch_all, fetch_one, get_cursor
from .crud_lookups import get_league_id_or_none

logger = logging.getLogger(__name__)


# =============================================================================
# Elo Rating Operations
# =============================================================================
# CRUD operations for managing team Elo ratings across the multi-table
# Elo architecture:
#
#   - teams.current_elo_rating: Live/current rating (updated after each game)
#   - historical_elo: Seeded from external sources (FiveThirtyEight, etc.)
#   - elo_calculation_log: Audit trail of every Elo computation (PRIMARY)
#
# Note: elo_rating_history was REMOVED in migration 0015 (2025-12-26).
#       It was superseded by elo_calculation_log which provides:
#         1. Game-centric view (both teams per row) vs team-centric
#         2. Full audit trail with parameters (K-factor, MOV, expected scores)
#         3. Links to source game (game_states or games)
#
#   To get team-centric view from elo_calculation_log:
#     SELECT game_date, home_post_elo as rating FROM elo_calculation_log
#     WHERE home_team_id = :team_id
#     UNION ALL
#     SELECT game_date, away_post_elo as rating FROM elo_calculation_log
#     WHERE away_team_id = :team_id
#     ORDER BY game_date
#
# References:
#   - Migration 0001: teams.current_elo_rating (elo_rating_history removed)
#   - Migration 0005: historical_elo
#   - Migration 0013: elo_calculation_log, historical_epa
#   - Migration 0015: Dropped deprecated elo_rating_history table
#   - ADR-109: Elo Rating Computation Engine Architecture
#   - Issue #273: Comprehensive Elo Rating Computation Module
#   - Issue #277: Remove deprecated elo_rating_history table
# =============================================================================


def update_team_elo_rating(
    team_id: int,
    new_rating: Decimal,
) -> bool:
    """
    Update a team's current Elo rating in the teams table.

    This function syncs the computed Elo rating to the teams table after
    processing a game. It's the final step in the Elo computation pipeline:

        historical_elo (bootstrap) -> elo_calculation_log (audit)
            -> teams.current_elo_rating (LIVE)

    Note: elo_rating_history was removed in migration 0015 (superseded by elo_calculation_log).

    Args:
        team_id: Primary key of the team in the teams table
        new_rating: New Elo rating value (typically 1000-2000 range)

    Returns:
        True if update succeeded, False if team not found

    Example:
        >>> # After computing new Elo from game result
        >>> success = update_team_elo_rating(team_id=42, new_rating=Decimal("1567.25"))
        >>> if success:
        ...     print("Team Elo updated successfully")

    Educational Note:
        Elo ratings are stored as DECIMAL(10,2) for precision. The valid range
        is 0-3000 per the CHECK constraint in Migration 0001. Typical ratings:
        - 1500: Average team (starting point)
        - 1600-1700: Good team (playoff contender)
        - 1700+: Elite team (championship caliber)
        - Below 1400: Rebuilding/struggling team

    References:
        - Migration 0001: teams.current_elo_rating column
        - ADR-109: Elo Rating Computation Engine Architecture
    """
    query = """
        UPDATE teams
        SET current_elo_rating = %s,
            updated_at = NOW()
        WHERE team_id = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (new_rating, team_id))
        return int(cur.rowcount or 0) > 0


def update_team_classification(
    team_id: int,
    classification: str | None = None,
    conference: str | None = None,
) -> bool:
    """Update a team's classification and/or conference.

    Used by the CFBD backfill to populate division classification
    (FBS/FCS/D2/D3/professional) and conference for teams that were
    auto-created without this data.

    Args:
        team_id: Primary key of the team
        classification: Division classification (fbs, fcs, d2, d3, professional)
        conference: Conference name (SEC, Big Ten, etc.)

    Returns:
        True if update succeeded, False if team not found

    Example:
        >>> update_team_classification(42, classification="fbs", conference="SEC")
    """
    sets = []
    params: list[Any] = []
    if classification is not None:
        sets.append("classification = %s")
        params.append(classification)
    if conference is not None:
        sets.append("conference = %s")
        params.append(conference)
    if not sets:
        return False
    sets.append("updated_at = NOW()")
    params.append(team_id)
    query = f"UPDATE teams SET {', '.join(sets)} WHERE team_id = %s"  # noqa: S608
    with get_cursor(commit=True) as cur:
        cur.execute(query, tuple(params))
        return int(cur.rowcount or 0) > 0


def get_team_elo_rating(team_id: int) -> Decimal | None:
    """
    Get a team's current Elo rating from the teams table.

    Args:
        team_id: Primary key of the team

    Returns:
        Current Elo rating as Decimal, or None if team not found

    Example:
        >>> rating = get_team_elo_rating(team_id=42)
        >>> if rating is not None:  # Pattern 45: explicit None, not falsy guard
        ...     print(f"Team Elo: {rating}")
    """
    result = fetch_one(
        "SELECT current_elo_rating FROM teams WHERE team_id = %s",
        (team_id,),
    )
    # Pattern 45 (None-preserving sanitization): explicit None check —
    # do NOT use a falsy guard, which conflates rating=0 with missing rating.
    # See #1027.
    if not result:
        return None
    rating = result.get("current_elo_rating")
    if rating is None:
        return None
    return Decimal(str(rating))


def get_team_elo_by_code(
    team_code: str,
    league: str | None = None,
) -> Decimal | None:
    """
    Get a team's current Elo rating by team code.

    Args:
        team_code: Team abbreviation (e.g., 'KC', 'LAL', 'BOS')
        league: Optional league filter (e.g., 'nfl', 'nba'). Queries teams.league.

    Returns:
        Current Elo rating as Decimal, or None if team not found

    Note:
        If multiple teams share the same team_code (e.g., 'ATL' in both
        NFL and MLS), a warning is logged and the first result is returned.
        Callers should provide the league parameter to avoid ambiguity.

    Example:
        >>> rating = get_team_elo_by_code("KC", league="nfl")
        >>> print(f"Chiefs Elo: {rating}")
    """
    if league:
        results = fetch_all(
            "SELECT current_elo_rating FROM teams WHERE team_code = %s AND league = %s",
            (team_code, league),
        )
    else:
        results = fetch_all(
            "SELECT current_elo_rating FROM teams WHERE team_code = %s",
            (team_code,),
        )
    if not results:
        return None
    if len(results) > 1:
        logger.warning(
            "Ambiguous team_code lookup: '%s' (league=%s) matched %d rows. "
            "Returning first result. Pass league parameter to disambiguate.",
            team_code,
            league,
            len(results),
        )
    result = results[0]
    # Pattern 45 (None-preserving sanitization): explicit None check —
    # do NOT use a falsy guard, which conflates rating=0 with missing rating.
    # See #1027.
    if not result:
        return None
    rating = result.get("current_elo_rating")
    if rating is None:
        return None
    return Decimal(str(rating))


def insert_elo_calculation_log(
    league: str,
    game_date: date,
    home_team_code: str,
    away_team_code: str,
    home_score: int,
    away_score: int,
    home_elo_before: Decimal,
    away_elo_before: Decimal,
    k_factor: int,
    home_advantage: Decimal,
    home_expected: Decimal,
    away_expected: Decimal,
    home_actual: Decimal,
    away_actual: Decimal,
    home_elo_change: Decimal,
    away_elo_change: Decimal,
    home_elo_after: Decimal,
    away_elo_after: Decimal,
    calculation_source: str,
    *,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    game_state_id: int | None = None,
    game_id: int | None = None,
    mov_multiplier: Decimal | None = None,
    home_epa_adjustment: Decimal | None = None,
    away_epa_adjustment: Decimal | None = None,
    calculation_version: str = "1.0",
) -> int:
    """
    Insert a record into the elo_calculation_log audit table.

    This function captures every Elo calculation for debugging, compliance,
    and historical analysis. It records all inputs and outputs of the
    Elo formula including K-factor, home advantage, and EPA adjustments.

    Args:
        sport: Sport code ('nfl', 'nba', 'nhl', 'mlb', etc.)
        game_date: Date of the game
        home_team_code: Home team abbreviation
        away_team_code: Away team abbreviation
        home_score: Home team final score
        away_score: Away team final score
        home_elo_before: Home team Elo before game
        away_elo_before: Away team Elo before game
        k_factor: K-factor used (NFL: 20, NBA: 20, NHL: 6, MLB: 4)
        home_advantage: Home advantage points applied (NFL: 65, NBA: 100)
        home_expected: Expected score for home team (0.0 to 1.0)
        away_expected: Expected score for away team (0.0 to 1.0)
        home_actual: Actual score for home team (1.0=win, 0.5=tie, 0.0=loss)
        away_actual: Actual score for away team (1.0=win, 0.5=tie, 0.0=loss)
        home_elo_change: Change in home team Elo
        away_elo_change: Change in away team Elo
        home_elo_after: Home team Elo after game
        away_elo_after: Away team Elo after game
        calculation_source: How triggered ('bootstrap', 'realtime', 'backfill', 'manual')
        home_team_id: FK to teams.team_id (optional, for live games)
        away_team_id: FK to teams.team_id (optional, for live games)
        game_state_id: FK to game_states.id (optional)
        game_id: FK to games.id (optional)
        mov_multiplier: Margin of victory multiplier (optional)
        home_epa_adjustment: EPA-based adjustment for home team (NFL only)
        away_epa_adjustment: EPA-based adjustment for away team (NFL only)
        calculation_version: Version of Elo algorithm used (default: "1.0")

    Returns:
        elo_log_id of the inserted record

    Example:
        >>> log_id = insert_elo_calculation_log(
        ...     league="nfl",
        ...     game_date=date(2024, 9, 8),
        ...     home_team_code="KC",
        ...     away_team_code="BAL",
        ...     home_score=27,
        ...     away_score=20,
        ...     home_elo_before=Decimal("1650"),
        ...     away_elo_before=Decimal("1620"),
        ...     k_factor=20,
        ...     home_advantage=Decimal("65"),
        ...     home_expected=Decimal("0.5714"),
        ...     away_expected=Decimal("0.4286"),
        ...     home_actual=Decimal("1.0"),
        ...     away_actual=Decimal("0.0"),
        ...     home_elo_change=Decimal("8.57"),
        ...     away_elo_change=Decimal("-8.57"),
        ...     home_elo_after=Decimal("1658.57"),
        ...     away_elo_after=Decimal("1611.43"),
        ...     calculation_source="realtime",
        ... )

    Educational Note:
        The Elo calculation log provides a complete audit trail:
        1. Pre-game state (both teams' ratings)
        2. Parameters used (K-factor, home advantage, MOV multiplier)
        3. Expected vs actual outcomes
        4. Post-game state (new ratings after adjustment)

        This allows debugging of rating discrepancies and analysis of
        the Elo system's predictive accuracy over time.

    References:
        - Migration 0013: elo_calculation_log table schema
        - ADR-109: Elo Rating Computation Engine Architecture
    """
    # Dual-write (#738 A1): populate league_id FK alongside the VARCHAR.
    league_id_value = get_league_id_or_none(league)
    query = """
        INSERT INTO elo_calculation_log (
            league, game_date, home_team_id, away_team_id,
            game_state_id, game_id,
            home_team_code, away_team_code,
            home_score, away_score,
            home_elo_before, away_elo_before,
            k_factor, home_advantage, mov_multiplier,
            home_expected, away_expected,
            home_actual, away_actual,
            home_elo_change, away_elo_change,
            home_elo_after, away_elo_after,
            home_epa_adjustment, away_epa_adjustment,
            calculation_source, calculation_version, league_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING elo_log_id
    """
    params = (
        league,
        game_date,
        home_team_id,
        away_team_id,
        game_state_id,
        game_id,
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
        home_epa_adjustment,
        away_epa_adjustment,
        calculation_source,
        calculation_version,
        league_id_value,
    )
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return cast("int", result["elo_log_id"])


def get_elo_calculation_logs(
    league: str,
    start_date: date | None = None,
    end_date: date | None = None,
    team_code: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Retrieve Elo calculation logs with optional filters.

    Args:
        league: League code to filter by (e.g., 'nfl', 'nba')
        start_date: Start of date range (optional)
        end_date: End of date range (optional)
        team_code: Filter by team (matches home or away)
        limit: Maximum records to return (default 100)

    Returns:
        List of Elo calculation log records

    Example:
        >>> logs = get_elo_calculation_logs(
        ...     league="nfl",
        ...     start_date=date(2024, 9, 1),
        ...     team_code="KC",
        ... )
        >>> for log in logs:
        ...     print(f"{log['game_date']}: {log['home_team_code']} vs {log['away_team_code']}")
    """
    conditions = ["league = %s"]
    params: list[Any] = [league]

    if start_date:
        conditions.append("game_date >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("game_date <= %s")
        params.append(end_date)

    if team_code:
        conditions.append("(home_team_code = %s OR away_team_code = %s)")
        params.extend([team_code, team_code])

    params.append(limit)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM elo_calculation_log
        WHERE {" AND ".join(conditions)}
        ORDER BY game_date DESC, created_at DESC
        LIMIT %s
    """  # noqa: S608

    return fetch_all(query, tuple(params))


# =============================================================================
# ALERT CRUD OPERATIONS
# =============================================================================
