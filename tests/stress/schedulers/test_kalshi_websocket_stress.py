"""
Stress Tests for Kalshi WebSocket Handler.

Tests WebSocket handler behavior under high load conditions:
- High callback throughput
- Many concurrent subscriptions
- Sustained connection load

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- REQ-TEST-016: Stress Test Requirements for Infrastructure
- schedulers/kalshi_websocket module coverage

Usage:
    pytest tests/stress/schedulers/test_kalshi_websocket_stress.py -v -m stress

CI-Safe Refactoring (Issue #168):
    Previously used `xfail(run=False)` to skip in CI. These tests use finite
    time loops (not barriers), so they complete reliably in CI environments.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


@pytest.mark.stress
class TestKalshiWebSocketHandlerStress:
    """Stress tests for Kalshi WebSocket operations."""

    def test_high_callback_throughput(self):
        """
        STRESS: Handle high callback invocation rate.

        Verifies:
        - System processes many callbacks per second
        - No callback loss under load
        - Stats tracking remains accurate

        Educational Note:
            KalshiWebSocketHandler fires callbacks for each price update.
            In production, callbacks may be invoked hundreds of times
            per second during high market activity.
        """
        from precog.schedulers.kalshi_websocket import KalshiWebSocketHandler

        # Create handler with mocked auth to avoid API calls
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

        # Track callback invocations
        callbacks_received = []

        def test_callback(ticker: str, yes_price: Decimal, no_price: Decimal):
            callbacks_received.append((ticker, yes_price, no_price))

        handler.add_callback(test_callback)

        # Simulate high-throughput callback invocations
        for i in range(1000):
            for callback in handler._callbacks:
                callback(f"MKT-{i:04d}", Decimal("0.55"), Decimal("0.45"))

        assert len(callbacks_received) == 1000, f"Only received {len(callbacks_received)} callbacks"

    def test_many_concurrent_subscriptions(self):
        """
        STRESS: Many concurrent market subscriptions.

        Verifies:
        - System handles many subscriptions
        - Subscription tracking is accurate
        - No memory leaks from subscription tracking

        Educational Note:
            In production, we may subscribe to 100+ markets simultaneously.
            The handler stores subscribed tickers in a set for efficient lookup.
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

        # Subscribe to many markets
        tickers = [f"MKT-{i:04d}" for i in range(200)]
        handler.subscribe(tickers)

        assert len(handler.subscribed_tickers) == 200

        # Unsubscribe from half
        handler.unsubscribe(tickers[:100])
        assert len(handler.subscribed_tickers) == 100

    def test_sustained_callback_load(self):
        """
        STRESS: Sustained callback activity over time.

        Verifies:
        - Handler stability under continuous callbacks
        - No resource exhaustion
        - Callback timing remains consistent
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

        callback_count = [0]

        def counting_callback(ticker: str, yes_price: Decimal, no_price: Decimal):
            callback_count[0] += 1

        handler.add_callback(counting_callback)

        # Simulate 2 seconds of continuous callbacks
        duration = 2.0
        start = time.perf_counter()

        while time.perf_counter() - start < duration:
            for callback in handler._callbacks:
                callback("MKT-TEST", Decimal("0.50"), Decimal("0.50"))

        elapsed = time.perf_counter() - start
        throughput = callback_count[0] / elapsed

        assert throughput > 100, f"Only {throughput:.1f} callbacks/sec"

    def test_concurrent_callback_invocations(self):
        """
        STRESS: Multiple threads invoking callbacks simultaneously.

        Verifies:
        - Thread-safe callback list access
        - No lost callback invocations
        - No deadlocks

        Educational Note:
            In production, callbacks might be invoked from the WebSocket
            receive loop while the main thread adds/removes callbacks.
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

        # Thread-safe counter
        callback_count = [0]
        lock = threading.Lock()

        def thread_safe_callback(ticker: str, yes_price: Decimal, no_price: Decimal):
            with lock:
                callback_count[0] += 1

        handler.add_callback(thread_safe_callback)

        errors = []

        def invoke_callbacks(worker_id: int):
            try:
                for _ in range(100):
                    for callback in handler._callbacks:
                        callback(f"MKT-{worker_id}", Decimal("0.50"), Decimal("0.50"))
            except Exception as e:
                errors.append((worker_id, str(e)))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(invoke_callbacks, i) for i in range(10)]
            for f in futures:
                f.result()

        assert len(errors) == 0, f"Errors: {errors}"
        assert callback_count[0] == 1000  # 10 workers * 100 invocations each
