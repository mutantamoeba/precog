"""
Create team_season_records view for win/loss/draw tracking.

Revision ID: 0014
Revises: 0013
Create Date: 2025-12-26

This migration creates a VIEW that derives team season records (wins, losses,
draws) from BOTH data sources:

1. historical_games table - Pre-seeded historical data (FiveThirtyEight, pybaseball)
2. game_states table - Live game data from ESPN poller (current season)

This dual-source approach ensures:
- Historical seasons have W/L/D from pre-seeded data
- Current season updates automatically from live game tracking
- Single unified VIEW for all queries

Design Decision:
    Uses UNION ALL to combine both sources, avoiding duplicates by:
    - historical_games: Used for seasons BEFORE current year
    - game_states: Used for current year (status='final')

    This prevents double-counting if historical data is seeded for current season.

Related Issues:
    - User question about W/L/D tracking (2025-12-26)
    - Gap identified: game_states → historical_games sync missing
    - Solution: VIEW reads from both tables directly

Educational Note:
    Sports use different terminology:
    - NFL/NCAAF: Wins, Losses, Ties (ties are rare in NFL since OT rules)
    - NBA/WNBA: Wins, Losses (no ties possible)
    - NHL: Wins, Losses, OT Losses (OTL counts as loss but gives 1 point)
    - MLB: Wins, Losses (no ties in regular games)
    - Soccer: Wins, Losses, Draws

    The view uses generic 'draws' column which can represent:
    - Ties (NFL/NCAAF)
    - OT Losses (NHL - for display purposes)
    - Draws (soccer)
"""

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0014"
down_revision: str = "0013"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create team_season_records view from both historical_games and game_states."""
    # =========================================================================
    # View: team_season_records
    # =========================================================================
    # Aggregates win/loss/draw records from BOTH:
    # - historical_games (pre-seeded historical data)
    # - game_states (live game data, status='final')
    op.execute("""
        CREATE OR REPLACE VIEW team_season_records AS
        WITH all_games AS (
            -- Source 1: historical_games (pre-seeded data)
            -- Used for all seasons (historical + backfill of current)
            SELECT
                sport,
                season,
                game_date,
                home_team_code,
                away_team_code,
                home_score,
                away_score,
                'historical_games' AS data_source
            FROM historical_games
            WHERE home_score IS NOT NULL AND away_score IS NOT NULL

            UNION ALL

            -- Source 2: game_states (live ESPN data, current season only)
            -- Only include final games not already in historical_games
            -- Note: game_states doesn't have sport column; derive from teams table
            SELECT
                ht.sport,  -- Sport from teams table (home/away have same sport)
                EXTRACT(YEAR FROM gs.game_date)::INTEGER AS season,
                gs.game_date,
                ht.team_code AS home_team_code,
                at.team_code AS away_team_code,
                gs.home_score,
                gs.away_score,
                'game_states' AS data_source
            FROM game_states gs
            JOIN teams ht ON gs.home_team_id = ht.team_id
            JOIN teams at ON gs.away_team_id = at.team_id
            WHERE gs.game_status = 'final'
              AND gs.row_current_ind = TRUE
              AND NOT EXISTS (
                  -- Avoid duplicates if game already in historical_games
                  SELECT 1 FROM historical_games hg
                  WHERE hg.sport = ht.sport  -- Use teams.sport, not game_states.sport
                    AND hg.game_date = gs.game_date
                    AND hg.home_team_code = ht.team_code
                    AND hg.away_team_code = at.team_code
              )
        ),
        team_games AS (
            -- Get all games from home team perspective
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

            -- Get all games from away team perspective
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
            -- Win percentage (handle division by zero)
            CASE
                WHEN SUM(wins + losses + draws) > 0
                THEN ROUND(SUM(wins)::NUMERIC / SUM(wins + losses + draws), 3)
                ELSE 0.000
            END AS win_pct,
            -- Points differential
            SUM(points_for)::INTEGER AS points_for,
            SUM(points_against)::INTEGER AS points_against,
            (SUM(points_for) - SUM(points_against))::INTEGER AS point_differential,
            -- Record display string
            CONCAT(
                SUM(wins)::TEXT, '-',
                SUM(losses)::TEXT,
                CASE WHEN SUM(draws) > 0 THEN '-' || SUM(draws)::TEXT ELSE '' END
            ) AS record_display
        FROM team_games
        GROUP BY sport, season, team_code
        ORDER BY sport, season DESC, win_pct DESC, wins DESC
    """)

    # Add comment to view for documentation
    op.execute("""
        COMMENT ON VIEW team_season_records IS
        'Derived view showing team season records (W-L-D) from BOTH historical_games
         AND game_states tables. Handles deduplication automatically.

         Data Sources:
         - historical_games: Pre-seeded data (FiveThirtyEight, pybaseball, etc.)
         - game_states: Live game data (ESPN poller, status=final)

         Query examples:
         - Current season: WHERE season = 2024 AND sport = ''nfl''
         - Historical: WHERE team_code = ''KC'' ORDER BY season DESC
         - Standings: WHERE sport = ''nfl'' AND season = 2024 ORDER BY win_pct DESC'
    """)

    # =========================================================================
    # View: current_season_standings
    # =========================================================================
    # Convenience view for current season only (assumes current year)
    # This simplifies common queries for active season standings
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
         Auto-filters to current calendar year.

         Data automatically includes both:
         - Pre-seeded historical games (if any for current season)
         - Live completed games from ESPN poller'
    """)


def downgrade() -> None:
    """Remove team_season_records views."""
    op.execute("DROP VIEW IF EXISTS current_season_standings CASCADE")
    op.execute("DROP VIEW IF EXISTS team_season_records CASCADE")
