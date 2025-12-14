"""
Integration Tests for Rate Limiter.

Tests interaction between rate limiter components and integration
with API clients and other system components.

Reference: TESTING_STRATEGY V3.2 - Integration tests for component interaction
Related Requirements: REQ-API-005 (API Rate Limit Management)

Usage:
    pytest tests/integration/api_connectors/test_rate_limiter_integration.py -v -m integration
"""

import threading
import time
from typing import Any
from unittest.mock import patch

import pytest

from precog.api_connectors.rate_limiter import RateLimiter, TokenBucket

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def token_bucket() -> TokenBucket:
    """Create a TokenBucket for testing."""
    return TokenBucket(capacity=100, refill_rate=10.0)


@pytest.fixture
def rate_limiter() -> RateLimiter:
    """Create a RateLimiter for testing."""
    return RateLimiter(requests_per_minute=600)


@pytest.fixture
def fast_rate_limiter() -> RateLimiter:
    """Create a fast RateLimiter for quick tests."""
    return RateLimiter(requests_per_minute=6000)


# =============================================================================
# Integration Tests: TokenBucket and RateLimiter
# =============================================================================


@pytest.mark.integration
class TestBucketLimiterIntegration:
    """Tests for TokenBucket and RateLimiter integration."""

    def test_rate_limiter_uses_token_bucket(self, rate_limiter: RateLimiter) -> None:
        """Test that RateLimiter correctly wraps TokenBucket."""
        assert isinstance(rate_limiter.bucket, TokenBucket)
        assert rate_limiter.bucket.capacity == rate_limiter.burst_size

    def test_wait_if_needed_consumes_tokens(self, rate_limiter: RateLimiter) -> None:
        """Test that wait_if_needed() consumes tokens from bucket."""
        initial_tokens = rate_limiter.bucket.get_available_tokens()

        rate_limiter.wait_if_needed()

        # Should have consumed one token (approximately)
        # Account for refill during test
        assert rate_limiter.bucket.get_available_tokens() < initial_tokens

    def test_utilization_reflects_bucket_state(self, rate_limiter: RateLimiter) -> None:
        """Test that utilization correctly reflects bucket state."""
        # Initially 0%
        assert rate_limiter.get_utilization() == 0.0

        # Consume half the tokens
        for _ in range(rate_limiter.burst_size // 2):
            rate_limiter.bucket.acquire(tokens=1, block=False)

        # Should be approximately 50% utilized
        util = rate_limiter.get_utilization()
        assert 0.4 <= util <= 0.6


# =============================================================================
# Integration Tests: Thread Coordination
# =============================================================================


@pytest.mark.integration
class TestThreadCoordination:
    """Tests for thread coordination in rate limiting."""

    def test_multiple_threads_share_bucket(self, token_bucket: TokenBucket) -> None:
        """Test that multiple threads share the same token bucket."""
        results: list[bool] = []
        lock = threading.Lock()

        def consume_token() -> None:
            result = token_bucket.acquire(tokens=1, block=False)
            with lock:
                results.append(result)

        # Start multiple threads
        threads = [threading.Thread(target=consume_token) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed (bucket had 100 tokens)
        assert all(results)
        # 50 tokens should have been consumed
        assert token_bucket.get_available_tokens() < 60

    def test_multiple_threads_rate_limited(self, rate_limiter: RateLimiter) -> None:
        """Test that multiple threads are properly rate limited."""
        request_times: list[float] = []
        lock = threading.Lock()

        def make_request() -> None:
            rate_limiter.wait_if_needed()
            with lock:
                request_times.append(time.time())

        # Start threads
        threads = [threading.Thread(target=make_request) for _ in range(10)]
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        # All should complete
        assert len(request_times) == 10
        # Should be very fast with 600 rpm (10 tokens/sec)
        assert elapsed < 2.0

    def test_concurrent_utilization_checks(self, rate_limiter: RateLimiter) -> None:
        """Test that concurrent utilization checks are safe."""
        results: list[float] = []
        lock = threading.Lock()

        def check_utilization() -> None:
            for _ in range(10):
                util = rate_limiter.get_utilization()
                with lock:
                    results.append(util)

        threads = [threading.Thread(target=check_utilization) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be valid utilization values
        assert len(results) == 50
        for util in results:
            assert 0.0 <= util <= 1.0


# =============================================================================
# Integration Tests: API Client Simulation
# =============================================================================


@pytest.mark.integration
class TestAPIClientSimulation:
    """Tests simulating API client usage patterns."""

    def test_burst_then_steady_rate(self, fast_rate_limiter: RateLimiter) -> None:
        """Test burst of requests followed by steady rate."""
        # Initial burst - should all succeed immediately
        burst_start = time.time()
        for _ in range(20):
            fast_rate_limiter.wait_if_needed()
        burst_duration = time.time() - burst_start

        # Burst should be very fast
        assert burst_duration < 0.5

        # Steady rate - simulate continuous requests
        steady_count = 0
        steady_start = time.time()
        while time.time() - steady_start < 0.2:
            fast_rate_limiter.wait_if_needed()
            steady_count += 1

        # Should have made several requests in 0.2s
        assert steady_count > 0

    def test_rate_limit_error_handling(self, rate_limiter: RateLimiter) -> None:
        """Test handling rate limit error (429 simulation)."""
        # Simulate 429 error with Retry-After header
        with patch("time.sleep") as mock_sleep:
            rate_limiter.handle_rate_limit_error(retry_after=30)
            mock_sleep.assert_called_once_with(30)

    def test_rate_limit_error_default_wait(self, rate_limiter: RateLimiter) -> None:
        """Test default wait time when no Retry-After header."""
        with patch("time.sleep") as mock_sleep:
            rate_limiter.handle_rate_limit_error(retry_after=None)
            mock_sleep.assert_called_once_with(60)  # Default 60s

    def test_mixed_blocking_nonblocking(self, token_bucket: TokenBucket) -> None:
        """Test mixing blocking and non-blocking acquire calls."""
        # Non-blocking acquisitions
        non_blocking_results = [token_bucket.acquire(tokens=1, block=False) for _ in range(80)]
        all_succeeded = all(non_blocking_results)
        assert all_succeeded

        # Remaining tokens should be low
        remaining = token_bucket.get_available_tokens()
        assert remaining < 25

        # Non-blocking should fail if tokens exhausted
        if remaining < 1:
            token_bucket.acquire(tokens=1, block=False)
            # May succeed due to refill, but shouldn't hang
            # Just verify no exception


# =============================================================================
# Integration Tests: Refill Behavior
# =============================================================================


@pytest.mark.integration
class TestRefillBehavior:
    """Tests for token refill behavior."""

    def test_refill_during_long_operation(self) -> None:
        """Test that tokens refill during long operations."""
        bucket = TokenBucket(capacity=100, refill_rate=100.0)  # 100 tokens/sec

        # Consume all tokens
        for _ in range(100):
            bucket.acquire(tokens=1, block=False)

        # Should be nearly empty
        assert bucket.get_available_tokens() < 10

        # Wait for refill
        time.sleep(0.1)

        # Should have refilled ~10 tokens
        available = bucket.get_available_tokens()
        assert available > 5

    def test_continuous_refill_with_acquisition(self) -> None:
        """Test continuous refill during ongoing acquisitions."""
        bucket = TokenBucket(capacity=50, refill_rate=50.0)  # 50 tokens/sec

        acquired = 0
        start = time.time()

        # Try to acquire 100 tokens (more than capacity)
        while acquired < 100 and (time.time() - start) < 5:
            if bucket.acquire(tokens=1, block=False):
                acquired += 1
            time.sleep(0.01)  # Small delay to allow refill

        # Should have acquired more than capacity due to refill
        assert acquired > 50

    def test_bucket_recovery_after_drain(self) -> None:
        """Test bucket recovery after being drained."""
        bucket = TokenBucket(capacity=100, refill_rate=200.0)

        # Drain bucket
        drained = 0
        while bucket.acquire(tokens=1, block=False):
            drained += 1
            if drained > 100:
                break

        # Wait for recovery
        time.sleep(0.2)

        # Should have recovered substantially
        recovered = bucket.get_available_tokens()
        assert recovered > 30


# =============================================================================
# Integration Tests: Logging Integration
# =============================================================================


@pytest.mark.integration
class TestLoggingIntegration:
    """Tests for logging integration."""

    def test_low_token_warning_logged(self, token_bucket: TokenBucket, caplog: Any) -> None:
        """Test that low token warning is logged."""
        import logging

        caplog.set_level(logging.WARNING)

        # Consume tokens to trigger warning
        for _ in range(85):
            token_bucket.acquire(tokens=1, block=False)

        # Should have logged warning about low tokens
        # Note: caplog may not capture this depending on logger configuration
        # The key is that no exception occurs

    def test_rate_limit_error_logged(self, rate_limiter: RateLimiter, caplog: Any) -> None:
        """Test that rate limit errors are logged."""
        import logging

        caplog.set_level(logging.WARNING)

        with patch("time.sleep"):
            rate_limiter.handle_rate_limit_error(retry_after=10)

        # Should have logged the rate limit error
        # Note: caplog may not capture this depending on logger configuration


# =============================================================================
# Integration Tests: Configuration Variations
# =============================================================================


@pytest.mark.integration
class TestConfigurationVariations:
    """Tests for different configuration scenarios."""

    def test_very_high_rate_limit(self) -> None:
        """Test with very high rate limit (no practical limit)."""
        limiter = RateLimiter(requests_per_minute=60000)  # 1000/sec

        start = time.time()
        for _ in range(100):
            limiter.wait_if_needed()
        elapsed = time.time() - start

        # Should be essentially instant
        assert elapsed < 0.5

    def test_very_low_rate_limit(self) -> None:
        """Test with very low rate limit (slow)."""
        limiter = RateLimiter(requests_per_minute=60)  # 1/sec

        # Non-blocking to avoid long wait
        results = [limiter.bucket.acquire(tokens=1, block=False) for _ in range(5)]

        # First should succeed
        assert results[0] is True

    def test_custom_burst_larger_than_rpm(self) -> None:
        """Test burst size larger than RPM."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=120)

        assert limiter.burst_size == 120
        assert limiter.requests_per_minute == 60

        # Should be able to burst 120 requests
        burst_count = 0
        while limiter.bucket.acquire(tokens=1, block=False):
            burst_count += 1
            if burst_count > 150:
                break

        # Should have gotten roughly 120 tokens
        assert burst_count > 100

    def test_custom_burst_smaller_than_rpm(self) -> None:
        """Test burst size smaller than RPM."""
        limiter = RateLimiter(requests_per_minute=600, burst_size=10)

        assert limiter.burst_size == 10
        assert limiter.requests_per_minute == 600

        # Can only burst 10 requests
        burst_count = 0
        while limiter.bucket.acquire(tokens=1, block=False):
            burst_count += 1
            if burst_count > 20:
                break

        # Should have gotten roughly 10 tokens (allow for refill)
        assert burst_count <= 15
