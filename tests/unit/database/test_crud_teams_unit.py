"""Unit tests for crud_teams module — extracted from test_crud_operations_unit.py (split per #893 Option 1).

Covers teams, venues, and team_rankings sub-modules (all live in crud_teams.py):
- create_venue / get_venue_by_espn_id / get_venue_by_id
- create_team_ranking / get_team_rankings / get_current_rankings
- get_team_by_espn_id / get_teams_with_kalshi_codes / create_team
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import psycopg2.errors
import pytest

from precog.database.crud_teams import (
    create_team,
    create_team_ranking,
    create_venue,
    get_current_rankings,
    get_team_by_espn_id,
    get_team_rankings,
    get_teams_with_kalshi_codes,
    get_venue_by_espn_id,
    get_venue_by_id,
)


@pytest.mark.unit
class TestCreateVenueUnit:
    """Unit tests for create_venue function with mocked database."""

    @patch("precog.database.crud_teams.get_cursor")
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

    @patch("precog.database.crud_teams.get_cursor")
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

    @patch("precog.database.crud_teams.get_cursor")
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
    @patch("precog.database.crud_teams.get_cursor")
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

    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.fetch_one")
    def test_get_venue_by_espn_id_not_found_returns_none(self, mock_fetch_one):
        """Test get_venue_by_espn_id returns None when not found."""
        mock_fetch_one.return_value = None

        result = get_venue_by_espn_id("nonexistent")

        assert result is None

    @patch("precog.database.crud_teams.fetch_one")
    def test_get_venue_by_id_returns_dict(self, mock_fetch_one):
        """Test get_venue_by_id returns venue dictionary."""
        mock_fetch_one.return_value = {"venue_id": 42, "venue_name": "Test Stadium"}

        result = get_venue_by_id(42)

        assert result is not None
        assert result["venue_id"] == 42


@pytest.mark.unit
class TestCreateTeamRankingUnit:
    """Unit tests for create_team_ranking function."""

    @patch("precog.database.crud_teams.get_cursor")
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

    @patch("precog.database.crud_teams.get_cursor")
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

    @patch("precog.database.crud_teams.fetch_all")
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

    @patch("precog.database.crud_teams.fetch_all")
    def test_get_team_rankings_empty_list_when_none(self, mock_fetch_all):
        """Test get_team_rankings returns empty list when no rankings."""
        mock_fetch_all.return_value = []

        result = get_team_rankings(team_id=999)

        assert result == []

    @patch("precog.database.crud_teams.fetch_all")
    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.fetch_one")
    def test_get_current_rankings_no_week_returns_empty(self, mock_fetch_one):
        """Test get_current_rankings returns empty when no weeks exist."""
        mock_fetch_one.return_value = {"max_week": None}

        result = get_current_rankings("ap_poll", 2024)

        assert result == []


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

    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.fetch_one")
    def test_get_team_by_espn_id_wrong_league_returns_none(self, mock_fetch_one):
        """Test team exists but in wrong league returns None.

        Educational Note:
            A team might exist in the database (e.g., ESPN ID 22 for NFL),
            but if we query with the wrong league filter, no match is found.
        """
        mock_fetch_one.return_value = None  # No match for this league

        result = get_team_by_espn_id("22", league="nba")  # NFL team queried as NBA

        assert result is None

    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.fetch_one")
    def test_get_team_by_espn_id_empty_string_handled(self, mock_fetch_one):
        """Test empty ESPN ID is handled gracefully."""
        mock_fetch_one.return_value = None

        result = get_team_by_espn_id("")

        assert result is None


@pytest.mark.unit
class TestGetTeamsWithKalshiCodesUnit:
    """Unit tests for get_teams_with_kalshi_codes — team registry data source."""

    @patch("precog.database.crud_teams.fetch_all")
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

    @patch("precog.database.crud_teams.fetch_all")
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

    @patch("precog.database.crud_teams.fetch_all")
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


@pytest.mark.unit
class TestCreateTeamUnit:
    """Unit tests for create_team function.

    Key behavior: when espn_team_id is provided and Step 1 (ESPN ID lookup)
    finds no match, the code fallback (Step 2) must NOT fire. This prevents
    college sports code collisions (e.g., two 'MISS' teams in NCAAF) from
    silently losing ~61 teams per restart.
    """

    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.get_cursor")
    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.get_cursor")
    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.get_cursor")
    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.get_league_id_or_none")
    @patch("precog.database.crud_teams.get_sport_id_or_none")
    @patch("precog.database.crud_teams.get_cursor")
    @patch("precog.database.crud_teams.fetch_one")
    def test_insert_includes_all_fields(
        self, mock_fetch_one, mock_get_cursor, mock_sport_id, mock_league_id
    ):
        """Verify INSERT passes all 11 columns including espn_team_id and the FK pair."""
        mock_fetch_one.return_value = None  # Step 1: no match
        # Unit-test isolation: pin the #738 A1 lookup helpers so the test is
        # independent of whether the unit-test DB happens to have the lookup
        # tables populated (which changes when migration 0060 is applied).
        mock_sport_id.return_value = None
        mock_league_id.return_value = None

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
        # Verify all 11 params are passed in correct order.
        # The trailing sport_id/league_id pair lands from the #738 A1
        # dual-write path; the patches above pin both lookup helpers to
        # None so the test verifies the NO-FK-backfill code path
        # deterministically.
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
            None,
            None,
        )

    @patch("precog.database.crud_teams.get_cursor")
    @patch("precog.database.crud_teams.fetch_one")
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

    @patch("precog.database.crud_teams.fetch_one")
    @patch("precog.database.crud_teams.get_cursor")
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
