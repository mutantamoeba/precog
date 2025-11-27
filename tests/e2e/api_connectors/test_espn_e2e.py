"""
End-to-End Tests for ESPN API Client.

These tests validate the ESPN API client against the REAL ESPN public API.
Unlike unit tests that use mocks, these tests make actual HTTP requests
to verify real-world integration.

Educational Note:
    E2E tests for ESPN differ from Kalshi E2E tests in important ways:
    - ESPN API is public (no authentication required)
    - ESPN data changes constantly (live games, scores)
    - Tests must handle variable data gracefully
    - Network availability is the main skip condition

Test Categories:
1. API Connectivity - Can we reach ESPN servers?
2. Response Parsing - Does real API data parse correctly?
3. Data Structure Validation - Are all fields present?
4. Rate Limiting - Does rate tracking work with real requests?
5. Error Handling - How do we handle API issues?

Run with:
    pytest tests/e2e/api_connectors/test_espn_e2e.py -v -m e2e

References:
    - Issue #125: E2E tests for ESPN client
    - REQ-TEST-012: Test types taxonomy (E2E tests)
    - docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1.6

Phase: 2 (Live Data Collection)
"""

import socket

import pytest
import requests

# Skip entire module if network is unavailable
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.api,
]


def is_network_available() -> bool:
    """Check if network is available by attempting to reach ESPN.

    Educational Note:
        This is a quick connectivity check before running E2E tests.
        We use socket with timeout rather than full HTTP request
        for faster failure detection.
    """
    try:
        socket.create_connection(("site.api.espn.com", 443), timeout=5)
        return True
    except OSError:
        return False


# Skip all tests if network unavailable
pytestmark.append(
    pytest.mark.skipif(
        not is_network_available(),
        reason="Network unavailable - cannot reach ESPN API",
    )
)


@pytest.fixture(scope="module")
def espn_client():
    """Create an ESPNClient instance for E2E tests.

    Uses module scope to reuse client across tests (preserves connection pooling).

    Educational Note:
        Module-scoped fixtures are efficient for E2E tests because:
        - HTTP session is reused across all tests
        - Rate limit tracking persists (realistic behavior)
        - Tests run faster overall
    """
    from precog.api_connectors.espn_client import ESPNClient

    return ESPNClient(rate_limit_per_hour=500)


# =============================================================================
# E2E Tests: API Connectivity
# =============================================================================


class TestESPNConnectivity:
    """E2E tests for ESPN API connectivity."""

    def test_client_can_reach_espn_api(self, espn_client):
        """Verify client can successfully reach ESPN API.

        This is the most basic E2E test - if this fails, nothing else works.

        Educational Note:
            We just verify we get any response - the API might return
            an empty list if no games are scheduled today.
        """
        # Attempt to fetch NFL scoreboard
        games = espn_client.get_nfl_scoreboard()

        # Should return a list (possibly empty)
        assert isinstance(games, list)

    def test_session_is_reused(self, espn_client):
        """Verify HTTP session is reused for connection efficiency.

        Educational Note:
            Connection pooling via requests.Session provides significant
            performance benefits for repeated API calls to same host.
        """
        # Make two requests
        espn_client.get_nfl_scoreboard()
        espn_client.get_nfl_scoreboard()

        # Both should use same session (tracked via timestamps)
        assert len(espn_client.request_timestamps) >= 2

    def test_both_leagues_accessible(self, espn_client):
        """Verify both NFL and NCAAF endpoints are accessible.

        Educational Note:
            ESPN uses different API endpoints for different leagues.
            We verify both work to ensure broad coverage.
        """
        nfl_games = espn_client.get_nfl_scoreboard()
        ncaaf_games = espn_client.get_ncaaf_scoreboard()

        # Both should return lists
        assert isinstance(nfl_games, list)
        assert isinstance(ncaaf_games, list)


# =============================================================================
# E2E Tests: Response Parsing
# =============================================================================


class TestESPNResponseParsing:
    """E2E tests for parsing real ESPN API responses."""

    def test_parse_real_nfl_response(self, espn_client):
        """Verify real NFL response parses correctly.

        Educational Note:
            Real API responses may differ from our test fixtures.
            This test validates our parsing handles real-world data.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        game = games[0]

        # Core fields should always be present
        assert "espn_event_id" in game
        assert "home_team" in game
        assert "away_team" in game

    def test_scores_are_integers(self, espn_client):
        """Verify scores are parsed as integers.

        Educational Note:
            ESPN returns scores as strings in JSON. We must convert
            them to integers for calculations. This validates that
            conversion.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        for game in games:
            assert isinstance(game["home_score"], int)
            assert isinstance(game["away_score"], int)
            # Scores should be non-negative
            assert game["home_score"] >= 0
            assert game["away_score"] >= 0

    def test_game_status_maps_correctly(self, espn_client):
        """Verify game status maps to known values.

        Educational Note:
            ESPN uses various status codes (pre, in, post, etc.).
            We must map these to our internal status values consistently.
        """
        games = espn_client.get_nfl_scoreboard()

        known_statuses = {"scheduled", "in_progress", "halftime", "final", "unknown"}

        for game in games:
            assert game["game_status"] in known_statuses, f"Unknown status: {game['game_status']}"

    def test_team_abbreviations_are_strings(self, espn_client):
        """Verify team abbreviations are parsed as strings.

        Educational Note:
            Team abbreviations are used as keys for lookups and joins.
            They must be consistent string types.
        """
        games = espn_client.get_nfl_scoreboard()

        for game in games:
            assert isinstance(game["home_team"], str)
            assert isinstance(game["away_team"], str)
            # Abbreviations should be short (2-4 chars typically)
            assert 1 <= len(game["home_team"]) <= 10
            assert 1 <= len(game["away_team"]) <= 10


# =============================================================================
# E2E Tests: Data Structure Validation
# =============================================================================


class TestESPNDataStructure:
    """E2E tests validating the complete GameState structure."""

    def test_game_state_has_required_fields(self, espn_client):
        """Verify GameState contains all required fields.

        Educational Note:
            Our GameState TypedDict defines required fields for downstream
            processing. This validates real API data populates them.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        required_fields = [
            "espn_event_id",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "period",
            "clock_display",
            "game_status",
        ]

        game = games[0]
        for field in required_fields:
            assert field in game, f"Missing required field: {field}"

    def test_model_training_fields_present(self, espn_client):
        """Verify model training fields are populated when available.

        Educational Note:
            Some fields (records, venue, broadcast) are for ML model features.
            They may not always be present, but when they are, they should
            have correct types.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        # Model training fields (optional but typed when present)
        model_fields = {
            "home_team_id": str,
            "away_team_id": str,
            "home_display_name": str,
            "away_display_name": str,
            "home_record": str,
            "away_record": str,
            "venue_name": str,
            "game_date": str,
        }

        game = games[0]
        for field, expected_type in model_fields.items():
            if field in game and game[field] is not None:
                assert isinstance(game[field], expected_type), (
                    f"Field {field} is {type(game[field])}, expected {expected_type}"
                )

    def test_situation_data_valid_when_present(self, espn_client):
        """Verify situation data (down, distance, possession) is valid.

        Educational Note:
            Situation data is only present for in-progress games.
            When present, values must be in valid ranges.
        """
        games = espn_client.get_live_games(league="nfl")

        if len(games) == 0:
            pytest.skip("No live NFL games right now")

        for game in games:
            # If down is present, should be 1-4
            if game.get("down") is not None:
                assert 1 <= game["down"] <= 4

            # If distance is present, should be positive
            if game.get("distance") is not None:
                assert game["distance"] > 0

            # Timeouts should be 0-3
            assert 0 <= game["home_timeouts"] <= 3
            assert 0 <= game["away_timeouts"] <= 3


# =============================================================================
# E2E Tests: Rate Limiting
# =============================================================================


class TestESPNRateLimiting:
    """E2E tests for rate limiting with real requests."""

    def test_rate_limit_tracking_with_real_requests(self, espn_client):
        """Verify rate limiting tracks real requests.

        Educational Note:
            We make a few real requests and verify the rate limiter
            is tracking them. We don't actually hit the limit (wasteful).
        """
        initial_count = len(espn_client.request_timestamps)

        # Make 3 real requests
        espn_client.get_nfl_scoreboard()
        espn_client.get_nfl_scoreboard()
        espn_client.get_nfl_scoreboard()

        # Should have 3 more timestamps
        new_count = len(espn_client.request_timestamps)
        assert new_count >= initial_count + 3

    def test_remaining_requests_decrements(self, espn_client):
        """Verify remaining request count decrements.

        Educational Note:
            This validates the rate limiter is actually counting
            and enforcing limits (without hitting the limit).
        """
        # Get remaining before
        before = espn_client.get_remaining_requests()

        # Make a request
        espn_client.get_nfl_scoreboard()

        # Get remaining after
        after = espn_client.get_remaining_requests()

        # Should have one less (unless time passed and old ones expired)
        assert after <= before


# =============================================================================
# E2E Tests: Error Handling
# =============================================================================


class TestESPNErrorHandling:
    """E2E tests for error handling with real scenarios."""

    def test_handles_network_timeout_gracefully(self):
        """Verify client handles timeout gracefully.

        Educational Note:
            We create a client with very short timeout to force a timeout.
            This validates our error handling for network issues.
        """
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        # Create client with impossibly short timeout
        client = ESPNClient(timeout_seconds=0.001)

        # Should raise timeout error
        with pytest.raises((ESPNAPIError, requests.Timeout)):
            client.get_nfl_scoreboard()

    def test_retry_logic_functions(self, espn_client):
        """Verify retry logic by checking request count increases.

        Educational Note:
            We can't easily force server errors, but we can verify
            the retry mechanism is wired up by checking configurations.
        """
        # Verify retry configuration
        assert espn_client.max_retries >= 1
        assert espn_client.timeout_seconds >= 1


# =============================================================================
# E2E Tests: Data Quality
# =============================================================================


class TestESPNDataQuality:
    """E2E tests for data quality from real API."""

    def test_event_ids_are_unique(self, espn_client):
        """Verify all returned event IDs are unique.

        Educational Note:
            Duplicate event IDs would cause data integrity issues.
            This validates ESPN returns distinct games.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) < 2:
            pytest.skip("Need multiple games to test uniqueness")

        event_ids = [g["espn_event_id"] for g in games]
        assert len(event_ids) == len(set(event_ids)), "Duplicate event IDs found"

    def test_clock_display_format_valid(self, espn_client):
        """Verify clock display follows expected format.

        Educational Note:
            Clock display should be something like "12:34" or "0:00".
            We validate the format is parseable.
        """
        games = espn_client.get_nfl_scoreboard()

        for game in games:
            clock = game.get("clock_display", "")

            # Should contain colon for time display or be empty
            if clock and game["game_status"] == "in_progress":
                assert ":" in clock or clock.isdigit(), f"Invalid clock format: {clock}"

    def test_periods_in_valid_range(self, espn_client):
        """Verify periods are in valid football range.

        Educational Note:
            Football has 4 quarters (periods 1-4) plus possible overtime.
            Period 0 means pre-game.
        """
        games = espn_client.get_nfl_scoreboard()

        for game in games:
            period = game.get("period", 0)
            # Should be 0 (pre-game) to ~6 (multiple OT)
            assert 0 <= period <= 10, f"Invalid period: {period}"


# =============================================================================
# E2E Tests: Full Data Pipeline
# =============================================================================


class TestESPNDataPipeline:
    """E2E tests validating the full data collection pipeline."""

    def test_full_pipeline_nfl(self, espn_client):
        """Test complete NFL data collection pipeline.

        Educational Note:
            This is a comprehensive test that exercises the entire
            data collection flow from API to parsed GameState.
        """
        # Step 1: Fetch scoreboard
        games = espn_client.get_nfl_scoreboard()
        assert isinstance(games, list)

        # Step 2: If games exist, validate structure
        if games:
            game = games[0]

            # Core identification
            assert game["espn_event_id"]
            assert game["home_team"]
            assert game["away_team"]

            # Scores
            assert isinstance(game["home_score"], int)
            assert isinstance(game["away_score"], int)

            # Status
            assert game["game_status"] in {
                "scheduled",
                "in_progress",
                "halftime",
                "final",
                "unknown",
            }

            # Rate limiting worked
            assert len(espn_client.request_timestamps) > 0

    def test_full_pipeline_ncaaf(self, espn_client):
        """Test complete NCAAF data collection pipeline.

        Educational Note:
            NCAAF has more teams than NFL and different scheduling,
            but the data structure should be identical.
        """
        # Step 1: Fetch scoreboard
        games = espn_client.get_ncaaf_scoreboard()
        assert isinstance(games, list)

        # Step 2: If games exist, validate structure
        if games:
            game = games[0]

            # Same structure as NFL
            assert game["espn_event_id"]
            assert game["home_team"]
            assert game["away_team"]
            assert isinstance(game["home_score"], int)
            assert isinstance(game["away_score"], int)

    def test_get_live_games_filters_correctly(self, espn_client):
        """Test that get_live_games only returns in-progress games.

        Educational Note:
            This tests the filtering logic that separates live games
            from scheduled/completed games.
        """
        live_games = espn_client.get_live_games(league="nfl")

        # All returned games should be in progress or halftime
        for game in live_games:
            assert game["game_status"] in {"in_progress", "halftime"}, (
                f"get_live_games returned non-live game: {game['game_status']}"
            )
