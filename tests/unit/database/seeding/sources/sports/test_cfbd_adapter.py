"""Unit tests for cfbd_adapter module.

Tests the CFBD (College Football Data) API adapter that fetches
team classification data (FBS/FCS/D2/D3) from the CFBD REST API.

All HTTP calls are mocked -- no real API requests are made.

Reference: Issue #486 - Team code collision fix + division classification
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from precog.database.seeding.sources.base_source import (
    DataSourceConfigError,
    DataSourceConnectionError,
    DataSourceError,
)
from precog.database.seeding.sources.sports.cfbd_adapter import (
    CFBD_API_KEY_ENV,
    CFBD_BASE_URL,
    CFBD_CLASSIFICATION_MAP,
    CFBDSource,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cfbd_source() -> CFBDSource:
    """Create a CFBDSource with an explicit API key (no env var needed)."""
    return CFBDSource(api_key="test-api-key-12345")


@pytest.fixture
def sample_cfbd_teams() -> list[dict]:
    """Sample CFBD /teams response data.

    Includes one team per classification plus edge cases.
    Based on actual CFBD API response structure.
    """
    return [
        {
            "id": 333,
            "school": "Alabama",
            "mascot": "Crimson Tide",
            "abbreviation": "ALA",
            "alt_name_1": None,
            "alt_name_2": None,
            "alt_name_3": None,
            "conference": "SEC",
            "classification": "fbs",
            "color": "#9E1B32",
            "alt_color": "#828A8F",
            "logos": ["https://example.com/alabama.png"],
            "twitter": "@AlabamaFTBL",
            "location": {
                "venue_id": 3657,
                "name": "Bryant-Denny Stadium",
                "city": "Tuscaloosa",
                "state": "AL",
            },
        },
        {
            "id": 2000,
            "school": "Abilene Christian",
            "mascot": "Wildcats",
            "abbreviation": "ACU",
            "conference": "WAC",
            "classification": "fcs",
            "color": "#461D7C",
        },
        {
            "id": 5000,
            "school": "Adams State",
            "mascot": "Grizzlies",
            "abbreviation": None,
            "conference": "RMAC",
            "classification": "ii",
            "color": "#003366",
        },
        {
            "id": 6000,
            "school": "Albion",
            "mascot": "Britons",
            "abbreviation": "ALBI",
            "conference": "MIAA",
            "classification": "iii",
            "color": "#5B2C6F",
        },
        {
            "id": 252,
            "school": "Ohio State",
            "mascot": "Buckeyes",
            "abbreviation": "OSU",
            "conference": "Big Ten",
            "classification": "fbs",
            "color": "#BB0000",
        },
    ]


@pytest.fixture
def mock_response(sample_cfbd_teams: list[dict]) -> MagicMock:
    """Create a mock response that returns sample team data."""
    response = MagicMock(spec=requests.Response)
    response.json.return_value = sample_cfbd_teams
    response.status_code = 200
    response.raise_for_status.return_value = None
    return response


# =============================================================================
# Construction & Configuration Tests
# =============================================================================


class TestCFBDSourceInit:
    """Tests for CFBDSource initialization and configuration."""

    def test_source_name_is_cfbd(self, cfbd_source: CFBDSource) -> None:
        """Verify source identifies as cfbd."""
        assert cfbd_source.source_name == "cfbd"

    def test_supported_sports_is_ncaaf(self, cfbd_source: CFBDSource) -> None:
        """Verify only ncaaf is supported."""
        assert cfbd_source.supports_sport("ncaaf") is True
        assert cfbd_source.supports_sport("nfl") is False
        assert cfbd_source.supports_sport("nba") is False

    def test_explicit_api_key_stored(self) -> None:
        """Verify explicit api_key is used over env var."""
        source = CFBDSource(api_key="explicit-key")
        assert source._api_key == "explicit-key"

    def test_env_var_api_key_fallback(self) -> None:
        """Verify falls back to CFBD_API_KEY env var when no explicit key."""
        with patch.dict("os.environ", {CFBD_API_KEY_ENV: "env-key"}):
            source = CFBDSource()
            assert source._api_key == "env-key"

    def test_no_api_key_allows_construction(self) -> None:
        """Verify construction succeeds without a key (fails at request time)."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove env var if present
            source = CFBDSource(api_key=None)
            # Construction succeeds, but _api_key is None/empty
            assert source._api_key is None or source._api_key == ""


# =============================================================================
# API Key Validation Tests
# =============================================================================


class TestAPIKeyValidation:
    """Tests for API key validation behavior."""

    def test_ensure_api_key_returns_key_when_present(self, cfbd_source: CFBDSource) -> None:
        """Verify _ensure_api_key returns the key when configured."""
        key = cfbd_source._ensure_api_key()
        assert key == "test-api-key-12345"

    def test_ensure_api_key_raises_without_key(self) -> None:
        """Verify _ensure_api_key raises DataSourceConfigError when no key."""
        source = CFBDSource(api_key=None)
        source._api_key = None  # Ensure it's truly None

        with pytest.raises(DataSourceConfigError, match="CFBD API key not configured"):
            source._ensure_api_key()

    def test_config_error_message_includes_env_var_name(self) -> None:
        """Verify error message tells user which env var to set."""
        source = CFBDSource(api_key=None)
        source._api_key = None

        with pytest.raises(DataSourceConfigError, match=CFBD_API_KEY_ENV):
            source._ensure_api_key()


# =============================================================================
# Session Management Tests
# =============================================================================


class TestSessionManagement:
    """Tests for HTTP session creation and cleanup."""

    def test_get_session_creates_session_with_bearer_auth(self, cfbd_source: CFBDSource) -> None:
        """Verify session includes Bearer token in Authorization header."""
        session = cfbd_source._get_session()
        assert session.headers["Authorization"] == "Bearer test-api-key-12345"
        assert session.headers["Accept"] == "application/json"
        cfbd_source.close()

    def test_get_session_reuses_existing_session(self, cfbd_source: CFBDSource) -> None:
        """Verify same session object is returned on subsequent calls."""
        session1 = cfbd_source._get_session()
        session2 = cfbd_source._get_session()
        assert session1 is session2
        cfbd_source.close()

    def test_close_clears_session(self, cfbd_source: CFBDSource) -> None:
        """Verify close() releases the session."""
        _ = cfbd_source._get_session()
        assert cfbd_source._session is not None
        cfbd_source.close()
        assert cfbd_source._session is None

    def test_close_is_idempotent(self, cfbd_source: CFBDSource) -> None:
        """Verify close() can be called multiple times safely."""
        cfbd_source.close()
        cfbd_source.close()  # Should not raise


# =============================================================================
# Classification Mapping Tests
# =============================================================================


class TestClassificationMapping:
    """Tests for CFBD classification value mapping."""

    def test_fbs_maps_to_fbs(self) -> None:
        """Verify 'fbs' maps to 'fbs'."""
        assert CFBD_CLASSIFICATION_MAP["fbs"] == "fbs"

    def test_fcs_maps_to_fcs(self) -> None:
        """Verify 'fcs' maps to 'fcs'."""
        assert CFBD_CLASSIFICATION_MAP["fcs"] == "fcs"

    def test_ii_maps_to_d2(self) -> None:
        """Verify 'ii' (Division II) maps to 'd2'."""
        assert CFBD_CLASSIFICATION_MAP["ii"] == "d2"

    def test_iii_maps_to_d3(self) -> None:
        """Verify 'iii' (Division III) maps to 'd3'."""
        assert CFBD_CLASSIFICATION_MAP["iii"] == "d3"

    def test_all_expected_classifications_present(self) -> None:
        """Verify all four CFBD classification values are mapped."""
        expected = {"fbs", "fcs", "ii", "iii"}
        assert set(CFBD_CLASSIFICATION_MAP.keys()) == expected


# =============================================================================
# get_team_classifications() Tests
# =============================================================================


class TestGetTeamClassifications:
    """Tests for the primary get_team_classifications() method."""

    def test_returns_list_of_team_classifications(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify returns a list of TeamClassification dicts."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            teams = cfbd_source.get_team_classifications()

        assert isinstance(teams, list)
        assert len(teams) == 5
        for team in teams:
            assert "school" in team
            assert "abbreviation" in team
            assert "conference" in team
            assert "classification" in team

    def test_fbs_team_classification(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify FBS teams get classification='fbs'."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            teams = cfbd_source.get_team_classifications()

        alabama = next(t for t in teams if t["school"] == "Alabama")
        assert alabama["classification"] == "fbs"
        assert alabama["abbreviation"] == "ALA"
        assert alabama["conference"] == "SEC"

    def test_fcs_team_classification(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify FCS teams get classification='fcs'."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            teams = cfbd_source.get_team_classifications()

        acu = next(t for t in teams if t["school"] == "Abilene Christian")
        assert acu["classification"] == "fcs"
        assert acu["conference"] == "WAC"

    def test_division_ii_mapped_to_d2(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify Division II ('ii') is mapped to 'd2'."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            teams = cfbd_source.get_team_classifications()

        adams = next(t for t in teams if t["school"] == "Adams State")
        assert adams["classification"] == "d2"

    def test_division_iii_mapped_to_d3(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify Division III ('iii') is mapped to 'd3'."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            teams = cfbd_source.get_team_classifications()

        albion = next(t for t in teams if t["school"] == "Albion")
        assert albion["classification"] == "d3"

    def test_null_abbreviation_preserved(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify teams without abbreviation get None."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            teams = cfbd_source.get_team_classifications()

        adams = next(t for t in teams if t["school"] == "Adams State")
        assert adams["abbreviation"] is None

    def test_skips_teams_without_classification(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify teams with no classification field are skipped."""
        response = MagicMock(spec=requests.Response)
        response.json.return_value = [
            {"school": "Club Team", "abbreviation": "CLB", "conference": None},
            {
                "school": "Real Team",
                "abbreviation": "RT",
                "conference": "Big Ten",
                "classification": "fbs",
            },
        ]
        response.status_code = 200
        response.raise_for_status.return_value = None

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = response
            teams = cfbd_source.get_team_classifications()

        assert len(teams) == 1
        assert teams[0]["school"] == "Real Team"

    def test_skips_unknown_classification_values(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify unknown classification values are skipped with warning."""
        response = MagicMock(spec=requests.Response)
        response.json.return_value = [
            {
                "school": "Mystery U",
                "abbreviation": "MYS",
                "conference": "Unknown",
                "classification": "naia",  # Not in our mapping
            },
            {
                "school": "Normal U",
                "abbreviation": "NRM",
                "conference": "SEC",
                "classification": "fbs",
            },
        ]
        response.status_code = 200
        response.raise_for_status.return_value = None

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = response
            teams = cfbd_source.get_team_classifications()

        assert len(teams) == 1
        assert teams[0]["school"] == "Normal U"

    def test_empty_response_returns_empty_list(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify empty API response returns empty list."""
        response = MagicMock(spec=requests.Response)
        response.json.return_value = []
        response.status_code = 200
        response.raise_for_status.return_value = None

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = response
            teams = cfbd_source.get_team_classifications()

        assert teams == []

    def test_non_list_response_raises_error(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify non-list response raises DataSourceError."""
        response = MagicMock(spec=requests.Response)
        response.json.return_value = {"error": "something"}
        response.status_code = 200
        response.raise_for_status.return_value = None

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = response
            with pytest.raises(DataSourceError, match="unexpected type"):
                cfbd_source.get_team_classifications()

    def test_classification_case_insensitive(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify classification mapping is case-insensitive."""
        response = MagicMock(spec=requests.Response)
        response.json.return_value = [
            {
                "school": "Upper Case U",
                "abbreviation": "UCU",
                "conference": "SEC",
                "classification": "FBS",  # Uppercase
            },
            {
                "school": "Mixed Case U",
                "abbreviation": "MCU",
                "conference": "ACC",
                "classification": "Fcs",  # Mixed case
            },
        ]
        response.status_code = 200
        response.raise_for_status.return_value = None

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = response
            teams = cfbd_source.get_team_classifications()

        assert len(teams) == 2
        assert teams[0]["classification"] == "fbs"
        assert teams[1]["classification"] == "fcs"

    def test_empty_abbreviation_becomes_none(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify empty string abbreviation is normalized to None."""
        response = MagicMock(spec=requests.Response)
        response.json.return_value = [
            {
                "school": "Blank Abbrev U",
                "abbreviation": "",
                "conference": "WAC",
                "classification": "fcs",
            },
        ]
        response.status_code = 200
        response.raise_for_status.return_value = None

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = response
            teams = cfbd_source.get_team_classifications()

        assert len(teams) == 1
        assert teams[0]["abbreviation"] is None

    def test_calls_correct_endpoint(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify the /teams endpoint is called."""
        with patch.object(cfbd_source, "_request", return_value=[]) as mock_req:
            cfbd_source.get_team_classifications()
            mock_req.assert_called_once_with("/teams")


# =============================================================================
# HTTP Request Error Handling Tests
# =============================================================================


class TestHTTPErrorHandling:
    """Tests for HTTP error handling in _request()."""

    def test_timeout_raises_connection_error(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify timeout raises DataSourceConnectionError."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.side_effect = requests.exceptions.Timeout(
                "Connection timed out"
            )
            with pytest.raises(DataSourceConnectionError, match="timed out"):
                cfbd_source._request("/teams")

    def test_401_raises_auth_error(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify 401 response raises auth-specific error."""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 401

        http_error = requests.exceptions.HTTPError(response=mock_resp)

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_resp
            mock_resp.raise_for_status.side_effect = http_error

            with pytest.raises(DataSourceConnectionError, match="authentication failed"):
                cfbd_source._request("/teams")

    def test_500_raises_connection_error(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify 500 response raises DataSourceConnectionError."""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500

        http_error = requests.exceptions.HTTPError(response=mock_resp)

        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_resp
            mock_resp.raise_for_status.side_effect = http_error

            with pytest.raises(DataSourceConnectionError, match="HTTP error 500"):
                cfbd_source._request("/teams")

    def test_network_error_raises_connection_error(
        self,
        cfbd_source: CFBDSource,
    ) -> None:
        """Verify general network errors raise DataSourceConnectionError."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.side_effect = requests.exceptions.ConnectionError(
                "DNS resolution failed"
            )
            with pytest.raises(DataSourceConnectionError, match="connection error"):
                cfbd_source._request("/teams")

    def test_request_passes_params(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify query parameters are forwarded to the HTTP call."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            cfbd_source._request("/games", params={"year": 2023})

            mock_session.return_value.get.assert_called_once()
            call_kwargs = mock_session.return_value.get.call_args
            assert call_kwargs.kwargs.get("params") == {"year": 2023} or (
                call_kwargs[1].get("params") == {"year": 2023}
            )

    def test_request_uses_correct_base_url(
        self,
        cfbd_source: CFBDSource,
        mock_response: MagicMock,
    ) -> None:
        """Verify requests go to the CFBD base URL."""
        with patch.object(cfbd_source, "_get_session") as mock_session:
            mock_session.return_value.get.return_value = mock_response
            cfbd_source._request("/teams")

            call_args = mock_session.return_value.get.call_args
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
            assert url == f"{CFBD_BASE_URL}/teams"


# =============================================================================
# Game Loading Stub Tests
# =============================================================================


class TestLoadGamesStub:
    """Tests for the stubbed load_games() method."""

    def test_load_games_raises_not_implemented(self, cfbd_source: CFBDSource) -> None:
        """Verify load_games() raises NotImplementedError with helpful message."""
        with pytest.raises(NotImplementedError, match="#487"):
            list(cfbd_source.load_games())

    def test_load_games_error_mentions_alternative(self, cfbd_source: CFBDSource) -> None:
        """Verify error message suggests get_team_classifications()."""
        with pytest.raises(NotImplementedError, match="get_team_classifications"):
            list(cfbd_source.load_games())


# =============================================================================
# Capability Tests
# =============================================================================


class TestCapabilities:
    """Tests for capability discovery methods."""

    def test_supports_games_false(self, cfbd_source: CFBDSource) -> None:
        """Verify games not yet supported (until #487)."""
        assert cfbd_source.supports_games() is False

    def test_supports_odds_false(self, cfbd_source: CFBDSource) -> None:
        """Verify odds not supported."""
        assert cfbd_source.supports_odds() is False

    def test_supports_elo_false(self, cfbd_source: CFBDSource) -> None:
        """Verify Elo not supported (we compute our own)."""
        assert cfbd_source.supports_elo() is False

    def test_supports_stats_false(self, cfbd_source: CFBDSource) -> None:
        """Verify stats not supported."""
        assert cfbd_source.supports_stats() is False

    def test_supports_rankings_false(self, cfbd_source: CFBDSource) -> None:
        """Verify rankings not supported."""
        assert cfbd_source.supports_rankings() is False

    def test_name_property(self, cfbd_source: CFBDSource) -> None:
        """Verify name property returns source_name."""
        assert cfbd_source.name == "cfbd"
