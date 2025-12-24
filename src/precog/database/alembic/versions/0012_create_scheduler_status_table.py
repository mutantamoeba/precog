"""Create scheduler_status table for cross-process IPC.

Revision ID: 0012
Revises: 0011
Create Date: 2024-12-24

This migration creates a table to track scheduler service status, enabling
any process to query the current state of running schedulers. Solves the
IPC problem where `scheduler status` runs in a different process and can't
see the in-memory state of running schedulers.

Design:
- Each service instance identified by (host_id, service_name)
- Heartbeat mechanism for detecting stale/crashed services
- JSON columns for flexible stats and config storage

Educational Note:
    Inter-Process Communication (IPC) for status requires shared state.
    Options considered:
    1. File-based (simpler but less reliable on crashes)
    2. Database table (chosen - fits existing patterns, atomic, crash-safe)
    3. Redis/memcached (overkill for this use case)

Related:
- Issue #255: Scheduler status shows "not running" even when running
- REQ-OBSERV-001: Observability Requirements
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scheduler_status table for service state tracking.

    Columns:
    - host_id: Hostname of the machine running the service (for multi-host support)
    - service_name: Name of the service (e.g., 'espn', 'kalshi_rest', 'kalshi_ws')
    - pid: Process ID of the running service
    - status: Current status ('starting', 'running', 'stopping', 'stopped', 'failed')
    - started_at: When the service was last started
    - last_heartbeat: Last time the service reported it's alive
    - stats: JSON with service-specific metrics (polls, errors, etc.)
    - config: JSON with service configuration
    - error_message: Last error message if status is 'failed'

    Educational Note:
        The (host_id, service_name) composite primary key allows:
        - Same service on different hosts
        - Multiple services on the same host
        - Querying all services on a specific host
        - Querying status of a specific service across all hosts
    """
    op.create_table(
        "scheduler_status",
        sa.Column(
            "host_id", sa.String(255), nullable=False, comment="Hostname running the service"
        ),
        sa.Column("service_name", sa.String(100), nullable=False, comment="Service identifier"),
        sa.Column("pid", sa.Integer, nullable=True, comment="Process ID of the service"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="stopped",
            comment="Service status",
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True, comment="When service started"
        ),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last heartbeat timestamp",
        ),
        sa.Column("stats", JSONB, nullable=True, comment="Service statistics as JSON"),
        sa.Column("config", JSONB, nullable=True, comment="Service configuration as JSON"),
        sa.Column("error_message", sa.Text, nullable=True, comment="Last error message"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        # Composite primary key for multi-host support
        sa.PrimaryKeyConstraint("host_id", "service_name", name="pk_scheduler_status"),
        # CHECK constraint for valid status values
        sa.CheckConstraint(
            "status IN ('starting', 'running', 'stopping', 'stopped', 'failed')",
            name="ck_scheduler_status_status",
        ),
        comment="Tracks scheduler service status for cross-process IPC",
    )

    # Create index for querying by status (common query pattern)
    op.create_index(
        "ix_scheduler_status_status",
        "scheduler_status",
        ["status"],
    )

    # Create index for finding stale services (heartbeat older than threshold)
    op.create_index(
        "ix_scheduler_status_last_heartbeat",
        "scheduler_status",
        ["last_heartbeat"],
    )


def downgrade() -> None:
    """Remove scheduler_status table."""
    op.drop_index("ix_scheduler_status_last_heartbeat", table_name="scheduler_status")
    op.drop_index("ix_scheduler_status_status", table_name="scheduler_status")
    op.drop_table("scheduler_status")
