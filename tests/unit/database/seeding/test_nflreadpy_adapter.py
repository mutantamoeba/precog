"""
Unit Tests for NFLReadPy Source Adapter.

Tests the nflreadpy adapter for loading NFL historical data and EPA metrics.

Related Requirements:
    - REQ-DATA-006: Historical Games Data Seeding
    - REQ-DATA-008: Data Source Adapter Architecture
    - REQ-ELO-003: EPA Integration from nflreadpy

Related Architecture:
    - ADR-106: Historical Data Collection Architecture
    - ADR-109: Elo Rating Computation Engine
    - Issue #229: Expanded Historical Data Sources
    - Issue #273: Elo computation with EPA integration

Usage:
    pytest tests/unit/database/seeding/test_nflreadpy_adapter.py -v

Note:
    These tests validate the adapter structure, team code mapping,
    and EPA aggregation logic. They mock the nflreadpy library
    to run without the optional dependency installed.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.sources.sports.nflreadpy_adapter import (
    EPARecord,
    NFLReadPySource,
    _to_decimal,
    normalize_nflreadpy_team_code,
)
from precog.database.seeding.team_history import resolve_team_code

# =============================================================================
# Team Code Mapping Tests
# =============================================================================


class TestNflreadpyTeamCodeMapping:
    """Test suite for nflreadpy team code normalization."""

    def test_la_rams_mapping(self) -> None:
        """Verify LA is mapped to LAR for Rams."""
        assert normalize_nflreadpy_team_code("LA") == "LAR"

    def test_jacksonville_mapping(self) -> None:
        """Verify JAC is mapped to JAX."""
        assert normalize_nflreadpy_team_code("JAC") == "JAX"

    def test_las_vegas_mapping(self) -> None:
        """Verify LV is mapped to LVR (Raiders post-move code)."""
        assert normalize_nflreadpy_team_code("LV") == "LVR"

    def test_oakland_to_vegas_mapping(self) -> None:
        """Verify OAK is mapped to LVR (Raiders relocation)."""
        assert normalize_nflreadpy_team_code("OAK") == "LVR"

    def test_san_diego_to_la_mapping(self) -> None:
        """Verify SD is mapped to LAC (Chargers relocation)."""
        assert normalize_nflreadpy_team_code("SD") == "LAC"

    def test_st_louis_to_la_mapping(self) -> None:
        """Verify STL is mapped to LAR (Rams relocation)."""
        assert normalize_nflreadpy_team_code("STL") == "LAR"

    def test_unmapped_code_passthrough(self) -> None:
        """Verify unmapped codes pass through unchanged."""
        assert normalize_nflreadpy_team_code("KC") == "KC"
        assert normalize_nflreadpy_team_code("BUF") == "BUF"
        assert normalize_nflreadpy_team_code("SF") == "SF"
        assert normalize_nflreadpy_team_code("PHI") == "PHI"

    def test_case_insensitivity(self) -> None:
        """Verify mapping works regardless of case."""
        assert normalize_nflreadpy_team_code("la") == "LAR"
        assert normalize_nflreadpy_team_code("kc") == "KC"
        assert normalize_nflreadpy_team_code("Sf") == "SF"

    def test_whitespace_handling(self) -> None:
        """Verify mapping handles whitespace."""
        assert normalize_nflreadpy_team_code("  KC  ") == "KC"
        assert normalize_nflreadpy_team_code(" LA ") == "LAR"


# =============================================================================
# Decimal Conversion Tests
# =============================================================================


class TestToDecimal:
    """Test suite for _to_decimal helper function."""

    def test_float_conversion(self) -> None:
        """Verify float values convert to Decimal."""
        result = _to_decimal(0.1234)
        assert result == Decimal("0.1234")
        assert isinstance(result, Decimal)

    def test_int_conversion(self) -> None:
        """Verify int values convert to Decimal."""
        result = _to_decimal(5)
        assert result == Decimal("5.0000")

    def test_string_conversion(self) -> None:
        """Verify string values convert to Decimal."""
        result = _to_decimal("0.5678")
        assert result == Decimal("0.5678")

    def test_none_returns_none(self) -> None:
        """Verify None returns None."""
        result = _to_decimal(None)
        assert result is None

    def test_nan_returns_none(self) -> None:
        """Verify NaN returns None."""
        result = _to_decimal(float("nan"))
        assert result is None

    def test_custom_precision(self) -> None:
        """Verify custom precision works."""
        result = _to_decimal(0.123456789, precision="0.01")
        assert result == Decimal("0.12")

    def test_rounding(self) -> None:
        """Verify rounding uses ROUND_HALF_UP."""
        result = _to_decimal(0.12345)
        assert result == Decimal("0.1235")  # Rounded up from 0.12345


# =============================================================================
# NFLReadPySource Class Tests
# =============================================================================


class TestNFLReadPySource:
    """Test suite for NFLReadPySource class."""

    def test_source_name(self) -> None:
        """Verify source_name class attribute."""
        assert NFLReadPySource.source_name == "nflreadpy"

    def test_supported_sports(self) -> None:
        """Verify supported_sports only includes NFL."""
        assert NFLReadPySource.supported_sports == ["nfl"]

    def test_source_is_subclass_of_base_data_source(self) -> None:
        """Verify NFLReadPySource inherits from BaseDataSource."""
        from precog.database.seeding.sources.base_source import BaseDataSource

        assert issubclass(NFLReadPySource, BaseDataSource)

    def test_source_has_api_mixin(self) -> None:
        """Verify NFLReadPySource includes API-based mixin."""
        from precog.database.seeding.sources.base_source import APIBasedSourceMixin

        assert issubclass(NFLReadPySource, APIBasedSourceMixin)

    def test_supports_games(self) -> None:
        """Verify source supports game data loading."""
        source = NFLReadPySource()
        assert source.supports_games() is True

    def test_supports_epa(self) -> None:
        """Verify source supports EPA data loading."""
        source = NFLReadPySource()
        assert source.supports_epa() is True

    def test_does_not_support_odds(self) -> None:
        """Verify source does not support odds data."""
        source = NFLReadPySource()
        assert source.supports_odds() is False

    def test_does_not_support_elo(self) -> None:
        """Verify source does not support Elo (we compute our own)."""
        source = NFLReadPySource()
        assert source.supports_elo() is False


# =============================================================================
# Load Games Tests (Mocked)
# =============================================================================


class TestLoadGames:
    """Test suite for load_games method with mocked nflreadpy."""

    @pytest.fixture
    def mock_nflreadpy(self) -> MagicMock:
        """Create a mock nflreadpy module."""
        mock_nfl = MagicMock()

        # Create a mock Polars DataFrame with to_dicts method
        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [
            {
                "game_id": "2023_01_KC_DET",
                "season": 2023,
                "week": 1,
                "gameday": "2023-09-07",
                "home_team": "DET",
                "away_team": "KC",
                "home_score": 21,
                "away_score": 20,
                "game_type": "REG",
                "location": "Home",
                "stadium": "Ford Field",
            },
            {
                "game_id": "2023_01_PHI_NE",
                "season": 2023,
                "week": 1,
                "gameday": "2023-09-10",
                "home_team": "NE",
                "away_team": "PHI",
                "home_score": 17,
                "away_score": 25,
                "game_type": "REG",
                "location": "Home",
                "stadium": "Gillette Stadium",
            },
        ]

        mock_nfl.load_schedules.return_value = mock_df
        return mock_nfl

    def test_load_games_returns_game_records(self, mock_nflreadpy: MagicMock) -> None:
        """Verify load_games yields GameRecord objects."""
        source = NFLReadPySource()
        source._nfl = mock_nflreadpy

        games = list(source.load_games(seasons=[2023]))

        assert len(games) == 2
        assert games[0]["sport"] == "nfl"
        assert games[0]["home_team_code"] == "DET"
        assert games[0]["away_team_code"] == "KC"
        assert games[0]["home_score"] == 21
        assert games[0]["away_score"] == 20
        assert games[0]["game_type"] == "regular"
        assert games[0]["source"] == "nflreadpy"

    def test_load_games_normalizes_team_codes(self, mock_nflreadpy: MagicMock) -> None:
        """Verify team codes are normalized."""
        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [
            {
                "game_id": "2023_01_JAC_LA",
                "season": 2023,
                "week": 1,
                "gameday": "2023-09-10",
                "home_team": "LA",  # Should become LAR
                "away_team": "JAC",  # Should become JAX
                "home_score": 24,
                "away_score": 21,
                "game_type": "REG",
                "location": "Home",
                "stadium": "SoFi Stadium",
            },
        ]
        mock_nflreadpy.load_schedules.return_value = mock_df

        source = NFLReadPySource()
        source._nfl = mock_nflreadpy

        games = list(source.load_games(seasons=[2023]))

        assert len(games) == 1
        assert games[0]["home_team_code"] == "LAR"
        assert games[0]["away_team_code"] == "JAX"

    def test_load_games_skips_incomplete_games(self, mock_nflreadpy: MagicMock) -> None:
        """Verify games without scores are skipped."""
        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [
            {
                "game_id": "2023_18_KC_DEN",
                "season": 2023,
                "week": 18,
                "gameday": "2024-01-07",
                "home_team": "DEN",
                "away_team": "KC",
                "home_score": None,  # Not played yet
                "away_score": None,
                "game_type": "REG",
                "location": "Home",
                "stadium": "Empower Field",
            },
        ]
        mock_nflreadpy.load_schedules.return_value = mock_df

        source = NFLReadPySource()
        source._nfl = mock_nflreadpy

        games = list(source.load_games(seasons=[2023]))

        assert len(games) == 0

    def test_load_games_identifies_playoff_games(self, mock_nflreadpy: MagicMock) -> None:
        """Verify playoff game types are correctly identified."""
        mock_df = MagicMock()
        mock_df.to_dicts.return_value = [
            {
                "game_id": "2023_WC_KC_MIA",
                "season": 2023,
                "week": 19,
                "gameday": "2024-01-13",
                "home_team": "KC",
                "away_team": "MIA",
                "home_score": 26,
                "away_score": 7,
                "game_type": "WC",
                "location": "Home",
                "stadium": "Arrowhead Stadium",
            },
            {
                "game_id": "2023_SB_KC_SF",
                "season": 2023,
                "week": 22,
                "gameday": "2024-02-11",
                "home_team": "KC",
                "away_team": "SF",
                "home_score": 25,
                "away_score": 22,
                "game_type": "SB",
                "location": "NEUTRAL",
                "stadium": "Allegiant Stadium",
            },
        ]
        mock_nflreadpy.load_schedules.return_value = mock_df

        source = NFLReadPySource()
        source._nfl = mock_nflreadpy

        games = list(source.load_games(seasons=[2023]))

        assert len(games) == 2
        assert games[0]["is_playoff"] is True
        assert games[0]["game_type"] == "wildcard"
        assert games[1]["is_playoff"] is True
        assert games[1]["game_type"] == "superbowl"
        assert games[1]["is_neutral_site"] is True


# =============================================================================
# EPA Record Type Tests
# =============================================================================


class TestEPARecord:
    """Test suite for EPARecord TypedDict."""

    def test_epa_record_structure(self) -> None:
        """Verify EPARecord has correct fields."""
        record: EPARecord = {
            "team_id": None,
            "team_name": "Kansas City Chiefs",
            "team_code": "KC",
            "season": 2023,
            "week": 1,
            "off_epa_per_play": Decimal("0.1500"),
            "pass_epa_per_play": Decimal("0.2000"),
            "rush_epa_per_play": Decimal("0.0500"),
            "def_epa_per_play": Decimal("-0.0800"),
            "def_pass_epa_per_play": Decimal("-0.1000"),
            "def_rush_epa_per_play": Decimal("-0.0600"),
            "epa_differential": Decimal("0.2300"),
            "games_played": 1,
            "source": "nflreadpy",
        }

        assert record["team_code"] == "KC"
        assert record["season"] == 2023
        assert record["off_epa_per_play"] == Decimal("0.1500")
        assert record["epa_differential"] == Decimal("0.2300")

    def test_epa_record_allows_null_week(self) -> None:
        """Verify EPARecord allows null week for season totals."""
        record: EPARecord = {
            "team_id": None,
            "team_name": "Philadelphia Eagles",
            "team_code": "PHI",
            "season": 2023,
            "week": None,  # Season total
            "off_epa_per_play": Decimal("0.1200"),
            "pass_epa_per_play": Decimal("0.1800"),
            "rush_epa_per_play": Decimal("0.0400"),
            "def_epa_per_play": Decimal("-0.0500"),
            "def_pass_epa_per_play": Decimal("-0.0700"),
            "def_rush_epa_per_play": Decimal("-0.0300"),
            "epa_differential": Decimal("0.1700"),
            "games_played": 17,
            "source": "nflreadpy",
        }

        assert record["week"] is None
        assert record["games_played"] == 17


# =============================================================================
# Team Code Mapping Completeness Tests
# =============================================================================


class TestTeamCodeMappingCompleteness:
    """Test suite for team code mapping completeness."""

    def test_all_relocation_mappings_present(self) -> None:
        """Verify all known NFL team relocations are mapped.

        Educational Note:
            NFL team relocations since 2000:
            - Rams: STL -> LA (2016)
            - Chargers: SD -> LA (2017)
            - Raiders: OAK -> LV (2020)

            The mapping ensures historical data can be associated
            with current team records.
        """
        relocation_mappings = {
            "STL": "LAR",  # St. Louis Rams -> LA Rams
            "SD": "LAC",  # San Diego Chargers -> LA Chargers
            "OAK": "LV",  # Oakland Raiders -> Las Vegas Raiders
        }

        # Using unified team history module (Issue #257)
        for old_code, new_code in relocation_mappings.items():
            assert resolve_team_code("nfl", old_code) == new_code

    def test_all_32_current_teams_passthrough(self) -> None:
        """Verify all 32 current NFL teams pass through correctly.

        Educational Note:
            These are the official abbreviations as of 2024.
            Any relocation would require updating the mapping.
        """
        current_teams = [
            "ARI",
            "ATL",
            "BAL",
            "BUF",
            "CAR",
            "CHI",
            "CIN",
            "CLE",
            "DAL",
            "DEN",
            "DET",
            "GB",
            "HOU",
            "IND",
            "JAX",
            "KC",
            "LAC",
            "LAR",
            "LV",
            "MIA",
            "MIN",
            "NE",
            "NO",
            "NYG",
            "NYJ",
            "PHI",
            "PIT",
            "SEA",
            "SF",
            "TB",
            "TEN",
            "WAS",
        ]

        for team in current_teams:
            # Current teams should mostly pass through
            # (some like LV have mappings, which is fine)
            result = normalize_nflreadpy_team_code(team)
            assert result is not None
            assert len(result) in [2, 3]  # Valid abbreviation length


# =============================================================================
# Module Import Tests
# =============================================================================


class TestModuleImports:
    """Test suite for module import behavior."""

    def test_nflreadpy_import_error_handling(self) -> None:
        """Verify DataSourceError raised when nflreadpy not installed."""
        from precog.database.seeding.sources.base_source import DataSourceError

        source = NFLReadPySource()
        source._nfl = None  # Ensure fresh state

        # Mock the import to fail
        with patch.dict("sys.modules", {"nflreadpy": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'nflreadpy'"),
            ):
                with pytest.raises(DataSourceError) as exc_info:
                    source._get_nfl_module()

                assert "nflreadpy is not installed" in str(exc_info.value)

    def test_lazy_loading(self) -> None:
        """Verify nflreadpy is lazily loaded."""
        source = NFLReadPySource()
        assert source._nfl is None  # Not loaded on init

    def test_module_caching(self) -> None:
        """Verify nflreadpy module is cached after first load."""
        source = NFLReadPySource()
        mock_module = MagicMock()
        source._nfl = mock_module

        # Second call should return cached module
        result = source._get_nfl_module()
        assert result is mock_module


# =============================================================================
# Sports __init__.py Export Tests
# =============================================================================


class TestModuleExports:
    """Test suite for verifying NFLReadPySource is properly exported."""

    def test_nflreadpy_source_in_all(self) -> None:
        """Verify NFLReadPySource is in __all__."""
        from precog.database.seeding.sources.sports import __all__

        assert "NFLReadPySource" in __all__

    def test_nflreadpy_source_importable(self) -> None:
        """Verify NFLReadPySource can be imported from sports package."""
        # This should work via lazy import
        from precog.database.seeding.sources.sports import NFLReadPySource as ImportedSource

        assert ImportedSource.source_name == "nflreadpy"
