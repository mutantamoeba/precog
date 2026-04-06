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


class _FakeDiag:
    """Stand-in for psycopg2 Diagnostics with controllable constraint_name."""

    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _StubUniqueViolation(psycopg2.errors.UniqueViolation):
    """UniqueViolation subclass that exposes a writable, fake ``diag``.

    psycopg2's native ``Error.diag`` is a read-only descriptor populated from
    libpq, so we cannot mutate it on a real ``UniqueViolation`` instance.
    Subclassing lets us override ``diag`` as a property; the helper reads
    via ``getattr(exc, "diag", None)``, so this stub is behaviorally
    indistinguishable while preserving ``isinstance`` checks.
    """

    def __init__(self, message: str, constraint_name: str | None) -> None:
        super().__init__(message)
        self._fake_diag = _FakeDiag(constraint_name)

    @property  # type: ignore[override]
    def diag(self) -> _FakeDiag:  # type: ignore[override]
        return self._fake_diag


class _StubCheckViolation(psycopg2.errors.CheckViolation):
    """CheckViolation subclass with the same writable-diag pattern."""

    def __init__(self, message: str, constraint_name: str | None) -> None:
        super().__init__(message)
        self._fake_diag = _FakeDiag(constraint_name)

    @property  # type: ignore[override]
    def diag(self) -> _FakeDiag:  # type: ignore[override]
        return self._fake_diag


def _make_unique_violation(constraint_name: str | None) -> psycopg2.errors.UniqueViolation:
    """Build a UniqueViolation-compatible exception with a controlled constraint_name."""
    return _StubUniqueViolation("simulated unique violation", constraint_name)


def _make_check_violation() -> psycopg2.errors.CheckViolation:
    """Build a CheckViolation as a non-matching IntegrityError sibling."""
    return _StubCheckViolation("simulated check violation", "balance_non_negative_check")


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
                new_balance=1234.5678,  # type: ignore[arg-type]
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
