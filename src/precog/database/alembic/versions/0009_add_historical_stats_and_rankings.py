"""
Add historical_stats and historical_rankings tables for data seeding.

Revision ID: 0009
Revises: 0008
Create Date: 2025-12-21

Implements Issue #236: StatsRecord/RankingRecord Infrastructure.
Adds tables for historical player/team statistics and rankings from
external data sources (nfl_data_py, FiveThirtyEight, Kaggle, etc.).

Purpose:
    - Store player and team statistics for model training
    - Store historical rankings (AP Poll, CFP, Coaches Poll, Elo-derived)
    - Support data provenance tracking (source, source_file)
    - Enable backtesting with realistic historical context

Design Decisions:
    - Uses team_code (VARCHAR) instead of team_id (FK) for flexible data loading
      (FK resolution happens during seed → production data transfer)
    - JSONB for stats field enables flexible stat schemas per sport/category
    - Separate from live tables (team_rankings, game_states) to avoid mixing
      historical seed data with real-time production data
    - Follows pattern from Migrations 0005-0007 (historical_elo, historical_games, historical_odds)

Related:
    - Issue #236: StatsRecord/RankingRecord Infrastructure
    - ADR-106: Historical Data Collection Architecture
    - REQ-DATA-005 through REQ-DATA-008: Historical data requirements
    - base_source.py: StatsRecord and RankingRecord TypedDict definitions

Educational Note:
    This migration creates "staging tables" for historical data. Unlike the live
    tables (team_rankings, game_states), these use VARCHAR team_code instead of
    INTEGER team_id FK. This allows loading data before team mappings exist,
    with FK resolution as a separate step. The JSONB stats field allows each
    sport/source to have different stat schemas without schema changes.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision: str = "0009"
down_revision: str = "0008"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create historical_stats and historical_rankings tables."""
    # =========================================================================
    # Table 1: historical_stats
    # =========================================================================
    # Stores player and team statistics from external sources
    # Uses JSONB for flexible stat schemas across sports/categories
    op.create_table(
        "historical_stats",
        sa.Column(
            "historical_stat_id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Primary key for historical stat record",
        ),
        sa.Column(
            "sport",
            sa.String(20),
            nullable=False,
            comment="Sport code (nfl, ncaaf, nba, ncaab, nhl, mlb)",
        ),
        sa.Column(
            "season",
            sa.Integer(),
            nullable=False,
            comment="Season year (e.g., 2024 for 2024-25 season)",
        ),
        sa.Column(
            "week",
            sa.Integer(),
            nullable=True,
            comment="Week number (NULL for season-level stats)",
        ),
        sa.Column(
            "team_code",
            sa.String(10),
            nullable=True,
            comment="Team abbreviation (NULL for individual player stats)",
        ),
        sa.Column(
            "player_id",
            sa.String(50),
            nullable=True,
            comment="External player ID from source (NULL for team stats)",
        ),
        sa.Column(
            "player_name",
            sa.String(100),
            nullable=True,
            comment="Player display name (NULL for team stats)",
        ),
        sa.Column(
            "stat_category",
            sa.String(50),
            nullable=False,
            comment="Category: passing, rushing, receiving, team_offense, team_defense, etc.",
        ),
        sa.Column(
            "stats",
            JSONB(),
            nullable=False,
            comment="Flexible stat fields as JSONB (varies by sport/category)",
        ),
        sa.Column(
            "source",
            sa.String(100),
            nullable=False,
            comment="Data source name (nfl_data_py, espn, pro_football_reference)",
        ),
        sa.Column(
            "source_file",
            sa.String(255),
            nullable=True,
            comment="Source filename for CSV/file-based sources",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Record creation timestamp",
        ),
        # Constraints
        sa.CheckConstraint(
            "sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'mlb', 'wnba', 'soccer')",
            name="ck_historical_stats_sport",
        ),
        sa.CheckConstraint(
            "season BETWEEN 1900 AND 2100",
            name="ck_historical_stats_season",
        ),
        sa.CheckConstraint(
            "week IS NULL OR week BETWEEN 0 AND 30",
            name="ck_historical_stats_week",
        ),
        sa.CheckConstraint(
            "(team_code IS NOT NULL) OR (player_id IS NOT NULL)",
            name="ck_historical_stats_team_or_player",
        ),
    )

    # Indexes for historical_stats
    # Note: SQLAlchemy Index doesn't support comments, documenting intent here:
    # - idx_historical_stats_sport_season: Query stats by sport and season
    # - idx_historical_stats_team: Query team stats (partial index)
    # - idx_historical_stats_player: Query player stats (partial index)
    # - idx_historical_stats_category: Query by stat category
    # - idx_historical_stats_source: Query/filter by data source
    # - idx_historical_stats_stats_gin: GIN index for JSONB stat field queries
    op.create_index(
        "idx_historical_stats_sport_season",
        "historical_stats",
        ["sport", "season"],
    )
    op.create_index(
        "idx_historical_stats_team",
        "historical_stats",
        ["team_code", "season"],
        postgresql_where=sa.text("team_code IS NOT NULL"),
    )
    op.create_index(
        "idx_historical_stats_player",
        "historical_stats",
        ["player_id", "season"],
        postgresql_where=sa.text("player_id IS NOT NULL"),
    )
    op.create_index(
        "idx_historical_stats_category",
        "historical_stats",
        ["sport", "stat_category"],
    )
    op.create_index(
        "idx_historical_stats_source",
        "historical_stats",
        ["source"],
    )
    op.create_index(
        "idx_historical_stats_stats_gin",
        "historical_stats",
        ["stats"],
        postgresql_using="gin",
    )

    # =========================================================================
    # Table 2: historical_rankings
    # =========================================================================
    # Stores historical team rankings from various sources
    op.create_table(
        "historical_rankings",
        sa.Column(
            "historical_ranking_id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Primary key for historical ranking record",
        ),
        sa.Column(
            "sport",
            sa.String(20),
            nullable=False,
            comment="Sport code (nfl, ncaaf, nba, ncaab, nhl, mlb)",
        ),
        sa.Column(
            "season",
            sa.Integer(),
            nullable=False,
            comment="Season year (e.g., 2024 for 2024-25 season)",
        ),
        sa.Column(
            "week",
            sa.Integer(),
            nullable=False,
            comment="Week number when ranking was released",
        ),
        sa.Column(
            "team_code",
            sa.String(10),
            nullable=False,
            comment="Team abbreviation (e.g., KC, DAL, ALA)",
        ),
        sa.Column(
            "rank",
            sa.Integer(),
            nullable=False,
            comment="Ranking position (1 = best)",
        ),
        sa.Column(
            "previous_rank",
            sa.Integer(),
            nullable=True,
            comment="Previous week ranking (NULL for week 1 or if unknown)",
        ),
        sa.Column(
            "points",
            sa.Integer(),
            nullable=True,
            comment="Poll points received (NULL for non-point rankings like Elo)",
        ),
        sa.Column(
            "first_place_votes",
            sa.Integer(),
            nullable=True,
            comment="Number of first-place votes (NULL for non-voting rankings)",
        ),
        sa.Column(
            "poll_type",
            sa.String(50),
            nullable=False,
            comment="Ranking type: ap_poll, cfp, coaches, elo, power_ranking, etc.",
        ),
        sa.Column(
            "source",
            sa.String(100),
            nullable=False,
            comment="Data source name (espn, fivethirtyeight, kaggle)",
        ),
        sa.Column(
            "source_file",
            sa.String(255),
            nullable=True,
            comment="Source filename for CSV/file-based sources",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Record creation timestamp",
        ),
        # Constraints
        sa.CheckConstraint(
            "sport IN ('nfl', 'ncaaf', 'nba', 'ncaab', 'nhl', 'mlb', 'wnba', 'soccer')",
            name="ck_historical_rankings_sport",
        ),
        sa.CheckConstraint(
            "season BETWEEN 1900 AND 2100",
            name="ck_historical_rankings_season",
        ),
        sa.CheckConstraint(
            "week BETWEEN 0 AND 30",
            name="ck_historical_rankings_week",
        ),
        sa.CheckConstraint(
            "rank > 0",
            name="ck_historical_rankings_rank_positive",
        ),
        sa.CheckConstraint(
            "previous_rank IS NULL OR previous_rank > 0",
            name="ck_historical_rankings_previous_rank_positive",
        ),
        sa.CheckConstraint(
            "points IS NULL OR points >= 0",
            name="ck_historical_rankings_points_non_negative",
        ),
        sa.CheckConstraint(
            "first_place_votes IS NULL OR first_place_votes >= 0",
            name="ck_historical_rankings_votes_non_negative",
        ),
        # Unique constraint: one ranking per team per poll per week
        sa.UniqueConstraint(
            "sport",
            "season",
            "week",
            "team_code",
            "poll_type",
            name="uq_historical_rankings_team_poll_week",
        ),
    )

    # Indexes for historical_rankings
    # Note: SQLAlchemy Index doesn't support comments, documenting intent here:
    # - idx_historical_rankings_sport_season: Query rankings by sport and season
    # - idx_historical_rankings_team: Query team ranking history
    # - idx_historical_rankings_poll: Query full poll for a week
    op.create_index(
        "idx_historical_rankings_sport_season",
        "historical_rankings",
        ["sport", "season"],
    )
    op.create_index(
        "idx_historical_rankings_team",
        "historical_rankings",
        ["team_code", "season"],
    )
    op.create_index(
        "idx_historical_rankings_poll",
        "historical_rankings",
        ["poll_type", "season", "week"],
    )
    # - idx_historical_rankings_source: Query/filter by data source
    # - idx_historical_rankings_rank: Query by rank position (e.g., top 25)
    op.create_index(
        "idx_historical_rankings_source",
        "historical_rankings",
        ["source"],
    )
    op.create_index(
        "idx_historical_rankings_rank",
        "historical_rankings",
        ["sport", "season", "week", "rank"],
    )

    # Add table comments for documentation
    op.execute("""
        COMMENT ON TABLE historical_stats IS
        'Historical player and team statistics for model training and backtesting.
         Uses JSONB for flexible stat schemas. Links to teams via team_code (VARCHAR)
         instead of FK for flexible data loading. Source: Issue #236.'
    """)
    op.execute("""
        COMMENT ON TABLE historical_rankings IS
        'Historical team rankings from various polls and sources.
         Includes AP Poll, CFP, Coaches Poll, and derived rankings like Elo.
         Uses team_code (VARCHAR) for flexible loading. Source: Issue #236.'
    """)


def downgrade() -> None:
    """Remove historical_stats and historical_rankings tables."""
    # Drop historical_rankings table and indexes
    op.drop_index("idx_historical_rankings_rank", table_name="historical_rankings")
    op.drop_index("idx_historical_rankings_source", table_name="historical_rankings")
    op.drop_index("idx_historical_rankings_poll", table_name="historical_rankings")
    op.drop_index("idx_historical_rankings_team", table_name="historical_rankings")
    op.drop_index("idx_historical_rankings_sport_season", table_name="historical_rankings")
    op.drop_table("historical_rankings")

    # Drop historical_stats table and indexes
    op.drop_index("idx_historical_stats_stats_gin", table_name="historical_stats")
    op.drop_index("idx_historical_stats_source", table_name="historical_stats")
    op.drop_index("idx_historical_stats_category", table_name="historical_stats")
    op.drop_index("idx_historical_stats_player", table_name="historical_stats")
    op.drop_index("idx_historical_stats_team", table_name="historical_stats")
    op.drop_index("idx_historical_stats_sport_season", table_name="historical_stats")
    op.drop_table("historical_stats")
