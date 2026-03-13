"""
Unit tests for ESPN team ID validation module.

Tests cover:
- ESPN API team fetching with mocked responses
- Code alias resolution (ESPN abbreviation -> DB team_code)
- Mismatch detection between ESPN API and database
- Auto-correction of mismatched ESPN IDs
- Network error handling (graceful degradation)
- Multi-league validation orchestration

Educational Note:
    These tests mock both requests.get (ESPN API) and database functions
    to test the validation logic in isolation. No real API calls or
    database connections are made.

Reference: src/precog/api_connectors/espn_team_validator.py
Related: scripts/fix_espn_team_ids.py (standalone audit script)
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from precog.api_connectors.espn_team_validator import (
    CODE_ALIASES,
    LEAGUE_CONFIGS,
    _get_team_by_espn_id_or_code,
    _resolve_db_code,
    fetch_espn_teams,
    validate_espn_teams,
    validate_league_teams,
)

# =============================================================================
# Test Fixtures - Mock ESPN API Responses
# =============================================================================


def _make_espn_teams_response(teams: list[dict]) -> dict:
    """Build a mock ESPN teams API response structure.

    Args:
        teams: List of team dicts with id, abbreviation, displayName fields.

    Returns:
        Dict mimicking the ESPN API response shape.

    Educational Note:
        ESPN wraps teams in a deeply nested structure:
        sports -> [0] -> leagues -> [0] -> teams -> [i] -> team -> {data}
    """
    return {"sports": [{"leagues": [{"teams": [{"team": t} for t in teams]}]}]}


@pytest.fixture
def mock_nfl_espn_teams():
    """A small set of NFL teams as ESPN API would return them."""
    return [
        {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        {"id": "2", "abbreviation": "BUF", "displayName": "Buffalo Bills"},
        {"id": "28", "abbreviation": "WSH", "displayName": "Washington Commanders"},
        {"id": "25", "abbreviation": "SF", "displayName": "San Francisco 49ers"},
    ]


@pytest.fixture
def mock_nhl_espn_teams():
    """A small set of NHL teams as ESPN API would return them."""
    return [
        {"id": "1", "abbreviation": "BOS", "displayName": "Boston Bruins"},
        {"id": "26", "abbreviation": "LA", "displayName": "Los Angeles Kings"},
        {"id": "14", "abbreviation": "TB", "displayName": "Tampa Bay Lightning"},
    ]


# =============================================================================
# Tests: Code Alias Resolution
# =============================================================================


class TestCodeAliasResolution:
    """Tests for _resolve_db_code function."""

    def test_resolves_nfl_alias(self):
        """ESPN 'WSH' should resolve to our DB code 'WAS' for NFL."""
        assert _resolve_db_code("WSH", "nfl") == "WAS"

    def test_returns_unchanged_when_no_alias(self):
        """Team codes with no alias should pass through unchanged."""
        assert _resolve_db_code("KC", "nfl") == "KC"
        assert _resolve_db_code("BUF", "nfl") == "BUF"

    def test_resolves_nhl_aliases(self):
        """NHL aliases should resolve correctly."""
        assert _resolve_db_code("LA", "nhl") == "LAK"
        assert _resolve_db_code("TB", "nhl") == "TBL"
        assert _resolve_db_code("SJ", "nhl") == "SJS"
        assert _resolve_db_code("NJ", "nhl") == "NJD"
        assert _resolve_db_code("UTAH", "nhl") == "UTA"

    def test_resolves_nba_aliases(self):
        """NBA aliases should resolve correctly."""
        assert _resolve_db_code("GS", "nba") == "GSW"
        assert _resolve_db_code("NO", "nba") == "NOP"
        assert _resolve_db_code("NY", "nba") == "NYK"
        assert _resolve_db_code("SA", "nba") == "SAS"

    def test_resolves_ncaaf_aliases(self):
        """NCAAF aliases should resolve correctly."""
        assert _resolve_db_code("OU", "ncaaf") == "OKLA"
        assert _resolve_db_code("UNC", "ncaaf") == "NC"
        assert _resolve_db_code("TA&M", "ncaaf") == "TAMU"

    def test_unknown_league_returns_unchanged(self):
        """Codes for unknown leagues should pass through unchanged."""
        assert _resolve_db_code("XYZ", "unknown_league") == "XYZ"


# =============================================================================
# Tests: ESPN API Fetching
# =============================================================================


class TestFetchESPNTeams:
    """Tests for fetch_espn_teams function."""

    @patch("precog.api_connectors.espn_team_validator.requests.Session")
    def test_fetches_teams_successfully(self, mock_session_cls, mock_nfl_espn_teams):
        """Should parse teams from ESPN API response."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = _make_espn_teams_response(mock_nfl_espn_teams)
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        teams = fetch_espn_teams("nfl")

        assert len(teams) == 4
        assert teams[0]["id"] == "12"
        assert teams[0]["abbreviation"] == "KC"
        mock_session.get.assert_called_once()

    @patch("precog.api_connectors.espn_team_validator.requests.Session")
    def test_handles_empty_response(self, mock_session_cls):
        """Should return empty list when ESPN returns no teams."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = {"sports": []}
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        teams = fetch_espn_teams("nfl")

        assert teams == []

    @patch("precog.api_connectors.espn_team_validator.requests.Session")
    def test_handles_network_error(self, mock_session_cls):
        """Should raise RequestException on network failure."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_session.get.side_effect = requests.ConnectionError("Network down")

        with pytest.raises(requests.ConnectionError):
            fetch_espn_teams("nfl")

    @patch("precog.api_connectors.espn_team_validator.requests.Session")
    def test_paginates_large_results(self, mock_session_cls):
        """Should paginate when a page returns exactly limit teams."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # Page 1: exactly 2 teams (matching limit=2), so we request page 2
        page1_teams = [
            {"id": "1", "abbreviation": "BOS", "displayName": "Boston Bruins"},
            {"id": "2", "abbreviation": "NYR", "displayName": "New York Rangers"},
        ]
        # Page 2: 1 team (less than limit=2), so pagination stops
        page2_teams = [
            {"id": "3", "abbreviation": "CHI", "displayName": "Chicago Blackhawks"},
        ]

        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = _make_espn_teams_response(page1_teams)
        mock_resp1.raise_for_status = MagicMock()

        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = _make_espn_teams_response(page2_teams)
        mock_resp2.raise_for_status = MagicMock()

        mock_session.get.side_effect = [mock_resp1, mock_resp2]

        with patch("precog.api_connectors.espn_team_validator.time.sleep"):
            teams = fetch_espn_teams("nhl", limit=2)

        assert len(teams) == 3
        assert mock_session.get.call_count == 2

    @patch("precog.api_connectors.espn_team_validator.requests.Session")
    def test_session_closed_on_success(self, mock_session_cls):
        """Session should be closed after successful fetch."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = _make_espn_teams_response([])
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        fetch_espn_teams("nfl")

        mock_session.close.assert_called_once()

    @patch("precog.api_connectors.espn_team_validator.requests.Session")
    def test_session_closed_on_error(self, mock_session_cls):
        """Session should be closed even when an error occurs."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_session.get.side_effect = requests.ConnectionError("fail")

        with pytest.raises(requests.ConnectionError):
            fetch_espn_teams("nfl")

        mock_session.close.assert_called_once()


# =============================================================================
# Tests: ESPN-ID-First Team Lookup
# =============================================================================


class TestGetTeamByEspnIdOrCode:
    """Tests for _get_team_by_espn_id_or_code function.

    Educational Note:
        This function has two lookup paths: ESPN ID (primary) and
        team_code+league (fallback). Both must be tested directly
        since integration tests mock this function away.
    """

    @patch("precog.api_connectors.espn_team_validator.fetch_one")
    @patch("precog.api_connectors.espn_team_validator.get_team_by_espn_id")
    def test_espn_id_found_returns_team(self, mock_get_by_espn, mock_fetch_one):
        """Should return team when ESPN ID lookup succeeds."""
        expected = {"team_id": 1, "team_code": "KC", "espn_team_id": "12"}
        mock_get_by_espn.return_value = expected

        result = _get_team_by_espn_id_or_code("12", "KC", "nfl")

        assert result == expected
        mock_get_by_espn.assert_called_once_with("12", league="nfl")
        mock_fetch_one.assert_not_called()

    @patch("precog.api_connectors.espn_team_validator.fetch_one")
    @patch("precog.api_connectors.espn_team_validator.get_team_by_espn_id")
    def test_espn_id_found_with_code_mismatch_logs_warning(
        self, mock_get_by_espn, mock_fetch_one, caplog
    ):
        """Should log warning when ESPN ID matches but DB code differs."""
        mock_get_by_espn.return_value = {
            "team_id": 1,
            "team_code": "WAS",
            "espn_team_id": "28",
        }

        import logging

        with caplog.at_level(logging.WARNING):
            result = _get_team_by_espn_id_or_code("28", "WSH", "nfl")

        assert result is not None
        assert result["team_code"] == "WAS"
        assert "differs" in caplog.text
        mock_fetch_one.assert_not_called()

    @patch("precog.api_connectors.espn_team_validator.fetch_one")
    @patch("precog.api_connectors.espn_team_validator.get_team_by_espn_id")
    def test_fallback_when_espn_id_not_found(self, mock_get_by_espn, mock_fetch_one):
        """Should fall back to code+league when ESPN ID lookup returns None."""
        mock_get_by_espn.return_value = None
        expected = {"team_id": 5, "team_code": "TEST", "espn_team_id": None}
        mock_fetch_one.return_value = expected

        result = _get_team_by_espn_id_or_code("999", "TEST", "nfl")

        assert result == expected
        mock_get_by_espn.assert_called_once_with("999", league="nfl")
        mock_fetch_one.assert_called_once()

    @patch("precog.api_connectors.espn_team_validator.fetch_one")
    @patch("precog.api_connectors.espn_team_validator.get_team_by_espn_id")
    def test_fallback_when_espn_id_empty(self, mock_get_by_espn, mock_fetch_one):
        """Should skip ESPN ID lookup and go straight to fallback when ID is empty."""
        expected = {"team_id": 5, "team_code": "OLD", "espn_team_id": None}
        mock_fetch_one.return_value = expected

        result = _get_team_by_espn_id_or_code("", "OLD", "nfl")

        assert result == expected
        mock_get_by_espn.assert_not_called()
        mock_fetch_one.assert_called_once()

    @patch("precog.api_connectors.espn_team_validator.fetch_one")
    @patch("precog.api_connectors.espn_team_validator.get_team_by_espn_id")
    def test_both_paths_return_none(self, mock_get_by_espn, mock_fetch_one):
        """Should return None when team not found by either method."""
        mock_get_by_espn.return_value = None
        mock_fetch_one.return_value = None

        result = _get_team_by_espn_id_or_code("999", "UNKNOWN", "nfl")

        assert result is None


# =============================================================================
# Tests: League Validation
# =============================================================================


class TestValidateLeagueTeams:
    """Tests for validate_league_teams function."""

    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_detects_espn_id_mismatch(self, mock_fetch, mock_get_team):
        """Should detect when DB has different ESPN ID than API."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        ]
        # DB has wrong ESPN ID for KC
        mock_get_team.return_value = {
            "team_id": 1,
            "team_code": "KC",
            "espn_team_id": "99",  # Wrong!
        }

        result = validate_league_teams("nfl")

        assert result["teams_checked"] == 1
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["db_espn_id"] == "99"
        assert result["mismatches"][0]["api_espn_id"] == "12"

    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_no_mismatch_when_ids_match(self, mock_fetch, mock_get_team):
        """Should report zero mismatches when IDs match."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        ]
        mock_get_team.return_value = {
            "team_id": 1,
            "team_code": "KC",
            "espn_team_id": "12",  # Correct
        }

        result = validate_league_teams("nfl")

        assert result["teams_checked"] == 1
        assert len(result["mismatches"]) == 0

    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_resolves_code_alias_before_lookup(self, mock_fetch, mock_get_team):
        """Should apply code alias when looking up team in DB.

        ESPN uses 'WSH' for Commanders, our DB uses 'WAS'. The validator
        should translate 'WSH' -> 'WAS' before the DB lookup.
        """
        mock_fetch.return_value = [
            {"id": "28", "abbreviation": "WSH", "displayName": "Washington Commanders"},
        ]
        mock_get_team.return_value = {
            "team_id": 5,
            "team_code": "WAS",
            "espn_team_id": "28",
        }

        result = validate_league_teams("nfl")

        # Should have looked up with ESPN ID '28', resolved code 'WAS', league 'nfl'
        mock_get_team.assert_called_with("28", "WAS", "nfl")
        assert result["teams_checked"] == 1
        assert len(result["mismatches"]) == 0

    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_skips_teams_not_in_db(self, mock_fetch, mock_get_team):
        """Should skip teams that are not in our database (not seeded)."""
        mock_fetch.return_value = [
            {"id": "999", "abbreviation": "XYZ", "displayName": "Unknown Team"},
        ]
        mock_get_team.return_value = None  # Not in DB

        result = validate_league_teams("nfl")

        assert result["teams_checked"] == 0
        assert len(result["mismatches"]) == 0

    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_reports_teams_without_espn_id_as_needing_population(self, mock_fetch, mock_get_team):
        """Teams with NULL ESPN ID should be reported as needing population."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        ]
        mock_get_team.return_value = {
            "team_id": 1,
            "team_code": "KC",
            "espn_team_id": None,  # No ESPN ID in DB yet — should be populated
        }

        result = validate_league_teams("nfl")

        assert result["teams_checked"] == 1
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["db_espn_id"] == "(NULL)"
        assert result["mismatches"][0]["api_espn_id"] == "12"

    @patch("precog.api_connectors.espn_team_validator._correct_espn_id")
    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_auto_correct_populates_null_espn_id(self, mock_fetch, mock_get_team, mock_correct):
        """Auto-correct should populate ESPN ID when DB has NULL."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        ]
        mock_get_team.return_value = {
            "team_id": 1,
            "team_code": "KC",
            "espn_team_id": None,
        }

        result = validate_league_teams("nfl", auto_correct=True)

        assert len(result["mismatches"]) == 1
        mock_correct.assert_called_once_with(
            team_id=1,
            team_code="KC",
            league="nfl",
            old_espn_id="",
            new_espn_id="12",
        )

    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_handles_api_network_error_gracefully(self, mock_fetch):
        """Should return error result (not raise) on network failure."""
        mock_fetch.side_effect = requests.ConnectionError("Network down")

        result = validate_league_teams("nfl")

        assert len(result["errors"]) == 1
        assert "Failed to fetch" in result["errors"][0]
        assert result["teams_checked"] == 0

    def test_handles_unsupported_league(self):
        """Should return error for unsupported league code."""
        result = validate_league_teams("cricket")

        assert len(result["errors"]) == 1
        assert "Unsupported league" in result["errors"][0]

    @patch("precog.api_connectors.espn_team_validator._correct_espn_id")
    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_auto_correct_calls_correction(self, mock_fetch, mock_get_team, mock_correct):
        """Should call _correct_espn_id when auto_correct=True and mismatch found."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        ]
        mock_get_team.return_value = {
            "team_id": 1,
            "team_code": "KC",
            "espn_team_id": "99",  # Wrong
        }

        validate_league_teams("nfl", auto_correct=True)

        mock_correct.assert_called_once_with(
            team_id=1,
            team_code="KC",
            league="nfl",
            old_espn_id="99",
            new_espn_id="12",
        )

    @patch("precog.api_connectors.espn_team_validator._correct_espn_id")
    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_no_auto_correct_by_default(self, mock_fetch, mock_get_team, mock_correct):
        """Should NOT call _correct_espn_id when auto_correct=False (default)."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
        ]
        mock_get_team.return_value = {
            "team_id": 1,
            "team_code": "KC",
            "espn_team_id": "99",  # Wrong
        }

        validate_league_teams("nfl", auto_correct=False)

        mock_correct.assert_not_called()

    @patch("precog.api_connectors.espn_team_validator._get_team_by_espn_id_or_code")
    @patch("precog.api_connectors.espn_team_validator.fetch_espn_teams")
    def test_multiple_teams_with_mixed_results(self, mock_fetch, mock_get_team):
        """Should correctly count matches and mismatches across multiple teams."""
        mock_fetch.return_value = [
            {"id": "12", "abbreviation": "KC", "displayName": "Kansas City Chiefs"},
            {"id": "2", "abbreviation": "BUF", "displayName": "Buffalo Bills"},
            {"id": "25", "abbreviation": "SF", "displayName": "San Francisco 49ers"},
        ]

        def side_effect(espn_id, code, league):
            db_teams = {
                "KC": {"team_id": 1, "team_code": "KC", "espn_team_id": "12"},  # match
                "BUF": {"team_id": 2, "team_code": "BUF", "espn_team_id": "99"},  # mismatch
                "SF": {"team_id": 3, "team_code": "SF", "espn_team_id": "25"},  # match
            }
            return db_teams.get(code)

        mock_get_team.side_effect = side_effect

        result = validate_league_teams("nfl")

        assert result["teams_checked"] == 3
        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["team_code"] == "BUF"


# =============================================================================
# Tests: Multi-League Validation
# =============================================================================


class TestValidateESPNTeams:
    """Tests for validate_espn_teams orchestrator function."""

    @patch("precog.api_connectors.espn_team_validator.time.sleep")
    @patch("precog.api_connectors.espn_team_validator.validate_league_teams")
    def test_validates_specified_leagues(self, mock_validate_league, mock_sleep):
        """Should validate only the leagues specified."""
        mock_validate_league.return_value = {
            "league": "nfl",
            "teams_checked": 32,
            "mismatches": [],
            "errors": [],
        }

        result = validate_espn_teams(leagues=["nfl"])

        mock_validate_league.assert_called_once_with(league="nfl", auto_correct=False)
        assert result["total_checked"] == 32
        assert result["total_mismatches"] == 0

    @patch("precog.api_connectors.espn_team_validator.time.sleep")
    @patch("precog.api_connectors.espn_team_validator.validate_league_teams")
    def test_aggregates_results_across_leagues(self, mock_validate_league, mock_sleep):
        """Should sum up totals across multiple leagues."""
        mock_validate_league.side_effect = [
            {
                "league": "nfl",
                "teams_checked": 32,
                "mismatches": [{"team_code": "KC"}],
                "errors": [],
            },
            {
                "league": "nba",
                "teams_checked": 30,
                "mismatches": [],
                "errors": [],
            },
        ]

        result = validate_espn_teams(leagues=["nfl", "nba"])

        assert result["total_checked"] == 62
        assert result["total_mismatches"] == 1
        assert "nfl" in result["leagues"]
        assert "nba" in result["leagues"]

    @patch("precog.api_connectors.espn_team_validator.time.sleep")
    @patch("precog.api_connectors.espn_team_validator.validate_league_teams")
    def test_rate_limits_between_leagues(self, mock_validate_league, mock_sleep):
        """Should sleep 0.5s between league fetches (not before first)."""
        mock_validate_league.return_value = {
            "league": "test",
            "teams_checked": 10,
            "mismatches": [],
            "errors": [],
        }

        validate_espn_teams(leagues=["nfl", "nba", "nhl"])

        # Should sleep between leagues (2 sleeps for 3 leagues)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.5)

    @patch("precog.api_connectors.espn_team_validator.time.sleep")
    @patch("precog.api_connectors.espn_team_validator.validate_league_teams")
    def test_defaults_to_all_leagues(self, mock_validate_league, mock_sleep):
        """Should validate all configured leagues when none specified."""
        mock_validate_league.return_value = {
            "league": "test",
            "teams_checked": 10,
            "mismatches": [],
            "errors": [],
        }

        validate_espn_teams()

        assert mock_validate_league.call_count == len(LEAGUE_CONFIGS)

    @patch("precog.api_connectors.espn_team_validator.time.sleep")
    @patch("precog.api_connectors.espn_team_validator.validate_league_teams")
    def test_skips_unsupported_leagues(self, mock_validate_league, mock_sleep):
        """Should skip leagues not in LEAGUE_CONFIGS."""
        mock_validate_league.return_value = {
            "league": "nfl",
            "teams_checked": 32,
            "mismatches": [],
            "errors": [],
        }

        validate_espn_teams(leagues=["nfl", "cricket"])

        # Only NFL should be validated
        mock_validate_league.assert_called_once()

    @patch("precog.api_connectors.espn_team_validator.time.sleep")
    @patch("precog.api_connectors.espn_team_validator.validate_league_teams")
    def test_passes_auto_correct_flag(self, mock_validate_league, mock_sleep):
        """Should pass auto_correct flag through to league validation."""
        mock_validate_league.return_value = {
            "league": "nfl",
            "teams_checked": 32,
            "mismatches": [],
            "errors": [],
        }

        validate_espn_teams(leagues=["nfl"], auto_correct=True)

        mock_validate_league.assert_called_once_with(league="nfl", auto_correct=True)


# =============================================================================
# Tests: Code Aliases Completeness
# =============================================================================


class TestCodeAliasesCompleteness:
    """Tests to verify CODE_ALIASES mapping integrity."""

    def test_all_configured_leagues_have_alias_entries(self):
        """Every league in LEAGUE_CONFIGS should have a CODE_ALIASES entry."""
        for league in LEAGUE_CONFIGS:
            assert league in CODE_ALIASES, (
                f"League '{league}' is in LEAGUE_CONFIGS but missing from CODE_ALIASES"
            )

    def test_no_identity_aliases(self):
        """Aliases should not map a code to itself (wasteful)."""
        for league, aliases in CODE_ALIASES.items():
            for espn_code, db_code in aliases.items():
                if espn_code == db_code:
                    # JAX -> JAX is documented as intentional, skip it
                    if espn_code == "JAX":
                        continue
                    pytest.fail(
                        f"Identity alias in {league}: '{espn_code}' -> '{db_code}' "
                        f"(remove or document as intentional)"
                    )
