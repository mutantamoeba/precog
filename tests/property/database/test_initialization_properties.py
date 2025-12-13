"""
Property-based tests for database initialization module.

Tests mathematical properties and invariants using Hypothesis.

Reference: TESTING_STRATEGY_V3.2.md Section "Property Tests"
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.database.initialization import (
    apply_schema,
    get_database_url,
    validate_schema_file,
)

pytestmark = [pytest.mark.property]


class TestValidateSchemaFileProperties:
    """Property tests for validate_schema_file function."""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_nonexistent_paths_return_false(self, path: str) -> None:
        """Any nonexistent path should return False."""
        # Filter out paths that might accidentally exist
        if not Path(path).exists():
            result = validate_schema_file(path)
            assert result is False

    @given(st.text(min_size=0, max_size=10))
    @settings(max_examples=20)
    def test_returns_boolean(self, path: str) -> None:
        """Function should always return a boolean."""
        result = validate_schema_file(path)
        assert isinstance(result, bool)


class TestApplySchemaProperties:
    """Property tests for apply_schema function."""

    @given(
        st.text(min_size=1, max_size=50).filter(
            lambda x: not x.startswith(("postgresql://", "postgres://"))
        )
    )
    @settings(max_examples=30)
    def test_invalid_urls_always_fail(self, url: str) -> None:
        """Any non-PostgreSQL URL should fail."""
        success, error = apply_schema(url, "schema.sql")
        assert success is False
        assert "Invalid database URL" in error

    @given(st.sampled_from(["postgresql://", "postgres://"]))
    def test_valid_url_prefixes_pass_url_check(self, prefix: str) -> None:
        """Valid URL prefixes should pass URL validation."""
        # Will fail on file check, not URL check
        success, error = apply_schema(f"{prefix}localhost/test", "nonexistent.sql")
        assert success is False
        assert "Invalid database URL" not in error

    @given(st.sampled_from([".txt", ".py", ".md", ".yaml", ".json"]))
    def test_non_sql_extensions_rejected(self, ext: str) -> None:
        """Non-.sql file extensions should be rejected."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / f"schema{ext}"
            test_file.write_text("CREATE TABLE test (id INT);")

            success, error = apply_schema("postgresql://localhost/test", str(test_file))

            assert success is False
            assert ".sql file" in error

    @given(st.integers(min_value=1, max_value=300))
    @settings(max_examples=10)
    def test_timeout_parameter_accepted(self, timeout: int) -> None:
        """Any positive timeout value should be accepted."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            schema_file = Path(tmp_dir) / "schema.sql"
            schema_file.write_text("CREATE TABLE test (id INT);")

            with patch("precog.database.initialization.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")

                _success, _error = apply_schema(
                    "postgresql://localhost/test", str(schema_file), timeout=timeout
                )

                # Verify timeout was passed to subprocess.run
                mock_run.assert_called_once()
                assert mock_run.call_args[1]["timeout"] == timeout


class TestGetDatabaseUrlProperties:
    """Property tests for get_database_url function."""

    @given(st.text(min_size=1, max_size=200).filter(lambda x: "\x00" not in x))
    @settings(max_examples=30)
    def test_returns_exact_env_value(self, url: str) -> None:
        """Function should return exact value from environment.

        Note: Filter excludes null characters because Windows cannot set
        environment variables containing null bytes (ValueError: embedded null character).
        """
        import os

        old_value = os.environ.get("DATABASE_URL")
        try:
            os.environ["DATABASE_URL"] = url
            result = get_database_url()
            assert result == url
        finally:
            if old_value is not None:
                os.environ["DATABASE_URL"] = old_value
            elif "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]

    def test_returns_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Function should return None when env var is unset."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        result = get_database_url()

        assert result is None
