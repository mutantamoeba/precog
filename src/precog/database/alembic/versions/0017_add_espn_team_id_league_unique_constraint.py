"""Add UNIQUE constraint on (espn_team_id, league) to teams table.

Prevents duplicate ESPN team IDs within the same league, which caused
data corruption when multiple teams shared the same ESPN ID (e.g.,
game_states linked to wrong teams).

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-11

Related:
- Issue #312: ESPN team ID validation and startup integrity checks
- Issue #313: Deferred external ID table (future multi-provider support)
- Migration 0003: Added UNIQUE(team_code, sport) composite constraint
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add UNIQUE(espn_team_id, league) constraint to teams table.

    Educational Note:
        This constraint prevents the root cause of the ESPN ID mismatch
        bug: if two teams in the same league accidentally get the same
        ESPN ID (e.g., from a bad seed file), PostgreSQL will reject the
        INSERT/UPDATE rather than silently creating data corruption.

        The constraint is partial — it only applies to rows WHERE
        espn_team_id IS NOT NULL, so teams without ESPN IDs are
        not affected.
    """
    # Use a partial unique index (excludes NULLs) rather than a table constraint
    # This allows multiple teams to have NULL espn_team_id (e.g., unseeded teams)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_espn_id_league_unique
        ON teams(espn_team_id, league)
        WHERE espn_team_id IS NOT NULL
    """)

    op.execute("""
        COMMENT ON INDEX idx_teams_espn_id_league_unique IS
        'Prevents duplicate ESPN team IDs within the same league. Partial index excludes NULLs.'
    """)


def downgrade() -> None:
    """Remove the ESPN ID uniqueness constraint.

    WARNING: After removing this constraint, duplicate ESPN IDs can
    be inserted, which may cause game_states to link to wrong teams.
    """
    op.execute("DROP INDEX IF EXISTS idx_teams_espn_id_league_unique")
