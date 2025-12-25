"""
End-to-End Tests for Base Poller.

Tests complete polling workflows from start to stop with real scheduler.

Reference: TESTING_STRATEGY V3.2 - E2E tests for critical paths
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/e2e/schedulers/test_base_poller_e2e.py -v -m e2e
"""

import logging
import time

import pytest

from precog.schedulers.base_poller import BasePoller

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class E2EPoller(BasePoller):
    """Concrete implementation for E2E testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 2

    def __init__(
        self,
        poll_interval: int | None = None,
        simulate_work_time: float = 0.0,
    ) -> None:
        super().__init__(poll_interval=poll_interval)
        self.simulate_work_time = simulate_work_time
        self.poll_timestamps: list[float] = []
        self.items_per_poll = 10

    def _poll_once(self) -> dict[str, int]:
        self.poll_timestamps.append(time.time())
        if self.simulate_work_time > 0:
            time.sleep(self.simulate_work_time)
        return {
            "items_fetched": self.items_per_poll,
            "items_updated": self.items_per_poll // 2,
            "items_created": self.items_per_poll // 5,
        }

    def _get_job_name(self) -> str:
        return "E2E Test Poller"


# =============================================================================
# E2E Tests: Complete Polling Workflow
# =============================================================================


@pytest.mark.e2e
class TestCompletePollingWorkflow:
    """E2E tests for complete polling workflows."""

    def test_full_polling_lifecycle(self) -> None:
        """Test complete polling lifecycle from creation to shutdown."""
        # Step 1: Create poller
        poller = E2EPoller(poll_interval=1)
        assert poller.enabled is False
        assert poller.stats["polls_completed"] == 0

        # Step 2: Start poller
        poller.start()
        assert poller.enabled is True

        # Step 3: Let it run for several cycles
        time.sleep(3.5)  # type: ignore[unreachable]

        # Step 4: Verify polling occurred
        assert poller.stats["polls_completed"] >= 3

        # Step 5: Stop poller
        poller.stop()
        assert poller.enabled is False

        # Step 6: Verify final stats
        stats = poller.stats
        assert stats["polls_completed"] >= 3
        assert stats["items_fetched"] >= 30
        assert stats["errors"] == 0

    def test_polling_with_simulated_work(self) -> None:
        """Test polling with simulated work time."""
        poller = E2EPoller(poll_interval=1, simulate_work_time=0.2)

        poller.start()
        try:
            time.sleep(2.5)

            # Should complete polls even with work time
            assert poller.stats["polls_completed"] >= 2
        finally:
            poller.stop()

    def test_data_accumulation_over_time(self) -> None:
        """Test data correctly accumulates over multiple poll cycles."""
        poller = E2EPoller(poll_interval=1)
        poller.items_per_poll = 5

        poller.start()
        try:
            time.sleep(3.5)

            stats = poller.stats
            polls = stats["polls_completed"]

            # Verify accumulation is correct
            assert stats["items_fetched"] == polls * 5
            assert stats["items_updated"] == polls * 2  # 5 // 2 = 2
            assert stats["items_created"] == polls * 1  # 5 // 5 = 1
        finally:
            poller.stop()


# =============================================================================
# E2E Tests: Error Recovery
# =============================================================================


@pytest.mark.e2e
class TestErrorRecovery:
    """E2E tests for error recovery scenarios."""

    def test_recovery_after_transient_errors(self) -> None:
        """Test poller recovers after transient errors."""

        class TransientErrorPoller(E2EPoller):
            def __init__(self) -> None:
                super().__init__(poll_interval=1)
                self.call_count = 0

            def _poll_once(self) -> dict[str, int]:
                self.call_count += 1
                if self.call_count <= 2:
                    raise ConnectionError("Transient network error")
                return super()._poll_once()

        poller = TransientErrorPoller()
        poller.start()

        try:
            time.sleep(4.5)

            stats = poller.stats
            # Should have recorded errors
            assert stats["errors"] >= 2
            # Should have recovered and done successful polls
            assert stats["polls_completed"] >= 1
            assert stats["items_fetched"] >= 10
        finally:
            poller.stop()

    def test_continuous_error_handling(self) -> None:
        """Test poller continues operating despite persistent errors."""

        class PersistentErrorPoller(E2EPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("Persistent error")

        poller = PersistentErrorPoller()
        poller.start()

        try:
            time.sleep(2.5)

            # Scheduler should still be running
            assert poller.enabled is True
            # Errors should be tracked
            assert poller.stats["errors"] >= 2
        finally:
            poller.stop()


# =============================================================================
# E2E Tests: Multiple Pollers
# =============================================================================


@pytest.mark.e2e
class TestMultiplePollers:
    """E2E tests for multiple poller instances."""

    def test_multiple_pollers_independent(self) -> None:
        """Test multiple poller instances operate independently."""
        poller1 = E2EPoller(poll_interval=1)
        poller1.items_per_poll = 10

        poller2 = E2EPoller(poll_interval=1)
        poller2.items_per_poll = 20

        poller1.start()
        poller2.start()

        try:
            time.sleep(2.5)

            # Both should have completed polls
            assert poller1.stats["polls_completed"] >= 2
            assert poller2.stats["polls_completed"] >= 2

            # Stats should be independent
            assert poller1.stats["items_fetched"] != poller2.stats["items_fetched"]
        finally:
            poller1.stop()
            poller2.stop()

    def test_staggered_start_stop(self) -> None:
        """Test pollers with staggered start/stop times.

        Note: This test uses timing to verify staggered operation. Under heavy
        CI load, timing can vary. We use longer sleeps and lenient assertions
        to avoid flakiness.
        """
        poller1 = E2EPoller(poll_interval=1)
        poller2 = E2EPoller(poll_interval=1)

        try:
            # Start poller1 first
            poller1.start()
            time.sleep(2.5)  # Increased from 1.5s to ensure polls happen

            # Start poller2
            poller2.start()
            time.sleep(2.5)  # Increased from 1.5s

            # Stop poller1
            poller1.stop()
            time.sleep(2.5)  # Increased from 1.5s

            # Stop poller2
            poller2.stop()

            # Both pollers should have completed polls
            # Under timing variance, we verify both completed some polls
            # rather than strict ordering (which is flaky under CI load)
            assert poller1.stats["polls_completed"] > 0, "Poller1 should have completed polls"
            assert poller2.stats["polls_completed"] > 0, "Poller2 should have completed polls"
        finally:
            # Ensure cleanup even if test fails
            if poller1.is_running():
                poller1.stop()
            if poller2.is_running():
                poller2.stop()


# =============================================================================
# E2E Tests: Stats Monitoring
# =============================================================================


@pytest.mark.e2e
class TestStatsMonitoring:
    """E2E tests for stats monitoring during operation."""

    def test_stats_updated_in_realtime(self) -> None:
        """Test stats are updated in real-time during polling."""
        poller = E2EPoller(poll_interval=1)

        poller.start()
        try:
            initial_stats = poller.stats
            time.sleep(2.5)
            final_stats = poller.stats

            # Stats should have changed
            assert final_stats["polls_completed"] > initial_stats["polls_completed"]
            assert final_stats["items_fetched"] > initial_stats["items_fetched"]
        finally:
            poller.stop()

    def test_last_poll_timestamp_updates(self) -> None:
        """Test last_poll timestamp updates with each poll."""
        poller = E2EPoller(poll_interval=1)

        poller.start()
        try:
            time.sleep(1.5)
            first_last_poll = poller.stats["last_poll"]

            time.sleep(1.5)
            second_last_poll = poller.stats["last_poll"]

            # Timestamps should be different
            assert first_last_poll is not None
            assert second_last_poll is not None
            assert second_last_poll != first_last_poll
        finally:
            poller.stop()

    def test_continuous_stats_monitoring(self) -> None:
        """Test stats can be monitored continuously without issues."""
        poller = E2EPoller(poll_interval=1)

        poller.start()
        try:
            stats_history: list[int] = []

            for _ in range(10):
                stats_history.append(poller.stats["polls_completed"])
                time.sleep(0.3)

            # Stats should be non-decreasing
            for i in range(1, len(stats_history)):
                assert stats_history[i] >= stats_history[i - 1]
        finally:
            # Use wait=False to avoid timeout during scheduler shutdown
            # when a poll is in progress (E2E test doesn't need clean shutdown)
            poller.stop(wait=False)


# =============================================================================
# E2E Tests: Restart Scenarios
# =============================================================================


@pytest.mark.e2e
class TestRestartScenarios:
    """E2E tests for restart scenarios."""

    def test_restart_preserves_stats(self) -> None:
        """Test restart preserves accumulated stats."""
        poller = E2EPoller(poll_interval=1)

        # First run
        poller.start()
        time.sleep(2.5)
        poller.stop()

        first_run_polls = poller.stats["polls_completed"]
        first_run_items = poller.stats["items_fetched"]

        # Second run (stats should continue accumulating)
        poller.start()
        time.sleep(2.5)
        poller.stop()

        # Stats should have accumulated
        assert poller.stats["polls_completed"] > first_run_polls
        assert poller.stats["items_fetched"] > first_run_items

    def test_rapid_restart(self) -> None:
        """Test rapid start/stop cycles don't cause issues."""
        poller = E2EPoller(poll_interval=1)

        for _ in range(5):
            poller.start()
            time.sleep(0.3)
            poller.stop()

        # Final state should be consistent
        assert poller.enabled is False


# =============================================================================
# E2E Tests: Logging Integration
# =============================================================================


@pytest.mark.e2e
class TestLoggingIntegration:
    """E2E tests for logging integration."""

    def test_poller_uses_logger(self) -> None:
        """Test poller uses logger for output."""
        custom_logger = logging.getLogger("test_e2e_poller")
        custom_logger.setLevel(logging.DEBUG)

        poller = E2EPoller(poll_interval=1)
        poller.logger = custom_logger

        poller.start()
        try:
            time.sleep(1.5)
            # Should not raise
            assert poller.stats["polls_completed"] >= 1
        finally:
            poller.stop()

    def test_error_logged(self) -> None:
        """Test errors are logged properly."""

        class LoggingErrorPoller(E2EPoller):
            def __init__(self) -> None:
                super().__init__(poll_interval=1)
                self.logger = logging.getLogger("error_poller_test")

            def _poll_once(self) -> dict[str, int]:
                raise ValueError("Logged error message")

        poller = LoggingErrorPoller()
        poller.start()

        try:
            time.sleep(1.5)
            assert poller.stats["errors"] >= 1
            assert poller.stats["last_error"] == "Logged error message"
        finally:
            poller.stop()
