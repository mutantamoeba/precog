"""
Race Condition Tests for Base Poller.

Tests thread safety and concurrent access patterns for BasePoller.

Reference: TESTING_STRATEGY V3.2 - Race condition tests for thread safety
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/race/schedulers/test_base_poller_race.py -v -m race
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from precog.schedulers.base_poller import BasePoller, PollerStats

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class RacePoller(BasePoller):
    """Concrete implementation for race condition testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 1

    def __init__(self, poll_interval: int | None = None) -> None:
        super().__init__(poll_interval=poll_interval)
        self._poll_result = {
            "items_fetched": 10,
            "items_updated": 5,
            "items_created": 2,
        }

    def _poll_once(self) -> dict[str, int]:
        return self._poll_result

    def _get_job_name(self) -> str:
        return "Race Test Poller"


# =============================================================================
# Race Tests: Concurrent Stats Access
# =============================================================================


@pytest.mark.race
class TestConcurrentStatsAccess:
    """Race condition tests for concurrent stats access."""

    def test_concurrent_stats_reads(self) -> None:
        """Test multiple threads reading stats simultaneously."""
        poller = RacePoller()
        # Pre-populate some stats
        for _ in range(10):
            poller._poll_wrapper()

        results: list[PollerStats] = []
        errors: list[Exception] = []

        def read_stats() -> PollerStats:
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
        # All results should be consistent (same stats at that moment)
        for stats in results:
            assert stats["polls_completed"] == 10

    def test_stats_read_during_poll(self) -> None:
        """Test reading stats while polling is occurring."""
        poller = RacePoller()
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
        # Results should be non-decreasing (stats only increase)
        for i in range(1, len(read_results)):
            assert read_results[i] >= read_results[i - 1]


# =============================================================================
# Race Tests: Concurrent Poll Wrapper Calls
# =============================================================================


@pytest.mark.race
class TestConcurrentPollWrapper:
    """Race condition tests for concurrent poll wrapper calls."""

    def test_concurrent_poll_wrapper_calls(self) -> None:
        """Test multiple threads calling poll_wrapper simultaneously."""
        poller = RacePoller()
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
        # All polls should be counted
        assert poller.stats["polls_completed"] == 500

    def test_stats_accumulation_thread_safe(self) -> None:
        """Test stats accumulate correctly with concurrent polls."""
        poller = RacePoller()
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
        assert stats["items_fetched"] == expected_polls * 10
        assert stats["items_updated"] == expected_polls * 5
        assert stats["items_created"] == expected_polls * 2


# =============================================================================
# Race Tests: Start/Stop Races
# =============================================================================


@pytest.mark.race
class TestStartStopRaces:
    """Race condition tests for start/stop operations."""

    def test_concurrent_start_calls(self) -> None:
        """Test multiple threads trying to start the poller.

        The implementation raises RuntimeError on double-start, so
        we expect only one thread to succeed and the rest to get errors.
        """
        poller = RacePoller(poll_interval=1)
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
        # Poller should be running
        assert poller.enabled is True

        poller.stop()

    def test_concurrent_stop_calls(self) -> None:
        """Test multiple threads trying to stop the poller."""
        poller = RacePoller(poll_interval=1)
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

        # No errors from concurrent stop attempts
        assert len(errors) == 0
        # Poller should be stopped
        assert poller.enabled is False

    def test_interleaved_start_stop(self) -> None:
        """Test interleaved start and stop calls.

        Multiple threads doing start/stop cycles will generate RuntimeErrors
        when start() is called on an already-running poller. This test verifies
        the poller handles this gracefully without crashing or corrupting state.
        """
        poller = RacePoller(poll_interval=1)
        runtime_errors: list[RuntimeError] = []
        other_errors: list[Exception] = []

        def start_stop_cycle() -> None:
            for _ in range(10):
                try:
                    poller.start()
                    time.sleep(0.05)
                    poller.stop()
                except RuntimeError as e:
                    # Expected when start is called while already running
                    runtime_errors.append(e)
                except Exception as e:
                    # Unexpected errors
                    other_errors.append(e)

        threads = [threading.Thread(target=start_stop_cycle) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Clean up - ensure poller is stopped
        if poller.enabled:
            poller.stop()

        # RuntimeErrors from double-start are expected
        # No other unexpected errors should occur
        assert len(other_errors) == 0


# =============================================================================
# Race Tests: Stats Copy Isolation
# =============================================================================


@pytest.mark.race
class TestStatsCopyIsolation:
    """Race condition tests for stats copy isolation."""

    def test_stats_copies_isolated(self) -> None:
        """Test that stats copies are independent."""
        poller = RacePoller()
        poller._poll_wrapper()

        copies: list[PollerStats] = []

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

    def test_stats_modification_no_affect_internal(self) -> None:
        """Test modifying stats copy doesn't affect internal state."""
        poller = RacePoller()
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
        assert poller.stats["items_fetched"] == 10


# =============================================================================
# Race Tests: Error Handling Races
# =============================================================================


@pytest.mark.race
class TestErrorHandlingRaces:
    """Race condition tests for error handling."""

    def test_concurrent_errors(self) -> None:
        """Test concurrent error handling."""
        call_count = 0
        count_lock = threading.Lock()

        class ErrorRacePoller(RacePoller):
            def _poll_once(self) -> dict[str, int]:
                nonlocal call_count
                with count_lock:
                    call_count += 1
                raise RuntimeError("Concurrent error")

        poller = ErrorRacePoller()

        def poll_with_error() -> None:
            for _ in range(50):
                poller._poll_wrapper()

        threads = [threading.Thread(target=poll_with_error) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All errors should be tracked
        assert poller.stats["errors"] == 500
        assert call_count == 500

    def test_error_message_race(self) -> None:
        """Test last_error update under race conditions."""
        message_counter = 0
        counter_lock = threading.Lock()

        class MessagePoller(RacePoller):
            def _poll_once(self) -> dict[str, int]:
                nonlocal message_counter
                with counter_lock:
                    message_counter += 1
                    msg = f"Error {message_counter}"
                raise RuntimeError(msg)

        poller = MessagePoller()

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

    def test_instances_isolated(self) -> None:
        """Test multiple instances don't interfere with each other."""
        pollers = [RacePoller() for _ in range(5)]

        def poll_instance(poller: RacePoller, count: int) -> None:
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

    def test_concurrent_instance_operations(self) -> None:
        """Test concurrent operations across multiple instances."""
        pollers = [RacePoller(poll_interval=1) for _ in range(3)]
        errors: list[Exception] = []

        def operate_on_poller(poller: RacePoller) -> None:
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

    def test_stats_lock_held_briefly(self) -> None:
        """Test that stats lock is held briefly (no deadlock risk)."""
        poller = RacePoller()
        poller._poll_wrapper()

        timings: list[float] = []

        def timed_stats_access() -> None:
            start = time.perf_counter()
            _ = poller.stats
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        # Many quick accesses
        threads = [threading.Thread(target=timed_stats_access) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All accesses should be fast (< 10ms each)
        avg_time = sum(timings) / len(timings)
        assert avg_time < 0.01  # 10ms average

    def test_no_deadlock_under_load(self) -> None:
        """Test no deadlock occurs under heavy load."""
        poller = RacePoller(poll_interval=1)
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

        # Wait with timeout - if threads don't complete, we have deadlock
        for t in threads:
            t.join(timeout=10.0)
            if t.is_alive():
                deadlock_detected.set()

        # Clean up any remaining state
        if poller.enabled:
            poller.stop()

        # All threads should have completed
        assert not deadlock_detected.is_set(), "Deadlock detected!"
