"""
End-to-End Tests for ESPN Data Validation.

Tests complete validation workflows as they would occur in production,
including realistic game progression and error recovery scenarios.

Reference: TESTING_STRATEGY V3.2 - E2E tests for complete workflows
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/e2e/validation/test_espn_validation_e2e.py -v -m e2e
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
    """Create a validator for E2E testing."""
    return ESPNDataValidator(track_anomalies=True)


# =============================================================================
# E2E Tests: Complete Game Workflow
# =============================================================================


@pytest.mark.e2e
class TestCompleteGameWorkflow:
    """E2E tests for complete game validation workflow."""

    def test_nfl_game_lifecycle(self, validator: ESPNDataValidator) -> None:
        """Test validation through complete NFL game lifecycle."""
        game_id = "401547389"

        # Pre-game
        pregame = {
            "metadata": {
                "espn_event_id": game_id,
                "league": "nfl",
                "game_date": "2025-12-07T20:00:00Z",
                "home_team": {"espn_team_id": "12", "team_name": "Chiefs"},
                "away_team": {"espn_team_id": "33", "team_name": "Broncos"},
            },
            "state": {
                "home_score": 0,
                "away_score": 0,
                "period": 0,
                "clock_seconds": Decimal("900"),
                "game_status": "scheduled",
            },
        }

        result = validator.validate_game_state(pregame)
        assert result.is_valid, "Pre-game state should be valid"

        # First quarter starts
        q1_start = {
            "metadata": pregame["metadata"],
            "state": {
                "home_score": 0,
                "away_score": 0,
                "period": 1,
                "clock_seconds": Decimal("900"),
                "game_status": "in_progress",
                "situation": {"down": 1, "distance": 10, "possession": "KC"},
            },
        }

        result = validator.validate_game_state(q1_start)
        assert result.is_valid, "Q1 start should be valid"

        # First scoring play
        first_score = {
            "metadata": pregame["metadata"],
            "state": {
                "home_score": 7,
                "away_score": 0,
                "period": 1,
                "clock_seconds": Decimal("456"),
                "game_status": "in_progress",
            },
        }

        result = validator.validate_game_state(first_score)
        assert result.is_valid, "First score should be valid"

        # Halftime
        halftime = {
            "metadata": pregame["metadata"],
            "state": {
                "home_score": 14,
                "away_score": 10,
                "period": 2,
                "clock_seconds": Decimal("0"),
                "game_status": "halftime",
            },
        }

        result = validator.validate_game_state(halftime)
        assert result.is_valid, "Halftime should be valid"

        # Final
        final = {
            "metadata": pregame["metadata"],
            "state": {
                "home_score": 31,
                "away_score": 24,
                "period": 4,
                "clock_seconds": Decimal("0"),
                "game_status": "final",
            },
        }

        result = validator.validate_game_state(final)
        assert result.is_valid, "Final state should be valid"

    def test_nba_game_lifecycle(self, validator: ESPNDataValidator) -> None:
        """Test validation through complete NBA game lifecycle."""
        game_id = "401584001"

        states = [
            # Pre-game
            {
                "home_score": 0,
                "away_score": 0,
                "period": 0,
                "clock_seconds": Decimal("720"),
                "game_status": "scheduled",
            },
            # Q1
            {
                "home_score": 28,
                "away_score": 25,
                "period": 1,
                "clock_seconds": Decimal("0"),
            },
            # Q2
            {
                "home_score": 55,
                "away_score": 52,
                "period": 2,
                "clock_seconds": Decimal("0"),
            },
            # Q3
            {
                "home_score": 82,
                "away_score": 80,
                "period": 3,
                "clock_seconds": Decimal("0"),
            },
            # Q4 Final
            {
                "home_score": 112,
                "away_score": 108,
                "period": 4,
                "clock_seconds": Decimal("0"),
                "game_status": "final",
            },
        ]

        for i, state in enumerate(states):
            game = {
                "metadata": {
                    "espn_event_id": game_id,
                    "league": "nba",
                    "home_team": {"espn_team_id": "13", "team_name": "Lakers"},
                    "away_team": {"espn_team_id": "2", "team_name": "Celtics"},
                },
                "state": state,
            }

            result = validator.validate_game_state(game)
            assert result.is_valid, f"State {i} should be valid"


# =============================================================================
# E2E Tests: Score Correction Workflow
# =============================================================================


@pytest.mark.e2e
class TestScoreCorrectionWorkflow:
    """E2E tests for score correction scenarios."""

    def test_score_correction_detected(self, validator: ESPNDataValidator) -> None:
        """Test that score corrections generate warnings."""
        game_id = "401547400"
        metadata = {
            "espn_event_id": game_id,
            "league": "nfl",
            "home_team": {"espn_team_id": "1"},
            "away_team": {"espn_team_id": "2"},
        }

        # Initial state
        initial = {
            "metadata": metadata,
            "state": {"home_score": 14, "away_score": 7, "period": 2},
        }
        validator.validate_game_state(initial)

        # Corrected state (home score decreased - official correction)
        corrected = {
            "metadata": metadata,
            "state": {"home_score": 13, "away_score": 7, "period": 2},
        }
        previous = {"home_score": 14, "away_score": 7}

        result = validator.validate_game_state(corrected, previous)

        # Should have warning about score decrease
        assert result.has_warnings
        assert any("decreased" in w.message for w in result.warnings)

        # Should still be valid (corrections happen)
        assert result.is_valid

    def test_multiple_corrections_tracked(self, validator: ESPNDataValidator) -> None:
        """Test tracking of multiple corrections in a game."""
        game_id = "correction_test"
        metadata = {
            "espn_event_id": game_id,
            "league": "nfl",
            "home_team": {"espn_team_id": "1"},
            "away_team": {"espn_team_id": "2"},
        }

        # Multiple corrections
        states = [
            ({"home_score": 14, "away_score": 7}, None),
            ({"home_score": 13, "away_score": 7}, {"home_score": 14, "away_score": 7}),
            ({"home_score": 13, "away_score": 6}, {"home_score": 13, "away_score": 7}),
        ]

        for state, prev in states:
            game = {"metadata": metadata, "state": {**state, "period": 2}}
            validator.validate_game_state(game, prev)

        # Should track multiple anomalies
        count = validator.get_anomaly_count(game_id)
        assert count >= 2, "Should track multiple corrections"


# =============================================================================
# E2E Tests: Multi-Game Session
# =============================================================================


@pytest.mark.e2e
class TestMultiGameSession:
    """E2E tests for multi-game validation sessions."""

    def test_sunday_slate_validation(self, validator: ESPNDataValidator) -> None:
        """Test validating multiple concurrent NFL games."""
        games = [
            {
                "espn_event_id": f"40154700{i}",
                "home_team": f"Team{i}H",
                "away_team": f"Team{i}A",
                "home_score": i * 7,
                "away_score": i * 3,
            }
            for i in range(1, 6)
        ]

        results = []
        for game_data in games:
            game = {
                "metadata": {
                    "espn_event_id": game_data["espn_event_id"],
                    "league": "nfl",
                    "home_team": {
                        "espn_team_id": str(hash(game_data["home_team"]) % 100),
                        "team_name": game_data["home_team"],
                    },
                    "away_team": {
                        "espn_team_id": str(hash(game_data["away_team"]) % 100),
                        "team_name": game_data["away_team"],
                    },
                },
                "state": {
                    "home_score": game_data["home_score"],
                    "away_score": game_data["away_score"],
                    "period": 2,
                    "clock_seconds": Decimal("450"),
                },
            }

            result = validator.validate_game_state(game)
            results.append(result)

        # All games should be valid
        assert all(r.is_valid for r in results)

        # Each game tracked independently
        all_counts = validator.get_all_anomaly_counts()
        # Valid games should have no anomalies
        assert len(all_counts) == 0 or all(v == 0 for v in all_counts.values())

    def test_mixed_sport_session(self, validator: ESPNDataValidator) -> None:
        """Test validating games from multiple sports."""
        sports_games = [
            ("nfl", 4, 900),  # 4 quarters, 15 min
            ("nba", 4, 720),  # 4 quarters, 12 min
            ("ncaab", 2, 1200),  # 2 halves, 20 min
            ("nhl", 3, 1200),  # 3 periods, 20 min
        ]

        for league, periods, period_length in sports_games:
            game = {
                "metadata": {
                    "espn_event_id": f"game_{league}",
                    "league": league,
                    "home_team": {"espn_team_id": "1", "team_name": "Home"},
                    "away_team": {"espn_team_id": "2", "team_name": "Away"},
                },
                "state": {
                    "home_score": 10,
                    "away_score": 8,
                    "period": periods,  # Final period
                    "clock_seconds": Decimal(str(period_length // 2)),
                },
            }

            result = validator.validate_game_state(game)
            assert result.is_valid, f"{league} game should be valid"


# =============================================================================
# E2E Tests: Data Quality Monitoring
# =============================================================================


@pytest.mark.e2e
class TestDataQualityMonitoring:
    """E2E tests for data quality monitoring workflow."""

    def test_anomaly_report_generation(self, validator: ESPNDataValidator) -> None:
        """Test generating anomaly report for session."""
        # Mix of valid and invalid data
        # Note: Valid games need complete metadata to avoid warnings
        games = [
            {"id": "valid1", "home_score": 14, "away_score": 7, "has_teams": True},
            {"id": "invalid1", "home_score": -1, "away_score": 7, "has_teams": True},
            {"id": "valid2", "home_score": 21, "away_score": 14, "has_teams": True},
            {"id": "invalid2", "home_score": 10, "away_score": -3, "has_teams": True},
        ]

        for game_data in games:
            metadata: dict[str, Any] = {
                "espn_event_id": game_data["id"],
                "league": "nfl",
            }
            if game_data.get("has_teams"):
                metadata["home_team"] = {"espn_team_id": "1", "team_name": "Home"}
                metadata["away_team"] = {"espn_team_id": "2", "team_name": "Away"}

            game = {
                "metadata": metadata,
                "state": {
                    "home_score": game_data["home_score"],
                    "away_score": game_data["away_score"],
                    "period": 2,
                },
            }
            validator.validate_game_state(game)

        # Generate report
        all_counts = validator.get_all_anomaly_counts()

        # Invalid games should have anomalies (negative scores = errors)
        assert all_counts.get("invalid1", 0) > 0
        assert all_counts.get("invalid2", 0) > 0

        # Valid games with complete metadata should have no anomalies
        assert all_counts.get("valid1", 0) == 0
        assert all_counts.get("valid2", 0) == 0

    def test_session_reset_workflow(self, validator: ESPNDataValidator) -> None:
        """Test session reset for new batch."""
        # First batch
        game1 = {
            "metadata": {"espn_event_id": "batch1", "league": "nfl"},
            "state": {"home_score": -1, "away_score": 0, "period": 1},
        }
        validator.validate_game_state(game1)
        assert validator.get_anomaly_count("batch1") > 0

        # Reset for new batch
        validator.reset_anomaly_counts()

        # Second batch
        game2 = {
            "metadata": {"espn_event_id": "batch2", "league": "nfl"},
            "state": {"home_score": -1, "away_score": 0, "period": 1},
        }
        validator.validate_game_state(game2)

        # First batch counts should be gone
        assert validator.get_anomaly_count("batch1") == 0
        assert validator.get_anomaly_count("batch2") > 0


# =============================================================================
# E2E Tests: Error Recovery Workflow
# =============================================================================


@pytest.mark.e2e
class TestErrorRecoveryWorkflow:
    """E2E tests for error recovery scenarios."""

    def test_continue_after_invalid_data(self, validator: ESPNDataValidator) -> None:
        """Test validation continues after encountering invalid data."""
        games = [
            {"id": "game1", "home_score": 14, "away_score": 7, "valid": True},
            {"id": "game2", "home_score": -1, "away_score": 0, "valid": False},
            {"id": "game3", "home_score": 21, "away_score": 14, "valid": True},
        ]

        results = []
        for game_data in games:
            game = {
                "metadata": {"espn_event_id": game_data["id"], "league": "nfl"},
                "state": {
                    "home_score": game_data["home_score"],
                    "away_score": game_data["away_score"],
                    "period": 2,
                },
            }

            result = validator.validate_game_state(game)
            results.append(result)

        # First and third should be valid
        assert results[0].is_valid
        assert not results[1].is_valid  # Invalid
        assert results[2].is_valid  # Still validated despite earlier error

    def test_recover_from_malformed_data(self, validator: ESPNDataValidator) -> None:
        """Test handling of malformed game data."""
        # Missing required fields
        malformed = {
            "metadata": {},  # Missing espn_event_id
            "state": {"home_score": 14, "away_score": 7},
        }

        result = validator.validate_game_state(malformed)

        # Should report error for missing event ID
        assert not result.is_valid
        assert any("espn_event_id" in e.field for e in result.errors)

        # But validator should still work for next game
        valid_game = {
            "metadata": {"espn_event_id": "valid_after_error", "league": "nfl"},
            "state": {"home_score": 14, "away_score": 7, "period": 2},
        }

        result = validator.validate_game_state(valid_game)
        assert result.is_valid


# =============================================================================
# E2E Tests: Overtime Scenarios
# =============================================================================


@pytest.mark.e2e
class TestOvertimeScenarios:
    """E2E tests for overtime game scenarios."""

    def test_nfl_overtime_game(self, validator: ESPNDataValidator) -> None:
        """Test NFL overtime game validation."""
        game_id = "401547500"
        metadata = {
            "espn_event_id": game_id,
            "league": "nfl",
            "home_team": {"espn_team_id": "12", "team_name": "Chiefs"},
            "away_team": {"espn_team_id": "33", "team_name": "Broncos"},
        }

        # End of regulation (tied)
        regulation_end = {
            "metadata": metadata,
            "state": {
                "home_score": 24,
                "away_score": 24,
                "period": 4,
                "clock_seconds": Decimal("0"),
            },
        }
        result = validator.validate_game_state(regulation_end)
        assert result.is_valid

        # Overtime
        overtime = {
            "metadata": metadata,
            "state": {
                "home_score": 24,
                "away_score": 24,
                "period": 5,  # OT
                "clock_seconds": Decimal("450"),
                "situation": {"down": 1, "distance": 10, "possession": "KC"},
            },
        }
        result = validator.validate_game_state(overtime)
        assert result.is_valid

        # OT win
        ot_final = {
            "metadata": metadata,
            "state": {
                "home_score": 30,
                "away_score": 24,
                "period": 5,
                "clock_seconds": Decimal("0"),
                "game_status": "final",
            },
        }
        result = validator.validate_game_state(ot_final)
        assert result.is_valid

    def test_nba_multiple_overtime(self, validator: ESPNDataValidator) -> None:
        """Test NBA multiple overtime game."""
        game_id = "401584500"
        metadata = {
            "espn_event_id": game_id,
            "league": "nba",
            "home_team": {"espn_team_id": "13", "team_name": "Lakers"},
            "away_team": {"espn_team_id": "2", "team_name": "Celtics"},
        }

        # Multiple OT periods
        ot_periods = [5, 6, 7]  # 3OT
        for ot in ot_periods:
            game = {
                "metadata": metadata,
                "state": {
                    "home_score": 140 + (ot - 5) * 5,
                    "away_score": 138 + (ot - 5) * 5,
                    "period": ot,
                    "clock_seconds": Decimal("300"),
                },
            }
            result = validator.validate_game_state(game)
            assert result.is_valid, f"OT period {ot} should be valid"


# =============================================================================
# E2E Tests: Production-Like Validation Pipeline
# =============================================================================


@pytest.mark.e2e
class TestProductionPipeline:
    """E2E tests simulating production validation pipeline."""

    def test_batch_validation_pipeline(self) -> None:
        """Test batch validation as it would run in production."""
        # Create fresh validator for batch
        validator = create_validator(strict_mode=False, track_anomalies=True)

        # Simulate batch of game updates
        batch_size = 20
        valid_count = 0
        warning_count = 0
        error_count = 0

        for i in range(batch_size):
            game = {
                "metadata": {
                    "espn_event_id": f"batch_game_{i}",
                    "league": "nfl" if i % 2 == 0 else "nba",
                    "home_team": {"espn_team_id": str(i), "team_name": f"Home{i}"},
                    "away_team": {"espn_team_id": str(i + 100), "team_name": f"Away{i}"},
                },
                "state": {
                    "home_score": i * 7 if i != 5 else -1,  # One invalid
                    "away_score": i * 3,
                    "period": (i % 4) + 1,
                    "clock_seconds": Decimal(str(900 - i * 30)),
                },
            }

            result = validator.validate_game_state(game)

            if result.is_valid:
                valid_count += 1
                if result.has_warnings:
                    warning_count += 1
            else:
                error_count += 1

        # Should have processed all games
        assert valid_count + error_count == batch_size

        # Should have exactly one error (game 5 with negative score)
        assert error_count == 1

        # Generate summary
        all_anomalies = validator.get_all_anomaly_counts()
        games_with_issues = len([c for c in all_anomalies.values() if c > 0])
        assert games_with_issues >= 1

    def test_continuous_monitoring_simulation(self) -> None:
        """Test continuous monitoring workflow."""
        validator = create_validator()

        # Simulate polling updates for a single game
        game_id = "401547600"
        # Include complete metadata to avoid warnings
        metadata = {
            "espn_event_id": game_id,
            "league": "nfl",
            "home_team": {"espn_team_id": "12", "team_name": "Chiefs"},
            "away_team": {"espn_team_id": "33", "team_name": "Broncos"},
        }

        updates = [
            {"home_score": 0, "away_score": 0, "clock": 900, "period": 1},
            {"home_score": 0, "away_score": 0, "clock": 840, "period": 1},
            {"home_score": 7, "away_score": 0, "clock": 756, "period": 1},
            {"home_score": 7, "away_score": 0, "clock": 650, "period": 1},
            {"home_score": 7, "away_score": 7, "clock": 512, "period": 1},
        ]

        prev_state = None
        for update in updates:
            game = {
                "metadata": metadata,
                "state": {
                    "home_score": update["home_score"],
                    "away_score": update["away_score"],
                    "clock_seconds": Decimal(str(update["clock"])),
                    "period": update["period"],
                },
            }

            result = validator.validate_game_state(game, prev_state)
            assert result.is_valid, f"Update {update} should be valid"

            prev_state = {
                "home_score": update["home_score"],
                "away_score": update["away_score"],
            }

        # No anomalies for clean progression with complete metadata
        assert validator.get_anomaly_count(game_id) == 0
