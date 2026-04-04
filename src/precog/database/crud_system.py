"""CRUD operations for system health, circuit breakers, and alerts.

Extracted from crud_operations.py during Phase 1c domain split.

Tables covered:
    - system_health: Component health status tracking
    - circuit_breaker_events: Circuit breaker activation records
    - alerts: System alert records
"""

import json
import logging
from typing import Any

from .connection import fetch_all, get_cursor
from .crud_shared import (
    VALID_SYSTEM_HEALTH_COMPONENTS,
    DecimalEncoder,
    SystemHealthComponent,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ALERT CRUD OPERATIONS
# =============================================================================


def create_alert(
    alert_type: str,
    severity: str,
    message: str,
    source: str | None = None,
) -> int | None:
    """
    Create an alert record in the alerts table.

    Alerts are append-only operational signals for anomalies, threshold
    breaches, and system events. This is the first writer for the alerts
    table (created in migration 0001 but previously unused).

    Args:
        alert_type: Category of alert (e.g., "validation_error_rate",
            "data_staleness", "circuit_breaker"). VARCHAR(50).
        severity: One of "info", "warning", "error", "critical".
            Enforced by CHECK constraint in the DB.
        message: Human-readable description of the alert.
        source: Optional source component (e.g., "kalshi_poller",
            "espn_poller"). VARCHAR(100).

    Returns:
        alert_id of the newly created record, or None if insert failed.

    Raises:
        psycopg2.IntegrityError: If severity not in allowed values.

    Example:
        >>> alert_id = create_alert(
        ...     alert_type="validation_error_rate",
        ...     severity="warning",
        ...     message="Error rate 15.0% exceeds 10% threshold (3/20 markets)",
        ...     source="kalshi_poller:KXNFLGAME",
        ... )
    """
    query = """
        INSERT INTO alerts (alert_type, severity, message, source, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING alert_id
    """
    params = (alert_type, severity, message, source)

    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result["alert_id"] if result else None


# =============================================================================
# System Health CRUD Operations
# =============================================================================


# =============================================================================
# System Health CRUD Operations
# =============================================================================


def upsert_system_health(
    component: str | SystemHealthComponent,
    status: str,
    details: dict[str, Any] | None = None,
    alert_sent: bool = False,
) -> bool:
    """
    Insert or update component health in the system_health table.

    Uses DELETE + INSERT within a single committed transaction to maintain
    one row per component. The system_health table is not SCD Type 2.

    Why DELETE + INSERT?
    --------------------
    The system_health table has a non-unique index on component (not a
    UNIQUE constraint), so ON CONFLICT UPSERT is not available. DELETE +
    INSERT within get_cursor(commit=True) achieves the same result: exactly
    one current health row per component. A future migration can add a
    UNIQUE constraint to enable proper ON CONFLICT.

    Args:
        component: Component identifier. Must be a value in SystemHealthComponent:
            'kalshi_api', 'polymarket_api', 'espn_api', 'database',
            'edge_detector', 'trading_engine', 'websocket'.
            Validated at app layer (PostgreSQL CHECK constraint was dropped
            in Migration 0043 — see ADR-114 Part 2, R2).
        status: Health status. Must match the DB CHECK constraint:
            'healthy', 'degraded', 'down'.
        details: Optional JSONB payload with component-specific metrics
            (e.g., error_rate, polls_completed, last_successful_poll).
        alert_sent: Whether an alert has been sent for this health state.

    Returns:
        True if operation succeeded, False otherwise.

    Raises:
        ValueError: If component is not in VALID_SYSTEM_HEALTH_COMPONENTS.
        psycopg2.IntegrityError: If status violates the DB CHECK constraint.

    Example:
        >>> upsert_system_health(
        ...     component="kalshi_api",
        ...     status="healthy",
        ...     details={"error_rate": "0.02", "polls": 142, "errors": 3},
        ... )

        >>> upsert_system_health(
        ...     component="espn_api",
        ...     status="degraded",
        ...     details={"error_rate": "0.12", "last_poll_age_seconds": 180},
        ...     alert_sent=True,
        ... )

    Educational Note:
        The system_health table currently has a non-unique index on component.
        DELETE + INSERT keeps one row per component. A future migration should
        add a UNIQUE constraint to enable proper ON CONFLICT UPSERT.

        The component CHECK constraint was removed in Migration 0043 (ADR-114).
        To add a new component: add it to SystemHealthComponent and
        VALID_SYSTEM_HEALTH_COMPONENTS near the top of this file.

    References:
        - Migration 0001: system_health table schema (original CHECK constraint)
        - Migration 0043: DROP component CHECK constraint
        - Issue #389: Wire system_health table
        - Issue #491: Move component validation to app layer
        - ADR-114: Tier A data source architecture
        - REQ-OBSERV-001: Observability Requirements
    """
    # App-layer validation replacing the dropped PostgreSQL CHECK constraint.
    # The status CHECK constraint ('healthy', 'degraded', 'down') is still
    # enforced by the database — only component validation moved here.
    if component not in VALID_SYSTEM_HEALTH_COMPONENTS:
        valid = sorted(VALID_SYSTEM_HEALTH_COMPONENTS)
        raise ValueError(
            f"Invalid system_health component: {component!r}. "
            f"Valid components: {valid}. "
            f"To add a new component, update SystemHealthComponent and "
            f"VALID_SYSTEM_HEALTH_COMPONENTS in crud_operations.py."
        )

    # The system_health table has a non-unique index on component, so we use
    # DELETE + INSERT within a single transaction to simulate upsert behavior.
    # This keeps exactly one row per component (latest health snapshot).
    delete_query = "DELETE FROM system_health WHERE component = %s"
    insert_query = """
        INSERT INTO system_health (component, status, last_check, details, alert_sent)
        VALUES (%s, %s, NOW(), %s, %s)
    """
    details_json = json.dumps(details, cls=DecimalEncoder) if details else None

    with get_cursor(commit=True) as cur:
        cur.execute(delete_query, (component,))
        cur.execute(insert_query, (component, status, details_json, alert_sent))
        return int(cur.rowcount or 0) > 0


def get_system_health(component: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch system health records, optionally filtered by component.

    Args:
        component: If provided, fetch health for this component only.
            If None, fetch all components.

    Returns:
        List of health records as dictionaries. Each dict contains:
            health_id, component, status, last_check, details, alert_sent.
        Empty list if no records found.

    Example:
        >>> # Get all component health
        >>> records = get_system_health()
        >>> for r in records:
        ...     print(r["component"], r["status"])
        kalshi_api healthy
        espn_api degraded

        >>> # Get specific component
        >>> records = get_system_health(component="kalshi_api")
        >>> print(records[0]["status"])  # 'healthy'

    References:
        - Migration 0001: system_health table schema
        - Issue #389: Wire system_health table
    """
    if component:
        query = """
            SELECT health_id, component, status, last_check, details, alert_sent
            FROM system_health
            WHERE component = %s
            ORDER BY component
        """
        return fetch_all(query, (component,))

    query = """
        SELECT health_id, component, status, last_check, details, alert_sent
        FROM system_health
        ORDER BY component
    """
    return fetch_all(query)


def get_system_health_summary() -> dict[str, str]:
    """
    Get a compact component -> status mapping for all tracked components.

    This is a convenience function for CLI display and quick health checks.
    Returns only the latest status per component without full details.

    Returns:
        Dictionary mapping component name to status string.
        Example: {"kalshi_api": "healthy", "espn_api": "degraded"}
        Empty dict if no health records exist.

    Example:
        >>> summary = get_system_health_summary()
        >>> if summary.get("kalshi_api") != "healthy":
        ...     print("Kalshi API is not healthy!")

    References:
        - Migration 0001: system_health table schema
        - Issue #389: Wire system_health table
    """
    records = get_system_health()
    return {r["component"]: r["status"] for r in records}


# =============================================================================
# Circuit Breaker CRUD Operations
# =============================================================================


# =============================================================================
# Circuit Breaker CRUD Operations
# =============================================================================


def create_circuit_breaker_event(
    breaker_type: str,
    trigger_value: dict[str, Any] | None = None,
    notes: str | None = None,
) -> int | None:
    """
    Create a circuit breaker event (trip a breaker).

    Circuit breakers are safety guards that halt trading or data collection
    when anomalies are detected. A tripped breaker stays active until
    explicitly resolved via resolve_circuit_breaker().

    Args:
        breaker_type: Type of breaker to trip. Must match CHECK constraint:
            'daily_loss_limit', 'api_failures', 'data_stale',
            'position_limit', 'manual'.
        trigger_value: Optional JSONB payload with context about what
            triggered the breaker (e.g., error counts, component name).
        notes: Optional human-readable reason for tripping the breaker.

    Returns:
        event_id of the newly created record, or None if insert failed.

    Raises:
        psycopg2.IntegrityError: If breaker_type not in allowed values.

    Example:
        >>> event_id = create_circuit_breaker_event(
        ...     breaker_type="data_stale",
        ...     trigger_value={"component": "espn_api", "reason": "not_running"},
        ...     notes="ESPN poller went down during health check",
        ... )

    References:
        - Migration 0001: circuit_breaker_events table schema
        - Issue #390: Wire circuit_breaker_events table
    """
    query = """
        INSERT INTO circuit_breaker_events (breaker_type, triggered_at, trigger_value, notes)
        VALUES (%s, NOW(), %s, %s)
        RETURNING event_id
    """
    trigger_json = (
        json.dumps(trigger_value, cls=DecimalEncoder) if trigger_value is not None else None
    )

    with get_cursor(commit=True) as cur:
        cur.execute(query, (breaker_type, trigger_json, notes))
        result = cur.fetchone()
        return result["event_id"] if result else None


def resolve_circuit_breaker(
    event_id: int,
    resolution_action: str | None = None,
) -> bool:
    """
    Resolve an active circuit breaker event.

    Sets resolved_at to NOW() and optionally records what action was taken.
    Only resolves breakers that are currently active (resolved_at IS NULL).

    Args:
        event_id: The event_id of the breaker to resolve.
        resolution_action: Optional description of resolution action taken
            (e.g., "manual reset", "service restarted"). VARCHAR(100).

    Returns:
        True if the breaker was resolved, False if not found or already resolved.

    Example:
        >>> resolved = resolve_circuit_breaker(
        ...     event_id=42,
        ...     resolution_action="ESPN poller restarted successfully",
        ... )
        >>> print(resolved)  # True

    References:
        - Migration 0001: circuit_breaker_events table schema
        - Issue #390: Wire circuit_breaker_events table
    """
    query = """
        UPDATE circuit_breaker_events
        SET resolved_at = NOW(), resolution_action = %s
        WHERE event_id = %s AND resolved_at IS NULL
    """

    with get_cursor(commit=True) as cur:
        cur.execute(query, (resolution_action, event_id))
        return int(cur.rowcount or 0) > 0


def get_active_breakers(breaker_type: str | None = None) -> list[dict[str, Any]]:
    """
    Fetch all active (unresolved) circuit breaker events.

    Active breakers have resolved_at IS NULL, meaning they are currently
    tripped and have not been manually or automatically resolved.

    Args:
        breaker_type: If provided, filter to only this breaker type.
            If None, return all active breakers regardless of type.

    Returns:
        List of active breaker records as dictionaries. Each dict contains:
            event_id, breaker_type, triggered_at, trigger_value, notes.
        Empty list if no active breakers.

    Example:
        >>> # Check if any breakers are active
        >>> breakers = get_active_breakers()
        >>> if breakers:
        ...     print(f"{len(breakers)} active breaker(s)!")

        >>> # Check for specific type
        >>> stale = get_active_breakers(breaker_type="data_stale")

    References:
        - Migration 0001: circuit_breaker_events table schema
        - Issue #390: Wire circuit_breaker_events table
    """
    if breaker_type:
        query = """
            SELECT event_id, breaker_type, triggered_at, trigger_value, notes
            FROM circuit_breaker_events
            WHERE resolved_at IS NULL AND breaker_type = %s
            ORDER BY triggered_at DESC
        """
        return fetch_all(query, (breaker_type,))

    query = """
        SELECT event_id, breaker_type, triggered_at, trigger_value, notes
        FROM circuit_breaker_events
        WHERE resolved_at IS NULL
        ORDER BY triggered_at DESC
    """
    return fetch_all(query)


# =============================================================================
# EDGE OPERATIONS
# =============================================================================
#
# Migration 0023: edges table enriched with analytics-ready columns.
#   - probability_matrix_id dropped (dead FK)
#   - New columns: actual_outcome, settlement_value, resolved_at, strategy_id,
#     edge_status, yes_ask_price, no_ask_price, spread, volume, open_interest,
#     last_price, liquidity, category, subcategory, execution_environment
#   - New views: current_edges (recreated), edge_lifecycle (computed P&L)
#
# SCD Type 2: edges use row_current_ind versioning.
#   - create_edge: sets row_current_ind = TRUE
#   - update_edge_outcome / update_edge_status: direct updates (lifecycle
#     events, not version changes)
# =============================================================================
