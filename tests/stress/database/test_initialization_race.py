"""
Race condition tests for database initialization module.

Tests for race conditions in concurrent operations.

Reference: TESTING_STRATEGY_V3.2.md Section "Race Tests"
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.initialization import (
    apply_migrations,
    apply_schema,
    get_database_url,
    validate_schema_file,
)

pytestmark = [pytest.mark.race]


class TestValidateSchemaFileRace:
    """Race condition tests for schema validation."""

    def test_concurrent_validation_no_corruption(self, tmp_path: Path) -> None:
        """Verify concurrent validation doesn't corrupt results."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        results = []
        errors = []
        lock = threading.Lock()

        def validate() -> None:
            try:
                result = validate_schema_file(str(schema))
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r is True for r in results)

    def test_validation_while_file_being_written(self, tmp_path: Path) -> None:
        """Test validation during concurrent file writes."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        results = []
        errors = []
        lock = threading.Lock()
        write_count = [0]

        def validate_repeatedly() -> None:
            for _ in range(50):
                try:
                    result = validate_schema_file(str(schema))
                    with lock:
                        results.append(result)
                except Exception as e:
                    with lock:
                        errors.append(e)

        def write_repeatedly() -> None:
            for i in range(50):
                try:
                    schema.write_text(f"CREATE TABLE test_{i} (id INT);")
                    with lock:
                        write_count[0] += 1
                except Exception:
                    pass

        t1 = threading.Thread(target=validate_repeatedly)
        t2 = threading.Thread(target=write_repeatedly)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        # All validations should return True (file always exists)
        assert all(r is True for r in results)


class TestApplySchemaRace:
    """Race condition tests for schema application."""

    @patch("precog.database.initialization.subprocess.run")
    def test_concurrent_applications_no_corruption(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Verify concurrent schema applications don't corrupt."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        results = []
        errors = []
        lock = threading.Lock()

        def apply() -> None:
            try:
                result = apply_schema("postgresql://localhost/test", str(schema))
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=apply) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 50
        assert all(r[0] is True for r in results)


class TestApplyMigrationsRace:
    """Race condition tests for migration application."""

    @patch("precog.database.initialization.subprocess.run")
    def test_concurrent_migration_discovery(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test concurrent migration discovery doesn't miss files."""
        migration_dir = tmp_path / "migrations"
        migration_dir.mkdir()

        # Create migrations
        for i in range(10):
            (migration_dir / f"{i:03d}_migration.sql").write_text(f"SELECT {i};")

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        results = []
        errors = []
        lock = threading.Lock()

        def apply() -> None:
            try:
                applied, failed = apply_migrations(
                    "postgresql://localhost/test", str(migration_dir)
                )
                with lock:
                    results.append((applied, failed))
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=apply) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 20
        # Each run should find 10 migrations
        assert all(r[0] == 10 for r in results)


class TestGetDatabaseUrlRace:
    """Race condition tests for URL retrieval."""

    def test_concurrent_retrieval_consistent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify concurrent retrieval returns consistent results."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        results = []
        errors = []
        lock = threading.Lock()

        def get_url() -> None:
            try:
                url = get_database_url()
                with lock:
                    results.append(url)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=get_url) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"
        assert len(results) == 100
        assert all(r == "postgresql://localhost/test" for r in results)
