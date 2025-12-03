"""
Performance Tests for Kalshi Market Poller.

Establishes latency benchmarks for polling operations:
- Poll cycle latency
- Stats access latency
- Market data processing speed

Related:
- TESTING_STRATEGY V3.3: All 8 test types required
- schedulers/kalshi_poller module coverage

Usage:
    pytest tests/performance/schedulers/test_kalshi_poller_performance.py -v -m performance

Note: All tests skipped - schedulers module not yet implemented (Phase 1.9+).
The KalshiMarketPoller class will be implemented in Phase 1.9.
"""

import time
from unittest.mock import MagicMock

import pytest


@pytest.mark.skip(reason="schedulers module not yet implemented - Phase 1.9+")
@pytest.mark.performance
class TestKalshiMarketPollerPerformance:
    """Performance benchmarks for Kalshi Market Poller operations."""

    def test_poll_once_latency(self):
        """
        PERFORMANCE: Measure single poll_once latency.

        Benchmark:
        - Target: < 50ms per poll cycle (p95)
        - SLA: < 100ms per poll cycle (p99)

        Educational Note:
            poll_once() iterates through all series_tickers and calls
            the Kalshi client for each. With a mocked client, we measure
            the overhead of the polling logic itself.
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

        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            poller.poll_once()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        assert p95 < 50, f"p95 latency {p95:.2f}ms exceeds 50ms target"
        assert p99 < 100, f"p99 latency {p99:.2f}ms exceeds 100ms SLA"

    def test_stats_access_latency(self):
        """
        PERFORMANCE: Measure stats property access latency.

        Benchmark:
        - Target: < 1ms per access (p95)

        Educational Note:
            The stats property acquires a lock and returns a copy of
            the internal _stats dict. This should be very fast.
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

        latencies = []

        for _ in range(1000):
            start = time.perf_counter()
            _ = poller.stats
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 1, f"p95 stats access latency {p95:.4f}ms exceeds 1ms target"

    def test_market_data_processing_speed(self):
        """
        PERFORMANCE: Measure processing speed with realistic market data.

        Benchmark:
        - Target: < 100ms to process 100 markets (p95)

        Educational Note:
            This tests the full poll_once cycle with a realistic
            number of markets returned from the API.
        """
        from precog.schedulers.kalshi_poller import KalshiMarketPoller

        # Create mock with realistic market data
        mock_client = MagicMock()
        mock_client.get_markets.return_value = [
            {
                "ticker": f"KXNFL-{i:04d}",
                "event_ticker": "KXNFLGAME",
                "series_ticker": "KXNFLGAME",
                "title": f"Test Market {i}",
                "yes_ask": 50 + (i % 10),
                "no_ask": 50 - (i % 10),
                "status": "open",
                "volume": 1000 * i,
                "open_interest": 500 * i,
            }
            for i in range(100)
        ]
        mock_client.close.return_value = None

        poller = KalshiMarketPoller(
            series_tickers=["KXNFLGAME"],
            poll_interval=5,
            environment="demo",
            kalshi_client=mock_client,
        )

        latencies = []

        for _ in range(50):
            start = time.perf_counter()
            poller.poll_once()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100, f"p95 processing time {p95:.2f}ms exceeds 100ms target"

    def test_polling_throughput(self):
        """
        PERFORMANCE: Measure overall polling throughput.

        Benchmark:
        - Target: >= 50 polls/sec

        Educational Note:
            With a mocked client, throughput is limited only by the
            polling logic overhead. In production, network latency
            will be the limiting factor.
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

        operations = 100
        start = time.perf_counter()

        for _ in range(operations):
            poller.poll_once()

        elapsed = time.perf_counter() - start
        throughput = operations / elapsed

        assert throughput >= 50, f"Throughput {throughput:.1f} polls/sec below 50/sec minimum"
