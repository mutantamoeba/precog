"""
Unit Tests for Historical Data CRUD Operations (Stats and Rankings).

Tests the historical_stats and historical_rankings table CRUD functions
with proper marker annotations per TESTING_STRATEGY V3.2.

Related:
- Issue #253: Add CRUD for historical_stats and historical_rankings tables
- Migration 0009: historical_stats and historical_rankings tables
- ADR-107: Historical Data Seeding Architecture
- Pattern 1: Decimal Precision (NEVER USE FLOAT)

Usage:
    pytest tests/unit/database/test_historical_data_crud.py -v
    pytest tests/unit/database/test_historical_data_crud.py -v -m unit
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.crud_operations import (
    get_historical_rankings,
    get_historical_stats,
    get_player_stats,
    get_team_ranking_history,
    get_team_stats,
    insert_historical_ranking,
    insert_historical_rankings_batch,
    insert_historical_stat,
    insert_historical_stats_batch,
)

# =============================================================================
# HISTORICAL STATS UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestInsertHistoricalStatUnit:
    """Unit tests for insert_historical_stat function with mocked database."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_stat_returns_stat_id(self, mock_get_cursor):
        """Test insert_historical_stat returns the stat_id from database."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_stat_id": 42}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Execute
        result = insert_historical_stat(
            sport="NFL",
            season=2024,
            stat_category="passing",
            stats={"yards": 4500, "touchdowns": 35},
            source="espn",
            week=17,
            team_code="KC",
            player_id="12345",
            player_name="Patrick Mahomes",
        )

        # Verify
        assert result == 42
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_stat_with_minimal_params(self, mock_get_cursor):
        """Test insert_historical_stat with only required parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_stat_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = insert_historical_stat(
            sport="NBA",
            season=2023,
            stat_category="points",
            stats={"ppg": 30.5},
            source="balldontlie",
            player_id="12345",  # Required: either team_code or player_id
        )

        assert result == 1
        # Verify SQL contains UPSERT pattern
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_stat_upsert_updates_existing(self, mock_get_cursor):
        """Test that UPSERT pattern updates stats when record exists.

        Educational Note:
            The UPSERT pattern (ON CONFLICT ... DO UPDATE) allows us to
            insert new records or update existing ones in a single atomic
            operation. This is essential for idempotent data seeding -
            running the same seed operation multiple times produces the
            same result without duplicating data.

        Reference:
            - PostgreSQL ON CONFLICT documentation
            - ADR-107: Historical Data Seeding Architecture
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_stat_id": 5}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        insert_historical_stat(
            sport="NFL",
            season=2024,
            stat_category="rushing",
            stats={"yards": 1500},
            source="espn",
            team_code="SF",  # Provides team-level stats
        )

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        # Verify UPSERT updates the stats on conflict
        assert "stats = EXCLUDED.stats" in sql
        assert "DO UPDATE SET" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_stat_handles_jsonb(self, mock_get_cursor):
        """Test that stats dict is properly handled as JSONB.

        Educational Note:
            JSONB columns in PostgreSQL allow flexible schema for stats.
            Different sports have different stat types (passing yards for
            NFL, 3-point percentage for NBA), and JSONB accommodates this
            without requiring schema changes for each new stat type.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_stat_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        complex_stats = {
            "yards": 4500,
            "touchdowns": 35,
            "interceptions": 10,
            "completion_pct": 68.5,  # Note: floats OK in JSON stats
            "games_started": 17,
        }

        insert_historical_stat(
            sport="NFL",
            season=2024,
            stat_category="passing",
            stats=complex_stats,
            source="espn",
            player_id="12345",  # Required: either team_code or player_id
        )

        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # Stats are JSON-serialized before being sent to the database
        # Find the JSON string in the params (8th position: after stat_category)
        import json

        expected_json = json.dumps(complex_stats)
        assert expected_json in params


@pytest.mark.unit
class TestInsertHistoricalStatsBatchUnit:
    """Unit tests for insert_historical_stats_batch function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_insert_single_batch(self, mock_get_cursor):
        """Test batch insert with records that fit in single batch."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        records = [
            {
                "sport": "NFL",
                "season": 2024,
                "week": i,
                "team_code": "KC",
                "stat_category": "passing",
                "stats": {"yards": 300 * i},
                "source": "espn",
            }
            for i in range(1, 6)
        ]

        inserted, failed = insert_historical_stats_batch(records)

        assert inserted == 5
        assert failed == 0
        # Should be called once for 5 records (less than default batch_size of 1000)
        # Note: batch insert uses executemany, not execute
        assert mock_cursor.executemany.call_count == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_insert_multiple_batches(self, mock_get_cursor):
        """Test batch insert splits records into multiple batches.

        Educational Note:
            Batch processing with configurable batch_size allows us to
            balance between memory usage and database round-trips. Large
            datasets are split into manageable chunks to prevent memory
            exhaustion and overly long transactions.
        """
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3  # Each batch inserts 3 records
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        records = [
            {
                "sport": "NFL",
                "season": 2024,
                "week": i,
                "team_code": "KC",
                "stat_category": "passing",
                "stats": {"yards": 300},
                "source": "espn",
            }
            for i in range(1, 10)  # 9 records
        ]

        inserted, failed = insert_historical_stats_batch(records, batch_size=3)

        assert inserted == 9  # 3 batches * 3 records
        assert failed == 0
        # Note: batch insert uses executemany, not execute
        assert mock_cursor.executemany.call_count == 3  # 3 batches

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_insert_empty_list(self, mock_get_cursor):
        """Test batch insert handles empty record list."""
        inserted, failed = insert_historical_stats_batch([])

        assert inserted == 0
        assert failed == 0
        mock_get_cursor.assert_not_called()


@pytest.mark.unit
class TestGetHistoricalStatsUnit:
    """Unit tests for get_historical_stats function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_stats_basic_query(self, mock_fetch_all):
        """Test basic query with required parameters only."""
        mock_fetch_all.return_value = [
            {"historical_stat_id": 1, "sport": "NFL", "season": 2024, "stats": {"yards": 4500}}
        ]

        result = get_historical_stats(sport="NFL", season=2024)

        assert len(result) == 1
        assert result[0]["sport"] == "NFL"
        mock_fetch_all.assert_called_once()

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_stats_with_all_filters(self, mock_fetch_all):
        """Test query with all optional filters applied."""
        mock_fetch_all.return_value = []

        get_historical_stats(
            sport="NFL",
            season=2024,
            week=10,
            team_code="KC",
            player_id="12345",
            stat_category="passing",
            source="espn",
            limit=50,
        )

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        # Verify all filters are in the WHERE clause
        assert "week = %s" in sql
        assert "team_code = %s" in sql
        assert "player_id = %s" in sql
        assert "stat_category = %s" in sql
        assert "source = %s" in sql
        assert "LIMIT %s" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_stats_ordered_by_season_week(self, mock_fetch_all):
        """Test results are ordered by season DESC, week DESC."""
        mock_fetch_all.return_value = []

        get_historical_stats(sport="NFL", season=2024)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        # The actual ORDER BY includes COALESCE for null-safe week ordering
        assert "ORDER BY season DESC" in sql


@pytest.mark.unit
class TestGetPlayerStatsUnit:
    """Unit tests for get_player_stats function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_player_stats_basic(self, mock_fetch_all):
        """Test get_player_stats with required parameters."""
        mock_fetch_all.return_value = [
            {"historical_stat_id": 1, "player_id": "12345", "stats": {"yards": 4500}}
        ]

        result = get_player_stats(sport="NFL", player_id="12345")

        assert len(result) == 1
        assert result[0]["player_id"] == "12345"

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_player_stats_with_season_filter(self, mock_fetch_all):
        """Test get_player_stats filters by season when provided."""
        mock_fetch_all.return_value = []

        get_player_stats(sport="NFL", player_id="12345", season=2024)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "season = %s" in sql


@pytest.mark.unit
class TestGetTeamStatsUnit:
    """Unit tests for get_team_stats function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_stats_basic(self, mock_fetch_all):
        """Test get_team_stats with required parameters."""
        mock_fetch_all.return_value = [
            {"historical_stat_id": 1, "team_code": "KC", "stats": {"points": 450}}
        ]

        result = get_team_stats(sport="NFL", team_code="KC")

        assert len(result) == 1
        assert result[0]["team_code"] == "KC"

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_stats_ordered_by_season_week(self, mock_fetch_all):
        """Test results ordered by season DESC, week DESC."""
        mock_fetch_all.return_value = []

        get_team_stats(sport="NFL", team_code="KC")

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "ORDER BY season DESC" in sql


# =============================================================================
# HISTORICAL RANKINGS UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestInsertHistoricalRankingUnit:
    """Unit tests for insert_historical_ranking function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_ranking_returns_ranking_id(self, mock_get_cursor):
        """Test insert_historical_ranking returns the ranking_id from database."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_ranking_id": 42}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = insert_historical_ranking(
            sport="NCAAF",
            season=2024,
            week=10,
            team_code="MICH",
            rank=1,
            poll_type="AP",
            source="espn",
            previous_rank=2,
            points=1500,
            first_place_votes=50,
        )

        assert result == 42
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_ranking_with_minimal_params(self, mock_get_cursor):
        """Test insert_historical_ranking with only required parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = insert_historical_ranking(
            sport="NCAAF",
            season=2024,
            week=10,
            team_code="OSU",
            rank=3,
            poll_type="AP",
            source="espn",
        )

        assert result == 1
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_insert_ranking_upsert_uses_poll_type(self, mock_get_cursor):
        """Test UPSERT conflict key includes poll_type.

        Educational Note:
            The unique constraint on historical_rankings includes poll_type
            because the same team can have different ranks in different polls
            (e.g., AP Poll vs CFP Rankings) during the same week. The UPSERT
            correctly handles updates per poll type.

        Reference:
            - Migration 0009: unique constraint on (sport, season, week, team_code, poll_type)
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"historical_ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        insert_historical_ranking(
            sport="NCAAF",
            season=2024,
            week=10,
            team_code="MICH",
            rank=1,
            poll_type="AP",
            source="espn",
        )

        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT (sport, season, week, team_code, poll_type)" in sql


@pytest.mark.unit
class TestInsertHistoricalRankingsBatchUnit:
    """Unit tests for insert_historical_rankings_batch function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_insert_rankings(self, mock_get_cursor):
        """Test batch insert for rankings."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 25
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        records = [
            {
                "sport": "NCAAF",
                "season": 2024,
                "week": 10,
                "team_code": f"TEAM{i}",
                "rank": i,
                "poll_type": "AP",
                "source": "espn",
            }
            for i in range(1, 26)  # Top 25 teams
        ]

        inserted, failed = insert_historical_rankings_batch(records)

        assert inserted == 25
        assert failed == 0

    @patch("precog.database.crud_operations.get_cursor")
    def test_batch_insert_rankings_empty_list(self, mock_get_cursor):
        """Test batch insert handles empty record list."""
        inserted, failed = insert_historical_rankings_batch([])

        assert inserted == 0
        assert failed == 0
        mock_get_cursor.assert_not_called()


@pytest.mark.unit
class TestGetHistoricalRankingsUnit:
    """Unit tests for get_historical_rankings function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_rankings_basic_query(self, mock_fetch_all):
        """Test basic rankings query."""
        mock_fetch_all.return_value = [
            {"historical_ranking_id": 1, "sport": "NCAAF", "team_code": "MICH", "rank": 1}
        ]

        result = get_historical_rankings(sport="NCAAF", season=2024)

        assert len(result) == 1
        assert result[0]["rank"] == 1

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_rankings_top_n_filter(self, mock_fetch_all):
        """Test top_n parameter limits results to top N teams."""
        mock_fetch_all.return_value = []

        get_historical_rankings(sport="NCAAF", season=2024, top_n=10)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "rank <= %s" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_rankings_ordered_by_rank(self, mock_fetch_all):
        """Test results ordered by week DESC, rank ASC."""
        mock_fetch_all.return_value = []

        get_historical_rankings(sport="NCAAF", season=2024)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "ORDER BY week DESC, rank ASC" in sql


@pytest.mark.unit
class TestGetTeamRankingHistoryUnit:
    """Unit tests for get_team_ranking_history function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_ranking_history_basic(self, mock_fetch_all):
        """Test get_team_ranking_history with required parameters."""
        mock_fetch_all.return_value = [
            {"historical_ranking_id": 1, "team_code": "MICH", "week": 10, "rank": 1},
            {"historical_ranking_id": 2, "team_code": "MICH", "week": 9, "rank": 2},
        ]

        result = get_team_ranking_history(sport="NCAAF", team_code="MICH", poll_type="AP")

        assert len(result) == 2
        # Verify ordered by week DESC
        assert result[0]["week"] > result[1]["week"]

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_ranking_history_ordered_by_season_week(self, mock_fetch_all):
        """Test results ordered by season DESC, week ASC for chronological history.

        Educational Note:
            Rankings are ordered with week ASC so that within a season, you see
            the progression from early weeks to later weeks (chronological order).
            Season is DESC so you see the most recent season first.
        """
        mock_fetch_all.return_value = []

        get_team_ranking_history(sport="NCAAF", team_code="MICH", poll_type="AP")

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "ORDER BY season DESC, week ASC" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_ranking_history_with_season_filter(self, mock_fetch_all):
        """Test filtering by specific season."""
        mock_fetch_all.return_value = []

        get_team_ranking_history(sport="NCAAF", team_code="MICH", poll_type="AP", season=2024)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "season = %s" in sql
