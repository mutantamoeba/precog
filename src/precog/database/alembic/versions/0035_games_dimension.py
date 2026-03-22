"""Create games dimension table — canonical game identity across all data sources.

Unifies game identity fragmentation where 6 tables describe the same games
with no shared key (Issue #439). The games table becomes the single source
of truth for "a game happened between team A and team B on date X".

Steps:
    1. CREATE TABLE games with natural key (sport, game_date, home_team_code, away_team_code)
    2. ALTER game_states — add game_id FK
    3. ALTER elo_calculation_log — add game_id FK, drop historical_game_id FK
    4. ALTER temporal_alignment — add game_id FK
    5. ALTER historical_odds — migrate historical_game_id FK to game_id FK
    6. DROP TABLE historical_games (absorbed into games)
    7. DROP + RECREATE team_season_records and current_season_standings views

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-21

Related:
    - Issue #439: Games dimension table
    - migration_batch_plan_v1.md: Migration 0035 spec
    - s25_council_findings.md: 6-agent council approval
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0035"
down_revision: str = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create games dimension table and migrate dependent objects."""
    # =========================================================================
    # Step 1: CREATE TABLE games
    # =========================================================================
    op.execute("""
        CREATE TABLE games (
            id SERIAL PRIMARY KEY,

            -- Natural key: one game per sport/date/matchup
            sport VARCHAR(20) NOT NULL,
            game_date DATE NOT NULL,
            home_team_code VARCHAR(10) NOT NULL,
            away_team_code VARCHAR(10) NOT NULL,

            -- Season context
            season INTEGER NOT NULL,
            season_type VARCHAR(20),
            week_number INTEGER,
            league VARCHAR(20) NOT NULL,

            -- Team FKs (nullable for historical data before team seeding)
            home_team_id INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,
            away_team_id INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,

            -- Venue
            venue_id INTEGER REFERENCES venues(venue_id) ON DELETE SET NULL,
            venue_name VARCHAR(100),

            -- Game context
            neutral_site BOOLEAN DEFAULT FALSE NOT NULL,
            is_playoff BOOLEAN DEFAULT FALSE NOT NULL,
            game_type VARCHAR(30),

            -- Precise game time (ESPN has timestamp; historical has date only)
            game_time TIMESTAMP WITH TIME ZONE,

            -- Final result (populated on game completion)
            home_score INTEGER,
            away_score INTEGER,
            actual_margin INTEGER,
            result VARCHAR(10),
            game_status VARCHAR(50) NOT NULL DEFAULT 'scheduled',

            -- Cross-source linking
            espn_event_id VARCHAR(50),
            external_game_id VARCHAR(100),

            -- Elo snapshots (nullable, backfilled by EloComputationService)
            -- DECIMAL(10,2) intentional: Elo ratings are integer-scale (e.g., 1500.00)
            home_pre_elo DECIMAL(10,2),
            away_pre_elo DECIMAL(10,2),

            -- Absorbed from historical_games
            attendance INTEGER,
            source_file VARCHAR(255),

            -- Feature extension (Phase 5 ML)
            features JSONB,

            -- Provenance
            data_source VARCHAR(50) NOT NULL DEFAULT 'espn',

            -- Audit
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            -- Constraints
            CONSTRAINT uq_games_matchup UNIQUE (sport, game_date, home_team_code, away_team_code),
            CONSTRAINT ck_games_sport CHECK (sport IN (
                'nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer'
            )),
            CONSTRAINT ck_games_season CHECK (season BETWEEN 1900 AND 2100),
            CONSTRAINT ck_games_status CHECK (game_status IN (
                'scheduled', 'pre', 'in_progress', 'halftime', 'end_of_period',
                'final', 'final_ot', 'delayed', 'postponed', 'cancelled', 'suspended'
            )),
            CONSTRAINT ck_games_season_type CHECK (season_type IS NULL OR season_type IN (
                'preseason', 'regular', 'playoff', 'bowl', 'allstar', 'exhibition'
            )),
            CONSTRAINT ck_games_game_type CHECK (game_type IS NULL OR game_type IN (
                'regular', 'playoff', 'wildcard', 'divisional', 'conference',
                'championship', 'superbowl', 'bowl', 'preseason', 'allstar'
            )),
            CONSTRAINT ck_games_week CHECK (week_number IS NULL OR (week_number >= 0 AND week_number <= 25)),
            CONSTRAINT ck_games_scores CHECK (
                (home_score IS NULL AND away_score IS NULL) OR (home_score >= 0 AND away_score >= 0)
            ),
            CONSTRAINT ck_games_result CHECK (result IS NULL OR result IN ('home_win', 'away_win', 'draw')),
            CONSTRAINT ck_games_source CHECK (data_source IN (
                'espn', 'espn_poller', 'historical_import', 'imported', 'kaggle',
                'sports_reference', 'fivethirtyeight', 'pybaseball', 'manual', 'reconciled'
            ))
        )
    """)

    # =========================================================================
    # Step 1b: CREATE INDEXES for games
    # =========================================================================
    op.execute("""
        CREATE UNIQUE INDEX idx_games_espn_event
        ON games(espn_event_id) WHERE espn_event_id IS NOT NULL
    """)
    op.execute("CREATE INDEX idx_games_sport_season ON games(sport, season, game_date)")
    op.execute("CREATE INDEX idx_games_date ON games(game_date)")
    op.execute("CREATE INDEX idx_games_home_team ON games(home_team_code)")
    op.execute("CREATE INDEX idx_games_away_team ON games(away_team_code)")
    op.execute("CREATE INDEX idx_games_league ON games(league)")
    op.execute("""
        CREATE INDEX idx_games_status ON games(game_status)
        WHERE game_status NOT IN ('final', 'final_ot', 'cancelled')
    """)
    op.execute("CREATE INDEX idx_games_teams ON games(home_team_id, away_team_id)")
    op.execute("""
        CREATE INDEX idx_games_features ON games USING GIN (features)
        WHERE features IS NOT NULL
    """)

    # Add table comment
    op.execute("""
        COMMENT ON TABLE games IS
        'Canonical game dimension table. One row per game across all sports and
         data sources. Natural key: (sport, game_date, home_team_code, away_team_code).
         Replaces historical_games table. Source: Issue #439, 6-agent council.'
    """)

    # =========================================================================
    # Step 2: ALTER game_states — add game_id FK
    # =========================================================================
    op.execute("""
        ALTER TABLE game_states
        ADD COLUMN game_id INTEGER REFERENCES games(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX idx_game_states_game_id ON game_states(game_id)
        WHERE game_id IS NOT NULL
    """)

    # =========================================================================
    # Step 3: ALTER elo_calculation_log — add game_id, drop historical_game_id
    # =========================================================================
    # Add new game_id column
    op.execute("""
        ALTER TABLE elo_calculation_log
        ADD COLUMN game_id INTEGER REFERENCES games(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX idx_elo_log_game_id ON elo_calculation_log(game_id)
        WHERE game_id IS NOT NULL
    """)

    # Drop old historical_game_id FK and column (clean DB, 0 rows)
    op.execute("DROP INDEX IF EXISTS idx_elo_log_historical_game")
    op.execute("""
        ALTER TABLE elo_calculation_log
        DROP COLUMN IF EXISTS historical_game_id
    """)

    # =========================================================================
    # Step 4: ALTER temporal_alignment — add game_id FK
    # =========================================================================
    op.execute("""
        ALTER TABLE temporal_alignment
        ADD COLUMN game_id INTEGER REFERENCES games(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX idx_alignment_game_id ON temporal_alignment(game_id)
        WHERE game_id IS NOT NULL
    """)

    # =========================================================================
    # Step 5: ALTER historical_odds — migrate FK from historical_game_id to game_id
    # =========================================================================
    # Drop old FK column and index (clean DB, 0 rows)
    op.execute("DROP INDEX IF EXISTS idx_historical_odds_game")
    op.execute("""
        ALTER TABLE historical_odds
        DROP COLUMN IF EXISTS historical_game_id
    """)

    # Add new game_id FK column
    op.execute("""
        ALTER TABLE historical_odds
        ADD COLUMN game_id INTEGER REFERENCES games(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX idx_historical_odds_game_id ON historical_odds(game_id)
        WHERE game_id IS NOT NULL
    """)

    # =========================================================================
    # Step 6: DROP TABLE historical_games (absorbed into games)
    # =========================================================================
    # Must drop dependent views first (they reference historical_games)
    op.execute("DROP VIEW IF EXISTS current_season_standings CASCADE")
    op.execute("DROP VIEW IF EXISTS team_season_records CASCADE")

    # Now drop the table (clean DB, 0 rows — no data migration needed)
    op.execute("DROP TABLE IF EXISTS historical_games CASCADE")

    # =========================================================================
    # Step 7: RECREATE views to query games table instead of historical_games
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW team_season_records AS
        WITH all_games AS (
            -- Single source: games table (replaces historical_games + game_states UNION)
            SELECT
                sport,
                season,
                game_date,
                home_team_code,
                away_team_code,
                home_score,
                away_score,
                data_source
            FROM games
            WHERE home_score IS NOT NULL AND away_score IS NOT NULL
              AND game_status IN ('final', 'final_ot')
        ),
        team_games AS (
            -- Home team perspective
            SELECT
                sport,
                season,
                home_team_code AS team_code,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS wins,
                CASE WHEN home_score < away_score THEN 1 ELSE 0 END AS losses,
                CASE WHEN home_score = away_score THEN 1 ELSE 0 END AS draws,
                1 AS home_games,
                0 AS away_games,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS home_wins,
                0 AS away_wins,
                COALESCE(home_score, 0) AS points_for,
                COALESCE(away_score, 0) AS points_against
            FROM all_games

            UNION ALL

            -- Away team perspective
            SELECT
                sport,
                season,
                away_team_code AS team_code,
                CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS wins,
                CASE WHEN away_score < home_score THEN 1 ELSE 0 END AS losses,
                CASE WHEN away_score = home_score THEN 1 ELSE 0 END AS draws,
                0 AS home_games,
                1 AS away_games,
                0 AS home_wins,
                CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS away_wins,
                COALESCE(away_score, 0) AS points_for,
                COALESCE(home_score, 0) AS points_against
            FROM all_games
        )
        SELECT
            sport,
            season,
            team_code,
            SUM(wins + losses + draws)::INTEGER AS games_played,
            SUM(wins)::INTEGER AS wins,
            SUM(losses)::INTEGER AS losses,
            SUM(draws)::INTEGER AS draws,
            SUM(home_games)::INTEGER AS home_games,
            SUM(away_games)::INTEGER AS away_games,
            SUM(home_wins)::INTEGER AS home_wins,
            SUM(away_wins)::INTEGER AS away_wins,
            CASE
                WHEN SUM(wins + losses + draws) > 0
                THEN ROUND(SUM(wins)::NUMERIC / SUM(wins + losses + draws), 3)
                ELSE 0.000
            END AS win_pct,
            SUM(points_for)::INTEGER AS points_for,
            SUM(points_against)::INTEGER AS points_against,
            (SUM(points_for) - SUM(points_against))::INTEGER AS point_differential,
            CONCAT(
                SUM(wins)::TEXT, '-',
                SUM(losses)::TEXT,
                CASE WHEN SUM(draws) > 0 THEN '-' || SUM(draws)::TEXT ELSE '' END
            ) AS record_display
        FROM team_games
        GROUP BY sport, season, team_code
        ORDER BY sport, season DESC, win_pct DESC, wins DESC
    """)

    op.execute("""
        COMMENT ON VIEW team_season_records IS
        'Derived view showing team season records (W-L-D) from the games table.
         Only includes games with status final/final_ot.

         Query examples:
         - Current season: WHERE season = 2026 AND sport = ''nfl''
         - Historical: WHERE team_code = ''KC'' ORDER BY season DESC
         - Standings: WHERE sport = ''nfl'' AND season = 2025 ORDER BY win_pct DESC'
    """)

    op.execute("""
        CREATE OR REPLACE VIEW current_season_standings AS
        SELECT
            tsr.*,
            t.team_name,
            t.display_name,
            t.conference,
            t.division,
            t.current_elo_rating
        FROM team_season_records tsr
        LEFT JOIN teams t ON t.team_code = tsr.team_code AND t.sport = tsr.sport
        WHERE tsr.season = EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER
        ORDER BY tsr.sport, tsr.win_pct DESC, tsr.wins DESC
    """)

    op.execute("""
        COMMENT ON VIEW current_season_standings IS
        'Convenience view joining team_season_records with teams table for
         current year standings. Includes team names, divisions, and Elo ratings.
         Auto-filters to current calendar year.'
    """)


def downgrade() -> None:
    """Reverse: restore historical_games table, revert FK changes, restore old views."""
    # =========================================================================
    # Step 1: Drop new views
    # =========================================================================
    op.execute("DROP VIEW IF EXISTS current_season_standings CASCADE")
    op.execute("DROP VIEW IF EXISTS team_season_records CASCADE")

    # =========================================================================
    # Step 2: Recreate historical_games table (from migration 0006)
    # =========================================================================
    op.execute("""
        CREATE TABLE historical_games (
            historical_game_id SERIAL PRIMARY KEY,
            sport VARCHAR(20) NOT NULL,
            season INTEGER NOT NULL,
            game_date DATE NOT NULL,
            home_team_code VARCHAR(10) NOT NULL,
            away_team_code VARCHAR(10) NOT NULL,
            home_team_id INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,
            away_team_id INTEGER REFERENCES teams(team_id) ON DELETE SET NULL,
            home_score INTEGER,
            away_score INTEGER,
            is_neutral_site BOOLEAN DEFAULT FALSE,
            is_playoff BOOLEAN DEFAULT FALSE,
            game_type VARCHAR(30),
            venue_name VARCHAR(100),
            attendance INTEGER,
            source VARCHAR(50) NOT NULL DEFAULT 'imported',
            source_file VARCHAR(255),
            external_game_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_historical_games_matchup
                UNIQUE (sport, game_date, home_team_code, away_team_code),
            CONSTRAINT historical_games_sport_check
                CHECK (sport IN ('nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer')),
            CONSTRAINT historical_games_season_check
                CHECK (season BETWEEN 1900 AND 2100),
            CONSTRAINT historical_games_score_check
                CHECK ((home_score IS NULL AND away_score IS NULL) OR (home_score >= 0 AND away_score >= 0)),
            CONSTRAINT historical_games_source_check
                CHECK (source IN ('espn', 'kaggle', 'sports_reference', 'fivethirtyeight', 'manual', 'imported')),
            CONSTRAINT historical_games_game_type_check
                CHECK (game_type IS NULL OR game_type IN (
                    'regular', 'playoff', 'wildcard', 'divisional', 'conference',
                    'championship', 'superbowl', 'bowl', 'preseason', 'allstar'))
        )
    """)

    # =========================================================================
    # Step 3: Revert historical_odds — drop game_id, add historical_game_id
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_historical_odds_game_id")
    op.execute("ALTER TABLE historical_odds DROP COLUMN IF EXISTS game_id")
    op.execute("""
        ALTER TABLE historical_odds
        ADD COLUMN historical_game_id INTEGER
            REFERENCES historical_games(historical_game_id) ON DELETE CASCADE
    """)
    op.execute("CREATE INDEX idx_historical_odds_game ON historical_odds(historical_game_id)")

    # =========================================================================
    # Step 4: Revert temporal_alignment — drop game_id
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_alignment_game_id")
    op.execute("ALTER TABLE temporal_alignment DROP COLUMN IF EXISTS game_id")

    # =========================================================================
    # Step 5: Revert elo_calculation_log — drop game_id, add historical_game_id
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_elo_log_game_id")
    op.execute("ALTER TABLE elo_calculation_log DROP COLUMN IF EXISTS game_id")
    op.execute("""
        ALTER TABLE elo_calculation_log
        ADD COLUMN historical_game_id INTEGER
            REFERENCES historical_games(historical_game_id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX idx_elo_log_historical_game ON elo_calculation_log(historical_game_id)
        WHERE historical_game_id IS NOT NULL
    """)

    # =========================================================================
    # Step 6: Revert game_states — drop game_id
    # =========================================================================
    op.execute("DROP INDEX IF EXISTS idx_game_states_game_id")
    op.execute("ALTER TABLE game_states DROP COLUMN IF EXISTS game_id")

    # =========================================================================
    # Step 7: Recreate old views (from migration 0014)
    # =========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW team_season_records AS
        WITH all_games AS (
            SELECT
                sport, season, game_date, home_team_code, away_team_code,
                home_score, away_score, 'historical_games' AS data_source
            FROM historical_games
            WHERE home_score IS NOT NULL AND away_score IS NOT NULL

            UNION ALL

            SELECT
                ht.sport,
                EXTRACT(YEAR FROM gs.game_date)::INTEGER AS season,
                gs.game_date,
                ht.team_code AS home_team_code,
                at.team_code AS away_team_code,
                gs.home_score, gs.away_score,
                'game_states' AS data_source
            FROM game_states gs
            JOIN teams ht ON gs.home_team_id = ht.team_id
            JOIN teams at ON gs.away_team_id = at.team_id
            WHERE gs.game_status = 'final'
              AND gs.row_current_ind = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM historical_games hg
                  WHERE hg.sport = ht.sport
                    AND hg.game_date = gs.game_date
                    AND hg.home_team_code = ht.team_code
                    AND hg.away_team_code = at.team_code
              )
        ),
        team_games AS (
            SELECT sport, season, home_team_code AS team_code,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS wins,
                CASE WHEN home_score < away_score THEN 1 ELSE 0 END AS losses,
                CASE WHEN home_score = away_score THEN 1 ELSE 0 END AS draws,
                1 AS home_games, 0 AS away_games,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS home_wins,
                0 AS away_wins,
                COALESCE(home_score, 0) AS points_for,
                COALESCE(away_score, 0) AS points_against
            FROM all_games
            UNION ALL
            SELECT sport, season, away_team_code AS team_code,
                CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS wins,
                CASE WHEN away_score < home_score THEN 1 ELSE 0 END AS losses,
                CASE WHEN away_score = home_score THEN 1 ELSE 0 END AS draws,
                0 AS home_games, 1 AS away_games, 0 AS home_wins,
                CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS away_wins,
                COALESCE(away_score, 0) AS points_for,
                COALESCE(home_score, 0) AS points_against
            FROM all_games
        )
        SELECT sport, season, team_code,
            SUM(wins + losses + draws)::INTEGER AS games_played,
            SUM(wins)::INTEGER AS wins,
            SUM(losses)::INTEGER AS losses,
            SUM(draws)::INTEGER AS draws,
            SUM(home_games)::INTEGER AS home_games,
            SUM(away_games)::INTEGER AS away_games,
            SUM(home_wins)::INTEGER AS home_wins,
            SUM(away_wins)::INTEGER AS away_wins,
            CASE WHEN SUM(wins + losses + draws) > 0
                THEN ROUND(SUM(wins)::NUMERIC / SUM(wins + losses + draws), 3)
                ELSE 0.000
            END AS win_pct,
            SUM(points_for)::INTEGER AS points_for,
            SUM(points_against)::INTEGER AS points_against,
            (SUM(points_for) - SUM(points_against))::INTEGER AS point_differential,
            CONCAT(SUM(wins)::TEXT, '-', SUM(losses)::TEXT,
                CASE WHEN SUM(draws) > 0 THEN '-' || SUM(draws)::TEXT ELSE '' END
            ) AS record_display
        FROM team_games
        GROUP BY sport, season, team_code
        ORDER BY sport, season DESC, win_pct DESC, wins DESC
    """)

    op.execute("""
        CREATE OR REPLACE VIEW current_season_standings AS
        SELECT tsr.*, t.team_name, t.display_name, t.conference, t.division, t.current_elo_rating
        FROM team_season_records tsr
        LEFT JOIN teams t ON t.team_code = tsr.team_code AND t.sport = tsr.sport
        WHERE tsr.season = EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER
        ORDER BY tsr.sport, tsr.win_pct DESC, tsr.wins DESC
    """)

    # =========================================================================
    # Step 8: Drop games table
    # =========================================================================
    op.execute("DROP TABLE IF EXISTS games CASCADE")
