"""
Unit tests for ESPN Data Validation module.

Tests comprehensive validation of ESPN game state data including:
- Score validation (non-negative, monotonic)
- Clock validation (Decimal precision, period bounds)
- Situation validation (down/distance rules by sport)
- Team/Venue validation (required fields, formats)

Reference: Issue #186 (P2-004: Data Quality Validation)
Related: src/precog/validation/espn_validation.py
"""

from decimal import Decimal

import pytest

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationResult,
    create_validator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> ESPNDataValidator:
    """Create a fresh validator for each test."""
    return ESPNDataValidator()


@pytest.fixture
def strict_validator() -> ESPNDataValidator:
    """Create a validator in strict mode."""
    return ESPNDataValidator(strict_mode=True)


@pytest.fixture
def valid_game_state() -> dict:
    """Create a valid ESPN game state for testing."""
    return {
        "metadata": {
            "espn_event_id": "401547389",
            "league": "nfl",
            "game_date": "2025-12-07T20:00:00Z",
            "home_team": {
                "espn_team_id": "12",
                "team_name": "Kansas City Chiefs",
                "team_code": "KC",
            },
            "away_team": {
                "espn_team_id": "33",
                "team_name": "Denver Broncos",
                "team_code": "DEN",
            },
            "venue": {
                "espn_venue_id": "3622",
                "venue_name": "Arrowhead Stadium",
                "city": "Kansas City",
                "state": "MO",
                "capacity": 76416,
            },
        },
        "state": {
            "home_score": 14,
            "away_score": 7,
            "period": 2,
            "clock_seconds": Decimal("450"),
            "clock_display": "7:30",
            "game_status": "in_progress",
            "situation": {
                "down": 2,
                "distance": 8,
                "possession": "KC",
                "yard_line": 35,
            },
        },
    }


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_empty_result_is_valid(self) -> None:
        """Empty result should be valid."""
        result = ValidationResult()
        assert result.is_valid
        assert not result.has_errors
        assert not result.has_warnings

    def test_add_error_makes_invalid(self) -> None:
        """Adding an error should make result invalid."""
        result = ValidationResult()
        result.add_error("field", "message")
        assert not result.is_valid
        assert result.has_errors
        assert len(result.errors) == 1

    def test_add_warning_stays_valid(self) -> None:
        """Adding a warning should not make result invalid."""
        result = ValidationResult()
        result.add_warning("field", "message")
        assert result.is_valid
        assert result.has_warnings
        assert len(result.warnings) == 1

    def test_add_info_stays_valid(self) -> None:
        """Adding info should not affect validity."""
        result = ValidationResult()
        result.add_info("field", "message")
        assert result.is_valid
        assert not result.has_errors
        assert not result.has_warnings

    def test_error_with_value_and_expected(self) -> None:
        """Error should store value and expected."""
        result = ValidationResult(game_id="test123")
        result.add_error("score", "Invalid", value=-1, expected=">=0")

        error = result.errors[0]
        assert error.field == "score"
        assert error.value == -1
        assert error.expected == ">=0"

    def test_game_id_preserved(self) -> None:
        """Game ID should be preserved in result."""
        result = ValidationResult(game_id="401547389")
        assert result.game_id == "401547389"


# =============================================================================
# Score Validation Tests
# =============================================================================


class TestScoreValidation:
    """Tests for score validation rules."""

    def test_valid_scores(self, validator: ESPNDataValidator) -> None:
        """Valid scores should pass validation."""
        result = validator.validate_score(21, 14)
        assert result.is_valid
        assert not result.has_errors

    def test_zero_scores_valid(self, validator: ESPNDataValidator) -> None:
        """Zero scores (start of game) should be valid."""
        result = validator.validate_score(0, 0)
        assert result.is_valid

    def test_negative_home_score_error(self, validator: ESPNDataValidator) -> None:
        """Negative home score should be an error."""
        result = validator.validate_score(-1, 7)
        assert not result.is_valid
        assert result.has_errors
        assert any("home_score" in e.field for e in result.errors)

    def test_negative_away_score_error(self, validator: ESPNDataValidator) -> None:
        """Negative away score should be an error."""
        result = validator.validate_score(14, -3)
        assert not result.is_valid
        assert result.has_errors
        assert any("away_score" in e.field for e in result.errors)

    def test_score_decrease_warning(self, validator: ESPNDataValidator) -> None:
        """Score decrease should be a warning (possible correction)."""
        result = validator.validate_score(
            home_score=14,
            away_score=7,
            previous_home=21,  # Score decreased from 21 to 14
            previous_away=7,
        )
        assert result.is_valid  # Warnings don't make invalid
        assert result.has_warnings
        assert any("decreased" in w.message for w in result.warnings)

    def test_score_increase_valid(self, validator: ESPNDataValidator) -> None:
        """Score increase should be valid."""
        result = validator.validate_score(
            home_score=21,
            away_score=14,
            previous_home=14,
            previous_away=7,
        )
        assert result.is_valid
        assert not result.has_warnings


# =============================================================================
# Clock Validation Tests
# =============================================================================


class TestClockValidation:
    """Tests for clock validation rules."""

    def test_valid_clock_nfl(self, validator: ESPNDataValidator) -> None:
        """Valid NFL clock should pass."""
        result = validator.validate_clock(
            clock_seconds=Decimal("450"),
            period=2,
            league="nfl",
        )
        assert result.is_valid

    def test_valid_clock_nba(self, validator: ESPNDataValidator) -> None:
        """Valid NBA clock should pass."""
        result = validator.validate_clock(
            clock_seconds=Decimal("360"),
            period=3,
            league="nba",
        )
        assert result.is_valid

    def test_negative_clock_error(self, validator: ESPNDataValidator) -> None:
        """Negative clock should be an error."""
        result = validator.validate_clock(
            clock_seconds=Decimal("-10"),
            period=2,
            league="nfl",
        )
        assert not result.is_valid
        assert result.has_errors

    def test_clock_exceeds_period_warning(self, validator: ESPNDataValidator) -> None:
        """Clock exceeding period length should be a warning."""
        # NFL period is 900 seconds (15 minutes)
        result = validator.validate_clock(
            clock_seconds=Decimal("1000"),
            period=1,
            league="nfl",
        )
        assert result.is_valid  # Warning only
        assert result.has_warnings
        assert any("exceeds" in w.message for w in result.warnings)

    def test_zero_period_info(self, validator: ESPNDataValidator) -> None:
        """Period 0 (pre-game) should log info."""
        result = validator.validate_clock(
            clock_seconds=Decimal("900"),
            period=0,
            league="nfl",
        )
        assert result.is_valid
        # Should have info about pre-game

    def test_negative_period_error(self, validator: ESPNDataValidator) -> None:
        """Negative period should be an error."""
        result = validator.validate_clock(
            clock_seconds=Decimal("450"),
            period=-1,
            league="nfl",
        )
        assert not result.is_valid
        assert result.has_errors

    def test_overtime_period_valid(self, validator: ESPNDataValidator) -> None:
        """Overtime period (5 for NFL) should be valid."""
        result = validator.validate_clock(
            clock_seconds=Decimal("600"),
            period=5,  # OT
            league="nfl",
        )
        assert result.is_valid

    def test_float_clock_converted_to_decimal(self, validator: ESPNDataValidator) -> None:
        """Float clock should be handled (converted to Decimal)."""
        result = validator.validate_clock(
            clock_seconds=450.5,  # type: ignore  # Testing float handling
            period=2,
            league="nfl",
        )
        assert result.is_valid


# =============================================================================
# Situation Validation Tests
# =============================================================================


class TestSituationValidation:
    """Tests for game situation validation rules."""

    def test_valid_football_situation(self, validator: ESPNDataValidator) -> None:
        """Valid football situation should pass."""
        result = validator.validate_situation(
            situation={"down": 3, "distance": 7, "possession": "KC"},
            league="nfl",
        )
        assert result.is_valid

    def test_down_minus_one_info(self, validator: ESPNDataValidator) -> None:
        """Down -1 (non-play) should log info, not error."""
        result = validator.validate_situation(
            situation={"down": -1, "distance": -1},
            league="nfl",
        )
        assert result.is_valid
        # Should have info about non-play situation

    def test_invalid_down_warning(self, validator: ESPNDataValidator) -> None:
        """Invalid down (not 1-4 or -1) should warn."""
        result = validator.validate_situation(
            situation={"down": 5, "distance": 10},
            league="nfl",
        )
        assert result.has_warnings
        assert any("down" in w.field for w in result.warnings)

    def test_negative_distance_error(self, validator: ESPNDataValidator) -> None:
        """Negative distance (except -1) should error."""
        result = validator.validate_situation(
            situation={"down": 2, "distance": -5},
            league="nfl",
        )
        assert not result.is_valid
        assert result.has_errors

    def test_distance_minus_one_info(self, validator: ESPNDataValidator) -> None:
        """Distance -1 (non-play) should log info."""
        result = validator.validate_situation(
            situation={"down": 1, "distance": -1},
            league="nfl",
        )
        assert result.is_valid

    def test_basketball_fouls_valid(self, validator: ESPNDataValidator) -> None:
        """Valid basketball fouls should pass."""
        result = validator.validate_situation(
            situation={"fouls": 4},
            league="nba",
        )
        assert result.is_valid

    def test_basketball_negative_fouls_error(self, validator: ESPNDataValidator) -> None:
        """Negative fouls should error."""
        result = validator.validate_situation(
            situation={"fouls": -1},
            league="nba",
        )
        assert not result.is_valid
        assert result.has_errors

    def test_empty_situation_valid(self, validator: ESPNDataValidator) -> None:
        """Empty situation should be valid."""
        result = validator.validate_situation(
            situation={},
            league="nfl",
        )
        assert result.is_valid

    def test_ncaaf_uses_football_rules(self, validator: ESPNDataValidator) -> None:
        """NCAAF should use football validation rules."""
        result = validator.validate_situation(
            situation={"down": 3, "distance": 5},
            league="ncaaf",
        )
        assert result.is_valid


# =============================================================================
# Full Game State Validation Tests
# =============================================================================


class TestFullGameStateValidation:
    """Tests for complete game state validation."""

    def test_valid_game_state(self, validator: ESPNDataValidator, valid_game_state: dict) -> None:
        """Valid game state should pass all checks."""
        result = validator.validate_game_state(valid_game_state)
        assert result.is_valid
        assert not result.has_errors

    def test_missing_espn_event_id_error(
        self, validator: ESPNDataValidator, valid_game_state: dict
    ) -> None:
        """Missing ESPN event ID should error."""
        del valid_game_state["metadata"]["espn_event_id"]
        result = validator.validate_game_state(valid_game_state)
        assert not result.is_valid
        assert any("espn_event_id" in e.field for e in result.errors)

    def test_missing_team_warning(
        self, validator: ESPNDataValidator, valid_game_state: dict
    ) -> None:
        """Missing team should warn."""
        del valid_game_state["metadata"]["home_team"]
        result = validator.validate_game_state(valid_game_state)
        assert result.has_warnings
        assert any("home_team" in w.field for w in result.warnings)

    def test_invalid_venue_capacity_warning(
        self, validator: ESPNDataValidator, valid_game_state: dict
    ) -> None:
        """Invalid venue capacity should warn."""
        valid_game_state["metadata"]["venue"]["capacity"] = -100
        result = validator.validate_game_state(valid_game_state)
        assert result.has_warnings
        assert any("capacity" in w.field for w in result.warnings)

    def test_game_id_in_result(self, validator: ESPNDataValidator, valid_game_state: dict) -> None:
        """Game ID should be preserved in result."""
        result = validator.validate_game_state(valid_game_state)
        assert result.game_id == "401547389"


# =============================================================================
# Anomaly Tracking Tests
# =============================================================================


class TestAnomalyTracking:
    """Tests for anomaly count tracking."""

    def test_anomalies_tracked(self, validator: ESPNDataValidator, valid_game_state: dict) -> None:
        """Anomalies should be tracked per game."""
        # Add an error
        valid_game_state["state"]["home_score"] = -1
        validator.validate_game_state(valid_game_state)

        count = validator.get_anomaly_count("401547389")
        assert count >= 1

    def test_multiple_validations_accumulate(
        self, validator: ESPNDataValidator, valid_game_state: dict
    ) -> None:
        """Multiple validations should accumulate counts."""
        valid_game_state["state"]["home_score"] = -1
        validator.validate_game_state(valid_game_state)
        validator.validate_game_state(valid_game_state)

        count = validator.get_anomaly_count("401547389")
        assert count >= 2

    def test_reset_anomaly_counts(
        self, validator: ESPNDataValidator, valid_game_state: dict
    ) -> None:
        """Reset should clear all counts."""
        valid_game_state["state"]["home_score"] = -1
        validator.validate_game_state(valid_game_state)

        validator.reset_anomaly_counts()
        assert validator.get_anomaly_count("401547389") == 0

    def test_get_all_anomaly_counts(
        self, validator: ESPNDataValidator, valid_game_state: dict
    ) -> None:
        """Should return all tracked games."""
        valid_game_state["state"]["home_score"] = -1
        validator.validate_game_state(valid_game_state)

        all_counts = validator.get_all_anomaly_counts()
        assert "401547389" in all_counts

    def test_tracking_disabled(self, valid_game_state: dict) -> None:
        """Tracking disabled should not store counts."""
        validator = ESPNDataValidator(track_anomalies=False)
        valid_game_state["state"]["home_score"] = -1
        validator.validate_game_state(valid_game_state)

        assert validator.get_anomaly_count("401547389") == 0


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateValidator:
    """Tests for create_validator factory function."""

    def test_default_validator(self) -> None:
        """Default validator should be created correctly."""
        validator = create_validator()
        assert not validator.strict_mode
        assert validator.track_anomalies

    def test_strict_mode(self) -> None:
        """Strict mode should be configurable."""
        validator = create_validator(strict_mode=True)
        assert validator.strict_mode

    def test_tracking_disabled(self) -> None:
        """Tracking should be configurable."""
        validator = create_validator(track_anomalies=False)
        assert not validator.track_anomalies


# =============================================================================
# Sport-Specific Period Tests
# =============================================================================


class TestSportSpecificPeriods:
    """Tests for sport-specific period validation."""

    @pytest.mark.parametrize(
        ("league", "expected_periods"),
        [
            ("nfl", 4),
            ("ncaaf", 4),
            ("nba", 4),
            ("ncaab", 2),
            ("nhl", 3),
            ("wnba", 4),
        ],
    )
    def test_period_counts_correct(
        self,
        validator: ESPNDataValidator,
        league: str,
        expected_periods: int,
    ) -> None:
        """Each sport should have correct period count."""
        assert validator.PERIOD_COUNTS[league] == expected_periods

    @pytest.mark.parametrize(
        ("league", "expected_length"),
        [
            ("nfl", 900),
            ("ncaaf", 900),
            ("nba", 720),
            ("ncaab", 1200),
            ("nhl", 1200),
            ("wnba", 600),
        ],
    )
    def test_period_lengths_correct(
        self,
        validator: ESPNDataValidator,
        league: str,
        expected_length: int,
    ) -> None:
        """Each sport should have correct period length."""
        assert validator.PERIOD_LENGTHS[league] == expected_length
