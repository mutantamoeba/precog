"""Rename markets.league to markets.subcategory for naming consistency.

The markets.league column stores the Kalshi API subcategory value (e.g., "nfl",
"nba"). This is the same concept as events.subcategory. Renaming makes the
semantic relationship explicit and eliminates the confusing terminology overlap
with game_states.league / teams.league (which are different: they store the
league on the games side of the schema).

Naming convention after this migration:
- Markets side: subcategory (Kalshi's term, e.g., "nfl")
- Games side: league (ESPN's term, e.g., "nfl") + sport (e.g., "football")

Steps:
    1. RENAME COLUMN markets.league -> subcategory
    2. RENAME INDEX idx_markets_league -> idx_markets_subcategory
    3. RECREATE current_markets view with new column name

Revision ID: 0037
Revises: 0036
Create Date: 2026-03-22

Related:
- Issue #460: Category/subcategory naming consistency
- Migration 0033: Original column creation (as 'league')
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0037"
down_revision: str = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename markets.league to markets.subcategory."""
    # -- Step 1: Rename column --
    op.execute("ALTER TABLE markets RENAME COLUMN league TO subcategory")

    # -- Step 2: Rename index --
    op.execute("ALTER INDEX idx_markets_league RENAME TO idx_markets_subcategory")

    # -- Step 3: Recreate current_markets view --
    # Must reflect the renamed column. View definition matches migration 0036
    # (which was the last to touch this view), with league -> subcategory.
    op.execute("DROP VIEW IF EXISTS current_markets")
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
    """Revert: rename markets.subcategory back to markets.league."""
    # -- Step 1: Rename column back --
    op.execute("ALTER TABLE markets RENAME COLUMN subcategory TO league")

    # -- Step 2: Rename index back --
    op.execute("ALTER INDEX idx_markets_subcategory RENAME TO idx_markets_league")

    # -- Step 3: Recreate current_markets view --
    op.execute("DROP VIEW IF EXISTS current_markets")
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
            m.league,
            m.bracket_count,
            m.source_url,
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
