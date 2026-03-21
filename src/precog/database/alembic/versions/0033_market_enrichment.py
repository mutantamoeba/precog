"""Promote JSONB fields to proper columns + add enrichment columns on markets.

Market lifecycle timestamps (open_time, close_time, expiration_time) and
subtitle are currently buried in markets.metadata JSONB. They need to be
proper indexed columns for the web GUI and strategy logic.

Additional enrichment columns (outcome_label, league, bracket_count,
source_url) improve UX and analytics.

Steps:
    1. ADD columns: subtitle, open_time, close_time, expiration_time,
       outcome_label, league, bracket_count, source_url
    2. MIGRATE data from metadata JSONB into new columns (for existing rows)
    3. CREATE indexes on new columns
    4. DROP/REPLACE current_markets view to include new columns

All new columns are nullable — the poller populates what it can, the rest
stays NULL. No data loss, no constraint changes on existing columns.

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-21

Related:
- Issue #441: Market enrichment columns
- migration_batch_plan_v1.md: Migration 0033 spec
- Migration 0021: markets dimension table creation
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033"
down_revision: str = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add enrichment columns to markets dimension table.

    Educational Note:
        These columns were previously stuffed into the metadata JSONB blob.
        Promoting them to proper columns enables:
        - SQL indexing (filter by close_time, league)
        - Type safety (TIMESTAMPTZ, INTEGER)
        - Cleaner queries (no JSON extraction operators)
        - Web GUI column sorting/filtering
    """
    # -- Step 1: Add new columns to markets dimension table --
    #
    # Lifecycle timestamps — promoted from metadata JSONB
    op.execute("ALTER TABLE markets ADD COLUMN subtitle VARCHAR(255)")
    op.execute("ALTER TABLE markets ADD COLUMN open_time TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE markets ADD COLUMN close_time TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE markets ADD COLUMN expiration_time TIMESTAMP WITH TIME ZONE")

    # Enrichment columns — new data, not from metadata
    op.execute("ALTER TABLE markets ADD COLUMN outcome_label VARCHAR(100)")
    op.execute("ALTER TABLE markets ADD COLUMN league VARCHAR(20)")
    op.execute("ALTER TABLE markets ADD COLUMN bracket_count INTEGER CHECK (bracket_count >= 0)")
    op.execute("ALTER TABLE markets ADD COLUMN source_url VARCHAR(500)")

    # -- Step 2: Migrate existing data from metadata JSONB --
    #
    # Extract subtitle, open_time, close_time, expiration_time from
    # the metadata blob into the new proper columns. Only updates rows
    # where the key exists in metadata.
    op.execute("""
        UPDATE markets
        SET subtitle = metadata->>'subtitle'
        WHERE metadata IS NOT NULL
          AND metadata->>'subtitle' IS NOT NULL
    """)
    op.execute("""
        UPDATE markets
        SET open_time = (metadata->>'open_time')::TIMESTAMP WITH TIME ZONE
        WHERE metadata IS NOT NULL
          AND metadata->>'open_time' IS NOT NULL
    """)
    op.execute("""
        UPDATE markets
        SET close_time = (metadata->>'close_time')::TIMESTAMP WITH TIME ZONE
        WHERE metadata IS NOT NULL
          AND metadata->>'close_time' IS NOT NULL
    """)
    op.execute("""
        UPDATE markets
        SET expiration_time = (metadata->>'expiration_time')::TIMESTAMP WITH TIME ZONE
        WHERE metadata IS NOT NULL
          AND metadata->>'expiration_time' IS NOT NULL
    """)

    # -- Step 3: Clean promoted keys from metadata JSONB --
    #
    # Remove the keys that are now proper columns so they don't drift.
    op.execute("""
        UPDATE markets
        SET metadata = metadata - 'subtitle' - 'open_time' - 'close_time' - 'expiration_time'
        WHERE metadata IS NOT NULL
    """)

    # -- Step 4: Create indexes --
    #
    # Lifecycle timestamps are frequently filtered/sorted in GUI and strategy logic.
    op.execute("CREATE INDEX idx_markets_close_time ON markets(close_time)")
    op.execute("CREATE INDEX idx_markets_expiration_time ON markets(expiration_time)")
    op.execute("CREATE INDEX idx_markets_league ON markets(league)")

    # -- Step 5: Recreate current_markets view --
    #
    # Must include new dimension columns so downstream queries see them.
    op.execute("DROP VIEW IF EXISTS current_markets")
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT
            m.id,
            m.platform_id,
            m.event_internal_id,
            m.external_id,
            m.ticker,
            m.title,
            m.subtitle,
            m.market_type,
            m.status,
            m.settlement_value,
            m.open_time,
            m.close_time,
            m.expiration_time,
            m.outcome_label,
            m.league,
            m.bracket_count,
            m.source_url,
            m.metadata,
            m.created_at,
            m.updated_at,
            ms.yes_ask_price,
            ms.no_ask_price,
            ms.yes_bid_price,
            ms.no_bid_price,
            ms.last_price,
            ms.spread,
            ms.volume,
            ms.open_interest,
            ms.liquidity,
            ms.row_start_ts,
            ms.row_end_ts,
            ms.row_current_ind
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id
            AND ms.row_current_ind = TRUE
    """)


def downgrade() -> None:
    """Remove enrichment columns from markets dimension table."""
    # -- Step 1: Restore current_markets view to pre-0033 definition --
    op.execute("DROP VIEW IF EXISTS current_markets")
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT
            m.id,
            m.platform_id,
            m.event_internal_id,
            m.external_id,
            m.ticker,
            m.title,
            m.market_type,
            m.status,
            m.settlement_value,
            m.metadata,
            m.created_at,
            m.updated_at,
            ms.yes_ask_price,
            ms.no_ask_price,
            ms.yes_bid_price,
            ms.no_bid_price,
            ms.last_price,
            ms.spread,
            ms.volume,
            ms.open_interest,
            ms.liquidity,
            ms.row_start_ts,
            ms.row_end_ts,
            ms.row_current_ind
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id
            AND ms.row_current_ind = TRUE
    """)

    # -- Step 2: Migrate data back into metadata JSONB --
    #
    # Re-stuff the promoted fields back into metadata before dropping columns.
    op.execute("""
        UPDATE markets
        SET metadata = COALESCE(metadata, '{}'::jsonb)
            || CASE WHEN subtitle IS NOT NULL
                THEN jsonb_build_object('subtitle', subtitle)
                ELSE '{}'::jsonb END
            || CASE WHEN open_time IS NOT NULL
                THEN jsonb_build_object('open_time', open_time::text)
                ELSE '{}'::jsonb END
            || CASE WHEN close_time IS NOT NULL
                THEN jsonb_build_object('close_time', close_time::text)
                ELSE '{}'::jsonb END
            || CASE WHEN expiration_time IS NOT NULL
                THEN jsonb_build_object('expiration_time', expiration_time::text)
                ELSE '{}'::jsonb END
    """)

    # -- Step 3: Drop indexes --
    op.execute("DROP INDEX IF EXISTS idx_markets_close_time")
    op.execute("DROP INDEX IF EXISTS idx_markets_expiration_time")
    op.execute("DROP INDEX IF EXISTS idx_markets_league")

    # -- Step 4: Drop columns --
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS subtitle")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS open_time")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS close_time")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS expiration_time")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS outcome_label")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS league")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS bracket_count")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS source_url")
