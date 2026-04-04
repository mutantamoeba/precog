"""CRUD operations for scheduler status tracking.

Extracted from crud_operations.py during Phase 1c domain split.

Tables covered:
    - scheduler_status: Service heartbeat and state tracking
"""

import json
import logging
from datetime import datetime
from typing import Any

from .connection import fetch_all, fetch_one, get_cursor
from .crud_shared import (
    DecimalEncoder,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Scheduler Status Operations (IPC via Database)
# =============================================================================
# These operations enable cross-process communication for scheduler status.
# The problem: `scheduler status` runs in a separate process from the scheduler
# itself, so it can't see in-memory state. Solution: store status in database.
#
# References:
#   - Migration 0012: scheduler_status table
#   - Issue #255: Scheduler status shows "not running" even when running
#   - ADR-TBD: Cross-Process IPC Strategy
# =============================================================================


def upsert_scheduler_status(
    host_id: str,
    service_name: str,
    *,
    status: str | None = None,
    pid: int | None = None,
    started_at: datetime | None = None,
    stats: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """
    Insert or update scheduler service status.

    This is the primary function for schedulers to report their status. It uses
    PostgreSQL's UPSERT (INSERT ... ON CONFLICT UPDATE) for atomic operation.

    Why UPSERT?
    -----------
    The scheduler might be starting for the first time (INSERT) or restarting
    after a crash (UPDATE). UPSERT handles both cases atomically without race
    conditions that would occur with "check then insert/update" logic.

    Args:
        host_id: Hostname running the service (e.g., 'DESKTOP-ABC123')
        service_name: Service identifier (e.g., 'espn', 'kalshi_rest', 'kalshi_ws')
        status: Current status ('starting', 'running', 'stopping', 'stopped', 'failed')
        pid: Process ID of the running service
        started_at: When the service was started
        stats: JSON with service-specific metrics (polls, errors, etc.)
        config: JSON with service configuration
        error_message: Last error message if status is 'failed'

    Returns:
        True if operation succeeded, False otherwise

    Example:
        >>> # Scheduler starting up
        >>> upsert_scheduler_status(
        ...     host_id=socket.gethostname(),
        ...     service_name="espn",
        ...     status="starting",
        ...     pid=os.getpid(),
        ...     started_at=datetime.now(timezone.utc),
        ...     config={"poll_interval_seconds": 60}
        ... )

        >>> # Scheduler heartbeat (update stats, refresh timestamp)
        >>> upsert_scheduler_status(
        ...     host_id=socket.gethostname(),
        ...     service_name="espn",
        ...     status="running",
        ...     stats={"polls": 142, "errors": 0, "games_updated": 8}
        ... )

    Educational Note:
        The last_heartbeat column is automatically set to NOW() on every upsert.
        This allows other processes to detect stale/crashed services by checking
        if last_heartbeat is older than a threshold (e.g., 2 minutes).

    References:
        - Migration 0012: scheduler_status table schema
        - REQ-OBSERV-001: Observability Requirements
    """
    # Build dynamic INSERT columns and ON CONFLICT UPDATE clause
    # Uses psycopg2-style %s placeholders
    insert_cols = ["host_id", "service_name", "last_heartbeat"]
    insert_vals = ["%s", "%s", "NOW()"]

    if status is not None:
        insert_cols.append("status")
        insert_vals.append("%s")
    if pid is not None:
        insert_cols.append("pid")
        insert_vals.append("%s")
    if started_at is not None:
        insert_cols.append("started_at")
        insert_vals.append("%s")
    if stats is not None:
        insert_cols.append("stats")
        insert_vals.append("%s")
    if config is not None:
        insert_cols.append("config")
        insert_vals.append("%s")
    if error_message is not None:
        insert_cols.append("error_message")
        insert_vals.append("%s")

    # Build SET clause with %s placeholders
    set_clause_parts = ["last_heartbeat = NOW()"]
    if status is not None:
        set_clause_parts.append("status = EXCLUDED.status")
    if pid is not None:
        set_clause_parts.append("pid = EXCLUDED.pid")
    if started_at is not None:
        set_clause_parts.append("started_at = EXCLUDED.started_at")
    if stats is not None:
        set_clause_parts.append("stats = EXCLUDED.stats")
    if config is not None:
        set_clause_parts.append("config = EXCLUDED.config")
    if error_message is not None:
        set_clause_parts.append("error_message = EXCLUDED.error_message")

    query = f"""
        INSERT INTO scheduler_status ({", ".join(insert_cols)})
        VALUES ({", ".join(insert_vals)})
        ON CONFLICT (host_id, service_name)
        DO UPDATE SET {", ".join(set_clause_parts)}
    """  # noqa: S608

    # Build params list: host_id, service_name, then optional params
    all_params: list[Any] = [host_id, service_name]
    if status is not None:
        all_params.append(status)
    if pid is not None:
        all_params.append(pid)
    if started_at is not None:
        all_params.append(started_at)
    if stats is not None:
        all_params.append(json.dumps(stats, cls=DecimalEncoder))
    if config is not None:
        all_params.append(json.dumps(config, cls=DecimalEncoder))
    if error_message is not None:
        all_params.append(error_message)

    with get_cursor(commit=True) as cur:
        cur.execute(query, tuple(all_params))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0) > 0


def get_scheduler_status(
    host_id: str,
    service_name: str,
) -> dict[str, Any] | None:
    """
    Get status for a specific scheduler service.

    Args:
        host_id: Hostname running the service
        service_name: Service identifier

    Returns:
        Dictionary with service status, or None if not found

    Example:
        >>> status = get_scheduler_status("DESKTOP-ABC123", "espn")
        >>> if status:
        ...     print(f"ESPN scheduler: {status['status']}")
        ...     print(f"Last heartbeat: {status['last_heartbeat']}")
        ...     if status['stats']:
        ...         print(f"Polls: {status['stats'].get('polls', 0)}")

    Educational Note:
        The returned stats and config are automatically parsed from JSON
        back to Python dictionaries by psycopg2's JSON handling.

    References:
        - Migration 0012: scheduler_status table schema
    """
    query = """
        SELECT host_id, service_name, pid, status, started_at, last_heartbeat,
               stats, config, error_message, created_at, updated_at
        FROM scheduler_status
        WHERE host_id = %s AND service_name = %s
    """
    return fetch_one(query, (host_id, service_name))


def list_scheduler_services(
    *,
    host_id: str | None = None,
    status_filter: str | None = None,
    include_stale: bool = True,
    stale_threshold_seconds: int = 120,
) -> list[dict[str, Any]]:
    """
    List all scheduler services and their status.

    This is the primary function for CLI status display. It can filter by
    host, status, and optionally mark services with old heartbeats as stale.

    Args:
        host_id: Filter to specific host (None for all hosts)
        status_filter: Filter by status ('running', 'stopped', etc.)
        include_stale: If True, includes a 'is_stale' field in results
        stale_threshold_seconds: Heartbeat age to consider service stale (default 2 min)

    Returns:
        List of service status dictionaries, ordered by host_id, service_name

    Example:
        >>> # Get all services on this host
        >>> services = list_scheduler_services(host_id=socket.gethostname())
        >>> for svc in services:
        ...     status = svc['status']
        ...     if svc.get('is_stale') and status == 'running':
        ...         status = 'stale (crashed?)'
        ...     print(f"{svc['service_name']}: {status}")

    Educational Note:
        The 'is_stale' field helps detect crashed services. If a service
        status is 'running' but last_heartbeat is >2 minutes old, the
        service likely crashed without updating its status to 'stopped'.

    References:
        - Migration 0012: scheduler_status table schema
        - REQ-OBSERV-001: Observability Requirements
    """
    conditions = []
    params: list[Any] = []

    if host_id is not None:
        conditions.append("host_id = %s")
        params.append(host_id)

    if status_filter is not None:
        conditions.append("status = %s")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Include stale detection in query if requested
    # Note: We use string interpolation for the interval value because PostgreSQL
    # INTERVAL syntax doesn't support parameter substitution in all drivers
    stale_expr = ""
    if include_stale:
        stale_expr = (
            f", (last_heartbeat < NOW() - INTERVAL '{stale_threshold_seconds} seconds') AS is_stale"
        )

    # S608 false positive: conditions built from validated inputs
    query = f"""
        SELECT host_id, service_name, pid, status, started_at, last_heartbeat,
               stats, config, error_message, created_at, updated_at
               {stale_expr}
        FROM scheduler_status
        {where_clause}
        ORDER BY host_id, service_name
    """  # noqa: S608

    return fetch_all(query, tuple(params))


def cleanup_stale_schedulers(
    stale_threshold_seconds: int = 120,
    host_id: str | None = None,
) -> int:
    """
    Mark stale scheduler services as 'failed'.

    A service is considered stale if:
    1. Its status is 'running' or 'starting'
    2. Its last_heartbeat is older than the threshold

    This function should be called periodically (e.g., by a monitoring process)
    to clean up services that crashed without graceful shutdown.

    Args:
        stale_threshold_seconds: How old heartbeat must be to consider stale
        host_id: Only clean up services on specific host (None for all)

    Returns:
        Number of services marked as failed

    Example:
        >>> # Clean up crashed services on this host
        >>> import socket
        >>> cleaned = cleanup_stale_schedulers(
        ...     stale_threshold_seconds=120,
        ...     host_id=socket.gethostname()
        ... )
        >>> if cleaned > 0:
        ...     print(f"Marked {cleaned} crashed services as failed")

    Educational Note:
        This implements a "lease renewal" pattern common in distributed systems.
        Services must renew their lease (heartbeat) periodically to prove they're
        alive. If the lease expires, the service is considered dead.

    References:
        - Migration 0012: scheduler_status table schema
        - Pattern: Lease renewal / heartbeat monitoring
    """
    conditions = [
        "status IN ('running', 'starting')",
        "last_heartbeat < NOW() - INTERVAL '%s seconds'",
    ]
    params: list[Any] = [stale_threshold_seconds]

    if host_id is not None:
        conditions.append("host_id = %s")
        params.append(host_id)

    # S608 false positive: conditions are hardcoded strings
    query = f"""
        UPDATE scheduler_status
        SET status = 'failed',
            error_message = 'Service heartbeat expired (assumed crashed)',
            updated_at = NOW()
        WHERE {" AND ".join(conditions)}
    """  # noqa: S608

    with get_cursor(commit=True) as cur:
        cur.execute(query, tuple(params))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0)


def check_active_schedulers(
    stale_threshold_seconds: int = 120,
) -> list[dict[str, Any]]:
    """
    Check for actively running scheduler services with recent heartbeats.

    Used by the startup guard to detect concurrent scheduler instances before
    allowing a new supervisor to start. Returns services that appear to be
    genuinely alive (status is 'running'/'starting' AND heartbeat is fresh).

    Args:
        stale_threshold_seconds: How recent heartbeat must be to consider active.
            Default is 120s (2 minutes). Typically set to 2x the health check
            interval to allow for one missed heartbeat.

    Returns:
        List of active service dictionaries with host_id, service_name, pid,
        status, started_at, and last_heartbeat fields.

    Example:
        >>> active = check_active_schedulers(stale_threshold_seconds=120)
        >>> if active:
        ...     for svc in active:
        ...         print(f"Active: {svc['host_id']}/{svc['service_name']} PID {svc['pid']}")

    References:
        - Issue #363: Concurrent scheduler startup guard
        - Migration 0012: scheduler_status table schema
    """
    query = """
        SELECT host_id, service_name, pid, status, started_at, last_heartbeat
        FROM scheduler_status
        WHERE status IN ('running', 'starting')
        AND last_heartbeat >= NOW() - INTERVAL '%s seconds'
        ORDER BY host_id, service_name
    """
    return fetch_all(query, (stale_threshold_seconds,))


def delete_scheduler_status(host_id: str, service_name: str) -> bool:
    """
    Delete a scheduler status record.

    Use this when a service is being completely removed (not just stopped).
    For normal shutdown, use upsert_scheduler_status with status='stopped'.

    Args:
        host_id: Hostname running the service
        service_name: Service identifier

    Returns:
        True if record was deleted, False if not found

    Example:
        >>> # Remove old service record during cleanup
        >>> deleted = delete_scheduler_status("OLD-HOST", "legacy_service")

    References:
        - Migration 0012: scheduler_status table schema
    """
    query = """
        DELETE FROM scheduler_status
        WHERE host_id = %s AND service_name = %s
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, (host_id, service_name))
        # Cast rowcount to int for type safety (psycopg2 types it as Any)
        return int(cur.rowcount or 0) > 0


# =============================================================================
# Elo Rating Operations
# =============================================================================
# CRUD operations for managing team Elo ratings across the multi-table
# Elo architecture:
#
#   - teams.current_elo_rating: Live/current rating (updated after each game)
#   - historical_elo: Seeded from external sources (FiveThirtyEight, etc.)
#   - elo_calculation_log: Audit trail of every Elo computation (PRIMARY)
#
# Note: elo_rating_history was REMOVED in migration 0015 (2025-12-26).
#       It was superseded by elo_calculation_log which provides:
#         1. Game-centric view (both teams per row) vs team-centric
#         2. Full audit trail with parameters (K-factor, MOV, expected scores)
#         3. Links to source game (game_states or games)
#
#   To get team-centric view from elo_calculation_log:
#     SELECT game_date, home_post_elo as rating FROM elo_calculation_log
#     WHERE home_team_id = :team_id
#     UNION ALL
#     SELECT game_date, away_post_elo as rating FROM elo_calculation_log
#     WHERE away_team_id = :team_id
#     ORDER BY game_date
#
# References:
#   - Migration 0001: teams.current_elo_rating (elo_rating_history removed)
#   - Migration 0005: historical_elo
#   - Migration 0013: elo_calculation_log, historical_epa
#   - Migration 0015: Dropped deprecated elo_rating_history table
#   - ADR-109: Elo Rating Computation Engine Architecture
#   - Issue #273: Comprehensive Elo Rating Computation Module
#   - Issue #277: Remove deprecated elo_rating_history table
# =============================================================================
