"""Unit tests for nhl_api_adapter module.

This module tests the NHL API adapter that loads historical
NHL game data using the nhl-api-py Python library.

Reference: Phase 2C - Python library data source adapters
"""

from precog.database.seeding.sources.sports.nhl_api_adapter import (
    NHLApiSource,
    normalize_nhl_team_code,
)


class TestNormalizeNHLTeamCode:
    """Tests for normalize_nhl_team_code function."""

    def test_returns_uppercase(self) -> None:
        """Verify team codes are uppercased."""
        result = normalize_nhl_team_code("bos")
        assert result == "BOS"

    def test_preserves_valid_codes(self) -> None:
        """Verify valid team codes are preserved."""
        codes = ["BOS", "NYR", "TOR", "MTL", "CHI"]
        for code in codes:
            result = normalize_nhl_team_code(code)
            assert len(result) == 3


class TestNHLApiSource:
    """Tests for NHLApiSource class."""

    def test_source_name_is_nhl(self) -> None:
        """Verify source identifies as nhl."""
        source = NHLApiSource()
        assert "nhl" in source.source_name.lower()

    def test_supports_games(self) -> None:
        """Verify source claims to support games."""
        source = NHLApiSource()
        assert source.supports_games() is True

    def test_supports_stats_not_yet(self) -> None:
        """Verify stats support not yet implemented."""
        source = NHLApiSource()
        # Stats loading is planned but not yet implemented
        assert source.supports_stats() is False
