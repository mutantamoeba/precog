"""
Unit tests for ESPN Game State Polling (ESPNGamePoller).

Tests cover:
- Initialization and parameter validation
- Job persistence configuration
- Start/stop lifecycle management
- Stats tracking
- refresh_scoreboards() method
- Poll logic with mocked ESPN responses
- Factory functions and convenience methods
- Error handling and recovery
- Backward compatibility aliases (MarketUpdater)

All tests use mocked responses - NO actual API calls or database operations.

Reference: Phase 2 Live Data Integration
Related: src/precog/schedulers/espn_game_poller.py
Coverage Target: >=85%
"""

from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import pytest

# Import from new module (espn_game_poller)
# Also import backward compatibility aliases to test them
from precog.schedulers.espn_game_poller import (
    ESPNGamePoller,
    MarketUpdater,
    create_espn_poller,
    create_market_updater,
    refresh_all_scoreboards,
    run_single_espn_poll,
    run_single_poll,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_espn_client():
    """Create a mock ESPNClient for testing."""
    mock_client = Mock()
    mock_client.get_scoreboard.return_value = []
    mock_client.get_game.return_value = None
    return mock_client


@pytest.fixture
def mock_game_data() -> dict[str, Any]:
    """Sample ESPN game data (ESPNGameFull TypedDict structure)."""
    return {
        "espn_event_id": "401547389",
        "league": "nfl",
        "game_date": "2025-12-07T20:00:00Z",
        "status": "in_progress",
        "home_team": {
            "espn_team_id": "12",
            "team_name": "Kansas City Chiefs",
            "team_code": "KC",
            "score": 21,
        },
        "away_team": {
            "espn_team_id": "33",
            "team_name": "Denver Broncos",
            "team_code": "DEN",
            "score": 14,
        },
        "period": 3,
        "clock_seconds": Decimal("450"),
        "clock_display": "7:30",
        "situation": {
            "down": 2,
            "distance": 8,
            "possession": "KC",
            "yard_line": 35,
        },
        "venue": {
            "espn_venue_id": "3622",
            "venue_name": "Arrowhead Stadium",
            "city": "Kansas City",
            "state": "MO",
        },
    }


@pytest.fixture
def updater_with_mock_client(mock_espn_client):
    """Create ESPNGamePoller with mocked ESPN client."""
    return ESPNGamePoller(
        leagues=["nfl", "ncaaf"],
        poll_interval=15,
        idle_interval=60,
        espn_client=mock_espn_client,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestESPNGamePollerInit:
    """Tests for ESPNGamePoller initialization."""

    def test_default_initialization(self) -> None:
        """Test default parameters are set correctly."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller()

        assert poller.leagues == ["nfl", "ncaaf"]
        assert poller.poll_interval == 15
        assert poller.idle_interval == 60
        assert not poller.persist_jobs
        assert poller.job_store_url is None

    def test_custom_leagues(self) -> None:
        """Test custom leagues are accepted."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(leagues=["nba", "nhl"])

        assert poller.leagues == ["nba", "nhl"]

    def test_custom_intervals(self) -> None:
        """Test custom polling intervals."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(poll_interval=30, idle_interval=120)

        assert poller.poll_interval == 30
        assert poller.idle_interval == 120

    def test_poll_interval_minimum(self) -> None:
        """Test poll_interval must be at least 5 seconds."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            with pytest.raises(ValueError, match="poll_interval must be at least 5"):
                ESPNGamePoller(poll_interval=3)

    def test_idle_interval_minimum(self) -> None:
        """Test idle_interval must be at least 15 seconds."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            with pytest.raises(ValueError, match="idle_interval must be at least 15"):
                ESPNGamePoller(idle_interval=10)

    def test_custom_espn_client(self, mock_espn_client) -> None:
        """Test custom ESPN client is used."""
        poller = ESPNGamePoller(espn_client=mock_espn_client)
        assert poller.espn_client is mock_espn_client


# =============================================================================
# Job Persistence Tests
# =============================================================================


class TestJobPersistence:
    """Tests for job persistence configuration."""

    def test_persist_jobs_disabled_by_default(self) -> None:
        """Test job persistence is disabled by default."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller()

        assert not poller.persist_jobs
        assert poller.job_store_url is None

    def test_persist_jobs_enabled(self) -> None:
        """Test job persistence can be enabled with URL."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(
                persist_jobs=True,
                job_store_url="sqlite:///jobs.db",
            )

        assert poller.persist_jobs
        assert poller.job_store_url == "sqlite:///jobs.db"

    def test_persist_jobs_requires_url(self) -> None:
        """Test persist_jobs=True requires job_store_url."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            with pytest.raises(ValueError, match="job_store_url required"):
                ESPNGamePoller(persist_jobs=True)

    def test_job_store_url_without_persist_is_ignored(self) -> None:
        """Test job_store_url is stored but not used when persist_jobs=False."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = ESPNGamePoller(
                persist_jobs=False,
                job_store_url="sqlite:///unused.db",
            )

        assert not poller.persist_jobs
        # URL is stored but won't be used
        assert poller.job_store_url == "sqlite:///unused.db"


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestESPNGamePollerLifecycle:
    """Tests for start/stop lifecycle."""

    def test_not_enabled_initially(self, updater_with_mock_client) -> None:
        """Test poller is not enabled on creation."""
        assert not updater_with_mock_client.enabled

    def test_start_enables_poller(self, updater_with_mock_client) -> None:
        """Test start() enables the poller."""
        with patch.object(updater_with_mock_client, "_poll_wrapper"):
            updater_with_mock_client.start()

        assert updater_with_mock_client.enabled
        updater_with_mock_client.stop()

    def test_stop_disables_poller(self, updater_with_mock_client) -> None:
        """Test stop() disables the poller."""
        with patch.object(updater_with_mock_client, "_poll_wrapper"):
            updater_with_mock_client.start()
            updater_with_mock_client.stop()

        assert not updater_with_mock_client.enabled

    def test_double_start_raises_error(self, updater_with_mock_client) -> None:
        """Test starting twice raises RuntimeError."""
        with patch.object(updater_with_mock_client, "_poll_wrapper"):
            updater_with_mock_client.start()

            with pytest.raises(RuntimeError, match="already running"):
                updater_with_mock_client.start()

            updater_with_mock_client.stop()

    def test_stop_when_not_running_logs_warning(self, updater_with_mock_client, caplog) -> None:
        """Test stopping when not running logs warning."""
        updater_with_mock_client.stop()
        assert "not running" in caplog.text


# =============================================================================
# Stats Tracking Tests
# =============================================================================


class TestStatsTracking:
    """Tests for statistics tracking."""

    def test_initial_stats_are_zero(self, updater_with_mock_client) -> None:
        """Test initial stats are all zero/None.

        Uses BasePoller stats interface: items_fetched, items_updated, items_created
        instead of ESPN-specific games_updated.
        """
        stats = updater_with_mock_client.stats

        assert stats["polls_completed"] == 0
        assert stats["items_fetched"] == 0
        assert stats["items_updated"] == 0
        assert stats["items_created"] == 0
        assert stats["errors"] == 0
        assert stats["last_poll"] is None
        assert stats["last_error"] is None

    def test_stats_returns_copy(self, updater_with_mock_client) -> None:
        """Test stats returns a copy, not the internal dict."""
        stats1 = updater_with_mock_client.stats
        stats1["polls_completed"] = 999

        stats2 = updater_with_mock_client.stats
        assert stats2["polls_completed"] == 0


# =============================================================================
# refresh_scoreboards Tests
# =============================================================================


class TestRefreshScoreboards:
    """Tests for refresh_scoreboards() method."""

    def test_returns_detailed_results(self, updater_with_mock_client) -> None:
        """Test refresh_scoreboards returns detailed result dict."""
        with patch.object(updater_with_mock_client, "_poll_league", return_value=(5, 3)):
            with patch("precog.schedulers.espn_game_poller.get_live_games", return_value=[]):
                result = updater_with_mock_client.refresh_scoreboards()

        assert "leagues_polled" in result
        assert "games_by_league" in result
        assert "total_games_fetched" in result
        assert "total_games_updated" in result
        assert "active_games" in result
        assert "timestamp" in result
        assert "elapsed_seconds" in result

    def test_respects_active_only_flag(self, updater_with_mock_client) -> None:
        """Test active_only=True filters to active leagues."""
        with patch.object(updater_with_mock_client, "_poll_league", return_value=(2, 1)):
            # Mock: nfl has active games, ncaaf does not
            def mock_live_games(league):
                if league == "nfl":
                    return [{"id": 1}]  # Has active games
                return []  # No active games

            with patch(
                "precog.schedulers.espn_game_poller.get_live_games",
                side_effect=mock_live_games,
            ):
                result = updater_with_mock_client.refresh_scoreboards(active_only=True)

        # Should only poll nfl since it has active games
        assert result["leagues_polled"] == ["nfl"]

    def test_active_only_polls_all_when_none_active(self, updater_with_mock_client) -> None:
        """Test active_only polls all leagues when none have active games."""
        with patch.object(updater_with_mock_client, "_poll_league", return_value=(3, 2)):
            with patch("precog.schedulers.espn_game_poller.get_live_games", return_value=[]):
                result = updater_with_mock_client.refresh_scoreboards(active_only=True)

        # Should poll all configured leagues to discover new games
        assert result["leagues_polled"] == ["nfl", "ncaaf"]

    def test_custom_leagues_parameter(self, updater_with_mock_client) -> None:
        """Test custom leagues parameter overrides configured leagues."""
        with patch.object(updater_with_mock_client, "_poll_league", return_value=(1, 1)):
            with patch("precog.schedulers.espn_game_poller.get_live_games", return_value=[]):
                result = updater_with_mock_client.refresh_scoreboards(
                    leagues=["nba"],
                    active_only=False,
                )

        assert result["leagues_polled"] == ["nba"]

    def test_handles_api_errors_gracefully(self, updater_with_mock_client) -> None:
        """Test API errors are logged but don't crash."""
        from precog.api_connectors.espn_client import ESPNAPIError

        def mock_poll_league(league):
            if league == "ncaaf":
                raise ESPNAPIError("API error")
            return (5, 3)

        with patch.object(updater_with_mock_client, "_poll_league", side_effect=mock_poll_league):
            with patch("precog.schedulers.espn_game_poller.get_live_games", return_value=[]):
                result = updater_with_mock_client.refresh_scoreboards()

        # nfl succeeded, ncaaf failed
        assert result["games_by_league"]["nfl"] == 5
        assert result["games_by_league"]["ncaaf"] == 0

    def test_elapsed_seconds_is_calculated(self, updater_with_mock_client) -> None:
        """Test elapsed_seconds is a reasonable value."""
        with patch.object(updater_with_mock_client, "_poll_league", return_value=(1, 1)):
            with patch("precog.schedulers.espn_game_poller.get_live_games", return_value=[]):
                result = updater_with_mock_client.refresh_scoreboards()

        # Should be a small positive number
        assert result["elapsed_seconds"] >= 0
        assert result["elapsed_seconds"] < 10  # Shouldn't take 10 seconds


# =============================================================================
# poll_once Tests
# =============================================================================


class TestPollOnce:
    """Tests for poll_once() method."""

    def test_returns_count_dict(self, updater_with_mock_client) -> None:
        """Test poll_once returns dict with counts.

        Uses BasePoller interface: items_fetched, items_updated, items_created
        instead of ESPN-specific games_fetched, games_updated.
        """
        with patch.object(updater_with_mock_client, "_poll_league", return_value=(3, 2)):
            result = updater_with_mock_client.poll_once()

        assert "items_fetched" in result
        assert "items_updated" in result
        assert "items_created" in result

    def test_polls_configured_leagues(self, updater_with_mock_client) -> None:
        """Test poll_once polls all configured leagues."""
        poll_calls = []

        def track_poll(league):
            poll_calls.append(league)
            return (1, 1)

        with patch.object(updater_with_mock_client, "_poll_league", side_effect=track_poll):
            updater_with_mock_client.poll_once()

        assert poll_calls == ["nfl", "ncaaf"]

    def test_custom_leagues_parameter(self, updater_with_mock_client) -> None:
        """Test custom leagues parameter."""
        poll_calls = []

        def track_poll(league):
            poll_calls.append(league)
            return (1, 1)

        with patch.object(updater_with_mock_client, "_poll_league", side_effect=track_poll):
            updater_with_mock_client.poll_once(leagues=["nba"])

        assert poll_calls == ["nba"]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateESPNPoller:
    """Tests for create_espn_poller factory function."""

    def test_creates_with_defaults(self) -> None:
        """Test factory creates poller with default settings."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = create_espn_poller()

        assert poller.leagues == ["nfl", "ncaaf"]
        assert poller.poll_interval == 15
        assert poller.idle_interval == 60
        assert not poller.persist_jobs

    def test_creates_with_custom_leagues(self) -> None:
        """Test factory accepts custom leagues."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = create_espn_poller(leagues=["nba", "wnba"])

        assert poller.leagues == ["nba", "wnba"]

    def test_creates_with_custom_intervals(self) -> None:
        """Test factory accepts custom intervals."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = create_espn_poller(poll_interval=30, idle_interval=90)

        assert poller.poll_interval == 30
        assert poller.idle_interval == 90

    def test_creates_with_job_persistence(self) -> None:
        """Test factory enables job persistence."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            poller = create_espn_poller(
                persist_jobs=True,
                job_store_url="sqlite:///test_jobs.db",
            )

        assert poller.persist_jobs
        assert poller.job_store_url == "sqlite:///test_jobs.db"


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestRunSingleESPNPoll:
    """Tests for run_single_espn_poll convenience function."""

    def test_creates_poller_and_polls(self) -> None:
        """Test run_single_espn_poll creates poller and calls poll_once.

        Uses BasePoller interface: items_fetched, items_updated, items_created
        instead of ESPN-specific games_fetched, games_updated.
        """
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            with patch.object(
                ESPNGamePoller,
                "poll_once",
                return_value={"items_fetched": 5, "items_updated": 3, "items_created": 0},
            ) as mock_poll:
                result = run_single_espn_poll(["nfl"])

        mock_poll.assert_called_once()
        assert result["items_fetched"] == 5
        assert result["items_updated"] == 3


class TestRefreshAllScoreboards:
    """Tests for refresh_all_scoreboards convenience function."""

    def test_creates_poller_and_refreshes(self) -> None:
        """Test refresh_all_scoreboards creates poller and calls refresh."""
        expected_result = {
            "leagues_polled": ["nfl"],
            "total_games_fetched": 5,
            "total_games_updated": 3,
        }

        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            with patch.object(
                ESPNGamePoller, "refresh_scoreboards", return_value=expected_result
            ) as mock_refresh:
                result = refresh_all_scoreboards(["nfl"])

        mock_refresh.assert_called_once_with(active_only=True)
        assert result["leagues_polled"] == ["nfl"]

    def test_passes_active_only_flag(self) -> None:
        """Test active_only parameter is passed through."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            with patch.object(
                ESPNGamePoller, "refresh_scoreboards", return_value={}
            ) as mock_refresh:
                refresh_all_scoreboards(["nfl"], active_only=False)

        mock_refresh.assert_called_once_with(active_only=False)


# =============================================================================
# Module Export Tests
# =============================================================================


class TestModuleExports:
    """Tests for module-level exports from schedulers package.

    Tests both the new primary exports (ESPNGamePoller, create_espn_poller, etc.)
    and the backward compatibility aliases (MarketUpdater, create_market_updater, etc.).
    """

    def test_espn_game_poller_exported(self) -> None:
        """Test ESPNGamePoller is exported from schedulers package."""
        from precog.schedulers import ESPNGamePoller as ImportedClass

        assert ImportedClass is ESPNGamePoller

    def test_create_espn_poller_exported(self) -> None:
        """Test create_espn_poller is exported."""
        from precog.schedulers import create_espn_poller as imported_func

        assert imported_func is create_espn_poller

    def test_refresh_all_scoreboards_exported(self) -> None:
        """Test refresh_all_scoreboards is exported."""
        from precog.schedulers import refresh_all_scoreboards as imported_func

        assert imported_func is refresh_all_scoreboards

    def test_run_single_espn_poll_exported(self) -> None:
        """Test run_single_espn_poll is exported."""
        from precog.schedulers import run_single_espn_poll as imported_func

        assert imported_func is run_single_espn_poll


class TestBackwardCompatibilityAliases:
    """Tests for backward compatibility aliases.

    These aliases allow existing code using the old names (MarketUpdater, etc.)
    to continue working during the migration period.
    """

    def test_market_updater_is_alias_for_espn_game_poller(self) -> None:
        """Test MarketUpdater is an alias for ESPNGamePoller."""
        from precog.schedulers import MarketUpdater as ImportedClass

        # MarketUpdater should be the same class as ESPNGamePoller
        assert ImportedClass is ESPNGamePoller
        assert ImportedClass is MarketUpdater

    def test_create_market_updater_is_alias_for_create_espn_poller(self) -> None:
        """Test create_market_updater is an alias for create_espn_poller."""
        from precog.schedulers import create_market_updater as imported_func

        assert imported_func is create_espn_poller
        assert imported_func is create_market_updater

    def test_run_single_poll_is_alias_for_run_single_espn_poll(self) -> None:
        """Test run_single_poll is an alias for run_single_espn_poll."""
        from precog.schedulers import run_single_poll as imported_func

        assert imported_func is run_single_espn_poll
        assert imported_func is run_single_poll

    def test_backward_compat_creates_espn_game_poller(self) -> None:
        """Test backward compatibility: MarketUpdater creates ESPNGamePoller instance."""
        with patch("precog.schedulers.espn_game_poller.ESPNClient"):
            instance = MarketUpdater()

        assert isinstance(instance, ESPNGamePoller)
        # Verify it's the same class, just aliased
        assert type(instance).__name__ == "ESPNGamePoller"
