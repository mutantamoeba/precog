"""
Create historical_odds table for historical betting lines.

Revision ID: 0007
Revises: 0006
Create Date: 2025-12-15

Creates a table for storing historical betting odds from external sources
(Kaggle, Odds Portal, sportsbook archives).

Purpose:
    - Store historical spreads, moneylines, and totals
    - Enable closing line value (CLV) analysis
    - Measure market efficiency over time
    - Support backtesting betting strategies

Related:
    - Issue #229: Expanded Historical Data Sources
    - ADR-002: Decimal Precision for Financial Data
    - REQ-DATA-003: Multi-Sport Team Support

Schema Design Notes:
    - Links to historical_games for game context
    - Supports open and close lines (for CLV analysis)
    - Tracks sportsbook source for line shopping research
    - All prices stored as DECIMAL for precision

Data Sources:
    - Kaggle NFL Scores and Betting Data (1966-present)
    - Odds Portal historical archives
    - Action Network line history

Educational Note:
    Closing Line Value (CLV) = Your bet price vs closing line.
    Beating the closing line is the best predictor of long-term profitability.
    This table enables historical CLV analysis across thousands of games.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0007"
down_revision: str = "0006"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create historical_odds table with indexes and constraints."""
    op.create_table(
        "historical_odds",
        sa.Column("historical_odds_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "historical_game_id",
            sa.Integer(),
            sa.ForeignKey("historical_games.historical_game_id", ondelete="CASCADE"),
            nullable=True,  # Nullable for orphan odds records
        ),
        # Game identification (for matching when game_id not available)
        sa.Column("sport", sa.String(20), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("home_team_code", sa.String(10), nullable=False),
        sa.Column("away_team_code", sa.String(10), nullable=False),
        # Sportsbook info
        sa.Column("sportsbook", sa.String(50), nullable=True),  # 'consensus', 'pinnacle', etc.
        # Spread (point spread)
        sa.Column("spread_home_open", sa.Numeric(5, 1), nullable=True),  # -3.5, +7.0
        sa.Column("spread_home_close", sa.Numeric(5, 1), nullable=True),
        sa.Column("spread_home_odds_open", sa.Integer(), nullable=True),  # -110, +105
        sa.Column("spread_home_odds_close", sa.Integer(), nullable=True),
        # Moneyline
        sa.Column("moneyline_home_open", sa.Integer(), nullable=True),  # -150, +130
        sa.Column("moneyline_home_close", sa.Integer(), nullable=True),
        sa.Column("moneyline_away_open", sa.Integer(), nullable=True),
        sa.Column("moneyline_away_close", sa.Integer(), nullable=True),
        # Total (over/under)
        sa.Column("total_open", sa.Numeric(5, 1), nullable=True),  # 45.5, 52.0
        sa.Column("total_close", sa.Numeric(5, 1), nullable=True),
        sa.Column("over_odds_open", sa.Integer(), nullable=True),  # -110
        sa.Column("over_odds_close", sa.Integer(), nullable=True),
        # Result info (for quick win/cover lookup)
        sa.Column("home_covered", sa.Boolean(), nullable=True),  # Did home cover spread?
        sa.Column("game_went_over", sa.Boolean(), nullable=True),  # Did total go over?
        # Data Provenance
        sa.Column("source", sa.String(50), nullable=False, server_default="imported"),
        sa.Column("source_file", sa.String(255), nullable=True),
        # Metadata
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        # Unique constraint: one odds record per game per sportsbook
        sa.UniqueConstraint(
            "sport",
            "game_date",
            "home_team_code",
            "away_team_code",
            "sportsbook",
            name="uq_historical_odds_game_book",
        ),
        # Check constraints
        sa.CheckConstraint(
            "sport IN ('nfl', 'nba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'soccer')",
            name="historical_odds_sport_check",
        ),
        sa.CheckConstraint(
            "source IN ('kaggle', 'odds_portal', 'action_network', 'pinnacle', 'manual', 'imported', 'betting_csv', 'fivethirtyeight', 'consensus')",
            name="historical_odds_source_check",
        ),
        sa.CheckConstraint(
            "spread_home_open IS NULL OR (spread_home_open BETWEEN -100 AND 100)",
            name="historical_odds_spread_check",
        ),
        sa.CheckConstraint(
            "total_open IS NULL OR (total_open BETWEEN 0 AND 500)",
            name="historical_odds_total_check",
        ),
    )

    # Create indexes for query performance
    op.create_index("idx_historical_odds_game", "historical_odds", ["historical_game_id"])
    op.create_index("idx_historical_odds_sport", "historical_odds", ["sport"])
    op.create_index("idx_historical_odds_date", "historical_odds", ["game_date"])
    op.create_index("idx_historical_odds_source", "historical_odds", ["source"])
    op.create_index("idx_historical_odds_sportsbook", "historical_odds", ["sportsbook"])

    # Composite index for game lookup
    op.create_index(
        "idx_historical_odds_game_lookup",
        "historical_odds",
        ["sport", "game_date", "home_team_code", "away_team_code"],
    )


def downgrade() -> None:
    """Drop historical_odds table and all dependent objects."""
    op.drop_table("historical_odds")
