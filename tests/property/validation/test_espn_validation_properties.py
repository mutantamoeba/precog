"""
Property-Based Tests for ESPN Data Validation.

Uses Hypothesis to test validation invariants that should hold for any valid input.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/property/validation/test_espn_validation_properties.py -v -m property
"""

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)

# =============================================================================
# Custom Strategies
# =============================================================================


# Valid score strategy (non-negative integers)
score_strategy = st.integers(min_value=0, max_value=200)

# Invalid score strategy (negative integers)
negative_score_strategy = st.integers(min_value=-1000, max_value=-1)

# Valid clock strategy (0 to max period length with Decimal precision)
clock_strategy = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1500"),
    places=1,
    allow_nan=False,
    allow_infinity=False,
)

# Valid period strategy
period_strategy = st.integers(min_value=1, max_value=8)

# League strategy
league_strategy = st.sampled_from(["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"])

# Down strategy (1-4 or -1)
down_strategy = st.sampled_from([1, 2, 3, 4, -1])

# Invalid down strategy
invalid_down_strategy = st.sampled_from([0, 5, 6, -2, -3, 100])

# Distance strategy (positive or -1)
distance_strategy = st.integers(min_value=1, max_value=99) | st.just(-1)


# =============================================================================
# Helper Functions
# =============================================================================


def create_validator(strict_mode: bool = False) -> ESPNDataValidator:
    """Create a validator instance (avoids fixture issues with Hypothesis)."""
    return ESPNDataValidator(strict_mode=strict_mode)


# =============================================================================
# Property Tests: ValidationResult Invariants
# =============================================================================


@pytest.mark.property
class TestValidationResultProperties:
    """Property tests for ValidationResult invariants."""

    @given(
        num_errors=st.integers(min_value=0, max_value=10),
        num_warnings=st.integers(min_value=0, max_value=10),
        num_infos=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=50)
    def test_issue_counts_match(self, num_errors: int, num_warnings: int, num_infos: int) -> None:
        """Issue counts should match added issues."""
        result = ValidationResult(game_id="test123")

        for i in range(num_errors):
            result.add_error(f"field{i}", f"error{i}")
        for i in range(num_warnings):
            result.add_warning(f"field{i}", f"warning{i}")
        for i in range(num_infos):
            result.add_info(f"field{i}", f"info{i}")

        assert len(result.errors) == num_errors
        assert len(result.warnings) == num_warnings
        assert len(result.issues) == num_errors + num_warnings + num_infos

    @given(num_errors=st.integers(min_value=0, max_value=10))
    @settings(max_examples=30)
    def test_is_valid_iff_no_errors(self, num_errors: int) -> None:
        """Result is valid if and only if no errors."""
        result = ValidationResult()

        for i in range(num_errors):
            result.add_error(f"field{i}", f"error{i}")

        # Add some warnings (shouldn't affect validity)
        for i in range(3):
            result.add_warning(f"wfield{i}", f"warning{i}")

        assert result.is_valid == (num_errors == 0)
        assert result.has_errors == (num_errors > 0)

    @given(game_id=st.text(min_size=1, max_size=20))
    @settings(max_examples=30)
    def test_game_id_preserved(self, game_id: str) -> None:
        """Game ID should be preserved in result."""
        result = ValidationResult(game_id=game_id)
        assert result.game_id == game_id


# =============================================================================
# Property Tests: Score Validation Invariants
# =============================================================================


@pytest.mark.property
class TestScoreValidationProperties:
    """Property tests for score validation invariants."""

    @given(home_score=score_strategy, away_score=score_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_scores_always_pass(self, home_score: int, away_score: int) -> None:
        """Non-negative scores should always pass validation."""
        validator = create_validator()
        result = validator.validate_score(home_score, away_score)

        assert result.is_valid
        assert not result.has_errors

    @given(home_score=negative_score_strategy, away_score=score_strategy)
    @settings(max_examples=30)
    def test_negative_home_score_always_fails(self, home_score: int, away_score: int) -> None:
        """Negative home score should always fail."""
        validator = create_validator()
        result = validator.validate_score(home_score, away_score)

        assert not result.is_valid
        assert any("home_score" in e.field for e in result.errors)

    @given(home_score=score_strategy, away_score=negative_score_strategy)
    @settings(max_examples=30)
    def test_negative_away_score_always_fails(self, home_score: int, away_score: int) -> None:
        """Negative away score should always fail."""
        validator = create_validator()
        result = validator.validate_score(home_score, away_score)

        assert not result.is_valid
        assert any("away_score" in e.field for e in result.errors)

    @given(
        current_home=score_strategy,
        current_away=score_strategy,
        delta_home=st.integers(min_value=0, max_value=50),
        delta_away=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_score_increase_no_warning(
        self, current_home: int, current_away: int, delta_home: int, delta_away: int
    ) -> None:
        """Score increase should not generate warnings."""
        validator = create_validator()

        previous_home = current_home
        previous_away = current_away
        new_home = current_home + delta_home
        new_away = current_away + delta_away

        result = validator.validate_score(
            home_score=new_home,
            away_score=new_away,
            previous_home=previous_home,
            previous_away=previous_away,
        )

        # No decrease warnings
        assert not any("decreased" in w.message for w in result.warnings)


# =============================================================================
# Property Tests: Clock Validation Invariants
# =============================================================================


@pytest.mark.property
class TestClockValidationProperties:
    """Property tests for clock validation invariants."""

    @given(
        clock_seconds=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("600"),
            places=1,
            allow_nan=False,
            allow_infinity=False,
        ),
        period=period_strategy,
        league=league_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_clock_within_bounds(
        self, clock_seconds: Decimal, period: int, league: str
    ) -> None:
        """Clock within period bounds should be valid."""
        validator = create_validator()
        result = validator.validate_clock(clock_seconds, period, league)

        # Should be valid (no errors) when clock is within bounds
        assert result.is_valid

    @given(
        negative_clock=st.decimals(
            min_value=Decimal("-1000"),
            max_value=Decimal("-0.1"),
            places=1,
            allow_nan=False,
            allow_infinity=False,
        ),
        period=period_strategy,
        league=league_strategy,
    )
    @settings(max_examples=30)
    def test_negative_clock_always_fails(
        self, negative_clock: Decimal, period: int, league: str
    ) -> None:
        """Negative clock should always fail."""
        validator = create_validator()
        result = validator.validate_clock(negative_clock, period, league)

        assert not result.is_valid
        assert result.has_errors

    @given(
        negative_period=st.integers(min_value=-100, max_value=-1),
        league=league_strategy,
    )
    @settings(max_examples=30)
    def test_negative_period_always_fails(self, negative_period: int, league: str) -> None:
        """Negative period should always fail."""
        validator = create_validator()
        result = validator.validate_clock(
            clock_seconds=Decimal("450"), period=negative_period, league=league
        )

        assert not result.is_valid
        assert result.has_errors


# =============================================================================
# Property Tests: Situation Validation Invariants
# =============================================================================


@pytest.mark.property
class TestSituationValidationProperties:
    """Property tests for situation validation invariants."""

    @given(down=down_strategy, distance=distance_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_football_situation(self, down: int, distance: int) -> None:
        """Valid down/distance should pass for football sports."""
        validator = create_validator()

        for league in ["nfl", "ncaaf"]:
            result = validator.validate_situation(
                situation={"down": down, "distance": distance},
                league=league,
            )
            # Valid downs (1-4 or -1) with valid distance should not error
            assert result.is_valid

    @given(down=invalid_down_strategy)
    @settings(max_examples=30)
    def test_invalid_down_warns(self, down: int) -> None:
        """Invalid down should generate warning."""
        validator = create_validator()

        result = validator.validate_situation(
            situation={"down": down, "distance": 10},
            league="nfl",
        )

        assert result.has_warnings
        assert any("down" in w.field for w in result.warnings)

    @given(
        negative_distance=st.integers(min_value=-100, max_value=-2),  # Exclude -1
    )
    @settings(max_examples=30)
    def test_invalid_distance_errors(self, negative_distance: int) -> None:
        """Negative distance (except -1) should error."""
        validator = create_validator()

        result = validator.validate_situation(
            situation={"down": 2, "distance": negative_distance},
            league="nfl",
        )

        assert not result.is_valid
        assert result.has_errors

    @given(fouls=st.integers(min_value=0, max_value=20))
    @settings(max_examples=30)
    def test_valid_basketball_fouls(self, fouls: int) -> None:
        """Non-negative fouls should be valid for basketball."""
        validator = create_validator()

        for league in ["nba", "ncaab", "wnba"]:
            result = validator.validate_situation(
                situation={"fouls": fouls},
                league=league,
            )
            assert result.is_valid


# =============================================================================
# Property Tests: Anomaly Tracking Invariants
# =============================================================================


@pytest.mark.property
class TestAnomalyTrackingProperties:
    """Property tests for anomaly tracking invariants."""

    @given(num_validations=st.integers(min_value=1, max_value=10))
    @settings(max_examples=30)
    def test_anomaly_count_accumulates(self, num_validations: int) -> None:
        """Anomaly counts should accumulate across validations."""
        validator = create_validator()

        game_state = {
            "metadata": {"espn_event_id": "test123", "league": "nfl"},
            "state": {"home_score": -1, "away_score": 0, "period": 1},
        }

        for _ in range(num_validations):
            validator.validate_game_state(game_state)

        count = validator.get_anomaly_count("test123")
        # At least one anomaly per validation
        assert count >= num_validations

    @given(
        game_ids=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Nd", "Lu")),
                min_size=5,
                max_size=10,
            ),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_reset_clears_all_counts(self, game_ids: list[str]) -> None:
        """Reset should clear counts for all games."""
        validator = create_validator()

        # Add anomalies for multiple games
        for game_id in game_ids:
            game_state = {
                "metadata": {"espn_event_id": game_id, "league": "nfl"},
                "state": {"home_score": -1, "away_score": 0, "period": 1},
            }
            validator.validate_game_state(game_state)

        # Reset
        validator.reset_anomaly_counts()

        # All counts should be zero
        for game_id in game_ids:
            assert validator.get_anomaly_count(game_id) == 0


# =============================================================================
# Property Tests: ValidationIssue Invariants
# =============================================================================


@pytest.mark.property
class TestValidationIssueProperties:
    """Property tests for ValidationIssue invariants."""

    @given(
        level=st.sampled_from(list(ValidationLevel)),
        field_name=st.text(min_size=1, max_size=20),
        message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=30)
    def test_issue_fields_preserved(
        self, level: ValidationLevel, field_name: str, message: str
    ) -> None:
        """Issue fields should be preserved correctly."""
        issue = ValidationIssue(
            level=level,
            field=field_name,
            message=message,
        )

        assert issue.level == level
        assert issue.field == field_name
        assert issue.message == message

    @given(
        level=st.sampled_from(list(ValidationLevel)),
        field_name=st.text(min_size=1, max_size=20),
        message=st.text(min_size=1, max_size=100),
        value=st.integers(),
        expected=st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=30)
    def test_issue_str_contains_fields(
        self,
        level: ValidationLevel,
        field_name: str,
        message: str,
        value: int,
        expected: str,
    ) -> None:
        """Issue string representation should contain key fields."""
        issue = ValidationIssue(
            level=level,
            field=field_name,
            message=message,
            value=value,
            expected=expected,
        )

        issue_str = str(issue)
        assert level.value.upper() in issue_str
        assert field_name in issue_str
        assert message in issue_str


# =============================================================================
# Property Tests: Idempotency and Determinism
# =============================================================================


@pytest.mark.property
class TestValidationDeterminism:
    """Property tests for validation determinism."""

    @given(
        home_score=score_strategy,
        away_score=score_strategy,
    )
    @settings(max_examples=30)
    def test_score_validation_deterministic(self, home_score: int, away_score: int) -> None:
        """Same input should produce same validation result."""
        validator1 = create_validator()
        validator2 = create_validator()

        result1 = validator1.validate_score(home_score, away_score)
        result2 = validator2.validate_score(home_score, away_score)

        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)
        assert len(result1.warnings) == len(result2.warnings)

    @given(
        clock=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("900"),
            places=1,
            allow_nan=False,
            allow_infinity=False,
        ),
        period=period_strategy,
        league=league_strategy,
    )
    @settings(max_examples=30)
    def test_clock_validation_deterministic(self, clock: Decimal, period: int, league: str) -> None:
        """Same clock input should produce same result."""
        validator1 = create_validator()
        validator2 = create_validator()

        result1 = validator1.validate_clock(clock, period, league)
        result2 = validator2.validate_clock(clock, period, league)

        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)
