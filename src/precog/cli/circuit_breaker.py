"""
Circuit Breaker CLI Commands.

Provides commands for managing circuit breaker events -- safety guards
that halt trading or data collection when anomalies are detected.

Commands:
    list    - Show active (unresolved) circuit breakers
    trip    - Manually trip a circuit breaker
    resolve - Resolve an active circuit breaker

Usage:
    precog circuit-breaker list
    precog circuit-breaker trip data_stale --notes "ESPN poller unresponsive"
    precog circuit-breaker resolve 42 --action "Service restarted"

Related:
    - Issue #390: Wire circuit_breaker_events table
    - Migration 0001: circuit_breaker_events table schema
    - REQ-OBSERV-001: Observability Requirements
"""

from __future__ import annotations

import typer

from precog.cli._common import (
    console,
    echo_error,
    echo_success,
    format_table,
)

app = typer.Typer(
    name="circuit-breaker",
    help="Circuit breaker management (list, trip, resolve)",
    no_args_is_help=True,
)

# Valid breaker types matching the CHECK constraint in migration 0001
VALID_BREAKER_TYPES = frozenset(
    {"daily_loss_limit", "api_failures", "data_stale", "position_limit", "manual"}
)


@app.command(
    name="list",
    help="Show active (unresolved) circuit breakers.",
    epilog="Example: precog circuit-breaker list",
)
def list_breakers() -> None:
    """Show active (unresolved) circuit breakers.

    Queries the circuit_breaker_events table for all events where
    resolved_at IS NULL. These are currently tripped breakers that
    may be blocking trading or data collection.

    Examples:
        precog circuit-breaker list
    """
    try:
        from precog.database.crud_operations import get_active_breakers

        breakers = get_active_breakers()
    except Exception as e:
        echo_error(f"Failed to query circuit breakers: {e}")
        raise typer.Exit(code=1) from e

    if not breakers:
        console.print("No active circuit breakers.")
        return

    rows = []
    for b in breakers:
        triggered = b.get("triggered_at")
        triggered_str = triggered.strftime("%Y-%m-%d %H:%M:%S UTC") if triggered else "unknown"
        notes = b.get("notes") or "-"
        # Truncate long notes for table display
        if len(notes) > 60:
            notes = notes[:57] + "..."

        rows.append(
            [
                str(b.get("event_id", "?")),
                b.get("breaker_type", "unknown"),
                triggered_str,
                notes,
            ]
        )

    table = format_table(
        "Active Circuit Breakers",
        ["ID", "Type", "Triggered At", "Notes"],
        rows,
    )
    console.print(table)
    console.print(f"\n{len(breakers)} active breaker(s).")


@app.command(
    name="trip",
    help="Manually trip a circuit breaker.",
    epilog=(
        "Example: precog circuit-breaker trip manual --notes 'Emergency stop'\n"
        "Valid types: daily_loss_limit, api_failures, data_stale, position_limit, manual"
    ),
)
def trip(
    breaker_type: str = typer.Argument(
        ...,
        help=(
            "Breaker type to trip: daily_loss_limit, api_failures, "
            "data_stale, position_limit, manual"
        ),
    ),
    notes: str = typer.Option(
        "",
        "--notes",
        "-n",
        help="Reason for tripping the breaker",
    ),
) -> None:
    """Manually trip a circuit breaker.

    Creates a new circuit_breaker_events record with the given type.
    The breaker remains active until explicitly resolved.

    Examples:
        precog circuit-breaker trip manual --notes "Emergency stop"
        precog circuit-breaker trip data_stale --notes "ESPN API down"
    """
    if breaker_type not in VALID_BREAKER_TYPES:
        echo_error(
            f"Invalid breaker type: {breaker_type}\n"
            f"Valid types: {', '.join(sorted(VALID_BREAKER_TYPES))}"
        )
        raise typer.Exit(code=1)

    try:
        from precog.database.crud_operations import create_circuit_breaker_event

        event_id = create_circuit_breaker_event(
            breaker_type=breaker_type,
            trigger_value={"source": "cli", "manual": True},
            notes=notes or None,
        )
    except Exception as e:
        echo_error(f"Failed to trip circuit breaker: {e}")
        raise typer.Exit(code=1) from e

    if event_id is not None:
        echo_success(f"Circuit breaker tripped: {breaker_type} (event_id={event_id})")
    else:
        echo_error("Failed to create circuit breaker event (no ID returned).")
        raise typer.Exit(code=1)


@app.command(
    name="resolve",
    help="Resolve an active circuit breaker.",
    epilog="Example: precog circuit-breaker resolve 42 --action 'Service restarted'",
)
def resolve(
    event_id: int = typer.Argument(
        ...,
        help="Event ID of the circuit breaker to resolve",
    ),
    action: str = typer.Option(
        "",
        "--action",
        "-a",
        help="Description of the resolution action taken",
    ),
) -> None:
    """Resolve an active circuit breaker.

    Sets resolved_at on the specified event. Only works if the breaker
    is currently active (resolved_at IS NULL).

    Examples:
        precog circuit-breaker resolve 42
        precog circuit-breaker resolve 42 --action "ESPN poller restarted"
    """
    try:
        from precog.database.crud_operations import resolve_circuit_breaker

        resolved = resolve_circuit_breaker(
            event_id=event_id,
            resolution_action=action or None,
        )
    except Exception as e:
        echo_error(f"Failed to resolve circuit breaker: {e}")
        raise typer.Exit(code=1) from e

    if resolved:
        echo_success(f"Circuit breaker resolved: event_id={event_id}")
    else:
        echo_error(
            f"Could not resolve event_id={event_id}. It may not exist or is already resolved."
        )
        raise typer.Exit(code=1)
