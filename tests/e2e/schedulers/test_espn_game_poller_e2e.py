"""
End-to-End Tests for ESPN Game Poller.

Tests complete ESPNGamePoller workflows from initialization to data persistence.

Reference: TESTING_STRATEGY V3.2 - E2E tests for full workflow validation
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/e2e/schedulers/test_espn_game_poller_e2e.py -v -m e2e
"""

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.schedulers.espn_game_poller import (
    ESPNGamePoller,
    create_espn_poller,
    refresh_all_scoreboards,
    run_single_espn_poll,
)

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
def sample_game_data() -> dict[str, Any]:
    """Sample ESPN game data in ESPNGameFull format."""
    return {
        "metadata": {
            "espn_event_id": "401547417",
            "home_team": {
                "espn_team_id": "1",
                "team_code": "ATL",
                "display_name": "Atlanta Falcons",
            },
            "away_team": {
                "espn_team_id": "2",
                "team_code": "NO",
                "display_name": "New Orleans Saints",
            },
            "venue": {
                "espn_venue_id": "5348",
                "venue_name": "Mercedes-Benz Stadium",
                "city": "Atlanta",
                "state": "GA",
            },
            "game_date": "2025-12-07T18:00:00Z",
            "broadcast": "FOX",
            "neutral_site": False,
            "season_type": 2,
            "week_number": 14,
        },
        "state": {
            "home_score": 21,
            "away_score": 17,
            "period": 3,
            "clock_seconds": 845.5,
            "clock_display": "14:05",
            "game_status": "in_progress",
            "situation": {
                "down": 2,
                "distance": 7,
                "yard_line": 35,
                "possession_team_id": "1",
            },
            "linescores": [[7, 7, 7], [10, 7, 0]],
        },
    }


# =============================================================================
# E2E Tests: Complete Polling Workflow
# =============================================================================


@pytest.mark.e2e
class TestCompletePollingWorkflow:
    """E2E tests for complete polling workflow."""

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_full_poll_cycle(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test complete poll cycle from API fetch to DB update."""
        # Setup mocks
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]

        # Create and run poller
        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        # Execute single poll
        result = poller.poll_once()

        # Verify complete workflow
        assert result["items_fetched"] == 1
        assert result["items_updated"] == 1

        # Verify API was called
        mock_espn_client.get_scoreboard.assert_called_once_with("nfl")

        # Verify DB operations
        mock_upsert.assert_called_once()
        call_kwargs = mock_upsert.call_args.kwargs
        assert call_kwargs["espn_event_id"] == "401547417"
        assert call_kwargs["home_score"] == 21
        assert call_kwargs["away_score"] == 17

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_scheduler_runs_multiple_polls(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test scheduler executes multiple poll cycles."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        poller.start()
        try:
            # Wait for multiple polls
            time.sleep(11)

            # Should have at least 3 polls (initial + 2 scheduled)
            stats = poller.stats
            assert stats["polls_completed"] >= 3
            assert stats["items_fetched"] >= 3
        finally:
            poller.stop()


# =============================================================================
# E2E Tests: Factory Function Workflows
# =============================================================================


@pytest.mark.e2e
class TestFactoryFunctionWorkflows:
    """E2E tests for factory function workflows."""

    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_create_espn_poller_workflow(self, mock_client_class: MagicMock) -> None:
        """Test create_espn_poller factory workflow."""
        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []
        mock_client_class.return_value = mock_client

        # Create via factory
        poller = create_espn_poller(
            leagues=["nfl", "nba"],
            poll_interval=30,
        )

        # Verify configuration
        assert poller.leagues == ["nfl", "nba"]
        assert poller.poll_interval == 30

        # Test can poll
        result = poller.poll_once()
        assert "items_fetched" in result

    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_run_single_poll_workflow(self, mock_client_class: MagicMock) -> None:
        """Test run_single_espn_poll workflow."""
        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []
        mock_client_class.return_value = mock_client

        result = run_single_espn_poll(leagues=["nfl"])

        assert "items_fetched" in result
        assert "items_updated" in result
        mock_client.get_scoreboard.assert_called_once_with("nfl")

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_refresh_all_scoreboards_workflow(
        self,
        mock_client_class: MagicMock,
        mock_get_live: MagicMock,
    ) -> None:
        """Test refresh_all_scoreboards workflow."""
        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []
        mock_client_class.return_value = mock_client
        mock_get_live.return_value = []

        result = refresh_all_scoreboards(leagues=["nfl", "ncaaf"])

        assert result["total_games_fetched"] == 0
        assert "elapsed_seconds" in result
        assert len(result["leagues_polled"]) == 2


# =============================================================================
# E2E Tests: Multi-League Workflow
# =============================================================================


@pytest.mark.e2e
class TestMultiLeagueWorkflow:
    """E2E tests for multi-league polling workflow."""

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_multi_league_poll(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test polling multiple leagues."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        # Different games for different leagues
        nfl_game = {
            "metadata": {
                "espn_event_id": "nfl_game_1",
                "home_team": {"espn_team_id": "1"},
                "away_team": {"espn_team_id": "2"},
                "venue": {"venue_name": "Stadium A"},
            },
            "state": {"home_score": 14, "away_score": 7, "game_status": "in_progress"},
        }
        nba_game = {
            "metadata": {
                "espn_event_id": "nba_game_1",
                "home_team": {"espn_team_id": "10"},
                "away_team": {"espn_team_id": "20"},
                "venue": {"venue_name": "Arena B"},
            },
            "state": {"home_score": 98, "away_score": 102, "game_status": "final"},
        }

        def mock_scoreboard(league: str) -> list:
            if league == "nfl":
                return [nfl_game]
            if league == "nba":
                return [nba_game]
            return []

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()

        assert result["items_fetched"] == 2
        assert result["items_updated"] == 2
        assert mock_upsert.call_count == 2


# =============================================================================
# E2E Tests: Error Recovery Workflow
# =============================================================================


@pytest.mark.e2e
class TestErrorRecoveryWorkflow:
    """E2E tests for error recovery workflow."""

    def test_recovers_from_api_errors(self, mock_espn_client: MagicMock) -> None:
        """Test poller recovers from API errors."""
        call_count = 0

        def mock_scoreboard(league: str) -> list:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("Temporary API error")
            return []

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        poller.start()
        try:
            time.sleep(11)

            # Should have recovered and continued
            assert poller.enabled is True
            # Should have logged errors
            assert poller.stats["errors"] >= 2
        finally:
            poller.stop()

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_partial_league_failure(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test continues polling when one league fails.

        Note: _poll_wrapper() uses _poll_once() which catches per-league errors.
        poll_once() is a direct method that propagates errors immediately.
        This test uses _poll_wrapper() to verify error isolation behavior.
        """
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        game = {
            "metadata": {
                "espn_event_id": "game_1",
                "home_team": {"espn_team_id": "1"},
                "away_team": {"espn_team_id": "2"},
                "venue": {"venue_name": "Stadium"},
            },
            "state": {"home_score": 0, "away_score": 0, "game_status": "pre"},
        }

        def mock_scoreboard(league: str) -> list:
            if league == "nfl":
                raise RuntimeError("NFL API down")
            return [game]

        mock_espn_client.get_scoreboard.side_effect = mock_scoreboard

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        # Use _poll_wrapper which catches per-league errors
        poller._poll_wrapper()

        # Should have logged 1 poll with 1 error
        stats = poller.stats
        assert stats["polls_completed"] == 1
        assert stats["errors"] == 1

        # Both leagues should have been attempted
        assert mock_espn_client.get_scoreboard.call_count == 2


# =============================================================================
# E2E Tests: Lifecycle Workflow
# =============================================================================


@pytest.mark.e2e
class TestLifecycleWorkflow:
    """E2E tests for complete lifecycle workflow."""

    def test_full_lifecycle(self, mock_espn_client: MagicMock) -> None:
        """Test complete start -> poll -> stop lifecycle."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        # Initial state
        assert poller.enabled is False
        assert poller.stats["polls_completed"] == 0

        # Start
        poller.start()
        assert poller.enabled is True

        # Let it poll
        time.sleep(2)
        assert poller.stats["polls_completed"] >= 1

        # Stop
        poller.stop()
        assert poller.enabled is False

        # Final stats
        final_polls = poller.stats["polls_completed"]
        assert final_polls >= 1

    def test_restart_preserves_stats(self, mock_espn_client: MagicMock) -> None:
        """Test restarting poller preserves accumulated stats."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,
            espn_client=mock_espn_client,
        )

        # First run
        poller.start()
        time.sleep(2)
        poller.stop()

        first_polls = poller.stats["polls_completed"]
        assert first_polls >= 1

        # Second run
        poller.start()
        time.sleep(2)
        poller.stop()

        # Stats should have accumulated
        assert poller.stats["polls_completed"] >= first_polls + 1


# =============================================================================
# E2E Tests: Refresh Scoreboards Workflow
# =============================================================================


@pytest.mark.e2e
class TestRefreshScoreboardsWorkflow:
    """E2E tests for refresh_scoreboards workflow."""

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_refresh_scoreboards_complete(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test complete refresh_scoreboards workflow."""
        mock_get_live.return_value = []
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        result = poller.refresh_scoreboards()

        # Verify result structure
        assert result["leagues_polled"] == ["nfl", "ncaaf"]
        assert isinstance(result["games_by_league"], dict)
        assert result["total_games_fetched"] == 0
        assert result["elapsed_seconds"] >= 0
        assert "timestamp" in result

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_refresh_with_active_games(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test refresh_scoreboards with active games."""
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        # NFL has active games
        mock_get_live.side_effect = [
            [{"game_id": 1}],  # NFL has active
            [],  # NCAAF no active
            [{"game_id": 1}],  # Count check
        ]

        game = {
            "metadata": {
                "espn_event_id": "live_game_1",
                "home_team": {"espn_team_id": "1"},
                "away_team": {"espn_team_id": "2"},
                "venue": {"venue_name": "Stadium"},
            },
            "state": {"home_score": 14, "away_score": 10, "game_status": "in_progress"},
        }
        mock_espn_client.get_scoreboard.return_value = [game]

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        result = poller.refresh_scoreboards(active_only=True)

        # Should only poll NFL (has active games)
        assert "nfl" in result["leagues_polled"]
        assert result["active_games"] >= 1


# =============================================================================
# E2E Tests: Adaptive Polling Workflow (Issue #234)
# =============================================================================


@pytest.mark.e2e
class TestAdaptivePollingWorkflow:
    """E2E tests for adaptive polling workflow.

    Related: Issue #234 - Adaptive polling to reduce API load during idle periods
    Reference: TESTING_STRATEGY V3.2 - E2E tests for complete workflow validation

    Adaptive polling adjusts the polling interval based on game activity:
    - Active games: poll_interval (default 15s) for real-time updates
    - No active games: idle_interval (default 60s) to reduce API load
    """

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_complete_lifecycle(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """E2E: Test complete adaptive polling lifecycle.

        Workflow:
        1. Initialize poller with adaptive polling enabled
        2. Start with no active games -> idle interval
        3. Active games appear -> poll interval
        4. Games end -> idle interval
        5. Verify scheduler reschedules job correctly
        """
        # Initially no active games
        mock_get_live.return_value = []
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,  # Fast for testing
            idle_interval=30,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        # Verify initial configuration
        assert poller.adaptive_polling is True
        assert poller.poll_interval == 5
        assert poller.idle_interval == 30

        # Start poller
        poller.start()
        try:
            time.sleep(0.5)

            # Should be at idle interval (no games)
            assert poller.get_current_interval() == 30
            assert poller._last_active_state is False

            # Simulate games becoming active
            mock_get_live.return_value = [{"game_id": 1, "status": "in_progress"}]
            poller._adjust_poll_interval()

            # Should switch to poll interval
            assert poller.get_current_interval() == 5
            assert poller._last_active_state is True

            # Simulate games ending
            mock_get_live.return_value = []
            poller._adjust_poll_interval()

            # Should return to idle interval
            assert poller.get_current_interval() == 30
            assert poller._last_active_state is False

        finally:
            poller.stop()

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_preserves_state_across_polls(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """E2E: Verify adaptive state preserved across multiple poll cycles."""
        mock_get_live.return_value = [{"game_id": 1}]  # Active
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=5,  # Minimum allowed interval
            idle_interval=30,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        poller.start()
        try:
            # Let scheduler run a few cycles (longer wait for more polls)
            time.sleep(7)

            # Should stay at poll interval while games active
            assert poller.get_current_interval() == 5
            # Should have at least 2 polls (initial + scheduled)
            assert poller.stats["polls_completed"] >= 2

        finally:
            poller.stop()

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_with_poll_wrapper(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """E2E: Test _poll_wrapper updates adaptive state after each poll.

        Note: poll_once() is the raw poll method that doesn't adjust intervals.
        _poll_wrapper() is used by the scheduler and calls _adjust_poll_interval().
        """
        mock_get_live.return_value = []
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=10,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        # Initial poll with no active games (use _poll_wrapper which adjusts interval)
        poller._poll_wrapper()

        assert poller.get_current_interval() == 60  # Idle

        # Simulate game starting
        game = {
            "metadata": {
                "espn_event_id": "game_1",
                "home_team": {"espn_team_id": "1"},
                "away_team": {"espn_team_id": "2"},
                "venue": {"venue_name": "Stadium"},
            },
            "state": {"home_score": 7, "away_score": 3, "game_status": "in_progress"},
        }
        mock_get_live.return_value = [{"game_id": 1}]
        mock_espn_client.get_scoreboard.return_value = [game]

        # Second poll with active games
        poller._poll_wrapper()

        assert poller.get_current_interval() == 10  # Active

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_create_poller_factory_with_adaptive_polling(
        self,
        mock_client_class: MagicMock,
        mock_get_live: MagicMock,
    ) -> None:
        """E2E: Test factory function creates poller with adaptive polling enabled.

        Note: create_espn_poller() always creates pollers with adaptive_polling=True
        by default in the ESPNGamePoller constructor.
        """
        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []
        mock_client_class.return_value = mock_client
        mock_get_live.return_value = []

        # Create via factory (adaptive polling is enabled by default)
        poller = create_espn_poller(
            leagues=["nfl"],
            poll_interval=15,
            idle_interval=60,
        )

        # Verify factory respects poll/idle intervals
        assert poller.poll_interval == 15
        assert poller.idle_interval == 60

        # Adaptive polling is enabled by default in ESPNGamePoller
        assert poller.adaptive_polling is True

        # After poll wrapper (which adjusts interval), should be at idle
        poller._poll_wrapper()
        assert poller.get_current_interval() == 60

    def test_adaptive_polling_disabled_workflow(
        self,
        mock_espn_client: MagicMock,
    ) -> None:
        """E2E: Verify behavior when adaptive polling is disabled."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=15,
            idle_interval=60,
            adaptive_polling=False,  # Disabled
            espn_client=mock_espn_client,
        )

        assert poller.adaptive_polling is False

        # Should always use poll_interval
        assert poller.get_current_interval() == 15

        poller.start()
        try:
            time.sleep(1)

            # Still at poll_interval regardless of game activity
            assert poller.get_current_interval() == 15

        finally:
            poller.stop()

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adaptive_polling_multi_league_workflow(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """E2E: Test adaptive polling with multiple leagues.

        If ANY league has active games, use poll_interval.
        Only use idle_interval when ALL leagues have no active games.
        """
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba"],
            poll_interval=10,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
        )

        # No games in any league
        mock_get_live.return_value = []
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 60

        # Game in NFL only
        def get_live_by_league(league: str):
            return [{"game_id": 1}] if league == "nfl" else []

        mock_get_live.side_effect = get_live_by_league
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 10

        # Game in NCAAF only (NFL empty)
        def get_live_by_league_ncaaf(league: str):
            return [{"game_id": 2}] if league == "ncaaf" else []

        mock_get_live.side_effect = get_live_by_league_ncaaf
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 10  # Still active

        # All leagues empty
        mock_get_live.side_effect = None
        mock_get_live.return_value = []
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 60
