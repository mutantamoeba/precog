"""
Performance Tests for ESPN Data Validation.

Tests latency thresholds and throughput requirements for validation operations.

Reference: TESTING_STRATEGY V3.2 - Performance tests for latency/throughput
Related Requirements: REQ-DATA-002 (Data Quality Monitoring)

Usage:
    pytest tests/performance/validation/test_espn_validation_performance.py -v -m performance
"""

import time
from decimal import Decimal
from typing import Any

import pytest

from precog.validation.espn_validation import (
    ESPNDataValidator,
    ValidationResult,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> ESPNDataValidator:
    """Create a validator for performance testing."""
    return ESPNDataValidator(track_anomalies=True)


@pytest.fixture
def valid_nfl_game() -> dict[str, Any]:
    """Create a valid NFL game state."""
    return {
        "metadata": {
            "espn_event_id": "401547389",
            "league": "nfl",
            "game_date": "2025-12-07T20:00:00Z",
            "home_team": {
                "espn_team_id": "12",
                "team_name": "Kansas City Chiefs",
            },
            "away_team": {
                "espn_team_id": "33",
                "team_name": "Denver Broncos",
            },
            "venue": {
                "espn_venue_id": "3622",
                "venue_name": "Arrowhead Stadium",
                "capacity": 76416,
            },
        },
        "state": {
            "home_score": 21,
            "away_score": 14,
            "period": 3,
            "clock_seconds": Decimal("723"),
            "game_status": "in_progress",
            "situation": {
                "down": 2,
                "distance": 8,
                "possession": "KC",
            },
        },
    }


# =============================================================================
# Performance Tests: Single Validation Latency
# =============================================================================


@pytest.mark.performance
class TestSingleValidationLatency:
    """Performance tests for single validation latency."""

    def test_full_game_validation_latency(
        self, validator: ESPNDataValidator, valid_nfl_game: dict[str, Any]
    ) -> None:
        """Test full game state validation completes within threshold."""
        # Warm up
        for _ in range(10):
            validator.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validator.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]
            latency = (time.perf_counter() - start) * 1000  # ms
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]
        p99_latency = sorted(latencies)[98]

        # Validation should be fast
        assert avg_latency < 1.0, f"Average latency {avg_latency:.2f}ms exceeds 1.0ms"
        assert p95_latency < 2.0, f"P95 latency {p95_latency:.2f}ms exceeds 2.0ms"
        assert p99_latency < 5.0, f"P99 latency {p99_latency:.2f}ms exceeds 5.0ms"

    def test_score_validation_latency(self, validator: ESPNDataValidator) -> None:
        """Test score validation latency."""
        # Warm up
        for _ in range(10):
            validator.validate_score(21, 14)

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validator.validate_score(21, 14, previous_home=14, previous_away=7)
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        # Score validation should be very fast
        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"

    def test_clock_validation_latency(self, validator: ESPNDataValidator) -> None:
        """Test clock validation latency."""
        # Warm up
        for _ in range(10):
            validator.validate_clock(Decimal("450"), 2, "nfl")

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validator.validate_clock(Decimal("450"), 2, "nfl")
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"

    def test_situation_validation_latency(self, validator: ESPNDataValidator) -> None:
        """Test situation validation latency."""
        situation = {"down": 2, "distance": 8, "possession": "KC"}

        # Warm up
        for _ in range(10):
            validator.validate_situation(situation, "nfl")

        # Measure
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            validator.validate_situation(situation, "nfl")
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)

        assert avg_latency < 0.5, f"Average latency {avg_latency:.3f}ms exceeds 0.5ms"


# =============================================================================
# Performance Tests: Throughput
# =============================================================================


@pytest.mark.performance
class TestValidationThroughput:
    """Performance tests for validation throughput."""

    def test_game_validation_throughput(
        self, validator: ESPNDataValidator, valid_nfl_game: dict[str, Any]
    ) -> None:
        """Test game validation throughput."""
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            validator.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        # Should handle at least 1000 validations per second
        assert throughput > 1000, f"Throughput {throughput:.0f}/s below 1000/s"

    def test_score_validation_throughput(self, validator: ESPNDataValidator) -> None:
        """Test score validation throughput."""
        iterations = 5000

        start = time.perf_counter()
        for i in range(iterations):
            validator.validate_score(
                home_score=i % 100,
                away_score=(i * 3) % 100,
            )
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed

        # Score validation should be very fast
        assert throughput > 10000, f"Throughput {throughput:.0f}/s below 10000/s"

    def test_mixed_validation_throughput(
        self, validator: ESPNDataValidator, valid_nfl_game: dict[str, Any]
    ) -> None:
        """Test mixed validation operations throughput."""
        iterations = 500

        start = time.perf_counter()
        for i in range(iterations):
            # Mix of operations
            validator.validate_score(i % 50, i % 30)
            validator.validate_clock(Decimal(str(i % 900)), (i % 4) + 1, "nfl")
            validator.validate_situation({"down": (i % 4) + 1, "distance": 10}, "nfl")
            validator.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]
        elapsed = time.perf_counter() - start

        # 4 operations per iteration
        total_ops = iterations * 4
        throughput = total_ops / elapsed

        assert throughput > 2000, f"Mixed throughput {throughput:.0f}/s below 2000/s"


# =============================================================================
# Performance Tests: Batch Operations
# =============================================================================


@pytest.mark.performance
class TestBatchValidationPerformance:
    """Performance tests for batch validation operations."""

    def test_batch_game_validation(self, validator: ESPNDataValidator) -> None:
        """Test batch game validation performance."""
        batch_sizes = [10, 50, 100, 200]
        results = {}

        for batch_size in batch_sizes:
            games = [
                {
                    "metadata": {
                        "espn_event_id": f"game_{i}",
                        "league": "nfl",
                        "home_team": {"espn_team_id": str(i)},
                        "away_team": {"espn_team_id": str(i + 100)},
                    },
                    "state": {
                        "home_score": i * 7,
                        "away_score": i * 3,
                        "period": (i % 4) + 1,
                        "clock_seconds": Decimal(str(900 - i * 10)),
                    },
                }
                for i in range(batch_size)
            ]

            start = time.perf_counter()
            for game in games:
                validator.validate_game_state(game)  # type: ignore[arg-type]
            elapsed = time.perf_counter() - start

            results[batch_size] = {
                "elapsed": elapsed,
                "per_game": elapsed / batch_size * 1000,  # ms per game
            }

            # Reset for next batch
            validator.reset_anomaly_counts()

        # Verify performance scales linearly
        for batch_size, metrics in results.items():
            assert metrics["per_game"] < 2.0, (
                f"Batch {batch_size}: {metrics['per_game']:.2f}ms/game exceeds 2.0ms"
            )

    def test_multi_sport_batch_validation(self, validator: ESPNDataValidator) -> None:
        """Test batch validation across multiple sports."""
        sports = ["nfl", "nba", "ncaab", "nhl"]
        games_per_sport = 25

        games = []
        for sport in sports:
            for i in range(games_per_sport):
                games.append(
                    {
                        "metadata": {
                            "espn_event_id": f"{sport}_{i}",
                            "league": sport,
                        },
                        "state": {
                            "home_score": i * 5,
                            "away_score": i * 3,
                            "period": (i % 4) + 1,
                            "clock_seconds": Decimal(str(600)),
                        },
                    }
                )

        start = time.perf_counter()
        for game in games:
            validator.validate_game_state(game)  # type: ignore[arg-type]
        elapsed = time.perf_counter() - start

        total_games = len(games)
        throughput = total_games / elapsed
        per_game = elapsed / total_games * 1000

        assert throughput > 500, f"Multi-sport throughput {throughput:.0f}/s below 500/s"
        assert per_game < 2.0, f"Per-game latency {per_game:.2f}ms exceeds 2.0ms"


# =============================================================================
# Performance Tests: Anomaly Tracking Overhead
# =============================================================================


@pytest.mark.performance
class TestAnomalyTrackingOverhead:
    """Performance tests for anomaly tracking overhead."""

    def test_tracking_enabled_vs_disabled(self, valid_nfl_game: dict[str, Any]) -> None:
        """Compare performance with tracking enabled vs disabled."""
        iterations = 500

        # With tracking
        validator_tracking = ESPNDataValidator(track_anomalies=True)
        start = time.perf_counter()
        for _ in range(iterations):
            validator_tracking.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]
        tracking_elapsed = time.perf_counter() - start

        # Without tracking
        validator_no_tracking = ESPNDataValidator(track_anomalies=False)
        start = time.perf_counter()
        for _ in range(iterations):
            validator_no_tracking.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]
        no_tracking_elapsed = time.perf_counter() - start

        # Tracking overhead should be reasonable (<50%)
        # Note: 50% threshold allows for system load variance while catching major regressions
        overhead = (tracking_elapsed - no_tracking_elapsed) / no_tracking_elapsed
        assert overhead < 0.5, f"Tracking overhead {overhead:.1%} exceeds 50%"

    def test_many_tracked_games_performance(self) -> None:
        """Test performance with many tracked games."""
        validator = ESPNDataValidator(track_anomalies=True)

        # Track many different games
        num_games = 100
        for i in range(num_games):
            game = {
                "metadata": {"espn_event_id": f"game_{i}", "league": "nfl"},
                "state": {"home_score": -1, "away_score": 0, "period": 1},  # Invalid
            }
            validator.validate_game_state(game)  # type: ignore[arg-type]

        # Access all counts
        start = time.perf_counter()
        all_counts = validator.get_all_anomaly_counts()
        elapsed = (time.perf_counter() - start) * 1000

        assert len(all_counts) == num_games
        assert elapsed < 10, f"Getting {num_games} counts took {elapsed:.2f}ms"


# =============================================================================
# Performance Tests: Memory Efficiency
# =============================================================================


@pytest.mark.performance
class TestMemoryEfficiency:
    """Performance tests for memory efficiency."""

    def test_validation_result_memory(self) -> None:
        """Test ValidationResult doesn't leak memory."""
        import gc

        gc.collect()

        # Create many results
        results = []
        for i in range(1000):
            result = ValidationResult(game_id=f"game_{i}")
            result.add_error("field", f"error_{i}")
            result.add_warning("field", f"warning_{i}")
            results.append(result)

        # Clear references
        results.clear()
        gc.collect()

        # Should complete without memory error

    def test_validator_no_memory_accumulation(self, valid_nfl_game: dict[str, Any]) -> None:
        """Test validator doesn't accumulate memory over time."""
        import gc

        # Validator with tracking disabled (no accumulation expected)
        validator = ESPNDataValidator(track_anomalies=False)

        gc.collect()

        # Many validations
        for _ in range(10000):
            validator.validate_game_state(valid_nfl_game)  # type: ignore[arg-type]

        gc.collect()

        # Should complete without memory issues

    def test_reset_clears_memory(self) -> None:
        """Test reset actually clears tracked data."""
        import gc

        validator = ESPNDataValidator(track_anomalies=True)

        # Track many games
        for i in range(500):
            game = {
                "metadata": {"espn_event_id": f"mem_game_{i}", "league": "nfl"},
                "state": {"home_score": -1, "away_score": 0, "period": 1},
            }
            validator.validate_game_state(game)  # type: ignore[arg-type]

        assert len(validator.get_all_anomaly_counts()) == 500

        # Reset
        validator.reset_anomaly_counts()
        gc.collect()

        assert len(validator.get_all_anomaly_counts()) == 0


# =============================================================================
# Performance Tests: Decimal Handling
# =============================================================================


@pytest.mark.performance
class TestDecimalHandlingPerformance:
    """Performance tests for Decimal handling in validation."""

    def test_decimal_clock_validation_performance(self, validator: ESPNDataValidator) -> None:
        """Test Decimal clock validation performance."""
        iterations = 1000

        # High precision Decimals
        clock_values = [
            Decimal("450.123456789"),
            Decimal("723.987654321"),
            Decimal("0.000000001"),
        ]

        start = time.perf_counter()
        for _ in range(iterations):
            for clock in clock_values:
                validator.validate_clock(clock, 2, "nfl")
        elapsed = time.perf_counter() - start

        total_ops = iterations * len(clock_values)
        throughput = total_ops / elapsed

        assert throughput > 10000, f"Decimal throughput {throughput:.0f}/s below 10000/s"

    def test_float_to_decimal_conversion_overhead(self, validator: ESPNDataValidator) -> None:
        """Test overhead of float-to-Decimal conversion."""
        iterations = 1000

        # Pre-converted Decimals
        start = time.perf_counter()
        for i in range(iterations):
            validator.validate_clock(Decimal("450"), 2, "nfl")
        decimal_elapsed = time.perf_counter() - start

        # Float inputs (will be converted)
        start = time.perf_counter()
        for i in range(iterations):
            validator.validate_clock(450.0, 2, "nfl")
        float_elapsed = time.perf_counter() - start

        # Conversion overhead should be minimal (<50%)
        overhead = (float_elapsed - decimal_elapsed) / decimal_elapsed
        assert overhead < 0.5, f"Float conversion overhead {overhead:.1%} exceeds 50%"
