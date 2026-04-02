"""
Rename historical_odds to game_odds and add SCD Type 2 support.

Revision ID: 0048
Revises: 0047
Create Date: 2026-04-01

Renames the historical_odds table to game_odds to reflect its expanded role:
now stores both historical CSV-imported odds AND live ESPN poller odds.

Changes:
    1. Rename table historical_odds -> game_odds
    2. Rename PK column historical_odds_id -> id
    3. Add SCD Type 2 columns (row_current_ind, row_start_ts, row_end_ts)
    4. Add updated_at for freshness tracking
    5. Add away spread columns (spread_away_odds_open, spread_away_odds_close)
    6. Add under odds columns (under_odds_open, under_odds_close)
    7. Add favorite flags (home_favorite, away_favorite, *_at_open)
    8. Add details_text for ESPN summary text
    9. Update CHECK constraints (rename + add espn_poller source)
    10. Rename indexes
    11. Add SCD and game_id partial indexes

Related:
    - Issue #533: ESPN DraftKings odds extraction
    - Migration 0007: Original historical_odds table
    - Migration 0035: Added game_id FK column
    - ADR-106: Historical Data Collection Architecture
"""

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0048"
down_revision: str = "0047"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Rename historical_odds to game_odds with SCD Type 2 support."""
    # =========================================================================
    # Step 1: Rename table
    # =========================================================================
    op.execute("ALTER TABLE historical_odds RENAME TO game_odds")

    # =========================================================================
    # Step 2: Rename PK column
    # =========================================================================
    op.execute("ALTER TABLE game_odds RENAME COLUMN historical_odds_id TO id")

    # =========================================================================
    # Step 3: Add SCD Type 2 columns
    # =========================================================================
    op.execute("""
        ALTER TABLE game_odds
        ADD COLUMN row_current_ind BOOLEAN DEFAULT TRUE,
        ADD COLUMN row_start_ts TIMESTAMPTZ DEFAULT NOW(),
        ADD COLUMN row_end_ts TIMESTAMPTZ
    """)

    # =========================================================================
    # Step 4: Add updated_at (freshness tracking per Fathom's concern)
    # =========================================================================
    op.execute("""
        ALTER TABLE game_odds
        ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW()
    """)

    # =========================================================================
    # Step 5: Add away spread columns (historical_odds only had home spread)
    # =========================================================================
    op.execute("""
        ALTER TABLE game_odds
        ADD COLUMN spread_away_odds_open INTEGER,
        ADD COLUMN spread_away_odds_close INTEGER
    """)

    # =========================================================================
    # Step 6: Add under odds (historical_odds only had over odds)
    # =========================================================================
    op.execute("""
        ALTER TABLE game_odds
        ADD COLUMN under_odds_open INTEGER,
        ADD COLUMN under_odds_close INTEGER
    """)

    # =========================================================================
    # Step 7: Add favorite flags
    # =========================================================================
    op.execute("""
        ALTER TABLE game_odds
        ADD COLUMN home_favorite BOOLEAN,
        ADD COLUMN away_favorite BOOLEAN,
        ADD COLUMN home_favorite_at_open BOOLEAN,
        ADD COLUMN away_favorite_at_open BOOLEAN
    """)

    # =========================================================================
    # Step 8: Add details text (ESPN summary like "BOS -3.5")
    # =========================================================================
    op.execute("""
        ALTER TABLE game_odds
        ADD COLUMN details_text VARCHAR(100)
    """)

    # =========================================================================
    # Step 9: Update source CHECK constraint to include 'espn_poller'
    # =========================================================================
    op.execute("ALTER TABLE game_odds DROP CONSTRAINT IF EXISTS historical_odds_source_check")
    op.execute("""
        ALTER TABLE game_odds ADD CONSTRAINT game_odds_source_check CHECK (
            source IN (
                'kaggle', 'odds_portal', 'action_network', 'pinnacle',
                'manual', 'imported', 'betting_csv', 'fivethirtyeight',
                'consensus', 'espn_poller'
            )
        )
    """)

    # =========================================================================
    # Step 10: Convert old unique constraint for SCD compatibility
    # The old constraint enforced UNIQUE(sport, game_date, home_team_code,
    # away_team_code, sportsbook) across ALL rows. SCD Type 2 creates multiple
    # rows per game, so we convert to a partial unique index that only applies
    # to current rows. Seeding path ON CONFLICT still works because seeded
    # rows all have row_current_ind = TRUE.
    # =========================================================================
    op.execute("ALTER TABLE game_odds DROP CONSTRAINT IF EXISTS uq_historical_odds_game_book")
    op.execute("""
        CREATE UNIQUE INDEX uq_game_odds_game_book
        ON game_odds(sport, game_date, home_team_code, away_team_code, sportsbook)
        WHERE row_current_ind = TRUE
    """)
    # Update sport CHECK constraint to accept both league codes (CSV imports)
    # and sport categories (ESPN poller, matching games.sport post-migration 0039)
    op.execute("ALTER TABLE game_odds DROP CONSTRAINT IF EXISTS historical_odds_sport_check")
    op.execute("""
        ALTER TABLE game_odds ADD CONSTRAINT game_odds_sport_check CHECK (
            sport IN (
                'nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer',
                'football', 'basketball', 'baseball', 'hockey'
            )
        )
    """)
    op.execute("""
        ALTER TABLE game_odds
        RENAME CONSTRAINT historical_odds_spread_check
        TO game_odds_spread_check
    """)
    op.execute("""
        ALTER TABLE game_odds
        RENAME CONSTRAINT historical_odds_total_check
        TO game_odds_total_check
    """)

    # =========================================================================
    # Step 11: Rename indexes
    # Note: idx_historical_odds_game was dropped by migration 0035 and replaced
    # with idx_historical_odds_game_id. We rename the game_id index.
    # =========================================================================
    op.execute("ALTER INDEX IF EXISTS idx_historical_odds_sport RENAME TO idx_game_odds_sport")
    op.execute("ALTER INDEX IF EXISTS idx_historical_odds_date RENAME TO idx_game_odds_date")
    op.execute("ALTER INDEX IF EXISTS idx_historical_odds_source RENAME TO idx_game_odds_source")
    op.execute(
        "ALTER INDEX IF EXISTS idx_historical_odds_sportsbook RENAME TO idx_game_odds_sportsbook"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_historical_odds_game_lookup RENAME TO idx_game_odds_game_lookup"
    )
    op.execute("ALTER INDEX IF EXISTS idx_historical_odds_game_id RENAME TO idx_game_odds_game_id")

    # =========================================================================
    # Step 12: Add new indexes for SCD Type 2 and ESPN poller lookups
    # =========================================================================
    op.execute("""
        CREATE INDEX idx_game_odds_current
        ON game_odds(row_current_ind) WHERE row_current_ind = TRUE
    """)

    # Partial unique index for ESPN poller SCD pattern:
    # Only one current row per game+sportsbook combination
    op.execute("""
        CREATE UNIQUE INDEX uq_game_odds_game_sportsbook_current
        ON game_odds(game_id, sportsbook)
        WHERE game_id IS NOT NULL AND row_current_ind = TRUE
    """)


def downgrade() -> None:
    """Revert game_odds back to historical_odds."""
    # Drop new indexes
    op.execute("DROP INDEX IF EXISTS uq_game_odds_game_sportsbook_current")
    op.execute("DROP INDEX IF EXISTS idx_game_odds_current")

    # Rename indexes back
    op.execute("ALTER INDEX IF EXISTS idx_game_odds_game_id RENAME TO idx_historical_odds_game_id")
    op.execute(
        "ALTER INDEX IF EXISTS idx_game_odds_game_lookup RENAME TO idx_historical_odds_game_lookup"
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_game_odds_sportsbook RENAME TO idx_historical_odds_sportsbook"
    )
    op.execute("ALTER INDEX IF EXISTS idx_game_odds_source RENAME TO idx_historical_odds_source")
    op.execute("ALTER INDEX IF EXISTS idx_game_odds_date RENAME TO idx_historical_odds_date")
    op.execute("ALTER INDEX IF EXISTS idx_game_odds_sport RENAME TO idx_historical_odds_sport")

    # Rename constraints back
    op.execute("""
        ALTER TABLE game_odds
        RENAME CONSTRAINT game_odds_total_check
        TO historical_odds_total_check
    """)
    op.execute("""
        ALTER TABLE game_odds
        RENAME CONSTRAINT game_odds_spread_check
        TO historical_odds_spread_check
    """)
    # Sport CHECK was dropped+recreated (not renamed) in upgrade, so reverse the same way
    op.execute("ALTER TABLE game_odds DROP CONSTRAINT IF EXISTS game_odds_sport_check")
    op.execute("""
        ALTER TABLE game_odds ADD CONSTRAINT historical_odds_sport_check CHECK (
            sport IN ('nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer')
        )
    """)
    # uq_game_odds_game_book is a partial INDEX (not constraint), so drop + recreate
    op.execute("DROP INDEX IF EXISTS uq_game_odds_game_book")
    op.execute("""
        ALTER TABLE game_odds ADD CONSTRAINT uq_historical_odds_game_book
        UNIQUE (sport, game_date, home_team_code, away_team_code, sportsbook)
    """)

    # Revert source constraint
    op.execute("ALTER TABLE game_odds DROP CONSTRAINT IF EXISTS game_odds_source_check")
    op.execute("""
        ALTER TABLE game_odds ADD CONSTRAINT historical_odds_source_check CHECK (
            source IN (
                'kaggle', 'odds_portal', 'action_network', 'pinnacle',
                'manual', 'imported', 'betting_csv', 'fivethirtyeight',
                'consensus'
            )
        )
    """)

    # Drop new columns
    op.execute("""
        ALTER TABLE game_odds
        DROP COLUMN IF EXISTS details_text,
        DROP COLUMN IF EXISTS away_favorite_at_open,
        DROP COLUMN IF EXISTS home_favorite_at_open,
        DROP COLUMN IF EXISTS away_favorite,
        DROP COLUMN IF EXISTS home_favorite,
        DROP COLUMN IF EXISTS under_odds_close,
        DROP COLUMN IF EXISTS under_odds_open,
        DROP COLUMN IF EXISTS spread_away_odds_close,
        DROP COLUMN IF EXISTS spread_away_odds_open,
        DROP COLUMN IF EXISTS updated_at,
        DROP COLUMN IF EXISTS row_end_ts,
        DROP COLUMN IF EXISTS row_start_ts,
        DROP COLUMN IF EXISTS row_current_ind
    """)

    # Rename PK column back
    op.execute("ALTER TABLE game_odds RENAME COLUMN id TO historical_odds_id")

    # Rename table back
    op.execute("ALTER TABLE game_odds RENAME TO historical_odds")
