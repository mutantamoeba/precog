"""Integration tests for the SCD Type 2 copy-forward contract on positions.edge_id.

Migration 0059 (#725) added ``positions.edge_id`` as a nullable FK to
``edges(id)``. The highest risk at land time is that any SCD supersede
path whose INSERT column list omits ``edge_id`` will silently NULL the
provenance FK on the new version — the exact SET NULL behavior 0057
was built to prevent. Design memo: #725 Holden S57 §6 (the "critical
SCD copy-forward risk" section).

This file asserts the contract against a real PostgreSQL database
(testcontainer per ADR-057):

    Given an SCD current row with a non-NULL ``edge_id``,
    When any supersede path fires,
    Then the NEW current version carries the SAME ``edge_id`` forward.

Three supersede paths are covered — one test per path so a regression
in any one path is surfaced immediately with a precise failure signal:

    1. ``update_position_price`` (crud_positions.py line ~598)
    2. ``close_position`` (crud_positions.py line ~810)
    3. ``set_trailing_stop_state`` (crud_positions.py line ~1113)

Why this test uses a real DB (not mocks):
    The Mock Fidelity Rule (protocols.md) explicitly prohibits
    pure-function mocks for SCD code (failure mode A, temporal
    coupling) — the supersede path's read-then-write transaction
    semantics are exactly the thing that broke silently in #629.
    This test fills the same integration gap
    ``test_crud_positions_trailing_stop_integration.py`` filled for
    the trailing-stop rewrite, but for the provenance-FK contract.

Non-goals:
    - Edge-side copy-forward: no SCD supersede path exists for edges
      today; ``edges.market_snapshot_id`` and ``edges.prediction_id``
      are written by ``create_edge`` only (NULL by default), and the
      two live mutators (``update_edge_outcome`` / ``update_edge_status``)
      are direct UPDATEs filtered by ``row_current_ind = TRUE`` (lifecycle
      events, not SCD versions). When a true SCD supersede path is later
      added for edges, the Pattern 49 copy-forward checklist at the top
      of each ``INSERT INTO positions (...)`` call in crud_positions.py
      must be applied there too.
    - ``create_position`` happy-path: covered by every other position
      integration test. The new ``edge_id`` parameter is exercised
      indirectly here via the fixture setup.

Issues: #725 (items 1-7, migration 0059)
Markers:
    @pytest.mark.integration: real DB required (testcontainer per ADR-057)
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_positions import (
    close_position,
    create_position,
    set_trailing_stop_state,
    update_position_price,
)

# Test identifiers reserved for this suite. TEST- prefix so suite-wide
# ``clean_test_data`` regex picks up any orphaned rows.
_TEST_TICKER = "TEST-INT-725-SCD-MKT"
_TEST_POSITION_BK_PREFIX = "TEST-INT-725-POS-"


# =============================================================================
# Fixture
# =============================================================================


@pytest.fixture
def position_with_edge(db_pool: Any) -> Any:
    """Seed market, edge, and open position linked via edge_id; teardown after.

    The fixture creates:
      - a test market,
      - a test ``edges`` row (minimum-required columns; row_current_ind=TRUE),
      - an open position created via ``create_position`` with the new
        ``edge_id`` parameter set to the edge's surrogate id.

    Yields (position_surrogate_id, position_business_key, market_pk, edge_pk)
    so each test can:
      - address the position by its surrogate id (the CRUD entry point),
      - verify state by business key (the SCD chain identifier),
      - assert ``edge_id`` values against the seeded ``edge_pk``.

    Uses ``get_cursor(commit=True)`` so rows survive to the next supersede
    transaction (the supersede helpers commit their own writes).
    """
    position_bk = f"{_TEST_POSITION_BK_PREFIX}1"

    from tests.fixtures.cleanup_helpers import delete_market_with_children

    # --- Setup ---------------------------------------------------------------
    with get_cursor(commit=True) as cur:
        # RESTRICT-safe cleanup of any leftover test state.
        delete_market_with_children(cur, "ticker = %s", (_TEST_TICKER,))

        # Underlying market (positions and edges both FK to markets.id).
        # Migration 0062 (#791): markets.market_key is NOT NULL + UNIQUE.
        # SCD-mechanics test — keep raw INSERT (the surrounding test is
        # verifying SCD supersede semantics on positions/edges, not market
        # creation) and inline the TEMP→MKT-{id} two-step.
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
                "Issue 725 SCD Copy-Forward Market",
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

        # Seed a minimal edge row. All non-NULL columns on edges are either
        # business-identity (edge_key), FK (market_id), or metric fields
        # (expected_value, probabilities, price). Uses a small deterministic
        # set of values so the test's provenance assertions are stable.
        # ``row_current_ind`` is explicitly TRUE so partial indexes accept it.
        cur.execute(
            """
            INSERT INTO edges (
                edge_key, market_id, model_id,
                expected_value, true_win_probability,
                market_implied_probability, market_price,
                execution_environment, edge_status,
                row_current_ind, row_start_ts
            )
            VALUES (
                'TEMP', %s, %s,
                %s, %s, %s, %s,
                %s, 'detected',
                TRUE, NOW()
            )
            RETURNING id
            """,
            (
                market_pk,
                None,  # model_id nullable
                Decimal("0.0500"),
                Decimal("0.6000"),
                Decimal("0.5500"),
                Decimal("0.5500"),
                "paper",
            ),
        )
        edge_pk = cur.fetchone()["id"]

        # Set the proper edge_key now that we know the surrogate.
        cur.execute(
            "UPDATE edges SET edge_key = %s WHERE id = %s",
            (f"EDGE-{edge_pk}", edge_pk),
        )

    # Create the position via the CRUD entry point (exercises the new
    # ``edge_id`` parameter end-to-end). ``create_position`` commits.
    position_surrogate_id = create_position(
        market_id=market_pk,
        strategy_id=None,  # nullable FK
        model_id=None,  # nullable FK
        side="YES",
        quantity=10,
        entry_price=Decimal("0.5000"),
        execution_environment="paper",
        stop_loss_price=Decimal("0.4500"),
        edge_id=edge_pk,
    )

    # Re-key from the auto-assigned ``POS-{id}`` to our deterministic bk
    # so the test can address the chain by a stable business key.
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE positions SET position_key = %s WHERE id = %s",
            (position_bk, position_surrogate_id),
        )

    yield position_surrogate_id, position_bk, market_pk, edge_pk

    # --- Teardown ------------------------------------------------------------
    try:
        with get_cursor(commit=True) as cur:
            delete_market_with_children(cur, "id = %s", (market_pk,))
    except Exception:
        # Best-effort; do not mask the actual test outcome.
        pass


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestPositionsEdgeIdCopyForward:
    """SCD copy-forward contract for ``positions.edge_id`` (migration 0059, #725).

    Each test exercises one supersede path end-to-end against a real
    database. The common assertion shape is:

        - after supersede, exactly 2 rows exist for the business key
          (1 historical, 1 current);
        - both rows carry the SAME ``edge_id`` as the seeded value.

    Separate tests per path (rather than a single parametrized shared
    test) so a regression in any single supersede INSERT produces a
    precise failure pointer at the CRUD function name.
    """

    def test_update_position_price_preserves_edge_id(
        self, position_with_edge: tuple[int, str, int, int]
    ) -> None:
        """Price-update supersede must carry ``edge_id`` forward."""
        surrogate_id, position_bk, _market_pk, edge_pk = position_with_edge

        new_id = update_position_price(
            position_id=surrogate_id,
            current_price=Decimal("0.5600"),
        )

        assert new_id != surrogate_id, "must allocate a new surrogate id"

        rows = _fetch_scd_chain(position_bk)
        assert len(rows) == 2, (
            f"expected 1 historical + 1 current row after supersede, found {len(rows)}"
        )
        historical, current = _partition_scd_rows(rows)
        _assert_edge_id_copy_forward(historical, current, expected_edge_pk=edge_pk)

    def test_close_position_preserves_edge_id(
        self, position_with_edge: tuple[int, str, int, int]
    ) -> None:
        """close-position supersede must carry ``edge_id`` forward."""
        surrogate_id, position_bk, _market_pk, edge_pk = position_with_edge

        new_id = close_position(
            position_id=surrogate_id,
            exit_price=Decimal("0.6000"),
            exit_reason="test_target_hit",
            realized_pnl=Decimal("1.0000"),
        )

        assert new_id != surrogate_id, "must allocate a new surrogate id"

        rows = _fetch_scd_chain(position_bk)
        assert len(rows) == 2
        historical, current = _partition_scd_rows(rows)
        _assert_edge_id_copy_forward(historical, current, expected_edge_pk=edge_pk)
        # And close_position must transition status:
        assert current["status"] == "closed"

    def test_set_trailing_stop_state_preserves_edge_id(
        self, position_with_edge: tuple[int, str, int, int]
    ) -> None:
        """trailing-stop supersede must carry ``edge_id`` forward."""
        surrogate_id, position_bk, _market_pk, edge_pk = position_with_edge

        new_state = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": False,
            "activation_price": None,
            "current_stop_price": "0.4500",
            "highest_price": "0.5500",
        }
        new_id = set_trailing_stop_state(
            position_id=surrogate_id,
            trailing_stop_state=new_state,
        )

        assert new_id != surrogate_id, "must allocate a new surrogate id"

        rows = _fetch_scd_chain(position_bk)
        assert len(rows) == 2
        historical, current = _partition_scd_rows(rows)
        _assert_edge_id_copy_forward(historical, current, expected_edge_pk=edge_pk)


@pytest.mark.integration
class TestPositionsHistoricalIdRepair:
    """Historical-id repair contract regression guard (PR #863 Glokta P1-1/P1-2)."""

    def test_update_position_price_repairs_historical_id(
        self,
        position_with_edge: tuple[int, str, int, int],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Historical id repair path; also asserts id_repaired log line fires (Glokta P1-1)."""
        historical_surrogate_id, position_bk, _market_pk, _edge_pk = position_with_edge

        # Step 2: supersede once to allocate a new current version.
        intermediate_id = update_position_price(
            position_id=historical_surrogate_id,
            current_price=Decimal("0.5600"),
        )
        assert intermediate_id != historical_surrogate_id

        # Step 3-5: call again with the now-historical id and a different
        # price. Must succeed and allocate a THIRD version.
        with caplog.at_level(logging.INFO, logger="precog.database.crud_positions"):
            third_id = update_position_price(
                position_id=historical_surrogate_id,
                current_price=Decimal("0.5700"),
            )

        assert third_id != historical_surrogate_id, (
            "returned id must differ from caller-supplied historical id"
        )
        assert third_id != intermediate_id, (
            "returned id must differ from the intermediate sibling's id "
            "(a third SCD version must be created)"
        )

        # P1-1: the id_repaired log line must fire.
        repair_log_present = any(
            "historical position_id" in rec.getMessage()
            and "repaired to current id" in rec.getMessage()
            for rec in caplog.records
        )
        assert repair_log_present, (
            "expected an info log line matching 'historical position_id ... "
            "repaired to current id' when a historical id is passed. "
            f"Got: {[rec.getMessage() for rec in caplog.records]}"
        )

        # SCD invariant: exactly one current row at the end.
        rows = _fetch_scd_chain(position_bk)
        current_rows = [r for r in rows if r["row_current_ind"]]
        assert len(current_rows) == 1, (
            f"expected exactly 1 current row for business key {position_bk!r}, "
            f"got {len(current_rows)}. Full chain: {rows}"
        )
        assert current_rows[0]["id"] == third_id

    def test_close_position_repairs_historical_id(
        self,
        position_with_edge: tuple[int, str, int, int],
    ) -> None:
        """Historical id repair → status-guard fires on already-closed sibling (Glokta P1-1 audit-trail)."""
        historical_surrogate_id, _position_bk, _market_pk, _edge_pk = position_with_edge

        # Step 2: first close succeeds and transitions status to 'closed'.
        _intermediate_id = close_position(
            position_id=historical_surrogate_id,
            exit_price=Decimal("0.6000"),
            exit_reason="test_target_hit",
            realized_pnl=Decimal("1.0000"),
        )

        # Step 3: re-invoke with the historical id and different exit params.
        # The business-key resolution succeeds, but the closure's status
        # guard fires because the current row's status is 'closed' — this
        # is the audit trail Glokta's P1-1 fix is designed to produce
        # (the alternative would be silent state corruption).
        with pytest.raises(ValueError, match="is not open"):
            close_position(
                position_id=historical_surrogate_id,
                exit_price=Decimal("0.6500"),
                exit_reason="test_manual",
                realized_pnl=Decimal("1.5000"),
            )

    def test_set_trailing_stop_state_repairs_historical_id(
        self,
        position_with_edge: tuple[int, str, int, int],
    ) -> None:
        """Historical id passed to set_trailing_stop_state must repair."""
        historical_surrogate_id, position_bk, _market_pk, _edge_pk = position_with_edge

        state_a = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": False,
            "activation_price": None,
            "current_stop_price": "0.4500",
            "highest_price": "0.5500",
        }
        state_b = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": True,
            "activation_price": "0.5800",
            "current_stop_price": "0.5200",
            "highest_price": "0.6100",
        }

        # Step 2: supersede once to allocate a new current version.
        intermediate_id = set_trailing_stop_state(
            position_id=historical_surrogate_id,
            trailing_stop_state=state_a,
        )
        assert intermediate_id != historical_surrogate_id

        # Step 3-5: call again with the now-historical id. Must succeed
        # and allocate a THIRD version.
        third_id = set_trailing_stop_state(
            position_id=historical_surrogate_id,
            trailing_stop_state=state_b,
        )

        assert third_id != historical_surrogate_id, (
            "returned id must differ from caller-supplied historical id"
        )
        assert third_id != intermediate_id, (
            "returned id must differ from the intermediate sibling's id "
            "(a third SCD version must be created)"
        )

        # SCD invariant: exactly one current row at the end.
        rows = _fetch_scd_chain(position_bk)
        current_rows = [r for r in rows if r["row_current_ind"]]
        assert len(current_rows) == 1, (
            f"expected exactly 1 current row for business key {position_bk!r}, "
            f"got {len(current_rows)}. Full chain: {rows}"
        )
        assert current_rows[0]["id"] == third_id


# =============================================================================
# Helpers
# =============================================================================


def _fetch_scd_chain(position_bk: str) -> list[dict[str, Any]]:
    """Return every positions row for the business key, oldest first."""
    with get_cursor(commit=False) as cur:
        cur.execute(
            """
            SELECT id, position_key, edge_id, status, row_current_ind,
                   row_start_ts, row_end_ts
            FROM positions
            WHERE position_key = %s
            ORDER BY row_start_ts ASC
            """,
            (position_bk,),
        )
        return list(cur.fetchall())


def _partition_scd_rows(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a 2-row SCD chain into (historical, current) and sanity-check shape."""
    historical_rows = [r for r in rows if not r["row_current_ind"]]
    current_rows = [r for r in rows if r["row_current_ind"]]
    assert len(historical_rows) == 1, (
        f"expected exactly 1 historical row, got {len(historical_rows)}"
    )
    assert len(current_rows) == 1, f"expected exactly 1 current row, got {len(current_rows)}"
    return historical_rows[0], current_rows[0]


def _assert_edge_id_copy_forward(
    historical: dict[str, Any],
    current: dict[str, Any],
    *,
    expected_edge_pk: int,
) -> None:
    """Assert both rows carry ``edge_id == expected_edge_pk``.

    Dedicated assertion helper with a rich failure message — a regression
    here has a precise signature (the supersede INSERT omitted ``edge_id``
    from its column list or params tuple) and the error message should
    reproduce that diagnosis automatically.
    """
    assert historical["edge_id"] == expected_edge_pk, (
        f"fixture seed broke: historical row's edge_id={historical['edge_id']!r} "
        f"differs from expected {expected_edge_pk!r} BEFORE supersede fires. "
        f"This means create_position did not persist the edge_id parameter."
    )
    assert current["edge_id"] == expected_edge_pk, (
        f"SCD copy-forward contract violation: current row's edge_id="
        f"{current['edge_id']!r} should equal historical "
        f"edge_id={historical['edge_id']!r} (={expected_edge_pk}). "
        f"The supersede INSERT silently NULLed the provenance FK. "
        f"Fix: ensure edge_id appears in BOTH the INSERT column list AND "
        f"its params tuple in crud_positions.py, sourced from current['edge_id']. "
        f"See migration 0059 docstring and design memo #725 Holden S57 §6."
    )
