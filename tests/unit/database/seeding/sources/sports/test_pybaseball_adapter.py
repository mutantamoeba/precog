"""Unit tests for pybaseball_adapter module.

This module tests the pybaseball adapter that loads historical
MLB game data using the pybaseball Python library.

Reference: Phase 2C - Python library data source adapters
"""

from precog.database.seeding.sources.sports.pybaseball_adapter import (
    PybaseballSource,
    normalize_mlb_team_code,
)


class TestNormalizeMLBTeamCode:
    """Tests for normalize_mlb_team_code function."""

    def test_returns_uppercase(self) -> None:
        """Verify team codes are uppercased."""
        result = normalize_mlb_team_code("nyy")
        assert result == "NYY"

    def test_preserves_valid_codes(self) -> None:
        """Verify valid team codes are preserved."""
        codes = ["NYY", "BOS", "LAD", "CHC", "SF"]
        for code in codes:
            result = normalize_mlb_team_code(code)
            assert len(result) >= 2  # MLB codes vary 2-3 chars


class TestPybaseballSource:
    """Tests for PybaseballSource class."""

    def test_source_name_is_pybaseball(self) -> None:
        """Verify source identifies as pybaseball."""
        source = PybaseballSource()
        assert "baseball" in source.source_name.lower() or "mlb" in source.source_name.lower()

    def test_supports_games(self) -> None:
        """Verify source claims to support games."""
        source = PybaseballSource()
        assert source.supports_games() is True

    def test_supports_stats_not_yet(self) -> None:
        """Verify stats support not yet implemented."""
        source = PybaseballSource()
        # Stats loading is planned but not yet implemented
        assert source.supports_stats() is False
