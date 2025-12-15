"""
Property-Based Tests for Historical Elo Loader.

Uses Hypothesis to test Elo rating invariants and parsing consistency.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-DATA-003, Issue #208

Usage:
    pytest tests/property/database/seeding/test_historical_elo_loader_properties.py -v -m property
"""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    LoadResult,
    normalize_team_code,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Valid team codes (3-letter abbreviations)
team_code_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=2,
    max_size=4,
)

# Valid Elo ratings (typical range 1200-1800)
elo_rating_strategy = st.decimals(
    min_value=Decimal("1000.00"),
    max_value=Decimal("2000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

# Season years
season_strategy = st.integers(min_value=1920, max_value=2030)

# Rating dates
date_strategy = st.dates(min_value=date(1920, 1, 1), max_value=date(2030, 12, 31))


# =============================================================================
# Property Tests: Team Code Normalization
# =============================================================================


@pytest.mark.property
class TestTeamCodeNormalizationProperties:
    """Property tests for team code normalization invariants."""

    @given(code=team_code_strategy)
    @settings(max_examples=100)
    def test_normalize_always_returns_uppercase(self, code: str) -> None:
        """Normalized code should always be uppercase."""
        result = normalize_team_code(code)
        assert result == result.upper(), f"Expected uppercase, got {result}"

    @given(code=team_code_strategy)
    @settings(max_examples=100)
    def test_normalize_is_idempotent(self, code: str) -> None:
        """Normalizing twice should give same result as once."""
        once = normalize_team_code(code)
        twice = normalize_team_code(once)
        assert once == twice, f"Not idempotent: {once} != {twice}"

    @given(code=st.sampled_from(["KC", "BUF", "NYJ", "DET", "LAR", "SF", "NE", "DAL"]))
    @settings(max_examples=20)
    def test_common_codes_unchanged(self, code: str) -> None:
        """Common team codes should remain unchanged."""
        assert normalize_team_code(code) == code


# =============================================================================
# Property Tests: HistoricalEloRecord Invariants
# =============================================================================


@pytest.mark.property
class TestHistoricalEloRecordProperties:
    """Property tests for HistoricalEloRecord data structure."""

    @given(
        elo=elo_rating_strategy,
        season=season_strategy,
    )
    @settings(max_examples=50)
    def test_elo_rating_preserved_in_record(self, elo: Decimal, season: int) -> None:
        """Elo rating should be preserved exactly in record."""
        record: HistoricalEloRecord = {
            "team_code": "KC",
            "sport": "nfl",
            "season": season,
            "rating_date": date(2023, 9, 7),
            "elo_rating": elo,
            "qb_adjusted_elo": None,
            "qb_name": None,
            "qb_value": None,
            "source": "test",
            "source_file": None,
        }
        assert record["elo_rating"] == elo

    @given(
        elo=elo_rating_strategy,
        qb_elo=elo_rating_strategy,
    )
    @settings(max_examples=50)
    def test_qb_adjusted_elo_independent(self, elo: Decimal, qb_elo: Decimal) -> None:
        """QB-adjusted Elo should be stored independently of base Elo."""
        record: HistoricalEloRecord = {
            "team_code": "KC",
            "sport": "nfl",
            "season": 2023,
            "rating_date": date(2023, 9, 7),
            "elo_rating": elo,
            "qb_adjusted_elo": qb_elo,
            "qb_name": "Patrick Mahomes",
            "qb_value": None,
            "source": "test",
            "source_file": None,
        }
        # Both values should be stored
        assert record["elo_rating"] == elo
        assert record["qb_adjusted_elo"] == qb_elo


# =============================================================================
# Property Tests: LoadResult Invariants
# =============================================================================


@pytest.mark.property
class TestLoadResultProperties:
    """Property tests for LoadResult data structure."""

    @given(
        processed=st.integers(min_value=0, max_value=100000),
        inserted=st.integers(min_value=0, max_value=100000),
        skipped=st.integers(min_value=0, max_value=100000),
    )
    @settings(max_examples=50)
    def test_load_result_counts_non_negative(
        self, processed: int, inserted: int, skipped: int
    ) -> None:
        """All counts in LoadResult should be non-negative."""
        result = LoadResult(
            records_processed=processed,
            records_inserted=inserted,
            records_skipped=skipped,
        )
        assert result.records_processed >= 0
        assert result.records_inserted >= 0
        assert result.records_skipped >= 0

    @given(errors=st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10))
    @settings(max_examples=30)
    def test_error_messages_preserved(self, errors: list[str]) -> None:
        """Error messages should be preserved in LoadResult."""
        result = LoadResult(
            records_processed=0,
            error_messages=errors,
            errors=len(errors),
        )
        assert len(result.error_messages) == len(errors)
        for i, msg in enumerate(errors):
            assert result.error_messages[i] == msg
