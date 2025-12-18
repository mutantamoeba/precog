"""
Precog CLI Package.

Provides a modular command-line interface for the Precog trading system.
Commands are organized into logical groups for discoverability and maintainability.

Command Groups:
    kalshi      - Kalshi market operations (balance, markets, positions, fills)
    espn        - ESPN data operations (scores, schedule, games, teams)
    data        - Data management (seed, verify, sources)
    db          - Database operations (init, upgrade, downgrade, status)
    scheduler   - Service management (start, stop, status, poll-once)
    config      - Configuration management (show, validate, env)
    system      - System utilities (health, version, info)

Future Commands (Phase 4-5):
    strategy    - Strategy management (list, show, create, activate)
    model       - Model management (list, show, create, evaluate)
    position    - Position management (list, show, monitor, close)
    trade       - Trading operations (execute, cancel, history)

Usage:
    precog kalshi balance
    precog espn scores --league nfl
    precog data seed --type elo --sport nfl
    precog scheduler start --espn --kalshi

Architecture:
    This package follows the grouped sub-command pattern (docker/kubectl style)
    for better discoverability and scalability. Each command group is a separate
    Typer app registered as a sub-application.

    main.py (entry point, ~50 lines)
        -> cli/__init__.py (this file, app assembly)
            -> cli/kalshi.py, cli/espn.py, etc. (command implementations)

Related:
    - Issue #204: Refactor main.py into modular CLI
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md
    - ADR-103: BasePoller pattern (scheduler commands)
    - ADR-106: Historical data collection (data commands)
"""

from __future__ import annotations

import typer

# Create the main CLI app
app = typer.Typer(
    name="precog",
    help="Precog - Prediction Market Trading System",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def register_commands() -> None:
    """Register all command groups with the main app.

    This function is called during app initialization to register
    all sub-applications. Import is deferred to avoid circular imports
    and improve startup time.

    Command groups are registered in order of typical usage:
    1. Data access (kalshi, espn)
    2. Data management (data, db)
    3. Operations (scheduler, config, system)
    4. Future stubs (strategy, model, position, trade)
    """
    # Import command modules (deferred for performance)
    from precog.cli import config as config_cmd
    from precog.cli import data as data_cmd
    from precog.cli import db as db_cmd
    from precog.cli import espn as espn_cmd
    from precog.cli import kalshi as kalshi_cmd
    from precog.cli import scheduler as scheduler_cmd
    from precog.cli import system as system_cmd

    # Register command groups
    app.add_typer(kalshi_cmd.app, name="kalshi", help="Kalshi market operations")
    app.add_typer(espn_cmd.app, name="espn", help="ESPN data operations")
    app.add_typer(data_cmd.app, name="data", help="Data seeding and management")
    app.add_typer(db_cmd.app, name="db", help="Database operations")
    app.add_typer(scheduler_cmd.app, name="scheduler", help="Service management")
    app.add_typer(config_cmd.app, name="config", help="Configuration management")
    app.add_typer(system_cmd.app, name="system", help="System utilities")

    # Register future command stubs (Phase 4-5)
    from precog.cli._future import model as model_cmd
    from precog.cli._future import position as position_cmd
    from precog.cli._future import strategy as strategy_cmd
    from precog.cli._future import trade as trade_cmd

    app.add_typer(
        strategy_cmd.app,
        name="strategy",
        help="[Phase 4] Strategy management",
    )
    app.add_typer(
        model_cmd.app,
        name="model",
        help="[Phase 4] Model management",
    )
    app.add_typer(
        position_cmd.app,
        name="position",
        help="[Phase 5] Position management",
    )
    app.add_typer(
        trade_cmd.app,
        name="trade",
        help="[Phase 5] Trading operations",
    )


# Version callback for --version flag
def version_callback(value: bool) -> None:
    """Display version information."""
    if value:
        from precog import __version__

        typer.echo(f"Precog v{__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Precog - Prediction Market Trading System.

    A modular Python application for identifying and executing positive
    expected value (EV+) trading opportunities on prediction markets.

    Use 'precog <command> --help' for more information on a specific command.
    """


__all__ = ["app", "register_commands"]
