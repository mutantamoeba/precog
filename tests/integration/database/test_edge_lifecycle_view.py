"""Integration tests for the ``edge_lifecycle`` view's ``realized_pnl`` math.

Migration 0065 (#909) fixed a sign-inversion in the ``'no'`` branch of the
view's realized-P&L CASE expression. The broken form had lived through
migrations 0023, 0024, and 0058 because the unit test coverage of
``edge_lifecycle`` was entirely MOCK-ONLY — the actual view math was never
exercised against a real database.

This file is the tripwire. Any future migration that re-creates
``edge_lifecycle`` (as 0058 did) will break these tests if it reintroduces
the inversion. The test closes the systemic gap that let #909 live for 42
migrations, not just the single instance.

The fix (for a YES-side position — edge detection = buy YES):
    - YES outcome: gain = settlement_value (1.0) - market_price_paid
    - NO outcome:  loss = settlement_value (0.0) - market_price_paid  (negative)

Both branches use ``(settlement_value - market_price)``; the sign handles
the loss naturally.

Issues: #909
Design review: Holden (session 66) — memory/design_review_909_holden_memo.md
Migration: 0065_fix_edge_lifecycle_realized_pnl.py
Markers:
    @pytest.mark.integration: real DB required (test DB via conftest.db_pool)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor

# Unique test sentinels — filter each assertion by edge_key so parallel
# tests and residual rows don't contaminate the SELECT.
_TEST_TICKER = "TEST-INT-909-EDGE-LIFECYCLE-MKT"
_EDGE_KEY_YES = "TEST-YES-909"
_EDGE_KEY_NO = "TEST-NO-909"
_EDGE_KEY_NULL = "TEST-NULL-909"


# =============================================================================
# Fixture
# =============================================================================


@pytest.fixture
def seeded_market(db_pool: Any) -> Any:
    """Seed a minimal market row + teardown for edge_lifecycle view tests.

    Yields the integer surrogate PK of the seeded market. The fixture uses
    ``get_cursor(commit=True)`` so rows persist across the subsequent edge
    INSERT transactions in each test body. Teardown deletes the market and
    all its children (including the seeded edges) via dynamic FK discovery.
    """
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    # --- Setup ---------------------------------------------------------------
    with get_cursor(commit=True) as cur:
        # RESTRICT-safe cleanup of any residual state.
        delete_market_with_children(cur, "ticker = %s", (_TEST_TICKER,))

        # Inline INSERT with TEMP→MKT-{id} two-step for market_key (0062 #791
        # made market_key NOT NULL + UNIQUE). This test verifies VIEW math,
        # not market creation semantics — raw INSERT keeps the test focused.
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_id, external_id, ticker, title,
                market_type, status, market_key
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                None,
                f"{_TEST_TICKER}-EXT",
                _TEST_TICKER,
                "Issue 909 edge_lifecycle view test market",
                "binary",
                "open",
                f"TEMP-{uuid.uuid4()}",
            ),
        )
        market_pk = cur.fetchone()["id"]
        cur.execute(
            "UPDATE markets SET market_key = %s WHERE id = %s",
            (f"MKT-{market_pk}", market_pk),
        )

    yield market_pk

    # --- Teardown ------------------------------------------------------------
    try:
        with get_cursor(commit=True) as cur:
            delete_market_with_children(cur, "id = %s", (market_pk,))
    except Exception:
        # Best-effort; do not mask the actual test outcome.
        pass


def _insert_edge(
    market_pk: int,
    edge_key: str,
    actual_outcome: str | None,
    settlement_value: Decimal | None,
    market_price: Decimal,
) -> None:
    """Seed one ``edges`` row with ``row_current_ind=TRUE`` for the view.

    Committed immediately so the subsequent SELECT from the view observes
    the row under its own MVCC snapshot. ``edge_status`` uses the valid
    domain values per ``edges_edge_status_check`` — ``'settled'`` for
    resolved outcomes, ``'detected'`` for the NULL/unresolved case.
    """
    # Match the CHECK constraint: resolved → 'settled', unresolved → 'detected'.
    edge_status = "settled" if actual_outcome is not None else "detected"

    # NULL resolved_at when unresolved (matches semantic + view ELSE branch).
    resolved_at_sql = "NOW()" if actual_outcome is not None else "NULL"

    with get_cursor(commit=True) as cur:
        cur.execute(
            f"""
            INSERT INTO edges (
                edge_key, market_id, model_id,
                expected_value, true_win_probability,
                market_implied_probability, market_price,
                actual_outcome, settlement_value, resolved_at,
                execution_environment, edge_status,
                row_current_ind, row_start_ts
            )
            VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, {resolved_at_sql},
                %s, %s,
                TRUE, NOW()
            )
            """,  # noqa: S608 -- edge_status + resolved_at_sql are internal literals
            (
                edge_key,
                market_pk,
                None,  # model_id nullable
                Decimal("0.2000"),  # expected_value
                Decimal("0.5000"),  # true_win_probability
                Decimal("0.3000"),  # market_implied_probability
                market_price,
                actual_outcome,
                settlement_value,
                "paper",
                edge_status,
            ),
        )


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
def test_edge_lifecycle_realized_pnl_yes_outcome(seeded_market: int) -> None:
    """YES outcome: settlement_value=1.0, market_price=0.3 → realized_pnl=+0.7.

    The YES branch is unchanged by migration 0065 — this test establishes
    the baseline that the fix does not regress the winning path.
    """
    _insert_edge(
        market_pk=seeded_market,
        edge_key=_EDGE_KEY_YES,
        actual_outcome="yes",
        settlement_value=Decimal("1.0"),
        market_price=Decimal("0.3"),
    )

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT realized_pnl FROM edge_lifecycle WHERE edge_key = %s",
            (_EDGE_KEY_YES,),
        )
        row = cur.fetchone()

    assert row is not None, f"Expected a row for edge_key={_EDGE_KEY_YES!r}"
    # +0.7: profit on winning YES (settlement 1.0 - premium paid 0.3).
    assert row["realized_pnl"] == Decimal("0.7"), (
        f"YES-win realized_pnl should be +0.7, got {row['realized_pnl']}"
    )


@pytest.mark.integration
def test_edge_lifecycle_realized_pnl_no_outcome(seeded_market: int) -> None:
    """NO outcome: settlement_value=0.0, market_price=0.3 → realized_pnl=-0.3.

    CRITICAL: the sign on the NO-loss branch. Pre-#909 this returned +0.3
    (wrong — fake gains on lost YES-side positions). A YES-side position
    that resolves NO loses the full premium paid: settlement 0.0 - 0.3 = -0.3.
    """
    _insert_edge(
        market_pk=seeded_market,
        edge_key=_EDGE_KEY_NO,
        actual_outcome="no",
        settlement_value=Decimal("0.0"),
        market_price=Decimal("0.3"),
    )

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT realized_pnl FROM edge_lifecycle WHERE edge_key = %s",
            (_EDGE_KEY_NO,),
        )
        row = cur.fetchone()

    assert row is not None, f"Expected a row for edge_key={_EDGE_KEY_NO!r}"
    # -0.3: loss on NO outcome (settlement 0.0 - premium paid 0.3).
    # Pre-#909 this was +0.3 (sign-inverted). Tripwire for any future
    # migration that re-creates this view.
    assert row["realized_pnl"] == Decimal("-0.3"), (
        f"NO-loss realized_pnl should be -0.3, got {row['realized_pnl']} "
        "(pre-#909 bug returned +0.3)"
    )


@pytest.mark.integration
def test_edge_lifecycle_realized_pnl_unresolved(seeded_market: int) -> None:
    """Unresolved edge (actual_outcome IS NULL) → realized_pnl IS NULL.

    The ELSE branch of the CASE is unchanged by migration 0065; this test
    asserts the NULL pass-through still works end-to-end on the real view.
    """
    _insert_edge(
        market_pk=seeded_market,
        edge_key=_EDGE_KEY_NULL,
        actual_outcome=None,
        settlement_value=None,
        market_price=Decimal("0.3"),
    )

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT realized_pnl FROM edge_lifecycle WHERE edge_key = %s",
            (_EDGE_KEY_NULL,),
        )
        row = cur.fetchone()

    assert row is not None, f"Expected a row for edge_key={_EDGE_KEY_NULL!r}"
    assert row["realized_pnl"] is None, (
        f"Unresolved edge realized_pnl should be NULL, got {row['realized_pnl']}"
    )
