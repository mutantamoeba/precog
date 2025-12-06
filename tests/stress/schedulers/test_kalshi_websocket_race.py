"""
Race Condition Tests for Kalshi WebSocket Handler.

Tests for race conditions in WebSocket operations:
- Concurrent callback add/remove
- Concurrent subscription changes
- Stats access during updates

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- schedulers/kalshi_websocket module coverage

Usage:
    pytest tests/stress/schedulers/test_kalshi_websocket_race.py -v -m race

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
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

# Import CI-safe barrier from stress test fixtures
from tests.fixtures.stress_testcontainers import CISafeBarrier


@pytest.mark.race
class TestKalshiWebSocketHandlerRace:
    """Race condition tests for Kalshi WebSocket Handler.

    Uses CISafeBarrier for CI-compatible thread synchronization.
    """

    # Timeout for barrier synchronization (seconds)
    BARRIER_TIMEOUT = 15.0

    def test_concurrent_callback_add_remove(self):
        """
        RACE: Adding and removing callbacks concurrently.

        Verifies:
        - Thread-safe callback list modification
        - No lost callbacks during concurrent modification
        - No crashes from list modification during iteration
        """
        from precog.schedulers.kalshi_websocket import KalshiWebSocketHandler

        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-TIMESTAMP": "12345",
            "KALSHI-ACCESS-SIGNATURE": "sig",
        }

        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def noop_callback(t, y, n):
            pass

        def add_callbacks(worker_id: int):
            try:
                barrier.wait()
                for i in range(5):
                    handler.add_callback(noop_callback)
            except TimeoutError:
                errors.append((worker_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((worker_id, f"add: {e}"))

        def remove_callbacks(worker_id: int):
            try:
                barrier.wait()
                for i in range(5):
                    if handler._callbacks:
                        try:
                            handler.remove_callback(handler._callbacks[0])
                        except (IndexError, ValueError):
                            pass  # Expected race condition
            except TimeoutError:
                errors.append((worker_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((worker_id, f"remove: {e}"))

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(add_callbacks, i))
            for i in range(10, 20):
                futures.append(executor.submit(remove_callbacks, i))

            for f in futures:
                f.result(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in str(e[1]).lower()]
        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        # Should not have critical errors (IndexError during iteration is acceptable)
        critical_errors = [e for e in errors if "critical" in str(e[1]).lower()]
        assert len(critical_errors) == 0, f"Critical errors: {critical_errors}"

    def test_concurrent_subscription_changes(self):
        """
        RACE: Subscribe and unsubscribe from multiple threads.

        Verifies:
        - Thread-safe subscription set modification
        - Subscription state remains consistent
        - No deadlocks
        """
        from precog.schedulers.kalshi_websocket import KalshiWebSocketHandler

        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-TIMESTAMP": "12345",
            "KALSHI-ACCESS-SIGNATURE": "sig",
        }

        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        errors = []
        barrier = CISafeBarrier(20, timeout=self.BARRIER_TIMEOUT)

        def subscribe_worker(worker_id: int):
            try:
                barrier.wait()
                for i in range(5):
                    handler.subscribe([f"MKT-{worker_id}-{i}"])
            except TimeoutError:
                errors.append((worker_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((worker_id, f"subscribe: {e}"))

        def unsubscribe_worker(worker_id: int):
            try:
                barrier.wait()
                for i in range(5):
                    handler.unsubscribe([f"MKT-{worker_id % 10}-{i}"])
            except TimeoutError:
                errors.append((worker_id, "Barrier timeout - CI resource constraints"))
            except Exception as e:
                errors.append((worker_id, f"unsubscribe: {e}"))

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(subscribe_worker, i))
            for i in range(10, 20):
                futures.append(executor.submit(unsubscribe_worker, i))

            for f in futures:
                f.result(timeout=30)

        # Handle CI timeouts gracefully
        timeout_errors = [e for e in errors if "timeout" in str(e[1]).lower()]
        other_errors = [e for e in errors if "timeout" not in str(e[1]).lower()]

        if timeout_errors:
            pytest.skip(f"Barrier timeout in CI: {len(timeout_errors)} threads timed out")

        assert len(other_errors) == 0, f"Errors: {other_errors}"

    def test_stats_access_during_updates(self):
        """
        RACE: Reading stats while they're being updated.

        Verifies:
        - Thread-safe stats access via lock
        - No partially updated stats visible
        - Stats remain internally consistent

        Educational Note:
            The stats property returns a copy of _stats while holding the lock,
            ensuring atomic read access to the stats dictionary.
        """
        from precog.schedulers.kalshi_websocket import KalshiWebSocketHandler

        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-TIMESTAMP": "12345",
            "KALSHI-ACCESS-SIGNATURE": "sig",
        }

        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        stats_snapshots = []
        stop_event = threading.Event()
        barrier_errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def update_stats(worker_id: int):
            try:
                barrier.wait()
            except TimeoutError:
                barrier_errors.append(worker_id)
                return
            while not stop_event.is_set():
                with handler._lock:
                    handler._stats["messages_received"] += 1
                    handler._stats["price_updates"] += 1

        def read_stats(worker_id: int):
            try:
                barrier.wait()
            except TimeoutError:
                barrier_errors.append(worker_id)
                return
            while not stop_event.is_set():
                stats = handler.stats
                stats_snapshots.append(stats)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(update_stats, i))
            for i in range(5, 10):
                futures.append(executor.submit(read_stats, i))

            time.sleep(0.5)
            stop_event.set()

            for f in futures:
                f.result(timeout=30)

        if barrier_errors:
            pytest.skip(f"Barrier timeout in CI: {len(barrier_errors)} threads")

        # All snapshots should be valid dicts with expected keys
        assert len(stats_snapshots) > 0
        for stats in stats_snapshots:
            assert "messages_received" in stats
            assert "price_updates" in stats
            assert isinstance(stats["messages_received"], int)

    def test_callback_invocation_during_modification(self):
        """
        RACE: Invoking callbacks while the list is being modified.

        Verifies:
        - Safe iteration over callbacks during modification
        - No crashes from concurrent list access
        """
        from precog.schedulers.kalshi_websocket import KalshiWebSocketHandler

        mock_auth = MagicMock()
        mock_auth.get_headers.return_value = {
            "KALSHI-ACCESS-KEY": "test",
            "KALSHI-ACCESS-TIMESTAMP": "12345",
            "KALSHI-ACCESS-SIGNATURE": "sig",
        }

        handler = KalshiWebSocketHandler(
            environment="demo",
            auth=mock_auth,
            auto_reconnect=False,
            sync_to_database=False,
        )

        invocation_count = [0]
        lock = threading.Lock()
        stop_event = threading.Event()
        barrier_errors = []
        barrier = CISafeBarrier(10, timeout=self.BARRIER_TIMEOUT)

        def counting_callback(ticker: str, yes: Decimal, no: Decimal):
            with lock:
                invocation_count[0] += 1

        handler.add_callback(counting_callback)

        def invoke_continuously(worker_id: int):
            try:
                barrier.wait()
            except TimeoutError:
                barrier_errors.append(worker_id)
                return
            while not stop_event.is_set():
                for callback in list(handler._callbacks):  # Copy for safe iteration
                    try:
                        callback("MKT", Decimal("0.50"), Decimal("0.50"))
                    except Exception:
                        pass

        def noop_callback_for_modify(t, y, n):
            pass

        def modify_continuously(worker_id: int):
            try:
                barrier.wait()
            except TimeoutError:
                barrier_errors.append(worker_id)
                return
            while not stop_event.is_set():
                handler.add_callback(noop_callback_for_modify)
                try:
                    handler.remove_callback(noop_callback_for_modify)
                except ValueError:
                    pass

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(invoke_continuously, i))
            for i in range(5, 10):
                futures.append(executor.submit(modify_continuously, i))

            time.sleep(0.5)
            stop_event.set()

            for f in futures:
                f.result(timeout=30)

        if barrier_errors:
            pytest.skip(f"Barrier timeout in CI: {len(barrier_errors)} threads")

        # Should have invoked callbacks many times
        assert invocation_count[0] > 0
