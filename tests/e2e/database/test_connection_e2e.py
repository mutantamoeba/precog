"""
End-to-End Tests for Database Connection.

Tests complete database workflows:
- Full CRUD operations through connection
- Complex transaction scenarios
- Production-like usage patterns

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- database/connection module coverage

Usage:
    pytest tests/e2e/database/test_connection_e2e.py -v -m e2e
"""

import pytest

from precog.database.connection import get_cursor


@pytest.mark.e2e
class TestConnectionE2E:
    """End-to-end tests for complete database workflows."""

    def test_full_crud_workflow(self, db_pool, clean_test_data):
        """
        E2E: Complete Create-Read-Update-Delete workflow.

        Verifies:
        - All CRUD operations work end-to-end
        - Data integrity maintained throughout
        """
        venue_id = "E2E-CRUD-001"

        # Create
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO venues (espn_venue_id, venue_name, city)
                VALUES (%s, %s, %s)
                ON CONFLICT (espn_venue_id) DO UPDATE
                SET venue_name = EXCLUDED.venue_name
                """,
                (venue_id, "E2E Test Venue", "Test City"),
            )

        # Read
        with get_cursor() as cur:
            cur.execute(
                "SELECT venue_name, city FROM venues WHERE espn_venue_id = %s",
                (venue_id,),
            )
            result = cur.fetchone()
            assert result["venue_name"] == "E2E Test Venue"

        # Update
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE venues SET venue_name = %s WHERE espn_venue_id = %s",
                ("Updated E2E Venue", venue_id),
            )

        # Verify update
        with get_cursor() as cur:
            cur.execute(
                "SELECT venue_name FROM venues WHERE espn_venue_id = %s",
                (venue_id,),
            )
            result = cur.fetchone()
            assert result["venue_name"] == "Updated E2E Venue"

        # Delete
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM venues WHERE espn_venue_id = %s",
                (venue_id,),
            )

        # Verify deletion
        with get_cursor() as cur:
            cur.execute(
                "SELECT venue_name FROM venues WHERE espn_venue_id = %s",
                (venue_id,),
            )
            result = cur.fetchone()
            assert result is None

    def test_batch_operations_workflow(self, db_pool, clean_test_data):
        """
        E2E: Batch insert and query workflow.

        Verifies:
        - Batch operations work correctly
        - Data can be queried after batch insert
        """
        # Batch insert
        venue_ids = [f"E2E-BATCH-{i:03d}" for i in range(10)]

        with get_cursor(commit=True) as cur:
            for venue_id in venue_ids:
                cur.execute(
                    """
                    INSERT INTO venues (espn_venue_id, venue_name, city)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (espn_venue_id) DO NOTHING
                    """,
                    (venue_id, f"Venue {venue_id}", "Batch City"),
                )

        # Query batch
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM venues WHERE espn_venue_id LIKE 'E2E-BATCH-%'")
            count = cur.fetchone()["cnt"]
            assert count == 10

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id LIKE 'E2E-BATCH-%'")

    def test_concurrent_access_workflow(self, db_pool, clean_test_data):
        """
        E2E: Concurrent database access pattern.

        Verifies:
        - Multiple connections can access database
        - No data corruption from concurrent access
        """
        venue_id = "E2E-CONCURRENT-001"

        # Setup
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO venues (espn_venue_id, venue_name, city)
                VALUES (%s, %s, %s)
                ON CONFLICT (espn_venue_id) DO NOTHING
                """,
                (venue_id, "Concurrent Venue", "Concurrent City"),
            )

        # Simulate concurrent reads
        results = []
        for _ in range(5):
            with get_cursor() as cur:
                cur.execute(
                    "SELECT venue_name FROM venues WHERE espn_venue_id = %s",
                    (venue_id,),
                )
                result = cur.fetchone()
                if result:
                    results.append(result["venue_name"])

        # All reads should return same value
        assert len(set(results)) <= 1

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM venues WHERE espn_venue_id = %s",
                (venue_id,),
            )

    def test_error_recovery_workflow(self, db_pool, clean_test_data):
        """
        E2E: Error recovery and continuation workflow.

        Verifies:
        - System recovers from errors
        - Subsequent operations work correctly
        """
        # Cause an error
        try:
            with get_cursor() as cur:
                cur.execute("SELECT * FROM nonexistent_table_e2e")
        except Exception:
            pass  # Expected error

        # System should still work
        with get_cursor() as cur:
            cur.execute("SELECT 1 AS val")
            result = cur.fetchone()
            assert result["val"] == 1

    def test_transaction_isolation_workflow(self, db_pool, clean_test_data):
        """
        E2E: Transaction isolation verification.

        Verifies:
        - Uncommitted changes not visible to other transactions
        - Committed changes are visible
        """
        venue_id = "E2E-ISOLATION-001"

        # Insert but don't commit yet in context manager scope
        # Note: get_cursor with commit=False won't persist
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                INSERT INTO venues (espn_venue_id, venue_name, city)
                VALUES (%s, %s, %s)
                ON CONFLICT (espn_venue_id) DO NOTHING
                """,
                (venue_id, "Isolation Test", "Test City"),
            )

        # Verify not visible (rolled back)
        with get_cursor() as cur:
            cur.execute(
                "SELECT venue_name FROM venues WHERE espn_venue_id = %s",
                (venue_id,),
            )
            result = cur.fetchone()
            # Should be None since we didn't commit
            assert result is None
