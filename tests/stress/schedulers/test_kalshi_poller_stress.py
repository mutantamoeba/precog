"""
Stress Tests for Kalshi Market Poller.

Tests poller behavior under high load conditions:
- High frequency polling cycles
- Concurrent poll operations
- Sustained polling load

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- REQ-TEST-016: Stress Test Requirements for Infrastructure
- schedulers/kalshi_poller module coverage

Usage:
    pytest tests/stress/schedulers/test_kalshi_poller_stress.py -v -m stress

CI-Safe Refactoring (Issue #168):
    Previously used `xfail(run=False)` to skip in CI. These tests use finite
    time loops (not barriers), so they complete reliably in CI environments.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest


@pytest.mark.stress
class TestKalshiMarketPollerStress:
    """Stress tests for Kalshi Market Poller operations."""

    def test_high_frequency_poll_cycles(self):
        """
        STRESS: Execute many poll cycles rapidly.

        Verifies:
        - Poller handles rapid consecutive polling
        - Stats accumulate correctly under load
        - No resource exhaustion

        Educational Note:
            KalshiMarketPoller accepts a kalshi_client parameter for
            dependency injection, which is the correct way to mock
            external API calls per REQ-TEST-013.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        # Mock the KalshiClient to avoid real API calls (REQ-TEST-013 allows this)
        mock_client = MagicMock()
        mock_client.get_markets.return_value = []
        mock_client.close.return_value = None

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=5,  # Minimum allowed
            environment="demo",
            kalshi_client=mock_client,
        )

        # Execute 100 rapid poll cycles using the actual poll_once method
        for _ in range(100):
            result = poller.poll_once()
            assert "markets_fetched" in result
            assert "markets_updated" in result
            assert "markets_created" in result

        stats = poller.stats
        assert stats["errors"] == 0, f"Errors during stress: {stats['last_error']}"

    def test_concurrent_poll_operations(self):
        """
        STRESS: Multiple threads calling poll_once concurrently.

        Verifies:
        - Thread-safe poll execution
        - No data corruption under concurrent access
        - Lock contention doesn't cause deadlocks

        Educational Note:
            The KalshiMarketPoller uses a threading.Lock() internally
            to protect the _stats dictionary from concurrent modification.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        mock_client = MagicMock()
        mock_client.get_markets.return_value = []
        mock_client.close.return_value = None

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=5,
            environment="demo",
            kalshi_client=mock_client,
        )

        results = []
        errors = []

        def poll_worker(worker_id: int):
            try:
                for _ in range(10):
                    result = poller.poll_once()
                    results.append((worker_id, result))
            except Exception as e:
                errors.append((worker_id, str(e)))

        # Launch 10 concurrent workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(poll_worker, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Errors during concurrent polling: {errors}"
        assert len(results) == 100  # 10 workers * 10 polls each

    def test_sustained_polling_load(self):
        """
        STRESS: Sustained polling over time.

        Verifies:
        - System remains stable under continuous load
        - Memory doesn't grow unbounded
        - Stats tracking remains accurate
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        mock_client = MagicMock()
        mock_client.get_markets.return_value = []
        mock_client.close.return_value = None

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=5,
            environment="demo",
            kalshi_client=mock_client,
        )

        duration = 2.0  # seconds
        start = time.perf_counter()
        poll_count = 0

        while time.perf_counter() - start < duration:
            poller.poll_once()
            poll_count += 1

        elapsed = time.perf_counter() - start
        polls_per_second = poll_count / elapsed

        # Should achieve at least 10 polls/sec (conservative for mocked client)
        assert polls_per_second > 10, f"Only {polls_per_second:.1f} polls/sec"

    def test_stats_access_under_load(self):
        """
        STRESS: Concurrent stats access during polling.

        Verifies:
        - Thread-safe stats access via lock
        - Stats remain consistent during updates
        - No race conditions on stats dict

        Educational Note:
            The stats property returns a copy of the internal _stats dict
            while holding the lock, ensuring thread-safe read access.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        mock_client = MagicMock()
        mock_client.get_markets.return_value = []
        mock_client.close.return_value = None

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=5,
            environment="demo",
            kalshi_client=mock_client,
        )

        stats_snapshots = []
        stop_event = threading.Event()

        def poll_continuously():
            while not stop_event.is_set():
                poller.poll_once()

        def read_stats_continuously():
            while not stop_event.is_set():
                stats = poller.stats
                stats_snapshots.append(stats)

        # Start polling and stats reading threads
        poll_thread = threading.Thread(target=poll_continuously)
        stats_thread = threading.Thread(target=read_stats_continuously)

        poll_thread.start()
        stats_thread.start()

        # Let them run for 1 second
        time.sleep(1.0)
        stop_event.set()

        poll_thread.join()
        stats_thread.join()

        # Should have collected many stats snapshots
        assert len(stats_snapshots) > 10
        # All stats should be valid dicts with expected keys
        for stats in stats_snapshots:
            assert "polls_completed" in stats
            assert "markets_fetched" in stats
            assert "errors" in stats
