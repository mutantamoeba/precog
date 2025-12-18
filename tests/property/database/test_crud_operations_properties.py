"""
Property-based tests for crud_operations module.

Tests mathematical properties and invariants of state change detection
using Hypothesis.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
Related Requirements: REQ-DATA-001 (Game State Data Collection)
Related Issue: Issue #234 (State Change Detection)
"""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from precog.database.crud_operations import game_state_changed

pytestmark = [pytest.mark.property]


# =============================================================================
# Custom Strategies
# =============================================================================

# Score values (realistic range for most sports)
score_strategy = st.integers(min_value=0, max_value=200)

# Period values (quarters, halves, overtime periods)
period_strategy = st.integers(min_value=0, max_value=10)

# Game status values
game_status_strategy = st.sampled_from(["pre", "in_progress", "halftime", "final"])

# Situation keys that matter for comparison
situation_keys = ["possession", "down", "distance", "yard_line", "is_red_zone"]

# NFL teams for possession
nfl_teams = st.sampled_from(["KC", "BUF", "SF", "PHI", "DET", "DAL", "MIA", "CIN", None])

# Down values (1-4 for football)
down_strategy = st.integers(min_value=1, max_value=4) | st.none()

# Distance values
distance_strategy = st.integers(min_value=1, max_value=99) | st.none()

# Yard line values
yard_line_strategy = st.integers(min_value=0, max_value=100) | st.none()

# Red zone boolean
red_zone_strategy = st.booleans() | st.none()


# Generate situation dict
@st.composite
def situation_strategy(draw: st.DrawFn) -> dict | None:
    """Generate a realistic situation dictionary or None."""
    if draw(st.booleans()):
        return None
    return {
        "possession": draw(nfl_teams),
        "down": draw(down_strategy),
        "distance": draw(distance_strategy),
        "yard_line": draw(yard_line_strategy),
        "is_red_zone": draw(red_zone_strategy),
    }


# Generate current state dict
@st.composite
def current_state_strategy(draw: st.DrawFn) -> dict | None:
    """Generate a current state dictionary or None."""
    if draw(st.booleans()):
        return None
    return {
        "home_score": draw(score_strategy),
        "away_score": draw(score_strategy),
        "period": draw(period_strategy),
        "game_status": draw(game_status_strategy),
        "situation": draw(situation_strategy()),
        # Include clock fields that should be ignored
        "clock_seconds": draw(st.integers(min_value=0, max_value=900)),
        "clock_display": draw(st.text(min_size=4, max_size=10)),
    }


# =============================================================================
# Property Tests: Reflexivity and Determinism
# =============================================================================


class TestGameStateChangedReflexivity:
    """Property tests for reflexive comparison (same state = no change)."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
    )
    @settings(max_examples=100)
    def test_same_core_state_returns_false(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
    ) -> None:
        """Same core state should always return False (no change)."""
        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
        }

        result = game_state_changed(
            current, home_score, away_score, period, game_status, situation=None
        )

        assert result is False

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
        situation=situation_strategy(),
    )
    @settings(max_examples=100)
    def test_same_full_state_returns_false(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
        situation: dict | None,
    ) -> None:
        """Same full state (including situation) should return False."""
        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
            "situation": situation,
        }

        result = game_state_changed(current, home_score, away_score, period, game_status, situation)

        assert result is False

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
    )
    @settings(max_examples=50)
    def test_deterministic_comparison(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
    ) -> None:
        """Same inputs should always produce same output (deterministic)."""
        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
        }

        result1 = game_state_changed(current, home_score, away_score, period, game_status)
        result2 = game_state_changed(current, home_score, away_score, period, game_status)

        assert result1 == result2


# =============================================================================
# Property Tests: None Current State
# =============================================================================


class TestGameStateChangedNoneCurrentState:
    """Property tests for None current state (new game)."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
        situation=situation_strategy(),
    )
    @settings(max_examples=100)
    def test_none_current_always_returns_true(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
        situation: dict | None,
    ) -> None:
        """When current state is None, should always return True (new game)."""
        result = game_state_changed(None, home_score, away_score, period, game_status, situation)

        assert result is True


# =============================================================================
# Property Tests: Score Changes
# =============================================================================


class TestGameStateChangedScoreChanges:
    """Property tests for score change detection."""

    @given(
        current_home=score_strategy,
        new_home=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
    )
    @settings(max_examples=100)
    def test_home_score_change_triggers_update(
        self,
        current_home: int,
        new_home: int,
        away_score: int,
        period: int,
        game_status: str,
    ) -> None:
        """Different home score should return True."""
        assume(current_home != new_home)

        current = {
            "home_score": current_home,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
        }

        result = game_state_changed(current, new_home, away_score, period, game_status)

        assert result is True

    @given(
        home_score=score_strategy,
        current_away=score_strategy,
        new_away=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
    )
    @settings(max_examples=100)
    def test_away_score_change_triggers_update(
        self,
        home_score: int,
        current_away: int,
        new_away: int,
        period: int,
        game_status: str,
    ) -> None:
        """Different away score should return True."""
        assume(current_away != new_away)

        current = {
            "home_score": home_score,
            "away_score": current_away,
            "period": period,
            "game_status": game_status,
        }

        result = game_state_changed(current, home_score, new_away, period, game_status)

        assert result is True


# =============================================================================
# Property Tests: Period Changes
# =============================================================================


class TestGameStateChangedPeriodChanges:
    """Property tests for period change detection."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        current_period=period_strategy,
        new_period=period_strategy,
        game_status=game_status_strategy,
    )
    @settings(max_examples=100)
    def test_period_change_triggers_update(
        self,
        home_score: int,
        away_score: int,
        current_period: int,
        new_period: int,
        game_status: str,
    ) -> None:
        """Different period should return True."""
        assume(current_period != new_period)

        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": current_period,
            "game_status": game_status,
        }

        result = game_state_changed(current, home_score, away_score, new_period, game_status)

        assert result is True


# =============================================================================
# Property Tests: Status Changes
# =============================================================================


class TestGameStateChangedStatusChanges:
    """Property tests for status change detection."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        current_status=game_status_strategy,
        new_status=game_status_strategy,
    )
    @settings(max_examples=100)
    def test_status_change_triggers_update(
        self,
        home_score: int,
        away_score: int,
        period: int,
        current_status: str,
        new_status: str,
    ) -> None:
        """Different game status should return True."""
        assume(current_status != new_status)

        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": current_status,
        }

        result = game_state_changed(current, home_score, away_score, period, new_status)

        assert result is True


# =============================================================================
# Property Tests: Clock Invariance
# =============================================================================


class TestGameStateChangedClockInvariance:
    """Property tests ensuring clock changes don't trigger updates."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
        clock1=st.integers(min_value=0, max_value=900),
        clock2=st.integers(min_value=0, max_value=900),
    )
    @settings(max_examples=100)
    def test_clock_changes_ignored(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
        clock1: int,
        clock2: int,
    ) -> None:
        """Clock changes should NOT trigger state change."""
        # Current state has clock1
        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
            "clock_seconds": clock1,
            "clock_display": f"{clock1 // 60}:{clock1 % 60:02d}",
        }

        # Compare with same core state but different clock (implicit)
        result = game_state_changed(current, home_score, away_score, period, game_status)

        # Clock is not compared, so should return False
        assert result is False


# =============================================================================
# Property Tests: Situation Changes
# =============================================================================


class TestGameStateChangedSituationChanges:
    """Property tests for situation change detection."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
        possession1=nfl_teams,
        possession2=nfl_teams,
    )
    @settings(max_examples=100)
    def test_possession_change_triggers_update(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
        possession1: str | None,
        possession2: str | None,
    ) -> None:
        """Different possession should return True."""
        assume(possession1 != possession2)

        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
            "situation": {"possession": possession1},
        }

        new_situation = {"possession": possession2}

        result = game_state_changed(
            current, home_score, away_score, period, game_status, new_situation
        )

        assert result is True

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
        down1=down_strategy,
        down2=down_strategy,
    )
    @settings(max_examples=100)
    def test_down_change_triggers_update(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
        down1: int | None,
        down2: int | None,
    ) -> None:
        """Different down should return True."""
        assume(down1 != down2)

        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
            "situation": {"down": down1},
        }

        new_situation = {"down": down2}

        result = game_state_changed(
            current, home_score, away_score, period, game_status, new_situation
        )

        assert result is True

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
        period=period_strategy,
        game_status=game_status_strategy,
    )
    @settings(max_examples=50)
    def test_none_situation_ignores_comparison(
        self,
        home_score: int,
        away_score: int,
        period: int,
        game_status: str,
    ) -> None:
        """When new situation is None, situation comparison is skipped."""
        current = {
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "game_status": game_status,
            "situation": {"possession": "KC", "down": 1},
        }

        # None situation = don't compare situations
        result = game_state_changed(
            current, home_score, away_score, period, game_status, situation=None
        )

        assert result is False


# =============================================================================
# Property Tests: Return Type Invariants
# =============================================================================


class TestGameStateChangedReturnType:
    """Property tests for return type invariants."""

    @given(current=current_state_strategy())
    @settings(max_examples=100)
    def test_always_returns_boolean(self, current: dict | None) -> None:
        """Function should always return a boolean."""
        result = game_state_changed(
            current,
            home_score=10,
            away_score=7,
            period=2,
            game_status="in_progress",
        )

        assert isinstance(result, bool)
