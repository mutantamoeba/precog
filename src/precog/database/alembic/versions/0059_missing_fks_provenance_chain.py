"""Add 7 missing foreign keys to complete the provenance chain.

Closes #725 items 1-7. Item 11 (orderbook_snapshots wiring for orders/edges)
is explicitly deferred to a follow-up migration 0060 per Holden's S57
split recommendation — it is design-decision-heavy and splitting lets
items 1-7 land clean. Items 8-10 are deferred to #726 (Cohort C3 analytics
enrichment) because they overlap with the analytics re-wiring there.

Revision ID: 0059
Revises: 0058
Create Date: 2026-04-15

Issues: #725 (items 1-7)
Epic: #745 (Schema Hardening Arc, residual from C2)

Design review:
    Holden (S57) — design memo authoritative. Recommended split (0060 items
    1-7 + 0061 item 11) onto post-0058 main. This migration is numbered
    0059 per task-brief instruction because 0058 is the latest on disk
    and there is no other 0059 in the versions tree.

Council attribution:
    Holden (Principled Steward) — provenance FK gap identified alongside
    #724/#725 scoping, S44 C1 review.

Columns added (all nullable, all ON DELETE RESTRICT per ADR-116):

    1. positions.edge_id            → edges(id)             [SCD parent]
    2. settlements.position_id      → positions(id)         [SCD parent]
    3. settlements.order_id         → orders(id)
    4. position_exits.order_id      → orders(id)
    5. exit_attempts.order_id       → orders(id)
    6. edges.market_snapshot_id     → market_snapshots(id)  [SCD parent]
    7. edges.prediction_id          → predictions(id)       [append-only]

Why nullable:
    Forward-only adoption. Every one of the 7 child tables already has
    rows (production and test). Adding NOT NULL would force a backfill
    decision per row, which is out of scope for a provenance-FK wiring
    migration. Nullable + ``NOT VALID``-free instant validation (empty
    constraint) keeps this as a pure metadata ALTER.

Why RESTRICT:
    Matches 0057's RESTRICT conversion. RESTRICT blocks parent deletion
    when children reference the parent; SET NULL would silently orphan
    provenance; CASCADE would silently destroy downstream records. For a
    provenance chain, RESTRICT is the only defensible default.

Why partial indexes:
    Each new column is NULL-dominant at time of creation (all existing
    rows are NULL). A full index would bloat with NULLs. Partial indexes
    WHERE ``<col> IS NOT NULL`` keep the index tight while still giving
    lookup speed for non-NULL rows.

Naming:
    Constraints follow PostgreSQL's auto-naming convention
    ``{child_table}_{child_column}_fkey`` to match 0057's ``NAMED_CONSTRAINTS``
    fallback. information_schema discovery will pick them up without a
    dict entry.

SCD co-requirement (highest risk, addressed in the SAME PR):
    Columns 1, 6, 7 target SCD Type 2 tables (positions, edges, edges).
    Without updating the SCD *supersede* INSERT column lists in
    ``crud_positions.py``, every position-version update would silently
    set ``edge_id = NULL`` on the new version — the equivalent of
    SET NULL cascade, exactly the behavior 0057 was built to eliminate.
    This PR therefore also ships:
        - ``crud_positions.py``: 3 supersede INSERTs gain ``edge_id``
          sourced from ``current["edge_id"]`` (Pattern 49 copy-forward).
        - ``tests/integration/database/test_scd_copy_forward.py``:
          regression test asserting the contract.
    For ``edges``, no SCD supersede path exists today in the codebase
    (only ``create_edge`` + direct ``UPDATE`` lifecycle transitions
    filtered by ``row_current_ind = TRUE``). The ``create_edge`` helper
    was NOT changed because the two new FK columns will default to
    ``NULL`` on write and can be populated later when callers have
    provenance context. When a genuine SCD supersede path is later
    added for edges (e.g. on price drift), the Pattern 49 copy-forward
    checklist must be applied there too — see design memo §6 and the
    checklist comment at the top of ``crud_positions.py`` add for the
    pattern to follow.

Naming collision note:
    ``positions.edge_id`` (new) is the surrogate FK to ``edges(id)``
    — the edge row that produced the position. ``positions.edge_at_entry``
    (existing, DECIMAL) is the numeric edge value captured at entry time.
    Distinct semantics; a ``COMMENT ON COLUMN`` is added to make the
    distinction explicit at the DB level.

Write-protection trigger interaction (0056):
    ``ALTER TABLE ADD COLUMN`` is DDL and bypasses 0056's row-level
    write-protection triggers, which fire on INSERT/UPDATE/DELETE. No
    ``session_replication_role`` adjustment is required. Verified by
    reading 0056 before authoring this migration.

Downgrade semantics:
    Forward-only backfill is lost on downgrade (any rows that had
    non-NULL values revert to having never had the column). Documented
    per Holden memo §5. Safe because on day-of-land every row is NULL;
    downgrade discipline over time is a separate process concern.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0059"
down_revision: str = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# =============================================================================
# FK addition specification
# =============================================================================
# Each tuple: (child_table, child_column, parent_table, parent_column)
# All constraints use ON DELETE RESTRICT (ADR-116).
# All columns are nullable INTEGER (forward-only adoption).
# All columns get a partial index WHERE <col> IS NOT NULL.

MISSING_FKS: list[tuple[str, str, str, str]] = [
    # Item 1: positions provenance back to the edge that triggered it
    ("positions", "edge_id", "edges", "id"),
    # Item 2: settlements back to the originating position
    ("settlements", "position_id", "positions", "id"),
    # Item 3: settlements back to the originating order
    ("settlements", "order_id", "orders", "id"),
    # Item 4: position_exits back to the exit-order
    ("position_exits", "order_id", "orders", "id"),
    # Item 5: exit_attempts back to the exit-order
    ("exit_attempts", "order_id", "orders", "id"),
    # Item 6: edges back to the market_snapshot used at edge calculation
    ("edges", "market_snapshot_id", "market_snapshots", "id"),
    # Item 7: edges back to the prediction row that produced the probability
    ("edges", "prediction_id", "predictions", "id"),
]


def _fk_name(child_table: str, child_column: str) -> str:
    """Return the auto-naming FK constraint name used by PostgreSQL.

    Matches the ``{table}_{column}_fkey`` pattern that 0057's
    ``_get_constraint_name`` falls back to when no entry exists in
    ``NAMED_CONSTRAINTS``. Keeps future information_schema discovery
    simple.
    """
    return f"{child_table}_{child_column}_fkey"


def _index_name(child_table: str, child_column: str) -> str:
    """Return the partial-index name for a new FK column."""
    return f"idx_{child_table}_{child_column}"


def upgrade() -> None:
    """Add 7 nullable FK columns with RESTRICT + partial indexes."""
    for child_table, child_column, parent_table, parent_column in MISSING_FKS:
        constraint_name = _fk_name(child_table, child_column)
        index_name = _index_name(child_table, child_column)

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

    # Clarifying comment on positions.edge_id — distinguishes the new
    # FK column from the pre-existing DECIMAL ``edge_at_entry`` column.
    # Holden's memo §2 flagged this as a naming-collision risk that would
    # confuse future readers without an explicit DB-level comment.
    op.execute(
        """
        COMMENT ON COLUMN positions.edge_id IS
        'Provenance FK to edges(id) — the edge row that produced this '
        'position. Distinct from edge_at_entry which stores the numeric '
        'edge value (probability - market_price) captured at entry time. '
        'Added in migration 0059 for #725.'
        """
    )


def downgrade() -> None:
    """Drop the 7 FK columns + partial indexes. Forward-only data is lost."""
    # Drop in reverse order of upgrade so indexes come down before their
    # backing columns (Postgres tolerates either order today, but the
    # explicit teardown sequence matches the upgrade narrative).
    for child_table, child_column, _parent_table, _parent_column in reversed(MISSING_FKS):
        index_name = _index_name(child_table, child_column)
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        # ``DROP COLUMN`` cascades the FK constraint automatically.
        op.execute(f"ALTER TABLE {child_table} DROP COLUMN IF EXISTS {child_column}")
