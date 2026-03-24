"""Add kalshi_team_code to teams table and drop unused external_ids JSONB.

Teams need a Kalshi-specific team code for matching Kalshi event tickers to
games. Most teams use the same code on Kalshi as their ESPN team_code, but
some differ (e.g., Kalshi uses "JAC" for Jacksonville, ESPN uses "JAX";
Kalshi uses "LA" for the Rams, ESPN uses "LAR").

The external_ids JSONB column was added in migration 0001 but never populated
by any code path. Removing it keeps the schema clean.

Steps:
    1. ADD COLUMN kalshi_team_code VARCHAR(10) to teams
    2. CREATE partial INDEX on (kalshi_team_code, league) WHERE NOT NULL
    3. DROP COLUMN external_ids (unused JSONB)

Revision ID: 0041
Revises: 0040
Create Date: 2026-03-23

Related:
    - Issue #462: Event-to-game matching
    - Migration 0001: Original teams table with external_ids
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: str = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add kalshi_team_code column and drop unused external_ids."""
    # -- Step 1: Add kalshi_team_code column --
    op.execute("ALTER TABLE teams ADD COLUMN kalshi_team_code VARCHAR(10)")

    # -- Step 2: Partial index for fast lookups by Kalshi code + league --
    op.execute("""
        CREATE INDEX idx_teams_kalshi_code
        ON teams(kalshi_team_code, league)
        WHERE kalshi_team_code IS NOT NULL
    """)

    # -- Step 3: Drop unused external_ids JSONB column --
    # This column was created in migration 0001 but never populated.
    op.execute("ALTER TABLE teams DROP COLUMN IF EXISTS external_ids")


def downgrade() -> None:
    """Revert: drop kalshi_team_code, restore external_ids."""
    # Drop index first
    op.execute("DROP INDEX IF EXISTS idx_teams_kalshi_code")

    # Drop column
    op.execute("ALTER TABLE teams DROP COLUMN IF EXISTS kalshi_team_code")

    # Restore external_ids JSONB column
    op.execute("ALTER TABLE teams ADD COLUMN external_ids JSONB")
