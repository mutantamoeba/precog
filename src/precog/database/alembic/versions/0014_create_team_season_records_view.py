"""
Create team_season_records view for win/loss/draw tracking.

Revision ID: 0014
Revises: 0013
Create Date: 2025-12-26

This migration creates a VIEW that derives team season records (wins, losses,
draws) from the historical_games table. This approach was chosen over:

1. New table: Would require sync logic and data duplication
2. Columns on teams: Would lose historical season-by-season data
3. Stored in historical_stats JSONB: Less queryable, harder to aggregate

The VIEW approach:
- No data duplication (single source of truth: historical_games)
- Automatic updates when games are inserted
- Full query flexibility (filter by sport, season, team)
- Supports current AND historical season records

Design Decision:
    Uses team_code (VARCHAR) instead of team_id (FK) to match historical_games
    schema pattern. FK resolution happens at application layer when needed.

Related Issues:
    - User question about W/L/D tracking (2025-12-26)
    - Issue #236: StatsRecord/RankingRecord Infrastructure (extends pattern)

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
    """Create team_season_records view."""
    # =========================================================================
    # View: team_season_records
    # =========================================================================
    # Aggregates win/loss/draw records from historical_games table
    # Each team appears once per season with their complete record
    op.execute("""
        CREATE OR REPLACE VIEW team_season_records AS
        WITH team_games AS (
            -- Get all games from home team perspective
            SELECT
                sport,
                season,
                home_team_code AS team_code,
                CASE
                    WHEN home_score > away_score THEN 1
                    ELSE 0
                END AS wins,
                CASE
                    WHEN home_score < away_score THEN 1
                    ELSE 0
                END AS losses,
                CASE
                    WHEN home_score = away_score AND home_score IS NOT NULL THEN 1
                    ELSE 0
                END AS draws,
                1 AS home_games,
                0 AS away_games,
                CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS home_wins,
                0 AS away_wins,
                COALESCE(home_score, 0) AS points_for,
                COALESCE(away_score, 0) AS points_against
            FROM historical_games
            WHERE home_score IS NOT NULL

            UNION ALL

            -- Get all games from away team perspective
            SELECT
                sport,
                season,
                away_team_code AS team_code,
                CASE
                    WHEN away_score > home_score THEN 1
                    ELSE 0
                END AS wins,
                CASE
                    WHEN away_score < home_score THEN 1
                    ELSE 0
                END AS losses,
                CASE
                    WHEN away_score = home_score AND away_score IS NOT NULL THEN 1
                    ELSE 0
                END AS draws,
                0 AS home_games,
                1 AS away_games,
                0 AS home_wins,
                CASE WHEN away_score > home_score THEN 1 ELSE 0 END AS away_wins,
                COALESCE(away_score, 0) AS points_for,
                COALESCE(home_score, 0) AS points_against
            FROM historical_games
            WHERE away_score IS NOT NULL
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
            -- Streak tracking (for current records)
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
        'Derived view showing team season records (W-L-D) from historical_games.
         Automatically updated when games are inserted. Uses team_code (VARCHAR)
         for flexibility. Query examples:
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
         Auto-filters to current calendar year.'
    """)


def downgrade() -> None:
    """Remove team_season_records views."""
    op.execute("DROP VIEW IF EXISTS current_season_standings CASCADE")
    op.execute("DROP VIEW IF EXISTS team_season_records CASCADE")
