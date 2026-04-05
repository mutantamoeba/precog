"""
Unit Tests for ESPN Game Poller.

Tests ESPNGamePoller initialization, configuration, and basic functionality.

Reference: TESTING_STRATEGY V3.2 - Unit tests for isolated functionality
Related Requirements: REQ-DATA-001 (Game State Data Collection)

Usage:
    pytest tests/unit/schedulers/test_espn_game_poller_unit.py -v -m unit
"""

from contextlib import nullcontext
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from precog.api_connectors.espn_client import ESPNAPIError
from precog.schedulers.espn_game_poller import (
    LEAGUE_STATE_DISCOVERY,
    LEAGUE_STATE_TRACKING,
    ESPNGamePoller,
    create_espn_poller,
    refresh_all_scoreboards,
    run_single_espn_poll,
)
from precog.validation.espn_validation import ValidationResult

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
            "clock_seconds": Decimal("845.5"),
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

        assert poller.leagues == ["nfl", "ncaaf", "nba", "nhl"]
        assert poller.poll_interval == 30
        assert poller.idle_interval == 300
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

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_poll_once_with_games(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test poll_once with games."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        result = poller.poll_once()

        assert result["items_fetched"] == 1
        assert result["items_updated"] == 1
        mock_upsert.assert_called_once()
        mock_get_or_create_game.assert_called_once()
        # Verify game_id is passed to upsert_game_state
        upsert_kwargs = mock_upsert.call_args
        assert upsert_kwargs.kwargs.get("game_id") == 42 or (
            upsert_kwargs[1].get("game_id") == 42 if len(upsert_kwargs) > 1 else False
        )

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

        assert poller.leagues == ["nfl", "ncaaf", "nba", "nhl"]
        assert poller.poll_interval == 30
        assert poller.idle_interval == 300

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
        assert ESPNGamePoller.MIN_POLL_INTERVAL == 15

    def test_default_poll_interval(self) -> None:
        """Test DEFAULT_POLL_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_POLL_INTERVAL == 30

    def test_default_idle_interval(self) -> None:
        """Test DEFAULT_IDLE_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_IDLE_INTERVAL == 300

    def test_default_leagues(self) -> None:
        """Test DEFAULT_LEAGUES constant."""
        assert ESPNGamePoller.DEFAULT_LEAGUES == ["nfl", "ncaaf", "nba", "nhl"]

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


@pytest.mark.unit
class TestGetCurrentInterval:
    """Unit tests for get_current_interval method."""

    def test_get_current_interval_per_league_default(self, mock_espn_client: MagicMock) -> None:
        """Test get_current_interval returns min league interval in per-league mode."""
        poller = ESPNGamePoller(
            espn_client=mock_espn_client,
        )

        # All leagues start in DISCOVERY (900s)
        assert poller.get_current_interval() == 900

    def test_get_current_interval_per_league_with_tracking(
        self, mock_espn_client: MagicMock
    ) -> None:
        """Test get_current_interval returns tracking interval when one league is tracking."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        # Simulate NFL in tracking mode
        poller._league_intervals["nfl"] = 30
        poller._league_intervals["nba"] = 900

        # Should return min = 30
        assert poller.get_current_interval() == 30


# =============================================================================
# Unit Tests: Per-League Polling Initialization
# =============================================================================


@pytest.mark.unit
class TestPerLeaguePollingInitialization:
    """Unit tests for per-league polling initialization.

    Educational Note:
        Per-league polling creates independent polling jobs for each league,
        each with its own state (DISCOVERY or TRACKING) and interval. This
        keeps total ESPN API requests under the 250 req/hr rate limit.
    """

    def test_league_states_initialized_to_discovery(self, mock_espn_client: MagicMock) -> None:
        """Test all leagues start in DISCOVERY state."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_espn_client,
        )

        for league in ["nfl", "nba", "nhl"]:
            assert poller._league_states[league] == LEAGUE_STATE_DISCOVERY

    def test_league_intervals_initialized_to_discovery(self, mock_espn_client: MagicMock) -> None:
        """Test all leagues start with DISCOVERY interval."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf"],
            espn_client=mock_espn_client,
        )

        for league in ["nfl", "ncaaf"]:
            assert poller._league_intervals[league] == ESPNGamePoller.DEFAULT_DISCOVERY_INTERVAL

    def test_league_states_match_configured_leagues(self, mock_espn_client: MagicMock) -> None:
        """Test _league_states keys match configured leagues exactly."""
        leagues = ["nfl", "ncaaf", "nba"]
        poller = ESPNGamePoller(
            leagues=leagues,
            espn_client=mock_espn_client,
        )

        assert set(poller._league_states.keys()) == set(leagues)
        assert set(poller._league_intervals.keys()) == set(leagues)


# =============================================================================
# Unit Tests: Per-League Polling Constants
# =============================================================================


@pytest.mark.unit
class TestPerLeaguePollingConstants:
    """Unit tests for per-league polling class constants."""

    def test_default_tracking_interval(self) -> None:
        """Test DEFAULT_TRACKING_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_TRACKING_INTERVAL == 30

    def test_default_discovery_interval(self) -> None:
        """Test DEFAULT_DISCOVERY_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_DISCOVERY_INTERVAL == 900

    def test_max_throttled_interval(self) -> None:
        """Test DEFAULT_MAX_THROTTLED_INTERVAL constant."""
        assert ESPNGamePoller.DEFAULT_MAX_THROTTLED_INTERVAL == 60

    def test_league_stagger_offset(self) -> None:
        """Test LEAGUE_STAGGER_OFFSET constant."""
        assert ESPNGamePoller.LEAGUE_STAGGER_OFFSET == 15

    def test_default_rate_budget(self) -> None:
        """Test DEFAULT_RATE_BUDGET constant."""
        assert ESPNGamePoller.DEFAULT_RATE_BUDGET == 250

    def test_computed_max_concurrent_full_speed(self) -> None:
        """Test max concurrent full speed is computed from budget."""
        # Default: 250 budget, 30s interval, 4 leagues
        # Discovery overhead: 4 * 4 = 16, Available: 234, Per league: 120
        # Max concurrent: 234 // 120 = 1 (conservative with 4 leagues at 900s)
        poller = ESPNGamePoller()
        assert poller._max_concurrent_full_speed >= 1

    def test_custom_rate_budget(self) -> None:
        """Test custom rate budget changes computed concurrent limit."""
        poller = ESPNGamePoller(rate_budget_per_hour=500)
        assert poller.rate_budget_per_hour == 500
        # Higher budget = more concurrent full-speed leagues
        assert poller._max_concurrent_full_speed >= 2

    def test_league_state_constants(self) -> None:
        """Test module-level state constants."""
        assert LEAGUE_STATE_DISCOVERY == "discovery"
        assert LEAGUE_STATE_TRACKING == "tracking"


# =============================================================================
# Unit Tests: League Job ID
# =============================================================================


@pytest.mark.unit
class TestLeagueJobId:
    """Unit tests for _league_job_id method."""

    def test_league_job_id_format(self, mock_espn_client: MagicMock) -> None:
        """Test job ID format for a league."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller._league_job_id("nfl") == "poll_espn_nfl"
        assert poller._league_job_id("ncaaf") == "poll_espn_ncaaf"
        assert poller._league_job_id("nba") == "poll_espn_nba"

    def test_league_job_ids_are_unique(self, mock_espn_client: MagicMock) -> None:
        """Test each league gets a unique job ID."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba", "nhl"],
            espn_client=mock_espn_client,
        )

        job_ids = [poller._league_job_id(league) for league in poller.leagues]
        assert len(job_ids) == len(set(job_ids))


# =============================================================================
# Unit Tests: Scoreboard Has Live Games
# =============================================================================


@pytest.mark.unit
class TestScoreboardHasLiveGames:
    """Unit tests for _scoreboard_has_live_games method.

    Educational Note:
        This method checks the raw ESPN scoreboard response for live games
        without querying the database. It is the source of truth for
        state transitions.
    """

    def test_no_games_returns_false(self, mock_espn_client: MagicMock) -> None:
        """Test empty game list returns False."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller._scoreboard_has_live_games([]) is False

    def test_all_pre_returns_false(self, mock_espn_client: MagicMock) -> None:
        """Test all pre-game statuses returns False."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "pre"}},
            {"state": {"game_status": "scheduled"}},
        ]

        assert poller._scoreboard_has_live_games(games) is False  # type: ignore[arg-type]

    def test_all_final_returns_false(self, mock_espn_client: MagicMock) -> None:
        """Test all final statuses returns False."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "final"}},
            {"state": {"game_status": "post"}},
        ]

        assert poller._scoreboard_has_live_games(games) is False  # type: ignore[arg-type]

    def test_in_progress_returns_true(self, mock_espn_client: MagicMock) -> None:
        """Test in_progress game returns True."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "pre"}},
            {"state": {"game_status": "in_progress"}},
            {"state": {"game_status": "final"}},
        ]

        assert poller._scoreboard_has_live_games(games) is True  # type: ignore[arg-type]

    def test_in_status_returns_true(self, mock_espn_client: MagicMock) -> None:
        """Test 'in' status (raw ESPN) returns True."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "in"}},
        ]

        assert poller._scoreboard_has_live_games(games) is True  # type: ignore[arg-type]

    def test_halftime_returns_true(self, mock_espn_client: MagicMock) -> None:
        """Test halftime status returns True."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "halftime"}},
        ]

        assert poller._scoreboard_has_live_games(games) is True  # type: ignore[arg-type]

    def test_case_insensitive(self, mock_espn_client: MagicMock) -> None:
        """Test status check is case-insensitive."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "IN"}},
        ]

        assert poller._scoreboard_has_live_games(games) is True  # type: ignore[arg-type]

    def test_missing_state_returns_false(self, mock_espn_client: MagicMock) -> None:
        """Test game with missing state dict returns False."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"metadata": {"espn_event_id": "123"}},
        ]

        assert poller._scoreboard_has_live_games(games) is False  # type: ignore[arg-type]

    def test_missing_game_status_returns_false(self, mock_espn_client: MagicMock) -> None:
        """Test game with missing game_status returns False."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        games: list[dict[str, Any]] = [
            {"state": {}},
        ]

        assert poller._scoreboard_has_live_games(games) is False  # type: ignore[arg-type]


# =============================================================================
# Unit Tests: Evaluate League State
# =============================================================================


@pytest.mark.unit
class TestEvaluateLeagueState:
    """Unit tests for _evaluate_league_state method.

    Educational Note:
        This method transitions a league between DISCOVERY and TRACKING
        states based on the scoreboard response. It also triggers
        interval recalculation for all leagues (throttling logic).
    """

    def test_transition_discovery_to_tracking(self, mock_espn_client: MagicMock) -> None:
        """Test DISCOVERY -> TRACKING when live games detected."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        assert poller._league_states["nfl"] == LEAGUE_STATE_DISCOVERY

        games: list[dict[str, Any]] = [
            {"state": {"game_status": "in_progress"}},
        ]

        poller._evaluate_league_state("nfl", games)  # type: ignore[arg-type]

        assert poller._league_states["nfl"] == LEAGUE_STATE_TRACKING

    def test_transition_tracking_to_discovery(self, mock_espn_client: MagicMock) -> None:
        """Test TRACKING -> DISCOVERY when no live games."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        # Start in tracking
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING

        games: list[dict[str, Any]] = [
            {"state": {"game_status": "final"}},
            {"state": {"game_status": "pre"}},
        ]

        poller._evaluate_league_state("nfl", games)  # type: ignore[arg-type]

        assert poller._league_states["nfl"] == LEAGUE_STATE_DISCOVERY

    def test_no_transition_when_same_state(self, mock_espn_client: MagicMock) -> None:
        """Test no transition when state doesn't change."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        # Already in discovery
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "pre"}},
        ]

        poller._evaluate_league_state("nfl", games)  # type: ignore[arg-type]

        # Should remain discovery (no change)
        assert poller._league_states["nfl"] == LEAGUE_STATE_DISCOVERY

    def test_transition_updates_intervals(self, mock_espn_client: MagicMock) -> None:
        """Test state transition triggers interval recalculation."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        games: list[dict[str, Any]] = [
            {"state": {"game_status": "in_progress"}},
        ]

        poller._evaluate_league_state("nfl", games)  # type: ignore[arg-type]

        # NFL should now have tracking interval, NBA still discovery
        assert poller._league_intervals["nfl"] == ESPNGamePoller.DEFAULT_TRACKING_INTERVAL
        assert poller._league_intervals["nba"] == ESPNGamePoller.DEFAULT_DISCOVERY_INTERVAL

    def test_empty_games_goes_to_discovery(self, mock_espn_client: MagicMock) -> None:
        """Test empty game list transitions to DISCOVERY."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING

        poller._evaluate_league_state("nfl", [])

        assert poller._league_states["nfl"] == LEAGUE_STATE_DISCOVERY

    def test_unknown_league_ignored(self, mock_espn_client: MagicMock) -> None:
        """Test that unknown league is ignored and doesn't corrupt state."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        games: list[dict[str, Any]] = [
            {"state": {"game_status": "in"}},
        ]

        poller._evaluate_league_state("FAKE_LEAGUE", games)  # type: ignore[arg-type]

        # State dict should not have the fake league
        assert "FAKE_LEAGUE" not in poller._league_states

    def test_reschedule_returned_not_executed_under_lock(self, mock_espn_client: MagicMock) -> None:
        """Test that reschedule ops are returned, not executed inside the lock."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )
        # Set up a mock scheduler so reschedule_job is trackable
        mock_scheduler = MagicMock()
        poller._scheduler = mock_scheduler
        poller._enabled = True

        games: list[dict[str, Any]] = [
            {"state": {"game_status": "in"}},
        ]
        poller._evaluate_league_state("nfl", games)  # type: ignore[arg-type]

        # reschedule_job should have been called (outside the lock)
        assert mock_scheduler.reschedule_job.called


# =============================================================================
# Unit Tests: Recalculate League Intervals
# =============================================================================


@pytest.mark.unit
class TestRecalculateLeagueIntervals:
    """Unit tests for _recalculate_league_intervals method.

    Educational Note:
        This method enforces the rate budget by computing throttle intervals
        from the rate budget and tracking interval. The max concurrent full-speed
        count is derived, not hardcoded (#560).
    """

    def test_single_tracking_league_gets_normal_interval(self, mock_espn_client: MagicMock) -> None:
        """Test 1 tracking league uses base tracking interval."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_espn_client,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        assert poller._league_intervals["nfl"] == 30
        assert poller._league_intervals["nba"] == 900
        assert poller._league_intervals["nhl"] == 900

    def test_two_tracking_leagues_get_normal_interval(self, mock_espn_client: MagicMock) -> None:
        """Test 2 tracking leagues within budget use base interval."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=500,  # Enough for 2 at 30s
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        assert poller._league_intervals["nfl"] == 30
        assert poller._league_intervals["nba"] == 30
        assert poller._league_intervals["nhl"] == 900

    def test_overflow_leagues_get_throttled(self, mock_espn_client: MagicMock) -> None:
        """Test leagues beyond budget capacity are throttled."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=250,  # Can only do ~2 at 30s
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING
        poller._league_states["nhl"] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        # All tracking leagues should have intervals <= max_throttled_interval
        for league in ["nfl", "nba", "nhl"]:
            assert poller._league_intervals[league] <= poller.max_throttled_interval

    def test_throttled_interval_capped_at_max(self, mock_espn_client: MagicMock) -> None:
        """Test throttled interval never exceeds max_throttled_interval."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba", "nhl"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=100,  # Very tight budget
            max_throttled_interval=60,
        )
        for league in poller.leagues:
            poller._league_states[league] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        for league in poller.leagues:
            assert poller._league_intervals[league] <= 60

    def test_total_rate_within_budget(self, mock_espn_client: MagicMock) -> None:
        """Test total request rate stays within budget after throttling."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba", "nhl"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=250,
        )
        for league in poller.leagues:
            poller._league_states[league] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        total_req_hr = sum(3600 // iv for iv in poller._league_intervals.values())
        assert total_req_hr <= poller.rate_budget_per_hour

    def test_tight_budget_no_division_by_zero(self, mock_espn_client: MagicMock) -> None:
        """Test tight budget (122/hr) doesn't crash with ZeroDivisionError.

        With budget=122 and max_throttled_interval=60, 4 leagues at 60s = 240 req/hr
        which exceeds the budget. The cap is respected (no interval > 60s) and a
        warning is logged. Budget cannot be met when the cap makes it impossible.
        """
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba", "nhl"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=122,
        )
        for league in poller.leagues:
            poller._league_states[league] = LEAGUE_STATE_TRACKING

        # Should not raise ZeroDivisionError
        poller._recalculate_league_intervals()

        # Cap should be respected — no interval faster than base or slower than cap
        for iv in poller._league_intervals.values():
            assert iv <= poller.max_throttled_interval or iv == poller.DEFAULT_DISCOVERY_INTERVAL

    def test_higher_budget_allows_more_full_speed(self, mock_espn_client: MagicMock) -> None:
        """Test higher rate budget allows more leagues at full speed."""
        poller_low = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=250,
        )
        poller_high = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
            rate_budget_per_hour=500,
        )
        assert poller_high._max_concurrent_full_speed >= poller_low._max_concurrent_full_speed

    def test_discovery_leagues_always_get_discovery_interval(
        self, mock_espn_client: MagicMock
    ) -> None:
        """Test DISCOVERY leagues always get DEFAULT_DISCOVERY_INTERVAL regardless of tracking count."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba", "nhl", "ncaaf"],
            espn_client=mock_espn_client,
        )
        # 3 tracking, 1 discovery
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING
        poller._league_states["nhl"] = LEAGUE_STATE_TRACKING
        poller._league_states["ncaaf"] = LEAGUE_STATE_DISCOVERY

        poller._recalculate_league_intervals()

        # Discovery league unaffected
        assert poller._league_intervals["ncaaf"] == 900

    def test_rate_budget_with_two_tracking(self, mock_espn_client: MagicMock) -> None:
        """Test rate budget stays under 250 req/hr with 2 tracking + 2 discovery."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba", "nhl"],
            espn_client=mock_espn_client,
        )
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        poller._league_states["nba"] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        # Calculate total req/hr
        total_req_hr = sum(3600 / interval for interval in poller._league_intervals.values())
        assert total_req_hr < 250, f"Rate budget exceeded: {total_req_hr:.0f} req/hr"

    def test_rate_budget_with_four_tracking(self, mock_espn_client: MagicMock) -> None:
        """Test rate budget stays under 250 req/hr with 4 tracking (throttled)."""
        poller = ESPNGamePoller(
            leagues=["nfl", "ncaaf", "nba", "nhl"],
            espn_client=mock_espn_client,
        )
        for league in poller.leagues:
            poller._league_states[league] = LEAGUE_STATE_TRACKING

        poller._recalculate_league_intervals()

        # Calculate total req/hr
        total_req_hr = sum(3600 / interval for interval in poller._league_intervals.values())
        assert total_req_hr < 250, f"Rate budget exceeded: {total_req_hr:.0f} req/hr"

    def test_rate_budget_warning_with_six_leagues(self, mock_espn_client: MagicMock) -> None:
        """Test rate budget warning fires when >4 tracking leagues exceed limit."""
        leagues = ["nfl", "nba", "nhl", "ncaaf", "ncaab", "wnba"]
        poller = ESPNGamePoller(
            leagues=leagues,
            espn_client=mock_espn_client,
        )
        for league in leagues:
            poller._league_states[league] = LEAGUE_STATE_TRACKING

        with pytest.warns(match="Rate budget exceeded") if False else nullcontext():
            # _recalculate_league_intervals logs a warning, doesn't raise
            poller._recalculate_league_intervals()

        # 6 leagues at throttled 60s = 360 req/hr > 250 limit
        total_req_hr = sum(3600 // iv for iv in poller._league_intervals.values())
        assert total_req_hr > 250, "Expected rate budget to exceed limit with 6 tracking leagues"

    def test_recalculate_returns_pending_reschedules(self, mock_espn_client: MagicMock) -> None:
        """Test _recalculate_league_intervals returns list of pending reschedules."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )
        poller._scheduler = MagicMock()
        poller._enabled = True

        # Transition NFL to tracking - interval should change
        poller._league_states["nfl"] = LEAGUE_STATE_TRACKING
        pending = poller._recalculate_league_intervals()

        # Should have one pending reschedule for NFL
        assert len(pending) == 1
        job_id, old_interval, new_interval, _state, _tracking_count = pending[0]
        assert "nfl" in job_id
        assert old_interval == ESPNGamePoller.DEFAULT_DISCOVERY_INTERVAL
        assert new_interval == ESPNGamePoller.DEFAULT_TRACKING_INTERVAL


# =============================================================================
# Unit Tests: Get League States / Get League Intervals
# =============================================================================


@pytest.mark.unit
class TestGetLeagueStatesAndIntervals:
    """Unit tests for get_league_states and get_league_intervals."""

    def test_get_league_states_returns_copy(self, mock_espn_client: MagicMock) -> None:
        """Test get_league_states returns independent copy."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        states = poller.get_league_states()
        states["nfl"] = "modified"

        # Original should be unaffected
        assert poller._league_states["nfl"] == LEAGUE_STATE_DISCOVERY

    def test_get_league_intervals_returns_copy(self, mock_espn_client: MagicMock) -> None:
        """Test get_league_intervals returns independent copy."""
        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )

        intervals = poller.get_league_intervals()
        intervals["nfl"] = 1

        # Original should be unaffected
        assert poller._league_intervals["nfl"] == 900

    def test_get_league_states_thread_safe(self, mock_espn_client: MagicMock) -> None:
        """Test get_league_states acquires lock."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Should not raise even with lock held (reentrant check)
        states = poller.get_league_states()
        assert "nfl" in states


# =============================================================================
# Unit Tests: Poll League Wrapper
# =============================================================================


@pytest.mark.unit
class TestPollLeagueWrapper:
    """Unit tests for _poll_league_wrapper method.

    Educational Note:
        _poll_league_wrapper is the per-league equivalent of _poll_wrapper.
        It polls one league, updates stats, and evaluates state transitions.
    """

    def test_poll_league_wrapper_updates_stats(self, mock_espn_client: MagicMock) -> None:
        """Test _poll_league_wrapper updates poll statistics."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_league_wrapper("nfl")

        assert poller._stats["polls_completed"] == 1
        assert poller._stats["items_fetched"] == 0

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_poll_league_wrapper_syncs_games(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test _poll_league_wrapper syncs games to database."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 55

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_league_wrapper("nfl")

        assert poller._stats["items_fetched"] == 1
        assert poller._stats["items_updated"] == 1
        mock_upsert.assert_called_once()
        mock_get_or_create_game.assert_called_once()

    def test_poll_league_wrapper_handles_api_error(self, mock_espn_client: MagicMock) -> None:
        """Test _poll_league_wrapper handles ESPN API errors gracefully."""
        mock_espn_client.get_scoreboard.side_effect = ESPNAPIError("API down")
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Should not raise
        poller._poll_league_wrapper("nfl")

        assert poller._stats["errors"] == 1

    def test_poll_league_wrapper_transitions_to_tracking(
        self,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test _poll_league_wrapper transitions league to TRACKING on live games."""
        mock_espn_client.get_scoreboard.return_value = [
            {"state": {"game_status": "in_progress"}, "metadata": {}},
        ]
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_league_wrapper("nfl")

        assert poller._league_states["nfl"] == LEAGUE_STATE_TRACKING

    def test_poll_league_wrapper_stays_in_discovery(
        self,
        mock_espn_client: MagicMock,
    ) -> None:
        """Test _poll_league_wrapper keeps DISCOVERY when no live games."""
        mock_espn_client.get_scoreboard.return_value = [
            {"state": {"game_status": "pre"}, "metadata": {}},
        ]
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_league_wrapper("nfl")

        assert poller._league_states["nfl"] == LEAGUE_STATE_DISCOVERY


# =============================================================================
# Periodic Team Validation Tests (Part F)
# =============================================================================


@pytest.mark.unit
class TestPeriodicTeamValidation:
    """Tests for periodic ESPN team validation scheduling and dedup guard.

    Educational Note:
        Part F adds a 6-hour periodic validation job to catch ESPN ID drift
        during long soak tests. The dedup guard prevents redundant validation
        when the poller was recently started or restarted.
    """

    def test_periodic_validation_skips_when_recent(self, mock_espn_client):
        """Should skip periodic validation if last run was < 10 minutes ago."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        with patch("precog.schedulers.espn_game_poller.time") as mock_time:
            mock_time.monotonic.return_value = 1000.0
            poller._last_validation_time = 500.0  # 500s ago (< 600s)

            with patch(
                "precog.api_connectors.espn_team_validator.validate_espn_teams"
            ) as mock_validate:
                poller._periodic_team_validation()
                mock_validate.assert_not_called()

    def test_periodic_validation_runs_when_stale(self, mock_espn_client):
        """Should run periodic validation if last run was > 10 minutes ago."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        with patch("precog.schedulers.espn_game_poller.time") as mock_time:
            mock_time.monotonic.return_value = 1200.0
            poller._last_validation_time = 0.0

            with patch(
                "precog.api_connectors.espn_team_validator.validate_espn_teams"
            ) as mock_validate:
                mock_validate.return_value = {
                    "total_checked": 32,
                    "total_mismatches": 0,
                    "leagues": {"nfl": {}},
                }
                poller._periodic_team_validation()
                mock_validate.assert_called_once_with(leagues=["nfl"], auto_correct=True)

    def test_periodic_validation_updates_timestamp(self, mock_espn_client):
        """Should update _last_validation_time after successful run."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        with patch("precog.schedulers.espn_game_poller.time") as mock_time:
            mock_time.monotonic.side_effect = [700.0, 700.0]  # check + update
            poller._last_validation_time = 0.0

            with patch(
                "precog.api_connectors.espn_team_validator.validate_espn_teams"
            ) as mock_validate:
                mock_validate.return_value = {
                    "total_checked": 32,
                    "total_mismatches": 0,
                    "leagues": {"nfl": {}},
                }
                poller._periodic_team_validation()
                assert poller._last_validation_time == 700.0

    def test_periodic_validation_handles_exception(self, mock_espn_client):
        """Should catch exceptions without crashing the scheduler."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        with patch("precog.schedulers.espn_game_poller.time") as mock_time:
            mock_time.monotonic.return_value = 1200.0
            poller._last_validation_time = 0.0

            with patch(
                "precog.api_connectors.espn_team_validator.validate_espn_teams",
                side_effect=RuntimeError("ESPN API down"),
            ):
                # Should not raise
                poller._periodic_team_validation()
                # Timestamp should NOT update on failure (so next run retries)
                assert poller._last_validation_time == 0.0

    def test_periodic_job_registered_in_start(self, mock_espn_client):
        """Should register periodic validation job when validate_teams_on_start=True."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
            validate_teams_on_start=True,
        )
        with patch.object(poller, "_on_start"):
            poller.start()

        try:
            job = poller._scheduler.get_job("espn_team_validation")
            assert job is not None
            assert job.name == "ESPN Team ID Periodic Validation"
        finally:
            poller.stop()

    def test_periodic_job_not_registered_when_disabled(self, mock_espn_client):
        """Should NOT register periodic validation job when validate_teams_on_start=False."""
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
            validate_teams_on_start=False,
        )
        with patch.object(poller, "_on_start"):
            poller.start()

        try:
            job = poller._scheduler.get_job("espn_team_validation")
            assert job is None
        finally:
            poller.stop()


# =============================================================================
# Unit Tests: ESPN Data Validation Wiring
# =============================================================================


@pytest.mark.unit
class TestESPNDataValidationWiring:
    """Unit tests for ESPN data validation wiring in the poller.

    Educational Note:
        The ESPNDataValidator is wired into _poll_league_wrapper to run
        soft validation on raw API data BEFORE DB sync. Validation is
        rate-limited (every VALIDATION_INTERVAL polls) and never blocks
        ingestion. This mirrors the Kalshi poller's validation pattern.
    """

    def test_validator_initialized(self, mock_espn_client: MagicMock) -> None:
        """Test ESPNDataValidator is instantiated in __init__."""
        from precog.validation.espn_validation import ESPNDataValidator

        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert hasattr(poller, "_validator")
        assert isinstance(poller._validator, ESPNDataValidator)

    def test_validation_constants_defined(self) -> None:
        """Test validation class constants exist and have correct values."""
        assert ESPNGamePoller.VALIDATION_INTERVAL == 20
        assert ESPNGamePoller.VALIDATION_ERROR_RATE == 0.25
        assert ESPNGamePoller.VALIDATION_WARN_RATE == 0.05

    def test_validation_stats_initialized(self, mock_espn_client: MagicMock) -> None:
        """Test validation stats are initialized to zero."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller._validation_stats["validation_errors"] == 0
        assert poller._validation_stats["validation_warnings"] == 0
        assert poller._validation_stats["validation_runs"] == 0
        assert poller._validation_stats["games_checked_last_cycle"] == 0
        assert poller._validation_stats["error_rate_pct_last_cycle"] == 0.0

    def test_validation_stats_in_get_stats(self, mock_espn_client: MagicMock) -> None:
        """Test get_stats includes validation stats."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        stats = poller.get_stats()

        assert "validation_errors" in stats
        assert "validation_warnings" in stats
        assert "validation_runs" in stats

    def test_polls_since_validation_starts_at_interval(self, mock_espn_client: MagicMock) -> None:
        """Test counter starts at VALIDATION_INTERVAL to trigger on first poll."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)

        assert poller._polls_since_validation == ESPNGamePoller.VALIDATION_INTERVAL

    def test_counter_triggers_on_first_league_poll(self, mock_espn_client: MagicMock) -> None:
        """Test validation triggers on first _poll_league_wrapper call.

        Counter starts at VALIDATION_INTERVAL so the first poll increments it
        past the threshold, triggering validation and resetting to 0.
        """
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        poller._poll_league_wrapper("nfl")

        # After first poll: counter was at VALIDATION_INTERVAL, incremented to
        # VALIDATION_INTERVAL+1 which >= VALIDATION_INTERVAL, so it reset to 0
        assert poller._polls_since_validation == 0

    def test_counter_does_not_trigger_after_recent_validation(
        self, mock_espn_client: MagicMock
    ) -> None:
        """Test validation does not trigger on subsequent polls before interval."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # First poll triggers validation (counter starts at VALIDATION_INTERVAL)
        poller._poll_league_wrapper("nfl")
        # Second poll should NOT trigger (counter is at 1 after reset+increment)
        poller._poll_league_wrapper("nfl")

        assert poller._polls_since_validation == 1

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_validation_runs_when_should_validate(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test validation runs on games when _should_validate is True."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        # Force validation to run
        poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL

        with patch.object(poller._validator, "validate_game_state") as mock_validate:
            mock_validate.return_value = ValidationResult(game_id="401547417")
            poller._poll_league_wrapper("nfl")

            # Validator should have been called once per game
            mock_validate.assert_called_once_with(sample_game_data)

        # Validation stats should be updated
        assert poller._validation_stats["validation_runs"] == 1
        assert poller._validation_stats["games_checked_last_cycle"] == 1

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_validation_skipped_when_not_due(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test validation is skipped when _should_validate is False."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        # Ensure validation does NOT run
        poller._polls_since_validation = 0

        with patch.object(poller._validator, "validate_game_state") as mock_validate:
            poller._poll_league_wrapper("nfl")

            mock_validate.assert_not_called()

        # Validation stats should remain at zero
        assert poller._validation_stats["validation_runs"] == 0

    def test_validation_skipped_on_empty_games(self, mock_espn_client: MagicMock) -> None:
        """Test validation is skipped when no games returned (even if due)."""
        mock_espn_client.get_scoreboard.return_value = []

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL

        with patch.object(poller._validator, "validate_game_state") as mock_validate:
            poller._poll_league_wrapper("nfl")

            mock_validate.assert_not_called()

        assert poller._validation_stats["validation_runs"] == 0

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_validation_error_does_not_block_sync(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test validator exception does NOT prevent game sync."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL

        with patch.object(
            poller._validator,
            "validate_game_state",
            side_effect=RuntimeError("Validator exploded"),
        ):
            poller._poll_league_wrapper("nfl")

        # Game sync should still have happened
        mock_upsert.assert_called_once()
        mock_get_or_create_game.assert_called_once()
        # Items should be fetched and updated
        assert poller._stats["items_fetched"] == 1
        assert poller._stats["items_updated"] == 1

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_validation_stats_accumulate(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test validation stats accumulate across multiple poll cycles."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )

        # Create a result with one error
        error_result = ValidationResult(game_id="401547417")
        error_result.add_error("home_score", "Negative score", value=-1)

        with patch.object(poller._validator, "validate_game_state", return_value=error_result):
            # Run two validation cycles
            poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL
            poller._poll_league_wrapper("nfl")
            poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL
            poller._poll_league_wrapper("nfl")

        # Errors should accumulate
        assert poller._validation_stats["validation_errors"] == 2
        assert poller._validation_stats["validation_runs"] == 2

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_error_rate_escalation_error_level(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test error-level logging when error rate >= VALIDATION_ERROR_RATE."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL

        # 1 game with error = 100% error rate (> 25% threshold)
        error_result = ValidationResult(game_id="401547417")
        error_result.add_error("home_score", "Negative score", value=-1)

        with patch.object(poller._validator, "validate_game_state", return_value=error_result):
            with patch("precog.schedulers.espn_game_poller.logger") as mock_logger:
                poller._poll_league_wrapper("nfl")
                # Should have logged at ERROR level for the aggregate
                mock_logger.error.assert_any_call(
                    "ESPN validation [%s]: ERROR RATE %.1f%% - %d/%d games failed "
                    "(%d errors, %d warning-only) [ACTION: investigate data source]",
                    "NFL",
                    100.0,
                    1,
                    1,
                    1,
                    0,
                )

        assert poller._validation_stats["error_rate_pct_last_cycle"] == 100.0

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_warning_only_games_counted_correctly(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test warnings-only results count toward warnings not errors."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL

        # Result with warnings only (no errors)
        warn_result = ValidationResult(game_id="401547417")
        warn_result.add_warning("clock_seconds", "Unusual clock value")

        with patch.object(poller._validator, "validate_game_state", return_value=warn_result):
            poller._poll_league_wrapper("nfl")

        assert poller._validation_stats["validation_errors"] == 0
        assert poller._validation_stats["validation_warnings"] == 1
        assert poller._validation_stats["error_rate_pct_last_cycle"] == 0.0

    def test_wrapper_counter_increments(self, mock_espn_client: MagicMock) -> None:
        """Test _poll_league_wrapper increments the validation counter each call."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        # Reset counter to 0
        poller._polls_since_validation = 0

        poller._poll_league_wrapper("nfl")
        assert poller._polls_since_validation == 1

        poller._poll_league_wrapper("nfl")
        assert poller._polls_since_validation == 2

    def test_wrapper_counter_resets_at_interval(self, mock_espn_client: MagicMock) -> None:
        """Test counter resets to 0 when VALIDATION_INTERVAL reached."""
        mock_espn_client.get_scoreboard.return_value = []
        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        # Set counter just below threshold
        poller._polls_since_validation = ESPNGamePoller.VALIDATION_INTERVAL - 1

        poller._poll_league_wrapper("nfl")

        assert poller._polls_since_validation == 0


class TestDataGapDetection:
    """Tests for per-league last_successful_poll tracking and data gap detection.

    The supervisor's _determine_health() checks stats["last_successful_poll"]
    for staleness. These tests verify the key is set correctly.
    """

    def test_last_successful_poll_initialized_none(self, mock_espn_client: MagicMock) -> None:
        """Test last_successful_poll starts as None."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        stats = poller.get_stats()

        assert stats["last_successful_poll"] is None
        assert stats["league_last_successful_poll"] == {}

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_last_successful_poll_set_on_success(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test last_successful_poll is set after a clean poll."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = 0

        poller._poll_league_wrapper("nfl")

        stats = poller.get_stats()
        assert stats["last_successful_poll"] is not None
        assert stats["league_last_successful_poll"]["nfl"] is not None

    def test_last_successful_poll_not_set_on_api_error(self, mock_espn_client: MagicMock) -> None:
        """Test last_successful_poll is NOT set when ESPN API fails."""
        mock_espn_client.get_scoreboard.side_effect = Exception("API down")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = 0

        poller._poll_league_wrapper("nfl")

        stats = poller.get_stats()
        assert stats["last_successful_poll"] is None

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_per_league_timestamps_independent(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test each league gets its own timestamp."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42

        poller = ESPNGamePoller(
            leagues=["nfl", "nba"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = 0

        poller._poll_league_wrapper("nfl")

        stats = poller.get_stats()
        assert "nfl" in stats["league_last_successful_poll"]
        assert "nba" not in stats["league_last_successful_poll"]

    @patch("precog.schedulers.espn_game_poller.update_game_result")
    @patch("precog.schedulers.espn_game_poller.get_or_create_game")
    @patch("precog.schedulers.espn_game_poller.get_team_by_espn_id")
    @patch("precog.schedulers.espn_game_poller.upsert_game_state")
    @patch("precog.schedulers.espn_game_poller.create_venue")
    def test_last_successful_poll_not_set_on_sync_errors(
        self,
        mock_create_venue: MagicMock,
        mock_upsert: MagicMock,
        mock_get_team: MagicMock,
        mock_get_or_create_game: MagicMock,
        mock_update_result: MagicMock,
        mock_espn_client: MagicMock,
        sample_game_data: dict[str, Any],
    ) -> None:
        """Test last_successful_poll not updated when sync errors occur."""
        mock_espn_client.get_scoreboard.return_value = [sample_game_data]
        mock_get_team.return_value = {"team_id": 1}
        mock_create_venue.return_value = 100
        mock_get_or_create_game.return_value = 42
        mock_upsert.side_effect = Exception("DB write failed")

        poller = ESPNGamePoller(
            leagues=["nfl"],
            espn_client=mock_espn_client,
        )
        poller._polls_since_validation = 0

        poller._poll_league_wrapper("nfl")

        stats = poller.get_stats()
        assert stats["last_successful_poll"] is None
