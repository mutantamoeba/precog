"""
Stress tests for TokenBucket and RateLimiter.

Tests high-volume concurrent access patterns to validate thread safety
and rate limiting behavior under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from precog.api_connectors.rate_limiter import RateLimiter, TokenBucket


@pytest.mark.stress
class TestTokenBucketStress:
    """Stress tests for TokenBucket thread safety."""

    def test_concurrent_acquisitions_no_race_condition(self) -> None:
        """Verify thread safety with many concurrent token acquisitions."""
        bucket = TokenBucket(capacity=1000, refill_rate=100)
        acquired_count = 0
        lock = threading.Lock()

        def acquire_tokens() -> int:
            nonlocal acquired_count
            count = 0
            for _ in range(10):
                if bucket.acquire(block=False):
                    with lock:
                        acquired_count += 1
                    count += 1
            return count

        # Run 100 threads concurrently
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(acquire_tokens) for _ in range(100)]
            for future in as_completed(futures):
                future.result()  # Ensure no exceptions

        # Should never exceed initial capacity
        assert acquired_count <= 1000

    def test_sustained_load_respects_refill_rate(self) -> None:
        """Test that sustained load respects the refill rate."""
        # 10 tokens/second, capacity 10
        bucket = TokenBucket(capacity=10, refill_rate=10)

        # Drain the bucket
        for _ in range(10):
            bucket.acquire(block=False)

        # Wait for refill
        time.sleep(0.5)  # Should refill 5 tokens

        # Should be able to acquire some tokens
        acquired = 0
        for _ in range(10):
            if bucket.acquire(block=False):
                acquired += 1

        assert 3 <= acquired <= 7  # Approximately 5 tokens

    def test_burst_then_steady(self) -> None:
        """Test burst followed by steady-state acquisition."""
        bucket = TokenBucket(capacity=100, refill_rate=50)

        # Burst: acquire all tokens quickly
        burst_count = 0
        for _ in range(100):
            if bucket.acquire(block=False):
                burst_count += 1

        assert burst_count >= 95  # Should get most tokens

        # Steady: wait and acquire at rate
        time.sleep(0.2)  # Should refill ~10 tokens
        steady_count = 0
        for _ in range(20):
            if bucket.acquire(block=False):
                steady_count += 1

        assert steady_count >= 5  # Should get some refilled tokens


@pytest.mark.stress
class TestRateLimiterStress:
    """Stress tests for RateLimiter under concurrent load."""

    def test_many_threads_waiting(self) -> None:
        """Test many threads waiting for rate limit."""
        limiter = RateLimiter(requests_per_minute=600, burst_size=10)

        results = []
        lock = threading.Lock()

        def make_request() -> float:
            start = time.time()
            limiter.wait_if_needed()
            elapsed = time.time() - start
            with lock:
                results.append(elapsed)
            return elapsed

        # 20 threads, but only 10 burst capacity
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            for future in as_completed(futures, timeout=5):
                future.result()

        # Some should have waited
        waited = sum(1 for r in results if r > 0.01)
        assert waited >= 5  # At least half should have waited

    def test_utilization_under_load(self) -> None:
        """Test utilization tracking under concurrent load."""
        limiter = RateLimiter(requests_per_minute=600, burst_size=100)

        # Make many requests
        for _ in range(50):
            limiter.bucket.acquire(block=False)

        util = limiter.get_utilization()
        assert 0.4 <= util <= 0.6  # Approximately 50% utilized


@pytest.mark.race
class TestTokenBucketRaceConditions:
    """Race condition tests for TokenBucket."""

    def test_acquire_and_refill_race(self) -> None:
        """Test for race between acquire and refill operations."""
        bucket = TokenBucket(capacity=100, refill_rate=1000)

        errors = []

        def aggressive_acquire() -> None:
            for _ in range(100):
                try:
                    bucket.acquire(block=False)
                except Exception as e:
                    errors.append(e)

        def check_tokens() -> None:
            for _ in range(100):
                try:
                    tokens = bucket.get_available_tokens()
                    if tokens < 0:
                        errors.append(ValueError(f"Negative tokens: {tokens}"))
                except Exception as e:
                    errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=aggressive_acquire))
            threads.append(threading.Thread(target=check_tokens))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race conditions detected: {errors}"

    def test_concurrent_get_available_tokens(self) -> None:
        """Test concurrent calls to get_available_tokens don't corrupt state."""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        results = []
        lock = threading.Lock()

        def check_many() -> None:
            for _ in range(100):
                tokens = bucket.get_available_tokens()
                with lock:
                    results.append(tokens)

        threads = [threading.Thread(target=check_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be valid (non-negative, <= capacity)
        assert all(0 <= r <= 100 for r in results)


@pytest.mark.chaos
class TestRateLimiterChaos:
    """Chaos tests for rate limiter failure scenarios."""

    def test_rapid_creation_and_destruction(self) -> None:
        """Test creating and destroying many rate limiters rapidly."""
        limiters = []
        for _ in range(100):
            limiter = RateLimiter(requests_per_minute=100)
            limiter.wait_if_needed()
            limiters.append(limiter)

        # All should be valid
        for limiter in limiters:
            assert limiter.get_utilization() >= 0

        # Destroy all
        limiters.clear()

    def test_extreme_refill_rates(self) -> None:
        """Test with extreme refill rate configurations."""
        # Very slow refill
        slow = TokenBucket(capacity=10, refill_rate=0.001)
        assert slow.acquire(block=False)  # Should get one token

        # Very fast refill
        fast = TokenBucket(capacity=10, refill_rate=10000)
        for _ in range(10):
            fast.acquire(block=False)
        time.sleep(0.01)
        # Should refill quickly
        assert fast.get_available_tokens() > 0

    def test_zero_capacity_handling(self) -> None:
        """Test edge case of zero capacity bucket."""
        bucket = TokenBucket(capacity=0, refill_rate=1)

        # Should never be able to acquire
        assert not bucket.acquire(block=False)
        assert bucket.get_available_tokens() == 0
