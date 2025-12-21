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

            The ESPN client returns ESPNGameFull TypedDict with:
            - metadata: Static game info (teams, venue, broadcast)
            - state: Dynamic info (scores, clock, status)
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        game = games[0]

        # Core structure should have metadata and state
        assert "metadata" in game
        assert "state" in game

        # Core fields in metadata
        assert "espn_event_id" in game["metadata"]
        assert "home_team" in game["metadata"]
        assert "away_team" in game["metadata"]

    def test_scores_are_integers(self, espn_client):
        """Verify scores are parsed as integers.

        Educational Note:
            ESPN returns scores as strings in JSON. We must convert
            them to integers for calculations. This validates that
            conversion. Scores are in the 'state' section of ESPNGameFull.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        for game in games:
            # Scores are in the state section
            assert isinstance(game["state"]["home_score"], int)
            assert isinstance(game["state"]["away_score"], int)
            # Scores should be non-negative
            assert game["state"]["home_score"] >= 0
            assert game["state"]["away_score"] >= 0

    def test_game_status_maps_correctly(self, espn_client):
        """Verify game status maps to known values.

        Educational Note:
            ESPN uses various status codes (pre, in, post, etc.).
            We must map these to our internal status values consistently.
            Status is in the 'state' section of ESPNGameFull.
        """
        games = espn_client.get_nfl_scoreboard()

        known_statuses = {"pre", "scheduled", "in_progress", "halftime", "final", "unknown"}

        for game in games:
            # Status is in the state section
            status = game["state"]["game_status"]
            assert status in known_statuses, f"Unknown status: {status}"

    def test_team_abbreviations_are_strings(self, espn_client):
        """Verify team abbreviations are parsed as strings.

        Educational Note:
            Team abbreviations are used as keys for lookups and joins.
            They must be consistent string types.
            In ESPNGameFull, home_team/away_team are dicts with team_code.
        """
        games = espn_client.get_nfl_scoreboard()

        for game in games:
            # Teams are now dicts in metadata section
            home_team = game["metadata"]["home_team"]
            away_team = game["metadata"]["away_team"]
            assert isinstance(home_team["team_code"], str)
            assert isinstance(away_team["team_code"], str)
            # Abbreviations should be short (2-4 chars typically)
            assert 1 <= len(home_team["team_code"]) <= 10
            assert 1 <= len(away_team["team_code"]) <= 10


# =============================================================================
# E2E Tests: Data Structure Validation
# =============================================================================


class TestESPNDataStructure:
    """E2E tests validating the complete GameState structure."""

    def test_game_state_has_required_fields(self, espn_client):
        """Verify ESPNGameFull contains all required fields.

        Educational Note:
            Our ESPNGameFull TypedDict has metadata (static) and state (dynamic).
            This validates real API data populates both sections.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        # Required fields in metadata
        metadata_fields = [
            "espn_event_id",
            "home_team",
            "away_team",
        ]

        # Required fields in state
        state_fields = [
            "espn_event_id",
            "home_score",
            "away_score",
            "period",
            "clock_display",
            "game_status",
        ]

        game = games[0]
        assert "metadata" in game, "Missing metadata section"
        assert "state" in game, "Missing state section"

        for field in metadata_fields:
            assert field in game["metadata"], f"Missing metadata field: {field}"

        for field in state_fields:
            assert field in game["state"], f"Missing state field: {field}"

    def test_model_training_fields_present(self, espn_client):
        """Verify model training fields are populated when available.

        Educational Note:
            Some fields (records, venue, broadcast) are for ML model features.
            They may not always be present, but when they are, they should
            have correct types.

            In ESPNGameFull, team info is nested in metadata.home_team/away_team.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) == 0:
            pytest.skip("No NFL games available today")

        game = games[0]
        metadata = game["metadata"]

        # Check team objects have expected fields
        home_team = metadata["home_team"]
        away_team = metadata["away_team"]

        team_fields = {
            "espn_team_id": str,
            "team_code": str,
            "team_name": str,
            "display_name": str,
            "record": str,
        }

        for field, expected_type in team_fields.items():
            if field in home_team and home_team[field] is not None:
                assert isinstance(home_team[field], expected_type), (
                    f"home_team.{field} is {type(home_team[field])}, expected {expected_type}"
                )
            if field in away_team and away_team[field] is not None:
                assert isinstance(away_team[field], expected_type), (
                    f"away_team.{field} is {type(away_team[field])}, expected {expected_type}"
                )

        # Check venue info if present
        if "venue" in metadata and metadata["venue"] is not None:
            venue = metadata["venue"]
            if "venue_name" in venue:
                assert isinstance(venue["venue_name"], str)

        # Check game_date in metadata
        if "game_date" in metadata and metadata["game_date"] is not None:
            assert isinstance(metadata["game_date"], str)

    def test_situation_data_valid_when_present(self, espn_client):
        """Verify situation data (down, distance, possession) is valid.

        Educational Note:
            Situation data is only present for in-progress football games.
            When present, values must be in valid ranges.
            In ESPNGameFull, situation is nested in state.situation.

            Edge Cases:
            - down == -1: ESPN returns this when there's no active down
              (e.g., during kickoff, timeout, between plays, PAT attempts)
            - distance == 0: Can occur during goal-line situations or
              when no active play (e.g., after touchdown)

            Multi-League Strategy:
            - NFL games are typically on Sunday/Monday/Thursday
            - NCAAF games are on weekends (more frequent during season)
            - We check both leagues to increase test coverage success rate
        """
        # Try multiple football leagues for better test coverage
        # NFL has limited game days, NCAAF has more games on weekends
        games = espn_client.get_live_games(league="nfl")

        if len(games) == 0:
            # Fall back to NCAAF (college football) if no NFL games
            games = espn_client.get_live_games(league="ncaaf")

        if len(games) == 0:
            pytest.skip("No live football games (NFL or NCAAF) right now")

        for game in games:
            state = game["state"]
            situation = state.get("situation", {})

            # If down is present and positive, should be 1-4
            # ESPN returns -1 when no active down (kickoff, timeout, PAT, etc.)
            down = situation.get("down")
            if down is not None and down > 0:
                assert 1 <= down <= 4, f"Invalid down value: {down}"

            # If distance is present and positive, validate range
            # Can be 0 during goal-line or no-active-play situations
            distance = situation.get("distance")
            if distance is not None and distance > 0:
                assert distance <= 99, f"Invalid distance: {distance}"

            # Timeouts should be 0-3
            assert 0 <= situation.get("home_timeouts", 3) <= 3
            assert 0 <= situation.get("away_timeouts", 3) <= 3


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
        client = ESPNClient(timeout_seconds=0.001)  # Sub-millisecond to guarantee timeout

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
            Event IDs are in both metadata and state sections.
        """
        games = espn_client.get_nfl_scoreboard()

        if len(games) < 2:
            pytest.skip("Need multiple games to test uniqueness")

        # Event IDs are in the metadata section
        event_ids = [g["metadata"]["espn_event_id"] for g in games]
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
            data collection flow from API to parsed ESPNGameFull.
        """
        # Step 1: Fetch scoreboard
        games = espn_client.get_nfl_scoreboard()
        assert isinstance(games, list)

        # Step 2: If games exist, validate structure
        if games:
            game = games[0]
            metadata = game["metadata"]
            state = game["state"]

            # Core identification (in metadata)
            assert metadata["espn_event_id"]
            assert metadata["home_team"]
            assert metadata["away_team"]

            # Scores (in state)
            assert isinstance(state["home_score"], int)
            assert isinstance(state["away_score"], int)

            # Status (in state) - refers to GAME STATE (pre/in/post = pregame/live/finished)
            # NOT to be confused with SEASON TYPE (preseason/regular/postseason)
            # Valid game_status values from STATUS_MAP + halftime + unknown fallback
            assert state["game_status"] in {
                "pre",  # Pregame (game scheduled but not started)
                "in_progress",  # Game is live
                "halftime",  # Halftime break
                "final",  # Game completed
                "unknown",  # Fallback for unmapped ESPN states
            }

            # Rate limiting worked
            assert len(espn_client.request_timestamps) > 0

    def test_full_pipeline_ncaaf(self, espn_client):
        """Test complete NCAAF data collection pipeline.

        Educational Note:
            NCAAF has more teams than NFL and different scheduling,
            but the data structure should be identical (ESPNGameFull).
        """
        # Step 1: Fetch scoreboard
        games = espn_client.get_ncaaf_scoreboard()
        assert isinstance(games, list)

        # Step 2: If games exist, validate structure
        if games:
            game = games[0]
            metadata = game["metadata"]
            state = game["state"]

            # Same structure as NFL (in metadata and state)
            assert metadata["espn_event_id"]
            assert metadata["home_team"]
            assert metadata["away_team"]
            assert isinstance(state["home_score"], int)
            assert isinstance(state["away_score"], int)

    def test_get_live_games_filters_correctly(self, espn_client):
        """Test that get_live_games only returns in-progress games.

        Educational Note:
            This tests the filtering logic that separates live games
            from scheduled/completed games.

            Multi-Sport Strategy:
            Since live games are time-dependent, we check multiple leagues
            to maximize the chance of finding active games:
            - NFL: Sunday/Monday/Thursday during season
            - NCAAF: Weekends (Saturdays primarily)
            - NBA: Most nights October-April
            - NCAAB: Most nights November-March
            - NHL: Most nights October-April
        """
        # Try multiple leagues to find live games
        # NCAA basketball (NCAAB) runs most evenings November-March
        leagues_to_try = ["nfl", "ncaaf", "nba", "ncaab", "nhl"]
        live_games = []

        for league in leagues_to_try:
            live_games = espn_client.get_live_games(league=league)
            if len(live_games) > 0:
                break

        # If we found live games, verify they're all in-progress
        # All returned games should be in progress or halftime
        for game in live_games:
            status = game["state"]["game_status"]
            assert status in {"in_progress", "halftime"}, (
                f"get_live_games returned non-live game: {status}"
            )
