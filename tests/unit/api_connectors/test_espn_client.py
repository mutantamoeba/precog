"""
Unit tests for ESPN API Client - Phase 2.

Tests cover:
- Client initialization
- NFL/NCAAF scoreboard fetching
- Multi-sport support (NFL, NCAAF, NBA, NCAAB, NHL, WNBA) - REQ-DATA-003
- Response parsing (game state extraction)
- Rate limiting (500 req/hour)
- Error handling (retries, timeouts, HTTP errors)
- Edge cases (empty responses, malformed data)

Following TDD: Tests written BEFORE implementation.
Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1

Requirements Tested:
    - REQ-DATA-003: Multi-Sport Support (6 Leagues: NFL, NCAAF, NBA, NCAAB, NHL, WNBA)

Educational Note:
    These tests use the pytest-mock library for mocking HTTP requests.
    The ESPN API is a public API without authentication, but we still
    mock it to avoid network dependencies in unit tests.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from tests.fixtures import (
    ESPN_ERROR_404_RESPONSE,
    ESPN_NCAAF_SCOREBOARD_LIVE,
    ESPN_NFL_SCOREBOARD_EMPTY,
    ESPN_NFL_SCOREBOARD_FINAL,
    ESPN_NFL_SCOREBOARD_HALFTIME,
    ESPN_NFL_SCOREBOARD_LIVE,
    ESPN_NFL_SCOREBOARD_OVERTIME,
    ESPN_NFL_SCOREBOARD_PREGAME,
    ESPN_NFL_SCOREBOARD_REDZONE,
    ESPN_RESPONSE_MISSING_COMPETITORS,
    ESPN_RESPONSE_MISSING_EVENTS,
    ESPN_RESPONSE_NULL_SCORES,
)

# =============================================================================
# Test Constants
# =============================================================================

ESPN_NFL_ENDPOINT = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_NCAAF_ENDPOINT = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)


# =============================================================================
# Client Initialization Tests
# =============================================================================


class TestESPNClientInitialization:
    """Tests for ESPN client initialization."""

    def test_client_initializes_with_default_config(self):
        """Verify client initializes with default configuration."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()

        assert client is not None
        assert client.rate_limit_per_hour == 250
        assert client.timeout_seconds == 10
        assert client.max_retries == 3

    def test_client_accepts_custom_config(self):
        """Verify client accepts custom configuration values."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(
            rate_limit_per_hour=200,
            timeout_seconds=5,
            max_retries=5,
        )

        assert client.rate_limit_per_hour == 200
        assert client.timeout_seconds == 5
        assert client.max_retries == 5

    def test_client_has_session(self):
        """Verify client creates requests session for connection pooling."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()

        assert hasattr(client, "session")
        assert isinstance(client.session, requests.Session)

    def test_client_tracks_request_count(self):
        """Verify client initializes request tracking for rate limiting."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient()

        assert hasattr(client, "request_timestamps")
        assert isinstance(client.request_timestamps, list)
        assert len(client.request_timestamps) == 0


# =============================================================================
# NFL Scoreboard Tests
# =============================================================================


class TestNFLScoreboard:
    """Tests for NFL scoreboard fetching."""

    @patch("requests.Session.get")
    def test_get_nfl_scoreboard_returns_events(self, mock_get: MagicMock):
        """Verify NFL scoreboard returns list of game events."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_nfl_scoreboard()

        assert isinstance(result, list)
        assert len(result) == 2  # ESPN_NFL_SCOREBOARD_LIVE has 2 events
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_get_nfl_scoreboard_correct_endpoint(self, mock_get: MagicMock):
        """Verify NFL scoreboard uses correct ESPN API endpoint."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        client.get_nfl_scoreboard()

        call_args = mock_get.call_args
        assert ESPN_NFL_ENDPOINT in call_args[0][0]

    @patch("requests.Session.get")
    def test_get_nfl_scoreboard_with_date_filter(self, mock_get: MagicMock):
        """Verify NFL scoreboard accepts date parameter for filtering."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        target_date = datetime(2025, 12, 15)
        client.get_nfl_scoreboard(date=target_date)

        call_args = mock_get.call_args
        # ESPN API uses dates= parameter - check the params dict directly
        _, kwargs = call_args
        assert kwargs.get("params", {}).get("dates") == "20251215"

    @patch("requests.Session.get")
    def test_get_nfl_scoreboard_empty_returns_empty_list(self, mock_get: MagicMock):
        """Verify empty scoreboard returns empty list (no games today)."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_EMPTY
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_nfl_scoreboard()

        assert result == []


# =============================================================================
# NCAAF Scoreboard Tests
# =============================================================================


class TestNCAAFScoreboard:
    """Tests for NCAAF (college football) scoreboard fetching."""

    @patch("requests.Session.get")
    def test_get_ncaaf_scoreboard_returns_events(self, mock_get: MagicMock):
        """Verify NCAAF scoreboard returns list of game events."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NCAAF_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_ncaaf_scoreboard()

        assert isinstance(result, list)
        assert len(result) == 1  # ESPN_NCAAF_SCOREBOARD_LIVE has 1 event
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_get_ncaaf_scoreboard_correct_endpoint(self, mock_get: MagicMock):
        """Verify NCAAF scoreboard uses correct ESPN API endpoint."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NCAAF_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        client.get_ncaaf_scoreboard()

        call_args = mock_get.call_args
        assert ESPN_NCAAF_ENDPOINT in call_args[0][0]


# =============================================================================
# Game State Parsing Tests
# =============================================================================


class TestGameStateParsing:
    """Tests for parsing game state from ESPN API response."""

    @patch("requests.Session.get")
    def test_parse_live_game_extracts_scores(self, mock_get: MagicMock):
        """Verify parsing extracts home and away scores from live game.

        Educational Note:
            ESPNGameFull structure separates static metadata from dynamic state.
            Scores are in game["state"] since they change during the game.
        """
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # First game: KC @ BUF - access via state dict
        game = games[0]
        assert game["state"]["home_score"] == 24
        assert game["state"]["away_score"] == 21

    @patch("requests.Session.get")
    def test_parse_live_game_extracts_teams(self, mock_get: MagicMock):
        """Verify parsing extracts team abbreviations from live game.

        Educational Note:
            Team info is in game["metadata"]["home_team"] and game["metadata"]["away_team"]
            because team identity is static (doesn't change during game).
        """
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # First game: KC @ BUF - access via metadata dict
        game = games[0]
        assert game["metadata"]["home_team"]["team_code"] == "BUF"
        assert game["metadata"]["away_team"]["team_code"] == "KC"

    @patch("requests.Session.get")
    def test_parse_live_game_extracts_period_and_clock(self, mock_get: MagicMock):
        """Verify parsing extracts period and clock from live game."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        # First game: KC @ BUF in 4th quarter - access via state dict
        game = games[0]
        assert game["state"]["period"] == 4
        assert game["state"]["clock_seconds"] == 485
        assert game["state"]["clock_display"] == "8:05"

    @patch("requests.Session.get")
    def test_parse_live_game_extracts_status(self, mock_get: MagicMock):
        """Verify parsing extracts game status (in_progress, final, etc.)."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert game["state"]["game_status"] == "in_progress"

    @patch("requests.Session.get")
    def test_parse_pregame_status(self, mock_get: MagicMock):
        """Verify parsing handles pre-game status correctly."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_PREGAME
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert game["state"]["game_status"] == "pre"
        assert game["state"]["home_score"] == 0
        assert game["state"]["away_score"] == 0

    @patch("requests.Session.get")
    def test_parse_final_game_status(self, mock_get: MagicMock):
        """Verify parsing handles final (completed) game status."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_FINAL
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert game["state"]["game_status"] == "final"
        assert game["state"]["home_score"] == 20
        assert game["state"]["away_score"] == 27

    @patch("requests.Session.get")
    def test_parse_halftime_status(self, mock_get: MagicMock):
        """Verify parsing handles halftime status correctly."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_HALFTIME
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert game["state"]["game_status"] == "halftime"

    @patch("requests.Session.get")
    def test_parse_overtime_period(self, mock_get: MagicMock):
        """Verify parsing handles overtime period correctly."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_OVERTIME
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert game["state"]["period"] == 5  # OT = period 5

    @patch("requests.Session.get")
    def test_parse_extracts_espn_event_id(self, mock_get: MagicMock):
        """Verify parsing extracts ESPN event ID for tracking.

        Educational Note:
            espn_event_id is in metadata (static identifier for the game).
        """
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert "espn_event_id" in game["metadata"]
        assert game["metadata"]["espn_event_id"] == "401547417"

    @patch("requests.Session.get")
    def test_parse_extracts_possession_info(self, mock_get: MagicMock):
        """Verify parsing extracts possession and down/distance info.

        Educational Note:
            Situation data (possession, down, distance) is in game["state"]["situation"]
            because this data changes during the game.
        """
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        situation = game["state"]["situation"]
        assert "possession" in situation
        assert "down" in situation
        assert "distance" in situation
        assert "yard_line" in situation

    @patch("requests.Session.get")
    def test_parse_extracts_red_zone_flag(self, mock_get: MagicMock):
        """Verify parsing extracts red zone indicator."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_REDZONE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert game["state"]["situation"]["is_red_zone"] is True


# =============================================================================
# Sport-Conditional Situation Parsing Tests (#398)
# =============================================================================


def _make_espn_scoreboard(situation: dict, team_ids: tuple[str, str] = ("1", "2")) -> dict:
    """Build a minimal ESPN scoreboard response with given situation data."""
    home_id, away_id = team_ids
    return {
        "events": [
            {
                "id": "401999001",
                "date": "2026-03-14T20:00Z",
                "competitions": [
                    {
                        "id": "401999001",
                        "competitors": [
                            {
                                "id": home_id,
                                "homeAway": "home",
                                "team": {
                                    "id": home_id,
                                    "abbreviation": "HME",
                                    "displayName": "Home Team",
                                    "name": "HomeName",
                                    "location": "HomeCity",
                                },
                                "score": "50",
                            },
                            {
                                "id": away_id,
                                "homeAway": "away",
                                "team": {
                                    "id": away_id,
                                    "abbreviation": "AWY",
                                    "displayName": "Away Team",
                                    "name": "AwayName",
                                    "location": "AwayCity",
                                },
                                "score": "45",
                            },
                        ],
                        "venue": {
                            "id": "1000",
                            "fullName": "Test Arena",
                            "address": {"city": "TestCity", "state": "TS"},
                        },
                        "status": {
                            "clock": 300.0,
                            "displayClock": "5:00",
                            "period": 3,
                            "type": {
                                "id": "2",
                                "state": "in",
                                "completed": False,
                                "description": "In Progress",
                            },
                        },
                        "situation": situation,
                        "broadcasts": [],
                    }
                ],
            }
        ]
    }


class TestSportConditionalSituationParsing:
    """Tests for sport-conditional situation data extraction (#398)."""

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_nfl_situation_includes_football_fields(self, mock_get: MagicMock):
        """NFL parsing extracts down, distance, yard_line, turnovers."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "possession": "1",
            "homeTimeouts": 2,
            "awayTimeouts": 1,
            "down": 3,
            "distance": 7,
            "yardLine": 42,
            "isRedZone": False,
            "homeTurnovers": 1,
            "awayTurnovers": 0,
            "lastPlay": {
                "text": "Pass complete for 12 yards",
                "scoreValue": 0,
                "drive": {"plays": 6, "yards": 43},
            },
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit["down"] == 3
        assert sit["distance"] == 7
        assert sit["yard_line"] == 42
        assert sit["is_red_zone"] is False
        assert sit["home_timeouts"] == 2
        assert sit["away_timeouts"] == 1
        assert sit["home_turnovers"] == 1
        assert sit["away_turnovers"] == 0
        assert sit["last_play"] == "Pass complete for 12 yards"
        assert sit["drive_plays"] == 6
        assert sit["drive_yards"] == 43
        # Should NOT have basketball/hockey fields
        assert "home_fouls" not in sit
        assert "home_powerplay" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_nba_situation_excludes_football_fields(self, mock_get: MagicMock):
        """NBA parsing does NOT include down/distance/yard_line."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "lastPlay": {
                "text": "makes 23-foot three point jumper",
                "scoreValue": 3,
            },
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nba_scoreboard()
        sit = games[0]["state"]["situation"]

        # Should NOT have football fields
        assert "down" not in sit
        assert "distance" not in sit
        assert "yard_line" not in sit
        assert "is_red_zone" not in sit
        # Should have lastPlay text
        assert sit["last_play"] == "makes 23-foot three point jumper"

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_nba_situation_extracts_fouls_when_present(self, mock_get: MagicMock):
        """NBA parsing extracts fouls/bonus when ESPN provides them."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "homeTimeouts": 4,
            "awayTimeouts": 3,
            "homeFouls": 3,
            "awayFouls": 5,
            "bonus": "away",
            "lastPlay": {"text": "free throw made"},
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nba_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit["home_fouls"] == 3
        assert sit["away_fouls"] == 5
        assert sit["bonus"] == "away"
        assert sit["home_timeouts"] == 4
        assert sit["away_timeouts"] == 3

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_nhl_situation_extracts_powerplay(self, mock_get: MagicMock):
        """NHL parsing extracts powerplay and shots when present."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "homePowerPlay": True,
            "awayPowerPlay": False,
            "powerPlayTime": "1:32",
            "homeShots": 28,
            "awayShots": 22,
            "lastPlay": {"text": "Shot on goal saved"},
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nhl_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit["home_powerplay"] is True
        assert sit["away_powerplay"] is False
        assert sit["powerplay_time"] == "1:32"
        assert sit["home_shots"] == 28
        assert sit["away_shots"] == 22
        assert "down" not in sit
        assert "home_fouls" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_nba_minimal_situation_only_has_lastplay(self, mock_get: MagicMock):
        """NBA with minimal ESPN data (just lastPlay) produces clean situation."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "lastPlay": {"text": "layup made", "scoreValue": 2},
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nba_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit == {"last_play": "layup made"}

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_empty_situation_nba_produces_empty_dict(self, mock_get: MagicMock):
        """Empty ESPN situation for NBA produces empty dict."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard({})
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nba_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit == {}

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_empty_situation_nfl_still_sets_defaults(self, mock_get: MagicMock):
        """Empty ESPN situation for NFL still sets timeout/redzone defaults."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard({})
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()
        sit = games[0]["state"]["situation"]

        # Football defaults are always set even with empty input
        assert sit["home_timeouts"] == 3
        assert sit["away_timeouts"] == 3
        assert sit["is_red_zone"] is False
        assert sit["down"] is None
        assert sit["distance"] is None
        # Should NOT have basketball/hockey fields
        assert "home_fouls" not in sit
        assert "home_powerplay" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_empty_situation_nhl_produces_empty_dict(self, mock_get: MagicMock):
        """Empty ESPN situation for NHL produces empty dict."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard({})
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nhl_scoreboard()
        sit = games[0]["state"]["situation"]

        assert "home_powerplay" not in sit
        assert "down" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_ncaaf_routes_to_football_parsing(self, mock_get: MagicMock):
        """NCAAF uses same football situation fields as NFL."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "down": 1,
            "distance": 10,
            "yardLine": 25,
            "isRedZone": True,
            "homeTimeouts": 3,
            "awayTimeouts": 3,
            "homeTurnovers": 0,
            "awayTurnovers": 2,
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_ncaaf_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit["down"] == 1
        assert sit["distance"] == 10
        assert sit["yard_line"] == 25
        assert sit["is_red_zone"] is True
        assert sit["away_turnovers"] == 2
        # Should NOT have basketball/hockey fields
        assert "home_fouls" not in sit
        assert "home_powerplay" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_ncaab_routes_to_basketball_parsing(self, mock_get: MagicMock):
        """NCAAB uses same basketball situation fields as NBA."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "homeTimeouts": 5,
            "awayTimeouts": 4,
            "homeFouls": 7,
            "awayFouls": 4,
            "possessionArrow": "home",
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_ncaab_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit["home_fouls"] == 7
        assert sit["away_fouls"] == 4
        assert sit["possession_arrow"] == "home"
        assert sit["home_timeouts"] == 5
        # Should NOT have football/hockey fields
        assert "down" not in sit
        assert "home_powerplay" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_wnba_routes_to_basketball_parsing(self, mock_get: MagicMock):
        """WNBA uses same basketball situation fields as NBA."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "homeFouls": 2,
            "bonus": "home",
            "lastPlay": {"text": "three-pointer made"},
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_wnba_scoreboard()
        sit = games[0]["state"]["situation"]

        assert sit["home_fouls"] == 2
        assert sit["bonus"] == "home"
        assert sit["last_play"] == "three-pointer made"
        assert "down" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_nfl_without_lastplay_still_extracts_turnovers(self, mock_get: MagicMock):
        """Turnovers are top-level situation fields, not gated by lastPlay."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "down": 2,
            "distance": 5,
            "yardLine": 30,
            "isRedZone": False,
            "homeTimeouts": 3,
            "awayTimeouts": 2,
            "homeTurnovers": 2,
            "awayTurnovers": 1,
            # No lastPlay key at all
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()
        sit = games[0]["state"]["situation"]

        # Turnovers extracted even without lastPlay
        assert sit["home_turnovers"] == 2
        assert sit["away_turnovers"] == 1
        # Drive data absent (no lastPlay)
        assert "drive_plays" not in sit
        assert "drive_yards" not in sit
        assert "last_play" not in sit

    @pytest.mark.unit
    @patch("requests.Session.get")
    def test_unknown_sport_fallback(self, mock_get: MagicMock):
        """Unknown sports store basic timeout data as fallback."""
        from precog.api_connectors.espn_client import ESPNClient

        situation_raw = {
            "homeTimeouts": 2,
            "awayTimeouts": 3,
            "lastPlay": {"text": "goal scored"},
        }
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = _make_espn_scoreboard(situation_raw)
        mock_get.return_value = mock_response

        client = ESPNClient()
        # Call _parse_event directly with an unknown league
        events = mock_response.json.return_value["events"]
        result = client._parse_event(events[0], league="soccer")

        sit = result["state"]["situation"]
        assert sit["home_timeouts"] == 2
        assert sit["away_timeouts"] == 3
        assert sit["last_play"] == "goal scored"
        # Should NOT have sport-specific fields
        assert "down" not in sit
        assert "home_fouls" not in sit
        assert "home_powerplay" not in sit


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting (500 requests per hour)."""

    @patch("requests.Session.get")
    def test_rate_limiter_tracks_requests(self, mock_get: MagicMock):
        """Verify rate limiter tracks request timestamps."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        initial_count = len(client.request_timestamps)

        client.get_nfl_scoreboard()

        assert len(client.request_timestamps) == initial_count + 1

    @patch("requests.Session.get")
    def test_rate_limiter_blocks_when_limit_reached(self, mock_get: MagicMock):
        """Verify rate limiter blocks requests when limit is reached."""
        from precog.api_connectors.espn_client import ESPNClient, RateLimitExceeded

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=5)

        # Simulate 5 requests in the past hour
        now = datetime.now()
        client.request_timestamps = [now - timedelta(minutes=i) for i in range(5)]

        # 6th request should raise RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            client.get_nfl_scoreboard()

    @patch("requests.Session.get")
    def test_rate_limiter_allows_after_window_expires(self, mock_get: MagicMock):
        """Verify rate limiter allows requests after hour window expires."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=5)

        # Simulate 5 requests from >1 hour ago
        old_time = datetime.now() - timedelta(hours=2)
        client.request_timestamps = [old_time for _ in range(5)]

        # Should not raise - old requests expired
        result = client.get_nfl_scoreboard()
        assert result is not None

    @patch("requests.Session.get")
    def test_rate_limiter_cleans_old_timestamps(self, mock_get: MagicMock):
        """Verify rate limiter removes timestamps older than 1 hour."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient(rate_limit_per_hour=10)

        # Add mix of old and recent timestamps
        now = datetime.now()
        old_timestamps = [now - timedelta(hours=2) for _ in range(5)]
        recent_timestamps = [now - timedelta(minutes=30) for _ in range(3)]
        client.request_timestamps = old_timestamps + recent_timestamps

        client.get_nfl_scoreboard()

        # Old timestamps should be cleaned
        assert len(client.request_timestamps) <= 4  # 3 recent + 1 new

    def test_get_remaining_requests(self):
        """Verify client reports remaining requests in rate limit window."""
        from precog.api_connectors.espn_client import ESPNClient

        client = ESPNClient(rate_limit_per_hour=500)

        # No requests made yet
        assert client.get_remaining_requests() == 500

        # Simulate 100 requests
        now = datetime.now()
        client.request_timestamps = [now - timedelta(minutes=i % 60) for i in range(100)]

        assert client.get_remaining_requests() == 400


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling (HTTP errors, timeouts, retries)."""

    @patch("requests.Session.get")
    def test_handles_404_error(self, mock_get: MagicMock):
        """Verify client handles 404 Not Found errors gracefully."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = ESPN_ERROR_404_RESPONSE

        # Create HTTPError with response attribute properly set
        http_error = requests.HTTPError("404 Not Found")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        client = ESPNClient()

        with pytest.raises(ESPNAPIError) as exc_info:
            client.get_nfl_scoreboard()

        # 404 errors should NOT be retried - should fail immediately
        assert mock_get.call_count == 1  # Only 1 attempt (no retries for 4xx)
        assert "404" in str(exc_info.value)

    @patch("requests.Session.get")
    def test_handles_500_error_with_retry(self, mock_get: MagicMock):
        """Verify client retries on 500 Internal Server Error."""
        from precog.api_connectors.espn_client import ESPNClient

        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.raise_for_status.side_effect = requests.HTTPError(
            "500 Internal Server Error"
        )

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = ESPN_NFL_SCOREBOARD_LIVE

        mock_get.side_effect = [mock_response_fail, mock_response_success]

        client = ESPNClient(max_retries=3)
        result = client.get_nfl_scoreboard()

        assert result is not None
        assert mock_get.call_count == 2  # 1 fail + 1 success

    @patch("requests.Session.get")
    def test_handles_503_service_unavailable(self, mock_get: MagicMock):
        """Verify client handles 503 Service Unavailable with backoff."""
        from precog.api_connectors.espn_client import ESPNClient

        # Multiple failures then success
        mock_response_fail = Mock()
        mock_response_fail.status_code = 503
        mock_response_fail.raise_for_status.side_effect = requests.HTTPError(
            "503 Service Unavailable"
        )

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = ESPN_NFL_SCOREBOARD_LIVE

        mock_get.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]

        client = ESPNClient(max_retries=3)
        result = client.get_nfl_scoreboard()

        assert result is not None
        assert mock_get.call_count == 3

    @patch("requests.Session.get")
    def test_raises_after_max_retries_exceeded(self, mock_get: MagicMock):
        """Verify client raises error after exhausting retries."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")
        mock_get.return_value = mock_response

        client = ESPNClient(max_retries=3)

        with pytest.raises(ESPNAPIError):
            client.get_nfl_scoreboard()

        assert mock_get.call_count == 4  # 1 initial + 3 retries

    @patch("requests.Session.get")
    def test_handles_timeout(self, mock_get: MagicMock):
        """Verify client handles request timeout."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        mock_get.side_effect = requests.Timeout("Request timed out")

        client = ESPNClient(timeout_seconds=5, max_retries=1)

        with pytest.raises(ESPNAPIError) as exc_info:
            client.get_nfl_scoreboard()

        assert "timeout" in str(exc_info.value).lower()

    @patch("requests.Session.get")
    def test_handles_connection_error(self, mock_get: MagicMock):
        """Verify client handles connection errors (network issues)."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        mock_get.side_effect = requests.ConnectionError("Network unreachable")

        client = ESPNClient(max_retries=1)

        with pytest.raises(ESPNAPIError) as exc_info:
            client.get_nfl_scoreboard()

        assert "connection" in str(exc_info.value).lower()

    @patch("requests.Session.get")
    def test_uses_exponential_backoff(self, mock_get: MagicMock):
        """Verify client uses exponential backoff between retries."""

        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("500")

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = ESPN_NFL_SCOREBOARD_LIVE

        mock_get.side_effect = [mock_response, mock_response_success]

        client = ESPNClient(max_retries=3)

        # Record timing
        with patch("time.sleep") as mock_sleep:
            client.get_nfl_scoreboard()

            # First retry should have some backoff delay
            assert mock_sleep.called
            # Backoff should be > 0
            call_args = mock_sleep.call_args[0][0]
            assert call_args > 0


# =============================================================================
# Edge Case Tests (Chaos - Malformed Response Handling)
# =============================================================================


@pytest.mark.chaos
class TestEdgeCases:
    """Tests for edge cases and malformed data.

    These tests verify the client handles malformed API responses gracefully.
    Marked as @pytest.mark.chaos per TESTING_STRATEGY_V3.2 - chaos tests cover
    failure recovery scenarios including malformed responses.

    Educational Note:
        Chaos tests validate system resilience when things go wrong.
        These tests ensure the ESPN client doesn't crash when receiving
        unexpected or malformed data from the API.
    """

    @patch("requests.Session.get")
    def test_handles_missing_events_key(self, mock_get: MagicMock):
        """Verify client handles response missing 'events' key."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_RESPONSE_MISSING_EVENTS
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_nfl_scoreboard()

        # Should return empty list, not crash
        assert result == []

    @patch("requests.Session.get")
    def test_handles_missing_competitors_key(self, mock_get: MagicMock):
        """Verify client handles response with missing competitors."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_RESPONSE_MISSING_COMPETITORS
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_nfl_scoreboard()

        # Should skip malformed games, return empty or filtered list
        assert isinstance(result, list)

    @patch("requests.Session.get")
    def test_handles_null_scores(self, mock_get: MagicMock):
        """Verify client handles null/None scores (pre-game edge case)."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_RESPONSE_NULL_SCORES
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_nfl_scoreboard()

        # Should handle gracefully - convert None to 0
        if result:
            game = result[0]
            assert game.get("home_score", 0) == 0
            assert game.get("away_score", 0) == 0

    @patch("requests.Session.get")
    def test_handles_json_decode_error(self, mock_get: MagicMock):
        """Verify client handles invalid JSON response."""
        from precog.api_connectors.espn_client import ESPNAPIError, ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        client = ESPNClient()

        with pytest.raises(ESPNAPIError):
            client.get_nfl_scoreboard()


# =============================================================================
# Get Live Games Helper Tests
# =============================================================================


class TestGetLiveGames:
    """Tests for filtering to only live/in-progress games."""

    @patch("requests.Session.get")
    def test_get_live_games_filters_completed(self, mock_get: MagicMock):
        """Verify get_live_games excludes completed games."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_FINAL
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_live_games(league="nfl")

        # Final games should be filtered out
        assert result == []

    @patch("requests.Session.get")
    def test_get_live_games_filters_scheduled(self, mock_get: MagicMock):
        """Verify get_live_games excludes scheduled (future) games."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_PREGAME
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_live_games(league="nfl")

        # Pre-game should be filtered out
        assert result == []

    @patch("requests.Session.get")
    def test_get_live_games_includes_in_progress(self, mock_get: MagicMock):
        """Verify get_live_games includes in-progress games."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_live_games(league="nfl")

        # Both games in ESPN_NFL_SCOREBOARD_LIVE are in progress
        assert len(result) == 2

    @patch("requests.Session.get")
    def test_get_live_games_includes_halftime(self, mock_get: MagicMock):
        """Verify get_live_games includes games at halftime."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_HALFTIME
        mock_get.return_value = mock_response

        client = ESPNClient()
        result = client.get_live_games(league="nfl")

        # Halftime counts as "live" (game not over)
        assert len(result) == 1


# =============================================================================
# TypedDict Return Type Tests
# =============================================================================


class TestTypedDictReturnTypes:
    """Tests for TypedDict return types (type safety).

    Educational Note:
        ESPNGameFull now returns a normalized structure with:
        - metadata: Static game info (teams, venue, broadcast)
        - state: Dynamic game state (scores, clock, situation)
    """

    @patch("requests.Session.get")
    def test_game_state_has_required_keys(self, mock_get: MagicMock):
        """Verify parsed game state has all required top-level and nested keys."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]

        # Top-level keys (ESPNGameFull structure)
        assert "metadata" in game, "Missing required key: metadata"
        assert "state" in game, "Missing required key: state"

        # Metadata keys
        metadata_keys = [
            "espn_event_id",
            "home_team",
            "away_team",
        ]
        for key in metadata_keys:
            assert key in game["metadata"], f"Missing metadata key: {key}"

        # State keys
        state_keys = [
            "home_score",
            "away_score",
            "period",
            "clock_seconds",
            "clock_display",
            "game_status",
        ]
        for key in state_keys:
            assert key in game["state"], f"Missing state key: {key}"

    @patch("requests.Session.get")
    def test_score_values_are_integers(self, mock_get: MagicMock):
        """Verify score values are integers (not strings)."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        assert isinstance(game["state"]["home_score"], int)
        assert isinstance(game["state"]["away_score"], int)

    @patch("requests.Session.get")
    def test_team_abbreviations_are_strings(self, mock_get: MagicMock):
        """Verify team abbreviations are strings."""
        from precog.api_connectors.espn_client import ESPNClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        mock_get.return_value = mock_response

        client = ESPNClient()
        games = client.get_nfl_scoreboard()

        game = games[0]
        home_team_code = game["metadata"]["home_team"]["team_code"]
        away_team_code = game["metadata"]["away_team"]["team_code"]

        assert isinstance(home_team_code, str)
        assert isinstance(away_team_code, str)
        assert len(home_team_code) <= 4  # NFL abbreviations are 2-4 chars
        assert len(away_team_code) <= 4
