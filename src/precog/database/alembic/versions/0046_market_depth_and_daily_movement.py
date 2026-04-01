"""Add depth signals and daily price movement columns to markets schema.

Captures high-value Kalshi API fields that are currently returned but not
stored. These are prerequisites for future edge-detection models:

Dimension table (markets) -- per-market constants:
    - expiration_value: Settlement outcome description (e.g., "above 42.5")
    - notional_value: Dollar notional value of the contract

Fact table (market_snapshots) -- per-poll observations:
    - volume_24h: 24-hour trading volume in contracts
    - previous_yes_bid: Yesterday's YES bid price
    - previous_yes_ask: Yesterday's YES ask price
    - previous_price: Yesterday's last trade price
    - yes_bid_size: Size (depth) at best YES bid
    - yes_ask_size: Size (depth) at best YES ask

All columns are nullable -- existing rows won't have these values, and not
all API responses include them.

Steps:
    1. ADD columns to markets dimension table
    2. ADD columns to market_snapshots fact table
    3. DROP/RECREATE current_markets view to include new columns

Revision ID: 0046
Revises: 0045
Create Date: 2026-03-30

Related:
- Issue #513: Kalshi API enrichment (P1)
- Migration 0033: Market enrichment columns (predecessor)
- Migration 0037: Last view definition (subcategory rename)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0046"
down_revision: str = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add depth and daily movement columns to markets + market_snapshots.

    Educational Note:
        Dimension vs Fact placement:
        - expiration_value and notional_value are per-market constants that
          don't change between polls -> dimension table (markets).
        - volume_24h, previous_*, and *_size fields are per-poll observations
          that change over time -> fact table (market_snapshots).

        INTEGER vs DECIMAL:
        - volume_24h, yes_bid_size, yes_ask_size are contract counts -> INTEGER.
        - previous_* and notional_value are dollar prices -> DECIMAL(10,4).
    """
    # -- Step 1: Add dimension columns to markets table --
    #
    # expiration_value: free-text settlement outcome description from Kalshi API
    # (e.g., "above 42.5", "yes"). Not a price -- VARCHAR(100).
    op.execute("ALTER TABLE markets ADD COLUMN expiration_value VARCHAR(100)")

    # notional_value: dollar notional value of the contract. Decimal for
    # precision consistency with other price columns.
    op.execute("ALTER TABLE markets ADD COLUMN notional_value DECIMAL(10,4)")

    # -- Step 2: Add fact columns to market_snapshots table --
    #
    # Daily movement columns: yesterday's prices for computing daily deltas.
    # Already converted to Decimal by _convert_prices_to_decimal in the client.
    op.execute("ALTER TABLE market_snapshots ADD COLUMN volume_24h INTEGER")
    op.execute("ALTER TABLE market_snapshots ADD COLUMN previous_yes_bid DECIMAL(10,4)")
    op.execute("ALTER TABLE market_snapshots ADD COLUMN previous_yes_ask DECIMAL(10,4)")
    op.execute("ALTER TABLE market_snapshots ADD COLUMN previous_price DECIMAL(10,4)")

    # Depth signals: number of contracts at the best bid/ask.
    # These are integers (contract counts), not dollar values.
    op.execute("ALTER TABLE market_snapshots ADD COLUMN yes_bid_size INTEGER")
    op.execute("ALTER TABLE market_snapshots ADD COLUMN yes_ask_size INTEGER")

    # -- Step 3: Recreate current_markets view --
    #
    # Must include ALL new columns from both tables so downstream queries
    # (web GUI, analytics, strategy logic) see them without raw table joins.
    # View definition matches migration 0037 (last to touch this view) plus
    # the new columns from this migration.
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


def downgrade() -> None:
    """Remove depth and daily movement columns, restore previous view."""
    # -- Step 1: Restore current_markets view to pre-0046 definition --
    # (matches migration 0037 view definition)
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

    # -- Step 2: Drop fact columns from market_snapshots --
    op.execute("ALTER TABLE market_snapshots DROP COLUMN IF EXISTS volume_24h")
    op.execute("ALTER TABLE market_snapshots DROP COLUMN IF EXISTS previous_yes_bid")
    op.execute("ALTER TABLE market_snapshots DROP COLUMN IF EXISTS previous_yes_ask")
    op.execute("ALTER TABLE market_snapshots DROP COLUMN IF EXISTS previous_price")
    op.execute("ALTER TABLE market_snapshots DROP COLUMN IF EXISTS yes_bid_size")
    op.execute("ALTER TABLE market_snapshots DROP COLUMN IF EXISTS yes_ask_size")

    # -- Step 3: Drop dimension columns from markets --
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS expiration_value")
    op.execute("ALTER TABLE markets DROP COLUMN IF EXISTS notional_value")
