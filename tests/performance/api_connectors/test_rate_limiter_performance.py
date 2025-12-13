"""
Performance tests for TokenBucket and RateLimiter.

Validates latency and throughput requirements for rate limiting.

Reference: TESTING_STRATEGY_V3.2.md Section "Performance Tests"
"""

import time

import pytest

from precog.api_connectors.rate_limiter import RateLimiter, TokenBucket


@pytest.mark.performance
class TestTokenBucketPerformance:
    """Performance benchmarks for TokenBucket."""

    def test_acquire_latency(self) -> None:
        """Test that non-blocking acquire is fast (<1ms)."""
        bucket = TokenBucket(capacity=10000, refill_rate=1000)

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            bucket.acquire(block=False)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Average should be under 0.1ms, max under 5ms
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"
        assert max_latency < 0.005, f"Max latency {max_latency * 1000:.3f}ms too high"

    def test_get_available_tokens_latency(self) -> None:
        """Test that checking available tokens is fast."""
        bucket = TokenBucket(capacity=1000, refill_rate=100)

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            bucket.get_available_tokens()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_throughput_non_blocking(self) -> None:
        """Test throughput of non-blocking acquire operations."""
        bucket = TokenBucket(capacity=100000, refill_rate=100000)

        start = time.perf_counter()
        count = 0
        for _ in range(10000):
            if bucket.acquire(block=False):
                count += 1
        elapsed = time.perf_counter() - start

        throughput = count / elapsed
        # Should handle at least 100k ops/sec
        assert throughput > 100000, f"Throughput {throughput:.0f} ops/sec too low"


@pytest.mark.performance
class TestRateLimiterPerformance:
    """Performance benchmarks for RateLimiter."""

    def test_wait_if_needed_latency_when_available(self) -> None:
        """Test that wait_if_needed is fast when tokens available."""
        limiter = RateLimiter(requests_per_minute=60000, burst_size=10000)

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            limiter.wait_if_needed()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_utilization_calculation_latency(self) -> None:
        """Test that utilization calculation is fast."""
        limiter = RateLimiter(requests_per_minute=6000)

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            limiter.get_utilization()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.0001, f"Average latency {avg_latency * 1000:.3f}ms too high"

    def test_initialization_performance(self) -> None:
        """Test that rate limiter initialization is fast."""
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            RateLimiter(requests_per_minute=100)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        # Should initialize in under 1ms
        assert avg_latency < 0.001, f"Initialization {avg_latency * 1000:.3f}ms too slow"
