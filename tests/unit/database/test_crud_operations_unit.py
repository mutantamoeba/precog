"""
Unit Tests for Phase 2C CRUD Operations (Venues, Game States, Team Rankings).

Tests the new ESPN data model CRUD functions with proper marker annotations.
All 8 test types per TESTING_STRATEGY V3.2.

Related:
- REQ-DATA-001: Game State Data Collection (SCD Type 2)
- REQ-DATA-002: Venue Data Management
- ADR-029: ESPN Data Model with Normalized Schema
- Pattern 1: Decimal Precision (NEVER USE FLOAT)
- Pattern 2: Dual Versioning System (SCD Type 2)

Usage:
    pytest tests/unit/database/test_phase2c_crud.py -v
    pytest tests/unit/database/test_phase2c_crud.py -v -m unit
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import psycopg2.errors
import pytest

# Import functions to test
from precog.database.crud_operations import (
    LEAGUE_SPORT_CATEGORY,
    TRACKED_SITUATION_KEYS,
    _fill_event_null_fields,
    build_event_result,
    check_event_fully_settled,
    create_game_state,
    create_team,
    create_team_ranking,
    create_venue,
    find_game_by_matchup,
    game_state_changed,
    get_current_game_state,
    get_current_rankings,
    get_game_state_history,
    get_games_by_date,
    get_live_games,
    get_or_create_event,
    get_or_create_game,
    get_team_by_espn_id,
    get_team_rankings,
    get_teams_with_kalshi_codes,
    get_venue_by_espn_id,
    get_venue_by_id,
    update_event,
    update_event_game_id,
    update_game_result,
    update_market_with_versioning,
    upsert_game_state,
)

# =============================================================================
# VENUE UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateVenueUnit:
    """Unit tests for create_venue function with mocked database."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_venue_returns_venue_id(self, mock_get_cursor):
        """Test create_venue returns the venue_id from database."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 42}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Execute
        result = create_venue(
            espn_venue_id="3622",
            venue_name="GEHA Field at Arrowhead Stadium",
            city="Kansas City",
            state="Missouri",
            capacity=76416,
            indoor=False,
        )

        # Verify
        assert result == 42
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_venue_with_minimal_params(self, mock_get_cursor):
        """Test create_venue with only required parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_venue(espn_venue_id="1234", venue_name="Test Stadium")

        assert result == 1
        # Verify SQL contains UPSERT pattern
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_venue_indoor_flag_default_false(self, mock_get_cursor):
        """Test indoor flag defaults to False."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_venue(espn_venue_id="1234", venue_name="Outdoor Stadium")

        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # indoor is the last parameter
        assert params[-1] is False

    @pytest.mark.parametrize(
        ("capacity_input", "expected_capacity"),
        [
            (50000, 50000),  # Normal capacity - unchanged
            (76416, 76416),  # Large NFL stadium - unchanged
            (0, None),  # ESPN returns 0 for unknown -> normalize to NULL
            (-1, None),  # Invalid negative -> normalize to NULL
            (-100, None),  # Large negative -> normalize to NULL
            (None, None),  # Explicit NULL -> stays NULL
        ],
        ids=[
            "normal_capacity",
            "large_stadium",
            "zero_capacity_normalized",
            "negative_one_normalized",
            "large_negative_normalized",
            "explicit_none",
        ],
    )
    @patch("precog.database.crud_operations.get_cursor")
    def test_create_venue_capacity_edge_cases(
        self, mock_get_cursor, capacity_input, expected_capacity
    ):
        """Test venue capacity normalization for API edge cases.

        Educational Note:
            ESPN API sometimes returns 0 for unknown venue capacity.
            Our DB constraint requires capacity > 0 OR capacity IS NULL.
            This normalization layer converts invalid values (0, negative)
            to NULL before database insertion to prevent constraint violations.

            This test covers Antipattern 2 from TESTING_ANTIPATTERNS_V1.0.md:
            "Not Testing API Edge Cases Against Database Constraints"

        Reference:
            - src/precog/database/crud_operations.py lines 1930-1933
            - docs/utility/TESTING_ANTIPATTERNS_V1.0.md Antipattern 2
        """
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"venue_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Execute
        result = create_venue(
            espn_venue_id="test_venue",
            venue_name="Test Stadium",
            capacity=capacity_input,
        )

        # Verify venue was created
        assert result == 1

        # Verify capacity was normalized correctly in SQL params
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # params order: (espn_venue_id, venue_name, city, state, capacity, indoor)
        actual_capacity = params[4]
        assert actual_capacity == expected_capacity, (
            f"Capacity {capacity_input} should normalize to {expected_capacity}, "
            f"got {actual_capacity}"
        )


@pytest.mark.unit
class TestGetVenueUnit:
    """Unit tests for venue retrieval functions."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_venue_by_espn_id_returns_dict(self, mock_fetch_one):
        """Test get_venue_by_espn_id returns venue dictionary."""
        mock_fetch_one.return_value = {
            "venue_id": 42,
            "espn_venue_id": "3622",
            "venue_name": "Arrowhead Stadium",
            "city": "Kansas City",
            "state": "Missouri",
            "capacity": 76416,
            "indoor": False,
        }

        result = get_venue_by_espn_id("3622")

        assert result is not None
        assert result["venue_id"] == 42
        assert result["venue_name"] == "Arrowhead Stadium"
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_venue_by_espn_id_not_found_returns_none(self, mock_fetch_one):
        """Test get_venue_by_espn_id returns None when not found."""
        mock_fetch_one.return_value = None

        result = get_venue_by_espn_id("nonexistent")

        assert result is None

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_venue_by_id_returns_dict(self, mock_fetch_one):
        """Test get_venue_by_id returns venue dictionary."""
        mock_fetch_one.return_value = {"venue_id": 42, "venue_name": "Test Stadium"}

        result = get_venue_by_id(42)

        assert result is not None
        assert result["venue_id"] == 42


# =============================================================================
# TEAM RANKING UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateTeamRankingUnit:
    """Unit tests for create_team_ranking function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_team_ranking_returns_ranking_id(self, mock_get_cursor):
        """Test create_team_ranking returns the ranking_id."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ranking_id": 100}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team_ranking(
            team_id=1,
            ranking_type="ap_poll",
            rank=3,
            season=2024,
            ranking_date=datetime(2024, 11, 17),
            week=12,
            points=1432,
            first_place_votes=12,
        )

        assert result == 100
        # Verify UPSERT SQL
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_team_ranking_with_minimal_params(self, mock_get_cursor):
        """Test create_team_ranking with only required parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"ranking_id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team_ranking(
            team_id=1,
            ranking_type="cfp",
            rank=1,
            season=2024,
            ranking_date=datetime(2024, 12, 1),
        )

        assert result == 1


@pytest.mark.unit
class TestGetTeamRankingsUnit:
    """Unit tests for team ranking retrieval functions."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_rankings_returns_list(self, mock_fetch_all):
        """Test get_team_rankings returns list of rankings."""
        mock_fetch_all.return_value = [
            {"ranking_id": 1, "rank": 3, "week": 12},
            {"ranking_id": 2, "rank": 5, "week": 11},
        ]

        result = get_team_rankings(team_id=1, ranking_type="ap_poll", season=2024)

        assert len(result) == 2
        assert result[0]["rank"] == 3
        mock_fetch_all.assert_called_once()

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_team_rankings_empty_list_when_none(self, mock_fetch_all):
        """Test get_team_rankings returns empty list when no rankings."""
        mock_fetch_all.return_value = []

        result = get_team_rankings(team_id=999)

        assert result == []

    @patch("precog.database.crud_operations.fetch_all")
    @patch("precog.database.crud_operations.fetch_one")
    def test_get_current_rankings_returns_ordered_list(self, mock_fetch_one, mock_fetch_all):
        """Test get_current_rankings returns rankings ordered by rank."""
        mock_fetch_one.return_value = {"max_week": 12}
        mock_fetch_all.return_value = [
            {"rank": 1, "team_id": 10, "points": 1500},
            {"rank": 2, "team_id": 20, "points": 1450},
            {"rank": 3, "team_id": 30, "points": 1400},
        ]

        result = get_current_rankings("ap_poll", 2024)

        assert len(result) == 3
        assert result[0]["rank"] == 1

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_current_rankings_no_week_returns_empty(self, mock_fetch_one):
        """Test get_current_rankings returns empty when no weeks exist."""
        mock_fetch_one.return_value = {"max_week": None}

        result = get_current_rankings("ap_poll", 2024)

        assert result == []


# =============================================================================
# GAME STATE UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateGameStateUnit:
    """Unit tests for create_game_state function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_game_state_returns_id(self, mock_get_cursor):
        """Test create_game_state returns surrogate id."""
        mock_cursor = MagicMock()
        # Note: RETURNING id returns "id" key (surrogate PK)
        mock_cursor.fetchone.return_value = {"id": 500}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_game_state(
            espn_event_id="401547417",
            home_team_id=1,
            away_team_id=2,
            venue_id=42,
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        assert result == 500

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_game_state_with_situation_jsonb(self, mock_get_cursor):
        """Test create_game_state serializes situation to JSONB."""
        mock_cursor = MagicMock()
        # Note: RETURNING id returns "id" key
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        situation = {"possession": "KC", "down": 2, "distance": 7, "yardLine": 35}

        create_game_state(espn_event_id="401547417", situation=situation, game_status="in_progress")

        # Verify JSON serialization in params
        # create_game_state makes 1 execute call: INSERT RETURNING id
        insert_call = mock_cursor.execute.call_args_list[0]
        params = insert_call[0][1]
        # situation is near the end of params
        assert '{"possession": "KC"' in str(params)

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_game_state_with_decimal_clock(self, mock_get_cursor):
        """Test create_game_state handles Decimal clock_seconds."""
        mock_cursor = MagicMock()
        # Note: RETURNING id returns "id" key
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_game_state(
            espn_event_id="401547417",
            clock_seconds=Decimal("332"),
            clock_display="5:32",
        )

        # create_game_state makes 1 execute call: INSERT RETURNING id
        insert_call = mock_cursor.execute.call_args_list[0]
        params = insert_call[0][1]
        # Verify Decimal is passed (not float)
        assert any(isinstance(p, Decimal) for p in params)

    @patch("precog.database.crud_operations.get_cursor")
    def test_create_game_state_passes_game_id(self, mock_get_cursor):
        """Test create_game_state passes game_id FK to INSERT."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        create_game_state(
            espn_event_id="401547417",
            game_status="pre",
            league="nfl",
            game_id=42,
        )

        insert_call = mock_cursor.execute.call_args_list[0]
        sql = insert_call[0][0]
        params = insert_call[0][1]
        # Verify game_id column is in the SQL
        assert "game_id" in sql
        # Verify game_id=42 is in the params (last before row_current_ind)
        assert 42 in params


@pytest.mark.unit
class TestGetGameStateUnit:
    """Unit tests for game state retrieval functions."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_current_game_state_returns_current(self, mock_fetch_one):
        """Test get_current_game_state returns current version only."""
        mock_fetch_one.return_value = {
            "id": 500,
            "espn_event_id": "401547417",
            "home_score": 14,
            "away_score": 7,
            "row_current_ind": True,
        }

        result = get_current_game_state("401547417")

        assert result is not None
        assert result["row_current_ind"] is True
        assert result["home_score"] == 14

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_current_game_state_not_found_returns_none(self, mock_fetch_one):
        """Test get_current_game_state returns None when not found."""
        mock_fetch_one.return_value = None

        result = get_current_game_state("nonexistent")

        assert result is None

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_game_state_history_returns_all_versions(self, mock_fetch_all):
        """Test get_game_state_history returns all versions."""
        mock_fetch_all.return_value = [
            {"id": 503, "home_score": 21, "row_current_ind": True},
            {"id": 502, "home_score": 14, "row_current_ind": False},
            {"id": 501, "home_score": 7, "row_current_ind": False},
        ]

        result = get_game_state_history("401547417")

        assert len(result) == 3
        assert result[0]["home_score"] == 21  # Most recent first

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_game_state_history_respects_limit(self, mock_fetch_all):
        """Test get_game_state_history respects limit parameter."""
        mock_fetch_all.return_value = [{"id": 1}]

        get_game_state_history("401547417", limit=5)

        call_args = mock_fetch_all.call_args
        params = call_args[0][1]
        assert params[-1] == 5  # Limit is last param


@pytest.mark.unit
class TestUpsertGameStateUnit:
    """Unit tests for upsert_game_state SCD Type 2 function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_game_state_closes_current_row(self, mock_get_cursor):
        """Test upsert_game_state closes current row before inserting.

        Educational Note:
            upsert_game_state makes 2 execute calls:
            1. close_query - SET row_current_ind = FALSE
            2. insert_query - INSERT new row RETURNING id
        """
        mock_cursor = MagicMock()
        # Mock fetchone to return id for RETURNING clause
        mock_cursor.fetchone.return_value = {"id": 100}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_game_state(
            espn_event_id="401547417",
            home_score=7,
            away_score=3,
            game_status="in_progress",
            skip_if_unchanged=False,  # Bypass state check to avoid DB call
        )

        # Verify close query was first execute call
        close_sql = mock_cursor.execute.call_args_list[0][0][0]  # First call, first positional arg
        assert "row_current_ind = FALSE" in close_sql
        assert "row_end_ts = NOW()" in close_sql
        assert result == 100


@pytest.mark.unit
class TestGetLiveGamesUnit:
    """Unit tests for get_live_games function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_live_games_filters_in_progress(self, mock_fetch_all):
        """Test get_live_games filters by in_progress status."""
        mock_fetch_all.return_value = [
            {"espn_event_id": "1", "game_status": "in_progress"},
            {"espn_event_id": "2", "game_status": "in_progress"},
        ]

        result = get_live_games()

        assert len(result) == 2
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "game_status = 'in_progress'" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_live_games_filters_by_league(self, mock_fetch_all):
        """Test get_live_games filters by league when provided."""
        mock_fetch_all.return_value = []

        get_live_games(league="nfl")

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "gs.league = %s" in sql
        assert "nfl" in params


@pytest.mark.unit
class TestGetGamesByDateUnit:
    """Unit tests for get_games_by_date function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_games_by_date_filters_by_date(self, mock_fetch_all):
        """Test get_games_by_date filters by date correctly."""
        mock_fetch_all.return_value = [
            {"espn_event_id": "1", "game_date": datetime(2024, 11, 28, 16, 30)}
        ]

        test_date = datetime(2024, 11, 28)
        result = get_games_by_date(test_date)

        assert len(result) == 1
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "DATE(gs.game_date) = DATE(%s)" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_games_by_date_filters_by_league(self, mock_fetch_all):
        """Test get_games_by_date filters by league when provided."""
        mock_fetch_all.return_value = []

        get_games_by_date(datetime(2024, 11, 28), league="nba")

        call_args = mock_fetch_all.call_args
        params = call_args[0][1]
        assert "nba" in params


# =============================================================================
# GAMES DIMENSION UNIT TESTS (Migration 0035)
# =============================================================================


@pytest.mark.unit
class TestGetOrCreateGameUnit:
    """Unit tests for get_or_create_game — games dimension upsert."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_or_create_game_returns_id(self, mock_get_cursor):
        """Test get_or_create_game returns the game id."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 42}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = get_or_create_game(
            sport="football",
            game_date=date(2024, 9, 8),
            home_team_code="KC",
            away_team_code="BAL",
            season=2024,
            league="nfl",
        )

        assert result == 42
        assert mock_cursor.execute.call_count == 1

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_or_create_game_derives_season_from_date(self, mock_get_cursor):
        """Test season is derived from game_date.year when not provided."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        get_or_create_game(
            sport="football",
            game_date=date(2025, 11, 15),
            home_team_code="KC",
            away_team_code="BAL",
            league="nfl",
        )

        # Check season param (5th positional param after sport, date, home, away)
        insert_call = mock_cursor.execute.call_args_list[0]
        params = insert_call[0][1]
        assert params[4] == 2025  # season derived from game_date.year

    def test_get_or_create_game_raises_if_league_missing(self):
        """Test ValueError raised when league is not provided (latent trap after Phase B)."""
        with pytest.raises(ValueError, match="league is required"):
            get_or_create_game(
                sport="football",
                game_date=date(2024, 10, 5),
                home_team_code="OSU",
                away_team_code="MICH",
            )

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_or_create_game_on_conflict_sql_has_case_guard(self, mock_get_cursor):
        """Test the ON CONFLICT clause has CASE guard for game_status.

        The CASE expression prevents regressing game_status from 'final'/'final_ot'
        back to an earlier status when the same game is upserted again.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        get_or_create_game(
            sport="football",
            game_date=date(2024, 9, 8),
            home_team_code="KC",
            away_team_code="BAL",
            league="nfl",
            game_status="scheduled",
        )

        # Verify the SQL contains the CASE guard
        insert_call = mock_cursor.execute.call_args_list[0]
        sql = insert_call[0][0]
        assert "CASE" in sql
        assert "final" in sql
        assert "final_ot" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_get_or_create_game_passes_all_fields(self, mock_get_cursor):
        """Test all optional fields are passed through to SQL."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 99}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = get_or_create_game(
            sport="football",
            game_date=date(2024, 9, 8),
            home_team_code="KC",
            away_team_code="BAL",
            season=2024,
            league="nfl",
            season_type="regular",
            week_number=1,
            home_team_id=10,
            away_team_id=20,
            venue_id=5,
            venue_name="Arrowhead Stadium",
            neutral_site=False,
            espn_event_id="401547417",
            game_status="pre",
            data_source="espn_poller",
        )

        assert result == 99
        insert_call = mock_cursor.execute.call_args_list[0]
        params = insert_call[0][1]
        # Verify key fields are in params
        assert "nfl" in params  # sport
        assert "KC" in params  # home_team_code
        assert "BAL" in params  # away_team_code
        assert "401547417" in params  # espn_event_id
        assert "espn_poller" in params  # data_source


@pytest.mark.unit
class TestUpdateGameResultUnit:
    """Unit tests for update_game_result — final score + derived fields."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_update_game_result_home_win(self, mock_get_cursor):
        """Test home win sets correct margin and result."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        update_game_result(game_id=42, home_score=27, away_score=20)

        call_args = mock_cursor.execute.call_args_list[0]
        params = call_args[0][1]
        assert params[0] == 27  # home_score
        assert params[1] == 20  # away_score
        assert params[2] == 7  # actual_margin (27-20)
        assert params[3] == "home_win"  # result
        assert params[4] == 42  # game_id

    @patch("precog.database.crud_operations.get_cursor")
    def test_update_game_result_away_win(self, mock_get_cursor):
        """Test away win sets correct margin and result."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        update_game_result(game_id=99, home_score=10, away_score=24)

        call_args = mock_cursor.execute.call_args_list[0]
        params = call_args[0][1]
        assert params[2] == -14  # actual_margin (10-24)
        assert params[3] == "away_win"

    @patch("precog.database.crud_operations.get_cursor")
    def test_update_game_result_draw(self, mock_get_cursor):
        """Test draw sets correct margin and result."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        update_game_result(game_id=1, home_score=17, away_score=17)

        call_args = mock_cursor.execute.call_args_list[0]
        params = call_args[0][1]
        assert params[2] == 0  # actual_margin
        assert params[3] == "draw"


# =============================================================================
# TEAM LOOKUP UNIT TESTS (Missing Teams Edge Cases)
# =============================================================================


@pytest.mark.unit
class TestGetTeamByEspnIdUnit:
    """Unit tests for get_team_by_espn_id with edge cases.

    Educational Note:
        This test class specifically addresses Antipattern 1 from
        TESTING_ANTIPATTERNS_V1.0.md: "Testing Against Empty/Unseeded Databases"

        The problem: Unit tests that mock database calls hide the fact that
        the teams table is empty in real databases. When ESPN returns data
        with valid team IDs, lookups fail silently (returning None).

        These tests explicitly cover the "team not found" scenarios to ensure
        the code handles missing teams gracefully without crashing.

    Reference:
        - docs/utility/TESTING_ANTIPATTERNS_V1.0.md Antipattern 1
        - src/precog/database/crud_operations.py get_team_by_espn_id
    """

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_team_by_espn_id_returns_team_dict(self, mock_fetch_one):
        """Test successful team lookup returns dictionary."""
        mock_fetch_one.return_value = {
            "team_id": 12,
            "espn_team_id": "22",
            "team_name": "Arizona Cardinals",
            "team_abbreviation": "ARI",
            "league": "nfl",
        }

        result = get_team_by_espn_id("22", league="nfl")

        assert result is not None
        assert result["team_id"] == 12
        assert result["team_name"] == "Arizona Cardinals"
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_team_by_espn_id_not_found_returns_none(self, mock_fetch_one):
        """Test team not found returns None gracefully.

        Educational Note:
            This is the critical edge case that was missing from tests.
            When teams table is empty or team doesn't exist, the function
            returns None. Callers must handle this case.
        """
        mock_fetch_one.return_value = None

        result = get_team_by_espn_id("99999", league="nfl")

        assert result is None

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_team_by_espn_id_wrong_league_returns_none(self, mock_fetch_one):
        """Test team exists but in wrong league returns None.

        Educational Note:
            A team might exist in the database (e.g., ESPN ID 22 for NFL),
            but if we query with the wrong league filter, no match is found.
        """
        mock_fetch_one.return_value = None  # No match for this league

        result = get_team_by_espn_id("22", league="nba")  # NFL team queried as NBA

        assert result is None

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_team_by_espn_id_without_league_filter(self, mock_fetch_one):
        """Test team lookup without league filter.

        Educational Note:
            When league is not specified, the query should still work
            but might return unexpected results if team IDs are not unique
            across leagues. This test ensures the function works without
            the league parameter.
        """
        mock_fetch_one.return_value = {
            "team_id": 42,
            "espn_team_id": "500",
            "team_name": "Generic Team",
            "league": "nfl",
        }

        result = get_team_by_espn_id("500")  # No league filter

        assert result is not None
        assert result["team_id"] == 42

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_team_by_espn_id_empty_string_handled(self, mock_fetch_one):
        """Test empty ESPN ID is handled gracefully."""
        mock_fetch_one.return_value = None

        result = get_team_by_espn_id("")

        assert result is None


# =============================================================================
# GAME STATE CHANGE DETECTION UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestGameStateChangedUnit:
    """Unit tests for game_state_changed function.

    Educational Note:
        The game_state_changed function determines if a game state has
        meaningfully changed to avoid creating duplicate SCD Type 2 rows.

        We intentionally DO NOT compare clock_seconds or clock_display because:
        - Clock changes every few seconds during play
        - This would create ~1000+ rows per game instead of ~50-100

        We DO compare:
        - home_score, away_score: Core game state
        - period: Quarter/half transitions
        - game_status: Pre/in_progress/halftime/final transitions
        - situation: Possession, down/distance changes (significant for NFL)

    Reference:
        - Issue #234: ESPNGamePoller for Live Game State Collection
        - REQ-DATA-001: Game State Data Collection (SCD Type 2)
    """

    def test_game_state_changed_no_current_state_returns_true(self):
        """Test that new game (no current state) always returns True."""

        result = game_state_changed(
            current=None,
            home_score=0,
            away_score=0,
            period=1,
            game_status="pre",
        )

        assert result is True

    def test_game_state_changed_same_state_returns_false(self):
        """Test that identical state returns False (no change)."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
        }

        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
        )

        assert result is False

    def test_game_state_changed_score_change_returns_true(self):
        """Test that score change is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
        }

        # Home team scores
        result = game_state_changed(
            current=current,
            home_score=21,  # Changed from 14 to 21
            away_score=7,
            period=2,
            game_status="in_progress",
        )

        assert result is True

    def test_game_state_changed_away_score_change_returns_true(self):
        """Test that away score change is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
        }

        # Away team scores
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=14,  # Changed from 7 to 14
            period=2,
            game_status="in_progress",
        )

        assert result is True

    def test_game_state_changed_period_change_returns_true(self):
        """Test that period change is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
        }

        # Quarter change
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=3,  # Changed from 2 to 3
            game_status="in_progress",
        )

        assert result is True

    def test_game_state_changed_status_change_returns_true(self):
        """Test that game status change is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
        }

        # Halftime
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="halftime",  # Changed from in_progress
        )

        assert result is True

    def test_game_state_changed_situation_possession_change_returns_true(self):
        """Test that possession change in situation is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "KC", "down": 1, "distance": 10},
        }

        # Possession change (turnover)
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={"possession": "DEN", "down": 1, "distance": 10},  # Changed
        )

        assert result is True

    def test_game_state_changed_situation_down_change_returns_true(self):
        """Test that down change in situation is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "KC", "down": 1, "distance": 10},
        }

        # Down change
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={"possession": "KC", "down": 2, "distance": 7},  # Changed
        )

        assert result is True

    def test_game_state_changed_situation_red_zone_change_returns_true(self):
        """Test that red zone change in situation is detected."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"is_red_zone": False},
        }

        # Entered red zone
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={"is_red_zone": True},  # Changed
        )

        assert result is True

    def test_game_state_changed_no_situation_change_returns_false(self):
        """Test that same situation returns False."""

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "KC", "down": 2, "distance": 7},
        }

        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={"possession": "KC", "down": 2, "distance": 7},  # Same
        )

        assert result is False

    def test_game_state_changed_new_situation_no_current_returns_true(self):
        """Test that new situation when current has none returns True."""

        current = {
            "home_score": 0,
            "away_score": 0,
            "period": 1,
            "game_status": "pre",
            "situation": None,
        }

        result = game_state_changed(
            current=current,
            home_score=0,
            away_score=0,
            period=1,
            game_status="in_progress",  # Status changed
            situation={"possession": "KC", "down": 1, "distance": 10},
        )

        assert result is True

    def test_game_state_changed_ignores_clock_seconds(self):
        """Test that clock_seconds changes are intentionally ignored.

        Educational Note:
            We explicitly DO NOT track clock_seconds changes because:
            - Clock changes every few seconds during live play
            - Tracking clock would create ~1000+ rows per game
            - Score, period, status, and situation capture meaningful state

            This test verifies the design decision from Issue #234.
        """

        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "clock_seconds": 845,  # This should be ignored
        }

        # Only clock changed - should return False (no meaningful change)
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            # clock_seconds is not a parameter of game_state_changed
        )

        assert result is False


@pytest.mark.unit
class TestGameStateChangedSportAwareUnit:
    """Unit tests for sport-aware situation filtering in game_state_changed.

    Educational Note:
        Different sports have different high-frequency situation fields that
        should NOT trigger SCD row creation. For example:
        - Basketball: foul counts change every few minutes
        - Hockey: shot counts change constantly
        Only sport-relevant keys (defined in TRACKED_SITUATION_KEYS) trigger
        new rows. Unknown leagues fall back to comparing ALL keys (safe default).

    Reference:
        - Issue #397: Game states SCD noise tuning
        - ESPNSituationData in api_connectors/espn_client.py
    """

    # --- Constants validation ---

    def test_tracked_situation_keys_has_all_sport_categories(self):
        """Verify TRACKED_SITUATION_KEYS covers football, basketball, hockey."""
        assert "football" in TRACKED_SITUATION_KEYS
        assert "basketball" in TRACKED_SITUATION_KEYS
        assert "hockey" in TRACKED_SITUATION_KEYS

    def test_league_sport_category_maps_all_leagues(self):
        """Verify LEAGUE_SPORT_CATEGORY maps all expected leagues."""
        expected = {"nfl", "ncaaf", "nba", "ncaab", "wnba", "ncaaw", "nhl", "mlb", "mls"}
        assert set(LEAGUE_SPORT_CATEGORY.keys()) == expected

    # --- Football (existing behavior preserved with league param) ---

    def test_football_down_change_triggers_with_league(self):
        """Football down change triggers new row when league='nfl'."""
        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "KC", "down": 1, "distance": 10},
        }
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={"possession": "KC", "down": 2, "distance": 7},
            league="nfl",
        )
        assert result is True

    def test_football_timeout_change_does_not_trigger(self):
        """Football timeout change does NOT trigger new row (not tracked)."""
        current = {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "KC", "down": 1, "distance": 10, "home_timeouts": 3},
        }
        result = game_state_changed(
            current=current,
            home_score=14,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation={"possession": "KC", "down": 1, "distance": 10, "home_timeouts": 2},
            league="ncaaf",
        )
        assert result is False

    # --- Basketball ---

    def test_basketball_foul_change_triggers(self):
        """Basketball foul count change triggers new row (useful for model training)."""
        current = {
            "home_score": 55,
            "away_score": 52,
            "period": 3,
            "game_status": "in_progress",
            "situation": {"possession": "home", "home_fouls": 3, "away_fouls": 2, "bonus": None},
        }
        result = game_state_changed(
            current=current,
            home_score=55,
            away_score=52,
            period=3,
            game_status="in_progress",
            situation={"possession": "home", "home_fouls": 4, "away_fouls": 2, "bonus": None},
            league="nba",
        )
        assert result is True

    def test_basketball_bonus_change_triggers(self):
        """Basketball bonus status change DOES trigger new row."""
        current = {
            "home_score": 55,
            "away_score": 52,
            "period": 3,
            "game_status": "in_progress",
            "situation": {"possession": "home", "bonus": None, "home_fouls": 4},
        }
        result = game_state_changed(
            current=current,
            home_score=55,
            away_score=52,
            period=3,
            game_status="in_progress",
            situation={"possession": "home", "bonus": "home", "home_fouls": 5},
            league="nba",
        )
        assert result is True

    def test_basketball_possession_arrow_change_triggers(self):
        """Basketball possession arrow change DOES trigger new row."""
        current = {
            "home_score": 40,
            "away_score": 38,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "home", "possession_arrow": "home"},
        }
        result = game_state_changed(
            current=current,
            home_score=40,
            away_score=38,
            period=2,
            game_status="in_progress",
            situation={"possession": "home", "possession_arrow": "away"},
            league="ncaab",
        )
        assert result is True

    def test_basketball_possession_change_triggers(self):
        """Basketball possession change DOES trigger new row."""
        current = {
            "home_score": 55,
            "away_score": 52,
            "period": 3,
            "game_status": "in_progress",
            "situation": {"possession": "home", "home_fouls": 3},
        }
        result = game_state_changed(
            current=current,
            home_score=55,
            away_score=52,
            period=3,
            game_status="in_progress",
            situation={"possession": "away", "home_fouls": 3},
            league="nba",
        )
        assert result is True

    def test_basketball_wnba_uses_basketball_keys(self):
        """WNBA uses basketball sport category keys."""
        current = {
            "home_score": 30,
            "away_score": 28,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"possession": "home", "home_timeouts": 3},
        }
        # Only timeouts changed - should NOT trigger (timeouts are noise)
        result = game_state_changed(
            current=current,
            home_score=30,
            away_score=28,
            period=2,
            game_status="in_progress",
            situation={"possession": "home", "home_timeouts": 2},
            league="wnba",
        )
        assert result is False

    # --- Hockey ---

    def test_hockey_shot_change_does_not_trigger(self):
        """Hockey shot count change does NOT trigger new row."""
        current = {
            "home_score": 2,
            "away_score": 1,
            "period": 2,
            "game_status": "in_progress",
            "situation": {
                "home_shots": 15,
                "away_shots": 12,
                "home_powerplay": False,
                "away_powerplay": False,
            },
        }
        result = game_state_changed(
            current=current,
            home_score=2,
            away_score=1,
            period=2,
            game_status="in_progress",
            situation={
                "home_shots": 18,
                "away_shots": 14,
                "home_powerplay": False,
                "away_powerplay": False,
            },
            league="nhl",
        )
        assert result is False

    def test_hockey_powerplay_change_triggers(self):
        """Hockey power play change DOES trigger new row."""
        current = {
            "home_score": 2,
            "away_score": 1,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"home_powerplay": False, "away_powerplay": False, "home_shots": 15},
        }
        result = game_state_changed(
            current=current,
            home_score=2,
            away_score=1,
            period=2,
            game_status="in_progress",
            situation={"home_powerplay": True, "away_powerplay": False, "home_shots": 16},
            league="nhl",
        )
        assert result is True

    def test_hockey_away_powerplay_change_triggers(self):
        """Hockey away power play change DOES trigger new row."""
        current = {
            "home_score": 2,
            "away_score": 1,
            "period": 2,
            "game_status": "in_progress",
            "situation": {"home_powerplay": False, "away_powerplay": False},
        }
        result = game_state_changed(
            current=current,
            home_score=2,
            away_score=1,
            period=2,
            game_status="in_progress",
            situation={"home_powerplay": False, "away_powerplay": True},
            league="nhl",
        )
        assert result is True

    # --- Fallback behavior ---

    def test_unknown_league_falls_back_to_full_comparison(self):
        """Unknown league compares ALL situation keys (safe fallback)."""
        current = {
            "home_score": 10,
            "away_score": 8,
            "period": 1,
            "game_status": "in_progress",
            "situation": {"some_field": "a", "other_field": "b"},
        }
        # Changing any field should trigger with unknown league
        result = game_state_changed(
            current=current,
            home_score=10,
            away_score=8,
            period=1,
            game_status="in_progress",
            situation={"some_field": "a", "other_field": "c"},
            league="cricket",
        )
        assert result is True

    def test_unknown_league_same_situation_returns_false(self):
        """Unknown league with same situation returns False."""
        current = {
            "home_score": 10,
            "away_score": 8,
            "period": 1,
            "game_status": "in_progress",
            "situation": {"some_field": "a"},
        }
        result = game_state_changed(
            current=current,
            home_score=10,
            away_score=8,
            period=1,
            game_status="in_progress",
            situation={"some_field": "a"},
            league="cricket",
        )
        assert result is False

    def test_none_league_falls_back_to_full_comparison(self):
        """league=None compares ALL situation keys (safe fallback)."""
        current = {
            "home_score": 10,
            "away_score": 8,
            "period": 1,
            "game_status": "in_progress",
            "situation": {"arbitrary_key": "value1"},
        }
        result = game_state_changed(
            current=current,
            home_score=10,
            away_score=8,
            period=1,
            game_status="in_progress",
            situation={"arbitrary_key": "value2"},
            league=None,
        )
        assert result is True

    def test_none_league_detects_new_keys_in_situation(self):
        """league=None detects keys present in new but not current situation."""
        current = {
            "home_score": 10,
            "away_score": 8,
            "period": 1,
            "game_status": "in_progress",
            "situation": {},
        }
        result = game_state_changed(
            current=current,
            home_score=10,
            away_score=8,
            period=1,
            game_status="in_progress",
            situation={"new_key": "value"},
            league=None,
        )
        assert result is True

    def test_league_case_insensitive(self):
        """League lookup is case-insensitive."""
        current = {
            "home_score": 55,
            "away_score": 52,
            "period": 3,
            "game_status": "in_progress",
            "situation": {"possession": "home", "home_timeouts": 4},
        }
        # Only timeouts changed with uppercase league - should NOT trigger
        result = game_state_changed(
            current=current,
            home_score=55,
            away_score=52,
            period=3,
            game_status="in_progress",
            situation={"possession": "home", "home_timeouts": 3},
            league="NBA",
        )
        assert result is False


# =============================================================================
# SCHEDULER STATUS UNIT TESTS (IPC via Database)
# =============================================================================
# Tests for the scheduler status CRUD operations that enable cross-process
# communication for the `scheduler status` CLI command.
#
# References:
#   - Migration 0012: scheduler_status table
#   - Issue #255: Scheduler status shows "not running" even when running
#   - REQ-OBSERV-001: Observability Requirements
# =============================================================================


@pytest.mark.unit
class TestUpsertSchedulerStatusUnit:
    """Unit tests for upsert_scheduler_status function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_scheduler_status_minimal_params(self, mock_get_cursor):
        """Test upsert with only required parameters (host_id, service_name)."""
        from precog.database.crud_operations import upsert_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_scheduler_status(
            host_id="DESKTOP-TEST",
            service_name="espn",
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        # Verify SQL contains UPSERT pattern
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO scheduler_status" in sql
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_scheduler_status_all_params(self, mock_get_cursor):
        """Test upsert with all parameters.

        Educational Note:
            This tests the full scheduler status update including:
            - status: Service state transition
            - pid: Process ID for monitoring
            - started_at: Service start timestamp
            - stats: JSON metrics (polls, errors, etc.)
            - config: JSON configuration
            - error_message: For failed status
        """
        from precog.database.crud_operations import upsert_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_scheduler_status(
            host_id="DESKTOP-TEST",
            service_name="espn",
            status="running",
            pid=12345,
            started_at=datetime(2024, 12, 24, 10, 0, 0),
            stats={"polls": 100, "errors": 0},
            config={"poll_interval": 60},
            error_message=None,
        )

        assert result is True
        # Verify all columns are in the INSERT
        sql = mock_cursor.execute.call_args[0][0]
        assert "status" in sql
        assert "pid" in sql
        assert "started_at" in sql
        assert "stats" in sql
        assert "config" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_upsert_scheduler_status_with_error(self, mock_get_cursor):
        """Test upsert with error message for failed status."""
        from precog.database.crud_operations import upsert_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = upsert_scheduler_status(
            host_id="DESKTOP-TEST",
            service_name="kalshi_rest",
            status="failed",
            error_message="Connection timeout after 30s",
        )

        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "failed" in params
        assert "Connection timeout after 30s" in params


@pytest.mark.unit
class TestGetSchedulerStatusUnit:
    """Unit tests for get_scheduler_status function."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_scheduler_status_found(self, mock_fetch_one):
        """Test get_scheduler_status returns service status when found."""
        from precog.database.crud_operations import get_scheduler_status

        mock_fetch_one.return_value = {
            "host_id": "DESKTOP-TEST",
            "service_name": "espn",
            "status": "running",
            "pid": 12345,
            "last_heartbeat": datetime(2024, 12, 24, 10, 5, 0),
            "stats": {"polls": 50},
            "config": {"poll_interval": 60},
        }

        result = get_scheduler_status("DESKTOP-TEST", "espn")

        assert result is not None
        assert result["status"] == "running"
        assert result["pid"] == 12345
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_scheduler_status_not_found(self, mock_fetch_one):
        """Test get_scheduler_status returns None when service not found."""
        from precog.database.crud_operations import get_scheduler_status

        mock_fetch_one.return_value = None

        result = get_scheduler_status("NONEXISTENT-HOST", "unknown_service")

        assert result is None


@pytest.mark.unit
class TestListSchedulerServicesUnit:
    """Unit tests for list_scheduler_services function."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_list_scheduler_services_all(self, mock_fetch_all):
        """Test listing all scheduler services."""
        from precog.database.crud_operations import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running"},
            {"host_id": "HOST-1", "service_name": "kalshi_rest", "status": "stopped"},
            {"host_id": "HOST-2", "service_name": "espn", "status": "running"},
        ]

        result = list_scheduler_services()

        assert len(result) == 3
        assert result[0]["service_name"] == "espn"

    @patch("precog.database.crud_operations.fetch_all")
    def test_list_scheduler_services_by_host(self, mock_fetch_all):
        """Test filtering services by host_id."""
        from precog.database.crud_operations import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running"},
            {"host_id": "HOST-1", "service_name": "kalshi_rest", "status": "stopped"},
        ]

        result = list_scheduler_services(host_id="HOST-1")

        assert len(result) == 2
        # Verify host_id filter was applied
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "host_id = %s" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_list_scheduler_services_by_status(self, mock_fetch_all):
        """Test filtering services by status."""
        from precog.database.crud_operations import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running"},
        ]

        result = list_scheduler_services(status_filter="running")

        assert len(result) == 1
        # Verify status filter was applied
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "status = %s" in sql

    @patch("precog.database.crud_operations.fetch_all")
    def test_list_scheduler_services_includes_stale_detection(self, mock_fetch_all):
        """Test that is_stale field is included when requested.

        Educational Note:
            The is_stale field helps detect crashed services. If a service
            status is 'running' but last_heartbeat is >2 minutes old, the
            service likely crashed without graceful shutdown.
        """
        from precog.database.crud_operations import list_scheduler_services

        mock_fetch_all.return_value = [
            {"host_id": "HOST-1", "service_name": "espn", "status": "running", "is_stale": False},
        ]

        result = list_scheduler_services(include_stale=True, stale_threshold_seconds=120)

        # Verify stale detection is in the query
        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        assert "is_stale" in sql
        # Verify result contains the expected service
        assert len(result) == 1
        assert result[0]["host_id"] == "HOST-1"


@pytest.mark.unit
class TestCleanupStaleSchedulersUnit:
    """Unit tests for cleanup_stale_schedulers function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_cleanup_stale_schedulers_marks_as_failed(self, mock_get_cursor):
        """Test that stale services are marked as failed."""
        from precog.database.crud_operations import cleanup_stale_schedulers

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2  # 2 stale services cleaned up
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = cleanup_stale_schedulers(stale_threshold_seconds=120)

        assert result == 2
        # Verify SQL updates status to 'failed'
        sql = mock_cursor.execute.call_args[0][0]
        assert "SET status = 'failed'" in sql
        assert "IN ('running', 'starting')" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_cleanup_stale_schedulers_by_host(self, mock_get_cursor):
        """Test cleanup only affects specified host."""
        from precog.database.crud_operations import cleanup_stale_schedulers

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = cleanup_stale_schedulers(
            stale_threshold_seconds=120,
            host_id="DESKTOP-TEST",
        )

        assert result == 1
        # Verify host_id filter was applied
        sql = mock_cursor.execute.call_args[0][0]
        assert "host_id = %s" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_cleanup_stale_schedulers_no_stale_services(self, mock_get_cursor):
        """Test cleanup when no stale services exist."""
        from precog.database.crud_operations import cleanup_stale_schedulers

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No stale services
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = cleanup_stale_schedulers(stale_threshold_seconds=120)

        assert result == 0


@pytest.mark.unit
class TestDeleteSchedulerStatusUnit:
    """Unit tests for delete_scheduler_status function."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_delete_scheduler_status_found(self, mock_get_cursor):
        """Test delete returns True when record found and deleted."""
        from precog.database.crud_operations import delete_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = delete_scheduler_status("DESKTOP-TEST", "old_service")

        assert result is True
        # Verify DELETE SQL
        sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM scheduler_status" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_delete_scheduler_status_not_found(self, mock_get_cursor):
        """Test delete returns False when record not found."""
        from precog.database.crud_operations import delete_scheduler_status

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No record deleted
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = delete_scheduler_status("NONEXISTENT-HOST", "unknown_service")

        assert result is False


# =============================================================================
# FIND GAME BY MATCHUP UNIT TESTS (Issue #462)
# =============================================================================


@pytest.mark.unit
class TestFindGameByMatchupUnit:
    """Unit tests for find_game_by_matchup — league-to-sport mapping + game lookup."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_nfl_maps_to_football(self, mock_fetch_one):
        """NFL league maps to 'football' sport in query."""
        mock_fetch_one.return_value = {"id": 42}

        result = find_game_by_matchup(
            league="nfl",
            game_date=date(2026, 1, 18),
            home_team_code="NE",
            away_team_code="HOU",
        )

        assert result == 42
        # Verify the sport param passed to query is "football"
        call_args = mock_fetch_one.call_args[0]
        params = call_args[1]
        assert params[0] == "football"

    @patch("precog.database.crud_operations.fetch_one")
    def test_nba_maps_to_basketball(self, mock_fetch_one):
        """NBA league maps to 'basketball' sport in query."""
        mock_fetch_one.return_value = {"id": 99}

        result = find_game_by_matchup(
            league="nba",
            game_date=date(2026, 3, 25),
            home_team_code="BOS",
            away_team_code="OKC",
        )

        assert result == 99
        call_args = mock_fetch_one.call_args[0]
        params = call_args[1]
        assert params[0] == "basketball"

    @patch("precog.database.crud_operations.fetch_one")
    def test_ncaaf_maps_to_football(self, mock_fetch_one):
        """NCAAF league maps to 'football' sport."""
        mock_fetch_one.return_value = {"id": 7}

        result = find_game_by_matchup(
            league="ncaaf",
            game_date=date(2026, 1, 2),
            home_team_code="MSST",
            away_team_code="WAKE",
        )

        assert result == 7
        call_args = mock_fetch_one.call_args[0]
        params = call_args[1]
        assert params[0] == "football"

    @patch("precog.database.crud_operations.fetch_one")
    def test_nhl_maps_to_hockey(self, mock_fetch_one):
        """NHL league maps to 'hockey' sport."""
        mock_fetch_one.return_value = {"id": 55}

        result = find_game_by_matchup(
            league="nhl",
            game_date=date(2026, 1, 15),
            home_team_code="TOR",
            away_team_code="BOS",
        )

        assert result == 55
        call_args = mock_fetch_one.call_args[0]
        params = call_args[1]
        assert params[0] == "hockey"

    @patch("precog.database.crud_operations.fetch_all")
    @patch("precog.database.crud_operations.fetch_one")
    def test_returns_none_when_no_match(self, mock_fetch_one, mock_fetch_all):
        """Returns None when no exact or fuzzy match found."""
        mock_fetch_one.return_value = None
        mock_fetch_all.return_value = []

        result = find_game_by_matchup(
            league="nfl",
            game_date=date(2026, 1, 18),
            home_team_code="NE",
            away_team_code="HOU",
        )

        assert result is None
        mock_fetch_one.assert_called_once()
        mock_fetch_all.assert_called_once()

    @patch("precog.database.crud_operations.fetch_all")
    @patch("precog.database.crud_operations.fetch_one")
    def test_fuzzy_match_finds_game_on_adjacent_day(self, mock_fetch_one, mock_fetch_all):
        """When exact date misses, +/-1 day window finds the game."""
        mock_fetch_one.return_value = None  # Exact date: no match
        mock_fetch_all.return_value = [{"id": 77, "game_date": date(2026, 1, 19)}]

        result = find_game_by_matchup(
            league="nfl",
            game_date=date(2026, 1, 18),
            home_team_code="NE",
            away_team_code="HOU",
        )

        assert result == 77
        # Verify fuzzy query uses correct date window
        fuzzy_params = mock_fetch_all.call_args[0][1]
        assert fuzzy_params[1] == date(2026, 1, 17)  # day before
        assert fuzzy_params[2] == date(2026, 1, 19)  # day after

    @patch("precog.database.crud_operations.fetch_all")
    @patch("precog.database.crud_operations.fetch_one")
    def test_fuzzy_match_returns_none_on_ambiguity(self, mock_fetch_one, mock_fetch_all):
        """When +/-1 day returns multiple games, returns None (ambiguous)."""
        mock_fetch_one.return_value = None
        mock_fetch_all.return_value = [
            {"id": 77, "game_date": date(2026, 1, 17)},
            {"id": 78, "game_date": date(2026, 1, 19)},
        ]

        result = find_game_by_matchup(
            league="nfl",
            game_date=date(2026, 1, 18),
            home_team_code="NE",
            away_team_code="HOU",
        )

        assert result is None

    @patch("precog.database.crud_operations.fetch_one")
    def test_exact_match_skips_fuzzy(self, mock_fetch_one):
        """When exact date matches, fuzzy query is never called."""
        mock_fetch_one.return_value = {"id": 42}

        result = find_game_by_matchup(
            league="nfl",
            game_date=date(2026, 1, 18),
            home_team_code="NE",
            away_team_code="HOU",
        )

        assert result == 42
        # fetch_all should NOT have been called (exact match found)
        mock_fetch_one.assert_called_once()

    def test_returns_none_for_unknown_league(self):
        """Returns None for league not in LEAGUE_SPORT_CATEGORY (no DB call)."""
        result = find_game_by_matchup(
            league="xyz_unknown",
            game_date=date(2026, 1, 18),
            home_team_code="NE",
            away_team_code="HOU",
        )

        assert result is None

    @patch("precog.database.crud_operations.fetch_one")
    def test_passes_all_params_to_query(self, mock_fetch_one):
        """Verify game_date, home_team_code, away_team_code all passed."""
        mock_fetch_one.return_value = {"id": 1}
        target_date = date(2026, 2, 14)

        find_game_by_matchup(
            league="nba",
            game_date=target_date,
            home_team_code="LAL",
            away_team_code="GSW",
        )

        call_args = mock_fetch_one.call_args[0]
        params = call_args[1]
        assert params == ("basketball", target_date, "LAL", "GSW")


# =============================================================================
# GET TEAMS WITH KALSHI CODES UNIT TESTS (Issue #462)
# =============================================================================


@pytest.mark.unit
class TestGetTeamsWithKalshiCodesUnit:
    """Unit tests for get_teams_with_kalshi_codes — team registry data source."""

    @patch("precog.database.crud_operations.fetch_all")
    def test_returns_list_of_team_dicts(self, mock_fetch_all):
        """Returns list of team dicts with expected keys."""
        mock_fetch_all.return_value = [
            {"team_id": 1, "team_code": "HOU", "league": "nfl", "kalshi_team_code": None},
            {"team_id": 2, "team_code": "JAX", "league": "nfl", "kalshi_team_code": "JAC"},
        ]

        result = get_teams_with_kalshi_codes(league="nfl")

        assert len(result) == 2
        assert result[0]["team_code"] == "HOU"
        assert result[1]["kalshi_team_code"] == "JAC"

    @patch("precog.database.crud_operations.fetch_all")
    def test_filters_by_league(self, mock_fetch_all):
        """When league is provided, passes it as query param."""
        mock_fetch_all.return_value = []

        get_teams_with_kalshi_codes(league="nba")

        call_args = mock_fetch_all.call_args[0]
        # Query should contain WHERE league = %s
        sql = call_args[0]
        assert "WHERE league" in sql
        params = call_args[1]
        assert params == ("nba",)

    @patch("precog.database.crud_operations.fetch_all")
    def test_returns_all_when_league_none(self, mock_fetch_all):
        """When league is None, returns all teams (no WHERE clause on league)."""
        mock_fetch_all.return_value = [
            {"team_id": 1, "team_code": "HOU", "league": "nfl", "kalshi_team_code": None},
            {"team_id": 3, "team_code": "BOS", "league": "nba", "kalshi_team_code": None},
        ]

        result = get_teams_with_kalshi_codes(league=None)

        assert len(result) == 2
        call_args = mock_fetch_all.call_args[0]
        sql = call_args[0]
        assert "WHERE league" not in sql


# =============================================================================
# UPDATE EVENT GAME ID UNIT TESTS (Issue #462)
# =============================================================================


@pytest.mark.unit
class TestUpdateEventGameIdUnit:
    """Unit tests for update_event_game_id — linking events to games."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_returns_true_when_updated(self, mock_get_cursor):
        """Returns True when event was found and updated."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event_game_id(event_internal_id=42, game_id=15)

        assert result is True
        mock_cursor.execute.assert_called_once()
        # Verify params include game_id and event_internal_id
        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]
        assert 15 in params  # game_id
        assert 42 in params  # event_internal_id

    @patch("precog.database.crud_operations.get_cursor")
    def test_returns_false_when_no_event_found(self, mock_get_cursor):
        """Returns False when no event matched (rowcount=0)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event_game_id(event_internal_id=999, game_id=15)

        assert result is False


# =============================================================================
# UPDATE EVENT UNIT TESTS (general-purpose)
# =============================================================================


@pytest.mark.unit
class TestUpdateEventUnit:
    """Unit tests for update_event — general-purpose event field updater."""

    @patch("precog.database.crud_operations.get_cursor")
    def test_basic_status_update(self, mock_get_cursor):
        """Single-field update (status) executes correct SQL."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(42, status="final")

        assert result is True
        mock_cursor.execute.assert_called_once()
        query, params = mock_cursor.execute.call_args[0]
        assert "status = %s" in query
        assert "updated_at = NOW()" in query
        assert "final" in params
        assert 42 in params  # event_internal_id in WHERE clause

    @patch("precog.database.crud_operations.get_cursor")
    def test_partial_update_multiple_fields(self, mock_get_cursor):
        """Update start_time and end_time together, leaving other fields untouched."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(
            7,
            start_time="2025-12-01T12:00:00Z",
            end_time="2025-12-01T23:59:00Z",
        )

        assert result is True
        query, _params = mock_cursor.execute.call_args[0]
        assert "start_time = %s" in query
        assert "end_time = %s" in query
        # status, result, description should NOT appear
        assert "status = %s" not in query
        assert "result = %s" not in query
        assert "description = %s" not in query

    @patch("precog.database.crud_operations.get_cursor")
    def test_returns_false_when_event_not_found(self, mock_get_cursor):
        """Returns False when no row matches the event_internal_id."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(999, status="live")

        assert result is False

    def test_invalid_status_raises_value_error(self):
        """Invalid status value raises ValueError before touching the DB."""
        with pytest.raises(ValueError, match="Invalid event status 'bogus'"):
            update_event(42, status="bogus")

    def test_all_none_returns_false(self):
        """Calling with no fields to update returns False without DB call."""
        # No DB mock needed — should short-circuit before get_cursor()
        result = update_event(42)
        assert result is False

    @patch("precog.database.crud_operations.get_cursor")
    def test_result_serialized_as_json(self, mock_get_cursor):
        """result dict is JSON-serialized (matching create_event metadata pattern)."""
        import json

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result_dict = {"winner": "yes", "settlement_value": "1.0000"}
        update_event(42, result=result_dict)

        query, params = mock_cursor.execute.call_args[0]
        assert "result = %s" in query
        # The result should be a JSON string, not a dict
        json_param = params[0]  # result is first non-None field
        assert isinstance(json_param, str)
        assert json.loads(json_param) == result_dict

    @patch("precog.database.crud_operations.get_cursor")
    def test_description_update(self, mock_get_cursor):
        """Description field can be updated."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(42, description="Updated event description")

        assert result is True
        query, params = mock_cursor.execute.call_args[0]
        assert "description = %s" in query
        assert "Updated event description" in params

    @patch("precog.database.crud_operations.get_cursor")
    def test_all_fields_together(self, mock_get_cursor):
        """All five fields can be updated in a single call."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = update_event(
            42,
            start_time="2025-12-01T12:00:00Z",
            end_time="2025-12-01T23:59:00Z",
            status="final",
            result={"winner": "yes"},
            description="Settled",
        )

        assert result is True
        query, _params = mock_cursor.execute.call_args[0]
        assert "start_time = %s" in query
        assert "end_time = %s" in query
        assert "status = %s" in query
        assert "result = %s" in query
        assert "description = %s" in query
        assert "updated_at = NOW()" in query

    def test_valid_statuses_accepted(self):
        """All five valid statuses pass validation (ValueError not raised)."""
        valid = ["scheduled", "live", "final", "cancelled", "postponed"]
        for s in valid:
            # Should NOT raise — we don't care about the DB call,
            # just that validation passes. Use mock to avoid actual DB.
            with patch("precog.database.crud_operations.get_cursor") as mock_gc:
                mock_cursor = MagicMock()
                mock_cursor.rowcount = 0
                mock_gc.return_value.__enter__ = MagicMock(return_value=mock_cursor)
                mock_gc.return_value.__exit__ = MagicMock(return_value=False)
                # Should not raise ValueError
                update_event(1, status=s)


# =============================================================================
# CREATE TEAM UNIT TESTS
# =============================================================================


@pytest.mark.unit
class TestCreateTeamUnit:
    """Unit tests for create_team function.

    Key behavior: when espn_team_id is provided and Step 1 (ESPN ID lookup)
    finds no match, the code fallback (Step 2) must NOT fire. This prevents
    college sports code collisions (e.g., two 'MISS' teams in NCAAF) from
    silently losing ~61 teams per restart.
    """

    @patch("precog.database.crud_operations.fetch_one")
    def test_returns_existing_team_by_espn_id(self, mock_fetch_one):
        """Step 1: ESPN ID lookup finds existing team -> return its team_id."""
        mock_fetch_one.return_value = {"team_id": 42}

        result = create_team(
            team_code="MISS",
            team_name="Ole Miss Rebels",
            display_name="Ole Miss",
            sport="football",
            league="ncaaf",
            espn_team_id="145",
        )

        assert result == 42
        # Only one fetch_one call (ESPN ID lookup)
        mock_fetch_one.assert_called_once()
        call_args = mock_fetch_one.call_args[0]
        assert "espn_team_id" in call_args[0]

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.fetch_one")
    def test_skips_code_fallback_when_espn_id_provided(self, mock_fetch_one, mock_get_cursor):
        """When espn_team_id is provided and Step 1 finds no match, skip Step 2
        and go straight to INSERT. This is THE critical fix for #486."""
        # Step 1: ESPN ID lookup returns no match
        mock_fetch_one.return_value = None

        # Step 3: INSERT succeeds
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"team_id": 99}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team(
            team_code="MISS",
            team_name="Mississippi State Bulldogs",
            display_name="Mississippi St",
            sport="football",
            league="ncaaf",
            espn_team_id="344",
        )

        assert result == 99
        # fetch_one called exactly ONCE (ESPN ID lookup only, NOT code fallback)
        mock_fetch_one.assert_called_once()
        call_args = mock_fetch_one.call_args[0]
        assert "espn_team_id" in call_args[0]
        # INSERT was executed
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.fetch_one")
    def test_uses_code_fallback_when_no_espn_id(self, mock_fetch_one, mock_get_cursor):
        """When espn_team_id is None, Step 2 code fallback fires normally.
        This preserves backward compatibility for non-ESPN data sources."""
        # Step 2: code lookup finds existing team
        mock_fetch_one.return_value = {"team_id": 50}

        result = create_team(
            team_code="KC",
            team_name="Kansas City Chiefs",
            display_name="Chiefs",
            sport="football",
            league="nfl",
            espn_team_id=None,  # No ESPN ID
        )

        assert result == 50
        # fetch_one called once (code fallback — Step 1 was skipped)
        mock_fetch_one.assert_called_once()
        call_args = mock_fetch_one.call_args[0]
        assert "team_code" in call_args[0]

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.fetch_one")
    def test_inserts_new_team_when_no_espn_id_and_no_code_match(
        self, mock_fetch_one, mock_get_cursor
    ):
        """When espn_team_id is None and code lookup finds nothing, INSERT."""
        # Step 2: code lookup finds nothing
        mock_fetch_one.return_value = None

        # Step 3: INSERT succeeds
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"team_id": 77}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team(
            team_code="NEW",
            team_name="New Team",
            display_name="New",
            sport="football",
            league="nfl",
        )

        assert result == 77
        mock_cursor.execute.assert_called_once()

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.fetch_one")
    def test_insert_includes_all_fields(self, mock_fetch_one, mock_get_cursor):
        """Verify INSERT passes all 9 columns including espn_team_id."""
        mock_fetch_one.return_value = None  # Step 1: no match

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"team_id": 101}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team(
            team_code="ALA",
            team_name="Alabama Crimson Tide",
            display_name="Alabama",
            sport="football",
            league="ncaaf",
            espn_team_id="333",
            current_elo_rating=None,
            conference="SEC",
            division="West",
        )

        assert result == 101
        call_args = mock_cursor.execute.call_args[0]
        sql = call_args[0]
        params = call_args[1]
        assert "INSERT INTO teams" in sql
        assert "RETURNING team_id" in sql
        # Verify all 9 params are passed in correct order
        assert params == (
            "ALA",
            "Alabama Crimson Tide",
            "Alabama",
            "football",
            "ncaaf",
            "333",
            None,
            "SEC",
            "West",
        )

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.fetch_one")
    def test_collision_scenario_two_teams_same_code(self, mock_fetch_one, mock_get_cursor):
        """Simulate the exact NCAAF collision: two different ESPN teams with
        code 'MISS' in the same league. First call creates Ole Miss (espn_id=145),
        second call must NOT match it — must create Mississippi State (espn_id=344)."""
        # --- Call 1: Ole Miss (espn_id=145) is brand new ---
        mock_fetch_one.return_value = None  # ESPN lookup: not found

        mock_cursor_1 = MagicMock()
        mock_cursor_1.fetchone.return_value = {"team_id": 200}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor_1)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result_1 = create_team(
            team_code="MISS",
            team_name="Ole Miss Rebels",
            display_name="Ole Miss",
            sport="football",
            league="ncaaf",
            espn_team_id="145",
        )
        assert result_1 == 200

        # --- Call 2: Mississippi State (espn_id=344) is also new ---
        mock_fetch_one.reset_mock()
        mock_get_cursor.reset_mock()
        mock_fetch_one.return_value = None  # ESPN lookup: not found

        mock_cursor_2 = MagicMock()
        mock_cursor_2.fetchone.return_value = {"team_id": 201}
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor_2)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result_2 = create_team(
            team_code="MISS",
            team_name="Mississippi State Bulldogs",
            display_name="Mississippi St",
            sport="football",
            league="ncaaf",
            espn_team_id="344",
        )

        # CRITICAL: second call must get a DIFFERENT team_id (201, not 200)
        assert result_2 == 201
        assert result_1 != result_2
        # Each call only did ONE fetch_one (ESPN lookup), never code fallback
        mock_fetch_one.assert_called_once()

    @patch("precog.database.crud_operations.fetch_one")
    @patch("precog.database.crud_operations.get_cursor")
    def test_unique_violation_with_espn_id_skips_code_fallback(
        self, mock_get_cursor, mock_fetch_one
    ):
        """When INSERT raises UniqueViolation and espn_team_id is provided,
        the handler should look up by ESPN ID only — NOT fall through to
        code-based lookup (same guard as Step 2, defense-in-depth)."""
        # Step 1: ESPN ID lookup returns None (new team)
        # UniqueViolation handler ESPN lookup returns the conflicting team
        mock_fetch_one.side_effect = [None, {"team_id": 300}]

        # Step 3: INSERT raises UniqueViolation (race condition)
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.errors.UniqueViolation("duplicate key")
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = create_team(
            team_code="MISS",
            team_name="Ole Miss Rebels",
            display_name="Ole Miss",
            sport="football",
            league="ncaaf",
            espn_team_id="145",
        )

        assert result == 300
        # fetch_one called exactly twice:
        # 1. Step 1 ESPN lookup (returned None)
        # 2. UniqueViolation handler ESPN lookup (returned team_id=300)
        # NOT a third call for code fallback
        assert mock_fetch_one.call_count == 2
        # Both calls should be ESPN ID lookups, not code lookups
        for call in mock_fetch_one.call_args_list:
            assert "espn_team_id" in call[0][0]


# =============================================================================
# SETTLEMENT VALUE ON UPDATE_MARKET_WITH_VERSIONING TESTS
# =============================================================================


@pytest.mark.unit
class TestUpdateMarketSettlementValue:
    """Test settlement_value flows through update_market_with_versioning."""

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.get_current_market")
    def test_settlement_value_included_in_dimension_update(self, mock_get_current, mock_get_cursor):
        """settlement_value is written to the markets dimension UPDATE."""
        mock_get_current.return_value = {
            "id": 1,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "open",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": None,
            "yes_bid_price": None,
            "no_bid_price": None,
            "last_price": None,
            "liquidity": None,
            "subtitle": None,
            "open_time": None,
            "close_time": None,
            "expiration_time": None,
            "outcome_label": None,
            "subcategory": None,
            "bracket_count": None,
            "source_url": None,
            "settlement_value": None,
        }

        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        update_market_with_versioning(
            ticker="TEST-MKT",
            status="settled",
            settlement_value=Decimal("1.0000"),
        )

        # The first execute call is the dimension UPDATE
        dim_call = mock_cursor.execute.call_args_list[0]
        sql = dim_call[0][0]
        params = dim_call[0][1]

        assert "settlement_value" in sql
        # settlement_value is the 11th param (after source_url, before market_pk)
        assert Decimal("1.0000") in params

    @patch("precog.database.crud_operations.get_cursor")
    @patch("precog.database.crud_operations.get_current_market")
    def test_settlement_value_none_preserves_existing(self, mock_get_current, mock_get_cursor):
        """When settlement_value is None, the existing value is preserved."""
        mock_get_current.return_value = {
            "id": 1,
            "yes_ask_price": Decimal("0.5000"),
            "no_ask_price": Decimal("0.5000"),
            "status": "settled",
            "volume": 100,
            "open_interest": 50,
            "metadata": None,
            "spread": None,
            "yes_bid_price": None,
            "no_bid_price": None,
            "last_price": None,
            "liquidity": None,
            "subtitle": None,
            "open_time": None,
            "close_time": None,
            "expiration_time": None,
            "outcome_label": None,
            "subcategory": None,
            "bracket_count": None,
            "source_url": None,
            "settlement_value": Decimal("1.0000"),
        }

        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Do NOT pass settlement_value — it should use existing
        update_market_with_versioning(
            ticker="TEST-MKT",
            yes_ask_price=Decimal("0.6000"),
        )

        dim_call = mock_cursor.execute.call_args_list[0]
        params = dim_call[0][1]
        # Existing Decimal("1.0000") should be preserved
        assert Decimal("1.0000") in params

    def test_settlement_value_rejects_float(self):
        """settlement_value must be Decimal, not float."""
        with pytest.raises(TypeError, match="settlement_value must be Decimal"):
            update_market_with_versioning(
                ticker="TEST-MKT",
                settlement_value=1.0,  # type: ignore[arg-type]
            )


# =============================================================================
# CHECK_EVENT_FULLY_SETTLED TESTS
# =============================================================================


@pytest.mark.unit
class TestCheckEventFullySettled:
    """Test check_event_fully_settled helper."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_all_markets_settled_returns_true(self, mock_fetch_one):
        """Returns True when all markets in the event are settled."""
        mock_fetch_one.return_value = {"total": 3, "settled": 3}

        assert check_event_fully_settled(42) is True
        mock_fetch_one.assert_called_once()
        # Verify event_internal_id is passed as param
        call_args = mock_fetch_one.call_args
        assert call_args[0][1] == (42,)

    @patch("precog.database.crud_operations.fetch_one")
    def test_some_unsettled_returns_false(self, mock_fetch_one):
        """Returns False when some markets are not yet settled."""
        mock_fetch_one.return_value = {"total": 3, "settled": 1}

        assert check_event_fully_settled(42) is False

    @patch("precog.database.crud_operations.fetch_one")
    def test_no_markets_returns_false(self, mock_fetch_one):
        """Returns False when no markets exist for the event."""
        mock_fetch_one.return_value = {"total": 0, "settled": 0}

        assert check_event_fully_settled(42) is False

    @patch("precog.database.crud_operations.fetch_one")
    def test_fetch_one_returns_none(self, mock_fetch_one):
        """Returns False when fetch_one returns None (defensive)."""
        mock_fetch_one.return_value = None

        assert check_event_fully_settled(42) is False

    @patch("precog.database.crud_operations.fetch_one")
    def test_single_market_settled(self, mock_fetch_one):
        """Returns True when a single market in the event is settled."""
        mock_fetch_one.return_value = {"total": 1, "settled": 1}

        assert check_event_fully_settled(99) is True

    @patch("precog.database.crud_operations.fetch_one")
    def test_query_uses_filter_clause(self, mock_fetch_one):
        """Verify the SQL uses FILTER (WHERE status = 'settled') pattern."""
        mock_fetch_one.return_value = {"total": 0, "settled": 0}

        check_event_fully_settled(1)

        call_args = mock_fetch_one.call_args
        sql = call_args[0][0]
        assert "FILTER" in sql
        assert "settled" in sql
        assert "event_internal_id" in sql


# =============================================================================
# _FILL_EVENT_NULL_FIELDS TESTS
# =============================================================================


@pytest.mark.unit
class TestFillEventNullFields:
    """Test _fill_event_null_fields helper for enrichment gap filling.

    Educational Note:
        _fill_event_null_fields implements the "fill gaps" pattern: it only
        writes values where the existing column is NULL AND the caller has
        provided a non-None replacement.  Non-NULL values are never
        overwritten.  This is critical on the hot path (every poll cycle)
        because it short-circuits when all fields are already populated.

    Reference:
        - Issue #513: Enrichment data gaps
        - get_or_create_event(): sole caller
    """

    @patch("precog.database.crud_operations.get_cursor")
    def test_fills_null_start_time(self, mock_get_cursor):
        """When existing start_time is NULL, caller value is written."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {
            "id": 42,
            "start_time": None,
            "end_time": "2025-01-01T20:00:00Z",
            "status": "live",
            "game_id": None,
        }

        _fill_event_null_fields(existing, start_time="2025-01-01T18:00:00Z")

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        assert "start_time" in sql
        assert "2025-01-01T18:00:00Z" in params
        # end_time and status should NOT be in the update
        assert "end_time" not in sql.split("WHERE")[0]

    @patch("precog.database.crud_operations.get_cursor")
    def test_fills_multiple_null_fields(self, mock_get_cursor):
        """Multiple NULL fields are all filled in a single UPDATE."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        _fill_event_null_fields(
            existing,
            start_time="2025-01-01T18:00:00Z",
            end_time="2025-01-01T22:00:00Z",
            status="live",
            game_id=15,
        )

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "start_time" in sql
        assert "end_time" in sql
        assert "status" in sql
        assert "game_id" in sql
        assert "updated_at = NOW()" in sql

    @patch("precog.database.crud_operations.get_cursor")
    def test_does_not_overwrite_non_null_values(self, mock_get_cursor):
        """Non-NULL existing values are never overwritten."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {
            "id": 42,
            "start_time": "2025-01-01T18:00:00Z",
            "end_time": "2025-01-01T22:00:00Z",
            "status": "live",
            "game_id": 10,
        }

        _fill_event_null_fields(
            existing,
            start_time="2025-06-01T00:00:00Z",
            end_time="2025-06-01T04:00:00Z",
            status="final",
            game_id=99,
        )

        # No UPDATE should be issued because all fields are non-NULL
        mock_cursor.execute.assert_not_called()

    @patch("precog.database.crud_operations.get_cursor")
    def test_no_update_when_no_values_provided(self, mock_get_cursor):
        """No UPDATE when caller provides no enrichment values."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        _fill_event_null_fields(existing)

        # No caller values -> no UPDATE
        mock_cursor.execute.assert_not_called()

    @patch("precog.database.crud_operations.get_cursor")
    def test_partial_fill_only_null_columns(self, mock_get_cursor):
        """Only NULL columns get updated; populated columns are skipped."""
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {
            "id": 42,
            "start_time": "2025-01-01T18:00:00Z",
            "end_time": None,
            "status": "live",
            "game_id": None,
        }

        _fill_event_null_fields(
            existing,
            start_time="SHOULD-NOT-OVERWRITE",
            end_time="2025-01-01T22:00:00Z",
            status="SHOULD-NOT-OVERWRITE",
            game_id=15,
        )

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]
        # Only end_time and game_id should appear
        assert "end_time" in sql
        assert "game_id" in sql
        # start_time and status should NOT appear in SET clause
        set_clause = sql.split("WHERE")[0]
        assert "start_time" not in set_clause
        # The status keyword appears in the WHERE clause but not SET
        assert set_clause.count("status") == 0
        assert "2025-01-01T22:00:00Z" in params
        assert 15 in params

    @patch("precog.database.crud_operations.get_cursor")
    def test_game_id_zero_is_treated_as_value(self, mock_get_cursor):
        """game_id=0 is falsy in Python but should still be written if existing is NULL.

        Educational Note:
            We use ``game_id is not None`` (not ``if game_id``) to correctly
            handle the edge case where game_id could be 0.  In practice this
            shouldn't happen (PKs start at 1), but defensive coding matters.
        """
        mock_cursor = MagicMock()
        mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)

        existing = {"id": 42, "start_time": None, "end_time": None, "status": None, "game_id": None}

        # game_id=0 should still trigger an update (0 is not None)
        _fill_event_null_fields(existing, game_id=0)

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "game_id" in sql


# =============================================================================
# GET_OR_CREATE_EVENT UPSERT BEHAVIOR TESTS
# =============================================================================


@pytest.mark.unit
class TestGetOrCreateEventUpsert:
    """Test get_or_create_event fills NULL enrichment fields on existing events.

    Educational Note:
        Prior to the enrichment fix, get_or_create_event returned immediately
        for existing events without updating any fields.  Now it calls
        _fill_event_null_fields to fill NULL gaps.  These tests verify the
        integration between get_or_create_event and the fill helper.

    Reference:
        - Issue #513: 98.7% of events had NULL start_time/end_time
    """

    @patch("precog.database.crud_operations._fill_event_null_fields")
    @patch("precog.database.crud_operations.get_event")
    def test_existing_event_triggers_fill(self, mock_get_event, mock_fill):
        """Existing event triggers _fill_event_null_fields with caller args."""
        mock_get_event.return_value = {
            "id": 42,
            "start_time": None,
            "end_time": None,
            "status": None,
            "game_id": None,
        }

        pk, created = get_or_create_event(
            event_id="TEST-EVT-1",
            platform_id="kalshi",
            external_id="TEST-EVT-1",
            category="sports",
            title="Test Event",
            start_time="2025-01-01T18:00:00Z",
            end_time="2025-01-01T22:00:00Z",
            status="live",
            game_id=15,
        )

        assert pk == 42
        assert created is False
        mock_fill.assert_called_once_with(
            mock_get_event.return_value,
            "2025-01-01T18:00:00Z",
            "2025-01-01T22:00:00Z",
            "live",
            15,
        )

    @patch("precog.database.crud_operations._fill_event_null_fields")
    @patch("precog.database.crud_operations.get_event")
    def test_new_event_does_not_trigger_fill(self, mock_get_event, mock_fill):
        """New event (not existing) goes through create path, not fill."""
        mock_get_event.return_value = None

        with patch("precog.database.crud_operations.create_event", return_value=99):
            pk, created = get_or_create_event(
                event_id="NEW-EVT-1",
                platform_id="kalshi",
                external_id="NEW-EVT-1",
                category="sports",
                title="New Event",
            )

        assert pk == 99
        assert created is True
        mock_fill.assert_not_called()


# =============================================================================
# BUILD_EVENT_RESULT TESTS
# =============================================================================


@pytest.mark.unit
class TestBuildEventResult:
    """Test build_event_result JSONB construction from child markets.

    Educational Note:
        build_event_result assembles a result dict from child market
        settlement values, serializing Decimal to string to avoid float
        precision issues in JSONB.

    Reference:
        - Issue #513: Event result population on settlement
    """

    @patch("precog.database.crud_operations.fetch_all")
    def test_basic_result_structure(self, mock_fetch_all):
        """Verify correct JSONB structure from settled markets."""
        mock_fetch_all.return_value = [
            {"ticker": "KXNFL-T1", "settlement_value": Decimal("1.0000"), "status": "settled"},
            {"ticker": "KXNFL-T2", "settlement_value": Decimal("0.0000"), "status": "settled"},
        ]

        result = build_event_result(42)

        assert result["markets_total"] == 2
        assert result["markets_settled"] == 2
        assert result["outcomes"]["KXNFL-T1"]["settlement_value"] == "1.0000"
        assert result["outcomes"]["KXNFL-T2"]["settlement_value"] == "0.0000"

    @patch("precog.database.crud_operations.fetch_all")
    def test_handles_null_settlement_values(self, mock_fetch_all):
        """Markets with NULL settlement_value are included with None."""
        mock_fetch_all.return_value = [
            {"ticker": "KXNFL-T1", "settlement_value": Decimal("1.0000"), "status": "settled"},
            {"ticker": "KXNFL-T2", "settlement_value": None, "status": "settled"},
        ]

        result = build_event_result(42)

        assert result["markets_total"] == 2
        assert result["markets_settled"] == 2
        assert result["outcomes"]["KXNFL-T1"]["settlement_value"] == "1.0000"
        assert result["outcomes"]["KXNFL-T2"]["settlement_value"] is None

    @patch("precog.database.crud_operations.fetch_all")
    def test_mixed_settled_and_open_markets(self, mock_fetch_all):
        """Result correctly counts settled vs non-settled markets."""
        mock_fetch_all.return_value = [
            {"ticker": "MKT-A", "settlement_value": Decimal("1.0000"), "status": "settled"},
            {"ticker": "MKT-B", "settlement_value": None, "status": "open"},
        ]

        result = build_event_result(42)

        assert result["markets_total"] == 2
        assert result["markets_settled"] == 1
        assert result["outcomes"]["MKT-A"]["settlement_value"] == "1.0000"
        assert result["outcomes"]["MKT-B"]["settlement_value"] is None

    @patch("precog.database.crud_operations.fetch_all")
    def test_no_markets_returns_empty(self, mock_fetch_all):
        """Event with no child markets returns empty structure."""
        mock_fetch_all.return_value = []

        result = build_event_result(42)

        assert result["markets_total"] == 0
        assert result["markets_settled"] == 0
        assert result["outcomes"] == {}

    @patch("precog.database.crud_operations.fetch_all")
    def test_decimal_precision_preserved(self, mock_fetch_all):
        """Decimal precision is preserved via string serialization.

        Educational Note:
            Storing Decimal as string in JSONB avoids float precision issues.
            e.g., float(Decimal("0.3333")) -> 0.3333 (OK) but
            json.dumps(float(Decimal("0.1"))) -> "0.1" (could lose precision
            with other values like 0.04 + 0.96 = 1.0000000000000002).
        """
        mock_fetch_all.return_value = [
            {"ticker": "SCALAR-MKT", "settlement_value": Decimal("0.3333"), "status": "settled"},
        ]

        result = build_event_result(99)

        assert result["outcomes"]["SCALAR-MKT"]["settlement_value"] == "0.3333"

    @patch("precog.database.crud_operations.fetch_all")
    def test_query_filters_by_event_internal_id(self, mock_fetch_all):
        """Verify the SQL uses event_internal_id filter."""
        mock_fetch_all.return_value = []

        build_event_result(42)

        call_args = mock_fetch_all.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "event_internal_id" in sql
        assert params == (42,)
