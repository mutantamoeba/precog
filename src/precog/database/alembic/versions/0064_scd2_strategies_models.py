"""0064: C2c SCD Type 2 prep on ``strategies`` + ``probability_models``.

Arc: Phase B step 3 of the Schema Hardening Arc (epic #745, issue #791).

Adds SCD Type 2 temporal columns (``row_current_ind``, ``row_start_ts``,
``row_end_ts``) to ``strategies`` and ``probability_models`` so status
transitions can be recorded as supersede versions instead of in-place
UPDATEs.  This finally aligns the two "immutable config / mutable status"
tables with the SCD2 pattern every other versioned table in the schema
already uses (markets, positions, game_states, account_balance, etc.).

Design memo: S59 Holden + Galadriel review
(``design_791_c2c_business_keys.md`` § "Migration 0063: SCD2 Prep").  The
original design-memo number was 0063; a number collision with #725 item 11
(orderbook_snapshot_id FK, merged as 0063 in PR #863) pushed this
migration to 0064 during S60/S61.

Row counts at design time (MCP-verified 2026-04-16):
    * strategies:        0 rows
    * probability_models: 0 rows

Backfill is therefore trivial.  Explicit UPDATEs are still included for
defensive safety and to keep the upgrade idempotent if a future operator
runs this migration on a non-empty dev DB.

Steps:
    1. ADD COLUMN ``row_current_ind BOOLEAN NOT NULL DEFAULT TRUE`` on both tables.
    2. ADD COLUMN ``row_start_ts TIMESTAMPTZ NOT NULL DEFAULT NOW()`` on both tables.
    3. ADD COLUMN ``row_end_ts TIMESTAMPTZ NULL`` on both tables.
    4. Defensive backfill of the new NOT NULL columns for any
       pre-existing rows (no-op on dev/test where tables are empty).
    5. DROP the unconditional UNIQUE constraints that conflict with SCD2
       supersede semantics (``unique_strategy_name_version`` +
       ``unique_model_name_version``).  A supersede INSERTs a second row
       with the same ``(name, version)`` while the previous row still
       carries ``row_current_ind = TRUE`` until the UPDATE closes it —
       the full UNIQUE would reject this.
    6. CREATE partial UNIQUE indexes ``WHERE row_current_ind = TRUE`` to
       preserve the same uniqueness semantics at the ``current`` layer:
       at most one current row per ``(name, version)`` at any time.
       Historical (closed) rows may share ``(name, version)`` — that is
       the SCD2 contract.

Downgrade: strict reverse.  DROP statements are wrapped in ``IF EXISTS``
per S59 idempotency lesson (``feedback_idempotent_migration_drops.md``)
so a downgrade→upgrade cycle survives even if a previous downgrade was
partially applied.  Constraint recreation in downgrade recreates the
original unconditional UNIQUEs — this is lossy for any historical
(non-current) rows that would now collide, matching the "downgrade
intentionally discards SCD history" pattern established in 0049.

CRUD impact (same PR, lands alongside this migration):
    * ``crud_strategies.update_strategy_status`` — convert from an
      in-place UPDATE to an SCD2 close+INSERT supersede.  Contract is
      preserved (``strategy_id: int, new_status: str, ...) -> bool``),
      but the underlying row graph now grows a new version on every
      status transition.  Mirrors the positions / markets supersede
      pattern (``crud_positions.update_position_price``,
      ``crud_markets.update_market_snapshot``).
    * ``analytics.model_manager.ModelManager.create_model`` — add
      explicit SCD2 column values to the INSERT (``row_current_ind,
      row_start_ts, row_end_ts``).  The column defaults would populate
      these implicitly; writing them explicitly keeps the INSERT shape
      self-documenting and matches Pattern 2 (SCD2 INSERT explicitness).

Out of scope (per design memo § "Key Decisions"):
    * PK rename ``strategy_id``/``model_id`` → ``id`` is deferred to C2d
      (5-6 child FK cascades + immutability trigger edits + sequence
      rename — separate concern).
    * Business-key columns (``_key``) on strategies or probability_models
      are explicitly deferred: the natural composite key
      ``(name, version)`` already serves that role for in-platform use;
      cross-platform identity will be addressed in C2d if/when needed.
    * Immutability triggers (``trg_strategies_immutability``,
      ``trg_models_immutability``) fire on UPDATE of guarded columns
      (config / version / name / type|class).  SCD2 supersede is a
      CLOSE-UPDATE of ``row_current_ind`` + ``row_end_ts`` (NOT guarded)
      followed by an INSERT — the triggers still fire on the CLOSE-UPDATE
      but their IS-DISTINCT-FROM guards return FALSE for the non-guarded
      columns we touch, so they let the update pass.  No trigger change
      required.  Verified post-apply via
      ``information_schema.triggers`` + ``pg_get_functiondef``.

Write-protection trigger interaction (0056):
    The 0056 row-level write-protection triggers guard a different column
    set from the immutability triggers and do not fire on either of
    these tables (verified: the 0056 audit selected only tables explicitly
    listed in that migration's ``PROTECTED_TABLES`` tuple — strategies
    and probability_models were not in that tuple).  No
    ``session_replication_role`` adjustment required.

View dependencies (Pattern 38):
    Neither table has any dependent views at HEAD.  Verified via
    ``information_schema.view_column_usage`` — no ``SELECT * FROM
    strategies`` / ``FROM probability_models`` views exist.  No DROP /
    CREATE VIEW guards required.

S72 post-build constraint audit (MCP, pre-upgrade baseline):
    strategies:
        - strategies_pkey               PRIMARY KEY     (keep: PK is SCD2-compatible)
        - strategies_platform_id_fkey   FOREIGN KEY     (keep: FK compatible)
        - strategies_strategy_type_fkey FOREIGN KEY     (keep: FK compatible)
        - unique_strategy_name_version  UNIQUE          (DROP + replace with partial)
    probability_models:
        - probability_models_pkey           PRIMARY KEY (keep)
        - probability_models_model_class_fkey FOREIGN KEY (keep)
        - unique_model_name_version         UNIQUE      (DROP + replace with partial)

Issue: #791
Epic: #745 (Schema Hardening Arc, Cohort C2c)
Session: S62
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0064"
down_revision: str = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =============================================================================
# Per-table spec
# =============================================================================
# (table, full_unique_constraint_to_drop, partial_unique_index_name,
#  partial_unique_columns)
#
# The two tables share an identical SCD2 shape and an identical
# ``(name, version)`` natural key — only the table and column names
# differ.  Driving everything from a spec list keeps upgrade +
# downgrade + audit perfectly symmetric.
_SCD2_SPEC: list[tuple[str, str, str, str]] = [
    (
        "strategies",
        "unique_strategy_name_version",
        "idx_strategies_name_version_current",
        "strategy_name, strategy_version",
    ),
    (
        "probability_models",
        "unique_model_name_version",
        "idx_probability_models_name_version_current",
        "model_name, model_version",
    ),
]


def upgrade() -> None:
    """Add SCD2 temporal columns + partial UNIQUE indexes on both tables."""

    # ─── Step 1-3: ADD SCD2 COLUMNS ─────────────────────────────────────────
    # row_current_ind: TRUE for live rows, FALSE after supersede.
    # row_start_ts:    version-start timestamp (defaults to NOW() on INSERT).
    # row_end_ts:      NULL for current rows, timestamp for historical rows.
    #
    # Defaults make the ALTER safe on a non-empty table: every existing row
    # will become ``row_current_ind = TRUE`` with ``row_start_ts = NOW()``,
    # which is the correct "pretend everything created so far is the current
    # version as of migration time" semantic.
    for table, _drop_uq, _part_idx, _part_cols in _SCD2_SPEC:
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN row_current_ind BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN row_start_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ADD COLUMN row_end_ts TIMESTAMPTZ
            """
        )

    # ─── Step 4: Defensive backfill ─────────────────────────────────────────
    # Row counts at design time are zero on both tables, so these UPDATEs
    # are no-ops in practice.  They exist so that a future operator running
    # this migration against a DB with pre-existing strategies / models
    # rows gets the same well-defined SCD2 state as a fresh DB.
    #
    # ``COALESCE(created_at, NOW())`` on strategies preserves the natural
    # creation-time anchor for row_start_ts where possible (strategies.
    # created_at is nullable).  probability_models.created_at is also
    # nullable, so we apply the same COALESCE.
    for table, _drop_uq, _part_idx, _part_cols in _SCD2_SPEC:
        # safe: table is a hardcoded module constant (see _SCD2_SPEC)
        op.execute(
            f"UPDATE {table} "  # noqa: S608
            f"SET row_current_ind = TRUE, "
            f"    row_start_ts = COALESCE(created_at, NOW()), "
            f"    row_end_ts = NULL "
            f"WHERE row_current_ind IS NULL OR row_start_ts IS NULL"
        )

    # ─── Step 5: DROP unconditional UNIQUE constraints ──────────────────────
    # These constraints enforce one-row-per-(name, version) at every point
    # in time — incompatible with SCD2, where a supersede INSERT creates
    # a second row with the same (name, version) while the previous row
    # still has row_current_ind = TRUE during the split-second between
    # INSERT and the CLOSE-UPDATE of the predecessor.
    #
    # IF EXISTS is used per S59 idempotency lesson — if a downgrade was
    # partially applied and then re-upgraded, the constraint may already
    # be gone and the DROP must not fail.
    for table, drop_uq, _part_idx, _part_cols in _SCD2_SPEC:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {drop_uq}")

    # ─── Step 6: CREATE partial UNIQUE indexes ──────────────────────────────
    # Preserves the uniqueness semantics at the "current" layer:
    # at most one current row per (name, version).  Historical rows may
    # share (name, version) — that is the SCD2 contract.
    for table, _drop_uq, part_idx, part_cols in _SCD2_SPEC:
        op.execute(
            f"""
            CREATE UNIQUE INDEX {part_idx}
            ON {table}({part_cols})
            WHERE row_current_ind = TRUE
            """
        )


def downgrade() -> None:
    """Strict reverse: drop partial indexes → restore full UNIQUE → drop cols.

    Downgrade is **lossy** for SCD history.  If historical (non-current)
    rows share (name, version) with a current row, recreating the
    unconditional UNIQUE constraint will fail.  In that event the
    operator is expected to DELETE historical rows before downgrading
    (or cancel the downgrade) — consistent with the 0049 account_balance
    downgrade model and the general "downgrade intentionally discards
    SCD history" pattern for SCD-adding migrations.
    """

    # ─── Reverse Step 6: drop partial UNIQUE indexes ────────────────────────
    # IF EXISTS per S59 idempotency lesson.
    for _table, _drop_uq, part_idx, _part_cols in reversed(_SCD2_SPEC):
        op.execute(f"DROP INDEX IF EXISTS {part_idx}")

    # ─── Reverse Step 5: restore full UNIQUE constraints ────────────────────
    # Will FAIL if SCD history has accumulated conflicting rows — see
    # docstring.  Names are restored verbatim from the pre-0064 schema
    # so subsequent migrations that DROP them by name continue to work.
    for table, drop_uq, _part_idx, part_cols in reversed(_SCD2_SPEC):
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {drop_uq} UNIQUE ({part_cols})")

    # ─── Reverse Step 1-4: drop SCD2 columns ────────────────────────────────
    # Dropping the columns implicitly drops the DEFAULTs and the backfill.
    # IF EXISTS per S59 idempotency lesson.
    for table, _drop_uq, _part_idx, _part_cols in reversed(_SCD2_SPEC):
        op.execute(
            f"""
            ALTER TABLE {table}
            DROP COLUMN IF EXISTS row_end_ts,
            DROP COLUMN IF EXISTS row_start_ts,
            DROP COLUMN IF EXISTS row_current_ind
            """
        )
