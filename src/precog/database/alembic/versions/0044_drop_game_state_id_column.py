"""Drop redundant game_state_id VARCHAR(50) column from game_states table.

The game_state_id column always contains "GS-{id}" — a value trivially
derivable from the integer PK. Every INSERT required two extra SQL
statements (INSERT with 'TEMP' placeholder + UPDATE to set 'GS-{id}'),
adding latency and complexity for zero informational value.

The C10 Post-Soak Council's Armitage agent REFUSED sign-off until this
redundancy was removed.

Dependencies handled:
    1. DROP VIEW current_game_states (uses SELECT * — would break if column
       removed while view exists)
    2. DROP INDEX idx_game_states_business_key (indexes the dropped column)
    3. ALTER TABLE DROP COLUMN game_state_id
    4. Recreate VIEW current_game_states (now without game_state_id)

Note: temporal_alignment.game_state_id (INTEGER FK to game_states.id) and
elo_calculation_log.game_state_id (INTEGER FK to game_states.id) are
DIFFERENT columns — they reference the PK, not this VARCHAR column.
They are NOT affected by this migration.

Revision ID: 0044
Revises: 0043
Create Date: 2026-03-28

Related:
    - C10 Post-Soak Council: Armitage REFUSED sign-off on game_state_id redundancy
    - Migration 0001: Original game_states table schema (created game_state_id)
    - Pattern 38: 5 dependency classes (view + index dependencies)
    - ADR-029: ESPN Data Model with Normalized Schema
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0044"
down_revision: str = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the game_state_id VARCHAR(50) column and its dependencies.

    Order matters:
        1. Drop the current_game_states VIEW (SELECT * would break)
        2. Drop the idx_game_states_business_key INDEX
        3. Drop the game_state_id column
        4. Recreate the VIEW without game_state_id

    Educational Note:
        PostgreSQL views created with SELECT * capture the column list at
        creation time. Dropping a column from the underlying table while
        the view exists raises an error. We must DROP + recreate the view.

        IF EXISTS / IF NOT EXISTS make this migration idempotent — safe
        to re-run if partially applied.
    """
    # Step 1: Drop the view that uses SELECT * on game_states
    op.execute("DROP VIEW IF EXISTS current_game_states")

    # Step 2: Drop the index on game_state_id
    op.execute("DROP INDEX IF EXISTS idx_game_states_business_key")

    # Step 3: Drop the column
    op.execute("ALTER TABLE game_states DROP COLUMN IF EXISTS game_state_id")

    # Step 4: Recreate the view (now without game_state_id in the column list)
    op.execute(
        "CREATE OR REPLACE VIEW current_game_states AS "
        "SELECT * FROM game_states WHERE row_current_ind = TRUE"
    )


def downgrade() -> None:
    """Re-add the game_state_id column and its dependencies.

    WARNING: Existing rows will have NULL game_state_id values after
    downgrade. The UPDATE sets them to 'GS-{id}' format to match the
    original convention. This may take time on large tables.
    """
    # Step 1: Drop the view (will be recreated with the restored column)
    op.execute("DROP VIEW IF EXISTS current_game_states")

    # Step 2: Add the column back (nullable initially to allow backfill)
    op.execute("ALTER TABLE game_states ADD COLUMN IF NOT EXISTS game_state_id VARCHAR(50)")

    # Step 3: Backfill existing rows with GS-{id} format
    op.execute("UPDATE game_states SET game_state_id = 'GS-' || id::text")

    # Step 4: Set NOT NULL after backfill
    op.execute("ALTER TABLE game_states ALTER COLUMN game_state_id SET NOT NULL")

    # Step 5: Recreate the business key index
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_states_business_key ON game_states(game_state_id)"
    )

    # Step 6: Recreate the view (now including game_state_id again)
    op.execute(
        "CREATE OR REPLACE VIEW current_game_states AS "
        "SELECT * FROM game_states WHERE row_current_ind = TRUE"
    )
