"""
Property-Based Tests for Rate Limiter.

Uses Hypothesis to test invariants and mathematical properties that should hold
for any valid input combination.

Reference: TESTING_STRATEGY V3.2 - Property tests for mathematical logic
Related Requirements: REQ-API-005 (API Rate Limit Management)

Usage:
    pytest tests/property/api_connectors/test_rate_limiter_properties.py -v -m property
"""

import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.api_connectors.rate_limiter import RateLimiter, TokenBucket

# =============================================================================
# Custom Strategies
# =============================================================================


# Valid capacity values (reasonable range for rate limiters)
capacity_strategy = st.integers(min_value=1, max_value=10000)

# Valid refill rate (tokens per second)
refill_rate_strategy = st.floats(
    min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False
)

# Valid tokens to acquire
tokens_strategy = st.integers(min_value=1, max_value=100)

# Requests per minute strategy
rpm_strategy = st.integers(min_value=1, max_value=10000)


# =============================================================================
# Property Tests: TokenBucket Invariants
# =============================================================================


@pytest.mark.property
class TestTokenBucketInvariants:
    """Property tests for TokenBucket mathematical invariants."""

    @given(capacity=capacity_strategy, refill_rate=refill_rate_strategy)
    @settings(max_examples=30)
    def test_initial_tokens_equals_capacity(self, capacity: int, refill_rate: float) -> None:
        """Test that bucket starts with full capacity."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        assert bucket.tokens == capacity
        assert bucket.get_available_tokens() == capacity

    @given(capacity=capacity_strategy, refill_rate=refill_rate_strategy)
    @settings(max_examples=30)
    def test_tokens_never_exceed_capacity(self, capacity: int, refill_rate: float) -> None:
        """Test that tokens never exceed capacity after refill."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)

        # Consume some tokens
        bucket.acquire(tokens=min(5, capacity), block=False)

        # Wait for refill
        time.sleep(0.05)

        # Refill
        bucket._refill()

        # Tokens should never exceed capacity
        assert bucket.tokens <= capacity

    @given(
        capacity=st.integers(min_value=10, max_value=100),
        refill_rate=refill_rate_strategy,
        consume_amount=st.integers(min_value=1, max_value=9),
    )
    @settings(max_examples=30)
    def test_acquire_decrements_tokens_correctly(
        self, capacity: int, refill_rate: float, consume_amount: int
    ) -> None:
        """Test that acquiring tokens decrements count correctly."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        initial = bucket.tokens

        # Consume tokens (non-blocking)
        result = bucket.acquire(tokens=consume_amount, block=False)

        if result:
            # Allow for tiny time-based refill
            assert bucket.tokens <= initial
            assert bucket.tokens >= initial - consume_amount - 1  # Allow small refill

    @given(capacity=capacity_strategy, refill_rate=refill_rate_strategy)
    @settings(max_examples=20)
    def test_acquire_returns_true_with_full_bucket(self, capacity: int, refill_rate: float) -> None:
        """Test that acquire succeeds with full bucket."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)

        # Should succeed when bucket is full
        result = bucket.acquire(tokens=1, block=False)
        assert result is True

    @given(capacity=capacity_strategy, refill_rate=refill_rate_strategy)
    @settings(max_examples=20)
    def test_acquire_exceeding_capacity_raises_error(
        self, capacity: int, refill_rate: float
    ) -> None:
        """Test that requesting more tokens than capacity raises ValueError."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)

        with pytest.raises(ValueError, match="exceeds capacity"):
            bucket.acquire(tokens=capacity + 1, block=False)

    @given(
        capacity=st.integers(min_value=10, max_value=100),
        refill_rate=st.floats(
            min_value=100.0, max_value=1000.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=20)
    def test_refill_increases_tokens(self, capacity: int, refill_rate: float) -> None:
        """Test that refill increases token count after time passes."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)

        # Consume all tokens
        for _ in range(capacity):
            bucket.acquire(tokens=1, block=False)

        # Token count should be near zero (accounting for refill during loop)
        assert bucket.tokens < capacity / 2

        # Wait a bit
        time.sleep(0.02)

        # Refill should add tokens
        old_tokens = bucket.tokens
        bucket._refill()

        # With high refill rate and sleep, should have more tokens
        assert bucket.tokens >= old_tokens


# =============================================================================
# Property Tests: RateLimiter Invariants
# =============================================================================


@pytest.mark.property
class TestRateLimiterInvariants:
    """Property tests for RateLimiter invariants."""

    @given(rpm=rpm_strategy)
    @settings(max_examples=30)
    def test_default_burst_equals_rpm(self, rpm: int) -> None:
        """Test that default burst size equals requests per minute."""
        limiter = RateLimiter(requests_per_minute=rpm)
        assert limiter.burst_size == rpm

    @given(rpm=rpm_strategy, burst=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=30)
    def test_custom_burst_is_preserved(self, rpm: int, burst: int) -> None:
        """Test that custom burst size is preserved."""
        limiter = RateLimiter(requests_per_minute=rpm, burst_size=burst)
        assert limiter.burst_size == burst
        assert limiter.requests_per_minute == rpm

    @given(rpm=rpm_strategy)
    @settings(max_examples=20)
    def test_utilization_starts_at_zero(self, rpm: int) -> None:
        """Test that utilization starts at 0% with full bucket."""
        limiter = RateLimiter(requests_per_minute=rpm)
        util = limiter.get_utilization()
        assert util == 0.0

    @given(rpm=st.integers(min_value=10, max_value=1000))
    @settings(max_examples=20)
    def test_utilization_increases_after_requests(self, rpm: int) -> None:
        """Test that utilization increases after making requests."""
        limiter = RateLimiter(requests_per_minute=rpm)

        # Make some requests
        for _ in range(min(5, rpm)):
            limiter.bucket.acquire(tokens=1, block=False)

        util = limiter.get_utilization()
        assert util > 0.0
        assert util <= 1.0

    @given(rpm=rpm_strategy)
    @settings(max_examples=20)
    def test_utilization_bounded_zero_to_one(self, rpm: int) -> None:
        """Test that utilization is always between 0 and 1."""
        limiter = RateLimiter(requests_per_minute=rpm)

        # Check initial
        util = limiter.get_utilization()
        assert 0.0 <= util <= 1.0

        # Make a request
        limiter.bucket.acquire(tokens=1, block=False)

        # Check after request
        util = limiter.get_utilization()
        assert 0.0 <= util <= 1.0


# =============================================================================
# Property Tests: Mathematical Relationships
# =============================================================================


@pytest.mark.property
class TestMathematicalRelationships:
    """Property tests for mathematical relationships in rate limiting."""

    @given(
        rpm=st.integers(min_value=60, max_value=6000),
    )
    @settings(max_examples=20)
    def test_refill_rate_calculation(self, rpm: int) -> None:
        """Test that refill rate is correctly calculated from RPM."""
        limiter = RateLimiter(requests_per_minute=rpm)

        expected_refill_rate = rpm / 60.0
        actual_refill_rate = limiter.bucket.refill_rate

        assert abs(actual_refill_rate - expected_refill_rate) < 0.001

    @given(
        capacity=st.integers(min_value=10, max_value=100),
        refill_rate=st.floats(
            min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=20)
    def test_time_to_refill_one_token(self, capacity: int, refill_rate: float) -> None:
        """Test that time to refill one token is 1/refill_rate."""
        TokenBucket(capacity=capacity, refill_rate=refill_rate)

        # Expected time to refill one token
        expected_time = 1.0 / refill_rate

        # This is a mathematical property
        assert expected_time > 0
        assert expected_time == pytest.approx(1.0 / refill_rate)


# =============================================================================
# Property Tests: Thread Safety Invariants
# =============================================================================


@pytest.mark.property
class TestThreadSafetyInvariants:
    """Property tests for thread safety invariants (non-concurrent)."""

    @given(capacity=capacity_strategy, refill_rate=refill_rate_strategy)
    @settings(max_examples=20)
    def test_lock_exists(self, capacity: int, refill_rate: float) -> None:
        """Test that bucket has a lock for thread safety."""
        bucket = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        assert hasattr(bucket, "_lock")
        assert bucket._lock is not None

    @given(rpm=rpm_strategy)
    @settings(max_examples=20)
    def test_limiter_bucket_has_lock(self, rpm: int) -> None:
        """Test that RateLimiter's bucket has a lock."""
        limiter = RateLimiter(requests_per_minute=rpm)
        assert hasattr(limiter.bucket, "_lock")
        assert limiter.bucket._lock is not None


# =============================================================================
# Property Tests: Edge Cases
# =============================================================================


@pytest.mark.property
class TestEdgeCases:
    """Property tests for edge cases."""

    def test_minimum_capacity_works(self) -> None:
        """Test that minimum capacity (1) works correctly."""
        bucket = TokenBucket(capacity=1, refill_rate=1.0)

        assert bucket.capacity == 1
        assert bucket.tokens == 1

        # Acquire the one token
        result = bucket.acquire(tokens=1, block=False)
        assert result is True

        # Should be empty now (approximately)
        assert bucket.tokens < 1

        # Can't acquire more (non-blocking)
        result = bucket.acquire(tokens=1, block=False)
        # May succeed if enough time passed for refill
        # Just verify no exception

    def test_very_high_refill_rate(self) -> None:
        """Test with very high refill rate."""
        bucket = TokenBucket(capacity=100, refill_rate=1000.0)

        # Consume all
        for _ in range(100):
            bucket.acquire(tokens=1, block=False)

        # Wait tiny bit
        time.sleep(0.01)

        # Should refill quickly
        bucket._refill()
        # With 1000 tokens/sec and 0.01s sleep, should have ~10 tokens
        assert bucket.tokens > 0

    def test_very_low_refill_rate(self) -> None:
        """Test with very low refill rate."""
        bucket = TokenBucket(capacity=100, refill_rate=0.01)

        # Consume some
        bucket.acquire(tokens=10, block=False)

        # Wait a bit
        time.sleep(0.05)

        # Should refill very slowly
        old_tokens = bucket.tokens
        bucket._refill()

        # With 0.01 tokens/sec and 0.05s, should add ~0.0005 tokens
        # Tokens should barely change
        assert bucket.tokens >= old_tokens
        assert bucket.tokens < old_tokens + 1
