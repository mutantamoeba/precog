"""Property-based tests for CLI system commands.

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


class TestSystemOutputInvariants:
    """Property tests for system command output consistency."""

    @given(st.sampled_from(["health", "version", "info"]))
    @settings(max_examples=3)
    def test_subcommand_help_available(self, subcommand: str):
        """Each subcommand should have help available."""
        result = runner.invoke(app, ["system", subcommand, "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 0

    @given(st.booleans())
    @settings(max_examples=10)
    def test_help_output_always_includes_commands(self, verbose: bool):
        """Help output should always list available subcommands."""
        result = runner.invoke(app, ["system", "--help"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "health" in output_lower or "version" in output_lower or "info" in output_lower


class TestSystemHealthInvariants:
    """Property tests for health check command invariants."""

    @given(st.booleans(), st.booleans(), st.booleans())
    @settings(max_examples=20)
    def test_health_with_various_service_states(
        self, db_healthy: bool, api_healthy: bool, config_valid: bool
    ):
        """Health check should handle any combination of service states.

        Note: The health command calls both test_connection() AND get_connection(),
        so both must be mocked to prevent real database access and test pollution.
        """
        with (
            patch("precog.database.connection.test_connection") as mock_test,
            patch("precog.database.connection.get_connection") as mock_conn,
        ):
            mock_test.return_value = db_healthy
            if db_healthy:
                mock_connection = MagicMock()
                mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
                mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            else:
                mock_conn.side_effect = Exception("Connection failed")

            result = runner.invoke(app, ["system", "health"])
            # Command should complete without crashing
            assert result.exit_code in [0, 1, 2]

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=20)
    def test_health_with_various_error_messages(self, error_msg: str):
        """Health check should handle any error message from database."""
        assume(all(ord(c) >= 32 or c in "\n\t" for c in error_msg))

        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_conn.side_effect = Exception(error_msg)

            result = runner.invoke(app, ["system", "health"])
            # Should complete without crashing
            assert result.exit_code in [0, 1, 2]


class TestSystemVersionInvariants:
    """Property tests for version command invariants."""

    @given(st.booleans())
    @settings(max_examples=10)
    def test_version_always_outputs_something(self, verbose: bool):
        """Version command should always produce output."""
        result = runner.invoke(app, ["system", "version"])
        assert result.exit_code in [0, 1, 2]
        # Version should output something
        assert len(result.output) > 0 or result.exit_code != 0


class TestSystemInfoInvariants:
    """Property tests for info command invariants."""

    @given(
        st.dictionaries(
            # Windows env vars: ASCII alphanumeric + underscore only, must start with letter
            keys=st.from_regex(r"^[A-Z][A-Z0-9_]{0,19}$", fullmatch=True),
            values=st.text(
                min_size=0,
                max_size=50,
                # Only printable ASCII to avoid encoding issues on Windows
                alphabet=st.characters(min_codepoint=32, max_codepoint=126),
            ),
            min_size=0,
            max_size=10,  # Reduced to avoid env pollution
        )
    )
    @settings(max_examples=20)
    def test_info_with_various_env_configs(self, env_vars: dict):
        """Info command should handle any environment configuration.

        Note: Keys are constrained to valid Windows environment variable names
        (ASCII alphanumeric + underscore, starting with a letter) to ensure
        cross-platform compatibility.
        """
        with patch.dict("os.environ", env_vars, clear=False):
            result = runner.invoke(app, ["system", "info"])
            assert result.exit_code in [0, 1, 2]

    @given(st.integers(min_value=0, max_value=1000))
    @settings(max_examples=20)
    def test_info_with_varying_process_counts(self, process_count: int):
        """Info command should handle any number of background processes."""
        # Info command doesn't call get_process_info - just mock the connection
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_connection = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            result = runner.invoke(app, ["system", "info"])
            assert result.exit_code in [0, 1, 2]


class TestSystemCommandSequences:
    """Property tests for system command sequences."""

    @given(st.lists(st.sampled_from(["health", "version", "info"]), min_size=1, max_size=10))
    @settings(max_examples=20, deadline=None)  # CLI invocations can exceed 200ms deadline
    def test_command_sequence_stability(self, commands: list):
        """Any sequence of system commands should not crash."""
        with patch("precog.database.connection.get_connection") as mock_conn:
            mock_connection = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_connection)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)

            for cmd in commands:
                result = runner.invoke(app, ["system", cmd])
                assert result.exit_code in [0, 1, 2]
