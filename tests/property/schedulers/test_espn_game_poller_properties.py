"""
Property-Based Tests for ESPN Game Poller.

Uses Hypothesis to test ESPNGamePoller invariants and behaviors.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/property/schedulers/test_espn_game_poller_properties.py -v -m property
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.schedulers.espn_game_poller import ESPNGamePoller

# =============================================================================
# Custom Strategies
# =============================================================================

# Valid poll intervals
valid_poll_interval = st.integers(min_value=5, max_value=3600)

# Valid idle intervals
valid_idle_interval = st.integers(min_value=15, max_value=3600)

# Valid leagues
valid_leagues = st.lists(
    st.sampled_from(["nfl", "ncaaf", "nba", "ncaab", "nhl", "wnba"]),
    min_size=1,
    max_size=6,
    unique=True,
)

# Game status strings
game_status_strategy = st.sampled_from(
    [
        "pre",
        "scheduled",
        "in",
        "in_progress",
        "halftime",
        "post",
        "final",
        "final/ot",
        "final/2ot",
        "unknown",
        "",
    ]
)

# Score values
score_strategy = st.integers(min_value=0, max_value=200)

# Period values
period_strategy = st.integers(min_value=0, max_value=10)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_espn_client() -> MagicMock:
    """Create mock ESPN client."""
    client = MagicMock()
    client.get_scoreboard.return_value = []
    return client


# =============================================================================
# Property Tests: Initialization Invariants
# =============================================================================


@pytest.mark.property
class TestInitializationInvariants:
    """Property tests for initialization invariants."""

    @given(interval=valid_poll_interval)
    @settings(max_examples=50)
    def test_poll_interval_preserved(self, interval: int) -> None:
        """Poll interval should be preserved after initialization."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=interval)
            assert poller.poll_interval == interval

    @given(interval=valid_idle_interval)
    @settings(max_examples=50)
    def test_idle_interval_preserved(self, interval: int) -> None:
        """Idle interval should be preserved after initialization."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(idle_interval=interval)
            assert poller.idle_interval == interval

    @given(leagues=valid_leagues)
    @settings(max_examples=30)
    def test_leagues_preserved(self, leagues: list[str]) -> None:
        """Leagues should be preserved after initialization."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(leagues=leagues)
            assert poller.leagues == leagues

    @given(interval=st.integers(min_value=1, max_value=4))
    @settings(max_examples=10)
    def test_poll_interval_below_minimum_rejected(self, interval: int) -> None:
        """Poll intervals below MIN_POLL_INTERVAL should be rejected."""
        with pytest.raises(ValueError):
            with patch("precog.schedulers.espn_game_poller.ESPNClient"):
                ESPNGamePoller(poll_interval=interval)

    @given(interval=st.integers(min_value=1, max_value=14))
    @settings(max_examples=10)
    def test_idle_interval_below_minimum_rejected(self, interval: int) -> None:
        """Idle intervals below 15 should be rejected."""
        with pytest.raises(ValueError):
            with patch("precog.schedulers.espn_game_poller.ESPNClient"):
                ESPNGamePoller(idle_interval=interval)


# =============================================================================
# Property Tests: Status Normalization Invariants
# =============================================================================


@pytest.mark.property
class TestStatusNormalizationInvariants:
    """Property tests for status normalization."""

    @given(status=game_status_strategy)
    @settings(max_examples=50)
    def test_normalized_status_is_valid(self, status: str) -> None:
        """Normalized status should always be one of valid values."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller()
            normalized = poller._normalize_game_status(status)
            assert normalized in {"pre", "in_progress", "halftime", "final"}

    @given(status=game_status_strategy)
    @settings(max_examples=50)
    def test_normalization_is_idempotent(self, status: str) -> None:
        """Normalizing twice should give same result."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller()
            first = poller._normalize_game_status(status)
            second = poller._normalize_game_status(first)
            assert first == second

    @given(status=st.text(min_size=0, max_size=20))
    @settings(max_examples=50)
    def test_normalization_never_raises(self, status: str) -> None:
        """Status normalization should never raise exceptions."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller()
            # Should not raise
            result = poller._normalize_game_status(status)
            assert isinstance(result, str)


# =============================================================================
# Property Tests: Stats Invariants
# =============================================================================


@pytest.mark.property
class TestStatsInvariants:
    """Property tests for stats behavior."""

    @given(poll_interval=valid_poll_interval)
    @settings(max_examples=20)
    def test_initial_stats_zero(self, poll_interval: int) -> None:
        """Initial stats should all be zero."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=poll_interval)
            stats = poller.stats

            assert stats["polls_completed"] == 0
            assert stats["items_fetched"] == 0
            assert stats["items_updated"] == 0
            assert stats["items_created"] == 0
            assert stats["errors"] == 0

    @given(st.data())
    @settings(max_examples=20)
    def test_stats_copy_isolation(self, data: st.DataObject) -> None:
        """Stats copies should be independent."""
        poll_interval = data.draw(valid_poll_interval)

        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=poll_interval)

            stats1 = poller.stats
            stats1["polls_completed"] = 9999

            stats2 = poller.stats
            assert stats2["polls_completed"] == 0


# =============================================================================
# Property Tests: Poll Result Invariants
# =============================================================================


@pytest.mark.property
class TestPollResultInvariants:
    """Property tests for poll result invariants."""

    @given(leagues=valid_leagues)
    @settings(max_examples=30)
    def test_poll_once_returns_required_keys(self, leagues: list[str]) -> None:
        """poll_once should always return required keys."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient") as mock_client:
            mock_client.return_value.get_scoreboard.return_value = []
            poller = ESPNGamePoller(leagues=leagues)

            result = poller.poll_once()

            assert "items_fetched" in result
            assert "items_updated" in result
            assert "items_created" in result

    @given(leagues=valid_leagues)
    @settings(max_examples=30)
    def test_poll_once_values_non_negative(self, leagues: list[str]) -> None:
        """poll_once values should be non-negative."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient") as mock_client:
            mock_client.return_value.get_scoreboard.return_value = []
            poller = ESPNGamePoller(leagues=leagues)

            result = poller.poll_once()

            assert result["items_fetched"] >= 0
            assert result["items_updated"] >= 0
            assert result["items_created"] >= 0


# =============================================================================
# Property Tests: Configuration Invariants
# =============================================================================


@pytest.mark.property
class TestConfigurationInvariants:
    """Property tests for configuration invariants."""

    @given(
        poll=valid_poll_interval,
        idle=valid_idle_interval,
        leagues=valid_leagues,
    )
    @settings(max_examples=30)
    def test_configuration_independent(self, poll: int, idle: int, leagues: list[str]) -> None:
        """Configuration values should be independent of each other."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(
                poll_interval=poll,
                idle_interval=idle,
                leagues=leagues,
            )

            assert poller.poll_interval == poll
            assert poller.idle_interval == idle
            assert poller.leagues == leagues

    @given(leagues=valid_leagues)
    @settings(max_examples=30)
    def test_leagues_list_used_directly(self, leagues: list[str]) -> None:
        """Leagues list is used directly (not copied) for efficiency.

        Note: The implementation uses the provided list directly. If callers
        need isolation, they should pass a copy. This is intentional for
        performance - defensive copying is done at the caller's discretion.
        """
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            leagues_copy = leagues.copy()
            poller = ESPNGamePoller(leagues=leagues_copy)

            # Verify leagues are used (they should match exactly)
            assert poller.leagues == leagues_copy
            assert len(poller.leagues) == len(leagues)


# =============================================================================
# Property Tests: State Machine Invariants
# =============================================================================


@pytest.mark.property
class TestStateMachineInvariants:
    """Property tests for state machine behavior."""

    @given(poll_interval=valid_poll_interval)
    @settings(max_examples=20)
    def test_poller_starts_disabled(self, poll_interval: int) -> None:
        """Poller should start in disabled state."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=poll_interval)
            assert poller.enabled is False
            assert poller.is_running() is False

    @given(poll_interval=valid_poll_interval)
    @settings(max_examples=10)
    def test_enabled_matches_is_running(self, poll_interval: int) -> None:
        """enabled and is_running() should always match."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=poll_interval)
            assert poller.enabled == poller.is_running()


# =============================================================================
# Property Tests: ESPN Client Interaction Invariants
# =============================================================================


@pytest.mark.property
class TestClientInteractionInvariants:
    """Property tests for ESPN client interaction."""

    @given(leagues=valid_leagues)
    @settings(max_examples=20)
    def test_poll_once_calls_client_for_each_league(self, leagues: list[str]) -> None:
        """poll_once should call ESPN client for each league."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.get_scoreboard.return_value = []

            poller = ESPNGamePoller(leagues=leagues)
            poller.poll_once()

            # Should be called once per league
            assert mock_instance.get_scoreboard.call_count == len(leagues)


# =============================================================================
# Property Tests: Job Name Invariants
# =============================================================================


@pytest.mark.property
class TestJobNameInvariants:
    """Property tests for job name."""

    @given(
        poll_interval=valid_poll_interval,
        leagues=valid_leagues,
    )
    @settings(max_examples=20)
    def test_job_name_consistent(self, poll_interval: int, leagues: list[str]) -> None:
        """Job name should be consistent regardless of configuration."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(
                poll_interval=poll_interval,
                leagues=leagues,
            )

            # Job name should always be the same
            assert poller._get_job_name() == "ESPN Game State Poll"

    @given(st.data())
    @settings(max_examples=20)
    def test_job_name_is_string(self, data: st.DataObject) -> None:
        """Job name should always be a string."""
        poll_interval = data.draw(valid_poll_interval)

        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=poll_interval)
            assert isinstance(poller._get_job_name(), str)


# =============================================================================
# Property Tests: Error Handling Invariants
# =============================================================================


@pytest.mark.property
class TestErrorHandlingInvariants:
    """Property tests for error handling."""

    @given(leagues=valid_leagues)
    @settings(max_examples=20)
    def test_api_error_increments_error_count(self, leagues: list[str]) -> None:
        """API errors should increment error count in stats."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.get_scoreboard.side_effect = Exception("API Error")

            poller = ESPNGamePoller(leagues=leagues)

            # Errors are caught and logged, not raised
            poller._poll_wrapper()

            # Error count should be incremented
            assert poller.stats["errors"] >= 1
