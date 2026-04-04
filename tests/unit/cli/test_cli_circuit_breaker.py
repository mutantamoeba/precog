"""
Unit tests for CLI circuit-breaker commands.

Tests all circuit-breaker CLI commands:
- list: Show active circuit breakers
- trip: Manually trip a circuit breaker
- resolve: Resolve an active circuit breaker

Related:
    - Issue #390: Wire circuit_breaker_events table
    - src/precog/cli/circuit_breaker.py
    - REQ-OBSERV-001: Observability Requirements

Coverage Target: 80%+ for cli/circuit_breaker.py

Usage:
    pytest tests/unit/cli/test_cli_circuit_breaker.py -v
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from precog.cli.circuit_breaker import app
from tests.helpers.cli_helpers import strip_ansi

# =============================================================================
# LIST COMMAND TESTS
# =============================================================================


@pytest.mark.unit
class TestListBreakers:
    """Tests for 'precog circuit-breaker list' command."""

    def test_list_help_shows_description(self, cli_runner) -> None:
        """Test list --help shows command description."""
        result = cli_runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout).lower()
        assert "active" in output or "unresolved" in output

    @patch("precog.database.crud_system.get_active_breakers")
    def test_list_no_active_breakers(self, mock_get: MagicMock, cli_runner) -> None:
        """Test list with no active breakers shows informative message."""
        mock_get.return_value = []

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout).lower()
        assert "no active" in output

    @patch("precog.database.crud_system.get_active_breakers")
    def test_list_shows_active_breakers(self, mock_get: MagicMock, cli_runner) -> None:
        """Test list displays active breakers in a table."""
        mock_get.return_value = [
            {
                "event_id": 1,
                "breaker_type": "data_stale",
                "triggered_at": datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC),
                "notes": "ESPN poller down",
            },
            {
                "event_id": 2,
                "breaker_type": "api_failures",
                "triggered_at": datetime(2026, 3, 15, 12, 5, 0, tzinfo=UTC),
                "notes": None,
            },
        ]

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "data_stale" in output
        assert "api_failures" in output
        assert "2 active breaker" in output.lower()

    @patch("precog.database.crud_system.get_active_breakers")
    def test_list_truncates_long_notes(self, mock_get: MagicMock, cli_runner) -> None:
        """Test list truncates notes longer than 60 characters."""
        mock_get.return_value = [
            {
                "event_id": 1,
                "breaker_type": "manual",
                "triggered_at": datetime(2026, 3, 15, tzinfo=UTC),
                "notes": "A" * 100,
            },
        ]

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        # Should be truncated -- Rich may use "..." or unicode ellipsis
        assert "..." in output or "\u2026" in output

    @patch("precog.database.crud_system.get_active_breakers")
    def test_list_handles_db_error(self, mock_get: MagicMock, cli_runner) -> None:
        """Test list handles database errors gracefully."""
        mock_get.side_effect = Exception("DB connection failed")

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 1
        output = strip_ansi(result.stdout).lower()
        assert "failed" in output


# =============================================================================
# TRIP COMMAND TESTS
# =============================================================================


@pytest.mark.unit
class TestTripBreaker:
    """Tests for 'precog circuit-breaker trip' command."""

    @patch("precog.database.crud_system.create_circuit_breaker_event")
    def test_trip_valid_type(self, mock_create: MagicMock, cli_runner) -> None:
        """Test tripping a breaker with a valid type."""
        mock_create.return_value = 42

        result = cli_runner.invoke(app, ["trip", "manual", "--notes", "Emergency stop"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout).lower()
        assert "tripped" in output
        assert "42" in output
        mock_create.assert_called_once_with(
            breaker_type="manual",
            trigger_value={"source": "cli", "manual": True},
            notes="Emergency stop",
        )

    def test_trip_invalid_type(self, cli_runner) -> None:
        """Test tripping with invalid breaker type shows error."""
        result = cli_runner.invoke(app, ["trip", "invalid_type"])

        assert result.exit_code == 1
        output = strip_ansi(result.stdout).lower()
        assert "invalid" in output

    @patch("precog.database.crud_system.create_circuit_breaker_event")
    def test_trip_all_valid_types(self, mock_create: MagicMock, cli_runner) -> None:
        """Test all five valid breaker types are accepted."""
        valid_types = [
            "daily_loss_limit",
            "api_failures",
            "data_stale",
            "position_limit",
            "manual",
        ]
        mock_create.return_value = 1

        for btype in valid_types:
            result = cli_runner.invoke(app, ["trip", btype])
            assert result.exit_code == 0, f"Type '{btype}' should be valid"

    @patch("precog.database.crud_system.create_circuit_breaker_event")
    def test_trip_without_notes(self, mock_create: MagicMock, cli_runner) -> None:
        """Test tripping without --notes passes None."""
        mock_create.return_value = 10

        result = cli_runner.invoke(app, ["trip", "manual"])

        assert result.exit_code == 0
        mock_create.assert_called_once_with(
            breaker_type="manual",
            trigger_value={"source": "cli", "manual": True},
            notes=None,
        )

    @patch("precog.database.crud_system.create_circuit_breaker_event")
    def test_trip_returns_none_shows_error(self, mock_create: MagicMock, cli_runner) -> None:
        """Test trip shows error when create returns None."""
        mock_create.return_value = None

        result = cli_runner.invoke(app, ["trip", "manual"])

        assert result.exit_code == 1

    @patch("precog.database.crud_system.create_circuit_breaker_event")
    def test_trip_handles_db_error(self, mock_create: MagicMock, cli_runner) -> None:
        """Test trip handles database errors gracefully."""
        mock_create.side_effect = Exception("DB error")

        result = cli_runner.invoke(app, ["trip", "manual"])

        assert result.exit_code == 1
        output = strip_ansi(result.stdout).lower()
        assert "failed" in output


# =============================================================================
# RESOLVE COMMAND TESTS
# =============================================================================


@pytest.mark.unit
class TestResolveBreaker:
    """Tests for 'precog circuit-breaker resolve' command."""

    @patch("precog.database.crud_system.resolve_circuit_breaker")
    def test_resolve_active_breaker(self, mock_resolve: MagicMock, cli_runner) -> None:
        """Test resolving an active breaker."""
        mock_resolve.return_value = True

        result = cli_runner.invoke(app, ["resolve", "42", "--action", "Service restarted"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout).lower()
        assert "resolved" in output
        assert "42" in output

    @patch("precog.database.crud_system.resolve_circuit_breaker")
    def test_resolve_nonexistent_breaker(self, mock_resolve: MagicMock, cli_runner) -> None:
        """Test resolving a nonexistent breaker shows error."""
        mock_resolve.return_value = False

        result = cli_runner.invoke(app, ["resolve", "999"])

        assert result.exit_code == 1
        output = strip_ansi(result.stdout).lower()
        assert "could not resolve" in output or "already resolved" in output

    @patch("precog.database.crud_system.resolve_circuit_breaker")
    def test_resolve_without_action(self, mock_resolve: MagicMock, cli_runner) -> None:
        """Test resolving without --action passes None."""
        mock_resolve.return_value = True

        result = cli_runner.invoke(app, ["resolve", "10"])

        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(
            event_id=10,
            resolution_action=None,
        )

    @patch("precog.database.crud_system.resolve_circuit_breaker")
    def test_resolve_handles_db_error(self, mock_resolve: MagicMock, cli_runner) -> None:
        """Test resolve handles database errors gracefully."""
        mock_resolve.side_effect = Exception("DB error")

        result = cli_runner.invoke(app, ["resolve", "1"])

        assert result.exit_code == 1
        output = strip_ansi(result.stdout).lower()
        assert "failed" in output


# =============================================================================
# HELP & STRUCTURE TESTS
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerHelp:
    """Tests for circuit-breaker command group help and structure."""

    def test_help_shows_all_commands(self, cli_runner) -> None:
        """Test circuit-breaker --help shows list, trip, resolve."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout).lower()
        assert "list" in output
        assert "trip" in output
        assert "resolve" in output

    def test_trip_help_shows_epilog(self, cli_runner) -> None:
        """Test trip --help shows usage example in epilog."""
        result = cli_runner.invoke(app, ["trip", "--help"])

        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        # Epilog should show valid types
        assert "manual" in output
