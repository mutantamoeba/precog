"""
Add SCD Type 2 temporal columns and unique index to account_balance.

Revision ID: 0049
Revises: 0048
Create Date: 2026-04-05

account_balance is the only SCD Type 2 table missing row_start_ts and row_end_ts
columns. This migration adds them for point-in-time balance reconstruction, which
Phase 2 trade execution requires for pre-trade balance checks and P&L reporting.

Also adds a partial unique index on (platform_id) WHERE row_current_ind = TRUE
to prevent concurrent SCD writes from creating duplicate current rows.

Changes:
    1. ADD COLUMN row_start_ts TIMESTAMPTZ DEFAULT NOW()
    2. ADD COLUMN row_end_ts TIMESTAMPTZ (nullable)
    3. Backfill row_start_ts from created_at for existing rows
    4. CREATE UNIQUE INDEX idx_balance_unique_current ON account_balance(platform_id)
       WHERE row_current_ind = TRUE

Related:
    - C4 Phase Gate findings H1 (blocker) and H2 (warning)
    - Issue #339: Phase 2 requirements formalization
    - Pattern 2 in CLAUDE.md: SCD Type 2 Versioning
    - REQ-DB-004: SCD Type 2 for Frequently-Changing Data
"""

from alembic import op

# revision identifiers
revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add temporal columns
    op.execute("""
        ALTER TABLE account_balance
        ADD COLUMN row_start_ts TIMESTAMPTZ DEFAULT NOW(),
        ADD COLUMN row_end_ts TIMESTAMPTZ
    """)

    # Step 2: Backfill row_start_ts from created_at for existing rows
    # This preserves the original creation time as the version start time
    op.execute("""
        UPDATE account_balance
        SET row_start_ts = created_at
        WHERE row_start_ts IS NULL OR row_start_ts != created_at
    """)

    # Step 3: Set row_end_ts for historical rows (non-current)
    # Historical rows ended when the next row for the same platform started
    op.execute("""
        UPDATE account_balance ab
        SET row_end_ts = (
            SELECT MIN(ab2.created_at)
            FROM account_balance ab2
            WHERE ab2.platform_id = ab.platform_id
              AND ab2.created_at > ab.created_at
        )
        WHERE ab.row_current_ind = FALSE
          AND ab.row_end_ts IS NULL
    """)

    # Step 4: Add partial unique index to prevent duplicate current rows
    # Only one row per platform can be current at any time
    op.execute("""
        CREATE UNIQUE INDEX idx_balance_unique_current
        ON account_balance(platform_id)
        WHERE row_current_ind = TRUE
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_balance_unique_current")
    op.execute("""
        ALTER TABLE account_balance
        DROP COLUMN IF EXISTS row_end_ts,
        DROP COLUMN IF EXISTS row_start_ts
    """)
