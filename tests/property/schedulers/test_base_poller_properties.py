"""
Property-Based Tests for Base Poller.

Uses Hypothesis to test BasePoller invariants and behaviors.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-DATA-001, REQ-OBSERV-001

Usage:
    pytest tests/property/schedulers/test_base_poller_properties.py -v -m property
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.schedulers.base_poller import BasePoller, PollerStats

# =============================================================================
# Concrete Test Implementation
# =============================================================================


class PropertyPoller(BasePoller):
    """Concrete implementation for property testing."""

    MIN_POLL_INTERVAL = 1
    DEFAULT_POLL_INTERVAL = 5

    def __init__(self, poll_interval: int | None = None) -> None:
        super().__init__(poll_interval=poll_interval)
        self._poll_result: dict[str, int] = {
            "items_fetched": 0,
            "items_updated": 0,
            "items_created": 0,
        }

    def _poll_once(self) -> dict[str, int]:
        return self._poll_result

    def _get_job_name(self) -> str:
        return "Property Poller"

    def set_poll_result(self, fetched: int = 0, updated: int = 0, created: int = 0) -> None:
        self._poll_result = {
            "items_fetched": fetched,
            "items_updated": updated,
            "items_created": created,
        }


# =============================================================================
# Custom Strategies
# =============================================================================

# Valid poll intervals (>= MIN_POLL_INTERVAL)
valid_interval_strategy = st.integers(min_value=1, max_value=3600)

# Item counts from polling
item_count_strategy = st.integers(min_value=0, max_value=10000)

# Error messages
error_message_strategy = st.text(min_size=0, max_size=200).filter(lambda s: "\x00" not in s)


# =============================================================================
# Property Tests: Initialization Invariants
# =============================================================================


@pytest.mark.property
class TestInitializationInvariants:
    """Property tests for initialization invariants."""

    @given(interval=valid_interval_strategy)
    @settings(max_examples=50)
    def test_poll_interval_preserved(self, interval: int) -> None:
        """Poll interval should be preserved after initialization."""
        poller = PropertyPoller(poll_interval=interval)
        assert poller.poll_interval == interval

    @given(interval=st.integers(min_value=1, max_value=100))
    @settings(max_examples=30)
    def test_poller_starts_disabled(self, interval: int) -> None:
        """Poller should start in disabled state for any valid interval."""
        poller = PropertyPoller(poll_interval=interval)
        assert poller.enabled is False
        assert poller.is_running() is False

    @given(interval=st.integers(min_value=1, max_value=100))
    @settings(max_examples=30)
    def test_initial_stats_zeroed(self, interval: int) -> None:
        """Initial stats should have all counters at zero."""
        poller = PropertyPoller(poll_interval=interval)
        stats = poller.stats

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0


# =============================================================================
# Property Tests: Stats Accumulation Invariants
# =============================================================================


@pytest.mark.property
class TestStatsAccumulationInvariants:
    """Property tests for stats accumulation behavior."""

    @given(
        fetched=item_count_strategy,
        updated=item_count_strategy,
        created=item_count_strategy,
    )
    @settings(max_examples=50)
    def test_stats_accumulate_correctly(self, fetched: int, updated: int, created: int) -> None:
        """Stats should accumulate item counts correctly."""
        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched, updated=updated, created=created)

        poller._poll_wrapper()

        stats = poller.stats
        assert stats["items_fetched"] == fetched
        assert stats["items_updated"] == updated
        assert stats["items_created"] == created

    @given(poll_count=st.integers(min_value=1, max_value=20))
    @settings(max_examples=30)
    def test_polls_completed_increments(self, poll_count: int) -> None:
        """polls_completed should increment with each poll."""
        poller = PropertyPoller()

        for _ in range(poll_count):
            poller._poll_wrapper()

        assert poller.stats["polls_completed"] == poll_count

    @given(
        fetched=item_count_strategy,
        poll_count=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=30)
    def test_items_accumulate_over_polls(self, fetched: int, poll_count: int) -> None:
        """Items should accumulate correctly over multiple polls."""
        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched)

        for _ in range(poll_count):
            poller._poll_wrapper()

        expected_total = fetched * poll_count
        assert poller.stats["items_fetched"] == expected_total


# =============================================================================
# Property Tests: Stats Copy Invariants
# =============================================================================


@pytest.mark.property
class TestStatsCopyInvariants:
    """Property tests for stats copy behavior."""

    @given(
        fetched=item_count_strategy,
        updated=item_count_strategy,
    )
    @settings(max_examples=30)
    def test_stats_returns_independent_copy(self, fetched: int, updated: int) -> None:
        """Stats property should return an independent copy."""
        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched, updated=updated)
        poller._poll_wrapper()

        stats1 = poller.stats
        stats2 = poller.stats

        # Modify stats1
        stats1["polls_completed"] = 9999

        # stats2 should be unaffected
        assert stats2["polls_completed"] == 1

    @given(st.data())
    @settings(max_examples=20)
    def test_get_stats_matches_stats_property(self, data: st.DataObject) -> None:
        """get_stats() should return same values as stats property."""
        fetched = data.draw(item_count_strategy)
        updated = data.draw(item_count_strategy)

        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched, updated=updated)
        poller._poll_wrapper()

        stats_prop = poller.stats
        stats_method = poller.get_stats()

        assert stats_prop["polls_completed"] == stats_method["polls_completed"]
        assert stats_prop["items_fetched"] == stats_method["items_fetched"]
        assert stats_prop["items_updated"] == stats_method["items_updated"]


# =============================================================================
# Property Tests: Error Handling Invariants
# =============================================================================


@pytest.mark.property
class TestErrorHandlingInvariants:
    """Property tests for error handling behavior."""

    @given(error_count=st.integers(min_value=1, max_value=50))
    @settings(max_examples=30)
    def test_error_count_accumulates(self, error_count: int) -> None:
        """Error count should accumulate correctly."""

        class ErrorPoller(PropertyPoller):
            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError("Test error")

        poller = ErrorPoller()

        for _ in range(error_count):
            poller._poll_wrapper()

        assert poller.stats["errors"] == error_count

    @given(error_msg=error_message_strategy)
    @settings(max_examples=30)
    def test_last_error_captured(self, error_msg: str) -> None:
        """Last error message should be captured."""
        if not error_msg:
            return  # Skip empty messages

        class ErrorPoller(PropertyPoller):
            def __init__(self, msg: str) -> None:
                super().__init__()
                self.msg = msg

            def _poll_once(self) -> dict[str, int]:
                raise RuntimeError(self.msg)

        poller = ErrorPoller(error_msg)
        poller._poll_wrapper()

        assert poller.stats["last_error"] == error_msg


# =============================================================================
# Property Tests: PollerStats TypedDict Invariants
# =============================================================================


@pytest.mark.property
class TestPollerStatsInvariants:
    """Property tests for PollerStats TypedDict."""

    @given(
        polls=item_count_strategy,
        fetched=item_count_strategy,
        updated=item_count_strategy,
        created=item_count_strategy,
        errors=item_count_strategy,
    )
    @settings(max_examples=50)
    def test_poller_stats_round_trip(
        self, polls: int, fetched: int, updated: int, created: int, errors: int
    ) -> None:
        """PollerStats should preserve values through round-trip."""
        stats = PollerStats(
            polls_completed=polls,
            items_fetched=fetched,
            items_updated=updated,
            items_created=created,
            errors=errors,
            last_poll=None,
            last_error=None,
        )

        # Create copy
        copy = PollerStats(**stats)

        assert copy["polls_completed"] == polls
        assert copy["items_fetched"] == fetched
        assert copy["items_updated"] == updated
        assert copy["items_created"] == created
        assert copy["errors"] == errors


# =============================================================================
# Property Tests: Interval Validation Invariants
# =============================================================================


@pytest.mark.property
class TestIntervalValidationInvariants:
    """Property tests for interval validation."""

    def test_zero_interval_uses_default(self) -> None:
        """Zero interval is treated as None and uses default.

        Note: poll_interval=0 is falsy and treated like None.
        This tests that 0 results in the default interval being used,
        not an error being raised.
        """
        poller = PropertyPoller(poll_interval=0)
        assert poller.poll_interval == PropertyPoller.DEFAULT_POLL_INTERVAL

    @given(interval=st.integers(min_value=-100, max_value=-1))
    @settings(max_examples=20)
    def test_negative_interval_rejected(self, interval: int) -> None:
        """Negative interval should be rejected."""
        with pytest.raises(ValueError):
            PropertyPoller(poll_interval=interval)

    @given(interval=st.integers(min_value=1, max_value=10000))
    @settings(max_examples=30)
    def test_valid_interval_accepted(self, interval: int) -> None:
        """Valid interval should be accepted."""
        poller = PropertyPoller(poll_interval=interval)
        assert poller.poll_interval == interval


# =============================================================================
# Property Tests: Poll Result Invariants
# =============================================================================


@pytest.mark.property
class TestPollResultInvariants:
    """Property tests for poll result handling."""

    @given(
        fetched=item_count_strategy,
        updated=item_count_strategy,
        created=item_count_strategy,
    )
    @settings(max_examples=50)
    def test_poll_result_preserved(self, fetched: int, updated: int, created: int) -> None:
        """Poll result should be reflected in stats."""
        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched, updated=updated, created=created)

        result = poller.poll_once()

        assert result["items_fetched"] == fetched
        assert result["items_updated"] == updated
        assert result["items_created"] == created

    @given(st.data())
    @settings(max_examples=30)
    def test_poll_once_equals_internal_poll(self, data: st.DataObject) -> None:
        """poll_once() should return same as _poll_once()."""
        fetched = data.draw(item_count_strategy)

        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched)

        external = poller.poll_once()
        internal = poller._poll_once()

        assert external == internal


# =============================================================================
# Property Tests: State Consistency
# =============================================================================


@pytest.mark.property
class TestStateConsistency:
    """Property tests for state consistency."""

    @given(poll_count=st.integers(min_value=0, max_value=20))
    @settings(max_examples=30)
    def test_enabled_state_consistent(self, poll_count: int) -> None:
        """enabled and is_running() should always match."""
        poller = PropertyPoller()

        # Before any polls
        assert poller.enabled == poller.is_running()

        # After polls (without starting scheduler)
        for _ in range(poll_count):
            poller._poll_wrapper()

        assert poller.enabled == poller.is_running()

    @given(
        fetched=item_count_strategy,
        errors=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=30)
    def test_stats_internally_consistent(self, fetched: int, errors: int) -> None:
        """Stats should be internally consistent."""
        poller = PropertyPoller()
        poller.set_poll_result(fetched=fetched)

        # Run successful polls
        for _ in range(5):
            poller._poll_wrapper()

        stats = poller.stats

        # polls_completed should match number of wrapper calls
        assert stats["polls_completed"] == 5
        # items should be accumulated correctly
        assert stats["items_fetched"] == fetched * 5
