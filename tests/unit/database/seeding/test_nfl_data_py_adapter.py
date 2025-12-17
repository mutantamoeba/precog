"""
Unit Tests for NFL Data Py Source Adapter.

Tests the nfl_data_py adapter for loading NFL historical data.

Related Requirements:
    - REQ-DATA-006: Historical Games Data Seeding
    - REQ-DATA-008: Data Source Adapter Architecture

Related Architecture:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources

Usage:
    pytest tests/unit/database/seeding/test_nfl_data_py_adapter.py -v

Note:
    These tests validate the adapter structure and team code mapping.
    Full integration tests require the nfl_data_py library installed.
"""

from precog.database.seeding.sources.sports.nfl_data_py_adapter import (
    NFL_TEAM_CODE_MAPPING,
    NFLDataPySource,
    normalize_nfl_team_code,
)

# =============================================================================
# Team Code Mapping Tests
# =============================================================================


class TestNflTeamCodeMapping:
    """Test suite for NFL team code normalization."""

    def test_la_rams_mapping(self) -> None:
        """Verify LA is mapped to LAR for Rams."""
        assert normalize_nfl_team_code("LA") == "LAR"

    def test_jacksonville_mapping(self) -> None:
        """Verify JAC is mapped to JAX."""
        assert normalize_nfl_team_code("JAC") == "JAX"

    def test_oakland_to_vegas_mapping(self) -> None:
        """Verify OAK is mapped to LV (Raiders relocation)."""
        assert normalize_nfl_team_code("OAK") == "LV"

    def test_san_diego_to_la_mapping(self) -> None:
        """Verify SD is mapped to LAC (Chargers relocation)."""
        assert normalize_nfl_team_code("SD") == "LAC"

    def test_st_louis_to_la_mapping(self) -> None:
        """Verify STL is mapped to LAR (Rams relocation)."""
        assert normalize_nfl_team_code("STL") == "LAR"

    def test_unmapped_code_passthrough(self) -> None:
        """Verify unmapped codes pass through unchanged."""
        assert normalize_nfl_team_code("KC") == "KC"
        assert normalize_nfl_team_code("BUF") == "BUF"
        assert normalize_nfl_team_code("SF") == "SF"

    def test_case_insensitivity(self) -> None:
        """Verify mapping works regardless of case."""
        assert normalize_nfl_team_code("la") == "LAR"
        assert normalize_nfl_team_code("kc") == "KC"
        assert normalize_nfl_team_code("Sf") == "SF"

    def test_whitespace_handling(self) -> None:
        """Verify mapping handles whitespace."""
        assert normalize_nfl_team_code("  KC  ") == "KC"
        assert normalize_nfl_team_code(" LA ") == "LAR"


# =============================================================================
# NFLDataPySource Class Tests
# =============================================================================


class TestNFLDataPySource:
    """Test suite for NFLDataPySource class."""

    def test_source_name(self) -> None:
        """Verify source_name class attribute."""
        assert NFLDataPySource.source_name == "nfl_data_py"

    def test_supported_sports(self) -> None:
        """Verify supported_sports only includes NFL."""
        assert NFLDataPySource.supported_sports == ["nfl"]

    def test_source_is_subclass_of_base_data_source(self) -> None:
        """Verify NFLDataPySource inherits from BaseDataSource."""
        from precog.database.seeding.sources.base_source import BaseDataSource

        assert issubclass(NFLDataPySource, BaseDataSource)

    def test_source_has_api_mixin(self) -> None:
        """Verify NFLDataPySource includes API-based mixin."""
        from precog.database.seeding.sources.base_source import APIBasedSourceMixin

        assert issubclass(NFLDataPySource, APIBasedSourceMixin)


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

        for old_code, new_code in relocation_mappings.items():
            assert NFL_TEAM_CODE_MAPPING.get(old_code) == new_code
