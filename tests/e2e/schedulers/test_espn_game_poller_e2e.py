"""
End-to-End Tests for ESPN Game Poller.

Tests complete ESPNGamePoller workflows from initialization to data persistence.

Includes two categories:
1. Mock-based workflow tests: Validate poller logic with mocked API and DB
2. Real-API integration tests: Call the REAL ESPN API through the poller,
   mocking only the database layer. These catch data structure mismatches
   between what ESPN actually returns and what the poller expects.

Reference: TESTING_STRATEGY V3.2 - E2E tests for full workflow validation
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/e2e/schedulers/test_espn_game_poller_e2e.py -v -m e2e
"""

import socket
import time
from decimal import Decimal
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
            poll_interval=15,
            espn_client=mock_espn_client,
            per_league_polling=False,
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
            poll_interval=15,
            espn_client=mock_espn_client,
            per_league_polling=False,
        )

        poller.start()
        try:
            # Wait for multiple polls (15s interval)
            time.sleep(32)

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
            per_league_polling=False,
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
            poll_interval=15,
            espn_client=mock_espn_client,
            per_league_polling=False,
        )

        poller.start()
        try:
            time.sleep(32)

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
            per_league_polling=False,
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
            poll_interval=15,
            espn_client=mock_espn_client,
            per_league_polling=False,
        )

        # Initial state
        assert poller.enabled is False
        assert poller.stats["polls_completed"] == 0

        # Start
        poller.start()
        assert poller.enabled is True

        # Let it poll (initial poll happens immediately)
        time.sleep(2)  # type: ignore[unreachable]
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
            poll_interval=15,
            espn_client=mock_espn_client,
            per_league_polling=False,
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
            per_league_polling=False,
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

        # NFL has active games, NCAAF does not.
        # Use function-based side_effect to handle keyword arg calls
        # in any order (filter check + count check call get_live_games
        # multiple times with league= kwarg).
        def live_games_by_league(**kwargs: Any) -> list[dict[str, Any]]:
            return [{"game_id": 1}] if kwargs.get("league") == "nfl" else []

        mock_get_live.side_effect = live_games_by_league

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
            per_league_polling=False,
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
            poll_interval=15,  # Minimum allowed interval
            idle_interval=30,
            adaptive_polling=True,
            espn_client=mock_espn_client,
            per_league_polling=False,
        )

        # Verify initial configuration
        assert poller.adaptive_polling is True
        assert poller.poll_interval == 15
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
            assert poller.get_current_interval() == 15
            assert poller._last_active_state is True

            # Simulate games ending
            mock_get_live.return_value = []  # type: ignore[unreachable]
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
            poll_interval=15,  # Minimum allowed interval
            idle_interval=30,
            adaptive_polling=True,
            espn_client=mock_espn_client,
            per_league_polling=False,
        )

        poller.start()
        try:
            # Let scheduler run a few cycles (15s interval, wait for 2+ polls)
            time.sleep(17)

            # Should stay at poll interval while games active
            assert poller.get_current_interval() == 15
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
            poll_interval=15,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
            per_league_polling=False,
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

        assert poller.get_current_interval() == 15  # Active

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
            per_league_polling=False,
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
            poll_interval=15,
            idle_interval=60,
            adaptive_polling=True,
            espn_client=mock_espn_client,
            per_league_polling=False,
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
        assert poller.get_current_interval() == 15

        # Game in NCAAF only (NFL empty)
        def get_live_by_league_ncaaf(league: str):
            return [{"game_id": 2}] if league == "ncaaf" else []

        mock_get_live.side_effect = get_live_by_league_ncaaf
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 15  # Still active

        # All leagues empty
        mock_get_live.side_effect = None
        mock_get_live.return_value = []
        poller._adjust_poll_interval()
        assert poller.get_current_interval() == 60


# =============================================================================
# Real-API E2E Tests: ESPN Poller with Live ESPN API
# =============================================================================


def _is_espn_reachable() -> bool:
    """Check if ESPN API is reachable via socket connection.

    Educational Note:
        Uses a quick socket check rather than a full HTTP request
        for faster failure detection. This allows graceful skipping
        in CI environments without network access.
    """
    try:
        socket.create_connection(("site.api.espn.com", 443), timeout=5)
        return True
    except OSError:
        return False


@pytest.mark.e2e
@pytest.mark.skipif(
    not _is_espn_reachable(),
    reason="ESPN API unreachable - skipping real-API poller tests",
)
class TestRealAPIPollerIntegration:
    """E2E tests that call the REAL ESPN API through ESPNGamePoller.

    These tests fill a critical gap: the existing mock-based poller tests
    validate poller logic but cannot catch data structure mismatches between
    what ESPN actually returns and what the poller expects.

    The Kalshi poller has real-API e2e tests (test_kalshi_poller_e2e.py)
    that write to a real database. ESPN tests mock only the DB layer
    because ESPN is a public API (no credentials needed) and we want
    these tests to run in cross-platform CI without database access.

    Educational Note:
        Testing Layers for ESPN:
        - Layer 1: ESPNClient e2e (test_espn_e2e.py) - API -> Python objects
        - Layer 2: ESPNGamePoller mock (this file, above) - Poller logic with mocks
        - Layer 3: ESPNGamePoller real-API (THIS CLASS) - Real API -> Poller processing
          Catches: field name mismatches, type errors, missing keys, status mapping bugs
    """

    @pytest.fixture
    def real_espn_client(self):
        """Create a real ESPNClient for live API tests.

        Educational Note:
            We create a fresh client per test (function scope) to avoid
            rate limit state leaking between tests. The rate limit is
            generous (500/hour) so this is safe for a handful of tests.
        """
        from precog.api_connectors.espn_client import ESPNClient

        return ESPNClient(rate_limit_per_hour=500)

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_real_api_poll_once_nfl(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        real_espn_client: Any,
    ) -> None:
        """Poll NFL scoreboard from real ESPN API and validate poller processing.

        This is the primary real-API poller test. It verifies that:
        1. Real ESPN API data flows through the poller without errors
        2. The poller correctly extracts fields from ESPNGameFull format
        3. Database upsert is called with correctly typed arguments

        Educational Note:
            We mock DB functions to return plausible values so the poller
            completes its full processing pipeline. The key assertion is
            that poll_once() succeeds without exceptions -- meaning the
            real API response structure matches what the poller expects.
        """
        # DB mocks return plausible values
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=30,
            espn_client=real_espn_client,
            per_league_polling=False,
        )

        # This calls the real ESPN API -- should not raise
        result = poller.poll_once()

        # Basic result structure validation
        assert isinstance(result, dict)
        assert "items_fetched" in result
        assert "items_updated" in result
        assert "items_created" in result
        assert result["items_fetched"] >= 0
        assert result["items_updated"] >= 0

        # If games were found, verify DB was called with correct argument types
        if result["items_fetched"] > 0:
            assert mock_upsert.call_count > 0

            # Inspect the first upsert call's keyword arguments
            first_call_kwargs = mock_upsert.call_args_list[0].kwargs

            # espn_event_id should be a non-empty string
            assert isinstance(first_call_kwargs["espn_event_id"], str)
            assert len(first_call_kwargs["espn_event_id"]) > 0

            # Scores should be integers
            assert isinstance(first_call_kwargs["home_score"], int)
            assert isinstance(first_call_kwargs["away_score"], int)
            assert first_call_kwargs["home_score"] >= 0
            assert first_call_kwargs["away_score"] >= 0

            # Period should be an integer
            assert isinstance(first_call_kwargs["period"], int)
            assert first_call_kwargs["period"] >= 0

            # Game status should be one of the normalized values
            assert first_call_kwargs["game_status"] in {
                "pre",
                "in_progress",
                "halftime",
                "final",
            }

            # clock_seconds should be Decimal or None (Pattern 1: NEVER float)
            clock_val = first_call_kwargs["clock_seconds"]
            if clock_val is not None:
                assert isinstance(clock_val, Decimal), (
                    f"clock_seconds is {type(clock_val).__name__}, expected Decimal. "
                    "Pattern 1 violation: NEVER USE FLOAT."
                )

            # league should be passed through
            assert first_call_kwargs["league"] == "nfl"

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_real_api_multi_league_poll(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        real_espn_client: Any,
    ) -> None:
        """Poll multiple leagues from real ESPN API.

        Validates that the poller handles all configured leagues without
        errors when processing real API responses.

        Educational Note:
            Different leagues may have different data characteristics
            (e.g., NBA has no "down/distance", NHL has 3 periods not 4).
            This test ensures the poller handles all sports correctly.
        """
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            poll_interval=30,
            espn_client=real_espn_client,
            per_league_polling=False,
        )

        # Should not raise for any league
        result = poller.poll_once()

        assert isinstance(result, dict)
        assert result["items_fetched"] >= 0

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_real_api_venue_extraction(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        real_espn_client: Any,
    ) -> None:
        """Verify venue data is correctly extracted from real API responses.

        Educational Note:
            Venue data comes from metadata.venue in the ESPNGameFull format.
            The poller calls create_venue() with the extracted fields.
            This test verifies the extraction works with real API data.
        """
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=30,
            espn_client=real_espn_client,
            per_league_polling=False,
        )

        result = poller.poll_once()

        if result["items_fetched"] > 0:
            # create_venue should have been called
            assert mock_create_venue.call_count > 0

            # Verify venue args are strings (not None or wrong type)
            first_venue_call = mock_create_venue.call_args_list[0]
            venue_kwargs = first_venue_call.kwargs

            # venue_name is required and should be a string
            if "venue_name" in venue_kwargs and venue_kwargs["venue_name"] is not None:
                assert isinstance(venue_kwargs["venue_name"], str)
                assert len(venue_kwargs["venue_name"]) > 0

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_real_api_team_lookup_called_with_espn_ids(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        real_espn_client: Any,
    ) -> None:
        """Verify team lookups use real ESPN team IDs from the API.

        Educational Note:
            The poller extracts espn_team_id from each game's metadata
            and calls get_team_by_espn_id() to find the database team_id.
            This test validates that real ESPN IDs are passed correctly.
        """
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=30,
            espn_client=real_espn_client,
            per_league_polling=False,
        )

        result = poller.poll_once()

        if result["items_fetched"] > 0:
            # get_team_by_espn_id should be called twice per game (home + away)
            assert mock_get_team.call_count >= 2

            # Each call should have a string ESPN team ID and league
            for team_call in mock_get_team.call_args_list:
                espn_id = (
                    team_call.args[0] if team_call.args else team_call.kwargs.get("espn_team_id")
                )
                league = (
                    team_call.args[1] if len(team_call.args) > 1 else team_call.kwargs.get("league")
                )

                # ESPN team IDs are numeric strings (e.g., "1", "34")
                if espn_id is not None:
                    assert isinstance(espn_id, str), (
                        f"ESPN team ID should be string, got {type(espn_id).__name__}"
                    )

                assert league == "nfl"

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_real_api_all_upsert_calls_have_consistent_types(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        real_espn_client: Any,
    ) -> None:
        """Verify every upsert_game_state call has consistently typed arguments.

        This is the most thorough real-API validation: iterate ALL upsert
        calls from a real poll and verify every one has correct types.

        Educational Note:
            If one game out of 16 has unusual data (e.g., a postponed game
            with null fields), the poller must handle it gracefully. This
            test catches edge cases that a single-game test might miss.
        """
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        # Use NFL -- most likely to have games in the API
        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=30,
            espn_client=real_espn_client,
            per_league_polling=False,
        )

        result = poller.poll_once()

        if result["items_fetched"] == 0:
            pytest.skip("No NFL games available in ESPN API today")

        valid_statuses = {"pre", "in_progress", "halftime", "final"}

        for i, upsert_call in enumerate(mock_upsert.call_args_list):
            kwargs = upsert_call.kwargs
            game_id = kwargs.get("espn_event_id", f"call_{i}")

            # String fields
            assert isinstance(kwargs["espn_event_id"], str), (
                f"Game {game_id}: espn_event_id not a string"
            )
            assert kwargs["game_status"] in valid_statuses, (
                f"Game {game_id}: invalid game_status '{kwargs['game_status']}'"
            )

            # Integer fields
            assert isinstance(kwargs["home_score"], int), f"Game {game_id}: home_score not int"
            assert isinstance(kwargs["away_score"], int), f"Game {game_id}: away_score not int"
            assert isinstance(kwargs["period"], int), f"Game {game_id}: period not int"

            # Decimal or None (Pattern 1: NEVER float)
            clock = kwargs.get("clock_seconds")
            if clock is not None:
                assert isinstance(clock, Decimal), (
                    f"Game {game_id}: clock_seconds is {type(clock).__name__}, "
                    "expected Decimal (Pattern 1 violation)"
                )

            # League passed through
            assert kwargs["league"] == "nfl", (
                f"Game {game_id}: league is '{kwargs['league']}', expected 'nfl'"
            )

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_real_api_poll_wrapper_completes(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_live: MagicMock,
        real_espn_client: Any,
    ) -> None:
        """Verify _poll_wrapper() completes with real API data.

        _poll_wrapper() is what the scheduler actually calls. It includes
        error handling and adaptive polling adjustment. This test ensures
        the full wrapper path works with real data.

        Educational Note:
            _poll_wrapper() differs from poll_once() in that it:
            - Catches exceptions instead of propagating them
            - Updates stats (polls_completed, items_fetched, etc.)
            - Calls _adjust_poll_interval() for adaptive polling
        """
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_live.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            poll_interval=30,
            adaptive_polling=True,
            espn_client=real_espn_client,
            per_league_polling=False,
        )

        # Should not raise -- _poll_wrapper catches errors
        poller._poll_wrapper()

        # Stats should be updated
        assert poller.stats["polls_completed"] == 1
        assert poller.stats["errors"] == 0
        assert poller.stats["items_fetched"] >= 0
