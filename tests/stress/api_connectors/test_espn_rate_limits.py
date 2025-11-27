"""
Stress tests for ESPN API Client rate limiting.

These tests verify the rate limiting behavior under high-volume scenarios,
simulating production-like load patterns.

Test Categories:
1. High-volume request bursts (many requests in short time)
2. Sustained request load (consistent requests over time)
3. Rate limit recovery (behavior after limit is hit)
4. Concurrent request handling (parallel requests)

Educational Note:
    Stress tests differ from unit tests:
    - Unit tests: "Does this single function work?"
    - Stress tests: "Does this work under production-like load?"

    We use mocking to avoid hitting real APIs while still testing
    the rate limiting logic at scale.

Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1.5
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from tests.fixtures import ESPN_NFL_SCOREBOARD_LIVE

# =============================================================================
# Stress Tests: High-Volume Burst Requests
# =============================================================================


class TestRateLimitingUnderBurst:
    """Stress tests for burst request scenarios."""

    @patch("requests.Session.get")
    def test_burst_requests_tracked_accurately(self, mock_get):
        """Stress test: Verify 100 rapid requests are tracked correctly."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=500)

        # Make 100 rapid requests
        for _ in range(100):
            client.get_nfl_scoreboard()

        # All should be tracked
        assert len(client.request_timestamps) == 100
        assert client.get_remaining_requests() == 400

    @patch("requests.Session.get")
    def test_burst_respects_rate_limit(self, mock_get):
        """Stress test: Verify burst stops when rate limit is reached."""
        from precog.api_connectors.espn_client import ESPNClient, RateLimitExceeded

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=50)  # Low limit for testing

        successful_requests = 0
        rate_limit_hit = False

        # Try to make 100 requests with limit of 50
        for _ in range(100):
            try:
                client.get_nfl_scoreboard()
                successful_requests += 1
            except RateLimitExceeded:
                rate_limit_hit = True
                break

        assert rate_limit_hit, "Rate limit should have been hit"
        assert successful_requests == 50, (
            f"Expected 50 successful requests, got {successful_requests}"
        )

    @patch("requests.Session.get")
    def test_burst_performance_acceptable(self, mock_get):
        """Stress test: 100 requests complete in reasonable time (<5s)."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=500)

        start_time = time.time()

        # Make 100 rapid requests
        for _ in range(100):
            client.get_nfl_scoreboard()

        elapsed = time.time() - start_time

        # Should complete in <5 seconds (mocked, so very fast)
        assert elapsed < 5.0, f"100 requests took {elapsed:.2f}s (expected <5s)"


# =============================================================================
# Stress Tests: Sustained Load
# =============================================================================


class TestRateLimitingUnderSustainedLoad:
    """Stress tests for sustained request load."""

    @patch("requests.Session.get")
    def test_sustained_load_with_mixed_timestamps(self, mock_get):
        """Stress test: Simulate sustained load with requests over time."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=100)

        # Simulate requests spread over the past hour
        now = datetime.now()
        for i in range(80):
            # Spread over 59 minutes (still within rate limit window)
            client.request_timestamps.append(now - timedelta(minutes=i % 59))

        # Should have 20 remaining
        assert client.get_remaining_requests() == 20

        # Make 20 more requests (should work)
        for _ in range(20):
            client.get_nfl_scoreboard()

        # Now at limit
        assert client.get_remaining_requests() == 0

    @patch("requests.Session.get")
    def test_timestamp_cleanup_under_load(self, mock_get):
        """Stress test: Verify old timestamps cleaned during high load."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=500)

        # Add 200 old timestamps (>1 hour ago)
        old_time = datetime.now() - timedelta(hours=2)
        client.request_timestamps = [old_time for _ in range(200)]

        # Make a new request (triggers cleanup)
        client.get_nfl_scoreboard()

        # Old timestamps should be cleaned, only 1 recent request
        assert len(client.request_timestamps) == 1
        assert client.get_remaining_requests() == 499


# =============================================================================
# Stress Tests: Rate Limit Recovery
# =============================================================================


class TestRateLimitRecovery:
    """Stress tests for rate limit recovery scenarios."""

    @patch("requests.Session.get")
    def test_recovery_after_limit_hit(self, mock_get):
        """Stress test: Verify recovery after rate limit is exhausted."""
        from precog.api_connectors.espn_client import ESPNClient, RateLimitExceeded

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=10)

        # Exhaust rate limit
        for _ in range(10):
            client.get_nfl_scoreboard()

        # Verify limit is hit
        with pytest.raises(RateLimitExceeded):
            client.get_nfl_scoreboard()

        # Simulate time passing (move timestamps to >1 hour ago)
        old_time = datetime.now() - timedelta(hours=2)
        client.request_timestamps = [old_time for _ in range(10)]

        # Should now be able to make requests again
        client.get_nfl_scoreboard()  # Should not raise
        assert client.get_remaining_requests() == 9

    @patch("requests.Session.get")
    def test_partial_recovery_with_rolling_window(self, mock_get):
        """Stress test: Verify partial recovery as timestamps age out."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=100)

        now = datetime.now()

        # 50 requests from 90 minutes ago (should be cleaned)
        old_timestamps = [now - timedelta(minutes=90) for _ in range(50)]

        # 30 requests from 30 minutes ago (still valid)
        recent_timestamps = [now - timedelta(minutes=30) for _ in range(30)]

        client.request_timestamps = old_timestamps + recent_timestamps

        # After cleanup, should have 70 remaining (100 - 30 recent)
        remaining = client.get_remaining_requests()
        assert remaining == 70, f"Expected 70 remaining, got {remaining}"


# =============================================================================
# Stress Tests: Concurrent Requests
# =============================================================================


class TestConcurrentRequests:
    """Stress tests for concurrent request handling."""

    @patch("requests.Session.get")
    def test_concurrent_requests_all_tracked(self, mock_get):
        """Stress test: Verify concurrent requests are all tracked."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=500)

        def make_request():
            return client.get_nfl_scoreboard()

        # Make 20 concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]

        # All 20 should complete
        assert len(results) == 20

        # All should be tracked (may have slight race condition tolerance)
        tracked = len(client.request_timestamps)
        assert 18 <= tracked <= 20, f"Expected ~20 tracked, got {tracked}"

    @patch("requests.Session.get")
    def test_concurrent_respects_rate_limit(self, mock_get):
        """Stress test: Verify concurrent requests respect rate limit."""
        from precog.api_connectors.espn_client import ESPNClient, RateLimitExceeded

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=10)

        successful = []
        rate_limited = []

        def make_request():
            try:
                client.get_nfl_scoreboard()
                return True
            except RateLimitExceeded:
                return False

        # Try 20 concurrent requests with limit of 10
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            for f in as_completed(futures):
                if f.result():
                    successful.append(True)
                else:
                    rate_limited.append(True)

        # Should have ~10 successful and ~10 rate limited
        # Allow some tolerance due to race conditions
        assert len(successful) <= 12, f"Too many successful: {len(successful)}"
        assert len(rate_limited) >= 8, f"Too few rate limited: {len(rate_limited)}"


# =============================================================================
# Stress Tests: Memory and Performance
# =============================================================================


class TestMemoryAndPerformance:
    """Stress tests for memory and performance under load."""

    @patch("requests.Session.get")
    def test_timestamp_list_doesnt_grow_unbounded(self, mock_get):
        """Stress test: Verify timestamp list is cleaned to prevent memory leak."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=1000)

        # Simulate long-running process with many requests
        now = datetime.now()

        # Add 1000 old timestamps (should be cleaned)
        for i in range(1000):
            client.request_timestamps.append(now - timedelta(hours=2, minutes=i % 60))

        # Make a new request (triggers cleanup)
        client.get_nfl_scoreboard()

        # Should only have 1 timestamp (old ones cleaned)
        assert len(client.request_timestamps) == 1

    @patch("requests.Session.get")
    def test_get_remaining_requests_performance(self, mock_get):
        """Stress test: get_remaining_requests is fast even with many timestamps."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(rate_limit_per_hour=500)

        # Add 500 timestamps in valid window
        now = datetime.now()
        client.request_timestamps = [now - timedelta(minutes=i % 59) for i in range(500)]

        start = time.time()

        # Call get_remaining_requests 1000 times
        for _ in range(1000):
            client.get_remaining_requests()

        elapsed = time.time() - start

        # Should complete in <1 second
        assert elapsed < 1.0, f"1000 calls took {elapsed:.3f}s (expected <1s)"
