"""Shared test data cleanup helpers for RESTRICT FK semantics.

Migration 0057 converted all CASCADE/SET NULL FKs to ON DELETE RESTRICT.
Test fixtures can no longer rely on CASCADE to auto-delete children when
deleting parents. This module provides cleanup functions that delete in
strict reverse FK order.

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
# FK dependency tiers (leaf → root)
# =============================================================================
# Tier 1: Leaf tables (nothing references these)
# Tier 2: Tables whose only children are in Tier 1
# Tier 3: Core tables (children in Tier 1-2)
# Tier 4: Dimension tables (children in Tier 1-3)
# Tier 5: Root tables (platforms)

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
    tables (teams, venues, series, platforms) or seed data — use the
    scoped functions for those.
    """
    for table in _TIER_1_TABLES:
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608
    for table in _TIER_2_TABLES:
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608
    for table in _TIER_3_TABLES:
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608


def delete_market_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete market(s) and all children in reverse FK order.

    Args:
        cursor: Database cursor.
        where_clause: SQL WHERE clause for the markets table
            (e.g., "ticker = %s" or "platform_id = %s").
        params: Parameters for the WHERE clause.

    Example:
        delete_market_with_children(cur, "ticker = %s", ("TEST-MKT",))
        delete_market_with_children(cur, "platform_id = %s", ("kalshi",))
    """
    # Get market IDs matching the condition
    cursor.execute(
        f"SELECT id FROM markets WHERE {where_clause}",  # noqa: S608
        params,
    )
    market_ids = [row["id"] for row in cursor.fetchall()]
    if not market_ids:
        return

    placeholders = ",".join(["%s"] * len(market_ids))

    # Tables referencing markets via market_internal_id (from migrations 0022, 0028, 0034)
    for table in (
        "orderbook_snapshots",
        "market_trades",
        "edges",
        "settlements",
    ):
        cursor.execute(
            f"DELETE FROM {table} WHERE market_internal_id IN ({placeholders})",  # noqa: S608
            tuple(market_ids),
        )

    # Tables that use market_id (from migrations 0021, 0027, 0031)
    # NOTE: temporal_alignment must be deleted BEFORE market_snapshots
    # because it has an FK to market_snapshots(id)
    cursor.execute(
        f"DELETE FROM temporal_alignment WHERE market_id IN ({placeholders})",  # noqa: S608
        tuple(market_ids),
    )
    cursor.execute(
        f"DELETE FROM predictions WHERE market_id IN ({placeholders})",  # noqa: S608
        tuple(market_ids),
    )
    cursor.execute(
        f"DELETE FROM market_snapshots WHERE market_id IN ({placeholders})",  # noqa: S608
        tuple(market_ids),
    )

    # Orders reference markets AND have their own children
    cursor.execute(
        f"SELECT id FROM orders WHERE market_internal_id IN ({placeholders})",  # noqa: S608
        tuple(market_ids),
    )
    order_ids = [row["id"] for row in cursor.fetchall()]
    if order_ids:
        order_placeholders = ",".join(["%s"] * len(order_ids))
        cursor.execute(
            f"DELETE FROM account_ledger WHERE order_id IN ({order_placeholders})",  # noqa: S608
            tuple(order_ids),
        )
        cursor.execute(
            f"DELETE FROM trades WHERE order_id IN ({order_placeholders})",  # noqa: S608
            tuple(order_ids),
        )
        cursor.execute(
            f"DELETE FROM orders WHERE id IN ({order_placeholders})",  # noqa: S608
            tuple(order_ids),
        )

    # Positions reference markets AND have their own children
    cursor.execute(
        f"SELECT id FROM positions WHERE market_internal_id IN ({placeholders})",  # noqa: S608
        tuple(market_ids),
    )
    position_ids = [row["id"] for row in cursor.fetchall()]
    if position_ids:
        pos_placeholders = ",".join(["%s"] * len(position_ids))
        cursor.execute(
            f"DELETE FROM exit_attempts WHERE position_internal_id IN ({pos_placeholders})",  # noqa: S608
            tuple(position_ids),
        )
        cursor.execute(
            f"DELETE FROM position_exits WHERE position_internal_id IN ({pos_placeholders})",  # noqa: S608
            tuple(position_ids),
        )
        cursor.execute(
            f"DELETE FROM positions WHERE id IN ({pos_placeholders})",  # noqa: S608
            tuple(position_ids),
        )

    # Now safe to delete markets
    cursor.execute(
        f"DELETE FROM markets WHERE {where_clause}",  # noqa: S608
        params,
    )


def delete_event_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete event(s) and all children (markets + their subtrees) in reverse FK order."""
    cursor.execute(
        f"SELECT id FROM events WHERE {where_clause}",  # noqa: S608
        params,
    )
    event_ids = [row["id"] for row in cursor.fetchall()]
    if not event_ids:
        return

    # Markets reference events via event_internal_id
    for eid in event_ids:
        delete_market_with_children(cursor, "event_internal_id = %s", (eid,))

    # Now safe to delete events
    cursor.execute(
        f"DELETE FROM events WHERE {where_clause}",  # noqa: S608
        params,
    )


def delete_venue_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete venue(s) after clearing FK references from games/game_states."""
    cursor.execute(
        f"SELECT venue_id FROM venues WHERE {where_clause}",  # noqa: S608
        params,
    )
    venue_ids = [row["venue_id"] for row in cursor.fetchall()]
    if not venue_ids:
        return

    placeholders = ",".join(["%s"] * len(venue_ids))

    # Games reference venues via venue_id — SET NULL the FK (games are not owned by venues)
    # With RESTRICT we can't delete venues if games reference them.
    # Clear the venue_id FK on games first.
    cursor.execute(
        f"UPDATE games SET venue_id = NULL WHERE venue_id IN ({placeholders})",  # noqa: S608
        tuple(venue_ids),
    )
    # game_states also reference venues
    cursor.execute(
        f"UPDATE game_states SET venue_id = NULL WHERE venue_id IN ({placeholders})",  # noqa: S608
        tuple(venue_ids),
    )

    cursor.execute(
        f"DELETE FROM venues WHERE {where_clause}",  # noqa: S608
        params,
    )


def delete_platform_with_children(
    cursor: Any,
    where_clause: str,
    params: tuple[Any, ...] | None = None,
) -> None:
    """Delete platform(s) and everything underneath in reverse FK order.

    This is the nuclear option — equivalent to the old CASCADE behavior
    but explicit about what gets deleted.
    """
    cursor.execute(
        f"SELECT platform_id FROM platforms WHERE {where_clause}",  # noqa: S608
        params,
    )
    platform_ids = [row["platform_id"] for row in cursor.fetchall()]
    if not platform_ids:
        return

    for pid in platform_ids:
        # Delete markets and all their subtrees
        delete_market_with_children(cursor, "platform_id = %s", (pid,))
        # Delete events
        cursor.execute("DELETE FROM events WHERE platform_id = %s", (pid,))
        # Delete series
        cursor.execute("DELETE FROM series WHERE platform_id = %s", (pid,))
        # Delete strategies and models (they reference platforms)
        cursor.execute("DELETE FROM strategies WHERE platform_id = %s", (pid,))
        # Delete account_balance
        cursor.execute("DELETE FROM account_balance WHERE platform_id = %s", (pid,))

    cursor.execute(
        f"DELETE FROM platforms WHERE {where_clause}",  # noqa: S608
        params,
    )
