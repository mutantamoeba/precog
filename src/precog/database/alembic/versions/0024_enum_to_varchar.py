"""Convert execution_environment and trade_source ENUMs to VARCHAR + CHECK.

PostgreSQL ENUMs are inflexible: you cannot remove values, and ALTER TYPE
cannot run inside transactions. Converting to VARCHAR(20) + CHECK constraints
gives identical data integrity with full ALTER TABLE flexibility, unblocking
future environment value additions without new type migrations.

Steps:
    1. Drop ALL dependent views (Pattern 38 -- views cache column types)
    2. Convert trades.execution_environment ENUM -> VARCHAR(20) + CHECK
    3. Convert positions.execution_environment ENUM -> VARCHAR(20) + CHECK
    4. Convert trades.trade_source ENUM -> VARCHAR(20) + CHECK
    5. Drop ENUM types (execution_environment, trade_source_type)
    6. Recreate ALL views with correct definitions

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0024 spec
- ADR-107: Single-Database Architecture (original ENUM source)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: str = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert ENUM columns to VARCHAR + CHECK, drop ENUM types.

    Pattern 38 applied: Drop all views that reference trades/positions
    before altering column types, then recreate afterward.

    ENUM -> VARCHAR is safe because PostgreSQL can cast ENUM values to text
    via the ``USING column::text`` clause. The CHECK constraint preserves
    the same domain restriction as the original ENUM.
    """
    # ------------------------------------------------------------------
    # Step 1: Drop ALL dependent views (Pattern 38)
    # PostgreSQL views with SELECT * cache column types at creation time.
    # When the underlying column type changes from ENUM to VARCHAR, stale
    # type bindings cause errors. Drop everything first, recreate after.
    # ------------------------------------------------------------------

    # Environment-filtered views (created in migration 0008)
    op.execute("DROP VIEW IF EXISTS live_trades")
    op.execute("DROP VIEW IF EXISTS paper_trades")
    op.execute("DROP VIEW IF EXISTS backtest_trades")
    op.execute("DROP VIEW IF EXISTS training_data_trades")
    op.execute("DROP VIEW IF EXISTS live_positions")
    op.execute("DROP VIEW IF EXISTS paper_positions")
    op.execute("DROP VIEW IF EXISTS backtest_positions")

    # SCD convenience views
    op.execute("DROP VIEW IF EXISTS open_positions")

    # Edge views (edges is already VARCHAR from 0023, but edge_lifecycle
    # references execution_environment and is safer to recreate)
    op.execute("DROP VIEW IF EXISTS edge_lifecycle")
    op.execute("DROP VIEW IF EXISTS current_edges")
    op.execute("DROP VIEW IF EXISTS current_game_states")

    # ------------------------------------------------------------------
    # Step 2: Convert trades.execution_environment (ENUM -> VARCHAR)
    # Must drop DEFAULT first -- can't ALTER TYPE with a default that
    # references the ENUM type.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE trades ALTER COLUMN execution_environment DROP DEFAULT")
    op.execute(
        "ALTER TABLE trades ALTER COLUMN execution_environment "
        "TYPE VARCHAR(20) USING execution_environment::text"
    )
    op.execute("ALTER TABLE trades ALTER COLUMN execution_environment SET DEFAULT 'live'")
    op.execute(
        "ALTER TABLE trades ADD CONSTRAINT chk_trades_exec_env "
        "CHECK (execution_environment IN ('live', 'paper', 'backtest'))"
    )

    # ------------------------------------------------------------------
    # Step 3: Convert positions.execution_environment (ENUM -> VARCHAR)
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE positions ALTER COLUMN execution_environment DROP DEFAULT")
    op.execute(
        "ALTER TABLE positions ALTER COLUMN execution_environment "
        "TYPE VARCHAR(20) USING execution_environment::text"
    )
    op.execute("ALTER TABLE positions ALTER COLUMN execution_environment SET DEFAULT 'live'")
    op.execute(
        "ALTER TABLE positions ADD CONSTRAINT chk_positions_exec_env "
        "CHECK (execution_environment IN ('live', 'paper', 'backtest'))"
    )

    # ------------------------------------------------------------------
    # Step 4: Convert trades.trade_source (ENUM -> VARCHAR)
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE trades ALTER COLUMN trade_source DROP DEFAULT")
    op.execute(
        "ALTER TABLE trades ALTER COLUMN trade_source TYPE VARCHAR(20) USING trade_source::text"
    )
    op.execute("ALTER TABLE trades ALTER COLUMN trade_source SET DEFAULT 'automated'")
    op.execute(
        "ALTER TABLE trades ADD CONSTRAINT chk_trades_source "
        "CHECK (trade_source IN ('automated', 'manual'))"
    )

    # ------------------------------------------------------------------
    # Step 5: Drop ENUM types (no longer referenced by any column)
    # ------------------------------------------------------------------
    op.execute("DROP TYPE IF EXISTS execution_environment")
    op.execute("DROP TYPE IF EXISTS trade_source_type")

    # ------------------------------------------------------------------
    # Step 6: Recreate ALL views
    # ------------------------------------------------------------------

    # Environment-filtered trade views
    op.execute(
        "CREATE OR REPLACE VIEW live_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'live'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW paper_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'paper'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW backtest_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'backtest'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW training_data_trades AS "
        "SELECT * FROM trades WHERE execution_environment IN ('paper', 'backtest')"
    )

    # Environment-filtered position views (SCD Type 2: always filter row_current_ind)
    op.execute(
        "CREATE OR REPLACE VIEW live_positions AS "
        "SELECT * FROM positions WHERE execution_environment = 'live' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW paper_positions AS "
        "SELECT * FROM positions WHERE execution_environment = 'paper' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW backtest_positions AS "
        "SELECT * FROM positions "
        "WHERE execution_environment = 'backtest' AND row_current_ind = TRUE"
    )

    # SCD convenience views
    op.execute(
        "CREATE OR REPLACE VIEW open_positions AS "
        "SELECT * FROM positions WHERE row_current_ind = TRUE AND status = 'open'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW current_game_states AS "
        "SELECT * FROM game_states WHERE row_current_ind = TRUE"
    )

    # Edge lifecycle view (from migration 0023)
    op.execute("""
        CREATE OR REPLACE VIEW edge_lifecycle AS
        SELECT
            e.id,
            e.edge_id,
            e.market_internal_id,
            e.model_id,
            e.strategy_id,
            e.expected_value,
            e.true_win_probability,
            e.market_implied_probability,
            e.market_price,
            e.yes_ask_price,
            e.no_ask_price,
            e.edge_status,
            e.actual_outcome,
            e.settlement_value,
            e.confidence_level,
            e.execution_environment,
            e.created_at,
            e.resolved_at,
            -- P&L assumes YES-side position (edge detection = buy YES)
            CASE
                WHEN e.actual_outcome = 'yes' THEN e.settlement_value - e.market_price
                WHEN e.actual_outcome = 'no' THEN e.market_price - e.settlement_value
                ELSE NULL
            END AS realized_pnl,
            CASE
                WHEN e.resolved_at IS NOT NULL AND e.created_at IS NOT NULL
                THEN EXTRACT(EPOCH FROM (e.resolved_at - e.created_at)) / 3600.0
                ELSE NULL
            END AS hours_to_resolution
        FROM edges e
        WHERE e.row_current_ind = TRUE
    """)


def downgrade() -> None:
    """Reverse: restore ENUM types, convert VARCHAR back to ENUM, recreate views."""
    # Step 1: Drop all views
    op.execute("DROP VIEW IF EXISTS edge_lifecycle")
    op.execute("DROP VIEW IF EXISTS current_game_states")
    op.execute("DROP VIEW IF EXISTS current_edges")
    op.execute("DROP VIEW IF EXISTS open_positions")
    op.execute("DROP VIEW IF EXISTS backtest_positions")
    op.execute("DROP VIEW IF EXISTS paper_positions")
    op.execute("DROP VIEW IF EXISTS live_positions")
    op.execute("DROP VIEW IF EXISTS training_data_trades")
    op.execute("DROP VIEW IF EXISTS backtest_trades")
    op.execute("DROP VIEW IF EXISTS paper_trades")
    op.execute("DROP VIEW IF EXISTS live_trades")

    # Step 2: Drop CHECK constraints
    op.execute("ALTER TABLE trades DROP CONSTRAINT IF EXISTS chk_trades_source")
    op.execute("ALTER TABLE positions DROP CONSTRAINT IF EXISTS chk_positions_exec_env")
    op.execute("ALTER TABLE trades DROP CONSTRAINT IF EXISTS chk_trades_exec_env")

    # Step 3: Recreate ENUM types
    op.execute("CREATE TYPE execution_environment AS ENUM ('live', 'paper', 'backtest')")
    op.execute("CREATE TYPE trade_source_type AS ENUM ('automated', 'manual')")

    # Step 4: Convert VARCHAR back to ENUM
    # trades.trade_source
    op.execute("ALTER TABLE trades ALTER COLUMN trade_source DROP DEFAULT")
    op.execute(
        "ALTER TABLE trades ALTER COLUMN trade_source "
        "TYPE trade_source_type USING trade_source::trade_source_type"
    )
    op.execute("ALTER TABLE trades ALTER COLUMN trade_source SET DEFAULT 'automated'")

    # positions.execution_environment
    op.execute("ALTER TABLE positions ALTER COLUMN execution_environment DROP DEFAULT")
    op.execute(
        "ALTER TABLE positions ALTER COLUMN execution_environment "
        "TYPE execution_environment USING execution_environment::execution_environment"
    )
    op.execute("ALTER TABLE positions ALTER COLUMN execution_environment SET DEFAULT 'live'")

    # trades.execution_environment
    op.execute("ALTER TABLE trades ALTER COLUMN execution_environment DROP DEFAULT")
    op.execute(
        "ALTER TABLE trades ALTER COLUMN execution_environment "
        "TYPE execution_environment USING execution_environment::execution_environment"
    )
    op.execute("ALTER TABLE trades ALTER COLUMN execution_environment SET DEFAULT 'live'")

    # Step 5: Recreate views (same definitions as upgrade -- views are type-agnostic)
    op.execute(
        "CREATE OR REPLACE VIEW live_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'live'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW paper_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'paper'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW backtest_trades AS "
        "SELECT * FROM trades WHERE execution_environment = 'backtest'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW training_data_trades AS "
        "SELECT * FROM trades WHERE execution_environment IN ('paper', 'backtest')"
    )
    op.execute(
        "CREATE OR REPLACE VIEW live_positions AS "
        "SELECT * FROM positions WHERE execution_environment = 'live' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW paper_positions AS "
        "SELECT * FROM positions WHERE execution_environment = 'paper' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW backtest_positions AS "
        "SELECT * FROM positions "
        "WHERE execution_environment = 'backtest' AND row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW open_positions AS "
        "SELECT * FROM positions WHERE row_current_ind = TRUE AND status = 'open'"
    )
    op.execute(
        "CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW current_game_states AS "
        "SELECT * FROM game_states WHERE row_current_ind = TRUE"
    )
    op.execute("""
        CREATE OR REPLACE VIEW edge_lifecycle AS
        SELECT
            e.id,
            e.edge_id,
            e.market_internal_id,
            e.model_id,
            e.strategy_id,
            e.expected_value,
            e.true_win_probability,
            e.market_implied_probability,
            e.market_price,
            e.yes_ask_price,
            e.no_ask_price,
            e.edge_status,
            e.actual_outcome,
            e.settlement_value,
            e.confidence_level,
            e.execution_environment,
            e.created_at,
            e.resolved_at,
            CASE
                WHEN e.actual_outcome = 'yes' THEN e.settlement_value - e.market_price
                WHEN e.actual_outcome = 'no' THEN e.market_price - e.settlement_value
                ELSE NULL
            END AS realized_pnl,
            CASE
                WHEN e.resolved_at IS NOT NULL AND e.created_at IS NOT NULL
                THEN EXTRACT(EPOCH FROM (e.resolved_at - e.created_at)) / 3600.0
                ELSE NULL
            END AS hours_to_resolution
        FROM edges e
        WHERE e.row_current_ind = TRUE
    """)
