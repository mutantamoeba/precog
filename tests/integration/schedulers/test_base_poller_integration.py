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
from collections.abc import Callable
from typing import Any

import pytest

from precog.schedulers.base_poller import BasePoller, PollerStats

# =============================================================================
# Test Helpers - Robust Polling-Based Waiting
# =============================================================================


def wait_for_condition(
    condition_fn: Callable[[], bool],
    timeout: float = 10.0,
    poll_interval: float = 0.1,
    description: str = "condition",
) -> bool:
    """Wait for a condition to become true, with timeout.

    This is a robust alternative to time.sleep() for timing-sensitive tests.
    Instead of sleeping for a fixed duration and hoping the condition is met,
    this actively polls until the condition is true or timeout is reached.

    Args:
        condition_fn: Zero-argument callable that returns True when condition is met.
        timeout: Maximum time to wait in seconds (default: 10s).
        poll_interval: How often to check the condition (default: 0.1s).
        description: Description for error messages.

    Returns:
        True if condition was met within timeout, False otherwise.

    Example:
        # Instead of: time.sleep(3.5); assert len(poller.poll_calls) >= 2
        # Use:
        success = wait_for_condition(
            lambda: len(poller.poll_calls) >= 2,
            timeout=10.0,
            description="at least 2 polls"
        )
        assert success, "Expected at least 2 polls within timeout"
    """
    start = time.time()
    while time.time() - start < timeout:
        if condition_fn():
            return True
        time.sleep(poll_interval)
    return False


def wait_for_polls(poller: Any, min_polls: int, timeout: float = 10.0) -> bool:
    """Wait for poller to complete at least min_polls poll cycles.

    Args:
        poller: Poller instance with poll_calls list or stats dict.
        min_polls: Minimum number of polls required.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if enough polls completed within timeout, False otherwise.
    """
    return wait_for_condition(
        lambda: len(poller.poll_calls) >= min_polls,
        timeout=timeout,
        description=f"at least {min_polls} polls",
    )


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
            # Use robust polling-based wait instead of fixed sleep
            # This adapts to actual scheduler behavior rather than assuming timing
            success = wait_for_polls(poller, min_polls=2, timeout=10.0)

            # Should have at least 2 polls (initial + interval)
            assert success, (
                f"Expected at least 2 polls within 10s timeout, got {len(poller.poll_calls)}"
            )
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
            # Use robust polling-based wait instead of fixed sleep
            success = wait_for_polls(poller, min_polls=2, timeout=10.0)

            assert success, (
                f"Expected at least 2 polls within 10s timeout, got {len(poller.poll_calls)}"
            )

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
            # Use robust polling-based wait for error recovery
            # Wait until we have 2 errors AND 1 successful poll
            def error_recovery_complete() -> bool:
                stats = poller.stats
                return stats["errors"] >= 2 and stats["polls_completed"] >= 1

            success = wait_for_condition(
                error_recovery_complete,
                timeout=15.0,  # Extra time for error recovery
                description="2 errors and 1 successful poll",
            )

            # Scheduler should still be running
            assert poller.enabled is True

            assert success, (
                f"Expected error recovery within 15s timeout. "
                f"Got errors={poller.stats['errors']}, "
                f"polls_completed={poller.stats['polls_completed']}"
            )

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
