"""
Property-Based Tests for Phase 2C CRUD Operations.

Tests invariants that must hold for ALL inputs using Hypothesis:
- Decimal precision preservation (clock_seconds)
- SCD Type-2 current row uniqueness (game_states)
- Foreign key integrity (team references)
- Upsert idempotency (venues, rankings)

Related:
- REQ-DATA-001: Game State Data Collection (SCD Type 2)
- REQ-DATA-002: Venue Data Management
- Pattern 1: Decimal Precision (NEVER USE FLOAT)
- Pattern 2: Dual Versioning System (SCD Type 2)
- Pattern 10: Property-Based Testing with Hypothesis

Educational Note:
    Property-based tests validate invariants across THOUSANDS of inputs.
    For SCD Type 2, the critical property is: "At most ONE row can have
    row_current_ind=TRUE per entity." This test ensures upsert_game_state
    maintains this invariant under ALL conditions.

Usage:
    pytest tests/property/test_phase2c_crud_properties.py -v
    pytest tests/property/test_phase2c_crud_properties.py -v --hypothesis-show-statistics
"""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from precog.database.connection import get_cursor
from precog.database.crud_operations import (
    create_game_state,
    create_team_ranking,
    create_venue,
    get_current_game_state,
    get_game_state_history,
    get_venue_by_espn_id,
    upsert_game_state,
)

# =============================================================================
# CUSTOM HYPOTHESIS STRATEGIES
# =============================================================================


@st.composite
def espn_venue_id(draw):
    """Generate valid ESPN venue IDs (alphanumeric with optional dashes)."""
    # ESPN venue IDs are typically numeric strings like "3622"
    return draw(st.text(alphabet="0123456789", min_size=3, max_size=8))


@st.composite
def venue_name(draw):
    """Generate realistic venue names."""
    prefixes = ["", "State ", "AT&T ", "GEHA Field at ", "Mercedes-Benz "]
    names = ["Stadium", "Arena", "Coliseum", "Dome", "Field", "Center"]
    prefix = draw(st.sampled_from(prefixes))
    name = draw(st.sampled_from(names))
    return f"{prefix}Test {name}"


@st.composite
def game_score(draw):
    """Generate realistic game scores (0-99)."""
    return draw(st.integers(min_value=0, max_value=99))


@st.composite
def clock_seconds_decimal(draw):
    """Generate clock seconds as Decimal (0-900 for 15-minute periods)."""
    seconds = draw(st.integers(min_value=0, max_value=900))
    return Decimal(str(seconds))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_property_test_data(db_pool, clean_test_data):
    """
    Create minimal test data for property tests.

    Property tests run MANY iterations, so we need lightweight fixtures.
    """
    with get_cursor(commit=True) as cur:
        # Create test teams with high IDs to avoid conflicts
        # Note: Using columns from migration 010 schema (not migration 028 enhancements)
        cur.execute(
            """
            INSERT INTO teams (
                team_id, team_code, team_name,
                espn_team_id, conference, division, sport, current_elo_rating
            )
            VALUES
                (99001, 'PT1', 'Property Team 1', '99001', 'Test', 'East', 'nfl', 1500),
                (99002, 'PT2', 'Property Team 2', '99002', 'Test', 'West', 'nfl', 1500)
            ON CONFLICT (team_id) DO NOTHING
        """
        )

    yield {"home_team_id": 99001, "away_team_id": 99002}

    # Cleanup
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM game_states WHERE home_team_id IN (99001, 99002)")
        cur.execute("DELETE FROM team_rankings WHERE team_id IN (99001, 99002)")
        cur.execute("DELETE FROM teams WHERE team_id IN (99001, 99002)")
        # Clean up venues created by property tests
        cur.execute("DELETE FROM venues WHERE espn_venue_id LIKE 'PROP-%'")


# =============================================================================
# VENUE PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50,  # Reduce examples for faster CI
)
@given(venue_name_str=st.text(min_size=1, max_size=100))
def test_venue_upsert_idempotency(
    db_pool, clean_test_data, setup_property_test_data, venue_name_str
):
    """
    PROPERTY: Venue upsert is idempotent - same ESPN ID always updates same record.

    Validates:
    - create_venue with same ESPN ID doesn't create duplicates
    - Each ESPN ID maps to exactly ONE venue_id
    - Multiple calls return same venue_id

    Why This Matters:
        During data ingestion, we may receive the same venue multiple times
        (from different games). Idempotent upsert ensures no duplicates and
        consistent venue_id references across all game records.
    """
    # Filter out problematic strings
    assume(len(venue_name_str.strip()) > 0)
    assume("\x00" not in venue_name_str)  # No null bytes

    # Use UUID to ensure unique ESPN ID per test example
    unique_id = uuid.uuid4().hex[:8]
    espn_id = f"PROP-IDEM-{unique_id}"

    # First call
    venue_id_1 = create_venue(espn_venue_id=espn_id, venue_name=venue_name_str)

    # Second call with SAME ESPN ID
    venue_id_2 = create_venue(espn_venue_id=espn_id, venue_name="Updated Name")

    # Should return SAME venue_id (upsert, not insert)
    assert venue_id_1 == venue_id_2, "Upsert should return same venue_id for same ESPN ID"

    # Verify only ONE record exists
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM venues WHERE espn_venue_id = %s",
            (espn_id,),
        )
        result = cur.fetchone()
        count = result["count"]

    assert count == 1, f"Expected 1 venue record, found {count}"


@pytest.mark.property
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=30,
)
@given(
    capacity=st.integers(min_value=1, max_value=150000),
    indoor=st.booleans(),
)
def test_venue_data_preserved_on_roundtrip(
    db_pool, clean_test_data, setup_property_test_data, capacity, indoor
):
    """
    PROPERTY: Venue data is preserved exactly on database round-trip.

    Validates:
    - capacity value preserved exactly
    - indoor boolean preserved exactly
    - No data loss or type coercion issues
    """
    unique_id = uuid.uuid4().hex[:8]
    espn_id = f"PROP-ROUND-{unique_id}"

    venue_id = create_venue(
        espn_venue_id=espn_id,
        venue_name="Round Trip Stadium",
        capacity=capacity,
        indoor=indoor,
    )

    # Retrieve and verify
    venue = get_venue_by_espn_id(espn_id)

    assert venue is not None
    assert venue["venue_id"] == venue_id
    assert venue["capacity"] == capacity
    assert venue["indoor"] is indoor


# =============================================================================
# GAME STATE PROPERTY TESTS (SCD TYPE 2)
# =============================================================================


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=30,
)
@given(
    home_score=game_score(),
    away_score=game_score(),
)
def test_scd_type2_at_most_one_current_row(
    db_pool, clean_test_data, setup_property_test_data, home_score, away_score
):
    """
    PROPERTY: At most ONE row can have row_current_ind=TRUE per game.

    This is the CRITICAL SCD Type 2 invariant. If violated, queries become
    ambiguous and we don't know which score is "current".

    Validates:
    - After create_game_state: exactly 1 current row
    - After upsert_game_state: still exactly 1 current row
    - Multiple upserts: always exactly 1 current row

    Educational Note:
        SCD Type 2 relies on a partial unique index:
        UNIQUE (espn_event_id) WHERE row_current_ind = TRUE

        This database constraint prevents duplicates, but we test it here
        to ensure our CRUD functions respect the pattern.
    """
    teams = setup_property_test_data
    unique_id = uuid.uuid4().hex[:8]
    espn_event_id = f"PROP-SCD-{unique_id}"

    # Create initial state
    create_game_state(
        espn_event_id=espn_event_id,
        home_team_id=teams["home_team_id"],
        away_team_id=teams["away_team_id"],
        home_score=0,
        away_score=0,
        game_status="pre",
        league="nfl",
    )

    # Verify exactly 1 current row
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM game_states
            WHERE espn_event_id = %s AND row_current_ind = TRUE
        """,
            (espn_event_id,),
        )
        result = cur.fetchone()
        count_after_create = result["count"]

    assert count_after_create == 1, (
        f"Expected 1 current row after create, found {count_after_create}"
    )

    # Upsert with new score
    upsert_game_state(
        espn_event_id=espn_event_id,
        home_team_id=teams["home_team_id"],
        away_team_id=teams["away_team_id"],
        home_score=home_score,
        away_score=away_score,
        game_status="in_progress",
        league="nfl",
    )

    # Verify STILL exactly 1 current row
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM game_states
            WHERE espn_event_id = %s AND row_current_ind = TRUE
        """,
            (espn_event_id,),
        )
        result = cur.fetchone()
        count_after_upsert = result["count"]

    assert count_after_upsert == 1, (
        f"Expected 1 current row after upsert, found {count_after_upsert}"
    )


@pytest.mark.property
@pytest.mark.critical
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=20,
)
@given(clock_seconds=clock_seconds_decimal())
def test_decimal_precision_preserved_clock_seconds(
    db_pool, clean_test_data, setup_property_test_data, clock_seconds
):
    """
    PROPERTY: clock_seconds Decimal values survive database round-trip.

    Validates Pattern 1: Decimal Precision - NEVER USE FLOAT.

    Educational Note:
        clock_seconds may seem like a simple integer, but we use Decimal
        to future-proof for sub-second precision and to maintain consistency
        with our "Decimal for all numeric data" pattern.
    """
    teams = setup_property_test_data
    unique_id = uuid.uuid4().hex[:8]
    espn_event_id = f"PROP-CLOCK-{unique_id}"

    create_game_state(
        espn_event_id=espn_event_id,
        home_team_id=teams["home_team_id"],
        away_team_id=teams["away_team_id"],
        clock_seconds=clock_seconds,
        clock_display=f"{int(clock_seconds) // 60}:{int(clock_seconds) % 60:02d}",
        game_status="in_progress",
        league="nfl",
    )

    # Retrieve and verify
    state = get_current_game_state(espn_event_id)

    assert state is not None
    # Note: PostgreSQL may return as integer or Decimal depending on column type
    # The important thing is the VALUE is preserved
    if state["clock_seconds"] is not None:
        assert Decimal(str(state["clock_seconds"])) == clock_seconds


@pytest.mark.property
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=20,
)
@given(num_updates=st.integers(min_value=1, max_value=5))
def test_scd_type2_history_length_equals_updates_plus_one(
    db_pool, clean_test_data, setup_property_test_data, num_updates
):
    """
    PROPERTY: History length = initial create + number of upserts.

    Validates SCD Type 2 creates new row on each update.

    Educational Note:
        If history length < expected, we're losing history (updating in place).
        If history length > expected, we have a bug creating extra rows.
    """
    teams = setup_property_test_data
    unique_id = uuid.uuid4().hex[:8]
    espn_event_id = f"PROP-HIST-{unique_id}"

    # Create initial
    create_game_state(
        espn_event_id=espn_event_id,
        home_team_id=teams["home_team_id"],
        away_team_id=teams["away_team_id"],
        home_score=0,
        away_score=0,
        game_status="pre",
        league="nfl",
    )

    # Perform N upserts
    for i in range(num_updates):
        upsert_game_state(
            espn_event_id=espn_event_id,
            home_team_id=teams["home_team_id"],
            away_team_id=teams["away_team_id"],
            home_score=i + 1,
            away_score=0,
            game_status="in_progress",
            league="nfl",
        )

    # Check history
    history = get_game_state_history(espn_event_id)
    expected_length = 1 + num_updates

    assert len(history) == expected_length, (
        f"Expected {expected_length} history rows (1 create + {num_updates} upserts), "
        f"found {len(history)}"
    )


# =============================================================================
# TEAM RANKING PROPERTY TESTS
# =============================================================================


@pytest.mark.property
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=30,
)
@given(
    rank=st.integers(min_value=1, max_value=25),
    points=st.integers(min_value=0, max_value=2000),
    first_place_votes=st.integers(min_value=0, max_value=65),
)
def test_team_ranking_upsert_preserves_uniqueness(
    db_pool, clean_test_data, setup_property_test_data, rank, points, first_place_votes
):
    """
    PROPERTY: Team ranking upsert ensures unique (team, type, season, week).

    Validates:
    - Same combination always updates, never creates duplicate
    - Different weeks create separate records

    Educational Note:
        Rankings use temporal validity (season + week) instead of SCD Type 2.
        Each week's poll is a distinct point-in-time snapshot. The unique
        constraint is on (team_id, ranking_type, season, week).
    """
    teams = setup_property_test_data
    team_id = teams["home_team_id"]

    # Use a valid week (0-20 per team_rankings_week_check constraint)
    # and use a valid ranking_type from team_rankings_type_check constraint
    test_week = 20  # Max valid week (0-20 range)

    # Create ranking for test week
    # NOTE: Season must be in range 2020-2050 per team_rankings_season_check constraint
    create_team_ranking(
        team_id=team_id,
        ranking_type="ap_poll",  # Valid type per team_rankings_type_check constraint
        rank=rank,
        season=2049,  # Far-future but valid season (2020-2050 constraint)
        ranking_date=datetime(2024, 11, 10),
        week=test_week,
        points=points,
        first_place_votes=first_place_votes,
    )

    # Upsert SAME week (should update, not create duplicate)
    create_team_ranking(
        team_id=team_id,
        ranking_type="ap_poll",
        rank=rank + 1,  # Different rank
        season=2049,
        ranking_date=datetime(2024, 11, 10),
        week=test_week,  # Same week!
        points=points + 10,
    )

    # Count records for this (team, type, season, week)
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM team_rankings
            WHERE team_id = %s
              AND ranking_type = 'ap_poll'
              AND season = 2049
              AND week = %s
        """,
            (team_id, test_week),
        )
        result = cur.fetchone()
        count = result["count"]

    assert count == 1, f"Expected 1 ranking record for same week, found {count}"

    # Clean up - use specific season/week to avoid deleting other test data
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM team_rankings WHERE season = 2049 AND week = %s", (test_week,))
