"""
Add NCAAW (NCAA Women's Basketball) support.

Revision ID: 0004
Revises: 0003
Create Date: 2025-12-11

Updates CHECK constraints on teams and game_states tables to include 'ncaaw' as a valid
sport and league value. This enables seeding NCAAW teams for multi-sport support.

Related:
    - Issue #194: Add NCAAW team seeding
    - REQ-DATA-003: Multi-Sport Team Support
    - ADR-029: ESPN Data Model
"""

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0004"
down_revision: str = "0003"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """
    Add 'ncaaw' to sport and league CHECK constraints.

    Updates:
        - teams.sport CHECK constraint to include 'ncaaw'
        - teams.league CHECK constraint to include 'ncaaw'
        - game_states.league CHECK constraint to include 'ncaaw' (if exists)
    """
    # Drop and recreate teams sport CHECK constraint
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_sport_check;")
    op.execute(
        """
        ALTER TABLE teams ADD CONSTRAINT teams_sport_check
        CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'ncaaw', 'nhl', 'wnba', 'mlb', 'soccer'));
        """
    )

    # Drop and recreate teams league CHECK constraint
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_league_check;")
    op.execute(
        """
        ALTER TABLE teams ADD CONSTRAINT teams_league_check
        CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'ncaaw', 'nhl', 'wnba', 'mlb', 'soccer'));
        """
    )

    # Drop and recreate game_states league CHECK constraint (if exists)
    op.execute("ALTER TABLE game_states DROP CONSTRAINT IF EXISTS game_states_league_check;")
    op.execute(
        """
        ALTER TABLE game_states ADD CONSTRAINT game_states_league_check
        CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'ncaaw', 'nhl', 'wnba'));
        """
    )


def downgrade() -> None:
    """
    Remove 'ncaaw' from sport and league CHECK constraints.

    Reverts constraints to previous state (without ncaaw).
    Note: This will fail if any ncaaw data exists in the tables.
    """
    # Restore teams sport CHECK constraint without ncaaw
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_sport_check;")
    op.execute(
        """
        ALTER TABLE teams ADD CONSTRAINT teams_sport_check
        CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer'));
        """
    )

    # Restore teams league CHECK constraint without ncaaw
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_league_check;")
    op.execute(
        """
        ALTER TABLE teams ADD CONSTRAINT teams_league_check
        CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer'));
        """
    )

    # Restore game_states league CHECK constraint without ncaaw
    op.execute("ALTER TABLE game_states DROP CONSTRAINT IF EXISTS game_states_league_check;")
    op.execute(
        """
        ALTER TABLE game_states ADD CONSTRAINT game_states_league_check
        CHECK (league IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba'));
        """
    )
