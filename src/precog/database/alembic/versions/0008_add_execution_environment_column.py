"""
Add execution_environment column for single-database architecture.

Revision ID: 0008
Revises: 0007
Create Date: 2025-12-20

Implements ADR-107: Single-Database Architecture with Execution Environments.
Adds an ENUM column to distinguish trade/position origin across live, paper,
and backtest environments.

Purpose:
    - Enable single-database architecture (vs separate databases per environment)
    - Tag trades and positions by execution context
    - Support cross-environment analysis (compare paper vs live performance)
    - Provide unified data for model training

Related:
    - ADR-107: Single-Database Architecture with Execution Environments
    - ADR-092: Trade Source Tracking (existing trade_source column)
    - Issue #241: Cloud Deployment Strategy
    - REQ-DB-017: Execution Environment Tracking (planned)

Schema Design Notes:
    - ENUM type with three values: 'live', 'paper', 'backtest'
    - Default 'live' ensures backward compatibility
    - Orthogonal to trade_source (WHO created vs WHERE executed)
    - Convenience views for common filtered queries

Educational Note:
    This implements a "discriminator column" pattern - a single database with
    a column to distinguish data subsets. This is simpler than separate databases
    (one schema, one migration path, unified queries) while still allowing
    environment-specific views and queries.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0008"
down_revision: str = "0007"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Add execution_environment ENUM and column to trades and positions tables."""
    # Step 1: Create the ENUM type
    # Using raw SQL because SQLAlchemy's ENUM handling varies by dialect
    op.execute("""
        CREATE TYPE execution_environment AS ENUM ('live', 'paper', 'backtest')
    """)

    # Step 2: Add column to trades table
    # Default 'live' for backward compatibility with existing data
    op.add_column(
        "trades",
        sa.Column(
            "execution_environment",
            sa.Enum("live", "paper", "backtest", name="execution_environment"),
            nullable=False,
            server_default="live",
        ),
    )

    # Step 3: Add column to positions table
    op.add_column(
        "positions",
        sa.Column(
            "execution_environment",
            sa.Enum("live", "paper", "backtest", name="execution_environment"),
            nullable=False,
            server_default="live",
        ),
    )

    # Step 4: Create indexes for common queries
    op.create_index(
        "idx_trades_execution_environment",
        "trades",
        ["execution_environment"],
    )
    op.create_index(
        "idx_positions_execution_environment",
        "positions",
        ["execution_environment"],
    )

    # Step 5: Create convenience views for filtered access
    # live_trades - Production trading only
    op.execute("""
        CREATE VIEW live_trades AS
        SELECT * FROM trades WHERE execution_environment = 'live'
    """)

    # paper_trades - Demo/sandbox testing
    op.execute("""
        CREATE VIEW paper_trades AS
        SELECT * FROM trades WHERE execution_environment = 'paper'
    """)

    # backtest_trades - Historical simulation
    op.execute("""
        CREATE VIEW backtest_trades AS
        SELECT * FROM trades WHERE execution_environment = 'backtest'
    """)

    # live_positions - Production positions only (current rows)
    # Note: positions is SCD Type 2 table, must filter row_current_ind
    op.execute("""
        CREATE VIEW live_positions AS
        SELECT * FROM positions
        WHERE execution_environment = 'live' AND row_current_ind = TRUE
    """)

    # paper_positions - Demo positions (current rows)
    op.execute("""
        CREATE VIEW paper_positions AS
        SELECT * FROM positions
        WHERE execution_environment = 'paper' AND row_current_ind = TRUE
    """)

    # backtest_positions - Simulated positions (current rows)
    op.execute("""
        CREATE VIEW backtest_positions AS
        SELECT * FROM positions
        WHERE execution_environment = 'backtest' AND row_current_ind = TRUE
    """)

    # training_data_trades - Non-production trades for model training
    op.execute("""
        CREATE VIEW training_data_trades AS
        SELECT * FROM trades WHERE execution_environment IN ('paper', 'backtest')
    """)

    # Add column comments for documentation
    op.execute("""
        COMMENT ON COLUMN trades.execution_environment IS
        'Execution context: live (production), paper (demo API), backtest (simulation)'
    """)
    op.execute("""
        COMMENT ON COLUMN positions.execution_environment IS
        'Execution context: live (production), paper (demo API), backtest (simulation)'
    """)


def downgrade() -> None:
    """Remove execution_environment column and ENUM type."""
    # Step 1: Drop views first (they depend on the column)
    op.execute("DROP VIEW IF EXISTS training_data_trades")
    op.execute("DROP VIEW IF EXISTS backtest_positions")
    op.execute("DROP VIEW IF EXISTS paper_positions")
    op.execute("DROP VIEW IF EXISTS live_positions")
    op.execute("DROP VIEW IF EXISTS backtest_trades")
    op.execute("DROP VIEW IF EXISTS paper_trades")
    op.execute("DROP VIEW IF EXISTS live_trades")

    # Step 2: Drop indexes
    op.drop_index("idx_positions_execution_environment", table_name="positions")
    op.drop_index("idx_trades_execution_environment", table_name="trades")

    # Step 3: Drop columns
    op.drop_column("positions", "execution_environment")
    op.drop_column("trades", "execution_environment")

    # Step 4: Drop ENUM type
    op.execute("DROP TYPE IF EXISTS execution_environment")
