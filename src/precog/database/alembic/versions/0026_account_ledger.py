"""Create account_ledger table for append-only transaction log.

The account_balance table uses SCD Type 2 to track balance snapshots, but does
not explain WHY the balance changed. The account_ledger table provides an
append-only transaction log that links balance changes to their causes
(deposits, withdrawals, trade P&L, fees, rebates).

Steps:
    1. CREATE TABLE account_ledger with financials, reference, and order FK
    2. Add indexes for common query patterns

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0026 spec
- ADR-002: Decimal Precision for All Financial Data
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: str = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create account_ledger table for tracking balance change causation.

    Design intent:
        - Append-only: rows are never updated or deleted
        - Links to orders via FK for trade-related entries
        - Polymorphic reference_type + reference_id for flexible sourcing
        - amount CAN be negative (withdrawals, fees)
        - running_balance cannot go below zero
    """
    # ------------------------------------------------------------------
    # Step 1: CREATE TABLE account_ledger
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE account_ledger (
            id SERIAL PRIMARY KEY,

            -- Platform identity
            platform_id VARCHAR(50) NOT NULL
                REFERENCES platforms(platform_id) ON DELETE CASCADE,

            -- Transaction classification
            transaction_type VARCHAR(20) NOT NULL
                CHECK (transaction_type IN (
                    'deposit', 'withdrawal', 'trade_pnl', 'fee', 'rebate', 'adjustment'
                )),

            -- Financials (DECIMAL only, never float)
            amount DECIMAL(10,4) NOT NULL,
            running_balance DECIMAL(10,4) NOT NULL
                CHECK (running_balance >= 0.0000),
            currency VARCHAR(10) NOT NULL DEFAULT 'USD',

            -- Reference to source entity (polymorphic)
            reference_type VARCHAR(20)
                CHECK (reference_type IS NULL OR reference_type IN (
                    'order', 'settlement', 'trade', 'manual', 'system'
                )),
            reference_id INTEGER,

            -- Direct order FK for trade-related entries
            order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,

            -- Human-readable description
            description TEXT,

            -- Immutable timestamp (append-only, no updates)
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------
    # Step 2: Add indexes for common query patterns
    # ------------------------------------------------------------------
    # idx_ledger_platform_date covers platform_id-only queries via leading column
    op.execute(
        "CREATE INDEX idx_ledger_platform_date ON account_ledger(platform_id, created_at DESC)"
    )
    op.execute("CREATE INDEX idx_ledger_type ON account_ledger(transaction_type)")
    op.execute(
        "CREATE INDEX idx_ledger_order ON account_ledger(order_id) WHERE order_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_ledger_reference ON account_ledger(reference_type, reference_id) "
        "WHERE reference_type IS NOT NULL"
    )


def downgrade() -> None:
    """Reverse: drop indexes and account_ledger table."""
    # Step 1: Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_ledger_reference")
    op.execute("DROP INDEX IF EXISTS idx_ledger_order")
    op.execute("DROP INDEX IF EXISTS idx_ledger_type")
    op.execute("DROP INDEX IF EXISTS idx_ledger_platform_date")

    # Step 2: Drop table
    op.execute("DROP TABLE IF EXISTS account_ledger")
