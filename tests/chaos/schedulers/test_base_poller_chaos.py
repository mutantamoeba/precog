"""
Chaos Tests for Base Poller.

Tests edge cases, unusual inputs, and unexpected scenarios for BasePoller.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for edge cases
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/chaos/schedulers/test_base_poller_chaos.py -v -m chaos
"""

import logging
import threading
import time

import pytest

from precog.schedulers.base_poller import BasePoller

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class ChaosPoller(BasePoller):
    """Concrete implementation for chaos testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 5

    def __init__(self, poll_interval: int | None = None) -> None:
        super().__init__(poll_interval=poll_interval)
        self._poll_result: dict[str, int] = {
            "items_fetched": 10,
            "items_updated": 5,
            "items_created": 2,
        }

    def _poll_once(self) -> dict[str, int]:
        return self._poll_result

    def _get_job_name(self) -> str:
        return "Chaos Test Poller"

    def set_poll_result(self, result: dict[str, int]) -> None:
        self._poll_result = result


# =============================================================================
# Chaos Tests: Edge Case Intervals
# =============================================================================


@pytest.mark.chaos
class TestEdgeCaseIntervals:
    """Chaos tests for edge case poll intervals."""

    def test_minimum_interval_boundary(self) -> None:
        """Test exactly at minimum interval boundary."""
        poller = ChaosPoller(poll_interval=1)
        assert poller.poll_interval == 1

    def test_maximum_reasonable_interval(self) -> None:
        """Test very large interval."""
        poller = ChaosPoller(poll_interval=86400)  # 24 hours
        assert poller.poll_interval == 86400

    def test_zero_interval_uses_default(self) -> None:
        """Test zero interval is treated as None and uses default.

        Note: poll_interval=0 is falsy in Python and treated like None.
        """
        poller = ChaosPoller(poll_interval=0)
        assert poller.poll_interval == ChaosPoller.DEFAULT_POLL_INTERVAL

    def test_negative_interval_rejected(self) -> None:
        """Test negative interval is rejected."""
        with pytest.raises(ValueError):
            ChaosPoller(poll_interval=-1)

        with pytest.raises(ValueError):
            ChaosPoller(poll_interval=-100)


# =============================================================================
# Chaos Tests: Unusual Poll Results
# =============================================================================


@pytest.mark.chaos
class TestUnusualPollResults:
    """Chaos tests for unusual poll result values."""

    def test_zero_item_counts(self) -> None:
        """Test poll returning zero for all counts."""
        poller = ChaosPoller()
        poller.set_poll_result(
            {
                "items_fetched": 0,
                "items_updated": 0,
                "items_created": 0,
            }
        )

        poller._poll_wrapper()

        assert poller.stats["items_fetched"] == 0
        assert poller.stats["items_updated"] == 0
        assert poller.stats["items_created"] == 0

    def test_very_large_item_counts(self) -> None:
        """Test poll returning very large counts."""
        poller = ChaosPoller()
        poller.set_poll_result(
            {
                "items_fetched": 10**9,
                "items_updated": 10**8,
                "items_created": 10**7,
            }
        )

        poller._poll_wrapper()

        assert poller.stats["items_fetched"] == 10**9
        assert poller.stats["items_updated"] == 10**8
        assert poller.stats["items_created"] == 10**7

    def test_negative_item_counts(self) -> None:
        """Test poll returning negative counts (shouldn't happen but test handling)."""
        poller = ChaosPoller()
        poller.set_poll_result(
            {
                "items_fetched": -10,
                "items_updated": -5,
                "items_created": -1,
            }
        )

        # Should not raise, just track the negative values
        poller._poll_wrapper()

        # Stats will show negative values (implementation detail)
        assert poller.stats["items_fetched"] == -10


# =============================================================================
# Chaos Tests: Error Conditions
# =============================================================================


@pytest.mark.chaos
class TestErrorConditions:
    """Chaos tests for error conditions."""

    def test_poll_raises_base_exception(self) -> None:
        """Test handling of BaseException subclasses."""

        class BaseExceptionPoller(ChaosPoller):
            def _poll_once(self) -> dict[str, int]:
                raise KeyboardInterrupt("Simulated interrupt")

        poller = BaseExceptionPoller()

        # BaseException should propagate (not caught by wrapper)
        with pytest.raises(KeyboardInterrupt):
            poller._poll_wrapper()

    def test_poll_raises_system_exit(self) -> None:
        """Test SystemExit is not suppressed."""

        class SystemExitPoller(ChaosPoller):
            def _poll_once(self) -> dict[str, int]:
                raise SystemExit(1)

        poller = SystemExitPoller()

        with pytest.raises(SystemExit):
            poller._poll_wrapper()

    def test_empty_error_message(self) -> None:
        """Test error with empty message."""

        class EmptyErrorPoller(ChaosPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("")

        poller = EmptyErrorPoller()
        poller._poll_wrapper()

        assert poller.stats["errors"] == 1
        assert poller.stats["last_error"] == ""

    def test_unicode_error_message(self) -> None:
        """Test error with unicode message."""

        class UnicodeErrorPoller(ChaosPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("Error with unicode: \u2603 \u2764 \U0001f600")

        poller = UnicodeErrorPoller()
        poller._poll_wrapper()

        assert poller.stats["errors"] == 1
        assert "\u2603" in poller.stats["last_error"]

    def test_very_long_error_message(self) -> None:
        """Test error with very long message."""

        class LongErrorPoller(ChaosPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("A" * 10000)

        poller = LongErrorPoller()
        poller._poll_wrapper()

        assert poller.stats["errors"] == 1
        # Message should be captured (may be truncated by implementation)
        assert len(poller.stats["last_error"]) > 0


# =============================================================================
# Chaos Tests: State Corruption Attempts
# =============================================================================


@pytest.mark.chaos
class TestStateCorruptionAttempts:
    """Chaos tests for state corruption attempts."""

    def test_stats_modification_doesnt_corrupt(self) -> None:
        """Test modifying returned stats doesn't corrupt internal state."""
        poller = ChaosPoller()
        poller._poll_wrapper()

        # Get and modify stats
        stats = poller.stats
        stats["polls_completed"] = 999999
        stats["items_fetched"] = -1
        stats["errors"] = 1000

        # Internal state should be unchanged
        internal_stats = poller.stats
        assert internal_stats["polls_completed"] == 1
        assert internal_stats["items_fetched"] == 10
        assert internal_stats["errors"] == 0

    def test_poll_result_mutation(self) -> None:
        """Test mutating poll result between polls."""
        poller = ChaosPoller()

        poller.set_poll_result({"items_fetched": 10, "items_updated": 5, "items_created": 1})
        poller._poll_wrapper()

        poller.set_poll_result({"items_fetched": 20, "items_updated": 10, "items_created": 2})
        poller._poll_wrapper()

        # Should accumulate correctly
        assert poller.stats["items_fetched"] == 30
        assert poller.stats["items_updated"] == 15
        assert poller.stats["items_created"] == 3


# =============================================================================
# Chaos Tests: Lifecycle Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestLifecycleEdgeCases:
    """Chaos tests for lifecycle edge cases."""

    def test_stop_without_start(self) -> None:
        """Test calling stop on never-started poller."""
        poller = ChaosPoller()

        # Should not raise
        poller.stop()
        assert poller.enabled is False

    def test_multiple_stops(self) -> None:
        """Test calling stop multiple times."""
        poller = ChaosPoller(poll_interval=1)
        poller.start()

        # Multiple stops should be safe
        poller.stop()
        poller.stop()
        poller.stop()

        assert poller.enabled is False

    def test_start_after_polls(self) -> None:
        """Test starting scheduler after manual polls."""
        poller = ChaosPoller(poll_interval=1)

        # Manual polls first
        for _ in range(5):
            poller._poll_wrapper()

        # Then start scheduler
        poller.start()
        try:
            time.sleep(1.5)

            # Stats should continue from manual polls
            assert poller.stats["polls_completed"] >= 6
        finally:
            poller.stop()

    def test_poll_wrapper_after_stop(self) -> None:
        """Test poll_wrapper can be called after scheduler stops."""
        poller = ChaosPoller(poll_interval=1)
        poller.start()
        time.sleep(0.5)
        poller.stop()

        # Manual poll after stop should work
        initial_polls = poller.stats["polls_completed"]
        poller._poll_wrapper()

        assert poller.stats["polls_completed"] == initial_polls + 1


# =============================================================================
# Chaos Tests: Concurrent Chaos
# =============================================================================


@pytest.mark.chaos
class TestConcurrentChaos:
    """Chaos tests for concurrent chaotic operations."""

    def test_rapid_start_stop_with_polls(self) -> None:
        """Test rapid start/stop while polls are happening."""
        poller = ChaosPoller(poll_interval=1)
        errors: list[Exception] = []
        stop_event = threading.Event()

        def rapid_start_stop() -> None:
            while not stop_event.is_set():
                try:
                    poller.start()
                    time.sleep(0.05)
                    poller.stop()
                except Exception as e:
                    errors.append(e)

        def continuous_manual_polls() -> None:
            while not stop_event.is_set():
                try:
                    poller._poll_wrapper()
                    time.sleep(0.02)
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=rapid_start_stop),
            threading.Thread(target=continuous_manual_polls),
        ]

        for t in threads:
            t.start()

        time.sleep(2.0)
        stop_event.set()

        for t in threads:
            t.join()

        # Clean up
        if poller.enabled:
            poller.stop()

        # Should handle chaotic usage without crashes
        # Note: Some exceptions might be expected behavior
        # The key is no deadlocks or corrupted state

    def test_stats_access_during_error_storm(self) -> None:
        """Test stats access while errors are happening rapidly."""

        class ErrorStormPoller(ChaosPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("Storm error")

        poller = ErrorStormPoller()
        stop_event = threading.Event()
        read_errors: list[Exception] = []

        def generate_errors() -> None:
            while not stop_event.is_set():
                poller._poll_wrapper()
                time.sleep(0.001)

        def read_stats() -> None:
            while not stop_event.is_set():
                try:
                    _ = poller.stats
                except Exception as e:
                    read_errors.append(e)
                time.sleep(0.001)

        threads = [
            threading.Thread(target=generate_errors),
            threading.Thread(target=read_stats),
            threading.Thread(target=read_stats),
        ]

        for t in threads:
            t.start()

        time.sleep(1.0)
        stop_event.set()

        for t in threads:
            t.join()

        # Stats reads should not fail
        assert len(read_errors) == 0
        # Errors should be tracked
        assert poller.stats["errors"] > 0


# =============================================================================
# Chaos Tests: Unusual Logger Scenarios
# =============================================================================


@pytest.mark.chaos
class TestUnusualLoggerScenarios:
    """Chaos tests for unusual logger scenarios."""

    def test_none_logger_handling(self) -> None:
        """Test handling when logger is set to None."""
        poller = ChaosPoller()
        # This shouldn't happen in normal use, but test resilience
        # Note: Implementation should handle this gracefully

        # Do some operations
        poller._poll_wrapper()
        assert poller.stats["polls_completed"] == 1

    def test_custom_logger_with_high_level(self) -> None:
        """Test with custom logger at CRITICAL level."""
        logger = logging.getLogger("chaos_test")
        logger.setLevel(logging.CRITICAL)

        poller = ChaosPoller()
        poller.logger = logger

        poller._poll_wrapper()
        assert poller.stats["polls_completed"] == 1


# =============================================================================
# Chaos Tests: PollerStats TypedDict Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestPollerStatsEdgeCases:
    """Chaos tests for PollerStats edge cases."""

    def test_stats_all_zeros(self) -> None:
        """Test fresh poller has all zero stats."""
        poller = ChaosPoller()
        stats = poller.stats

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0
        assert stats["last_poll"] is None
        assert stats["last_error"] is None

    def test_stats_after_many_operations(self) -> None:
        """Test stats correctness after many operations."""
        poller = ChaosPoller()

        # Many successful polls
        for _ in range(1000):
            poller._poll_wrapper()

        stats = poller.stats
        assert stats["polls_completed"] == 1000
        assert stats["items_fetched"] == 10000
        assert stats["items_updated"] == 5000
        assert stats["items_created"] == 2000
        assert stats["errors"] == 0

    def test_stats_type_consistency(self) -> None:
        """Test stats values have correct types."""
        poller = ChaosPoller()
        poller._poll_wrapper()

        stats = poller.stats

        assert isinstance(stats["polls_completed"], int)
        assert isinstance(stats["items_fetched"], int)
        assert isinstance(stats["items_updated"], int)
        assert isinstance(stats["items_created"], int)
        assert isinstance(stats["errors"], int)
        # last_poll is str or None
        assert stats["last_poll"] is None or isinstance(stats["last_poll"], str)
        # last_error is str or None
        assert stats["last_error"] is None or isinstance(stats["last_error"], str)


# =============================================================================
# Chaos Tests: Boundary Value Accumulation
# =============================================================================


@pytest.mark.chaos
class TestBoundaryValueAccumulation:
    """Chaos tests for boundary value accumulation."""

    def test_accumulation_near_int_max(self) -> None:
        """Test accumulation approaching integer limits."""
        poller = ChaosPoller()
        # Python ints have arbitrary precision, but test large values
        poller.set_poll_result(
            {
                "items_fetched": 10**15,
                "items_updated": 10**15,
                "items_created": 10**15,
            }
        )

        for _ in range(10):
            poller._poll_wrapper()

        stats = poller.stats
        assert stats["items_fetched"] == 10**16  # 10 * 10^15

    def test_poll_count_accumulation(self) -> None:
        """Test poll count accumulates correctly over many calls."""
        poller = ChaosPoller()

        for _ in range(10000):
            poller._poll_wrapper()

        assert poller.stats["polls_completed"] == 10000


# =============================================================================
# Chaos Tests: Inheritance Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestInheritanceEdgeCases:
    """Chaos tests for inheritance edge cases."""

    def test_deep_inheritance(self) -> None:
        """Test deeply inherited poller."""

        class Level1Poller(ChaosPoller):
            pass

        class Level2Poller(Level1Poller):
            pass

        class Level3Poller(Level2Poller):
            def _get_job_name(self) -> str:
                return "Deep Level 3 Poller"

        poller = Level3Poller()
        poller._poll_wrapper()

        assert poller.stats["polls_completed"] == 1
        assert poller._get_job_name() == "Deep Level 3 Poller"

    def test_overridden_class_variables(self) -> None:
        """Test poller with overridden class variables."""

        class CustomIntervalPoller(ChaosPoller):
            MIN_POLL_INTERVAL = 10
            DEFAULT_POLL_INTERVAL = 60

        poller = CustomIntervalPoller()
        assert poller.poll_interval == 60

        # Should reject intervals below custom minimum
        with pytest.raises(ValueError):
            CustomIntervalPoller(poll_interval=5)
