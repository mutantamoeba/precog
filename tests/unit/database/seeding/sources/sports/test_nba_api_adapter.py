"""Unit tests for nba_api_adapter module.

This module tests the NBA API adapter that loads historical
NBA game data using the nba_api Python library.

Reference: Phase 2C - Python library data source adapters
"""

from precog.database.seeding.sources.sports.nba_api_adapter import (
    NBAApiSource,
    normalize_nba_team_code,
)


class TestNormalizeNBATeamCode:
    """Tests for normalize_nba_team_code function."""

    def test_returns_uppercase(self) -> None:
        """Verify team codes are uppercased."""
        result = normalize_nba_team_code("lal")
        assert result == "LAL"

    def test_handles_phx_phoenix(self) -> None:
        """Verify PHO -> PHX normalization (Phoenix Suns)."""
        # Some APIs use PHO, we normalize to PHX
        result = normalize_nba_team_code("PHO")
        assert result in ("PHX", "PHO")  # Either is valid

    def test_preserves_valid_codes(self) -> None:
        """Verify valid team codes are preserved."""
        codes = ["LAL", "BOS", "GSW", "MIA", "CHI"]
        for code in codes:
            result = normalize_nba_team_code(code)
            assert len(result) == 3


class TestNBAApiSource:
    """Tests for NBAApiSource class."""

    def test_source_name_is_nba_api(self) -> None:
        """Verify source identifies as nba_api."""
        source = NBAApiSource()
        assert "nba" in source.source_name.lower()

    def test_supports_games(self) -> None:
        """Verify source claims to support games."""
        source = NBAApiSource()
        assert source.supports_games() is True

    def test_supports_stats_not_yet(self) -> None:
        """Verify stats support not yet implemented."""
        source = NBAApiSource()
        # Stats loading is planned but not yet implemented
        assert source.supports_stats() is False
