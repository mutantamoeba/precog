"""Create orders table with attribution, simplify trades table.

Orders capture the trading DECISION (what was requested, why, by which strategy/model).
Trades capture execution EVENTS (what actually happened at the exchange). This clean
separation eliminates attribution duplication and absorbs the planned portfolio_fills
table (migration 0029 is now eliminated -- trades IS the fills table).

Steps:
    1. Drop dependent views on trades (Pattern 38)
    2. CREATE TABLE orders with attribution, pricing, lifecycle columns
    3. Add indexes on orders
    4. Drop redundant columns from trades (attribution now on orders)
    5. Add new columns to trades (order_id FK, is_taker)
    6. Drop stale trades indexes for dropped columns
    7. Recreate trade views with updated column set

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0025 spec
- ADR-002: Decimal Precision for All Financial Data
- issue336_council_findings.md: UNANIMOUS Option 2 (separate orders table)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create orders table, drop redundant trade columns, add order FK to trades.

    Pattern 38 applied: Drop all views that reference trades before altering
    columns, then recreate afterward. PostgreSQL views with SELECT * cache
    column definitions at creation time -- column additions/removals silently
    produce wrong results unless views are dropped and recreated.

    Design intent:
        - Orders own attribution (strategy, model, edge, position)
        - Trades are pure fill/execution records linked via orders(id) FK
        - portfolio_fills (migration 0029) is ELIMINATED -- trades IS fills
    """
    # ------------------------------------------------------------------
    # Step 1: Drop ALL dependent views on trades (Pattern 38)
    # ------------------------------------------------------------------
    op.execute("DROP VIEW IF EXISTS live_trades")
    op.execute("DROP VIEW IF EXISTS paper_trades")
    op.execute("DROP VIEW IF EXISTS backtest_trades")
    op.execute("DROP VIEW IF EXISTS training_data_trades")

    # ------------------------------------------------------------------
    # Step 2: CREATE TABLE orders
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE orders (
            id SERIAL PRIMARY KEY,

            -- Platform + external identity
            platform_id VARCHAR(50) NOT NULL
                REFERENCES platforms(platform_id) ON DELETE CASCADE,
            external_order_id VARCHAR(100) NOT NULL,
            client_order_id VARCHAR(100),

            -- Market reference
            market_internal_id INTEGER NOT NULL
                REFERENCES markets(id) ON DELETE CASCADE,

            -- Attribution (the decision context -- lives HERE, not on trades)
            strategy_id INTEGER REFERENCES strategies(strategy_id) ON DELETE SET NULL,
            model_id INTEGER REFERENCES probability_models(model_id) ON DELETE SET NULL,
            edge_id INTEGER REFERENCES edges(id) ON DELETE SET NULL,
            position_id INTEGER REFERENCES positions(id) ON DELETE SET NULL,

            -- Order intent
            side VARCHAR(10) NOT NULL CHECK (side IN ('yes', 'no')),
            action VARCHAR(10) NOT NULL CHECK (action IN ('buy', 'sell')),
            order_type VARCHAR(20) NOT NULL DEFAULT 'market'
                CHECK (order_type IN ('market', 'limit')),
            time_in_force VARCHAR(30) DEFAULT 'good_till_canceled'
                CHECK (time_in_force IN (
                    'fill_or_kill', 'good_till_canceled', 'immediate_or_cancel'
                )),

            -- Pricing
            requested_price DECIMAL(10,4) NOT NULL
                CHECK (requested_price >= 0.0000 AND requested_price <= 1.0000),
            requested_quantity INTEGER NOT NULL CHECK (requested_quantity > 0),

            -- Fill tracking (mutable)
            filled_quantity INTEGER NOT NULL DEFAULT 0 CHECK (filled_quantity >= 0),
            remaining_quantity INTEGER NOT NULL CHECK (remaining_quantity >= 0),
            average_fill_price DECIMAL(10,4),
            total_fees DECIMAL(10,4) DEFAULT 0.0000,

            -- Lifecycle status (mutable)
            status VARCHAR(20) NOT NULL DEFAULT 'submitted'
                CHECK (status IN (
                    'submitted', 'resting', 'pending',
                    'partial_fill', 'filled',
                    'cancelled', 'expired'
                )),

            -- Execution context
            execution_environment VARCHAR(20) NOT NULL DEFAULT 'live'
                CHECK (execution_environment IN ('live', 'paper', 'backtest')),
            trade_source VARCHAR(20) NOT NULL DEFAULT 'automated'
                CHECK (trade_source IN ('automated', 'manual')),

            -- Metadata
            order_metadata JSONB,

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            submitted_at TIMESTAMP WITH TIME ZONE,
            filled_at TIMESTAMP WITH TIME ZONE,
            cancelled_at TIMESTAMP WITH TIME ZONE,

            CONSTRAINT uq_orders_platform_external
                UNIQUE (platform_id, external_order_id)
        )
    """)

    # ------------------------------------------------------------------
    # Step 3: Add indexes on orders
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX idx_orders_market ON orders(market_internal_id)")
    op.execute("CREATE INDEX idx_orders_strategy ON orders(strategy_id)")
    op.execute(
        "CREATE INDEX idx_orders_status ON orders(status) "
        "WHERE status IN ('submitted', 'resting', 'pending', 'partial_fill')"
    )
    op.execute("CREATE INDEX idx_orders_exec_env ON orders(execution_environment)")
    op.execute("CREATE INDEX idx_orders_created ON orders(created_at)")

    # ------------------------------------------------------------------
    # Step 4: Drop redundant columns from trades
    # Attribution now lives on orders; old VARCHAR order refs replaced by
    # integer FK. Clean DB = no data loss.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS order_id")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS external_order_id")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS strategy_id")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS model_id")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS edge_internal_id")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS position_internal_id")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS order_type")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS trade_source")

    # ------------------------------------------------------------------
    # Step 5: Add new columns to trades
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE trades ADD COLUMN order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE trades ADD COLUMN is_taker BOOLEAN")
    op.execute("CREATE INDEX idx_trades_order ON trades(order_id)")

    # ------------------------------------------------------------------
    # Step 6: Drop stale trades indexes for dropped columns
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS idx_trades_source")

    # ------------------------------------------------------------------
    # Step 7: Recreate trade views with updated column set
    # ------------------------------------------------------------------
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


def downgrade() -> None:
    """Reverse: drop order FK from trades, re-add dropped columns, drop orders table."""
    # Step 1: Drop trade views (column set is changing)
    op.execute("DROP VIEW IF EXISTS live_trades")
    op.execute("DROP VIEW IF EXISTS paper_trades")
    op.execute("DROP VIEW IF EXISTS backtest_trades")
    op.execute("DROP VIEW IF EXISTS training_data_trades")

    # Step 2: Drop new columns/indexes from trades
    op.execute("DROP INDEX IF EXISTS idx_trades_order")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS is_taker")
    op.execute("ALTER TABLE trades DROP COLUMN IF EXISTS order_id")

    # Step 3: Re-add dropped columns to trades
    op.execute("ALTER TABLE trades ADD COLUMN order_id VARCHAR(100)")
    op.execute("ALTER TABLE trades ADD COLUMN external_order_id VARCHAR(100)")
    op.execute(
        "ALTER TABLE trades ADD COLUMN strategy_id INTEGER REFERENCES strategies(strategy_id)"
    )
    op.execute(
        "ALTER TABLE trades ADD COLUMN model_id INTEGER REFERENCES probability_models(model_id)"
    )
    op.execute(
        "ALTER TABLE trades ADD COLUMN edge_internal_id INTEGER "
        "REFERENCES edges(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE trades ADD COLUMN position_internal_id INTEGER "
        "REFERENCES positions(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE trades ADD COLUMN order_type VARCHAR(20) DEFAULT 'market' "
        "CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit'))"
    )
    op.execute(
        "ALTER TABLE trades ADD COLUMN trade_source VARCHAR(20) DEFAULT 'automated' "
        "CHECK (trade_source IN ('automated', 'manual'))"
    )

    # Step 4: Re-add dropped indexes
    op.execute("CREATE INDEX idx_trades_source ON trades(trade_source)")

    # Step 5: Drop orders indexes and table
    op.execute("DROP INDEX IF EXISTS idx_orders_created")
    op.execute("DROP INDEX IF EXISTS idx_orders_exec_env")
    op.execute("DROP INDEX IF EXISTS idx_orders_status")
    op.execute("DROP INDEX IF EXISTS idx_orders_strategy")
    op.execute("DROP INDEX IF EXISTS idx_orders_market")
    op.execute("DROP TABLE IF EXISTS orders")

    # Step 6: Recreate trade views with restored columns
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
