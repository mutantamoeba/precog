"""Integration tests for #911 — ``update_edge_outcome`` void-outcome fix.

Before #911, ``update_edge_outcome`` hardcoded ``edge_status = 'settled'``
for every resolved outcome, including ``'void'``. This forced a semantic
contradiction: a void edge had ``actual_outcome='void'`` but
``edge_status='settled'`` — two columns carrying contradictory lifecycle
information. The ``edges_edge_status_check`` CHECK constraint accepts
``'void'`` as a first-class status, so the hardcode was unnecessary.

The fix uses a CASE expression so ``'void'`` outcomes set
``edge_status='void'`` while ``'yes'`` / ``'no'`` / ``'unresolved'``
continue to set ``edge_status='settled'``. These tests lock in the fix
and guard the yes/no regression surface.

Issues: #911
Scope: ``'void' → 'void'`` only. The ``'unresolved'`` path is a separate
    design question (does an unresolved edge belong under 'settled'?) and
    is intentionally not touched here.
Markers:
    @pytest.mark.integration: real DB required (test DB via conftest.db_pool)
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_analytics import update_edge_outcome

# Unique test sentinels — filter each assertion by edge_key so parallel
# tests and residual rows do not contaminate the SELECT.
_TEST_TICKER = "TEST-911-VOID-STATUS-MKT"
_EDGE_KEY_VOID = "TEST-911-VOID"
_EDGE_KEY_YES = "TEST-911-YES"
_EDGE_KEY_NO = "TEST-911-NO"


# =============================================================================
# Fixture
# =============================================================================


@pytest.fixture
def seeded_market(db_pool: Any) -> Any:
    """Seed a minimal market row + teardown for #911 update_edge_outcome tests.

    Yields the integer surrogate PK of the seeded market. Uses
    ``get_cursor(commit=True)`` so rows persist across subsequent edge
    INSERT / UPDATE transactions in each test body. Teardown deletes the
    market and all its children (including any seeded edges) via dynamic
    FK discovery.
    """
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    # --- Setup ---------------------------------------------------------------
    with get_cursor(commit=True) as cur:
        # RESTRICT-safe cleanup of any residual state.
        delete_market_with_children(cur, "ticker = %s", (_TEST_TICKER,))

        # Inline INSERT with TEMP→MKT-{id} two-step for market_key (0062
        # #791 made market_key NOT NULL + UNIQUE). This test verifies
        # update_edge_outcome, not market creation semantics — raw INSERT
        # keeps the test focused.
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
                "Issue 911 update_edge_outcome void-status test market",
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


def _insert_detected_edge(market_pk: int, edge_key: str) -> int:
    """Seed one ``edges`` row in the ``'detected'`` pre-settlement state.

    Committed immediately so the subsequent ``update_edge_outcome`` call
    observes the row under its own MVCC snapshot. Returns the surrogate
    PK (``edges.id``) for passing to the function under test.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO edges (
                edge_key, market_id, model_id,
                expected_value, true_win_probability,
                market_implied_probability, market_price,
                execution_environment, edge_status,
                actual_outcome, settlement_value, resolved_at,
                row_current_ind, row_start_ts
            )
            VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                NULL, NULL, NULL,
                TRUE, NOW()
            )
            RETURNING id
            """,
            (
                edge_key,
                market_pk,
                None,  # model_id nullable
                Decimal("0.2000"),  # expected_value
                Decimal("0.5000"),  # true_win_probability
                Decimal("0.3000"),  # market_implied_probability
                Decimal("0.3000"),  # market_price
                "paper",
                "detected",
            ),
        )
        return int(cur.fetchone()["id"])


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
def test_update_edge_outcome_void_sets_edge_status_void(seeded_market: int) -> None:
    """#911 core fix: actual_outcome='void' → edge_status='void' (not 'settled').

    Pre-#911, the function hardcoded ``edge_status = 'settled'`` for every
    resolved outcome, contradicting the CHECK-constraint-accepted ``'void'``
    status. The fix uses a CASE expression so void routes to void.
    """
    edge_pk = _insert_detected_edge(seeded_market, _EDGE_KEY_VOID)

    success = update_edge_outcome(
        edge_pk=edge_pk,
        actual_outcome="void",
        settlement_value=Decimal("0.0000"),
    )

    assert success is True, "update_edge_outcome should return True on row update"

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT edge_status, actual_outcome, settlement_value "
            "FROM edges WHERE id = %s AND row_current_ind = TRUE",
            (edge_pk,),
        )
        row = cur.fetchone()

    assert row is not None, f"Expected a current row for edge_pk={edge_pk}"
    # Core #911 assertion: void outcome now produces void status.
    assert row["edge_status"] == "void", (
        f"void outcome should set edge_status='void', got {row['edge_status']!r} "
        "(pre-#911 bug returned 'settled')"
    )
    assert row["actual_outcome"] == "void"
    assert row["settlement_value"] == Decimal("0.0000")


@pytest.mark.integration
def test_update_edge_outcome_yes_still_sets_settled(seeded_market: int) -> None:
    """Regression: actual_outcome='yes' continues to set edge_status='settled'.

    The CASE expression must preserve the non-void path. This test guards
    against a future refactor accidentally routing 'yes' to 'void' or
    otherwise breaking the winning-outcome lifecycle transition.
    """
    edge_pk = _insert_detected_edge(seeded_market, _EDGE_KEY_YES)

    success = update_edge_outcome(
        edge_pk=edge_pk,
        actual_outcome="yes",
        settlement_value=Decimal("1.0000"),
    )

    assert success is True

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT edge_status, actual_outcome, settlement_value "
            "FROM edges WHERE id = %s AND row_current_ind = TRUE",
            (edge_pk,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row["edge_status"] == "settled", (
        f"yes outcome should set edge_status='settled', got {row['edge_status']!r}"
    )
    assert row["actual_outcome"] == "yes"
    assert row["settlement_value"] == Decimal("1.0000")


@pytest.mark.integration
def test_update_edge_outcome_no_still_sets_settled(seeded_market: int) -> None:
    """Regression: actual_outcome='no' continues to set edge_status='settled'.

    Completes the non-void binary-outcome coverage. The losing YES-side
    position still transitions to 'settled' — only 'void' diverges from
    the 'settled' sink.
    """
    edge_pk = _insert_detected_edge(seeded_market, _EDGE_KEY_NO)

    success = update_edge_outcome(
        edge_pk=edge_pk,
        actual_outcome="no",
        settlement_value=Decimal("0.0000"),
    )

    assert success is True

    with get_cursor(commit=False) as cur:
        cur.execute(
            "SELECT edge_status, actual_outcome, settlement_value "
            "FROM edges WHERE id = %s AND row_current_ind = TRUE",
            (edge_pk,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row["edge_status"] == "settled", (
        f"no outcome should set edge_status='settled', got {row['edge_status']!r}"
    )
    assert row["actual_outcome"] == "no"
    assert row["settlement_value"] == Decimal("0.0000")
