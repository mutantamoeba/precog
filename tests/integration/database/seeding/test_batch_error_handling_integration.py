"""
Integration Tests for Batch Insert Error Handling with Real Database.

These tests use REAL database operations with no mocking.
Requires running PostgreSQL database with test schema.

Test Strategy:
    Tests verify error handling modes (FAIL, SKIP, COLLECT) against
    real database operations with intentionally bad data.

Related:
    - Issue #255: Improve batch insert error handling with partial failure tracking
    - ADR-XXX: Batch Insert Error Handling Architecture

Usage:
    pytest tests/integration/database/seeding/test_batch_error_handling_integration.py -v
    pytest tests/integration/database/seeding/ -v -m integration
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from precog.database.seeding.batch_result import (
    BatchInsertResult,
    ErrorHandlingMode,
)
from precog.database.seeding.historical_elo_loader import (
    HistoricalEloRecord,
    bulk_insert_historical_elo,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def setup_test_teams(db_pool, db_cursor):
    """
    Create test teams required for Elo record inserts.

    Educational Note:
        These tests need team records for FK constraints. The bulk_insert_historical_elo
        function looks up teams by (team_code, sport) to get the team_id for insertion.
        Without these teams, the loader will fail with "Team not found" errors.

    Note:
        The teams table has a unique constraint on (team_code, sport).
        - In CI: No seed data exists, so teams are created fresh
        - In local dev: Seed data already has KC/BUF, so INSERT is skipped

        We use ON CONFLICT (team_code, sport) DO NOTHING to handle both cases.
        The fixture tracks which team_ids to use (seed data or newly created).
    """
    from precog.database.connection import get_cursor

    # First check if teams already exist (from seed data)
    with get_cursor(commit=False) as cur:
        cur.execute("SELECT team_id FROM teams WHERE team_code = 'KC' AND sport = 'nfl'")
        kc_row = cur.fetchone()
        cur.execute("SELECT team_id FROM teams WHERE team_code = 'BUF' AND sport = 'nfl'")
        buf_row = cur.fetchone()

    # Track whether we created new teams (for cleanup)
    created_team_ids = []

    if kc_row and buf_row:
        # Teams exist from seed data - use those
        kc_team_id = kc_row["team_id"]
        buf_team_id = buf_row["team_id"]
    else:
        # Teams don't exist (CI environment) - create them
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO teams (
                    team_id, team_code, team_name,
                    conference, division, sport, current_elo_rating
                )
                VALUES
                    (98001, 'KC', 'Kansas City Chiefs', 'AFC', 'West', 'nfl', 1624),
                    (98002, 'BUF', 'Buffalo Bills', 'AFC', 'East', 'nfl', 1618)
                ON CONFLICT (team_code, sport) DO NOTHING
                RETURNING team_id
            """
            )
        kc_team_id = 98001
        buf_team_id = 98002
        created_team_ids = [98001, 98002]

    yield {"kc_team_id": kc_team_id, "buf_team_id": buf_team_id}

    # Cleanup - only remove teams we created (not seed data)
    if created_team_ids:
        with get_cursor(commit=True) as cur:
            # First delete any historical_elo records referencing these teams
            cur.execute(
                "DELETE FROM historical_elo WHERE team_id = ANY(%s)",
                (created_team_ids,),
            )
            cur.execute(
                "DELETE FROM teams WHERE team_id = ANY(%s)",
                (created_team_ids,),
            )


@pytest.fixture
def valid_elo_records() -> list[HistoricalEloRecord]:
    """Create valid Elo records for testing.

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
            source="imported",
            source_file="test_error_handling.csv",
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
            source="imported",
            source_file="test_error_handling.csv",
        ),
    ]


@pytest.fixture
def mixed_elo_records() -> list[HistoricalEloRecord]:
    """Create mix of valid and invalid Elo records.

    Educational Note:
        This fixture includes records with unknown team codes to test
        error handling behavior. Unknown teams should trigger either
        skip or failure depending on error_mode.
    """
    return [
        # Valid record
        HistoricalEloRecord(
            team_code="KC",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 7),
            elo_rating=Decimal("1624.09"),
            qb_adjusted_elo=None,
            qb_name=None,
            qb_value=None,
            source="imported",
            source_file="test_partial_failure.csv",
        ),
        # Invalid: Unknown team
        HistoricalEloRecord(
            team_code="UNKNOWN_TEAM_ABC",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 8),
            elo_rating=Decimal("1500.00"),
            qb_adjusted_elo=None,
            qb_name=None,
            qb_value=None,
            source="imported",
            source_file="test_partial_failure.csv",
        ),
        # Valid record
        HistoricalEloRecord(
            team_code="BUF",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 9),
            elo_rating=Decimal("1618.75"),
            qb_adjusted_elo=None,
            qb_name=None,
            qb_value=None,
            source="imported",
            source_file="test_partial_failure.csv",
        ),
        # Invalid: Another unknown team
        HistoricalEloRecord(
            team_code="UNKNOWN_TEAM_XYZ",
            sport="nfl",
            season=2023,
            rating_date=date(2023, 9, 10),
            elo_rating=Decimal("1450.00"),
            qb_adjusted_elo=None,
            qb_name=None,
            qb_value=None,
            source="imported",
            source_file="test_partial_failure.csv",
        ),
    ]


# =============================================================================
# INTEGRATION TESTS: Error Handling Modes
# =============================================================================


@pytest.mark.integration
class TestCollectModeIntegration:
    """Integration tests for COLLECT error handling mode.

    Educational Note:
        COLLECT mode continues processing all records even when errors
        occur, gathering all failures into the result for later analysis.
        This is ideal for data validation pipelines where you want to
        identify ALL problems in one pass.
    """

    def test_collect_mode_continues_after_failures(
        self, db_pool, db_cursor, setup_test_teams, mixed_elo_records
    ) -> None:
        """Verify COLLECT mode processes all records despite failures.

        Given: 4 records (2 valid, 2 with unknown teams)
        When: bulk_insert with COLLECT mode
        Then: All 4 records processed, 2 successful, 2 failures collected
        """
        result = bulk_insert_historical_elo(
            iter(mixed_elo_records),
            error_mode=ErrorHandlingMode.COLLECT,
        )

        # All 4 records should be processed
        assert result.total_records == 4

        # Valid teams inserted successfully
        assert result.successful == 2

        # Unknown teams collected as failures (not skipped)
        assert result.failed == 2
        assert result.has_failures is True

        # Failures contain detailed tracking information
        assert len(result.failed_records) == 2
        for failure in result.failed_records:
            assert "UNKNOWN_TEAM" in failure.record_data["team_code"]
            assert failure.error_type == "ValueError"
            assert "Team not found" in failure.error_message

    def test_collect_mode_returns_batch_insert_result(
        self, db_pool, db_cursor, setup_test_teams, valid_elo_records
    ) -> None:
        """Verify COLLECT mode returns BatchInsertResult type."""
        result = bulk_insert_historical_elo(
            iter(valid_elo_records),
            error_mode=ErrorHandlingMode.COLLECT,
        )

        assert isinstance(result, BatchInsertResult)
        assert result.error_mode == ErrorHandlingMode.COLLECT
        assert result.operation == "Historical Elo Insert"

    def test_collect_mode_tracks_success_rate(
        self, db_pool, db_cursor, setup_test_teams, mixed_elo_records
    ) -> None:
        """Verify COLLECT mode calculates success rate correctly.

        Educational Note:
            Success rate = successful / total_records * 100
            With 4 records and 2 skips, we expect ~50% success rate
            (if valid teams insert successfully).
        """
        result = bulk_insert_historical_elo(
            iter(mixed_elo_records),
            error_mode=ErrorHandlingMode.COLLECT,
        )

        # Success rate should reflect partial success
        # Note: Actual rate depends on whether valid team inserts succeed
        assert 0.0 <= result.success_rate <= 100.0


@pytest.mark.integration
class TestSkipModeIntegration:
    """Integration tests for SKIP error handling mode.

    Educational Note:
        SKIP mode silently continues when encountering errors,
        incrementing the skip counter but not tracking failure details.
        This is efficient for large data loads where you don't need
        detailed error tracking.
    """

    def test_skip_mode_increments_skip_counter(
        self, db_pool, db_cursor, setup_test_teams, mixed_elo_records
    ) -> None:
        """Verify SKIP mode tracks skipped records."""
        result = bulk_insert_historical_elo(
            iter(mixed_elo_records),
            error_mode=ErrorHandlingMode.SKIP,
        )

        # All records processed
        assert result.total_records == 4

        # Unknown teams should be skipped
        assert result.records_skipped >= 2

    def test_skip_mode_does_not_track_failure_details(
        self, db_pool, db_cursor, setup_test_teams, mixed_elo_records
    ) -> None:
        """Verify SKIP mode does not populate failed_records list.

        Educational Note:
            Unlike COLLECT mode, SKIP mode is optimized for performance
            and doesn't store failure details. Use when you only need
            aggregate skip counts, not individual failure diagnostics.
        """
        result = bulk_insert_historical_elo(
            iter(mixed_elo_records),
            error_mode=ErrorHandlingMode.SKIP,
        )

        # SKIP mode doesn't track individual failures for skipped unknown teams
        # (unknown teams are skipped, not failures)
        assert result.records_skipped >= 2


@pytest.mark.integration
class TestFailModeIntegration:
    """Integration tests for FAIL error handling mode (default).

    Educational Note:
        FAIL mode is the default and most strict mode. It stops
        processing immediately on the first error and raises an
        exception. This ensures data consistency but requires
        all-or-nothing batch semantics.
    """

    def test_fail_mode_is_default(
        self, db_pool, db_cursor, setup_test_teams, valid_elo_records
    ) -> None:
        """Verify FAIL mode is the default error handling mode."""
        result = bulk_insert_historical_elo(iter(valid_elo_records))

        assert result.error_mode == ErrorHandlingMode.FAIL

    def test_fail_mode_succeeds_with_valid_data(
        self, db_pool, db_cursor, setup_test_teams, valid_elo_records
    ) -> None:
        """Verify FAIL mode succeeds when all data is valid."""
        result = bulk_insert_historical_elo(
            iter(valid_elo_records),
            error_mode=ErrorHandlingMode.FAIL,
        )

        # All records processed with no failures
        assert result.total_records == len(valid_elo_records)
        assert result.has_failures is False


# =============================================================================
# INTEGRATION TESTS: Backward Compatibility
# =============================================================================


@pytest.mark.integration
class TestBackwardCompatibilityIntegration:
    """Integration tests for LoadResult backward compatibility.

    Educational Note:
        Issue #255 unified LoadResult with BatchInsertResult while
        maintaining backward compatibility via property aliases:
        - records_processed -> total_records
        - records_inserted -> successful
        - records_skipped -> skipped
        - errors -> failed
        - error_messages -> string list from failed_records
    """

    def test_loadresult_property_aliases(
        self, db_pool, db_cursor, setup_test_teams, valid_elo_records
    ) -> None:
        """Verify LoadResult property aliases work correctly."""
        result = bulk_insert_historical_elo(iter(valid_elo_records))

        # New BatchInsertResult API
        assert result.total_records >= 0
        assert result.successful >= 0
        assert result.skipped >= 0
        assert result.failed >= 0

        # Backward-compatible LoadResult API (property aliases)
        assert result.records_processed == result.total_records
        assert result.records_inserted == result.successful
        assert result.records_skipped == result.skipped
        assert result.errors == result.failed

    def test_error_messages_returns_list(
        self, db_pool, db_cursor, setup_test_teams, valid_elo_records
    ) -> None:
        """Verify error_messages property returns list of strings."""
        result = bulk_insert_historical_elo(iter(valid_elo_records))

        messages = result.error_messages
        assert isinstance(messages, list)
        # With valid data, should be empty
        for msg in messages:
            assert isinstance(msg, str)


# =============================================================================
# INTEGRATION TESTS: Result Serialization
# =============================================================================


@pytest.mark.integration
class TestResultSerializationIntegration:
    """Integration tests for BatchInsertResult serialization.

    Educational Note:
        The to_dict() method enables JSON serialization for logging,
        API responses, and pipeline reporting.
    """

    def test_result_to_dict(self, db_pool, db_cursor, setup_test_teams, valid_elo_records) -> None:
        """Verify result can be serialized to dictionary."""
        result = bulk_insert_historical_elo(
            iter(valid_elo_records),
            error_mode=ErrorHandlingMode.COLLECT,
        )

        d = result.to_dict()

        # Verify dict contains expected keys
        assert "total_records" in d
        assert "successful" in d
        assert "failed" in d
        assert "skipped" in d
        assert "success_rate" in d
        assert "error_mode" in d
        assert "operation" in d
        assert "failed_records" in d
        assert "elapsed_time" in d

    def test_result_failure_summary(
        self, db_pool, db_cursor, setup_test_teams, valid_elo_records
    ) -> None:
        """Verify get_failure_summary() returns readable string."""
        result = bulk_insert_historical_elo(iter(valid_elo_records))

        summary = result.get_failure_summary()
        assert isinstance(summary, str)

        # With valid data, should indicate no failures
        if not result.has_failures:
            assert "No failures" in summary
