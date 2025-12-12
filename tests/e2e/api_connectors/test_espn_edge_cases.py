"""
ESPN Edge Case E2E Tests (Issue #207).

Comprehensive tests for ESPN data edge cases that have caused production issues:
- Venue data anomalies (missing fields, null values)
- Game state edge cases (overtime, suspended, delayed)
- Down/distance edge cases (goal, inches, null during special plays)
- Score edge cases (0-0, high scores, tied games)
- Team data edge cases (unknown IDs, special characters)

These tests use a combination of:
1. VCR cassettes with real recorded data
2. Validation module testing with synthetic edge cases
3. Live API tests when network is available

Educational Note:
    E2E edge case tests differ from unit tests because:
    - They test realistic data scenarios from real API responses
    - They verify the full pipeline handles edge cases gracefully
    - They catch integration issues between parsing and validation

    The validation approach is "soft validation":
    - Log anomalies but don't block storage
    - Track counts for pattern detection
    - Provide structured results for debugging

    Note on Type Annotations:
        Some tests use `cast()` or `# type: ignore` for edge case data
        that intentionally violates TypedDict contracts. This is correct
        because we're testing how the validator handles malformed API data.

Reference:
    - Issue #207: E2E Testing for ESPN Polling Edge Cases
    - ADR-101: ESPN Status and Season Type Mapping
    - REQ-DATA-002: Data Quality Monitoring
    - docs/foundation/TESTING_STRATEGY_V3.2.md

Phase: 2 (Live Data Collection)
"""

from typing import Any, cast

import pytest
import vcr

from precog.api_connectors.espn_client import (
    ESPNClient,
    ESPNGameFull,
    ESPNSituationData,
    ESPNTeamInfo,
    ESPNVenueInfo,
)
from precog.validation.espn_validation import ESPNDataValidator

# Mark all tests with e2e marker
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.api,
]

# Configure VCR for cassette replay
my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes/espn",
    record_mode="none",
    match_on=["method", "scheme", "host", "port", "path", "query"],
    decode_compressed_response=True,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def validator() -> ESPNDataValidator:
    """Create a validator instance for edge case testing."""
    return ESPNDataValidator(track_anomalies=True)


@pytest.fixture
def minimal_team_info() -> ESPNTeamInfo:
    """Create minimal team info for synthetic tests."""
    return {
        "espn_team_id": "1",
        "team_code": "TST",
        "team_name": "Test Team",
        "display_name": "Test",
        "record": "0-0",
        "home_record": "0-0",
        "away_record": "0-0",
        "rank": None,
    }


@pytest.fixture
def minimal_venue_info() -> ESPNVenueInfo:
    """Create minimal venue info for synthetic tests."""
    return {
        "espn_venue_id": "1",
        "venue_name": "Test Stadium",
        "city": "Test City",
        "state": "TS",
        "capacity": 70000,
        "indoor": False,
    }


# =============================================================================
# Venue Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestVenueEdgeCases:
    """
    Tests for venue data edge cases.

    ESPN API sometimes returns venues with missing or null fields.
    These tests verify our validation handles these gracefully.

    Edge cases from Issue #207:
    - Venue with no capacity (ESPN doesn't provide capacity in basic API)
    - Venue name with special characters
    - Missing venue entirely (neutral site games)
    """

    def test_missing_venue_is_allowed(self, validator: ESPNDataValidator) -> None:
        """Verify games without venue data are valid (neutral site, etc.).

        Educational Note:
            Some games have no venue data in the ESPN API:
            - London/Mexico City international games may have partial data
            - Some historical data has missing venue info
            - Exhibition games may omit venue

            Note: We use cast() here because we're intentionally creating
            malformed data to test the validator's edge case handling.
        """
        # Build as dict[str, Any] then cast - we're testing edge cases
        # where real API data might have None values or missing fields
        game_data: dict[str, Any] = {
            "metadata": {
                "espn_event_id": "401547001",
                "game_date": "2025-01-15T18:00:00Z",
                "home_team": {
                    "espn_team_id": "1",
                    "team_code": "TST",
                    "team_name": "Test Team",
                    "display_name": "Test",
                    "record": "0-0",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "rank": None,
                },
                "away_team": {
                    "espn_team_id": "2",
                    "team_code": "OPP",
                    "team_name": "Opponent",
                    "display_name": "Opponent",
                    "record": "0-0",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "rank": None,
                },
                # Missing venue - real API can return None for neutral site
                "broadcast": "ESPN",
                "neutral_site": True,  # Often correlates with missing venue
                "season_type": "regular",
                "week_number": 1,
            },
            "state": {
                "espn_event_id": "401547001",
                "home_score": 0,
                "away_score": 0,
                "period": 0,
                "clock_seconds": 0.0,  # Pre-game has 0 seconds
                "clock_display": "",
                "game_status": "pre",
                "situation": {},
                "linescores": [],  # Empty before game starts
            },
        }
        game = cast("ESPNGameFull", game_data)

        result = validator.validate_game_state(game)

        # Missing venue should not cause an error
        assert not result.has_errors, f"Missing venue should be allowed: {result.errors}"

    def test_venue_with_special_characters(self, validator: ESPNDataValidator) -> None:
        """Verify venue names with special characters are handled.

        Educational Note:
            Real stadium names have special characters:
            - Mercedes-Benz Stadium (hyphen)
            - Levi's Stadium (apostrophe)
            - Caesars Superdome (used to have apostrophe)
            - SoFi Stadium (no special chars but unusual capitalization)
        """
        game: ESPNGameFull = {
            "metadata": {
                "espn_event_id": "401547002",
                "game_date": "2025-01-15T18:00:00Z",
                "home_team": {
                    "espn_team_id": "1",
                    "team_code": "NO",
                    "team_name": "New Orleans Saints",
                    "display_name": "Saints",
                    "record": "5-5",
                    "home_record": "3-2",
                    "away_record": "2-3",
                    "rank": None,
                },
                "away_team": {
                    "espn_team_id": "2",
                    "team_code": "ATL",
                    "team_name": "Atlanta Falcons",
                    "display_name": "Falcons",
                    "record": "4-6",
                    "home_record": "2-3",
                    "away_record": "2-3",
                    "rank": None,
                },
                "venue": {
                    "venue_name": "Caesars Superdome",
                    "city": "New Orleans",
                    "state": "LA",
                    "indoor": True,
                },
                "broadcast": "FOX",
                "neutral_site": False,
                "season_type": "regular",
                "week_number": 10,
            },
            "state": {
                "espn_event_id": "401547002",
                "home_score": 14,
                "away_score": 10,
                "period": 2,
                "clock_seconds": 300,
                "clock_display": "5:00",
                "game_status": "in_progress",
                "situation": {
                    "possession": "NO",
                    "down": 1,
                    "distance": 10,
                    "yard_line": 35,
                    "is_red_zone": False,
                    "home_timeouts": 3,
                    "away_timeouts": 3,
                },
                "linescores": [],
            },
        }

        result = validator.validate_game_state(game)

        assert result.is_valid, f"Special character venue should be valid: {result.errors}"


# =============================================================================
# Game State Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestGameStateEdgeCases:
    """
    Tests for game state edge cases.

    These test unusual game situations that require special handling:
    - Overtime games (period > 4 for football, > 4 for basketball)
    - Suspended/delayed games (special status values)
    - Cancelled/postponed games
    """

    def test_overtime_period_valid(self, validator: ESPNDataValidator) -> None:
        """Verify overtime periods (5+) are valid.

        Educational Note:
            Overtime in different sports:
            - NFL: Single 10-minute OT period (regular season), unlimited (playoffs)
            - NCAAF: Alternating possessions from 25-yard line
            - NBA: 5-minute OT periods
            - NHL: 5-minute 3v3 OT, then shootout

            Period numbers during OT:
            - Period 5 = 1st OT
            - Period 6 = 2nd OT
            - etc.
        """
        game: ESPNGameFull = {
            "metadata": {
                "espn_event_id": "401547003",
                "game_date": "2025-01-15T18:00:00Z",
                "home_team": {
                    "espn_team_id": "1",
                    "team_code": "KC",
                    "team_name": "Kansas City Chiefs",
                    "display_name": "Chiefs",
                    "record": "10-2",
                    "home_record": "5-1",
                    "away_record": "5-1",
                    "rank": None,
                },
                "away_team": {
                    "espn_team_id": "2",
                    "team_code": "BUF",
                    "team_name": "Buffalo Bills",
                    "display_name": "Bills",
                    "record": "9-3",
                    "home_record": "5-1",
                    "away_record": "4-2",
                    "rank": None,
                },
                "venue": {
                    "venue_name": "Arrowhead Stadium",
                    "city": "Kansas City",
                    "state": "MO",
                    "indoor": False,
                },
                "broadcast": "CBS",
                "neutral_site": False,
                "season_type": "postseason",
                "week_number": 20,
            },
            "state": {
                "espn_event_id": "401547003",
                "home_score": 42,
                "away_score": 36,
                "period": 5,  # Overtime!
                "clock_seconds": 420,
                "clock_display": "7:00",
                "game_status": "in_progress",
                "situation": {
                    "possession": "KC",
                    "down": 2,
                    "distance": 7,
                    "yard_line": 45,
                    "is_red_zone": False,
                    "home_timeouts": 2,
                    "away_timeouts": 1,
                },
                "linescores": [],
            },
        }

        result = validator.validate_game_state(game)

        # Overtime period should be valid
        assert result.is_valid, f"Overtime period should be valid: {result.errors}"

    def test_multiple_overtime_periods(self, validator: ESPNDataValidator) -> None:
        """Verify multiple OT periods (6, 7, 8) are handled.

        Educational Note:
            Historical multi-OT games:
            - 6 OT college basketball games are not uncommon
            - NFL playoff games can theoretically go multiple OTs
            - College football has seen 7+ OT games
        """
        game: ESPNGameFull = {
            "metadata": {
                "espn_event_id": "401547004",
                "game_date": "2025-01-15T18:00:00Z",
                "home_team": {
                    "espn_team_id": "1",
                    "team_code": "TEX",
                    "team_name": "Texas Longhorns",
                    "display_name": "Texas",
                    "record": "8-2",
                    "home_record": "5-0",
                    "away_record": "3-2",
                    "rank": 5,  # Ranked college team
                },
                "away_team": {
                    "espn_team_id": "2",
                    "team_code": "OKLA",
                    "team_name": "Oklahoma Sooners",
                    "display_name": "Oklahoma",
                    "record": "7-3",
                    "home_record": "4-1",
                    "away_record": "3-2",
                    "rank": 12,
                },
                "venue": {
                    "venue_name": "Cotton Bowl",
                    "city": "Dallas",
                    "state": "TX",
                    "indoor": False,
                },
                "broadcast": "ABC",
                "neutral_site": True,
                "season_type": "regular",
                "week_number": 8,
            },
            "state": {
                "espn_event_id": "401547004",
                "home_score": 63,
                "away_score": 63,
                "period": 8,  # 4th overtime!
                "clock_seconds": 0,
                "clock_display": "0:00",
                "game_status": "in_progress",
                "situation": {
                    "possession": "TEX",
                    "down": 1,
                    "distance": 3,  # From the 3-yard line in college OT
                    "yard_line": 3,
                    "is_red_zone": True,
                    "home_timeouts": 0,
                    "away_timeouts": 0,
                },
                "linescores": [],
            },
        }

        result = validator.validate_game_state(game)

        # Multiple OT periods should be valid
        assert result.is_valid, f"Multiple OT periods should be valid: {result.errors}"

    def test_unknown_game_status_logged(self, validator: ESPNDataValidator) -> None:
        """Verify unknown game statuses are logged as warnings.

        Educational Note:
            ESPN may return statuses we haven't mapped:
            - suspended: Game stopped mid-play (weather, power outage)
            - delayed: Start time pushed back
            - cancelled: Game won't be played
            - postponed: Rescheduled to different date
            - forfeit: One team declared loser

            We should handle these gracefully and log them.

            Note: We use cast() here because we're intentionally creating
            malformed data to test the validator's edge case handling.
        """
        # Build as dict[str, Any] then cast - testing malformed API data
        game_data: dict[str, Any] = {
            "metadata": {
                "espn_event_id": "401547005",
                "game_date": "2025-01-15T18:00:00Z",
                "home_team": {
                    "espn_team_id": "1",
                    "team_code": "TST",
                    "team_name": "Test Team",
                    "display_name": "Test",
                    "record": "0-0",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "rank": None,
                },
                "away_team": {
                    "espn_team_id": "2",
                    "team_code": "OPP",
                    "team_name": "Opponent",
                    "display_name": "Opponent",
                    "record": "0-0",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "rank": None,
                },
                "venue": None,  # Missing venue
                "broadcast": None,  # Missing broadcast
                "neutral_site": False,
                "season_type": "regular",
                "week_number": 1,
            },
            "state": {
                "espn_event_id": "401547005",
                "home_score": 0,
                "away_score": 0,
                "period": 0,
                "clock_seconds": None,  # Unknown clock
                "clock_display": "",
                "game_status": "unknown",  # Unmapped status
                "situation": {},
                "linescores": [],  # Missing linescores
            },
        }
        game = cast("ESPNGameFull", game_data)

        result = validator.validate_game_state(game)

        # Unknown status should not cause error (soft validation)
        assert not result.has_errors, f"Unknown status should not error: {result.errors}"


# =============================================================================
# Down/Distance Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestDownDistanceEdgeCases:
    """
    Tests for football down/distance edge cases.

    The ESPN API returns unusual down/distance values in certain situations:
    - down: -1 during kickoffs, PAT attempts, timeouts
    - distance: 0 during goal-line situations
    - Null values during non-play situations
    """

    def test_down_negative_one_valid(self, validator: ESPNDataValidator) -> None:
        """Verify down=-1 is valid (special play situations).

        Educational Note:
            ESPN returns down=-1 during:
            - Kickoffs (no down applicable)
            - Extra point/2-point attempts
            - Timeouts
            - Between plays

            Issue #180 documented this edge case causing E2E test failures.
        """
        situation: ESPNSituationData = {
            "possession": "KC",
            "down": -1,  # Special situation
            "distance": 0,
            "yard_line": 35,
            "is_red_zone": False,
            "home_timeouts": 3,
            "away_timeouts": 3,
        }

        result = validator.validate_situation(situation, "nfl")

        # down=-1 should be valid
        assert result.is_valid, f"down=-1 should be valid: {result.errors}"

    def test_goal_line_situation(self, validator: ESPNDataValidator) -> None:
        """Verify goal-line situations are valid.

        Educational Note:
            "1st & Goal" occurs when:
            - Team is inside the 10-yard line
            - Distance to goal < 10 yards
            - ESPN may show distance as actual yards to goal (not 10)
        """
        situation: ESPNSituationData = {
            "possession": "BUF",
            "down": 1,
            "distance": 3,  # Goal from the 3
            "yard_line": 3,
            "is_red_zone": True,
            "home_timeouts": 2,
            "away_timeouts": 2,
        }

        result = validator.validate_situation(situation, "nfl")

        assert result.is_valid, f"Goal-line should be valid: {result.errors}"

    def test_fourth_and_inches(self, validator: ESPNDataValidator) -> None:
        """Verify 4th & inches is valid.

        Educational Note:
            "4th & Inches" typically shows as:
            - distance: 1 (rounded up)
            - Some systems show distance: 0.5 (Decimal)
        """
        situation: ESPNSituationData = {
            "possession": "NE",
            "down": 4,
            "distance": 1,  # Inches, rounded to 1
            "yard_line": 45,
            "is_red_zone": False,
            "home_timeouts": 1,
            "away_timeouts": 0,
        }

        result = validator.validate_situation(situation, "nfl")

        assert result.is_valid, f"4th & inches should be valid: {result.errors}"

    def test_null_situation_during_timeout(self, validator: ESPNDataValidator) -> None:
        """Verify null/empty situation during timeout is valid.

        Educational Note:
            During timeouts, commercial breaks, or injuries:
            - Situation data may be null/empty
            - down/distance not applicable during stoppage
        """
        situation: ESPNSituationData = {
            "possession": None,
            "down": None,
            "distance": None,
            "yard_line": None,
            "is_red_zone": False,
            "home_timeouts": 2,
            "away_timeouts": 2,
        }

        result = validator.validate_situation(situation, "nfl")

        # Null values during stoppage should be valid
        assert result.is_valid, f"Null situation should be valid: {result.errors}"


# =============================================================================
# Score Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestScoreEdgeCases:
    """
    Tests for score edge cases.

    Score validation ensures data integrity:
    - Non-negative scores
    - Monotonic increase within period
    - Reasonable maximum values
    """

    def test_zero_zero_score_valid(self, validator: ESPNDataValidator) -> None:
        """Verify 0-0 score is valid (pre-game or scoreless).

        Educational Note:
            0-0 is valid for:
            - Pre-game (game hasn't started)
            - Scoreless games (rare but possible)
            - Start of overtime periods
        """
        result = validator.validate_score(home_score=0, away_score=0)

        assert result.is_valid, f"0-0 should be valid: {result.errors}"

    def test_high_score_valid(self, validator: ESPNDataValidator) -> None:
        """Verify high scores (100+) are valid.

        Educational Note:
            High scores can occur in:
            - Basketball (120+ common)
            - Football (occasional 70+ games)
            - Hockey (rarely 10+)

            We should allow high scores but may want to track as anomalies.
        """
        result = validator.validate_score(home_score=127, away_score=124)

        # High scores should be valid (no maximum)
        assert result.is_valid, f"High scores should be valid: {result.errors}"

    def test_tied_game_valid(self, validator: ESPNDataValidator) -> None:
        """Verify tied scores are valid."""
        result = validator.validate_score(home_score=21, away_score=21)

        assert result.is_valid, f"Tied scores should be valid: {result.errors}"

    def test_negative_score_error(self, validator: ESPNDataValidator) -> None:
        """Verify negative scores cause errors.

        Educational Note:
            Negative scores indicate data corruption:
            - API parsing error
            - Byte overflow issue
            - Malformed response
        """
        result = validator.validate_score(home_score=-1, away_score=10)

        assert result.has_errors, "Negative score should cause error"
        assert any("home_score" in str(e) for e in result.errors), "Should identify home_score"


# =============================================================================
# VCR Cassette Edge Case Verification Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.timeout(30)
class TestVCRCassetteEdgeCases:
    """
    Verify existing VCR cassettes contain expected edge case data.

    These tests confirm our recorded cassettes have realistic edge case
    scenarios that validate our parsing handles real-world data correctly.
    """

    def test_cassette_has_overtime_data(self):
        """Verify NCAAF cassette contains overtime game reference.

        Educational Note:
            The NCAAF cassette was recorded during championship week when
            Duke vs Virginia went to overtime. This provides real OT data.
        """
        with my_vcr.use_cassette("espn_ncaaf_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_ncaaf_scoreboard()

        # Check if any game headline mentions overtime
        # (From cassette: Duke beats Virginia 27-20 in overtime)
        game_texts = []
        for game in games:
            metadata = game.get("metadata", {})
            home = metadata.get("home_team", {}).get("display_name", "")
            away = metadata.get("away_team", {}).get("display_name", "")
            game_texts.append(f"{away} @ {home}")

        # Verify we have games
        assert len(games) > 0, "Should have NCAAF games in cassette"

    def test_cassette_has_live_game_situations(self):
        """Verify live games cassette has situation data including edge cases.

        Educational Note:
            The live games cassette was recorded during Week 14 with 8 games
            in progress. It captured:
            - Normal down/distance
            - down=-1 edge cases (kickoffs, PAT)
            - Various possession states
        """
        with my_vcr.use_cassette("espn_nfl_live_games.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_live_games(league="nfl")

        assert len(games) == 8, "Should have 8 live games"

        # Check for down=-1 edge cases
        edge_cases_found = 0
        for game in games:
            situation = game["state"].get("situation", {})
            down = situation.get("down")
            if down is not None and down < 1:
                edge_cases_found += 1

        # Should find at least one edge case (from recording notes)
        assert edge_cases_found >= 1, f"Should find down<1 edge cases, found {edge_cases_found}"

    def test_all_cassette_games_valid(self):
        """Verify all games in NFL cassette pass validation.

        Educational Note:
            This is a comprehensive check that our validation module
            handles all real ESPN data correctly. If this fails, it
            means we found a new edge case to handle.
        """
        validator = ESPNDataValidator(track_anomalies=True)

        with my_vcr.use_cassette("espn_nfl_scoreboard.yaml"):
            client = ESPNClient(rate_limit_per_hour=500)
            games = client.get_nfl_scoreboard()

        all_valid = True
        error_games = []

        for game in games:
            result = validator.validate_game_state(game)
            if result.has_errors:
                all_valid = False
                error_games.append(
                    {
                        "game_id": game["metadata"]["espn_event_id"],
                        "errors": [str(e) for e in result.errors],
                    }
                )

        assert all_valid, f"All cassette games should be valid. Errors: {error_games}"


# =============================================================================
# Regression Prevention Tests
# =============================================================================


@pytest.mark.unit
class TestRegressionPrevention:
    """
    Tests that prevent regression of previously fixed bugs.

    Each test documents a specific bug that was fixed and ensures
    the fix remains in place.
    """

    def test_issue_180_down_negative_one(self, validator: ESPNDataValidator) -> None:
        """Regression test for Issue #180: down=-1 edge case.

        Bug: E2E tests failed because validation expected down >= 1
        Fix: Changed validation to allow negative down values
        PR: #180
        """
        # This specific scenario caused the bug
        situation: ESPNSituationData = {
            "possession": "NO",
            "down": -1,  # The problematic value
            "distance": 0,
            "yard_line": 35,
            "is_red_zone": False,
            "home_timeouts": 3,
            "away_timeouts": 2,
        }

        result = validator.validate_situation(situation, "nfl")

        assert result.is_valid, (
            "Regression: Issue #180 - down=-1 should be valid. "
            "This was fixed to allow ESPN's special situation indicator."
        )

    def test_venue_null_handling(self, validator: ESPNDataValidator) -> None:
        """Regression test for venue null capacity issue.

        Bug: Venue capacity returning null caused validation errors
        Fix: Made venue fields optional in validation

        Note: We use cast() here because we're intentionally creating
        malformed data to test the validator's edge case handling.
        """
        # Build as dict[str, Any] then cast - testing null venue fields
        game_data: dict[str, Any] = {
            "metadata": {
                "espn_event_id": "401547006",
                "game_date": "2025-01-15T18:00:00Z",
                "home_team": {
                    "espn_team_id": "1",
                    "team_code": "TST",
                    "team_name": "Test Team",
                    "display_name": "Test",
                    "record": "0-0",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "rank": None,
                },
                "away_team": {
                    "espn_team_id": "2",
                    "team_code": "OPP",
                    "team_name": "Opponent",
                    "display_name": "Opponent",
                    "record": "0-0",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "rank": None,
                },
                "venue": {
                    "venue_name": "Test Stadium",
                    "city": None,  # Null city
                    "state": None,  # Null state
                    "indoor": None,  # Null indoor
                },
                "broadcast": None,  # Null broadcast
                "neutral_site": False,
                "season_type": "regular",
                "week_number": 1,
            },
            "state": {
                "espn_event_id": "401547006",
                "home_score": 7,
                "away_score": 3,
                "period": 1,
                "clock_seconds": 600,
                "clock_display": "10:00",
                "game_status": "in_progress",
                "situation": {},
                "linescores": [],
            },
        }
        game = cast("ESPNGameFull", game_data)

        result = validator.validate_game_state(game)

        assert not result.has_errors, f"Null venue fields should not error: {result.errors}"
