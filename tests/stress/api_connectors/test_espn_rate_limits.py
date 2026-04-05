"""
Stress tests for ESPN API Client rate limiting (TokenBucket).

These tests verify the TokenBucket rate limiting behavior under high-volume
scenarios, simulating production-like load patterns.

Test Categories:
1. High-volume request bursts (many requests in short time)
2. Sustained request load (consistent requests over time)
3. Rate limit recovery (bucket refill behavior)
4. Concurrent request handling (parallel requests)

Educational Note:
    The ESPNClient uses a generic TokenBucket from rate_limiter.py (C18 JC-4).
    - Token bucket allows bursts up to capacity, then throttles
    - Tokens refill at a steady rate (requests_per_hour / 3600)
    - acquire(block=False) returns False when empty (non-blocking)
    - acquire(block=True) sleeps until a token is available (blocking)

    Stress tests use block=False to avoid hanging on empty buckets.
"""

import time
from datetime import datetime, timedelta  # noqa: F401
from unittest.mock import Mock, patch

import pytest

from tests.fixtures import ESPN_NFL_SCOREBOARD_LIVE

# =============================================================================
# Stress Tests: Burst Rate Limiting
# =============================================================================


@pytest.mark.stress
class TestRateLimitingUnderBurst:
    """Stress tests for burst request scenarios with TokenBucket."""

    @patch("requests.Session.get")
    def test_burst_requests_consume_tokens(self, mock_get):
        """Stress test: Verify 100 rapid requests consume tokens from bucket."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=500)
        initial = client.get_remaining_requests()

        # Make 100 rapid requests
        for _ in range(100):
            client.get_nfl_scoreboard()

        # Tokens should have been consumed (some may refill during burst)
        remaining = client.get_remaining_requests()
        assert remaining < initial

    @patch("requests.Session.get")
    def test_burst_respects_rate_limit(self, mock_get):
        """Stress test: TokenBucket stops issuing tokens when empty."""
        from precog.api_connectors.rate_limiter import TokenBucket

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        # Small bucket, very slow refill
        limiter = TokenBucket(capacity=50, refill_rate=0.001)
        successful = 0

        # Try to acquire 100 tokens (non-blocking)
        for _ in range(100):
            if not limiter.acquire(block=False):
                break
            successful += 1

        # Should stop around capacity
        assert 49 <= successful <= 51

    @patch("requests.Session.get")
    def test_burst_performance_acceptable(self, mock_get):
        """Stress test: 100 requests complete in reasonable time (<5s)."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=500)

        start = time.perf_counter()
        for _ in range(100):
            client.get_nfl_scoreboard()
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"100 requests took {elapsed:.2f}s"


# =============================================================================
# Stress Tests: Sustained Load
# =============================================================================


@pytest.mark.stress
class TestRateLimitingUnderSustainedLoad:
    """Stress tests for sustained request patterns with TokenBucket."""

    @patch("requests.Session.get")
    def test_sustained_load_token_consumption(self, mock_get):
        """Stress test: Verify tokens consumed proportionally under sustained load."""
        from precog.api_connectors.espn_client import ESPNClient
        from precog.api_connectors.rate_limiter import TokenBucket

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        limiter = TokenBucket(capacity=100, refill_rate=0.001)  # Slow refill
        client = ESPNClient(rate_limiter=limiter)

        # Consume 80 tokens
        for _ in range(80):
            limiter.acquire()

        # Should have ~20 remaining
        remaining = client.get_remaining_requests()
        assert 15 <= remaining <= 25

        # Make 20 requests (consumes remaining tokens)
        for _ in range(20):
            client.get_nfl_scoreboard()

        # Should be near empty
        assert client.get_remaining_requests() < 5

    @patch("requests.Session.get")
    def test_token_refill_under_load(self, mock_get):
        """Stress test: Verify TokenBucket refills correctly under sustained use."""
        from precog.api_connectors.espn_client import ESPNClient
        from precog.api_connectors.rate_limiter import TokenBucket

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        # Fast refill rate for testing
        limiter = TokenBucket(capacity=500, refill_rate=500.0)
        client = ESPNClient(rate_limiter=limiter)

        # Consume some tokens
        for _ in range(10):
            client.get_nfl_scoreboard()

        # With fast refill (500/sec), tokens should be nearly full
        remaining = client.get_remaining_requests()
        assert remaining >= 480


# =============================================================================
# Stress Tests: Rate Limit Recovery
# =============================================================================


@pytest.mark.stress
class TestRateLimitRecovery:
    """Stress tests for rate limit recovery behavior."""

    def test_bucket_refills_after_drain(self):
        """Stress test: Verify bucket refills after being drained."""
        from precog.api_connectors.rate_limiter import TokenBucket

        # Fast refill for test speed
        limiter = TokenBucket(capacity=10, refill_rate=100.0)

        # Drain completely
        for _ in range(10):
            assert limiter.acquire(block=False) is True

        # Should be empty
        assert limiter.acquire(block=False) is False

        # Wait a tiny bit for refill (100 tokens/sec = 1 token per 10ms)
        time.sleep(0.05)

        # Should have refilled
        assert limiter.acquire(block=False) is True

    def test_non_blocking_acquire_never_hangs(self):
        """Stress test: Verify acquire(block=False) returns immediately even when empty."""
        from precog.api_connectors.rate_limiter import TokenBucket

        limiter = TokenBucket(capacity=1, refill_rate=0.001)
        limiter.acquire()  # Drain

        start = time.perf_counter()
        for _ in range(1000):
            limiter.acquire(block=False)
        elapsed = time.perf_counter() - start

        # 1000 non-blocking acquires should be nearly instant
        assert elapsed < 0.1, f"1000 non-blocking acquires took {elapsed:.3f}s"

    @patch("requests.Session.get")
    def test_remaining_requests_accuracy(self, mock_get):
        """Stress test: Verify get_remaining_requests tracks consumption accurately."""
        from precog.api_connectors.espn_client import ESPNClient
        from precog.api_connectors.rate_limiter import TokenBucket

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        # Slow refill so we can measure consumption precisely
        limiter = TokenBucket(capacity=500, refill_rate=0.001)
        client = ESPNClient(rate_limiter=limiter)

        before = client.get_remaining_requests()

        # Make 50 requests
        for _ in range(50):
            client.get_nfl_scoreboard()

        after = client.get_remaining_requests()

        # Should have consumed ~50 tokens (within small refill margin)
        consumed = before - after
        assert 48 <= consumed <= 52


# =============================================================================
# Stress Tests: Concurrent Access
# =============================================================================


@pytest.mark.stress
class TestConcurrentRateLimiting:
    """Stress tests for thread-safe rate limiting."""

    def test_concurrent_acquire_thread_safety(self):
        """Stress test: Verify TokenBucket is thread-safe under concurrent access."""
        import threading

        from precog.api_connectors.rate_limiter import TokenBucket

        limiter = TokenBucket(capacity=1000, refill_rate=0.001)
        acquired_count = {"value": 0}
        lock = threading.Lock()

        def acquire_tokens(n):
            count = 0
            for _ in range(n):
                if limiter.acquire(block=False):
                    count += 1
            with lock:
                acquired_count["value"] += count

        # 10 threads each trying 200 acquires (2000 total, but only 1000 tokens)
        threads = [threading.Thread(target=acquire_tokens, args=(200,)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Total acquired should not exceed capacity
        assert acquired_count["value"] <= 1001  # Allow 1 for float precision

    def test_capacity_never_exceeded(self):
        """Stress test: Verify capacity is never exceeded under rapid refill + acquire."""
        from precog.api_connectors.rate_limiter import TokenBucket

        limiter = TokenBucket(capacity=100, refill_rate=10.0)

        # Rapid acquire/check cycles
        for _ in range(500):
            limiter.acquire(block=False)
            assert limiter.tokens <= limiter.capacity + 1  # Float precision tolerance
