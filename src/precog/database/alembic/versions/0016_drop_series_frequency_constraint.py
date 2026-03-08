"""Drop series frequency CHECK constraint to match Kalshi API vocabulary.

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-07

The Kalshi API sends frequency values beyond our CHECK constraint allowlist
(e.g., 'custom', 'annual', 'quarterly'). The constraint causes INSERT failures
that cascade to FK errors on events and markets, silently losing trading data.

Per Pattern 33 (API Vocabulary Alignment): adapt our schema to match the
external API, don't restrict it with an incomplete allowlist.

Related:
- Pattern 33: API Vocabulary Alignment
- Migration 0011: Previous constraint update (still too restrictive)
- KXNFLGAME FK constraint errors in e2e tests
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the series_frequency_check constraint.

    The frequency column remains VARCHAR(20) - we just remove the CHECK
    constraint that was rejecting valid Kalshi API values.

    Educational Note:
        PostgreSQL CHECK constraints are enforced on INSERT and UPDATE.
        When the Kalshi API returns a frequency value not in our allowlist,
        the entire INSERT fails. Since events and markets have FK references
        to series, this cascading failure prevents ALL data collection for
        that series.
    """
    op.execute("ALTER TABLE series DROP CONSTRAINT IF EXISTS series_frequency_check")


def downgrade() -> None:
    """Re-add the frequency CHECK constraint.

    WARNING: This will fail if any rows contain frequency values outside
    the allowlist (e.g., 'custom', 'annual'). Clean up non-conforming
    rows first, or use DROP CONSTRAINT IF EXISTS + re-add pattern.
    In practice this is a forward-only migration.
    """
    op.execute("""
        ALTER TABLE series
        ADD CONSTRAINT series_frequency_check
        CHECK (frequency IN ('daily', 'weekly', 'monthly', 'event', 'once'))
    """)
