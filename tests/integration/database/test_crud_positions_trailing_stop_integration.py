"""
CI integration tests for ``set_trailing_stop_state`` against a real
PostgreSQL database.

Issue #629: the pre-PR-#629 ``initialize_trailing_stop`` and
``update_trailing_stop`` methods in ``position_manager`` issued an
``UPDATE positions SET row_current_ind = FALSE`` followed by an
``INSERT INTO positions (...) SELECT ... FROM positions WHERE
row_current_ind = TRUE`` in the same transaction. Under PostgreSQL READ
COMMITTED isolation, the INSERT's SELECT observes the UPDATE's row-level
change within the same transaction, so the SELECT returns ZERO rows, the
INSERT inserts nothing, and ``cur.fetchone()["id"]`` raises TypeError.
The bug was latent for 4.5 months because:

    (a) zero production callers exercised these write paths, and
    (b) all unit tests mocked the cursor with pure-function side_effects
        that did not simulate read-then-write transaction visibility.

This file fills the integration gap with single-threaded tests that run
in CI (no ``_is_ci`` skip). They verify, against a real database, that:

    1. Initialize path -- a fresh trailing_stop_state writes a new SCD
       version cleanly, with current_price preserved (initialize does
       not mutate price) and ``execution_environment`` preserved.
    2. Update path -- a subsequent call mutates trailing_stop_state +
       current_price + unrealized_pnl on top of the active version,
       preserving Pattern 49 temporal continuity
       (historical.row_end_ts == current.row_start_ts).
    3. Status guard -- closed positions reject the call with ValueError
       (the hardened ``!= "open"`` allow-list, mirroring PR #665's
       update_position_price / close_position).
    4. ``execution_environment`` preservation -- the bug Marvin's
       sentinel pass found in #662 (update_position_price omits
       execution_environment from the INSERT column list) must NOT
       repeat in this CRUD function.

The race-path coverage (concurrent calls actually triggering the
``retry_on_scd_unique_conflict`` helper inside a real transaction) lives
in ``tests/race/test_scd_sibling_first_insert_races.py`` and runs
locally + nightly. The combination of unit tests (mocked CRUD boundary
in ``test_position_manager_trailing_stops.py``), this file
(single-threaded real-DB composition), and the race test gives full
defense in depth without depending on CI-hostile threading.

Reference:
    - Issue #629: latent INSERT...SELECT bug in trailing stop write paths.
    - Issue #628: trailing stop race test coverage.
    - PR #665: canonical Pattern 49 adoption for ``update_position_price``
      and ``close_position`` (model for the new ``set_trailing_stop_state``).
    - Pattern 49 (DEVELOPMENT_PATTERNS_V1.30.md): SCD Race Prevention.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.crud_positions import set_trailing_stop_state

# Test identifiers reserved for this integration suite. Use the TEST- prefix
# so the suite-wide ``clean_test_data`` regex picks up any orphaned rows the
# explicit teardown below misses.
_TEST_TICKER = "TEST-INT-629-MKT"
_TEST_POSITION_BK_PREFIX = "TEST-INT-629-POS-"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def trailing_stop_position(db_pool: Any) -> Any:
    """Create a clean test market + open position; tear down after each test.

    Uses its own ``get_cursor(commit=True)`` blocks (NOT the suite-wide
    ``clean_test_data`` SAVEPOINT-style rollback fixture) because
    ``set_trailing_stop_state`` commits real rows that would survive a
    transaction rollback.

    Yields a tuple of (position_surrogate_id, position_business_key,
    market_pk) so each test can address the position by its surrogate id
    (the public CRUD entry point) and verify state by business key
    (the SCD chain identifier).
    """
    position_bk = f"{_TEST_POSITION_BK_PREFIX}1"

    # Setup: clean any leftover state and ensure the market + position rows exist.
    with get_cursor(commit=True) as cur:
        # Cleanup in FK order: positions first (FKs to markets), then markets.
        cur.execute(
            "DELETE FROM positions WHERE position_id LIKE %s",
            (_TEST_POSITION_BK_PREFIX + "%",),
        )
        cur.execute(
            """
            DELETE FROM market_snapshots WHERE market_id IN (
                SELECT id FROM markets WHERE ticker = %s
            )
            """,
            (_TEST_TICKER,),
        )
        cur.execute("DELETE FROM markets WHERE ticker = %s", (_TEST_TICKER,))

        # Create the underlying market (positions FK to markets.id).
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_internal_id, external_id, ticker, title,
                market_type, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                None,
                f"{_TEST_TICKER}-EXT",
                _TEST_TICKER,
                "Issue 629 Integration Market",
                "binary",
                "open",
            ),
        )
        market_pk = cur.fetchone()["id"]

        # Create the initial open position (current row, no trailing stop yet).
        # execution_environment defaults to 'live' per migration 0008.
        cur.execute(
            """
            INSERT INTO positions (
                position_id, market_internal_id, side, quantity,
                entry_price, current_price, stop_loss_price,
                status, entry_time, last_check_time,
                row_current_ind, row_start_ts,
                execution_environment
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, NOW(), NOW(),
                TRUE, NOW(),
                %s
            )
            RETURNING id
            """,
            (
                position_bk,
                market_pk,
                "YES",
                10,
                Decimal("0.5000"),
                Decimal("0.5500"),
                Decimal("0.4500"),
                "open",
                "paper",  # Non-default execution_environment to verify preservation
            ),
        )
        position_surrogate_id = cur.fetchone()["id"]

    yield position_surrogate_id, position_bk, market_pk

    # Teardown: remove all rows this test touched.
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM positions WHERE position_id = %s", (position_bk,))
            cur.execute("DELETE FROM market_snapshots WHERE market_id = %s", (market_pk,))
            cur.execute("DELETE FROM markets WHERE id = %s", (market_pk,))
    except Exception:
        # Best-effort cleanup; do not mask the actual test outcome.
        pass


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestSetTrailingStopStateIntegration:
    """Single-threaded integration coverage for ``set_trailing_stop_state``.

    These tests would have caught Issue #629 immediately: the
    pre-refactor ``UPDATE ... ; INSERT ... SELECT`` pattern raises
    ``TypeError: 'NoneType' object is not subscriptable`` against a real
    database, because the SELECT in the same transaction observes the
    UPDATE's row-level change and returns zero rows. Mocked unit tests
    cannot reproduce this read-then-write visibility bug.
    """

    def test_initialize_trailing_stop_writes_new_scd_version(
        self, trailing_stop_position: tuple[int, str, int]
    ) -> None:
        """First call seeds an inactive trailing_stop_state on an open position.

        Verifies the canonical SCD pattern composes against a real database:
        the prior current row is closed, a new current row is inserted with
        the new trailing_stop_state, current_price is preserved (initialize
        path passes None for ``current_price``), and the version chain has
        no Pattern 49 temporal-continuity gap.
        """
        surrogate_id, position_bk, _market_pk = trailing_stop_position

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

        assert new_id is not None
        assert isinstance(new_id, int)
        assert new_id != surrogate_id, "must allocate a new surrogate id"

        # Verify SCD chain: exactly two rows (one historical, one current),
        # both for the same business key, temporal continuity intact.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, position_id, current_price, trailing_stop_state,
                       execution_environment, status, row_current_ind,
                       row_start_ts, row_end_ts
                FROM positions
                WHERE position_id = %s
                ORDER BY row_start_ts ASC
                """,
                (position_bk,),
            )
            rows = cur.fetchall()

        assert len(rows) == 2, f"expected exactly two rows, found {len(rows)}: {rows}"

        historical_rows = [r for r in rows if not r["row_current_ind"]]
        current_rows = [r for r in rows if r["row_current_ind"]]

        assert len(historical_rows) == 1
        assert len(current_rows) == 1

        historical = historical_rows[0]
        current = current_rows[0]

        # Historical row's id matches the original surrogate; current row's
        # id matches the returned new id.
        assert historical["id"] == surrogate_id
        assert current["id"] == new_id

        # Pattern 49 temporal continuity.
        assert historical["row_end_ts"] is not None
        assert current["row_end_ts"] is None
        assert historical["row_end_ts"] == current["row_start_ts"], (
            f"temporal continuity violation: "
            f"historical.row_end_ts={historical['row_end_ts']} != "
            f"current.row_start_ts={current['row_start_ts']}"
        )

        # Initialize path does NOT mutate current_price -- the new row
        # carries the SAME current_price as the historical row.
        assert current["current_price"] == historical["current_price"]
        assert current["current_price"] == Decimal("0.5500")

        # Trailing stop state is now populated.
        assert current["trailing_stop_state"] is not None
        assert current["trailing_stop_state"]["activated"] is False
        assert current["trailing_stop_state"]["current_stop_price"] == "0.4500"

        # Status preserved as 'open'.
        assert current["status"] == "open"

        # ⭐ execution_environment preserved (Issue #662 / Marvin sentinel
        # check). The fixture seeded 'paper'; the new SCD row must carry
        # 'paper' through, NOT default to 'live'.
        assert current["execution_environment"] == "paper", (
            f"execution_environment must be preserved across SCD writes; "
            f"expected 'paper', got {current['execution_environment']!r}. "
            f"This is the same bug class Marvin found in update_position_price "
            f"(#662) -- if it appears here too, the INSERT column list is "
            f"missing execution_environment."
        )
        assert historical["execution_environment"] == "paper"

    def test_update_trailing_stop_writes_price_pnl_state_together(
        self, trailing_stop_position: tuple[int, str, int]
    ) -> None:
        """Second call mutates trailing_stop_state + current_price + unrealized_pnl.

        Verifies the update path passes all three values to the CRUD and
        the resulting SCD row carries them, while preserving
        execution_environment and Pattern 49 temporal continuity across
        the chain (historical_v1 -> historical_v2 -> current).
        """
        surrogate_id, position_bk, _market_pk = trailing_stop_position

        # First call: initialize the trailing stop.
        initial_state = {
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
        v1_id = set_trailing_stop_state(
            position_id=surrogate_id,
            trailing_stop_state=initial_state,
        )

        # Second call: update with a new price + activated state + pnl.
        updated_state = {
            "config": initial_state["config"],
            "activated": True,
            "activation_price": "0.6500",
            "current_stop_price": "0.6000",
            "highest_price": "0.6500",
        }
        new_price = Decimal("0.6500")
        new_pnl = Decimal("1.5000")
        v2_id = set_trailing_stop_state(
            position_id=v1_id,
            trailing_stop_state=updated_state,
            current_price=new_price,
            unrealized_pnl=new_pnl,
        )

        assert v2_id is not None
        assert v2_id != v1_id
        assert v2_id != surrogate_id

        # Verify the chain: three rows (initial historical, v1 historical,
        # v2 current). Each consecutive pair has temporal continuity.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, current_price, unrealized_pnl, trailing_stop_state,
                       execution_environment, row_current_ind, row_start_ts,
                       row_end_ts
                FROM positions
                WHERE position_id = %s
                ORDER BY row_start_ts ASC
                """,
                (position_bk,),
            )
            rows = cur.fetchall()

        assert len(rows) == 3, f"expected three rows in chain, found {len(rows)}: {rows}"

        # Last row is current and reflects the v2 mutations.
        current_row = rows[-1]
        assert current_row["row_current_ind"] is True
        assert current_row["id"] == v2_id
        assert current_row["current_price"] == new_price
        assert current_row["unrealized_pnl"] == new_pnl
        assert current_row["trailing_stop_state"]["activated"] is True
        assert current_row["trailing_stop_state"]["activation_price"] == "0.6500"

        # First two rows are historical.
        for historical in rows[:-1]:
            assert historical["row_current_ind"] is False
            assert historical["row_end_ts"] is not None

        # Pattern 49 temporal continuity across each adjacent pair.
        for prev, nxt in pairwise(rows):
            assert prev["row_end_ts"] == nxt["row_start_ts"], (
                f"temporal continuity violation between {prev['id']} and "
                f"{nxt['id']}: prev.row_end_ts={prev['row_end_ts']} != "
                f"next.row_start_ts={nxt['row_start_ts']}"
            )

        # execution_environment preserved across BOTH SCD writes.
        assert all(r["execution_environment"] == "paper" for r in rows), (
            f"execution_environment must survive every SCD write; got "
            f"{[r['execution_environment'] for r in rows]}"
        )

    def test_refuses_to_set_on_closed_position(
        self, trailing_stop_position: tuple[int, str, int]
    ) -> None:
        """The hardened ``!= 'open'`` guard rejects closed positions.

        Mirrors the same guard added to ``update_position_price`` and
        ``close_position`` in PR #665. Without this guard, the old
        ``INSERT ... SELECT`` path would silently succeed against a
        closed position, layering a new trailing_stop_state onto a
        terminal SCD row.
        """
        surrogate_id, position_bk, _market_pk = trailing_stop_position

        # Close the position out-of-band so the next ``set_trailing_stop_state``
        # call observes a non-open status.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE positions
                SET status = 'closed', exit_time = NOW()
                WHERE position_id = %s AND row_current_ind = TRUE
                """,
                (position_bk,),
            )

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

        with pytest.raises(ValueError, match="is not open"):
            set_trailing_stop_state(
                position_id=surrogate_id,
                trailing_stop_state=new_state,
            )

        # Verify NO new SCD row was created -- the chain still has exactly
        # the original (now-closed) current row.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM positions
                WHERE position_id = %s
                """,
                (position_bk,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["n"] == 1, (
            "the closed-position guard must reject BEFORE writing a new SCD "
            "version, so the chain length should still be 1"
        )

    def test_raises_value_error_when_position_missing(
        self, trailing_stop_position: tuple[int, str, int]
    ) -> None:
        """Calling with a non-existent surrogate id raises ValueError immediately.

        The not-found guard fires OUTSIDE the retry closure, so a missing
        position never enters the SCD write path. Verifies the contract
        parity with ``update_position_price`` and ``close_position``.
        """
        # Use a surrogate id far above any test data — guaranteed not to exist.
        with pytest.raises(ValueError, match="Position not found"):
            set_trailing_stop_state(
                position_id=2147483640,  # near INT max, never used by SERIAL
                trailing_stop_state={"activated": False},
            )

    def test_accepts_decimal_values_in_trailing_stop_state(
        self, trailing_stop_position: tuple[int, str, int]
    ) -> None:
        """Production-shape test: trailing_stop_state contains Decimal values.

        **Marvin blocking-fix test (#629 PR review, session 42e):**

        The production callers (``position_manager.initialize_trailing_stop``
        at line 796, ``position_manager.update_trailing_stop`` at lines 980,
        1007, 1026) build ``trailing_stop_state`` dicts containing
        ``Decimal`` values at multiple keys:

            - ``activation_price``: Decimal
            - ``highest_price``: Decimal
            - ``current_stop_price``: Decimal
            - ``config.activation_threshold``: Decimal
            - ``config.initial_distance``: Decimal
            - ``config.tightening_rate``: Decimal
            - ``config.floor_distance``: Decimal

        Before the fix: ``psycopg2.extras.Json(trailing_stop_state)`` used
        the default ``json.dumps`` which raised
        ``TypeError: Object of type Decimal is not JSON serializable``.
        Samwise's original integration tests (``test_initialize_...``,
        ``test_update_...``) passed STRING values and so could not detect
        this — Marvin's sentinel pass reproduced the crash end-to-end
        against a real testcontainer.

        After the fix: ``_jsonb_dumps`` (in ``crud_positions.py``) uses
        ``DecimalEncoder`` from ``crud_shared`` to serialize ``Decimal``
        as its string representation before wrapping in ``Json(...)``.

        This test pins the fix. If the production-shape dict ever fails
        to round-trip, this test will fail loudly rather than hiding the
        bug behind string-typed mocks.

        Round-trip contract note: on the READ path, JSONB decoders return
        the stored string form (not Decimal). Consumers that need Decimal
        semantics must parse with ``Decimal(value)`` at read time. This
        test documents the expected round-trip shape (strings come back)
        so future readers don't mistake the contract.
        """
        surrogate_id, _position_bk, _market_pk = trailing_stop_position

        # Production-shape dict: every numeric value is a Decimal, exactly
        # as position_manager constructs the state in both the initialize
        # and update paths.
        production_shape_state = {
            "config": {
                "activation_threshold": Decimal("0.15"),
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            },
            "activated": True,
            "activation_price": Decimal("0.6500"),
            "current_stop_price": Decimal("0.6000"),
            "highest_price": Decimal("0.6500"),
        }

        # This call would have raised TypeError before the fix.
        new_id = set_trailing_stop_state(
            position_id=surrogate_id,
            trailing_stop_state=production_shape_state,
            current_price=Decimal("0.6500"),
            unrealized_pnl=Decimal("1.5000"),
        )
        assert new_id is not None

        # Verify round-trip: read back the JSONB column and confirm the
        # values are preserved (as strings, per the JSONB decoder contract).
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT trailing_stop_state, current_price, unrealized_pnl
                FROM positions
                WHERE id = %s AND row_current_ind = TRUE
                """,
                (new_id,),
            )
            row = cur.fetchone()

        assert row is not None
        stored_state = row["trailing_stop_state"]

        # Numeric values round-trip as strings (JSONB + DecimalEncoder
        # preserves precision via string serialization). The str(Decimal)
        # form is stable across psycopg2 versions.
        assert stored_state["activation_price"] == "0.6500", (
            f"Decimal serialization failed: activation_price is "
            f"{stored_state['activation_price']!r} (expected '0.6500'). "
            f"If this is '0.65' or any other form, DecimalEncoder is not "
            f"being applied correctly."
        )
        assert stored_state["highest_price"] == "0.6500"
        assert stored_state["current_stop_price"] == "0.6000"
        assert stored_state["config"]["activation_threshold"] == "0.15"
        assert stored_state["config"]["initial_distance"] == "0.05"
        assert stored_state["config"]["tightening_rate"] == "0.10"
        assert stored_state["config"]["floor_distance"] == "0.02"
        assert stored_state["activated"] is True

        # Non-JSONB Decimal columns (current_price, unrealized_pnl) stay
        # as Decimal — psycopg2 reads DECIMAL(10,4) as Decimal natively.
        assert row["current_price"] == Decimal("0.6500")
        assert row["unrealized_pnl"] == Decimal("1.5000")
