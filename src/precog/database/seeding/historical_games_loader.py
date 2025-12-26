"""
Historical Games Data Loader for Precog.

This module provides utilities for loading historical game results from
external data sources (FiveThirtyEight, ESPN API, Kaggle, CSV files) into the
historical_games table.

Data Sources:
    - FiveThirtyEight NFL/NBA/MLB: CSV with game-by-game results
    - ESPN API: Live and historical game data with local caching
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
import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
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


def parse_fivethirtyeight_nba_csv(
    file_path: Path,
    seasons: list[int] | None = None,
) -> Iterator[HistoricalGameRecord]:
    """
    Parse FiveThirtyEight NBA Elo CSV (nbaallelo.csv format).

    This format differs from the NFL format:
    - Each game appears twice (once per team, with _iscopy flag)
    - Uses different column names: year_id, date_game, team_id, opp_id
    - Date format is M/D/YYYY instead of YYYY-MM-DD
    - game_location indicates H=home, A=away, N=neutral

    Educational Note:
        FiveThirtyEight NBA data uses a different structure than NFL data.
        We filter by _iscopy=0 to get one row per game, then determine
        home/away based on game_location. This prevents duplicate records.

    Args:
        file_path: Path to the nbaallelo.csv file
        seasons: Filter to specific seasons (default: all)

    Yields:
        HistoricalGameRecord for each game

    Example:
        >>> records = list(parse_fivethirtyeight_nba_csv(
        ...     Path("nbaallelo.csv"), seasons=[2020, 2021, 2022]
        ... ))
        >>> len(records)  # ~1230 games per season
        3690
    """
    source_file = file_path.name

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Skip copy rows (each game appears twice)
            if row.get("_iscopy", "0") == "1":
                continue

            # Parse season (year_id in NBA format)
            try:
                season = int(row.get("year_id", "0"))
            except ValueError:
                continue

            if seasons and season not in seasons:
                continue

            # Parse date (M/D/YYYY format in NBA data)
            try:
                date_str = row.get("date_game", "")
                game_date = datetime.strptime(date_str, "%m/%d/%Y").date()  # noqa: DTZ007
            except ValueError:
                logger.warning("Invalid date in NBA row: %s", row)
                continue

            # Extract team codes and determine home/away based on game_location
            # CRITICAL: Pass sport="nba" to avoid cross-sport code collisions
            # (e.g., PHO = Phoenix Cardinals in NFL, but Phoenix Suns in NBA)
            game_location = row.get("game_location", "H")
            team_code = normalize_team_code(row.get("team_id", ""), sport="nba")
            opp_code = normalize_team_code(row.get("opp_id", ""), sport="nba")

            if not team_code or not opp_code:
                logger.warning("Missing team codes in NBA row: %s", row)
                continue

            # Determine home/away based on game_location
            # H = this team is home, A = this team is away, N = neutral
            if game_location == "H":
                home_team_code = team_code
                away_team_code = opp_code
                home_score_str = row.get("pts", "")
                away_score_str = row.get("opp_pts", "")
            else:
                # A or N - this team is away
                home_team_code = opp_code
                away_team_code = team_code
                home_score_str = row.get("opp_pts", "")
                away_score_str = row.get("pts", "")

            # Parse scores
            try:
                home_score = int(home_score_str) if home_score_str else None
                away_score = int(away_score_str) if away_score_str else None
            except ValueError:
                home_score = None
                away_score = None

            # Parse game context
            is_playoffs = row.get("is_playoffs", "0") == "1"
            is_neutral_site = game_location == "N"

            # Determine game type
            game_type = "playoff" if is_playoffs else "regular"

            yield HistoricalGameRecord(
                sport="nba",
                season=season,
                game_date=game_date,
                home_team_code=home_team_code,
                away_team_code=away_team_code,
                home_score=home_score,
                away_score=away_score,
                is_neutral_site=is_neutral_site,
                is_playoff=is_playoffs,
                game_type=game_type,
                venue_name=None,
                source="fivethirtyeight",
                source_file=source_file,
                external_game_id=row.get("game_id"),
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


def load_fivethirtyeight_nba_games(
    file_path: Path,
    seasons: list[int] | None = None,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
    *,
    show_progress: bool = True,
) -> BatchInsertResult:
    """
    Load FiveThirtyEight NBA game data (nbaallelo.csv format).

    This handles the NBA-specific format where each game appears twice
    (once per team) with _iscopy flag to distinguish duplicates.

    Args:
        file_path: Path to nbaallelo.csv file
        seasons: Filter to specific seasons (default: all)
        error_mode: How to handle errors (default: FAIL)
        show_progress: Whether to show progress bar

    Returns:
        BatchInsertResult with statistics

    Example:
        >>> result = load_fivethirtyeight_nba_games(
        ...     Path("nba_elo.csv"),
        ...     seasons=[2020, 2021, 2022, 2023, 2024],
        ...     error_mode=ErrorHandlingMode.COLLECT
        ... )
        >>> print(f"Loaded {result.records_inserted} NBA games")
    """
    logger.info("Loading FiveThirtyEight NBA game data from %s", file_path)

    records = parse_fivethirtyeight_nba_csv(file_path, seasons)
    result = bulk_insert_historical_games(
        records, error_mode=error_mode, show_progress=show_progress
    )

    logger.info(
        "FiveThirtyEight NBA games load complete: processed=%d, inserted=%d, skipped=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
    )

    # Print summary table
    print_load_summary(
        "FiveThirtyEight NBA Games Load",
        processed=result.records_processed,
        inserted=result.records_inserted,
        skipped=result.records_skipped,
        errors=result.errors,
        show_summary=show_progress,
    )

    return result


# =============================================================================
# Neil Paine NHL Games Loader
# =============================================================================


def parse_neil_paine_nhl_games_csv(
    file_path: Path,
    seasons: list[int] | None = None,
) -> Iterator[HistoricalGameRecord]:
    """
    Parse Neil Paine NHL Elo CSV and yield historical game records.

    Neil Paine NHL Format:
        This format has dual rows per game (one for each team's perspective).
        Filter by is_home=1 to get one row per game with correct home/away.

    Columns Used:
        - game_ID: External game identifier
        - season: Season year (1918 = 1917-18 season)
        - date: Game date (YYYY-MM-DD)
        - team1: Home team (when is_home=1)
        - team2: Away team (when is_home=1)
        - score1, score2: Final scores
        - playoff: 0=regular, 1=playoff
        - neutral: 0=home, 1=neutral site
        - ot: Overtime indicator (NA or OT)
        - is_home: 1=home perspective, 0=away perspective

    Args:
        file_path: Path to Neil Paine NHL CSV file
        seasons: Filter to specific seasons (default: all)

    Yields:
        HistoricalGameRecord for each game

    Educational Note:
    -----------------
    The NHL season spans two calendar years (e.g., 2023-24).
    The season value represents the ending year (2024 for 2023-24 season).
    Games start in October and playoffs end in June.

    Overtime handling:
        - "NA" or empty: Regulation game
        - "OT": Overtime game (any format - SO, 3v3, etc.)
        The game_type field captures this: "regular", "playoff", "overtime"

    Example:
        >>> records = list(parse_neil_paine_nhl_games_csv(
        ...     Path("nhl_elo.csv"),
        ...     seasons=[2023, 2024]
        ... ))
        >>> len(records)  # ~82 games * 32 teams / 2 * 2 seasons ≈ 2624
    """
    source_file = file_path.name
    from precog.database.seeding.team_history import resolve_team_code

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Filter to home perspective only (is_home=1) to avoid duplicates
            is_home = row.get("is_home", "0")
            if is_home != "1":
                continue

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
                logger.warning("Invalid date in NHL row: %s", row)
                continue

            # Extract team codes (team1 = home when is_home=1)
            home_team_code = row.get("team1", "").strip().upper()
            away_team_code = row.get("team2", "").strip().upper()

            if not home_team_code or not away_team_code:
                continue

            # Normalize team codes using unified team history
            home_team_code = resolve_team_code("nhl", home_team_code)
            away_team_code = resolve_team_code("nhl", away_team_code)

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
            # Note: Overtime (ot column) is a game modifier, not a type
            # The 'ot' column indicates if game went to overtime (OT, SO, etc.)
            # but the game_type should still be 'regular' or 'playoff'
            game_type = "playoff" if is_playoff else "regular"

            # External game ID
            external_id = row.get("game_ID", "") or None

            yield HistoricalGameRecord(
                sport="nhl",
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
                source="fivethirtyeight",  # Neil Paine created 538's Elo model
                source_file=source_file,
                external_game_id=external_id,
            )


def load_neil_paine_nhl_games(
    file_path: Path,
    seasons: list[int] | None = None,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.FAIL,
    *,
    show_progress: bool = True,
) -> BatchInsertResult:
    """
    Load Neil Paine NHL game data into the historical_games table.

    Loads NHL game results from the Neil Paine Elo dataset which spans
    from 1917 (NHL founding) to present with 137,000+ games.

    Args:
        file_path: Path to Neil Paine NHL CSV file
        seasons: Filter to specific seasons (default: all)
        error_mode: How to handle errors (default: FAIL)
        show_progress: Whether to show progress bar

    Returns:
        BatchInsertResult with statistics

    Example:
        >>> # Load recent seasons for Elo computation
        >>> result = load_neil_paine_nhl_games(
        ...     Path("data/historical/nhl_elo.csv"),
        ...     seasons=[2020, 2021, 2022, 2023, 2024],
        ... )
        >>> print(f"Loaded {result.records_inserted} NHL games")
        >>>
        >>> # Load all historical data with error collection
        >>> result = load_neil_paine_nhl_games(
        ...     Path("data/historical/nhl_elo.csv"),
        ...     error_mode=ErrorHandlingMode.COLLECT,
        ... )

    Related:
        - ADR-109: Elo Rating Computation Engine Architecture
        - Issue #273: Multi-sport Elo computation
        - load_neil_paine_nhl_elo(): Loads Elo ratings from same file
    """
    logger.info("Loading Neil Paine NHL game data from %s", file_path)

    records = parse_neil_paine_nhl_games_csv(file_path, seasons)
    result = bulk_insert_historical_games(
        records, error_mode=error_mode, show_progress=show_progress
    )

    logger.info(
        "Neil Paine NHL games load complete: processed=%d, inserted=%d, skipped=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
    )

    # Print summary table
    print_load_summary(
        "Neil Paine NHL Games Load",
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


# =============================================================================
# ESPN Historical Games Loader
# =============================================================================
# Reference: Issue #257 - ESPN Historical Data Seeding
# Related ADR: ADR-029 (ESPN Data Model)
#
# Design Philosophy:
#   1. Cache-first: Always check local cache before making API calls
#   2. Persistent: Save all ESPN responses to local files for reproducibility
#   3. Rate-aware: Respect ESPN's rate limits with automatic retry
#   4. TimescaleDB-ready: Standard PostgreSQL schema works with hypertables
#
# Cache Structure:
#   data/historical/espn/{sport}/
#     └── {YYYY-MM-DD}.json  (one file per date with all games)
#
# Usage Modes:
#   - fetch: API calls + cache (default for new data)
#   - cache: Load from cache only (no API calls)
# =============================================================================

# Default cache directory for ESPN data
ESPN_CACHE_DIR = Path("data/historical/espn")


def get_espn_cache_path(sport: str, game_date: date) -> Path:
    """Get the cache file path for a specific sport and date.

    Args:
        sport: Sport code (nfl, nba, nhl, mlb, etc.)
        game_date: Date of the games

    Returns:
        Path to the JSON cache file

    Educational Note:
        Cache files are organized by sport and date for easy navigation:
        data/historical/espn/nfl/2024-01-15.json

        This structure allows:
        - Easy manual inspection of cached data
        - Simple date-range operations (glob patterns)
        - Efficient incremental updates (only fetch missing dates)
    """
    cache_dir = ESPN_CACHE_DIR / sport.lower()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{game_date.isoformat()}.json"


def is_date_cached(sport: str, game_date: date) -> bool:
    """Check if ESPN data for a date is already cached.

    Args:
        sport: Sport code
        game_date: Date to check

    Returns:
        True if cache file exists and is non-empty
    """
    cache_path = get_espn_cache_path(sport, game_date)
    return cache_path.exists() and cache_path.stat().st_size > 0


def save_espn_cache(sport: str, game_date: date, games: list[dict[str, Any]]) -> None:
    """Save ESPN game data to local cache file.

    Args:
        sport: Sport code
        game_date: Date of the games
        games: List of ESPNGameFull dicts from API

    Educational Note:
        We save the raw API response to preserve all data fields,
        even those we don't currently use. This future-proofs the cache
        for potential feature additions (e.g., play-by-play data).
    """
    cache_path = get_espn_cache_path(sport, game_date)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "sport": sport,
                "date": game_date.isoformat(),
                "fetched_at": datetime.now().isoformat(),
                "games": games,
            },
            f,
            indent=2,
            default=str,  # Handle datetime, Decimal, etc.
        )
    logger.debug("Cached %d games for %s on %s", len(games), sport, game_date)


def load_espn_cache(sport: str, game_date: date) -> list[dict[str, Any]] | None:
    """Load ESPN game data from local cache file.

    Args:
        sport: Sport code
        game_date: Date to load

    Returns:
        List of game dicts if cache exists, None otherwise
    """
    cache_path = get_espn_cache_path(sport, game_date)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
            games: list[dict[str, Any]] = data.get("games", [])
            return games
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Invalid cache file %s: %s", cache_path, e)
        return None


def espn_game_to_historical_record(
    game: dict[str, Any],
    sport: str,
) -> HistoricalGameRecord | None:
    """Convert ESPN API game data to HistoricalGameRecord format.

    Args:
        game: ESPNGameFull dict from API
        sport: Sport code for normalization

    Returns:
        HistoricalGameRecord if conversion successful, None if game not complete

    Educational Note:
        We only seed COMPLETED games (status = "final") because:
        1. Incomplete games have no final scores
        2. Scheduled games haven't happened yet
        3. In-progress games may change before completion

        ESPN's game_status values:
        - "scheduled": Game hasn't started
        - "in_progress": Game is live
        - "halftime": At halftime/intermission
        - "final": Game is complete (this is what we want)
    """
    try:
        # Extract metadata and state
        metadata = game.get("metadata", {})
        state = game.get("state", {})

        # Only process completed games
        game_status = state.get("game_status", "")
        if game_status != "final":
            return None

        # Parse game date
        game_date_str = metadata.get("game_date", "")
        if not game_date_str:
            return None

        try:
            # Handle ISO format with timezone
            if "T" in game_date_str:
                game_date_obj = datetime.fromisoformat(game_date_str.replace("Z", "+00:00")).date()
            else:
                game_date_obj = datetime.strptime(  # noqa: DTZ007
                    game_date_str, "%Y-%m-%d"
                ).date()
        except ValueError:
            logger.warning("Invalid date format: %s", game_date_str)
            return None

        # Extract team codes
        home_team = metadata.get("home_team", {})
        away_team = metadata.get("away_team", {})

        home_code = home_team.get("team_code", "")
        away_code = away_team.get("team_code", "")

        if not home_code or not away_code:
            return None

        # Normalize team codes using sport-specific mapping
        home_code = normalize_team_code(home_code, sport=sport)
        away_code = normalize_team_code(away_code, sport=sport)

        # Extract scores
        home_score = state.get("home_score")
        away_score = state.get("away_score")

        # Determine season (use year of game date)
        # For sports like NFL that span years, this is still correct
        # because we use the calendar year the game was played
        season = game_date_obj.year

        # Check for playoff/postseason
        season_type = metadata.get("season_type", "regular")
        is_playoff = season_type in ("playoff", "postseason", "bowl")

        # Get venue
        venue = metadata.get("venue", {})
        venue_name = venue.get("name")

        # Get ESPN event ID
        espn_event_id = metadata.get("espn_event_id", "")

        return HistoricalGameRecord(
            sport=sport.lower(),
            season=season,
            game_date=game_date_obj,
            home_team_code=home_code,
            away_team_code=away_code,
            home_score=home_score,
            away_score=away_score,
            is_neutral_site=metadata.get("neutral_site", False),
            is_playoff=is_playoff,
            game_type=season_type,
            venue_name=venue_name,
            source="espn",
            source_file=None,
            external_game_id=espn_event_id,
        )

    except Exception as e:
        logger.warning("Error converting ESPN game: %s", e)
        return None


def fetch_espn_games_for_date(
    sport: str,
    game_date: date,
    *,
    use_cache: bool = True,
    rate_limit_wait: float = 7.5,
) -> list[dict[str, Any]]:
    """Fetch ESPN games for a specific date, with optional caching.

    Args:
        sport: Sport code (nfl, nba, nhl, mlb, etc.)
        game_date: Date to fetch games for
        use_cache: If True, check cache first and save results
        rate_limit_wait: Seconds to wait on rate limit before retry

    Returns:
        List of ESPNGameFull dicts

    Educational Note:
        Rate Limiting Strategy:
        - ESPN allows ~500 requests/hour (8.3 per minute)
        - We wait 7.5 seconds on rate limit, then retry
        - This ensures we stay well within limits for bulk operations

        For a full season of ~180 days, this means:
        - Best case (all cached): 0 API calls
        - Worst case (nothing cached): 180 calls = ~22 minutes
        - Rate limited: Automatic retry after 7.5s delay
    """
    # Check cache first if enabled
    if use_cache and is_date_cached(sport, game_date):
        cached = load_espn_cache(sport, game_date)
        if cached is not None:
            logger.debug("Loaded %d games from cache for %s on %s", len(cached), sport, game_date)
            return cached

    # Import ESPN client here to avoid circular imports
    from precog.api_connectors.espn_client import ESPNClient, RateLimitExceeded

    # Fetch from API
    client = ESPNClient()
    try:
        # Convert date to datetime for API call
        game_datetime = datetime.combine(game_date, datetime.min.time())
        games = client.get_scoreboard(sport, game_datetime)

        # Convert to serializable dicts (ESPNGameFull is TypedDict)
        games_list = [dict(g) for g in games]

        # Cache the results if enabled
        if use_cache:
            save_espn_cache(sport, game_date, games_list)

        logger.debug(
            "Fetched %d games from ESPN API for %s on %s", len(games_list), sport, game_date
        )
        return games_list

    except RateLimitExceeded:
        logger.warning("Rate limit hit, waiting %.1f seconds...", rate_limit_wait)
        time.sleep(rate_limit_wait)
        # Retry once after waiting
        games = client.get_scoreboard(sport, datetime.combine(game_date, datetime.min.time()))
        games_list = [dict(g) for g in games]
        if use_cache:
            save_espn_cache(sport, game_date, games_list)
        return games_list

    finally:
        client.close()


def generate_date_range(start_date: date, end_date: date) -> list[date]:
    """Generate list of dates between start and end (inclusive).

    Args:
        start_date: First date in range
        end_date: Last date in range

    Returns:
        List of dates
    """
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def load_espn_historical_games(
    sport: str,
    start_date: date,
    end_date: date,
    *,
    use_cache: bool = True,
    fetch_missing: bool = True,
    error_mode: ErrorHandlingMode = ErrorHandlingMode.SKIP,
    show_progress: bool = True,
) -> BatchInsertResult:
    """Load historical games from ESPN API with caching support.

    This is the main entry point for ESPN historical game seeding.

    Args:
        sport: Sport code (nfl, nba, nhl, mlb, ncaaf, ncaab, wnba)
        start_date: First date to load (inclusive)
        end_date: Last date to load (inclusive)
        use_cache: If True, use cached data when available
        fetch_missing: If True, fetch from API for dates not in cache
                       If False, only load from cache (no API calls)
        error_mode: How to handle insertion errors
        show_progress: If True, show progress bar

    Returns:
        BatchInsertResult with insertion statistics

    Educational Note:
        Two primary usage modes:

        1. Fetch Mode (fetch_missing=True):
           - Check cache for each date
           - Fetch from ESPN API if not cached
           - Save fetched data to cache
           - Insert into database
           Use for: Initial seeding, updating with new games

        2. Cache Mode (fetch_missing=False):
           - Only load from existing cache files
           - No API calls made
           - Useful for reproducible seeding in CI/CD
           Use for: Production deployments, offline seeding

    Example:
        >>> # Fetch and cache NFL games for 2023 season
        >>> result = load_espn_historical_games(
        ...     sport="nfl",
        ...     start_date=date(2023, 9, 7),
        ...     end_date=date(2024, 2, 11),
        ...     use_cache=True,
        ...     fetch_missing=True,
        ... )
        >>> print(f"Loaded {result.successful} games")

        >>> # Load from cache only (no API calls)
        >>> result = load_espn_historical_games(
        ...     sport="nfl",
        ...     start_date=date(2023, 9, 7),
        ...     end_date=date(2024, 2, 11),
        ...     fetch_missing=False,  # Cache only
        ... )
    """
    logger.info(
        "Loading ESPN historical games: sport=%s, range=%s to %s, cache=%s, fetch=%s",
        sport,
        start_date,
        end_date,
        use_cache,
        fetch_missing,
    )

    # Generate date range
    dates = generate_date_range(start_date, end_date)

    # Collect all games from dates
    all_records: list[HistoricalGameRecord] = []
    cached_count = 0
    fetched_count = 0
    skipped_count = 0

    # Create progress description
    desc = f"Loading ESPN {sport.upper()} games"

    with seeding_progress(description=desc, total=len(dates), show_progress=show_progress) as (
        progress,
        task,
    ):
        for game_date in dates:
            # Check if we should fetch or skip
            if use_cache and is_date_cached(sport, game_date):
                games = load_espn_cache(sport, game_date)
                if games:
                    cached_count += 1
            elif fetch_missing:
                games = fetch_espn_games_for_date(sport, game_date, use_cache=use_cache)
                fetched_count += 1
            else:
                # Cache mode but no cache file - skip
                skipped_count += 1
                if progress and task is not None:
                    progress.advance(task)
                continue

            # Convert games to records
            if games:
                for game in games:
                    record = espn_game_to_historical_record(game, sport)
                    if record:
                        all_records.append(record)

            if progress and task is not None:
                progress.advance(task)

    logger.info(
        "ESPN data collection complete: %d dates cached, %d fetched, %d skipped",
        cached_count,
        fetched_count,
        skipped_count,
    )

    # Bulk insert all records
    if not all_records:
        logger.warning("No completed games found in date range")
        return BatchInsertResult(
            total_records=0,
            successful=0,
            skipped=0,
            failed=0,
            failed_records=[],
        )

    result = bulk_insert_historical_games(
        iter(all_records),
        error_mode=error_mode,
        show_progress=show_progress,
    )

    # Log summary
    logger.info(
        "ESPN historical games load complete: processed=%d, inserted=%d, skipped=%d",
        result.total_records,
        result.successful,
        result.skipped,
    )

    # Print summary table
    print_load_summary(
        operation=f"ESPN {sport.upper()} Games Load Complete",
        processed=result.total_records,
        inserted=result.successful,
        skipped=result.skipped,
    )

    return result


def list_cached_dates(sport: str) -> list[date]:
    """List all dates that have cached ESPN data for a sport.

    Args:
        sport: Sport code

    Returns:
        Sorted list of dates with cache files
    """
    cache_dir = ESPN_CACHE_DIR / sport.lower()
    if not cache_dir.exists():
        return []

    dates = []
    for cache_file in cache_dir.glob("*.json"):
        try:
            date_str = cache_file.stem  # e.g., "2024-01-15"
            dates.append(date.fromisoformat(date_str))
        except ValueError:
            continue

    return sorted(dates)


def get_cache_stats(sport: str | None = None) -> dict[str, Any]:
    """Get statistics about cached ESPN data.

    Args:
        sport: Specific sport to check, or None for all sports

    Returns:
        Dict with cache statistics
    """
    if sport:
        sports = [sport.lower()]
    else:
        # Find all sport directories
        if not ESPN_CACHE_DIR.exists():
            return {"total_files": 0, "total_size_mb": 0, "sports": {}}
        sports = [d.name for d in ESPN_CACHE_DIR.iterdir() if d.is_dir()]

    stats: dict[str, Any] = {"total_files": 0, "total_size_mb": 0.0, "sports": {}}

    for s in sports:
        cache_dir = ESPN_CACHE_DIR / s
        if not cache_dir.exists():
            continue

        files = list(cache_dir.glob("*.json"))
        size_bytes = sum(f.stat().st_size for f in files)
        size_mb = size_bytes / (1024 * 1024)

        dates = list_cached_dates(s)
        date_range = f"{min(dates)} to {max(dates)}" if dates else "none"

        stats["sports"][s] = {
            "files": len(files),
            "size_mb": round(size_mb, 2),
            "date_range": date_range,
        }
        stats["total_files"] += len(files)
        stats["total_size_mb"] += size_mb

    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    return stats
