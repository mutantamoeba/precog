"""0062: C2c business key columns on markets/events/game_states/games.

Arc: Phase B kickoff of the Schema Hardening Arc (epic #745, issue #791).

Adds a stable, human-readable business key (``market_key``, ``event_key``,
``game_state_key``, ``game_key``) to each of the four core entity tables.
These ``<entity>_key`` columns provide:

  * Cross-platform identity for non-Kalshi markets (Polymarket, Manifold, etc.)
  * Stable SCD2 natural keys (carried forward on supersede, preserved across
    versions of the same logical entity)
  * Human-readable primary reference in logs and analytics

Design memo: S59 Holden + Galadriel review (design_791_c2c_business_keys.md).
Sibling migration 0063 adds SCD2 temporal columns to strategies +
probability_models (separate PR).  Sibling migration 0064 wires
``orderbook_snapshot_id`` onto orders + edges (#725 item 11, separate PR).

Steps:
    1. ADD COLUMN <x>_key VARCHAR NULL on each of markets / events /
       game_states / games.
    2. Backfill ``<PREFIX>-<id>`` into each column using a single UPDATE
       per table (row counts from MCP: markets 8,242; events 4,121;
       game_states 29,087; games 5,074 — all sub-second).
    3. SET NOT NULL on all four columns.
    4. Indexes:
         - markets, events, games: full UNIQUE btree on ``<x>_key``
           (these tables are dimensions, not SCD2 — one row per business key).
         - game_states: a non-unique btree on ``game_state_key`` for
           lookup, PLUS a partial UNIQUE (``game_state_key``) WHERE
           ``row_current_ind = true`` (SCD2-aware — at most one current
           row per business key).

Downgrade: strict reverse (drop indexes → DROP NOT NULL → drop columns).

CRUD impact (same PR, lands alongside this migration):
    * ``crud_markets.create_market`` — two-step INSERT (TEMP sentinel →
      ``MKT-{id}`` via UPDATE) so the ``NOT NULL`` column is always
      populated before any other transaction can see the row.
    * ``crud_events.create_event`` — two-step INSERT (TEMP → ``EVT-{id}``).
    * ``crud_game_states.create_game_state`` — two-step INSERT (TEMP → ``GST-{id}``).
    * ``crud_game_states.upsert_game_state`` — expand the FOR UPDATE lock
      query SELECT list to include ``game_state_key``; carry existing key
      forward on supersede (SCD Type 2 rule — never regenerate).
    * ``crud_game_states.get_or_create_game`` — two-step INSERT (TEMP →
      ``GAM-{id}``) on the CREATE path; COALESCE on the ON CONFLICT path.
    * ``seeding/historical_games_loader._flush_games_batch`` — follow-up
      UPDATE on the batch to set ``game_key = 'GAM-' || id`` for newly
      inserted rows.

Issue: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)
Session: S60
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0062"
down_revision: str = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ─── Per-table spec ─────────────────────────────────────────────────────────
# (table, key_column, prefix, is_scd2)
#
# ``is_scd2=True`` means the table has a ``row_current_ind`` column and the
# UNIQUE constraint on the new ``<x>_key`` must be a *partial* UNIQUE that
# only fires for the current version (allowing historical versions to share
# the same business key).  Non-SCD2 tables (dimensions) get a full UNIQUE.
_KEY_SPEC: list[tuple[str, str, str, bool]] = [
    ("markets", "market_key", "MKT", False),
    ("events", "event_key", "EVT", False),
    ("game_states", "game_state_key", "GST", True),
    ("games", "game_key", "GAM", False),
]


def upgrade() -> None:
    """Add + backfill + index the four new business-key columns."""
    conn = op.get_bind()

    # ─── Step 1: ADD COLUMN (nullable) ──────────────────────────────────────
    # Must be nullable first so the backfill in step 2 can run.  Step 3
    # enforces NOT NULL once every row has a value.
    for table, key_col, _prefix, _is_scd2 in _KEY_SPEC:
        op.execute(f"ALTER TABLE {table} ADD COLUMN {key_col} VARCHAR")

    # ─── Step 2: Backfill from surrogate id ─────────────────────────────────
    # Pattern: <PREFIX>-<id>, e.g. "MKT-42", "GAM-1007".  All four tables
    # have an INTEGER ``id`` column (PK, SERIAL).  Row counts verified via
    # MCP are sub-second trivial for PostgreSQL — no batching required.
    #
    # ``WHERE <key_col> IS NULL`` is a defensive filter: allows this
    # migration to be re-run (or re-applied after a partial failure)
    # without corrupting rows that already got a key value from CRUD
    # writes between steps.
    #
    # ``prefix`` is sent as a bound parameter (not f-string interpolated)
    # to keep the SQL stable for PostgreSQL statement caching and to eliminate
    # any residual injection surface — table/key_col are hardcoded module
    # constants, but routing ``prefix`` through binds is still the correct
    # default pattern (Glokta S60 review W1).
    for table, key_col, prefix, _is_scd2 in _KEY_SPEC:
        # safe: table/key_col are hardcoded module constants; prefix is a bind
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {key_col} = :prefix || '-' || id "  # noqa: S608
                f"WHERE {key_col} IS NULL"
            ),
            {"prefix": prefix},
        )

    # ─── Step 2.5: Zero-NULL assertion ──────────────────────────────────────
    # If any row failed to backfill, surface the row count (not a sample,
    # since id is monotonic and a count tells ops everything they need).
    # A NULL here would cause step 3 (SET NOT NULL) to fail opaquely.
    for table, key_col, _prefix, _is_scd2 in _KEY_SPEC:
        null_count = conn.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} WHERE {key_col} IS NULL"  # noqa: S608
            )
        ).scalar()
        if null_count and int(null_count) > 0:
            raise RuntimeError(
                f"[0062] Backfill failure on {table}.{key_col}: "
                f"{null_count} row(s) still NULL after backfill. "
                f"This should be impossible — every row has a non-NULL "
                f"``id`` — and indicates a data-integrity issue that must "
                f"be investigated before retrying."
            )

    # ─── Step 3: SET NOT NULL ───────────────────────────────────────────────
    for table, key_col, _prefix, _is_scd2 in _KEY_SPEC:
        op.alter_column(table, key_col, nullable=False)

    # ─── Step 4: Indexes ────────────────────────────────────────────────────
    # Non-SCD2 tables (markets, events, games): full UNIQUE btree.  One row
    # per logical entity, enforced at every point in time.
    #
    # SCD2 table (game_states): two indexes —
    #   (a) non-unique btree for efficient lookup of any version by key;
    #   (b) partial UNIQUE WHERE row_current_ind = true, mirroring the
    #       existing ``idx_game_states_current_unique`` pattern (which is
    #       on ``espn_event_id``).  The partial predicate allows historical
    #       versions to share the same ``game_state_key`` while guaranteeing
    #       at most one CURRENT row per business key.
    for table, key_col, _prefix, is_scd2 in _KEY_SPEC:
        if is_scd2:
            # game_states: lookup btree (all versions)
            op.execute(f"CREATE INDEX idx_{table}_{key_col} ON {table}({key_col})")
            # game_states: SCD2-aware partial UNIQUE (current version only)
            op.execute(
                f"CREATE UNIQUE INDEX idx_{table}_{key_col}_current "
                f"ON {table}({key_col}) WHERE row_current_ind = true"
            )
        else:
            # markets / events / games: full UNIQUE (one row per key)
            op.execute(f"CREATE UNIQUE INDEX idx_{table}_{key_col} ON {table}({key_col})")


def downgrade() -> None:
    """Strict reverse of upgrade (indexes → nullability → columns)."""
    # ─── Reverse Step 4: drop indexes ───────────────────────────────────────
    # For SCD2 table, drop BOTH indexes (lookup + partial UNIQUE).
    for table, key_col, _prefix, is_scd2 in reversed(_KEY_SPEC):
        if is_scd2:
            op.execute(f"DROP INDEX IF EXISTS idx_{table}_{key_col}_current")
            op.execute(f"DROP INDEX IF EXISTS idx_{table}_{key_col}")
        else:
            op.execute(f"DROP INDEX IF EXISTS idx_{table}_{key_col}")

    # ─── Reverse Step 3: restore nullable ───────────────────────────────────
    for table, key_col, _prefix, _is_scd2 in reversed(_KEY_SPEC):
        op.alter_column(table, key_col, nullable=True)

    # ─── Reverse Step 1: drop columns ───────────────────────────────────────
    # (Step 2 backfill is inherently reversed by column drop.)
    for table, key_col, _prefix, _is_scd2 in reversed(_KEY_SPEC):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {key_col}")
