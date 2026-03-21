"""Replace market_id VARCHAR with market_internal_id INTEGER FK on downstream tables.

Completes the markets surrogate PK migration started in 0021. Four downstream
tables (edges, positions, trades, settlements) currently JOIN to markets via
a denormalized market_id VARCHAR(100) column containing derived strings like
"MKT-{ticker}". This migration replaces that with a proper INTEGER FK
referencing markets(id).

Also drops the transitional market_id VARCHAR column from the markets
dimension table itself (no longer needed once downstream tables use integer FKs).

Changes per table (edges, positions, trades, settlements):
  1. Add market_internal_id INTEGER column
  2. Backfill from markets.id via JOIN on market_id VARCHAR
  3. Add FK constraint to markets(id)
  4. Create index on market_internal_id
  5. Drop old market_id VARCHAR column + index

Changes to markets dimension:
  6. Drop market_id VARCHAR column (transitional, no longer needed)
  7. Drop index on market_id

This is a CLEAN DB migration — no production data to preserve.

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-20

Related:
- Issue #366: FK integrity
- migration_batch_plan_v1.md: Migration 0022 spec
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that have market_id VARCHAR to replace
DOWNSTREAM_TABLES = ["edges", "positions", "trades", "settlements"]


def upgrade() -> None:
    """Replace market_id VARCHAR with market_internal_id INTEGER FK.

    Steps per downstream table:
    1. Add market_internal_id INTEGER column
    2. Backfill from markets via JOIN on market_id
    3. Add FK constraint
    4. Create index
    5. Drop old market_id column + index

    Then drop market_id from markets dimension table.
    """
    # Table names come from DOWNSTREAM_TABLES constant — not user input.
    for table in DOWNSTREAM_TABLES:
        # Step 1: Add INTEGER column
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS market_internal_id INTEGER")

        # Step 2: Backfill from markets via JOIN on old VARCHAR
        backfill_sql = (
            f"UPDATE {table} t SET market_internal_id = m.id "  # noqa: S608
            f"FROM markets m WHERE t.market_id = m.market_id AND t.market_internal_id IS NULL"
        )
        op.execute(backfill_sql)

        # Step 2b: Set NOT NULL after backfill (clean DB — all rows should be populated)
        op.execute(f"ALTER TABLE {table} ALTER COLUMN market_internal_id SET NOT NULL")

        # Step 3: Add FK constraint
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_market_internal_id_fkey "
            f"FOREIGN KEY (market_internal_id) REFERENCES markets(id) ON DELETE CASCADE"
        )

        # Step 4: Create index
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_market_internal ON {table}(market_internal_id)"
        )

        # Step 5: Drop ALL dependent views before column drop
        # (Pattern 38 / feedback_migration_dependencies: SELECT * views bind to columns
        # at creation time — dropping a referenced column fails with DependentObjectsStillExist)
        dependent_views: dict[str, list[str]] = {
            "edges": ["current_edges"],
            "positions": [
                "open_positions",
                "live_positions",
                "paper_positions",
                "backtest_positions",
            ],
            "trades": [
                "live_trades",
                "paper_trades",
                "backtest_trades",
                "training_data_trades",
            ],
        }
        for view in dependent_views.get(table, []):
            op.execute(f"DROP VIEW IF EXISTS {view}")

        # Step 6: Drop old market_id VARCHAR column + index
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_market")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS market_id")

        # Step 7: Recreate views with new column names
        for view in dependent_views.get(table, []):
            if view == "current_edges":
                op.execute(
                    "CREATE OR REPLACE VIEW current_edges AS "
                    "SELECT * FROM edges WHERE row_current_ind = TRUE"
                )
            elif view == "open_positions":
                op.execute(
                    "CREATE OR REPLACE VIEW open_positions AS "
                    "SELECT * FROM positions WHERE row_current_ind = TRUE AND status = 'open'"
                )
            elif view.endswith("_positions"):
                # live_positions, paper_positions, backtest_positions
                env = view.replace("_positions", "")
                op.execute(
                    f"CREATE OR REPLACE VIEW {view} AS "  # noqa: S608
                    f"SELECT * FROM positions WHERE execution_environment = '{env}'"
                )
            elif view == "training_data_trades":
                op.execute(
                    "CREATE OR REPLACE VIEW training_data_trades AS "
                    "SELECT * FROM trades WHERE execution_environment IN ('live', 'paper')"
                )
            elif view.endswith("_trades"):
                # live_trades, paper_trades, backtest_trades
                env = view.replace("_trades", "")
                op.execute(
                    f"CREATE OR REPLACE VIEW {view} AS "  # noqa: S608
                    f"SELECT * FROM trades WHERE execution_environment = '{env}'"
                )

    # Step 8: Drop current_markets view BEFORE dropping markets.market_id
    # (Pattern 38: views bind to columns at creation time)
    op.execute("DROP VIEW IF EXISTS current_markets")

    # Step 9: Drop transitional market_id from markets dimension
    op.execute("DROP INDEX IF EXISTS idx_markets_market_id")
    op.execute("""
        ALTER TABLE markets
        DROP COLUMN IF EXISTS market_id
    """)
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT
            m.id,
            m.platform_id,
            m.event_internal_id,
            m.external_id,
            m.ticker,
            m.title,
            m.market_type,
            m.status,
            m.settlement_value,
            m.metadata,
            m.created_at,
            m.updated_at,
            ms.yes_ask_price,
            ms.no_ask_price,
            ms.yes_bid_price,
            ms.no_bid_price,
            ms.last_price,
            ms.spread,
            ms.volume,
            ms.open_interest,
            ms.liquidity,
            ms.row_start_ts,
            ms.row_end_ts,
            ms.row_current_ind
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id
            AND ms.row_current_ind = TRUE
    """)


def downgrade() -> None:
    """Reverse: re-add market_id VARCHAR columns."""
    raise NotImplementedError(
        "Full downgrade not implemented for clean-DB migration. Re-run from baseline if needed."
    )
