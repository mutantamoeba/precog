"""Unit tests for database/crud_account module (account balance operations).

Stub test created for test type coverage audit compliance.
Module extracted from crud_operations.py in session 37-38 (ADR-115).

Issue #613 retry-behavior tests added to verify
``update_account_balance_with_versioning`` integrates the SCD race-prevention
retry helper correctly. The helper itself is unit-tested in
``tests/unit/database/test_crud_shared_retry.py``; these tests verify the
caller wires it up with the right constraint name and business key.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

import psycopg2.errors
import pytest

from precog.database.crud_account import (
    create_account_balance,
    update_account_balance_with_versioning,
)
from tests.unit.database._psycopg2_stubs import (
    _make_check_violation,
    _make_unique_violation,
)


@pytest.mark.unit
class TestCrudAccount:
    """Verify crud_account module is importable and exports expected functions."""

    def test_create_account_balance_is_callable(self):
        """create_account_balance should be a callable function."""
        assert callable(create_account_balance)


# =============================================================================
# Issue #613: retry-behavior unit tests for update_account_balance_with_versioning
# =============================================================================
#
# These tests stub the cursor returned by ``get_cursor`` to inject controlled
# UniqueViolation behavior on the INSERT step. The retry helper is exercised
# end-to-end through the public CRUD function, with no real DB. Race-condition
# verification against a live database lives in
# ``tests/race/test_account_balance_concurrent_first_insert.py``.
#
# The psycopg2 stub classes (_FakeDiag, _StubUniqueViolation,
# _StubCheckViolation) and their factory helpers live in the shared
# ``tests/unit/database/_psycopg2_stubs.py`` module so test_crud_shared_retry.py
# and the upcoming SCD CRUD tests for sibling tables can reuse them without
# duplicating the writable-diag pattern.


def _build_cursor_stub(insert_side_effect: Exception | None) -> MagicMock:
    """Construct a fake cursor whose INSERT either raises or returns id=42.

    The cursor receives four ``execute()`` calls per attempt in order:
        1. ``SELECT NOW() AS ts``
        2. ``SELECT ... FOR UPDATE`` (lock query)
        3. ``UPDATE account_balance ... row_current_ind = FALSE`` (close query)
        4. ``INSERT INTO account_balance ...`` (insert query)

    The first ``fetchone()`` after step 1 returns the timestamp; the second
    ``fetchone()`` after step 4 returns the inserted row id (or the
    ``insert_side_effect`` is raised before fetchone is reached).
    """
    cursor = MagicMock(name="cursor")

    timestamp_row = {"ts": "2026-04-06T12:00:00+00:00"}
    inserted_row = {"id": 42}

    fetchone_returns = [timestamp_row, inserted_row]

    def fetchone() -> dict[str, object]:
        return fetchone_returns.pop(0)

    cursor.fetchone.side_effect = fetchone

    call_index = {"n": 0}

    def execute(query: str, params: tuple | None = None) -> None:
        call_index["n"] += 1
        # The 4th execute call is the INSERT. Apply side effect if configured.
        if call_index["n"] == 4 and insert_side_effect is not None:
            raise insert_side_effect

    cursor.execute.side_effect = execute
    return cursor


def _patch_get_cursor(cursors: list[MagicMock]) -> patch._patch:
    """Patch ``crud_account.get_cursor`` to yield a fresh cursor per call.

    Each ``with get_cursor(commit=True)`` invocation pops one cursor off the
    front of ``cursors``. Each cursor models one attempt of the SCD close+insert
    sequence. This isolates retry attempts: attempt 1 uses cursors[0], attempt
    2 uses cursors[1].
    """
    iterator = iter(cursors)

    class _CursorContext:
        def __enter__(self) -> MagicMock:
            return next(iterator)

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def factory(commit: bool = False) -> _CursorContext:
        del commit  # signature must mirror get_cursor; we ignore it
        return _CursorContext()

    return patch("precog.database.crud_account.get_cursor", side_effect=factory)


@pytest.mark.unit
class TestUpdateBalanceRejectsFloat:
    """Float rejection runs before the retry helper is reached."""

    def test_float_balance_raises_before_db_call(self) -> None:
        """update_account_balance_with_versioning rejects float balances."""
        with pytest.raises(ValueError, match="Balance must be Decimal"):
            update_account_balance_with_versioning(
                platform_id="kalshi",
                new_balance=1234.5678,  # type: ignore[arg-type],
                execution_environment="paper",  # required (#622+#686)
            )


@pytest.mark.unit
class TestUpdateBalanceRetryBehavior:
    """End-to-end retry-helper integration via stubbed get_cursor."""

    def test_succeeds_first_attempt_no_retry(self, caplog: pytest.LogCaptureFixture) -> None:
        """Happy path: single attempt, single transaction, returns id."""
        cursors = [_build_cursor_stub(insert_side_effect=None)]

        with caplog.at_level(logging.WARNING, logger="precog.database.crud_account"):
            with _patch_get_cursor(cursors):
                result = update_account_balance_with_versioning(
                    platform_id="kalshi",
                    new_balance=Decimal("1000.0000"),
                    execution_environment="paper",  # required (#622+#686)
                )

        assert result == 42
        # Exactly four executes on the single cursor: NOW, lock, close, insert.
        assert cursors[0].execute.call_count == 4
        # No retry logs on the happy path.
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_retries_once_on_matching_unique_violation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """First attempt hits idx_balance_unique_current; second attempt succeeds."""
        first_cursor = _build_cursor_stub(
            insert_side_effect=_make_unique_violation("idx_balance_unique_current")
        )
        second_cursor = _build_cursor_stub(insert_side_effect=None)
        cursors = [first_cursor, second_cursor]

        with caplog.at_level(logging.WARNING, logger="precog.database.crud_account"):
            with _patch_get_cursor(cursors):
                result = update_account_balance_with_versioning(
                    platform_id="kalshi",
                    new_balance=Decimal("2500.0000"),
                    execution_environment="paper",  # required (#622+#686)
                )

        assert result == 42
        # First cursor reached the INSERT (4 executes) before raising.
        assert first_cursor.execute.call_count == 4
        # Second cursor completed all 4 executes successfully.
        assert second_cursor.execute.call_count == 4

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "exactly one WARNING between attempts"
        msg = warnings[0].getMessage()
        assert "idx_balance_unique_current" in msg
        assert "kalshi" in msg
        assert "platform_id" in msg

    def test_does_not_retry_on_check_violation(self, caplog: pytest.LogCaptureFixture) -> None:
        """CHECK violation (e.g., negative balance) re-raises without retry.

        Holden Condition 1: a bare except IntegrityError would mask this as a
        race-retry failure. The constraint_name discrimination prevents that.
        """
        cursors = [_build_cursor_stub(insert_side_effect=_make_check_violation())]

        with caplog.at_level(logging.WARNING, logger="precog.database.crud_account"):
            with _patch_get_cursor(cursors):
                with pytest.raises(psycopg2.errors.CheckViolation):
                    update_account_balance_with_versioning(
                        platform_id="kalshi",
                        new_balance=Decimal("-100.0000"),
                        execution_environment="paper",  # required (#622+#686)
                    )

        # Only the first cursor was used; no retry.
        assert cursors[0].execute.call_count == 4
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_does_not_retry_on_unique_violation_with_different_constraint(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A UniqueViolation on a non-matching constraint must NOT trigger retry."""
        cursors = [
            _build_cursor_stub(insert_side_effect=_make_unique_violation("some_other_unique_index"))
        ]

        with caplog.at_level(logging.WARNING, logger="precog.database.crud_account"):
            with _patch_get_cursor(cursors):
                with pytest.raises(psycopg2.errors.UniqueViolation):
                    update_account_balance_with_versioning(
                        platform_id="kalshi",
                        new_balance=Decimal("500.0000"),
                        execution_environment="paper",  # required (#622+#686)
                    )

        assert cursors[0].execute.call_count == 4
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_reraises_on_retry_exhaustion(self, caplog: pytest.LogCaptureFixture) -> None:
        """Both attempts hit the matching constraint -> ERROR + re-raise."""
        cursors = [
            _build_cursor_stub(
                insert_side_effect=_make_unique_violation("idx_balance_unique_current")
            ),
            _build_cursor_stub(
                insert_side_effect=_make_unique_violation("idx_balance_unique_current")
            ),
        ]

        with caplog.at_level(logging.WARNING, logger="precog.database.crud_account"):
            with _patch_get_cursor(cursors):
                with pytest.raises(psycopg2.errors.UniqueViolation):
                    update_account_balance_with_versioning(
                        platform_id="kalshi",
                        new_balance=Decimal("750.0000"),
                        execution_environment="paper",  # required (#622+#686)
                    )

        # Both cursors fully attempted (4 executes each).
        assert cursors[0].execute.call_count == 4
        assert cursors[1].execute.call_count == 4

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(warnings) == 1
        assert len(errors) == 1
        assert "idx_balance_unique_current" in errors[0].getMessage()
        assert "kalshi" in errors[0].getMessage()


# =============================================================================
# PR #631 / Claude Review Issue 1: refuse to silently return None
# =============================================================================
#
# The retry helper is generic over T (including None for callers that
# legitimately expect None on the success path). For money-touching SCD code
# the closure must NARROW that contract: if INSERT...RETURNING id yields no
# row -- e.g., a future DB trigger or constraint suppresses the return -- the
# closure raises RuntimeError rather than propagating None up to a caller
# that would treat it as a "successful" balance id.


@pytest.mark.unit
class TestUpdateBalanceRefusesSilentNone:
    """The closure raises RuntimeError if INSERT...RETURNING yields no row."""

    def test_raises_runtime_error_when_insert_returning_yields_no_row(self) -> None:
        """fetchone() after the INSERT returns None -> RuntimeError, not None.

        The cursor stub for this test is bespoke: it must succeed all four
        execute() calls (NOW, lock, close, insert) but return None from the
        SECOND fetchone() (the one that follows the INSERT). The shared
        ``_build_cursor_stub`` helper always returns ``{"id": 42}`` for that
        fetchone, so we cannot reuse it here.
        """
        cursor = MagicMock(name="cursor_returning_none")

        timestamp_row = {"ts": "2026-04-06T12:00:00+00:00"}
        # Second fetchone returns None to simulate INSERT...RETURNING yielding
        # no row. This is the failure mode the None-check guards against.
        fetchone_returns: list[dict[str, object] | None] = [timestamp_row, None]

        def fetchone() -> dict[str, object] | None:
            return fetchone_returns.pop(0)

        cursor.fetchone.side_effect = fetchone
        # All four execute calls succeed without raising.
        cursor.execute.return_value = None

        class _CursorContext:
            def __enter__(self) -> MagicMock:
                return cursor

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        def factory(commit: bool = False) -> _CursorContext:
            del commit
            return _CursorContext()

        with patch("precog.database.crud_account.get_cursor", side_effect=factory):
            with pytest.raises(RuntimeError, match="produced no row"):
                update_account_balance_with_versioning(
                    platform_id="kalshi",
                    new_balance=Decimal("1000.0000"),
                    execution_environment="paper",  # required (#622+#686)
                )

        # All four executes ran (NOW, lock, close, insert) before fetchone
        # returned None and the closure raised.
        assert cursor.execute.call_count == 4

    def test_raises_runtime_error_when_insert_returning_row_lacks_id(self) -> None:
        """fetchone() returns a dict missing the ``id`` key -> RuntimeError.

        Defensive companion to the None case: if a future trigger rewrites
        RETURNING to omit the id column, ``result.get("id")`` is None and
        the same guard fires. We assert the same RuntimeError surfaces so
        callers cannot silently propagate a missing balance id.
        """
        cursor = MagicMock(name="cursor_missing_id")

        timestamp_row = {"ts": "2026-04-06T12:00:00+00:00"}
        # Insert returns a row, but the ``id`` field is absent (or None).
        empty_inserted_row: dict[str, object] = {}
        fetchone_returns: list[dict[str, object]] = [timestamp_row, empty_inserted_row]

        def fetchone() -> dict[str, object]:
            return fetchone_returns.pop(0)

        cursor.fetchone.side_effect = fetchone
        cursor.execute.return_value = None

        class _CursorContext:
            def __enter__(self) -> MagicMock:
                return cursor

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        def factory(commit: bool = False) -> _CursorContext:
            del commit
            return _CursorContext()

        with patch("precog.database.crud_account.get_cursor", side_effect=factory):
            with pytest.raises(RuntimeError, match="produced no row"):
                update_account_balance_with_versioning(
                    platform_id="kalshi",
                    new_balance=Decimal("1000.0000"),
                    execution_environment="paper",  # required (#622+#686)
                )

        assert cursor.execute.call_count == 4
