"""
Create historical_elo table for historical Elo ratings seeding.

Revision ID: 0005
Revises: 0004
Create Date: 2025-12-14

Creates a table for storing historical Elo ratings from external sources
(FiveThirtyEight, Kaggle datasets, or calculated from historical games).

Purpose:
    - Store historical Elo ratings by team, date, and season
    - Support model training and backtesting with historical data
    - Track data source provenance (FiveThirtyEight, calculated, etc.)

Related:
    - Issue #208: Historical Data Seeding
    - ADR-029: ESPN Data Model
    - REQ-DATA-003: Multi-Sport Team Support

Schema Design Notes:
    - historical_elo stores point-in-time ratings (seedable from external sources)
    - elo_rating_history tracks changes from game events (append-only audit trail)
    - Both tables work together: historical_elo for backfill, elo_rating_history for live

Data Sources:
    - FiveThirtyEight NFL Elo (1920-present, includes QB-adjusted)
    - Calculated from historical game results (other sports)
    - Kaggle datasets as backup source

Educational Note:
    FiveThirtyEight Elo data includes:
    - elo1_pre, elo2_pre: Pre-game Elo ratings
    - elo1_post, elo2_post: Post-game Elo ratings
    - qbelo1_pre, qbelo2_pre: QB-adjusted ratings
    We store pre-game ratings with optional QB adjustments.
"""

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0005"
down_revision: str = "0004"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create historical_elo table with indexes and constraints."""
    # Create the historical_elo table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS historical_elo (
            historical_elo_id SERIAL PRIMARY KEY,
            team_id INT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
            sport VARCHAR(20) NOT NULL,
            season INT NOT NULL,
            rating_date DATE NOT NULL,

            -- Core Elo Rating
            elo_rating DECIMAL(10,2) NOT NULL,

            -- Optional QB-Adjusted Rating (NFL-specific)
            qb_adjusted_elo DECIMAL(10,2),
            qb_name VARCHAR(100),
            qb_value DECIMAL(10,2),

            -- Data Provenance
            source VARCHAR(50) NOT NULL DEFAULT 'calculated',
            source_file VARCHAR(255),

            -- Metadata
            created_at TIMESTAMP DEFAULT NOW(),

            -- Unique constraint: one rating per team per date
            UNIQUE (team_id, rating_date)
        )
        """
    )

    # Create indexes for query performance
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_team ON historical_elo (team_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_sport ON historical_elo (sport)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_season ON historical_elo (season)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_date ON historical_elo (rating_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_historical_elo_source ON historical_elo (source)")

    # Create composite index for common queries (team + season + date)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_historical_elo_team_season
        ON historical_elo (team_id, season, rating_date)
        """
    )

    # Add CHECK constraints for data validation
    # Note: PostgreSQL doesn't support ADD CONSTRAINT IF NOT EXISTS, so we use
    # DROP IF EXISTS first to make the migration idempotent
    op.execute("ALTER TABLE historical_elo DROP CONSTRAINT IF EXISTS historical_elo_sport_check")
    op.execute(
        """
        ALTER TABLE historical_elo ADD CONSTRAINT historical_elo_sport_check
        CHECK (sport IN ('nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer'))
        """
    )

    op.execute(
        "ALTER TABLE historical_elo DROP CONSTRAINT IF EXISTS historical_elo_elo_rating_check"
    )
    op.execute(
        """
        ALTER TABLE historical_elo ADD CONSTRAINT historical_elo_elo_rating_check
        CHECK (elo_rating BETWEEN 0 AND 3000)
        """
    )

    op.execute(
        "ALTER TABLE historical_elo DROP CONSTRAINT IF EXISTS historical_elo_qb_adjusted_elo_check"
    )
    op.execute(
        """
        ALTER TABLE historical_elo ADD CONSTRAINT historical_elo_qb_adjusted_elo_check
        CHECK (qb_adjusted_elo IS NULL OR qb_adjusted_elo BETWEEN 0 AND 3000)
        """
    )

    op.execute("ALTER TABLE historical_elo DROP CONSTRAINT IF EXISTS historical_elo_season_check")
    op.execute(
        """
        ALTER TABLE historical_elo ADD CONSTRAINT historical_elo_season_check
        CHECK (season BETWEEN 1900 AND 2100)
        """
    )

    op.execute("ALTER TABLE historical_elo DROP CONSTRAINT IF EXISTS historical_elo_source_check")
    op.execute(
        """
        ALTER TABLE historical_elo ADD CONSTRAINT historical_elo_source_check
        CHECK (source IN ('fivethirtyeight', 'calculated', 'kaggle', 'espn', 'manual', 'imported'))
        """
    )

    # Add table and column comments for documentation
    op.execute(
        """
        COMMENT ON TABLE historical_elo IS
        'Historical Elo ratings seeded from external sources (FiveThirtyEight, Kaggle, calculated)'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN historical_elo.elo_rating IS
        'Pre-game Elo rating at this date (from external source or calculated)'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN historical_elo.qb_adjusted_elo IS
        'QB-adjusted Elo rating (NFL only, from FiveThirtyEight qbelo field)'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN historical_elo.source IS
        'Data source: fivethirtyeight, calculated, kaggle, espn, manual, imported'
        """
    )


def downgrade() -> None:
    """Drop historical_elo table and all dependent objects."""
    op.execute("DROP TABLE IF EXISTS historical_elo CASCADE")
