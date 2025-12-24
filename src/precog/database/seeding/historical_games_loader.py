"""
Historical Games Data Loader for Precog.

This module provides utilities for loading historical game results from
external data sources (FiveThirtyEight, Kaggle, CSV files) into the
historical_games table.

Data Sources:
    - FiveThirtyEight NFL/NBA/MLB: CSV with game-by-game results
    - Kaggle datasets: Various sports game data
    - Custom CSVs: Team, date, score format

Educational Notes:
------------------
FiveThirtyEight Data Format:
    The FiveThirtyEight Elo CSVs include game results alongside ratings:
    - date: Game date (YYYY-MM-DD)
    - season: Season year
    - team1, team2: Team abbreviations
    - score1, score2: Final scores
    - neutral: 1 if neutral site, 0 otherwise
    - playoff: 1 if playoff game, 0 otherwise

    We extract game results to populate historical_games table.

Team Code Mapping:
    FiveThirtyEight uses different team codes than our database.
    Uses the same TEAM_CODE_MAPPING from historical_elo_loader.

Reference:
    - Issue #229: Expanded Historical Data Sources
    - Issue #254: Add progress bars for large seeding operations
    - Migration 0006: Create historical_games table
    - ADR-029: ESPN Data Model
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, TypedDict

from precog.database.connection import get_cursor
from precog.database.seeding.batch_result import (
    BatchInsertResult,
    ErrorHandlingMode,
)
from precog.database.seeding.historical_elo_loader import (
    normalize_team_code,
)
from precog.database.seeding.progress import print_load_summary, seeding_progress

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class HistoricalGameRecord(TypedDict):
    """A single historical game record."""

    sport: str
    season: int
    game_date: date
    home_team_code: str
    away_team_code: str
    home_score: int | None
    away_score: int | None
    is_neutral_site: bool
    is_playoff: bool
    game_type: str | None
    venue_name: str | None
    source: str
    source_file: str | None
    external_game_id: str | None


# Type alias for backward compatibility (Issue #255)
# BatchInsertResult provides:
#   - total_records (aliased as records_processed)
#   - successful (aliased as records_inserted)
#   - skipped (aliased as records_skipped)
#   - failed (aliased as errors)
#   - error_messages property (compatibility)
#   - PLUS: failed_records list with FailedRecord details
LoadResult = BatchInsertResult


# =============================================================================
# FiveThirtyEight Loader
# =============================================================================


def parse_fivethirtyeight_games_csv(
    file_path: Path,
    sport: str = "nfl",
    seasons: list[int] | None = None,
) -> Iterator[HistoricalGameRecord]:
    """
    Parse FiveThirtyEight Elo CSV and yield historical game records.

    FiveThirtyEight format has one row per game with both teams and scores.
    By convention, team1 is home and team2 is away (unless neutral site).

    Args:
        file_path: Path to the CSV file
        sport: Sport code (default: "nfl")
        seasons: Filter to specific seasons (default: all)

    Yields:
        HistoricalGameRecord for each game

    Example:
        >>> records = list(parse_fivethirtyeight_games_csv(
        ...     Path("nfl_elo.csv"), seasons=[2023]
        ... ))
        >>> len(records)  # ~272 for a 17-week season
        272
    """
    source_file = file_path.name

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse season and check filter
            try:
                season = int(row.get("season", "0"))
            except ValueError:
                continue

            if seasons and season not in seasons:
                continue

            # Parse date
            try:
                date_str = row.get("date", "")
                game_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
            except ValueError:
                logger.warning("Invalid date in row: %s", row)
                continue

            # Extract team codes
            # FiveThirtyEight convention: team1 = home, team2 = away
            home_team_code = normalize_team_code(row.get("team1", ""))
            away_team_code = normalize_team_code(row.get("team2", ""))

            if not home_team_code or not away_team_code:
                logger.warning("Missing team codes in row: %s", row)
                continue

            # Parse scores
            try:
                score1 = row.get("score1", "")
                score2 = row.get("score2", "")
                home_score = int(score1) if score1 else None
                away_score = int(score2) if score2 else None
            except ValueError:
                home_score = None
                away_score = None

            # Parse game context
            neutral_str = row.get("neutral", "0")
            playoff_str = row.get("playoff", "0")
            is_neutral_site = neutral_str == "1"
            is_playoff = playoff_str == "1"

            # Determine game type
            game_type = "playoff" if is_playoff else "regular"

            yield HistoricalGameRecord(
                sport=sport,
                season=season,
                game_date=game_date,
                home_team_code=home_team_code,
                away_team_code=away_team_code,
                home_score=home_score,
                away_score=away_score,
                is_neutral_site=is_neutral_site,
                is_playoff=is_playoff,
                game_type=game_type,
                venue_name=None,
                source="fivethirtyeight",
                source_file=source_file,
                external_game_id=None,
            )


def parse_simple_games_csv(
    file_path: Path,
    sport: str,
    source: str = "imported",
) -> Iterator[HistoricalGameRecord]:
    """
    Parse a simple CSV with game data.

    Expected columns:
        - game_date: Game date (YYYY-MM-DD)
        - season: Season year
        - home_team_code: Home team abbreviation
        - away_team_code: Away team abbreviation
        - home_score: Home team final score
        - away_score: Away team final score

    Optional columns:
        - is_neutral_site: 1 or 0
        - is_playoff: 1 or 0
        - game_type: regular, playoff, bowl, etc.
        - venue_name: Venue name
        - external_game_id: External ID

    Args:
        file_path: Path to CSV file
        sport: Sport code (e.g., "nfl")
        source: Data source identifier

    Yields:
        HistoricalGameRecord for each row
    """
    source_file = file_path.name

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                date_str = row.get("game_date", row.get("date", ""))
                game_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
                season = int(row.get("season", "0"))

                home_team_code = normalize_team_code(row.get("home_team_code", ""))
                away_team_code = normalize_team_code(row.get("away_team_code", ""))

                home_score_str = row.get("home_score", "")
                away_score_str = row.get("away_score", "")
                home_score = int(home_score_str) if home_score_str else None
                away_score = int(away_score_str) if away_score_str else None

                yield HistoricalGameRecord(
                    sport=sport,
                    season=season,
                    game_date=game_date,
                    home_team_code=home_team_code,
                    away_team_code=away_team_code,
                    home_score=home_score,
                    away_score=away_score,
                    is_neutral_site=row.get("is_neutral_site", "0") == "1",
                    is_playoff=row.get("is_playoff", "0") == "1",
                    game_type=row.get("game_type") or None,
                    venue_name=row.get("venue_name") or None,
                    source=source,
                    source_file=source_file,
                    external_game_id=row.get("external_game_id") or None,
                )
            except (ValueError, TypeError, KeyError) as e:
                logger.warning("Error parsing row: %s - %s", row, e)


# =============================================================================
# Database Operations
# =============================================================================


def get_team_id_by_code(team_code: str, sport: str) -> int | None:
    """
    Look up team_id from team_code and sport.

    Args:
        team_code: Team abbreviation (e.g., "KC")
        sport: Sport code (e.g., "nfl")

    Returns:
        team_id if found, None otherwise
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT team_id FROM teams
            WHERE team_code = %s AND sport = %s
            """,
            (team_code, sport),
        )
        row = cursor.fetchone()
        if row:
            return int(row["team_id"])
    return None


def bulk_insert_historical_games(
    records: Iterator[HistoricalGameRecord],
    batch_size: int = 1000,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
    *,
    total: int | None = None,
    show_progress: bool = True,
) -> BatchInsertResult:
    """
    Bulk insert historical game records with batching, progress display, and error handling.

    Args:
        records: Iterator of HistoricalGameRecord
        batch_size: Number of records per batch (default: 1000)
        error_mode: How to handle errors (default: FAIL - stop on first error)
            - FAIL: Raise exception on first unknown team
            - SKIP: Skip records with unknown teams, continue processing
            - COLLECT: Collect all failures, continue processing
        total: Expected total records (enables determinate progress bar)
        show_progress: Whether to show progress bar (auto-disabled in CI)

    Returns:
        BatchInsertResult with statistics and any failed records

    Raises:
        ValueError: When error_mode is FAIL and both teams are unknown

    Example:
        >>> # Collect all failures for diagnostics
        >>> result = bulk_insert_historical_games(
        ...     records,
        ...     error_mode=ErrorHandlingMode.COLLECT,
        ...     show_progress=True,
        ... )
        >>> if result.has_failures:
        ...     print(result.get_failure_summary())
    """
    result = BatchInsertResult(error_mode=error_mode, operation="bulk_insert_historical_games")

    batch: list[tuple[Any, ...]] = []
    team_id_cache: dict[tuple[str, str], int | None] = {}

    with seeding_progress(
        "Loading game results...",
        total=total,
        show_progress=show_progress,
    ) as (progress, task):
        for record_index, record in enumerate(records):
            result.total_records += 1

            # Look up team_ids (with caching)
            home_cache_key = (record["home_team_code"], record["sport"])
            away_cache_key = (record["away_team_code"], record["sport"])

            if home_cache_key not in team_id_cache:
                team_id_cache[home_cache_key] = get_team_id_by_code(
                    record["home_team_code"],
                    record["sport"],
                )

            if away_cache_key not in team_id_cache:
                team_id_cache[away_cache_key] = get_team_id_by_code(
                    record["away_team_code"],
                    record["sport"],
                )

            home_team_id = team_id_cache[home_cache_key]
            away_team_id = team_id_cache[away_cache_key]

            # Handle case where BOTH teams not found (allows for defunct teams)
            if not home_team_id and not away_team_id:
                error = ValueError(
                    f"Both teams unknown: home={record['home_team_code']}, "
                    f"away={record['away_team_code']} for sport={record['sport']}"
                )
                if error_mode == ErrorHandlingMode.FAIL:
                    result.add_failure(record_index, dict(record), error)
                    raise error
                if error_mode == ErrorHandlingMode.SKIP:
                    result.add_skip()
                elif error_mode == ErrorHandlingMode.COLLECT:
                    result.add_failure(record_index, dict(record), error)
                if progress and task is not None:
                    progress.advance(task)
                continue

            batch.append(
                (
                    record["sport"],
                    record["season"],
                    record["game_date"],
                    record["home_team_code"],
                    record["away_team_code"],
                    home_team_id,
                    away_team_id,
                    record["home_score"],
                    record["away_score"],
                    record["is_neutral_site"],
                    record["is_playoff"],
                    record["game_type"],
                    record["venue_name"],
                    record["source"],
                    record["source_file"],
                    record["external_game_id"],
                )
            )

            # Update progress
            if progress and task is not None:
                progress.advance(task)

            # Flush batch when full
            if len(batch) >= batch_size:
                inserted = _flush_games_batch(batch)
                result.successful += inserted
                batch = []

    # Flush remaining records
    if batch:
        inserted = _flush_games_batch(batch)
        result.successful += inserted

    return result


def _flush_games_batch(batch: list[tuple[Any, ...]]) -> int:
    """
    Insert a batch of game records using execute_values.

    Args:
        batch: List of tuples to insert

    Returns:
        Number of records inserted/updated
    """
    if not batch:
        return 0

    with get_cursor(commit=True) as cursor:
        from psycopg2.extras import execute_values

        query = """
            INSERT INTO historical_games (
                sport, season, game_date, home_team_code, away_team_code,
                home_team_id, away_team_id, home_score, away_score,
                is_neutral_site, is_playoff, game_type, venue_name,
                source, source_file, external_game_id
            ) VALUES %s
            ON CONFLICT (sport, game_date, home_team_code, away_team_code) DO UPDATE SET
                home_team_id = EXCLUDED.home_team_id,
                away_team_id = EXCLUDED.away_team_id,
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                is_neutral_site = EXCLUDED.is_neutral_site,
                is_playoff = EXCLUDED.is_playoff,
                game_type = EXCLUDED.game_type,
                venue_name = EXCLUDED.venue_name,
                source = EXCLUDED.source,
                source_file = EXCLUDED.source_file,
                external_game_id = EXCLUDED.external_game_id
        """
        execute_values(cursor, query, batch)
        return len(batch)


# =============================================================================
# Main Entry Points
# =============================================================================


def load_fivethirtyeight_games(
    file_path: Path,
    sport: str = "nfl",
    seasons: list[int] | None = None,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
    *,
    show_progress: bool = True,
) -> BatchInsertResult:
    """
    Load FiveThirtyEight game data into the database.

    Args:
        file_path: Path to FiveThirtyEight CSV file
        sport: Sport code (default: "nfl")
        seasons: Filter to specific seasons (default: all)
        error_mode: How to handle errors (default: FAIL - stop on first error)
            - FAIL: Raise exception on first unknown team
            - SKIP: Skip records with unknown teams, continue processing
            - COLLECT: Collect all failures, continue processing
        show_progress: Whether to show progress bar (auto-disabled in CI)

    Returns:
        BatchInsertResult with statistics

    Example:
        >>> result = load_fivethirtyeight_games(
        ...     Path("nfl_elo.csv"),
        ...     seasons=[2022, 2023],
        ...     show_progress=True,
        ... )
        >>> print(f"Loaded {result.records_inserted} games")
        >>> # With error collection
        >>> result = load_fivethirtyeight_games(
        ...     Path("nfl_elo.csv"),
        ...     error_mode=ErrorHandlingMode.COLLECT
        ... )
        >>> if result.has_failures:
        ...     print(result.get_failure_summary())
    """
    logger.info("Loading FiveThirtyEight game data from %s", file_path)

    records = parse_fivethirtyeight_games_csv(file_path, sport, seasons)
    result = bulk_insert_historical_games(
        records, error_mode=error_mode, show_progress=show_progress
    )

    logger.info(
        "FiveThirtyEight games load complete: processed=%d, inserted=%d, skipped=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
    )

    # Print summary table
    print_load_summary(
        "FiveThirtyEight Games Load",
        processed=result.records_processed,
        inserted=result.records_inserted,
        skipped=result.records_skipped,
        errors=result.errors,
        show_summary=show_progress,
    )

    return result


def load_csv_games(
    file_path: Path,
    sport: str,
    source: str = "imported",
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
    *,
    show_progress: bool = True,
) -> BatchInsertResult:
    """
    Load game data from a simple CSV file.

    Args:
        file_path: Path to CSV file
        sport: Sport code
        source: Data source identifier
        error_mode: How to handle errors (default: FAIL - stop on first error)
        show_progress: Whether to show progress bar (auto-disabled in CI)

    Returns:
        BatchInsertResult with statistics
    """
    logger.info("Loading game data from %s", file_path)

    records = parse_simple_games_csv(file_path, sport, source)
    result = bulk_insert_historical_games(
        records, error_mode=error_mode, show_progress=show_progress
    )

    logger.info(
        "CSV games load complete: processed=%d, inserted=%d, skipped=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
    )

    # Print summary table
    print_load_summary(
        f"CSV Games Load ({source})",
        processed=result.records_processed,
        inserted=result.records_inserted,
        skipped=result.records_skipped,
        errors=result.errors,
        show_summary=show_progress,
    )

    return result


def get_historical_games_stats() -> dict[str, Any]:
    """
    Get statistics about historical game data in the database.

    Returns:
        Dictionary with counts by sport, season, source
    """
    with get_cursor() as cursor:
        # Count by sport
        cursor.execute("""
            SELECT sport, COUNT(*) as count
            FROM historical_games
            GROUP BY sport
            ORDER BY sport
        """)
        by_sport = {row["sport"]: row["count"] for row in cursor.fetchall()}

        # Count by season (last 10)
        cursor.execute("""
            SELECT season, COUNT(*) as count
            FROM historical_games
            GROUP BY season
            ORDER BY season DESC
            LIMIT 10
        """)
        by_season = {row["season"]: row["count"] for row in cursor.fetchall()}

        # Count by source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM historical_games
            GROUP BY source
            ORDER BY count DESC
        """)
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM historical_games")
        total = cursor.fetchone()["total"]

    return {
        "total": total,
        "by_sport": by_sport,
        "by_season": by_season,
        "by_source": by_source,
    }
