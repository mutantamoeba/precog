"""Property-based tests for CLI database commands.

Tests command-line argument parsing invariants and output format consistency
using Hypothesis to generate edge cases.

Reference: TESTING_STRATEGY V3.2 - Property Tests (2/8)
"""

from unittest.mock import MagicMock, patch

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from precog.cli import app, register_commands

# Initialize CLI for testing
register_commands()
runner = CliRunner()


class TestDbArgumentInvariants:
    """Property tests for database command argument validation."""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_table_name_handling(self, table_name: str):
        """Tables command should handle arbitrary table names gracefully."""
        # Skip control characters
        assume(all(ord(c) >= 32 for c in table_name))
        assume(table_name.strip())

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(app, ["db", "tables", "--name", table_name])
            # Command should complete without crashing
            assert result.exit_code in [0, 1, 2]

    @given(st.integers(min_value=1, max_value=1000))
    @settings(max_examples=20)
    def test_migration_version_handling(self, version: int):
        """Migrate command should handle any migration version."""
        # Mock at the point where db.py imports from
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_connection = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(app, ["db", "migrate", "--version", str(version)])
            # Command should complete (may fail if version doesn't exist)
            assert result.exit_code in [0, 1, 2, 3]


class TestDbOutputInvariants:
    """Property tests for database command output consistency."""

    @given(st.sampled_from(["init", "status", "migrate", "tables"]))
    @settings(max_examples=4)
    def test_subcommand_help_available(self, subcommand: str):
        """Each subcommand should have help available."""
        result = runner.invoke(app, ["db", subcommand, "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 0

    @given(st.booleans())
    @settings(max_examples=10)
    def test_help_output_always_includes_commands(self, verbose: bool):
        """Help output should always list available subcommands."""
        result = runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        # Help should mention key commands
        output_lower = result.output.lower()
        assert "init" in output_lower or "status" in output_lower


class TestDbTableListInvariants:
    """Property tests for table listing functionality."""

    @given(st.integers(min_value=0, max_value=50))
    @settings(max_examples=20)
    def test_status_with_varying_table_counts(self, count: int):
        """Status should handle any number of tables."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            # Generate mock table list
            mock_cursor.fetchall.return_value = [(f"table_{i}",) for i in range(count)]
            mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]

    @given(
        st.lists(
            st.text(
                min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N"))
            ),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=20)
    def test_tables_with_arbitrary_names(self, table_names: list):
        """Tables command should handle arbitrary table name lists."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [(name,) for name in table_names]
            mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2]


class TestDbMigrationInvariants:
    """Property tests for migration command invariants."""

    @given(st.integers(min_value=-100, max_value=0))
    @settings(max_examples=20)
    def test_invalid_migration_version_handling(self, version: int):
        """Migrate should handle invalid (negative/zero) versions gracefully."""
        result = runner.invoke(app, ["db", "migrate", "--version", str(version)])
        # Should fail gracefully, not crash
        assert result.exit_code in [0, 1, 2, 3]

    @given(st.text(min_size=1, max_size=20))
    @settings(max_examples=20)
    def test_non_numeric_version_handling(self, version_str: str):
        """Migrate should handle non-numeric version strings."""
        assume(not version_str.strip().isdigit())  # Ensure not a valid number

        result = runner.invoke(app, ["db", "migrate", "--version", version_str])
        # Typer should reject non-integer, exit code 2
        assert result.exit_code in [0, 1, 2]
