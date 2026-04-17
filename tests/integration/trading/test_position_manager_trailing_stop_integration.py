"""Integration tests for ``PositionManager`` trailing-stop read-path Decimal preservation.

Issue #669: ``check_trailing_stop_trigger`` and ``update_trailing_stop`` were
comparing a ``Decimal`` ``current_price`` against a JSONB-round-tripped
``current_stop_price`` that psycopg2 returns as a plain Python ``str``,
raising::

    TypeError: '<=' not supported between instances of 'decimal.Decimal' and 'str'

The symmetric write-side serializer ``crud_positions._jsonb_dumps`` (added in
PR #671 for #629) emits ``Decimal`` values as their string representation;
psycopg2's JSONB decoder hands those strings back unchanged at read time. The
``TrailingStopState`` TypedDict (``trading/types.py``) declares all
Decimal-bearing fields as ``Decimal`` -- the type contract was lying about the
runtime reality until ``_decode_trailing_stop_state`` was added in
``position_manager.py`` to restore Decimal types at the read boundary.

These tests would have caught the #669 bug class immediately because they:

    1. Use the production write path (``initialize_trailing_stop`` ->
       ``set_trailing_stop_state``) so trailing_stop_state is real JSONB in
       a committed row.
    2. Re-fetch via ``check_trailing_stop_trigger`` /
       ``update_trailing_stop``, which call ``get_connection`` and read the
       persisted JSONB through psycopg2's real decoder.
    3. Pass production-shape ``Decimal`` ``current_price`` arguments and
       assert that arithmetic and comparisons inside the methods do not
       raise ``TypeError``.

Mock-based unit tests cannot reproduce this bug class because the mocks
deliver pre-shaped Python objects that bypass psycopg2's JSONB decoder.

The Mock Fidelity Rule (protocols.md) is the design rule that catches this:
test fixtures must match the runtime types of the code under test, not the
ideal types declared in the TypedDict. ``test_position_manager_trailing_stops.py``
was updated in the same PR to use STRING values in the trailing_stop_state
fixture for exactly this reason.

Reference:
    - Issue #669: trailing stop READ path Decimal-vs-string mismatch.
    - PR #671 (#628 + #629): symmetric write-side serializer.
    - ``crud_positions._jsonb_dumps``: write-side counterpart.
    - ``position_manager._decode_trailing_stop_state``: read-side helper.
    - Pattern 1 (CLAUDE.md): Decimal Precision -- NEVER USE FLOAT.
    - Mock Fidelity Rule (protocols.md).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.trading.position_manager import (
    PositionManager,
    _decode_trailing_stop_state,
)

# Test identifiers reserved for this integration suite. The TEST- prefix lets
# the suite-wide ``clean_test_data`` cleanup pick up any orphaned rows the
# explicit teardown below misses.
_TEST_TICKER = "TEST-INT-669-MKT"
_TEST_POSITION_BK_PREFIX = "TEST-INT-669-POS-"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def trailing_stop_open_position(db_pool: Any) -> Any:
    """Create a clean test market + open position; tear down after each test.

    Mirrors the fixture pattern from
    ``tests/integration/database/test_crud_positions_trailing_stop_integration.py``:
    uses its own ``get_cursor(commit=True)`` blocks (NOT the suite-wide
    ``clean_test_data`` rollback fixture) because the production code paths
    under test commit real rows that would survive a transaction rollback.

    Yields a tuple of (position_surrogate_id, position_business_key, market_pk)
    so each test can address the position by its surrogate id (the public
    PositionManager entry point) and verify state by business key (the SCD
    chain identifier).
    """
    position_bk = f"{_TEST_POSITION_BK_PREFIX}1"

    with get_cursor(commit=True) as cur:
        # Cleanup in FK order: positions first (FKs to markets), then markets.
        cur.execute(
            "DELETE FROM positions WHERE position_key LIKE %s",
            (_TEST_POSITION_BK_PREFIX + "%",),
        )
        from tests.fixtures.cleanup_helpers import delete_market_with_children

        delete_market_with_children(cur, "ticker = %s", (_TEST_TICKER,))

    # Create the underlying market (positions FK to markets.id) via the
    # CRUD helper.  Migration 0062 (#791): markets.market_key is NOT NULL +
    # UNIQUE; ``create_market`` handles the canonical ``TEMP → MKT-{id}``
    # two-step internally, keeping this fixture in sync with production
    # semantics.
    from decimal import Decimal as _Decimal

    from precog.database.crud_markets import create_market

    market_pk = create_market(
        platform_id="kalshi",
        event_id=None,
        external_id=f"{_TEST_TICKER}-EXT",
        ticker=_TEST_TICKER,
        title="Issue 669 Integration Market",
        yes_ask_price=_Decimal("0.5000"),
        no_ask_price=_Decimal("0.5000"),
        market_type="binary",
        status="open",
    )

    with get_cursor(commit=True) as cur:
        # Create the initial open position (current row, no trailing stop yet).
        # We bypass PositionManager.open_position() here because it requires
        # a strategy_id + model_id + market_snapshot, and the bug under test
        # lives entirely on the trailing-stop read path -- not the open path.
        # The minimal-row approach mirrors the #629 integration fixture.
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
                100,
                Decimal("0.5000"),  # entry_price
                Decimal("0.5500"),  # current_price (initial)
                Decimal("0.4500"),  # stop_loss_price (static fallback)
                "open",
                "paper",
            ),
        )
        position_surrogate_id = cur.fetchone()["id"]

    yield position_surrogate_id, position_bk, market_pk

    # Teardown: remove all rows this test touched. Best-effort; do not mask
    # the actual test outcome.
    try:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM positions WHERE position_key = %s", (position_bk,))
            from tests.fixtures.cleanup_helpers import delete_market_with_children

            delete_market_with_children(cur, "id = %s", (market_pk,))
    except Exception:
        pass


# =============================================================================
# _decode_trailing_stop_state helper unit tests
# =============================================================================


@pytest.mark.integration
class TestDecodeTrailingStopStateHelper:
    """Pure unit tests for the read-side decoder helper.

    These verify the helper's idempotency, None-tolerance, and partial-input
    tolerance. They live in this file (rather than the unit test file) so the
    helper's contract sits next to the integration tests that exercise it
    end-to-end -- the connection between the round-trip shape and the helper
    is the whole point of #669.
    """

    def test_decodes_string_values_to_decimal(self) -> None:
        """Round-trip shape from JSONB: every Decimal-bearing key is a str."""
        state = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": True,
            "activation_price": "0.65",
            "current_stop_price": "0.60",
            "highest_price": "0.75",
        }

        decoded = _decode_trailing_stop_state(state)

        assert decoded is not None
        # Top-level Decimal-bearing keys.
        assert decoded["activation_price"] == Decimal("0.65")
        assert isinstance(decoded["activation_price"], Decimal)
        assert decoded["current_stop_price"] == Decimal("0.60")
        assert isinstance(decoded["current_stop_price"], Decimal)
        assert decoded["highest_price"] == Decimal("0.75")
        assert isinstance(decoded["highest_price"], Decimal)
        # Non-Decimal keys preserved.
        assert decoded["activated"] is True
        # Nested config Decimal-bearing keys.
        assert decoded["config"]["activation_threshold"] == Decimal("0.15")
        assert isinstance(decoded["config"]["activation_threshold"], Decimal)
        assert decoded["config"]["initial_distance"] == Decimal("0.05")
        assert decoded["config"]["tightening_rate"] == Decimal("0.10")
        assert decoded["config"]["floor_distance"] == Decimal("0.02")

    def test_idempotent_on_decimal_values(self) -> None:
        """Helper is safe to apply twice (or to in-memory dicts that never round-tripped)."""
        state = {
            "config": {
                "activation_threshold": Decimal("0.15"),
                "initial_distance": Decimal("0.05"),
                "tightening_rate": Decimal("0.10"),
                "floor_distance": Decimal("0.02"),
            },
            "activated": True,
            "activation_price": Decimal("0.65"),
            "current_stop_price": Decimal("0.60"),
            "highest_price": Decimal("0.75"),
        }

        decoded = _decode_trailing_stop_state(state)

        assert decoded is not None
        assert decoded["activation_price"] == Decimal("0.65")
        assert decoded["current_stop_price"] == Decimal("0.60")
        assert decoded["highest_price"] == Decimal("0.75")
        assert decoded["config"]["activation_threshold"] == Decimal("0.15")

        # Apply the helper twice -- still Decimal, still equal.
        twice_decoded = _decode_trailing_stop_state(decoded)
        assert twice_decoded is not None
        assert twice_decoded["activation_price"] == Decimal("0.65")
        assert twice_decoded["config"]["floor_distance"] == Decimal("0.02")

    def test_returns_none_for_none_input(self) -> None:
        """Positions without trailing stops have ``trailing_stop_state = NULL``."""
        assert _decode_trailing_stop_state(None) is None

    def test_handles_missing_config_key(self) -> None:
        """A partial dict with no ``config`` key must not raise."""
        state = {
            "activated": False,
            "activation_price": None,
            "current_stop_price": "0.50",
            "highest_price": "0.60",
        }
        decoded = _decode_trailing_stop_state(state)
        assert decoded is not None
        assert decoded["current_stop_price"] == Decimal("0.50")
        assert decoded["highest_price"] == Decimal("0.60")
        assert "config" not in decoded

    def test_handles_none_config(self) -> None:
        """A dict with ``config = None`` must not raise."""
        state = {
            "config": None,
            "activated": False,
            "activation_price": None,
            "current_stop_price": "0.50",
            "highest_price": "0.60",
        }
        decoded = _decode_trailing_stop_state(state)
        assert decoded is not None
        assert decoded["config"] is None
        assert decoded["current_stop_price"] == Decimal("0.50")

    def test_handles_none_top_level_decimal_fields(self) -> None:
        """``activation_price`` is None until the trailing stop activates."""
        state = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": False,
            "activation_price": None,  # Pre-activation
            "current_stop_price": "0.45",
            "highest_price": "0.55",
        }
        decoded = _decode_trailing_stop_state(state)
        assert decoded is not None
        assert decoded["activation_price"] is None  # Stays None
        assert decoded["current_stop_price"] == Decimal("0.45")

    def test_does_not_mutate_input(self) -> None:
        """Helper returns a new dict; the input dict is unchanged."""
        state = {
            "config": {
                "activation_threshold": "0.15",
                "initial_distance": "0.05",
                "tightening_rate": "0.10",
                "floor_distance": "0.02",
            },
            "activated": True,
            "activation_price": "0.65",
            "current_stop_price": "0.60",
            "highest_price": "0.75",
        }
        original_top = state["current_stop_price"]
        original_nested = state["config"]["activation_threshold"]

        _decode_trailing_stop_state(state)

        # Input dict still has string values; helper produced an independent copy.
        assert state["current_stop_price"] == original_top
        assert isinstance(state["current_stop_price"], str)
        assert state["config"]["activation_threshold"] == original_nested
        assert isinstance(state["config"]["activation_threshold"], str)


# =============================================================================
# End-to-end JSONB round-trip tests
# =============================================================================


@pytest.mark.integration
class TestTrailingStopReadPathRoundTrip:
    """End-to-end tests that exercise the JSONB write -> read round-trip via the
    real PositionManager methods.

    These would have failed pre-#669 with::

        TypeError: '<=' not supported between instances of 'decimal.Decimal' and 'str'

    on the comparison ``current_price <= stop_price`` inside
    ``check_trailing_stop_trigger``, or on the arithmetic
    ``current_price - config["initial_distance"]`` inside
    ``update_trailing_stop``.
    """

    def test_check_trailing_stop_trigger_after_jsonb_round_trip(
        self, trailing_stop_open_position: tuple[int, str, int]
    ) -> None:
        """End-to-end: initialize trailing stop, activate via update, then check trigger.

        The bug pre-#669 was that the check method read JSONB-encoded
        ``current_stop_price`` as a Python ``str`` and tried to compare it
        against a ``Decimal`` ``current_price``, raising TypeError.

        This test exercises the full path against a real database:

            1. ``initialize_trailing_stop`` writes the inactive state via
               JSONB (Decimal -> string at the write boundary).
            2. ``update_trailing_stop`` reads it back, activates the stop
               (because the unrealized PnL crosses the activation threshold),
               and writes the activated state back.
            3. ``check_trailing_stop_trigger`` reads the activated state and
               must compare ``current_price`` against ``current_stop_price``
               WITHOUT raising TypeError.
        """
        surrogate_id, _position_bk, _market_pk = trailing_stop_open_position
        manager = PositionManager()

        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.10"),
            "floor_distance": Decimal("0.02"),
        }

        # Step 1: initialize trailing stop on the open position. The state is
        # written through ``crud_positions._jsonb_dumps``, which serializes
        # Decimal values as their string representation.
        position_v1 = manager.initialize_trailing_stop(surrogate_id, config)
        assert position_v1["trailing_stop_state"] is not None

        # Step 2: drive the price up enough to cross the activation threshold.
        # Entry price is 0.5000 with quantity 100, so a price move from 0.5500
        # (initial current_price) to 0.6800 yields PnL = 100 * (0.68 - 0.50)
        # = 18.00 >> 0.15 activation_threshold. update_trailing_stop will:
        #   (a) read the prior trailing_stop_state from JSONB (string values),
        #   (b) decode via _decode_trailing_stop_state (THIS IS THE FIX),
        #   (c) compute activation, write a new SCD version with Decimals,
        #   (d) the JSONB encoder serializes them back to strings.
        position_v2 = manager.update_trailing_stop(position_v1["id"], Decimal("0.6800"))
        # The CRUD layer is the canonical write path; the post-write trailing
        # state (in-memory dict) carries Decimals because the production code
        # constructs the new state with Decimals before handing it to the CRUD.
        assert position_v2["trailing_stop_state"]["activated"] is True

        # Step 3: drop the price to trigger the stop. By the time we get here,
        # the trailing_stop_state has round-tripped through JSONB ONCE and
        # the check method must read it back through psycopg2's decoder.
        # current_stop_price will be a string in the row; the read-path
        # helper must decode it to Decimal so the comparison works.
        triggered = manager.check_trailing_stop_trigger(position_v2["id"])

        # Whether the actual stop fires depends on where update_trailing_stop's
        # tightening formula put current_stop_price -- the IMPORTANT property is
        # that the call returns a bool without raising TypeError on the
        # Decimal-vs-string comparison. The bug pre-#669 raised TypeError BEFORE
        # the bool was computed.
        assert isinstance(triggered, bool)

    def test_update_trailing_stop_after_jsonb_round_trip(
        self, trailing_stop_open_position: tuple[int, str, int]
    ) -> None:
        """End-to-end: initialize, then call update_trailing_stop multiple times.

        Each call reads the prior state from JSONB (which round-tripped through
        the encoder on the previous write) and must perform Decimal arithmetic
        on the decoded values without raising TypeError. This catches the
        ``update_trailing_stop`` arithmetic bugs at sites 1-7 from #669:

            * unrealized_pnl >= config["activation_threshold"]
            * current_price - config["initial_distance"]
            * current_price > trailing_state["highest_price"]
            * Decimal("1") - (config["tightening_rate"] * profit_ratio)
            * max(config["floor_distance"], config["initial_distance"] * factor)
            * trailing_state["highest_price"] - distance
            * new_stop > trailing_state["current_stop_price"]
        """
        surrogate_id, position_bk, _market_pk = trailing_stop_open_position
        manager = PositionManager()

        config = {
            "activation_threshold": Decimal("0.15"),
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.10"),
            "floor_distance": Decimal("0.02"),
        }

        # Initialize on the open position.
        position_v1 = manager.initialize_trailing_stop(surrogate_id, config)

        # Walk the price up step by step. Each call exercises the read-path
        # decoder because each iteration reads the JSONB row written by the
        # previous iteration. Pre-#669, the second call would raise on the
        # ``if current_price > trailing_state["highest_price"]`` comparison.
        prices = [
            Decimal("0.6500"),  # crosses activation (PnL = 100 * 0.15 = 15.00)
            Decimal("0.7000"),  # new high, tightens stop
            Decimal("0.7500"),  # new high, tightens further
            Decimal("0.7200"),  # NOT a new high; stop must not move down
            Decimal("0.8000"),  # new high again
        ]

        last_position = position_v1
        last_highest = Decimal("0.0000")
        last_stop = Decimal("-1.0000")  # impossible sentinel
        for price in prices:
            updated = manager.update_trailing_stop(last_position["id"], price)

            # The state passed back from the CRUD wrapper is a fresh row
            # dict; verify the trailing_stop_state structure is sane.
            state = updated["trailing_stop_state"]
            assert state is not None
            # The state in the dict comes back as JSONB-decoded -- it MAY
            # contain Decimal values (if psycopg2 returned them via fetchone
            # and the helper decoded them) or plain strings (if returned
            # without decoding). Apply the helper here to verify either way.
            decoded = _decode_trailing_stop_state(state)
            assert decoded is not None
            assert decoded["activated"] is True

            # Highest price should be the running max.
            highest = decoded["highest_price"]
            assert isinstance(highest, Decimal)
            assert highest >= last_highest, (
                f"highest_price regressed: {highest} < {last_highest} (price={price})"
            )
            last_highest = max(last_highest, price)

            # Current stop should never decrease (trailing stops only move up).
            current_stop = decoded["current_stop_price"]
            assert isinstance(current_stop, Decimal)
            if last_stop > Decimal("-1"):
                assert current_stop >= last_stop, (
                    f"current_stop_price regressed: {current_stop} < {last_stop} (price={price})"
                )
            last_stop = current_stop

            last_position = updated

        # Final sanity: the SCD chain should have the right number of rows.
        # initialize (1 historical -> 1 current) + 5 update calls = 6 rows total.
        with get_cursor(commit=False) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM positions WHERE position_key = %s
                """,
                (position_bk,),
            )
            count_row = cur.fetchone()
            # 1 original + 1 from initialize + 5 from updates = 7 rows
            assert count_row["n"] == 7, (
                f"expected 7 SCD rows (1 original + 1 init + 5 updates), found {count_row['n']}"
            )

    def test_check_trailing_stop_trigger_inactive_after_round_trip(
        self, trailing_stop_open_position: tuple[int, str, int]
    ) -> None:
        """A non-activated trailing stop returns False from check after round-trip.

        Even though no Decimal arithmetic happens on the inactive branch (the
        method short-circuits at ``if not trailing_state['activated']``), the
        helper still has to be applied so the dict is in a consistent
        Decimal-typed shape for any downstream code. This test verifies the
        early-return path also tolerates the JSONB round-trip.
        """
        surrogate_id, _position_bk, _market_pk = trailing_stop_open_position
        manager = PositionManager()

        config = {
            "activation_threshold": Decimal("0.99"),  # impossible to activate
            "initial_distance": Decimal("0.05"),
            "tightening_rate": Decimal("0.10"),
            "floor_distance": Decimal("0.02"),
        }

        position_v1 = manager.initialize_trailing_stop(surrogate_id, config)
        assert position_v1["trailing_stop_state"]["activated"] is False

        # Even with no arithmetic on the read path, the call must complete
        # without raising on dict access into the JSONB-decoded state.
        triggered = manager.check_trailing_stop_trigger(position_v1["id"])
        assert triggered is False
