"""
Integration tests for ESPN API Client using VCR cassettes.

These tests use VCR (Video Cassette Recorder) to record and replay real ESPN
API responses. This provides:
1. Deterministic tests (always same response data)
2. Fast execution (no network latency after first run)
3. Testing against real API structure

VCR cassettes are stored in tests/integration/api_connectors/vcr_cassettes/

Educational Note:
    VCR records HTTP interactions on first run, then replays them on subsequent
    runs. This is ideal for:
    - Public APIs without authentication
    - Ensuring tests work against real response structures
    - CI/CD environments without network access

    To re-record cassettes: delete the YAML file and run tests again.

Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1.4
"""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import vcr

from tests.fixtures import (
    ESPN_NCAAF_SCOREBOARD_LIVE,
    ESPN_NFL_SCOREBOARD_LIVE,
)

# VCR configuration
VCR_CASSETTES_DIR = Path(__file__).parent / "vcr_cassettes"

# Determine VCR record mode based on environment
# - CI environments: "none" (playback only, no network requests)
# - Local development: "new_episodes" (record new API calls)
# This prevents CI hangs when cassettes don't match exactly
_is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
_vcr_record_mode = "none" if _is_ci else "new_episodes"

# Custom VCR instance for ESPN API
espn_vcr = vcr.VCR(
    cassette_library_dir=str(VCR_CASSETTES_DIR),
    record_mode=_vcr_record_mode,
    match_on=["uri", "method"],
    filter_headers=["User-Agent"],
)


# =============================================================================
# Mock VCR Cassette Tests (Using Fixtures Instead of Real API)
# =============================================================================
# Note: These tests use mock responses instead of real VCR cassettes
# because ESPN API may return different data each time (live games change).
# For production, you would record cassettes during known game states.


class TestESPNIntegrationWithMocks:
    """Integration tests using mock responses that simulate VCR cassettes.

    Educational Note:
        Tests now use ESPNGameFull format with metadata/state structure.
        - game["metadata"]["espn_event_id"] for static game identifier
        - game["state"]["home_score"] for dynamic score data
    """

    @patch("requests.Session.get")
    def test_fetch_nfl_scoreboard_integration(self, mock_get):
        """Integration test: Fetch and parse NFL scoreboard."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        # Simulate VCR cassette response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # Verify we got games back
        assert len(games) == 2

        # Verify first game structure (KC @ BUF) - using normalized format
        game = games[0]
        assert game["metadata"]["espn_event_id"] == "401547417"
        assert game["metadata"]["home_team"]["team_code"] == "BUF"
        assert game["metadata"]["away_team"]["team_code"] == "KC"
        assert game["state"]["home_score"] == 24
        assert game["state"]["away_score"] == 21
        assert game["state"]["period"] == 4
        assert game["state"]["game_status"] == "in_progress"

    @patch("requests.Session.get")
    def test_fetch_ncaaf_scoreboard_integration(self, mock_get):
        """Integration test: Fetch and parse NCAAF scoreboard."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        # Simulate VCR cassette response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NCAAF_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_ncaaf_scoreboard()

        # Verify we got the OSU vs Michigan game
        assert len(games) == 1
        game = games[0]
        assert game["metadata"]["espn_event_id"] == "401628501"
        home_code = game["metadata"]["home_team"]["team_code"]
        away_code = game["metadata"]["away_team"]["team_code"]
        assert "OSU" in home_code or "MICH" in away_code

    @patch("requests.Session.get")
    def test_get_live_games_filters_correctly(self, mock_get):
        """Integration test: get_live_games only returns in-progress games."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        live_games = client.get_live_games(league="nfl")

        # All games in ESPN_NFL_SCOREBOARD_LIVE are in progress
        assert len(live_games) == 2
        for game in live_games:
            assert game["state"]["game_status"] in {"in_progress", "halftime"}

    @patch("requests.Session.get")
    def test_multiple_requests_share_session(self, mock_get):
        """Integration test: Multiple requests reuse HTTP session."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()

        # Make multiple requests
        client.get_nfl_scoreboard()
        client.get_nfl_scoreboard()
        client.get_nfl_scoreboard()

        # Should have used the same session (tracked via request_timestamps)
        assert len(client.request_timestamps) == 3


# =============================================================================
# Real VCR Cassette Tests (Requires Network on First Run)
# =============================================================================
# These tests use @espn_vcr.use_cassette() decorator and will:
# 1. On first run: Make real API calls and record responses to YAML cassettes
# 2. On subsequent runs: Replay recorded responses from YAML cassettes
# Note: Tests pass in isolation and with pytest-xdist parallel execution


@pytest.mark.skipif(
    _is_ci,
    reason=(
        "VCR cassette tests hang in CI due to large YAML parsing issues. "
        "Mock-based tests (TestESPNIntegrationWithMocks) provide equivalent coverage. "
        "Run locally with 'pytest -k TestESPNRealVCRCassettes' to validate API structure."
    ),
)
class TestESPNRealVCRCassettes:
    """
    Integration tests using real VCR cassettes.

    VCR Configuration:
    - record_mode="new_episodes": Records new API calls, replays existing
    - Cassettes saved to: tests/integration/api_connectors/vcr_cassettes/

    Note: ESPN data changes constantly, so cassettes capture a
    point-in-time snapshot. Re-record when testing specific scenarios.

    CI Skip Reason (Phase 1.9 Investigation):
        These tests hang in CI after VCR cassette decorator activates but before
        the test body executes. Root cause: 347KB YAML cassette with embedded JSON
        causes issues during VCR initialization in CI environment. The pytest-timeout
        signal handler never triggers because the hang occurs during VCR setup.

        The mock-based tests (TestESPNIntegrationWithMocks) provide equivalent
        functional coverage using verified fixture data. These VCR tests remain
        available for local validation of real API structure changes.
    """

    @pytest.mark.timeout(10)  # Prevent indefinite hangs
    @espn_vcr.use_cassette("espn_nfl_scoreboard.yaml")
    def test_real_nfl_scoreboard_fetch(self):
        """Fetch real NFL scoreboard (recorded via VCR)."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # Verify we got a response
        assert isinstance(games, list)
        # Games may or may not exist depending on when cassette was recorded
        if games:
            game = games[0]
            # ESPNGameFull format: metadata/state structure
            assert "metadata" in game, "Expected ESPNGameFull format with 'metadata' key"
            assert "state" in game, "Expected ESPNGameFull format with 'state' key"
            assert "espn_event_id" in game["metadata"]
            assert "home_team" in game["metadata"]
            assert "away_team" in game["metadata"]

    @pytest.mark.timeout(10)  # Prevent indefinite hangs
    @espn_vcr.use_cassette("espn_ncaaf_scoreboard.yaml")
    def test_real_ncaaf_scoreboard_fetch(self):
        """Fetch real NCAAF scoreboard (recorded via VCR)."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        games = client.get_ncaaf_scoreboard()

        assert isinstance(games, list)
        # NCAAF may have no games depending on season
        if games:
            game = games[0]
            assert "metadata" in game
            assert "state" in game


# =============================================================================
# Integration Tests: Error Handling with Mocks
# =============================================================================


class TestESPNErrorHandlingIntegration:
    """Integration tests for error handling behavior."""

    @patch("requests.Session.get")
    def test_retry_behavior_on_server_error(self, mock_get):
        """Integration test: Verify retry behavior on 500 errors."""
        from unittest.mock import Mock

        import requests

        from precog.api_connectors.espn_client import ESPNClient

        # First two calls fail, third succeeds
        fail_response = Mock()
        fail_response.status_code = 500
        http_error = requests.HTTPError("500 Server Error")
        http_error.response = fail_response
        fail_response.raise_for_status.side_effect = http_error

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE

        mock_get.side_effect = [fail_response, fail_response, success_response]

        client = ESPNClient(max_retries=3)
        games = client.get_nfl_scoreboard()

        # Should succeed after retries
        assert len(games) == 2
        assert mock_get.call_count == 3

    @patch("requests.Session.get")
    def test_timeout_handling(self, mock_get):
        """Integration test: Verify timeout handling."""

        import requests

        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        # All calls timeout
        mock_get.side_effect = requests.Timeout("Connection timed out")

        client = ESPNClient(timeout_seconds=5, max_retries=2)

        with pytest.raises(ESPNAPIError) as exc_info:
            client.get_nfl_scoreboard()

        assert "timeout" in str(exc_info.value).lower()


# =============================================================================
# Integration Tests: Rate Limiting
# =============================================================================


class TestESPNRateLimitingIntegration:
    """Integration tests for rate limiting behavior."""

    @patch("requests.Session.get")
    def test_rate_limit_tracking_across_requests(self, mock_get):
        """Integration test: Rate limit is tracked across multiple requests."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=100)

        # Initial state
        assert client.get_remaining_requests() == 100

        # Make 5 requests
        for _ in range(5):
            client.get_nfl_scoreboard()

        # Should have 95 remaining
        assert client.get_remaining_requests() == 95

    @patch("requests.Session.get")
    def test_rate_limit_blocks_when_exceeded(self, mock_get):
        """Integration test: Rate limit blocks requests when exceeded."""
        from datetime import timedelta
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient, RateLimitExceeded

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=5)

        # Simulate 5 requests already made
        now = datetime.now()
        client.request_timestamps = [now - timedelta(minutes=i) for i in range(5)]

        # 6th request should be blocked
        with pytest.raises(RateLimitExceeded):
            client.get_nfl_scoreboard()


# =============================================================================
# Integration Tests: Data Consistency
# =============================================================================


class TestESPNDataConsistencyIntegration:
    """Integration tests for data consistency between calls.

    Educational Note:
        Tests now validate ESPNGameFull structure with metadata/state separation.
    """

    @patch("requests.Session.get")
    def test_game_data_structure_consistent(self, mock_get):
        """Integration test: All games have consistent ESPNGameFull structure."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # Top-level required fields
        top_level_fields = ["metadata", "state"]

        # Metadata required fields
        metadata_fields = ["espn_event_id", "home_team", "away_team"]

        # State required fields
        state_fields = [
            "home_score",
            "away_score",
            "period",
            "clock_seconds",
            "clock_display",
            "game_status",
        ]

        for game in games:
            event_id = game.get("metadata", {}).get("espn_event_id", "unknown")

            for field in top_level_fields:
                assert field in game, f"Missing top-level field: {field} in game {event_id}"

            for field in metadata_fields:
                assert field in game["metadata"], (
                    f"Missing metadata field: {field} in game {event_id}"
                )

            for field in state_fields:
                assert field in game["state"], f"Missing state field: {field} in game {event_id}"

    @patch("requests.Session.get")
    def test_score_types_are_integers(self, mock_get):
        """Integration test: Scores are always integers, not strings."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        for game in games:
            assert isinstance(game["state"]["home_score"], int), (
                f"home_score is {type(game['state']['home_score'])}, expected int"
            )
            assert isinstance(game["state"]["away_score"], int), (
                f"away_score is {type(game['state']['away_score'])}, expected int"
            )


# =============================================================================
# Integration Tests: API Response Variations
# =============================================================================


class TestESPNResponseVariationsIntegration:
    """Integration tests for handling various API response formats."""

    @patch("requests.Session.get")
    def test_handles_empty_events_list(self, mock_get):
        """Integration test: Handle empty events list (no games today)."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient
        from tests.fixtures import ESPN_NFL_SCOREBOARD_EMPTY

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_EMPTY
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        assert games == []

    @patch("requests.Session.get")
    def test_handles_malformed_event_gracefully(self, mock_get):
        """Integration test: Handle malformed event without crashing."""
        from unittest.mock import Mock

        from precog.api_connectors.espn_client import ESPNClient

        malformed_response = {
            "events": [
                {"id": "123"},  # Missing competitions
                ESPN_NFL_SCOREBOARD_LIVE["events"][0],  # type: ignore[index]  # Valid event
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = malformed_response
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # Should parse the valid event and skip the malformed one
        assert len(games) >= 1
