"""
Integration Tests for Base Poller.

Tests BasePoller integration with APScheduler and lifecycle management.

Reference: TESTING_STRATEGY V3.2 - Integration tests for component interactions
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/integration/schedulers/test_base_poller_integration.py -v -m integration
"""

import threading
import time

import pytest

from precog.schedulers.base_poller import BasePoller, PollerStats

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class IntegrationPoller(BasePoller):
    """Concrete implementation for integration testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 2

    def __init__(
        self,
        poll_interval: int | None = None,
        poll_result: dict[str, int] | None = None,
    ) -> None:
        super().__init__(poll_interval=poll_interval)
        self.poll_result = poll_result or {
            "items_fetched": 0,
            "items_updated": 0,
            "items_created": 0,
        }
        self.poll_calls: list[float] = []

    def _poll_once(self) -> dict[str, int]:
        self.poll_calls.append(time.time())
        return self.poll_result

    def _get_job_name(self) -> str:
        return "Integration Test Poller"


# =============================================================================
# Integration Tests: Scheduler Lifecycle
# =============================================================================


@pytest.mark.integration
class TestSchedulerLifecycle:
    """Integration tests for scheduler lifecycle management."""

    def test_start_initializes_scheduler(self) -> None:
        """Test start() creates and starts the scheduler."""
        poller = IntegrationPoller(poll_interval=1)

        assert poller._scheduler is None
        assert poller.enabled is False

        poller.start()

        try:
            assert poller._scheduler is not None
            assert poller.enabled is True
            assert poller.is_running() is True
        finally:
            poller.stop()

    def test_stop_shuts_down_scheduler(self) -> None:
        """Test stop() properly shuts down scheduler."""
        poller = IntegrationPoller(poll_interval=1)
        poller.start()

        assert poller.enabled is True

        poller.stop()

        assert poller.enabled is False
        assert poller.is_running() is False

    def test_multiple_start_stop_cycles(self) -> None:
        """Test poller handles multiple start/stop cycles."""
        poller = IntegrationPoller(poll_interval=1)

        for _ in range(3):
            poller.start()
            assert poller.enabled is True
            poller.stop()
            assert poller.enabled is False

    def test_stop_on_unstarted_poller(self) -> None:
        """Test stop() on never-started poller is safe."""
        poller = IntegrationPoller(poll_interval=1)

        # Should not raise
        poller.stop()
        assert poller.enabled is False

    def test_double_start_raises_error(self) -> None:
        """Test calling start() twice raises RuntimeError.

        The implementation explicitly prevents double-start to avoid
        scheduler conflicts.
        """
        poller = IntegrationPoller(poll_interval=1)

        poller.start()
        try:
            # Second start should raise RuntimeError
            with pytest.raises(RuntimeError, match="already running"):
                poller.start()
            # Should still be enabled
            assert poller.enabled is True
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Poll Execution
# =============================================================================


@pytest.mark.integration
class TestPollExecution:
    """Integration tests for poll execution."""

    def test_poll_executes_on_schedule(self) -> None:
        """Test polls execute according to interval."""
        poller = IntegrationPoller(poll_interval=1)
        poller.start()

        try:
            # Wait for at least 2 poll cycles
            time.sleep(2.5)

            # Should have at least 2 polls (initial + interval)
            assert len(poller.poll_calls) >= 2
        finally:
            poller.stop()

    def test_poll_results_accumulated(self) -> None:
        """Test poll results are accumulated in stats."""
        poller = IntegrationPoller(
            poll_interval=1,
            poll_result={"items_fetched": 5, "items_updated": 3, "items_created": 1},
        )
        poller.start()

        try:
            time.sleep(2.5)

            stats = poller.stats
            assert stats["polls_completed"] >= 2
            assert stats["items_fetched"] >= 10  # At least 2 polls * 5
        finally:
            poller.stop()

    def test_poll_wrapper_updates_last_poll(self) -> None:
        """Test poll wrapper updates last_poll timestamp."""
        poller = IntegrationPoller(poll_interval=1)
        poller.start()

        try:
            time.sleep(1.5)

            stats = poller.stats
            assert stats["last_poll"] is not None
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling in scheduler context."""

    def test_poll_error_doesnt_stop_scheduler(self) -> None:
        """Test poll errors don't crash the scheduler."""

        class ErrorPoller(IntegrationPoller):
            def __init__(self) -> None:
                super().__init__(poll_interval=1)
                self.error_count = 0

            def _poll_once(self) -> dict[str, int]:
                self.error_count += 1
                if self.error_count <= 2:
                    raise RuntimeError("Test error")
                return {"items_fetched": 1, "items_updated": 0, "items_created": 0}

        poller = ErrorPoller()
        poller.start()

        try:
            time.sleep(3.5)

            # Scheduler should still be running
            assert poller.enabled is True
            # Errors should be tracked
            assert poller.stats["errors"] >= 2
            # Should have recovered and done successful polls
            assert poller.stats["polls_completed"] >= 1
        finally:
            poller.stop()

    def test_error_message_captured(self) -> None:
        """Test error message is captured in stats."""

        class ErrorPoller(IntegrationPoller):
            def _poll_once(self) -> dict[str, int]:
                raise ValueError("Integration test error message")

        poller = ErrorPoller()
        poller.start()

        try:
            time.sleep(1.5)

            stats = poller.stats
            assert stats["errors"] >= 1
            assert stats["last_error"] == "Integration test error message"
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Stats Thread Safety
# =============================================================================


@pytest.mark.integration
class TestStatsThreadSafety:
    """Integration tests for stats access thread safety."""

    def test_concurrent_stats_access(self) -> None:
        """Test stats can be accessed safely while polling."""
        poller = IntegrationPoller(poll_interval=1)
        poller.start()

        try:
            stats_snapshots: list[PollerStats] = []
            errors: list[Exception] = []

            def read_stats() -> None:
                for _ in range(50):
                    try:
                        stats_snapshots.append(poller.stats)
                        time.sleep(0.02)
                    except Exception as e:
                        errors.append(e)

            threads = [threading.Thread(target=read_stats) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # No errors during concurrent access
            assert len(errors) == 0
            # Should have captured stats
            assert len(stats_snapshots) > 0
        finally:
            poller.stop()

    def test_stats_consistent_during_poll(self) -> None:
        """Test stats remain consistent during active polling."""
        poller = IntegrationPoller(
            poll_interval=1,
            poll_result={"items_fetched": 10, "items_updated": 5, "items_created": 2},
        )
        poller.start()

        try:
            time.sleep(2.5)

            stats = poller.stats
            polls = stats["polls_completed"]

            # Verify accumulated values are consistent
            if polls > 0:
                assert stats["items_fetched"] == polls * 10
                assert stats["items_updated"] == polls * 5
                assert stats["items_created"] == polls * 2
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Service Protocol
# =============================================================================


@pytest.mark.integration
class TestServiceProtocol:
    """Integration tests for EventLoopService protocol compliance."""

    def test_implements_service_protocol(self) -> None:
        """Test poller implements EventLoopService protocol methods."""
        poller = IntegrationPoller()

        # Protocol requires these
        assert hasattr(poller, "enabled")
        assert hasattr(poller, "is_running")
        assert hasattr(poller, "get_stats")

    def test_service_stats_available(self) -> None:
        """Test get_stats returns valid PollerStats."""
        poller = IntegrationPoller()
        poller._poll_wrapper()

        stats = poller.get_stats()

        assert isinstance(stats, dict)
        assert "polls_completed" in stats
        assert "items_fetched" in stats
        assert "errors" in stats


# =============================================================================
# Integration Tests: Callback Hooks
# =============================================================================


@pytest.mark.integration
class TestCallbackHooks:
    """Integration tests for lifecycle callback hooks."""

    def test_on_start_called(self) -> None:
        """Test _on_start is called when scheduler starts."""

        class HookPoller(IntegrationPoller):
            def __init__(self) -> None:
                super().__init__()
                self.on_start_called = False

            def _on_start(self) -> None:
                self.on_start_called = True

        poller = HookPoller()
        poller.start()

        try:
            assert poller.on_start_called is True
        finally:
            poller.stop()

    def test_on_stop_called(self) -> None:
        """Test _on_stop is called when scheduler stops."""

        class HookPoller(IntegrationPoller):
            def __init__(self) -> None:
                super().__init__()
                self.on_stop_called = False

            def _on_stop(self) -> None:
                self.on_stop_called = True

        poller = HookPoller()
        poller.start()
        poller.stop()

        assert poller.on_stop_called is True
