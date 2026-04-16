"""CRUD operations for historical statistics and rankings.

Extracted from crud_operations.py during Phase 1c domain split.

Tables covered:
    - historical_stats: Season/game-level player and team statistics
    - historical_rankings: Point-in-time ranking records (AP, coaches, etc.)
"""

import json
import logging
from typing import Any, cast

from .connection import fetch_all, get_cursor
from .crud_lookups import get_sport_id_from_league_or_none

logger = logging.getLogger(__name__)


# =============================================================================
# HISTORICAL STATS CRUD OPERATIONS
# =============================================================================
# Functions for historical_stats table (Migration 0009)
# Used for storing player/team statistics from external data sources
# =============================================================================


def insert_historical_stat(
    sport: str,
    season: int,
    stat_category: str,
    stats: dict[str, Any],
    source: str,
    week: int | None = None,
    team_code: str | None = None,
    player_id: str | None = None,
    player_name: str | None = None,
    source_file: str | None = None,
) -> int:
    """
    Insert a single historical stat record with UPSERT semantics.

    Uses INSERT ... ON CONFLICT to handle re-imports idempotently. The unique
    constraint is on (sport, season, week, team_code, player_id, stat_category, source),
    allowing the same stat to be updated if re-imported from the same source.

    Args:
        sport: Sport code (nfl, ncaaf, nba, ncaab, nhl, mlb)
        season: Season year (e.g., 2024)
        stat_category: Category (passing, rushing, receiving, team_offense, etc.)
        stats: JSONB dictionary of stat fields (flexible schema per sport/category)
        source: Data source identifier (nfl_data_py, espn, pro_football_reference)
        week: Week number (None for seasonal aggregates)
        team_code: Team abbreviation (required for team stats)
        player_id: External player ID (required for player stats)
        player_name: Player display name (for player stats)
        source_file: Source filename for CSV-based imports

    Returns:
        historical_stat_id of created/updated record

    Raises:
        ValueError: If neither team_code nor player_id is provided

    Educational Note:
        Historical stats use JSONB for the stats field to support flexible schemas
        across different sports and categories. Unlike the live tables (game_states),
        these use VARCHAR team_code instead of INTEGER team_id FK, allowing data
        loading before team mappings exist. FK resolution is a separate step.

    Example:
        >>> stat_id = insert_historical_stat(
        ...     sport="nfl",
        ...     season=2024,
        ...     week=12,
        ...     team_code="KC",
        ...     stat_category="team_offense",
        ...     stats={"yards": 412, "points": 31, "turnovers": 1},
        ...     source="nfl_data_py"
        ... )

    References:
        - Migration 0009: historical_stats table
        - ADR-106: Historical Data Collection Architecture
        - REQ-DATA-005: Historical Statistics Storage
    """
    if not team_code and not player_id:
        raise ValueError("Either team_code or player_id must be provided")

    # Use a composite conflict target for upsert
    # This handles re-imports of the same data gracefully
    # Dual-write (#738 A1): historical_stats.sport holds league codes
    # ('nfl', 'ncaaf', ...) despite the column name.  Resolve via leagues
    # -> sports join.
    sport_id_value = get_sport_id_from_league_or_none(sport)
    query = """
        INSERT INTO historical_stats (
            sport, season, week, team_code, player_id, player_name,
            stat_category, stats, source, source_file, sport_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, COALESCE(week, -1), COALESCE(team_code, ''),
                     COALESCE(player_id, ''), stat_category, source)
        DO UPDATE SET
            player_name = EXCLUDED.player_name,
            stats = EXCLUDED.stats,
            source_file = EXCLUDED.source_file,
            sport_id = COALESCE(EXCLUDED.sport_id, historical_stats.sport_id)
        RETURNING historical_stat_id
    """
    with get_cursor(commit=True) as cur:
        # Convert dict to JSON string for psycopg2
        import json

        stats_json = json.dumps(stats)
        cur.execute(
            query,
            (
                sport,
                season,
                week,
                team_code,
                player_id,
                player_name,
                stat_category,
                stats_json,
                source,
                source_file,
                sport_id_value,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["historical_stat_id"])


def insert_historical_stats_batch(
    records: list[dict[str, Any]],
    batch_size: int = 1000,
) -> tuple[int, int]:
    """
    Batch insert historical stat records with progress tracking.

    Efficiently inserts multiple records using executemany with batching.
    Uses UPSERT semantics for idempotent re-imports.

    Args:
        records: List of stat record dictionaries with keys:
            - sport, season, week, team_code, player_id, player_name,
            - stat_category, stats, source, source_file
        batch_size: Number of records per batch (default 1000)

    Returns:
        Tuple of (inserted_count, updated_count)

    Educational Note:
        Batch inserts are significantly faster than individual inserts for large
        datasets (10x-100x improvement). The batch_size parameter balances memory
        usage against transaction overhead. 1000 records is a good default for
        most systems.

    Example:
        >>> records = [
        ...     {"sport": "nfl", "season": 2024, "week": 12, "team_code": "KC",
        ...      "stat_category": "team_offense", "stats": {"yards": 412},
        ...      "source": "nfl_data_py"},
        ...     {"sport": "nfl", "season": 2024, "week": 12, "team_code": "DEN",
        ...      "stat_category": "team_offense", "stats": {"yards": 289},
        ...      "source": "nfl_data_py"},
        ... ]
        >>> inserted, updated = insert_historical_stats_batch(records)
        >>> print(f"Inserted: {inserted}, Updated: {updated}")

    References:
        - Issue #253: CRUD operations for historical tables
        - ADR-106: Historical Data Collection Architecture
    """

    if not records:
        return (0, 0)

    # Dual-write (#738 A1): resolve sport_id from the league-code stored in
    # the `sport` column (historical_stats uses league codes, not sport names).
    query = """
        INSERT INTO historical_stats (
            sport, season, week, team_code, player_id, player_name,
            stat_category, stats, source, source_file, sport_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, COALESCE(week, -1), COALESCE(team_code, ''),
                     COALESCE(player_id, ''), stat_category, source)
        DO UPDATE SET
            player_name = EXCLUDED.player_name,
            stats = EXCLUDED.stats,
            source_file = EXCLUDED.source_file,
            sport_id = COALESCE(EXCLUDED.sport_id, historical_stats.sport_id)
    """
    total_inserted = 0

    with get_cursor(commit=True) as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            params = [
                (
                    r["sport"],
                    r["season"],
                    r.get("week"),
                    r.get("team_code"),
                    r.get("player_id"),
                    r.get("player_name"),
                    r["stat_category"],
                    json.dumps(r["stats"]),
                    r["source"],
                    r.get("source_file"),
                    get_sport_id_from_league_or_none(r["sport"]),
                )
                for r in batch
            ]
            cur.executemany(query, params)
            total_inserted += len(batch)

    # Note: PostgreSQL doesn't distinguish inserts vs updates in executemany
    # Return total as inserted, 0 as updated (conservative estimate)
    return (total_inserted, 0)


def get_historical_stats(
    sport: str,
    season: int,
    week: int | None = None,
    team_code: str | None = None,
    player_id: str | None = None,
    stat_category: str | None = None,
    source: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """
    Query historical stats with flexible filtering.

    Supports filtering by sport, season, week, team, player, category, and source.
    Returns stats ordered by season (desc), week (desc), team, player.

    Args:
        sport: Sport code (required)
        season: Season year (required)
        week: Filter by specific week (None for all weeks)
        team_code: Filter by team (None for all teams)
        player_id: Filter by player ID (None for all players)
        stat_category: Filter by category (None for all categories)
        source: Filter by data source (None for all sources)
        limit: Maximum records to return (default 1000)

    Returns:
        List of stat records with all fields including parsed stats JSONB

    Example:
        >>> # Get all KC offensive stats for week 12
        >>> stats = get_historical_stats(
        ...     sport="nfl", season=2024, week=12,
        ...     team_code="KC", stat_category="team_offense"
        ... )
        >>> for s in stats:
        ...     print(f"{s['stat_category']}: {s['stats']}")

    References:
        - Migration 0009: historical_stats table indexes
        - REQ-DATA-005: Historical Statistics Storage
    """
    conditions = ["sport = %s", "season = %s"]
    params: list[Any] = [sport, season]

    if week is not None:
        conditions.append("week = %s")
        params.append(week)

    if team_code:
        conditions.append("team_code = %s")
        params.append(team_code)

    if player_id:
        conditions.append("player_id = %s")
        params.append(player_id)

    if stat_category:
        conditions.append("stat_category = %s")
        params.append(stat_category)

    if source:
        conditions.append("source = %s")
        params.append(source)

    params.append(limit)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_stats
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, COALESCE(week, 0) DESC, team_code, player_id
        LIMIT %s
    """  # noqa: S608
    return fetch_all(query, tuple(params))


def get_player_stats(
    sport: str,
    player_id: str,
    season: int | None = None,
    stat_category: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get all stats for a specific player.

    Retrieves player statistics across seasons, weeks, and categories.
    Useful for player performance analysis and historical comparisons.

    Args:
        sport: Sport code (required)
        player_id: External player ID from source (required)
        season: Filter by season (None for all seasons)
        stat_category: Filter by category (None for all categories)

    Returns:
        List of stat records ordered by season (desc), week (desc)

    Example:
        >>> # Get all passing stats for Patrick Mahomes
        >>> stats = get_player_stats(
        ...     sport="nfl",
        ...     player_id="00-0033873",  # Mahomes NFL ID
        ...     stat_category="passing"
        ... )
        >>> for s in stats:
        ...     print(f"Season {s['season']} Week {s['week']}: {s['stats']}")

    References:
        - idx_historical_stats_player index
        - REQ-DATA-005: Historical Statistics Storage
    """
    conditions = ["sport = %s", "player_id = %s"]
    params: list[Any] = [sport, player_id]

    if season is not None:
        conditions.append("season = %s")
        params.append(season)

    if stat_category:
        conditions.append("stat_category = %s")
        params.append(stat_category)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_stats
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, COALESCE(week, 0) DESC
    """  # noqa: S608
    return fetch_all(query, tuple(params))


def get_team_stats(
    sport: str,
    team_code: str,
    season: int | None = None,
    stat_category: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get all stats for a specific team.

    Retrieves team statistics across seasons, weeks, and categories.
    Excludes individual player stats (player_id IS NULL).

    Args:
        sport: Sport code (required)
        team_code: Team abbreviation (required, e.g., "KC", "DAL")
        season: Filter by season (None for all seasons)
        stat_category: Filter by category (None for all categories)

    Returns:
        List of stat records ordered by season (desc), week (desc)

    Example:
        >>> # Get all Chiefs defensive stats for 2024
        >>> stats = get_team_stats(
        ...     sport="nfl",
        ...     team_code="KC",
        ...     season=2024,
        ...     stat_category="team_defense"
        ... )
        >>> for s in stats:
        ...     print(f"Week {s['week']}: {s['stats']}")

    References:
        - idx_historical_stats_team index
        - REQ-DATA-006: Team Statistics Aggregation
    """
    conditions = ["sport = %s", "team_code = %s", "player_id IS NULL"]
    params: list[Any] = [sport, team_code]

    if season is not None:
        conditions.append("season = %s")
        params.append(season)

    if stat_category:
        conditions.append("stat_category = %s")
        params.append(stat_category)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_stats
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, COALESCE(week, 0) DESC
    """  # noqa: S608
    return fetch_all(query, tuple(params))


# =============================================================================
# HISTORICAL RANKINGS CRUD OPERATIONS
# =============================================================================
# Functions for historical_rankings table (Migration 0009)
# Used for storing team rankings from various polls and rating systems
# =============================================================================


# =============================================================================
# HISTORICAL RANKINGS CRUD OPERATIONS
# =============================================================================
# Functions for historical_rankings table (Migration 0009)
# Used for storing team rankings from various polls and rating systems
# =============================================================================


def insert_historical_ranking(
    sport: str,
    season: int,
    week: int,
    team_code: str,
    rank: int,
    poll_type: str,
    source: str,
    previous_rank: int | None = None,
    points: int | None = None,
    first_place_votes: int | None = None,
    source_file: str | None = None,
) -> int:
    """
    Insert a single historical ranking record with UPSERT semantics.

    Uses INSERT ... ON CONFLICT based on the unique constraint
    (sport, season, week, team_code, poll_type) to handle re-imports.

    Args:
        sport: Sport code (nfl, ncaaf, nba, ncaab, nhl, mlb)
        season: Season year (e.g., 2024)
        week: Week number when ranking was released
        team_code: Team abbreviation (e.g., "KC", "ALA")
        rank: Ranking position (1 = best)
        poll_type: Type of poll (ap_poll, cfp, coaches, elo, power_ranking)
        source: Data source identifier (espn, fivethirtyeight, cfbd)
        previous_rank: Previous week's rank (None if unranked or first poll)
        points: Poll points received (for voting polls)
        first_place_votes: Number of first-place votes (for voting polls)
        source_file: Source filename for CSV-based imports

    Returns:
        historical_ranking_id of created/updated record

    Educational Note:
        Rankings differ from stats in that they have a natural unique constraint
        on (sport, season, week, team, poll_type). A team can only have one rank
        in a specific poll for a specific week. The UPSERT pattern allows safe
        re-imports without duplicates.

    Example:
        >>> ranking_id = insert_historical_ranking(
        ...     sport="ncaaf",
        ...     season=2024,
        ...     week=12,
        ...     team_code="UGA",
        ...     rank=1,
        ...     poll_type="ap_poll",
        ...     source="espn",
        ...     points=1525,
        ...     first_place_votes=45
        ... )

    References:
        - Migration 0009: historical_rankings table
        - uq_historical_rankings_team_poll_week unique constraint
        - ADR-106: Historical Data Collection Architecture
    """
    # Dual-write (#738 A1): resolve sport_id from the league-code stored in
    # `sport` (historical_rankings uses league codes).
    sport_id_value = get_sport_id_from_league_or_none(sport)
    query = """
        INSERT INTO historical_rankings (
            sport, season, week, team_code, rank, previous_rank,
            points, first_place_votes, poll_type, source, source_file, sport_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, week, team_code, poll_type)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            previous_rank = EXCLUDED.previous_rank,
            points = EXCLUDED.points,
            first_place_votes = EXCLUDED.first_place_votes,
            source = EXCLUDED.source,
            source_file = EXCLUDED.source_file,
            sport_id = COALESCE(EXCLUDED.sport_id, historical_rankings.sport_id)
        RETURNING historical_ranking_id
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            query,
            (
                sport,
                season,
                week,
                team_code,
                rank,
                previous_rank,
                points,
                first_place_votes,
                poll_type,
                source,
                source_file,
                sport_id_value,
            ),
        )
        result = cur.fetchone()
        return cast("int", result["historical_ranking_id"])


def insert_historical_rankings_batch(
    records: list[dict[str, Any]],
    batch_size: int = 1000,
) -> tuple[int, int]:
    """
    Batch insert historical ranking records with progress tracking.

    Efficiently inserts multiple records using executemany with batching.
    Uses UPSERT semantics for idempotent re-imports.

    Args:
        records: List of ranking record dictionaries with keys:
            - sport, season, week, team_code, rank, poll_type, source
            - Optional: previous_rank, points, first_place_votes, source_file
        batch_size: Number of records per batch (default 1000)

    Returns:
        Tuple of (inserted_count, updated_count)

    Example:
        >>> records = [
        ...     {"sport": "ncaaf", "season": 2024, "week": 12, "team_code": "UGA",
        ...      "rank": 1, "poll_type": "ap_poll", "source": "espn", "points": 1525},
        ...     {"sport": "ncaaf", "season": 2024, "week": 12, "team_code": "OSU",
        ...      "rank": 2, "poll_type": "ap_poll", "source": "espn", "points": 1489},
        ... ]
        >>> inserted, updated = insert_historical_rankings_batch(records)

    References:
        - Issue #253: CRUD operations for historical tables
        - ADR-106: Historical Data Collection Architecture
    """
    if not records:
        return (0, 0)

    # Dual-write (#738 A1): resolve sport_id for each record from its
    # league-code `sport` value.
    query = """
        INSERT INTO historical_rankings (
            sport, season, week, team_code, rank, previous_rank,
            points, first_place_votes, poll_type, source, source_file, sport_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sport, season, week, team_code, poll_type)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            previous_rank = EXCLUDED.previous_rank,
            points = EXCLUDED.points,
            first_place_votes = EXCLUDED.first_place_votes,
            source = EXCLUDED.source,
            source_file = EXCLUDED.source_file,
            sport_id = COALESCE(EXCLUDED.sport_id, historical_rankings.sport_id)
    """
    total_inserted = 0

    with get_cursor(commit=True) as cur:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            params = [
                (
                    r["sport"],
                    r["season"],
                    r["week"],
                    r["team_code"],
                    r["rank"],
                    r.get("previous_rank"),
                    r.get("points"),
                    r.get("first_place_votes"),
                    r["poll_type"],
                    r["source"],
                    r.get("source_file"),
                    get_sport_id_from_league_or_none(r["sport"]),
                )
                for r in batch
            ]
            cur.executemany(query, params)
            total_inserted += len(batch)

    return (total_inserted, 0)


def get_historical_rankings(
    sport: str,
    season: int,
    week: int | None = None,
    poll_type: str | None = None,
    team_code: str | None = None,
    top_n: int | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Query historical rankings with flexible filtering and pagination.

    Supports filtering by sport, season, week, poll type, team, and source.
    Can limit to top N teams (e.g., Top 25 AP Poll).

    Args:
        sport: Sport code (required)
        season: Season year (required)
        week: Filter by specific week (None for all weeks)
        poll_type: Filter by poll type (None for all poll types)
        team_code: Filter by team (None for all teams)
        top_n: Limit to top N ranked teams (e.g., 25 for AP Top 25)
        source: Filter by data source (None for all sources)
        limit: Maximum number of records to return (default: 100)
        offset: Number of records to skip for pagination (default: 0)

    Returns:
        List of ranking records ordered by week (desc), rank (asc)

    Example:
        >>> # Get AP Poll Top 25 for week 12
        >>> rankings = get_historical_rankings(
        ...     sport="ncaaf", season=2024, week=12,
        ...     poll_type="ap_poll", top_n=25
        ... )
        >>> # Pagination: get page 2 (records 100-199)
        >>> page2 = get_historical_rankings(sport="ncaaf", season=2024, limit=100, offset=100)

    References:
        - idx_historical_rankings_poll index
        - idx_historical_rankings_rank index
        - REQ-DATA-007: Historical Rankings Storage
    """
    conditions = ["sport = %s", "season = %s"]
    params: list[Any] = [sport, season]

    if week is not None:
        conditions.append("week = %s")
        params.append(week)

    if poll_type:
        conditions.append("poll_type = %s")
        params.append(poll_type)

    if team_code:
        conditions.append("team_code = %s")
        params.append(team_code)

    if top_n is not None:
        conditions.append("rank <= %s")
        params.append(top_n)

    if source:
        conditions.append("source = %s")
        params.append(source)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_rankings
        WHERE {" AND ".join(conditions)}
        ORDER BY week DESC, rank ASC
        LIMIT %s OFFSET %s
    """  # noqa: S608
    params.extend([limit, offset])
    return fetch_all(query, tuple(params))


def get_team_ranking_history(
    sport: str,
    team_code: str,
    poll_type: str,
    season: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get ranking history for a specific team in a specific poll.

    Retrieves how a team's ranking changed over time in a particular poll.
    Useful for tracking team performance and generating ranking charts.

    Args:
        sport: Sport code (required)
        team_code: Team abbreviation (required)
        poll_type: Type of poll (required, e.g., "ap_poll", "cfp")
        season: Filter by season (None for all seasons)

    Returns:
        List of ranking records ordered by season (desc), week (asc)

    Example:
        >>> # Get Georgia's AP Poll history for 2024
        >>> history = get_team_ranking_history(
        ...     sport="ncaaf",
        ...     team_code="UGA",
        ...     poll_type="ap_poll",
        ...     season=2024
        ... )
        >>> for r in history:
        ...     change = ""
        ...     if r['previous_rank']:
        ...         diff = r['previous_rank'] - r['rank']
        ...         change = f" (+{diff})" if diff > 0 else f" ({diff})" if diff < 0 else ""
        ...     print(f"Week {r['week']}: #{r['rank']}{change}")

    References:
        - idx_historical_rankings_team index
        - REQ-DATA-007: Historical Rankings Storage
    """
    conditions = ["sport = %s", "team_code = %s", "poll_type = %s"]
    params: list[Any] = [sport, team_code, poll_type]

    if season is not None:
        conditions.append("season = %s")
        params.append(season)

    # S608 false positive: conditions are hardcoded strings, not user input
    query = f"""
        SELECT *
        FROM historical_rankings
        WHERE {" AND ".join(conditions)}
        ORDER BY season DESC, week ASC
    """  # noqa: S608
    return fetch_all(query, tuple(params))


# =============================================================================
# Scheduler Status Operations (IPC via Database)
# =============================================================================
# These operations enable cross-process communication for scheduler status.
# The problem: `scheduler status` runs in a separate process from the scheduler
# itself, so it can't see in-memory state. Solution: store status in database.
#
# References:
#   - Migration 0012: scheduler_status table
#   - Issue #255: Scheduler status shows "not running" even when running
#   - ADR-TBD: Cross-Process IPC Strategy
# =============================================================================
