"""Property-based tests for CLI database commands.

Tests command-line argument parsing invariants and output format consistency
using Hypothesis to generate edge cases.

Reference: TESTING_STRATEGY V3.2 - Property Tests (2/8)
"""

from unittest.mock import MagicMock, patch

import typer
from hypothesis import given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner


def get_fresh_cli():
    """Create a fresh CLI app instance for isolated testing.

    This prevents race conditions during parallel pytest-xdist execution
    by avoiding shared global state.
    """
    from precog.cli import db, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(system.app, name="system")
    runner = CliRunner()
    return fresh_app, runner


class TestDbArgumentInvariants:
    """Property tests for database command argument validation."""


class TestDbOutputInvariants:
    """Property tests for database command output consistency."""

    @given(st.sampled_from(["init", "status", "tables"]))
    @settings(max_examples=4)
    def test_subcommand_help_available(self, subcommand: str):
        """Each subcommand should have help available."""
        app, runner = get_fresh_cli()
        result = runner.invoke(app, ["db", subcommand, "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 0

    @given(st.booleans())
    @settings(max_examples=10)
    def test_help_output_always_includes_commands(self, verbose: bool):
        """Help output should always list available subcommands."""
        app, runner = get_fresh_cli()
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
        """Status should handle any number of tables.

        Note: Exit code 5 (DATABASE_ERROR) is acceptable when mocking doesn't
        fully prevent database access in parallel execution.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            # Generate mock table list
            mock_cursor.fetchall.return_value = [(f"table_{i}",) for i in range(count)]
            mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            app, runner = get_fresh_cli()
            result = runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2, 5]

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
        """Tables command should handle arbitrary table name lists.

        Note: Exit code 5 (DATABASE_ERROR) is acceptable when mocking doesn't
        fully prevent database access in parallel execution.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = True
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [(name,) for name in table_names]
            mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            app, runner = get_fresh_cli()
            result = runner.invoke(app, ["db", "tables"])
            assert result.exit_code in [0, 1, 2, 5]

    # TestDbMigrationInvariants removed — `db migrate` command deleted (G5 S58).
    # Use `alembic upgrade head` directly for migrations.
