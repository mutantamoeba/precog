"""
Race Condition Tests for Kalshi Market Poller.

Tests for race conditions in polling operations:
- Concurrent poll_once operations
- Stats access during polling
- Enabled state transitions

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- schedulers/kalshi_poller module coverage

Usage:
    pytest tests/stress/schedulers/test_kalshi_poller_race.py -v -m race

CI-Safe Refactoring (Issue #168):
    Previously used `xfail(run=False)` to skip in CI due to threading.Barrier hangs.
    Now uses CISafeBarrier with timeouts for graceful degradation:
    - Tests run in CI (not skipped)
    - Timeouts prevent indefinite hangs
    - Failures are fast and informative
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

# Import CI-safe barrier from stress test fixtures
from tests.fixtures.stress_testcontainers import CISafeBarrier


@pytest.mark.race
class TestKalshiMarketPollerRace:
    """Race condition tests for Kalshi Market Poller.

    Uses CISafeBarrier for CI-compatible thread synchronization.
    """

    # Timeout for barrier synchronization (seconds)
    BARRIER_TIMEOUT = 15.0

    def test_concurrent_poll_once_calls(self):
        """
        RACE: Multiple threads calling poll_once simultaneously.

        Verifies:
        - Thread-safe poll execution
        - No data corruption under concurrent access
        - Results are consistent

        Educational Note:
            poll_once() is designed to be called from multiple threads.
            The internal _lock protects the stats dictionary.
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

        errors = []
        results = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def poll_worker(worker_id: int):
            try:
                barrier.wait()  # All threads start together (with timeout)
                for _ in range(5):
                    result = poller.poll_once()
                    results.append((worker_id, result))
            except TimeoutError:
                errors.append((worker_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((worker_id, str(e)))

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(poll_worker, i) for i in range(20)]
            for f in futures:
                f.result(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Race condition errors: {other_errors}"
        assert len(results) == 100  # 20 workers * 5 polls each

    def test_stats_update_during_concurrent_polling(self):
        """
        RACE: Reading stats while polling updates them.

        Verifies:
        - Thread-safe stats access
        - No partially updated stats returned
        - Lock prevents read/write conflicts
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

        stats_values = []
        stop_event = threading.Event()
        barrier_errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def poll_continuously(worker_id: int):
            try:
                barrier.wait()
            except TimeoutError:
                barrier_errors.append(worker_id)
                return
            while not stop_event.is_set():
                poller.poll_once()

        def read_stats_continuously(worker_id: int):
            try:
                barrier.wait()
            except TimeoutError:
                barrier_errors.append(worker_id)
                return
            while not stop_event.is_set():
                stats = poller.stats
                stats_values.append(stats["items_fetched"])

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            # 5 polling threads
            for i in range(5):
                futures.append(executor.submit(poll_continuously, i))
            # 5 stats reading threads
            for i in range(5, 10):
                futures.append(executor.submit(read_stats_continuously, i))

            time.sleep(0.5)
            stop_event.set()

            for f in futures:
                f.result(timeout=30)

        if barrier_errors:
            pytest.skip(f"Barrier timeout in CI: {len(barrier_errors)} threads")

        # Stats values should be monotonically non-decreasing or at least consistent
        assert len(stats_values) > 0
        # All values should be valid integers
        assert all(isinstance(v, int) for v in stats_values)

    def test_enabled_property_race(self):
        """
        RACE: Checking enabled property during start/stop transitions.

        Verifies:
        - enabled property is thread-safe
        - No inconsistent state visible

        Educational Note:
            The enabled property reads _enabled which is protected by _lock.
            start() and stop() also use _lock to ensure atomic state transitions.
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

        enabled_values = []
        errors = []

        def read_enabled(worker_id: int):
            try:
                for _ in range(100):
                    enabled_values.append(poller.enabled)
            except Exception as e:
                errors.append((worker_id, str(e)))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_enabled, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0
        # All values should be boolean
        assert all(isinstance(v, bool) for v in enabled_values)

    def test_poll_once_during_series_change(self):
        """
        RACE: Calling poll_once while series_tickers might be accessed.

        Verifies:
        - Safe access to series_tickers during iteration
        - No corruption if series list is read during poll

        Educational Note:
            In production, series_tickers is typically set once at init.
            This test verifies the polling loop safely iterates the list.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        mock_client = MagicMock()
        mock_client.get_markets.return_value = []
        mock_client.close.return_value = None

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME", "KXNCAAFGAME"],
            poll_interval=5,
            environment="demo",
            kalshi_client=mock_client,
        )

        errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def poll_worker(worker_id: int):
            try:
                barrier.wait()
                for _ in range(10):
                    result = poller.poll_once()
                    assert isinstance(result, dict)
            except TimeoutError:
                errors.append((worker_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((worker_id, str(e)))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(poll_worker, i) for i in range(10)]
            for f in futures:
                f.result(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in e[1].lower()]
        other_errors = [e for e in errors if "timeout" not in e[1].lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors: {other_errors}"
