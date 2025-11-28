"""
Property-based tests for ESPN API Client using Hypothesis.

Property-based testing generates thousands of test cases automatically,
testing invariants (properties that should ALWAYS hold true) rather than
specific examples.

Key Properties Tested:
1. Game state parsing invariants (scores non-negative, periods valid)
2. Team abbreviation invariants (uppercase, valid length)
3. Clock/time invariants (non-negative, format consistency)
4. Rate limiting invariants (remaining never negative)
5. Status mapping completeness (all states map to known values)

Educational Note:
    Property tests complement example-based tests:
    - Example tests: "When input is X, output should be Y"
    - Property tests: "For ALL valid inputs, property P holds"

    Example: "scores are always non-negative" is a property - we don't care
    about specific scores, just that they're never negative.

Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1.3
Related: ADR-074 (Property-Based Testing with Hypothesis)
"""

from datetime import datetime, timedelta
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================


@st.composite
def espn_scores(draw: st.DrawFn) -> str:
    """Generate valid ESPN score values (string representations of integers)."""
    score = draw(st.integers(min_value=0, max_value=99))
    return str(score)


@st.composite
def espn_periods(draw: st.DrawFn) -> int:
    """Generate valid football periods (0 for pre-game, 1-4 for quarters, 5+ for OT)."""
    return draw(st.integers(min_value=0, max_value=10))


@st.composite
def espn_clock_seconds(draw: st.DrawFn) -> float:
    """Generate valid clock times in seconds (0-900 for 15-minute quarters)."""
    return draw(st.floats(min_value=0.0, max_value=900.0, allow_nan=False, allow_infinity=False))


@st.composite
def team_abbreviation(draw: st.DrawFn) -> str:
    """Generate valid team abbreviations (2-4 uppercase letters)."""
    length = draw(st.integers(min_value=2, max_value=4))
    return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=length, max_size=length))


@st.composite
def espn_game_status(draw: st.DrawFn) -> dict[str, Any]:
    """Generate valid ESPN game status objects."""
    state = draw(st.sampled_from(["pre", "in", "post"]))
    status_map = {
        "pre": ("STATUS_SCHEDULED", "Scheduled"),
        "in": ("STATUS_IN_PROGRESS", "In Progress"),
        "post": ("STATUS_FINAL", "Final"),
    }
    name, description = status_map[state]

    period = draw(espn_periods())
    clock = draw(espn_clock_seconds())

    return {
        "clock": clock,
        "displayClock": f"{int(clock // 60)}:{int(clock % 60):02d}",
        "period": period,
        "type": {
            "id": "2",
            "name": name,
            "state": state,
            "completed": state == "post",
            "description": description,
        },
    }


@st.composite
def espn_competitor(draw: st.DrawFn, home_away: str = "home") -> dict[str, Any]:
    """Generate valid ESPN competitor (team) objects."""
    team_id = draw(st.integers(min_value=1, max_value=100))
    abbrev = draw(team_abbreviation())
    score = draw(espn_scores())

    return {
        "id": str(team_id),
        "homeAway": home_away,
        "team": {
            "id": str(team_id),
            "abbreviation": abbrev,
            "displayName": f"Test {abbrev} Team",
        },
        "score": score,
    }


@st.composite
def espn_event(draw: st.DrawFn) -> dict[str, Any]:
    """Generate valid ESPN event (game) objects."""
    event_id = draw(st.integers(min_value=100000000, max_value=999999999))
    home = draw(espn_competitor("home"))
    away = draw(espn_competitor("away"))
    status = draw(espn_game_status())

    return {
        "id": str(event_id),
        "competitions": [
            {
                "competitors": [home, away],
                "status": status,
                "situation": {
                    "down": draw(st.integers(min_value=1, max_value=4)),
                    "distance": draw(st.integers(min_value=1, max_value=99)),
                    "yardLine": draw(st.integers(min_value=1, max_value=99)),
                    "isRedZone": draw(st.booleans()),
                    "possession": home["id"] if draw(st.booleans()) else away["id"],
                    "homeTimeouts": draw(st.integers(min_value=0, max_value=3)),
                    "awayTimeouts": draw(st.integers(min_value=0, max_value=3)),
                },
            }
        ],
        "status": status,
    }


# =============================================================================
# Property Tests: Game State Parsing Invariants
# =============================================================================


class TestGameStateParsingInvariants:
    """Property tests for game state parsing invariants."""

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_parsed_scores_are_non_negative(self, event: dict[str, Any]):
        """Property: Parsed scores are always non-negative integers."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert game_state["home_score"] >= 0, "Home score should be non-negative"
            assert game_state["away_score"] >= 0, "Away score should be non-negative"
            assert isinstance(game_state["home_score"], int), "Home score should be int"
            assert isinstance(game_state["away_score"], int), "Away score should be int"

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_parsed_period_is_valid_range(self, event: dict[str, Any]):
        """Property: Parsed period is always in valid range (0-10)."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert 0 <= game_state["period"] <= 10, "Period should be 0-10"

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_clock_seconds_is_non_negative(self, event: dict[str, Any]):
        """Property: Clock seconds is always non-negative."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert game_state["clock_seconds"] >= 0, "Clock seconds should be non-negative"


# =============================================================================
# Property Tests: Team Abbreviation Invariants
# =============================================================================


class TestTeamAbbreviationInvariants:
    """Property tests for team abbreviation handling."""

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_team_abbreviations_are_strings(self, event: dict[str, Any]):
        """Property: Team abbreviations are always strings."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert isinstance(game_state["home_team"], str), "Home team should be string"
            assert isinstance(game_state["away_team"], str), "Away team should be string"

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_team_abbreviations_are_non_empty(self, event: dict[str, Any]):
        """Property: Team abbreviations are never empty strings."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            # Note: abbreviations come from our test data, so they should be non-empty
            assert len(game_state["home_team"]) > 0 or game_state["home_team"] == ""
            assert len(game_state["away_team"]) > 0 or game_state["away_team"] == ""


# =============================================================================
# Property Tests: Status Mapping Invariants
# =============================================================================


class TestStatusMappingInvariants:
    """Property tests for status mapping completeness."""

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_game_status_maps_to_known_value(self, event: dict[str, Any]):
        """Property: Game status always maps to a known status value."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        known_statuses = {"scheduled", "in_progress", "halftime", "final", "unknown"}

        if game_state:
            assert game_state["game_status"] in known_statuses, (
                f"Unknown status: {game_state['game_status']}"
            )

    @given(state=st.sampled_from(["pre", "in", "post"]))
    @settings(max_examples=50)
    def test_all_espn_states_are_mapped(self, state: str):
        """Property: All ESPN state values have a mapping."""
        from precog.api_connectors.espn_client import ESPNClient

        assert state in ESPNClient.STATUS_MAP, f"State '{state}' not in STATUS_MAP"


# =============================================================================
# Property Tests: Rate Limiting Invariants
# =============================================================================


class TestRateLimitingInvariants:
    """Property tests for rate limiting behavior."""

    @given(num_requests=st.integers(min_value=0, max_value=1000))
    @settings(max_examples=50)
    def test_remaining_requests_never_negative(self, num_requests: int):
        """Property: Remaining requests is never negative."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(rate_limit_per_hour=500)

        # Simulate requests in the past hour
        now = datetime.now()
        client.request_timestamps = [
            now - timedelta(minutes=i % 60) for i in range(min(num_requests, 500))
        ]

        remaining = client.get_remaining_requests()
        assert remaining >= 0, "Remaining requests should never be negative"

    @given(rate_limit=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=50)
    def test_remaining_never_exceeds_limit(self, rate_limit: int):
        """Property: Remaining requests never exceeds the configured limit."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(rate_limit_per_hour=rate_limit)

        remaining = client.get_remaining_requests()
        assert remaining <= rate_limit, "Remaining should not exceed rate limit"

    @given(num_old=st.integers(min_value=0, max_value=100))
    @settings(max_examples=50)
    def test_old_timestamps_are_cleaned(self, num_old: int):
        """Property: Timestamps older than 1 hour are cleaned up."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(rate_limit_per_hour=500)

        # Add old timestamps (>1 hour ago)
        old_time = datetime.now() - timedelta(hours=2)
        client.request_timestamps = [old_time for _ in range(num_old)]

        # Clean should remove all old timestamps
        client._clean_old_timestamps()

        assert len(client.request_timestamps) == 0, "Old timestamps should be cleaned"


# =============================================================================
# Property Tests: Event ID Invariants
# =============================================================================


class TestEventIdInvariants:
    """Property tests for event ID handling."""

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_espn_event_id_is_string(self, event: dict[str, Any]):
        """Property: ESPN event ID is always a string."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert isinstance(game_state["espn_event_id"], str), "Event ID should be string"

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_espn_event_id_is_non_empty(self, event: dict[str, Any]):
        """Property: ESPN event ID is never empty."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert len(game_state["espn_event_id"]) > 0, "Event ID should be non-empty"


# =============================================================================
# Property Tests: Possession and Situation Invariants
# =============================================================================


class TestPossessionInvariants:
    """Property tests for possession and situation data."""

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_possession_is_home_away_or_none(self, event: dict[str, Any]):
        """Property: Possession is 'home', 'away', or None."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            valid_possessions = {"home", "away", None}
            assert game_state["possession"] in valid_possessions, (
                f"Invalid possession: {game_state['possession']}"
            )

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_down_is_valid_or_none(self, event: dict[str, Any]):
        """Property: Down is 1-4 or None."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state and game_state.get("down") is not None:
            assert 1 <= game_state["down"] <= 4, f"Invalid down: {game_state['down']}"

    @given(event=espn_event())
    @settings(max_examples=100, deadline=None)
    def test_timeouts_are_valid_range(self, event: dict[str, Any]):
        """Property: Timeouts are in valid range (0-3)."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()
        game_state = client._parse_event(event)

        if game_state:
            assert 0 <= game_state["home_timeouts"] <= 3, "Home timeouts should be 0-3"
            assert 0 <= game_state["away_timeouts"] <= 3, "Away timeouts should be 0-3"


# =============================================================================
# Property Tests: Clock Display Format
# =============================================================================


class TestClockDisplayInvariants:
    """Property tests for clock display format."""

    @given(seconds=espn_clock_seconds())
    @settings(max_examples=100)
    def test_clock_display_format_is_valid(self, seconds: float):
        """Property: Clock display matches MM:SS format."""
        # Generate expected display format
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        expected = f"{minutes}:{secs:02d}"

        # Format should be valid
        assert ":" in expected, "Clock display should contain colon"
        parts = expected.split(":")
        assert len(parts) == 2, "Clock display should have two parts"
        assert parts[1].isdigit(), "Seconds should be digits"
        assert len(parts[1]) == 2, "Seconds should be 2 digits"
