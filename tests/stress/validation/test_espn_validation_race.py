"""
Race condition tests for espn_validation module.

Tests for race conditions in concurrent validation operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading
from decimal import Decimal
from typing import Any

import pytest

from precog.validation.espn_validation import (
    ValidationResult,
    create_validator,
)

pytestmark = [pytest.mark.race]


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


class TestValidationResultRace:
    """Race condition tests for ValidationResult."""

    def test_concurrent_result_access_consistent(self) -> None:
        """Verify concurrent access to ValidationResult is consistent."""
        results: list[ValidationResult] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        validator = create_validator()
        game = _create_sample_game("401547389")

        def validate_and_check() -> None:
            try:
                result = validator.validate_game_state(game)  # type: ignore[arg-type]
                # Access multiple properties concurrently
                _ = result.is_valid
                _ = result.has_errors
                _ = result.has_warnings
                _ = result.errors
                _ = result.warnings
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate_and_check) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        # All results should be identical (same game)
        first_valid = results[0].is_valid
        assert all(r.is_valid == first_valid for r in results)

    def test_concurrent_add_issues_separate_results(self) -> None:
        """Verify concurrent issue additions to separate results."""
        errors: list[Exception] = []
        lock = threading.Lock()

        def add_issues_to_result(result: ValidationResult, idx: int) -> None:
            try:
                for _ in range(10):
                    result.add_error(f"field_{idx}", "Test error")
                    result.add_warning(f"field_{idx}", "Test warning")
                    result.add_info(f"field_{idx}", "Test info")
            except Exception as e:
                with lock:
                    errors.append(e)

        # Create separate results for each thread
        results = [ValidationResult(game_id=f"game_{i}") for i in range(50)]

        threads = [
            threading.Thread(target=add_issues_to_result, args=(r, i))
            for i, r in enumerate(results)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # Each result should have 30 issues (10 errors + 10 warnings + 10 infos)
        for result in results:
            assert len(result.issues) == 30


class TestValidatorRace:
    """Race condition tests for ESPNDataValidator."""

    def test_concurrent_validation_same_game(self) -> None:
        """Verify concurrent validation of same game returns consistent results."""
        validator = create_validator()
        game = _create_sample_game("401547389")

        results: list[ValidationResult] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate() -> None:
            try:
                result = validator.validate_game_state(game)  # type: ignore[arg-type]
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100

        # All results should be consistent
        first_valid = results[0].is_valid
        first_issue_count = len(results[0].issues)
        assert all(r.is_valid == first_valid for r in results)
        assert all(len(r.issues) == first_issue_count for r in results)

    def test_concurrent_validation_different_games(self) -> None:
        """Verify concurrent validation of different games."""
        validator = create_validator(track_anomalies=True)

        results: list[tuple[str, ValidationResult]] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_game(game_id: str) -> None:
            try:
                game = _create_sample_game(game_id)
                result = validator.validate_game_state(game)  # type: ignore[arg-type]
                with lock:
                    results.append((game_id, result))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=validate_game, args=(f"40154{i:04d}",)) for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100

        # All game IDs should be unique
        game_ids = [gid for gid, _ in results]
        assert len(set(game_ids)) == 100


class TestAnomalyCountRace:
    """Race condition tests for anomaly count tracking."""

    def test_concurrent_anomaly_count_updates(self) -> None:
        """Verify concurrent anomaly count updates don't corrupt."""
        validator = create_validator(track_anomalies=True)

        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_with_anomaly(game_id: str) -> None:
            try:
                game = _create_sample_game(game_id)
                # Add an issue to trigger anomaly tracking
                game["state"]["period"] = -1
                validator.validate_game_state(game)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=validate_with_anomaly, args=(f"40154{i:04d}",))
            for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"

        counts = validator.get_all_anomaly_counts()
        assert len(counts) == 100

    def test_concurrent_get_anomaly_count(self) -> None:
        """Verify concurrent reads of anomaly counts."""
        validator = create_validator(track_anomalies=True)

        # Pre-populate anomaly counts
        for i in range(50):
            game = _create_sample_game(f"40154{i:04d}")
            game["state"]["period"] = -1
            validator.validate_game_state(game)  # type: ignore[arg-type]

        results: list[int] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def get_count(game_id: str) -> None:
            try:
                count = validator.get_anomaly_count(game_id)
                with lock:
                    results.append(count)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=get_count, args=(f"40154{i:04d}",)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 50
        assert all(count >= 0 for count in results)

    def test_concurrent_reset_and_validate(self) -> None:
        """Test reset while validation is occurring."""
        validator = create_validator(track_anomalies=True)

        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_batch() -> None:
            try:
                for i in range(20):
                    game = _create_sample_game(f"401{threading.current_thread().ident}{i:04d}")
                    game["state"]["period"] = -1
                    validator.validate_game_state(game)  # type: ignore[arg-type]
            except Exception as e:
                with lock:
                    errors.append(e)

        def reset_periodically() -> None:
            try:
                for _ in range(5):
                    validator.reset_anomaly_counts()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate_batch) for _ in range(5)]
        threads.append(threading.Thread(target=reset_periodically))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestMixedOperationsRace:
    """Race condition tests for mixed operations."""

    def test_concurrent_score_clock_situation_validation(self) -> None:
        """Test concurrent validation of score, clock, and situation."""
        validator = create_validator()

        score_results: list[ValidationResult] = []
        clock_results: list[ValidationResult] = []
        situation_results: list[ValidationResult] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def validate_score(idx: int) -> None:
            try:
                result = validator.validate_score(idx % 50, idx % 30)
                with lock:
                    score_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        def validate_clock(idx: int) -> None:
            try:
                result = validator.validate_clock(
                    Decimal(str(idx % 900)),
                    (idx % 4) + 1,
                    "nfl",
                )
                with lock:
                    clock_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        def validate_situation(idx: int) -> None:
            try:
                situation = {"down": (idx % 4) + 1, "distance": (idx % 10) + 1}
                result = validator.validate_situation(situation, "nfl")
                with lock:
                    situation_results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = []
        for i in range(50):
            threads.append(threading.Thread(target=validate_score, args=(i,)))
            threads.append(threading.Thread(target=validate_clock, args=(i,)))
            threads.append(threading.Thread(target=validate_situation, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(score_results) == 50
        assert len(clock_results) == 50
        assert len(situation_results) == 50


class TestValidatorModeRace:
    """Race condition tests for validator mode settings."""

    def test_strict_mode_consistent(self) -> None:
        """Verify strict mode behavior is consistent under concurrency."""
        validator_strict = create_validator(strict_mode=True)
        validator_normal = create_validator(strict_mode=False)

        strict_results: list[bool] = []
        normal_results: list[bool] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def check_strict_mode() -> None:
            try:
                with lock:
                    strict_results.append(validator_strict.strict_mode)
                    normal_results.append(validator_normal.strict_mode)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=check_strict_mode) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert all(s is True for s in strict_results)
        assert all(n is False for n in normal_results)
