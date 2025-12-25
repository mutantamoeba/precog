"""
Add historical_epa table, elo_calculation_log audit table, and team_id FKs.

Revision ID: 0013
Revises: 0012
Create Date: 2025-12-25

Phase 2.7: Historical Data Seeding infrastructure.
This migration adds schema enhancements needed for Elo computation and model training.

Purpose:
    - Create historical_epa table for NFL EPA metrics (used for Elo adjustments)
    - Create elo_calculation_log table for audit trail of Elo computations
    - Add team_id foreign keys to historical tables for production joins

Design Decisions:
    - historical_epa: Separate from historical_elo (NFL-specific, weekly granularity)
    - elo_calculation_log: Captures every Elo calculation for debugging and compliance
    - team_id FKs: Enable joins to teams/markets; nullable for gradual backfill
    - team_code retained: Both team_code (seeding) and team_id (production) coexist

Related:
    - Issue #273: Comprehensive Elo Rating Computation Module
    - ADR-109: Elo Computation Architecture
    - REQ-ELO-001 through REQ-ELO-007: Elo computation requirements
    - REQ-DATA-009: Team_id FK for historical tables
    - REQ-DATA-010: Historical odds loading
    - REQ-DATA-011: Historical EPA loading

Educational Note:
    This migration implements a "two-layer schema architecture":
    1. Seeding Layer: team_code (VARCHAR) for flexible external data loading
    2. Production Layer: team_id (INTEGER FK) for referential integrity

    The historical tables originally used only team_code to allow seeding data
    before team mappings exist. This migration adds team_id FKs to enable
    efficient joins to the teams table while preserving backward compatibility.
    A separate backfill step will populate team_id from team_code mapping.

    The historical_epa table stores NFL Expected Points Added metrics from
    nflreadpy. EPA is the best predictor of team quality and is used to
    adjust Elo ratings (+/- 50 points based on EPA differential).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0013"
down_revision: str = "0012"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Add historical_epa, elo_calculation_log tables and team_id FKs."""
    # =========================================================================
    # Table 1: historical_epa (NFL EPA metrics for Elo adjustment)
    # =========================================================================
    # Stores Expected Points Added metrics from nflreadpy load_pbp()
    # Weekly granularity, team-level aggregation
    op.create_table(
        "historical_epa",
        sa.Column(
            "historical_epa_id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Primary key for historical EPA record",
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,  # Nullable for gradual backfill from team_code
            comment="FK to teams table (for production joins)",
        ),
        sa.Column(
            "team_code",
            sa.String(10),
            nullable=False,
            comment="Team abbreviation (e.g., KC, BUF) for data loading",
        ),
        sa.Column(
            "sport",
            sa.String(20),
            nullable=False,
            server_default="nfl",
            comment="Sport code (nfl only currently, EPA is NFL-specific)",
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
            comment="Week number (NULL for season-level totals)",
        ),
        # EPA metrics from nflreadpy
        sa.Column(
            "off_epa_per_play",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Offensive EPA per play (higher is better)",
        ),
        sa.Column(
            "def_epa_per_play",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Defensive EPA per play (lower is better, stored as positive)",
        ),
        sa.Column(
            "pass_epa_per_play",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Passing EPA per play",
        ),
        sa.Column(
            "rush_epa_per_play",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Rushing EPA per play",
        ),
        sa.Column(
            "epa_differential",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Offensive EPA - Defensive EPA (positive = good)",
        ),
        sa.Column(
            "elo_adjustment",
            sa.Numeric(8, 2),
            nullable=True,
            comment="Computed Elo adjustment from EPA (-50 to +50 range)",
        ),
        # Game context
        sa.Column(
            "games_played",
            sa.Integer(),
            nullable=True,
            comment="Number of games included in this aggregation",
        ),
        sa.Column(
            "total_plays",
            sa.Integer(),
            nullable=True,
            comment="Total plays in aggregation (for weighted averages)",
        ),
        # Data provenance
        sa.Column(
            "source",
            sa.String(100),
            nullable=False,
            server_default="nflreadpy",
            comment="Data source (nflreadpy, nfl_data_py, manual)",
        ),
        sa.Column(
            "source_file",
            sa.String(255),
            nullable=True,
            comment="Source filename for file-based sources",
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
            "sport IN ('nfl')",  # EPA is NFL-specific currently
            name="ck_historical_epa_sport",
        ),
        sa.CheckConstraint(
            "season BETWEEN 1999 AND 2100",  # nflverse data starts 1999
            name="ck_historical_epa_season",
        ),
        sa.CheckConstraint(
            "week IS NULL OR week BETWEEN 0 AND 22",  # Including playoffs
            name="ck_historical_epa_week",
        ),
        sa.CheckConstraint(
            "elo_adjustment IS NULL OR (elo_adjustment BETWEEN -100 AND 100)",
            name="ck_historical_epa_adjustment",
        ),
        # Unique constraint: one EPA record per team per season per week
        sa.UniqueConstraint(
            "team_code",
            "season",
            "week",
            name="uq_historical_epa_team_season_week",
        ),
    )

    # Indexes for historical_epa
    op.create_index(
        "idx_historical_epa_team_id",
        "historical_epa",
        ["team_id"],
        postgresql_where=sa.text("team_id IS NOT NULL"),
    )
    op.create_index(
        "idx_historical_epa_team_code",
        "historical_epa",
        ["team_code", "season"],
    )
    op.create_index(
        "idx_historical_epa_season_week",
        "historical_epa",
        ["season", "week"],
    )
    op.create_index(
        "idx_historical_epa_source",
        "historical_epa",
        ["source"],
    )

    # =========================================================================
    # Table 2: elo_calculation_log (Audit trail for Elo computations)
    # =========================================================================
    # Records every Elo calculation for debugging and regulatory compliance
    op.create_table(
        "elo_calculation_log",
        sa.Column(
            "log_id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment="Primary key for log entry",
        ),
        # Game reference (one of game_state_id or historical_game_id should be set)
        # Note: game_states uses SCD Type 2 (multiple rows per game), so we reference
        # the surrogate key (id) rather than espn_event_id
        sa.Column(
            "game_state_id",
            sa.Integer(),
            sa.ForeignKey("game_states.id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to game_states.id (for real-time updates, references specific SCD row)",
        ),
        sa.Column(
            "historical_game_id",
            sa.Integer(),
            sa.ForeignKey("historical_games.historical_game_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to historical_games table (for bootstrap)",
        ),
        # Game identification
        sa.Column(
            "sport",
            sa.String(20),
            nullable=False,
            comment="Sport code (nfl, nba, nhl, mlb, etc.)",
        ),
        sa.Column(
            "game_date",
            sa.Date(),
            nullable=False,
            comment="Date of the game",
        ),
        # Team references
        sa.Column(
            "home_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table for home team",
        ),
        sa.Column(
            "away_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table for away team",
        ),
        sa.Column(
            "home_team_code",
            sa.String(10),
            nullable=False,
            comment="Home team abbreviation",
        ),
        sa.Column(
            "away_team_code",
            sa.String(10),
            nullable=False,
            comment="Away team abbreviation",
        ),
        # Game result
        sa.Column(
            "home_score",
            sa.Integer(),
            nullable=False,
            comment="Home team final score",
        ),
        sa.Column(
            "away_score",
            sa.Integer(),
            nullable=False,
            comment="Away team final score",
        ),
        # Pre-game Elo ratings
        sa.Column(
            "home_elo_before",
            sa.Numeric(8, 2),
            nullable=False,
            comment="Home team Elo before game",
        ),
        sa.Column(
            "away_elo_before",
            sa.Numeric(8, 2),
            nullable=False,
            comment="Away team Elo before game",
        ),
        # Calculation parameters
        sa.Column(
            "k_factor",
            sa.Integer(),
            nullable=False,
            comment="K-factor used (NFL: 20, NBA: 20, NHL: 6, MLB: 4)",
        ),
        sa.Column(
            "home_advantage",
            sa.Numeric(6, 2),
            nullable=False,
            comment="Home advantage applied (NFL: 65, NBA: 100)",
        ),
        sa.Column(
            "mov_multiplier",
            sa.Numeric(6, 4),
            nullable=True,
            comment="Margin of victory multiplier (optional)",
        ),
        # Expected vs actual scores
        sa.Column(
            "home_expected",
            sa.Numeric(6, 4),
            nullable=False,
            comment="Expected score for home team (0.0 to 1.0)",
        ),
        sa.Column(
            "away_expected",
            sa.Numeric(6, 4),
            nullable=False,
            comment="Expected score for away team (0.0 to 1.0)",
        ),
        sa.Column(
            "home_actual",
            sa.Numeric(4, 2),
            nullable=False,
            comment="Actual score for home team (1.0=win, 0.5=tie, 0.0=loss)",
        ),
        sa.Column(
            "away_actual",
            sa.Numeric(4, 2),
            nullable=False,
            comment="Actual score for away team (1.0=win, 0.5=tie, 0.0=loss)",
        ),
        # Elo changes
        sa.Column(
            "home_elo_change",
            sa.Numeric(6, 2),
            nullable=False,
            comment="Change in home team Elo",
        ),
        sa.Column(
            "away_elo_change",
            sa.Numeric(6, 2),
            nullable=False,
            comment="Change in away team Elo",
        ),
        # Post-game Elo ratings
        sa.Column(
            "home_elo_after",
            sa.Numeric(8, 2),
            nullable=False,
            comment="Home team Elo after game",
        ),
        sa.Column(
            "away_elo_after",
            sa.Numeric(8, 2),
            nullable=False,
            comment="Away team Elo after game",
        ),
        # EPA adjustments (NFL only)
        sa.Column(
            "home_epa_adjustment",
            sa.Numeric(6, 2),
            nullable=True,
            comment="EPA-based adjustment for home team (NFL only)",
        ),
        sa.Column(
            "away_epa_adjustment",
            sa.Numeric(6, 2),
            nullable=True,
            comment="EPA-based adjustment for away team (NFL only)",
        ),
        # Metadata
        sa.Column(
            "calculation_source",
            sa.String(50),
            nullable=False,
            comment="How calculation was triggered: bootstrap, realtime, backfill, manual",
        ),
        sa.Column(
            "calculation_version",
            sa.String(20),
            nullable=False,
            server_default="1.0",
            comment="Version of Elo algorithm used",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="When calculation was performed",
        ),
        # Constraints
        sa.CheckConstraint(
            "sport IN ('nfl', 'nba', 'nhl', 'mlb', 'ncaaf', 'ncaab', 'ncaaw', 'wnba', 'mls', 'soccer')",
            name="ck_elo_log_sport",
        ),
        sa.CheckConstraint(
            "home_expected BETWEEN 0 AND 1 AND away_expected BETWEEN 0 AND 1",
            name="ck_elo_log_expected",
        ),
        sa.CheckConstraint(
            "home_actual IN (0.0, 0.5, 1.0) AND away_actual IN (0.0, 0.5, 1.0)",
            name="ck_elo_log_actual",
        ),
        sa.CheckConstraint(
            "calculation_source IN ('bootstrap', 'realtime', 'backfill', 'manual', 'test')",
            name="ck_elo_log_source",
        ),
        sa.CheckConstraint(
            "home_elo_before BETWEEN 100 AND 2500 AND away_elo_before BETWEEN 100 AND 2500",
            name="ck_elo_log_elo_range_before",
        ),
        sa.CheckConstraint(
            "home_elo_after BETWEEN 100 AND 2500 AND away_elo_after BETWEEN 100 AND 2500",
            name="ck_elo_log_elo_range_after",
        ),
    )

    # Indexes for elo_calculation_log
    op.create_index(
        "idx_elo_log_game_state",
        "elo_calculation_log",
        ["game_state_id"],
        postgresql_where=sa.text("game_state_id IS NOT NULL"),
    )
    op.create_index(
        "idx_elo_log_historical_game",
        "elo_calculation_log",
        ["historical_game_id"],
        postgresql_where=sa.text("historical_game_id IS NOT NULL"),
    )
    op.create_index(
        "idx_elo_log_sport_date",
        "elo_calculation_log",
        ["sport", "game_date"],
    )
    op.create_index(
        "idx_elo_log_home_team",
        "elo_calculation_log",
        ["home_team_id"],
        postgresql_where=sa.text("home_team_id IS NOT NULL"),
    )
    op.create_index(
        "idx_elo_log_away_team",
        "elo_calculation_log",
        ["away_team_id"],
        postgresql_where=sa.text("away_team_id IS NOT NULL"),
    )
    op.create_index(
        "idx_elo_log_source",
        "elo_calculation_log",
        ["calculation_source"],
    )
    op.create_index(
        "idx_elo_log_created",
        "elo_calculation_log",
        ["created_at"],
    )

    # =========================================================================
    # Add team_id FK to historical_odds
    # =========================================================================
    op.add_column(
        "historical_odds",
        sa.Column(
            "home_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table for home team (backfill from home_team_code)",
        ),
    )
    op.add_column(
        "historical_odds",
        sa.Column(
            "away_team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table for away team (backfill from away_team_code)",
        ),
    )
    op.create_index(
        "idx_historical_odds_home_team_id",
        "historical_odds",
        ["home_team_id"],
        postgresql_where=sa.text("home_team_id IS NOT NULL"),
    )
    op.create_index(
        "idx_historical_odds_away_team_id",
        "historical_odds",
        ["away_team_id"],
        postgresql_where=sa.text("away_team_id IS NOT NULL"),
    )

    # =========================================================================
    # Add team_id FK to historical_stats
    # =========================================================================
    op.add_column(
        "historical_stats",
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table (backfill from team_code)",
        ),
    )
    op.create_index(
        "idx_historical_stats_team_id",
        "historical_stats",
        ["team_id"],
        postgresql_where=sa.text("team_id IS NOT NULL"),
    )

    # =========================================================================
    # Add team_id FK to historical_rankings
    # =========================================================================
    op.add_column(
        "historical_rankings",
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to teams table (backfill from team_code)",
        ),
    )
    op.create_index(
        "idx_historical_rankings_team_id",
        "historical_rankings",
        ["team_id"],
        postgresql_where=sa.text("team_id IS NOT NULL"),
    )

    # =========================================================================
    # Add table comments
    # =========================================================================
    op.execute("""
        COMMENT ON TABLE historical_epa IS
        'NFL Expected Points Added metrics for Elo adjustment and model training.
         Weekly team-level aggregates from nflreadpy load_pbp(). EPA differential
         is used to compute Elo adjustments (+/- 50 points). Source: Issue #273.'
    """)
    op.execute("""
        COMMENT ON TABLE elo_calculation_log IS
        'Audit trail for all Elo rating calculations. Records pre/post ratings,
         calculation parameters, and result for every game processed. Supports
         debugging, validation against FiveThirtyEight, and regulatory compliance.
         Source: Issue #273, ADR-109.'
    """)


def downgrade() -> None:
    """Remove historical_epa, elo_calculation_log tables and team_id FKs."""
    # =========================================================================
    # Remove team_id FK from historical_rankings
    # =========================================================================
    op.drop_index("idx_historical_rankings_team_id", table_name="historical_rankings")
    op.drop_column("historical_rankings", "team_id")

    # =========================================================================
    # Remove team_id FK from historical_stats
    # =========================================================================
    op.drop_index("idx_historical_stats_team_id", table_name="historical_stats")
    op.drop_column("historical_stats", "team_id")

    # =========================================================================
    # Remove team_id FKs from historical_odds
    # =========================================================================
    op.drop_index("idx_historical_odds_away_team_id", table_name="historical_odds")
    op.drop_index("idx_historical_odds_home_team_id", table_name="historical_odds")
    op.drop_column("historical_odds", "away_team_id")
    op.drop_column("historical_odds", "home_team_id")

    # =========================================================================
    # Drop elo_calculation_log table
    # =========================================================================
    op.drop_index("idx_elo_log_created", table_name="elo_calculation_log")
    op.drop_index("idx_elo_log_source", table_name="elo_calculation_log")
    op.drop_index("idx_elo_log_away_team", table_name="elo_calculation_log")
    op.drop_index("idx_elo_log_home_team", table_name="elo_calculation_log")
    op.drop_index("idx_elo_log_sport_date", table_name="elo_calculation_log")
    op.drop_index("idx_elo_log_historical_game", table_name="elo_calculation_log")
    op.drop_index("idx_elo_log_game_state", table_name="elo_calculation_log")
    op.drop_table("elo_calculation_log")

    # =========================================================================
    # Drop historical_epa table
    # =========================================================================
    op.drop_index("idx_historical_epa_source", table_name="historical_epa")
    op.drop_index("idx_historical_epa_season_week", table_name="historical_epa")
    op.drop_index("idx_historical_epa_team_code", table_name="historical_epa")
    op.drop_index("idx_historical_epa_team_id", table_name="historical_epa")
    op.drop_table("historical_epa")
