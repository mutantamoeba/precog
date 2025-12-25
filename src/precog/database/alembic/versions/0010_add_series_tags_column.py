"""
Add tags column to series table for sport identification.

Revision ID: 0010
Revises: 0009
Create Date: 2025-12-24

Purpose:
    Add a TEXT[] (array of strings) column to store series tags from Kalshi API.
    Tags are used to identify the sport type for a series:
    - ["Football"] -> NFL, NCAAF
    - ["Basketball"] -> NBA, NCAAB, NCAAW
    - ["Hockey"] -> NHL

    This enables proper sport filtering without relying solely on ticker prefix patterns.

Design Decisions:
    - TEXT[] array instead of JSONB for simpler querying with ANY() operator
    - Nullable since existing series records won't have tags initially
    - Index on tags using GIN for efficient array containment queries

Related:
    - Issue #271: Series data storage enhancement
    - KalshiClient.get_series() returns tags from API
    - KalshiClient.get_sports_series() uses tags for filtering

Educational Note:
    PostgreSQL arrays are ideal for simple lists of values where you need:
    - Fast containment checks: WHERE 'Football' = ANY(tags)
    - No complex nested structure (unlike JSONB)
    - Index support via GIN (Generalized Inverted Index)

    GIN indexes are optimized for "does this array contain X?" queries,
    making them perfect for tag-based filtering.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0010"
down_revision: str = "0009"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Add tags column to series table."""
    # Add tags column as TEXT array (nullable for existing records)
    op.add_column(
        "series",
        sa.Column(
            "tags",
            sa.ARRAY(sa.Text()),
            nullable=True,
            comment="Array of tags from Kalshi API (e.g., ['Football'], ['Basketball'])",
        ),
    )

    # Create GIN index for efficient array containment queries
    # Example query: SELECT * FROM series WHERE 'Football' = ANY(tags)
    op.create_index(
        "idx_series_tags",
        "series",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove tags column from series table."""
    op.drop_index("idx_series_tags", table_name="series")
    op.drop_column("series", "tags")
