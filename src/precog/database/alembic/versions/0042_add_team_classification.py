"""Add classification column to teams table.

Teams need a classification to distinguish FBS from Division III in college
sports. This matters for matching (Kalshi only has FBS/FCS markets) and for
data quality (filtering by division level).

Classification values:
    - 'fbs'          NCAA Division I Football Bowl Subdivision
    - 'fcs'          NCAA Division I Football Championship Subdivision
    - 'd2'           NCAA Division II
    - 'd3'           NCAA Division III
    - 'd1'           NCAA Division I (basketball)
    - 'professional' Pro leagues (NFL, NBA, NHL, etc.)
    - NULL           Not yet classified

Steps:
    1. ADD COLUMN classification VARCHAR(20) to teams (nullable)
    2. UPDATE pro league teams to 'professional'

Revision ID: 0042
Revises: 0041
Create Date: 2026-03-26

Related:
    - Issue #486: Team code collision fix + division classification
    - Migration 0018: Partial unique index for pro leagues
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0042"
down_revision: str = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add classification column and set pro league defaults."""
    # -- Step 1: Add nullable classification column --
    op.execute("ALTER TABLE teams ADD COLUMN classification VARCHAR(20)")

    # -- Step 2: Set pro leagues to 'professional' --
    op.execute(
        "UPDATE teams SET classification = 'professional' "
        "WHERE league IN ('nfl', 'nba', 'nhl', 'wnba', 'mlb', 'mls')"
    )


def downgrade() -> None:
    """Revert: drop classification column."""
    op.execute("ALTER TABLE teams DROP COLUMN IF EXISTS classification")
