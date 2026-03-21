"""Create market_trades table for public trade tape data.

Kalshi exposes a public trade tape (all fills on a market, not just ours).
This data reveals volume patterns, price discovery, and liquidity -- critical
signals for ML models in Phase 4+. Distinct from the trades table which
stores only our portfolio fills.

Steps:
    1. CREATE TABLE market_trades with FKs, dedup constraint, CHECK constraints
    2. Add indexes for common query patterns (market lookup, time-series, dedup)

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0028 spec
- Issue #402: Add market_trades table for public trade tape
- ADR-002: Decimal Precision for All Financial Data
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: str = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create market_trades table for public trade tape persistence.

    Design intent:
        - Stores ALL public trades on a market (the tape), not just our fills
        - Append-only: rows are never updated once created
        - Dedup via UNIQUE(platform_id, external_trade_id) + ON CONFLICT DO NOTHING
        - yes_price/no_price are EXECUTED trade prices (not order book quotes),
          hence named without _ask_ suffix
        - taker_side reveals aggressor direction (market signal for ML)
        - count is Kalshi's aggregated contract count per trade record
    """
    # ------------------------------------------------------------------
    # Step 1: CREATE TABLE market_trades
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE market_trades (
            id SERIAL PRIMARY KEY,

            -- Platform + external identity (Kalshi's trade UUID)
            platform_id VARCHAR(50) NOT NULL
                REFERENCES platforms(platform_id) ON DELETE CASCADE,
            external_trade_id VARCHAR(100) NOT NULL,

            -- Market reference (integer FK per surrogate PK pattern)
            market_internal_id INTEGER NOT NULL
                REFERENCES markets(id) ON DELETE CASCADE,

            -- Trade data
            count INTEGER NOT NULL CHECK (count > 0),
            yes_price DECIMAL(10,4)
                CHECK (yes_price IS NULL OR (yes_price >= 0.0000 AND yes_price <= 1.0000)),
            no_price DECIMAL(10,4)
                CHECK (no_price IS NULL OR (no_price >= 0.0000 AND no_price <= 1.0000)),
            taker_side VARCHAR(10)
                CHECK (taker_side IS NULL OR taker_side IN ('yes', 'no')),

            -- Timestamps
            trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
            collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            -- Dedup
            CONSTRAINT uq_market_trades_platform_external
                UNIQUE (platform_id, external_trade_id)
        )
    """)

    # ------------------------------------------------------------------
    # Step 2: Add indexes for common query patterns
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX idx_market_trades_market ON market_trades(market_internal_id)")
    op.execute(
        "CREATE INDEX idx_market_trades_market_time ON market_trades(market_internal_id, trade_time DESC)"
    )
    op.execute("CREATE INDEX idx_market_trades_time ON market_trades(trade_time DESC)")


def downgrade() -> None:
    """Reverse: drop indexes and market_trades table."""
    # Step 1: Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_market_trades_time")
    op.execute("DROP INDEX IF EXISTS idx_market_trades_market_time")
    op.execute("DROP INDEX IF EXISTS idx_market_trades_market")

    # Step 2: Drop table
    op.execute("DROP TABLE IF EXISTS market_trades")
