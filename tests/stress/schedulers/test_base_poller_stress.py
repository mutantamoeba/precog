"""
Stress Tests for Base Poller.

Tests BasePoller under high load and sustained operation.

Reference: TESTING_STRATEGY V3.2 - Stress tests for load handling
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/stress/schedulers/test_base_poller_stress.py -v -m stress
"""

import threading
import time

import pytest

from precog.schedulers.base_poller import BasePoller, PollerStats

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class StressPoller(BasePoller):
    """Concrete implementation for stress testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 1

    def __init__(
        self,
        poll_interval: int | None = None,
        items_per_poll: int = 100,
    ) -> None:
        super().__init__(poll_interval=poll_interval)
        self.items_per_poll = items_per_poll
        self.poll_timestamps: list[float] = []
        self._poll_lock = threading.Lock()

    def _poll_once(self) -> dict[str, int]:
        with self._poll_lock:
            self.poll_timestamps.append(time.time())
        return {
            "items_fetched": self.items_per_poll,
            "items_updated": self.items_per_poll // 2,
            "items_created": self.items_per_poll // 10,
        }

    def _get_job_name(self) -> str:
        return "Stress Test Poller"


# =============================================================================
# Stress Tests: High Volume Polling
# =============================================================================


@pytest.mark.stress
class TestHighVolumePolling:
    """Stress tests for high volume polling scenarios."""

    def test_rapid_polling_interval(self) -> None:
        """Test poller handles minimum interval (1 second)."""
        poller = StressPoller(poll_interval=1, items_per_poll=1000)

        poller.start()
        try:
            time.sleep(5.5)

            stats = poller.stats
            # Should have completed several polls
            assert stats["polls_completed"] >= 5
            # Should have processed significant items
            assert stats["items_fetched"] >= 5000
        finally:
            poller.stop()

    def test_large_item_counts(self) -> None:
        """Test poller handles large item counts per poll."""
        poller = StressPoller(poll_interval=1, items_per_poll=100000)

        poller.start()
        try:
            time.sleep(3.5)

            stats = poller.stats
            # Should handle large numbers without overflow
            assert stats["items_fetched"] >= 300000
        finally:
            poller.stop()

    def test_sustained_operation(self) -> None:
        """Test poller maintains stable operation over time."""
        poller = StressPoller(poll_interval=1, items_per_poll=100)

        poller.start()
        try:
            time.sleep(10.5)

            stats = poller.stats
            # Should complete expected polls
            assert stats["polls_completed"] >= 10
            # No errors in stable operation
            assert stats["errors"] == 0
        finally:
            poller.stop()


# =============================================================================
# Stress Tests: Concurrent Stats Access
# =============================================================================


@pytest.mark.stress
class TestConcurrentStatsAccess:
    """Stress tests for concurrent stats access."""

    def test_many_concurrent_readers(self) -> None:
        """Test many threads reading stats concurrently."""
        poller = StressPoller(poll_interval=1)
        poller.start()

        try:
            read_counts: list[int] = []
            errors: list[Exception] = []

            def read_stats_repeatedly() -> None:
                count = 0
                for _ in range(100):
                    try:
                        _ = poller.stats
                        count += 1
                        time.sleep(0.01)
                    except Exception as e:
                        errors.append(e)
                read_counts.append(count)

            threads = [threading.Thread(target=read_stats_repeatedly) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All reads should succeed
            assert len(errors) == 0
            assert sum(read_counts) == 1000
        finally:
            poller.stop()

    def test_stats_access_during_high_activity(self) -> None:
        """Test stats access while poller is highly active."""
        poller = StressPoller(poll_interval=1, items_per_poll=10000)
        poller.start()

        try:
            stats_snapshots: list[PollerStats] = []

            for _ in range(50):
                stats_snapshots.append(poller.stats)
                time.sleep(0.1)

            # All snapshots should be valid
            for stats in stats_snapshots:
                assert "polls_completed" in stats
                assert isinstance(stats["polls_completed"], int)
                assert stats["polls_completed"] >= 0
        finally:
            poller.stop()


# =============================================================================
# Stress Tests: Many Poller Instances
# =============================================================================


@pytest.mark.stress
class TestManyPollerInstances:
    """Stress tests for many concurrent poller instances."""

    def test_multiple_concurrent_pollers(self) -> None:
        """Test multiple pollers running concurrently."""
        pollers = [StressPoller(poll_interval=1) for _ in range(5)]

        # Start all pollers
        for p in pollers:
            p.start()

        try:
            time.sleep(3.5)

            # All should have completed polls
            for p in pollers:
                assert p.stats["polls_completed"] >= 3
        finally:
            # Stop all pollers
            for p in pollers:
                p.stop()

    def test_staggered_poller_creation(self) -> None:
        """Test creating pollers in rapid succession."""
        pollers: list[StressPoller] = []

        try:
            # Create and start pollers rapidly
            for i in range(10):
                p = StressPoller(poll_interval=1)
                p.start()
                pollers.append(p)
                time.sleep(0.1)

            time.sleep(2.0)

            # All should be running
            for p in pollers:
                assert p.enabled is True
        finally:
            for p in pollers:
                p.stop()


# =============================================================================
# Stress Tests: Error Handling Under Load
# =============================================================================


@pytest.mark.stress
class TestErrorHandlingUnderLoad:
    """Stress tests for error handling under load."""

    def test_intermittent_errors_under_load(self) -> None:
        """Test handling intermittent errors while under load."""

        class IntermittentErrorPoller(StressPoller):
            def __init__(self) -> None:
                super().__init__(poll_interval=1)
                self.poll_count = 0

            def _poll_once(self) -> dict[str, int]:
                self.poll_count += 1
                if self.poll_count % 3 == 0:
                    raise RuntimeError("Intermittent error")
                return super()._poll_once()

        poller = IntermittentErrorPoller()
        poller.start()

        try:
            time.sleep(6.5)

            stats = poller.stats
            # Should have both successes and errors
            assert stats["polls_completed"] >= 4
            assert stats["errors"] >= 2
        finally:
            poller.stop()

    def test_error_recovery_loop(self) -> None:
        """Test error recovery in continuous loop."""

        class RecoveringPoller(StressPoller):
            def __init__(self) -> None:
                super().__init__(poll_interval=1)
                self.fail_until = 3

            def _poll_once(self) -> dict[str, int]:
                current_polls = len(self.poll_timestamps) + 1
                if current_polls <= self.fail_until:
                    self.poll_timestamps.append(time.time())
                    raise ConnectionError("Temporary failure")
                return super()._poll_once()

        poller = RecoveringPoller()
        poller.start()

        try:
            time.sleep(6.5)

            stats = poller.stats
            # Should have recovered after initial failures
            assert stats["polls_completed"] >= 3
            assert stats["errors"] >= 3
        finally:
            poller.stop()


# =============================================================================
# Stress Tests: Memory and Resource Usage
# =============================================================================


@pytest.mark.stress
class TestResourceUsage:
    """Stress tests for resource usage."""

    def test_no_memory_leak_in_stats(self) -> None:
        """Test stats don't accumulate unbounded data."""
        poller = StressPoller(poll_interval=1, items_per_poll=1000)

        poller.start()
        try:
            # Run for a while
            time.sleep(5.5)

            stats = poller.stats
            # Stats should have fixed number of keys
            assert len(stats) == 7  # Fixed keys in PollerStats
        finally:
            poller.stop()

    def test_poll_timestamp_list_bounds(self) -> None:
        """Test poll timestamp tracking doesn't grow unbounded."""
        poller = StressPoller(poll_interval=1)

        poller.start()
        try:
            time.sleep(5.5)

            # Our test implementation tracks timestamps
            # In real implementation this should be bounded or cleared
            assert len(poller.poll_timestamps) == poller.stats["polls_completed"]
        finally:
            poller.stop()


# =============================================================================
# Stress Tests: Rapid Start/Stop
# =============================================================================


@pytest.mark.stress
class TestRapidStartStop:
    """Stress tests for rapid start/stop cycles."""

    def test_many_rapid_restarts(self) -> None:
        """Test many rapid restart cycles."""
        poller = StressPoller(poll_interval=1)

        for i in range(20):
            poller.start()
            time.sleep(0.2)
            poller.stop()

        # Should end in clean state
        assert poller.enabled is False

    def test_start_stop_with_concurrent_access(self) -> None:
        """Test start/stop while stats are being read."""
        poller = StressPoller(poll_interval=1)
        errors: list[Exception] = []
        stop_event = threading.Event()

        def read_stats() -> None:
            while not stop_event.is_set():
                try:
                    _ = poller.stats
                    time.sleep(0.01)
                except Exception as e:
                    errors.append(e)

        reader = threading.Thread(target=read_stats)
        reader.start()

        try:
            for _ in range(10):
                poller.start()
                time.sleep(0.2)
                poller.stop()
                time.sleep(0.1)
        finally:
            stop_event.set()
            reader.join()

        # Stats access should be safe during start/stop
        assert len(errors) == 0


# =============================================================================
# Stress Tests: Poll Wrapper Performance
# =============================================================================


@pytest.mark.stress
class TestPollWrapperPerformance:
    """Stress tests for poll wrapper performance."""

    def test_many_direct_poll_calls(self) -> None:
        """Test many direct _poll_wrapper calls."""
        poller = StressPoller()

        for _ in range(1000):
            poller._poll_wrapper()

        assert poller.stats["polls_completed"] == 1000

    def test_poll_wrapper_with_errors(self) -> None:
        """Test many poll wrapper calls with errors."""

        class ErrorPoller(StressPoller):
            def __init__(self) -> None:
                super().__init__()
                self.call_count = 0

            def _poll_once(self) -> dict[str, int]:
                self.call_count += 1
                if self.call_count % 2 == 0:
                    raise ValueError("Even call error")
                return super()._poll_once()

        poller = ErrorPoller()

        for _ in range(100):
            poller._poll_wrapper()

        stats = poller.stats
        assert stats["polls_completed"] == 50  # Half succeeded
        assert stats["errors"] == 50  # Half failed
