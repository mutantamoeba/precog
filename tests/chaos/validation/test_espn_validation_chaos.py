"""
Chaos Tests for ESPN Data Validation.

Tests behavior under chaotic conditions including malformed data,
extreme values, unexpected types, and recovery scenarios.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for edge cases
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/chaos/validation/test_espn_validation_chaos.py -v -m chaos
"""

from decimal import Decimal

import pytest

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> ESPNDataValidator:
    """Create a validator for chaos testing."""
    return ESPNDataValidator()


# =============================================================================
# Chaos Tests: Malformed Data
# =============================================================================


@pytest.mark.chaos
class TestMalformedData:
    """Chaos tests for malformed data handling."""

    def test_completely_empty_game(self, validator: ESPNDataValidator) -> None:
        """Test handling of completely empty game dict."""
        result = validator.validate_game_state({})
        # Should handle gracefully (error for missing event ID)
        assert not result.is_valid

    def test_missing_metadata(self, validator: ESPNDataValidator) -> None:
        """Test handling of missing metadata."""
        game = {"state": {"home_score": 14, "away_score": 7}}
        result = validator.validate_game_state(game)
        assert not result.is_valid

    def test_missing_state(self, validator: ESPNDataValidator) -> None:
        """Test handling of missing state."""
        game = {
            "metadata": {"espn_event_id": "123", "league": "nfl"},
        }
        # Should not crash
        result = validator.validate_game_state(game)
        assert result.game_id == "123"

    def test_none_values_in_metadata(self, validator: ESPNDataValidator) -> None:
        """Test handling of None values in metadata."""
        game = {
            "metadata": {
                "espn_event_id": None,
                "league": None,
                "home_team": None,
                "away_team": None,
            },
            "state": {"home_score": 14, "away_score": 7},
        }
        result = validator.validate_game_state(game)
        # Should report errors/warnings but not crash
        assert result.has_errors or result.has_warnings

    def test_none_values_in_state(self, validator: ESPNDataValidator) -> None:
        """Test handling of None values in state."""
        game = {
            "metadata": {"espn_event_id": "123", "league": "nfl"},
            "state": {
                "home_score": None,
                "away_score": None,
                "period": None,
                "clock_seconds": None,
            },
        }
        validator.validate_game_state(game)
        # Should not crash


# =============================================================================
# Chaos Tests: Extreme Values
# =============================================================================


@pytest.mark.chaos
class TestExtremeValues:
    """Chaos tests for extreme value handling."""

    def test_extremely_high_scores(self, validator: ESPNDataValidator) -> None:
        """Test handling of extremely high scores."""
        result = validator.validate_score(
            home_score=999999999,
            away_score=888888888,
        )
        # High scores are technically valid (no upper limit)
        assert result.is_valid

    def test_extremely_negative_scores(self, validator: ESPNDataValidator) -> None:
        """Test handling of extremely negative scores."""
        result = validator.validate_score(
            home_score=-999999999,
            away_score=-888888888,
        )
        assert not result.is_valid
        assert len(result.errors) >= 2

    def test_extremely_long_period(self, validator: ESPNDataValidator) -> None:
        """Test handling of extremely long overtime."""
        result = validator.validate_clock(
            clock_seconds=Decimal("500"),
            period=100,  # 100 OT periods
            league="nfl",
        )
        # Should generate warning for unusual period
        assert result.has_warnings

    def test_extremely_large_clock(self, validator: ESPNDataValidator) -> None:
        """Test handling of extremely large clock value."""
        result = validator.validate_clock(
            clock_seconds=Decimal("999999999"),
            period=1,
            league="nfl",
        )
        # Should generate warning for clock exceeding period
        assert result.has_warnings

    def test_extremely_high_precision_decimal(self, validator: ESPNDataValidator) -> None:
        """Test handling of high precision Decimal clock."""
        # 50 decimal places
        high_precision = Decimal("450." + "1" * 50)
        result = validator.validate_clock(
            clock_seconds=high_precision,
            period=2,
            league="nfl",
        )
        assert result.is_valid

    def test_max_int_values(self, validator: ESPNDataValidator) -> None:
        """Test handling of maximum integer values."""
        import sys

        result = validator.validate_score(
            home_score=sys.maxsize,
            away_score=sys.maxsize,
        )
        # Should handle without overflow
        assert result.is_valid


# =============================================================================
# Chaos Tests: Wrong Types
# =============================================================================


@pytest.mark.chaos
class TestWrongTypes:
    """Chaos tests for wrong type handling."""

    def test_string_scores(self, validator: ESPNDataValidator) -> None:
        """Test handling of string scores."""
        game = {
            "metadata": {"espn_event_id": "123", "league": "nfl"},
            "state": {
                "home_score": "fourteen",  # Intentionally wrong type for chaos test
                "away_score": "seven",  # Intentionally wrong type for chaos test
            },
        }
        # Should handle without crash (Python comparison may work)
        try:
            validator.validate_game_state(game)
        except (TypeError, ValueError):
            pass  # Expected for comparison

    def test_list_as_metadata(self, validator: ESPNDataValidator) -> None:
        """Test handling of list instead of dict for metadata."""
        game = {
            "metadata": ["espn_event_id", "123"],  # Wrong type
            "state": {"home_score": 14},
        }
        # Should handle gracefully or raise expected exception
        try:
            validator.validate_game_state(game)
        except (TypeError, AttributeError, ValueError):
            pass  # Expected - validator may not handle non-dict metadata

    def test_nested_wrong_types(self, validator: ESPNDataValidator) -> None:
        """Test handling of nested wrong types."""
        game = {
            "metadata": {
                "espn_event_id": 123,  # Should be string
                "league": ["nfl"],  # Should be string
                "home_team": "Chiefs",  # Should be dict
            },
            "state": {"home_score": 14, "away_score": 7},
        }
        # Should handle gracefully or raise expected exception
        try:
            result = validator.validate_game_state(game)
            # If no exception, should have errors or warnings for wrong types
            assert result.has_errors or result.has_warnings
        except (TypeError, AttributeError):
            pass  # Expected - validator may not handle string as team dict

    def test_boolean_as_score(self, validator: ESPNDataValidator) -> None:
        """Test handling of boolean as score."""
        # Note: In Python, True == 1 and False == 0
        validator.validate_score(
            home_score=True,  # Intentionally wrong type (bool is subtype of int)
            away_score=False,  # Intentionally wrong type (bool is subtype of int)
        )
        # May pass due to Python's boolean-int equivalence
        # But should not crash


# =============================================================================
# Chaos Tests: Edge Case Situations
# =============================================================================


@pytest.mark.chaos
class TestEdgeCaseSituations:
    """Chaos tests for edge case game situations."""

    def test_zero_down_in_football(self, validator: ESPNDataValidator) -> None:
        """Test down = 0 (invalid for football)."""
        result = validator.validate_situation(
            situation={"down": 0, "distance": 10},
            league="nfl",
        )
        assert result.has_warnings

    def test_negative_down_except_minus_one(self, validator: ESPNDataValidator) -> None:
        """Test various negative down values."""
        for down in [-2, -5, -10, -100]:
            result = validator.validate_situation(
                situation={"down": down, "distance": 10},
                league="nfl",
            )
            assert result.has_warnings, f"Down {down} should warn"

    def test_extremely_long_distance(self, validator: ESPNDataValidator) -> None:
        """Test unrealistic distance to go."""
        result = validator.validate_situation(
            situation={"down": 1, "distance": 100},  # 100 yards to go
            league="nfl",
        )
        # Valid (unusual but possible after penalty)
        assert result.is_valid

    def test_empty_string_possession(self, validator: ESPNDataValidator) -> None:
        """Test empty string possession."""
        result = validator.validate_situation(
            situation={"down": 1, "distance": 10, "possession": ""},
            league="nfl",
        )
        # Empty string is valid string type
        assert result.is_valid

    def test_numeric_possession(self, validator: ESPNDataValidator) -> None:
        """Test numeric possession (wrong type)."""
        result = validator.validate_situation(
            situation={"down": 1, "distance": 10, "possession": 12},
            league="nfl",
        )
        # Should warn about non-string possession
        assert result.has_warnings


# =============================================================================
# Chaos Tests: Unknown Leagues
# =============================================================================


@pytest.mark.chaos
class TestUnknownLeagues:
    """Chaos tests for unknown league handling."""

    def test_unknown_league_clock_validation(self, validator: ESPNDataValidator) -> None:
        """Test clock validation with unknown league."""
        result = validator.validate_clock(
            clock_seconds=Decimal("600"),
            period=2,
            league="unknown_sport",
        )
        # Should not crash, may skip league-specific checks
        assert isinstance(result, ValidationResult)

    def test_unknown_league_situation_validation(self, validator: ESPNDataValidator) -> None:
        """Test situation validation with unknown league."""
        result = validator.validate_situation(
            situation={"some_field": "some_value"},
            league="cricket",
        )
        # Should not crash (no sport-specific rules apply)
        assert result.is_valid

    def test_empty_league(self, validator: ESPNDataValidator) -> None:
        """Test validation with empty league string."""
        game = {
            "metadata": {"espn_event_id": "123", "league": ""},
            "state": {"home_score": 14, "away_score": 7},
        }
        validator.validate_game_state(game)
        # Should handle gracefully


# =============================================================================
# Chaos Tests: Concurrent Validation Issues
# =============================================================================


@pytest.mark.chaos
class TestMultipleValidationIssues:
    """Chaos tests for games with multiple issues."""

    def test_all_fields_invalid(self, validator: ESPNDataValidator) -> None:
        """Test game with all fields invalid."""
        game = {
            "metadata": {
                "espn_event_id": "",  # Empty (warning)
                "league": "nfl",
                "home_team": {},  # Empty (warning)
                "away_team": {},  # Empty (warning)
                "venue": {"capacity": -1},  # Invalid (warning)
            },
            "state": {
                "home_score": -10,  # Invalid (error)
                "away_score": -5,  # Invalid (error)
                "period": -1,  # Invalid (error)
                "clock_seconds": Decimal("-100"),  # Invalid (error)
            },
        }

        result = validator.validate_game_state(game)

        # Should have multiple errors
        assert not result.is_valid
        assert len(result.errors) >= 3

    def test_cascading_validation_issues(self, validator: ESPNDataValidator) -> None:
        """Test that validation continues after finding first issue."""
        game = {
            "metadata": {
                "espn_event_id": "123",
                "league": "nfl",
            },
            "state": {
                "home_score": -1,  # First error
                "away_score": -2,  # Second error
                "period": -1,  # Third error
            },
        }

        result = validator.validate_game_state(game)

        # Should find all errors, not stop at first
        assert len(result.errors) >= 3


# =============================================================================
# Chaos Tests: Anomaly Tracking Under Stress
# =============================================================================


@pytest.mark.chaos
class TestAnomalyTrackingChaos:
    """Chaos tests for anomaly tracking under stress."""

    def test_many_unique_games_tracking(self, validator: ESPNDataValidator) -> None:
        """Test tracking many unique games."""
        for i in range(500):
            game = {
                "metadata": {"espn_event_id": f"chaos_game_{i}", "league": "nfl"},
                "state": {"home_score": -1, "away_score": 0, "period": 1},
            }
            validator.validate_game_state(game)

        all_counts = validator.get_all_anomaly_counts()
        assert len(all_counts) == 500

    def test_repeated_validation_same_game(self, validator: ESPNDataValidator) -> None:
        """Test repeated validation of same game accumulates correctly."""
        game = {
            "metadata": {"espn_event_id": "repeat_test", "league": "nfl"},
            "state": {"home_score": -1, "away_score": 0, "period": 1},
        }

        for _ in range(100):
            validator.validate_game_state(game)

        count = validator.get_anomaly_count("repeat_test")
        assert count >= 100

    def test_get_count_nonexistent_game(self, validator: ESPNDataValidator) -> None:
        """Test getting count for non-existent game."""
        count = validator.get_anomaly_count("nonexistent_game_xyz")
        assert count == 0


# =============================================================================
# Chaos Tests: ValidationIssue Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestValidationIssueChaos:
    """Chaos tests for ValidationIssue edge cases."""

    def test_issue_with_none_value(self) -> None:
        """Test ValidationIssue with None value."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            field="test",
            message="test message",
            value=None,
            expected=None,
        )
        # Should have valid string representation
        str_repr = str(issue)
        assert "ERROR" in str_repr
        assert "test" in str_repr

    def test_issue_with_complex_value(self) -> None:
        """Test ValidationIssue with complex value."""
        issue = ValidationIssue(
            level=ValidationLevel.WARNING,
            field="complex",
            message="complex value",
            value={"nested": {"deeply": [1, 2, 3]}},
            expected={"simple": "value"},
        )
        str_repr = str(issue)
        assert "WARNING" in str_repr

    def test_issue_with_very_long_message(self) -> None:
        """Test ValidationIssue with very long message."""
        long_message = "A" * 10000
        issue = ValidationIssue(
            level=ValidationLevel.INFO,
            field="long",
            message=long_message,
        )
        str_repr = str(issue)
        assert long_message in str_repr


# =============================================================================
# Chaos Tests: ValidationResult Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestValidationResultChaos:
    """Chaos tests for ValidationResult edge cases."""

    def test_add_many_issues(self) -> None:
        """Test adding many issues to result."""
        result = ValidationResult(game_id="many_issues")

        for i in range(1000):
            result.add_error(f"field_{i}", f"error_{i}")
            result.add_warning(f"field_{i}", f"warning_{i}")
            result.add_info(f"field_{i}", f"info_{i}")

        assert len(result.issues) == 3000
        assert len(result.errors) == 1000
        assert len(result.warnings) == 1000

    def test_empty_game_id(self) -> None:
        """Test ValidationResult with empty game_id."""
        result = ValidationResult(game_id="")
        result.add_error("field", "message")

        assert result.game_id == ""
        assert not result.is_valid

    def test_log_issues_many_levels(self, validator: ESPNDataValidator) -> None:
        """Test logging issues at all levels."""
        result = ValidationResult(game_id="log_test")
        result.add_error("e", "error")
        result.add_warning("w", "warning")
        result.add_info("i", "info")

        # Should not crash
        result.log_issues()


# =============================================================================
# Chaos Tests: Recovery After Errors
# =============================================================================


@pytest.mark.chaos
class TestErrorRecovery:
    """Chaos tests for validator recovery after errors."""

    def test_validator_usable_after_invalid_data(self, validator: ESPNDataValidator) -> None:
        """Test validator remains usable after processing invalid data."""
        # Process invalid data
        invalid_game = {
            "metadata": {"espn_event_id": "invalid", "league": "nfl"},
            "state": {"home_score": -999, "away_score": -999, "period": -99},
        }
        validator.validate_game_state(invalid_game)

        # Should still work for valid data
        valid_game = {
            "metadata": {"espn_event_id": "valid", "league": "nfl"},
            "state": {"home_score": 14, "away_score": 7, "period": 2},
        }
        result = validator.validate_game_state(valid_game)
        assert result.is_valid

    def test_validator_usable_after_exception_in_data(self, validator: ESPNDataValidator) -> None:
        """Test validator survives potential exception-causing data."""
        problematic_inputs = [
            {},
            {"metadata": None},
            {"state": []},
        ]

        for bad_input in problematic_inputs:
            try:
                validator.validate_game_state(bad_input)
            except (TypeError, AttributeError, KeyError):
                pass  # May raise, but validator should survive

        # Validator should still work
        valid_game = {
            "metadata": {"espn_event_id": "after_bad", "league": "nfl"},
            "state": {"home_score": 14, "away_score": 7},
        }
        validator.validate_game_state(valid_game)
        # Should process without crash
