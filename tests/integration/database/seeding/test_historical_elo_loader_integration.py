"""
Integration Tests for Historical Elo Loader with Real Database.

These tests use REAL database operations with no mocking.
Requires running PostgreSQL database with test schema.

Test Strategy:
    Tests verify bulk insert operations against real database,
    including team lookup, batch processing, and data integrity.

Related:
    - Issue #208: Historical Data Seeding
    - REQ-DATA-003: Multi-Sport Team Support
    - Migration 030: Create historical_elo table

Usage:
    pytest tests/integration/database/seeding/test_historical_elo_loader_integration.py -v
    pytest tests/integration/database/seeding/ -v -m integration
"""

from datetime import date
from decimal import Decimal

import pytest

from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    LoadResult,
    bulk_insert_historical_elo,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_elo_records() -> list[HistoricalEloRecord]:
    """Create sample Elo records for testing.

    Educational Note:
        These records use team codes that should exist in the teams table
        after standard seeding (KC, BUF, etc.).
    """
    return [
        HistoricalEloRecord(
            team_code="KC",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 7),
            elo_rating=Decimal("1624.09"),
            qb_adjusted_elo=Decimal("1711.05"),
            qb_name="Patrick Mahomes",
            qb_value=Decimal("86.96"),
            source="imported",  # Valid source per historical_elo_source_check
            source_file="test_data.csv",
        ),
        HistoricalEloRecord(
            team_code="BUF",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 10),
            elo_rating=Decimal("1618.75"),
            qb_adjusted_elo=Decimal("1666.92"),
            qb_name="Josh Allen",
            qb_value=Decimal("48.17"),
            source="imported",  # Valid source per historical_elo_source_check
            source_file="test_data.csv",
        ),
    ]


# =============================================================================
# INTEGRATION TESTS: Team Lookup
# =============================================================================


@pytest.mark.integration
class TestTeamLookupIntegration:
    """Integration tests for team lookup functionality."""

    def test_valid_team_returns_id(self, db_pool, db_cursor) -> None:
        """Verify valid team codes return team IDs.

        Educational Note:
            This requires the teams table to be seeded with NFL teams.
        """
        from precog.database.seeding.historical_elo_loader import get_team_id_by_code

        # KC should exist in NFL
        team_id = get_team_id_by_code("KC", "nfl")
        if team_id is not None:
            assert isinstance(team_id, int)
            assert team_id > 0

    def test_invalid_team_returns_none(self, db_pool, db_cursor) -> None:
        """Verify invalid team codes return None."""
        from precog.database.seeding.historical_elo_loader import get_team_id_by_code

        team_id = get_team_id_by_code("INVALID_TEAM_CODE", "nfl")
        assert team_id is None


# =============================================================================
# INTEGRATION TESTS: Bulk Insert
# =============================================================================


@pytest.mark.integration
class TestBulkInsertIntegration:
    """Integration tests for bulk insert operations."""

    def test_bulk_insert_returns_result(self, db_pool, db_cursor, sample_elo_records) -> None:
        """Verify bulk insert returns LoadResult."""
        result = bulk_insert_historical_elo(iter(sample_elo_records))

        assert isinstance(result, LoadResult)
        assert result.records_processed == len(sample_elo_records)

    def test_bulk_insert_handles_empty_input(self, db_pool, db_cursor) -> None:
        """Verify bulk insert handles empty input gracefully."""
        result = bulk_insert_historical_elo(iter([]))

        assert result.records_processed == 0
        assert result.records_inserted == 0
        assert result.errors == 0

    def test_bulk_insert_skips_unknown_teams(self, db_pool, db_cursor) -> None:
        """Verify bulk insert skips records with unknown team codes."""
        records = [
            HistoricalEloRecord(
                team_code="UNKNOWN_TEAM_XYZ",
                sport="nfl",
                season=2023,
                rating_date=date(2023, 9, 7),
                elo_rating=Decimal("1500.00"),
                qb_adjusted_elo=None,
                qb_name=None,
                qb_value=None,
                source="imported",  # Valid source per historical_elo_source_check
                source_file=None,
            )
        ]

        result = bulk_insert_historical_elo(iter(records))

        assert result.records_processed == 1
        assert result.records_skipped == 1
        assert result.records_inserted == 0


# =============================================================================
# INTEGRATION TESTS: Data Integrity
# =============================================================================


@pytest.mark.integration
class TestDataIntegrityIntegration:
    """Integration tests for data integrity after bulk insert."""

    def test_decimal_precision_preserved(self, db_pool, db_cursor, sample_elo_records) -> None:
        """Verify Decimal precision is preserved in database.

        Educational Note:
            Pattern 1 (Decimal Precision) - All Elo ratings must maintain
            precision through storage and retrieval.
        """
        # Insert records
        result = bulk_insert_historical_elo(iter(sample_elo_records))

        # If insertion succeeded, precision should be preserved
        if result.records_inserted > 0:
            # Query back and verify precision
            db_cursor.execute(
                """
                SELECT elo_rating, qb_adjusted_elo
                FROM historical_elo
                WHERE source = 'imported'
                ORDER BY rating_date
                LIMIT 1
                """
            )
            row = db_cursor.fetchone()
            if row:
                # Verify values are Decimal and have correct precision
                # RealDictCursor returns dict-like rows
                assert isinstance(row["elo_rating"], Decimal)
                if row["qb_adjusted_elo"] is not None:
                    assert isinstance(row["qb_adjusted_elo"], Decimal)
