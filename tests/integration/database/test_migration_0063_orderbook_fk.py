"""Integration tests for migration 0063 -- orderbook_snapshot_id FK on orders + edges.

Verifies the POST-MIGRATION state of ``orderbook_snapshot_id`` on orders
and edges, plus the CRUD create-path contracts that populate the column
when callers pass it.

Test groups:
    - TestOrderbookSnapshotColumnsPresent: column exists and is nullable
      on both orders + edges (query information_schema.columns).
    - TestOrderbookSnapshotForeignKey: FK constraint exists and is
      ON DELETE RESTRICT on both tables (query information_schema
      table_constraints + referential_constraints).
    - TestOrderbookSnapshotPartialIndex: partial btree index exists with
      ``WHERE (orderbook_snapshot_id IS NOT NULL)`` predicate on both
      tables (query pg_indexes).
    - TestCreateOrderWritesFK: ``create_order(..., orderbook_snapshot_id=N)``
      persists the FK; ``create_order(...)`` without it persists NULL
      (backward-compat regression).
    - TestCreateEdgeWritesFK: same two scenarios for ``create_edge``.
    - TestOnDeleteRestrict: deleting a parent ``orderbook_snapshots`` row
      while an order or edge references it raises a ForeignKeyViolation
      (RESTRICT semantics enforced).

Issue: #725 (item 11)
Epic: #745 (Schema Hardening Arc, provenance chain completion)

Markers:
    @pytest.mark.integration: real DB required (testcontainer per ADR-057)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import psycopg2
import pytest

from precog.database.connection import fetch_one, get_cursor
from precog.database.crud_analytics import create_edge
from precog.database.crud_markets import create_market, insert_orderbook_snapshot
from precog.database.crud_orders import create_order

pytestmark = [pytest.mark.integration]


# =============================================================================
# Per-table spec -- tables that got the new FK column
# =============================================================================

# (table, fk_column, index_name, constraint_name)
_FK_SPEC: list[tuple[str, str, str, str]] = [
    (
        "orders",
        "orderbook_snapshot_id",
        "idx_orders_orderbook_snapshot_id",
        "orders_orderbook_snapshot_id_fkey",
    ),
    (
        "edges",
        "orderbook_snapshot_id",
        "idx_edges_orderbook_snapshot_id",
        "edges_orderbook_snapshot_id_fkey",
    ),
]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def orderbook_parent(db_pool: Any) -> Any:
    """Create a parent orderbook_snapshots row + its market for FK tests.

    Yields a dict with ``market_pk``, ``snapshot_id``, and ``test_ticker``.
    Cleanup deletes dependents (orders, edges) + the snapshot + the market
    in reverse FK order.
    """
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    test_ticker = f"TEST-0063-{uuid.uuid4().hex[:8]}"

    with get_cursor(commit=True) as cur:
        delete_market_with_children(cur, "ticker = %s", (test_ticker,))

    market_pk = create_market(
        platform_id="kalshi",
        event_id=None,
        external_id=f"{test_ticker}-EXT",
        ticker=test_ticker,
        title="Test market for 0063 orderbook FK",
        yes_ask_price=Decimal("0.5000"),
        no_ask_price=Decimal("0.5000"),
    )
    snapshot_id = insert_orderbook_snapshot(
        market_id=market_pk,
        best_bid=Decimal("0.5000"),
        best_ask=Decimal("0.5100"),
    )

    yield {
        "market_pk": market_pk,
        "snapshot_id": snapshot_id,
        "test_ticker": test_ticker,
    }

    with get_cursor(commit=True) as cur:
        delete_market_with_children(cur, "ticker = %s", (test_ticker,))


# =============================================================================
# Group 1: Column presence + nullability
# =============================================================================


@pytest.mark.parametrize(("table", "fk_col", "_index", "_constraint"), _FK_SPEC)
def test_orderbook_snapshot_column_exists_and_nullable(
    db_pool: Any, table: str, fk_col: str, _index: str, _constraint: str
) -> None:
    """Column exists, is INTEGER, and is nullable on both tables."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            """,
            (table, fk_col),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.{fk_col} column missing post-0063"
    assert row["data_type"] == "integer", (
        f"{table}.{fk_col} must be INTEGER, got {row['data_type']}"
    )
    assert row["is_nullable"] == "YES", f"{table}.{fk_col} must be nullable"


# =============================================================================
# Group 2: Foreign key constraint + ON DELETE RESTRICT
# =============================================================================


@pytest.mark.parametrize(("table", "fk_col", "_index", "constraint_name"), _FK_SPEC)
def test_orderbook_snapshot_fk_is_restrict(
    db_pool: Any, table: str, fk_col: str, _index: str, constraint_name: str
) -> None:
    """FK constraint exists on both tables with ON DELETE RESTRICT.

    Joins information_schema.table_constraints with referential_constraints
    to read the delete_rule. Mirrors the pattern used by migration 0057's
    test harness.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT tc.constraint_name,
                   tc.table_name,
                   rc.delete_rule,
                   ccu.table_name AS referenced_table,
                   ccu.column_name AS referenced_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.referential_constraints rc
              ON tc.constraint_name = rc.constraint_name
             AND tc.constraint_schema = rc.constraint_schema
            JOIN information_schema.constraint_column_usage ccu
              ON rc.unique_constraint_name = ccu.constraint_name
             AND rc.unique_constraint_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = %s
              AND tc.constraint_name = %s
            """,
            (table, constraint_name),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"FK constraint {constraint_name!r} missing on {table}.{fk_col} post-0063"
    )
    assert row["delete_rule"] == "RESTRICT", (
        f"{table}.{fk_col} FK delete_rule must be RESTRICT "
        f"(provenance preservation), got {row['delete_rule']!r}"
    )
    assert row["referenced_table"] == "orderbook_snapshots", (
        f"{table}.{fk_col} must reference orderbook_snapshots, got {row['referenced_table']!r}"
    )
    assert row["referenced_column"] == "id", (
        f"{table}.{fk_col} must reference orderbook_snapshots(id), "
        f"got ...({row['referenced_column']!r})"
    )


# =============================================================================
# Group 3: Partial btree index
# =============================================================================


@pytest.mark.parametrize(("table", "fk_col", "index_name", "_constraint"), _FK_SPEC)
def test_orderbook_snapshot_partial_index_exists(
    db_pool: Any, table: str, fk_col: str, index_name: str, _constraint: str
) -> None:
    """Partial btree index exists on both tables with IS NOT NULL predicate.

    Postgres normalizes the index predicate in pg_indexes.indexdef to
    ``WHERE (orderbook_snapshot_id IS NOT NULL)``. The parenthesization
    is stable; the assertion uses a contains-check on that normalized form.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = %s AND indexname = %s
            """,
            (table, index_name),
        )
        row = cur.fetchone()
    assert row is not None, f"Partial index {index_name!r} missing on {table}.{fk_col}"
    indexdef = row["indexdef"]
    # Non-unique partial index (NULL-dominant). If this ever becomes UNIQUE
    # the design is broken -- multiple orders CAN share a snapshot.
    assert "UNIQUE" not in indexdef, (
        f"{index_name} must NOT be UNIQUE (orders/edges both reference "
        f"the same snapshot is expected); got: {indexdef}"
    )
    assert f"({fk_col} IS NOT NULL)" in indexdef, (
        f"{index_name} must be partial WHERE ({fk_col} IS NOT NULL); got: {indexdef}"
    )


# =============================================================================
# Group 4: create_order writes the FK column (both paths)
# =============================================================================


def test_create_order_with_orderbook_snapshot_id_persists_fk(
    db_pool: Any, orderbook_parent: Any
) -> None:
    """``create_order(..., orderbook_snapshot_id=N)`` writes N to the row."""
    snapshot_id = orderbook_parent["snapshot_id"]
    market_pk = orderbook_parent["market_pk"]

    order_pk = create_order(
        platform_id="kalshi",
        external_order_id=f"TEST-0063-ORD-{uuid.uuid4().hex[:8]}",
        market_id=market_pk,
        side="yes",
        action="buy",
        requested_price=Decimal("0.5000"),
        requested_quantity=1,
        execution_environment="paper",
        orderbook_snapshot_id=snapshot_id,
    )

    with get_cursor() as cur:
        cur.execute(
            "SELECT orderbook_snapshot_id FROM orders WHERE id = %s",
            (order_pk,),
        )
        row = cur.fetchone()
    assert row is not None, "Order row must exist after create_order"
    assert row["orderbook_snapshot_id"] == snapshot_id, (
        f"create_order did not persist orderbook_snapshot_id; "
        f"expected {snapshot_id}, got {row['orderbook_snapshot_id']!r}"
    )


def test_create_order_without_orderbook_snapshot_id_persists_null(
    db_pool: Any, orderbook_parent: Any
) -> None:
    """Backward-compat: omitting ``orderbook_snapshot_id`` yields NULL.

    This is the load-bearing regression test for #725 item 11. The whole
    design relies on the column being a *forward-compatible addition*;
    every existing caller (and every caller until the orderbook pipeline
    lands) omits the new kwarg. If that path ever writes a non-NULL
    accidental value, the nullable + partial-index assumption breaks.
    """
    market_pk = orderbook_parent["market_pk"]

    order_pk = create_order(
        platform_id="kalshi",
        external_order_id=f"TEST-0063-ORD-NULL-{uuid.uuid4().hex[:8]}",
        market_id=market_pk,
        side="no",
        action="buy",
        requested_price=Decimal("0.5000"),
        requested_quantity=1,
        execution_environment="paper",
        # orderbook_snapshot_id deliberately omitted
    )

    with get_cursor() as cur:
        cur.execute(
            "SELECT orderbook_snapshot_id FROM orders WHERE id = %s",
            (order_pk,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row["orderbook_snapshot_id"] is None, (
        f"create_order without orderbook_snapshot_id must persist NULL; "
        f"got {row['orderbook_snapshot_id']!r}"
    )


# =============================================================================
# Group 5: create_edge writes the FK column (both paths)
# =============================================================================


def test_create_edge_with_orderbook_snapshot_id_persists_fk(
    db_pool: Any, orderbook_parent: Any
) -> None:
    """``create_edge(..., orderbook_snapshot_id=N)`` writes N to the row."""
    snapshot_id = orderbook_parent["snapshot_id"]
    market_pk = orderbook_parent["market_pk"]

    edge_pk = create_edge(
        market_id=market_pk,
        model_id=None,  # edges.model_id is nullable; no probability_model needed
        expected_value=Decimal("0.0500"),
        true_win_probability=Decimal("0.5500"),
        market_implied_probability=Decimal("0.5000"),
        market_price=Decimal("0.5000"),
        execution_environment="paper",
        orderbook_snapshot_id=snapshot_id,
    )

    with get_cursor() as cur:
        cur.execute(
            "SELECT orderbook_snapshot_id FROM edges WHERE id = %s",
            (edge_pk,),
        )
        row = cur.fetchone()
    assert row is not None, "Edge row must exist after create_edge"
    assert row["orderbook_snapshot_id"] == snapshot_id, (
        f"create_edge did not persist orderbook_snapshot_id; "
        f"expected {snapshot_id}, got {row['orderbook_snapshot_id']!r}"
    )


def test_create_edge_without_orderbook_snapshot_id_persists_null(
    db_pool: Any, orderbook_parent: Any
) -> None:
    """Backward-compat: omitting ``orderbook_snapshot_id`` yields NULL."""
    market_pk = orderbook_parent["market_pk"]

    edge_pk = create_edge(
        market_id=market_pk,
        model_id=None,
        expected_value=Decimal("0.0300"),
        true_win_probability=Decimal("0.5300"),
        market_implied_probability=Decimal("0.5000"),
        market_price=Decimal("0.5000"),
        execution_environment="paper",
        # orderbook_snapshot_id deliberately omitted
    )

    with get_cursor() as cur:
        cur.execute(
            "SELECT orderbook_snapshot_id FROM edges WHERE id = %s",
            (edge_pk,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row["orderbook_snapshot_id"] is None, (
        f"create_edge without orderbook_snapshot_id must persist NULL; "
        f"got {row['orderbook_snapshot_id']!r}"
    )


# =============================================================================
# Group 6: ON DELETE RESTRICT is enforced at runtime
# =============================================================================


def test_delete_orderbook_snapshot_blocked_when_order_references_it(
    db_pool: Any, orderbook_parent: Any
) -> None:
    """RESTRICT semantics: parent DELETE fails while an order references it.

    This is the whole point of RESTRICT over SET NULL -- provenance must
    not be silently severed. The test attempts to DELETE the parent
    ``orderbook_snapshots`` row while an order with
    ``orderbook_snapshot_id = <parent.id>`` exists, and asserts that
    psycopg2 raises ``ForeignKeyViolation``.
    """
    snapshot_id = orderbook_parent["snapshot_id"]
    market_pk = orderbook_parent["market_pk"]

    create_order(
        platform_id="kalshi",
        external_order_id=f"TEST-0063-RESTRICT-ORD-{uuid.uuid4().hex[:8]}",
        market_id=market_pk,
        side="yes",
        action="buy",
        requested_price=Decimal("0.5000"),
        requested_quantity=1,
        execution_environment="paper",
        orderbook_snapshot_id=snapshot_id,
    )

    with pytest.raises((psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation)):
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM orderbook_snapshots WHERE id = %s",
                (snapshot_id,),
            )

    # Assert the parent row actually survived the blocked DELETE.
    # RESTRICT raises before the delete commits, so the snapshot must
    # still exist -- the whole point of RESTRICT over CASCADE is that
    # provenance rows are preserved, not silently destroyed.
    result = fetch_one(
        "SELECT COUNT(*) AS c FROM orderbook_snapshots WHERE id = %s",
        (snapshot_id,),
    )
    assert result is not None
    assert result["c"] == 1, "RESTRICT should have preserved the parent row"


def test_delete_orderbook_snapshot_blocked_when_edge_references_it(
    db_pool: Any, orderbook_parent: Any
) -> None:
    """RESTRICT semantics: parent DELETE fails while an edge references it."""
    snapshot_id = orderbook_parent["snapshot_id"]
    market_pk = orderbook_parent["market_pk"]

    create_edge(
        market_id=market_pk,
        model_id=None,
        expected_value=Decimal("0.0500"),
        true_win_probability=Decimal("0.5500"),
        market_implied_probability=Decimal("0.5000"),
        market_price=Decimal("0.5000"),
        execution_environment="paper",
        orderbook_snapshot_id=snapshot_id,
    )

    with pytest.raises((psycopg2.errors.ForeignKeyViolation, psycopg2.errors.RestrictViolation)):
        with get_cursor(commit=True) as cur:
            cur.execute(
                "DELETE FROM orderbook_snapshots WHERE id = %s",
                (snapshot_id,),
            )

    # Assert the parent row actually survived the blocked DELETE (see
    # the orders sibling above for rationale).
    result = fetch_one(
        "SELECT COUNT(*) AS c FROM orderbook_snapshots WHERE id = %s",
        (snapshot_id,),
    )
    assert result is not None
    assert result["c"] == 1, "RESTRICT should have preserved the parent row"


# =============================================================================
# Group 7: View parity -- current_edges exposes orderbook_snapshot_id
# =============================================================================


def test_current_edges_view_includes_orderbook_snapshot_id(db_pool: Any) -> None:
    """``current_edges`` view must expose ``orderbook_snapshot_id`` post-0063.

    Pattern 38: ``SELECT * FROM edges`` views bind their column list at
    view-creation time. If a migration appends a column to ``edges``
    without re-creating the dependent view, the new column is silently
    dropped from downstream queries against the view. Migration 0063
    must DROP + CREATE OR REPLACE ``current_edges`` around the
    ``ALTER TABLE edges ADD COLUMN orderbook_snapshot_id`` to avoid this
    drift.

    This test asserts the outcome: the view definition -- as normalized
    and re-emitted by ``information_schema.views.view_definition`` --
    must contain the literal ``orderbook_snapshot_id`` identifier. If a
    future migration regresses by appending to ``edges`` without
    re-creating the view, this test fails loudly.
    """
    result = fetch_one(
        """
        SELECT view_definition
        FROM information_schema.views
        WHERE table_name = 'current_edges'
          AND table_schema = 'public'
        """
    )
    assert result is not None, "current_edges view is missing from public schema"
    view_def = result["view_definition"]
    assert "orderbook_snapshot_id" in view_def, (
        "current_edges view definition does not expose "
        "orderbook_snapshot_id -- Pattern 38 view-drift regression. "
        f"Actual view definition: {view_def!r}"
    )
