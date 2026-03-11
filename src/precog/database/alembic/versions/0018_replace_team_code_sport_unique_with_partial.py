"""Replace UNIQUE(team_code, sport) with partial unique index for pro leagues.

Drops the full UNIQUE(team_code, sport) constraint that prevented multiple
NCAAF teams from sharing abbreviation codes (e.g., 5 teams with code "WES").
Replaces it with a partial unique index that only enforces uniqueness for
pro leagues (NFL, NBA, NHL, WNBA, MLB, MLS) where codes are naturally unique.

College sports (ncaaf, ncaab, ncaaw) are excluded — they have 1000+ teams
and codes frequently collide. Team identity for college sports uses
ESPN ID via the idx_teams_espn_id_league_unique partial index (migration 0017).

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-11

Related:
- Issue #317: NCAAF team code collisions cause ESPN ID swapping
- Issue #318: Drop UNIQUE(team_code, sport), add partial unique index
- Migration 0003: Originally added UNIQUE(team_code, sport)
- Migration 0017: Added UNIQUE(espn_team_id, league) partial index

WARNING: This is a one-way-door migration. Once college sport teams with
duplicate codes are inserted, the downgrade requires manual deduplication.
Take a pg_dump backup before running this migration.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Pro leagues where team codes are naturally unique (league-assigned).
# College sports (ncaaf, ncaab, ncaaw) are excluded — codes collide.
PRO_LEAGUE_SPORTS = ("nfl", "nba", "nhl", "wnba", "mlb", "soccer")


def upgrade() -> None:
    """Replace full unique constraint with partial index for pro leagues.

    Steps:
    1. Create partial unique index for pro leagues (additive, safe)
    2. Drop the redundant non-unique index (cleanup)
    3. Drop the full UNIQUE constraint (the breaking change)

    Educational Note:
        PostgreSQL partial unique indexes enforce uniqueness only for rows
        matching the WHERE clause. This lets us say "team codes must be
        unique within a sport for NFL/NBA/NHL, but NOT for NCAAF."

        The partial index also supports ON CONFLICT targeting in SQL:
        ON CONFLICT (team_code, sport) WHERE sport IN ('nfl', 'nba', ...)
    """
    # Step 1: Create the partial unique index for pro leagues.
    # This is safe to create while the full constraint exists — no conflicts.
    sports_list = ", ".join(f"'{s}'" for s in PRO_LEAGUE_SPORTS)
    op.execute(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_code_sport_pro
        ON teams(team_code, sport)
        WHERE sport IN ({sports_list})
    """)

    op.execute("""
        COMMENT ON INDEX idx_teams_code_sport_pro IS
        'Enforces unique team codes per sport for pro leagues only. '
        'College sports (ncaaf, ncaab, ncaaw) allow code collisions.'
    """)

    # Step 2: Drop the redundant non-unique index.
    # This index duplicates the (now being dropped) unique constraint.
    op.execute("DROP INDEX IF EXISTS idx_teams_code_sport")

    # Step 3: Drop the full UNIQUE constraint.
    # This is the one-way-door change. College sport teams can now share codes.
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_team_code_sport_key")


def downgrade() -> None:
    """Restore the full UNIQUE(team_code, sport) constraint.

    WARNING: This will FAIL if any college sport teams with duplicate
    (team_code, sport) pairs have been inserted since the upgrade.
    You must manually deduplicate first:

        -- Find duplicates
        SELECT team_code, sport, COUNT(*)
        FROM teams GROUP BY team_code, sport HAVING COUNT(*) > 1;

        -- Keep lowest team_id, reassign FKs, delete others
    """
    # Restore the full unique constraint (fails if duplicates exist)
    op.execute("""
        ALTER TABLE teams
        ADD CONSTRAINT teams_team_code_sport_key UNIQUE (team_code, sport)
    """)

    # Recreate the non-unique index (redundant but was there before)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_teams_code_sport
        ON teams(team_code, sport)
    """)

    # Drop the partial index (no longer needed with full constraint)
    op.execute("DROP INDEX IF EXISTS idx_teams_code_sport_pro")
