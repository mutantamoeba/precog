"""
Unit Tests for Historical Odds Loader.

Tests the data transformation and loading functions for historical
betting odds data.

Related Requirements:
    - REQ-DATA-007: Historical Odds Data Seeding
    - REQ-DATA-008: Data Source Adapter Architecture

Related Architecture:
    - ADR-106: Historical Data Collection Architecture
    - Issue #229: Expanded Historical Data Sources

Usage:
    pytest tests/unit/database/seeding/test_historical_odds_loader.py -v
"""

from precog.database.seeding.historical_odds_loader import (
    SOURCE_NAME_MAPPING,
    LoadResult,
    normalize_source_name,
)

# =============================================================================
# LoadResult Tests
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
        assert result.error_messages is not None
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


# =============================================================================
# Source Name Mapping Tests
# =============================================================================


class TestSourceNameMapping:
    """Test suite for source name normalization."""

    def test_known_sources_mapped_correctly(self) -> None:
        """Verify known source names are mapped."""
        assert SOURCE_NAME_MAPPING["betting_csv"] == "betting_csv"
        assert SOURCE_NAME_MAPPING["fivethirtyeight"] == "fivethirtyeight"
        assert SOURCE_NAME_MAPPING["kaggle"] == "kaggle"

    def test_normalize_known_source(self) -> None:
        """Verify normalize_source_name returns mapped value."""
        assert normalize_source_name("betting_csv") == "betting_csv"
        assert normalize_source_name("fivethirtyeight") == "fivethirtyeight"

    def test_normalize_unknown_source(self) -> None:
        """Verify normalize_source_name returns 'imported' for unknown sources."""
        # Unknown sources should default to 'imported' or raise an error
        result = normalize_source_name("unknown_source_xyz")
        assert result == "imported"

    def test_source_name_mapping_has_required_sources(self) -> None:
        """Verify all expected data sources are in mapping."""
        required_sources = [
            "betting_csv",
            "fivethirtyeight",
            "kaggle",
            "odds_portal",
            "action_network",
            "pinnacle",
            "manual",
        ]
        for source in required_sources:
            assert source in SOURCE_NAME_MAPPING
