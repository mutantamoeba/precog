"""Unit tests for ``precog.database.constants`` — canonical SSOT constants.

These tests verify that ``CANONICAL_EVENT_LIFECYCLE_PHASES`` matches both
its specification (ADR-118 V2.40 Cohort 1 carry-forward item 3) and the
DDL CHECK constraint shipped in Migration 0070.

The Pattern 73 SSOT discipline that motivates this module also applies
*within this test file*: the load-bearing cross-validation test reads the
CHECK clause from Migration 0070 via regex parse rather than hardcoding
the 8 values a third time.  The two locations are (1) the constant in
``constants.py`` and (2) the SQL string literal in Migration 0070; this
test verifies they match.

Reference:
    - Issue #1038 (this PR's spec)
    - ADR-118 V2.40 Cohort 1 carry-forward item 3
    - Migration 0070 (``canonical_events_lifecycle_phase_check``)
    - DEVELOPMENT_PATTERNS V1.37 Pattern 73
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_type_hints

import pytest

from precog.database import constants
from precog.database.constants import CANONICAL_EVENT_LIFECYCLE_PHASES

pytestmark = [pytest.mark.unit]

# Path to Migration 0070, the second SSOT location for the lifecycle_phase
# vocabulary.  Resolved relative to the repo root (parents[3] == repo root
# from tests/unit/database/test_constants_unit.py).
MIGRATION_0070_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "precog"
    / "database"
    / "alembic"
    / "versions"
    / "0070_cohort_1_carryforward_hardening.py"
)

# Expected canonical 8 values.  Hardcoded ONCE here as the test's own
# specification — this is the single point at which a human re-asserts
# "these are the 8 values per ADR-118 V2.40."  Any future change to the
# canonical vocabulary requires updating this expected tuple AND the
# migration AND the constant in lockstep (and adding a new migration that
# alters the CHECK).
EXPECTED_PHASES: tuple[str, ...] = (
    "proposed",
    "listed",
    "pre_event",
    "live",
    "suspended",
    "settling",
    "resolved",
    "voided",
)


class TestCanonicalEventLifecyclePhasesContents:
    """Direct value/shape assertions on the constant."""

    def test_constant_matches_expected_8_values(self) -> None:
        """Constant equals the spec's exact 8-tuple in the documented order."""
        assert CANONICAL_EVENT_LIFECYCLE_PHASES == EXPECTED_PHASES

    def test_constant_length_is_exactly_8(self) -> None:
        """Drift detector — count must be exactly 8 (not 7, not 9)."""
        assert len(CANONICAL_EVENT_LIFECYCLE_PHASES) == 8

    def test_all_values_are_str(self) -> None:
        """Every entry is a ``str`` — type discipline for DDL comparison."""
        for value in CANONICAL_EVENT_LIFECYCLE_PHASES:
            assert isinstance(value, str), f"Expected str, got {type(value).__name__}: {value!r}"

    def test_constant_is_tuple(self) -> None:
        """Container is a tuple (immutable) — not a list or set."""
        assert isinstance(CANONICAL_EVENT_LIFECYCLE_PHASES, tuple)

    def test_constant_is_immutable(self) -> None:
        """Tuples have no item-assignment — defensive check on the contract."""
        with pytest.raises(TypeError):
            CANONICAL_EVENT_LIFECYCLE_PHASES[0] = "mutated"  # type: ignore[index]


class TestCanonicalEventLifecyclePhasesTyping:
    """Type-annotation discipline."""

    def test_constant_annotated_as_final_tuple_of_str(self) -> None:
        """``Final[tuple[str, ...]]`` is preserved in module annotations.

        With ``include_extras=True``, ``get_type_hints`` keeps the outer
        ``Final[...]`` wrapper; we unwrap it to assert the inner
        ``tuple[str, ...]`` shape.
        """
        from typing import Final

        hints = get_type_hints(constants, include_extras=True)
        assert "CANONICAL_EVENT_LIFECYCLE_PHASES" in hints, (
            "Constant missing type annotation in module __annotations__"
        )
        annotation = hints["CANONICAL_EVENT_LIFECYCLE_PHASES"]

        # Outer wrapper must be ``Final`` — distinguishes ``Final[tuple[...]]``
        # from a bare ``tuple[...]``.  __origin__ on ``Final[X]`` is the
        # ``Final`` special form itself.
        outer_origin = getattr(annotation, "__origin__", None)
        assert outer_origin is Final, (
            f"Expected Final outer wrapper, got {outer_origin!r} (annotation={annotation!r})"
        )

        # Unwrap ``Final[X]`` -> ``X`` (the inner tuple[str, ...] type).
        inner_args = getattr(annotation, "__args__", ())
        assert len(inner_args) == 1, (
            f"Expected exactly one type arg inside Final[...], got {inner_args!r}"
        )
        inner = inner_args[0]

        # Inner must be ``tuple[str, ...]`` — origin tuple, args (str, ...).
        inner_origin = getattr(inner, "__origin__", None)
        inner_args_inner = getattr(inner, "__args__", ())
        assert inner_origin is tuple, (
            f"Expected tuple origin inside Final, got {inner_origin!r} (inner={inner!r})"
        )
        assert inner_args_inner == (str, Ellipsis), (
            f"Expected (str, ...) args, got {inner_args_inner!r}"
        )


class TestMigration0070CheckMatchesConstant:
    """Load-bearing SSOT cross-validation: constant <-> Migration 0070 CHECK.

    This is the test that fires if the migration's SQL string and the
    constant ever drift apart.  It does NOT hardcode the 8 values a
    third time — it parses them out of the migration file.
    """

    def test_migration_0070_file_exists(self) -> None:
        """Migration 0070 path resolves — guard for the regex parse below."""
        assert MIGRATION_0070_PATH.is_file(), f"Migration 0070 not found at {MIGRATION_0070_PATH}"

    def test_migration_0070_check_values_equal_constant(self) -> None:
        """The 8 values in the CHECK clause match the constant set-equality.

        Regex parse strategy: find the CHECK clause, then extract every
        single-quoted token inside it.  Set-equality (not ordered) since
        the CHECK uses ``IN (...)`` which is order-independent at the SQL
        layer; the constant's tuple ordering is for Python consumers.
        """
        source = MIGRATION_0070_PATH.read_text(encoding="utf-8")

        # Locate the CHECK clause for lifecycle_phase.  Pattern matches
        # ``CHECK (lifecycle_phase IN (...))`` in the migration's
        # multi-line SQL string concatenation.  ``re.DOTALL`` lets ``.``
        # cross newlines because the SQL spans multiple Python string
        # literals concatenated by adjacent-string-literal syntax.
        check_match = re.search(
            r"CHECK\s*\(\s*lifecycle_phase\s+IN\s*\((.*?)\)\)",
            source,
            re.DOTALL | re.IGNORECASE,
        )
        assert check_match is not None, (
            "Could not find ``CHECK (lifecycle_phase IN (...))`` clause "
            f"in {MIGRATION_0070_PATH.name} — has the migration been "
            "rewritten?  Update this test if the SQL shape changed."
        )

        # Extract every single-quoted token inside the matched CHECK body.
        check_body = check_match.group(1)
        migration_values = tuple(re.findall(r"'([^']+)'", check_body))

        assert len(migration_values) == 8, (
            f"Migration 0070 CHECK has {len(migration_values)} values, "
            f"expected 8: {migration_values!r}"
        )

        # Set-equality — order in the SQL IN-list is independent.
        assert set(migration_values) == set(CANONICAL_EVENT_LIFECYCLE_PHASES), (
            "Migration 0070 CHECK values diverge from "
            "CANONICAL_EVENT_LIFECYCLE_PHASES.\n"
            f"  Migration: {sorted(migration_values)}\n"
            f"  Constant:  {sorted(CANONICAL_EVENT_LIFECYCLE_PHASES)}\n"
            "  Fix: update both the migration (new alembic revision) and "
            "the constant in lockstep, per Pattern 73 SSOT."
        )
