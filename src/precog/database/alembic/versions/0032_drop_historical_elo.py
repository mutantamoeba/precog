"""Drop historical_elo table — superseded by unified Elo architecture.

The historical_elo table was created in migration 0005 for seeding Elo ratings
from external CSV data (FiveThirtyEight). It is superseded by the unified Elo
tables (elo_ratings, elo_snapshots) which handle both seeded and computed
ratings in a single architecture.

Code cleanup (archiving historical_elo_loader.py + 14 test files) is tracked
separately and will follow this migration.

Steps:
    1. DROP TABLE historical_elo

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0032 spec
- Issue #367: Elo table unification
- Migration 0005: Original historical_elo creation
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032"
down_revision: str = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the historical_elo table (superseded by unified Elo architecture)."""
    op.execute("DROP TABLE IF EXISTS historical_elo CASCADE")


def downgrade() -> None:
    """Recreate historical_elo table (original schema from migration 0005)."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS historical_elo (
            historical_elo_id SERIAL PRIMARY KEY,
            team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
            sport VARCHAR(20) NOT NULL,
            season INT NOT NULL,
            rating_date DATE NOT NULL,
            elo_rating DECIMAL(10,2) NOT NULL,
            qb_adjusted_elo DECIMAL(10,2),
            qb_name VARCHAR(100),
            qb_value DECIMAL(10,2),
            source VARCHAR(50) NOT NULL DEFAULT 'calculated',
            source_file VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (team_id, rating_date)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_team ON historical_elo(team_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_sport ON historical_elo(sport)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_season ON historical_elo(season)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_date ON historical_elo(rating_date)")
