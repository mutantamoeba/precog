"""Property-based tests for CLI scheduler commands.

Tests command-line argument parsing invariants and output format consistency
using Hypothesis to generate edge cases.

Reference:
    - TESTING_STRATEGY V3.2 - Property Tests (2/8)
    - Issue #764 - scheduler CLI factory-vs-class mock anti-pattern

Mock Level Notes (#764):
    Tests that exercise the scheduler ``start`` command MUST patch
    ``create_supervisor`` (the factory the CLI actually calls) with
    ``_validate_startup`` also patched, and they MUST pass
    ``--supervised``. Otherwise the CLI takes the non-supervised
    path that instantiates real Kalshi/ESPN pollers.

    Tests that exercise ``status`` patch
    ``_show_db_backed_status`` because the status command does NOT
    go through ``create_supervisor`` -- it queries the database via
    ``list_scheduler_services``.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner


def get_fresh_cli():
    """Create a fresh CLI app instance for isolated testing.

    This prevents race conditions during parallel pytest-xdist execution
    by avoiding shared global state.
    """
    from precog.cli import db, scheduler, system

    fresh_app = typer.Typer(name="precog", help="Precog CLI (test instance)")
    fresh_app.add_typer(db.app, name="db")
    fresh_app.add_typer(scheduler.app, name="scheduler")
    fresh_app.add_typer(system.app, name="system")
    runner = CliRunner()
    return fresh_app, runner


def _make_supervised_mock() -> MagicMock:
    """Build a supervisor mock for non-foreground supervised start tests."""
    mock_supervisor = MagicMock()
    mock_supervisor.is_running = True
    mock_supervisor.start_all.return_value = None
    mock_supervisor.stop_all.return_value = None
    mock_supervisor.get_aggregate_metrics.return_value = {
        "uptime_seconds": 0,
        "services_healthy": 1,
        "services_total": 1,
        "total_restarts": 0,
        "total_errors": 0,
        "per_service": {},
    }
    return mock_supervisor


@pytest.fixture(autouse=True)
def _mock_migration_check():
    """Bypass migration parity check in all scheduler CLI tests."""
    from precog.database.migration_check import MigrationStatus

    ok = MigrationStatus(is_current=True, db_version="0057", head_version="0057")
    with patch("precog.database.migration_check.check_migration_parity", return_value=ok):
        yield


class TestSchedulerArgumentInvariants:
    """Property tests for scheduler command argument validation."""

    @given(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz,"))
    @settings(max_examples=50, deadline=None)
    def test_leagues_string_handling(self, leagues: str):
        """The scheduler start --leagues option should accept any
        comma-separated lowercase ASCII string without crashing the
        supervised path.

        Replaces the original ``test_scheduler_name_handling`` test,
        which used ``status --name <text>`` -- ``status`` does not
        accept ``--name``, so the original test was exercising only
        the Typer parser's "no such option" rejection. The mocks
        never ran. We now exercise an option the CLI actually
        accepts and verify the supervised path completes cleanly.
        """
        assume(leagues.strip(","))  # at least one non-comma char

        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock()

            app, runner = get_fresh_cli()
            result = runner.invoke(
                app,
                [
                    "scheduler",
                    "start",
                    "--supervised",
                    "--no-kalshi",
                    "--leagues",
                    leagues,
                ],
            )

            assert result.exit_code == 0, (
                f"supervised start should exit 0 for leagues={leagues!r}; "
                f"got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()

    @given(st.integers(min_value=1, max_value=10000))
    @settings(max_examples=50, deadline=None)
    def test_kalshi_interval_integer_handling(self, interval: int):
        """The scheduler start --kalshi-interval option should accept
        any positive integer and propagate it to the factory.

        Replaces the original ``test_poll_interval_integer_handling``
        test, which passed ``poll-once --poll-interval`` -- a flag
        ``poll-once`` does not accept. The original was a Typer
        rejection test in disguise.
        """
        with (
            patch(
                "precog.schedulers.service_supervisor.create_supervisor"
            ) as mock_create_supervisor,
            patch("precog.cli.scheduler._validate_startup", return_value=True),
            patch("precog.cli.scheduler._prevent_system_sleep_for_supervised"),
        ):
            mock_create_supervisor.return_value = _make_supervised_mock()

            app, runner = get_fresh_cli()
            result = runner.invoke(
                app,
                [
                    "scheduler",
                    "start",
                    "--supervised",
                    "--no-espn",
                    "--kalshi-interval",
                    str(interval),
                ],
            )

            assert result.exit_code == 0, (
                f"supervised start should exit 0 for interval={interval}; "
                f"got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_called_once()
            call_kwargs = mock_create_supervisor.call_args.kwargs
            assert call_kwargs.get("kalshi_poll_interval") == interval

    @given(st.floats(allow_nan=False, allow_infinity=False))
    @settings(max_examples=50, deadline=None)
    def test_kalshi_interval_float_rejection(self, interval: float):
        """The scheduler start --kalshi-interval option should reject
        non-integer values with Typer's bad-usage exit code 2.

        Replaces the original ``test_poll_interval_float_rejection``
        test, which used a non-existent ``--poll-interval`` option.
        Property tested: invalid integer input -> Typer exit 2 -> the
        factory is never called.
        """
        with patch(
            "precog.schedulers.service_supervisor.create_supervisor"
        ) as mock_create_supervisor:
            mock_create_supervisor.return_value = _make_supervised_mock()

            app, runner = get_fresh_cli()
            result = runner.invoke(
                app,
                [
                    "scheduler",
                    "start",
                    "--supervised",
                    "--kalshi-interval",
                    str(interval),
                ],
            )

            # Typer's int parser calls int(value_str) which raises for every
            # str(float) representation — including "0.0", "1e+300", and plain
            # integer-valued floats like "1.0". Every finite float should
            # therefore produce exit code 2 with the factory never called.
            #
            # If this assertion ever fires, it means Typer's parser changed or
            # a new Hypothesis strategy is producing values that bypass the
            # int() rejection — a legitimate assumption decay the property
            # test should surface, not silently paper over.
            assert result.exit_code == 2, (
                f"expected Typer exit 2 (bad int parse) for interval={interval!r}, "
                f"got {result.exit_code}: {result.output}"
            )
            mock_create_supervisor.assert_not_called()


class TestSchedulerOutputInvariants:
    """Property tests for scheduler command output consistency."""

    @given(st.booleans())
    @settings(max_examples=10)
    def test_help_output_always_includes_commands(self, verbose: bool):
        """Help output should always list available subcommands."""
        app, runner = get_fresh_cli()
        result = runner.invoke(app, ["scheduler", "--help"])
        assert result.exit_code == 0
        # Help should mention key commands
        assert "start" in result.output.lower() or "Commands" in result.output
        assert "stop" in result.output.lower() or "Commands" in result.output

    @given(st.sampled_from(["start", "stop", "status", "poll-once"]))
    @settings(max_examples=4)
    def test_subcommand_help_available(self, subcommand: str):
        """Each subcommand should have help available."""
        app, runner = get_fresh_cli()
        result = runner.invoke(app, ["scheduler", subcommand, "--help"])
        assert result.exit_code == 0
        assert len(result.output) > 0


class TestSchedulerStateTransitions:
    """Property tests for scheduler state handling."""

    @given(st.lists(st.sampled_from(["status", "stop"]), min_size=1, max_size=5))
    @settings(max_examples=20, deadline=None)
    def test_command_sequence_stability(self, commands: list):
        """Any sequence of status/stop commands should not crash.

        Replaces the original ``test_command_sequence_stability``
        which alternated start/stop with a non-existent ``--name``
        flag (Typer rejected each call with exit 2). We now sequence
        status and stop -- both no-op-friendly commands -- and
        require strict exit 0 with the underlying paths mocked.

        ``start`` is excluded from the sequence because each
        successful start would mutate module-global state in
        ``precog.cli.scheduler`` and pollute subsequent calls; that
        is a real coupling but is not what this property test is
        meant to exercise.
        """
        from precog.cli import scheduler as scheduler_module

        # Snapshot and clear module globals so stop is a clean no-op.
        original_supervisor = scheduler_module._supervisor
        original_espn = scheduler_module._espn_updater
        original_kalshi = scheduler_module._kalshi_poller
        scheduler_module._supervisor = None
        scheduler_module._espn_updater = None
        scheduler_module._kalshi_poller = None
        try:
            with patch("precog.cli.scheduler._show_db_backed_status", return_value=False):
                app, runner = get_fresh_cli()
                for cmd in commands:
                    result = runner.invoke(app, ["scheduler", cmd])
                    assert result.exit_code == 0, (
                        f"{cmd} should exit 0; got {result.exit_code}: {result.output}"
                    )
        finally:
            scheduler_module._supervisor = original_supervisor
            scheduler_module._espn_updater = original_espn
            scheduler_module._kalshi_poller = original_kalshi

    @given(st.integers(min_value=0, max_value=100))
    @settings(max_examples=20, deadline=None)
    def test_status_with_varying_db_results(self, parity_seed: int):
        """Status should handle the database-backed path returning
        either success or fall-through for any iteration count.

        Replaces the original ``test_status_with_varying_scheduler_counts``
        which built a mock dictionary of N schedulers but patched
        ``ServiceSupervisor`` -- which the status command never
        instantiates. The original test exercised only the empty
        in-process fallback path, regardless of N. We now use N as
        an iteration count and verify the patched
        ``_show_db_backed_status`` invariant holds across calls.
        """
        from precog.cli import scheduler as scheduler_module

        original_supervisor = scheduler_module._supervisor
        scheduler_module._supervisor = None
        try:
            # parity_seed is just a source of True/False variation --
            # hypothesis gives us a range of integers and we use parity to
            # toggle the mock's return value. See #778 for a related
            # latent-assumption issue flagged on a sibling chaos test.
            db_returns = parity_seed % 2 == 0
            with patch(
                "precog.cli.scheduler._show_db_backed_status",
                return_value=db_returns,
            ) as mock_status:
                app, runner = get_fresh_cli()
                result = runner.invoke(app, ["scheduler", "status"])
                assert result.exit_code == 0, (
                    f"status should exit 0; got {result.exit_code}: {result.output}"
                )
                mock_status.assert_called_once()
        finally:
            scheduler_module._supervisor = original_supervisor
