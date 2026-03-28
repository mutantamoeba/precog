"""Drop system_health.component CHECK constraint — move validation to app layer.

ADR-114 (Part 2, R2) requires removing the PostgreSQL CHECK constraint on
system_health.component so that new Tier A data sources can be added without
a schema migration. Validation is moved to app-layer via SystemHealthComponent
in crud_operations.py.

Before this migration, adding a new component (e.g., 'polymarket_api' or
'odds_api') required a schema migration and downtime. After this migration,
adding a component requires only a code change to SystemHealthComponent.

The component column remains VARCHAR(50) NOT NULL. All existing rows are
unaffected because the constraint only blocked future INSERTs with unknown
values.

The status CHECK constraint ('healthy', 'degraded', 'down') is NOT touched —
those values are stable and DB enforcement is appropriate.

Steps:
    1. DROP CONSTRAINT system_health_component_check (auto-generated name)

Revision ID: 0043
Revises: 0042
Create Date: 2026-03-27

Related:
    - ADR-114: Tier A data source architecture (Part 2, R2)
    - Issue #491: Remove system_health component CHECK constraint
    - Migration 0001: Original system_health table schema
    - Migration 0016: Precedent — dropped series_frequency_check for same reason
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: str = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the system_health_component_check constraint.

    The component column remains VARCHAR(50) NOT NULL — only the CHECK
    constraint is removed. Validation moves to SystemHealthComponent in
    crud_operations.py (app-layer enum).

    Educational Note:
        PostgreSQL auto-generates a constraint name for inline CHECK
        constraints using the pattern: {tablename}_{columnname}_check.
        The system_health table was created in migration 0001 with:
            component VARCHAR(50) NOT NULL CHECK (component IN (...))
        This produces the name 'system_health_component_check'.

        IF EXISTS makes this migration idempotent — safe to re-run if
        the constraint was already removed.
    """
    op.execute("ALTER TABLE system_health DROP CONSTRAINT IF EXISTS system_health_component_check")


def downgrade() -> None:
    """Re-add the component CHECK constraint.

    WARNING: This will fail if any rows contain component values not in
    the original allowlist (e.g., 'cfbd_api', 'odds_api'). Remove
    non-conforming rows first, or treat this as a forward-only migration.

    The original 7 values from migration 0001 are restored.
    """
    op.execute("""
        ALTER TABLE system_health
        ADD CONSTRAINT system_health_component_check
        CHECK (component IN (
            'kalshi_api', 'polymarket_api', 'espn_api', 'database',
            'edge_detector', 'trading_engine', 'websocket'
        ))
    """)
