"""
Tests for rate limiting functionality.

Tests the token bucket algorithm and rate limiter integration.

Educational Notes:
- Mock time.time() to test time-based behavior without actual delays
- Mock time.sleep() to test waiting logic without slowing tests
- Use threading to test thread-safety
"""

import threading
from unittest.mock import patch

import pytest

from precog.api_connectors.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    """Test token bucket algorithm."""

    def test_initial_state(self):
        """Test bucket starts with full capacity."""
        bucket = TokenBucket(capacity=100, refill_rate=1.67)

        assert bucket.capacity == 100
        assert bucket.refill_rate == 1.67
        assert bucket.tokens == 100.0  # Starts full

    def test_acquire_single_token(self):
        """Test acquiring a single token."""
        bucket = TokenBucket(capacity=100, refill_rate=1.67)

        # Acquire one token
        result = bucket.acquire(tokens=1, block=False)

        assert result is True
        assert bucket.tokens == 99.0

    def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        bucket = TokenBucket(capacity=100, refill_rate=1.67)

        # Acquire 10 tokens
        result = bucket.acquire(tokens=10, block=False)

        assert result is True
        assert bucket.tokens == 90.0

    def test_acquire_fails_when_insufficient_tokens_nonblocking(self):
        """Test non-blocking acquire fails when insufficient tokens.

        Educational Note:
            Uses low refill rate (0.01 tokens/sec) to prevent timing sensitivity.
            With 1.0 tokens/sec, even 30ms delay between operations would add
            0.03 tokens, failing the 0.01 tolerance. 0.01 tokens/sec means
            even 1 second delay only adds 0.01 tokens.
        """
        # Low refill rate prevents timing sensitivity in tests
        bucket = TokenBucket(capacity=10, refill_rate=0.01)

        # Consume all tokens
        bucket.acquire(tokens=10, block=False)
        assert bucket.tokens == pytest.approx(0.0, abs=0.05)  # Allow timing tolerance

        # Try to acquire more (should fail)
        result = bucket.acquire(tokens=1, block=False)

        assert result is False
        assert bucket.tokens == pytest.approx(0.0, abs=0.05)  # Allow small refill

    def test_acquire_exceeding_capacity_raises_error(self):
        """Test requesting more tokens than capacity raises ValueError."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        with pytest.raises(ValueError, match="exceeds capacity"):
            bucket.acquire(tokens=11, block=False)

    def test_refill_adds_tokens_over_time(self):
        """Test tokens refill based on elapsed time."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)  # 10 tokens/sec

        # Consume all tokens
        bucket.acquire(tokens=100, block=False)
        assert bucket.tokens == 0.0

        # Simulate 5 seconds passing
        with patch("time.time") as mock_time:
            # Set initial time
            mock_time.return_value = bucket.last_refill

            # Advance 5 seconds
            mock_time.return_value += 5.0

            # Refill should add 50 tokens (5 sec * 10 tokens/sec)
            bucket._refill()

            assert bucket.tokens == 50.0

    def test_refill_respects_capacity_limit(self):
        """Test refill doesn't exceed capacity."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)

        # Start with 90 tokens
        bucket.tokens = 90.0

        # Simulate 10 seconds passing (should add 100 tokens, but cap at 100)
        with patch("time.time") as mock_time:
            mock_time.return_value = bucket.last_refill
            mock_time.return_value += 10.0

            bucket._refill()

            # Should be capped at capacity
            assert bucket.tokens == 100.0

    def test_blocking_acquire_waits_for_tokens(self):
        """Test blocking acquire waits until tokens available."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)  # 1 token/sec

        # Consume all tokens
        bucket.acquire(tokens=10, block=False)
        assert bucket.tokens == 0.0

        # Mock sleep to verify wait time
        with patch("time.sleep") as mock_sleep, patch("time.time") as mock_time:
            # Set initial time
            mock_time.return_value = bucket.last_refill

            # First acquire call: no tokens, should calculate wait
            # Need 1 token, refill rate 1.0 tokens/sec -> wait 1 second
            # Then on retry (after sleep), advance time and refill
            call_count = [0]

            def time_side_effect():
                call_count[0] += 1
                if call_count[0] <= 5:  # Initial refill checks
                    return bucket.last_refill
                # After sleep, time advanced
                return bucket.last_refill + 1.0

            mock_time.side_effect = time_side_effect

            result = bucket.acquire(tokens=1, block=True)

            assert result is True
            # Should have called sleep with wait time ~1 second
            assert mock_sleep.called
            wait_time = mock_sleep.call_args[0][0]
            assert 0.9 <= wait_time <= 1.1  # Allow small floating point error

    def test_get_available_tokens(self):
        """Test getting current token count."""
        bucket = TokenBucket(capacity=100, refill_rate=1.67)

        # Initial state
        available = bucket.get_available_tokens()
        assert available == pytest.approx(100.0, abs=0.01)

        # After consuming
        bucket.acquire(tokens=25, block=False)
        available = bucket.get_available_tokens()
        assert available == pytest.approx(75.0, abs=0.01)

    def test_thread_safety(self):
        """Test token bucket is thread-safe with concurrent access.

        Educational Note:
            This test verifies thread-safety by spawning 100 threads that
            all try to acquire tokens simultaneously. We use a very low
            refill rate (0.1 tokens/sec) to minimize refill during thread
            execution, making the test more deterministic across platforms.

            Windows CI with Python 3.13 showed timing sensitivity where
            higher refill rates (10 tokens/sec) caused 1.5+ tokens to refill
            during the ~0.15 seconds of thread execution, exceeding tolerance.
        """
        # Use low refill rate to prevent significant refill during thread execution
        # 0.1 tokens/sec means max ~0.05 tokens refill in 0.5 seconds of thread work
        bucket = TokenBucket(capacity=100, refill_rate=0.1)
        results = []

        def acquire_tokens():
            """Thread worker: try to acquire 1 token."""
            result = bucket.acquire(tokens=1, block=False)
            results.append(result)

        # Create 100 threads all trying to acquire at once
        threads = [threading.Thread(target=acquire_tokens) for _ in range(100)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join()

        # Should have 100 successful acquisitions (bucket had 100 tokens)
        assert sum(results) == 100
        # With refill_rate=0.1, even if threads take 0.5s, only ~0.05 tokens refill
        assert bucket.tokens == pytest.approx(0.0, abs=0.5)


class TestRateLimiter:
    """Test high-level rate limiter."""

    def test_initialization(self):
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter(requests_per_minute=100)

        assert limiter.requests_per_minute == 100
        assert limiter.burst_size == 100
        assert limiter.bucket.capacity == 100
        assert limiter.bucket.refill_rate == pytest.approx(100 / 60, rel=0.01)

    def test_initialization_with_custom_burst_size(self):
        """Test rate limiter with custom burst size."""
        limiter = RateLimiter(requests_per_minute=100, burst_size=50)

        assert limiter.requests_per_minute == 100
        assert limiter.burst_size == 50
        assert limiter.bucket.capacity == 50

    def test_wait_if_needed_acquires_token(self):
        """Test wait_if_needed() acquires token from bucket."""
        limiter = RateLimiter(requests_per_minute=100)

        initial_tokens = limiter.bucket.tokens

        limiter.wait_if_needed()

        # Should have consumed 1 token
        assert limiter.bucket.tokens == initial_tokens - 1

    def test_handle_rate_limit_error_with_retry_after(self):
        """Test handling 429 error with Retry-After header."""
        limiter = RateLimiter(requests_per_minute=100)

        with patch("time.sleep") as mock_sleep:
            limiter.handle_rate_limit_error(retry_after=30)

            # Should sleep for exact retry_after duration
            mock_sleep.assert_called_once_with(30)

    def test_handle_rate_limit_error_without_retry_after(self):
        """Test handling 429 error without Retry-After header."""
        limiter = RateLimiter(requests_per_minute=100)

        with patch("time.sleep") as mock_sleep:
            limiter.handle_rate_limit_error(retry_after=None)

            # Should sleep for default 60 seconds
            mock_sleep.assert_called_once_with(60)

    def test_get_utilization_empty_bucket(self):
        """Test utilization when bucket is full (unused)."""
        limiter = RateLimiter(requests_per_minute=100)

        utilization = limiter.get_utilization()

        # Full bucket = 0% utilized
        assert utilization == 0.0

    def test_get_utilization_half_used(self):
        """Test utilization when bucket is half empty."""
        limiter = RateLimiter(requests_per_minute=100)

        # Consume 50 tokens
        for _ in range(50):
            limiter.wait_if_needed()

        utilization = limiter.get_utilization()

        # Half empty = 50% utilized
        assert utilization == pytest.approx(0.5, rel=0.01)

    def test_get_utilization_fully_used(self):
        """Test utilization when bucket is empty."""
        limiter = RateLimiter(requests_per_minute=100)

        # Consume all 100 tokens
        for _ in range(100):
            limiter.wait_if_needed()

        utilization = limiter.get_utilization()

        # Empty bucket = 100% utilized
        assert utilization == pytest.approx(1.0, rel=0.01)

    def test_burst_behavior(self):
        """Test rate limiter allows bursts up to burst_size."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)

        # Should allow 10 requests immediately (burst)
        for i in range(10):
            limiter.wait_if_needed()  # Should not block

        # Bucket should now be empty
        assert limiter.bucket.tokens == pytest.approx(0.0, abs=0.1)

    def test_rate_limiting_over_time(self):
        """Test rate limiter enforces burst capacity limit."""
        limiter = RateLimiter(requests_per_minute=60)  # 1 req/sec, capacity=60

        request_count = 0

        # Try to make 100 requests rapidly (more than capacity)
        for _ in range(100):
            # Non-blocking: will fail when tokens exhausted
            if limiter.bucket.acquire(tokens=1, block=False):
                request_count += 1

        # Should only allow 60 requests (bucket capacity)
        assert request_count == 60

        # Bucket should be depleted
        assert limiter.bucket.tokens == pytest.approx(0.0, abs=0.1)


class TestIntegration:
    """Integration tests for rate limiter."""

    def test_rate_limiter_prevents_exceeding_limit(self):
        """Test rate limiter prevents exceeding API rate limit."""
        # Kalshi: 100 requests per minute
        limiter = RateLimiter(requests_per_minute=100)

        request_count = 0
        blocked_count = 0

        # Try to make 150 requests rapidly
        for _ in range(150):
            # Check if token available (non-blocking)
            if limiter.bucket.acquire(tokens=1, block=False):
                request_count += 1
            else:
                blocked_count += 1

        # Should have made 100 requests, blocked 50
        assert request_count == 100
        assert blocked_count == 50

    def test_rate_limiter_allows_requests_after_refill(self):
        """Test rate limiter allows requests after tokens refill."""
        limiter = RateLimiter(requests_per_minute=60)  # 1 req/sec

        # Consume all tokens
        for _ in range(60):
            limiter.wait_if_needed()

        # No tokens left
        assert limiter.bucket.acquire(tokens=1, block=False) is False

        # Simulate 10 seconds passing and make requests
        with patch("precog.api_connectors.rate_limiter.time.time") as mock_time:
            # Initial time
            start_time = limiter.bucket.last_refill
            # Return advanced time for all subsequent calls
            mock_time.return_value = start_time + 10.0

            limiter.bucket._refill()

            # Should have ~10 tokens now (10 sec * 1 token/sec)
            assert limiter.bucket.tokens == pytest.approx(10.0, abs=0.1)

            # Should be able to make 10 more requests
            # (keep patch active so refill checks use advanced time)
            for _ in range(10):
                result = limiter.bucket.acquire(tokens=1, block=False)
                assert result is True
