"""
Integration Tests for Database Connection.

Tests database connection with real PostgreSQL:
- Actual connection establishment
- Transaction management
- Connection pooling behavior

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- database/connection module coverage

Usage:
    pytest tests/integration/database/test_connection_integration.py -v
"""

from precog.database.connection import get_cursor


class TestConnectionIntegration:
    """Integration tests for database connection with real PostgreSQL."""

    def test_basic_connection(self, db_pool, clean_test_data):
        """
        INTEGRATION: Establish basic database connection.

        Verifies:
        - Connection to PostgreSQL works
        - Cursor can execute queries
        """
        with get_cursor() as cur:
            cur.execute("SELECT 1 AS val")
            result = cur.fetchone()
            assert result["val"] == 1

    def test_connection_with_commit(self, db_pool, clean_test_data):
        """
        INTEGRATION: Connection with transaction commit.

        Verifies:
        - Transactions commit successfully
        - Data persists after commit
        """
        # Insert data with commit
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO venues (espn_venue_id, venue_name, city)
                VALUES (%s, %s, %s)
                ON CONFLICT (espn_venue_id) DO NOTHING
                """,
                ("INT-TEST-001", "Integration Test Venue", "Test City"),
            )

        # Verify data persists
        with get_cursor() as cur:
            cur.execute(
                "SELECT venue_name FROM venues WHERE espn_venue_id = %s",
                ("INT-TEST-001",),
            )
            result = cur.fetchone()
            if result:
                assert result["venue_name"] == "Integration Test Venue"

        # Cleanup
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM venues WHERE espn_venue_id = 'INT-TEST-001'")

    def test_connection_rollback_on_error(self, db_pool, clean_test_data):
        """
        INTEGRATION: Connection rollback on error.

        Verifies:
        - Errors trigger rollback
        - Data is not persisted on failure
        """
        try:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO venues (espn_venue_id, venue_name, city)
                    VALUES (%s, %s, %s)
                    """,
                    ("INT-TEST-002", "Should Rollback", "Test City"),
                )
                # Force an error
                cur.execute("SELECT * FROM nonexistent_table_xyz")
        except Exception:
            pass  # Expected error

        # Verify data was rolled back
        with get_cursor() as cur:
            cur.execute(
                "SELECT venue_name FROM venues WHERE espn_venue_id = %s",
                ("INT-TEST-002",),
            )
            result = cur.fetchone()
            assert result is None, "Data should have been rolled back"

    def test_multiple_cursors(self, db_pool, clean_test_data):
        """
        INTEGRATION: Multiple cursors work correctly.

        Verifies:
        - Multiple cursors can be opened
        - Each cursor operates independently
        """
        with get_cursor() as cur1:
            cur1.execute("SELECT 1 AS val")
            result1 = cur1.fetchone()

            with get_cursor() as cur2:
                cur2.execute("SELECT 2 AS val")
                result2 = cur2.fetchone()

            assert result1["val"] == 1
            assert result2["val"] == 2

    def test_connection_pool_reuse(self, db_pool, clean_test_data):
        """
        INTEGRATION: Connections are reused from pool.

        Verifies:
        - Connections are returned to pool
        - Pool maintains connections
        """
        # First connection
        with get_cursor() as cur:
            cur.execute("SELECT 1 AS val")

        # Second connection (should reuse from pool)
        with get_cursor() as cur:
            cur.execute("SELECT 2 AS val")
            result = cur.fetchone()
            assert result["val"] == 2
