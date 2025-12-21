"""
Unit Tests for ESPN Game Poller.

Tests ESPNGamePoller initialization, configuration, and basic functionality.

Reference: TESTING_STRATEGY V3.2 - Unit tests for isolated functionality
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/unit/schedulers/test_espn_game_poller_unit.py -v -m unit
"""

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
# Unit Tests: Initialization
# =============================================================================


@pytest.mark.unit
class TestESPNGamePollerInitialization:
    """Unit tests for ESPNGamePoller initialization."""

    def test_default_initialization(self, mock_espn_client: MagicMock) -> None:
        """Test poller initializes with defaults."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller.leagues == ["nfl", "ncaaf"]
        assert poller.poll_interval == 15
        assert poller.idle_interval == 60
        assert poller.persist_jobs is False
        assert poller.enabled is False

    def test_custom_leagues(self, mock_espn_client: MagicMock) -> None:
        """Test poller with custom leagues."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_espn_client,
        )
        assert poller.leagues == ["nfl", "nba", "nhl"]

    def test_custom_poll_interval(self, mock_espn_client: MagicMock) -> None:
        """Test poller with custom poll interval."""
        poller = ESPNGamePoller(
            poll_interval=30,
            espn_client=mock_espn_client,
        )
        assert poller.poll_interval == 30

    def test_custom_idle_interval(self, mock_espn_client: MagicMock) -> None:
        """Test poller with custom idle interval."""
        poller = ESPNGamePoller(
            idle_interval=120,
            espn_client=mock_espn_client,
        )
        assert poller.idle_interval == 120

    def test_poll_interval_minimum_enforced(self, mock_espn_client: MagicMock) -> None:
        """Test poll interval below minimum raises error."""
        with pytest.raises(ValueError, match="must be at least"):
            ESPNGamePoller(poll_interval=2, espn_client=mock_espn_client)

    def test_idle_interval_minimum_enforced(self, mock_espn_client: MagicMock) -> None:
        """Test idle interval below 15 raises error."""
        with pytest.raises(ValueError, match="must be at least 15"):
            ESPNGamePoller(idle_interval=10, espn_client=mock_espn_client)

    def test_persist_jobs_requires_url(self, mock_espn_client: MagicMock) -> None:
        """Test persist_jobs=True requires job_store_url."""
        with pytest.raises(ValueError, match="job_store_url required"):
            ESPNGamePoller(
                persist_jobs=True,
                espn_client=mock_espn_client,
            )

    def test_persist_jobs_with_url(self, mock_espn_client: MagicMock) -> None:
        """Test persist_jobs=True with valid URL."""
        poller = ESPNGamePoller(
            persist_jobs=True,
            job_store_url="sqlite:///test_jobs.db",
            espn_client=mock_espn_client,
        )
        assert poller.persist_jobs is True
        assert poller.job_store_url == "sqlite:///test_jobs.db"

    def test_negative_poll_interval_rejected(self, mock_espn_client: MagicMock) -> None:
        """Test negative poll interval raises error."""
        with pytest.raises(ValueError):
            ESPNGamePoller(poll_interval=-1, espn_client=mock_espn_client)


# =============================================================================
# Unit Tests: Job Name
# =============================================================================


@pytest.mark.unit
class TestESPNGamePollerJobName:
    """Unit tests for job name."""

    def test_get_job_name(self, mock_espn_client: MagicMock) -> None:
        """Test job name is descriptive."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._get_job_name() == "ESPN Game State Poll"


# =============================================================================
# Unit Tests: Status Normalization
# =============================================================================


@pytest.mark.unit
class TestStatusNormalization:
    """Unit tests for game status normalization."""

    def test_normalize_pre_status(self, mock_espn_client: MagicMock) -> None:
        """Test 'pre' status normalization."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._normalize_game_status("pre") == "pre"
        assert poller._normalize_game_status("PRE") == "pre"
        assert poller._normalize_game_status("scheduled") == "pre"

    def test_normalize_in_progress_status(self, mock_espn_client: MagicMock) -> None:
        """Test in-progress status normalization."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._normalize_game_status("in") == "in_progress"
        assert poller._normalize_game_status("IN") == "in_progress"
        assert poller._normalize_game_status("in_progress") == "in_progress"

    def test_normalize_halftime_status(self, mock_espn_client: MagicMock) -> None:
        """Test halftime status normalization."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._normalize_game_status("halftime") == "halftime"
        assert poller._normalize_game_status("HALFTIME") == "halftime"

    def test_normalize_final_status(self, mock_espn_client: MagicMock) -> None:
        """Test final status normalization."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._normalize_game_status("post") == "final"
        assert poller._normalize_game_status("final") == "final"
        assert poller._normalize_game_status("final/ot") == "final"
        assert poller._normalize_game_status("final/2ot") == "final"

    def test_normalize_unknown_status(self, mock_espn_client: MagicMock) -> None:
        """Test unknown status defaults to 'pre'."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._normalize_game_status("unknown") == "pre"
        assert poller._normalize_game_status("weird_status") == "pre"

    def test_normalize_empty_status(self, mock_espn_client: MagicMock) -> None:
        """Test empty/None status defaults to 'pre'."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller._normalize_game_status("") == "pre"


# =============================================================================
# Unit Tests: Poll Once
# =============================================================================


@pytest.mark.unit
class TestPollOnce:
    """Unit tests for poll_once method."""

    def test_poll_once_empty_scoreboard(self, mock_espn_client: MagicMock) -> None:
        """Test poll_once with no games."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()

        assert result["items_fetched"] == 0
        assert result["items_updated"] == 0
        assert result["items_created"] == 0

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_poll_once_with_games(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test poll_once with games."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()

        assert result["items_fetched"] == 1
        assert result["items_updated"] == 1
        mock_upsert.assert_called_once()

    def test_poll_once_custom_leagues(self, mock_espn_client: MagicMock) -> None:
        """Test poll_once with custom leagues parameter."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once(leagues=["ncaaf"])

        mock_espn_client.get_scoreboard.assert_called_once_with("ncaaf")
        assert result["items_fetched"] == 0


# =============================================================================
# Unit Tests: Team ID Lookup
# =============================================================================


@pytest.mark.unit
class TestTeamIdLookup:
    """Unit tests for team ID lookup."""

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    def test_get_db_team_id_found(
        self,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test team ID lookup when team exists."""
        mock_get_team.return_value = {"team_id": 42}
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        team_id = poller._get_db_team_id("123", "nfl", "ATL")

        assert team_id == 42
        mock_get_team.assert_called_once_with("123", "nfl")

    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    def test_get_db_team_id_not_found(
        self,
        mock_get_team: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test team ID lookup when team doesn't exist."""
        mock_get_team.return_value = None
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        team_id = poller._get_db_team_id("999", "nfl", "UNK")

        assert team_id is None

    def test_get_db_team_id_none_input(self, mock_espn_client: MagicMock) -> None:
        """Test team ID lookup with None input."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        team_id = poller._get_db_team_id(None, "nfl", "ATL")

        assert team_id is None


# =============================================================================
# Unit Tests: Venue Handling
# =============================================================================


@pytest.mark.unit
class TestVenueHandling:
    """Unit tests for venue handling."""

    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_ensure_venue_normalized_success(
        self,
        mock_create_venue: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test venue creation succeeds."""
        mock_create_venue.return_value = 100
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        venue_info = {
            "espn_venue_id": "5348",
            "venue_name": "Mercedes-Benz Stadium",
            "city": "Atlanta",
            "state": "GA",
            "capacity": 71000,
            "indoor": True,
        }

        venue_id = poller._ensure_venue_normalized(venue_info)  # type: ignore[arg-type]

        assert venue_id == 100
        mock_create_venue.assert_called_once()

    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_ensure_venue_normalized_error(
        self,
        mock_create_venue: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test venue creation error returns None."""
        mock_create_venue.side_effect = Exception("DB error")
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        venue_info = {"venue_name": "Test Stadium"}

        venue_id = poller._ensure_venue_normalized(venue_info)  # type: ignore[arg-type]

        assert venue_id is None

    def test_ensure_venue_normalized_no_name(self, mock_espn_client: MagicMock) -> None:
        """Test venue creation with no name returns None."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        venue_id = poller._ensure_venue_normalized({})

        assert venue_id is None


# =============================================================================
# Unit Tests: Stats Access
# =============================================================================


@pytest.mark.unit
class TestStatsAccess:
    """Unit tests for stats access."""

    def test_initial_stats(self, mock_espn_client: MagicMock) -> None:
        """Test initial stats are zero."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        stats = poller.stats

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["errors"] == 0

    def test_stats_copy_independent(self, mock_espn_client: MagicMock) -> None:
        """Test stats returns independent copy."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        stats1 = poller.stats
        stats1["polls_completed"] = 999

        stats2 = poller.stats
        assert stats2["polls_completed"] == 0


# =============================================================================
# Unit Tests: Factory Functions
# =============================================================================


@pytest.mark.unit
class TestFactoryFunctions:
    """Unit tests for factory functions."""

    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_create_espn_poller_defaults(self, mock_client_class: MagicMock) -> None:
        """Test create_espn_poller with defaults."""
        poller = create_espn_poller()

        assert poller.leagues == ["nfl", "ncaaf"]
        assert poller.poll_interval == 15
        assert poller.idle_interval == 60

    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_create_espn_poller_custom(self, mock_client_class: MagicMock) -> None:
        """Test create_espn_poller with custom settings."""
        poller = create_espn_poller(
            leagues=["nba"],
            poll_interval=30,
            idle_interval=90,
        )

        assert poller.leagues == ["nba"]
        assert poller.poll_interval == 30
        assert poller.idle_interval == 90

    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_run_single_espn_poll(self, mock_client_class: MagicMock) -> None:
        """Test run_single_espn_poll."""
        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []
        mock_client_class.return_value = mock_client

        result = run_single_espn_poll(leagues=["nfl"])

        assert "items_fetched" in result
        assert "items_updated" in result

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    @patch("precog.schedulers.espn_game_poller.ESPNClient")
    def test_refresh_all_scoreboards(
        self,
        mock_client_class: MagicMock,
        mock_get_live: MagicMock,
    ) -> None:
        """Test refresh_all_scoreboards."""
        mock_client = MagicMock()
        mock_client.get_scoreboard.return_value = []
        mock_client_class.return_value = mock_client
        mock_get_live.return_value = []

        result = refresh_all_scoreboards(leagues=["nfl"])

        assert "total_games_fetched" in result
        assert "elapsed_seconds" in result


# =============================================================================
# Unit Tests: Has Active Games
# =============================================================================


@pytest.mark.unit
class TestHasActiveGames:
    """Unit tests for has_active_games method."""

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_has_active_games_true(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test has_active_games returns True when games active."""
        mock_get_live.return_value = [{"game_id": 1}]
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        assert poller.has_active_games() is True

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_has_active_games_false(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test has_active_games returns False when no games."""
        mock_get_live.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        assert poller.has_active_games() is False

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_has_active_games_multiple_leagues(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test has_active_games checks all leagues."""
        # NFL has no games, NCAAF has games
        mock_get_live.side_effect = [[], [{"game_id": 1}]]
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        assert poller.has_active_games() is True
        assert mock_get_live.call_count == 2


# =============================================================================
# Unit Tests: Class Constants
# =============================================================================


@pytest.mark.unit
class TestClassConstants:
    """Unit tests for class constants."""

    def test_min_poll_interval(self) -> None:
        """Test MIN_POLL_INTERVAL constant."""
        assert ESPNGamePoller.MIN_POLL_INTERVAL == 5

    def test_default_poll_interval(self) -> None:
        """Test DEFAULT_POLL_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_POLL_INTERVAL == 15

    def test_default_idle_interval(self) -> None:
        """Test DEFAULT_IDLE_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_IDLE_INTERVAL == 60

    def test_default_leagues(self) -> None:
        """Test DEFAULT_LEAGUES constant."""
        assert ESPNGamePoller.DEFAULT_LEAGUES == ["nfl", "ncaaf"]

    def test_live_statuses(self) -> None:
        """Test LIVE_STATUSES constant."""
        assert "in" in ESPNGamePoller.LIVE_STATUSES
        assert "in_progress" in ESPNGamePoller.LIVE_STATUSES
        assert "halftime" in ESPNGamePoller.LIVE_STATUSES

    def test_completed_statuses(self) -> None:
        """Test COMPLETED_STATUSES constant."""
        assert "post" in ESPNGamePoller.COMPLETED_STATUSES
        assert "final" in ESPNGamePoller.COMPLETED_STATUSES


# =============================================================================
# Unit Tests: Adaptive Polling
# =============================================================================


@pytest.mark.unit
class TestAdaptivePollingInitialization:
    """Unit tests for adaptive polling initialization.

    Educational Note:
        Adaptive polling dynamically adjusts the poll interval based on
        whether games are actively in progress:
        - Active games: poll_interval (default 15s)
        - No active games: idle_interval (default 60s)

        This reduces API load and database writes during idle periods
        while maintaining responsiveness during live games.

    Reference:
        - Issue #234: ESPNGamePoller for Live Game State Collection
        - REQ-DATA-001: Game State Data Collection
    """

    def test_adaptive_polling_enabled_by_default(self, mock_espn_client: MagicMock) -> None:
        """Test adaptive polling is enabled by default."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller.adaptive_polling is True

    def test_adaptive_polling_can_be_disabled(self, mock_espn_client: MagicMock) -> None:
        """Test adaptive polling can be explicitly disabled."""
        poller = ESPNGamePoller(
            espn_client=mock_espn_client,
            adaptive_polling=False,
        )

        assert poller.adaptive_polling is False

    def test_current_interval_defaults_to_poll_interval(self, mock_espn_client: MagicMock) -> None:
        """Test _current_interval starts at poll_interval."""
        poller = ESPNGamePoller(
            poll_interval=30,
            espn_client=mock_espn_client,
        )

        assert poller._current_interval == 30

    def test_last_active_state_starts_as_none(self, mock_espn_client: MagicMock) -> None:
        """Test _last_active_state starts as None."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller._last_active_state is None


@pytest.mark.unit
class TestGetCurrentInterval:
    """Unit tests for get_current_interval method."""

    def test_get_current_interval_returns_current(self, mock_espn_client: MagicMock) -> None:
        """Test get_current_interval returns the current interval."""
        poller = ESPNGamePoller(
            poll_interval=20,
            espn_client=mock_espn_client,
        )

        assert poller.get_current_interval() == 20

    def test_get_current_interval_after_adjustment(self, mock_espn_client: MagicMock) -> None:
        """Test get_current_interval after manual adjustment."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
        )

        # Simulate interval adjustment
        poller._current_interval = 60

        assert poller.get_current_interval() == 60


@pytest.mark.unit
class TestAdjustPollInterval:
    """Unit tests for _adjust_poll_interval method.

    Educational Note:
        The _adjust_poll_interval method is called after each poll to
        determine if the interval should change based on active game status.

        Key behaviors:
        1. Only adjusts when active state changes (not on every poll)
        2. Uses poll_interval when games are active
        3. Uses idle_interval when no games are active
        4. Reschedules APScheduler job when interval changes
    """

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adjust_increases_interval_when_no_active_games(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test interval increases when no active games."""
        mock_get_live.return_value = []  # No active games
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
        )

        poller._adjust_poll_interval()

        assert poller._current_interval == 60
        assert poller._last_active_state is False

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adjust_decreases_interval_when_games_active(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test interval decreases when games are active."""
        mock_get_live.return_value = [{"game_id": 1}]  # Active game
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
        )
        # Simulate previously idle
        poller._current_interval = 60
        poller._last_active_state = False

        poller._adjust_poll_interval()

        assert poller._current_interval == 15
        assert poller._last_active_state is True

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adjust_no_change_when_same_state(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test interval doesn't change when state unchanged."""
        mock_get_live.return_value = []  # No active games
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
        )
        # Already in idle state
        poller._current_interval = 60
        poller._last_active_state = False

        poller._adjust_poll_interval()

        # Should stay at idle interval
        assert poller._current_interval == 60

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adjust_first_call_transitions_from_none(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test first adjustment transitions from None state."""
        mock_get_live.return_value = []  # No active games
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
        )
        assert poller._last_active_state is None

        poller._adjust_poll_interval()

        # Should transition and set state
        assert poller._last_active_state is False
        assert poller._current_interval == 60  # type: ignore[unreachable]

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_adjust_disabled_does_nothing(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test adjustment does nothing when adaptive_polling=False."""
        poller = ESPNGamePoller(
            poll_interval=15,
            idle_interval=60,
            espn_client=mock_espn_client,
            adaptive_polling=False,
        )
        original_interval = poller._current_interval

        poller._adjust_poll_interval()

        # Should not call get_live_games or change anything
        mock_get_live.assert_not_called()
        assert poller._current_interval == original_interval


@pytest.mark.unit
class TestPollWrapperAdaptive:
    """Unit tests for _poll_wrapper with adaptive polling."""

    @patch("precog.schedulers.espn_game_poller.get_live_games")
    def test_poll_wrapper_calls_adjust_when_enabled(
        self,
        mock_get_live: MagicMock,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test _poll_wrapper calls _adjust_poll_interval when enabled."""
        mock_get_live.return_value = []
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=True,
        )

        poller._poll_wrapper()

        # Should have called get_live_games for adjustment
        mock_get_live.assert_called()

    def test_poll_wrapper_skips_adjust_when_disabled(
        self,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test _poll_wrapper skips adjustment when disabled."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
            adaptive_polling=False,
        )

        # Mock _adjust_poll_interval to verify it's not called
        mock_adjust = MagicMock()
        object.__setattr__(poller, "_adjust_poll_interval", mock_adjust)

        poller._poll_wrapper()

        # Should not have called adjustment
        mock_adjust.assert_not_called()
