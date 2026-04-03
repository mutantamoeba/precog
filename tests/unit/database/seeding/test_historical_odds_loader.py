"""
Unit Tests for Historical Odds Loader - BACKWARD COMPATIBILITY.

These tests verify the backward-compatibility shim still works after the
rename from historical_odds_loader to game_odds_loader (migration 0048).

The real tests are in test_game_odds_loader.py. This file ensures old
import paths remain functional.

Related Architecture:
    - Issue #533: ESPN DraftKings odds extraction
    - Migration 0048: Rename historical_odds -> game_odds

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
# LoadResult Tests (via backward compat shim)
# =============================================================================


class TestLoadResult:
    """Test suite for LoadResult dataclass via old import path."""

    def test_default_values(self) -> None:
        """Verify LoadResult initializes with zero counts."""
        result = LoadResult()
        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert isinstance(result, BatchInsertResult)

    def test_type_alias_equivalence(self) -> None:
        """Verify LoadResult is an alias for BatchInsertResult."""
        assert LoadResult is BatchInsertResult

    def test_error_mode_support(self) -> None:
        """Verify LoadResult supports error_mode parameter (Issue #255)."""
        result = LoadResult(error_mode=ErrorHandlingMode.COLLECT)
        assert result.error_mode == ErrorHandlingMode.COLLECT


# =============================================================================
# Source Name Mapping Tests (via backward compat shim)
# =============================================================================


class TestSourceNameMapping:
    """Test suite for source name normalization via old import path."""

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
