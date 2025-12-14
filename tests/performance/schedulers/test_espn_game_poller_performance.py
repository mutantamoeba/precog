"""
Performance Tests for ESPN Game Poller.

Tests latency and throughput of ESPNGamePoller operations.

Reference: TESTING_STRATEGY V3.2 - Performance tests for latency/throughput
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/performance/schedulers/test_espn_game_poller_performance.py -v -m performance
"""

import statistics
import time
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


# =============================================================================
# Performance Tests: Initialization Latency
# =============================================================================


@pytest.mark.performance
class TestInitializationLatency:
    """Performance tests for initialization latency."""

    def test_poller_creation_latency(self) -> None:
        """Test poller creation is fast."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            timings: list[float] = []

            for _ in range(100):
                start = time.perf_counter()
                _ = ESPNGamePoller()
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

            avg_time = statistics.mean(timings)
            p95_time = sorted(timings)[94]

            # Creation should be fast
            assert avg_time < 0.01  # < 10ms average
            assert p95_time < 0.02  # < 20ms p95

    def test_poller_with_custom_config_latency(self) -> None:
        """Test poller creation with custom config."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            timings: list[float] = []

            for i in range(100):
                start = time.perf_counter()
                _ = ESPNGamePoller(
                    leagues=["nfl", "nba"],
                    poll_interval=10 + i % 50,
                    idle_interval=30 + i % 60,
                )
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

            avg_time = statistics.mean(timings)
            assert avg_time < 0.01  # < 10ms average


# =============================================================================
# Performance Tests: Stats Access Latency
# =============================================================================


@pytest.mark.performance
class TestStatsAccessLatency:
    """Performance tests for stats access latency."""

    def test_stats_property_latency(self, mock_espn_client: MagicMock) -> None:
        """Test stats property access is fast."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

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
        p95_time = sorted(timings)[949]
        max_time = max(timings)

        assert avg_time < 0.0001  # < 100us average
        assert p95_time < 0.0005  # < 500us p95
        assert max_time < 0.001  # < 1ms max

    def test_get_stats_method_latency(self, mock_espn_client: MagicMock) -> None:
        """Test get_stats() method latency."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

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


# =============================================================================
# Performance Tests: Poll Wrapper Latency
# =============================================================================


@pytest.mark.performance
class TestPollWrapperLatency:
    """Performance tests for poll wrapper latency."""

    def test_poll_wrapper_latency(self, mock_espn_client: MagicMock) -> None:
        """Test poll wrapper overhead is minimal."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        timings: list[float] = []

        for _ in range(1000):
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        p95_time = sorted(timings)[949]

        # Poll wrapper should be fast (excluding actual API call)
        assert avg_time < 0.001  # < 1ms average
        assert p95_time < 0.002  # < 2ms p95

    def test_poll_once_latency(self, mock_espn_client: MagicMock) -> None:
        """Test poll_once latency."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        timings: list[float] = []

        for _ in range(500):
            start = time.perf_counter()
            poller.poll_once()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)
        assert avg_time < 0.001  # < 1ms average


# =============================================================================
# Performance Tests: Throughput
# =============================================================================


@pytest.mark.performance
class TestThroughput:
    """Performance tests for throughput."""

    def test_polls_per_second(self, mock_espn_client: MagicMock) -> None:
        """Test polling throughput."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poll_count = 10000

        start = time.perf_counter()
        for _ in range(poll_count):
            poller._poll_wrapper()
        elapsed = time.perf_counter() - start

        polls_per_second = poll_count / elapsed

        # Should achieve high throughput
        assert polls_per_second > 5000  # > 5k polls/sec

    def test_stats_reads_per_second(self, mock_espn_client: MagicMock) -> None:
        """Test stats reading throughput."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

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


# =============================================================================
# Performance Tests: Start/Stop Latency
# =============================================================================


@pytest.mark.performance
class TestStartStopLatency:
    """Performance tests for start/stop latency."""

    def test_start_latency(self, mock_espn_client: MagicMock) -> None:
        """Test scheduler start latency."""
        timings: list[float] = []

        for _ in range(20):
            poller = ESPNGamePoller(
                poll_interval=5,
                leagues=["nfl"],
                espn_client=mock_espn_client,
            )

            start = time.perf_counter()
            poller.start()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            poller.stop()

        avg_time = statistics.mean(timings)

        # Start should be reasonably fast
        assert avg_time < 0.1  # < 100ms average

    def test_stop_latency(self, mock_espn_client: MagicMock) -> None:
        """Test scheduler stop latency."""
        timings: list[float] = []

        for _ in range(20):
            poller = ESPNGamePoller(
                poll_interval=5,
                leagues=["nfl"],
                espn_client=mock_espn_client,
            )
            poller.start()
            time.sleep(0.1)

            start = time.perf_counter()
            poller.stop()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)

        # Stop should be reasonably fast
        assert avg_time < 0.5  # < 500ms average


# =============================================================================
# Performance Tests: Status Normalization
# =============================================================================


@pytest.mark.performance
class TestStatusNormalizationPerformance:
    """Performance tests for status normalization."""

    def test_normalize_status_latency(self, mock_espn_client: MagicMock) -> None:
        """Test status normalization is fast."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        statuses = ["pre", "in", "halftime", "final", "unknown"]
        timings: list[float] = []

        for _ in range(10000):
            for status in statuses:
                start = time.perf_counter()
                _ = poller._normalize_game_status(status)
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

        avg_time = statistics.mean(timings)
        assert avg_time < 0.00001  # < 10us average

    def test_normalize_status_throughput(self, mock_espn_client: MagicMock) -> None:
        """Test status normalization throughput."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        count = 100000

        start = time.perf_counter()
        for _ in range(count):
            poller._normalize_game_status("in_progress")
        elapsed = time.perf_counter() - start

        normalizations_per_second = count / elapsed
        assert normalizations_per_second > 1000000  # > 1M/sec


# =============================================================================
# Performance Tests: Memory Efficiency
# =============================================================================


@pytest.mark.performance
class TestMemoryEfficiency:
    """Performance tests for memory efficiency."""

    def test_stats_copy_size_constant(self, mock_espn_client: MagicMock) -> None:
        """Test stats copy size doesn't grow with polls."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        initial_stats = poller.stats
        initial_keys = len(initial_stats)

        for _ in range(10000):
            poller._poll_wrapper()

        final_stats = poller.stats
        final_keys = len(final_stats)

        assert initial_keys == final_keys == 7

    def test_many_pollers_reasonable_memory(self) -> None:
        """Test creating many pollers doesn't use excessive memory."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            pollers: list[ESPNGamePoller] = []

            for _ in range(100):
                p = ESPNGamePoller(leagues=["nfl"])
                pollers.append(p)

            for p in pollers:
                assert p.stats["polls_completed"] == 0


# =============================================================================
# Performance Tests: Error Handling Overhead
# =============================================================================


@pytest.mark.performance
class TestErrorHandlingOverhead:
    """Performance tests for error handling overhead."""

    def test_error_handling_latency(self, mock_espn_client: MagicMock) -> None:
        """Test error handling doesn't add significant latency."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError("Error")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        timings: list[float] = []

        for _ in range(100):
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)

        # Error handling should be reasonably fast (includes logging)
        assert avg_time < 0.01  # < 10ms average

    def test_error_rate_no_performance_degradation(self, mock_espn_client: MagicMock) -> None:
        """Test high error rate doesn't degrade performance significantly."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError("Error")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        start = time.perf_counter()
        for _ in range(100):
            poller._poll_wrapper()
        elapsed = time.perf_counter() - start

        polls_per_second = 100 / elapsed

        # Should achieve reasonable throughput with errors
        assert polls_per_second > 100  # > 100 polls/sec (conservative)


# =============================================================================
# Performance Tests: Multi-League Performance
# =============================================================================


@pytest.mark.performance
class TestMultiLeaguePerformance:
    """Performance tests for multi-league polling."""

    def test_multi_league_poll_latency(self, mock_espn_client: MagicMock) -> None:
        """Test polling multiple leagues latency."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        timings: list[float] = []

        for _ in range(100):
            start = time.perf_counter()
            poller.poll_once()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        avg_time = statistics.mean(timings)

        # Multi-league should still be fast
        assert avg_time < 0.005  # < 5ms average for 4 leagues


# =============================================================================
# Performance Tests: Latency Consistency
# =============================================================================


@pytest.mark.performance
class TestLatencyConsistency:
    """Performance tests for latency consistency."""

    def test_stats_latency_consistent(self, mock_espn_client: MagicMock) -> None:
        """Test stats access latency is consistent."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

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

        cv = stdev_time / mean_time if mean_time > 0 else 0
        assert cv < 5.0 or stdev_time < 0.001

    def test_poll_wrapper_latency_consistent(self, mock_espn_client: MagicMock) -> None:
        """Test poll wrapper latency is consistent."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        timings: list[float] = []

        for _ in range(500):
            start = time.perf_counter()
            poller._poll_wrapper()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        mean_time = statistics.mean(timings)
        p99_time = sorted(timings)[494]

        assert p99_time < mean_time * 10 or p99_time < 0.002
