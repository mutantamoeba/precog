"""Rename teams.sport and games.sport column VALUES from league codes to sport names.

Phase B of issue #460: The sport column should store the sport name ("football"),
not the league name ("nfl"). This aligns semantics: sport stores sport, league
stores league.

Value mapping:
    nfl    -> football
    ncaaf  -> football
    nba    -> basketball
    ncaab  -> basketball
    wnba   -> basketball
    ncaaw  -> basketball
    nhl    -> hockey
    mlb    -> baseball
    soccer -> soccer  (already correct)
    mls    -> soccer  (games table only)

Steps:
    0. UPDATE existing data — convert league codes to sport names
    1. DROP + RECREATE CHECK constraint on teams.sport with sport names
    2. DROP + RECREATE CHECK constraint on games.sport with sport names
    3. DROP + RECREATE partial unique index — now filters by league column
       (sport can no longer distinguish pro from college: both are 'football')

Revision ID: 0039
Revises: 0038
Create Date: 2026-03-23

Related:
    - Issue #460: Category/subcategory naming (Phase B)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039"
down_revision: str = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# League code -> sport name mapping for UPDATE statements
_SPORT_UPDATES = [
    ("'football'", "'nfl', 'ncaaf'"),
    ("'basketball'", "'nba', 'ncaab', 'wnba', 'ncaaw'"),
    ("'hockey'", "'nhl'"),
    ("'baseball'", "'mlb'"),
    ("'soccer'", "'mls'"),
]


def upgrade() -> None:
    """Rename sport column CHECK constraints to accept sport names."""
    # =========================================================================
    # Step 1: Drop old CHECK constraints (must happen BEFORE data update)
    # =========================================================================
    # Old constraints only allow league codes ('nfl', 'nba', etc.).
    # Must drop them before updating data to sport names ('football', etc.).
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_sport_check;")
    op.execute("ALTER TABLE games DROP CONSTRAINT IF EXISTS ck_games_sport;")

    # =========================================================================
    # Step 2: Update existing data — convert league codes to sport names
    # =========================================================================
    for target, sources in _SPORT_UPDATES:
        op.execute(f"UPDATE teams SET sport = {target} WHERE sport IN ({sources})")  # noqa: S608
        op.execute(f"UPDATE games SET sport = {target} WHERE sport IN ({sources})")  # noqa: S608

    # =========================================================================
    # Step 3: Add new CHECK constraints with sport names
    # =========================================================================
    op.execute("""
        ALTER TABLE teams ADD CONSTRAINT teams_sport_check
        CHECK (sport IN ('football', 'basketball', 'hockey', 'baseball', 'soccer'))
    """)
    op.execute("""
        ALTER TABLE games ADD CONSTRAINT ck_games_sport
        CHECK (sport IN ('football', 'basketball', 'hockey', 'baseball', 'soccer'))
    """)

    # =========================================================================
    # Step 3: Partial unique index — switch from sport to league column
    # =========================================================================
    # From migration 0018: idx_teams_code_sport_pro enforced unique team codes
    # for pro leagues only by filtering on sport IN ('nfl', 'nba', ...).
    # Now that sport='football' covers both NFL (pro) and NCAAF (college),
    # the index must filter by league instead to maintain the pro/college
    # distinction. Renamed to idx_teams_code_league_pro to reflect this.
    op.execute("DROP INDEX IF EXISTS idx_teams_code_sport_pro;")
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_code_league_pro
        ON teams(team_code, league)
        WHERE league IN ('nfl', 'nba', 'nhl', 'wnba', 'mlb', 'mls')
    """)
    op.execute("""
        COMMENT ON INDEX idx_teams_code_league_pro IS
        'Enforces unique team codes per league for pro leagues only. '
        'College leagues (ncaaf, ncaab, ncaaw) allow code collisions.'
    """)


def downgrade() -> None:
    """Restore original CHECK constraints with league codes."""
    # =========================================================================
    # Step 0: Revert data — convert sport names back to league codes
    # =========================================================================
    # Use the league column to determine the correct league code to restore.
    op.execute(
        "UPDATE teams SET sport = league"
        " WHERE sport IN ('football', 'basketball', 'hockey', 'baseball', 'soccer')"
    )
    op.execute(
        "UPDATE games SET sport = league"
        " WHERE sport IN ('football', 'basketball', 'hockey', 'baseball', 'soccer')"
    )

    # =========================================================================
    # Step 1: teams.sport — restore league-code constraint
    # =========================================================================
    op.execute("ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_sport_check;")
    op.execute("""
        ALTER TABLE teams ADD CONSTRAINT teams_sport_check
        CHECK (sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'wnba', 'mlb', 'soccer'))
    """)

    # =========================================================================
    # Step 2: games.sport — restore league-code constraint
    # =========================================================================
    op.execute("ALTER TABLE games DROP CONSTRAINT IF EXISTS ck_games_sport;")
    op.execute("""
        ALTER TABLE games ADD CONSTRAINT ck_games_sport
        CHECK (sport IN (
            'nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer'
        ))
    """)

    # =========================================================================
    # Step 3: Partial unique index — restore original sport-based filter
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_teams_code_league_pro;")
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_code_sport_pro
        ON teams(team_code, sport)
        WHERE sport IN ('nfl', 'nba', 'nhl', 'wnba', 'mlb', 'soccer')
    """)
