"""
Historical Odds Data Loader for Precog.

This module provides utilities for loading historical betting odds from
external data sources into the historical_odds table.

Data Sources:
    - betting_csv: CSV files with spread/total data (e.g., slieb74/NFL-Betting-Data)
    - BettingCSVSource: Adapter for betting CSV files

Educational Notes:
------------------
Closing Line Value (CLV):
    CLV = Your bet price vs closing line.
    Beating the closing line is the best predictor of long-term profitability.
    This table enables historical CLV analysis across thousands of games.

Historical Odds Data Format:
    - spread_home_close: Point spread from home team perspective (e.g., -3.5)
    - total_close: Over/under line (e.g., 45.5)
    - moneyline_home_close: Moneyline odds for home team (e.g., -150)
    - home_covered: Whether home team covered the spread
    - game_went_over: Whether total went over the line

Team Code Normalization:
    Source adapters handle team code normalization internally.
    Historical data may have different codes than current teams:
    - Oakland Raiders (OAK) -> Las Vegas Raiders (LV)
    - San Diego Chargers (SD) -> LA Chargers (LAC)

Reference:
    - Issue #229: Expanded Historical Data Sources
    - Migration 0007: Create historical_odds table
    - ADR-106: Historical Data Collection Architecture
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from precog.database.connection import get_cursor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from precog.database.seeding.sources.base_source import OddsRecord

logger = logging.getLogger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class LoadResult:
    """Result of loading historical odds data."""

    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    def __add__(self, other: LoadResult) -> LoadResult:
        """Combine two LoadResults."""
        return LoadResult(
            records_processed=self.records_processed + other.records_processed,
            records_inserted=self.records_inserted + other.records_inserted,
            records_updated=self.records_updated + other.records_updated,
            records_skipped=self.records_skipped + other.records_skipped,
            errors=self.errors + other.errors,
            error_messages=self.error_messages + other.error_messages,
        )


# =============================================================================
# Source Name Mapping
# =============================================================================

# Map source adapter names to database-allowed values
# historical_odds table CHECK constraint: 'kaggle', 'odds_portal', 'action_network',
# 'pinnacle', 'manual', 'imported', 'consensus', 'betting_csv', 'fivethirtyeight'
SOURCE_NAME_MAPPING: dict[str, str] = {
    "betting_csv": "betting_csv",
    "fivethirtyeight": "fivethirtyeight",
    "kaggle": "kaggle",
    "odds_portal": "odds_portal",
    "action_network": "action_network",
    "pinnacle": "pinnacle",
    "manual": "manual",
}


def normalize_source_name(source: str) -> str:
    """
    Normalize source name to database-allowed value.

    Args:
        source: Source name from adapter

    Returns:
        Database-compatible source name
    """
    return SOURCE_NAME_MAPPING.get(source.lower(), "imported")


# =============================================================================
# Database Operations
# =============================================================================


def lookup_historical_game_id(
    sport: str,
    game_date: Any,  # date object
    home_team_code: str,
    away_team_code: str,
) -> int | None:
    """
    Look up historical_game_id for matching game.

    Args:
        sport: Sport code (e.g., "nfl")
        game_date: Game date
        home_team_code: Home team code (e.g., "KC")
        away_team_code: Away team code (e.g., "BUF")

    Returns:
        historical_game_id if found, None otherwise
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT historical_game_id FROM historical_games
            WHERE sport = %s
              AND game_date = %s
              AND home_team_code = %s
              AND away_team_code = %s
            """,
            (sport, game_date, home_team_code, away_team_code),
        )
        row = cursor.fetchone()
        if row:
            return int(row["historical_game_id"])
    return None


def insert_historical_odds(record: OddsRecord) -> bool:
    """
    Insert or update a single historical odds record.

    Uses ON CONFLICT to handle duplicates (same game, same sportsbook).

    Args:
        record: OddsRecord to insert

    Returns:
        True if successful, False otherwise
    """
    # Try to find matching historical game
    historical_game_id = lookup_historical_game_id(
        record["sport"],
        record["game_date"],
        record["home_team_code"],
        record["away_team_code"],
    )

    source = normalize_source_name(record["source"])
    sportsbook = record.get("sportsbook") or "consensus"

    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO historical_odds (
                historical_game_id, sport, game_date,
                home_team_code, away_team_code, sportsbook,
                spread_home_open, spread_home_close,
                spread_home_odds_open, spread_home_odds_close,
                moneyline_home_open, moneyline_home_close,
                moneyline_away_open, moneyline_away_close,
                total_open, total_close,
                over_odds_open, over_odds_close,
                home_covered, game_went_over,
                source, source_file
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (sport, game_date, home_team_code, away_team_code, sportsbook)
            DO UPDATE SET
                historical_game_id = EXCLUDED.historical_game_id,
                spread_home_open = COALESCE(EXCLUDED.spread_home_open, historical_odds.spread_home_open),
                spread_home_close = COALESCE(EXCLUDED.spread_home_close, historical_odds.spread_home_close),
                spread_home_odds_open = COALESCE(EXCLUDED.spread_home_odds_open, historical_odds.spread_home_odds_open),
                spread_home_odds_close = COALESCE(EXCLUDED.spread_home_odds_close, historical_odds.spread_home_odds_close),
                moneyline_home_open = COALESCE(EXCLUDED.moneyline_home_open, historical_odds.moneyline_home_open),
                moneyline_home_close = COALESCE(EXCLUDED.moneyline_home_close, historical_odds.moneyline_home_close),
                moneyline_away_open = COALESCE(EXCLUDED.moneyline_away_open, historical_odds.moneyline_away_open),
                moneyline_away_close = COALESCE(EXCLUDED.moneyline_away_close, historical_odds.moneyline_away_close),
                total_open = COALESCE(EXCLUDED.total_open, historical_odds.total_open),
                total_close = COALESCE(EXCLUDED.total_close, historical_odds.total_close),
                over_odds_open = COALESCE(EXCLUDED.over_odds_open, historical_odds.over_odds_open),
                over_odds_close = COALESCE(EXCLUDED.over_odds_close, historical_odds.over_odds_close),
                home_covered = COALESCE(EXCLUDED.home_covered, historical_odds.home_covered),
                game_went_over = COALESCE(EXCLUDED.game_went_over, historical_odds.game_went_over),
                source = EXCLUDED.source,
                source_file = EXCLUDED.source_file
            """,
            (
                historical_game_id,
                record["sport"],
                record["game_date"],
                record["home_team_code"],
                record["away_team_code"],
                sportsbook,
                record.get("spread_home_open"),
                record.get("spread_home_close"),
                record.get("spread_home_odds_open"),
                record.get("spread_home_odds_close"),
                record.get("moneyline_home_open"),
                record.get("moneyline_home_close"),
                record.get("moneyline_away_open"),
                record.get("moneyline_away_close"),
                record.get("total_open"),
                record.get("total_close"),
                record.get("over_odds_open"),
                record.get("over_odds_close"),
                record.get("home_covered"),
                record.get("game_went_over"),
                source,
                record.get("source_file"),
            ),
        )
        return True


def bulk_insert_historical_odds(
    records: Iterator[OddsRecord],
    batch_size: int = 1000,
    link_games: bool = True,
) -> LoadResult:
    """
    Bulk insert historical odds records with batching.

    Args:
        records: Iterator of OddsRecord
        batch_size: Number of records per batch (default: 1000)
        link_games: Whether to look up historical_game_id (default: True)

    Returns:
        LoadResult with statistics
    """
    result = LoadResult()

    batch: list[tuple[Any, ...]] = []
    game_id_cache: dict[tuple[str, Any, str, str], int | None] = {}

    for record in records:
        result.records_processed += 1

        # Look up historical_game_id (with caching)
        historical_game_id: int | None = None
        if link_games:
            cache_key = (
                record["sport"],
                record["game_date"],
                record["home_team_code"],
                record["away_team_code"],
            )
            if cache_key not in game_id_cache:
                game_id_cache[cache_key] = lookup_historical_game_id(
                    record["sport"],
                    record["game_date"],
                    record["home_team_code"],
                    record["away_team_code"],
                )
            historical_game_id = game_id_cache[cache_key]

        source = normalize_source_name(record["source"])
        sportsbook = record.get("sportsbook") or "consensus"

        batch.append(
            (
                historical_game_id,
                record["sport"],
                record["game_date"],
                record["home_team_code"],
                record["away_team_code"],
                sportsbook,
                record.get("spread_home_open"),
                record.get("spread_home_close"),
                record.get("spread_home_odds_open"),
                record.get("spread_home_odds_close"),
                record.get("moneyline_home_open"),
                record.get("moneyline_home_close"),
                record.get("moneyline_away_open"),
                record.get("moneyline_away_close"),
                record.get("total_open"),
                record.get("total_close"),
                record.get("over_odds_open"),
                record.get("over_odds_close"),
                record.get("home_covered"),
                record.get("game_went_over"),
                source,
                record.get("source_file"),
            )
        )

        # Flush batch when full
        if len(batch) >= batch_size:
            inserted = _flush_odds_batch(batch)
            result.records_inserted += inserted
            batch = []

    # Flush remaining records
    if batch:
        inserted = _flush_odds_batch(batch)
        result.records_inserted += inserted

    return result


def _flush_odds_batch(batch: list[tuple[Any, ...]]) -> int:
    """
    Insert a batch of odds records using execute_values.

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
            INSERT INTO historical_odds (
                historical_game_id, sport, game_date,
                home_team_code, away_team_code, sportsbook,
                spread_home_open, spread_home_close,
                spread_home_odds_open, spread_home_odds_close,
                moneyline_home_open, moneyline_home_close,
                moneyline_away_open, moneyline_away_close,
                total_open, total_close,
                over_odds_open, over_odds_close,
                home_covered, game_went_over,
                source, source_file
            ) VALUES %s
            ON CONFLICT (sport, game_date, home_team_code, away_team_code, sportsbook)
            DO UPDATE SET
                historical_game_id = EXCLUDED.historical_game_id,
                spread_home_close = COALESCE(EXCLUDED.spread_home_close, historical_odds.spread_home_close),
                total_close = COALESCE(EXCLUDED.total_close, historical_odds.total_close),
                home_covered = COALESCE(EXCLUDED.home_covered, historical_odds.home_covered),
                game_went_over = COALESCE(EXCLUDED.game_went_over, historical_odds.game_went_over),
                source = EXCLUDED.source,
                source_file = EXCLUDED.source_file
        """
        execute_values(cursor, query, batch)
        return len(batch)


# =============================================================================
# Main Entry Points
# =============================================================================


def load_odds_from_source(
    source_adapter: Any,
    sport: str = "nfl",
    seasons: list[int] | None = None,
    link_games: bool = True,
) -> LoadResult:
    """
    Load historical odds from a source adapter into the database.

    Args:
        source_adapter: A source adapter with load_odds() method
        sport: Sport code (default: "nfl")
        seasons: Filter to specific seasons (default: all)
        link_games: Whether to look up historical_game_id (default: True)

    Returns:
        LoadResult with statistics

    Example:
        >>> from precog.database.seeding.sources import BettingCSVSource
        >>> source = BettingCSVSource(data_dir=Path("data/historical"))
        >>> result = load_odds_from_source(source, sport="nfl", seasons=[2023])
        >>> print(f"Loaded {result.records_inserted} odds records")
    """
    logger.info(
        "Loading historical odds: source=%s, sport=%s, seasons=%s",
        source_adapter.source_name,
        sport,
        seasons,
    )

    records = source_adapter.load_odds(sport=sport, seasons=seasons)
    result = bulk_insert_historical_odds(records, link_games=link_games)

    logger.info(
        "Historical odds load complete: processed=%d, inserted=%d, skipped=%d",
        result.records_processed,
        result.records_inserted,
        result.records_skipped,
    )

    return result


def get_historical_odds_stats() -> dict[str, Any]:
    """
    Get statistics about historical odds data in the database.

    Returns:
        Dictionary with counts by sport, season, source, sportsbook
    """
    with get_cursor() as cursor:
        # Count by sport
        cursor.execute("""
            SELECT sport, COUNT(*) as count
            FROM historical_odds
            GROUP BY sport
            ORDER BY sport
        """)
        by_sport = {row["sport"]: row["count"] for row in cursor.fetchall()}

        # Count by season (derived from game_date)
        cursor.execute("""
            SELECT EXTRACT(YEAR FROM game_date)::integer as season, COUNT(*) as count
            FROM historical_odds
            GROUP BY season
            ORDER BY season DESC
            LIMIT 10
        """)
        by_season = {row["season"]: row["count"] for row in cursor.fetchall()}

        # Count by source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM historical_odds
            GROUP BY source
            ORDER BY count DESC
        """)
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        # Count by sportsbook
        cursor.execute("""
            SELECT sportsbook, COUNT(*) as count
            FROM historical_odds
            GROUP BY sportsbook
            ORDER BY count DESC
        """)
        by_sportsbook = {row["sportsbook"]: row["count"] for row in cursor.fetchall()}

        # Count linked vs unlinked
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE historical_game_id IS NOT NULL) as linked,
                COUNT(*) FILTER (WHERE historical_game_id IS NULL) as unlinked
            FROM historical_odds
        """)
        linkage = cursor.fetchone()

        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM historical_odds")
        total = cursor.fetchone()["total"]

    return {
        "total": total,
        "by_sport": by_sport,
        "by_season": by_season,
        "by_source": by_source,
        "by_sportsbook": by_sportsbook,
        "linked_to_games": linkage["linked"] if linkage else 0,
        "unlinked": linkage["unlinked"] if linkage else 0,
    }


def link_orphan_odds_to_games() -> int:
    """
    Link historical_odds records without historical_game_id to matching games.

    This is useful after loading odds before games, or if new games are added.

    Returns:
        Number of records updated
    """
    with get_cursor(commit=True) as cursor:
        cursor.execute("""
            UPDATE historical_odds o
            SET historical_game_id = g.historical_game_id
            FROM historical_games g
            WHERE o.historical_game_id IS NULL
              AND o.sport = g.sport
              AND o.game_date = g.game_date
              AND o.home_team_code = g.home_team_code
              AND o.away_team_code = g.away_team_code
        """)
        rowcount: int = cursor.rowcount or 0
        return rowcount
