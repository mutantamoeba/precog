"""
Add Phase 2 indexes for trade execution queries.

Revision ID: 0050
Revises: 0049
Create Date: 2026-04-05

Adds partial indexes to support Phase 2 manual trading query patterns:
- orders(trade_source) for filtering manual trades
- positions(market_internal_id) for market+current lookups

Related:
    - C4 Phase Gate findings H3 and H4
    - REQ-TRADE-001: Order placement pipeline queries
    - REQ-WEB-004: Position management page queries
"""

from alembic import op

# revision identifiers
revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # H3: Partial index on orders(trade_source) for manual trade filtering
    # Phase 2 queries: "show me all manually placed orders"
    op.execute("""
        CREATE INDEX idx_orders_manual_trade_source
        ON orders(trade_source)
        WHERE trade_source = 'manual'
    """)

    # H4: Composite partial index on positions for market+current lookups
    # Phase 2 queries: "what's my current position on this market?"
    op.execute("""
        CREATE INDEX idx_positions_market_current
        ON positions(market_internal_id)
        WHERE row_current_ind = TRUE AND status = 'open'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_positions_market_current")
    op.execute("DROP INDEX IF EXISTS idx_orders_manual_trade_source")
