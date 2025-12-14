"""
Race Condition Tests for ESPN Game Poller.

Tests thread safety and concurrent access patterns for ESPNGamePoller.

Reference: TESTING_STRATEGY V3.2 - Race condition tests for thread safety
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/race/schedulers/test_espn_game_poller_race.py -v -m race
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from unittest.mock import MagicMock

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


# =============================================================================
# Race Tests: Concurrent Stats Access
# =============================================================================


@pytest.mark.race
class TestConcurrentStatsAccess:
    """Race condition tests for concurrent stats access."""

    def test_concurrent_stats_reads(self, mock_espn_client: MagicMock) -> None:
        """Test multiple threads reading stats simultaneously."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Pre-populate stats
        for _ in range(10):
            poller._poll_wrapper()

        results: list[dict[str, Any]] = []
        errors: list[Exception] = []

        def read_stats() -> dict[str, Any]:
            return poller.stats

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(read_stats) for _ in range(100)]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    errors.append(e)

        assert len(errors) == 0
        assert len(results) == 100
        for stats in results:
            assert stats["polls_completed"] == 10

    def test_stats_read_during_poll(self, mock_espn_client: MagicMock) -> None:
        """Test reading stats while polling is occurring."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        stop_event = threading.Event()
        read_results: list[int] = []
        errors: list[Exception] = []

        def continuous_poll() -> None:
            while not stop_event.is_set():
                poller._poll_wrapper()
                time.sleep(0.01)

        def continuous_read() -> None:
            while not stop_event.is_set():
                try:
                    stats = poller.stats
                    read_results.append(stats["polls_completed"])
                    time.sleep(0.005)
                except Exception as e:
                    errors.append(e)

        poll_thread = threading.Thread(target=continuous_poll)
        read_threads = [threading.Thread(target=continuous_read) for _ in range(5)]

        poll_thread.start()
        for t in read_threads:
            t.start()

        time.sleep(1.0)
        stop_event.set()

        poll_thread.join()
        for t in read_threads:
            t.join()

        assert len(errors) == 0
        # Results should be non-decreasing
        for i in range(1, len(read_results)):
            assert read_results[i] >= read_results[i - 1]


# =============================================================================
# Race Tests: Concurrent Poll Wrapper Calls
# =============================================================================


@pytest.mark.race
class TestConcurrentPollWrapper:
    """Race condition tests for concurrent poll wrapper calls."""

    def test_concurrent_poll_wrapper_calls(self, mock_espn_client: MagicMock) -> None:
        """Test multiple threads calling poll_wrapper simultaneously."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        errors: list[Exception] = []

        def poll_many_times() -> None:
            for _ in range(50):
                try:
                    poller._poll_wrapper()
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=poll_many_times) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert poller.stats["polls_completed"] == 500

    def test_stats_accumulation_thread_safe(self, mock_espn_client: MagicMock) -> None:
        """Test stats accumulate correctly with concurrent polls."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        thread_count = 5
        polls_per_thread = 100

        def poll_wrapper_calls() -> None:
            for _ in range(polls_per_thread):
                poller._poll_wrapper()

        threads = [threading.Thread(target=poll_wrapper_calls) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = poller.stats
        expected_polls = thread_count * polls_per_thread

        assert stats["polls_completed"] == expected_polls


# =============================================================================
# Race Tests: Start/Stop Races
# =============================================================================


@pytest.mark.race
class TestStartStopRaces:
    """Race condition tests for start/stop operations."""

    def test_concurrent_start_calls(self, mock_espn_client: MagicMock) -> None:
        """Test multiple threads trying to start the poller.

        The implementation raises RuntimeError on double-start, so
        we expect only one thread to succeed and the rest to get errors.
        """
        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        successes: list[bool] = []
        start_lock = threading.Lock()

        def try_start() -> None:
            try:
                poller.start()
                with start_lock:
                    successes.append(True)
            except RuntimeError:
                with start_lock:
                    successes.append(False)

        threads = [threading.Thread(target=try_start) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one thread should succeed
        assert successes.count(True) == 1
        assert poller.enabled is True

        poller.stop()

    def test_concurrent_stop_calls(self, mock_espn_client: MagicMock) -> None:
        """Test multiple threads trying to stop the poller."""
        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        errors: list[Exception] = []

        def try_stop() -> None:
            try:
                poller.stop()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=try_stop) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert poller.enabled is False

    def test_interleaved_start_stop(self, mock_espn_client: MagicMock) -> None:
        """Test interleaved start and stop calls.

        Multiple threads doing start/stop cycles will generate RuntimeErrors
        when start() is called on an already-running poller.
        """
        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        runtime_errors: list[RuntimeError] = []
        other_errors: list[Exception] = []

        def start_stop_cycle() -> None:
            for _ in range(10):
                try:
                    poller.start()
                    time.sleep(0.05)
                    poller.stop()
                except RuntimeError as e:
                    runtime_errors.append(e)
                except Exception as e:
                    other_errors.append(e)

        threads = [threading.Thread(target=start_stop_cycle) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if poller.enabled:
            poller.stop()

        # RuntimeErrors are expected, no other errors
        assert len(other_errors) == 0


# =============================================================================
# Race Tests: Stats Copy Isolation
# =============================================================================


@pytest.mark.race
class TestStatsCopyIsolation:
    """Race condition tests for stats copy isolation."""

    def test_stats_copies_isolated(self, mock_espn_client: MagicMock) -> None:
        """Test that stats copies are independent."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._poll_wrapper()

        copies: list[dict[str, Any]] = []

        def get_stats_copy() -> None:
            copy = poller.stats
            copies.append(copy)

        threads = [threading.Thread(target=get_stats_copy) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Modify one copy
        copies[0]["polls_completed"] = 9999

        # Other copies should be unaffected
        for copy in copies[1:]:
            assert copy["polls_completed"] == 1

    def test_stats_modification_no_affect_internal(self, mock_espn_client: MagicMock) -> None:
        """Test modifying stats copy doesn't affect internal state."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._poll_wrapper()

        def modify_stats() -> None:
            stats = poller.stats
            stats["polls_completed"] = 9999
            stats["items_fetched"] = 9999

        threads = [threading.Thread(target=modify_stats) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Internal state should be unchanged
        assert poller.stats["polls_completed"] == 1
        assert poller.stats["items_fetched"] == 0


# =============================================================================
# Race Tests: Error Handling Races
# =============================================================================


@pytest.mark.race
class TestErrorHandlingRaces:
    """Race condition tests for error handling."""

    def test_concurrent_errors(self, mock_espn_client: MagicMock) -> None:
        """Test concurrent error handling."""
        call_count = 0
        count_lock = threading.Lock()

        def mock_scoreboard(league: str) -> list:
            nonlocal call_count
            with count_lock:
                call_count += 1
            raise RuntimeError("Concurrent error")

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        def poll_with_error() -> None:
            for _ in range(50):
                poller._poll_wrapper()

        threads = [threading.Thread(target=poll_with_error) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert poller.stats["errors"] == 500
        assert call_count == 500

    def test_error_message_race(self, mock_espn_client: MagicMock) -> None:
        """Test last_error update under race conditions."""
        message_counter = 0
        counter_lock = threading.Lock()

        def mock_scoreboard(league: str) -> list:
            nonlocal message_counter
            with counter_lock:
                message_counter += 1
                msg = f"Error {message_counter}"
            raise RuntimeError(msg)

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        def poll_with_messages() -> None:
            for _ in range(10):
                poller._poll_wrapper()

        threads = [threading.Thread(target=poll_with_messages) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Last error should be one of the messages
        assert poller.stats["last_error"] is not None
        assert poller.stats["last_error"].startswith("Error ")


# =============================================================================
# Race Tests: Multiple Instance Isolation
# =============================================================================


@pytest.mark.race
class TestMultipleInstanceIsolation:
    """Race condition tests for multiple poller instances."""

    def test_instances_isolated(self, mock_espn_client: MagicMock) -> None:
        """Test multiple instances don't interfere with each other."""
        mock_espn_client.get_scoreboard.return_value = []

        pollers = [ESPNGamePoller(leagues=["nfl"], espn_client=mock_espn_client) for _ in range(5)]

        def poll_instance(poller: ESPNGamePoller, count: int) -> None:
            for _ in range(count):
                poller._poll_wrapper()

        threads = []
        counts = [10, 20, 30, 40, 50]

        for poller, count in zip(pollers, counts, strict=False):
            t = threading.Thread(target=poll_instance, args=(poller, count))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Each poller should have its own count
        for poller, count in zip(pollers, counts, strict=False):
            assert poller.stats["polls_completed"] == count

    def test_concurrent_instance_operations(self, mock_espn_client: MagicMock) -> None:
        """Test concurrent operations across multiple instances."""
        mock_espn_client.get_scoreboard.return_value = []

        pollers = [
            ESPNGamePoller(
                poll_interval=5,
                leagues=["nfl"],
                espn_client=mock_espn_client,
            )
            for _ in range(3)
        ]

        errors: list[Exception] = []

        def operate_on_poller(poller: ESPNGamePoller) -> None:
            try:
                poller.start()
                time.sleep(0.2)
                _ = poller.stats
                poller._poll_wrapper()
                poller.stop()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=operate_on_poller, args=(p,)) for p in pollers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        for p in pollers:
            assert p.enabled is False


# =============================================================================
# Race Tests: Lock Verification
# =============================================================================


@pytest.mark.race
class TestLockVerification:
    """Race condition tests verifying lock behavior."""

    def test_stats_lock_held_briefly(self, mock_espn_client: MagicMock) -> None:
        """Test that stats lock is held briefly (no deadlock risk)."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._poll_wrapper()

        timings: list[float] = []

        def timed_stats_access() -> None:
            start = time.perf_counter()
            _ = poller.stats
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        threads = [threading.Thread(target=timed_stats_access) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        avg_time = sum(timings) / len(timings)
        assert avg_time < 0.01  # 10ms average

    def test_no_deadlock_under_load(self, mock_espn_client: MagicMock) -> None:
        """Test no deadlock occurs under heavy load."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        deadlock_detected = threading.Event()

        def stats_reader() -> None:
            for _ in range(50):
                if deadlock_detected.is_set():
                    return
                _ = poller.stats
                time.sleep(0.01)

        def poll_caller() -> None:
            for _ in range(50):
                if deadlock_detected.is_set():
                    return
                poller._poll_wrapper()
                time.sleep(0.01)

        def lifecycle_manager() -> None:
            for _ in range(10):
                if deadlock_detected.is_set():
                    return
                poller.start()
                time.sleep(0.1)
                poller.stop()

        threads = [
            threading.Thread(target=stats_reader),
            threading.Thread(target=stats_reader),
            threading.Thread(target=poll_caller),
            threading.Thread(target=lifecycle_manager),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10.0)
            if t.is_alive():
                deadlock_detected.set()

        if poller.enabled:
            poller.stop()

        assert not deadlock_detected.is_set(), "Deadlock detected!"


# =============================================================================
# Race Tests: League Polling Races
# =============================================================================


@pytest.mark.race
class TestLeaguePollingRaces:
    """Race condition tests for league polling."""

    def test_concurrent_league_changes(self, mock_espn_client: MagicMock) -> None:
        """Test reading leagues while poll happens."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        stop_event = threading.Event()
        leagues_read: list[list[str]] = []
        errors: list[Exception] = []

        def poll_continuously() -> None:
            while not stop_event.is_set():
                try:
                    poller._poll_wrapper()
                except Exception as e:
                    errors.append(e)

        def read_leagues() -> None:
            while not stop_event.is_set():
                try:
                    leagues_read.append(poller.leagues.copy())
                    time.sleep(0.001)
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=poll_continuously),
            threading.Thread(target=read_leagues),
        ]

        for t in threads:
            t.start()

        time.sleep(1.0)
        stop_event.set()

        for t in threads:
            t.join()

        assert len(errors) == 0
        # All league reads should be consistent
        for leagues in leagues_read:
            assert leagues == ["nfl", "nba"]
