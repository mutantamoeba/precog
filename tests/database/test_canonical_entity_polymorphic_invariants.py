"""Pattern 82 V2 polymorphic invariant tests for canonical_entity (LOAD-BEARING).

This file is the **mandatory compensating mechanism** for Pattern 82 V2 on
the canonical_entity table -- ADR-118 V2.40 Item 4 (lines ~17580-17590) and
DEVELOPMENT_PATTERNS V1.37 Pattern 82 V2 (lines ~12235-12239) BOTH name
this exact file path:

    > **Mandatory compensating mechanism:** every Pattern 82 application
    > MUST be paired with a regression test that asserts no row carries a
    > ``ref_*_id`` for a non-matching discriminator value.  The test is
    > **load-bearing** -- it MUST NOT be skipped, retired, or admitted to
    > any audit bypass set.  For the canonical_entity instance, the test
    > lives at ``tests/database/test_canonical_entity_polymorphic_invariants.py``
    > (folded into #1021 scope).

**THIS FILE MUST NOT BE RETIRED OR SKIPPED.**  Pattern 82 V2 forward-only
direction policy is intentionally LESS strict at the trigger level
(forward-only: "team requires ref_team_id"), preserving polymorphic-
overloading future-extensibility (ADR-118 V2.38 decision #5, ratified in
V2.40).  The compensating regression test below is the load-bearing
invariant -- it asserts the inverse direction at the application
boundary, which the trigger intentionally does not enforce.

This file is at the top-level ``tests/database/`` directory (NOT
``tests/integration/database/``) per ADR-118 V2.40 path pin.  The path
itself is load-bearing -- audit-bypass mechanisms keyed on directory
location must NOT include this path.

Test framing distinct from #1012 trigger DDL/body coverage:
    - ``tests/integration/database/test_migration_0068_canonical_entity_foundation.py``
      tests verify the trigger DDL exists and its body raises on the
      forward-direction violation (post-migration shape).
    - This file (Pattern 82 V2 invariant tests) verifies the invariant
      holds when accessed *through the canonical CRUD interface*
      (``crud_canonical_entity.create_canonical_entity()``) AND verifies
      the load-bearing inverse-direction invariant via direct DB query
      (no row has a mismatched discriminator + ref_*_id pairing).

Markers:
    @pytest.mark.integration: real DB required (uses session-scoped
    ``db_pool`` fixture from ``tests/conftest.py``; pytest discovers
    parent conftest fixtures across directories).

Cleanup discipline:
    All test rows use the ``TEST-1021-`` entity_key prefix; cleanup
    targets that prefix in try/finally blocks.  No bulk teardown -- each
    test cleans up its own data.

Reference:
    - ``docs/foundation/ARCHITECTURE_DECISIONS_V2.40.md`` lines
      ~17580-17590 (Item 4 -- Pattern 82 V2 + this file's path pin)
    - ``docs/guides/DEVELOPMENT_PATTERNS_V1.38.md`` Pattern 82 V2
      (lines ~12239-12245)
    - ``src/precog/database/crud_canonical_entity.py``
    - ``src/precog/database/alembic/versions/0068_canonical_entity_foundation.py``
    - ``tests/integration/database/test_migration_0068_canonical_entity_foundation.py``
      (#1012 -- sibling DDL/body coverage)

Issue: #1021 (Cohort 1 Pattern 14 retro -- Slice B)
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg2
import pytest

from precog.database.connection import get_cursor
from precog.database.crud_canonical_entity import (
    create_canonical_entity,
    get_canonical_entity_kind_id_by_kind,
)

# This file is in tests/database/ (not tests/integration/), but it requires
# a real DB.  The marker is what gates real-DB collection -- the directory
# location is purely the ADR-pinned semantic frame.
pytestmark = [pytest.mark.integration]


# =============================================================================
# Helpers
# =============================================================================


def _real_team_id() -> int:
    """Return a real teams.team_id for the team-kind happy path.

    The trigger only enforces ``entity_kind='team' => ref_team_id NOT NULL``;
    the FK on ``ref_team_id REFERENCES teams(team_id)`` enforces the value
    is a real team id.  Fetch one from the live seed.  Mirrors the
    ``_real_team_id()`` helper in
    ``test_migration_0068_canonical_entity_foundation.py``.
    """
    with get_cursor() as cur:
        cur.execute("SELECT team_id FROM teams ORDER BY team_id LIMIT 1")
        row = cur.fetchone()
    assert row is not None, "teams table must have at least one seed row"
    return int(row["team_id"])


def _cleanup_entity_key(entity_key: str) -> None:
    """Delete any canonical_entity row matching the given entity_key.

    Cleanup discipline: each test that inserts uses TEST-1021- prefix on
    entity_key, and calls this helper in a finally block.  No bulk
    teardown.
    """
    with get_cursor(commit=True) as cur:
        cur.execute(
            "DELETE FROM canonical_entity WHERE entity_key = %s",
            (entity_key,),
        )


# =============================================================================
# Pattern 82 V2 forward-direction invariant -- through the CRUD path
#
# These tests exercise the trigger by calling the CRUD function (not raw
# SQL).  They mirror #1012's TestConstraintTrigger semantically but at the
# application boundary instead of the DB boundary.
# =============================================================================


def test_pattern_82_v2_invariant_blocks_team_kind_with_null_ref_team_id(
    db_pool: Any,
) -> None:
    """``create_canonical_entity(entity_kind='team', ref_team_id=None)`` must raise.

    Pattern 82 V2 forward-direction: the trigger fires when the CRUD layer
    inserts a team-kind row with NULL ref_team_id.  The CRUD layer does
    NOT pre-validate (Pattern 82 V2 forward-only -- DB is SSOT), so the
    psycopg2.errors.RaiseException propagates to the caller unwrapped.
    """
    team_kind_id = get_canonical_entity_kind_id_by_kind("team")
    assert team_kind_id is not None, "canonical_entity_kinds seed missing 'team'"
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1021-p82v2-block-{suffix}"

    _cleanup_entity_key(entity_key)
    try:
        with pytest.raises(psycopg2.errors.RaiseException):
            create_canonical_entity(
                entity_kind_id=team_kind_id,
                entity_key=entity_key,
                display_name="Test Team With NULL Backref (Pattern 82 V2)",
                ref_team_id=None,
            )
    finally:
        _cleanup_entity_key(entity_key)


def test_pattern_82_v2_invariant_allows_team_kind_with_valid_ref_team_id(
    db_pool: Any,
) -> None:
    """``create_canonical_entity(entity_kind='team', ref_team_id=<valid>)`` must succeed.

    Pattern 82 V2 forward-direction happy path: team-kind rows MUST carry
    a non-NULL ref_team_id; the trigger allows the INSERT when this rule
    is satisfied.
    """
    team_kind_id = get_canonical_entity_kind_id_by_kind("team")
    assert team_kind_id is not None, "canonical_entity_kinds seed missing 'team'"
    real_team_id = _real_team_id()
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1021-p82v2-ok-{suffix}"

    _cleanup_entity_key(entity_key)
    try:
        row = create_canonical_entity(
            entity_kind_id=team_kind_id,
            entity_key=entity_key,
            display_name="Test Team With Valid Backref (Pattern 82 V2)",
            ref_team_id=real_team_id,
        )
        assert row["id"] is not None, "INSERT must return the new id on success"
        assert row["entity_kind_id"] == team_kind_id
        assert row["ref_team_id"] == real_team_id
        assert row["entity_key"] == entity_key
    finally:
        _cleanup_entity_key(entity_key)


def test_pattern_82_v2_invariant_skips_non_team_kind_with_null_ref_team_id(
    db_pool: Any,
) -> None:
    """``create_canonical_entity(entity_kind='fighter', ref_team_id=None)`` must succeed.

    Pattern 82 V2 forward-direction skip path: the trigger ONLY fires when
    entity_kind resolves to 'team'.  Non-team kinds with NULL ref_team_id
    are the typical, valid case and pass through unchanged.
    """
    fighter_kind_id = get_canonical_entity_kind_id_by_kind("fighter")
    assert fighter_kind_id is not None, "canonical_entity_kinds seed missing 'fighter'"
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1021-p82v2-skip-{suffix}"

    _cleanup_entity_key(entity_key)
    try:
        row = create_canonical_entity(
            entity_kind_id=fighter_kind_id,
            entity_key=entity_key,
            display_name="Test Fighter (no team back-ref, Pattern 82 V2)",
            ref_team_id=None,
        )
        assert row["id"] is not None, (
            "fighter-kind row with NULL ref_team_id must succeed (trigger skip path)"
        )
        assert row["ref_team_id"] is None
    finally:
        _cleanup_entity_key(entity_key)


def test_pattern_82_v2_invariant_blocks_update_morphing_to_team_kind_with_null_ref_team_id(
    db_pool: Any,
) -> None:
    """UPDATE morphing entity_kind -> 'team' on a NULL ref_team_id row must raise.

    Pattern 82 V2 forward-direction UPDATE coverage: the trigger fires on
    ``UPDATE OF entity_kind_id, ref_team_id``.  Seed a fighter row (NULL
    ref_team_id allowed by the skip path), then attempt to morph it into a
    team row -- the trigger must block.

    Note: this test exercises the UPDATE path via raw SQL because Slice B
    of #1021 deliberately ships INSERT-only CRUD (no update_canonical_entity()
    -- see crud_canonical_entity module docstring "UPDATE / RETIRE coverage"
    note).  When #1007 lands the BEFORE UPDATE trigger retrofit and an
    update helper is added, this test should be re-pointed at the helper.
    """
    fighter_kind_id = get_canonical_entity_kind_id_by_kind("fighter")
    team_kind_id = get_canonical_entity_kind_id_by_kind("team")
    assert fighter_kind_id is not None, "canonical_entity_kinds seed missing 'fighter'"
    assert team_kind_id is not None, "canonical_entity_kinds seed missing 'team'"
    suffix = uuid.uuid4().hex[:8]
    entity_key = f"TEST-1021-p82v2-update-{suffix}"

    _cleanup_entity_key(entity_key)
    try:
        # Step 1: seed a fighter row via CRUD (NULL ref_team_id allowed by trigger skip).
        create_canonical_entity(
            entity_kind_id=fighter_kind_id,
            entity_key=entity_key,
            display_name="Test Fighter -> Team morph attempt (Pattern 82 V2)",
            ref_team_id=None,
        )

        # Step 2: morph entity_kind_id to 'team' via raw SQL (no update CRUD
        # in Slice B).  The trigger must fire on the UPDATE OF entity_kind_id.
        with pytest.raises(psycopg2.errors.RaiseException):
            with get_cursor(commit=True) as cur:
                cur.execute(
                    """
                    UPDATE canonical_entity
                    SET entity_kind_id = %s
                    WHERE entity_key = %s
                    """,
                    (team_kind_id, entity_key),
                )
    finally:
        _cleanup_entity_key(entity_key)


# =============================================================================
# Pattern 82 V2 INVERSE-direction invariant -- LOAD-BEARING compensating test
#
# This is the canonical "compensating mechanism" cited in DEVELOPMENT_PATTERNS
# V1.37 Pattern 82 V2 lines ~12235-12239 and ADR-118 V2.40 Item 4 lines
# ~17580-17590.  The forward-only trigger does NOT enforce
# "non-team kind => ref_team_id IS NULL" (that direction is intentionally
# left open per ADR-118 V2.38 decision #5 for polymorphic-overloading
# future-extensibility).  The mandatory compensating mechanism is THIS
# regression test, which asserts that no row in canonical_entity carries
# a ref_team_id for a non-team discriminator value.
#
# THIS TEST IS LOAD-BEARING.  IT MUST NOT BE RETIRED OR SKIPPED.
# =============================================================================


def test_pattern_82_v2_no_non_team_kind_carries_ref_team_id(db_pool: Any) -> None:
    """LOAD-BEARING: no canonical_entity row has ref_team_id NOT NULL when
    entity_kind != 'team'.

    Pattern 82 V2 forward-only direction policy intentionally does NOT
    enforce the inverse direction at the trigger level (preserves
    polymorphic-overloading future-extensibility per ADR-118 V2.38
    decision #5, ratified in V2.40).  This regression test is the
    mandatory compensating mechanism per Pattern 82 V2.

    If this test fails, either:
      (a) a misconfigured seed/migration introduced a non-team row with
          ref_team_id set (a Pattern 82 V2 inverse-direction violation),
          OR
      (b) ADR-118 was deliberately amended to permit polymorphic
          overloading of ref_team_id (in which case this test should be
          relaxed in tandem with the ADR amendment, NOT silenced).

    Test scope: scans the entire canonical_entity table.  Lightweight
    aggregate query -- safe to run on production-sized tables.

    REMOVAL POLICY: this test is named in ADR-118 V2.40 Item 4 (lines
    ~17580-17590) and DEVELOPMENT_PATTERNS V1.37 Pattern 82 V2 (lines
    ~12235-12239) as MUST NOT BE RETIRED.  Removing or skipping it
    requires an ADR amendment.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT ce.id, ce.entity_key, ce.ref_team_id, k.entity_kind
            FROM canonical_entity ce
            JOIN canonical_entity_kinds k ON k.id = ce.entity_kind_id
            WHERE k.entity_kind <> 'team'
              AND ce.ref_team_id IS NOT NULL
            """
        )
        violations = cur.fetchall()

    assert violations == [], (
        "Pattern 82 V2 INVERSE-direction violation: "
        f"{len(violations)} canonical_entity row(s) have a non-team entity_kind "
        f"yet carry a non-NULL ref_team_id. Violation rows: {violations!r}.  "
        "Per ADR-118 V2.40 Item 4 + DEVELOPMENT_PATTERNS V1.37 Pattern 82 V2, "
        "the forward-only trigger does NOT enforce this direction at the "
        "DB layer -- this test is the load-bearing compensating mechanism.  "
        "If the violation is intentional (e.g., polymorphic-overloading "
        "feature), the ADR must be amended in tandem with relaxing this "
        "test; do NOT silently skip."
    )


def test_pattern_82_v2_load_bearing_test_file_path_is_adr_pinned(db_pool: Any) -> None:
    """Self-referential pin: this file's path is named in ADR-118 V2.40.

    The file path ``tests/database/test_canonical_entity_polymorphic_invariants.py``
    is itself load-bearing per ADR-118 V2.40 Item 4 + DEVELOPMENT_PATTERNS
    V1.37 Pattern 82 V2.  Audit-bypass mechanisms (test type audits,
    coverage-skip lists, test discovery filters) keyed on directory
    location MUST NOT include this path.

    This test is intentionally minimal -- its purpose is to surface the
    path-pin contract in test output and fail loudly if the file is moved
    without an ADR amendment.  The assertion compares ``__file__`` against
    the expected path suffix; if the file is moved, the assertion fails
    and the failure trace cites the ADR.
    """
    expected_suffix = "tests/database/test_canonical_entity_polymorphic_invariants.py"
    # Normalize Windows backslashes for the comparison
    actual_path = __file__.replace("\\", "/")
    assert actual_path.endswith(expected_suffix), (
        f"Pattern 82 V2 load-bearing test file MOVED from ADR-pinned path.  "
        f"Expected suffix: {expected_suffix!r}.  Actual: {actual_path!r}.  "
        "ADR-118 V2.40 Item 4 (lines ~17580-17590) and DEVELOPMENT_PATTERNS "
        "V1.37 Pattern 82 V2 (lines ~12235-12239) both name this exact path; "
        "moving requires an ADR amendment."
    )
