"""
Position Management CLI Commands (Phase 5 Stub).

NOT IMPLEMENTED - Target: Phase 5a (Position Monitoring)

This module will provide CLI commands for managing trading positions:
    - list: List positions with P&L and status
    - show: Display detailed position information
    - monitor: Start position monitoring loop
    - close: Manually close a position

Planned Usage:
    precog position list [--status open|closed|all]
    precog position show POSITION_ID [--verbose]
    precog position monitor [--interval N]
    precog position close POSITION_ID [--reason REASON]

Implementation Notes:
    When implementing, refer to:
    - docs/guides/POSITION_MANAGER_USER_GUIDE_V1.0.md
    - docs/supplementary/POSITION_MONITORING_SPEC_V1.0.md
    - src/precog/trading/position_manager.py (when created)

Position States:
    - open: Active position with market exposure
    - pending_exit: Exit signal triggered, awaiting execution
    - closed: Position fully exited
    - expired: Market expired (settled by platform)

Trailing Stop Logic:
    - Tracked per position
    - Ratchets up as profit increases
    - Triggers exit when price drops below stop level
    - See: docs/guides/TRAILING_STOP_GUIDE_V1.0.md

Database Tables Used:
    - positions: Position records with SCD Type 2 versioning
    - trades: Individual trade executions
    - position_snapshots: Point-in-time P&L snapshots

Related:
    - Issue #204: CLI Refactor
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.3.3
"""

from __future__ import annotations

import typer

from precog.cli._common import cli_error

app = typer.Typer(
    name="position",
    help="[Phase 5] Position management - NOT IMPLEMENTED",
    no_args_is_help=True,
)


def _not_implemented(command: str) -> None:
    """Raise not implemented error with helpful context."""
    cli_error(
        f"Command 'precog position {command}' is not yet implemented.",
        hint=(
            "Target: Phase 5a (Position Monitoring)\n"
            "         See: docs/guides/POSITION_MANAGER_USER_GUIDE_V1.0.md"
        ),
    )


@app.command()
def list(
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (open, closed, all)",
    ),
) -> None:
    """List positions with P&L and status.

    NOT IMPLEMENTED - Target: Phase 5a

    Will display:
        - Position ID and market
        - Side (YES/NO) and quantity
        - Entry price and current price
        - Unrealized P&L (open) or realized P&L (closed)
        - Trailing stop level (if active)
    """
    _not_implemented("list")


@app.command()
def show(
    position_id: str = typer.Argument(..., help="Position ID"),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed information",
    ),
) -> None:
    """Show detailed position information.

    NOT IMPLEMENTED - Target: Phase 5a

    Will display:
        - Full position details
        - Trade history (entries and exits)
        - P&L breakdown
        - Trailing stop history
        - Exit condition status (10-condition hierarchy)
    """
    _not_implemented("show")


@app.command()
def monitor(
    interval: int = typer.Option(
        30,
        "--interval",
        "-i",
        help="Monitoring interval in seconds",
    ),
) -> None:
    """Start position monitoring loop.

    NOT IMPLEMENTED - Target: Phase 5a

    Will:
        - Poll position prices at specified interval
        - Update trailing stops
        - Evaluate 10-condition exit hierarchy
        - Trigger exit signals when conditions met
        - Display real-time P&L updates

    See: docs/supplementary/POSITION_MONITORING_SPEC_V1.0.md
    """
    _not_implemented("monitor")


@app.command()
def close(
    position_id: str = typer.Argument(..., help="Position ID to close"),
    reason: str | None = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason for manual close",
    ),
) -> None:
    """Manually close a position.

    NOT IMPLEMENTED - Target: Phase 5b

    WARNING: This will execute a market order to close the position!

    Will:
        - Require confirmation in production
        - Execute market order to exit
        - Record close reason in audit trail
        - Update position status to 'closed'
    """
    _not_implemented("close")
