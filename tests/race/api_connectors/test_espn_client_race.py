"""
Race Condition Tests for ESPNClient.

Tests thread safety and concurrent access patterns.

Reference: TESTING_STRATEGY V3.2 - Race condition tests for thread safety
Related Requirements: Phase 2 - Live Data Integration

Usage:
    pytest tests/race/api_connectors/test_espn_client_race.py -v -m race
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from precog.api_connectors.espn_client import ESPNClient

# =============================================================================
# Mock Helpers
# =============================================================================


def create_mock_response(data: dict) -> MagicMock:
    """Create a mock HTTP response."""
    response = MagicMock(spec=requests.Response)
    response.status_code = 200
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


def create_mock_game(event_id: str = "1") -> dict[str, Any]:
    """Create a minimal mock game for race testing."""
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
# Race Condition Tests: Concurrent Requests
# =============================================================================


@pytest.mark.race
class TestConcurrentRequests:
    """Race condition tests for concurrent request handling."""

    def test_concurrent_scoreboard_fetches(self) -> None:
        """Test multiple threads fetching scoreboards simultaneously."""
        num_threads = 10
        results: list[list[Any]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_game()]}

            client = ESPNClient(rate_limit_per_hour=10000)

            def fetch_scoreboard() -> None:
                try:
                    games = client.get_nfl_scoreboard()
                    with lock:
                        results.append(games)
                except Exception as e:
                    with lock:
                        errors.append(e)

            try:
                threads = [threading.Thread(target=fetch_scoreboard) for _ in range(num_threads)]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                assert len(errors) == 0, f"Errors occurred: {errors}"
                assert len(results) == num_threads
                for result in results:
                    assert len(result) == 1

            finally:
                client.close()

    def test_concurrent_different_leagues(self) -> None:
        """Test concurrent requests to different leagues."""
        leagues = ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"]
        results: dict[str, list[Any]] = {}
        errors: list[Exception] = []
        lock = threading.Lock()

        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_game()]}

            client = ESPNClient(rate_limit_per_hour=10000)

            def fetch_league(league: str) -> None:
                try:
                    games = client.get_scoreboard(league)
                    with lock:
                        results[league] = games
                except Exception as e:
                    with lock:
                        errors.append(e)

            try:
                threads = [
                    threading.Thread(target=fetch_league, args=(league,)) for league in leagues
                ]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                assert len(errors) == 0, f"Errors occurred: {errors}"
                assert len(results) == len(leagues)
                for league in leagues:
                    assert league in results
                    assert len(results[league]) == 1

            finally:
                client.close()

    def test_concurrent_with_thread_pool(self) -> None:
        """Test concurrent access using ThreadPoolExecutor."""
        num_requests = 20

        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_game()]}

            client = ESPNClient(rate_limit_per_hour=10000)

            try:
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [
                        executor.submit(client.get_nfl_scoreboard) for _ in range(num_requests)
                    ]

                    results = []
                    for future in as_completed(futures):
                        result = future.result()
                        results.append(result)

                assert len(results) == num_requests
                for result in results:
                    assert len(result) == 1

            finally:
                client.close()


# =============================================================================
# Race Condition Tests: Rate Limiting
# =============================================================================


@pytest.mark.race
class TestRateLimitRaceConditions:
    """Race condition tests for rate limiting under concurrent access."""

    def test_concurrent_timestamp_recording(self) -> None:
        """Test that timestamps are recorded correctly under concurrent access."""
        num_threads = 20

        client = ESPNClient(rate_limit_per_hour=10000)

        # Patch at session level so _make_request runs and records timestamps
        with patch.object(client.session, "get") as mock_get:
            mock_get.return_value = create_mock_response({"events": []})

            try:
                threads = [
                    threading.Thread(target=client.get_nfl_scoreboard) for _ in range(num_threads)
                ]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                # All timestamps should be recorded
                # Note: May have slight variation due to timing, but should be close
                assert len(client.request_timestamps) >= num_threads * 0.9

            finally:
                client.close()

    def test_concurrent_rate_limit_checking(self) -> None:
        """Test rate limit checking under concurrent access."""
        num_threads = 50
        remaining_values: list[int] = []
        lock = threading.Lock()

        client = ESPNClient(rate_limit_per_hour=500)

        try:
            # Pre-populate with some timestamps
            client.request_timestamps = [datetime.now() for _ in range(200)]

            def check_remaining() -> None:
                remaining = client.get_remaining_requests()
                with lock:
                    remaining_values.append(remaining)

            threads = [threading.Thread(target=check_remaining) for _ in range(num_threads)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(remaining_values) == num_threads
            # All values should be consistent (around 300)
            for value in remaining_values:
                assert 280 <= value <= 320, f"Unexpected remaining value: {value}"

        finally:
            client.close()

    def test_concurrent_timestamp_cleanup(self) -> None:
        """Test concurrent timestamp cleanup operations."""
        from datetime import timedelta

        num_threads = 10
        client = ESPNClient(rate_limit_per_hour=1000)

        try:
            # Add mix of old and recent timestamps
            now = datetime.now()
            old_time = now - timedelta(hours=2)

            client.request_timestamps = []
            for i in range(500):
                if i % 2 == 0:
                    client.request_timestamps.append(old_time)
                else:
                    client.request_timestamps.append(now)

            def cleanup() -> None:
                client._clean_old_timestamps()

            threads = [threading.Thread(target=cleanup) for _ in range(num_threads)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should have cleaned up old timestamps
            # Remaining should be recent ones only
            assert len(client.request_timestamps) <= 300

        finally:
            client.close()


# =============================================================================
# Race Condition Tests: Session Management
# =============================================================================


@pytest.mark.race
class TestSessionRaceConditions:
    """Race condition tests for HTTP session management."""

    def test_concurrent_session_access(self) -> None:
        """Test concurrent access to shared session."""
        num_threads = 15
        success_count = [0]
        lock = threading.Lock()

        client = ESPNClient(rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:
                mock_get.return_value = create_mock_response({"events": []})

                def make_request() -> None:
                    games = client.get_nfl_scoreboard()
                    if games is not None:
                        with lock:
                            success_count[0] += 1

                threads = [threading.Thread(target=make_request) for _ in range(num_threads)]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                assert success_count[0] == num_threads

        finally:
            client.close()

    def test_session_not_closed_during_requests(self) -> None:
        """Test that session remains valid during concurrent requests."""
        num_requests = 10
        results: list[bool] = []
        lock = threading.Lock()

        client = ESPNClient(rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:

                def delayed_response(*args: Any, **kwargs: Any) -> MagicMock:
                    time.sleep(0.01)  # Small delay
                    return create_mock_response({"events": []})

                mock_get.side_effect = delayed_response

                def make_request() -> None:
                    games = client.get_nfl_scoreboard()
                    with lock:
                        results.append(games is not None)

                threads = [threading.Thread(target=make_request) for _ in range(num_requests)]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                assert all(results), "Some requests failed unexpectedly"

        finally:
            client.close()


# =============================================================================
# Race Condition Tests: Error Handling
# =============================================================================


@pytest.mark.race
class TestErrorHandlingRaceConditions:
    """Race condition tests for error handling."""

    def test_concurrent_error_recovery(self) -> None:
        """Test error recovery under concurrent load."""
        num_threads = 10
        success_count = [0]
        error_count = [0]
        lock = threading.Lock()
        call_counter = [0]

        client = ESPNClient(max_retries=2, rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:

                def intermittent_response(*args: Any, **kwargs: Any) -> MagicMock:
                    with lock:
                        call_counter[0] += 1
                        current_call = call_counter[0]

                    # Fail every 3rd call
                    if current_call % 3 == 0:
                        raise requests.Timeout
                    return create_mock_response({"events": [create_mock_game()]})

                mock_get.side_effect = intermittent_response

                def make_request() -> None:
                    try:
                        games = client.get_nfl_scoreboard()
                        with lock:
                            if games:
                                success_count[0] += 1
                    except Exception:
                        with lock:
                            error_count[0] += 1

                threads = [threading.Thread(target=make_request) for _ in range(num_threads)]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                # Most should succeed (retries help)
                total = success_count[0] + error_count[0]
                assert total == num_threads
                assert success_count[0] > num_threads * 0.5  # At least half should succeed

        finally:
            client.close()

    def test_concurrent_different_error_types(self) -> None:
        """Test handling different error types concurrently."""
        num_threads = 12
        results: dict[str, int] = {"success": 0, "timeout": 0, "connection": 0, "other": 0}
        lock = threading.Lock()

        client = ESPNClient(max_retries=1, rate_limit_per_hour=10000)

        try:
            with patch.object(client.session, "get") as mock_get:
                error_types: list[Any] = [
                    None,  # Success
                    requests.Timeout(),
                    requests.ConnectionError(),
                ]

                call_count = [0]

                def rotating_response(*args: Any, **kwargs: Any) -> MagicMock:
                    with lock:
                        call_count[0] += 1
                        error = error_types[call_count[0] % 3]

                    if error is None:
                        return create_mock_response({"events": []})
                    raise error

                mock_get.side_effect = rotating_response

                def make_request(thread_id: int) -> None:
                    try:
                        client.get_nfl_scoreboard()
                        with lock:
                            results["success"] += 1
                    except requests.Timeout:
                        with lock:
                            results["timeout"] += 1
                    except requests.ConnectionError:
                        with lock:
                            results["connection"] += 1
                    except Exception:
                        with lock:
                            results["other"] += 1

                threads = [
                    threading.Thread(target=make_request, args=(i,)) for i in range(num_threads)
                ]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                # Verify all threads completed (including those with other exceptions)
                total = (
                    results["success"]
                    + results["timeout"]
                    + results["connection"]
                    + results["other"]
                )
                assert total == num_threads

        finally:
            client.close()


# =============================================================================
# Race Condition Tests: Client Lifecycle
# =============================================================================


@pytest.mark.race
class TestClientLifecycleRaceConditions:
    """Race condition tests for client create/close cycles."""

    def test_rapid_create_close_cycles(self) -> None:
        """Test rapid creation and closing of clients."""
        num_cycles = 20
        errors: list[Exception] = []
        lock = threading.Lock()

        def create_and_close() -> None:
            try:
                client = ESPNClient()
                time.sleep(0.001)  # Brief work
                client.close()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=create_and_close) for _ in range(num_cycles)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during create/close: {errors}"

    def test_concurrent_close_attempts(self) -> None:
        """Test multiple threads attempting to close same client."""
        num_threads = 5
        client = ESPNClient()
        errors: list[Exception] = []
        lock = threading.Lock()

        def close_client() -> None:
            try:
                client.close()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=close_client) for _ in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise errors even with multiple close attempts
        assert len(errors) == 0, f"Errors during concurrent close: {errors}"


# =============================================================================
# Race Condition Tests: Data Consistency
# =============================================================================


@pytest.mark.race
class TestDataConsistencyRaceConditions:
    """Race condition tests for data consistency under concurrent access."""

    def test_response_parsing_isolation(self) -> None:
        """Test that response parsing is isolated between threads."""
        num_threads = 10
        results: dict[int, list[Any]] = {}
        lock = threading.Lock()

        with patch.object(ESPNClient, "_make_request") as mock_request:

            def unique_response(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
                # Each call gets a unique response
                thread_id = threading.current_thread().ident
                return {"events": [create_mock_game(event_id=str(thread_id))]}

            mock_request.side_effect = unique_response

            client = ESPNClient(rate_limit_per_hour=10000)

            def fetch_and_record(thread_num: int) -> None:
                games = client.get_nfl_scoreboard()
                with lock:
                    results[thread_num] = games

            try:
                threads = [
                    threading.Thread(target=fetch_and_record, args=(i,)) for i in range(num_threads)
                ]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                assert len(results) == num_threads
                # Each thread should have gotten a response
                for i in range(num_threads):
                    assert i in results
                    assert len(results[i]) == 1

            finally:
                client.close()

    def test_no_cross_contamination(self) -> None:
        """Test that data doesn't leak between concurrent requests."""
        num_iterations = 5
        leagues = ["nfl", "nba"]
        all_results: list[tuple[str, Any]] = []
        lock = threading.Lock()

        with patch.object(ESPNClient, "_make_request") as mock_request:

            def league_specific_response(
                url: str, params: dict[str, Any] | None = None
            ) -> dict[str, Any]:
                # Return different data based on league in URL
                if "football/nfl" in url:
                    return {"events": [create_mock_game(event_id="NFL-1")]}
                if "basketball/nba" in url:
                    return {"events": [create_mock_game(event_id="NBA-1")]}
                return {"events": []}

            mock_request.side_effect = league_specific_response

            client = ESPNClient(rate_limit_per_hour=10000)

            def fetch_league(league: str) -> None:
                for _ in range(num_iterations):
                    games = client.get_scoreboard(league)
                    with lock:
                        if games:
                            # Access espn_event_id from metadata dict
                            all_results.append((league, games[0]["metadata"]["espn_event_id"]))

            try:
                threads = [
                    threading.Thread(target=fetch_league, args=(league,)) for league in leagues
                ]

                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                # Verify no cross-contamination
                for league, event_id in all_results:
                    expected_prefix = league.upper()
                    assert event_id.startswith(expected_prefix), (
                        f"Expected {expected_prefix} prefix for {league}, got {event_id}"
                    )

            finally:
                client.close()
