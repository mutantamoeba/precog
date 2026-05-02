"""Pattern 73 SSOT three-way parity: CANONICAL_EVENT_LIFECYCLE_PHASES vs DDL CHECKs.

Verifies the 8-value lifecycle_phase vocabulary is consistent across all
THREE authoritative locations:

    1. ``src/precog/database/constants.py:CANONICAL_EVENT_LIFECYCLE_PHASES``
       -- Python canonical home (the SSOT anchor).
    2. ``canonical_events.lifecycle_phase`` CHECK constraint shipped in
       Migration 0070 (V2.40 Cohort 1 carry-forward Item 3).
    3. ``canonical_event_phase_log.new_phase`` AND ``previous_phase`` CHECK
       constraints shipped in Migration 0079 (slot 0079, Cohort 4).

Drift between any of these locations would silently produce state-machine
bugs (a CRUD-side write of an unknown phase rejected by DDL but passing
Python validation, or vice versa).  The Pattern 73 SSOT discipline says
"any rule, value, formula, or logic that appears in more than one location
MUST have ONE canonical definition plus pointers/imports".

This test queries the LIVE PG ``pg_get_constraintdef`` output for both
CHECK constraints and asserts set-equality with the Python constant.

Pattern 73 SSOT (CLAUDE.md Critical Pattern #8):
    The constant in constants.py is the canonical source.  Both DDL CHECKs
    in Migration 0070 + Migration 0079 must mirror it.  Adding a new phase
    requires lockstep update of all three locations.

Reference:
    - ``src/precog/database/constants.py:CANONICAL_EVENT_LIFECYCLE_PHASES``
    - ``src/precog/database/alembic/versions/0070_cohort_1_carryforward_hardening.py``
    - ``src/precog/database/alembic/versions/0079_canonical_event_phase_log.py``
    - ``tests/unit/database/test_constants_unit.py`` (parses Migration 0070
      via regex; this test queries the live DB instead)
    - Slot 0079 build spec § 3
    - DEVELOPMENT_PATTERNS V1.40 Pattern 73 SSOT

Markers:
    @pytest.mark.integration: real DB required.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from precog.database.connection import get_cursor
from precog.database.constants import CANONICAL_EVENT_LIFECYCLE_PHASES

pytestmark = [pytest.mark.integration]


def _extract_check_values(constraint_def: str) -> set[str]:
    """Extract every single-quoted string literal from a CHECK constraint def.

    Pattern: PG returns CHECK constraints in the form
        ``CHECK (((col)::text = ANY ((ARRAY['v1'::character varying, ...])::text[])))``.
    The single-quoted tokens are the IN-list values.  Set-form because
    the order is irrelevant at the SQL layer.
    """
    return set(re.findall(r"'([^']+)'", constraint_def))


def test_canonical_events_lifecycle_phase_check_matches_constant(db_pool: Any) -> None:
    """canonical_events.lifecycle_phase CHECK contains exactly the 8 constant values."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_events'::regclass
              AND contype = 'c'
              AND conname = 'canonical_events_lifecycle_phase_check'
            """
        )
        row = cur.fetchone()
    assert row is not None, "canonical_events_lifecycle_phase_check must exist post-Migration 0070"
    db_values = _extract_check_values(row["def"])
    constant_values = set(CANONICAL_EVENT_LIFECYCLE_PHASES)
    assert db_values == constant_values, (
        "canonical_events.lifecycle_phase CHECK diverged from "
        "CANONICAL_EVENT_LIFECYCLE_PHASES.\n"
        f"  DB CHECK:  {sorted(db_values)}\n"
        f"  Constant:  {sorted(constant_values)}\n"
        "  Fix: update both the migration (new alembic revision) and "
        "the constant in lockstep, per Pattern 73 SSOT."
    )


def test_canonical_event_phase_log_new_phase_check_matches_constant(db_pool: Any) -> None:
    """canonical_event_phase_log.new_phase CHECK contains exactly the 8 constant values."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_phase_log'::regclass
              AND contype = 'c'
              AND conname = 'ck_canonical_event_phase_log_new_phase'
            """
        )
        row = cur.fetchone()
    assert row is not None, "ck_canonical_event_phase_log_new_phase must exist post-Migration 0079"
    db_values = _extract_check_values(row["def"])
    constant_values = set(CANONICAL_EVENT_LIFECYCLE_PHASES)
    assert db_values == constant_values, (
        "canonical_event_phase_log.new_phase CHECK diverged from "
        "CANONICAL_EVENT_LIFECYCLE_PHASES.\n"
        f"  DB CHECK:  {sorted(db_values)}\n"
        f"  Constant:  {sorted(constant_values)}\n"
        "  Fix: update both the migration (new alembic revision) and "
        "the constant in lockstep, per Pattern 73 SSOT."
    )


def test_canonical_event_phase_log_previous_phase_check_matches_constant(
    db_pool: Any,
) -> None:
    """canonical_event_phase_log.previous_phase CHECK contains exactly the 8 constant values.

    Note: previous_phase CHECK is NULL-tolerant; the value-set inside the
    OR-IN clause still mirrors the same 8 values.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conrelid = 'canonical_event_phase_log'::regclass
              AND contype = 'c'
              AND conname = 'ck_canonical_event_phase_log_previous_phase'
            """
        )
        row = cur.fetchone()
    assert row is not None, (
        "ck_canonical_event_phase_log_previous_phase must exist post-Migration 0079"
    )
    constraint_def = row["def"]
    # NULL-tolerant CHECK form must include "IS NULL".
    assert "IS NULL" in constraint_def.upper(), (
        f"previous_phase CHECK must be NULL-tolerant (IS NULL OR ...); got: {constraint_def!r}"
    )

    db_values = _extract_check_values(constraint_def)
    constant_values = set(CANONICAL_EVENT_LIFECYCLE_PHASES)
    assert db_values == constant_values, (
        "canonical_event_phase_log.previous_phase CHECK diverged from "
        "CANONICAL_EVENT_LIFECYCLE_PHASES.\n"
        f"  DB CHECK:  {sorted(db_values)}\n"
        f"  Constant:  {sorted(constant_values)}\n"
        "  Fix: update both the migration (new alembic revision) and "
        "the constant in lockstep, per Pattern 73 SSOT."
    )


def test_three_way_parity_constant_matches_both_db_checks(db_pool: Any) -> None:
    """LOAD-BEARING three-way SSOT parity test.

    Single test that asserts ALL THREE locations agree:
        constants.py:CANONICAL_EVENT_LIFECYCLE_PHASES
        ==
        canonical_events.lifecycle_phase CHECK values
        ==
        canonical_event_phase_log.new_phase CHECK values
        ==
        canonical_event_phase_log.previous_phase CHECK values (NULL-tolerant subset)

    Drift between any of these would have produced silent state-machine
    bugs.  This is the canonical Pattern 73 SSOT enforcement gate.
    """
    constant_values = set(CANONICAL_EVENT_LIFECYCLE_PHASES)
    assert len(constant_values) == 8, (
        f"CANONICAL_EVENT_LIFECYCLE_PHASES must have 8 values; got {len(constant_values)}"
    )

    with get_cursor() as cur:
        cur.execute(
            """
            SELECT conname, pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conname IN (
                'canonical_events_lifecycle_phase_check',
                'ck_canonical_event_phase_log_new_phase',
                'ck_canonical_event_phase_log_previous_phase'
            )
            ORDER BY conname
            """
        )
        rows = cur.fetchall()
    assert len(rows) == 3, (
        f"All 3 CHECK constraints must exist post-Migration 0079; got {len(rows)}: "
        f"{[r['conname'] for r in rows]}"
    )

    constraint_value_sets = {row["conname"]: _extract_check_values(row["def"]) for row in rows}

    for conname, db_values in constraint_value_sets.items():
        assert db_values == constant_values, (
            f"Three-way SSOT parity violation: {conname} value-set diverged "
            f"from CANONICAL_EVENT_LIFECYCLE_PHASES.\n"
            f"  DB CHECK ({conname}):  {sorted(db_values)}\n"
            f"  Constant:               {sorted(constant_values)}"
        )
