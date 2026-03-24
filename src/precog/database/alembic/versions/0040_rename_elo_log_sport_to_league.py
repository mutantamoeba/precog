"""Rename elo_calculation_log.sport column to league.

The sport column in elo_calculation_log stores league codes ("nfl", "nba"),
not sport names. Renaming it to league aligns the column name with its
actual semantics, consistent with the League enum rename in elo_engine.py.

Steps:
    1. RENAME COLUMN sport -> league
    2. DROP + RECREATE index idx_elo_log_sport_date as idx_elo_log_league_date

Revision ID: 0040
Revises: 0039
Create Date: 2026-03-23

Related:
    - Issue #460: Category/subcategory naming (Phase B)
    - Migration 0013: Original elo_calculation_log table + idx_elo_log_sport_date index
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: str = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename elo_calculation_log.sport column to league."""
    # -- Step 1: Rename the column --
    op.execute("ALTER TABLE elo_calculation_log RENAME COLUMN sport TO league")

    # -- Step 2: Recreate index with new column name --
    # Original index from migration 0013: idx_elo_log_sport_date ON (sport, game_date)
    op.execute("DROP INDEX IF EXISTS idx_elo_log_sport_date")
    op.execute("CREATE INDEX idx_elo_log_league_date ON elo_calculation_log(league, game_date)")


def downgrade() -> None:
    """Revert: rename elo_calculation_log.league back to sport."""
    op.execute("DROP INDEX IF EXISTS idx_elo_log_league_date")
    op.execute("ALTER TABLE elo_calculation_log RENAME COLUMN league TO sport")
    op.execute("CREATE INDEX idx_elo_log_sport_date ON elo_calculation_log(sport, game_date)")
