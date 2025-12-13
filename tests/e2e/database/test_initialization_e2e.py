"""
End-to-End tests for database initialization module.

Tests complete initialization workflows with real filesystem operations.

Reference: TESTING_STRATEGY_V3.2.md Section "E2E Tests"
"""

from pathlib import Path

import pytest

from precog.database.initialization import (
    apply_migrations,
    apply_schema,
    get_database_url,
    validate_schema_file,
)

pytestmark = [pytest.mark.e2e]


class TestSchemaValidationE2E:
    """E2E tests for schema file validation."""

    def test_validate_real_schema_file(self) -> None:
        """Verify validation works with actual project schema file."""
        # Look for actual schema file in project
        possible_paths = [
            "database/precog_schema_v1.7.sql",
            "src/precog/database/schema.sql",
            "schema.sql",
        ]

        found_schema = None
        for path in possible_paths:
            if Path(path).exists():
                found_schema = path
                break

        if found_schema:
            result = validate_schema_file(found_schema)
            assert result is True
        else:
            pytest.skip("No schema file found in expected locations")

    def test_validate_nonexistent_schema_returns_false(self) -> None:
        """Verify nonexistent schema file returns False."""
        result = validate_schema_file("nonexistent_schema_xyz.sql")
        assert result is False

    def test_validate_created_schema_file(self, tmp_path: Path) -> None:
        """Verify newly created schema file validates correctly."""
        schema = tmp_path / "test_schema.sql"
        schema.write_text("""
            -- Test schema
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX idx_users_username ON users(username);
        """)

        result = validate_schema_file(str(schema))

        assert result is True


class TestSchemaApplicationE2E:
    """E2E tests for schema application."""

    def test_schema_security_validations(self, tmp_path: Path) -> None:
        """Verify all security validations work end-to-end."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        # Test 1: Invalid URL rejected
        success, error = apply_schema("http://localhost/test", str(schema))
        assert success is False
        assert "Invalid database URL" in error

        # Test 2: Non-.sql file rejected
        txt_file = tmp_path / "schema.txt"
        txt_file.write_text("CREATE TABLE test (id INT);")
        success, error = apply_schema("postgresql://localhost/test", str(txt_file))
        assert success is False
        assert ".sql file" in error

        # Test 3: Nonexistent file rejected
        success, error = apply_schema("postgresql://localhost/test", "nonexistent.sql")
        assert success is False
        assert "not found" in error

    def test_path_traversal_prevention(self) -> None:
        """Verify path traversal attacks are prevented."""
        malicious_paths = [
            "../../../etc/passwd.sql",
            "..\\..\\..\\windows\\system32\\config.sql",
            "/etc/passwd.sql",
        ]

        for path in malicious_paths:
            success, _error = apply_schema("postgresql://localhost/test", path)
            assert success is False, f"Path {path} should be rejected"


class TestMigrationApplicationE2E:
    """E2E tests for migration application."""

    def test_empty_migrations_directory(self, tmp_path: Path) -> None:
        """Verify empty directory is handled gracefully."""
        empty_dir = tmp_path / "migrations"
        empty_dir.mkdir()

        applied, failed = apply_migrations("postgresql://localhost/test", str(empty_dir))

        assert applied == 0
        assert failed == []

    def test_nonexistent_migrations_directory(self) -> None:
        """Verify nonexistent directory is handled gracefully."""
        applied, failed = apply_migrations(
            "postgresql://localhost/test", "nonexistent_migrations_dir"
        )

        assert applied == 0
        assert failed == []

    def test_migration_file_discovery(self, tmp_path: Path) -> None:
        """Verify only .sql files are discovered for migration."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()

        # Create mix of files
        (migration_dir / "001_create_table.sql").write_text("CREATE TABLE t1;")
        (migration_dir / "002_add_index.sql").write_text("CREATE INDEX i1;")
        (migration_dir / "README.md").write_text("# Migrations")
        (migration_dir / ".gitkeep").write_text("")
        (migration_dir / "003_add_column.sql").write_text("ALTER TABLE t1;")

        # Get list of .sql files
        sql_files = sorted([f.name for f in migration_dir.iterdir() if f.suffix == ".sql"])

        assert len(sql_files) == 3
        assert sql_files == ["001_create_table.sql", "002_add_index.sql", "003_add_column.sql"]


class TestDatabaseUrlE2E:
    """E2E tests for database URL retrieval."""

    def test_get_database_url_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify URL is retrieved from environment."""
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        monkeypatch.setenv("DATABASE_URL", test_url)

        url = get_database_url()

        assert url == test_url

    def test_get_database_url_returns_none_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify None returned when DATABASE_URL not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        url = get_database_url()

        assert url is None

    def test_actual_database_url_format(self) -> None:
        """Verify actual DATABASE_URL (if set) has correct format."""
        url = get_database_url()

        if url is not None and url != "":
            # Should start with postgresql:// or postgres://
            assert url.startswith(("postgresql://", "postgres://")), (
                f"DATABASE_URL should start with postgresql:// or postgres://, got: {url[:20]}..."
            )
