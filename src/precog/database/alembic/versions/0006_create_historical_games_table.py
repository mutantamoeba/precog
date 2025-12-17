"""
Create historical_games table for historical game results.

Revision ID: 0006
Revises: 0005
Create Date: 2025-12-15

Creates a table for storing historical game results from external sources
(ESPN, Sports-Reference, Kaggle datasets).

Purpose:
    - Store historical game results for backtesting predictions
    - Enable calculation of actual W/L against predictions
    - Support model validation with ground truth data

Related:
    - Issue #229: Expanded Historical Data Sources
    - ADR-029: ESPN Data Model
    - REQ-DATA-003: Multi-Sport Team Support

Schema Design Notes:
    - Stores final scores for completed games
    - Links to teams table via foreign keys
    - Supports neutral site games (bowl games, playoffs)
    - Tracks data provenance (source, source_file)

Data Sources:
    - ESPN API historical games
    - Pro-Football-Reference (web scraping)
    - Kaggle NFL/NBA datasets
    - Sports-Reference.com

Educational Note:
    Game results are the ground truth for validating predictions.
    By comparing predicted win probabilities against actual outcomes,
    we can measure model accuracy (Brier score, calibration curves).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0006"
down_revision: str = "0005"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create historical_games table with indexes and constraints."""
    op.create_table(
        "historical_games",
        sa.Column("historical_game_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sport", sa.String(20), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        # Team References (using team codes for flexibility with historical data)
        sa.Column("home_team_code", sa.String(10), nullable=False),
        sa.Column("away_team_code", sa.String(10), nullable=False),
        sa.Column(
            "home_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "away_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Game Results
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        # Game Context
        sa.Column("is_neutral_site", sa.Boolean(), server_default="false"),
        sa.Column("is_playoff", sa.Boolean(), server_default="false"),
        sa.Column("game_type", sa.String(30), nullable=True),
        # Venue (optional)
        sa.Column("venue_name", sa.String(100), nullable=True),
        sa.Column("attendance", sa.Integer(), nullable=True),
        # Data Provenance
        sa.Column("source", sa.String(50), nullable=False, server_default="imported"),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("external_game_id", sa.String(100), nullable=True),
        # Metadata
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        # Unique constraint: one game per date per team matchup
        sa.UniqueConstraint(
            "sport",
            "game_date",
            "home_team_code",
            "away_team_code",
            name="uq_historical_games_matchup",
        ),
        # Check constraints
        sa.CheckConstraint(
            "sport IN ('nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer')",
            name="historical_games_sport_check",
        ),
        sa.CheckConstraint(
            "season BETWEEN 1900 AND 2100",
            name="historical_games_season_check",
        ),
        sa.CheckConstraint(
            "(home_score IS NULL AND away_score IS NULL) OR (home_score >= 0 AND away_score >= 0)",
            name="historical_games_score_check",
        ),
        sa.CheckConstraint(
            "source IN ('espn', 'kaggle', 'sports_reference', 'fivethirtyeight', 'manual', 'imported')",
            name="historical_games_source_check",
        ),
        sa.CheckConstraint(
            "game_type IS NULL OR game_type IN ("
            "'regular', 'playoff', 'wildcard', 'divisional', 'conference', "
            "'championship', 'superbowl', 'bowl', 'preseason', 'allstar')",
            name="historical_games_game_type_check",
        ),
    )

    # Create indexes for query performance
    op.create_index("idx_historical_games_sport", "historical_games", ["sport"])
    op.create_index("idx_historical_games_season", "historical_games", ["season"])
    op.create_index("idx_historical_games_date", "historical_games", ["game_date"])
    op.create_index("idx_historical_games_home_team", "historical_games", ["home_team_code"])
    op.create_index("idx_historical_games_away_team", "historical_games", ["away_team_code"])
    op.create_index("idx_historical_games_source", "historical_games", ["source"])

    # Composite index for common queries (sport + season + date)
    op.create_index(
        "idx_historical_games_sport_season",
        "historical_games",
        ["sport", "season", "game_date"],
    )


def downgrade() -> None:
    """Drop historical_games table and all dependent objects."""
    op.drop_table("historical_games")
