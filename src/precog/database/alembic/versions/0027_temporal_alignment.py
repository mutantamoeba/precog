"""Create temporal_alignment table linking market snapshots to game states.

Kalshi polls every 15s, ESPN every 30s. There is no cross-reference between
price updates and game state updates. The temporal_alignment table links a
specific market_snapshot row to a specific game_state row by timestamp
proximity, enabling queries like "what was the market price when the score
changed?" Critical for Phase 4 backtesting accuracy.

Steps:
    1. CREATE TABLE temporal_alignment with FKs, alignment metadata, denormalized fields
    2. Add indexes for common query patterns

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-21

Related:
- migration_batch_plan_v1.md: Migration 0027 spec
- Issue #375: Add temporal alignment table linking Kalshi polls to ESPN game states
- ADR-002: Decimal Precision for All Financial Data
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: str = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create temporal_alignment table for cross-source timestamp linking.

    Design intent:
        - Links a SPECIFIC market_snapshot to a SPECIFIC game_state by time proximity
        - Denormalizes key fields for query convenience (avoids joins for common reads)
        - alignment_quality categorizes time delta: exact/good/fair/poor/stale
        - Unique constraint prevents duplicate snapshot-to-game-state pairings
        - Append-only: rows are never updated once created
    """
    # ------------------------------------------------------------------
    # Step 1: CREATE TABLE temporal_alignment
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE temporal_alignment (
            id SERIAL PRIMARY KEY,

            -- Market reference
            market_id INTEGER NOT NULL
                REFERENCES markets(id) ON DELETE CASCADE,
            market_snapshot_id INTEGER NOT NULL
                REFERENCES market_snapshots(id) ON DELETE CASCADE,

            -- Game state reference
            game_state_id INTEGER NOT NULL
                REFERENCES game_states(id) ON DELETE CASCADE,

            -- Alignment metadata
            snapshot_time TIMESTAMP WITH TIME ZONE NOT NULL,
            game_state_time TIMESTAMP WITH TIME ZONE NOT NULL,
            time_delta_seconds DECIMAL(10,2) NOT NULL,
            alignment_quality VARCHAR(20) NOT NULL DEFAULT 'good'
                CHECK (alignment_quality IN ('exact', 'good', 'fair', 'poor', 'stale')),

            -- Denormalized snapshot values for query convenience
            yes_ask_price DECIMAL(10,4),
            no_ask_price DECIMAL(10,4),
            spread DECIMAL(10,4),
            volume INTEGER,

            -- Denormalized game state values
            game_status VARCHAR(50),
            home_score INTEGER,
            away_score INTEGER,
            period VARCHAR(20),
            clock VARCHAR(20),

            -- Audit
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

            -- Prevent duplicate alignments
            CONSTRAINT uq_alignment_snapshot_game
                UNIQUE (market_snapshot_id, game_state_id)
        )
    """)

    # ------------------------------------------------------------------
    # Step 2: Add indexes for common query patterns
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX idx_alignment_market ON temporal_alignment(market_id)")
    op.execute(
        "CREATE INDEX idx_alignment_market_time ON temporal_alignment(market_id, snapshot_time DESC)"
    )
    op.execute(
        "CREATE INDEX idx_alignment_quality ON temporal_alignment(alignment_quality) "
        "WHERE alignment_quality IN ('poor', 'stale')"
    )
    op.execute("CREATE INDEX idx_alignment_game_state ON temporal_alignment(game_state_id)")


def downgrade() -> None:
    """Reverse: drop indexes and temporal_alignment table."""
    # Step 1: Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_alignment_game_state")
    op.execute("DROP INDEX IF EXISTS idx_alignment_quality")
    op.execute("DROP INDEX IF EXISTS idx_alignment_market_time")
    op.execute("DROP INDEX IF EXISTS idx_alignment_market")

    # Step 2: Drop table
    op.execute("DROP TABLE IF EXISTS temporal_alignment")
