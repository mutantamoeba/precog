"""Shared test data cleanup helpers for RESTRICT FK semantics.

Migration 0057 converted all CASCADE/SET NULL FKs to ON DELETE RESTRICT.
Test fixtures can no longer rely on CASCADE to auto-delete children when
deleting parents. This module provides cleanup functions that delete in
strict reverse FK order.

The helpers in this file use **dynamic FK discovery** via
``information_schema`` rather than hardcoded child-table lists. This
means new FKs added by future migrations are picked up automatically,
and column-name drift (e.g., ``market_internal_id`` vs ``market_id`` vs
a future rename to ``market_id`` everywhere) is handled without touching
this file. The first hand-rolled version of these helpers broke twice in
session 48 because it hardcoded column names that did not match reality
in all child tables -- #757 is the refactor that made the DB the source
of truth for FK topology.

Per-FK handling respects ``delete_rule``:

- ``RESTRICT`` / ``NO ACTION`` -> recursively delete children, then delete parent
- ``SET NULL`` -> ``UPDATE child SET fk_col = NULL`` (parent can then delete)
- ``CASCADE`` -> PostgreSQL handles the child delete when we delete the parent;
  we could skip explicit handling, but we still walk the child for transitive
  cleanup in case the test relies on a specific intermediate state
- ``SET DEFAULT`` -> not currently used in the precog schema; raises NotImplementedError
  if encountered so we fail loudly rather than silently mishandle it

Usage:
    from tests.fixtures.cleanup_helpers import (
        delete_all_test_data,
        delete_market_with_children,
    )

    # In a fixture:
    delete_all_test_data(cursor)

    # Scoped cleanup:
    delete_market_with_children(cursor, "ticker = %s", ("TEST-MKT",))
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# Dynamic FK discovery primitives
# =============================================================================

_PK_CACHE: dict[str, str | None] = {}
_CHILDREN_CACHE: dict[tuple[str, str], list[tuple[str, str, str]]] = {}


def _clear_fk_caches() -> None:
    """Reset the FK discovery caches.

    The caches are scoped to a process -- migrations between tests in the
    same process are rare, but test fixtures that apply and revert schema
    changes in a single run (e.g., downgrade round-trip tests) can leave
    stale entries. Tests that manipulate schema should call this before
    using the cleanup helpers.
    """
    _PK_CACHE.clear()
    _CHILDREN_CACHE.clear()


def _discover_primary_key(cursor: Any, table: str) -> str | None:
    """Return the single-column primary-key name for ``table``.

    Returns ``None`` for composite PKs or tables without a PK. The cleanup
    helpers only recurse into tables that have a simple scalar PK (the
    overwhelmingly common case in the precog schema); composite-PK tables
    must not have children that FK into them, which is enforced by the
    schema design.
    """
    if table in _PK_CACHE:
        return _PK_CACHE[table]

    cursor.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_name = %s
            AND tc.table_schema = 'public'
        ORDER BY kcu.ordinal_position
        """,
        (table,),
    )
    rows = cursor.fetchall()
    pk: str | None = rows[0]["column_name"] if len(rows) == 1 else None
    _PK_CACHE[table] = pk
    return pk


def _discover_direct_children(
    cursor: Any,
    parent_table: str,
    parent_column: str,
) -> list[tuple[str, str, str]]:
    """Return direct FK children of ``parent_table.parent_column``.

    Each entry is ``(child_table, child_column, delete_rule)`` where
    ``delete_rule`` is one of ``RESTRICT``, ``NO ACTION``, ``CASCADE``,
    ``SET NULL``, ``SET DEFAULT``.

    Ordering is by (child_table, child_column) so that the returned list
    is deterministic across runs, which makes test debugging easier when
    a cleanup chain fails partway through.
    """
    cache_key = (parent_table, parent_column)
    if cache_key in _CHILDREN_CACHE:
        return _CHILDREN_CACHE[cache_key]

    cursor.execute(
        """
        SELECT
            tc.table_name AS child_table,
            kcu.column_name AS child_column,
            rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            AND ccu.table_name = %s
            AND ccu.column_name = %s
        ORDER BY tc.table_name, kcu.column_name
        """,
        (parent_table, parent_column),
    )
    children: list[tuple[str, str, str]] = [
        (row["child_table"], row["child_column"], row["delete_rule"]) for row in cursor.fetchall()
    ]
    _CHILDREN_CACHE[cache_key] = children
    return children


def _delete_cascade(
    cursor: Any,
    table: str,
    column: str,
    ids: list[Any],
    _visited: set[tuple[str, str]] | None = None,
) -> None:
    """Recursively delete ``ids`` from ``table.column`` and all transitive children.

    Walks the FK graph via ``information_schema`` and deletes deepest
    children first. For SET NULL children, the FK column is cleared
    instead of deleting the child row. Cycles are broken by the
    ``_visited`` set so that self-referential FKs or unusual schema
    patterns do not cause infinite recursion.

    Parameters mirror the tuple returned by ``_discover_direct_children``
    so the caller can drive the cascade from either direct IDs (initial
    call) or a discovered child relationship (recursive call).
    """
    if not ids:
        return
    if _visited is None:
        _visited = set()
    visit_key = (table, column)
    if visit_key in _visited:
        return
    _visited.add(visit_key)

    children = _discover_direct_children(cursor, table, column)

    for child_table, child_column, delete_rule in children:
        if delete_rule == "SET NULL":
            # Clear the reference instead of deleting the row.
            placeholders = ",".join(["%s"] * len(ids))
            cursor.execute(
                f"UPDATE {child_table} SET {child_column} = NULL "  # noqa: S608
                f"WHERE {child_column} IN ({placeholders})",
                tuple(ids),
            )
            continue

        if delete_rule == "SET DEFAULT":
            raise NotImplementedError(
                f"FK {child_table}.{child_column} uses SET DEFAULT, which is "
                f"not handled by the cleanup helper. Add explicit support if "
                f"the schema introduces SET DEFAULT FKs."
            )

        # RESTRICT / NO ACTION / CASCADE all require deleting the child row.
        # For CASCADE we could skip and rely on PostgreSQL, but walking
        # transitively is cheap, keeps the delete order deterministic, and
        # guards against partial-CASCADE schemas where some FKs are CASCADE
        # and others are RESTRICT under the same parent.

        # Discover the child's own children (grandchildren of the root)
        # by looking up the child's PK and recursing.
        child_pk = _discover_primary_key(cursor, child_table)
        if child_pk is not None and child_pk != child_column:
            # Fetch the child row IDs that match our parent ids, then
            # recursively cascade into the child's subtree before deleting.
            placeholders = ",".join(["%s"] * len(ids))
            cursor.execute(
                f"SELECT {child_pk} FROM {child_table} "  # noqa: S608
                f"WHERE {child_column} IN ({placeholders})",
                tuple(ids),
            )
            child_ids = [row[child_pk] for row in cursor.fetchall()]
            if child_ids:
                _delete_cascade(cursor, child_table, child_pk, child_ids, _visited)

        # Now safe to delete the child rows referencing the parent ids.
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"DELETE FROM {child_table} "  # noqa: S608
            f"WHERE {child_column} IN ({placeholders})",
            tuple(ids),
        )

    # Finally delete the parent rows themselves.
    placeholders = ",".join(["%s"] * len(ids))
    cursor.execute(
        f"DELETE FROM {table} WHERE {column} IN ({placeholders})",  # noqa: S608
        tuple(ids),
    )


# =============================================================================
# Bulk-clear of transactional tables
# =============================================================================
# The tiered approach is retained for ``delete_all_test_data`` because
# the goal there is "wipe transactional state between tests" rather than
# "delete a specific parent and everything beneath it." Dynamic discovery
# adds complexity without benefit for a full-tier wipe, and the table
# lists below are self-contained and easy to audit.

_TIER_1_TABLES = (
    "temporal_alignment",
    "exit_attempts",
    "position_exits",
    "account_ledger",
    "settlements",
    "market_trades",
    "orderbook_snapshots",
    "elo_calculation_log",
    "predictions",
    "backtesting_runs",
    "evaluation_runs",
    "historical_epa",
    "historical_stats",
    "historical_rankings",
    "game_odds",
    "team_rankings",
    "external_team_codes",
)

_TIER_2_TABLES = (
    "trades",
    "orders",
    "market_snapshots",
)

_TIER_3_TABLES = (
    "edges",
    "positions",
    "account_balance",
)


def delete_all_test_data(cursor: Any) -> None:
    """Delete ALL data from transactional tables in strict reverse FK order.

    Safe for RESTRICT semantics. Does NOT delete from dimension/reference
    tables (teams, venues, series, platforms) or seed data -- use the
    scoped functions for those.

    This retains the static tier approach because the goal is a full-
    tier wipe, not a scoped delete. For scoped deletes from a specific
    parent, use ``delete_market_with_children``, ``delete_event_with_children``,
    ``delete_venue_with_children``, or ``delete_platform_with_children``
    which all use dynamic FK discovery.

    NOTE: ``games`` and ``game_states`` are intentionally omitted from
    the tier lists because no current test creates rows in them via
    this helper path. Tests that populate those tables must clean them
    up explicitly. Tracked by #760.
    """
    for table in _TIER_1_TABLES:
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608
    for table in _TIER_2_TABLES:
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608
    for table in _TIER_3_TABLES:
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608


# =============================================================================
# Scoped cascading delete functions
# =============================================================================


def delete_market_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete market(s) and all children via dynamic FK discovery.

    Args:
        cursor: Database cursor.
        where_clause: SQL WHERE clause for the markets table
            (e.g., "ticker = %s" or "platform_id = %s").
        params: Parameters for the WHERE clause.

    Example:
        delete_market_with_children(cur, "ticker = %s", ("TEST-MKT",))
        delete_market_with_children(cur, "platform_id = %s", ("kalshi",))
    """
    cursor.execute(
        f"SELECT id FROM markets WHERE {where_clause}",  # noqa: S608
        params,
    )
    market_ids = [row["id"] for row in cursor.fetchall()]
    if not market_ids:
        return

    _delete_cascade(cursor, "markets", "id", market_ids)


def delete_event_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete event(s) and all children via dynamic FK discovery."""
    cursor.execute(
        f"SELECT id FROM events WHERE {where_clause}",  # noqa: S608
        params,
    )
    event_ids = [row["id"] for row in cursor.fetchall()]
    if not event_ids:
        return

    _delete_cascade(cursor, "events", "id", event_ids)


def delete_venue_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete venue(s) via dynamic FK discovery.

    In the current schema, ``games.venue_id`` is ``ON DELETE SET NULL``
    and ``game_states.venue_id`` is ``ON DELETE NO ACTION``. Neither is
    listed in migration 0057 because both were already RESTRICT-compliant.
    ``_delete_cascade`` handles both rules automatically: SET NULL becomes
    an UPDATE to clear the reference, NO ACTION triggers recursive delete
    of the child rows -- but since tests rarely populate ``game_states``
    through this path, the NO ACTION branch is usually a no-op.
    """
    cursor.execute(
        f"SELECT venue_id FROM venues WHERE {where_clause}",  # noqa: S608
        params,
    )
    venue_ids = [row["venue_id"] for row in cursor.fetchall()]
    if not venue_ids:
        return

    _delete_cascade(cursor, "venues", "venue_id", venue_ids)


def delete_platform_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete platform(s) and everything underneath via dynamic FK discovery.

    This is the nuclear option -- equivalent to the old CASCADE behavior
    but explicit about what gets deleted. Walks the full FK subtree
    rooted at ``platforms.platform_id``.
    """
    cursor.execute(
        f"SELECT platform_id FROM platforms WHERE {where_clause}",  # noqa: S608
        params,
    )
    platform_ids = [row["platform_id"] for row in cursor.fetchall()]
    if not platform_ids:
        return

    _delete_cascade(cursor, "platforms", "platform_id", platform_ids)
