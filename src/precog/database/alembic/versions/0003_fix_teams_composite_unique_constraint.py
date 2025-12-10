"""Fix teams table composite unique constraint.

This migration changes the unique constraint on the teams table from
UNIQUE(team_code) to UNIQUE(team_code, sport) to support multi-sport
team seeding where different sports can have the same team code
(e.g., PHI = Philadelphia Eagles in NFL, 76ers in NBA).

GitHub Issue: #186 (Phase 2.5 ESPN Data Integration)

Key Changes:
- Drop the existing teams_team_code_key constraint (UNIQUE team_code)
- Add teams_team_code_sport_key constraint (UNIQUE team_code, sport)

Revision ID: 0003
Revises: 0002
Create Date: 2025-12-09

References:
- ADR-029: ESPN Data Model (Multi-Sport Support)
- REQ-DATA-003: Multi-Sport Team Support
- TESTING_ANTIPATTERNS_V1.0.md (Antipattern 2: API Edge Cases)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Change teams unique constraint from (team_code) to (team_code, sport).

    This allows the same team_code to exist for different sports:
    - PHI (nfl) = Philadelphia Eagles
    - PHI (nba) = Philadelphia 76ers
    - MIA (nfl) = Miami Dolphins
    - MIA (nba) = Miami Heat
    - etc.
    """

    # =========================================================================
    # 1. DROP EXISTING SINGLE-COLUMN CONSTRAINT (Idempotent)
    # =========================================================================

    # The constraint might be named differently depending on how it was created:
    # - teams_team_code_key (from CREATE TABLE ... UNIQUE)
    # - teams_team_code_idx (if created via CREATE UNIQUE INDEX)
    op.execute("""
        DO $$
        BEGIN
            -- Try to drop the constraint if it exists
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'teams_team_code_key'
                AND conrelid = 'teams'::regclass
            ) THEN
                ALTER TABLE teams DROP CONSTRAINT teams_team_code_key;
                RAISE NOTICE 'Dropped constraint teams_team_code_key';
            END IF;
        END $$
    """)

    # Also drop the index if it exists separately
    op.execute("DROP INDEX IF EXISTS idx_teams_code")

    # =========================================================================
    # 2. ADD COMPOSITE UNIQUE CONSTRAINT (Idempotent)
    # =========================================================================

    # Create the new composite constraint if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'teams_team_code_sport_key'
                AND conrelid = 'teams'::regclass
            ) THEN
                ALTER TABLE teams
                ADD CONSTRAINT teams_team_code_sport_key UNIQUE (team_code, sport);
                RAISE NOTICE 'Created constraint teams_team_code_sport_key (team_code, sport)';
            ELSE
                RAISE NOTICE 'Constraint teams_team_code_sport_key already exists';
            END IF;
        END $$
    """)

    # =========================================================================
    # 3. CREATE OPTIMIZED INDEX FOR TEAM LOOKUPS
    # =========================================================================

    # Create an index for common query patterns (team lookup by code)
    # This replaces the dropped idx_teams_code with a more useful composite index
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_teams_code_sport
        ON teams(team_code, sport)
    """)

    # Add comment explaining the constraint change
    op.execute("""
        COMMENT ON CONSTRAINT teams_team_code_sport_key ON teams IS
        'Composite unique constraint allowing same team_code across different sports (e.g., PHI for Eagles and 76ers)'
    """)


def downgrade() -> None:
    """Revert to single-column unique constraint on team_code.

    WARNING: This downgrade will fail if there are duplicate team_codes
    across different sports. You must remove duplicate team_codes first.
    """

    # Drop the composite constraint
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'teams_team_code_sport_key'
                AND conrelid = 'teams'::regclass
            ) THEN
                ALTER TABLE teams DROP CONSTRAINT teams_team_code_sport_key;
                RAISE NOTICE 'Dropped constraint teams_team_code_sport_key';
            END IF;
        END $$
    """)

    # Drop the composite index
    op.execute("DROP INDEX IF EXISTS idx_teams_code_sport")

    # Recreate the original single-column constraint
    # WARNING: This will fail if duplicate team_codes exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'teams_team_code_key'
                AND conrelid = 'teams'::regclass
            ) THEN
                ALTER TABLE teams ADD CONSTRAINT teams_team_code_key UNIQUE (team_code);
                RAISE NOTICE 'Recreated constraint teams_team_code_key (team_code only)';
            END IF;
        END $$
    """)

    # Recreate the original index
    op.execute("CREATE INDEX IF NOT EXISTS idx_teams_code ON teams(team_code)")
