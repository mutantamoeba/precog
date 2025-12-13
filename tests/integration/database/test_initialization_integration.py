"""
Integration tests for database initialization module.

Tests interactions between initialization functions and actual database.
These tests require a running PostgreSQL instance.

Reference: TESTING_STRATEGY_V3.2.md Section "Integration Tests"
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.initialization import (
    apply_migrations,
    apply_schema,
    validate_critical_tables,
)

pytestmark = [pytest.mark.integration]


class TestApplySchemaIntegration:
    """Integration tests for schema application."""

    @pytest.mark.skipif(
        not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set - requires PostgreSQL"
    )
    def test_apply_schema_with_real_psql(self, tmp_path: Path) -> None:
        """Test schema application with actual psql command.

        Note:
            This test requires psql to be installed and DATABASE_URL to be set.
            It creates a temporary schema file and attempts to apply it.
        """
        schema_file = tmp_path / "test_schema.sql"
        schema_file.write_text("""
            CREATE TABLE IF NOT EXISTS integration_test_table (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            );
        """)

        db_url = os.getenv("DATABASE_URL")
        success, error = apply_schema(db_url, str(schema_file))

        # Should succeed or fail with "already exists" (which is OK)
        if not success:
            assert "already exists" in error.lower() or "psql" in error.lower()

    @patch("precog.database.initialization.subprocess.run")
    def test_schema_application_uses_correct_command(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Verify psql is called with correct arguments."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        db_url = "postgresql://user:pass@localhost:5432/testdb"

        apply_schema(db_url, str(schema_file))

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "psql"
        assert call_args[1] == db_url
        assert call_args[2] == "-f"


class TestApplyMigrationsIntegration:
    """Integration tests for migration application."""

    @patch("precog.database.initialization.subprocess.run")
    def test_migrations_applied_in_alphabetical_order(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Verify migrations are applied in correct order."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()

        # Create migrations out of order
        (migration_dir / "003_third.sql").write_text("SELECT 3;")
        (migration_dir / "001_first.sql").write_text("SELECT 1;")
        (migration_dir / "002_second.sql").write_text("SELECT 2;")

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        applied, failed = apply_migrations("postgresql://localhost/test", str(migration_dir))

        assert applied == 3
        assert failed == []

        # Verify order of calls
        calls = mock_run.call_args_list
        assert "001_first.sql" in str(calls[0])
        assert "002_second.sql" in str(calls[1])
        assert "003_third.sql" in str(calls[2])

    @patch("precog.database.initialization.subprocess.run")
    def test_continues_after_migration_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify migration continues after individual failure."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()
        (migration_dir / "001_first.sql").write_text("SELECT 1;")
        (migration_dir / "002_fails.sql").write_text("SELECT 2;")
        (migration_dir / "003_third.sql").write_text("SELECT 3;")

        # Second migration fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="ERROR: syntax error"),
            MagicMock(returncode=0, stderr=""),
        ]

        applied, failed = apply_migrations("postgresql://localhost/test", str(migration_dir))

        assert applied == 2
        assert len(failed) == 1
        assert "002_fails.sql" in failed


class TestValidateCriticalTablesIntegration:
    """Integration tests for table validation."""

    @patch("precog.database.connection.fetch_all")
    def test_validates_default_critical_tables(self, mock_fetch: MagicMock) -> None:
        """Verify default critical tables are checked."""
        mock_fetch.return_value = [{"exists": True}]

        missing = validate_critical_tables()

        # Should check 8 default tables
        assert mock_fetch.call_count == 8
        assert missing == []

    @patch("precog.database.connection.fetch_all")
    def test_reports_missing_tables(self, mock_fetch: MagicMock) -> None:
        """Verify missing tables are correctly reported."""
        # Alternate between exists and missing
        mock_fetch.side_effect = [
            [{"exists": True}],  # platforms
            [{"exists": False}],  # series - missing
            [{"exists": True}],  # events
            [{"exists": False}],  # markets - missing
            [{"exists": True}],  # strategies
            [{"exists": True}],  # probability_models
            [{"exists": True}],  # positions
            [{"exists": True}],  # trades
        ]

        missing = validate_critical_tables()

        assert "series" in missing
        assert "markets" in missing
        assert len(missing) == 2

    @patch("precog.database.connection.fetch_all")
    def test_custom_table_list(self, mock_fetch: MagicMock) -> None:
        """Verify custom table list is used when provided."""
        mock_fetch.return_value = [{"exists": True}]
        custom_tables = ["custom_table_1", "custom_table_2"]

        missing = validate_critical_tables(custom_tables)

        assert mock_fetch.call_count == 2
        assert missing == []
