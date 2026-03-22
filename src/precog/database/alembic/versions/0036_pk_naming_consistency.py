"""Rename inconsistent PKs to `id` for naming consistency.

All data tables should use `id` as their surrogate PK column name,
matching the pattern established in migrations 0019-0022 (series, events,
markets all use `id`).

Tables affected:
    - trades: trade_id -> id
    - settlements: settlement_id -> id
    - account_balance: balance_id -> id

No FK references point to these columns, so the rename is safe.

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-21

Related:
    - migration_batch_plan_v1.md: PK naming consistency spec
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036"
down_revision: str = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename trade_id, settlement_id, balance_id to id."""
    op.execute("ALTER TABLE trades RENAME COLUMN trade_id TO id")
    op.execute("ALTER TABLE settlements RENAME COLUMN settlement_id TO id")
    op.execute("ALTER TABLE account_balance RENAME COLUMN balance_id TO id")


def downgrade() -> None:
    """Restore original PK column names."""
    op.execute("ALTER TABLE trades RENAME COLUMN id TO trade_id")
    op.execute("ALTER TABLE settlements RENAME COLUMN id TO settlement_id")
    op.execute("ALTER TABLE account_balance RENAME COLUMN id TO balance_id")
