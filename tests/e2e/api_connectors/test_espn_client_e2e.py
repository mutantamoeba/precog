"""
End-to-End Tests for ESPNClient.

Tests complete workflows including multi-sport fetching, rate limiting,
error recovery, and full data parsing pipelines.

Reference: TESTING_STRATEGY V3.2 - E2E tests for critical workflows
Related Requirements: Phase 2 - Live Data Integration

Usage:
    pytest tests/e2e/api_connectors/test_espn_client_e2e.py -v -m e2e
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from precog.api_connectors.espn_client import (
    ESPNAPIError,
    ESPNClient,
    RateLimitExceeded,
)

# =============================================================================
# Mock Response Helpers
# =============================================================================


def create_mock_response(data: dict, status_code: int = 200):
    """Create a mock HTTP response."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        http_error = requests.HTTPError()
        http_error.response = response
        response.raise_for_status.side_effect = http_error
    return response


def create_mock_nfl_game(
    event_id: str = "401547417",
    home_team: str = "BUF",
    away_team: str = "KC",
    home_score: int = 24,
    away_score: int = 21,
    status_state: str = "in",
    period: int = 3,
    clock: str = "8:32",
):
    """Create a mock NFL game event."""
    return {
        "id": event_id,
        "date": "2025-01-15T20:15Z",
        "name": f"{away_team} at {home_team}",
        "season": {"type": 2},
        "week": {"number": 18},
        "competitions": [
            {
                "id": event_id,
                "status": {
                    "type": {"state": status_state, "name": "STATUS_IN_PROGRESS"},
                    "period": period,
                    "displayClock": clock,
                    "clock": 512.0,
                },
                "venue": {
                    "id": "3883",
                    "fullName": "Highmark Stadium",
                    "address": {"city": "Orchard Park", "state": "NY"},
                    "capacity": 71608,
                    "indoor": False,
                },
                "broadcasts": [{"names": ["CBS"]}],
                "neutralSite": False,
                "situation": {
                    "down": 2,
                    "distance": 7,
                    "yardLine": 35,
                    "possession": "21",
                    "isRedZone": False,
                },
                "competitors": [
                    {
                        "id": "21",
                        "homeAway": "home",
                        "score": str(home_score),
                        "team": {
                            "abbreviation": home_team,
                            "name": "Bills",
                            "displayName": "Buffalo Bills",
                        },
                        "records": [
                            {"name": "overall", "summary": "12-5"},
                            {"name": "home", "summary": "7-2"},
                            {"name": "away", "summary": "5-3"},
                        ],
                        "linescores": [{"value": 7}, {"value": 10}, {"value": 7}],
                    },
                    {
                        "id": "22",
                        "homeAway": "away",
                        "score": str(away_score),
                        "team": {
                            "abbreviation": away_team,
                            "name": "Chiefs",
                            "displayName": "Kansas City Chiefs",
                        },
                        "records": [
                            {"name": "overall", "summary": "14-3"},
                            {"name": "home", "summary": "8-1"},
                            {"name": "away", "summary": "6-2"},
                        ],
                        "linescores": [{"value": 7}, {"value": 7}, {"value": 7}],
                    },
                ],
            }
        ],
    }


# =============================================================================
# E2E Tests: Complete Client Lifecycle
# =============================================================================


@pytest.mark.e2e
class TestClientLifecycle:
    """E2E tests for complete client lifecycle."""

    def test_initialize_fetch_close_lifecycle(self) -> None:
        """Test complete client lifecycle from init to close."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game()]}

            # Initialize
            client = ESPNClient(rate_limit_per_hour=100)

            try:
                # Fetch data
                games = client.get_nfl_scoreboard()
                assert len(games) == 1

                # Verify data structure
                game = games[0]
                assert "metadata" in game
                assert "state" in game
                assert game["metadata"]["home_team"]["team_code"] == "BUF"
                assert game["state"]["home_score"] == 24

            finally:
                # Close session
                client.close()

    def test_multiple_leagues_same_session(self) -> None:
        """Test fetching multiple leagues with same client."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game()]}

            client = ESPNClient()

            try:
                # Fetch multiple leagues
                nfl_games = client.get_nfl_scoreboard()
                ncaaf_games = client.get_ncaaf_scoreboard()
                nba_games = client.get_nba_scoreboard()

                # All should succeed
                assert len(nfl_games) == 1
                assert len(ncaaf_games) == 1
                assert len(nba_games) == 1

            finally:
                client.close()


# =============================================================================
# E2E Tests: Multi-Sport Fetching
# =============================================================================


@pytest.mark.e2e
class TestMultiSportFetching:
    """E2E tests for multi-sport data fetching."""

    def test_all_supported_leagues(self) -> None:
        """Test fetching all supported leagues."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game()]}

            client = ESPNClient()

            try:
                leagues = ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"]

                for league in leagues:
                    games = client.get_scoreboard(league)
                    assert isinstance(games, list)

            finally:
                client.close()

    def test_invalid_league_raises_error(self) -> None:
        """Test that invalid league raises ValueError."""
        client = ESPNClient()

        try:
            with pytest.raises(ValueError) as exc_info:
                client.get_scoreboard("invalid_league")

            assert "Unsupported league" in str(exc_info.value)

        finally:
            client.close()

    def test_live_games_filtering(self) -> None:
        """Test filtering to only live games."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            # Mix of game statuses
            events = [
                create_mock_nfl_game(event_id="1", status_state="pre"),  # Scheduled
                create_mock_nfl_game(event_id="2", status_state="in"),  # Live
                create_mock_nfl_game(event_id="3", status_state="post"),  # Final
            ]
            mock_request.return_value = {"events": events}

            client = ESPNClient()

            try:
                live_games = client.get_live_games("nfl")

                # Only "in" status game should be returned
                assert len(live_games) == 1
                assert live_games[0]["state"]["game_status"] == "in_progress"

            finally:
                client.close()


# =============================================================================
# E2E Tests: Rate Limiting Workflow
# =============================================================================


@pytest.mark.e2e
class TestRateLimitingWorkflow:
    """E2E tests for rate limiting behavior."""

    def test_rate_limit_tracking(self) -> None:
        """Test rate limit tracking across requests."""
        client = ESPNClient(rate_limit_per_hour=10)

        try:
            # Patch at session level so _make_request still runs and tracks timestamps
            with patch.object(client.session, "get") as mock_get:
                mock_get.return_value = create_mock_response({"events": []})

                initial_remaining = client.get_remaining_requests()
                assert initial_remaining == 10

                # Make requests and track remaining
                for _ in range(3):
                    client.get_nfl_scoreboard()

                remaining_after = client.get_remaining_requests()
                assert remaining_after == 7

        finally:
            client.close()

    def test_rate_limit_exceeded_raises_error(self) -> None:
        """Test that exceeding rate limit raises error."""
        client = ESPNClient(rate_limit_per_hour=2)

        try:
            # Fill rate limit
            client.request_timestamps = [
                datetime.now(),
                datetime.now(),
            ]

            with pytest.raises(RateLimitExceeded) as exc_info:
                client._check_rate_limit()

            assert "Rate limit exceeded" in str(exc_info.value)

        finally:
            client.close()

    def test_rate_limit_resets_after_hour(self) -> None:
        """Test that rate limit resets after old timestamps expire."""
        client = ESPNClient(rate_limit_per_hour=5)

        try:
            # Add old timestamps (older than 1 hour)
            old_time = datetime.now() - timedelta(hours=2)
            client.request_timestamps = [old_time] * 5

            # Should reset after cleanup
            remaining = client.get_remaining_requests()
            assert remaining == 5

        finally:
            client.close()


# =============================================================================
# E2E Tests: Error Recovery Workflow
# =============================================================================


@pytest.mark.e2e
class TestErrorRecoveryWorkflow:
    """E2E tests for error handling and recovery."""

    def test_retry_on_timeout(self) -> None:
        """Test retry behavior on timeout."""
        client = ESPNClient(max_retries=2, timeout_seconds=1)

        try:
            with patch.object(client.session, "get") as mock_get:
                # First two timeout, third succeeds
                mock_get.side_effect = [
                    requests.Timeout(),
                    requests.Timeout(),
                    create_mock_response({"events": [create_mock_nfl_game()]}),
                ]

                games = client.get_nfl_scoreboard()
                assert len(games) == 1
                assert mock_get.call_count == 3

        finally:
            client.close()

    def test_retry_on_connection_error(self) -> None:
        """Test retry behavior on connection error."""
        client = ESPNClient(max_retries=1)

        try:
            with patch.object(client.session, "get") as mock_get:
                # First fails, second succeeds
                mock_get.side_effect = [
                    requests.ConnectionError(),
                    create_mock_response({"events": []}),
                ]

                games = client.get_nfl_scoreboard()
                assert len(games) == 0
                assert mock_get.call_count == 2

        finally:
            client.close()

    def test_no_retry_on_4xx_error(self) -> None:
        """Test that 4xx errors don't trigger retry."""
        client = ESPNClient(max_retries=3)

        try:
            with patch.object(client.session, "get") as mock_get:
                mock_get.return_value = create_mock_response({}, status_code=404)

                with pytest.raises(ESPNAPIError):
                    client.get_nfl_scoreboard()

                # Should only try once
                assert mock_get.call_count == 1

        finally:
            client.close()

    def test_retries_exhausted_raises_error(self) -> None:
        """Test that exhausted retries raise error."""
        client = ESPNClient(max_retries=2)

        try:
            with patch.object(client.session, "get") as mock_get:
                mock_get.side_effect = requests.Timeout()

                with pytest.raises(ESPNAPIError) as exc_info:
                    client.get_nfl_scoreboard()

                assert "timeout" in str(exc_info.value).lower()
                assert mock_get.call_count == 3  # Initial + 2 retries

        finally:
            client.close()


# =============================================================================
# E2E Tests: Data Parsing Pipeline
# =============================================================================


@pytest.mark.e2e
class TestDataParsingPipeline:
    """E2E tests for complete data parsing pipeline."""

    def test_full_game_data_extraction(self) -> None:
        """Test complete game data extraction pipeline."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game()]}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()
                game = games[0]

                # Verify metadata structure
                metadata = game["metadata"]
                assert metadata["espn_event_id"] == "401547417"
                assert metadata["home_team"]["team_code"] == "BUF"
                assert metadata["away_team"]["team_code"] == "KC"
                assert metadata["venue"]["venue_name"] == "Highmark Stadium"

                # Verify state structure
                state = game["state"]
                assert state["home_score"] == 24
                assert state["away_score"] == 21
                assert state["period"] == 3
                assert state["game_status"] == "in_progress"

                # Verify situation
                situation = state["situation"]
                assert situation["down"] == 2
                assert situation["distance"] == 7

            finally:
                client.close()

    def test_multiple_games_parsing(self) -> None:
        """Test parsing multiple games from response."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            events = [
                create_mock_nfl_game(event_id="1", home_team="BUF", away_team="KC"),
                create_mock_nfl_game(event_id="2", home_team="DEN", away_team="MIA"),
                create_mock_nfl_game(event_id="3", home_team="SF", away_team="DAL"),
            ]
            mock_request.return_value = {"events": events}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()

                assert len(games) == 3
                event_ids = [g["metadata"]["espn_event_id"] for g in games]
                assert event_ids == ["1", "2", "3"]

            finally:
                client.close()

    def test_empty_scoreboard(self) -> None:
        """Test handling empty scoreboard response."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": []}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()
                assert games == []

            finally:
                client.close()

    def test_linescores_parsing(self) -> None:
        """Test quarter-by-quarter linescore parsing."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game()]}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()
                linescores = games[0]["state"]["linescores"]

                # Should have 3 quarters worth of linescores
                assert len(linescores) == 3
                # Each entry is [home_q, away_q]
                assert linescores[0] == [7, 7]  # Q1
                assert linescores[1] == [10, 7]  # Q2

            finally:
                client.close()


# =============================================================================
# E2E Tests: Date Parameter Handling
# =============================================================================


@pytest.mark.e2e
class TestDateParameterHandling:
    """E2E tests for date parameter handling."""

    def test_fetch_specific_date(self) -> None:
        """Test fetching scoreboard for specific date."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game()]}

            client = ESPNClient()

            try:
                specific_date = datetime(2025, 1, 15)
                client.get_nfl_scoreboard(date=specific_date)

                # Verify date was passed correctly
                call_args = mock_request.call_args
                assert "20250115" in str(call_args)

            finally:
                client.close()

    def test_fetch_without_date_uses_today(self) -> None:
        """Test fetching without date parameter."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": []}

            client = ESPNClient()

            try:
                client.get_nfl_scoreboard()

                # Should be called without date parameter
                mock_request.assert_called_once()

            finally:
                client.close()


# =============================================================================
# E2E Tests: Status Mapping
# =============================================================================


@pytest.mark.e2e
class TestStatusMapping:
    """E2E tests for game status mapping."""

    def test_status_pre_maps_correctly(self) -> None:
        """Test 'pre' status maps to 'pre'."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game(status_state="pre")]}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()
                assert games[0]["state"]["game_status"] == "pre"

            finally:
                client.close()

    def test_status_in_maps_correctly(self) -> None:
        """Test 'in' status maps to 'in_progress'."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game(status_state="in")]}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()
                assert games[0]["state"]["game_status"] == "in_progress"

            finally:
                client.close()

    def test_status_post_maps_correctly(self) -> None:
        """Test 'post' status maps to 'final'."""
        with patch.object(ESPNClient, "_make_request") as mock_request:
            mock_request.return_value = {"events": [create_mock_nfl_game(status_state="post")]}

            client = ESPNClient()

            try:
                games = client.get_nfl_scoreboard()
                assert games[0]["state"]["game_status"] == "final"

            finally:
                client.close()
