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
    - Issue #255: Batch Insert Error Handling

Usage:
    pytest tests/unit/database/seeding/test_historical_odds_loader.py -v
"""

from precog.database.seeding.batch_result import BatchInsertResult, ErrorHandlingMode
from precog.database.seeding.historical_odds_loader import (
    SOURCE_NAME_MAPPING,
    LoadResult,
    normalize_source_name,
)

# =============================================================================
# LoadResult Tests
# =============================================================================


class TestLoadResult:
    """Test suite for LoadResult dataclass.

    Note: LoadResult is now an alias for BatchInsertResult (Issue #255).
    These tests verify backward compatibility with the old LoadResult API.
    """

    def test_default_values(self) -> None:
        """Verify LoadResult initializes with zero counts."""
        result = LoadResult()
        # Test backward-compatible property access
        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert result.records_skipped == 0
        assert result.errors == 0
        assert result.error_messages == []
        # Also verify it's actually BatchInsertResult
        assert isinstance(result, BatchInsertResult)

    def test_custom_initialization(self) -> None:
        """Verify LoadResult accepts custom values using BatchInsertResult API."""
        result = LoadResult(
            total_records=100,
            successful=90,
            skipped=3,
            failed=2,
        )
        # Add failures to populate error_messages
        result.add_failure(0, {"id": 1}, ValueError("Error 1"))
        result.add_failure(1, {"id": 2}, ValueError("Error 2"))

        # Test backward-compatible property access
        assert result.records_processed == 100
        assert result.records_inserted == 90
        assert result.records_skipped == 3
        assert result.errors == 4  # 2 initial + 2 added
        assert result.error_messages is not None
        assert len(result.error_messages) == 2

    def test_type_alias_equivalence(self) -> None:
        """Verify LoadResult is an alias for BatchInsertResult."""
        assert LoadResult is BatchInsertResult

    def test_error_mode_support(self) -> None:
        """Verify LoadResult supports error_mode parameter (Issue #255)."""
        result = LoadResult(error_mode=ErrorHandlingMode.COLLECT)
        assert result.error_mode == ErrorHandlingMode.COLLECT

    def test_has_failures_property(self) -> None:
        """Verify has_failures property works for error detection."""
        result = LoadResult(total_records=10, successful=10)
        assert result.has_failures is False

        result.add_failure(0, {"id": 1}, ValueError("Test error"))
        assert result.has_failures is True


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
