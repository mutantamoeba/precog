"""Wire orderbook_snapshot_id provenance FK onto orders + edges.

Closes #725 item 11. Links every order and every edge to the specific
``orderbook_snapshots`` row that was visible at decision time — completing
the provenance chain that ``0059`` started (items 1-7) but deferred item 11
per Holden's S57 split recommendation.

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-16

Issue: #725 (item 11)
Epic: #745 (Schema Hardening Arc, residual from Cohort C2)

Design review:
    Holden (S59) — see ``design_725_item11_orderbook.md``. PM-approved.
    Migration numbered 0063 (chains off 0062 C2c business keys, which
    landed as PR #861). The C2c SCD2 prep migration takes 0064.

Columns added (both nullable, both ON DELETE RESTRICT per ADR-116):

    1. orders.orderbook_snapshot_id  -> orderbook_snapshots(id)
    2. edges.orderbook_snapshot_id   -> orderbook_snapshots(id)

Why nullable:
    Forward-only. The orderbook polling pipeline is not yet built; until
    it is, every order and every edge is created without an orderbook
    snapshot context. Adding ``NOT NULL`` now would force a backfill
    decision for production rows that never had this provenance. The
    orderbook pipeline (Phase 3) will start populating the column when
    it lands; a follow-up migration can then ``SET NOT NULL`` once the
    write-side is reliably populating.

Why RESTRICT:
    Matches 0057 + 0059 convention. RESTRICT preserves provenance:
    blocking parent ``orderbook_snapshots`` deletion while orders/edges
    reference it is the whole point of the wiring. SET NULL would
    silently orphan the provenance; CASCADE would silently destroy
    the referencing order/edge record.

Why partial indexes:
    On day-of-land every row is NULL (no orderbook pipeline yet). A
    full btree on a NULL-dominant column would bloat disk with NULLs.
    ``WHERE orderbook_snapshot_id IS NOT NULL`` keeps the index tight
    while still giving lookup speed for non-NULL rows once the pipeline
    writes them. Same pattern as 0059's 7 partial indexes.

CRUD impact (same PR):
    - ``crud_orders.create_order()`` -- add optional
      ``orderbook_snapshot_id: int | None = None`` kwarg. INSERT column
      list + params tuple both grow by one position (appended at end).
    - ``crud_analytics.create_edge()`` -- same treatment.

    No SCD supersede path exists for edges today (``create_edge`` +
    direct lifecycle UPDATEs via ``update_edge_outcome`` /
    ``update_edge_status``). Orders are not SCD at all (mutable rows).
    If a future PR adds SCD supersede for edges, Pattern 49 copy-forward
    applies: source ``orderbook_snapshot_id`` from ``current`` on the
    new version.

    ``update_order`` / ``update_edge_*`` paths are NOT updated. This is
    a write-at-creation-time-only column for now -- callers that need
    to backfill an orderbook snapshot onto an existing row can do so
    with a direct UPDATE until a mutator is warranted.

Write-protection trigger interaction (0056):
    ``ALTER TABLE ADD COLUMN`` is DDL and bypasses 0056's row-level
    write-protection triggers (which fire on INSERT/UPDATE/DELETE only).
    No ``session_replication_role`` adjustment required.

View dependencies (Pattern 38):
    ``current_edges`` (``SELECT * FROM edges WHERE row_current_ind = TRUE``)
    binds its column list at view-creation time -- an ``ALTER TABLE ADD
    COLUMN`` on edges does NOT propagate into the view. This migration
    DROPs and re-creates the view around the ALTER, mirroring the pattern
    used in 0023 and 0058. ``orders`` has no views (verified via
    information_schema), so no orders-side view handling is needed.

Downgrade semantics:
    Forward-only data is lost on downgrade (rows that had non-NULL
    values revert to having never had the column). Safe on day-of-land
    because every row is NULL; downgrade discipline over time is a
    separate process concern.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0063"
down_revision: str = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =============================================================================
# FK addition specification
# =============================================================================
# Each tuple: (child_table, child_column, parent_table, parent_column)
# Both columns: nullable INTEGER, ON DELETE RESTRICT, partial btree index.

NEW_FKS: list[tuple[str, str, str, str]] = [
    # Item 11a: orders provenance back to the orderbook snapshot at decision time
    ("orders", "orderbook_snapshot_id", "orderbook_snapshots", "id"),
    # Item 11b: edges provenance back to the orderbook snapshot at edge detection
    ("edges", "orderbook_snapshot_id", "orderbook_snapshots", "id"),
]


def _fk_name(child_table: str, child_column: str) -> str:
    """Return the auto-naming FK constraint name used by PostgreSQL.

    Matches the ``{table}_{column}_fkey`` pattern that 0057/0059 use,
    keeping information_schema discovery uniform.
    """
    return f"{child_table}_{child_column}_fkey"


def _index_name(child_table: str, child_column: str) -> str:
    """Return the partial-index name for a new FK column."""
    return f"idx_{child_table}_{child_column}"


def upgrade() -> None:
    """Add 2 nullable FK columns with RESTRICT + partial indexes."""
    for child_table, child_column, parent_table, parent_column in NEW_FKS:
        constraint_name = _fk_name(child_table, child_column)
        index_name = _index_name(child_table, child_column)

        # Pattern 38: SELECT * views bind their column list at view
        # creation time, so an ALTER TABLE ADD COLUMN does NOT propagate
        # into the view. ``current_edges`` (last refreshed by 0058) must
        # be dropped BEFORE the edges ALTER and re-created after so the
        # new ``orderbook_snapshot_id`` column surfaces through the view.
        # ``orders`` has no views -- only the edges iteration needs this.
        if child_table == "edges":
            op.execute("DROP VIEW IF EXISTS current_edges")

        # Combined column-add + FK constraint. Postgres validates the
        # constraint instantly because the column is nullable and no
        # existing rows violate it (all NULL).
        op.execute(
            f"""
            ALTER TABLE {child_table}
            ADD COLUMN {child_column} INTEGER
            CONSTRAINT {constraint_name}
            REFERENCES {parent_table}({parent_column}) ON DELETE RESTRICT
            """
        )

        # Partial index to keep the NULL-dominant column's index tight.
        op.execute(
            f"""
            CREATE INDEX {index_name}
            ON {child_table}({child_column})
            WHERE {child_column} IS NOT NULL
            """
        )

        # Pattern 38 (part 2): re-create the view now that the edges
        # column list includes ``orderbook_snapshot_id``. SELECT *
        # re-expands against the current column list at view creation.
        if child_table == "edges":
            op.execute(
                "CREATE OR REPLACE VIEW current_edges AS "
                "SELECT * FROM edges WHERE row_current_ind = TRUE"
            )


def downgrade() -> None:
    """Drop the 2 FK columns + partial indexes. Forward-only data is lost."""
    # Drop in reverse order of upgrade so indexes come down before their
    # backing columns (Postgres tolerates either order today, but the
    # explicit teardown sequence matches the upgrade narrative and
    # matches 0059's downgrade style).
    for child_table, child_column, _parent_table, _parent_column in reversed(NEW_FKS):
        index_name = _index_name(child_table, child_column)

        # Pattern 38: drop the view BEFORE the DROP COLUMN. Even though
        # ``current_edges`` is defined via SELECT *, PostgreSQL resolves
        # and binds the expansion to specific column references at view
        # creation time, and will refuse to drop a column the view
        # depends on. Mirror of the upgrade guard.
        if child_table == "edges":
            op.execute("DROP VIEW IF EXISTS current_edges")

        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        # ``DROP COLUMN`` cascades the FK constraint automatically.
        op.execute(f"ALTER TABLE {child_table} DROP COLUMN IF EXISTS {child_column}")

        # Pattern 38 (part 2): re-create the view with SELECT *, which
        # now re-expands to the pre-0063 column list (since we just
        # dropped ``orderbook_snapshot_id``). This is the correct "undo"
        # -- the view is restored to its pre-0063 shape.
        if child_table == "edges":
            op.execute(
                "CREATE OR REPLACE VIEW current_edges AS "
                "SELECT * FROM edges WHERE row_current_ind = TRUE"
            )
