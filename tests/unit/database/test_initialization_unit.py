"""
Unit tests for database initialization module.

Tests individual functions in isolation with mocked dependencies.

Reference: TESTING_STRATEGY_V3.2.md Section "Unit Tests"
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.initialization import (
    apply_migrations,
    apply_schema,
    get_database_url,
    validate_schema_file,
)

pytestmark = [pytest.mark.unit]


class TestValidateSchemaFileUnit:
    """Unit tests for validate_schema_file function."""

    def test_returns_true_for_existing_readable_file(self, tmp_path: Path) -> None:
        """Verify function returns True for valid schema file."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT);")

        result = validate_schema_file(str(schema_file))

        assert result is True

    def test_returns_false_for_nonexistent_file(self) -> None:
        """Verify function returns False for nonexistent file."""
        result = validate_schema_file("nonexistent_file.sql")

        assert result is False

    def test_returns_false_for_empty_path(self) -> None:
        """Verify function returns False for empty path."""
        result = validate_schema_file("")

        assert result is False


class TestApplySchemaUnit:
    """Unit tests for apply_schema function."""

    @patch("precog.database.initialization.subprocess.run")
    def test_returns_success_on_successful_psql(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify successful schema application returns (True, '')."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        success, error = apply_schema("postgresql://localhost/test", str(schema_file))

        assert success is True
        assert error == ""

    def test_rejects_invalid_db_url(self, tmp_path: Path) -> None:
        """Verify invalid database URL is rejected."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT);")

        success, error = apply_schema("invalid-url", str(schema_file))

        assert success is False
        assert "Invalid database URL" in error

    def test_rejects_non_sql_file(self, tmp_path: Path) -> None:
        """Verify non-.sql files are rejected."""
        txt_file = tmp_path / "schema.txt"
        txt_file.write_text("CREATE TABLE test (id INT);")

        success, error = apply_schema("postgresql://localhost/test", str(txt_file))

        assert success is False
        assert ".sql file" in error

    def test_rejects_nonexistent_file(self) -> None:
        """Verify nonexistent file is rejected."""
        success, error = apply_schema("postgresql://localhost/test", "nonexistent.sql")

        assert success is False
        assert "not found" in error

    @patch("precog.database.initialization.subprocess.run")
    def test_handles_psql_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify psql not found is handled gracefully."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT);")
        mock_run.side_effect = FileNotFoundError()

        success, error = apply_schema("postgresql://localhost/test", str(schema_file))

        assert success is False
        assert "psql command not found" in error

    @patch("precog.database.initialization.subprocess.run")
    def test_handles_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify timeout is handled gracefully."""
        schema_file = tmp_path / "schema.sql"
        schema_file.write_text("CREATE TABLE test (id INT);")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="psql", timeout=30)

        success, error = apply_schema("postgresql://localhost/test", str(schema_file), timeout=30)

        assert success is False
        assert "timed out" in error


class TestApplyMigrationsUnit:
    """Unit tests for apply_migrations function."""

    def test_returns_zero_for_invalid_db_url(self, tmp_path: Path) -> None:
        """Verify invalid DB URL returns (0, [])."""
        applied, failed = apply_migrations("invalid-url", str(tmp_path))

        assert applied == 0
        assert failed == []

    def test_returns_zero_for_nonexistent_directory(self) -> None:
        """Verify nonexistent directory returns (0, [])."""
        applied, failed = apply_migrations("postgresql://localhost/test", "nonexistent")

        assert applied == 0
        assert failed == []

    def test_returns_zero_for_empty_directory(self, tmp_path: Path) -> None:
        """Verify empty directory returns (0, [])."""
        empty_dir = tmp_path / "migrations"
        empty_dir.mkdir()

        applied, failed = apply_migrations("postgresql://localhost/test", str(empty_dir))

        assert applied == 0
        assert failed == []

    @patch("precog.database.initialization.subprocess.run")
    def test_applies_migrations_in_order(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify migrations are applied in alphabetical order."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()
        (migration_dir / "001_first.sql").write_text("CREATE TABLE t1 (id INT);")
        (migration_dir / "002_second.sql").write_text("CREATE TABLE t2 (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        applied, failed = apply_migrations("postgresql://localhost/test", str(migration_dir))

        assert applied == 2
        assert failed == []
        assert mock_run.call_count == 2


class TestGetDatabaseUrlUnit:
    """Unit tests for get_database_url function."""

    def test_returns_url_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify URL is returned when environment variable is set."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        url = get_database_url()

        assert url == "postgresql://localhost/test"

    def test_returns_none_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify None is returned when environment variable is not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        url = get_database_url()

        assert url is None

    def test_returns_empty_string_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify empty string is returned when variable is empty."""
        monkeypatch.setenv("DATABASE_URL", "")

        url = get_database_url()

        assert url == ""
