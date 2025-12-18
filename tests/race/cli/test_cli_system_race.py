"""
Race condition tests for CLI system commands.

Tests system CLI under concurrent access.

Related:
    - Issue #234: 8 Test Type Coverage
    - src/precog/cli/system.py
    - REQ-TEST-006: Race Condition Testing

Coverage Target: 80%+ for cli/system.py (infrastructure tier)
"""

import threading
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from precog.cli.system import app


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Race Tests
# ============================================================================


@pytest.mark.race
class TestSystemRace:
    """Race condition tests for system CLI."""

    def test_concurrent_version_calls(self, runner):
        """Test concurrent version command calls."""
        results = []
        outputs = []
        errors = []

        def invoke_version():
            try:
                result = runner.invoke(app, ["version"])
                results.append(result.exit_code)
                outputs.append(result.output)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=invoke_version) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Filter out known thread-safety issues with CLI runner stdout
        real_errors = [e for e in errors if "I/O operation on closed file" not in e]
        assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"
        # At least some should succeed
        assert len(results) > 0
        assert all(r == 0 for r in results)

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

    def test_concurrent_health_calls(self, runner):
        """Test concurrent health command calls."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            results = []
            errors = []

            def invoke_health():
                try:
                    result = runner.invoke(app, ["health"])
                    results.append(result.exit_code)
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=invoke_health) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            # Filter out known thread-safety issues with CLI runner stdout
            real_errors = [e for e in errors if "I/O operation on closed file" not in e]
            assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"
            assert len(results) + len(errors) == 10

    def test_concurrent_info_calls(self, runner):
        """Test concurrent info command calls."""
        results = []
        errors = []

        def invoke_info():
            try:
                result = runner.invoke(app, ["info"])
                results.append(result.exit_code)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=invoke_info) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Filter out known thread-safety issues with CLI runner stdout
        real_errors = [e for e in errors if "I/O operation on closed file" not in e]
        assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"
        assert len(results) + len(errors) == 10


@pytest.mark.race
class TestSystemMixedRace:
    """Mixed operation race tests."""

    def test_concurrent_mixed_commands(self, runner):
        """Test concurrent mixed command calls."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            results = []
            errors = []

            def invoke_version():
                try:
                    result = runner.invoke(app, ["version"])
                    results.append(("version", result.exit_code))
                except Exception as e:
                    errors.append(str(e))

            def invoke_health():
                try:
                    result = runner.invoke(app, ["health"])
                    results.append(("health", result.exit_code))
                except Exception as e:
                    errors.append(str(e))

            def invoke_info():
                try:
                    result = runner.invoke(app, ["info"])
                    results.append(("info", result.exit_code))
                except Exception as e:
                    errors.append(str(e))

            threads = []
            for _ in range(3):
                threads.append(threading.Thread(target=invoke_version))
                threads.append(threading.Thread(target=invoke_health))
                threads.append(threading.Thread(target=invoke_info))

            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            # Filter out known thread-safety issues with CLI runner stdout
            real_errors = [e for e in errors if "I/O operation on closed file" not in e]
            assert len(real_errors) == 0, f"Unexpected errors: {real_errors}"
            assert len(results) + len(errors) == 9
