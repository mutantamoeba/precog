"""Add SERIAL surrogate primary key to series table, update events FK.

Decouples internal identity from external Kalshi identifiers. Integer PKs
provide better join performance (4 bytes vs 100 bytes for VARCHAR FK),
smaller index footprint, and enable multi-platform support via
UNIQUE(platform_id, external_id).

Changes to `series` table:
- Add `id SERIAL` column (new primary key)
- Demote `series_id VARCHAR(100)` from PK to UNIQUE business key
- Add UNIQUE(platform_id, external_id) composite constraint
- Add index on `id` (implicit via PRIMARY KEY)

Changes to `events` table:
- Add `series_internal_id INTEGER` column with FK to series(id)
- Drop old `series_id VARCHAR(100)` FK column
- Rebuild index on the new FK column

This is a CLEAN DB migration -- no data to preserve. All ALTER TABLE
operations are safe to run directly without data backfill.

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-19

Related:
- Issue #365: Schema skepticism audit (surrogate PK recommendation)
- migration_batch_plan_v1.md: Migration 0019 spec
- ADR pending: ID architecture decision (Elrond council)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add surrogate PK to series, migrate events FK to integer.

    Steps:
    1. Add SERIAL id column to series
    2. Drop existing PRIMARY KEY on series_id
    3. Set id as new PRIMARY KEY
    4. Add UNIQUE constraint on series_id (business key)
    5. Add UNIQUE(platform_id, external_id) composite constraint
    6. Add series_internal_id INTEGER column to events
    7. Drop old events.series_id VARCHAR FK + index
    8. Add FK constraint + index on events.series_internal_id

    Educational Note:
        Surrogate keys (auto-incrementing integers) decouple internal
        identity from external business identifiers. This is critical
        for multi-platform support: two platforms could use the same
        external_id, but the surrogate PK keeps them distinct.

        The old series_id VARCHAR column is retained as a UNIQUE business
        key for human readability and backward-compatible lookups.
    """
    # ── Step 1: Add SERIAL id column to series ──
    # SERIAL = INTEGER + auto-increment sequence. On a clean DB this is
    # a simple ADD COLUMN. The NOT NULL + DEFAULT nextval() are implicit.
    op.execute("""
        ALTER TABLE series
        ADD COLUMN id SERIAL
    """)

    # ── Step 2: Drop existing PRIMARY KEY on series_id ──
    # The PK constraint name follows PostgreSQL's default naming convention.
    op.execute("""
        ALTER TABLE series
        DROP CONSTRAINT series_pkey
    """)

    # ── Step 3: Set id as new PRIMARY KEY ──
    op.execute("""
        ALTER TABLE series
        ADD PRIMARY KEY (id)
    """)

    # ── Step 4: Add UNIQUE constraint on series_id (business key) ──
    # Keeps series_id queryable and prevents duplicates, but it's no
    # longer the primary key. Also add NOT NULL since it was previously
    # the PK (and thus implicitly NOT NULL), but demoting it loses that.
    op.execute("""
        ALTER TABLE series
        ALTER COLUMN series_id SET NOT NULL
    """)
    op.execute("""
        ALTER TABLE series
        ADD CONSTRAINT uq_series_series_id UNIQUE (series_id)
    """)

    # ── Step 5: Add UNIQUE(platform_id, external_id) composite constraint ──
    # Enables multi-platform support: same external_id on different platforms
    # is allowed, but same (platform_id, external_id) pair is not.
    op.execute("""
        ALTER TABLE series
        ADD CONSTRAINT uq_series_platform_external UNIQUE (platform_id, external_id)
    """)

    # ── Step 6: Add series_internal_id INTEGER column to events ──
    # Named series_internal_id to avoid confusion during transition.
    # Nullable: events can exist without a series (orphaned or unlinked data).
    # ON DELETE SET NULL matches the original series_id FK behavior.
    op.execute("""
        ALTER TABLE events
        ADD COLUMN series_internal_id INTEGER
    """)
    op.execute("""
        ALTER TABLE events
        ADD CONSTRAINT fk_events_series_internal
        FOREIGN KEY (series_internal_id) REFERENCES series(id) ON DELETE SET NULL
    """)

    # ── Step 7: Drop old events.series_id VARCHAR FK + index ──
    # Drop FK constraint first, then index, then column.
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT IF EXISTS events_series_id_fkey
    """)
    op.execute("DROP INDEX IF EXISTS idx_events_series")
    op.execute("""
        ALTER TABLE events
        DROP COLUMN series_id
    """)

    # ── Step 8: Add index on events.series_internal_id ──
    # Replaces the old idx_events_series index for FK lookups.
    op.execute("""
        CREATE INDEX idx_events_series_internal
        ON events(series_internal_id)
    """)

    op.execute("""
        COMMENT ON COLUMN series.id IS
        'Surrogate primary key (SERIAL). Internal identity, never exposed to users.'
    """)
    op.execute("""
        COMMENT ON COLUMN series.series_id IS
        'Business key from Kalshi API (e.g., KXNFLGAME). Unique, human-readable.'
    """)
    op.execute("""
        COMMENT ON COLUMN events.series_internal_id IS
        'FK to series(id). Integer surrogate key replaces old VARCHAR series_id FK.'
    """)


def downgrade() -> None:
    """Reverse surrogate PK: restore series_id as PK, events.series_id as VARCHAR FK.

    WARNING: This downgrade assumes a clean DB or that all events have
    a corresponding series record (for FK re-linkage). On a populated DB,
    you may need to manually reconcile orphaned events first.
    """
    # ── Restore events.series_id VARCHAR column ──
    op.execute("""
        ALTER TABLE events
        ADD COLUMN series_id VARCHAR(100)
    """)

    # ── Rebuild FK from events.series_id -> series.series_id ──
    # (series_id is still UNIQUE at this point, so FK is valid)
    op.execute("""
        ALTER TABLE events
        ADD CONSTRAINT events_series_id_fkey
        FOREIGN KEY (series_id) REFERENCES series(series_id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX idx_events_series
        ON events(series_id)
    """)

    # ── Drop the new integer FK column from events ──
    op.execute("DROP INDEX IF EXISTS idx_events_series_internal")
    op.execute("""
        ALTER TABLE events
        DROP CONSTRAINT IF EXISTS fk_events_series_internal
    """)
    op.execute("""
        ALTER TABLE events
        DROP COLUMN series_internal_id
    """)

    # ── Restore series_id as PRIMARY KEY ──
    op.execute("""
        ALTER TABLE series
        DROP CONSTRAINT IF EXISTS uq_series_platform_external
    """)
    op.execute("""
        ALTER TABLE series
        DROP CONSTRAINT IF EXISTS uq_series_series_id
    """)
    op.execute("""
        ALTER TABLE series
        DROP CONSTRAINT series_pkey
    """)
    op.execute("""
        ALTER TABLE series
        ADD PRIMARY KEY (series_id)
    """)

    # ── Drop the surrogate id column ──
    op.execute("""
        ALTER TABLE series
        DROP COLUMN id
    """)
