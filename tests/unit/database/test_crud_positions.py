"""Unit tests for ``crud_positions`` position SCD + trade CRUD.

``crud_positions`` owns the position lifecycle (create, price update, close)
and the trade fill records. The position tables use SCD Type 2 versioning
(``row_current_ind = TRUE`` for the one current version per ``position_key``
business key), and every SCD supersede INSERT must carry
``execution_environment`` forward — Issue #662 is the living record of what
breaks when it does not.

These unit tests cover the highest-leverage subset of the module:

  * ``create_position`` — execution_environment validation, edge_at_entry
    calculation, returns surrogate id, Decimal parameter acceptance.
  * ``update_position_price`` — the #662 regression canary (INSERT MUST
    carry execution_environment forward), early-return optimization,
    status guard, and position-not-found ValueError.
  * ``close_position`` — a second execution_environment canary and the
    status guard mirroring update_position_price.
  * ``get_position_by_id`` / ``get_current_positions`` /
    ``get_positions_with_pnl`` — read helpers; assert ``row_current_ind``
    filtering is in the SQL, dict/list/None shapes, filter wiring.

Functions intentionally OUT OF SCOPE for this unit file (have their own
integration coverage, or would push the file past the session-63 pilot
scale of 25-35 tests):

  * ``set_trailing_stop_state`` — covered by
    ``test_crud_positions_trailing_stop_integration.py`` (Issue #629);
    the supersede path mirrors ``update_position_price`` so the canary
    here transfers semantically.
  * ``create_trade`` / ``get_trades_by_market`` / ``get_recent_trades`` /
    ``get_trade_by_id`` — trade fills deserve their own unit file; a
    separate burn-down PR is appropriate rather than cramming them in.
  * Retry-helper behavior (UniqueViolation discrimination, retry
    exhaustion) — ``test_crud_shared_retry.py`` owns the helper itself
    and ``test_crud_account_unit.py`` owns the caller-wiring pattern.
    Repeating both here would be duplicative; positions use the same
    helper with the same constraint name (``idx_positions_unique_current``).

Pattern references:
  * Pattern 1 — Decimal precision (NEVER float) for all money values.
  * Pattern 22 — VCR OR live for external API tests (N/A here: no HTTP).
  * Pattern 43 — Mock Fidelity: cursor.fetchone returns real-shaped DB rows
    (dict with ``id``, ``execution_environment``, ``status``, ... columns
    copied from the SELECT column list in crud_positions.py).
  * Pattern 49 — SCD Race Prevention: the INSERT column list MUST include
    ``execution_environment`` (Issue #662), ``edge_id`` (Issue #725), and
    every immutable attribution column on every supersede path.

Mock-target discipline:
  The CRUD module does ``from .connection import fetch_all, fetch_one,
  get_cursor`` into its own namespace. These unit tests patch at
  ``precog.database.crud_positions.get_cursor`` (and the ``fetch_one``
  equivalent), NOT at ``precog.database.connection.*`` — patching the
  origin module does not intercept names that have already been bound
  into ``crud_positions``'s namespace at import time. This is the
  #764 factory-vs-class mistake in miniature; getting it wrong means
  tests silently invoke the real DB.

Slice 2 — CRUD unit test burn-down (#887). Issue: #887.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import psycopg2.errors
import pytest

from precog.database.crud_positions import (
    close_position,
    create_position,
    get_current_positions,
    get_position_by_id,
    get_positions_with_pnl,
    update_position_price,
)
from tests.unit.database._psycopg2_stubs import _make_unique_violation

pytestmark = [pytest.mark.unit]


# =============================================================================
# HELPERS
# =============================================================================


def _mock_cursor_context(mock_get_cursor, mock_cursor=None):
    """Wire ``mock_get_cursor`` to yield ``mock_cursor`` from its context.

    Mirrors the helper of the same name in
    ``test_crud_ledger_account.py`` so anyone navigating sibling unit
    tests sees a consistent mocking idiom.
    """
    if mock_cursor is None:
        mock_cursor = MagicMock()
    mock_get_cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_get_cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


def _default_create_position_kwargs() -> dict:
    """Return minimal valid kwargs for ``create_position``.

    Decimal values only (Pattern 1). ``execution_environment='paper'``
    by default so tests exercise the non-live path and a regression that
    silently defaulted to 'live' would be visible immediately.
    """
    return {
        "market_id": 42,
        "strategy_id": 1,
        "model_id": 2,
        "side": "YES",
        "quantity": 100,
        "entry_price": Decimal("0.5200"),
        "execution_environment": "paper",
    }


def _current_position_row(**overrides) -> dict:
    """Return a DB-shaped row for a current position (matches the SELECT *).

    Every column the supersede INSERTs in ``update_position_price`` and
    ``close_position`` copy forward must be present here (Pattern 43 mock
    fidelity). Values are realistic Decimals / ints / strings so a caller
    that inadvertently mutates them can be caught by equality asserts.
    """
    base = {
        "id": 1,
        "position_key": "POS-1",
        "market_id": 42,
        "strategy_id": 1,
        "model_id": 2,
        "side": "YES",
        "quantity": 100,
        "entry_price": Decimal("0.5200"),
        "current_price": Decimal("0.5200"),
        "target_price": Decimal("0.7000"),
        "stop_loss_price": Decimal("0.4800"),
        "trailing_stop_state": None,
        "position_metadata": None,
        "status": "open",
        "entry_time": "2026-04-19T12:00:00+00:00",
        "exit_time": None,
        "exit_price": None,
        "exit_reason": None,
        "realized_pnl": None,
        "unrealized_pnl": Decimal("0.0000"),
        "calculated_probability": Decimal("0.6250"),
        "edge_at_entry": Decimal("0.1050"),
        "market_price_at_entry": Decimal("0.5200"),
        "execution_environment": "paper",
        "edge_id": None,
        "row_current_ind": True,
    }
    base.update(overrides)
    return base


def _build_supersede_cursor_stub(
    current_row: dict,
    new_id: int = 2,
    insert_side_effect: Exception | None = None,
) -> MagicMock:
    """Build a cursor that models one SCD close+insert attempt on positions.

    Sequence (matches ``_attempt_close_and_insert`` in both
    ``update_position_price`` and ``close_position``):

      1. ``SELECT NOW() AS ts`` -> fetchone returns ``{"ts": ...}``.
      2. ``SELECT id ... FOR UPDATE`` -> no fetchone needed.
      3. ``SELECT * ... row_current_ind = TRUE`` -> fetchone returns
         ``current_row``.
      4. ``UPDATE positions SET row_current_ind = FALSE`` (close).
      5. ``INSERT INTO positions ... RETURNING id`` -> fetchone returns
         ``{"id": new_id}``.

    Total: 5 execute() calls, 3 fetchone() calls.
    """
    cursor = MagicMock(name="cursor")

    fetchone_returns = [
        {"ts": "2026-04-19T12:00:00+00:00"},  # after SELECT NOW()
        current_row,  # after SELECT * ... row_current_ind = TRUE
        {"id": new_id},  # after INSERT ... RETURNING id
    ]

    def _fetchone():
        return fetchone_returns.pop(0)

    cursor.fetchone.side_effect = _fetchone

    call_index = {"n": 0}

    def _execute(query: str, params=None):
        call_index["n"] += 1
        # The 5th execute call is the INSERT. Apply side effect if configured.
        if call_index["n"] == 5 and insert_side_effect is not None:
            raise insert_side_effect

    cursor.execute.side_effect = _execute
    return cursor


def _patch_get_cursor_with_single(cursor: MagicMock):
    """Return a patch context that yields ``cursor`` from the single
    ``with get_cursor(commit=True)`` block inside the closure.
    """

    class _CursorContext:
        def __enter__(self):
            return cursor

        def __exit__(self, exc_type, exc, tb):
            return False

    def factory(commit: bool = False):
        del commit
        return _CursorContext()

    return patch("precog.database.crud_positions.get_cursor", side_effect=factory)


# =============================================================================
# A. create_position
# =============================================================================


class TestCreatePosition:
    """create_position — execution_environment validation, Decimal, surrogate id."""

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_returns_surrogate_id(self, mock_get_cursor):
        """Happy path: fetchone({id: 1}) -> returns 1."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        result = create_position(**_default_create_position_kwargs())

        assert result == 1

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_executes_insert_then_update(self, mock_get_cursor):
        """create_position issues exactly two execute() calls: INSERT + UPDATE.

        Step 1 INSERTs with position_key='TEMP' and gets the surrogate id
        back. Step 2 UPDATEs the same row to set position_key='POS-{id}'.
        A regression that skipped step 2 would leave every position with
        business key 'TEMP' and violate the unique index on
        (position_key, row_current_ind=TRUE).
        """
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 7}

        create_position(**_default_create_position_kwargs())

        assert mock_cursor.execute.call_count == 2
        # The second call sets the real position_key.
        second_call_params = mock_cursor.execute.call_args_list[1][0][1]
        assert second_call_params == ("POS-7", 7)

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_rejects_invalid_execution_environment(self, mock_get_cursor):
        """'unknown' is reserved for account_balance; must raise ValueError."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_create_position_kwargs()
        kwargs["execution_environment"] = "unknown"

        with pytest.raises(ValueError, match="Invalid execution_environment"):
            create_position(**kwargs)

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_rejects_typo_execution_environment(self, mock_get_cursor):
        """Near-miss 'Live' (wrong case) must fail loudly, not bypass to CHECK."""
        _mock_cursor_context(mock_get_cursor)

        kwargs = _default_create_position_kwargs()
        kwargs["execution_environment"] = "Live"

        with pytest.raises(ValueError, match="Invalid execution_environment"):
            create_position(**kwargs)

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_accepts_all_valid_execution_environments(self, mock_get_cursor):
        """'live', 'paper', 'backtest' are the three valid values for positions."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        for env in ("live", "paper", "backtest"):
            kwargs = _default_create_position_kwargs()
            kwargs["execution_environment"] = env
            result = create_position(**kwargs)
            assert result == 1

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_passes_execution_environment_in_insert_params(self, mock_get_cursor):
        """#662 canary for the CREATE path: execution_environment must be
        bound into the INSERT params tuple, not relied upon via DB default.
        """
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        kwargs = _default_create_position_kwargs()
        kwargs["execution_environment"] = "backtest"
        create_position(**kwargs)

        # First execute call is the INSERT. Its params tuple must contain
        # 'backtest' — if a regression dropped the column from the INSERT,
        # 'backtest' would be absent and this assertion would flip red.
        insert_params = mock_cursor.execute.call_args_list[0][0][1]
        assert "backtest" in insert_params

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_computes_edge_at_entry_from_prob_and_price(self, mock_get_cursor):
        """edge_at_entry = calculated_probability - market_price_at_entry.

        The literal arithmetic MUST use Decimal semantics; a float
        regression would propagate rounding error into the INSERT.
        """
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        kwargs = _default_create_position_kwargs()
        kwargs["calculated_probability"] = Decimal("0.6500")
        kwargs["market_price_at_entry"] = Decimal("0.5000")
        create_position(**kwargs)

        insert_params = mock_cursor.execute.call_args_list[0][0][1]
        # The Decimal-subtracted value must appear in the params tuple.
        assert Decimal("0.1500") in insert_params

    @patch("precog.database.crud_positions.get_cursor")
    def test_create_position_leaves_edge_at_entry_none_when_inputs_missing(self, mock_get_cursor):
        """If either input is None, edge_at_entry stays None."""
        mock_cursor = _mock_cursor_context(mock_get_cursor)
        mock_cursor.fetchone.return_value = {"id": 1}

        # Only probability provided; price missing.
        kwargs = _default_create_position_kwargs()
        kwargs["calculated_probability"] = Decimal("0.6500")
        create_position(**kwargs)

        insert_params = mock_cursor.execute.call_args_list[0][0][1]
        # There is no legitimate Decimal("0.1500") computation here; the
        # params should contain None for edge_at_entry. The simplest
        # strict check: no Decimal value equal to 0.1500 snuck in.
        assert Decimal("0.1500") not in insert_params


# =============================================================================
# B. update_position_price — #662 CANARY CLASS + guards
# =============================================================================


@pytest.mark.unit
class TestUpdatePositionPriceExecutionEnvironment:
    """Regression canary for #662 — execution_environment must survive SCD supersede."""

    @patch("precog.database.crud_positions.fetch_one")
    def test_update_position_price_preserves_execution_environment(self, mock_fetch_one):
        """#662 canary: update_position_price MUST carry execution_environment forward.

        Historical bug (fixed in commit af73928): the SCD INSERT on the
        supersede path omitted ``execution_environment`` from its
        column list, so the DB's DEFAULT 'live' silently overwrote
        any 'paper' or 'backtest' value on every price update —
        cross-environment money contamination with no audit signal.

        This test is the living canary for that fix. If
        update_position_price ever stops propagating
        execution_environment, the insert_params assertion below
        flips red immediately.
        """
        # Outer fetch_one calls: (1) business-key lookup, (2) initial current row.
        current_row = _current_position_row(
            execution_environment="paper",
            current_price=Decimal("0.5200"),
        )
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},  # Step 1: find business key
            current_row,  # Step 2: initial current row
        ]

        # Cursor inside the closure: NOW, FOR UPDATE, re-fetch, UPDATE, INSERT.
        cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=2)

        with _patch_get_cursor_with_single(cursor):
            result = update_position_price(
                position_id=1,
                current_price=Decimal("0.5800"),
            )

        assert result == 2

        # The 5th execute call is the INSERT. Its params tuple MUST include
        # 'paper' — the preserved execution_environment from the current row.
        # If the INSERT regressed to omit the column, the DB DEFAULT 'live'
        # would silently take over and 'paper' would NOT appear here.
        insert_params = cursor.execute.call_args_list[4][0][1]
        assert "paper" in insert_params, (
            "#662 CANARY FAILED: update_position_price INSERT did not bind "
            "execution_environment='paper'. The supersede path has regressed "
            "to the pre-af73928 state where DB DEFAULT 'live' would silently "
            "overwrite the paper/backtest value on every price update. "
            "Re-check the INSERT column list in crud_positions.py."
        )
        # And the stale 'live' default must NOT be bound for this test's
        # 'paper' case. A false-positive defense: if someone sees the
        # positive assertion pass on an all-'live' row, this negative
        # assertion would also matter on a paper row.
        assert "live" not in insert_params

    @patch("precog.database.crud_positions.fetch_one")
    def test_update_position_price_preserves_backtest_environment(self, mock_fetch_one):
        """Sibling canary — the 'backtest' case. Exercises a different value
        to catch a regression that hard-coded 'paper' in the INSERT."""
        current_row = _current_position_row(execution_environment="backtest")
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]
        cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=2)

        with _patch_get_cursor_with_single(cursor):
            update_position_price(
                position_id=1,
                current_price=Decimal("0.5800"),
            )

        insert_params = cursor.execute.call_args_list[4][0][1]
        assert "backtest" in insert_params
        assert "paper" not in insert_params
        assert "live" not in insert_params


@pytest.mark.unit
class TestUpdatePositionPriceGuards:
    """Guard behavior: not-found, status != 'open', no-state-change early return."""

    @patch("precog.database.crud_positions.fetch_one")
    def test_raises_value_error_when_position_id_never_existed(self, mock_fetch_one):
        """Step-1 business-key lookup returns None -> ValueError at the door."""
        mock_fetch_one.return_value = None

        with pytest.raises(ValueError, match="Position not found: 999"):
            update_position_price(
                position_id=999,
                current_price=Decimal("0.5800"),
            )

    @patch("precog.database.crud_positions.fetch_one")
    def test_raises_value_error_when_business_key_has_no_current_row(self, mock_fetch_one):
        """Step 1 finds the business key but Step 2 has no current row.

        Schema-invariant violation surface. Message must include the
        business key to aid debugging.
        """
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},  # Step 1: business key exists
            None,  # Step 2: no current row
        ]

        with pytest.raises(ValueError, match="schema invariant violation"):
            update_position_price(
                position_id=1,
                current_price=Decimal("0.5800"),
            )

    @patch("precog.database.crud_positions.fetch_one")
    def test_no_state_change_returns_existing_id_without_calling_cursor(self, mock_fetch_one):
        """Issue #113 early-return: same price + same trailing_stop -> no new version.

        This defends the monitor-loop 3600+ writes/hour regression.
        """
        current_row = _current_position_row(current_price=Decimal("0.5200"))
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]

        # get_cursor is patched but must NEVER be called.
        with patch("precog.database.crud_positions.get_cursor") as mock_get_cursor:
            result = update_position_price(
                position_id=1,
                current_price=Decimal("0.5200"),  # identical to current
            )

        assert result == current_row["id"]
        assert mock_get_cursor.call_count == 0

    @patch("precog.database.crud_positions.fetch_one")
    def test_raises_value_error_when_status_not_open_inside_closure(self, mock_fetch_one):
        """Status guard: closed/settled positions refuse the update.

        The outer fetch sees ``status='open'`` (so we get past early-return),
        but the in-closure re-fetch sees ``status='closed'`` — simulates a
        concurrent close committing between the outer fetch and the closure.
        The closure MUST raise ValueError with the non-open status in the
        message, not silently insert a new version over a terminal row.
        """
        outer_current_row = _current_position_row(current_price=Decimal("0.5200"))
        inner_current_row = _current_position_row(current_price=Decimal("0.5200"), status="closed")

        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            outer_current_row,
        ]

        # Cursor returns the CLOSED row on the in-closure re-fetch.
        cursor = _build_supersede_cursor_stub(current_row=inner_current_row)

        with _patch_get_cursor_with_single(cursor):
            with pytest.raises(ValueError, match="is not open"):
                update_position_price(
                    position_id=1,
                    current_price=Decimal("0.5800"),  # different, to bypass early-return
                )

    @patch("precog.database.crud_positions.fetch_one")
    def test_raises_value_error_on_settled_status(self, mock_fetch_one):
        """Status guard covers 'settled', not just 'closed' (positive-allow-list).

        Pins the ``status != 'open'`` semantics against a regression to
        ``status == 'closed'``. The close_position sibling has the same
        guard + same test (see TestClosePosition); mirroring here prevents
        drift between the two code paths. Glokta P2-2 (session 64 review).
        """
        outer_current_row = _current_position_row(current_price=Decimal("0.5200"))
        inner_current_row = _current_position_row(current_price=Decimal("0.5200"), status="settled")

        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            outer_current_row,
        ]
        cursor = _build_supersede_cursor_stub(current_row=inner_current_row)

        with _patch_get_cursor_with_single(cursor):
            with pytest.raises(ValueError, match="is not open"):
                update_position_price(
                    position_id=1,
                    current_price=Decimal("0.5800"),
                )

    @patch("precog.database.crud_positions.fetch_one")
    def test_returns_new_surrogate_id_on_successful_supersede(self, mock_fetch_one):
        """Happy path for the full supersede: returns the INSERT's new id."""
        current_row = _current_position_row(current_price=Decimal("0.5200"))
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]
        cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=99)

        with _patch_get_cursor_with_single(cursor):
            result = update_position_price(
                position_id=1,
                current_price=Decimal("0.5800"),  # different -> full supersede runs
            )

        assert result == 99
        # Five execute() calls on the one cursor (NOW, FOR UPDATE, SELECT *,
        # UPDATE close, INSERT). If any were skipped, the assert would fail.
        assert cursor.execute.call_count == 5


# =============================================================================
# C. close_position — second execution_environment canary + status guard
# =============================================================================


@pytest.mark.unit
class TestClosePosition:
    """close_position — SCD supersede with status='closed', exit fields, canary."""

    @patch("precog.database.crud_positions.fetch_one")
    def test_close_position_preserves_execution_environment(self, mock_fetch_one):
        """Second #662 canary: close_position MUST also carry
        execution_environment forward on its supersede INSERT.

        close_position has its own INSERT column list (distinct from
        update_position_price), so it needs its own canary. Issue #662
        was diagnosed in update_position_price but the sibling supersede
        in close_position has the identical shape and risk.
        """
        current_row = _current_position_row(execution_environment="paper")
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]
        cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=3)

        with _patch_get_cursor_with_single(cursor):
            result = close_position(
                position_id=1,
                exit_price=Decimal("0.6000"),
                exit_reason="target_hit",
                realized_pnl=Decimal("8.00"),
            )

        assert result == 3
        insert_params = cursor.execute.call_args_list[4][0][1]
        assert "paper" in insert_params
        assert "live" not in insert_params

    @patch("precog.database.crud_positions.fetch_one")
    def test_close_position_binds_exit_price_and_realized_pnl(self, mock_fetch_one):
        """Verify the caller-supplied exit values reach the INSERT params."""
        current_row = _current_position_row()
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]
        cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=3)

        with _patch_get_cursor_with_single(cursor):
            close_position(
                position_id=1,
                exit_price=Decimal("0.6000"),
                exit_reason="manual",
                realized_pnl=Decimal("8.0000"),
            )

        insert_params = cursor.execute.call_args_list[4][0][1]
        assert Decimal("0.6000") in insert_params
        assert Decimal("8.0000") in insert_params

    @patch("precog.database.crud_positions.fetch_one")
    def test_close_position_raises_when_position_id_never_existed(self, mock_fetch_one):
        """Position not found at business-key lookup -> ValueError."""
        mock_fetch_one.return_value = None

        with pytest.raises(ValueError, match="Position not found: 999"):
            close_position(
                position_id=999,
                exit_price=Decimal("0.6000"),
                exit_reason="target_hit",
                realized_pnl=Decimal("8.0000"),
            )

    @patch("precog.database.crud_positions.fetch_one")
    def test_close_position_raises_value_error_on_double_close_race(self, mock_fetch_one):
        """Status guard: a concurrent close race must surface as ValueError.

        Two concurrent close_position callers: the first commits
        status='closed'; the second's in-closure re-fetch sees the
        terminal state. Without the guard, the second caller silently
        overwrites the first's exit_price and realized_pnl. With the
        guard, a loud ValueError surfaces to the outer handler.
        """
        outer_current_row = _current_position_row()
        inner_current_row = _current_position_row(status="closed")

        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            outer_current_row,
        ]

        cursor = _build_supersede_cursor_stub(current_row=inner_current_row)

        with _patch_get_cursor_with_single(cursor):
            with pytest.raises(ValueError, match="is not open"):
                close_position(
                    position_id=1,
                    exit_price=Decimal("0.6000"),
                    exit_reason="stop_loss",
                    realized_pnl=Decimal("-1.0000"),
                )

    @patch("precog.database.crud_positions.fetch_one")
    def test_close_position_raises_value_error_on_settled_status(self, mock_fetch_one):
        """The ``!= 'open'`` guard must ALSO reject 'settled' (not just 'closed').

        Pins the positive-allow-list semantics: status must BE 'open', not
        just not-be 'closed'. A future regression to ``== 'closed'`` would
        let 'settled' (and NULL) slip through — this test catches that.
        """
        outer_current_row = _current_position_row()
        inner_current_row = _current_position_row(status="settled")

        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            outer_current_row,
        ]

        cursor = _build_supersede_cursor_stub(current_row=inner_current_row)

        with _patch_get_cursor_with_single(cursor):
            with pytest.raises(ValueError, match="is not open"):
                close_position(
                    position_id=1,
                    exit_price=Decimal("0.6000"),
                    exit_reason="settlement",
                    realized_pnl=Decimal("8.0000"),
                )


# =============================================================================
# D. Retry-helper integration (thin wiring check, not the helper itself)
# =============================================================================


@pytest.mark.unit
class TestUpdatePositionPriceRetryWiring:
    """Wiring check: update_position_price routes through
    ``retry_on_scd_unique_conflict`` with the correct constraint name
    (``idx_positions_unique_current``).

    We do NOT re-verify the helper's internal logic — that is owned by
    ``test_crud_shared_retry.py``. Here we only exercise the caller
    wiring: on a matching UniqueViolation the operation retries once,
    and a non-matching constraint does NOT retry.
    """

    @patch("precog.database.crud_positions.fetch_one")
    def test_retries_once_on_matching_positions_unique_violation(self, mock_fetch_one):
        """First INSERT hits idx_positions_unique_current; retry succeeds."""
        current_row = _current_position_row()
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]

        # First attempt: INSERT raises UniqueViolation on the matching index.
        first_cursor = _build_supersede_cursor_stub(
            current_row=current_row,
            insert_side_effect=_make_unique_violation("idx_positions_unique_current"),
        )
        # Second attempt: clean success.
        second_cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=42)

        cursors = iter([first_cursor, second_cursor])

        class _CursorContext:
            def __init__(self, cur):
                self._cur = cur

            def __enter__(self):
                return self._cur

            def __exit__(self, exc_type, exc, tb):
                return False

        def factory(commit: bool = False):
            del commit
            return _CursorContext(next(cursors))

        with patch("precog.database.crud_positions.get_cursor", side_effect=factory):
            result = update_position_price(
                position_id=1,
                current_price=Decimal("0.5800"),
            )

        assert result == 42
        # Both attempts ran all 5 executes.
        assert first_cursor.execute.call_count == 5
        assert second_cursor.execute.call_count == 5

    @patch("precog.database.crud_positions.fetch_one")
    def test_non_matching_constraint_does_not_retry(self, mock_fetch_one):
        """Wrong-constraint UniqueViolation must re-raise, NOT trigger retry.

        Proves the caller wiring passes 'idx_positions_unique_current' as
        the constraint-name discriminator (not some generic "retry on any
        UniqueViolation" degradation). If the wiring ever regresses to
        bare-UniqueViolation matching, this test catches it at unit speed.
        Glokta P2-1 / Ripley F2 (session 64 review).
        """
        current_row = _current_position_row()
        mock_fetch_one.side_effect = [
            {"position_key": "POS-1"},
            current_row,
        ]

        # First attempt raises a UniqueViolation on a DIFFERENT index —
        # the retry helper should NOT swallow it.
        first_cursor = _build_supersede_cursor_stub(
            current_row=current_row,
            insert_side_effect=_make_unique_violation("idx_some_other_unique"),
        )
        # Second cursor is present but must NEVER be entered.
        second_cursor = _build_supersede_cursor_stub(current_row=current_row, new_id=999)

        cursors = iter([first_cursor, second_cursor])

        class _CursorContext:
            def __init__(self, cur):
                self._cur = cur

            def __enter__(self):
                return self._cur

            def __exit__(self, exc_type, exc, tb):
                return False

        def factory(commit: bool = False):
            del commit
            return _CursorContext(next(cursors))

        with patch("precog.database.crud_positions.get_cursor", side_effect=factory):
            with pytest.raises(psycopg2.errors.UniqueViolation):
                update_position_price(
                    position_id=1,
                    current_price=Decimal("0.5800"),
                )

        # Only the first cursor ever ran. No retry.
        assert first_cursor.execute.call_count == 5
        assert second_cursor.execute.call_count == 0


# =============================================================================
# E. get_position_by_id — read helper
# =============================================================================


@pytest.mark.unit
class TestGetPositionById:
    """get_position_by_id returns current version only (row_current_ind filter)."""

    @patch("precog.database.crud_positions.fetch_one")
    def test_returns_dict_when_position_exists(self, mock_fetch_one):
        """Row present -> dict returned."""
        row = _current_position_row()
        mock_fetch_one.return_value = row

        result = get_position_by_id(position_id=1)

        assert result == row

    @patch("precog.database.crud_positions.fetch_one")
    def test_returns_none_when_position_missing(self, mock_fetch_one):
        """No row -> None returned, NOT an empty dict / falsy artifact."""
        mock_fetch_one.return_value = None

        result = get_position_by_id(position_id=999)

        assert result is None

    @patch("precog.database.crud_positions.fetch_one")
    def test_query_filters_row_current_ind_true(self, mock_fetch_one):
        """SCD Type 2 filter — the SQL MUST include row_current_ind = TRUE.

        Without this filter, historical versions would be returned and
        the caller would silently read stale data.
        """
        mock_fetch_one.return_value = None

        get_position_by_id(position_id=1)

        query = mock_fetch_one.call_args[0][0]
        assert "row_current_ind = TRUE" in query
        assert "p.id = %s" in query


# =============================================================================
# F. get_current_positions — read helper with filter wiring
# =============================================================================


@pytest.mark.unit
class TestGetCurrentPositions:
    """get_current_positions: filters by status, market_id, execution_environment."""

    @patch("precog.database.crud_positions.fetch_all")
    def test_returns_empty_list_when_no_positions(self, mock_fetch_all):
        mock_fetch_all.return_value = []

        result = get_current_positions()

        assert result == []

    @patch("precog.database.crud_positions.fetch_all")
    def test_default_query_filters_row_current_ind_true(self, mock_fetch_all):
        """The base WHERE clause MUST filter row_current_ind = TRUE."""
        mock_fetch_all.return_value = []

        get_current_positions()

        query = mock_fetch_all.call_args[0][0]
        assert "p.row_current_ind = TRUE" in query

    @patch("precog.database.crud_positions.fetch_all")
    def test_status_filter_appends_and_clause(self, mock_fetch_all):
        """status='open' -> ``AND p.status = %s`` with 'open' in params."""
        mock_fetch_all.return_value = []

        get_current_positions(status="open")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "p.status = %s" in query
        assert "open" in params

    @patch("precog.database.crud_positions.fetch_all")
    def test_execution_environment_filter_appends_and_clause(self, mock_fetch_all):
        """execution_environment='paper' -> filter + 'paper' in params."""
        mock_fetch_all.return_value = []

        get_current_positions(execution_environment="paper")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "p.execution_environment = %s" in query
        assert "paper" in params

    @patch("precog.database.crud_positions.fetch_all")
    def test_default_limit_and_offset_are_applied(self, mock_fetch_all):
        """Default pagination: LIMIT 100 OFFSET 0."""
        mock_fetch_all.return_value = []

        get_current_positions()

        params = mock_fetch_all.call_args[0][1]
        assert 100 in params  # default limit
        assert 0 in params  # default offset


# =============================================================================
# G. get_positions_with_pnl — PnL-calculating read helper
# =============================================================================


@pytest.mark.unit
class TestGetPositionsWithPnl:
    """get_positions_with_pnl: SCD filter + status filter wiring."""

    @patch("precog.database.crud_positions.fetch_all")
    def test_returns_empty_list_when_no_positions(self, mock_fetch_all):
        mock_fetch_all.return_value = []

        result = get_positions_with_pnl()

        assert result == []

    @patch("precog.database.crud_positions.fetch_all")
    def test_query_filters_row_current_ind_true(self, mock_fetch_all):
        """SCD Type 2 filter on positions + market_snapshots JOIN."""
        mock_fetch_all.return_value = []

        get_positions_with_pnl()

        query = mock_fetch_all.call_args[0][0]
        assert "p.row_current_ind = TRUE" in query
        # market_snapshots JOIN also filters row_current_ind on its side
        # so the current pricing surface is used.
        assert "ms.row_current_ind = TRUE" in query

    @patch("precog.database.crud_positions.fetch_all")
    def test_status_filter_is_case_insensitive(self, mock_fetch_all):
        """The status filter wraps both sides in LOWER(); regression would
        make status='Open' silently return zero rows vs. a stored 'open'."""
        mock_fetch_all.return_value = []

        get_positions_with_pnl(status="open")

        query = mock_fetch_all.call_args[0][0]
        params = mock_fetch_all.call_args[0][1]
        assert "LOWER(p.status) = LOWER(%s)" in query
        assert "open" in params


# =============================================================================
# H. Import-time sanity — catches module-level regressions early
# =============================================================================


@pytest.mark.unit
class TestModuleImports:
    """Module-level wiring sanity: functions we rely on are importable and
    psycopg2 errors are reachable for the retry stubs above.

    Kept minimal — these are sentinels that give a clearer failure signal
    than deep-stack import errors when someone reorganizes the module.
    """

    def test_public_functions_are_callable(self):
        assert callable(create_position)
        assert callable(update_position_price)
        assert callable(close_position)
        assert callable(get_position_by_id)
        assert callable(get_current_positions)
        assert callable(get_positions_with_pnl)

    def test_psycopg2_unique_violation_is_reachable(self):
        """The retry path catches IntegrityError subclasses; smoke-check
        that psycopg2.errors.UniqueViolation still exists at the expected
        import path (a refactor or dep bump that moved it would break
        the retry helper and every retry test in this suite)."""
        assert issubclass(psycopg2.errors.UniqueViolation, psycopg2.errors.IntegrityError)
