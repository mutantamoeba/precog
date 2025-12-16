"""
Unit Tests for Base Data Source Module.

Tests the abstract base classes, TypedDict definitions, and helper mixins
for historical data source adapters.

Tests follow the project's testing patterns:
- Pattern 1: Decimal precision (all monetary values use Decimal)
- Pattern 7: Educational docstrings
- Pattern 10: Property-based testing for data validation

Related Requirements:
- REQ-DATA-006: Historical Games Data Seeding
- REQ-DATA-007: Historical Odds Data Seeding
- REQ-DATA-008: Data Source Adapter Architecture

Related Architecture:
- ADR-106: Historical Data Collection Architecture
- ADR-103: BasePoller Unified Design Pattern
- Issue #229: Expanded Historical Data Sources

Usage:
    pytest tests/unit/database/seeding/test_base_source.py -v
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from precog.database.seeding.sources.base_source import (
    APIBasedSourceMixin,
    BaseDataSource,
    DataSourceConfigError,
    DataSourceConnectionError,
    DataSourceError,
    EloRecord,
    FileBasedSourceMixin,
    GameRecord,
    LoadResult,
    OddsRecord,
)

# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestDataSourceExceptions:
    """Test suite for data source exception hierarchy."""

    def test_data_source_error_is_base_exception(self) -> None:
        """Verify DataSourceError is the base exception class."""
        exc = DataSourceError("Test error")
        assert str(exc) == "Test error"
        assert isinstance(exc, Exception)

    def test_config_error_inherits_from_base(self) -> None:
        """Verify DataSourceConfigError inherits from DataSourceError."""
        exc = DataSourceConfigError("Invalid config")
        assert isinstance(exc, DataSourceError)
        assert isinstance(exc, Exception)

    def test_connection_error_inherits_from_base(self) -> None:
        """Verify DataSourceConnectionError inherits from DataSourceError."""
        exc = DataSourceConnectionError("Connection failed")
        assert isinstance(exc, DataSourceError)
        assert isinstance(exc, Exception)

    def test_exception_can_be_caught_by_base(self) -> None:
        """Verify specific exceptions can be caught by base class."""
        try:
            raise DataSourceConfigError("Config issue")
        except DataSourceError as e:
            assert "Config issue" in str(e)


# =============================================================================
# LOAD RESULT TESTS
# =============================================================================


class TestLoadResult:
    """Test suite for LoadResult dataclass."""

    def test_default_values(self) -> None:
        """Verify LoadResult initializes with zero counts."""
        result = LoadResult()
        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert result.records_updated == 0
        assert result.records_skipped == 0
        assert result.errors == 0
        assert result.error_messages == []

    def test_custom_initialization(self) -> None:
        """Verify LoadResult accepts custom values."""
        result = LoadResult(
            records_processed=100,
            records_inserted=90,
            records_updated=5,
            records_skipped=3,
            errors=2,
            error_messages=["Error 1", "Error 2"],
        )
        assert result.records_processed == 100
        assert result.records_inserted == 90
        assert result.records_updated == 5
        assert result.records_skipped == 3
        assert result.errors == 2
        assert len(result.error_messages) == 2

    def test_addition_combines_results(self) -> None:
        """Verify LoadResult addition aggregates statistics correctly.

        Educational Note:
            When loading from multiple sources or files, we need to combine
            results. The __add__ method enables: total = result1 + result2
        """
        result1 = LoadResult(
            records_processed=50,
            records_inserted=45,
            records_skipped=5,
            error_messages=["Error A"],
        )
        result2 = LoadResult(
            records_processed=30,
            records_inserted=28,
            records_skipped=2,
            error_messages=["Error B", "Error C"],
        )

        combined = result1 + result2

        assert combined.records_processed == 80
        assert combined.records_inserted == 73
        assert combined.records_skipped == 7
        assert len(combined.error_messages) == 3
        assert "Error A" in combined.error_messages
        assert "Error B" in combined.error_messages

    def test_error_message_list_independence(self) -> None:
        """Verify error_messages list is not shared between instances."""
        result1 = LoadResult()
        result2 = LoadResult()

        result1.error_messages.append("Error")

        assert len(result1.error_messages) == 1
        assert len(result2.error_messages) == 0


# =============================================================================
# RECORD TYPE TESTS
# =============================================================================


class TestGameRecord:
    """Test suite for GameRecord TypedDict."""

    def test_game_record_structure(self) -> None:
        """Verify GameRecord has all required fields.

        Educational Note:
            GameRecord maps to the historical_games table (migration 0006).
            All fields must match the database schema.
        """
        record: GameRecord = {
            "sport": "nfl",
            "season": 2023,
            "game_date": date(2023, 9, 7),
            "home_team_code": "KC",
            "away_team_code": "DET",
            "home_score": 21,
            "away_score": 20,
            "is_neutral_site": False,
            "is_playoff": False,
            "game_type": "regular",
            "venue_name": "GEHA Field",
            "source": "fivethirtyeight",
            "source_file": "nfl_elo.csv",
            "external_game_id": "2023090700",
        }

        assert record["sport"] == "nfl"
        assert record["season"] == 2023
        assert record["home_team_code"] == "KC"
        assert record["home_score"] == 21

    def test_game_record_optional_fields(self) -> None:
        """Verify optional fields can be None."""
        record: GameRecord = {
            "sport": "nfl",
            "season": 2023,
            "game_date": date(2023, 9, 7),
            "home_team_code": "KC",
            "away_team_code": "DET",
            "home_score": None,  # Game not completed
            "away_score": None,
            "is_neutral_site": False,
            "is_playoff": False,
            "game_type": None,
            "venue_name": None,
            "source": "fivethirtyeight",
            "source_file": None,
            "external_game_id": None,
        }

        assert record["home_score"] is None
        assert record["venue_name"] is None


class TestOddsRecord:
    """Test suite for OddsRecord TypedDict."""

    def test_odds_record_structure(self) -> None:
        """Verify OddsRecord has all required fields.

        Educational Note:
            OddsRecord maps to the historical_odds table (migration 0007).
            Spread and total use Decimal for precision (ADR-002).
        """
        record: OddsRecord = {
            "sport": "nfl",
            "game_date": date(2023, 9, 7),
            "home_team_code": "KC",
            "away_team_code": "DET",
            "sportsbook": "consensus",
            "spread_home_open": Decimal("-3.5"),
            "spread_home_close": Decimal("-4.5"),
            "spread_home_odds_open": -110,
            "spread_home_odds_close": -110,
            "moneyline_home_open": -180,
            "moneyline_home_close": -200,
            "moneyline_away_open": 155,
            "moneyline_away_close": 170,
            "total_open": Decimal("52.5"),
            "total_close": Decimal("53.0"),
            "over_odds_open": -110,
            "over_odds_close": -115,
            "home_covered": True,
            "game_went_over": False,
            "source": "betting_csv",
            "source_file": "nfl_betting_2023.csv",
        }

        assert record["spread_home_close"] == Decimal("-4.5")
        assert record["total_close"] == Decimal("53.0")
        assert record["home_covered"] is True

    def test_odds_record_uses_decimal_not_float(self) -> None:
        """Verify spreads and totals use Decimal, not float.

        Educational Note:
            Pattern 1 (Decimal Precision) - All monetary/probability values
            must use Decimal to avoid floating-point precision errors.
            Example: 0.1 + 0.2 != 0.3 with floats, but works with Decimal.
        """
        record: OddsRecord = {
            "sport": "nfl",
            "game_date": date(2023, 9, 7),
            "home_team_code": "KC",
            "away_team_code": "DET",
            "sportsbook": None,
            "spread_home_open": Decimal("-3.5"),
            "spread_home_close": Decimal("-3.5"),
            "spread_home_odds_open": None,
            "spread_home_odds_close": None,
            "moneyline_home_open": None,
            "moneyline_home_close": None,
            "moneyline_away_open": None,
            "moneyline_away_close": None,
            "total_open": Decimal("45.5"),
            "total_close": Decimal("45.5"),
            "over_odds_open": None,
            "over_odds_close": None,
            "home_covered": None,
            "game_went_over": None,
            "source": "test",
            "source_file": None,
        }

        assert isinstance(record["spread_home_open"], Decimal)
        assert isinstance(record["total_open"], Decimal)


class TestEloRecord:
    """Test suite for EloRecord TypedDict."""

    def test_elo_record_structure(self) -> None:
        """Verify EloRecord has all required fields."""
        record: EloRecord = {
            "sport": "nfl",
            "team_code": "KC",
            "rating_date": date(2023, 9, 7),
            "elo_rating": Decimal("1624.09"),
            "season": 2023,
            "source": "fivethirtyeight",
            "source_file": "nfl_elo.csv",
        }

        assert record["team_code"] == "KC"
        assert record["elo_rating"] == Decimal("1624.09")
        assert record["season"] == 2023


# =============================================================================
# BASE DATA SOURCE TESTS
# =============================================================================


class ConcreteSource(BaseDataSource):
    """Concrete implementation for testing BaseDataSource."""

    source_name = "test_source"
    supported_sports = ["nfl", "nba"]  # noqa: RUF012


class TestBaseDataSource:
    """Test suite for BaseDataSource abstract class."""

    def test_source_name_property(self) -> None:
        """Verify source_name property returns correct value."""
        source = ConcreteSource()
        assert source.name == "test_source"
        assert source.source_name == "test_source"

    def test_supports_sport_returns_true_for_supported(self) -> None:
        """Verify supports_sport returns True for supported sports."""
        source = ConcreteSource()
        assert source.supports_sport("nfl") is True
        assert source.supports_sport("NBA") is True  # Case-insensitive

    def test_supports_sport_returns_false_for_unsupported(self) -> None:
        """Verify supports_sport returns False for unsupported sports."""
        source = ConcreteSource()
        assert source.supports_sport("mlb") is False
        assert source.supports_sport("soccer") is False

    def test_validate_sport_raises_for_unsupported(self) -> None:
        """Verify _validate_sport raises DataSourceConfigError."""
        source = ConcreteSource()

        with pytest.raises(DataSourceConfigError) as exc_info:
            source._validate_sport("mlb")

        assert "mlb" in str(exc_info.value)
        assert "not supported" in str(exc_info.value)

    def test_validate_sport_passes_for_supported(self) -> None:
        """Verify _validate_sport does not raise for supported sport."""
        source = ConcreteSource()
        source._validate_sport("nfl")  # Should not raise

    def test_load_games_raises_not_implemented(self) -> None:
        """Verify base load_games raises NotImplementedError."""
        source = ConcreteSource()

        with pytest.raises(NotImplementedError):
            list(source.load_games())

    def test_load_odds_raises_not_implemented(self) -> None:
        """Verify base load_odds raises NotImplementedError."""
        source = ConcreteSource()

        with pytest.raises(NotImplementedError):
            list(source.load_odds())

    def test_load_elo_raises_not_implemented(self) -> None:
        """Verify base load_elo raises NotImplementedError."""
        source = ConcreteSource()

        with pytest.raises(NotImplementedError):
            list(source.load_elo())

    def test_get_capabilities_default(self) -> None:
        """Verify get_capabilities returns False for unimplemented methods."""
        source = ConcreteSource()
        caps = source.get_capabilities()

        # Default implementation raises NotImplementedError
        assert caps["games"] is False
        assert caps["odds"] is False
        assert caps["elo"] is False


# =============================================================================
# FILE-BASED SOURCE MIXIN TESTS
# =============================================================================


class FileBasedTestSource(FileBasedSourceMixin, BaseDataSource):
    """Concrete implementation for testing FileBasedSourceMixin."""

    source_name = "file_test"
    supported_sports = ["nfl"]  # noqa: RUF012


class TestFileBasedSourceMixin:
    """Test suite for FileBasedSourceMixin."""

    def test_default_data_dir(self) -> None:
        """Verify default data directory is set."""
        source = FileBasedTestSource()
        assert source.data_dir == Path("data/historical")

    def test_custom_data_dir(self) -> None:
        """Verify custom data directory is used."""
        custom_dir = Path("/custom/data")
        source = FileBasedTestSource(data_dir=custom_dir)
        assert source.data_dir == custom_dir

    def test_get_file_path_combines_dir_and_filename(self) -> None:
        """Verify get_file_path returns correct full path."""
        source = FileBasedTestSource(data_dir=Path("/data"))
        path = source.get_file_path("test.csv")
        assert path == Path("/data/test.csv")

    def test_validate_file_path_raises_for_missing_file(self) -> None:
        """Verify _validate_file_path raises for non-existent file."""
        source = FileBasedTestSource()

        with pytest.raises(DataSourceConfigError) as exc_info:
            source._validate_file_path(Path("/nonexistent/file.csv"))

        assert "not found" in str(exc_info.value)

    def test_validate_file_path_passes_for_existing_file(self) -> None:
        """Verify _validate_file_path passes for existing file."""
        source = FileBasedTestSource()

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = Path(f.name)

        try:
            source._validate_file_path(temp_path)  # Should not raise
        finally:
            temp_path.unlink()  # Cleanup

    def test_validate_file_path_raises_for_directory(self) -> None:
        """Verify _validate_file_path raises for directory path."""
        source = FileBasedTestSource()

        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(DataSourceConfigError) as exc_info:
                source._validate_file_path(Path(temp_dir))

            assert "not a file" in str(exc_info.value)


# =============================================================================
# API-BASED SOURCE MIXIN TESTS
# =============================================================================


class APIBasedTestSource(APIBasedSourceMixin, BaseDataSource):
    """Concrete implementation for testing APIBasedSourceMixin."""

    source_name = "api_test"
    supported_sports = ["nfl", "nba"]  # noqa: RUF012


class TestAPIBasedSourceMixin:
    """Test suite for APIBasedSourceMixin."""

    def test_default_rate_limit(self) -> None:
        """Verify default rate limit is 60 requests/minute."""
        source = APIBasedTestSource()
        assert source.rate_limit == 60

    def test_custom_rate_limit(self) -> None:
        """Verify custom rate limit is used."""
        source = APIBasedTestSource(rate_limit=30)
        assert source.rate_limit == 30

    def test_rate_limit_property_readonly(self) -> None:
        """Verify rate_limit is accessible but set at init."""
        source = APIBasedTestSource(rate_limit=100)
        assert source.rate_limit == 100
        # Property should be read-only (no setter defined)
