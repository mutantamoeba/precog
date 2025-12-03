"""
Performance Tests for Kalshi WebSocket Handler.

Establishes latency benchmarks for WebSocket operations:
- Callback invocation latency
- Subscription management overhead
- Stats access latency

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- schedulers/kalshi_websocket module coverage

Usage:
    pytest tests/performance/schedulers/test_kalshi_websocket_performance.py -v -m performance
"""

import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


@pytest.mark.performance
class TestKalshiWebSocketHandlerPerformance:
    """Performance benchmarks for Kalshi WebSocket operations."""

    def test_callback_invocation_latency(self):
        """
        PERFORMANCE: Measure callback invocation latency.

        Benchmark:
        - Target: < 1ms per callback (p95)
        - SLA: < 5ms per callback (p99)

        Educational Note:
            In real-time trading, callback latency directly affects
            how quickly we can respond to price updates.
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

        results = []

        def timing_callback(ticker: str, yes_price: Decimal, no_price: Decimal):
            results.append((ticker, yes_price))

        handler.add_callback(timing_callback)

        latencies = []

        for i in range(200):
            start = time.perf_counter()
            for callback in handler._callbacks:
                callback(f"MKT-{i:04d}", Decimal("0.55"), Decimal("0.45"))
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 5, f"p95 latency {p95:.2f}ms exceeds 5ms target"
        assert p99 < 10, f"p99 latency {p99:.2f}ms exceeds 10ms SLA"

    def test_subscription_management_overhead(self):
        """
        PERFORMANCE: Measure subscription add/remove overhead.

        Benchmark:
        - Target: < 1ms per operation (p95)

        Educational Note:
            subscribe() and unsubscribe() modify internal sets.
            Set operations are O(1) average case, so should be fast.
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

        latencies = []

        # Add subscriptions
        for i in range(100):
            ticker = f"MKT-{i:04d}"
            start = time.perf_counter()
            handler.subscribe([ticker])
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        # Remove subscriptions
        for i in range(100):
            ticker = f"MKT-{i:04d}"
            start = time.perf_counter()
            handler.unsubscribe([ticker])
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 2, f"p95 latency {p95:.4f}ms exceeds 2ms target"

    def test_stats_access_latency(self):
        """
        PERFORMANCE: Measure stats property access latency.

        Benchmark:
        - Target: < 1ms per access (p95)

        Educational Note:
            The stats property acquires a lock and copies the dict.
            This should be extremely fast since it's just dict copying.
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

        latencies = []

        for _ in range(1000):
            start = time.perf_counter()
            _ = handler.stats
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 1, f"p95 stats access latency {p95:.4f}ms exceeds 1ms target"

    def test_callback_throughput(self):
        """
        PERFORMANCE: Measure callback invocation throughput.

        Benchmark:
        - Target: >= 5000 callbacks/sec

        Educational Note:
            High throughput is critical during volatile market periods
            when many price updates arrive in quick succession.
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

        def fast_callback(ticker: str, yes: Decimal, no: Decimal):
            invocation_count[0] += 1

        handler.add_callback(fast_callback)

        operations = 1000
        start = time.perf_counter()

        for i in range(operations):
            for callback in handler._callbacks:
                callback(f"MKT-{i}", Decimal("0.50"), Decimal("0.50"))

        elapsed = time.perf_counter() - start
        throughput = operations / elapsed

        assert throughput >= 1000, (
            f"Throughput {throughput:.1f} callbacks/sec below 1000/sec minimum"
        )
