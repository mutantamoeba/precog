"""
Unit Tests for NFL Data Py Source Adapter.

Tests the NFLDataPySource adapter for loading player/team statistics
from the nfl_data_py library.

Tests follow the project's testing patterns:
- Pattern 7: Educational docstrings
- Pattern 8: Mocking external dependencies

Related Requirements:
- REQ-DATA-005 through REQ-DATA-008: Historical data requirements

Related Architecture:
- ADR-106: Historical Data Collection Architecture
- Issue #236: StatsRecord/RankingRecord Infrastructure

Usage:
    pytest tests/unit/database/seeding/test_nfl_data_py_source.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from precog.database.seeding.sources.base_source import (
    DataSourceConfigError,
)


class TestNFLDataPySourceImport:
    """Test NFLDataPySource import and initialization."""

    def test_can_import_source_class(self) -> None:
        """Verify NFLDataPySource can be imported."""
        from precog.database.seeding.sources import NFLDataPySource

        assert NFLDataPySource is not None

    def test_source_name_is_nfl_data_py(self) -> None:
        """Verify source_name is correctly set."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.source_name == "nfl_data_py"
        assert source.name == "nfl_data_py"

    def test_supported_sports_is_nfl_only(self) -> None:
        """Verify only NFL is supported."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.supported_sports == ["nfl"]
        assert source.supports_sport("nfl") is True
        assert source.supports_sport("nba") is False


class TestNFLDataPySourceCapabilities:
    """Test NFLDataPySource capability methods (Issue #236)."""

    def test_supports_stats_returns_true(self) -> None:
        """Verify NFLDataPySource supports stats loading."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.supports_stats() is True

    def test_supports_rankings_returns_false(self) -> None:
        """Verify NFLDataPySource does NOT support rankings."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.supports_rankings() is False

    def test_supports_games_returns_true(self) -> None:
        """Verify NFLDataPySource supports game loading."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.supports_games() is True

    def test_supports_elo_returns_false(self) -> None:
        """Verify NFLDataPySource does NOT support Elo."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.supports_elo() is False

    def test_supports_odds_returns_false(self) -> None:
        """Verify NFLDataPySource does NOT support odds."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        assert source.supports_odds() is False

    def test_get_capabilities_includes_stats(self) -> None:
        """Verify get_capabilities includes stats as True."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        caps = source.get_capabilities()

        assert caps["stats"] is True
        assert caps["games"] is True
        assert caps["rankings"] is False
        assert caps["elo"] is False
        assert caps["odds"] is False


class TestNFLDataPySourceValidation:
    """Test NFLDataPySource input validation."""

    def test_load_stats_rejects_non_nfl_sport(self) -> None:
        """Verify load_stats raises for non-NFL sports."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()

        with pytest.raises(DataSourceConfigError) as exc_info:
            list(source.load_stats(sport="nba"))

        assert "nba" in str(exc_info.value).lower()
        assert "not supported" in str(exc_info.value).lower()

    def test_load_stats_accepts_nfl_sport(self) -> None:
        """Verify load_stats accepts NFL sport (doesn't raise on validation)."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        # Mock the nfl module to avoid actual API calls
        source._nfl = MagicMock()
        source._nfl.import_weekly_data.return_value = MagicMock(
            empty=True, iterrows=lambda: iter([])
        )

        # Should not raise DataSourceConfigError for validation
        result = list(source.load_stats(sport="nfl", seasons=[2023], stat_type="weekly"))
        # Empty result is fine - we're testing validation, not data
        assert isinstance(result, list)


class TestNFLDataPySourceStatTypes:
    """Test NFLDataPySource stat type handling."""

    def test_invalid_stat_type_raises_error(self) -> None:
        """Verify invalid stat_type raises DataSourceConfigError."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        source._nfl = MagicMock()

        with pytest.raises(DataSourceConfigError) as exc_info:
            list(source.load_stats(sport="nfl", seasons=[2023], stat_type="invalid"))

        assert "invalid" in str(exc_info.value).lower()

    def test_weekly_stat_type_accepted(self) -> None:
        """Verify weekly stat_type is accepted."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        source._nfl = MagicMock()
        source._nfl.import_weekly_data.return_value = MagicMock(
            empty=True, iterrows=lambda: iter([])
        )

        # Should not raise
        list(source.load_stats(sport="nfl", seasons=[2023], stat_type="weekly"))

    def test_seasonal_stat_type_accepted(self) -> None:
        """Verify seasonal stat_type is accepted."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        source._nfl = MagicMock()
        source._nfl.import_seasonal_data.return_value = MagicMock(
            empty=True, iterrows=lambda: iter([])
        )

        # Should not raise
        list(source.load_stats(sport="nfl", seasons=[2023], stat_type="seasonal"))

    def test_team_stat_type_accepted(self) -> None:
        """Verify team stat_type is accepted."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        source._nfl = MagicMock()
        source._nfl.import_team_desc.return_value = MagicMock(empty=True)
        source._nfl.import_schedules.return_value = MagicMock(empty=True)

        # Should not raise
        list(source.load_stats(sport="nfl", seasons=[2023], stat_type="team"))


class TestNFLDataPySourceLazyLoading:
    """Test NFLDataPySource lazy loading behavior.

    Educational Note:
        nfl_data_py is lazily loaded to avoid ImportError if not installed.
        This allows the module to be imported even if nfl_data_py is optional.
    """

    def test_nfl_module_lazy_loaded(self) -> None:
        """Verify nfl module is not loaded until accessed."""
        from precog.database.seeding.sources import NFLDataPySource

        source = NFLDataPySource()
        # Before accessing, _nfl should be None
        assert source._nfl is None

    @patch("precog.database.seeding.sources.nfl_data_py_source._get_nfl_data_py")
    def test_nfl_property_calls_get_nfl_data_py(self, mock_get_nfl: MagicMock) -> None:
        """Verify nfl property triggers lazy loading."""
        from precog.database.seeding.sources import NFLDataPySource

        mock_module = MagicMock()
        mock_get_nfl.return_value = mock_module

        source = NFLDataPySource()
        result = source.nfl

        mock_get_nfl.assert_called_once()
        assert result == mock_module

    @patch("precog.database.seeding.sources.nfl_data_py_source._get_nfl_data_py")
    def test_nfl_property_caches_result(self, mock_get_nfl: MagicMock) -> None:
        """Verify nfl module is cached after first access."""
        from precog.database.seeding.sources import NFLDataPySource

        mock_module = MagicMock()
        mock_get_nfl.return_value = mock_module

        source = NFLDataPySource()
        _ = source.nfl
        _ = source.nfl  # Second access

        # Should only be called once due to caching
        mock_get_nfl.assert_called_once()
