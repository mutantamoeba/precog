"""Create orderbook_snapshots table for order book depth storage.

Stores full order book depth data for liquidity analysis, slippage
estimation, and market microstructure signals. The existing
market_snapshots table only captures BBO (best bid/ask); this table
stores the full depth at each level.

This is an append-only time-series table (NOT SCD Type 2). Each row
is an immutable point-in-time snapshot of the order book.

Steps:
    1. CREATE TABLE orderbook_snapshots with typed arrays for depth
    2. CREATE indexes for market, time, spread, imbalance lookups
    3. ADD CHECK constraints for spread, depth totals, levels, imbalance

Revision ID: 0034
Revises: 0033
Create Date: 2026-03-21

Related:
- Issue #443: Orderbook snapshots table
- migration_batch_plan_v1.md: Migration 0034 spec
- ADR-002: Decimal Precision for All Financial Data
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: str = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create orderbook_snapshots table with depth arrays and indexes.

    Educational Note:
        PostgreSQL typed arrays (DECIMAL(10,4)[], INTEGER[]) store the
        full order book depth in a single row. This avoids the need for
        a separate orderbook_levels table with one row per level, which
        would be 10-20x more rows and much harder to query atomically.

        The arrays are parallel: bid_prices[i] corresponds to
        bid_quantities[i], and similarly for asks.

    Design decisions:
        - Append-only (no SCD, no row_current_ind) -- time-series data
        - Arrays for depth levels -- compact, atomic reads
        - CHECK constraints on spread, depth totals, levels, imbalance
        - FK to markets(id) with CASCADE -- market deletion cleans up
    """
    # -- Step 1: Create orderbook_snapshots table --
    op.execute("""
        CREATE TABLE orderbook_snapshots (
            id SERIAL PRIMARY KEY,
            market_internal_id INTEGER NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
            snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            best_bid DECIMAL(10,4),
            best_ask DECIMAL(10,4),
            spread DECIMAL(10,4) CHECK (spread IS NULL OR spread >= 0),
            bid_depth_total INTEGER CHECK (bid_depth_total IS NULL OR bid_depth_total >= 0),
            ask_depth_total INTEGER CHECK (ask_depth_total IS NULL OR ask_depth_total >= 0),
            depth_imbalance DECIMAL(10,4) CHECK (depth_imbalance IS NULL OR (depth_imbalance >= -1 AND depth_imbalance <= 1)),
            weighted_mid DECIMAL(10,4),
            bid_prices DECIMAL(10,4)[],
            bid_quantities INTEGER[],
            ask_prices DECIMAL(10,4)[],
            ask_quantities INTEGER[],
            levels INTEGER CHECK (levels IS NULL OR levels >= 0)
        )
    """)

    # -- Step 2: Create indexes --
    #
    # Market lookup: most queries filter by market first
    op.execute("CREATE INDEX idx_orderbook_market ON orderbook_snapshots(market_internal_id)")
    # Time-based queries: history, range scans
    op.execute("CREATE INDEX idx_orderbook_time ON orderbook_snapshots(snapshot_time)")
    # Spread analysis: find thin/wide markets
    op.execute("CREATE INDEX idx_orderbook_spread ON orderbook_snapshots(spread)")
    # Imbalance analysis: detect directional pressure
    op.execute("CREATE INDEX idx_orderbook_imbalance ON orderbook_snapshots(depth_imbalance)")


def downgrade() -> None:
    """Drop orderbook_snapshots table and all indexes."""
    # Indexes are dropped automatically with the table
    op.execute("DROP TABLE IF EXISTS orderbook_snapshots")
