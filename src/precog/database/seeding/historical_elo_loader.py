"""
Historical Elo Data Loader for Precog.

This module provides utilities for loading historical Elo ratings from
external data sources (FiveThirtyEight, Kaggle, CSV files) into the
historical_elo table.

Data Sources:
    - FiveThirtyEight NFL Elo (1920-present): CSV with game-by-game ratings
    - Kaggle datasets: Various sports Elo calculations
    - Custom CSVs: Team, date, rating format

Educational Notes:
------------------
FiveThirtyEight Data Format:
    The FiveThirtyEight NFL Elo CSV contains game-by-game data:
    - date: Game date (YYYY-MM-DD)
    - season: Season year
    - team1, team2: Team abbreviations
    - elo1_pre, elo2_pre: Pre-game Elo ratings
    - elo1_post, elo2_post: Post-game Elo ratings
    - qbelo1_pre, qbelo2_pre: QB-adjusted ratings (NFL-specific)

    We extract pre-game ratings to populate historical_elo table.

Team Code Mapping:
    FiveThirtyEight uses different team codes than our database:
    - 538: "KC" vs DB: "KC" (match)
    - 538: "LAR" vs DB: "LAR" (match)
    - 538: "WSH" vs DB: "WAS" (needs mapping)

    The TEAM_CODE_MAPPING dict handles these translations.

Error Handling Modes (Issue #255):
    - FAIL: Stop on first error (default, current behavior)
    - SKIP: Skip failed records, continue processing
    - COLLECT: Process all records, return detailed failure list

Reference:
    - Issue #208: Historical Data Seeding
    - Issue #255: Batch Insert Error Handling
    - Migration 030: Create historical_elo table
    - ADR-029: ESPN Data Model
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict

from precog.database.connection import get_cursor
from precog.database.seeding.batch_result import (
    BatchInsertResult,
    ErrorHandlingMode,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class HistoricalEloRecord(TypedDict):
    """A single historical Elo rating record."""

    team_code: str
    sport: str
    season: int
    rating_date: date
    elo_rating: Decimal
    qb_adjusted_elo: Decimal | None
    qb_name: str | None
    qb_value: Decimal | None
    source: str
    source_file: str | None


# LoadResult is now an alias for BatchInsertResult for backward compatibility.
# BatchInsertResult has compatibility properties (records_processed, records_inserted, etc.)
# that make it work with code expecting LoadResult field names.
# See Issue #255 for migration details.
LoadResult = BatchInsertResult


# =============================================================================
# Team Code Mapping - Unified Module
# =============================================================================

# Team history imported at top of file (Issue #257)
# See precog.database.seeding.team_history for comprehensive multi-sport tracking


def normalize_team_code(code: str, sport: str = "nfl") -> str:
    """
    Normalize a team code from external source to database format.

    This function wraps the unified team history module's resolve_team_code()
    for backward compatibility with existing code.

    Args:
        code: Team code from external source (e.g., FiveThirtyEight)
        sport: Sport code (default: "nfl" for FiveThirtyEight NFL data)

    Returns:
        Normalized team code for database lookup

    Example:
        >>> normalize_team_code("WSH")
        'WAS'
        >>> normalize_team_code("KC")
        'KC'
        >>> normalize_team_code("OAK")
        'LV'

    Note:
        Uses the unified team history module (Issue #257) which provides
        comprehensive tracking of all major sports team relocations.
    """
    return resolve_team_code(sport, code)


# =============================================================================
# FiveThirtyEight Loader
# =============================================================================


def parse_fivethirtyeight_csv(
    file_path: Path,
    sport: str = "nfl",
    seasons: list[int] | None = None,
) -> Iterator[HistoricalEloRecord]:
    """
    Parse FiveThirtyEight Elo CSV and yield historical Elo records.

    FiveThirtyEight format has one row per game, with both teams' ratings.
    This function extracts pre-game ratings for each team.

    Supports two column formats:
    - Full format: elo1_pre, qbelo1_pre, qb1, qb1_value_pre (original 538 API)
    - Simple format: elo1 (nfl-elo-game repo, no QB data)

    Args:
        file_path: Path to the CSV file
        sport: Sport code (default: "nfl")
        seasons: Filter to specific seasons (default: all)

    Yields:
        HistoricalEloRecord for each team in each game

    Example:
        >>> records = list(parse_fivethirtyeight_csv(Path("nfl_elo.csv"), seasons=[2023]))
        >>> len(records)  # ~544 for a 17-week season (32 teams * 17 games / 2)
        544
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

            # Parse date (date-only string, not datetime with timezone)
            try:
                date_str = row.get("date", "")
                rating_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
            except ValueError:
                logger.warning("Invalid date in row: %s", row)
                continue

            # Extract team 1 data (support both "elo1_pre" and "elo1" column names)
            team1_code = normalize_team_code(row.get("team1", ""))
            elo1_pre = row.get("elo1_pre") or row.get("elo1", "")
            qbelo1_pre = row.get("qbelo1_pre", "")
            qb1 = row.get("qb1", "")
            qb1_value = row.get("qb1_value_pre", "")

            if team1_code and elo1_pre:
                try:
                    yield HistoricalEloRecord(
                        team_code=team1_code,
                        sport=sport,
                        season=season,
                        rating_date=rating_date,
                        elo_rating=Decimal(elo1_pre),
                        qb_adjusted_elo=Decimal(qbelo1_pre) if qbelo1_pre else None,
                        qb_name=qb1 if qb1 else None,
                        qb_value=Decimal(qb1_value) if qb1_value else None,
                        source="fivethirtyeight",
                        source_file=source_file,
                    )
                except (ValueError, TypeError) as e:
                    logger.warning("Error parsing team1 data: %s - %s", row, e)

            # Extract team 2 data (support both "elo2_pre" and "elo2" column names)
            team2_code = normalize_team_code(row.get("team2", ""))
            elo2_pre = row.get("elo2_pre") or row.get("elo2", "")
            qbelo2_pre = row.get("qbelo2_pre", "")
            qb2 = row.get("qb2", "")
            qb2_value = row.get("qb2_value_pre", "")

            if team2_code and elo2_pre:
                try:
                    yield HistoricalEloRecord(
                        team_code=team2_code,
                        sport=sport,
                        season=season,
                        rating_date=rating_date,
                        elo_rating=Decimal(elo2_pre),
                        qb_adjusted_elo=Decimal(qbelo2_pre) if qbelo2_pre else None,
                        qb_name=qb2 if qb2 else None,
                        qb_value=Decimal(qb2_value) if qb2_value else None,
                        source="fivethirtyeight",
                        source_file=source_file,
                    )
                except (ValueError, TypeError) as e:
                    logger.warning("Error parsing team2 data: %s - %s", row, e)


def parse_simple_csv(
    file_path: Path,
    sport: str,
    source: str = "imported",
) -> Iterator[HistoricalEloRecord]:
    """
    Parse a simple CSV with team, date, rating columns.

    Expected columns:
        - team_code: Team abbreviation (e.g., "KC")
        - date: Rating date (YYYY-MM-DD)
        - season: Season year
        - elo_rating: Elo rating value

    Optional columns:
        - qb_adjusted_elo: QB-adjusted rating
        - qb_name: Quarterback name
        - qb_value: QB value adjustment

    Args:
        file_path: Path to CSV file
        sport: Sport code (e.g., "nfl")
        source: Data source identifier

    Yields:
        HistoricalEloRecord for each row
    """
    source_file = file_path.name

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                team_code = normalize_team_code(row.get("team_code", ""))
                season = int(row.get("season", "0"))
                date_str = row.get("date", "")
                rating_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
                elo_rating = Decimal(row.get("elo_rating", "0"))

                yield HistoricalEloRecord(
                    team_code=team_code,
                    sport=sport,
                    season=season,
                    rating_date=rating_date,
                    elo_rating=elo_rating,
                    qb_adjusted_elo=Decimal(row["qb_adjusted_elo"])
                    if row.get("qb_adjusted_elo")
                    else None,
                    qb_name=row.get("qb_name") or None,
                    qb_value=Decimal(row["qb_value"]) if row.get("qb_value") else None,
                    source=source,
                    source_file=source_file,
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


def insert_historical_elo(record: HistoricalEloRecord) -> bool:
    """
    Insert or update a single historical Elo record.

    Uses ON CONFLICT to handle duplicates (same team, same date).

    Args:
        record: HistoricalEloRecord to insert

    Returns:
        True if successful, False otherwise
    """
    # Look up team_id
    team_id = get_team_id_by_code(record["team_code"], record["sport"])
    if not team_id:
        logger.warning(
            "Team not found: %s (%s)",
            record["team_code"],
            record["sport"],
        )
        return False

    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO historical_elo (
                team_id, sport, season, rating_date, elo_rating,
                qb_adjusted_elo, qb_name, qb_value, source, source_file
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (team_id, rating_date) DO UPDATE SET
                elo_rating = EXCLUDED.elo_rating,
                qb_adjusted_elo = EXCLUDED.qb_adjusted_elo,
                qb_name = EXCLUDED.qb_name,
                qb_value = EXCLUDED.qb_value,
                source = EXCLUDED.source,
                source_file = EXCLUDED.source_file
            """,
            (
                team_id,
                record["sport"],
                record["season"],
                record["rating_date"],
                record["elo_rating"],
                record["qb_adjusted_elo"],
                record["qb_name"],
                record["qb_value"],
                record["source"],
                record["source_file"],
            ),
        )
        return True


def bulk_insert_historical_elo(
    records: Iterator[HistoricalEloRecord],
    batch_size: int = 1000,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
) -> BatchInsertResult:
    """
    Bulk insert historical Elo records with batching and configurable error handling.

    Args:
        records: Iterator of HistoricalEloRecord
        batch_size: Number of records per batch (default: 1000)
        error_mode: How to handle errors (default: FAIL)
            - FAIL: Stop on first error, raise exception
            - SKIP: Skip failed records, continue processing
            - COLLECT: Process all records, collect failures for analysis

    Returns:
        BatchInsertResult with statistics and failure details

    Educational Note:
        The error_mode parameter (Issue #255) allows flexible error handling:
        - Use FAIL for transactional integrity (all-or-nothing)
        - Use SKIP for "best effort" imports
        - Use COLLECT for data quality analysis (see ALL failures)

    Example:
        >>> result = bulk_insert_historical_elo(
        ...     records,
        ...     error_mode=ErrorHandlingMode.COLLECT,
        ... )
        >>> if result.has_failures:
        ...     print(result.get_failure_summary())
    """
    start_time = time.perf_counter()
    result = BatchInsertResult(
        operation="Historical Elo Insert",
        error_mode=error_mode,
    )

    batch: list[tuple[Any, ...]] = []
    # Track record index to original record for failure reporting
    batch_indices: list[int] = []
    batch_records: list[dict[str, Any]] = []

    team_id_cache: dict[tuple[str, str], int | None] = {}

    for record in records:
        record_index = result.total_records
        result.total_records += 1

            # Look up team_id (with caching)
            cache_key = (record["team_code"], record["sport"])
            if cache_key not in team_id_cache:
                team_id_cache[cache_key] = get_team_id_by_code(
                    record["team_code"],
                    record["sport"],
                )

            team_id = team_id_cache[cache_key]
            if not team_id:
                result.records_skipped += 1
                if progress and task is not None:
                    progress.advance(task)
                continue

            batch.append(
                (
                    team_id,
                    record["sport"],
                    record["season"],
                    record["rating_date"],
                    record["elo_rating"],
                    record["qb_adjusted_elo"],
                    record["qb_name"],
                    record["qb_value"],
                    record["source"],
                    record["source_file"],
                )
            )

        team_id = team_id_cache[cache_key]
        if not team_id:
            # Team not found - handle according to error_mode
            if error_mode == ErrorHandlingMode.COLLECT:
                result.add_failure(
                    record_index=record_index,
                    record_data=dict(record),
                    error=ValueError(f"Team not found: {record['team_code']} ({record['sport']})"),
                    context="team_lookup",
                )
            elif error_mode == ErrorHandlingMode.SKIP:
                result.add_skip()
            else:  # FAIL mode
                result.elapsed_time = time.perf_counter() - start_time
                msg = f"Team not found: {record['team_code']} ({record['sport']})"
                raise ValueError(msg)
            continue

        batch.append(
            (
                team_id,
                record["sport"],
                record["season"],
                record["rating_date"],
                record["elo_rating"],
                record["qb_adjusted_elo"],
                record["qb_name"],
                record["qb_value"],
                record["source"],
                record["source_file"],
            )
        )
        batch_indices.append(record_index)
        batch_records.append(dict(record))

        # Flush batch when full
        if len(batch) >= batch_size:
            inserted = _flush_batch(batch)
            result.successful += inserted
            batch = []
            batch_indices = []
            batch_records = []

    # Flush remaining records
    if batch:
        inserted = _flush_batch(batch)
        result.successful += inserted

    result.elapsed_time = time.perf_counter() - start_time
    return result


def _flush_batch(batch: list[tuple[Any, ...]]) -> int:
    """
    Insert a batch of records using executemany.

    Args:
        batch: List of tuples to insert

    Returns:
        Number of records inserted/updated
    """
    if not batch:
        return 0

    with get_cursor(commit=True) as cursor:
        # Use execute_values for better performance with psycopg2
        # Note: This uses ON CONFLICT for upsert behavior
        from psycopg2.extras import execute_values

        query = """
            INSERT INTO historical_elo (
                team_id, sport, season, rating_date, elo_rating,
                qb_adjusted_elo, qb_name, qb_value, source, source_file
            ) VALUES %s
            ON CONFLICT (team_id, rating_date) DO UPDATE SET
                elo_rating = EXCLUDED.elo_rating,
                qb_adjusted_elo = EXCLUDED.qb_adjusted_elo,
                qb_name = EXCLUDED.qb_name,
                qb_value = EXCLUDED.qb_value,
                source = EXCLUDED.source,
                source_file = EXCLUDED.source_file
        """
        execute_values(cursor, query, batch)
        return len(batch)


# =============================================================================
# Main Entry Points
# =============================================================================


def load_fivethirtyeight_elo(
    file_path: Path,
    sport: str = "nfl",
    seasons: list[int] | None = None,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
) -> BatchInsertResult:
    """
    Load FiveThirtyEight Elo data into the database.

    Args:
        file_path: Path to FiveThirtyEight CSV file
        sport: Sport code (default: "nfl")
        seasons: Filter to specific seasons (default: all)
        error_mode: How to handle errors (default: FAIL)
            - FAIL: Stop on first error, raise exception
            - SKIP: Skip failed records, continue processing
            - COLLECT: Process all records, collect failures for analysis

    Returns:
        BatchInsertResult with statistics and failure details

    Example:
        >>> result = load_fivethirtyeight_elo(
        ...     Path("nfl_elo.csv"),
        ...     seasons=[2022, 2023, 2024],
        ...     show_progress=True,
        ... )
        >>> print(f"Loaded {result.records_inserted} records")
        >>>
        >>> # With error collection for data quality analysis
        >>> result = load_fivethirtyeight_elo(
        ...     Path("nfl_elo.csv"),
        ...     error_mode=ErrorHandlingMode.COLLECT
        ... )
        >>> if result.has_failures:
        ...     print(result.get_failure_summary())
    """
    logger.info("Loading FiveThirtyEight Elo data from %s", file_path)

    records = parse_fivethirtyeight_csv(file_path, sport, seasons)
    result = bulk_insert_historical_elo(records, error_mode=error_mode)

    logger.info(
        "FiveThirtyEight load complete: processed=%d, inserted=%d, skipped=%d, failed=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
        result.failed,
    )

    # Print summary table
    print_load_summary(
        "FiveThirtyEight Elo Load",
        processed=result.records_processed,
        inserted=result.records_inserted,
        skipped=result.records_skipped,
        errors=result.errors,
        show_summary=show_progress,
    )

    return result


def load_csv_elo(
    file_path: Path,
    sport: str,
    source: str = "imported",
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
) -> BatchInsertResult:
    """
    Load Elo data from a simple CSV file.

    Args:
        file_path: Path to CSV file
        sport: Sport code
        source: Data source identifier
        error_mode: How to handle errors (default: FAIL)

    Returns:
        BatchInsertResult with statistics and failure details
    """
    logger.info("Loading Elo data from %s", file_path)

    records = parse_simple_csv(file_path, sport, source)
    result = bulk_insert_historical_elo(records, error_mode=error_mode)

    logger.info(
        "CSV load complete: processed=%d, inserted=%d, skipped=%d, failed=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
        result.failed,
    )

    # Print summary table
    print_load_summary(
        f"CSV Elo Load ({source})",
        processed=result.records_processed,
        inserted=result.records_inserted,
        skipped=result.records_skipped,
        errors=result.errors,
        show_summary=show_progress,
    )

    return result


def get_historical_elo_stats() -> dict[str, Any]:
    """
    Get statistics about historical Elo data in the database.

    Returns:
        Dictionary with counts by sport, season, source
    """
    with get_cursor() as cursor:
        # Count by sport
        cursor.execute("""
            SELECT sport, COUNT(*) as count
            FROM historical_elo
            GROUP BY sport
            ORDER BY sport
        """)
        by_sport = {row["sport"]: row["count"] for row in cursor.fetchall()}

        # Count by season
        cursor.execute("""
            SELECT season, COUNT(*) as count
            FROM historical_elo
            GROUP BY season
            ORDER BY season DESC
            LIMIT 10
        """)
        by_season = {row["season"]: row["count"] for row in cursor.fetchall()}

        # Count by source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM historical_elo
            GROUP BY source
            ORDER BY count DESC
        """)
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM historical_elo")
        total = cursor.fetchone()["total"]

    return {
        "total": total,
        "by_sport": by_sport,
        "by_season": by_season,
        "by_source": by_source,
    }
