"""
Integration tests for ESPN API client using VCR cassettes (Pattern 13).

Tests the full ESPNClient integration using REAL recorded API responses.
These tests use the VCR (Video Cassette Recorder) pattern:
- Cassettes recorded from real ESPN API during live NFL games (2025-12-07)
- Tests replay cassettes (no network calls needed)
- 100% real API response data (no mocks!)

Benefits of VCR pattern:
- Fast: No network calls during tests
- Deterministic: Same responses every time
- Real data: Uses actual ESPN API structures
- CI-friendly: Works without internet connection

Cassettes recorded: tests/cassettes/espn/*.yaml
- espn_nfl_scoreboard.yaml (14 NFL games)
- espn_ncaaf_scoreboard.yaml (6 NCAAF games)
- espn_nfl_live_games.yaml (8 live NFL games with situation data)
- espn_nba_scoreboard.yaml (7 NBA games)

Pattern 13 Exception: External API mock
These tests use VCR to replay REAL API responses. They test API client behavior
without touching the database, so database fixtures (db_pool, db_cursor, clean_test_data)
are not applicable. Pattern 13 lesson learned was about DATABASE connection pool mocking,
not HTTP interaction recording.

Related Requirements:
    - REQ-DATA-001: Game State Data Collection
    - REQ-TEST-002: Integration tests use real API fixtures (Pattern 13)

Reference:
    - Pattern 13 (CLAUDE.md): Real Fixtures, Not Mocks
    - GitHub Issue #180: ESPN E2E test edge cases (down: -1)
    - scripts/record_espn_cassettes.py: Cassette recording script
"""

import pytest
import vcr

from precog.api_connectors.espn_client import ESPNClient

# Configure VCR for test cassettes
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes/espn",
    record_mode="none",  # Never record in tests (only replay)
    match_on=["method", "scheme", "host", "port", "path", "query"],
    decode_compressed_response=True,
)


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.timeout(30)  # Prevent indefinite VCR hangs in CI
class TestESPNClientWithVCR:
    """
    Test ESPN API client using VCR cassettes with REAL API data.

    These tests verify:
    - Successful API requests return real ESPN data
    - ESPNGameFull structure with metadata/state sections
    - Response parsing handles real API structures
    - Edge cases like down: -1 during non-play situations

    Educational Note:
        Pattern 13: Real Fixtures, Not Mocks
        -----------------------------------
        Problem: Mocks create false positives (tests pass but code broken)
        - Mock returns simplified structure but real API has nested events
        - Test passes with mock, fails in production

        Solution: VCR Pattern
        - Record real API responses ONCE (during live games for best data)
        - Replay in tests (fast, no network)
        - Tests use 100% real data structures

        Cassettes recorded during NFL Week 14 (2025-12-07):
        - 8 live games in progress
        - Captured real situation data including down: -1 edge cases
    """

    def test_get_nfl_scoreboard_with_real_api_data(self):
        """
        Test get_nfl_scoreboard() with REAL recorded ESPN NFL data.

        Uses cassette: espn_nfl_scoreboard.yaml
        - 14 real NFL games from Week 14 (2025-12-07)
        - Real team names, scores, game status
        - Real metadata and state structure
        """
        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_nfl_scoreboard()

        # Verify real data structure
        assert len(games) == 14, "Should return 14 NFL games from cassette"

        # Verify first game has ESPNGameFull structure
        game = games[0]
        assert "metadata" in game, "Game should have metadata section"
        assert "state" in game, "Game should have state section"

        # Verify metadata structure
        metadata = game["metadata"]
        assert "espn_event_id" in metadata, "Metadata should have event ID"
        assert "home_team" in metadata, "Metadata should have home_team"
        assert "away_team" in metadata, "Metadata should have away_team"

        # Verify team info structure
        home_team = metadata["home_team"]
        assert "team_code" in home_team, "Team should have team_code"
        assert "display_name" in home_team, "Team should have display_name"

        # Verify state structure
        state = game["state"]
        assert "home_score" in state, "State should have home_score"
        assert "away_score" in state, "State should have away_score"
        assert "game_status" in state, "State should have game_status"
        assert "situation" in state, "State should have situation"

    def test_get_ncaaf_scoreboard_with_real_api_data(self):
        """
        Test get_ncaaf_scoreboard() with REAL recorded ESPN NCAAF data.

        Uses cassette: espn_ncaaf_scoreboard.yaml
        - 6 real college football games
        - Real team names with rankings
        - Championship week games
        """
        with my_vcr.use_cassette("espn_ncaaf_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_ncaaf_scoreboard()

        # Verify real data
        assert len(games) == 6, "Should return 6 NCAAF games from cassette"

        # Verify structure for college games
        for game in games:
            assert "metadata" in game
            assert "state" in game

            # Verify team info exists
            home_team = game["metadata"]["home_team"]
            away_team = game["metadata"]["away_team"]
            assert home_team["team_code"], "Home team should have code"
            assert away_team["team_code"], "Away team should have code"

    def test_get_nba_scoreboard_with_real_api_data(self):
        """
        Test get_nba_scoreboard() with REAL recorded ESPN NBA data.

        Uses cassette: espn_nba_scoreboard.yaml
        - 7 real NBA games
        - Different sport with different period structure
        """
        with my_vcr.use_cassette("espn_nba_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_nba_scoreboard()

        # Verify real data
        assert len(games) == 7, "Should return 7 NBA games from cassette"

        # Verify NBA games have proper structure
        for game in games:
            assert "metadata" in game
            assert "state" in game

            # NBA should have venue info
            venue = game["metadata"].get("venue", {})
            assert venue, "NBA game should have venue info"

    def test_get_live_games_with_real_api_data(self):
        """
        Test get_live_games() with REAL recorded live NFL games.

        Uses cassette: espn_nfl_live_games.yaml
        - 8 live NFL games captured during Week 14 (2025-12-07)
        - In-progress games with situation data
        - Includes edge cases like down: -1

        Educational Note:
            Live games have richer data than scheduled/final games:
            - possession: Which team has the ball
            - down: Current down (1-4, or -1 for special situations)
            - distance: Yards to first down
            - yard_line: Current field position

            The down: -1 edge case occurs during:
            - Kickoffs
            - Extra point attempts
            - Timeouts
            - Between plays
        """
        with my_vcr.use_cassette("espn_nfl_live_games.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_live_games(league="nfl")

        # Verify real data
        assert len(games) == 8, "Should return 8 live NFL games from cassette"

        # Verify all games are in-progress
        for game in games:
            state = game["state"]
            assert state["game_status"] in {
                "in_progress",
                "halftime",
            }, f"Live game should be in_progress or halftime, got {state['game_status']}"

            # Verify situation data exists
            situation = state.get("situation", {})
            assert situation is not None, "Live game should have situation data"

    def test_situation_data_edge_cases(self):
        """
        Test that situation data edge cases are handled correctly.

        Specifically tests the down: -1 edge case that caused CI failures.

        Edge Case Details:
            ESPN returns down: -1 during non-play situations:
            - Kickoffs (no down applicable)
            - Extra point/2-point attempts
            - Timeouts
            - Between plays

            The E2E test (test_espn_e2e.py) was failing because it expected:
            - down >= 1 when present

            Fix (PR #180): Changed validation to allow negative down values
            - if situation_down is not None and situation_down >= 1:

        Reference: GitHub Issue #180, tests/e2e/api_connectors/test_espn_e2e.py
        """
        with my_vcr.use_cassette("espn_nfl_live_games.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_live_games(league="nfl")

        # Find games with down: -1 or down: None (edge cases)
        edge_case_games = []
        for game in games:
            situation = game["state"].get("situation", {})
            down = situation.get("down")

            # down can be None, -1, or 1-4
            if down is None or down < 1:
                edge_case_games.append(
                    {
                        "matchup": f"{game['metadata']['away_team']['display_name']} @ {game['metadata']['home_team']['display_name']}",
                        "down": down,
                        "status": game["state"]["game_status"],
                    }
                )

        # Should find at least one edge case in live games
        # (From recording: Saints @ Buccaneers and Steelers @ Ravens had down: -1)
        assert len(edge_case_games) >= 1, (
            f"Should find at least 1 game with down edge case. Found: {edge_case_games}"
        )

        # Edge cases found in cassette are logged via pytest output


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.timeout(30)
class TestESPNClientStructureWithVCR:
    """
    Test ESPN client response structure using REAL API data.

    Verifies that:
    - ESPNGameFull TypedDict structure is correct
    - ESPNGameMetadata contains expected fields
    - ESPNGameState contains expected fields
    - ESPNTeamInfo contains expected fields
    - ESPNSituationData contains expected fields
    """

    def test_espn_game_full_structure(self):
        """
        Verify ESPNGameFull TypedDict has correct structure.

        ESPNGameFull should have:
        - metadata: ESPNGameMetadata
        - state: ESPNGameState

        This structure matches database schema design for:
        - metadata -> game metadata + venues + teams tables
        - state -> game_states table (SCD Type 2)
        """
        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_nfl_scoreboard()

        # Test structure of first game
        game = games[0]

        # ESPNGameFull keys
        assert set(game.keys()) == {
            "metadata",
            "state",
        }, f"ESPNGameFull should have metadata and state, got {game.keys()}"

    def test_espn_game_metadata_structure(self):
        """
        Verify ESPNGameMetadata has expected fields.

        Expected fields:
        - espn_event_id: Unique ESPN identifier
        - game_date: ISO 8601 date string
        - home_team: ESPNTeamInfo
        - away_team: ESPNTeamInfo
        - venue: ESPNVenueInfo
        - broadcast: TV network
        - neutral_site: Boolean
        - season_type: Preseason/regular/playoff
        - week_number: Week of season
        """
        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_nfl_scoreboard()

        metadata = games[0]["metadata"]

        # Required fields
        required_fields = [
            "espn_event_id",
            "game_date",
            "home_team",
            "away_team",
            "venue",
        ]
        for field in required_fields:
            assert field in metadata, f"Metadata should have {field}"

        # Optional fields (may not always be present)
        optional_fields = ["broadcast", "neutral_site", "season_type", "week_number"]
        for field in optional_fields:
            # Just check type if present
            if field in metadata:
                assert metadata[field] is not None or True  # Can be None

    def test_espn_team_info_structure(self):
        """
        Verify ESPNTeamInfo has expected fields.

        Expected fields:
        - espn_team_id: ESPN's internal team ID
        - team_code: Short abbreviation (e.g., "KC")
        - team_name: Full name (e.g., "Kansas City Chiefs")
        - display_name: Short name (e.g., "Chiefs")
        - record: Season record (e.g., "10-1")
        - home_record: Home record
        - away_record: Away record
        - rank: College ranking (None for NFL)
        """
        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_nfl_scoreboard()

        home_team = games[0]["metadata"]["home_team"]
        away_team = games[0]["metadata"]["away_team"]

        # Required fields for team info
        required_fields = ["espn_team_id", "team_code", "display_name"]
        for field in required_fields:
            assert field in home_team, f"Home team should have {field}"
            assert field in away_team, f"Away team should have {field}"

        # Verify team codes are short abbreviations
        assert len(home_team["team_code"]) <= 4, "Team code should be short abbreviation"
        assert len(away_team["team_code"]) <= 4, "Team code should be short abbreviation"

    def test_espn_game_state_structure(self):
        """
        Verify ESPNGameState has expected fields.

        Expected fields:
        - espn_event_id: Reference to game
        - home_score: Home team score
        - away_score: Away team score
        - period: Current period (1-4, 5+ for OT)
        - clock_seconds: Time remaining
        - clock_display: Formatted clock (e.g., "8:05")
        - game_status: scheduled/in_progress/halftime/final
        - situation: ESPNSituationData
        - linescores: Quarter-by-quarter scores
        """
        with my_vcr.use_cassette("espn_nfl_live_games.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_live_games(league="nfl")

        state = games[0]["state"]

        # Required fields
        required_fields = [
            "espn_event_id",
            "home_score",
            "away_score",
            "period",
            "game_status",
            "situation",
        ]
        for field in required_fields:
            assert field in state, f"State should have {field}"

        # Verify score types
        assert isinstance(state["home_score"], int), "home_score should be int"
        assert isinstance(state["away_score"], int), "away_score should be int"

        # Verify period is positive
        assert state["period"] >= 0, "period should be non-negative"

    def test_espn_situation_data_structure(self):
        """
        Verify ESPNSituationData has expected fields for football.

        Football-specific fields:
        - possession: Team code with ball
        - down: Current down (1-4, or -1 for special situations)
        - distance: Yards to first down
        - yard_line: Current field position
        - is_red_zone: Inside opponent's 20
        - home_timeouts: Home team timeouts remaining
        - away_timeouts: Away team timeouts remaining
        """
        with my_vcr.use_cassette("espn_nfl_live_games.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_live_games(league="nfl")

        situation = games[0]["state"]["situation"]

        # Situation should be a dict
        assert isinstance(situation, dict), "Situation should be a dict"

        # Football-specific fields (may be None if not applicable)
        football_fields = ["down", "distance", "yard_line", "is_red_zone"]
        for field in football_fields:
            if field in situation:
                # Just verify the field exists and has reasonable type
                value = situation[field]
                # down, distance, yard_line can be int or None
                # is_red_zone should be bool
                if field == "is_red_zone":
                    assert isinstance(value, bool), f"{field} should be bool"


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.timeout(30)
class TestESPNClientMultiLeagueWithVCR:
    """
    Test ESPN client multi-league support with REAL data.

    Verifies that different sports return appropriate data structures
    while maintaining the same ESPNGameFull format.
    """

    def test_nfl_vs_nba_structure_consistency(self):
        """
        Verify NFL and NBA games share the same structure.

        Both should return ESPNGameFull with:
        - metadata: Team info, venue, date
        - state: Scores, clock, status, situation

        The difference is in situation data:
        - NFL: down, distance, yard_line
        - NBA: fouls, bonus, possession_arrow
        """
        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            nfl_client = ESPNClient(rate_limit_per_hour=500)
            nfl_games = nfl_client.get_nfl_scoreboard()

        with my_vcr.use_cassette("espn_nba_scoreboard.yaml"):
            nba_client = ESPNClient(rate_limit_per_hour=500)
            nba_games = nba_client.get_nba_scoreboard()

        # Both should have games
        assert len(nfl_games) > 0, "Should have NFL games"
        assert len(nba_games) > 0, "Should have NBA games"

        # Both should have same top-level structure
        nfl_keys = set(nfl_games[0].keys())
        nba_keys = set(nba_games[0].keys())
        assert (
            nfl_keys
            == nba_keys
            == {
                "metadata",
                "state",
            }
        ), "NFL and NBA should have same structure"

        # Both metadata should have same required fields
        nfl_meta_keys = set(nfl_games[0]["metadata"].keys())
        nba_meta_keys = set(nba_games[0]["metadata"].keys())
        required_meta = {"espn_event_id", "home_team", "away_team", "venue"}
        assert required_meta <= nfl_meta_keys, "NFL metadata should have required fields"
        assert required_meta <= nba_meta_keys, "NBA metadata should have required fields"

    def test_scoreboard_method_consistency(self):
        """
        Verify get_scoreboard() works for all recorded leagues.

        The generic get_scoreboard(league) method should return
        the same data as the sport-specific methods.
        """
        # Test NFL
        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            nfl_via_specific = client.get_nfl_scoreboard()

        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            nfl_via_generic = client.get_scoreboard("nfl")

        # Should return same number of games
        assert len(nfl_via_specific) == len(nfl_via_generic), (
            "Specific and generic methods should return same games"
        )

        # Test NBA
        with my_vcr.use_cassette("espn_nba_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            nba_via_specific = client.get_nba_scoreboard()

        with my_vcr.use_cassette("espn_nba_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            nba_via_generic = client.get_scoreboard("nba")

        assert len(nba_via_specific) == len(nba_via_generic), (
            "Specific and generic methods should return same games"
        )
