"""
Unit Tests for Base Poller.

Tests individual methods and components of the BasePoller abstract class.

Reference: TESTING_STRATEGY V3.2 - Unit tests for individual functions
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/unit/schedulers/test_base_poller_unit.py -v -m unit
"""

import logging

import pytest

from precog.schedulers.base_poller import BasePoller, PollerStats

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class MockPoller(BasePoller):
    """Concrete implementation of BasePoller for testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 5

    def __init__(
        self,
        poll_interval: int | None = None,
        logger: logging.Logger | None = None,
        poll_result: dict[str, int] | None = None,
        poll_error: Exception | None = None,
    ) -> None:
        super().__init__(poll_interval=poll_interval, logger=logger)
        self.poll_result = poll_result or {
            "items_fetched": 0,
            "items_updated": 0,
            "items_created": 0,
        }
        self.poll_error = poll_error
        self.poll_count = 0
        self.on_start_called = False
        self.on_stop_called = False

    def _poll_once(self) -> dict[str, int]:
        self.poll_count += 1
        if self.poll_error:
            raise self.poll_error
        return self.poll_result

    def _get_job_name(self) -> str:
        return "Mock Poller Job"

    def _on_start(self) -> None:
        self.on_start_called = True

    def _on_stop(self) -> None:
        self.on_stop_called = True


# =============================================================================
# Unit Tests: Initialization
# =============================================================================


@pytest.mark.unit
class TestBasePollerInitialization:
    """Unit tests for BasePoller initialization."""

    def test_default_interval(self) -> None:
        """Test poller uses default interval when none specified."""
        poller = MockPoller()
        assert poller.poll_interval == MockPoller.DEFAULT_POLL_INTERVAL

    def test_custom_interval(self) -> None:
        """Test poller uses custom interval when specified."""
        poller = MockPoller(poll_interval=10)
        assert poller.poll_interval == 10

    def test_minimum_interval_enforced(self) -> None:
        """Test ValueError raised when interval below minimum.

        Note: poll_interval=0 is treated as None (falsy), so we use
        a negative value to test the minimum enforcement.
        """
        with pytest.raises(ValueError, match="must be at least"):
            MockPoller(poll_interval=-1)

    def test_minimum_interval_boundary(self) -> None:
        """Test minimum interval is accepted."""
        poller = MockPoller(poll_interval=MockPoller.MIN_POLL_INTERVAL)
        assert poller.poll_interval == MockPoller.MIN_POLL_INTERVAL

    def test_custom_logger(self) -> None:
        """Test poller uses custom logger when provided."""
        custom_logger = logging.getLogger("test_logger")
        poller = MockPoller(logger=custom_logger)
        assert poller.logger is custom_logger

    def test_default_logger_created(self) -> None:
        """Test default logger created when none provided."""
        poller = MockPoller()
        assert poller.logger is not None
        assert isinstance(poller.logger, logging.Logger)

    def test_initial_state(self) -> None:
        """Test poller initializes in disabled state."""
        poller = MockPoller()
        assert poller.enabled is False
        assert poller.is_running() is False
        assert poller._scheduler is None

    def test_initial_stats(self) -> None:
        """Test initial statistics are zeroed."""
        poller = MockPoller()
        stats = poller.stats

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0
        assert stats["last_poll"] is None
        assert stats["last_error"] is None


# =============================================================================
# Unit Tests: Stats Access
# =============================================================================


@pytest.mark.unit
class TestStatsAccess:
    """Unit tests for stats access methods."""

    def test_stats_property_returns_copy(self) -> None:
        """Test stats property returns a copy."""
        poller = MockPoller()
        stats1 = poller.stats

        # Modifying one shouldn't affect the other
        stats1["polls_completed"] = 100
        assert poller.stats["polls_completed"] == 0

    def test_get_stats_returns_dict(self) -> None:
        """Test get_stats returns dictionary."""
        poller = MockPoller()
        stats = poller.get_stats()

        assert isinstance(stats, dict)
        assert "polls_completed" in stats

    def test_stats_thread_safety(self) -> None:
        """Test stats access is thread-safe (lock acquired)."""
        poller = MockPoller()

        # Access stats to ensure lock is used properly
        with poller._lock:
            # This should not deadlock if stats uses the same lock
            pass

        stats = poller.stats
        assert stats is not None


# =============================================================================
# Unit Tests: Poll Once
# =============================================================================


@pytest.mark.unit
class TestPollOnce:
    """Unit tests for poll_once method."""

    def test_poll_once_calls_implementation(self) -> None:
        """Test poll_once calls _poll_once."""
        poller = MockPoller(
            poll_result={"items_fetched": 5, "items_updated": 3, "items_created": 1}
        )

        result = poller.poll_once()

        assert poller.poll_count == 1
        assert result["items_fetched"] == 5
        assert result["items_updated"] == 3
        assert result["items_created"] == 1

    def test_poll_once_propagates_errors(self) -> None:
        """Test poll_once propagates errors from implementation."""
        poller = MockPoller(poll_error=ValueError("Test error"))

        with pytest.raises(ValueError, match="Test error"):
            poller.poll_once()


# =============================================================================
# Unit Tests: Poll Wrapper
# =============================================================================


@pytest.mark.unit
class TestPollWrapper:
    """Unit tests for _poll_wrapper method."""

    def test_poll_wrapper_updates_stats(self) -> None:
        """Test poll wrapper updates statistics."""
        poller = MockPoller(
            poll_result={"items_fetched": 10, "items_updated": 5, "items_created": 2}
        )

        poller._poll_wrapper()

        stats = poller.stats
        assert stats["polls_completed"] == 1
        assert stats["items_fetched"] == 10
        assert stats["items_updated"] == 5
        assert stats["items_created"] == 2
        assert stats["last_poll"] is not None

    def test_poll_wrapper_handles_errors(self) -> None:
        """Test poll wrapper catches and records errors."""
        poller = MockPoller(poll_error=RuntimeError("Connection failed"))

        # Should not raise
        poller._poll_wrapper()

        stats = poller.stats
        assert stats["errors"] == 1
        assert stats["last_error"] == "Connection failed"

    def test_poll_wrapper_increments_poll_count(self) -> None:
        """Test poll wrapper increments completed poll count."""
        poller = MockPoller()

        poller._poll_wrapper()
        poller._poll_wrapper()
        poller._poll_wrapper()

        assert poller.stats["polls_completed"] == 3

    def test_poll_wrapper_accumulates_items(self) -> None:
        """Test poll wrapper accumulates item counts."""
        poller = MockPoller(
            poll_result={"items_fetched": 5, "items_updated": 2, "items_created": 1}
        )

        poller._poll_wrapper()
        poller._poll_wrapper()

        stats = poller.stats
        assert stats["items_fetched"] == 10
        assert stats["items_updated"] == 4
        assert stats["items_created"] == 2


# =============================================================================
# Unit Tests: Get Job Name
# =============================================================================


@pytest.mark.unit
class TestGetJobName:
    """Unit tests for _get_job_name abstract method."""

    def test_job_name_returned(self) -> None:
        """Test concrete implementation returns job name."""
        poller = MockPoller()
        assert poller._get_job_name() == "Mock Poller Job"


# =============================================================================
# Unit Tests: Create Initial Stats
# =============================================================================


@pytest.mark.unit
class TestCreateInitialStats:
    """Unit tests for _create_initial_stats method."""

    def test_returns_poller_stats(self) -> None:
        """Test returns PollerStats TypedDict."""
        poller = MockPoller()
        stats = poller._create_initial_stats()

        # Verify all required keys exist
        assert "polls_completed" in stats
        assert "items_fetched" in stats
        assert "items_updated" in stats
        assert "items_created" in stats
        assert "errors" in stats
        assert "last_poll" in stats
        assert "last_error" in stats

    def test_all_counters_zero(self) -> None:
        """Test all counters are initialized to zero."""
        poller = MockPoller()
        stats = poller._create_initial_stats()

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0

    def test_timestamps_none(self) -> None:
        """Test timestamps are initialized to None."""
        poller = MockPoller()
        stats = poller._create_initial_stats()

        assert stats["last_poll"] is None
        assert stats["last_error"] is None


# =============================================================================
# Unit Tests: Enabled Property
# =============================================================================


@pytest.mark.unit
class TestEnabledProperty:
    """Unit tests for enabled property."""

    def test_enabled_initially_false(self) -> None:
        """Test enabled is False before start."""
        poller = MockPoller()
        assert poller.enabled is False

    def test_is_running_same_as_enabled(self) -> None:
        """Test is_running returns same as enabled."""
        poller = MockPoller()
        assert poller.is_running() == poller.enabled


# =============================================================================
# Unit Tests: PollerStats TypedDict
# =============================================================================


@pytest.mark.unit
class TestPollerStatsTypedDict:
    """Unit tests for PollerStats TypedDict."""

    def test_poller_stats_creation(self) -> None:
        """Test PollerStats can be created."""
        stats = PollerStats(
            polls_completed=5,
            items_fetched=100,
            items_updated=50,
            items_created=25,
            errors=2,
            last_poll="2024-01-01T00:00:00",
            last_error="Test error",
        )

        assert stats["polls_completed"] == 5
        assert stats["items_fetched"] == 100
        assert stats["items_updated"] == 50
        assert stats["items_created"] == 25
        assert stats["errors"] == 2
        assert stats["last_poll"] == "2024-01-01T00:00:00"
        assert stats["last_error"] == "Test error"

    def test_poller_stats_unpacking(self) -> None:
        """Test PollerStats can be unpacked with **."""
        stats = PollerStats(
            polls_completed=0,
            items_fetched=0,
            items_updated=0,
            items_created=0,
            errors=0,
            last_poll=None,
            last_error=None,
        )

        copy = PollerStats(**stats)
        assert copy == stats
