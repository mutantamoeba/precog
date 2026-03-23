"""Add game_id FK to events table for structural market-to-game linking.

This is the missing link between the Kalshi side (series → events → markets)
and the ESPN side (games → game_states). Without this FK, the only way to
connect a market to its game is by parsing event titles or matching by
date/teams — fragile and not queryable.

One Kalshi event maps to one ESPN game (e.g., event "KXNFL-24DEC22-KC-SEA"
= KC vs SEA on Dec 22). Multiple markets share one event, so the FK belongs
on events (not markets) to avoid denormalization.

Join paths enabled:
    Market → Game: markets.event_internal_id → events.game_id → games.id
    Game → Markets: reverse join via events

Steps:
    1. ADD COLUMN events.game_id INTEGER REFERENCES games(id)
    2. CREATE INDEX on events(game_id)

The column is NULLABLE because:
    - Non-sports events have no game
    - Sports events may not yet have a matched game (ESPN data not yet loaded)
    - The matching logic (ticker parsing + team code lookup) is built separately

Revision ID: 0038
Revises: 0037
Create Date: 2026-03-22

Related:
- Issue #462: Structural market-to-game linking
- Issue #445: Temporal alignment algorithm (depends on this FK)
- Migration 0035: games dimension table creation
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: str = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add game_id FK to events table."""
    # -- Step 1: Add nullable FK column --
    op.execute(
        "ALTER TABLE events ADD COLUMN game_id INTEGER REFERENCES games(id) ON DELETE SET NULL"
    )

    # -- Step 2: Create index for FK lookups --
    # Querying "which events belong to this game?" is a hot path for
    # temporal alignment and model training.
    op.execute("CREATE INDEX idx_events_game_id ON events(game_id)")


def downgrade() -> None:
    """Remove game_id FK from events table."""
    op.execute("DROP INDEX IF EXISTS idx_events_game_id")
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS game_id")
