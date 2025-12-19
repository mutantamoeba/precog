"""
Strategy Management CLI Commands (Phase 4 Stub).

NOT IMPLEMENTED - Target: Phase 4 (Strategy & Model Development)

This module will provide CLI commands for managing trading strategies:
    - list: List all strategies with versions and status
    - show: Display strategy details and configuration
    - create: Create a new strategy version
    - activate: Activate a strategy for live trading
    - compare: A/B comparison of strategy performance

Planned Usage:
    precog strategy list [--status active|testing|deprecated]
    precog strategy show STRATEGY_NAME [--version VERSION]
    precog strategy create --name NAME --config CONFIG_FILE
    precog strategy activate STRATEGY_NAME --version VERSION
    precog strategy compare STRATEGY_A STRATEGY_B [--metric sharpe|roi|win_rate]

Implementation Notes:
    When implementing, refer to:
    - docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.0.md
    - src/precog/trading/strategy_manager.py (when created)
    - ADR-018, ADR-019: Strategy versioning patterns

Database Tables Used:
    - strategies: Strategy definitions and configurations
    - strategy_versions: Immutable strategy versions (SCD Type 2)
    - strategy_performance: Historical performance metrics

Related:
    - Issue #204: CLI Refactor
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.3.1
"""

from __future__ import annotations

import typer

from precog.cli._common import cli_error

app = typer.Typer(
    name="strategy",
    help="[Phase 4] Strategy management - NOT IMPLEMENTED",
    no_args_is_help=True,
)


def _not_implemented(command: str) -> None:
    """Raise not implemented error with helpful context."""
    cli_error(
        f"Command 'precog strategy {command}' is not yet implemented.",
        hint=(
            "Target: Phase 4 (Strategy & Model Development)\n"
            "         See: docs/guides/STRATEGY_MANAGER_USER_GUIDE_V1.0.md"
        ),
    )


@app.command()
def list(
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (active, testing, deprecated)",
    ),
) -> None:
    """List all strategies with versions and status.

    NOT IMPLEMENTED - Target: Phase 4

    Will display:
        - Strategy name and current version
        - Status (active, testing, deprecated)
        - Performance metrics (Sharpe, ROI, win rate)
        - Last updated timestamp
    """
    _not_implemented("list")


@app.command()
def show(
    strategy_name: str = typer.Argument(..., help="Strategy name"),
    version: str | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Specific version (default: current)",
    ),
) -> None:
    """Show strategy details and configuration.

    NOT IMPLEMENTED - Target: Phase 4

    Will display:
        - Full strategy configuration
        - Entry/exit conditions
        - Risk parameters
        - Historical performance
        - A/B test results
    """
    _not_implemented("show")


@app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", help="Strategy name"),
    config_file: str = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to strategy configuration file",
    ),
) -> None:
    """Create a new strategy version.

    NOT IMPLEMENTED - Target: Phase 4

    Will:
        - Validate configuration file
        - Create new immutable version
        - Set status to 'testing' by default
        - Log creation in audit trail
    """
    _not_implemented("create")


@app.command()
def activate(
    strategy_name: str = typer.Argument(..., help="Strategy name"),
    version: str = typer.Option(..., "--version", "-v", help="Version to activate"),
) -> None:
    """Activate a strategy for live trading.

    NOT IMPLEMENTED - Target: Phase 4

    WARNING: This will enable live trading with real money!

    Will:
        - Require confirmation in production
        - Deactivate previous version
        - Set new version as active
        - Begin tracking performance
    """
    _not_implemented("activate")


@app.command()
def compare(
    strategy_a: str = typer.Argument(..., help="First strategy to compare"),
    strategy_b: str = typer.Argument(..., help="Second strategy to compare"),
    metric: str = typer.Option(
        "sharpe",
        "--metric",
        "-m",
        help="Comparison metric (sharpe, roi, win_rate)",
    ),
) -> None:
    """A/B comparison of strategy performance.

    NOT IMPLEMENTED - Target: Phase 4

    Will compare:
        - Risk-adjusted returns (Sharpe ratio)
        - Raw ROI
        - Win rate and profit factor
        - Statistical significance of difference
    """
    _not_implemented("compare")
