"""
Stress tests for database initialization module.

Tests high-volume operations to validate behavior under load.

Reference: TESTING_STRATEGY_V3.2.md Section "Stress Tests"
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from precog.database.initialization import (
    apply_schema,
    get_database_url,
    validate_schema_file,
)

pytestmark = [pytest.mark.stress]


class TestValidateSchemaFileStress:
    """Stress tests for schema file validation."""

    def test_concurrent_validation_same_file(self, tmp_path: Path) -> None:
        """Test concurrent validation of the same file."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        results = []
        lock = threading.Lock()

        def validate() -> bool:
            result = validate_schema_file(str(schema))
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(validate) for _ in range(100)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100
        assert all(r is True for r in results)

    def test_concurrent_validation_different_files(self, tmp_path: Path) -> None:
        """Test concurrent validation of different files."""
        # Create 20 schema files
        files = []
        for i in range(20):
            f = tmp_path / f"schema_{i}.sql"
            f.write_text(f"CREATE TABLE test_{i} (id INT);")
            files.append(str(f))

        results = []
        lock = threading.Lock()

        def validate_file(path: str) -> bool:
            result = validate_schema_file(path)
            with lock:
                results.append((path, result))
            return result

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(validate_file, f) for f in files * 5]  # 100 total
            for future in as_completed(futures):
                future.result()

        assert len(results) == 100
        assert all(r[1] is True for r in results)

    def test_rapid_validation_calls(self, tmp_path: Path) -> None:
        """Test rapid sequential validation calls."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")

        for _ in range(1000):
            result = validate_schema_file(str(schema))
            assert result is True


class TestApplySchemaStress:
    """Stress tests for schema application."""

    @patch("precog.database.initialization.subprocess.run")
    def test_concurrent_schema_applications(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test concurrent schema application calls."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        results = []
        lock = threading.Lock()

        def apply() -> tuple[bool, str]:
            result = apply_schema("postgresql://localhost/test", str(schema))
            with lock:
                results.append(result)
            return result

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(apply) for _ in range(60)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 60
        assert all(r[0] is True for r in results)

    @patch("precog.database.initialization.subprocess.run")
    def test_sustained_schema_application_load(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test sustained schema application under load."""
        schema = tmp_path / "schema.sql"
        schema.write_text("CREATE TABLE test (id INT);")
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        for _ in range(500):
            success, _error = apply_schema("postgresql://localhost/test", str(schema))
            assert success is True


class TestGetDatabaseUrlStress:
    """Stress tests for database URL retrieval."""

    def test_concurrent_url_retrieval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test concurrent URL retrieval."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        results = []
        lock = threading.Lock()

        def get_url() -> str | None:
            url = get_database_url()
            with lock:
                results.append(url)
            return url

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(get_url) for _ in range(200)]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 200
        assert all(r == "postgresql://localhost/test" for r in results)

    def test_rapid_url_retrieval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rapid sequential URL retrieval."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        for _ in range(10000):
            url = get_database_url()
            assert url == "postgresql://localhost/test"
