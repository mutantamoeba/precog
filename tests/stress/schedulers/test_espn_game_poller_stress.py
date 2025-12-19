"""
Stress Tests for ESPN Game Poller.

Tests ESPNGamePoller under high load and resource pressure.

Reference: TESTING_STRATEGY V3.2 - Stress tests for high volume scenarios
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/stress/schedulers/test_espn_game_poller_stress.py -v -m stress
"""

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.espn_game_poller import ESPNGamePoller

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_espn_client() -> MagicMock:
    """Create mock ESPN client."""
    client = MagicMock()
    client.get_scoreboard.return_value = []
    return client


@pytest.fixture
def large_game_batch() -> list[dict[str, Any]]:
    """Generate a large batch of game data."""
    games = []
    for i in range(100):
        games.append(
            {
                "metadata": {
                    "espn_event_id": f"game_{i}",
                    "home_team": {"espn_team_id": str(i * 2), "team_code": f"H{i}"},
                    "away_team": {"espn_team_id": str(i * 2 + 1), "team_code": f"A{i}"},
                    "venue": {"venue_name": f"Stadium {i}"},
                },
                "state": {
                    "home_score": i,
                    "away_score": i + 1,
                    "game_status": "in_progress",
                },
            }
        )
    return games


# =============================================================================
# Stress Tests: High Volume Polling
# =============================================================================


@pytest.mark.stress
class TestHighVolumePolling:
    """Stress tests for high volume polling scenarios."""

    def test_rapid_poll_calls(self, mock_espn_client: MagicMock) -> None:
        """Test rapid consecutive poll calls."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Rapid poll calls
        for _ in range(100):
            poller.poll_once()

        assert poller.stats["polls_completed"] == 0  # poll_once doesn't update stats
        assert mock_espn_client.get_scoreboard.call_count == 100

    def test_rapid_poll_wrapper_calls(self, mock_espn_client: MagicMock) -> None:
        """Test rapid _poll_wrapper calls (updates stats)."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        for _ in range(1000):
            poller._poll_wrapper()

        assert poller.stats["polls_completed"] == 1000

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_large_game_batch(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
        large_game_batch: list[dict[str, Any]],
    ) -> None:
        """Test polling with large batch of games."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_espn_client.get_scoreboard.return_value = large_game_batch

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()

        assert result["items_fetched"] == 100
        assert result["items_updated"] == 100
        assert mock_upsert.call_count == 100


# =============================================================================
# Stress Tests: Multi-League High Volume
# =============================================================================


@pytest.mark.stress
class TestMultiLeagueHighVolume:
    """Stress tests for high volume multi-league polling."""

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_all_leagues_high_volume(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test polling all supported leagues with many games each."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        def generate_games(count: int) -> list[dict[str, Any]]:
            return [
                {
                    "metadata": {
                        "espn_event_id": f"game_{j}",
                        "home_team": {"espn_team_id": str(j)},
                        "away_team": {"espn_team_id": str(j + 1)},
                        "venue": {"venue_name": f"Stadium {j}"},
                    },
                    "state": {"home_score": 0, "away_score": 0, "game_status": "pre"},
                }
                for j in range(count)
            ]

        mock_espn_client.get_scoreboard.return_value = generate_games(20)

        all_leagues = ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"]
        poller = ESPNGamePoller(
            leagues=all_leagues,
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()

        # 6 leagues * 20 games each = 120 games
        assert result["items_fetched"] == 120
        assert mock_espn_client.get_scoreboard.call_count == 6


# =============================================================================
# Stress Tests: Stats Under Load
# =============================================================================


@pytest.mark.stress
class TestStatsUnderLoad:
    """Stress tests for stats access under load."""

    def test_stats_access_during_rapid_polls(self, mock_espn_client: MagicMock) -> None:
        """Test stats access while polling rapidly."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        stats_reads: list[dict[str, Any]] = []

        for i in range(500):
            poller._poll_wrapper()
            if i % 10 == 0:
                stats_reads.append(poller.stats)

        # All stats reads should be valid
        assert len(stats_reads) == 50
        for stats in stats_reads:
            assert "polls_completed" in stats

        # Final stats should be accumulated
        assert poller.stats["polls_completed"] == 500

    def test_stats_consistency_under_load(self, mock_espn_client: MagicMock) -> None:
        """Test stats remain consistent under load."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        for i in range(1000):
            poller._poll_wrapper()

            # Periodically check consistency
            if i % 100 == 0:
                stats = poller.stats
                assert stats["polls_completed"] == i + 1
                assert stats["errors"] == 0


# =============================================================================
# Stress Tests: Error Recovery Under Load
# =============================================================================


@pytest.mark.stress
class TestErrorRecoveryUnderLoad:
    """Stress tests for error recovery under load."""

    def test_intermittent_errors_under_load(self, mock_espn_client: MagicMock) -> None:
        """Test handling intermittent errors under load."""
        call_count = 0

        def mock_scoreboard(league: str) -> list:
            nonlocal call_count
            call_count += 1
            if call_count % 10 == 0:
                raise RuntimeError("Intermittent error")
            return []

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        for _ in range(100):
            poller._poll_wrapper()

        # Should have logged errors but continued
        assert poller.stats["polls_completed"] == 100
        assert poller.stats["errors"] == 10  # Every 10th call errors

    def test_all_errors_under_load(self, mock_espn_client: MagicMock) -> None:
        """Test handling when all polls error."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError("Always error")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        for _ in range(100):
            poller._poll_wrapper()

        # All should be errors
        assert poller.stats["polls_completed"] == 100
        assert poller.stats["errors"] == 100


# =============================================================================
# Stress Tests: Concurrent Operations
# =============================================================================


@pytest.mark.stress
class TestConcurrentOperations:
    """Stress tests for concurrent operations."""

    def test_concurrent_stats_and_polls(self, mock_espn_client: MagicMock) -> None:
        """Test concurrent stats access while polling."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        stop_event = threading.Event()
        errors: list[Exception] = []

        def poll_continuously() -> None:
            while not stop_event.is_set():
                try:
                    poller._poll_wrapper()
                except Exception as e:
                    errors.append(e)

        def read_stats_continuously() -> None:
            while not stop_event.is_set():
                try:
                    _ = poller.stats
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=poll_continuously),
            threading.Thread(target=read_stats_continuously),
            threading.Thread(target=read_stats_continuously),
        ]

        for t in threads:
            t.start()

        time.sleep(2)
        stop_event.set()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert poller.stats["polls_completed"] > 0

    def test_many_concurrent_polls(self, mock_espn_client: MagicMock) -> None:
        """Test many threads polling concurrently."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        errors: list[Exception] = []

        def poll_many() -> None:
            for _ in range(100):
                try:
                    poller._poll_wrapper()
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=poll_many) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Should have 1000 polls (10 threads * 100 polls)
        assert poller.stats["polls_completed"] == 1000


# =============================================================================
# Stress Tests: Scheduler Under Load
# =============================================================================


@pytest.mark.stress
class TestSchedulerUnderLoad:
    """Stress tests for scheduler under load."""

    def test_scheduler_rapid_start_stop(self, mock_espn_client: MagicMock) -> None:
        """Test rapid scheduler start/stop cycles."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        for _ in range(20):
            poller.start()
            time.sleep(0.1)
            poller.stop()

        # Should have done some polls
        assert poller.stats["polls_completed"] >= 20

    def test_scheduler_with_manual_polls(self, mock_espn_client: MagicMock) -> None:
        """Test scheduler with concurrent manual polls."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller.start()
        try:
            # Do manual polls while scheduler running
            for _ in range(50):
                poller._poll_wrapper()
                time.sleep(0.02)

            # Should have accumulated polls from both
            assert poller.stats["polls_completed"] >= 50
        finally:
            poller.stop()


# =============================================================================
# Stress Tests: Memory Pressure
# =============================================================================


@pytest.mark.stress
class TestMemoryPressure:
    """Stress tests for memory usage under pressure."""

    def test_many_stats_copies(self, mock_espn_client: MagicMock) -> None:
        """Test creating many stats copies doesn't accumulate."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Do some polls
        for _ in range(100):
            poller._poll_wrapper()

        # Create many stats copies
        copies = []
        for _ in range(10000):
            copies.append(poller.stats)

        # All should be independent
        for copy in copies[:10]:
            copy["polls_completed"] = 9999

        # Original should be unchanged
        assert poller.stats["polls_completed"] == 100

    def test_many_poller_instances(self, mock_espn_client: MagicMock) -> None:
        """Test creating many poller instances."""
        pollers = []

        for _ in range(100):
            p = ESPNGamePoller(
                leagues=["nfl"],
                espn_client=mock_espn_client,
            )
            pollers.append(p)

        # All should be independent
        for i, p in enumerate(pollers):
            for _ in range(i + 1):
                p._poll_wrapper()

        # Each should have correct count
        for i, p in enumerate(pollers):
            assert p.stats["polls_completed"] == i + 1


# =============================================================================
# Stress Tests: Status Normalization Under Load
# =============================================================================


@pytest.mark.stress
class TestStatusNormalizationUnderLoad:
    """Stress tests for status normalization under load."""

    def test_normalize_many_statuses(self, mock_espn_client: MagicMock) -> None:
        """Test normalizing many statuses rapidly."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        statuses = ["pre", "in", "halftime", "final", "unknown", "", "POST"]
        results = []

        for _ in range(10000):
            for status in statuses:
                result = poller._normalize_game_status(status)
                results.append(result)

        # All should be valid
        valid = {"pre", "in_progress", "halftime", "final"}
        for r in results:
            assert r in valid


# =============================================================================
# Stress Tests: Adaptive Polling Under Load (Issue #234)
# =============================================================================


@pytest.mark.stress
class TestAdaptivePollingStress:
    """Stress tests for adaptive polling interval adjustment under load.

    Tests the _adjust_poll_interval() and has_active_games() methods
    under various stress scenarios.

    Related: Issue #234 (ESPNGamePoller adaptive polling)
    """

    def test_rapid_interval_adjustments(self, mock_espn_client: MagicMock) -> None:
        """Test rapid interval adjustment calls."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        # Don't start scheduler - just test the adjustment logic
        with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
            # Alternate between active and idle states rapidly
            for i in range(1000):
                mock_get_live.return_value = [{"game_id": 1}] if i % 2 == 0 else []
                poller._adjust_poll_interval()

        # Should complete without errors
        # Final state depends on last iteration (i=999, i%2=1, so idle)
        assert poller._last_active_state is False

    def test_concurrent_interval_adjustments(self, mock_espn_client: MagicMock) -> None:
        """Test concurrent interval adjustment from multiple threads."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        errors: list[Exception] = []
        call_count = {"total": 0}
        lock = threading.Lock()

        def adjust_intervals(thread_id: int) -> None:
            try:
                with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
                    for i in range(100):
                        # Simulate varying active game states
                        mock_get_live.return_value = (
                            [{"game_id": thread_id}] if (i + thread_id) % 3 == 0 else []
                        )
                        poller._adjust_poll_interval()
                        with lock:
                            call_count["total"] += 1
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=adjust_intervals, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors during concurrent adjustment: {errors}"
        assert call_count["total"] == 1000  # 10 threads * 100 calls

    def test_has_active_games_high_volume(self, mock_espn_client: MagicMock) -> None:
        """Test has_active_games() under high volume calls."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
            # Simulate different responses for different leagues
            def get_live_games_mock(league: str) -> list:
                if league == "nfl":
                    return [{"game_id": 1}]
                return []

            mock_get_live.side_effect = get_live_games_mock

            results = []
            for _ in range(1000):
                result = poller.has_active_games()
                results.append(result)

            # All should return True (NFL has active games)
            assert all(results), "Expected all True when NFL has active games"
            assert mock_get_live.call_count == 1000  # Short-circuits after first True

    def test_interval_adjustment_under_scheduler_load(self, mock_espn_client: MagicMock) -> None:
        """Test interval adjustment while scheduler is running under load."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,  # Minimum allowed poll interval
            idle_interval=15,  # Minimum allowed idle interval
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
            mock_get_live.return_value = []

            poller.start()
            try:
                # Let it run for a bit while alternating states
                for i in range(20):
                    mock_get_live.return_value = [{"game_id": 1}] if i % 2 == 0 else []
                    time.sleep(0.1)

                # Should have completed some polls
                assert poller.stats["polls_completed"] > 0
            finally:
                poller.stop()

    def test_adaptive_polling_state_transitions_stress(self, mock_espn_client: MagicMock) -> None:
        """Test rapid state transitions between active and idle."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        transition_count = {"active_to_idle": 0, "idle_to_active": 0}

        with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
            last_state = None

            for i in range(500):
                is_active = i % 2 == 0
                mock_get_live.return_value = [{"game_id": 1}] if is_active else []

                poller._adjust_poll_interval()

                current_state = poller._last_active_state
                if last_state is not None and last_state != current_state:
                    if last_state and not current_state:
                        transition_count["active_to_idle"] += 1
                    elif not last_state and current_state:
                        transition_count["idle_to_active"] += 1
                last_state = current_state

        # Should have many transitions (alternating every call)
        assert transition_count["active_to_idle"] > 200
        assert transition_count["idle_to_active"] > 200

    def test_adaptive_polling_disabled_stress(self, mock_espn_client: MagicMock) -> None:
        """Test that disabled adaptive polling doesn't adjust intervals under load."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=False,  # Disabled
        )

        with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
            mock_get_live.return_value = [{"game_id": 1}]

            for _ in range(1000):
                poller._adjust_poll_interval()

            # Should never call get_live_games when disabled
            mock_get_live.assert_not_called()

    def test_get_current_interval_stress(self, mock_espn_client: MagicMock) -> None:
        """Test get_current_interval() under high volume calls."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        intervals = []
        for _ in range(10000):
            interval = poller.get_current_interval()
            intervals.append(interval)

        # All should be valid intervals (15 or 60)
        valid_intervals = {15, 60}
        for interval in intervals:
            assert interval in valid_intervals, f"Invalid interval: {interval}"


# =============================================================================
# Race Tests: Adaptive Polling Race Conditions (Issue #234)
# =============================================================================


@pytest.mark.race
class TestAdaptivePollingRace:
    """Race condition tests for adaptive polling interval adjustment.

    Tests thread safety of _adjust_poll_interval() and has_active_games().

    Related: Issue #234 (ESPNGamePoller adaptive polling)
    """

    def test_race_concurrent_interval_adjustment(self, mock_espn_client: MagicMock) -> None:
        """
        RACE: Multiple threads adjusting interval simultaneously.

        Validates:
        - Interval adjustment is thread-safe
        - _last_active_state updates correctly
        - No corrupted interval values
        """
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        errors: list[Exception] = []
        results = {"adjustments": 0}
        lock = threading.Lock()
        barrier = threading.Barrier(10, timeout=10.0)

        def adjust_interval(thread_id: int) -> None:
            try:
                with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
                    barrier.wait()
                    for i in range(100):
                        # Alternate between active and idle
                        mock_get_live.return_value = [{"game_id": thread_id}] if i % 2 == 0 else []
                        poller._adjust_poll_interval()
                        with lock:
                            results["adjustments"] += 1
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=adjust_interval, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors: {errors}"
        assert results["adjustments"] == 1000  # 10 threads * 100 calls
        # Final state should be valid
        assert poller._last_active_state in (True, False)

    def test_race_has_active_games_concurrent(self, mock_espn_client: MagicMock) -> None:
        """
        RACE: Concurrent calls to has_active_games().

        Validates:
        - Method returns consistent results under concurrent access
        - No race condition between league checks
        """
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        results = {"true_count": 0, "false_count": 0, "errors": []}
        lock = threading.Lock()
        barrier = threading.Barrier(10, timeout=10.0)

        def check_active_games(thread_id: int) -> None:
            try:
                with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
                    # Even threads: no active games, Odd threads: active games
                    mock_get_live.return_value = [{"game_id": 1}] if thread_id % 2 == 1 else []
                    barrier.wait()

                    for _ in range(100):
                        result = poller.has_active_games()
                        with lock:
                            if result:
                                results["true_count"] += 1
                            else:
                                results["false_count"] += 1
            except Exception as e:
                with lock:
                    results["errors"].append(str(e))

        threads = [threading.Thread(target=check_active_games, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(results["errors"]) == 0, f"Errors: {results['errors']}"
        # Total calls should be 1000
        assert results["true_count"] + results["false_count"] == 1000

    def test_race_get_current_interval_during_adjustment(self, mock_espn_client: MagicMock) -> None:
        """
        RACE: Read interval while another thread is adjusting.

        Validates:
        - Interval reads are atomic
        - No partially updated values
        """
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        errors: list[Exception] = []
        intervals_read: list[int] = []
        lock = threading.Lock()
        stop_event = threading.Event()

        def adjust_continuously() -> None:
            try:
                with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
                    while not stop_event.is_set():
                        # Flip between active and idle rapidly
                        mock_get_live.return_value = [{"game_id": 1}]
                        poller._adjust_poll_interval()
                        mock_get_live.return_value = []
                        poller._adjust_poll_interval()
            except Exception as e:
                errors.append(e)

        def read_continuously() -> None:
            try:
                while not stop_event.is_set():
                    interval = poller.get_current_interval()
                    with lock:
                        intervals_read.append(interval)
            except Exception as e:
                errors.append(e)

        adjuster = threading.Thread(target=adjust_continuously)
        readers = [threading.Thread(target=read_continuously) for _ in range(5)]

        adjuster.start()
        for r in readers:
            r.start()

        time.sleep(1)  # Let threads run
        stop_event.set()

        adjuster.join(timeout=5)
        for r in readers:
            r.join(timeout=5)

        assert len(errors) == 0, f"Errors: {errors}"
        # All intervals should be valid (15 or 60)
        valid_intervals = {15, 60}
        for interval in intervals_read:
            assert interval in valid_intervals, f"Invalid interval read: {interval}"

    def test_race_poll_wrapper_concurrent_calls(self, mock_espn_client: MagicMock) -> None:
        """
        RACE: Concurrent _poll_wrapper calls with adaptive polling.

        Validates:
        - Stats are updated atomically
        - Interval adjustments don't corrupt state
        """
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        errors: list[Exception] = []

        def poll_wrapper_calls() -> None:
            try:
                with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
                    mock_get_live.return_value = []
                    for _ in range(100):
                        poller._poll_wrapper()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=poll_wrapper_calls) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors: {errors}"
        # Should have exactly 1000 polls (10 threads * 100 calls)
        assert poller.stats["polls_completed"] == 1000

    def test_race_adaptive_state_toggle_stress(self, mock_espn_client: MagicMock) -> None:
        """
        RACE: Rapid toggling between active/idle with multiple threads.

        Validates:
        - State transitions are consistent
        - No stuck/invalid states
        """
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        transitions = {"count": 0, "errors": []}
        lock = threading.Lock()
        barrier = threading.Barrier(5, timeout=10.0)

        def toggle_state(thread_id: int) -> None:
            try:
                with patch("precog.schedulers.espn_game_poller.get_live_games") as mock_get_live:
                    barrier.wait()
                    last_state = None
                    local_transitions = 0

                    for i in range(200):
                        # Rapid state changes
                        mock_get_live.return_value = [{"game_id": thread_id}] if i % 2 == 0 else []
                        poller._adjust_poll_interval()

                        current = poller._last_active_state
                        if last_state is not None and last_state != current:
                            local_transitions += 1
                        last_state = current

                    with lock:
                        transitions["count"] += local_transitions
            except Exception as e:
                with lock:
                    transitions["errors"].append(str(e))

        threads = [threading.Thread(target=toggle_state, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(transitions["errors"]) == 0, f"Errors: {transitions['errors']}"
        # Should have many transitions (threads rapidly toggling)
        assert transitions["count"] > 0
