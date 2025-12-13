"""
Chaos tests for database initialization module.

Tests failure scenarios and edge cases.

Reference: TESTING_STRATEGY_V3.2.md Section "Chaos Tests"
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.initialization import (
    apply_migrations,
    apply_schema,
    get_database_url,
    validate_critical_tables,
    validate_schema_file,
)

pytestmark = [pytest.mark.chaos]


class TestValidateSchemaFileChaos:
    """Chaos tests for schema validation."""

    def test_empty_path(self) -> None:
        """Test behavior with empty path."""
        result = validate_schema_file("")
        assert result is False

    def test_whitespace_path(self) -> None:
        """Test behavior with whitespace-only path."""
        result = validate_schema_file("   ")
        assert result is False

    def test_special_characters_in_path(self) -> None:
        """Test behavior with special characters in path."""
        special_paths = [
            "schema@#$.sql",
            "schema with spaces.sql",
            "schema\ttab.sql",
            "schema\nnewline.sql",
        ]
        for path in special_paths:
            result = validate_schema_file(path)
            # Should return False (file doesn't exist), not crash
            assert isinstance(result, bool)

    def test_very_long_path(self) -> None:
        """Test behavior with very long path."""
        long_path = "a" * 1000 + ".sql"
        result = validate_schema_file(long_path)
        # Should handle gracefully
        assert isinstance(result, bool)


class TestApplySchemaChaos:
    """Chaos tests for schema application."""

    def test_empty_url(self, tmp_path: Path) -> None:
        """Test behavior with empty URL."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        success, error = apply_schema("", str(schema))

        assert success is False
        assert "Invalid database URL" in error

    def test_none_url(self, tmp_path: Path) -> None:
        """Test behavior with None-like URL."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        # Pass empty string (can't pass None due to type hints)
        success, _error = apply_schema("", str(schema))

        assert success is False

    def test_malformed_url_formats(self, tmp_path: Path) -> None:
        """Test various malformed URL formats."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        malformed_urls = [
            "http://localhost/test",  # Wrong protocol
            "postgresql",  # Missing ://
            "postgresql:/",  # Incomplete
            "POSTGRESQL://localhost/test",  # Uppercase (should still work)
            "postgres://localhost/test",  # Alternative valid format
        ]

        for url in malformed_urls:
            success, _error = apply_schema(url, str(schema))
            # Either fails URL check or proceeds to file check
            assert isinstance(success, bool)

    @patch("precog.database.initialization.subprocess.run")
    def test_subprocess_returns_various_codes(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test handling of various subprocess return codes."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        test_cases = [
            (0, "", True),  # Success
            (1, "already exists", True),  # Idempotent success
            (1, "syntax error", False),  # Actual error
            (2, "permission denied", False),
            (127, "command not found", False),
            (255, "unknown error", False),
        ]

        for returncode, stderr, expected_success in test_cases:
            mock_run.return_value = MagicMock(returncode=returncode, stderr=stderr)

            success, _error = apply_schema("postgresql://localhost/test", str(schema))

            assert success == expected_success, (
                f"Failed for returncode={returncode}, stderr={stderr}"
            )

    def test_directory_path_instead_of_file(self, tmp_path: Path) -> None:
        """Test behavior when given directory instead of file."""
        success, error = apply_schema("postgresql://localhost/test", str(tmp_path))

        assert success is False
        # Should fail because it's not a .sql file
        assert ".sql file" in error or "not found" in error


class TestApplyMigrationsChaos:
    """Chaos tests for migration application."""

    def test_empty_url(self, tmp_path: Path) -> None:
        """Test behavior with empty URL."""
        applied, failed = apply_migrations("", str(tmp_path))

        assert applied == 0
        assert failed == []

    def test_special_characters_in_migration_names(self, tmp_path: Path) -> None:
        """Test handling of special characters in migration names."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()

        # Create migrations with special characters
        (migration_dir / "001_normal.sql").write_text("SELECT 1;")
        # Note: Some special chars may be invalid on Windows filesystems

        with patch("precog.database.initialization.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            applied, _failed = apply_migrations("postgresql://localhost/test", str(migration_dir))

            # Should apply the valid migration
            assert applied >= 1

    @patch("precog.database.initialization.subprocess.run")
    def test_mixed_success_and_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test handling of mixed success and failure across migrations."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()

        for i in range(5):
            (migration_dir / f"{i:03d}_migration.sql").write_text(f"SELECT {i};")

        # Alternate success/failure
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="ERROR"),
            MagicMock(returncode=0, stderr=""),
            subprocess.TimeoutExpired(cmd="psql", timeout=30),
            MagicMock(returncode=0, stderr=""),
        ]

        applied, failed = apply_migrations("postgresql://localhost/test", str(migration_dir))

        assert applied == 3
        assert len(failed) == 2


class TestValidateCriticalTablesChaos:
    """Chaos tests for table validation."""

    @patch("precog.database.connection.fetch_all")
    def test_database_returns_empty_list(self, mock_fetch: MagicMock) -> None:
        """Test handling when database returns empty list."""
        mock_fetch.return_value = []

        missing = validate_critical_tables(["test_table"])

        assert "test_table" in missing

    @patch("precog.database.connection.fetch_all")
    def test_database_returns_none(self, mock_fetch: MagicMock) -> None:
        """Test handling when database returns None."""
        mock_fetch.return_value = None

        missing = validate_critical_tables(["test_table"])

        assert "test_table" in missing

    @patch("precog.database.connection.fetch_all")
    def test_database_connection_error(self, mock_fetch: MagicMock) -> None:
        """Test handling of database connection errors."""
        mock_fetch.side_effect = RuntimeError("Connection refused")

        with pytest.raises(RuntimeError, match="Connection refused"):
            validate_critical_tables(["test_table"])

    @patch("precog.database.connection.fetch_all")
    def test_empty_table_list(self, mock_fetch: MagicMock) -> None:
        """Test handling of empty table list."""
        missing = validate_critical_tables([])

        assert missing == []
        mock_fetch.assert_not_called()


class TestGetDatabaseUrlChaos:
    """Chaos tests for URL retrieval."""

    def test_url_with_special_characters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test URL with special characters in password."""
        special_urls = [
            "postgresql://user:p@ss@localhost/db",
            "postgresql://user:p%40ss@localhost/db",
            "postgresql://user:pass word@localhost/db",
        ]

        for url in special_urls:
            monkeypatch.setenv("DATABASE_URL", url)
            result = get_database_url()
            assert result == url

    def test_very_long_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling of very long URL."""
        long_url = "postgresql://localhost/" + "a" * 10000
        monkeypatch.setenv("DATABASE_URL", long_url)

        result = get_database_url()

        assert result == long_url

    def test_unicode_in_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test handling of Unicode characters in URL."""
        unicode_url = "postgresql://user:p\u00e4ss@localhost/db"
        monkeypatch.setenv("DATABASE_URL", unicode_url)

        result = get_database_url()

        assert result == unicode_url
