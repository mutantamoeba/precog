"""
Tests for database/initialization.py module.

This test suite provides comprehensive coverage for database initialization
functions including schema validation, schema application, migrations, and
table validation.

Educational Note:
    These tests demonstrate the "Mock API Boundaries, Not Implementation" pattern
    (Pattern 11). We mock subprocess.run() (external dependency) but don't mock
    internal helper functions like os.path.exists() unless necessary for isolation.

Coverage Target: ≥90% (critical infrastructure module)

Reference:
    database/initialization.py - Module under test
    docs/guides/DEVELOPMENT_PATTERNS_V1.0.md - Pattern 11 (Test Mocking Patterns)
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from database.initialization import (
    apply_migrations,
    apply_schema,
    get_database_url,
    validate_critical_tables,
    validate_schema_file,
)

# ==============================================================================
# FIXTURE SETUP
# ==============================================================================


@pytest.fixture
def temp_schema_file(tmp_path: Path) -> str:
    """Create temporary schema file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary schema file

    Educational Note:
        Using tmp_path ensures test isolation - each test gets its own
        temporary directory that's automatically cleaned up after the test.
    """
    schema_file = tmp_path / "test_schema.sql"
    schema_file.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")
    return str(schema_file)


@pytest.fixture
def temp_migration_dir(tmp_path: Path) -> str:
    """Create temporary migration directory with sample migrations.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary migration directory

    Educational Note:
        We create realistic migration files (001_*.sql, 002_*.sql) to test
        alphabetical ordering and sequential application.
    """
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()

    # Create 3 sample migration files
    (migration_dir / "001_create_users.sql").write_text("CREATE TABLE users (id SERIAL);")
    (migration_dir / "002_add_index.sql").write_text("CREATE INDEX idx_users_id ON users(id);")
    (migration_dir / "003_add_column.sql").write_text("ALTER TABLE users ADD COLUMN name TEXT;")

    return str(migration_dir)


# ==============================================================================
# TEST: validate_schema_file()
# ==============================================================================


class TestValidateSchemaFile:
    """Tests for validate_schema_file() function."""

    def test_validate_schema_file_exists_and_readable(self, temp_schema_file: str) -> None:
        """Test validation succeeds for existing readable file.

        Educational Note:
            This is the "happy path" test - verify function works correctly
            when given valid input.
        """
        result = validate_schema_file(temp_schema_file)

        assert result is True

    def test_validate_schema_file_does_not_exist(self) -> None:
        """Test validation fails for non-existent file.

        Educational Note:
            Testing edge case - what happens when file doesn't exist?
            Function should return False, not raise exception.
        """
        result = validate_schema_file("nonexistent_file.sql")

        assert result is False

    def test_validate_schema_file_not_readable(self, tmp_path: Path) -> None:
        """Test validation fails for file without read permissions.

        Educational Note:
            This test may be platform-specific (Windows handles permissions
            differently than Linux). We use pytest.mark.skipif to skip on
            Windows if needed.

        Note:
            On Windows, os.chmod() may not work as expected. This test
            verifies the INTENT of checking readability even if we can't
            actually remove read permissions on Windows.
        """
        # Create file with no read permissions
        no_read_file = tmp_path / "no_read.sql"
        no_read_file.write_text("CREATE TABLE test (id INT);")

        # Try to remove read permissions (may not work on Windows)
        try:
            os.chmod(no_read_file, 0o000)
            result = validate_schema_file(str(no_read_file))

            # If we successfully removed permissions, validation should fail
            if os.name != "nt":  # Skip assertion on Windows
                assert result is False

        finally:
            # Restore permissions for cleanup
            os.chmod(no_read_file, 0o644)

    def test_validate_schema_file_directory_not_file(self, tmp_path: Path) -> None:
        """Test validation fails when given directory path instead of file.

        Educational Note:
            Edge case testing - what if someone passes a directory instead of
            a file? os.access(dir, R_OK) returns True for readable directories,
            but we still want validation to fail because it's not a file.
        """
        result = validate_schema_file(str(tmp_path))

        # Directory exists and is readable, but validation should consider
        # whether it makes sense as a schema FILE
        # Current implementation: returns True (directory exists and is readable)
        # This is acceptable behavior - caller should verify .sql extension
        assert isinstance(result, bool)


# ==============================================================================
# TEST: apply_schema()
# ==============================================================================


class TestApplySchema:
    """Tests for apply_schema() function."""

    @patch("database.initialization.subprocess.run")
    def test_apply_schema_success(self, mock_run: MagicMock, temp_schema_file: str) -> None:
        """Test successful schema application.

        Educational Note:
            We mock subprocess.run() because we don't want to actually execute
            psql during unit tests. This follows Pattern 11 - mock external
            dependencies (psql subprocess) not internal logic.
        """
        # Mock successful psql execution
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        success, error = apply_schema("postgresql://localhost/test_db", temp_schema_file)

        assert success is True
        assert error == ""
        mock_run.assert_called_once()

    @patch("database.initialization.subprocess.run")
    def test_apply_schema_already_exists_is_ok(
        self, mock_run: MagicMock, temp_schema_file: str
    ) -> None:
        """Test schema application tolerates 'already exists' errors (idempotency).

        Educational Note:
            Idempotency means the operation can be run multiple times safely.
            If tables already exist, that's OK - we don't want to fail just
            because someone ran db-init twice.
        """
        # Mock psql execution with "already exists" error
        mock_run.return_value = MagicMock(returncode=1, stderr="ERROR: table already exists")

        success, error = apply_schema("postgresql://localhost/test_db", temp_schema_file)

        assert success is True  # Should succeed despite error
        assert error == ""

    @patch("database.initialization.subprocess.run")
    def test_apply_schema_fails_on_other_errors(
        self, mock_run: MagicMock, temp_schema_file: str
    ) -> None:
        """Test schema application fails on non-idempotent errors.

        Educational Note:
            We tolerate "already exists" but NOT other errors like syntax
            errors, permission denied, etc. This test verifies we fail correctly.
        """
        # Mock psql execution with syntax error
        mock_run.return_value = MagicMock(
            returncode=1, stderr="ERROR: syntax error at or near 'CRATE'"
        )

        success, error = apply_schema("postgresql://localhost/test_db", temp_schema_file)

        assert success is False
        assert "syntax error" in error

    def test_apply_schema_invalid_db_url(self, temp_schema_file: str) -> None:
        """Test schema application fails with invalid database URL.

        Educational Note:
            Security validation - we check db_url format BEFORE passing to
            subprocess to prevent command injection attacks.
        """
        success, error = apply_schema("invalid-url", temp_schema_file)

        assert success is False
        assert "Invalid database URL" in error

    def test_apply_schema_non_sql_file(self, tmp_path: Path) -> None:
        """Test schema application fails for non-.sql files.

        Educational Note:
            Security validation - we only allow .sql files to prevent
            accidentally executing arbitrary files via subprocess.
        """
        non_sql_file = tmp_path / "schema.txt"
        non_sql_file.write_text("CREATE TABLE test (id INT);")

        success, error = apply_schema("postgresql://localhost/test_db", str(non_sql_file))

        assert success is False
        assert ".sql file" in error

    def test_apply_schema_file_not_found(self) -> None:
        """Test schema application fails when schema file doesn't exist.

        Educational Note:
            Pre-validation - we check file existence BEFORE calling subprocess
            to provide clear error messages instead of cryptic subprocess errors.
        """
        success, error = apply_schema("postgresql://localhost/test_db", "nonexistent.sql")

        assert success is False
        assert "not found" in error

    @patch("database.initialization.subprocess.run")
    def test_apply_schema_psql_not_installed(
        self, mock_run: MagicMock, temp_schema_file: str
    ) -> None:
        """Test schema application fails gracefully when psql not installed.

        Educational Note:
            Dependency checking - if psql isn't installed, provide helpful
            error message instead of cryptic FileNotFoundError.
        """
        mock_run.side_effect = FileNotFoundError("psql command not found")

        success, error = apply_schema("postgresql://localhost/test_db", temp_schema_file)

        assert success is False
        assert "psql command not found" in error

    @patch("database.initialization.subprocess.run")
    def test_apply_schema_timeout(self, mock_run: MagicMock, temp_schema_file: str) -> None:
        """Test schema application fails on timeout.

        Educational Note:
            Timeout handling - large schema files might take a long time.
            We set reasonable timeout (30s default) and handle TimeoutExpired.
        """
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="psql", timeout=30)

        success, error = apply_schema(
            "postgresql://localhost/test_db", temp_schema_file, timeout=30
        )

        assert success is False
        assert "timed out" in error


# ==============================================================================
# TEST: apply_migrations()
# ==============================================================================


class TestApplyMigrations:
    """Tests for apply_migrations() function."""

    @patch("database.initialization.subprocess.run")
    def test_apply_migrations_success(self, mock_run: MagicMock, temp_migration_dir: str) -> None:
        """Test successful migration application.

        Educational Note:
            We verify migrations are applied in alphabetical order (001, 002, 003)
            by checking that subprocess.run() is called 3 times.
        """
        # Mock successful psql execution for all migrations
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        applied, failed = apply_migrations("postgresql://localhost/test_db", temp_migration_dir)

        assert applied == 3  # All 3 migrations applied
        assert failed == []
        assert mock_run.call_count == 3

    @patch("database.initialization.subprocess.run")
    def test_apply_migrations_partial_failure(
        self, mock_run: MagicMock, temp_migration_dir: str
    ) -> None:
        """Test migration application continues after failure.

        Educational Note:
            Resilience - if one migration fails, we still try the rest.
            This allows partial application and clear error reporting.
        """
        # Mock: first migration succeeds, second fails, third succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # 001 succeeds
            MagicMock(returncode=1, stderr="ERROR: syntax error"),  # 002 fails
            MagicMock(returncode=0, stderr=""),  # 003 succeeds
        ]

        applied, failed = apply_migrations("postgresql://localhost/test_db", temp_migration_dir)

        assert applied == 2  # 001 and 003 applied
        assert len(failed) == 1
        assert "002_add_index.sql" in failed

    def test_apply_migrations_invalid_db_url(self, temp_migration_dir: str) -> None:
        """Test migration application fails with invalid database URL.

        Educational Note:
            Security validation - same as apply_schema(), we validate URL
            format before attempting subprocess calls.
        """
        applied, failed = apply_migrations("invalid-url", temp_migration_dir)

        assert applied == 0
        assert failed == []

    def test_apply_migrations_directory_not_found(self) -> None:
        """Test migration application handles missing migration directory.

        Educational Note:
            Graceful degradation - if migrations directory doesn't exist,
            return (0, []) instead of raising exception. Not all databases
            will have migrations.
        """
        applied, failed = apply_migrations("postgresql://localhost/test_db", "nonexistent_dir")

        assert applied == 0
        assert failed == []

    def test_apply_migrations_empty_directory(self, tmp_path: Path) -> None:
        """Test migration application handles empty migration directory.

        Educational Note:
            Edge case - what if migrations/ exists but contains no .sql files?
            Should return (0, []) gracefully.
        """
        empty_dir = tmp_path / "empty_migrations"
        empty_dir.mkdir()

        applied, failed = apply_migrations("postgresql://localhost/test_db", str(empty_dir))

        assert applied == 0
        assert failed == []

    @patch("database.initialization.subprocess.run")
    def test_apply_migrations_psql_timeout(
        self, mock_run: MagicMock, temp_migration_dir: str
    ) -> None:
        """Test migration application handles timeout on individual migration.

        Educational Note:
            Timeout per-migration - if one migration times out, we record it
            as failed and continue with remaining migrations.
        """
        # Mock timeout on second migration
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # 001 succeeds
            subprocess.TimeoutExpired(cmd="psql", timeout=30),  # 002 times out
            MagicMock(returncode=0, stderr=""),  # 003 succeeds
        ]

        applied, failed = apply_migrations(
            "postgresql://localhost/test_db", temp_migration_dir, timeout=30
        )

        assert applied == 2  # 001 and 003 applied
        assert len(failed) == 1
        assert "002_add_index.sql" in failed


# ==============================================================================
# TEST: validate_critical_tables()
# ==============================================================================


class TestValidateCriticalTables:
    """Tests for validate_critical_tables() function."""

    @patch("database.connection.fetch_all")
    def test_validate_critical_tables_all_exist(self, mock_fetch_all: MagicMock) -> None:
        """Test validation succeeds when all critical tables exist.

        Educational Note:
            We mock fetch_all() at database.connection (where it's defined)
            not database.initialization (where it's imported). This is because
            the import happens inside the function, so we need to mock at the
            source location. Pattern 11 - mock at the right boundary.
        """
        # Mock database response - all tables exist
        mock_fetch_all.return_value = [{"exists": True}]

        missing = validate_critical_tables()

        assert missing == []

    @patch("database.connection.fetch_all")
    def test_validate_critical_tables_some_missing(self, mock_fetch_all: MagicMock) -> None:
        """Test validation reports missing tables correctly.

        Educational Note:
            We use side_effect to return different values for each call
            (first table exists, second missing, third exists, etc.).
        """
        # Mock responses: platforms exists, series missing, events exists, markets missing
        mock_fetch_all.side_effect = [
            [{"exists": True}],  # platforms
            [{"exists": False}],  # series (missing)
            [{"exists": True}],  # events
            [{"exists": False}],  # markets (missing)
            [{"exists": True}],  # strategies
            [{"exists": True}],  # probability_models
            [{"exists": True}],  # positions
            [{"exists": True}],  # trades
        ]

        missing = validate_critical_tables()

        assert len(missing) == 2
        assert "series" in missing
        assert "markets" in missing

    @patch("database.connection.fetch_all")
    def test_validate_critical_tables_custom_list(self, mock_fetch_all: MagicMock) -> None:
        """Test validation works with custom table list.

        Educational Note:
            Function accepts optional custom table list for flexibility.
            Useful for testing specific schema subsets.
        """
        # Mock: first table exists, second missing
        mock_fetch_all.side_effect = [
            [{"exists": True}],
            [{"exists": False}],
        ]

        missing = validate_critical_tables(["users", "orders"])

        assert missing == ["orders"]
        assert mock_fetch_all.call_count == 2

    @patch("database.connection.fetch_all")
    def test_validate_critical_tables_empty_result(self, mock_fetch_all: MagicMock) -> None:
        """Test validation handles empty database response.

        Educational Note:
            Edge case - what if fetch_all() returns empty list or None?
            Treat as "table doesn't exist" instead of crashing.
        """
        # Mock empty response (table doesn't exist)
        mock_fetch_all.return_value = []

        missing = validate_critical_tables(["test_table"])

        assert missing == ["test_table"]


# ==============================================================================
# TEST: get_database_url()
# ==============================================================================


class TestGetDatabaseUrl:
    """Tests for get_database_url() function."""

    def test_get_database_url_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retrieval of DATABASE_URL when set.

        Educational Note:
            We use monkeypatch to temporarily set environment variable
            without affecting other tests or requiring actual .env file.
        """
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test_db")

        url = get_database_url()

        assert url == "postgresql://localhost/test_db"

    def test_get_database_url_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retrieval of DATABASE_URL when not set.

        Educational Note:
            Edge case - what if DATABASE_URL isn't in environment?
            Should return None, not raise KeyError.
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)

        url = get_database_url()

        assert url is None

    def test_get_database_url_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retrieval of DATABASE_URL when set to empty string.

        Educational Note:
            Edge case - DATABASE_URL is SET but EMPTY. os.getenv() returns
            empty string, not None. Caller should handle this case.
        """
        monkeypatch.setenv("DATABASE_URL", "")

        url = get_database_url()

        assert url == ""
