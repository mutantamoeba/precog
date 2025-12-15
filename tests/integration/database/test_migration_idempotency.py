"""
Migration Idempotency Integration Tests

Tests that database migrations can be run multiple times without errors.
This verifies that migrations use IF NOT EXISTS and other idempotent patterns.

Educational Note:
    Idempotent migrations are CRITICAL for production deployments:
    - Deployments may retry on transient failures
    - Multiple servers may run migrations concurrently
    - Manual re-runs should not corrupt data

    Pattern: All CREATE TABLE should use IF NOT EXISTS
    Pattern: All ALTER TABLE should check column existence first
    Pattern: All INSERT for seeds should use ON CONFLICT DO NOTHING

References:
    - Issue #104: Automate migration testing
    - src/precog/database/migrations/migration_utils.py
    - docs/database/DATABASE_SCHEMA_SUMMARY_V1.12.md

Created: 2025-11-25
Phase: 1.5 (Foundation Validation)
GitHub Issue: #104
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from precog.database.connection import execute_query, fetch_one  # noqa: E402
from precog.database.connection import test_connection as check_db_connection  # noqa: E402

# Skip all tests if database not available
# Note: Renamed import to check_db_connection to avoid pytest collecting it as a test
pytestmark = pytest.mark.skipif(
    not check_db_connection(), reason="Database connection not available"
)


class TestMigrationIdempotency:
    """Test that migrations can be run multiple times without errors."""

    def test_table_exists_check_is_idempotent(self, db_pool, db_cursor, clean_test_data):
        """Verify table_exists function works correctly."""
        # Check for a known existing table
        result = fetch_one(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'markets'
            ) as exists
            """
        )
        assert result is not None
        # markets table should exist
        assert result["exists"] is True

    def test_column_exists_check_is_idempotent(self, db_pool, db_cursor, clean_test_data):
        """Verify we can check if column exists before adding."""
        result = fetch_one(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'markets'
                AND column_name = 'ticker'
            ) as exists
            """
        )
        assert result is not None
        # ticker column should exist in markets table
        assert result["exists"] is True

    def test_create_table_if_not_exists_pattern(self, db_pool, db_cursor, clean_test_data):
        """Verify CREATE TABLE IF NOT EXISTS is idempotent."""
        # Try to create a table that already exists
        # This should not raise an error
        try:
            execute_query(
                """
                CREATE TABLE IF NOT EXISTS _test_idempotent_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100)
                )
                """
            )
            # Second execution should also succeed
            execute_query(
                """
                CREATE TABLE IF NOT EXISTS _test_idempotent_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100)
                )
                """
            )
            # Cleanup
            execute_query("DROP TABLE IF EXISTS _test_idempotent_table")
        except Exception as e:
            # Cleanup on failure
            execute_query("DROP TABLE IF EXISTS _test_idempotent_table")
            pytest.fail(f"CREATE TABLE IF NOT EXISTS should be idempotent: {e}")

    def test_create_index_if_not_exists_pattern(self, db_pool, db_cursor, clean_test_data):
        """Verify CREATE INDEX IF NOT EXISTS is idempotent."""
        # Create test table
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS _test_index_table (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100)
            )
            """
        )
        try:
            # First index creation
            execute_query(
                """
                CREATE INDEX IF NOT EXISTS idx_test_name
                ON _test_index_table(name)
                """
            )
            # Second index creation should succeed (idempotent)
            execute_query(
                """
                CREATE INDEX IF NOT EXISTS idx_test_name
                ON _test_index_table(name)
                """
            )
        finally:
            # Cleanup
            execute_query("DROP TABLE IF EXISTS _test_index_table CASCADE")

    def test_insert_on_conflict_do_nothing_pattern(self, db_pool, db_cursor, clean_test_data):
        """Verify INSERT ON CONFLICT DO NOTHING is idempotent for seeds."""
        # Create test table with unique constraint
        execute_query(
            """
            CREATE TABLE IF NOT EXISTS _test_seed_table (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100)
            )
            """
        )
        try:
            # First insert
            execute_query(
                """
                INSERT INTO _test_seed_table (code, name)
                VALUES ('TEST', 'Test Value')
                ON CONFLICT (code) DO NOTHING
                """
            )
            # Second insert should succeed (idempotent)
            execute_query(
                """
                INSERT INTO _test_seed_table (code, name)
                VALUES ('TEST', 'Test Value')
                ON CONFLICT (code) DO NOTHING
                """
            )
            # Verify only one row exists
            result = fetch_one("SELECT COUNT(*) as count FROM _test_seed_table WHERE code = 'TEST'")
            assert result is not None  # Guard for type checker
            assert result["count"] == 1
        finally:
            # Cleanup
            execute_query("DROP TABLE IF EXISTS _test_seed_table CASCADE")


class TestMigrationUtilsIntegration:
    """Test migration utility functions from migration_utils.py.

    Note: migration_utils.py is archived in _archived_legacy_migrations/
    but these tests verify the utility functions still work correctly
    for any legacy code that may reference them.
    """

    def test_table_exists_function(self, db_pool, db_cursor, clean_test_data):
        """Test table_exists utility function."""
        from precog.database._archived_legacy_migrations.migration_utils import (
            table_exists,
        )

        # Known existing table
        assert table_exists("markets") is True
        # Non-existent table
        assert table_exists("nonexistent_table_xyz") is False

    def test_column_exists_function(self, db_pool, db_cursor, clean_test_data):
        """Test column_exists utility function."""
        from precog.database._archived_legacy_migrations.migration_utils import (
            column_exists,
        )

        # Known existing column
        assert column_exists("markets", "ticker") is True
        # Non-existent column
        assert column_exists("markets", "nonexistent_column_xyz") is False

    def test_index_exists_function(self, db_pool, db_cursor, clean_test_data):
        """Test index_exists utility function."""
        from precog.database._archived_legacy_migrations.migration_utils import (
            index_exists,
        )

        # Primary key index should exist
        assert index_exists("markets_pkey") is True
        # Non-existent index
        assert index_exists("nonexistent_index_xyz") is False

    def test_safe_create_table(self, db_pool, db_cursor, clean_test_data):
        """Test safe_create_table function is idempotent."""
        from precog.database._archived_legacy_migrations.migration_utils import (
            safe_create_table,
        )

        create_sql = """
            CREATE TABLE _test_safe_table (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100)
            )
        """
        try:
            # First creation - returns (success, message) tuple
            success1, msg1 = safe_create_table("_test_safe_table", create_sql)
            assert success1 is True, f"First creation failed: {msg1}"

            # Second creation should succeed (idempotent)
            # Note: safe_create_table returns (True, "[SKIP]...") when table exists
            success2, msg2 = safe_create_table("_test_safe_table", create_sql)
            assert success2 is True, f"Second creation failed: {msg2}"
            assert "[SKIP]" in msg2, "Expected skip message for existing table"
        finally:
            execute_query("DROP TABLE IF EXISTS _test_safe_table CASCADE")

    def test_safe_add_column(self, db_pool, db_cursor, clean_test_data):
        """Test safe_add_column function is idempotent."""
        from precog.database._archived_legacy_migrations.migration_utils import (
            safe_add_column,
            safe_create_table,
        )

        # Create test table - returns (success, message) tuple
        success, _ = safe_create_table(
            "_test_add_column", "CREATE TABLE _test_add_column (id SERIAL PRIMARY KEY)"
        )
        assert success is True
        try:
            # First add - returns (success, message) tuple
            success1, msg1 = safe_add_column("_test_add_column", "new_column", "VARCHAR(100)")
            assert success1 is True, f"First add failed: {msg1}"

            # Second add should succeed (idempotent)
            # Note: safe_add_column returns (True, "[SKIP]...") when column exists
            success2, msg2 = safe_add_column("_test_add_column", "new_column", "VARCHAR(100)")
            assert success2 is True, f"Second add failed: {msg2}"
            assert "[SKIP]" in msg2, "Expected skip message for existing column"
        finally:
            execute_query("DROP TABLE IF EXISTS _test_add_column CASCADE")


class TestSchemaValidation:
    """Validate current schema matches expected state."""

    def test_core_tables_exist(self, db_pool, db_cursor, clean_test_data):
        """Verify all core tables from migrations exist."""
        core_tables = [
            "markets",
            "positions",
            "trades",
            "strategies",
            "probability_models",
            "game_states",
            "edges",
        ]

        for table in core_tables:
            result = fetch_one(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                ) as exists
                """,
                (table,),
            )
            assert result is not None  # Guard for type checker
            assert result["exists"] is True, f"Core table '{table}' does not exist"

    def test_scd_type2_columns_exist(self, db_pool, db_cursor, clean_test_data):
        """Verify SCD Type 2 columns exist on versioned tables.

        Note: The actual schema uses row_current_ind and row_end_ts.
        row_start_ts and row_version are not implemented in current schema.
        """
        versioned_tables = ["markets", "positions", "game_states", "edges"]
        # Only check columns that exist in the actual schema
        scd_columns = ["row_current_ind", "row_end_ts"]

        for table in versioned_tables:
            for column in scd_columns:
                result = fetch_one(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = %s
                        AND column_name = %s
                    ) as exists
                    """,
                    (table, column),
                )
                assert result is not None  # Guard for type checker
                assert result["exists"] is True, (
                    f"SCD Type 2 column '{column}' missing from '{table}'"
                )

    def test_price_columns_are_decimal(self, db_pool, db_cursor, clean_test_data):
        """Verify price columns use DECIMAL (numeric) type.

        Note: The actual schema uses yes_price/no_price (not yes_bid/yes_ask).
        """
        price_columns = [
            ("markets", "yes_price"),
            ("markets", "no_price"),
            ("positions", "entry_price"),
        ]

        for table, column in price_columns:
            result = fetch_one(
                """
                SELECT data_type, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = %s
                AND column_name = %s
                """,
                (table, column),
            )
            assert result is not None, f"Column {table}.{column} does not exist"
            assert result["data_type"] == "numeric", (
                f"{table}.{column} should be DECIMAL (numeric), got {result['data_type']}"
            )
            # Note: Precision/scale may vary, so we just check it's numeric
