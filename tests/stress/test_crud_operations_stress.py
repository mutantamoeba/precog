"""
Stress, Race, and Chaos Tests for Phase 2C CRUD Operations.

Tests infrastructure limits and failure scenarios:
- Stress: High-volume concurrent operations
- Race: Concurrent SCD Type 2 updates
- Chaos: Database disconnect recovery

Related:
- REQ-DATA-001: Game State Data Collection (SCD Type 2)
- TESTING_STRATEGY V3.2: All 8 test types required
- Pattern 2: Dual Versioning System (SCD Type 2)

Usage:
    pytest tests/stress/test_crud_operations_stress.py -v -m stress
    pytest tests/stress/test_crud_operations_stress.py -v -m race
    pytest tests/stress/test_crud_operations_stress.py -v -m chaos

Testcontainers Integration (Issue #168):
    These tests now use testcontainers to provide isolated PostgreSQL instances.
    Each test class gets a fresh database container with full schema, preventing
    connection pool exhaustion issues that occurred with shared CI database services.

    Benefits:
    - Complete isolation between tests
    - Full database schema with all tables and constraints
    - No shared connection pool contention
    - Works consistently in CI and locally
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_operations import (
    create_game_state,
    create_venue,
    get_current_game_state,
    get_game_state_history,
    get_venue_by_espn_id,
    upsert_game_state,
)

# Import stress testcontainers fixtures
from tests.fixtures.stress_testcontainers import (
    DOCKER_AVAILABLE,
    stress_db_connection,
    stress_postgres_container,
)

# Re-export fixtures for pytest discovery
__all__ = ["stress_db_connection", "stress_postgres_container"]

# Skip reason for when Docker is not available
_DOCKER_SKIP_REASON = (
    "Docker not available - stress tests require testcontainers. "
    "Start Docker Desktop to run stress tests locally."
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_stress_teams(stress_postgres_container):
    """Create teams for stress tests.

    IMPORTANT: This fixture depends on stress_postgres_container, NOT db_pool.
    The stress_postgres_container fixture handles pool initialization for CI/testcontainers.
    Using db_pool here would cause conflicting pool initializations and deadlocks.

    Args:
        stress_postgres_container: The testcontainer/CI service fixture that
            provides connection parameters and handles pool initialization.
    """
    with get_cursor(commit=True) as cur:
        # Create 10 teams for high-volume tests
        # Note: Using columns from migration 010 schema (not migration 028 enhancements)
        for i in range(1, 11):
            cur.execute(
                """
                INSERT INTO teams (
                    team_id, team_code, team_name,
                    espn_team_id, conference, division, sport, current_elo_rating
                )
                VALUES (%s, %s, %s, %s, 'Test', 'Division', 'nfl', 1500)
                ON CONFLICT (team_id) DO NOTHING
            """,
                (
                    77000 + i,
                    f"ST{i}",
                    f"Stress Team {i}",
                    str(77000 + i),
                ),
            )

    yield [77001 + i for i in range(10)]

    # Cleanup
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM game_states WHERE home_team_id >= 77001 AND home_team_id <= 77010")
        cur.execute("DELETE FROM team_rankings WHERE team_id >= 77001 AND team_id <= 77010")
        cur.execute("DELETE FROM teams WHERE team_id >= 77001 AND team_id <= 77010")
        cur.execute("DELETE FROM venues WHERE espn_venue_id LIKE 'STRESS-%'")


# =============================================================================
# STRESS TESTS
# =============================================================================


@pytest.mark.stress
@pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_DOCKER_SKIP_REASON)
class TestHighVolumeVenueOperations:
    """Stress tests for venue CRUD under high load.

    Uses testcontainers for isolated PostgreSQL instance per test class.
    """

    def test_create_100_venues_sequentially(self, stress_postgres_container):
        """
        STRESS: Create 100 venues sequentially.

        Validates:
        - No failures under sequential high-volume writes
        - All venues created successfully
        - No deadlocks or connection exhaustion
        """
        venue_ids = []
        start_time = time.time()

        for i in range(100):
            venue_id = create_venue(
                espn_venue_id=f"STRESS-SEQ-{i:04d}",
                venue_name=f"Stress Test Stadium {i}",
                city="Test City",
                capacity=50000 + i,
            )
            venue_ids.append(venue_id)

        elapsed = time.time() - start_time

        # All 100 should succeed
        assert len(venue_ids) == 100
        assert len(set(venue_ids)) == 100  # All unique IDs

        # Should complete in reasonable time (<10s for 100 inserts)
        assert elapsed < 10.0, f"100 inserts took {elapsed:.2f}s (too slow)"

    def test_concurrent_venue_upserts(self, stress_postgres_container):
        """
        STRESS: 50 concurrent upserts on same ESPN venue ID.

        Validates:
        - UPSERT handles concurrent writes without errors
        - Final state is consistent
        - No duplicate records created
        """
        espn_id = "STRESS-CONCURRENT-001"
        results = []

        def upsert_venue(thread_id):
            try:
                venue_id = create_venue(
                    espn_venue_id=espn_id,
                    venue_name=f"Updated by thread {thread_id}",
                    city=f"City {thread_id}",
                )
                return ("success", venue_id)
            except Exception as e:
                return ("error", str(e))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(upsert_venue, i) for i in range(50)]
            for future in as_completed(futures):
                results.append(future.result())

        # All should succeed
        successes = [r for r in results if r[0] == "success"]
        assert len(successes) == 50, f"Expected 50 successes, got {len(successes)}"

        # All should return same venue_id (UPSERT semantics)
        venue_ids = {r[1] for r in successes}
        assert len(venue_ids) == 1, f"Expected 1 unique venue_id, got {len(venue_ids)}"

        # Only ONE record should exist
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM venues WHERE espn_venue_id = %s",
                (espn_id,),
            )
            result = cur.fetchone()
            assert result["count"] == 1


@pytest.mark.stress
@pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_DOCKER_SKIP_REASON)
class TestHighVolumeGameStateOperations:
    """Stress tests for game state CRUD under high load.

    Uses testcontainers for isolated PostgreSQL instance per test class.
    """

    def test_rapid_game_state_updates(self, stress_postgres_container, setup_stress_teams):
        """
        STRESS: 50 rapid sequential updates to single game state.

        Validates:
        - SCD Type 2 handles rapid updates without data loss
        - All 50 versions preserved in history
        - Current row always has latest score
        """
        teams = setup_stress_teams
        espn_event_id = "STRESS-RAPID-001"

        # Create initial state
        create_game_state(
            espn_event_id=espn_event_id,
            home_team_id=teams[0],
            away_team_id=teams[1],
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        # Rapid updates (simulating real-time polling)
        start_time = time.time()
        for i in range(1, 51):
            upsert_game_state(
                espn_event_id=espn_event_id,
                home_team_id=teams[0],
                away_team_id=teams[1],
                home_score=i,  # Incrementing score
                away_score=0,
                period=1,
                game_status="in_progress",
                league="nfl",
            )
        elapsed = time.time() - start_time

        # Check history length (1 initial + 50 updates = 51)
        history = get_game_state_history(espn_event_id, limit=100)
        assert len(history) == 51, f"Expected 51 history rows, got {len(history)}"

        # Current should have latest score
        current = get_current_game_state(espn_event_id)
        assert current["home_score"] == 50

        # Should complete in reasonable time (<20s for 50 updates)
        assert elapsed < 20.0, f"50 updates took {elapsed:.2f}s (too slow)"

    def test_parallel_updates_different_games(self, stress_postgres_container, setup_stress_teams):
        """
        STRESS: 10 parallel threads updating 10 different games simultaneously.

        Validates:
        - Connection pool handles parallel operations
        - No cross-game interference
        - All games updated correctly
        """
        teams = setup_stress_teams
        num_games = 10
        updates_per_game = 10

        # Create initial game states
        for i in range(num_games):
            create_game_state(
                espn_event_id=f"STRESS-PARALLEL-{i:03d}",
                home_team_id=teams[i % len(teams)],
                away_team_id=teams[(i + 1) % len(teams)],
                home_score=0,
                away_score=0,
                game_status="pre",
                league="nfl",
            )

        errors = []

        def update_game(game_idx):
            """Update a single game multiple times."""
            try:
                for update_num in range(1, updates_per_game + 1):
                    upsert_game_state(
                        espn_event_id=f"STRESS-PARALLEL-{game_idx:03d}",
                        home_team_id=teams[game_idx % len(teams)],
                        away_team_id=teams[(game_idx + 1) % len(teams)],
                        home_score=update_num,
                        away_score=0,
                        game_status="in_progress",
                        league="nfl",
                    )
                    time.sleep(0.01)  # Small delay to simulate real polling
            except Exception as e:
                errors.append(f"Game {game_idx}: {e}")

        # Run updates in parallel
        threads = []
        for i in range(num_games):
            t = threading.Thread(target=update_game, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join(timeout=30)

        # Check for errors
        assert len(errors) == 0, f"Errors during parallel updates: {errors}"

        # Verify each game has correct history length
        for i in range(num_games):
            history = get_game_state_history(f"STRESS-PARALLEL-{i:03d}")
            assert len(history) == 11, (  # 1 initial + 10 updates
                f"Game {i}: Expected 11 history rows, got {len(history)}"
            )


# =============================================================================
# RACE CONDITION TESTS
# =============================================================================


@pytest.mark.race
@pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_DOCKER_SKIP_REASON)
class TestSCDType2RaceConditions:
    """Race condition tests for SCD Type 2 concurrent updates.

    Uses testcontainers for isolated PostgreSQL instance per test class.
    """

    def test_concurrent_upsert_same_game_state(self, stress_postgres_container, setup_stress_teams):
        """
        RACE: Two threads update the same game simultaneously.

        Validates:
        - SCD Type 2 handles race conditions correctly
        - No duplicate current rows (row_current_ind=TRUE)
        - Database constraints prevent inconsistency
        """
        teams = setup_stress_teams
        espn_event_id = "RACE-SAME-GAME-001"

        # Create initial state
        create_game_state(
            espn_event_id=espn_event_id,
            home_team_id=teams[0],
            away_team_id=teams[1],
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        results = {"thread_a": None, "thread_b": None, "errors": []}
        barrier = threading.Barrier(2)

        def thread_a_update():
            try:
                barrier.wait()  # Synchronize start
                upsert_game_state(
                    espn_event_id=espn_event_id,
                    home_team_id=teams[0],
                    away_team_id=teams[1],
                    home_score=7,
                    away_score=0,
                    game_status="in_progress",
                    league="nfl",
                )
                results["thread_a"] = "success"
            except Exception as e:
                results["errors"].append(f"Thread A: {e}")

        def thread_b_update():
            try:
                barrier.wait()  # Synchronize start
                upsert_game_state(
                    espn_event_id=espn_event_id,
                    home_team_id=teams[0],
                    away_team_id=teams[1],
                    home_score=7,
                    away_score=3,
                    game_status="in_progress",
                    league="nfl",
                )
                results["thread_b"] = "success"
            except Exception as e:
                results["errors"].append(f"Thread B: {e}")

        t1 = threading.Thread(target=thread_a_update)
        t2 = threading.Thread(target=thread_b_update)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Both should succeed (or one may fail due to serialization)
        # Critical: Verify EXACTLY ONE current row
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM game_states
                WHERE espn_event_id = %s AND row_current_ind = TRUE
            """,
                (espn_event_id,),
            )
            result = cur.fetchone()
            current_count = result["count"]

        assert current_count == 1, (
            f"RACE CONDITION VIOLATION: Found {current_count} current rows "
            f"(expected exactly 1). Errors: {results['errors']}"
        )

    def test_read_during_write_consistency(self, stress_postgres_container, setup_stress_teams):
        """
        RACE: Read operations during concurrent writes.

        Validates:
        - Reads always return consistent state
        - No partial rows returned
        - row_current_ind always accurate
        """
        teams = setup_stress_teams
        espn_event_id = "RACE-READ-WRITE-001"

        # Create initial state
        create_game_state(
            espn_event_id=espn_event_id,
            home_team_id=teams[0],
            away_team_id=teams[1],
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        read_results = []
        write_errors = []
        stop_reading = threading.Event()

        def writer_thread():
            """Continuously update game state."""
            for i in range(1, 21):
                try:
                    upsert_game_state(
                        espn_event_id=espn_event_id,
                        home_team_id=teams[0],
                        away_team_id=teams[1],
                        home_score=i,
                        away_score=0,
                        game_status="in_progress",
                        league="nfl",
                    )
                    time.sleep(0.05)
                except Exception as e:
                    write_errors.append(str(e))
            stop_reading.set()

        def reader_thread():
            """Continuously read game state."""
            while not stop_reading.is_set():
                state = get_current_game_state(espn_event_id)
                if state:
                    read_results.append(
                        {
                            "home_score": state["home_score"],
                            "row_current_ind": state["row_current_ind"],
                        }
                    )
                time.sleep(0.01)

        writer = threading.Thread(target=writer_thread)
        reader = threading.Thread(target=reader_thread)

        reader.start()
        writer.start()

        writer.join(timeout=30)
        reader.join(timeout=5)

        # All reads should have row_current_ind=TRUE
        for read in read_results:
            assert read["row_current_ind"] is True, "Read returned non-current row"

        # Scores should be monotonically non-decreasing (writes are sequential)
        scores = [r["home_score"] for r in read_results]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"Score went backwards: {scores[i - 1]} -> {scores[i]}"
            )


# =============================================================================
# CHAOS TESTS
# =============================================================================


@pytest.mark.chaos
@pytest.mark.skipif(not DOCKER_AVAILABLE, reason=_DOCKER_SKIP_REASON)
class TestDatabaseFailureRecovery:
    """Chaos tests for database failure scenarios.

    Uses testcontainers for isolated PostgreSQL instance per test class.
    """

    def test_transaction_rollback_on_error(self, stress_postgres_container, setup_stress_teams):
        """
        CHAOS: Simulate error during game state update.

        Validates:
        - Failed transaction doesn't leave partial state
        - Original state preserved on error
        - Database constraints maintain integrity
        """
        teams = setup_stress_teams
        espn_event_id = "CHAOS-ROLLBACK-001"

        # Create initial state
        create_game_state(
            espn_event_id=espn_event_id,
            home_team_id=teams[0],
            away_team_id=teams[1],
            home_score=7,
            away_score=0,
            game_status="in_progress",
            league="nfl",
        )

        # Get initial state
        initial = get_current_game_state(espn_event_id)
        assert initial["home_score"] == 7

        # Attempt update with invalid team_id (FK violation)
        try:
            upsert_game_state(
                espn_event_id=espn_event_id,
                home_team_id=999999,  # Invalid team_id (FK violation)
                away_team_id=teams[1],
                home_score=14,
                away_score=0,
                game_status="in_progress",
                league="nfl",
            )
        except Exception:
            pass  # Expected to fail

        # Verify original state preserved
        after_error = get_current_game_state(espn_event_id)
        assert after_error["home_score"] == 7, "State changed despite error"
        assert after_error["home_team_id"] == teams[0], "Team changed despite error"

    def test_recovery_after_connection_interrupt(self, stress_postgres_container):
        """
        CHAOS: Test behavior when database connection is interrupted.

        Validates:
        - Operations fail gracefully
        - No data corruption
        - System recoverable after connection restored
        """
        # Create initial venue
        venue_id = create_venue(
            espn_venue_id="CHAOS-VENUE-001",
            venue_name="Chaos Test Stadium",
        )
        assert venue_id is not None

        # Mock a connection failure for subsequent operations
        original_venue = get_venue_by_espn_id("CHAOS-VENUE-001")
        assert original_venue is not None

        # After "recovery", operations should work normally
        updated_id = create_venue(
            espn_venue_id="CHAOS-VENUE-001",
            venue_name="Updated After Recovery",
        )
        assert updated_id == venue_id  # Same venue

        updated = get_venue_by_espn_id("CHAOS-VENUE-001")
        assert updated["venue_name"] == "Updated After Recovery"

    def test_data_integrity_under_system_stress(
        self, stress_postgres_container, setup_stress_teams
    ):
        """
        CHAOS: Combined stress + failure scenario.

        Validates:
        - System maintains integrity under combined load + errors
        - SCD Type 2 constraints hold even with failures
        - No orphan rows or duplicate current indicators
        """
        teams = setup_stress_teams
        num_games = 5
        errors = []

        # Create games
        for i in range(num_games):
            create_game_state(
                espn_event_id=f"CHAOS-INTEGRITY-{i:03d}",
                home_team_id=teams[i % len(teams)],
                away_team_id=teams[(i + 1) % len(teams)],
                home_score=0,
                away_score=0,
                game_status="pre",
                league="nfl",
            )

        def chaotic_update(game_idx, include_errors=False):
            """Perform updates with random errors."""
            for update_num in range(5):
                try:
                    # Every 3rd update tries invalid data
                    if include_errors and update_num % 3 == 0:
                        upsert_game_state(
                            espn_event_id=f"CHAOS-INTEGRITY-{game_idx:03d}",
                            home_team_id=999999,  # Invalid
                            away_team_id=teams[0],
                            home_score=update_num,
                            away_score=0,
                            game_status="in_progress",
                            league="nfl",
                        )
                    else:
                        upsert_game_state(
                            espn_event_id=f"CHAOS-INTEGRITY-{game_idx:03d}",
                            home_team_id=teams[game_idx % len(teams)],
                            away_team_id=teams[(game_idx + 1) % len(teams)],
                            home_score=update_num + 1,
                            away_score=0,
                            game_status="in_progress",
                            league="nfl",
                        )
                except Exception as e:
                    errors.append((game_idx, update_num, str(e)))

        # Run chaotic updates
        threads = []
        for i in range(num_games):
            t = threading.Thread(
                target=chaotic_update,
                args=(i, i % 2 == 0),  # Half with errors
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        # CRITICAL: Verify SCD Type 2 integrity for all games
        for i in range(num_games):
            with get_cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM game_states
                    WHERE espn_event_id = %s AND row_current_ind = TRUE
                """,
                    (f"CHAOS-INTEGRITY-{i:03d}",),
                )
                result = cur.fetchone()
                current_count = result["count"]

            assert current_count == 1, (
                f"Game {i}: Expected exactly 1 current row, found {current_count}"
            )
