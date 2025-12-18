"""
Chaos Tests for ESPN Game Poller.

Tests edge cases, unusual inputs, and unexpected scenarios for ESPNGamePoller.

Reference: TESTING_STRATEGY V3.2 - Chaos tests for edge cases
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/chaos/schedulers/test_espn_game_poller_chaos.py -v -m chaos
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.espn_game_poller import ESPNGamePoller

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
# Chaos Tests: Edge Case Intervals
# =============================================================================


@pytest.mark.chaos
class TestEdgeCaseIntervals:
    """Chaos tests for edge case poll intervals."""

    def test_minimum_poll_interval_boundary(self, mock_espn_client: MagicMock) -> None:
        """Test exactly at minimum poll interval boundary."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )
        assert poller.poll_interval == 5

    def test_minimum_idle_interval_boundary(self, mock_espn_client: MagicMock) -> None:
        """Test exactly at minimum idle interval boundary."""
        poller = ESPNGamePoller(
            idle_interval=15,
            espn_client=mock_espn_client,
        )
        assert poller.idle_interval == 15

    def test_maximum_reasonable_intervals(self, mock_espn_client: MagicMock) -> None:
        """Test very large intervals."""
        poller = ESPNGamePoller(
            poll_interval=86400,  # 24 hours
            idle_interval=86400,
            espn_client=mock_espn_client,
        )
        assert poller.poll_interval == 86400
        assert poller.idle_interval == 86400

    def test_zero_poll_interval_uses_default(self, mock_espn_client: MagicMock) -> None:
        """Test zero poll interval is treated as None and uses default."""
        poller = ESPNGamePoller(
            poll_interval=0,
            espn_client=mock_espn_client,
        )
        assert poller.poll_interval == ESPNGamePoller.DEFAULT_POLL_INTERVAL

    def test_negative_poll_interval_rejected(self, mock_espn_client: MagicMock) -> None:
        """Test negative poll interval is rejected."""
        with pytest.raises(ValueError):
            ESPNGamePoller(poll_interval=-1, espn_client=mock_espn_client)

    def test_negative_idle_interval_rejected(self, mock_espn_client: MagicMock) -> None:
        """Test negative idle interval is rejected."""
        with pytest.raises(ValueError):
            ESPNGamePoller(idle_interval=-1, espn_client=mock_espn_client)


# =============================================================================
# Chaos Tests: Unusual Game Data
# =============================================================================


@pytest.mark.chaos
class TestUnusualGameData:
    """Chaos tests for unusual game data."""

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_empty_metadata(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test game with empty metadata."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        game = {
            "metadata": {},
            "state": {"home_score": 0, "away_score": 0, "game_status": "pre"},
        }
        mock_espn_client.get_scoreboard.return_value = [game]

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Should not crash, but skip game with no event_id
        result = poller.poll_once()
        assert result["items_fetched"] == 1
        assert result["items_updated"] == 0  # Skipped due to no event_id

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_very_high_scores(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test game with unrealistically high scores."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        game = {
            "metadata": {
                "espn_event_id": "game_1",
                "home_team": {"espn_team_id": "1"},
                "away_team": {"espn_team_id": "2"},
                "venue": {"venue_name": "Stadium"},
            },
            "state": {
                "home_score": 999999,
                "away_score": 999999,
                "game_status": "final",
            },
        }
        mock_espn_client.get_scoreboard.return_value = [game]

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()
        assert result["items_updated"] == 1

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_negative_scores(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test game with negative scores (shouldn't happen)."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        game = {
            "metadata": {
                "espn_event_id": "game_1",
                "home_team": {"espn_team_id": "1"},
                "away_team": {"espn_team_id": "2"},
                "venue": {"venue_name": "Stadium"},
            },
            "state": {
                "home_score": -10,
                "away_score": -5,
                "game_status": "final",
            },
        }
        mock_espn_client.get_scoreboard.return_value = [game]

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Should not crash
        result = poller.poll_once()
        assert result["items_fetched"] == 1


# =============================================================================
# Chaos Tests: Error Conditions
# =============================================================================


@pytest.mark.chaos
class TestErrorConditions:
    """Chaos tests for error conditions."""

    def test_api_raises_base_exception(self, mock_espn_client: MagicMock) -> None:
        """Test handling of BaseException subclasses."""
        mock_espn_client.get_scoreboard.side_effect = KeyboardInterrupt()

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # KeyboardInterrupt should propagate through _poll_once
        with pytest.raises(KeyboardInterrupt):
            poller._poll_once()

    def test_empty_error_message(self, mock_espn_client: MagicMock) -> None:
        """Test error with empty message."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError("")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_wrapper()

        assert poller.stats["errors"] == 1
        assert poller.stats["last_error"] == ""

    def test_unicode_error_message(self, mock_espn_client: MagicMock) -> None:
        """Test error with unicode message."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError(
            "Error: \u2603 \u2764 \U0001f600"
        )

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_wrapper()

        assert poller.stats["errors"] == 1
        assert "\u2603" in poller.stats["last_error"]

    def test_very_long_error_message(self, mock_espn_client: MagicMock) -> None:
        """Test error with very long message."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError("A" * 10000)

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_wrapper()

        assert poller.stats["errors"] == 1
        assert len(poller.stats["last_error"]) > 0


# =============================================================================
# Chaos Tests: State Corruption Attempts
# =============================================================================


@pytest.mark.chaos
class TestStateCorruptionAttempts:
    """Chaos tests for state corruption attempts."""

    def test_stats_modification_doesnt_corrupt(self, mock_espn_client: MagicMock) -> None:
        """Test modifying returned stats doesn't corrupt internal state."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._poll_wrapper()

        stats = poller.stats
        stats["polls_completed"] = 999999
        stats["items_fetched"] = -1
        stats["errors"] = 1000

        internal_stats = poller.stats
        assert internal_stats["polls_completed"] == 1
        assert internal_stats["items_fetched"] == 0
        assert internal_stats["errors"] == 0

    def test_leagues_list_modification(self, mock_espn_client: MagicMock) -> None:
        """Test modifying leagues list after creation."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Get reference and modify
        poller.leagues.append("hacked")

        # Poller's leagues is the actual list (mutable)
        # This is a design choice - be aware
        assert "hacked" in poller.leagues


# =============================================================================
# Chaos Tests: Lifecycle Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestLifecycleEdgeCases:
    """Chaos tests for lifecycle edge cases."""

    def test_stop_without_start(self, mock_espn_client: MagicMock) -> None:
        """Test calling stop on never-started poller."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Should not raise
        poller.stop()
        assert poller.enabled is False

    def test_multiple_stops(self, mock_espn_client: MagicMock) -> None:
        """Test calling stop multiple times."""
        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        poller.stop()
        poller.stop()
        poller.stop()

        assert poller.enabled is False

    def test_start_after_manual_polls(self, mock_espn_client: MagicMock) -> None:
        """Test starting scheduler after manual polls."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Manual polls first
        for _ in range(5):
            poller._poll_wrapper()

        poller.start()
        try:
            time.sleep(1.5)

            # Stats should continue from manual polls
            assert poller.stats["polls_completed"] >= 6
        finally:
            poller.stop()

    def test_poll_wrapper_after_stop(self, mock_espn_client: MagicMock) -> None:
        """Test poll_wrapper can be called after scheduler stops."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller.start()
        time.sleep(0.5)
        poller.stop()

        initial_polls = poller.stats["polls_completed"]
        poller._poll_wrapper()

        assert poller.stats["polls_completed"] == initial_polls + 1


# =============================================================================
# Chaos Tests: Concurrent Chaos
# =============================================================================


@pytest.mark.chaos
class TestConcurrentChaos:
    """Chaos tests for concurrent chaotic operations."""

    def test_rapid_start_stop_with_polls(self, mock_espn_client: MagicMock) -> None:
        """Test rapid start/stop while polls are happening."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

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

        if poller.enabled:
            poller.stop()

        # Should handle chaotic usage without crashes

    def test_stats_access_during_error_storm(self, mock_espn_client: MagicMock) -> None:
        """Test stats access while errors are happening rapidly."""
        mock_espn_client.get_scoreboard.side_effect = RuntimeError("Storm")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

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

        assert len(read_errors) == 0
        assert poller.stats["errors"] > 0


# =============================================================================
# Chaos Tests: Unusual League Configurations
# =============================================================================


@pytest.mark.chaos
class TestUnusualLeagueConfigurations:
    """Chaos tests for unusual league configurations."""

    def test_empty_leagues_list_uses_defaults(self, mock_espn_client: MagicMock) -> None:
        """Test empty leagues list falls back to defaults.

        Note: Empty list [] is falsy in Python, so the implementation
        uses DEFAULT_LEAGUES. This is intentional - an empty list is
        treated as "no preference, use defaults" rather than "poll nothing".
        """
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=[],
            espn_client=mock_espn_client,
        )

        # Empty list is falsy, so defaults are used
        assert poller.leagues == ESPNGamePoller.DEFAULT_LEAGUES

        poller.poll_once()

        # Should poll default leagues
        assert mock_espn_client.get_scoreboard.call_count == len(ESPNGamePoller.DEFAULT_LEAGUES)

    def test_duplicate_leagues(self, mock_espn_client: MagicMock) -> None:
        """Test with duplicate leagues in list."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "nfl", "nfl"],
            espn_client=mock_espn_client,
        )

        poller.poll_once()

        # Should poll NFL 3 times
        assert mock_espn_client.get_scoreboard.call_count == 3

    def test_unknown_league(self, mock_espn_client: MagicMock) -> None:
        """Test with unknown league code."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["unknown_league"],
            espn_client=mock_espn_client,
        )

        poller.poll_once()

        # Should attempt to poll (ESPN client will handle)
        mock_espn_client.get_scoreboard.assert_called_once_with("unknown_league")


# =============================================================================
# Chaos Tests: Status Normalization Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestStatusNormalizationEdgeCases:
    """Chaos tests for status normalization edge cases."""

    def test_normalize_none_like_status(self, mock_espn_client: MagicMock) -> None:
        """Test normalizing None-like status values."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Empty string should normalize to "pre"
        assert poller._normalize_game_status("") == "pre"

    def test_normalize_whitespace_status(self, mock_espn_client: MagicMock) -> None:
        """Test normalizing whitespace status."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Whitespace should normalize to "pre" (unknown)
        assert poller._normalize_game_status("   ") == "pre"
        assert poller._normalize_game_status("\n\t") == "pre"

    def test_normalize_mixed_case_status(self, mock_espn_client: MagicMock) -> None:
        """Test normalizing mixed case status.

        Note: Normalization is case-insensitive via .lower(), so
        "In_Progress" matches "in_progress" and returns "in_progress".
        """
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        assert poller._normalize_game_status("FINAL") == "final"
        assert poller._normalize_game_status("In_Progress") == "in_progress"  # Case-insensitive
        assert poller._normalize_game_status("IN") == "in_progress"
        assert poller._normalize_game_status("PRE") == "pre"
        assert poller._normalize_game_status("HaLfTiMe") == "halftime"


# =============================================================================
# Chaos Tests: Persistence Configuration Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestPersistenceEdgeCases:
    """Chaos tests for persistence configuration edge cases."""

    def test_persist_without_url_fails(self, mock_espn_client: MagicMock) -> None:
        """Test persist_jobs=True without URL raises error."""
        with pytest.raises(ValueError, match="job_store_url required"):
            ESPNGamePoller(
                persist_jobs=True,
                espn_client=mock_espn_client,
            )

    def test_url_without_persist_ignored(self, mock_espn_client: MagicMock) -> None:
        """Test job_store_url without persist_jobs is ignored."""
        poller = ESPNGamePoller(
            persist_jobs=False,
            job_store_url="sqlite:///ignored.db",
            espn_client=mock_espn_client,
        )

        assert poller.persist_jobs is False
        assert poller.job_store_url == "sqlite:///ignored.db"


# =============================================================================
# Chaos Tests: Stats TypedDict Edge Cases
# =============================================================================


@pytest.mark.chaos
class TestStatsTypedDictEdgeCases:
    """Chaos tests for PollerStats edge cases."""

    def test_stats_all_zeros(self, mock_espn_client: MagicMock) -> None:
        """Test fresh poller has all zero stats."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        stats = poller.stats

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0
        assert stats["last_poll"] is None
        assert stats["last_error"] is None

    def test_stats_after_many_operations(self, mock_espn_client: MagicMock) -> None:
        """Test stats correctness after many operations."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        for _ in range(1000):
            poller._poll_wrapper()

        stats = poller.stats
        assert stats["polls_completed"] == 1000
        assert stats["errors"] == 0

    def test_stats_type_consistency(self, mock_espn_client: MagicMock) -> None:
        """Test stats values have correct types."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._poll_wrapper()

        stats = poller.stats

        assert isinstance(stats["polls_completed"], int)
        assert isinstance(stats["items_fetched"], int)
        assert isinstance(stats["items_updated"], int)
        assert isinstance(stats["items_created"], int)
        assert isinstance(stats["errors"], int)
        assert stats["last_poll"] is None or isinstance(stats["last_poll"], str)
        assert stats["last_error"] is None or isinstance(stats["last_error"], str)


# =============================================================================
# Chaos Tests: Adaptive Polling Edge Cases (Issue #234)
# =============================================================================


@pytest.mark.chaos
class TestAdaptivePollingChaos:
    """Chaos tests for adaptive polling edge cases.

    Related: Issue #234 (ESPNGamePoller adaptive polling)

    Educational Note:
        Adaptive polling adjusts poll_interval based on active games.
        These chaos tests verify edge cases in interval adjustment,
        state transitions, and has_active_games() detection.
    """

    def test_adjust_interval_with_disabled_adaptive_polling(
        self, mock_espn_client: MagicMock
    ) -> None:
        """Interval adjustment should be no-op when adaptive polling disabled.

        Educational Note:
            When adaptive_polling=False, _adjust_poll_interval() should
            not modify the scheduler's interval, even if called.
        """
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=False,
        )

        initial_interval = poller.get_current_interval()

        # Manually call adjustment (would be no-op)
        with patch.object(poller, "_scheduler"):
            poller._adjust_poll_interval()

        assert poller.get_current_interval() == initial_interval

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_has_active_games_with_empty_leagues(
        self,
        mock_get_live_games: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """has_active_games should handle empty leagues gracefully.

        Educational Note:
            When leagues list uses defaults (empty list provided), the
            method should still correctly check for active games across
            all default leagues.
        """
        mock_get_live_games.return_value = []
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=[],  # Falls back to defaults
            espn_client=mock_espn_client,
        )

        # Should check default leagues, not crash
        result = poller.has_active_games()
        assert isinstance(result, bool)

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_get_current_interval_consistency(
        self,
        mock_get_live_games: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """get_current_interval should be consistent across calls.

        Educational Note:
            Without external state changes, get_current_interval()
            should return the same value on consecutive calls. This
            verifies no internal state corruption.
        """
        mock_get_live_games.return_value = []

        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
        )

        intervals = [poller.get_current_interval() for _ in range(100)]

        # All should be the same
        assert all(i == intervals[0] for i in intervals)

    def test_adaptive_polling_state_at_initialization(self, mock_espn_client: MagicMock) -> None:
        """Initial adaptive polling state should be consistent.

        Educational Note:
            At initialization, _last_active_state should be None
            (unknown) and interval should match poll_interval or
            idle_interval based on initial state.
        """
        poller = ESPNGamePoller(
            poll_interval=10,
            idle_interval=120,
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        # Initial state should be None (not yet determined)
        assert poller._last_active_state is None

        # Interval should be poll_interval initially
        assert poller.get_current_interval() == 10

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_transition_from_active_to_inactive(
        self,
        mock_get_live_games: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Interval should transition from poll to idle when games end.

        Educational Note:
            When all games finish (has_active_games returns False),
            the interval should switch from poll_interval to idle_interval.
        """
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        # Start with active games
        mock_get_live_games.return_value = [{"game_id": 1}]
        poller._poll_wrapper()

        # Now no active games
        mock_get_live_games.return_value = []
        poller._poll_wrapper()

        # Should transition to idle
        assert poller._last_active_state is False

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_rapid_state_toggles(
        self,
        mock_get_live_games: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Rapid toggling between active/inactive should not corrupt state.

        Educational Note:
            In edge cases (game data flapping), rapid state changes
            should not cause internal inconsistency or errors.
        """
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        # Rapidly toggle state
        for i in range(100):
            if i % 2 == 0:
                mock_get_live_games.return_value = [{"game_id": 1}]
            else:
                mock_get_live_games.return_value = []
            poller._poll_wrapper()

        # Should complete without errors
        assert poller.stats["errors"] == 0
        # State should be consistent with last mock
        assert poller._last_active_state is False  # Last was empty

    def test_interval_boundaries_with_adaptive_polling(self, mock_espn_client: MagicMock) -> None:
        """Boundary intervals should work with adaptive polling.

        Educational Note:
            poll_interval at minimum (5) and idle_interval at large
            values should both work correctly with adaptive polling.
        """
        poller = ESPNGamePoller(
            poll_interval=5,  # Minimum
            idle_interval=3600,  # 1 hour
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        assert poller.poll_interval == 5
        assert poller.idle_interval == 3600
        assert poller.get_current_interval() == 5  # Starts at poll_interval
