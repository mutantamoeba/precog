#!/usr/bin/env python3
"""
Precog CLI - Entry Point.

This is the main entry point for the Precog command-line interface.
All command implementations are in the precog.cli package.

Usage:
    precog --help                    Show available commands
    precog kalshi balance            Fetch Kalshi account balance
    precog espn scores nfl           Show NFL scores
    precog data seed --type elo      Seed Elo rating data
    precog scheduler start           Start data collection
    precog db status                 Show database status
    precog config env                Show environment configuration
    precog system health             Check system health

Command Groups:
    kalshi      Kalshi market operations (balance, markets, positions, fills)
    espn        ESPN data operations (scores, schedule, live, status)
    data        Data management (seed, verify, sources, stats)
    db          Database operations (init, status, migrate, tables)
    scheduler   Service management (start, stop, status, poll-once)
    config      Configuration management (show, validate, env)
    system      System utilities (health, version, info)

Future Commands (Phase 4-5):
    strategy    Strategy management
    model       Model management
    position    Position management
    trade       Trading operations

Related:
    - Issue #204: CLI Refactor
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md
    - src/precog/cli/ package for command implementations
"""

from precog.cli import app, register_commands


def main() -> None:
    """Main entry point for CLI.

    Registers all command groups and runs the Typer application.
    Command implementations are in the precog.cli package.
    """
    register_commands()
    app()


if __name__ == "__main__":
    main()
