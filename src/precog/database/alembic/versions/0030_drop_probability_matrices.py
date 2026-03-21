"""Drop dead table probability_matrices.

probability_matrices was created in the initial schema but never had CRUD code
written for it. It was superseded by probability_models. The FK from edges
(edges.probability_matrix_id) was already dropped in migration 0023
(edges_enrichment). No live code references this table.

Steps:
    1. DROP TABLE probability_matrices

Revision ID: 0030
Revises: 0028
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0030 spec
- Migration 0023: Dropped edges.probability_matrix_id FK
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: str = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the dead probability_matrices table."""
    op.execute("DROP TABLE IF EXISTS probability_matrices")


def downgrade() -> None:
    """Recreate probability_matrices table (original schema from migration 0001)."""
    op.execute("""
        CREATE TABLE probability_matrices (
            matrix_id SERIAL PRIMARY KEY,
            model_id INTEGER REFERENCES probability_models(model_id) ON DELETE CASCADE,
            market_id VARCHAR(100),
            event_id VARCHAR(100),
            matrix_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX idx_prob_matrix_model ON probability_matrices(model_id)")
    op.execute("CREATE INDEX idx_prob_matrix_market ON probability_matrices(market_id)")
