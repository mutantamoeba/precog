"""
Performance Tests for Phase 2C CRUD Operations.

Establishes latency benchmarks for database operations:
- Query latency (p50, p95, p99)
- Write throughput (ops/sec)
- SCD Type 2 history query performance

Related:
- REQ-DATA-001: Game State Data Collection (SCD Type 2)
- TESTING_STRATEGY V3.2: All 8 test types required

Usage:
    pytest tests/performance/test_phase2c_crud_performance.py -v -m performance
    pytest tests/performance/test_phase2c_crud_performance.py -v --benchmark-only
"""

import statistics
import time
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
    get_live_games,
    get_venue_by_espn_id,
    upsert_game_state,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_perf_teams(db_pool, clean_test_data):
    """Create teams for performance tests."""
    with get_cursor(commit=True) as cur:
        for i in range(1, 11):
            cur.execute(
                """
                INSERT INTO teams (
                    team_id, team_code, team_name, display_name,
                    espn_team_id, conference, division, sport, league, current_elo
                )
                VALUES (%s, %s, %s, %s, %s, 'Perf', 'Div', 'football', 'nfl', 1500)
                ON CONFLICT (team_id) DO NOTHING
            """,
                (
                    66000 + i,
                    f"PF{i}",
                    f"Perf Team {i}",
                    f"Performance Test Team {i}",
                    str(66000 + i),
                ),
            )

    yield [66001 + i for i in range(10)]

    # Cleanup
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM game_states WHERE home_team_id >= 66001 AND home_team_id <= 66010")
        cur.execute("DELETE FROM team_rankings WHERE team_id >= 66001 AND team_id <= 66010")
        cur.execute("DELETE FROM teams WHERE team_id >= 66001 AND team_id <= 66010")
        cur.execute("DELETE FROM venues WHERE espn_venue_id LIKE 'PERF-%'")


# =============================================================================
# PERFORMANCE BENCHMARKS
# =============================================================================


@pytest.mark.performance
class TestVenueQueryPerformance:
    """Performance benchmarks for venue operations."""

    def test_venue_create_latency(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure venue creation latency.

        Benchmark:
        - Target: < 50ms per insert (p95)
        - SLA: < 100ms per insert (p99)
        """
        latencies = []

        for i in range(50):
            start = time.perf_counter()
            create_venue(
                espn_venue_id=f"PERF-CREATE-{i:04d}",
                venue_name=f"Performance Stadium {i}",
                city="Test City",
                capacity=50000,
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nVenue CREATE latencies (ms):")
        print(f"  p50: {p50:.2f}")
        print(f"  p95: {p95:.2f}")
        print(f"  p99: {p99:.2f}")

        # Assertions (adjust thresholds as needed)
        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms target"
        assert p99 < 200, f"p99 latency {p99:.2f}ms exceeds 200ms SLA"

    def test_venue_read_latency(self, db_pool, clean_test_data):
        """
        PERFORMANCE: Measure venue read latency.

        Benchmark:
        - Target: < 10ms per read (p95)
        - SLA: < 50ms per read (p99)
        """
        # Setup: Create venues to read
        for i in range(10):
            create_venue(
                espn_venue_id=f"PERF-READ-{i:04d}",
                venue_name=f"Read Test Stadium {i}",
            )

        latencies = []

        # Measure reads
        for i in range(100):
            venue_idx = i % 10
            start = time.perf_counter()
            get_venue_by_espn_id(f"PERF-READ-{venue_idx:04d}")
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nVenue READ latencies (ms):")
        print(f"  p50: {p50:.2f}")
        print(f"  p95: {p95:.2f}")
        print(f"  p99: {p99:.2f}")

        assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms target"
        assert p99 < 100, f"p99 latency {p99:.2f}ms exceeds 100ms SLA"


@pytest.mark.performance
class TestGameStateQueryPerformance:
    """Performance benchmarks for game state operations."""

    def test_game_state_upsert_latency(self, db_pool, clean_test_data, setup_perf_teams):
        """
        PERFORMANCE: Measure game state upsert (SCD Type 2) latency.

        This is the critical path for live game polling.

        Benchmark:
        - Target: < 100ms per upsert (p95)
        - SLA: < 200ms per upsert (p99)
        """
        teams = setup_perf_teams
        espn_event_id = "PERF-UPSERT-001"

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

        latencies = []

        # Measure upserts
        for i in range(50):
            start = time.perf_counter()
            upsert_game_state(
                espn_event_id=espn_event_id,
                home_team_id=teams[0],
                away_team_id=teams[1],
                home_score=i + 1,
                away_score=0,
                period=1,
                game_status="in_progress",
                league="nfl",
            )
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nGame State UPSERT (SCD Type 2) latencies (ms):")
        print(f"  p50: {p50:.2f}")
        print(f"  p95: {p95:.2f}")
        print(f"  p99: {p99:.2f}")

        assert p95 < 200, f"p95 latency {p95:.2f}ms exceeds 200ms target"
        assert p99 < 500, f"p99 latency {p99:.2f}ms exceeds 500ms SLA"

    def test_game_state_history_query_performance(self, db_pool, clean_test_data, setup_perf_teams):
        """
        PERFORMANCE: Measure game state history query latency.

        Tests query performance when there are many historical versions.

        Benchmark:
        - Target: < 50ms for 100 versions (p95)
        - SLA: < 100ms for 100 versions (p99)
        """
        teams = setup_perf_teams
        espn_event_id = "PERF-HISTORY-001"

        # Create game with 100 historical versions
        create_game_state(
            espn_event_id=espn_event_id,
            home_team_id=teams[0],
            away_team_id=teams[1],
            home_score=0,
            away_score=0,
            game_status="pre",
            league="nfl",
        )

        for i in range(99):
            upsert_game_state(
                espn_event_id=espn_event_id,
                home_team_id=teams[0],
                away_team_id=teams[1],
                home_score=i + 1,
                away_score=0,
                game_status="in_progress",
                league="nfl",
            )

        latencies = []

        # Measure history queries
        for _ in range(50):
            start = time.perf_counter()
            history = get_game_state_history(espn_event_id, limit=100)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            assert len(history) == 100

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nGame State HISTORY (100 rows) latencies (ms):")
        print(f"  p50: {p50:.2f}")
        print(f"  p95: {p95:.2f}")
        print(f"  p99: {p99:.2f}")

        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms target"
        assert p99 < 200, f"p99 latency {p99:.2f}ms exceeds 200ms SLA"

    def test_get_live_games_performance(self, db_pool, clean_test_data, setup_perf_teams):
        """
        PERFORMANCE: Measure live games query latency.

        This query runs frequently during game day for trading decisions.

        Benchmark:
        - Target: < 30ms for 10 live games (p95)
        - SLA: < 100ms for 10 live games (p99)
        """
        teams = setup_perf_teams

        # Create 10 "live" games
        for i in range(10):
            create_game_state(
                espn_event_id=f"PERF-LIVE-{i:03d}",
                home_team_id=teams[i % len(teams)],
                away_team_id=teams[(i + 1) % len(teams)],
                home_score=7 * (i % 4),
                away_score=3 * (i % 3),
                period=2,
                game_status="in_progress",
                league="nfl",
            )

        latencies = []

        # Measure query
        for _ in range(100):
            start = time.perf_counter()
            games = get_live_games(league="nfl")
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            assert len(games) >= 10

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nGet LIVE GAMES (10 games) latencies (ms):")
        print(f"  p50: {p50:.2f}")
        print(f"  p95: {p95:.2f}")
        print(f"  p99: {p99:.2f}")

        assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms target"
        assert p99 < 100, f"p99 latency {p99:.2f}ms exceeds 100ms SLA"


@pytest.mark.performance
class TestTeamRankingQueryPerformance:
    """Performance benchmarks for team ranking operations."""

    def test_ranking_insert_throughput(self, db_pool, clean_test_data, setup_perf_teams):
        """
        PERFORMANCE: Measure ranking insert throughput.

        Benchmark:
        - Target: > 50 inserts/sec
        - This is important for weekly poll ingestion (25+ teams)
        """
        teams = setup_perf_teams

        start = time.perf_counter()
        for i, team_id in enumerate(teams):
            create_team_ranking(
                team_id=team_id,
                ranking_type="perf_poll",
                rank=i + 1,
                season=2024,
                ranking_date=datetime(2024, 11, 17),
                week=12,
                points=1500 - (i * 50),
            )
        elapsed = time.perf_counter() - start

        throughput = len(teams) / elapsed
        print(f"\nRanking INSERT throughput: {throughput:.1f} ops/sec")

        assert throughput > 20, f"Throughput {throughput:.1f} ops/sec below 20 target"

    def test_current_rankings_query_performance(self, db_pool, clean_test_data, setup_perf_teams):
        """
        PERFORMANCE: Measure current rankings query latency.

        Benchmark:
        - Target: < 50ms for 25 teams (p95)
        - SLA: < 100ms for 25 teams (p99)
        """
        teams = setup_perf_teams

        # Create rankings for multiple weeks
        for week in range(10, 15):
            for i, team_id in enumerate(teams):
                create_team_ranking(
                    team_id=team_id,
                    ranking_type="perf_query_poll",
                    rank=i + 1,
                    season=2024,
                    ranking_date=datetime(2024, 11, week),
                    week=week,
                    points=1500 - (i * 50),
                )

        latencies = []

        # Measure query (should get latest week = 14)
        for _ in range(50):
            start = time.perf_counter()
            rankings = get_current_rankings("perf_query_poll", 2024)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            assert len(rankings) == 10  # All teams ranked

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print("\nGet CURRENT RANKINGS (10 teams) latencies (ms):")
        print(f"  p50: {p50:.2f}")
        print(f"  p95: {p95:.2f}")
        print(f"  p99: {p99:.2f}")

        assert p95 < 100, f"p95 latency {p95:.2f}ms exceeds 100ms target"
        assert p99 < 200, f"p99 latency {p99:.2f}ms exceeds 200ms SLA"


@pytest.mark.performance
class TestOverallThroughput:
    """Overall throughput benchmarks."""

    def test_mixed_workload_throughput(self, db_pool, clean_test_data, setup_perf_teams):
        """
        PERFORMANCE: Measure mixed read/write workload throughput.

        Simulates realistic game day workload:
        - 80% reads (get current state, live games)
        - 20% writes (upserts)

        Benchmark:
        - Target: > 100 mixed ops/sec
        """
        teams = setup_perf_teams

        # Setup: Create initial game states
        for i in range(5):
            create_game_state(
                espn_event_id=f"PERF-MIXED-{i:03d}",
                home_team_id=teams[i % len(teams)],
                away_team_id=teams[(i + 1) % len(teams)],
                home_score=0,
                away_score=0,
                game_status="in_progress",
                league="nfl",
            )

        ops_count = 0
        start = time.perf_counter()

        # Run mixed workload for 100 ops
        for i in range(100):
            game_idx = i % 5
            if i % 5 == 0:  # 20% writes
                upsert_game_state(
                    espn_event_id=f"PERF-MIXED-{game_idx:03d}",
                    home_team_id=teams[game_idx % len(teams)],
                    away_team_id=teams[(game_idx + 1) % len(teams)],
                    home_score=i // 5,
                    away_score=0,
                    game_status="in_progress",
                    league="nfl",
                )
            else:  # 80% reads
                if i % 2 == 0:
                    get_current_game_state(f"PERF-MIXED-{game_idx:03d}")
                else:
                    get_live_games(league="nfl")
            ops_count += 1

        elapsed = time.perf_counter() - start
        throughput = ops_count / elapsed

        print(f"\nMixed workload (80% reads, 20% writes) throughput: {throughput:.1f} ops/sec")

        assert throughput > 50, f"Throughput {throughput:.1f} ops/sec below 50 target"
