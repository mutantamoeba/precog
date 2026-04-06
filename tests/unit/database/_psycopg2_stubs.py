"""Shared psycopg2 exception stubs for database CRUD unit tests.

This is a private fixture module (underscore prefix) for the
``tests/unit/database/`` test directory. It exists to deduplicate the
``UniqueViolation`` / ``CheckViolation`` / ``Diagnostics`` stubs that
multiple SCD CRUD test modules need to inject controlled
``constraint_name`` values into the SCD race-prevention retry helper
(see ``precog.database.crud_shared.retry_on_scd_unique_conflict``).

Why a separate module?
    psycopg2's native ``Error.diag`` is a read-only descriptor populated
    from libpq, so we cannot mutate it on a real ``UniqueViolation``
    instance. The retry helper reads ``getattr(exc, "diag", None)``, so
    a subclass that exposes ``diag`` as a property backed by a plain
    instance attribute is behaviorally indistinguishable from the real
    exception while preserving ``isinstance`` checks against the
    psycopg2 base classes.

    Originally these stubs were duplicated across
    ``test_crud_shared_retry.py`` and ``test_crud_account_unit.py``.
    PR #631 / Claude Review Issue 2 extracted them here BEFORE follow-up
    PRs (#623-#628) add equivalent tests for the seven sibling SCD CRUD
    sites, so the duplication does not compound.

Contents:
    - ``_FakeDiag``: Stand-in for psycopg2's Diagnostics object exposing
      a writable ``constraint_name``.
    - ``_StubUniqueViolation``: ``UniqueViolation`` subclass with a
      writable ``diag``.
    - ``_StubCheckViolation``: ``CheckViolation`` subclass with the same
      writable-diag pattern, used to verify the retry helper does NOT
      retry sibling IntegrityError types.
    - ``_make_unique_violation``: Factory for a ``UniqueViolation`` with
      a controlled ``constraint_name``.
    - ``_make_check_violation``: Factory for a ``CheckViolation`` whose
      constraint name simulates a balance non-negative CHECK violation.

This module contains NO test classes -- it is fixture code only.
"""

from __future__ import annotations

import psycopg2.errors


class _FakeDiag:
    """Stand-in for psycopg2's Diagnostics object exposing constraint_name."""

    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _StubUniqueViolation(psycopg2.errors.UniqueViolation):
    """UniqueViolation subclass that exposes a writable, fake ``diag``.

    psycopg2's native ``Error.diag`` is a read-only descriptor populated from
    libpq, so we cannot mutate it on a real ``UniqueViolation`` instance.
    Subclassing lets us override ``diag`` as a property backed by a plain
    instance attribute. The retry helper reads the attribute via
    ``getattr(exc, "diag", None)`` so this stub is behaviorally
    indistinguishable from a real ``UniqueViolation`` for the discrimination
    logic, while preserving ``isinstance`` checks against the real class.
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
