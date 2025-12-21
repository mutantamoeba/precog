"""
Integration Tests for ESPN Data Validation.

Tests validation with real ESPN data structures and integration
with other system components.

Reference: TESTING_STRATEGY V3.2 - Integration tests for component interaction
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/integration/validation/test_espn_validation_integration.py -v -m integration
"""

from decimal import Decimal
from typing import Any

import pytest

from precog.validation.espn_validation import (
    ESPNDataValidator,
    create_validator,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> ESPNDataValidator:
    """Create a validator for testing."""
    return ESPNDataValidator()


@pytest.fixture
def nfl_game_in_progress() -> dict[str, Any]:
    """Create a realistic NFL game in progress."""
    return {
        "metadata": {
            "espn_event_id": "401547389",
            "league": "nfl",
            "game_date": "2025-12-07T20:00:00Z",
            "season_year": 2025,
            "week": 14,
            "home_team": {
                "espn_team_id": "12",
                "team_name": "Kansas City Chiefs",
                "team_code": "KC",
                "conference": "AFC",
                "division": "West",
            },
            "away_team": {
                "espn_team_id": "33",
                "team_name": "Denver Broncos",
                "team_code": "DEN",
                "conference": "AFC",
                "division": "West",
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
            "home_score": 21,
            "away_score": 14,
            "period": 3,
            "clock_seconds": Decimal("723"),
            "clock_display": "12:03",
            "game_status": "in_progress",
            "situation": {
                "down": 2,
                "distance": 8,
                "possession": "KC",
                "yard_line": 45,
                "is_red_zone": False,
            },
        },
    }


@pytest.fixture
def nba_game_in_progress() -> dict[str, Any]:
    """Create a realistic NBA game in progress."""
    return {
        "metadata": {
            "espn_event_id": "401584123",
            "league": "nba",
            "game_date": "2025-12-08T19:30:00Z",
            "home_team": {
                "espn_team_id": "13",
                "team_name": "Los Angeles Lakers",
                "team_code": "LAL",
            },
            "away_team": {
                "espn_team_id": "2",
                "team_name": "Boston Celtics",
                "team_code": "BOS",
            },
        },
        "state": {
            "home_score": 87,
            "away_score": 91,
            "period": 4,
            "clock_seconds": Decimal("245"),
            "clock_display": "4:05",
            "game_status": "in_progress",
            "situation": {
                "fouls": 3,
                "timeouts_remaining_home": 2,
                "timeouts_remaining_away": 3,
            },
        },
    }


@pytest.fixture
def pregame_state() -> dict[str, Any]:
    """Create a pre-game state."""
    return {
        "metadata": {
            "espn_event_id": "401547400",
            "league": "nfl",
            "game_date": "2025-12-14T13:00:00Z",
            "home_team": {
                "espn_team_id": "8",
                "team_name": "Detroit Lions",
                "team_code": "DET",
            },
            "away_team": {
                "espn_team_id": "7",
                "team_name": "Chicago Bears",
                "team_code": "CHI",
            },
        },
        "state": {
            "home_score": 0,
            "away_score": 0,
            "period": 0,
            "clock_seconds": Decimal("900"),
            "game_status": "scheduled",
        },
    }


@pytest.fixture
def final_game_state() -> dict[str, Any]:
    """Create a final game state."""
    return {
        "metadata": {
            "espn_event_id": "401547350",
            "league": "nfl",
            "game_date": "2025-12-01T13:00:00Z",
            "home_team": {
                "espn_team_id": "1",
                "team_name": "Atlanta Falcons",
                "team_code": "ATL",
            },
            "away_team": {
                "espn_team_id": "29",
                "team_name": "Carolina Panthers",
                "team_code": "CAR",
            },
        },
        "state": {
            "home_score": 31,
            "away_score": 24,
            "period": 4,
            "clock_seconds": Decimal("0"),
            "game_status": "final",
        },
    }


# =============================================================================
# Integration Tests: Multi-Sport Validation
# =============================================================================


@pytest.mark.integration
class TestMultiSportValidation:
    """Integration tests for validation across different sports."""

    def test_nfl_game_validation(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test full validation of NFL game state."""
        result = validator.validate_game_state(nfl_game_in_progress)  # type: ignore[arg-type]

        assert result.is_valid
        assert not result.has_errors
        assert result.game_id == "401547389"

    def test_nba_game_validation(
        self, validator: ESPNDataValidator, nba_game_in_progress: dict[str, Any]
    ) -> None:
        """Test full validation of NBA game state."""
        result = validator.validate_game_state(nba_game_in_progress)  # type: ignore[arg-type]

        assert result.is_valid
        assert not result.has_errors
        assert result.game_id == "401584123"

    def test_pregame_state_validation(
        self, validator: ESPNDataValidator, pregame_state: dict[str, Any]
    ) -> None:
        """Test validation of pre-game state."""
        result = validator.validate_game_state(pregame_state)  # type: ignore[arg-type]

        assert result.is_valid
        # May have info about period 0 (pre-game)

    def test_final_state_validation(
        self, validator: ESPNDataValidator, final_game_state: dict[str, Any]
    ) -> None:
        """Test validation of final game state."""
        result = validator.validate_game_state(final_game_state)  # type: ignore[arg-type]

        assert result.is_valid
        assert not result.has_errors


# =============================================================================
# Integration Tests: State Transitions
# =============================================================================


@pytest.mark.integration
class TestStateTransitionValidation:
    """Integration tests for game state transitions."""

    def test_score_progression(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test validation across score progression."""
        # Initial state
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])
        game["state"]["home_score"] = 7
        game["state"]["away_score"] = 0

        result1 = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result1.is_valid

        # Score increases
        previous_state = {"home_score": 7, "away_score": 0}
        game["state"]["home_score"] = 14
        game["state"]["away_score"] = 7

        result2 = validator.validate_game_state(game, previous_state)  # type: ignore[arg-type]
        assert result2.is_valid
        assert not result2.has_warnings  # No decrease warnings

    def test_period_progression(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test validation across period progression."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])

        # Validate each period
        for period in range(1, 5):
            game["state"]["period"] = period
            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            assert result.is_valid, f"Period {period} should be valid"

    def test_overtime_period(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test overtime period validation."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])
        game["state"]["period"] = 5  # OT

        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid

    def test_clock_countdown(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test clock countdown validation."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])

        # Clock counts down
        clock_values = [Decimal("900"), Decimal("600"), Decimal("300"), Decimal("0")]
        for clock in clock_values:
            game["state"]["clock_seconds"] = clock
            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            assert result.is_valid, f"Clock {clock} should be valid"


# =============================================================================
# Integration Tests: Football Situation Tracking
# =============================================================================


@pytest.mark.integration
class TestFootballSituationIntegration:
    """Integration tests for football situation tracking."""

    def test_drive_progression(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test validation across a drive."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])
        game["state"]["situation"] = dict(game["state"]["situation"])

        # First and 10
        game["state"]["situation"]["down"] = 1
        game["state"]["situation"]["distance"] = 10
        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid

        # Second and 7
        game["state"]["situation"]["down"] = 2
        game["state"]["situation"]["distance"] = 7
        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid

        # Third and 2
        game["state"]["situation"]["down"] = 3
        game["state"]["situation"]["distance"] = 2
        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid

        # Fourth and 1
        game["state"]["situation"]["down"] = 4
        game["state"]["situation"]["distance"] = 1
        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid

    def test_special_teams_situation(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test special teams situation (down = -1)."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])
        game["state"]["situation"] = {
            "down": -1,
            "distance": -1,
            "possession": "KC",
        }

        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid  # -1 is valid for non-play situations

    def test_goal_line_situation(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test goal line situation validation."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])
        game["state"]["situation"] = {
            "down": 1,
            "distance": 3,  # Goal to go
            "possession": "KC",
            "yard_line": 3,
            "is_red_zone": True,
        }

        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid


# =============================================================================
# Integration Tests: Anomaly Detection Across Games
# =============================================================================


@pytest.mark.integration
class TestAnomalyDetectionIntegration:
    """Integration tests for anomaly detection across multiple games."""

    def test_track_anomalies_across_games(self, validator: ESPNDataValidator) -> None:
        """Test anomaly tracking across multiple games."""
        games = [
            {
                "metadata": {"espn_event_id": f"game{i}", "league": "nfl"},
                "state": {"home_score": -1, "away_score": 0, "period": 1},
            }
            for i in range(3)
        ]

        for game in games:
            validator.validate_game_state(game)  # type: ignore[arg-type]

        all_counts = validator.get_all_anomaly_counts()
        assert len(all_counts) == 3
        for game_id in ["game0", "game1", "game2"]:
            assert validator.get_anomaly_count(game_id) >= 1

    def test_anomaly_pattern_detection(self, validator: ESPNDataValidator) -> None:
        """Test detecting patterns across multiple validations."""
        game = {
            "metadata": {"espn_event_id": "pattern_test", "league": "nfl"},
            "state": {"home_score": -1, "away_score": 0, "period": 1},
        }

        # Multiple validations with same issue
        for _ in range(5):
            validator.validate_game_state(game)  # type: ignore[arg-type]

        count = validator.get_anomaly_count("pattern_test")
        assert count >= 5, "Should track repeated anomalies"


# =============================================================================
# Integration Tests: Strict Mode Behavior
# =============================================================================


@pytest.mark.integration
class TestStrictModeIntegration:
    """Integration tests for strict mode behavior."""

    def test_strict_mode_vs_normal(self, nfl_game_in_progress: dict[str, Any]) -> None:
        """Test strict mode treats warnings differently."""
        normal_validator = create_validator(strict_mode=False)
        strict_validator = create_validator(strict_mode=True)

        # Game with minor issue (warning-level)
        game = nfl_game_in_progress.copy()
        game["metadata"] = dict(game["metadata"])
        game["metadata"]["venue"]["capacity"] = -1  # Invalid capacity (warning)

        normal_result = normal_validator.validate_game_state(game)  # type: ignore[arg-type]
        strict_result = strict_validator.validate_game_state(game)  # type: ignore[arg-type]

        # Both should have warnings
        assert normal_result.has_warnings
        assert strict_result.has_warnings

        # Strict mode flag is set
        assert strict_validator.strict_mode

    def test_strict_mode_complete_validation(self) -> None:
        """Test strict mode with complete game state."""
        strict_validator = create_validator(strict_mode=True)

        valid_game = {
            "metadata": {
                "espn_event_id": "401547389",
                "league": "nfl",
                "home_team": {"espn_team_id": "12", "team_name": "Chiefs"},
                "away_team": {"espn_team_id": "33", "team_name": "Broncos"},
            },
            "state": {
                "home_score": 14,
                "away_score": 7,
                "period": 2,
                "clock_seconds": Decimal("450"),
            },
        }

        result = strict_validator.validate_game_state(valid_game)  # type: ignore[arg-type]
        assert result.is_valid


# =============================================================================
# Integration Tests: Real-World Data Patterns
# =============================================================================


@pytest.mark.integration
class TestRealWorldDataPatterns:
    """Integration tests for real-world ESPN data patterns."""

    def test_minimal_game_state(self, validator: ESPNDataValidator) -> None:
        """Test validation of minimal required fields."""
        minimal_game = {
            "metadata": {
                "espn_event_id": "401547389",
                "league": "nfl",
            },
            "state": {
                "home_score": 0,
                "away_score": 0,
            },
        }

        result = validator.validate_game_state(minimal_game)  # type: ignore[arg-type]
        # Should have warnings for missing optional data
        assert result.has_warnings

    def test_game_with_empty_situation(
        self, validator: ESPNDataValidator, nfl_game_in_progress: dict[str, Any]
    ) -> None:
        """Test game with empty situation (halftime, timeout)."""
        game = nfl_game_in_progress.copy()
        game["state"] = dict(game["state"])
        game["state"]["situation"] = {}  # Empty during timeout

        result = validator.validate_game_state(game)  # type: ignore[arg-type]
        assert result.is_valid

    def test_ncaab_two_halves(self, validator: ESPNDataValidator) -> None:
        """Test NCAAB validation (2 halves instead of 4 quarters)."""
        ncaab_game = {
            "metadata": {
                "espn_event_id": "401585001",
                "league": "ncaab",
                "home_team": {"espn_team_id": "150", "team_name": "Duke"},
                "away_team": {"espn_team_id": "153", "team_name": "UNC"},
            },
            "state": {
                "home_score": 45,
                "away_score": 42,
                "period": 2,  # Second half
                "clock_seconds": Decimal("900"),
            },
        }

        result = validator.validate_game_state(ncaab_game)  # type: ignore[arg-type]
        assert result.is_valid

    def test_nhl_three_periods(self, validator: ESPNDataValidator) -> None:
        """Test NHL validation (3 periods)."""
        nhl_game = {
            "metadata": {
                "espn_event_id": "401586001",
                "league": "nhl",
                "home_team": {"espn_team_id": "4", "team_name": "Bruins"},
                "away_team": {"espn_team_id": "10", "team_name": "Maple Leafs"},
            },
            "state": {
                "home_score": 3,
                "away_score": 2,
                "period": 3,
                "clock_seconds": Decimal("600"),
            },
        }

        result = validator.validate_game_state(nhl_game)  # type: ignore[arg-type]
        assert result.is_valid


# =============================================================================
# Integration Tests: Factory Function Integration
# =============================================================================


@pytest.mark.integration
class TestFactoryFunctionIntegration:
    """Integration tests for create_validator factory function."""

    def test_factory_default_config(self, nfl_game_in_progress: dict[str, Any]) -> None:
        """Test factory function with default configuration."""
        validator = create_validator()

        result = validator.validate_game_state(nfl_game_in_progress)  # type: ignore[arg-type]
        assert result.is_valid

        # Default settings
        assert not validator.strict_mode
        assert validator.track_anomalies

    def test_factory_custom_config(self, nfl_game_in_progress: dict[str, Any]) -> None:
        """Test factory function with custom configuration."""
        validator = create_validator(strict_mode=True, track_anomalies=False)

        result = validator.validate_game_state(nfl_game_in_progress)  # type: ignore[arg-type]
        assert result.is_valid

        # Custom settings
        assert validator.strict_mode
        assert not validator.track_anomalies

    def test_factory_multiple_instances_independent(self) -> None:
        """Test that factory creates independent instances."""
        validator1 = create_validator()
        validator2 = create_validator()

        game = {
            "metadata": {"espn_event_id": "test123", "league": "nfl"},
            "state": {"home_score": -1, "away_score": 0, "period": 1},
        }

        validator1.validate_game_state(game)  # type: ignore[arg-type]

        # Validator2 should not have validator1's anomaly counts
        assert validator2.get_anomaly_count("test123") == 0
        assert validator1.get_anomaly_count("test123") >= 1
