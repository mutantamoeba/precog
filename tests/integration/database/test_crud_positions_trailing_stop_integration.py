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
from precog.database.crud_positions import (
    close_position,
    create_position,
    set_trailing_stop_state,
    update_position_price,
)

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
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    with get_cursor(commit=True) as cur:
        # RESTRICT-safe cleanup: delete all children before parents.
        delete_market_with_children(cur, "ticker = %s", (_TEST_TICKER,))

        # Create the underlying market (positions FK to markets.id).
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_id, external_id, ticker, title,
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
                position_key, market_id, side, quantity,
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

    # Teardown: RESTRICT-safe cleanup.
    try:
        with get_cursor(commit=True) as cur:
            delete_market_with_children(cur, "id = %s", (market_pk,))
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
                SELECT id, position_key, current_price, trailing_stop_state,
                       execution_environment, status, row_current_ind,
                       row_start_ts, row_end_ts
                FROM positions
                WHERE position_key = %s
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
                WHERE position_key = %s
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
                WHERE position_key = %s AND row_current_ind = TRUE
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
                WHERE position_key = %s
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


@pytest.mark.integration
class TestUpdatePositionPriceIntegration:
    """Single-threaded integration coverage for ``update_position_price``.

    Issue #662 (Marvin sentinel pass on PR #665, session 42e):

    The pre-fix INSERT column list in ``update_position_price`` omitted
    ``execution_environment``. The column is ``NOT NULL DEFAULT 'live'``
    (migrations 0008 + 0024), so every SCD version produced by a price
    update silently stamped the new row with ``'live'`` regardless of
    the original position's environment. A position opened in ``'paper'``
    or ``'backtest'`` mode flipped to ``'live'`` on its very first price
    tick -- cross-environment contamination with no audit signal except
    the SCD history itself.

    This test pins the fix. It would have failed loudly on the pre-fix
    code because the fixture seeds the position with
    ``execution_environment='paper'`` and then asserts the new SCD
    version is still ``'paper'``. Pre-fix, the new row would carry the
    DEFAULT ``'live'``.

    Reuses the ``trailing_stop_position`` fixture from this file because
    that fixture already seeds an open position with a non-default
    ``execution_environment='paper'`` -- the exact setup needed to
    detect the regression.

    Reference:
        - Issue #662: update_position_price drops execution_environment.
        - PR #665: SCD retry helper batch adoption (the PR Marvin
          reviewed when she found this latent bug).
        - close_position at crud_positions.py:760: the canonical
          reference -- it has handled execution_environment correctly
          since the SCD pattern was first introduced.
    """

    def test_preserves_execution_environment_across_price_update(
        self, trailing_stop_position: tuple[int, str, int]
    ) -> None:
        """A price update on a 'paper' position must keep execution_environment='paper'.

        Pre-fix behavior: the INSERT column list omitted
        ``execution_environment``, so the new SCD row picked up the
        column DEFAULT ``'live'``. This test would fail with
        ``assert 'live' == 'paper'`` against pre-fix code.

        Post-fix behavior: the INSERT column list explicitly includes
        ``execution_environment`` and the values tuple copies
        ``current["execution_environment"]`` from the re-fetched current
        row, mirroring ``close_position``'s pattern.
        """
        surrogate_id, position_bk, _market_pk = trailing_stop_position

        # Sanity check: the fixture seeds 'paper'. If this assertion ever
        # fails, the fixture has drifted and the rest of the test is
        # meaningless.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT execution_environment
                FROM positions
                WHERE id = %s AND row_current_ind = TRUE
                """,
                (surrogate_id,),
            )
            seed_row = cur.fetchone()
        assert seed_row is not None
        assert seed_row["execution_environment"] == "paper", (
            "fixture must seed execution_environment='paper' for this test "
            "to detect the #662 regression"
        )

        # Trigger an SCD version write via update_position_price. The
        # fixture's current_price is Decimal('0.5500'); use a different
        # value so the early-return optimization (price_unchanged AND
        # trailing_stop_unchanged) does NOT short-circuit and skip the
        # INSERT we want to test.
        new_id = update_position_price(
            position_id=surrogate_id,
            current_price=Decimal("0.6000"),
        )

        assert new_id is not None
        assert new_id != surrogate_id, "must allocate a new surrogate id"

        # Read back the new current row and verify execution_environment
        # was preserved (not silently flipped to the DEFAULT 'live').
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, current_price, execution_environment, row_current_ind
                FROM positions
                WHERE position_key = %s AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            current = cur.fetchone()

        assert current is not None
        assert current["id"] == new_id
        assert current["current_price"] == Decimal("0.6000")
        assert current["execution_environment"] == "paper", (
            f"execution_environment must be preserved across SCD price "
            f"updates; expected 'paper', got "
            f"{current['execution_environment']!r}. This is the #662 bug "
            f"Marvin found in PR #665 review: update_position_price's "
            f"INSERT column list omitted execution_environment, so the "
            f"new SCD row picked up the column DEFAULT 'live' and "
            f"silently flipped paper-mode positions to live."
        )

        # Also verify the historical row still carries 'paper' (the
        # close path doesn't touch execution_environment, but assert it
        # explicitly so a future regression that mutates the historical
        # row gets caught here too).
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT execution_environment
                FROM positions
                WHERE position_key = %s AND row_current_ind = FALSE
                ORDER BY row_start_ts DESC
                LIMIT 1
                """,
                (position_bk,),
            )
            historical = cur.fetchone()
        assert historical is not None
        assert historical["execution_environment"] == "paper"

        # Marvin sentinel pass: a SECOND price update on the surviving
        # 'paper' row. This catches "partial fix" regressions where one
        # call site is fixed but a downstream refactor reintroduces the
        # bug on a follow-up update -- the canonical failure mode for
        # SCD chains, where the first version preserves the value but
        # the chain drops it on subsequent versions. Pre-fix code would
        # flip the new row to 'live' here exactly the same way as on the
        # first update, so this assertion is independent evidence (not
        # just a re-check of the first assertion).
        second_new_id = update_position_price(
            position_id=new_id,
            current_price=Decimal("0.6500"),
        )
        assert second_new_id != new_id, "second update must allocate a new surrogate id"

        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, current_price, execution_environment
                FROM positions
                WHERE position_key = %s AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            after_second = cur.fetchone()
        assert after_second is not None
        assert after_second["id"] == second_new_id
        assert after_second["current_price"] == Decimal("0.6500")
        assert after_second["execution_environment"] == "paper", (
            f"execution_environment must be preserved across the FULL SCD "
            f"chain, not just the first update; expected 'paper', got "
            f"{after_second['execution_environment']!r} after the second "
            f"price update"
        )


# =============================================================================
# Issue #666 + #706: psycopg2 dict-adapter / Decimal-JSONB fixtures
# =============================================================================


# Production-shape trailing_stop_state: every numeric value is a Decimal,
# mirroring the dict ``position_manager`` builds in
# ``initialize_trailing_stop`` and ``update_trailing_stop`` callers. Kept
# at module scope (not a fixture) so each test copies it via ``dict(...)``
# and mutates independently without cross-test bleed.
_PRODUCTION_SHAPE_TRAILING_STOP: dict[str, Any] = {
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


_CREATE_POS_TEST_TICKER = "TEST-INT-706-MKT"
_CREATE_POS_BK_PREFIX = "TEST-INT-706-POS-"
_CREATE_POS_STRATEGY_ID = 99901  # matches conftest.clean_test_data seed
_CREATE_POS_MODEL_ID = 99901  # matches conftest.clean_test_data seed


@pytest.fixture
def create_position_market(db_pool: Any) -> Any:
    """Seed a clean market plus strategy/model parent rows for create_position tests.

    ``create_position`` requires ``strategy_id`` and ``model_id`` FKs to
    non-null rows in ``strategies`` / ``probability_models`` (see
    ``crud_positions.py:281``). This fixture seeds the same high-id parent
    rows the suite-wide ``clean_test_data`` fixture uses (99901/99901) so
    tests can call ``create_position(...)`` directly.

    Tears down positions, market, and market_snapshots after each test.
    Leaves the strategy/model rows alone because other tests in the same
    session may reuse them and the cleanup happens in the test-session
    ``clean_test_data`` teardown block.

    Yields the market surrogate PK.
    """
    from tests.fixtures.cleanup_helpers import delete_market_with_children

    with get_cursor(commit=True) as cur:
        # Cleanup any orphaned rows from a prior failed run (RESTRICT-safe).
        delete_market_with_children(cur, "ticker = %s", (_CREATE_POS_TEST_TICKER,))

        # Seed strategy + model parent rows idempotently. Mirrors the high
        # IDs conftest.clean_test_data uses so we don't collide with
        # SERIAL-generated rows from property tests.
        cur.execute(
            """
            INSERT INTO strategies (
                strategy_id, strategy_name, strategy_version, strategy_type,
                config, status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (strategy_id) DO NOTHING
            """,
            (
                _CREATE_POS_STRATEGY_ID,
                "test_706_strategy",
                "v1.0",
                "value",
                '{"test": true}',
                "active",
            ),
        )
        cur.execute(
            """
            INSERT INTO probability_models (
                model_id, model_name, model_version, model_class,
                config, status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (model_id) DO NOTHING
            """,
            (
                _CREATE_POS_MODEL_ID,
                "test_706_model",
                "v1.0",
                "elo",
                '{"test": true}',
                "active",
            ),
        )

        # Seed the market (positions FK to markets.id).
        cur.execute(
            """
            INSERT INTO markets (
                platform_id, event_id, external_id, ticker, title,
                market_type, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "kalshi",
                None,
                f"{_CREATE_POS_TEST_TICKER}-EXT",
                _CREATE_POS_TEST_TICKER,
                "Issue 706 Integration Market",
                "binary",
                "open",
            ),
        )
        market_pk = cur.fetchone()["id"]

    yield market_pk

    # Teardown: RESTRICT-safe cleanup via helper.
    try:
        with get_cursor(commit=True) as cur:
            delete_market_with_children(cur, "id = %s", (market_pk,))
    except Exception:
        # Best-effort cleanup; do not mask the actual test outcome.
        pass


def _seed_open_position_with_trailing_stop(
    *,
    market_pk: int,
    position_bk: str,
    trailing_stop_state: Any,
    execution_environment: str = "paper",
) -> int:
    """Seed an open position with a raw SQL INSERT so the trailing stop
    state hits the DB via psycopg2's adapter (not via any CRUD function).

    Used by the update_position_price / close_position tests to pre-stage
    a current row carrying a populated (or NULL) trailing_stop_state. We
    cannot use ``create_position`` for this seed step because
    ``create_position`` itself is under test here -- bootstrapping via
    ``create_position`` would mask a regression where the seed succeeds
    for the wrong reason (e.g., adapter works for create but not update).

    Wraps non-None dicts with ``Json(..., dumps=_jsonb_dumps)`` via the
    same internal encoder the CRUD functions now use, so the seeded row
    has the correct on-disk shape. Uses ``json.dumps(..., cls=DecimalEncoder)``
    inlined here to avoid importing a private symbol from the module
    under test.
    """
    import json as _json

    from psycopg2.extras import Json

    from precog.database.crud_shared import DecimalEncoder

    def _dumps(obj: Any) -> str:
        return _json.dumps(obj, cls=DecimalEncoder)

    wrapped_state = (
        Json(trailing_stop_state, dumps=_dumps) if trailing_stop_state is not None else None
    )

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO positions (
                position_key, market_id, side, quantity,
                entry_price, current_price, stop_loss_price,
                trailing_stop_state,
                status, entry_time, last_check_time,
                row_current_ind, row_start_ts,
                execution_environment
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s,
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
                wrapped_state,
                "open",
                execution_environment,
            ),
        )
        return cast_int(cur.fetchone()["id"])


def cast_int(value: Any) -> int:
    """Narrow ``Any`` -> ``int`` without pulling ``typing.cast`` into the
    test file's public namespace. Wraps psycopg2 RealDictRow lookups where
    we know the column is SERIAL.
    """
    return int(value)


# =============================================================================
# Issue #706: create_position — psycopg2 dict-adapter / Decimal-JSONB fix
# =============================================================================


@pytest.mark.integration
class TestCreatePositionTrailingStopJsonbWrite:
    """Single-threaded integration coverage for ``create_position`` when the
    ``trailing_stop_state`` parameter is a dict containing Decimal values.

    Issue #706 (filed session 43 from Glokta review of PR #705):

    ``create_position`` passes the raw ``trailing_stop_state`` dict to
    ``cur.execute(...)`` as an INSERT parameter. psycopg2 has no default
    ``dict -> jsonb`` adapter, so any non-None caller crashes with
    ``ProgrammingError: can't adapt type 'dict'``. Even if the adapter
    existed, plain ``json.dumps`` cannot serialize ``Decimal`` values
    (``TypeError: Object of type Decimal is not JSON serializable``).

    This test class pins the fix: ``trailing_stop_state`` is now wrapped
    with ``Json(..., dumps=_jsonb_dumps)`` if not None (matching the
    canonical ``set_trailing_stop_state`` pattern from #629 PR). The
    ``is not None`` conditional is critical -- wrapping ``None`` with
    ``Json(None)`` would serialize as the JSONB string ``"null"``, a
    4-character JSONB value that is NOT a SQL NULL. That would silently
    break any existing ``WHERE trailing_stop_state IS NULL`` query.
    """

    def test_create_position_with_decimal_trailing_stop_state(
        self, create_position_market: int
    ) -> None:
        """A fresh ``create_position`` call with a production-shape dict
        round-trips correctly.

        Pre-fix behavior: crashes with either ``ProgrammingError: can't
        adapt type 'dict'`` or ``TypeError: Object of type Decimal is not
        JSON serializable`` (both are valid pre-fix failure modes; the
        exact one depends on psycopg2 internals).

        Post-fix behavior: returns a valid surrogate id, the row is
        readable, and the trailing stop state is stored as a JSONB object
        with the Decimal-bearing values preserved as their string form
        (per the ``_jsonb_dumps`` / ``DecimalEncoder`` contract).
        """
        market_pk = create_position_market

        # Copy the module-scope production-shape dict so the test is
        # independent of other tests' mutations.
        state = {
            "config": dict(_PRODUCTION_SHAPE_TRAILING_STOP["config"]),
            "activated": _PRODUCTION_SHAPE_TRAILING_STOP["activated"],
            "activation_price": _PRODUCTION_SHAPE_TRAILING_STOP["activation_price"],
            "current_stop_price": _PRODUCTION_SHAPE_TRAILING_STOP["current_stop_price"],
            "highest_price": _PRODUCTION_SHAPE_TRAILING_STOP["highest_price"],
        }

        new_id = create_position(
            market_id=market_pk,
            strategy_id=_CREATE_POS_STRATEGY_ID,
            model_id=_CREATE_POS_MODEL_ID,
            side="YES",
            quantity=10,
            entry_price=Decimal("0.5200"),
            execution_environment="paper",
            target_price=Decimal("0.7500"),
            stop_loss_price=Decimal("0.4500"),
            trailing_stop_state=state,
        )

        assert new_id is not None
        assert isinstance(new_id, int)

        # Read back the row and verify the trailing stop state round-trips.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, trailing_stop_state, execution_environment,
                       row_current_ind
                FROM positions
                WHERE id = %s
                """,
                (new_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["row_current_ind"] is True
        assert row["execution_environment"] == "paper"

        stored_state = row["trailing_stop_state"]
        # psycopg2 auto-decodes JSONB to a Python dict on read.
        assert isinstance(stored_state, dict), (
            f"expected JSONB to decode as dict, got {type(stored_state).__name__}: {stored_state!r}"
        )

        # Every Decimal-bearing value comes back as its string
        # representation (because _jsonb_dumps used DecimalEncoder on
        # write). Assert the exact string form to catch any regression
        # where the encoder is bypassed.
        assert stored_state["activation_price"] == "0.6500"
        assert stored_state["current_stop_price"] == "0.6000"
        assert stored_state["highest_price"] == "0.6500"
        assert stored_state["config"]["activation_threshold"] == "0.15"
        assert stored_state["config"]["initial_distance"] == "0.05"
        assert stored_state["config"]["tightening_rate"] == "0.10"
        assert stored_state["config"]["floor_distance"] == "0.02"
        assert stored_state["activated"] is True

    def test_create_position_with_none_trailing_stop_state(
        self, create_position_market: int
    ) -> None:
        """Passing ``trailing_stop_state=None`` must store SQL NULL, not
        the JSONB string ``"null"``.

        If ``create_position`` ever wrapped ``None`` with ``Json(None)``,
        the column would contain the 4-character JSONB string ``"null"``
        instead of an actual SQL NULL. That would silently break every
        caller that uses ``WHERE trailing_stop_state IS NULL`` to find
        positions without a trailing stop.
        """
        market_pk = create_position_market

        new_id = create_position(
            market_id=market_pk,
            strategy_id=_CREATE_POS_STRATEGY_ID,
            model_id=_CREATE_POS_MODEL_ID,
            side="YES",
            quantity=5,
            entry_price=Decimal("0.4500"),
            execution_environment="paper",
            trailing_stop_state=None,
        )

        assert new_id is not None

        # The SQL-level check: ``trailing_stop_state IS NULL`` must return
        # True. A JSONB ``"null"`` string would return False here.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT
                    trailing_stop_state IS NULL AS is_sql_null,
                    trailing_stop_state
                FROM positions
                WHERE id = %s
                """,
                (new_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["is_sql_null"] is True, (
            f"trailing_stop_state must be SQL NULL, not a JSONB value; "
            f"got is_sql_null={row['is_sql_null']!r}, "
            f"stored_value={row['trailing_stop_state']!r}. If stored_value "
            f"is the string 'null' or None-as-JSONB, the None-wrap guard "
            f"was bypassed."
        )
        assert row["trailing_stop_state"] is None


# =============================================================================
# Issue #666 (part 1): update_position_price JSONB write
# =============================================================================


@pytest.mark.integration
class TestUpdatePositionPriceTrailingStopJsonbWrite:
    """Single-threaded integration coverage for the ``update_position_price``
    trailing_stop_state re-insert path.

    Issue #666 (filed session 42e by Marvin sentinel pass on PR #665):

    ``update_position_price`` re-inserts ``current["trailing_stop_state"]``
    (decoded from JSONB to a Python ``dict`` by psycopg2 on the re-fetch)
    straight into the new SCD row's INSERT params. psycopg2 has no
    ``dict -> jsonb`` adapter, so any position carrying a non-None
    trailing_stop_state crashed on the FIRST price update after the
    trailing stop was initialized. The bug was latent because
    ``trailing_stop_state`` is NULL on every fixture-seeded position in
    the unit tests -- the write path was never exercised with a
    non-None value.

    This test class pins the fix: the sibling ``fresh_trailing_stop``
    parameter is now wrapped with ``Json(..., dumps=_jsonb_dumps)`` if
    not None. Both paths covered (populated dict + NULL preserved).
    """

    def test_update_position_price_with_populated_trailing_stop(
        self, create_position_market: int
    ) -> None:
        """A price update on a position carrying a production-shape
        trailing_stop_state does not crash and preserves the state.

        Pre-fix: crashes at the INSERT step with
        ``ProgrammingError: can't adapt type 'dict'`` because the
        re-fetched ``current["trailing_stop_state"]`` is a plain dict
        that psycopg2 cannot serialize.

        Post-fix: the new SCD row is created, and the trailing_stop_state
        round-trips as the same dict shape (string form on read).
        """
        market_pk = create_position_market
        position_bk = f"{_CREATE_POS_BK_PREFIX}update-decimal"

        state = dict(_PRODUCTION_SHAPE_TRAILING_STOP)
        state["config"] = dict(_PRODUCTION_SHAPE_TRAILING_STOP["config"])

        surrogate_id = _seed_open_position_with_trailing_stop(
            market_pk=market_pk,
            position_bk=position_bk,
            trailing_stop_state=state,
        )

        # Sanity: the seed wrote a real JSONB object (not NULL, not "null").
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT trailing_stop_state, trailing_stop_state IS NULL AS is_null
                FROM positions
                WHERE id = %s
                """,
                (surrogate_id,),
            )
            seed_row = cur.fetchone()
        assert seed_row is not None
        assert seed_row["is_null"] is False
        assert isinstance(seed_row["trailing_stop_state"], dict)

        # Trigger the code path under test. No explicit trailing_stop_state
        # passed -- this exercises the "preserve from current row" branch
        # that re-feeds the decoded dict back into the INSERT params.
        new_id = update_position_price(
            position_id=surrogate_id,
            current_price=Decimal("0.6200"),
        )

        assert new_id is not None
        assert new_id != surrogate_id

        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, current_price, trailing_stop_state,
                       execution_environment, row_current_ind
                FROM positions
                WHERE position_key = %s AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            current = cur.fetchone()

        assert current is not None
        assert current["id"] == new_id
        assert current["current_price"] == Decimal("0.6200")
        assert current["execution_environment"] == "paper"

        stored_state = current["trailing_stop_state"]
        assert isinstance(stored_state, dict)
        # Values preserved across the re-insert.
        assert stored_state["activation_price"] == "0.6500"
        assert stored_state["current_stop_price"] == "0.6000"
        assert stored_state["highest_price"] == "0.6500"
        assert stored_state["config"]["activation_threshold"] == "0.15"

    def test_update_position_price_with_null_trailing_stop(
        self, create_position_market: int
    ) -> None:
        """A price update on a position with NULL trailing_stop_state
        keeps it SQL NULL, not the JSONB ``"null"`` string.
        """
        market_pk = create_position_market
        position_bk = f"{_CREATE_POS_BK_PREFIX}update-null"

        surrogate_id = _seed_open_position_with_trailing_stop(
            market_pk=market_pk,
            position_bk=position_bk,
            trailing_stop_state=None,
        )

        new_id = update_position_price(
            position_id=surrogate_id,
            current_price=Decimal("0.6200"),
        )

        assert new_id is not None
        assert new_id != surrogate_id

        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT
                    trailing_stop_state IS NULL AS is_sql_null,
                    trailing_stop_state
                FROM positions
                WHERE id = %s
                """,
                (new_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["is_sql_null"] is True, (
            f"trailing_stop_state must remain SQL NULL across the SCD "
            f"update; got is_sql_null={row['is_sql_null']!r}, "
            f"stored_value={row['trailing_stop_state']!r}"
        )
        assert row["trailing_stop_state"] is None


# =============================================================================
# Issue #666 (part 2): close_position JSONB write
# =============================================================================


@pytest.mark.integration
class TestClosePositionTrailingStopJsonbWrite:
    """Single-threaded integration coverage for the ``close_position``
    trailing_stop_state re-insert path.

    Issue #666 (same archetype as the update path): ``close_position``
    re-inserts ``current["trailing_stop_state"]`` (decoded dict) into the
    closed-version SCD row's INSERT params without wrapping. Any position
    closed while carrying a non-None trailing_stop_state crashed at the
    close boundary. The fix wraps with ``Json(..., dumps=_jsonb_dumps)``
    if not None.
    """

    def test_close_position_preserves_decimal_trailing_stop(
        self, create_position_market: int
    ) -> None:
        """Closing a position carrying a production-shape trailing stop
        preserves the state into the closed SCD row.
        """
        market_pk = create_position_market
        position_bk = f"{_CREATE_POS_BK_PREFIX}close-decimal"

        state = dict(_PRODUCTION_SHAPE_TRAILING_STOP)
        state["config"] = dict(_PRODUCTION_SHAPE_TRAILING_STOP["config"])

        surrogate_id = _seed_open_position_with_trailing_stop(
            market_pk=market_pk,
            position_bk=position_bk,
            trailing_stop_state=state,
        )

        closed_id = close_position(
            position_id=surrogate_id,
            exit_price=Decimal("0.6000"),
            exit_reason="target_hit",
            realized_pnl=Decimal("1.0000"),
        )

        assert closed_id is not None
        assert closed_id != surrogate_id

        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT id, status, exit_price, realized_pnl,
                       trailing_stop_state, execution_environment,
                       row_current_ind
                FROM positions
                WHERE position_key = %s AND row_current_ind = TRUE
                """,
                (position_bk,),
            )
            current = cur.fetchone()

        assert current is not None
        assert current["id"] == closed_id
        assert current["status"] == "closed"
        assert current["exit_price"] == Decimal("0.6000")
        assert current["realized_pnl"] == Decimal("1.0000")
        assert current["execution_environment"] == "paper"

        stored_state = current["trailing_stop_state"]
        assert isinstance(stored_state, dict)
        assert stored_state["activation_price"] == "0.6500"
        assert stored_state["current_stop_price"] == "0.6000"
        assert stored_state["highest_price"] == "0.6500"
        assert stored_state["config"]["activation_threshold"] == "0.15"
        assert stored_state["config"]["floor_distance"] == "0.02"

    def test_close_position_with_null_trailing_stop(self, create_position_market: int) -> None:
        """Closing a position with NULL trailing_stop_state leaves it
        SQL NULL on the closed row.

        Regression guard on the None path: the ``is not None`` conditional
        must not be bypassed by any refactor that moves the check into
        the SQL layer (where JSONB NULL semantics differ from SQL NULL).
        """
        market_pk = create_position_market
        position_bk = f"{_CREATE_POS_BK_PREFIX}close-null"

        surrogate_id = _seed_open_position_with_trailing_stop(
            market_pk=market_pk,
            position_bk=position_bk,
            trailing_stop_state=None,
        )

        closed_id = close_position(
            position_id=surrogate_id,
            exit_price=Decimal("0.6000"),
            exit_reason="target_hit",
            realized_pnl=Decimal("1.0000"),
        )

        assert closed_id is not None

        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT
                    trailing_stop_state IS NULL AS is_sql_null,
                    trailing_stop_state,
                    status
                FROM positions
                WHERE id = %s
                """,
                (closed_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row["status"] == "closed"
        assert row["is_sql_null"] is True, (
            f"trailing_stop_state must remain SQL NULL on the closed SCD "
            f"row; got is_sql_null={row['is_sql_null']!r}, "
            f"stored_value={row['trailing_stop_state']!r}"
        )
        assert row["trailing_stop_state"] is None
