"""Split markets table into markets (dimension) + market_snapshots (fact).

The old markets table is a monolith: static identity columns (ticker, title,
type) are duplicated across every SCD Type 2 price snapshot. This migration
splits it into:

  - `markets` (dimension): stable identity + lifecycle state. One row per
    market. NOT versioned — status is mutable via UPDATE.
  - `market_snapshots` (fact): volatile pricing data. SCD Type 2 versioned.
    One current row + N historical rows per market.

Column renames per batch plan:
  - yes_price  → yes_ask_price  (clarifies these are Kalshi ask prices)
  - no_price   → no_ask_price
  - New columns: yes_bid_price, no_bid_price, last_price, liquidity

Transitional columns:
  - markets.market_id VARCHAR(100) is KEPT temporarily for backward
    compatibility with downstream JOINs (edges, positions, trades,
    settlements still JOIN on market_id VARCHAR). Migration 0022 adds
    integer FKs to downstream tables, then drops market_id.

Dropped columns:
  - market_uuid UUID (dead — never used in CRUD or pollers)
  - SCD columns on dimension table (versioning moves to market_snapshots)

This is a CLEAN DB migration — no production data to preserve. All
operations are safe to run directly.

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-20

Related:
- Issue #396, #366: ID architecture + fact/dim split
- migration_batch_plan_v1.md: Migration 0021 spec
- S25 council findings: 8 schema changes approved
- ADR pending: fact/dimension split decision
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: str = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Split markets into dimension + fact tables.

    Steps:
    1. Drop current_markets view (depends on old markets columns)
    2. Rename markets → markets_old
    3. Create new markets (dimension) table
    4. Create market_snapshots (fact) table
    5. Migrate data: dimension rows from markets_old
    6. Migrate data: snapshot rows from markets_old
    7. Drop markets_old
    8. Create indexes on new tables
    9. Recreate current_markets view as dimension + snapshot JOIN

    Educational Note:
        The markets table currently stores BOTH identity (ticker, title)
        and volatile pricing (yes_price, no_price). SCD Type 2 versioning
        duplicates identity data on every price change (~100 versions/market/day).

        After the split:
        - markets (dimension): 1 row per market. Status is mutable.
        - market_snapshots (fact): N rows per market. SCD Type 2 versioned.

        This reduces storage, simplifies queries (dimension lookups don't
        need row_current_ind), and cleanly separates identity from pricing.
    """
    # -- Step 1: Drop current_markets view --
    # This view is SELECT * FROM markets WHERE row_current_ind = TRUE.
    # It depends on columns we're about to restructure.
    op.execute("DROP VIEW IF EXISTS current_markets")

    # -- Step 2: Rename old table --
    # We rename rather than drop so we can migrate data.
    op.execute("ALTER TABLE markets RENAME TO markets_old")

    # Also rename indexes and constraints to avoid naming collisions.
    # PostgreSQL doesn't auto-rename these when the table is renamed.
    op.execute("ALTER INDEX IF EXISTS idx_markets_platform RENAME TO idx_markets_old_platform")
    op.execute("ALTER INDEX IF EXISTS idx_markets_current RENAME TO idx_markets_old_current")
    op.execute("ALTER INDEX IF EXISTS idx_markets_status RENAME TO idx_markets_old_status")
    op.execute("ALTER INDEX IF EXISTS idx_markets_market_id RENAME TO idx_markets_old_market_id")
    op.execute(
        "ALTER INDEX IF EXISTS idx_markets_unique_current RENAME TO idx_markets_old_unique_current"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_markets_unique_ticker_current "
        "RENAME TO idx_markets_old_unique_ticker_current"
    )
    op.execute("ALTER INDEX IF EXISTS idx_markets_history RENAME TO idx_markets_old_history")
    op.execute(
        "ALTER INDEX IF EXISTS idx_markets_event_internal RENAME TO idx_markets_old_event_internal"
    )

    # -- Step 3: Create new markets (dimension) table --
    #
    # One row per market. NOT versioned (no SCD columns).
    # Status is mutable (open → closed → settled → halted).
    # market_id VARCHAR is TRANSITIONAL — kept for downstream JOIN compat
    # until migration 0022 adds integer FKs to edges/positions/trades/settlements.
    op.execute("""
        CREATE TABLE markets (
            -- Surrogate primary key
            id SERIAL PRIMARY KEY,

            -- Transitional: kept for backward-compatible JOINs with
            -- edges, positions, trades, settlements (all have market_id VARCHAR).
            -- Migration 0022 adds integer FKs, then this column is dropped.
            market_id VARCHAR(100) NOT NULL,

            -- Platform + external identity
            platform_id VARCHAR(50) NOT NULL
                REFERENCES platforms(platform_id) ON DELETE CASCADE,
            event_internal_id INTEGER
                REFERENCES events(id) ON DELETE CASCADE,
            external_id VARCHAR(100) NOT NULL,

            -- Human-readable identifiers
            ticker VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,

            -- Market classification
            market_type VARCHAR(20) NOT NULL DEFAULT 'binary'
                CHECK (market_type IN ('binary', 'categorical', 'scalar')),

            -- Lifecycle state (mutable — updated directly, not versioned)
            status VARCHAR(20) NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'closed', 'settled', 'halted')),
            settlement_value DECIMAL(10,4)
                CHECK (settlement_value >= 0.0000 AND settlement_value <= 1.0000),

            -- Extensible metadata
            metadata JSONB,

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            -- Uniqueness constraints
            UNIQUE(platform_id, external_id),
            UNIQUE(ticker),
            UNIQUE(market_id)
        )
    """)

    # -- Step 4: Create market_snapshots (fact) table --
    #
    # SCD Type 2 versioned. One current row + N historical rows per market.
    # Column names follow the batch plan: yes_ask_price, no_ask_price, etc.
    # These clarify that Kalshi prices are ASK prices, not implied probabilities.
    op.execute("""
        CREATE TABLE market_snapshots (
            -- Surrogate primary key
            id SERIAL PRIMARY KEY,

            -- FK to dimension table
            market_id INTEGER NOT NULL
                REFERENCES markets(id) ON DELETE CASCADE,

            -- Pricing columns (Kalshi ask prices, NOT implied probabilities)
            -- yes_ask_price + no_ask_price > 1.0 is normal (spread included)
            -- At settlement, both can reach 1.0 or 0.0
            yes_ask_price DECIMAL(10,4)
                CHECK (yes_ask_price >= 0.0000 AND yes_ask_price <= 1.0000),
            no_ask_price DECIMAL(10,4)
                CHECK (no_ask_price >= 0.0000 AND no_ask_price <= 1.0000),

            -- Bid prices (may be NULL if not available from API)
            yes_bid_price DECIMAL(10,4)
                CHECK (yes_bid_price >= 0.0000 AND yes_bid_price <= 1.0000),
            no_bid_price DECIMAL(10,4)
                CHECK (no_bid_price >= 0.0000 AND no_bid_price <= 1.0000),

            -- Last trade price
            last_price DECIMAL(10,4)
                CHECK (last_price >= 0.0000 AND last_price <= 1.0000),

            -- Market microstructure
            spread DECIMAL(10,4)
                CHECK (spread >= 0.0000 AND spread <= 1.0000),
            volume INTEGER CHECK (volume >= 0),
            open_interest INTEGER CHECK (open_interest >= 0),
            liquidity DECIMAL(10,4),

            -- SCD Type 2 versioning columns
            row_start_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            row_end_ts TIMESTAMP WITH TIME ZONE,
            row_current_ind BOOLEAN NOT NULL DEFAULT TRUE,

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # -- Step 5: Migrate dimension data from markets_old --
    #
    # Insert ONE row per unique market (the current version).
    # On a clean DB this may insert 0 rows. On a DB with data, we pick
    # the row_current_ind = TRUE version for each ticker.
    op.execute("""
        INSERT INTO markets (
            market_id, platform_id, event_internal_id, external_id,
            ticker, title, market_type, status, settlement_value,
            metadata, created_at, updated_at
        )
        SELECT
            market_id, platform_id, event_internal_id, external_id,
            ticker, title, market_type, status, settlement_value,
            metadata, created_at, updated_at
        FROM markets_old
        WHERE row_current_ind = TRUE
    """)

    # -- Step 6: Migrate snapshot data from markets_old --
    #
    # Insert ALL rows (current + historical) as snapshots.
    # Map old column names to new: yes_price → yes_ask_price, etc.
    op.execute("""
        INSERT INTO market_snapshots (
            market_id, yes_ask_price, no_ask_price,
            spread, volume, open_interest,
            row_start_ts, row_end_ts, row_current_ind,
            created_at, updated_at
        )
        SELECT
            m.id,
            o.yes_price,
            o.no_price,
            o.spread,
            o.volume,
            o.open_interest,
            o.row_start_ts,
            o.row_end_ts,
            o.row_current_ind,
            o.created_at,
            o.updated_at
        FROM markets_old o
        JOIN markets m ON o.ticker = m.ticker
    """)

    # -- Step 7: Drop old table --
    op.execute("DROP TABLE markets_old")

    # -- Step 8: Create indexes --
    #
    # Dimension table indexes
    op.execute("CREATE INDEX idx_markets_platform ON markets(platform_id)")
    op.execute("CREATE INDEX idx_markets_status ON markets(status)")
    op.execute("CREATE INDEX idx_markets_event_internal ON markets(event_internal_id)")
    op.execute("CREATE INDEX idx_markets_market_id ON markets(market_id)")

    # Snapshot table indexes
    op.execute("CREATE INDEX idx_market_snapshots_market ON market_snapshots(market_id)")
    op.execute(
        "CREATE INDEX idx_market_snapshots_current "
        "ON market_snapshots(row_current_ind) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_market_snapshots_unique_current "
        "ON market_snapshots(market_id) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX idx_market_snapshots_history ON market_snapshots(market_id, created_at DESC)"
    )

    # -- Step 9: Recreate current_markets view --
    #
    # Now a JOIN between dimension + current snapshot.
    # Downstream code that queries current_markets gets both identity
    # and current pricing in one view.
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT
            m.id,
            m.market_id,
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


def downgrade() -> None:
    """Reverse the markets split — merge back into single table.

    This is a destructive downgrade: snapshot history beyond the current
    row is lost (the old schema only supported SCD on the monolith).
    """
    op.execute("DROP VIEW IF EXISTS current_markets")
    op.execute("DROP TABLE IF EXISTS market_snapshots")
    op.execute("DROP TABLE IF EXISTS markets")

    # Recreate original markets table structure would go here.
    # For a clean DB migration, a full downgrade is not implemented.
    # If needed, re-run from 0001 baseline.
    raise NotImplementedError(
        "Full downgrade not implemented for clean-DB migration. Re-run from baseline if needed."
    )
