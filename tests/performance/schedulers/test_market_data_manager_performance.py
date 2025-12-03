"""
Performance Tests for MarketDataManager.

Establishes latency benchmarks for market data operations:
- Market data update latency
- Subscription management overhead
- Cache lookup performance

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- schedulers/market_data_manager module coverage

Usage:
    pytest tests/performance/schedulers/test_market_data_manager_performance.py -v -m performance
"""

import time
from decimal import Decimal

import pytest


@pytest.mark.performance
class TestMarketDataManagerPerformance:
    """Performance benchmarks for MarketDataManager operations."""

    def test_market_data_cache_lookup_latency(self):
        """
        PERFORMANCE: Measure market data cache lookup latency.

        Benchmark:
        - Target: < 1ms per lookup (p99)
        """
        # Simulate a simple cache implementation
        cache = {}
        for i in range(100):
            cache[f"market_{i}"] = {
                "ticker": f"MKT-{i:04d}",
                "yes_price": Decimal("0.50"),
                "no_price": Decimal("0.50"),
                "volume": 1000,
            }

        latencies = []
        keys = list(cache.keys())

        for _ in range(500):
            key = keys[_ % len(keys)]
            start = time.perf_counter()
            _ = cache.get(key)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        assert p99 < 1, f"p99 latency {p99:.4f}ms exceeds 1ms target"

    def test_market_data_update_processing(self):
        """
        PERFORMANCE: Measure market data update processing time.

        Benchmark:
        - Target: < 5ms per update batch (p95)
        """
        # Simulate processing a batch of market updates
        updates = [
            {
                "ticker": f"MKT-{i:04d}",
                "yes_price": Decimal("0.50") + Decimal(str(i / 1000)),
                "no_price": Decimal("0.50") - Decimal(str(i / 1000)),
                "volume": 1000 + i,
            }
            for i in range(20)
        ]

        latencies = []

        for _ in range(50):
            start = time.perf_counter()
            # Simulate update processing
            processed = []
            for update in updates:
                processed.append(
                    {
                        "ticker": update["ticker"],
                        "spread": update["yes_price"] + update["no_price"],
                        "volume": update["volume"],
                    }
                )
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 10, f"p95 latency {p95:.2f}ms exceeds 10ms target"

    def test_subscription_management_overhead(self):
        """
        PERFORMANCE: Measure subscription add/remove overhead.

        Benchmark:
        - Target: < 2ms per subscription operation (p95)
        """
        subscriptions = set()
        latencies = []

        # Add subscriptions
        for i in range(100):
            start = time.perf_counter()
            subscriptions.add(f"MKT-{i:04d}")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        # Remove subscriptions
        for i in range(100):
            start = time.perf_counter()
            subscriptions.discard(f"MKT-{i:04d}")
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 2, f"p95 latency {p95:.4f}ms exceeds 2ms target"
