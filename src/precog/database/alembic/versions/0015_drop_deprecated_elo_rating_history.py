"""
Drop deprecated elo_rating_history table.

Revision ID: 0015
Revises: 0014
Create Date: 2025-12-26

This migration removes the deprecated elo_rating_history table which has been
superseded by elo_calculation_log.

Background (from Issue #277):
    - elo_rating_history: Created in migration 0001, never used (0 rows)
    - elo_calculation_log: Created in migration 0013, actively used (9,240+ rows)

Comparison:
    | Aspect              | elo_rating_history | elo_calculation_log |
    |---------------------|-------------------|---------------------|
    | Structure           | Team-centric      | Game-centric        |
    | Columns             | 10                | 28                  |
    | Audit Detail        | Basic             | Complete            |
    | Source Tracking     | None              | FK to games         |
    | Version Tracking    | None              | calculation_version |

The elo_calculation_log table provides:
    - Full calculation inputs (K-factor, home advantage, MOV multiplier)
    - Expected vs actual scores for both teams
    - EPA adjustments (when available)
    - Links to source game (game_states or historical_games)
    - Calculation source and version tracking

Related:
    - Issue #277: Remove deprecated elo_rating_history table
    - ADR-109: Elo Rating Computation Engine Architecture
    - Migration 0013: Created elo_calculation_log
"""

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0015"
down_revision: str = "0014"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Drop deprecated elo_rating_history table and its indexes."""
    # Drop indexes first (if they exist)
    op.execute("DROP INDEX IF EXISTS idx_elo_team")
    op.execute("DROP INDEX IF EXISTS idx_elo_date")
    op.execute("DROP INDEX IF EXISTS idx_elo_history_team")
    op.execute("DROP INDEX IF EXISTS idx_elo_history_event")
    op.execute("DROP INDEX IF EXISTS idx_elo_history_created")
    op.execute("DROP INDEX IF EXISTS idx_elo_history_opponent")

    # Drop the deprecated table
    op.execute("DROP TABLE IF EXISTS elo_rating_history CASCADE")


def downgrade() -> None:
    """Recreate elo_rating_history table (for rollback only).

    Note: This recreates the table structure but NOT the data.
    The table was empty (0 rows) before removal.
    """
    op.execute("""
        CREATE TABLE IF NOT EXISTS elo_rating_history (
            id SERIAL PRIMARY KEY,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            event_id INTEGER,
            rating_before DECIMAL(10,4) NOT NULL,
            rating_after DECIMAL(10,4) NOT NULL,
            rating_change DECIMAL(10,4) GENERATED ALWAYS AS (rating_after - rating_before) STORED,
            opponent_team_id INTEGER REFERENCES teams(id),
            game_result VARCHAR(10) CHECK (game_result IN ('win', 'loss', 'tie')),
            k_factor INTEGER NOT NULL DEFAULT 20,
            rating_date DATE NOT NULL DEFAULT CURRENT_DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_elo_team ON elo_rating_history(team_id)")
    op.execute("CREATE INDEX idx_elo_date ON elo_rating_history(rating_date)")
