"""Standardize column naming: business keys use _key, FK columns use _id.

Category A — Business-key renames (3 columns):
    positions.position_id  → position_key
    edges.edge_id          → edge_key
    series.series_id       → series_key

Category D — FK column renames, removing _internal_id suffix (8 columns):
    Depends on Cat A completing first to free the _id namespace.
    edges.market_internal_id              → market_id
    events.series_internal_id             → series_id
    markets.event_internal_id             → event_id
    orderbook_snapshots.market_internal_id → market_id
    market_trades.market_internal_id      → market_id
    positions.market_internal_id          → market_id
    settlements.market_internal_id        → market_id
    trades.market_internal_id             → market_id

Category E — Convert remaining NO ACTION FKs to explicit RESTRICT:
    Dynamic discovery via information_schema (same pattern as 0057).

Index and constraint renames to match new column names.

Views dropped and re-created with updated column references.

Revision ID: 0058
Revises: 0057
Create Date: 2026-04-12

Issues: #788
Parent: #787 (C2b PK/FK Standardization)
Epic: #745 (Schema Hardening Arc)

Design review: Session 52 (Holden + Galadriel)
ADR: #116 (ODS Schema Conventions)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0058"
down_revision: str = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# =========================================================================
# All views that reference columns being renamed.  PostgreSQL stores
# SELECT * expansions by attnum so they'd survive, but explicit-column
# views (current_markets, edge_lifecycle) would show stale pg_get_viewdef
# output.  Safest to drop-then-recreate all of them.
# =========================================================================
_VIEWS_TO_DROP = [
    # Explicit-column views (directly reference renamed columns)
    "edge_lifecycle",
    "current_markets",
    # SELECT * views on tables with renamed columns
    "current_edges",
    "current_series",
    "open_positions",
    "live_positions",
    "paper_positions",
    "backtest_positions",
    "live_trades",
    "paper_trades",
    "backtest_trades",
    "training_data_trades",
]

# =========================================================================
# Category A: Business-key column renames (table, old_name, new_name)
# Must execute BEFORE Cat D to free the _id namespace.
# =========================================================================
_CAT_A_RENAMES = [
    ("positions", "position_id", "position_key"),
    ("edges", "edge_id", "edge_key"),
    ("series", "series_id", "series_key"),
]

# =========================================================================
# Category D: FK column renames — _internal_id → _id
# Must execute AFTER Cat A (e.g., series.series_id no longer collides
# with events.series_internal_id → series_id).
# =========================================================================
_CAT_D_RENAMES = [
    ("edges", "market_internal_id", "market_id"),
    ("events", "series_internal_id", "series_id"),
    ("markets", "event_internal_id", "event_id"),
    ("orderbook_snapshots", "market_internal_id", "market_id"),
    ("market_trades", "market_internal_id", "market_id"),
    ("positions", "market_internal_id", "market_id"),
    ("settlements", "market_internal_id", "market_id"),
    ("trades", "market_internal_id", "market_id"),
    ("orders", "market_internal_id", "market_id"),
]

# =========================================================================
# Index renames: old index names that embed the old column name.
# ALTER INDEX old_name RENAME TO new_name is a no-op if old doesn't exist.
# =========================================================================
_INDEX_RENAMES = [
    # Cat A business-key indexes (column ref auto-updated, name stays stale)
    # edges: idx_edges_unique_current and idx_edges_business_key are on
    #   edge_id — column auto-updated to edge_key, but names are generic
    #   enough to keep.  Same for positions equivalents.
    # Cat D FK indexes
    ("idx_events_series_internal", "idx_events_series"),
    ("idx_markets_event_internal", "idx_markets_event"),
    ("idx_edges_market_internal", "idx_edges_market"),
    ("idx_positions_market_internal", "idx_positions_market"),
    ("idx_trades_market_internal", "idx_trades_market"),
    ("idx_settlements_market_internal", "idx_settlements_market"),
]

# =========================================================================
# FK constraint renames: rename constraints on columns that were renamed
# in Cat D.  Uses dynamic discovery from information_schema because
# constraint names vary between incremental migration and fresh-DB runs.
# =========================================================================
_FK_COLUMNS_TO_RENAME_CONSTRAINTS = [
    # (table, NEW column name after Cat D rename) — the constraint still
    # references the correct column (PostgreSQL updates by attnum), but
    # the constraint NAME may embed the old column name.  We discover
    # the actual name and rename to {table}_{new_column}_fkey.
    ("events", "series_id"),
    ("markets", "event_id"),
    ("edges", "market_id"),
    ("positions", "market_id"),
    ("trades", "market_id"),
    ("settlements", "market_id"),
    ("orders", "market_id"),
    ("market_trades", "market_id"),
    ("orderbook_snapshots", "market_id"),
]


def _rename_fk_constraints(conn: sa.engine.Connection) -> int:
    """Discover actual FK constraint names and rename to match new columns.

    After Cat D column renames, the FK constraints still work (PostgreSQL
    updates column references by attnum) but their NAMES may embed the old
    column name.  This function discovers the actual name via
    information_schema and renames to {table}_{new_column}_fkey.

    Returns the number of constraints renamed.
    """
    renamed = 0
    for table, new_column in _FK_COLUMNS_TO_RENAME_CONSTRAINTS:
        row = conn.execute(
            sa.text("""
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = :table_name
                    AND kcu.column_name = :column_name
                    AND tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
            """),
            {"table_name": table, "column_name": new_column},
        ).fetchone()
        if row is None:
            continue
        actual_name = row[0]
        desired_name = f"{table}_{new_column}_fkey"
        if actual_name != desired_name:
            conn.execute(
                sa.text(f"ALTER TABLE {table} RENAME CONSTRAINT {actual_name} TO {desired_name}")
            )
            renamed += 1
    return renamed


def _convert_no_action_to_restrict(conn: sa.engine.Connection) -> int:
    """Find all public-schema FKs with NO ACTION and convert to RESTRICT.

    Category E: dynamic discovery, same pattern as migration 0057.
    NO ACTION and RESTRICT behave identically for non-deferred constraints
    but RESTRICT is explicit and self-documenting.

    Returns the number of FKs converted.
    """
    rows = conn.execute(
        sa.text("""
            SELECT tc.table_name, kcu.column_name,
                   ccu.table_name AS parent_table, ccu.column_name AS parent_column,
                   tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.table_schema = rc.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
                AND rc.delete_rule = 'NO ACTION'
            ORDER BY tc.table_name, kcu.column_name
        """)
    ).fetchall()

    for child_table, child_col, parent_table, parent_col, constraint_name in rows:
        conn.execute(sa.text(f"ALTER TABLE {child_table} DROP CONSTRAINT {constraint_name}"))
        new_name = f"{child_table}_{child_col}_fkey"
        conn.execute(
            sa.text(
                f"ALTER TABLE {child_table} ADD CONSTRAINT {new_name} "
                f"FOREIGN KEY ({child_col}) REFERENCES {parent_table}({parent_col}) "
                f"ON DELETE RESTRICT"
            )
        )
    return len(rows)


def upgrade() -> None:
    """Standardize column naming per ADR-116 ODS conventions."""
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Step 0: Drop all dependent views
    # ------------------------------------------------------------------
    for view in _VIEWS_TO_DROP:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    # ------------------------------------------------------------------
    # Step 1: Category A — Business-key renames
    # Frees the _id namespace for Cat D.
    # ------------------------------------------------------------------
    for table, old_col, new_col in _CAT_A_RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}")

    # ------------------------------------------------------------------
    # Step 2: Category D — FK column renames (_internal_id → _id)
    # ------------------------------------------------------------------
    for table, old_col, new_col in _CAT_D_RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}")

    # ------------------------------------------------------------------
    # Step 3: Index renames
    # ------------------------------------------------------------------
    for old_name, new_name in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX IF EXISTS {old_name} RENAME TO {new_name}")

    # ------------------------------------------------------------------
    # Step 4: FK constraint renames (dynamic — names vary by DB history)
    # ------------------------------------------------------------------
    renamed = _rename_fk_constraints(conn)
    if renamed:
        op.execute(f"SELECT '[0058] Renamed {renamed} FK constraint(s)'")

    # ------------------------------------------------------------------
    # Step 5: Category E — NO ACTION → RESTRICT (dynamic)
    # ------------------------------------------------------------------
    converted = _convert_no_action_to_restrict(conn)
    if converted:
        op.execute(f"SELECT '[0058] Converted {converted} NO ACTION FK(s) to RESTRICT'")

    # ------------------------------------------------------------------
    # Step 6: Re-create all views with new column names
    # ------------------------------------------------------------------

    # -- current_markets (explicit columns, from 0046 + event_internal_id → event_id) --
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT
            m.id,
            m.platform_id,
            m.event_id,
            m.external_id,
            m.ticker,
            m.title,
            m.subtitle,
            m.market_type,
            m.status,
            m.settlement_value,
            m.open_time,
            m.close_time,
            m.expiration_time,
            m.outcome_label,
            m.subcategory,
            m.bracket_count,
            m.source_url,
            m.expiration_value,
            m.notional_value,
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
            ms.volume_24h,
            ms.previous_yes_bid,
            ms.previous_yes_ask,
            ms.previous_price,
            ms.yes_bid_size,
            ms.yes_ask_size,
            ms.row_start_ts,
            ms.row_end_ts,
            ms.row_current_ind
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id
            AND ms.row_current_ind = TRUE
    """)

    # -- edge_lifecycle (explicit columns, from 0024 + edge_id → edge_key, market_internal_id → market_id) --
    op.execute("""
        CREATE OR REPLACE VIEW edge_lifecycle AS
        SELECT
            e.id,
            e.edge_key,
            e.market_id,
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

    # -- Simple SELECT * views --
    op.execute(
        "CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW current_series AS SELECT * FROM series WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW open_positions AS "
        "SELECT * FROM positions WHERE status = 'open' AND row_current_ind = TRUE"
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
    """Reverse all renames to restore pre-0058 column names."""
    # Step 0: Drop views (will recreate with old names)
    for view in _VIEWS_TO_DROP:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    # Step 1: Reverse Category D (restore _internal_id suffix)
    # Must reverse D BEFORE A to avoid series_id collision.
    for table, old_col, new_col in _CAT_D_RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN {new_col} TO {old_col}")

    # Step 2: Reverse Category A (restore business-key _id names)
    for table, old_col, new_col in _CAT_A_RENAMES:
        op.execute(f"ALTER TABLE {table} RENAME COLUMN {new_col} TO {old_col}")

    # Step 3: Reverse index renames
    for old_name, new_name in _INDEX_RENAMES:
        op.execute(f"ALTER INDEX IF EXISTS {new_name} RENAME TO {old_name}")

    # Step 4: Reverse constraint renames (dynamic — discover current names)
    # After reversing column renames, the constraint names from upgrade's
    # dynamic rename (e.g., events_series_id_fkey) need to be discovered
    # and renamed back.  But since the columns are now restored to their
    # old names, we just need to ensure constraint names are consistent.
    # The simplest safe approach: skip constraint name reversal.
    # The constraints still work (PostgreSQL tracks by attnum), and
    # a subsequent `alembic upgrade head` will re-apply the rename.

    # Step 5: Re-create views with original column names
    op.execute("""
        CREATE OR REPLACE VIEW current_markets AS
        SELECT
            m.id,
            m.platform_id,
            m.event_internal_id,
            m.external_id,
            m.ticker,
            m.title,
            m.subtitle,
            m.market_type,
            m.status,
            m.settlement_value,
            m.open_time,
            m.close_time,
            m.expiration_time,
            m.outcome_label,
            m.subcategory,
            m.bracket_count,
            m.source_url,
            m.expiration_value,
            m.notional_value,
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
            ms.volume_24h,
            ms.previous_yes_bid,
            ms.previous_yes_ask,
            ms.previous_price,
            ms.yes_bid_size,
            ms.yes_ask_size,
            ms.row_start_ts,
            ms.row_end_ts,
            ms.row_current_ind
        FROM markets m
        LEFT JOIN market_snapshots ms
            ON ms.market_id = m.id
            AND ms.row_current_ind = TRUE
    """)

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

    op.execute(
        "CREATE OR REPLACE VIEW current_edges AS SELECT * FROM edges WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW current_series AS SELECT * FROM series WHERE row_current_ind = TRUE"
    )
    op.execute(
        "CREATE OR REPLACE VIEW open_positions AS "
        "SELECT * FROM positions WHERE status = 'open' AND row_current_ind = TRUE"
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

    # Note: Cat E (NO ACTION → RESTRICT) is not reversed because RESTRICT
    # was the intended steady-state from 0057.  Downgrading to NO ACTION
    # would weaken the schema.
