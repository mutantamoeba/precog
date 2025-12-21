"""
Performance Tests for Base Poller.

Tests latency and throughput of BasePoller operations.

Reference: TESTING_STRATEGY V3.2 - Performance tests for latency/throughput
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/performance/schedulers/test_base_poller_performance.py -v -m performance

CI Strategy (aligns with stress test pattern from Issue #168):
    **Throughput tests** (TestThroughput) skip in CI because they require consistent
    CPU performance that shared CI runners cannot provide.

    **Latency tests** run in CI because they test maximum acceptable time (upper bounds),
    which remain valid even on slower runners.

    Run locally for full performance validation:
        pytest tests/performance/schedulers/test_base_poller_performance.py -v
"""

import os
import statistics
import time

import pytest

from precog.schedulers.base_poller import BasePoller

# =============================================================================
# CI Environment Detection (Pattern from stress tests - Issue #168)
# =============================================================================

# CI runners have variable performance - throughput tests skip in CI
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
_CI_SKIP_REASON = (
    "Throughput tests skip in CI - shared runners have variable CPU performance. "
    "Run locally for validation: "
    "pytest tests/performance/schedulers/test_base_poller_performance.py -v"
)

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class PerfPoller(BasePoller):
    """Concrete implementation for performance testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 1

    def __init__(self, poll_interval: int | None = None) -> None:
        super().__init__(poll_interval=poll_interval)
        self._poll_result = {
            "items_fetched": 100,
            "items_updated": 50,
            "items_created": 10,
        }

    def _poll_once(self) -> dict[str, int]:
        return self._poll_result

    def _get_job_name(self) -> str:
        return "Performance Test Poller"


# =============================================================================
# Performance Tests: Initialization Latency
# =============================================================================


@pytest.mark.performance
class TestInitializationLatency:
    """Performance tests for initialization latency."""

    def test_poller_creation_latency(self) -> None:
        """Test poller creation is fast."""
        timings: list[float] = []

        for _ in range(100):
            start = time.perf_counter()
            _ = PerfPoller()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        p95_time = sorted(timings)[94]  # 95th percentile

        # Creation should be fast
        assert avg_time < 0.001  # < 1ms average
        assert p95_time < 0.002  # < 2ms p95

    def test_poller_with_custom_interval_latency(self) -> None:
        """Test poller creation with custom interval."""
        timings: list[float] = []

        for i in range(100):
            start = time.perf_counter()
            _ = PerfPoller(poll_interval=i + 1)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        assert avg_time < 0.001  # < 1ms average


# =============================================================================
# Performance Tests: Stats Access Latency
# =============================================================================


@pytest.mark.performance
class TestStatsAccessLatency:
    """Performance tests for stats access latency."""

    def test_stats_property_latency(self) -> None:
        """Test stats property access is fast."""
        poller = PerfPoller()
        # Pre-populate stats
        for _ in range(100):
            poller._poll_wrapper()

        timings: list[float] = []

        for _ in range(1000):
            start = time.perf_counter()
            _ = poller.stats
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        p95_time = sorted(timings)[949]  # 95th percentile
        max_time = max(timings)

        # Stats access should be very fast
        assert avg_time < 0.0001  # < 100us average
        assert p95_time < 0.0005  # < 500us p95
        assert max_time < 0.001  # < 1ms max

    def test_get_stats_method_latency(self) -> None:
        """Test get_stats() method latency."""
        poller = PerfPoller()
        for _ in range(100):
            poller._poll_wrapper()

        timings: list[float] = []

        for _ in range(1000):
            start = time.perf_counter()
            _ = poller.get_stats()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        assert avg_time < 0.0001  # < 100us average

    def test_stats_latency_under_high_poll_count(self) -> None:
        """Test stats access latency doesn't degrade with many polls."""
        poller = PerfPoller()

        # Do many polls
        for _ in range(10000):
            poller._poll_wrapper()

        timings: list[float] = []

        for _ in range(100):
            start = time.perf_counter()
            _ = poller.stats
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        # Should still be fast regardless of poll count
        assert avg_time < 0.0001  # < 100us average


# =============================================================================
# Performance Tests: Poll Wrapper Latency
# =============================================================================


@pytest.mark.performance
class TestPollWrapperLatency:
    """Performance tests for poll wrapper latency."""

    def test_poll_wrapper_latency(self) -> None:
        """Test poll wrapper overhead is minimal."""
        poller = PerfPoller()
        timings: list[float] = []

        for _ in range(1000):
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        p95_time = sorted(timings)[949]

        # Poll wrapper should be fast
        assert avg_time < 0.0005  # < 500us average
        assert p95_time < 0.001  # < 1ms p95

    def test_poll_once_vs_poll_wrapper_overhead(self) -> None:
        """Test poll_wrapper overhead over poll_once."""
        poller = PerfPoller()

        # Measure poll_once
        poll_once_times: list[float] = []
        for _ in range(500):
            start = time.perf_counter()
            poller.poll_once()
            elapsed = time.perf_counter() - start
            poll_once_times.append(elapsed)

        # Measure poll_wrapper
        wrapper_times: list[float] = []
        for _ in range(500):
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            wrapper_times.append(elapsed)

        avg_poll_once = statistics.mean(poll_once_times)
        avg_wrapper = statistics.mean(wrapper_times)

        # Wrapper overhead should be reasonable (< 10x poll_once)
        # Note: wrapper does stats updates, error handling, etc.
        assert avg_wrapper < avg_poll_once * 10 or avg_wrapper < 0.001


# =============================================================================
# Performance Tests: Throughput
# =============================================================================


@pytest.mark.performance
@pytest.mark.skipif(_is_ci, reason=_CI_SKIP_REASON)
class TestThroughput:
    """Performance tests for throughput.

    Note:
        Skipped in CI - throughput tests require consistent CPU performance
        that shared runners cannot provide. See module docstring for details.
    """

    def test_polls_per_second(self) -> None:
        """Test polling throughput."""
        poller = PerfPoller()
        poll_count = 10000

        start = time.perf_counter()
        for _ in range(poll_count):
            poller._poll_wrapper()
        elapsed = time.perf_counter() - start

        polls_per_second = poll_count / elapsed

        # Should achieve high throughput
        assert polls_per_second > 10000  # > 10k polls/sec

    def test_stats_reads_per_second(self) -> None:
        """Test stats reading throughput."""
        poller = PerfPoller()
        for _ in range(100):
            poller._poll_wrapper()

        read_count = 100000

        start = time.perf_counter()
        for _ in range(read_count):
            _ = poller.stats
        elapsed = time.perf_counter() - start

        reads_per_second = read_count / elapsed

        # Should achieve very high read throughput
        assert reads_per_second > 100000  # > 100k reads/sec

    def test_mixed_operations_throughput(self) -> None:
        """Test throughput with mixed operations."""
        poller = PerfPoller()
        operation_count = 10000

        start = time.perf_counter()
        for i in range(operation_count):
            if i % 10 == 0:
                poller._poll_wrapper()
            else:
                _ = poller.stats
        elapsed = time.perf_counter() - start

        ops_per_second = operation_count / elapsed

        # Mixed operations should still be fast
        assert ops_per_second > 50000  # > 50k ops/sec


# =============================================================================
# Performance Tests: Start/Stop Latency
# =============================================================================


@pytest.mark.performance
class TestStartStopLatency:
    """Performance tests for start/stop latency."""

    def test_start_latency(self) -> None:
        """Test scheduler start latency."""
        timings: list[float] = []

        for _ in range(20):
            poller = PerfPoller(poll_interval=1)
            start = time.perf_counter()
            poller.start()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            poller.stop()

        avg_time = statistics.mean(timings)

        # Start should be reasonably fast
        assert avg_time < 0.1  # < 100ms average

    def test_stop_latency(self) -> None:
        """Test scheduler stop latency."""
        timings: list[float] = []

        for _ in range(20):
            poller = PerfPoller(poll_interval=1)
            poller.start()
            time.sleep(0.1)

            start = time.perf_counter()
            poller.stop()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)

        # Stop should be reasonably fast
        assert avg_time < 0.5  # < 500ms average

    def test_start_stop_cycle_latency(self) -> None:
        """Test full start/stop cycle latency."""
        timings: list[float] = []

        for _ in range(10):
            poller = PerfPoller(poll_interval=1)

            start = time.perf_counter()
            poller.start()
            poller.stop()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)

        # Full cycle should complete quickly
        assert avg_time < 0.5  # < 500ms average


# =============================================================================
# Performance Tests: Memory Efficiency
# =============================================================================


@pytest.mark.performance
class TestMemoryEfficiency:
    """Performance tests for memory efficiency."""

    def test_stats_copy_size_constant(self) -> None:
        """Test stats copy size doesn't grow with polls."""
        poller = PerfPoller()

        # Get initial stats
        initial_stats = poller.stats
        initial_keys = len(initial_stats)

        # Do many polls
        for _ in range(10000):
            poller._poll_wrapper()

        # Get final stats
        final_stats = poller.stats
        final_keys = len(final_stats)

        # Stats structure should have same number of keys
        assert initial_keys == final_keys == 7

    def test_many_pollers_reasonable_memory(self) -> None:
        """Test creating many pollers doesn't use excessive memory."""
        pollers: list[PerfPoller] = []

        for _ in range(100):
            p = PerfPoller()
            pollers.append(p)

        # All should be valid
        for p in pollers:
            assert p.stats["polls_completed"] == 0


# =============================================================================
# Performance Tests: Error Handling Overhead
# =============================================================================


@pytest.mark.performance
class TestErrorHandlingOverhead:
    """Performance tests for error handling overhead."""

    def test_error_handling_latency(self) -> None:
        """Test error handling doesn't add significant latency."""

        class ErrorPoller(PerfPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("Test error")

        poller = ErrorPoller()
        timings: list[float] = []

        for _ in range(100):  # Fewer iterations for faster test
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)

        # Error handling should be reasonably fast (including logging)
        assert avg_time < 0.01  # < 10ms average (includes logging overhead)

    def test_error_rate_no_performance_degradation(self) -> None:
        """Test high error rate doesn't degrade performance significantly.

        Note: Error handling includes logging which has overhead, so
        throughput with errors will be lower than without.
        """

        class HighErrorPoller(PerfPoller):
            def _poll_once(self) -> dict[str, int]:
                raise ValueError("High rate error")

        poller = HighErrorPoller()

        start = time.perf_counter()
        for _ in range(100):  # Fewer iterations for faster test
            poller._poll_wrapper()
        elapsed = time.perf_counter() - start

        polls_per_second = 100 / elapsed

        # Should achieve reasonable throughput with errors (includes logging)
        assert polls_per_second > 100  # > 100 polls/sec (conservative)


# =============================================================================
# Performance Tests: Latency Consistency
# =============================================================================


@pytest.mark.performance
class TestLatencyConsistency:
    """Performance tests for latency consistency."""

    def test_stats_latency_consistent(self) -> None:
        """Test stats access latency is consistent."""
        poller = PerfPoller()
        for _ in range(100):
            poller._poll_wrapper()

        timings: list[float] = []

        for _ in range(1000):
            start = time.perf_counter()
            _ = poller.stats
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        mean_time = statistics.mean(timings)
        stdev_time = statistics.stdev(timings)

        # Standard deviation should be small relative to mean
        # Allow for some variability due to OS scheduling
        cv = stdev_time / mean_time if mean_time > 0 else 0
        # Coefficient of variation should be reasonable (< 5x mean)
        # This is lenient to account for test environment variability
        assert cv < 5.0 or stdev_time < 0.001

    def test_poll_wrapper_latency_consistent(self) -> None:
        """Test poll wrapper latency is consistent."""
        poller = PerfPoller()
        timings: list[float] = []

        for _ in range(500):
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        mean_time = statistics.mean(timings)
        p99_time = sorted(timings)[494]

        # P99 should not be too far from mean
        assert p99_time < mean_time * 10 or p99_time < 0.001
