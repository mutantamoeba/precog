"""Drop redundant event_id column from events table.

The events table has two columns storing identical values:
  - event_id (VARCHAR, UNIQUE) -- the original PK, demoted in migration 0020
  - external_id (VARCHAR, UNIQUE compound with platform_id) -- semantically correct

All 3,894 existing events have event_id == external_id.  The external_id column
is the correct one: it is scoped by platform_id for multi-platform support.
event_id is redundant and confusingly named (looks like the PK but isn't --
id SERIAL is the PK since migration 0020).

Steps:
    1. DROP the uq_events_event_id UNIQUE constraint
    2. DROP the event_id column

Downgrade:
    1. ADD event_id column back (nullable first)
    2. Backfill from external_id
    3. Set NOT NULL
    4. Re-add UNIQUE constraint

Revision ID: 0047
Revises: 0046
Create Date: 2026-03-31

Related:
- Issue #530: Remove redundant event_id column
- Migration 0020: event_id demoted from PK to UNIQUE business key
- Migration 0001: Original events table with event_id as PK
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0047"
down_revision: str = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the redundant event_id column from events."""
    # -- Step 1: Drop UNIQUE constraint on event_id --
    # Added in migration 0020 when event_id was demoted from PK to business key.
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT IF EXISTS uq_events_event_id
    """)

    # -- Step 2: Drop the event_id column --
    # All code now uses external_id (scoped by platform_id) instead.
    op.execute("""
        ALTER TABLE events
        DROP COLUMN IF EXISTS event_id
    """)


def downgrade() -> None:
    """Restore the event_id column and populate from external_id."""
    # -- Step 1: Add event_id column back (nullable to allow backfill) --
    op.execute("""
        ALTER TABLE events
        ADD COLUMN IF NOT EXISTS event_id VARCHAR(100)
    """)

    # -- Step 2: Backfill from external_id --
    op.execute("""
        UPDATE events SET event_id = external_id WHERE event_id IS NULL
    """)

    # -- Step 3: Set NOT NULL --
    op.execute("""
        ALTER TABLE events
        ALTER COLUMN event_id SET NOT NULL
    """)

    # -- Step 4: Re-add UNIQUE constraint --
    op.execute("""
        ALTER TABLE events
        ADD CONSTRAINT uq_events_event_id UNIQUE (event_id)
    """)
