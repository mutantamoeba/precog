"""
Integration Tests for ESPN Game Poller.

Tests ESPNGamePoller integration with APScheduler and lifecycle management.

Reference: TESTING_STRATEGY V3.2 - Integration tests for component interactions
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/integration/schedulers/test_espn_game_poller_integration.py -v -m integration
"""

import threading
import time
from typing import Any
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


@pytest.fixture
def mock_db_operations() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Create mock database operations."""
    get_team = MagicMock(return_value={"team_id": 1})
    upsert_game = MagicMock()
    create_venue = MagicMock(return_value=100)
    get_live_games = MagicMock(return_value=[])
    return get_team, upsert_game, create_venue, get_live_games


# =============================================================================
# Integration Tests: Scheduler Lifecycle
# =============================================================================


@pytest.mark.integration
class TestSchedulerLifecycle:
    """Integration tests for scheduler lifecycle management."""

    def test_start_initializes_scheduler(self, mock_espn_client: MagicMock) -> None:
        """Test start() creates and starts the scheduler."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        assert poller._scheduler is None
        assert poller.enabled is False

        poller.start()

        try:
            assert poller._scheduler is not None
            assert poller.enabled is True
            assert poller.is_running() is True
        finally:
            poller.stop()

    def test_stop_shuts_down_scheduler(self, mock_espn_client: MagicMock) -> None:
        """Test stop() properly shuts down scheduler."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )
        poller.start()

        assert poller.enabled is True

        poller.stop()

        assert poller.enabled is False
        assert poller.is_running() is False

    def test_multiple_start_stop_cycles(self, mock_espn_client: MagicMock) -> None:
        """Test poller handles multiple start/stop cycles."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        for _ in range(3):
            poller.start()
            assert poller.enabled is True
            poller.stop()
            assert poller.enabled is False

    def test_stop_on_unstarted_poller(self, mock_espn_client: MagicMock) -> None:
        """Test stop() on never-started poller is safe."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        # Should not raise
        poller.stop()
        assert poller.enabled is False

    def test_double_start_raises_error(self, mock_espn_client: MagicMock) -> None:
        """Test calling start() twice raises RuntimeError."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        poller.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                poller.start()
            assert poller.enabled is True
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Poll Execution
# =============================================================================


@pytest.mark.integration
class TestPollExecution:
    """Integration tests for poll execution."""

    def test_poll_executes_on_schedule(self, mock_espn_client: MagicMock) -> None:
        """Test polls execute according to interval."""
        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        try:
            # Wait for initial poll + at least one scheduled poll
            # Note: Using 12s (2.5x poll_interval) to account for:
            # - CI startup delays (1-2s)
            # - APScheduler thread scheduling variability
            # - Adaptive polling reschedule on first poll
            time.sleep(12)

            # Should have at least 2 polls
            assert mock_espn_client.get_scoreboard.call_count >= 2
        finally:
            poller.stop()

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_poll_results_accumulated(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test poll results are accumulated in stats."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        game_data = {
            "metadata": {
                "espn_event_id": "401547417",
                "home_team": {"espn_team_id": "1", "team_code": "ATL"},
                "away_team": {"espn_team_id": "2", "team_code": "NO"},
                "venue": {"venue_name": "Stadium"},
            },
            "state": {
                "home_score": 21,
                "away_score": 17,
                "game_status": "in_progress",
            },
        }
        mock_espn_client.get_scoreboard.return_value = [game_data]

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        try:
            # Note: Using 12s (2.5x poll_interval) to account for CI delays
            time.sleep(12)

            stats = poller.stats
            assert stats["polls_completed"] >= 2
            assert stats["items_fetched"] >= 2
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling in scheduler context."""

    def test_poll_error_doesnt_stop_scheduler(self, mock_espn_client: MagicMock) -> None:
        """Test poll errors don't crash the scheduler."""
        # First 2 calls error, then succeed
        call_count = 0

        def mock_scoreboard(league: str) -> list:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("Test error")
            return []

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        try:
            # Note: Using 17s (3.5x poll_interval) to ensure 2+ error cycles on CI
            time.sleep(17)

            # Scheduler should still be running
            assert poller.enabled is True
            # Errors should be tracked
            assert poller.stats["errors"] >= 2
        finally:
            poller.stop()

    def test_error_message_captured(self, mock_espn_client: MagicMock) -> None:
        """Test error message is captured in stats."""
        mock_espn_client.get_scoreboard.side_effect = ValueError("Integration test error")

        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        try:
            time.sleep(1)

            stats = poller.stats
            assert stats["errors"] >= 1
            assert stats["last_error"] == "Integration test error"
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Stats Thread Safety
# =============================================================================


@pytest.mark.integration
class TestStatsThreadSafety:
    """Integration tests for stats access thread safety."""

    def test_concurrent_stats_access(self, mock_espn_client: MagicMock) -> None:
        """Test stats can be accessed safely while polling."""
        poller = ESPNGamePoller(
            poll_interval=5,
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller.start()

        try:
            stats_snapshots: list[dict[str, Any]] = []
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

            assert len(errors) == 0
            assert len(stats_snapshots) > 0
        finally:
            poller.stop()


# =============================================================================
# Integration Tests: Job Persistence
# =============================================================================


@pytest.mark.integration
class TestJobPersistence:
    """Integration tests for job persistence."""

    def test_persistence_disabled_by_default(self, mock_espn_client: MagicMock) -> None:
        """Test job persistence is disabled by default."""
        poller = ESPNGamePoller(
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        assert poller.persist_jobs is False
        assert poller.job_store_url is None

    def test_persistence_enabled_with_url(self, mock_espn_client: MagicMock) -> None:
        """Test job persistence can be enabled with URL."""
        poller = ESPNGamePoller(
            poll_interval=5,
            persist_jobs=True,
            job_store_url="sqlite:///test_jobs.db",
            espn_client=mock_espn_client,
        )

        assert poller.persist_jobs is True
        assert poller.job_store_url == "sqlite:///test_jobs.db"


# =============================================================================
# Integration Tests: Refresh Scoreboards
# =============================================================================


@pytest.mark.integration
class TestRefreshScoreboards:
    """Integration tests for refresh_scoreboards method."""

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_refresh_scoreboards_returns_result(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test refresh_scoreboards returns expected structure."""
        mock_get_live.return_value = []
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        result = poller.refresh_scoreboards()

        assert "leagues_polled" in result
        assert "games_by_league" in result
        assert "total_games_fetched" in result
        assert "elapsed_seconds" in result
        assert "timestamp" in result

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_refresh_scoreboards_active_only(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test refresh_scoreboards with active_only=True."""
        # NFL has active games, NCAAF doesn't
        mock_get_live.side_effect = [
            [{"game_id": 1}],  # NFL has games
            [],  # NCAAF no games
            [{"game_id": 1}],  # NFL count check
        ]
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        result = poller.refresh_scoreboards(active_only=True)

        # Should only poll NFL (has active games)
        assert "nfl" in result["leagues_polled"]


# =============================================================================
# Integration Tests: Multi-League Polling
# =============================================================================


@pytest.mark.integration
class TestMultiLeaguePolling:
    """Integration tests for multi-league polling."""

    def test_polls_all_configured_leagues(self, mock_espn_client: MagicMock) -> None:
        """Test poller polls all configured leagues."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_espn_client,
        )

        poller.poll_once()

        # Should be called for each league
        assert mock_espn_client.get_scoreboard.call_count == 3

        # Check each league was polled
        calls = [c.args[0] for c in mock_espn_client.get_scoreboard.call_args_list]
        assert "nfl" in calls
        assert "nba" in calls
        assert "nhl" in calls

    def test_league_error_doesnt_stop_others(self, mock_espn_client: MagicMock) -> None:
        """Test error in one league doesn't stop polling others.

        Note: _poll_wrapper() uses _poll_once() which catches per-league errors.
        poll_once() is a direct method that propagates errors immediately.
        This test verifies the scheduler's behavior via _poll_wrapper().
        """

        def mock_scoreboard(league: str) -> list:
            if league == "nfl":
                raise RuntimeError("NFL API error")
            return []

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        # Use _poll_wrapper which internally uses _poll_once (catches per-league errors)
        poller._poll_wrapper()

        # Both leagues should have been attempted
        assert mock_espn_client.get_scoreboard.call_count == 2


# =============================================================================
# Integration Tests: Adaptive Polling (Issue #234)
# =============================================================================


@pytest.mark.integration
class TestAdaptivePollingIntegration:
    """Integration tests for adaptive polling with scheduler lifecycle.

    Related: Issue #234 - Adaptive polling to reduce API load during idle periods.
    """

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_with_scheduler(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test adaptive polling adjusts interval during scheduler lifecycle."""
        # Start with no active games
        mock_get_live.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        # Before adjustment, should use poll_interval
        assert poller.get_current_interval() == 5

        # After adjustment with no games, should use idle_interval
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 60

        # Simulate games becoming active
        mock_get_live.return_value = [{"game_id": 1}]
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 5

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_state_transitions(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test adaptive polling tracks state transitions correctly."""
        mock_get_live.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        # Initial state is None
        assert poller._last_active_state is None

        # First adjustment sets state
        poller._adjust_poll_interval()
        assert poller._last_active_state is False  # No games = inactive

        # Simulate active games
        mock_get_live.return_value = [{"game_id": 1}]
        poller._adjust_poll_interval()
        assert poller._last_active_state is True  # Has games = active

        # Back to no games
        mock_get_live.return_value = []
        poller._adjust_poll_interval()
        assert poller._last_active_state is False  # No games = inactive

    def test_disabled_adaptive_polling_keeps_poll_interval(
        self,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test disabled adaptive polling always uses poll_interval."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            adaptive_polling=False,
            espn_client=mock_espn_client,
        )

        # Should always use poll_interval
        assert poller.get_current_interval() == 15

        # _adjust_poll_interval should be a no-op
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 15

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_poll_wrapper_triggers_adaptive_adjustment(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test _poll_wrapper calls _adjust_poll_interval when enabled."""
        mock_get_live.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        # Before poll
        assert poller._last_active_state is None

        # Run poll wrapper
        poller._poll_wrapper()

        # Should have been adjusted
        assert poller._last_active_state is False
        assert poller.get_current_interval() == 60

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_during_running_scheduler(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test adaptive polling works during live scheduler run."""
        # Start with no games
        mock_get_live.return_value = []

        poller = ESPNGamePoller(
            poll_interval=5,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )
        poller.start()

        try:
            # Let first poll run
            time.sleep(1)

            # Should have adjusted to idle
            assert poller.get_current_interval() == 60
            assert poller._last_active_state is False

        finally:
            poller.stop()


@pytest.mark.integration
class TestHasActiveGamesIntegration:
    """Integration tests for has_active_games method."""

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_has_active_games_checks_all_leagues(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test has_active_games checks all configured leagues."""

        # NFL has games, NCAAF doesn't
        def mock_live(league: str) -> list:
            if league == "nfl":
                return [{"game_id": 1}]
            return []

        mock_get_live.side_effect = mock_live

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        # Should return True because NFL has games
        assert poller.has_active_games() is True

        # Check both leagues were checked
        assert mock_get_live.call_count == 1  # Short-circuits on first True

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_has_active_games_no_games(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test has_active_games returns False when no games."""
        mock_get_live.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        assert poller.has_active_games() is False

        # Should have checked both leagues
        assert mock_get_live.call_count == 2
