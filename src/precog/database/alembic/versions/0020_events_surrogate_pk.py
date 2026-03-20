"""Add SERIAL surrogate primary key to events table, update markets FK.

Decouples internal identity from external Kalshi identifiers. Integer PKs
provide better join performance (4 bytes vs 100 bytes for VARCHAR FK),
smaller index footprint, and enable multi-platform support via
UNIQUE(platform_id, external_id).

Changes to `events` table:
- Add `id SERIAL` column (new primary key)
- Demote `event_id VARCHAR(100)` from PK to UNIQUE business key
- Add UNIQUE(platform_id, external_id) composite constraint

Changes to `markets` table (SCD Type 2):
- Add `event_internal_id INTEGER` column with FK to events(id)
- Backfill from old `event_id VARCHAR` via join
- Drop old `event_id VARCHAR` FK column
- Rebuild index on new FK column

This is a CLEAN DB migration -- no data to preserve. All ALTER TABLE
operations are safe to run directly without data backfill.

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-19

Related:
- Issue #365: Schema skepticism audit (surrogate PK recommendation)
- migration_batch_plan_v1.md: Migration 0020 spec
- ADR pending: ID architecture decision (Elrond council)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: str = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add surrogate PK to events, migrate markets FK to integer.

    Steps:
    1. Drop markets FK to events (must precede PK drop -- dependent objects)
    2. Add SERIAL id column to events
    3. Drop existing PRIMARY KEY on event_id
    4. Set id as new PRIMARY KEY
    5. Add UNIQUE constraint on event_id (business key)
    6. Add UNIQUE(platform_id, external_id) composite constraint
    7. Add event_internal_id INTEGER column to markets
    8. Backfill event_internal_id from old VARCHAR event_id
    9. Add FK constraint on event_internal_id
    10. Drop old markets.event_id VARCHAR column + index
    11. Add index on markets.event_internal_id

    Educational Note:
        CRITICAL LESSON: Drop dependent FKs BEFORE dropping the PK.
        The markets table has `event_id VARCHAR FK -> events(event_id)`.
        PostgreSQL won't let you drop a PK that has FKs referencing it.

        The markets table uses SCD Type 2 versioning. Multiple rows can
        share the same event_internal_id (one current, many historical).
        The FK references events(id), which is unique by PK definition.
    """
    # -- Step 1: Drop markets FK to events FIRST --
    # Must drop the dependent FK before we can drop the events PK.
    # PostgreSQL auto-names inline FKs as {table}_{column}_fkey.
    op.execute("""
        ALTER TABLE markets
        DROP CONSTRAINT IF EXISTS markets_event_id_fkey
    """)

    # -- Step 2: Add SERIAL id column to events --
    # SERIAL = INTEGER + auto-increment sequence. Existing rows get
    # auto-assigned IDs from the sequence.
    op.execute("""
        ALTER TABLE events
        ADD COLUMN id SERIAL
    """)

    # -- Step 3: Drop existing PRIMARY KEY on event_id --
    # Safe now that the markets FK has been dropped in Step 1.
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT events_pkey
    """)

    # -- Step 4: Set id as new PRIMARY KEY --
    op.execute("""
        ALTER TABLE events
        ADD PRIMARY KEY (id)
    """)

    # -- Step 5: Add UNIQUE constraint on event_id (business key) --
    # Keeps event_id queryable and prevents duplicates, but it's no
    # longer the primary key. Also add NOT NULL since it was previously
    # the PK (and thus implicitly NOT NULL), but demoting it loses that.
    op.execute("""
        ALTER TABLE events
        ALTER COLUMN event_id SET NOT NULL
    """)
    op.execute("""
        ALTER TABLE events
        ADD CONSTRAINT uq_events_event_id UNIQUE (event_id)
    """)

    # -- Step 6: Add UNIQUE(platform_id, external_id) composite constraint --
    # Enables multi-platform support: same external_id on different platforms
    # is allowed, but same (platform_id, external_id) pair is not.
    op.execute("""
        ALTER TABLE events
        ADD CONSTRAINT uq_events_platform_external UNIQUE (platform_id, external_id)
    """)

    # -- Step 7: Add event_internal_id INTEGER column to markets --
    # Named event_internal_id to clearly indicate it's the surrogate FK.
    # Nullable initially for backfill, but practically all markets have events.
    op.execute("""
        ALTER TABLE markets
        ADD COLUMN event_internal_id INTEGER
    """)

    # -- Step 8: Backfill event_internal_id from old VARCHAR event_id --
    # For existing data: look up the new integer PK from the events table
    # using the old VARCHAR event_id that markets still has (not yet dropped).
    op.execute("""
        UPDATE markets m
        SET event_internal_id = e.id
        FROM events e
        WHERE m.event_id = e.event_id
    """)

    # -- Step 9: Add FK constraint on the new integer column --
    # ON DELETE CASCADE matches the original event_id FK behavior.
    op.execute("""
        ALTER TABLE markets
        ADD CONSTRAINT fk_markets_event_internal
        FOREIGN KEY (event_internal_id) REFERENCES events(id) ON DELETE CASCADE
    """)

    # -- Step 10: Drop old markets.event_id VARCHAR column + index --
    # Must drop the current_markets view first (depends on event_id via SELECT *).
    op.execute("DROP VIEW IF EXISTS current_markets CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_markets_event")
    op.execute("""
        ALTER TABLE markets
        DROP COLUMN event_id
    """)
    # Recreate the view with the new schema (SELECT * picks up event_internal_id)
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT * FROM markets WHERE row_current_ind = TRUE
    """)

    # -- Step 11: Add index on markets.event_internal_id --
    # Replaces the old idx_markets_event index for FK lookups.
    op.execute("""
        CREATE INDEX idx_markets_event_internal
        ON markets(event_internal_id)
    """)

    # -- Comments for documentation --
    op.execute("""
        COMMENT ON COLUMN events.id IS
        'Surrogate primary key (SERIAL). Internal identity, never exposed to users.'
    """)
    op.execute("""
        COMMENT ON COLUMN events.event_id IS
        'Business key from Kalshi API (e.g., KXNFL-24DEC22-KC-SEA). Unique, human-readable.'
    """)
    op.execute("""
        COMMENT ON COLUMN markets.event_internal_id IS
        'FK to events(id). Integer surrogate key replaces old VARCHAR event_id FK.'
    """)


def downgrade() -> None:
    """Reverse surrogate PK: restore event_id as PK, markets.event_id as VARCHAR FK.

    WARNING: This downgrade assumes a clean DB or that all markets have
    a corresponding events record (for FK re-linkage). On a populated DB,
    you may need to manually reconcile orphaned markets first.
    """
    # -- Restore markets.event_id VARCHAR column --
    op.execute("""
        ALTER TABLE markets
        ADD COLUMN event_id VARCHAR(100)
    """)

    # -- Backfill event_id from events table using event_internal_id --
    op.execute("""
        UPDATE markets m
        SET event_id = e.event_id
        FROM events e
        WHERE m.event_internal_id = e.id
    """)

    # -- Rebuild FK from markets.event_id -> events.event_id --
    # (event_id is still UNIQUE at this point, so FK is valid)
    op.execute("""
        ALTER TABLE markets
        ADD CONSTRAINT markets_event_id_fkey
        FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
    """)
    op.execute("""
        CREATE INDEX idx_markets_event
        ON markets(event_id)
    """)

    # -- Drop the new integer FK column from markets --
    # Must drop current_markets view first (depends on event_internal_id via SELECT *)
    op.execute("DROP VIEW IF EXISTS current_markets CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_markets_event_internal")
    op.execute("""
        ALTER TABLE markets
        DROP CONSTRAINT IF EXISTS fk_markets_event_internal
    """)
    op.execute("""
        ALTER TABLE markets
        DROP COLUMN event_internal_id
    """)
    # Recreate view with restored VARCHAR event_id column
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT * FROM markets WHERE row_current_ind = TRUE
    """)

    # -- Restore event_id as PRIMARY KEY --
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT IF EXISTS uq_events_platform_external
    """)
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT IF EXISTS uq_events_event_id
    """)
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT events_pkey
    """)
    op.execute("""
        ALTER TABLE events
        ADD PRIMARY KEY (event_id)
    """)

    # -- Drop the surrogate id column --
    op.execute("""
        ALTER TABLE events
        DROP COLUMN id
    """)
