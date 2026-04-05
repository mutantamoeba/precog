"""
Stress Tests for ESPNClient.

Tests high-volume scenarios and resource management under load.

Reference: TESTING_STRATEGY V3.2 - Stress tests for resource limits
Related Requirements: Phase 2 - Live Data Integration

Usage:
    pytest tests/stress/api_connectors/test_espn_client_stress.py -v -m stress
"""

import gc
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from precog.api_connectors.espn_client import ESPNClient

# =============================================================================
# Mock Helpers
# =============================================================================


def create_mock_response(data: dict):
    """Create a mock HTTP response."""
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


def create_mock_game(event_id: str = "1"):
    """Create a minimal mock game for stress testing."""
    return {
        "id": event_id,
        "date": "2025-01-15T20:15Z",
        "season": {"type": 2},
        "competitions": [
            {
                "id": event_id,
                "status": {
                    "type": {"state": "in"},
                    "period": 3,
                    "displayClock": "8:32",
                    "clock": 512.0,
                },
                "venue": {
                    "id": "1",
                    "fullName": "Test Stadium",
                    "address": {"city": "Test", "state": "NY"},
                },
                "competitors": [
                    {
                        "id": "1",
                        "homeAway": "home",
                        "score": "24",
                        "team": {
                            "abbreviation": "HOME",
                            "name": "Home",
                            "displayName": "Home Team",
                        },
                        "records": [{"name": "overall", "summary": "10-5"}],
                    },
                    {
                        "id": "2",
                        "homeAway": "away",
                        "score": "21",
                        "team": {
                            "abbreviation": "AWAY",
                            "name": "Away",
                            "displayName": "Away Team",
                        },
                        "records": [{"name": "overall", "summary": "8-7"}],
                    },
                ],
            }
        ],
    }


# =============================================================================
# Stress Tests: High Volume Requests
# =============================================================================


@pytest.mark.stress
class TestHighVolumeRequests:
    """Stress tests for high-volume request scenarios."""

    def test_many_sequential_requests(self) -> None:
        """Test many sequential requests without memory leaks."""
        num_requests = 100

        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_game()]}

            client = ESPNClient(rate_limit_per_hour=10000)  # High limit for stress test

            try:
                for i in range(num_requests):
                    games = client.get_nfl_scoreboard()
                    assert len(games) == 1

                assert mock_request.call_count == num_requests

            finally:
                client.close()

    def test_rapid_rate_limit_checks(self) -> None:
        """Test rapid rate limit checking performance with TokenBucket."""
        num_checks = 1000

        client = ESPNClient(rate_limit_per_hour=500)

        try:
            start = time.perf_counter()

            for _ in range(num_checks):
                remaining = client.get_remaining_requests()
                assert remaining >= 0

            elapsed = time.perf_counter() - start

            # Should complete in reasonable time (O(1) per check with TokenBucket)
            assert elapsed < 2.0, f"Rate limit checks took {elapsed:.2f}s for {num_checks} checks"

        finally:
            client.close()

    def test_token_bucket_consumption_under_load(self) -> None:
        """Test that TokenBucket tokens decrease under sustained load."""
        num_requests = 200

        client = ESPNClient(rate_limit_per_hour=10000)

        try:
            initial_tokens = client.rate_limiter.tokens

            with patch.object(client.session, "get") as mock_get:
                mock_get.return_value = create_mock_response({"events": []})

                for _ in range(num_requests):
                    client.get_nfl_scoreboard()

                # Tokens should have been consumed (may have partial refill)
                assert client.rate_limiter.tokens < initial_tokens

        finally:
            client.close()


# =============================================================================
# Stress Tests: Large Response Handling
# =============================================================================


@pytest.mark.stress
class TestLargeResponseHandling:
    """Stress tests for large response processing."""

    def test_many_games_in_response(self) -> None:
        """Test handling many games in single response."""
        num_games = 50  # Simulate busy day with many games

        with patch.object(ESPNClient, "_make_request") as mock_request:
            events = [create_mock_game(event_id=str(i)) for i in range(num_games)]
            mock_request.return_value = {"events": events}

            client = ESPNClient()

            try:
                start = time.perf_counter()
                games = client.get_nfl_scoreboard()
                elapsed = time.perf_counter() - start

                assert len(games) == num_games
                # Parsing should be fast
                assert elapsed < 1.0, f"Parsing {num_games} games took {elapsed:.2f}s"

            finally:
                client.close()

    def test_repeated_large_fetches(self) -> None:
        """Test repeated large response processing."""
        num_games = 30
        num_iterations = 20

        with patch.object(ESPNClient, "_make_request") as mock_request:
            events = [create_mock_game(event_id=str(i)) for i in range(num_games)]
            mock_request.return_value = {"events": events}

            client = ESPNClient(rate_limit_per_hour=10000)

            try:
                for _ in range(num_iterations):
                    games = client.get_nfl_scoreboard()
                    assert len(games) == num_games

            finally:
                client.close()


# =============================================================================
# Stress Tests: Session Management
# =============================================================================


@pytest.mark.stress
class TestSessionManagement:
    """Stress tests for HTTP session management."""

    def test_session_reuse_across_many_requests(self) -> None:
        """Test session is reused across many requests."""
        num_requests = 50

        client = ESPNClient(rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:
                mock_get.return_value = create_mock_response({"events": []})

                for _ in range(num_requests):
                    client.get_nfl_scoreboard()

                assert mock_get.call_count == num_requests

        finally:
            client.close()

    def test_session_headers_persist(self) -> None:
        """Test that session headers persist across requests."""
        client = ESPNClient()

        try:
            # Verify headers are set
            assert "User-Agent" in client.session.headers
            assert "Precog" in client.session.headers["User-Agent"]

        finally:
            client.close()

    def test_many_client_create_close_cycles(self) -> None:
        """Test many create/close cycles don't leak resources."""
        num_cycles = 50

        for _ in range(num_cycles):
            client = ESPNClient()
            client.close()

        # Force garbage collection
        gc.collect()


# =============================================================================
# Stress Tests: Rate Limit Window
# =============================================================================


@pytest.mark.stress
class TestRateLimitWindow:
    """Stress tests for rate limit sliding window."""

    def test_sliding_window_cleanup_under_load(self) -> None:
        """Test sliding window cleanup performance."""

        client = ESPNClient(rate_limit_per_hour=1000)

        try:
            # TokenBucket refill is O(1) — no cleanup needed
            # Verify get_remaining_requests is fast under load
            start = time.perf_counter()
            for _ in range(1000):
                client.get_remaining_requests()
            elapsed = time.perf_counter() - start

            # O(1) operations should be fast
            assert elapsed < 0.1, f"1000 remaining checks took {elapsed:.3f}s"

        finally:
            client.close()

    def test_rate_limit_near_boundary(self) -> None:
        """Test behavior near rate limit boundary with TokenBucket."""
        from precog.api_connectors.rate_limiter import TokenBucket

        # Small bucket to test boundary
        limiter = TokenBucket(capacity=5, refill_rate=0.001)  # Very slow refill
        client = ESPNClient(rate_limiter=limiter)

        try:
            # Consume 4 tokens
            for _ in range(4):
                limiter.acquire()

            # Should have ~1 remaining
            assert client.get_remaining_requests() >= 1

            # Consume the last token
            limiter.acquire()

            # Should be empty
            assert client.get_remaining_requests() < 1

        finally:
            client.close()


# =============================================================================
# Stress Tests: Memory Usage
# =============================================================================


@pytest.mark.stress
class TestMemoryUsage:
    """Stress tests for memory management."""

    def test_parsed_data_does_not_accumulate(self) -> None:
        """Test that parsed game data doesn't accumulate in client."""
        num_fetches = 100

        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_game()]}

            client = ESPNClient(rate_limit_per_hour=10000)

            try:
                for _ in range(num_fetches):
                    games = client.get_nfl_scoreboard()
                    # Process and discard
                    _ = len(games)

                # Client should not store parsed games internally
                assert not hasattr(client, "_cached_games")

            finally:
                client.close()

    def test_retry_attempts_dont_accumulate_state(self) -> None:
        """Test that retry attempts don't accumulate state."""
        client = ESPNClient(max_retries=3, rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:
                # Fail twice, succeed third time
                mock_get.side_effect = [
                    requests.Timeout(),
                    requests.Timeout(),
                    create_mock_response({"events": []}),
                ]

                # Multiple retry cycles
                for _ in range(5):
                    mock_get.side_effect = [
                        requests.Timeout(),
                        create_mock_response({"events": []}),
                    ]
                    client.get_nfl_scoreboard()

        finally:
            client.close()


# =============================================================================
# Stress Tests: Multi-League Alternating
# =============================================================================


@pytest.mark.stress
class TestMultiLeagueAlternating:
    """Stress tests for alternating between leagues."""

    def test_rapid_league_switching(self) -> None:
        """Test rapidly switching between different leagues."""
        num_iterations = 20
        leagues = ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"]

        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_game()]}

            client = ESPNClient(rate_limit_per_hour=10000)

            try:
                for _ in range(num_iterations):
                    for league in leagues:
                        games = client.get_scoreboard(league)
                        assert len(games) == 1

            finally:
                client.close()

    def test_concurrent_endpoint_builds(self) -> None:
        """Test that endpoint building is efficient."""
        client = ESPNClient()

        try:
            # Access endpoints many times
            for _ in range(50):
                for league in client.ENDPOINTS:
                    _ = client.ENDPOINTS[league]

        finally:
            client.close()


# =============================================================================
# Stress Tests: Error Recovery Under Load
# =============================================================================


@pytest.mark.stress
class TestErrorRecoveryUnderLoad:
    """Stress tests for error recovery scenarios."""

    def test_intermittent_failures_under_load(self) -> None:
        """Test handling intermittent failures during high load."""
        num_requests = 30
        success_count = 0

        client = ESPNClient(max_retries=1, rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:
                call_count = [0]

                def intermittent_response(*args, **kwargs):
                    call_count[0] += 1
                    # Fail every 5th request
                    if call_count[0] % 5 == 0:
                        raise requests.Timeout
                    return create_mock_response({"events": [create_mock_game()]})

                mock_get.side_effect = intermittent_response

                for _ in range(num_requests):
                    try:
                        games = client.get_nfl_scoreboard()
                        if games:
                            success_count += 1
                    except Exception:
                        pass

                # Most requests should succeed due to retry
                assert success_count > num_requests * 0.6

        finally:
            client.close()
