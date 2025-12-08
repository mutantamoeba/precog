"""
Integration Tests for Phase 2C CRUD Operations (Venues, Game States, Team Rankings).

These tests use REAL database operations with no mocking.
Requires running PostgreSQL database with test schema.

Related:
- REQ-DATA-001: Game State Data Collection (SCD Type 2)
- REQ-DATA-002: Venue Data Management
- ADR-029: ESPN Data Model with Normalized Schema
- Pattern 2: Dual Versioning System (SCD Type 2)

Usage:
    pytest tests/integration/database/test_phase2c_crud_integration.py -v
    pytest tests/integration/database/test_phase2c_crud_integration.py -v -m integration
"""

from datetime import datetime

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_operations import (
    create_game_state,
    create_team_ranking,
    create_venue,
    get_current_game_state,
    get_current_rankings,
    get_game_state_history,
    get_games_by_date,
    get_live_games,
    get_team_rankings,
    get_venue_by_espn_id,
    get_venue_by_id,
    upsert_game_state,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_test_teams(db_pool, clean_test_data):
    """
    Create test teams required for game_states and team_rankings.

    These tests need team records for FK constraints.

    Note: Uses TEST-prefixed team codes to avoid conflicts with seed data.
    Seed file 001_nfl_teams_initial_elo.sql already inserts 'KC', 'SF', etc.
    """
    with get_cursor(commit=True) as cur:
        # Create test teams with unique codes to avoid seed data conflicts
        # The teams table has a unique constraint on (team_code, sport)
        cur.execute(
            """
            INSERT INTO teams (
                team_id, team_code, team_name,
                espn_team_id, conference, division, sport, current_elo_rating
            )
            VALUES
                (9001, 'TEST-KC', 'Test Chiefs', 'TEST-12', 'AFC', 'West', 'nfl', 1650),
                (9002, 'TEST-SF', 'Test 49ers', 'TEST-25', 'NFC', 'West', 'nfl', 1620),
                (9003, 'TEST-OSU', 'Test Buckeyes', 'TEST-194', 'Big Ten', 'East', 'ncaaf', 1600)
            ON CONFLICT (team_id) DO NOTHING
        """
        )

    yield {"home_team_id": 9001, "away_team_id": 9002, "ncaaf_team_id": 9003}

    # Cleanup
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM game_states WHERE home_team_id IN (9001, 9002)")
        cur.execute("DELETE FROM team_rankings WHERE team_id IN (9001, 9002, 9003)")
        cur.execute("DELETE FROM teams WHERE team_id IN (9001, 9002, 9003)")


@pytest.fixture
def setup_test_venue(db_pool, clean_test_data):
    """Create test venue for game_states FK constraint."""
    venue_id = create_venue(
        espn_venue_id="TEST-VENUE-001",
        venue_name="Test Stadium",
        city="Test City",
        state="TS",
        capacity=50000,
        indoor=False,
    )

    yield venue_id

    # Cleanup
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM venues WHERE espn_venue_id = 'TEST-VENUE-001'")


# =============================================================================
# VENUE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
class TestVenueIntegration:
    """Integration tests for venue CRUD operations."""

    def test_create_venue_inserts_record(self, db_pool, db_cursor, clean_test_data):
        """Test create_venue inserts record into database."""
        venue_id = create_venue(
            espn_venue_id="INT-TEST-3622",
            venue_name="GEHA Field at Arrowhead Stadium",
            city="Kansas City",
            state="Missouri",
            capacity=76416,
            indoor=False,
        )

        assert venue_id is not None
        assert isinstance(venue_id, int)

        # Verify in database
        venue = get_venue_by_espn_id("INT-TEST-3622")
        assert venue is not None
        assert venue["venue_name"] == "GEHA Field at Arrowhead Stadium"
        assert venue["capacity"] == 76416
        assert venue["indoor"] is False

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'INT-TEST-3622'")

    def test_create_venue_upsert_updates_existing(self, db_pool, db_cursor, clean_test_data):
        """Test create_venue updates existing record on conflict."""
        # Create initial
        venue_id1 = create_venue(
            espn_venue_id="INT-UPSERT-001",
            venue_name="Old Stadium Name",
            city="Old City",
        )

        # Upsert with same ESPN ID
        venue_id2 = create_venue(
            espn_venue_id="INT-UPSERT-001",
            venue_name="New Stadium Name",
            city="New City",
        )

        # Should return same venue_id
        assert venue_id2 == venue_id1

        # Verify update applied
        venue = get_venue_by_espn_id("INT-UPSERT-001")
        assert venue["venue_name"] == "New Stadium Name"
        assert venue["city"] == "New City"

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'INT-UPSERT-001'")

    def test_get_venue_by_id_returns_correct_venue(self, db_pool, db_cursor, clean_test_data):
        """Test get_venue_by_id retrieves correct record."""
        venue_id = create_venue(espn_venue_id="INT-BYID-001", venue_name="ById Test Stadium")

        result = get_venue_by_id(venue_id)

        assert result is not None
        assert result["venue_id"] == venue_id
        assert result["venue_name"] == "ById Test Stadium"

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'INT-BYID-001'")

    def test_venue_with_nullable_fields(self, db_pool, db_cursor, clean_test_data):
        """Test venue creation with nullable fields as None."""
        venue_id = create_venue(
            espn_venue_id="INT-NULL-001",
            venue_name="Minimal Stadium",
            # city, state, capacity all None
        )

        venue = get_venue_by_id(venue_id)
        assert venue["city"] is None
        assert venue["state"] is None
        assert venue["capacity"] is None

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'INT-NULL-001'")


# =============================================================================
# TEAM RANKING INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
class TestTeamRankingIntegration:
    """Integration tests for team ranking CRUD operations."""

    def test_create_team_ranking_inserts_record(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams
    ):
        """Test create_team_ranking inserts record into database."""
        team_id = setup_test_teams["home_team_id"]

        ranking_id = create_team_ranking(
            team_id=team_id,
            ranking_type="ap_poll",
            rank=3,
            season=2024,
            ranking_date=datetime(2024, 11, 17),
            week=12,
            points=1432,
            first_place_votes=12,
        )

        assert ranking_id is not None

        # Verify in database
        rankings = get_team_rankings(team_id, ranking_type="ap_poll", season=2024)
        assert len(rankings) >= 1
        ranking = rankings[0]
        assert ranking["rank"] == 3
        assert ranking["points"] == 1432

    def test_create_team_ranking_upsert_updates(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams
    ):
        """Test create_team_ranking updates on conflict."""
        team_id = setup_test_teams["home_team_id"]

        # Create initial
        create_team_ranking(
            team_id=team_id,
            ranking_type="cfp",
            rank=5,
            season=2024,
            ranking_date=datetime(2024, 12, 1),
            week=13,
        )

        # Update same (team, type, season, week) combination
        create_team_ranking(
            team_id=team_id,
            ranking_type="cfp",
            rank=3,  # Changed rank
            season=2024,
            ranking_date=datetime(2024, 12, 1),
            week=13,  # Same week
        )

        # Should only have one record with updated rank
        rankings = get_team_rankings(team_id, ranking_type="cfp", season=2024)
        cfp_week_13 = [r for r in rankings if r["week"] == 13]
        assert len(cfp_week_13) == 1
        assert cfp_week_13[0]["rank"] == 3

    def test_get_current_rankings_returns_latest_week(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams
    ):
        """Test get_current_rankings returns most recent week."""
        team_id = setup_test_teams["home_team_id"]

        # Create rankings for multiple weeks
        create_team_ranking(
            team_id=team_id,
            ranking_type="coaches_poll",
            rank=5,
            season=2024,
            ranking_date=datetime(2024, 11, 10),
            week=10,
        )
        create_team_ranking(
            team_id=team_id,
            ranking_type="coaches_poll",
            rank=3,
            season=2024,
            ranking_date=datetime(2024, 11, 17),
            week=11,
        )

        # Get current (should be week 11)
        rankings = get_current_rankings("coaches_poll", 2024)

        assert len(rankings) >= 1
        # All returned should be week 11 (latest)
        for r in rankings:
            if r["team_id"] == team_id:
                assert r["rank"] == 3


# =============================================================================
# GAME STATE INTEGRATION TESTS
# =============================================================================


@pytest.mark.integration
@pytest.mark.critical
class TestGameStateIntegration:
    """Integration tests for game state CRUD with SCD Type 2."""

    def test_create_game_state_inserts_current_record(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test create_game_state inserts with row_current_ind=TRUE."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        state_id = create_game_state(
            espn_event_id="INT-GAME-001",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        assert state_id is not None

        # Verify row_current_ind = TRUE
        state = get_current_game_state("INT-GAME-001")
        assert state is not None
        assert state["row_current_ind"] is True
        assert state["game_status"] == "pre"

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'INT-GAME-001'")

    def test_upsert_game_state_creates_history(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test upsert_game_state creates SCD Type 2 history."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        # Create initial state
        create_game_state(
            espn_event_id="INT-GAME-002",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        # Update with score change
        upsert_game_state(
            espn_event_id="INT-GAME-002",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            home_score=7,
            away_score=0,
            period=1,
            game_status="in_progress",
            league="nfl",
        )

        # Check history
        history = get_game_state_history("INT-GAME-002")
        assert len(history) == 2

        # Verify current is latest
        current = get_current_game_state("INT-GAME-002")
        assert current["home_score"] == 7
        assert current["row_current_ind"] is True

        # Verify old row is FALSE
        historical = [h for h in history if h["row_current_ind"] is False]
        assert len(historical) == 1
        assert historical[0]["home_score"] == 0

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'INT-GAME-002'")

    def test_get_game_state_history_orders_by_timestamp(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test get_game_state_history returns newest first."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        # Create multiple versions
        create_game_state(
            espn_event_id="INT-GAME-003",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        for score in [7, 14, 21]:
            upsert_game_state(
                espn_event_id="INT-GAME-003",
                home_team_id=teams["home_team_id"],
                away_team_id=teams["away_team_id"],
                venue_id=venue_id,
                home_score=score,
                away_score=0,
                game_status="in_progress",
                league="nfl",
            )

        history = get_game_state_history("INT-GAME-003")
        assert len(history) == 4

        # Verify ordering (newest first)
        scores = [h["home_score"] for h in history]
        assert scores == [21, 14, 7, 0]

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'INT-GAME-003'")

    def test_get_live_games_filters_in_progress(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test get_live_games returns only in_progress games."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        # Create completed game
        create_game_state(
            espn_event_id="INT-GAME-FINAL",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            home_score=24,
            away_score=17,
            game_status="final",
            league="nfl",
        )

        # Create live game
        create_game_state(
            espn_event_id="INT-GAME-LIVE",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            home_score=14,
            away_score=7,
            game_status="in_progress",
            league="nfl",
        )

        live_games = get_live_games(league="nfl")

        # Should include live game, not final
        event_ids = [g["espn_event_id"] for g in live_games]
        assert "INT-GAME-LIVE" in event_ids
        assert "INT-GAME-FINAL" not in event_ids

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM game_states WHERE espn_event_id IN ('INT-GAME-FINAL', 'INT-GAME-LIVE')"
            )

    def test_get_games_by_date_filters_correctly(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test get_games_by_date filters by date."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        # Create game for Nov 28
        create_game_state(
            espn_event_id="INT-GAME-NOV28",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            game_date=datetime(2024, 11, 28, 16, 30),
            game_status="pre",
            league="nfl",
        )

        # Create game for Nov 29
        create_game_state(
            espn_event_id="INT-GAME-NOV29",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            game_date=datetime(2024, 11, 29, 13, 0),
            game_status="pre",
            league="nfl",
        )

        # Query Nov 28 games
        nov28_games = get_games_by_date(datetime(2024, 11, 28), league="nfl")
        event_ids = [g["espn_event_id"] for g in nov28_games]

        assert "INT-GAME-NOV28" in event_ids
        assert "INT-GAME-NOV29" not in event_ids

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM game_states WHERE espn_event_id IN ('INT-GAME-NOV28', 'INT-GAME-NOV29')"
            )


@pytest.mark.integration
class TestGameStateSituationJsonb:
    """Integration tests for JSONB situation field."""

    def test_situation_jsonb_round_trip(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test JSONB situation field preserves data structure."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        situation = {
            "possession": "TEST-KC",
            "down": 2,
            "distance": 7,
            "yardLine": 35,
            "isRedZone": False,
            "homeTimeouts": 3,
            "awayTimeouts": 2,
        }

        create_game_state(
            espn_event_id="INT-GAME-JSONB",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            situation=situation,
            game_status="in_progress",
            league="nfl",
        )

        # Retrieve and verify
        state = get_current_game_state("INT-GAME-JSONB")
        assert state["situation"] is not None

        # PostgreSQL returns JSONB as dict
        retrieved_situation = state["situation"]
        assert retrieved_situation["possession"] == "TEST-KC"
        assert retrieved_situation["down"] == 2
        assert retrieved_situation["isRedZone"] is False

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'INT-GAME-JSONB'")

    def test_linescores_jsonb_round_trip(
        self, db_pool, db_cursor, clean_test_data, setup_test_teams, setup_test_venue
    ):
        """Test JSONB linescores field preserves array structure."""
        teams = setup_test_teams
        venue_id = setup_test_venue

        linescores = [
            {"period": 1, "home": 7, "away": 3},
            {"period": 2, "home": 10, "away": 7},
            {"period": 3, "home": 0, "away": 0},
            {"period": 4, "home": 7, "away": 3},
        ]

        create_game_state(
            espn_event_id="INT-GAME-LINES",
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            venue_id=venue_id,
            linescores=linescores,
            game_status="final",
            league="nfl",
        )

        state = get_current_game_state("INT-GAME-LINES")
        assert state["linescores"] is not None
        assert len(state["linescores"]) == 4
        assert state["linescores"][0]["home"] == 7

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'INT-GAME-LINES'")
