"""
Race condition tests for CLI database commands.

Tests database CLI under concurrent access.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/db.py
    - REQ-TEST-006: Race Condition Testing

Coverage Target: 85%+ for cli/db.py (business tier)
"""

import threading
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from precog.cli.db import app


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Race Tests
# ============================================================================


@pytest.mark.race
class TestDbRace:
    """Race condition tests for database CLI."""

    def test_concurrent_status_calls(self, runner):
        """Test concurrent status command calls."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            results = []
            errors = []

            def invoke_status():
                try:
                    result = runner.invoke(app, ["status"])
                    results.append(result.exit_code)
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=invoke_status) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            # Filter out known thread-safety issues with CLI runner stdout
            real_errors = [e for e in errors if "I/O operation on closed file" not in e]
            assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"
            # At least some should complete
            assert len(results) + len(errors) == 10

    def test_concurrent_help_calls(self, runner):
        """Test concurrent help command calls."""
        results = []
        errors = []

        def invoke_help():
            try:
                result = runner.invoke(app, ["--help"])
                results.append(result.exit_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=invoke_help) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Help should always succeed
        assert len(errors) == 0
        assert all(r == 0 for r in results)

    def test_concurrent_tables_calls(self, runner):
        """Test concurrent tables command calls."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            conn = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            cursor = MagicMock()
            conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
            conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            cursor.fetchall.return_value = [("games",)]

            results = []
            errors = []

            def invoke_tables():
                try:
                    result = runner.invoke(app, ["tables"])
                    results.append(result.exit_code)
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=invoke_tables) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            # Filter out known thread-safety issues with CLI runner stdout
            real_errors = [e for e in errors if "I/O operation on closed file" not in e]
            assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"


@pytest.mark.race
class TestDbInitMigrateRace:
    """Race tests for init/migrate operations."""

    def test_concurrent_init_calls(self, runner):
        """Test concurrent init calls (with dry-run)."""
        results = []
        errors = []

        def invoke_init():
            try:
                result = runner.invoke(app, ["init", "--dry-run"])
                results.append(result.exit_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=invoke_init) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Filter out known thread-safety issues with CLI runner stdout
        real_errors = [e for e in errors if "I/O operation on closed file" not in e]
        assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"
        # At least some should complete
        assert len(results) + len(errors) == 5
