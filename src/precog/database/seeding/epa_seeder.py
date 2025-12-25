"""
EPA (Expected Points Added) Seeder Module.

Seeds the historical_epa table with NFL EPA metrics from nflreadpy.
EPA is used to enhance Elo predictions with efficiency metrics.

Usage:
    CLI:
        python main.py data seed-epa --seasons 2023 2024
        python main.py data seed-epa --seasons 2023 --weekly  # Include weekly data

    Programmatic:
        from precog.database.seeding.epa_seeder import EPASeeder
        seeder = EPASeeder(connection)
        seeder.seed_seasons([2023, 2024])

Related:
    - ADR-109: Elo Rating Computation Engine
    - REQ-ELO-003: EPA Integration from nflreadpy
    - Migration 0013: historical_epa table
    - ELO_COMPUTATION_GUIDE_V1.1.md: EPA methodology

Educational Note:
    EPA (Expected Points Added) measures how much each play improves
    a team's expected points. It's the most predictive publicly
    available NFL metric. We aggregate play-level EPA to team-week
    and team-season levels for Elo enhancement.

    Example EPA values:
    - Offensive EPA +0.15: Above average offense (~8th best)
    - Defensive EPA -0.10: Good defense (lower is better)
    - EPA differential +0.25: Playoff-caliber team
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from sqlalchemy import text

from precog.database.seeding.sources.sports.nflreadpy_adapter import (
    EPARecord,
    NFLReadPySource,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================


class SeedingStats(TypedDict):
    """Statistics for EPA seeding operations."""

    seasons_processed: int
    season_records_inserted: int
    season_records_updated: int
    season_records_skipped: int
    weekly_inserted: int
    weekly_updated: int
    weekly_skipped: int
    errors: list[str]


class OperationStats(TypedDict):
    """Statistics for a single seeding operation."""

    inserted: int
    updated: int
    skipped: int


# =============================================================================
# EPA Seeder Class
# =============================================================================


class EPASeeder:
    """Seeds EPA metrics into the historical_epa table.

    Loads EPA data from nflreadpy and inserts/updates records
    in the historical_epa table for Elo enhancement.

    Attributes:
        connection: SQLAlchemy database connection
        source: NFLReadPySource instance for data fetching

    Example:
        >>> from precog.database import get_connection
        >>> conn = get_connection()
        >>> seeder = EPASeeder(conn)
        >>> stats = seeder.seed_seasons([2023, 2024])
        >>> print(f"Inserted {stats['season_records_inserted']} records")

    Related:
        - Migration 0013: Creates historical_epa table
        - NFLReadPySource: Fetches EPA from nflreadpy
    """

    def __init__(self, connection: Connection) -> None:
        """Initialize EPA seeder.

        Args:
            connection: Active SQLAlchemy database connection

        Raises:
            DataSourceError: If nflreadpy is not installed
        """
        self.connection = connection
        self.source = NFLReadPySource()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def seed_seasons(
        self,
        seasons: list[int],
        include_weekly: bool = False,
    ) -> SeedingStats:
        """Seed EPA data for specified seasons.

        Args:
            seasons: List of NFL seasons to seed (e.g., [2022, 2023])
            include_weekly: If True, also seed weekly EPA data

        Returns:
            Statistics dict with counts of inserted, updated, skipped records

        Example:
            >>> stats = seeder.seed_seasons([2023], include_weekly=True)
            >>> print(f"Seasons: {stats['seasons_processed']}")
            >>> print(f"Weekly records: {stats['weekly_inserted']}")
        """
        stats: SeedingStats = {
            "seasons_processed": 0,
            "season_records_inserted": 0,
            "season_records_updated": 0,
            "season_records_skipped": 0,
            "weekly_inserted": 0,
            "weekly_updated": 0,
            "weekly_skipped": 0,
            "errors": [],
        }

        for season in seasons:
            try:
                self._logger.info("Seeding EPA for season %d", season)

                # Seed season-level aggregates
                season_stats = self._seed_season_epa(season)
                stats["season_records_inserted"] += season_stats["inserted"]
                stats["season_records_updated"] += season_stats["updated"]
                stats["season_records_skipped"] += season_stats["skipped"]

                # Optionally seed weekly data
                if include_weekly:
                    weekly_stats = self._seed_weekly_epa(season)
                    stats["weekly_inserted"] += weekly_stats["inserted"]
                    stats["weekly_updated"] += weekly_stats["updated"]
                    stats["weekly_skipped"] += weekly_stats["skipped"]

                stats["seasons_processed"] += 1
                self._logger.info(
                    "Season %d complete: %d season records, %d weekly records",
                    season,
                    season_stats["inserted"] + season_stats["updated"],
                    stats["weekly_inserted"] if include_weekly else 0,
                )

            except Exception as e:
                error_msg = f"Failed to seed season {season}: {e}"
                self._logger.error(error_msg)
                stats["errors"].append(error_msg)

        return stats

    def _seed_season_epa(self, season: int) -> OperationStats:
        """Seed season-level EPA aggregates.

        Args:
            season: NFL season year

        Returns:
            Stats dict with inserted/updated/skipped counts
        """
        stats: OperationStats = {"inserted": 0, "updated": 0, "skipped": 0}

        for record in self.source.load_season_epa(season):
            result = self._upsert_epa_record(record, season)
            stats[result] += 1

        return stats

    def _seed_weekly_epa(self, season: int) -> OperationStats:
        """Seed weekly EPA data for a season.

        Args:
            season: NFL season year

        Returns:
            Stats dict with inserted/updated/skipped counts
        """
        stats: OperationStats = {"inserted": 0, "updated": 0, "skipped": 0}

        for record in self.source.load_epa(season=season, week=None):
            result = self._upsert_epa_record(record, season)
            stats[result] += 1

        return stats

    def _upsert_epa_record(
        self, record: EPARecord, season: int
    ) -> Literal["inserted", "updated", "skipped"]:
        """Insert or update a single EPA record.

        Args:
            record: EPA record from nflreadpy adapter
            season: NFL season year

        Returns:
            "inserted", "updated", or "skipped"
        """
        team_code = record["team_code"]
        week = record["week"]

        # Resolve team_id from teams table
        team_id = self._resolve_team_id(team_code)
        if team_id is None:
            self._logger.warning("Could not resolve team_id for %s, skipping", team_code)
            return "skipped"

        # Check if record exists
        existing = self._get_existing_record(team_id, season, week)

        if existing:
            # Update existing record
            self._update_epa_record(existing["id"], record)
            return "updated"

        # Insert new record
        self._insert_epa_record(team_id, record)
        return "inserted"

    def _resolve_team_id(self, team_code: str) -> int | None:
        """Resolve team code to team_id from teams table.

        Args:
            team_code: Team abbreviation (e.g., "KC")

        Returns:
            team_id or None if not found
        """
        result = self.connection.execute(
            text(
                """
                SELECT id FROM teams
                WHERE abbreviation = :team_code AND sport = 'nfl'
                LIMIT 1
                """
            ),
            {"team_code": team_code},
        )
        row = result.fetchone()
        return row[0] if row else None

    def _get_existing_record(
        self, team_id: int, season: int, week: int | None
    ) -> dict[str, Any] | None:
        """Check if EPA record already exists.

        Args:
            team_id: Team ID from teams table
            season: NFL season year
            week: Week number or None for season total

        Returns:
            Existing record dict or None
        """
        if week is None:
            result = self.connection.execute(
                text(
                    """
                    SELECT id FROM historical_epa
                    WHERE team_id = :team_id AND season = :season AND week IS NULL
                    LIMIT 1
                    """
                ),
                {"team_id": team_id, "season": season},
            )
        else:
            result = self.connection.execute(
                text(
                    """
                    SELECT id FROM historical_epa
                    WHERE team_id = :team_id AND season = :season AND week = :week
                    LIMIT 1
                    """
                ),
                {"team_id": team_id, "season": season, "week": week},
            )

        row = result.fetchone()
        return {"id": row[0]} if row else None

    def _insert_epa_record(self, team_id: int, record: EPARecord) -> None:
        """Insert new EPA record.

        Args:
            team_id: Resolved team ID
            record: EPA record from adapter
        """
        now = datetime.datetime.now(datetime.UTC)

        self.connection.execute(
            text(
                """
                INSERT INTO historical_epa (
                    team_id, season, week,
                    off_epa_per_play, pass_epa_per_play, rush_epa_per_play,
                    def_epa_per_play, def_pass_epa_per_play, def_rush_epa_per_play,
                    epa_differential, games_played, source,
                    created_at, updated_at
                ) VALUES (
                    :team_id, :season, :week,
                    :off_epa, :pass_epa, :rush_epa,
                    :def_epa, :def_pass_epa, :def_rush_epa,
                    :epa_diff, :games_played, :source,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "team_id": team_id,
                "season": record["season"],
                "week": record["week"],
                "off_epa": self._decimal_to_float(record["off_epa_per_play"]),
                "pass_epa": self._decimal_to_float(record["pass_epa_per_play"]),
                "rush_epa": self._decimal_to_float(record["rush_epa_per_play"]),
                "def_epa": self._decimal_to_float(record["def_epa_per_play"]),
                "def_pass_epa": self._decimal_to_float(record["def_pass_epa_per_play"]),
                "def_rush_epa": self._decimal_to_float(record["def_rush_epa_per_play"]),
                "epa_diff": self._decimal_to_float(record["epa_differential"]),
                "games_played": record["games_played"],
                "source": record["source"],
                "created_at": now,
                "updated_at": now,
            },
        )

    def _update_epa_record(self, record_id: int, record: EPARecord) -> None:
        """Update existing EPA record.

        Args:
            record_id: ID of existing record
            record: Updated EPA data
        """
        now = datetime.datetime.now(datetime.UTC)

        self.connection.execute(
            text(
                """
                UPDATE historical_epa SET
                    off_epa_per_play = :off_epa,
                    pass_epa_per_play = :pass_epa,
                    rush_epa_per_play = :rush_epa,
                    def_epa_per_play = :def_epa,
                    def_pass_epa_per_play = :def_pass_epa,
                    def_rush_epa_per_play = :def_rush_epa,
                    epa_differential = :epa_diff,
                    games_played = :games_played,
                    source = :source,
                    updated_at = :updated_at
                WHERE id = :record_id
                """
            ),
            {
                "off_epa": self._decimal_to_float(record["off_epa_per_play"]),
                "pass_epa": self._decimal_to_float(record["pass_epa_per_play"]),
                "rush_epa": self._decimal_to_float(record["rush_epa_per_play"]),
                "def_epa": self._decimal_to_float(record["def_epa_per_play"]),
                "def_pass_epa": self._decimal_to_float(record["def_pass_epa_per_play"]),
                "def_rush_epa": self._decimal_to_float(record["def_rush_epa_per_play"]),
                "epa_diff": self._decimal_to_float(record["epa_differential"]),
                "games_played": record["games_played"],
                "source": record["source"],
                "updated_at": now,
                "record_id": record_id,
            },
        )

    @staticmethod
    def _decimal_to_float(value: Decimal | None) -> float | None:
        """Convert Decimal to float for database insertion.

        Args:
            value: Decimal value or None

        Returns:
            float value or None

        Note:
            PostgreSQL DECIMAL columns accept float values.
            The precision is preserved in the database column type.
        """
        if value is None:
            return None
        return float(value)


def seed_epa_from_cli(
    seasons: list[int],
    include_weekly: bool = False,
    connection: Connection | None = None,
) -> SeedingStats:
    """CLI entry point for EPA seeding.

    Args:
        seasons: List of seasons to seed
        include_weekly: Include weekly EPA data
        connection: Optional database connection (creates new if None)

    Returns:
        Seeding statistics

    Example:
        >>> stats = seed_epa_from_cli([2023, 2024], include_weekly=True)
        >>> print(f"Processed {stats['seasons_processed']} seasons")
    """
    if connection is None:
        from precog.database import get_connection

        connection = get_connection()

    seeder = EPASeeder(connection)
    return seeder.seed_seasons(seasons, include_weekly=include_weekly)
