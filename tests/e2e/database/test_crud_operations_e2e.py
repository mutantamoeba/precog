"""
End-to-End Tests for Phase 2C CRUD Operations.

Tests complete ESPN data ingestion workflow:
1. Create venues from ESPN API response
2. Create/update game states with SCD Type 2 versioning
3. Ingest team rankings with temporal validity
4. Query combined data for trading decisions

Related:
- REQ-DATA-001: Game State Data Collection (SCD Type 2)
- REQ-DATA-002: Venue Data Management
- ADR-029: ESPN Data Model with Normalized Schema

Usage:
    pytest tests/e2e/database/test_phase2c_e2e.py -v
    pytest tests/e2e/database/test_phase2c_e2e.py -v -m e2e
"""

from datetime import datetime
from decimal import Decimal

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_operations import (
    create_game_state,
    create_team_ranking,
    create_venue,
    get_current_game_state,
    get_current_rankings,
    get_game_state_history,
    get_live_games,
    get_team_rankings,
    get_venue_by_espn_id,
    upsert_game_state,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_e2e_teams(db_pool, clean_test_data):
    """Create realistic team data for E2E tests.

    Note: Uses E2E-prefixed team codes to avoid conflicts with seed data.
    Seed file 001_nfl_teams_initial_elo.sql already inserts 'KC', 'LV', etc.
    """
    with get_cursor(commit=True) as cur:
        # Note: Using columns from migration 010 schema (not migration 028 enhancements)
        # E2E-prefixed codes avoid (team_code, sport) unique constraint violations
        cur.execute(
            """
            INSERT INTO teams (
                team_id, team_code, team_name,
                espn_team_id, conference, division, sport, current_elo_rating
            )
            VALUES
                (88001, 'E2E-KC', 'E2E Chiefs', 'E2E-12', 'AFC', 'West', 'nfl', 1650),
                (88002, 'E2E-LV', 'E2E Raiders', 'E2E-13', 'AFC', 'West', 'nfl', 1480),
                (88003, 'E2E-DET', 'E2E Lions', 'E2E-8', 'NFC', 'North', 'nfl', 1580),
                (88004, 'E2E-CHI', 'E2E Bears', 'E2E-3', 'NFC', 'North', 'nfl', 1420)
            ON CONFLICT (team_id) DO NOTHING
        """
        )

    yield {
        "kc": {"team_id": 88001, "espn_team_id": "E2E-12"},
        "lv": {"team_id": 88002, "espn_team_id": "E2E-13"},
        "det": {"team_id": 88003, "espn_team_id": "E2E-8"},
        "chi": {"team_id": 88004, "espn_team_id": "E2E-3"},
    }

    # Cleanup
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM game_states WHERE home_team_id IN (88001, 88002, 88003, 88004)")
        cur.execute("DELETE FROM team_rankings WHERE team_id IN (88001, 88002, 88003, 88004)")
        cur.execute("DELETE FROM teams WHERE team_id IN (88001, 88002, 88003, 88004)")
        cur.execute("DELETE FROM venues WHERE espn_venue_id LIKE 'E2E-%'")


# =============================================================================
# E2E WORKFLOW TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.critical
class TestESPNDataIngestionWorkflow:
    """E2E tests simulating complete ESPN data ingestion pipeline."""

    def test_complete_game_day_data_ingestion(self, db_pool, clean_test_data, setup_e2e_teams):
        """
        E2E: Simulate complete NFL game day data ingestion.

        Workflow:
        1. Ingest venues from ESPN schedule response
        2. Create pre-game states for scheduled games
        3. Update game states as scores change (SCD Type 2)
        4. Query live games for trading decisions
        5. Mark games as final

        This mirrors the actual ESPN API polling workflow.
        """
        teams = setup_e2e_teams

        # Step 1: Ingest venue data (typically from first API call)
        arrowhead_id = create_venue(
            espn_venue_id="E2E-3622",
            venue_name="GEHA Field at Arrowhead Stadium",
            city="Kansas City",
            state="Missouri",
            capacity=76416,
            indoor=False,
        )
        ford_field_id = create_venue(
            espn_venue_id="E2E-3727",
            venue_name="Ford Field",
            city="Detroit",
            state="Michigan",
            capacity=65000,
            indoor=True,
        )

        # Verify venues created
        assert arrowhead_id is not None
        assert ford_field_id is not None

        # Step 2: Create pre-game states (morning of game day)
        create_game_state(
            espn_event_id="E2E-401547417",  # KC vs LV
            home_team_id=teams["kc"]["team_id"],
            away_team_id=teams["lv"]["team_id"],
            venue_id=arrowhead_id,
            home_score=0,
            away_score=0,
            game_status="pre",
            game_date=datetime(2024, 11, 29, 16, 30),
            broadcast="CBS",
            league="nfl",
            season_type="regular",
            week_number=13,
        )
        create_game_state(
            espn_event_id="E2E-401547418",  # DET vs CHI
            home_team_id=teams["det"]["team_id"],
            away_team_id=teams["chi"]["team_id"],
            venue_id=ford_field_id,
            home_score=0,
            away_score=0,
            game_status="pre",
            game_date=datetime(2024, 11, 29, 12, 30),
            broadcast="FOX",
            league="nfl",
            season_type="regular",
            week_number=13,
        )

        # Verify pre-game states
        kc_game = get_current_game_state("E2E-401547417")
        assert kc_game is not None
        assert kc_game["game_status"] == "pre"
        assert kc_game["home_score"] == 0

        # Step 3: Simulate game updates (Lions game starts first)
        # Q1 - Lions score TD
        upsert_game_state(
            espn_event_id="E2E-401547418",
            home_team_id=teams["det"]["team_id"],
            away_team_id=teams["chi"]["team_id"],
            venue_id=ford_field_id,
            home_score=7,
            away_score=0,
            period=1,
            clock_seconds=Decimal("512"),
            clock_display="8:32",
            game_status="in_progress",
            league="nfl",
            situation={"possession": "DET", "down": 1, "distance": 10},
        )

        # Q2 - Bears respond
        upsert_game_state(
            espn_event_id="E2E-401547418",
            home_team_id=teams["det"]["team_id"],
            away_team_id=teams["chi"]["team_id"],
            venue_id=ford_field_id,
            home_score=14,
            away_score=7,
            period=2,
            clock_seconds=Decimal("120"),
            clock_display="2:00",
            game_status="in_progress",
            league="nfl",
            situation={"possession": "CHI", "down": 2, "distance": 5},
        )

        # Step 4: Query live games for trading decisions
        live_games = get_live_games(league="nfl")
        assert len(live_games) >= 1

        # Find our test game
        det_game = next((g for g in live_games if g["espn_event_id"] == "E2E-401547418"), None)
        assert det_game is not None
        assert det_game["home_score"] == 14
        assert det_game["away_score"] == 7

        # Step 5: Verify SCD Type 2 history
        det_history = get_game_state_history("E2E-401547418")
        assert len(det_history) == 3  # pre + 2 updates

        # Current should be latest
        assert det_history[0]["row_current_ind"] is True
        assert det_history[0]["home_score"] == 14

        # Historical rows should be FALSE
        historical = [h for h in det_history if h["row_current_ind"] is False]
        assert len(historical) == 2
        scores = sorted([h["home_score"] for h in historical])
        assert scores == [0, 7]

        # Step 6: Mark game as final
        upsert_game_state(
            espn_event_id="E2E-401547418",
            home_team_id=teams["det"]["team_id"],
            away_team_id=teams["chi"]["team_id"],
            venue_id=ford_field_id,
            home_score=31,
            away_score=17,
            period=4,
            clock_seconds=Decimal("0"),
            clock_display="0:00",
            game_status="final",
            league="nfl",
        )

        # Verify final state
        final_state = get_current_game_state("E2E-401547418")
        assert final_state["game_status"] == "final"
        assert final_state["home_score"] == 31

        # Verify no longer in live games
        live_after = get_live_games(league="nfl")
        det_live = [g for g in live_after if g["espn_event_id"] == "E2E-401547418"]
        assert len(det_live) == 0  # Not in live anymore

    def test_team_rankings_weekly_update_workflow(self, db_pool, clean_test_data, setup_e2e_teams):
        """
        E2E: Simulate weekly AP Poll rankings ingestion.

        Workflow:
        1. Ingest Week 12 rankings (4 teams)
        2. Ingest Week 13 rankings (rankings changed)
        3. Query historical rankings for trend analysis
        4. Query current rankings for market context
        """
        teams = setup_e2e_teams

        # Step 1: Week 12 rankings
        week_12_rankings = [
            (teams["det"]["team_id"], 5, 1100, 0),  # #5 Detroit
            (teams["kc"]["team_id"], 8, 950, 0),  # #8 KC
            (teams["chi"]["team_id"], None, None, None),  # Unranked
            (teams["lv"]["team_id"], None, None, None),  # Unranked
        ]

        for team_id, rank, points, votes in week_12_rankings:
            if rank is not None:
                create_team_ranking(
                    team_id=team_id,
                    ranking_type="ap_poll",
                    rank=rank,
                    season=2024,
                    ranking_date=datetime(2024, 11, 17),
                    week=12,
                    points=points,
                    first_place_votes=votes,
                )

        # Step 2: Week 13 rankings (Lions move up, KC drops)
        week_13_rankings = [
            (teams["det"]["team_id"], 3, 1250, 5),  # #3 Detroit (moved up from #5)
            (teams["kc"]["team_id"], 10, 850, 0),  # #10 KC (dropped from #8)
        ]

        for team_id, rank, points, votes in week_13_rankings:
            create_team_ranking(
                team_id=team_id,
                ranking_type="ap_poll",
                rank=rank,
                season=2024,
                ranking_date=datetime(2024, 11, 24),
                week=13,
                points=points,
                first_place_votes=votes,
                previous_rank=5 if team_id == teams["det"]["team_id"] else 8,
            )

        # Step 3: Query historical rankings for Detroit
        det_rankings = get_team_rankings(
            team_id=teams["det"]["team_id"],
            ranking_type="ap_poll",
            season=2024,
        )
        assert len(det_rankings) == 2

        # Verify trending up
        week_12_rank = next((r for r in det_rankings if r["week"] == 12), None)
        week_13_rank = next((r for r in det_rankings if r["week"] == 13), None)
        assert week_12_rank["rank"] == 5
        assert week_13_rank["rank"] == 3
        assert week_13_rank["rank"] < week_12_rank["rank"]  # Improved

        # Step 4: Query current rankings (latest week)
        current = get_current_rankings("ap_poll", 2024)
        assert len(current) >= 2

        # Should return week 13 rankings
        det_current = next((r for r in current if r["team_id"] == teams["det"]["team_id"]), None)
        assert det_current is not None
        assert det_current["week"] == 13
        assert det_current["rank"] == 3


@pytest.mark.e2e
class TestVenueDataEnrichment:
    """E2E tests for venue data enrichment workflow."""

    def test_venue_update_on_naming_rights_change(self, db_pool, clean_test_data):
        """
        E2E: Simulate venue name update due to naming rights change.

        Real example: Arrowhead Stadium -> GEHA Field at Arrowhead Stadium
        """
        # Original name (before naming rights deal)
        venue_id_1 = create_venue(
            espn_venue_id="E2E-NAMING-001",
            venue_name="Arrowhead Stadium",
            city="Kansas City",
            state="Missouri",
            capacity=76416,
            indoor=False,
        )

        # ESPN API returns updated name (after naming rights)
        venue_id_2 = create_venue(
            espn_venue_id="E2E-NAMING-001",  # Same ESPN ID
            venue_name="GEHA Field at Arrowhead Stadium",  # New name
            city="Kansas City",
            state="Missouri",
            capacity=76416,
            indoor=False,
        )

        # Should be same venue (upsert)
        assert venue_id_1 == venue_id_2

        # Verify name updated
        venue = get_venue_by_espn_id("E2E-NAMING-001")
        assert venue["venue_name"] == "GEHA Field at Arrowhead Stadium"

        # Verify only ONE record exists (no history - venues don't use SCD Type 2)
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM venues WHERE espn_venue_id = 'E2E-NAMING-001'")
            result = cur.fetchone()
            assert result["count"] == 1


# =============================================================================
# E2E TESTS: STATE CHANGE DETECTION WORKFLOW (Issue #234)
# =============================================================================


@pytest.mark.e2e
@pytest.mark.critical
class TestStateChangeDetectionWorkflow:
    """E2E tests for state change detection to reduce SCD Type 2 row bloat.

    Related: Issue #234 - State change detection for game state polling
    Reference: TESTING_STRATEGY V3.2 - E2E tests for complete workflow validation

    Problem: Without state change detection, each poll creates a new historical row
    even when nothing meaningful changed (e.g., just clock tick).

    Solution: game_state_changed() compares core fields (score, period, status,
    situation) and skip_if_unchanged parameter prevents redundant row creation.

    Expected Row Reduction: ~1000 rows/game -> ~50-100 rows/game (90%+ reduction)
    """

    def test_complete_game_polling_with_state_change_detection(
        self, db_pool, clean_test_data, setup_e2e_teams
    ):
        """
        E2E: Simulate realistic polling during a game with state change detection.

        Workflow:
        1. Create pre-game state
        2. Simulate 15-second polls where clock ticks but nothing changes
        3. Verify NO new rows created for clock-only changes
        4. Simulate actual state changes (score, period)
        5. Verify new rows created only for meaningful changes
        6. Compare final row count with vs without state change detection
        """
        from precog.database.crud_operations import game_state_changed

        teams = setup_e2e_teams

        # Clean up any existing test data
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'E2E-STATE-GAME-001'")
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'E2E-STATE-001'")

        # Create venue for the game
        venue_id = create_venue(
            espn_venue_id="E2E-STATE-001",
            venue_name="State Change Stadium",
            city="Test City",
            state="TS",
        )

        # Step 1: Create pre-game state
        create_game_state(
            espn_event_id="E2E-STATE-GAME-001",
            home_team_id=teams["kc"]["team_id"],
            away_team_id=teams["lv"]["team_id"],
            venue_id=venue_id,
            home_score=0,
            away_score=0,
            period=0,
            game_status="pre",
            league="nfl",
        )

        # Verify initial state
        history = get_game_state_history("E2E-STATE-GAME-001")
        assert len(history) == 1

        # Step 2: Simulate 5 clock-tick polls (no meaningful changes)
        # Each poll is 15 seconds later - clock changes but nothing else
        current = get_current_game_state("E2E-STATE-GAME-001")
        for clock_value in [900, 885, 870, 855, 840]:
            # Check if state changed (should NOT)
            changed = game_state_changed(
                current,
                home_score=0,
                away_score=0,
                period=1,
                game_status="in_progress",
            )
            # First poll - period 0->1 is a change
            if current["period"] == 0:
                assert changed is True
                upsert_game_state(
                    espn_event_id="E2E-STATE-GAME-001",
                    home_score=0,
                    away_score=0,
                    period=1,
                    clock_seconds=Decimal(str(clock_value)),
                    clock_display=f"{clock_value // 60}:{clock_value % 60:02d}",
                    game_status="in_progress",
                    league="nfl",
                    skip_if_unchanged=True,
                )
                current = get_current_game_state("E2E-STATE-GAME-001")
            else:
                # Clock-only changes should NOT create new row
                upsert_game_state(
                    espn_event_id="E2E-STATE-GAME-001",
                    home_score=0,
                    away_score=0,
                    period=1,
                    clock_seconds=Decimal(str(clock_value)),
                    clock_display=f"{clock_value // 60}:{clock_value % 60:02d}",
                    game_status="in_progress",
                    league="nfl",
                    skip_if_unchanged=True,
                )

        # Step 3: Verify only 2 rows (pre + game start) - NOT 6 rows!
        history = get_game_state_history("E2E-STATE-GAME-001")
        assert len(history) == 2, (
            f"Expected 2 rows, got {len(history)} - clock changes should not create rows"
        )

        # Step 4: Simulate actual score change (TD)
        upsert_game_state(
            espn_event_id="E2E-STATE-GAME-001",
            home_score=7,  # Touchdown!
            away_score=0,
            period=1,
            clock_seconds=Decimal("720"),
            clock_display="12:00",
            game_status="in_progress",
            league="nfl",
            skip_if_unchanged=True,
        )

        # Should have 3 rows now
        history = get_game_state_history("E2E-STATE-GAME-001")
        assert len(history) == 3

        # Step 5: Simulate more clock ticks (no score change)
        for _ in range(3):
            upsert_game_state(
                espn_event_id="E2E-STATE-GAME-001",
                home_score=7,
                away_score=0,
                period=1,
                clock_seconds=Decimal("600"),
                game_status="in_progress",
                league="nfl",
                skip_if_unchanged=True,
            )

        # Still 3 rows (clock ticks ignored)
        history = get_game_state_history("E2E-STATE-GAME-001")
        assert len(history) == 3

        # Step 6: Period change (Q1 -> Q2)
        upsert_game_state(
            espn_event_id="E2E-STATE-GAME-001",
            home_score=7,
            away_score=0,
            period=2,  # New period!
            game_status="in_progress",
            league="nfl",
            skip_if_unchanged=True,
        )

        # Should have 4 rows
        history = get_game_state_history("E2E-STATE-GAME-001")
        assert len(history) == 4

        # Summary: 10+ polls created only 4 rows (vs 10+ without detection)
        # This is the 90%+ row reduction promised by Issue #234

    def test_situation_changes_create_rows(self, db_pool, clean_test_data, setup_e2e_teams):
        """
        E2E: Verify situation field changes (possession, down) create new rows.

        This is critical for football where possession changes are significant
        events that should be recorded.
        """
        from precog.database.crud_operations import game_state_changed

        teams = setup_e2e_teams

        # Clean up any existing test data
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'E2E-SIT-GAME-001'")
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'E2E-SIT-001'")

        venue_id = create_venue(
            espn_venue_id="E2E-SIT-001",
            venue_name="Situation Stadium",
            city="Test City",
            state="TS",
        )

        # Create game in progress
        create_game_state(
            espn_event_id="E2E-SIT-GAME-001",
            home_team_id=teams["kc"]["team_id"],
            away_team_id=teams["lv"]["team_id"],
            venue_id=venue_id,
            home_score=7,
            away_score=7,
            period=2,
            game_status="in_progress",
            league="nfl",
            situation={"possession": "KC", "down": 1, "distance": 10, "yard_line": 25},
        )

        initial_history = get_game_state_history("E2E-SIT-GAME-001")
        assert len(initial_history) == 1

        current = get_current_game_state("E2E-SIT-GAME-001")

        # Situation change: KC advances to 2nd down
        new_situation = {"possession": "KC", "down": 2, "distance": 7, "yard_line": 32}
        changed = game_state_changed(
            current,
            home_score=7,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation=new_situation,
        )
        assert changed is True

        upsert_game_state(
            espn_event_id="E2E-SIT-GAME-001",
            home_score=7,
            away_score=7,
            period=2,
            game_status="in_progress",
            league="nfl",
            situation=new_situation,
            skip_if_unchanged=True,
        )

        # Should have 2 rows
        history = get_game_state_history("E2E-SIT-GAME-001")
        assert len(history) == 2

        # Turnover: Possession changes to LV
        turnover_situation = {"possession": "LV", "down": 1, "distance": 10, "yard_line": 68}
        current = get_current_game_state("E2E-SIT-GAME-001")
        changed = game_state_changed(
            current,
            home_score=7,
            away_score=7,
            period=2,
            game_status="in_progress",
            situation=turnover_situation,
        )
        assert changed is True

        upsert_game_state(
            espn_event_id="E2E-SIT-GAME-001",
            home_score=7,
            away_score=7,
            period=2,
            game_status="in_progress",
            league="nfl",
            situation=turnover_situation,
            skip_if_unchanged=True,
        )

        # Should have 3 rows (possession change is significant)
        history = get_game_state_history("E2E-SIT-GAME-001")
        assert len(history) == 3

    def test_status_transitions_workflow(self, db_pool, clean_test_data, setup_e2e_teams):
        """
        E2E: Verify complete game status transitions create appropriate rows.

        Status progression: pre -> in_progress -> halftime -> in_progress -> final
        """
        teams = setup_e2e_teams

        # Clean up any existing test data
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM game_states WHERE espn_event_id = 'E2E-STATUS-GAME-001'")
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'E2E-STATUS-001'")

        venue_id = create_venue(
            espn_venue_id="E2E-STATUS-001",
            venue_name="Status Stadium",
            city="Test City",
            state="TS",
        )

        # Pre-game
        create_game_state(
            espn_event_id="E2E-STATUS-GAME-001",
            home_team_id=teams["det"]["team_id"],
            away_team_id=teams["chi"]["team_id"],
            venue_id=venue_id,
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        # Game starts
        upsert_game_state(
            espn_event_id="E2E-STATUS-GAME-001",
            home_score=0,
            away_score=0,
            period=1,
            game_status="in_progress",
            league="nfl",
            skip_if_unchanged=True,
        )

        # Halftime
        upsert_game_state(
            espn_event_id="E2E-STATUS-GAME-001",
            home_score=14,
            away_score=10,
            period=2,
            game_status="halftime",
            league="nfl",
            skip_if_unchanged=True,
        )

        # Second half starts
        upsert_game_state(
            espn_event_id="E2E-STATUS-GAME-001",
            home_score=14,
            away_score=10,
            period=3,
            game_status="in_progress",
            league="nfl",
            skip_if_unchanged=True,
        )

        # Game ends
        upsert_game_state(
            espn_event_id="E2E-STATUS-GAME-001",
            home_score=28,
            away_score=21,
            period=4,
            game_status="final",
            league="nfl",
            skip_if_unchanged=True,
        )

        # Verify 5 rows: pre, in_progress, halftime, in_progress, final
        history = get_game_state_history("E2E-STATUS-GAME-001")
        assert len(history) == 5

        # Verify status progression
        statuses = [h["game_status"] for h in reversed(history)]
        assert statuses == ["pre", "in_progress", "halftime", "in_progress", "final"]
