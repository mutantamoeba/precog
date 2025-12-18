"""
Unit tests for main.py CLI entry point.

The main.py is now a thin wrapper that:
1. Imports the Typer app from precog.cli
2. Registers all command groups
3. Runs the application

Tests verify the entry point works and commands are properly registered.

Related:
    - Issue #204: CLI Refactor
    - src/precog/cli/ package for command implementations
    - REQ-CLI-001: CLI Framework (Typer)

Note:
    Command-specific tests are in tests/unit/cli/ for each CLI module:
    - test_cli_scheduler.py: Scheduler commands (start, stop, status, poll-once)
    - test_cli_db.py: Database commands (init, status, migrate, tables)
    - test_cli_system.py: System commands (health, version, info)
    - test_cli_kalshi.py: Kalshi commands (balance, markets, positions, fills)
    - test_cli_espn.py: ESPN commands (scores, schedule, live, status)
    - test_cli_config.py: Config commands (show, validate, env)
    - test_cli_data.py: Data commands (seed, verify, sources, stats)
"""

import pytest
from typer.testing import CliRunner

from precog.cli import app, register_commands

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def runner() -> CliRunner:
    """Create Typer CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def setup_commands():
    """Ensure commands are registered before each test."""
    register_commands()


# ============================================================================
# Test Classes
# ============================================================================


class TestMainEntryPoint:
    """Test the main.py entry point functionality."""

    def test_app_exists(self):
        """Test that the Typer app is properly initialized."""
        assert app is not None
        assert hasattr(app, "command")

    def test_help_command(self, runner):
        """Test --help shows available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Should show command groups
        assert "kalshi" in result.stdout.lower() or "Commands" in result.stdout
        assert "espn" in result.stdout.lower() or "scheduler" in result.stdout.lower()

    def test_version_accessible(self, runner):
        """Test system version command is accessible."""
        result = runner.invoke(app, ["system", "version"])

        # Should not error (may need mocking for actual version)
        assert result.exit_code in [0, 1]  # 0 success or 1 if deps missing

    def test_command_groups_registered(self, runner):
        """Test all command groups are registered."""
        result = runner.invoke(app, ["--help"])

        # All command groups should be visible
        output_lower = result.stdout.lower()
        expected_groups = ["kalshi", "espn", "data", "db", "scheduler", "config", "system"]

        for group in expected_groups:
            assert group in output_lower, f"Command group '{group}' not found in help output"


class TestSubcommandAccess:
    """Test that subcommands are accessible."""

    def test_kalshi_help(self, runner):
        """Test kalshi subcommand help is accessible."""
        result = runner.invoke(app, ["kalshi", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "balance" in output_lower or "markets" in output_lower

    def test_espn_help(self, runner):
        """Test espn subcommand help is accessible."""
        result = runner.invoke(app, ["espn", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "scores" in output_lower or "live" in output_lower

    def test_db_help(self, runner):
        """Test db subcommand help is accessible."""
        result = runner.invoke(app, ["db", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "init" in output_lower or "status" in output_lower

    def test_scheduler_help(self, runner):
        """Test scheduler subcommand help is accessible."""
        result = runner.invoke(app, ["scheduler", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "start" in output_lower or "stop" in output_lower

    def test_config_help(self, runner):
        """Test config subcommand help is accessible."""
        result = runner.invoke(app, ["config", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "show" in output_lower or "env" in output_lower

    def test_system_help(self, runner):
        """Test system subcommand help is accessible."""
        result = runner.invoke(app, ["system", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "health" in output_lower or "version" in output_lower

    def test_data_help(self, runner):
        """Test data subcommand help is accessible."""
        result = runner.invoke(app, ["data", "--help"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "seed" in output_lower or "verify" in output_lower


class TestInvalidCommands:
    """Test handling of invalid commands."""

    def test_invalid_command(self, runner):
        """Test that invalid commands return error."""
        result = runner.invoke(app, ["nonexistent-command"])

        assert result.exit_code != 0

    def test_old_command_format_fails(self, runner):
        """Test that old command format (fetch-balance) is rejected."""
        result = runner.invoke(app, ["fetch-balance"])

        assert result.exit_code != 0
        assert "No such command" in result.stdout or result.exit_code == 2

    def test_old_config_show_fails(self, runner):
        """Test that old config-show command is rejected."""
        result = runner.invoke(app, ["config-show"])

        assert result.exit_code != 0

    def test_old_health_check_fails(self, runner):
        """Test that old health-check command is rejected."""
        result = runner.invoke(app, ["health-check"])

        assert result.exit_code != 0
