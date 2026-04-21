"""Fix edge_lifecycle view realized_pnl sign-inversion for actual_outcome='no'.

The ``edge_lifecycle`` view's ``realized_pnl`` computation was sign-inverted
on the ``'no'`` branch, reporting fake gains on lost YES-side positions.

Edges detect YES-side buy opportunities. For a YES-side position:
    - YES outcome: gain  = settlement_value (1.0) - market_price_paid
    - NO outcome:  loss  = settlement_value (0.0) - market_price_paid  (negative)

Both branches must use ``settlement_value - market_price``. The sign handles
the loss naturally (settlement_value=0 produces a negative P&L on NO).

This migration replaces the view via ``CREATE OR REPLACE VIEW`` (idempotent,
sub-millisecond catalog lock, no table locks, no data migration). The column
list, ordinal positions, and types are preserved verbatim — only the
expression inside the ``'no'`` CASE branch changes.

Downgrade restores the pre-0065 (broken) formula per Alembic's reversibility
contract. See #909 for context on why we preserve the broken form.

Revision ID: 0065
Revises: 0064
Create Date: 2026-04-20

Issues: #909
Design review: Holden (session 66) — ``memory/design_review_909_holden_memo.md``
Reference migration: 0058_business_key_fk_renames.py (column list)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0065"
down_revision: str = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fix the 'no' branch sign-inversion in edge_lifecycle.realized_pnl."""
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
            -- P&L assumes YES-side position (edge detection = buy YES).
            -- Both branches use (settlement_value - market_price); the sign
            -- handles the NO-loss case naturally (settlement_value=0 → -market_price).
            CASE
                WHEN e.actual_outcome = 'yes' THEN e.settlement_value - e.market_price
                WHEN e.actual_outcome = 'no'  THEN e.settlement_value - e.market_price  -- FIXED #909 (was: e.market_price - e.settlement_value)
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
    """Restore the pre-0065 (inverted) formula for Alembic reversibility.

    Intentionally restore the pre-0065 broken formula. See #909.

    The ``'no'`` branch inversion was a latent bug in migrations 0023, 0024,
    and 0058; this downgrade preserves the chain's historical state so that
    ``alembic downgrade -1`` from 0065 reproduces the schema state that 0064
    left behind. Consumers that rely on the correct formula must stay on
    revision 0065 or later.
    """
    # Intentionally restore the pre-0065 broken formula. See #909.
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
            CASE
                WHEN e.actual_outcome = 'yes' THEN e.settlement_value - e.market_price
                WHEN e.actual_outcome = 'no'  THEN e.market_price - e.settlement_value  -- INVERTED (pre-#909 state)
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
