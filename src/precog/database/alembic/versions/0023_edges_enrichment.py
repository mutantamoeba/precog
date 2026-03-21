"""Enrich edges table with analytics-ready columns and lifecycle tracking.

Adds 15 new columns to the edges table for full edge lifecycle tracking:
detection -> recommendation -> execution -> settlement -> outcome.

Also drops the dead probability_matrix_id FK column (the probability_matrices
table itself is dropped later in migration 0030).

New columns:
  - actual_outcome: Settlement result ('yes', 'no', 'void', 'unresolved')
  - settlement_value: Actual settlement price (DECIMAL(10,4))
  - resolved_at: When the edge was resolved
  - strategy_id: FK to strategies(strategy_id) for attribution
  - edge_status: Lifecycle status ('detected' -> 'settled')
  - yes_ask_price, no_ask_price: Kalshi ask price snapshots at detection
  - spread, volume, open_interest, last_price, liquidity: Market microstructure
  - category, subcategory: Market classification
  - execution_environment: 'live', 'paper', 'backtest'

New views:
  - edge_lifecycle: Edges with computed realized_pnl and hours_to_resolution

This is a CLEAN DB migration -- no production data to preserve.

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-21

Related:
- Issue #366: FK integrity
- migration_batch_plan_v1.md: Migration 0023 spec
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add analytics columns, drop probability_matrix_id, create edge_lifecycle view.

    Steps:
    1. Drop current_edges view (Pattern 38 -- view binds to columns)
    2. Drop probability_matrix_id FK + column
    3. Add 15 new columns
    4. Add partial indexes for common query patterns
    5. Recreate current_edges view
    6. Create edge_lifecycle view with computed fields
    """
    # Step 1: Drop current_edges view (Pattern 38)
    # SELECT * views bind to columns at creation time -- dropping a column
    # that the view references will fail with DependentObjectsStillExist.
    op.execute("DROP VIEW IF EXISTS current_edges")

    # Step 2: Drop probability_matrix_id FK and column
    op.execute("ALTER TABLE edges DROP CONSTRAINT IF EXISTS edges_probability_matrix_id_fkey")
    op.execute("ALTER TABLE edges DROP COLUMN IF EXISTS probability_matrix_id")

    # Step 3: Add new columns (all NULLABLE -- existing SCD versions get NULLs)
    op.execute("""
        ALTER TABLE edges ADD COLUMN IF NOT EXISTS actual_outcome VARCHAR(20)
            CHECK (actual_outcome IN ('yes', 'no', 'void', 'unresolved'))
    """)
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS settlement_value DECIMAL(10,4)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE")
    op.execute(
        "ALTER TABLE edges ADD COLUMN IF NOT EXISTS strategy_id INTEGER "
        "REFERENCES strategies(strategy_id) ON DELETE SET NULL"
    )
    op.execute("""
        ALTER TABLE edges ADD COLUMN IF NOT EXISTS edge_status VARCHAR(30)
            DEFAULT 'detected'
            CHECK (edge_status IN (
                'detected', 'recommended', 'acted_on',
                'expired', 'settled', 'void'
            ))
    """)
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS yes_ask_price DECIMAL(10,4)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS no_ask_price DECIMAL(10,4)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS spread DECIMAL(10,4)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS volume INTEGER")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS open_interest INTEGER")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS last_price DECIMAL(10,4)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS liquidity DECIMAL(10,4)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS category VARCHAR(100)")
    op.execute("ALTER TABLE edges ADD COLUMN IF NOT EXISTS subcategory VARCHAR(100)")
    op.execute("""
        ALTER TABLE edges ADD COLUMN IF NOT EXISTS execution_environment VARCHAR(20)
            DEFAULT 'live'
            CHECK (execution_environment IN ('live', 'paper', 'backtest'))
    """)

    # Step 4: Add partial indexes for common analytics queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_strategy "
        "ON edges(strategy_id) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_status "
        "ON edges(edge_status) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_category "
        "ON edges(category) WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_resolved "
        "ON edges(resolved_at) WHERE resolved_at IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_exec_env "
        "ON edges(execution_environment) WHERE row_current_ind = TRUE"
    )

    # Step 5: Recreate current_edges view
    op.execute(
        "CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE"
    )

    # Step 6: Create edge_lifecycle view with computed analytics fields
    op.execute("""
        CREATE OR REPLACE VIEW edge_lifecycle AS
        SELECT
            e.id,
            e.edge_id,
            e.market_internal_id,
            e.model_id,
            e.strategy_id,
            e.expected_value,
            e.true_win_probability,
            e.market_implied_probability,
            e.market_price,
            e.yes_ask_price,
            e.no_ask_price,
            e.edge_status,
            e.actual_outcome,
            e.settlement_value,
            e.confidence_level,
            e.execution_environment,
            e.created_at,
            e.resolved_at,
            -- P&L assumes YES-side position (edge detection = buy YES)
            CASE
                WHEN e.actual_outcome = 'yes' THEN e.settlement_value - e.market_price
                WHEN e.actual_outcome = 'no' THEN e.market_price - e.settlement_value
                ELSE NULL
            END AS realized_pnl,
            CASE
                WHEN e.resolved_at IS NOT NULL AND e.created_at IS NOT NULL
                THEN EXTRACT(EPOCH FROM (e.resolved_at - e.created_at)) / 3600.0
                ELSE NULL
            END AS hours_to_resolution
        FROM edges e
        WHERE e.row_current_ind = TRUE
    """)


def downgrade() -> None:
    """Reverse: drop new columns/views, restore probability_matrix_id."""
    # Drop views first
    op.execute("DROP VIEW IF EXISTS edge_lifecycle")
    op.execute("DROP VIEW IF EXISTS current_edges")

    # Drop new indexes
    for idx in [
        "idx_edges_strategy",
        "idx_edges_status",
        "idx_edges_category",
        "idx_edges_resolved",
        "idx_edges_exec_env",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    # Drop new columns (reverse order of addition)
    for col in [
        "execution_environment",
        "subcategory",
        "category",
        "liquidity",
        "last_price",
        "open_interest",
        "volume",
        "spread",
        "no_ask_price",
        "yes_ask_price",
        "edge_status",
        "strategy_id",
        "resolved_at",
        "settlement_value",
        "actual_outcome",
    ]:
        op.execute(f"ALTER TABLE edges DROP COLUMN IF EXISTS {col}")

    # Re-add probability_matrix_id
    op.execute(
        "ALTER TABLE edges ADD COLUMN probability_matrix_id INTEGER "
        "REFERENCES probability_matrices(probability_id) ON DELETE SET NULL"
    )

    # Recreate current_edges view
    op.execute(
        "CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE"
    )
