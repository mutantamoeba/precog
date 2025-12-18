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

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# Import functions to test
from precog.database.crud_operations import (
    create_game_state,
    create_team_ranking,
    create_venue,
    game_state_changed,
    get_current_game_state,
    get_current_rankings,
    get_game_state_history,
    get_games_by_date,
    get_live_games,
    get_team_by_espn_id,
    get_team_rankings,
    get_venue_by_espn_id,
    get_venue_by_id,
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
        """Test create_game_state returns game_state_id."""
        mock_cursor = MagicMock()
        # Note: RETURNING id returns "id" key, then code maps to game_state_id
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
        # Note: create_game_state makes 2 execute calls: INSERT then UPDATE
        # Check the first call (INSERT) for the params
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

        # Note: create_game_state makes 2 execute calls: INSERT then UPDATE
        # Check the first call (INSERT) for the params
        insert_call = mock_cursor.execute.call_args_list[0]
        params = insert_call[0][1]
        # Verify Decimal is passed (not float)
        assert any(isinstance(p, Decimal) for p in params)


@pytest.mark.unit
class TestGetGameStateUnit:
    """Unit tests for game state retrieval functions."""

    @patch("precog.database.crud_operations.fetch_one")
    def test_get_current_game_state_returns_current(self, mock_fetch_one):
        """Test get_current_game_state returns current version only."""
        mock_fetch_one.return_value = {
            "game_state_id": 500,
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
            {"game_state_id": 503, "home_score": 21, "row_current_ind": True},
            {"game_state_id": 502, "home_score": 14, "row_current_ind": False},
            {"game_state_id": 501, "home_score": 7, "row_current_ind": False},
        ]

        result = get_game_state_history("401547417")

        assert len(result) == 3
        assert result[0]["home_score"] == 21  # Most recent first

    @patch("precog.database.crud_operations.fetch_all")
    def test_get_game_state_history_respects_limit(self, mock_fetch_all):
        """Test get_game_state_history respects limit parameter."""
        mock_fetch_all.return_value = [{"game_state_id": 1}]

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
            upsert_game_state makes 3 execute calls:
            1. close_query - SET row_current_ind = FALSE
            2. insert_query - INSERT new row RETURNING id
            3. update_id_query - UPDATE game_state_id
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
