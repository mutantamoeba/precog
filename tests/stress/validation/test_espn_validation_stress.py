"""
Stress tests for espn_validation module.

Tests high-volume validation operations under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Any

import pytest

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationResult,
    create_validator,
)

pytestmark = [pytest.mark.stress]


def _create_sample_game(game_id: str, home_score: int = 14, away_score: int = 7) -> dict[str, Any]:
    """Create a sample game for testing."""
    return {
        "metadata": {
            "espn_event_id": game_id,
            "league": "nfl",
            "game_date": "2024-01-15",
            "home_team": {"espn_team_id": "1", "team_name": "Team A"},
            "away_team": {"espn_team_id": "2", "team_name": "Team B"},
            "venue": {"venue_name": "Stadium", "capacity": 50000},
        },
        "state": {
            "home_score": home_score,
            "away_score": away_score,
            "clock_seconds": Decimal("300"),
            "period": 2,
            "situation": {
                "down": 2,
                "distance": 7,
                "possession": "home",
            },
        },
    }


class TestValidatorCreationStress:
    """Stress tests for validator creation."""

    def test_rapid_validator_creation(self) -> None:
        """Test rapid sequential validator creation."""
        validators = []
        for _ in range(500):
            v = create_validator(strict_mode=False, track_anomalies=True)
            validators.append(v)

        assert len(validators) == 500
        assert all(isinstance(v, ESPNDataValidator) for v in validators)

    def test_concurrent_validator_creation(self) -> None:
        """Test concurrent validator creation."""
        validators: list[ESPNDataValidator] = []
        lock = threading.Lock()

        def create_one() -> ESPNDataValidator:
            v = create_validator(strict_mode=True)
            with lock:
                validators.append(v)
            return v

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_one) for _ in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(validators) == 200


class TestGameStateValidationStress:
    """Stress tests for game state validation."""

    def test_rapid_validation_sequential(self) -> None:
        """Test rapid sequential game validation."""
        validator = create_validator()

        for i in range(1000):
            game = _create_sample_game(f"40154{i:04d}")
            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            assert isinstance(result, ValidationResult)

    def test_concurrent_validation_same_validator(self) -> None:
        """Test concurrent validation with shared validator."""
        validator = create_validator()
        results: list[ValidationResult] = []
        lock = threading.Lock()

        def validate_game(game_id: str) -> ValidationResult:
            game = _create_sample_game(game_id)
            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(validate_game, f"40154{i:04d}") for i in range(300)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 300
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_concurrent_validation_separate_validators(self) -> None:
        """Test concurrent validation with separate validators."""
        results: list[ValidationResult] = []
        lock = threading.Lock()

        def validate_with_new_validator(game_id: str) -> ValidationResult:
            validator = create_validator()
            game = _create_sample_game(game_id)
            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(validate_with_new_validator, f"40154{i:04d}") for i in range(200)
            ]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200


class TestValidationWithVaryingDataStress:
    """Stress tests with varying validation scenarios."""

    def test_mixed_valid_invalid_games(self) -> None:
        """Test validation with mix of valid and invalid games."""
        validator = create_validator()
        valid_count = 0
        invalid_count = 0

        for i in range(500):
            if i % 3 == 0:
                # Invalid: negative score
                game = _create_sample_game(f"40154{i:04d}", home_score=-1)
            elif i % 5 == 0:
                # Invalid: negative away score
                game = _create_sample_game(f"40154{i:04d}", away_score=-1)
            else:
                # Valid game
                game = _create_sample_game(f"40154{i:04d}")

            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            if result.is_valid:
                valid_count += 1
            else:
                invalid_count += 1

        # Verify we got both valid and invalid results
        assert valid_count > 0
        assert invalid_count > 0
        assert valid_count + invalid_count == 500

    def test_many_games_same_validator_anomaly_tracking(self) -> None:
        """Test anomaly tracking with many games."""
        validator = create_validator(track_anomalies=True)

        for i in range(200):
            # Create games with issues to trigger anomaly tracking
            game = _create_sample_game(f"40154{i:04d}")
            # Add an issue
            game["state"]["clock_seconds"] = Decimal("1000")  # Exceeds period length
            validator.validate_game_state(game)  # type: ignore[arg-type]

        counts = validator.get_all_anomaly_counts()
        assert len(counts) == 200

    def test_validation_across_multiple_leagues(self) -> None:
        """Test validation across all supported leagues."""
        validator = create_validator()
        leagues = ["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"]

        for i in range(300):
            league = leagues[i % len(leagues)]
            game = {
                "metadata": {
                    "espn_event_id": f"40154{i:04d}",
                    "league": league,
                    "home_team": {"espn_team_id": "1", "team_name": "Team A"},
                    "away_team": {"espn_team_id": "2", "team_name": "Team B"},
                },
                "state": {
                    "home_score": 14,
                    "away_score": 7,
                    "clock_seconds": Decimal("300"),
                    "period": 2,
                },
            }
            result = validator.validate_game_state(game)  # type: ignore[arg-type]
            assert isinstance(result, ValidationResult)


class TestIndividualValidationMethodsStress:
    """Stress tests for individual validation methods."""

    def test_validate_score_stress(self) -> None:
        """Test rapid score validation."""
        validator = create_validator()

        for i in range(2000):
            result = validator.validate_score(
                home_score=i % 100,
                away_score=(i * 3) % 100,
            )
            assert isinstance(result, ValidationResult)

    def test_validate_clock_stress(self) -> None:
        """Test rapid clock validation."""
        validator = create_validator()

        for i in range(2000):
            result = validator.validate_clock(
                clock_seconds=Decimal(str(i % 900)),
                period=(i % 4) + 1,
                league="nfl",
            )
            assert isinstance(result, ValidationResult)

    def test_validate_situation_stress(self) -> None:
        """Test rapid situation validation."""
        validator = create_validator()

        for i in range(2000):
            situation = {
                "down": (i % 4) + 1,
                "distance": (i % 20) + 1,
                "possession": "home" if i % 2 else "away",
            }
            result = validator.validate_situation(situation, "nfl")
            assert isinstance(result, ValidationResult)


class TestAnomalyCountStress:
    """Stress tests for anomaly count tracking."""

    def test_concurrent_anomaly_updates(self) -> None:
        """Test concurrent updates to anomaly counts."""
        validator = create_validator(track_anomalies=True)

        def validate_batch(start_idx: int) -> None:
            for i in range(50):
                game = _create_sample_game(f"40154{start_idx + i:04d}")
                # Add issue to trigger anomaly tracking
                game["state"]["period"] = -1
                validator.validate_game_state(game)  # type: ignore[arg-type]

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_batch, i * 50) for i in range(10)]
            for future in as_completed(futures):
                future.result()

        counts = validator.get_all_anomaly_counts()
        assert len(counts) == 500

    def test_reset_anomaly_counts_under_load(self) -> None:
        """Test resetting anomaly counts while validating."""
        validator = create_validator(track_anomalies=True)

        # Add some anomalies
        for i in range(100):
            game = _create_sample_game(f"40154{i:04d}")
            game["state"]["period"] = -1
            validator.validate_game_state(game)  # type: ignore[arg-type]

        assert len(validator.get_all_anomaly_counts()) == 100

        # Reset
        validator.reset_anomaly_counts()

        assert len(validator.get_all_anomaly_counts()) == 0

        # Add more
        for i in range(50):
            game = _create_sample_game(f"40155{i:04d}")
            game["state"]["period"] = -1
            validator.validate_game_state(game)  # type: ignore[arg-type]

        assert len(validator.get_all_anomaly_counts()) == 50
